#!/usr/bin/env node
const http = require('http');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const SERVER = 'http://127.0.0.1:58596';
const WS_HOST = 'ws://127.0.0.1:58596';

function getInternalSecret() {
  try {
    const p = path.join(process.env.HOME || '/home/admin', '.aone-cloud-cli', 'internal-rpc-secret');
    if (fs.existsSync(p)) return fs.readFileSync(p, 'utf-8').trim();
  } catch {}
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
    return execSync(`sqlite3 "${dbPath}" "SELECT token FROM active_tokens ORDER BY created_at DESC LIMIT 1;"`, { encoding: 'utf-8' }).trim();
  } catch {}
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
