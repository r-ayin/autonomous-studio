---
name: project-index
description: x-tool 工作区全部项目索引 — 5 个核心项目 + 辅助项目
metadata:
  type: project
---

# 项目索引

## 核心项目
1. **晚霞预报小红书** → `E:\x-tool\wanxia\` — 预报系统已完成，待做小红书自动化
2. **杭州摄影约拍网站** → `E:\x-tool\xia\` — 「山夏」站，框架完成，待填充内容
3. **个人抖音内容号** → 未创建目录 — 规划中，文章生成 skill 已调教好
4. **股票量化模拟** → `E:\x-tool\moni\` — 模拟盘骨架完成，待每日自动因子挖掘
5. **招投标商机雷达** → `E:\x-tool\pachong-master\` — tender-radar，Python+PostgreSQL+飞书推送

## 协议基础设施（永久）

- `PROTOCOL.md` — 工作区宪法
- `PROJECTS.md` — 项目索引
- `.claude/skills/project-protocol/` — **自举 Skill**（安装即用）
  - `SKILL.md` — Skill 定义
  - `templates/` — 三件套模板
  - `bootstrap.py` — 自动探测 + 生成引擎
- `.claude/hooks/protocol-check.py` — PreToolUse Hook：缺失文件自动自举，不阻塞工作

### 协议保证
- 任何人/Agent 进入项目目录 → `CLAUDE.md` 自动加载
- 任何 Write/Edit 操作 → Hook 检查三件套，缺失自动生成
- 声称完成 → 必须先过 `GATES.md` 🔴 全部项目

## 辅助项目
- `聚合ai客服开发/` — OmniCS AI客服
- `AB system/` — Ozon电子面单
- `ota美团运营/` — 美团OTA自动化
- `pdd监测/` — 拼多多数据采集
- `api额度监测/` — API额度监控
- `CL4R1T4S/` — AI提示词研究
- `dongxiao/` — 水彩流体素材
- `claude/` — Claude Code启动配置
