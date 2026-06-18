#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据质量概览 —— 一站式输出质量大盘全貌

聚合规则执行概览、风险表排行、按表/按人分布、执行趋势。

用法:
    python dqc_overview.py --project-name autotest
    python dqc_overview.py --project-id 14255 --date yesterday
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from bff_client import BFFClient, save_tool_result, resolve_project_id
from telemetry import telemetry_start, telemetry_end, telemetry_fail


_TAG = "[dqc]"

# 所有大盘 API 需要的公共参数（和页面行为对齐）
_COMMON = {"envTypes": ""}


# ─── 内部 API 调用 ────────────────────────────────────────────

def _api_call(client, api_name, **kwargs):
    api_meta = client.api_index.get(api_name)
    if not api_meta:
        raise ValueError(f"未找到 API: {api_name}")
    result = client._do_request(api_name, api_meta, **kwargs)
    code = result.get("code")
    if code not in (None, 0, "0", 200, "200"):
        msg = result.get("message", "")
        raise RuntimeError(f"{api_name} 失败: code={code}, message={msg}")
    return_structure = api_meta.get("return_structure", "")
    return client._parse_return_structure(result, return_structure)


def _safe_call(client, api_name, **kwargs):
    try:
        return _api_call(client, api_name, **kwargs)
    except Exception:
        return None


# ─── 参数解析 ────────────────────────────────────────────────

def _resolve_date(date_str):
    today = datetime.now().date()
    if date_str == "today" or not date_str:
        return today
    elif date_str == "yesterday":
        return today - timedelta(days=1)
    else:
        return datetime.strptime(date_str, "%Y-%m-%d").date()


def _fmt(n):
    if n is None:
        return "-"
    return str(int(n)) if isinstance(n, (int, float)) else str(n)


def _pct(part, total):
    if not total:
        return "-"
    return f"{part / total * 100:.1f}%"


# ─── 0. 获取默认数据源类型 ────────────────────────────────────

def _get_default_datasource_type(client, pid):
    """从 listDataSourcesLite 获取第一个数据源类型（页面默认行为）"""
    data = _safe_call(client, "listDataSourcesLite", projectId=pid)
    if isinstance(data, list) and data:
        return data[0].get("dbType", "").lower() or "odps"
    return "odps"


# ─── 1. 可用日期范围 ─────────────────────────────────────────

def _get_available_date(client, pid, target_date):
    """获取可用数据日期，如果目标日期无数据则降级到最近有数据的日期"""
    data = _safe_call(client, "availableDataDateRange", projectId=pid)
    if not data or not isinstance(data, dict):
        return str(target_date), False

    # API 返回 {"from": "2025-10-08", "to": "2026-04-06"}
    max_date = data.get("to")
    min_date = data.get("from")

    target_str = str(target_date)
    if max_date and target_str > max_date:
        return max_date, True
    if min_date and target_str < min_date:
        return min_date, True
    return target_str, False


# ─── 2. 执行概览 ─────────────────────────────────────────────

def _section_overview(client, pid, data_date, ds_type):
    """规则执行总览统计

    API 返回字段:
      configCount    — 总配置规则数
      enabledCount   — 已启用规则数
      checkedCount   — 已检查规则数（通过 + 失败）
      failedCount    — 失败总数
      strongRedCount / strongOrangeCount — 强规则阻塞/告警
      weakRedCount   / weakOrangeCount   — 弱规则阻塞/告警
      strongRuleFailedCount / weakFailedCount — 强/弱规则失败数
    """
    data = _safe_call(client, "getOverview", projectId=pid, dataDate=data_date,
                      datasourceTypes=ds_type, aggregateBy="TABLE", **_COMMON)
    if not data or not isinstance(data, dict):
        return None

    config = data.get("configCount", 0) or 0
    enabled = data.get("enabledCount", 0) or 0
    checked = data.get("checkedCount", 0) or 0
    failed = data.get("failedCount", 0) or 0
    passed = checked - failed if checked >= failed else 0

    strong_red = data.get("strongRedCount", 0) or 0
    strong_orange = data.get("strongOrangeCount", 0) or 0
    weak_red = data.get("weakRedCount", 0) or 0
    weak_orange = data.get("weakOrangeCount", 0) or 0

    return {
        "configCount": config,
        "enabledCount": enabled,
        "checkedCount": checked,
        "passed": passed,
        "failed": failed,
        "strongRed": strong_red,
        "strongOrange": strong_orange,
        "weakRed": weak_red,
        "weakOrange": weak_orange,
        "critical": strong_red + weak_red,       # 阻塞 = 红色
        "warning": strong_orange + weak_orange,   # 告警 = 橙色
    }


# ─── 3. 执行状态分布 ─────────────────────────────────────────

def _section_run_status(client, pid, data_date, ds_type):
    """按状态维度的执行分布"""
    data = _safe_call(client, "getRunStatus", projectId=pid,
                      datasourceTypes=ds_type,
                      maxDataDate=data_date, minDataDate=data_date, **_COMMON)
    if not data or not isinstance(data, dict):
        return None

    return {
        "passedCount": data.get("passedCount", 0) or 0,
        "failedCount": data.get("failedCount", 0) or 0,
        "strongPassedCount": data.get("strongPassedCount", 0) or 0,
        "weakPassedCount": data.get("weakPassedCount", 0) or 0,
        "strongRedCount": data.get("strongRedCount", 0) or 0,
        "weakRedCount": data.get("weakRedCount", 0) or 0,
        "strongOrangeCount": data.get("strongOrangeCount", 0) or 0,
        "weakOrangeCount": data.get("weakOrangeCount", 0) or 0,
        "unknownCount": data.get("unknownCount", 0) or 0,
    }


# ─── 4. 风险表 ───────────────────────────────────────────────

def _section_risky_tables(client, pid, data_date, ds_type):
    """风险表概览 + 明细 top10"""
    overview = _safe_call(client, "listQualityRiskyTableOverview",
                          projectId=pid, dataDate=data_date,
                          datasourceTypes=ds_type, **_COMMON)
    tables = _safe_call(client, "listQualityRiskyTables",
                        projectId=pid, dataDate=data_date,
                        datasourceTypes=ds_type,
                        riskType="NONE", orderBy="ruleCount", orderType="DESC",
                        pageSize=10, **_COMMON)
    return {
        "overview": overview,
        "top_tables": tables if isinstance(tables, list) else [],
    }


# ─── 5. 按表分布 ─────────────────────────────────────────────

def _section_by_table(client, pid, data_date, ds_type):
    """规则检查按表分布 top10"""
    data = _safe_call(client, "listRuleCheckDistributionByTable",
                      projectId=pid, dataDate=data_date,
                      datasourceTypes=ds_type, blockType="null",
                      pageSize=10, **_COMMON)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("list") or data.get("data") or []
    return []


# ─── 6. 按人分布 ─────────────────────────────────────────────

def _section_by_follower(client, pid, data_date, ds_type):
    """规则检查按关注人分布 top10"""
    data = _safe_call(client, "listRuleCheckDistributionByFollower",
                      projectId=pid, dataDate=data_date,
                      datasourceTypes=ds_type,
                      aggregateBy="OWNER", pageSize=10,
                      orderBy="failedRuleCount", orderType="DESC", **_COMMON)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("list") or data.get("data") or []
    return []


# ─── 7. 执行趋势 ─────────────────────────────────────────────

def _section_trend(client, pid, data_date, ds_type):
    """当天按小时执行趋势

    API 返回柱状图格式:
      labels: ["00", "01", ..., "17"]
      passedData: [183, 63, ...]
      failedData: [18, 19, ...]
      strongRedData: [...]
    转换为行列格式便于输出。
    """
    data = _safe_call(client, "listRunTrend",
                      projectId=pid,
                      datasourceTypes=ds_type, dataDate=data_date,
                      maxDataDate=data_date, minDataDate=data_date,
                      aggregateBy="HOUR", **_COMMON)
    if not data or not isinstance(data, dict):
        return []

    labels = data.get("labels") or []
    passed = data.get("passedData") or []
    failed = data.get("failedData") or []
    strong_red = data.get("strongRedData") or []

    rows = []
    for i, label in enumerate(labels):
        p = passed[i] if i < len(passed) else 0
        f = failed[i] if i < len(failed) else 0
        sr = strong_red[i] if i < len(strong_red) else 0
        if p or f:  # 跳过全零行
            rows.append({"hour": label, "passed": p, "failed": f, "strongRed": sr})
    return rows


# ─── 输出格式化 ──────────────────────────────────────────────

def _print_report(pid, data_date, date_fallback, ds_type, overview, run_status,
                  risky, by_table, by_follower, trend):
    print()
    print(f"{'=' * 60}")
    print(f"  数据质量概览  项目={pid}  日期={data_date}  数据源={ds_type}")
    if date_fallback:
        print(f"  (目标日期无数据，已降级到最近有数据的日期)")
    print(f"{'=' * 60}")

    # ── 执行概览 ──
    if overview:
        config = overview["configCount"]
        enabled = overview["enabledCount"]
        checked = overview["checkedCount"]
        passed = overview["passed"]
        failed = overview["failed"]
        critical = overview["critical"]
        warning = overview["warning"]

        print()
        print(f"  规则执行概览")
        print(f"  {'─' * 50}")
        print(f"    总配置:     {_fmt(config)}")
        print(f"    已启用:     {_fmt(enabled)}")
        print(f"    已检查:     {_fmt(checked)}")
        print(f"    通过:       {_fmt(passed):>6s}  {_pct(passed, checked)}")
        print(f"    失败:       {_fmt(failed):>6s}  {_pct(failed, checked)}")
        if critical or warning:
            print()
            print(f"    强规则阻塞:  {_fmt(overview['strongRed'])}")
            print(f"    强规则告警:  {_fmt(overview['strongOrange'])}")
            print(f"    弱规则阻塞:  {_fmt(overview['weakRed'])}")
            print(f"    弱规则告警:  {_fmt(overview['weakOrange'])}")
    else:
        print()
        print(f"  规则执行概览: 无数据")

    # ── 运行状态 ──
    if run_status:
        print()
        print(f"  运行状态分布")
        print(f"  {'─' * 50}")
        print(f"    通过:       强 {_fmt(run_status['strongPassedCount'])}  弱 {_fmt(run_status['weakPassedCount'])}  合计 {_fmt(run_status['passedCount'])}")
        print(f"    阻塞(红):   强 {_fmt(run_status['strongRedCount'])}  弱 {_fmt(run_status['weakRedCount'])}")
        print(f"    告警(橙):   强 {_fmt(run_status['strongOrangeCount'])}  弱 {_fmt(run_status['weakOrangeCount'])}")
        if run_status.get('unknownCount'):
            print(f"    未知:       {_fmt(run_status['unknownCount'])}")

    # ── 风险表 ──
    if risky and risky.get("top_tables"):
        tables = risky["top_tables"]
        print()
        print(f"  风险表 TOP {len(tables)}")
        print(f"  {'─' * 50}")
        print(f"    {'表名':<30s}  {'规则数':>5s}  {'失败':>4s}")
        for t in tables:
            name = t.get("tableName") or t.get("name") or "?"
            if len(name) > 28:
                name = name[:25] + "..."
            rule_count = _fmt(t.get("ruleCount", 0))
            fail = _fmt(t.get("failedRuleCount") or t.get("failedCount", 0))
            print(f"    {name:<30s}  {rule_count:>5s}  {fail:>4s}")

    # ── 按表分布 ──
    if by_table:
        print()
        print(f"  按表分布 TOP {len(by_table)} (失败规则数排序)")
        print(f"  {'─' * 50}")
        print(f"    {'表名':<30s}  {'失败':>4s}  {'强阻塞':>5s}")
        for t in by_table[:10]:
            name = t.get("tableName") or t.get("name") or "?"
            if len(name) > 28:
                name = name[:25] + "..."
            fail = _fmt(t.get("failedRuleCount") or t.get("failedCount", 0))
            strong_red = _fmt(t.get("strongRedRuleCount", 0))
            print(f"    {name:<30s}  {fail:>4s}  {strong_red:>5s}")

    # ── 按人分布 ──
    if by_follower:
        print()
        print(f"  按负责人分布 TOP {len(by_follower)}")
        print(f"  {'─' * 50}")
        print(f"    {'负责人':<20s}  {'规则数':>5s}  {'失败':>4s}  {'失败表':>5s}")
        for f in by_follower[:10]:
            name = f.get("followerNick") or f.get("ownerNick") or f.get("name") or "?"
            rule_count = _fmt(f.get("totalRuleCount") or f.get("ruleCount", 0))
            fail = _fmt(f.get("failedRuleCount") or f.get("failedCount", 0))
            fail_table = _fmt(f.get("failedTableCount", 0))
            print(f"    {name:<20s}  {rule_count:>5s}  {fail:>4s}  {fail_table:>5s}")

    # ── 趋势 ──
    if trend:
        print()
        print(f"  当日执行趋势（按小时）")
        print(f"  {'─' * 50}")
        print(f"    {'时间':>4s}  {'通过':>5s}  {'失败':>5s}  {'强阻塞':>5s}")
        for row in trend:
            h = row.get("hour", "?")
            p = _fmt(row.get("passed", 0))
            f = _fmt(row.get("failed", 0))
            sr = _fmt(row.get("strongRed", 0))
            print(f"    {h:>4s}  {p:>5s}  {f:>5s}  {sr:>5s}")

    # ── 下一步建议 ──
    print()
    print(f"  {'─' * 50}")
    if overview and overview.get("failed", 0) > 0:
        print(f"  下一步（查看失败规则明细）:")
        print(f"    python dqc_rule_checks.py --project-id {pid} --date {data_date}")
        # 如果有风险表，推荐查看第一张
        if risky and risky.get("top_tables"):
            first = risky["top_tables"][0]
            t = first.get("tableName") or first.get("name")
            if t:
                print(f"    python dqc_rule_checks.py --project-id {pid} --table {t} --date {data_date}")
    else:
        print(f"  所有规则运行正常")
    print()


# ─── Main ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="数据质量概览")
    parser.add_argument("--project-id", type=int, default=None)
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--date", default="today",
                        help="日期（today/yesterday/YYYY-MM-DD，默认 today）")
    args = parser.parse_args()

    telemetry_start("dqc_overview.py", module="dqc",
                    projectId=args.project_id, date=args.date)

    client = BFFClient(quiet=True)
    pid = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)
    target_date = _resolve_date(args.date)

    # 获取默认数据源类型 + 可用日期
    ds_type = _get_default_datasource_type(client, pid)
    data_date, date_fallback = _get_available_date(client, pid, target_date)

    # 并行拉取各维度数据
    with ThreadPoolExecutor(max_workers=6) as pool:
        f_overview = pool.submit(_section_overview, client, pid, data_date, ds_type)
        f_run_status = pool.submit(_section_run_status, client, pid, data_date, ds_type)
        f_risky = pool.submit(_section_risky_tables, client, pid, data_date, ds_type)
        f_by_table = pool.submit(_section_by_table, client, pid, data_date, ds_type)
        f_by_follower = pool.submit(_section_by_follower, client, pid, data_date, ds_type)
        f_trend = pool.submit(_section_trend, client, pid, data_date, ds_type)

    overview = f_overview.result()
    run_status = f_run_status.result()
    risky = f_risky.result()
    by_table = f_by_table.result()
    by_follower = f_by_follower.result()
    trend = f_trend.result()

    # 输出报告
    _print_report(pid, data_date, date_fallback, ds_type, overview, run_status,
                  risky, by_table, by_follower, trend)

    # 保存结构化结果
    save_tool_result("dqc_overview", {
        "projectId": pid,
        "dataDate": data_date,
        "datasourceType": ds_type,
        "overview": overview,
        "runStatus": run_status,
        "riskyTables": risky.get("top_tables", []) if risky else [],
        "byTable": by_table[:10] if by_table else [],
        "byFollower": by_follower[:10] if by_follower else [],
        "trend": trend,
    })

    telemetry_end(result={"projectId": pid, "dataDate": data_date,
                          "totalRules": overview.get("configCount") if overview else 0})


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        telemetry_fail("dqc_overview.py", "dqc", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
