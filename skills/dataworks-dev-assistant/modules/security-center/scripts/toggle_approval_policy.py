#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启用/停用/删除审批策略（两阶段写操作）

Phase 1（preview）:
    python toggle_approval_policy.py --id <workflowId> --action enable|disable|delete

Phase 2（confirm）:
    python toggle_approval_policy.py --confirm

⚠️ delete 不可逆，系统策略 (isSystem=true) 可能被拒绝。
"""

import argparse
import sys

from bff_client import BFFClient


_ACTION_TO_API = {
    "enable": "enableProcessDefinition",
    "disable": "disableProcessDefinition",
    "delete": "deleteProcessDefinition",
}


def main():
    p = argparse.ArgumentParser(description="启用/停用/删除审批策略")
    p.add_argument("--id", help="workflowId（Phase 1 必填）")
    p.add_argument("--action", choices=list(_ACTION_TO_API.keys()),
                   help="操作类型（Phase 1 必填）")
    p.add_argument("--confirm", action="store_true", help="Phase 2: 执行")
    args = p.parse_args()

    client = BFFClient()

    if args.confirm:
        client.confirm_write()
        return

    if not args.id or not args.action:
        p.error("Phase 1 必填 --id 和 --action")

    api_name = _ACTION_TO_API[args.action]
    print(f"策略 {args.id} ← 动作 {args.action.upper()}")
    if args.action == "delete":
        print("⚠️ 删除不可逆；系统策略（isSystem=true）可能被拒")
    client.write(api_name, id=args.id)
    print(f"\n→ 用户确认后: toggle_approval_policy.py --confirm")


if __name__ == "__main__":
    main()
