# log 领域说明

当用户在问日志查询、SLS 日志、Pod 容器日志、查看日志内容、日志排障时，进入这个领域。

## 选命令规则

`log` 只有一个子命令 `list`，通过 `--source` 区分三种工作模式：

| 模式 | 触发条件 | 关键参数 |
|------|----------|----------|
| SLS 单源直查 | 指定 `--project` + `--logstore`（默认 `--source sls`） | `--project --logstore --query --from --to --size --offset --reverse` |
| Pod 单源直查 | 指定 `--source pod` + `--server` | `--server --path --lines --container` |
| 场景聚合 | 指定 `--scene <name>` | `--scene --source sls\|pod`（选择执行哪种源） |

## SLS 模式（默认）

直接查询单个 SLS Logstore 的日志内容：

```
normandy log list --project <project> --logstore <logstore> [OPTIONS]
```

参数说明：
- `--project` 必填：SLS Project 名称
- `--logstore` 必填：SLS Logstore 名称
- `--from`：起始时间（默认 15 分钟前），格式如 `"2026-04-01 10:00:00+0800"`
- `--to`：结束时间（默认当前时间）
- `--query`：查询/分析语句，如 `"error"`、`"status:500"`
- `--topic`：日志主题
- `--size`：返回条数（默认 10）
- `--offset`：起始行号（默认 0），用于分页
- `--reverse`：倒序排列（最新的在前）
- `--power-sql`：使用独立 SQL 模式

缺少 `--project` 时 CLI 会报错 `--project is required when --source=sls`。

## Pod 模式

直接读取 ASI Pod 容器内的日志文件，无需 SSH 登录主机或进容器：

```
normandy log list --source pod --server <ip|sn|hostname> [OPTIONS]
```

参数说明：
- `--server` 必填：服务器标识，可传 IP、SN 或 hostname
- `--path`：容器内日志文件路径（默认 `/home/admin`）
- `--container`：容器名称（默认 `main`）
- `--lines`：读取尾部行数（默认 10）

注意：Pod 模式不支持 `--size` / `--offset`（SLS 专用），用 `--lines` 控制日志长度。混用时 CLI 会给出提示。

## 场景聚合模式

通过 `--scene` 一次查询多个预配置的日志源：

```
normandy log list --scene <name> [--source sls|pod] [OPTIONS]
```

- 场景配置存放在 `~/.normandy/log.yaml`
- `--source sls`（默认）执行 `sources.sls` 部分，`--source pod` 执行 `sources.pod` 部分
- 场景中 `sls` 和 `pod` 两个 section 可以共存
- CLI 显式传入的参数会覆盖场景配置中的默认值

### 参数合并优先级

```
CLI 显式指定  >  配置文件中的默认值  >  硬编码默认值
```

### 场景配置文件格式

`~/.normandy/log.yaml` 示例：

```yaml
scenes:
  baas-center:                          # 场景名称
    sources:
      sls:                              # SLS 日志源
        - project: baas-center
          logstores:
            - baas-center-logstore      # 简写：直接写 logstore 名
            - name: resource-login      # 详写：可附加默认参数
              query: "operationType:LOGIN"
              size: 20
        - project: baas-center-operation
          logstores:
            - baas-center-change-order-operation
      pod:                              # Pod 日志源（可选）
        - server: "33.4.190.155"
          path: "/home/admin/app/logs/application.log"
          container: "main"             # 可选，默认 main
          lines: 20                     # 可选，默认 10
        - server: "33.5.100.237"
          path: "/home/admin/app/logs/application.log"
```

用户可以让 Agent 帮忙编辑 `~/.normandy/log.yaml` 来管理场景配置（添加源、创建新场景等）。操作配置文件时应：先读取现有配置保留已有内容、按 YAML 规范写入、操作后建议验证命令。

## 通用参数

- `--output text|json`：输出格式（默认 text）。AI/程序场景优先加 `--output json`
- `--verbose`：显示详细诊断信息（时间范围、凭证缓存、资源 SN、Endpoint 等）
- `--config PATH`：自定义配置文件路径（覆盖默认的 `~/.normandy/log.yaml`）

## 凭证管理

- SLS 模式凭证自动获取：CLI 自动通过 Normandy 平台查找 SLS Project 对应的资源 SN -> 获取 Region/Endpoint -> 申请 STS 临时凭证 -> 调用 aliyunlog CLI 执行查询
- 无需手工配置 AK/SK
- 凭证和资源元数据缓存在 `~/.normandy/sls_cache.yaml`（权限 0600）
- 连续查询同一 Project 几乎零延迟启动

## JSON 输出格式

### SLS 单源 JSON

直接返回日志条目数组。

### Pod 单源 JSON

```json
{
  "success": true,
  "data": {
    "content": "日志内容..."
  }
}
```

### 场景聚合 JSON

```json
{
  "scene": "场景名",
  "results": [
    {
      "source": "sls",
      "success": true,
      "data": [...],
      "project": "project-name",
      "logstore": "logstore-name"
    }
  ]
}
```

每个 `results` 条目独立标记 `success` 状态，部分源失败不影响其他源结果返回。

## 错误处理

| 错误场景 | CLI 提示 | 建议操作 |
|---------|---------|---------|
| 缺少 `--project` | `--project is required when --source=sls` | 补充 `--project` 参数 |
| Project 不存在 | `SLS project 'xxx' not found` | 确认 Project 名称存在 |
| 场景不存在 | `Scene 'xxx' not found. Available scenes: ...` | 使用提示中的可用场景名 |
| JSON 模式错误 | 返回结构化 `{code, message, action}` | Agent 可据此自动决策 |

退出码：`0` 成功，`1` 查询失败或所有源均失败。

## 什么时候用 `log list`

- 用户说"查日志"、"看日志"、"SLS 日志"、"Pod 日志"、"容器日志"、"错误日志"
- 用户要查某个 SLS Project / Logstore 的日志内容
- 用户要读容器内日志文件
- 用户要按场景聚合查多个日志源

## 什么时候不用 `log list`

- 查 SLS Project / Logstore 的**资源元信息**（如 region、配置）→ `aliyun-sls-project` / `aliyun-sls-logstore`
- 看容器内**文件/目录列表**（不是读内容）→ `host path`
- 只知道应用名，不知道 Project/Logstore → 先用 `aliyun-sls-project list --app-name` 和 `aliyun-sls-logstore list --app-name` 查找
- 只知道应用名，不知道机器 → 先用 `host list --app-group` 查找机器

## 典型排障链路

### SLS 链路

```
aliyun-sls-project list --app-name <app> → 找到 Project
  → aliyun-sls-logstore list --app-name <app> → 找到 Logstore
    → log list --project <proj> --logstore <ls> --query "error" --output json → 查日志
```

### Pod 链路

```
host list --app-group <app.group> → 找到机器
  → host path --server <ip> --path /home/admin/logs → 找到日志文件
    → log list --source pod --server <ip> --path <file> --lines 50 → 读日志
```

## 前置依赖

- SLS 模式需要安装 `aliyunlog` CLI：`uv tool install aliyun-log-cli` 或 `pip install -U aliyun-log-cli`
- Pod 模式不需要额外安装

## 进一步确认

- 需要最新参数时，运行 `normandy log list --help`
