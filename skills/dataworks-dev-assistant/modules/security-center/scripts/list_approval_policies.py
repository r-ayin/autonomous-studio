#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查审批策略列表 / 单策略详情（安全中心-申请审批）

用法:
    python list_approval_policies.py                            # 列 MaxComputeTable 类型策略（默认）
    python list_approval_policies.py --policy-type HologresTable
    python list_approval_policies.py --id <workflowId>          # 查单策略完整配置
    python list_approval_policies.py --region cn-beijing        # 指定 region

仅公有云。支持的 policyType：MaxComputeTable / DLFNext / DLF / HologresTable / LindormTable / DsApiDeploy / ExtensionSet / DgcCheckerOperation
"""

import argparse
import json
import sys

from bff_client import BFFClient


def main():
    p = argparse.ArgumentParser(description="查审批策略")
    p.add_argument("--id", help="workflowId（单策略详情模式）")
    p.add_argument("--policy-type", default="MaxComputeTable",
                   help="策略类型（列表模式必填，默认 MaxComputeTable）")
    p.add_argument("--region", help="region（如 chengdu / beijing），部分租户必填")
    p.add_argument("--limit", type=int, default=100, help="列表模式每页数量")
    args = p.parse_args()

    client = BFFClient(quiet=True)

    # ── 详情模式 ──
    if args.id:
        result = client.load("getProcessDefinition", id=args.id)
        if not result:
            print(f"未找到策略 id={args.id}", file=sys.stderr)
            sys.exit(1)
        print(f"━━ 策略 {args.id} 完整配置 ━━")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str)[:3000])
        print()
        print(f"→ 启停/删除: toggle_approval_policy.py --id {args.id} --action enable|disable|delete")
        print(f"→ 更新配置: upsert_approval_policy.py --id {args.id} --config-json <file>")
        return

    # ── 列表模式 ──
    params = {
        "policyType": args.policy_type,
        "pageSize": args.limit,
        "pageNumber": 1,
    }
    if args.region:
        params["region"] = args.region

    rows = client.load("listProcessDefinitions_security", **params) or []
    if not rows:
        print(f"无 {args.policy_type} 类型策略 "
              f"{('(region=' + args.region + ')') if args.region else ''}")
        print("→ 换类型试试: --policy-type HologresTable|DsApiDeploy|ExtensionSet|...")
        return

    print(f"{args.policy_type} 类型审批策略: {len(rows)} 个")
    print()
    print(f"  {'序号':<4} {'策略名':<30} {'workflowId':<40} {'状态':<6} {'优先级':<6}")
    print(f"  {'-'*4} {'-'*30} {'-'*40} {'-'*6} {'-'*6}")
    for i, r in enumerate(rows, 1):
        name = (r.get("name") or "")[:30]
        wid = (r.get("workflowId") or r.get("policyUuid") or "")[:40]
        status = "启用" if r.get("status") else "停用"
        prio = str(r.get("priority") or "-")
        is_sys = " [系统]" if r.get("isSystem") else ""
        print(f"  {i:<4} {name:<30} {wid:<40} {status:<6} {prio:<6}{is_sys}")

    print()
    print(f"→ 看详情: list_approval_policies.py --id <workflowId>")
    print(f"→ 启停:   toggle_approval_policy.py --id <workflowId> --action enable|disable")


if __name__ == "__main__":
    main()
