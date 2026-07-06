#!/usr/bin/env node
const http = require('http');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

// 可由部署环境通过 CLOUDCLI_API_BASE_URL 覆盖（precedent: devix-automation-skill SKILL.md commit 2560c9b）。
// 未设置时回退到本地 cloud-cli server 默认端口，保持原有行为。
const DEFAULT_API_BASE = 'http://127.0.0.1:58596';
const API_BASE = process.env.CLOUDCLI_API_BASE_URL || DEFAULT_API_BASE;
const SERVER = API_BASE.replace(/\/+$/, ''); // 去尾部斜杠，避免拼路径出现双斜杠
const WS_HOST = SERVER.replace(/^http/, 'ws'); // http(s):// → ws(s)://

function getInternalSecret() {
  try {
    const p = path.join(process.env.HOME || '/home/admin', '.aone-cloud-cli', 'internal-rpc-secret');
    if (fs.existsSync(p)) return fs.readFileSync(p, 'utf-8').trim();
  } catch (e) { /* keep fallback to pgrep path; file read failure non-fatal */ }
  try {
    const pid = execSync("pgrep -f 'node.*cloud-cli.*server'", { encoding: 'utf-8' }).trim().split('\n')[0];
    if (pid) {
      const env = fs.readFileSync(`/proc/${pid}/environ`, 'utf-8');
      const m = env.match(/INTERNAL_RPC_SECRET=([^\0]+)/);
      if (m) return m[1];
    }
  } catch {}
  throw new Error('无法获取 Internal Secret');
}

function getSessionToken() {
  const dbPath = path.join(process.env.HOME || '/home/admin', '.aone-cloud-cli', 'auth.db');
  try {
    return execFileSync('sqlite3', [dbPath, 'SELECT token FROM active_tokens ORDER BY created_at DESC LIMIT 1;'], { encoding: 'utf-8' }).trim();
  } catch (e) { throw new Error('无法获取 session token: ' + e.message); }
  throw new Error('无法获取 session token');
}

function getRunnerID(secret) {
  return new Promise((resolve, reject) => {
    const req = http.request(`${SERVER}/api/runner-internal-rpc/list-runners`, {
      headers: { 'X-Internal-Secret': secret },
    }, (res) => {
      let buf = '';
      res.on('data', c => buf += c);
      res.on('end', () => {
        try {
          const runners = JSON.parse(buf).runners || [];
          if (!runners.length) reject(new Error('没有在线 runner'));
          else resolve(runners[0].id);
        } catch (e) { reject(e); }
      });
    });
    req.on('error', reject);
    req.end();
  });
}

module.exports = { getInternalSecret, getSessionToken, getRunnerID, SERVER, WS_HOST };
