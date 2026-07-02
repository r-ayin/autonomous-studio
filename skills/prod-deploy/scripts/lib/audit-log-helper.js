/**
 * audit-log-helper.js — Append-only JSONL audit logger for prod-deploy skill.
 *
 * DO B compliance (autonomous-constraints.md): deploy/release/CR/pipeline-trigger
 * are sensitive paths requiring audit-log instrumentation per audit-log.schema.json.
 *
 * Writes to: skills/prod-deploy/.audit/audit-YYYY-MM-DD.jsonl
 * Format: one JSON object per line, append-only, no DB / no external system.
 * userId fixed to "engine" (autonomous agent); ip fixed to "local" (no network context).
 *
 * Fail-safe: logging errors never throw; they print to stderr and return silently.
 * Audit is observability, not control flow.
 */

import { appendFileSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomBytes } from 'node:crypto';

const __dirname = dirname(fileURLToPath(import.meta.url));
const AUDIT_DIR = join(__dirname, '..', '.audit');

/**
 * Generate audit event ID: audit-{YYYYMMDD}-{HHmmss}-{rand6}
 * Matches schema pattern: ^audit-\d{8}-\d{6}-[a-zA-Z0-9]{6}$
 */
function generateAuditId() {
  const now = new Date();
  const pad = (n, len = 2) => String(n).padStart(len, '0');
  const datePart = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`;
  const timePart = `${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
  const rand = randomBytes(3).toString('hex').slice(0, 6);
  return `audit-${datePart}-${timePart}-${rand}`;
}

/**
 * Map prod-deploy actions to schema action enum + sensitivity level.
 * See .claude/decisions/audit-log.schema.json for valid actions.
 */
const ACTION_MAP = {
  'deploy-complete':    { action: 'deploy',             sensitiveLevel: 'critical' },
  'pipeline-triggered': { action: 'pipeline_trigger',   sensitiveLevel: 'high' },
  'batch-deploy-start': { action: 'deploy',             sensitiveLevel: 'critical' },
  'cr-created':         { action: 'create',             sensitiveLevel: 'medium' },
  'pre-check-start':    { action: 'compliance_check',   sensitiveLevel: 'medium' },
};

/**
 * Write one audit log entry.
 *
 * @param {Object} opts
 * @param {string} opts.auditAction - Key in ACTION_MAP (e.g. 'deploy-complete')
 * @param {string} opts.resourceType - Schema resource.type enum value
 * @param {string} opts.resourceId - Identifier (task-id, pipeline-id, etc.)
 * @param {string} opts.result - 'success' | 'failure' | 'denied' | 'timeout' | 'partial'
 * @param {Object} [opts.details] - Optional details (reason, errorMessage, duration, etc.)
 * @param {Object} [opts.metadata] - Optional metadata (tags, sessionId, etc.)
 * @returns {void} Never throws; logs errors to stderr.
 */
export function writeAuditLog({ auditAction, resourceType, resourceId, result, details, metadata }) {
  try {
    const mapping = ACTION_MAP[auditAction];
    if (!mapping) {
      process.stderr.write(`[audit-log] WARN: unknown auditAction '${auditAction}', skipping\n`);
      return;
    }

    mkdirSync(AUDIT_DIR, { recursive: true });

    const now = new Date();
    const dateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    const logFile = join(AUDIT_DIR, `audit-${dateStr}.jsonl`);

    const entry = {
      id: generateAuditId(),
      timestamp: now.toISOString(),
      userId: 'engine',
      userRole: 'engine',
      action: mapping.action,
      resource: {
        type: resourceType,
        identifier: String(resourceId ?? 'unknown'),
      },
      result: result || 'success',
      ip: 'local',
      sensitive: mapping.sensitiveLevel !== 'none',
      sensitiveLevel: mapping.sensitiveLevel,
    };

    if (details && Object.keys(details).length > 0) {
      entry.details = details;
    }
    if (metadata && Object.keys(metadata).length > 0) {
      entry.metadata = metadata;
    }

    appendFileSync(logFile, JSON.stringify(entry) + '\n', 'utf8');
  } catch (err) {
    // Fail-safe: audit errors must never break deployment flow
    process.stderr.write(`[audit-log] ERROR: ${err.message}\n`);
  }
}
