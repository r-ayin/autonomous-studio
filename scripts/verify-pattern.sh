#!/bin/bash
# verify-pattern.sh — 蒸馏质量门禁（确定性，零 LLM，bash exit 1 不可协商）
#
# 4 个 gate，任一失败 → exit 1，distill-patterns.py 不落盘。
# 原则（研究）："提示词不是护栏"——bash exit 1 无法被 LLM 话术绕过。
#
# 用法: verify-pattern.sh <项目目录>
set -uo pipefail

P="${1:-.}"
CAL="$P/.claude/decisions/calibration.json"
MD="$P/.claude/memory/decision-patterns.md"
MIN_SAMPLE=2          # gate1: pattern 至少关联 2 个 case 才算可信 accuracy
ACC_FLOOR=0.4         # gate2: accuracy < 0.4 的 pattern 标退役（不删，标 retired）
CAP=30                # gate3: patterns.md 条目上限，超出须先退役最低 accuracy
FAIL=0

echo "[verify-pattern] 项目: $P"

# 前置：calibration 必须是合法 JSON（路径经 sys.argv 传入，避免 $CAL shell 注入到 python 代码串）
if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$CAL" 2>/dev/null; then
  echo "  ❌ GATE-0: calibration.json 非合法 JSON，先修 distill-patterns.py 的鲁棒加载"
  exit 1
fi
echo "  ✓ GATE-0: calibration.json 合法"

# 用 python 跑 4 个 gate（bash 调度，python 判定）
# 路径全部经 sys.argv 传入，heredoc 内不做任何 shell 变量/f-string 派生，避免注入与引号破损
python3 - "$P" "$MIN_SAMPLE" "$ACC_FLOOR" "$CAP" "$CAL" "$MD" <<'PY' || FAIL=1
import json, os, re, sys
P, MIN_SAMPLE, ACC_FLOOR, CAP = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])
CAL, MD = sys.argv[5], sys.argv[6]
cal = json.load(open(CAL))
patterns = cal.get("patterns", {})
ok = True

# GATE-1: 最小样本底线 — accuracy 标 verified 的须有 ≥MIN_SAMPLE 显式 outcome
# （此处检查 accuracy_basis 字段；无显式的不阻断，只标 indeterminate）
for k, v in patterns.items():
    basis = v.get("accuracy_basis", "")
    if basis.startswith("verified") and int(basis.split(":")[1]) < MIN_SAMPLE:
        print(f"  ❌ GATE-1: {k} 标 verified 但样本 < {MIN_SAMPLE}")
        ok = False
print(f"  ✓ GATE-1: 最小样本底线通过") if ok else None

# GATE-2: accuracy < ACC_FLOOR 且 actions≥MIN_SAMPLE 的 pattern 标 retired（不删）
retired = []
for k, v in patterns.items():
    acc = v.get("accuracy") or 0
    actions = v.get("actions", 0)
    if actions >= MIN_SAMPLE and acc < ACC_FLOOR:
        v["retired"] = True
        v["retired_reason"] = f"accuracy {acc} < floor {ACC_FLOOR} over {actions} cases"
        retired.append(k)
if retired:
    print(f"  ⚠️ GATE-2: {len(retired)} 个 pattern 标 retired: {retired[:3]}")
else:
    print(f"  ✓ GATE-2: accuracy 底线通过（无退役）")
# 回写 retired 标记
json.dump(cal, open(CAL, "w"), ensure_ascii=False, indent=2)

# GATE-3: 容量帽 — 活跃（非 retired）pattern 数 ≤ CAP
active = [k for k, v in patterns.items() if not v.get("retired")]
if len(active) > CAP:
    # 按 accuracy 升序退役最低的
    active.sort(key=lambda k: patterns[k].get("accuracy") or 0)
    for k in active[:len(active)-CAP]:
        patterns[k]["retired"] = True
        patterns[k]["retired_reason"] = "capacity_cap"
    print(f"  ⚠️ GATE-3: 超 {CAP} 上限，退役 {len(active)-CAP} 个最低 accuracy")
else:
    print(f"  ✓ GATE-3: 容量帽通过（活跃 {len(active)}）")
json.dump(cal, open(CAL, "w"), ensure_ascii=False, indent=2)

# GATE-4: 同步检查 — calibration pattern 数（非 retired）与 patterns.md 条目数对齐
md_count = 0
if os.path.exists(MD):
    md_count = open(MD).read().count("### Pattern:")
active_cal = len([k for k,v in patterns.items() if not v.get("retired")])
# 允许 patterns.md 多（历史），但不允许 calibration 多而 md 少（漂移）
if active_cal > md_count:
    print(f"  ❌ GATE-4: 漂移 — calibration 活跃 {active_cal} > patterns.md {md_count}（distill Step3 应补齐）")
    ok = False
else:
    print(f"  ✓ GATE-4: 同步通过（cal活跃 {active_cal} ≤ md {md_count}）")

sys.exit(0 if ok else 1)
PY

if [ $FAIL -ne 0 ]; then
  echo "[verify-pattern] ❌ 门禁失败，distill 不应落盘"
  exit 1
fi
echo "[verify-pattern] ✅ 全部门禁通过"
exit 0
