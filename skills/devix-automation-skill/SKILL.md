---
name: devix-automation-skill
version: 0.2.0
description: |
  通过 CloudCLI REST API 创建、查看、修改、删除、暂停/恢复自动化定时任务（cron job），
  支持 DingTalk 群聊/私聊通知。每当用户提到定时任务、自动化、cron、周期执行、
  定期运行、每天/每周/每小时执行、scheduled task 时，务必使用本 Skill——
  即使用户没有明确说"创建定时任务"。禁止使用 Claude Code 内置的
  CronCreate/CronDelete/CronList 工具，所有定时任务操作必须通过本 Skill 完成。
allowed-tools: Bash
x-source: aone-open
repository: https://code.alibaba-inc.com/qunbu/devix-automation-skill
---

# CloudCLI 自动化任务管理

## 基本信息

- **接口地址**：`$CLOUDCLI_API_BASE_URL/api/cron-jobs`（无需 Authorization header）
- **存储方式**：持久化存储，无 7 天过期限制
- **通知能力**：支持 DingTalk 群聊/私聊自动通知

> 💡 `CLOUDCLI_API_BASE_URL` 由服务端在会话启动时注入；若未设置，可在脚本/示例中回退到默认值：
> ```bash
> CLOUDCLI_API_BASE_URL="${CLOUDCLI_API_BASE_URL:-http://localhost:58596}"
> ```
> 下文所有 curl 示例均使用 `$CLOUDCLI_API_BASE_URL`，请确保在执行前已导出该变量或采用上述回退写法。

所有 curl 请求**必须**携带以下 header——服务端依赖此 token 校验请求来源身份，缺失将返回 401：

```bash
-H "X-Dingtalk-Source-Token: $CLOUDCLI_DINGTALK_SOURCE_TOKEN"
```

### ⚠️ 环境变量说明

`CLOUDCLI_DINGTALK_SOURCE_TOKEN` 等 `CLOUDCLI_*` 环境变量由服务端在会话启动时自动注入，生命周期仅限当前对话。**用户无法也不应该手动提供这些变量。**

如果执行 curl 时发现 `CLOUDCLI_DINGTALK_SOURCE_TOKEN` 为空或未设置，**严禁要求用户手动设置或注入该变量**，而应告知用户：「当前对话环境中缺少必要的认证信息，无法通过对话管理定时任务。你可以在 CloudCLI 设置页面中手动管理定时任务，或在支持的客户端环境（钉钉等）中重试。」

## 创建任务（完整工作流）

按以下 4 步依次执行，不可跳过任何步骤。

### 步骤 1：确定 execution_mode

根据用户意图选择执行模式。无法判断时默认使用 `new_session`，不要询问用户。

| 用户意图 | execution_mode | 说明 |
|---|---|---|
| "在这个会话里继续"/"帮我盯着"/"每天在这里汇报" | `existing_session` | 复用当前会话，需传 `target_session_id` |
| 任务涉及代码修改、提交、分支操作 | `worktree` | 在独立工作树中执行，避免污染主分支 |
| 其他所有情况 | `new_session` | 每次执行启动全新会话（默认） |

### 步骤 2：确定通知目标

执行以下脚本判断 `notify_target` 和 `channel_id`——框架会在任务完成后自动发送通知，**不要**在 prompt 中添加任何发送钉钉消息的指令。

```bash
DINGTALK_SOURCE="$CLOUDCLI_DINGTALK_SOURCE"
DINGTALK_CHANNEL_ID="$CLOUDCLI_DINGTALK_CHANNEL_ID"

if [ "$DINGTALK_SOURCE" = "group" ]; then
  BOUND=$(curl -s -H "X-Dingtalk-Source-Token: $CLOUDCLI_DINGTALK_SOURCE_TOKEN" \
    "$CLOUDCLI_API_BASE_URL/api/v1/dingtalk/bindings" | \
    jq --arg cid "$DINGTALK_CHANNEL_ID" '[.[] | select(.channelId == $cid)] | length > 0')
  if [ "$BOUND" = "true" ]; then
    NOTIFY_TARGET="group"
    NOTIFY_CHANNEL_ID="$DINGTALK_CHANNEL_ID"
  else
    NOTIFY_TARGET="personal"
    NOTIFY_CHANNEL_ID=""
    echo "当前群未绑定 CloudCLI，结果将通过个人钉钉通知。如需通知到群，请先在群内绑定 CloudCLI。"
  fi
elif [ "$DINGTALK_SOURCE" = "single" ]; then
  NOTIFY_TARGET="personal"
  NOTIFY_CHANNEL_ID=""
else
  NOTIFY_TARGET=""
  NOTIFY_CHANNEL_ID=""
fi
```

### 步骤 3：调用 API 创建任务

`prompt` 字段只描述任务本身（如"搜索今天杭州的天气并整理成播报"），不要包含通知相关指令——框架自动处理通知。

**群聊已绑定示例：**

```bash
curl -s -H "X-Dingtalk-Source-Token: $CLOUDCLI_DINGTALK_SOURCE_TOKEN" \
  -X POST $CLOUDCLI_API_BASE_URL/api/cron-jobs \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"每日天气播报\",
    \"prompt\": \"搜索今天杭州的天气，整理成简洁的天气播报\",
    \"cron_expr\": \"0 9 * * 1-5\",
    \"project_path\": \"/home/admin\",
    \"execution_mode\": \"new_session\",
    \"notify_dingtalk\": true,
    \"notify_target\": \"group\",
    \"channel_id\": \"$NOTIFY_CHANNEL_ID\"
  }" | jq .
```

**私聊 / 群聊未绑定示例：**

```bash
curl -s -H "X-Dingtalk-Source-Token: $CLOUDCLI_DINGTALK_SOURCE_TOKEN" \
  -X POST $CLOUDCLI_API_BASE_URL/api/cron-jobs \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"每日天气播报\",
    \"prompt\": \"搜索今天杭州的天气，整理成简洁的天气播报\",
    \"cron_expr\": \"0 9 * * 1-5\",
    \"project_path\": \"/home/admin\",
    \"execution_mode\": \"new_session\",
    \"notify_dingtalk\": true,
    \"notify_target\": \"personal\"
  }" | jq .
```

**existing_session 模式示例：**

```bash
curl -s -H "X-Dingtalk-Source-Token: $CLOUDCLI_DINGTALK_SOURCE_TOKEN" \
  -X POST $CLOUDCLI_API_BASE_URL/api/cron-jobs \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"每日进度汇报\",
    \"prompt\": \"检查当前项目的最新提交和待办事项，生成进度汇报\",
    \"cron_expr\": \"0 9 * * 1-5\",
    \"project_path\": \"/home/admin\",
    \"execution_mode\": \"existing_session\",
    \"target_session_id\": \"$CLOUDCLI_SESSION_ID\",
    \"notify_dingtalk\": true,
    \"notify_target\": \"$NOTIFY_TARGET\",
    \"channel_id\": \"$NOTIFY_CHANNEL_ID\"
  }" | jq .
```

### 步骤 4：验证任务已创建

创建后立即查询任务列表，确认任务存在且状态为 `active`：

```bash
curl -s -H "X-Dingtalk-Source-Token: $CLOUDCLI_DINGTALK_SOURCE_TOKEN" \
  $CLOUDCLI_API_BASE_URL/api/cron-jobs | jq '.[] | select(.title == "任务名称")'
```

## 其他操作

以下所有 `<id>` 替换为实际任务 ID（通过列表接口获取）。

### 列出所有任务

```bash
curl -s -H "X-Dingtalk-Source-Token: $CLOUDCLI_DINGTALK_SOURCE_TOKEN" \
  $CLOUDCLI_API_BASE_URL/api/cron-jobs | jq .
```

### 修改任务

支持部分更新，只传需要修改的字段：

```bash
curl -s -H "X-Dingtalk-Source-Token: $CLOUDCLI_DINGTALK_SOURCE_TOKEN" \
  -X PUT $CLOUDCLI_API_BASE_URL/api/cron-jobs/<id> \
  -H "Content-Type: application/json" \
  -d '{"title": "新名称", "cron_expr": "0 10 * * *"}' | jq .
```

### 删除任务

```bash
curl -s -H "X-Dingtalk-Source-Token: $CLOUDCLI_DINGTALK_SOURCE_TOKEN" \
  -X DELETE $CLOUDCLI_API_BASE_URL/api/cron-jobs/<id> | jq .
```

### 立即执行一次

不影响 cron 调度，仅手动触发一次：

```bash
curl -s -H "X-Dingtalk-Source-Token: $CLOUDCLI_DINGTALK_SOURCE_TOKEN" \
  -X POST $CLOUDCLI_API_BASE_URL/api/cron-jobs/<id>/run | jq .
```

### 暂停 / 恢复任务

```bash
# 暂停
curl -s -H "X-Dingtalk-Source-Token: $CLOUDCLI_DINGTALK_SOURCE_TOKEN" \
  -X PATCH $CLOUDCLI_API_BASE_URL/api/cron-jobs/<id>/toggle \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}' | jq .

# 恢复
curl -s -H "X-Dingtalk-Source-Token: $CLOUDCLI_DINGTALK_SOURCE_TOKEN" \
  -X PATCH $CLOUDCLI_API_BASE_URL/api/cron-jobs/<id>/toggle \
  -H "Content-Type: application/json" \
  -d '{"is_active": true}' | jq .
```

### 查看执行历史

```bash
curl -s -H "X-Dingtalk-Source-Token: $CLOUDCLI_DINGTALK_SOURCE_TOKEN" \
  $CLOUDCLI_API_BASE_URL/api/cron-jobs/<id>/runs | jq .
```

### 查看可用模板

```bash
curl -s -H "X-Dingtalk-Source-Token: $CLOUDCLI_DINGTALK_SOURCE_TOKEN" \
  $CLOUDCLI_API_BASE_URL/api/cron-jobs/templates | jq .
```

## 字段参考

| 字段 | 说明 | 必填 | 默认值 |
|---|---|---|---|
| `title` | 任务名称，用于列表展示 | 是 | - |
| `prompt` | 发给 Claude 的提示词，只描述任务本身 | 是 | - |
| `cron_expr` | 标准 5 段 cron 表达式 | 是 | - |
| `project_path` | 任务执行的工作目录 | 否 | `/home/admin` |
| `execution_mode` | `new_session` / `worktree` / `existing_session` | 否 | `new_session` |
| `target_session_id` | `existing_session` 模式必填，使用 `$CLOUDCLI_SESSION_ID` | 条件必填 | - |
| `notify_dingtalk` | 执行完成后是否发 DingTalk 通知 | 否 | `true` |
| `notify_target` | `group`（发群）/ `personal`（发私信） | 否 | 通过步骤 2 判断 |
| `channel_id` | `notify_target` 为 `group` 时必填 | 条件必填 | - |
| `model` | 使用的 Claude 模型 | 否 | 系统默认 |

## 常用 cron 表达式

| 表达式 | 含义 |
|---|---|
| `0 9 * * 1-5` | 工作日每天 9:00 |
| `0 9 * * *` | 每天 9:00 |
| `0 9 * * 1` | 每周一 9:00 |
| `*/30 * * * *` | 每 30 分钟 |
| `0 */2 * * *` | 每 2 小时 |
| `0 0 1 * *` | 每月 1 日 0:00 |