# Phase 7: 分批部署轮询

每批部署开始时上报事件，完成时更新状态。先确定总批次数：

```bash
a1 app deploy-order batch list <deploy-order-id> --app <app>
```

## 第 N 批开始

```bash
node scripts/report-event.js --task-id $TASK_ID deploy_batch \
  --deploy-order-id "<deploy-order-id>" \
  --batch-index N \
  --batch-total <总批次> \
  --group "<分组名>" \
  --instances <机器数>
```

## 轮询批次状态

间隔 20 秒：

```bash
# 查看各批次状态
a1 app deploy-order batch list <deploy-order-id> --app <app>

# 查看某批次主机详情
a1 app deploy-order batch hosts <deploy-order-id> --batch-num <n> --app <app>
```

**每次轮询完成后，无论结果如何，都保存当前批次状态数据：**

```bash
node scripts/report-event.js --task-id $TASK_ID deploy_batch \
  --deploy-order-id "<deploy-order-id>" \
  --batch-index N \
  --payload '{"batch_status":"<当前批次状态>","success_count":<成功数>,"total_count":<总数>,"hosts":[<主机列表摘要>],"poll_time":"<当前时间>"}'
```

## 每批观察期

**每批**部署完成后，**必须通过脚本 `resume-next-batch.js` 推进下一批**。
该脚本会读取第 1 批事件中的 `resolved_strategy.observe_minutes` 作为观察时长，
强制校验最近一批成功后的观察期是否已满，并检查 Sunfire 观测结果，未满或存在 HIGH 级异常则拒绝推进。

流程：
1. 确认当前批次成功率 100%（`deploy-order batch list` 的 success == total）
2. 更新当前批次事件状态为 SUCCESS
3. 进入观察期，**间隔 60 秒**执行以下操作：
   a. 调用 `report-observation.js` 查询 Sunfire 观测数据并写入事件 payload
   b. 检查返回的 `conclusion` 字段判断是否有异常
   c. 调用 `resume-next-batch.js` 尝试推进（会同时校验时间和观测结果）
4. 观察期内 Sunfire 检测到 HIGH 级别异常 → `resume-next-batch.js` 会拒绝推进，报告异常规则
5. 观察期满且无 HIGH 异常 → `resume-next-batch.js` 返回 approved: true，执行推进

### 观察期轮询示例

```bash
# 每 60 秒执行一次：

# Step 1: 查询 Sunfire 观测数据并写入事件
node scripts/report-observation.js --task-id $TASK_ID \
  --batch-index N \
  --app-name <app>

# Step 2: 尝试推进下一批（同时校验时间门控和观测门控）
node scripts/resume-next-batch.js --task-id $TASK_ID \
  --deploy-order-id "<deploy-order-id>" \
  --batch-index N
```

- `report-observation.js` 输出 `conclusion: "passed"|"warning"|"failed"`
  - `passed`: 无异常
  - `warning`: LOW 级别异常（允许推进）
  - `failed`: HIGH 级别异常（`resume-next-batch.js` 会阻止推进）
- 如果 `SUNFIRE_ACCESS_ID` / `SUNFIRE_SECRET_KEY` 未配置，观测步骤会被跳过（skipped），不影响推进

## 第 N 批成功

```bash
node scripts/report-event.js --task-id $TASK_ID deploy_batch \
  --deploy-order-id "<deploy-order-id>" \
  --batch-index N \
  --status "SUCCESS"
```

## 第 N 批失败/异常

```bash
node scripts/report-event.js --task-id $TASK_ID deploy_batch \
  --deploy-order-id "<deploy-order-id>" \
  --batch-index N \
  --status "FAILED" \
  --error-message "<异常描述>"
```

## 批次推进（第 2 批及以后）

观察期满后调用：

```bash
node scripts/resume-next-batch.js --task-id $TASK_ID \
  --deploy-order-id "<deploy-order-id>" \
  --batch-index <当前已完成的批次号>
```

脚本返回确认后，执行实际推进命令：

```bash
a1 app deploy-order batch resume <deploy-order-id> --batch-num <next-batch> --app <app>
```

## 所有批次完成

最后一批观察期通过后 → 进入 Phase 8 完成任务。

## 失败诊断

```bash
a1 app pipeline stage job task status --task-id <task-id> view-diagnosis
a1 app pipeline stage job task status --task-id <task-id> log
```
