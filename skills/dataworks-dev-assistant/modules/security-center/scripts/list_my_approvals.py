#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""我已审批过的权限申请历史（RAP 新版，listApprove）

区别：
    list_pending_approvals.py — 待我审批的（RAP 新版）
    list_my_approvals.py      — 我已审批过的历史，本脚本
    list_my_applications.py   — 我自己提交的申请（dsm-guard 老接口）

用法：
    list_my_approvals.py                    # 默认 page=1, limit=50
    list_my_approvals.py --limit 100        # 最多返回 100 条
    list_my_approvals.py --page 2           # 第 2 页
"""

import argparse
import sys

from bff_client import BFFClient


def main():
    p = argparse.ArgumentParser(description="我已审批过的权限申请历史（RAP 新版）")
    p.add_argument("--limit", type=int, default=50,
                   help="返回上限（默认 50，上限 200）")
    p.add_argument("--page", type=int, default=1,
                   help="页码（默认 1）")
    args = p.parse_args()

    page_size = min(args.limit, 200)

    client = BFFClient(quiet=True)
    data = client.load("listApprove", current=args.page, pageSize=page_size)

    # data 为 list[] 列表
    rows = data if isinstance(data, list) else []

    if not rows:
        print("无审批历史记录")
        print("→ 看待审批的申请: list_pending_approvals.py")
        return

    print(f"我的审批历史（第 {args.page} 页，共 {len(rows)} 条）\n")
    print(f"  {'orderId/节点':<38} {'状态':<12} {'状态说明':<14} {'更新时间':<20} {'审批意见':<24}")
    print(f"  {'-'*38} {'-'*12} {'-'*14} {'-'*20} {'-'*24}")

    for r in rows:
        # 响应结构：accountList/approveComment/nodeType/status/statusDesc/updateTime
        node_type = str(r.get("nodeType") or "")[:38]
        status = str(r.get("status") or "")[:12]
        status_desc = str(r.get("statusDesc") or "")[:14]
        update_time = str(r.get("updateTime") or "")[:20]
        comment = str(r.get("approveComment") or "")[:24]
        print(f"  {node_type:<38} {status:<12} {status_desc:<14} {update_time:<20} {comment:<24}")

    print()
    print(f"→ 查申请单详情: get_apply_order.py --order-id <orderId>")
    print(f"→ 看待审批的申请: list_pending_approvals.py")
    if len(rows) == page_size:
        print(f"→ 下一页: list_my_approvals.py --page {args.page + 1} --limit {args.limit}")


if __name__ == "__main__":
    main()
