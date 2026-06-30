# skills — 进度

> 文档型 skill 集合仓库（29 个一级 skill 目录，37 个 SKILL.md 含嵌套）。
> 本仓库无运行时代码，进度以 skill 增删 / frontmatter 合规 / 文档门禁为准。
> 进度按时间倒序，单条对应一次可观察变更。

## 当前状态（2026-06-30）

- 仓库结构稳定：29 一级 skill 目录、37 SKILL.md（含 studio/、luban/ 等嵌套），无 TODO/FIXME/HACK 标记（scout-scan 2026-06-30 核验 0/0/0）。
- 质量门禁见 `GATES.md`：CRITICAL 项全部通过（writing-style frontmatter 已补、dingtalk-sheet-pull-skill 孤立 gitlink 已移除 ✅ 2026-06-30）。
- 最近合并：`opt-skills-1782736482`（2026-06-29，scout-scan deferred-marker 约定 + 4 处 TODO 转 deferred）。

## 最近变更

- `opt-skills-1782760777` 2026-06-30（待合并）：①writing-style/SKILL.md 补 name+description frontmatter；②移除 dingtalk-sheet-pull-skill/ 孤立 gitlink（无 .gitmodules 映射、空目录不可初始化、被 devix-dingtalk-skill 取代）；③本 PROGRESS.md 新增（原 opt-docs-1782736126 分支已不存在，陈旧「待合并」blocked 实为真缺失）；目录数 30→29。
- `merge(opt-skills-1782736482)` 2026-06-29：scout-scan 引入 `TODO(deferred)` 标记约定，延期债不计入 triage 推荐分子；skills 内 4 处已 triage TODO 转 deferred 形式。
- `feat` GLM-5.2 预算制高吞吐 + 并发构建架构（daf3635）。
- `sync` 1d-platform-dev/webcontainer.md 同步最新（FontAwesome 图标乱码解决方案）。
- `feat` 新增 cloud-preview.md 云端预览服务指南。

## 待办（小工作单位池）

- [x] ~~**dingtalk-sheet-pull-skill/ 缺 SKILL.md**（GATES CRITICAL）——已移除孤立 gitlink ✅ 2026-06-30。~~
- [x] ~~**writing-style/SKILL.md 缺 name+description frontmatter**（GATES CRITICAL）——已补齐 ✅ 2026-06-30。~~
- [ ] GATES CRITICAL: `name:` 与目录名一致性逐项核验（当前 29 目录）。
- [ ] GATES IMPORTANT: 引用脚本/资源路径在仓库内可达（`scripts/`、`assets/` 相对链接扫描）。
- [ ] GATES NICE: planning/ 目录沉淀 skill 设计决策（当前缺失，可后续补）。

## 纪律

- 本仓库为纯文档型，改动以 frontmatter 合规 + 链接可达性为准，不引入运行时代码。
- 不直接动 main，所有改动走 `scripts/opt-worktree.sh commit`。
