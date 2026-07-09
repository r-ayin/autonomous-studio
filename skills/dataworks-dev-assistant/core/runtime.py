#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行时工具函数：状态持久化、待办管理、工作空间解析

独立于 BFFClient 类，供脚本和客户端共用。
"""

import atexit
import json
import os
import sys
import time
import uuid
from datetime import datetime


def _read_skill_version():
    """从 SKILL.md frontmatter 读取 version 字段"""
    skill_md = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "SKILL.md")
    try:
        with open(skill_md, "r", encoding="utf-8") as f:
            in_frontmatter = False
            for line in f:
                line = line.strip()
                if line == "---":
                    if in_frontmatter:
                        break
                    in_frontmatter = True
                    continue
                if in_frontmatter and line.startswith("version:"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "unknown"


def _load_env_file(path):
    """手动解析 .env 文件，无需 python-dotenv 依赖"""
    if not os.path.exists(path):
        return {}
    env = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # 去掉引号
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            env[key] = value
    return env


class WriteOperationError(Exception):
    """写操作未经确认时抛出的异常"""
    pass


# 已知工具脚本：文件名 → 简短用途说明
_TOOL_SCRIPTS = {
    "trace_upstream.py": "排查分区停产（python trace_upstream.py '表名'）",
    "search_nodes.py": "搜索表的产出节点（python search_nodes.py '表名'，输出工作空间/创建时间/修改时间/修改人，--with-instances 查实例状态）",
    "find_node_code.py": "根据节点ID获取代码（python find_node_code.py --project-id <id> --task-id <taskId> --runtime 查运行态代码，--entity-id <entityId> 查开发态代码；只传 --task-id 自动反查 entityId）",
    "analyze_checker_rca.py": "分析发布检查器失败根因（python analyze_checker_rca.py --project-id <id> --uuid <node_uuid>）",
    "smoke_test.py": "冒烟测试（python smoke_test.py --project-id <id> --task-id <taskId>，在开发环境运行节点验证逻辑）",
}

# 运行时文件统一目录
_RUNTIME_DIR = ".dataworks"

# 会话状态持久化文件名
_SESSION_STATE_FILE = "session_state.json"

# 待确认写操作文件名
_PENDING_WRITE_FILE = "pending_write.json"

# 异步任务待办列表
_BACKLOGS_FILE = "backlogs.json"

# Session ID 持久化（与 telemetry.py 共享，单一实现源）
_SESSION_ID_FILE = os.path.join(os.path.expanduser("~"), _RUNTIME_DIR, "current_session")
_SESSION_IDLE_SECONDS = 30 * 60  # 30 分钟无活动视为新会话


def _touch_session_file(sid):
    """写入 sid 并刷新 mtime。静默失败。"""
    try:
        os.makedirs(os.path.dirname(_SESSION_ID_FILE), exist_ok=True)
        with open(_SESSION_ID_FILE, "w", encoding="utf-8") as f:
            f.write(sid)
    except Exception:
        pass


# ── Bootstrap context：从启动环境变量 materialize 到 session_state.context ──
# 上游启动器只管 export 这组环境变量，skill 自己吸收到 session_state。
# 详见 docs/design/startup-context-spec.md（方案 B）。
_BOOTSTRAP_ENV_MAP = [
    # (env var, context path，用 . 分隔嵌套)
    ("DW_PROJECT_ID",         "projectId"),
    ("DW_PROJECT_NAME",       "projectName"),
    ("DW_USER_BASE_ID",       "user.baseId"),
    ("DW_USER_DISPLAY_NAME",  "user.displayName"),
    ("DW_USER_ACCOUNT",       "user.account"),
    ("DW_TENANT_ID",          "tenantId"),
    ("DW_REGION",             "region"),
    ("DW_STARTUP_AT",         "startupAt"),
    ("DW_STARTUP_SOURCE",     "source"),
]


def _set_nested(d, path, value):
    """把 value 写到 d[key1][key2]...，按需创建中间 dict"""
    keys = path.split(".")
    cur = d
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = value


def bootstrap_context(work_dir=None):
    """把启动环境变量 DW_* materialize 到 $CWD/.dataworks/session_state.json 的 context 段。

    语义：
      - 启动器只 export 环境变量（或写 ~/.dataworks/.env），不直接写 JSON
      - 本函数在 skill 首次需要 context 时自动调用一次（resolve_project_id / get_my_base_id 的前置）
      - 已有 context.projectId 时默认跳过，除非 env 的 DW_STARTUP_AT 比 session 里的 bootstrappedAt 更新

    静默失败：写入错误不阻塞主流程。
    """
    # 收集本次要吸收的字段
    collected = {}
    for env_var, ctx_path in _BOOTSTRAP_ENV_MAP:
        v = os.environ.get(env_var)
        if v:  # 空字符串和 None 都跳过
            _set_nested(collected, ctx_path, v)
    if not collected:
        return

    base = work_dir or os.path.expanduser("~")
    path = os.path.join(base, _RUNTIME_DIR, _SESSION_STATE_FILE)
    state = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except (json.JSONDecodeError, OSError, ValueError):
            state = {}
    ctx = state.get("context") or {}

    # 幂等：已 bootstrap 过同样 startupAt，或 context 已有 projectId 且 env 没带更新的 startupAt，跳过
    env_startup_at = collected.get("startupAt")
    last_bootstrapped_at = ctx.get("bootstrappedAt")
    if ctx.get("projectId"):
        if not env_startup_at or env_startup_at == last_bootstrapped_at:
            return  # 已有 context 且 env 未更新，不重复吸收

    # 合并：env 字段覆盖到 ctx，但保留 skill 后续写入的非 bootstrap 字段
    merged = dict(ctx)  # 保留原有字段
    for k, v in collected.items():
        if isinstance(v, dict):
            sub = dict(merged.get(k) or {})
            sub.update(v)
            merged[k] = sub
        else:
            merged[k] = v
    merged["bootstrappedAt"] = env_startup_at or datetime.now().isoformat(timespec="seconds")
    state["context"] = merged

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError:
        pass  # 静默失败，不阻塞主流程


def get_session_id():
    """获取当前 session_id，自动创建/续租。

    优先级：
      1. 环境变量 DW_BFF_SESSION_CODE（同进程或父进程显式 export）
      2. .dataworks/current_session 文件（mtime < 30 分钟则复用）
      3. 生成新 sid + 写文件 + 写环境变量

    每次调用都会 touch 文件，刷新空闲计时。

    Returns:
        str: 12 字符的 session ID
    """
    sid = os.environ.get("DW_BFF_SESSION_CODE")
    if sid:
        _touch_session_file(sid)
        return sid

    # 尝试从文件恢复
    try:
        if os.path.isfile(_SESSION_ID_FILE):
            age = time.time() - os.path.getmtime(_SESSION_ID_FILE)
            if age < _SESSION_IDLE_SECONDS:
                with open(_SESSION_ID_FILE, "r", encoding="utf-8") as f:
                    sid = f.read().strip()
                if sid:
                    os.environ["DW_BFF_SESSION_CODE"] = sid
                    _touch_session_file(sid)
                    return sid
    except Exception:
        pass

    # 生成新 sid
    sid = uuid.uuid4().hex[:12]
    os.environ["DW_BFF_SESSION_CODE"] = sid
    _touch_session_file(sid)
    return sid


def get_runtime_dir(work_dir=None):
    """获取运行时文件目录，自动创建 .dataworks/"""
    base = work_dir or os.path.expanduser("~")
    d = os.path.join(base, _RUNTIME_DIR)
    os.makedirs(d, exist_ok=True)
    return d


# 当前任务推断：pending 文件 → 任务标签
# 这些 pending 文件由现有脚本写入和清理，atexit 只读不写
_PENDING_TASK_LABELS = {
    "pending_di_sync_job.json": "创建 DI 同步任务",
    "pending_di_create_table.json": "创建 DI 同步任务（建表确认中）",
    "pending_deploy.json": "发布节点（开发环境）",
    "pending_deploy_prod.json": "发布节点（生产环境）",
    "pending_write.json": "写操作待确认",
}


def _detect_current_task(work_dir=None):
    """从 .dataworks/pending_*.json 推断当前任务标签

    选 mtime 最新的 pending 文件作为"当前任务"（最近活跃的）。
    pending 文件由各脚本自行清理，本函数只读不写。

    Returns:
        str | None: 任务标签，无活跃 pending 时返回 None
    """
    runtime_dir = get_runtime_dir(work_dir)
    candidates = []
    for fname, label in _PENDING_TASK_LABELS.items():
        path = os.path.join(runtime_dir, fname)
        if os.path.exists(path):
            try:
                candidates.append((os.path.getmtime(path), label))
            except OSError:
                pass
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _atexit_print_status():
    """进程退出前输出简洁状态提示（atexit 钩子）

    输出原则：信号最大化、噪音最小化。只显示对 agent 决策有价值的字段：
    - 🎯 当前任务（从 pending 文件推断）
    - 工作空间
    - 已确认参数概览（confirmed_params 业务 keys 列表）
    - 异步任务待查看
    """
    state_path = os.path.join(get_runtime_dir(), _SESSION_STATE_FILE)
    if not os.path.exists(state_path):
        return
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        return

    parts = []

    # 🎯 当前任务（从 pending 文件推断）
    task = _detect_current_task()
    if task:
        parts.append(f"🎯 {task}")

    # 工作空间
    pid = state.get("context", {}).get("projectId")
    if pid:
        parts.append(f"工作空间={pid}")

    # 📌 已确认参数概览（仅 keys，前 4 个 + 总数）
    cp = state.get(_CONFIRMED_PARAMS_KEY, {})
    if isinstance(cp, dict):
        business_keys = [k for k in cp.keys() if not k.startswith("_")]
        if business_keys:
            preview = ", ".join(business_keys[:4])
            if len(business_keys) > 4:
                preview += f" 等 {len(business_keys)} 项"
            parts.append(f"📌 已确认参数: {preview}")

    # 📋 异步任务待查看
    backlogs = load_backlogs()
    if backlogs:
        parts.append(f"📋 {len(backlogs)} 个异步任务待查看")

    if parts:
        print(f"\n[会话状态] {' | '.join(parts)}")


atexit.register(_atexit_print_status)


def _atomic_write_json(path, obj):
    """原子写 JSON：先写 tmp 文件再 os.replace，崩溃不截断目标文件。

    与 bootstrap_context 的写入语义一致（RUNTIM-03：原 save_tool_result
    用 open(w)+json.dump 非原子，崩溃会留下截断的 session_state.json）。
    失败打印 stderr 不抛（RUNTIM-06：原裸 `except: pass` 静默吞错）。
    """
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except (OSError, TypeError, ValueError) as e:
        print(f"⚠️ 写入失败 {path}: {e}", file=sys.stderr)


def save_tool_result(tool_name, result_dict, work_dir=None):
    """Save structured tool result to a JSON file in the working directory.

    Writes to: .dataworks/{tool_name}_result.json
    Also updates .dataworks/session_state.json with a summary under "tool_results".

    Args:
        tool_name: Tool identifier (e.g., "trace", "find_node")
        result_dict: Structured result data
        work_dir: Working directory (default: cwd)
    """
    runtime_dir = get_runtime_dir(work_dir)
    result_path = os.path.join(runtime_dir, f"{tool_name}_result.json")

    result_dict["_tool"] = tool_name
    result_dict["_timestamp"] = datetime.now().isoformat()

    _atomic_write_json(result_path, result_dict)

    # Update session state
    state_path = os.path.join(runtime_dir, _SESSION_STATE_FILE)
    state = _read_session_state(work_dir)

    state.setdefault("tool_results", {})[tool_name] = {
        "file": f".dataworks/{tool_name}_result.json",
        "timestamp": result_dict["_timestamp"],
        "summary": result_dict.get("summary", ""),
    }

    _atomic_write_json(state_path, state)


def load_backlogs(work_dir=None):
    """读取待办列表，文件不存在则返回空列表"""
    path = os.path.join(get_runtime_dir(work_dir), _BACKLOGS_FILE)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_backlogs(backlogs, work_dir=None):
    """保存待办列表，空列表时删除文件"""
    path = os.path.join(get_runtime_dir(work_dir), _BACKLOGS_FILE)
    if not backlogs:
        if os.path.exists(path):
            os.remove(path)
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(backlogs, f, ensure_ascii=False, indent=2)


def add_backlog(type_name, label, check, context=None, on_success=None, on_fail=None, work_dir=None):
    """追加一条待办记录

    Args:
        type_name: 操作类型，如 "backfill", "deploy", "write_api"
        label: 一行摘要，供 agent 和用户阅读
        check: 自包含的查询配方 {api, params, status_field, terminal, pending}
        context: 可选的附加元数据
        on_success: 成功后输出的下一步指引
        on_fail: 失败后输出的下一步指引
    Returns:
        创建的 entry dict
    """
    backlogs = load_backlogs(work_dir)
    entry = {
        "id": f"{type_name}_{int(datetime.now().timestamp())}",
        "type": type_name,
        "label": label,
        "created_at": datetime.now().isoformat(),
        "check": check,
    }
    if context:
        entry["context"] = context
    if on_success:
        entry["on_success"] = on_success
    if on_fail:
        entry["on_fail"] = on_fail
    backlogs.append(entry)
    save_backlogs(backlogs, work_dir)
    return entry


# ─── confirmed_params: Agent 注意力辅助层 ───────────────────────
#
# 多步骤工作流（如 DI 5 步）中，跨步骤累积已确认的标量参数，
# 让 agent 在每次脚本调用时看到累积上下文，避免因 LLM context
# 滑动而忘记早期参数。
#
# 命名契约：所有业务参数 key 必须遵守 "CLI flag 去掉 '--' 转下划线"
# 例如 --src-type → src_type, --project-id → project_id
#
# 与续接载体（pending 文件）正交：删除 confirmed_params 不影响任何
# 现有流程功能。它只是 stdout 显示用的 agent 辅助层。
#
# 详见：create_bff_skill/docs/design/workflow-context.md

_CONFIRMED_PARAMS_KEY = "confirmed_params"
_SESSION_ID_META_KEY = "_session_id"


def _read_session_state(work_dir=None):
    """读取 session_state.json，文件不存在或损坏返回 {}"""
    state_path = os.path.join(get_runtime_dir(work_dir), _SESSION_STATE_FILE)
    if not os.path.exists(state_path):
        return {}
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_session_state(state, work_dir=None):
    """写入 session_state.json，使用保留未知字段语义"""
    state_path = os.path.join(get_runtime_dir(work_dir), _SESSION_STATE_FILE)
    # 先读旧 state 合并，避免覆盖其他写入方的字段
    old = _read_session_state(work_dir)
    old.update(state)
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(old, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        print(f"⚠️ session_state 写入失败: {e}", file=sys.stderr)


def remember(work_dir=None, **kwargs):
    """合并参数到 confirmed_params。

    内部行为：
      1. 调 get_session_id() 获取当前 sid
      2. 读 session_state.confirmed_params（不存在则创建）
      3. 检查 _session_id：与当前 sid 不一致 → 先清空业务 keys
      4. 把 kwargs merge 进 confirmed_params
      5. 更新 _session_id
      6. 写回 session_state（保留其他未知顶层字段）

    幂等：重复调用同样参数无副作用。

    Args:
        work_dir: 工作目录（默认 cwd）
        **kwargs: 要记忆的参数。key 必须遵守命名契约（CLI flag 转下划线）

    Returns:
        合并后的 confirmed_params dict（含 _session_id 元字段）
    """
    if not kwargs:
        return get_confirmed_params(work_dir=work_dir, include_meta=True)

    sid = get_session_id()
    state = _read_session_state(work_dir)
    cp = state.get(_CONFIRMED_PARAMS_KEY, {})
    if not isinstance(cp, dict):
        cp = {}

    # session 切换检测：清空业务 keys，保留 _session_id
    if cp.get(_SESSION_ID_META_KEY) and cp.get(_SESSION_ID_META_KEY) != sid:
        cp = {}

    cp[_SESSION_ID_META_KEY] = sid
    cp.update(kwargs)

    state[_CONFIRMED_PARAMS_KEY] = cp
    _write_session_state(state, work_dir)
    return cp


def forget(*keys, work_dir=None):
    """删除指定 keys（不传参数则全清，但保留 _session_id）

    Args:
        *keys: 要删除的参数名。无参数表示全清业务 keys
        work_dir: 工作目录

    Returns:
        清理后的 confirmed_params dict
    """
    state = _read_session_state(work_dir)
    cp = state.get(_CONFIRMED_PARAMS_KEY, {})
    if not isinstance(cp, dict):
        return {}

    if not keys:
        # 全清：只保留 _session_id
        sid = cp.get(_SESSION_ID_META_KEY)
        cp = {_SESSION_ID_META_KEY: sid} if sid else {}
    else:
        for k in keys:
            cp.pop(k, None)

    state[_CONFIRMED_PARAMS_KEY] = cp
    _write_session_state(state, work_dir)
    return cp


def get_confirmed_params(work_dir=None, include_meta=False):
    """读取当前 confirmed_params。

    自动处理 session_id 过期：若 _session_id 与当前 sid 不一致，
    返回 {} 并不更新文件（下次 remember 会自然清理）。

    Args:
        work_dir: 工作目录
        include_meta: True 时包含 _session_id 元字段，默认 False

    Returns:
        dict（业务参数，可能为空）
    """
    state = _read_session_state(work_dir)
    cp = state.get(_CONFIRMED_PARAMS_KEY, {})
    if not isinstance(cp, dict):
        return {}

    # session 过期检测
    stored_sid = cp.get(_SESSION_ID_META_KEY)
    current_sid = get_session_id()
    if stored_sid and stored_sid != current_sid:
        return {}

    if include_meta:
        return dict(cp)
    return {k: v for k, v in cp.items() if not k.startswith("_")}


def print_confirmed_params(prefix="📌 已确认参数", work_dir=None):
    """打印当前 confirmed_params 到 stdout。无参数时静默不输出。

    输出格式:
        📌 已确认参数
          project_id: 22153
          src_datasource: my_mysql
          src_table: t_parameter
    """
    params = get_confirmed_params(work_dir=work_dir)
    if not params:
        return
    print(prefix)
    for k, v in params.items():
        print(f"  {k}: {v}")


def resolve_project_id(client, project_id, project_name, tag="", quiet_on_missing=False):
    """从 project_id / project_name / session / .env 四级回退获取 projectId

    所有脚本共用此逻辑，避免各自复制。
    Args:
        client: BFFClient 实例（用于 ListProjects 调用）
        project_id: 显式指定的 projectId（优先）
        project_name: 工作空间名称（次优先）
        tag: 日志前缀，如 "[ops]"
        quiet_on_missing: True 时缺失 projectId 的 fallback 阶段不打印 workspace 列表，
                          直接 sys.exit(1)。调用方自己决定是否继续（catch SystemExit）。
    Returns:
        int: projectId
    Raises:
        SystemExit: 无法获取时退出
    """
    prefix = f"{tag} " if tag else ""
    # 首次调用时从启动环境变量吸收 context（幂等，已 bootstrap 过会跳过）
    bootstrap_context()
    if project_id:
        print(f"{prefix}工作空间: {project_id}")
        return int(project_id)
    if project_name:
        projects = client.load("ListProjects", pageSize=100)
        for p in projects:
            if p.get("projectName") == project_name or p.get("displayName") == project_name:
                pid = p.get("projectId")
                print(f"{prefix}工作空间: {project_name} → projectId={pid}")
                return pid
        names = [p.get("projectName", "") for p in projects[:20]]
        print(f"{prefix}未找到工作空间: {project_name}")
        print(f"{prefix}可用工作空间: {', '.join(names)}")
        sys.exit(1)
    # fallback: session（由启动器或 identify.py 注入，见 docs/design/startup-context-spec.md）
    path = os.path.join(os.path.expanduser("~"), _RUNTIME_DIR, _SESSION_STATE_FILE)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            pid = state.get("context", {}).get("projectId")
            if pid:
                print(f"{prefix}工作空间: {pid} (来自 session)")
                return int(pid)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    # quiet_on_missing: 调用方要自己处理缺失场景，直接 exit
    if quiet_on_missing:
        sys.exit(1)
    # fallback: 走"探索-执行分离" — 给出明确单一路径，不让 agent 自由选择
    script_hint = tag.strip("[] ") or "当前脚本"
    try:
        projects = client.load("ListProjects", pageSize=50)
    except Exception:
        projects = []
    active = [p for p in projects if p.get("status") == "Available"] or projects
    # 首选：已有 session 但没 projectId → 先跑 identify
    session_path = os.path.join(os.path.expanduser("~"), _RUNTIME_DIR, _SESSION_STATE_FILE)
    has_session = os.path.exists(session_path)
    if has_session:
        print(f"{prefix}session 存在但未锁定工作空间。下一步执行：")
        print(f"  python modules/discovery/scripts/identify.py --help  # 建立 session")
        print(f"或直接重试当前命令并加 --project <name-or-id>")
    else:
        print(f"{prefix}缺少工作空间。下一步执行（任选其一）：")
    if active:
        # 只列前 5 个，避免选择过载；总数 >5 时提示 identify 浏览
        for p in active[:5]:
            pid_val = p.get("projectId", "")
            name = p.get("projectName", "")
            print(f"  {script_hint}.py --project {name}   # 或 --project {pid_val}")
        if len(active) > 5:
            print(f"  （共 {len(active)} 个可用工作空间，完整列表: identify.py --list-workspaces）")
    else:
        print(f"  {script_hint}.py --project <name-or-id>")
    sys.exit(1)


def list_workspaces_for_selection(script_name):
    """缺少 project-id 时的通用探索函数。

    列出所有可用工作空间，输出下一步命令供 agent 直接执行。
    遵循"探索-执行分离"：探索阶段输出完整的执行命令，agent 不需要自己拼参数。

    Args:
        script_name: 调用方脚本名（用于生成示例命令）
    """
    # 延迟导入避免循环依赖
    from bff_client import BFFClient
    client = BFFClient(quiet=True, analyzer=False)
    projects = client.load("ListProjects", pageSize=100)
    if not projects:
        print("未找到工作空间，请指定 --project-id")
        return

    active = [p for p in projects if p.get("status") == "Available"]

    print(f"\n未指定工作空间，当前有 {len(active)} 个可用工作空间:")
    print(f"{'─' * 60}")
    for p in active:
        pid = p.get("projectId", "?")
        name = p.get("projectName", "?")
        display = p.get("displayName", "")
        label = f"{display} ({name})" if display and display != name else name
        print(f"  --project-id {pid}  {label}")

    print(f"\n请指定工作空间后重试，示例:")
    print(f"  {script_name} --project-id {active[0].get('projectId', '?')}")
    if len(active) > 1:
        print(f"  {script_name} --project-name {active[0].get('projectName', '?')}")


def project_id_to_project_name(client, project_id):
    """DataWorks workspace ID → projectName（约定 projectName = 底层数据库基名）

    Args:
        client: BFFClient 实例
        project_id: DataWorks workspace ID

    Returns:
        str: projectName（如 "dataworks_analyze"），未找到返回 None
    """
    if not project_id:
        return None
    try:
        projects = client.load("ListProjects", pageSize=100) or []
        for p in projects:
            if p.get("projectId") == int(project_id):
                return p.get("projectName") or p.get("displayName")
    except Exception:
        pass
    return None


def resolve_table_with_workspace(client, keyword, project=None, project_id=None,
                                 tag="[resolve]"):
    """表名解析 + workspace 级同名消歧（上层启发式，不污染 find_table）

    解析顺序：
      1. 显式 --project（databaseName）优先，直接调 find_table 返回
      2. 无 project 时，先纯元数据搜索
      3. 多同名表冲突 + 有 project_id → 映射 workspace 的 projectName，优先 prod 数据库
      4. prod 没命中回退 dev（projectName + "_dev"）
      5. 都不行则抛出原 ValueError，让调用方透传给 agent

    Args:
        keyword: 表名
        project: databaseName（显式优先）
        project_id: DataWorks workspace ID（用于 prod/dev 启发式）
        tag: 日志前缀

    Returns:
        dict: find_table 的完整返回

    Raises:
        ValueError: 找不到或无法消歧（带清晰的 --project 提示）
    """
    # 延迟导入避免 discovery/scripts 不在 path 时 runtime 加载失败
    import sys, os
    script_dir = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "modules", "discovery", "scripts"))
    if os.path.isdir(script_dir) and script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    # dist 场景：core 和 modules 都在同一个 skill 根下
    dist_script_dir = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "modules", "discovery", "scripts"))
    if dist_script_dir not in sys.path:
        sys.path.insert(0, dist_script_dir)
    from search_table import find_table

    # 1. 显式 --project 直接用
    if project:
        return find_table(client, keyword, project=project)

    # 2. 纯搜，命中单表即返回
    try:
        return find_table(client, keyword)
    except ValueError as e:
        msg = str(e)
        # 非"多同名"错误（如"未找到表"）直接透传
        if "多个同名" not in msg and "多同名" not in msg and "同名表" not in msg:
            raise
        # 无 project_id 可用，原样抛出让 agent 按提示选 --project
        if not project_id:
            raise

    # 3. 用 project_id 映射 prod 数据库名，优先 prod
    pname = project_id_to_project_name(client, project_id)
    if not pname:
        # workspace 解析失败，无法自动消歧，原样报错
        return find_table(client, keyword)  # 再抛一次让错误信息返回

    # 3a. 先试 prod
    try:
        table = find_table(client, keyword, project=pname)
        print(f"{tag} 同名表多张，自动选 workspace {project_id} 的 prod 数据库 '{pname}'。"
              f"要 dev 请加 --project {pname}_dev")
        return table
    except ValueError:
        pass

    # 3b. 再试 dev
    dev_name = f"{pname}_dev"
    try:
        table = find_table(client, keyword, project=dev_name)
        print(f"{tag} prod 数据库 '{pname}' 未命中，已自动回退 dev 数据库 '{dev_name}'")
        return table
    except ValueError:
        pass

    # 都没命中，重新触发原错误（多表列表）给 agent
    return find_table(client, keyword)
