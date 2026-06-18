#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""遥测上报 —— 通过 BFF suggest 接口将本地遥测数据上报到服务端

利用已有的 /bff_v1/suggest 接口作为传输通道。
suggest 接口的 text 字段携带 JSON 编码的 telemetry batch。

服务端通过 text 内容的 `"_type": "telemetry_batch"` 标记区分
普通用户反馈和遥测上报。

用法:
    # 上报最近数据（自动记录上次上报位置，增量上报）
    PYTHONPATH=<skill>/core python <skill>/core/telemetry_upload.py

    # 上报指定日期之后的数据
    PYTHONPATH=<skill>/core python <skill>/core/telemetry_upload.py --since 2026-04-01

    # 空跑：只打印 batch 不实际上报
    PYTHONPATH=<skill>/core python <skill>/core/telemetry_upload.py --dry-run
"""

import json
import os
import sys
from datetime import datetime

from telemetry import _load_records, _TELEMETRY_FILE
from telemetry_schema import SCHEMA_VERSION, validate_batch

# ─── 上报位点（增量上报） ───────────────────────────────────────

_CURSOR_FILE = os.path.join(os.path.expanduser("~"), ".dataworks", "telemetry_cursor.json")


def _load_cursor():
    """读取上次上报的最后一条记录时间戳"""
    path = _CURSOR_FILE
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("last_ts")
    except Exception:
        return None


def _save_cursor(last_ts):
    """保存上报位点"""
    path = _CURSOR_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"last_ts": last_ts, "updated_at": datetime.now().isoformat()}, f)


# ─── 构建 batch ──────────────────────────────────────────────

def _load_skill_meta():
    """从 profile.json 读�� skill 元信息"""
    # 尝试多个可能的 profile 路径
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "profile.json"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    profile = json.load(f)
                env_val = profile.get("env", "unknown")
                # 兼容两种 schema：env 作为字符串（当前）或作为 dict（历史）
                if isinstance(env_val, dict):
                    env_val = env_val.get("name", "unknown")
                return {
                    "skill_name": profile.get("skill_name", "dataworks"),
                    "skill_version": profile.get("version", "unknown"),
                    "env": env_val,
                }
            except Exception:
                pass
    return {"skill_name": "dataworks", "skill_version": "unknown", "env": "unknown"}


def build_batch(records):
    """将记录列表打包为符合契约的 batch"""
    meta = _load_skill_meta()
    return {
        "schema_version": SCHEMA_VERSION,
        "skill_name": meta["skill_name"],
        "skill_version": meta["skill_version"],
        "env": meta["env"],
        "uploaded_at": datetime.now().isoformat(timespec="seconds"),
        "events": records,
    }


# ─── 上报 ────────────────────────────────────────────────────

def upload_via_suggest(batch):
    """通过 BFF suggest 接口上报 telemetry batch。

    利用 BFFClient 的 HTTP 层发送，但绕过 DuckDB 灌入。
    suggest 接口参数: { "_type": "telemetry_batch", "text": "<batch JSON>" }

    Returns:
        (ok: bool, message: str)
    """
    try:
        from bff_client import BFFClient
        client = BFFClient(analyzer=False, quiet=True)

        api_meta = client.api_index.get("suggest")
        if not api_meta:
            return False, "api-index 中未找到 suggest 接口"

        payload = {
            "_type": "telemetry_batch",
            "text": json.dumps(batch, ensure_ascii=False, separators=(",", ":")),
        }

        result = client._do_request("suggest", api_meta, **payload)

        if client.is_success(result):
            return True, f"上报成功 (requestId={result.get('requestId', '?')})"
        else:
            return False, f"上报失败: code={result.get('code')}, message={result.get('message')}"

    except ImportError:
        return False, "无法导入 BFFClient（缺少依赖）"
    except Exception as e:
        return False, f"上报异常: {e}"


# ─── 自动上报（供 check_session 调用） ───────────────────────

def try_upload_pending(quiet=True):
    """尝试上报待发送的遥测数据。

    设计为 check_session.py 的会话开始钩子：
    - 静默执行，不产生 stdout（不干扰 agent）
    - 失败不抛异常（遥测不影响主流程）
    - 有数据才上报，无数据直接返回

    Args:
        quiet: True 时不产生任何 stdout 输出

    Returns:
        dict: {"uploaded": int, "ok": bool, "message": str} 或 None（无数据）
    """
    try:
        since = _load_cursor()
        records = _load_records(since=since)
        if not records:
            return None

        # 单次上报上限
        max_events = 500
        if len(records) > max_events:
            records = records[-max_events:]

        batch = build_batch(records)
        ok, msg = upload_via_suggest(batch)

        if ok:
            last_ts = records[-1].get("ts", "")
            if last_ts:
                _save_cursor(last_ts)

        if not quiet:
            print(f"[telemetry] {msg} ({len(records)} 条)")

        return {"uploaded": len(records), "ok": ok, "message": msg}
    except Exception:
        return {"uploaded": 0, "ok": False, "message": "上报异常"}


# ─── 本地文件轮转 ────────────────────────────────────────────

_MAX_LOCAL_LINES = 5000  # 本地保留最近 5000 条


def rotate_local():
    """轮转本地 JSONL 文件，保留最近 N 条。

    只在文件超过阈值时触发，避免频繁 IO。
    """
    filepath = _TELEMETRY_FILE
    if not os.path.exists(filepath):
        return

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if len(lines) <= _MAX_LOCAL_LINES:
            return

        # 保留最近的记录
        kept = lines[-_MAX_LOCAL_LINES:]
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(kept)
    except Exception:
        pass  # 轮转不影响主流程


# ─── CLI ──────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="遥测数据上报（通过 BFF suggest 接口）")
    parser.add_argument("--since", help="上报起始日期 (YYYY-MM-DD)，默认从上次位点开始")
    parser.add_argument("--dry-run", action="store_true", help="只构建 batch 不实际上报")
    parser.add_argument("--max-events", type=int, default=500,
                        help="单次上报最大事件数（默认 500）")
    args = parser.parse_args()

    # 确定起始位点
    since = args.since
    if not since:
        cursor = _load_cursor()
        if cursor:
            since = cursor
            print(f"从上次位点继续: {since}")

    # 加载记录
    records = _load_records(since=since)
    if not records:
        print("无新数据需要上报")
        return

    # 截断
    if len(records) > args.max_events:
        print(f"记录数 {len(records)} 超过上限 {args.max_events}，只上报最近 {args.max_events} 条")
        records = records[-args.max_events:]

    # 构建 batch
    batch = build_batch(records)

    # 校验
    ok, errors = validate_batch(batch)
    if not ok:
        print(f"batch 校验有 {len(errors)} 个问题（仍继续上报）:", file=sys.stderr)
        for e in errors[:5]:
            print(f"  ⚠ {e}", file=sys.stderr)

    if args.dry_run:
        print(f"\n[dry-run] batch 包含 {len(records)} 条事件，schema v{batch['schema_version']}")
        print(f"  skill: {batch['skill_name']} v{batch['skill_version']} ({batch['env']})")
        print(f"  ��间范围: {records[0].get('ts', '?')} ~ {records[-1].get('ts', '?')}")
        return

    # 上报
    print(f"上报 {len(records)} 条事件...")
    ok, msg = upload_via_suggest(batch)
    print(msg)

    if ok:
        # 更新位点
        last_ts = records[-1].get("ts", "")
        if last_ts:
            _save_cursor(last_ts)
            print(f"位点已更新: {last_ts}")


if __name__ == "__main__":
    main()
