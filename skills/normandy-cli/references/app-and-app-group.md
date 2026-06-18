# app 与 app-group 领域说明

当用户需求围绕应用概况查询或应用分组查询时，进入这个领域。

## 先分对象

- 对象是"应用"本身：`app`
- 对象是"应用分组"这一层：`app-group`

## `app`

适用于：

- 查应用概况：`app get`
- 查应用资源汇总：`app summary`

进一步确认参数时，运行 `normandy app --help` 或对应子命令 `--help`。

## `app-group`

适用于：

- 查应用分组详情：`app-group get`
- 查应用分组列表：`app-group list`

进一步确认参数时，运行 `normandy app-group --help` 或对应子命令 `--help`。

## 常见分流提示

- 用户说"某个分组下的机器"，通常不是 `app-group get`，而是进一步走 `host list`
- 用户说"我要按应用维度看资源概况"，优先 `app summary`
- 用户要"发起重启/置换/扩容等变更"，不要根据旧实现细节推荐未公开命令；当前 skill 只覆盖公开 CLI 命令面，应提示这类动作不在当前推荐范围内

## 相关补充

- 如果问题其实在查环境信息，再看 `references/env-order-quota-resource.md`
- 如果问题已经落到具体机器，再看 `references/host.md`
