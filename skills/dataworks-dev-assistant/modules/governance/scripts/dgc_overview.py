#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据治理总览 — 评分 + 趋势 + 资产概况

查看治理评分、各维度得分明细、趋势变化、数据资产（存储/计算/范围/标签）。
管理员可查看任意用户的治理情况。

用法:
    python dgc_overview.py                          # 查看自己的治理总览（个人视角）
    python dgc_overview.py --owner-id 012345        # 查看指定用户的治理总览
    python dgc_overview.py --workspace              # 工作空间视角（全局）

涉及 API: getAllScore, getScoreFactorDetail, getTrend, getMetricReport,
          getDataAssetCompute, getDataAssetScope, getDataAssetStorage,
          getDataAssetTag, getScannerSummary
"""

import argparse
import sys
import os

from bff_client import BFFClient


def fmt_score(obj):
    """格式化评分对象"""
    if not isinstance(obj, dict):
        return str(obj)
    score = obj.get("score", "?")
    level = obj.get("scoreLevelEnum") or obj.get("level", "")
    to_solve = obj.get("toSolveItemCount", 0)
    return f"{score} (等级 {level}, 待治理 {to_solve} 项)"


def main():
    parser = argparse.ArgumentParser(description="数据治理总览")
    parser.add_argument("--owner-id", help="目标用户 ID（不传则默认当前用户）")
    parser.add_argument("--workspace", action="store_true", help="工作空间视角（viewType=1），默认个人视角（viewType=2）")
    args = parser.parse_args()

    client = BFFClient()

    # viewType: 1=工作空间视角（全局）, 2=个人视角
    view_type = "1" if args.workspace else "2"
    owner_id = args.owner_id or client.get_my_base_id()
    common = dict(viewType=view_type, ownerId=owner_id)

    scope_label = "工作空间" if args.workspace else f"用户 {owner_id}"

    # 1. 治理评分
    score = client.load("getAllScore", **common)
    print(f"\n━━ 治理评分（{scope_label}）━━")
    if isinstance(score, dict):
        print(f"  总分: {fmt_score(score)}")
        for key, label in [("computeScore", "计算"), ("storageScore", "存储"),
                           ("qualityScore", "质量"), ("securityScore", "安全"),
                           ("developmentScore", "开发规范")]:
            sub = score.get(key)
            if sub:
                print(f"  {label}: {fmt_score(sub)}")

    # 2. 扣分项明细（field=5 表示全部维度）
    factors = client.load("getScoreFactorDetail", **common, field="5")
    if isinstance(factors, list) and factors:
        # 按扣分排序
        factors.sort(key=lambda f: f.get("deduction", 0))
        print(f"\n━━ 扣分项 TOP 10（共 {len(factors)} 项）━━")
        for f in factors[:10]:
            name = f.get("name", "?")
            count = f.get("count", 0)
            deduction = f.get("deduction", 0)
            item_code = f.get("itemCode", "?")
            print(f"  {deduction:+.2f}  {name} ({count} 个)  [itemCode={item_code}]")
        print(f"\n  💡 查看某项详情: python dgc_rule_findings.py --item-code <itemCode>")

    # 3. 数据资产概况
    print(f"\n━━ 数据资产概况 ━━")

    scope = client.load("getDataAssetScope", **common)
    if isinstance(scope, dict):
        ws_count = scope.get("totalWorkspaceCount", "?")
        ds_list = scope.get("reportScopeVOList") or []
        print(f"  工作空间: {ws_count} 个")
        for ds in ds_list:
            print(f"  {ds.get('datasourceType', '?')}: {ds.get('datasourceNum', '?')} 个数据源")

    storage = client.load("getDataAssetStorage", **common)
    if storage is not None:
        if isinstance(storage, (int, float)):
            tb = storage / (1024 ** 4)
            print(f"  总存储: {tb:.2f} TB")
        else:
            print(f"  总存储: {storage}")

    # 4. 扫描器汇总
    scanner = client.load("getScannerSummary", **common)
    print(f"\n━━ 待治理汇总 ━━")
    if isinstance(scanner, dict):
        issues = scanner.get("toSolveIssuesCount", "?")
        assets = scanner.get("toSolveDataAssetsCount", "?")
        print(f"  待治理问题: {issues} 个")
        print(f"  涉及资产: {assets} 个")


if __name__ == "__main__":
    main()
