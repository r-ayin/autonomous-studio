#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据管道概览 —— 展示 Source → 同步链路 → Sink 的全景视图

用法:
    python pipeline_overview.py <projectId>
    python pipeline_overview.py 14255

输出:
    - 按 Source → DI 同步 → Sink 展示数据管道
    - 每条管道的同步状态（Running/Failed/Stopped）
    - 未关联 DI 任务的数据源统计
"""

import os
import argparse
from collections import defaultdict

from bff_client import BFFClient, save_tool_result
from telemetry import telemetry_start, telemetry_end, telemetry_fail


def get_datasources(client, project_id):
    """获取全量数据源，返回 {name: {type, id}} 的映射"""
    sources = client.load("ListDataSources", projectId=project_id)
    ds_map = {}
    for s in sources:
        name = s.get("name", "")
        ds_list = s.get("dataSource", [])
        ds_id = ds_list[0].get("id") if ds_list else None
        ds_map[name] = {
            "type": s.get("type", "unknown"),
            "id": ds_id,
            "name": name,
        }
    return ds_map


def get_di_jobs(client, project_id):
    """获取全量 DI 任务，提取 Source-Sink 映射

    ListDIJobs 返回字段：diJobId, jobName, sourceDataSourceType, destinationDataSourceType,
    jobStatus, migrationType, jobType, owner
    注意：ListDIJobs 不含具体数据源名称，只有类型。数据源名称需通过 GetDIJob 获取。
    """
    jobs = client.load("ListDIJobs", projectId=project_id)
    pipelines = []
    for job in jobs:
        pipelines.append({
            "job_id": job.get("diJobId"),
            "name": job.get("jobName", "未知"),
            "state": job.get("jobStatus", "unknown"),
            "src_type": job.get("sourceDataSourceType", "unknown"),
            "dst_type": job.get("destinationDataSourceType", "unknown"),
            "migration_type": job.get("migrationType", ""),
            "job_type": job.get("jobType", ""),
            "owner": job.get("owner", ""),
            "error": job.get("errorMessage", ""),
        })

    return pipelines


def enrich_with_detail(client, project_id, pipelines):
    """尝试通过 GetDIJob 补充具体数据源名称（可选，失败不影响主流程）"""
    for p in pipelines:
        p["src_names"] = []
        p["dst_names"] = []
        try:
            detail = client.load("GetDIJob", projectId=project_id, diJobId=p["job_id"])
            if isinstance(detail, dict):
                # 从 sourceDataSourceSettings / destinationDataSourceSettings 提取
                src_settings = detail.get("sourceDataSourceSettings") or []
                dst_settings = detail.get("destinationDataSourceSettings") or []
                for s in (src_settings if isinstance(src_settings, list) else [src_settings]):
                    if isinstance(s, dict) and s.get("dataSourceName"):
                        p["src_names"].append(s["dataSourceName"])
                for d in (dst_settings if isinstance(dst_settings, list) else [dst_settings]):
                    if isinstance(d, dict) and d.get("dataSourceName"):
                        p["dst_names"].append(d["dataSourceName"])
        except Exception:
            pass  # GetDIJob 失败不影响主流程


def classify_datasources(ds_map, pipelines):
    """将数据源分为：作为 Source、作为 Sink、未关联

    注意：ListDIJobs 只返回数据源类型，不返回具体名称。
    如果有具体名称（通过 GetDIJob 补充），按名称匹配；否则跳过关联统计。
    """
    used_as_source = set()
    used_as_sink = set()

    for p in pipelines:
        for name in p.get("src_names", []):
            used_as_source.add(name)
        for name in p.get("dst_names", []):
            used_as_sink.add(name)

    # 统计涉及的数据源类型（即使没有具体名称）
    src_types = set(p["src_type"] for p in pipelines)
    dst_types = set(p["dst_type"] for p in pipelines)

    unlinked = {}
    for name, info in ds_map.items():
        if name not in used_as_source and name not in used_as_sink:
            unlinked[name] = info

    return used_as_source, used_as_sink, unlinked, src_types, dst_types


def state_icon(state):
    """状态图标"""
    s = (state or "").lower()
    if s in ("running", "finished"):
        return "✅"
    elif s in ("failed",):
        return "❌"
    elif s in ("stopped",):
        return "⏸️"
    elif s in ("initialized",):
        return "🔵"
    return "❓"


def print_pipeline_overview(project_id, ds_map, pipelines, used_src, used_sink, unlinked, src_types, dst_types):
    """输出管道概览"""
    print()
    print(f"{'=' * 70}")
    print(f"  数据管道概览  工作空间: {project_id}")
    print(f"{'=' * 70}")

    if not pipelines:
        print(f"\n  ⚠️ 该工作空间没有 DI 同步任务")
        print(f"  📊 共 {len(ds_map)} 个数据源，均未配置同步链路")
        return

    # 按状态分组统计
    by_state = defaultdict(int)
    for p in pipelines:
        by_state[p["state"]] += 1
    state_summary = " | ".join(f"{state_icon(s)} {s}: {c}" for s, c in sorted(by_state.items()))
    print(f"\n  🔄 DI 同步任务: {len(pipelines)} 个  ({state_summary})")

    # 按 Source 分组展示管道
    print(f"\n{'─' * 70}")
    print(f"  📥 Source → 🔄 同步 → 📤 Sink")
    print(f"{'─' * 70}")

    # 按 src_type → dst_type 分组
    by_link = defaultdict(list)
    for p in pipelines:
        src_label = p["src_type"]
        dst_label = p["dst_type"]
        # 如果有具体数据源名称，附上
        if p.get("src_names"):
            src_label += f" ({', '.join(p['src_names'])})"
        if p.get("dst_names"):
            dst_label += f" ({', '.join(p['dst_names'])})"
        link_key = f"{src_label} → {dst_label}"
        by_link[link_key].append(p)

    for link_key in sorted(by_link.keys()):
        group = by_link[link_key]
        print(f"\n  📥 {link_key}")
        for p in group:
            icon = state_icon(p["state"])
            extra = f"  [{p['migration_type']}]" if p.get("migration_type") else ""
            print(f"    └─ {icon} {p['name']}{extra}  ({p['state']})")
            if p["error"]:
                print(f"       ⚠️ {p['error'][:80]}")

    # 异常管道汇总
    failed = [p for p in pipelines if (p["state"] or "").lower() == "failed"]
    if failed:
        print(f"\n{'─' * 70}")
        print(f"  ❌ 异常管道 ({len(failed)} 个)")
        print(f"{'─' * 70}")
        for p in failed:
            print(f"    {p['name']}: {p['src_type']} → {p['dst_type']}  (owner: {p.get('owner', '未知')})")
            if p["error"]:
                print(f"      原因: {p['error'][:100]}")

    # 未关联数据源
    print(f"\n{'─' * 70}")
    print(f"  📊 数据源关联统计")
    print(f"{'─' * 70}")
    print(f"    作为 Source: {len(used_src)} 个数据源")
    print(f"    作为 Sink:   {len(used_sink)} 个数据源")
    print(f"    未关联 DI:   {len(unlinked)} 个数据源（共 {len(ds_map)} 个）")

    if unlinked:
        # 按类型分组
        unlinked_by_type = defaultdict(int)
        for info in unlinked.values():
            unlinked_by_type[info["type"]] += 1
        top_types = sorted(unlinked_by_type.items(), key=lambda x: -x[1])[:5]
        for t, count in top_types:
            print(f"      {t:15s}  {count:>4d} 个")

    # 引导
    print(f"\n{'=' * 70}")
    print(f"  💡 你可以继续问我：")
    if failed:
        print(f"     - \"帮我看看 {failed[0]['name']} 为什么失败了\"")
    print(f"     - \"从 xxx 同步数据到 yyy\"")
    print(f"     - \"查看某个 DI 任务的详情\"")
    print(f"{'=' * 70}")
    print()


def main():
    parser = argparse.ArgumentParser(description="数据管道概览")
    parser.add_argument("projectId", type=int, help="工作空间 ID")
    parser.add_argument("--detail", action="store_true",
                        help="补充具体数据源名称（需逐个查询 DI 任务详情，较慢）")
    args = parser.parse_args()

    telemetry_start("pipeline_overview.py", module="workspace", projectId=args.projectId)

    client = BFFClient(quiet=True)

    print(f"\n正在分析工作空间 {args.projectId} 的数据管道 ...")

    ds_map = get_datasources(client, args.projectId)
    pipelines = get_di_jobs(client, args.projectId)

    if args.detail and pipelines:
        print(f"  正在补充数据源名称（{len(pipelines)} 个任务）...")
        enrich_with_detail(client, args.projectId, pipelines)

    used_src, used_sink, unlinked, src_types, dst_types = classify_datasources(ds_map, pipelines)

    print_pipeline_overview(args.projectId, ds_map, pipelines, used_src, used_sink, unlinked, src_types, dst_types)

    telemetry_end(result={"pipeline_count": len(pipelines)})
    # 结构化结果输出
    failed = [p for p in pipelines if (p.get("state") or "").lower() == "failed"]
    save_tool_result("pipeline", {
        "projectId": args.projectId,
        "total_pipelines": len(pipelines),
        "failed_pipelines": failed,
        "datasource_count": len(ds_map),
        "unlinked_count": len(unlinked),
        "summary": f"{len(pipelines)} 条管道, {len(failed)} 条失败",
    })


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("pipeline_overview.py", "workspace", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("pipeline_overview.py", "workspace", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
