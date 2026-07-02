/**
 * task-client.js — HTTP client wrapping AgentTask REST API.
 *
 * Replaces local SQLite operations with HTTP calls to aone-agent-server.
 * API base URL is read from process.env.DEVOUT_SERVER_URL.
 */

// ─── Internal helpers ────────────────────────────────────────────────────────

/**
 * Default HTTP request timeout in milliseconds.
 * Prevents fetch() from hanging indefinitely when the server is unresponsive.
 * Can be overridden via DEVOUT_HTTP_TIMEOUT_MS env var for testing / slow networks.
 * Added by audit-2026-07-02-006 findings H-001 / H-002 (HTTP clients without timeout).
 */
const DEFAULT_TIMEOUT_MS = Number(process.env.DEVOUT_HTTP_TIMEOUT_MS) || 30000;

function getBaseUrl() {
  const url = process.env.DEVOUT_SERVER_URL;
  if (!url) {
    throw new Error('DEVOUT_SERVER_URL not set');
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

const API_PREFIX = '/api/v1/agent/tasks';

async function apiGet(path) {
  const url = `${getBaseUrl()}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: getHeaders(),
      signal: controller.signal,
    });
    if (res.status === 404) {
      return null;
    }
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`GET ${url} failed with status ${res.status}: ${text}`);
    }
    return res.json();
  } catch (err) {
    if (err && err.name === 'AbortError') {
      throw new Error(`GET ${url} timed out after ${DEFAULT_TIMEOUT_MS}ms`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

async function apiPost(path, body) {
  const url = `${getBaseUrl()}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`POST ${url} failed with status ${res.status}: ${text}`);
    }
    return res.json();
  } catch (err) {
    if (err && err.name === 'AbortError') {
      throw new Error(`POST ${url} timed out after ${DEFAULT_TIMEOUT_MS}ms`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

async function apiPut(path, body) {
  const url = `${getBaseUrl()}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      method: 'PUT',
      headers: getHeaders(),
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`PUT ${url} failed with status ${res.status}: ${text}`);
    }
    return res.json();
  } catch (err) {
    if (err && err.name === 'AbortError') {
      throw new Error(`PUT ${url} timed out after ${DEFAULT_TIMEOUT_MS}ms`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
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
