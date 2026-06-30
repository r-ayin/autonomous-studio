#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DataWorks BFF API 客户端

使用方式:
    from bff_client import BFFClient

    client = BFFClient()

    # 取数：load() 自动翻页 + 灌入 DuckDB
    client.load("searchTables", keyword="表名", entityType="maxcompute-table")
    # stdout: [searchTables_r1_c1] N 条 | qualifiedName, name, databaseName, ...

    # 脚本内查询 DuckDB（返回 list[dict]，用于链式调用）
    rows = client.query("SELECT qualifiedName, name FROM searchTables_r1_c1 WHERE name = 'xxx'")

    # 交互式分析（输出到 stdout）
    # python duckdb_query.py "SELECT name FROM searchTables_r1_c1"

    # 写操作（必须在用户确认后调用）：
    client.write("rerun_task_instances", env="prod", projectId=23304, taskIds=[123])

    # 便捷方法：
    base_id = client.get_my_base_id()
"""

try:
    import requests
except ImportError:
    raise ImportError("缺少 requests 库，请先安装: pip install requests")
# 抑制 urllib3 v2 在 macOS LibreSSL 环境下的 NotOpenSSLWarning
import urllib3
urllib3.disable_warnings(urllib3.exceptions.NotOpenSSLWarning)
import json
import os
import platform
import sys
import threading
import time
from datetime import datetime

from runtime import (
    _read_skill_version, _load_env_file, WriteOperationError,
    _RUNTIME_DIR, _SESSION_STATE_FILE, _PENDING_WRITE_FILE,
    get_runtime_dir, save_tool_result, load_backlogs, save_backlogs, add_backlog,
    resolve_project_id, list_workspaces_for_selection,
    project_id_to_project_name, resolve_table_with_workspace,
    get_session_id, bootstrap_context,
)
from pagination import PaginationMixin
from output import OutputMixin
from audit_log import record as _audit_write

__version__ = _read_skill_version()

# 再导出：保持 from bff_client import xxx 的兼容性
__all__ = [
    "BFFClient", "WriteOperationError",
    "save_tool_result", "load_backlogs", "save_backlogs", "add_backlog",
    "resolve_project_id", "list_workspaces_for_selection",
    "project_id_to_project_name", "resolve_table_with_workspace",
    "get_client", "load_api", "read_api",
]


class BFFClient(PaginationMixin, OutputMixin):
    """DataWorks BFF API 客户端（仅依赖 requests，无需 python-dotenv）"""

    def __init__(self, skill_dir=None, analyzer=True, quiet=False):
        """
        初始化客户端

        Args:
            skill_dir: skill 目录路径，用于读取 api-index.json
            analyzer: False 完全关闭 DuckDB（不加载、不分析）。
            quiet: True 时仍写 DuckDB + session_state，但不输出 auto_summary 到 stdout。
                   适合工具脚本：数据共享但不产生噪音。
        """
        # 加载 profile（build 时生成的环境身份）
        self._profile = self._load_profile(skill_dir)
        auth_cfg = self._profile["auth"]
        err_msgs = self._profile.get("error_messages", {})

        # 加载 .env 文件（不覆盖已有环境变量）
        # 优先级：shell env > cwd/.dataworks/.env > ~/.dataworks/.env
        # cwd 优先支持多项目/多租户并行开发，每个工作目录用独立 token。
        # `HOME=$(pwd) qwen` 场景下两路径会指向同一处，不受影响。
        _env_paths = []
        cwd_env = os.path.join(os.getcwd(), ".dataworks", ".env")
        home_env = os.path.expanduser("~/.dataworks/.env")
        if cwd_env != home_env:
            _env_paths.append(cwd_env)
        _env_paths.append(home_env)
        for _p in _env_paths:
            for key, value in _load_env_file(_p).items():
                if key not in os.environ:
                    os.environ[key] = value

        # Token：根据 profile 决定是否必填
        self.token = os.getenv("BFF_TOKEN")
        if not self.token and auth_cfg["token_required"]:
            msg = err_msgs.get("no_token")
            if msg:
                print(msg, file=sys.stderr)

        # 加载 endpoint 字典（用于 BFF_ENV 解析）
        self._endpoints_dict = self._load_endpoints_dict(skill_dir)

        # Endpoint：根据 profile 的 endpoint_source 决定获取方式
        self.endpoint = self._resolve_endpoint(auth_cfg)
        self._endpoint_source = "profile"

        if not self.endpoint:
            msg = err_msgs.get("no_endpoint")
            if msg:
                print(msg, file=sys.stderr)

        # Headers：直接从 profile 读取
        self._extra_headers = auth_cfg.get("headers", {})

        # session code：与 skill 本地 session 串联同一个 ID；
        # runtime.get_session_id() 保证：环境变量 DW_BFF_SESSION_CODE 优先，
        # 否则从 .dataworks/current_session 恢复（30min 内），否则生成 12 字符 uuid
        self.session_code = get_session_id()

        # 运行时文件统一放到 ~/.dataworks/
        self._work_dir = os.path.expanduser("~")

        # 环境信息 User-Agent
        self._user_agent = self._build_user_agent()

        # 日志配置
        self.log_dir = os.path.join(self._work_dir, ".dataworks", "logs")
        self.log_file = os.path.join(self.log_dir, "dw_bff_calls.log")

        # 加载 API 元数据（同时发现 skill 目录）
        self.api_index, self._skill_scripts_dir = self._load_api_index(skill_dir)

        # DuckDB 数据分析：自动将读 API 返回数据灌入 DuckDB + 自动统计
        self._loader_lock = threading.Lock()
        self.loader = None
        self._analyzer = None
        self._analyzer_enabled = analyzer
        self._quiet = quiet
        self.last_table = None  # 最近一次 load() 写入的 DuckDB 快照表名
        self._context = {}  # 会话上下文：user, projectId 等
        if analyzer:
            try:
                from duckdb_loader import DuckDBLoader
                from data_analyzer import DataAnalyzer
            except ImportError:
                # Fallback: try skill's scripts/ dir, then current script's dir
                for _try_dir in filter(None, [self._skill_scripts_dir,
                                              os.path.dirname(os.path.abspath(__file__))]):
                    if _try_dir not in sys.path:
                        sys.path.insert(0, _try_dir)
                try:
                    from duckdb_loader import DuckDBLoader
                    from data_analyzer import DataAnalyzer
                except ImportError:
                    DuckDBLoader = None
                    DataAnalyzer = None
            if DuckDBLoader and DataAnalyzer:
                try:
                    self.loader = DuckDBLoader()
                    self._analyzer = DataAnalyzer(self.loader, skill_scripts_dir=self._skill_scripts_dir)
                except Exception as e:
                    print(f"⚠️ DuckDB/Analyzer 初始化失败: {e}", file=sys.stderr)
                    self._analyzer_enabled = False
            else:
                self._analyzer_enabled = False

    # ── Profile & Endpoint ──

    def _load_profile(self, skill_dir=None):
        """加载 profile.json（build 产物，只读）

        查找优先级：
        1. skill_dir/profile.json（调用方显式指定）
        2. profile_loader.py（从 core/ 目录推导）
        3. bff_client.py 自身相对路径

        迁移兼容：若 profile.json 不存在（未升级的旧 dist），返回 public 默认值
        并输出警告。此兼容逻辑仅限迁移期使用，待所有 dist 升级完成后删除。
        """
        # 优先使用调用方指定的 skill_dir
        if skill_dir:
            path = os.path.join(skill_dir, "profile.json")
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)

        try:
            from profile_loader import load_profile
            return load_profile()
        except (FileNotFoundError, ImportError):
            try:
                core_dir = os.path.dirname(os.path.abspath(__file__))
                inferred_skill_dir = os.path.dirname(core_dir)
                path = os.path.join(inferred_skill_dir, "profile.json")
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except FileNotFoundError:
                pass
        # ⚠️ 迁移期兼容：旧 dist 无 profile.json，按 public 行为运行
        # TODO(deferred): 待人工裁决删除条件——所有部署环境的 dist 均已含 profile.json 时移除此兼容分支；
        #       可用 `find <dist-root> -name profile.json` 确认全覆盖后，连同下方 warnings.warn/print 兼容块一并删除
        import warnings
        warnings.warn(
            "profile.json 未找到，使用 public 默认配置。请运行 build 重新生成 dist。"
            "此兼容逻辑将在后续版本移除。",
            DeprecationWarning, stacklevel=2,
        )
        print("⚠️ [DEPRECATED] profile.json 未找到，使用 public 默认配置（请重新构建 dist）",
              file=sys.stderr)
        return {
            "env": "public",
            "auth": {
                "token_required": True,
                "endpoint_source": "endpoints_json",
                "headers": {},
            },
            "features": {},
            "error_messages": {
                "no_token": "⚠️ BFF_TOKEN 未设置！\n\n请按以下步骤配置：\n  1. 访问 https://dw.alibaba-inc.com/dmc/skill-auth 获取个人 Token\n  2. 将 Token 写入配置文件：\n\n     mkdir -p ~/.dataworks\n     cat > ~/.dataworks/.env << 'EOF'\n     BFF_TOKEN=<粘贴你的 token>\n     BFF_ENDPOINT=http://bff.dw.alibaba-inc.com\n     EOF\n\n  配置完成后重新运行即可。",
                "no_endpoint": "⚠️ BFF_ENDPOINT 未设置！请在 ~/.dataworks/.env 中配置：\n  方式1：BFF_ENDPOINT=https://your-endpoint.com\n  方式2：BFF_ENV=cn-beijing（从字典选择）",
            },
        }

    def _resolve_endpoint(self, auth_cfg):
        """根据 profile 的 endpoint_source 获取 endpoint。

        优先级（高→低）：
          1. BFF_ENDPOINT 环境变量 / ~/.dataworks/.env 中的显式值 —— 用户意图最高
             （网络环境复杂，endpoints.json 地址可能失效；profile 硬编码也应允许被 env var 覆盖，
             例如 alibaba profile 下测预发 `pre-bff.dw.alibaba-inc.com`。）
          2. profile.auth.endpoint —— 环境硬编码（如 alibaba）
          3. BFF_ENV → endpoints.json 字典查找
        """
        # 1. BFF_ENDPOINT 最高优先级（env var 或 .env 文件）
        ep = os.getenv("BFF_ENDPOINT")
        if ep:
            return ep

        # 2. profile 硬编码 endpoint
        if auth_cfg.get("endpoint"):
            return auth_cfg["endpoint"]

        # 3. endpoints.json 字典查找
        if auth_cfg["endpoint_source"] == "endpoints_json":
            bff_env = os.getenv("BFF_ENV")
            if bff_env:
                ep = self._resolve_endpoint_from_env(bff_env)
                if ep:
                    print(f"ℹ️ BFF_ENV={bff_env} → endpoint={ep}", file=sys.stderr)
                return ep

        return None

    def _load_endpoints_dict(self, skill_dir):
        """加载 endpoint 字典（endpoints.json）"""
        possible_paths = []

        if skill_dir:
            possible_paths.append(os.path.join(skill_dir, "core", "references", "endpoints.json"))

        script_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths.append(os.path.join(script_dir, "references", "endpoints.json"))

        home = os.path.expanduser("~")
        for skills_root in [
            os.path.join(home, ".qwen", "skills"),
            os.path.join(home, ".claude", "skills"),
        ]:
            possible_paths.append(os.path.join(skills_root, "dataworks", "core", "references", "endpoints.json"))

        for path in possible_paths:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)

        return {"environments": {}, "aliases": {}}

    def _resolve_endpoint_from_env(self, bff_env):
        """从 BFF_ENV 解析 endpoint URL

        支持两种格式：
        - region ID：cn-beijing, ap-southeast-1 等
        - 中文别名：北京, 新加坡 等
        """
        envs = self._endpoints_dict.get("environments", {})
        aliases = self._endpoints_dict.get("aliases", {})

        # 直接匹配 region ID
        if bff_env in envs:
            return envs[bff_env]

        # 匹配中文别名
        if bff_env in aliases:
            region_id = aliases[bff_env]
            if region_id in envs:
                return envs[region_id]

        return None

    # ── API Index ──

    def _load_api_index(self, skill_dir):
        """加载 API 元数据索引，同时发现 skill 的 scripts/ 目录"""
        # 尝试多个路径查找 api-index.json（只用相对路径，不依赖硬编码绝对路径）
        possible_paths = []

        if skill_dir:
            possible_paths.append(os.path.join(skill_dir, "core", "references", "api-index.json"))

        # 相对于脚本自身位置（bff_client.py 在 core/ 目录，references/ 在 core/references/）
        script_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths.append(os.path.join(script_dir, "references", "api-index.json"))

        # 当前工作目录（脚本被 cp 到工作目录时，api-index.json 也应一起复制）
        possible_paths.extend([
            os.path.join(os.getcwd(), "api-index.json"),
            os.path.join(os.getcwd(), "references", "api-index.json"),
        ])

        # 常见 skill 安装位置（用于推导 scripts/ 目录，即使 api-index.json 已从工作目录加载）
        home = os.path.expanduser("~")
        for skills_root in [
            os.path.join(home, ".qwen", "skills"),
            os.path.join(home, ".claude", "skills"),
        ]:
            possible_paths.append(os.path.join(skills_root, "dataworks", "core", "references", "api-index.json"))

        api_index = None
        skill_scripts_dir = None
        for path in possible_paths:
            if not os.path.exists(path):
                continue
            if api_index is None:
                with open(path, "r", encoding="utf-8") as f:
                    api_index = json.load(f).get("api_index", {})
            # 从 core/references/ 下的 api-index.json 推导 skill 的 core/ 目录
            if skill_scripts_dir is None:
                real_path = os.path.realpath(path)
                parent_dir = os.path.dirname(real_path)
                if os.path.basename(parent_dir) == "references":
                    core_dir = os.path.dirname(parent_dir)
                    if os.path.basename(core_dir) == "core" and os.path.isdir(core_dir):
                        skill_scripts_dir = core_dir
            if api_index is not None and skill_scripts_dir is not None:
                break

        if api_index is None:
            raise FileNotFoundError(
                "找不到 api-index.json。请确保 skill 目录结构完整（core/references/api-index.json）"
            )
        return api_index, skill_scripts_dir

    # ── HTTP ──

    def _build_user_agent(self):
        """构建 User-Agent：skill版本 + 运行环境 + AI agent + LLM"""
        parts = [
            f"dataworks/{__version__}",
            f"Python/{platform.python_version()}",
            f"{platform.system()}/{platform.release()}",
        ]

        # AI agent：从 skill 安装路径自动推断，env var 可覆盖
        agent = os.getenv("DW_AGENT")
        if not agent:
            script_path = os.path.realpath(os.path.abspath(__file__))
            if "/.claude/" in script_path:
                agent = "claude-code"
            elif "/.qwen/" in script_path:
                agent = "qwen-code"
        if agent:
            parts.append(f"Agent/{agent}")

        # LLM 模型：从环境变量读取
        llm = os.getenv("DW_LLM")
        if llm:
            parts.append(f"LLM/{llm}")

        return " ".join(parts)

    def _log(self, path, method, params, data, json_body, response, cost_ms):
        """记录 API 调用日志

        文件写入包 try/except（与 _log_warn 一致）：_do_request 是 HTTP chokepoint，
        调试日志的磁盘/权限异常不应阻断真实 API 调用（case-420 审计修复 F3）。
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "cost_ms": round(cost_ms, 2),
            "request": {
                "path": path,
                "method": method,
                "params": params,
                "data": data,
                "json_body": json_body
            },
            "response": {
                "code": response.get("code"),
                "data": response.get("data"),
                "message": response.get("message"),
                "requestId": response.get("requestId")
            }
        }
        try:
            os.makedirs(self.log_dir, exist_ok=True)
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _log_warn(self, message):
        """Write a warning to the log file (not stdout/stderr)."""
        os.makedirs(self.log_dir, exist_ok=True)
        entry = {"timestamp": datetime.now().isoformat(), "level": "WARN", "message": message}
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _build_headers(self, content_type=None, write_confirmed=None):
        """构建请求头（根据 profile 决定认证方式）"""
        headers = {
            "Accept": "application/json",
            "Referer": f"http://{self.session_code}.qwen.cli",
            "User-Agent": self._user_agent,
        }
        # 只在有 token 时发送 Authorization 头
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if content_type:
            headers["Content-Type"] = content_type
        if write_confirmed:
            headers["X-User-Confirmed"] = write_confirmed
        # 合并 profile 中的附加请求头（如集团环境的 X-Auth-Type）
        if self._extra_headers:
            headers.update(self._extra_headers)
        return headers

    def _parse_return_structure(self, result, return_structure):
        """根据 return_structure 元数据自动提取数据"""
        if not return_structure:
            return result.get("data")

        # data=xxx 格式：直接返回 data 字段
        if "=" in return_structure:
            return result.get("data")

        # 去掉末尾的 [] 和 {} 标记（仅作类型提示，不影响取值路径）
        # 但要记住 [] 后面是否还有子字段（如 data.list[].entity）
        map_field = None
        structure = return_structure
        if "[]." in structure:
            # data.list[].entity → 先取到 data.list，再 map 取 entity
            parts = structure.split("[].")
            structure = parts[0] + "[]"
            map_field = parts[1]

        structure = structure.rstrip("[]{}}")

        # 按 . 拆分路径，逐层取值
        current = result
        for key in structure.split("."):
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None

        # 如果有 map 字段，对列表中每个元素提取该字段
        if map_field and isinstance(current, list):
            current = [item.get(map_field) if isinstance(item, dict) else item for item in current]

        return current

    def _do_request(self, api_name, api_meta, write_confirmed=None,
                    correlation_id=None, attempt=0, **kwargs):
        """执行 HTTP 请求并返回原始响应 dict（内部方法）

        correlation_id/attempt 透传到审计埋点：_call 的限频重试循环共享同一
        correlation_id、递增 attempt，使一次逻辑写重试 N 次产 N 条可关联的审计记录
        而非 N 条孤条（case-348 F2）。call_raw 单次直调也由调用方传入独有 correlation_id。
        """
        path = api_meta["path"]
        method = api_meta.get("method", "GET")
        params_type = api_meta.get("params_type")

        url = f"{self.endpoint}{path}"

        # 根据参数类型构建请求
        params = None
        data = None
        json_body = None
        content_type = None

        if params_type is None:
            # 无参数 GET 请求
            pass
        elif params_type in ("params", "query"):
            params = {k: str(v) if not isinstance(v, str) else v for k, v in kwargs.items()}
        elif params_type == "data":
            data = {k: str(v) if not isinstance(v, str) else v for k, v in kwargs.items()}
            content_type = "application/x-www-form-urlencoded"
        elif params_type in ("json_body", "json"):
            json_body = kwargs

        headers = self._build_headers(content_type, write_confirmed=write_confirmed)

        # 发送请求
        start_time = time.time()
        try:
            m = method.upper()
            if m == "GET":
                resp = requests.get(url, params=params, headers=headers, timeout=30)
            elif m == "PUT":
                if json_body:
                    resp = requests.put(url, json=json_body, headers=headers, timeout=30)
                elif data:
                    resp = requests.put(url, data=data, headers=headers, timeout=30)
                else:
                    resp = requests.put(url, headers=headers, timeout=30)
            else:  # POST
                if json_body:
                    resp = requests.post(url, json=json_body, headers=headers, timeout=30)
                elif data:
                    resp = requests.post(url, data=data, headers=headers, timeout=30)
                else:
                    resp = requests.post(url, headers=headers, timeout=30)
            result = resp.json()
        except requests.exceptions.RequestException as e:
            result = {"code": -1, "message": f"网络请求失败: {e}", "data": None, "requestId": None}
        except ValueError as e:
            # JSON 解析失败
            result = {"code": -1, "message": f"响应解析失败: {e}（HTTP {resp.status_code}）", "data": None, "requestId": None}

        cost_ms = (time.time() - start_time) * 1000
        self._log(path, method, params, data, json_body, result, cost_ms)

        # 审计埋点（DO B）：写操作执行即落审计。_do_request 是唯一 HTTP chokepoint，
        # 经 confirm_write()（write_confirmed 非空 = sanctioned 两阶段确认）或 call_raw()
        # （write_confirmed 为空 = 绕过确认门禁）都在此统一记录，使绕过不再 silent。
        if api_meta.get("is_write_operation"):
            _audit_write(
                self._work_dir,
                api_name=api_name,
                params_summary=",".join(kwargs.keys()),
                result_code=result.get("code") if isinstance(result, dict) else None,
                user_id=getattr(self, "_cached_base_id", None) or os.getenv("DW_USER_BASE_ID") or "unknown",
                bypass=write_confirmed is None,
                correlation_id=correlation_id,
                attempt=attempt,
            )

        return result

    # ── Public API ──

    def load(self, api_name, **kwargs):
        """取数 + 灌入 DuckDB：自动翻页 + 入库 + auto_summary"""
        api_meta = self.api_index.get(api_name)
        if not api_meta:
            raise ValueError(f"未找到 API: {api_name}。可用 API: {list(self.api_index.keys())}")
        if api_meta.get("is_write_operation"):
            raise TypeError(
                f"⚠️ {api_name} 是写操作，请用 client.write(\"{api_name}\", ...)"
                f"\n写操作必须在用户确认后才能调用。"
            )
        return self._call(api_name, **kwargs)

    # 向后兼容别名
    read = load

    def write(self, api_name, _caller_confirmed=False, **kwargs):
        """写操作 Phase 1：准备并输出确认摘要，不执行。"""
        api_meta = self.api_index.get(api_name)
        if not api_meta:
            raise ValueError(f"未找到 API: {api_name}。可用 API: {list(self.api_index.keys())}")
        if not api_meta.get("is_write_operation"):
            raise TypeError(
                f"{api_name} 是读操作，请用 client.load(\"{api_name}\", ...)"
            )

        # 保存 pending 写操作到文件
        pending = {
            "api_name": api_name,
            "params": kwargs,
            "created_at": datetime.now().isoformat(),
            "caller_confirmed": _caller_confirmed,
        }
        pending_path = os.path.join(get_runtime_dir(self._work_dir), _PENDING_WRITE_FILE)
        with open(pending_path, "w", encoding="utf-8") as f:
            json.dump(pending, f, ensure_ascii=False, indent=2)

        # 输出确认摘要到 stdout（agent 的信号通道）
        params_str = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
        print(f"⚠️ 待确认写操作: {api_name}")
        print(f"  参数: {params_str}")

        return {"api_name": api_name, "params": kwargs}

    def confirm_write(self):
        """写操作 Phase 2：执行待确认的写操作。"""
        pending_path = os.path.join(get_runtime_dir(self._work_dir), _PENDING_WRITE_FILE)
        if not os.path.exists(pending_path):
            raise WriteOperationError(
                "没有待确认的写操作。请先调用 client.write(...) 准备操作。"
            )

        with open(pending_path, "r", encoding="utf-8") as f:
            pending = json.load(f)

        # 时间间隔防护：write() 和 confirm_write() 之间必须有足够的用户确认时间
        if not pending.get("caller_confirmed"):
            created_at = pending.get("created_at")
            if created_at:
                elapsed = (datetime.now() - datetime.fromisoformat(created_at)).total_seconds()
                if elapsed < 10:
                    print(
                        f"⚠️ 操作被拦截：必须先让用户确认。\n"
                        f"现在立即停止，将上一步的操作摘要展示给用户，等用户明确回复「确认」后，再调用 confirm_write()。\n"
                        f"不要重试，不要等待，不要 sleep —— 先回复用户。"
                    )
                    sys.exit(1)

        # 清除 pending 文件（无论执行成功与否）
        os.remove(pending_path)

        api_name = pending["api_name"]
        params = pending["params"]

        print(f"✅ 执行写操作: {api_name}")
        result = self._call(api_name, confirmed=True, **params)

        # 异步操作引导：输出 follow-up 查询命令
        api_meta = self.api_index.get(api_name, {})
        follow_up = api_meta.get("follow_up")
        if follow_up:
            self._print_follow_up(follow_up, params, result)

        # 写后提示：输出 api-index.json 中定义的 post_write_hint
        post_hint = api_meta.get("post_write_hint")
        if post_hint:
            print(f"💡 {post_hint}")

        return result

    # ── Internal call dispatch ──

    def _call(self, api_name, confirmed=False, **kwargs):
        """内部方法：统一调用逻辑"""
        api_meta = self.api_index.get(api_name)
        if not api_meta:
            raise ValueError(f"未找到 API: {api_name}。可用 API: {list(self.api_index.keys())}")

        # 跟踪 projectId 上下文
        pid = kwargs.get("projectId") or kwargs.get("project_id")
        if pid:
            self._context["projectId"] = str(pid)

        is_write = api_meta.get("is_write_operation", False)

        # 写操作拦截
        if is_write and not confirmed:
            raise WriteOperationError(
                f"⚠️ {api_name} 是写操作，必须传 confirmed=True 才能执行！"
                f"\n用法: client.write(\"{api_name}\", ...)"
            )

        # 列表 API 自动全量翻页（固定行为，不受参数控制）
        return_structure = api_meta.get("return_structure", "")
        is_list_api = "[]" in return_structure

        if is_list_api and not is_write:
            # max_pages 是翻页控制参数，不是 API 参数，需要提取出来
            # 默认上限 3000 页 × 默认 100 条 = 30w 行；callers 可 pageSize=1000 + max_pages=300 达到同上限但更快
            caller_max_pages = kwargs.pop("max_pages", 3000)
            caller_max_offset = kwargs.pop("max_offset", None)
            result = self._call_all_pages(api_name, max_pages=caller_max_pages, max_offset=caller_max_offset, **kwargs)
            self._save_session_state()
            return result

        # 写操作确认签名：confirm_write() 路径下附带 X-User-Confirmed header
        write_confirmed = None
        if confirmed:
            import hashlib
            params_json = json.dumps(kwargs, sort_keys=True, ensure_ascii=False, default=str)
            params_hash = hashlib.sha256(params_json.encode()).hexdigest()[:16]
            write_confirmed = f"{api_name}:{params_hash}:{datetime.now().isoformat()}"

        # 非列表 API：单次调用（限频自动重试）
        import time as _time
        import uuid
        max_retries = 3
        # 一次逻辑写操作共享同一 correlation_id：限频重试产生的多条审计记录据此关联，
        # 审计者可区分「1 次逻辑写重试 N 次」与「N 次独立逻辑写」（case-348 F2）。
        correlation_id = str(uuid.uuid4())
        for attempt in range(max_retries + 1):
            result = self._do_request(
                api_name, api_meta, write_confirmed=write_confirmed,
                correlation_id=correlation_id, attempt=attempt, **kwargs,
            )
            if self.is_success(result):
                break
            err_msg = f"code={result.get('code')}, message={result.get('message')}"
            if self._is_rate_limit_error(err_msg) and attempt < max_retries:
                wait = 2 ** attempt
                print(f"[BFFClient] 限频，{wait}s 后重试（{attempt + 1}/{max_retries}）", file=sys.stderr)
                _time.sleep(wait)
                continue
            raise RuntimeError(
                f"API 调用失败: {api_name} → code={result.get('code')}, "
                f"message={result.get('message')}, requestId={result.get('requestId')}"
            )

        parsed = self._parse_return_structure(result, return_structure)

        # 防御性检测：非列表 API 返回了分页结构，说明 return_structure 可能配错
        if isinstance(parsed, dict) and "totalCount" in parsed and any(
                isinstance(v, list) for v in parsed.values()
        ):
            print(f"⚠️ {api_name} 返回了分页结构（totalCount={parsed.get('totalCount')}），"
                  f"但 return_structure='{return_structure}' 未标记为列表 API。"
                  f"\n请检查 api-index.json 中该 API 的 return_structure 是否应包含 '[]'",
                  file=sys.stderr)

        self._auto_load_to_analyzer(api_name, parsed, call_params=kwargs)

        # 写操作成功后：清除关联 API 的所有快照（Strategy B）
        if is_write and self.loader:
            invalidates = api_meta.get("invalidates", [])
            for api in invalidates:
                self.loader.drop_api_tables(api)

        self._save_session_state()

        return parsed

    def call_raw(self, api_name, **kwargs):
        """调用 API，返回原始响应 dict（仅供调试）"""
        api_meta = self.api_index.get(api_name)
        if not api_meta:
            raise ValueError(f"未找到 API: {api_name}。可用 API: {list(self.api_index.keys())}")
        import uuid
        # call_raw 单次直调无重试，生成独有 correlation_id、attempt=0，
        # 使其审计记录与 _call 重试路径同构可关联（case-348 F2）。
        return self._do_request(
            api_name, api_meta,
            correlation_id=str(uuid.uuid4()), attempt=0, **kwargs,
        )

    # ── Convenience methods ──

    def get_user_info(self):
        """获取当前用户完整信息"""
        return self.load("currentUser")

    def get_my_base_id(self):
        """快捷获取当前用户的 baseId。

        优先级：
        1. session_state.json 的 context.user.baseId（启动器 export DW_USER_BASE_ID 后由 bootstrap_context 吸收）
        2. currentUser API（结果缓存，不会重复请求）
        """
        if not hasattr(self, '_cached_base_id'):
            # 首次调用前触发 bootstrap（从 DW_USER_BASE_ID 等环境变量吸收到 session）
            bootstrap_context(work_dir=self._work_dir)
            # 优先从 session 读（启动器写入，免接口调用）
            session_path = os.path.join(self._work_dir, _RUNTIME_DIR, "session_state.json")
            if os.path.exists(session_path):
                try:
                    with open(session_path, "r", encoding="utf-8") as f:
                        state = json.load(f)
                    bid = state.get("context", {}).get("user", {}).get("baseId")
                    if bid:
                        self._cached_base_id = str(bid)
                        return self._cached_base_id
                except (json.JSONDecodeError, ValueError, TypeError, OSError):
                    pass
            # fallback: 接口调用
            user_info = self.load("currentUser")
            self._cached_base_id = user_info.get("baseId")
            if not self._cached_base_id:
                raise RuntimeError("currentUser 响应中缺少 baseId 字段")
        return self._cached_base_id

    def query(self, sql):
        """在脚本内查询 DuckDB，返回 list[dict]"""
        if not self.loader:
            raise RuntimeError("DuckDB 未初始化。请确保 duckdb 已安装: pip install duckdb")
        return self.loader.fetch(sql)

    def is_success(self, result):
        """检查原始响应是否成功（code 为 0 或 200）。配合 call_raw() 使用。"""
        return isinstance(result, dict) and result.get("code") in [0, 200]


# 便捷函数
_client = None

def get_client():
    """获取全局客户端实例"""
    global _client
    if _client is None:
        _client = BFFClient()
    return _client

def load_api(api_name, **kwargs):
    """便捷函数：取数"""
    return get_client().load(api_name, **kwargs)

# 向后兼容
read_api = load_api


if __name__ == "__main__":
    client = BFFClient()

    print("测试 load('currentUser'):")
    user_info = client.load("currentUser")
    print(f"  用户信息: {user_info}")

    print("\n测试 get_my_base_id:")
    base_id = client.get_my_base_id()
    print(f"  baseId: {base_id}")

    print("\n测试 load('searchTables'):")
    tables = client.load("searchTables", keyword="dwd_order", entityType="maxcompute-table")
    print(f"  找到 {len(tables)} 张表")
