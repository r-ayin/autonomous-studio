---
name: memory
version: 0.16.0
description: |
  面向 AI Agent 的跨平台持久个人记忆能力，用于让 Agent 主动检索和保存用户偏好、
  身份背景、项目上下文、历史决策、编码风格、沟通风格和工作流习惯。
  当用户提到“我/之前/上次/继续/以后/按我的习惯/这个项目”等上下文信号，
  或明确要求记住、保存、回忆、搜索、更新、删除记忆时，应使用个人记忆能力。
  默认通过本 Skill 自带的 scripts/user-memory 执行。
  当用户明确提供 spaceId，或请求团队、空间、协作、共享上下文相关记忆时，可使用 scripts/space-memory。
x-source: aone-open
repository: https://code.alibaba-inc.com/qunbu/memory
---

# Memory

本技能将记忆持久化到云端，以支持在不同场景、平台下共享记忆，提供对记忆的自动路由/定向写入、分层/范围检索与定向更新删除能力，让 AI Agent 在跨会话、跨设备、跨平台场景下持续复用用户偏好、决策记录与项目上下文。

这个 Skill 默认服务于**个人记忆**。空间记忆只是显式补充能力。

## 执行入口

通过本 Skill 自带的三个脚本执行记忆能力：

- `scripts/memory`：认证与配置。
- `scripts/user-memory`：个人记忆。
- `scripts/space-memory`：空间记忆。

文档中的 `scripts/...` 均指相对于当前 `SKILL.md` 所在目录的脚本，实际执行时解析为完整路径。

## 前置条件

首次使用或遇到鉴权失败时，执行 `scripts/memory auth` 确认当前身份有效。
如果没有权限，到 https://kbase.alibaba-inc.com/#/private-token 获取 Private Token 作为 authTicket。

## 优先规则

- 默认使用个人记忆：用户偏好、身份背景、个人项目上下文、编码风格、沟通习惯、工具习惯和长期个人决策。
- 空间记忆用于团队、空间、协作、共享上下文；涉及这类记忆检索时，可以主动使用 `scripts/space-memory ...`。
- 更新和删除前必须先在对应记忆域搜索，使用搜索结果里的记忆条目 `id`。

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
| 查看可用空间记忆 | `scripts/space-memory list` | 用户要求查看可用空间，或需要先确认 `spaceId` 时使用。 |
| 检索空间记忆 | `scripts/space-memory search "<spaceId>" "<query>"` | 用户给出 `spaceId` 时直接检索；未给但语境明显涉及团队/空间记忆时，先 `list` 再选择空间。 |
| 写入空间记忆 | `scripts/space-memory add "<spaceId>" "<content>"` | 操作意图、目标空间和内容明确时执行。 |
| 更新/删除空间记忆 | 搜索 -> `scripts/space-memory update/delete "<spaceId>" "<id>" ...` | 必须在同一 `spaceId` 下先检索到明确记忆 `id`。 |

## 个人记忆流程

1. 对依赖历史上下文的请求，先执行 `scripts/user-memory search`。
2. 将检索到的记忆自然融入回答或执行计划。
3. 保存时写入精炼、可复用的事实，不保存整段对话。
4. 如果用户是在纠正旧事实，先搜索并更新已有条目。
5. 写入、更新或删除后，简短告诉用户变更了什么。

## 空间记忆流程

1. 用户明确提供 `spaceId` 并要求读取空间记忆时，直接执行 `scripts/space-memory search` 或 `scripts/space-memory tree`。
2. 用户没有提供 `spaceId`，但问题明显涉及团队、空间、协作、共享上下文时，先执行 `scripts/space-memory list`，结合空间名称、描述和当前用户角色选择候选空间。
3. 如果只有一个明显相关空间，可以继续检索；如果多个空间都可能相关，先让用户选择。
4. 回答空间记忆检索结果时，说明结果来自哪个空间，避免和个人记忆混淆。
5. 空间记忆的写入、更新、删除以操作意图、目标空间和内容或记忆 `id` 是否明确为准；信息完整时可以直接执行。
6. 如果缺少 `spaceId`、空间名称不明确、或写入内容是 Agent 总结生成的，先让用户确认目标空间或内容。
7. 不因为 Agent 自己判断某条信息适合团队共享，就在目标空间或操作意图不明确时写入、更新或删除空间记忆。

## 命令速查

```bash
scripts/memory auth
scripts/user-memory tree
scripts/user-memory search <query> [memoriesPerNode] [totalLimit]
scripts/user-memory add <content> [--infer] [--target-path <path>]
scripts/user-memory update <id> <content>
scripts/user-memory delete <id>
```

## 空间记忆补充

当用户明确提供 `spaceId`，或请求团队、空间、协作、共享上下文相关记忆时使用：

```bash
scripts/space-memory list
scripts/space-memory tree <spaceId>
scripts/space-memory search <spaceId> <query> [memoriesPerNode] [totalLimit]
scripts/space-memory add <spaceId> <content> [--infer] [--target-path <path>]
scripts/space-memory update <spaceId> <id> <content>
scripts/space-memory delete <spaceId> <id>
```
