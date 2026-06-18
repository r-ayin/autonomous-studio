#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发布检查器根因分析工具 —— 解析调度依赖一致性检查失败原因

用法:
    python analyze_checker_rca.py --project-id 23304 --uuid 6965880077658415685
    python analyze_checker_rca.py --project-id 23304 --pipeline-uuid 3a4ffba0-bb53-48c5-b5b4-1f1552184eff

功能:
    1. 从节点 uuid 或 pipeline uuid 定位目标节点与失败检查器
    2. 优先获取运行态代码，必要时降级到开发态代码
    3. 调用 code_parse 解析代码输入/输出依赖
    4. 提取节点当前声明的调度上游
    5. 输出缺失依赖、根因与建议动作
"""

import argparse
import json
import os
import re
import sys

from bff_client import BFFClient, save_tool_result

# find_node_code 在 node-management 模块，确保可导入
_script_dir = os.path.dirname(os.path.abspath(__file__))
_node_mgmt_dir = os.path.join(_script_dir, "..", "..", "node-management", "scripts")
if os.path.isdir(_node_mgmt_dir) and _node_mgmt_dir not in sys.path:
    sys.path.insert(0, _node_mgmt_dir)
from find_node_code import get_node_code
from telemetry import telemetry_start, telemetry_end, telemetry_fail


_CHECKER_CODE = "datastudio5_dependency_consistency_checker"
_CHECKER_NAME = "调度依赖一致性检查"


def _api_call(client, api_name, **kwargs):
    api_meta = client.api_index.get(api_name)
    if not api_meta:
        raise ValueError(f"未找到 API: {api_name}")
    result = client._do_request(api_name, api_meta, **kwargs)
    code = result.get("code")
    if code not in (None, 0, "0", 200, "200"):
        msg = result.get("message", "")
        raise RuntimeError(f"{api_name} 失败: code={code}, message={msg}")
    return client._parse_return_structure(result, api_meta.get("return_structure", ""))


def _parse_tip(checker):
    raw_tip = checker.get("checkResultTip")
    if not raw_tip:
        return ""
    if isinstance(raw_tip, dict):
        return raw_tip.get("hintMsg", "") or ""
    try:
        parsed = json.loads(raw_tip)
        if isinstance(parsed, dict):
            return parsed.get("hintMsg", "") or raw_tip
    except Exception:
        pass
    return str(raw_tip)


def _extract_missing_from_tip(tip):
    if not tip:
        return []
    patterns = [
        r"代码中依赖的输出\s+([\w.]+)\s+在调度依赖上游中不存在",
        r"依赖的输出\s+([\w.]+)\s+在调度依赖上游中不存在",
        r"输出\s+([\w.]+)\s+在调度依赖上游中不存在",
    ]
    found = []
    for pattern in patterns:
        found.extend(re.findall(pattern, tip))
    return list(dict.fromkeys(found))


def _normalize_dep(value):
    if not value:
        return ""
    value = str(value).strip().strip("`").strip()
    value = re.sub(r"\s+", "", value)
    return value.lower()


def _unique_keep_order(values):
    seen = set()
    out = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _extract_node_spec(node_detail):
    spec_raw = node_detail.get("spec")
    if not spec_raw:
        return {}
    if isinstance(spec_raw, dict):
        return spec_raw
    try:
        return json.loads(spec_raw)
    except Exception:
        return {}


def _extract_node_entry(spec_obj, node_uuid):
    nodes = ((spec_obj.get("spec") or {}).get("nodes") or []) if isinstance(spec_obj, dict) else []
    for node in nodes:
        if str(node.get("id", "")) == str(node_uuid):
            return node
    return nodes[0] if nodes else {}


def _extract_declared_dependencies(spec_obj, node_uuid):
    flow_list = ((spec_obj.get("spec") or {}).get("flow") or []) if isinstance(spec_obj, dict) else []
    raw = []
    for flow in flow_list:
        if str(flow.get("nodeId", "")) != str(node_uuid):
            continue
        for dep in flow.get("depends") or []:
            output = dep.get("output") or dep.get("data") or dep.get("refTableName") or dep.get("str")
            if output:
                raw.append(str(output))
    raw = _unique_keep_order(raw)
    normalized = {_normalize_dep(v): v for v in raw if _normalize_dep(v)}
    return raw, normalized


def _extract_schedule_connection(project_id, node_entry, checker_snapshot, client):
    datasource = node_entry.get("datasource") or {}
    name = datasource.get("name") or ""
    dtype = datasource.get("type") or ""

    snapshot_file = (((checker_snapshot or {}).get("data") or {}).get("dataSnapshot") or {}).get("fileVersion") or {}
    snapshot_node = snapshot_file.get("nodeDef") or {}
    snapshot_file_info = snapshot_file.get("file") or {}
    conn_name = snapshot_file_info.get("connName") or name
    if not name:
        name = conn_name
    if not dtype:
        dtype = snapshot_node.get("datasource", {}).get("type", "")

    conn_id = None
    try:
        datasources = client.load("ListDataSources", projectId=int(project_id))
        if isinstance(datasources, list):
            for ds in datasources:
                ds_name = str(ds.get("name") or ds.get("dataSourceName") or "")
                ds_type = str(ds.get("type") or ds.get("dataSourceType") or "")
                if name and ds_name != name:
                    continue
                if dtype and ds_type and ds_type.lower() != dtype.lower():
                    continue
                conn_id = ds.get("id")
                if conn_id:
                    break
    except Exception as e:
        print(f"[checker_rca] 查找数据源连接失败: {e}", file=sys.stderr)

    result = {}
    if conn_id is not None:
        result["id"] = str(conn_id)
    if name:
        result["name"] = name
    if dtype:
        result["type"] = dtype
    return result


def _extract_snapshot_dependencies(checker_snapshot):
    snapshot_node = ((((checker_snapshot or {}).get("data") or {}).get("dataSnapshot") or {}).get("fileVersion") or {}).get("nodeDef") or {}
    inputs = snapshot_node.get("inputList") or []
    outputs = snapshot_node.get("outputList") or []

    def collect(items):
        values = []
        for item in items:
            if not isinstance(item, dict):
                continue
            value = item.get("refTableName") or item.get("str") or item.get("data")
            if value:
                values.append(str(value))
        return _unique_keep_order(values)

    return {
        "inputs": collect(inputs),
        "outputs": collect(outputs),
    }


def _collect_dep_values(items):
    values = []
    for item in items or []:
        if isinstance(item, dict):
            dep = item.get("refTableName") or item.get("output") or item.get("str") or item.get("data") or item.get("name")
            if dep:
                values.append(str(dep))
        elif isinstance(item, str):
            values.append(item)
    return _unique_keep_order(values)


def _extract_parse_dependencies(parse_result):
    top_inputs = _collect_dep_values((parse_result or {}).get("input") if isinstance(parse_result, dict) else [])
    top_outputs = _collect_dep_values((parse_result or {}).get("output") if isinstance(parse_result, dict) else [])

    diff_prod = ((parse_result or {}).get("diff") or {}).get("prod") if isinstance(parse_result, dict) else {}
    diff_draft = ((parse_result or {}).get("diff") or {}).get("draft") if isinstance(parse_result, dict) else {}

    diff_inputs = _collect_dep_values((diff_prod or {}).get("input") or (diff_draft or {}).get("input") or [])
    diff_outputs = _collect_dep_values((diff_prod or {}).get("output") or (diff_draft or {}).get("output") or [])

    inputs = _unique_keep_order(top_inputs + diff_inputs)
    outputs = _unique_keep_order(top_outputs + diff_outputs)
    return {
        "inputs": inputs,
        "outputs": outputs,
        "normalized_inputs": {_normalize_dep(v): v for v in inputs if _normalize_dep(v)},
        "normalized_outputs": {_normalize_dep(v): v for v in outputs if _normalize_dep(v)},
        "diff_prod": diff_prod or {},
        "diff_draft": diff_draft or {},
    }


def _find_checker_by_biz_status(client, extension_biz_id):
    checkers = _api_call(client, "getBizStatus", extensionBizId=extension_biz_id)
    if not isinstance(checkers, list):
        return None, []
    for checker in checkers:
        if checker.get("extensionCode") == _CHECKER_CODE or checker.get("extensionName") == _CHECKER_NAME:
            return checker, checkers
    return None, checkers


def _find_checker_context_from_pipeline(client, project_id, pipeline_uuid):
    pipeline = client.load("GetPipelineRun", projectId=project_id, uuid=pipeline_uuid)
    if not isinstance(pipeline, dict):
        raise RuntimeError("未找到发布流程")

    stages = pipeline.get("stages") or []
    hook_process_id = ""
    for stage in stages:
        ext_infos = stage.get("extInfos") or {}
        if str(ext_infos.get("checkStatus", "")).upper() == "BLOCKED":
            hook_process_id = ext_infos.get("hookProcessId", "")
            if hook_process_id:
                break
        if str(stage.get("status", "")).upper() == "FAIL" and str(stage.get("type", "")).upper() == "CHECK":
            hook_process_id = ext_infos.get("hookProcessId", "")
            if hook_process_id:
                break

    if not hook_process_id:
        raise RuntimeError("发布流程中未找到 BLOCKED 的检查器阶段")

    events = _api_call(client, "listExtensionEventSnapshot", hookProcessId=hook_process_id)
    if not isinstance(events, list) or not events:
        raise RuntimeError("未找到检查器事件快照")

    blocked = None
    for event in events:
        if event.get("status") == "BLOCKED":
            blocked = event
            break
    blocked = blocked or events[-1]
    extension_biz_id = blocked.get("extensionBizId", "")
    if not extension_biz_id:
        raise RuntimeError("检查器快照未返回 extensionBizId")

    checker, checkers = _find_checker_by_biz_status(client, extension_biz_id)
    return {
        "pipeline": pipeline,
        "events": events,
        "checker_snapshot": blocked,
        "extension_biz_id": extension_biz_id,
        "checker": checker,
        "checkers": checkers,
        "node_uuid": blocked.get("objectId") or (((blocked.get("data") or {}).get("dataSnapshot") or {}).get("fileVersion") or {}).get("fileId"),
    }


def _get_checker_context_by_node(client, project_id, node_uuid):
    node_detail = client.load("GetNode", uuid=str(node_uuid))
    if not isinstance(node_detail, dict):
        raise RuntimeError("未找到节点")
    return {
        "checker": None,
        "checkers": [],
        "checker_snapshot": None,
        "node_uuid": str(node_uuid),
        "node_detail": node_detail,
        "pipeline": None,
        "events": [],
        "extension_biz_id": "",
    }


def _compute_missing(parse_deps, declared_norm, hinted_missing):
    missing_keys = [key for key in parse_deps["normalized_inputs"] if key not in declared_norm]
    missing = [parse_deps["normalized_inputs"][key] for key in missing_keys]

    diff_missing = []
    for item in (parse_deps.get("diff_prod", {}) or {}).get("input") or []:
        if not isinstance(item, dict) or item.get("applyType") != "Add":
            continue
        value = item.get("refTableName") or item.get("output") or item.get("name")
        if value:
            diff_missing.append(str(value))
    for item in (parse_deps.get("diff_draft", {}) or {}).get("input") or []:
        if not isinstance(item, dict) or item.get("applyType") != "Add":
            continue
        value = item.get("refTableName") or item.get("output") or item.get("name")
        if value:
            diff_missing.append(str(value))

    for value in _unique_keep_order(diff_missing):
        normalized = _normalize_dep(value)
        if normalized and normalized not in missing_keys:
            missing_keys.append(normalized)
            missing.append(value)

    for hinted in hinted_missing:
        normalized = _normalize_dep(hinted)
        if normalized and normalized not in missing_keys:
            if normalized in parse_deps["normalized_inputs"] or normalized not in declared_norm:
                missing_keys.append(normalized)
                missing.append(hinted)

    return _unique_keep_order(missing)


def _parse_code_deps(client, project_id, node_uuid, language, code, schedule_connection):
    parse_payload = {
        "projectId": int(project_id),
        "currentNodeUuid": str(node_uuid),
        "language": language or "odps-sql",
        "content": code,
        "scheduleConnection": schedule_connection,
        "debugConnection": {},
    }
    parse_result = _api_call(client, "code_parse", **parse_payload)
    return _extract_parse_dependencies(parse_result)


def analyze_checker_rca(project_id, node_uuid=None, pipeline_uuid=None, runtime_env="prod"):
    client = BFFClient(quiet=True)

    if pipeline_uuid:
        context = _find_checker_context_from_pipeline(client, project_id, pipeline_uuid)
        node_uuid = context.get("node_uuid")
        if not node_uuid:
            raise RuntimeError("无法从 pipeline 定位节点 uuid")
        node_detail = client.load("GetNode", uuid=str(node_uuid))
        if not isinstance(node_detail, dict):
            raise RuntimeError(f"无法获取节点详情: {node_uuid}")
        context["node_detail"] = node_detail
    else:
        context = _get_checker_context_by_node(client, project_id, node_uuid)
        node_detail = context["node_detail"]

    spec_obj = _extract_node_spec(node_detail)
    node_entry = _extract_node_entry(spec_obj, node_detail.get("uuid") or node_uuid)
    checker_snapshot = context.get("checker_snapshot")
    checker = context.get("checker") or {}
    checker_tip = _parse_tip(checker)
    hinted_missing = _extract_missing_from_tip(checker_tip)

    node_candidate = {
        "entityId": str(node_detail.get("uuid") or node_uuid),
        "taskId": str(node_detail.get("taskId") or ""),
    }

    runtime_code, runtime_err = get_node_code(client, project_id, node_candidate, runtime=True, env=runtime_env)
    dev_code, dev_err = get_node_code(client, project_id, node_candidate, runtime=False, env=runtime_env)

    schedule_connection = _extract_schedule_connection(project_id, node_entry, checker_snapshot, client)
    declared_raw, declared_norm = _extract_declared_dependencies(spec_obj, node_detail.get("uuid") or node_uuid)
    snapshot_deps = _extract_snapshot_dependencies(checker_snapshot)
    language = ((node_entry.get("script") or {}).get("language") or "odps-sql")

    analyses = []
    if runtime_code:
        parse_deps = _parse_code_deps(client, project_id, node_detail.get("uuid") or node_uuid, language, runtime_code, schedule_connection)
        analyses.append({
            "code_source": f"runtime:{runtime_env}",
            "parse_deps": parse_deps,
            "missing": _compute_missing(parse_deps, declared_norm, hinted_missing),
        })
    if dev_code:
        parse_deps = _parse_code_deps(client, project_id, node_detail.get("uuid") or node_uuid, language, dev_code, schedule_connection)
        analyses.append({
            "code_source": "dev",
            "parse_deps": parse_deps,
            "missing": _compute_missing(parse_deps, declared_norm, hinted_missing),
        })

    if not analyses:
        raise RuntimeError(runtime_err or dev_err or "未获取到节点代码")

    preferred = next((a for a in analyses if a["code_source"].startswith("runtime") and a["missing"]), None)
    preferred = preferred or next((a for a in analyses if a["missing"]), None)
    preferred = preferred or next((a for a in analyses if a["code_source"].startswith("runtime")), None)
    preferred = preferred or analyses[0]

    parse_deps = preferred["parse_deps"]
    missing = preferred["missing"]
    checker_name = checker.get("extensionName") or _CHECKER_NAME

    result = {
        "checker_name": checker_name,
        "checker_code": checker.get("extensionCode") or _CHECKER_CODE,
        "checker_tip": checker_tip,
        "project_id": project_id,
        "pipeline_uuid": pipeline_uuid,
        "node_uuid": str(node_detail.get("uuid") or node_uuid),
        "node_name": node_detail.get("name", ""),
        "task_id": str(node_detail.get("taskId") or ""),
        "deploy_status": node_detail.get("deployStatus", ""),
        "code_source": preferred["code_source"],
        "schedule_connection": schedule_connection,
        "parsed_inputs": parse_deps["inputs"],
        "parsed_outputs": parse_deps["outputs"],
        "declared_dependencies": declared_raw,
        "snapshot_inputs": snapshot_deps["inputs"],
        "snapshot_outputs": snapshot_deps["outputs"],
        "missing_dependencies": missing,
        "all_analyses": [
            {
                "code_source": item["code_source"],
                "parsed_inputs": item["parse_deps"]["inputs"],
                "parsed_outputs": item["parse_deps"]["outputs"],
                "missing_dependencies": item["missing"],
            }
            for item in analyses
        ],
        "summary": f"{checker_name}: 缺失依赖 {', '.join(missing) if missing else '未识别'}",
    }

    return result


def print_result(result):
    print(f"【检查器】{result.get('checker_name', _CHECKER_NAME)}")
    print(
        f"【节点】{result.get('node_name', '')} "
        f"(uuid={result.get('node_uuid', '')}, taskId={result.get('task_id', '')})"
    )
    print(f"【代码来源】{result.get('code_source', '')}")
    if result.get("checker_tip"):
        print(f"【检查器提示】{result['checker_tip']}")
    if result.get("parsed_inputs"):
        print(f"【代码依赖】{', '.join(result['parsed_inputs'])}")
    if result.get("declared_dependencies"):
        print(f"【调度上游】{', '.join(result['declared_dependencies'])}")
    elif result.get("snapshot_inputs"):
        print(f"【调度上游】{', '.join(result['snapshot_inputs'])}")
    else:
        print("【调度上游】（未识别到已声明上游）")

    missing = result.get("missing_dependencies") or []
    if missing:
        print(f"【缺失依赖】{', '.join(missing)}")
        print("【根因】代码引用了上游输出，但未出现在当前节点调度依赖中")
        print("【建议措施】补齐/刷新调度依赖后重新发布")
    else:
        print("【缺失依赖】（未识别到明确缺口）")
        print("【根因】当前 code_parse 结果与已声明调度上游未形成明确差集，请结合 checker 提示继续核对")
        print("【建议措施】核对 code_parse 结果、GetNode.spec.flow.depends 与 checker 原始提示")

    if result.get("code_source") == "dev":
        print("【提示】当前分析基于开发态代码，可能与发布检查器看到的版本不完全一致")


def main():
    parser = argparse.ArgumentParser(
        description="发布检查器根因分析工具（重点支持调度依赖一致性检查）",
        epilog="输入节点 uuid 或 pipeline uuid，输出代码依赖 / 当前调度上游 / 缺失依赖",
    )
    parser.add_argument("--project-id", dest="project_id", type=int, required=True,
                        help="工作空间ID")
    parser.add_argument("--uuid", help="节点 uuid")
    parser.add_argument("--pipeline-uuid", dest="pipeline_uuid", help="发布流程 uuid")
    parser.add_argument("--env", default="prod", choices=["prod", "dev"],
                        help="优先获取运行态代码的环境（默认 prod）")
    args = parser.parse_args()

    telemetry_start("analyze_checker_rca.py", module="deployment", project_id=args.project_id)

    if not args.uuid and not args.pipeline_uuid:
        parser.error("--uuid 和 --pipeline-uuid 至少提供一个")

    try:
        result = analyze_checker_rca(
            project_id=args.project_id,
            node_uuid=args.uuid,
            pipeline_uuid=args.pipeline_uuid,
            runtime_env=args.env,
        )
        print_result(result)
        telemetry_end(result={"checker_count": len(result.get("checkers", []))})
        save_tool_result("checker_rca", result)
    except Exception as e:
        print(f"[checker_rca] 分析失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("analyze_checker_rca.py", "deployment", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("analyze_checker_rca.py", "deployment", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
