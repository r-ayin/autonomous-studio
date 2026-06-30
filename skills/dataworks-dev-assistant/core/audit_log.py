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
import sys
from datetime import datetime


def _audit_id(now=None):
    """audit-YYYYMMDD-HHmmss-rand6 —— 对齐 schema id pattern。

    可选传 now 以让 id 与 record() 内的 timestamp/filename 三者同源，避免在秒/午夜
    边界分别调用 datetime.now() 致 id 日期(YYYYMMDD) 与落盘文件日期(YYYY-MM-DD) 不一致
    （如 23:59:59.999 生成 id → 00:00:00.001 落盘 → id 标昨日、文件属今日）。
    """
    now = now or datetime.now()
    return "audit-" + now.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)


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


def _resource_type_for(action):
    """将 schema action 映射到 schema resource.type 枚举。

    audit-log.schema.json 规定 resource 为对象 {type, identifier}，type 取值限于
    file/artifact/deployment/config/permission/secret/pipeline/model/session。
    DataWorks 写 API 操作的资源类型由此按 action 近似推导（无完整元数据时取最贴近项），
    使审计记录符合 schema 契约——此前 resource 写成裸字符串 api_name 违反 required 结构，
    任何 schema 校验器会拒收全部记录（DO B：字段对齐 schema）。
    """
    if action == "permission_change":
        return "permission"
    if action in ("deploy", "pipeline_cancel"):
        return "pipeline"
    if action in ("create", "delete"):
        return "artifact"
    return "config"  # update / compliance_check 及未知写操作归 config


def record(work_dir, api_name, params_summary, result_code, *, user_id="unknown",
           user_role="engine", ip="local", bypass=False,
           correlation_id=None, attempt=None):
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
        correlation_id: 一次逻辑写操作的关联 ID。bff_client._call 在限频重试循环前
            生成一次，重试的每次 _do_request 共享同一值，使审计者能区分「1 次逻辑写
            命中限频重试 N 次」与「N 次独立逻辑写」（case-348 F2 修复）。call_raw 单次
            直调也生成独有值。None 则不写该字段（向后兼容旧调用点）。
        attempt: 重试序号（0=首次，1..N=限频重试）。None 则不写。
    """
    try:
        log_dir = os.path.join(work_dir, ".dataworks", ".audit")
        os.makedirs(log_dir, exist_ok=True)
        # 单次捕获 now：id/timestamp/filename 三者同源，避免跨秒/午夜边界调用多次
        # datetime.now() 致 id 日期与落盘文件日期不一致（审计记录内部一致性）。
        now = datetime.now()
        action = _action_for(api_name)
        result = "success" if result_code in (0, 200) else "failure"
        entry = {
            "id": _audit_id(now),
            "timestamp": now.isoformat(),
            "userId": str(user_id),
            "userRole": user_role,
            "action": action,
            "resource": {
                "type": _resource_type_for(action),
                "identifier": api_name,
            },
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
        # 关联 ID/重试序号仅在调用方提供时写入，避免污染旧调用点的记录
        # （correlation_id 把同一次逻辑写的限频重试多条记录串起来，case-348 F2）。
        if correlation_id is not None:
            entry["details"]["correlationId"] = str(correlation_id)
        if attempt is not None:
            entry["details"]["attempt"] = attempt
        path = os.path.join(log_dir, "audit-" + now.strftime("%Y-%m-%d") + ".jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception as exc:
        # 审计日志失败不应阻断业务写操作（不 re-raise），但须可观测——
        # 落 stderr 而非 silent pass，避免审计写失败被静默吞掉（DO B：result 须如实反映成功/失败，不可恒静默）。
        try:
            sys.stderr.write(
                "[audit_log] write failed (non-blocking): api={api} result_code={code} err={err}\n".format(
                    api=api_name, code=result_code, err=repr(exc)))
        except Exception:
            pass
