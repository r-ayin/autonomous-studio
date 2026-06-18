# Phase 8: 完成

## 所有批次部署成功

最后一批观察期通过后，直接完成任务：

```bash
node scripts/complete-task.js --task-id $TASK_ID --success true --summary "全部 <N> 批部署完成"
```

## 中途失败

任何阶段失败时，直接完成任务：

```bash
node scripts/complete-task.js --task-id $TASK_ID --success false --summary "<失败描述>"
```

## 异常处理

- submit 报 CR 已在其他流水线 → `a1 app cr quit <cr-id> --pipeline-id <原id>` 后重新 submit
- pipeline run 无响应 → `a1 app pipeline retry --pipeline-id <id> --app <app>`
- 认证失败 → 提示 `a1 auth login --buc`
- 脚本调用失败 → 不阻塞部署流程，记录日志后继续
- 整体超时 → `node scripts/complete-task.js --task-id $TASK_ID --success false --summary "部署超时"`
