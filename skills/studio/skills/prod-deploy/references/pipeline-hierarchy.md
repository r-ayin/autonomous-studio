# 流水线层级结构与监控参考

## 1. 层级关系

```
Pipeline Instance (流水线实例)
└── Stage (阶段)          — 如：构建、准入检查、部署
    └── Job (作业)        — 阶段内的具体作业
        └── Task (任务)   — 作业内的最小执行单元
            └── Deploy Order (部署单)   — 部署类 task 关联的部署单
                └── Batch (批次)        — 分批部署的每个批次
                    └── Host (主机)     — 批次中的每台主机
```

## 2. 每层 CLI 命令速查

### Pipeline Instance

| 操作 | 命令 |
|------|------|
| 查看状态 | `a1 app pipeline status --pipeline-id=<id> --app <app>` |
| 触发执行 | `a1 app pipeline run --pipeline-id=<id> --app <app>` |
| 等待完成 | `a1 app pipeline status --pipeline-id=<id> --wait-until-settled --app <app>` |
| 重新执行 | `a1 app pipeline retry --pipeline-id=<id> --app <app>` |
| 列出历史实例 | `a1 app pipeline instance list --pipeline-id=<id> --app <app>` |

### Stage

| 操作 | 命令 |
|------|------|
| 列出全部 stage | `a1 app pipeline stage list --pipeline-id=<id> --app <app>` |
| 查看特定 stage | `a1 app pipeline stage status --stage-id=<id> --app <app>` |

### Job

| 操作 | 命令 |
|------|------|
| 列出 stage 下 job | `a1 app pipeline stage job list --stage-id=<id> --app <app>` |
| 查看 job 状态 | `a1 app pipeline stage job status --job-id=<id> --app <app>` |

### Task

| 操作 | 命令 |
|------|------|
| 列出 job 下 task | `a1 app pipeline stage job task list --job-inst-id=<id> --app <app>` |
| 查看 task 状态 | `a1 app pipeline stage job task status --task-id=<id>` |
| 执行 task action | `a1 app pipeline stage job task status --task-id=<id> <action> [key=value ...]` |

### Deploy Order

| 操作 | 命令 |
|------|------|
| 按流水线列出 | `a1 app deploy-order list --pipeline-id=<id> --app <app>` |
| 查看详情 | `a1 app deploy-order get <deploy-order-id> --app <app>` |
| 列出关联 CR | `a1 app deploy-order cr <deploy-order-id> --app <app>` |

### Batch

| 操作 | 命令 |
|------|------|
| 列出分批摘要 | `a1 app deploy-order batch list <deploy-order-id> --app <app>` |
| 查看批次主机 | `a1 app deploy-order batch hosts <deploy-order-id> --batch-num=<n> --app <app>` |

## 3. 状态枚举与终态判断

### 流水线/Stage/Job 通用状态

| 状态 | 是否终态 | 含义 |
|------|---------|------|
| `SUCCESS` | ✅ 终态 | 执行成功 |
| `FAIL` / `FAILED` | ✅ 终态 | 执行失败 |
| `SKIPPED` | ✅ 终态 | 被跳过 |
| `WAITING` | ❌ 非终态 | 等待中（准入审批/分批确认/人工操作） |
| `RUNNING` | ❌ 非终态 | 正在执行 |
| `PENDING` | ❌ 非终态 | 排队等待开始 |
| `INIT` | ❌ 非终态 | 初始化中 |

### 终态判断逻辑

```
is_terminal(status) = status in ["SUCCESS", "FAIL", "FAILED", "SKIPPED"]
```

### WAITING 状态的细分

WAITING 可能出现在不同环节，含义不同：

| 出现位置 | 常见原因 | Agent 行为 |
|---------|---------|-----------|
| 准入检查 Stage | 等待人工审批 | 提示用户在 Aone 平台操作，持续轮询 |
| 部署 Stage 的 Task | 分批部署等待确认 | AskUserQuestion 确认后 resume |
| 构建 Stage | 排队等待构建资源 | 持续轮询，向用户说明在排队 |

## 4. Task Supported Actions 详解

`a1 app pipeline stage job task status --task-id=<id>` 的输出中包含一个 **Supported Actions** 列表。只有列表中出现的 action 才能执行。

### deploy-order-list

列出 task 关联的部署单。

```bash
a1 app pipeline stage job task status --task-id=<task-id> deploy-order-list
```

返回部署单 ID 列表，用于后续查询分批详情。

### submit-deploy

提交发布单。构建和准入通过后，部署阶段的 task 进入 WAITING 状态，当 Supported Actions 出现 `submit-deploy` 时才可以提交发布单，触发第一批部署。

```bash
a1 app pipeline stage job task status --task-id=<task-id> submit-deploy deploy-id-list=<deploy-order-id>
```

参数说明：
- `deploy-id-list`：要提交的部署单 ID，从 `deploy-order-list` action 获取

> ⚠️ **必须确认 Supported Actions 中包含 `submit-deploy` 后才能执行。**

### resume

恢复暂停的 task 执行。**用途**：分批部署中确认继续下一批。

```bash
a1 app pipeline stage job task status --task-id=<task-id> resume deploy-id-list=<deploy-order-id>
```

参数说明：
- `deploy-id-list`：要恢复的部署单 ID，从 `deploy-order-list` action 获取

> ⚠️ **必须通过 `resume_next_batch` MCP 工具推进，该工具强制校验观察期。**

### view-diagnosis

查看部署失败时的启动诊断信息。

```bash
a1 app pipeline stage job task status --task-id=<task-id> view-diagnosis
```

包含应用启动日志、健康检查结果等诊断数据。在部署失败时优先使用此 action 收集诊断信息。

### log

查看 task 的执行日志。

```bash
a1 app pipeline stage job task status --task-id=<task-id> log
```

用于排查构建失败、测试失败等非部署类 task 的错误原因。

## 5. 监控下钻流程

标准监控下钻路径：

```
1. pipeline status → 获取整体状态
   │
   ├── 终态 → 结束监控
   │
   └── 非终态 → 继续
       │
       2. stage list → 找到当前活跃 stage
          │
          3. job list → 找到 stage 下活跃 job
             │
             4. task list → 找到 job 下的 task
                │
                5. task status → 查看 task 状态和 Supported Actions
                   │
                   ├── 有 deploy-order-list action
                   │   → 获取部署单 → batch list → 监控分批
                   │
                   ├── WAITING + submit-deploy action 可用
                   │   → 提交发布单（submit-deploy）
                   │
                   ├── WAITING + resume action 可用
                   │   → resume_next_batch MCP → 推进下一批
                   │
                   └── FAIL
                       → view-diagnosis / log → 收集诊断
```

## 6. 轮询间隔建议

| 场景 | 建议间隔 |
|------|---------|
| 等待构建完成 | 10 秒 |
| 等待准入审批 | 10 秒 |
| 分批部署中 | 20 秒 |
| 等待用户操作后（resume 后） | 20 秒 |
