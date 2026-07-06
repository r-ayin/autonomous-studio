#!/bin/bash
# verify-user-style.sh — 用户决策风格蒸馏质量门禁（确定性，零 LLM，bash exit 1 不可协商）
#
# 3 个 gate，任一失败 → exit 1，distill-user-style.py 不落盘（或回滚）。
# 原则（研究）："提示词不是护栏"——bash exit 1 无法被 LLM 话术绕过。
#
# 与 verify-pattern.sh 的区别：用户风格不退役（只增不改），无 accuracy floor；
# 重点检查"孤证不取"和"evidence 必填"——防止 LLM 臆造规则。
#
# 用法: verify-user-style.sh <项目目录>
set -uo pipefail

P="${1:-.}"
MD="$P/.claude/memory/user-decision-style.md"
MAX_RULES=40         # gate2: 规则总数上限，防止 LLM 膨胀
FAIL=0

echo "[verify-user-style] 项目: $P"

if [ ! -f "$MD" ]; then
  echo "  ❌ GATE-0: user-decision-style.md 不存在（distill 应先写再跑门禁）"
  exit 1
fi

# 用 python 跑 3 个 gate
python3 - "$P" "$MAX_RULES" <<'PY' || FAIL=1
import json, os, re, sys
P = sys.argv[1]
MAX_RULES = int(sys.argv[2])
MD = f"{P}/.claude/memory/user-decision-style.md"
text = open(MD, encoding="utf-8").read()
ok = True

# GATE-0: 含 4 个维度 section header
dims = ["沟通粒度与汇报偏好", "确认门槛与自动化边界", "风险偏好与节奏", "技术选型与实现倾向"]
missing = [d for d in dims if f"## {d}" not in text]
if missing:
    print(f"  ❌ GATE-0: 缺维度 section: {missing}")
    ok = False
else:
    print(f"  ✓ GATE-0: 4 维度 section 齐全")

# GATE-1: 每个 ### Style 块必须有非空 evidence（防 LLM 臆造无证据规则）
blocks = re.split(r"\n(?=### Style:)", text)
no_evidence = []
for b in blocks[1:]:  # 跳过 header
    sig_m = re.search(r"签名前缀[^`]*`([^`]+)`", b)
    sig = sig_m.group(1) if sig_m else "?"
    ev_m = re.search(r"\*\*evidence\*\*:\s*(.+)", b)
    if not ev_m or "_(无)_" in ev_m.group(1) or not ev_m.group(1).strip():
        no_evidence.append(sig)
if no_evidence:
    print(f"  ❌ GATE-1: {len(no_evidence)} 条规则无 evidence（孤证/臆造）: {no_evidence[:5]}")
    ok = False
else:
    print(f"  ✓ GATE-1: 所有规则 evidence 非空")

# GATE-2: 规则总数 ≤ MAX_RULES（防膨胀）
rule_count = text.count("### Style:")
if rule_count > MAX_RULES:
    print(f"  ❌ GATE-2: 规则数 {rule_count} > 上限 {MAX_RULES}，须精简")
    ok = False
else:
    print(f"  ✓ GATE-2: 规则数 {rule_count} ≤ {MAX_RULES}")

sys.exit(0 if ok else 1)
PY

if [ $FAIL -ne 0 ]; then
  echo "[verify-user-style] ❌ 门禁失败，distill 不应落盘"
  exit 1
fi
echo "[verify-user-style] ✅ 全部门禁通过"
exit 0
