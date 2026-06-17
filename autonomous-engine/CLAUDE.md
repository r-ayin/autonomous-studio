# autonomous-engine — 自主决策引擎 v2.2

> 七阶段自主决策系统：OBSERVE → MATCH → RESEARCH → DECIDE → ACT → REPORT → LEARN
> 六层防护：L1 Inline / L2 Heartbeat / L3 Deep / L4 自举 / L5 固件注入 / L6 WSL Watchdog

## 项目身份
- **名称**：autonomous-engine（自主决策引擎）
- **版本**：v2.2（检查点保护 + Git 回滚）
- **目的**：会话空闲时自动延续已建立的开发方向，受信心分级和硬限制约束
- **语言**：Markdown（Skill）+ Python（Hooks）+ JSON（配置/校准）

## 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    六层防护体系                              │
├──────┬──────────────────────────────────────────────────────┤
│  L1  │ Inline 检查 — 每次回复末尾内联自检                     │
│  L2  │ Heartbeat — CronCreate 每 30 分钟                       │
│  L3  │ Deep Check — CronCreate 每 60 分钟（自适应降频）          │
│  L4  │ 自举守护 — 检测组件缺失 → 自动重建                       │
│  L5  │ SessionStart 固件注入 — 每次启动强制注入引擎指令           │
│  L6  │ WSL Watchdog — 系统级 crontab 每 5 分钟（独立进程）        │
├──────┴──────────────────────────────────────────────────────┤
│  七阶段循环：OBSERVE → MATCH → RESEARCH → DECIDE → ACT → REPORT → LEARN │
│  信心分级（0-100）：OBSERVE / SUGGEST / PREPARE / ACT_NOTIFY / ACT_SILENT  │
└─────────────────────────────────────────────────────────────┘
```

## 文件地图

> 运行时文件分布在不同目录（受 Claude Code 基础设施约束）。本目录是引擎的**项目身份入口**。

### 🏠 项目目录 `autonomous-engine/`
| 文件 | 用途 |
|------|------|
| `CLAUDE.md` | 本文件 — 引擎文档入口 |
| `PROGRESS.md` | 引擎演进历史 |
| `GATES.md` | 引擎质量门禁 |

### 🧠 Skill（`.claude/skills/autonomous-engine/`）
| 文件 | 用途 |
|------|------|
| `SKILL.md` | 引擎调度器 Skill — 主会话激活入口 |
| `decision-agent-prompt.md` | 子 Agent 操作手册 — 独立上下文执行 |

### 📊 决策数据（`.claude/decisions/`）
| 文件 | 用途 |
|------|------|
| `calibration.json` | 中央校准 — 模式注册、冷却状态、L3 发现、用户偏好 |
| `decision-archive.md` | 归档案例汇总 — 学到的教训 |
| `schema.md` | 数据结构文档 |
| `case-*.json` | 单个决策案例（16 个已归档） |

### 🧩 记忆系统（`.claude/memory/`）
| 文件 | 用途 |
|------|------|
| `autonomous-state.md` | 引擎运行状态 — 目标、冷却计数、协议版本 |
| `autonomous-suggestions.md` | 瞭望扫描发现 — 待用户确认的建议 |
| `decision-patterns.md` | 已提取的模式库 — MATCH 阶段输入 |
| `session-progress.md` | 跨会话进度追踪 |

### 🔌 Hooks（`.claude/hooks/`）
| 文件 | 触发时机 | 功能 |
|------|---------|------|
| `decision-observer.py` | UserPromptSubmit, Stop | 输入分类、上下文注入、会话日志 |
| `save-checkpoint.py` | PreCompact, SessionEnd, Stop | 三层检查点保护 |
| `resume-checkpoint.py` | SessionStart | 固件注入引擎指令 |
| `incremental-save.py` | Stop | 增量保存 + 检查点联动 |

### ⏰ 定时任务
| ID | Cron | 功能 |
|----|------|------|
| `0a291b1f` | `23,53 * * * *` | L2 Heartbeat（每 30 分钟） |
| `53e6f6f8` | `43 * * * *` | L3 Deep Check（每小时） |

### 📋 其他
| 文件 | 用途 |
|------|------|
| `.claude/decision-log.jsonl` | 决策日志 — `decision-observer.py` 写入 |
| `.claude/checkpoints/latest.json` | 最新检查点 |
| `.claude/sessions/{id}.json` | 会话上下文文件 |
| `.claude/.watchdog_heartbeat` | 看门狗心跳 |
| `.claude/watchdog.sh` | WSL 系统级 crontab（L6） |

## 核心机制

### 冷启动协议 v2.2
- 旧行为：SUGGEST only，不可执行操作
- 新行为：检查点保护下可达 ACT_SILENT，失败自动 git reset --hard 回滚
- 可逆操作（文件修改/测试/commit）→ ACT_SILENT
- 不可逆操作（push/deploy/destroy）→ ACT_NOTIFY + 用户确认

### 信心分级
| 级别 | 阈值 | 行为 |
|------|------|------|
| OBSERVE | <40 | 仅记录，不行动 |
| SUGGEST | 40-59 | 写入 suggestions，等用户确认 |
| PREPARE | 60-70 | 准备工作（创建分支/文件），不执行 |
| ACT_NOTIFY | 71-84 | 执行前通知用户 |
| ACT_SILENT | 85+ | 静默执行（仅可逆操作） |

### 硬限制
1. 连续 3 次自主行动无用户交互 → 强制冷却
2. 不可修改 settings.json（仅限恢复已有 Hook）、PROTOCOL.md、用户文件
3. 不可绕过门禁

## 快速命令
```bash
# 查看引擎状态
cat .claude/memory/autonomous-state.md

# 查看校准数据
cat .claude/decisions/calibration.json | head -20

# 查看最近决策
tail -5 .claude/decision-log.jsonl

# 手动激活引擎
说「自主模式」或「别等我」或「auto-continue」
```

## 关联项目
- x-tool 工作区 `CLAUDE.md` — 阶段 5 自主决策引擎章节
- x-tool 工作区 `ARCHITECTURE.md` — 架构图
- x-tool 工作区 `SETUP.md` — 引擎安装说明
