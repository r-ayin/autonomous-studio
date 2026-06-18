#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作空间概览 —— 快速了解 DataWorks 工作空间的资源和状态

用法:
    python workspace_overview.py              # 全部工作空间概览
    python workspace_overview.py <projectId>  # 具体工作空间详情
    python workspace_overview.py 14255

输出:
    无参数：列出所有工作空间 + 每个空间的轻量摘要
    有参数：当前用户、数据源统计、今日任务状态、DI 任务统计
"""

import os
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from bff_client import BFFClient, save_tool_result
from telemetry import telemetry_start, telemetry_end, telemetry_fail


# ─── 全部工作空间概览 ────────────────────────────────────────────


def get_all_projects(client):
    """获取全量工作空间列表"""
    return client.load("ListProjects", pageSize=100, pageNumber=1)


def get_workspace_summary(client, project_id):
    """获取单个工作空间的轻量摘要（3 次 API 调用：数据源计数、今日失败数、DI 任务数）"""
    summary = {"ds_count": "-", "failed_today": "-", "di_count": "-"}

    # 数据源总数（用 pageSize=1 只取 totalCount）
    try:
        result = client.call_raw("ListDataSources", projectId=project_id, pageSize=1, pageNumber=1)
        if client.is_success(result):
            data = result.get("data", {})
            summary["ds_count"] = data.get("totalCount", 0)
    except Exception:
        pass

    # 今日失败实例数
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        result = client.call_raw(
            "listTaskInstances",
            projectId=str(project_id),
            status="5",
            startRunTimeFrom=f"{today} 00:00:00",
            startRunTimeTo=f"{today} 23:59:59",
            pageSize="1",
            pageStart="0",
        )
        if client.is_success(result):
            data = result.get("data", {})
            summary["failed_today"] = data.get("totalCount", 0)
    except Exception:
        pass

    # DI 任务数（用 pageSize=1 只取 totalCount）
    try:
        result = client.call_raw("ListDIJobs", projectId=project_id, pageSize=1, pageNumber=1)
        if client.is_success(result):
            data = result.get("data", {})
            # ListDIJobs 返回的分页结构可能在 data.pagingInfo.totalCount
            paging = data.get("pagingInfo", {})
            summary["di_count"] = paging.get("totalCount", data.get("totalCount", 0))
    except Exception:
        pass

    return summary


def print_all_workspaces(user, projects):
    """输出全部工作空间概览"""
    today = datetime.now().strftime("%Y-%m-%d")

    print()
    print(f"{'=' * 72}")
    print(f"  DataWorks 工作空间全貌  {today}")
    print(f"{'=' * 72}")
    print(f"\n  👤 当前用户    {user['nickName']} (baseId: {user['baseId']})")
    print(f"  📋 工作空间    共 {len(projects)} 个")

    print(f"\n{'─' * 72}")
    # 表头
    print(f"  {'ID':>8s}  {'名称':<20s}  {'数据源':>6s}  {'今日失败':>8s}  {'DI任务':>6s}")
    print(f"  {'─'*8}  {'─'*20}  {'─'*6}  {'─'*8}  {'─'*6}")

    has_failed = False
    for p in projects:
        pid = p.get("projectId", "")
        name = p.get("projectName", "未知")
        # 兼容不同字段名：projectStatus / status / projectStatusCode
        status = p.get("projectStatus") or p.get("status") or p.get("projectStatusCode") or ""
        status = str(status)
        s = p.get("_summary", {})

        ds_str = str(s.get("ds_count", "-"))
        failed_str = str(s.get("failed_today", "-"))
        di_str = str(s.get("di_count", "-"))

        # 状态标记
        failed_count = s.get("failed_today", 0)
        if isinstance(failed_count, int) and failed_count > 0:
            has_failed = True
            failed_str = f"❌ {failed_count}"

        # 状态图标：兼容字符串和数字（0/Available = 正常）
        status_lower = status.lower()
        if status_lower in ("available", "0", "normal", "enabled"):
            status_icon = "✅"
        elif status and status_lower not in ("", "unknown"):
            status_icon = "⚠️"
        else:
            status_icon = "·"

        # 截断名称到 20 字符
        display_name = name[:20] if len(name) <= 20 else name[:18] + ".."
        print(f"  {pid:>8}  {display_name:<20s}  {ds_str:>6s}  {failed_str:>8s}  {di_str:>6s}  {status_icon}")

    # 引导
    print(f"\n{'=' * 72}")
    print(f"  💡 下一步：")
    print(f"     → python workspace_overview.py <projectId>  查看具体工作空间详情")
    if has_failed:
        print(f"     → 有工作空间存在失败任务，建议先排查")
    print(f"{'=' * 72}")
    print()


# ─── 具体工作空间详情 ────────────────────────────────────────────


def get_user_info(client):
    """获取当前用户"""
    try:
        user = client.load("currentUser")
        return {
            "baseId": user.get("baseId", "未知"),
            "nickName": user.get("nickName", "未知"),
        }
    except Exception as e:
        return {"baseId": "获取失败", "nickName": str(e)}


def get_project_info(client, project_id):
    """获取工作空间信息"""
    try:
        projects = client.load("ListProjects", pageSize=100, pageNumber=1)
        for p in projects:
            if str(p.get("projectId")) == str(project_id):
                return {
                    "name": p.get("projectName", "未知"),
                    "description": p.get("projectDescription", ""),
                    "status": p.get("projectStatus", "未知"),
                }
        return {"name": f"projectId={project_id}", "description": "（未在你的项目列表中找到）", "status": "未知"}
    except Exception as e:
        return {"name": f"projectId={project_id}", "description": str(e), "status": "获取失败"}


def get_datasource_stats(client, project_id):
    """获取数据源统计"""
    try:
        sources = client.load("ListDataSources", projectId=project_id)
        total = len(sources)

        # 按类型分组
        by_type = {}
        for s in sources:
            t = s.get("type", "unknown")
            by_type.setdefault(t, []).append(s.get("name", ""))

        # 按数量排序取 Top 5
        sorted_types = sorted(by_type.items(), key=lambda x: -len(x[1]))
        top_types = sorted_types[:5]
        rest_count = sum(len(v) for _, v in sorted_types[5:])

        return {"total": total, "top_types": top_types, "rest_count": rest_count}
    except Exception as e:
        return {"total": 0, "top_types": [], "rest_count": 0, "error": str(e)}


def get_task_instance_stats(client, project_id):
    """获取今日调度任务实例统计（只取摘要，不全量翻页）"""
    # status: 4=运行中, 5=失败, 6=成功
    stats = {"success": 0, "failed": 0, "running": 0, "error": None}

    today = datetime.now().strftime("%Y-%m-%d")
    time_from = f"{today} 00:00:00"
    time_to = f"{today} 23:59:59"

    try:
        for status_code, key in [(6, "success"), (5, "failed"), (4, "running")]:
            result = client.call_raw(
                "listTaskInstances",
                projectId=str(project_id),
                status=str(status_code),
                startRunTimeFrom=time_from,
                startRunTimeTo=time_to,
                pageSize="1",
                pageStart="0",
            )
            if client.is_success(result):
                data = result.get("data", {})
                stats[key] = data.get("totalCount", 0)
    except Exception as e:
        stats["error"] = str(e)

    return stats


def get_di_job_stats(client, project_id):
    """获取 DI 同步任务统计"""
    try:
        jobs = client.load("ListDIJobs", projectId=project_id)
        total = len(jobs)

        # 按 jobStatus 分组
        by_status = {}
        for j in jobs:
            s = j.get("jobStatus", "unknown")
            by_status.setdefault(s, 0)
            by_status[s] += 1

        return {"total": total, "by_status": by_status}
    except Exception as e:
        return {"total": 0, "by_status": {}, "error": str(e)}


def print_overview(project_id, user, project, ds, tasks, di):
    """输出概览"""
    today = datetime.now().strftime("%Y-%m-%d")

    print()
    print(f"{'=' * 60}")
    print(f"  DataWorks 工作空间概览  {today}")
    print(f"{'=' * 60}")

    # 用户 & 工作空间
    print(f"\n  👤 当前用户    {user['nickName']} (baseId: {user['baseId']})")
    print(f"  🏠 工作空间    {project['name']} (projectId: {project_id})")
    if project.get("description"):
        print(f"                 {project['description'][:60]}")

    # 数据源
    print(f"\n{'─' * 60}")
    print(f"  📊 数据源      共 {ds['total']} 个")
    if ds.get("error"):
        print(f"                 ⚠️ {ds['error']}")
    elif ds["top_types"]:
        for type_name, names in ds["top_types"]:
            sample = ", ".join(names[:3])
            more = f" ... +{len(names) - 3}" if len(names) > 3 else ""
            print(f"       {type_name:15s}  {len(names):>4d} 个    {sample}{more}")
        if ds["rest_count"]:
            print(f"       {'其他':15s}  {ds['rest_count']:>4d} 个")

    # 调度任务
    print(f"\n{'─' * 60}")
    if tasks.get("error"):
        print(f"  ⚙️ 今日任务    ⚠️ {tasks['error']}")
    else:
        total = tasks["success"] + tasks["failed"] + tasks["running"]
        print(f"  ⚙️ 今日任务    共 {total} 个实例")
        parts = []
        if tasks["success"]:
            parts.append(f"✅ {tasks['success']} 成功")
        if tasks["failed"]:
            parts.append(f"❌ {tasks['failed']} 失败")
        if tasks["running"]:
            parts.append(f"🔄 {tasks['running']} 运行中")
        if parts:
            print(f"                 {' | '.join(parts)}")
        if tasks["failed"] > 0:
            print(f"\n  💡 查看失败详情: client.load(\"listTaskInstances\", projectId=\"{project_id}\", status=\"5\")")

    # DI 同步任务
    print(f"\n{'─' * 60}")
    if di.get("error"):
        print(f"  🔄 数据集成    ⚠️ {di['error']}")
    else:
        print(f"  🔄 数据集成    共 {di['total']} 个 DI 任务")
        if di["by_status"]:
            parts = [f"{k}: {v}" for k, v in sorted(di["by_status"].items())]
            print(f"                 {', '.join(parts)}")
        failed_count = di["by_status"].get("Failed", 0)
        if failed_count:
            print(f"                 ⚠️ {failed_count} 个任务失败！")

    # 提示
    print(f"\n{'=' * 60}")
    print(f"  💡 下一步：")
    if di.get("total", 0) > 0:
        print(f"     → 运行 python pipeline_overview.py {project_id} 查看数据管道详情（Source → 同步 → Sink）")
    print(f"     - \"查一下 xxx 数据源\"")
    print(f"     - \"今天有哪些任务失败了\"")
    print(f"     - \"从 A 同步数据到 B\"")
    print(f"     - \"查表 xxx 的分区\"")
    print(f"{'=' * 60}")
    print()


# ─── main ────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="DataWorks 工作空间概览")
    parser.add_argument("projectId", type=int, nargs="?", default=None,
                        help="工作空间 ID（不传则展示全部工作空间概览）")
    args = parser.parse_args()

    telemetry_start("workspace_overview.py", module="workspace", projectId=args.projectId)

    client = BFFClient(quiet=True)
    user = get_user_info(client)

    if args.projectId is None:
        # ── 全部工作空间概览（并行采集） ──
        print(f"\n正在扫描全部工作空间 ...")
        projects = get_all_projects(client)
        print(f"  找到 {len(projects)} 个工作空间，正在并行采集摘要 ...")

        # call_raw 是无状态 HTTP 调用，共享一个 client 即可
        def fetch_summary(project):
            pid = project.get("projectId")
            if pid:
                project["_summary"] = get_workspace_summary(client, pid)

        with ThreadPoolExecutor(max_workers=min(len(projects), 30)) as pool:
            futures = [pool.submit(fetch_summary, p) for p in projects]
            for f in as_completed(futures):
                f.result()

        print_all_workspaces(user, projects)

        telemetry_end(result={"workspace_count": len(projects)})
        # 结构化结果输出
        save_tool_result("workspace", {
            "workspaces": [{
                "projectId": p.get("projectId"),
                "name": p.get("projectName"),
                "summary": p.get("_summary", {}),
            } for p in projects],
            "summary": f"{len(projects)} 个工作空间",
        })
    else:
        # ── 具体工作空间详情（并行采集） ──
        # call_raw() 不写 DuckDB，共享一个 client 即可
        print(f"\n正在扫描工作空间 {args.projectId} ...")
        pid = args.projectId
        with ThreadPoolExecutor(max_workers=4) as pool:
            f_project = pool.submit(get_project_info, client, pid)
            f_ds = pool.submit(get_datasource_stats, client, pid)
            f_tasks = pool.submit(get_task_instance_stats, client, pid)
            f_di = pool.submit(get_di_job_stats, client, pid)
        project_result = f_project.result()
        ds_result = f_ds.result()
        tasks_result = f_tasks.result()
        di_result = f_di.result()
        print_overview(pid, user, project_result, ds_result, tasks_result, di_result)

        telemetry_end(result={"projectId": pid})
        # 结构化结果输出
        save_tool_result("workspace", {
            "projectId": pid,
            "project": project_result,
            "datasources": ds_result,
            "tasks": tasks_result,
            "di_jobs": di_result,
            "summary": f"工作空间 {pid} 详情",
        })


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("workspace_overview.py", "workspace", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("workspace_overview.py", "workspace", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
