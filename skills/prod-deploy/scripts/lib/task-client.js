/**
 * task-client.js — HTTP client wrapping AgentTask REST API.
 *
 * Replaces local SQLite operations with HTTP calls to aone-agent-server.
 * API base URL is read from process.env.DEVOUT_SERVER_URL.
 *
 * Shared HTTP helpers (getBaseUrl/getHeaders/apiGet/apiPost/apiPut) live in
 * ./http-base.js — extracted per audit-2026-07-02-006 finding L-001.
 * Timeout logic preserved from H-001 / H-002 fixes.
 */

import { apiGet, apiPost, apiPut } from './http-base.js';

const API_PREFIX = '/api/v1/agent/tasks';

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
