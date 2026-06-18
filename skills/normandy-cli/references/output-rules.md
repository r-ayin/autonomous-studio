# 输出规则

这个文件只在回答格式拿不准时读取；高频约束已内联到 `SKILL.md`。回答仍应短、稳、可复制。

## 标准输出模板

始终按这个结构回答：

```markdown
推荐命令：
`normandy ...`

说明：
- 一句话解释为什么选这个命令
- 点出 1-3 个关键参数
- 如果容易混淆，再补一句和相邻命令的区别

可直接复制的模板：
```bash
normandy ...
normandy ...
```
```

## 回答约束

- 默认只给一个最佳命令方向，不要把答案写成命令大全
- 模板数量控制在 1 到 3 条
- 不补造业务参数，缺什么就直接说缺什么
- 参数名、命令名保持 CLI 原文英文；解释文字跟随用户语言
- 如果用户明显是 AI/程序调用场景，且该命令支持 `--output`，模板优先带 `--output json`
- 不要默认补“先执行 `normandy auth login`”。只有在用户明确要登录、需要排查认证、或真实执行后收到认证失败信号时，才补认证说明；优先推荐 `normandy auth status --output json`，确认需要 OAuth 修复时再推荐 `normandy auth login`

## 缺参数时怎么说

用直接句式指出缺口，例如：

- 缺少应用名，需要先确认 `--app-name`
- 缺少资源标识，需要先确认 `--id` 或 `--sn`
- 缺少环境上下文，需要先确认 `--stack-id`、`--app-group` 或 `--location`

## JSON 输出参数

只在当前 skill 已明确列出 `--output`，或实时 `normandy ... --help` 明确提供 `--output` 选项时，才追加 `--output json`。不要对浏览器登录类命令（如 `auth login`、`host login`、`aliyun-sub-account login`）强行追加 JSON 参数。

如果命令支持结构化输出，统一使用 `--output json`，不要使用过时的 `--json`。

## 何时补充对比说明

只在这些情况补一小句对比：

- `app` / `app-group` / `host` 容易混淆
- `resource` / `aliyun-*` 容易混淆

对比说明不要超过两句。
