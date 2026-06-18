#!/usr/bin/env python3
"""遥测契约 —— 客户端采集 & 服务端消费的唯一 schema 定义

本文件是 telemetry 数据的 Single Source of Truth。
客户端（telemetry.py）按此 schema 写入，服务端按此 schema 校验和消费。

使用方式:
    # 校验单条记录
    from telemetry_schema import validate_event, validate_batch

    ok, errors = validate_event(record_dict)

    # 校验上报批次
    ok, errors = validate_batch(batch_dict)

    # 获取当前 schema 版本
    from telemetry_schema import SCHEMA_VERSION

CLI:
    python telemetry_schema.py                         # 打印 schema JSON
    python telemetry_schema.py --validate batch.json   # 校验文件
"""

# ─── Schema 版本 ──────────────────────────────────────────────
# 变更规则：
#   - 新增 optional 字段：minor +1（向后兼容，服务端忽略未知字段）
#   - 删除/改类型/新增 required 字段：major +1（需双方同步升级）

SCHEMA_VERSION = "1.0"

# ─── Event Schema ─────────────────────────────────────────────
# 每条遥测记录的字段定义。
# required: 客户端必须填写，服务端可依赖其存在
# optional: 客户端按场景填写，服务端需容忍缺失

EVENT_SCHEMA = {
    # ── 必填字段 ──
    "ts":           {"type": "string",  "required": True,
                     "description": "ISO 8601 时间戳（秒精度），如 2026-04-04T14:30:00"},
    "session_id":   {"type": "string",  "required": True,
                     "description": "会话 ID（同一次对话内所有脚本共享），12 位 hex"},
    "script":       {"type": "string",  "required": True,
                     "description": "脚本文件名，如 ops_overview.py"},
    "module":       {"type": "string",  "required": True,
                     "description": "所属模块名，如 task-ops、discovery"},
    "duration_ms":  {"type": "int",     "required": True,
                     "description": "执行耗时（毫秒）"},
    "exit_code":    {"type": "int",     "required": True,
                     "description": "退出码，0=成功，非0=失败"},

    # ── 可选字段：routing 层 ──
    "intent":       {"type": "string",  "required": False,
                     "description": "agent 匹配到的 routing intent 描述（用于计算 routing 命中率）"},

    # ── 可选字段：业务上下文 ──
    "project_id":   {"type": "string",  "required": False,
                     "description": "DataWorks 工作空间 ID"},
    "date":         {"type": "string",  "required": False,
                     "description": "业务日期（非执行日期），如 2026-04-03"},
    "node_id":      {"type": "string",  "required": False,
                     "description": "任务节点 ID"},
    "keyword":      {"type": "string",  "required": False,
                     "description": "搜索关键词"},
    "status":       {"type": "string",  "required": False,
                     "description": "过滤条件中的状态值"},
    "args":         {"type": "dict",    "required": False,
                     "description": "其他上下文参数（不在上述列表中的 kwargs）"},

    # ── 可选字段：脚本结果摘要 ──
    "result":       {"type": "dict",    "required": False,
                     "description": "脚本输出的结构化摘要（字段因脚本而异，见 RESULT_SCHEMAS）"},
}

# ─── Result 子 Schema（按 script 分类） ────────────────────────
# result 字段的内容因脚本而异。这里列出已知的 result 结构，
# 用于服务端做精确解析。未列出的 script 的 result 视为自由 dict。

RESULT_SCHEMAS = {
    "ops_overview.py": {
        "severity":         {"type": "string",  "description": "ok | warning | critical"},
        "error_rank_count": {"type": "int",     "description": "错误排行榜条目数"},
    },
    "query_instances.py": {
        "count":            {"type": "int",     "description": "返回的实例数"},
        "failed_count":     {"type": "int",     "description": "失败实例数"},
    },
    "task_detail.py": {
        "instance_count":   {"type": "int",     "description": "实例总数"},
        "failed_count":     {"type": "int",     "description": "失败实例数"},
    },
    "di_overview.py": {
        "offline_fail_count":    {"type": "int", "description": "离线失败任务数"},
        "realtime_alarm_count":  {"type": "int", "description": "实时告警数"},
    },
    "daily_check.py": {
        "severity":         {"type": "string",  "description": "ok | warning | critical"},
        "error_rank_count": {"type": "int",     "description": "错误排行榜条目数"},
    },
    "search_nodes.py": {
        "runtime_count":    {"type": "int",     "description": "运行态匹配数"},
        "dev_count":        {"type": "int",     "description": "开发态匹配数"},
    },
    "query_partitions.py": {
        "total_partitions": {"type": "int",     "description": "分区总数"},
        "latest":           {"type": "string",  "description": "最新分区值"},
    },
}


# ─── Batch Schema（上报批次格式） ────────────────────────────
# 客户端按批次上报，每个批次包含元信息 + 事件列表。

BATCH_SCHEMA = {
    "schema_version":  {"type": "string",  "required": True,
                        "description": "契约版本号，如 1.0"},
    "skill_name":      {"type": "string",  "required": True,
                        "description": "Skill 名称，如 dataworks"},
    "skill_version":   {"type": "string",  "required": True,
                        "description": "Skill 版本号（来自 profile.json）"},
    "env":             {"type": "string",  "required": True,
                        "description": "部署环境标识，如 public、private"},
    "uploaded_at":     {"type": "string",  "required": True,
                        "description": "批次上报时间（ISO 8601）"},
    "events":          {"type": "list",    "required": True,
                        "description": "遥测事件列表，每项符合 EVENT_SCHEMA"},
}


# ─── 校验函数 ─────────────────────────────────────────────────

_TYPE_MAP = {
    "string": str,
    "int": (int, float),  # 宽松：接受 float 形式的整数
    "dict": dict,
    "list": list,
}


def validate_event(record):
    """校验单条遥测记录，返回 (ok: bool, errors: list[str])"""
    errors = []
    if not isinstance(record, dict):
        return False, ["record 不是 dict"]

    for field, spec in EVENT_SCHEMA.items():
        val = record.get(field)
        if spec["required"] and val is None:
            errors.append(f"缺少必填字段: {field}")
            continue
        if val is not None:
            expected = _TYPE_MAP.get(spec["type"])
            if expected and not isinstance(val, expected):
                errors.append(f"{field}: 期望 {spec['type']}，实际 {type(val).__name__}")

    return len(errors) == 0, errors


def validate_batch(batch):
    """校验上报批次，返回 (ok: bool, errors: list[str])"""
    errors = []
    if not isinstance(batch, dict):
        return False, ["batch 不是 dict"]

    for field, spec in BATCH_SCHEMA.items():
        val = batch.get(field)
        if spec["required"] and val is None:
            errors.append(f"batch 缺少必填字段: {field}")

    # 版本兼容性检查
    ver = batch.get("schema_version", "")
    if ver and ver.split(".")[0] != SCHEMA_VERSION.split(".")[0]:
        errors.append(f"schema 主版本不兼容: batch={ver}, 当前={SCHEMA_VERSION}")

    # 校验每条事件
    events = batch.get("events", [])
    if not isinstance(events, list):
        errors.append("events 不是 list")
    else:
        for i, evt in enumerate(events):
            ok, evt_errors = validate_event(evt)
            if not ok:
                for e in evt_errors:
                    errors.append(f"events[{i}]: {e}")

    return len(errors) == 0, errors


# ─── 导出 JSON Schema（供服务端/文档使用） ────────────────────

def to_json_schema():
    """将 EVENT_SCHEMA 转换为标准 JSON Schema 格式"""
    type_mapping = {
        "string": "string",
        "int": "integer",
        "dict": "object",
        "list": "array",
    }
    properties = {}
    required = []
    for field, spec in EVENT_SCHEMA.items():
        properties[field] = {
            "type": type_mapping.get(spec["type"], "string"),
            "description": spec["description"],
        }
        if spec["required"]:
            required.append(field)

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


# ─── CLI ──────────────────────────────────────────────────────

def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="遥测契约 schema")
    parser.add_argument("--validate", metavar="FILE",
                        help="校验 JSON 文件（单条 event 或 batch）")
    parser.add_argument("--json-schema", action="store_true",
                        help="输出标准 JSON Schema 格式")
    args = parser.parse_args()

    if args.json_schema:
        print(json.dumps(to_json_schema(), indent=2, ensure_ascii=False))
        return

    if args.validate:
        with open(args.validate, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 自动判断是 batch 还是单条 event
        if "events" in data:
            ok, errors = validate_batch(data)
            label = "batch"
        else:
            ok, errors = validate_event(data)
            label = "event"

        if ok:
            print(f"校验通过 ✓ ({label})")
        else:
            print(f"校验失败 ({len(errors)} 个问题):")
            for e in errors:
                print(f"  ✗ {e}")
            raise SystemExit(1)
        return

    # 默认：打印 schema 摘要
    print(f"Telemetry Schema v{SCHEMA_VERSION}")
    print(f"\nEvent 字段 ({len(EVENT_SCHEMA)}):")
    for field, spec in EVENT_SCHEMA.items():
        req = "必填" if spec["required"] else "可选"
        print(f"  {field:<16} {spec['type']:<8} [{req}]  {spec['description']}")

    print(f"\nResult 子 Schema ({len(RESULT_SCHEMAS)} 个脚本):")
    for script, fields in RESULT_SCHEMAS.items():
        names = ", ".join(fields.keys())
        print(f"  {script:<25} → {names}")

    print(f"\nBatch 字段 ({len(BATCH_SCHEMA)}):")
    for field, spec in BATCH_SCHEMA.items():
        req = "必填" if spec["required"] else "可选"
        print(f"  {field:<20} {spec['type']:<8} [{req}]  {spec['description']}")


if __name__ == "__main__":
    main()
