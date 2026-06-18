#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查所有待办异步操作的状态

用法:
    python check_backlogs.py          # 查询所有待办并更新状态
    python check_backlogs.py --list   # 仅列出待办，不查询 API
"""

import argparse
import json
import os
import sys
from datetime import datetime

from bff_client import BFFClient, load_backlogs, save_backlogs

_TAG = "[backlogs]"


def _api_call(client, api_name, **kwargs):
    """直接调用 API（用于状态查询，绕过写操作检查）"""
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


def _extract_status(result, status_field):
    """通过点路径提取状态值（如 'taskCurrentRun.status'）"""
    value = result
    for key in status_field.split("."):
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


def _format_elapsed(created_at):
    """格式化创建时间为相对时间"""
    from datetime import datetime
    try:
        created = datetime.fromisoformat(created_at)
        elapsed = (datetime.now() - created).total_seconds()
        if elapsed < 60:
            return f"{int(elapsed)}秒前"
        elif elapsed < 3600:
            return f"{int(elapsed / 60)}分钟前"
        elif elapsed < 86400:
            return f"{int(elapsed / 3600)}小时前"
        else:
            return f"{int(elapsed / 86400)}天前"
    except Exception:
        return created_at


def _check_fail_fast(items, check, entry, elapsed):
    """fail_fast 模式：遍历列表，任一失败立即报失败，全部成功才报成功"""
    status_field = check.get("status_field", "status")
    terminal = check.get("terminal", {})
    pending = check.get("pending", {})
    fail_terminals = {k for k, v in terminal.items() if v in ("失败",)}
    success_terminals = {k for k, v in terminal.items() if v in ("成功",)}

    failed_items = []
    pending_items = []
    success_items = []

    for item in items:
        s = str(_extract_status(item, status_field) or "")
        name = item.get("nodeName") or item.get("dagName") or ""
        if s in fail_terminals:
            failed_items.append((s, name, item))
        elif s in success_terminals:
            success_items.append((s, name))
        else:
            label = pending.get(s) or terminal.get(s) or f"状态{s}"
            pending_items.append((s, name, label))

    if failed_items:
        s, name, item = failed_items[0]
        label_text = terminal[s]
        failed_task_id = item.get("taskId", "")
        print(f"  状态: {s}（{label_text}）| 失败节点: {name} | taskId={failed_task_id}")
        if len(failed_items) > 1:
            print(f"  另有 {len(failed_items) - 1} 个节点也失败")
        # 输出查日志指引
        ctx = entry.get("context", {})
        project_id = ctx.get("project_id") or check.get("params", {}).get("projectId", "")
        _skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _log_script = os.path.join(_skill_root, "modules", "task-ops", "scripts", "log_analyzer.py")
        _core_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"  → 查看失败日志: PYTHONPATH={_core_dir} python {_log_script} --project-id {project_id} --task-id {failed_task_id}")
        entry["done"] = True
        entry["done_status"] = "failed"
        entry["done_label"] = label_text
        entry["done_at"] = datetime.now().isoformat()
        return True, label_text

    if pending_items:
        labels = set(l for _, _, l in pending_items)
        print(f"  状态: {', '.join(labels)} | {len(success_items)} 成功, {len(pending_items)} 进行中 | 创建于 {elapsed}")
        return False, None

    # 全部成功
    print(f"  状态: 全部成功（{len(success_items)} 个实例）")
    on_success = entry.get("on_success")
    if on_success:
        print(f"  → {on_success}")
    entry["done"] = True
    entry["done_status"] = "success"
    entry["done_label"] = "成功"
    entry["done_at"] = datetime.now().isoformat()
    return True, "成功"


def _check_backfill_instances(client, entry, dag_ids):
    """补数据第二层：用 dagId 查实例真实执行状态，返回 (is_terminal, status_label)"""
    INSTANCE_TERMINAL = {"5": "失败", "6": "成功"}
    INSTANCE_PENDING  = {"1": "等待时间", "2": "等待资源", "3": "等待上游", "4": "运行中"}
    check = entry.get("check", {})
    params = check.get("params", {})
    project_id = params.get("projectId") or entry.get("context", {}).get("project_id", "")
    env = params.get("env", "prod")
    all_success, any_failed, any_pending = [], [], []
    for dag_id in dag_ids:
        try:
            result = _api_call(client, "getInstanceList",
                               projectId=project_id, env=env, dagId=dag_id)
            items = result if isinstance(result, list) else []
            for inst in items:
                s = str(inst.get("status", ""))
                name = inst.get("nodeName", "")
                task_id = inst.get("taskId", "")
                if s in INSTANCE_TERMINAL:
                    label = INSTANCE_TERMINAL[s]
                    if label == "失败":
                        any_failed.append((s, name, task_id, dag_id))
                    else:
                        all_success.append((s, name))
                else:
                    label = INSTANCE_PENDING.get(s, f"状态{s}")
                    any_pending.append((s, name, label))
        except Exception as e:
            print(f"  ⚠ dagId={dag_id} 实例查询失败: {e}")
            return False, None
    if any_failed:
        s, name, task_id, dag_id = any_failed[0]
        print(f"  实例状态: 失败 | 节点: {name} | taskId={task_id}")
        ctx = entry.get("context", {})
        project_id_ctx = ctx.get("project_id", project_id)
        _skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _log_script = os.path.join(_skill_root, "modules", "task-ops", "scripts", "log_analyzer.py")
        _core_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"  → 查日志: PYTHONPATH={_core_dir} python {_log_script} --project-id {project_id_ctx} --task-id {task_id}")
        entry["done"] = True
        entry["done_status"] = "failed"
        entry["done_label"] = "实例失败"
        entry["done_at"] = datetime.now().isoformat()
        return True, "实例失败"
    if any_pending:
        labels = set(l for _, _, l in any_pending)
        print(f"  实例状态: {', '.join(labels)} | {len(all_success)} 成功, {len(any_pending)} 进行中")
        return False, None
    if all_success:
        print(f"  实例状态: 全部成功（{len(all_success)} 个实例）")
        on_success = entry.get("on_success")
        if on_success:
            print(f"  → {on_success}")
        entry["done"] = True
        entry["done_status"] = "success"
        entry["done_label"] = "成功"
        entry["done_at"] = datetime.now().isoformat()
        return True, "成功"
    print(f"  实例状态: 暂无实例（DAG 刚入队，稍后再查）")
    return False, None


def _check_entry(client, entry, idx_str):
    """查询单条任务状态，返回 (is_terminal, status_label)"""
    label = entry.get("label", entry.get("type", "unknown"))
    check = entry.get("check", {})
    elapsed = _format_elapsed(entry.get("created_at", ""))

    # 已经是终态的条目，重新查询获取最新状态
    was_done = entry.get("done", False)
    if was_done:
        done_label = entry.get("done_label", "已完成")
        prefix = "✓" if entry.get("done_status") == "success" else "✗"
        print(f"{idx_str} {prefix} {label}")
    else:
        print(f"{idx_str} {label}")

    try:
        result = _api_call(client, check["api"], **check.get("params", {}))
    except Exception as e:
        print(f"  状态: 查询失败（{e}）")
        print(f"  创建于: {elapsed}")
        return False, None

    # 从嵌套路径提取列表（如 getInstanceList 返回 {data: [...]}）
    list_path = check.get("list_path")
    if list_path and isinstance(result, dict):
        for key in list_path.split("."):
            result = result.get(key, result) if isinstance(result, dict) else result

    # API 返回列表时
    if check.get("result_is_list") and isinstance(result, list):
        # fail_fast 模式：遍历所有项，任一失败即报失败
        if check.get("fail_fast") and len(result) > 0:
            return _check_fail_fast(result, check, entry, elapsed)
        # 默认：取第一个元素
        result = result[0] if result else {}

    status_value = _extract_status(result, check.get("status_field", "status"))
    status_str = str(status_value) if status_value is not None else "unknown"

    terminal = check.get("terminal", {})
    pending = check.get("pending", {})

    if status_str in terminal:
        label_text = terminal[status_str]
        print(f"  状态: {status_str}（{label_text}）")
        # 补数据：DAG 创建成功后，再查一层实例真实状态
        if entry.get("type") == "backfill" and label_text == "成功":
            print(f"  DAG 创建: 成功 | 创建于 {elapsed}")
            dag_ids = []
            if isinstance(result, dict):
                dag_ids = [d["dagId"] for d in result.get("details", []) if "dagId" in d]
            elif isinstance(result, list):
                dag_ids = [d["dagId"] for d in result if isinstance(d, dict) and "dagId" in d]
            if dag_ids:
                return _check_backfill_instances(client, entry, dag_ids)
            else:
                print(f"  ⚠ 未找到 dagId，无法查实例状态")
                return False, None
        on_success = entry.get("on_success")
        if on_success and label_text in ("成功",):
            print(f"  → {on_success}")
        # 标记终态但不删除
        entry["done"] = True
        entry["done_status"] = "success" if label_text in ("成功",) else "failed"
        entry["done_label"] = label_text
        entry["done_at"] = datetime.now().isoformat()
        return True, label_text
    elif status_str in pending:
        label_text = pending[status_str]
        print(f"  状态: {status_str}（{label_text}）| 创建于 {elapsed}")
        return False, label_text
    else:
        print(f"  状态: {status_str}（未知状态）| 创建于 {elapsed}")
        return False, None


def check_all():
    """查询所有任务的状态（含已完成的）"""
    backlogs = load_backlogs()
    if not backlogs:
        print(f"{_TAG} 没有异步任务")
        return

    client = BFFClient(quiet=True)

    # 分组：进行中 + 已完成
    pending_entries = [e for e in backlogs if not e.get("done")]
    done_entries = [e for e in backlogs if e.get("done")]

    completed_count = 0
    in_progress_count = 0
    total = len(backlogs)

    if pending_entries:
        print(f"{_TAG} {len(pending_entries)} 个异步任务进行中\n")
        for i, entry in enumerate(pending_entries):
            is_terminal, _ = _check_entry(client, entry, f"[{i + 1}/{len(pending_entries)}]")
            if is_terminal:
                completed_count += 1
            else:
                in_progress_count += 1
            print()

    if done_entries:
        print(f"{_TAG} {len(done_entries)} 个已完成任务（重新查询最新状态）\n")
        for i, entry in enumerate(done_entries):
            _check_entry(client, entry, f"[{i + 1}/{len(done_entries)}]")
            completed_count += 1
            print()

    print(f"{_TAG} 完成: {completed_count} | 进行中: {in_progress_count} | 总计: {total}")

    save_backlogs(backlogs)


def list_only():
    """仅列出所有任务，不查询 API"""
    backlogs = load_backlogs()
    if not backlogs:
        print(f"{_TAG} 没有异步任务")
        return

    pending_entries = [e for e in backlogs if not e.get("done")]
    done_entries = [e for e in backlogs if e.get("done")]

    print(f"{_TAG} {len(backlogs)} 个异步任务（{len(pending_entries)} 进行中, {len(done_entries)} 已完成）\n")
    for i, entry in enumerate(backlogs):
        label = entry.get("label", entry.get("type", "unknown"))
        elapsed = _format_elapsed(entry.get("created_at", ""))
        done = entry.get("done")
        if done:
            prefix = "✓" if entry.get("done_status") == "success" else "✗"
            done_label = entry.get("done_label", "已完成")
            print(f"[{i + 1}/{len(backlogs)}] {prefix} {label} — {done_label}")
        else:
            print(f"[{i + 1}/{len(backlogs)}] {label}")
        print(f"  创建于: {elapsed}")
        print()


def clean_done():
    """清理已完成的任务"""
    backlogs = load_backlogs()
    remaining = [e for e in backlogs if not e.get("done")]
    removed = len(backlogs) - len(remaining)
    save_backlogs(remaining)
    print(f"{_TAG} 已清理 {removed} 个已完成任务，剩余 {len(remaining)} 个")


def main():
    parser = argparse.ArgumentParser(description="查看异步操作状态")
    parser.add_argument("--list", action="store_true",
                        help="仅列出所有任务，不查询 API 状态")
    parser.add_argument("--clean", action="store_true",
                        help="清理已完成的任务记录")
    args = parser.parse_args()

    if args.clean:
        clean_done()
    elif args.list:
        list_only()
    else:
        check_all()


if __name__ == "__main__":
    main()
