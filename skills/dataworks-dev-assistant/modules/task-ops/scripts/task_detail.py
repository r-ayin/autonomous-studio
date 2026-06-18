#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行态任务详情 —— 查看任务的调度配置、实例列表、上下游依赖、操作日志

用法:
    python task_detail.py --project-id 14255 --node-id 308437862
    python task_detail.py --project-name autotest --node-id 308437862
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

from bff_client import BFFClient, save_tool_result, resolve_project_id
from telemetry import telemetry_start, telemetry_end, telemetry_fail


# ─── 常量 ──────────────────────────────────────────────────────

_TAG = "[task]"


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

def _fmt(n):
    if n is None:
        return "-"
    return str(n)


def _fmt_ts(ts):
    """毫秒时间戳转日期字符串"""
    if not ts or not isinstance(ts, (int, float)):
        return str(ts) if ts else "-"
    try:
        return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError):
        return str(ts)


# ─── 1. 任务详情 ─────────────────────────────────────────────

def _section_node_detail(client, project_id, node_id):
    """运行态任务详情"""
    data = _safe_call(client, "getNodeDetail",
                      projectId=project_id, env="prod", tenantId=1,
                      nodeId=node_id)
    if not data or not isinstance(data, dict):
        print(f"  (无数据)")
        return data, None, None

    name = data.get("nodeName", data.get("name", ""))
    owner = data.get("ownerName", data.get("owner", ""))
    node_type = data.get("prgType", data.get("nodeType", data.get("type", "")))
    cron = data.get("cronExpress", data.get("cron", ""))
    status = data.get("status", data.get("statusName", ""))
    create_time = _fmt_ts(data.get("createTime", data.get("gmtCreate")))
    modify_time = _fmt_ts(data.get("modifyTime", data.get("gmtModified")))
    desc = data.get("description", data.get("desc", ""))

    # 提取产出表名
    outputs = data.get("outputs") or []
    ref_tables = [o.get("refTableName") for o in outputs
                  if isinstance(o, dict) and o.get("refTableName")]
    primary_table = min(set(ref_tables), key=len) if ref_tables else ""

    print(f"  节点名: {name}")
    print(f"  nodeId: {node_id}")
    print(f"  负责人: {owner}")
    print(f"  类型: {node_type}")
    if primary_table:
        print(f"  产出表: {primary_table}")
    print(f"  调度: {cron}")
    if status:
        print(f"  状态: {status}")
    if desc:
        print(f"  描述: {desc}")
    print(f"  创建: {create_time}  修改: {modify_time}")

    # resolve：写入 output_table + 补全 entity_id（一次调用搞定）
    entity_id = None
    try:
        from node_profile import resolve, get_profile
        # 先写入本次已知的 output_table（resolve 内部的 getNodeDetail 会重复调，
        # 所以先手动 upsert 省一次 API）
        np = get_profile()
        if np:
            np.upsert(project_id, task_id=int(node_id),
                       node_name=name or None, owner=owner or None,
                       node_type=str(data.get("prgTypeName", "")) or None,
                       output_table=primary_table or None)
        # resolve 补全 entity_id（缓存命中就不调 API）
        profile = resolve(project_id, client, task_id=int(node_id))
        if profile and profile.get("entity_id"):
            entity_id = profile["entity_id"]
            print(f"  entityId: {entity_id}")
    except Exception:
        pass

    return data, entity_id, primary_table


# ─── 2. 最近实例 ─────────────────────────────────────────────

_STATUS_NAMES = {
    "0": "未运行", "1": "等待调度", "2": "等待中",
    "3": "等待资源", "4": "运行中", "5": "失败",
    "6": "成功", "7": "暂停",
}


def _section_instances(client, project_id, node_id):
    """最近周期实例，返回实例列表"""
    data = _safe_call(client, "getInstanceList",
                      projectId=project_id, env="prod", tenantId=1,
                      dagType=0, taskTypes="", taskStatuses="",
                      searchText=str(node_id),
                      includeRelation="false",
                      withAlarm="false", slowly="false", withRerun="false",
                      prgTypes="", owner="", resgroupId="",
                      sortOrder="", sortField="",
                      alarmTime="", solId="", nodeTag="", bizId="",
                      connectionRegionId="", connectionType="", connections="",
                      baseLineId="", priorityList="", scheIntervalList="",
                      diResGroupIdentifier="", diSrcType="", diSrcDatasource="",
                      diDstType="", diDstDatasource="",
                      flowId="", alarmId="", advanceSort="",
                      pageNum=1, pageSize=10)
    if not data:
        print(f"  (无实例)")
        return []
    items = data if isinstance(data, list) else [data]
    if not items:
        print(f"  (无实例)")
        return []

    print(f"  {'业务日期':<12} {'状态':<8} {'taskId':<20}")
    print(f"  {'─' * 12} {'─' * 8} {'─' * 20}")
    for item in items[:10]:
        raw_biz = item.get("bizdate", "")
        if isinstance(raw_biz, (int, float)):
            bizdate = datetime.fromtimestamp(raw_biz / 1000).strftime("%Y-%m-%d")
        else:
            bizdate = str(raw_biz)[:10]
        status_code = str(item.get("status", ""))
        status = _STATUS_NAMES.get(status_code, item.get("statusName", status_code))
        task_id = str(item.get("taskId", ""))
        print(f"  {bizdate:<12} {status:<8} {task_id:<20}")
    return items


# ─── 2.5 补数据实例 ──────────────────────────────────────────

def _section_backfill_instances(client, project_id, node_id):
    """补数据实例（dagType=3）：先查 DAG 列表，再查最近一次 DAG 的实例"""
    # 第一层：查该节点的补数据 DAG 列表
    data = _safe_call(client, "getDagByLayer",
                      projectId=project_id, env="prod", tenantId=1,
                      searchText=str(node_id), dagType=3, layer="first",
                      sortField="bizdate", sortOrder="desc",
                      pageNum=1, pageSize=10,
                      createTime="", createDagBeginTime="",
                      createDagEndTime="", bizdate="")
    if not data:
        print(f"  (无补数据记录)")
        return

    items = data if isinstance(data, list) else data.get("list", data.get("data", []))
    if not isinstance(items, list) or not items:
        print(f"  (无补数据记录)")
        return

    print(f"  最近 {min(len(items), 5)} 次补数据:")
    print(f"  {'名称':<25} {'状态':<8} {'创建时间':<20}")
    print(f"  {'─' * 25} {'─' * 8} {'─' * 20}")
    for item in items[:5]:
        name = item.get("name", item.get("dagName", ""))[:25]
        status = item.get("statusName", item.get("status", ""))
        create = _fmt_ts(item.get("createTime", item.get("gmtCreate")))
        print(f"  {name:<25} {status:<8} {create}")

    # 第二层：查最近一次补数据 DAG 的实例列表
    latest_dag = items[0]
    op_seq = latest_dag.get("opSeq", latest_dag.get("dagId", latest_dag.get("id")))
    if not op_seq:
        return

    print(f"\n  最近一次补数据（opSeq={op_seq}）的实例:")
    detail = _safe_call(client, "getDagByLayer",
                        projectId=project_id, env="prod", tenantId=1,
                        dagType=3, layer="second", opSeq=str(op_seq),
                        sortField="bizdate", sortOrder="desc",
                        pageNum=1, pageSize=20,
                        createTime="", createDagBeginTime="",
                        createDagEndTime="", bizdate="")
    if not detail:
        print(f"  (无实例)")
        return

    sub_items = detail if isinstance(detail, list) else detail.get("list", detail.get("data", []))
    if not isinstance(sub_items, list) or not sub_items:
        print(f"  (无实例)")
        return

    print(f"  {'节点名':<25} {'状态':<8} {'业务日期':<12}")
    print(f"  {'─' * 25} {'─' * 8} {'─' * 12}")
    for item in sub_items[:10]:
        name = item.get("nodeName", item.get("name", ""))[:25]
        status_code = str(item.get("status", ""))
        status = _STATUS_NAMES.get(status_code, item.get("statusName", status_code))
        raw_biz = item.get("bizdate", "")
        if isinstance(raw_biz, (int, float)):
            bizdate = datetime.fromtimestamp(raw_biz / 1000).strftime("%Y-%m-%d")
        else:
            bizdate = str(raw_biz)[:10]
        print(f"  {name:<25} {status:<8} {bizdate}")


# ─── 3. 上下游依赖 ──────────────────────────────────────────

def _section_dependencies(client, project_id, node_id, relation):
    """上游或下游依赖，返回节点列表"""
    data = _safe_call(client, "getNodeListByDepth",
                      projectId=project_id, env="prod", tenantId=1,
                      nodeId=node_id, depth=6, relation=relation)
    if not data:
        print(f"  (无{('上游' if relation == 'parent' else '下游')}依赖)")
        return []

    # data 可能是 dict 或 list
    nodes = []
    if isinstance(data, list):
        nodes = data
    elif isinstance(data, dict):
        nodes = data.get("nodes", data.get("list", data.get("data", [])))
        if not isinstance(nodes, list):
            # 可能是树结构，直接输出概要
            print(f"  {json.dumps(data, ensure_ascii=False, default=str)[:500]}")
            return []

    if not nodes:
        print(f"  (无{('上游' if relation == 'parent' else '下游')}依赖)")
        return []

    label = "上游" if relation == "parent" else "下游"
    for node in nodes[:15]:
        name = node.get("nodeName", node.get("name", ""))[:30]
        nid = node.get("nodeId", node.get("id", ""))
        owner = node.get("ownerName", node.get("owner", ""))
        print(f"  {name:<30} nodeId={nid}  {owner}")
    return nodes


# ─── 4. 操作日志 ────────────────────────────────────────────

def _section_op_logs(client, project_id, node_id):
    """操作日志"""
    data = _safe_call(client, "listOpLogs",
                      projectId=project_id, env="prod", tenantId=1,
                      nodeId=node_id, projectEnv="prod",
                      pageSize=10, pageNumber=1)
    if not data:
        print(f"  (无操作日志)")
        return

    items = data if isinstance(data, list) else data.get("list", data.get("data", []))
    if not isinstance(items, list) or not items:
        print(f"  (无操作日志)")
        return

    for item in items[:10]:
        op_type = item.get("opType", item.get("operationType", item.get("type", "")))
        op_time = _fmt_ts(item.get("opTime", item.get("gmtCreate", item.get("createTime"))))
        operator = item.get("operator", item.get("operatorName", item.get("userName", "")))
        desc = item.get("description", item.get("content", item.get("detail", "")))
        if desc and len(str(desc)) > 60:
            desc = str(desc)[:60] + "..."
        print(f"  {op_time}  {operator:<12} {op_type}  {desc or ''}")


# ─── 状态判断 ────────────────────────────────────────────────

def _print_assessment(node_data, instances, upstream, project_id, node_id,
                      entity_id=None, output_table=None):
    """基于收集的指标输出状态判断 + 关键发现 + 建议动作"""
    findings = []
    actions = []

    # ── 判断维度 1：最近实例是否有失败 ──
    failed = [i for i in instances if str(i.get("status")) == "5"]
    recent_fail_count = len(failed)
    # 连续失败检测（从最新开始连续失败的个数）
    consecutive_fails = 0
    for inst in instances:
        if str(inst.get("status")) == "5":
            consecutive_fails += 1
        else:
            break

    # ── 判断维度 2：依赖是否完整 ──
    has_upstream = len(upstream) > 0 if upstream else False

    # ── 判断维度 3：调度配置是否合理 ──
    cron = ""
    node_name = ""
    if node_data and isinstance(node_data, dict):
        cron = node_data.get("cronExpress", node_data.get("cron", ""))
        node_name = node_data.get("nodeName", node_data.get("name", ""))

    # ── 综合严重度 ──
    if consecutive_fails >= 3:
        severity_emoji = "🔴 严重"
    elif recent_fail_count > 0 or not has_upstream:
        severity_emoji = "🟡 注意"
    else:
        severity_emoji = "🟢 正常"

    # ── 汇总 ──
    parts = []
    if instances:
        parts.append(f"最近 {len(instances)} 个实例")
        if recent_fail_count:
            parts.append(f"{recent_fail_count} 个失败")
        if consecutive_fails >= 2:
            parts.append(f"连续失败 {consecutive_fails} 次")
    else:
        parts.append("无实例数据")
    if not has_upstream:
        parts.append("无上游依赖（根节点）")
    summary = "，".join(parts) if parts else "无异常"

    print(f"\n{'=' * 60}")
    print(f"【状态判断】{severity_emoji}：{summary}")

    # ── 关键发现 ──
    if consecutive_fails >= 2:
        findings.append(f"连续失败 {consecutive_fails} 次，需要立即排查")
    elif recent_fail_count > 0:
        findings.append(f"最近 {len(instances)} 个实例中有 {recent_fail_count} 个失败")
    if not has_upstream:
        findings.append("该任务无上游依赖，为调度链根节点")
    if not cron:
        findings.append("未检测到调度表达式，可能为手动触发任务")

    if findings:
        print("【关键发现】")
        for f in findings:
            print(f"  - {f}")

    # ── 建议动作 ──
    if failed:
        first_fail = failed[0]
        tid = first_fail.get("taskId", "")
        actions.append(("查看失败实例日志",
                        f"log_analyzer.py --task-instance-id {tid} --node-id {node_id} --project-id {project_id}"))
    if recent_fail_count > 1:
        actions.append(("查看该任务所有失败实例",
                        f"query_instances.py --project-id {project_id} --search {node_id} --status failed"))
    actions.append(("查看运行态代码",
                    f"find_node_code.py --project-id {project_id} --task-id {node_id} --runtime"))
    if entity_id:
        actions.append(("查看开发态代码",
                        f"find_node_code.py --project-id {project_id} --entity-id {entity_id}"))
    if output_table:
        actions.append((f"查看产出表 ({output_table})",
                        f"search_table.py \"{output_table}\""))
    if not failed and not recent_fail_count:
        if instances:
            tid = instances[0].get("taskId", "")
            actions.append(("查看最新实例日志",
                            f"log_analyzer.py --task-instance-id {tid} --node-id {node_id} --project-id {project_id}"))

    print("【建议动作】")
    for i, (desc, cmd) in enumerate(actions, 1):
        print(f"  {i}. {desc}")
        print(f"     → {cmd}")


# ─── 主流程 ──────────────────────────────────────────────────

def detail(args):
    client = BFFClient(quiet=True)
    project_id = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)
    node_id = args.node_id
    telemetry_start("task_detail.py", module="task-ops",
                    project_id=project_id, node_id=node_id)

    print(f"{_TAG} 工作空间: {project_id} | 任务 nodeId: {node_id}")
    print(f"{'=' * 60}")

    # 1. 任务详情
    print(f"\n📋 任务详情")
    node_data, entity_id, output_table = _section_node_detail(client, project_id, node_id)

    # 2. 最近实例
    print(f"\n📊 最近周期实例")
    instances = _section_instances(client, project_id, node_id)

    # 2.5 补数据实例
    print(f"\n🔄 补数据实例")
    _section_backfill_instances(client, project_id, node_id)

    # 3. 上游依赖
    print(f"\n⬆️  上游依赖")
    upstream = _section_dependencies(client, project_id, node_id, "parent")

    # 4. 下游依赖
    print(f"\n⬇️  下游依赖")
    _section_dependencies(client, project_id, node_id, "child")

    # 5. 操作日志
    print(f"\n📝 操作日志")
    _section_op_logs(client, project_id, node_id)

    # 状态判断 + 建议动作
    _print_assessment(node_data, instances, upstream, project_id, node_id,
                      entity_id=entity_id, output_table=output_table)

    failed_count = len([i for i in instances if str(i.get("status")) == "5"])
    telemetry_end(result={"instance_count": len(instances), "failed_count": failed_count})

    save_tool_result("task_detail", {
        "status": "ok",
        "project_id": project_id,
        "node_id": node_id,
        "instance_count": len(instances),
        "failed_count": failed_count,
        "upstream_count": len(upstream) if upstream else 0,
    })


# ─── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="运行态任务详情")
    parser.add_argument("--project-id", type=int, help="工作空间 ID")
    parser.add_argument("--project-name", help="工作空间名称")
    parser.add_argument("--node-id", required=True, help="运行态任务 ID (nodeId)")
    args = parser.parse_args()

    if not args.project_id and not args.project_name:
        telemetry_start("task_detail.py", module="task-ops")
        from bff_client import list_workspaces_for_selection
        list_workspaces_for_selection("task_detail.py")
        telemetry_end(exit_code=0, result={"action": "list_workspaces"})
        return

    detail(args)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("task_detail.py", "task-ops", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("task_detail.py", "task-ops", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
