#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
whoami —— 查询当前 DataWorks 用户身份、所属工作空间及角色

用法:
    python whoami.py                          # 基本信息 + 空间列表（≤3 个空间自动带角色）
    python whoami.py --with-roles             # 基本信息 + 空间列表 + 每个空间角色（N 次 API）
    python whoami.py --project <projectId>    # 基本信息 + 指定空间的角色
    python whoami.py --no-roles               # 仅基本信息 + 空间列表，不拉角色

输出:
    - 基本信息：nickName、accountName、email、baseId、tenant
    - 工作空间列表：projectId + projectName
    - 角色（按开关）：每个空间下当前用户的角色列表
"""

import sys
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from bff_client import BFFClient, save_tool_result
from telemetry import telemetry_start, telemetry_end, telemetry_fail


AUTO_ROLES_THRESHOLD = 3  # 空间数 ≤ 此值时默认自动拉角色


def fetch_current_user(client):
    user = client.load("currentUser")
    # client.load 可能返回 dict 或 list，统一成 dict
    if isinstance(user, list) and user:
        user = user[0]
    return user or {}


def fetch_projects(client):
    return client.load("ListProjects", pageSize=100, pageNumber=1) or []


def fetch_roles_for_project(client, project_id, base_id):
    """查某个空间下当前用户的角色。失败返回 None。"""
    try:
        members = client.load("ListProjectMembers", projectId=project_id) or []
    except Exception:
        return None
    for m in members:
        if str(m.get("userId")) == str(base_id):
            roles = m.get("roles", []) or []
            return [r.get("name") or r.get("code") or "?" for r in roles]
    return []


def fetch_all_roles(client, projects, base_id):
    """并行拉取所有空间的角色，返回 {projectId: [role_name...]}。"""
    result = {}
    with ThreadPoolExecutor(max_workers=min(max(len(projects), 1), 16)) as pool:
        futures = {
            pool.submit(fetch_roles_for_project, client, p.get("projectId"), base_id): p.get("projectId")
            for p in projects
        }
        for f in as_completed(futures):
            pid = futures[f]
            try:
                result[pid] = f.result()
            except Exception:
                result[pid] = None
    return result


def print_report(user, projects, roles_by_pid, roles_mode):
    """
    roles_mode: 'all' | 'single:<pid>' | 'auto' | 'none'
    """
    nick = user.get("nickName") or user.get("displayName") or "未知"
    account = user.get("accountName") or user.get("loginName") or "-"
    email = user.get("email") or "-"
    base_id = user.get("baseId") or user.get("id") or "-"
    tenant = user.get("tenant") or {}
    tenant_name = tenant.get("tenantName") or tenant.get("companyName") or "-" if isinstance(tenant, dict) else "-"

    print()
    print("=" * 64)
    print("  当前 DataWorks 用户")
    print("=" * 64)
    print(f"  👤 昵称       {nick}")
    print(f"  🔑 账号       {account}")
    print(f"  📧 邮箱       {email}")
    print(f"  🆔 baseId     {base_id}")
    print(f"  🏢 租户       {tenant_name}")

    print()
    print("─" * 64)
    print(f"  📋 工作空间    共 {len(projects)} 个")
    if not projects:
        print("     （无）")
    else:
        show_roles = roles_by_pid is not None
        header = f"  {'ID':>8s}  {'名称':<28s}"
        if show_roles:
            header += "  角色"
        print(header)
        print(f"  {'─'*8}  {'─'*28}" + ("  " + "─"*18 if show_roles else ""))
        for p in projects:
            pid = p.get("projectId", "")
            name = (p.get("projectName") or "未知")[:28]
            line = f"  {pid:>8}  {name:<28s}"
            if show_roles:
                rlist = roles_by_pid.get(pid)
                if rlist is None:
                    role_str = "⚠️ 查询失败"
                elif not rlist:
                    role_str = "（无）"
                else:
                    role_str = ", ".join(rlist)
                line += f"  {role_str}"
            print(line)

    # 引导：压缩到一行 —— 元问题"我是谁"后 agent 通常简洁收尾，不强推 follow-up
    print()
    print(f"  💡 深入某空间: workspace_overview.py <projectId> | daily_check.py <projectId>")
    print()


def main():
    parser = argparse.ArgumentParser(description="查询当前 DataWorks 用户身份及工作空间角色")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--with-roles", action="store_true", help="拉取所有空间的角色（N 次 API）")
    group.add_argument("--no-roles", action="store_true", help="不拉角色（即使空间数少）")
    group.add_argument("--project", type=int, metavar="PID", help="只查指定空间的角色")
    args = parser.parse_args()

    telemetry_start("whoami.py", module="workspace")

    client = BFFClient(quiet=True)

    user = fetch_current_user(client)
    base_id = user.get("baseId") or user.get("id")

    projects = fetch_projects(client)

    # 决定角色查询策略
    roles_by_pid = None
    roles_mode = "none"

    if args.no_roles or not base_id:
        roles_mode = "none"
    elif args.project is not None:
        target = [p for p in projects if str(p.get("projectId")) == str(args.project)]
        if not target:
            print(f"\n[warn] projectId={args.project} 不在你的工作空间列表中\n", file=sys.stderr)
            roles_by_pid = {}
        else:
            roles_by_pid = fetch_all_roles(client, target, base_id)
        roles_mode = f"single:{args.project}"
    elif args.with_roles:
        roles_by_pid = fetch_all_roles(client, projects, base_id)
        roles_mode = "all"
    else:
        # 自动：空间数 ≤ 阈值则拉
        if len(projects) <= AUTO_ROLES_THRESHOLD and projects:
            roles_by_pid = fetch_all_roles(client, projects, base_id)
            roles_mode = "auto"
        else:
            roles_mode = "auto-skipped"

    print_report(user, projects, roles_by_pid, roles_mode)

    telemetry_end(result={
        "baseId": base_id,
        "workspace_count": len(projects),
        "roles_mode": roles_mode,
    })
    save_tool_result("whoami", {
        "user": {
            "nickName": user.get("nickName"),
            "accountName": user.get("accountName") or user.get("loginName"),
            "email": user.get("email"),
            "baseId": base_id,
        },
        "workspaces": [
            {
                "projectId": p.get("projectId"),
                "projectName": p.get("projectName"),
                "roles": (roles_by_pid or {}).get(p.get("projectId")),
            }
            for p in projects
        ],
        "roles_mode": roles_mode,
        "summary": f"用户 {user.get('nickName', '-')}，{len(projects)} 个工作空间",
    })


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("whoami.py", "workspace", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("whoami.py", "workspace", 1, error=str(e)[:120])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
