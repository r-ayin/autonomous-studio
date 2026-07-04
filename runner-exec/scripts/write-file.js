#!/usr/bin/env node
const WebSocket = require('./vendor/ws');
const { getInternalSecret, getSessionToken, getRunnerID, WS_HOST } = require('./creds');

function escapePS(str) {
  return str.replace(/`/g, '``').replace(/\$/g, '`$').replace(/"/g, '`"').replace(/\r?\n/g, '`n');
}

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
        const parent = windowsPath.replace(/\\[^\\]+$/, '');
        const cmd = `chcp 65001 > $null\r\nNew-Item -ItemType Directory -Force -Path '${parent}' > $null\r\nSet-Content -Path '${windowsPath}' -Value "${escapePS(content)}" -Encoding UTF8\r\necho "${MARKER}"\r\n`;
        ws.send(JSON.stringify({ type: 'input', data: cmd }));
        timer = setTimeout(() => { ws.close(); resolve({ ok: false, error: 'timeout' }); }, timeoutMs);
      }
      if (msg.type === 'output') {
        output += msg.data;
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

module.exports = { writeFile, escapePS };
