/**
 * event-client.js — HTTP client wrapping TaskEventController REST API.
 *
 * Replaces local SQLite operations with HTTP calls to aone-agent-server.
 * API base URL is read from process.env.DEVOUT_SERVER_URL.
 *
 * All functions use scene="DEPLOY" and operate on deploy task events.
 */

const TERMINAL_STATUSES = new Set(['SUCCESS', 'FAILED']);

// ─── Internal helpers ────────────────────────────────────────────────────────

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

async function apiPost(path, body) {
  const url = `${getBaseUrl()}${path}`;
  const res = await fetch(url, {
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
  const res = await fetch(url, {
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

/**
 * Deserialize a raw event from the server (payload is a JSON string → object).
 */
function deserializeEvent(raw) {
  if (!raw) return null;
  return {
    ...raw,
    payload: raw.payload ? JSON.parse(raw.payload) : {},
  };
}

/**
 * Serialize payload object → JSON string for the wire format.
 */
function serializePayload(payload) {
  return payload != null ? JSON.stringify(payload) : null;
}

/**
 * Extract items from the server response.
 * Handles both { data: [...] } and { data: { items: [...], total: N } }.
 */
function extractItems(resp) {
  return resp.data?.items ?? resp.data ?? [];
}

// ─── Exported API ────────────────────────────────────────────────────────────

/**
 * findEvent(taskId, eventType)
 *
 * Queries for events matching taskId + eventType.
 * Returns the first result deserialized (payload as object), or null.
 */
export async function findEvent(taskId, eventType) {
  const resp = await apiPost('/api/v1/sre/task-events/query', {
    task_ids: [taskId],
    scene: 'DEPLOY',
    event_type: eventType,
  });
  const items = extractItems(resp);
  return items.length > 0 ? deserializeEvent(items[0]) : null;
}

/**
 * findBatchEvent(taskId, batchIndex)
 *
 * Queries all deploy_batch events for taskId, then filters client-side
 * by payload.batch_index === batchIndex.
 * Returns the matching event (payload as object) or null.
 */
export async function findBatchEvent(taskId, batchIndex) {
  const resp = await apiPost('/api/v1/sre/task-events/query', {
    task_ids: [taskId],
    scene: 'DEPLOY',
    event_type: 'deploy_batch',
  });
  const items = extractItems(resp);
  const match = items.find(raw => {
    const payload = raw.payload ? JSON.parse(raw.payload) : {};
    return payload.batch_index === batchIndex;
  });
  return match ? deserializeEvent(match) : null;
}

/**
 * createEvent(taskId, eventType, payload, refId, initialStatus)
 *
 * Creates a single event with scene="DEPLOY".
 * Returns the created event with payload deserialized as an object.
 *
 * @param {string} taskId
 * @param {string} eventType
 * @param {object} payload
 * @param {string|null} refId
 * @param {string} [initialStatus="RUNNING"]
 */
export async function createEvent(taskId, eventType, payload, refId, initialStatus) {
  const event = {
    task_id: taskId,
    scene: 'DEPLOY',
    event_type: eventType,
    status: initialStatus || 'RUNNING',
    payload: serializePayload(payload),
  };
  if (refId != null) {
    event.ref_id = refId;
  }
  if (process.env.DEVOUT_DELEGATOR) {
    event.delegator = process.env.DEVOUT_DELEGATOR;
  }

  const resp = await apiPost('/api/v1/sre/task-events', [event]);
  const items = extractItems(resp);
  return items.length > 0 ? deserializeEvent(items[0]) : null;
}

/**
 * queryEvents(taskId, { eventType, status, limit })
 *
 * Queries events for a given taskId with optional filters.
 * Returns an array of deserialized events (payload as object).
 *
 * @param {string} taskId
 * @param {object} [options]
 * @param {string} [options.eventType]
 * @param {string} [options.status]
 * @param {number} [options.limit]
 * @returns {object[]}
 */
export async function queryEvents(taskId, { eventType, status, limit } = {}) {
  const body = { task_ids: [taskId], scene: 'DEPLOY', page_size: limit || 50 };
  if (eventType) body.event_type = eventType;
  if (status) body.status = status;
  const resp = await apiPost('/api/v1/sre/task-events/query', body);
  const items = extractItems(resp);
  return items.map(deserializeEvent);
}

/**
 * updateEvent(existingEvent, status, newPayloadFields)
 *
 * Merges newPayloadFields into the existing event's payload client-side,
 * then sends a batch PUT to update status and/or payload.
 *
 * Returns null (without calling the API) if the event is already in a
 * terminal status (SUCCESS or FAILED).
 *
 * @param {object} existingEvent  Full event object as returned by findEvent/createEvent
 * @param {string|null} status    New status, or null to keep current status
 * @param {object|null} newPayloadFields  Fields to merge into existing payload
 * @returns {object|null}  Updated event with payload as object, or null if terminal
 */
export async function updateEvent(existingEvent, status, newPayloadFields) {
  if (!existingEvent) return null;
  if (TERMINAL_STATUSES.has(existingEvent.status)) {
    // Allow payload-only updates on terminal events (e.g. observation_result after SUCCESS)
    if (!newPayloadFields || status) {
      return null;
    }
  }

  const existingPayload = existingEvent.payload ?? {};
  const mergedPayload = { ...existingPayload, ...(newPayloadFields || {}) };

  const update = { id: existingEvent.id };
  update.status = status ?? existingEvent.status;
  update.payload = serializePayload(mergedPayload);

  const resp = await apiPut('/api/v1/sre/task-events/batch', [update]);
  const items = extractItems(resp);
  return items.length > 0 ? deserializeEvent(items[0]) : null;
}
