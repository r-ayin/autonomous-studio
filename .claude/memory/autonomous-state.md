---
<!-- ENGINE_VERSION: 2.2 -->
<!-- ISOLATION_MODE: agent_subprocess -->
<!-- SCOUT_MODE: active -->
<!-- CHECKPOINT_PROTECTION: enabled -->
name: autonomous-state
description: 自主决策引擎运行状态 — 跨会话追踪引擎活动、目标、冷却计数
metadata:
  type: project
---

# 引擎状态

- **最后活跃: 2026-06-16T21:00:00Z（moni 看板重写 + 私有仓库部署 + 全模块梳理 — 两层架构 30+ 模块状态追踪）
- **活跃项目**: **moni** (股票量化系统) — 看板已重写，两层架构 30+ 模块，待推进 WFO 评估 + 因子回测
- **当前阶段**: 项目归并完成——moni = 策略执行层 + 因子研发层，私有仓库部署完毕
- **连续自主行动**: 0 / 3（用户已交互，冷却重置）
- **自主循环**: 🟢 活跃
  - L1 Inline: 每次回复末尾内联检查 (+ git status)
  - L2 Heartbeat: CronCreate 每7分钟（goal_achieved 不再跳过）
  - L3 Deep: CronCreate 每60分钟
- **v2.1 升级**: 2026-06-15T23:20Z
  - 冷启动判定: 手动标记 → 自动数据检测
  - L2 预检: goal_achieved 不再 SKIP → 执行主动扫描
  - 新增: §1.5 主动扫描协议（瞭望模式）
  - 冷启动行为: 被动 OBSERVE → 主动 SUGGEST
  - L1 内联: + git status 检查
- **v2.2 升级**: 2026-06-16T03:15Z
  - 🚀 冷启动协议重写: 「禁止执行」→「检查点保护 + Git 回滚」
  - 🔧 calibration patterns 同步: 2 → 13（decision-patterns.md ↔ calibration.json）
  - 🔧 冷却计数修复: autonomous-state.md ↔ calibration.json 同步
  - 🔧 冷启动毕业: 移除手动 COLD_START_GRADUATED 标记，纯数据驱动
  - 🔧 L3 降频自适应: 连续无增量时自动 60→120→240 分钟
  - 新增: §0.2 三轨策略（数据积累 + 主动扫描 + 检查点保护执行）
  - 冷启动行为: SUGGEST only → 检查点保护下可达 ACT_SILENT（不可逆操作仍须 NOTIFY）

---

## 🎯 历史目标

<!-- GOAL: achieved -->
<!-- GOAL_ID: G-2026-06-15-001 -->
<!-- GOAL_STATUS: goal_achieved -->

| 字段 | 内容 |
|------|------|
| **目标** | 搭建自主决策引擎，验证三阶段（Hook/Skill/CronCreate）正常工作 |
| **完成条件** | ①Hook ②Skill ③CronCreate ④用户确认 |
| **进度** | ①✅ ②✅ ③✅ ④✅ 已完成 (2026-06-15T06:40Z) |

## 🎯 当前行为模式（v2.2 检查点保护模式）

<!-- GOAL: scout -->
<!-- GOAL_ID: G-2026-06-15-002 -->
<!-- GOAL_STATUS: active -->

| 字段 | 内容 |
|------|------|
| **模式** | 瞭望哨兵 + 检查点保护执行——主动扫描工作区，检查点保护下可自由行动 |
| **行为规则** | ① 每次 L2/L3 心跳执行 §1.5 主动扫描协议 ② 发现写入 autonomous-suggestions.md ③ 可逆操作（文件修改/测试/git commit）→ 检查点保护下可达 ACT_SILENT ④ 不可逆操作（push/deploy/destroy）→ 仍须 ACT_NOTIFY + 用户确认 ⑤ 执行前自动创建 git 检查点，失败自动 git reset --hard 回滚 |
| **扫描范围** | git status、各项目 PROGRESS.md 更新时间、GATES.md 门禁、依赖过期、代码 TODO |
| **停止条件** | 用户设定新目标 → 引擎从瞭望模式切回目标驱动模式 |
| **超时** | 无——瞭望模式是持续后台守护 |

> 引擎在 DECIDE 阶段检查：**无活跃目标？** → 执行主动扫描协议 + 机会排序 → 信心≥60 的可逆操作在检查点保护下直接执行。
> 用户可随时说「设定目标：XXX」退出瞭望模式。
