"""钉钉文档 MCP 封装（薄层，复用 _mcp_client）。

对外 API 保持与早期 dingtalk-doc-rw 兼容。
"""

from ._mcp_client import (  # noqa: F401  (re-export)
    DingMCPError,
    setup,
    list_servers,
    remove_server,
    list_mcp_tools,
    try_servers,
)

_TYPE = "doc"


# ============================================================
# 读取
# ============================================================


def read_doc(url):
    """读取钉钉文档内容（Markdown 格式）。

    Args:
        url: 钉钉文档链接 https://alidocs.dingtalk.com/i/nodes/<nodeId>

    Returns:
        dict: 含 "markdown" 等字段
    """
    return try_servers(_TYPE, "get_document_content", {"nodeId": url})


def read_doc_blocks(url, start_index=None, end_index=None, block_type=None):
    """读取钉钉文档的块元素列表。"""
    arguments = {"nodeId": url}
    if start_index is not None:
        arguments["startIndex"] = start_index
    if end_index is not None:
        arguments["endIndex"] = end_index
    if block_type:
        arguments["blockType"] = block_type
    return try_servers(_TYPE, "list_document_blocks", arguments)


def get_doc_info(url):
    """获取文档元信息。"""
    return try_servers(_TYPE, "get_document_info", {"nodeId": url})


# ============================================================
# 写入 / 块操作
# ============================================================


def create_doc(doc_name, content="", workspace_id=None, folder_id=None):
    """创建新的钉钉文档。"""
    arguments = {"name": doc_name}
    if content:
        arguments["markdown"] = content
    if workspace_id:
        arguments["workspaceId"] = workspace_id
    if folder_id:
        arguments["folderId"] = folder_id
    return try_servers(_TYPE, "create_document", arguments)


def update_doc(url, content):
    """全量更新文档内容（Markdown）。"""
    return try_servers(_TYPE, "update_document", {"nodeId": url, "markdown": content})


def insert_block(url, element):
    """在文档末尾插入一个块元素。"""
    return try_servers(_TYPE, "insert_document_block", {"nodeId": url, "element": element})


def update_block(url, block_id, element):
    """更新文档中指定块元素。"""
    return try_servers(
        _TYPE,
        "update_document_block",
        {"nodeId": url, "blockId": block_id, "element": element},
    )


def delete_block(url, block_id):
    """删除文档中指定块元素。"""
    return try_servers(_TYPE, "delete_document_block", {"nodeId": url, "blockId": block_id})


# ============================================================
# 搜索 / 浏览
# ============================================================


def search_docs(keyword, count=10):
    """搜索钉钉文档。"""
    return try_servers(_TYPE, "search_documents", {"keyword": keyword, "count": count})


def list_nodes(folder_id=None, workspace_id=None):
    """列出文件夹或知识库下的文件列表。"""
    arguments = {}
    if folder_id:
        arguments["folderId"] = folder_id
    if workspace_id:
        arguments["workspaceId"] = workspace_id
    return try_servers(_TYPE, "list_nodes", arguments)


def create_folder(name, workspace_id=None, parent_folder_id=None):
    """创建文件夹。"""
    arguments = {"name": name}
    if workspace_id:
        arguments["workspaceId"] = workspace_id
    if parent_folder_id:
        arguments["parentFolderId"] = parent_folder_id
    return try_servers(_TYPE, "create_folder", arguments)
