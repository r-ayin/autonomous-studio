# vip / vip-rs 领域说明

当用户明确在问 VIP 资源、VIP 健康状态、VIP 下挂载的 Real Server 时，进入这个领域。

## 选命令规则

- 查某个应用有哪些 VIP：`vip list`
- 查单个 VIP 完整配置：`vip get`
- 查 VIP 下挂载的所有 RS 及健康状态：`vip-rs list`

## 什么时候优先 `vip` / `vip-rs`

- 用户给的是 IP、端口、协议，想查 VIP 详情
- 用户想知道某个应用有哪些 VIP
- 用户说"VIP 下有哪些后端服务器"

## 什么时候不要优先 `vip`

- 用户只是想查域名配置，用 `domain`
- 用户在说"统一接入/专线/Ingress"，用 `uni-connect`
- 用户在说"跨云通道/PVL/HTTP Proxy"，用 `cloud-link`

## 进一步确认

- 需要最新参数时，运行 `normandy vip --help`、`normandy vip get --help` 或 `normandy vip-rs list --help`
