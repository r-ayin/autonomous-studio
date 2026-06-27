"""test_scout_scan.py — 锁定 scout-scan 健康度排序行为。

回归守护：确保
  1. 缺 PROGRESS+GATES 的项目排在高分（引擎被导向真正缺照顾的项目）；
  2. health_priority 不依赖 last_commit 新旧（打破 worktree 流程下的自反馈）；
  3. autonomous-studio 不被特殊排除——按健康度公平排名（引擎真有 bug 仍可被选中）；
  4. 文本输出含「推荐工作单位」段。
"""
import importlib.util
import os
import subprocess
import sys

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
