#!/bin/bash
# PostToolUse hook: Skill 文件修改后提醒推送到 GitLab

FILE_PATH=$(echo "$CLAUDE_TOOL_INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('file_path', ''))
except:
    print('')
" 2>/dev/null)

SKILLS_DIR="$HOME/.claude/skills"

# 只处理 skills 目录下的文件
case "$FILE_PATH" in
    "$SKILLS_DIR"/*) ;;
    *) exit 0 ;;
esac

# 提取 skill 名称（第一级子目录）
SKILL_NAME=$(echo "$FILE_PATH" | sed "s|$SKILLS_DIR/||" | cut -d'/' -f1)
[ -z "$SKILL_NAME" ] && exit 0

SKILL_MD="$SKILLS_DIR/$SKILL_NAME/SKILL.md"
[ ! -f "$SKILL_MD" ] && exit 0

# 检查 SKILL.md 是否有 repository 字段（有仓库才需要推送）
REPO=$(grep -m1 '^repository:' "$SKILL_MD" | sed 's/repository: *//')
[ -z "$REPO" ] && exit 0

# 记录到待推送文件（去重）
PENDING="$HOME/.claude/.pending-skill-pushes"
touch "$PENDING"
if ! grep -qF "$SKILL_NAME" "$PENDING" 2>/dev/null; then
    echo "$SKILL_NAME|$REPO" >> "$PENDING"
fi

# 统计待推送数量
COUNT=$(wc -l < "$PENDING" | tr -d ' ')
if [ "$COUNT" -ge 1 ]; then
    NAMES=$(cut -d'|' -f1 "$PENDING" | tr '\n' '、' | sed 's/、$//')
    echo "Skill 提醒: ${NAMES} 有修改未推送到 GitLab（共 ${COUNT} 个）"
fi
