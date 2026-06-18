#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""创建敏感数据识别任务（写操作，两阶段提交）

Phase 1（准备+预览）：
    python create_recognition_task.py --task-name test_abc --engine ODPS.ODPS --task-type Once

Phase 2（用户确认后执行）：
    python create_recognition_task.py --confirm

复杂识别范围 / 配置用 JSON 文件：
    python create_recognition_task.py --task-name xxx --engine ODPS.ODPS --config-json ./task.json

仅公有云。
"""

import argparse
import json
import sys

from bff_client import BFFClient


def _load_config_json(path):
    """加载复杂 object 参数（rangeList / taskConfig / emrConfigs）"""
    try:
        with open(path) as f:
            data = json.load(f)
    except OSError as e:
        print(f"读取 config-json 失败: {path} ({e})", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"config-json 不是合法 JSON: {path} ({e})", file=sys.stderr)
        sys.exit(1)
    # 接受两种形态：直接是完整 body dict，或含 rangeList/taskConfig/emrConfigs 三键的子集
    return data if isinstance(data, dict) else {}


def main():
    parser = argparse.ArgumentParser(
        description="创建敏感数据识别任务（写操作，两阶段：先 preview → 用户确认 → --confirm 执行）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--task-name", help="任务名（Phase 1 必填）")
    parser.add_argument("--task-type", choices=["Once", "Scheduled"], default="Once",
                        help="Once=单次执行（默认），Scheduled=定时")
    parser.add_argument("--engine", help="引擎类型 ODPS.ODPS/STARROCKS/DLF.LEGACY/HOLOGRES 等（Phase 1 必填）")
    parser.add_argument("--account-type", choices=["Master", "RAM"], default="Master",
                        help="账号类型（服务端必填；枚举 Master=主账号 / RAM=RAM子账号，默认 Master）")
    parser.add_argument("--account-id", help="RAM 子账号 ID（accountType=RAM 时必填）")
    parser.add_argument("--sampling-count", type=int, default=100,
                        help="每张表采样条数 1-200（服务端上限 200）。与任务耗时、识别准确率正相关：样本越多越准但越慢。默认 100（平衡）；想要更准传 200，想快速扫传 50")
    parser.add_argument("--scheduled-frequency", choices=["Day", "Week", "Month"],
                        help="定时周期（Scheduled 必填）")
    parser.add_argument("--scheduled-date", type=int,
                        help="定时日期 1-31（Week/Month 必填）")
    parser.add_argument("--scheduled-time", type=int,
                        help="定时秒数 0-86400（Scheduled 必填）")
    parser.add_argument("--config-json", help="rangeList/taskConfig/emrConfigs 的 JSON 文件路径（Once 类型 rangeList 不能空，必须具体到 project/schema 级）")
    parser.add_argument("--confirm", action="store_true", help="Phase 2: 执行已 preview 的写操作")
    args = parser.parse_args()

    client = BFFClient()

    if args.confirm:
        # Phase 2：执行 + 引导接 wait
        result = client.confirm_write()
        if isinstance(result, dict):
            tid = result.get("taskId")
            tname = result.get("taskName")
            status = result.get("taskStatus")
            if tid:
                print()
                print(f"✅ 任务已创建: taskId={tid}  taskName={tname}  taskStatus={status}")
                print(f"→ 轮询等执行结果: wait_recognition_task.py --task-id {tid}")
                print(f"→ 不等了先看一眼: list_recognition_tasks.py --task-id {tid}")
        return

    # Phase 1：准备 payload
    if not args.task_name or not args.engine:
        print("Phase 1 必填：--task-name 和 --engine", file=sys.stderr)
        print("→ 参考：create_recognition_task.py --task-name test_abc --engine ODPS.ODPS --task-type Once", file=sys.stderr)
        sys.exit(1)

    # samplingCount 边界（服务端上限 200）
    if not (1 <= args.sampling_count <= 200):
        print(f"❌ --sampling-count={args.sampling_count} 超出范围，服务端上限 200。与耗时、准确率正相关，默认 100", file=sys.stderr)
        sys.exit(1)

    payload = {
        "taskName": args.task_name,
        "taskType": args.task_type,
        "engineType": args.engine,
        "accountType": args.account_type,
        "samplingCount": args.sampling_count,
    }
    if args.account_type == "RAM":
        if not args.account_id:
            print("❌ accountType=RAM 时 --account-id 必填", file=sys.stderr)
            sys.exit(1)
        payload["accountId"] = args.account_id
    if args.scheduled_frequency:
        payload["scheduledFrequency"] = args.scheduled_frequency
    if args.scheduled_date is not None:
        payload["scheduledDate"] = args.scheduled_date
    if args.scheduled_time is not None:
        payload["scheduledTime"] = args.scheduled_time
    if args.config_json:
        extras = _load_config_json(args.config_json)
        # ⚠️ 识别目标（敏感类型）为租户级全局配置，服务端创建任务时不读 taskConfig.sensitiveTypes
        # 之前实测 agent 会尝试通过 taskConfig 自定义敏感类型排除，然后向用户谎报"已去掉 XX"
        # 这里显式拦截，防止 agent 自欺
        tc = extras.get("taskConfig") or {}
        forbidden = [k for k in ("sensitiveTypes", "sensitiveTypeNames", "excludeCategories",
                                 "includeCategories", "classificationTemplate") if k in tc]
        if forbidden:
            print(f"❌ config-json 的 taskConfig 含服务端忽略的字段: {forbidden}", file=sys.stderr)
            print("   敏感类型是**租户级全局配置**，创建任务时无法 per-task 排除或定制。", file=sys.stderr)
            print("   扫描对象 = listClassificationEnabledSensitiveTypeNames 返回的全部 leaf（本任务 46 种）。", file=sys.stderr)
            print("   要关闭某类型：去 DataWorks 控制台 → 数据保护伞 → 敏感类型管理，在租户级禁用。", file=sys.stderr)
            sys.exit(1)
        for k in ("rangeList", "taskConfig", "emrConfigs"):
            if k in extras:
                payload[k] = extras[k]

    # ── 0. 先 catalog 级 resolve：listMixedCatalogMeta 列引擎下所有可用目录 ──
    available_catalogs = []
    try:
        available_catalogs = client.load("listMixedCatalogMeta", engineType=args.engine) or []
    except Exception as e:
        print(f"⚠️ 拉 listMixedCatalogMeta 失败（{e}），跳过目录级验证", file=sys.stderr)

    def _catalog_key(c):
        """生成比对键：优先 projectName，否则 dbName"""
        return (c.get("projectName") or c.get("dbName") or "").strip()

    catalog_names = {_catalog_key(c) for c in available_catalogs if _catalog_key(c)}

    if not catalog_names:
        print(f"⚠️ 当前 token 在引擎 {args.engine} 下**无任何可用 catalog/db**（listMixedCatalogMeta 返回 0 条）")
        print(f"   可能原因：账号无该引擎权限 / 租户未接入此引擎 / 引擎名拼错")
        print(f"   → 换引擎试：--engine STARROCKS / DLF.LEGACY / HOLO.POSTGRES / EMR.HIVE")
        print()

    # rangeList 服务端必填：未传时打印引擎下可用 catalog/db 清单，帮用户 resolve
    if not payload.get("rangeList"):
        print("━━ 可选识别范围（引擎 {} 下可用 catalog/db）━━".format(args.engine))
        if catalog_names:
            sample = sorted(catalog_names)[:30]
            for n in sample:
                # 找一条 catalog 元信息展示完整结构
                meta = next((c for c in available_catalogs if _catalog_key(c) == n), {})
                schema = meta.get("schemaName") or ""
                print(f"  • {n}" + (f" (schema={schema})" if schema else ""))
            if len(catalog_names) > 30:
                print(f"  ... 共 {len(catalog_names)} 个，仅展示前 30")
        print()
        print("❌ 未传 rangeList（服务端必填，Once 类型需具体到 project/schema 级）")
        print("→ 把上面的 project/schema 填到 JSON 再跑，例如 range.json:")
        eg = sorted(catalog_names)[0] if catalog_names else "your_project"
        eg_meta = next((c for c in available_catalogs if _catalog_key(c) == eg), {}) if catalog_names else {}
        eg_schema = eg_meta.get("schemaName") or "default"
        print(json.dumps({
            "rangeList": [{
                "engineType": args.engine,
                "projectName": eg,
                "schemaName": eg_schema,
                "tableName": "*",
            }]
        }, ensure_ascii=False, indent=2))
        print(f"→ 然后: create_recognition_task.py --task-name {args.task_name} --engine {args.engine} --task-type {args.task_type} --config-json ./range.json")
        sys.exit(1)

    # ── 识别范围展开：对 tableName='*' 或空 的条目，调 listMixedTablesMeta 列实际表供确认 ──
    ranges = payload.get("rangeList") or []
    if ranges:
        print("━━ 识别范围（将被扫描）━━")
        for i, r in enumerate(ranges, 1):
            eng = r.get("engineType") or args.engine
            proj = r.get("projectName") or r.get("dbName") or "?"
            schema = r.get("schemaName") or ""
            table = r.get("tableName") or ""
            loc = f"{eng} / {proj}" + (f".{schema}" if schema else "")

            # 目录级预检：project/db 在该引擎的可用清单里吗？
            if catalog_names and proj not in catalog_names:
                similar = [n for n in catalog_names if proj.lower() in n.lower() or n.lower() in proj.lower()][:5]
                print(f"  [{i}] {loc} / ❌ 项目不存在于引擎 {eng} 可用目录下")
                print(f"        {eng} 下共 {len(catalog_names)} 个可用 catalog/db" +
                      (f"，相似候选: {similar}" if similar else ""))
                if len(catalog_names) <= 15:
                    print(f"        完整清单: {sorted(catalog_names)}")
                continue

            if table and table != "*":
                # 用户指定了具体表（单/多逗号分隔）
                tables = [t.strip() for t in table.split(",") if t.strip()]
                print(f"  [{i}] {loc} / 指定 {len(tables)} 张表:")
                for t in tables[:10]:
                    print(f"        - {t}")
                if len(tables) > 10:
                    print(f"        ... 还有 {len(tables) - 10} 张")
            else:
                # tableName='*' 或空 → 展开实际表清单
                label = "* (全选)" if table == "*" else "(未填 = 全部)"
                resolve_kwargs = {
                    "engineType": eng,
                    "projectName": r.get("projectName") or None,
                    "instanceId": r.get("instanceId") or None,
                    "clusterId": r.get("clusterId") or None,
                    "catalogName": r.get("catalogName") or None,
                    "dbName": r.get("dbName") or None,
                    "schemaName": r.get("schemaName") or None,
                }
                try:
                    tables = client.load("listMixedTablesMeta", **{k: v for k, v in resolve_kwargs.items() if v is not None}) or []
                    n = len(tables)
                    print(f"  [{i}] {loc} / 表: {label} → 展开 {n} 张")
                    for t in tables[:10]:
                        tname = t.get("tableName") if isinstance(t, dict) else str(t)
                        print(f"        - {tname}")
                    if n > 10:
                        print(f"        ... 共 {n} 张（仅预览前 10 条）")
                    if n == 0:
                        print(f"        ⚠️ 该范围下无表命中，确认 projectName/schemaName 是否正确")
                except Exception as e:
                    print(f"  [{i}] {loc} / 表: {label}  ⚠️ 展开失败（{e}），信 服务端按 '*' 全扫")

    # ── 敏感类型展示（给用户确认会扫哪些敏感类型）──
    # 响应是树：{name, type: branch, children: [{name, type: branch/leaf, children}]}
    # branch = 分类，leaf = 具体敏感类型（扫描目标）
    print()
    print("━━ 敏感类型（识别目标，租户级全局，本任务不可排除/定制）━━")
    try:
        tree = client.load("listClassificationEnabledSensitiveTypeNames")
        if not isinstance(tree, dict) or not tree.get("children"):
            print("  租户未启用任何敏感类型模板（服务端扫描规则由默认配置决定）")
        else:
            branches = tree.get("children") or []
            # 统计所有 leaf
            def _collect_leaves(node):
                out = []
                if node.get("type") == "leaf":
                    out.append(node.get("name", ""))
                for ch in node.get("children") or []:
                    out.extend(_collect_leaves(ch))
                return out
            all_leaves = _collect_leaves(tree)
            print(f"  模板「{tree.get('name', '')}」：{len(branches)} 个分类 / 共 {len(all_leaves)} 种敏感类型")
            for br in branches:
                leaves = _collect_leaves(br)
                preview = "、".join(leaves[:5])
                more = f"… 共 {len(leaves)}" if len(leaves) > 5 else ""
                print(f"    • {br.get('name', '')}（{len(leaves)} 项）: {preview}{more}")
    except Exception as e:
        print(f"  ⚠️ 拉取敏感类型失败: {e}")
    print()

    # Scheduled 校验
    if args.task_type == "Scheduled":
        if not (args.scheduled_frequency and args.scheduled_time is not None):
            print("❌ Scheduled 必填 --scheduled-frequency 和 --scheduled-time（秒 0-86400）", file=sys.stderr)
            sys.exit(1)
        if args.scheduled_frequency in ("Week", "Month") and args.scheduled_date is None:
            print("❌ Week/Month 周期必填 --scheduled-date（1-31）", file=sys.stderr)
            sys.exit(1)

    # 触发 write preview
    client.write("createRecognitionTask", **payload)
    print()
    print("→ 用户确认无误后: create_recognition_task.py --confirm")
    print(f"→ 执行后轮询等结果: wait_recognition_task.py --task-name {args.task_name}")
    print(f"→ 或直接看单任务状态: list_recognition_tasks.py --task-name {args.task_name}")


if __name__ == "__main__":
    main()
