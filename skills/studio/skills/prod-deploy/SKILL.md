---
name: prod-deploy
description: |
  生产环境部署技能。变更单 → 流水线状态检测 → 提交流水线 → 构建 → 发布准入 → 分批部署 → 完成。
  全自动执行，无需人工交互。通过脚本实时记录每个阶段进度事件。
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# prod-deploy

## 环境变量

| 变量 | 说明 | 必填 |
|------|------|------|
| `DEVOUT_SERVER_URL` | aone-agent-server 基础 URL（如 `http://localhost:7001`） | 是 |
| `SUNFIRE_ACCESS_ID` | Sunfire OpenAPI accessKeyId（观测数据查询） | 否 |
| `SUNFIRE_SECRET_KEY` | Sunfire OpenAPI secretKey（HMAC-SHA1 签名） | 否 |

## 输入参数

| 参数 | 说明 | 必填 |
|------|------|------|
| app | 应用名 | 是 |
| pipeline-id | 流水线 ID | 是 |
| branch | 分支名 | 是 |
| cr-id | 变更单 ID | 否（为空时 Phase 1 创建） |
| org-id | 项目空间 ID | 否 |
| task-id | 任务 ID（由系统注入） | 是 |

每批观察期默认 5 分钟（由 `resume-next-batch.js` 从 deploy_plan 的 `resolved_strategy.observe_minutes` 读取）。

## 进度追踪

通过 `scripts/` 目录下的脚本记录部署进度。所有脚本都需要传 `--task-id`。

| 脚本 | 用途 |
|------|------|
| `node scripts/report-event.js --task-id <id> pipeline_check [opts]` | 流水线检测：首次调用创建事件(RUNNING)，传 --status 时更新为终态 |
| `node scripts/report-event.js --task-id <id> build [opts]` | 构建阶段：首次调用创建事件(RUNNING)，传 --status 时更新为终态 |
| `node scripts/report-event.js --task-id <id> pre_check [opts]` | 准入阶段：创建事件 + 更新 check_items + 终态 |
| `node scripts/report-event.js --task-id <id> deploy_plan [opts]` | 发布计划：存储 resolved_strategy |
| `node scripts/report-event.js --task-id <id> deploy_batch [opts]` | 单批次部署：按 batch_index 定位，创建/更新 |
| `node scripts/report-observation.js --task-id <id> --batch-index N --app-name APP` | 观察期查询 Sunfire 观测数据并写入事件 |
| `node scripts/resume-next-batch.js --task-id <id> --batch-index N` | 推进下一批：校验观察期 + Sunfire 观测后允许继续 |
| `node scripts/complete-task.js --task-id <id> --success true/false --summary "..."` | 标记任务完成/失败 |
| `node scripts/list-events.js --task-id <id> [--status S]` | 查询已有事件（断点恢复时使用） |
| `node scripts/poll-build.js --task-id <id> --pipeline-id PID --app-name APP` | 单次轮询构建状态 |
| `node scripts/poll-pre-check.js --task-id <id> --pipeline-id PID --app-name APP` | 单次轮询准入状态 |

**关键特性**：
- 无需追踪 event_id — 脚本通过 task_id + event_type（+ batch_index）自动定位事件
- 首次调用创建事件（status=RUNNING），后续调用 merge 更新 payload
- 传入 --status 时更新为终态（SUCCESS/FAILED），终态不可再修改
- 轮询类脚本为单次执行，需要你自行循环调用（每 5s 一次）

## report-event.js 各事件类型参数

### pipeline_check
```bash
node scripts/report-event.js --task-id <id> pipeline_check \
  --pipeline-id <PID> --app-name <APP> [--status SUCCESS|FAILED] \
  [--pipeline-status <actual_status>] [--error-message <msg>]
```

### build
```bash
node scripts/report-event.js --task-id <id> build \
  --pipeline-id <PID> --cr-id <CRID> [--status SUCCESS|FAILED] \
  [--error-message <msg>]
```

### pre_check
```bash
node scripts/report-event.js --task-id <id> pre_check \
  [--pipeline-id <PID>] [--task-id <precheck_task_id>] \
  [--check-items '<JSON_ARRAY>'] [--status SUCCESS|FAILED] \
  [--error-message <msg>]
```

### deploy_plan
```bash
node scripts/report-event.js --task-id <id> deploy_plan \
  --deploy-order-id <OID> --resolved-strategy '<JSON>'
```

### deploy_batch
```bash
node scripts/report-event.js --task-id <id> deploy_batch \
  --deploy-order-id <OID> --batch-index <N> [--batch-total <T>] \
  [--group <name>] [--instances <N>] [--payload '<JSON>'] \
  [--status SUCCESS|FAILED] [--error-message <msg>]
```

## 流程状态机

```
Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8
(恢复检查)  (CR准备)  (流水线检测) (提交流水线) (轮询构建) (发布准入) (提交发布单) (分批部署)  (完成)
```

任何阶段失败 → `complete-task.js --success false` 终止流程。

## 阶段详情

各阶段的详细操作指令参见 `phases/` 目录下的对应文件：

| 阶段 | 文件 | 说明 |
|------|------|------|
| Phase 0 | `phases/00-checkpoint-recovery.md` | 断点恢复检查 |
| Phase 1 | `phases/01-prepare-cr.md` | 准备变更单 |
| Phase 2 | `phases/02-pipeline-check.md` | 流水线状态检测 |
| Phase 3 | `phases/03-trigger-build.md` | 提交流水线 + 构建事件 |
| Phase 4 | `phases/04-poll-build.md` | 轮询构建阶段 |
| Phase 5 | `phases/05-pre-check.md` | 发布准入 |
| Phase 6 | `phases/06-submit-release.md` | 提交发布单 |
| Phase 7 | `phases/07-batch-deploy.md` | 分批部署轮询 |
| Phase 8 | `phases/08-finish.md` | 完成/回滚 |

**执行时请阅读对应阶段文件获取详细指令。**

## 关键约束

1. **观察期强制**：每批部署后必须通过 `resume-next-batch.js` 推进，观察期未满会被拒绝
2. **事件幂等**：相同 event_type（+ batch_index）不会重复创建，自动定位已有事件
3. **任务完成**：必须通过 `complete-task.js` 标记任务结束
4. **失败即停**：任何阶段检测到失败，立即调用 `complete-task.js --success false` 终止
5. **状态统一**：所有状态值使用大写 INIT/RUNNING/SUCCESS/FAILED
