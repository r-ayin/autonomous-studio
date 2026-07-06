#!/usr/bin/env node
const WebSocket = require('./vendor/ws');
const { getInternalSecret, getSessionToken, getRunnerID, WS_HOST } = require('./creds');

// 16MB cap — Runner 命令可能 emit GB 级输出（Get-Content huge.log / tree /f / 误执行递归列目录），
// output += msg.data 无界累积会 OOM 崩溃本地 node 进程 (audit-017 RE-EXEC-01)。超 cap 时 reject 并把
// 部分输出挂 error.output，与 write-file/batch-write 的 {ok:false,error:...} 契约对齐。
const MAX_OUTPUT = 16 * 1024 * 1024;

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
        // 超时不再静默 resolve 部分输出（会令调用方误判命令成功完成）；
        // 改为 reject 并把已收到的部分输出挂在 error.output 上，与 write-file/batch-write 的 {ok:false,error:'timeout'} 契约对齐。
        timer = setTimeout(() => { ws.close(); const e = new Error('timeout'); e.output = output; reject(e); }, timeoutMs);
      }
      if (msg.type === 'output') {
        output += msg.data;
        if (output.length > MAX_OUTPUT) {
          clearTimeout(timer);
          ws.close();
          const e = new Error('output_overflow');
          e.output = output.slice(0, MAX_OUTPUT);
          reject(e);
          return;
        }
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
