# autonomous-studio

> 遵循工作区协议 [PROTOCOL.md](../PROTOCOL.md) | 由 project-protocol Skill 管理

## 项目身份
- **名称**：autonomous-studio（自主开发引擎 · 分发版源码）
- **目的**：Claude Code 自主决策引擎 + Studio 六阶段流水线的**唯一真源**，部署到 `~/.claude/`（全局运行位）
- **技术栈**：Markdown（Skill/Prompt）+ Python（Hooks）+ Bash/PowerShell（脚本）
- **入口**：`SKILL.md`（skill 激活）| `hooks/install-studio-hooks.sh`（全栈部署器）

## 快速命令
```bash
bash hooks/install-studio-hooks.sh        # 部署 hooks + 重建 settings.json 引擎栈
powershell -File watchdog-boot.ps1        # 注册 Windows L6 watchdog 计划任务
python -m pytest tests/ -q                # 跑测试
```

## 项目规则
1. **真源链路**：本仓库 → `~/.claude/`（全局运行位）→ 各项目 `.claude/` 只存运行时数据。改引擎先改这里，再用部署器同步。
2. **禁止内联明文凭证**（token 走 git credential helper）。
3. 跨平台约束：shell 脚本必须用 polyglot python shim；Windows 用 watchdog.ps1，Linux 用 watchdog.sh。
4. 上游：GitHub `r-ayin/autonomous-studio` + aone `qunbu/autonomous-studio`；ECS `/root/workspace/autonomous-studio-aone` 是活跃运行副本，同步前先收割其未提交改动。
