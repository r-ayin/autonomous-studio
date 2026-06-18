# Workflow 工作流系统详解

## 核心概念

- **Chatflow vs Workflow**：Chatflow 面向对话（有 Memory、流式输出、直接回复节点）；Workflow 面向批处理（无 Memory、有结束节点）
- **变量**：四种类型：系统变量(`sys.*`) / 自定义变量（开始节点定义） / 环境变量（只读，敏感信息） / 会话变量（仅 Chatflow，可读写）

## 系统变量

| 变量 | 适用 | 说明 |
|------|------|------|
| `sys.user_id` | 全部 | 当前用户 ID |
| `sys.app_id` | 全部 | 当前应用 ID |
| `sys.workflow_id` | 全部 | 当前工作流 ID |
| `sys.workflow_run_id` | 全部 | 当前运行 ID |
| `sys.query` | Chatflow | 用户输入内容 |
| `sys.conversation_id` | Chatflow | 会话 ID |
| `sys.dialogue_count` | Chatflow | 对话轮数（可与 IF/ELSE 配合） |
| `sys.files` | 全部[LEGACY] | 上传文件数组（Chatflow 推荐用自定义文件变量） |

## 节点全景

### 流程控制

| 节点 | 功能 | 关键限制 |
|------|------|---------|
| **开始** | 工作流入口，定义输入变量 | 字段类型：文本(最大256)、段落、下拉选项、数字、文件 |
| **结束** | Workflow 出口（非 Chatflow） | 多分支需多个结束节点 |
| **条件分支** | IF/ELIF/ELSE 六路径 | 8种条件：包含/不包含/开始是/结束是/是/不是/为空/不为空，支持 AND/OR |
| **循环** | 轮次间有依赖的优化型任务 | 循环终止条件 + 最大循环次数 + 循环变量 |
| **迭代** | 轮次间无依赖的批处理 | 输入 Array，输出 Array[List]，内置 `items[object]` 和 `index[number]` |
| **直接回复** | Chatflow 专属，定义回复格式 | 支持流式输出，可作中间步骤节点 |

### AI 核心

| 节点 | 功能 | 关键配置 |
|------|------|---------|
| **LLM** | 大模型推理 | 温度/TopP/存在惩罚/频率惩罚，3套预设(创意/平衡/精确)，Jinja-2 模板，`/` 键呼出变量菜单 |
| **知识检索** | RAG 检索 | 查询最大 200 字符，输出 `result` 需配到 LLM「上下文变量」，元数据过滤支持 AND/OR |
| **问题分类器** | 自动分类路由 | 输出 `class_name`，支持视觉(图片)+记忆+文件变量 |
| **参数提取器** | 文本→结构化参数 | FC/Tool Call 或 Prompt 模式，内置 `__is_success` 和 `__reason` 变量 |

### 数据处理

| 节点 | 功能 | 关键限制 |
|------|------|---------|
| **代码执行** | Python3/NodeJS 沙箱 | 禁止文件系统/网络/OS 命令，Cloudflare WAF 拦截，嵌套最大 5 层 |
| **模板转换** | Jinja2 模板引擎 | 拼接文本、渲染 HTML 表单（`<form data-format="json">`） |
| **文档提取器** | 文档→文本 | 仅 TXT/MD/PDF/HTML/DOCX，不支持图片/音视频 |
| **列表操作** | 过滤/排序/取前 N 项 | 输入仅 Array[string/number/file]，取前 N 项范围 1-20 |
| **变量聚合器** | 多路分支变量聚合 | **只能聚合同一数据类型**，支持分组 |
| **变量赋值** | 写入会话变量/循环变量 | 覆盖/清空/设置/追加/扩展/移除，Number 支持加减乘除 |

### 外部集成

| 节点 | 功能 | 关键配置 |
|------|------|---------|
| **HTTP请求** | 调用外部 API | GET/POST/PUT/PATCH/DELETE/HEAD，响应最大 10MB，动态变量插入 |
| **工具** | 内置/自定义/MCP/HSF 工具 | 错误重试最大 10 次 / 5000ms 间隔 |
| **Agent** | FC 或 ReAct 策略 | 需授权+描述，支持记忆窗口、Jinja 指令 |

## 并行与编排限制

| 项目 | 限制值 |
|------|--------|
| 并行分支上限 | 10 个 |
| 嵌套并行最大层数 | 3 层 |
| 迭代并行最大轮数 | 10 轮（超出则前 10 个先执行） |
| 迭代内不建议放置 | 直接回答、变量赋值、工具节点（开启并行后可能异常） |

## 异常处理

三种预定义逻辑（仅 LLM/HTTP/代码执行/工具节点可用）：
1. **无**（默认）— 直接报错中断
2. **默认值** — 预定义替代值，流程继续
3. **异常分支** — 橙色线条高亮，执行预编排下游节点

优先级：同时开启错误重试和异常处理时，先重试后异常处理。

工作流状态：`Success` / `Failed`（流程中断）/ `Partial success`（节点异常但启用处理，最终正常）

## 错误类型速查

**代码执行节点：** `CodeNodeError`（代码逻辑异常，显示行号）、`DepthLimitError`（嵌套超5层）、`OutputValidationError`（输出类型不一致）

**LLM节点：** `VariableNotFoundError`（变量不存在）、`InvalidContextStructureError`（**上下文仅支持 String**）、`ModelNotExistError`（未选模型）、`LLMModeRequiredError`（未配 API Key）、`NoPromptFoundError`（提示词为空）

**HTTP节点：** `AuthorizationConfigError`（未配认证）、`ResponseSizeError`（响应超10MB）、`HTTPResponseCodeError`（非2xx状态码）

**工具节点：** `ToolNodeError`（工具执行异常）、`ToolParameterError`（参数异常）

## 调试功能

| 功能 | 说明 |
|------|------|
| **预览与运行** | Chatflow 点「预览」，Workflow 点「运行」，右侧调试 |
| **单步调试** | 逐节点执行，查看输入/输出 |
| **运行日志** | 详情（总览）+ 追踪（各节点输入输出/Token/耗时） |
| **部分运行** | 指定开始/结束节点（结束/直接回复/条件分支/变量聚合等不可作开始） |
| **检查清单** | 发布前自检未完成的配置/未连线节点 |

## 结构化输出

- JSON Schema 编辑器：可视化+代码编辑双模式，支持 AI 生成、嵌套对象/数组
- 原生支持 JSON Schema 的模型：Gemini 2.0 Flash/Pro、GPT-4o 系列、o1-mini/o3-mini 系列
- 不支持的模型以提示词方式输入 Schema，解析不确定
- 70B 以下模型指令遵循性弱，建议配置失败重试（最大10次/5000ms）+ 异常分支
