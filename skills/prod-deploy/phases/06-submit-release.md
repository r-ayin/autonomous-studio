# Phase 6: 提交发布单

构建和准入通过后，pipeline 进入"正式提交发布单"stage。
**提交前必须先校验发布权限（canAutoSubmit），再决定是否继续。**

## 步骤 1：下钻定位"正式提交发布单"task

```bash
# 获取 stage 列表，找到"正式提交发布单"stage（位于"构建准入"之后）
a1 app pipeline stage list --pipeline-id <pipeline-id> --app <app>
→ 获取"正式提交发布单"stage 的 stage-id

# 获取该 stage 下的 job 列表
a1 app pipeline stage job list --stage-id <submit-stage-id> --app <app>
→ 获取 job-inst-id

# 获取 job 下的 task 列表
a1 app pipeline stage job task list --job-inst-id <job-inst-id> --app <app>
→ 获取 task-id
```

## 步骤 2：校验发布权限（canAutoSubmit）

```bash
a1 app pipeline stage job task status --task-id <task-id> --app <app>
→ 提取返回结果中的 canAutoSubmit 字段
```

**注意：此命令不需要 deploy-order-list 参数，只查 task status 获取 canAutoSubmit 字段。**

### canAutoSubmit == true（有权限）

追加权限检查项到 pre_check 事件（工具会自动合并到已有检查项中，只需传入新增项）：

```bash
node scripts/report-event.js --task-id $TASK_ID pre_check \
  --check-items '[{"name":"发布权限检查","status":"PASS","tips":"当前agent有发布权限可以继续发布"}]' \
  --status "SUCCESS"
```

→ 继续步骤 3 提交发布单。

### canAutoSubmit == false（无权限）

追加权限检查失败项并终止（工具会自动合并到已有检查项中）：

```bash
node scripts/report-event.js --task-id $TASK_ID pre_check \
  --check-items '[{"name":"发布权限检查","status":"FAILED","tips":"当前agent无发布权限，请配置"}]' \
  --status "FAILED" \
  --error-message "当前agent无发布权限，请配置"
```

→ 完成任务：

```bash
node scripts/complete-task.js --task-id $TASK_ID --success false --summary "发布权限校验失败"
```

## 步骤 3：轮询等待 submit-deploy 可用

权限校验通过后，部署阶段的 task 会进入 WAITING 状态。
**必须轮询 task status，直到 Supported Actions 出现 `submit-deploy` 才可以提交发布单。**

```bash
# 下钻到部署阶段的 task
a1 app pipeline stage job list --stage-id <deploy-stage-id> --app <app>
a1 app pipeline stage job task list --job-inst-id <job-inst-id> --app <app>

# 轮询 task 状态，等待 Supported Actions 包含 submit-deploy
a1 app pipeline stage job task status --task-id <task-id> --app <app>
# 如果 Supported Actions 中没有 submit-deploy，间隔 10s 继续轮询

# Supported Actions 出现 submit-deploy 后，提交发布单
a1 app pipeline stage job task status --task-id <task-id> --app <app> submit-deploy
```

## 步骤 4：获取发布计划（resolvedStrategy）

提交发布单成功后，查询 task 状态获取发布计划：

```bash
a1 app pipeline stage job task status --task-id <submit-task-id> --app <app>
→ 提取返回结果中的 resolvedStrategy 字段
```

将发布计划保存为独立事件：

```bash
node scripts/report-event.js --task-id $TASK_ID deploy_plan \
  --deploy-order-id "<deploy-order-id>" \
  --resolved-strategy '<resolvedStrategy JSON>'
```
