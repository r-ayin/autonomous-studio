#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手动任务大屏 —— 补数据/手动运行的执行概况

用法:
    python manual_biz_overview.py --project-name autotest
    python manual_biz_overview.py --project-id 14255
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

from bff_client import BFFClient, save_tool_result, resolve_project_id
from telemetry import telemetry_start, telemetry_end, telemetry_fail


# ─── 常量 ──────────────────────────────────────────────────────

_TAG = "[manual]"


# ─── 内部 API 调用 ────────────────────────────────────────────

def _api_call(client, api_name, **kwargs):
    api_meta = client.api_index.get(api_name)
    if not api_meta:
        raise ValueError(f"未找到 API: {api_name}")
    result = client._do_request(api_name, api_meta, **kwargs)
    code = result.get("code")
    if code not in (None, 0, "0", 200, "200"):
        msg = result.get("message", "")
        raise RuntimeError(f"{api_name} 失败: code={code}, message={msg}")
    return_structure = api_meta.get("return_structure", "")
    return client._parse_return_structure(result, return_structure)


def _safe_call(client, api_name, **kwargs):
    try:
        return _api_call(client, api_name, **kwargs)
    except Exception:
        return None


# ─── 参数解析 ────────────────────────────────────────────────



# ─── 各板块 ─────────────────────────────────────────────────

def _section_status_dist(client, project_id, today_str):
    """状态分布"""
    data = _safe_call(client, "getManualBizStatusDist",
                      projectId=project_id, env="prod", tenantId=1,
                      startCreateTime=f"{today_str} 00:00:00",
                      endCreateTime=f"{today_str} 23:59:59",
                      owner="false")
    return data


def _section_trend(client, project_id, today_str):
    """执行趋势（外部 + 内部）"""
    outer = _safe_call(client, "getManualBizStatsTrend",
                       projectId=project_id, env="prod", tenantId=1,
                       gmtDate=today_str, inner="false")
    inner = _safe_call(client, "getManualBizStatsTrend",
                       projectId=project_id, env="prod", tenantId=1,
                       gmtDate=today_str, inner="true")
    return outer, inner


def _section_error_rank(client, project_id, today_str):
    """失败排行（外部 + 内部合并）"""
    outer = _safe_call(client, "getManualBizErrorRank",
                       projectId=project_id, env="prod", tenantId=1,
                       startCreateTime=f"{today_str} 00:00:00",
                       endCreateTime=f"{today_str} 23:59:59",
                       inner="false")
    inner = _safe_call(client, "getManualBizErrorRank",
                       projectId=project_id, env="prod", tenantId=1,
                       startCreateTime=f"{today_str} 00:00:00",
                       endCreateTime=f"{today_str} 23:59:59",
                       inner="true")
    return outer, inner


def _section_node_group(client, project_id):
    """节点分组"""
    data = _safe_call(client, "getManualBizNodeGroup",
                      projectId=project_id, env="prod", tenantId=1,
                      groupType=4)
    return data


def _section_instance_list(client, project_id, today_str, page_size=20, create_user=None):
    """手动实例列表（listManualOverview）

    create_user: baseId 字符串，传入后只看该用户创建的实例
    """
    params = dict(
        projectId=project_id, env="prod", tenantId=1,
        dagType=5, flowType=1,
        createTime=f"{today_str} 00:00:00",
        pageNum=1, pageSize=page_size,
        sortOrder="", sortField="",
        includeRelation="false",
        statuses="", instanceTypes="",
        nodeSearchType=0, bizDate="",
    )
    if create_user:
        params["createUser"] = create_user
    return _safe_call(client, "listManualOverview", **params)


def _section_manual_nodes(client, project_id, page_size=100, owner=None):
    """手动任务节点列表（getNodeList?nodeType=1）— 任务定义，非运行实例

    返回 (nodes_list, total_count)：nodes 是前 page_size 条样本，total 是全量总数。
    owner: baseId 字符串，用于按负责人过滤。
    """
    api_meta = client.api_index.get("getNodeList")
    if not api_meta:
        return [], 0
    try:
        params = dict(
            projectId=project_id, env="prod", tenantId=1,
            nodeType=1,
            pageNum=1, pageSize=page_size,
            sortOrder="", sortField="",
            includeRelation="false",
        )
        if owner:
            params["owner"] = owner
        result = client._do_request("getNodeList", api_meta, **params)
        if result.get("code") not in (None, 0, "0", 200, "200"):
            return [], 0
        data_obj = result.get("data") or {}
        nodes = data_obj.get("data") or []
        total = data_obj.get("totalNum") or len(nodes)
        return nodes, total
    except Exception:
        return [], 0


# ─── 输出 ───────────────────────────────────────────────────

def _fmt(n):
    if n is None:
        return "-"
    return str(int(n)) if isinstance(n, (int, float)) else str(n)


_STATUS_FIELD_CN = {
    "successDagCount": "成功",
    "failureDagCount": "失败",
    "runningDagCount": "运行中",
    "notRunDagCount": "未运行",
    "waitTimeDagCount": "等待时间",
    "waitResDagCount": "等资源",
    "totalDagCount": "总计",
}


def _print_status_dist(data):
    if not data:
        print(f"  (无数据)")
        return
    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, (int, float)):
                label = _STATUS_FIELD_CN.get(key, key)
                print(f"  {label}: {_fmt(val)}")
    elif isinstance(data, list):
        for item in data:
            name = item.get("statusName", item.get("name", item.get("status", "")))
            count = item.get("count", item.get("num", ""))
            print(f"  {name}: {_fmt(count)}")


def _print_trend(outer, inner):
    if not outer and not inner:
        print(f"  (无数据)")
        return
    for label, data in [("外部触发", outer), ("内部触发", inner)]:
        if not data:
            continue
        # 时序数据：汇总成功/失败/总计
        if isinstance(data, list):
            total = sum((p.get("totalCount") or 0) for p in data if isinstance(p, dict))
            success = sum((p.get("successCount") or 0) for p in data if isinstance(p, dict))
            fail = sum((p.get("failCount") or p.get("failureCount") or 0) for p in data if isinstance(p, dict))
            print(f"  {label}: 总计 {_fmt(total)}  成功 {_fmt(success)}  失败 {_fmt(fail)}  （{len(data)} 个时段）")
        elif isinstance(data, dict):
            total = data.get("totalCount") or data.get("total") or 0
            success = data.get("successCount") or data.get("success") or 0
            fail = data.get("failCount") or data.get("fail") or 0
            print(f"  {label}: 总计 {_fmt(total)}  成功 {_fmt(success)}  失败 {_fmt(fail)}")


def _print_error_rank(outer, inner):
    items = []
    for data in [outer, inner]:
        if isinstance(data, list):
            items.extend(data)
    if not items:
        print(f"  (无失败任务)")
        return
    # 过滤无名条目（API 偶尔返回没有 nodeName 的占位项）
    named_items = [x for x in items if (x.get("nodeName") or x.get("name"))]
    if not named_items:
        print(f"  (无失败任务)")
        return
    for i, item in enumerate(named_items[:10], 1):
        name = (item.get("nodeName") or item.get("name") or "")[:35]
        count = item.get("errorCount") or item.get("count") or item.get("failCount") or ""
        owner = item.get("ownerName") or item.get("owner") or ""
        print(f"  {i:2d}. {name:<35} 失败 {_fmt(count)} 次  {owner}")


def _print_node_group(data):
    if not data:
        print(f"  (无数据)")
        return
    items = data if isinstance(data, list) else data.get("list", data.get("data", []))
    if not isinstance(items, list):
        print(f"  (无数据)")
        return
    for item in items[:15]:
        name = item.get("groupName", item.get("name", ""))
        count = item.get("count", item.get("num", ""))
        if name and count:
            print(f"  {name}: {_fmt(count)}")


_DAG_STATUS = {0: "未运行", 1: "未运行", 2: "等待中", 3: "准备中", 4: "运行中", 5: "失败", 6: "成功"}


def _print_instance_list(data, project_id):
    """打印手动实例列表，返回失败的 dagIds"""
    if not data:
        print(f"  (无手动实例)")
        return []
    items = data if isinstance(data, list) else []
    if not items:
        print(f"  (无手动实例)")
        return []

    failed_dag_ids = []
    print(f"  {'DAG名称':<30} {'状态':<6} {'成功':<5} {'失败':<5} {'总计':<5} {'创建人'}")
    print(f"  {'─' * 80}")
    for item in items[:30]:
        dag_id = item.get("dagId", "")
        dag_name = (item.get("dagName") or "")[:28]
        status = _DAG_STATUS.get(item.get("status"), str(item.get("status", "?")))
        success = _fmt(item.get("successCount"))
        fail = _fmt(item.get("failureCount"))
        total = _fmt(item.get("totalCount"))
        user = item.get("createUserName") or item.get("createUser") or ""
        print(f"  {dag_name:<30} {status:<6} {success:<5} {fail:<5} {total:<5} {user}")
        if item.get("status") == 5 and dag_id:
            failed_dag_ids.append(dag_id)

    return failed_dag_ids


def _print_manual_nodes(items, total):
    """打印手动任务节点列表（任务定义）"""
    if not items:
        print(f"  (无手动任务节点)")
        return

    from collections import Counter
    owner_counter = Counter()
    prg_type_counter = Counter()
    for n in items:
        owner_name = n.get("ownerName") or n.get("owner") or "(无负责人)"
        owner_counter[owner_name] += 1
        prg = n.get("prgTypeName") or (f"prgType={n.get('prgType')}" if n.get("prgType") else "?")
        prg_type_counter[prg] += 1

    sample_note = f"（以下统计基于前 {len(items)} 条样本）" if total > len(items) else ""
    print(f"  共 {total} 个手动任务节点{sample_note}")

    print(f"\n  按负责人 top 10:")
    for owner, cnt in owner_counter.most_common(10):
        print(f"    {owner:<20} {cnt}")

    print(f"\n  按任务类型 top 10:")
    for prg, cnt in prg_type_counter.most_common(10):
        print(f"    {prg:<20} {cnt}")

    print(f"\n  节点明细（前 10）:")
    print(f"    {'节点名':<35} {'负责人':<15} {'类型'}")
    print(f"    {'─' * 75}")
    for n in items[:10]:
        name = (n.get("nodeName") or "")[:33]
        owner = (n.get("ownerName") or n.get("owner") or "")[:13]
        prg = n.get("prgTypeName") or f"prgType={n.get('prgType')}"
        print(f"    {name:<35} {owner:<15} {prg}")


# ─── 主流程 ──────────────────────────────────────────────────

def dashboard(args):
    client = BFFClient(quiet=True)
    project_id = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)

    today = datetime.now().date()
    if args.date == "today" or not args.date:
        target = today
    elif args.date == "yesterday":
        target = today - timedelta(days=1)
    else:
        target = datetime.strptime(args.date, "%Y-%m-%d").date()
    today_str = target.strftime("%Y-%m-%d")

    my_base_id = None
    if args.mine:
        my_base_id = client.get_my_base_id()

    scope = f"我的 (baseId={my_base_id})" if my_base_id else "全部"
    print(f"{_TAG} 工作空间: {project_id} | 日期: {today_str} | 范围: {scope}")
    print(f"{'=' * 60}")

    # 统计类 API 不支持按 baseId 过滤，即使 --mine 也是全工作空间数据
    stats_note = "（全工作空间统计，不按 --mine 过滤）" if my_base_id else ""

    # 1. 状态分布
    print(f"\n📊 今日手动任务状态分布 {stats_note}")
    status_dist = _section_status_dist(client, project_id, today_str)
    _print_status_dist(status_dist)

    # 2. 执行趋势
    print(f"\n📈 执行趋势 {stats_note}")
    outer, inner = _section_trend(client, project_id, today_str)
    _print_trend(outer, inner)

    # 3. 失败排行
    print(f"\n🔴 失败排行 {stats_note}")
    err_outer, err_inner = _section_error_rank(client, project_id, today_str)
    _print_error_rank(err_outer, err_inner)

    # 4. 节点分组
    print(f"\n📋 节点分组 {stats_note}")
    node_group = _section_node_group(client, project_id)
    _print_node_group(node_group)

    # 5. 手动任务节点（定义）
    node_scope = "我的" if my_base_id else "全部"
    print(f"\n📦 手动任务节点（定义，nodeType=1 不走日常调度 | {node_scope}）")
    nodes, node_total = _section_manual_nodes(client, project_id, owner=my_base_id)
    _print_manual_nodes(nodes, node_total)

    # 6. 手动实例列表
    inst_scope = "我创建的" if my_base_id else "全部"
    print(f"\n📋 今日手动实例列表（已运行的 DAG | {inst_scope}）")
    instances = _section_instance_list(client, project_id, today_str, create_user=my_base_id)
    failed_dag_ids = _print_instance_list(instances, project_id)

    # 下一步
    print(f"\n{'─' * 60}")
    print(f"下一步")
    print(f"{'─' * 60}")
    idx = 1
    if failed_dag_ids:
        dag_ids_str = json.dumps(failed_dag_ids[:5])
        print(f"  {idx}. 重跑失败的手动工作流:")
        print(f"     → rerunDag API: dagIds={dag_ids_str}, statusList=[5], projectId={project_id}, env=prod, tenantId=1")
        idx += 1
    if node_total > 0:
        print(f"  {idx}. 触发某个手动任务运行（需要 flowId）:")
        print(f"     → manualRunNode API: flowId=<来自节点明细>, name=<运行名称>, multipleTimePeriods=[{{bizBeginTime, bizEndTime}}], projectId={project_id}, env=prod, tenantId=1")
        idx += 1
    print(f"  {idx}. 查看周期实例运维大屏: ops_overview.py --project-id {project_id}")
    idx += 1
    print(f"  {idx}. 查看失败实例详情: query_instances.py --project-id {project_id} --status failed")

    save_tool_result("manual_biz_overview", {
        "status": "ok",
        "project_id": project_id,
        "date": today_str,
        "manual_node_total": node_total,
        "failed_dag_ids": failed_dag_ids,
    })


# ─── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="手动任务概览")
    parser.add_argument("--project-id", type=int, help="工作空间 ID")
    parser.add_argument("--project-name", help="工作空间名称")
    parser.add_argument("--date", default="today",
                        help="日期: today(默认)/yesterday/YYYY-MM-DD")
    parser.add_argument("--mine", action="store_true",
                        help="只看我的手动任务节点（按 owner 过滤）")
    args = parser.parse_args()

    telemetry_start("manual_biz_overview.py", module="task-ops", project_id=args.project_id, project_name=args.project_name, date=args.date)

    if not args.project_id and not args.project_name:
        telemetry_start("manual_biz_overview.py", module="task-ops")
        from bff_client import list_workspaces_for_selection
        list_workspaces_for_selection("manual_biz_overview.py")
        telemetry_end(exit_code=0, result={"action": "list_workspaces"})
        return

    dashboard(args)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("manual_biz_overview.py", "task-ops", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("manual_biz_overview.py", "task-ops", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
