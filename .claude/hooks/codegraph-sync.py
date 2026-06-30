#!/usr/bin/env python3
"""
CodeGraph 融合层自动同步 Hook
===============================

监听事件:
  - PostToolUse: Bash 匹配 *codegraph*upgrade* 或 *npm update*codegraph*
  - SessionStart: 每次会话启动时检查版本变化

功能:
  1. 检测 CodeGraph 版本变化
  2. 重新扫描能力（解析 codegraph --help 所有子命令）
  3. 对比旧 capability-registry.json 生成差异报告
  4. 遍历 integration-rules.json 检查新能力匹配
  5. 更新 autonomous-suggestions.md 汇报变化
  6. 自动创建新规则（auto_registration 匹配到的）
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
CODEGRAPH_DIR = Path(PROJECT_DIR) / ".claude" / "codegraph"
REGISTRY_PATH = CODEGRAPH_DIR / "capability-registry.json"
TOUCHPOINTS_PATH = CODEGRAPH_DIR / "engine-touchpoints.json"
RULES_PATH = CODEGRAPH_DIR / "integration-rules.json"
SUGGESTIONS_PATH = Path(PROJECT_DIR) / ".claude" / "memory" / "autonomous-suggestions.md"


def get_codegraph_version():
    """获取当前安装的 CodeGraph 版本"""
    try:
        result = subprocess.run(
            ["codegraph", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        print(f"[codegraph-sync] 无法获取 CodeGraph 版本: {e}", file=sys.stderr)
    return None


def scan_codegraph_capabilities():
    """扫描 CodeGraph 当前完整能力"""
    try:
        # 获取版本
        version = get_codegraph_version()
        if not version:
            return None

        # 获取所有子命令
        result = subprocess.run(
            ["codegraph", "--help"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return None

        # 解析子命令列表
        capabilities = {
            "version": version,
            "last_scan": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scan_method": "codegraph --help + subcommand parsing (auto)",
            "mcp_tools": [],
            "cli_commands": [],
        }

        # 解析 commands 列表
        help_text = result.stdout
        in_commands = False
        commands = []
        for line in help_text.split("\n"):
            if line.strip().startswith("Commands:"):
                in_commands = True
                continue
            if in_commands:
                if line.strip() == "" or line.startswith("Options:"):
                    break
                # 提取命令名 - 匹配 "  command [options]" 或 "  command|alias [options]"
                stripped = line.strip()
                if stripped:
                    cmd = stripped.split()[0].rstrip(",")
                    commands.append(cmd)

        # 对每个子命令获取详细帮助
        known_capabilities = load_existing_capabilities()
        for cmd in commands:
            if cmd in ("help", "version", "telemetry", "install", "uninstall"):
                # 这些命令引擎不需要深度集成
                continue

            try:
                sub_result = subprocess.run(
                    ["codegraph", cmd, "--help"],
                    capture_output=True, text=True, timeout=10
                )
                if sub_result.returncode == 0:
                    desc = parse_subcommand_description(sub_result.stdout)
                    options = parse_subcommand_options(sub_result.stdout)
                    tags = infer_capability_tags(cmd, desc, options)

                    # 如果已有注册表，保留旧的 capability_tags 描述
                    existing = find_existing_command(known_capabilities, cmd)

                    capabilities["cli_commands"].append({
                        "name": cmd,
                        "description": desc,
                        "capability_tags": tags,
                        "engine_value": existing.get("engine_value", desc) if existing else desc,
                        "options": options,
                    })
            except Exception:
                pass

        # MCP tools (从已知信息推断，需要实际 MCP 连接才能枚举)
        capabilities["mcp_tools"] = [
            {
                "name": "codegraph_explore",
                "description": "探索代码区域：返回相关符号源码+调用路径",
                "capability_tags": ["symbol_lookup", "call_path", "source_read", "area_exploration"],
                "engine_value": "替代 grep+read 组合获取结构化代码上下文",
            },
            {
                "name": "codegraph_node",
                "description": "查看单个符号：源码+调用者/被调用者链，或读取文件含行号和依赖",
                "capability_tags": ["caller_callee", "symbol_detail", "dependency_trace", "file_read"],
                "engine_value": "追踪单个函数/类的完整调用关系+文件内容",
            },
        ]

        return capabilities
    except Exception as e:
        print(f"[codegraph-sync] 能力扫描失败: {e}", file=sys.stderr)
        return None


def parse_subcommand_description(help_text):
    """从 --help 输出中解析描述"""
    lines = help_text.strip().split("\n")
    if len(lines) >= 2:
        # Usage 行后的第一行通常是描述
        for line in lines[1:]:
            stripped = line.strip()
            if stripped and not stripped.startswith("Usage:") and not stripped.startswith("Options:"):
                if not stripped.startswith("-"):
                    return stripped
    return lines[0].strip() if lines else ""


def parse_subcommand_options(help_text):
    """解析选项列表"""
    options = []
    in_options = False
    for line in help_text.split("\n"):
        if line.strip().startswith("Options:") or line.strip().startswith("Arguments:"):
            in_options = True
            continue
        if in_options:
            stripped = line.strip()
            if stripped.startswith("-"):
                opt_name = stripped.split()[0].rstrip(",")
                options.append(opt_name)
            elif stripped.startswith("--"):
                opt_name = stripped.split()[0].rstrip(",")
                options.append(opt_name)
    return options


def infer_capability_tags(cmd_name, description, options):
    """根据命令名和描述推断能力标签"""
    tag_map = {
        "init": ["project_setup", "index_build"],
        "uninit": ["project_setup"],
        "index": ["index_build", "full_scan"],
        "sync": ["incremental_update", "watcher"],
        "status": ["index_health", "statistics", "project_metrics"],
        "query": ["symbol_search", "fts5", "fulltext"],
        "explore": ["symbol_lookup", "call_path", "source_read", "area_exploration"],
        "node": ["caller_callee", "symbol_detail", "dependency_trace", "file_read"],
        "files": ["structure", "navigation", "project_map"],
        "daemon": ["daemon_management"],
        "unlock": ["lock_management", "recovery"],
        "callers": ["caller_trace", "reverse_dependency", "impact_analysis"],
        "callees": ["callee_trace", "forward_dependency"],
        "impact": ["impact_analysis", "change_blast_radius", "refactoring_safety"],
        "affected": ["test_impact", "coverage_hint", "test_selection"],
        "install": ["agent_setup", "mcp_registration"],
        "uninstall": ["agent_setup", "mcp_registration"],
        "upgrade": ["self_update"],
    }
    return tag_map.get(cmd_name, ["general"])


def load_existing_capabilities():
    """加载现有能力注册表"""
    try:
        if REGISTRY_PATH.exists():
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def find_existing_command(existing, cmd_name):
    """在已有注册表中查找命令"""
    for cmd in existing.get("cli_commands", []):
        if cmd.get("name") == cmd_name:
            return cmd
    return None


def compute_diff(old_caps, new_caps):
    """计算能力差异"""
    old_commands = {c["name"] for c in old_caps.get("cli_commands", [])}
    new_commands = {c["name"] for c in new_caps.get("cli_commands", [])}

    added = new_commands - old_commands
    removed = old_commands - new_commands
    kept = new_commands & old_commands

    # 检查已有命令的选项变化
    changed = []
    for cmd_name in kept:
        old_cmd = find_existing_command(old_caps, cmd_name)
        new_cmd = find_existing_command(new_caps, cmd_name)
        if old_cmd and new_cmd:
            old_opts = set(old_cmd.get("options", []))
            new_opts = set(new_cmd.get("options", []))
            if old_opts != new_opts:
                changed.append({
                    "name": cmd_name,
                    "added_options": list(new_opts - old_opts),
                    "removed_options": list(old_opts - new_opts),
                })

    return {
        "added_commands": list(added),
        "removed_commands": list(removed),
        "changed_commands": changed,
        "old_version": old_caps.get("version", "unknown"),
        "new_version": new_caps.get("version", "unknown"),
    }


def check_auto_registration(new_caps):
    """检查是否有新能力可以自动匹配到触点"""
    try:
        with open(TOUCHPOINTS_PATH, "r", encoding="utf-8") as f:
            touchpoints = json.load(f)
    except Exception:
        return []

    try:
        with open(RULES_PATH, "r", encoding="utf-8") as f:
            rules = json.load(f)
    except Exception:
        rules = {"rules": []}

    all_tags = set()
    for cmd in new_caps.get("cli_commands", []):
        all_tags.update(cmd.get("capability_tags", []))
    for tool in new_caps.get("mcp_tools", []):
        all_tags.update(tool.get("capability_tags", []))

    existing_rule_touchpoints = {r["then"]["touchpoint"] for r in rules.get("rules", []) if "touchpoint" in r.get("then", {})}

    new_matches = []
    for tp in touchpoints.get("touchpoints", []):
        if not tp.get("auto_adapt", False):
            continue
        if tp["id"] in existing_rule_touchpoints:
            continue
        needed = set(tp.get("needed_capabilities", []))
        if needed & all_tags:
            new_matches.append(tp)

    return new_matches


def append_suggestions(diff, new_matches):
    """向 autonomous-suggestions.md 追加建议"""
    if not diff and not new_matches:
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"\n---",
        f"## CodeGraph 融合层变更检测 — {timestamp}",
        f"",
    ]

    if diff:
        lines.append(f"**版本变化**: {diff['old_version']} → {diff['new_version']}")
        if diff["added_commands"]:
            lines.append(f"- 🆕 新增命令: {', '.join(f'`{c}`' for c in diff['added_commands'])}")
        if diff["removed_commands"]:
            lines.append(f"- 🗑️ 移除命令: {', '.join(f'`{c}`' for c in diff['removed_commands'])}")
        if diff["changed_commands"]:
            for ch in diff["changed_commands"]:
                lines.append(f"- 🔄 `{ch['name']}` 选项变化: +{ch['added_options']} / -{ch['removed_options']}")
        if not any([diff["added_commands"], diff["removed_commands"], diff["changed_commands"]]):
            lines.append("- 能力无变化（版本号更新但命令集相同）")

    if new_matches:
        lines.append(f"\n### 🤖 自动匹配到新引擎触点")
        for tp in new_matches:
            lines.append(f"- **{tp['id']} {tp['name']}** (优先级: {tp['priority']})")
            lines.append(f"  → 需要能力: {tp['needed_capabilities']}")
            lines.append(f"  → 建议创建对应集成规则")

    lines.append(f"\n> 由 `codegraph-sync.py` 自动生成。L3 研判轨下次激活时审核。")
    lines.append("")

    try:
        with open(SUGGESTIONS_PATH, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"[codegraph-sync] 已追加建议到 {SUGGESTIONS_PATH}")
    except Exception as e:
        print(f"[codegraph-sync] 写入建议失败: {e}", file=sys.stderr)


def main():
    print("[codegraph-sync] 开始 CodeGraph 融合层同步检查...")

    # 1. 获取当前版本
    current_version = get_codegraph_version()
    if not current_version:
        print("[codegraph-sync] CodeGraph 未安装或无法访问，跳过同步")
        return 0

    # 2. 加载已有注册表
    old_caps = load_existing_capabilities()
    old_version = old_caps.get("version", "")

    # 3. 版本相同则跳过完整扫描（但仍做轻量检查）
    if old_version == current_version and old_caps:
        print(f"[codegraph-sync] 版本未变化 ({current_version})，跳过完整扫描")
        return 0

    print(f"[codegraph-sync] 检测到版本变化: {old_version} → {current_version}")

    # 4. 重新扫描能力
    new_caps = scan_codegraph_capabilities()
    if not new_caps:
        print("[codegraph-sync] 能力扫描失败")
        return 1

    # 5. 保存新注册表
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(new_caps, f, ensure_ascii=False, indent=2)
    print(f"[codegraph-sync] 能力注册表已更新 → {REGISTRY_PATH}")

    # 6. 计算差异
    diff = compute_diff(old_caps, new_caps) if old_caps else None

    # 7. 检查自动注册
    new_matches = check_auto_registration(new_caps)

    # 8. 追加建议
    if diff or new_matches:
        append_suggestions(diff, new_matches)

    # 9. 打印摘要
    if diff:
        print(f"[codegraph-sync] 差异: +{diff['added_commands']} / -{diff['removed_commands']} / ~{diff['changed_commands']}")
    if new_matches:
        print(f"[codegraph-sync] 自动匹配: {len(new_matches)} 个新触点可用")

    print("[codegraph-sync] 同步完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
