#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
表产出节点搜索工具 —— 从表名出发，定位产出该表的任务/节点

用法:
    python search_nodes.py "表名关键字"
    python search_nodes.py "表名关键字" --with-instances   # 同时查询运行态节点的最新实例
    python search_nodes.py --recent --project-id 30024                              # 最近 24h 变更节点
    python search_nodes.py --recent --project-id 30024 --by create --hours 168      # 最近一周新建节点
    python search_nodes.py --recent --project-id 30024 --my-changes                 # 只看我变更的
    python search_nodes.py --recent --project-id 30024 --by create --group-by owner # 新建节点按创建人分布

功能:
    1. 搜索目标表，获取所属项目
    2. 优先通过表的上游任务 API 定位产出任务/节点
    3. 未命中时回退到节点名搜索
    4. 输出运行态/开发态节点列表（含工作空间、创建时间、最后修改时间、修改人等）
    5. --with-instances: 查询运行态节点在生产/开发环境的最新实例状态
    6. --recent: 扫工作空间最近的**运行态**节点（已发布到调度 PROD/DEV 的 scheduler 节点），
       自动把 scheduler nodeId 解析为 entityId，输出下一步命令（治理检查 / 查代码）。
       ⚠️ 仅覆盖已发布节点，IDE 中未发布的开发态草稿不在统计内

输出示例:
    表: m_task_sql (项目: dataworks_analyze, projectId: 23304)

    运行态节点 (1 个):
      m_task_sql_public (taskId=100, entityId=123456)
        工作空间=Dataworks数据分析, 周期=DAILY
        创建=2026-02-09 20:18, 最后修改=2026-03-25 22:53, 修改人=乾离
        生产环境: 成功 (业务日期=2026-03-26)
        开发环境: 成功 (业务日期=2026-03-26)

    开发态节点 (2 个):
      m_task_sql_public (taskId=100, entityId=123456)
        工作空间=Dataworks数据分析, 负责人=高铁
        创建=2026-02-09 20:18, 最后修改=2026-03-25 22:53, 修改人=乾离
      m_task_sql_new (entityId=345678)
        工作空间=Dataworks数据分析, 负责人=高铁
        创建=2026-03-10 09:00, 最后修改=2026-03-10 09:05, 修改人=高铁
"""

import sys
import argparse
from datetime import datetime, timedelta

from bff_client import BFFClient, save_tool_result
from telemetry import telemetry_start, telemetry_end, telemetry_fail


def _fmt_ts(ts):
    """毫秒时间戳 → 可读日期字符串"""
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OSError):
        return str(ts)

# 实例状态码 → 标签
_INSTANCE_STATUS = {
    "1": "未运行", "2": "等待中", "3": "准备中", "4": "运行中",
    "5": "失败", "6": "成功", "7": "暂停",
}


def search_table(client, keyword, project=None):
    """搜索表，返回精确匹配。非精确匹配或找不到时返回 None（走节点名 fallback）。"""
    from search_table import find_table
    try:
        table = find_table(client, keyword, project=project)
        # find_table 在无精确匹配时会返回第一个模糊结果
        # 这里检查表名是否真的精确匹配，不精确则走 fallback
        table_name = (table.get("name") or "").lower()
        if table_name != keyword.lower():
            print(f"  表搜索返回 '{table.get('name')}' ≠ '{keyword}'，非精确匹配")
            return None
        return table
    except (SystemExit, ValueError):
        return None


def search_nodes(client, table, keyword=None):
    """搜索与表相关的产出任务/节点，按运行态/开发态分组。

    运行态: 优先用 getTableUpstreamTasks 从表反查产出任务；未命中时回退到
            searchBatchEntities 中 deployStatus=2 的节点。
    开发态: searchBatchEntities 中 deployStatus≠2 的节点。

    Returns:
        (runtime_nodes, dev_nodes): 运行态节点列表, 开发态节点列表
    """
    table_name = table.get("name", "")
    project_id = table.get("projectId") or 0

    # searchBatchEntities 同时覆盖运行态和开发态，并通过 GetNode 补全详情
    batch_runtime, batch_dev = _search_batch_entities(client, table_name, project_id)

    # 运行态: 优先 upstream tasks，未命中时用 batch_runtime
    runtime, _ = _search_upstream_tasks(client, table)
    if runtime:
        # upstream tasks 缺少详情，用 batch 结果按名字补全
        batch_by_name = {n["name"]: n for n in batch_runtime}
        for rt in runtime:
            batch_info = batch_by_name.get(rt["name"])
            if batch_info:
                for key in ("workspace", "createTime", "lastEditTime",
                            "lastModifier", "entityId"):
                    if batch_info.get(key) and not rt.get(key):
                        rt[key] = batch_info[key]
    else:
        runtime = batch_runtime

    return runtime, batch_dev


def _search_upstream_tasks(client, table):
    """通过 getTableUpstreamTasks 反查表的产出任务/节点。"""
    entity_guid = table.get("entityGuid")
    project_id = table.get("projectId") or 0
    if not entity_guid:
        return [], []

    try:
        tasks = client.load("getTableUpstreamTasks", entityGuid=entity_guid,
                            entityType="odps-table")
    except Exception as e:
        print(f"getTableUpstreamTasks 失败: {e}", file=sys.stderr)
        return [], []

    if not tasks:
        return [], []

    runtime, dev = [], []
    for item in tasks:
        info = _normalize_upstream_task(item, project_id)
        if not info:
            continue
        _upsert_profile(client, project_id, info)
        if info["deployStatus"] == "2":
            runtime.append(info)
        else:
            dev.append(info)

    if runtime or dev:
        print(f"通过 getTableUpstreamTasks 找到 {len(runtime) + len(dev)} 个产出任务/节点")
    return runtime, dev


def _normalize_upstream_task(item, project_id):
    """把 getTableUpstreamTasks 返回值标准化为内部节点结构。"""
    if not isinstance(item, dict):
        return None

    name = item.get("taskName") or item.get("name") or ""
    task_id = item.get("taskId")
    entity_id = item.get("entityId") or item.get("uuid") or ""
    owner = item.get("ownerName") or item.get("owner") or item.get("principal") or ""

    if not name and not entity_id and not task_id:
        return None

    return {
        "name": name or str(task_id or entity_id),
        "entityId": str(entity_id) if entity_id else "",
        "taskId": str(task_id) if task_id else "",
        "deployStatus": str(item.get("deployStatus", "2")),
        "owner": owner,
        "source": "upstream_task",
        "projectId": item.get("projectId") or project_id,
        "cycleTypeLabel": item.get("cycleTypeLabel", ""),
        "cronExpression": item.get("cronExpression", ""),
    }


def _search_batch_entities(client, table_name, project_id):
    """通过 searchBatchEntities 搜索已发布节点"""
    try:
        nodes = client.load("searchBatchEntities", keyword=table_name,
                            projectId=int(project_id), pageSize=50, pageNum=1,
                            scene="DATAWORKS_PROJECT")
    except Exception as e:
        print(f"searchBatchEntities 失败: {e}", file=sys.stderr)
        return [], []

    if not nodes:
        return [], []

    runtime, dev = [], []
    for n in nodes:
        entity_id = n.get("entityId", "")
        info = {
            "name": n.get("name", ""),
            "entityId": entity_id,
            "deployStatus": str(n.get("deployStatus", "")),
            "owner": n.get("ownerName", n.get("owner", "")),
            "createTime": _fmt_ts(n.get("createTime")),
            "lastEditTime": _fmt_ts(n.get("lastEditTime")),
            "source": "batch",
        }
        # 通过 GetNode 补全工作空间名、最后修改人、taskId
        if entity_id:
            _enrich_from_get_node(client, info, entity_id)
        # 写入 node_profile（零额外 API 调用）
        _upsert_profile(client, project_id, info)
        # 所有节点都有开发态版本，entityId 即开发态节点 ID
        dev.append(info)
        # deployStatus=2 的节点同时也是运行态
        if info["deployStatus"] == "2":
            runtime.append(info)
    return runtime, dev


def search_nodes_by_name(client, keyword, project_id=None):
    """直接按节点名搜索（不经过表搜索），返回 (runtime_nodes, dev_nodes, project_id)。

    当关键字是节点名而非表名时使用此路径。
    project_id 为 None 时从 session 获取。
    """
    from bff_client import resolve_project_id

    if not project_id:
        try:
            project_id = resolve_project_id(client, None, None, tag="[search_nodes]")
        except SystemExit:
            # session 里没有 projectId，输出恢复命令
            print(f"\n→ search_nodes.py \"{keyword}\" --project-id <工作空间 ID>")
            print(f"→ query_instances.py --search \"{keyword}\" --status failed --project-name <工作空间名>")
            sys.exit(1)

    runtime, dev = _search_batch_entities(client, keyword, project_id)

    if not runtime and not dev:
        # 尝试去掉数字前缀重搜（如 "49_dw_meta_collector" → "dw_meta_collector"）
        import re
        stripped = re.sub(r"^\d+_", "", keyword)
        if stripped != keyword:
            print(f"按节点名 '{keyword}' 未找到，尝试去前缀 '{stripped}' ...")
            runtime, dev = _search_batch_entities(client, stripped, project_id)

    return runtime, dev, project_id


def _upsert_profile(client, project_id, info):
    """写入 node_profile（静默失败，不影响主流程）"""
    try:
        from node_profile import get_profile
        np = get_profile()
        if not np:
            return
        np.upsert(
            int(project_id),
            entity_id=info.get("entityId") or None,
            task_id=int(info["taskId"]) if info.get("taskId") else None,
            node_name=info.get("name"),
            owner=info.get("owner"),
            deploy_status=int(info["deployStatus"]) if info.get("deployStatus") else None,
        )
    except Exception:
        pass


def _enrich_from_get_node(client, info, entity_id):
    """通过 GetNode 补全工作空间名、最后修改人、taskId"""
    try:
        detail = client.load("GetNode", uuid=entity_id)
    except Exception:
        return
    if not isinstance(detail, dict):
        return
    project = detail.get("project") or {}
    if project.get("projectName"):
        info["workspace"] = project["projectName"]
    if detail.get("modifierName"):
        info["lastModifier"] = detail["modifierName"]
    if detail.get("taskId"):
        info["taskId"] = str(detail["taskId"])



def query_latest_instances(client, project_id, nodes):
    """查询运行态节点在生产/开发环境的最新实例状态。

    为每个节点查询 prod 和 dev 环境的最新实例，将结果挂到 node 的
    instances 字段: {"prod": {...}, "dev": {...}}
    """
    for node in nodes:
        node_id = node.get("taskId") or node.get("entityId")
        if not node_id:
            continue
        instances = {}
        for env in ("prod", "dev"):
            inst = _query_node_instance(client, project_id, node_id, env)
            if inst:
                instances[env] = inst
        if instances:
            node["instances"] = instances


def _query_node_instance(client, project_id, node_id, env):
    """查询单个节点在指定环境的最新实例。"""
    try:
        result = client.load("listTaskInstances", projectId=str(project_id),
                             nodeId=str(node_id), env=env, pageSize=1, pageStart=1)
    except Exception:
        return None

    if not result:
        return None

    items = result if isinstance(result, list) else [result]
    if not items:
        return None

    inst = items[0] if isinstance(items[0], dict) else {}
    if not inst:
        return None

    status_code = str(inst.get("status", ""))
    return {
        "taskId": inst.get("taskId", ""),
        "status": _INSTANCE_STATUS.get(status_code, status_code),
        "statusCode": status_code,
        "bizDate": inst.get("bizDate", ""),
    }


def _format_node(n, mode="runtime"):
    """格式化节点信息为多行文本

    mode="runtime": taskId 优先（运行态操作用 taskId）
    mode="dev":     entityId 优先（开发态操作用 entityId）
    """
    # 第一行：节点名 + ID 信息（按 mode 决定顺序）
    id_parts = []
    if mode == "dev":
        if n.get("entityId"):
            id_parts.append(f"entityId={n['entityId']}")
        if n.get("taskId"):
            id_parts.append(f"taskId={n['taskId']}")
    else:
        if n.get("taskId"):
            id_parts.append(f"taskId={n['taskId']}")
        if n.get("entityId"):
            id_parts.append(f"entityId={n['entityId']}")
    id_suffix = f" ({', '.join(id_parts)})" if id_parts else ""
    lines = [f"  {n['name']}{id_suffix}"]

    # 第二行：详情
    details = []
    if n.get("workspace"):
        details.append(f"工作空间={n['workspace']}")
    if n.get("owner"):
        details.append(f"负责人={n['owner']}")
    if n.get("cycleTypeLabel"):
        details.append(f"周期={n['cycleTypeLabel']}")
    if details:
        lines.append(f"    {', '.join(details)}")

    # 第三行：时间信息
    time_parts = []
    if n.get("createTime"):
        time_parts.append(f"创建={n['createTime']}")
    if n.get("lastEditTime"):
        time_parts.append(f"最后修改={n['lastEditTime']}")
    if n.get("lastModifier"):
        time_parts.append(f"修改人={n['lastModifier']}")
    if time_parts:
        lines.append(f"    {', '.join(time_parts)}")

    return "\n".join(lines)


def _format_instances(n, indent="    "):
    """格式化节点的实例信息"""
    instances = n.get("instances")
    if not instances:
        return ""
    lines = []
    for env, label in [("prod", "生产环境"), ("dev", "开发环境")]:
        inst = instances.get(env)
        if inst:
            lines.append(f"{indent}{label}: {inst['status']} (业务日期={inst['bizDate']})")
        else:
            lines.append(f"{indent}{label}: 无实例")
    return "\n".join(lines)


_DEPLOY_STATUS_LABELS = {
    "0": "已下线", "1": "未发布", "2": "已发布",
}


def _print_assessment(runtime_nodes, dev_nodes, table_name, project_id):
    """状态判断 + 关键发现 + 建议动作"""
    findings = []
    actions = []

    # ── 判断维度 1：节点发布状态 ──
    offline_nodes = [n for n in (runtime_nodes + dev_nodes)
                     if n.get("deployStatus") == "0"]
    unpublished = [n for n in dev_nodes
                   if n.get("deployStatus") not in ("0", "2")]

    # ── 判断维度 2：实例状态（如果有） ──
    failed_instances = []
    for n in runtime_nodes:
        for env in ("prod", "dev"):
            inst = (n.get("instances") or {}).get(env)
            if inst and inst.get("statusCode") == "5":
                failed_instances.append((n, env, inst))

    # ── 判断维度 3：最后修改距今 ──
    now = datetime.now()
    stale_nodes = []
    for n in runtime_nodes:
        last_edit = n.get("lastEditTime")
        if last_edit:
            try:
                edit_dt = datetime.strptime(last_edit, "%Y-%m-%d %H:%M")
                days_ago = (now - edit_dt).days
                if days_ago > 180:
                    stale_nodes.append((n, days_ago))
            except (ValueError, TypeError):
                pass

    # ── 严重度 ──
    if offline_nodes or failed_instances:
        severity = "🔴 严重"
    elif not runtime_nodes:
        severity = "🟡 注意"
    else:
        severity = "🟢 正常"

    # ── 汇总 ──
    parts = [f"{len(runtime_nodes)} 个运行态", f"{len(dev_nodes)} 个开发态"]
    for n in (runtime_nodes + dev_nodes):
        ds = n.get("deployStatus", "")
        label = _DEPLOY_STATUS_LABELS.get(ds)
        if label and ds != "2":
            parts.append(f"{n['name']} {label}")
    summary = "，".join(parts)

    print(f"\n{'=' * 60}")
    print(f"【状态判断】{severity}：{summary}")

    # ── 关键发现 ──
    if offline_nodes:
        for n in offline_nodes:
            findings.append(f"{n['name']} 已下线（deployStatus=0），无法产出数据")
    if not runtime_nodes:
        findings.append(f"表 {table_name} 无运行态产出节点，数据可能已停止更新")
    if failed_instances:
        for n, env, inst in failed_instances:
            env_label = "生产" if env == "prod" else "开发"
            findings.append(f"{n['name']} {env_label}环境实例失败")
    if stale_nodes:
        for n, days in stale_nodes:
            findings.append(f"{n['name']} 已 {days} 天未修改")

    if findings:
        print("【关键发现】")
        for f in findings:
            print(f"  - {f}")

    # ── 建议动作 ──
    if offline_nodes:
        n = offline_nodes[0]
        owner = n.get("owner") or n.get("lastModifier") or "未知"
        actions.append((f"联系 {owner} 确认下线原因", None))
    if failed_instances:
        n, _, _ = failed_instances[0]
        tid = n.get("taskId", "")
        if tid:
            actions.append((f"查看失败实例详情",
                            f"task_detail.py --project-id {project_id} --node-id {tid}"))
    if runtime_nodes and not offline_nodes and not failed_instances:
        n = runtime_nodes[0]
        tid = n.get("taskId", "")
        if tid:
            actions.append(("查看任务详情和最近运行情况",
                            f"task_detail.py --project-id {project_id} --node-id {tid}"))
            actions.append(("查看运行态节点代码",
                            f"find_node_code.py --project-id {project_id} --task-id {tid} --runtime"))
    if not runtime_nodes and dev_nodes:
        n = dev_nodes[0]
        eid = n.get("entityId", "")
        actions.append(("查看开发态节点代码",
                        f"find_node_code.py --project-id {project_id} --entity-id {eid}"))

    if actions:
        print("【建议动作】")
        for i, (desc, cmd) in enumerate(actions, 1):
            print(f"  {i}. {desc}")
            if cmd:
                print(f"     → {cmd}")


def _output_results(runtime_nodes, dev_nodes, table_name, project_id,
                     with_instances, client):
    """展示节点列表 + 状态判断 + 建议动作"""
    # 查询运行态节点的实例状态
    if with_instances and runtime_nodes:
        print(f"\n查询运行态节点实例状态（生产/开发环境）...")
        query_latest_instances(client, project_id, runtime_nodes)

    # 展示节点列表
    if runtime_nodes:
        print(f"\n运行态节点 ({len(runtime_nodes)} 个):")
        for n in runtime_nodes:
            print(_format_node(n))
            if n.get("instances"):
                print(_format_instances(n))
    else:
        print("\n⚠️ 未找到运行态节点")

    if dev_nodes:
        print(f"\n开发态节点 ({len(dev_nodes)} 个):")
        for n in dev_nodes:
            print(_format_node(n, mode="dev"))

    # 状态判断 + 建议动作
    _print_assessment(runtime_nodes, dev_nodes, table_name, project_id)

    telemetry_end(result={"runtime_count": len(runtime_nodes),
                          "dev_count": len(dev_nodes)})

    save_tool_result("search_nodes", {
        "table_name": table_name,
        "project_id": project_id,
        "runtime_nodes": runtime_nodes,
        "dev_nodes": dev_nodes,
        "summary": f"{len(runtime_nodes)} 个运行态节点, {len(dev_nodes)} 个开发态节点",
    })


def _search_dev_recent(client, project_id, hours, my_owned, by):
    """开发态搜索 searchBatchEntities（scene=DATAWORKS_PROJECT）
    分页真实生效 + 默认排序 lastEditTime DESC 全局单调 → 翻页早停

    返回内部标准化节点列表（含 entityId / createTimeLong / lastEditTimeLong / owner 等）
    """
    start_dt = datetime.now() - timedelta(hours=hours)
    start_ms = int(start_dt.timestamp() * 1000)
    base = {
        "keyword": "",
        "projectId": int(project_id),
        "scene": "DATAWORKS_PROJECT",
        "sortField": "lastEditTime",
        "sortType": "desc",
    }
    if my_owned:
        try:
            user_info = client.load("currentUser") or {}
        except Exception:
            user_info = {}
        uid = user_info.get("loginName") or user_info.get("nickName", "")
        if uid:
            base["owners"] = uid  # searchBatchEntities 底层支持 owners
    PAGE_SIZE = 200
    MAX_PAGES = 300
    raw = []
    total_count = None
    scanned = 0
    hit_cap = False
    for pn in range(1, MAX_PAGES + 1):
        try:
            resp = client.call_raw("searchBatchEntities", **base, pageSize=PAGE_SIZE, pageNum=pn)
        except Exception as e:
            print(f"searchBatchEntities 失败 (page={pn}): {e}", file=sys.stderr)
            break
        if not client.is_success(resp):
            print(f"searchBatchEntities 失败 (page={pn}): {resp.get('message')}", file=sys.stderr)
            break
        rd = resp.get("data") or {}
        items = rd.get("data") or []
        if total_count is None:
            total_count = rd.get("totalCount") or 0
        if not items:
            break
        scanned += len(items)
        hit_end = False
        for it in items:
            last_edit = it.get("lastEditTime") or 0
            if last_edit < start_ms:
                hit_end = True  # 单调 desc，之后必然更早
                break
            if by == "create":
                # 最近创建 ⊂ 最近修改，再按 createTime 精筛
                ct = it.get("createTime") or 0
                if ct < start_ms:
                    continue
            raw.append(it)
        if hit_end:
            break
        if len(items) < PAGE_SIZE:
            break
        if pn == MAX_PAGES:
            hit_cap = True
    if hit_cap:
        print(f"⚠️ 达翻页上限 {MAX_PAGES} 页，可能还有更多节点未扫到。缩小 --hours 或加 --my-owned 收窄", file=sys.stderr)
    print(f"扫描开发态节点 {scanned} 个（totalCount={total_count}），窗口内 {len(raw)} 个", file=sys.stderr)

    nodes = []
    for it in raw:
        create_ms = it.get("createTime") or 0
        edit_ms = it.get("lastEditTime") or 0
        nodes.append({
            "nodeId": "",  # 开发态无 scheduler nodeId
            "nodeName": it.get("name", ""),
            "owner": it.get("owner", ""),
            "ownerName": it.get("ownerName", ""),
            "modifyUser": it.get("modifier") or it.get("owner", ""),
            "modifyUserName": it.get("modifierName") or it.get("ownerName", ""),
            "modifyTime": _fmt_ts(edit_ms),
            "gmtCreate": _fmt_ts(create_ms),
            "creator": it.get("creator") or it.get("owner", ""),
            "creatorName": it.get("creatorName") or it.get("ownerName", ""),
            "entityId": it.get("entityId", ""),
            "deployStatus": it.get("deployStatus", ""),
            "commandType": it.get("commandType", ""),
        })
    return nodes


def search_recent_changes(client, project_id, hours=24, my_changes=False,
                          my_owned=False, env="PROD", by="modify",
                          resolve_entity=True, scope="runtime"):
    """扫工作空间最近节点。

    scope="runtime" (默认)：走 searchSchedulerNodes，只覆盖已发布到调度的节点
    scope="dev"：走 searchBatchEntities，覆盖开发态节点（含未发布草稿）
    by="modify": 按修改时间过滤；by="create": 按创建时间过滤
    resolve_entity=False 时跳过 node_profile.resolve
    """
    if scope == "dev":
        return _search_dev_recent(client, project_id, hours=hours, my_owned=my_owned or my_changes, by=by)
    start_dt = datetime.now() - timedelta(hours=hours)
    start_ms = int(start_dt.timestamp() * 1000)
    base_params = {
        "executeMethod": "SEARCH",
        "projectId": project_id,
        "env": env,
    }
    # searchSchedulerNodes 无按创建时间区间过滤参数，但有 modifyStartTime。
    # 洞察：最近一周创建的节点 ⊂ 最近一周修改的节点（创建即首次修改）→
    # 用 modifyStartTime 服务端预筛，client 再按 createTimeLong 精确过滤 "真的是这周创建的"。
    base_params["modifyStartTime"] = start_dt.strftime("%Y-%m-%d %H:%M:%S")

    if my_changes or my_owned:
        try:
            user_info = client.load("currentUser") or {}
        except Exception as e:
            print(f"currentUser 失败: {e}", file=sys.stderr)
            user_info = {}
        user_id = user_info.get("loginName") or user_info.get("nickName", "")
        if my_changes and user_id:
            base_params["modifyUser"] = user_id
        if my_owned and user_id:
            base_params["owner"] = user_id

    # searchSchedulerNodes 实测服务端分页失效（pageStart/pageNum 被忽略，返回相同前 N 条）。
    # 策略：单次 call_raw pageSize=2000（硬上限），看 data.count 判断是否触顶
    try:
        resp = client.call_raw("searchSchedulerNodes", pageSize=2000, **base_params)
    except Exception as e:
        print(f"searchSchedulerNodes 失败: {e}", file=sys.stderr)
        return []
    if not client.is_success(resp):
        print(f"searchSchedulerNodes 失败: {resp.get('message')}", file=sys.stderr)
        return []
    _data = resp.get("data") or {}
    all_nodes_raw = _data.get("returnValue") or []
    total_count = _data.get("count") or 0
    if total_count > 2000:
        print(f"⚠️ 服务端匹配 {total_count} 条，但分页不可用（pageStart 失效），只返回前 2000 条。建议缩小 --hours 或加 --my-changes/--my-owned 收窄", file=sys.stderr)
        print(f"⚠️ 服务端匹配 {total_count} 条，仅返回前 2000 条（分页不可用），建议缩窗或加过滤")

    if by == "modify":
        raw = all_nodes_raw
    else:
        # --by create: 服务端已按 modifyStartTime 预筛（最近创建⊂最近修改），客户端再精确过滤
        raw = []
        earliest_hit_ms = None
        latest_hit_ms = None
        for n in all_nodes_raw:
            cts = n.get("createTimeLong") or 0
            if cts >= start_ms:
                raw.append(n)
                if earliest_hit_ms is None or cts < earliest_hit_ms:
                    earliest_hit_ms = cts
                if latest_hit_ms is None or cts > latest_hit_ms:
                    latest_hit_ms = cts
        print(f"服务端按 modifyStartTime 预筛回 {len(all_nodes_raw)} 个节点，客户端按 createTime 精筛 {len(raw)} 个"
              + (f"（createTime 实际范围: {_fmt_ts(earliest_hit_ms)} ~ {_fmt_ts(latest_hit_ms)}）" if raw else ""),
              file=sys.stderr)
    nodes = []
    for n in raw:
        node_id = n.get("nodeId")
        if not node_id:
            continue
        # 字段映射：searchSchedulerNodes 实际返回 createTime/createTimeLong/createUser，
        # 无 createUserName（创建人姓名取不到就回落到工号）
        create_long = n.get("createTimeLong")
        modify_long = n.get("modifyTimeLong")
        nodes.append({
            "nodeId": str(node_id),
            "nodeName": n.get("nodeName", ""),
            "owner": n.get("owner", ""),
            "ownerName": n.get("ownerName", ""),
            "modifyUser": n.get("modifyUser", ""),
            "modifyUserName": n.get("modifyUserName", ""),
            "modifyTime": _fmt_ts(modify_long) or n.get("modifyTime", ""),
            "gmtCreate": _fmt_ts(create_long) or n.get("createTime", ""),
            "creator": n.get("createUser", ""),
            "creatorName": n.get("createUserName") or n.get("createUser", ""),  # 回落到 login
            "entityId": "",
        })

    if resolve_entity and nodes:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from node_profile import resolve as np_resolve
        total = len(nodes)
        # 节点数过多时 resolve 成本 >>> 价值（用户大概率只想要计数/分布），给出 stderr 提示
        if total > 100:
            print(f"⚠️ 命中 {total} 个节点，entityId 反查耗时较长；", file=sys.stderr)
            print(f"   仅需计数/分布用: --group-by owner 可跳过反查瞬时返回", file=sys.stderr)
        print(f"正在并发解析 {total} 个节点的 entityId ...", file=sys.stderr)

        def _resolve_one(item):
            try:
                profile = np_resolve(int(project_id), client, task_id=int(item["nodeId"]))
                if profile:
                    item["entityId"] = profile.get("entity_id", "") or ""
                    if not item["nodeName"]:
                        item["nodeName"] = profile.get("node_name", "") or ""
            except Exception:
                pass
            return item

        done = 0
        with ThreadPoolExecutor(max_workers=8) as ex:
            for _ in as_completed([ex.submit(_resolve_one, n) for n in nodes]):
                done += 1
                if done % 20 == 0 or done == total:
                    print(f"  已解析 {done}/{total}", file=sys.stderr)

    return nodes


def _group_nodes_by_owner(nodes, by="modify"):
    """按创建人/修改人聚合，login（工号）为主键去重。返回 (rows, total)。

    rows: [(display_name, login, count, pct), ...]，按 count desc 排序。
    """
    from collections import Counter
    counter = Counter()
    name_map = {}
    for n in nodes:
        if by == "create":
            login = n.get("creator") or ""
            name = n.get("creatorName") or ""
        else:
            login = n.get("modifyUser") or n.get("owner") or ""
            name = n.get("modifyUserName") or n.get("ownerName") or ""
        if not login:
            continue
        counter[login] += 1
        if name and login not in name_map:
            name_map[login] = name
    total = sum(counter.values())
    rows = []
    for login, cnt in counter.most_common():
        pct = (cnt * 100.0 / total) if total else 0
        rows.append((name_map.get(login, login), login, cnt, pct))
    return rows, total


def _print_recent_results(nodes, project_id, hours, my_changes, my_owned,
                          by="modify", group_by=None):
    action_label = "新发布" if by == "create" else "变更"  # 仅运行态（scheduler），非 IDE 开发态草稿
    flag_suffix = ""
    if by == "create":
        flag_suffix += " --by create"
    if my_changes:
        flag_suffix += " --my-changes"
    if my_owned:
        flag_suffix += " --my-owned"

    trunc_note = ""  # 截断警告由 bff_client 自己打印（stdout "⚠️ xxx 已截断为前 N 条"）
    if group_by == "owner":
        rows, total = _group_nodes_by_owner(nodes, by=by)
        role = "创建人" if by == "create" else "修改人"
        print(f"最近 {hours}h {action_label}节点: {total} 个 (projectId={project_id}{flag_suffix}) — 按{role}分布{trunc_note}")
        if not rows:
            print("  （无数据）")
            return
        print()
        print(f"  {'排名':<4} {'姓名':<12} {'工号':<10} {'数量':>6} {'占比':>7}")
        for i, (name, login, cnt, pct) in enumerate(rows, 1):
            print(f"  {i:<4} {name:<12} {login:<10} {cnt:>6} {pct:>6.1f}%")
        print(f"\n  合计: {total}")
        print()
        print(f"→ 看明细:       python search_nodes.py --recent --project-id {project_id} --hours {hours}" + (" --by create" if by == "create" else ""))
        return

    if not nodes:
        print(f"最近 {hours}h 无{action_label}节点 (projectId={project_id}{flag_suffix})")
        print()
        if hours <= 24:
            print(f"→ 扩大时间窗:   python search_nodes.py --recent --project-id {project_id} --hours 168{flag_suffix}")
        if by == "modify":
            print(f"→ 按创建时间:   python search_nodes.py --recent --project-id {project_id} --by create")
        if not my_changes and not my_owned:
            print(f"→ 只看我提交:   python search_nodes.py --recent --project-id {project_id} --my-changes")
            print(f"→ 只看我负责:   python search_nodes.py --recent --project-id {project_id} --my-owned")
        print(f"→ 查已知节点:   python identify.py <nodeName|entityId> --project-id {project_id}")
        return

    # 先收集**全部** entityId（下一步命令用全量，不受展示截断影响）
    all_entity_ids = [n.get("entityId", "") for n in nodes if n.get("entityId")]
    missing_eid = len(nodes) - len(all_entity_ids)

    print(f"最近 {hours}h {action_label}节点: {len(nodes)} 个 (projectId={project_id}{flag_suffix}){trunc_note}")
    if missing_eid:
        print(f"  ⚠️ {missing_eid} 个节点 entityId 未解析（node_profile 反查失败）")
    print()
    for i, n in enumerate(nodes[:20], 1):
        name = n.get("nodeName") or "?"
        eid = n.get("entityId", "")
        nid = n.get("nodeId", "")
        eid_part = f"entityId={eid}" if eid else "(entityId 未解析)"
        print(f"  [{i}] {name}  {eid_part}  nodeId={nid}")
        meta = []
        if by == "create":
            creator = n.get("creatorName") or n.get("creator", "")
            if creator:
                meta.append(f"creator={creator}")
            if n.get("gmtCreate"):
                meta.append(f"gmtCreate={n['gmtCreate']}")
        else:
            owner = n.get("ownerName") or n.get("owner", "")
            mu = n.get("modifyUserName") or n.get("modifyUser", "")
            if owner:
                meta.append(f"owner={owner}")
            if mu:
                meta.append(f"modifyUser={mu}")
            if n.get("modifyTime"):
                meta.append(f"modifyTime={n['modifyTime']}")
        if meta:
            print(f"      {', '.join(meta)}")
    if len(nodes) > 20:
        print(f"  ... 共 {len(nodes)} 个（仅展示前 20，下一步命令含全部 {len(all_entity_ids)} 个 entityId）")

    print()
    group_cmd = f"python search_nodes.py --recent --project-id {project_id} --hours {hours}" + (" --by create" if by == "create" else "") + " --group-by owner"
    print(f"→ 按人分布:     {group_cmd}")

    # 治理检查命令：全量 entityId。超过 30 个写 .dataworks/ 临时文件，用 @file 语法引用
    if all_entity_ids and by == "modify":
        if len(all_entity_ids) <= 30:
            joined = ",".join(all_entity_ids)
            print(f"→ 治理检查:     python dgc_check_nodes.py --file-ids {joined} --project-id {project_id}")
        else:
            from pathlib import Path
            import os
            dw_dir = Path(".dataworks")
            dw_dir.mkdir(exist_ok=True)
            fpath = dw_dir / f"recent_entity_ids_{project_id}.txt"
            fpath.write_text("\n".join(all_entity_ids))
            abs_fpath = os.path.abspath(fpath)
            print(f"→ 治理检查全量: python dgc_check_nodes.py --file-ids @{abs_fpath} --project-id {project_id}  # {len(all_entity_ids)} 个 entityId 已写入文件")
            short = ",".join(all_entity_ids[:30])
            print(f"→ 治理检查前30: python dgc_check_nodes.py --file-ids {short} --project-id {project_id}")

    if nodes and nodes[0].get("nodeId"):
        nid = nodes[0]["nodeId"]
        print(f"→ 查节点代码:   python find_node_code.py --project-id {project_id} --task-id {nid} --runtime")
        print(f"→ 查节点档案:   python identify.py {nid} --project-id {project_id}")


def main():
    parser = argparse.ArgumentParser(
        description="节点搜索工具 — 从表名或节点名出发，定位任务/节点；--recent 扫最近变更",
        epilog="输出: 运行态/开发态节点列表。获取代码请用 find_node_code.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("keyword", nargs="?",
                        help="表名或节点名关键字（支持 '项目.表名' 格式自动拆分）；--recent 时可省略")
    parser.add_argument("--project", help="按项目名过滤（对应 databaseName）")
    parser.add_argument("--project-id", type=int, help="工作空间 ID（节点名直搜 / --recent 时必填）")
    parser.add_argument("--with-instances", action="store_true",
                        help="查询运行态节点在生产/开发环境的最新实例状态")
    parser.add_argument("--recent", action="store_true",
                        help="扫工作空间最近节点（需配 --project-id）")
    parser.add_argument("--hours", type=int, default=24,
                        help="--recent 的时间窗（小时，默认 24）")
    parser.add_argument("--by", choices=["modify", "create"], default="modify",
                        help="--recent 的时间维度：modify=最近变更（默认），create=最近新建")
    parser.add_argument("--my-changes", action="store_true",
                        help="--recent 时只看我变更的节点")
    parser.add_argument("--my-owned", action="store_true",
                        help="--recent 时只看我负责的节点")
    parser.add_argument("--env", default="PROD",
                        help="--recent 查询环境（PROD/DEV，默认 PROD，仅 runtime 模式生效）")
    parser.add_argument("--scope", choices=["runtime", "dev"], default="runtime",
                        help="--recent 扫描范围：runtime=已发布到调度（默认，searchSchedulerNodes）；dev=开发态含未发布草稿（searchBatchEntities）")
    parser.add_argument("--group-by", choices=["owner"],
                        help="--recent 聚合模式：owner=按创建人/修改人分布")
    args = parser.parse_args()

    if args.recent:
        if not args.project_id:
            print("--recent 需要 --project-id", file=sys.stderr)
            print("→ python identify.py <工作空间名>  # 先查工作空间 ID", file=sys.stderr)
            sys.exit(1)
        client = BFFClient(quiet=True)
        telemetry_start("search_nodes.py", module="discovery",
                        mode="recent", project_id=args.project_id,
                        hours=args.hours, by=args.by, group_by=args.group_by or "")
        # dev scope：entityId 已内建返回，无需 resolve；runtime scope 聚合模式也跳过 resolve
        resolve_entity = args.group_by is None and args.scope == "runtime"
        nodes = search_recent_changes(
            client, args.project_id,
            hours=args.hours, my_changes=args.my_changes,
            my_owned=args.my_owned, env=args.env, by=args.by,
            resolve_entity=resolve_entity, scope=args.scope,
        )
        _print_recent_results(nodes, args.project_id, args.hours,
                              args.my_changes, args.my_owned,
                              by=args.by, group_by=args.group_by)
        save_tool_result("search_nodes", {
            "mode": "recent",
            "project_id": args.project_id,
            "hours": args.hours,
            "by": args.by,
            "group_by": args.group_by,
            "count": len(nodes),
            "nodes": nodes if args.group_by is None else None,
        })
        telemetry_end(result={"recent_count": len(nodes)})
        return

    if not args.keyword:
        parser.error("缺少 keyword（或使用 --recent 扫最近变更）")

    keyword = args.keyword
    project = args.project
    if not project and "." in keyword:
        parts = keyword.split(".", 1)
        project = parts[0]
        keyword = parts[1]

    client = BFFClient(quiet=True)
    telemetry_start("search_nodes.py", module="discovery", keyword=keyword)

    # 路径 1：从表名出发（表搜索 → 上游任务 → 节点）
    print(f"搜索表: {keyword} ...")
    table = search_table(client, keyword, project=project)

    if table:
        table_name = table.get("name", keyword)
        project_id = table.get("projectId") or 0
        print(f"表: {table_name} (项目: {table.get('databaseName', '?')}, projectId: {project_id})")
        print(f"\n定位产出任务/节点（优先 getTableUpstreamTasks，未命中时回退节点名搜索）...")
        runtime_nodes, dev_nodes = search_nodes(client, table, keyword=keyword)
        _output_results(runtime_nodes, dev_nodes, table_name, project_id,
                        args.with_instances, client)
        return

    # 路径 2：表未找到，按节点名直搜
    print(f"\n表搜索未命中，按节点名直搜: {keyword} ...")
    runtime_nodes, dev_nodes, project_id = search_nodes_by_name(
        client, keyword, project_id=args.project_id)

    if runtime_nodes or dev_nodes:
        _output_results(runtime_nodes, dev_nodes, keyword, project_id,
                        args.with_instances, client)
        return

    # 两条路径都没找到
    print(f"\n⚠️ 未找到与 '{keyword}' 匹配的表或节点")
    print(f"\n→ query_instances.py --search \"{keyword}\" --status failed")
    print(f"→ search_table.py \"{keyword}\"")
    telemetry_end(result={"runtime_count": 0, "dev_count": 0})
    sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("search_nodes.py", "discovery", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("search_nodes.py", "discovery", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
