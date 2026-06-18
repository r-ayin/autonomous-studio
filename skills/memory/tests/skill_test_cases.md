# Memory skill — test cases

用于检验 Agent 是否按 `SKILL.md` 正确触发与执行；也可作人工验收清单。CLI 自动化见 `tests/run_tests.sh`。

---

## 1. 触发与不应触发

| ID | 输入 / 场景 | 期望 |
|----|-------------|------|
| T1.1 | 用户说「记住我们后端用 Go」 | 使用本 skill；直接 `user-memory add` |
| T1.2 | 用户说「我之前说过用什么数据库？搜一下记忆」 | `user-memory search`，用用户自然表述或略宽关键词 |
| T1.3 | 用户说「按我之前的编码风格改一下」 | 即使未提“记忆”，也先 `user-memory search "编码风格"` |
| T1.4 | 用户说「继续上次那个方案」 | 先 `user-memory search "上次 方案"`，再继续任务 |
| T1.5 | 用户说「这个项目以后都用 pnpm」 | 主动 `user-memory add` 保存项目工具习惯 |
| T1.6 | 用户说「我不喜欢太长的解释」 | 主动 `user-memory add` 保存沟通偏好 |
| T1.7 | 用户贴大段错误日志让排查 | 不原样写入日志；仅在用户明确要求时保存提炼后的结论 |
| T1.8 | 用户要存密码/API key/authTicket | 拒绝写入；提示安全原因 |
| T1.9 | 用户要求查看可用空间记忆或不知道 spaceId | 使用 `space-memory list` 查看有权限的空间 |
| T1.10 | 目标 spaceId 和写入内容明确，且语境是空间记忆写入 | 直接使用 `space-memory add <spaceId> ...`，不机械二次确认 |
| T1.11 | 用户要求搜索团队/空间/共享记忆但没给 spaceId | 先 `space-memory list` 查看候选空间 |

---

## 2. 检索策略

| ID | 用户问题 | 期望执行的思路 |
|----|----------|----------------|
| T2.1 | 「我是谁」 | 先 `user-memory search "我是谁"` 或 `"用户"`；不用抽象词堆砌 |
| T2.2 | 「我们用什么数据库」 | `user-memory search "数据库"` 等自然关键词 |
| T2.3 | 「搜一下团队空间里发布惯例」但没给 spaceId | 先 `space-memory list`，再根据空间名称/描述选择候选空间检索；候选不唯一时让用户选 |
| T2.4 | 首次检索无结果 | 尝试更宽关键词（skill 中示例策略） |

---

## 3. 写入流程（智能写入）

| ID | 用户原话 | 预检索策略（示例） | 期望分类与动作 |
|----|----------|------------------------|----------------|
| T3.1 | 「记住我们后端用 Java」 | 无需预检索 | 直接 `user-memory add "团队后端技术栈是 Java"` |
| T3.2 | 已有「后端 Python」，再说「后端改成 Java」 | `user-memory search "后端"` | 找到旧记忆后 `user-memory update <id> "..."` |
| T3.3 | 已有「后端 Python FastAPI」，再说「我们后端是 Python 加 FastAPI」 | 无需预检索 | 可直接 `user-memory add`，由后端处理路由与去重 |
| T3.4 | 已有「后端 Python」，再说「缓存用 Redis」 | 无需预检索 | 直接新增一条 `user-memory add` |
| T3.5 | Agent 想定向写入但不确定目录路径 | `user-memory tree` | 从真实目录结构中选择 `--target-path`，不要凭空猜路径 |
| T3.6 | 定向写入因目录/文件不存在失败 | 不继续猜路径 | 引导用户到 [管理平台](https://kbase.alibaba-inc.com/#/memory) 新建或调整目录/文件；非强指定目录时可改自动路由 |
| T3.7 | 「写到 spaceId=123：发布前必须完成灰度验证」 | 无需二次确认 | 直接 `space-memory add 123 "发布前必须完成灰度验证"` |
| T3.8 | Agent 从讨论中判断某结论适合团队共享，但目标空间或写入意图不明确 | 不自动写入 | 先确认目标空间或写入意图 |

---

## 4. 配置与错误处理（乐观执行）

| ID | 场景 | 期望 |
|----|------|------|
| T4.1 | 正常已配置 | 直接执行子命令，不先 `command -v memory` |
| T4.2 |  stderr 含 `command not found` | 引导安装（`install.sh` 或复制脚本） |
| T4.3 |  stderr 含 `Memory not configured` | 引导 `memory setup` 或 `KBase_AuthTicket` |
| T4.4 | 认证/API 失败 | 提示检查 ticket 与网络；不展示完整 ticket |

---

## 5. 管理操作

| ID | 场景 | 期望 |
|----|------|------|
| T5.1 | 更新某条 | 先 `user-memory search` 拿到 id → `user-memory update <id> "..."` |
| T5.2 | 删除指定记忆 | 先 `user-memory search` 拿到 id → `user-memory delete <id>` |
| T5.3 | 更新或删除空间记忆 | 在同一 `spaceId` 下先 `space-memory search` 拿到 id → 再 `space-memory update/delete <spaceId> <id> ...` |

---

## 6. 输出呈现

| ID | 场景 | 期望 |
|----|------|------|
| T6.1 | `user-memory search` 有结果 | 可读展示内容与相似度/相关性 |
| T6.2 | `user-memory search` 无结果 | 明确说明未找到相关记忆 |

---

## 7. CLI 脚本（与 skill 一致）

| ID | 命令 | 期望 |
|----|------|------|
| C7.1 | `memory help` | 列出 setup/auth，并提示 user-memory/space-memory |
| C7.2 | `user-memory help` | 列出 tree/search/add/update/delete |
| C7.3 | `space-memory help` | 列出 list/tree/search/add/update/delete |
| C7.4 | 无配置时 `user-memory search "x" 10` | 非零退出；提示未配置 |
| C7.5 | 无配置时 `user-memory tree` | 非零退出；提示未配置 |
| C7.6 | `memory tree` | 非零退出；提示未知命令 |
| C7.7 | `memory` 无参数 | 等价 help |

自动化覆盖 C7.x 中可在离线环境验证的部分：运行 `./tests/run_tests.sh`。
