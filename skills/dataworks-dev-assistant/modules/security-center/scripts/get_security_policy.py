#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查看 DataStudio 安全策略详情（getDataStudioSecurityPolicyDetail + getLimit 对照）

自动对照当前版本的绝对上限（getLimit），高亮超 cap 的字段。

用法：
    get_security_policy.py --policy-uuid <policyUuid>
"""

import argparse
import json
import sys

from bff_client import BFFClient


def _fmt(v):
    return str(v) if v is not None else ""


_POLICY_KEYS = [
    ("maxLimitOfSingleQuery", "单次查询上限"),
    ("maxLimitOfSingleCopy", "单次复制上限"),
    ("maxLimitOfSingleDownload", "单次下载上限"),
    ("allowExportExcel", "允许导出 Excel"),
    ("allowExtensionInServerIDE", "ServerIDE 扩展"),
    ("allowTerminalInServerIDE", "ServerIDE 终端"),
    ("allowDownloadMountedWorkspaceFile", "挂载目录文件下载"),
    ("allowDownloadInMyCatalog", "MyCatalog 文件下载"),
]


def main():
    p = argparse.ArgumentParser(description="DataStudio 安全策略详情 + 版本 cap 对照")
    p.add_argument("--policy-uuid", required=True,
                   help="策略 UUID（从 list_security_policies.py 取）")
    args = p.parse_args()

    client = BFFClient(quiet=True)

    # 并行拉详情 + 版本 cap
    try:
        detail = client.load("getDataStudioSecurityPolicyDetail", policyUuid=args.policy_uuid)
    except Exception as e:
        print(f"❌ 查询详情失败: {e}", file=sys.stderr)
        sys.exit(1)

    if isinstance(detail, list):
        detail = detail[0] if detail else {}
    if not detail:
        print(f"❌ 未找到策略: {args.policy_uuid}", file=sys.stderr)
        sys.exit(1)

    try:
        limit = client.load("getLimit") or {}
    except Exception:
        limit = {}
    if isinstance(limit, list):
        limit = limit[0] if limit else {}

    # 基本信息
    print(f"策略详情：{args.policy_uuid}\n")
    print(f"  名称    : {_fmt(detail.get('name'))}")
    print(f"  描述    : {_fmt(detail.get('desc'))}")
    print(f"  类型    : {_fmt(detail.get('policyType'))}")
    print(f"  启用    : {'✓' if detail.get('status') else '✗'}")
    print(f"  系统策略: {'★ 是（name/rule 不可改）' if detail.get('system') else '否'}")

    # 关联 workspace
    ws = detail.get("workspaces") or []
    if ws:
        print(f"\n  应用范围（{len(ws)} 个 workspace）:")
        for w in ws[:20]:
            print(f"    {_fmt(w.get('workspaceId')):<12} {_fmt(w.get('workspaceName'))}")
        if len(ws) > 20:
            print(f"    ... 还有 {len(ws) - 20} 个")
    else:
        print(f"\n  应用范围  : （无）")

    # 策略内容 + cap 对照
    content = detail.get("rawContent") or {}
    if content:
        print(f"\n  策略内容:")
        version = limit.get("versionType") or "?"
        cap_map = {
            "maxLimitOfSingleQuery": limit.get("maxViewCount"),
            "maxLimitOfSingleCopy": limit.get("maxCopyCount"),
            "maxLimitOfSingleDownload": limit.get("maxDownloadCount"),
        }
        for key, label in _POLICY_KEYS:
            if key not in content:
                continue
            val = content[key]
            cap = cap_map.get(key)
            note = ""
            if cap is not None:
                try:
                    vnum = int(val)
                    if vnum > cap:
                        note = f"  ⚠️ 超 cap（{version} 版上限 {cap}，服务端会静默裁剪）"
                    else:
                        note = f"  (cap {cap})"
                except (ValueError, TypeError):
                    pass
            print(f"    {label:<20} {_fmt(val):<12}{note}")

    if limit:
        print(f"\n  当前版本（{_fmt(limit.get('versionType'))}）绝对上限:")
        print(f"    maxViewCount     : {_fmt(limit.get('maxViewCount'))}")
        print(f"    maxCopyCount     : {_fmt(limit.get('maxCopyCount'))}")
        print(f"    maxDownloadCount : {_fmt(limit.get('maxDownloadCount'))}")

    print()
    print(f"→ 更新此策略: create_security_policy.py --policy-uuid {args.policy_uuid} --name <name> --content <json>")
    print(f"→ 列全部策略: list_security_policies.py")


if __name__ == "__main__":
    main()
