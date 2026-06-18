#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""治理扫描器概况 — 汇总 + 类型 + 报告

查看扫描器运行汇总、支持的节点类型和引擎、扫描器分类、数据源类型、报告对象。
管理员可查看任意用户的扫描器情况。

用法:
    python dgc_scanner.py                           # 查看当前用户（个人视角）
    python dgc_scanner.py --owner-id 012345         # 查看指定用户
    python dgc_scanner.py --workspace               # 工作空间视角（全局）

涉及 API: getScannerSummary, getNodeTypeMapPropWithEngineScanner,
          listManageTypesScanner, listDatasourceTypes, listReportObject
"""

import argparse
import sys
import os

from bff_client import BFFClient


def main():
    parser = argparse.ArgumentParser(description="治理扫描器概况")
    parser.add_argument("--owner-id", help="目标用户 ID（不传则默认当前用户）")
    parser.add_argument("--workspace", action="store_true", help="工作空间视角（viewType=1），默认个人视角（viewType=2）")
    args = parser.parse_args()

    client = BFFClient()

    view_type = "1" if args.workspace else "2"
    owner_id = args.owner_id or client.get_my_base_id()
    common = dict(viewType=view_type, ownerId=owner_id)

    # 1. 扫描器汇总
    summary = client.load("getScannerSummary", **common)
    scope_label = "工作空间" if args.workspace else f"用户 {owner_id}"
    print(f"\n━━ 扫描器汇总（{scope_label}）━━")
    if isinstance(summary, dict):
        for k, v in summary.items():
            if isinstance(v, (int, float, str)):
                print(f"  {k}: {v}")
    else:
        print(f"  {summary}")

    # 2. 节点类型 × 引擎映射（全局，不需要 ownerId）
    node_map = client.load("getNodeTypeMapPropWithEngineScanner")
    print(f"\n━━ 节点类型 × 引擎 ━━")
    if isinstance(node_map, dict):
        print(f"  {len(node_map)} 种节点类型")
    else:
        print(f"  {node_map}")

    # 3. 扫描器分类（isScoreFactor=1 表示纳入评分的）
    types = client.load("listManageTypesScanner", **common, isScoreFactor="1")
    print(f"\n━━ 扫描器分类（纳入评分，仅显示有问题的）━━")
    if isinstance(types, list):
        has_issues = [t for t in types if isinstance(t, dict) and t.get("count", 0) > 0]
        has_issues.sort(key=lambda t: t.get("count", 0), reverse=True)
        for t in has_issues:
            print(f"  {t.get('name', '?')}: {t.get('count', 0)} 个")
        if not has_issues:
            print("  全部通过")
    else:
        print(f"  {types}")

    # 4. 数据源类型（全局）
    ds_types = client.load("listDatasourceTypes")
    if isinstance(ds_types, list):
        print(f"\n━━ 数据源类型（{len(ds_types)} 种）━━")

    # 5. 报告对象
    reports = client.load("listReportObject", **common)
    print(f"\n━━ 报告对象 ━━")
    if isinstance(reports, list):
        print(f"  {len(reports)} 个报告对象")
        for r in reports[:5]:
            print(f"  {r}")
    else:
        print(f"  {reports}")


if __name__ == "__main__":
    main()
