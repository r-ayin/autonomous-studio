# Phase 2: 流水线状态检测

在提交流水线之前，先检查当前流水线是否有其他任务占用。

## 步骤

### 1. 上报检测开始

```bash
node scripts/report-event.js --task-id $TASK_ID pipeline_check \
  --pipeline-id "<pipeline-id>" \
  --app-name "<app>"
```

### 2. 查询流水线状态

```bash
a1 app pipeline status --pipeline-id=<pipeline-id> --app <app>
```

解析文本输出，提取流水线实例的运行状态。

### 3. 判断结果

| 流水线状态 | 结果 | 动作 |
|-----------|------|------|
| 无实例 / SUCCESS / FAILED / SKIPPED | 空闲 | 继续 Phase 3 |
| RUNNING / PENDING / WAITING / INIT | 被占用 | 终止流程 |

### 4. 上报检测结果

**空闲（可继续）：**

```bash
node scripts/report-event.js --task-id $TASK_ID pipeline_check \
  --pipeline-id "<pipeline-id>" \
  --app-name "<app>" \
  --status "SUCCESS" \
  --pipeline-status "<实际状态>"
```

→ 继续 Phase 3。

**被占用（终止）：**

```bash
node scripts/report-event.js --task-id $TASK_ID pipeline_check \
  --pipeline-id "<pipeline-id>" \
  --app-name "<app>" \
  --status "FAILED" \
  --pipeline-status "<实际状态>" \
  --error-message "流水线被其他任务占用，当前状态: <实际状态>"
```

→ 调用 `complete-task.js` 终止流程：

```bash
node scripts/complete-task.js --task-id $TASK_ID --success false --summary "流水线被其他任务占用"
```
