// Frame-accurate renderer: drives player.html in headless Chromium and pipes frames into ffmpeg.
// usage:
//   node engine/render.mjs --scene NAME [--w 3840 --h 2160] [--fps 30] [--from S] [--to S] --out FILE.mp4
//   node engine/render.mjs --scene NAME --stills 0,1.5,3 --outdir DIR      (PNG stills for review)
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { serve } from './server.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_PATH || '/opt/node22/lib/node_modules/playwright');

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) acc.push([a.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : '1']);
  return acc;
}, []));
const FILM = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ASSETS = process.env.FILM_ASSETS || path.join(FILM, 'assets');
const W = +(args.w || 3840), H = +(args.h || 2160), FPS = +(args.fps || 30);
const scene = args.scene;

const { server, port } = await serve({ '/': FILM, '/assets/': ASSETS + '/' });
const browser = await chromium.launch({
  headless: true,
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist',
    '--disable-gpu-vsync', '--disable-frame-rate-limit', '--force-color-profile=srgb',
    '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--font-render-hinting=none'],
});
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.error('[page]', m.text()); });
page.on('pageerror', (e) => console.error('[pageerror]', e.message));
const extra = args.params ? '&' + args.params : '';
await page.goto(`http://127.0.0.1:${port}/engine/player.html?scene=${scene}&w=${W}&h=${H}${extra}`);
await page.waitForFunction(() => window.__ready || window.__error, null, { timeout: 600000 });
const err = await page.evaluate(() => window.__error);
if (err) { console.error(err); process.exit(2); }
const duration = await page.evaluate(() => window.__duration);
const cdp = await page.context().newCDPSession(page);
const fmt = args.fmt || 'png';

async function grab() {
  const r = await cdp.send('Page.captureScreenshot', { format: fmt, quality: fmt === 'jpeg' ? 96 : undefined, optimizeForSpeed: true, fromSurface: true });
  return Buffer.from(r.data, 'base64');
}
async function frameAt(t) {
  await page.evaluate((tt) => window.__frame(tt), t);
  return grab();
}

if (args.stills) {
  const outdir = args.outdir || path.join(FILM, 'out', 'stills');
  fs.mkdirSync(outdir, { recursive: true });
  for (const s of args.stills.split(',')) {
    const t = +s;
    const t0 = Date.now();
    const buf = await frameAt(t);
    const f = path.join(outdir, `${scene}_${t.toFixed(2)}.${fmt === 'jpeg' ? 'jpg' : 'png'}`);
    fs.writeFileSync(f, buf);
    console.log(`still ${f} ${(Date.now() - t0)}ms`);
  }
} else {
  const from = +(args.from || 0), to = +(args.to || duration);
  const n0 = Math.round(from * FPS), n1 = Math.round(to * FPS);
  const out = args.out || path.join(FILM, 'out', `${scene}.mp4`);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const crf = args.crf || '10';
  const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(FPS),
    '-c:v', fmt === 'jpeg' ? 'mjpeg' : 'png', '-i', '-',
    '-c:v', 'libx264', '-preset', args.preset || 'medium', '-crf', crf, '-pix_fmt', 'yuv420p',
    '-x264-params', 'keyint=60:min-keyint=1', '-r', String(FPS), out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let n = n0; n < n1; n++) {
    const t = n / FPS;
    const buf = await frameAt(t);
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
    if ((n - n0) % 30 === 0) {
      const el = (Date.now() - t0) / 1000, done = n - n0 + 1;
      console.log(`${scene} frame ${n}/${n1} t=${t.toFixed(2)} ${(el / done).toFixed(2)}s/f eta ${((n1 - n) * el / done / 60).toFixed(1)}min`);
    }
  }
  ff.stdin.end();
  await new Promise((r) => ff.on('close', r));
  console.log(`done ${out} in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
}
await browser.close();
server.close();
