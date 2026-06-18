#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建数据质量规则 —— 为指定表添加质量检查规则

两阶段操作：
  1. 预览规则配置（默认行为）
  2. 确认后提交（--confirm）

用法:
    # 表行数大于0（最常用）
    python dqc_create_rule.py --project-id 14255 --table jhr_mc_test --template row_count_gt0

    # 表行数固定值比较
    python dqc_create_rule.py --project-id 14255 --table jhr_mc_test --template row_count_fixed --passed-value 100

    # 空值记录数为0
    python dqc_create_rule.py --project-id 14255 --table jhr_mc_test --template null_count_0 --field birthday

    # 强规则
    python dqc_create_rule.py --project-id 14255 --table jhr_mc_test --template row_count_gt0 --block-type 1

    # 确认提交
    python dqc_create_rule.py --confirm
"""

import argparse
import json
import os
import sys
from datetime import datetime

from bff_client import BFFClient, save_tool_result, resolve_project_id
from table_profile import resolve as resolve_table
from telemetry import telemetry_start, telemetry_end, telemetry_fail


_TAG = "[dqc]"
_PENDING_FILE = os.path.join(os.path.expanduser("~"), ".dataworks", "dqc_create_rule_pending.json")
BLOCK_MAP = {0: "弱规则", 1: "强规则"}

# ── Threshold 默认模板（共享给不同模板）────────────────────────
_THRESHOLD_FIXED_GT_0 = {
    "passed": {"value": "0", "operator": ">"},
    "critical": {"value": "0", "operator": "<="},
}
_THRESHOLD_FIXED_EQ_0 = {
    "passed": {"value": "0", "operator": "="},
    "critical": {"value": "0", "operator": "!="},
}
_THRESHOLD_PERCENT_LTE_005 = {
    "passed": {"value": "0.05", "operator": "<="},
    "critical": {"value": "0.05", "operator": ">"},
}
_THRESHOLD_FLUX = {
    "passed": {"value": "0.1", "operator": "<"},
    "warning": {"value": "0.1", "operator": ">="},
    "critical": {"value": "0.2", "operator": ">="},
}
_THRESHOLD_EMPTY = {}


def _flux_tmpl(code, name, method, requires_field=False):
    """生成 flux 类模板（波动率，含 warn/fail）"""
    return {
        "templateCode": code,
        "templateName": name,
        "methodCode": method,
        "checkerCode": "fulx",  # 服务端实际接受的字符串（拼写保留原样）
        "checkerDescription": name,
        "checkerCompareType": 1,
        "requires_field": requires_field,
        "threshold": _THRESHOLD_FLUX,
    }


def _dynamic_tmpl(code, name, method, requires_field=False):
    """生成动态阈值类模板"""
    return {
        "templateCode": code,
        "templateName": name,
        "methodCode": method,
        "checkerCode": "dynamic_threshold",
        "checkerDescription": name,
        "requires_field": requires_field,
        "threshold": _THRESHOLD_EMPTY,
    }


def _fixed_tmpl(code, name, method, threshold=None, requires_field=False):
    """生成固定值类模板"""
    return {
        "templateCode": code,
        "templateName": name,
        "methodCode": method,
        "checkerCode": "fixed",
        "checkerDescription": name,
        "requires_field": requires_field,
        "threshold": threshold or dict(_THRESHOLD_FIXED_GT_0),
    }


# 常用模板快捷名 → templateId + 默认配置
# 组织：表级行数 → 表级大小 → 字段级（空值 / 重复值 / 唯一值 / 聚合）
TEMPLATE_SHORTCUTS = {
    # ─── 表行数 ─────────────────────────────────────────
    "row_count_gt0": {
        **_fixed_tmpl("SYSTEM:table:table_count:fixed:0", "表行数大于0", "table_count"),
        "assertion": "row_count > 0",
    },
    "row_count_fixed": _fixed_tmpl(
        "SYSTEM:table:table_count:fixed", "表行数，固定值", "table_count"),
    "row_count_flux": _flux_tmpl(
        "SYSTEM:table:table_count:flux:1_7_1m_bizdate", "表行数，1/7/30天波动率", "table_count"),
    "row_count_flux_1d": _flux_tmpl(
        "SYSTEM:table:table_count:flux:1_bizdate", "表行数，1天波动率", "table_count"),
    "row_count_flux_7d": _flux_tmpl(
        "SYSTEM:table:table_count:flux:7_bizdate", "表行数，7天波动率", "table_count"),
    "row_count_flux_1m": _flux_tmpl(
        "SYSTEM:table:table_count:flux:1m_bizdate", "表行数，30天波动率", "table_count"),
    "row_count_flux_month": _flux_tmpl(
        "SYSTEM:table:table_count:flux:1_7_1m_1st_bizdate", "表行数，1/7/30天及月初波动率", "table_count"),
    "row_count_avg_7d": _flux_tmpl(
        "SYSTEM:table:table_count:avg:7_bizdate", "表行数，7天平均值波动率", "table_count"),
    "row_count_avg_1m": _flux_tmpl(
        "SYSTEM:table:table_count:avg:1m_bizdate", "表行数，30天平均值波动率", "table_count"),
    "row_count_cycle": _flux_tmpl(
        "SYSTEM:table:table_count:cycle:latest_bizdate", "表行数，上周期波动率", "table_count"),
    "row_count_delta_1d": _fixed_tmpl(
        "SYSTEM:table:table_count_delta:fixed:1_bizdate", "表行数，1天差值", "table_count_delta"),
    "row_count_delta_cycle": _fixed_tmpl(
        "SYSTEM:table:table_count_delta:fixed:latest_bizdate", "表行数，上周期差值", "table_count_delta"),
    "dynamic_threshold": _dynamic_tmpl(
        "SYSTEM:table:table_count:dynamic_threshold", "表行数，动态阈值", "table_count"),

    # ─── 表大小 ─────────────────────────────────────────
    "table_size_fixed": _fixed_tmpl(
        "SYSTEM:table:table_size:fixed", "表大小，固定值", "table_size"),
    "table_size_flux_1d": _flux_tmpl(
        "SYSTEM:table:table_size:flux:1_bizdate", "表大小，1天波动率", "table_size"),
    "table_size_flux_7d": _flux_tmpl(
        "SYSTEM:table:table_size:flux:7_bizdate", "表大小，7天波动率", "table_size"),
    "table_size_flux_1m": _flux_tmpl(
        "SYSTEM:table:table_size:flux:1m_bizdate", "表大小，30天波动率", "table_size"),
    "table_size_dynamic": _dynamic_tmpl(
        "SYSTEM:table:table_size:dynamic_threshold", "表大小，动态阈值", "table_size"),
    "table_size_delta_1d": _fixed_tmpl(
        "SYSTEM:table:table_size_delta:fixed:1_bizdate", "表大小，1天差值", "table_size_delta"),
    "table_size_delta_cycle": _fixed_tmpl(
        "SYSTEM:table:table_size_delta:fixed:latest_bizdate", "表大小，上周期差值", "table_size_delta"),

    # ─── 字段级 — 空值 ──────────────────────────────────
    "null_count_0": _fixed_tmpl(
        "SYSTEM:field:null_value:fixed:0", "空值记录数为0", "null_value",
        threshold=dict(_THRESHOLD_FIXED_EQ_0), requires_field=True),
    "null_count_fixed": _fixed_tmpl(
        "SYSTEM:field:null_value:fixed", "空值个数，固定值", "null_value",
        threshold=dict(_THRESHOLD_FIXED_EQ_0), requires_field=True),
    "null_percent": _fixed_tmpl(
        "SYSTEM:field:null_value_percent:fixed", "空值个数/总行数，固定值", "null_value_percent",
        threshold=dict(_THRESHOLD_PERCENT_LTE_005), requires_field=True),

    # ─── 字段级 — 重复值 ────────────────────────────────
    "duplicate_count_0": _fixed_tmpl(
        "SYSTEM:field:duplicated_count:fixed:0", "字段重复值为0", "duplicated_count",
        threshold=dict(_THRESHOLD_FIXED_EQ_0), requires_field=True),
    "duplicate_count_fixed": _fixed_tmpl(
        "SYSTEM:field:duplicated_count:fixed", "重复值个数，固定值", "duplicated_count",
        threshold=dict(_THRESHOLD_FIXED_EQ_0), requires_field=True),
    "duplicate_percent": _fixed_tmpl(
        "SYSTEM:field:duplicated_percent:fixed", "重复值个数/总行数，固定值", "duplicated_percent",
        threshold=dict(_THRESHOLD_PERCENT_LTE_005), requires_field=True),
    "duplicates_multi_0": _fixed_tmpl(
        "SYSTEM:fields:duplicated_count:fixed:0", "多字段重复值为0", "duplicated_count",
        threshold=dict(_THRESHOLD_FIXED_EQ_0), requires_field=True),

    # ─── 字段级 — 唯一值 ────────────────────────────────
    "col_distinct_fixed": _fixed_tmpl(
        "SYSTEM:field:count_distinct:fixed", "唯一值个数，固定值", "count_distinct",
        requires_field=True),
    "col_distinct_flux": _flux_tmpl(
        "SYSTEM:field:count_distinct:flux:1_7_1m_bizdate", "唯一值个数，1/7/30天波动率",
        "count_distinct", requires_field=True),
    "col_distinct_dynamic": _dynamic_tmpl(
        "SYSTEM:field:count_distinct:dynamic_threshold", "唯一值个数，动态阈值",
        "count_distinct", requires_field=True),
    "col_distinct_percent": _fixed_tmpl(
        "SYSTEM:field:count_distinct_percent:fixed", "唯一值个数/总行数，固定值",
        "count_distinct_percent", requires_field=True),

    # ─── 字段级 — 聚合（min/max/avg/sum）─────────────────
    "col_min_flux": _flux_tmpl(
        "SYSTEM:field:min:flux:1_7_1m_bizdate", "最小值，1/7/30天波动率", "min",
        requires_field=True),
    "col_min_dynamic": _dynamic_tmpl(
        "SYSTEM:field:min:dynamic_threshold", "最小值，动态阈值", "min", requires_field=True),
    "col_max_dynamic": _dynamic_tmpl(
        "SYSTEM:field:max:dynamic_threshold", "最大值，动态阈值", "max", requires_field=True),
    "col_avg_flux": _flux_tmpl(
        "SYSTEM:field:avg:flux:1_7_1m_bizdate", "平均值，1/7/30天波动率", "avg",
        requires_field=True),
    "col_avg_dynamic": _dynamic_tmpl(
        "SYSTEM:field:avg:dynamic_threshold", "平均值，动态阈值", "avg", requires_field=True),
    "col_sum_flux": _flux_tmpl(
        "SYSTEM:field:sum:flux:1_7_1m_bizdate", "汇总值，1/7/30天波动率", "sum",
        requires_field=True),
    "col_sum_dynamic": _dynamic_tmpl(
        "SYSTEM:field:sum:dynamic_threshold", "汇总值，动态阈值", "sum", requires_field=True),
}


def _build_template_from_code(template_code):
    """逃生舱：任意 templateCode → 自动推断 methodCode/checkerCode 构造模板
    格式约定：SYSTEM:<scope>:<method>:<checker>[:<variant>]
    用于支持 TEMPLATE_SHORTCUTS 未覆盖的模板（如 pattern_match / count_not_in，但这类
    需要 valid.regex/valid.format/valid.values 扩展字段，走 spec-builder 更合适）。
    """
    if not template_code or not template_code.startswith("SYSTEM:"):
        return None, "templateCode 须以 SYSTEM: 开头"
    parts = template_code.split(":")
    if len(parts) < 4:
        return None, f"templateCode 格式应为 SYSTEM:<scope>:<method>:<checker>[:<variant>]，实际: {template_code}"
    scope = parts[1]
    method = parts[2]
    checker = parts[3]
    variant = ":".join(parts[4:]) if len(parts) > 4 else None

    if checker == "flux":
        threshold = _THRESHOLD_FLUX
        checker_code = "fulx"
        compare_type = 1
    elif checker == "dynamic_threshold":
        threshold = _THRESHOLD_EMPTY
        checker_code = "dynamic_threshold"
        compare_type = 2
    elif checker in ("avg", "cycle"):
        threshold = _THRESHOLD_FLUX
        checker_code = checker
        compare_type = 1
    else:
        threshold = dict(_THRESHOLD_FIXED_GT_0)
        checker_code = "fixed"
        compare_type = 2

    requires_field = scope in ("field", "fields")
    name = f"自定义（{method}:{checker}{':'+variant if variant else ''}）"
    return {
        "templateCode": template_code,
        "templateName": name,
        "methodCode": method,
        "checkerCode": checker_code,
        "checkerDescription": name,
        "checkerCompareType": compare_type,
        "requires_field": requires_field,
        "threshold": dict(threshold),
    }, None


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


def _get_entity_id(client, pid, table_guid):
    """获取表的 qualityJob entityId（DQC 监控实体）"""
    jobs = _safe_call(client, "listQualityJobs", projectId=pid,
                      tableGuid=table_guid, pageSize=1)
    if isinstance(jobs, list) and jobs:
        return jobs[0].get("entityId") or jobs[0].get("id")
    return None


def _build_rule(template_key, args, pid, table_name, db_type, table_guid, database):
    """构建规则对象。template_key 可以是 TEMPLATE_SHORTCUTS 的快捷名，
    或以 SYSTEM: 开头的原生 templateCode（逃生舱，适用于脚本未收录的模板）。"""
    # 固化模板 + 用户自定义阈值 → 自动升级到可配模板
    UPGRADE_MAP = {
        "row_count_gt0": "row_count_fixed",    # fixed:0 → fixed（阈值可配）
        "null_count_0": "null_count_fixed",     # fixed:0 → fixed（阈值可配）
        "duplicate_count_0": "duplicate_count_fixed",
        "duplicates_multi_0": "duplicates_multi_0",  # 保持
    }
    if args.passed_value is not None or args.critical_value is not None:
        upgraded = UPGRADE_MAP.get(template_key)
        if upgraded and upgraded != template_key:
            template_key = upgraded

    # 逃生舱：直接传 templateCode（SYSTEM:... 开头）时自动构造模板
    if template_key.startswith("SYSTEM:"):
        tmpl, err = _build_template_from_code(template_key)
        if err:
            return None, err
    else:
        tmpl = TEMPLATE_SHORTCUTS.get(template_key)
        if not tmpl:
            hint = "，或直接传完整 templateCode 如 SYSTEM:field:avg:flux:1_7_1m_bizdate"
            return None, f"未知模板: {template_key}\n可用模板: {', '.join(TEMPLATE_SHORTCUTS.keys())}{hint}"

    # 多字段模板（scope=fields）：--fields 必须是逗号分隔 / --field 单个
    has_fields_scope = "fields:" in tmpl["templateCode"]
    if tmpl.get("requires_field") and not (args.field or args.fields):
        hint = "--fields field1,field2" if has_fields_scope else "--field <colName>"
        return None, f"模板 {template_key} 需要 {hint} 参数"

    # 基础阈值
    threshold = dict(tmpl["threshold"])
    # 用户覆盖
    if args.passed_value is not None and "passed" in threshold:
        threshold["passed"] = dict(threshold["passed"])
        threshold["passed"]["value"] = str(args.passed_value)
        # 阻塞阈值自动联动（如果用户没有显式指定 critical）
        if args.critical_value is None and "critical" in threshold:
            threshold["critical"] = dict(threshold["critical"])
            threshold["critical"]["value"] = str(args.passed_value)
    if args.critical_value is not None and "critical" in threshold:
        threshold["critical"] = dict(threshold["critical"])
        threshold["critical"]["value"] = str(args.critical_value)

    rule_name = args.name or tmpl["templateName"]
    if args.field:
        rule_name = f"{args.field}_{rule_name}" if not args.name else args.name

    rule = {
        "templateCode": tmpl["templateCode"],
        "templateName": tmpl["templateName"],
        "ruleName": rule_name,
        "methodCode": tmpl["methodCode"],
        "checkerCode": tmpl["checkerCode"],
        "checkerDescription": tmpl.get("checkerDescription", ""),
        "checkerCompareType": tmpl.get("checkerCompareType", 2),
        "checkerSetting": {
            "threshold": threshold,
            "empty": False,
        },
        "blockType": args.block_type,
        "enabled": True,
        "tableName": table_name,
        "tableGuid": table_guid,
        "database": database,
        "dbType": db_type,
        "dataScope": 0,
        "whetherToFilterDirtyData": False,
        "ruleTemplate": {
            "code": tmpl["templateCode"],
            "name": tmpl["templateName"],
        },
        "sourceSystem": "agent",
    }

    # methodSetting：单字段 field / 多字段 fields
    if args.fields:
        field_list = [f.strip() for f in args.fields.split(",") if f.strip()]
        if field_list:
            rule["methodSetting"] = {"field": None, "fields": field_list, "scope": [], "SQL": None}
    elif args.field:
        rule["methodSetting"] = {"field": args.field, "scope": [], "SQL": None}

    if args.filter:
        rule["dataFilter"] = args.filter

    return rule, None


def main():
    parser = argparse.ArgumentParser(description="创建数据质量规则")
    parser.add_argument("--project-id", type=int, default=None)
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--table", help="表名")
    parser.add_argument("--template",
                        help="规则模板：快捷名（row_count_gt0 / col_avg_flux / col_distinct_dynamic / ... ，--list-templates 查全部）"
                             " 或完整 templateCode（如 SYSTEM:field:avg:flux:1_7_1m_bizdate）")
    parser.add_argument("--field", help="字段名（字段级规则需要）")
    parser.add_argument("--fields",
                        help="多字段，逗号分隔（仅 duplicates_multi_0 等 scope=fields 的模板用）")
    parser.add_argument("--name", help="自定义规则名称")
    parser.add_argument("--passed-value", type=float, help="通过阈值")
    parser.add_argument("--critical-value", type=float, help="阻塞阈值")
    parser.add_argument("--block-type", type=int, choices=[0, 1], default=0,
                        help="规则类型（0=弱规则, 1=强规则，默认0）")
    parser.add_argument("--filter", help="数据过滤条件（如 dt=$[yyyymmdd-1]）")
    parser.add_argument("--spec-file", help="Spec YAML 文件路径（由 dqc_spec_builder.py 生成）")
    parser.add_argument("--confirm", action="store_true", help="确认提交")
    parser.add_argument("--list-templates", action="store_true", help="列出可用模板")
    args = parser.parse_args()

    telemetry_start("dqc_create_rule.py", module="dqc",
                    projectId=args.project_id, table=args.table)

    client = BFFClient(quiet=True)

    # 列出模板
    if args.list_templates:
        groups = [
            ("表行数", ["row_count_gt0", "row_count_fixed", "row_count_flux",
                      "row_count_flux_1d", "row_count_flux_7d", "row_count_flux_1m",
                      "row_count_flux_month", "row_count_avg_7d", "row_count_avg_1m",
                      "row_count_cycle", "row_count_delta_1d", "row_count_delta_cycle",
                      "dynamic_threshold"]),
            ("表大小", ["table_size_fixed", "table_size_flux_1d", "table_size_flux_7d",
                      "table_size_flux_1m", "table_size_dynamic",
                      "table_size_delta_1d", "table_size_delta_cycle"]),
            ("字段 — 空值", ["null_count_0", "null_count_fixed", "null_percent"]),
            ("字段 — 重复值", ["duplicate_count_0", "duplicate_count_fixed",
                           "duplicate_percent", "duplicates_multi_0"]),
            ("字段 — 唯一值", ["col_distinct_fixed", "col_distinct_flux",
                           "col_distinct_dynamic", "col_distinct_percent"]),
            ("字段 — 聚合（min/avg/sum）", ["col_min_flux", "col_min_dynamic",
                                       "col_max_dynamic", "col_avg_flux",
                                       "col_avg_dynamic", "col_sum_flux",
                                       "col_sum_dynamic"]),
        ]
        print(f"\n  DQC 可用规则模板（共 {len(TEMPLATE_SHORTCUTS)} 条）:")
        for group_name, keys in groups:
            print(f"\n  【{group_name}】")
            for k in keys:
                t = TEMPLATE_SHORTCUTS.get(k)
                if not t:
                    continue
                hint = ""
                if t.get("requires_field"):
                    hint = " (需要 --field)" if "fields:" not in t["templateCode"] else " (需要 --fields)"
                print(f"    {k:<26s}  {t['templateName']}{hint}")

        print(f"\n  格式校验 / 枚举值 / 自定义 SQL 类：走 Spec 路径 →")
        print(f"    python dqc_spec_builder.py --list   # 看 Spec 级模板（含 regex/email/enum）")
        print(f"    python dqc_spec_builder.py --template col_regex --field phone --regex '^\\d{{11}}$' -o rules.yaml")
        print(f"    python dqc_create_rule.py --project-id <id> --table <名> --spec-file rules.yaml")
        print()
        print(f"  逃生舱 (未收录的 templateCode)：")
        print(f"    --template 'SYSTEM:field:avg:flux:1_7_1m_bizdate'   # 直接传完整 templateCode")
        print()
        return

    # 确认模式
    if args.confirm:
        if not os.path.exists(_PENDING_FILE):
            print(f"❌ 没有待确认的规则创建（{_PENDING_FILE} 不存在）")
            sys.exit(1)

        with open(_PENDING_FILE) as f:
            pending = json.load(f)

        pid = pending["projectId"]
        mode = pending.get("mode", "rule_list")
        entity_id = pending.get("entityId")
        table_guid = pending.get("tableGuid", "")
        db_type = pending.get("dbType", "ODPS")
        database = pending.get("database", "")

        payload = {
            "projectId": pid,
            "tableGuid": table_guid,
            "dbType": db_type,
            "database": database,
        }
        if entity_id:
            payload["qualityJobId"] = entity_id

        if mode == "spec":
            spec = pending["ruleSpec"]
            print(f"\n  通过 Spec 提交创建规则")
            payload["ruleSpec"] = spec
        else:
            rule = pending["rule"]
            print(f"\n  提交创建规则: {rule['ruleName']}")
            print(f"  表: {rule['tableName']}")
            print(f"  模板: {rule['templateName']}")
            payload["ruleList"] = [rule]

        result = _api_call(client, "batchCreateRules", **payload)
        os.remove(_PENDING_FILE)

        print(f"\n  ✅ 规则创建成功")
        if isinstance(result, list):
            print(f"     创建了 {len(result)} 条规则, ruleIds: {result}")
            for rid in result:
                print(f"\n  下一步（修改规则）:")
                print(f"    python dqc_update_rule.py --project-id {pid} --rule-id {rid}")
        elif isinstance(result, dict):
            print(f"     returnCode: {result.get('returnCode', result)}")

        telemetry_end(result={"projectId": pid, "action": "created",
                              "ruleName": rule["ruleName"]})
        return

    # ── Spec 文件模式 ──
    if args.spec_file:
        if not args.table:
            print(f"❌ --spec-file 需要同时指定 --table")
            sys.exit(1)
        pid = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)

        # 解析表（含存在性校验）
        profile = resolve_table(client, pid, args.table)
        database = profile["database"]
        ds_type = profile["dbType"]
        table_guid = profile["tableGuid"]
        table_name = profile["tableName"]
        entity_id = _get_entity_id(client, pid, table_guid)

        with open(args.spec_file) as f:
            spec_content = f.read()

        # 去掉注释行
        spec_lines = [l for l in spec_content.split('\n') if not l.strip().startswith('#')]
        spec_clean = '\n'.join(spec_lines).strip()

        print(f"\n{'=' * 60}")
        print(f"  通过 Spec 创建规则")
        print(f"  {'─' * 55}")
        print(f"    表名:       {table_name}")
        print(f"    表 GUID:    {table_guid}")
        print(f"    Spec 文件:  {args.spec_file}")
        print(f"\n  Spec 内容:")
        for line in spec_clean.split('\n'):
            print(f"    {line}")

        # 保存 pending（用 spec 模式）
        os.makedirs(os.path.dirname(_PENDING_FILE), exist_ok=True)
        with open(_PENDING_FILE, 'w') as f:
            json.dump({
                "projectId": pid,
                "mode": "spec",
                "ruleSpec": spec_clean,
                "entityId": entity_id,
                "tableGuid": table_guid,
                "dbType": ds_type,
                "database": database,
                "timestamp": datetime.now().isoformat(),
            }, f, ensure_ascii=False, indent=2)

        print(f"\n  ⚠️ 确认后执行:")
        print(f"    python dqc_create_rule.py --confirm")
        print()
        telemetry_end(result={"projectId": pid, "action": "spec_pending", "table": args.table})
        return

    # ── 模板创建模式 ──
    if not args.table or not args.template:
        print(f"❌ 请指定 --table 和 (--template 或 --spec-file)")
        print(f"   可用模板: {', '.join(TEMPLATE_SHORTCUTS.keys())}")
        print(f"   Spec 模式: python dqc_create_rule.py --table <表名> --spec-file rules.yaml")
        sys.exit(1)

    pid = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)

    # 解析表（含存在性校验，支持 'db.table' 短名）
    profile = resolve_table(client, pid, args.table)
    database = profile["database"]
    ds_type = profile["dbType"]
    table_guid = profile["tableGuid"]
    table_name = profile["tableName"]
    entity_id = _get_entity_id(client, pid, table_guid)

    # 构建规则
    rule, err = _build_rule(args.template, args, pid, table_name, ds_type,
                             table_guid, database)
    if err:
        print(f"❌ {err}")
        sys.exit(1)

    # 展示
    block_label = BLOCK_MAP.get(args.block_type, "?")
    threshold = (rule.get("checkerSetting") or {}).get("threshold") or {}
    passed = threshold.get("passed") or {}
    critical = threshold.get("critical") or {}

    print()
    print(f"{'=' * 60}")
    print(f"  创建规则预览")
    print(f"  {'─' * 55}")
    print(f"    规则名:     {rule['ruleName']}")
    print(f"    表名:       {table_name}")
    print(f"    表 GUID:    {table_guid}")
    print(f"    模板:       {rule['templateName']} ({rule['templateCode']})")
    print(f"    规则类型:   {block_label}")
    if args.field:
        print(f"    字段:       {args.field}")
    if args.filter:
        print(f"    数据过滤:   {args.filter}")
    print(f"\n  阈值配置:")
    if passed:
        print(f"    通过条件:   {passed.get('operator', '')} {passed.get('value', '')}")
    if critical:
        print(f"    阻塞条件:   {critical.get('operator', '')} {critical.get('value', '')}")
    if entity_id:
        print(f"\n  监控实体:   entityId={entity_id}")
    else:
        print(f"\n  ℹ️  该表尚无监控实体，创建规则时会自动创建")

    # 保存 pending
    os.makedirs(os.path.dirname(_PENDING_FILE), exist_ok=True)
    with open(_PENDING_FILE, 'w') as f:
        json.dump({
            "projectId": pid,
            "rule": rule,
            "entityId": entity_id,
            "tableGuid": table_guid or "",
            "dbType": ds_type,
            "database": database,
            "timestamp": datetime.now().isoformat(),
        }, f, ensure_ascii=False, indent=2)

    print(f"\n  ⚠️ 确认后执行:")
    print(f"    python dqc_create_rule.py --confirm")
    print()

    telemetry_end(result={"projectId": pid, "action": "pending",
                          "template": args.template, "table": args.table})


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        telemetry_fail("dqc_create_rule.py", "dqc", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
