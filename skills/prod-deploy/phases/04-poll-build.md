# Phase 4: 轮询构建阶段

轮询脚本单次运行后返回结果，Claude 每 5 秒循环调用直到 `done=true`。

## 轮询循环

每次循环执行：

```bash
node scripts/poll-build.js --task-id $TASK_ID --pipeline-id <pipeline-id> --app-name <app>
```

脚本返回 JSON：

```json
{ "done": true/false, "status": "running|completed|failed", "payload": { ... } }
```

- `done == false` → 等待 5s 后再次调用
- `done == true, status == "completed"` → 构建成功，进入 Phase 5
- `done == true, status == "failed"` → 构建失败，获取 `payload.error_message`

## 构建失败

```bash
node scripts/complete-task.js --task-id $TASK_ID --success false --summary "构建失败: <原因>"
```
