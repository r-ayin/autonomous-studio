#!/usr/bin/env bash
# studio-status-guard.sh — PreToolUse 拦截直接改 status.json
#
# 触发：模型用 Write/Edit 改 planning/status.json 时
# 行为：拒绝（exit 2 阻断），提示用 studio-stage-gate.sh 推进阶段。
#       status.json 的 currentStage 必须由脚本核验后写入，不能手改。
#
# 例外：允许 stage-gate.sh 和 status-sync.sh 自己写（通过 STAGE_GATE_SELF 标记）。
# 允许 sync 脚本回写 completedTasks（非 currentStage 字段）——但 currentStage 字段
# 只能 stage-gate 改，这个 hook 拦不住"字段级"，所以靠脚本自觉 + 此 hook 拦直接手写。

set -euo pipefail

# 从 stdin 读 hook 输入（JSON）
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null || echo "")

# 只管 planning/status.json
case "$FILE_PATH" in
  */planning/status.json|planning/status.json) : ;;
  *) exit 0 ;;
esac

# 例外：stage-gate / status-sync 自己写时带标记
if [[ "${STUDIO_GATE_SELF:-}" == "1" ]]; then
  exit 0
fi

cat <<'MSG'
{
  "decision": "block",
  "reason": "status.json 的阶段状态(currentStage)必须用脚本核验后写入，不能手改。\n\n请用:\n  推进阶段 → bash ~/.claude/skills/autonomous-studio/scripts/studio-stage-gate.sh . [目标阶段]\n  回填任务完成状态 → bash ~/.claude/skills/autonomous-studio/scripts/studio-status-sync.sh . --apply\n\n脚本会检查: 执行回填(sync全done) + 审查回填(review-findings无必修未解决) 都齐才放行。\n这是'代码建立规范'，不靠模型自觉标记。"
}
MSG
exit 2
