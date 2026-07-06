"""Skill 用量统计 — 每次触发时静默写入一条记录到钉钉 AI 表格。

埋点固定走 skill 作者的 MCP 授权，不依赖用户本地 servers.json 配置。
"""

import sys
import subprocess
import os
import json
from datetime import datetime

import requests

BASE_ID = "EpGBa2Lm8aZxe5myCwXB1Ek2WgN7R35y"
TABLE_ID = "hERWDMS"
FIELD_SKILL = "VBgG6lv"
FIELD_USER = "Rmokh4y"
FIELD_TS = "FaG0OSB"
FIELD_DIAGRAM_TYPE = "9o7vorp"

_MCP_BASE_URL = os.environ.get("EXCALIDRAW_MCP_BASE_URL", "")
_MCP_KEY = os.environ.get("EXCALIDRAW_MCP_KEY", "")
_MCP_PROTOCOL_VERSION = "2024-11-05"


def _mcp_call(method, params, timeout=30):
    url = f"{_MCP_BASE_URL}?key={_MCP_KEY}"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", "MCP error"))
    return data.get("result", {})


def ping(skill_name="excalidraw-diagram", diagram_type=""):
    try:
        user = subprocess.check_output(
            ["git", "config", "user.name"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        user = os.environ.get("USER", "unknown")

    _mcp_call("initialize", {
        "protocolVersion": _MCP_PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "excalidraw-skill-ping", "version": "0.1.0"},
    })

    _mcp_call("tools/call", {
        "name": "create_records",
        "arguments": {
            "baseId": BASE_ID,
            "tableId": TABLE_ID,
            "records": [{
                "cells": {
                    FIELD_SKILL: skill_name,
                    FIELD_USER: user,
                    FIELD_TS: datetime.now().strftime("%Y-%m-%d %H:%M"),
                    FIELD_DIAGRAM_TYPE: diagram_type,
                }
            }],
        },
    })


if __name__ == "__main__":
    skill = sys.argv[1] if len(sys.argv) > 1 else "excalidraw-diagram"
    dtype = sys.argv[2] if len(sys.argv) > 2 else ""
    ping(skill, dtype)
