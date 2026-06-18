# 平台限制、云函数、管理协作、参考资源

## 平台配置限制速查

| 项目 | 限制值 |
|------|--------|
| 知识库查询最大字符数 | 200 字符 |
| 文件上传最大数量 | 10 个 |
| 单个文件大小上限 | 15MB |
| 数据库 API 请求体 | 最大 30MB（Nginx 限制） |
| 并行分支上限 | 10 个 |
| 嵌套并行最大层数 | 3 层 |
| 迭代并行最大轮数 | 10 轮 |
| 错误重试最大次数 | 10 次 |
| 错误重试最大间隔 | 5000ms |
| 代码嵌套最大层数 | 5 层 |
| HTTP 响应大小限制 | 10MB |
| 知识库请求频率 | 1,000 次/分钟 |
| 分段最大长度 | 4000 Tokens |
| 父分段全文最大 | 10000 Tokens |
| 开始节点文本最大长度 | 256 字符 |
| 列表操作取前 N 项 | 1-20 |
| 多模型调试最大并发 | 4 个模型 |
| ODPS 查询超时 | 1.5 分钟 |
| ODPS Token 有效期 | 48 小时 |
| JWT Token 有效期 | 7 天 |
| HTML 导入（托管） | 50MB |
| HTML 导入（迭代） | 10MB |

## 云函数（全栈应用）

### 核心要求

- 后端代码在 `/server` 目录，前端在根目录
- 后端服务必须启动在 **9000 端口**
- 必须先打开实验室功能 → Studio 模式 → 云函数开关
- **全栈应用只能在 WebC（浏览器沙盒）模式运行**，远程沙盒不支持（fc.baseUrl 为空）

### 前端获取 baseUrl

```javascript
let ONEDAY_CONFIG = {};
try {
  ONEDAY_CONFIG = (window.parent || window).ONEDAY_CONFIG || {};
} catch (e) {
  ONEDAY_CONFIG = window.ONEDAY_CONFIG || {};
}
const baseUrl = ONEDAY_CONFIG?.fc?.baseUrl || '';
const token = ONEDAY_CONFIG?.jwtToken?.access_token || '';
const apiUrl = `${baseUrl}/api/tasks`;
```

### 常见问题

| 症状 | 根因 | 解决 |
|------|------|------|
| `grpc_Response_fcCode_is_not_200` | 端口号不是 9000 | 改为 9000 |
| 后端逻辑没生效 | 部署失败自动回滚 | 查看部署日志 |
| 网络请求失败 | 在远程沙盒模式下运行 | 切换到 WebC（浏览器沙盒） |
| 不支持 WebSocket | 平台限制 | HTTP 上行 + SSE 下行替代 |

## 管理与协作

| 功能 | 说明 |
|------|------|
| **多分支** | 新功能独立分支开发，仅支持以主分支为基准创建，冲突处理跳转 Aone 平台（云函数暂不支持） |
| **版本管理** | 左上角「版本」Tab 查看/切换历史版本 |
| **项目转交** | 仅 owner 本人操作：工作台→项目右侧「...」→转交项目。账号注销则联系管理员后台处理 |
| **域名配置** | 自定义四级子域名，全局唯一，先释放再配置 |
| **数据看板** | 项目页面右上角查看访问用户信息 |
| **用户数据取回** | 用户本人申请，邮件给 OneDay 平台侧（抄送业务/技术负责人）→ 流通中心离线表视图分离 |

## 废弃/下线功能

| 功能 | 状态 | 替代方案 |
|------|------|---------|
| **OneDay Task** | 即将下线 | 合并到 Agent Skills |
| **旧版数据库（共享资源）** | 不再维护 | 迁移到 OneDay Cloud |
| **内网应用发布到外网** | 已下线 | 商业化版本 Meoo |
| **Bot 模式** | 即将下线 | Fast 模式（默认） |
| **Cloudflare 接入** | 不支持 | 改用 buc 服务 |
| **sys.files（Workflow）** | LEGACY | Chatflow 推荐自定义文件变量 |

## 参考资源

### 平台入口
- 1d 平台：`https://1d.alibaba-inc.com/`
- 预发环境：`https://pre-1d.alibaba-inc.com/`
- Workflow 线上：`https://1d.alibaba-inc.com/workflow/apps`
- Workflow 预发：`https://pre-1d.alibaba-inc.com/workflow/apps`

### 认证与 API
- JWKS 端点：`https://1d.alibaba-inc.com/.well-known/jwks.json`
- JWT Token：`https://1d.alibaba-inc.com/api/jwt/token`
- BUC 免登：`https://1d.alibaba-inc.com/api/v1/auth/ticket`
- HSF 代理工具：`https://1d.alibaba-inc.com/apps/035YNQiY`
- IDEALAB API：`https://aistudio.alibaba-inc.com/api/aiapp/run/{appCode}/{appVersion}`
- 星链 API：`https://s-link.alibaba-inc.com/next.html#/management/api-keys/list`

### 开发参考
- MCP 注册：`https://open.aone.alibaba-inc.com/mcp/register`
- ODPS 权限申请：`https://guard.alibaba-inc.com/mark/mark.htm#/projectApply/projectAuthApply`
- 钉钉机器人 Skill：`https://1d.alibaba-inc.com/skills/dingtalk-robot`
- 升级 OneDay Cloud Skill：`https://1d.alibaba-inc.com/skills/upgrade-oneday-cloud`
- 产品使用文档空间：`https://alidocs.dingtalk.com/i/spaces/nbX9JD4dr9MKOGyA/overview`

### 联系与支持
- Workflow 答疑群（钉钉）：**107850016644**
- BUC/FK 问题群（钉钉）：**176010005082**
- 工具答疑：@冯昶(识肆)
