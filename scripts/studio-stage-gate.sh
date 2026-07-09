#!/usr/bin/env bash
# studio-stage-gate.sh — 阶段推进硬关卡（代码强制，不靠模型自觉）
#
# 模型不许手改 status.json 的 currentStage，必须调本脚本推进。
# 脚本对每个推进点做硬检查，不满足 → exit 1 拒绝 + 打印缺什么。
#
# 用法：
#   bash studio-stage-gate.sh [project-dir] [target-stage]
#     target-stage 省略 → 自动推进到下一阶段
#   bash studio-stage-gate.sh [project-dir] --check   # 只检查当前能否推进，不写
#
# 阶段链 + 推进关卡：
#   requirements → prd → development → prd-review → verification → review → deployment → archiving
#                  PRD确认   开发完成   全面审查       E2E测试     代码评审    部署验证
#
# 两道回填铁律：执行回填(sync) + 审查回填(review-findings)，都齐才放行。
# 配套 hook：拦截直接 Write status.json，强制走本脚本。

set -euo pipefail

PROJ_DIR="${1:-.}"
shift 2>/dev/null || true
# 解析剩余参数：--check 只读，否则第一个非 flag 为 target
CHECK_ONLY=0
TARGET=""
for arg in "$@"; do
  if [[ "$arg" == "--check" ]]; then
    CHECK_ONLY=1
  else
    TARGET="$arg"
  fi
done

PLANNING="$PROJ_DIR/planning"
STATUS_FILE="$PLANNING/status.json"
GATE_LOG="$PLANNING/stage-gate.log"

STAGE_ORDER=(requirements prd development prd-review verification review deployment archiving archived)

err()  { echo "❌ GATE 拒绝推进: $*" >&2; }
ok()   { echo "✅ $*"; }
die()  { err "$*"; echo "$(date '+%F %T') REJECT $*" >> "$GATE_LOG"; exit 1; }

[[ -f "$STATUS_FILE" ]] || die "status.json 不存在 ($STATUS_FILE)"

# 读当前阶段
CURRENT=$(python3 -c "import json;print(json.load(open('$STATUS_FILE'))['currentStage'])")
LOCKED=$(python3 -c "import json;print(str(json.load(open('$STATUS_FILE')).get('locked',False)).lower())")

# 推断 target
if [[ -z "$TARGET" ]]; then
  idx=-1
  for i in "${!STAGE_ORDER[@]}"; do [[ "${STAGE_ORDER[$i]}" == "$CURRENT" ]] && idx=$i; done
  [[ $idx -ge 0 && $((idx+1)) -lt ${#STAGE_ORDER[@]} ]] || die "无法推断下一阶段 (current=$CURRENT)"
  TARGET="${STAGE_ORDER[$((idx+1))]}"
fi

echo "当前阶段: $CURRENT"
echo "目标阶段: $TARGET"
[[ "$LOCKED" == "true" ]] && echo "(locked=true — 确认是本会话的专属任务后再推进)"

# ── 顺序检查：不能跳过未完成的中间阶段 ────────────────────────
COMPLETED=$(python3 -c "import json;print(' '.join(json.load(open('$STATUS_FILE')).get('completedStages',[])))")
cur_idx=-1; tgt_idx=-1
for i in "${!STAGE_ORDER[@]}"; do
  [[ "${STAGE_ORDER[$i]}" == "$CURRENT" ]] && cur_idx=$i
  [[ "${STAGE_ORDER[$i]}" == "$TARGET" ]] && tgt_idx=$i
done
if [[ $tgt_idx -ge 0 && $cur_idx -ge 0 && $tgt_idx -gt $((cur_idx+1)) ]]; then
  die "不能跳跃推进 $CURRENT → $TARGET。中间阶段未完成（如需跳过某阶段，逐个推进并各自过关卡）"
fi

# ── 关卡检查函数 ──────────────────────────────────────────────

# 执行回填：跑 status-sync，要求所有任务 done（partial/todo/manual 不计）
check_sync_all_done() {
  local sync_report="$PLANNING/status-sync-report.md"
  # 先跑 sync（dry-run，不改文件）
  bash "$(dirname "$0")/studio-status-sync.sh" "$PROJ_DIR" >/dev/null 2>&1 || true
  [[ -f "$sync_report" ]] || { err "未生成 status-sync-report，先跑 studio-status-sync.sh"; return 1; }
  # 取统计行的"值"而非"行存在数"（值为0时行仍存在，grep -c 会误返回1）
  val_of() { grep "^- $1" "$sync_report" | grep -oE "[0-9]+" | head -1; }
  local todo partial manual done total
  todo=$(val_of "todo(未实现)")
  partial=$(val_of "partial(部分实现)")
  manual=$(val_of "manual(需人工核验)")
  done=$(val_of "done(已实现)")
  total=$(val_of "总任务")
  todo=${todo:-0}; partial=${partial:-0}; manual=${manual:-0}
  if [[ "$todo" -ne 0 || "$partial" -ne 0 || "$manual" -ne 0 ]]; then
    err "执行回填未齐: done=${done:-?}/${total:-?}, partial=${partial}, todo=${todo}, manual=${manual}"
    err "→ 还有未实现/部分实现/待核验任务，继续改代码，改完重跑 studio-status-sync.sh"
    return 1
  fi
  ok "执行回填齐: ${done}/${total} 全 done"
  return 0
}

# 审查回填：prd.json 所有 task 的 verdict=pass（对齐 auto-coding 原始方案）
# 审代码 Agent 直接写 verdict=pass/blocker 到 prd.json 对应 task，
# verdict=blocker → 该 task 必须回头改 bug，整个阶段推不出去（不允许带未通过审查写下游）
check_verdict_all_pass() {
  local prd_json
  prd_json=$(ls -1 "$PLANNING"/prd-*.json 2>/dev/null | grep -v "prd.json$" | sort -V | tail -1)
  [[ -z "$prd_json" ]] && prd_json="$PLANNING/prd.json"
  [[ -f "$prd_json" ]] || { err "prd.json 不存在"; return 1; }

  local stats
  stats=$(STUDIO_GATE_SELF=1 python3 << PYEOF
import json
d = json.load(open("$prd_json"))
tasks = [t for n in d.get("nodes",[]) for t in n.get("tasks",[])]
total = len(tasks)
passed = sum(1 for t in tasks if t.get("verdict")=="pass")
blocker = sum(1 for t in tasks if t.get("verdict")=="blocker")
unreviewed = sum(1 for t in tasks if t.get("verdict") not in ("pass","blocker"))
# 统计 retryCount 达上限 blocked 的
blocked = sum(1 for t in tasks if t.get("blocked",False))
print(f"{passed}|{blocker}|{unreviewed}|{total}|{blocked}")
PYEOF
)
  local passed blocker unreviewed total blocked
  IFS='|' read passed blocker unreviewed total blocked <<< "$stats"
  passed=${passed:-0}; blocker=${blocker:-0}; unreviewed=${unreviewed:-0}; total=${total:-0}; blocked=${blocked:-0}

  if [[ "${unreviewed:-0}" -ne 0 ]]; then
    err "审查回填未齐: 还有 ${unreviewed} 个 task 没被审代码 Agent 审过（verdict 未设）"
    err "→ 每个写完的 task 必须过审代码 Agent，写回 verdict=pass/blocker"
    return 1
  fi
  if [[ "${blocker:-0}" -ne 0 ]]; then
    err "审查未通过: 还有 ${blocker} 个 task verdict=blocker，必须回头改 bug（不允许带未通过审查推进）"
    err "→ 改完对应 bug 重审，verdict 改 pass 后再推进"
    return 1
  fi
  if [[ "${passed:-0}" -ne "${total:-0}" ]]; then
    err "审查回填未齐: pass=${passed}/${total}，未全部通过"
    return 1
  fi
  ok "审查回填齐: ${passed}/${total} 全 verdict=pass${blocked:+ (${blocked} 个已 blocked 跳过)}"
  return 0
}

# 审查回填清：最终全量对照(③-R)段无未修必修项
check_review_findings_clean() {
  local rf
  rf=$(python3 -c "import json;d=json.load(open('$PLANNING/status.json'));print(d.get('engine',{}).get('stageArtifacts',{}).get('reviewFindings','planning/review-findings.md'))" 2>/dev/null)
  [[ -z "$rf" ]] && rf="$PLANNING/review-findings.md"
  [[ -f "$rf" ]] || { ok "无 review-findings 文件，视为审查清"; return 0; }
  # 取最后一个 ③-R 全量对照 段作为最终判定
  local final
  final=$(awk '/## ③-R 全量对照/{f=1} f' "$rf" | tail -40)
  if [[ -z "$final" ]]; then
    # 无 ③-R 段：检查整文件有无"必修阻塞项"未伴"已修/已修复/fixed"
    if grep -qE "必修阻塞项" "$rf" && ! grep -qE "无.*阻塞|均已修复|全部已修|无代码层阻塞" "$rf"; then
      err "审查回填未清: review-findings 有必修阻塞项未标已修"
      return 1
    fi
    ok "审查回填清(无 ③-R 段，无未修必修)"; return 0
  fi
  if echo "$final" | grep -qE "无代码层阻塞项|无必修|均已修复|全部已修|无阻塞"; then
    ok "审查回填清: ③-R 全量对照确认无阻塞项(必修均已修)"; return 0
  fi
  err "审查回填未清: ③-R 全量对照仍有未修必修项"
  return 1
}

# ── 各阶段关卡 ────────────────────────────────────────────────
case "$TARGET" in
  prd)
    [[ -f "$PLANNING/prd.json" || -f "$PLANNING/prd-*.json" ]] || die "prd.json 未生成"
    # PRD 确认硬关卡：status.json 须有用户确认标记
    CONF=$(python3 -c "import json;d=json.load(open('$STATUS_FILE'));print(str(d.get('prdConfirmed',d.get('notes','')).lower()))" 2>/dev/null || echo "")
    [[ "$CONF" == *"确认"* || "$CONF" == *"approved"* ]] || die "PRD 未获用户明确确认（铁律6）。用户说'确认/approved/没问题'才能推进，'差不多''看起来还行'不算"
    ok "PRD 已确认"
    ;;
  development)
    # 进入开发：PRD 已存在即可
    ls "$PLANNING"/prd-*.json >/dev/null 2>&1 || [[ -f "$PLANNING/prd.json" ]] || die "prd.json 不存在"
    ok "PRD 就绪，可进入开发"
    ;;
  prd-review)
    # 全面审查关卡：执行回填 + 审查回填 都要齐
    check_sync_all_done || die "执行回填未齐 — 全面审查前所有任务必须先全 done"
    check_review_findings_clean || die "审查回填未清 — 必修项未修完不能说完成"
    ;;
  verification)
    # E2E 验证前：全面审查已通过
    check_review_findings_clean || die "审查未全通过，不能进 E2E 验证"
    ok "审查全通过，可进 E2E 验证"
    ;;
  review)
    # 代码评审前：E2E 验证报告 + 真跑过（不含"待用户实跑"）
    [[ -f "$PLANNING/e2e-report.md" ]] || die "E2E 验证报告 (e2e-report.md) 不存在，未跑 E2E 测试"
    grep -qiE "通过|pass" "$PLANNING/e2e-report.md" || die "E2E 验证报告未标'通过'"
    grep -qiE "待用户实跑|待跑|⏳|未真跑|待实跑" "$PLANNING/e2e-report.md" && die "E2E 报告含'待用户实跑/待跑'——功能 E2E 未真做，不能进 review。先跑 bash ~/.claude/skills/autonomous-studio/scripts/setup-e2e.sh . && npx playwright test，或回 development"
    ok "E2E 验证通过（真跑）"
    ;;
  deployment)
    # 部署前：代码评审(code-review/simplify)无必修
    check_review_findings_clean || die "代码评审有必修项未清，不能部署"
    ok "代码评审通过，可部署"
    ;;
  archiving)
    # 归档前：部署后验证无 5xx
    [[ -f "$PLANNING/deploy-verify.md" ]] || die "部署后验证报告 (deploy-verify.md) 不存在"
    grep -qiE "通过|pass|200" "$PLANNING/deploy-verify.md" || die "部署后验证未通过（可能 5xx）"
    ok "部署验证通过，可归档"
    ;;
  archived)
    ok "归档完成"
    ;;
  *)
    die "未知目标阶段: $TARGET (合法: ${STAGE_ORDER[*]})"
    ;;
esac

# ── 通过关卡，写回 status.json ────────────────────────────────
# 带 STUDIO_GATE_SELF=1 标记，避免被自己的 status-guard hook 拦截
if [[ $CHECK_ONLY -eq 1 ]]; then
  echo ""
  echo "✅ 关卡检查通过（--check，未写回）"
  exit 0
fi

STUDIO_GATE_SELF=1 python3 << PYEOF
import json, datetime
with open("$STATUS_FILE") as f:
    st = json.load(f)
old = st["currentStage"]
st["currentStage"] = "$TARGET"
st["lastUpdated"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
completed = st.get("completedStages", [])
if old not in completed:
    completed.append(old)
st["completedStages"] = completed
st.setdefault("engine",{}).setdefault("stageGate",{})
st["engine"]["stageGate"]["lastAdvance"] = f"{old} → $TARGET @ {st['lastUpdated']}"
with open("$STATUS_FILE", "w") as f:
    json.dump(st, f, ensure_ascii=False, indent=2)
print(f"✅ 已推进: {old} → $TARGET")
PYEOF

echo "$(date '+%F %T') ADVANCE $CURRENT → $TARGET" >> "$GATE_LOG"
