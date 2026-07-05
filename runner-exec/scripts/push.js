#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { RunnerSession } = require('./session');

function escapePS(str) {
  return str.replace(/`/g, '``').replace(/\$/g, '`$').replace(/"/g, '`"').replace(/\r?\n/g, '`n');
}

// Escape a path for safe interpolation into a PowerShell *single-quoted* string.
// In PS single-quote context the only special character is ' itself; escape by
// doubling (' -> ''). escapePS above is for double-quote -Value context and does
// NOT escape single quotes, so -Path '${path}' was injectable (audit-017 RE-CMDI-01).
function escapePSPath(p) {
  return String(p).replace(/'/g, "''");
}

// walkDir: enumerate regular files under dir (depth-first), skipping dotfiles.
// Symlinks are skipped (audit-2026-07-05-017 RE-PATH-01): fs.readdirSync with
// withFileTypes gives Dirent objects whose isSymbolicLink() reliably identifies
// links regardless of target type. fs.readFileSync follows symlinks by default,
// so a link inside localDir pointing at /etc/... or ~/.ssh/... would have its
// target content read and pushed to the remote Runner → local file exfiltration.
// Skipping symlinks (files AND dir-links) closes the vector at zero behavioral
// cost: a skill mirror dir contains only regular files.
function walkDir(dir) {
  const results = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue;
    if (entry.isSymbolicLink()) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) results.push(...walkDir(full));
    else results.push(full);
  }
  return results;
}

async function push(localDir, winDir) {
  winDir = winDir.replace(/\\$/, '');
  const files = walkDir(localDir);

  const manifestPath = path.join(localDir, '.pull-manifest.json');
  let oldManifest = {};
  try { oldManifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8')); } catch {}

  const changed = [];
  const newManifest = {};

  for (const localPath of files) {
    const rel = path.relative(localDir, localPath).replace(/\\/g, '/');
    const content = fs.readFileSync(localPath, 'utf-8');
    const hash = crypto.createHash('md5').update(content).digest('hex');
    newManifest[rel] = hash;

    if (oldManifest[rel] !== hash) {
      const winPath = winDir + '\\' + rel.replace(/\//g, '\\');
      changed.push({ rel, content, winPath });
    }
  }

  if (!changed.length) {
    console.log('没有变更，无需推送');
    return;
  }

  console.log(`push: ${changed.length}/${files.length} 个变更 → ${winDir}\n`);

  const session = new RunnerSession();
  await session.connect();

  let ok = 0, fail = 0;
  for (const f of changed) {
    const parent = escapePSPath(f.winPath.replace(/\\[^\\]+$/, ''));
    try {
      await session.exec(
        `New-Item -ItemType Directory -Force -Path '${parent}' > $null; Set-Content -Path '${escapePSPath(f.winPath)}' -Value "${escapePS(f.content)}" -Encoding UTF8`
      );
      process.stdout.write(`  ${f.rel.padEnd(55)} ✓\n`);
      ok++;
    } catch (e) {
      process.stdout.write(`  ${f.rel.padEnd(55)} ✗ ${e.message}\n`);
      fail++;
    }
  }

  session.close();
  fs.writeFileSync(manifestPath, JSON.stringify(newManifest, null, 2));

  console.log(`\n完成: ${ok} 成功, ${fail} 失败`);
}

if (require.main === module) {
  const localDir = process.argv[2];
  const winDir = process.argv[3];
  if (!localDir || !winDir) {
    console.log("用法: node push.js <本地目录> 'C:\\Windows\\Path'");
    console.log("示例: node push.js ./mirror 'C:\\Users\\石云鹏\\.claude\\skills\\workflow-consultant'");
    process.exit(0);
  }
  push(localDir, winDir).catch(e => { console.error('ERROR:', e.message); process.exit(1); });
}

module.exports = { push };
