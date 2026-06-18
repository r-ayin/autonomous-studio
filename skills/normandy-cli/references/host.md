# host 领域说明

当用户明确在问机器、主机、节点、主机 SN、hostname，或要对主机做登录操作时，进入这个领域。

## 选命令规则

- 查单台主机详情：`host get`
- 查主机对应 Pod 的原始 YAML：`host get --yaml`
- 查主机列表：`host list`
- 登录主机：`host login`
- 浏览容器内文件/目录：`host path`
- 暂停/恢复 Pod：`host pause` / `host resume`

## 什么时候优先 `host`

- 用户说"某个 app-group 下有哪些机器"
- 用户给的是 SN、hostname、IP
- 用户想登录某台主机
- 用户想看 Pod 的原始 YAML
- 用户想看容器里某个目录下有哪些文件
- 用户想临时暂停或恢复某个 Pod 的执行

## 什么时候不要优先 `host`

- 用户只是在看应用概况，用 `app`
- 用户只是看应用分组详情，用 `app-group`
- 用户只是想搜某个资源实例，不一定是主机，用 `resource`

## 容器文件浏览 `host path`

浏览 ASI 容器内指定目录的文件和子目录列表：

- `normandy host path --server <ip|sn|hostname> [--path /home/admin] [--container main]`

参数说明：
- `--server` 必填：服务器标识，可传 IP、SN 或 hostname
- `--path`：容器内目录路径，默认 `/home/admin`
- `--container`：容器名，默认 `main`
- `--layer`：目录深度，默认 `2`

### 什么时候用 `host path`

- 用户说"看看容器里有哪些文件"、"列出目录"、"查看日志目录结构"
- 用户想确认某个路径下有什么文件再决定查看具体日志

### `host path` vs `log list --source pod`

- `host path` 列出目录内容（文件名和类型），不读文件内容
- `log list --source pod` 读取具体日志文件的内容（tail 尾部 N 行）
- 典型流程：先用 `host path` 找到日志文件路径，再用 `log list --source pod` 读内容

## Pod YAML 查询 `host get --yaml`

查询主机当前对应 Pod 的原始 YAML：

- `normandy host get --host <ip|sn|hostname> --yaml`

参数说明：
- `--host` 必填：服务器标识，可传 IP、SN 或 hostname
- `--yaml`：输出 Pod 原始 YAML
- `--verbose`：输出详细诊断信息

注意事项：
- `--yaml` 不能和 `--output json` 同时使用
- 这里返回的是 Pod YAML，不是目录列表，也不是日志内容

### 什么时候用 `host get --yaml`

- 用户说"看这个 Pod 的 yaml"、"导出 Pod yaml"、"查部署 yaml"
- 用户已经拿到一台机器/SN/hostname，想反查该机器对应工作负载的原始 Pod 配置

### `host get --yaml` vs `host path` vs `log list --source pod`

- `host get --yaml` 返回 Pod 原始 YAML
- `host path` 列出容器目录结构，不返回 YAML
- `log list --source pod` 读取日志文件内容，不返回 YAML

## Pod 暂停/恢复 `host pause` / `host resume`

通过 Normandy ASI proxy 打开或关闭 Pod debug delay 模式：

- 暂停：`normandy host pause --server <sn|hostname|ip> [--timeout-minutes 30] [--container main]`
- 恢复：`normandy host resume --server <sn|hostname|ip> [--container main]`

参数说明：
- `--server` 必填：服务器标识，可传 SN、hostname 或 IP，推荐优先使用 SN 或 hostname。后端会用它做应用权限校验，并在未传 `--pod-name` 时解析目标 Pod
- `--timeout-minutes`：暂停时长，默认 30 分钟，必须大于 0
- `--container`：容器名，默认 `main`；如果用户指定 `--container test`，pause 前检查的是 YAML 中 `test` 容器的状态，不再固定检查 `main`
- `--pod-name`：可选，仅用于显式覆盖目标 Pod；不要只传 `--pod-name`，因为权限校验仍需要 `--server`
- `--output json`：返回接口原始 JSON

状态检查：
- `host pause` 会先通过 `host get --yaml` 同源接口获取 Pod YAML，并检查 `status.containerStatuses[]` 中目标容器的 `ready` 字段
- 只有目标容器 `ready` 不是 `true` 时才会继续执行 pause；如果目标容器已经 ready，会拒绝暂停
- 默认目标容器是 `main`；显式传 `--container <name>` 时，以用户指定的容器为准

权限说明：
- 当前登录用户必须是目标应用的 owner、appops、PE，或目标应用分组的 PE
- 如果返回权限拒绝，先确认 `--server` 是否能反查到正确应用/分组，再确认当前用户是否在上述角色中
- 这些命令是变更类操作，不要建议绕过权限或只传 `--pod-name`

### 什么时候用 `host pause`

- 用户说"暂停这个 Pod"、"让这个 Pod 先停住"、"开启 pod debug delay"
- 用户明确给了主机 IP/SN/hostname，并要求暂停一段时间
- 未指定暂停时长时使用默认 30 分钟；需要更短/更长时再显式加 `--timeout-minutes <minutes>`

### 什么时候用 `host resume`

- 用户说"恢复这个 Pod"、"取消 Pod 暂停"、"关闭 pod debug delay"
- 用户已经完成调试，需要把容器恢复运行

## 诊断命令 `host diagnose`

`host diagnose` 是一个子命令组，包含 `list` 和 `get` 两个子命令。

### `host diagnose list` — 查诊断事件列表

查询目标主机或 Pod 的异常诊断事件，支持两种 scope：

- **HOST scope**（默认）：`normandy host diagnose list --host <ip|sn|hostname>`
  - `--host` 必填，可传 IP、SN 或 hostname
  - `--type host|pod` 可选，强制指定 node 或 pod 诊断；省略时自动推断
  - `--pod-name` 在 HOST scope 下不可用
- **GPU scope**：`normandy host diagnose list --scope GPU --pod-name <pod-name>` 或 `--host <ip|sn|hostname>`
  - 必须且只能传 `--pod-name` 或 `--host` 其中一个
  - 优先用 `--pod-name` 直接定位工作负载；`--host` 会推断 podName/nodeSn
  - `--type` 在 GPU scope 下不可用

通用参数：
- `--start-time` / `--end-time`：毫秒时间戳，省略默认最近 24 小时
- `--page` / `--limit`：分页，默认第 1 页、每页 20 条
- `--output json`：JSON 输出
- `--verbose`：详细日志

### `host diagnose get` — 查单条诊断详情

查看一条 HOST 或 GPU 诊断的详细结果：

- `normandy host diagnose get --diagnose-id <id> --type HOST`
- `normandy host diagnose get --diagnose-id <id> --type GPU [--dimension top-kernel,critical-path]`

参数说明：
- `--diagnose-id` 必填：值来自 `host diagnose list` 返回结果中的 taskId（HOST 类型）或 profileId（GPU 类型）。用户没有 diagnose-id 时，应先引导用 `list` 查询获取
- `--type HOST|GPU` 必填
- `--dimension`：GPU 专用，支持 `default`、`top-kernel`、`critical-path`，可逗号分隔多选；`default` 始终包含
- HOST 类型的 dimension 固定为 `default`

### 什么时候用 `host diagnose`

- 用户说"查机器异常"、"诊断事件"、"机器告警"、"GPU 诊断"、"pod 诊断"
- 用户给了 diagnose-id 或 taskId/profileId 要看详情
- 用户提到 "AWP profiling"、"GPU profiling"

### 什么时候不用 `host diagnose`

- 只查机器基本信息，用 `host get`
- 只查机器列表，用 `host list`
- 只登录机器，用 `host login`

## 进一步确认

- 需要最新参数时，运行 `normandy host --help` 或对应子命令 `--help`
