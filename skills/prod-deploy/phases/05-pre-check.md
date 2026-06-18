# Phase 5: 发布准入（Pre-Check）

构建通过后，pipeline 进入 pre-check stage。

## 步骤 1：上报准入开始

```bash
node scripts/report-event.js --task-id $TASK_ID pre_check \
  --pipeline-id "<pipeline-id>"
```

## 步骤 2：轮询准入状态

轮询脚本单次运行后返回结果，Claude 每 5 秒循环调用直到 `done=true`。

脚本会自动：
1. 通过 stage→job→task 三级下钻定位"发布准入"task-id 并缓存
2. 调用 `a1 app pipeline stage job task status` 提取 checkInsts
3. 映射状态后更新 deploy_event payload（check_items）
4. 终态时置 `done=true`

**状态映射**：PASS/PASS_WITH_LOW_RISK → SUCCESS，FAIL → FAILED，RUNNING/CHECKING → RUNNING，未开始 → INIT

每次循环执行：

```bash
node scripts/poll-pre-check.js --task-id $TASK_ID --pipeline-id <pipeline-id> --app-name <app>
```

脚本返回 JSON：

```json
{ "done": true/false, "status": "running|completed|failed", "payload": { ... } }
```

- `done == false` → 等待 5s 后再次调用
- `done == true, status == "completed"` → 准入通过，进入 Phase 6
- `done == true, status == "failed"` → 准入失败

## 准入失败

```bash
node scripts/complete-task.js --task-id $TASK_ID --success false --summary "准入失败: <失败项>"
```
