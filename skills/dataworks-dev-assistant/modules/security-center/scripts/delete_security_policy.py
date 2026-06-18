#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""删除 DataStudio 安全策略（deleteDataStudioSecurityPolicy）

⚠️ 两阶段写操作：Phase 1 拉详情预览并警告保留行为，Phase 2（--confirm）才真正提交。
⚠️ 服务端特殊保留行为：
    - 系统策略（SYSTEM_ 前缀或 isDefaultPolicy）：接口返回 true 但实际不删
    - DISABLE_DOWNLOAD_FROM_SETTING_CENTER：被强制改为 DISABLE 状态而非真删

用法：
    delete_security_policy.py --policy-uuid <uuid>    # Phase 1
    delete_security_policy.py --confirm               # Phase 2
"""

import argparse
import sys

from bff_client import BFFClient


_SPECIAL_RETAINED = {"DISABLE_DOWNLOAD_FROM_SETTING_CENTER"}


def _fmt(v):
    return str(v) if v is not None else ""


def main():
    p = argparse.ArgumentParser(description="删除 DataStudio 安全策略（两阶段确认）")
    p.add_argument("--policy-uuid",
                   help="策略 UUID（Phase 1 必填；Phase 2 不用传）")
    p.add_argument("--confirm", action="store_true",
                   help="Phase 2: 执行删除")
    args = p.parse_args()

    client = BFFClient()

    if args.confirm:
        client.confirm_write()
        return

    if not args.policy_uuid:
        print("❌ Phase 1 需要 --policy-uuid", file=sys.stderr)
        print("→ 从 list_security_policies.py 取 policyUuid", file=sys.stderr)
        sys.exit(1)

    try:
        detail = client.load("getDataStudioSecurityPolicyDetail",
                             policyUuid=args.policy_uuid)
    except Exception as e:
        print(f"❌ 查询策略详情失败: {e}", file=sys.stderr)
        print("→ 检查 policyUuid 是否正确", file=sys.stderr)
        sys.exit(1)

    if isinstance(detail, list):
        detail = detail[0] if detail else {}
    if not detail:
        print(f"❌ 未找到策略: {args.policy_uuid}", file=sys.stderr)
        sys.exit(1)

    name = _fmt(detail.get("name"))
    ptype = _fmt(detail.get("policyType"))
    is_system = bool(detail.get("system"))
    ws = detail.get("workspaces") or []

    print(f"将要删除策略：{args.policy_uuid}\n")
    print(f"  名称    : {name}")
    print(f"  描述    : {_fmt(detail.get('desc'))}")
    print(f"  类型    : {ptype}")
    print(f"  启用    : {'✓' if detail.get('status') else '✗'}")
    if ws:
        print(f"  应用范围: {len(ws)} 个 workspace")

    # 保留行为预警
    if is_system or name.startswith("SYSTEM_"):
        print(f"\n  ⚠️ 系统策略：服务端会返回成功但实际不删（isDefaultPolicy 保护）")
    if name in _SPECIAL_RETAINED:
        print(f"\n  ⚠️ 特殊策略 {name}：服务端会强制改为 DISABLE 而非真删（管理中心同步会反复加载）")

    # Phase 1：提交待确认写操作
    client.write("deleteDataStudioSecurityPolicy", policyUuid=args.policy_uuid)
    print()
    print(f"→ 用户确认后执行: delete_security_policy.py --confirm")


if __name__ == "__main__":
    main()
