#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""待我审批的权限申请列表（RAP 新版，listTodoApprove）

区别：
    list_my_applications.py   — 我提交的申请（dsm-guard 老接口）
    list_pending_approvals.py — 待我审批的申请（RAP 新版，本脚本）
    list_my_approvals.py      — 我已审批过的历史记录（RAP 新版）

用法：
    list_pending_approvals.py                    # 默认 page=1, limit=50
    list_pending_approvals.py --limit 100        # 最多返回 100 条
    list_pending_approvals.py --page 2           # 第 2 页
"""

import argparse
import sys

from bff_client import BFFClient


def main():
    p = argparse.ArgumentParser(description="待我审批的权限申请列表（RAP 新版）")
    p.add_argument("--limit", type=int, default=50,
                   help="返回上限（默认 50，上限 200）")
    p.add_argument("--page", type=int, default=1,
                   help="页码（默认 1）")
    args = p.parse_args()

    page_size = min(args.limit, 200)

    client = BFFClient(quiet=True)
    data = client.load("listTodoApprove", current=args.page, pageSize=page_size)

    # data 为 model[] 列表
    rows = data if isinstance(data, list) else []

    if not rows:
        print("无待审批申请")
        print("→ 看我已审批过的记录: list_my_approvals.py")
        print("→ 看我提交的申请: list_my_applications.py")
        return

    print(f"待审批申请（第 {args.page} 页，共 {len(rows)} 条）\n")
    print(f"  {'orderId':<38} {'申请人':<16} {'状态':<10} {'申请时间':<20} {'申请理由':<30}")
    print(f"  {'-'*38} {'-'*16} {'-'*10} {'-'*20} {'-'*30}")

    for r in rows:
        oid = str(r.get("orderId") or "")[:38]
        applicant = str(r.get("applicant") or r.get("applyAccount") or "")[:16]
        status = str(r.get("approveStatus") or r.get("approveStatusDesc") or "")[:10]
        apply_date = str(r.get("applyDate") or "")[:20]
        reason = str(r.get("applyReason") or "")[:30]
        print(f"  {oid:<38} {applicant:<16} {status:<10} {apply_date:<20} {reason:<30}")

    print()
    print(f"→ 查申请单详情: get_apply_order.py --order-id <orderId>")
    print(f"→ 看我已审批过的: list_my_approvals.py")
    if len(rows) == page_size:
        print(f"→ 下一页: list_pending_approvals.py --page {args.page + 1} --limit {args.limit}")


if __name__ == "__main__":
    main()
