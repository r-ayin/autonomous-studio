# cloud-link 领域说明

当用户明确在问跨云通道、PVL、HTTP网关时，进入这个领域。

## 选命令规则

- 查某个应用的所有跨云通道：`cloud-link list`
- 查单条通道详情（已知 Link ID）：`cloud-link get`

## 什么时候优先 `cloud-link`

- 用户说"应用的跨云链路"
- 用户手里有 `createOrderId`（即 Link ID），想查通道详情
- 用户在问 PVL 或 HTTP Proxy 类型的跨云通道

## 什么时候不要优先 `cloud-link`

- 用户在说"统一接入/专线/Ingress/域名+路径"，用 `uni-connect`
- 用户只是想查应用或分组，用 `app` / `app-group`

## 进一步确认

- 需要最新参数时，运行 `normandy cloud-link --help` 或对应子命令 `--help`
