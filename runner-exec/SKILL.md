repository: https://code.alibaba-inc.com/qunbu/runner-exec
---
name: runner-exec
description: Runner Exec — 在 Windows Runner 上执行命令和读写文件。当用户需要在连接的 Windows runner 上执行命令、读写文件时使用。
version: 1.0.3
files:
  - SKILL.md
  - scripts/
---

# Runner Exec — 在 Windows Runner 上执行命令和读写文件

当用户需要在连接的 Windows runner 上执行命令、读写文件时，使用此技能。

## 推荐工作流: pull → 本地编辑 → push

**远程读写 ~2s/次，本地读写 ~1ms/次，差 2000 倍。** 批量操作务必用同步模式：

```bash
SKILL=~/.claude/skills/runner-exec/scripts
WIN='C:\Users\石云鹏\.claude\skills\workflow-consultant'

# 1. 拉取到本地（一个连接读所有文件，~100ms/文件）
node $SKILL/pull.js "$WIN" ./mirror

# 2. 本地用 Read/Edit/Write 正常编辑（极快）

# 3. 推送变更回 Windows（只推送有改动的文件）
node $SKILL/push.js ./mirror "$WIN"
```

### pull.js 行为
- 单个持久 WebSocket 连接，复用同一个 PowerShell 进程
- 自动递归扫描目录，只拉取文本文件（.md .js .json .yaml 等）
- 每个文件用内容标记提取干净内容，剥离 ANSI 转义和终端噪音
- 生成 `.pull-manifest.json`（文件哈希表），供 push 做增量比较

### push.js 行为
- 对比 `.pull-manifest.json` 与当前文件哈希，只推送有变更的文件
- 单个持久连接批量写入，一个 PowerShell 进程完成所有文件
- 写入后更新 manifest

## 单条命令执行

不需要同步目录时，直接执行：

```bash
node $SKILL/exec.js 'Get-ChildItem C:\Users'
node $SKILL/write-file.js 'C:\path\file.txt' '内容'
node $SKILL/batch-write.js manifest.json
```

## 凭据自动发现

所有脚本自动获取凭据，无需手动填写：

| 凭据 | 来源 |
|------|------|
| Internal Secret | `~/.aone-cloud-cli/internal-rpc-secret` 或服务端进程环境 |
| Runner ID | `list-runners` API 自动发现 |
| Session Token | `~/.aone-cloud-cli/auth.db` SQLite 最新 token |

## 使用约束

- **认证**: WebSocket URL `?token=` 参数，不是 Authorization header
- **Shell**: 必须用 `powershell.exe`，不能用 `/bin/sh`
- **cwd**: init 消息不传 cwd，让 runner 用默认路径
- **语言模式**: Constrained Language Mode — 只能用核心 cmdlet（Set-Content、Get-Content、New-Item、Copy-Item），不能调用 .NET 方法
- **PS 转义**: 双引号中 `` ` → `` ``、`$ → `$`、`" → `"`、换行 → `n`

## 错误速查

| 错误 | 修复 |
|------|------|
| 401 Unauthorized | 脚本自动获取最新 token，若仍失败检查 runner 是否在线 |
| spawn /bin/sh ENOENT | 用 runner-shell WebSocket，不用 shell.exec API |
| path not under allowed root | 不传 cwd |
| Constrained Language Mode | 只用 PowerShell 核心 cmdlet |
| timeout | 拆分命令或加大 timeout 参数 |
