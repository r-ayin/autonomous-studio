# Phase 0: 断点恢复检查

启动后首先检查是否有已有进度。**必须同时查 SUCCESS 与 RUNNING 事件**，避免中断发生在某阶段完成后、下一阶段事件创建前时重复执行已完成阶段。

## Step 1: 建立已完成阶段列表

```bash
node scripts/list-events.js --task-id $TASK_ID --status SUCCESS
```

遍历返回的 SUCCESS 事件，按 event_type 标记哪些阶段已彻底完成（例如看到 `deploy_plan` SUCCESS 即 Phase 6 已完成）。

## Step 2: 查找中断点

```bash
node scripts/list-events.js --task-id $TASK_ID --status RUNNING
```

如果有 `status=RUNNING` 的事件，说明该阶段正在执行时被中断，从该阶段继续：

| RUNNING 事件的 event_type | 继续位置 |
|--------------------------|---------|
| pipeline_check           | Phase 2: 重新执行流水线状态检测 |
| build                    | Phase 4: 继续轮询构建状态 |
| pre_check                | Phase 5: 继续轮询准入状态 |
| deploy_batch             | Phase 7: 继续轮询当前批次状态 |

## Step 3: 决定恢复起点

- **有 RUNNING 事件** → 从该 RUNNING 事件对应阶段继续（Step 2 表）
- **无 RUNNING 但有 SUCCESS 事件** → 从"最后完成的 SUCCESS 阶段"的**下一个**阶段开始（跳过所有已完成阶段）
- **无任何事件** → 从 Phase 1 开始

> ⚠️ 旧版只查 RUNNING 的 bug：若中断发生在 Phase 6 (`deploy_plan` SUCCESS) 之后、Phase 7 (`deploy_batch` 创建) 之前，无 RUNNING 事件会导致从 Phase 1 重跑，重复创建 CR / 触发流水线。修复于 audit-2026-07-02-006 / M-003。