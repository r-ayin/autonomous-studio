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
 * Host allowlist + IP-literal block added per audit-2026-07-06-001 PD-TOKEN-01
 * (auth token must not be sent to an arbitrary host in DEVOUT_SERVER_URL).
 */

/**
 * Default HTTP request timeout in milliseconds.
 * Prevents fetch() from hanging indefinitely when the server is unresponsive.
 * Can be overridden via DEVOUT_HTTP_TIMEOUT_MS env var for testing / slow networks.
 */
const DEFAULT_TIMEOUT_MS = Number(process.env.DEVOUT_HTTP_TIMEOUT_MS) || 30000;

/**
 * Default hostname allowlist for DEVOUT_SERVER_URL.
 * getHeaders() attaches the deploy token (CODE_PRIVATE_TOKEN / DEVOUT_TOKEN) to
 * every request. Without an allowlist, a misconfigured, typo'd, or DNS-rebinding
 * DEVOUT_SERVER_URL would silently leak that token to an attacker-controlled host.
 * Allowed by default: loopback + internal *.alibaba-inc.com. Extend at runtime
 * via DEVOUT_ALLOWED_HOSTS (comma-separated, e.g. "deploy.internal,10.0.0.5").
 * IP literals are rejected unless explicitly listed (SSRF / metadata-service guard).
 */
const DEFAULT_ALLOWED_HOSTS = ['localhost', '127.0.0.1', '::1', '*.alibaba-inc.com'];

function getAllowedHosts() {
  const extra = (process.env.DEVOUT_ALLOWED_HOSTS || '')
    .split(',')
    .map(h => h.trim().toLowerCase())
    .filter(Boolean);
  // Dedupe while preserving order (defaults first).
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

/**
 * True if hostname looks like a raw IP literal (IPv4 dotted-quad or IPv6).
 * new URL().hostname returns IPv6 without brackets, so we detect by pattern.
 */
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

export function getBaseUrl() {
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
      `(audit-2026-07-06-001 PD-TOKEN-01).`
    );
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
