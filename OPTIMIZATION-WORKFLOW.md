# 优化工作流：自动研究/修复 → worktree → 人工审合并

> 设计原则（用户定）：引擎的自动研究/修复/优化**全部进 optimization worktree，不碰 main**。
> 等人工回复才决定合并——这样能看到具体优化了什么，**优化可以大胆执行，不用担心损坏 main**。
> 方向差距大时自动开新 worktree，避免不同方向的改动纠缠在一个分支。

## 流程

```
引擎（scout/L3/心跳）做自动研究或修复优化
   ↓
opt-worktree.sh commit <direction> <message>
   ↓ 按方向路由
   ├─ 方向 area 与主 worktree 一致 → 提交到 auto/optimization（累积）
   └─ 方向 area 不同（大差距）→ 自动开新 worktree auto/opt-{area}-{ts}（隔离）
   ↓
opt-worktree.sh list / show <worktree>   ← 人工看 diff
   ↓ 人工回复
opt-worktree.sh merge <worktree>    （squash 合并→main + 清理）
opt-worktree.sh reject <worktree>   （拒绝 + 删 worktree，分支可恢复）
```

**安全保证**：自动优化从不直接提交 main。main 永远只由人工 `merge` 命令推进。因此引擎可以大胆跑优化、大胆改，最坏情况只是某个 worktree 被拒绝，main 不受影响。

## 方向分歧判定（2 层）

direction 格式 `area:subdirection`（修补类）或 `area:subdirection | hypothesis: <可证伪假设>`（探索类），例如：
- `engine:distillation`、`engine:scout-fix`（修补类，同 area=engine）
- `engine:explore | hypothesis: 用线上错误尾部聚类做技能因子，比等测试结果快3倍且不丢信号`（探索类）
- `moni:quant-fix`、`wanxia:pipeline`（不同 area）

> ★ v3.1：探索类 worktree 必须带 `hypothesis:`。`area_of()` 只取第一个 `:` 前，hypothesis 文本里的 `:` 不影响 area 提取；
> `.opt-direction` 存全 direction 串，`show`/`list` 天然展示 hypothesis；`merge`/`reject` 时 hypothesis 回写 `planning/explore-log.md`。

| 情况 | 判定 | 动作 |
|---|---|---|
| 新方向 area == 主 worktree area | 小差距 | 提交到主 optimization worktree（累积） |
| 新方向 area != 主 worktree area | 大差距 | 开新 worktree `auto/opt-{area}-{ts}` |
| 首次提交 | — | 建主 worktree，方向=engine:general |

这样相关优化（如多次 engine 改进）累积在一个分支便于一起审；不相关的（engine 改进 vs 某项目业务修复）隔离到各自 worktree，互不污染。

## 修补 vs 探索（★ v3.1）

worktree 分两类，路由同一套（都进 opt-worktree，不碰 main），但语义不同：

| 类别 | direction 样式 | 起源 | 合并/拒绝后 |
|---|---|---|---|
| 修补类 | `area:subdirection` | §1.5 修补榜（repair_score） | 仅审计日志（既有行为） |
| 探索类 | `area:explore \| hypothesis: ...` | §1.5 探索榜（explore_score）+ 阶段③b EXPLORE | 额外回写 `planning/explore-log.md`（verified/abandoned） |

探索类 worktree 是"研究方向的探针"——大胆起、人审决定、结论进研究档案、回写 BUSINESS-INTENT.md 假设状态。

## 命令

```bash
scripts/opt-worktree.sh <project> init                       # 建主 optimization worktree
scripts/opt-worktree.sh <project> commit <direction> <msg>   # 按方向提交（自动路由/开新）
scripts/opt-worktree.sh <project> list                       # 列所有 opt worktree + 方向 + diffstat
scripts/opt-worktree.sh <project> show [worktree]            # 给人审：看 diff（不合并）
scripts/opt-worktree.sh <project> merge <worktree>           # 人工批准：squash→main + 清理
scripts/opt-worktree.sh <project> reject <worktree>          # 人工拒绝：删 worktree
```

worktree 存在 `<project>/../.opt-worktrees/`（项目外，不污染仓库）。

## 与其他流程的关系

| 流程 | 用什么 | 场景 |
|---|---|---|
| **引擎自我优化**（研究/修复/改进引擎或基础设施） | **opt-worktree.sh**（本工作流） | 自动优化→worktree→人审合并 |
| **功能并发构建**（按 PRD 多任务并行开发） | phase-dev ④ + parallel-dispatch.sh / parallel-merge.sh | 多 agent 各 worktree 并行建功能 |
| **项目常规提交** | auto-commit.py（本地 commit，绝不 push） | 扫描 KNOWN_REPOS 变更自动 commit |

三者互补：opt-worktree 管"引擎怎么改自己/基础设施才安全"；parallel-dispatch 管"怎么并行建功能"；auto-commit 管"项目日常变更别丢"。

## 引擎接入

- L3/scout 做完自动优化后，调 `opt-worktree.sh commit <direction> <msg>`（而非直接 commit main）
  - 修补类：`direction="engine:scout-fix"` 等
  - 探索类：`direction="engine:explore | hypothesis: <可证伪假设>"`（来自阶段③b EXPLORE，必须带 hypothesis）
- 心跳汇报里带 `opt-worktree.sh list` 的摘要（待审 worktree 数 + 方向 + 是否含 hypothesis）
- 人工说"合并 X" → 引擎调 `opt-worktree.sh merge X`（探索类自动回写 explore-log）
- 人工说"拒绝 X" → 引擎调 `opt-worktree.sh reject X`（探索类自动回写 explore-log 为 abandoned）
- 新项目缺业务意图契约时，阶段① CONTEXTUALIZE 输出 P1 建议，触发 `scripts/extract-intent-sources.py` 提炼原料 → 生成 `BUSINESS-INTENT.md`

## 为什么不自动合并到 main

研究共识（Kitchen Loop / ForgeDock / "the gate is the product"）：自动合并到主干的风险是
"agent 把自己的 bug 合进 main 且难回滚"。本工作流把合并权留给人工——agent 大胆改 worktree，
人看 diff 决定，兼顾**优化吞吐**（不受人审阻塞地跑）和**主干安全**（人审才进 main）。
