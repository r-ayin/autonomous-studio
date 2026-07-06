#!/bin/bash
# UserPromptSubmit hook: 代码同步（提交+拉取二合一）
# 用户发消息时：① 先提交上一轮未推送的代码 ② 再拉取远端最新代码

# ── Step 1: 自动提交+推送（Studio 开发阶段限定）──

PROJECT_DIR=""
for candidate in "$(pwd)" "$HOME/zhinengdiaodu"; do
    if [[ -f "$candidate/planning/status.json" ]]; then
        PROJECT_DIR="$candidate"
        break
    fi
done

if [[ -n "$PROJECT_DIR" ]]; then
    STAGE=$(python3 -c "
import json
try:
    d = json.load(open('$PROJECT_DIR/planning/status.json'))
    print(d.get('currentStage', ''))
except: print('')
" 2>/dev/null)

    if [[ "$STAGE" == "development" ]]; then
        cd "$PROJECT_DIR"
        UNCOMMITTED=$(git status --porcelain -- src/ CLAUDE.md 2>/dev/null | wc -l)
        if [[ "$UNCOMMITTED" -gt 0 ]]; then
            BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
            REMOTE="oneday"
            git add src/ CLAUDE.md 2>/dev/null
            git commit -m "auto: Studio 自动提交 (${UNCOMMITTED} files changed)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>" 2>/dev/null
            if [[ $? -eq 0 ]]; then
                git push "$REMOTE" "$BRANCH" &>/dev/null &
                disown
                echo "Studio 自动提交: ${UNCOMMITTED} 个文件已提交并推送"
            fi
        fi
    fi
fi

# ── Step 2: 拉取远端最新代码 ──

git rev-parse --is-inside-work-tree &>/dev/null || exit 0
git fetch origin &>/dev/null
if git status -uno 2>/dev/null | grep -q 'behind'; then
    BRANCH=$(git branch --show-current 2>/dev/null)
    git pull origin "$BRANCH" &>/dev/null
    echo "已拉取远端最新代码"
fi

exit 0
