#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作空间持久记忆 —— 跨会话积累运维知识

存储路径: {cwd}/.dataworks/workspace_memory/workspace-{project_id}.yaml

使用方式:
    from workspace_memory import (
        load_workspace_memory, save_workspace_memory,
        record_known_issue, get_known_issues,
        update_baseline, get_baseline,
    )

    # 读取/保存整体记忆
    mem = load_workspace_memory(14255)
    save_workspace_memory(14255, {"custom_key": "value"})

    # 基线指标（ops_overview 使用）
    update_baseline(14255, success_rate=0.94, failure_count=12)
    baseline = get_baseline(14255)

    # 已知问题（query_instances 使用）
    record_known_issue(14255, "308437862", "sync_cn_odps_m_task",
                       pattern="连续失败5天", fix_strategy="调整优先级")
    issues = get_known_issues(14255)
"""

import json
import os
from datetime import date, datetime, timedelta

try:
    import yaml
except ImportError:
    yaml = None

_MEMORY_DIR = os.path.join(".dataworks", "workspace_memory")


def _memory_path(project_id, work_dir=None):
    """返回工作空间记忆文件路径，自动创建目录"""
    base = work_dir or os.getcwd()
    d = os.path.join(base, _MEMORY_DIR)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"workspace-{project_id}.yaml")


def _today():
    return date.today().isoformat()


def _load_yaml(path):
    """读取 YAML 文件，不存在或解析失败返回空 dict"""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            if yaml:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
            else:
                # fallback: 文件存在但无 PyYAML，返回空
                return {}
    except Exception:
        return {}


def _save_yaml(path, data):
    """写入 YAML 文件"""
    if not yaml:
        # fallback: 用简单格式写入（不支持嵌套列表的完整序列化）
        import json
        with open(path, "w", encoding="utf-8") as f:
            # 写成 JSON 也能被 yaml.safe_load 读取
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ─── 公开 API ──────────────────────────────────────────────────


def load_workspace_memory(project_id, work_dir=None):
    """加载工作空间记忆，不存在则返回空 dict"""
    path = _memory_path(project_id, work_dir)
    return _load_yaml(path)


def save_workspace_memory(project_id, data, work_dir=None):
    """保存/合并工作空间记忆

    与已有数据做浅合并（顶层 key 覆盖），known_issues 保留原列表。
    """
    path = _memory_path(project_id, work_dir)
    existing = _load_yaml(path)

    # 保留 known_issues 不被覆盖（由 record_known_issue 专门管理）
    if "known_issues" in existing and "known_issues" not in data:
        data.setdefault("known_issues", existing["known_issues"])

    existing.update(data)
    existing["workspace_id"] = int(project_id)
    existing["last_updated"] = _today()
    _save_yaml(path, existing)


_BASELINE_HISTORY_MAX = 14  # 保留最近 14 天快照，足够看趋势


def update_baseline(project_id, success_rate, failure_count, work_dir=None):
    """更新工作空间基线指标（由 ops_overview 调用）"""
    path = _memory_path(project_id, work_dir)
    mem = _load_yaml(path)

    baseline = mem.get("baseline", {})
    # 滑动平均：新值占 30%，历史占 70%（首次直接写入）
    old_rate = baseline.get("avg_success_rate")
    if old_rate is not None and isinstance(old_rate, (int, float)):
        baseline["avg_success_rate"] = round(old_rate * 0.7 + success_rate * 0.3, 4)
    else:
        baseline["avg_success_rate"] = round(success_rate, 4)

    old_fail = baseline.get("typical_failure_count")
    if old_fail is not None and isinstance(old_fail, (int, float)):
        baseline["typical_failure_count"] = round(old_fail * 0.7 + failure_count * 0.3)
    else:
        baseline["typical_failure_count"] = int(failure_count)

    baseline["last_updated"] = _today()

    # 追加历史快照（每天最多一条，按日期去重）
    history = baseline.get("history", [])
    if not isinstance(history, list):
        history = []
    today = _today()
    # 同一天更新则覆盖最后一条
    if history and history[-1].get("date") == today:
        history[-1] = {"date": today, "success_rate": round(success_rate, 4),
                        "failure_count": int(failure_count)}
    else:
        history.append({"date": today, "success_rate": round(success_rate, 4),
                         "failure_count": int(failure_count)})
    # 保留最近 N 天
    baseline["history"] = history[-_BASELINE_HISTORY_MAX:]

    mem["baseline"] = baseline
    mem["workspace_id"] = int(project_id)
    mem["last_updated"] = _today()
    _save_yaml(path, mem)


def get_baseline(project_id, work_dir=None):
    """获取工作空间基线指标，不存在返回 None"""
    mem = load_workspace_memory(project_id, work_dir)
    baseline = mem.get("baseline")
    if not baseline or not isinstance(baseline, dict):
        return None
    return baseline


def get_baseline_trend(project_id, work_dir=None):
    """获取基线趋势，返回 dict 或 None。

    返回格式:
        {
            "current_rate": 0.94,
            "prev_rate": 0.97,       # 最近一次历史记录（非今天）
            "rate_direction": "down", # "up" | "down" | "stable"
            "current_fail": 12,
            "prev_fail": 8,
            "fail_direction": "up",
            "days_tracked": 5,
        }
    """
    baseline = get_baseline(project_id, work_dir)
    if not baseline:
        return None

    history = baseline.get("history", [])
    if not isinstance(history, list) or len(history) < 2:
        return None

    current = history[-1]
    prev = history[-2]

    cur_rate = current.get("success_rate")
    prev_rate = prev.get("success_rate")
    cur_fail = current.get("failure_count")
    prev_fail = prev.get("failure_count")

    def _direction(cur, prev, higher_is_better=True):
        if cur is None or prev is None:
            return "stable"
        diff = cur - prev
        threshold = 0.01 if isinstance(cur, float) else 1
        if abs(diff) < threshold:
            return "stable"
        if higher_is_better:
            return "up" if diff > 0 else "down"
        else:
            return "down" if diff > 0 else "up"  # 失败数越多越差

    return {
        "current_rate": cur_rate,
        "prev_rate": prev_rate,
        "rate_direction": _direction(cur_rate, prev_rate, higher_is_better=True),
        "current_fail": cur_fail,
        "prev_fail": prev_fail,
        "fail_direction": _direction(cur_fail, prev_fail, higher_is_better=False),
        "days_tracked": len(history),
    }


def record_known_issue(project_id, node_id, node_name, pattern, fix_strategy=None, work_dir=None):
    """记录或更新已知问题

    按 node_id 去重：已存在则更新 last_seen 和 seen_count，不存在则追加。
    """
    path = _memory_path(project_id, work_dir)
    mem = _load_yaml(path)
    issues = mem.get("known_issues", [])
    if not isinstance(issues, list):
        issues = []

    # 查找已有条目
    found = False
    for issue in issues:
        if str(issue.get("node_id")) == str(node_id):
            issue["last_seen"] = _today()
            issue["seen_count"] = issue.get("seen_count", 1) + 1
            issue["pattern"] = pattern
            if fix_strategy:
                issue["fix_strategy"] = fix_strategy
            found = True
            break

    if not found:
        entry = {
            "node_id": str(node_id),
            "node_name": node_name,
            "pattern": pattern,
            "last_seen": _today(),
            "seen_count": 1,
        }
        if fix_strategy:
            entry["fix_strategy"] = fix_strategy
        issues.append(entry)

    mem["known_issues"] = issues
    mem["workspace_id"] = int(project_id)
    mem["last_updated"] = _today()
    _save_yaml(path, mem)


def get_known_issues(project_id, work_dir=None):
    """获取已知问题列表，不存在返回空列表"""
    mem = load_workspace_memory(project_id, work_dir)
    issues = mem.get("known_issues", [])
    return issues if isinstance(issues, list) else []


# ─── Next Check（跨会话跟进） ─────────────────────────────────

_NEXT_CHECKS_FILE = os.path.join(_MEMORY_DIR, "next_checks.json")
_EXPIRE_DAYS = 3


def _next_checks_path(work_dir=None):
    """返回 next_checks.json 路径，自动创建目录"""
    base = work_dir or os.getcwd()
    d = os.path.join(base, _MEMORY_DIR)
    os.makedirs(d, exist_ok=True)
    return os.path.join(base, _NEXT_CHECKS_FILE)


def _load_next_checks(work_dir=None):
    """读取 next_checks.json，过滤过期条目"""
    path = _next_checks_path(work_dir)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        # 过滤过期条目
        cutoff = (datetime.now() - timedelta(days=_EXPIRE_DAYS)).isoformat()
        return [item for item in data
                if isinstance(item, dict) and item.get("created", "") >= cutoff]
    except Exception:
        return []


def _save_next_checks(checks, work_dir=None):
    """写入 next_checks.json"""
    path = _next_checks_path(work_dir)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(checks, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def save_next_check(project_id, reason, command, work_dir=None):
    """保存一个待跟进事项，供下次会话开始时检查。

    按 project_id 去重：已存在则更新 reason/command/created。
    """
    try:
        checks = _load_next_checks(work_dir)
        pid = str(project_id)
        # 去重：替换同 project_id 的条目
        checks = [c for c in checks if str(c.get("project_id")) != pid]
        checks.append({
            "project_id": pid,
            "reason": reason,
            "command": command,
            "created": datetime.now().isoformat(),
        })
        _save_next_checks(checks, work_dir)
    except Exception:
        pass  # 绝不失败


def get_next_checks(work_dir=None):
    """获取所有待跟进事项（已过滤过期条目）。返回 list[dict]。"""
    try:
        return _load_next_checks(work_dir)
    except Exception:
        return []


def clear_next_check(project_id, work_dir=None):
    """清除指定 project_id 的待跟进事项。"""
    try:
        checks = _load_next_checks(work_dir)
        pid = str(project_id)
        checks = [c for c in checks if str(c.get("project_id")) != pid]
        _save_next_checks(checks, work_dir)
    except Exception:
        pass
