# Studio — 研发全链路流程路由器

> 状态感知的研发流程路由器。自动检测项目当前走到哪一步，告诉你下一步该做什么。
> 不是菜单，是导航。

## 概述

Studio 将研发全流程分为 7 个阶段，每个阶段对应一个或多个 Skill。它通过读取 `.planning/status.json` 实现跨对话状态记忆，自动判断当前进度并建议下一步行动。

```
需求 → PRD → 技术方案 → 开发 → 验证 → 评审 → 部署
  ↑                                ↓
  └──── 验证不通过时回退 ───────────┘
```

**来源仓库**：https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/studio

## 文件索引

### 🔧 核心文件

| 文件 | 用途 |
|------|------|
| [`SKILL.md`](./SKILL.md) | Studio 主 Skill — 7 阶段流程路由 + 状态检测 + 跳过/回退规则 |
| [`hooks/check-planning-status.sh`](./hooks/check-planning-status.sh) | PostToolUse Hook — git commit 后检查 status.json 是否同步更新 |

### 📋 导航与配置

| 文件 | 用途 |
|------|------|
| [`AGENTS.md`](./AGENTS.md) | Skill 仓库导航 — 全部 Skill 速查表 + 仓库地图 |
| [`ALIASES.md`](./ALIASES.md) | Skill 别名约定 — 互引用时的名称映射 |

### 🎯 研发流程链 Skills（按 Studio 阶段排列）

| 阶段 | Skill | 文件数 | 目录 |
|------|-------|--------|------|
| ⓪ 项目接入 | `agents-map` | 2 | [`skills/agents-map/`](./skills/agents-map/) |
| ① 需求探索 | `demand-discovery` | 1 | [`skills/demand-discovery/`](./skills/demand-discovery/) |
| ①' 想法探索 | `idea-exploration` | 1 | [`skills/idea-exploration/`](./skills/idea-exploration/) |
| ② 写 PRD | `pm-spec` | 1 | [`skills/pm-spec/`](./skills/pm-spec/) |
| ③ 技术方案 | `plan-feature` | 1 | [`commands/plan-feature.md`](./commands/plan-feature.md) |
| ④ 代码开发 | `serial-agent-handoff` | 2 | [`skills/serial-agent-handoff/`](./skills/serial-agent-handoff/) |
| ⑦ 上线部署 | `prod-deploy` | 13 | [`skills/prod-deploy/`](./skills/prod-deploy/) |

### 🔨 辅助 Skills

| Skill | 用途 | 文件数 | 目录 |
|-------|------|--------|------|
| `zujianfuyon` | 组件复用库操作 | 3 | [`skills/zujianfuyon/`](./skills/zujianfuyon/) |
| `memory` | 跨会话持久记忆 | 10 | [`skills/memory/`](./skills/memory/) |

### ⚠️ 外部依赖（不在本仓库）

| Skill | 用途 | 仓库地址 |
|-------|------|---------|
| `excalidraw-diagram-skill` | Excalidraw 流程图/泳道图 | https://code.alibaba-inc.com/xiqxhq/excalidraw-skill |
| `devix-dingtalk-skill` | PRD 写入钉钉文档 | 未收录到源仓库 |
| `verify` | 启动应用验证 | Claude Code 内置 |
| `code-review` | 代码评审 | Claude Code 内置 |
| `simplify` | 代码简化 | Claude Code 内置 |

## 完整文件清单

```
studio_raw/
├── README.md                              ← 本文件
├── SKILL.md                               ← Studio 主 Skill（流程路由）
├── AGENTS.md                              ← Skill 导航索引
├── ALIASES.md                             ← Skill 别名表
├── hooks/
│   └── check-planning-status.sh           ← status.json 同步检查
├── commands/
│   └── plan-feature.md                    ← ③ 技术方案命令
└── skills/
    ├── agents-map/                        ← ⓪ 项目接入 (2 files)
    │   ├── SKILL.md
    │   └── references/agents_principles.md
    ├── demand-discovery/                  ← ① 需求探索 (1 file)
    │   └── SKILL.md
    ├── idea-exploration/                  ← ①' 想法探索 (1 file)
    │   └── SKILL.md
    ├── pm-spec/                           ← ② PRD (1 file)
    │   └── SKILL.md
    ├── serial-agent-handoff/              ← ④ 代码开发 (2 files)
    │   ├── SKILL.md
    │   └── references/handoff-template.md
    ├── prod-deploy/                       ← ⑦ 部署 (13 files)
    │   ├── SKILL.md
    │   ├── references/
    │   │   ├── pipeline-hierarchy.md
    │   │   └── troubleshooting.md
    │   └── scripts/
    │       ├── complete-task.js
    │       ├── list-events.js
    │       ├── poll-build.js
    │       ├── poll-pre-check.js
    │       ├── report-event.js
    │       ├── report-observation.js
    │       ├── resume-next-batch.js
    │       └── lib/
    │           ├── event-client.js
    │           ├── extract-url-from-tips.js
    │           ├── sunfire-client.js
    │           └── task-client.js
    ├── zujianfuyon/                       ← 组件复用 (3 files)
    │   ├── SKILL.md
    │   ├── references/component-index.md
    │   └── scripts/ensure-repo
    └── memory/                            ← 持久记忆 (10 files)
        ├── SKILL.md
        ├── README.md
        ├── package.json
        ├── scripts/
        │   ├── install.sh
        │   ├── memory
        │   ├── space-memory
        │   ├── user-memory
        │   └── lib/memory-common.sh
        └── tests/
            ├── run_tests.sh
            └── skill_test_cases.md
```

## 统计

| 指标 | 数值 |
|------|------|
| 总文件数 | 39 |
| 核心 Skill | 1 (studio) |
| 流程链 Skills | 7 |
| 辅助 Skills | 2 |
| Hook 脚本 | 1 |
| 导航/配置文件 | 2 |
| 外部依赖 | 5 |

---

*最后更新：2026-06-17 · 来源：xiqxhq/claude.MD*
