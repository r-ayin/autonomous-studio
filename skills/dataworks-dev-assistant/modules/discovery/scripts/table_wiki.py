#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""表使用说明（wiki）读写工具

用法:
    # 查看使用说明
    python table_wiki.py show "表名关键字"
    python table_wiki.py show "项目.表名"
    python table_wiki.py show --entity-id odps.aone_dw.表名
    python table_wiki.py show "表名" --ai-only

    # 写入/更新使用说明（两阶段确认）
    python table_wiki.py edit "表名关键字" --content "使用说明纯文本"
    python table_wiki.py edit --entity-id odps.aone_dw.表名 --file /tmp/wiki.md
    python table_wiki.py edit --confirm
"""

import sys
import os
import argparse
import re

from bff_client import BFFClient, save_tool_result
from search_table import find_table
from telemetry import telemetry_start, telemetry_end, telemetry_fail


_TAG = "[table_wiki]"


def _resolve_entity_id(client, keyword=None, project=None, entity_id=None):
    """从关键字解析出 entityId (格式: odps.项目名.表名)

    优先级: --entity-id > odps.x.y 格式直传 > find_table 搜索 > 项目.表名降级构造
    """
    if entity_id:
        parts = entity_id.split(".")
        if len(parts) == 3:
            return entity_id, parts[2], parts[1]
        return entity_id, entity_id, ""

    if not keyword:
        raise ValueError("请提供表名关键字或 --entity-id")

    if keyword.startswith("odps.") and keyword.count(".") == 2:
        parts = keyword.split(".")
        return keyword, parts[2], parts[1]

    if project is None and "." in keyword:
        parts = keyword.split(".", 1)
        project, keyword = parts[0], parts[1]

    try:
        table = find_table(client, keyword, project=project)
        name = table.get("name", keyword)
        db = table.get("databaseName", "")
        qualified = table.get("qualifiedName", "")
        if qualified:
            return qualified, name, db
        if db:
            return f"odps.{db}.{name}", name, db
    except (ValueError, Exception) as e:
        if project:
            entity_id = f"odps.{project}.{keyword}"
            print(f"  [info] 搜索未命中，降级使用 entityId: {entity_id}", file=sys.stderr)
            return entity_id, keyword, project
        raise ValueError(f"无法确定表的 entityId: {keyword}（{e}）")

    raise ValueError(f"无法确定表的 entityId: {keyword}")


def _text_to_html(text):
    """将纯文本转为简单 HTML（段落包裹）"""
    paragraphs = text.strip().split("\n\n")
    html_parts = []
    for p in paragraphs:
        lines = p.strip().split("\n")
        content = "<br>".join(_escape_html(line) for line in lines)
        html_parts.append(f"<p>{content}</p>")
    return "\n".join(html_parts)


def _escape_html(text):
    """基础 HTML 转义"""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _strip_html(html):
    """从 HTML 中提取纯文本"""
    if not html:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"</p>\s*<p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return text.strip()


def cmd_show(args):
    """查看表的使用说明"""
    if not args.keyword and not args.entity_id:
        print(f"{_TAG} 请提供表名关键字或 --entity-id")
        sys.exit(1)

    telemetry_start("table_wiki.py", module="discovery", action="show",
                    keyword=args.keyword or args.entity_id)
    client = BFFClient(quiet=True)

    entity_id, name, db = _resolve_entity_id(
        client, keyword=args.keyword, project=args.project, entity_id=args.entity_id)
    print(f"表: {name} (项目: {db})")
    print(f"entityId: {entity_id}")

    human_wiki = None
    ai_wiki = None

    if not args.ai_only:
        try:
            human_wiki = client.load("getWiki", entityId=entity_id, type="odps")
        except Exception as e:
            if "not found" not in str(e).lower():
                print(f"  [warn] 获取人工 wiki 失败: {e}", file=sys.stderr)

    if not args.human_only:
        try:
            ai_wiki = client.load("getEntityAiWiki", entityId=entity_id)
        except Exception as e:
            if "not found" not in str(e).lower():
                print(f"  [warn] 获取 AI 说明失败: {e}", file=sys.stderr)

    print()
    if human_wiki and not args.ai_only:
        print("## 人工编写使用说明")
        creator = human_wiki.get("creatorName") or human_wiki.get("creator", "?")
        version = human_wiki.get("version", "?")
        modified = human_wiki.get("gmtModified", "?")
        print(f"  作者: {creator} | 版本: {version} | 更新: {modified}")

        content_html = human_wiki.get("dataSrc", "")
        content_text = _strip_html(content_html) if content_html else "(无内容)"
        print(f"\n{content_text}")
    elif not args.ai_only:
        print("(暂无人工编写说明)")

    if ai_wiki and not args.human_only:
        print("\n## AI 生成使用说明")
        if isinstance(ai_wiki, dict):
            ai_content = ai_wiki.get("content") or ai_wiki.get("dataSrc") or str(ai_wiki)
        else:
            ai_content = str(ai_wiki)
        print(ai_content)
    elif not args.human_only:
        print("\n(暂无 AI 生成说明)")

    telemetry_end(result={"has_human_wiki": bool(human_wiki), "has_ai_wiki": bool(ai_wiki)})
    save_tool_result("table_wiki_show", {
        "entityId": entity_id,
        "table": f"{db}.{name}",
        "human_wiki": human_wiki,
        "ai_wiki": ai_wiki,
    })


def cmd_edit(args):
    """添加/更新表的使用说明"""
    if args.confirm:
        _do_confirm()
        return

    if not args.keyword and not args.entity_id:
        print(f"{_TAG} 请提供表名关键字或 --entity-id")
        sys.exit(1)

    content = args.content
    if args.file:
        if not os.path.exists(args.file):
            print(f"{_TAG} 文件不存在: {args.file}")
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()

    if not content:
        print(f"{_TAG} 请通过 --content 或 --file 提供使用说明内容")
        sys.exit(1)

    telemetry_start("table_wiki.py", module="discovery", action="edit",
                    keyword=args.keyword or args.entity_id)
    client = BFFClient(quiet=True)

    entity_id, name, db = _resolve_entity_id(
        client, keyword=args.keyword, project=args.project, entity_id=args.entity_id)
    print(f"表: {name} (项目: {db})")
    print(f"entityId: {entity_id}")

    existing = None
    try:
        existing = client.load("getWiki", entityId=entity_id, type="odps")
    except Exception:
        pass

    if existing:
        old_text = _strip_html(existing.get("dataSrc", ""))
        if old_text:
            print(f"\n--- 当前使用说明 ---")
            print(old_text[:500])
            if len(old_text) > 500:
                print(f"  ... (共 {len(old_text)} 字)")
            print(f"--- 结束 ---\n")

    html_content = _text_to_html(content)

    client.write("addNewWiki",
                 wikiContent=content,
                 wikiContent2=html_content,
                 entityId=entity_id,
                 type="odps")

    print(f"\n--- 将要写入的内容 ---")
    print(content[:500])
    if len(content) > 500:
        print(f"  ... (共 {len(content)} 字)")
    print(f"--- 结束 ---")
    print(f"\n  → 用户确认后执行: python table_wiki.py edit --confirm")

    telemetry_end(result={"entity_id": entity_id, "content_length": len(content)})


def _do_confirm():
    """Phase 2: 执行待确认的写操作"""
    client = BFFClient(quiet=True)
    result = client.confirm_write()

    print(f"\n{_TAG} 使用说明已更新")
    if isinstance(result, dict):
        wiki_id = result.get("id", "")
        if wiki_id:
            print(f"  wiki ID: {wiki_id}")

    save_tool_result("table_wiki_edit", {"result": result})


def main():
    parser = argparse.ArgumentParser(description="表使用说明（wiki）读写工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # show 子命令
    show_parser = subparsers.add_parser("show", help="查看表的使用说明")
    show_parser.add_argument("keyword", nargs="?", help="表名关键字（支持 '项目.表名' 格式）")
    show_parser.add_argument("--entity-id", help="直接指定 entityId（如 odps.aone_dw.表名），跳过搜索")
    show_parser.add_argument("--project", help="按项目名过滤")
    show_parser.add_argument("--ai-only", action="store_true", help="只显示 AI 生成说明")
    show_parser.add_argument("--human-only", action="store_true", help="只显示人工编写说明")

    # edit 子命令
    edit_parser = subparsers.add_parser("edit", help="添加/更新表的使用说明")
    edit_parser.add_argument("keyword", nargs="?", help="表名关键字（支持 '项目.表名' 格式）")
    edit_parser.add_argument("--entity-id", help="直接指定 entityId（如 odps.aone_dw.表名），跳过搜索")
    edit_parser.add_argument("--project", help="按项目名过滤")
    edit_parser.add_argument("--content", help="使用说明纯文本内容")
    edit_parser.add_argument("--file", help="从文件读取使用说明内容")
    edit_parser.add_argument("--confirm", action="store_true", help="Phase 2: 确认并执行写入")

    args = parser.parse_args()

    if args.command == "show":
        cmd_show(args)
    elif args.command == "edit":
        cmd_edit(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        if e.code and e.code != 0:
            telemetry_fail("table_wiki.py", "discovery", e.code, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("table_wiki.py", "discovery", 1, error=str(e)[:100])
        print(f"\n{_TAG} {e}", file=sys.stderr)
        sys.exit(1)
