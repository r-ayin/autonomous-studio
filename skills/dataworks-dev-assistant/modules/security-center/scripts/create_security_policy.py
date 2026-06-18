#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""创建 / 更新 DataStudio 安全策略（createDataStudioSecurityPolicy，upsert）

⚠️ 两阶段写操作：Phase 1 输出确认摘要（含 cap 预检），Phase 2（--confirm）才真正提交。
⚠️ upsert 语义：传 --policy-uuid 就是更新，不传就是创建。

策略内容 7 字段（Phase 1 脚本会自动做版本 cap 预检）：
    maxLimitOfSingleQuery    单次查询上限（硬 cap 10000）
    maxLimitOfSingleCopy     单次复制上限（硬 cap 10000）
    maxLimitOfSingleDownload 单次下载上限（版本 cap：BASIC=0 / STANDARD=200000 / PROFESSIONAL=2000000 / ENTERPRISE=5000000）
    allowExportExcel         bool
    allowExtensionInServerIDE       bool
    allowTerminalInServerIDE        bool
    allowDownloadMountedWorkspaceFile  bool

用法：
    # Phase 1（创建）：
    create_security_policy.py \\
        --name DISABLE_DOWNLOAD_2026 \\
        --desc "禁止生产空间下载" \\
        --workspace-ids 12345,67890 \\
        --set maxLimitOfSingleDownload=0 \\
        --set allowExportExcel=false

    # Phase 1（更新已有）：
    create_security_policy.py --policy-uuid abc-123 --set maxLimitOfSingleQuery=5000

    # Phase 2：
    create_security_policy.py --confirm
"""

import argparse
import json
import sys

from bff_client import BFFClient


_BOOL_KEYS = {
    "allowExportExcel",
    "allowExtensionInServerIDE",
    "allowTerminalInServerIDE",
    "allowDownloadMountedWorkspaceFile",
    "allowDownloadInMyCatalog",
}
_LONG_KEYS = {
    "maxLimitOfSingleQuery",
    "maxLimitOfSingleCopy",
    "maxLimitOfSingleDownload",
}
_ALL_KEYS = _BOOL_KEYS | _LONG_KEYS


def _parse_set(entries):
    """--set key=value 解析"""
    out = {}
    for e in entries or []:
        if "=" not in e:
            raise SystemExit(f"--set 格式错误，期望 key=value，实际: {e}")
        k, v = e.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k not in _ALL_KEYS:
            raise SystemExit(f"--set 未知字段: {k}（合法：{', '.join(sorted(_ALL_KEYS))}）")
        if k in _BOOL_KEYS:
            lv = v.lower()
            if lv not in ("true", "false"):
                raise SystemExit(f"--set {k} 必须是 true/false，实际: {v}")
            out[k] = lv == "true"
        else:
            try:
                out[k] = int(v)
            except ValueError:
                raise SystemExit(f"--set {k} 必须是整数，实际: {v}")
    return out


def _pre_check_cap(client, content):
    """拉 getLimit 对超 cap 字段给 warning（不阻塞，服务端会静默裁剪）"""
    try:
        limit = client.load("getLimit") or {}
    except Exception:
        return None
    if isinstance(limit, list):
        limit = limit[0] if limit else {}

    warnings = []
    cap_map = {
        "maxLimitOfSingleQuery": limit.get("maxViewCount"),
        "maxLimitOfSingleCopy": limit.get("maxCopyCount"),
        "maxLimitOfSingleDownload": limit.get("maxDownloadCount"),
    }
    version = limit.get("versionType") or "?"
    for k, cap in cap_map.items():
        if cap is None or k not in content:
            continue
        try:
            v = int(content[k])
            if v > cap:
                warnings.append((k, v, cap))
        except (ValueError, TypeError):
            pass
    return {"version": version, "warnings": warnings, "caps": cap_map}


def main():
    p = argparse.ArgumentParser(
        description="创建 / 更新 DataStudio 安全策略（upsert，两阶段确认）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--policy-uuid",
                   help="传了就更新；不传就创建")
    p.add_argument("--name",
                   help="策略名（创建必填；更新时不传则保留原名。⚠️ SYSTEM_ 前缀是系统策略，rule/name 服务端会强制保留）")
    p.add_argument("--desc", help="描述")
    p.add_argument("--workspace-ids", default="",
                   help="应用的 workspace ID 列表，逗号分隔（如 12345,67890）")
    p.add_argument("--sub-module", choices=["MyCatalog"],
                   help="子模块（可选）")
    p.add_argument("--set", action="append", dest="set_entries",
                   help="策略内容字段（可重复），格式 key=value")
    p.add_argument("--content-json",
                   help="直接传完整 policyContent JSON（覆盖 --set）")
    p.add_argument("--confirm", action="store_true", help="Phase 2: 执行提交")
    args = p.parse_args()

    client = BFFClient()

    if args.confirm:
        client.confirm_write()
        return

    # Phase 1 参数校验
    if not args.policy_uuid and not args.name:
        print("❌ 创建模式必须传 --name；若要更新传 --policy-uuid", file=sys.stderr)
        sys.exit(1)

    # 解析 policyContent
    content = {}
    if args.content_json:
        try:
            content = json.loads(args.content_json)
        except json.JSONDecodeError as e:
            print(f"❌ --content-json 解析失败: {e}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(content, dict) or not content:
            print("❌ --content-json 必须是非空 JSON 对象", file=sys.stderr)
            sys.exit(1)
    else:
        content = _parse_set(args.set_entries)

    if not content and not args.policy_uuid:
        # 创建必须给内容（@NotEmpty policyContent）
        print("❌ 创建时 policyContent 不能为空，请用 --set 或 --content-json 指定", file=sys.stderr)
        sys.exit(1)

    # workspace-ids
    ws_ids = []
    if args.workspace_ids.strip():
        for s in args.workspace_ids.split(","):
            s = s.strip()
            if not s:
                continue
            try:
                ws_ids.append(int(s))
            except ValueError:
                print(f"❌ --workspace-ids 必须是整数列表: {s!r}", file=sys.stderr)
                sys.exit(1)

    body = {}
    if args.policy_uuid:
        body["policyUuid"] = args.policy_uuid
    if args.name:
        body["name"] = args.name
    if args.desc is not None:
        body["desc"] = args.desc
    if ws_ids:
        body["workspaceIds"] = ws_ids
    if args.sub_module:
        body["subModule"] = args.sub_module
    if content:
        body["policyContent"] = content

    # 预览
    mode = "更新" if args.policy_uuid else "创建"
    print(f"将要{mode} DataStudio 安全策略：\n")
    print(f"  name           : {body.get('name') or '(保留原名)'}")
    if body.get("desc") is not None:
        print(f"  desc           : {body['desc']}")
    if body.get("policyUuid"):
        print(f"  policyUuid     : {body['policyUuid']}")
    if body.get("subModule"):
        print(f"  subModule      : {body['subModule']}")
    if ws_ids:
        print(f"  workspaceIds   : {ws_ids}")
    if content:
        print(f"  policyContent  :")
        for k in sorted(content.keys()):
            print(f"    {k:<36} {content[k]}")

    # cap pre-check（超 cap 不阻塞，给 warning）
    if content:
        check = _pre_check_cap(client, content)
        if check:
            if check["warnings"]:
                print(f"\n  ⚠️ 超 cap 预警（当前版本 {check['version']}；服务端会静默裁剪到 cap）:")
                for k, v, cap in check["warnings"]:
                    print(f"    {k:<36} {v}  >  cap {cap}")
            if args.name and args.name.startswith("SYSTEM_"):
                print(f"\n  ⚠️ 系统策略（SYSTEM_ 前缀）：服务端会忽略 rule/workspaceIds 调整")

    # Phase 1：提交待确认
    client.write("createDataStudioSecurityPolicy", **body)
    print()
    print(f"→ 用户确认后执行: create_security_policy.py --confirm")


if __name__ == "__main__":
    main()
