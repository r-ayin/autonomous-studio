#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { RunnerSession } = require('./session');

const TEXT_EXTS = new Set([
  '.md','.js','.ts','.tsx','.jsx','.json','.yaml','.yml','.txt',
  '.html','.css','.py','.sh','.ps1','.xml','.toml','.cfg','.ini',
  '.vue','.svg','.bat','.cmd','.env','.gitignore',
]);

function stripAnsi(s) {
  return s
    .replace(/\x1B\[[0-9;?]*[A-Za-z]/g, '')
    .replace(/\x1B\][^\x07]*\x07/g, '')
    .replace(/\x1B[()][A-Za-z]/g, '')
    .replace(/\x1B./g, '');
}

function extractBetween(raw, startMark, endMark) {
  const clean = stripAnsi(raw);
  const lines = clean.split(/\r?\n/);
  const si = lines.findIndex(l => l.trim() === startMark);
  let ei = -1;
  for (let i = lines.length - 1; i > si; i--) {
    if (lines[i].trim() === endMark) { ei = i; break; }
  }
  if (si >= 0 && ei > si) return lines.slice(si + 1, ei).join('\n');
  return null;
}

async function pull(winDir, localDir) {
  winDir = winDir.replace(/\\$/, '');
  const session = new RunnerSession();
  await session.connect();

  console.log(`pull: ${winDir} → ${localDir}\n`);

  const listRaw = await session.exec(
    `Get-ChildItem -Path '${winDir}' -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }`
  );
  const allFiles = stripAnsi(listRaw).split(/\r?\n/)
    .map(l => l.trim())
    .filter(l => /^[A-Za-z]:\\/.test(l) && !/>$/.test(l));

  const textFiles = allFiles.filter(f => {
    const dot = f.lastIndexOf('.');
    if (dot < 0) return false;
    const ext = f.substring(dot).toLowerCase();
    return TEXT_EXTS.has(ext);
  });

  console.log(`${allFiles.length} 个文件, ${textFiles.length} 个文本文件\n`);

  const manifest = {};
  let ok = 0, fail = 0;

  for (const winPath of textFiles) {
    const rel = winPath.substring(winDir.length).replace(/\\/g, '/').replace(/^\//, '');
    const localPath = path.join(localDir, rel);
    const ts = Date.now();
    const S = `__RS${ts}__`, E = `__RE${ts}__`;

    const raw = await session.exec(`echo "${S}"; Get-Content -Path '${winPath}' -Raw -ErrorAction SilentlyContinue; echo "${E}"`);
    const content = extractBetween(raw, S, E);

    if (content !== null) {
      fs.mkdirSync(path.dirname(localPath), { recursive: true });
      fs.writeFileSync(localPath, content, 'utf-8');
      manifest[rel] = crypto.createHash('md5').update(content).digest('hex');
      process.stdout.write(`  ${rel.padEnd(55)} ✓\n`);
      ok++;
    } else {
      process.stdout.write(`  ${rel.padEnd(55)} ✗\n`);
      fail++;
    }
  }

  fs.writeFileSync(path.join(localDir, '.pull-manifest.json'), JSON.stringify(manifest, null, 2));
  session.close();

  console.log(`\n完成: ${ok} 成功, ${fail} 失败`);
  console.log(`本地目录: ${path.resolve(localDir)}`);
}

if (require.main === module) {
  const winDir = process.argv[2];
  const localDir = process.argv[3] || path.join(process.cwd(), '.runner-mirror', path.basename(winDir || 'x'));
  if (!winDir) {
    console.log("用法: node pull.js 'C:\\Windows\\Path' [本地目录]");
    console.log("示例: node pull.js 'C:\\Users\\石云鹏\\.claude\\skills\\workflow-consultant'");
    process.exit(0);
  }
  pull(winDir, localDir).catch(e => { console.error('ERROR:', e.message); process.exit(1); });
}

module.exports = { pull };
