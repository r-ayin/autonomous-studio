#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ODPS Python UDF 一键上传 + 发布工具

用法：
    PYTHONPATH=<skill>/core python deploy_udf.py \
        --project-id 21375 \
        --file /tmp/my_udf.py \
        [--name my_udf]           # 默认取文件名（不含 .py）
        --resource-path 旧版工作流/青迹  # 资源存放路径（新建必填）
        --func-path 旧版工作流/青迹/函数  # 函数存放路径（新建必填）
        [--datasource odps_first]
        [--resource-group group_4341]
        [--skip-prod]             # 只发到开发环境
        [--update]                # 更新模式：只重传文件内容，不重建资源/函数

流程（新建，4 阶段并行）：
    阶段1: OSS 上传链（Steps 1-3）‖ CreateResource（Step 4）
    阶段2: UpdateResource 绑定内容（Step 5）
    阶段3: 发布资源 DEV+PROD ‖ CreateFunction（Step 6+7）
    阶段4: 发布函数 DEV+PROD（Step 8）

流程（更新，3 阶段串行）：
    阶段U1: OSS 重新上传
    阶段U2: UpdateResource 绑定新内容
    阶段U3: 发布资源 DEV+PROD
"""

import argparse
import datetime
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_CORE_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..", "..", "core"))
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from bff_client import BFFClient


def _confirmed_post(c, path, params):
    confirmed = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:16]
    headers = {
        "Authorization": f"Bearer {c.token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": f"http://{c.session_code}.qwen.cli",
        "X-User-Confirmed": confirmed,
    }
    resp = requests.post(f"{c.endpoint}{path}", headers=headers, data=params)
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") not in (None, 0, 200, "0", "200"):
        raise RuntimeError(f"{path} 失败: {body}")
    return body["data"]


def _json_post(c, path, body):
    headers = {
        "Authorization": f"Bearer {c.token}",
        "Content-Type": "application/json",
        "Referer": f"http://{c.session_code}.qwen.cli",
    }
    resp = requests.post(f"{c.endpoint}{path}", headers=headers, json=body)
    resp.raise_for_status()
    body_r = resp.json()
    if body_r.get("code") not in (None, 0, 200, "0", "200"):
        raise RuntimeError(f"{path} 失败: {body_r}")
    return body_r["data"]


def _form_post(c, path, params):
    headers = {
        "Authorization": f"Bearer {c.token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": f"http://{c.session_code}.qwen.cli",
    }
    resp = requests.post(f"{c.endpoint}{path}", headers=headers, data=params)
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") not in (None, 0, 200, "0", "200"):
        raise RuntimeError(f"{path} 失败: {body}")
    return body["data"]


def _log(tag, msg):
    print(f"[{tag}] {msg}", flush=True)


def oss_upload_chain(c, fname, file_bytes):
    """Steps 1-3: generateUadUploadPolicy → OSS upload → callback"""
    _log("OSS-1", "generateUadUploadPolicy ...")
    policy_data = _json_post(c, "/da/generateUadUploadPolicy", {
        "expiredDate": -1, "fssKey": "datastudio-ide", "moduleType": "ide",
        "accelerateTag": False, "fileShowName": fname,
    })
    file_uuid = policy_data["fileUuid"]
    file_path = policy_data["filePath"]
    pi = policy_data["policyInfo"]

    _log("OSS-2", f"上传到 OSS ({len(file_bytes)} bytes) ...")
    oss_resp = requests.post(pi["host"],
        data={"key": file_path, "OSSAccessKeyId": pi["accessid"],
              "policy": pi["policy"], "Signature": pi["signature"],
              "success_action_status": "200"},
        files={"file": (fname, file_bytes, "text/plain")})
    oss_resp.raise_for_status()

    _log("OSS-3", "callbackUadUploadFront ...")
    _json_post(c, "/da/callbackUadUploadFront", {"fileUuid": file_uuid, "status": "SUCCESS"})

    _log("OSS", f"完成 → file_uuid={file_uuid}")
    return file_uuid, file_path


def create_resource(c, project_id, fname, dw_path):
    """Step 4: CreateResource（只建空条目，不需要 file_uuid）"""
    _log("Step4", "CreateResource ...")
    spec = json.dumps({"kind": "Resource", "fileResources": [{
        "name": fname, "type": "Python",
        "script": {"runtime": {"command": "ODPS_PYTHON"}, "path": dw_path},
        "datasource": {"name": "odps_first"},
    }]}, ensure_ascii=False)
    resource_uuid = _confirmed_post(c, "/dataworks_public_v2024-05-18/createResource",
                                    {"projectId": project_id, "spec": spec})
    _log("Step4", f"完成 → resource_uuid={resource_uuid}")
    return resource_uuid


def update_resource(c, project_id, fname, file_uuid, file_path, file_size,
                    resource_uuid, dw_path, datasource, resource_group, resource_group_id):
    """Step 5: UpdateResource 绑定 OSS 内容"""
    _log("Step5", "UpdateResource 绑定内容 ...")
    content_obj = {
        "ossKey": file_path, "fileSize": file_size,
        "uploadTime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "uadResourceId": file_uuid, "uuid": resource_uuid, "fileName": fname,
        "datasource": {"name": datasource, "type": ""},
        "runtimeResource": {"resourceGroup": resource_group, "resourceGroupId": resource_group_id},
        "type": "PYTHON", "sourceType": "LOCAL",
    }
    spec = json.dumps({"kind": "Resource", "fileResources": [{
        "id": resource_uuid, "name": fname, "type": "Python",
        "script": {"content": json.dumps(content_obj, ensure_ascii=False),
                   "runtime": {"command": "ODPS_PYTHON"}, "path": dw_path},
        "datasource": {"name": datasource},
    }]}, ensure_ascii=False)
    _confirmed_post(c, "/dataworks_public_v2024-05-18/updateResource",
                    {"projectId": project_id, "uuid": resource_uuid, "spec": spec})
    _log("Step5", "完成")


_STAGE_CODE_MAP = {
    "DEPLOY_NODE_DEV": "DEV",
    "DEPLOY_NODE_PROD": "PROD",
}


def deploy_object(c, project_id, uuid, stage, label, poll_interval=2, timeout=120):
    """createDeployment 到指定阶段，轮询直到目标 stage 完成"""
    _log(label, f"发布到 {stage} ...")
    pipeline_uuid = _form_post(c, "/ide/createDeployment", {
        "projectId": project_id, "type": "Online",
        "objectIds": json.dumps([uuid]), "runMode": "AUTO",
        "autoRunUntilStage": stage,
    })

    target_code = _STAGE_CODE_MAP.get(stage, stage)
    headers = {
        "Authorization": f"Bearer {c.token}",
        "Referer": f"http://{c.session_code}.qwen.cli",
    }
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{c.endpoint}/ide/getDeployPipeline", headers=headers,
                            params={"uuid": pipeline_uuid, "projectId": project_id, "objectId": uuid})
        resp.raise_for_status()
        data = resp.json().get("data", {})
        overall = data.get("status", "")
        stages = data.get("stages", [])
        target = next((s for s in stages if s.get("code") == target_code), None)
        target_status = target.get("status", "") if target else ""

        if target_status == "SUCCESS":
            _log(label, f"完成 pipeline={pipeline_uuid}")
            return pipeline_uuid
        if overall in ("FAILED", "CANCELED") or target_status in ("FAILED", "CANCELED"):
            error_msg = data.get("errorMsg", "") or (target.get("errorMsg", "") if target else "")
            raise RuntimeError(
                f"{label} pipeline {pipeline_uuid} 失败: {target_code}={target_status}, msg={error_msg}"
            )
        time.sleep(poll_interval)

    raise RuntimeError(f"{label} pipeline {pipeline_uuid} 超时（{timeout}s）")


def create_function(c, project_id, udf_name, fname, resource_uuid, func_dw_path, datasource,
                    class_name=None):
    """Step 7: CreateFunction"""
    _log("Step7", "CreateFunction ...")
    clazz = class_name or f"{udf_name}.{udf_name}"
    spec = json.dumps({"kind": "Function", "functions": [{
        "name": udf_name,
        "className": clazz,
        "clazzName": clazz,
        "script": {"path": func_dw_path, "runtime": {"command": "ODPS_FUNCTION"}},
        "fileResources": [{"id": resource_uuid, "name": fname}],
        "datasource": {"name": datasource},
    }]}, ensure_ascii=False)
    func_uuid = _confirmed_post(c, "/dataworks_public_v2024-05-18/createFunction",
                                {"projectId": project_id, "spec": spec})
    _log("Step7", f"完成 → func_uuid={func_uuid}")
    return func_uuid


def lookup_resource(c, project_id, fname):
    """查找已有资源，返回 (resource_uuid, dw_path)。找不到则抛出 RuntimeError。"""
    _log("Lookup", f"查找已有资源 {fname} ...")
    raw = _form_post(c, "/dataworks_public_v2024-05-18/listResources",
                     {"projectId": project_id, "keyword": fname, "pageSize": 50})

    if isinstance(raw, dict):
        items = raw.get("list") or raw.get("data") or []
    elif isinstance(raw, list):
        items = raw
    else:
        items = []

    match = next((r for r in items if isinstance(r, dict) and r.get("name") == fname), None)
    if not match:
        raise RuntimeError(
            f"找不到名为 {fname} 的资源。请先去掉 --update 用新建模式创建，或检查 --name 是否正确。"
        )

    resource_uuid = str(match.get("uuid") or match.get("id") or "")
    if not resource_uuid:
        raise RuntimeError(f"资源 {fname} 的 uuid 为空，无法更新")

    detail = _form_post(c, "/dataworks_public_v2024-05-18/getResource",
                        {"projectId": project_id, "uuid": resource_uuid})

    dw_path = None
    if isinstance(detail, dict):
        # 第一层：直接字段
        file_resources = detail.get("fileResources") or []
        if file_resources and isinstance(file_resources[0], dict):
            dw_path = file_resources[0].get("script", {}).get("path")
        if not dw_path:
            dw_path = detail.get("script", {}).get("path") or detail.get("path")

        # 第二层：spec 是 JSON 字符串（JSON-in-JSON）
        if not dw_path:
            spec_str = detail.get("spec")
            if spec_str and isinstance(spec_str, str):
                try:
                    spec_obj = json.loads(spec_str)
                    frs = (spec_obj.get("spec") or spec_obj).get("fileResources") or []
                    if frs and isinstance(frs[0], dict):
                        dw_path = frs[0].get("script", {}).get("path")
                except Exception:
                    pass

    if not dw_path:
        raise RuntimeError(
            f"无法从 getResource 获取 {fname} 的 dw_path，请手动传 --resource-path"
        )

    _log("Lookup", f"完成 → resource_uuid={resource_uuid}, dw_path={dw_path}")
    return resource_uuid, dw_path


def main():
    parser = argparse.ArgumentParser(description="ODPS Python UDF 一键上传发布")
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--file", required=True, help="本地 .py 文件路径")
    parser.add_argument("--name", help="UDF 名称（默认取文件名不含 .py）")
    parser.add_argument("--resource-path",
                        help="资源存放路径，如 工作流/资源（--update 模式下自动查找，可省略）")
    parser.add_argument("--func-path",
                        help="函数存放路径，如 工作流/函数（--update 模式下不使用）")
    parser.add_argument("--datasource", default="odps_first")
    parser.add_argument("--resource-group", default="group_4341")
    parser.add_argument("--resource-group-id", default="4341")
    parser.add_argument("--skip-prod", action="store_true", help="只发到开发环境")
    parser.add_argument("--update", action="store_true",
                        help="更新模式：只重传文件内容，不重建资源/函数")
    parser.add_argument("--class-name",
                        help="函数类名（默认 模块名.模块名），如 chat_message_quality.ChatMessageQuality")
    args = parser.parse_args()

    if not args.update and not args.resource_path:
        parser.error("新建模式下 --resource-path 必填（更新模式用 --update 自动查找）")
    if not args.update and not args.func_path:
        parser.error("新建模式下 --func-path 必填（更新模式用 --update 不需要此参数）")

    file_path_local = args.file
    if not os.path.exists(file_path_local):
        print(f"错误：文件不存在 {file_path_local}", file=sys.stderr)
        sys.exit(1)

    with open(file_path_local, "rb") as f:
        file_bytes = f.read()
    file_size = len(file_bytes)
    fname = os.path.basename(file_path_local)
    udf_name = args.name or os.path.splitext(fname)[0]

    c = BFFClient()
    project_id = args.project_id

    if args.update:
        # ── 更新模式：只重传文件内容，不重建资源/函数 ──────────────
        resource_uuid, dw_resource_path = lookup_resource(c, project_id, fname)

        print(f"\n{'='*55}")
        print(f"  [更新模式] UDF: {udf_name}  ({fname}, {file_size} bytes)")
        print(f"  项目: {project_id}  数据源: {args.datasource}")
        print(f"  资源路径: {dw_resource_path}  resource_uuid: {resource_uuid}")
        print(f"{'='*55}\n")

        t0 = time.time()

        print("── 阶段U1: OSS上传 ──")
        file_uuid, oss_key = oss_upload_chain(c, fname, file_bytes)
        print(f"阶段U1 完成 ({time.time()-t0:.1f}s)\n")

        print("── 阶段U2: UpdateResource 绑定内容 ──")
        t1 = time.time()
        update_resource(c, project_id, fname, file_uuid, oss_key, file_size,
                        resource_uuid, dw_resource_path,
                        args.datasource, args.resource_group, args.resource_group_id)
        print(f"阶段U2 完成 ({time.time()-t1:.1f}s)\n")

        print("── 阶段U3: 发布资源 ──")
        t2 = time.time()
        deploy_object(c, project_id, resource_uuid, "DEPLOY_NODE_DEV", "资源-DEV")
        if not args.skip_prod:
            deploy_object(c, project_id, resource_uuid, "DEPLOY_NODE_PROD", "资源-PROD")
        print(f"阶段U3 完成 ({time.time()-t2:.1f}s)\n")

        total = time.time() - t0
        print(f"{'='*55}")
        print(f"  更新完成！总耗时 {total:.1f}s")
        print(f"  resource_uuid : {resource_uuid}")
        print(f"  SQL 验证: SELECT {udf_name}(args);")
        print(f"{'='*55}\n")

    else:
        # ── 新建模式：完整 4 阶段流程 ──────────────────────────────
        dw_resource_path = f"{args.resource_path}/{fname}"
        dw_func_path = f"{args.func_path}/{udf_name}"

        print(f"\n{'='*55}")
        print(f"  UDF: {udf_name}  ({fname}, {file_size} bytes)")
        print(f"  项目: {project_id}  数据源: {args.datasource}")
        print(f"  资源路径: {dw_resource_path}")
        print(f"  函数路径: {dw_func_path}")
        print(f"{'='*55}\n")

        print("── 阶段1: OSS上传 ‖ CreateResource（并行）──")
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=2) as ex:
            fut_oss = ex.submit(oss_upload_chain, c, fname, file_bytes)
            fut_res = ex.submit(create_resource, c, project_id, fname, dw_resource_path)
            (file_uuid, oss_key), resource_uuid = fut_oss.result(), fut_res.result()
        print(f"阶段1 完成 ({time.time()-t0:.1f}s)\n")

        print("── 阶段2: UpdateResource 绑定内容 ──")
        t1 = time.time()
        update_resource(c, project_id, fname, file_uuid, oss_key, file_size,
                        resource_uuid, dw_resource_path,
                        args.datasource, args.resource_group, args.resource_group_id)
        print(f"阶段2 完成 ({time.time()-t1:.1f}s)\n")

        # 同一对象的 DEV 和 PROD 必须串行（服务端并发冲突会报系统错误）
        # CreateFunction 只依赖 resource_uuid，可与资源 DEV 发布并行
        print("── 阶段3: 发布资源DEV ‖ CreateFunction（并行）──")
        t2 = time.time()
        with ThreadPoolExecutor(max_workers=2) as ex:
            fut_res_dev = ex.submit(deploy_object, c, project_id, resource_uuid,
                                    "DEPLOY_NODE_DEV", "资源-DEV")
            fut_func = ex.submit(create_function, c, project_id, udf_name, fname,
                                 resource_uuid, dw_func_path, args.datasource,
                                 getattr(args, "class_name", None))
            fut_res_dev.result()
            func_uuid = fut_func.result()

        if not args.skip_prod:
            deploy_object(c, project_id, resource_uuid, "DEPLOY_NODE_PROD", "资源-PROD")
        print(f"阶段3 完成 ({time.time()-t2:.1f}s)\n")

        print("── 阶段4: 发布函数 ──")
        t3 = time.time()
        deploy_object(c, project_id, func_uuid, "DEPLOY_NODE_DEV", "函数-DEV")
        if not args.skip_prod:
            deploy_object(c, project_id, func_uuid, "DEPLOY_NODE_PROD", "函数-PROD")
        print(f"阶段4 完成 ({time.time()-t3:.1f}s)\n")

        total = time.time() - t0
        print(f"{'='*55}")
        print(f"  全部完成！总耗时 {total:.1f}s")
        print(f"  resource_uuid : {resource_uuid}")
        print(f"  func_uuid     : {func_uuid}")
        print(f"  SQL 验证: SELECT {udf_name}(args);")
        print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
