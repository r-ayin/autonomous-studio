# 部署常见问题排查

## 1. CR 状态不允许提交

### 症状

`a1 app cr submit` 报错，CR 不在 DEV 状态。

### 诊断

```bash
a1 app cr get <cr-id>
```

查看 CR 当前状态。

### 处理方案

| CR 状态 | 含义 | 处理 |
|---------|------|------|
| `DEV` | 开发中 | 正常，可直接提交 |
| `PREINTG` | 预集成 | 已提交过，需 `unsubmit` 后重新提交或直接继续 |
| `INTG` | 集成中 | 已在流水线中，需先 `quit` 退出当前流水线 |
| `CLOSED` | 已关闭 | 不可恢复，需创建新 CR |
| `TEST` | 测试中 | 需 `unsubmit` 回退到 DEV |

**回退 CR 状态**：
```bash
# 从 PREINTG/TEST 回退到 DEV
a1 app cr unsubmit <cr-id>
```

**从流水线中退出**：
```bash
# 从当前流水线中撤出 CR
a1 app cr quit <cr-id> --pipeline-id <pipeline-id> --app <app>
```

---

## 2. CR 已在其他流水线中

### 症状

`a1 app cr submit` 报错，提示 CR 已绑定到其他流水线。

### 诊断

```bash
a1 app cr get <cr-id>
```

查看 CR 是否关联了流水线实例。

### 处理方案

1. 通过 AskUserQuestion 确认是否从原流水线退出
2. 退出：
   ```bash
   a1 app cr quit <cr-id> --pipeline-id <原流水线ID> --app <app>
   ```
3. 重新提交到目标流水线：
   ```bash
   a1 app cr submit <cr-id> --pipeline-id=<目标pipeline-id> --app <app>
   ```

---

## 3. 流水线 WAITING 状态

### 症状

流水线或某个 stage 长时间处于 WAITING 状态。

### 诊断

```bash
# 查看哪个 stage 在 WAITING
a1 app pipeline stage list --pipeline-id=<pipeline-id> --app <app>

# 下钻到具体 stage
a1 app pipeline stage status --stage-id=<stage-id> --app <app>

# 查看 stage 下的 job 和 task
a1 app pipeline stage job list --stage-id=<stage-id> --app <app>
```

### 常见原因与处理

| 原因 | 特征 | 处理 |
|------|------|------|
| 准入审批未通过 | 准入检查 stage 的 WAITING | 提示用户在 Aone 平台完成审批 |
| 分批部署等待确认 | 部署 stage 的 task WAITING | AskUserQuestion 确认后 resume |
| 构建资源排队 | 构建 stage 的 WAITING | 耐心等待，无需操作 |
| 前置依赖未满足 | 某 stage WAITING 但前一个 stage 未完成 | 检查前序 stage 状态 |

---

## 4. 分批部署失败

### 症状

部署单的某个批次出现失败主机。

### 诊断

```bash
# 查看分批摘要
a1 app deploy-order batch list <deploy-order-id> --app <app>

# 查看失败批次的主机详情
a1 app deploy-order batch hosts <deploy-order-id> --batch-num=<失败批次> --app <app>
```

### 进一步诊断

```bash
# 查看启动诊断（若 task 支持）
a1 app pipeline stage job task status --task-id=<task-id> view-diagnosis

# 查看部署日志
a1 app pipeline stage job task status --task-id=<task-id> log
```

### 常见原因

| 原因 | 诊断线索 | 建议 |
|------|---------|------|
| 应用启动失败 | view-diagnosis 显示启动超时或异常 | 检查应用日志、端口冲突、资源不足 |
| 健康检查失败 | view-diagnosis 显示 health check failed | 检查健康检查接口是否正常 |
| 磁盘空间不足 | 主机详情显示部署失败 | 清理磁盘或扩容 |
| 镜像拉取失败 | log 中显示 image pull error | 检查镜像是否存在、网络是否通 |

---

## 5. pipeline run 无响应

### 症状

`a1 app pipeline run` 执行后没有触发新的流水线实例。

### 诊断

```bash
# 查看流水线当前实例状态
a1 app pipeline status --pipeline-id=<pipeline-id> --app <app>

# 列出历史实例
a1 app pipeline instance list --pipeline-id=<pipeline-id> --app <app>
```

### 常见原因与处理

| 原因 | 处理 |
|------|------|
| 流水线已有运行中实例 | 等待当前实例完成，或报告给用户 |
| 没有 CR 在 pending-publish 状态 | 确认 `cr submit` 是否成功执行 |
| 流水线配置问题 | 报告给用户，建议在 Aone 平台检查流水线配置 |

### 重试

```bash
# 使用 retry 重新触发
a1 app pipeline retry --pipeline-id=<pipeline-id> --app <app>
```

---

## 6. CLI 认证失败

### 症状

a1 命令返回 401 / 403 或提示认证过期。

### 处理

提示用户执行：
```bash
a1 auth login
```

重新认证后再次执行部署操作。

---

## 7. 部署后回滚

### 何时考虑回滚

- 部署完成后发现线上异常（监控告警、错误率上升等）
- 分批部署中发现早期批次有问题

### 回滚方式

回滚操作需要在 Aone 平台手动操作，a1 CLI 不直接支持回滚。Agent 应：

1. 停止继续推进分批部署（不再 resume）
2. 提示用户在 Aone 平台操作回滚
3. 可通过 `a1 app cr quit` 将 CR 退出流水线
4. 监控回滚后的应用状态

---

## 8. 查看部署单关联的 CR

当需要确认某个部署单包含了哪些 CR（变更）时：

```bash
a1 app deploy-order cr <deploy-order-id> --app <app>
```

这在多个 CR 同时提交到同一流水线时特别有用，可以确认部署内容是否符合预期。
