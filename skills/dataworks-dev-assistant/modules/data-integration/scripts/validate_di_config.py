#!/usr/bin/env python3
"""
DI 离线同步任务 JSON 配置校验脚本（CLI 瘦壳）

核心校验逻辑在 spec_builder/validation/schema_validator.py。

用法：
  python validate_di_config.py -f <json_file>
  python validate_di_config.py -j '<json_string>'
  cat config.json | python validate_di_config.py --stdin

退出码：
  0 - 校验通过
  1 - 校验失败
"""

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_MODULE_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_MODULE_DIR))

from spec_builder.validation.schema_validator import DIConfigValidator
from telemetry import telemetry_start, telemetry_end, telemetry_fail


def _format_report(is_valid, errors, warnings):
    lines = ["=" * 60]
    lines.append("✅ DI 配置校验通过" if is_valid else "❌ DI 配置校验失败")
    lines.append("=" * 60)
    if errors:
        lines.append(f"\n错误 ({len(errors)} 项):")
        for i, e in enumerate(errors, 1):
            lines.append(f"  {i}. {e}")
    if warnings:
        lines.append(f"\n警告 ({len(warnings)} 项):")
        for i, w in enumerate(warnings, 1):
            lines.append(f"  {i}. {w}")
    lines.append("")
    if is_valid and not warnings:
        lines.append("所有校验项均通过，可以进行后续的节点创建和部署操作。")
    elif is_valid:
        lines.append("校验通过（存在警告），建议处理后再进行部署。")
    else:
        lines.append("请根据以上错误信息修复 JSON 配置后重新校验。")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="DI 离线同步任务 JSON 配置校验工具")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", "-f", help="JSON 配置文件路径")
    group.add_argument("--json", "-j", help="JSON 配置字符串")
    group.add_argument("--stdin", action="store_true", help="从 stdin 读取 JSON")
    parser.add_argument("--schema-dir", "-s", help="Schema 目录路径")
    args = parser.parse_args()

    telemetry_start("validate_di_config.py", module="data-integration")

    try:
        if args.file:
            with open(args.file, "r", encoding="utf-8") as f:
                config = json.load(f)
        elif args.stdin:
            config = json.load(sys.stdin)
        else:
            config = json.loads(args.json)
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"❌ 文件未找到: {e}")
        sys.exit(1)

    validator = DIConfigValidator(schema_dir=args.schema_dir)
    is_valid, errors, warnings = validator.validate(config)
    print(_format_report(is_valid, errors, warnings))
    telemetry_end(result={"is_valid": is_valid, "error_count": len(errors)})
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("validate_di_config.py", "data-integration", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("validate_di_config.py", "data-integration", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
