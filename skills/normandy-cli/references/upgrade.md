# upgrade 领域说明

当用户明确在问如何升级 Normandy CLI 本身，而不是查询业务资源时，进入这个领域。

## 选命令规则

- 升级当前安装的 CLI：`normandy upgrade`

## 什么时候优先 `upgrade`

- 用户说“升级 normandy-cli”
- 用户说“更新到最新版本”
- 用户问“怎么从仓库或索引升级 CLI”

## 什么时候不要优先 `upgrade`

- 用户在问业务资源查询、登录、工单、主机、配额等操作
- 用户在问平台版本或应用版本，而不是 CLI 自身版本

## 进一步确认

- 需要最新参数时，运行 `normandy upgrade --help`
