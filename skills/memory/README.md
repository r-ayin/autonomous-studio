# Memory Skill

本技能将记忆持久化到云端，以支持在不同场景、平台下共享记忆，提供对记忆的自动路由/定向写入、分层/范围检索与定向更新删除能力，让 AI Agent 在跨会话、跨设备、跨平台场景下持续复用用户偏好、决策记录与项目上下文。

默认服务于个人记忆。只有当用户明确指定 `workspaceId` 并要求操作协作空间记忆时，才使用协作空间能力。

## 执行入口

通过本 Skill 自带的三个脚本执行记忆能力：

- `scripts/memory`：认证与配置。
- `scripts/user-memory`：个人记忆。
- `scripts/space-memory`：协作空间记忆。

## 认证

首次使用或遇到鉴权失败时，执行：

```bash
scripts/memory auth
```

如果没有权限，到 https://kbase.alibaba-inc.com/#/private-token 获取 Private Token 作为 authTicket。

## 记忆管理

管理记忆可以访问：https://devix.alibaba-inc.com/devix/memory

## 常用命令

```bash
scripts/memory auth
scripts/user-memory tree
scripts/user-memory search <query> [memoriesPerNode] [totalLimit]
scripts/user-memory add <content> [--infer] [--target-path <path>]
scripts/user-memory update <id> <content>
scripts/user-memory delete <id>
```

## 协作空间命令

仅当用户明确指定 `workspaceId` 并要求操作协作空间记忆时使用：

```bash
scripts/space-memory tree <workspaceId>
scripts/space-memory search <workspaceId> <query> [memoriesPerNode] [totalLimit]
scripts/space-memory add <workspaceId> <content> [--infer] [--target-path <path>]
scripts/space-memory update <workspaceId> <id> <content>
scripts/space-memory delete <workspaceId> <id>
```

## Agent 使用要点

- 回忆个人上下文时，优先使用用户原话或自然关键词执行 `scripts/user-memory search`。
- 保存个人长期上下文时，直接执行 `scripts/user-memory add`，由后端负责路由和去重。
- 定向写入但路径不确定时，先执行 `scripts/user-memory tree`。
- 更新和删除前必须先搜索，使用搜索结果里的记忆条目 `id`。
- 不保存密码、API Key、authTicket、访问令牌等敏感信息。
