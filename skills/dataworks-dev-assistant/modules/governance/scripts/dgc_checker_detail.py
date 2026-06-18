#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描器/规则详情 — 按项目看扫描结果 + 扫描器排行 + 解决方案

从 dgc_scanner.py 概览下钻到具体项目的扫描器检查明细。

用法:
    python dgc_checker_detail.py --project-id 14255                  # 查看项目的扫描器检查结果
    python dgc_checker_detail.py --owner-id 083361                   # 按用户看扫描器排行
    python dgc_checker_detail.py --project-id 14255 --solution DG-D-1  # 查看某条治理建议

涉及 API: searchProjectCheckers, sortCheckers, getCheckerMetric, getCheckerChart, getSolution
"""

import argparse

from bff_client import BFFClient


def main():
    parser = argparse.ArgumentParser(description="扫描器/规则详情")
    parser.add_argument("--project-id", type=int, help="项目 ID（查看该项目的扫描器检查结果）")
    parser.add_argument("--owner-id", help="用户 ID（不传则默认当前用户）")
    parser.add_argument("--solution", help="查看治理建议详情（如 DG-D-1）")
    parser.add_argument("--workspace", action="store_true", help="工作空间视角")
    args = parser.parse_args()

    client = BFFClient()
    owner_id = args.owner_id or client.get_my_base_id()
    view_type = "1" if args.workspace else "2"

    # 查治理建议详情
    if args.solution:
        sol = client.load("getSolution", id=args.solution)
        print(f"\n━━ 治理建议 {args.solution} ━━")
        if isinstance(sol, dict):
            print(f"  名称: {sol.get('name', '?')}")
            print(f"  说明: {sol.get('intro', '?')}")
            guide = sol.get("guide", "")
            if guide:
                print(f"  操作指引: {guide[:300]}")
            doc = sol.get("docUrl", "")
            if doc:
                print(f"  文档: {doc}")
        else:
            print(f"  {sol}")
        return

    # 1. 扫描器指标汇总
    metric = client.load("getCheckerMetric", viewType=view_type, ownerId=owner_id)
    scope_label = "工作空间" if args.workspace else f"用户 {owner_id}"
    print(f"\n━━ 扫描器指标（{scope_label}）━━")
    if isinstance(metric, dict):
        def _val(v):
            return v.get("count", v) if isinstance(v, dict) else v
        def _ratio(v):
            return f"{v.get('count', 0):.0%}" if isinstance(v, dict) else v
        total = _val(metric.get("totalCheck", 0))
        block = _val(metric.get("checkBlock", 0))
        block_ratio = _ratio(metric.get("checkBlockRatio", "?"))
        warning = _val(metric.get("checkWarning", 0))
        warning_ratio = _ratio(metric.get("checkWarningRatio", "?"))
        print(f"  检查总数: {int(total)}")
        print(f"  阻塞: {int(block)} ({block_ratio})")
        print(f"  告警: {int(warning)} ({warning_ratio})")
    else:
        print(f"  {metric}")

    # 2. 扫描器排行（按问题数排序）
    checkers = client.load("sortCheckers",
                           viewType=view_type, ownerId=owner_id,
                           type="3", subType="1",
                           projectId=str(args.project_id) if args.project_id else "0",
                           pageSize="20")
    print(f"\n━━ 扫描器排行（TOP 15）━━")
    if isinstance(checkers, list):
        has_issues = [c for c in checkers if isinstance(c, dict) and (c.get("checkBlock", 0) or 0) + (c.get("checkWarning", 0) or 0) > 0]
        if not has_issues:
            print("  全部通过")
        for c in has_issues[:15]:
            name = c.get("rankObjectName", c.get("name", c.get("baseId", "?")))
            block = c.get("checkBlock", 0) or 0
            warning = c.get("checkWarning", 0) or 0
            total = c.get("totalCheck", 0) or 0
            print(f"  {name}: 阻塞={block} 告警={warning} 总检查={total}")
    else:
        print(f"  {checkers}")

    # 3. 按项目查扫描器检查结果
    if args.project_id:
        project_checkers = client.load("searchProjectCheckers",
                                       projectId=str(args.project_id), field="5")
        print(f"\n━━ 项目 {args.project_id} 的扫描器（{len(project_checkers) if isinstance(project_checkers, list) else '?'} 个）━━")
        if isinstance(project_checkers, list):
            open_checkers = [c for c in project_checkers if isinstance(c, dict) and c.get("isOpen")]
            closed = len(project_checkers) - len(open_checkers)
            print(f"  已开启: {len(open_checkers)}  未开启: {closed}")
            # 列出有问题的
            for c in open_checkers[:20]:
                code = c.get("code", "?")
                name = c.get("name", code)
                controlled = c.get("controlled", False)
                tag = " [管控]" if controlled else ""
                print(f"  [{code}] {name}{tag}")
        else:
            print(f"  {project_checkers}")

    # chain hints
    print(f"\n  💡 查看治理建议: python dgc_checker_detail.py --solution DG-D-<编号>")
    print(f"  💡 返回扫描器概览: python dgc_scanner.py")


if __name__ == "__main__":
    main()
