#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bug 上报工具 —— 自动收集上下文并提交反馈

用法:
    python report_bug.py "probe_table 报错 datasourceType should not be null"
    python report_bug.py "trace_upstream 超时" --script trace_upstream.py
"""

import argparse
import json
import os
import sys
from datetime import datetime

from bff_client import BFFClient
from telemetry import telemetry_start, telemetry_end, telemetry_fail


# ─── 常量 ──────────────────────────────────────────────────────

_TAG = "[bug]"
_RUNTIME_DIR = os.path.join(".dataworks")
_LOG_DIR = "logs"
_MAX_LOG_LINES = 30     # 最近 N 行 API 调用日志
_MAX_RESULT_SIZE = 500  # 每个 result 文件最多取多少字符


# ─── 上下文收集 ──────────────────────────────────────────────

def _collect_session_state():
    """收集 session_state.json"""
    path = os.path.join(_RUNTIME_DIR, "session_state.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _collect_recent_results():
    """收集最近的 tool result 文件"""
    results = {}
    if not os.path.isdir(_RUNTIME_DIR):
        return results
    for fname in os.listdir(_RUNTIME_DIR):
        if fname.endswith("_result.json"):
            path = os.path.join(_RUNTIME_DIR, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read(_MAX_RESULT_SIZE)
                results[fname] = content
            except Exception:
                pass
    return results


def _collect_recent_logs():
    """收集最近的 API 调用日志"""
    log_path = os.path.join(_LOG_DIR, "dw_bff_calls.log")
    if not os.path.exists(log_path):
        return None
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return "".join(lines[-_MAX_LOG_LINES:])
    except Exception:
        return None


def _collect_error_from_result(script_name):
    """从 result 文件中提取错误信息"""
    if not script_name:
        return None
    # 去掉 .py 后缀
    base = script_name.replace(".py", "")
    result_path = os.path.join(_RUNTIME_DIR, f"{base}_result.json")
    if not os.path.exists(result_path):
        return None
    try:
        with open(result_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("status") in ("error", "failed", "fail"):
            return data
    except Exception:
        pass
    return None


# ─── 组装报告 ────────────────────────────────────────────────

def _build_report(description, script_name=None):
    """组装结构化 bug 报告"""
    report = {
        "type": "bug_report",
        "timestamp": datetime.now().isoformat(),
        "description": description,
    }

    if script_name:
        report["script"] = script_name

    # 收集上下文
    session = _collect_session_state()
    if session:
        # 提取关键信息，不传完整 session
        context = session.get("context", {})
        tools = session.get("tool_results", {})
        report["context"] = {
            "projectId": context.get("projectId"),
            "recent_tools": list(tools.keys()) if tools else [],
        }

    # 收集相关脚本的错误
    error = _collect_error_from_result(script_name)
    if error:
        report["error_detail"] = error

    # 最近 API 调用日志
    logs = _collect_recent_logs()
    if logs:
        report["recent_api_logs"] = logs

    return report


# ─── 主流程 ──────────────────────────────────────────────────

def report(args):
    description = args.description
    script_name = args.script

    print(f"{_TAG} 收集上下文...")

    report_data = _build_report(description, script_name)

    # 格式化为可读的 text
    text_parts = [
        f"[Bug Report] {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"问题描述: {description}",
    ]
    if script_name:
        text_parts.append(f"相关脚本: {script_name}")

    ctx = report_data.get("context", {})
    if ctx.get("projectId"):
        text_parts.append(f"工作空间: {ctx['projectId']}")
    if ctx.get("recent_tools"):
        text_parts.append(f"最近操作: {', '.join(ctx['recent_tools'])}")

    error = report_data.get("error_detail")
    if error:
        text_parts.append(f"错误详情: {json.dumps(error, ensure_ascii=False, default=str)[:300]}")

    logs = report_data.get("recent_api_logs")
    if logs:
        # 只取最后 5 行日志
        log_lines = logs.strip().split("\n")[-5:]
        text_parts.append(f"最近 API 调用:\n" + "\n".join(log_lines))

    text = "\n".join(text_parts)

    print(f"{_TAG} 报告内容:")
    print(text)
    print()

    # 上报
    client = BFFClient(quiet=True)
    try:
        result = client.load("suggest", text=text)
        print(f"{_TAG} 上报成功")
    except Exception as e:
        print(f"{_TAG} 上报失败: {e}")
        # 即使上报失败，也保存本地副本
    finally:
        # 保存本地副本
        local_path = os.path.join(_RUNTIME_DIR, "last_bug_report.json")
        os.makedirs(_RUNTIME_DIR, exist_ok=True)
        try:
            with open(local_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)
            print(f"{_TAG} 本地副本: {local_path}")
        except Exception:
            pass


# ─── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Bug 上报（自动收集上下文）")
    parser.add_argument("description", help="问题描述")
    parser.add_argument("--script", help="相关脚本名（如 probe_table.py）")
    args = parser.parse_args()

    telemetry_start("report_bug.py", module="workspace", description=args.description)

    report(args)
    telemetry_end(result={"status": "reported"})


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("report_bug.py", "workspace", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("report_bug.py", "workspace", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
