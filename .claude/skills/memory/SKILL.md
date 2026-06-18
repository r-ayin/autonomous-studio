---
name: memory
version: 0.13.0
description: |
  面向 AI Agent 的跨平台持久个人记忆能力，用于让 Agent 主动检索和保存用户偏好、
  身份背景、项目上下文、历史决策、编码风格、沟通风格和工作流习惯。
  当用户提到“我/之前/上次/继续/以后/按我的习惯/这个项目”等上下文信号，
  或明确要求记住、保存、回忆、搜索、更新、删除记忆时，应使用个人记忆能力。
  默认通过本 Skill 自带的 scripts/user-memory 执行。
  仅当用户明确指定 workspaceId 并要求操作协作空间记忆时，才使用 scripts/space-memory。
---

# Memory

本技能将记忆持久化到云端，以支持在不同场景、平台下共享记忆，提供对记忆的自动路由/定向写入、分层/范围检索与定向更新删除能力，让 AI Agent 在跨会话、跨设备、跨平台场景下持续复用用户偏好、决策记录与项目上下文。

这个 Skill 默认服务于**个人记忆**。协作空间记忆只是显式补充能力。

## 执行入口

通过本 Skill 自带的三个脚本执行记忆能力：

- `scripts/memory`：认证与配置。
- `scripts/user-memory`：个人记忆。
- `scripts/space-memory`：协作空间记忆。

文档中的 `scripts/...` 均指相对于当前 `SKILL.md` 所在目录的脚本，实际执行时解析为完整路径。

## 前置条件

首次使用或遇到鉴权失败时，执行 `scripts/memory auth` 确认当前身份有效。
如果没有权限，到 https://kbase.alibaba-inc.com/#/private-token 获取 Private Token 作为 authTicket。

## 优先规则

- 默认使用个人记忆：用户偏好、身份背景、个人项目上下文、编码风格、沟通习惯、工具习惯和长期个人决策。
- 只有当用户明确指定 `workspaceId` 并要求操作协作空间记忆时，才使用 `scripts/space-memory ...`。
- 更新和删除前必须先搜索，使用搜索结果里的记忆条目 `id`。

## 触发场景

- 用户要求记住、保存、存储、别忘了、以后都、以后按这个。
- 用户要求回忆、搜索记忆、我之前说过什么、上次、继续、按我的习惯。
- 用户要更新、修改、纠正、删除或忘掉某条记忆。
- 任务依赖用户偏好、身份背景、当前项目、历史决策、编码风格或工作流习惯。

## 操作路由

| 用户意图 | 使用命令 | 说明 |
| --- | --- | --- |
| 回忆个人上下文 | `scripts/user-memory search "<query>" 3` | 优先使用用户原话或自然关键词。 |
| 保存个人长期上下文 | `scripts/user-memory add "<content>"` | 普通新增不需要先搜索，后端负责路由和去重。 |
| 保存个人上下文到已知路径 | `scripts/user-memory add "<content>" --target-path "<path>"` | 路径不确定时先执行 `scripts/user-memory tree`。 |
| 从长内容中抽取事实再保存 | `scripts/user-memory add "<content>" --infer` | 适合会议纪要或混合上下文。 |
| 更新个人记忆 | 搜索 -> `scripts/user-memory update "<id>" "<content>"` | 用户纠正旧事实时优先更新。 |
| 删除个人记忆 | 搜索 -> `scripts/user-memory delete "<id>"` | 删除目标不明确时先确认。 |

## 个人记忆流程

1. 对依赖历史上下文的请求，先执行 `scripts/user-memory search`。
2. 将检索到的记忆自然融入回答或执行计划。
3. 保存时写入精炼、可复用的事实，不保存整段对话。
4. 如果用户是在纠正旧事实，先搜索并更新已有条目。
5. 写入、更新或删除后，简短告诉用户变更了什么。

## 命令速查

```bash
scripts/memory auth
scripts/user-memory tree
scripts/user-memory search <query> [memoriesPerNode] [totalLimit]
scripts/user-memory add <content> [--infer] [--target-path <path>]
scripts/user-memory update <id> <content>
scripts/user-memory delete <id>
```

## 协作空间补充

仅当用户明确指定 `workspaceId` 并要求操作协作空间记忆时使用：

```bash
scripts/space-memory tree <workspaceId>
scripts/space-memory search <workspaceId> <query> [memoriesPerNode] [totalLimit]
scripts/space-memory add <workspaceId> <content> [--infer] [--target-path <path>]
scripts/space-memory update <workspaceId> <id> <content>
scripts/space-memory delete <workspaceId> <id>
```
