"""discovery-gate.py — 发现门禁硬阻断 Hook

PreToolUse + UserPromptSubmit 双事件触发。
项目初始化信号检测 → 创建 .discovery_gate.lock → 阻断技术操作 → 强制苏格拉底发现协议。

这是引擎 §0 发现门禁的系统级强制执行层。没有这个 Hook，门禁只是文档建议。
"""
import os
import re
import sys
import json
import glob as _glob
import time as _time
from datetime import datetime, timezone
import random
import string

if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORKSPACE_ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
LOCK_FILE = os.path.join(WORKSPACE_ROOT, ".claude", "discovery_gate.lock")

# ── 项目初始化信号检测 ──────────────────────────────────
INIT_PATTERNS = [
    re.compile(r"(开启|启动|新建|初始化|创建|初始化|开始做|搞一个|做一个)\s*(.{1,20})?(项目|号|频道|账号|站|工具|系统|应用|App)"),
    re.compile(r"(帮我|帮我规划|规划一下|聊一下|讨论一下)\s*(.{1,20})?(项目|方向|怎么做|做什么)"),
    re.compile(r"这个.{1,20}(项目|号|频道)"),
    re.compile(r"(聊聊|谈谈|说说)\s*(.{1,20})?(方向|规划|计划|想法|定位)"),
]

# 用户确认方向的关键词 — 删除锁文件，放行
CONFIRM_PATTERNS = [
    re.compile(r"(可以开始了|按这个方向|先做起来|开始做|就这么定了|确认|同意|好的.*开始|ok.*开始|行.*开始)"),
    re.compile(r"(就按|就按照|就这个|就这样|按你|听你|你定|你决定)"),
]

# ── 允许通过的文件（发现阶段可读）─────────────────────
ALLOWED_FILES = {"CLAUDE.md", "PROGRESS.md", "GATES.md", "PROJECTS.md", "PROTOCOL.md"}
ALLOWED_SKILLS = {"idea-exploration", "demand-discovery"}

# ── 发现阶段禁用的工具 ──────────────────────────────────
BLOCKED_TOOLS = {"Agent", "TaskCreate", "Workflow"}


def _find_project_dir(user_input: str) -> str | None:
    """从用户输入中提取项目目录名。"""
    # 遍历workspace下的所有目录，匹配用户提到的项目名
    candidates = []
    for entry in os.scandir(WORKSPACE_ROOT):
        if entry.is_dir() and not entry.name.startswith("."):
            candidates.append(entry.name.lower())

    inp_lower = user_input.lower()
    # 优先精确匹配已知项目名
    for c in candidates:
        if c in inp_lower or inp_lower in c:
            return os.path.join(WORKSPACE_ROOT, c)

    # 回退：检查是否有 douyin/shipin/douyinhao 等关键词
    keyword_map = {
        "抖音": "douyin", "douyin": "douyin", "tiktok": "douyin",
        "晚霞": "wanxia", "摄影": "xia", "约拍": "xia",
        "量化": "moni", "股票": "moni", "moni": "moni",
        "爬虫": "pachong-master", "招标": "pachong-master",
    }
    for kw, d in keyword_map.items():
        if kw in inp_lower:
            return os.path.join(WORKSPACE_ROOT, d)

    return None


def _claude_has_todos(project_dir: str) -> bool:
    """检查项目的 CLAUDE.md 是否含未填充的 TODO 占位符。"""
    claude_md = os.path.join(project_dir, "CLAUDE.md")
    if not os.path.isfile(claude_md):
        return True  # 不存在 → 视为需要发现
    try:
        with open(claude_md, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return True

    # 检查 TODO 占位符（project-protocol 自动生成的模板特征）
    todo_markers = [
        "<!-- TODO",
        "TODO:",
        "<!-- TODO:",
        "技术栈：<!-- TODO -->",
        "目的：<!-- TODO",
    ]
    for marker in todo_markers:
        if marker in content:
            return True

    # 检查是否只有框架没有实质内容
    lines = [l.strip() for l in content.split("\n") if l.strip() and not l.strip().startswith("#")]
    # 排除模板骨架行
    substantive = [l for l in lines if not l.startswith(">") and not l.startswith("- [") and "TODO" not in l]
    if len(substantive) < 5:
        return True

    return False


def _progress_is_empty(project_dir: str) -> bool:
    """检查 PROGRESS.md 是否有实质性任务记录。"""
    progress_md = os.path.join(project_dir, "PROGRESS.md")
    if not os.path.isfile(progress_md):
        return True
    try:
        with open(progress_md, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return True

    # 检查是否有完成的或进行中的任务
    has_substantive = False
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- [x]") or stripped.startswith("- [X]"):
            has_substantive = True
            break
        if stripped.startswith("|") and ("✅" in stripped or "🟢" in stripped):
            has_substantive = True
            break
        if "已完成" in stripped and stripped.startswith("-"):
            has_substantive = True
            break

    return not has_substantive


def _detect_init_signal(user_input: str) -> str | None:
    """检测用户输入是否含项目初始化信号。返回匹配的项目目录或 None。"""
    for pattern in INIT_PATTERNS:
        if pattern.search(user_input):
            proj_dir = _find_project_dir(user_input)
            if proj_dir and os.path.isdir(proj_dir):
                return proj_dir
    return None


def _detect_confirm_signal(user_input: str) -> bool:
    """检测用户是否确认方向。"""
    for pattern in CONFIRM_PATTERNS:
        if pattern.search(user_input):
            return True
    return False


def _is_technical_tool_call(tool_name: str, tool_input: dict) -> bool:
    """判断工具调用是否是应被阻断的技术操作。"""
    # Agent spawn → 阻断（除 idea-exploration / demand-discovery）
    if tool_name == "Agent":
        subagent = tool_input.get("subagent_type", "")
        prompt = tool_input.get("prompt", "")
        # idea-exploration 相关的 agent 放行
        for allowed in ALLOWED_SKILLS:
            if allowed in str(tool_input).lower():
                return False
        # 技术相关的 agent 阻断
        tech_keywords = ["implement", "code", "refactor", "build", "fix", "debug",
                         "programming", "coding", "test", "优化", "实现", "开发", "写代码"]
        for kw in tech_keywords:
            if kw in prompt.lower():
                return True
        if subagent in ("general-purpose", "Plan", "ralph-planner", "ralph-reviewer"):
            return True
        return False

    if tool_name in BLOCKED_TOOLS:
        # TaskCreate → 只有尝试创建技术任务时才阻断
        if tool_name == "TaskCreate":
            subject = tool_input.get("subject", "")
            tech_keywords = ["实现", "开发", "写代码", "重构", "修复", "build", "implement", "fix", "refactor"]
            for kw in tech_keywords:
                if kw in subject.lower():
                    return True
            return False
        return True

    # Read/Write/Edit on project technical files → 阻断
    if tool_name in ("Read", "Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return False

        # 解析 lock 文件中的项目路径
        lock_data = _safe_read_lock(LOCK_FILE)
        if not lock_data:
            return False

        locked_project = lock_data.get("project_dir", "")
        if not locked_project:
            return False

        try:
            rel = os.path.relpath(file_path, WORKSPACE_ROOT)
        except ValueError:
            rel = file_path

        # 工作区根级文件放行
        if rel in ALLOWED_FILES or rel in ("PROJECTS.md", "PROTOCOL.md"):
            return False

        # 项目下的文件检查
        proj_name = os.path.basename(locked_project)
        if rel.startswith(proj_name + "/") or rel.startswith(proj_name + "\\"):
            filename = os.path.basename(file_path)
            # 三件套可读
            if filename in ALLOWED_FILES:
                return False
            # 其他项目文件 → 阻断
            return True

        # 非锁定项目的文件 → 放行
        return False

    return False


def _atomic_write_lock(lock_path: str, lock_data: dict) -> None:
    """原子写入 LOCK_FILE：先写临时文件再 os.replace，避免并发 hook 读到半写 JSON。

    安全审计 case-404 (2026-07-01): 原 open('w')+json.dump 非原子，PreToolUse 与
    UserPromptSubmit 并发触发时读端可能 json.load 失败 → 静默放行 → 门禁绕过。
    """
    dir_path = os.path.dirname(lock_path)
    os.makedirs(dir_path, exist_ok=True)
    tmp_fd = None
    tmp_path = lock_path + ".tmp"
    try:
        tmp_fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        payload = json.dumps(lock_data, ensure_ascii=False, indent=2).encode("utf-8")
        os.write(tmp_fd, payload)
        os.fsync(tmp_fd)
    finally:
        if tmp_fd is not None:
            os.close(tmp_fd)
    os.replace(tmp_path, lock_path)


def _safe_read_lock(lock_path: str, retries: int = 1) -> dict | None:
    """容错读取 LOCK_FILE：JSONDecodeError 时短暂退避重读一次，对抗并发半写窗口。"""
    for attempt in range(retries + 1):
        try:
            with open(lock_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            if attempt < retries:
                _time.sleep(0.05)
                continue
            return None
        except Exception:
            return None
    return None


def _audit_log_lock_op(action: str, result: str, project_name: str = "", detail: str = "") -> None:
    """审计埋点(DO B / .claude/decisions/audit-log.schema.json):
    discovery-gate 写 LOCK_FILE 属"文件系统写非 worktree"敏感路径。
    仅在 lock 创建/释放时记录；读操作高频不埋。fail-safe:日志失败吞异常不影响门禁主流程。"""
    try:
        now = datetime.now(timezone.utc)
        date = now.strftime("%Y%m%d")
        date_dashed = now.strftime("%Y-%m-%d")
        rid = now.strftime("%H%M%S")
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        entry = {
            "id": f"audit-{date}-{rid}-{suffix}",
            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "userId": "engine",
            "userRole": "engine",
            "action": action,
            "resource": {"type": "lock_file", "identifier": LOCK_FILE,
                         "project": project_name, "newValue": detail[:200]},
            "result": result,
            "ip": "local",
            "sensitive": True,
            "sensitiveLevel": "low",
            "details": {"reason": "discovery-gate.py LOCK_FILE 状态变更",
                        "errorMessage": detail[:200]},
        }
        adir = os.path.join(WORKSPACE_ROOT, ".audit")
        os.makedirs(adir, exist_ok=True)
        with open(os.path.join(adir, f"audit-{date_dashed}.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # fail-safe


def _create_lock(project_dir: str, trigger_reason: str) -> dict:
    """创建发现门禁锁文件（原子写入）。"""
    lock_data = {
        "project_dir": project_dir,
        "project_name": os.path.basename(project_dir),
        "trigger_reason": trigger_reason,
        "activated_at": "",  # 由主会话填充
        "discovery_rounds": 0,
        "direction_confirmed": False,
    }
    _atomic_write_lock(LOCK_FILE, lock_data)
    _audit_log_lock_op("lock_create", "success", os.path.basename(project_dir), trigger_reason)
    return lock_data


def _release_lock() -> None:
    """释放发现门禁锁。"""
    proj = ""
    try:
        ld = _safe_read_lock(LOCK_FILE)
        if ld:
            proj = ld.get("project_name", "")
    except Exception:
        pass
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
            _audit_log_lock_op("lock_release", "success", proj)
        except Exception as e:
            _audit_log_lock_op("lock_release", "failure", proj, str(e)[:200])


def _inject_discovery_prompt(lock_data: dict) -> str:
    """生成注入系统提示的发现门禁提醒。"""
    proj = lock_data.get("project_name", "未知项目")
    reason = lock_data.get("trigger_reason", "项目初始化")
    return f"""
🔴 [DISCOVERY GATE ACTIVE] 发现门禁已激活 — {proj}

触发原因: {reason}
强制规则:
  🚫 禁止读取/写入项目技术文件
  🚫 禁止 spawn 技术分析子代理
  🚫 禁止输出选择题式提问 (AskUserQuestion with options)
  ✅ 必须执行苏格拉底发现协议 — 一问一答、由宽到窄、复述确认
  ✅ 调用 idea-exploration Skill 执行 10 段发现流程
  ✅ 用户可以随时说"放行"类关键词解除门禁

门禁解除条件: 用户确认方向 → 锁文件自动删除
"""


# ── 主入口 ──────────────────────────────────────────────

def main():
    event = os.environ.get("CLAUDE_HOOK_EVENT", "")
    tool_name = os.environ.get("CLAUDE_HOOK_TOOL_NAME", "")
    user_input = os.environ.get("CLAUDE_HOOK_USER_INPUT", "")

    try:
        hook_input = json.loads(sys.stdin.read()) if sys.stdin.readable() else {}
    except Exception:
        hook_input = {}
    tool_input = hook_input.get("tool_input", {}) if isinstance(hook_input, dict) else {}

    # ── PreToolUse: 阻断检查 ────────────────────────────
    if event == "PreToolUse":
        if not os.path.exists(LOCK_FILE):
            return  # 无锁 → 放行

        lock_data = _safe_read_lock(LOCK_FILE)
        if not lock_data:
            return

        locked_project = lock_data.get("project_dir", "")
        if _is_technical_tool_call(tool_name, tool_input):
            file_path = tool_input.get("file_path", "")
            print(json.dumps({
                "decision": "block",
                "reason": f"🔴 发现门禁激活 — {lock_data.get('project_name', '')} 项目方向未确认\n"
                          f"请先完成方向讨论，或说「可以开始了」解除门禁。\n"
                          f"当前只允许: idea-exploration Skill + 项目三件套读取",
                "blocked_tool": tool_name,
                "blocked_file": file_path,
            }, ensure_ascii=False))
            sys.exit(0)  # 阻断

        # 检查是否是 Skill 调用 — 只放行 idea-exploration 和 demand-discovery
        if tool_name == "Skill":
            skill_name = tool_input.get("skill", "")
            if skill_name not in ALLOWED_SKILLS:
                print(json.dumps({
                    "decision": "block",
                    "reason": f"🔴 发现门禁激活 — 只允许 idea-exploration / demand-discovery Skill\n"
                              f"当前 Skill: {skill_name} 不被允许，请先完成方向讨论",
                }, ensure_ascii=False))
                sys.exit(0)

    # ── UserPromptSubmit: 检测 + 锁定/解锁 ───────────────
    if event == "UserPromptSubmit":
        # 先检查是否已激活 — 如果是，检测用户确认信号
        if os.path.exists(LOCK_FILE):
            lock_data = _safe_read_lock(LOCK_FILE) or {}

            if _detect_confirm_signal(user_input):
                _release_lock()
                proj = lock_data.get("project_name", "")
                print(json.dumps({
                    "decision": "release",
                    "reason": f"✅ 发现门禁解除 — {proj} 方向已确认",
                }, ensure_ascii=False))
                return

            # 更新轮次计数（原子写回）
            lock_data["discovery_rounds"] = lock_data.get("discovery_rounds", 0) + 1
            _atomic_write_lock(LOCK_FILE, lock_data)

            # 超时保护: > 5 轮 → 建议放行
            if lock_data["discovery_rounds"] > 5:
                print(json.dumps({
                    "decision": "warn_timeout",
                    "reason": "⚠️ 已进行 5+ 轮发现对话。如果方向难以确定，建议引擎给出推荐方向并询问「要按这个方向开始吗？」",
                    "discovery_rounds": lock_data["discovery_rounds"],
                }, ensure_ascii=False))
            return

        # 未激活 → 检测是否需要激活
        if not user_input or len(user_input.strip()) < 3:
            return

        proj_dir = _detect_init_signal(user_input)
        if not proj_dir:
            return

        # 检查是否需要发现门禁
        needs_discovery = _claude_has_todos(proj_dir) or _progress_is_empty(proj_dir)
        if not needs_discovery:
            return

        _create_lock(proj_dir, "项目 CLAUDE.md 含未填充模板 或 PROGRESS.md 无实质任务")
        lock_data = _safe_read_lock(LOCK_FILE) or {"project_name": os.path.basename(proj_dir)}

        print(json.dumps({
            "decision": "activate",
            "reason": f"🔴 发现门禁激活 — {lock_data['project_name']} 项目方向未确认，强制进入苏格拉底发现协议",
            "lock_file": LOCK_FILE,
            "injected_prompt": _inject_discovery_prompt(lock_data),
        }, ensure_ascii=False))

    # ── Stop: 检查锁状态，注入提醒 ─────────────────────
    if event == "Stop":
        if os.path.exists(LOCK_FILE):
            lock_data = _safe_read_lock(LOCK_FILE)
            if not lock_data:
                return
            print(json.dumps({
                "decision": "remind",
                "reason": f"⚠️ 发现门禁仍在激活 — {lock_data.get('project_name', '')} 下次会话将继续阻断技术操作",
                "injected_prompt": _inject_discovery_prompt(lock_data),
            }, ensure_ascii=False))


if __name__ == "__main__":
    main()
