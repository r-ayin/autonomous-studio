# autonomous-studio 安装指南

> 本仓库 `qunbu/autonomous-studio` 是唯一源。根目录即技能内容（v5.4）。安装 = 把根目录技能文件复制到目标项目的 `.claude/skills/autonomous-studio/`。
> 旧名 `autonomous-engine` 已废弃——若目标项目里有 `.claude/skills/autonomous-engine/`，删掉它再用本指南重装。

预计时间：15-30 分钟

## 前置条件

- Python 3.10+
- Claude Code 最新版
- Git 2.40+

可选: Android + Termux + ntfy.sh app

## 步骤 1：取得本仓库

```bash
git clone https://code.alibaba-inc.com/qunbu/autonomous-studio.git
cd autonomous-studio
```

`$SRC` = 本仓库根目录。`$TARGET` = 你要安装到的目标项目根目录。

## 步骤 2：部署技能包（autonomous-studio）

把根目录的技能内容装到目标项目的 `.claude/skills/autonomous-studio/`：

```bash
mkdir -p "$TARGET/.claude/skills/autonomous-studio"
# 核心引擎文件（根目录即源）
cp -r phases scripts hooks config "$TARGET/.claude/skills/autonomous-studio/"
cp decision-agent-prompt.md studio-inject.md studio-pipeline.md \
   SKILL.md README.md ARCHITECTURE.md AGENTS.md ALIASES.md GATES.md \
   watchdog.sh watchdog-boot.ps1 termux-listener.py \
   "$TARGET/.claude/skills/autonomous-studio/"
```

## 步骤 3：部署 Hooks（Python）

根目录的 `.claude/hooks/` 是确定性 hook 实现，装到目标项目的 `.claude/hooks/`：

```bash
mkdir -p "$TARGET/.claude/hooks"
cp .claude/hooks/*.py "$TARGET/.claude/hooks/"
cp .claude/hooks/*.sh "$TARGET/.claude/hooks/" 2>/dev/null || true
chmod +x "$TARGET/.claude/hooks/"*.sh "$TARGET/.claude/hooks/"*.py
```

关键 hook：`decision-observer.py`、`resume-checkpoint.py`、`save-checkpoint.py`、`incremental-save.py`、`discovery-gate.py`、`protocol-check.py`、`stop-completion-gate.py`（Stop 完成门控）、`post-edit-lint.py`（编辑后自动 lint/测试）、`auto-commit.py`、`notify-phone.py`、`codegraph-sync.py`、`pipeline-gate.py`（管线强制，见下）。

> **管线强制（pipeline-gate）**：studio 项目（含 `planning/status.json`）改动前必须先 `python3 scripts/triage.py --kind small|complex --desc '...'`（写 `<project>/.pipeline/current.json`）。complex 任务走 `requirement→prd→development→verify→done`（`triage.py --stage ...`），commit 前 `--verify-passed`；小修直放但 diff 超规模(files>3 或 +行>50)自动升级 complex。非 studio 项目不受约束。详见 `PIPELINE-GATE.md`。`scripts/triage.py` 随技能包一起 `cp -r scripts` 安装。

## 步骤 4：部署引擎种子数据

```bash
mkdir -p "$TARGET/.claude/decisions" "$TARGET/.claude/memory"
cp .claude/decisions/calibration.json    "$TARGET/.claude/decisions/"
cp .claude/decisions/model-profiles.json "$TARGET/.claude/decisions/"
cp .claude/decisions/notification-policy.json "$TARGET/.claude/decisions/"
cp .claude/decisions/role-permissions.json   "$TARGET/.claude/decisions/"
cp .claude/memory/autonomous-state.md "$TARGET/.claude/memory/"        # 富状态（手维护，勿 hook 覆写）
```

> 运行时文件（`autonomous-state-runtime.md`、`session-progress.md`、`autonomous-suggestions.md`、`decision-log.jsonl`、`scheduled_tasks.json`、`checkpoints/`、`sessions/`）由 hook 自动生成，**不要手动装**，且已在 `.gitignore` 里不纳入版本控制。

## 步骤 5：配置 Hook 绑定

把 `config/settings.json.example` 的 `hooks` 段落合并到 `$TARGET/.claude/settings.json`（用 python 安全合并，勿直接覆盖）：

```bash
python3 - <<'PY'
import json, pathlib
target = pathlib.Path("$TARGET/.claude/settings.json")
example = json.load(open("config/settings.json.example"))
cfg = json.load(open(target)) if target.exists() else {}
cfg.setdefault("hooks", {}).update(example.get("hooks", {}))
cfg.setdefault("env", {}).update(example.get("env", {}))
target.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
PY
```

## 步骤 6：(可选) 定时心跳

把 `config/scheduled_tasks.json.example` 复制为 `$TARGET/.claude/scheduled_tasks.json`（运行时副本，CronCreate 会维护）：

```bash
cp config/scheduled_tasks.json.example "$TARGET/.claude/scheduled_tasks.json"
```

L2 心跳每 2 小时、L3 深检每 4 小时（GLM 预算制频率；无活跃 Studio 项目时不 spawn）。

## 步骤 7：(可选) 手机通知

```json
// $TARGET/.claude/phone-notify.json
{ "enabled": true, "ntfy": { "server": "https://ntfy.sh", "topic": "your-topic-name" } }
```

## 步骤 8：(可选) L6 看门狗

```bash
chmod +x "$TARGET/.claude/skills/autonomous-studio/watchdog.sh"
# 编辑 watchdog.sh 设 PROJECT_DIR；crontab: */5 * * * * /path/watchdog.sh
```

## 步骤 9：(可选) CodeGraph 融合层

```bash
cp -r .claude/codegraph "$TARGET/.claude/"
cp scripts/route-health-scorer.py "$TARGET/scripts/"
```

## 步骤 10：(可选) 扩展技能

按需从根 `skills/` 复制扩展技能到 `$TARGET/.claude/skills/`：

```bash
for skill in memory prod-deploy serial-agent-handoff agents-map zujianfuyon demand-discovery idea-exploration pm-spec; do
  cp -r "skills/$skill" "$TARGET/.claude/skills/" 2>/dev/null || true
done
```

## 步骤 11：验证

```bash
ls "$TARGET/.claude/skills/autonomous-studio/phases/phase-dev.md"
ls "$TARGET/.claude/hooks/decision-observer.py"
ls "$TARGET/.claude/decisions/calibration.json"
python "$TARGET/.claude/hooks/decision-observer.py" < /dev/null   # 应输出 additionalContext 且 exit 0
```

启动 Claude Code → 观察 SessionStart 输出 → 说"初始化项目"验证 discovery-gate。

## 升级（从旧 autonomous-engine 迁移）

1. 删旧安装：`rm -rf "$TARGET/.claude/skills/autonomous-engine"`、`rm -rf "$TARGET/autonomous-engine"`（若有）。
2. 按上面步骤 2-5 重装为 `autonomous-studio`。
3. 保留 `$TARGET/.claude/memory/autonomous-state.md`（富状态迁移），其余运行时文件让 hook 重建。

## 常见问题

| 问题 | 解决 |
|------|------|
| 引擎未自动激活 | 说"检查心跳"确认 CronCreate；看 `.claude/scheduled_tasks.json` 是否存在 |
| `autonomous-state.md` 被清空 | 确认 `decision-observer.py` 是新版（写 `autonomous-state-runtime.md`，不碰 `autonomous-state.md`） |
| Stop hook 不阻断 | 确认 `stop-completion-gate.py` 已装且 settings.json Stop 段含它 |
| 通知发送失败 | 检查 ntfy topic / SSH tunnel |
