#!/usr/bin/env bash
# parallel-merge.sh — 并发构建增量合并（确定性 plumbing）
#
# 读 planning/parallel-plan.json，按 wave 顺序逐个把 parallel/{task-id} 合并进当前分支，
# 每并一个跑集成测试，失败则隔离该分支（不阻塞已成功的合并）。
#
# 用法: parallel-merge.sh <项目目录> [集成测试命令]
#   集成测试命令默认: npm test -- --watchAll=false（找不到则跳过，仅做合并）
set -euo pipefail

PROJECT_DIR="${1:-.}"
INTEGRATION_TEST="${2:-}"
cd "$PROJECT_DIR"

PLAN="planning/parallel-plan.json"
if [[ ! -f "$PLAN" ]]; then
  echo "❌ 未找到 $PLAN" >&2
  exit 1
fi

# 收集所有 task（按 wave 顺序）= 依赖序
TASKS=$(python3 - "$PLAN" <<'PY'
import json, sys
plan = json.load(open(sys.argv[1]))
out = []
for w in sorted(plan.get("waves", []), key=lambda x: x.get("wave", 0)):
    out.extend(w.get("tasks", []))
print("\n".join(out))
PY
)

# 默认集成测试命令探测
if [[ -z "$INTEGRATION_TEST" ]]; then
  if [[ -f package.json ]] && grep -q '"test"' package.json; then
    INTEGRATION_TEST="npm test -- --watchAll=false"
  elif [[ -f Makefile ]] && grep -qE '^test:' Makefile; then
    INTEGRATION_TEST="make test"
  elif ls test_*.py tests/test_*.py 2>/dev/null | head -1 | grep -q .; then
    INTEGRATION_TEST="python3 -m pytest --tb=short -q"
  else
    INTEGRATION_TEST=""
  fi
fi

echo "=== 增量合并（依赖序）==="
echo "集成测试: ${INTEGRATION_TEST:-(无，仅合并)}"
echo ""

MERGED=()
BLOCKED=()

for TASK_ID in $TASKS; do
  BRANCH="parallel/${TASK_ID}"
  echo "── 合并 $TASK_ID ($BRANCH) ──"

  # 分支是否存在
  if ! git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    echo "  ⚠️ 分支 $BRANCH 不存在，跳过（可能该 agent 未产出或 worktree 未提交）"
    BLOCKED+=("$TASK_ID(no-branch)")
    continue
  fi

  # 该分支有无新提交（相对当前 HEAD）
  if [[ -z "$(git log HEAD.."$BRANCH" --oneline 2>/dev/null)" ]]; then
    echo "  ↻ $BRANCH 无新提交，跳过"
    continue
  fi

  # 记录合并前 HEAD，用于测试失败时安全回滚（避免 HEAD@{1} 在有未提交 WIP 时误毁工作区）
  PRE_MERGE_HEAD="$(git rev-parse HEAD)"

  # 合并
  if git merge --no-ff "$BRANCH" -m "merge: 并发构建 $TASK_ID" 2>/dev/null; then
    # 合并成功 → 跑集成测试
    if [[ -n "$INTEGRATION_TEST" ]]; then
      if bash -c "$INTEGRATION_TEST" >/tmp/parallel-merge-test.log 2>&1; then
        echo "  ✅ 合并 + 集成测试通过"
        MERGED+=("$TASK_ID")
      else
        echo "  ❌ 集成测试失败 — 回滚本次合并，隔离 $BRANCH"
        # 优先 merge --abort；仅在 abort 不可用时退回精确 pre-merge commit
        # （不使用 HEAD@{1}，避免 reflog 偏移或存在未提交 WIP 时误毁工作区）
        if ! git merge --abort 2>/dev/null; then
          git reset --hard "$PRE_MERGE_HEAD" 2>/dev/null || true
        fi
        # 把失败分支挪到 parallel-blocked/ 命名空间备查
        git branch -m "$BRANCH" "parallel-blocked/${TASK_ID}" 2>/dev/null || true
        BLOCKED+=("$TASK_ID(test-fail)")
      fi
    else
      echo "  ✅ 合并完成（无集成测试）"
      MERGED+=("$TASK_ID")
    fi
  else
    echo "  ❌ 合并冲突 — 回滚，隔离 $BRANCH"
    git merge --abort 2>/dev/null || git reset --hard "$PRE_MERGE_HEAD" 2>/dev/null || true
    git branch -m "$BRANCH" "parallel-blocked/${TASK_ID}" 2>/dev/null || true
    BLOCKED+=("$TASK_ID(conflict)")
  fi
done

echo ""
echo "=== 合并报告 ==="
echo "成功合并: ${MERGED[*]:-(无)}"
echo "隔离 blocked: ${BLOCKED[*]:-(无)}"
echo ""

if (( ${#BLOCKED[@]} > 0 )); then
  echo "⚠️ 有 blocked 分支（parallel-blocked/）：交主合并 agent 二波重试或人工处理。"
  echo "   查看分支: git branch | grep parallel-blocked"
fi

# 清理已成功合并的 worktree（保留 blocked 的）
echo ""
echo "清理已合并 task 的 worktree..."
for TASK_ID in "${MERGED[@]}"; do
  WT_DIR="../.parallel-worktrees/${TASK_ID}"
  if [[ -d "$WT_DIR" ]]; then
    git worktree remove "$WT_DIR" --force 2>/dev/null || rm -rf "$WT_DIR"
    git branch -d "parallel/${TASK_ID}" 2>/dev/null || true
  fi
done

echo "✓ 完成。主合并 agent 现在应: 修剩余集成 bug → 实跑关键路径 → ③-R 全量对照。"
