/**
 * http-base.js — Shared HTTP helpers for prod-deploy skill clients.
 *
 * Extracted from task-client.js / event-client.js to deduplicate getBaseUrl,
 * getHeaders, and fetch wrappers (apiGet/apiPost/apiPut). All three read the
 * same env vars (DEVOUT_SERVER_URL, CODE_PRIVATE_TOKEN, DEVOUT_TOKEN) and
 * share identical error handling + timeout logic.
 *
 * Audit reference: audit-2026-07-02-006 finding L-001 (route-fix).
 * Timeout logic preserved from H-001 / H-002 fixes.
 */

/**
 * Default HTTP request timeout in milliseconds.
 * Prevents fetch() from hanging indefinitely when the server is unresponsive.
 * Can be overridden via DEVOUT_HTTP_TIMEOUT_MS env var for testing / slow networks.
 */
const DEFAULT_TIMEOUT_MS = Number(process.env.DEVOUT_HTTP_TIMEOUT_MS) || 30000;

export function getBaseUrl() {
  const url = process.env.DEVOUT_SERVER_URL;
  if (!url) {
    throw new Error('DEVOUT_SERVER_URL not set');
  }
  return url.replace(/\/$/, '');
}

export function getHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (process.env.CODE_PRIVATE_TOKEN) {
    headers['X-Agent-Authorization'] = `Code ${process.env.CODE_PRIVATE_TOKEN}`;
  } else if (process.env.DEVOUT_TOKEN) {
    headers['token'] = process.env.DEVOUT_TOKEN;
  }
  return headers;
}

export async function apiGet(path) {
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

export async function apiPost(path, body) {
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

export async function apiPut(path, body) {
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
