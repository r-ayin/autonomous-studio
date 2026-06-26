#!/usr/bin/env bash
# parallel-dispatch.sh — 并发构建 Wave 分发（确定性 plumbing）
#
# 读 planning/parallel-plan.json，为指定 wave 的每个 task 创建独立 worktree + 分支，
# 并（可选）用 `claude -p` 后台 spawn agent，并发上限 = maxConcurrency。
#
# 用法:
#   parallel-dispatch.sh <项目目录> [wave号]      # 只建 worktree + 写 prompt，打印 spawn 清单（控制器用 Agent 工具并发 spawn）
#   parallel-dispatch.sh <项目目录> <wave号> --spawn  # 额外用 claude -p 后台真 spawn（限流）
#
# 设计原则：worktree/分支/合并这些机械活用脚本（确定性），LLM 只决定"建什么"(spec)。
# 详见 phases/phase-dev.md ④ 并发构建模式。
set -euo pipefail

PROJECT_DIR="${1:-.}"
WAVE="${2:-1}"
SPAWN="${3:-}"

cd "$PROJECT_DIR"
PLAN="planning/parallel-plan.json"
WORKTREE_BASE="../.parallel-worktrees"  # worktree 放在项目外侧，避免污染

if [[ ! -f "$PLAN" ]]; then
  echo "❌ 未找到 $PLAN — 先由主 agent 产出并发契约（见 phase-dev ④ Wave 0）" >&2
  exit 1
fi

# 用 python3 解析 JSON（不依赖 jq）
read -r MAX_CONCURRENCY TASKS_JSON <<< "$(python3 - "$PLAN" "$WAVE" <<'PY'
import json, sys
plan = json.load(open(sys.argv[1]))
wave = int(sys.argv[2])
maxc = plan.get("maxConcurrency", 4)
tasks = []
for w in plan.get("waves", []):
    if w.get("wave") == wave:
        tasks = w.get("tasks", [])
        break
print(maxc, json.dumps(tasks, ensure_ascii=False))
PY
)"

if [[ -z "$TASKS_JSON" || "$TASKS_JSON" == "[]" ]]; then
  echo "⚠️ Wave $WAVE 无任务（可能已全部完成或 wave 号不存在）"
  exit 0
fi

mkdir -p "$WORKTREE_BASE"
echo "=== Wave $WAVE: $(echo "$TASKS_JSON" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))') 个 task, 并发上限 $MAX_CONCURRENCY ==="

# 为每个 task 建 worktree + 分支 + 写 prompt
PIDS=()
SPAWN_COUNT=0
for TASK_ID in $(echo "$TASKS_JSON" | python3 -c 'import json,sys; [print(t) for t in json.load(sys.stdin)]'); do
  BRANCH="parallel/${TASK_ID}"
  WT_DIR="${WORKTREE_BASE}/${TASK_ID}"

  if [[ -d "$WT_DIR" ]]; then
    echo "↻ $TASK_ID: worktree 已存在，跳过创建 ($WT_DIR)"
  else
    # 从当前 HEAD 建 worktree + 分支
    git worktree add -b "$BRANCH" "$WT_DIR" HEAD 2>/dev/null || {
      echo "❌ $TASK_ID: worktree 创建失败（分支 $BRANCH 可能已存在）" >&2
      git worktree add "$WT_DIR" "$BRANCH" 2>/dev/null || { echo "❌ $TASK_ID: 彻底失败，跳过" >&2; continue; }
    }
    echo "✓ $TASK_ID: worktree=$WT_DIR branch=$BRANCH"
  fi

  # 共享 node_modules（省 install），端口隔离
  if [[ -d "node_modules" && ! -e "$WT_DIR/node_modules" ]]; then
    ln -s "$(cd "$PROJECT_DIR" && pwd)/node_modules" "$WT_DIR/node_modules" 2>/dev/null || true
  fi

  # 写该 task 的 agent prompt（控制器或 claude -p 用）
  cat > "$WT_DIR/.task-prompt.md" <<PROMPT
你是并发构建 agent（task ${TASK_ID}）。

契约文件：${PROJECT_DIR}/planning/parallel-plan.json（读 contracts 段，按共享类型/API schema/状态字段编码，不得各自发明）。
任务定义：${PROJECT_DIR}/planning/prd.json 中 task ${TASK_ID}（读 description + acceptance + files）。

边界（强制）：
- 只改 prd.json 中该 task 的 files 清单内的文件。禁止越界改其他 task 的文件。
- 按 parallel-plan.json 的 contracts 段编码接口，不自己定义类型/schema。
- 遵守 GLM 代码风格纪律（最小改动、不重命名、不抽象，见 phase-dev ③）。
- 写完跑 acceptance 对应的测试（测试驱动 Reflexion，限 2 轮，用外部信号反馈）。
- 完成后 git add + commit 到本分支（${BRANCH}），不要 push、不要合并。

返回：改了哪些文件 + 测试结果 + 是否 blocked。
PROMPT
  echo "  → prompt 写入 $WT_DIR/.task-prompt.md"

  # 可选：用 claude -p 后台真 spawn（限流）
  if [[ "$SPAWN" == "--spawn" ]]; then
    # 限流：达到上限就等一个完成
    while (( ${#PIDS[@]} >= MAX_CONCURRENCY )); do
      for i in "${!PIDS[@]}"; do
        if ! kill -0 "${PIDS[$i]}" 2>/dev/null; then
          unset 'PIDS[i]'
          break
        fi
      done
      sleep 2
    done
    if command -v claude >/dev/null 2>&1; then
      ( cd "$WT_DIR" && claude -p "$(cat .task-prompt.md)" --permission-mode acceptEdits 2>&1 | tee ".task-output.log" ) &
      PIDS+=($!)
      echo "  → spawned claude -p (pid $!) for $TASK_ID"
      SPAWN_COUNT=$((SPAWN_COUNT+1))
    else
      echo "  ⚠️ claude CLI 不可用，无法 --spawn。请控制器用 Agent 工具按本清单并发 spawn。"
    fi
  fi
done

echo ""
echo "=== Wave $WAVE 分发完成 ==="
if [[ "$SPAWN" == "--spawn" && $SPAWN_COUNT -gt 0 ]]; then
  echo "等待 $SPAWN_COUNT 个 agent 完成..."
  wait
  echo "✓ 所有 agent 已返回"
else
  echo "未 --spawn：worktree + prompt 已就绪。控制器请在一条消息里并发 spawn Agent（subagent_type=general-purpose），每个读对应 $WORKTREE_BASE/{task}/.task-prompt.md 执行。"
fi
echo "下一步：scripts/parallel-merge.sh \"$PROJECT_DIR\"  # 按依赖序增量合并"
