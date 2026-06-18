# uni-connect 领域说明

当用户明确在问统一接入、七层 Ingress、域名+路径维度的接入配置时，进入这个领域。

## 选命令规则

- 按应用名或域名查接入资源列表：`uni-connect list`
- 查单条接入资源完整配置：`uni-connect get`

## 什么时候优先 `uni-connect`

- 用户说"统一接入/接入记录/专线"
- 用户给的是域名 + 路径 + cluster-id，想查接入详情
- 用户想知道某个域名在哪个集群有接入配置

## 什么时候不要优先 `uni-connect`

- 用户在说"跨云通道/PVL/HTTP Proxy"，用 `cloud-link`
- 用户说"这个域名走的是哪条 VIP"，先用 `domain get`
- 用户只是想查域名基本信息，用 `domain`

## 进一步确认

- 需要最新参数时，运行 `normandy uni-connect --help` 或对应子命令 `--help`
