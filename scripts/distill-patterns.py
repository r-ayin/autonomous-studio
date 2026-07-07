#!/usr/bin/env python3
"""distill-patterns.py — 决策习惯蒸馏器（闭合"结果→pattern"反馈线）

修复引擎核心断裂：pattern accuracy 由 LLM 自评 → 确定性从 case outcome 计算；
patterns.md 与 calibration.json 自动同步；僵尸 pattern 激活或退役。

三步（ExpeL 式适配版）:
  Step 1 (确定性, 零 token): 扫描 case-*.json → 按 new_pattern_discovered 聚合 →
          从 outcome 计算实际 actions/approved/accuracy → 同步 calibration + patterns.md
  Step 2 (可选 LLM, --llm): 对 accuracy 低的 pattern，配对 success/failure case，
          调用 GLM 提取 ADD/EDIT/REMOVE 规则操作（ExpeL parse_rules 式）
  Step 3 (确定性): 执行规则操作，跑 verify-pattern.sh 门禁，通过才落盘

设计原则（来自研究）:
  - 执行者不评判自己：accuracy 由脚本从 case outcome 算，非 LLM 自评
  - 确定性 > 提示词约束：Step1/3 零 LLM，bash gate 不可协商
  - 最小样本底线：<2 个有 outcome 的 case → accuracy 标 indeterminate，不参与判定
  - 鲁棒：calibration.json 损坏 → 备份重建骨架；patterns.md 缺失 → 从 case 重建

用法:
  python3 scripts/distill-patterns.py --project .            # 干跑（只报告）
  python3 scripts/distill-patterns.py --project . --apply    # 落盘
  python3 scripts/distill-patterns.py --project . --apply --llm  # 含 LLM 蒸馏
"""
import os, sys, json, glob, argparse, subprocess, re
from datetime import datetime, timezone

# Case schema outcome enum (见 audit-cycle-state.json _case_outcome_enum + loop prompt):
#   succeeded | failed | rolled_back | superseded | blocked
# 旧版本曾误用 success/failure/partial_success/user_rejected/aborted，导致所有 case
# 被判 indeterminate、accuracy 全为 0 —— AS-PERSIST-H01 (audit-2026-07-03-007)。
SUCCESS_OUTCOMES = {"succeeded"}
FAILURE_OUTCOMES = {"failed", "rolled_back", "superseded"}
# blocked 不计入成功也不计入失败：它是"等待外部动作"，不应拉低 pattern accuracy，
# 也不应虚高成功率。单独归类，统计时排除在分母外。
BLOCKED_OUTCOMES = {"blocked"}
OUTCOME_ENUM = SUCCESS_OUTCOMES | FAILURE_OUTCOMES | BLOCKED_OUTCOMES | {"indeterminate"}


def now_ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json_robust(path, default=None):
    """鲁棒加载：损坏/缺失/权限问题返回 default；不吞 KeyboardInterrupt/SystemExit/MemoryError（SCRIPTS-L04）"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, TypeError, UnicodeDecodeError):
        # OSError 覆盖 FileNotFoundError/PermissionError/IOError；
        # ValueError+TypeError+UnicodeDecodeError 覆盖 json.load 解析异常。
        # 显式放过 KeyboardInterrupt/SystemExit/MemoryError，避免阻塞中断与 OOM 静默化。
        return default


def load_calibration(cal_path):
    """加载 calibration.json；损坏则备份+返回干净骨架"""
    cal = load_json_robust(cal_path)
    if cal is None or "patterns" not in cal:
        # 损坏 → 备份重建
        if os.path.exists(cal_path):
            os.rename(cal_path, cal_path + ".broken." + now_ts().replace(":", ""))
            print(f"⚠️ calibration.json 损坏，已备份，重建骨架")
        cal = {
            "$schema": "autonomous-studio-decision-calibration/1.0",
            "initialized": now_ts(),
            "last_distill": None,
            "cold_start_protocol_version": "2.2",
            "checkpoint_protection_enabled": True,
            "patterns": {},
            "l3_findings": {},
        }
    cal.setdefault("patterns", {})
    cal.setdefault("l3_findings", {})
    return cal


def load_cases(decisions_dir):
    """加载所有 case-*.json，返回 [{case_file, ...}]"""
    cases = []
    for cf in sorted(glob.glob(os.path.join(decisions_dir, "case-*.json"))):
        c = load_json_robust(cf)
        if not c:
            continue
        cases.append(c)
    return cases


def infer_outcome(case):
    """从 case 提取 outcome。优先显式字段；否则从 action_level + retrospect 推断（标 inferred）"""
    # 显式字段（新 schema）
    for path in [("outcome",), ("retrospect", "outcome"), ("execute", "outcome")]:
        v = case
        try:
            for k in path:
                v = v[k]
            if v and v in OUTCOME_ENUM:
                return v, "explicit"
        except (KeyError, TypeError):
            pass
    # 推断（旧 case）
    decide = case.get("decide", {})
    retro = case.get("retrospect", {})
    exec_ = case.get("execute", {})
    level = decide.get("action_level", "")
    lessons = " ".join(retro.get("lessons_learned", []) or [])
    worked = retro.get("what_worked", [])
    improve = retro.get("what_to_improve", [])
    if re.search(r"失败|failed|blocked|aborted|错误|bug", lessons, re.I) or not exec_.get("actions_taken"):
        return "failure", "inferred"
    if level in ("ACT_NOTIFY", "ACT_SILENT") and exec_.get("actions_taken"):
        return "success", "inferred"
    if level == "SUGGEST":
        return "indeterminate", "inferred"
    return "indeterminate", "inferred"


def _sig_from_discovered(s):
    """从 new_pattern_discovered 长描述提取签名前缀。
    case 存的是 'l3:infrastructure:archive:batch_case_sync — L3深度检查中...' 或
    'cold_start_exhaustion: 当冷启动...' → 取 ' — ' 或 ': ' 前的部分。
    """
    if not s:
        return ""
    s = s.strip()
    for sep in [" — ", " – ", " - "]:
        if sep in s:
            return s.split(sep, 1)[0].strip()
    # 无破折号：取 ': ' 前的（': ' 后通常是中文描述）
    if ": " in s:
        head = s.split(": ", 1)[0]
        # head 可能就是签名（如 'cold_start_exhaustion'）或 'a:b:c' 签名
        return head.strip()
    return s


def match_case_to_cal_keys(case, cal_patterns):
    """把一个 case 关联到 calibration 的 pattern key 列表。
    两条桥： (1) case.new_pattern_discovered 的签名前缀 匹配 cal key（相等/前缀）；
            (2) cal pattern 的 source 字段含该 case_id。
    """
    matched = set()
    case_id = case.get("case_id", "")
    npd = (case.get("retrospect") or {}).get("new_pattern_discovered") or ""
    sig = _sig_from_discovered(npd)
    for key, pdata in cal_patterns.items():
        # 桥 2：source 含 case_id
        src = str(pdata.get("source", ""))
        if case_id and case_id in src:
            matched.add(key)
            continue
        # 桥 1：签名前缀匹配
        if sig and (sig == key or sig.startswith(key) or key.startswith(sig)):
            matched.add(key)
    return matched


def extract_pattern_key(case):
    """从 case 提取 NEW pattern key（用于注册 cal 里没有的新 pattern）。
    用签名前缀，不是长描述。"""
    retro = case.get("retrospect", {}) or {}
    p = retro.get("new_pattern_discovered")
    return _sig_from_discovered(p) if p else None


def step1_recompute(cal, cases):
    """确定性：从 case outcome 重算每个 pattern 的 actions/approved/accuracy"""
    patterns = cal["patterns"]
    # 建 cal key → 关联 cases 的映射
    pat_cases = {key: [] for key in patterns}  # key -> [(outcome, case_id, confidence, how)]
    unmatched_sigs = {}  # 新签名 → [(outcome, case_id, ...)]  用于注册
    for c in cases:
        outcome, how = infer_outcome(c)
        conf = (c.get("decide", {}) or {}).get("confidence_score", 0)
        matched = match_case_to_cal_keys(c, patterns)
        if matched:
            for key in matched:
                pat_cases.setdefault(key, []).append((outcome, c.get("case_id", "?"), conf, how))
        else:
            # 没匹配到任何已有 cal pattern → 收集为新签名
            sig = extract_pattern_key(c)
            if sig:
                unmatched_sigs.setdefault(sig, []).append((outcome, c.get("case_id", "?"), conf, how))

    # 对每个已有 pattern 重算
    for key, pdata in patterns.items():
        cs = pat_cases.get(key, [])
        pdata["actions"] = len(cs)
        if cs:
            approved = sum(1 for o, _, _, _ in cs if o in SUCCESS_OUTCOMES)
            verified = [o for o, _, _, h in cs if h == "explicit"]
            pdata["approved"] = approved
            if len(verified) >= 2:
                v_approved = sum(1 for o in verified if o in SUCCESS_OUTCOMES)
                pdata["accuracy"] = round(v_approved / len(verified), 3)
                pdata["accuracy_basis"] = f"verified:{len(verified)}"
            elif cs:
                pdata["accuracy"] = round(approved / len(cs), 3)
                pdata["accuracy_basis"] = f"inferred:{len(cs)}(需更多显式 outcome)"
            else:
                pdata["accuracy"] = 0.0
                pdata["accuracy_basis"] = "no_cases"
        else:
            pdata["actions"] = 0
            pdata["approved"] = 0
            pdata["accuracy"] = 0.0
            pdata["accuracy_basis"] = "zombie(无 case 关联,待退役)"

    # case 里发现但 calibration 没有的 pattern → 注册
    new_count = 0
    for sig, cs in unmatched_sigs.items():
        if sig in patterns:
            continue
        approved = sum(1 for o, _, _, _ in cs if o in SUCCESS_OUTCOMES)
        verified = [o for o, _, _, h in cs if h == "explicit"]
        acc = round(sum(1 for o in verified if o in SUCCESS_OUTCOMES) / len(verified), 3) if len(verified) >= 2 else 0.0
        basis = f"verified:{len(verified)}" if len(verified) >= 2 else "new(待积累显式 outcome)"
        patterns[sig] = {
            "actions": len(cs),
            "approved": approved,
            "accuracy": acc,
            "accuracy_basis": basis,
            "adjusted_base_score": 10,
            "source": "engine-discovered:" + cs[0][1],
        }
        new_count += 1
        pat_cases[sig] = cs

    cal["last_distill"] = now_ts()
    return pat_cases, new_count


def parse_patterns_md(md_path):
    """解析 patterns.md 现有条目（### Pattern: xxx + 签名前缀）。
    条目格式：'- **签名前缀**: `key`' — 捕获反引号内的 key。
    """
    entries = {}  # signature -> section text
    if not os.path.exists(md_path):
        return entries
    text = open(md_path, "r", encoding="utf-8").read()
    for block in re.split(r"\n(?=### Pattern:)", text):
        # 优先：签名前缀后反引号包裹的 key
        m = re.search(r"签名前缀[^`]*`([^`]+)`", block)
        if not m:
            # 退化：### Pattern: name 行本身
            m = re.search(r"### Pattern:\s*(.+)", block)
            if m:
                entries[m.group(1).strip()] = block.strip()
                continue
        if m:
            sig = m.group(1).strip()
            entries[sig] = block.strip()
    return entries


def dedup_patterns_md(md_path):
    """去重 patterns.md：按签名前缀保留首条，去掉重复追加的条目。"""
    if not os.path.exists(md_path):
        return 0
    text = open(md_path, "r", encoding="utf-8").read()
    # 分离 header 和条目
    parts = re.split(r"\n(?=### Pattern:)", text)
    header = parts[0]
    blocks = parts[1:]
    seen = {}
    order = []
    for b in blocks:
        m = re.search(r"签名前缀[^`]*`([^`]+)`", b)
        sig = m.group(1).strip() if m else None
        if sig is None:
            m2 = re.search(r"### Pattern:\s*(.+)", b)
            sig = m2.group(1).strip() if m2 else None
        if sig and sig in seen:
            continue  # 重复，跳过
        if sig:
            seen[sig] = True
        order.append(b)
    removed = len(blocks) - len(order)
    if removed > 0:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(header + "\n".join(order))
    return removed


def step3_sync_patterns_md(cal, md_path):
    """确定性：去重 + 同步 patterns.md 与 calibration 的 pattern key"""
    removed = dedup_patterns_md(md_path)
    if removed:
        print(f"  patterns.md 去重：移除 {removed} 条重复")
    existing = parse_patterns_md(md_path)
    cal_keys = set(cal["patterns"].keys())
    md_keys = set(existing.keys())
    missing_in_md = cal_keys - md_keys  # calibration 有、patterns.md 没有
    if not missing_in_md:
        return 0
    # 追加缺失条目
    header = ""
    body = ""
    if os.path.exists(md_path):
        body = open(md_path, "r", encoding="utf-8").read()
    else:
        header = (
            "---\nname: decision-patterns\n"
            "description: 从决策案例中提取的可复用决策模式 — 由 distill-patterns.py 自动同步\n"
            "metadata:\n  type: project\n---\n\n# 决策模式库\n\n"
            "> 引擎通过 pattern key 匹配历史模式。accuracy 由 distill-patterns.py 从 case outcome 确定性计算。\n\n## 已提取的模式\n\n"
        )
    additions = []
    for key in sorted(missing_in_md):
        pdata = cal["patterns"][key]
        acc = pdata.get("accuracy", 0)
        basis = pdata.get("accuracy_basis", "")
        additions.append(
            f"### Pattern: {key.split(':')[-1]}\n"
            f"- **签名前缀**: `{key}`\n"
            f"- **accuracy**: {acc} ({basis})\n"
            f"- **actions/approved**: {pdata.get('actions', 0)}/{pdata.get('approved', 0)}\n"
            f"- **来源**: {pdata.get('source', 'engine-discovered')}\n"
        )
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(header + body + "\n".join(additions) + "\n")
    return len(additions)


def step2_llm_distill(cal, pat_cases, cases, project_dir):
    """可选 LLM 步：对低 accuracy pattern 配对 success/failure，调 claude -p 提取规则操作"""
    proposals = []
    for key, pdata in cal["patterns"].items():
        acc = pdata.get("accuracy") or 0
        cs = pat_cases.get(key, [])
        if acc >= 0.6 or len(cs) < 2:
            continue
        succ = [c for c in cs if c[0] in SUCCESS_OUTCOMES]
        fail = [c for c in cs if c[0] in FAILURE_OUTCOMES]
        if not fail:
            continue
        # 构造配对 prompt
        case_dir = os.path.join(project_dir, ".claude", "decisions")
        prompt = (
            f"你是决策蒸馏器（ExpeL 式）。对 pattern `{key}`（当前 accuracy={acc}），"
            f"对比以下成功与失败案例，提取一条规则操作（ADD 新规则 / EDIT 修正现有规则 / REMOVE 淘汰）。\n"
            f"成功案例文件: {succ[0][1]}\n失败案例文件: {fail[0][1]}\n"
            f"读这两个 case 文件，输出 JSON: {{\"operation\":\"ADD|EDIT|REMOVE\","
            f"\"rule_text\":\"...\",\"evidence\":\"...\"}}。只输出 JSON。"
        )
        # 优先 claude -p（复用已配置的 GLM 鉴权）
        op = None
        llm_status = "skipped"
        if subprocess.run(["which", "claude"], capture_output=True).returncode == 0:
            try:
                r = subprocess.run(
                    ["claude", "-p", prompt, "--permission-mode", "plan"],
                    cwd=project_dir, capture_output=True, text=True, timeout=120)
                op = r.stdout.strip()
                if op:
                    llm_status = "ok"
                else:
                    # claude 返回空响应：鉴权/模型拒答/无输出，区别于超时
                    llm_status = "empty_response"
                    if r.stderr.strip():
                        llm_status = f"empty_response:stderr={r.stderr.strip()[:120]}"
            except subprocess.TimeoutExpired:
                op = None
                llm_status = "timeout"
            except subprocess.CalledProcessError as e:
                op = None
                llm_status = f"nonzero_exit:{e.returncode}"
            except (subprocess.SubprocessError, OSError, TimeoutError) as e:
                op = None
                llm_status = f"exception:{type(e).__name__}:{str(e)[:80]}"
        proposals.append({"pattern": key, "prompt": prompt, "llm_output": op, "llm_status": llm_status})
    if proposals:
        # 写提案文件（即使 LLM 没跑也留档供 agent 审）
        prop_path = os.path.join(project_dir, ".claude", "decisions", "distillation-proposals.json")
        with open(prop_path, "w", encoding="utf-8") as f:
            json.dump(proposals, f, ensure_ascii=False, indent=2)
        print(f"Step2: {len(proposals)} 条蒸馏提案写入 {prop_path}")
    else:
        print("Step2: 无低 accuracy pattern 需 LLM 蒸馏（跳过）")
    return proposals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--apply", action="store_true", help="落盘（否则干跑只报告）")
    ap.add_argument("--llm", action="store_true", help="启用 Step2 LLM 蒸馏")
    args = ap.parse_args()

    P = args.project
    cal_path = os.path.join(P, ".claude", "decisions", "calibration.json")
    decisions_dir = os.path.join(P, ".claude", "decisions")
    md_path = os.path.join(P, ".claude", "memory", "decision-patterns.md")

    print("=== Step 1: 确定性重算（零 token）===")
    cal = load_calibration(cal_path)
    cases = load_cases(decisions_dir)
    print(f"  加载 {len(cases)} 个 case, {len(cal['patterns'])} 个已有 pattern")

    # === Startup self-check (AS-PERSIST-H01 guard) ===
    # 抽样验证 outcome vocabulary 与 case schema 对齐；不对齐则 accuracy 全不可靠。
    if cases:
        sample = cases[:50] if len(cases) >= 50 else cases
        recognized = sum(1 for c in sample if infer_outcome(c)[0] != "indeterminate")
        explicit = sum(1 for c in sample if infer_outcome(c)[1] == "explicit")
        rate = recognized / len(sample)
        exp_rate = explicit / len(sample)
        print(f"  [self-check] 样本 {len(sample)} case: 识别率={rate:.2f} ({recognized}/{len(sample)}), "
              f"显式 outcome={exp_rate:.2f} ({explicit}/{len(sample)})")
        if rate < 0.5:
            print(f"  ⚠️ WARNING: outcome 识别率 < 50% — SUCCESS_OUTCOMES/FAILURE_OUTCOMES "
                  f"可能与 case schema 脱节。请检查 OUTCOME_ENUM 定义。")
            seen_outcomes = set()
            for c in sample:
                for path in [("outcome",), ("retrospect", "outcome"), ("execute", "outcome")]:
                    v = c
                    try:
                        for k in path:
                            v = v[k]
                        if v:
                            seen_outcomes.add(str(v))
                    except (KeyError, TypeError):
                        pass
            if seen_outcomes:
                print(f"     样本中观察到的 outcome 值: {sorted(seen_outcomes)[:10]}")
    # === end self-check ===

    pat_cases, new_count = step1_recompute(cal, cases)

    # 报告
    zombies = [k for k, v in cal["patterns"].items() if v.get("actions", 0) == 0]
    bogus = [k for k, v in cal["patterns"].items() if v.get("accuracy") == 1.0 and v.get("accuracy_basis", "").startswith("inferred")]
    print(f"  僵尸 pattern(actions=0): {len(zombies)} → {zombies[:5]}")
    print(f"  虚高 accuracy(推断=1.0): {len(bogus)}")
    print(f"  新发现 pattern(注册): {new_count}")

    if args.llm:
        print("=== Step 2: LLM 蒸馏（可选）===")
        step2_llm_distill(cal, pat_cases, cases, P)

    print("=== Step 3: 同步 patterns.md + 门禁 ===")
    added = step3_sync_patterns_md(cal, md_path)
    print(f"  patterns.md 追加 {added} 条缺失条目")

    if not args.apply:
        print("\n[干跑] 未落盘。加 --apply 落盘。")
        # 打印将写入的 accuracy 摘要
        for k, v in list(cal["patterns"].items())[:8]:
            print(f"    {k}: actions={v.get('actions')} acc={v.get('accuracy')} ({v.get('accuracy_basis')})")
        return

    # 落盘前跑门禁
    gate = os.path.join(P, "scripts", "verify-pattern.sh")
    if os.path.exists(gate):
        print("  跑 verify-pattern.sh 门禁...")
        r = subprocess.run(["bash", gate, P], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  ❌ 门禁失败，不落盘:\n{r.stdout}\n{r.stderr}")
            return
        print("  ✓ 门禁通过")

    # 落盘
    with open(cal_path, "w", encoding="utf-8") as f:
        json.dump(cal, f, ensure_ascii=False, indent=2)
    print(f"✓ 已落盘 {cal_path}")
    print(f"  下一步: case schema 需加显式 outcome 字段（见 decision-agent-prompt.md RETROSPECT）")


if __name__ == "__main__":
    main()
