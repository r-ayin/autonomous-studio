# PIPELINE-GATE — studio 管线强制（hook+脚本，不可协商）

> 解决"模型自身约束太软，新需求不走管线、任务状态不更新"问题。
> 原则同 autonomous-studio：**提示词不是护栏，hook 阻断不可协商**。但留小修直放通道。

## 机制
每个 studio 项目（含 `planning/status.json`）改动前必须先 triage，写 `<project>/.pipeline/current.json`。
`pipeline-gate.py` hook 据此放行/阻断。

## triage（scripts/triage.py）
```bash
python3 scripts/triage.py --kind small --desc "修拼写"      # 小修:直接 development,可改可提交
python3 scripts/triage.py --kind complex --desc "加日历"    # 复杂:stage=requirement,须走管线
python3 scripts/triage.py --stage prd                       # 推进:requirement→prd→development→verify→done(仅前进)
python3 scripts/triage.py --verify-passed                   # complex 提交前须标记
python3 scripts/triage.py --done                            # 收尾归档到 .pipeline/history/
python3 scripts/triage.py --show                            # 查看当前
```

## hook 强制规则（.claude/hooks/pipeline-gate.py）
| 事件 | 条件 | 结果 |
|---|---|---|
| Edit/Write 项目代码 | 无 current.json | **阻断**：先 triage |
| Edit/Write 项目代码 | complex 且 stage∉{development,verify} | **阻断**：先到 development（走完 PRD） |
| Edit/Write 项目代码 | small 或 complex∈{development,verify} | 放行 |
| Edit/Write 文档/planning/.pipeline | — | 放行（PRD/status 等可改） |
| git commit/push | 无 current.json | **阻断**：先 triage |
| git commit/push | complex 且 verify_passed=false | **阻断**：先 verify |
| git commit/push | small 但 diff 超规模(files>3 或 +行>50) | **阻断**：升级 complex 重 triage |
| git commit/push | small 小 diff / complex 已 verify | 放行 |
| Stop | current.stage≠done | 提醒收尾 |

## 小修 vs 复杂（判断）
- **small**：typo、单文件小 bug、配置 tweak、文档润色——直接 `--kind small` 改完提交。
- **complex**：新功能、多文件、架构改动、新需求——`--kind complex` 走 requirement→prd→development→verify→done。
- 防偷懒：小修 triage 但 diff 超规模 → hook 自动升级阻断，强制走 complex 管线。

## 仍为软约束（诚实交代）
- triage 的 small/complex 判断本身是模型判断（hook 不能读心）；但一旦声明 complex，阶段+verify 硬强制。
- harness TaskList 无法被 hook 读取，故"任务状态更新"靠 `.pipeline/current.json` + history 审计 + Stop 提醒兜底，非硬阻断。
- 非 studio 项目（无 planning/status.json）不受此 gate 约束。
