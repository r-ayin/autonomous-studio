#!/usr/bin/env node
'use strict';

var http = require('http');
var fs = require('fs');
var path = require('path');

var projectDir = process.argv[2] || process.cwd();
var PORT = parseInt(process.env.PORT, 10) || 9100;

var prdPath = path.join(projectDir, 'planning', 'prd.html');
var annotationsPath = path.join(projectDir, 'planning', 'annotations.json');
var imagesDir = path.join(projectDir, 'planning', 'annotation-images');

// ---- 工具函数 ----

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function readAnnotations() {
  try {
    var data = fs.readFileSync(annotationsPath, 'utf-8');
    return JSON.parse(data);
  } catch (e) {
    return [];
  }
}

function writeAnnotations(list) {
  var dir = path.dirname(annotationsPath);
  ensureDir(dir);
  fs.writeFileSync(annotationsPath, JSON.stringify(list, null, 2), 'utf-8');
}

function parseBody(req, callback) {
  var chunks = [];
  req.on('data', function(chunk) { chunks.push(chunk); });
  req.on('end', function() {
    try {
      callback(null, JSON.parse(Buffer.concat(chunks).toString()));
    } catch (e) {
      callback(e, null);
    }
  });
}

function parseMultipart(req, callback) {
  var contentType = req.headers['content-type'] || '';
  var boundaryMatch = contentType.match(/boundary=(.+)/);
  if (!boundaryMatch) { callback(new Error('No boundary'), null); return; }
  var boundary = boundaryMatch[1];

  var chunks = [];
  req.on('data', function(chunk) { chunks.push(chunk); });
  req.on('end', function() {
    try {
      var buf = Buffer.concat(chunks);
      var parts = [];
      var boundaryBuf = Buffer.from('--' + boundary);
      var endBuf = Buffer.from('--' + boundary + '--');

      var pos = 0;
      while (pos < buf.length) {
        var start = buf.indexOf(boundaryBuf, pos);
        if (start === -1) break;
        start += boundaryBuf.length;
        if (buf.slice(start, start + 2).toString() === '--') break;
        start += 2; // skip \r\n

        var headerEnd = buf.indexOf('\r\n\r\n', start);
        if (headerEnd === -1) break;
        var headers = buf.slice(start, headerEnd).toString();
        var bodyStart = headerEnd + 4;

        var nextBoundary = buf.indexOf(boundaryBuf, bodyStart);
        var bodyEnd = nextBoundary === -1 ? buf.length : nextBoundary - 2; // -2 for \r\n

        var nameMatch = headers.match(/name="([^"]+)"/);
        var filenameMatch = headers.match(/filename="([^"]+)"/);
        var ctMatch = headers.match(/Content-Type:\s*(.+)/i);

        parts.push({
          name: nameMatch ? nameMatch[1] : '',
          filename: filenameMatch ? filenameMatch[1] : null,
          contentType: ctMatch ? ctMatch[1].trim() : null,
          data: buf.slice(bodyStart, bodyEnd)
        });

        pos = nextBoundary === -1 ? buf.length : nextBoundary;
      }
      callback(null, parts);
    } catch (e) {
      callback(e, null);
    }
  });
}

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

function sendJSON(res, status, data) {
  cors(res);
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(data));
}

// MIME 类型映射
var MIME = {
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.gif': 'image/gif', '.webp': 'image/webp', '.svg': 'image/svg+xml',
  '.bmp': 'image/bmp'
};

// ---- 路由 ----

var server = http.createServer(function(req, res) {
  cors(res);

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  var url = req.url.split('?')[0];

  // GET / → 返回 prd.html
  if (req.method === 'GET' && url === '/') {
    try {
      var html = fs.readFileSync(prdPath, 'utf-8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(html);
    } catch (e) {
      res.writeHead(404, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end('<h1>prd.html not found</h1><p>Expected at: ' + prdPath + '</p>');
    }
    return;
  }

  // GET /images/<filename> → 返回图片
  var imageMatch = url.match(/^\/images\/(.+)$/);
  if (req.method === 'GET' && imageMatch) {
    var imgName = decodeURIComponent(imageMatch[1]);
    var imgPath = path.join(imagesDir, imgName);
    if (fs.existsSync(imgPath)) {
      var ext = path.extname(imgName).toLowerCase();
      var mime = MIME[ext] || 'application/octet-stream';
      res.writeHead(200, { 'Content-Type': mime, 'Cache-Control': 'public, max-age=3600' });
      fs.createReadStream(imgPath).pipe(res);
    } else {
      res.writeHead(404);
      res.end('Image not found');
    }
    return;
  }

  // POST /api/upload → 上传图片
  if (req.method === 'POST' && url === '/api/upload') {
    ensureDir(imagesDir);
    parseMultipart(req, function(err, parts) {
      if (err || !parts || parts.length === 0) {
        sendJSON(res, 400, { error: 'Upload failed' });
        return;
      }
      var filePart = null;
      for (var i = 0; i < parts.length; i++) {
        if (parts[i].filename) { filePart = parts[i]; break; }
      }
      if (!filePart) {
        sendJSON(res, 400, { error: 'No file found' });
        return;
      }
      var ext = path.extname(filePart.filename).toLowerCase() || '.png';
      var safeName = 'img-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6) + ext;
      var savePath = path.join(imagesDir, safeName);
      fs.writeFileSync(savePath, filePart.data);
      sendJSON(res, 201, { url: '/images/' + safeName, filename: safeName });
    });
    return;
  }

  // GET /api/annotations → 返回所有批注
  if (req.method === 'GET' && url === '/api/annotations') {
    sendJSON(res, 200, readAnnotations());
    return;
  }

  // POST /api/annotations → 添加批注
  if (req.method === 'POST' && url === '/api/annotations') {
    parseBody(req, function(err, body) {
      if (err || !body || !body.selectedText || !body.comment) {
        sendJSON(res, 400, { error: 'Missing required fields: selectedText, comment' });
        return;
      }
      var list = readAnnotations();
      var annotation = {
        id: 'ann-' + Date.now(),
        selectedText: body.selectedText,
        comment: body.comment,
        images: body.images || [],
        contextBefore: body.contextBefore || '',
        contextAfter: body.contextAfter || '',
        createdAt: new Date().toISOString()
      };
      list.push(annotation);
      writeAnnotations(list);
      sendJSON(res, 201, annotation);
    });
    return;
  }

  // PUT /api/annotations/:id → 更新批注
  var putMatch = url.match(/^\/api\/annotations\/(.+)$/);
  if (req.method === 'PUT' && putMatch) {
    var updateId = decodeURIComponent(putMatch[1]);
    parseBody(req, function(err, body) {
      if (err || !body) { sendJSON(res, 400, { error: 'Invalid body' }); return; }
      var list = readAnnotations();
      var found = false;
      for (var i = 0; i < list.length; i++) {
        if (list[i].id === updateId) {
          if (body.comment !== undefined) list[i].comment = body.comment;
          if (body.images !== undefined) list[i].images = body.images;
          list[i].updatedAt = new Date().toISOString();
          found = true;
          writeAnnotations(list);
          sendJSON(res, 200, list[i]);
          break;
        }
      }
      if (!found) sendJSON(res, 404, { error: 'Annotation not found' });
    });
    return;
  }

  // DELETE /api/annotations/:id → 删除批注
  var deleteMatch = url.match(/^\/api\/annotations\/(.+)$/);
  if (req.method === 'DELETE' && deleteMatch) {
    var id = decodeURIComponent(deleteMatch[1]);
    var list = readAnnotations();
    var before = list.length;
    list = list.filter(function(a) { return a.id !== id; });
    if (list.length === before) {
      sendJSON(res, 404, { error: 'Annotation not found' });
      return;
    }
    writeAnnotations(list);
    sendJSON(res, 200, { ok: true });
    return;
  }

  // 404
  res.writeHead(404, { 'Content-Type': 'text/plain' });
  res.end('Not Found');
});

// ---- 启动时归档检测：旧版本批注自动归档到版本文件夹 ----
// 预览服务器固定读 prd.html。若 annotations.json 里的批注选中文字在当前 prd.html
// 里大面积命中不到（命中率<50%），说明是上一版 PRD 残留的批注，自动归档避免错位高亮。
// 归档结构：planning/archive/V{大版本}/  （同版本细节迭代用 V{大}.{n} 子目录）
function archiveStaleAnnotations() {
  try {
    if (!fs.existsSync(prdPath)) return;
    var html = fs.readFileSync(prdPath, 'utf-8');
    var text = html.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
                   .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
                   .replace(/<[^>]+>/g, '');
    var list = readAnnotations();
    if (!list.length) return;
    var hit = 0;
    list.forEach(function(a) {
      var sel = (a.selectedText || '').trim();
      if (sel && text.indexOf(sel) >= 0) hit++;
    });
    var rate = hit / list.length;
    if (rate < 0.5) {
      // 大版本号取自当前 prd.html 的 title（如 "PRD v4 · ..." → V4）
      var titleMatch = html.match(/PRD\s+v?(\d+)/i);
      var majorV = titleMatch ? 'V' + titleMatch[1] : 'V' + new Date().toISOString().slice(0, 10).replace(/-/g, '');
      var archiveDir = path.join(projectDir, 'planning', 'archive', majorV);
      // 同一版本已有归档 → 作为细节迭代子目录 V{大}.{n}
      if (fs.existsSync(archiveDir)) {
        var existing = fs.readdirSync(archiveDir).filter(function(f){ return /^V\d+\.\d+$/.test(f); });
        var n = existing.length + 1;
        archiveDir = path.join(archiveDir, majorV + '.' + n);
      }
      ensureDir(archiveDir);
      // 归档 prd.html + annotations.json
      fs.writeFileSync(path.join(archiveDir, 'prd.html'), html, 'utf-8');
      fs.writeFileSync(path.join(archiveDir, 'annotations.json'), JSON.stringify(list, null, 2), 'utf-8');
      writeAnnotations([]);
      console.log('   🗂  检测到 ' + list.length + ' 条旧批注命中率 ' + Math.round(rate * 100) + '%，已归档到 planning/archive/' + majorV + '/ 并清空');
    }
  } catch (e) {
    // 归档失败不影响预览启动
  }
}

// ---- 启动服务器 ----

server.listen(PORT, function() {
  archiveStaleAnnotations();
  console.log('');
  console.log('📋 PRD 预览服务器已启动');
  console.log('   本地: http://localhost:' + PORT);
  console.log('   批注文件: ' + annotationsPath);
  console.log('   图片目录: ' + imagesDir);
  console.log('');
  console.log('   选中文字即可添加批注（支持图片），批注会自动保存');
  console.log('');

  http.get('http://localhost:58596/api/port-mapping?port=' + PORT, function(pmRes) {
    var data = '';
    pmRes.on('data', function(chunk) { data += chunk; });
    pmRes.on('end', function() {
      try {
        var result = JSON.parse(data);
        if (result.url) {
          console.log('   🔗 公网: ' + result.url);
          console.log('');
        }
      } catch (e) {}
    });
  }).on('error', function() {});
});

// ---- 文件变更监听 ----

try {
  fs.watchFile(prdPath, { interval: 1000 }, function(curr, prev) {
    if (curr.mtimeMs !== prev.mtimeMs) {
      console.log('📝 PRD 文件已更新，刷新浏览器查看最新版本');
    }
  });
} catch (e) {}
