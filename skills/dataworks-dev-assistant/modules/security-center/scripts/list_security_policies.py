#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出 DataStudio 安全策略（searchDataSecurityPolicies）

安全策略控制工作空间的 DataStudio 行为：
    - maxLimitOfSingleQuery / Copy / Download：单次查询/复制/下载的行数上限
    - allowExportExcel / allowExtensionInServerIDE / allowTerminalInServerIDE
      / allowDownloadMountedWorkspaceFile：布尔开关

用法：
    list_security_policies.py                              # 默认 policyType=DataStudio，第 1 页 × 10 条
    list_security_policies.py --all                        # 三类全返（DataStudio / DataStudio_MyCatalog / DataQuery）
    list_security_policies.py --type DataStudio_MyCatalog  # 指定类型
    list_security_policies.py --limit 50 --page 2
"""

import argparse
import sys

from bff_client import BFFClient


def _fmt(v, width=None):
    s = str(v) if v is not None else ""
    return s[:width] if width else s


def main():
    p = argparse.ArgumentParser(description="列出 DataStudio 安全策略")
    p.add_argument("--type", choices=["DataStudio", "DataStudio_MyCatalog", "DataQuery"],
                   default="DataStudio",
                   help="策略类型（默认 DataStudio）。--all 会忽略此参数")
    p.add_argument("--all", action="store_true", help="三类全返（不限 policyType）")
    p.add_argument("--limit", type=int, default=10,
                   help="每页数量（默认 10，上限 200）")
    p.add_argument("--page", type=int, default=1, help="页码（默认 1）")
    args = p.parse_args()

    page_size = min(args.limit, 200)

    kwargs = {"current": args.page, "pageSize": page_size}
    if not args.all:
        kwargs["policyType"] = args.type

    client = BFFClient(quiet=True)
    rows = client.load("searchDataSecurityPolicies", **kwargs) or []
    rows = rows if isinstance(rows, list) else []

    if not rows:
        scope = "（三类）" if args.all else f"(type={args.type})"
        print(f"无策略 {scope}")
        return

    scope = "三类" if args.all else args.type
    print(f"{scope} 策略列表（第 {args.page} 页，{len(rows)} 条）\n")
    print(f"  {'policyUuid':<38} {'type':<22} {'name':<40} {'启用':<6} {'系统':<6} {'workspaces':<12}")
    print(f"  {'-'*38} {'-'*22} {'-'*40} {'-'*6} {'-'*6} {'-'*12}")

    for r in rows:
        uuid = _fmt(r.get("policyUuid"), 38)
        ptype = _fmt(r.get("policyType"), 22)
        name = _fmt(r.get("name"), 40)
        status = "✓" if r.get("status") else "✗"
        system = "★" if r.get("system") else " "
        ws = r.get("workspaces") or []
        ws_str = f"{len(ws)} 个" if ws else "-"
        print(f"  {uuid:<38} {ptype:<22} {name:<40} {status:<6} {system:<6} {ws_str:<12}")

    print()
    print(f"→ 查单条详情: get_security_policy.py --policy-uuid <policyUuid>")
    print(f"→ 创建/更新:  create_security_policy.py --name <name> --content <json>")
    if len(rows) == page_size:
        print(f"→ 下一页:     list_security_policies.py --page {args.page + 1} --limit {args.limit}"
              + (" --all" if args.all else f" --type {args.type}"))


if __name__ == "__main__":
    main()
