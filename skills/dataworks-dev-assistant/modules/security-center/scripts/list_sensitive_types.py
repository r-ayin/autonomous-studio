#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出当前租户已启用的敏感类型（给 agent/用户选择用，避免乱编类型名）

用法:
    list_sensitive_types.py                             # 树形结构（分类 + 叶子）
    list_sensitive_types.py --category 个人信息          # 仅该分类下的叶子
    list_sensitive_types.py --leaf-only                 # 只输出叶子名，逗号分隔，直接喂 view --sensitive-type
    list_sensitive_types.py --keyword 手机              # 模糊匹配叶子名

⚠️ 敏感类型是**租户级全局配置**，无法 per-task 排除/定制（createRecognitionTask DTO 已核验）。
本脚本用途：
  · 让用户/agent 从真实清单里选，而非凭空编造类型名
  · 选中的叶子名可直接传给 view_recognition_result.py --sensitive-type 过滤结果
"""

import argparse
import sys
from bff_client import BFFClient


def _walk(node, parent_path="", out=None):
    """递归展开树：返回 [(category_path, leaf_name)]"""
    if out is None:
        out = []
    name = node.get("name", "")
    path = f"{parent_path}/{name}" if parent_path else name
    children = node.get("children") or []
    if node.get("type") == "leaf":
        out.append((parent_path, name))
    for ch in children:
        _walk(ch, path, out)
    return out


def main():
    p = argparse.ArgumentParser(description="列出租户启用的敏感类型（树形）")
    p.add_argument("--category", help="按分类名过滤（如 '个人信息' / '账户信息' / '设备敏感信息' 等）")
    p.add_argument("--keyword", help="按叶子名模糊匹配（如 '手机' 匹配 '手机号码'）")
    p.add_argument("--leaf-only", action="store_true",
                   help="仅输出叶子名，逗号分隔单行 —— 直接复制到 view_recognition_result.py --sensitive-type")
    args = p.parse_args()

    client = BFFClient(quiet=True)
    tree = client.load("listClassificationEnabledSensitiveTypeNames")
    if not isinstance(tree, dict) or not tree.get("children"):
        print("当前租户未启用任何敏感类型模板")
        print("→ 去 DataWorks 控制台 → 数据保护伞 → 敏感类型管理 启用")
        sys.exit(0)

    all_leaves = _walk(tree)  # [(category, leaf_name)]

    # 过滤
    filtered = all_leaves
    if args.category:
        filtered = [(c, n) for c, n in filtered if args.category in c]
    if args.keyword:
        kw = args.keyword.lower()
        filtered = [(c, n) for c, n in filtered if kw in n.lower()]

    if not filtered:
        print(f"无匹配敏感类型（--category={args.category} --keyword={args.keyword}）")
        print("→ 去掉过滤参数看全量: list_sensitive_types.py")
        sys.exit(0)

    if args.leaf_only:
        # 单行逗号分隔，方便 agent 复制
        names = sorted({n for _, n in filtered})
        print(",".join(names))
        return

    # 默认：按分类分组展示
    print(f"模板「{tree.get('name', '')}」：共 {len(all_leaves)} 种敏感类型"
          + (f"（过滤后 {len(filtered)} 种）" if len(filtered) != len(all_leaves) else ""))
    print()

    from collections import defaultdict
    by_cat = defaultdict(list)
    for cat, leaf in filtered:
        by_cat[cat].append(leaf)

    for cat in sorted(by_cat):
        leaves = sorted(by_cat[cat])
        # 分类路径去掉根节点名（通用模板）
        display_cat = cat.split("/", 1)[1] if "/" in cat else cat
        print(f"━━ {display_cat}（{len(leaves)} 项）━━")
        for n in leaves:
            print(f"  · {n}")
        print()

    # 引导 agent 下一步
    print("→ 按敏感类型过滤识别结果: view_recognition_result.py --sensitive-type \"身份证,手机号码\"")
    print("→ 只输出叶子名（逗号分隔，方便直接传参）: list_sensitive_types.py --leaf-only")
    print("→ ⚠️ 敏感类型是租户级全局配置，创建任务时无法 per-task 排除，请勿构造 taskConfig.sensitiveTypes")


if __name__ == "__main__":
    main()
