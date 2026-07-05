#!/usr/bin/env node
const fs = require('fs');
const WebSocket = require('./vendor/ws');
const { getInternalSecret, getSessionToken, getRunnerID, WS_HOST } = require('./creds');
const { escapePS, escapePSPath } = require('./write-file');

async function batchWrite(files, timeoutMs = 60000) {
  const secret = getInternalSecret();
  const runnerId = await getRunnerID(secret);
  const token = getSessionToken();

  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`${WS_HOST}/runner-shell/${runnerId}?token=${token}`);
    let output = '';
    const MARKER = `__BATCH_DONE_${Date.now()}__`;
    let timer;

    ws.on('open', () => {
      ws.send(JSON.stringify({ type: 'init', shell: 'powershell.exe', cols: 250, rows: 50 }));
    });

    ws.on('message', (raw) => {
      const msg = JSON.parse(raw.toString());
      if (msg.type === 'started') {
        const cmds = ['chcp 65001 > $null'];
        for (const f of files) {
          const parent = escapePSPath(f.path.replace(/\\[^\\]+$/, ''));
          cmds.push(`New-Item -ItemType Directory -Force -Path '${parent}' > $null`);
          cmds.push(`Set-Content -Path '${escapePSPath(f.path)}' -Value "${escapePS(f.content)}" -Encoding UTF8`);
          cmds.push(`echo "  ${f.path.split('\\').pop()} OK"`);
        }
        cmds.push(`echo "${MARKER}"`);
        ws.send(JSON.stringify({ type: 'input', data: cmds.join('\r\n') + '\r\n' }));
        timer = setTimeout(() => { ws.close(); resolve({ ok: false, error: 'timeout', output }); }, timeoutMs);
      }
      if (msg.type === 'output') {
        output += msg.data;
        if (output.includes(MARKER)) { clearTimeout(timer); ws.close(); resolve({ ok: true, output }); }
      }
      if (msg.type === 'exit') { clearTimeout(timer); ws.close(); resolve({ ok: true, output }); }
      if (msg.type === 'error') { clearTimeout(timer); ws.close(); reject(new Error(msg.message)); }
    });

    ws.on('error', (err) => { clearTimeout(timer); reject(err); });
  });
}

if (require.main === module) {
  const manifestPath = process.argv[2];
  if (!manifestPath) {
    console.log('用法: node batch-write.js <manifest.json>');
    console.log('manifest 格式: [{"path":"C:\\\\...","content":"..."}]');
    process.exit(0);
  }
  const files = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
  console.log(`批量写入 ${files.length} 个文件...`);
  batchWrite(files).then(r => {
    console.log(r.ok ? `✓ 全部完成` : `✗ ${r.error}`);
  }).catch(e => { console.error('ERROR:', e.message); process.exit(1); });
}

module.exports = { batchWrite };
