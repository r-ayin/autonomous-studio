#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DQC Spec 构建器 —— 从用户意图生成合法的 Spec YAML

Spec 是 DQC 规则的声明式配置格式，一段 YAML 可描述多条规则。
本脚本只负责生成 Spec，不负责提交。提交用 dqc_create_rule.py --spec-file。

用法:
    # 从模板生成 Spec
    python dqc_spec_builder.py --template row_count_gt0
    python dqc_spec_builder.py --template null_count_0 --field birthday
    python dqc_spec_builder.py --template row_count_fixed --passed-value 350 --severity High

    # 组合多条规则
    python dqc_spec_builder.py --template row_count_gt0 --template null_count_0 --field id

    # 自定义 SQL 规则
    python dqc_spec_builder.py --custom-sql "SELECT COUNT(*) FROM \${table} WHERE status IS NULL" --name 空状态检查

    # 输出到文件
    python dqc_spec_builder.py --template row_count_gt0 -o rules.yaml

    # 列出所有模板
    python dqc_spec_builder.py --list

    # 查看已有规则的 Spec（从 listRules 导出）
    python dqc_spec_builder.py --export --project-id 14255 --table jhr_mc_test

Spec 格式（YAML rules 片段）:
    - templateId: SYSTEM:table:table_count:fixed:0
      name: 表行数大于0
      severity: High
      enabled: true
"""

import argparse
import json
import os
import sys

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 模板定义：快捷名 → Spec 片段生成
# flag 说明：
#   needs_field          字段级（单字段）
#   needs_fields         字段级（多字段，scope=fields）
#   needs_threshold      可配 --passed-value（fixed 类）
#   needs_warn_fail      可配 --warn / --fail（flux / avg / cycle 类）
#   needs_regex          需要 --regex（正则校验）
#   needs_format         需要 --format（日期格式）
#   needs_values         需要 --values（枚举值清单）
_DEFAULT_FLUX_WARN = "when not between -0.1 and 0.1"
_DEFAULT_FLUX_FAIL = "when not between -0.2 and 0.2"

def _flux(code, name):
    return {"templateId": code, "name": name, "needs_warn_fail": True,
            "default_warn": _DEFAULT_FLUX_WARN, "default_fail": _DEFAULT_FLUX_FAIL}
def _flux_f(code, name):
    d = _flux(code, name); d["needs_field"] = True; return d
def _dyn(code, name):
    return {"templateId": code, "name": name}
def _dyn_f(code, name):
    d = _dyn(code, name); d["needs_field"] = True; return d
def _fixed_f(code, name, default_pass=None, needs_threshold=True):
    return {"templateId": code, "name": name, "needs_field": True,
            "needs_threshold": needs_threshold,
            **({"default_pass": default_pass} if default_pass else {})}


TEMPLATES = {
    # ─── 表行数 ─────────────────────────────────────
    "row_count_gt0": {"templateId": "SYSTEM:table:table_count:fixed:0",
                     "name": "表行数大于0", "default_severity": "High"},
    "row_count_fixed": {"templateId": "SYSTEM:table:table_count:fixed",
                       "name": "表行数，固定值", "needs_threshold": True, "default_pass": "when > 0"},
    "row_count_flux": _flux("SYSTEM:table:table_count:flux:1_7_1m_bizdate",
                            "表行数，1/7/30天波动率"),
    "row_count_flux_1d": _flux("SYSTEM:table:table_count:flux:1_bizdate", "表行数，1天波动率"),
    "row_count_flux_7d": _flux("SYSTEM:table:table_count:flux:7_bizdate", "表行数，7天波动率"),
    "row_count_flux_1m": _flux("SYSTEM:table:table_count:flux:1m_bizdate", "表行数，30天波动率"),
    "row_count_flux_month": _flux("SYSTEM:table:table_count:flux:1_7_1m_1st_bizdate",
                                  "表行数，1/7/30天及月初波动率"),
    "row_count_avg_7d": _flux("SYSTEM:table:table_count:avg:7_bizdate", "表行数，7天均值波动率"),
    "row_count_avg_1m": _flux("SYSTEM:table:table_count:avg:1m_bizdate", "表行数，30天均值波动率"),
    "row_count_cycle": _flux("SYSTEM:table:table_count:cycle:latest_bizdate", "表行数，上周期波动率"),
    "row_count_delta_1d": {"templateId": "SYSTEM:table:table_count_delta:fixed:1_bizdate",
                          "name": "表行数，1天差值", "needs_threshold": True, "default_pass": "when > 0"},
    "row_count_delta_cycle": {"templateId": "SYSTEM:table:table_count_delta:fixed:latest_bizdate",
                             "name": "表行数，上周期差值", "needs_threshold": True, "default_pass": "when > 0"},
    "dynamic_threshold": _dyn("SYSTEM:table:table_count:dynamic_threshold", "表行数，动态阈值"),

    # ─── 表大小 ─────────────────────────────────────
    "table_size_fixed": {"templateId": "SYSTEM:table:table_size:fixed", "name": "表大小，固定值",
                        "needs_threshold": True, "default_pass": "when > 0"},
    "table_size_flux_1d": _flux("SYSTEM:table:table_size:flux:1_bizdate", "表大小，1天波动率"),
    "table_size_flux_7d": _flux("SYSTEM:table:table_size:flux:7_bizdate", "表大小，7天波动率"),
    "table_size_flux_1m": _flux("SYSTEM:table:table_size:flux:1m_bizdate", "表大小，30天波动率"),
    "table_size_dynamic": _dyn("SYSTEM:table:table_size:dynamic_threshold", "表大小，动态阈值"),
    "table_size_delta_1d": {"templateId": "SYSTEM:table:table_size_delta:fixed:1_bizdate",
                           "name": "表大小，1天差值", "needs_threshold": True, "default_pass": "when > 0"},
    "table_size_delta_cycle": {"templateId": "SYSTEM:table:table_size_delta:fixed:latest_bizdate",
                              "name": "表大小，上周期差值", "needs_threshold": True, "default_pass": "when > 0"},

    # ─── 字段 — 空值 ─────────────────────────────────
    "null_count_0": {"templateId": "SYSTEM:field:null_value:fixed:0", "name": "空值记录数为0",
                    "needs_field": True},
    "null_count_fixed": _fixed_f("SYSTEM:field:null_value:fixed", "空值个数，固定值", "when = 0"),
    "null_percent": _fixed_f("SYSTEM:field:null_value_percent:fixed", "空值占比，固定值", "when <= 0.05"),

    # ─── 字段 — 重复值 ───────────────────────────────
    "duplicate_count_0": {"templateId": "SYSTEM:field:duplicated_count:fixed:0",
                         "name": "字段重复值为0", "needs_field": True},
    "duplicate_count_fixed": _fixed_f("SYSTEM:field:duplicated_count:fixed",
                                      "重复值个数，固定值", "when = 0"),
    "duplicate_percent": _fixed_f("SYSTEM:field:duplicated_percent:fixed",
                                  "重复值占比，固定值", "when <= 0.05"),
    "duplicates_multi_0": {"templateId": "SYSTEM:fields:duplicated_count:fixed:0",
                          "name": "多字段重复值为0（联合主键）", "needs_fields": True},

    # ─── 字段 — 唯一值 ───────────────────────────────
    "col_distinct_fixed": _fixed_f("SYSTEM:field:count_distinct:fixed", "唯一值个数，固定值",
                                   "when > 0"),
    "col_distinct_flux": _flux_f("SYSTEM:field:count_distinct:flux:1_7_1m_bizdate",
                                 "唯一值个数，1/7/30天波动率"),
    "col_distinct_dynamic": _dyn_f("SYSTEM:field:count_distinct:dynamic_threshold",
                                   "唯一值个数，动态阈值"),
    "col_distinct_percent": _fixed_f("SYSTEM:field:count_distinct_percent:fixed",
                                     "唯一值占比，固定值", "when > 0"),

    # ─── 字段 — 聚合（min/max/avg/sum）────────────────
    "col_min_flux": _flux_f("SYSTEM:field:min:flux:1_7_1m_bizdate", "最小值，1/7/30天波动率"),
    "col_min_dynamic": _dyn_f("SYSTEM:field:min:dynamic_threshold", "最小值，动态阈值"),
    "col_max_dynamic": _dyn_f("SYSTEM:field:max:dynamic_threshold", "最大值，动态阈值"),
    "col_avg_flux": _flux_f("SYSTEM:field:avg:flux:1_7_1m_bizdate", "平均值，1/7/30天波动率"),
    "col_avg_dynamic": _dyn_f("SYSTEM:field:avg:dynamic_threshold", "平均值，动态阈值"),
    "col_sum_flux": _flux_f("SYSTEM:field:sum:flux:1_7_1m_bizdate", "汇总值，1/7/30天波动率"),
    "col_sum_dynamic": _dyn_f("SYSTEM:field:sum:dynamic_threshold", "汇总值，动态阈值"),

    # ─── 字段 — 格式校验 ─────────────────────────────
    "col_regex": {"templateId": "SYSTEM:field:pattern_match:fixed", "name": "正则校验",
                  "needs_field": True, "needs_regex": True},
    "col_date_format": {"templateId": "SYSTEM:field:pattern_match_date:fixed", "name": "日期格式校验",
                        "needs_field": True, "needs_format": True},
    "col_email": {"templateId": "SYSTEM:field:pattern_match_email:fixed", "name": "电子邮箱格式校验",
                  "needs_field": True},
    "col_idcard": {"templateId": "SYSTEM:field:pattern_match_idcard:fixed", "name": "身份证格式校验",
                   "needs_field": True},
    "col_mobile": {"templateId": "SYSTEM:field:pattern_match_mobile_number:fixed",
                   "name": "手机号码格式校验", "needs_field": True},

    # ─── 字段 — 枚举值 ───────────────────────────────
    "col_enum_0": {"templateId": "SYSTEM:field:count_not_in:fixed:0",
                  "name": "枚举值不匹配行数为0", "needs_field": True, "needs_values": True},
    "col_enum_fixed": {"templateId": "SYSTEM:field:count_not_in:fixed",
                       "name": "枚举值不匹配行数，固定值", "needs_field": True,
                       "needs_values": True, "needs_threshold": True, "default_pass": "when = 0"},
    "col_distinct_enum": {"templateId": "SYSTEM:field:count_distinct_not_in:fixed",
                          "name": "枚举值不匹配唯一值个数，固定值", "needs_field": True,
                          "needs_values": True, "needs_threshold": True, "default_pass": "when = 0"},
}


def build_spec_entry(template_key, field=None, fields=None, passed_value=None, severity=None,
                     warn=None, fail=None, name=None, filter_expr=None,
                     regex=None, format_=None, values=None):
    """构建单条 Spec YAML 条目"""
    tmpl = TEMPLATES.get(template_key)
    if not tmpl:
        return None, f"未知模板: {template_key}"

    if tmpl.get("needs_field") and not field:
        return None, f"模板 {template_key} 需要 --field 参数"
    if tmpl.get("needs_fields") and not fields:
        return None, f"模板 {template_key} 需要 --fields field1,field2 参数（多字段）"
    if tmpl.get("needs_regex") and not regex:
        return None, f"模板 {template_key} 需要 --regex 参数"
    if tmpl.get("needs_format") and not format_:
        return None, f"模板 {template_key} 需要 --format 参数（日期格式如 yyyy-MM-dd）"
    if tmpl.get("needs_values") and not values:
        return None, f"模板 {template_key} 需要 --values 参数（枚举值逗号分隔，如 A,B,C）"

    lines = []
    lines.append(f"- templateId: {tmpl['templateId']}")
    lines.append(f"  name: {name or tmpl['name']}")
    lines.append(f"  severity: {severity or tmpl.get('default_severity', 'Normal')}")
    lines.append(f"  enabled: true")

    # fields（单字段 / 多字段）
    field_list = []
    if fields:
        field_list = [x.strip() for x in fields.split(",") if x.strip()]
    elif field:
        field_list = [field]
    if field_list:
        lines.append(f"  fields:")
        for fld in field_list:
            lines.append(f"  - {fld}")

    # valid（正则 / 格式 / 枚举）
    if regex or format_ or values:
        lines.append(f"  valid:")
        if regex:
            lines.append(f"    regex: \"{regex}\"")
        if format_:
            lines.append(f"    format: \"{format_}\"")
        if values:
            vlist = [x.strip() for x in values.split(",") if x.strip()]
            vals_yaml = ", ".join(f"\"{v}\"" for v in vlist)
            lines.append(f"    values: [{vals_yaml}]")

    if tmpl.get("needs_warn_fail"):
        w = warn or tmpl.get("default_warn", "")
        f_val = fail or tmpl.get("default_fail", "")
        if w:
            lines.append(f"  warn:")
            lines.append(f"  - {w}")
        if f_val:
            lines.append(f"  fail:")
            lines.append(f"  - {f_val}")
    elif tmpl.get("needs_threshold"):
        if passed_value is not None:
            lines.append(f"  pass:")
            lines.append(f"  - when > {passed_value}")
        elif tmpl.get("default_pass"):
            lines.append(f"  pass:")
            lines.append(f"  - {tmpl['default_pass']}")

    if filter_expr:
        lines.append(f"  filter: \"{filter_expr}\"")

    return "\n".join(lines), None


def build_custom_sql_spec(sql, name, severity="Normal"):
    """构建自定义 SQL 规则 Spec"""
    lines = []
    lines.append(f"- assertion: \"{name or 'custom_metric'} > 0\"")
    lines.append(f"  {name or 'custom_metric'}:")
    lines.append(f"    query: \"{sql}\"")
    lines.append(f"  name: {name or '自定义SQL检查'}")
    lines.append(f"  severity: {severity}")
    lines.append(f"  enabled: true")
    return "\n".join(lines)


def export_rules_as_spec(client, pid, table_guid):
    """从 listRules 导出已有规则为 Spec"""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "core"))
    from bff_client import BFFClient

    api_meta = client.api_index.get("listRules")
    result = client._do_request("listRules", api_meta,
                                 projectId=pid, tableGuid=table_guid, pageSize=200)
    items = result.get("data", {}).get("list", [])

    specs = []
    for r in items:
        spec = r.get("spec")
        if spec:
            specs.append(spec.strip())

    return "\n".join(specs) if specs else None


def main():
    parser = argparse.ArgumentParser(
        description="DQC Spec 构建器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python dqc_spec_builder.py --list
  python dqc_spec_builder.py --template row_count_gt0
  python dqc_spec_builder.py --template null_count_0 --field birthday
  python dqc_spec_builder.py --template row_count_fixed --passed-value 350 --severity High
  python dqc_spec_builder.py --custom-sql "SELECT COUNT(*) FROM t WHERE x IS NULL" --name null_check
  python dqc_spec_builder.py --export --project-id 14255 --table jhr_mc_test
""")
    parser.add_argument("--template", action="append", help="规则模板（可多次指定）")
    parser.add_argument("--field", help="字段名（字段级规则需要）")
    parser.add_argument("--fields", help="多字段，逗号分隔（scope=fields 模板用，如 duplicates_multi_0）")
    parser.add_argument("--passed-value", type=float, help="通过阈值")
    parser.add_argument("--severity", choices=["Normal", "High"], default="Normal",
                        help="严重等级（Normal=弱规则, High=强规则）")
    parser.add_argument("--name", help="自定义规则名称")
    parser.add_argument("--warn", help="告警条件（波动率规则）")
    parser.add_argument("--fail", help="阻塞条件（波动率规则）")
    parser.add_argument("--filter", help="数据过滤（如 dt=$[yyyymmdd-1]）")
    parser.add_argument("--regex", help="正则表达式（col_regex 模板用）")
    parser.add_argument("--format", dest="format_", help="日期格式（col_date_format 模板用，如 yyyy-MM-dd）")
    parser.add_argument("--values", help="枚举值清单，逗号分隔（col_enum_* 模板用）")
    parser.add_argument("--custom-sql", help="自定义 SQL 查询")
    parser.add_argument("-o", "--output", help="输出文件路径")
    parser.add_argument("--list", action="store_true", help="列出可用模板")
    parser.add_argument("--export", action="store_true", help="导出已有规则为 Spec")
    parser.add_argument("--project-id", type=int)
    parser.add_argument("--table", help="表名（导出时用）")
    args = parser.parse_args()

    # 列出模板
    if args.list:
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
            ("字段 — 聚合", ["col_min_flux", "col_min_dynamic", "col_max_dynamic",
                          "col_avg_flux", "col_avg_dynamic", "col_sum_flux",
                          "col_sum_dynamic"]),
            ("字段 — 格式校验", ["col_regex", "col_date_format", "col_email",
                             "col_idcard", "col_mobile"]),
            ("字段 — 枚举值", ["col_enum_0", "col_enum_fixed", "col_distinct_enum"]),
        ]
        print(f"\n  DQC Spec 可用模板（共 {len(TEMPLATES)} 条）:")
        for group_name, keys in groups:
            print(f"\n  【{group_name}】")
            for k in keys:
                tmpl = TEMPLATES.get(k)
                if not tmpl:
                    continue
                hints = []
                if tmpl.get("needs_field"): hints.append("--field")
                if tmpl.get("needs_fields"): hints.append("--fields")
                if tmpl.get("needs_regex"): hints.append("--regex")
                if tmpl.get("needs_format"): hints.append("--format")
                if tmpl.get("needs_values"): hints.append("--values")
                if tmpl.get("needs_threshold"): hints.append("--passed-value (可选)")
                if tmpl.get("needs_warn_fail"): hints.append("--warn/--fail (可选)")
                hint_str = f"  [{', '.join(hints)}]" if hints else ""
                print(f"    {k:<25s}  {tmpl['name']}{hint_str}")
        print(f"\n  示例:")
        print(f"    python dqc_spec_builder.py --template row_count_gt0 --severity High")
        print(f"    python dqc_spec_builder.py --template col_avg_flux --field price")
        print(f"    python dqc_spec_builder.py --template col_regex --field phone --regex '^\\d{{11}}$'")
        print(f"    python dqc_spec_builder.py --template col_enum_0 --field status --values 'A,B,C'")
        print(f"    python dqc_spec_builder.py --template duplicates_multi_0 --fields user_id,date")
        print()
        return

    # 导出模式
    if args.export:
        if not args.project_id or not args.table:
            print("❌ 导出需要 --project-id 和 --table")
            sys.exit(1)
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "core"))
        from bff_client import BFFClient
        from table_profile import resolve as resolve_table
        client = BFFClient(quiet=True)
        pid = args.project_id

        # 解析表（含存在性校验）
        profile = resolve_table(client, pid, args.table)
        table_guid = profile["tableGuid"]
        table_name = profile["tableName"]

        spec = export_rules_as_spec(client, pid, table_guid)
        if spec:
            print(f"# {table_name} 已有规则 Spec (projectId={pid})")
            print(spec)
            if args.output:
                with open(args.output, 'w') as f:
                    f.write(f"# {table_name} 规则 Spec\n")
                    f.write(spec + "\n")
                print(f"\n  ✅ 已保存到 {args.output}")
        else:
            print(f"  该表无已有规则或规则无 Spec 字段")
        return

    # 构建 Spec
    entries = []

    if args.template:
        for tmpl_key in args.template:
            entry, err = build_spec_entry(
                tmpl_key, field=args.field, fields=args.fields,
                passed_value=args.passed_value,
                severity=args.severity, warn=args.warn, fail=args.fail,
                name=args.name, filter_expr=args.filter,
                regex=args.regex, format_=args.format_, values=args.values)
            if err:
                print(f"❌ {err}")
                sys.exit(1)
            entries.append(entry)

    if args.custom_sql:
        entry = build_custom_sql_spec(args.custom_sql, args.name, args.severity)
        entries.append(entry)

    if not entries:
        print("❌ 请指定 --template 或 --custom-sql")
        print("   列出模板: python dqc_spec_builder.py --list")
        sys.exit(1)

    spec = "\n".join(entries)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(spec + "\n")
        print(f"  ✅ Spec 已保存到 {args.output}")
        print(f"\n  下一步:")
        print(f"    python dqc_create_rule.py --project-id <ID> --table <表名> --spec-file {args.output}")
    else:
        print(spec)
        print(f"\n  💡 用 -o rules.yaml 保存到文件")
        print(f"  💡 提交: python dqc_create_rule.py --project-id <ID> --table <表名> --spec-file rules.yaml")


if __name__ == "__main__":
    main()
