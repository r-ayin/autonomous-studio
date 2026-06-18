# -*- coding: utf-8 -*-
"""
查看 DataWorks 已发布 Python UDF 的源码。

用法：
    PYTHONPATH=<skill>/core python view_udf.py \
        --project-id 21375 \
        --name my_udf          # UDF 名称（即资源文件名，不含 .py）

流程：
    1. listResources keyword=<name> → 找到 resource_uuid
    2. getResource → spec(JSON-in-JSON) → fileResources[0].script.content(JSON) → uadResourceId(file_uuid)
    3. GET /ide/getOrcFileResourceContent?uuid=<file_uuid>&projectId=<id> → 源码字符串
"""

import argparse
import json
import sys

import requests

try:
    from bff_client import BFFClient
except ImportError:
    print("ERROR: 请加 PYTHONPATH=<skill-path>/core 运行本脚本", file=sys.stderr)
    sys.exit(1)


def _form_post(c, path, data):
    resp = requests.post(
        f"{c.endpoint}{path}",
        headers={
            "Authorization": f"Bearer {c.token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"http://{c.session_code}.qwen.cli",
        },
        data=data,
    )
    resp.raise_for_status()
    body = resp.json()
    data = body.get("data") or {}
    if body.get("code") != 200 and not (isinstance(data, dict) and data.get("success") is not False):
        raise RuntimeError(f"{path} 失败: {body.get('message') or body}")
    return data


def _find_resource(c, project_id, name):
    """listResources → 匹配名称 → 返回 resource_uuid"""
    fname = name if name.endswith(".py") else f"{name}.py"
    data = _form_post(c, "/dataworks_public_v2024-05-18/listResources",
                      {"projectId": project_id, "keyword": name, "pageSize": 50})
    items = (data or {}).get("data") or []
    for item in items:
        item_name = item.get("name") or ""
        if item_name == fname or item_name == name:
            return item.get("uuid") or item.get("id")
    # fallback: 关键字部分匹配
    for item in items:
        if name in (item.get("name") or ""):
            return item.get("uuid") or item.get("id")
    names = [i.get("name") for i in items]
    raise RuntimeError(f"未找到资源 '{name}'，listResources 返回: {names}")


def _get_file_uuid(c, project_id, resource_uuid):
    """getResource → JSON-in-JSON → uadResourceId"""
    detail = _form_post(c, "/dataworks_public_v2024-05-18/getResource",
                        {"projectId": project_id, "uuid": resource_uuid})
    if not detail:
        raise RuntimeError("getResource 返回空")

    # 第一层：spec 是 JSON 字符串
    spec_str = detail.get("spec")
    if spec_str and isinstance(spec_str, str):
        try:
            spec_obj = json.loads(spec_str)
            frs = (spec_obj.get("spec") or spec_obj).get("fileResources") or []
            if frs:
                content_str = frs[0].get("script", {}).get("content")
                if content_str and isinstance(content_str, str):
                    content_obj = json.loads(content_str)
                    file_uuid = content_obj.get("uadResourceId")
                    if file_uuid:
                        return file_uuid
        except Exception:
            pass

    # 兜底：直接字段
    frs = detail.get("fileResources") or []
    if frs:
        content_str = (frs[0].get("script") or {}).get("content")
        if content_str and isinstance(content_str, str):
            try:
                content_obj = json.loads(content_str)
                file_uuid = content_obj.get("uadResourceId")
                if file_uuid:
                    return file_uuid
            except Exception:
                pass

    raise RuntimeError(
        "无法从 getResource 结果中解析出 uadResourceId（file_uuid）。\n"
        f"getResource raw: {json.dumps(detail, ensure_ascii=False)[:500]}"
    )


def _fetch_source(c, project_id, file_uuid):
    """GET /ide/getOrcFileResourceContent → 源码字符串"""
    resp = requests.get(
        f"{c.endpoint}/ide/getOrcFileResourceContent",
        headers={
            "Authorization": f"Bearer {c.token}",
            "Referer": f"http://{c.session_code}.qwen.cli",
        },
        params={"uuid": file_uuid, "projectId": project_id},
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 200:
        raise RuntimeError(f"getOrcFileResourceContent 失败: {body.get('message') or body}")
    return body.get("data") or ""


def main():
    parser = argparse.ArgumentParser(description="查看 DataWorks Python UDF 源码")
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--name", required=True, help="UDF 名称（资源文件名，不含 .py 也可）")
    args = parser.parse_args()

    c = BFFClient()
    project_id = args.project_id
    name = args.name

    print(f"[1/3] 查找资源 '{name}' ...")
    resource_uuid = _find_resource(c, project_id, name)
    print(f"      resource_uuid: {resource_uuid}")

    print(f"[2/3] 解析 file_uuid ...")
    file_uuid = _get_file_uuid(c, project_id, resource_uuid)
    print(f"      file_uuid: {file_uuid}")

    print(f"[3/3] 拉取源码 ...")
    source = _fetch_source(c, project_id, file_uuid)

    print(f"\n{'='*60}")
    print(f"  UDF: {name}  (project: {project_id})")
    print(f"{'='*60}")
    print(source)
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
