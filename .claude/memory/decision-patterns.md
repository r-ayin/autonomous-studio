---
name: decision-patterns
description: 从决策案例中提取的可复用决策模式 — 引擎用于快速匹配和信心评估
metadata:
  type: project
---

# 决策模式库

> 引擎通过 `pattern_signature` 字段匹配历史模式，加速决策。
> 模式从 `decision-archive.md` 和 `case-*.json` 中提取。

## 已提取的模式

### Pattern: debug_fix_and_verify
- **签名前缀**: `implementation:debug:*:fix_verify`
- **触发条件**: 用户报告 bug，有明确复现步骤
- **典型响应**: 定位 1-3 个文件 → 修复 → 运行聚焦测试 → 报告结果
- **自主跟进**: 运行全量测试、搜索相似 bug、更新 PROGRESS.md
- **参考案例**: 决策档案案例 1（微信文件发送）、案例 5（爬虫全面修复）

### Pattern: wechat_file_send
- **签名前缀**: `tooling:debug:pachong-master:wechat_media`
- **触发条件**: 需要通过 Hermes 向微信发送文件
- **典型响应**: 使用 MEDIA: 语法嵌入消息体，走加密上传流程
- **关键教训**: `hermes send --file` 是读文件当正文，不是发附件
- **参考案例**: 决策档案案例 1

### Pattern: ssh_resume_recovery
- **签名前缀**: `infrastructure:meta:*:session_resume`
- **触发条件**: SSH 断开会话需要恢复
- **典型响应**: 读 checkpoint → 读 memory → 报告进度 → 继续工作
- **自主跟进**: SessionStart 自动注入恢复指令
- **参考案例**: 决策档案案例 4

### Pattern: crawler_quality_optimization
- **签名前缀**: `implementation:debug:pachong-master:crawler_fix`
- **触发条件**: 爬虫结果质量差，匹配精度不够
- **典型响应**: P0 阻塞修复 → P1 精度优化 → P2 精细化调整
- **自主跟进**: 端到端验证 + 关键词/评分模型持续优化
- **参考案例**: 决策档案案例 5

### Pattern: notification_channel_selection
- **签名前缀**: `tooling:meta:*:notification_choice`
- **触发条件**: 需要选择通知渠道
- **典型响应**: 优先已用基础设施（Hermes），不引入新第三方依赖
- **自主跟进**: 单向通知，微信默认通道
- **参考案例**: 决策档案案例 8

### Pattern: workspace_path_configuration
- **签名前缀**: `configuration:meta:*:workspace_path`
- **触发条件**: 工作区路径需要配置
- **典型响应**: 多层保障（bashrc + profile + PowerShell + 快捷方式）
- **关键教训**: PowerShell Get-Command 可能返回数组导致参数混乱
- **参考案例**: 决策档案案例 3

### Pattern: protocol_bootstrap
- **签名前缀**: `infrastructure:plan:*:protocol_setup`
- **触发条件**: 需要建立项目标准化规范
- **典型响应**: 宪法 → 自举引擎 → Hook 守门 → 终端三件套
- **自主跟进**: 自动检测缺失文件并生成
- **参考案例**: 决策档案案例 7

### Pattern: phone_notification_setup
- **签名前缀**: `infrastructure:meta:*:phone_notify`
- **触发条件**: 需要手机系统通知
- **典型响应**: ntfy.sh → Android app → 系统通知栏
- **关键决策**: AskUserQuestion 永不去抖，因为用户决策是极重要场景
- **参考案例**: 决策档案案例 6

---

## Studio 融合流程模式（v3.0 新增）

### Pattern: studio_prd_confirmation
- **签名前缀**: `studio:prd:*:draft_pending`
- **触发条件**: PRD 草稿生成后（draftPending.stage="prd"），用户未确认
- **典型响应**: L2 心跳检测到 draftPending.confirmed=false → 静默等待（不重复生成）
- **用户确认模式**: "没问题"/"OK"/"继续" → decision-observer.py stage_confirm → 推进阶段
- **关键规则**: 确认前不推进 currentStage；生成后不重复调用 pm-spec
- **自主跟进**: 确认后下次 L2 自动推进到 tech-plan 阶段

### Pattern: studio_route_correction
- **签名前缀**: `studio:route:*:health_low`
- **触发条件**: L3 研判 route_health_score < 5（路线偏差）
- **典型响应**: RC-1 回溯 → RC-2 外部研究 → RC-3 审议 → RC-4 SUGGEST 修正建议
- **关键规则**: 路线修正永远是 SUGGEST，不自动修改任何文件；用户确认后才执行
- **超时规则**: correctionPending 超 3 次心跳无响应 → 自动降级为建议（不持续阻断）
- **信心映射**: route_health_score 直接映射到 confidence（score×10）

### Pattern: studio_multi_worker_execution
- **签名前缀**: `studio:development:*:serial_handoff`
- **触发条件**: tech-plan.md 确认后，进入代码开发阶段
- **典型响应**: 先查 component-index.md → 可选 ensure-repo → spawn serial-agent-handoff
- **关键规则**: 整个 serial-agent-handoff 会话计为 1 次自主行动（不是 per-worker）
- **handoff 文件**: 创建后路径写入 status.json.engine.stageArtifacts.handoffFile
- **每个 worker prompt 必含**: "You are not alone. Do not revert edits made by others."

### Pattern: studio_verification_mode_select
- **签名前缀**: `studio:verification:*:e2e_mode`
- **触发条件**: 代码开发完成，进入验证阶段
- **典型响应**: 读 status.json.taskType → 选择验证模式
  - new-feature/enhancement → 模式A：全量（按 test-cases.md 逐条）
  - bug-fix/style → 模式B：定点（git diff 相关）+ 冒烟测试
- **失败处理**: 最多回退 ④ 3 次，第3次仍失败 → SUGGEST（等用户介入）
- **E2E 路径**: /home/admin/.local/bin/playwright

### Pattern: studio_l3_strategic_review
- **签名前缀**: `studio:l3:*:strategic_review`
- **触发条件**: L3 每次激活（不受 autoAdvance 影响）
- **典型响应**: S-0 降频豁免 → S-1 一致性 → S-2 机会成本 → S-3 技术债 → S-4 跨项目
- **关键规则**: locked=true 时强制将 consecutive_no_delta 归零（防止 L3 降频）
- **输出**: route_health_score 写入 status.json.engine.routeHealth
