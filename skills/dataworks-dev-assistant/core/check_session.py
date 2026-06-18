#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""会话开始时的轻量检查 —— 汇报工作空间记忆和待跟进事项

无输出 = 无需汇报，agent 直接跳过。

用法:
    PYTHONPATH=<skill-path>/core python <skill-path>/core/check_session.py
"""

import glob
import os
import sys

from workspace_memory import (
    load_workspace_memory, get_baseline, get_baseline_trend, get_next_checks,
)

_TAG = "[session]"


def _scan_workspace_memories():
    """扫描所有 workspace-*.yaml 文件，返回基线摘要列表"""
    pattern = os.path.join(".dataworks", "workspace_memory", "workspace-*.yaml")
    files = glob.glob(pattern)
    if not files:
        return []

    summaries = []
    for path in sorted(files):
        basename = os.path.basename(path)
        # 从文件名提取 project_id: workspace-14255.yaml -> 14255
        try:
            pid = basename.replace("workspace-", "").replace(".yaml", "")
            int(pid)  # 验证是数字
        except (ValueError, TypeError):
            continue

        mem = load_workspace_memory(pid)
        if not mem:
            continue

        baseline = mem.get("baseline", {})
        rate = baseline.get("avg_success_rate")
        fail = baseline.get("typical_failure_count")

        # 趋势数据
        trend = get_baseline_trend(pid)

        # 工作空间名（如果记忆中有）
        ws_name = mem.get("workspace_name", "")

        _ARROWS = {"up": "↑", "down": "↓", "stable": "→"}

        parts = []
        if rate is not None:
            rate_str = f"基线完成率 {rate * 100:.0f}%"
            if trend and trend.get("rate_direction") != "stable":
                arrow = _ARROWS[trend["rate_direction"]]
                prev = trend.get("prev_rate")
                if prev is not None:
                    rate_str += f" {arrow}（前次 {prev * 100:.0f}%）"
                else:
                    rate_str += f" {arrow}"
            parts.append(rate_str)
        if fail is not None and fail > 0:
            fail_str = f"失败 {int(fail)} 个"
            if trend and trend.get("fail_direction") != "stable":
                arrow = _ARROWS[trend["fail_direction"]]
                prev_fail = trend.get("prev_fail")
                if prev_fail is not None:
                    fail_str += f" {arrow}（前次 {int(prev_fail)}）"
                else:
                    fail_str += f" {arrow}"
            parts.append(fail_str)

        if parts:
            label = f"{ws_name} (projectId={pid})" if ws_name else f"projectId={pid}"
            summaries.append(f"  {label}: {', '.join(parts)}")

    return summaries


def _try_telemetry_upload():
    """会话开始时尝试上报待发送的遥测数据 + 轮转本地文件。

    静默执行：不产生 stdout，不抛异常。
    """
    try:
        from telemetry_upload import try_upload_pending, rotate_local
        try_upload_pending(quiet=True)
        rotate_local()
    except Exception:
        pass


def main():
    output_lines = []

    # 0. 静默上报遥测数据（不影响 agent 可见的 stdout）
    _try_telemetry_upload()

    # 1. 工作空间记忆
    try:
        summaries = _scan_workspace_memories()
        if summaries:
            output_lines.append(f"{_TAG} 发现 {len(summaries)} 个工作空间记忆:")
            output_lines.extend(summaries)
    except Exception:
        pass

    # 2. 待跟进事项
    try:
        checks = get_next_checks()
        if checks:
            output_lines.append(f"\n{_TAG} 待跟进事项:")
            for i, item in enumerate(checks, 1):
                reason = item.get("reason", "")
                command = item.get("command", "")
                pid = item.get("project_id", "")
                output_lines.append(f"  {i}. projectId={pid}: {reason}")
                if command:
                    output_lines.append(f"     → {command}")
    except Exception:
        pass

    # 有输出才打印，无输出 = agent 跳过
    if output_lines:
        print("\n".join(output_lines))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # 绝不失败
