#!/usr/bin/env node
const WebSocket = require('./vendor/ws');
const { getInternalSecret, getSessionToken, getRunnerID, WS_HOST } = require('./creds');

async function execOnRunner(command, timeoutMs = 30000) {
  const secret = getInternalSecret();
  const runnerId = await getRunnerID(secret);
  const token = getSessionToken();

  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`${WS_HOST}/runner-shell/${runnerId}?token=${token}`);
    let output = '';
    const MARKER = `__END_${Date.now()}__`;
    let timer;

    ws.on('open', () => {
      ws.send(JSON.stringify({ type: 'init', shell: 'powershell.exe', cols: 200, rows: 50 }));
    });

    ws.on('message', (raw) => {
      const msg = JSON.parse(raw.toString());
      if (msg.type === 'started') {
        ws.send(JSON.stringify({ type: 'input', data: `${command}\r\necho "${MARKER}"\r\n` }));
        timer = setTimeout(() => { ws.close(); resolve(output); }, timeoutMs);
      }
      if (msg.type === 'output') {
        output += msg.data;
        if (output.includes(MARKER)) {
          clearTimeout(timer);
          ws.close();
          resolve(output.substring(0, output.indexOf(MARKER)));
        }
      }
      if (msg.type === 'exit') { clearTimeout(timer); ws.close(); resolve(output); }
      if (msg.type === 'error') { clearTimeout(timer); ws.close(); reject(new Error(msg.message)); }
    });

    ws.on('error', reject);
  });
}

if (require.main === module) {
  const cmd = process.argv[2];
  if (!cmd) {
    console.log('用法: node exec.js \'<PowerShell命令>\'');
    process.exit(0);
  }
  execOnRunner(cmd).then(out => console.log(out)).catch(e => { console.error('ERROR:', e.message); process.exit(1); });
}

module.exports = { execOnRunner };
