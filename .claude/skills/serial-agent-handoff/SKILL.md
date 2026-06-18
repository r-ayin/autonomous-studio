---
name: serial-agent-handoff
description: Use when a reviewed PRD, technical contract, or implementation design should be executed through sequential sub-agents with a shared handoff file instead of Ralph. Creates or updates a task handoff record, asks which project harnesses to apply before execution, then runs worker agents serially with main-agent review, validation, and handoff updates.
---

# Serial Agent Handoff

This skill replaces the Ralph execution step when the user wants controlled, sequential sub-agent development with file-based handoff.

Use it after requirement clarification and planning are already done, usually after:

1. `grill-me` or `scenario-alignment`
2. PRD creation
3. `technical-contract-review`
4. `implementation-design-prd`

This skill owns only implementation orchestration. Do not redo product discovery unless the source documents contradict each other.

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

## Worker Prompt Rules

When spawning a worker, give it:

- The exact feature stage it owns
- The handoff file path
- The source documents it must read
- The harnesses it must read
- The allowed write scope and forbidden paths
- The expected validation commands
- A requirement to update or provide content for the handoff execution log

Every worker prompt must include:

```text
You are not alone in this codebase. Do not revert edits made by others. Work with existing changes. Keep the patch scoped to your assigned files and responsibilities.
```

Prefer one worker at a time. Wait for the current worker, review its changes locally, run verification, update the handoff file, then start the next worker.

## Validation

The main controller validates each worker result before continuing.

Default validation:

- Inspect changed files.
- Run the project's relevant typecheck/build/test commands.
- For UI changes, use browser/device/screenshot verification when available and meaningful.
- For backend changes, verify routes, schemas, idempotency, auth, and tests appropriate to risk.
- For deploy changes, use repository deployment scripts and keep backups when required by project policy.

Optional validator agent:

- Use a validator agent for high-risk flows: auth, payment, data migration, deployment, cross-project integration, file upload/download, or any user-specified critical path.
- Validator agents verify only; they do not fix code.

## Progress And Patterns

Preserve Ralph's useful habit of accumulating reusable learnings, but do not write new work into `scripts/ralph/progress.txt`.

Put reusable learnings in the handoff file under `Codebase Patterns` when they will help later workers. If the learning is stable and broadly useful, update the appropriate `.planning/codebase/` document after the user agrees or as part of a documentation task.

## Stop Conditions

Stop and ask the user when:

- Source documents contradict each other in a way that affects product behavior.
- A worker needs to change a forbidden path or existing API contract.
- A required external service, device, credential, or asset is unavailable and no safe fallback exists.
- Verification repeatedly fails for the same reason and the next action would be speculative.

Otherwise, continue through the serial plan until the requested stages are complete.
