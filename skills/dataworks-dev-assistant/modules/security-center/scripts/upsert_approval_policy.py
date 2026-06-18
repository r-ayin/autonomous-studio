#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""创建/更新审批策略（两阶段写操作，接 JSON 配置）

配置字段复杂（ruleConditions / approvalNodes / notificationServices），CLI 参数表达不清
→ 统一走 --config-json 传完整 body。参考字段见 SKILL.md 或 references/ 的 examples。

用法:
    # 创建（Phase 1 preview）
    python upsert_approval_policy.py --config-json ./policy.json

    # 更新（Phase 1 preview；带 --id 转为 update）
    python upsert_approval_policy.py --id <workflowId> --config-json ./policy.json

    # Phase 2 执行
    python upsert_approval_policy.py --confirm

⚠️ 参考 skill: base-tenant-skills/security-process-definition
   里有 policy_config.example.json 及对话式引导实现，可作为填 config.json 的参考。
"""

import argparse
import json
import sys

from bff_client import BFFClient


def _load_config(path):
    try:
        with open(path) as f:
            cfg = json.load(f)
    except OSError as e:
        print(f"读配置失败: {path} ({e})", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"配置非合法 JSON: {path} ({e})", file=sys.stderr)
        sys.exit(1)
    if not isinstance(cfg, dict):
        print(f"配置根不是 dict: {type(cfg).__name__}", file=sys.stderr)
        sys.exit(1)
    return cfg


def main():
    p = argparse.ArgumentParser(description="创建/更新审批策略")
    p.add_argument("--id", help="workflowId（有此参数 → update，否则 → create）")
    p.add_argument("--config-json", help="策略 body 的 JSON 文件路径（Phase 1 必填）")
    p.add_argument("--confirm", action="store_true", help="Phase 2: 执行")
    args = p.parse_args()

    client = BFFClient()

    if args.confirm:
        client.confirm_write()
        return

    if not args.config_json:
        p.error("Phase 1 必填 --config-json")

    cfg = _load_config(args.config_json)

    # 关键字段检查
    missing = [f for f in ("name", "type", "subType") if not cfg.get(f)]
    if missing:
        print(f"⚠️ config 缺关键字段: {missing}（继续 preview，用户确认时可发现）")

    if args.id:
        cfg["id"] = args.id
        api_name = "updateProcessDefinition"
        op = "更新"
    else:
        api_name = "createProcessDefinition"
        op = "创建"

    print(f"━━ {op}审批策略 preview ━━")
    print(f"  name:          {cfg.get('name', '-')}")
    print(f"  type/subType:  {cfg.get('type', '-')} / {cfg.get('subType', '-')}")
    print(f"  desc:          {cfg.get('desc', '-')}")
    print(f"  ruleConditions:       {len(cfg.get('ruleConditions', []))} 条")
    print(f"  approvalNodes:        {len(cfg.get('approvalNodes', []))} 个")
    print(f"  notificationServices: {len(cfg.get('notificationServices', []))} 个")
    print(f"  enabled:       {cfg.get('enabled', 'N/A')}")

    client.write(api_name, **cfg)
    print(f"\n→ 用户确认后: upsert_approval_policy.py --confirm")


if __name__ == "__main__":
    main()
