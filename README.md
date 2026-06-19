# autonomous-studio — 自主开发引擎 v5.1

> **三层心跳架构**：Tier 0 Hook（零成本）→ Tier 1 扫描 sonnet（低成本）→ Tier 2 行动 opus（按需）
> **六阶段 Studio 流水线**：需求探索 → PRD → 开发 → 验证 → 评审 → 部署
> **30 个可复用 Skill**：研发流程、平台工具、钉钉集成、内容写作、组件复用等

## 概述

autonomous-studio 是运行在 Claude Code 之上的自主开发引擎。它通过三层心跳架构实现"人不在时 AI 继续干活"——Hook 零成本守护、sonnet 低成本扫描、opus 按需执行。激活后将行为规则注入项目 CLAUDE.md，后续每条消息自动遵循研发流程。

- **版本**：v5.1（三层心跳 + 调度保障 + Hook 双轨改造 + 30 Skill 整合）
- **架构**：调度器模式 — 主会话 spawn 独立子 Agent，零上下文污染
- **语言**：Markdown（Skill/Prompt）+ Python（Hooks）+ Shell + JavaScript + JSON

## 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                    三层心跳架构                                │
├──────┬───────┬───────────────────────────────────────────────┤
│ 层级 │ 模型  │ 职责                                          │
├──────┼───────┼───────────────────────────────────────────────┤
│ T0   │ 无    │ Hook — 格式验证、进度统计、提交提醒（每次写入） │
│ T1   │ sonnet│ 扫描 — 快速诊断：要不要行动？（每 7/60 分钟）  │
│ T2   │ opus  │ 行动 — 写代码/跑验证/出建议（按需）            │
├──────┴───────┴───────────────────────────────────────────────┤
│  六阶段流水线：需求 → PRD → 开发 → 验证 → 评审 → 部署          │
│  原则：不需要 AI → Hook。需要判断 → sonnet。需要行动 → opus    │
└──────────────────────────────────────────────────────────────┘
```

### 心跳流程

```
1. 预检: bash scripts/studio-precheck.sh {项目目录}
   → skip → 静默退出

2. Tier 1 扫描: spawn Agent (model: sonnet)
   → Read scripts/scanner-prompt.md
   → 返回 {needsAction, actionType, reason}
   → needsAction=false → 静默退出

3. Tier 2 行动: spawn Agent (model: opus)
   → Read scripts/action-dispatch.md 按 actionType 分发
   → 返回执行结果

4. 主会话: git commit + status.json 更新 + 输出摘要
```

详见 [ARCHITECTURE.md](./ARCHITECTURE.md)

## 快速开始

### 部署到 Claude Code 项目

```bash
# 1. 克隆
git clone https://code.alibaba-inc.com/qunbu/autonomous-studio.git
cd autonomous-studio

# 2. 复制到你的项目
CLAUDE_PROJECT_DIR="/path/to/your/project"

# 核心 Skill + Hooks + 决策数据 + 记忆
cp -r .claude/skills/autonomous-engine "$CLAUDE_PROJECT_DIR/.claude/skills/"
cp .claude/hooks/*.py "$CLAUDE_PROJECT_DIR/.claude/hooks/"
cp .claude/hooks/*.sh "$CLAUDE_PROJECT_DIR/.claude/hooks/"
cp .claude/decisions/calibration.json "$CLAUDE_PROJECT_DIR/.claude/decisions/"
cp .claude/memory/autonomous-state.md "$CLAUDE_PROJECT_DIR/.claude/memory/"
cp .claude/memory/decision-patterns.md "$CLAUDE_PROJECT_DIR/.claude/memory/"

# 安装 Studio Hook（幂等）
bash hooks/install-studio-hooks.sh

# (可选) 扩展技能 — 按需复制
cp -r skills/<skill-name> "$CLAUDE_PROJECT_DIR/.claude/skills/"

# 3. 验证
ls "$CLAUDE_PROJECT_DIR/.claude/skills/autonomous-engine/SKILL.md"
```

详细步骤见 [SETUP.md](./SETUP.md)

### 激活引擎

在 Claude Code 中说以下任意触发词：

- 「自主模式」「别等我」「自动继续」「keep working」「autonomous mode」
- 「继续开发」「不用等我」「你自己做」「auto-continue」
- 「全链路」「开发流程」「从需求到上线」
- 「帮我聊需求」「写PRD」「开始开发」「验证一下」「部署」

## 研发流水线

激活后，引擎将行为规则注入项目 CLAUDE.md（`<!-- STUDIO:BEGIN/END -->` 标记），驱动六阶段流水线：

| 阶段 | Skill | 产出 |
|------|-------|------|
| ① 需求探索 | `demand-discovery` | `planning/requirements.md` |
| ② 写 PRD | `pm-spec` | `planning/prd.md` + `prd.json` + `test-cases.md` |
| ③ 开发 | `serial-agent-handoff` | 可运行代码 + git push |
| ④ 验证 | 内置 `verify` | 截图 + E2E 结果 |
| ⑤ 评审 | `code-review` + `simplify` | 问题列表 + 修复 |
| ⑥ 部署 | `prod-deploy` | 线上版本 |

### 跳过规则

| 任务类型 | 走哪些阶段 |
|---------|-----------|
| 新功能 | ①→②→③→④→⑤→⑥ |
| 功能优化 | ②→③→④→⑤→⑥ |
| Bug 修复 | ③→④→⑤→⑥ |
| 文案/样式 | ③→④→⑥ |

### 状态驱动

流水线通过 `planning/status.json` 驱动，阶段完成后自动推进：

```json
{
  "currentStage": "requirements",
  "completedStages": [],
  "lastUpdated": "ISO时间",
  "taskType": "new-feature",
  "locked": true,
  "autoAdvance": true
}
```

## 核心机制

### 信心分级

| 级别 | 阈值 | 行为 |
|------|------|------|
| OBSERVE | <40 | 仅记录，不行动 |
| SUGGEST | 40-59 | 写入建议队列，等用户确认 |
| PREPARE | 60-70 | 准备工作（创建分支/文件），不执行 |
| ACT_NOTIFY | 71-84 | 执行前通知用户 |
| ACT_SILENT | 85+ | 静默执行（仅可逆操作） |

### 安全硬限制

1. 连续 3 次自主行动无用户交互 → 强制冷却
2. 不可修改 settings.json（仅限恢复已有 Hook 注册）
3. 不可修改 PROTOCOL.md
4. 不可删除用户文件
5. 不可绕过门禁

### 子 Agent 调度保障（v5.1 新增）

| 机制 | 来源 | 作用 |
|------|------|------|
| **Stuck Detection** | OpenHands stuck_detector | 检测重复动作、反复 debug、无进展空转三种卡住模式，告警注入主会话 |
| **Lint Guard** | SWE-agent ACI 论文 | Write 操作前自动校验 Python/JSON 语法，语法错误时阻断并返回错误信息 |
| **输出重试** | — | 子 Agent 返回非结构化内容时，将原始输出作为上下文要求重新格式化，而非直接丢弃 |

### 七阶段决策循环

OBSERVE → MATCH → RESEARCH → DECIDE → ACT → REPORT → LEARN

信心公式：`confidence = pattern_match(0-25) + web_corroboration(0-25) + risk_assessment(0-25) + user_preference_alignment(0-25)`

## 文件索引

### 根目录

| 文件 | 用途 |
|------|------|
| [`SKILL.md`](./SKILL.md) | 根级 Skill 定义 v5.0 — 三层心跳 + CLAUDE.md 注入 |
| [`studio-pipeline.md`](./studio-pipeline.md) | 各阶段详细执行规范（按需加载） |
| [`decision-agent-prompt.md`](./decision-agent-prompt.md) | 子 Agent 操作手册 — 七阶段研判框架 |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | 五层防御架构图 + 组件依赖矩阵 |
| [`SETUP.md`](./SETUP.md) | 安装部署指南 |
| [`AGENTS.md`](./AGENTS.md) | 30 个 Skill 导航速查表 |
| [`ALIASES.md`](./ALIASES.md) | Skill 别名定义 |

### `hooks/` — Studio Hook 脚本

| 文件 | 功能 |
|------|------|
| [`install-studio-hooks.sh`](./hooks/install-studio-hooks.sh) | Hook 安装器（幂等） |
| [`studio-auto-commit-remind.sh`](./hooks/studio-auto-commit-remind.sh) | 自动提交提醒 |
| [`studio-prd-validate.sh`](./hooks/studio-prd-validate.sh) | PRD 格式校验 |
| [`studio-progress-check.sh`](./hooks/studio-progress-check.sh) | 进度检查 |
| [`studio-lint-guard.sh`](./hooks/studio-lint-guard.sh) | ACI 风格语法守卫（Write 前校验 Python/JSON） |

### `scripts/` — 心跳辅助脚本

| 文件 | 用途 |
|------|------|
| [`studio-precheck.sh`](./scripts/studio-precheck.sh) | 心跳预检（第一步） |
| [`scanner-prompt.md`](./scripts/scanner-prompt.md) | Tier 1 扫描 agent 的 prompt |
| [`action-dispatch.md`](./scripts/action-dispatch.md) | Tier 2 行动 agent 的分发逻辑 |
| [`route-health-scorer.py`](./scripts/route-health-scorer.py) | 路线健康度评分器 |

### `skills/` — 30 个可复用 Skill

#### 研发流程链

| Skill | 用途 |
|-------|------|
| [`studio`](./skills/studio) | 研发全链路配置（阶段 Skill 地图） |
| [`agents-map`](./skills/agents-map) | 多子系统项目导航索引 |
| [`demand-discovery`](./skills/demand-discovery) | 模糊想法 → 清晰需求 |
| [`idea-exploration`](./skills/idea-exploration) | 可行性判断、产品化方向 |
| [`pm-spec`](./skills/pm-spec) | 产品需求文档 |
| [`excalidraw-diagram-skill`](./skills/excalidraw-diagram-skill) | Excalidraw 流程图/架构图 |
| [`serial-agent-handoff`](./skills/serial-agent-handoff) | 拆任务 → 子 Agent 分步开发 |
| [`prod-deploy`](./skills/prod-deploy) | 变更单 → 流水线 → 分批部署 |

#### 平台与工具

| Skill | 用途 |
|-------|------|
| [`1d-platform-dev`](./skills/1d-platform-dev) | OneDay / 1d 平台全栈开发 |
| [`a1`](./skills/a1) | 集团内部研发平台 CLI |
| [`aone-pages-skill`](./skills/aone-pages-skill) | Aone Pages 静态站点部署 |
| [`normandy-cli`](./skills/normandy-cli) | Normandy 运维平台 CLI |
| [`sunfire-cli`](./skills/sunfire-cli) | Sunfire 可观测平台 CLI |
| [`dataworks-dev-assistant`](./skills/dataworks-dev-assistant) | DataWorks 数据平台操作 |
| [`port-mapping`](./skills/port-mapping) | 获取容器端口公网地址 |
| [`runner-exec`](./skills/runner-exec) | Windows 本地文件同步 |

#### 钉钉集成

| Skill | 用途 |
|-------|------|
| [`devix-dingtalk-skill`](./skills/devix-dingtalk-skill) | 文档/表格/AI表格三合一读写 |
| [`dws`](./skills/dws) | 钉钉全产品能力 |
| [`devix-automation-skill`](./skills/devix-automation-skill) | 定时任务管理 + 钉钉通知 |
| [`dingtalk-sheet-pull-skill`](./skills/dingtalk-sheet-pull-skill) | 钉钉表格数据拉取 |

#### 内容与写作

| Skill | 用途 |
|-------|------|
| [`business-writing-coach`](./skills/business-writing-coach) | 工作写作（OKR/述职/汇报） |
| [`writing-style`](./skills/writing-style) | 写作规范检查 |
| [`generate-image`](./skills/generate-image) | GPT Image 图片生成 |

#### Agent 与复用

| Skill | 用途 |
|-------|------|
| [`memory`](./skills/memory) | 跨会话持久记忆 |
| [`agent-context-authoring`](./skills/agent-context-authoring) | AGENTS.md / CLAUDE.md 撰写 |
| [`agents-md-slim`](./skills/agents-md-slim) | 精简 AGENTS.md |
| [`luban`](./skills/luban) | Skill 打磨工坊 |
| [`zujianfuyon`](./skills/zujianfuyon) | 组件复用库操作 |
| [`resume-screener`](./skills/resume-screener) | AI 简历筛选 |

### `.claude/` — 引擎运行时

| 目录/文件 | 用途 |
|-----------|------|
| `skills/autonomous-engine/` | 核心 Skill + 子 Agent prompt |
| `hooks/` | 10 个 Hook 脚本（7 Python + 1 Shell + 2 系统级） |
| `decisions/` | 校准配置 + 25 个决策案例 + Schema |
| `memory/` | 运行状态 + 建议队列 + 模式库 |
| `codegraph/` | CodeGraph 融合层（能力注册/触点映射/集成规则） |
| `checkpoints/` | 检查点快照 |
| `sessions/` | 测试会话上下文 |
| `commands/` | 自定义命令模板 |

### `config/` — 配置示例

| 文件 | 用途 |
|------|------|
| [`phone-notify.json.example`](./config/phone-notify.json.example) | 手机通知配置 |
| [`scheduled_tasks.json.example`](./config/scheduled_tasks.json.example) | 定时任务配置 |
| [`settings.json.example`](./config/settings.json.example) | Claude Code 设置 |

### 系统级脚本

| 文件 | 用途 |
|------|------|
| [`watchdog.sh`](./watchdog.sh) | WSL 看门狗（crontab 5 分钟） |
| [`watchdog-boot.ps1`](./watchdog-boot.ps1) | Windows 开机自启看门狗 |
| [`termux-listener.py`](./termux-listener.py) | Termux TCP 通知监听 |

## 统计

| 指标 | 数值 |
|------|------|
| 总文件数 | 636 |
| Skill 目录 | 30 |
| Hook 脚本 | 10 + 5（Studio Hook） |
| 心跳脚本 | 4（precheck / scanner / dispatch / pipeline） |
| 决策案例 | 25 |
| 决策基础设施 | 9（Schema / 校准器 / 模型配置 / 通知策略 / 权限） |
| 记忆文件 | 8 |
| CodeGraph 文件 | 3 |
| 文档文件 | 8 |
| 配置示例 | 3 |

## 版本历史

| 版本 | 变更 |
|------|------|
| v5.1 | 子 Agent 调度保障：Stuck Detection + Lint Guard + 输出重试机制 |
| v5.0 | 三层心跳架构（Hook/sonnet/opus）+ Hook 双轨改造 + 30 Skill 整合 |
| v3.0 | Studio 融合 + CodeGraph + 检查点保护 + Git 回滚 |
| v2.0 | 六层防护体系 + 七阶段决策循环 |

---

*最后更新：2026-06-19 · 引擎版本 v5.1（三层心跳 + 调度保障 + 30 Skill 整合）*
