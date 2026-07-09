# 阶段四五六七：验证 + 评审 + 部署 + 归档（交付期）

> 执行 E2E 验证、代码评审、上线、归档时加载本文件。

## ④ 验证（E2E）

按任务类型选模式：

**模式 A — 全量验证**（新功能、功能优化）
1. 遍历 prd.json 所有 done 的 task → 逐条验证 acceptance
2. 读 test-cases.md → 按顺序执行全部用例
3. 不通过 → 回退到开发阶段

**模式 B — 定点验证**（Bug 修复、文案/样式）
1. 只跑 git diff 涉及的用例
2. 额外跑冒烟测试

```bash
/home/admin/.local/bin/playwright test e2e/              # 全量
/home/admin/.local/bin/playwright test e2e/<功能>.spec.ts  # 定点
/home/admin/.local/bin/playwright test --grep @smoke       # 冒烟
```

测试脚本：`e2e/<功能名>.spec.ts`，失败截图存 `e2e/screenshots/`。

### E2E 方法论（V9.3 沉淀，必读）

**核心认知：`<<PLACEHOLDER>>` 不是阻断点。** oneday-sbproxy 服务端会把字面占位符 `<<PLACEHOLDER>>` 自动替换成真实 key——所以无论 curl 还是前端 SDK（`@ali/oneday-frontend-sdk` 不传 key 时默认用 `<<PLACEHOLDER>>`），走 sbproxy 都能正常读写。**禁止声称「SDK 占位符拿不到真实 key 所以 E2E 跑不了」——这是错的，placeholder 走 sbproxy 就是能跑。** 本地非嵌入环境能读能写，不需要配真实 key、不需要上 OneDay 平台。

**本地 Playwright 看 UI + curl 查 DB = 完整 E2E**，两者结合才是功能+数据双验证：
- **起 dev server**：`npm run dev`（或项目对应命令）。**端口从命令输出里找**——不一定是 8080，本项目实际是 3019。看输出里 `Loopback: http://localhost:XXXX/` 那行。起不来或连不上先确认端口对不对，别假设。
- **Playwright 看 UI**：用 `npx playwright test e2e/<功能名>.spec.ts` 跑本地 dev server，点按钮看 UI 交互/状态变化。Playwright config 里的 baseURL 要对上 dev server 实际端口。
- **curl 查/种 DB**：用 sbproxy 直读直写数据库，验数据真写入、或给 UI 喂数据。模板：
  ```
  # 读（APP_ID 从项目 onedaycloud/AGENTS.md 或 CLAUDE.md 找，如 1BSoUdqQ）
  curl -s 'https://oneday-sbproxy.alibaba-inc.com/<APP_ID>/rest/v1/<表名>?select=*&limit=5' \
    -H 'apikey: <<PLACEHOLDER>>' -H 'Authorization: Bearer <<PLACEHOLDER>>' -H 'oneday-app-id: <APP_ID>'
  # 写
  curl -s -X POST 'https://oneday-sbproxy.alibaba-inc.com/<APP_ID>/rest/v1/<表名>' \
    -H 'apikey: <<PLACEHOLDER>>' -H 'Authorization: Bearer <<PLACEHOLDER>>' -H 'oneday-app-id: <APP_ID>' \
    -H 'Content-Type: application/json' -H 'Prefer: return=representation' -d '<JSON>'
  ```
  验通不通：先 `curl .../rest/v1/<表>?select=*&limit=1`，返回真实数据/真实 PG 错误（如列名错）= 通了；返回 401/403 = 占位符没被注入（罕见，查 APP_ID 和 header）。

**UI 数据为空时怎么办（不是跳过的理由）**：
1. curl 同表确认 DB 里有没有数据。没数据 → 用 curl INSERT 种一条（带对应状态/字段），再刷新 UI 看。
2. DB 有数据但 UI 空 → 查前端 client 配置（appId 对不对、是否走 sbproxy）、查 RLS（anon 角色有没有读权限）。
3. 都查过仍 UI 空 → 才考虑 testMode+mock 或 OneDay 平台嵌入环境。**禁止第一步就跳过、禁止用"构建通过"冒充。**

**三层查工具**（查过才能声称"没工具"，禁止跳过）：
1. 项目自身：`package.json` 的 `@playwright/test`、`playwright.config.ts`、`e2e/` 目录、`*.spec.ts`
2. 全局 skill：`browser-flow-recorder`（录流程重放）、`1d-platform-dev` Browser Use
3. 跨项目：其他项目（如 chuizhihua）的 Playwright 脚本、`workspace/server/playwright-manager`

**小白环境一键配**：`bash ~/.claude/skills/autonomous-studio/scripts/setup-e2e.sh .`（检测装 @playwright/test + chromium + 跑冒烟，零配置）

**心跳/定时任务验证**：devix 定时脚本（如 itag2-devix-fetch.js）用 `pm2 start` 常驻，心跳 = curl 查目标表 `last_update` 是否在更新（隐式心跳），不更新=脚本没活着。

## ⑤ 代码评审

- Skill: `code-review` + `simplify`
- 上下文：git diff + prd-decisions.md + 项目代码风格规范
- 评审对照 PRD 决策，不是凭感觉，确保评审有依据

**代码健康度扫描**（可选，功能版本完成后推荐跑一次）：
- Skill: `ponytail-audit`
- 扫描全仓库，找多余代码、可简化逻辑、重复实现、未使用的抽象
- 输出按削减量排序，每条一行，附 tag（delete/stdlib/native/yagni/shrink）
- 发现的问题分两类处理：快速修（5 分钟内能改的当场改）、留待下版本（记入 planning/tech-debt.md）

## ⑥ 上线部署

**首选 OneDay CLI 发布**（OneDay 平台项目标准方式）：

```bash
# 前置：oneday CLI 已装 + 已登录（oneday whoami 有输出）
oneday build        # 云端沙箱构建（流式日志，看是否报错）
oneday publish      # 发布上线：构建 + 上传 + 出线上访问地址
```

- **已存在的 OneDay 项目**（项目已在平台，有 app id）：直接 `oneday build && oneday publish`，不重新 create/import。
- **新项目首次上线**：`oneday import ./项目目录` 导入 → `oneday build && oneday publish`。
- **登录过期**：`oneday whoami` 无输出时，提示用户在会话里 `! oneday login`（浏览器授权，不要静默替用户执行）。
- 详见 `oneday-open-cli` 技能。

**备选**：CLI 不可用时退回 `prod-deploy` skill。

**部署后验证**：拿到线上地址后，curl 核心页面 + 关键 API 确认能访问，不报 5xx。

## ⑦ 归档（Episodic LTM）

**触发时机**：部署完成后自动执行。

**执行步骤**：
1. 从 status.json 提取功能名称和时间范围
2. 创建 `archive/YYYY-MM-DD-{功能名}/` 目录
3. 复制 `planning/` 全部文件到归档目录
4. 从 prd.json 提取 blocked tasks 列表
5. 生成 `archive/YYYY-MM-DD-{功能名}/retrospective.md`
6. 更新 status.json：`currentStage = "archived"`

**retrospective.md 格式**（带结构化教训标签，供未来项目复用）：
```markdown
# 回顾：{功能名}
**时间**：{开始} → {结束}
**任务总数**：{total} 个，其中 P0 {p0_count} 个
**阻塞任务**：{blocked_count} 个

## 阻塞原因
- N1-03：权限校验时序问题，需先建角色再绑定权限

## 教训（供未来项目参考）
- [坑/权限] 权限 task 必须先建后用，不能和业务 task 并行
- [坑/数据库] Supabase RLS 开启后需要 service role 才能写入
- [坑/PRD] 弹窗关闭按钮经常被遗漏，PRD 要明确写触发条件和关闭效果

## 做得好的地方
- prd-decisions.md 的讨论记录完整，定稿时无遗漏
```

**跨项目学习闭环**：
- 新项目 Studio 激活时，扫描 `archive/*/retrospective.md`
- 提取同类型项目（根据 taskType 匹配）的教训标签 `[坑/*]`
- 写入本次项目 `planning/known-pitfalls.md`
- Validator 验证时额外检查 known-pitfalls.md 中的历史坑点

## 回退规则

| 场景 | 回退到 |
|---|---|
| ③-V Validator 失败 | → ③ 开发（自动修复） |
| ③-R 全量对照发现遗漏 | → ③ 开发（补充实现） |
| ④ 验证发现功能不对 | → ③ 开发 |
| ⑤ 评审发现设计问题 | → ② PRD |
| 上线后发现 bug | → ③→④→⑥ 快速发布 |

## 辅助 Skill（按需调用）

| Skill | 什么时候用 |
|---|---|
| `ponytail-audit` | 评审阶段做代码健康度扫描，找冗余/可简化/死代码 |
| `excalidraw-diagram-skill` | PRD 阶段需要画流程图时 |
| `devix-dingtalk-skill` | PRD 写入钉钉文档时 |
| `agents-map` | 进入新项目需要理解全貌时 |
| `zujianfuyon` | 开发阶段需要复用组件时 |
