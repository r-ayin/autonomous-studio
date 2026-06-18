# 执行前校验与错误恢复

只有在用户明确要执行命令，或需要本机真实查询结果时，才读这个文档。只返回模板时不需要。

## 执行前校验

- 检查 `uv` 命令是否可用；如果当前会话或任务链里已经确认可用，就不要重复检查；不可用需要安装。
- 先检查 `normandy` 是否可用；如果当前会话或任务链里已经确认可用，就不要重复检查。
- 如果 `normandy` 不可用，优先建议或执行安装：
  ```bash
  uv tool install --index-url http://artlab.alibaba-inc.com/1/pypi/simple normandy-cli
  ```
- 如果要执行 `normandy log list --source sls`（SLS 日志查询），还需要检查 `aliyunlog` 是否可用（Pod 模式不需要）。如果不可用，安装：
  ```bash
  uv tool install aliyun-log-cli
  ```
  或：
  ```bash
  pip install -U aliyun-log-cli
  ```
- 不要把“先执行 `normandy auth login`”当成所有非 `auth` 命令的固定前置步骤。当前 CLI 的默认认证路径是 AIT/APT，很多业务命令可以直接执行。
- 对需要真实执行的业务命令，优先直接执行主命令；只有用户明确要求先检查认证，或你需要定位认证问题时，才先跑：
  ```bash
  normandy auth status --output json
  ```
- 如果主命令失败并出现 `AUTH_FAILED`、`Not authenticated`、`Run 'normandy auth login'`、`Run \`normandy auth login\`` 或等价信号，再进入认证恢复流程。
- 认证恢复时优先看 `normandy auth status --output json` 的双通道结果：
  - `ait.available=true`：通常不需要先登录，优先重试一次原业务命令，或把上游错误直接返回给用户。
  - `ait.available=false` 但 OAuth 已登录：说明 CLI 应该能回退到 OAuth，优先重试一次原业务命令，或把当前错误返回给用户排查。
  - `ait.available=false` 且 OAuth 未登录/已过期：再建议或执行 `normandy auth login`。
- 非交互环境、CI、Agent 启动阶段如果用户明确要求“预热登录态”或“提前准备 OAuth”，可以直接执行：
  ```bash
  normandy auth login
  ```

## 执行后错误恢复

只有在执行型请求中，主命令已经真实运行且失败时，才进入这里。

- 如果失败原因是认证缺失，按上面的认证恢复流程处理。只有在确认需要 OAuth 修复时，才执行 `normandy auth login`，然后重试原命令一次。
- 如果报错里明确出现 `reason: Please upgrade CLI to v... and retry`，并且同时给出了可执行的 `action`，优先执行这个 `action` 做升级。
- 升级成功后，只重试原命令一次。
- 当前会话或任务链里，针对同一条主命令最多自动做一次"升级并重试"，避免死循环。
- 如果 `action` 缺失、不像升级动作、升级失败，或重试后仍失败，就直接把错误返回给用户，不继续自动重试。
