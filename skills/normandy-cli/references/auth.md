# auth 领域说明

当用户目标是认证、登录状态、退出登录、OAuth fallback、手工修复登录态时，进入这个领域。

## 进入条件

- 登录 Normandy CLI
- 排查 AIT / OAuth 双通道认证状态
- 在非交互环境预先准备 OAuth 登录态
- AIT 不可用时走 OAuth fallback
- 刷新现有认证
- 查询当前是否已登录
- 登出或清理本地认证信息

## 选命令规则

- 查询状态：`normandy auth status`
- 登录或刷新令牌：`normandy auth login`
- 登出：`normandy auth logout`

## 语义约束

- `normandy auth status` 是认证排查的首选入口，应优先用于查看 AIT 与 OAuth 双通道状态。
- `normandy auth login` 不是所有业务命令的固定前置步骤；它主要用于 OAuth fallback、非交互环境预热、或手工修复认证。
- 如果用户只是问业务命令怎么写，不要把主体答案写成 `auth`，也不要默认要求先登录。

## 常见提醒

- 如果后续是 AI 或程序继续消费结果，优先提示 `--output json`
- 需要排查认证时，优先推荐：
  ```bash
  normandy auth status --output json
  ```
- 只有在 `AIT` 不可用且 `OAuth` 缺失/过期，或者用户明确要求手工登录时，才推荐：
  ```bash
  normandy auth login
  ```

## 进一步确认

- 需要最新参数或输出选项时，运行 `normandy auth --help` 或对应子命令 `--help`
