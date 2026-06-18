#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""表数据采样 —— 一条命令看表前 N 行

用法:
    python sample_table.py "表名"                            # 自动识别项目，前 10 行
    python sample_table.py "项目.表名"                        # 全限定名
    python sample_table.py "表名" --project dataworks_analyze
    python sample_table.py "表名" -n 20                       # 前 20 行
    python sample_table.py "表名" --columns id,name           # 只选指定字段
    python sample_table.py "表名" --where "status=1"         # 额外过滤条件

流程:
    1. find_table 搜索表（支持同名多项目过滤）
    2. listColumns 获取字段 + 分区键
    3. 分区表自动补 WHERE ds=MAX_PT('project.table')，双分区再补 region
    4. 自动发现 DEV MaxCompute 数据源（避免影响生产）
    5. 提交只读 SQL → 执行 → 结果灌入 DuckDB 供二次聚合

失败提示:
    权限不足 → 通常是敏感字段（label=2），用 --columns 指定非敏感字段
    无分区数据 → 用 --where 指定历史分区: --where "ds=20260101"
"""

import argparse
import sys
import os

from bff_client import BFFClient, save_tool_result
from telemetry import telemetry_start, telemetry_end, telemetry_fail

# 复用 discovery 模块脚本（通过 sys.path 中已配的 PYTHONPATH）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DISCOVERY_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..", "discovery", "scripts"))
if _DISCOVERY_DIR not in sys.path:
    sys.path.insert(0, _DISCOVERY_DIR)


def _apply_script_path():
    """返回 apply_resource_access.py 的绝对路径；不存在（如 alibaba 弹内 dist 排除了 security-center）返回 None"""
    candidate = os.path.abspath(os.path.join(
        _SCRIPT_DIR, "..", "..", "security-center", "scripts", "apply_resource_access.py"))
    return candidate if os.path.exists(candidate) else None


def _current_session_workspace():
    """读 session_state.json 的当前工作空间 ID；读不到返回 None（不阻塞主流程）"""
    import json
    for path in (
        os.path.join(os.getcwd(), ".dataworks", "session_state.json"),
        os.path.join(os.path.expanduser("~"), ".dataworks", "session_state.json"),
    ):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            ctx = state.get("context") or {}
            ws = ctx.get("workspace") or ctx.get("project") or {}
            pid = ws.get("projectId") or ws.get("id") or ctx.get("projectId")
            if pid:
                return pid
        except Exception:
            pass
    return None


def _print_failure_next_steps(database, table_name, target_pid=None):
    """SQL 执行失败后读 execute_sql 的结果文件，针对权限类错误输出申请链路。"""
    import json, re
    result_path = os.path.join(os.getcwd(), ".dataworks", "execute_sql_result.json")
    if not os.path.exists(result_path):
        print(f'\n[sample] 失败兜底：用 --columns 指定字段 / --where 指定分区重试')
        print(f'[sample] 先看字段: query_columns.py "{database}.{table_name}"')
        return
    try:
        with open(result_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return

    err = payload.get("error") or ""
    # 敏感字段/Label 权限不足
    if "LABEL" in err.upper() or "sensitive label" in err or "NO privilege" in err:
        # 提取受限字段
        restricted = []
        m = re.search(r"access columns:\s*([^.]+)", err)
        if m:
            restricted = [c.strip() for c in m.group(1).split(",") if c.strip()]

        print(f'\n[sample] ❌ 权限不足（敏感字段 Label 拒绝）')
        if restricted:
            print(f'[sample]    受限字段: {", ".join(restricted[:10])}' +
                  (f' ... 共 {len(restricted)} 个' if len(restricted) > 10 else ''))
        print(f'\n[sample] 下一步可选：')

        apply_path = _apply_script_path()
        if apply_path:
            # 公有云：security-center 模块可用
            print(f'  1. 申请表权限：apply_resource_access.py \\')
            print(f'        --resource-type MaxComputeTable \\')
            print(f'        --project {database} \\')
            print(f'        --table {table_name} \\')
            if target_pid:
                print(f'        --workspace-id {target_pid} \\')
            print(f'        --grantee-id <你的 baseId> --reason "<用途>"')
        else:
            # 弹内：security-center 模块不在 dist 中
            print(f'  1. 弹内权限申请：本环境未部署 apply_resource_access.py（security-center 模块）')
            print(f'     → DataWorks 控制台 → 安全中心 → 数据访问申请，搜表 "{database}.{table_name}"')
            print(f'     → 或联系表 owner / 工作空间管理员授权（用 search_table.py "{database}.{table_name}" 查 owner）')
        print(f'  2. 换数据源（如有 PROD 权限）：sample_table.py "{database}.{table_name}" --env PROD')
        print(f'  3. 只看非敏感字段：先看 label: query_columns.py "{database}.{table_name}"，再 --columns 指定')
        return

    # 无分区数据
    if "分区" in err or "partition" in err.lower():
        print(f'\n[sample] 分区相关错误，尝试手动指定分区：')
        print(f'[sample]   sample_table.py "{database}.{table_name}" --where "ds=20260101"')
        return

    # 其他错误
    print(f'\n[sample] 其他错误排查：')
    print(f'  - 改手写 SQL：execute_sql.py "<SQL>" --datasource-code <code>')
    print(f'  - 查字段: query_columns.py "{database}.{table_name}"')


def _resolve_datasource(client, project_id, prefer_env=None):
    """自动选一个 MaxCompute 数据源

    策略：默认 DEV（安全路径，只读 SQL 不影响生产）；显式 --env PROD 才切 PROD。
    权限不足时由 apply_resource_access.py 链路处理（不要通过换数据源绕权限）。

    返回 (datasource_code, env)，找不到返回 (None, None)。
    """
    from list_datasource_da import discover_datasources
    try:
        datasources = discover_datasources(client, project_id, engine_filter="MAX_COMPUTE")
    except Exception as e:
        print(f"[sample] 数据源发现失败: {e}", file=sys.stderr)
        return None, None

    if not datasources:
        return None, None

    target_env = prefer_env if prefer_env in ("DEV", "PROD") else "DEV"

    primary = [d for d in datasources if d.get("env") == target_env]
    if primary:
        return primary[0]["datasource_code"], target_env

    fallback = [d for d in datasources if d.get("env") != target_env]
    if fallback:
        chosen = fallback[0]
        print(f"[sample] 未找到 {target_env} 环境的 MaxCompute 数据源，回退 {chosen.get('env')}")
        return chosen["datasource_code"], chosen.get("env", "")

    return None, None


def _build_sample_sql(database, table_name, columns, partition_cols,
                      limit, user_where=None, user_columns=None):
    """拼装 SELECT SQL：自动补分区条件 + LIMIT

    partition_cols: 分区字段名列表（按顺序）。单分区/双分区各自处理。
    """
    # 字段选择
    if user_columns:
        sel = ", ".join(user_columns)
    else:
        # 默认全字段（敏感字段由服务端拒绝，错误时提示用户用 --columns）
        sel = "*"

    where_parts = []
    full_name = f"{database}.{table_name}"

    # 分区条件：单分区用 MAX_PT；双分区 (ds, region) 特殊处理
    if partition_cols and not user_where:
        if len(partition_cols) == 1:
            where_parts.append(f"{partition_cols[0]} = MAX_PT('{full_name}')")
        elif len(partition_cols) == 2:
            p1, p2 = partition_cols
            where_parts.append(f"{p1} = MAX_PT('{full_name}')")
            # 双分区的第二维：子查询拿最新分区下最后一个值
            where_parts.append(
                f"{p2} = (SELECT MAX({p2}) FROM {full_name} "
                f"WHERE {p1} = MAX_PT('{full_name}'))"
            )
        else:
            # 3+ 分区少见，只处理第一维避免扫全表
            where_parts.append(f"{partition_cols[0]} = MAX_PT('{full_name}')")

    if user_where:
        where_parts.append(user_where)

    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    return f"SELECT {sel} FROM {full_name} {where_clause} LIMIT {limit}".strip()


def main():
    parser = argparse.ArgumentParser(
        description="表数据采样 — 一条命令看表前 N 行",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("keyword", help="表名关键字（支持 '项目.表名' 格式自动拆分）")
    parser.add_argument("--project", help="按项目名过滤（对应 databaseName）")
    parser.add_argument("--project-id", type=int, help="按项目数字 ID 过滤")
    parser.add_argument("-n", "--limit", type=int, default=10, help="采样行数（默认 10）")
    parser.add_argument("--columns", help="指定字段，逗号分隔；不传默认 SELECT *")
    parser.add_argument("--where", dest="where", help="额外过滤条件（覆盖自动分区条件）")
    parser.add_argument("--datasource-code", dest="datasource_code",
                        help="直接指定数据源 code；不传则自动选 DEV MaxCompute（安全默认）")
    parser.add_argument("--env", choices=["DEV", "PROD"], default=None,
                        help="强制指定数据源环境（默认 DEV；权限不足时申请权限，不通过切 PROD 绕过）")
    args = parser.parse_args()

    keyword = args.keyword
    project = args.project
    if not project and "." in keyword:
        parts = keyword.split(".", 1)
        project = parts[0]
        keyword = parts[1]

    telemetry_start("sample_table.py", module="sql-execution",
                    keyword=keyword, limit=args.limit)

    client = BFFClient(quiet=True)

    # 1. 搜索表（workspace 级消歧交给 resolve_table_with_workspace）
    from bff_client import resolve_table_with_workspace
    print(f"[sample] 搜索表: {keyword} ...")
    try:
        table = resolve_table_with_workspace(
            client, keyword, project=project, project_id=args.project_id,
            tag="[sample]")
    except ValueError as e:
        print(str(e), file=sys.stderr)
        telemetry_fail("sample_table.py", "sql-execution", 1, error=str(e)[:100])
        sys.exit(1)

    table_name = table.get("name", keyword)
    database = table.get("databaseName", "?")
    entity_type = table.get("entityType", "")

    if entity_type and "maxcompute" not in entity_type.lower() and "odps" not in entity_type.lower():
        print(f"[sample] ⚠️ 非 MaxCompute 表（entityType={entity_type}），分区/MAX_PT 语法可能不适用")

    # 2. 获取字段 + 分区键
    table_id = table.get("metaEntityId")
    if not table_id:
        qn = table.get("qualifiedName", "")
        if qn:
            parts = qn.split(".")
            table_id = parts[0] + ":::" + "::".join(parts[1:])

    partition_cols = []
    column_names = []
    if table_id:
        try:
            columns = client.load("listColumns", tableId=table_id) or []
            seen = set()
            for c in sorted(columns, key=lambda x: x.get("position") or 999):
                n = c.get("name")
                if not n or n in seen:
                    continue
                seen.add(n)
                column_names.append(n)
                if c.get("partitionKey"):
                    partition_cols.append(n)
        except Exception as e:
            print(f"[sample] listColumns 失败（将尝试无分区条件）: {e}", file=sys.stderr)

    print(f"[sample] 表: {database}.{table_name} | {len(column_names)} 字段 | 分区: {partition_cols or '无'}")

    # 3. 解析 --columns
    user_cols = None
    if args.columns:
        user_cols = [c.strip() for c in args.columns.split(",") if c.strip()]

    # 4. 拼 SQL
    sql = _build_sample_sql(database, table_name, column_names, partition_cols,
                            args.limit, user_where=args.where, user_columns=user_cols)
    print(f"[sample] SQL: {sql}")

    # 5. 数据源
    datasource_code = args.datasource_code
    if not datasource_code:
        # 需要 projectId 才能查数据源。优先用 table 的 projectId，否则用 args
        target_pid = args.project_id or table.get("projectId")
        if not target_pid:
            # 兜底：根据 database 名查 projectId
            try:
                projects = client.load("ListProjects", pageSize=100) or []
                for p in projects:
                    if (p.get("projectName") or "").lower() == database.lower():
                        target_pid = p.get("projectId")
                        break
            except Exception:
                pass

        if not target_pid:
            print(f"[sample] 无法确定工作空间 ID，请显式传 --project-id 或 --datasource-code", file=sys.stderr)
            telemetry_fail("sample_table.py", "sql-execution", 1, error="no_project_id")
            sys.exit(1)

        env_hint = args.env or "DEV"
        print(f"[sample] 自动发现数据源 (projectId={target_pid}, env={env_hint}) ...")
        datasource_code, env = _resolve_datasource(
            client, target_pid, prefer_env=args.env)
        if not datasource_code:
            # 先判断是不是跨工作空间（403 权限），给定向引导而不是通用兜底
            current_ws = _current_session_workspace()
            is_cross_ws = current_ws and str(current_ws) != str(target_pid)
            print(file=sys.stderr)
            if is_cross_ws:
                print(f"[sample] ❌ 跨工作空间取样不可行", file=sys.stderr)
                print(f"[sample]    目标表:    {database}.{table_name} (workspace {target_pid})", file=sys.stderr)
                print(f"[sample]    当前会话:  workspace {current_ws}", file=sys.stderr)
                print(f"[sample]    你不是 workspace {target_pid} 的成员，无法调度该工作空间的计算资源。", file=sys.stderr)
                print(f"[sample] ⚠️ 不要继续猜 datasource-code（_ODPS / dw_odps 等不会生效）", file=sys.stderr)
                print(f"[sample] 下一步二选一：", file=sys.stderr)
                apply_path = _apply_script_path()
                if apply_path:
                    print(f"  1. 申请权限：apply_resource_access.py --resource-type MaxComputeTable --project {database} --table {table_name} --workspace-id {target_pid} --grantee-id <你的 baseId> --reason \"<用途>\"", file=sys.stderr)
                else:
                    print(f"  1. 弹内控制台 → 安全中心 → 数据访问申请，搜表 \"{database}.{table_name}\"", file=sys.stderr)
                print(f"  2. 告知用户："\
                      f"此表归 workspace {target_pid}，当前会话在 workspace {current_ws}，"\
                      f"需切到前者或提交权限申请后重试", file=sys.stderr)
            else:
                print(f"[sample] 未找到 MaxCompute 数据源 (projectId={target_pid})", file=sys.stderr)
                print(f"[sample] → 手动列数据源: list_datasource_da.py --project-id {target_pid}", file=sys.stderr)
            telemetry_fail("sample_table.py", "sql-execution", 1,
                          error="cross_workspace" if is_cross_ws else "no_datasource")
            sys.exit(1)
        print(f"[sample] 已选数据源: {datasource_code} ({env})")

    # 6. 执行（复用 execute_sql.execute_readonly）
    from execute_sql import execute_readonly
    try:
        rows = execute_readonly(sql, datasource_code=datasource_code, timeout=180)
    except SystemExit:
        # 失败时读 tool_result 判断错误类型，输出下一步引导
        _print_failure_next_steps(database, table_name, target_pid=args.project_id or table.get("projectId"))
        raise

    # 7. 下一步引导
    print(f"\n[sample] 采样完成。结果已灌入 DuckDB（表名见上方 [xxx_rN_cN] 标签）")
    print(f"[sample] → 想聚合：client.query('SELECT ... FROM <DuckDB表名>') 或在 DuckDB CLI 里查")
    print(f"[sample] → 字段画像：profile_column.py \"{database}.{table_name}\" --columns <col1,col2>")

    save_tool_result("sample_table", {
        "database": database,
        "table_name": table_name,
        "sql": sql,
        "limit": args.limit,
        "datasource_code": datasource_code,
        "row_count": len(rows) if rows else 0,
    })

    telemetry_end(result={"row_count": len(rows) if rows else 0})


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        telemetry_fail("sample_table.py", "sql-execution", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
