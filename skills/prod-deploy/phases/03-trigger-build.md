# Phase 3: 提交流水线 + 构建事件

```bash
# 1. CR 入队（不会自动执行）
a1 app cr submit <cr-id> --pipeline-id <pipeline-id> --app <app>

# 2. 触发流水线执行
a1 app pipeline run --pipeline-id <pipeline-id> --app <app>
```

两步缺一不可。触发后立即上报构建开始：

```bash
node scripts/report-event.js --task-id $TASK_ID build \
  --pipeline-id "<pipeline-id>" \
  --cr-id "<cr-id>"
```
