/**
 * task-client.js — HTTP client wrapping AgentTask REST API.
 *
 * Replaces local SQLite operations with HTTP calls to aone-agent-server.
 * API base URL is read from process.env.DEVOUT_SERVER_URL.
 */

// ─── Internal helpers ────────────────────────────────────────────────────────

/**
 * Default hostname allowlist for DEVOUT_SERVER_URL.
 * getHeaders() attaches the deploy token (CODE_PRIVATE_TOKEN / DEVOUT_TOKEN) to
 * every request. Without an allowlist, a misconfigured, typo'd, or DNS-rebinding
 * DEVOUT_SERVER_URL would silently leak that token to an attacker-controlled host.
 * Allowed by default: loopback + internal *.alibaba-inc.com. Extend at runtime
 * via DEVOUT_ALLOWED_HOSTS (comma-separated, e.g. "deploy.internal,10.0.0.5").
 * IP literals are rejected unless explicitly listed (SSRF / metadata-service guard).
 *
 * Audit reference: audit-2026-07-06-001 PD-TOKEN-01-LIVE (route-fix, LIVE copy).
 */
const DEFAULT_ALLOWED_HOSTS = ['localhost', '127.0.0.1', '::1', '*.alibaba-inc.com'];

function getAllowedHosts() {
  const extra = (process.env.DEVOUT_ALLOWED_HOSTS || '')
    .split(',')
    .map(h => h.trim().toLowerCase())
    .filter(Boolean);
  const seen = new Set(DEFAULT_ALLOWED_HOSTS);
  const merged = [...DEFAULT_ALLOWED_HOSTS];
  for (const h of extra) {
    if (!seen.has(h)) {
      seen.add(h);
      merged.push(h);
    }
  }
  return merged;
}

/** True if hostname looks like a raw IP literal (IPv4 dotted-quad or IPv6). */
function looksLikeIpLiteral(hostname) {
  if (/^(\d{1,3}\.){3}\d{1,3}$/.test(hostname)) return true; // IPv4
  if (hostname.includes(':') && /^[0-9a-f:]+$/i.test(hostname)) return true; // IPv6
  return false;
}

function isAllowedHost(hostname) {
  const host = String(hostname || '').toLowerCase();
  if (!host) return false;
  const rules = getAllowedHosts();
  if (looksLikeIpLiteral(host)) {
    // IP literals never match wildcards — must be an exact, non-wildcard rule.
    return rules.some(r => !r.startsWith('*.') && r === host);
  }
  return rules.some(rule => {
    if (rule.startsWith('*.')) {
      const dotSuffix = rule.slice(1); // ".alibaba-inc.com"
      return host.endsWith(dotSuffix) || host === rule.slice(2);
    }
    return rule === host;
  });
}

function getBaseUrl() {
  const url = process.env.DEVOUT_SERVER_URL;
  if (!url) {
    throw new Error('DEVOUT_SERVER_URL not set');
  }
  let parsed;
  try {
    parsed = new URL(url);
  } catch (err) {
    throw new Error(`DEVOUT_SERVER_URL is not a valid URL: ${url}`);
  }
  // Node's URL.hostname returns IPv6 literals wrapped in brackets ([::1]); strip
  // them so the IPv6 pattern in looksLikeIpLiteral matches and the bare address
  // can be compared against the allowlist (e.g. "::1").
  const host = parsed.hostname.toLowerCase().replace(/^\[|\]$/g, '');
  if (!isAllowedHost(host)) {
    throw new Error(
      `DEVOUT_SERVER_URL host '${host}' is not in the allowlist. ` +
      `Allowed: ${getAllowedHosts().join(', ')}. ` +
      `To permit this host, set DEVOUT_ALLOWED_HOSTS (comma-separated). ` +
      `Refusing to send deploy token to an unverified host ` +
      `(audit-2026-07-06-001 PD-TOKEN-01-LIVE).`
    );
  }
  return url.replace(/\/$/, '');
}

function getHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (process.env.CODE_PRIVATE_TOKEN) {
    headers['X-Agent-Authorization'] = `Code ${process.env.CODE_PRIVATE_TOKEN}`;
  } else if (process.env.DEVOUT_TOKEN) {
    headers['token'] = process.env.DEVOUT_TOKEN;
  }
  return headers;
}

/**
 * Default HTTP request timeout in milliseconds.
 * Prevents fetch() from hanging indefinitely when DEVOUT_SERVER_URL is
 * unresponsive — without this, every task-client call (used by report-event,
 * resume-next-batch, complete-task, poll-build, poll-pre-check) can block
 * forever with no error. Can be overridden via DEVOUT_HTTP_TIMEOUT_MS env var.
 * Audit reference: audit-2026-07-06-001 finding PD-HANG-01.
 */
const DEFAULT_TIMEOUT_MS = Number(process.env.DEVOUT_HTTP_TIMEOUT_MS) || 30000;

/**
 * fetch() wrapper with an AbortController-based timeout.
 * Aborts after DEFAULT_TIMEOUT_MS and raises a typed timeout error so callers
 * see a clear failure instead of an indefinite hang.
 */
async function fetchWithTimeout(url, init) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (err) {
    if (err && err.name === 'AbortError') {
      throw new Error(`${init.method || 'GET'} ${url} timed out after ${DEFAULT_TIMEOUT_MS}ms`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

const API_PREFIX = '/api/v1/agent/tasks';

async function apiGet(path) {
  const url = `${getBaseUrl()}${path}`;
  const res = await fetchWithTimeout(url, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (res.status === 404) {
    return null;
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`GET ${url} failed with status ${res.status}: ${text}`);
  }
  return res.json();
}

async function apiPost(path, body) {
  const url = `${getBaseUrl()}${path}`;
  const res = await fetchWithTimeout(url, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`POST ${url} failed with status ${res.status}: ${text}`);
  }
  return res.json();
}

async function apiPut(path, body) {
  const url = `${getBaseUrl()}${path}`;
  const res = await fetchWithTimeout(url, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`PUT ${url} failed with status ${res.status}: ${text}`);
  }
  return res.json();
}

// ─── Exported API ────────────────────────────────────────────────────────────

/**
 * createTask({ taskId, taskType, orgId, workitemId, operator, sessionId, input })
 *
 * Creates an agent task record. `input` is a JSON string with caller-defined structure.
 * Returns the created task object (snake_case fields).
 */
export async function createTask({ taskId, taskType, orgId, workitemId, operator, sessionId, input }) {
  const body = { task_type: taskType };
  if (taskId) body.task_id = taskId;
  if (orgId) body.org_id = orgId;
  if (workitemId) body.workitem_id = workitemId;
  if (operator) body.operator = operator;
  if (sessionId) body.session_id = sessionId;
  if (input != null) body.input = typeof input === 'string' ? input : JSON.stringify(input);

  const resp = await apiPost(API_PREFIX, body);
  return resp.data ?? null;
}

/**
 * getTask(taskId)
 *
 * Fetches a task by its task_id.
 * Returns the task object (snake_case fields) or null if not found.
 */
export async function getTask(taskId) {
  const resp = await apiGet(`${API_PREFIX}/${encodeURIComponent(taskId)}`);
  if (!resp) return null;
  return resp.data ?? null;
}

/**
 * updateTask(taskId, fields)
 *
 * Selectively updates task fields.
 * Server automatically sets started_at/completed_at on status transitions.
 *
 * @param {string} taskId
 * @param {object} fields  { status, output, error_message }
 * @returns {object|null}  Updated task object
 */
export async function updateTask(taskId, fields) {
  const body = {};
  if (fields.status != null) body.status = fields.status;
  if (fields.output !== undefined) body.output = typeof fields.output === 'string' ? fields.output : JSON.stringify(fields.output);
  if (fields.error_message !== undefined) body.error_message = fields.error_message;

  const resp = await apiPut(`${API_PREFIX}/${encodeURIComponent(taskId)}`, body);
  return resp.data ?? null;
}

/**
 * queryTasks({ taskIds, taskType, orgId, workitemId, status, sessionId, operator, pageNum, pageSize })
 *
 * Query tasks with filters. Returns { items, total }.
 */
export async function queryTasks({ taskIds, taskType, orgId, workitemId, status, sessionId, operator, pageNum, pageSize } = {}) {
  const body = {};
  if (taskIds) body.task_ids = taskIds;
  if (taskType) body.task_type = taskType;
  if (orgId) body.org_id = orgId;
  if (workitemId) body.workitem_id = workitemId;
  if (status) body.status = status;
  if (sessionId) body.session_id = sessionId;
  if (operator) body.operator = operator;
  if (pageNum != null) body.page_num = pageNum;
  if (pageSize != null) body.page_size = pageSize;

  const resp = await apiPost(`${API_PREFIX}/query`, body);
  return {
    items: resp.data ?? [],
    total: resp.total ?? 0,
  };
}
