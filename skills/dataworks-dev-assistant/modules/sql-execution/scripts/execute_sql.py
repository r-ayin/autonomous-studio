#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQL 执行工具 —— 在指定数据源上执行 SQL 并返回结果

SELECT 等只读语句：直接执行，无需确认。
INSERT/UPDATE/DELETE/DROP 等写语句：两阶段确认（prepare → 用户确认 → --confirm）。

用法:
    # 只读 SQL（SELECT/SHOW/DESCRIBE/EXPLAIN/WITH）→ 直接执行
    python execute_sql.py "SELECT * FROM table LIMIT 10" --datasource-code ds0dd...

    # 写 SQL（INSERT/UPDATE/DELETE/DROP/CREATE/ALTER）→ 两阶段确认
    python execute_sql.py "INSERT INTO ..." --datasource-code ds0dd...
    # 输出确认摘要，用户确认后：
    python execute_sql.py --confirm

参数获取策略:
    --datasource-code: 来自 list_datasource_da.py（推荐）
    都缺失时 stdout 提示 agent 先运行 list_datasource_da.py 让用户选择数据源。
"""

import argparse
import json
import os
import re
import sys
import time
import uuid

from bff_client import BFFClient, save_tool_result, add_backlog
from telemetry import telemetry_start, telemetry_end, telemetry_fail


# ─── SQL 类型判断 ──────────────────────────────────────────────────

# 只读 SQL 关键词（语句开头匹配）
_READONLY_PREFIXES = re.compile(
    r"^\s*(SELECT|SHOW|DESCRIBE|DESC|EXPLAIN|WITH)\b",
    re.IGNORECASE,
)


def _is_readonly_sql(sql):
    """判断 SQL 是否为只读语句"""
    return bool(_READONLY_PREFIXES.match(sql))


# ─── 参数推断 ──────────────────────────────────────────────────────


def _load_session_state():
    """从 .dataworks/session_state.json 加载会话状态"""
    state_path = os.path.join(os.path.expanduser("~"), ".dataworks", "session_state.json")
    if not os.path.exists(state_path):
        return {}
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _infer_from_session(state):
    """从 session state 中推断 projectId 和 dataSourceId"""
    project_id = None
    datasource_id = None

    tables = state.get("tables", {})
    sorted_tables = sorted(
        tables.values(),
        key=lambda t: t.get("called_at", ""),
        reverse=True,
    )

    for table_info in sorted_tables:
        params = table_info.get("params") or {}
        if not project_id and params.get("projectId"):
            project_id = str(params["projectId"])
        if not datasource_id and params.get("dataSourceId"):
            datasource_id = str(params["dataSourceId"])
        if project_id and datasource_id:
            break

    return project_id, datasource_id


def _validate_params(datasource_code, project_id, datasource_id):
    """校验参数，缺失时给出引导并退出"""
    if datasource_code:
        return

    if not project_id or not datasource_id:
        state = _load_session_state()
        inferred_pid, inferred_dsid = _infer_from_session(state)
        if not project_id:
            project_id = inferred_pid
        if not datasource_id:
            datasource_id = inferred_dsid

    missing = []
    if not project_id:
        missing.append("--project-id")
    if not datasource_id:
        missing.append("--datasource-id")
    if missing:
        print(f"[execute_sql] 缺少 --datasource-code 参数")
        print(f"[execute_sql] → 先运行: python list_datasource_da.py --project-id <id>")
        print(f"[execute_sql]   列出可用数据源后，让用户选择 datasource-code")
        print(f"[execute_sql]   再运行: python execute_sql.py \"SQL\" --datasource-code <用户选择的code>")
        sys.exit(1)


# ─── jobType 映射 ──────────────────────────────────────────────────


_JOB_TYPE_TO_NODE_TYPE = {
    "ODPS_SQL": 10,
    "HOLOGRES": 1093,
}


# ─── 提交 + 轮询 + 取结果（公共逻辑） ───────────────────────────────


def _build_api_params(sql, datasource_code=None, project_id=None,
                      datasource_id=None, job_type=None, timeout=300,
                      readonly=False):
    """构造 API 调用参数，返回 (api_name, params)

    readonly=True 时返回 Read 变体 API（is_write_operation=false），
    readonly=False 时返回原始 API（is_write_operation=true，需 write/confirm_write）。
    """
    uid = str(uuid.uuid4())

    if datasource_code:
        api_name = "createQueryJobRead" if readonly else "createQueryJob"
        return api_name, {
            "executorMode": "SIMPLE_QUERY",
            "dataSourceCode": datasource_code,
            "codeContent": sql,
            "fileCode": uid,
            "param": {},
            "uuid": uid,
            "queryAuthStrategy": "DATASOURCE",
            "_timeout": timeout,
        }
    else:
        api_name = "createExecutorJob4IdaRead" if readonly else "createExecutorJob4Ida"
        file_id = f"fileuuid_{uuid.uuid4().hex[:8]}"
        params = {
            "scriptContent": sql,
            "appName": "DATAWORKS_DATA_ANALYSIS",
            "projectId": project_id,
            "dataSourceId": datasource_id,
            "expandMap": {
                "FILE_ID_KEY": file_id,
                "FILE_NAME_KEY": file_id,
            },
            "_timeout": timeout,
        }
        if job_type:
            params["jobType"] = job_type
            node_type = _JOB_TYPE_TO_NODE_TYPE.get(job_type)
            if node_type:
                params["nodeType"] = node_type
        return api_name, params


def _fetch_full_log(client, job_code, base_log, max_pages=20):
    """terminal 后从 index=1 起拼接所有页，避免 FAILED 行被截断在后续 index"""
    all_content = base_log.get("content", "") or ""
    for idx in range(1, max_pages + 1):
        try:
            page = client.load("getExecutorJobLog4Ida", jobCode=job_code, index=str(idx))
        except Exception:
            break
        page_content = page.get("content", "") or ""
        if not page_content:
            break
        all_content += page_content
        if page.get("end") is True:
            break
    base_log["content"] = all_content
    return base_log


def _poll_log(client, job_code, sql, timeout=300, interval=2):
    """轮询执行日志直到完成，超时则写入 backlog 而非报错"""
    start = time.time()
    while True:
        log = client.load("getExecutorJobLog4Ida", jobCode=job_code, index="0")

        is_end = log.get("end") is True
        status = log.get("status", "")
        is_terminal = status in ("SUCCESS", "FAIL", "CANCELED")

        if is_end and is_terminal:
            return _fetch_full_log(client, job_code, log)

        elapsed = time.time() - start
        if elapsed > timeout:
            # 超时不报错，写入 backlog 让用户稍后查
            sql_preview = (sql[:60] + "...") if len(sql) > 60 else sql
            _script_dir = os.path.dirname(os.path.abspath(__file__))
            _core_dir = os.path.abspath(os.path.join(_script_dir, "..", "..", "..", "core"))
            add_backlog(
                type_name="sql",
                label=f"SQL执行 jobCode={job_code} | {sql_preview}",
                check={
                    "api": "getExecutorJobLog4Ida",
                    "params": {"jobCode": job_code, "index": "0"},
                    "status_field": "status",
                    "terminal": {"SUCCESS": "成功", "FAIL": "失败", "CANCELED": "已取消"},
                    "pending": {"RUNNING": "运行中", "SUBMITTED": "已提交"},
                },
                context={"job_code": job_code, "sql": sql},
                on_success=f"SQL 执行完成，获取结果: PYTHONPATH={_core_dir} python {_script_dir}/execute_sql.py --fetch {job_code}",
            )
            print(f"[execute_sql] SQL 执行超过 {timeout}s 仍未完成，已加入异步任务列表")
            print(f"[execute_sql] ⚠️ 不要轮询等待。告知用户 SQL 在后台运行中，用户需要时再执行: python check_backlogs.py")
            save_tool_result("execute_sql", {
                "summary": f"SQL 执行中（超时转异步）| jobCode={job_code}",
                "jobCode": job_code,
                "status": "ASYNC",
                "sql": sql,
            })
            sys.exit(0)

        time.sleep(interval)


def _fetch_and_output(client, job_code, sql, cost_time):
    """取结果 + DuckDB 灌入 + save_tool_result"""
    fetch_result = client.load("getExecutorJobResult4Ida", jobCode=job_code, index="0")
    header_list = fetch_result.get("headerList") or []
    body_list = fetch_result.get("bodyList") or []
    count = fetch_result.get("count", len(body_list))

    print(f"[execute_sql] 执行成功 | 耗时 {cost_time}ms | {count} 行")

    if not header_list:
        print(f"[execute_sql] 无返回数据（可能是 DDL/DML 语句）")
        save_tool_result("execute_sql", {
            "summary": f"SQL 执行成功，无返回数据",
            "jobCode": job_code,
            "status": "SUCCESS",
            "sql": sql,
            "row_count": 0,
        })
        return []

    # 格式化
    col_names = [h["name"] for h in header_list]
    rows = []
    for row_values in body_list:
        row = {}
        for i, name in enumerate(col_names):
            row[name] = row_values[i] if i < len(row_values) else None
        rows.append(row)

    # 灌入 DuckDB
    if rows and client.loader:
        try:
            table_name = client.loader.load("execute_sql", rows)
            client.last_table = table_name
            print(f"[{table_name}] {count} 条 | {', '.join(col_names)}")
        except Exception as e:
            print(f"[execute_sql] DuckDB 加载失败: {e}", file=sys.stderr)

    save_tool_result("execute_sql", {
        "summary": f"SQL 执行成功，{count} 行",
        "jobCode": job_code,
        "status": "SUCCESS",
        "sql": sql,
        "row_count": count,
        "columns": col_names,
        "exceed_flag": fetch_result.get("exceedFlag", False),
    })

    return rows


def _handle_failure(job_code, sql, log):
    """处理执行失败"""
    status = log.get("status", "UNKNOWN")
    cost_time = log.get("costTime", 0)
    extended = log.get("extended") or {}
    error_msg = extended.get("errorMessage") or log.get("content", "")
    solution = extended.get("solutionMessage", "")
    print(f"[execute_sql] 执行失败 | status={status} | 耗时 {cost_time}ms")
    print(f"[execute_sql] 错误: {error_msg}")
    if solution:
        print(f"[execute_sql] 建议: {solution}")

    save_tool_result("execute_sql", {
        "summary": f"SQL 执行失败: {status}",
        "jobCode": job_code,
        "status": status,
        "error": error_msg,
        "solution": solution,
        "sql": sql,
    })
    sys.exit(1)


# ─── 只读 SQL：直接执行 ──────────────────────────────────────────────


def execute_readonly(sql, datasource_code=None, project_id=None,
                     datasource_id=None, job_type=None, timeout=300):
    """只读 SQL 直接执行，无需确认。使用 Read 变体 API（is_write_operation=false）"""
    client = BFFClient(quiet=True)
    api_name, params = _build_api_params(
        sql, datasource_code, project_id, datasource_id, job_type, timeout,
        readonly=True)

    ds_display = datasource_code or f"projectId={project_id}, dataSourceId={datasource_id}"
    print(f"[execute_sql] 提交只读 SQL ({ds_display})")

    call_params = {k: v for k, v in params.items() if not k.startswith("_")}
    result = client.load(api_name, **call_params)

    job_code = result.get("jobCode") if isinstance(result, dict) else None
    if not job_code:
        raise RuntimeError(f"提交 SQL 失败：未返回 jobCode。响应: {result}")
    print(f"[execute_sql] jobCode={job_code} | 轮询中...")

    log = _poll_log(client, job_code, sql, timeout=timeout)
    if log.get("status") != "SUCCESS":
        _handle_failure(job_code, sql, log)

    cost_time = log.get("costTime", 0)
    if not log.get("result", True):
        print(f"[execute_sql] 执行成功 | 耗时 {cost_time}ms | 无返回数据（DDL/DML）")
        save_tool_result("execute_sql", {
            "summary": "SQL 执行成功，无返回数据",
            "jobCode": job_code,
            "status": "SUCCESS",
            "sql": sql,
            "row_count": 0,
        })
        return []
    return _fetch_and_output(client, job_code, sql, cost_time)


# ─── 取已完成 job 的结果 ──────────────────────────────────────────────


def fetch_result(job_code):
    """从已完成的 job 取结果（用于异步 SQL 完成后取数据）"""
    client = BFFClient(quiet=True)
    print(f"[execute_sql] 查询 jobCode={job_code} 状态...")

    log = client.load("getExecutorJobLog4Ida", jobCode=job_code, index="0")
    status = log.get("status", "")

    if status == "SUCCESS":
        cost_time = log.get("costTime", 0)
        return _fetch_and_output(client, job_code, "(async SQL)", cost_time)
    elif status in ("FAIL", "CANCELED"):
        _handle_failure(job_code, "(async SQL)", log)
    else:
        print(f"[execute_sql] SQL 仍在执行中 | status={status}")
        print(f"[execute_sql] ⚠️ 不要轮询等待。告知用户 SQL 仍在运行，用户需要时再执行: python check_backlogs.py")
        sys.exit(0)


# ─── 写 SQL：两阶段确认 ──────────────────────────────────────────────


def prepare_write_sql(sql, datasource_code=None, project_id=None,
                      datasource_id=None, job_type=None, timeout=300):
    """写 SQL Phase 1：通过 client.write() 输出确认摘要"""
    client = BFFClient(quiet=True)
    api_name, params = _build_api_params(
        sql, datasource_code, project_id, datasource_id, job_type, timeout)

    client.write(api_name, **params)
    print(f"  → 确认后执行: python execute_sql.py --confirm")


def confirm_and_execute():
    """写 SQL Phase 2：confirm_write() → 轮询 → 取结果"""
    pending_path = os.path.join(os.path.expanduser("~"), ".dataworks", "pending_write.json")
    if not os.path.exists(pending_path):
        print("[execute_sql] 没有待确认的 SQL。请先运行: python execute_sql.py \"SQL\" --datasource-code <code>")
        sys.exit(1)

    with open(pending_path, "r", encoding="utf-8") as f:
        pending = json.load(f)

    params = pending.get("params", {})
    sql = params.get("codeContent") or params.get("scriptContent", "")
    timeout = params.pop("_timeout", 300)

    client = BFFClient(quiet=True)
    result = client.confirm_write()

    job_code = result.get("jobCode") if isinstance(result, dict) else None
    if not job_code:
        raise RuntimeError(f"提交 SQL 失败：未返回 jobCode。响应: {result}")

    print(f"[execute_sql] jobCode={job_code} | 轮询中...")

    log = _poll_log(client, job_code, sql, timeout=timeout)
    if log.get("status") != "SUCCESS":
        _handle_failure(job_code, sql, log)

    cost_time = log.get("costTime", 0)
    if not log.get("result", True):
        print(f"[execute_sql] 执行成功 | 耗时 {cost_time}ms | 无返回数据（DDL/DML）")
        save_tool_result("execute_sql", {
            "summary": "SQL 执行成功，无返回数据",
            "jobCode": job_code,
            "status": "SUCCESS",
            "sql": sql,
            "row_count": 0,
        })
        return []
    return _fetch_and_output(client, job_code, sql, cost_time)


# ─── 入口 ──────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="在 DataWorks 数据源上执行 SQL",
        epilog="SELECT 等只读语句直接执行；写语句需两阶段确认（prepare → --confirm）",
    )
    parser.add_argument("sql", nargs="?", help="要执行的 SQL 语句")
    parser.add_argument("--confirm", action="store_true",
                        help="执行已确认的写 SQL（Phase 2）")
    parser.add_argument("--fetch", metavar="JOB_CODE",
                        help="从已完成的 job 取结果（jobCode）")
    parser.add_argument("--datasource-code", dest="datasource_code",
                        help="数据源代码（ds...格式），来自 list_datasource_da.py")
    parser.add_argument("--project-id", dest="project_id", help="DataWorks 工作空间 ID")
    parser.add_argument("--datasource-id", dest="datasource_id",
                        help="DataWorks 数据源 ID（数字），来自 listConnection")
    parser.add_argument(
        "--job-type", dest="job_type",
        choices=["ODPS_SQL", "HOLOGRES", "MYSQL", "POSTGRESQL", "ORACLE", "STARROCKS", "CLICKHOUSE", "PYTHON"],
        help="执行引擎类型（仅 --datasource-id 路径需要）",
    )
    parser.add_argument("--timeout", type=int, default=300, help="执行超时秒数（默认 300）")

    args = parser.parse_args()

    telemetry_start("execute_sql.py", module="sql-execution", sql=args.sql, project_id=args.project_id)

    if args.fetch:
        fetch_result(args.fetch)
        telemetry_end(result={"action": "fetch"})
    elif args.confirm:
        confirm_and_execute()
        telemetry_end(result={"action": "confirm"})
    elif args.sql:
        _validate_params(args.datasource_code, args.project_id, args.datasource_id)

        if _is_readonly_sql(args.sql):
            execute_readonly(
                sql=args.sql,
                datasource_code=args.datasource_code,
                project_id=args.project_id,
                datasource_id=args.datasource_id,
                job_type=args.job_type,
                timeout=args.timeout,
            )
            telemetry_end(result={"action": "readonly"})
        else:
            prepare_write_sql(
                sql=args.sql,
                datasource_code=args.datasource_code,
                project_id=args.project_id,
                datasource_id=args.datasource_id,
                job_type=args.job_type,
                timeout=args.timeout,
            )
            telemetry_end(result={"action": "prepare_write"})
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("execute_sql.py", "sql-execution", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("execute_sql.py", "sql-execution", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
