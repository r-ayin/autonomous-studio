# Unregistered Hook Scripts — Triage Record

> Created: 2026-07-02 by autonomous engine (audit-cycle finding AS-CP-M04)
> Purpose: Document 5 hook scripts present on disk but NOT registered in `.claude/settings.json`,
>          to prevent future developers/agents from assuming they are active.

## Registration Check Methodology

Registered hooks = scripts referenced in `.claude/settings.json` under any hook event
(UserPromptSubmit / PreToolUse / PostToolUse / Stop / PreCompact / SessionStart / SessionEnd).

As of 2026-07-02, registered scripts are:
- decision-observer.py
- discovery-gate.py
- protocol-check.py
- patterns-write-gate.py
- autonomous-commit-gate.py
- pipeline-gate.py
- post-edit-lint.py
- notify-phone.py
- stop-completion-gate.py

## Unregistered Scripts (5)

| Script | Size | Last Modified | Status | Notes |
|---|---|---|---|---|
| auto-commit.py | 14KB | 2026-06-27 | DEPRECATED (functional replacement) | Referenced in OPTIMIZATION-WORKFLOW.md as "项目常规提交" tool, but opt-worktree.sh now owns all commit workflows. No settings.json registration. Keep for historical reference; do not activate without explicit re-design. |
| codegraph-sync.py | 14KB | 2026-06-27 | DORMANT | No references in active docs/tests/workflows outside .codebase-index JSON caches. Likely superseded by .codebase-index/ rebuild logic in scout-scan.py. Candidate for deletion after confirming no external consumers. |
| incremental-save.py | 3.3KB | 2026-06-27 | DORMANT (misleading GATES.md claim) | GATES.md historically listed this as "core hook" but it was NEVER registered in settings.json. No runtime invocation path. Either register formally or remove from GATES.md critical list. |
| resume-checkpoint.py | 9KB | 2026-06-27 | DORMANT (design artifact) | Tested in x-tool/tests/test_checkpoint_hooks.py as design intent, but never wired into settings.json. Part of unfinished checkpoint/resume subsystem. Keep until checkpoint feature is formally shipped or abandoned. |
| save-checkpoint.py | 7.6KB | 2026-06-27 | DORMANT (design artifact) | Same as resume-checkpoint.py — tested but unregistered. Pair with resume-checkpoint; same disposition. |

## Recommended Actions (not yet executed — requires owner decision)

1. **auto-commit.py**: Add deprecation header comment; update OPTIMIZATION-WORKFLOW.md to note opt-worktree.sh replacement.
2. **codegraph-sync.py**: Verify no external consumers → delete if confirmed orphaned.
3. **incremental-save.py**: Remove from GATES.md critical hook list (already corrected in parallel fix). Decide whether to implement or delete.
4. **resume-checkpoint.py + save-checkpoint.py**: Track in structural-debt.md as "unfinished checkpoint subsystem". Either ship (register in settings.json + add tests) or archive/delete with x-tool test updates.

## Why Not Delete Immediately?

- These scripts may be referenced in external documentation, training materials, or future feature plans.
- Deletion is irreversible; marking as UNREGISTERED + documenting status is the safe intermediate step.
- Audit trail preserved: finding AS-CP-M04 → this document → future disposition case.
