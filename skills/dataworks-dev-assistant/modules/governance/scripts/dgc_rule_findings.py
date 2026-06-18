#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""治理项详情下钻 — 查看某个扣分项的具体问题资产列表

从 dgc_overview.py 的扣分项列表中选择一个 itemCode，查看具体哪些表/任务命中了这条规则。

用法:
    python dgc_rule_findings.py --item-code 54                    # 查看 itemCode=54 的问题列表
    python dgc_rule_findings.py --item-code 54 --owner-id 083361  # 只看指定用户的
    python dgc_rule_findings.py --item-code 6 --page-size 20      # 指定页大小

涉及 API: ListGovernanceRuleFindings

关键参数:
    dataAssetType: TABLE（表）— 目前固定
    ruleCode: 对应 dgc_overview 中 getScoreFactorDetail 返回的 itemCode
    dataAssetOwner: 用户 ID（baseId），不传则查全部
"""

import argparse

from bff_client import BFFClient


def main():
    parser = argparse.ArgumentParser(description="治理项详情下钻")
    parser.add_argument("--item-code", required=True, help="治理项编号（dgc_overview 扣分项中的 itemCode）")
    parser.add_argument("--owner-id", help="只看指定用户的问题（不传则查全部）")
    parser.add_argument("--page-size", type=int, default=20, help="每页条数（默认 20）")
    parser.add_argument("--page", type=int, default=1, help="页码（默认 1）")
    args = parser.parse_args()

    client = BFFClient()

    params = dict(
        dataAssetType="TABLE",
        ruleCode=args.item_code,
        pageSize=str(args.page_size),
        pageNumber=str(args.page),
    )
    if args.owner_id:
        params["dataAssetOwner"] = args.owner_id
    elif not args.owner_id:
        # 默认查当前用户
        params["dataAssetOwner"] = client.get_my_base_id()

    findings = client.load("ListGovernanceRuleFindings", **params)

    owner_label = f"用户 {params.get('dataAssetOwner', '全部')}"
    print(f"\n━━ 治理项 {args.item_code} 详情（{owner_label}）━━")

    if not isinstance(findings, list):
        print(f"  {findings}")
        return

    if not findings:
        print("  无问题资产")
        return

    print(f"  共 {len(findings)} 条（第 {args.page} 页）\n")

    for i, item in enumerate(findings):
        da = item.get("dataAsset", {})
        name = da.get("name", "?")
        owner = da.get("owner", "?")
        project_id = da.get("projectId", "?")
        asset_type = da.get("type", "?")

        print(f"  {i+1}. {name}")
        print(f"     负责人={owner}  项目={project_id}  类型={asset_type}")

    if len(findings) >= args.page_size:
        print(f"\n  💡 下一页: python dgc_rule_findings.py --item-code {args.item_code} --page {args.page + 1}")


if __name__ == "__main__":
    main()
