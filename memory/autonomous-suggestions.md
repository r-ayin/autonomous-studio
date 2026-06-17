---
name: autonomous-suggestions
description: 自主引擎建议队列 — 引擎在 SUGGEST 级别时写入，等待用户审查
metadata:
  type: project
---

# 自主建议队列

> 引擎在信心不足 (31-50) 时的建议累积区，用户可在任意时候审查。
> 标记 `[采纳]` 或 `[拒绝]` 即可反馈给引擎进行校准学习。

## 待审查建议

> 扫描时间: 2026-06-16T17:10:00Z | 模式: 冷启动瞭望 + 检查点保护 (v2.2) | L2 Heartbeat | 用户已首次交互(5/20)
> 上次扫描(16:30Z)至今变化: ⚪ wanxia WAL已归零(风险解除) ⚪ moni/wanxia/pachong PROGRESS.md 1h内更新 ⚠️ xia 38.8h stale ➕ 新untracked: Hermes HTML报告+记忆备份目录

### 🔴 项目级
- [ ] **P0: cebpubservice.com 502 — 住宅代理IP解决** — 机会分 72 | 影响: pachong-master | pachong-master v2.0反检测已重新启用3个死数据源，但 cebpubservice.com 主站返回502(服务器级封锁——非TLS/指纹/时序问题)。需要住宅代理IP(Bright Data或类似)解决。CCGP双源稳定日产~1000条，此源阻塞不致命但会影响数据量。建议：评估代理成本 vs 增量数据价值。

- [x] **P1: moni 量化回测引入 GT-Score 抗过拟合目标函数** — ✅ wfo_backtest.py 已集成 GT-Score + Monte Carlo + Island Volume + Deflated Sharpe，提交 ff0f926

- [ ] **P1: wanxia SQLite WAL 未 checkpoint — 数据丢失风险** — 机会分 58 | 影响: wanxia | git status显示 data/sunset.db-shm + data/sunset.db-wal 已修改但未提交。WAL文件持续增长未checkpoint有数据丢失风险。建议：执行 PRAGMA wal_checkpoint(TRUNCATE) 或在下次数据库关闭时自动checkpoint。

### 🟡 引擎基础设施
- [ ] **P2: pachong-master 安装 Playwright Firefox** — 机会分 45 | 影响: pachong-master | 当前仅Chromium。Firefox 3%市场份额→反爬关注度低(Firefox路线是Chromium的战略替代)。invisible_playwright (MIT开源)验证通过。建议: playwright install firefox。

- [ ] **P2: pachong-master 安装 curl-cffi** — 机会分 40 | 影响: pachong-master | TLS指纹绕过能力受限(当前httpx仅部分缓解)。curl-cffi可伪装Chrome 124 JA3/JA4指纹。建议: pip install curl-cffi。

- [ ] **P3: moni/wanxia/xia 剩余文件补交git** — 机会分 35 | 影响: 多项目 | 88文件已提交(73a9137)但~100+仍未纳入版本控制。建议: 分项目逐步提交，pachong-master优先(最完整)→moni→wanxia→xia。

## 🔴 moni 当前冲刺（看板同步）

| # | 任务 | 优先级 | 状态 |
|:--|:--|:--|:--|
| 1 | WFO 评估运行 — 对现有策略跑 GT-Score 验证 | P1 | ⬜ 需 Qlib 数据 |
| 2 | 因子有效性回测 — 跨时段 OOS 验证 | P1 | ⬜ |
| 3 | 实时数据链路修复 | P1 | ⬜ |
| 4 | GPU 工厂 ↔ moni pipeline 对接 | P1 | ⬜ |
| 5 | 连续挖掘饱和度突破 | P2 | ⏸️ |

## 已解决（本轮）
- [x] **P1: moni GT-Score 抗过拟合** — ✅ wfo_backtest.py 已集成，ff0f926
- [x] **P1: wanxia XHS 内容管线收尾** — ✅ 22:30 cron + copy-generator + E2E，c447553
- [x] **P1: wanxia SQLite WAL 未 checkpoint** — ✅ 数据正常运作
- [x] **P0: 版本控制缺口** — ✅ stock-backtest 迁入 + moni 合并完成
- [x] **P0: stock-backtest 项目迁入** — ✅ F:\ → E:\x-tool\moni\factors\，路径修正 144 文件
- [x] **P0: moni 私有仓库部署** — ✅ r-ayin/moni (private)，独立 git 历史
- [x] **P2: calibration patterns同步** — ✅ v2.2升级同步至13模式（完全解决）
- [x] **冷启动毕业标记设计债** — ✅ v2.2改为数据驱动检测（5/20交互，15 more needed）

## 本轮L3研究更新 (2026-06-16)
### 自主Agent架构（4篇新论文，非重复）
- AHE (arXiv:2604.25850): closed-loop harness evolution, 3-pillar observability, +7.3%
- HarnessX (arXiv:2606.14249): 9-dim taxonomy, AEGIS co-evolution, +14.5% avg
- Adaptive Auto-Harness (arXiv:2606.01770): harness tree + solve-time routing
- Code as Agent Harness survey (arXiv:2605.18747): 42-author, 3-layer framework

### 爬虫反检测（4项新工具/方法，非重复）
- ChromiumFish: C++ persona seeds, 内部一致指纹
- playwright-with-fingerprints (Bablosoft): Playwright指纹替换
- 指纹一致性漏洞: UA vs navigator.platform 不匹配是#1检测原因
- pulsemcp PR#218: 环境变量配置隐身

### 量化回测（3项新方法论，非重复）
- GT-Score (JRFM Jan 2026): 嵌入优化的抗过拟合目标函数
- Island Volume Selection: 参数高原替代峰值选择
- WFO硬化参数: ≥70%窗口盈利, Sharpe CV ≤1.0, parameter CV ≤0.5
