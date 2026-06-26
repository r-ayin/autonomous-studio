"""stop-completion-gate.py — Stop 完成门控 Hook

Stop 事件触发。任务未真正完成则 exit 2 强制继续（Claude Code 标准阻断机制）。

把"任务是否完成"从 LLM 自评转为确定性二元信号（测试过/没过、任务 in_progress/done）。
对中等模型（如 GLM-5.2）尤其关键——Reflexion 论文实证：纯自我反思在中等模型上
可能零提升，但用"测试结果"这种外部二元信号反馈提升显著。本 hook 是那条主线的
系统级强制执行层。

exit 0 = 放行停止
exit 2 = 拒绝停止，Claude Code 继续工作（reason 注入为反馈）

作用域：仅在 Studio 项目内（planning/status.json 存在）且 currentStage 处于
development / verification 时生效。其他场景 exit 0，避免污染非 studio 会话。
防死循环：连续 3 次 exit 2 后改为 exit 0 + 告警（测试永远过不了时不能无限卡）。
"""
import os
import sys
import json
import subprocess

if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORKSPACE_ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
PLANNING_DIR = os.path.join(WORKSPACE_ROOT, "planning")
STATUS_FILE = os.path.join(PLANNING_DIR, "status.json")
PRD_FILE = os.path.join(PLANNING_DIR, "prd.json")
STRIKE_FILE = os.path.join(WORKSPACE_ROOT, ".claude", ".stop_gate_strikes.json")

ACTIVE_STAGES = {"development", "verification", "prd-review", "review"}
MAX_STRIKES = 3  # 连续阻断 3 次后放行 + 告警，防死循环


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _strike_count(inc=False, reset=False):
    """连续阻断计数。reset=True 归零；inc=True 自增。返回当前值。"""
    data = _read_json(STRIKE_FILE) or {"count": 0}
    if reset:
        data["count"] = 0
    elif inc:
        data["count"] = data.get("count", 0) + 1
    try:
        os.makedirs(os.path.dirname(STRIKE_FILE), exist_ok=True)
        with open(STRIKE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass
    return data.get("count", 0)


def check_in_progress_tasks(prd):
    """检查 prd.json 是否有 status=in_progress 的任务遗留。"""
    if not prd:
        return True, "no_prd"
    in_progress = []
    for node in prd.get("nodes", []):
        for task in node.get("tasks", []):
            if task.get("status") == "in_progress":
                in_progress.append(task.get("title") or task.get("id") or "?")
    if in_progress:
        return False, f"in_progress 任务未完成: {in_progress[:3]}"
    return True, "prd_ok"


def check_pending_p0(prd):
    """development 阶段：还有 pending 且 blocked=false 的 P0 任务没做。"""
    if not prd:
        return True, "no_prd"
    pending = []
    for node in prd.get("nodes", []):
        for task in node.get("tasks", []):
            if (task.get("status") == "pending"
                    and task.get("priority") == "P0"
                    and not task.get("blocked")):
                pending.append(task.get("title") or task.get("id") or "?")
    if pending:
        return False, f"仍有 {len(pending)} 个 P0 待办未完成: {pending[:3]}"
    return True, "p0_done"


def check_syntax():
    """检查最近改动文件有无语法错误（Python 用 py_compile，TS/JS 留给 lint hook）。"""
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=5)
        changed = [f for f in r.stdout.strip().split("\n")
                   if f and f.endswith(".py")]
    except Exception:
        return True, "git_skip"
    for f in changed[:15]:
        try:
            cr = subprocess.run(
                ["python", "-m", "py_compile", f],
                cwd=WORKSPACE_ROOT, capture_output=True, timeout=10)
            if cr.returncode != 0:
                return False, f"语法错误: {f}"
        except Exception:
            continue
    return True, "syntax_ok"


def check_tests_pass():
    """有测试套件则要求通过；无测试框架则放行（不强制建测试）。"""
    for cmd, label in [
        (["python", "-m", "pytest", "--tb=no", "-q"], "pytest"),
        (["npm", "test", "--", "--watchAll=false"], "npm"),
        (["make", "test"], "make"),
    ]:
        try:
            r = subprocess.run(cmd, cwd=WORKSPACE_ROOT,
                               capture_output=True, timeout=120)
            if r.returncode == 0:
                return True, f"{label}_pass"
            # 找到测试框架但失败 → 阻断；找不到（FileNotFoundError）继续试下一个
            return False, f"{label}_fail: {(r.stderr or r.stdout)[:200].decode('utf-8','replace') if isinstance((r.stderr or r.stdout), bytes) else (r.stderr or r.stdout)[:200]}"
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            return False, f"{label}_timeout"
        except Exception:
            continue
    return True, "no_tests_found"


def main():
    # 读 stdin（Stop hook 会传入 stop_reason 等）
    stop_reason = ""
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        stop_reason = data.get("stop_reason", "")
    except Exception:
        pass

    # 用户主动中断 → 不阻断
    if stop_reason in ("user_interrupt", "sigint", "end_turn"):
        _strike_count(reset=True)
        sys.exit(0)

    # 作用域：非 Studio 项目直接放行
    status = _read_json(STATUS_FILE)
    if not status:
        sys.exit(0)
    stage = status.get("currentStage", "")
    if stage not in ACTIVE_STAGES:
        _strike_count(reset=True)
        sys.exit(0)

    prd = _read_json(PRD_FILE)
    failures = []

    # 检查 1：无 in_progress 任务遗留
    ok, detail = check_in_progress_tasks(prd)
    if not ok:
        failures.append(detail)

    # 检查 2：development 阶段还有 pending P0
    if stage == "development":
        ok, detail = check_pending_p0(prd)
        if not ok:
            failures.append(detail)

    # 检查 3：语法错误
    ok, detail = check_syntax()
    if not ok:
        failures.append(detail)

    # 检查 4：测试通过（有套件才管）
    ok, detail = check_tests_pass()
    if not ok:
        failures.append(detail)

    if not failures:
        _strike_count(reset=True)
        sys.exit(0)

    # 有失败 → 阻断
    strikes = _strike_count(inc=True)
    if strikes >= MAX_STRIKES:
        # 防死循环：连续阻断已达上限，放行但告警
        _strike_count(reset=True)
        msg = (f"⚠️ Stop 门控已连续阻断 {MAX_STRIKES} 次仍未通过，现放行停止以避免死循环。"
               f"未通过项:\n" + "\n".join(f"- {f}" for f in failures)
               + "\n建议人工介入检查上述项。")
        print(json.dumps({"decision": "warn_strikeout", "reason": msg},
                         ensure_ascii=False))
        sys.exit(0)

    reason = ("任务未真正完成，不允许停止（第 %d/%d 次阻断）:\n" % (strikes, MAX_STRIKES)
              + "\n".join(f"- {f}" for f in failures)
              + "\n请继续完成上述项后再停止。")
    # 标准 Claude Code 阻断：exit 2 + reason
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False),
          file=sys.stderr)
    print(reason)
    sys.exit(2)


if __name__ == "__main__":
    main()
