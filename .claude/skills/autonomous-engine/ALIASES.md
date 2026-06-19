# Skill 别名表

用途：Skill 文档之间互相引用时优先使用 `@别名`，不要把具体目录名、Skill 文件名或未来可能改名的路径写散。

## 项目本地 Skill

| 别名 | 当前 Skill | 说明 |
|---|---|---|
| `@beginner-learning-code` | `beginner-learning-code` | 初学者教学版代码 |
| `@agent-context-authoring` | `agent-context-authoring` | AGENTS.md / CLAUDE.md / 子代理说明撰写规范 |
| `@business-writing-coach` | `business-writing-coach` | 中文工作写作、表达复盘、去 AI 感前的场景收敛 |
| `@douyin-script-coach` | `douyin-script-coach` | 短视频选题、口播脚本、录后表达复盘 |
| `@cover-skill` | `douyin-cover-designer` | 抖音/视频号/小红书/B站封面 |
| `@video-polish-skill` | `talking-head-video-polish` | 口播/录屏视频成片、字幕、动效、渲染 QA |
| `@wechat-note-ingestor` | `wechat-note-ingestor` | 微信公众号/Get/Biji 原始资料归档 |
| `@data-assets` | `数据资产` | Obsidian 数据资产根目录 |
| `@wechat-writing-home` | `公众号写作` | 公众号选题、草稿、已发布样稿、风格与复盘 |
| `@wechat-article-style` | `公众号写作/样式/风格学习档案.md` | 公众号写作风格记忆 |
| `@wechat-correction-log` | `公众号写作/复盘/纠偏日志.md` | 公众号文章纠偏复盘 |
| `@wechat-raw-inbox` | `raw/待处理/微信公众号` | ClawBot 提取的公众号原始资料 |

## 外部或用户级 Skill

这些 Skill 可能安装在用户级目录或插件目录，不一定在本项目 `.codex/skills/` 下。文档里仍用别名引用，执行时再按当前环境解析。

| 别名 | 当前 Skill / 工作流 | 说明 |
|---|---|---|
| `@wechat-public-writer` | `wechat-public-writer` | 公众号长文写作 |
| `@humanizer-zh` | `humanizer-zh` | 中文去 AI 痕迹 |
| `@team-okrs` | `team-okrs` | OKR 页面/可视化 |
| `@personal-ai-editorial-digest` | `personal-ai-editorial-digest` | AI 早报/新闻检索类内容 |
| `@wiki` | `wiki` | 数据资产 Wiki 写入/查询 |
| `@save` | `save` | 值得沉淀的发现写回 Wiki |
| `@agents-md-slim` | `agents-md-slim` | AGENTS.md 常驻上下文瘦身审查 |

## 规则

- Skill 文档之间互相引用时，优先写本表里的 `@别名`，例如 `@video-polish-skill`、`@cover-skill`、`@douyin-script-coach`。
- 不要在正文里写易漂移的具体目录、`SKILL.md` 文件路径、旧 Skill 名或临时项目路径。
- 不要把协作对象写成 `/path/to/skill`、`./.codex/skills/...`、`@别名/子路径` 的混合形式，除非是在同一个 Skill 内引用自己的 bundled `rules/`、`scripts/`、`references/` 资源。
- 跨 Skill 协作只写能力归属：例如“视频制作交给 `@video-polish-skill`”，不要写“交给 `talking-head-video-polish/SKILL.md`”。
- 如果确实需要引用同一 Skill 内的脚本或规则，先写 Skill 别名，再接相对资源路径，例如 `@video-polish-skill/scripts/asr_router.py`。
- 文档正文优先写 `@cover-skill`，不要写具体目录。
- 如果某个 Skill 改名或迁移，只更新本表和少量入口文件。
- 真实执行时可以把别名解析为当前安装位置；不要让长期规则依赖微信临时路径或机器绝对路径。
