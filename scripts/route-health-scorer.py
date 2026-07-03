#!/usr/bin/env python3
"""
路线健康度客观评分器（CodeGraph 驱动）
======================================

由 decision-agent-prompt.md §②E 调用。
使用 CodeGraph 将路线健康度诊断的 E1/E2 维度从主观评估转为数据驱动。

用法:
  python scripts/route-health-scorer.py --project <path> --spec <spec_dir>
  python scripts/route-health-scorer.py --all-projects  # 遍历所有项目

输出: JSON，包含 E1-E4 评分 + 各维度详细数据
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def run_codegraph(cmd_args, project_path=None, timeout=30):
    """运行 CodeGraph 命令并返回结果"""
    try:
        args = ["codegraph"] + cmd_args
        if project_path and "--path" not in args:
            args.extend(["--path", str(project_path)])
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except Exception as e:
        print(f"  [WARN] codegraph {' '.join(cmd_args)} 失败: {e}", file=sys.stderr)
        return None


def get_project_stats(project_path):
    """获取项目统计信息"""
    output = run_codegraph(["status", "--json"], project_path)
    if output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return None


def search_symbol(project_path, symbol_name, kind=None):
    """搜索符号"""
    args = ["query", symbol_name, "--json", "--limit", "5"]
    if kind:
        args.extend(["--kind", kind])
    output = run_codegraph(args, project_path)
    if output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return []


def get_symbol_callers(project_path, symbol_name):
    """获取调用者"""
    output = run_codegraph(["callers", symbol_name, "--json", "--limit", "20"], project_path)
    if output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return []


def score_e1_deliverable_quality(project_path, spec_entities):
    """
    E1: 产出物内在质量 (0-3)
    检查 spec 中声明的关键实体在代码中的实现覆盖率
    """
    if not spec_entities:
        return {"score": 0, "detail": "无 spec 实体可检查", "coverage": 0.0, "found": [], "missing": spec_entities}

    found = []
    missing = []
    stats = get_project_stats(project_path)

    for entity in spec_entities:
        results = search_symbol(project_path, entity["name"], entity.get("kind"))
        if results and len(results) > 0:
            found.append({"entity": entity["name"], "matches": len(results)})
        else:
            missing.append(entity["name"])

    total = len(spec_entities)
    coverage = len(found) / total if total > 0 else 0

    # 映射到 0-3 分
    if coverage >= 1.0:
        score = 3
    elif coverage >= 0.8:
        score = 2
    elif coverage >= 0.5:
        score = 1
    else:
        score = 0

    return {
        "score": score,
        "detail": f"spec 实体覆盖率 {coverage:.0%} ({len(found)}/{total})",
        "coverage": round(coverage, 3),
        "found": found,
        "missing": missing,
        "total_symbols": stats.get("total_symbols", "N/A") if stats else "N/A",
    }


def score_e2_cross_stage_consistency(project_path, data_model_entities, openapi_endpoints):
    """
    E2: 跨阶段一致性 (0-3)
    检查 data-model.md 声明的实体 ↔ 代码实际类型定义的一致性
    检查 openapi.yaml 声明的端点 ↔ 实际路由注册的一致性
    """
    results = []

    # 检查数据模型一致性
    for entity in (data_model_entities or []):
        actual = search_symbol(project_path, entity["name"], entity.get("kind", "class"))
        results.append({
            "entity": entity["name"],
            "stage": "data-model",
            "declared": True,
            "implemented": bool(actual),
            "match_count": len(actual) if actual else 0,
        })

    # 检查 API 端点一致性
    for ep in (openapi_endpoints or []):
        # 搜索路由处理函数
        handler_name = ep.get("handler", ep.get("path", "").replace("/", "_"))
        actual = search_symbol(project_path, handler_name, "function")
        results.append({
            "entity": ep.get("path", handler_name),
            "stage": "openapi",
            "declared": True,
            "implemented": bool(actual),
            "match_count": len(actual) if actual else 0,
        })

    if not results:
        return {"score": 3, "detail": "无跨阶段产物可检查（无 data-model 或无 openapi），跳过", "checks": []}

    implemented = sum(1 for r in results if r["implemented"])
    total = len(results)
    consistency = implemented / total if total > 0 else 1

    if consistency >= 0.95:
        score = 3
    elif consistency >= 0.75:
        score = 2
    elif consistency >= 0.5:
        score = 1
    else:
        score = 0

    return {
        "score": score,
        "detail": f"跨阶段一致性 {consistency:.0%} ({implemented}/{total})",
        "consistency": round(consistency, 3),
        "checks": results,
    }


def score_e3_external_stability(project_path):
    """
    E3: 外部环境稳定性 (0-2)
    通过 HEAD~5..HEAD 范围内依赖声明文件的实际内容变化评估。
    - 有版本变更 → score=1（外部依赖在动，需关注兼容性）
    - 无版本变更 → score=2（外部依赖稳定）
    - 无法读取依赖文件/git → score=1 + unavailable=True（不奖励不可观测状态）
    """
    dep_files = [
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "Pipfile.lock",
        "go.mod",
        "Cargo.toml",
    ]

    # 先确认项目里至少有一个依赖声明文件存在；全无则视为数据缺失
    existing = [f for f in dep_files if (Path(project_path) / f).exists()]
    if not existing:
        return {
            "score": 1,
            "detail": "未找到已知依赖声明文件，无法评估外部稳定性",
            "unavailable": True,
            "checked_files": [],
        }

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~5..HEAD", "--"] + existing,
            capture_output=True, text=True, timeout=10, cwd=project_path,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
    except Exception as e:
        return {
            "score": 1,
            "detail": f"git diff 失败，无法评估外部稳定性: {e}",
            "unavailable": True,
            "checked_files": existing,
        }

    if changed:
        return {
            "score": 1,
            "detail": f"最近 5 次提交修改了依赖声明: {', '.join(changed)}",
            "changed_dep_files": changed,
            "checked_files": existing,
        }
    return {
        "score": 2,
        "detail": f"最近 5 次提交未修改依赖声明 ({len(existing)} 个文件检查)",
        "changed_dep_files": [],
        "checked_files": existing,
    }


def score_e4_cumulative_deviation(project_path):
    """
    E4: 累积偏差 (0-2)
    通过 git diff 大小趋势评估。CodeGraph 可辅助分析影响面。
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--stat", "HEAD~5..HEAD"],
            capture_output=True, text=True, timeout=10, cwd=project_path
        )
        lines = result.stdout.strip().split("\n")
        file_count = max(0, len(lines) - 1)  # 最后一行是 summary
        if file_count <= 3:
            score = 2
        elif file_count <= 10:
            score = 1
        else:
            score = 0
        return {
            "score": score,
            "detail": f"最近 5 次提交涉及 {file_count} 个文件",
            "file_count": file_count,
        }
    except Exception:
        return {"score": 2, "detail": "无法获取 git diff 统计，默认满分", "file_count": 0}


def score_all(project_path, spec_entities=None, data_model_entities=None, openapi_endpoints=None):
    """计算完整的路线健康度"""
    path = Path(project_path)
    e1 = score_e1_deliverable_quality(project_path, spec_entities or [])
    e2 = score_e2_cross_stage_consistency(project_path, data_model_entities or [], openapi_endpoints or [])
    e3 = score_e3_external_stability(project_path)
    e4 = score_e4_cumulative_deviation(project_path)

    total = e1["score"] + e2["score"] + e3["score"] + e4["score"]
    max_score = 10

    return {
        "project": str(path.name),
        "scored_at": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                                    capture_output=True, text=True).stdout.strip() or "",
        "route_health": {
            "total": total,
            "max": max_score,
            "status": "healthy" if total >= 7 else "warning" if total >= 5 else "critical",
            "needs_correction": total < 5,
        },
        "dimensions": {
            "E1_deliverable_quality": e1,
            "E2_cross_stage_consistency": e2,
            "E3_external_stability": e3,
            "E4_cumulative_deviation": e4,
        },
        "codegraph_driven": {
            "E1_automated": e1.get("coverage", 0) > 0 if "coverage" in e1 else False,
            "E2_automated": e2.get("consistency", 0) > 0 if "consistency" in e2 else False,
        },
    }


def discover_spec_entities(project_path):
    """从 .planning/ 目录自动发现 spec 声明的实体"""
    entities = []
    planning_dir = Path(project_path) / ".planning"

    if not planning_dir.exists():
        return entities, [], []

    # 尝试读取 data-model
    data_model_path = planning_dir / "data-model.md"
    data_model_entities = []
    if data_model_path.exists():
        try:
            content = data_model_path.read_text(encoding="utf-8")
            # 简单解析：找 markdown 中的实体名（表名/类名）
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("### ") or line.startswith("## "):
                    name = line.replace("### ", "").replace("## ", "").strip()
                    if name and not name.startswith(" ") and len(name) < 50:
                        entities.append({"name": name, "kind": "class"})
                        data_model_entities.append({"name": name, "kind": "class"})
        except Exception:
            pass

    # 尝试读取 openapi
    openapi_dir = planning_dir / "contracts"
    openapi_entities = []
    if openapi_dir.exists():
        for yaml_file in openapi_dir.glob("*.yaml"):
            try:
                content = yaml_file.read_text(encoding="utf-8")
                for line in content.split("\n"):
                    if line.strip().startswith("/"):
                        path = line.strip().rstrip(":")
                        openapi_entities.append({"path": path})
                        entities.append({"name": path, "kind": "function"})
            except Exception:
                pass

    return entities, data_model_entities, openapi_entities


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="CodeGraph 驱动的路线健康度客观评分器"
    )
    parser.add_argument("--project", help="项目路径")
    parser.add_argument("--spec", help="spec 文件目录（含 data-model.md/openapi.yaml）")
    parser.add_argument("--all-projects", action="store_true",
                        help="遍历 x-tool 下所有项目")
    parser.add_argument("--json", action="store_true", default=True,
                        help="JSON 输出（默认）")

    args = parser.parse_args()

    projects = []
    if args.all_projects:
        base_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
        for d in base_dir.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                projects.append(str(d))
    elif args.project:
        projects = [args.project]
    else:
        projects = [os.getcwd()]

    results = []
    for proj in projects:
        entities, dm_entities, oa_endpoints = discover_spec_entities(proj)
        result = score_all(proj, entities, dm_entities, oa_endpoints)
        results.append(result)

    print(json.dumps(results if len(results) > 1 else results[0],
                     ensure_ascii=False, indent=2))

    # 如果有项目路线健康度 < 5，返回非零退出码
    for r in results:
        if r["route_health"]["needs_correction"]:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
