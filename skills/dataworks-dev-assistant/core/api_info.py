#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""api_info.py — 从 api-index.json 直出接口说明

场景：agent/开发在对话里问"xxx 接口的入参是什么 / 返回什么 / 是写操作吗"，
避免 grep 源码或读 api-index.json 整个文件。

用法:
    python api_info.py <action>                  # 精确查一条
    python api_info.py <keyword> --search        # 模糊搜（按名字/路径/描述/key_fields）
    python api_info.py --list-writes             # 列出所有写操作
    python api_info.py runRules --json           # JSON 原文输出（下游消费用）
"""

import argparse
import json
import os
import sys
from pathlib import Path


def _resolve_index_path():
    # 本文件在 core/ 下，api-index.json 在 core/references/
    here = Path(__file__).resolve().parent
    candidates = [
        here / "references" / "api-index.json",            # 主路径（src/core 或 dist/.../core）
        here.parent / "references" / "api-index.json",     # 兜底
    ]
    for p in candidates:
        if p.exists():
            return p
    print(f"api-index.json 未找到，尝试过: {[str(c) for c in candidates]}", file=sys.stderr)
    sys.exit(1)


def _load_index():
    path = _resolve_index_path()
    with open(path) as f:
        doc = json.load(f)
    return doc.get("api_index") or {}, path


def _print_one(name, meta, show_related=True):
    path = meta.get("path", "?")
    method = meta.get("method", "?")
    params_type = meta.get("params_type") or "—"
    rstruct = meta.get("return_structure") or "—"
    is_write = meta.get("is_write_operation", False)
    ct = meta.get("content_type") or "—"

    print(f"━━ {name} ━━")
    print(f"  path:           {path}")
    print(f"  method:         {method}")
    print(f"  params_type:    {params_type}")
    print(f"  content_type:   {ct}")
    print(f"  return:         {rstruct}")
    print(f"  is_write:       {'✅ 是（需 client.write / confirmed=True）' if is_write else '否（只读）'}")

    desc = meta.get("description")
    if desc:
        print(f"  description:    {desc}")

    kf = meta.get("key_fields") or {}
    if kf:
        print(f"\n  入参字段:")
        # 对齐列宽
        w = max((len(k) for k in kf.keys()), default=0) + 2
        for k, v in kf.items():
            print(f"    {k.ljust(w)}{v}")

    notes = meta.get("notes")
    if notes:
        print(f"\n  notes:")
        for line in str(notes).splitlines() or [notes]:
            print(f"    {line}")

    id_map = meta.get("id_mapping")
    if id_map:
        print(f"\n  id 映射: {json.dumps(id_map, ensure_ascii=False)}")

    pk = meta.get("primary_key")
    if pk:
        print(f"  primary_key:    {pk}")

    invalid = meta.get("invalidates")
    if invalid:
        print(f"  invalidates:    {', '.join(invalid)}")

    if show_related:
        rel = meta.get("related_apis") or []
        if rel:
            print(f"\n  related:        {', '.join(rel)}")


def _search(api_index, keyword, limit=20):
    kw = keyword.lower()
    hits = []
    for name, meta in api_index.items():
        if not isinstance(meta, dict):
            continue
        haystack_parts = [
            name,
            str(meta.get("path") or ""),
            str(meta.get("description") or ""),
            str(meta.get("notes") or ""),
            " ".join((meta.get("key_fields") or {}).keys()),
        ]
        hay = " ".join(haystack_parts).lower()
        if kw in hay:
            hits.append((name, meta))
    return hits[:limit]


def main():
    parser = argparse.ArgumentParser(
        description="查询 DataWorks BFF API 元数据（从 api-index.json 提取）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("name", nargs="?", help="API 名称（精确匹配）")
    parser.add_argument("--search", action="store_true", help="模糊搜索模式（name 当关键字）")
    parser.add_argument("--list-writes", action="store_true", help="列出所有写操作 API")
    parser.add_argument("--json", action="store_true", help="输出 JSON 原始 meta")
    args = parser.parse_args()

    api_index, index_path = _load_index()
    print(f"[api-index: {index_path}, 共 {len(api_index)} 个 API]", file=sys.stderr)

    if args.list_writes:
        writes = [(k, v) for k, v in api_index.items()
                  if isinstance(v, dict) and v.get("is_write_operation")]
        print(f"写操作 API: {len(writes)} 个")
        for name, meta in sorted(writes):
            desc = meta.get("description") or ""
            print(f"  {name}  [{meta.get('method')} {meta.get('path')}]  {desc[:60]}")
        return

    if not args.name:
        parser.error("需要 <action> 或 --list-writes")

    if args.search:
        hits = _search(api_index, args.name)
        if not hits:
            print(f"未找到含 '{args.name}' 的 API", file=sys.stderr)
            sys.exit(1)
        print(f"命中 {len(hits)} 个 API:\n")
        for name, meta in hits:
            desc = meta.get("description") or ""
            print(f"  {name}  [{meta.get('method')} {meta.get('path')}]\n    {desc[:100]}")
        print(f"\n→ 查详情: python api_info.py <name>")
        return

    meta = api_index.get(args.name)
    if not meta:
        # 精确未命中自动降级到模糊
        hits = _search(api_index, args.name, limit=5)
        print(f"未找到精确匹配 '{args.name}'", file=sys.stderr)
        if hits:
            print(f"你是想找：", file=sys.stderr)
            for name, _ in hits:
                print(f"  - {name}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({args.name: meta}, ensure_ascii=False, indent=2))
        return

    _print_one(args.name, meta)


if __name__ == "__main__":
    main()
