// Простой статик-сервер для продакшена. Заменяет пакет `serve`, у которого
// serve-handler рекурсивно применяет rewrites к своему же результату: любое
// специфичное правило (/panel -> /panel/index.html) в итоге перебивается
// catch-all-правилом ("**" -> /index.html) на следующем проходе, потому что
// catch-all матчит вообще всё, включая уже переписанный путь. Из-за этого
// /panel/ ВСЕГДА отдавал игровой index.html вместо админ-панели.
// Здесь маршрутизация простая и явная: /panel/* -> dist/panel (SPA-фолбэк
// на dist/panel/index.html), всё остальное -> dist (SPA-фолбэк на dist/index.html).
import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DIST = path.join(__dirname, 'dist');
const PORT = process.env.PORT || 3000;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.gif': 'image/gif',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.wasm': 'application/wasm',
  '.map': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.webmanifest': 'application/manifest+json',
};

function contentType(filePath) {
  return MIME[path.extname(filePath).toLowerCase()] || 'application/octet-stream';
}

function safeJoin(root, urlPath) {
  const decoded = decodeURIComponent(urlPath.split('?')[0]);
  const resolved = path.normalize(path.join(root, decoded));
  if (!resolved.startsWith(root)) {
    return null; // защита от path traversal (../../..)
  }
  return resolved;
}

function sendFile(res, filePath) {
  const stream = fs.createReadStream(filePath);
  stream.on('error', () => {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Not found');
  });
  res.writeHead(200, { 'Content-Type': contentType(filePath) });
  stream.pipe(res);
}

function serveFrom(res, root, urlPath, spaFallback) {
  const requested = safeJoin(root, urlPath === '/' ? '/index.html' : urlPath);
  if (!requested) {
    res.writeHead(400);
    res.end('Bad request');
    return;
  }

  fs.stat(requested, (err, stats) => {
    if (!err && stats.isFile()) {
      sendFile(res, requested);
      return;
    }
    // Директория или файл не найден — отдаём index.html этого приложения (SPA).
    sendFile(res, path.join(root, spaFallback));
  });
}

const server = http.createServer((req, res) => {
  const urlPath = req.url || '/';

  if (urlPath === '/panel' || urlPath.startsWith('/panel/')) {
    const sub = urlPath === '/panel' ? '/' : urlPath.slice('/panel'.length);
    serveFrom(res, path.join(DIST, 'panel'), sub, 'index.html');
    return;
  }

  serveFrom(res, DIST, urlPath, 'index.html');
});

server.listen(PORT, () => {
  console.log(`[server] serving ${DIST} on :${PORT} ( /panel/* -> dist/panel, остальное -> dist )`);
});
