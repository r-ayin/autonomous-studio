# Skill 仓库导航

本仓库存放所有可复用的 Claude Code Skill。AI 进入时先读本文件，了解有哪些能力可用。

所有仓库均在 [code.alibaba-inc.com/xiqxhq](https://code.alibaba-inc.com/xiqxhq) 下。

---

## 文档分层

| 层级 | 文件 | 职责 |
|------|------|------|
| 导航索引 | 本文件（AGENTS.md） | 入口地图，找 Skill 先看这里 |
| 全链路配置 | `studio/SKILL.md` | 10 阶段研发流程，Skill 如何串联 |
| 别名表 | `ALIASES.md` | Skill 之间互引用的别名约定 |
| 各 Skill | `<name>/SKILL.md` | 各 Skill 的详细说明 |

---

## 仓库总览

| 仓库 | 地址 | 用途 |
|------|------|------|
| **claude.MD** | [xiqxhq/claude.MD](https://code.alibaba-inc.com/xiqxhq/claude.MD) | Skill 总仓库 + Studio 配置 + 记忆备份 |
| **excalidraw-skill** | [xiqxhq/excalidraw-skill](https://code.alibaba-inc.com/xiqxhq/excalidraw-skill) | Excalidraw 图表技能（独立仓库，含泳道模板 + 验证脚本 + Hook） |
| **zujianfuyon** | [xiqxhq/zujianfuyon](https://code.alibaba-inc.com/xiqxhq/zujianfuyon) | 组件复用库 |
| **chuizhihua** | [xiqxhq/chuizhihua](https://code.alibaba-inc.com/xiqxhq/chuizhihua) | 搜推运营工具 + Excalidraw 图表文件 |

---

## Skill 速查表

### 研发流程链（按 Studio 阶段排列）

| 阶段 | Skill | 用途 | 位置 |
|------|-------|------|------|
| ⓪ 项目接入 | `agents-map` | 多子系统项目生成导航索引 + 架构图 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/agents-map) |
| ① 需求探索 | `demand-discovery` | 模糊想法 → 清晰需求 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/demand-discovery) |
| ①' 想法探索 | `idea-exploration` | 可行性判断、产品化方向评估 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/idea-exploration) |
| ② 写 PRD | `pm-spec` | 产品需求文档（工作流节点 + 交互 + 联动 + 异常） | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/pm-spec) |
| ③ 流程图 | `excalidraw-diagram-skill` | Excalidraw 图表（流程图/泳道图/架构图） | [独立仓库](https://code.alibaba-inc.com/xiqxhq/excalidraw-skill) |
| ④ 技术方案 | `plan-feature` | 代码库分析 → 分步实现计划 | [auto-coding 命令](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/auto-coding-v2.1/.claude/commands) |
| ⑤ 代码开发 | `serial-agent-handoff` | 拆任务 → 子 Agent 分步开发 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/serial-agent-handoff) |
| ⑥⑨ 验证 | 内置 `verify` | 启动应用 → 操作 → 截图确认 | Claude Code 内置 |
| ⑦ 代码评审 | 内置 `code-review` | 找 bug + 代码简化 | Claude Code 内置 |
| ⑧ 上线部署 | `prod-deploy` | 变更单 → 流水线 → 分批部署 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/prod-deploy) |

### 平台与工具

| Skill | 用途 | 位置 |
|-------|------|------|
| `1d-platform-dev` | OneDay / 1d 平台全栈开发 + 数据库规范 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/1d-platform-dev) |
| `a1` | 集团内部研发平台 CLI | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/a1) |
| `aone-pages-skill` | Aone Pages 静态站点部署 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/aone-pages-skill) |
| `normandy-cli` | Normandy 运维平台 CLI | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/normandy-cli) |
| `sunfire-cli` | Sunfire 可观测平台 CLI | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/sunfire-cli) |
| `port-mapping` | 获取容器端口公网地址 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/port-mapping) |
| `runner-exec` | Windows 本地文件同步 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/runner-exec) |
| `dataworks-dev-assistant` | DataWorks 数据平台操作 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/dataworks-dev-assistant) |

### 钉钉集成

| Skill | 用途 | 位置 |
|-------|------|------|
| `devix-dingtalk-skill` | 文档/表格/AI表格三合一读写 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/devix-dingtalk-skill) |
| `dws` | 钉钉全产品能力 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/dws) |
| `devix-automation-skill` | 定时任务管理 + 钉钉通知 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/devix-automation-skill) |
| `dingtalk-sheet-pull-skill` | 钉钉表格数据拉取到前端项目 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/dingtalk-sheet-pull-skill) |

### 内容与写作

| Skill | 用途 | 位置 |
|-------|------|------|
| `business-writing-coach` | 工作写作（OKR/述职/汇报） | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/business-writing-coach) |
| `writing-style` | 写作规范检查 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/writing-style) |
| `generate-image` | GPT Image 图片生成 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/generate-image) |

### 组件与复用

| Skill | 用途 | 位置 |
|-------|------|------|
| `zujianfuyon` | 组件复用库操作 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/zujianfuyon) + [组件仓库](https://code.alibaba-inc.com/xiqxhq/zujianfuyon) |
| `zujianfuyon-skill` | 组件复用技能 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/zujianfuyon-skill) |

### Agent 与记忆

| Skill | 用途 | 位置 |
|-------|------|------|
| `memory` | 跨会话持久记忆 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/memory) |
| `agent-context-authoring` | AGENTS.md / CLAUDE.md 撰写 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/agent-context-authoring) |
| `agents-md-slim` | 精简 AGENTS.md | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/agents-md-slim) |
| `luban` | Skill 打磨工坊 | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/luban) |

### 全局入口

| Skill | 用途 | 位置 |
|-------|------|------|
| `studio` | **研发全链路配置**（10 阶段 Skill 地图） | [本仓库](https://code.alibaba-inc.com/xiqxhq/claude.MD/tree/master/.codex/skills/studio) |

---

## 待收录 Skill

| Skill | 用途 | 待收录原因 |
|-------|------|-----------|
| `resume-screener` | AI 简历筛选 | 绑定招聘项目训练数据，暂不收录 |

---

## 阅读顺序

1. **想了解全局** → 读 `studio/SKILL.md`
2. **想找某个能力** → 看上面速查表，点链接进入
3. **想给 Skill 起别名** → 看 `ALIASES.md`
4. **想新增 Skill** → 创建 `<name>/SKILL.md`，更新本文件

---

## 维护规则

- 新增 Skill → 速查表加一行，带仓库链接
- 删除 Skill → 从速查表移除 + 检查 ALIASES.md
- 本地 Skill 同步到仓库后 → 从「待收录」移到正式速查表
- 含凭据的配置文件（servers.json 等）不上传
