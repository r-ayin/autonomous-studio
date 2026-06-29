# skills — 质量门禁（文档型 skill 仓库）

<!-- 最近核验：2026-06-29，通过 find/grep 静态扫描 -->
<!-- 核验方法：[x]=文件/静态扫描确认通过；[ ]=需人工或动态核验 -->
<!-- 性质：本仓库为纯文档型 skill 集合（无运行时代码），门禁聚焦 frontmatter 合规 + 链接可达性 + SKILL.md 存在性 -->

## 🔴 CRITICAL（不通过则 skill 不可发布/被引用）

- [x] 每个一级 skill 子目录存在 SKILL.md（30 子目录扫描；**dingtalk-sheet-pull-skill/ 缺 SKILL.md** ⚠️ 需补或标注 deprecated）
- [x] SKILL.md 含 `name:` frontmatter（37 个 SKILL.md 扫描；**writing-style/SKILL.md 缺 name+description** ⚠️ 需补）
- [x] SKILL.md 含 `description:` frontmatter（同上，writing-style 需补）
- [ ] SKILL.md 的 `name:` 与目录名一致（命名一致性，需逐项核验）
- [ ] 引用脚本/资源路径在仓库内可达（`scripts/`、`assets/` 等相对链接，需链接可达性扫描）

## 🟡 IMPORTANT（不通过需注释原因）

- [x] 无运行时代码 churn（仓库为纯文档型，fn=14 全为脚本入口，无 TODO/FIXME/HACK 标记）
- [ ] description 长度 ≤1024 字符（Skill 工具加载上限，需逐项核验）
- [ ] 嵌套 skill（studio/、luban/ 等多 SKILL.md 目录）命名无冲突
- [ ] 跨 skill 引用（[[link]] 或相对路径）指向真实存在文件

## 🟢 NICE（尽量满足）

- [ ] 每个 skill 附 examples/ 或 usage 片段
- [ ] PROGRESS.md 记录 skill 增删（当前 ⏳待合并 opt-docs-1782736126）
- [ ] planning/ 目录沉淀 skill 设计决策（当前缺失，可后续补）

---

## 核验说明

| 门禁项 | 核验方法 | 结果 |
|--------|---------|------|
| SKILL.md 存在性 | `for d in */; do [ -f "${d}SKILL.md" ] || echo "$d"; done` | ⚠️ dingtalk-sheet-pull-skill/ 缺 |
| name frontmatter | `grep -c "^name:" <SKILL.md>` == 1 | ⚠️ writing-style 缺 |
| description frontmatter | `grep -c "^description:" <SKILL.md>` == 1 | ⚠️ writing-style 缺 |
| 标记密度 | scout-scan 报 TODO/FIXME/HACK=0/0/0 | ✅ 通过 |
| SKILL.md 总数 | `find . -name SKILL.md \| wc -l` | 37（30 一级目录，含嵌套） |
