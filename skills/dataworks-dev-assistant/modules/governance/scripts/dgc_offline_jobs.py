#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线作业治理 — 阶段分布 + 治理计划 + 扫描排序

查看离线作业在各阶段的状态分布、责任人分布、治理计划运行情况。
管理员可查看任意用户的离线作业治理情况。

用法:
    python dgc_offline_jobs.py                              # 查看当前用户（个人视角）
    python dgc_offline_jobs.py --owner-id 012345            # 查看指定用户
    python dgc_offline_jobs.py --workspace                  # 工作空间视角（全局）
    python dgc_offline_jobs.py --target-type TABLE          # 按表维度（默认）
    python dgc_offline_jobs.py --project-id 14255           # 指定项目

涉及 API: queryOfflineJobStages, queryOfflineStatusListStageStatus,
          queryOfflineJobOwnerNodeOwner, queryOfflineTargetUuid,
          searchPlans, sortScanner
"""

import argparse
import sys
import os

from bff_client import BFFClient


def main():
    parser = argparse.ArgumentParser(description="离线作业治理")
    parser.add_argument("--owner-id", help="目标用户 ID（不传则默认当前用户）")
    parser.add_argument("--workspace", action="store_true", help="工作空间视角（viewType=1），默认个人视角（viewType=2）")
    parser.add_argument("--target-type", default="TABLE", help="维度：TABLE（默认）")
    parser.add_argument("--project-id", type=int, help="项目 ID（扫描排序时需要）")
    args = parser.parse_args()

    client = BFFClient()

    view_type = "1" if args.workspace else "2"
    owner_id = args.owner_id or client.get_my_base_id()

    # 1. 离线作业阶段分布（按 TABLE 维度）
    stage_common = dict(viewType="TABLE", targetType=args.target_type)

    stages = client.load("queryOfflineJobStages", **stage_common)
    print(f"\n━━ 离线作业阶段 ━━")
    if isinstance(stages, list):
        for s in stages:
            label = s.get("label", "?") if isinstance(s, dict) else str(s)
            print(f"  {label}")

    # 2. 责任人分布
    owners = client.load("queryOfflineJobOwnerNodeOwner", **stage_common)
    if isinstance(owners, list):
        print(f"\n━━ 责任人分布（{len(owners)} 人）━━")
        for o in owners[:15]:
            if isinstance(o, dict):
                print(f"  {o.get('label', '?')} ({o.get('value', '?')})")
            else:
                print(f"  {o}")
        if len(owners) > 15:
            print(f"  ... 还有 {len(owners) - 15} 人")

    # 3. 治理计划
    plans = client.load("searchPlans",
                        viewType=view_type, ownerId=owner_id,
                        sortField="gmtCreate", sortDir="DESC")
    scope_label = "工作空间" if args.workspace else f"用户 {owner_id}"
    print(f"\n━━ 治理计划（{scope_label}）━━")
    if isinstance(plans, list):
        if not plans:
            print("  无治理计划")
        for p in plans:
            name = p.get("name", "?")
            status = p.get("status", "?")
            owner_name = p.get("ownerName", "")
            template = p.get("templateCodeName", "")
            print(f"  [{status}] {name}  负责人={owner_name}  模板={template}")
    else:
        print(f"  {plans}")

    # 4. 扫描排序（需要 projectId）
    if args.project_id:
        scanners = client.load("sortScanner",
                               viewType=view_type, ownerId=owner_id,
                               type="3", subType="1",
                               projectId=str(args.project_id), pageSize="20")
        print(f"\n━━ 扫描排序（项目 {args.project_id}）━━")
        if isinstance(scanners, list):
            for s in scanners[:10]:
                if isinstance(s, dict):
                    print(f"  {s.get('name', s.get('label', s))}")
                else:
                    print(f"  {s}")
        else:
            print(f"  {scanners}")


if __name__ == "__main__":
    main()
