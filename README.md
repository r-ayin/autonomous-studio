# autonomous-studio — 自主开发引擎 v3.0

> **七阶段自主决策系统**：OBSERVE → MATCH → RESEARCH → DECIDE → ACT → REPORT → LEARN
> **七阶段 Studio 流水线**：需求发现 → PRD → 技术方案 → 开发 → 验证 → 评审 → 部署
> **六层防护体系**：L1 Inline / L2 Heartbeat / L3 Deep / L4 自举 / L5 固件注入 / L6 WSL Watchdog

## 概述

autonomous-studio 是一个运行在 Claude Code 之上的自主开发引擎。它使 AI Agent 能够在会话空闲时自动延续已建立的开发方向，同时受信心分级和硬限制约束确保安全。v3.0 新增 Studio 7 阶段研发流水线、CodeGraph 代码图谱融合层、发现门禁机制。

- **版本**：v3.0（Studio 融合 + CodeGraph + 检查点保护 + Git 回滚）
- **架构**：调度器模式 — 主会话 spawn 独立子 Agent，零上下文污染
- **语言**：Markdown（Skill/Prompt）+ Python（Hooks）+ Shell + JavaScript + JSON（配置/校准）

## 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    六层防护体系                              │
├──────┬──────────────────────────────────────────────────────┤
│  L1  │ Inline 检查 — 每次回复末尾内联自检                     │
│  L2  │ Heartbeat — CronCreate 每 30 分钟                      │
│  L3  │ Deep Check — CronCreate 每 60 分钟（自适应降频）         │
│  L4  │ 自举守护 — 检测组件缺失 → 自动重建                      │
│  L5  │ SessionStart 固件注入 — 每次启动强制注入引擎指令          │
│  L6  │ WSL Watchdog — 系统级 crontab 每 5 分钟（独立进程）       │
├──────┴──────────────────────────────────────────────────────┤
│  七阶段循环：OBSERVE → MATCH → RESEARCH → DECIDE → ACT → REPORT → LEARN │
│  信心分级（0-100）：OBSERVE / SUGGEST / PREPARE / ACT_NOTIFY / ACT_SILENT  │
└─────────────────────────────────────────────────────────────┘
```

详见 [ARCHITECTURE.md](./ARCHITECTURE.md)

## 文件索引

### 📁 `autonomous-engine/` — 项目入口

| 文件 | 用途 | 类型 |
|------|------|------|
| [`CLAUDE.md`](./autonomous-engine/CLAUDE.md) | 引擎文档入口 — 完整文件地图与机制说明 | 文档 |
| [`PROGRESS.md`](./autonomous-engine/PROGRESS.md) | 引擎演进历史 — 版本变更记录 | 追踪 |
| [`GATES.md`](./autonomous-engine/GATES.md) | 质量门禁 — CRITICAL/IMPORTANT/NICE 三级检查清单 | 质量 |

### 📁 `.claude/skills/autonomous-engine/` — Skill 核心

| 文件 | 用途 | 类型 |
|------|------|------|
| [`SKILL.md`](./.claude/skills/autonomous-engine/SKILL.md) | 调度器 Skill — 主会话激活入口，负责 spawn 子 Agent | Skill |
| [`decision-agent-prompt.md`](./.claude/skills/autonomous-engine/decision-agent-prompt.md) | 子 Agent 操作手册 — 七阶段研判框架 + 冷启动协议 | Prompt |

### 📁 `.claude/hooks/` — Hook 脚本

| 文件 | 触发时机 | 功能 | 类型 |
|------|---------|------|------|
| [`decision-observer.py`](./.claude/hooks/decision-observer.py) | UserPromptSubmit, Stop | 输入分类、Studio 上下文注入、会话日志 | Hook |
| [`save-checkpoint.py`](./.claude/hooks/save-checkpoint.py) | PreCompact, Stop, SessionEnd | 三层检查点保护 | Hook |
| [`resume-checkpoint.py`](./.claude/hooks/resume-checkpoint.py) | SessionStart | 固件注入引擎指令 + 检查点恢复 + Studio 状态恢复 | Hook |
| [`incremental-save.py`](./.claude/hooks/incremental-save.py) | Stop | 增量保存 + 检查点联动 + Studio 状态快照 | Hook |
| [`notify-phone.py`](./.claude/hooks/notify-phone.py) | Stop, PostToolUse | 手机通知（ntfy.sh / TCP 隧道 / 钉钉 Webhook） | Hook |
| [`protocol-check.py`](./.claude/hooks/protocol-check.py) | PreToolUse, PostToolUse | 项目协议自举检查 + Studio artifact 校验 | Hook |
| [`auto-commit.py`](./.claude/hooks/auto-commit.py) | Stop | 自动提交 | Hook |
| [`check-planning-status.sh`](./.claude/hooks/check-planning-status.sh) | PreToolUse | 规划状态检查 | Hook |
| [`codegraph-sync.py`](./.claude/hooks/codegraph-sync.py) | PostToolUse | CodeGraph 自动同步 | Hook |
| [`discovery-gate.py`](./.claude/hooks/discovery-gate.py) | PreToolUse | 发现门禁 — 系统级硬阻断 | Hook |

### 📁 `.claude/decisions/` — 决策数据

| 文件 | 用途 | 类型 |
|------|------|------|
| [`calibration.json`](./.claude/decisions/calibration.json) | 中央校准 — 模式注册、冷却状态、L3 发现、用户偏好 | 配置 |
| [`schema.md`](./.claude/decisions/schema.md) | 数据结构文档 — case JSON 字段定义 | 文档 |
| [`decision-archive.md`](./.claude/decisions/decision-archive.md) | 归档案例汇总 — 学到的教训 | 知识 |
| `case-2026-06-15-001.json` ~ `case-2026-06-17-002.json` | 21 个决策案例记录 | 数据 |
| [`audit-log.schema.json`](./.claude/decisions/audit-log.schema.json) | 审计日志 Schema | 文档 |
| [`team-decision-log.schema.json`](./.claude/decisions/team-decision-log.schema.json) | 团队决策日志 Schema | 文档 |
| [`confidence-calibrator.js`](./.claude/decisions/confidence-calibrator.js) | 置信度校准器 | 工具 |
| [`model-profiles.json`](./.claude/decisions/model-profiles.json) | 模型配置 | 配置 |
| [`notification-policy.json`](./.claude/decisions/notification-policy.json) | 通知策略（免打扰时段等）| 配置 |
| [`role-permissions.json`](./.claude/decisions/role-permissions.json) | 角色权限矩阵 | 配置 |

### 📁 `.claude/memory/` — 记忆系统

| 文件 | 用途 | 类型 |
|------|------|------|
| [`autonomous-state.md`](./.claude/memory/autonomous-state.md) | 引擎运行状态 — 目标、冷却计数、协议版本 | 状态 |
| [`autonomous-suggestions.md`](./.claude/memory/autonomous-suggestions.md) | 瞭望扫描发现 — 待用户确认的建议 | 队列 |
| [`decision-patterns.md`](./.claude/memory/decision-patterns.md) | 已提取的模式库 — MATCH 阶段输入 | 知识 |
| [`session-progress.md`](./.claude/memory/session-progress.md) | 跨会话进度追踪 | 状态 |
| [`MEMORY.md`](./.claude/memory/MEMORY.md) | 记忆索引 | 索引 |
| [`phone-notify.md`](./.claude/memory/phone-notify.md) | 通知配置参考 | 配置 |
| [`project-index.md`](./.claude/memory/project-index.md) | 项目索引 | 索引 |
| [`wechat-push-reference.md`](./.claude/memory/wechat-push-reference.md) | 微信推送参考 | 配置 |

### 📁 `.claude/checkpoints/` & `.claude/sessions/` — 运行时数据

| 文件 | 用途 | 类型 |
|------|------|------|
| [`checkpoints/latest.json`](./.claude/checkpoints/latest.json) | 最新检查点快照 | 状态 |
| `sessions/test-*.json` | 测试会话上下文 | 数据 |

### 📁 `.claude/codegraph/` — CodeGraph 融合层 (v3.0 新增)

| 文件 | 用途 | 类型 |
|------|------|------|
| [`capability-registry.json`](./.claude/codegraph/capability-registry.json) | 能力注册表 | 配置 |
| [`engine-touchpoints.json`](./.claude/codegraph/engine-touchpoints.json) | 引擎触点映射 | 配置 |
| [`integration-rules.json`](./.claude/codegraph/integration-rules.json) | 集成规则 | 配置 |

### 📁 `.claude/commands/` — 自定义命令

| 文件 | 用途 | 类型 |
|------|------|------|
| [`plan-feature.md`](./.claude/commands/plan-feature.md) | 功能规划命令模板 | 命令 |

### 📁 `.claude/skills/` — 扩展技能 (v3.0 新增)

| 目录 | 用途 | 文件数 |
|------|------|--------|
| `memory/` | 记忆管理系统 | 8 |
| `prod-deploy/` | 生产部署技能 | 13 |
| `serial-agent-handoff/` | 串行 Agent 交接 | 1 |
| `agents-map/` | Agent 原则参考 | 1 |
| `zujianfuyon/` | 组件服务技能 | 2 |
| `demand-discovery/` | 需求发现 | 1 |
| `idea-exploration/` | 创意探索 | 1 |
| `pm-spec/` | 产品规格 | 1 |

### 📁 `.claude/` — 其他引擎文件

| 文件 | 用途 | 类型 |
|------|------|------|
| [`decision-log.jsonl`](./.claude/decision-log.jsonl) | 决策日志 — decision-observer.py 写入 | 日志 |
| [`scheduled_tasks.json`](./.claude/scheduled_tasks.json) | CronCreate 定时任务配置 | 配置 |

### 📁 根目录文档 & 脚本

| 文件 | 用途 | 类型 |
|------|------|------|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | 五层防御架构图 + 组件依赖矩阵 | 文档 |
| [`SETUP.md`](./SETUP.md) | 安装部署指南 | 文档 |
| [`AGENTS.md`](./AGENTS.md) | Skill 导航表 | 文档 |
| [`ALIASES.md`](./ALIASES.md) | @alias 定义 | 文档 |
| [`README.md`](./README.md) | 本文件 — 项目索引 | 文档 |
| [`watchdog.sh`](./watchdog.sh) | L6 WSL 看门狗 — 系统级 crontab 监控 | 脚本 |
| [`watchdog-boot.ps1`](./watchdog-boot.ps1) | Windows 开机自启看门狗 | 脚本 |
| [`termux-listener.py`](./termux-listener.py) | Termux TCP 通知监听 | 脚本 |
| [`scripts/route-health-scorer.py`](./scripts/route-health-scorer.py) | 路线健康度评分器 | 脚本 |

### 📁 `config/` — 配置示例

| 文件 | 用途 | 类型 |
|------|------|------|
| [`phone-notify.json.example`](./config/phone-notify.json.example) | 手机通知配置示例 | 示例 |
| [`scheduled_tasks.json.example`](./config/scheduled_tasks.json.example) | 定时任务配置示例 | 示例 |
| [`settings.json.example`](./config/settings.json.example) | Claude Code 设置示例 | 示例 |

## 快速开始

### 部署到 Claude Code 项目

```bash
# 1. 克隆本仓库
git clone https://code.alibaba-inc.com/xtool/autonomous-engine.git
cd autonomous-engine

# 2. 复制文件到你的 Claude Code 项目
CLAUDE_PROJECT_DIR="/path/to/your/project"

cp -r .claude/skills/autonomous-engine "$CLAUDE_PROJECT_DIR/.claude/skills/"
cp .claude/hooks/*.py "$CLAUDE_PROJECT_DIR/.claude/hooks/"
cp .claude/decisions/calibration.json "$CLAUDE_PROJECT_DIR/.claude/decisions/"
cp .claude/memory/autonomous-state.md "$CLAUDE_PROJECT_DIR/.claude/memory/"
cp .claude/memory/autonomous-suggestions.md "$CLAUDE_PROJECT_DIR/.claude/memory/"
cp .claude/memory/decision-patterns.md "$CLAUDE_PROJECT_DIR/.claude/memory/"

# 3. 验证
ls "$CLAUDE_PROJECT_DIR/.claude/skills/autonomous-engine/SKILL.md"
ls "$CLAUDE_PROJECT_DIR/.claude/decisions/calibration.json"
```

详细步骤见 [SETUP.md](./SETUP.md)

### 激活引擎

在 Claude Code 中说以下任意触发词：
- 「自主模式」
- 「别等我」
- 「自动继续」
- 「auto-continue」
- 「keep working」

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

## 统计

| 指标 | 数值 |
|------|------|
| 总文件数 | 107+ |
| Skill 文件 | 10+ (含 8 个子技能目录) |
| Hook 脚本 | 10 |
| 决策案例 | 21 |
| 决策基础设施 | 6 (Schema/校准器/配置) |
| 记忆文件 | 8 |
| CodeGraph 文件 | 3 |
| 文档文件 | 10+ |
| 配置/数据/脚本 | 10+ |

---

*最后更新：2026-06-18 · 引擎版本 v3.0 (Studio 融合)*
