#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修改数据质量规则 —— 查看规则配置并修改阈值

两阶段操作：
  1. 查看规则当前配置（默认行为）
  2. 修改阈值后提交（需用户确认）

用法:
    # 查看规则配置
    python dqc_update_rule.py --project-id 14255 --rule-id 42627349

    # 修改通过阈值
    python dqc_update_rule.py --project-id 14255 --rule-id 42627349 --passed-value 350

    # 修改强弱规则类型
    python dqc_update_rule.py --project-id 14255 --rule-id 42627349 --block-type 0

    # 确认提交（第二阶段）
    python dqc_update_rule.py --confirm
"""

import argparse
import json
import os
import sys
from datetime import datetime

from bff_client import BFFClient, save_tool_result, resolve_project_id
from telemetry import telemetry_start, telemetry_end, telemetry_fail


_TAG = "[dqc]"
_PENDING_FILE = os.path.join(os.path.expanduser("~"), ".dataworks", "dqc_update_rule_pending.json")
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


def _find_rule(client, pid, rule_id):
    """从 listRules 中找到指定 ruleId 的规则"""
    rules = _api_call(client, "listRules", projectId=pid, ruleIds=str(rule_id), pageSize=100)
    if isinstance(rules, list):
        for r in rules:
            if r.get("id") == rule_id:
                return r
    # fallback: 遍历
    if isinstance(rules, list) and rules:
        return rules[0]
    return None


def _print_rule(rule):
    """输出规则当前配置"""
    name = rule.get("ruleName", "?")
    rid = rule.get("id")
    block = BLOCK_MAP.get(rule.get("blockType", 0), "?")
    enabled = "启用" if rule.get("enabled") else "禁用"
    table = rule.get("tableName", "?")
    checker = rule.get("checkerCode", "?")
    method = rule.get("methodCode", "?")
    checker_desc = (rule.get("ruleTemplate") or {}).get("name", "")

    threshold = (rule.get("checkerSetting") or {}).get("threshold") or {}
    passed = threshold.get("passed") or {}
    warning = threshold.get("warning") or {}
    critical = threshold.get("critical") or {}

    print(f"\n  规则配置  ruleId={rid}")
    print(f"  {'─' * 55}")
    print(f"    规则名:     {name}")
    print(f"    表名:       {table}")
    print(f"    规则类型:   {block} (blockType={rule.get('blockType', 0)})")
    print(f"    状态:       {enabled}")
    print(f"    检查器:     {checker_desc} ({checker})")
    print(f"    检查方法:   {method}")
    print(f"\n  阈值配置:")
    if passed:
        print(f"    通过条件:   {passed.get('operator', '')} {passed.get('value', '')}")
    if warning:
        print(f"    告警条件:   {warning.get('operator', '')} {warning.get('value', '')}")
    if critical:
        print(f"    阻塞条件:   {critical.get('operator', '')} {critical.get('value', '')}")

    return threshold


def _apply_changes(rule, args):
    """应用修改到规则对象，返回变更摘要"""
    changes = []
    threshold = (rule.get("checkerSetting") or {}).get("threshold") or {}

    if args.passed_value is not None or args.passed_operator is not None:
        passed = threshold.get("passed") or {}
        if args.passed_value is not None:
            old_val = passed.get("value", "?")
            passed["value"] = str(args.passed_value)
            changes.append(f"通过阈值: {old_val} → {args.passed_value}")
        if args.passed_operator is not None:
            old_op = passed.get("operator", "?")
            passed["operator"] = args.passed_operator
            changes.append(f"通过操作符: {old_op} → {args.passed_operator}")
        threshold["passed"] = passed

    if args.critical_value is not None or args.critical_operator is not None:
        critical = threshold.get("critical") or {}
        if args.critical_value is not None:
            old_val = critical.get("value", "?")
            critical["value"] = str(args.critical_value)
            changes.append(f"阻塞阈值: {old_val} → {args.critical_value}")
        if args.critical_operator is not None:
            old_op = critical.get("operator", "?")
            critical["operator"] = args.critical_operator
            changes.append(f"阻塞操作符: {old_op} → {args.critical_operator}")
        threshold["critical"] = critical

    if args.warning_value is not None or args.warning_operator is not None:
        warning = threshold.get("warning") or {}
        if args.warning_value is not None:
            old_val = warning.get("value", "?")
            warning["value"] = str(args.warning_value)
            changes.append(f"告警阈值: {old_val} → {args.warning_value}")
        if args.warning_operator is not None:
            old_op = warning.get("operator", "?")
            warning["operator"] = args.warning_operator
            changes.append(f"告警操作符: {old_op} → {args.warning_operator}")
        threshold["warning"] = warning

    if args.block_type is not None:
        old_bt = BLOCK_MAP.get(rule.get("blockType", 0), "?")
        new_bt = BLOCK_MAP.get(args.block_type, "?")
        rule["blockType"] = args.block_type
        changes.append(f"规则类型: {old_bt} → {new_bt}")

    if args.enabled is not None:
        old_en = "启用" if rule.get("enabled") else "禁用"
        new_en = "启用" if args.enabled else "禁用"
        rule["enabled"] = args.enabled
        changes.append(f"状态: {old_en} → {new_en}")

    # 写回 threshold
    if rule.get("checkerSetting"):
        rule["checkerSetting"]["threshold"] = threshold

    # 页面修改规则时传 spec=null，让后端从 checkerSetting.threshold 重新生成 spec
    if changes:
        rule["spec"] = None

    return changes


def main():
    parser = argparse.ArgumentParser(description="修改数据质量规则")
    parser.add_argument("--project-id", type=int, default=None)
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--rule-id", type=int, help="规则 ID")
    parser.add_argument("--passed-value", type=float, help="修改通过阈值")
    parser.add_argument("--passed-operator", help="修改通过操作符（>, >=, <, <=, =, !=）")
    parser.add_argument("--critical-value", type=float, help="修改阻塞阈值")
    parser.add_argument("--critical-operator", help="修改阻塞操作符")
    parser.add_argument("--warning-value", type=float, help="修改告警阈值")
    parser.add_argument("--warning-operator", help="修改告警操作符")
    parser.add_argument("--block-type", type=int, choices=[0, 1], help="规则类型（0=弱, 1=强）")
    parser.add_argument("--enabled", type=lambda x: x.lower() in ('true', '1', 'yes'),
                        default=None, help="启用/禁用 (true/false)")
    parser.add_argument("--confirm", action="store_true", help="确认提交上一次的修改")
    args = parser.parse_args()

    telemetry_start("dqc_update_rule.py", module="dqc",
                    projectId=args.project_id, ruleId=args.rule_id)

    client = BFFClient(quiet=True)

    # ── 确认模式 ──
    if args.confirm:
        if not os.path.exists(_PENDING_FILE):
            print(f"❌ 没有待确认的修改（{_PENDING_FILE} 不存在）")
            sys.exit(1)

        with open(_PENDING_FILE) as f:
            pending = json.load(f)

        pid = pending["projectId"]
        rule = pending["rule"]
        entity_id = pending.get("entityId")
        changes = pending["changes"]

        print(f"\n  提交规则修改  ruleId={rule['id']}")
        print(f"  {'─' * 55}")
        for c in changes:
            print(f"    {c}")

        # 调用 updateRule — ruleList 是数组，不是 JSON 字符串
        payload = {
            "projectId": pid,
            "ruleList": [rule],
        }
        result = _api_call(client, "updateRule", **payload)
        os.remove(_PENDING_FILE)

        print(f"\n  ✅ 规则修改已提交")
        print(f"     returnCode: {result.get('returnCode') if isinstance(result, dict) else result}")

        telemetry_end(result={"projectId": pid, "ruleId": rule["id"], "action": "confirmed"})
        return

    # ── 查看/修改模式 ──
    if not args.rule_id:
        print(f"❌ 请指定 --rule-id")
        sys.exit(1)

    pid = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)

    # 获取规则
    rule = _find_rule(client, pid, args.rule_id)
    if not rule:
        print(f"❌ 未找到 ruleId={args.rule_id}")
        sys.exit(1)

    # 展示当前配置
    print()
    print(f"{'=' * 60}")
    _print_rule(rule)

    # 检查是否有修改
    has_changes = any(x is not None for x in [
        args.passed_value, args.passed_operator,
        args.critical_value, args.critical_operator,
        args.warning_value, args.warning_operator,
        args.block_type, args.enabled])

    if not has_changes:
        print(f"\n  💡 修改示例:")
        print(f"    python dqc_update_rule.py --project-id {pid} --rule-id {args.rule_id} --passed-value 350")
        print(f"    python dqc_update_rule.py --project-id {pid} --rule-id {args.rule_id} --block-type 0")
        print()
        telemetry_end(result={"projectId": pid, "ruleId": args.rule_id, "action": "view"})
        return

    # 补全 templateCode/templateName（updateRule API 必需）
    rt = rule.get("ruleTemplate") or {}
    if not rule.get("templateCode") and rt.get("code"):
        rule["templateCode"] = rt["code"]
    if not rule.get("templateName") and rt.get("name"):
        rule["templateName"] = rt["name"]

    # 应用修改
    changes = _apply_changes(rule, args)

    print(f"\n  📝 待提交的修改:")
    print(f"  {'─' * 55}")
    for c in changes:
        print(f"    {c}")

    # 保存 pending
    entity_id = rule.get("entityId") or rule.get("qualityJobId")
    # entityId 也可能在 entities[0]
    if not entity_id:
        entities = rule.get("entities") or []
        if entities:
            entity_id = entities[0].get("entityId")
    os.makedirs(os.path.dirname(_PENDING_FILE), exist_ok=True)
    with open(_PENDING_FILE, 'w') as f:
        json.dump({
            "projectId": pid,
            "rule": rule,
            "entityId": entity_id,
            "changes": changes,
            "timestamp": datetime.now().isoformat(),
        }, f, ensure_ascii=False, indent=2)

    print(f"\n  ⚠️ 确认后执行:")
    print(f"    python dqc_update_rule.py --confirm")
    print()

    telemetry_end(result={"projectId": pid, "ruleId": args.rule_id, "action": "pending"})


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        telemetry_fail("dqc_update_rule.py", "dqc", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
