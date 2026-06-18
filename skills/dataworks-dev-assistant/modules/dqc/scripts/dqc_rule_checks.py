#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据质量规则检查明细 —— 查看失败/告警规则详情

查询指定日期的规则检查结果，按失败规则分组汇总。

用法:
    python dqc_rule_checks.py --project-name autotest
    python dqc_rule_checks.py --project-id 14255 --date 2026-04-06
    python dqc_rule_checks.py --project-id 14255 --table jhr_mc_test
    python dqc_rule_checks.py --project-id 14255 --status failed
"""

import argparse
import sys
from datetime import datetime, timedelta

from bff_client import BFFClient, save_tool_result, resolve_project_id
from table_profile import resolve as resolve_table
from telemetry import telemetry_start, telemetry_end, telemetry_fail


_TAG = "[dqc]"

# status: -1=未运行, 0=失败, 2=通过
STATUS_MAP = {-1: "未运行", 0: "失败", 2: "通过"}
# blockType: 0=弱规则, 1=强规则
BLOCK_MAP = {0: "弱规则", 1: "强规则"}


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


def _resolve_date(date_str):
    today = datetime.now().date()
    if date_str == "today" or not date_str:
        return today
    elif date_str == "yesterday":
        return today - timedelta(days=1)
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _fmt(n):
    if n is None:
        return "-"
    return str(int(n)) if isinstance(n, (int, float)) else str(n)


def _ts_to_str(ts):
    """毫秒时间戳 → HH:MM:SS"""
    if not ts or not isinstance(ts, (int, float)):
        return "-"
    return datetime.fromtimestamp(ts / 1000).strftime("%H:%M:%S")


def main():
    parser = argparse.ArgumentParser(description="数据质量规则检查明细")
    parser.add_argument("--project-id", type=int, default=None)
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--date", default="today",
                        help="日期（today/yesterday/YYYY-MM-DD，默认 today）")
    parser.add_argument("--table", help="指定表名，只看该表的规则检查")
    parser.add_argument("--status", choices=["failed", "all"],
                        default="failed", help="筛选状态（默认 failed）")
    parser.add_argument("--page-size", type=int, default=100,
                        help="每页条数（默认 100）")
    args = parser.parse_args()

    telemetry_start("dqc_rule_checks.py", module="dqc",
                    projectId=args.project_id, date=args.date, table=args.table)

    client = BFFClient(quiet=True)
    pid = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)
    data_date = str(_resolve_date(args.date))

    # 构建查询参数
    params = {
        "projectId": pid,
        "dataDate": data_date,
        "datasourceTypes": "odps",
        "envTypes": "",
        "pageSize": args.page_size,
    }
    if args.table:
        profile = resolve_table(client, pid, args.table)
        params["tableGuid"] = profile["tableGuid"]
        params["datasourceTypes"] = profile["dbType"].lower()

    # 拉取检查结果
    checks = _safe_call(client, "listRuleChecks", **params)
    if not checks:
        checks = []
    elif isinstance(checks, dict):
        checks = checks.get("list") or checks.get("data") or []
    elif not isinstance(checks, list):
        checks = []

    # 过滤
    if args.status == "failed":
        checks = [c for c in checks if c.get("status") == 0]

    # 按表 + 规则分组汇总
    by_table = {}
    for c in checks:
        table_info = c.get("table", {})
        table_name = table_info.get("tableName", "?")
        rule = c.get("rule", {})
        rule_name = rule.get("ruleName", "?")
        block_type = rule.get("blockType", 0)
        checker = rule.get("checkerDescription") or rule.get("checkerCode", "?")
        status = c.get("status", -1)

        # 提取阈值配置
        threshold = (rule.get("checkerSetting") or {}).get("threshold") or {}
        passed_cond = threshold.get("passed") or {}
        critical_cond = threshold.get("critical") or {}
        threshold_str = ""
        if passed_cond:
            threshold_str = f"通过: {passed_cond.get('operator','')} {passed_cond.get('value','')}"
        if critical_cond:
            if threshold_str:
                threshold_str += f", 阻塞: {critical_cond.get('operator','')} {critical_cond.get('value','')}"

        # 提取实际检查值
        sample = c.get("sample") or {}
        actual_value = sample.get("simpleValue")
        details = c.get("details") or []
        checked_value = details[0].get("checkedValue") if details else None
        ref_value = details[0].get("referencedValue") if details else None
        bizdate = c.get("bizdate", "")
        error_msg = sample.get("errorMessage")

        key = (table_name, rule_name, block_type, checker)
        if key not in by_table:
            by_table[key] = {"count": 0, "status": status, "last_finish": 0,
                             "table_guid": table_info.get("tableGuid", ""),
                             "db_type": table_info.get("dbType", ""),
                             "rule_id": rule.get("id"),
                             "threshold": threshold_str,
                             "method": rule.get("methodCode", ""),
                             "data_scope": rule.get("dataScope", 0),
                             "actual_value": None,
                             "checked_value": None,
                             "ref_value": None,
                             "bizdate": "",
                             "error_msg": None}
        by_table[key]["count"] += 1
        finish = c.get("finishTime", 0) or 0
        if finish > by_table[key]["last_finish"]:
            by_table[key]["last_finish"] = finish
            by_table[key]["actual_value"] = actual_value
            by_table[key]["checked_value"] = checked_value
            by_table[key]["ref_value"] = ref_value
            by_table[key]["bizdate"] = bizdate
            by_table[key]["error_msg"] = error_msg

    # 排序：强规则优先，然后按失败次数
    sorted_items = sorted(by_table.items(),
                          key=lambda x: (-x[0][2], -x[1]["count"]))

    # 输出
    status_label = "失败" if args.status == "failed" else "全部"
    table_label = f"  表={args.table}" if args.table else ""
    print()
    print(f"{'=' * 65}")
    print(f"  规则检查明细  项目={pid}  日期={data_date}{table_label}")
    print(f"  数据源={ds_type}  状态={status_label}  共 {len(checks)} 条检查记录")
    print(f"{'=' * 65}")

    if not sorted_items:
        print(f"\n  没有{status_label}的规则检查记录")
        print()
        telemetry_end(result={"projectId": pid, "dataDate": data_date, "count": 0})
        return

    # 按表分组输出
    show_detail = bool(args.table)  # 指定表时显示详细配置
    current_table = None
    for (table_name, rule_name, block_type, checker), info in sorted_items:
        if table_name != current_table:
            current_table = table_name
            print(f"\n  {table_name}  ({info['db_type']})")
            print(f"  {'─' * 60}")

        block_label = "强" if block_type == 1 else "弱"
        rn = (rule_name or "?")[:23] if len(rule_name or "") <= 23 else (rule_name or "")[:20] + "..."

        if show_detail:
            # 详细模式：规则名 + 实际值 vs 阈值 + rule_id
            rule_id = info.get('rule_id', '')
            print(f"    {rn}  [{block_label}]  失败 {info['count']} 次  (ruleId={rule_id})")
            threshold_str = info.get('threshold', '')
            if threshold_str:
                print(f"      阈值: {threshold_str}")
            actual = info.get('actual_value')
            checked = info.get('checked_value')
            ref = info.get('ref_value')
            biz = info.get('bizdate', '')
            if actual is not None or checked is not None:
                val_str = f"实际值={checked or actual}"
                if ref is not None:
                    val_str += f", 参考值={ref}"
                if biz:
                    val_str += f"  (bizdate={biz})"
                print(f"      {val_str}")
            error = info.get('error_msg')
            if error:
                print(f"      错误: {error[:80]}")
        else:
            ck = (checker or "?")[:18] if len(checker or "") <= 18 else (checker or "")[:15] + "..."
            print(f"    {rn:<25s}  {block_label:>4s}  {info['count']:>4d}  {ck:<20s}")

    # 汇总
    strong_failed = sum(info["count"] for (_, _, bt, _), info in sorted_items if bt == 1)
    weak_failed = sum(info["count"] for (_, _, bt, _), info in sorted_items if bt == 0)
    tables_affected = len(set(t for (t, _, _, _), _ in sorted_items))

    print(f"\n  {'─' * 60}")
    print(f"  汇总: 强规则失败 {strong_failed} 次，弱规则失败 {weak_failed} 次，涉及 {tables_affected} 张表")

    # 下一步
    if not args.table and tables_affected > 0:
        first_table = sorted_items[0][0][0]
        print(f"\n  下一步（查看具体表的规则明细 + 实际值）:")
        print(f"    python dqc_rule_checks.py --project-id {pid} --table {first_table} --date {data_date}")
    elif args.table:
        # 收集 rule_ids 用于修改建议
        rule_ids = [str(info.get('rule_id', '')) for (_, _, _, _), info in sorted_items if info.get('rule_id')]
        print(f"\n  下一步:")
        print(f"    数据问题 → 排查产出:")
        print(f"      python query_partitions.py \"{args.table}\"")
        print(f"      python search_nodes.py \"{args.table}\" --project-id {pid}")
        print(f"    规则问题 → 修改规则:")
        if rule_ids:
            print(f"      python dqc_update_rule.py --project-id {pid} --rule-id {rule_ids[0]}")
    print()

    # 保存结构化结果
    save_tool_result("dqc_rule_checks", {
        "projectId": pid,
        "dataDate": data_date,
        "datasourceType": ds_type,
        "table": args.table,
        "totalChecks": len(checks),
        "strongFailed": strong_failed,
        "weakFailed": weak_failed,
        "tablesAffected": tables_affected,
        "details": [
            {"table": t, "rule": r, "blockType": BLOCK_MAP.get(bt, "?"),
             "checker": ck, "count": info["count"]}
            for (t, r, bt, ck), info in sorted_items[:20]
        ],
    })

    telemetry_end(result={"projectId": pid, "dataDate": data_date,
                          "totalChecks": len(checks),
                          "strongFailed": strong_failed, "weakFailed": weak_failed})


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        telemetry_fail("dqc_rule_checks.py", "dqc", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
