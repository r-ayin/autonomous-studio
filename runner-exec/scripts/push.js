#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { RunnerSession } = require('./session');

function escapePS(str) {
  return str.replace(/`/g, '``').replace(/\$/g, '`$').replace(/"/g, '`"').replace(/\r?\n/g, '`n');
}

function walkDir(dir) {
  const results = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue;
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
    const parent = f.winPath.replace(/\\[^\\]+$/, '');
    try {
      await session.exec(
        `New-Item -ItemType Directory -Force -Path '${parent}' > $null; Set-Content -Path '${f.winPath}' -Value "${escapePS(f.content)}" -Encoding UTF8`
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
