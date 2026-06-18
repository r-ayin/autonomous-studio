#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节点部署工具 —— createDeployment(AUTO) + 轮询到完成

三阶段流程：
    # Phase 1：准备发布（输出确认摘要）
    python deploy_node.py --project-id 14255 --uuid <节点uuid>

    # Phase 2：用户确认后 → 发布到开发环境，提示用户去开发环境验证
    python deploy_node.py --confirm

    # Phase 3：开发环境验证通过后 → 继续发布到生产环境
    python deploy_node.py --confirm-prod

    # 查询已有发布流程状态
    python deploy_node.py --project-id 14255 --pipeline-uuid <发布流程uuid>
"""

import argparse
import json
import os
import re
import sys
import time

from bff_client import BFFClient, save_tool_result, add_backlog
from telemetry import telemetry_start, telemetry_end, telemetry_fail


# ─── 常量 ──────────────────────────────────────────────────────

_PENDING_FILE = os.path.join(os.path.expanduser("~"), ".dataworks", "pending_deploy.json")
_TAG = "[deploy]"
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_CORE_DIR = os.path.join(_PROJECT_ROOT, "core")


# ─── 内部 API 调用 ────────────────────────────────────────────

def _api_call(client, api_name, **kwargs):
    """直接调用 API（绕过写操作检查）"""
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


# ─── 检查器阻塞详情 ──────────────────────────────────────────

def _get_blocked_checkers(client, hook_process_id):
    """从 hookProcessId 获取检查器详情，返回 (skippable, has_force_fail)"""
    skippable = []
    has_force_fail = False
    try:
        events = _api_call(client, "listExtensionEventSnapshot",
                           hookProcessId=hook_process_id)
        if not events or not isinstance(events, list):
            return skippable, has_force_fail
        for event in events:
            if event.get("status") != "BLOCKED":
                continue
            biz_id = event.get("extensionBizId", "")
            if not biz_id:
                continue
            try:
                checkers = _api_call(client, "getBizStatus",
                                     extensionBizId=biz_id)
            except Exception:
                continue
            if not isinstance(checkers, list):
                continue
            for c in checkers:
                if c.get("checkResult") != "FAIL":
                    continue
                name = c.get("extensionName") or c.get("extensionCode", "")
                ext_code = c.get("extensionCode", "")
                force = c.get("force", False)
                tag = " [强制]" if force else " [可跳过]"
                hint = _extract_checker_hint(c)
                line = f"{_TAG}   ✗ {name}{tag}"
                if hint:
                    line += f": {hint}"
                print(line)
                if force:
                    has_force_fail = True
                elif biz_id and ext_code:
                    skippable.append({
                        "extensionBizId": biz_id,
                        "extensionCode": ext_code,
                        "name": name,
                    })
    except Exception as e:
        print(f"{_TAG}   查询检查器详情失败: {e}", file=sys.stderr)
    return skippable, has_force_fail


def _skip_checkers(client, skippable):
    """调用 setExtensionPass 跳过非强制检查器"""
    for s in skippable:
        try:
            _api_call(client, "setExtensionPass",
                      extensionBizId=s["extensionBizId"],
                      extensionCode=s["extensionCode"])
            print(f"{_TAG}   ✓ 已跳过: {s['name']}")
        except Exception as e:
            print(f"{_TAG}   ✗ 跳过失败 {s['name']}: {e}", file=sys.stderr)


def _extract_checker_hint(checker):
    """从 checkResultTip 中提取一行提示"""
    raw_tip = checker.get("checkResultTip", "")
    if not raw_tip:
        return ""
    try:
        tip = json.loads(raw_tip).get("hintMsg", "")
    except (json.JSONDecodeError, AttributeError, TypeError):
        tip = raw_tip
    hint_lines = [l.strip() for l in str(tip).strip().split("\n") if l.strip()] if tip else []
    for hl in hint_lines:
        if hl.startswith("Hint Message:"):
            return hl[len("Hint Message:"):].strip()
        if hl.startswith("Suggestion:"):
            return hl[len("Suggestion:"):].strip()
    return hint_lines[0][:120] if hint_lines else ""


# ─── 轮询 ──────────────────────────────────────────────────────

def _poll_pipeline(client, project_id, pipeline_uuid, timeout=300, until_stage=None):
    """轮询 GetPipelineRun 直到终态或指定阶段完成。

    Args:
        until_stage: 若指定（如 "DEV"），则该阶段 Success 时即返回 success，
                     不等待整个 pipeline 到终态。用于开发环境发布场景。
    """
    start = time.time()
    logged_stages = {}

    while True:
        try:
            data = _api_call(client, "GetPipelineRun",
                             projectId=project_id, uuid=pipeline_uuid)
        except Exception as e:
            print(f"{_TAG} 查询发布状态异常: {e}", file=sys.stderr)
            time.sleep(5)
            continue

        if not data or not isinstance(data, dict):
            time.sleep(5)
            continue

        pipeline_status = data.get("status", "")
        stages = data.get("stages") or []

        # 遍历 stages，打印进度 + 检测检查器阻塞
        until_stage_done = False
        for s in stages:
            code = s.get("code", "")
            s_status = s.get("status", "")
            ext_infos = s.get("extInfos") or {}
            check_status = str(ext_infos.get("checkStatus") or "").upper()
            track_key = f"{s_status}|{check_status}"

            if logged_stages.get(code) != track_key:
                prev = logged_stages.get(code)
                logged_stages[code] = track_key

                if s_status in ("Success", "PASSED", "FINISHED"):
                    print(f"{_TAG} ✓ {code}")
                elif s_status in ("Fail", "FAILED", "ERROR"):
                    err = s.get("errorMsg", "")
                    print(f"{_TAG} ✗ {code}" + (f": {err}" if err else ""))
                elif s_status == "Running" and prev is not None:
                    print(f"{_TAG} ⏳ {code} 运行中...")

                # 检查器阻塞 → 尝试自动跳过，强制检查器则退出
                if check_status == "BLOCKED":
                    print(f"{_TAG} ⚠️ {code} 被检查器阻塞")
                    hook_id = ext_infos.get("hookProcessId", "")
                    if hook_id:
                        skippable, has_force = _get_blocked_checkers(client, hook_id)
                        if has_force:
                            print(f"{_TAG} → 强制检查器失败，需修改节点后重新发布")
                            print(f"{_TAG} → 根因分析: PYTHONPATH={_CORE_DIR} python {_SCRIPT_DIR}/analyze_checker_rca.py"
                                  f" --project-id {project_id} --pipeline-uuid {pipeline_uuid}")
                            return "fail", {"stage": code, "error": "强制检查器失败"}
                        if skippable:
                            _skip_checkers(client, skippable)
                            print(f"{_TAG} ⏳ 继续轮询...")
                            logged_stages[code] = None  # 重置以跟踪后续状态变化
                            break  # 跳出 stages 循环，继续外层轮询
                    else:
                        print(f"{_TAG} → 根因分析: PYTHONPATH={_CORE_DIR} python {_SCRIPT_DIR}/analyze_checker_rca.py"
                              f" --project-id {project_id} --pipeline-uuid {pipeline_uuid}")
                        return "fail", {"stage": code, "error": "检查器阻塞"}

            # 检查目标阶段是否已完成
            if until_stage and code == until_stage and s_status in ("Success", "PASSED", "FINISHED"):
                until_stage_done = True

        # 目标阶段完成 → 提前返回
        if until_stage_done:
            return "success", {"elapsed": time.time() - start}

        # 终态判断
        if pipeline_status == "Success":
            return "success", {"elapsed": time.time() - start}

        if pipeline_status in ("Fail", "Termination", "Cancel"):
            # 检查是否有 CHECK 阶段失败
            for s in stages:
                ext = s.get("extInfos") or {}
                is_check_fail = (s.get("status") == "Fail" and
                                 s.get("type") == "Check")
                is_blocked = str(ext.get("checkStatus") or "").upper() == "BLOCKED"
                if is_check_fail or is_blocked:
                    print(f"{_TAG} ⚠️ {s.get('code', '')} 检查器失败")
                    hook_id = ext.get("hookProcessId", "")
                    if hook_id:
                        _get_blocked_checkers(client, hook_id)
                    print(f"{_TAG} → 根因分析: PYTHONPATH={_CORE_DIR} python {_SCRIPT_DIR}/analyze_checker_rca.py"
                          f" --project-id {project_id} --pipeline-uuid {pipeline_uuid}")
                    break

            error = data.get("errorMsg", pipeline_status)
            failed_stage = next(
                (s.get("code") for s in stages if s.get("status") == "Fail"), "")
            return "fail", {"stage": failed_stage, "error": error}

        # 超时
        if time.time() - start > timeout:
            return "timeout", {}

        time.sleep(5)


# ─── Phase 1：准备 ─────────────────────────────────────────────

def _parse_cron_human(cron_expr):
    """将 cron 表达式转为可读描述（秒 分 时 日 月 周）"""
    if not cron_expr:
        return ""
    parts = cron_expr.split()
    if len(parts) < 6:
        return cron_expr
    sec, minute, hour, day, month, weekday = parts[:6]
    # 常见模式
    if day == "*" and month == "*" and weekday == "?":
        if hour != "*" and minute != "*":
            return f"每天 {hour}:{minute.zfill(2)}"
        elif hour == "*" and minute != "*":
            return f"每小时第 {minute} 分钟"
    if weekday not in ("?", "*") and day == "?":
        week_map = {"1": "周日", "2": "周一", "3": "周二", "4": "周三",
                    "5": "周四", "6": "周五", "7": "周六"}
        days = ",".join(week_map.get(d, d) for d in weekday.split(","))
        return f"{days} {hour}:{minute.zfill(2)}"
    return cron_expr


def _parse_spec(node_detail, uuid):
    """解析 GetNode 返回值中的 spec JSON，返回 (spec_obj, node_entry)"""
    spec_raw = node_detail.get("spec")
    spec_obj = {}
    if isinstance(spec_raw, dict):
        spec_obj = spec_raw
    elif isinstance(spec_raw, str) and spec_raw:
        try:
            spec_obj = json.loads(spec_raw)
        except Exception:
            pass
    nodes = ((spec_obj.get("spec") or {}).get("nodes") or []) \
        if isinstance(spec_obj, dict) else []
    node_entry = {}
    for n in nodes:
        if str(n.get("id", "")) == str(uuid):
            node_entry = n
            break
    if not node_entry and nodes:
        node_entry = nodes[0]
    return spec_obj, node_entry


def _format_schedule_info(node_detail, uuid, spec_obj=None, node_entry=None):
    """从 GetNode 返回值中提取并格式化调度配置"""
    name = node_detail.get("name", uuid)
    owner = node_detail.get("ownerName", "")

    if spec_obj is None or node_entry is None:
        spec_obj, node_entry = _parse_spec(node_detail, uuid)

    # 调度触发
    trigger = node_entry.get("trigger") or {}
    trigger_type = trigger.get("type", "")
    cron = trigger.get("cron", "")
    cron_human = _parse_cron_human(cron)

    # 执行策略
    recurrence = node_entry.get("recurrence", "")
    recurrence_map = {"Normal": "正常调度", "Pause": "暂停", "Skip": "空跑", "NoneAuto": "不自动调度"}
    recurrence_label = recurrence_map.get(recurrence, recurrence)

    # 资源组
    res_group = (node_entry.get("runtimeResource") or {}).get("resourceGroup", "")

    # 上游依赖
    inputs = (node_entry.get("inputs") or {}).get("nodeOutputs") or []
    # 也检查 flow.depends
    flow_list = (spec_obj.get("spec") or {}).get("flow") or []
    flow_deps = []
    for flow in flow_list:
        if str(flow.get("nodeId", "")) == str(uuid):
            for dep in flow.get("depends") or []:
                d = dep.get("output") or dep.get("data") or ""
                if d:
                    flow_deps.append(d)

    # 输出
    outputs = (node_entry.get("outputs") or {}).get("nodeOutputs") or []

    # 格式化输出
    lines = []
    lines.append(f"  [{name}] (uuid: {uuid})")
    if owner:
        lines.append(f"    负责人: {owner}")
    if trigger_type:
        sched = f"    调度: {trigger_type}"
        if cron_human:
            sched += f" | {cron_human}"
        if cron:
            sched += f" ({cron})"
        lines.append(sched)
    if recurrence_label:
        lines.append(f"    执行策略: {recurrence_label}")
    if res_group:
        lines.append(f"    资源组: {res_group}")

    dep_items = flow_deps or [i.get("data", "") for i in inputs if i.get("data")]
    if dep_items:
        lines.append(f"    上游依赖({len(dep_items)}):")
        for d in dep_items[:10]:
            lines.append(f"      - {d}")
        if len(dep_items) > 10:
            lines.append(f"      ... 共 {len(dep_items)} 个")

    out_items = [o.get("data", "") for o in outputs if o.get("data")]
    if out_items:
        lines.append(f"    输出({len(out_items)}):")
        for o in out_items[:5]:
            lines.append(f"      - {o}")
        if len(out_items) > 5:
            lines.append(f"      ... 共 {len(out_items)} 个")

    return "\n".join(lines)


# DataWorks 内置系统变量（自动注入，无需在 paraValue 中声明）
# 注意：bizdate 不是内置变量，需要显式声明 bizdate=$[yyyymmdd-1]
_SYSTEM_VARS = frozenset({
    "bdp.system.bizdate", "bdp.system.cyctime",
})

# 常见变量的推荐声明值（用于提示用户）
_VAR_SUGGESTIONS = {
    "bizdate": "$[yyyymmdd-1]",
    "cyctime": "$[yyyymmddhh24miss]",
    "gmtdate": "$[yyyymmdd]",
}


def _extract_sql_variables(sql_content):
    """从 SQL 中提取 ${xxx} 变量引用（排除 ${workspace.xxx} 和 $[time_expr]）"""
    if not sql_content:
        return []
    # ${variable_name} — 排除 ${workspace.xxx}
    refs = re.findall(r'\$\{([^}]+)\}', sql_content)
    return [v for v in refs if not v.startswith("workspace.")]


def _parse_para_value(para_value):
    """从 paraValue 字符串解析已声明的变量名集合。格式: key1=val1 key2=val2"""
    if not para_value or not para_value.strip():
        return set()
    declared = set()
    for pair in para_value.strip().split():
        if "=" in pair:
            declared.add(pair.split("=", 1)[0])
    return declared


def _check_sql_variables(client, node_detail, node_entry, uuid):
    """检查 SQL 中引用的变量是否已在节点调度参数中声明。返回警告行列表"""
    # 1. 获取 SQL 代码
    sql_content = (node_entry.get("script") or {}).get("content", "")
    if not sql_content:
        return []

    # 2. 提取变量引用
    sql_vars = _extract_sql_variables(sql_content)
    if not sql_vars:
        return []

    # 3. 获取已声明的调度参数（两个来源都检查）
    declared = set()

    # 来源 A：spec.script.parameters（开发态声明，优先检查）
    spec_params = (node_entry.get("script") or {}).get("parameters") or []
    for p in spec_params:
        name = p.get("name", "")
        if name:
            declared.add(name)

    # 来源 B：get_task 的 paraValue（运行态声明，作为补充）
    task_id = node_detail.get("taskId")
    if task_id:
        try:
            task_detail = _api_call(client, "get_task", taskId=task_id)
            if isinstance(task_detail, dict):
                declared |= _parse_para_value(task_detail.get("paraValue", ""))
        except Exception:
            pass

    # 4. 找出未声明的变量（排除系统变量）
    undeclared = []
    seen = set()
    for v in sql_vars:
        v_lower = v.lower()
        if v_lower in seen:
            continue
        seen.add(v_lower)
        if v_lower in _SYSTEM_VARS:
            continue
        if v in declared:
            continue
        undeclared.append(v)

    if not undeclared:
        return []

    lines = []
    lines.append(f"    ⚠️ SQL 中引用了未声明的变量:")
    for v in undeclared:
        suggestion = _VAR_SUGGESTIONS.get(v, "")
        if suggestion:
            lines.append(f"      - ${{{v}}}  → 建议声明: {v}={suggestion}")
        else:
            lines.append(f"      - ${{{v}}}")
    if declared:
        lines.append(f"    已声明参数: {' '.join(f'{k}=...' for k in sorted(declared))}")
    else:
        lines.append(f"    当前节点未声明任何调度参数（paraValue 为空）")
    return lines


def prepare_deploy(project_id, uuids, deploy_type="Online", description=None):
    """展示确认摘要（含调度配置），写入 pending 文件"""
    client = BFFClient(quiet=True)

    print(f"{_TAG} ⚠️ 待确认发布操作:")
    print(f"  projectId: {project_id}")
    print(f"  type: {deploy_type}")
    print(f"  节点数: {len(uuids)}")

    # 获取每个节点的调度配置 + 变量检查
    print(f"{_TAG} 调度配置:")
    has_var_warning = False
    task_ids = {}  # uuid → taskId 映射，供后续 smoke_test 使用
    for u in uuids:
        try:
            node_detail = _api_call(client, "GetNode", uuid=u)
            if isinstance(node_detail, dict):
                spec_obj, node_entry = _parse_spec(node_detail, u)
                print(_format_schedule_info(node_detail, u, spec_obj, node_entry))
                # 保存 taskId
                tid = node_detail.get("taskId")
                if tid:
                    task_ids[u] = tid

                # 变量检查
                var_warnings = _check_sql_variables(client, node_detail, node_entry, u)
                if var_warnings:
                    has_var_warning = True
                    for line in var_warnings:
                        print(line)
            else:
                print(f"  - uuid: {u}")
        except Exception as e:
            print(f"  - uuid: {u} (获取详情失败: {e})")

    pending = {
        "project_id": project_id,
        "uuids": uuids,
        "deploy_type": deploy_type,
        "task_ids": task_ids,
        "description": description,
    }
    with open(_PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)

    print(f"  → 用户确认后执行: python deploy_node.py --confirm（先发布到开发环境）")


# ─── Phase 2：确认并发布到开发环境 ────────────────────────────

_PENDING_PROD_FILE = os.path.join(os.path.expanduser("~"), ".dataworks", "pending_deploy_prod.json")

def confirm_and_deploy_dev(timeout=300):
    """createDeployment(AUTO, DEPLOY_NODE_DEV) → 发布到开发环境"""
    pending_path = _PENDING_FILE
    if not os.path.exists(pending_path):
        print(f"{_TAG} 没有待确认的发布操作。请先运行: python deploy_node.py --project-id <id> --uuid <uuid>")
        sys.exit(1)

    with open(pending_path, "r", encoding="utf-8") as f:
        pending = json.load(f)
    os.remove(pending_path)

    project_id = pending["project_id"]
    uuids = pending["uuids"]
    deploy_type = pending.get("deploy_type", "Online")
    task_ids = pending.get("task_ids", {})
    description = pending.get("description")

    client = BFFClient(quiet=True)

    # 创建发布包（AUTO 模式，停在开发环境阶段）
    object_ids_str = json.dumps(uuids)
    print(f"{_TAG} 创建发布包（AUTO 模式 → 开发环境）...")
    deploy_kwargs = dict(projectId=project_id, type=deploy_type, objectIds=object_ids_str,
                         runMode="AUTO", autoRunUntilStage="DEPLOY_NODE_DEV")
    if description:
        deploy_kwargs["description"] = description
    pipeline_uuid = _api_call(client, "createDeployment", **deploy_kwargs)
    if not pipeline_uuid:
        print(f"{_TAG} 创建发布失败：未返回发布包ID")
        sys.exit(1)

    print(f"{_TAG} 发布流程已创建 | uuid={pipeline_uuid}")

    # 轮询到开发环境阶段完成（DEV 阶段 Success 即返回，不等 PROD）
    status, detail = _poll_pipeline(client, project_id, pipeline_uuid, timeout,
                                    until_stage="DEV")
    _output_dev_result(status, detail, project_id, pipeline_uuid, uuids, task_ids, description)


# ─── Phase 3：发布到生产环境 ──────────────────────────────────

def confirm_and_deploy_prod(timeout=300):
    """继续已有发布流程，推进到生产环境"""
    pending_path = _PENDING_PROD_FILE
    if not os.path.exists(pending_path):
        print(f"{_TAG} 没有待发布到生产的流程。请先完成开发环境发布: python deploy_node.py --confirm")
        sys.exit(1)

    with open(pending_path, "r", encoding="utf-8") as f:
        pending = json.load(f)
    os.remove(pending_path)

    project_id = pending["project_id"]
    pipeline_uuid = pending["pipeline_uuid"]
    uuids = pending["uuids"]
    description = pending.get("description")

    client = BFFClient(quiet=True)

    # 继续推进到生产环境（重新 createDeployment AUTO 到 PROD）
    object_ids_str = json.dumps(uuids)
    print(f"{_TAG} 继续发布到生产环境 | uuid={pipeline_uuid}")
    print(f"{_TAG} 创建生产发布包（AUTO 模式 → 生产环境）...")
    deploy_kwargs = dict(projectId=project_id, type=pending.get("deploy_type", "Online"),
                         objectIds=object_ids_str, runMode="AUTO",
                         autoRunUntilStage="DEPLOY_NODE_PROD")
    if description:
        deploy_kwargs["description"] = description
    pipeline_uuid = _api_call(client, "createDeployment", **deploy_kwargs)
    if not pipeline_uuid:
        print(f"{_TAG} 创建生产发布失败：未返回发布包ID")
        sys.exit(1)

    print(f"{_TAG} 生产发布流程已创建 | uuid={pipeline_uuid}")

    # 轮询到生产发布完成
    status, detail = _poll_pipeline(client, project_id, pipeline_uuid, timeout)
    _output_prod_result(status, detail, project_id, pipeline_uuid, uuids)


# ─── 查询模式 ──────────────────────────────────────────────────

def query_pipeline(project_id, pipeline_uuid):
    """查询已有发布流程的状态"""
    client = BFFClient(quiet=True)
    print(f"{_TAG} 查询发布流程 | uuid={pipeline_uuid}")

    data = _api_call(client, "GetPipelineRun",
                     projectId=project_id, uuid=pipeline_uuid)
    if not data:
        print(f"{_TAG} 未找到发布流程: {pipeline_uuid}")
        sys.exit(1)

    status = data.get("status", "未知")
    stages = data.get("stages") or []
    creator = data.get("creatorName", "")

    print(f"{_TAG} 状态: {status} | 创建者: {creator}")
    has_blocked = False
    for s in stages:
        code = s.get("code", "")
        s_status = s.get("status", "")
        error = s.get("errorMsg") or ""
        ext_infos = s.get("extInfos") or {}
        check_status = str(ext_infos.get("checkStatus", "")).upper()

        mark = "✓" if s_status == "Success" else ("✗" if s_status == "Fail" else "⏳")
        line = f"  {mark} {code}: {s_status}"
        if check_status == "BLOCKED":
            line += " [检查器阻塞]"
            has_blocked = True
        if error:
            line += f" ({error})"
        print(line)

        if check_status == "BLOCKED":
            hook_id = ext_infos.get("hookProcessId", "")
            if hook_id:
                skippable, _ = _get_blocked_checkers(client, hook_id)
                if skippable:
                    print(f"{_TAG}   → 跳过可跳过的检查器:")
                    for sk in skippable:
                        print(f"{_TAG}     PYTHONPATH={_CORE_DIR} python {_CORE_DIR}/write_api.py setExtensionPass"
                              f" extensionBizId={sk['extensionBizId']}"
                              f" extensionCode={sk['extensionCode']}")

    if has_blocked:
        print(f"{_TAG} → 根因分析: PYTHONPATH={_CORE_DIR} python {_SCRIPT_DIR}/analyze_checker_rca.py"
              f" --project-id {project_id} --pipeline-uuid {pipeline_uuid}")

    save_tool_result("deploy", {
        "summary": f"发布流程 {pipeline_uuid}: {status}",
        "pipeline_uuid": pipeline_uuid,
        "status": status,
    })


# ─── 结果输出 ──────────────────────────────────────────────────

def _handle_timeout(project_id, pipeline_uuid, uuids, phase):
    """超时时加入异步任务列表"""
    print(f"{_TAG} ⏳ 轮询超时，{phase}可能仍在进行中")

    if "生产" in phase:
        on_success = (f"生产环境发布成功。补数据: PYTHONPATH={_CORE_DIR} python {_PROJECT_ROOT}/modules/task-ops/scripts/backfill_node.py"
                      f" --project-id {project_id} --task-id <taskId> --days 7")
    elif "开发" in phase:
        on_success = (f"开发环境发布成功。下一步: PYTHONPATH={_CORE_DIR} python {_SCRIPT_DIR}/deploy_node.py --confirm-prod"
                      f"（发布到生产环境）")
    else:
        on_success = None

    add_backlog(
        type_name="deploy",
        label=f"发布 uuid={pipeline_uuid}（{phase}）",
        check={
            "api": "GetPipelineRun",
            "params": {"projectId": project_id, "uuid": pipeline_uuid},
            "status_field": "status",
            "terminal": {"Success": "发布成功", "Fail": "发布失败",
                         "Termination": "已终止", "Cancel": "已取消"},
            "pending": {"Running": "运行中"},
        },
        context={"project_id": project_id, "pipeline_uuid": pipeline_uuid,
                 "uuids": uuids},
        on_success=on_success,
    )
    print(f"{_TAG} → 已加入异步任务列表，稍后运行 check_backlogs.py 查看进度")
    save_tool_result("deploy", {
        "summary": f"轮询超时，已加入异步任务列表 | uuid={pipeline_uuid}（{phase}）",
        "status": "timeout",
        "pipeline_uuid": pipeline_uuid,
    })


def _handle_fail(detail, pipeline_uuid):
    """失败时输出错误"""
    stage = detail.get("stage", "")
    error = detail.get("error", "未知错误")
    print(f"{_TAG} ❌ 发布失败 | 阶段: {stage} | 错误: {error}")
    save_tool_result("deploy", {
        "summary": f"发布失败 | 阶段 {stage}: {error}",
        "status": "fail",
        "pipeline_uuid": pipeline_uuid,
        "failed_stage": stage,
        "error": error,
    })
    sys.exit(1)


def _output_dev_result(status, detail, project_id, pipeline_uuid, uuids, task_ids=None, description=None):
    """开发环境发布结果"""
    task_ids = task_ids or {}
    if status == "success":
        elapsed = detail.get("elapsed", 0)
        print(f"{_TAG} ✅ 开发环境发布成功 | 耗时 {elapsed:.0f}s")
        print(f"{_TAG}")
        # 输出冒烟测试命令（如果有 taskId）
        if task_ids:
            for u, tid in task_ids.items():
                print(f"{_TAG} 冒烟测试（验证开发环境）:")
                print(f"    smoke_test.py --project-id {project_id} --task-id {tid}")
        print(f"{_TAG}")
        print(f"{_TAG} 请确认下一步操作:")
        print(f"{_TAG}   1. 先冒烟测试验证开发环境，通过后再执行 --confirm-prod")
        print(f"{_TAG}   2. 直接发布到生产环境: python deploy_node.py --confirm-prod")

        # 保存待生产发布信息
        pending_prod = {
            "project_id": project_id,
            "pipeline_uuid": pipeline_uuid,
            "uuids": uuids,
            "description": description,
        }
        with open(_PENDING_PROD_FILE, "w", encoding="utf-8") as f:
            json.dump(pending_prod, f, ensure_ascii=False, indent=2)

        save_tool_result("deploy", {
            "summary": f"开发环境发布成功 | uuid={pipeline_uuid}",
            "status": "dev_success",
            "pipeline_uuid": pipeline_uuid,
            "project_id": project_id,
            "uuids": uuids,
            "task_ids": task_ids,
            "next_action": "ask_user",
            "options": [
                "冒烟测试验证开发环境，通过后再执行 --confirm-prod",
                "直接发布到生产环境: python deploy_node.py --confirm-prod",
            ],
        })
    elif status == "fail":
        _handle_fail(detail, pipeline_uuid)
    else:
        _handle_timeout(project_id, pipeline_uuid, uuids, "开发环境发布")


def _output_prod_result(status, detail, project_id, pipeline_uuid, uuids):
    """生产环境发布结果"""
    if status == "success":
        elapsed = detail.get("elapsed", 0)
        print(f"{_TAG} ✅ 生产环境发布成功 | 耗时 {elapsed:.0f}s")
        print(f"{_TAG} → 补数据: PYTHONPATH={_CORE_DIR} python {_PROJECT_ROOT}/modules/task-ops/scripts/backfill_node.py"
              f" --project-id {project_id} --task-id <taskId> --days 7"
              f"（taskId 从 GetNode 取 taskId 字段）")
        save_tool_result("deploy", {
            "summary": f"生产环境发布成功 | uuid={pipeline_uuid}",
            "status": "success",
            "pipeline_uuid": pipeline_uuid,
            "project_id": project_id,
            "uuids": uuids,
            "next_action": f"补数据: PYTHONPATH={_CORE_DIR} python {_PROJECT_ROOT}/modules/task-ops/scripts/backfill_node.py"
                           f" --project-id {project_id} --task-id <taskId> --days 7",
        })
    elif status == "fail":
        _handle_fail(detail, pipeline_uuid)
    else:
        _handle_timeout(project_id, pipeline_uuid, uuids, "生产环境发布")


# ─── 入口 ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="DataWorks 节点部署工具（AUTO 模式发布 + 轮询）",
        epilog="三阶段：prepare → --confirm（开发环境）→ --confirm-prod（生产环境）",
    )
    parser.add_argument("--project-id", dest="project_id", type=int,
                        help="工作空间ID")
    parser.add_argument("--uuid", nargs="+",
                        help="节点 uuid（支持多个）")
    parser.add_argument("--type", dest="deploy_type", default="Online",
                        choices=["Online", "Offline"],
                        help="发布动作：Online=上线, Offline=下线（默认 Online）")
    parser.add_argument("--pipeline-uuid", dest="pipeline_uuid",
                        help="已有发布流程 uuid（查询模式）")
    parser.add_argument("--confirm", action="store_true",
                        help="发布到开发环境（Phase 2）")
    parser.add_argument("--confirm-prod", dest="confirm_prod", action="store_true",
                        help="开发环境验证通过后，继续发布到生产环境（Phase 3）")
    parser.add_argument("--timeout", type=int, default=300,
                        help="轮询超时秒数（默认 300）")
    parser.add_argument("--description",
                        help="发布描述（可选，透传到 createDeployment）")

    args = parser.parse_args()

    telemetry_start("deploy_node.py", module="deployment", project_id=args.project_id)

    if args.confirm_prod:
        confirm_and_deploy_prod(timeout=args.timeout)
        telemetry_end(result={"action": "confirm_prod"})
    elif args.confirm:
        confirm_and_deploy_dev(timeout=args.timeout)
        telemetry_end(result={"action": "confirm_dev"})
    elif args.pipeline_uuid:
        if not args.project_id:
            print(f"{_TAG} --pipeline-uuid 模式需要 --project-id")
            sys.exit(1)
        query_pipeline(args.project_id, args.pipeline_uuid)
        telemetry_end(result={"action": "query_pipeline"})
    elif args.uuid:
        if not args.project_id:
            print(f"{_TAG} 需要 --project-id")
            sys.exit(1)
        prepare_deploy(args.project_id, args.uuid, args.deploy_type, args.description)
        telemetry_end(result={"action": "prepare_deploy"})
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("deploy_node.py", "deployment", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("deploy_node.py", "deployment", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
