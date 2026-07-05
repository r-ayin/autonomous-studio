/**
 * sunfire-client.js — Query Sunfire DeployObserve API for deploy insight results.
 *
 * Calls Sunfire's `DeployObserve.getDeployInsightResults` via the dispatcher API
 * to retrieve anomaly data during batch observation periods.
 *
 * Environment variables:
 *   SUNFIRE_ACCESS_ID  — Sunfire OpenAPI accessKeyId
 *   SUNFIRE_SECRET_KEY — Sunfire OpenAPI secretKey (for HMAC-SHA1 signing)
 */

import crypto from 'crypto';
import https from 'https';

const SUNFIRE_URL = 'https://api.x.alibaba-inc.com/api/dispatcher.do';

/**
 * Default HTTP request timeout in milliseconds for Sunfire API calls.
 * Prevents https.request from hanging indefinitely when the Sunfire dispatcher
 * is unresponsive (TCP stall / slowloris) — without this, report-observation
 * ticks block forever with no error, stalling batch progression.
 * Can be overridden via SUNFIRE_HTTP_TIMEOUT_MS env var for testing / slow networks.
 * Audit reference: audit-2026-07-06-001 finding PD-HANG-01.
 */
const DEFAULT_TIMEOUT_MS = Number(process.env.SUNFIRE_HTTP_TIMEOUT_MS) || 30000;

// ─── Auth / Transport ──────────────────────────────────────────────────────

/**
 * Build HMAC-SHA1 signature for Sunfire OpenAPI.
 * Sign string = sorted key=value pairs joined by '&'.
 * Signature = hex(HMAC-SHA1(secretKey, signString)).
 */
export function buildSunfireSignature(params, secretKey) {
  const sortedStr = Object.keys(params)
    .sort()
    .map((k) => `${k}=${params[k]}`)
    .join('&');
  return crypto.createHmac('sha1', secretKey).update(sortedStr).digest('hex');
}

function httpPost(url, body) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const options = {
      hostname: parsed.hostname,
      port: parsed.port || 443,
      path: parsed.pathname + parsed.search,
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(body),
      },
    };
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => resolve(data));
    });
    // Abort the request if the server stops responding within the timeout.
    // req.setTimeout fires on socket inactivity; destroy() rejects the promise
    // via the 'error' handler so querySunfireInsights can degrade to skipped.
    req.setTimeout(DEFAULT_TIMEOUT_MS, () => {
      req.destroy(new Error(`Sunfire httpPost timed out after ${DEFAULT_TIMEOUT_MS}ms`));
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

// ─── Sunfire API ───────────────────────────────────────────────────────────

/**
 * Query Sunfire DeployObserve.getDeployInsightResults.
 *
 * @param {object}  opts
 * @param {string}  opts.appName    — Application name
 * @param {number}  opts.startTime  — Start time in epoch milliseconds
 * @param {number}  opts.endTime    — End time in epoch milliseconds
 * @returns {Promise<{skipped: boolean, items?: Array, reason?: string}>}
 */
export async function querySunfireInsights({ appName, startTime, endTime }) {
  const accessKeyId = process.env.SUNFIRE_ACCESS_ID;
  const secretKey = process.env.SUNFIRE_SECRET_KEY;

  if (!accessKeyId || !secretKey) {
    return { skipped: true, reason: 'SUNFIRE_ACCESS_ID or SUNFIRE_SECRET_KEY not configured' };
  }

  const params = {
    accessKeyId,
    timestamp: String(Date.now()),
    signatureVersion: '2',
    action: 'DeployObserve.getDeployInsightResults',
    appName,
    resourceList: 'DEPLOY',
    statusList: 'WARNING,RECOVER',
    startTime: String(startTime),
    endTime: String(endTime),
  };

  const signature = buildSunfireSignature(params, secretKey);
  params.signature = signature;

  const body = Object.keys(params)
    .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`)
    .join('&');

  try {
    const raw = await httpPost(SUNFIRE_URL, body);
    const json = JSON.parse(raw);
    if (!json.success) {
      return { skipped: true, reason: `Sunfire API error: ${json.code || json.message || 'unknown'}` };
    }
    return { skipped: false, items: json.data || [] };
  } catch (err) {
    return { skipped: true, reason: `Sunfire request failed: ${err.message}` };
  }
}

// ─── Result Interpretation ─────────────────────────────────────────────────

/**
 * Build the `observation_result` object that gets stored in the deploy_batch
 * event payload and read by the backend's extractObservationDetail().
 *
 * Backend reads `observation_result.checks[]` and expects each item to carry
 * the FULL set of Sunfire AppInsightExceptionDataDTO fields so it can:
 *   1. Build rawItems (preserving every field)
 *   2. Dedup by insightRule (last status wins: RECOVER→passed, WARNING→failed)
 *   3. Map insightRule → displayName/type/metricType via InsightRuleMapping
 *
 * Fields read by backend per check item:
 *   id, insightRule, insightInfo, insightLevel, metric, status,
 *   appName, appGroup, detail, value, timestamp, version, resource
 *
 * @param {Array}   items    — Raw Sunfire API response items
 * @param {string}  [analysis] — Optional LLM analysis text
 * @returns {object} — { checked_at, checks, analysis? }
 */
export function buildObservationResult(items, analysis) {
  const checks = (items || []).map((item) => ({
    id: item.id ?? null,
    insightRule: item.insightRule || '',
    insightInfo: item.insightInfo || '',
    insightLevel: item.insightLevel || '',
    metric: item.metric || '',
    status: item.status || '',             // "WARNING" or "RECOVER" — backend maps these
    appName: item.appName || '',
    appGroup: item.appGroup || '',
    detail: item.detail || '',
    value: item.value != null ? String(item.value) : '',
    timestamp: item.timestamp != null ? String(item.timestamp) : '',
    version: item.version || '',
    resource: item.resource || '',
  }));

  const result = {
    checked_at: new Date().toISOString(),
    checks,
  };

  if (analysis) {
    result.analysis = analysis;
  }

  return result;
}

/**
 * Derive a conclusion from raw Sunfire items (same logic as old interpretSunfireResults).
 *
 * - Any HIGH-level WARNING → "failed"
 * - Any WARNING (no HIGH) → "warning"
 * - All RECOVER or empty → "passed"
 *
 * @param {Array} checks — observation_result.checks array (raw Sunfire items)
 * @returns {string} "passed" | "warning" | "failed"
 */
export function deriveConclusion(checks) {
  if (!checks || checks.length === 0) return 'passed';

  // Dedup by insightRule, keeping the last (newest) status per rule
  const byRule = new Map();
  for (const c of checks) {
    if (c.insightRule) {
      byRule.set(c.insightRule, c);
    }
  }
  const deduped = byRule.size > 0 ? [...byRule.values()] : checks;

  const hasHighWarning = deduped.some(
    (c) => c.insightLevel === 'HIGH' && c.status === 'WARNING',
  );
  const hasAnyWarning = deduped.some((c) => c.status === 'WARNING');

  if (hasHighWarning) return 'failed';
  if (hasAnyWarning) return 'warning';
  return 'passed';
}
