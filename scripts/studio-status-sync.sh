#!/usr/bin/env bash
# studio-status-sync.sh — 状态核验回写（执行回填）
#
# 用途：开发 agent 做完任务后必须跑这个，把 prd-*.json 各任务的 status
#       按"代码证据"回填，同步更新 status.json 的 completedTasks。
#       凭证据回填，不凭嘴说。
#
# 用法：
#   bash studio-status-sync.sh [project-dir]            # 只核验，输出报告，不改文件
#   bash studio-status-sync.sh [project-dir] --apply     # 核验 + 回写 prd.json/status.json
#
# 证据配置：planning/task-evidence.json（两种格式，任选）
#   精确配对（推荐，跨文件任务用）：
#     "N51-04": { "checks": [["src/store/index.ts","insertProgressSnapshot"],["src/store/engine.ts","预计释放"]] }
#   笛卡尔积（单文件多特征用）：
#     "N7-01": { "files": ["src/store/db.ts"], "patterns": ["review_outcome","insertOverrideRecord"] }
#   - 所有 check/file×pattern 命中 → done
#   - 部分命中 → partial
#   - 无配置 → manual（需人工核验，不自动回写）
#   铁律：manual/partial/todo 永不自动标 done，留审查 agent 核实。
#
# 这是"两道回填"中的第一道：执行回填。第二道是审查回填（review-findings.md）。
# 两道都齐了，studio-stage-gate.sh 才放行推进。

set -euo pipefail

PROJ_DIR="${1:-.}"
shift 2>/dev/null || true
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

PLANNING="$PROJ_DIR/planning"
STATUS_FILE="$PLANNING/status.json"
REPORT_FILE="$PLANNING/status-sync-report.md"

# 找最新的 prd-*.json（优先带版本号的）
PRD_JSON=$(ls -1 "$PLANNING"/prd-*.json 2>/dev/null | grep -v "prd.json$" | sort -V | tail -1)
if [[ -z "$PRD_JSON" ]]; then
  PRD_JSON="$PLANNING/prd.json"
fi

if [[ ! -f "$PRD_JSON" ]]; then
  echo "ERROR: 未找到 prd json ($PLANNING/prd-*.json)" >&2
  exit 2
fi

EVIDENCE="$PLANNING/task-evidence.json"

echo "PRD:     $PRD_JSON"
echo "证据:    $([[ -f "$EVIDENCE" ]] && echo "$EVIDENCE" || echo '(无 task-evidence.json，全部标 manual)')"
echo "模式:    $([[ $APPLY -eq 1 ]] && echo 'apply(回写)' || echo 'dry-run(只核验)')"
echo ""

# 核验：对每个 task 跑证据 grep，输出 {id, title, verdict, detail}
REPORT_JSON=$(python3 << PYEOF
import json, re, subprocess, os, sys

proj = "$PROJ_DIR"
prd_path = "$PRD_JSON"
evidence_path = "$EVIDENCE"
has_evidence = os.path.exists(evidence_path)
evidence = {}
if has_evidence:
    with open(evidence_path) as f:
        evidence = json.load(f)

with open(prd_path) as f:
    prd = json.load(f)

def grep_check(file_rel, pattern):
    """在项目里 grep pattern，返回命中行数。pattern 是字面量（非正则）。"""
    path = os.path.join(proj, file_rel)
    if not os.path.exists(path):
        return 0, "文件不存在: " + file_rel
    try:
        r = subprocess.run(["grep", "-c", "--", pattern, path],
                           capture_output=True, text=True, timeout=10)
        n = int(r.stdout.strip()) if r.stdout.strip().isdigit() else 0
        return n, ""
    except Exception as e:
        return 0, str(e)

results = []
for node in prd.get("nodes", []):
    for t in node.get("tasks", []):
        tid = t.get("id", "")
        title = t.get("title", "")
        ev = evidence.get(tid)
        # 解析证据为 [file, pattern] 对列表
        if ev and ev.get("checks"):
            checks = [tuple(c) for c in ev["checks"]]
        elif ev and ev.get("files") and ev.get("patterns"):
            checks = [(f, p) for f in ev["files"] for p in ev["patterns"]]
        else:
            results.append({"id": tid, "title": title, "verdict": "manual",
                            "detail": "未配证据，需人工核验"})
            continue
        hits = []
        miss = []
        for fl, p in checks:
            n, err = grep_check(fl, p)
            hits.append((fl, p, n))
            if n == 0:
                miss.append(f"{fl}:{p}")
        if not miss:
            verdict = "done"
            detail = f"全部命中({len(hits)}处)"
        elif len(miss) < len(hits):
            verdict = "partial"
            detail = "缺: " + ", ".join(miss)
        else:
            verdict = "todo"
            detail = "全部缺失: " + ", ".join(miss)
        results.append({"id": tid, "title": title, "verdict": verdict, "detail": detail})

print(json.dumps(results, ensure_ascii=False))
PYEOF
)

# 生成报告 + 统计
python3 << PYEOF
import json, os
results = json.loads('''$REPORT_JSON''')
done = [r for r in results if r["verdict"]=="done"]
partial = [r for r in results if r["verdict"]=="partial"]
todo = [r for r in results if r["verdict"]=="todo"]
manual = [r for r in results if r["verdict"]=="manual"]
total = len(results)

lines = []
lines.append("# 状态核验报告（执行回填）")
lines.append("")
lines.append(f"- 总任务: {total}")
lines.append(f"- done(已实现): {len(done)}")
lines.append(f"- partial(部分实现): {len(partial)}")
lines.append(f"- todo(未实现): {len(todo)}")
lines.append(f"- manual(需人工核验): {len(manual)}")
lines.append("")
lines.append("| 任务 | 标题 | 判定 | 说明 |")
lines.append("|---|---|---|---|")
for r in results:
    lines.append(f"| {r['id']} | {r['title']} | {r['verdict']} | {r['detail']} |")
lines.append("")
lines.append("> verdict=done 才会计入 completedTasks。partial/todo/manual 不计入。")
lines.append("> manual 项需人工核验后在 task-evidence.json 补证据再重跑。")

report = "\n".join(lines)
with open("$REPORT_FILE", "w") as f:
    f.write(report)
print(report)
print(f"\n报告已写: $REPORT_FILE")
print(f"done={len(done)}/{total}")
PYEOF

# --apply：回写 prd.json status + status.json completedTasks
# 带 STUDIO_GATE_SELF=1 标记，避免被 studio-status-guard.sh hook 拦截自己
if [[ $APPLY -eq 1 ]]; then
  STUDIO_GATE_SELF=1 python3 << PYEOF
import json, os, datetime
proj = "$PROJ_DIR"
prd_path = "$PRD_JSON"
status_path = "$STATUS_FILE"
results = json.loads('''$REPORT_JSON''')

# 回写 prd.json 各 task status
with open(prd_path) as f:
    prd = json.load(f)
verdict_map = {r["id"]: r["verdict"] for r in results}
changed = 0
for node in prd.get("nodes", []):
    for t in node.get("tasks", []):
        tid = t.get("id","")
        v = verdict_map.get(tid, "manual")
        new_status = {"done":"done","partial":"partial","todo":"pending","manual":"pending"}[v]
        if t.get("status") != new_status:
            t["status"] = new_status
            changed += 1
# prd.json 顶层 completedTasks/progress
done_count = sum(1 for r in results if r["verdict"]=="done")
total = len(results)
prd["completedTasks"] = done_count
prd["progress"] = round(done_count/total*100, 1) if total else 0
with open(prd_path, "w") as f:
    json.dump(prd, f, ensure_ascii=False, indent=2)
print(f"已回写 {prd_path}: {changed} 个 task status 更新, completedTasks={done_count}/{total}")

# 回写 status.json
if os.path.exists(status_path):
    with open(status_path) as f:
        st = json.load(f)
    prog = st.get("engine",{}).get("developmentProgress",{})
    prog["completedTasks"] = done_count
    prog["totalTasks"] = total
    prog["completedPercent"] = round(done_count/total*100, 1) if total else 0
    prog["p0Complete"] = all(verdict_map.get(t["id"])=="done"
                             for node in prd["nodes"] for t in node["tasks"]
                             if t.get("priority")=="P0") if total else False
    prog["lastSync"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    st["lastUpdated"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    with open(status_path, "w") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    print(f"已回写 {status_path}: completedTasks={done_count}/{total}")
PYEOF
else
  echo ""
  echo "(dry-run 模式，未回写文件。加 --apply 回写。)"
fi
