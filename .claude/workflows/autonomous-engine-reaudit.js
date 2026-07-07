export const meta = {
  name: 'autonomous-engine-reaudit',
  description: 'Re-audit autonomous-engine hooks+watchdog: verify 6 prior findings fix status + hunt new real logic/security bugs (anti-churn exception)',
  phases: [
    { title: 'Audit', detail: 'one sonnet agent per file: verify prior findings + hunt new real bugs' },
    { title: 'Verify', detail: 'adversarial skeptic per finding: real logic bug or cosmetic churn?' },
  ],
}

const ROOT = '/home/admin/workspace/autonomous-engine'

const FILES = [
  {
    path: `${ROOT}/.claude/hooks/resume-checkpoint.py`,
    prior: 'AE-H-001 [HIGH]: build_engine_firmware() L121/124/135 hardcodes "E:/x-tool/.claude/..." paths + WSL-only "wsl -d Ubuntu" command. On Linux deploy, injected paths nonexistent + WSL cmd absent → engine cold-start breaks.',
  },
  {
    path: `${ROOT}/.claude/hooks/save-checkpoint.py`,
    prior: 'AE-H-002 [HIGH]: (a) find_task_files() L137 uses Path() but "from pathlib import Path" is inside main block L215 → NameError when imported / called outside main; (b) collect_recent_activity() L80-82 reads ~/.claude/audit/audit.jsonl (global Claude path, wrong format) instead of engine decision-log.jsonl → recent_activity always [] → checkpoint loses recent context.',
  },
  {
    path: `${ROOT}/.claude/watchdog.sh`,
    prior: 'AE-M-001 [MEDIUM]: L15 PROJECT_DIR="/mnt/e/x-tool" hardcoded WSL mount path. On native Linux, all $PROJECT_DIR/.claude/... paths nonexistent → L31 [ ! -f $LATEST ] exit 0 → L6 watchdog becomes no-op.',
  },
  {
    path: `${ROOT}/.claude/hooks/notify-phone.py`,
    prior: 'AE-M-002 [MEDIUM]: main() L206 calls send(title,message,reason,priority) but discards return value → notification failure (esp. confirm-level) silently lost, no log/marker.',
  },
  {
    path: `${ROOT}/.claude/hooks/decision-observer.py`,
    prior: 'AE-M-003 [MEDIUM]: handle_stop L263-288 reverse-reads last 20 lines of LOG_FILE in chunks; cross-boundary lines get split by lines[-needed:] truncation → JSON parse fail → active_project="unknown" intermittently.',
  },
  {
    path: `${ROOT}/.claude/hooks/protocol-check.py`,
    prior: 'AE-L-001 [LOW]: L70 passes dummy path os.path.join(project_dir,"dummy") to bootstrap.py — relies on bootstrap.py doing dirname extraction (implicit contract, fragile).',
  },
  {
    path: `${ROOT}/.claude/hooks/incremental-save.py`,
    prior: '(no prior finding on this file)',
  },
]

const AUDIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['file', 'prior_findings_status', 'new_findings'],
  properties: {
    file: { type: 'string' },
    prior_findings_status: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['prior_id', 'status', 'evidence'],
        properties: {
          prior_id: { type: 'string' },
          status: { type: 'string', enum: ['fixed', 'still_present', 'partially_fixed', 'not_applicable'] },
          evidence: { type: 'string', description: 'concrete file:line citation proving the status' },
        },
      },
    },
    new_findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'line', 'severity', 'category', 'finding', 'remediation', 'evidence'],
        properties: {
          id: { type: 'string', description: 'AE-NEW-NNN' },
          line: { type: 'string' },
          severity: { type: 'string', enum: ['high', 'medium', 'low', 'info'] },
          category: { type: 'string', description: 'e.g. race, injection, silent-error-swallow, credential-leak, path-traversal, assertion-failure, resource-leak' },
          finding: { type: 'string' },
          remediation: { type: 'string' },
          evidence: { type: 'string', description: 'file:line + quoted code proving it' },
        },
      },
    },
  },
}

const VERIFY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['finding_id', 'verdict', 'reasoning', 'adjusted_severity', 'is_real_logic_bug'],
  properties: {
    finding_id: { type: 'string' },
    verdict: { type: 'string', enum: ['confirmed-real', 'cosmetic-churn', 'not-exploitable', 'false-positive'] },
    reasoning: { type: 'string' },
    adjusted_severity: { type: 'string', enum: ['high', 'medium', 'low', 'info', 'reject'] },
    is_real_logic_bug: { type: 'boolean', description: 'true only if this is a real logic/security bug (race/injection/silent-swallow/cred-leak/assertion-fail), NOT cosmetic churn' },
  },
}

phase('Audit')

const auditResults = await pipeline(
  FILES,
  (f) => agent(
    `You are a deep security/logic auditor. Read the file ${f.path} in full (it is a Python hook or shell script in the "autonomous-engine" project — a self-governing Claude Code agent runtime).

CRITICAL CONSTRAINT — anti-churn rule (2026-07-03, user-mandated):
This project is the engine's OWN machinery. You may ONLY flag REAL logic/security bugs: races, injections (shell/SQL/path), silent error swallowing, credential/secret leaks, assertion failures, resource leaks, crash-bugs, data-loss bugs. Do NOT flag: cosmetic style, missing comments, constant renames, docstring gaps, header reformatting, typo fixes, "could be more pythonic", missing type hints. If a finding is cosmetic, omit it entirely. Only real bugs survive.

TASK 1 — verify prior audit findings fix status:
${f.prior}

For each prior finding cited above, read the CURRENT code and determine: fixed / still_present / partially_fixed / not_applicable. Cite concrete file:line evidence (quote the current code). The prior audit was 2026-07-01; today is 2026-07-05, so changes may have landed.

TASK 2 — hunt NEW real logic/security bugs not covered by the prior findings. For each: give id (AE-NEW-NNN), line, severity, category, finding, remediation, evidence (file:line + quoted code). Look hard for: uncaught exceptions that kill the hook silently, file races (read-then-write without atomic replace), subprocess shell=True injection, path traversal, credentials/secrets written to logs or world-readable files, JSONL corruption on concurrent writes, off-by-one in log parsing, unbounded reads, missing timeouts on network/subprocess calls, broken control flow (dead code paths, wrong conditionals), state-file schema drift.

Return structured output. Be precise and skeptical — every finding must cite real code.`,
    { label: `audit:${f.path.split('/').pop()}`, phase: 'Audit', schema: AUDIT_SCHEMA, model: 'sonnet' }
  ),
  (auditResult, f) => {
    if (!auditResult || !auditResult.new_findings || auditResult.new_findings.length === 0) {
      return { file: f.path, audit: auditResult, verified: [] }
    }
    return parallel(
      auditResult.new_findings.map((nf) => () =>
        agent(
          `You are an adversarial skeptic. Another auditor flagged this finding in the file ${f.path} (autonomous-engine project, engine's own machinery). Your job is to REFUTE it. Default to skepticism.

FINDING:
- id: ${nf.id}
- line: ${nf.line}
- severity: ${nf.severity}
- category: ${nf.category}
- finding: ${nf.finding}
- remediation: ${nf.remediation}
- evidence: ${nf.evidence}

Read ${f.path} at the cited lines. Decide:
1. Is the finding factually correct about what the code does? (read the actual code)
2. Is it a REAL logic/security bug (race / injection / silent error swallow / credential leak / assertion failure / crash / data loss) — OR is it cosmetic churn (style, comments, naming, "could be cleaner") that the 2026-07-03 anti-churn rule forbids?
3. Is it actually exploitable / does it cause real misbehavior, or is it theoretical-only?
4. Correct the severity if overstated.

Verdict options: confirmed-real (real logic bug, worth fixing) / cosmetic-churn (forbidden by anti-churn rule, reject) / not-exploitable (real but no impact, downgrade to info or reject) / false-positive (code doesn't actually do what finding claims).

Be honest — if it's cosmetic, say cosmetic-churn even if the bug is "technically true". The anti-churn rule is strict.`,
          { label: `verify:${nf.id}`, phase: 'Verify', schema: VERIFY_SCHEMA, model: 'sonnet' }
        ).then((v) => ({ finding: nf, verdict: v }))
      )
    ).then((vs) => ({ file: f.path, audit: auditResult, verified: vs.filter(Boolean) }))
  }
)

const confirmed = []
const rejected = []
for (const r of auditResults.filter(Boolean)) {
  for (const v of r.verified) {
    if (v.verdict.is_real_logic_bug && (v.verdict.verdict === 'confirmed-real' || v.verdict.verdict === 'not-exploitable')) {
      confirmed.push({ file: r.file, ...v.finding, verdict: v.verdict })
    } else {
      rejected.push({ file: r.file, ...v.finding, verdict: v.verdict })
    }
  }
}

return {
  files_audited: FILES.map((f) => f.path),
  prior_findings_status: auditResults.filter(Boolean).map((r) => ({ file: r.file, prior: r.audit?.prior_findings_status })),
  confirmed_new_findings: confirmed,
  rejected_findings: rejected.map((r) => ({ id: r.id, file: r.file, verdict: r.verdict.verdict, reason: r.verdict.reasoning })),
}
