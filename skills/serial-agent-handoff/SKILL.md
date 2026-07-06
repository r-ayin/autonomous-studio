---
name: serial-agent-handoff
description: Use when a reviewed PRD, technical contract, or implementation design should be executed through sequential sub-agents with a shared handoff file instead of Ralph. Creates or updates a task handoff record, asks which project harnesses to apply before execution, then runs worker agents serially with main-agent review, validation, and handoff updates.
triggers:
  - "使用子 agent 串行工作"
  - "开始串行 agent"
  - "按交接文件执行"
  - "串行开发"
  - "serial agent"
  - "handoff"
  - "子agent开发"
repository: https://code.alibaba-inc.com/qunbu/serial-agent-handoff
---

# Serial Agent Handoff

This skill owns only implementation orchestration — turning a confirmed plan into working code through sequential sub-agents.

Use it after requirement clarification and planning are already done, usually after PRD creation or `demand-discovery`.

## When NOT to Use

- 需求还没聊清楚，用户还在讨论功能范围 → 用 `demand-discovery`；本 skill 执行已确认的计划，不做需求探索
- 用户只是要写 PRD，不是要写代码 → 用 `pm-spec`
- 任务独立且需要并行隔离（各需独立构建环境） → 用 autonomous-studio 的 ④ 并发构建模式
- 只有一个简单任务，不需要多 Worker 串行 → 直接在主会话完成，不启动本 skill

## Core Model

- The main Codex instance is the controller: it scopes work, spawns one sub-agent at a time, reviews changes, runs verification, updates the handoff file, and decides when to continue.
- Worker sub-agents execute serially by default. Do not run coding workers in parallel unless the user explicitly asks and the write scopes are disjoint.
- Each worker owns only 1-2 clear functional blocks.
- Each worker must read the current handoff file before editing and must not revert other people's changes.
- The handoff file is the durable memory across context compression, worker turns, and future sessions.
- Do not automatically commit after each worker. Commit only when the user asks, or when the current task explicitly includes commit behavior.

## Modes

Support two operating modes:

- `plan-only`: create or refresh the handoff file and stop.
- `run`: create or refresh the handoff file, then start serial worker execution.

If the user says "使用子 agent 串行工作", "开始串行 agent", "按交接文件执行", or similar, assume `run`.
If the user only asks to "制定计划", "生成交接文件", or "先整理任务", assume `plan-only`.

## Required Inputs

Before generating or running the plan, identify these from the user's request and repository:

- Requirement source documents: PRD, scenario alignment doc, or user-provided requirement text.
- Technical source documents: technical contract and implementation design, if available.
- Target work areas: front, back, android, deploy, docs, or mixed.
- Non-negotiable constraints from the user and root `AGENTS.md`.

If the user has not specified harnesses to use, ask a short harness confirmation before starting workers. Recommend the smallest useful set:

- Always: root `AGENTS.md`
- Front work: `front/.planning/codebase/ARCHITECTURE.md`, `STRUCTURE.md`, and `INTEGRATIONS.md` when APIs/auth/data are involved
- Back work: `back/.planning/codebase/ARCHITECTURE.md`, `STRUCTURE.md`, and `DB_MIGRATIONS.md` when database changes are involved
- Android work: `android/README.md` and Android-local guidance files if present
- Deploy work: `deploy_something/README.md`

If the user already says to use your recommendation, proceed with the recommended harness set.

## Android Work

For Android tasks, always treat `android/` as its own subsystem beside `front/` and `back`.

Required Android harness:

- `android/AGENTS.md`
- `android/README.md`
- `android/settings.gradle.kts`
- `android/app/build.gradle.kts`

Default Android constraints:

- Use native Kotlin + Jetpack Compose + Material 3.
- Do not turn the app into Flutter, React Native, Ionic, Capacitor, or WebView shell unless the user explicitly changes the technology decision.
- Use VS Code, Gradle, Android SDK command line tools, ADB, real devices, and AVDs as available.
- Keep dev/prod product flavors separated.
- Prod API base URLs must use HTTPS domains, not raw production IPs.
- Reuse current Web/front APIs when suitable. If an API cannot be reused, add a mobile-generic endpoint under `back/ruoyi-fastapi-backend/module_biz_mobile`; do not create Android-only backend APIs.
- Do not modify existing Web-used backend API contracts unless the user explicitly approves.
- Keep all visible Android text in the app's i18n structure when the feature supports Chinese/English.
- Respect Android git rules: Gradle wrapper and build scripts are versioned; `.gradle/`, build outputs, `local.properties`, IDE files, APK/AAB artifacts, and signing temporaries are not.

Android handoff records should also capture:

- Local JDK and Android SDK assumptions.
- ADB path and target device or AVD name.
- dev and prod application IDs and API base URLs.
- Required backend service state for dev testing.
- Build commands, install commands, and any screenshot/logcat evidence.

Default Android validation commands, adjusted to the actual project:

```bash
cd android
./gradlew assembleDevDebug
./gradlew assembleProdDebug
adb devices -l
```

When the user asks to install after implementation, install both dev and prod only if that was requested or is the established task scope. Otherwise install the relevant flavor.

## Handoff File

Create the handoff file near the requirement documents, normally:

```text
docs/需求文档/<topic>/<feature-name>开发任务交接记录.md
```

Use `references/handoff-template.md` as the base template when creating a new record. Keep it specific to the current feature.

The handoff file must include:

- Work mode and controller/worker responsibilities
- Source documents
- Harnesses to read
- Non-negotiable constraints
- Known baseline and target paths
- Recommended serial worker order
- Per-worker goals, write scope, forbidden scope, and acceptance checks
- Required completion report format
- Execution log with date, worker name, changed files, reused/new APIs, verification, residual risks, and next-worker notes
- Reusable codebase patterns learned during execution, when they are genuinely general

## Iron Law

```
NO NEXT WORKER WITHOUT CURRENT WORKER VERIFICATION FIRST
```

违反这条规则的字面就是违反它的精神。没有例外。

| 你心里想的 | 现实 |
|---|---|
| "编译通过了，应该没问题" | 编译通过 ≠ 功能正确。跑验证命令 |
| "Worker 自己说完成了" | Worker 的报告不是验证。独立验证 |
| "只是小改动，不需要验证" | 小改动 + 跳过验证 = 小 bug 累积成大问题 |
| "时间紧，先继续下一个" | 带着未验证的改动继续 = 下一个 Worker 基于可能坏掉的代码开发 |
| "验证失败了但不影响当前功能" | 验证不通过 = 不进下一个。修完再继续 |

宣称 Worker 完成但未跑验证 = 谎报进度，不是提高效率。

## Worker Prompt 模板

每个 Worker prompt 必须包含以下全部字段。缺任何一个 = prompt 不完整，不发。

```text
## 你的任务
{TASK_DESCRIPTION}（从 handoff 文件的 Agent N 段复制）

## 你必须读的文件
- 交接文件：{HANDOFF_PATH}
- 源文档：{SOURCE_DOCS}
- 项目规范：{HARNESS_FILES}

## 你能改的文件（只限这些）
{WRITE_SCOPE}

## 你绝对不能碰的文件
{FORBIDDEN_PATHS}

## 完成后跑这些验证命令
{VALIDATION_COMMANDS}

## 你不是一个人在改这个代码库
不要回滚别人的改动。基于已有变更工作。只改你负责的文件。

## 完成后告诉主控
改了哪些文件、用了哪些已有接口、新建了哪些接口、跑验证的结果、遗留问题、下一个 Worker 需要注意什么。
```

## Validation

```
NO COMPLETION CLAIM WITHOUT FRESH VERIFICATION EVIDENCE
```

每个 Worker 完成后，主控必须：

1. 检查改动文件的 diff
2. 跑项目对应的验证命令：
   - 前端：`npm run typecheck && npm run build`（或项目实际配置）
   - 后端：`python -m pytest`（或项目实际配置）
   - Android：`./gradlew assembleDevDebug && ./gradlew assembleProdDebug`
   - 如有 UI/交互变更：**必须跑功能 E2E（不能只用构建通过冒充）**。E2E 工具按以下三层顺序查，查过才能声称"没工具"：
     1. **项目自身**：`package.json` 的 `@playwright/test`/jest-e2e 依赖、`playwright.config.ts`、`e2e/` 目录、`*.spec.ts`。有就直接用 `npx playwright test e2e/`
     2. **全局 skill**：`browser-flow-recorder`（起 noVNC 浏览器录流程可重放）、`1d-platform-dev` 的 Browser Use（无头浏览器自动化）
     3. **跨项目**：其他项目（如 chuizhihua）的 Playwright 脚本、`workspace/server/playwright-manager`
     - **三层都查过且确认不可用**，才能停手问用户。**禁止跳过查直接说"没工具做不了 E2E"**——这是能力盲区，工具常在手边却声称没有
     - **禁止用"webpack 构建通过"冒充功能验证**——构建只验编译不验交互
     - **本地预览看不见数据时怎么办**：先确认 dev server 端口对不对（从 `npm run dev` 输出里找 `Loopback: http://localhost:XXXX/`，不一定是 8080，本项目实际 3019）。再 curl sbproxy 查同表有没有数据（`<<PLACEHOLDER>>` 占位符走 oneday-sbproxy 服务端注入真实 key，能读能写，**不是阻断点**——禁止声称"SDK 占位符拿不到真实 key 所以 E2E 跑不了"）：没数据用 curl INSERT 种一条再刷新 UI；DB 有数据但 UI 空查前端 client appId/RLS。都查过仍空才考虑 testMode+mock 或 OneDay 平台嵌入环境。**不要用"看不见数据"跳过 E2E**，详见 `~/.claude/skills/autonomous-studio/phases/phase-ship.md` ④ E2E 方法论。
3. 验证通过 → 更新 handoff 文件 → 继续下一个 Worker
4. 验证失败 → 给 Worker 错误信息重试一次 → 仍失败 → 回滚 Worker 改动、记录失败原因到 handoff、停下问用户

如果你发现自己在想以下任何一条，**停手**：
- "验证命令太慢了，先跳过"
- "上个 Worker 的验证通过了，这个改动类似应该也没问题"
- "我看了 diff 觉得没问题"
- "先把所有 Worker 跑完再统一验证"

**以上全部意味着：跑验证。"觉得没问题" ≠ "验证通过了"。**

高风险流程（登录认证、支付、数据迁移、部署、跨项目集成）额外使用 validator agent，验证者只验不修。

## Studio 集成 Checkpoint（当 status.json 存在且 currentStage=development 时强制生效）

serial-agent-handoff 在 Studio 开发阶段运行时，除了上述 Validation，还必须执行以下检查。**这些不是可选的——跳过任何一步等于流程不合规。**

### 每个 Worker 完成后
1. 构建验证（webpack/tsc）— 已有
2. **Spawn Validator agent（opus）做三维度审查**：正确性（acceptance 逐条验证）+ 代码风格 + PRD 一致性。输出 review-findings。
3. Validator 标必修的 → 修完才能进下一个 Worker

### 全部 Worker 完成后
4. **③-R 全量对照 PRD**：spawn opus agent 对照完整 prd.json，确认所有 task 的 description 都被实现
5. **跑 status-sync 脚本**：`bash ~/.claude/skills/autonomous-studio/scripts/studio-status-sync.sh . --apply`
6. **更新 status.json**：stageArtifacts 指向新版本的 PRD/prd.json/handoff 文件
7. **task-evidence.json**：为新增的 task 配代码特征（grep 证据），sync 脚本依赖此文件自动判定完成状态

### 正反例

**❌ 反例（禁止——这就是本次 V8 犯的错）**：
```
7 个 Worker 全跑完 → 每个只跑了 webpack 构建通过 → 没 spawn Validator
→ 没做 ③-R 全量对照 → 没跑 status-sync → status.json 还指向旧版本
→ 汇报"全部完成"
问题：构建通过 ≠ 功能正确。没有独立审查就无法发现遗漏/回归。
```

**✅ 正例（必须）**：
```
Worker 1 完成 → webpack 构建通过 → spawn Validator(opus) 三维度审查
→ Validator 报告 2 条必修 → 修完重新验证 → 通过 → 更新 handoff → Worker 2
...（每个 Worker 重复）
全部 Worker 完成 → ③-R 全量对照 PRD（opus agent）
→ status-sync 脚本回填 → task-evidence.json 就绪
→ 更新 status.json stageArtifacts → 汇报完成
```

## 禁止行为

- ❌ Worker 自己 git commit — 必须主控统一提交
- ❌ 同一文件拆给多个 Worker — 会冲突
- ❌ 验证未通过就进下一个 Worker — 会在坏代码上堆积
- ❌ Worker 之间直接通信绕过主控 — 主控是唯一协调者
- ❌ 修改 .env / credentials / secrets 文件 — 安全敏感
- ❌ force push — 破坏历史
- ❌ 跳过 handoff 文件更新 — handoff 是跨 Worker 记忆的唯一载体

## Continuous Execution

不要在 Worker 之间停下来问用户"要继续吗？"。用户让你执行计划，就一路执行到底。只在以下情况停：

- 源文档互相矛盾
- Worker 需要改 forbidden path 或已有 API 契约
- 需要的外部服务/凭据不可用且无安全降级方案
- 验证反复失败（同一原因失败 2 次）

## Codebase Patterns

执行过程中学到的可复用知识，写到 handoff 文件的 `Codebase Patterns` 段。稳定且通用的，任务结束后更新到项目的 `.planning/codebase/` 文档。
