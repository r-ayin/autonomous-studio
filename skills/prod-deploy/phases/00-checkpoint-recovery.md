# Phase 0: 断点恢复检查

启动后首先检查是否有已有进度：

```bash
node scripts/list-events.js --task-id $TASK_ID --status RUNNING
```

如果有 `status=RUNNING` 的事件，说明是从中断恢复，根据最后事件的 event_type 决定从哪一步继续：

| 最后 RUNNING 事件的 event_type | 继续位置 |
|-------------------------------|---------|
| pipeline_check | Phase 2: 重新执行流水线状态检测 |
| build | Phase 4: 继续轮询构建状态 |
| pre_check | Phase 5: 继续轮询准入状态 |
| deploy_batch | Phase 7: 继续轮询当前批次状态 |

如果没有 RUNNING 事件，从 Phase 1 开始。