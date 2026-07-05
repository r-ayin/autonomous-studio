#!/usr/bin/env node
const WebSocket = require('./vendor/ws');
const { getInternalSecret, getSessionToken, getRunnerID, WS_HOST } = require('./creds');

function escapePS(str) {
  return str.replace(/`/g, '``').replace(/\$/g, '`$').replace(/"/g, '`"').replace(/\r?\n/g, '`n');
}

// Escape a path for safe interpolation into a PowerShell *single-quoted* string.
// In PS single-quote context the only special character is ' itself; the standard
// escape is doubling (' -> ''). escapePS above is for double-quote -Value context
// and does NOT escape single quotes, so -Path '${path}' was injectable (audit-017
// RE-CMDI-01). Use this for every -Path '...' interpolation.
function escapePSPath(p) {
  return String(p).replace(/'/g, "''");
}

// 16MB cap — 写文件只需扫 MARKER 确认完成，不需要完整 output；但 output += msg.data 无界累积
// 会在 Runner 误回放大输出时 OOM (audit-017 RE-EXEC-01)。超 cap 时停止累积并报 output_overflow。
const MAX_OUTPUT = 16 * 1024 * 1024;

async function writeFile(windowsPath, content, timeoutMs = 30000) {
  const secret = getInternalSecret();
  const runnerId = await getRunnerID(secret);
  const token = getSessionToken();

  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`${WS_HOST}/runner-shell/${runnerId}?token=${token}`);
    let output = '';
    const MARKER = `__DONE_${Date.now()}__`;
    let timer;

    ws.on('open', () => {
      ws.send(JSON.stringify({ type: 'init', shell: 'powershell.exe', cols: 250, rows: 50 }));
    });

    ws.on('message', (raw) => {
      const msg = JSON.parse(raw.toString());
      if (msg.type === 'started') {
        const parent = escapePSPath(windowsPath.replace(/\\[^\\]+$/, ''));
        const cmd = `chcp 65001 > $null\r\nNew-Item -ItemType Directory -Force -Path '${parent}' > $null\r\nSet-Content -Path '${escapePSPath(windowsPath)}' -Value "${escapePS(content)}" -Encoding UTF8\r\necho "${MARKER}"\r\n`;
        ws.send(JSON.stringify({ type: 'input', data: cmd }));
        timer = setTimeout(() => { ws.close(); resolve({ ok: false, error: 'timeout' }); }, timeoutMs);
      }
      if (msg.type === 'output') {
        output += msg.data;
        if (output.length > MAX_OUTPUT) { clearTimeout(timer); ws.close(); resolve({ ok: false, error: 'output_overflow' }); return; }
        if (output.includes(MARKER)) { clearTimeout(timer); ws.close(); resolve({ ok: true }); }
      }
      if (msg.type === 'exit') { clearTimeout(timer); ws.close(); resolve({ ok: true }); }
      if (msg.type === 'error') { clearTimeout(timer); ws.close(); reject(new Error(msg.message)); }
    });

    ws.on('error', (err) => { clearTimeout(timer); reject(err); });
  });
}

if (require.main === module) {
  const winPath = process.argv[2];
  const content = process.argv[3];
  if (!winPath || content === undefined) {
    console.log('用法: node write-file.js \'C:\\path\\file.txt\' \'内容\'');
    process.exit(0);
  }
  writeFile(winPath, content).then(r => console.log(r.ok ? '✓' : `✗ ${r.error}`)).catch(e => { console.error('ERROR:', e.message); process.exit(1); });
}

module.exports = { writeFile, escapePS, escapePSPath };
