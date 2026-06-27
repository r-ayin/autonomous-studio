# autonomous-studio — 自主开发引擎 v6.0

> **持续自治管线**：空闲即触发，一直跑到人说停（不再 cron 定时）
> **确定性 > LLM 自评**：hook 强制 + 确定性脚本兜底，提示词不是护栏
> **worktree 隔离**：自动优化进其他分支，main 永远安全，人审 diff 才合并

## 概述

autonomous-studio 是运行在 Claude Code 之上的自主开发引擎。引擎让 AI 在你不在时持续做：探究项目、开发、修复、优化、补缺文件、建索引——所有产出进 opt-worktree（不碰 main），等你审 diff 后合并。

- **版本**：v6.0（持续自治 + 蒸馏闭环 + opt-worktree + 确定性扫描索引 + hook 强制）
- **模型**：GLM-5.2（智谱，通过 Anthropic 兼容端点）；预算制，确定性优先
- **语言**：Markdown（Skill/Prompt）+ Python（Hooks/脚本）+ Bash + JS + JSON

## 核心机制（v6.0 四大支柱）

### 1. 持续自治管线（替代 cron）
不再 2h/4h 定时心跳。`scripts/autonomous-loop.sh` 是 Ralph Wiggum 死循环：每轮 `claude -p` 新 context 做一个工作单位→提交 opt-worktree→退出→重开。**察觉空闲就持续触发，直到人说停**（`touch .claude/.stop_autonomous` 或 kill）。

```
autonomous-loop.sh <workspace> [--bg]    # 启动（前台/后台）
touch <workspace>/.claude/.stop_autonomous   # 停
```

每轮纪律：跑 `scout-scan`（末尾出「推荐工作单位」按健康度排序）→ 取 #1 项目的工作单位 → 探究/开发/修复/优化/缺文件就补 → `opt-worktree.sh commit` → 一行汇报 + 写 case JSON 喂蒸馏闭环（预算已解禁，2026-06-27）。**无限制**（无冷却/连续次数/降频/预算上限），worktree 隔离使 main 安全。仅卡死保护（同错误 3 次无进展→blocked 跳走）。

### 2. opt-worktree 隔离（main 永远安全）
自动优化**从不直接提交 main**。`scripts/opt-worktree.sh` 把改动提交到 `auto/optimization`（或 `auto/opt-<area>-<ts>`）worktree，人审 diff 后 `merge`/`reject`。

```bash
opt-worktree.sh <project> init                       # 建主 worktree
opt-worktree.sh <project> commit <area:sub> "<msg>" [files...]  # 提交（文件级 stash，不扫用户 WIP）
opt-worktree.sh <project> list                       # 列待审 worktree
opt-worktree.sh <project> show <wt>                  # 看 diff
opt-worktree.sh <project> merge <wt>                 # 人审后 squash 合并→main
opt-worktree.sh <project> reject <wt>                # 拒绝
```

方向分歧判定：`direction = area:subdirection`。同 area 累积同 worktree，不同 area 开新 worktree（隔离）。

### 3. 蒸馏闭环（决策习惯积累）
> 现状（2026-06-27）：预算解禁后，引擎每轮重新写 case JSON 喂闭环。基础设施齐备：`distill-patterns.py` / `index-cases.py` / `verify-pattern.sh` / `decision-observer.py` hook 均在；`scheduled_tasks.json` 定义了 L3 每 4h + distill 定时任务（依赖 REPL 空闲触发）。calibration.json `last_decision` 此前停在 06-17（预算暂停期），待引擎续写 case 后由 distill 重算刷新。

修复了"提示词描述闭环、代码实现开环"的 7 个断裂。`scripts/distill-patterns.py` 从 case outcome 确定性重算 pattern accuracy（不再 LLM 自评 82% 虚高），`scripts/verify-pattern.sh` 4 门禁（最小样本/accuracy 底线/容量帽/同步检查）防退化。

- **数据管道闭合**：`decision-observer.py` 从最新 case 回读 stage/result/confidence_score 写入 decision-log
- **case schema**：加 `outcome` 枚举 + `outcome_evidence`（引用可观察事实，不接受 LLM 散文）
- **检索**：`scripts/index-cases.py` TF-IDF + 中文双字组，零依赖零 token，相似案例 top-k
- **门禁**：`patterns-write-gate.py` 阻断 agent 直接改 patterns.md（强制走 distill+verify）
- **定时蒸馏**：每 6h 跑 `distill-patterns.py --apply`（确定性，零推理）

### 4. 确定性扫描索引（替代 LLM 自觉扫描）
`scripts/scout-scan.py` 自动发现 workspace 项目、生成 `PROJECTS.md` 单一源、每项目健康扫描（git/PROGRESS/GATES/TODO 标记）+ 文件树+符号索引（fn/class/headings），存 `.codebase-index/`。零 LLM token。子 agent 只读结构化报告，不再自觉跑 Bash。

```bash
scout-scan.py --workspace .           # 扫描+索引+写 PROJECTS.md
scout-scan.py --workspace . --json    # JSON 供 agent 解析
```

## Hook 栈（确定性 backstop）

| Hook | 触发 | 作用 |
|---|---|---|
| `autonomous-commit-gate.py` | PreToolUse/Bash | 自治标记在时拦死 `git commit/push/merge main`，强制走 opt-worktree |
| `stop-completion-gate.py` | Stop | 测试/任务/语法二元门控，未完成 exit 2 强制继续（3 连击防死循环） |
| `post-edit-lint.py` | PostToolUse/Edit\|Write | 编辑后自动 py_compile/tsc/关联测试 |
| `patterns-write-gate.py` | PreToolUse/Edit\|Write | 阻断直接改 patterns.md（强制走 distill） |
| `discovery-gate.py` | PreToolUse+UserPromptSubmit | 项目初始化门禁，强制苏格拉底发现协议 |
| `decision-observer.py` | Stop+UserPromptSubmit | 决策日志 + 从 case 回读 outcome + 每 10 轮 token 泄漏提醒 |
| `auto-commit.py` | Stop+SessionEnd | 项目变更自动 commit（自治标记在时跳过，不绕过 gate） |
| `resume-checkpoint.py` | SessionStart | 检查点恢复 + 引擎固件注入 |
| `protocol-check.py` | Pre+PostToolUse/Edit | 三件套自举 |

**原则**：提示词不是护栏——LLM 可能绕过文本指令，bash exit 2 不可协商。

## 六阶段 Studio 流水线（按需加载）

需求 → PRD → 技术方案 → 开发 → 验证 → 评审 → 部署。`phases/phase-{build,dev,ship}.md` 按需 Read，不全加载。

**phase-dev ④ 并发构建**：PRD 产出依赖 DAG（`blockedBy`）+ 文件所有权（`files`）→ `parallel-dispatch.sh` 每 task 一个 worktree（并发上限 4）→ `parallel-merge.sh` 按依赖序增量合并 + 集成测试 + blocked 隔离。修正了"分支→worktree、全末尾合并→增量、全开→限流、主 agent 产契约非完整架构"四个字面方案硬伤。

## 快速开始

```bash
git clone https://code.alibaba-inc.com/qunbu/autonomous-studio.git
cd autonomous-studio
# 按 SETUP.md 安装到目标项目（cp 技能+hooks+种子数据，配 settings.json）
# 启动持续自治：
touch <target>/.claude/.autonomous_active        # 激活 gate
bash scripts/autonomous-loop.sh <workspace> --bg # 后台持续跑
# 停：
touch <workspace>/.claude/.stop_autonomous
```

GLM-5.2 配置（`~/.claude/settings.json`）：
```json
{ "env": {
  "ANTHROPIC_BASE_URL": "https://open.bigmodel.cn/api/anthropic",
  "ANTHROPIC_AUTH_TOKEN": "<智谱Key>",
  "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.2[1m]",
  "ANTHROPIC_DEFAULT_HAIKU_MODEL": "GLM-4.7-air"
}}
```

## 设计原则（从研究+实测提炼）

1. **确定性 > LLM 自评**——accuracy/完成/可逆性由脚本判定，不靠模型自觉（同模型评估 82% 虚高）
2. **提示词不是护栏**——hook exit 2 不可协商，LLM 绕不过
3. **worktree 隔离**——自动优化不碰 main，大胆跑，人审才合并
4. **执行者不评判自己**——distill 用独立 agent + 确定性 outcome，不做自我反思
5. **最小样本底线**——<2 个有 outcome 的 case 不算 accuracy，标待验证
6. **预算感知**——蒸馏/扫描/检索用确定性（零 token），LLM 仅用于真正需要推理处

## 文档

- `SETUP.md` — 安装指南（从根目录技能文件装到目标项目）
- `OPTIMIZATION-WORKFLOW.md` — opt-worktree 优化工作流（自动优化→worktree→人审合并）
- `ARCHITECTURE.md` — 完整架构
- `AGENTS.md` / `ALIASES.md` — agent 导航/别名
- `GATES.md` — 质量门禁清单
- `phases/` — 六阶段流水线定义
- `decision-agent-prompt.md` — 决策 agent 七阶段框架

## 不可用（GLM-5.2 + 非 Anthropic 原生）

`/effort ultracode` 原生 thinking、Agent Teams、`/schedule` Cloud Routines、`/goal`、Anthropic Batch API、显式 `cache_control`——均 Anthropic 专属。本项目用智谱隐式缓存（前缀匹配 >512 tokens）+ CronCreate + autonomous-loop.sh 替代。

## 许可

MIT
