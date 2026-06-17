#!/usr/bin/env python3
"""
Decision Observer — 自主决策引擎的感知层 Hook。

触发时机:
  - UserPromptSubmit: 捕获用户输入模式，分类写入决策日志
  - Stop: 捕获助手响应模式，注入自主上下文到下次会话

设计原则:
  - 轻量 (<200ms)，纯正则匹配，不阻塞主流程
  - 所有错误静默处理，不影响 Claude Code 正常运行
  - 仅做日志写入 + 上下文注入，不直接修改任何项目文件
"""

import os
import sys
import json
import re
from datetime import datetime, timezone

# 强制 UTF-8：防止 Windows GBK 环境导致 stdin 解码失败 / stdout emoji 崩溃
if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
LOG_FILE = os.path.join(PROJECT_DIR, ".claude", "decision-log.jsonl")
STATE_FILE = os.path.join(PROJECT_DIR, ".claude", "memory", "autonomous-state.md")

# ── 辅助函数 ────────────────────────────────────────────

def safe_read_stdin():
    """安全读取 stdin JSON，失败返回空字典"""
    try:
        data = sys.stdin.read().strip()
        if not data:
            return {}
        result = json.loads(data)
        if not isinstance(result, dict):
            return {}
        return result
    except Exception:
        return {}

def safe_append_jsonl(filepath: str, record: dict):
    """安全追加一行 JSON 到日志文件"""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        record["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 静默失败

def classify_user_input(prompt: str) -> str:
    """
    用轻量正则对用户输入做快速分类。
    分类: plan | code | debug | review | meta | question | feedback | chat
    """
    if not prompt or len(prompt.strip()) < 2:
        return "chat"

    p = prompt.lower()

    # feedback（仅当消息是纯反馈时匹配——短消息 + 以反馈词开头）
    if len(prompt.strip()) < 20 and re.search(r'^(好[的了呀啊]?|yes|ok|no|不行|可以|同意|继续|go\s*ahead|approve|拒绝|行吧|嗯|哦|对的?)$', p.strip()):
        return "feedback"

    # plan：规划/设计/方案
    if re.search(r'(规划|计划|设计|方案|架构|specify|design|tasks|task|plan|prd|roadmap|目标|讨论)', p):
        return "plan"

    # debug：修复/排查/报错/为什么
    if re.search(r'(修复|fix|bug|error|错误|报错|失败|为什么|怎么(回|办|做)|怎么回事|排查|debug|好了吗|还不行|没收到|不对$)', p):
        return "debug"

    # review：审查/检查/安全
    if re.search(r'(审查|review|审计|audit|检查|check|验证|verify|看一[下看]|安全)', p):
        return "review"

    # meta：配置/skill/hook/设置
    if re.search(r'(设置|config|hook|skill|mcp|插件|安装|删除|卸载|禁用|启用|注册|命令|工作区|目录)', p):
        return "meta"

    # code：实现/写代码/构建
    if re.search(r'(实现|implement|写|build|创建|create|生成|开发|编程|重构|refactor|添加|新增|加上)', p):
        return "code"

    # question：疑问句
    if re.search(r'(怎么|如何|how|what|which|哪个|什么|是什么|有没有|能不能|可以吗|有.*吗)', p):
        return "question"

    return "chat"


def extract_project_hint(prompt: str) -> str:
    """从用户输入中提取项目名称提示"""
    project_map = {
        "wanxia": "wanxia", "晚霞": "wanxia", "小红书": "wanxia",
        "xia": "xia", "山夏": "xia", "摄影": "xia", "约拍": "xia",
        "moni": "moni", "股票": "moni", "量化": "moni", "因子": "moni",
        "pachong": "pachong-master", "爬虫": "pachong-master",
        "tender": "pachong-master", "招投标": "pachong-master", "雷达": "pachong-master",
        "tolaria": "tolaria", "laputa": "tolaria",
        "抖音": "douyin", "douyin": "douyin",
    }
    for key, project in project_map.items():
        if key in prompt.lower():
            return project
    return "unknown"


def extract_tool_calls(message: str) -> list:
    """从助手消息中提取工具调用信息（轻量启发式）"""
    tools = []
    tool_patterns = {
        "Read": r'(读取|阅读|read)', "Write": r'(写入|创建文件|write)',
        "Edit": r'(编辑|修改|edit)', "Bash": r'(运行|执行|bash|shell)',
        "Grep": r'(搜索|查找|grep)', "Glob": r'(匹配文件|glob)',
        "WebSearch": r'(联网搜索|web\s*search)', "WebFetch": r'(获取网页|web\s*fetch)',
        "Agent": r'(子agent|子代理|subagent|agent)',
        "AskUserQuestion": r'(询问|确认|ask)',
    }
    for tool, pattern in tool_patterns.items():
        if re.search(pattern, message.lower()):
            tools.append(tool)
    return tools


def extract_phase(message: str) -> str:
    """从助手消息中检测开发阶段"""
    if re.search(r'(规划|方案|spec|设计|design|架构|讨论)', message):
        return "stage_0_planning"
    if re.search(r'(实现|implement|写代码|构建|build|coding)', message):
        return "stage_1_coding"
    if re.search(r'(审查|review|审计|audit|检查|安全|质量)', message):
        return "stage_2_quality"
    if re.search(r'(ralph|自动执行|自主)', message):
        return "stage_3_autonomous"
    if re.search(r'(验证|verify|run|启动|ship|交付|部署)', message):
        return "stage_4_delivery"
    return "unknown"


def count_decisions(message: str) -> int:
    """统计助手消息中的决策点数量（单次编译正则，一次扫描）"""
    _DECISION_RE = re.compile(
        r'(我(?:决定|选择|建议|推荐|将|会|采用))'
        r'|(最好的(?:方式|方案|做法)是)'
        r'|(应该|应当|需要)'
        r'|(关键(?:是|在于))'
        r'|(最终(?:方案|决定))'
        r'|(我认为|我觉得)'
        r"|(I(?:'ll| will| recommend| suggest| decided))",
        re.IGNORECASE
    )
    matches = _DECISION_RE.findall(message)
    count = sum(1 for m in matches if any(m))
    return min(count, 10)


# ── 会话隔离 ──────────────────────────────────────────────

def get_session_file(session_id: str) -> str:
    """获取当前会话的上下文文件路径"""
    return os.path.join(PROJECT_DIR, ".claude", "sessions", f"{session_id}.json")


def write_session_context(session_id: str, data: dict):
    """写入会话隔离上下文文件"""
    try:
        filepath = get_session_file(session_id)
        existing = {}
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.update(data)
        existing["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ── 主逻辑 ──────────────────────────────────────────────

def handle_user_prompt_submit(data: dict):
    """UserPromptSubmit: 记录用户输入模式 + 会话隔离"""
    # Claude Code 传入的字段名可能是 "prompt" 或 "user_prompt"
    prompt = data.get("prompt", "") or data.get("user_prompt", "") or data.get("message", "")
    session_id = data.get("session_id", "unknown")

    record = {
        "type": "user_input",
        "session_id": session_id,
        "classification": classify_user_input(prompt),
        "project_hint": extract_project_hint(prompt),
        "prompt_length": len(prompt),
        "prompt_preview": prompt[:300] if len(prompt) > 300 else prompt,
    }
    safe_append_jsonl(LOG_FILE, record)

    # 会话隔离：记录本会话的用户输入历史
    existing_count = 0
    try:
        sfile = get_session_file(session_id)
        if os.path.exists(sfile):
            with open(sfile, "r", encoding="utf-8") as f:
                existing_count = json.load(f).get("input_count", 0)
    except Exception:
        pass
    write_session_context(session_id, {
        "session_id": session_id,
        "type": "user_session",
        "last_input_type": record["classification"],
        "last_project": record["project_hint"],
        "input_count": existing_count + 1,
    })


def handle_stop(data: dict):
    """Stop: 记录助手模式 + 注入自主上下文 + 会话隔离"""
    message = data.get("last_assistant_message", "")
    session_id = data.get("session_id", "unknown")

    # 1. 日志记录（含 session 标记）
    safe_append_jsonl(LOG_FILE, {
        "type": "session_boundary",
        "session_id": session_id,
        "boundary": "stop",
    })

    record = {
        "type": "assistant_response",
        "session_id": session_id,
        "tool_calls": extract_tool_calls(message),
        "phase": extract_phase(message),
        "decision_count": count_decisions(message),
        "message_length": len(message),
        "message_preview": message[:500] if len(message) > 500 else message,
    }
    safe_append_jsonl(LOG_FILE, record)

    # 会话隔离：更新本会话的状态
    write_session_context(session_id, {
        "session_id": session_id,
        "last_phase": record["phase"],
        "last_tool_calls": record["tool_calls"],
        "last_decision_count": record["decision_count"],
    })

    # 2. 构建自主上下文注入
    tools_used = record["tool_calls"]
    phase = record["phase"]
    decisions = record["decision_count"]

    # 尝试从日志中获取当前项目（从末尾向前读最后 20 行，避免加载整个文件）
    active_project = "unknown"
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "rb") as f:
                f.seek(0, 2)  # 定位到文件末尾
                fsize = f.tell()
                buf = b""
                chunk_size = 4096
                pos = fsize
                lines_found = 0
                while pos > 0 and lines_found < 20:
                    read_size = min(chunk_size, pos)
                    pos -= read_size
                    f.seek(pos)
                    buf = f.read(read_size) + buf
                    lines = buf.split(b"\n")
                    needed = min(20, len(lines))
                    buf = b"\n".join(lines[-needed:])  # keep only what we need
                    lines_found = len([l for l in lines[-needed:] if l.strip()])
                # parse last 20 lines from end
                for line in reversed(lines[-20:]):
                    try:
                        entry = json.loads(line.decode("utf-8"))
                        if entry.get("type") == "user_input" and entry.get("project_hint") != "unknown":
                            active_project = entry["project_hint"]
                            break
                    except Exception:
                        continue
    except Exception:
        pass

    # 3. 输出 additionalContext（注入到 Claude 的下次系统提示，含会话隔离）
    context_parts = [
        "## [AUTONOMOUS CONTEXT — 自主决策引擎]",
        "",
        f"**会话**: {session_id[-8:]} | **活跃项目**: {active_project} | **阶段**: {phase}",
        f"**使用工具**: {', '.join(tools_used) if tools_used else '无'} | **决策点**: {decisions}",
        "[ISOLATION] 日志和状态绑定到此 session_id，跨会话不混淆",
    ]

    # 如果是在代码阶段，给出具体提示
    if phase == "stage_1_coding" and active_project != "unknown":
        context_parts.extend([
            "",
            "**自主跟进建议**:",
            f"- 检查 `{active_project}/PROGRESS.md` 是否需要更新",
            f"- 验证刚才的修改是否通过了 `{active_project}/GATES.md`",
            "- 在本次回复末尾执行 L1 内联快速检查",
        ])

    context_parts.extend([
        "",
        "[AUTO] 自主循环活跃中 | L2 心跳 7min | 本次回复末尾执行 L1 内联检查",
    ])

    additional_context = "\n".join(context_parts)

    # 写入状态文件
    try:
        state_content = f"""---
name: autonomous-state
description: 自主决策引擎运行状态
metadata:
  type: project
---

# 引擎状态
- **最后活跃**: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
- **活跃项目**: {active_project}
- **当前阶段**: {phase}
- **工具调用**: {', '.join(tools_used) if tools_used else '无'}
- **决策点**: {decisions}
- **自主循环**: 活跃
"""
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            f.write(state_content)
    except Exception:
        pass

    # 返回给 Claude Code 的注入上下文
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": additional_context
        }
    }, ensure_ascii=False))


# ── 入口 ─────────────────────────────────────────────────

def main():
    try:
        hook_event = os.environ.get("CLAUDE_HOOK_EVENT", "unknown")
        data = safe_read_stdin()

        if hook_event == "UserPromptSubmit":
            handle_user_prompt_submit(data)
        elif hook_event == "Stop":
            handle_stop(data)
        else:
            # 未知事件 → 静默
            print("{}")

    except Exception:
        # 全局兜底：任何异常都不影响主流程
        print("{}")


if __name__ == "__main__":
    main()
