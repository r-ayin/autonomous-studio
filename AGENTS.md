# Skill 仓库导航

本仓库存放所有可复用的 Claude Code Skill。AI 进入时先读本文件，了解有哪些能力可用。

所有 Skill 已整合到本仓库 `skills/` 目录下，统一管理。

---

## 文档分层

| 层级 | 文件 | 职责 |
|------|------|------|
| 导航索引 | 本文件（AGENTS.md） | 入口地图，找 Skill 先看这里 |
| 全链路配置 | `skills/studio/SKILL.md` | 10 阶段研发流程，Skill 如何串联 |
| 别名表 | `ALIASES.md` | Skill 之间互引用的别名约定 |
| 各 Skill | `skills/<name>/SKILL.md` | 各 Skill 的详细说明 |

---

## 仓库总览

| 目录 | 用途 |
|------|------|
| `skills/` | 所有 Skill 源码（29 个） |
| `scripts/` | 辅助脚本 |
| `config/` | 配置模板 |

---

## Skill 速查表

### 研发流程链（按 Studio 阶段排列）

| 阶段 | Skill | 用途 | 位置 |
|------|-------|------|------|
| ⓪ 项目接入 | `agents-map` | 多子系统项目生成导航索引 + 架构图 | [skills/agents-map](skills/agents-map) |
| ① 需求探索 | `demand-discovery` | 模糊想法 → 清晰需求 | [skills/demand-discovery](skills/demand-discovery) |
| ①' 想法探索 | `idea-exploration` | 可行性判断、产品化方向评估 | [skills/idea-exploration](skills/idea-exploration) |
| ② 写 PRD | `pm-spec` | 产品需求文档（工作流节点 + 交互 + 联动 + 异常） | [skills/pm-spec](skills/pm-spec) |
| ③ 流程图 | `excalidraw-diagram-skill` | Excalidraw 图表（流程图/泳道图/架构图） | [skills/excalidraw-diagram-skill](skills/excalidraw-diagram-skill) |
| ⑤ 代码开发 | `serial-agent-handoff` | 拆任务 → 子 Agent 分步开发 | [skills/serial-agent-handoff](skills/serial-agent-handoff) |
| ⑥⑨ 验证 | 内置 `verify` | 启动应用 → 操作 → 截图确认 | Claude Code 内置 |
| ⑦ 代码评审 | 内置 `code-review` | 找 bug + 代码简化 | Claude Code 内置 |
| ⑧ 上线部署 | `prod-deploy` | 变更单 → 流水线 → 分批部署 | [skills/prod-deploy](skills/prod-deploy) |

### 平台与工具

| Skill | 用途 | 位置 |
|-------|------|------|
| `1d-platform-dev` | OneDay / 1d 平台全栈开发 + 数据库规范 | [skills/1d-platform-dev](skills/1d-platform-dev) |
| `a1` | 集团内部研发平台 CLI | [skills/a1](skills/a1) |
| `aone-pages-skill` | Aone Pages 静态站点部署 | [skills/aone-pages-skill](skills/aone-pages-skill) |
| `normandy-cli` | Normandy 运维平台 CLI | [skills/normandy-cli](skills/normandy-cli) |
| `sunfire-cli` | Sunfire 可观测平台 CLI | [skills/sunfire-cli](skills/sunfire-cli) |
| `port-mapping` | 获取容器端口公网地址 | [skills/port-mapping](skills/port-mapping) |
| `runner-exec` | Windows 本地文件同步 | [skills/runner-exec](skills/runner-exec) |
| `dataworks-dev-assistant` | DataWorks 数据平台操作 | [skills/dataworks-dev-assistant](skills/dataworks-dev-assistant) |

### 钉钉集成

| Skill | 用途 | 位置 |
|-------|------|------|
| `devix-dingtalk-skill` | 文档/表格/AI表格三合一读写 | [skills/devix-dingtalk-skill](skills/devix-dingtalk-skill) |
| `dws` | 钉钉全产品能力 | [skills/dws](skills/dws) |
| `devix-automation-skill` | 定时任务管理 + 钉钉通知 | [skills/devix-automation-skill](skills/devix-automation-skill) |
| `dingtalk-sheet-pull-skill` | 钉钉表格数据拉取到前端项目 | [skills/dingtalk-sheet-pull-skill](skills/dingtalk-sheet-pull-skill) |

### 内容与写作

| Skill | 用途 | 位置 |
|-------|------|------|
| `business-writing-coach` | 工作写作（OKR/述职/汇报） | [skills/business-writing-coach](skills/business-writing-coach) |
| `writing-style` | 写作规范检查 | [skills/writing-style](skills/writing-style) |
| `generate-image` | GPT Image 图片生成 | [skills/generate-image](skills/generate-image) |

### 组件与复用

| Skill | 用途 | 位置 |
|-------|------|------|
| `zujianfuyon` | 组件复用库操作 | [skills/zujianfuyon](skills/zujianfuyon) |
| `zujianfuyon-skill` | 组件复用技能 | [skills/zujianfuyon-skill](skills/zujianfuyon-skill) |

### Agent 与记忆

| Skill | 用途 | 位置 |
|-------|------|------|
| `memory` | 跨会话持久记忆 | [skills/memory](skills/memory) |
| `agent-context-authoring` | AGENTS.md / CLAUDE.md 撰写 | [skills/agent-context-authoring](skills/agent-context-authoring) |
| `agents-md-slim` | 精简 AGENTS.md | [skills/agents-md-slim](skills/agents-md-slim) |
| `luban` | Skill 打磨工坊 | [skills/luban](skills/luban) |

### 全局入口

| Skill | 用途 | 位置 |
|-------|------|------|
| `studio` | **研发全链路配置**（10 阶段 Skill 地图） | [skills/studio](skills/studio) |

---

## 待收录 Skill

| Skill | 用途 | 待收录原因 |
|-------|------|-----------|
| `resume-screener` | AI 简历筛选 | 已复制到 skills/resume-screener，绑定招聘项目训练数据 |

---

## 阅读顺序

1. **想了解全局** → 读 `skills/studio/SKILL.md`
2. **想找某个能力** → 看上面速查表，点链接进入
3. **想给 Skill 起别名** → 看 `ALIASES.md`
4. **想新增 Skill** → 创建 `skills/<name>/SKILL.md`，更新本文件

---

## 维护规则

- 新增 Skill → 在 `skills/` 下创建目录 + SKILL.md，速查表加一行
- 删除 Skill → 从速查表移除 + 检查 ALIASES.md + 删除 skills/ 下目录
- 更新 Skill → 直接修改 `skills/<name>/` 下的文件
- 含凭据的配置文件（servers.json 等）不上传（已在 .gitignore 中排除）
