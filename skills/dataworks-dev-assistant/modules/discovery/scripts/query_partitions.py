#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""表分区概览工具 — 一条命令查看历史产出全貌

用法:
    python query_partitions.py "表名"
    python query_partitions.py "表名" --project 项目名
    python query_partitions.py "项目.表名"

功能:
    搜索表 → 加载全量分区 → DuckDB 分析产出概览

输出示例:
    表: m_task_sql (项目: dataworks_analyze)

    分区概览:
      总分区数: 8,369
      时间范围: 20240101 ~ 20260330 (710 天)
      维度: region (31 个值)

    最近 14 天产出:
      20260330 | 27 分区 (27 region)
      20260329 | 27 分区 (27 region)
      ...

    各 region 最新分区:
      cn-hangzhou   20260330  ✅
      group         20250803  ⚠️ 停产 (落后 239 天)
"""

import sys
import re
import argparse

from bff_client import BFFClient, save_tool_result
from telemetry import telemetry_start, telemetry_end, telemetry_fail

from search_table import find_table


def parse_partition_date(partition_str):
    """从分区名提取日期 YYYYMMDD"""
    if not partition_str:
        return None
    m = re.search(r"(\d{8})", partition_str)
    if m:
        return m.group(1)
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", partition_str)
    if m:
        return m.group(1) + m.group(2) + m.group(3)
    return None


def analyze_single_dim(partitions):
    """单维分区（如 ds=20240101）：按日期统计"""
    dates = []
    for p in partitions:
        d = parse_partition_date(p.get("name", ""))
        if d:
            dates.append(d)

    if not dates:
        return None

    dates.sort()
    return {
        "total": len(partitions),
        "earliest": dates[0],
        "latest": dates[-1],
        "distinct_days": len(set(dates)),
        "dimensions": [],
    }


def analyze_with_duckdb(client, table_id, table_name, loader):
    """多维分区：用 DuckDB 做完整分析"""
    from duckdb_loader import DuckDBLoader

    partitions = client.load("ListPartitions", tableId=table_id)
    if not partitions:
        return None, []

    # 检测维度结构
    sample = partitions[0].get("name", "")
    dims = []
    if re.match(r'^[a-zA-Z_]+=.+', sample):
        for part in sample.split("/"):
            if "=" in part:
                key = part.split("=", 1)[0].strip()
                if key:
                    dims.append(key)

    time_dims = [d for d in dims if d in ("ds", "dt", "pt", "bizdate")]
    value_dims = [d for d in dims if d not in time_dims]
    ref_time = time_dims[0] if time_dims else None

    if not dims or not ref_time:
        # 单维或无法解析，fallback
        info = analyze_single_dim(partitions)
        return info, partitions

    # DuckDB 分析
    if not loader:
        loader = DuckDBLoader()

    tbl = loader.load(f"_partitions_{table_name}", partitions)
    if not tbl:
        info = analyze_single_dim(partitions)
        return info, partitions

    # 创建展开视图
    view = f"{tbl}_expanded"
    select_parts = [f'"{tbl}".*']
    for dim in dims:
        select_parts.append(
            f"regexp_extract(\"name\", '{re.escape(dim)}=([^/]*)', 1) AS \"{dim}\""
        )
    loader.db.execute(f'DROP VIEW IF EXISTS "{view}"')
    loader.db.execute(
        f'CREATE VIEW "{view}" AS SELECT {", ".join(select_parts)} FROM "{tbl}"'
    )

    # 基础统计
    rows = loader.fetch(f'''
        SELECT
            COUNT(*) as total,
            MIN("{ref_time}") as earliest,
            MAX("{ref_time}") as latest,
            COUNT(DISTINCT "{ref_time}") as distinct_days
        FROM "{view}"
        WHERE "{ref_time}" IS NOT NULL AND "{ref_time}" != ''
    ''')
    stats = rows[0] if rows else {}

    # 各维度值数
    dim_info = []
    for dim in value_dims:
        cnt_rows = loader.fetch(f'''
            SELECT COUNT(DISTINCT "{dim}") as cnt
            FROM "{view}"
            WHERE "{dim}" IS NOT NULL AND "{dim}" != ''
        ''')
        cnt = cnt_rows[0]["cnt"] if cnt_rows else 0
        dim_info.append({"name": dim, "distinct_values": cnt})

    # 最近 N 天产出趋势
    recent_rows = loader.fetch(f'''
        SELECT
            "{ref_time}" as date,
            COUNT(*) as partition_count
            {"".join(f', COUNT(DISTINCT "{d}") as "{d}_count"' for d in value_dims)}
        FROM "{view}"
        WHERE "{ref_time}" IS NOT NULL AND "{ref_time}" != ''
        GROUP BY "{ref_time}"
        ORDER BY "{ref_time}" DESC
        LIMIT 14
    ''')

    # 各维度值的最新分区
    dim_details = {}
    for dim in value_dims:
        detail_rows = loader.fetch(f'''
            SELECT
                "{dim}" as value,
                MAX("{ref_time}") as latest,
                COUNT(*) as count
            FROM "{view}"
            WHERE "{dim}" IS NOT NULL AND "{dim}" != ''
            GROUP BY "{dim}"
            ORDER BY latest DESC
        ''')
        dim_details[dim] = detail_rows or []

    info = {
        "total": stats.get("total", len(partitions)),
        "earliest": stats.get("earliest"),
        "latest": stats.get("latest"),
        "distinct_days": stats.get("distinct_days"),
        "dimensions": dim_info,
        "recent_trend": recent_rows or [],
        "dim_details": dim_details,
        "ref_time": ref_time,
        "value_dims": value_dims,
    }
    return info, partitions


def print_overview(table_name, database, info):
    """格式化输出分区概览"""
    if not info:
        print("\n无分区数据")
        return

    total = info.get("total", 0)
    earliest = info.get("earliest", "?")
    latest = info.get("latest", "?")
    days = info.get("distinct_days", 0)

    print(f"\n分区概览:")
    print(f"  总分区数: {total:,}")
    print(f"  时间范围: {earliest} ~ {latest} ({days} 天)")

    dims = info.get("dimensions", [])
    if dims:
        dim_str = ", ".join(f"{d['name']} ({d['distinct_values']} 个值)" for d in dims)
        print(f"  维度: {dim_str}")

    # 最近产出趋势
    recent = info.get("recent_trend", [])
    value_dims = info.get("value_dims", [])
    if recent:
        print(f"\n最近 {len(recent)} 天产出:")
        for r in recent:
            dim_parts = []
            for d in value_dims:
                cnt = r.get(f"{d}_count")
                if cnt is not None:
                    dim_parts.append(f"{cnt} {d}")
            dim_str = f" ({', '.join(dim_parts)})" if dim_parts else ""
            print(f"  {r['date']} | {r['partition_count']} 分区{dim_str}")

    # 各维度值详情
    dim_details = info.get("dim_details", {})
    for dim, rows in dim_details.items():
        if not rows:
            continue
        max_latest = rows[0]["latest"] if rows else None
        print(f"\n各 {dim} 最新分区:")
        stalled_count = 0
        for r in rows:
            val = r["value"]
            lat = r["latest"]
            if lat == max_latest:
                print(f"  {val:<24} {lat}  ✅")
            else:
                stalled_count += 1
                # 计算落后天数（粗略）
                try:
                    from datetime import datetime
                    d1 = datetime.strptime(str(max_latest), "%Y%m%d")
                    d2 = datetime.strptime(str(lat), "%Y%m%d")
                    gap = (d1 - d2).days
                    print(f"  {val:<24} {lat}  ⚠️ 停产 (落后 {gap} 天)")
                except (ValueError, TypeError):
                    print(f"  {val:<24} {lat}  ⚠️ 停产")
        if stalled_count > 0:
            print(f"  ({stalled_count} 个 {dim} 停产)")


# ─── 状态判断 ────────────────────────────────────────────────

def _print_assessment(info, table_name):
    """基于分区分析结果输出状态判断 + 关键发现 + 建议动作"""
    findings = []
    actions = []

    if not info:
        print(f"\n{'=' * 60}")
        print(f"【状态判断】🟡 注意：无分区数据，无法判断产出状态")
        print("【建议动作】")
        print(f"  1. 确认表是否为分区表")
        print(f"     → search_nodes.py \"{table_name}\"")
        return

    recent = info.get("recent_trend", [])
    latest = info.get("latest")
    dim_details = info.get("dim_details", {})

    # ── 判断维度 1：产出趋势（稳定/衰减/停产） ──
    trend_status = "stable"
    if recent and len(recent) >= 2:
        counts = [r.get("partition_count", 0) for r in recent]
        avg_recent_3 = sum(counts[:3]) / min(len(counts), 3) if counts else 0
        avg_older = sum(counts[3:]) / len(counts[3:]) if len(counts) > 3 else avg_recent_3
        if avg_recent_3 == 0:
            trend_status = "stopped"
        elif avg_older > 0 and avg_recent_3 < avg_older * 0.5:
            trend_status = "declining"

    # ── 判断维度 2：停产维度检测 ──
    stalled_dims = []
    for dim, rows in dim_details.items():
        if not rows:
            continue
        max_latest = rows[0].get("latest")
        for r in rows:
            if r.get("latest") != max_latest:
                stalled_dims.append({"dim": dim, "value": r["value"], "latest": r["latest"]})

    # ── 判断维度 3：最近14天产出是否有断档 ──
    gap_days = []
    if recent and len(recent) >= 2:
        dates_sorted = sorted([r.get("date", "") for r in recent if r.get("date")])
        for i in range(len(dates_sorted) - 1):
            try:
                from datetime import datetime
                d1 = datetime.strptime(str(dates_sorted[i + 1]), "%Y%m%d")
                d2 = datetime.strptime(str(dates_sorted[i]), "%Y%m%d")
                gap = (d2 - d1).days
                if gap > 1:
                    gap_days.append((dates_sorted[i + 1], dates_sorted[i], gap))
            except (ValueError, TypeError):
                pass

    # ── 综合严重度 ──
    if trend_status == "stopped" or len(stalled_dims) >= 3:
        severity_emoji = "🔴 严重"
    elif trend_status == "declining" or stalled_dims or gap_days:
        severity_emoji = "🟡 注意"
    else:
        severity_emoji = "🟢 正常"

    # ── 汇总 ──
    parts = []
    if trend_status == "stopped":
        parts.append("最近产出已停止")
    elif trend_status == "declining":
        parts.append("产出量呈衰减趋势")
    else:
        parts.append("产出稳定")
    if stalled_dims:
        parts.append(f"{len(stalled_dims)} 个维度值停产")
    if gap_days:
        parts.append(f"最近14天有 {len(gap_days)} 处断档")
    summary = "，".join(parts)

    print(f"\n{'=' * 60}")
    print(f"【状态判断】{severity_emoji}：{summary}")

    # ── 关键发现 ──
    if trend_status == "stopped":
        findings.append(f"最近 3 天产出分区数为 0，表可能已停止更新")
    elif trend_status == "declining":
        findings.append(f"最近 3 天产出量不足历史均值的 50%，产出在衰减")
    if stalled_dims:
        top = stalled_dims[:3]
        for s in top:
            findings.append(f"维度 {s['dim']}={s['value']} 停产（最新分区 {s['latest']}）")
    if gap_days:
        for start_d, end_d, gap in gap_days[:2]:
            findings.append(f"{start_d} ~ {end_d} 之间断档 {gap} 天")

    if findings:
        print("【关键发现】")
        for f in findings:
            print(f"  - {f}")

    # ── 建议动作 ──
    if trend_status in ("stopped", "declining"):
        actions.append(("定位产出任务，检查是否有失败或下线",
                        f"search_nodes.py \"{table_name}\" --with-instances"))
    if stalled_dims:
        actions.append((f"排查停产维度的产出任务",
                        f"search_nodes.py \"{table_name}\""))
    if not actions:
        actions.append(("查看产出任务运行情况",
                        f"search_nodes.py \"{table_name}\" --with-instances"))

    print("【建议动作】")
    for i, (desc, cmd) in enumerate(actions, 1):
        print(f"  {i}. {desc}")
        print(f"     → {cmd}")


def _fast_latest_partition(client, table_name, database, entity_guid):
    """快路径：/dma/listPartitions_2 单页取最新分区。不拉全量，不进 DuckDB。

    后端默认按 name.raw DESC 排序（实测，见 api-index.json caveat）。
    page 1 第一条 name 里的日期段即最新分区日期；多维度表 page 1 通常是同一日期的多个维度枚举。
    """
    resp = client.call_raw(
        "listPartitions_2",
        entityGuid=entity_guid,
        entityType="odps-table",
        pageNum=1,
        pageSize=20,
        keyword="",
    )
    if not client.is_success(resp):
        raise RuntimeError(f"listPartitions_2 调用失败: code={resp.get('code')} message={resp.get('message')}")

    rows = (resp.get("data") or {}).get("data") or []
    if not rows:
        print(f"\n表 {table_name} 无分区数据（可能是非分区表）")
        return None

    # 解析每行 name 的日期段
    parsed = []
    for r in rows:
        name = r.get("name", "")
        d = parse_partition_date(name)
        dims = {}
        for part in name.split("/"):
            if "=" in part:
                k, v = part.split("=", 1)
                dims[k.strip()] = v.strip()
        parsed.append({"name": name, "date": d, "dims": dims, "row": r})

    dated = [p for p in parsed if p["date"]]
    latest_date = max((p["date"] for p in dated), default=None)

    print(f"\n最新分区:")
    if not latest_date:
        # 无日期维度，直接输出 page 1 第一条
        first = parsed[0]
        print(f"  {first['name']}")
        return {"latest_name": first["name"], "latest_date": None, "dimensions": []}

    # 多维度：列出最新日期下 page 1 出现的所有维度组合（注意：不一定是全部，大表可能被 pageSize=20 截断）
    latest_rows = [p for p in parsed if p["date"] == latest_date]
    time_keys = {"ds", "dt", "pt", "bizdate"}
    value_dim_keys = sorted({k for p in latest_rows for k in p["dims"] if k not in time_keys})

    if not value_dim_keys:
        # 单维度表：最新分区只有一条
        print(f"  {latest_rows[0]['name']}")
    else:
        # 多维度表：展示最新日期的维度枚举
        truncated = len(latest_rows) == len(rows)  # page 1 全是同一日期，可能还有更多
        print(f"  日期: {latest_date}   维度: {', '.join(value_dim_keys)}   该日期枚举数: {len(latest_rows)}" + (" (page 1 已满，可能被截断)" if truncated else ""))
        for p in latest_rows[:10]:
            print(f"    - {p['name']}")
        if len(latest_rows) > 10:
            print(f"    ... 还有 {len(latest_rows) - 10} 个维度组合")

    # 只给结构引导；取样是独立意图，用户问"取样/看数据"时 agent 再走 sample_table / execute_sql
    qualified = f"{database}.{table_name}" if database else table_name
    sample = latest_rows[0]["dims"] if latest_rows else {}
    pred = next((f"{k}='{sample[k]}'" for k in ("pt", "ds", "dt", "bizdate") if k in sample), None)

    print("\n下一步")
    print(f"  → query_columns.py \"{qualified}\"")
    if pred:
        print(f"  最新分区 WHERE: {pred}")

    return {
        "latest_name": latest_rows[0]["name"],
        "latest_date": latest_date,
        "dimensions": value_dim_keys,
        "latest_count_on_page": len(latest_rows),
    }


def main():
    parser = argparse.ArgumentParser(
        description="表分区概览工具 — 查看历史产出全貌",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("keyword", help="表名关键字（支持 '项目.表名' 格式自动拆分）")
    parser.add_argument("--project", help="按项目名过滤（对应 databaseName）")
    parser.add_argument("--project-id", type=int,
                        help="按 DataWorks workspace ID 过滤（多同名表时启发式选 prod 数据库）")
    parser.add_argument("--latest-only", action="store_true",
                        help="快路径：只取最新分区日期（单次 GET listPartitions_2，不拉全量、不进 DuckDB）。"
                             "用户只问「最新分区是哪天 / 最新数据是几号 / 产出到几号了」时用。")
    args = parser.parse_args()

    keyword = args.keyword
    project = args.project
    if not project and "." in keyword:
        parts = keyword.split(".", 1)
        project = parts[0]
        keyword = parts[1]

    client = BFFClient(quiet=True)
    telemetry_start("query_partitions.py", module="discovery", keyword=keyword,
                    latest_only=args.latest_only)

    # 1. 搜索表（走上层启发式，支持 workspace 级消歧）
    from bff_client import resolve_table_with_workspace
    print(f"搜索表: {keyword} ...")
    try:
        table = resolve_table_with_workspace(
            client, keyword, project=project, project_id=args.project_id,
            tag="[partitions]")
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    table_name = table.get("name", keyword)
    database = table.get("databaseName", "?")
    entity_guid = table.get("entityGuid") or (f"odps.{database}.{table_name}" if database != "?" else None)

    print(f"表: {table_name} (项目: {database})")

    # 快路径：只要最新分区，直接走 listPartitions_2
    if args.latest_only:
        if not entity_guid:
            print("无法构造 entityGuid（缺少 database）", file=sys.stderr)
            sys.exit(1)
        result = _fast_latest_partition(client, table_name, database, entity_guid)
        telemetry_end(result={"latest": result.get("latest_date") if result else None,
                              "mode": "latest_only"})
        save_tool_result("query_partitions", {
            "table_name": table_name,
            "database": database,
            "entity_guid": entity_guid,
            "mode": "latest_only",
            "latest_name": result.get("latest_name") if result else None,
            "latest_date": result.get("latest_date") if result else None,
            "dimensions": result.get("dimensions", []) if result else [],
        })
        return

    # 慢路径：保留原有全量分析
    table_id = table.get("metaEntityId")
    if not table_id:
        qn = table.get("qualifiedName", "")
        if qn:
            parts = qn.split(".")
            table_id = parts[0] + ":::" + "::".join(parts[1:])
        else:
            print("无法获取 metaEntityId", file=sys.stderr)
            sys.exit(1)

    # 2. 加载分区 + DuckDB 分析
    from duckdb_loader import DuckDBLoader
    loader = client.loader or DuckDBLoader()

    info, _ = analyze_with_duckdb(client, table_id, table_name, loader)

    # 3. 输出
    print_overview(table_name, database, info)

    # 4. 状态判断
    _print_assessment(info, table_name)

    telemetry_end(result={"total_partitions": info.get("total", 0) if info else 0,
                          "latest": info.get("latest") if info else None})

    # 5. 结构化结果
    stalled_dims = [
        {"dimension": dim, "value": r["value"], "latest": r["latest"]}
        for dim, rows in (info.get("dim_details", {}) if info else {}).items()
        for r in rows
        if rows and r["latest"] != rows[0]["latest"]
    ]
    save_tool_result("query_partitions", {
        "table_name": table_name,
        "database": database,
        "table_id": table_id,
        "total_partitions": info.get("total", 0) if info else 0,
        "earliest": info.get("earliest") if info else None,
        "latest": info.get("latest") if info else None,
        "distinct_days": info.get("distinct_days") if info else None,
        "dimensions": info.get("dimensions", []) if info else [],
        "stalled_dims": stalled_dims,
        "stalled_dim_count": len(stalled_dims),
    })


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("query_partitions.py", "discovery", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("query_partitions.py", "discovery", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
