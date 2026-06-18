# Phase 1: 准备变更单

## 有 cr-id

确认状态为 `DEVELOPING`，否则处理：
- `PREINTG`/`TEST` → `a1 app cr unsubmit <cr-id>`
- `INTG` → `a1 app cr quit <cr-id> --pipeline-id <pipeline-id>`
- `CLOSED` → 终止

## 无 cr-id

```bash
a1 app cr create "发布描述" --existing-branch <branch> --app <app>
```
