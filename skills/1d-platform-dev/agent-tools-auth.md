# Agent、工具集成、用户认证、ODPS

## 一、Agent 开发

### 版本演进

| 版本 | 关键能力 |
|------|---------|
| V0.1.0-V0.7.0 | 基于 Claude Code 架构，Task/Read/Edit/Write/Bash/Glob/Grep 工具 |
| V0.8.0 | Plan 模式（模糊需求先澄清、复杂功能先规划）、上下文窗口透出 |
| V0.9.0 | 历史项目导入远程沙盒、动态配置扩展工具（Memory/Preview/WebSearch/WebFetch/PTC） |
| **V1.0.0** | **Fast 模式（默认）**、模型切换、Plan 升级(SubAgent)、MCP 升级(aone market+中文特殊字符)、实时 steering/suggestion、Human-in-the-Loop |

### 模式说明

- **Fast 模式（默认）**：具备完整 Agent 能力，一次性交付完整解决方案，兼具 Bot 的精准快速。Bot 模式即将下线。
- **Plan 模式**：Agent 自行判断是否进入 `/plan`，也可主动触发。Explore+Plan 迁移到 SubAgent。
- **实时 Steering**：运行中实时插入指令队列干预，无需取消重来
- **实时 Suggestion**：基于项目上下文预测下一步 prompt
- **Human-in-the-Loop**：感知人工修改 diff

### 模型选择

**推荐组合：Agent 模式 + Claude Sonnet 4.5 + 清空上下文**（官方称可解决 90% "模型很笨" 的问题）

切换方式：鼠标移到对话记录出现「切换模型」；或输入 `/model`

可用模型：Claude 系列、Gemini 2.0 Flash/Pro、GPT-4o 系列、Qwen 系列、DeepSeek 系列

免费额度：Trial 分类下内置 Qwen 和 DeepSeek 部分模型免费次数，超限后需自行配置 API-KEY（走 ideaLab 或 whale 申请预算）

### MCP 工具

- Agent 可调用用户配置的 MCP 服务（Aone 知识平台查询语雀/钉钉文档等）
- V1.0.0 兼容中文+特殊字符工具名，接入 aone mcp market
- 支持 SSE 导入和 Streamable 导入
- 每个 MCP 工具支持细粒度开关
- 自行注册：`https://open.aone.alibaba-inc.com/mcp/register`
- 环境注意：预发环境只调 MCP 预发，线上 MCP 必须在线上环境操作

---

## 二、工具与集成

### 工具类型

| 工具 | 说明 |
|------|------|
| **内置工具** | HSF、ODPS、Hologres、SLS、钉钉、代码解释器、时间、情报通、Audio、网页抓取、OpenAI图像、MCP工具、Redis、数据库查询、图表生成、JSON处理 |
| **自定义工具** | OpenAPI/Swagger/OpenAI Plugin 规范导入，支持无鉴权和 API Key |
| **MCP工具** | Model Context Protocol 标准，SSE/Streamable 导入 |
| **HSF工具** | 阿里内部 HSF 服务调用 |

### 钉钉集成

| 功能 | 方式 |
|------|------|
| **钉钉机器人** | 官方 skill：`https://1d.alibaba-inc.com/skills/dingtalk-robot` |
| **钉钉AI助理** | 将工作流发布为钉钉 AI 助理 |
| **钉钉群消息** | 通过 webhook token + 加签密钥发送 |
| **事件触发器** | 钉钉事件（消息等）触发工作流 |

接入步骤：群设置→机器人→添加 aibot→获取工作空间 API Key→群内绑定 API Key（支持 Chatflow 和 Agent，用户消息通过 `sys.query` 获取）

### Webhook & 调度

- Chatflow 和 Workflow 类型可用 Webhook：工作流页面→调度→Webhook，支持 GET/POST，参数可透传
- 定时触发工作流执行，运行异常时可发送告警通知

### 接口描述智能补全

实验室选项→打开开关→授权添加应用。仅 owner/pe/appops 能添加授权。需为 `deepwiki_user` 添加代码库至少「读」权限。

---

## 三、ODPS 数据源集成

### 限制

- 仅支持 SELECT，不支持 INSERT/UPDATE/DELETE
- 超时限制：最多 **1.5 分钟**
- Token 默认有效期 48h，过期刷新页面自动获取

### 请求格式

```javascript
const response = await fetch('/api/cc/auth/query', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${(window.parent || window).ONEDAY_CONFIG?.authToken || ''}`,
  },
  body: JSON.stringify({
    sql: 'SELECT * FROM workspace.table_name LIMIT 10;',  // ⚠️ 必须以 ; 结尾
    odps_id: 12345,  // ⚠️ 必填！数据源记录 ID
  }),
});
```

### 关键规范

1. **SQL 必须以英文分号 `;` 结尾**，否则报错 `Query must ends with ';'`
2. **响应数据从 `result.data.data` 读取**（两层 data 嵌套），不能直接 `result.data`
3. **表名格式**：`{sqlWorkspace}.{tableName}`，启用 Holo 加速则用 Holo 表名

### 故障排查

| 症状 | 可能原因 | 解决 |
|------|---------|------|
| SQL 执行失败 | 未关联数据源 | 打开集成数据源工具检查 |
| 运行超时 | 查询超过 1.5min | 优化 SQL 或减小数据量 |
| Query must ends with ';' | SQL 未以分号结尾 | 加分号 |
| NO privilege 'odps:CreateInstance' | 无工作空间权限 | guard 申请权限 |
| Holo 加速后无数据 | Holo 兼容问题 | 删除表→关 Holo 加速→重新导入 |

---

## 四、用户认证

### 前端获取用户信息

```javascript
const user = (window.parent || window).ONEDAY_CONFIG?.user;
// 包含工号(workid)、花名(name)、头像(headImg)
// 优先从父窗口取，兼容 iframe 嵌入场景
```

### JWKS 鉴权（推荐）

```js
// 前端获取 Token
const token = ONEDAY_CONFIG?.jwtToken;
// 或
const res = await fetch("https://1d.alibaba-inc.com/api/jwt/token", { method: "POST" });
const { access_token } = await res.json();
// 返回: { access_token, refresh_token, token_type: "Bearer", expires_in: 604800 }

// 请求时携带
fetch("https://your-api.com/endpoint", {
  headers: { Authorization: `Bearer ${access_token}` }
});
```

**服务端验证参数：**
- JWKS 端点：`https://1d.alibaba-inc.com/.well-known/jwks.json`
- 算法：RS256 | Audience：`oneday-services` | Issuer：`https://1d.alibaba-inc.com`

**Token 中的用户信息：**
```json
{ "workid": "BJ1180", "name": "若影", "lastName": "杨若影",
  "headImg": "//work.alibaba-inc.com/photo/BJ1180.80x80.jpg",
  "referer": "https://pre-1d.alibaba-inc.com/?id=032OPyYU" }
```

**Python 验证：**
```python
from jwt import PyJWKClient, decode
def validate_token(token: str):
    jwks_client = PyJWKClient("https://1d.alibaba-inc.com/.well-known/jwks.json")
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    return decode(token, signing_key.key, algorithms=["RS256"],
                  audience="oneday-services", issuer="https://1d.alibaba-inc.com")
```

**Node.js 验证：**
```js
const { expressjwt: jwt } = require('express-jwt');
const jwksRsa = require('jwks-rsa');
app.use(jwt({
  secret: jwksRsa.expressJwtSecret({
    cache: true, rateLimit: true,
    jwksUri: 'https://1d.alibaba-inc.com/.well-known/jwks.json',
  }),
  algorithms: ['RS256'],
}));
```

**Token 刷新：**
```js
const res = await fetch("https://1d.alibaba-inc.com/api/jwt/token", {
  method: "POST",
  body: JSON.stringify({ refresh_token: oldRefreshToken })
});
const { access_token } = await res.json();
```

### BUC 免登（备选）

- 申请 onedaynode 到接口应用的免登
- 通过 `https://1d.alibaba-inc.com/api/v1/auth/ticket` 获取 sso_ticket
- BUC 登录失败常见原因：OneDay Cloud 开启后 FK 冲突（profiles 表和 users 表不同步），需联系平台排查

---

## 五、知识库（RAG 系统）

### 分段模式

| 模式 | 特点 | 限制 |
|------|------|------|
| **通用模式** | 按段落分隔，默认 500Tokens，最大 4000Tokens，建议重叠 10-25% | — |
| **父子模式**（推荐） | 父分段(段落/全文前10000Tokens)+子分段(句子/200Tokens)，精准+完整上下文 | 仅高质量索引 |
| **Q&A 模式** | Q to Q 策略，系统自动生成 Q&A 匹配对，消耗更多 LLM Tokens | 无法用经济型索引 |

### 检索设置

- **权重设置**（免费）— 语义值=1 纯语义，关键词值=1 纯关键词，可自定义比例
- **Rerank 模型**（付费）— Cohere/Jina AI，适合内容来源复杂/多语言场景
- **TopK**：值小→更少分段（可能不全），值大→更低相关度
- **多路召回合并**：所有关联知识库同时检索，合并后 Rerank

### 元数据系统

- 字段命名：仅小写字母、数字和下划线(`_`)，不支持空格和大写
- 值类型：String、Number、Time
- 内置元数据：`document_name`、`uploader`、`upload_date`、`last_update_date`、`source`（默认禁用）

### 外部知识库 API

```
POST <your-endpoint>/retrieval
Authorization: Bearer {API_KEY}
Body: { knowledge_id, query, retrieval_setting: {top_k, score_threshold}, metadata_condition? }
```

请求频率限制：**1000次/分钟**（每个工作区）。多路召回仅计一次。30天未使用自动禁用。
