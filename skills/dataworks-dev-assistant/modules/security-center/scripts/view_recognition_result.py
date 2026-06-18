#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查看敏感数据识别结果（B 层：识别出的敏感字段清单）

返回每条字段的 sensitiveDataId / engineType / dbName / tableName / columnName / sensitiveTypeName / sensitiveLevelName。
支持 20 个维度过滤，首屏按 updatedTime desc 排序。

用法:
    python view_recognition_result.py                              # 全部前 50 条
    python view_recognition_result.py --engine ODPS.ODPS
    python view_recognition_result.py --project xx --db yy --table zz
    python view_recognition_result.py --sensitive-type 身份证,手机号   # 按敏感类型过滤
    python view_recognition_result.py --since 7d                    # 7 天内更新
    python view_recognition_result.py --limit 200
    python view_recognition_result.py --group-by sensitiveTypeName  # 按敏感类型分布

仅公有云。
"""

import argparse
import sys
from datetime import datetime, timedelta

from bff_client import BFFClient


def _fmt_ms(ms):
    if not ms:
        return ""
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(ms)


def _parse_since(s):
    if not s:
        return None
    s = s.strip()
    now = datetime.now()
    if s.endswith("d") and s[:-1].isdigit():
        return int((now - timedelta(days=int(s[:-1]))).timestamp() * 1000)
    if s.endswith("h") and s[:-1].isdigit():
        return int((now - timedelta(hours=int(s[:-1]))).timestamp() * 1000)
    if s.isdigit():
        return int((now - timedelta(days=int(s))).timestamp() * 1000)
    try:
        return int(datetime.strptime(s, "%Y-%m-%d").timestamp() * 1000)
    except ValueError:
        print(f"--since 解析失败: {s}", file=sys.stderr)
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description="查看识别出的敏感字段清单")
    p.add_argument("--engine", help="引擎类型：ODPS.ODPS / STARROCKS / DLF.LEGACY / HOLOGRES 等（支持逗号多值 → engineTypes）")
    p.add_argument("--project", help="按项目名过滤")
    p.add_argument("--instance", help="按 instanceId 过滤")
    p.add_argument("--cluster", help="按 clusterId 过滤（EMR 场景）")
    p.add_argument("--catalog", help="按 catalogName 过滤")
    p.add_argument("--db", help="按 dbName 过滤")
    p.add_argument("--schema", help="按 schemaName 过滤")
    p.add_argument("--table", help="按 tableName 过滤")
    p.add_argument("--column", help="按 columnName 过滤")
    p.add_argument("--classification", help="按 classificationName 过滤")
    p.add_argument("--sensitive-type", help="按敏感类型名过滤（如 身份证,手机号）")
    p.add_argument("--sensitive-level", help="按敏感等级过滤")
    p.add_argument("--mode", help="来源模式（SensDataStatusEnum）")
    p.add_argument("--fuzzy", help="fuzzySearchItem 模糊搜")
    p.add_argument("--since", help="updatedTime 起始：7d/24h/YYYY-MM-DD")
    p.add_argument("--until", help="updatedTime 截止：YYYY-MM-DD")
    p.add_argument("--sort-by", default="updatedTime", help="排序字段（默认 updatedTime）")
    p.add_argument("--sort-order", choices=["Asc", "Desc"], default="Desc")
    p.add_argument("--limit", type=int, default=50, help="返回上限（默认 50）")
    p.add_argument("--group-by",
                   help="聚合统计维度，支持单维或多维交叉（逗号分隔）。可用字段: sensitiveTypeName / sensitiveLevelName / engineType / projectName / dbName / schemaName / tableName / columnName / classificationName / mode。例: --group-by tableName,sensitiveLevelName")
    args = p.parse_args()

    body = {
        "pageSize": min(args.limit, 200),
        "pageNumber": 1,
        "sortBy": args.sort_by,
        "sortOrder": args.sort_order,
    }
    # 逐参赋值（服务端字段名 ↔ CLI）
    # ⚠️ 复数字段（Names/Types/modes）必须是 List，传 String 服务端 JSON 解析失败 → 302 到 err.taobao.com
    # 单数字段保持 String
    SINGULARS = {
        "projectName": args.project,
        "instanceId": args.instance,
        "clusterId": args.cluster,
        "catalogName": args.catalog,
        "dbName": args.db,
        "schemaName": args.schema,
        "tableName": args.table,
        "columnName": args.column,
        "classificationName": args.classification,
        "fuzzySearchItem": args.fuzzy,
    }
    PLURALS = {
        "engineTypes": args.engine,
        "sensitiveTypeNames": args.sensitive_type,
        "sensitiveLevelNames": args.sensitive_level,
        "modes": args.mode,
    }
    for k, v in SINGULARS.items():
        if v is not None:
            body[k] = v
    for k, v in PLURALS.items():
        if v is not None:
            # CLI 传逗号分隔串支持多选；单值自动 wrap 为单元素 List
            body[k] = [x.strip() for x in v.split(",") if x.strip()] if isinstance(v, str) else list(v)
    since_ms = _parse_since(args.since)
    if since_ms:
        body["selectedStartTime"] = since_ms
    if args.until:
        until_ms = _parse_since(args.until)
        if until_ms:
            body["selectedEndTime"] = until_ms

    client = BFFClient(quiet=True)
    rows = client.load("listRecognitionResult", **body) or []

    if not rows:
        print("无敏感字段识别结果")
        print("→ 有识别任务跑过吗？list_recognition_tasks.py")
        print("→ 放宽条件再试 或 --since 30d")
        return

    # 聚合：支持多维交叉（逗号分隔）
    if args.group_by:
        from collections import Counter
        dims = [d.strip() for d in args.group_by.split(",") if d.strip()]
        def _key(r):
            return tuple((r.get(d) or "未知") for d in dims)
        c = Counter(_key(r) for r in rows)
        total = sum(c.values())
        header_text = " × ".join(dims)
        print(f"基于返回的 {total} 条 — 按 {header_text} 分布：\n")
        widths = [max((len(str(k[i])) for k in c), default=len(dims[i])) for i in range(len(dims))]
        widths = [max(w, len(d)) for w, d in zip(widths, dims)]
        header = "  " + "  ".join(d.ljust(w) for d, w in zip(dims, widths)) + f"  {'数量':>6} {'占比':>7}"
        print(header)
        print("  " + "  ".join("-" * w for w in widths) + f"  {'-'*6} {'-'*7}")
        for k, n in c.most_common():
            row = "  " + "  ".join(str(v).ljust(w) for v, w in zip(k, widths)) + f"  {n:>6} {n*100.0/total:>6.1f}%"
            print(row)
        print(f"\n合计: {total}")
        return

    # 明细
    print(f"返回 {len(rows)} 条识别结果（按 {args.sort_by} {args.sort_order}）\n")
    print(f"  {'引擎':<14} {'项目':<14} {'库.表.列':<40} {'敏感类型':<12} {'等级':<6} {'来源':<6} {'更新':<17}")
    print(f"  {'-'*14} {'-'*14} {'-'*40} {'-'*12} {'-'*6} {'-'*6} {'-'*17}")
    for r in rows:
        eng = (r.get("engineType") or "")[:14]
        proj = (r.get("projectName") or "")[:14]
        loc = f"{r.get('dbName','?')}.{r.get('tableName','?')}.{r.get('columnName','?')}"[:40]
        stype = (r.get("sensitiveTypeName") or "")[:12]
        slvl = (r.get("sensitiveLevelName") or "")[:6]
        mode = (r.get("mode") or "")[:6]
        upd = _fmt_ms(r.get("updatedTime"))
        print(f"  {eng:<14} {proj:<14} {loc:<40} {stype:<12} {slvl:<6} {mode:<6} {upd:<17}")

    # 给 agent 明示入库 duckdb 表名 + schema + 查询模板
    # （test371 观察到 agent 用 stdout 的展示 label 去查 raw 表：
    #   · 查 source 列 → 实际字段叫 mode；· 拿 '2026-04-14' 比 updatedTime → 后者是 BIGINT 毫秒）
    last_table = getattr(client, "last_table", None) or "listRecognitionResult_rN_cN"
    print()
    print(f"→ 多维交叉: view_recognition_result.py --group-by tableName,sensitiveLevelName")
    print(f"→ SQL 分析（duckdb 表 {last_table}，字段 = API 原始名，不是 stdout 展示 label）:")
    print(f"    engineType / projectName / instanceId / clusterId / catalogName / dbName /")
    print(f"    schemaName / tableName / columnName / classificationName  VARCHAR")
    print(f"    sensitiveTypeName / sensitiveLevelName                    VARCHAR")
    print(f"    mode          VARCHAR  枚举 Recognized/Revise（stdout 里展示为「来源」）")
    print(f"    updatedTime   BIGINT   毫秒时间戳（stdout 展示为 YYYY-MM-DD HH:MM）")
    print(f"                  → 时间比较用 epoch_ms: WHERE updatedTime >= epoch_ms('2026-04-01'::DATE)")
    print(f"    sensitiveDataId  VARCHAR  主键")
    print(f"  示例: duckdb_query.py \"SELECT tableName, sensitiveLevelName, COUNT(*) FROM {last_table} GROUP BY 1,2 ORDER BY 1,2\"")
    print("→ 不确定 --sensitive-type 传什么名: list_sensitive_types.py --keyword 手机")
    print("→ 看单任务结果: 暂不支持按 taskId 过滤，API 设计是「跨任务全量」视角（按 db/table 筛）")


if __name__ == "__main__":
    main()
