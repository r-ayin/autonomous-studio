#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多类型并行搜表工具 — 关键字搜索 + 多维度过滤

两种模式：
  关键字模式（精确定位）：
    python search_table.py "表名"
    python search_table.py "表名" --project 项目名
    python search_table.py "项目.表名"              # 自动拆分

  过滤模式（列出匹配）：
    python search_table.py --owner self                            # 我拥有的表
    python search_table.py --owner 083361                          # 某人拥有的表
    python search_table.py --owner self --workspace autotest       # 我在某空间的表
    python search_table.py --owner self "dim_"                     # 我拥有的、含 dim_ 的表
    python search_table.py --workspace autotest --modified-after 2026-04-01
    python search_table.py --owner self --sort gmtModified --order desc --limit 50
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from bff_client import BFFClient, save_tool_result
from telemetry import telemetry_start, telemetry_end, telemetry_fail

ENTITY_TYPES = ["maxcompute-table", "dlf-table"]
_SEARCH_TABLES_MAX_OFFSET = 5000  # searchTables 服务端 offset 上限: (pageNum-1)*pageSize <= 5000


def search_all_types(client, keyword, page_size=20, max_pages=5):
    """并行搜索所有 entityType，返回合并结果

    searchTables 按相关度排序，精确匹配通常在第 1 页。
    默认 max_pages=5（pageSize=20 × 5 = 100 条/类型）足够覆盖同名表 + 模糊候选。
    max_offset 作为兜底安全网，防止 caller 传大 max_pages 时超出服务端限制。
    """
    def _search(entity_type):
        try:
            return client.load("searchTables", keyword=keyword,
                               entityType=entity_type, pageSize=page_size,
                               max_pages=max_pages,
                               max_offset=_SEARCH_TABLES_MAX_OFFSET)
        except Exception as e:
            print(f"[search_table] searchTables({entity_type}) error: {e}", file=sys.stderr)
            return []

    with ThreadPoolExecutor(max_workers=len(ENTITY_TYPES)) as executor:
        results = list(executor.map(_search, ENTITY_TYPES))

    all_tables = []
    for tables in results:
        if tables:
            all_tables.extend(tables)
    return all_tables


# ─── 过滤模式 ───────────────────────────────────────────────────


def _parse_date_to_ms(date_str_or_dt):
    """YYYY-MM-DD 字符串 或 datetime → 毫秒时间戳"""
    if isinstance(date_str_or_dt, datetime):
        return int(date_str_or_dt.timestamp() * 1000)
    dt = datetime.strptime(date_str_or_dt, "%Y-%m-%d")
    return int(dt.timestamp() * 1000)


def _parse_since(s):
    """解析 --since 快捷：7d → 7 天前，24h → 24 小时前，YYYY-MM-DD → 该日期。
    返回可被 _parse_date_to_ms 消费的值（datetime 或 YYYY-MM-DD 字符串），保留小时精度。"""
    from datetime import timedelta
    s = s.strip()
    now = datetime.now()
    if s.endswith("d") and s[:-1].isdigit():
        return now - timedelta(days=int(s[:-1]))
    if s.endswith("h") and s[:-1].isdigit():
        return now - timedelta(hours=int(s[:-1]))
    if s.isdigit():  # 纯数字按天
        return now - timedelta(days=int(s))
    # 兜底：原样当日期字符串（YYYY-MM-DD）
    return s


def _build_filter_params(args, owner_id):
    """从 CLI args 构造 searchTables API 参数

    遵循 NRTP id=2096 的参数透传规则：
      - baseId/operator 由后端自动注入，不要传
      - enableNlSearch 硬编码 false，不要传
      - useTypes/creatorBaseId 是 datastudio 专用，不要传
    """
    params = {
        "entityType": args.type,
        "pageSize": args.limit,
        "pageNum": args.page,
        "keyword": args.keyword or "",
    }
    if owner_id:
        params["owners"] = json.dumps([str(owner_id)])
    if args.workspace:
        # databaseGuids 格式: ["{type_prefix}.{workspace_name}"]
        type_prefix = args.type.split("-")[0]  # odps-table → odps
        params["databaseGuids"] = json.dumps([f"{type_prefix}.{args.workspace}"])
    if args.project_id:
        params["projectIds"] = json.dumps([str(args.project_id)])
    if args.env:
        envs = [e.strip() for e in args.env.split(",")]
        params["envTypes"] = json.dumps(envs)
    if args.modified_after:
        params["gmtModifiedFrom"] = _parse_date_to_ms(args.modified_after)
    if args.modified_before:
        params["gmtModifiedTo"] = _parse_date_to_ms(args.modified_before)
    if args.sort:
        params["sortField"] = args.sort
    if args.order:
        params["sortOrder"] = args.order
    return params


def _resolve_owner_id(client, owner_arg):
    """解析 --owner 参数：'self' → 当前用户 baseId，否则原样返回"""
    if not owner_arg:
        return None
    if owner_arg == "self":
        return client.get_my_base_id()
    return owner_arg


def _format_filter_summary(tables, args, owner_id):
    """构造过滤模式的 stdout 输出"""
    filter_parts = []
    if owner_id:
        label = "我自己" if args.owner == "self" else owner_id
        filter_parts.append(f"owner={label}")
    if args.workspace:
        filter_parts.append(f"workspace={args.workspace}")
    if args.project_id:
        filter_parts.append(f"projectId={args.project_id}")
    if args.env:
        filter_parts.append(f"env={args.env}")
    if args.modified_after:
        ma = args.modified_after
        if isinstance(ma, datetime):
            ma = ma.strftime("%Y-%m-%d %H:%M")
        filter_parts.append(f"after={ma}")
    if args.modified_before:
        filter_parts.append(f"before={args.modified_before}")
    if args.keyword:
        filter_parts.append(f"keyword={args.keyword}")
    filter_parts.append(f"type={args.type}")
    return " | ".join(filter_parts)


def run_filter_mode(client, args):
    """过滤模式：按多维度条件列出匹配的表 / 聚合分布"""
    owner_id = _resolve_owner_id(client, args.owner)
    params = _build_filter_params(args, owner_id)

    summary = _format_filter_summary(None, args, owner_id)
    print(f"[search_table] 过滤搜索: {summary}")

    # searchTables 服务端 offset 硬上限 200（实测 offset>=200 返回空，totalNum=10000 是 ES 虚假 sentinel）。
    # group-by 只能在前 200 条样本上算分布，**不是工作空间全量**，必须显式提示。
    if args.group_by:
        params["pageSize"] = 200  # 一次拿满服务端硬上限
        tables = client.load("searchTables", max_pages=1, **params)
    else:
        tables = client.load("searchTables", max_pages=1, **params)
    if not tables:
        print(f"\n[search_table] 未找到匹配表")
        save_tool_result("search_table", {
            "mode": "filter",
            "filters": {k: v for k, v in vars(args).items() if v is not None},
            "owner_id": owner_id,
            "result_count": 0,
        })
        return

    # group-by 模式输出分布，不列明细
    if args.group_by:
        _print_group_by(tables, args.group_by, args, owner_id)
        telemetry_end(result={"mode": "group-by", "by": args.group_by, "count": len(tables)})
        save_tool_result("search_table", {
            "mode": "group-by",
            "by": args.group_by,
            "total": len(tables),
            "filters": {k: v for k, v in vars(args).items() if v is not None},
        })
        return

    # 按 databaseName（工作空间）分组
    by_db = {}
    for t in tables:
        db = t.get("databaseName", "?")
        by_db.setdefault(db, []).append(t)

    print(f"\n找到 {len(tables)} 张表，分布在 {len(by_db)} 个工作空间:")
    for db, db_tables in sorted(by_db.items(), key=lambda x: -len(x[1])):
        print(f"\n  📁 {db} ({len(db_tables)} 张):")
        for t in db_tables:
            name = t.get("name", "?")
            owner = t.get("ownerName") or t.get("ownerId") or "?"
            comment = (t.get("comment") or "")[:40]
            print(f"    - {name}  [owner={owner}]  {comment}")

    print(f"\n→ 看某张表详情: search_table.py \"<表名>\"")

    telemetry_end(result={"mode": "filter", "count": len(tables)})
    save_tool_result("search_table", {
        "mode": "filter",
        "filters": {k: v for k, v in vars(args).items() if v is not None},
        "owner_id": owner_id,
        "result_count": len(tables),
        "by_workspace": {db: len(ts) for db, ts in by_db.items()},
        "tables": [{
            "name": t.get("name"),
            "databaseName": t.get("databaseName"),
            "entityType": t.get("entityType"),
            "ownerId": t.get("ownerId"),
            "ownerName": t.get("ownerName"),
            "qualifiedName": t.get("qualifiedName"),
        } for t in tables[:50]],
    })


def _print_group_by(tables, dim, args, owner_id):
    """按 owner / workspace / type 做分布统计"""
    from collections import Counter
    counter = Counter()
    label_map = {}  # key(login/id) → display name
    for t in tables:
        if dim == "owner":
            key = t.get("ownerId") or ""
            label = t.get("ownerName") or key
        elif dim == "workspace":
            key = t.get("databaseName") or ""
            label = key
        else:  # type
            key = t.get("entityType") or ""
            label = key
        if not key:
            continue
        counter[key] += 1
        if label and key not in label_map:
            label_map[key] = label
    total = sum(counter.values())
    role = {"owner": "owner（表负责人）", "workspace": "databaseName（工作空间）",
            "type": "entityType（表类型）"}[dim]
    # 关键：searchTables 服务端 offset cap 200，此样本 ≤ 200 时是全量，否则只是前 200 样本
    hit_cap = total >= 200
    cap_note = " ⚠️ 基于前 200 条样本（searchTables 服务端 offset 上限），非工作空间全量分布；如需真全量用 listTablesByDB" if hit_cap else ""
    print(f"\n共 {total} 张表 — 按 {role} 分布{cap_note}：\n")
    width = max((len(label_map.get(k, k)) for k in counter), default=4)
    print(f"  {'排名':<4} {'名称'.ljust(width)}  {'主键':<16} {'数量':>6} {'占比':>7}")
    for i, (k, cnt) in enumerate(counter.most_common(), 1):
        pct = cnt * 100.0 / total
        print(f"  {i:<4} {label_map.get(k, k).ljust(width)}  {k[:16]:<16} {cnt:>6} {pct:>6.1f}%")
    print(f"\n  合计: {total}")
    print(f"\n→ 看明细: search_table.py（去掉 --group-by）")


def find_table(client, keyword, project=None):
    """搜索表并获取完整详情（含 projectId、metaEntityId）

    纯元数据层：按 databaseName 过滤，不涉及 DataWorks workspace 概念。
    workspace 级的启发式（如"prod 优先"）由上层脚本用 runtime.resolve_table_with_workspace 处理。

    流程：并行搜索所有 entityType → 精确匹配 → getDetail 补全信息

    Args:
        project: 按 databaseName 过滤（如 "dataworks_analyze"），多个同名表时用此参数消歧

    Returns:
        dict: 表完整信息，含 databaseName、metaEntityId、qualifiedName 等

    Raises:
        ValueError: 未找到匹配的表，或多个同名表未指定 project
    """
    tables = search_all_types(client, keyword)
    if not tables:
        raise ValueError(f"未找到表: {keyword}")

    # 精确匹配表名
    exact = [t for t in tables if t.get("name", "").lower() == keyword.lower()]
    if not exact:
        exact = [tables[0]]

    # 按 databaseName 过滤
    if project:
        filtered = [t for t in exact if t.get("databaseName", "").lower() == project.lower()]
        if filtered:
            exact = filtered
        else:
            raise ValueError(f"未在数据库 {project} 中找到表: {keyword}")

    # 多个同名表在不同数据库，必须显式指定
    if len(exact) > 1:
        lines = [f"找到 {len(exact)} 个同名表，请用 --project <databaseName> 指定:"]
        for t in exact:
            db = t.get("databaseName", "?")
            lines.append(f"  {db}.{t.get('name', '?')}")
        raise ValueError("\n".join(lines))

    table = exact[0]

    # 通过 getDetail 补全 projectId、metaEntityId 等
    entity_guid = table.get("entityGuid")
    if entity_guid:
        try:
            detail = client.load("getDetail", entityType="odps-table", entityGuid=entity_guid)
            if isinstance(detail, dict):
                table.update(detail)
        except Exception:
            pass  # getDetail 失败时用 searchTables 的基础信息

    return table


def main():
    parser = argparse.ArgumentParser(
        description="多类型并行搜表工具 — 关键字搜索 + 多维度过滤",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("keyword", nargs="?", default="",
                        help="表名关键字（支持 '项目.表名' 格式自动拆分；可与 --owner 等过滤组合）")
    parser.add_argument("--project", help="按项目名过滤（对应 databaseName，本地过滤）")

    # ── 过滤模式参数 ──
    parser.add_argument("--owner", help='按 owner 过滤："self" 表示当前用户，或传 baseId（如 083361）')
    parser.add_argument("--workspace", help="按工作空间名过滤（自动加 type 前缀）")
    parser.add_argument("--project-id", help="按工作空间数字 ID 过滤（projectIds 参数）")
    parser.add_argument("--type", default="odps-table",
                        help="entity 类型（默认 odps-table，可选 maxcompute-table / dlf-table 等）")
    parser.add_argument("--env", help="环境过滤，逗号分隔，如 product,dev")
    parser.add_argument("--modified-after", help="修改时间起始 YYYY-MM-DD")
    parser.add_argument("--modified-before", help="修改时间截止 YYYY-MM-DD")
    parser.add_argument("--since", help='时间窗简写: 7d(最近 7 天) / 24h / YYYY-MM-DD；等价于 --modified-after')
    parser.add_argument("--sort", help="排序字段：accessTimes(热度) / visitNum / gmtModified / dataSize / gmtCreate / lastModifyTime / lifeCycleTime")
    parser.add_argument("--order", choices=["asc", "desc"], default="desc")
    parser.add_argument("--limit", type=int, default=20, help="每页数量（默认 20）")
    parser.add_argument("--page", type=int, default=1, help="页码（默认 1）")
    parser.add_argument("--group-by", choices=["owner", "workspace", "type"],
                        help="聚合模式：按 owner / workspace / type 分布（替代明细展示）")

    args = parser.parse_args()

    # --since 快捷语法 → --modified-after
    if args.since and not args.modified_after:
        args.modified_after = _parse_since(args.since)

    # 判断模式：有任一过滤参数 → 过滤模式；只有 keyword → 关键字模式
    is_filter_mode = bool(
        args.owner or args.workspace or args.project_id or args.env
        or args.modified_after or args.modified_before or args.sort
        or args.group_by
    )

    if not args.keyword and not is_filter_mode:
        parser.error("需要 keyword 或至少一个过滤参数（--owner / --workspace 等）")

    telemetry_start("search_table.py", module="discovery", keyword=args.keyword)

    if is_filter_mode:
        client = BFFClient(quiet=True)
        run_filter_mode(client, args)
        return

    # ── 关键字模式（原有逻辑） ──
    keyword = args.keyword
    project = args.project

    # 自动拆分 "项目.表名" 格式
    if not project and "." in keyword:
        parts = keyword.split(".", 1)
        project = parts[0]
        keyword = parts[1]

    client = BFFClient(quiet=True)

    # 并行搜索所有类型
    print(f"搜索表: {keyword} ...")
    all_tables = search_all_types(client, keyword)

    # 精确匹配表名
    exact = [t for t in all_tables if t.get("name", "").lower() == keyword.lower()]

    # 按 project 过滤
    if project:
        exact = [t for t in exact if t.get("databaseName", "").lower() == project.lower()]

    if not exact:
        # fallback: 模糊匹配
        fuzzy = [t for t in all_tables if keyword.lower() in t.get("name", "").lower()]
        if project:
            fuzzy = [t for t in fuzzy if t.get("databaseName", "").lower() == project.lower()]
        if fuzzy:
            print(f"\n未找到精确匹配，模糊匹配到 {len(fuzzy)} 个:")
            for t in fuzzy[:10]:
                et = t.get("entityType", "?")
                db = t.get("databaseName", "?")
                name = t.get("name", "?")
                comment = (t.get("comment") or "")[:40]
                print(f"  {et:<18} | {db}.{name} | {comment}")
            # 恢复命令：用最接近的模糊匹配重试
            best = fuzzy[0]
            best_name = best.get("name", "")
            best_db = best.get("databaseName", "")
            print(f"\n→ search_table.py \"{best_db}.{best_name}\"")
            print(f"→ search_nodes.py \"{best_db}.{best_name}\"")
            print(f"→ identify.py \"{keyword}\"  （不是表？试试按节点查）")
        else:
            print(f"\n未找到匹配表: {keyword}" + (f" (项目: {project})" if project else ""))
            print(f"\n→ search_table.py \"<换个关键字重试>\"")
            print(f"→ identify.py \"{keyword}\"  （不是表？试试按节点查）")
        save_tool_result("search_table", {
            "keyword": keyword,
            "project": project,
            "exact_matches": [],
            "fuzzy_matches": [{"name": t.get("name"), "databaseName": t.get("databaseName"),
                               "entityType": t.get("entityType")} for t in (fuzzy if not exact else [])[:10]],
        })
        sys.exit(1)

    # 按类型统计
    type_counts = {}
    for t in exact:
        et = t.get("entityType", "unknown")
        type_counts[et] = type_counts.get(et, 0) + 1
    type_summary = ", ".join(f"{k}: {v}" for k, v in type_counts.items())

    print(f"\n找到 {len(exact)} 个匹配（{type_summary}）:")
    for t in exact:
        et = t.get("entityType", "?")
        db = t.get("databaseName", "?")
        name = t.get("name", "?")
        guid = t.get("entityGuid", "?")
        comment = (t.get("comment") or "")[:40]
        size = t.get("dataSize")
        size_str = f" | {size:,}B" if size else ""
        print(f"  {et:<18} | {db}.{name} | {comment}{size_str}")

    # 下一步提示
    if len(exact) == 1:
        t = exact[0]
        guid = t.get("entityGuid", "")
        db = t.get("databaseName", "?")
        name = t.get("name", "?")
        if guid:
            print(f"\n→ 查字段列表: python query_columns.py \"{db}.{name}\"")
            print(f"→ 查完整详情: client.load(\"getDetail\", entityType=\"odps-table\", entityGuid=\"{guid}\")")
    else:
        print(f"\n→ 多个匹配，请指定项目: python search_table.py \"{keyword}\" --project <项目名>")
        print(f"→ 指定项目后查字段: python query_columns.py \"{keyword}\" --project <项目名>")
        print(f"→ 或查详情: client.load(\"getDetail\", entityType=\"odps-table\", entityGuid=<entityGuid>)")

    telemetry_end(result={"exact_count": len(exact)})
    # 结构化结果
    save_tool_result("search_table", {
        "keyword": keyword,
        "project": project,
        "exact_matches": [{
            "name": t.get("name"),
            "databaseName": t.get("databaseName"),
            "entityType": t.get("entityType"),
            "entityGuid": t.get("entityGuid"),
            "qualifiedName": t.get("qualifiedName"),
            "comment": t.get("comment"),
            "dataSize": t.get("dataSize"),
            "ownerName": t.get("ownerName"),
            "partitioned": t.get("partitioned"),
        } for t in exact],
    })


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("search_table.py", "discovery", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("search_table.py", "discovery", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
