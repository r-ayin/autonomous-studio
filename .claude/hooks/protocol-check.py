"""protocol-check.py — project-protocol 自举 Hook
PreToolUse:Write/Edit 触发。项目缺少三件套 → 自动从模板生成（不阻塞工作）。
"""
import os
import sys
import json

# Windows UTF-8 编码修复
if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORKSPACE_ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
SKILL_DIR = os.path.join(WORKSPACE_ROOT, ".claude", "skills", "project-protocol")
BOOTSTRAP_SCRIPT = os.path.join(SKILL_DIR, "bootstrap.py")

REQUIRED_FILES = ["CLAUDE.md", "PROGRESS.md", "GATES.md"]


def get_project_dir(file_path: str) -> tuple:
    """从文件路径推断项目目录"""
    try:
        rel = os.path.relpath(file_path, WORKSPACE_ROOT)
    except ValueError:
        # 跨驱动器路径（Windows 特有），无法计算相对路径
        return None, None
    parts = rel.replace("\\", "/").split("/")

    # 跳过 .claude / node_modules 等特殊目录
    skip_prefixes = (".claude", "node_modules", ".git", "__pycache__", ".venv")
    for part in parts:
        if any(part.startswith(p) for p in skip_prefixes):
            return None, None

    project_name = parts[0] if parts[0] not in (".", "..") else None
    if project_name is None:
        return None, None

    project_dir = os.path.join(WORKSPACE_ROOT, project_name)
    if not os.path.isdir(project_dir):
        return None, None

    # 不是目录型项目（是单文件）则跳过
    if os.path.isfile(project_dir):
        return None, None

    return project_name, project_dir


def check_and_bootstrap(project_name: str, project_dir: str) -> dict:
    """检查三件套，缺失则调 bootstrap 生成"""
    missing = []
    for f in REQUIRED_FILES:
        if not os.path.isfile(os.path.join(project_dir, f)):
            missing.append(f)

    if not missing:
        return {"ok": True, "project": project_name, "action": "none"}

    # 尝试自举生成
    if not os.path.isfile(BOOTSTRAP_SCRIPT):
        return {"ok": False, "project": project_name, "missing": missing,
                "action": "bootstrap_unavailable"}

    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, BOOTSTRAP_SCRIPT, os.path.join(project_dir, "dummy")],
            capture_output=True, text=True, encoding="utf-8", timeout=10,
            env={**os.environ, "CLAUDE_PROJECT_DIR": WORKSPACE_ROOT}
        )
        if result.returncode == 0:
            return {"ok": True, "project": project_name,
                    "action": "bootstrapped", "created": missing}
        else:
            return {"ok": False, "project": project_name, "missing": missing,
                    "action": "bootstrap_failed", "error": result.stderr}
    except Exception as e:
        return {"ok": False, "project": project_name, "missing": missing,
                "action": "bootstrap_error", "error": str(e)}


def main():
    try:
        input_data = json.loads(sys.stdin.read())
        file_path = input_data.get("tool_input", {}).get("file_path", "")
    except Exception:
        file_path = sys.argv[1] if len(sys.argv) > 1 else ""

    if not file_path:
        print(json.dumps({"protocol_check": "skipped", "reason": "no file_path"}))
        return

    project_name, project_dir = get_project_dir(file_path)

    if project_name is None:
        print(json.dumps({"protocol_check": "skipped", "reason": "not a project dir"}))
        return

    result = check_and_bootstrap(project_name, project_dir)

    # ★ Studio 融合：检查 planning/ 目录完整性（解决遗漏H）
    status_file = os.path.join(project_dir, "planning", "status.json")
    if os.path.exists(status_file):
        try:
            import json as _json
            with open(status_file, "r", encoding="utf-8") as f:
                status = _json.load(f)
            if status.get("locked"):
                stage = status.get("currentStage", "unknown")
                # 检查当前阶段所需的产出物
                stage_artifacts = {
                    "prd": ["planning/prd.md", "planning/requirements.md"],
                    "tech-plan": ["planning/prd.md", "planning/test-cases.md"],
                    "development": ["planning/tech-plan.md"],
                    "verification": ["planning/test-cases.md"],
                }
                required = stage_artifacts.get(stage, [])
                missing_artifacts = [
                    a for a in required
                    if not os.path.exists(os.path.join(project_dir, a))
                ]
                if missing_artifacts:
                    msg = f"[STUDIO] ⚠️ 阶段 {stage} 缺少产出物: {missing_artifacts}"
                    sys.stderr.write(msg + "\n")
        except Exception:
            pass

    if result["ok"]:
        if result["action"] == "bootstrapped":
            msg = f"[PROTOCOL] 🚀 '{project_name}' 三件套已自动生成: {result['created']}"
            sys.stderr.write(msg + "\n")
        status = "passed" if result["action"] == "none" else "bootstrapped"
        print(json.dumps({"protocol_check": status, **result}))
    else:
        msg = f"[PROTOCOL] ⚠️ '{project_name}' 缺少: {result['missing']} (自举失败: {result.get('error', 'unknown')})"
        sys.stderr.write(msg + "\n")
        print(json.dumps({"protocol_check": "failed", **result}))


if __name__ == "__main__":
    main()
