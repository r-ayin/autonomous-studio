#!/usr/bin/env node
const WebSocket = require('./vendor/ws');
const { getInternalSecret, getSessionToken, getRunnerID, WS_HOST } = require('./creds');

// 16MB cap — Runner 命令可能 emit GB 级输出，this.buf += msg.data 无界累积会 OOM (audit-017 RE-EXEC-01)。
// 超 cap 时 reject 当前 exec promise，部分输出挂 error.output，对齐 write-file/batch-write 契约。
const MAX_OUTPUT = 16 * 1024 * 1024;

class RunnerSession {
  constructor() {
    this.ws = null;
    this.buf = '';
    this._onData = null;
  }

  async connect() {
    const secret = getInternalSecret();
    const runnerId = await getRunnerID(secret);
    const token = getSessionToken();

    await new Promise((resolve, reject) => {
      this.ws = new WebSocket(`${WS_HOST}/runner-shell/${runnerId}?token=${token}`);
      this.ws.on('open', () => {
        this.ws.send(JSON.stringify({ type: 'init', shell: 'powershell.exe', cols: 250, rows: 50 }));
      });
      this.ws.on('message', (raw) => {
        const msg = JSON.parse(raw.toString());
        if (msg.type === 'started') resolve();
        if (msg.type === 'output') {
          this.buf += msg.data;
          if (this._onData) this._onData();
        }
        if (msg.type === 'error') reject(new Error(msg.message));
      });
      this.ws.on('error', reject);
    });

    await this.exec('$ProgressPreference="SilentlyContinue"; chcp 65001 > $null');
    return this;
  }

  exec(cmd, timeoutMs = 30000) {
    const marker = `__X${Date.now()}${Math.random().toString(36).slice(2, 8)}__`;
    return new Promise((resolve, reject) => {
      // 超时不再静默 resolve 部分输出（push.js 的 try/catch 会把截断误计为成功）；
      // 改为 reject 并把部分输出挂在 error.output 上，与 write-file/batch-write 的 {ok:false,error:'timeout'} 契约对齐。
      const timer = setTimeout(() => {
        const result = this.buf;
        this.buf = '';
        this._onData = null;
        const e = new Error('timeout');
        e.output = result;
        reject(e);
      }, timeoutMs);

      this._onData = () => {
        if (this.buf.length > MAX_OUTPUT) {
          clearTimeout(timer);
          const e = new Error('output_overflow');
          e.output = this.buf.slice(0, MAX_OUTPUT);
          this.buf = '';
          this._onData = null;
          reject(e);
          return;
        }
        if (this.buf.includes(marker)) {
          clearTimeout(timer);
          const idx = this.buf.indexOf(marker);
          const result = this.buf.substring(0, idx);
          this.buf = this.buf.substring(idx + marker.length);
          this._onData = null;
          resolve(result);
        }
      };

      this.ws.send(JSON.stringify({
        type: 'input',
        data: `${cmd}\r\necho "${marker}"\r\n`
      }));
    });
  }

  close() {
    if (this.ws) { this.ws.close(); this.ws = null; }
  }
}

module.exports = { RunnerSession };
