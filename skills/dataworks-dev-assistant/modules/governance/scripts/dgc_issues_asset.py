#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按治理项拉问题资产列表（/dgc/listUserIssuesAsset）

比 dgc_rule_findings.py（走 OpenAPI 版 ListGovernanceRuleFindings）返回字段更丰富：
含 visitCount / lastAccessTime / tableSize / recordNum / tableUrl / tags / deductScore /
   ownerDisplayName / ownerYunAccount / projectName / engineProjectName。

适合『热门访问表 + 治理问题』组合场景：按访问热度排序 + 后续 DQC 规则配置闭环。

典型闭环（以 itemCode=18『热门访问表未配置质量规则』为例）：
    1. dgc_overview.py         拿扣分项清单（含 itemCode / name / deduction / count）
    2. dgc_issues_asset.py --item-code 18    拉问题表（默认按 visitCount DESC）
    3. query_columns.py <表>   看字段结构
    4. dqc_spec_builder.py --template <模板> --field <字段> -o gap.yaml   生成规则 spec
    5. dqc_create_rule.py --project-id <id> --table <名> --spec-file gap.yaml   批量配置

用法：
    # 拉热门访问表未配置质量规则的问题表（top 20，按访问热度排）
    dgc_issues_asset.py --item-code 18

    # 按表规模排序
    dgc_issues_asset.py --item-code 18 --sort tableSize --top 10

    # 全局视角（需治理管理员权限）
    dgc_issues_asset.py --item-code 18 --view global

    # 指定工作空间
    dgc_issues_asset.py --item-code 18 --project-id 14255

    # 任务类治理项
    dgc_issues_asset.py --item-code <任务类 itemCode> --issue-type task

    # 结构化输出（供 agent 消费）
    dgc_issues_asset.py --item-code 18 --json
"""

import argparse
import json as _json
import sys

from bff_client import BFFClient


# 映射 ManageTargetEnum.value（后端 ScannerResultCriteria.issueType 字段）
_ISSUE_TYPE_MAP = {
    "table": "11",
    "task": "10",
    "dsapi": "34",
    "safe_compute": "30",
    "safe_transmission": "31",
    "safe_platform": "32",
    "safe_product": "33",
}

# 对应 com.alibaba.dataworks.governance.model.constants.Constants
# GLOBAL_VIEW_TYPE=0 / PROJECT_VIEW_TYPE=1 / PERSONAL_VIEW_TYPE=2
_VIEW_TYPE_MAP = {"personal": 2, "project": 1, "global": 0}


# ── DQC 推荐算法 ────────────────────────────────────────────

_PK_EXACT = {"id", "uid", "uuid", "pk"}
_ENUM_EXACT = {"status", "state", "type", "category", "flag", "level",
               "stat_date", "data_type"}


def _recommend_dqc_for_table(client, row):
    """按 listUserIssuesAsset 的 row 直接查字段 + heuristic 推荐 DQC 规则。

    - 直接用 row.tableGuid（odps.<project>.<table>）转冒号格式构造 listColumns tableId，
      不走 search_table（后者跨 owner/跨工作空间不稳定）。
    - 仅对 MC/ODPS 类表推荐（Hologres/StarRocks 等 DQC 规则语义不同，先跳过）。
    返回：list of dict {template, field?, reason, severity}；跳过时返回 None。
    """
    ds_type = (row.get("dataSourceType") or row.get("dataCategory") or "").upper()
    if ds_type not in ("MC", "ODPS"):
        return {"_skip": True, "_skip_reason": f"非 MaxCompute 表（{ds_type}），当前 DQC 推荐仅支持 MC"}

    table_guid = (row.get("tableGuid") or "").strip()
    if not table_guid.startswith("odps."):
        return None
    parts = table_guid.split(".")
    if len(parts) < 3:
        return None
    table_id = "maxcompute-table:::" + "::".join(parts[1:])

    try:
        columns = client.load("listColumns", tableId=table_id) or []
    except Exception:
        return None

    # 去重（listColumns 可能有重复）
    seen = set()
    cols = []
    for c in sorted(columns, key=lambda x: x.get("position") or 999):
        n = c.get("name")
        if n and n not in seen:
            seen.add(n)
            cols.append(c)

    partition_cols = [c for c in cols if c.get("partitionKey")]
    data_cols = [c for c in cols if not c.get("partitionKey")]

    recs = [{"template": "row_count_gt0", "reason": "基础：表行数非空", "severity": "High"}]

    if partition_cols:
        recs.append({"template": "row_count_flux",
                     "reason": f"分区表（{partition_cols[0].get('name')}）产出波动监测",
                     "severity": "Normal"})

    # 主键字段识别
    pk_candidate = None
    for c in data_cols:
        name = (c.get("name") or "").lower()
        if name in _PK_EXACT or name.endswith("_id") or name.startswith("id_"):
            pk_candidate = c["name"]
            break
    if pk_candidate:
        recs.append({"template": "null_count_0", "field": pk_candidate,
                     "reason": f"疑似主键 {pk_candidate} 非空检查", "severity": "High"})
        recs.append({"template": "duplicate_count_0", "field": pk_candidate,
                     "reason": f"疑似主键 {pk_candidate} 唯一性", "severity": "High"})

    # 枚举字段识别
    for c in data_cols:
        name = (c.get("name") or "").lower()
        if name in _ENUM_EXACT:
            recs.append({"template": "col_distinct_fixed", "field": c["name"],
                         "reason": f"枚举字段 {c['name']} 值范围稳定",
                         "severity": "Normal"})
            break

    return recs[:5]  # 单表最多 5 条


def _emit_recommendations(client, rows, max_detail):
    """对 rows 前 max_detail 个表发起字段推荐；其余给通用兜底提示。"""
    print(f"\n━━━━ DQC 规则推荐（前 {min(max_detail, len(rows))} 张表详细） ━━━━")
    detailed = rows[:max_detail]
    for i, r in enumerate(detailed, 1):
        tbl = r.get("tableName") or r.get("name") or "?"
        db = r.get("engineProjectName") or r.get("projectName") or ""
        pid = r.get("projectId")
        full = f"{db}.{tbl}" if db else tbl

        recs = _recommend_dqc_for_table(client, r)
        print(f"\n[{i}] {full}   (projectId={pid}, visitCount={r.get('visitCount') or '-'})")
        if isinstance(recs, dict) and recs.get("_skip"):
            print(f"     ⏭️ {recs['_skip_reason']}")
            continue
        if recs is None:
            print(f"     ⚠️ 字段识别失败（listColumns 失败）— 兜底跑 row_count_gt0")
            print(f"     dqc_spec_builder.py --template row_count_gt0 -o {tbl}.yaml")
            print(f"     dqc_create_rule.py --project-id {pid} --table \"{full}\" --spec-file {tbl}.yaml")
            continue

        for rec in recs:
            label = f"字段={rec['field']}" if rec.get("field") else "(表级)"
            print(f"     · {rec['template']:<26}{label:<22} {rec['reason']}")

        spec_file = f"{tbl}_dqc.yaml"
        cmds = _build_spec_cmds(recs, spec_file)
        print(f"\n     生成 spec：")
        for c in cmds:
            print(f"       {c}")
        print(f"     批量配置：")
        print(f"       dqc_create_rule.py --project-id {pid} --table \"{full}\" --spec-file {spec_file}")

    if len(rows) > max_detail:
        print(f"\n  ...剩余 {len(rows)-max_detail} 张表：建议最低配 row_count_gt0")
        print(f"     dqc_spec_builder.py --template row_count_gt0 -o fallback.yaml")


def _build_spec_cmds(recs, out_file):
    """把推荐列表转成若干条 dqc_spec_builder 命令（每条一行）。
    - 第一条：表级模板（多 --template 合并），-o 写文件
    - 其余每字段：分别跑一条，stdout 追加到同一个文件
    """
    table_level = [r["template"] for r in recs if not r.get("field")]
    field_groups = {}
    for r in recs:
        if r.get("field"):
            field_groups.setdefault(r["field"], []).append(r["template"])

    cmds = []
    if table_level:
        parts = ["dqc_spec_builder.py"]
        for t in table_level:
            parts.append(f"--template {t}")
        parts.append(f"-o {out_file}")
        cmds.append(" ".join(parts))

    # 字段级规则：每字段一条，stdout 追加（>>）到同一文件
    for field, tmpls in field_groups.items():
        parts = ["dqc_spec_builder.py"]
        for t in tmpls:
            parts.append(f"--template {t}")
        parts.append(f"--field {field}")
        # 没 -o 时 spec_builder 直接 print 到 stdout → 重定向追加
        parts.append(f">> {out_file}")
        cmds.append(" ".join(parts))

    return cmds


def _resolve_item_by_name(client, name_keyword):
    """从 getScannerEnums 按 targetName 关键字反查 (type, targetName, field)。
    支持模糊匹配（substring）；多条匹配时返回第一条并在 stderr 提示。"""
    try:
        items = client.load("getScannerEnums") or []
    except Exception as e:
        return None, f"getScannerEnums 调用失败: {e}"
    items = items if isinstance(items, list) else []
    if not items:
        return None, "getScannerEnums 返回空"

    kw = name_keyword.strip().lower()
    matches = [it for it in items if kw in (it.get("targetName") or "").lower()]
    if not matches:
        return None, f"未找到匹配 '{name_keyword}' 的治理项（共 {len(items)} 条字典项）"
    if len(matches) > 1:
        names = "、".join(f"{m.get('targetName')}(type={m.get('type')})" for m in matches[:5])
        print(f"⚠️ 多条匹配（{len(matches)}）：{names} ... 取第一条", file=sys.stderr)
    it = matches[0]
    return {"type": str(it.get("type")),
            "targetName": it.get("targetName"),
            "field": it.get("field"),
            "target": it.get("target"),
            "solutionId": it.get("solutionId")}, None


def _fmt_num(n):
    if n is None:
        return "-"
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


def _fmt_bytes(n):
    if not n:
        return "-"
    try:
        n = float(n)
    except (TypeError, ValueError):
        return str(n)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}EB"


def _truncate(s, n):
    s = str(s) if s is not None else ""
    return s[:n]


def main():
    p = argparse.ArgumentParser(
        description="按治理项拉问题资产列表（热门问题表）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--item-code",
                   help="治理项编号（= 后端 ruleId）。从 dgc_overview 扣分项取；如 18=热门访问表未配置质量规则")
    p.add_argument("--rule-id", help="等价 --item-code，别名")
    p.add_argument("--item-name",
                   help="治理项中文名（模糊匹配），自动调 getScannerEnums 反查 itemCode。例：--item-name '热门访问表未配置质量规则'")
    p.add_argument("--issue-type", choices=list(_ISSUE_TYPE_MAP.keys()), default="table",
                   help="资产类型（默认 table；映射到后端 ManageTargetEnum value）")
    p.add_argument("--top", type=int, default=20, help="每页条数（默认 20）")
    p.add_argument("--page", type=int, default=1, help="页码（默认 1）")
    p.add_argument("--sort",
                   choices=["visitCount", "lastAccessTime", "tableSize", "recordNum", "deductScore"],
                   default="visitCount", help="排序字段（默认 visitCount）")
    p.add_argument("--sort-dir", choices=["asc", "desc"], default="desc",
                   help="排序方向（默认 desc）")
    p.add_argument("--view", choices=list(_VIEW_TYPE_MAP.keys()), default="personal",
                   help="视角：personal=个人(=2) / project=项目空间(=1) / global=全局(=0，需治理管理员权限)")
    p.add_argument("--owner-id",
                   help="按负责人 baseId 过滤；个人视角默认当前用户")
    p.add_argument("--project-id", type=int, help="按工作空间过滤")
    p.add_argument("--keyword", help="按资产名称模糊")
    p.add_argument("--json", action="store_true", help="结构化 JSON 输出")
    p.add_argument("--recommend-dqc", action="store_true",
                   help="对返回的表调 listColumns 推荐 DQC 规则（仅 --issue-type=table 有效；默认对 top 5 详细推荐，其余给 fallback）")
    p.add_argument("--recommend-top", type=int, default=5,
                   help="详细推荐的表数上限（默认 5）")
    args = p.parse_args()

    client = BFFClient(quiet=True)

    # --item-name 反查 itemCode
    resolved_name = None
    if args.item_name and not (args.rule_id or args.item_code):
        resolved, err = _resolve_item_by_name(client, args.item_name)
        if err:
            print(f"❌ {err}", file=sys.stderr)
            sys.exit(1)
        rule_id = resolved["type"]
        resolved_name = resolved["targetName"]
        print(f"↳ 命中治理项: {resolved_name} (type={rule_id}, field={resolved['field']}, target={resolved['target']}, solution={resolved['solutionId']})", file=sys.stderr)
    else:
        rule_id = args.rule_id or args.item_code

    if not rule_id:
        print("❌ 需要 --item-code / --rule-id / --item-name 三选一", file=sys.stderr)
        print("→ 查扣分项清单: dgc_overview.py（看 itemCode 列）", file=sys.stderr)
        print("→ 查完整治理项字典: python -c \"from bff_client import BFFClient; print([(i['type'], i['targetName']) for i in BFFClient().load('getScannerEnums')])\"", file=sys.stderr)
        sys.exit(1)

    body = {
        "ruleId": str(rule_id),
        "issueType": _ISSUE_TYPE_MAP[args.issue_type],
        "pageNum": args.page,
        "pageSize": args.top,
        "viewType": _VIEW_TYPE_MAP[args.view],
        "queryType": 1,  # 工作台
        "sortField": args.sort,
        "sortDir": args.sort_dir.upper(),
    }

    # 个人视角默认当前用户
    if args.owner_id:
        body["ownerId"] = args.owner_id
    elif args.view == "personal":
        try:
            body["ownerId"] = client.get_my_base_id()
        except Exception:
            pass  # 拉不到让服务端兜底

    if args.project_id:
        body["projectId"] = args.project_id
    if args.keyword:
        body["keyword"] = args.keyword

    try:
        rows = client.load("listUserIssuesAsset", **body) or []
    except Exception as e:
        err_s = str(e)
        print(f"❌ 调用失败: {e}", file=sys.stderr)
        if "治理管理员权限" in err_s or "100300101" in err_s:
            print(f"→ 服务端拒绝了当前视角（viewType={body['viewType']}）。", file=sys.stderr)
            if args.view != "personal":
                print(f"→ 改用个人视角重试：dgc_issues_asset.py --item-code {rule_id} --view personal", file=sys.stderr)
            else:
                print(f"→ 个人视角仍失败，回退 OpenAPI 版：dgc_rule_findings.py --item-code {rule_id}", file=sys.stderr)
        else:
            print(f"→ 确认 --item-code={rule_id} 是否在 dgc_overview.py 扣分项里出现过", file=sys.stderr)
        sys.exit(1)
    rows = rows if isinstance(rows, list) else []

    if args.json:
        print(_json.dumps(rows, ensure_ascii=False, indent=2))
        return

    who = f"当前用户({body.get('ownerId','-')})" if args.view == "personal" else "全局"
    print(f"\n治理项 {rule_id} 问题资产")
    print(f"  视角: {who}   资产类型: {args.issue_type}   排序: {args.sort} {args.sort_dir.upper()}   第 {args.page} 页")
    print()

    if not rows:
        if args.view == "personal":
            print(f"  个人 owner 视角下无此治理项的问题资产 ✅")
            print(f"\n  如用户想看 **全租户范围**（跨 owner、跨工作空间）的问题表，按这些路径降级：")
            print(f"  1. OpenAPI 版（不按 owner 严格过滤，通常能拉更多）:")
            print(f"       dgc_rule_findings.py --item-code {rule_id} --page-size 100")
            print(f"  2. 项目空间视角（需传具体 project-id）:")
            print(f"       dgc_issues_asset.py --item-code {rule_id} --view project --project-id <workspaceId>")
            print(f"  3. 看自己有哪些扣分项: dgc_overview.py")
        else:
            print(f"  当前视角下无问题资产 ✅")
            print(f"\n  → 查扣分项清单: dgc_overview.py")
        return

    if args.issue_type == "table":
        print(f"  {'#':<3} {'资产名':<42} {'访问数':<10} {'规模':<10} {'负责人':<18} {'项目':<20} {'扣分':<8}")
        print(f"  {'-'*3} {'-'*42} {'-'*10} {'-'*10} {'-'*18} {'-'*20} {'-'*8}")
        for i, r in enumerate(rows, 1):
            name = _truncate(r.get("name") or r.get("tableName"), 42)
            visit = _fmt_num(r.get("visitCount"))
            size = _fmt_bytes(r.get("tableSize"))
            owner = _truncate(r.get("ownerDisplayName") or r.get("tableOwner"), 18)
            proj = _truncate(r.get("projectName") or r.get("engineProjectName"), 20)
            score = r.get("deductScore")
            score_s = f"{score:.3f}" if isinstance(score, (int, float)) else "-"
            print(f"  {i:<3} {name:<42} {visit:<10} {size:<10} {owner:<18} {proj:<20} {score_s:<8}")

        total_score = sum(
            (r.get("deductScore") or 0) for r in rows
            if isinstance(r.get("deductScore"), (int, float))
        )
        print(f"\n  合计扣分（前 {len(rows)} 条）: {total_score:.3f}")

        first_url = rows[0].get("tableUrl")
        if first_url:
            print(f"  数据地图直达（第 1 条）: {first_url}")
    else:
        for i, r in enumerate(rows, 1):
            name = r.get("name") or r.get("nodeName") or "?"
            owner = r.get("ownerDisplayName") or r.get("nodeOwner") or "?"
            print(f"  {i}. {name}  (owner={owner})")

    # --recommend-dqc: 对 table 类型触发推荐
    if args.recommend_dqc and args.issue_type == "table" and rows:
        _emit_recommendations(client, rows, args.recommend_top)

    # 下一步引导
    print(f"\n下一步")
    if args.issue_type == "table":
        t = rows[0]
        table_name = t.get("tableName") or t.get("name") or "?"
        proj = t.get("engineProjectName") or t.get("projectName") or "?"
        t_full = f"{proj}.{table_name}" if proj != "?" else table_name
        if str(rule_id) == "18":
            # 热门访问表未配置质量规则 → DQC 配置引导
            print(f"  (治理项 18：热门访问表未配置质量规则 → 按下方 3 步批量配置 DQC)")
            print(f"  1. 看样本表字段: query_columns.py \"{t_full}\"")
            print(f"  2. 生成 DQC spec:  dqc_spec_builder.py --template row_count_gt0 --template null_count_0 --field <id> -o gap.yaml")
            print(f"  3. 批量配置规则:    dqc_create_rule.py --project-id <id> --table \"{t_full}\" --spec-file gap.yaml")
        else:
            print(f"  → 看样本表详情:  identify.py \"{t_full}\"")
    print(f"  → 看所有扣分项:   dgc_overview.py")
    if len(rows) >= args.top:
        print(f"  → 下一页:         dgc_issues_asset.py --item-code {rule_id} --page {args.page + 1} --top {args.top}")


if __name__ == "__main__":
    main()
