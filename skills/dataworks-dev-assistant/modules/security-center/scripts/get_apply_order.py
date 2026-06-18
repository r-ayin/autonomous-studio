#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查看权限申请单详情（RAP 新版，getApplyOrderDetail）

orderId 来源：
    - list_my_applications.py   → 我提交的申请列表（orderId 列）
    - list_pending_approvals.py → 待我审批的列表（orderId 列）

用法：
    get_apply_order.py --order-id <orderId>
    get_apply_order.py --order-id abc123-xxxx-yyyy
"""

import argparse
import json
import sys

from bff_client import BFFClient


def _fmt(val, width=None):
    s = str(val) if val is not None else ""
    return s[:width] if width else s


def main():
    p = argparse.ArgumentParser(description="查看权限申请单详情（RAP 新版）")
    p.add_argument("--order-id", required=True,
                   help="申请单 ID（从 list_my_applications 或 list_pending_approvals 输出的 orderId 列取）")
    args = p.parse_args()

    client = BFFClient(quiet=True)
    data = client.load("getApplyOrderDetail", orderId=args.order_id)

    if not data:
        print(f"❌ 未找到申请单: {args.order_id}", file=sys.stderr)
        print("→ 确认 orderId 是否正确: list_my_applications.py 或 list_pending_approvals.py", file=sys.stderr)
        sys.exit(1)

    # data 为单个 dict
    if isinstance(data, list):
        data = data[0] if data else {}

    print(f"申请单详情: {args.order_id}\n")

    # 基本信息
    print(f"  申请时间  : {_fmt(data.get('applyDate'))}")
    print(f"  申请理由  : {_fmt(data.get('applyReason'))}")
    print(f"  申请类型  : {_fmt(data.get('applyType'))}")
    print(f"  截止类型  : {_fmt(data.get('deadlineType'))}")

    # 审批状态
    approve = data.get("approve") or {}
    if approve:
        print(f"\n  审批信息:")
        print(f"    状态      : {_fmt(approve.get('approveStatus'))} {_fmt(approve.get('approveStatusDesc'))}")
        print(f"    审批意见  : {_fmt(approve.get('approveComment'))}")
        print(f"    审批时间  : {_fmt(approve.get('approveTime') or approve.get('updateTime'))}")

    # 操作人（安全中心侧）
    operator = data.get("securityCenterOperator") or {}
    if operator:
        print(f"\n  安全中心操作人:")
        print(f"    账号      : {_fmt(operator.get('accountName') or operator.get('displayName'))}")

    # 授权对象
    grantee_list = data.get("granteeObjectList") or []
    if grantee_list:
        print(f"\n  授权对象（{len(grantee_list)} 个）:")
        for g in grantee_list:
            principal = _fmt(g.get("principalId"))
            ptype = _fmt(g.get("principalType"))
            name = _fmt(g.get("displayName") or g.get("accountName"))
            print(f"    {principal} ({ptype}) {name}")

    # 申请资源
    apply_resources = data.get("applyResources") or []
    if apply_resources:
        print(f"\n  申请资源（{len(apply_resources)} 条）:")
        for i, res in enumerate(apply_resources, 1):
            resource = res.get("resource") or {}
            meta = resource.get("metaData") or {}
            access_types = res.get("accessTypes") or []
            exp = _fmt(res.get("expirationTime"))
            project = _fmt(meta.get("project"))
            table = _fmt(meta.get("table"))
            column = meta.get("column")
            loc = f"{project}.{table}" + (f".{column}" if column else "")
            print(f"    [{i}] {loc:<50} 权限: {', '.join(access_types):<30} 过期: {exp}")

    # 项目元数据
    project_meta = data.get("projectMeta") or {}
    if project_meta:
        print(f"\n  项目信息:")
        print(f"    工作空间  : {_fmt(project_meta.get('workspaceName'))} (id={_fmt(project_meta.get('workspaceId'))})")
        print(f"    项目名    : {_fmt(project_meta.get('projectName'))}")

    print()
    print(f"→ 查我提交的其他申请: list_my_applications.py")
    print(f"→ 查待审批列表: list_pending_approvals.py")


if __name__ == "__main__":
    main()
