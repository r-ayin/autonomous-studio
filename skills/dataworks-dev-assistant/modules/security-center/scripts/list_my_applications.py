#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""我的权限申请列表（dsm-guard 系统的「我提交的申请单」）

页面：pre-dataworks/cn-beijing/guard#/application-approval/my-applications

用法：
    list_my_applications.py                                # 全部
    list_my_applications.py --status 审批中                  # 0=审批中 / 1=通过 / 2=拒绝
    list_my_applications.py --apply-type MaxComputeTable    # 按 applyType 串过滤（自动转 engineType+objectType）
    list_my_applications.py --project cwy_test_bj_0422      # 按项目过滤
    list_my_applications.py --object cwy_test_bj_0422.sql_test_pt_01    # 按对象（schema.table 自动拆）
    list_my_applications.py --limit 50                      # 上限 50

注意：本脚本属 dsm-guard 老审批系统，与 security-center 新审批策略（list_approval_policies）是两套互不重叠的体系。
本系统管「权限申请单」（资源访问授权流程），后者管「审批策略配置」。
"""

import argparse
import sys
from bff_client import BFFClient


# 申请状态串 → int（来自 dsm-guard Constant.WEB_APPROVE_STATUS_*）
_STATUS_MAP = {"审批中": 0, "通过": 1, "拒绝": 2}
_STATUS_REV = {v: k for k, v in _STATUS_MAP.items()}

# applyType 串 → (engineType, objectType) 元组（来自 ApplyTypeEnum.java）
# engineType: 1=ODPS, 2=EMR, 4=DLF, 5=HOLO, 6=STAR_ROCKS, 7=LINDORM, 9=DI, 10=Open, 11=DGC, 14=DLFNEXT
# objectType: 2=TABLE, 2048=SCHEMA
_APPLY_TYPE_MAP = {
    "MaxComputeTable": (1, 2),
    "DLFTable":        (4, 2),
    "DLFSchema":       (4, 2048),
    "DLFNextTable":    (14, 2),
    "DLFNextDatabase": (14, 2048),
    "HologresTable":   (5, 2),
    "StarRocksTable":  (6, 2),
    "StarRocksSchema": (6, 2048),
    "EmrTable":        (2, 2),
    "EmrSchema":       (2, 2048),
    "LindormTable":    (7, 2),
    "DsApiDeploy":     (8, 2048),
    "DIJobs":          (9, 2048),
}


def main():
    p = argparse.ArgumentParser(description="dsm-guard 我的权限申请列表")
    p.add_argument("--status", help="审批状态: 审批中/通过/拒绝（或直接传 0/1/2）")
    p.add_argument("--apply-type", choices=list(_APPLY_TYPE_MAP.keys()),
                   help="applyType 串，自动转换为 engineType+objectType")
    p.add_argument("--engine-type", type=int,
                   help="数字 engineType（1=ODPS/4=DLF/5=HOLO/6=STAR_ROCKS/...），未传时默认 1=ODPS")
    p.add_argument("--object-type", type=int,
                   help="数字 objectType（2=TABLE/2048=SCHEMA/4096=COLUMN）")
    p.add_argument("--workspace", type=int, help="workspaceId")
    p.add_argument("--project", help="projectName 过滤")
    p.add_argument("--object", help="对象名（支持 schema.table 自动取后段）")
    p.add_argument("--apply-date", help="申请日期")
    p.add_argument("--env", type=int, help="envCode")
    p.add_argument("--limit", type=int, default=50, help="返回上限（默认 50）")
    args = p.parse_args()

    body = {
        "current": 1,
        "pageSize": min(args.limit, 200),
        "orderType": 1,
    }

    # status
    if args.status:
        if args.status in _STATUS_MAP:
            body["approveStatus"] = _STATUS_MAP[args.status]
        elif args.status.isdigit():
            body["approveStatus"] = int(args.status)
        else:
            print(f"❌ --status 取值: 审批中/通过/拒绝 或 0/1/2，收到: {args.status}", file=sys.stderr)
            sys.exit(1)

    # applyType → engineType+objectType
    if args.apply_type:
        eng, obj = _APPLY_TYPE_MAP[args.apply_type]
        body["engineType"] = eng
        body["objectType"] = obj
    if args.engine_type is not None:
        body["engineType"] = args.engine_type
    if args.object_type is not None:
        body["objectType"] = args.object_type

    if args.workspace is not None:
        body["workspace"] = args.workspace
    if args.project:
        body["projectName"] = args.project
    if args.object:
        body["objectName"] = args.object
    if args.apply_date:
        body["applyDate"] = args.apply_date
    if args.env is not None:
        body["envCode"] = args.env

    client = BFFClient(quiet=True)
    rows = client.load("listApply", **body) or []

    if not rows:
        print("无申请记录")
        print("→ 放宽过滤再试：去掉 --status / --apply-type")
        print("→ 看可申请的对象类型：list_my_applications.py --apply-type MaxComputeTable / DLFTable / HologresTable 等")
        return

    print(f"返回 {len(rows)} 条申请单\n")
    print(f"  {'orderId':<38} {'申请类型':<16} {'状态':<8} {'项目.对象':<40} {'申请时间':<17} {'workspace'}")
    print(f"  {'-'*38} {'-'*16} {'-'*8} {'-'*40} {'-'*17} {'-'*10}")
    for r in rows:
        oid = (r.get("orderId") or "")[:38]
        # 还原 applyType 显示
        atype = r.get("applyType") or r.get("orderType") or ""
        atype = atype[:16]
        st_int = r.get("approveStatus")
        st = r.get("approveStatusDesc") or _STATUS_REV.get(st_int, str(st_int))
        st = st[:8]
        proj = r.get("projectName") or ""
        tables = r.get("tableNameList") or []
        obj = (tables[0] if tables else "")[:40 - len(proj) - 1] if proj else (tables[0] if tables else "")[:40]
        loc = f"{proj}.{obj}" if proj and not (obj.startswith(proj + ".")) else (obj or proj)
        loc = loc[:40]
        date = (r.get("applyDate") or "")[:17]
        ws = (r.get("workspaceName") or "")[:10]
        print(f"  {oid:<38} {atype:<16} {st:<8} {loc:<40} {date:<17} {ws}")

    last_table = getattr(client, "last_table", None) or "listApply_rN_cN"
    print()
    print(f"→ 看单笔申请详情: API getApplyOrderDetail（暂未脚本化，可 curl /guard/getApplyOrderDetail?orderId=xxx 看）")
    print(f"→ 撤销审批中的申请: API cancelPermission（写操作，待脚本化）")
    print(f"→ 仅看审批中: list_my_applications.py --status 审批中")
    print(f"→ duckdb 表 {last_table}：字段 orderId(主键) / approveStatus(0/1/2 INT) / approveStatusDesc / applyDate / projectName / tableNameList(LIST<VARCHAR>) / workspaceId(INT)")


if __name__ == "__main__":
    main()
