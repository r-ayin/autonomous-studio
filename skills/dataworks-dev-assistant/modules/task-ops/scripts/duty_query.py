#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
值班表查询 —— 列出工作空间的值班表 / 查指定值班表的排班记录和人员

用法:
    # 列工作空间的值班表
    python duty_query.py --project-id 14255

    # 查指定值班表的排班（默认未来 7 天）+ 排班人员
    python duty_query.py --project-id 14255 --calname <值班表名>

    # 自定义日期范围
    python duty_query.py --project-id 14255 --calname <名> --begin 2026-04-13 --end 2026-04-20
"""

import argparse
import sys
from datetime import datetime, timedelta

from bff_client import BFFClient, save_tool_result, resolve_project_id
from telemetry import telemetry_start, telemetry_end, telemetry_fail


_TAG = "[duty]"


def _call(client, api_name, **kwargs):
    api_meta = client.api_index.get(api_name)
    if not api_meta:
        raise ValueError(f"未找到 API: {api_name}")
    result = client._do_request(api_name, api_meta, **kwargs)
    code = result.get("code")
    if code not in (None, 0, "0", 200, "200"):
        raise RuntimeError(f"{api_name} 失败: code={code}, message={result.get('message','')}")
    return client._parse_return_structure(result, api_meta.get("return_structure", ""))


def main():
    parser = argparse.ArgumentParser(description="值班表查询")
    parser.add_argument("--project-id", type=int)
    parser.add_argument("--project-name")
    parser.add_argument("--calname", help="值班表名（来自不带此参数时的列表）")
    parser.add_argument("--begin", help="开始日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD（默认 7 天后）")
    parser.add_argument("--env", default="prod")
    args = parser.parse_args()

    telemetry_start("duty_query.py", module="task-ops",
                    project_id=args.project_id)

    client = BFFClient(quiet=True)
    project_id = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)
    tenant_id = client.get_tenant_id() if hasattr(client, "get_tenant_id") else 1

    # ── Phase 1: 列值班表 ──
    print(f"{_TAG} 工作空间 {project_id} 的值班表：")
    cals = _call(client, "listCalendars",
                 projectId=project_id, env=args.env, tenantId=tenant_id)
    if not isinstance(cals, list):
        cals = [cals] if cals else []
    if not cals:
        print(f"{_TAG} 未找到值班表")
        save_tool_result("duty_query", {"status": "empty", "project_id": project_id})
        telemetry_end(result={"count": 0})
        return

    print()
    print(f"  {'值班表名 (calname)':<30} {'描述':<30} {'管理员':<20}")
    print(f"  {'─'*30} {'─'*30} {'─'*20}")
    for c in cals:
        print(f"  {(c.get('calname') or '')[:30]:<30} {(c.get('caldesc') or '')[:30]:<30} {(c.get('admins') or '')[:20]:<20}")
    print()

    if not args.calname:
        print(f"{_TAG} → 查指定值班表的排班和人员: --calname <上面的 calname>")
        save_tool_result("duty_query", {
            "status": "ok", "project_id": project_id,
            "count": len(cals), "calendars": [c.get("calname") for c in cals],
        })
        telemetry_end(result={"count": len(cals)})
        return

    # ── Phase 2: 查指定值班表的排班 ──
    today = datetime.now().date()
    begin = args.begin or today.strftime("%Y-%m-%d")
    end = args.end or (today + timedelta(days=7)).strftime("%Y-%m-%d")

    print(f"{_TAG} 「{args.calname}」 排班 ({begin} ~ {end})：")
    schedule = _call(client, "getCalendarDetail",
                     calname=args.calname, begtime=begin, endtime=end, userType=0)
    if not isinstance(schedule, list):
        schedule = [schedule] if schedule else []
    if not schedule:
        print(f"  无排班")
    else:
        print()
        print(f"  {'日期':<14} {'值班人员':<30} {'职责':<20}")
        print(f"  {'─'*14} {'─'*30} {'─'*20}")
        for s in schedule:
            date = s.get("date") or s.get("dutyDate") or s.get("begtime") or ""
            person = s.get("watcherName") or s.get("watcher") or s.get("userName") or ""
            duty = s.get("dutyRole") or s.get("role") or s.get("usertype") or ""
            print(f"  {str(date)[:14]:<14} {str(person)[:30]:<30} {str(duty)[:20]:<20}")
        print()

    # ── Phase 3: 列排班人员（calId 实际传 calname）──
    print(f"{_TAG} 「{args.calname}」 排班人员名单：")
    personnel = _call(client, "listShiftPersonnel", calId=args.calname)
    if not isinstance(personnel, list):
        personnel = [personnel] if personnel else []
    if not personnel:
        print("  无人员")
    else:
        for p in personnel:
            uid = p.get("watcher") or p.get("userId") or ""
            uname = p.get("watcherName") or p.get("userName") or ""
            print(f"  - {uname} ({uid})")
        print()

    save_tool_result("duty_query", {
        "status": "ok", "project_id": project_id,
        "calname": args.calname, "schedule_count": len(schedule),
        "personnel_count": len(personnel),
    })
    telemetry_end(result={"schedule_count": len(schedule)})


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("duty_query.py", "task-ops",
                       e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("duty_query.py", "task-ops", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
