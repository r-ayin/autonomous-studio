# Decision Case Schema v1.0

> 自主决策引擎的 JSON 案例格式规范。每个案例是一个 `.claude/decisions/case-YYYY-MM-DD-NNN.json` 文件。

## JSON Schema

```json
{
  "$schema": "x-tool-decision-case/1.0",

  "id": "case-2026-06-15-001",
  "timestamp": "2026-06-15T14:30:00Z",
  "session_id": "abc123...",

  "trigger": {
    "type": "user_initiated | autonomous_wakeup | cron_heartbeat | pattern_recognition",
    "classification": "plan | code | debug | review | meta | question | feedback | chat",
    "context": "决策触发时的上下文简述"
  },

  "decision": {
    "summary": "一行决策描述",
    "domain": "architecture | implementation | tooling | workflow | dependency | testing | deployment | configuration",
    "phase": "stage_0_planning | stage_1_coding | stage_2_quality | stage_3_autonomous | stage_4_delivery",
    "project": "wanxia | xia | douyin | moni | pachong-master | tolaria | infrastructure | cross_project",
    "action_taken": "实际执行了什么",
    "alternatives_considered": [
      {"option": "备选方案 A", "why_rejected": "不选的原因"}
    ],
    "rationale": "为什么这样做——完整的决策理由"
  },

  "pattern": {
    "pattern_type": "exact_repeat | similar_situation | novel_situation",
    "matched_case_ids": [],
    "match_strength": 0.0,
    "pattern_signature": "可哈希的模式指纹（用于快速匹配）"
  },

  "research": {
    "queries_performed": [],
    "key_findings": [],
    "sources": [],
    "methodology_alignment": "TDD | BDD | CI/CD | GitOps | Agile | XP | Lean | DevOps | ..."
  },

  "confidence": {
    "total_score": 0,
    "breakdown": {
      "pattern_match": 0,
      "web_corroboration": 0,
      "risk_assessment": 0,
      "user_preference_alignment": 0
    },
    "level": "observe | suggest | prepare | act_notify | act_silent",
    "autonomous_action_permitted": false
  },

  "outcome": {
    "status": "pending_verification | succeeded | failed | rolled_back | superseded",
    "user_feedback": "用户反馈（如有）",
    "verification_method": "如何验证决策正确性",
    "lessons_learned": []
  },

  "links": {
    "related_cases": [],
    "checkpoint_ref": "",
    "memory_refs": [],
    "project_files_changed": []
  },

  "evolution": {
    "created_at": "ISO8601",
    "updated_at": "ISO8601",
    "history": []
  }
}
```

## 字段说明

### trigger（触发器）
- `type`: 谁触发了这个决策
  - `user_initiated` — 用户直接提出的请求
  - `autonomous_wakeup` — ScheduleWakeup 触发的自主检查
  - `cron_heartbeat` — CronCreate 定时心跳
  - `pattern_recognition` — 引擎从日志中识别出的模式
- `classification`: 用户输入类型（仅 user_initiated 时有意义）

### decision（决策内容）
- `domain`: 决策所属领域
- `phase`: 对应的开发阶段
- `action_taken`: 实际做了什么（不是计划做什么）
- `rationale`: 完整的 WHY，不是 WHAT

### pattern（模式匹配）
- `pattern_signature`: 用于快速查找相似案例的指纹
  - 格式: `{domain}:{classification}:{project}:{关键词哈希}`
  - 示例: `implementation:debug:pachong-master:hash_simhash_overflow`

### confidence（信心评分）
- 四个维度各 0-25 分，总分 0-100
- `level` 映射: 0-30→observe, 31-50→suggest, 51-70→prepare, 71-85→act_notify, 86-100→act_silent

### outcome（结果）
- `status`: 决策的最终状态
- `lessons_learned`: 可复用的经验（最重要！这是引擎学习的核心数据）

## 文件命名规范
- 格式: `case-YYYY-MM-DD-NNN.json`
- NNN: 当天 3 位序号（001-999），每天重置
- 排序: 自然按名称排序即为时间顺序

## 与 decision-archive.md 的关系
- JSON 案例 = 机器优化存储（快速匹配、模式识别）
- decision-archive.md = 人类可读汇总（定期从 JSON 案例重新生成）
