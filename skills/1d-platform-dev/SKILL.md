---
name: 1d-platform-dev
description: >-
  阿里 1d 平台 / OneDay 全栈开发。涵盖平台概述、AI应用创作、Workflow工作流编排、
  知识库(RAG)、Agent开发、用户认证、工具集成、WebContainer项目配置、
  OneDay Cloud 数据库（Supabase）、@ali/oneday-frontend-sdk 用法、
  OneDayCloudEnable 项目初始化、OneDayCloudSearchDocs 文档查询。
  当用户提到 OneDay、1d平台、工作流、知识库、RAG、AI应用、webpack配置、
  OneDayCloud、oneday-frontend-sdk、Supabase、数据库初始化、
  OneDayCloudEnable、OneDayCloudSearchDocs 时使用此 skill。
repository: https://code.alibaba-inc.com/qunbu/1d-platform-dev
version: 1.3.1
---

# OneDay / 1d 平台全栈开发指南

> **源仓库**：https://code.alibaba-inc.com/claudecode/skills/tree/master/1d-platform-dev
> 更新 Skill 内容时，修改此仓库对应目录后同步到本地 `~/.claude/skills/1d-platform-dev/`。

> **如何使用本 skill**：本文件是索引，详细内容在子文件中。
> 遇到具体问题时，用 Read 工具读取对应子文件获取完整代码和排查步骤。

## 平台速查

**入口**：`https://1d.alibaba-inc.com/` | 预发：`https://pre-1d.alibaba-inc.com/`

**五种应用类型**

| 类型 | 特点 | 适用场景 |
|------|------|---------|
| 聊天助手 | 多轮对话，上下文持续保存 | 客服、知识问答 |
| Chatflow | 节点编排对话流，多轮记忆+流式输出 | 复杂多轮对话 |
| Workflow | 自动化批处理，无 Memory，有结束节点 | 数据管线、定时任务 |
| Agent | 任务分解→工具调用→迭代执行 | 报表分析、规划 |
| 文本生成型 | 表单+结果，上下文仅当次有效 | 翻译、文本分类 |

## WebContainer 核心约束（最高频踩坑）

```
OneDay = webpack 5 + webpack-dev-server 4.x + HashRouter + allowedHosts all + historyApiFallback + anpm
双层架构 = webpack-dev-server:3019 → proxy /api → Express:3020
Express启动 = predev 钩子后台拉起，禁止在 webpack 钩子中 require()
永远不要用 Vite / esbuild / rollup / BrowserRouter / http.createServer()
```

**OneDay Cloud 核心约束**

```
必须用 @ali/oneday-frontend-sdk，禁止直接用 @supabase/supabase-js
externals 必须用 var 前缀格式（不是 commonjs）
项目设置 → 数据库 → 开启 OneDay Cloud（否则 token=undefined → 403）
```

## 新建项目脚手架

**当用户说"新建一个 OneDay 项目"时，使用 `templates/` 目录下的模板，不要从零手写配置。**

模板路径：`~/.claude/skills/1d-platform-dev/templates/`

| 模板 | 适用场景 | 前端端口 | API 端口 |
|------|---------|---------|---------|
| `oneday-lite/` | 纯前端看板，无需后端 | 3019 | — |
| `oneday-standard/` | TS + React + Tailwind，无需后端 | 3019 | — |
| `oneday-full/` | TS + React + Tailwind + Express + JWT 鉴权 | 3019 | 9000 |

### 初始化流程

```bash
TEMPLATE=oneday-full   # 或 oneday-lite / oneday-standard
TARGET=/home/admin/workspace/<项目名>

cp -r ~/.claude/skills/1d-platform-dev/templates/$TEMPLATE $TARGET
cd $TARGET
npm install
npm run dev   # 打开 OneDay 平台即可预览
```

### 选择模板的判断标准

- 只展示数据 / 无文件上传 → `oneday-lite`
- 需要 TypeScript / Tailwind / 路由 → `oneday-standard`
- 需要文件处理（PDF/Excel）/ JWT 鉴权 / 自定义 API → `oneday-full`

---

## 文件目录

需要详细内容时，Read 对应文件：

| 子文件 | 内容 | 何时读取 |
|--------|------|---------|
| `dingtalk-integration/` | 把钉钉表格/文档数据接入 OneDay 项目（生成集成代码） | 需要读取钉钉数据到前端时 |
| `webcontainer.md` | webpack配置、Express启动、代理、externals、路由、常见问题速查表 | 项目跑不起来、白屏、API失败、发布后白屏 |
| `oneday-cloud.md` | SDK初始化（含容错）、CRUD、Storage、Realtime、Migration DDL、Cloud连接完整修复指南、OneDayCloudEnable替代 | 数据库连不上、RLS报错、SDK初始化失败 |
| `workflow.md` | 节点全景、系统变量、并行限制、异常处理、错误类型、调试功能、结构化输出 | 编排 Workflow/Chatflow、节点报错 |
| `agent-tools-auth.md` | Agent版本/模式/MCP、ODPS数据源、工具集成、钉钉、用户认证(JWKS/BUC) | Agent开发、ODPS查询、鉴权、工具接入 |
| `import-guide.md` | 从 Bolt/v0/Claude Code 等平台迁移：五层根因、自检命令、三种迁移路径 | 外部项目导入后白屏/加载失败 |
| `reference.md` | 平台限制速查表、废弃功能、云函数、管理协作、所有参考链接 | 查限制数值、废弃替代方案、参考链接 |

## 常见问题 → 对应文件

| 问题现象 | 读哪个文件 |
|---------|-----------|
| 预览空白 / 卡在90% / Cannot GET / 发布后白屏 | `webcontainer.md` |
| Cloud连不上 / Bearer undefined / RLS 403 / SDK undefined | `oneday-cloud.md` |
| 从其他AI平台导入后加载失败 | `import-guide.md` |
| Workflow节点报错 / 并行异常 / 结构化输出失败 | `workflow.md` |
| ODPS查询失败 / 鉴权报错 / 钉钉集成 | `agent-tools-auth.md` |
| 查限制数值 / 废弃功能替代 / 参考链接 | `reference.md` |
