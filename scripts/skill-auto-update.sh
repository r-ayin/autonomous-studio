#!/usr/bin/env bash
# skill-auto-update.sh — qunbu 命名空间 skill 通用自动更新脚本
# 用法：bash skill-auto-update.sh [skill-name]
#   不传参数 → 更新所有 qunbu skill
#   传参数   → 只更新指定 skill（如 autonomous-studio）
#
# 逻辑：
#   1. 扫描 ~/.claude/skills/ 下所有 SKILL.md 含 qunbu 仓库地址的 skill
#   2. 比对本地 .version 和远程 HEAD commit hash
#   3. 不一致则 clone → 覆盖 → 记录新 hash → 清理
#   4. 一致则跳过
#
# 可被 hook、cron、或手动触发。

set -euo pipefail

SKILLS_DIR="$HOME/.claude/skills"
GIT_TOKEN="${GITLAB_PRIVATE_TOKEN:?请设置环境变量 GITLAB_PRIVATE_TOKEN}"
GIT_USER="${GITLAB_USER:-$(git config user.name 2>/dev/null || echo 'unknown')}"
GIT_BASE="https://${GIT_USER}:${GIT_TOKEN}@code.alibaba-inc.com/qunbu"
TMP_DIR="/tmp/_skill_update_$$"
UPDATED=0
SKIPPED=0
FAILED=0
TARGET="${1:-}"

update_skill() {
  local skill_name="$1"
  local skill_dir="$SKILLS_DIR/$skill_name"
  local skill_md="$skill_dir/SKILL.md"

  # 从 SKILL.md 提取仓库名
  local repo_line
  repo_line=$(grep -m1 "code.alibaba-inc.com/qunbu/" "$skill_md" 2>/dev/null || true)
  if [ -z "$repo_line" ]; then
    return 0
  fi

  # 提取仓库名（如 autonomous-studio）
  local repo_name
  repo_name=$(echo "$repo_line" | grep -oP 'qunbu/[\w-]+' | head -1 | sed 's|qunbu/||')
  if [ -z "$repo_name" ]; then
    return 0
  fi

  local repo_url="${GIT_BASE}/${repo_name}.git"
  local version_file="$skill_dir/.version"
  local local_hash
  local_hash=$(cat "$version_file" 2>/dev/null || echo "none")

  # 获取远程最新 commit hash
  local remote_hash
  remote_hash=$(git ls-remote "$repo_url" HEAD 2>/dev/null | cut -f1 || echo "")
  if [ -z "$remote_hash" ]; then
    echo "  ✗ $skill_name — 无法访问远程仓库"
    FAILED=$((FAILED + 1))
    return 0
  fi

  # 比对
  if [ "$local_hash" = "$remote_hash" ]; then
    echo "  ✓ $skill_name — 已是最新 (${remote_hash:0:8})"
    SKIPPED=$((SKIPPED + 1))
    return 0
  fi

  # 需要更新
  echo "  ↓ $skill_name — 更新中 (${local_hash:0:8} → ${remote_hash:0:8})..."
  local clone_dir="$TMP_DIR/$repo_name"
  rm -rf "$clone_dir"

  if ! git clone --depth 1 --quiet "$repo_url" "$clone_dir" 2>/dev/null; then
    echo "  ✗ $skill_name — clone 失败"
    FAILED=$((FAILED + 1))
    return 0
  fi

  # 复制文件（保留本地 config/ 目录不覆盖，避免丢钉钉授权等配置）
  # 策略：复制仓库里有的文件，不删除仓库里没有的本地文件
  #
  # ★ monorepo 感知：qunbu/autonomous-studio 这类 monorepo 根目录是 autonomous-studio
  #   skill 本身，子 skill（pm-spec/serial-agent-handoff/...）住在 skills/<skill-name>/ 下。
  #   如果 skill 目录名和仓库根的 skills/<skill-name>/ 子目录匹配，就从子目录抄
  #   （子 skill）；否则从仓库根抄（skill 本身就是仓库）。不这么做会把 monorepo 根的
  #   SKILL.md 错抄到子 skill 目录，把子 skill 改坏（pm-spec 曾被覆盖成 autonomous-studio）。
  local src_dir="$clone_dir"
  if [ -d "$clone_dir/skills/$skill_name" ]; then
    src_dir="$clone_dir/skills/$skill_name"
  fi
  cd "$src_dir"
  find . -maxdepth 1 -type f ! -name '.git' | while read -r f; do
    cp "$f" "$skill_dir/" 2>/dev/null || true
  done
  # 复制子目录（排除 .git 和 config）
  find . -maxdepth 1 -type d ! -name '.' ! -name '.git' ! -name 'config' ! -name 'node_modules' | while read -r d; do
    cp -r "$d" "$skill_dir/" 2>/dev/null || true
  done
  cd - >/dev/null

  # 记录版本
  echo "$remote_hash" > "$version_file"
  rm -rf "$clone_dir"

  echo "  ✓ $skill_name — 已更新到 ${remote_hash:0:8}"
  UPDATED=$((UPDATED + 1))
}

# 主流程
mkdir -p "$TMP_DIR"
echo "Skill 自动更新检查..."

if [ -n "$TARGET" ]; then
  # 只更新指定 skill
  if [ -f "$SKILLS_DIR/$TARGET/SKILL.md" ]; then
    update_skill "$TARGET"
  else
    echo "  ✗ skill '$TARGET' 不存在"
    FAILED=1
  fi
else
  # 更新所有 qunbu skill
  for skill_dir in "$SKILLS_DIR"/*/; do
    skill_name=$(basename "$skill_dir")
    if [ -f "$skill_dir/SKILL.md" ] && grep -q "qunbu/" "$skill_dir/SKILL.md" 2>/dev/null; then
      update_skill "$skill_name"
    fi
  done
fi

rm -rf "$TMP_DIR"
echo ""
echo "完成：$UPDATED 个已更新，$SKIPPED 个已是最新，$FAILED 个失败"
