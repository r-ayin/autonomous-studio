"""共享的钉钉 MCP 网关客户端。

被 dingtalk_doc / dingtalk_ai_table（以及后续 dingtalk_sheet）复用。

配置文件: <skill_dir>/config/servers.json
每个 server 带 type 字段（"doc" / "ai_table" / ...）。
setup() 时自动通过 tools/list 探测类型。
"""

import itertools
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests

# ============================================================
# 常量
# ============================================================

_SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = _SKILL_DIR / "config" / "servers.json"
MCP_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_INFO = {"name": "devix-dingtalk-skill", "version": "0.2.0"}

# 模块级 JSON-RPC request_id 生成器：每次 _mcp_call 拿一个唯一递增 id，
# 避免重试 / initialize+tools/call 多阶段调用共享同一 id 导致服务端响应匹配错乱。
_REQUEST_ID_COUNTER = itertools.count(1)

# 工具指纹: 出现这些 tool 名即可认定为对应类型
_TOOL_FINGERPRINTS = {
    "doc": {
        "get_document_content",
        "list_document_blocks",
        "create_document",
        "update_document",
    },
    "ai_table": {
        "list_bases",
        "get_base",
        "query_records",
        "create_records",
    },
    "sheet": {
        "get_all_sheets",
        "get_range",
        "update_range",
        "append_rows",
    },
}


# ============================================================
# 异常
# ============================================================


class DingMCPError(Exception):
    """钉钉 MCP API 错误。"""

    def __init__(self, message, details=None):
        self.details = details
        super().__init__(message)


# ============================================================
# URL / 配置
# ============================================================


_NODE_ID_RE = re.compile(r"/i/nodes/([A-Za-z0-9]+)")


def extract_id(url_or_id):
    """从钉钉链接里提取 nodeId / baseId / dentryUuid。

    支持的形态：
        https://alidocs.dingtalk.com/i/nodes/<id>?...
        https://docs.dingtalk.com/i/nodes/<id>?...
        其它 alidocs/docs 域名下的同结构 URL
    非 URL（已经是纯 ID）原样返回。

    AI 表格 MCP 严格要求 baseId 只含字母数字，必须用这个函数过滤。
    文档 MCP / Sheet MCP 接受两种形态，过滤后传入也能工作。
    """
    if not url_or_id or not isinstance(url_or_id, str):
        return url_or_id
    if url_or_id.startswith("http"):
        m = _NODE_ID_RE.search(url_or_id)
        if m:
            return m.group(1)
    return url_or_id


def _parse_mcp_url(mcp_url):
    """从 MCP URL 中解析出 base_url、server_id、key。"""
    parsed = urlparse(mcp_url)
    qs = parse_qs(parsed.query)

    key = qs.get("key", [None])[0]
    if not key:
        raise ValueError(
            f"MCP URL 中缺少 key 参数: {mcp_url}\n"
            "正确格式: https://mcp-gw.dingtalk.com/server/<server_id>?key=<api_key>"
        )

    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) < 2 or path_parts[0] != "server":
        raise ValueError(
            f"MCP URL 路径格式不正确: {parsed.path}\n"
            "正确格式: https://mcp-gw.dingtalk.com/server/<server_id>?key=<api_key>"
        )
    server_id = path_parts[1]
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    return {"base_url": base_url, "server_id": server_id, "key": key}


def _load_config():
    """加载 MCP 服务器配置列表。"""
    if not CONFIG_PATH.exists():
        raise DingMCPError(
            "尚未配置 MCP 服务器。\n"
            "请先调用 setup(mcp_url) 添加你的钉钉 MCP 地址。\n"
            "MCP URL 格式: https://mcp-gw.dingtalk.com/server/<server_id>?key=<api_key>"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    servers = config.get("mcp_servers", [])
    if not servers:
        raise DingMCPError("配置文件中没有 MCP 服务器，请调用 setup(mcp_url) 添加。")
    # 兼容老配置：缺 type 视作 "doc"
    for s in servers:
        s.setdefault("type", "doc")
    return servers


def _save_config(servers):
    """原子写入 servers.json：先写临时文件再 os.replace，避免崩溃/并发导致配置截断。"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"mcp_servers": servers}, ensure_ascii=False, indent=2)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".servers-", suffix=".tmp", dir=str(CONFIG_PATH.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, CONFIG_PATH)
    except BaseException:
        # 任何异常（含 KeyboardInterrupt）都清理临时文件，避免残留
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _mask(s):
    """脱敏 server 信息。"""
    return {
        "name": s.get("name", ""),
        "type": s.get("type", ""),
        "server_id": (s.get("server_id", "")[:16] + "...") if s.get("server_id") else "",
        "key": (s.get("key", "")[:8] + "...") if s.get("key") else "",
    }


# ============================================================
# MCP 通信层
# ============================================================


def _headers():
    return {"Content-Type": "application/json", "Accept": "application/json"}


def _mcp_call(server, method, params, request_id=None, timeout=60):
    """向指定 MCP 服务器发送 JSON-RPC 请求。

    request_id 缺省时自动从模块级计数器取唯一递增 id；显式传入仅用于测试/重放。
    """
    if request_id is None:
        request_id = next(_REQUEST_ID_COUNTER)
    url = f"{server['base_url']}?key={server['key']}"
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    response = requests.post(url, headers=_headers(), json=payload, timeout=timeout)

    if not response.ok:
        raise DingMCPError(
            f"HTTP {response.status_code}: {response.text}",
            details={"status_code": response.status_code},
        )
    data = response.json()
    if "error" in data:
        raise DingMCPError(
            f"MCP Error {data['error'].get('code')}: {data['error'].get('message')}",
            details=data["error"],
        )
    return data.get("result", {})


def _mcp_tool_call(server, tool_name, arguments, timeout=60):
    """调用一个 MCP 工具并解包 content。"""
    result = _mcp_call(
        server,
        method="tools/call",
        params={"name": tool_name, "arguments": arguments},
        timeout=timeout,
    )
    contents = result.get("content", [])
    if not contents:
        return {}
    text = contents[0].get("text", "")
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {"raw_text": text}


def _initialize_server(server):
    """MCP initialize 握手。"""
    return _mcp_call(
        server,
        method="initialize",
        params={
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": _CLIENT_INFO,
        },
    )


def _detect_server_type(server):
    """通过 tools/list 判别 server 的 MCP 类型。"""
    try:
        _initialize_server(server)
        result = _mcp_call(server, method="tools/list", params={})
        names = {t.get("name") for t in result.get("tools", [])}
        for t, fp in _TOOL_FINGERPRINTS.items():
            if fp.issubset(names):
                return t
    except Exception:
        pass
    return "unknown"


# ============================================================
# 公开 API（供子模块和用户使用）
# ============================================================


def try_servers(server_type, tool_name, arguments, timeout=60):
    """尝试所有匹配 server_type 的服务器，返回第一个成功结果。

    跨组织拒绝 / 业务失败 → 自动切换下一个；全部失败抛 DingMCPError。
    """
    all_servers = _load_config()
    candidates = [s for s in all_servers if s.get("type") == server_type]
    if not candidates:
        configured_types = sorted({s.get("type", "unknown") for s in all_servers})
        raise DingMCPError(
            f"未配置任何 [{server_type}] 类型的 MCP 服务器。\n"
            f"已配置的类型: {configured_types}\n"
            "请调用 setup(mcp_url) 添加对应类型的授权。"
        )

    errors = []
    for server in candidates:
        try:
            _initialize_server(server)
            result = _mcp_tool_call(server, tool_name, arguments, timeout=timeout)

            if isinstance(result, dict) and result.get("errorCode") == "forbidden.accessDenied":
                errors.append(
                    f"[{server.get('name', '?')}] 跨组织限制: {result.get('errorMessage', '')}"
                )
                continue
            if isinstance(result, dict) and result.get("success") is False:
                errors.append(
                    f"[{server.get('name', '?')}] {result.get('errorMessage', '未知错误')}"
                )
                continue
            return result

        except DingMCPError as e:
            errors.append(f"[{server.get('name', '?')}] {str(e)}")
            continue
        except requests.RequestException as e:
            errors.append(f"[{server.get('name', '?')}] 网络错误: {str(e)}")
            continue

    raise DingMCPError(
        f"所有 [{server_type}] MCP 服务器均无法完成请求:\n" + "\n".join(errors),
        details={"errors": errors},
    )


def setup(mcp_url, name=None, server_type=None):
    """添加一个 MCP 服务器。自动探测类型，也可显式指定。

    Args:
        mcp_url: 钉钉 MCP 地址
            (https://mcp-gw.dingtalk.com/server/<server_id>?key=<api_key>)
        name: 可选，给服务器起的名字。不传则自动生成 "<type>-<n>"
        server_type: 可选，强制指定类型（"doc" / "ai_table"）；不传则探测

    Returns:
        dict: {"success": bool, "message": str, "server": <脱敏 server>}
    """
    try:
        parsed = _parse_mcp_url(mcp_url)
    except ValueError as e:
        return {"success": False, "message": str(e)}

    try:
        servers = _load_config()
    except DingMCPError:
        servers = []

    # 已存在同 server_id → 更新 key/type
    for s in servers:
        if s.get("server_id") == parsed["server_id"]:
            s["key"] = parsed["key"]
            s["base_url"] = parsed["base_url"]
            if server_type:
                s["type"] = server_type
            _save_config(servers)
            return {
                "success": True,
                "message": f"已更新服务器 [{s['name']}] (type={s.get('type')}) 的配置。",
                "server": _mask(s),
            }

    # 新增：先探测类型
    probe = {
        "name": "_probe",
        "server_id": parsed["server_id"],
        "key": parsed["key"],
        "base_url": parsed["base_url"],
    }
    detected_type = server_type or _detect_server_type(probe)
    same_type_count = sum(1 for s in servers if s.get("type") == detected_type)
    server_name = name or f"{detected_type}-{same_type_count + 1}"

    new_server = {
        "name": server_name,
        "type": detected_type,
        "server_id": parsed["server_id"],
        "key": parsed["key"],
        "base_url": parsed["base_url"],
    }
    servers.append(new_server)
    _save_config(servers)

    return {
        "success": True,
        "message": (
            f"已添加 MCP 服务器 [{server_name}] (type={detected_type})，"
            f"当前共 {len(servers)} 个。"
        ),
        "server": _mask(new_server),
    }


def list_servers():
    """列出所有 MCP 服务器（脱敏）。"""
    try:
        servers = _load_config()
    except DingMCPError:
        return []
    return [{"index": i, **_mask(s)} for i, s in enumerate(servers)]


def remove_server(name_or_index):
    """按名称或索引删除一个 MCP 服务器配置。"""
    servers = _load_config()

    if isinstance(name_or_index, int):
        if 0 <= name_or_index < len(servers):
            removed = servers.pop(name_or_index)
            _save_config(servers)
            return {"success": True, "message": f"已删除服务器 [{removed['name']}]。"}
        return {"success": False, "message": f"索引 {name_or_index} 超出范围。"}

    for i, s in enumerate(servers):
        if s.get("name") == name_or_index:
            servers.pop(i)
            _save_config(servers)
            return {"success": True, "message": f"已删除服务器 [{name_or_index}]。"}

    return {"success": False, "message": f"未找到名为 [{name_or_index}] 的服务器。"}


def list_mcp_tools(server_index=0):
    """列出指定 MCP 服务器上的所有工具（调试用）。"""
    servers = _load_config()
    if not (0 <= server_index < len(servers)):
        raise DingMCPError(
            f"服务器索引 {server_index} 超出范围，共 {len(servers)} 个。"
        )
    server = servers[server_index]
    _initialize_server(server)
    return _mcp_call(server, method="tools/list", params={})
