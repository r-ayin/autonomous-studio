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
