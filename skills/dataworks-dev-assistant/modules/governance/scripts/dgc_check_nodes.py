#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""治理规则检查 — 对节点/文件/SQL 执行规则检查并输出诊断结果

对指定的开发节点(entityId/fileId)、SQL 文本执行治理规则检查，
轮询检查结果，输出问题摘要和修复建议。

用法:
    python dgc_check_nodes.py --file-ids 8672307312244157053 --project-id 14255  # 按开发节点 entityId 检查（最常用）
    python dgc_check_nodes.py --sql "SELECT * FROM t"                             # 检查 SQL 文本

"最近变更节点" 的发现已下沉到 search_nodes.py --recent，本脚本只负责执行检查。
典型链路：search_nodes.py --recent --project-id X → 复制 entityId → dgc_check_nodes.py --file-ids ...

涉及 API: runRules, checker_task_search, GetNode
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote

from bff_client import BFFClient, add_backlog

MAX_POLL_SEC = 180          # 多批并发提交后轮询也会更多
POLL_INTERVAL = 3
BATCH_SIZE = 10             # 后端 message_body MySQL 列限制受 nodeDef JSON 总体积影响，取 10 留足 buffer
MAX_WORKERS = 5             # GetNode / runRules / 轮询并发度
_TRUNCATION_HINTS = ("Data too long", "MysqlDataTruncation", "message_body")


def _build_file_entry(client, project_id, file_id):
    """通过 GetNode 获取节点信息，构造 fileList 条目（对齐页面 runRules 调用方式）

    页面发送的 fileList 条目包含完整的 nodeDef（整个 GetNode 返回对象），
    这里复用 GetNode 响应构造等价结构。
    """
    resp = client.call_raw("GetNode", projectId=project_id, uuid=file_id)
    if not client.is_success(resp):
        print(f"GetNode 失败 (fileId={file_id}): {resp.get('message')}", file=sys.stderr)
        return None

    node = resp.get("data", {})
    spec_str = node.get("spec", "{}")
    try:
        spec = json.loads(spec_str) if isinstance(spec_str, str) else spec_str
    except (json.JSONDecodeError, TypeError):
        spec = {}

    # 从 spec 中提取各字段
    first_node = {}
    nodes_list = spec.get("spec", {}).get("nodes", [])
    if nodes_list:
        first_node = nodes_list[0]

    script = first_node.get("script", {})
    runtime = script.get("runtime", {})
    ds = first_node.get("datasource", {})
    rr = first_node.get("runtimeResource", {})
    dqc_rule = first_node.get("dqcRule", {})

    content = script.get("content", "")
    file_type = runtime.get("commandTypeId", 10)
    file_name = script.get("path", node.get("name", ""))

    entry = {
        "fileId": str(file_id),
        "fileName": file_name,
        "fileType": file_type,
        "ownerId": node.get("owner", ""),
        "content": content,
        "nodeDef": json.dumps(node, ensure_ascii=False),
    }
    if ds.get("name"):
        entry["dataSourceName"] = ds["name"]
    if rr.get("resourceGroupId"):
        entry["resourceGroupId"] = rr["resourceGroupId"]
    if runtime:
        entry["realTimeDef"] = json.dumps(runtime, ensure_ascii=False)
    if dqc_rule:
        rule_config = dqc_rule.get("ruleConfig")
        entry["dqcConfig"] = {"enabled": bool(rule_config), "code": rule_config or ""}

    return entry


def _chunk(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def _is_truncation_error(resp):
    msg = str(resp.get("message", ""))
    return any(h in msg for h in _TRUNCATION_HINTS)


def _run_rules_with_filelist(client, project_id, file_list):
    body = {
        "triggerScope": "All",
        "fileScope": "Current",
        "fileList": file_list,
        "projectId": project_id,
        "source": "fileToolbar",
    }
    return client.call_raw("runRules", **body)


def _submit_run_rules(client, project_id, file_ids_batch):
    """构造 fileList（并发 GetNode）+ 调用 runRules。
    遇到 message_body 截断错误时自动对半拆分重试（直至批 ≤1 仍失败才放弃）。

    返回：(run_ids: list[str], message_ids: list[str], skipped: int)
    """
    # 并发 GetNode
    file_list = []
    skipped = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(_build_file_entry, client, project_id, fid): fid for fid in file_ids_batch}
        for fut in as_completed(futs):
            entry = fut.result()
            if entry:
                file_list.append(entry)
            else:
                skipped += 1

    if not file_list:
        return [], [], skipped

    # 递归提交；触发截断错误则对半拆分
    def _submit(entries):
        if not entries:
            return [], [], 0
        resp = _run_rules_with_filelist(client, project_id, entries)
        if client.is_success(resp):
            d = resp.get("data") or {}
            return ([d.get("runId", "")] if d.get("runId") else []), (d.get("messageIdList") or []), 0
        if _is_truncation_error(resp) and len(entries) > 1:
            mid = len(entries) // 2
            r1, m1, s1 = _submit(entries[:mid])
            r2, m2, s2 = _submit(entries[mid:])
            return r1 + r2, m1 + m2, s1 + s2
        print(f"runRules 失败 (批 {len(entries)} 个): code={resp.get('code')}, message={str(resp.get('message',''))[:180]}",
              file=sys.stderr)
        return [], [], len(entries)

    run_ids, message_ids, drop = _submit(file_list)
    return run_ids, message_ids, skipped + drop


def run_check(client, project_id=None, file_ids=None, sql_content=None):
    """触发 runRules 并轮询结果，返回 {messageId: [checkerTasks]}。

    file_ids 模式：超过 BATCH_SIZE 时自动分批并发提交；统一轮询所有 messageId。
    """
    if sql_content:
        # SQL 模式走旧路径（不需要分批）
        body = {
            "triggerScope": "All",
            "requestType": "innerApi",
            "sqlContent": sql_content,
        }
        resp = client.call_raw("runRules", **body)
        if not client.is_success(resp):
            print(f"runRules 失败: code={resp.get('code')}, message={resp.get('message')}", file=sys.stderr)
            sys.exit(1)
        data = resp.get("data", {})
        message_ids = data.get("messageIdList") or []
        run_ids = [data.get("runId", "")]
        total_skipped = 0
    elif file_ids and project_id:
        batches = list(_chunk(file_ids, BATCH_SIZE))
        total_input = len(file_ids)
        print(f"共 {total_input} 个节点，分 {len(batches)} 批并发提交 (初始每批 ≤{BATCH_SIZE}，截断错误自动拆分)")
        run_ids = []
        message_ids = []
        total_skipped = 0
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futs = [ex.submit(_submit_run_rules, client, project_id, b) for b in batches]
            for fut in as_completed(futs):
                rids, mids, skipped = fut.result()
                total_skipped += skipped
                run_ids.extend(rids)
                message_ids.extend(mids)
        covered = total_input - total_skipped
        if not message_ids:
            print(f"所有批次提交失败 ({total_input} 个节点全部未检查)", file=sys.stderr)
            sys.exit(1)
        status_suffix = f" ⚠️ {total_skipped} 个节点未检查（GetNode 或 runRules 失败）" if total_skipped else ""
        print(f"已提交 {len(run_ids)} 个 runRules, 合计 {len(message_ids)} 个检查任务；覆盖 {covered}/{total_input} 节点" + status_suffix)
    else:
        print("需要 --file-ids + --project-id 或 --sql", file=sys.stderr)
        sys.exit(1)

    # 轮询 checker_task_search。status 字段偶尔不翻 FINISHED 但 checkerTasks 已全到齐，
    # 所以用「稳态检测」：连续 2 轮总 task 数不变且所有 mid 都有 task → 视为完成
    all_results = {}
    start = time.time()
    prev_total = -1
    stable_rounds = 0
    while True:
        time.sleep(POLL_INTERVAL)
        pending_mids = [mid for mid in message_ids
                        if all_results.get(mid, {}).get("_status") != "FINISHED"]
        if pending_mids:
            def _poll(mid):
                resp = client.call_raw("checker_task_search", messageId=mid)
                if not client.is_success(resp):
                    return mid, None
                return mid, resp.get("data", {})

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
                for fut in as_completed([ex.submit(_poll, mid) for mid in pending_mids]):
                    mid, d = fut.result()
                    if d is None:
                        continue
                    all_results[mid] = {"_status": d.get("status"), "tasks": d.get("checkerTasks") or []}

        # 终态 A：所有 mid 都标 FINISHED
        if all(all_results.get(mid, {}).get("_status") == "FINISHED" for mid in message_ids):
            print(f"检查完成 ({time.time()-start:.0f}s)")
            break

        # 终态 B：所有 mid 都已有 task 数据，且连续 2 轮总数不变 → 后端偶尔不翻 FINISHED，视为已稳定
        all_have_tasks = all(all_results.get(mid, {}).get("tasks") for mid in message_ids)
        curr_total = sum(len(v.get("tasks") or []) for v in all_results.values())
        if all_have_tasks and curr_total == prev_total and curr_total > 0:
            stable_rounds += 1
            if stable_rounds >= 2:
                print(f"检查完成 ({time.time()-start:.0f}s, 结果已稳定)")
                break
        else:
            stable_rounds = 0
        prev_total = curr_total

        if time.time() - start > MAX_POLL_SEC:
            no_data = [m for m in message_ids if not all_results.get(m, {}).get("tasks")]
            if no_data:
                # 真正没拿到数据的那几个 mid 进 backlog
                print(f"轮询超时 ({MAX_POLL_SEC}s)，{len(no_data)}/{len(message_ids)} 个 messageId 无数据")
                add_backlog(
                    type_name="governance_check",
                    label=f"治理检查 {len(no_data)} 个 messageId 无数据 (runId={','.join(run_ids)[:60]})",
                    check={
                        "api": "checker_task_search",
                        "params": {"messageId": no_data[0]},
                        "status_field": "status",
                        "terminal": {"FINISHED": "检查完成"},
                        "pending": {"RUNNING": "检查中"},
                    },
                    context={"runIds": run_ids, "messageIds": no_data},
                    on_success="python dgc_check_nodes.py 查看结果已就绪，重新执行即可",
                )
                print("已加入异步任务，稍后可查看")
            else:
                # 数据已到但 status 未翻 → 视为完成，给 info 提示
                print(f"检查完成 ({MAX_POLL_SEC}s 后结果已齐但 status 未终态，按已完成处理)")
            break

    return {
        "results": {mid: v.get("tasks") or [] for mid, v in all_results.items()},
        "total_input": locals().get("total_input", 0),
        "total_skipped": locals().get("total_skipped", 0),
    }


def print_results(result):
    """汇总并输出检查结果。result 可为 dict(新) 或 legacy dict-of-tasks"""
    if isinstance(result, dict) and "results" in result:
        all_results = result["results"]
        total_input = result.get("total_input", 0)
        total_skipped = result.get("total_skipped", 0)
    else:
        all_results = result
        total_input = total_skipped = 0

    ok = warn = fail = 0
    issues = []
    for mid, tasks in all_results.items():
        for item in tasks:
            r = item.get("checkResult")
            if r == 0:
                ok += 1
            elif r == 1:
                warn += 1
                issues.append(item)
            elif r == 2:
                fail += 1
                issues.append(item)

    covered = total_input - total_skipped if total_input else None
    print(f"\n━━ 检查汇总 ━━")
    if covered is not None and total_input:
        cov_line = f"  覆盖 {covered}/{total_input} 节点"
        if total_skipped:
            cov_line += f"  ⚠️ {total_skipped} 个未检查"
        print(cov_line)
    print(f"  OK {ok} / WARN {warn} / FAIL {fail}")

    if not issues:
        return

    print(f"\n━━ 问题详情 ━━")
    for item in issues:
        r = item.get("checkResult")
        level = "FAIL" if r == 2 else "WARN"
        code = item.get("itemCode", "?")
        name = item.get("itemName", "?")
        print(f"\n  [{level}] {code} — {name}")

        detail_raw = item.get("checkDetail")
        if not detail_raw:
            continue
        try:
            detail = json.loads(detail_raw)
        except (json.JSONDecodeError, TypeError):
            continue

        for diag in detail.get("diagnostics", []):
            msg = diag.get("messageLangMap", {}).get("zh", "")
            if msg:
                print(f"    问题: {msg}")

            line_info = diag.get("range", {}).get("start", {})
            line = line_info.get("line")
            if line is not None:
                print(f"    位置: 第 {line + 1} 行")

            href = diag.get("codeDescription", {}).get("href", "")
            if href:
                try:
                    decoded = unquote(href)
                    if "suggestion=" in decoded:
                        suggestion = decoded.split("suggestion=", 1)[1].split("&")[0]
                        if suggestion:
                            print(f"    建议: {suggestion}")
                except Exception:
                    pass


def main():
    parser = argparse.ArgumentParser(
        description="治理规则检查 — 对 entityId / SQL 执行规则扫描",
        epilog="发现最近变更节点: python search_nodes.py --recent --project-id <PID>",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file-ids", help="开发节点 entityId/fileId（逗号分隔；@path 从文件读取，每行一个）")
    group.add_argument("--sql", help="SQL 文本")

    parser.add_argument("--project-id", type=int, help="工作空间 ID（--file-ids 时必填）")
    args = parser.parse_args()

    client = BFFClient()

    if args.file_ids:
        if not args.project_id:
            print("--file-ids 需要 --project-id", file=sys.stderr)
            print("→ python search_nodes.py --recent --project-id <PID>  # 先发现候选节点", file=sys.stderr)
            sys.exit(1)
        raw = args.file_ids.strip()
        if raw.startswith("@"):
            path = raw[1:]
            try:
                with open(path) as f:
                    file_ids = [x.strip() for x in f.read().replace(",", "\n").splitlines() if x.strip()]
            except OSError as e:
                print(f"读取 entityId 文件失败: {path} ({e})", file=sys.stderr)
                sys.exit(1)
            print(f"从 {path} 读取 {len(file_ids)} 个 entityId")
        else:
            file_ids = [x.strip() for x in raw.split(",") if x.strip()]
        all_results = run_check(client, project_id=args.project_id, file_ids=file_ids)
    elif args.sql:
        all_results = run_check(client, sql_content=args.sql)
    else:
        parser.print_help()
        sys.exit(1)

    print_results(all_results)


if __name__ == "__main__":
    main()
