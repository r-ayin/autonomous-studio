#!/usr/bin/env python3
"""SessionStart: 检测上次会话中断 → 自动注入恢复指令 + 自主引擎固件

工作原理：
  stdout 输出会被作为 additionalContext 注入到 Claude Code 系统提示中。
  - 有检查点 → 恢复指令 + 引擎固件
  - 无检查点 → 仅引擎固件（确保每次会话引擎指令都在）

引擎固件：
  每次 SessionStart 强制注入，不依赖 CLAUDE.md 是否被压缩。
"""

import os
import json
import sys
from datetime import datetime, timezone, timedelta

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
CHECKPOINT_DIR = os.path.join(PROJECT_DIR, ".claude", "checkpoints")
LATEST_FILE = os.path.join(CHECKPOINT_DIR, "latest.json")


def read_latest_checkpoint():
    if os.path.exists(LATEST_FILE):
        return _read_json(LATEST_FILE)
    if os.path.isdir(CHECKPOINT_DIR):
        files = sorted([
            f for f in os.listdir(CHECKPOINT_DIR)
            if f.startswith("checkpoint_") and f.endswith(".json")
        ], reverse=True)
        if files:
            return _read_json(os.path.join(CHECKPOINT_DIR, files[0]))
    return None


def _read_json(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def checkpoint_age(checkpoint):
    try:
        ts = checkpoint.get("timestamp", "")
        if not ts:
            return None
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - t).total_seconds() / 3600
    except (ValueError, TypeError):
        return None


def should_resume(checkpoint):
    if not checkpoint:
        return False
    age = checkpoint_age(checkpoint)
    return age is not None and age < 24


def build_resume_directive(checkpoint):
    git_info = checkpoint.get("git", {})
    branch = git_info.get("branch", "N/A")
    last_commit = git_info.get("last_commit", "N/A")
    cwd = checkpoint.get("cwd", PROJECT_DIR)
    timestamp = checkpoint.get("timestamp", "unknown")
    activities = checkpoint.get("recent_activity", [])
    last_prompt = ""
    for a in reversed(activities):
        if a.get("event") == "prompt":
            last_prompt = a.get("text", "")
            break
    memory_files = checkpoint.get("memory_files", [])
    memory_list = ", ".join(m.get("name", "") for m in memory_files[:8])
    session_id = checkpoint.get("session_id", "")[-8:]
    age = checkpoint_age(checkpoint)
    age_str = f"{age:.1f} 小时" if age else "未知"

    return f"""## [AUTO-RESUME] 自动会话恢复

上一条 Claude Code 会话在 **{age_str}前** 中断（SSH 断开 / 进程终止）。

**你必须自动执行恢复，不需要等用户说「继续上次的工作」：**

1. 读取检查点: `{LATEST_FILE}`
2. 读取进度 memory: `{PROJECT_DIR.replace(chr(92), '/')}/memory/session-progress.md`
3. 如果 MEMORY.md 存在，也读取它: `{PROJECT_DIR.replace(chr(92), '/')}/memory/MEMORY.md`
4. 然后向用户报告上次会话状态

### 上次会话快照
| 项目 | 内容 |
|------|------|
| 会话 ID | ...{session_id} |
| 中断时间 | {timestamp} |
| 距今 | {age_str} |
| Git 分支 | {branch} |
| 最后提交 | {last_commit} |
| 工作目录 | {cwd} |
| Memory 文件 | {memory_list or '（无）'} |
| 最后对话 | {last_prompt[:200] if last_prompt else '（无记录）'} |
"""


def build_engine_firmware():
    """构建自主引擎固件指令 — 每次 SessionStart 强制注入"""
    # 读取 Studio 状态（解决遗漏F）
    studio_context = ""
    try:
        status_file = os.path.join(PROJECT_DIR, ".planning", "status.json")
        if os.path.exists(status_file):
            with open(status_file, "r", encoding="utf-8") as f:
                status = json.load(f)
            if status.get("locked"):
                stage = status.get("currentStage", "unknown")
                notes = status.get("notes", "")
                engine = status.get("engine", {})
                auto_advance = engine.get("autoAdvance", True)
                next_hint = engine.get("nextActionHint", "")
                draft = engine.get("draftPending", {})
                correction = engine.get("routeHealth", {}).get("correctionPending", False)

                studio_context = f"""
### ★ Studio 自动驾驶状态（上次会话恢复）
| 字段 | 值 |
|------|---|
| 当前阶段 | {stage} |
| 主任务 | {notes} |
| 自动推进 | {'✅ 开启' if auto_advance else '⏸ 已暂停'} |
| 下一步 | {next_hint} |"""
                if draft.get("stage") and not draft.get("confirmed"):
                    studio_context += f"\n| ⏳ 待确认 | {draft.get('artifact', '')} 草稿等待审阅 |"
                if correction:
                    summary = engine.get("routeHealth", {}).get("correctionSummary", "")
                    studio_context += f"\n| ⚠️ 路线修正 | {summary} |"
                studio_context += "\n\n说「继续」或「接上次工作」即可恢复 Studio 流程。"
    except Exception:
        pass

    return f"""## 🔴 [AUTONOMOUS ENGINE FIRMWARE v3.0 — SessionStart 强制注入]

此指令由 `resume-checkpoint.py` Hook 注入，**每次会话启动必定执行**。
即使 CLAUDE.md 被压缩/丢失，以下指令仍然存在。{studio_context}

### 强制行为（不可跳过）
1. **每次回复末尾 → 执行 L1 内联自主检查**
   - 读 `.claude/decision-log.jsonl` 最后 5 行
   - 判断未完跟进 → 信心分 ≥71 直接执行（不询问用户）
   - 有 Studio status.json 且 locked=true → 同时检查阶段状态
   - 无事可做 → 静默，不额外输出
2. **首条回复 → 读 `autonomous-state.md` → 确认当前目标**
   - 等用户说了第一句话后才开始，不抢先
   - 目标 `achieved` → 仅报告，不行动
   - 目标 `in_progress` → 检查冷却(>3次)→按信心分行动
3. **引擎 Skill**: 说"自主模式"/"别等我"/"自动继续"激活
4. **Studio 自动驾驶**: 说"继续"/"接上次"/"studio auto on"恢复 Studio 流程
5. **CronCreate 心跳**: L2(每7min·执行轨) + L3(每60min·研判轨)，持久自修复

### 固件完整性自检（引擎 PHASE A 执行）
- `settings.json` → UserPromptSubmit + Stop hook 包含 decision-observer.py？缺失→恢复
- `skill/SKILL.md` → 存在？缺失→从 decision-patterns.md 重建
- `skill/decision-agent-prompt.md` → 存在？（子代理操作手册）
- CronCreate 心跳 → 存活？缺失→自动 CronCreate 重建
- **L6 Watchdog** → 读 `.claude/.watchdog_heartbeat`，年龄 >10min? → WSL cron 可能挂了

### 会话隔离
- 每条决策日志带 `session_id`，跨会话不混淆
- 引擎状态文件锁绑定到当前 session
- `.claude/sessions/{{session_id}}.json` 存会话级上下文

### 硬限制
- 绝不可修改 PROTOCOL.md
- 绝不可删除用户文件
- 绝不可绕过 GATES.md
- Studio 自动驾驶模式下绝不自动 git push（hook 会拦截）
- 部署阶段（⑦）永远等用户确认
- settings.json **仅限恢复已有 Hook 注册**（不得新增/删除权限、不得修改其他配置）
- 连续 3 次自主行动后无用户交互 → 强制冷却
"""


# ── main ───────────────────────────────────────
if __name__ == "__main__":
    checkpoint = read_latest_checkpoint()

    if checkpoint and should_resume(checkpoint):
        directive = build_resume_directive(checkpoint)
        firmware = build_engine_firmware()
        print(directive + "\n\n" + firmware)
    else:
        print(build_engine_firmware())
