#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""撤销权限申请（stopProcessInstance）

⚠️ 两阶段写操作：Phase 1 输出确认摘要，Phase 2（--confirm）才真正提交。

orderId 来源：
    - list_my_applications.py   → 我提交的申请列表
    - list_pending_approvals.py → 待审批列表（审批人也可撤销）

用法：
    cancel_application.py --order-id <orderId>   # Phase 1: 拉申请详情并预览
    cancel_application.py --confirm              # Phase 2: 真正撤销
"""

import argparse
import sys

from bff_client import BFFClient


def _fmt(v):
    return str(v) if v is not None else ""


def _print_preview(data, order_id):
    """拉申请详情，输出将被撤销的申请摘要 + 确认提示。"""
    print(f"将要撤销的申请单：{order_id}\n")
    print(f"  申请时间  : {_fmt(data.get('applyDate'))}")
    print(f"  申请理由  : {_fmt(data.get('applyReason'))}")
    print(f"  申请类型  : {_fmt(data.get('applyType'))}")

    approve = data.get("approve") or {}
    status_desc = _fmt(approve.get("approveStatusDesc")) or _fmt(approve.get("approveStatus"))
    if status_desc:
        print(f"  当前状态  : {status_desc}")

    grantee_list = data.get("granteeObjectList") or []
    if grantee_list:
        names = ", ".join(
            (_fmt(g.get("displayName") or g.get("accountName") or g.get("principalId")))
            for g in grantee_list[:3]
        )
        extra = f" 等 {len(grantee_list)} 个" if len(grantee_list) > 3 else ""
        print(f"  授权对象  : {names}{extra}")

    apply_resources = data.get("applyResources") or []
    if apply_resources:
        print(f"  涉及资源  : {len(apply_resources)} 条")
        for i, res in enumerate(apply_resources[:3], 1):
            meta = (res.get("resource") or {}).get("metaData") or {}
            loc = f"{_fmt(meta.get('project'))}.{_fmt(meta.get('table'))}"
            col = meta.get("column")
            if col:
                loc += f".{col}"
            access = ", ".join(res.get("accessTypes") or [])
            print(f"    [{i}] {loc}  权限: {access}")
        if len(apply_resources) > 3:
            print(f"    ... 还有 {len(apply_resources) - 3} 条")


def main():
    p = argparse.ArgumentParser(
        description="撤销权限申请（两阶段确认）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--order-id",
                   help="申请单 ID（= processInstanceId）。Phase 1 必填；Phase 2 不用传。")
    p.add_argument("--confirm", action="store_true",
                   help="Phase 2: 执行撤销（前置 Phase 1 预览须已确认）。")
    args = p.parse_args()

    client = BFFClient()

    if args.confirm:
        client.confirm_write()
        return

    if not args.order_id:
        print("❌ Phase 1 需要 --order-id", file=sys.stderr)
        print("→ 从 list_my_applications.py 或 list_pending_approvals.py 的 orderId 列取", file=sys.stderr)
        sys.exit(1)

    # 拉详情做预览（让用户看清楚要撤销什么）
    try:
        detail = client.load("getApplyOrderDetail", orderId=args.order_id)
    except Exception as e:
        print(f"❌ 查询申请单详情失败: {e}", file=sys.stderr)
        print("→ 确认 orderId 是否正确: list_my_applications.py", file=sys.stderr)
        sys.exit(1)

    if isinstance(detail, list):
        detail = detail[0] if detail else {}
    if not detail:
        print(f"❌ 未找到申请单: {args.order_id}", file=sys.stderr)
        sys.exit(1)

    # 已终态的申请不应再撤销
    approve = detail.get("approve") or {}
    status = _fmt(approve.get("approveStatus"))
    if status in ("agree", "reject", "cancel", "pass", "refuse"):
        desc = _fmt(approve.get("approveStatusDesc")) or status
        print(f"⚠️ 该申请已处于终态：{desc}，无需撤销")
        sys.exit(0)

    _print_preview(detail, args.order_id)

    # Phase 1：提交待确认写操作
    client.write("stopProcessInstance", processInstanceId=args.order_id)

    print()
    print(f"→ 用户确认后执行: cancel_application.py --confirm")


if __name__ == "__main__":
    main()
