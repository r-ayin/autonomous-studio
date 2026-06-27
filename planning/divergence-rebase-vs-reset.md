# 计划：autonomous-studio main/worktree 历史分歧裁决（rebase --onto vs reset main）

> 状态：**P0 阻塞**——阻塞所有基于 `b725eb4` 的 pending worktree 合入 main。
> 本文档只记录分析与可执行方案，**不改动任何 git 历史**（分歧既有，非本轮引入；历史改写有丢工作风险，需人工裁决后执行）。
> 创建：2026-06-27（autonomous-loop case-013）。来源：可观察 git 事实，非散文。

## 1. 事实（可观察）

common-ancestor：`f9b36aa fix(autonomous-loop): prompt 轻量化`。

从 `f9b36aa` 起，**同一组 4 个 worktree 合并**被独立重放了两次，产生两条平行历史线（提交消息相同，hash 不同）：

| 线 | 链（自 f9b36aa 起） |
|---|---|
| main | `40a69cb`(merge scout-ranking) → `74b3bf4`(chore .opt-direction) → `1f56a3a`(merge distillation) → `d18d72b`(merge opt-autonomous-studio-1782544512) → `34ac736`(merge opt-scanner-1782549266) → `34fe229`(step6 状态回写) |
| optimization | `b2bb8d9`(merge scout-ranking) → `631c5e7`(chore .opt-direction) → `901d1d3`(merge distillation) → `f2c6090`(merge opt-autonomous-studio-1782544512) → `f70b9a7`(merge opt-scanner-1782549266) → `b725eb4`(step6 状态回写) |

验证命令与结果：
- `git merge-base --is-ancestor b725eb4 main` → **NO**（分歧确认）。
- `git diff --shortstat 34fe229 b725eb4` → `1 file changed, 1 insertion(+), 2 deletions(-)`，唯一差异文件 = `SKILL.md`。
- `git diff 34fe229 b725eb4 -- SKILL.md`：main(34fe229) 含"按工作性质分档"措辞；optimization(b725eb4) 仍为旧"判断→sonnet/行动→opus"措辞。
- `git log --oneline --no-merges f9b36aa..34fe229` 含 `3c5d5a3 fix(SKILL): 模型分层原则措辞修正`；`f9b36aa..b725eb4` **不含** 3c5d5a3。

**结论**：main = optimization + 唯一额外提交 `3c5d5a3`（SKILL.md 措辞修正）。两条线的 4 个合并 + step6 + chore 在内容上等价，仅 hash 不同（重放）。

## 2. 受影响的 pending worktree

| worktree | 基线 | merge-base(main,HEAD) | 状态 |
|---|---|---|---|
| `opt-skills-1782553243`（f3efac0，3 提交：todo-triage） | `34fe229`（main 当前 HEAD） | `34fe229` | ✅ 可 ff-merge，**不阻塞** |
| `opt-scanner-1782549922`（135a67f，2 真实提交：9f2967b .venv/site-packages 忽略 + 135a67f HTML 注释占位符剥离） | `b725eb4`（optimization 线） | `f9b36aa` | ❌ 阻塞——合 main 会带入 optimization 线的重放合并历史 |
| `optimization`（b725eb4） | `b725eb4` | `f9b36aa` | ❌ 同上；但无独立新提交，仅为 opt-scanner 的基线 |

`opt-scanner-1782549922` 的真实新工作仅 2 提交（`9f2967b`/`135a67f`），是四类 scanner 虚高修复的 consolidate，价值高，须保留。

## 3. 方案对比

### 方案 A（推荐）：rebase --onto，把 opt-scanner 的 2 真实提交移植到 main
```bash
cd /home/admin/workspace/autonomous-studio
# 在 opt-scanner worktree 内，把 b725eb4 之后仅有的 2 提交重放到 main(34fe229)
git -C ../.opt-worktrees/autonomous-studio/opt-scanner-1782549922 \
  rebase --onto main b725eb4 auto/opt-scanner-1782549922
# 验证：只剩 2 真实提交在 main 之上
git -C ../.opt-worktrees/autonomous-studio/opt-scanner-1782549922 log --oneline main..HEAD
# 期望：仅 9f2967b'/135a67f'（hash 因 rebase 变，消息不变）
# 随后人工 ff-merge：bash scripts/opt-worktree.sh autonomous-studio show opt-scanner-1782549922 → 批准
```
- **安全性**：worktree 分支隔离，reflog 可回退；不动 main；`3c5d5a3`(SKILL fix) 已在 main 不会被丢；重放的 4 合并+step6 因 patch 等价被 rebase 识别为空/跳过。
- **丢工作风险**：低。仅当 9f2967b/135a67f 与 main 已有内容冲突时需人工解——但二者改的是 `scripts/scout-scan.py`，main 自 f9b36aa 起未动该文件，预期干净。
- **回退**：`git -C <wt> reset --hard 135a67f`（rebase 前 ORIG_HEAD/reflog 仍在）。

### 方案 B（不推荐）：reset main 到 b725eb4
```bash
git reset --hard b725eb4   # 在 main 上
```
- **丢工作**：会丢失 `3c5d5a3`（SKILL.md 措辞修正）+ main 线 4 个合并的 hash 身份。虽内容等价，但 main 的 reflog/已推历史会被改写。
- 若已推 origin（code.alibaba-inc.com），需 force-push，影响协作者。
- **不推荐**：方案 A 能达到同样效果（opt-scanner 可合入）且零丢失。

## 4. 建议执行顺序（人工裁决后）

1. 先合 `opt-skills-1782553243`（已 ff-able，3 提交 todo-triage，零风险）——独立工作单位，不依赖分歧解决。
2. 执行**方案 A** rebase opt-scanner，验证 `main..HEAD` 仅 2 提交且 `bash -n scripts/scout-scan.py` 通过。
3. 人工 ff-merge opt-scanner 到 main。
4. 清理 `optimization` worktree（无独立提交，仅基线）：`opt-worktree.sh autonomous-studio remove optimization`（确认无未合并工作后）。

## 5. 后续结构性收益

- 解除 P0 后，AS 所有 pending worktree 恢复 ff-mergeable，积压可逐批合入。
- 本文档创建 `planning/` 目录——同时降低 AS 在 scout-scan 的 score 驱动项"无 planning/"，打破 AS 因结构性缺文档持续霸榜 #1 的环路（与 [[autonomous-engine-self-selection-fix-2026-06-27]] 同向）。
