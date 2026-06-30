#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计日志（append-only JSONL）—— 记录敏感写操作的本地执行轨迹。

按 .claude/decisions/audit-log.schema.json 字段对齐。纯本地文件，不接外部系统、不建表。

用途：bff_client._do_request 是所有 HTTP 调用（读/写）的唯一 chokepoint。当被调 API
是写操作（is_write_operation=True）时，无论经由 confirm_write()（两阶段确认 sanctioned
路径）还是 call_raw()（调试通道，绕过确认门禁），都落一条审计记录，使写操作执行可被
追溯——特别是 call_raw 直接调写 API 的绕过不再 silent。

审计失败永不阻断业务写操作（except 吞掉）。
"""
import json
import os
import secrets
from datetime import datetime


def _audit_id():
    """audit-YYYYMMDD-HHmmss-rand6 —— 对齐 schema id pattern。"""
    return "audit-" + datetime.now().strftime("%Y%m%d-%H%m%S") + "-" + secrets.token_hex(3)


def _action_for(api_name):
    """将 API 名映射到 schema action 枚举；未知写操作归为 update。"""
    n = (api_name or "").lower()
    if "permission" in n or "access" in n:
        return "permission_change"
    if "rule" in n or "governance" in n or "compliance" in n:
        return "compliance_check"
    if n.startswith("create") or n.startswith("import"):
        return "create"
    if n.startswith("delete"):
        return "delete"
    if n.startswith("stop") or n.startswith("cancel"):
        return "pipeline_cancel"
    if "pipeline" in n or "deploy" in n or "stage" in n:
        return "deploy"
    return "update"


def record(work_dir, api_name, params_summary, result_code, *, user_id="unknown",
           user_role="engine", ip="local", bypass=False):
    """append 一条审计记录到 <work_dir>/.dataworks/.audit/audit-YYYY-MM-DD.jsonl。

    Args:
        work_dir: bff_client._work_dir（已 expanduser 的 home）。
        api_name: 写 API 名（如 applyResourceAccessPermission）。
        params_summary: 参数的可记录摘要（字符串，避免完整 PII；调用方负责脱敏）。
        result_code: 原始响应 code；0/200 视为 success，否则 failure。
        user_id: 操作者标识（baseId / 工号）。未知写 'unknown'。
        user_role: 固定 'engine'（skill 由 AI 引擎驱动）。
        ip: 本地引擎上下文写 'local'（skill 无法可靠推断操作者源 IP）。
        bypass: True 表示经由 call_raw 绕过两阶段确认（审计重点关注）。
    """
    try:
        log_dir = os.path.join(work_dir, ".dataworks", ".audit")
        os.makedirs(log_dir, exist_ok=True)
        result = "success" if result_code in (0, 200) else "failure"
        entry = {
            "id": _audit_id(),
            "timestamp": datetime.now().isoformat(),
            "userId": str(user_id),
            "userRole": user_role,
            "action": _action_for(api_name),
            "resource": api_name,
            "result": result,
            "ip": ip,
            "sensitive": True,
            "sensitiveLevel": "medium",
            "details": {
                "params_summary": params_summary,
                "result_code": result_code,
                "bypassed_two_phase_confirm": bypass,
            },
        }
        path = os.path.join(log_dir, "audit-" + datetime.now().strftime("%Y-%m-%d") + ".jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception:
        # 审计日志失败不应阻断业务写操作
        pass
