#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查某用户在某工作空间当前生效的 DataStudio 安全策略（getMatchedDataStudioPolicyContent）

用于排查：
    - "为什么他不能在 workspace X 下载？" → 查此用户此空间生效的 maxLimitOfSingleDownload
    - "为什么导出 Excel 按钮是灰的？" → 看 allowExportExcel
    - "为什么 ServerIDE 终端用不了？" → 看 allowTerminalInServerIDE

服务端走 RuleEngine#getTopPriorityMatchRule 找最高优先级匹配的策略；即使目标
用户没主动配置也会返回默认值（服务端会 trigger 生成默认策略）。

用法：
    match_security_policy.py                            # 查当前用户（默认全租户）
    match_security_policy.py --workspace-id 12345       # 查当前用户在工作空间 12345 的生效策略
    match_security_policy.py --base-id 012345           # 查他人
    match_security_policy.py --base-id 012345 --workspace-id 12345 --sub-module MyCatalog
"""

import argparse
import sys

from bff_client import BFFClient


_FIELD_LABEL = [
    ("maxLimitOfSingleQuery", "单次查询上限"),
    ("maxLimitOfSingleCopy", "单次复制上限"),
    ("maxLimitOfSingleDownload", "单次下载上限"),
    ("allowExportExcel", "允许导出 Excel"),
    ("allowExtensionInServerIDE", "ServerIDE 扩展"),
    ("allowTerminalInServerIDE", "ServerIDE 终端"),
    ("allowDownloadMountedWorkspaceFile", "挂载目录文件下载"),
    ("allowDownloadInMyCatalog", "MyCatalog 文件下载"),
]


def _fmt(v):
    if v is None:
        return "(未设置)"
    if isinstance(v, bool):
        return "✓" if v else "✗"
    return str(v)


def main():
    p = argparse.ArgumentParser(description="查当前生效的 DataStudio 安全策略")
    p.add_argument("--base-id",
                   help="目标用户 baseId；不传则查当前用户")
    p.add_argument("--workspace-id", type=int,
                   help="按工作空间过滤；不传返全租户默认策略")
    p.add_argument("--sub-module", choices=["MyCatalog"],
                   help="子模块（可选）")
    args = p.parse_args()

    client = BFFClient(quiet=True)

    # 默认用当前用户
    if args.base_id:
        base_id = args.base_id
        self_ref = False
    else:
        try:
            base_id = client.get_my_base_id()
            self_ref = True
        except Exception as e:
            print(f"❌ 无法获取当前用户 baseId: {e}", file=sys.stderr)
            print("→ 改传 --base-id <baseId>", file=sys.stderr)
            sys.exit(1)

    kwargs = {"baseId": str(base_id)}
    if args.workspace_id is not None:
        kwargs["workspaceId"] = str(args.workspace_id)
    if args.sub_module:
        kwargs["subModule"] = args.sub_module

    try:
        content = client.load("getMatchedDataStudioPolicyContent", **kwargs) or {}
    except Exception as e:
        print(f"❌ 查询生效策略失败: {e}", file=sys.stderr)
        sys.exit(1)
    if isinstance(content, list):
        content = content[0] if content else {}

    who = f"当前用户({base_id})" if self_ref else f"用户 {base_id}"
    ws = f"workspace {args.workspace_id}" if args.workspace_id else "（不限 workspace）"
    module = args.sub_module or "DataStudio（主）"

    print(f"生效策略：{who} / {ws} / {module}\n")

    if not content:
        print("  (服务端返回空)")
        return

    for k, label in _FIELD_LABEL:
        if k in content:
            print(f"  {label:<22} {_fmt(content[k])}")

    # 其他未列字段（兜底展示）
    known = {k for k, _ in _FIELD_LABEL}
    extra = {k: v for k, v in content.items() if k not in known}
    if extra:
        print(f"\n  其他字段:")
        for k in sorted(extra):
            print(f"    {k:<30} {_fmt(extra[k])}")

    # 用户提示
    if args.workspace_id is None:
        print()
        print(f"→ 想看具体工作空间下生效的：加 --workspace-id <id>")
    print(f"→ 看所有策略清单: list_security_policies.py")


if __name__ == "__main__":
    main()
