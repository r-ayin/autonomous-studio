#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节点识别工具 —— 给任意线索，返回完整节点档案

用法:
    python identify.py "ods_chat_history"                          # 表名或节点名
    python identify.py 178493714 --project-id 14255                # 运行态 nodeId
    python identify.py 93247000568 --project-id 14255              # 实例 instanceId
    python identify.py abc-def-123 --project-id 14255              # 开发态 entityId

自动识别输入类型（名称 / nodeId / instanceId / entityId），
通过 node_profile.resolve() 补全整条链，输出完整档案卡 + 下一步命令。
"""

import argparse
import re
import sys

from bff_client import BFFClient, save_tool_result, resolve_project_id
from telemetry import telemetry_start, telemetry_end, telemetry_fail

_TAG = "[identify]"


# ── 输入类型识别 ──────────────────────────────────────────

def _classify_input(keyword):
    """识别输入类型: name / node_id / instance_id / entity_id"""
    s = keyword.strip()

    # UUID 格式（含连字符或 32+ 位十六进制）
    if re.match(r'^[0-9a-f]{8}-', s, re.IGNORECASE):
        return "entity_id", s

    # 纯数字
    if s.isdigit():
        n = int(s)
        # 实例 ID 通常 > 10^10（11位+），nodeId 通常 < 10^10
        if n > 10_000_000_000:
            return "instance_id", s
        else:
            return "node_id", s

    # 非常长的数字型 entityId（searchBatchEntities 返回的那种）
    # 这种 entityId 是纯数字但很长（15-20位），和 instanceId 难以区分
    # 如果 > 10^14 且没有其他上下文，优先当 entity_id 尝试
    if re.match(r'^\d{15,}$', s):
        return "entity_id", s

    # 其余当名称（后续在 resolve 阶段会尝试匹配工作空间）
    return "name", s


# ── 按类型解析 ──────────────────────────────────────────

def _parse_search_files_hit(hit):
    """将 searchFiles 返回的 hit 转为统一的节点 dict"""
    xattrs = hit.get("xattrs", {})
    vp = xattrs.get("vertexProperties", {})
    owner = hit.get("owner", {})
    deploy_str = vp.get("deployStatus", "")
    deploy_map = {"DEPLOYED_PROD": 2, "DEPLOYED_DEV": 1}
    entity_id = vp.get("uuid") or hit.get("uuid")
    return {
        "entityId": entity_id,
        "name": hit.get("name"),
        "ownerName": owner.get("userName", ""),
        "owner": owner.get("userId", ""),
        "deployStatus": str(deploy_map.get(deploy_str, 0)),
        "command": vp.get("command", ""),
        "path": hit.get("path", ""),
    }


def _search_nodes_in_project(client, keyword, proj):
    """在单个 workspace 内搜节点。返回 list[dict]，dict 含 _source 标签（runtime/dev）。"""
    pid = proj.get("projectId")
    if not pid:
        return []
    pname = proj.get("projectName", "")
    # 优先 getNodeList（运行态，直接拿 nodeId）
    try:
        api_meta = client.api_index.get("getNodeList")
        if api_meta:
            result = client._do_request("getNodeList", api_meta,
                                        projectId=int(pid), env="prod", tenantId=1,
                                        searchText=keyword, pageNum=1, pageSize=10,
                                        includeRelation="false",
                                        expired="false", lonely="false",
                                        sortOrder="", sortField="",
                                        prgTypes="", owner="", resgroupId="",
                                        connectionRegionId="", solId="",
                                        nodeTag="", bizId="",
                                        connectionType="", connections="",
                                        baseLineId="", priorityList="",
                                        scheIntervalList="",
                                        diResGroupIdentifier="",
                                        diSrcType="", diSrcDatasource="",
                                        diDstType="", diDstDatasource="",
                                        flowId="", advanceSort="")
            items = (result.get("data") or {}).get("data", []) or []
            out = []
            for n in items:
                out.append({**n, "_project_id": pid, "_project_name": pname, "_source": "runtime"})
            if out:
                return out
    except Exception:
        pass
    # fallback: searchFiles（开发态）
    try:
        result = client.load("searchFiles", keyword=keyword,
                             projectId=int(pid), pageSize=10, pageNum=1,
                             scene="DATAWORKS_PROJECT",
                             withAncestorFolder="true")
        if isinstance(result, dict):
            hits = result.get("data", {}).get("hits", []) or []
            out = []
            for h in hits:
                n = _parse_search_files_hit(h)
                out.append({**n, "_project_id": pid, "_project_name": pname, "_source": "dev"})
            if out:
                return out
    except Exception:
        pass
    return []


def _match_workspaces(client, keyword):
    """名称 → workspace 匹配（精确 projectName/displayName 优先，其次模糊包含）"""
    try:
        projects = client.load("ListProjects", pageSize=100) or []
    except Exception:
        return []
    kw = keyword.lower()
    exact = []
    fuzzy = []
    for p in projects:
        if p.get("status") != "Available":
            continue
        pname = (p.get("projectName") or "").lower()
        dname = (p.get("displayName") or "").lower()
        if kw == pname or kw == dname:
            exact.append(p)
        elif kw in pname or kw in dname:
            fuzzy.append(p)
    return exact if exact else fuzzy


def _match_tables(client, keyword):
    """全库精确匹配表名（大小写不敏感）"""
    from search_table import search_all_types
    try:
        tables = search_all_types(client, keyword) or []
    except Exception as e:
        print(f"[identify] _match_tables('{keyword}') error: {e}", file=sys.stderr)
        return []
    return [t for t in tables if (t.get("name") or "").lower() == keyword.lower()]


def _match_nodes(client, keyword, project_id):
    """project_id 指定则单空间搜；否则遍历所有可用空间"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if project_id:
        # 单空间：走 search_nodes_by_name（已有的封装）
        from search_nodes import search_nodes_by_name
        try:
            runtime, dev, pid = search_nodes_by_name(client, keyword, project_id=project_id)
        except SystemExit:
            return []
        out = []
        for n in (runtime or []):
            out.append({**n, "_project_id": pid, "_source": "runtime"})
        for n in (dev or []):
            out.append({**n, "_project_id": pid, "_source": "dev"})
        return out

    # 遍历所有空间
    try:
        projects = client.load("ListProjects", pageSize=100) or []
    except Exception:
        return []
    active = [p for p in projects if p.get("status") == "Available"]
    if not active:
        return []
    all_hits = []
    with ThreadPoolExecutor(max_workers=min(len(active), 8)) as pool:
        futures = {pool.submit(_search_nodes_in_project, client, keyword, p): p for p in active}
        for f in as_completed(futures):
            try:
                all_hits.extend(f.result() or [])
            except Exception:
                continue
    return all_hits


def _profile_from_table(client, keyword, table, project_id, deep=False):
    """单表命中 → 默认只返回表 profile（含 getDetail 补全），不查上游节点（避免 30+s 节点查询）

    deep=True 时才并发查上游节点 + 补全 task/entity 字段。
    deep=False 时 next_steps 引导用户加 --deep 看节点详情。
    """
    # 补全 metaEntityId / lifeCycle 等字段
    entity_guid = table.get("entityGuid")
    if entity_guid and not table.get("metaEntityId"):
        try:
            detail = client.load("getDetail", entityType="odps-table", entityGuid=entity_guid)
            if isinstance(detail, dict):
                table.update(detail)
        except Exception:
            pass

    table_pid = table.get("projectId") or project_id

    if not deep:
        # 默认轻档案：不查节点，只给表信息（让 _print_profile 走 table-only next steps + --deep 引导）
        return {
            "node_name": table.get("name"),
            "project_id": table_pid,
            "_table": table,
        }

    # --deep: 查上游节点
    from search_nodes import search_nodes as search_nodes_via_table
    runtime, dev = search_nodes_via_table(client, table, keyword=keyword)
    nodes = runtime or dev
    if nodes:
        first = nodes[0]
        return {
            "task_id": int(first["taskId"]) if first.get("taskId") else None,
            "entity_id": first.get("entityId") or None,
            "node_name": first.get("name"),
            "owner": first.get("owner"),
            "project_id": table_pid,
            "deploy_status": int(first.get("deployStatus", 0)),
            "_all_nodes": nodes,
            "_table": table,
        }
    # 表找到了但没产出节点
    return {
        "node_name": table.get("name"),
        "project_id": table_pid,
        "_table": table,
    }


def _profile_from_node(client, node):
    """单节点命中 → 构建 profile（含 node_profile.resolve 的补全）"""
    from node_profile import resolve as _resolve_profile
    pid = node.get("_project_id")
    source = node.get("_source")

    if source == "runtime":
        task_id = node.get("nodeId") or node.get("taskId")
        profile = {
            "task_id": int(task_id) if task_id else None,
            "entity_id": node.get("entityId") or None,
            "node_name": node.get("nodeName") or node.get("name"),
            "owner": node.get("ownerName") or node.get("owner"),
            "project_id": pid,
            "node_type": node.get("prgTypeName"),
            "cron_express": node.get("cronExpress"),
            "schedule_type": node.get("cycTypeName"),
            "baseline_name": node.get("baseLineName"),
            "res_group": node.get("resGroupName"),
            "priority": int(node["priority"]) if node.get("priority") is not None else None,
            "deploy_status": int(node.get("deployStatus", 0)) if node.get("deployStatus") else 2,
        }
        if task_id:
            enriched = _resolve_profile(pid, client, task_id=int(task_id))
            if enriched:
                for k, v in enriched.items():
                    if v is not None and profile.get(k) is None:
                        profile[k] = v
        return profile

    # dev（searchFiles）
    entity_id = node.get("entityId")
    profile = {
        "task_id": None,
        "entity_id": entity_id or None,
        "node_name": node.get("name"),
        "owner": node.get("ownerName") or node.get("owner"),
        "project_id": pid,
        "deploy_status": int(node.get("deployStatus", 0)) if node.get("deployStatus") else 0,
    }
    if entity_id:
        enriched = _resolve_profile(pid, client, entity_id=entity_id)
        if enriched:
            for k, v in enriched.items():
                if v is not None and profile.get(k) is None:
                    profile[k] = v
    return profile


def _print_multi_candidates(keyword, ws, tables, nodes, project_id):
    """跨类型或同类多个 → 分组列候选 + identify 命令引导用户选类别后深探"""
    total = len(ws) + len(tables) + len(nodes)
    cats = []
    if ws: cats.append(f"工作空间×{len(ws)}")
    if tables: cats.append(f"表×{len(tables)}")
    if nodes: cats.append(f"节点×{len(nodes)}")
    cat_str = " / ".join(cats)

    print(f"\n{_TAG} '{keyword}' 命中 {total} 个候选（{cat_str}）—— 不替你选，请挑一条命令再次执行：")

    if ws:
        print(f"\n【工作空间】{len(ws)} 个")
        for w in ws[:5]:
            name = w.get("projectName", "")
            display = w.get("displayName", "")
            label = f"{display} ({name})" if display and display != name else name
            print(f"  identify.py \"{name}\"   # workspace: {label}")

    if tables:
        print(f"\n【表】{len(tables)} 个（跨数据库；选定后 identify 会输出表元信息+字段+分区+最新分区）")
        for t in tables[:5]:
            db = t.get("databaseName", "?")
            nm = t.get("name", "?")
            et = t.get("entityType", "?")
            print(f"  identify.py \"{nm}\" --project {db}   # table ({et}) @ {db}")
        if len(tables) > 5:
            print(f"  ... 共 {len(tables)} 张，已截断前 5 个")

    if nodes:
        print(f"\n【节点】{len(nodes)} 个（跨工作空间）")
        for n in nodes[:5]:
            pid = n.get("_project_id")
            pname = n.get("_project_name", "")
            source = n.get("_source")
            if source == "runtime":
                nid = n.get("nodeId") or n.get("taskId")
                nname = n.get("nodeName") or n.get("name", "")
                print(f"  identify.py {nid} --project-id {pid}   # node: {nname} @ {pname}")
            else:
                eid = n.get("entityId")
                nname = n.get("name", "")
                print(f"  identify.py {eid} --project-id {pid}   # dev node: {nname} @ {pname}")
        if len(nodes) > 5:
            print(f"  ... 共 {len(nodes)} 个节点，已截断前 5 个")


def _resolve_by_name(client, keyword, project_id, deep=False, project=None):
    """并发搜 workspace / table / node → 汇总消歧

    单命中直接返回 profile；多命中（跨类型或同类多个）分组打印候选 + sys.exit(0)，
    让 agent 按命令重试，避免跨层混淆（节点 vs 表）。
    """
    from concurrent.futures import ThreadPoolExecutor

    scope = f"workspace={project_id}" if project_id else "全局"
    print(f"{_TAG} 并发搜索 workspace / table / node ({scope}) ...")

    with ThreadPoolExecutor(max_workers=3) as pool:
        f_ws = pool.submit(_match_workspaces, client, keyword)
        f_tb = pool.submit(_match_tables, client, keyword)
        f_nd = pool.submit(_match_nodes, client, keyword, project_id)

    ws = f_ws.result() or []
    tables = f_tb.result() or []
    nodes = f_nd.result() or []

    # 显式 --project (databaseName) 过滤表
    if project and tables:
        filtered = [t for t in tables if (t.get("databaseName") or "").lower() == project.lower()]
        if filtered:
            print(f"{_TAG} 显式 --project={project}，过滤到 {len(filtered)} 张表")
            tables = filtered
            # 同时过滤掉无关 workspace 候选（用户已表态要这个 db 的表）
            ws = []

    print(f"{_TAG} 命中: workspace={len(ws)} table={len(tables)} node={len(nodes)}")
    total = len(ws) + len(tables) + len(nodes)

    if total == 0:
        return None  # caller 打 not_found

    # workspace 级启发式：有 project_id + 多张同名表 → 尝试过滤到 workspace 绑定的 prod 数据库
    if project_id and len(tables) > 1:
        from bff_client import project_id_to_project_name
        pname = project_id_to_project_name(client, project_id)
        if pname:
            prod = [t for t in tables if (t.get("databaseName") or "").lower() == pname.lower()]
            dev = [t for t in tables if (t.get("databaseName") or "").lower() == f"{pname.lower()}_dev"]
            if len(prod) == 1:
                print(f"{_TAG} 同名表多张，自动选 workspace {project_id} 的 prod 数据库 '{pname}'。要 dev 请用 --project {pname}_dev")
                tables = prod
            elif not prod and len(dev) == 1:
                print(f"{_TAG} prod 数据库 '{pname}' 未命中，已自动回退 dev 数据库 '{pname}_dev'")
                tables = dev

    total = len(ws) + len(tables) + len(nodes)

    # 总共 1 个命中 → 直接返回
    if total == 1:
        if ws:
            _print_workspace(ws[0], keyword)
            telemetry_end(result={"status": "ok", "input_type": "workspace",
                                  "project_id": ws[0].get("projectId")})
            sys.exit(0)
        if tables:
            return _profile_from_table(client, keyword, tables[0], project_id, deep=deep)
        if nodes:
            return _profile_from_node(client, nodes[0])

    # 多命中 → 分组打印 + 干净退出（不是 failure）
    _print_multi_candidates(keyword, ws, tables, nodes, project_id)
    telemetry_end(result={"status": "multi_candidates",
                          "ws_count": len(ws),
                          "table_count": len(tables),
                          "node_count": len(nodes)})
    sys.exit(0)


def _resolve_by_node_id(client, project_id, node_id):
    """按运行态 nodeId 解析"""
    from node_profile import resolve
    return resolve(project_id, client, task_id=int(node_id))


def _resolve_by_instance_id(client, project_id, instance_id):
    """按实例 ID 反查 nodeId，再 resolve"""
    # 先通过 get_task_instance 拿 nodeId
    api_meta = client.api_index.get("get_task_instance")
    if api_meta:
        try:
            result = client._do_request("get_task_instance", api_meta,
                                        taskInstanceId=instance_id)
            data = result.get("data", {})
            if isinstance(data, dict):
                node_id = data.get("nodeId") or data.get("dagId")
                node_name = data.get("nodeName") or data.get("dagName")
                if node_id:
                    print(f"{_TAG} instanceId={instance_id} → nodeId={node_id} ({node_name})")
                    from node_profile import resolve
                    profile = resolve(project_id, client, task_id=int(node_id))
                    if profile:
                        profile["_instance_id"] = instance_id
                        return profile
        except Exception:
            pass

    # fallback: 可能不是 instanceId 而是 nodeId，尝试按 nodeId 解析
    print(f"{_TAG} 按 instanceId 查询未命中，尝试当 nodeId 解析")
    return _resolve_by_node_id(client, project_id, instance_id)


def _resolve_by_entity_id(client, project_id, entity_id):
    """按开发态 entityId 解析"""
    from node_profile import resolve
    return resolve(project_id, client, entity_id=entity_id)


def _try_resolve_workspace(client, keyword, exact_only=False):
    """尝试按名称匹配工作空间。exact_only=True 时只返回 projectName/displayName 精确匹配"""
    try:
        projects = client.load("ListProjects", pageSize=100)
        if not projects:
            return None
        kw = keyword.lower()
        # 精确匹配 projectName（英文标识）/ displayName（中文名）
        for p in projects:
            pname = (p.get("projectName") or "").lower()
            display = (p.get("displayName") or "").lower()
            if kw == pname or kw == display:
                return p
        if exact_only:
            return None
        # 模糊匹配（包含）
        for p in projects:
            pname = (p.get("projectName") or "").lower()
            display = (p.get("displayName") or "").lower()
            if kw in pname or kw in display:
                return p
    except Exception:
        pass
    return None


def _print_workspace(ws, keyword):
    """输出工作空间概况 + 下一步命令"""
    pid = ws.get("projectId") or "?"
    identifier = ws.get("projectName") or ""       # 英文标识（如 autotest）
    display = ws.get("displayName") or ""           # 中文名称（如 线上自动化测试项目）
    status = ws.get("status", "")
    owner = ws.get("owner") or ""

    title = f"{identifier}" + (f" ({display})" if display and display != identifier else "")
    print(f"\n{'=' * 60}")
    print(f"  工作空间: {title}")
    print(f"{'=' * 60}")
    print(f"  projectId:  {pid}")
    print(f"  标识:       {identifier}")
    if display and display != identifier:
        print(f"  显示名:     {display}")
    print(f"  状态:       {status}")
    if owner:
        print(f"  Owner:      {owner}")

    print(f"\n{'─' * 60}")
    print(f"下一步")
    print(f"{'─' * 60}")
    print(f"  1. 搜索节点:     search_nodes.py \"关键字\" --project-id {pid}")
    print(f"  2. 搜索表:       search_table.py \"关键字\" --project-id {pid}")
    print(f"  3. 运维概览:     ops_overview.py --project-id {pid}")
    print(f"  4. 治理总览:     dgc_overview.py")
    print(f"  5. 最近变更节点: search_nodes.py --recent --project-id {pid}")
    print(f"  6. 最近新建节点: search_nodes.py --recent --project-id {pid} --by create")


# ── 输出 ──────────────────────────────────────────────────

def _format_size(b):
    """字节数格式化"""
    if b is None:
        return "?"
    try:
        b = float(b)
    except (TypeError, ValueError):
        return str(b)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f} {unit}" if b != int(b) else f"{int(b)} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def _format_ts(ms):
    """毫秒时间戳 → YYYY-MM-DD HH:MM:SS"""
    if not ms:
        return None
    try:
        from datetime import datetime
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return str(ms)


def _print_table_archive(table, pid_hint=None):
    """输出表元信息板块。table 是 _table 字段（含 getDetail 补全后的字段）"""
    name = table.get("name") or "?"
    comment = table.get("comment") or ""
    title = name + (f"  ({comment})" if comment else "")

    print(f"\n{'=' * 60}")
    print(f"📋 表档案: {title}")
    print(f"{'=' * 60}")

    db = table.get("databaseName") or "?"
    print(f"  数据库:           {db}")
    pid = table.get("projectId") or pid_hint
    if pid:
        print(f"  工作空间:         {pid}")

    owner_name = table.get("ownerName") or ""
    owner_base = table.get("ownerBaseId") or ""
    if owner_name:
        suffix = f" ({owner_base})" if owner_base else ""
        print(f"  Owner:            {owner_name}{suffix}")

    et = table.get("entityType") or ""
    partitioned = table.get("partitioned")
    pk = table.get("partitionKeys") or ""
    if et:
        type_str = et
        if partitioned:
            type_str += f"  | 分区表 ({pk})" if pk else "  | 分区表"
        else:
            type_str += "  | 非分区表"
        print(f"  类型:             {type_str}")

    size = table.get("dataSize")
    if size is not None:
        print(f"  数据量:           {_format_size(size)}")

    lc = table.get("lifeCycle")
    if lc:
        print(f"  生命周期:         {lc} 天")

    health = table.get("healthEvaluation") or {}
    if health.get("score") is not None:
        score = health.get("score")
        level = health.get("level", "")
        try:
            print(f"  健康评分:         {float(score):.2f} ({level})")
        except (TypeError, ValueError):
            print(f"  健康评分:         {score} ({level})")

    biz = table.get("bizLine") or ""
    if biz:
        print(f"  业务线:           {biz}")
    labels = table.get("officialLabels") or []
    if labels:
        print(f"  官方标签:         {', '.join(labels)}")

    create_t = _format_ts(table.get("gmtCreate"))
    mod_t = _format_ts(table.get("lastModifyTime") or table.get("gmtModified"))
    ddl_t = _format_ts(table.get("lastDdlTime"))
    access_t = _format_ts(table.get("lastAccessTime"))
    if any([create_t, mod_t, ddl_t, access_t]):
        print(f"\n  时间:")
        if create_t:
            print(f"    创建:           {create_t}")
        if mod_t:
            print(f"    最后修改:       {mod_t}")
        if ddl_t:
            print(f"    最后DDL:        {ddl_t}")
        if access_t:
            print(f"    最后访问:       {access_t}")


def _qn_to_table_id(qn):
    """qualifiedName (type.a.b) → tableId (type:::a::b)"""
    if not qn:
        return None
    parts = qn.split(".")
    if len(parts) < 2:
        return None
    return parts[0] + ":::" + "::".join(parts[1:])


def _print_table_columns_section(client, table):
    """字段板块：从 listColumns 拿全字段，前 20 行展示，区分分区键"""
    table_id = table.get("metaEntityId") or _qn_to_table_id(table.get("qualifiedName"))
    if not table_id:
        return
    try:
        cols = client.load("listColumns", tableId=table_id) or []
    except Exception:
        return
    if not cols:
        return

    # 去重 + 按 position 排序
    seen = set()
    ordered = []
    for c in sorted(cols, key=lambda x: x.get("position") or 999):
        n = c.get("name")
        if n and n not in seen:
            seen.add(n)
            ordered.append(c)

    partition_cols = [c for c in ordered if c.get("partitionKey")]
    data_cols = [c for c in ordered if not c.get("partitionKey")]

    pk_note = f"，分区键 {len(partition_cols)} 个" if partition_cols else ""
    print(f"\n{'─' * 60}")
    print(f"📋 字段（共 {len(ordered)} 个{pk_note}）")
    print(f"{'─' * 60}")
    print(f"  {'#':<4}{'字段名':<28}{'类型':<14}{'注释'}")
    show_limit = 20
    for i, c in enumerate(data_cols[:show_limit], 1):
        name = (c.get("name") or "")[:26]
        typ = (c.get("type") or "")[:12]
        cm = (c.get("comment") or "")[:40]
        print(f"  {i:<4}{name:<28}{typ:<14}{cm}")
    if len(data_cols) > show_limit:
        print(f"  ... 还有 {len(data_cols) - show_limit} 个非分区字段，全表用 query_columns.py")
    if partition_cols:
        pk_names = ", ".join(f"{c.get('name')} ({c.get('type', '')})" for c in partition_cols)
        print(f"  分区键: {pk_names}")


def _print_table_partitions_section(client, table):
    """轻量分区摘要：分区键 + 总数 + 最新 3 个分区。不展开历史趋势。"""
    if not table.get("partitioned"):
        return
    pk = table.get("partitionKeys") or ""

    table_id = table.get("metaEntityId") or _qn_to_table_id(table.get("qualifiedName"))
    total = None
    latest = []
    if table_id:
        api_meta = client.api_index.get("ListPartitions")
        if api_meta:
            # 第 1 页拿 totalCount（pageSize=1）
            try:
                first_page = client._do_request("ListPartitions", api_meta,
                                                tableId=table_id, pageSize=1, pageNumber=1)
                total = (first_page.get("data") or {}).get("totalCount")
            except Exception:
                pass
            # 跳末页拿最新分区（默认 ASC 排序，末页 = 最新）
            # ⚠️ 分页参数必须是 pageNumber 不是 pageNum，后者会被静默忽略
            if total and total > 0:
                page_size = 3
                last_page_num = (total + page_size - 1) // page_size
                try:
                    last_page = client._do_request("ListPartitions", api_meta,
                                                   tableId=table_id, pageSize=page_size,
                                                   pageNumber=last_page_num)
                    latest = (last_page.get("data") or {}).get("list", []) or []
                except Exception:
                    pass

    print(f"\n{'─' * 60}")
    print(f"📋 分区")
    print(f"{'─' * 60}")
    if pk:
        print(f"  分区键:     {pk}")
    if total is not None:
        print(f"  分区总数:   {total}")
    if latest:
        print(f"  最新分区:")
        for p in latest[-3:]:  # 末页最后 3 个
            name = p.get("name", "?")
            mt = _format_ts(p.get("modifyTime"))
            rc = p.get("recordCount")
            ds_size = _format_size(p.get("dataSize")) if p.get("dataSize") else ""
            extras = []
            if rc is not None:
                extras.append(f"{rc:,} 行")
            if ds_size:
                extras.append(ds_size)
            extras_str = f" ({', '.join(extras)})" if extras else ""
            time_str = f"  最后修改 {mt}" if mt else ""
            print(f"    {name}{extras_str}{time_str}")
    print(f"  详细趋势: query_partitions.py \"<db.table>\"")


def _print_profile(profile, project_id, keyword, input_type, deep=False):
    """输出档案卡。表搜索路径命中时优先输出「表档案 + 字段 + 分区 + 产出节点」

    deep=False（默认）: 表路径下节点信息只输出轻量摘要（计数+主节点ID）；
    deep=True: 节点信息含完整调度配置、上下游、同名节点列表。
    """
    node_name = profile.get("node_name") or keyword
    task_id = profile.get("task_id")
    entity_id = profile.get("entity_id")
    output_table = profile.get("output_table")
    owner = profile.get("owner")
    node_type = profile.get("node_type")
    pid = profile.get("project_id") or project_id
    client = profile.get("_client")

    # 来自表搜索路径 → 表档案为主，附字段 + 分区 + 产出节点
    table_info = profile.get("_table") or {}
    has_table = bool(table_info.get("name"))
    if has_table:
        _print_table_archive(table_info, pid_hint=pid)
        if client:
            _print_table_columns_section(client, table_info)
            _print_table_partitions_section(client, table_info)

        # 节点信息：默认轻量，--deep 完整
        if task_id or entity_id:
            if not deep:
                _print_node_section_light(profile, pid)
                _print_next_steps_for_table_only(table_info, pid, with_deep_hint=True,
                                                 keyword=keyword)
                return
            # deep mode: 走完整节点档案
            print(f"\n{'─' * 60}")
            print(f"📋 产出节点（详情，--deep）")
            print(f"{'─' * 60}")
        else:
            # 表存在但没产出节点（DI 等场景），跳过节点板块
            _print_next_steps_for_table_only(table_info, pid)
            return

    # 节点档案板块（节点路径直接到这；表路径 --deep 也到这）
    if not has_table:
        print(f"\n{'=' * 60}")
        print(f"📋 节点档案: {node_name}")
        print(f"{'=' * 60}")
    if task_id:
        print(f"  nodeId(运行态):   {task_id}")
    if entity_id:
        print(f"  entityId(开发态): {entity_id}")
    else:
        print(f"  entityId(开发态): (未找到对应的开发态节点)")
    if output_table:
        print(f"  产出表:           {output_table}")
    output_partition = profile.get("output_partition")
    if output_partition:
        print(f"  分区模式:         {output_partition}")
    # DI 输入源
    input_table = profile.get("input_table")
    input_ds = profile.get("input_datasource")
    if input_table or input_ds:
        src = input_table or ""
        if input_ds:
            src = f"{src} ← {input_ds}" if src else input_ds
        print(f"  输入源:           {src}")
    if owner:
        print(f"  负责人:           {owner}")
    if node_type:
        print(f"  类型:             {node_type}")
    # 表引擎类型（从 _table 或 table_profile 获取）
    table_info = profile.get("_table") or {}
    entity_type = table_info.get("entityType") or profile.get("entity_type")
    if entity_type:
        print(f"  表引擎:           {entity_type}")
    if pid:
        print(f"  工作空间:         {pid}")
    instance_id = profile.get("_instance_id")
    if instance_id:
        print(f"  实例ID:           {instance_id}")

    # 调度配置
    cron = profile.get("cron_express")
    sched_type = profile.get("schedule_type")
    baseline = profile.get("baseline_name")
    res_group = profile.get("res_group")
    priority = profile.get("priority")
    if any([cron, sched_type, baseline]):
        print(f"\n  调度配置:")
        if sched_type:
            cron_str = f" ({cron})" if cron else ""
            print(f"    周期:   {sched_type}{cron_str}")
        if priority is not None:
            print(f"    优先级: {priority}")
        if baseline:
            print(f"    基线:   {baseline}")
        if res_group:
            print(f"    资源组: {res_group}")

    # 上下游依赖
    if task_id and pid:
        _show_dependencies(profile.get("_client"), task_id, pid)

    # 展示同名节点列表（如果有多个）
    all_nodes = profile.get("_all_nodes")
    if all_nodes and len(all_nodes) > 1:
        print(f"\n  同名节点 ({len(all_nodes)} 个):")
        for n in all_nodes[:10]:
            tid = n.get("taskId", "")
            eid = n.get("entityId", "")
            print(f"    {n.get('name', '')} (taskId={tid}, entityId={eid})")

    # 下一步命令
    print(f"\n{'─' * 60}")
    print(f"下一步")
    print(f"{'─' * 60}")
    idx = 1
    # 表操作引导（表搜索路径优先展示）
    if has_table:
        tbl_db = table_info.get("databaseName", "")
        tbl_name = table_info.get("name", "")
        full = f"{tbl_db}.{tbl_name}" if tbl_db else tbl_name
        # 只引导元数据路径（快、无权限风险）。取样 / 画像 是独立意图，用户有需求时独立 prompt 触发
        print(f"  {idx}. 查字段:       query_columns.py \"{full}\"")
        idx += 1
        print(f"  {idx}. 查分区:       query_partitions.py \"{full}\"")
        idx += 1
        print(f"  {idx}. 查血缘:       query_lineage.py \"{full}\"")
        idx += 1
    if task_id and pid:
        print(f"  {idx}. 查运行态代码: find_node_code.py --project-id {pid} --task-id {task_id} --runtime")
        idx += 1
    if entity_id and pid:
        print(f"  {idx}. 查开发态代码: find_node_code.py --project-id {pid} --entity-id {entity_id}")
        idx += 1
    elif task_id and pid and not entity_id:
        print(f"  {idx}. 查开发态代码: find_node_code.py --project-id {pid} --task-id {task_id}")
        idx += 1
    if task_id and pid:
        print(f"  {idx}. 查任务详情: task_detail.py --project-id {pid} --node-id {task_id}")
        idx += 1
    if task_id and pid:
        print(f"  {idx}. 查失败实例: query_instances.py --project-id {pid} --search {task_id} --status failed")
        idx += 1
    if output_table and not has_table:
        # 节点路径有 output_table 时也给「查产出表」入口
        print(f"  {idx}. 查产出表: search_table.py \"{output_table}\"")
        idx += 1
    if instance_id:
        print(f"  {idx}. 查实例日志: log_analyzer.py --task-instance-id {instance_id} --node-id {task_id} --project-id {pid}")
        idx += 1

    # identify.py --deep 的具体能力（拆开列出，agent 才能按需匹配）
    id_arg = f"\"{node_name}\"" if node_name else f"\"{keyword}\""
    pid_arg = f" --project-id {pid}" if pid else ""
    deep_cmd = f"identify.py {id_arg}{pid_arg} --deep"
    print(f"  {idx}. 查健康状态（最近7天成功率、连续失败）: {deep_cmd}")
    idx += 1
    if output_table:
        print(f"  {idx}. 查产出时效（最新分区、分区趋势）: {deep_cmd}")
        idx += 1
        print(f"  {idx}. 查质量规则（DQC 通过/告警/阻塞）: {deep_cmd}")
        idx += 1
    print(f"  {idx}. 查发布历史 + 变更记录 + 版本diff: {deep_cmd}")
    idx += 1
    print(f"  {idx}. 查代码: identify.py {id_arg}{pid_arg} --show-code")
    idx += 1


def _print_node_section_light(profile, pid):
    """轻量节点摘要（默认 identify 表路径）：只显示计数 + 主节点 ID + 名字
    不调度/上下游/_show_dependencies，避免拖慢。
    """
    task_id = profile.get("task_id")
    entity_id = profile.get("entity_id")
    node_name = profile.get("node_name")
    all_nodes = profile.get("_all_nodes") or []
    cnt = max(len(all_nodes), 1 if (task_id or entity_id) else 0)

    if cnt == 0:
        return
    print(f"\n{'─' * 60}")
    print(f"📋 产出节点（{cnt} 个，仅摘要 — 完整信息加 --deep）")
    print(f"{'─' * 60}")
    if node_name:
        print(f"  主节点: {node_name}")
    if task_id:
        print(f"    nodeId(运行态):   {task_id}")
    if entity_id:
        print(f"    entityId(开发态): {entity_id}")
    if cnt > 1 and all_nodes:
        print(f"  另有 {cnt - 1} 个同名节点 (--deep 看全部)")


def _print_next_steps_for_table_only(table, pid, with_deep_hint=False, keyword=None):
    """表场景下的下一步引导（含或不含 --deep 引导）"""
    db = table.get("databaseName", "")
    name = table.get("name", "")
    full = f"{db}.{name}" if db else name
    print(f"\n{'─' * 60}")
    print(f"下一步")
    print(f"{'─' * 60}")
    # 只引导元数据路径。取样 / 画像 是独立意图，用户有需求时独立 prompt 触发
    print(f"  1. 查字段全表:   query_columns.py \"{full}\"")
    print(f"  2. 分区趋势/最新分区: query_partitions.py \"{full}\"")
    print(f"  3. 查血缘:       query_lineage.py \"{full}\"")
    if with_deep_hint:
        kw_arg = f'"{keyword}"' if keyword else f'"{name}"'
        pid_arg = f" --project-id {pid}" if pid else ""
        print(f"  4. 节点详情/调度/上下游: identify.py {kw_arg}{pid_arg} --deep")


# ── 上下游依赖 ────────────────────────────────────────────

def _show_dependencies(client, task_id, project_id):
    """展示运行态节点的上下游依赖"""
    if not client:
        return
    api_meta = client.api_index.get("getNodeListByDepth")
    if not api_meta:
        return

    try:
        parts = []
        for rel, label in [("parent", "上游"), ("child", "下游")]:
            result = client._do_request("getNodeListByDepth", api_meta,
                                        projectId=int(project_id), env="prod",
                                        tenantId=1, nodeId=int(task_id),
                                        depth=1, relation=rel)
            data = result.get("data", [])
            items = data if isinstance(data, list) else (data.get("data", []) if isinstance(data, dict) else [])
            # 排除自身
            others = [n for n in items if n.get("nodeId") != task_id]
            if others:
                parts.append((label, others))

        if not parts:
            return

        print(f"\n  依赖关系:")
        for label, nodes in parts:
            names = [f"{n.get('nodeName', '?')}({n.get('prgTypeName', '')})" for n in nodes[:5]]
            suffix = f" +{len(nodes)-5}个" if len(nodes) > 5 else ""
            print(f"    {label}: {', '.join(names)}{suffix}")
    except Exception:
        pass


# ── 代码引用 ──────────────────────────────────────────────

def _show_code_references(client, profile, keyword):
    """搜索哪些节点的代码中引用了该表"""
    # 确定搜索关键字：产出表名 > 输入关键字
    table_name = profile.get("output_table") or keyword
    if not table_name:
        return
    # 跳过 ID 类输入（纯数字、UUID）
    if table_name.isdigit() or "-" in table_name and len(table_name) > 30:
        return

    try:
        results = client.load("searchTables", keyword=table_name,
                              entityType="datastudio-code", pageSize=20, pageNumber=1)
        if not results:
            return

        # 过滤：名称中包含关键字的才算相关（排除噪音）
        relevant = [r for r in results
                    if table_name.lower() in (r.get("name") or "").lower()]
        if not relevant:
            return

        # 排除自身节点
        node_name = profile.get("node_name") or ""
        others = [r for r in relevant if r.get("name") != node_name]
        if not others:
            return

        print(f"\n🔍 代码引用（{len(others)} 个节点的 SQL 中使用了 {table_name}）")
        for r in others[:10]:
            name = r.get("name", "")
            qn = r.get("qualifiedName", "")
            # qualifiedName 格式: datastudio-code.<nodeId>
            node_id = qn.split(".")[-1] if "." in qn else ""
            suffix = f"  (nodeId={node_id})" if node_id else ""
            print(f"  {name}{suffix}")
    except Exception:
        pass


# ── --deep 深度探查 ───────────────────────────────────────

_STATUS_NAMES = {
    "0": "未运行", "1": "等待调度", "2": "等待中",
    "3": "等待资源", "4": "运行中", "5": "失败",
    "6": "成功", "7": "暂停",
}


def _deep_health(client, project_id, task_id):
    """最近 7 天实例健康状态（生产 + 开发环境）"""
    _deep_health_env(client, project_id, task_id, env="prod", label="生产环境")
    _deep_health_env(client, project_id, task_id, env="dev", label="开发环境")


def _deep_health_env(client, project_id, task_id, env="prod", label="生产环境"):
    """单环境实例健康状态"""
    from datetime import datetime, timedelta
    today = datetime.now().date()
    biz_start = today - timedelta(days=7)
    run_start = biz_start + timedelta(days=1)
    run_end = today + timedelta(days=1)

    try:
        api_meta = client.api_index.get("getInstanceList")
        if not api_meta:
            return
        result = client._do_request("getInstanceList", api_meta,
                                    projectId=project_id, env=env, tenantId=1,
                                    dagType=0, taskTypes=0,
                                    includeRelation="false", withAlarm="false",
                                    slowly="false", withRerun="false",
                                    taskStatuses="", prgTypes="",
                                    searchText=str(task_id),
                                    owner="", resgroupId="",
                                    sortOrder="", sortField="",
                                    alarmTime="", solId="", nodeTag="", bizId="",
                                    connectionRegionId="", connectionType="",
                                    connections="", baseLineId="", priorityList="",
                                    scheIntervalList="", diResGroupIdentifier="",
                                    diSrcType="", diSrcDatasource="",
                                    diDstType="", diDstDatasource="",
                                    flowId="", alarmId="", advanceSort="",
                                    pageNum=1, pageSize=10,
                                    bizdate=f"{biz_start} 00:00:00",
                                    bizBeginHour=f"{run_start} 00:00:00",
                                    bizEndHour=f"{run_end} 23:59:59")
        return_structure = api_meta.get("return_structure", "")
        items = client._parse_return_structure(result, return_structure)
        if not isinstance(items, list):
            items = [items] if items else []
    except Exception:
        return

    if not items:
        print(f"\n📊 健康状态 — {label} (最近 7 天)")
        print(f"  无实例记录")
        return

    success = sum(1 for i in items if str(i.get("status")) == "6")
    failed = sum(1 for i in items if str(i.get("status")) == "5")
    running = sum(1 for i in items if str(i.get("status")) == "4")
    total = len(items)
    rate = f"{success / total * 100:.0f}%" if total > 0 else "-"

    # 连续失败检测
    consecutive = 0
    for i in items:
        if str(i.get("status")) == "5":
            consecutive += 1
        else:
            break

    print(f"\n📊 健康状态 — {label} (最近 7 天)")
    print(f"  成功: {success}  失败: {failed}  运行中: {running}  成功率: {rate}")
    if consecutive >= 2:
        print(f"  ⚠️ 连续失败 {consecutive} 天")

    # 最近失败实例
    failed_items = [i for i in items if str(i.get("status")) == "5"]
    if failed_items:
        f = failed_items[0]
        inst_id = f.get("taskId", "")
        raw_biz = f.get("bizdate", "")
        if isinstance(raw_biz, (int, float)):
            bizdate = datetime.fromtimestamp(raw_biz / 1000).strftime("%Y-%m-%d")
        else:
            bizdate = str(raw_biz)[:10]
        print(f"  最近失败: {bizdate} (instanceId={inst_id})")
        print(f"    → log_analyzer.py --task-instance-id {inst_id} --node-id {task_id} --project-id {project_id}")


def _deep_freshness(client, project_id, output_table):
    """产出表最新分区时效"""
    if not output_table:
        return

    # 需要 searchTables → getDetail → ListPartitions，3 次 API
    # 用 _do_request 单页查询，不触发自动翻页
    try:
        # searchTables（只取第 1 页）
        st_meta = client.api_index.get("searchTables")
        if not st_meta:
            return
        st_result = client._do_request("searchTables", st_meta,
                                       keyword=output_table,
                                       entityType="maxcompute-table",
                                       pageSize=10, pageNumber=1)
        st_rs = st_meta.get("return_structure", "")
        tables = client._parse_return_structure(st_result, st_rs)
        if not tables:
            return
        if not isinstance(tables, list):
            tables = [tables]
        exact = [t for t in tables if t.get("name") == output_table]
        table = exact[0] if exact else tables[0]

        entity_guid = table.get("entityGuid")
        if not entity_guid:
            return

        # getDetail → metaEntityId
        gd_meta = client.api_index.get("getDetail")
        if not gd_meta:
            return
        gd_result = client._do_request("getDetail", gd_meta,
                                       entityType="odps-table",
                                       entityGuid=entity_guid)
        detail = client._parse_return_structure(gd_result, gd_meta.get("return_structure", ""))
        if not isinstance(detail, dict):
            return
        table_id = detail.get("metaEntityId")
        if not table_id:
            return

        # ListPartitions（最新 5 个）
        lp_meta = client.api_index.get("ListPartitions")
        if not lp_meta:
            return
        lp_result = client._do_request("ListPartitions", lp_meta,
                                       tableId=table_id,
                                       pageNumber=1, pageSize=5, order="desc")
        partitions = client._parse_return_structure(lp_result, lp_meta.get("return_structure", ""))
        if not partitions:
            print(f"\n📦 产出时效 ({output_table})")
            print(f"  非分区表或无分区数据")
            return
        if not isinstance(partitions, list):
            partitions = [partitions]

        latest = partitions[0] if partitions else None
        if latest:
            part_name = latest.get("name", "")
            print(f"\n📦 产出时效 ({output_table})")
            print(f"  最新分区: {part_name}")
            if len(partitions) > 1:
                dates = [p.get("name", "") for p in partitions[:5]]
                print(f"  最近 5 个: {', '.join(dates)}")
    except Exception:
        pass


def _deep_quality(client, project_id, output_table):
    """产出表 DQC 规则检查"""
    if not output_table:
        return

    try:
        api_meta = client.api_index.get("listRuleChecks")
        if not api_meta:
            return
        result = client._do_request("listRuleChecks", api_meta,
                                    projectId=project_id,
                                    tableName=output_table,
                                    pageNum=1, pageSize=20)
        code = result.get("code")
        if code not in (None, 0, "0", 200, "200"):
            return
        return_structure = api_meta.get("return_structure", "")
        items = client._parse_return_structure(result, return_structure)
        if not items:
            print(f"\n✅ 质量规则 ({output_table})")
            print(f"  无 DQC 规则")
            return
        if not isinstance(items, list):
            items = [items] if items else []

        total = len(items)
        passed = sum(1 for i in items if str(i.get("checkResult", "")).lower() in ("pass", "passed", "0"))
        warned = sum(1 for i in items if str(i.get("checkResult", "")).lower() in ("warn", "warning", "1"))
        blocked = sum(1 for i in items if str(i.get("checkResult", "")).lower() in ("block", "blocked", "2"))

        print(f"\n{'⚠️' if warned + blocked > 0 else '✅'} 质量规则 ({output_table})")
        print(f"  共 {total} 条规则  |  通过: {passed}  告警: {warned}  阻塞: {blocked}")

        # 展示失败/告警的规则
        failed_rules = [i for i in items
                        if str(i.get("checkResult", "")).lower() not in ("pass", "passed", "0", "")]
        for r in failed_rules[:3]:
            rule_name = r.get("ruleName") or r.get("checkerName") or "未知规则"
            check_result = r.get("checkResultName") or r.get("checkResult") or ""
            print(f"    {check_result}: {rule_name}")

        if warned + blocked > 0:
            print(f"    → dqc_rule_checks.py --project-id {project_id} --table {output_table}")
    except Exception:
        pass


def _deep_changes(client, project_id, entity_id, task_id):
    """开发态变更历史 + 发布历史 + 运行态操作日志"""
    from datetime import datetime

    # ── 开发态变更 + 发布（pageDataSnapshots）──
    dev_total, deploy_total = 0, 0
    if entity_id:
        try:
            api_meta = client.api_index.get("pageDataSnapshots")
            if api_meta:
                # 变更历史
                result = client._do_request("pageDataSnapshots", api_meta,
                                            projectId=int(project_id),
                                            entityUuid=str(entity_id),
                                            entityType="OrcDomain",
                                            typeList="Created,Changed,Renamed",
                                            pageSize=10, pageNum=1,
                                            withoutContent="true")
                if result.get("code") in (None, 0, "0", 200, "200"):
                    data = result.get("data") or {}
                    dev_total = data.get("totalNum", 0)
                    dev_items = data.get("data") or []
                else:
                    dev_items = []

                # 发布历史
                deploy_result = client._do_request("pageDataSnapshots", api_meta,
                                                   projectId=int(project_id),
                                                   entityUuid=str(entity_id),
                                                   entityType="OrcDomain",
                                                   typeList="Deployed,UnDeployed",
                                                   pageSize=10, pageNum=1,
                                                   withoutContent="true")
                if deploy_result.get("code") in (None, 0, "0", 200, "200"):
                    deploy_data = deploy_result.get("data") or {}
                    deploy_total = deploy_data.get("totalNum", 0)
                    deploy_items = deploy_data.get("data") or []
                else:
                    deploy_items = []
            else:
                dev_items, deploy_items = [], []
        except Exception:
            dev_items, deploy_items = [], []
    else:
        dev_items, deploy_items = [], []

    # ── 运行态操作日志（listOpLogs）──
    ops_total = 0
    ops_items = []
    if task_id:
        try:
            ops_meta = client.api_index.get("listOpLogs")
            if ops_meta:
                ops_result = client._do_request("listOpLogs", ops_meta,
                                                projectId=int(project_id),
                                                env="prod", tenantId=1,
                                                nodeId=str(task_id),
                                                projectEnv="prod",
                                                pageSize=10, pageNumber=1)
                ops_data = ops_result.get("data") or {}
                if isinstance(ops_data, dict):
                    ops_total = ops_data.get("count", 0)
                    ops_items = ops_data.get("returnValue") or []
        except Exception:
            pass

    # ── 输出（按 开发态 / 运行态 分区） ──
    parts = []
    if dev_total:
        parts.append(f"{dev_total} 次代码变更")
    if deploy_total:
        parts.append(f"{deploy_total} 次发布")
    if ops_total:
        parts.append(f"{ops_total} 条运维操作")
    summary = ", ".join(parts) if parts else "无记录"
    print(f"\n📝 变更历史 ({summary})")

    _type_labels = {"Created": "创建", "Changed": "修改", "Renamed": "重命名",
                    "Deployed": "发布", "UnDeployed": "下线"}

    def _fmt_timeline(items, dedup=False):
        """格式化时间线，返回 [(ts, desc, who)]"""
        lines = []
        for i in items:
            ts = i.get("_ts", 0)
            lines.append((ts, i.get("_desc", ""), i.get("_who", "")))
        lines.sort(key=lambda x: x[0], reverse=True)
        if not dedup:
            return lines
        # 连续相同操作合并
        result = []
        prev, dup = None, 0
        for ts, desc, who in lines:
            if prev and desc == prev[1] and who == prev[2]:
                dup += 1
            else:
                if prev:
                    s = f" (×{dup + 1})" if dup > 0 else ""
                    result.append((prev[0], prev[1] + s, prev[2]))
                prev = (ts, desc, who)
                dup = 0
        if prev:
            s = f" (×{dup + 1})" if dup > 0 else ""
            result.append((prev[0], prev[1] + s, prev[2]))
        return result

    def _print_section(label, items, dedup=False, limit=5):
        if not items:
            return
        lines = _fmt_timeline(items, dedup=dedup)
        print(f"  {label}:")
        for ts, desc, who in lines[:limit]:
            dt = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M") if ts else "?"
            print(f"    {dt}  {who:<8} {desc}")

    # 开发态变更
    dev_events = []
    for i in dev_items:
        label = _type_labels.get(i.get("type", ""), i.get("type", ""))
        ver = i.get("version", "")
        remark = i.get("submitRemark") or ""
        desc = f"v{ver} {label}"
        if remark:
            desc += f" ({remark[:30]})"
        dev_events.append({"_ts": i.get("gmtCreate", 0),
                           "_desc": desc, "_who": i.get("submitterName", "")})
    _print_section("开发态", dev_events)

    # 运行态-发布（开发环境 → 生产环境）
    deploy_events = []
    for i in deploy_items:
        label = _type_labels.get(i.get("type", ""), i.get("type", ""))
        ver = i.get("version", "")
        deploy_events.append({"_ts": i.get("gmtCreate", 0),
                              "_desc": f"v{ver} {label}", "_who": i.get("submitterName", "")})
    _print_section("发布记录（开发→生产）", deploy_events)

    # 运行态-运维操作（生产环境）
    ops_events = []
    for op in ops_items:
        content = (op.get("content") or "")[:60]
        if "补数据" in content:
            desc = "补数据"
        elif "冻结" in content:
            desc = "冻结任务"
        elif "解冻" in content:
            desc = "解冻任务"
        elif "重跑" in content or "rerun" in content.lower():
            desc = "重跑实例"
        elif "置成功" in content:
            desc = "置成功"
        else:
            desc = content or "操作"
        ops_events.append({"_ts": op.get("opTimeLong", 0),
                           "_desc": desc, "_who": op.get("userName", "")})
    _print_section("运维操作（生产环境）", ops_events, dedup=True)

    if not dev_events and not deploy_events and not ops_events:
        print(f"  (无变更记录)")

    # 开发态版本 diff（最近 2 个版本的内容对比）
    if entity_id and dev_items and len(dev_items) >= 2:
        _deep_version_diff(client, project_id, entity_id, dev_items)


def _deep_version_diff(client, project_id, entity_id, dev_items):
    """对比最近两个开发态版本的内容差异"""
    import json

    api_meta = client.api_index.get("getDataSnapshotByEntity")
    if not api_meta:
        return

    # 取最近的两个版本（dev_items 按时间倒序）
    recent = dev_items[:2]
    if len(recent) < 2:
        return

    specs = {}
    for snap in recent:
        ver = snap.get("version")
        vtype = snap.get("type", "Changed")
        try:
            result = client._do_request("getDataSnapshotByEntity", api_meta,
                                        projectId=int(project_id),
                                        entityUuid=str(entity_id),
                                        entityType="OrcDomain",
                                        type=vtype, version=ver)
            entity = (result.get("data") or {}).get("entity")
            if isinstance(entity, str):
                entity = json.loads(entity)
            if isinstance(entity, dict):
                content = entity.get("content")
                if isinstance(content, str):
                    specs[ver] = json.loads(content)
        except Exception:
            pass

    if len(specs) < 2:
        return

    versions = sorted(specs.keys())
    old_ver, new_ver = versions[-2], versions[-1]
    old_spec, new_spec = specs[old_ver], specs[new_ver]

    # 对比所有顶层字段
    diffs = []
    all_keys = sorted(set(list(old_spec.keys()) + list(new_spec.keys())))
    for k in all_keys:
        old_val = json.dumps(old_spec.get(k), ensure_ascii=False, default=str)
        new_val = json.dumps(new_spec.get(k), ensure_ascii=False, default=str)
        if old_val != new_val:
            diffs.append(k)

    if not diffs:
        return

    from datetime import datetime
    new_snap = [s for s in recent if s.get("version") == new_ver]
    ts = new_snap[0].get("gmtCreate", 0) if new_snap else 0
    dt = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M") if ts else "?"

    print(f"\n🔍 最近一次代码变更 (v{old_ver} → v{new_ver}, {dt})")
    print(f"  变更字段: {', '.join(diffs)}")

    # 对核心字段做语义化 diff
    for k in diffs:
        old_v = old_spec.get(k)
        new_v = new_spec.get(k)

        if k == "steps" and isinstance(old_v, list) and isinstance(new_v, list):
            _diff_steps(old_v, new_v)
        elif k == "setting" and isinstance(old_v, dict) and isinstance(new_v, dict):
            _diff_flat(k, old_v, new_v)
        elif k == "script" and isinstance(old_v, dict) and isinstance(new_v, dict):
            old_code = old_v.get("content", "")
            new_code = new_v.get("content", "")
            if old_code != new_code:
                old_lines = len(old_code.splitlines()) if old_code else 0
                new_lines = len(new_code.splitlines()) if new_code else 0
                print(f"  script: {old_lines} 行 → {new_lines} 行")
        else:
            old_s = json.dumps(old_v, ensure_ascii=False, default=str)
            new_s = json.dumps(new_v, ensure_ascii=False, default=str)
            if len(old_s) < 80 and len(new_s) < 80:
                print(f"  {k}: {old_s} → {new_s}")


def _diff_steps(old_steps, new_steps):
    """对比 DI 同步任务的 steps 差异"""
    import json
    for i, (old_s, new_s) in enumerate(zip(old_steps, new_steps)):
        if json.dumps(old_s, sort_keys=True) == json.dumps(new_s, sort_keys=True):
            continue
        step_type = old_s.get("stepType") or new_s.get("stepType") or f"step[{i}]"
        old_p = old_s.get("parameter", {})
        new_p = new_s.get("parameter", {})

        # 逐字段对比 parameter
        all_pk = sorted(set(list(old_p.keys()) + list(new_p.keys())))
        for pk in all_pk:
            ov = json.dumps(old_p.get(pk), ensure_ascii=False, default=str)
            nv = json.dumps(new_p.get(pk), ensure_ascii=False, default=str)
            if ov != nv:
                # 简化展示
                if pk == "connection" and isinstance(old_p.get(pk), list) and isinstance(new_p.get(pk), list):
                    for j, (oc, nc) in enumerate(zip(old_p[pk], new_p[pk])):
                        if isinstance(oc, dict) and isinstance(nc, dict):
                            for ck in sorted(set(list(oc.keys()) + list(nc.keys()))):
                                if json.dumps(oc.get(ck)) != json.dumps(nc.get(ck)):
                                    print(f"  {step_type}.{pk}[{j}].{ck}: {oc.get(ck)} → {nc.get(ck)}")
                elif len(ov) < 100 and len(nv) < 100:
                    print(f"  {step_type}.{pk}: {ov} → {nv}")
                else:
                    print(f"  {step_type}.{pk}: (已变更, {len(ov)}→{len(nv)} chars)")


def _diff_flat(key, old_d, new_d):
    """对比 flat dict 差异"""
    import json
    all_k = sorted(set(list(old_d.keys()) + list(new_d.keys())))
    for k in all_k:
        ov = json.dumps(old_d.get(k), ensure_ascii=False, default=str)
        nv = json.dumps(new_d.get(k), ensure_ascii=False, default=str)
        if ov != nv:
            print(f"  {key}.{k}: {ov} → {nv}")


def _show_code(client, profile, project_id, dev=False):
    """输出节点代码"""
    pid = profile.get("project_id") or project_id
    task_id = profile.get("task_id")
    entity_id = profile.get("entity_id")
    node_name = profile.get("node_name", "")

    try:
        from find_node_code import get_node_code
    except ImportError:
        # find_node_code 不在当前 path，用 API 直接调
        _show_code_via_api(client, pid, task_id, entity_id, node_name, dev)
        return

    node = {"projectId": str(pid)}
    if task_id:
        node["taskId"] = str(task_id)
    if entity_id:
        node["entityId"] = str(entity_id)

    if dev:
        mode_label = "开发态"
        code, err = get_node_code(client, int(pid), node, runtime=False)
    else:
        mode_label = "运行态"
        code, err = get_node_code(client, int(pid), node, runtime=True, env="prod")

    print(f"\n{'=' * 60}")
    print(f"📄 {mode_label}代码: {node_name}")
    print(f"{'=' * 60}")
    if err:
        print(f"  获取失败: {err}")
        if dev and not entity_id and task_id:
            print(f"  (此节点无对应开发态节点，尝试 --show-code 查看运行态代码)")
    elif code:
        print(code)
    else:
        print("  (无代码)")


def _show_code_via_api(client, project_id, task_id, entity_id, node_name, dev):
    """直接通过 API 获取代码（find_node_code 不可用时的 fallback）"""
    print(f"\n{'=' * 60}")
    mode_label = "开发态" if dev else "运行态"
    print(f"📄 {mode_label}代码: {node_name}")
    print(f"{'=' * 60}")

    try:
        if dev and entity_id:
            result = client.load("getContentByNodeId", projectId=str(project_id),
                                 nodeId=str(entity_id))
            if isinstance(result, dict):
                print(result.get("content", str(result)))
            else:
                print(result or "(无代码)")
        elif task_id:
            result = client.load("getNodeCode", projectId=int(project_id),
                                 env="prod", nodeId=str(task_id))
            if isinstance(result, dict):
                print(result.get("code", str(result)))
            else:
                print(result or "(无代码)")
        else:
            print(f"  缺少必要 ID（entityId={entity_id}, taskId={task_id}）")
    except Exception as e:
        print(f"  获取失败: {e}")


def _print_not_found(keyword, project_id):
    print(f"\n{_TAG} 未找到与 '{keyword}' 匹配的节点或表")
    if project_id:
        print(f"\n→ search_nodes.py \"{keyword}\" --project-id {project_id}")
        print(f"→ search_table.py \"{keyword}\"")
        print(f"→ query_instances.py --project-id {project_id} --search \"{keyword}\" --status failed")
    else:
        print(f"\n→ identify.py \"{keyword}\" --project-id <工作空间 ID>")


# ── 主流程 ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="节点识别工具 — 给任意线索，返回完整节点档案",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("keyword", help="表名、节点名、nodeId、instanceId、entityId（表名支持 'db.name' 自动拆分）")
    parser.add_argument("--project-id", type=int, help="DataWorks workspace ID")
    parser.add_argument("--project-name", help="DataWorks workspace 名称")
    parser.add_argument("--project", help="数据库名（databaseName，如 dataworks_analyze）—— 用于表搜索的精准消歧")
    parser.add_argument("--deep", action="store_true",
                        help="深度探查：上游节点 + 健康状态 + 产出时效 + 质量规则 + 变更历史")
    parser.add_argument("--show-code", action="store_true",
                        help="输出节点代码（默认运行态，加 --dev 查开发态）")
    parser.add_argument("--dev", action="store_true",
                        help="与 --show-code 配合，获取开发态代码（默认运行态）")
    args = parser.parse_args()

    client = BFFClient(quiet=True)
    project_id = None
    if args.project_id or args.project_name:
        try:
            project_id = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)
        except SystemExit:
            pass

    # 尝试从 session 获取 project_id；拿不到不打印 workspace 列表（后续并发搜索会处理）
    if not project_id:
        try:
            project_id = resolve_project_id(
                client, None, None, tag=_TAG, quiet_on_missing=True)
        except SystemExit:
            pass

    # 自动拆分 "db.name" 格式（仅当未显式传 --project 时）
    keyword_arg = args.keyword
    project_db = args.project
    if not project_db and "." in keyword_arg and not keyword_arg.replace(".", "").replace("-", "").isdigit():
        # 排除纯数字（如 IP 形式 ID 或带点的实例 ID）
        parts = keyword_arg.split(".", 1)
        if parts[0] and parts[1] and not parts[0].isdigit():
            project_db = parts[0]
            keyword_arg = parts[1]
            print(f"{_TAG} 自动拆分：database='{project_db}', keyword='{keyword_arg}'")

    input_type, value = _classify_input(keyword_arg)
    telemetry_start("identify.py", module="discovery",
                    keyword=args.keyword, input_type=input_type)

    _INPUT_LABELS = {
        "name": "按名称搜索",
        "node_id": "运行态 nodeId",
        "instance_id": "实例 instanceId",
        "entity_id": "开发态 entityId",
    }
    print(f"{_TAG} 输入: {args.keyword} → {_INPUT_LABELS.get(input_type, input_type)}")

    profile = None

    if input_type == "name":
        # 优先尝试工作空间**精确匹配**：避免 "dataworks_analyze" 被当成节点名，
        # 搜到同名前缀节点（如 check_dataworks_analyze_dev.*）导致返回无关档案
        ws_exact = _try_resolve_workspace(client, value, exact_only=True)
        if ws_exact:
            _print_workspace(ws_exact, value)
            telemetry_end(result={"status": "ok", "input_type": "workspace", "project_id": ws_exact.get("projectId")})
            sys.exit(0)

        profile = _resolve_by_name(client, value, project_id, deep=args.deep, project=project_db)
        # name 解析后补全 output_table（DI 节点等场景）
        if profile and profile.get("task_id") and not profile.get("output_table"):
            pid = profile.get("project_id") or project_id
            if pid:
                from node_profile import resolve as _resolve_profile
                enriched = _resolve_profile(pid, client, task_id=profile["task_id"],
                                            entity_id=profile.get("entity_id"))
                if enriched:
                    for k, v in enriched.items():
                        if v is not None and profile.get(k) is None:
                            profile[k] = v

        # 节点/表都未命中，降级到工作空间模糊匹配
        if not profile:
            ws = _try_resolve_workspace(client, value)
            if ws:
                _print_workspace(ws, value)
                telemetry_end(result={"status": "ok", "input_type": "workspace", "project_id": ws.get("projectId")})
                sys.exit(0)

    elif input_type == "node_id":
        if not project_id:
            print(f"{_TAG} 查询 nodeId 需要 --project-id")
            from bff_client import list_workspaces_for_selection
            list_workspaces_for_selection("identify.py")
            print(f"\n→ identify.py {value} --project-id <工作空间 ID>")
            telemetry_end(result={"status": "need_project_id"})
            sys.exit(1)
        profile = _resolve_by_node_id(client, project_id, value)

    elif input_type == "instance_id":
        if not project_id:
            print(f"{_TAG} 查询 instanceId 需要 --project-id")
            from bff_client import list_workspaces_for_selection
            list_workspaces_for_selection("identify.py")
            print(f"\n→ identify.py {value} --project-id <工作空间 ID>")
            telemetry_end(result={"status": "need_project_id"})
            sys.exit(1)
        profile = _resolve_by_instance_id(client, project_id, value)
        if not profile:
            print(f"{_TAG} 实例查询未命中，尝试当 entityId 解析")
            profile = _resolve_by_entity_id(client, project_id, value)

    elif input_type == "entity_id":
        if not project_id:
            print(f"{_TAG} 查询 entityId 需要 --project-id")
            from bff_client import list_workspaces_for_selection
            list_workspaces_for_selection("identify.py")
            print(f"\n→ identify.py {value} --project-id <工作空间 ID>")
            telemetry_end(result={"status": "need_project_id"})
            sys.exit(1)
        profile = _resolve_by_entity_id(client, project_id, value)

    if profile and (profile.get("task_id") or profile.get("entity_id") or profile.get("node_name")):
        profile["_client"] = client
        _print_profile(profile, project_id, args.keyword, input_type, deep=args.deep)

        # 代码引用：哪些节点的 SQL 中引用了该表
        _show_code_references(client, profile, args.keyword)

        # --show-code 输出代码
        if args.show_code:
            _show_code(client, profile, project_id, dev=args.dev)

        # --deep 深度探查
        if args.deep:
            pid = profile.get("project_id") or project_id
            tid = profile.get("task_id")
            eid = profile.get("entity_id")
            otable = profile.get("output_table")
            if tid and pid:
                _deep_health(client, pid, tid)
            if otable and pid:
                _deep_freshness(client, pid, otable)
                _deep_quality(client, pid, otable)
            if eid or tid:
                _deep_changes(client, pid, eid, tid)

        telemetry_end(result={
            "status": "ok",
            "input_type": input_type,
            "task_id": profile.get("task_id"),
            "entity_id": profile.get("entity_id"),
            "node_name": profile.get("node_name"),
        })
        save_tool_result("identify", {
            "keyword": args.keyword,
            "input_type": input_type,
            "profile": {k: v for k, v in profile.items() if not k.startswith("_")},
        })
    else:
        _print_not_found(args.keyword, project_id)
        telemetry_end(result={"status": "not_found", "input_type": input_type})
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("identify.py", "discovery", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("identify.py", "discovery", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
