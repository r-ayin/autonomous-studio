# 前沿研究调研报告（research phase）

> 由 autonomous-studio 引擎的 **researching 状态** 产出（autonomous-constraints.md 指令 E）。
> 与 `.claude/audits/`（内向代码审查）互补：这里存**对外调研**——同功能开源实现 + 论文对比。

## 触发

每 `research_every`（默认 2）个审计周期完成时触发 1 次（见 `audit-cycle-state.json.research_cadence`）。
研究轮**不写代码**，只产出本报告 + `derived_fixes` 里 `kind=research-informed` 的条目；实现由后续派发轮做。

## 报告命名

`research-YYYY-MM-DD-NNN.md`（NNN 取当日已存在 research 报告数 +1）

## 报告模板

```markdown
# research-YYYY-MM-DD-NNN — <topic>

- **topic**: <研究的核心功能/问题>
- **our_current_approach**: <本项目当前怎么做的，引用 file:line>
- **degraded**: false | true（WebSearch 不可用时降级为训练知识对比）
- **started_at** / **completed_at**: ISO8601

## 对比表

| reference | type | key_idea | our_gap | applicability | effort | source_url |
|-----------|------|----------|---------|---------------|--------|------------|
| <OSS项目名/论文标题> | oss/paper | <一句话核心思路> | <本项目缺什么 file:line> | high/med/low | S/M/L | <url> |

## 高适用性发现 → derived_fixes

- **R-001**: <gap 描述>
  - source: {type: oss|paper, name: <>, url: <>, reference_idea: <>}
  - applicability: high
  - effort: M
  - derived_fix_id: <写入 audit-cycle-state 后回填>
  - our_gap_evidence: <file:line + 不足证据>
```

## 派生 fix 流转

1. 本报告里 applicability=high 的发现 → `audit-cycle-state.derived_fixes[]` 加条目（`kind=research-informed`）
2. 后续轮次按 A 节派发流程逐个派生 case（通常 direction-shift）
3. case 的 `audit_id` 写本报告 id（`research-YYYY-MM-DD-NNN`），`audit_type=research`，`audit_depth=research`
4. 全部 merged/rejected → status 改 cycle-complete → 计数器+1 → 触发下一轮审计/研究

## DO NOT（见 constraints 指令 E）

- 不直接 copy 开源代码（license）——只借鉴思路
- 不在研究轮做代码改动——只产出 report + derived_fixes
- 不为研究而研究——每个 derived fix 必须有 `our_gap` 证据
