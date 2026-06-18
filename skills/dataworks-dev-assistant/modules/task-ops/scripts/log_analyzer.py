#!/usr/bin/env python3
"""
Log Analyzer — 分析任务实例日志，提取错误块供 agent 判断
策略：尾部优先 + 关键词过滤 + 结构化输出
"""

import argparse
import re
import sys
from typing import Optional, Tuple

_TAG = "[log-analyzer]"

# ── 错误模式定义 ─────────────────────────────────────────
# 确定性错误：命中即认定为错误
DEFINITE_ERROR_PATTERNS = [
    r"(?i)\bFAILED\b",
    r"(?i)\bException\b",
    r"(?i)\bError\b.*:",           # Error: xxx 或 SomeError: xxx
    r"(?i)\bfatal\b",
    r"(?i)\bcritical\b",
    r"(?i)segmentation fault",
    r"(?i)core dumped",
    r"(?i)out of memory",
    r"(?i)\bOOM\b",
    r"(?i)killed",
    r"(?i)command not found",
    r"(?i)permission denied",
    r"(?i)syntax error",
    r"(?i)stack overflow",
    r"(?i)connection refused",
    r"(?i)connection timed? ?out",
    r"(?i)no such file or directory",
    r"(?i)exit code [1-9]\d*",     # 非零退出码
    r"(?i)non-zero exit",
    r"(?i)shell run failed",
    r"(?i)task status:\s*error",
]

# 排除模式：匹配这些的行不是真正错误
EXCLUDE_PATTERNS = [
    r'["\']error["\']\s*:\s*(null|""|false|\[\s*\]|\{\s*\})',
    r'["\']errorMessage["\']\s*:\s*(null|"")',
    r'["\']error_code["\']\s*:\s*(null|""|0|"0")',
    r"(?i)error count:\s*0",
    r"(?i)no error",
    r"(?i)error.*=\s*0\b",
]

# 已编译的正则
_DEFINITE_RE = [re.compile(p) for p in DEFINITE_ERROR_PATTERNS]
_EXCLUDE_RE = [re.compile(p) for p in EXCLUDE_PATTERNS]


# ── 日志获取 ─────────────────────────────────────────────

def fetch_log_via_bff(task_instance_id: Optional[str] = None,
                      project_id: Optional[int] = None,
                      task_id: Optional[str] = None) -> str:
    """通过 BFF API 获取任务实例日志，返回纯文本"""
    from bff_client import BFFClient

    client = BFFClient(quiet=True)

    if task_instance_id:
        # dgc 接口：get_task_instance_log
        api_meta = client.api_index.get("get_task_instance_log")
        if not api_meta:
            print(f"{_TAG} 未找到 API: get_task_instance_log", file=sys.stderr)
            sys.exit(1)
        result = client._do_request("get_task_instance_log", api_meta,
                                    taskInstanceId=task_instance_id)
        code = result.get("code")
        if code not in (None, 0, "0", 200, "200"):
            print(f"{_TAG} get_task_instance_log 失败: code={code}, "
                  f"message={result.get('message', '')}", file=sys.stderr)
            sys.exit(1)
        # 返回值是 data 字段的纯文本
        return str(result.get("data", ""))

    elif project_id and task_id:
        # workbench 接口：getInstanceRunLog
        api_meta = client.api_index.get("getInstanceRunLog")
        if not api_meta:
            print(f"{_TAG} 未找到 API: getInstanceRunLog", file=sys.stderr)
            sys.exit(1)
        result = client._do_request("getInstanceRunLog", api_meta,
                                    projectId=project_id, env="prod",
                                    tenantId=1, taskId=task_id, historyId=0)
        code = result.get("code")
        if code not in (None, 0, "0", 200, "200"):
            print(f"{_TAG} getInstanceRunLog 失败: code={code}, "
                  f"message={result.get('message', '')}", file=sys.stderr)
            sys.exit(1)
        data = result.get("data")
        if isinstance(data, dict):
            return data.get("data") or data.get("content") or str(data)
        return str(data or "")

    else:
        print(f"{_TAG} 需要 --task-instance-id 或 --project-id + --task-id",
              file=sys.stderr)
        sys.exit(1)


def read_log_from_file(path: str) -> str:
    """从本地文件读取日志"""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


# ── 错误提取（尾部优先） ──────────────────────────────────

def _is_error_line(line: str) -> bool:
    """判断一行是否为错误行（命中确定性模式且不在排除列表中）"""
    # 先检查排除模式
    for pat in _EXCLUDE_RE:
        if pat.search(line):
            return False
    # 再检查错误模式
    for pat in _DEFINITE_RE:
        if pat.search(line):
            return True
    return False


def extract_error_block(log_text: str, tail_lines: int = 200,
                        context_before: int = 5, context_after: int = 3,
                        max_error_lines: int = 50) -> Tuple[str, str]:
    """
    从日志中提取错误块。

    策略：
    1. 先看尾部 tail_lines 行（错误几乎都在最后）
    2. 提取所有错误行 + 上下文
    3. 如果尾部没找到，再扫全文（但只取摘要）

    返回: (error_block, strategy_used)
    """
    lines = log_text.splitlines()
    total = len(lines)

    if total == 0:
        return "", "empty"

    # ── 第 1 步：尾部扫描 ──
    tail_start = max(0, total - tail_lines)
    tail = lines[tail_start:]

    error_indices = []  # 相对于 tail 的索引
    for i, line in enumerate(tail):
        if _is_error_line(line):
            error_indices.append(i)

    if error_indices:
        # 提取错误行 + 上下文，合并重叠区间
        blocks = []
        for idx in error_indices:
            start = max(0, idx - context_before)
            end = min(len(tail), idx + context_after + 1)
            blocks.append((start, end))

        # 合并重叠区间
        merged = [blocks[0]]
        for start, end in blocks[1:]:
            prev_start, prev_end = merged[-1]
            if start <= prev_end:
                merged[-1] = (prev_start, max(prev_end, end))
            else:
                merged.append((start, end))

        # 拼接提取的块
        result_lines = []
        for start, end in merged:
            block = tail[start:end]
            if len(result_lines) + len(block) > max_error_lines:
                # 截断，保留最后的错误块（通常最关键）
                remaining = max_error_lines - len(result_lines)
                if remaining > 0:
                    result_lines.append("... (truncated) ...")
                    result_lines.extend(block[-remaining:])
                break
            if result_lines:
                result_lines.append("---")
            result_lines.extend(block)

        return "\n".join(result_lines), "tail"

    # ── 第 2 步：全文扫描（尾部没发现错误时） ──
    error_indices_full = []
    for i, line in enumerate(lines):
        if _is_error_line(line):
            error_indices_full.append(i)

    if error_indices_full:
        # 取最后几个错误行 + 上下文
        last_errors = error_indices_full[-10:]
        result_lines = []
        for idx in last_errors:
            start = max(0, idx - context_before)
            end = min(total, idx + context_after + 1)
            block = lines[start:end]
            if len(result_lines) + len(block) > max_error_lines:
                break
            if result_lines:
                result_lines.append("---")
            result_lines.extend(block)
        return "\n".join(result_lines), "full_scan"

    # ── 没找到明确错误 ──
    # 返回最后 30 行让模型判断
    fallback = lines[-30:] if total > 30 else lines
    return "\n".join(fallback), "no_error_found"


# ── 输出（stdout → agent） ───────────────────────────────

def output_result(error_block: str, strategy: str, total_lines: int, args,
                  profile: dict = None):
    """结构化输出到 stdout，供 agent 消费"""
    print(f"{_TAG} 日志错误提取完成")
    print(f"  日志总行数: {total_lines}")
    print(f"  提取策略: {strategy}")
    print()

    print("=" * 60)
    print("错误日志片段")
    print("=" * 60)
    block_lines = error_block.splitlines()
    if len(block_lines) > 80:
        for line in block_lines[:40]:
            print(f"  {line}")
        print(f"  ... ({len(block_lines) - 80} lines omitted) ...")
        for line in block_lines[-40:]:
            print(f"  {line}")
    else:
        for line in block_lines:
            print(f"  {line}")

    # 下一步命令提示
    print()
    print("=" * 60)
    print("下一步")
    print("=" * 60)

    # 确定 nodeId 和 projectId（用于后续命令）
    nid = (hasattr(args, 'node_id') and args.node_id) or None
    pid = args.project_id or ""
    entity_id = profile.get("entity_id") if profile else None
    output_table = profile.get("output_table") if profile else None

    if args.task_instance_id:
        tid = args.task_instance_id
        print(f"  查看实例详情: get_task_instance --taskInstanceId {tid}")
    if nid and pid:
        print(f"  查看任务详情: task_detail.py --project-id {pid} --node-id {nid}")
        print(f"  查看运行态代码: find_node_code.py --project-id {pid} --task-id {nid} --runtime")
        if entity_id:
            print(f"  查看开发态代码: find_node_code.py --project-id {pid} --entity-id {entity_id}")
        if output_table:
            print(f"  查看产出表: search_table.py \"{output_table}\"")
        print(f"  重跑实例（谨慎）: rerun_task_instances --projectId {pid} --taskIds '[\"{nid}\"]'")
    elif pid and args.task_id:
        tid = args.task_id
        print(f"  查看运行态代码: find_node_code.py --project-id {pid} --task-id {tid} --runtime")
        if entity_id:
            print(f"  查看开发态代码: find_node_code.py --project-id {pid} --entity-id {entity_id}")
        print(f"  重跑实例（谨慎）: rerun_task_instances --projectId {pid} --taskIds '[\"{tid}\"]'")
    else:
        print(f"  重跑实例（谨慎）: rerun_task_instances --projectId <PID> --taskIds '[\"<TASK_ID>\"]'")


# ── 主流程 ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="分析任务实例日志，定位失败根因")

    # 日志来源（三选一）
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--task-instance-id",
                     help="任务实例 ID（调用 get_task_instance_log）")
    src.add_argument("--task-id",
                     help="任务 ID（配合 --project-id 调用 getInstanceRunLog）")
    src.add_argument("--file", help="本地日志文件路径")

    parser.add_argument("--project-id", type=int,
                        help="工作空间 ID（--task-id 时必传）")
    parser.add_argument("--node-id",
                        help="运行态节点 ID（用于生成下一步命令）")
    parser.add_argument("--tail-lines", type=int, default=200,
                        help="尾部扫描行数（默认 200）")

    args = parser.parse_args()

    # 校验参数
    if args.task_id and not args.project_id:
        print(f"{_TAG} --task-id 需要配合 --project-id 使用", file=sys.stderr)
        sys.exit(1)

    # ── 1. 获取日志 ──
    if args.file:
        log_text = read_log_from_file(args.file)
    else:
        log_text = fetch_log_via_bff(
            task_instance_id=args.task_instance_id,
            project_id=args.project_id,
            task_id=args.task_id,
        )

    if not log_text or not log_text.strip():
        print(f"{_TAG} 日志为空，无法分析")
        sys.exit(0)

    total_lines = len(log_text.splitlines())

    # ── 2. 提取错误块（尾部优先） ──
    error_block, strategy = extract_error_block(
        log_text, tail_lines=args.tail_lines)

    if not error_block.strip():
        print(f"{_TAG} 日志中未发现错误内容（{total_lines} 行）")
        sys.exit(0)

    # ── 2.5. 查 node_profile 补充 entityId/产出表（静默失败） ──
    profile = None
    node_id = (hasattr(args, 'node_id') and args.node_id) or args.task_id
    pid = args.project_id
    if node_id and pid:
        try:
            from node_profile import get_profile
            np = get_profile()
            if np:
                profile = np.lookup(int(pid), task_id=int(node_id))
        except Exception:
            pass

    # ── 3. 输出 ──
    output_result(error_block, strategy, total_lines, args, profile=profile)


if __name__ == "__main__":
    main()
