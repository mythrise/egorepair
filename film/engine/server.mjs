// Minimal static file server used by the renderer (ES modules need http://).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const TYPES = {
  '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.webp': 'image/webp', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.woff': 'font/woff',
  '.bin': 'application/octet-stream', '.f32': 'application/octet-stream', '.ttf': 'font/ttf', '.otf': 'font/otf',
};

// roots: { '/': filmDir, '/assets/': assetsDir }
export function serve(roots, port = 0) {
  const entries = Object.entries(roots).sort((a, b) => b[0].length - a[0].length);
  const server = http.createServer((req, res) => {
    const url = decodeURIComponent(req.url.split('?')[0]);
    for (const [prefix, dir] of entries) {
      if (url.startsWith(prefix)) {
        const p = path.join(dir, url.slice(prefix.length));
        if (!p.startsWith(dir)) break;
        fs.stat(p, (err, st) => {
          if (err || !st.isFile()) { res.writeHead(404); res.end('nf ' + url); return; }
          res.writeHead(200, { 'Content-Type': TYPES[path.extname(p).toLowerCase()] || 'application/octet-stream',
            'Content-Length': st.size, 'Cache-Control': 'max-age=3600' });
          fs.createReadStream(p).pipe(res);
        });
        return;
      }
    }
    res.writeHead(404); res.end('nf');
  });
  return new Promise((resolve) => server.listen(port, '127.0.0.1', () => resolve({ server, port: server.address().port })));
}
