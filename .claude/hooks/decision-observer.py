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
STUDIO_STATUS_FILE = os.path.join(PROJECT_DIR, "planning", "status.json")

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

def safe_read_json(filepath: str) -> dict:
    """安全读取 JSON 文件，失败返回空字典"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def safe_write_json(filepath: str, data: dict):
    """安全写入 JSON 文件"""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def read_studio_status() -> dict:
    """读取 Studio status.json，不存在时返回空"""
    return safe_read_json(STUDIO_STATUS_FILE)


def is_studio_draft_pending(status: dict) -> bool:
    """检查是否有待确认的 DRAFT 产物"""
    engine = status.get("engine", {})
    draft = engine.get("draftPending", {})
    return bool(draft.get("stage")) and not draft.get("confirmed", False)


def confirm_studio_draft(status: dict, prompt: str) -> bool:
    """
    更新 Studio status.json 中的 DRAFT 确认状态。
    返回 True 表示确认成功，False 表示无需更新。
    """
    engine = status.get("engine", {})
    draft = engine.get("draftPending", {})
    if not draft.get("stage") or draft.get("confirmed", False):
        return False

    confirmed_stage = draft["stage"]

    # 推进阶段映射
    stage_advance_map = {
        "requirements": "prd",
        "prd": "tech-plan",
        "tech-plan": "development",
        "development": "verification",
        "verification": "review",
        "review": "deployment",
    }
    next_stage = stage_advance_map.get(confirmed_stage, status.get("currentStage"))

    # 更新 status.json
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    status["lastUpdated"] = now
    if confirmed_stage not in status.get("completedStages", []):
        status.setdefault("completedStages", []).append(confirmed_stage)
    status["currentStage"] = next_stage

    engine["draftPending"] = {"stage": None, "artifact": None, "createdAt": None, "confirmed": False}
    engine["blockedReasons"] = [r for r in engine.get("blockedReasons", []) if "待用户审阅" not in r]
    engine["nextActionHint"] = f"已确认 {confirmed_stage}，引擎将在下次心跳自动推进至 {next_stage}"
    engine["lastEngineAction"] = now
    engine["lastEngineResult"] = f"stage_confirm: {confirmed_stage} → {next_stage}"
    engine["consecutiveHeartbeatsBlocked"] = 0

    stageConfidence = engine.get("stageConfidence", {})
    stageConfidence[confirmed_stage] = stageConfidence.get(confirmed_stage, 80)
    engine["stageConfidence"] = stageConfidence

    status["engine"] = engine
    safe_write_json(STUDIO_STATUS_FILE, status)
    return True


def classify_user_input(prompt: str, studio_status: dict = None) -> str:
    """
    用轻量正则对用户输入做快速分类。
    分类: stage_confirm | plan | code | debug | review | meta | question | feedback | chat

    stage_confirm（新增，解决冲突6: DRAFT确认机制）:
      当 Studio 有待确认的 DRAFT 产物时，检测用户的确认信号
    """
    if not prompt or len(prompt.strip()) < 2:
        return "chat"

    p = prompt.lower().strip()

    # stage_confirm: Studio DRAFT 确认检测（优先级最高）
    # 只有当 Studio 有 draftPending 时才激活此分类
    if studio_status and is_studio_draft_pending(studio_status):
        confirm_patterns = (
            r'^(没问题|ok[!！]?|好[的了呀啊!！]?|可以|同意|确认|通过|继续|没有问题'
            r'|approve|confirmed?|looks?\s*good|lgtm|ship\s*it|proceed'
            r'|方案\s*ok|方案没问题|prd\s*ok|没啥问题|可以了)'
        )
        if re.search(confirm_patterns, p):
            return "stage_confirm"

    # stop_auto: 紧急制动（解决冲突5的安全机制）
    if re.search(r'(停(下来)?|暂停|stop\s*auto|关闭自动|别自动|不要自动推进)', p):
        return "stop_auto"

    # feedback（短消息纯反馈）
    if len(p) < 20 and re.search(r'^(yes|ok|no|不行|go\s*ahead|拒绝|行吧|嗯|哦|对的?)$', p):
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


def detect_stuck_patterns(log_file: str, window: int = 5) -> dict:
    """
    分析最近 N 条日志，检测子 Agent 或引擎是否陷入卡住模式。
    返回 {"stuck": bool, "pattern": str, "details": str}

    检测三种模式（借鉴 OpenHands stuck_detector.py）：
    1. 重复动作：连续 N 条 phase 和 tool_calls 完全相同
    2. 反复报错：同一 classification=debug 连续出现 ≥3 次
    3. 无进展：连续 N 条 assistant_response 的 decision_count=0
    """
    result = {"stuck": False, "pattern": "none", "details": ""}
    try:
        if not os.path.exists(log_file):
            return result
        with open(log_file, "rb") as f:
            f.seek(0, 2)
            fsize = f.tell()
            buf = b""
            pos = fsize
            while pos > 0 and buf.count(b"\n") < window * 3:
                read_size = min(4096, pos)
                pos -= read_size
                f.seek(pos)
                buf = f.read(read_size) + buf
        lines = buf.decode("utf-8", errors="replace").strip().split("\n")
        entries = []
        for line in reversed(lines):
            try:
                entry = json.loads(line)
                entries.append(entry)
                if len(entries) >= window * 2:
                    break
            except Exception:
                continue
        entries.reverse()

        responses = [e for e in entries if e.get("type") == "assistant_response"][-window:]
        inputs = [e for e in entries if e.get("type") == "user_input"][-window:]

        # 模式 1：重复动作（连续 phase + tool_calls 完全相同）
        if len(responses) >= 3:
            sigs = [(r.get("phase", ""), tuple(r.get("tool_calls", []))) for r in responses[-3:]]
            if len(set(sigs)) == 1 and sigs[0] != ("", ()):
                result = {"stuck": True, "pattern": "repeat_action",
                          "details": f"连续 {len(sigs)} 次相同动作: phase={sigs[0][0]}, tools={list(sigs[0][1])}"}
                return result

        # 模式 2：反复 debug（连续 debug 分类 ≥3 次）
        if len(inputs) >= 3:
            recent_classes = [i.get("classification") for i in inputs[-3:]]
            if all(c == "debug" for c in recent_classes):
                result = {"stuck": True, "pattern": "repeat_debug",
                          "details": f"连续 {len(recent_classes)} 次 debug 输入，可能陷入排错循环"}
                return result

        # 模式 3：无进展（连续 N 条 decision_count 全为 0）
        if len(responses) >= window:
            if all(r.get("decision_count", 0) == 0 for r in responses[-window:]):
                result = {"stuck": True, "pattern": "no_progress",
                          "details": f"连续 {window} 条响应无决策点，引擎可能空转"}
                return result

    except Exception:
        pass
    return result


SUGGESTIONS_FILE = os.path.join(PROJECT_DIR, ".claude", "memory", "autonomous-suggestions.md")


def append_stuck_warning(stuck_info: dict):
    """将卡住告警追加到建议队列"""
    try:
        os.makedirs(os.path.dirname(SUGGESTIONS_FILE), exist_ok=True)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        warning = f"\n- [{now}] **STUCK:{stuck_info['pattern']}** — {stuck_info['details']}\n"
        with open(SUGGESTIONS_FILE, "a", encoding="utf-8") as f:
            f.write(warning)
    except Exception:
        pass


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
    """UserPromptSubmit: 记录用户输入模式 + Studio 阶段确认检测 + 会话隔离"""
    prompt = data.get("prompt", "") or data.get("user_prompt", "") or data.get("message", "")
    session_id = data.get("session_id", "unknown")

    # 读取 Studio 状态（用于 stage_confirm 检测）
    studio_status = read_studio_status()
    classification = classify_user_input(prompt, studio_status)

    # ── Studio 阶段确认处理（解决冲突6）──────────────────
    stage_confirmed = None
    if classification == "stage_confirm" and studio_status:
        if confirm_studio_draft(studio_status, prompt):
            stage_confirmed = studio_status.get("engine", {}).get("draftPending", {}).get("stage")

    # ── 紧急制动处理（解决冲突5）──────────────────
    if classification == "stop_auto" and studio_status:
        engine = studio_status.get("engine", {})
        engine["autoAdvance"] = False
        engine["blockedReasons"] = engine.get("blockedReasons", []) + ["用户主动停止自动推进"]
        engine["nextActionHint"] = '自动驾驶已暂停。说"继续自动"或"auto on"重新启用'
        studio_status["engine"] = engine
        studio_status["lastUpdated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        safe_write_json(STUDIO_STATUS_FILE, studio_status)

    record = {
        "type": "user_input",
        "session_id": session_id,
        "classification": classification,
        "project_hint": extract_project_hint(prompt),
        "prompt_length": len(prompt),
        "prompt_preview": prompt[:300] if len(prompt) > 300 else prompt,
    }
    if stage_confirmed:
        record["studio_stage_confirmed"] = stage_confirmed
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
        "last_input_type": classification,
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

    # 1.5 Stuck Detection（借鉴 OpenHands stuck_detector 模式分析）
    stuck_info = detect_stuck_patterns(LOG_FILE)
    if stuck_info["stuck"]:
        append_stuck_warning(stuck_info)

    # 2. 构建自主上下文注入
    tools_used = record["tool_calls"]
    phase = record["phase"]
    decisions = record["decision_count"]

    # 读取 Studio 状态（用于 L1 内联感知，解决遗漏I）
    studio_status = read_studio_status()
    studio_stage = None
    studio_hint = None
    if studio_status and studio_status.get("locked"):
        studio_stage = studio_status.get("currentStage")
        studio_hint = studio_status.get("engine", {}).get("nextActionHint")
        # L1 内联检查: 更新 stageConfidence 时间戳
        engine = studio_status.get("engine", {})
        engine["lastEngineAction"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        studio_status["engine"] = engine
        studio_status["lastUpdated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        safe_write_json(STUDIO_STATUS_FILE, studio_status)

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

    # Token 泄漏防护：每 10 轮提醒压缩/切会话（MSR 实测：输入:输出=20-25:1，上下文二次方增长）
    try:
        sfile = get_session_file(session_id)
        if os.path.exists(sfile):
            with open(sfile, "r", encoding="utf-8") as f:
                sc = json.load(f)
            ic = sc.get("input_count", 0)
            if ic > 0 and ic % 10 == 0:
                context_parts.extend([
                    "",
                    f"💡 **TOKEN 泄漏防护**: 本会话已 {ic} 轮。上下文二次方增长，"
                    "建议执行 /compact 总结进展或开新会话继续。代码评审一次性给全部修改意见，不逐条来回。",
                ])
    except Exception:
        pass

    # Studio 阶段状态注入（L1 内联感知，解决遗漏I）
    if studio_stage:
        context_parts.extend([
            "",
            f"**Studio 当前阶段**: {studio_stage} | **自动推进**: {'开启' if studio_status.get('engine', {}).get('autoAdvance', True) else '⏸暂停'}",
        ])
        if studio_hint:
            context_parts.append(f"**下一步**: {studio_hint}")
        draft_pending = studio_status.get("engine", {}).get("draftPending", {})
        if draft_pending.get("stage") and not draft_pending.get("confirmed"):
            context_parts.append(f"⏳ **待确认**: {draft_pending.get('artifact', '产出物')} 草稿等待你审阅")
        correction_pending = studio_status.get("engine", {}).get("routeHealth", {}).get("correctionPending", False)
        if correction_pending:
            summary = studio_status.get("engine", {}).get("routeHealth", {}).get("correctionSummary", "")
            context_parts.append(f"⚠️ **路线修正待处理**: {summary}")

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

    # Stuck 告警注入
    if stuck_info["stuck"]:
        context_parts.extend([
            "",
            f"⚠️ **STUCK 检测**: {stuck_info['pattern']} — {stuck_info['details']}",
            "建议：换一个方法试试，或者暂停自主行动等用户指导。",
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
