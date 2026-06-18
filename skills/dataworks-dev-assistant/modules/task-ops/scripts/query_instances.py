#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务实例查询工具 —— 运维看板多维筛选

用法:
    # 查昨天失败的任务（默认）
    python query_instances.py --project-name autotest --status failed

    # 查昨天失败的 ODPS SQL 任务
    python query_instances.py --project-id 14255 --status failed --type ODPS_SQL

    # 查未完成的任务
    python query_instances.py --project-id 14255 --status unfinished

    # 查我的失败任务
    python query_instances.py --project-id 14255 --status failed --owner me

    # 按节点名搜索
    python query_instances.py --project-id 14255 --search my_node
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from bff_client import BFFClient, save_tool_result, resolve_project_id
from telemetry import telemetry_start, telemetry_end, telemetry_fail
from workspace_memory import get_known_issues, record_known_issue, save_next_check


# ─── 常量 ──────────────────────────────────────────────────────

_TAG = "[instances]"

_STATUS_MAP = {
    "failed":     "5",
    "success":    "6",
    "running":    "4",
    "unfinished": "0,1,2,3,4",
}

_STATUS_NAMES = {
    "0": "未运行", "1": "等待调度", "2": "等待中",
    "3": "等待资源", "4": "运行中", "5": "失败",
    "6": "成功", "7": "暂停",
}


# ─── 内部 API 调用 ────────────────────────────────────────────

def _api_call(client, api_name, **kwargs):
    """直接调用 API（绕过写操作检查，用于已确认的内部步骤）"""
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


# ─── 参数解析 ────────────────────────────────────────────────

def _resolve_status(status_str):
    if not status_str:
        return ""
    key = status_str.strip().lower()
    return _STATUS_MAP.get(key, status_str)


def _calc_date_params(date_str):
    """将 --date 转为 bizdate / bizBeginHour / bizEndHour

    --date 的语义是业务日期（和运维看板一致）。
    调度实例在业务日期的次日执行，所以 bizBeginHour/bizEndHour = bizdate + 1 天。
    """
    today = datetime.now().date()

    if date_str == "yesterday" or not date_str:
        biz_date = today - timedelta(days=1)
    elif date_str == "today":
        biz_date = today
    else:
        biz_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    run_date = biz_date + timedelta(days=1)

    return {
        "bizdate": f"{biz_date.strftime('%Y-%m-%d')} 00:00:00",
        "bizBeginHour": f"{run_date.strftime('%Y-%m-%d')} 00:00:00",
        "bizEndHour": f"{run_date.strftime('%Y-%m-%d')} 23:59:59",
    }


def _resolve_task_type(client, project_id, type_name):
    """将任务类型名（如 ODPS_SQL）映射为 prgTypes 数字"""
    if not type_name:
        return ""
    if type_name.strip().isdigit():
        return type_name.strip()

    types = _api_call(client, "listNodeTypes_v2",
                      projectId=project_id, env="prod", tenantId=1)
    if not isinstance(types, list):
        types = [types] if types else []

    normalized = type_name.strip().upper().replace(" ", "_").replace("-", "_")

    # 精确匹配
    for t in types:
        name = (t.get("name") or "").upper()
        if name == normalized:
            type_id = str(t.get("id", ""))
            print(f"{_TAG} 任务类型: {type_name} → prgTypes={type_id}")
            return type_id

    # 模糊匹配（包含关系）
    candidates = []
    for t in types:
        name = (t.get("name") or "").upper()
        if normalized in name or name in normalized:
            candidates.append(t)

    if len(candidates) == 1:
        c = candidates[0]
        type_id = str(c.get("id", ""))
        print(f"{_TAG} 任务类型: {type_name} → prgTypes={type_id} ({c.get('name')})")
        return type_id

    # 匹配失败
    names = sorted(set(t.get("name", "") for t in types if t.get("name") and t.get("display")))
    print(f"{_TAG} 未找到任务类型: {type_name}")
    print(f"{_TAG} 可用类型: {', '.join(names[:30])}")
    sys.exit(1)


def _resolve_resource_group(client, project_id, group_name):
    """将资源组名称映射为 resgroupId"""
    if not group_name:
        return ""
    groups = _api_call(client, "listResourceGroups",
                       projectId=project_id, modules=["SCHEDULER"],
                       sortBy="RESOURCE_GROUP_NAME", order="ASC")
    if not isinstance(groups, list):
        groups = [groups] if groups else []

    for g in groups:
        name = g.get("name") or g.get("resourceGroupName") or ""
        identifier = g.get("resourceGroupIdentifier") or ""
        gid = str(g.get("id") or g.get("resourceGroupId") or "")
        if group_name in (name, identifier, gid):
            print(f"{_TAG} 资源组: {group_name} → resgroupId={gid}")
            return gid

    names = [g.get("name") or g.get("resourceGroupName") or "" for g in groups]
    print(f"{_TAG} 未找到资源组: {group_name}")
    print(f"{_TAG} 可用资源组: {', '.join(names)}")
    sys.exit(1)


def _resolve_owner(client, owner_str):
    if not owner_str:
        return ""
    if owner_str.strip().lower() == "me":
        base_id = client.get_my_base_id()
        print(f"{_TAG} 负责人: me → {base_id}")
        return str(base_id)
    return owner_str


# ─── 输出格式化 ──────────────────────────────────────────────

def _print_summary(args, date_params, project_id):
    parts = [f"projectId={project_id}"]
    if args.status:
        parts.append(f"status={args.status}")
    parts.append(f"bizdate={date_params['bizdate'][:10]}")
    if args.task_type:
        parts.append(f"type={args.task_type}")
    if args.search:
        parts.append(f"search={args.search}")
    if args.owner:
        parts.append(f"owner={args.owner}")
    print(f"{_TAG} 查询: {', '.join(parts)}")


def _fmt_duration(item):
    """从实例数据中提取并格式化耗时"""
    # 优先用 duration 字段，其次用 modifyTime - createTime 推算
    dur = item.get("duration")
    if dur and isinstance(dur, (int, float)) and dur > 0:
        secs = dur
    else:
        create = item.get("createTimeLong") or item.get("createTime")
        modify = item.get("modifyTimeLong") or item.get("modifyTime")
        if create and modify and isinstance(create, (int, float)) and isinstance(modify, (int, float)):
            diff = abs(modify - create)
            secs = diff / 1000 if diff > 100000 else diff  # 毫秒 or 秒
        else:
            return "-"
    if secs <= 0:
        return "-"
    if secs >= 3600:
        return f"{secs / 3600:.1f}h"
    if secs >= 60:
        return f"{secs / 60:.1f}m"
    return f"{int(secs)}s"


def _print_table(items):
    print(f"{_TAG} 共 {len(items)} 个实例:\n")
    # 表头 — instanceId=实例ID（查日志用），nodeId=节点定义ID（查代码/重跑用）
    print(f"  {'节点名':<30} {'状态':<8} {'耗时':<8} {'instanceId':<20} {'nodeId':<16} {'业务日期':<12} {'负责人':<10}")
    print(f"  {'─' * 30} {'─' * 8} {'─' * 8} {'─' * 20} {'─' * 16} {'─' * 12} {'─' * 10}")
    for item in items:
        node_name = (item.get("nodeName") or "")[:30]
        status_code = str(item.get("status", ""))
        status = _STATUS_NAMES.get(status_code, item.get("statusName", status_code))
        duration = _fmt_duration(item)
        instance_id = str(item.get("taskId", ""))
        node_id = str(item.get("nodeId", ""))
        raw_bizdate = item.get("bizdate") or ""
        if isinstance(raw_bizdate, (int, float)):
            bizdate = datetime.fromtimestamp(raw_bizdate / 1000).strftime("%Y-%m-%d")
        else:
            bizdate = str(raw_bizdate)[:10]
        owner = item.get("ownerName") or item.get("owner") or ""
        print(f"  {node_name:<30} {status:<8} {duration:<8} {instance_id:<20} {node_id:<16} {bizdate:<12} {owner:<10}")


def _print_fail_groups(failed, project_id):
    """按负责人和任务类型分组展示失败实例，输出每组的批量重跑命令"""
    if len(failed) < 3:
        return  # 少于 3 个不值得分组

    # ── 按 owner 分组 ──
    by_owner = {}
    for i in failed:
        o = i.get("ownerName") or i.get("owner") or "未知"
        by_owner.setdefault(o, []).append(i)

    if len(by_owner) > 1:
        print(f"\n  📋 按负责人分组:")
        for owner, group in sorted(by_owner.items(), key=lambda x: -len(x[1])):
            node_ids = [str(i.get("nodeId", i.get("taskId"))) for i in group]
            names = [i.get("nodeName", "")[:20] for i in group[:3]]
            names_str = ", ".join(names)
            if len(group) > 3:
                names_str += f" 等{len(group)}个"
            print(f"     {owner} ({len(group)}个): {names_str}")
            print(f"       → rerun_task_instances --env prod --projectId {project_id} --taskIds '{json.dumps(node_ids)}'")

    # ── 按任务类型分组（如果有 prgType 字段） ──
    by_type = {}
    for i in failed:
        t = i.get("prgTypeName") or i.get("prgType") or ""
        if t:
            by_type.setdefault(str(t), []).append(i)

    if len(by_type) > 1:
        print(f"\n  📋 按任务类型分组:")
        for type_name, group in sorted(by_type.items(), key=lambda x: -len(x[1])):
            print(f"     {type_name}: {len(group)} 个失败")


def _print_assessment(items, project_id, date_params, known_issues=None, client=None):
    """状态判断 + 关键发现 + 建议动作"""
    failed = [i for i in items if str(i.get("status")) == "5"]
    running = [i for i in items if str(i.get("status")) == "4"]
    waiting = [i for i in items if str(i.get("status")) in ("0", "1", "2", "3")]

    # ── 失败分组（在判断之前输出，给 agent 结构化的分组视图） ──
    if failed:
        _print_fail_groups(failed, project_id)

    # ── 已知问题匹配 ──
    known_ids = {}
    if known_issues:
        for issue in known_issues:
            nid = str(issue.get("node_id", ""))
            if nid:
                known_ids[nid] = issue

    # ── 按 owner 聚合失败 ──
    owner_fail = {}
    for i in failed:
        o = i.get("ownerName") or i.get("owner") or "未知"
        owner_fail[o] = owner_fail.get(o, 0) + 1

    # ── 严重度 ──
    if len(failed) >= 10:
        severity = "🔴 严重"
    elif len(failed) >= 3:
        severity = "🟡 注意"
    elif failed:
        severity = "🟡 注意"
    else:
        severity = "🟢 正常"

    # ── 汇总 ──
    parts = [f"共 {len(items)} 个实例"]
    if failed:
        parts.append(f"{len(failed)} 个失败")
    if running:
        parts.append(f"{len(running)} 个运行中")
    if waiting:
        parts.append(f"{len(waiting)} 个等待中")

    print(f"\n{'=' * 60}")
    print(f"【状态判断】{severity}：{'，'.join(parts)}")

    # ── 关键发现 ──
    findings = []
    if len(owner_fail) > 1 and failed:
        top_owner = max(owner_fail, key=owner_fail.get)
        findings.append(
            f"失败分布在 {len(owner_fail)} 个负责人，"
            f"{top_owner} 最多（{owner_fail[top_owner]} 个），建议按上方分组处理"
        )
    elif len(owner_fail) == 1 and failed:
        top_owner = list(owner_fail.keys())[0]
        if owner_fail[top_owner] >= 2:
            findings.append(f"全部 {owner_fail[top_owner]} 个失败都属于 {top_owner}")
    if len(failed) >= 10:
        findings.append(f"失败数量较多（{len(failed)}），可能存在批量性问题（资源组/上游依赖）")

    # ── 标记已知问题 ──
    if known_ids and failed:
        known_matched = []
        new_failures = []
        for i in failed:
            node_id = str(i.get("nodeId", i.get("taskId", "")))
            node_name = i.get("nodeName", "")
            if node_id in known_ids:
                issue = known_ids[node_id]
                known_matched.append(f"{node_name}（已知问题: {issue.get('pattern', '?')}，出现 {issue.get('seen_count', '?')} 次）")
            else:
                new_failures.append(node_name)
        if known_matched:
            findings.append(f"已知问题节点: {', '.join(known_matched[:3])}")
        if new_failures and known_matched:
            findings.append(f"新增失败节点（非已知问题）: {len(new_failures)} 个")

    if findings:
        print("【关键发现】")
        for f in findings:
            print(f"  - {f}")

    # ── 建议动作 ──
    # instanceId = taskId（API 返回的 taskId 实际是实例 ID，用于查日志）
    # nodeId = 节点定义 ID（用于查代码、重跑、查详情）
    actions = []
    try:
        from node_profile import get_profile
        np = get_profile()
    except Exception:
        np = None

    if failed:
        first = failed[0]
        inst_id = first.get("taskId", "")
        node_id = first.get("nodeId", "")
        name = first.get("nodeName", "")
        # 从 node_profile 查找 entity_id 和 output_table
        profile = np.lookup(project_id, task_id=int(node_id)) if np and node_id else None

        log_cmd = f"log_analyzer.py --task-instance-id {inst_id}"
        if node_id:
            log_cmd += f" --node-id {node_id} --project-id {project_id}"
        actions.append((f"查看失败日志 ({name})", log_cmd))
        if node_id:
            actions.append((f"查看运行态代码 ({name})",
                            f"find_node_code.py --project-id {project_id} --task-id {node_id} --runtime"))
        if profile and profile.get("entity_id"):
            actions.append((f"查看开发态代码 ({name})",
                            f"find_node_code.py --project-id {project_id} --entity-id {profile['entity_id']}"))
        if profile and profile.get("output_table"):
            actions.append((f"查看产出表 ({profile['output_table']})",
                            f"search_table.py \"{profile['output_table']}\""))
        if len(failed) > 1:
            node_ids = [str(i.get("nodeId", i.get("taskId"))) for i in failed]
            actions.append((f"批量重跑全部 {len(failed)} 个失败实例",
                            f"rerun_task_instances --env prod --projectId {project_id} --taskIds '{json.dumps(node_ids)}'"))
    else:
        first = items[0]
        inst_id = first.get("taskId", "")
        actions.append(("查看实例详情",
                        f"get_task_instance --taskInstanceId {inst_id}"))

    print("【建议动作】")
    for i, (desc, cmd) in enumerate(actions, 1):
        print(f"  {i}. {desc}")
        print(f"     → {cmd}")


def _print_empty(args):
    print(f"{_TAG} 无匹配实例")
    hints = []
    if args.status:
        hints.append("去掉 --status 查看所有状态")
    if args.task_type:
        hints.append("去掉 --type 查看所有类型")
    if args.search:
        hints.append("检查 --search 关键词")
    if hints:
        print(f"{_TAG} 建议: {'; '.join(hints)}")


# ─── 主流程 ──────────────────────────────────────────────────

_STATUS_LABEL = {"1": "未运行", "2": "等待中", "3": "准备中", "4": "运行中",
                 "5": "失败", "6": "成功", "7": "暂停"}


def _fetch_all_instances(client, common_params, project_id, page_size=200):
    """全量翻页拉取实例（用于 --group-by 准确统计）。getInstanceList 实测分页真实可信，totalCount 准确"""
    all_items = []
    total = None
    for pn in range(1, 200):  # safety cap 200 pages × 200 = 40000
        items = _api_call(client, "getInstanceList",
                          pageNum=pn, pageSize=page_size, **common_params)
        if items is None:
            break
        if not isinstance(items, list):
            items = [items] if items else []
        if not items:
            break
        all_items.extend(items)
        if len(items) < page_size:
            break
        if pn % 10 == 0:
            print(f"  已翻 {pn} 页，累加 {len(all_items)} 个实例 ...", file=sys.stderr)
    return all_items


def _print_instances_group_by(items, dim):
    from collections import Counter
    counter = Counter()
    label_map = {}
    for it in items:
        if dim == "status":
            key = str(it.get("status") or "")
            label = _STATUS_LABEL.get(key, key)
        elif dim == "owner":
            key = str(it.get("owner") or "")
            label = it.get("ownerName") or key
        else:  # task_type
            key = str(it.get("prgType") or "")
            label = it.get("prgTypeName") or it.get("prgType") or key
        if not key:
            continue
        counter[key] += 1
        if label and key not in label_map:
            label_map[key] = label
    total = sum(counter.values())
    role = {"status": "实例状态", "owner": "负责人", "task_type": "任务类型"}[dim]
    print(f"\n共 {total} 个实例 — 按 {role} 分布：\n")
    width = max((len(str(label_map.get(k, k))) for k in counter), default=4)
    print(f"  {'排名':<4} {'名称'.ljust(width)}  {'主键':<10} {'数量':>6} {'占比':>7}")
    for i, (k, cnt) in enumerate(counter.most_common(), 1):
        pct = cnt * 100.0 / total
        print(f"  {i:<4} {str(label_map.get(k, k)).ljust(width)}  {k[:10]:<10} {cnt:>6} {pct:>6.1f}%")
    print(f"\n  合计: {total}")


def query_instances(args):
    client = BFFClient(quiet=True)

    project_id = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)
    telemetry_start("query_instances.py", module="task-ops",
                    project_id=project_id, date=args.date, status=args.status)
    task_statuses = _resolve_status(args.status)
    prg_types = _resolve_task_type(client, project_id, args.task_type) if args.task_type else ""
    resgroup_id = _resolve_resource_group(client, project_id, args.resource_group) if args.resource_group else ""
    owner = _resolve_owner(client, args.owner)
    date_params = _calc_date_params(args.date)

    _print_summary(args, date_params, project_id)

    # 公共参数（用于 _api_call / 全量翻页）
    common_kwargs = dict(
        projectId=project_id, env="prod", tenantId=1, dagType=0, taskTypes=0,
        includeRelation="false", withAlarm="false", slowly="false", withRerun="false",
        taskStatuses=task_statuses, prgTypes=prg_types, searchText=args.search or "",
        owner=owner, resgroupId=resgroup_id,
        sortOrder="", sortField="", alarmTime="", solId="", nodeTag="", bizId="",
        connectionRegionId="", connectionType="", connections="", baseLineId="",
        priorityList="", scheIntervalList="", diResGroupIdentifier="",
        diSrcType="", diSrcDatasource="", diDstType="", diDstDatasource="",
        flowId="", alarmId="", advanceSort="", **date_params,
    )

    # group-by 全量翻页 → 按维度聚合（getInstanceList 实测分页可信）
    if getattr(args, "group_by", None):
        print(f"⏳ 全量翻页拉取实例做 {args.group_by} 分布统计 ...", file=sys.stderr)
        items = _fetch_all_instances(client, common_kwargs, project_id)
        if not items:
            print("无数据")
            return
        _print_instances_group_by(items, args.group_by)
        telemetry_end(result={"mode": "group-by", "by": args.group_by, "count": len(items)})
        save_tool_result("query_instances", {
            "mode": "group-by", "by": args.group_by, "count": len(items),
            "project_id": project_id,
        })
        return

    # 调用 API（空参数传空字符串，和运维看板一致）
    items = _api_call(client, "getInstanceList",
                      projectId=project_id,
                      env="prod",
                      tenantId=1,
                      dagType=0,
                      taskTypes=0,
                      includeRelation="false",
                      withAlarm="false",
                      slowly="false",
                      withRerun="false",
                      taskStatuses=task_statuses,
                      prgTypes=prg_types,
                      searchText=args.search or "",
                      owner=owner,
                      resgroupId=resgroup_id,
                      sortOrder="",
                      sortField="",
                      alarmTime="",
                      solId="",
                      nodeTag="",
                      bizId="",
                      connectionRegionId="",
                      connectionType="",
                      connections="",
                      baseLineId="",
                      priorityList="",
                      scheIntervalList="",
                      diResGroupIdentifier="",
                      diSrcType="",
                      diSrcDatasource="",
                      diDstType="",
                      diDstDatasource="",
                      flowId="",
                      alarmId="",
                      advanceSort="",
                      pageNum=1,
                      pageSize=args.page_size,
                      **date_params)

    if not isinstance(items, list):
        items = [items] if items else []

    if not items:
        _print_empty(args)
        telemetry_end(result={"count": 0})
        save_tool_result("query_instances", {"status": "empty", "project_id": project_id})
        return

    _print_table(items)

    # 写入 node_profile（零额外 API 调用，从实例列表提取 nodeId/nodeName/owner）
    try:
        from node_profile import get_profile
        np = get_profile()
        if np:
            seen = set()
            rows = []
            for item in items:
                nid = item.get("nodeId")
                if nid and nid not in seen:
                    seen.add(nid)
                    rows.append({
                        "task_id": int(nid),
                        "node_name": item.get("nodeName"),
                        "owner": item.get("ownerName") or item.get("owner"),
                    })
            if rows:
                np.bulk_upsert(project_id, rows)
    except Exception:
        pass

    # 加载已知问题（跨会话记忆）
    known_issues = get_known_issues(project_id)
    _print_assessment(items, project_id, date_params, known_issues=known_issues,
                      client=client)

    # 记录失败节点为已知问题（连续失败模式）
    failed_items = [i for i in items if str(i.get("status")) == "5"]
    for item in failed_items:
        node_id = str(item.get("nodeId", item.get("taskId", "")))
        node_name = item.get("nodeName", "")
        if node_id and node_name:
            try:
                record_known_issue(project_id, node_id, node_name,
                                   pattern="实例失败")
            except Exception:
                pass  # 记忆写入失败不影响主流程

    # 有失败实例时保存待跟进事项，供下次会话开始检查
    if failed_items:
        try:
            save_next_check(
                project_id,
                f"有 {len(failed_items)} 个失败实例待处理",
                f"query_instances.py --project-id {project_id} --status failed")
        except Exception:
            pass

    telemetry_end(result={"count": len(items), "failed_count": len(failed_items)})

    save_tool_result("query_instances", {
        "status": "ok",
        "count": len(items),
        "failed_count": len(failed_items),
        "project_id": project_id,
    })


# ─── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="查询任务实例（运维看板）")
    parser.add_argument("--project-id", type=int, help="工作空间 ID")
    parser.add_argument("--project-name", help="工作空间名称")
    parser.add_argument("--project", help="canonical：工作空间（纯数字=id，否则=name）")
    parser.add_argument("--status", help="failed/success/running/unfinished 或数字")
    parser.add_argument("--date", default=None,
                        help="业务日期: yesterday(默认)/today/YYYY-MM-DD")
    parser.add_argument("--business-date", dest="business_date",
                        help="canonical：等价于 --date")
    parser.add_argument("--type", dest="task_type",
                        help="任务类型名称（如 ODPS_SQL）或数字")
    parser.add_argument("--search", help="按节点名/ID 搜索")
    parser.add_argument("--owner", help="负责人（'me'=当前用户）")
    parser.add_argument("--mine", action="store_true",
                        help="只看我的实例（等价于 --owner me，与 ops_overview.py 参数保持一致）")
    parser.add_argument("--resource-group", help="调度资源组名称")
    parser.add_argument("--page-size", type=int, default=40, help="每页条数")
    parser.add_argument("--group-by", choices=["status", "owner", "task_type"],
                        help="聚合分布：按 status / owner / task_type 统计实例数（自动全量翻页，准确）")
    args = parser.parse_args()

    # ── canonical 参数归一（与 ops_overview 对齐）──
    if args.project and not args.project_id and not args.project_name:
        if args.project.isdigit():
            args.project_id = int(args.project)
        else:
            args.project_name = args.project
    if args.business_date and args.date is None:
        args.date = args.business_date
    if args.date is None:
        args.date = "yesterday"

    # --mine：自动注入当前用户 baseId（与 ops_overview.py 一致；不传 'me' 字面量走默认 owner resolver）
    if args.mine and not args.owner:
        from bff_client import get_client
        args.owner = str(get_client().get_my_base_id() or "")

    if not args.project_id and not args.project_name:
        telemetry_start("query_instances.py", module="task-ops")
        from bff_client import list_workspaces_for_selection
        list_workspaces_for_selection("query_instances.py")
        telemetry_end(exit_code=0, result={"action": "list_workspaces"})
        return

    query_instances(args)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("query_instances.py", "task-ops", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("query_instances.py", "task-ops", 1, error=str(e)[:100])
        print(f"\n[error] {e}")
        print(f"  如需上报此问题: report_bug.py \"{e}\" --script query_instances.py")
        sys.exit(1)
