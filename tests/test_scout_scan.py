"""test_scout_scan.py — 锁定 scout-scan 健康度排序行为。

回归守护：确保
  1. 缺 PROGRESS+GATES 的项目排在高分（引擎被导向真正缺照顾的项目）；
  2. health_priority 不依赖 last_commit 新旧（打破 worktree 流程下的自反馈）；
  3. autonomous-studio 不被特殊排除——按健康度公平排名（引擎真有 bug 仍可被选中）；
  4. 文本输出含「推荐工作单位」段；
  5. scan_project → health_priority 集成路径（非 _rep 合成旁路）对真实文件系统行为正确。
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "scout-scan.py")
WORKSPACE = os.path.abspath(os.path.join(HERE, "..", ".."))  # /home/admin/workspace


def _load():
    spec = importlib.util.spec_from_file_location("scout_scan", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rep(name, progress_stale_days, gates, planning, todo, fixme, hack, nfiles=100):
    """合成一个 scan_project 返回结构的最小 rep。"""
    return {
        "name": name,
        "progress_stale_days": progress_stale_days,  # None = 缺 PROGRESS
        "gates_exists": gates,
        "has_planning": planning,
        "markers": {"TODO": todo, "FIXME": fixme, "HACK": hack},
        "file_count_indexed": nfiles,
    }


def test_missing_docs_ranks_highest():
    """缺 PROGRESS+GATES 的项目应高于文档齐全的项目。"""
    mod = _load()
    broken = _rep("broken", progress_stale_days=None, gates=False, planning=False,
                  todo=10, fixme=5, hack=2)
    healthy = _rep("healthy", progress_stale_days=0.1, gates=True, planning=True,
                   todo=0, fixme=0, hack=0)
    assert mod.health_priority(broken)["score"] > mod.health_priority(healthy)["score"]


def test_score_independent_of_commit_recency():
    """health_priority 不读 last_commit——rep 里根本没有该字段也能算分。"""
    mod = _load()
    rep = _rep("x", progress_stale_days=0.2, gates=True, planning=True,
               todo=3, fixme=0, hack=0)
    hp = mod.health_priority(rep)
    # 不应抛 KeyError；且 rep 无 git/last_commit 字段
    assert "last_commit" not in rep
    assert isinstance(hp["score"], float)
    assert hp["work_unit"]


def test_autonomous_studio_not_excluded_from_ranking():
    """跑真实 workspace，autonomous-studio 必须出现在 recommendations 里（不被排除）。"""
    ws = WORKSPACE
    r = subprocess.run(
        [sys.executable, SCRIPT, "--workspace", ws, "--json"],
        capture_output=True, text=True, timeout=180,
    )
    assert r.returncode == 0, r.stderr
    import json
    recs = json.loads(r.stdout).get("recommendations", [])
    names = [rc["name"] for rc in recs]
    assert "autonomous-studio" in names, "autonomous-studio 被错误排除出排名"


def test_text_output_has_recommendation_section():
    """文本模式必须打印「推荐工作单位」段。"""
    ws = WORKSPACE
    r = subprocess.run(
        [sys.executable, SCRIPT, "--workspace", ws],
        capture_output=True, text=True, timeout=180,
    )
    assert r.returncode == 0, r.stderr
    assert "推荐工作单位" in r.stdout
    assert "#1" in r.stdout


def test_scan_project_to_health_priority_integration(tmp_path):
    """集成测试：scan_project → health_priority 全链路（非 _rep 合成旁路）。

    H-001 (audit-2026-07-01-004): 此前所有健康度单测用 _rep() 构造字典直调
    health_priority，绕过了 scan_project 对真实文件系统的探测路径
    （staleness/count_markers/git_info/pending_*_in_worktrees）。若 scan_project
    返回结构字段名/类型漂移、或缺省值变化，_rep 测试不会捕获。

    本测试在 tmpdir 里搭两个最小项目仓（broken/healthy），真调 scan_project
    产出 rep，再喂给 health_priority，验证：
      * broken（缺 PROGRESS+GATES+planning）得分严格高于 healthy（三件齐全）；
      * rep 含 scan_project 特有字段（git/markers_deferred/pending_worktrees），
        确认走的是真实集成路径而非 _rep 旁路。

    tmp_path 隔离 .codebase-index 写入副作用，不污染宿主 workspace。
    """
    mod = _load()

    # --- broken: 仅 .git 目录使其被 discover_projects 识别，无任何文档 ---
    broken_dir = tmp_path / "broken-proj"
    broken_dir.mkdir()
    (broken_dir / ".git").mkdir()  # 触发 has_git=True
    # 放一个带 TODO 注释的源文件，让 count_markers 有活干
    (broken_dir / "foo.py").write_text("# TODO: fix this\nprint('hi')\n", encoding="utf-8")

    # --- healthy: PROGRESS.md + GATES.md + planning/ 齐全 ---
    healthy_dir = tmp_path / "healthy-proj"
    healthy_dir.mkdir()
    (healthy_dir / ".git").mkdir()
    (healthy_dir / "PROGRESS.md").write_text("# Progress\nfresh\n", encoding="utf-8")
    (healthy_dir / "GATES.md").write_text("# Gates\nok\n", encoding="utf-8")
    (healthy_dir / "planning").mkdir()
    (healthy_dir / "planning" / "status.json").write_text("{}", encoding="utf-8")
    (healthy_dir / "bar.py").write_text("print('clean')\n", encoding="utf-8")

    # 把 .codebase-index 重定向到 tmp_path 下，避免写宿主 workspace
    # （scan_project 硬编码 idx_dir = os.path.join(os.path.dirname(path), ".codebase-index")，
    #  因 broken/healthy 都在 tmp_path 下，idx_dir 自动落在 tmp_path/.codebase-index）

    broken_rep = mod.scan_project({"name": "broken-proj", "path": str(broken_dir)})
    healthy_rep = mod.scan_project({"name": "healthy-proj", "path": str(healthy_dir)})

    # 集成路径专属字段断言——_rep 合成路径不会有这些键
    for key in ("git", "markers_deferred", "pending_worktrees", "marker_files", "symbols"):
        assert key in broken_rep, f"scan_project 返回缺少集成路径字段 {key}"
        assert key in healthy_rep, f"scan_project 返回缺少集成路径字段 {key}"

    broken_hp = mod.health_priority(broken_rep)
    healthy_hp = mod.health_priority(healthy_rep)

    # 核心契约：缺文档的项目健康度分数严格高于文档齐全的项目
    assert broken_hp["score"] > healthy_hp["score"], (
        f"集成路径下 broken({broken_hp['score']}) 应 > healthy({healthy_hp['score']})；"
        f"broken reasons={broken_hp['reasons']}, healthy reasons={healthy_hp['reasons']}"
    )
    # broken 必须命中"缺 PROGRESS.md"+"缺 GATES.md"两条原因（来自真实 staleness/os.path.isfile）
    assert any("缺 PROGRESS.md" in r for r in broken_hp["reasons"]), \
        f"broken 未检出缺 PROGRESS.md: {broken_hp['reasons']}"
    assert any("缺 GATES.md" in r for r in broken_hp["reasons"]), \
        f"broken 未检出缺 GATES.md: {broken_hp['reasons']}"
