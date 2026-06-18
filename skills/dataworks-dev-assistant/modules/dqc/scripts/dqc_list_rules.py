#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查看表的质量规则配置列表 —— 展示所有规则（不只是已执行/失败的）

用法:
    python dqc_list_rules.py --project-id 14255 --table jhr_mc_test
    python dqc_list_rules.py --project-name autotest --table test
"""

import argparse
import sys
from datetime import datetime

from bff_client import BFFClient, save_tool_result, resolve_project_id
from table_profile import resolve as resolve_table
from telemetry import telemetry_start, telemetry_end, telemetry_fail


_TAG = "[dqc]"
BLOCK_MAP = {0: "弱", 1: "强"}


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


def main():
    parser = argparse.ArgumentParser(description="查看表的质量规则配置列表")
    parser.add_argument("--project-id", type=int, default=None)
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--table", required=True, help="表名")
    parser.add_argument("--all", action="store_true", help="包含已禁用的规则")
    args = parser.parse_args()

    telemetry_start("dqc_list_rules.py", module="dqc",
                    projectId=args.project_id, table=args.table)

    client = BFFClient(quiet=True)
    pid = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)

    # 解析表（含存在性校验）
    profile = resolve_table(client, pid, args.table)
    table_guid = profile["tableGuid"]

    # 查询规则列表
    rules = _api_call(client, "listRules", projectId=pid,
                      tableGuid=table_guid, pageSize=200)
    if not rules or not isinstance(rules, list):
        rules = []

    # 过滤
    if not args.all:
        rules = [r for r in rules if r.get("enabled")]

    # 输出
    enabled_count = sum(1 for r in rules if r.get("enabled"))
    disabled_count = sum(1 for r in rules if not r.get("enabled"))
    strong_count = sum(1 for r in rules if r.get("blockType") == 1)

    print()
    print(f"{'=' * 65}")
    print(f"  规则配置列表  项目={pid}  表={args.table}")
    print(f"  共 {len(rules)} 条规则  启用 {enabled_count}  禁用 {disabled_count}  强规则 {strong_count}")
    print(f"{'=' * 65}")

    if not rules:
        print(f"\n  该表无质量规则")
        if not args.all:
            print(f"  💡 加 --all 查看包含已禁用的规则")
        print(f"\n  创建规则:")
        print(f"    python dqc_create_rule.py --project-id {pid} --table {args.table} --template row_count_gt0")
        print()
        telemetry_end(result={"projectId": pid, "table": args.table, "count": 0})
        return

    print()
    for r in rules:
        rid = r.get("id", "?")
        name = r.get("ruleName") or "?"
        block = BLOCK_MAP.get(r.get("blockType", 0), "?")
        enabled = "启用" if r.get("enabled") else "禁用"
        method = r.get("methodCode", "")
        checker = r.get("checkerCode", "")
        tmpl = (r.get("ruleTemplate") or {}).get("name", "")

        # 阈值
        threshold = (r.get("checkerSetting") or {}).get("threshold") or {}
        passed = threshold.get("passed") or {}
        critical = threshold.get("critical") or {}
        th_str = ""
        if passed:
            th_str = f"通过: {passed.get('operator','')} {passed.get('value','')}"
        if critical:
            th_str += f"  阻塞: {critical.get('operator','')} {critical.get('value','')}"

        # 字段
        ms = r.get("methodSetting") or {}
        field = ms.get("field", "")

        print(f"  [{block}] {name}  (ruleId={rid}, {enabled})")
        print(f"    模板: {tmpl}  检查器: {checker}  方法: {method}")
        if field:
            print(f"    字段: {field}")
        if th_str:
            print(f"    阈值: {th_str}")
        print()

    print(f"  {'─' * 60}")
    print(f"  下一步:")
    print(f"    查看检查结果: python dqc_rule_checks.py --project-id {pid} --table {args.table}")
    print(f"    修改规则:     python dqc_update_rule.py --project-id {pid} --rule-id <ruleId>")
    print(f"    创建规则:     python dqc_create_rule.py --project-id {pid} --table {args.table} --list-templates")
    print()

    save_tool_result("dqc_list_rules", {
        "projectId": pid,
        "table": args.table,
        "totalRules": len(rules),
        "enabledCount": enabled_count,
        "strongCount": strong_count,
        "rules": [
            {"id": r.get("id"), "name": r.get("ruleName"), "blockType": r.get("blockType"),
             "enabled": r.get("enabled"), "method": r.get("methodCode"),
             "template": (r.get("ruleTemplate") or {}).get("name", "")}
            for r in rules[:30]
        ],
    })

    telemetry_end(result={"projectId": pid, "table": args.table, "count": len(rules)})


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        telemetry_fail("dqc_list_rules.py", "dqc", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
