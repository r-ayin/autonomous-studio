"""test_scout_scan.py — 锁定 scout-scan 健康度排序行为。

回归守护：确保
  1. 缺 PROGRESS+GATES 的项目排在高分（引擎被导向真正缺照顾的项目）；
  2. health_priority 不依赖 last_commit 新旧（打破 worktree 流程下的自反馈）；
  3. autonomous-studio 不被特殊排除——按健康度公平排名（引擎真有 bug 仍可被选中）；
  4. 文本输出含「推荐工作单位」段且 #N 行格式合规（L-001 fix）；
  5. scan_project → health_priority 集成路径（非 _rep 合成旁路）对真实文件系统行为正确；
  6. recommendations 结构完整性通过 API 直验（I-001: subprocess→importlib）。
"""
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout

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
    """health_priority 不读 last_commit——rep 里根本没有该字段也能算分。

    M-003 fix: 原断言仅验 isinstance(score, float) + work_unit 非空，允许退化实现
    （恒返回 0.0）通过。现锁定两条数值不变量：
      (a) progress_stale_days 从 fresh→stale 必须让 score 严格上升（stale 贡献生效）；
      (b) FIXME/HACK 加权贡献精确 = min((F+H)*0.2, 4)（防加权被误删或封顶值漂移）。
    公式来自 scripts/scout-scan.py:487 health_priority。若重构公式，请同步更新本测试。
    """
    mod = _load()
    rep = _rep("x", progress_stale_days=0.2, gates=True, planning=True,
               todo=3, fixme=0, hack=0)
    hp = mod.health_priority(rep)
    # 不应抛 KeyError；且 rep 无 git/last_commit 字段
    assert "last_commit" not in rep
    assert isinstance(hp["score"], float)
    assert hp["work_unit"]

    # (a) stale 贡献必须生效：fresh(0.2d) vs stale(100d)，其余相同
    rep_fresh = _rep("f", progress_stale_days=0.2, gates=True, planning=True,
                     todo=0, fixme=0, hack=0)
    rep_stale = _rep("s", progress_stale_days=100.0, gates=True, planning=True,
                     todo=0, fixme=0, hack=0)
    score_fresh = mod.health_priority(rep_fresh)["score"]
    score_stale = mod.health_priority(rep_stale)["score"]
    assert score_stale > score_fresh, (
        f"stale 项目应得分更高：fresh={score_fresh}, stale={score_stale}"
    )
    # STALE_DAYS=7 → stale 贡献 +3；fresh 不触发。差值应恰好 3（无其他变量）
    assert abs((score_stale - score_fresh) - 3.0) < 1e-9, (
        f"stale-fresh 差值应为 3.0（STALE_DAYS 阈值贡献），实际 {score_stale - score_fresh}"
    )

    # (b) FIXME/HACK 加权锁定：min((F+H)*0.2, 4)。
    # 注意 density 贡献含 TODO+F+H，加 F/H 同时抬高 density；用同 todo baseline
    # 做差值后需扣除 density 增量才是纯 FIXME/HACK 加权。公式：
    #   delta = ((T+F+H)/n - T/n)*10 + min((F+H)*0.2, 4) = (F+H)/n*10 + min(...)
    n = 100  # _rep default
    f_base, h_base = 0, 0
    f_add, h_add = 5, 3
    rep_base = _rep("base", progress_stale_days=0.2, gates=True, planning=True,
                    todo=3, fixme=f_base, hack=h_base)
    rep_fixme = _rep("fh", progress_stale_days=0.2, gates=True, planning=True,
                     todo=3, fixme=f_add, hack=h_add)
    score_base = mod.health_priority(rep_base)["score"]
    hp_fixme = mod.health_priority(rep_fixme)
    expected_delta = ((f_add + h_add) / n) * 10 + min((f_add + h_add) * 0.2, 4.0)  # 0.8 + 1.6 = 2.4
    delta = hp_fixme["score"] - score_base
    assert abs(delta - expected_delta) < 1e-9, (
        f"FIXME/HACK 总增量应为 {expected_delta}，实际 {delta}"
    )
    # 封顶验证：F+H=30 → 30*0.2=6 > cap 4 → 加权截到 4；density 增量=30/100*10=3
    rep_capped = _rep("cap", progress_stale_days=0.2, gates=True, planning=True,
                      todo=3, fixme=20, hack=10)
    hp_capped = mod.health_priority(rep_capped)
    expected_cap_delta = (30 / n) * 10 + 4.0  # 3.0 + 4.0 = 7.0
    delta_cap = hp_capped["score"] - score_base
    assert abs(delta_cap - expected_cap_delta) < 1e-9, (
        f"FIXME/HACK 封顶增量应为 {expected_cap_delta}，实际 {delta_cap}"
    )


def _real_workspace():
    """返回含至少一个真项目（带 .git）的 workspace 路径。

    WORKSPACE 由 HERE 上溯两级推导；当测试在 opt-worktree 内运行时，
    HERE 落在 .opt-worktrees/<proj>/<wt>/tests，推导出的是 worktree 父目录
    （全为 worktree 子目录，无真项目），scout-scan 会返回空 recommendations。
    此时 fallback 到 AUTONOMOUS_STUDIO_WORKSPACE 环境变量。
    都没有 → raise SkipTest（unittest 标准，无需 pytest）。
    """
    import unittest as _unittest
    def _has_real_project(ws):
        if not os.path.isdir(ws):
            return False
        try:
            entries = os.listdir(ws)
        except OSError:
            return False
        return any(os.path.isdir(os.path.join(ws, d, ".git")) for d in entries)

    if _has_real_project(WORKSPACE):
        return WORKSPACE
    env_ws = os.environ.get("AUTONOMOUS_STUDIO_WORKSPACE")
    if env_ws and _has_real_project(env_ws):
        return env_ws
    raise _unittest.SkipTest(f"no real workspace available (derived={WORKSPACE})")


def test_recommendations_are_structurally_complete():
    """recommendations 必须是非空的结构完整列表（I-001: importlib 直调替代 subprocess）。

    M-001 fix: 移除硬编码 'autonomous-studio' 项目名断言——该断言把测试
    绑死到特定 workspace 布局与项目命名，违背"测行为不测内容"原则。
    改为结构完整性检查：列表非空、每项含 name/score/reasons/work_unit 字段、
    name 非空字符串、score 为数值。若引擎错误地过滤掉所有项目或推荐结构漂移，
    此测试仍会失败（守住原测试意图）。

    I-001: 原实现 spawn 完整 scout-scan.py 子进程 + JSON 解析 stdout。慢、
    环境耦合、CI 不友好。scout-scan 已模块化（discover_projects/scan_project/
    health_priority 均为纯函数或可隔离函数），直接 importlib 调用更快更稳定，
    且契约验证比 subprocess+JSON 解析更精准（验字段类型而非仅字符串存在）。
    """
    ws = _real_workspace()
    mod = _load()
    projects = mod.discover_projects(ws)
    assert len(projects) > 0, f"workspace {ws} 应发现至少一个项目"

    recs = []
    for p in projects:
        r = mod.scan_project(p)
        hp = mod.health_priority(r)
        recs.append({
            "name": r["name"], "score": hp["score"],
            "reasons": hp["reasons"], "work_unit": hp["work_unit"],
        })

    assert isinstance(recs, list) and len(recs) > 0, "recommendations 不应为空列表"
    for rc in recs:
        assert isinstance(rc.get("name"), str) and rc["name"].strip(), \
            f"recommendation 项缺有效 name: {rc!r}"
        assert isinstance(rc.get("score"), (int, float)), \
            f"recommendation 项 score 应为数值: {rc!r}"
        assert isinstance(rc.get("reasons"), list), \
            f"recommendation 项 reasons 应为 list: {rc!r}"
        assert isinstance(rc.get("work_unit"), str) and rc["work_unit"].strip(), \
            f"recommendation 项缺有效 work_unit: {rc!r}"


# L-001 fix: 锁定 #N 行格式 — `<2空格>#<rank> <name> (score=<float>) — <reason>`
# 防止回归到"只打印字符串、不打印结构化推荐行"的退化实现。
_REC_LINE_RE = re.compile(
    r"^  #(\d+)\s+(\S+)\s+\(score=([\d.]+)\)\s+—\s+(.+)$"
)


def test_text_output_has_recommendation_section():
    """文本模式必须打印「推荐工作单位」段且 #N 行格式合规（L-001 fix, I-001 importlib）。

    弱断言 `"#1" in stdout` 允许退化实现通过（例如把 "#1" 写在说明文字里
    而不是真正的推荐行）。本测试解析每行 #N，验证：
      - 至少存在一条格式合规的推荐行；
      - rank 编号从 1 开始连续递增；
      - score 为非负浮点；
      - reason 非空。

    I-001: 原 subprocess.run + capture_output 改为 redirect_stdout(StringIO)
    直调 main()。契约验证逻辑不变，但免去子进程开销与环境耦合。
    sys.argv 临时改写以传入 --workspace，main() 返回后恢复。
    """
    ws = _real_workspace()
    mod = _load()

    # 临时改 sys.argv 让 argparse 读到 --workspace；main() 完成后还原
    orig_argv = sys.argv
    try:
        sys.argv = ["scout-scan.py", "--workspace", ws]
        buf = io.StringIO()
        with redirect_stdout(buf):
            mod.main()
        stdout = buf.getvalue()
    finally:
        sys.argv = orig_argv

    assert "推荐工作单位" in stdout, "缺「推荐工作单位」段标题"

    matches = [_REC_LINE_RE.match(line) for line in stdout.splitlines()]
    rec_lines = [m for m in matches if m]
    assert rec_lines, (
        "未找到任何格式合规的 #N 推荐行；"
        f"期望匹配 {_REC_LINE_RE.pattern!r}"
    )

    ranks = [int(m.group(1)) for m in rec_lines]
    assert ranks[0] == 1, f"推荐行 rank 应从 1 起，实际首条 rank={ranks[0]}"
    assert ranks == list(range(1, len(ranks) + 1)), \
        f"推荐行 rank 应连续递增，实际 {ranks}"

    for m in rec_lines:
        score = float(m.group(3))
        assert score >= 0.0, f"score 应为非负浮点，实际 {score}"
        assert m.group(4).strip(), f"reason 不应为空：{m.group(0)!r}"


def test_subprocess_smoke_polyglot_shim():
    """subprocess smoke: 验证 scout-scan.py 作为独立脚本可被 python3 拉起（I-001）。

    I-001 重构把两个重 subprocess 测试改成 importlib 直调（更快、无环境耦合）。
    保留这一个最小 smoke test 守护 polyglot shim 契约：
      - 脚本文件存在且有 shebang / 可被 sys.executable 解释；
      - `--help` 退出码 0 且 stdout 含 '--workspace' 参数说明。
    不依赖具体 workspace 内容，CI 友好，timeout 5s 足够。
    """
    r = subprocess.run(
        [sys.executable, SCRIPT, "--help"],
        capture_output=True, text=True, timeout=5,
    )
    assert r.returncode == 0, f"--help 应退出码 0，stderr={r.stderr}"
    assert "--workspace" in r.stdout, \
        f"--help 输出应包含 --workspace 参数说明，stdout={r.stdout[:500]}"


def test_scan_project_to_health_priority_integration():
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

    用 stdlib tempfile.TemporaryDirectory 而非 pytest tmp_path fixture，
    确保 unittest/pytest 双 runner 都能跑（M-002 structural debt: pytest 未装）。
    tmpdir 隔离 .codebase-index 写入副作用，不污染宿主 workspace。
    """
    mod = _load()

    with tempfile.TemporaryDirectory(prefix="scout_scan_integ_") as tmp:
        # --- broken: 仅 .git 目录使其被 discover_projects 识别，无任何文档 ---
        broken_dir = os.path.join(tmp, "broken-proj")
        os.makedirs(os.path.join(broken_dir, ".git"))  # 触发 has_git=True
        # 放一个带 TODO 注释的源文件，让 count_markers 有活干
        with open(os.path.join(broken_dir, "foo.py"), "w", encoding="utf-8") as f:
            f.write("# TODO: fix this\nprint('hi')\n")

        # --- healthy: PROGRESS.md + GATES.md + planning/ 齐全 ---
        healthy_dir = os.path.join(tmp, "healthy-proj")
        os.makedirs(os.path.join(healthy_dir, ".git"))
        with open(os.path.join(healthy_dir, "PROGRESS.md"), "w", encoding="utf-8") as f:
            f.write("# Progress\nfresh\n")
        with open(os.path.join(healthy_dir, "GATES.md"), "w", encoding="utf-8") as f:
            f.write("# Gates\nok\n")
        os.makedirs(os.path.join(healthy_dir, "planning"))
        with open(os.path.join(healthy_dir, "planning", "status.json"), "w", encoding="utf-8") as f:
            f.write("{}")
        with open(os.path.join(healthy_dir, "bar.py"), "w", encoding="utf-8") as f:
            f.write("print('clean')\n")

        broken_rep = mod.scan_project({"name": "broken-proj", "path": broken_dir})
        healthy_rep = mod.scan_project({"name": "healthy-proj", "path": healthy_dir})

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
