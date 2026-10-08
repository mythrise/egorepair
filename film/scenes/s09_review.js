// S09 — No agent grades its own work: the real task ledger + three independent-review cases (collaboration.md).
import { THREE, el, clamp, lerp, remap, smooth, easeOutCubic, easeInOutCubic, easeInCubic, easeOutExpo, rng, loadJSON } from '@engine/core.js';
import { makeHaze } from '@engine/fx.js';
import { Title, Chapter, fadeEl } from '@engine/ui.js';

export const duration = 26;
let scene, camera, crawl, rowsEl = [], title, chapter, stat, cases = [], g2, S;
const C1 = [6.0, 12.4], C2 = [12.4, 19.0], C3 = [19.0, 25.6];

function caseBlock(ui, { kicker, en, zh, lines }) {
  const root = el(ui, 'abs', '', { left: '150px', top: '500px', width: '1580px' });
  root.k = el(root, 'mono', kicker, { fontSize: '26px', color: '#74d7ff', letterSpacing: '0.18em' });
  root.h = el(root, 'h2', en, { fontSize: '104px', marginTop: '26px', lineHeight: '1.06' });
  root.z = el(root, 'zh-s', zh, { fontSize: '38px', marginTop: '26px' });
  root.ls = lines.map((l) => el(root, '', l, { fontSize: '44px', fontWeight: 300, marginTop: '28px', color: 'rgba(238,243,255,0.85)', lineHeight: '1.35' }));
  return root;
}
function showCase(root, t, a, b) {
  const parts = [root.k, root.h, root.z, ...root.ls];
  const vis = t > a - 0.1 && t < b + 0.1;
  root.style.display = vis ? '' : 'none';
  if (!vis) return;
  parts.forEach((p, j) => { const k = Math.min(smooth((t - a - 0.15 - j * 0.18) / 0.6), smooth((b - t - 0.05) / 0.45)); p.style.opacity = k.toFixed(3); p.style.transform = `translateY(${((1 - k) * 24).toFixed(1)}px)`; p.style.filter = k < 0.98 ? `blur(${((1 - k) * 12).toFixed(1)}px)` : 'none'; });
}

export async function init(ctx) {
  scene = new THREE.Scene();
  scene.add(makeHaze({ top: '#040914', bottom: '#010204', glow: '#0a1830', glowK: 0.35 }));
  camera = new THREE.PerspectiveCamera(35, ctx.W / ctx.H, 0.1, 100);
  g2 = ctx.g2; S = ctx.S;
  const L = await loadJSON('/assets/data/ledger.json');
  // 3D ledger crawl (CSS 3D)
  const wrap = el(ctx.ui, 'abs', '', { left: '0px', top: '0px', width: '3840px', height: '2160px', perspective: '1800px', perspectiveOrigin: '50% 30%', overflow: 'hidden' });
  crawl = el(wrap, 'abs', '', { left: '320px', top: '0px', width: '3200px', transformOrigin: '50% 0%' });
  L.rows.forEach((r, i) => {
    const row = el(crawl, '', '', { position: 'relative', height: '70px', borderBottom: '1px solid rgba(160,190,255,0.10)', whiteSpace: 'nowrap', overflow: 'hidden' });
    el(row, 'abs mono-n', String(i + 1).padStart(3, '0'), { left: '0px', top: '18px', fontSize: '24px', color: 'rgba(238,243,255,0.35)' });
    el(row, 'abs mono-n', r.d, { left: '90px', top: '18px', fontSize: '24px', color: 'rgba(238,243,255,0.5)' });
    el(row, 'abs mono-n', r.m, { left: '330px', top: '18px', fontSize: '24px', color: '#a98bff', width: '230px', overflow: 'hidden' });
    el(row, 'abs', r.s, { left: '580px', top: '16px', fontSize: '26px', fontFamily: "'Noto Sans SC'", fontWeight: 300, color: 'rgba(238,243,255,0.62)', width: '1880px', overflow: 'hidden', textOverflow: 'ellipsis' });
    if (r.r) el(row, 'abs mono-n', '✓ ' + r.r, { left: '2500px', top: '17px', fontSize: '22px', color: '#5ef2a8', padding: '2px 12px', border: '1px solid rgba(94,242,168,0.45)', borderRadius: '6px' });
    rowsEl.push({ row, rev: !!r.r });
  });
  stat = el(ctx.ui, 'abs', `<span class="mono-n" style="font-size:150px;font-weight:300">302</span><span class="mono" style="font-size:28px;margin-left:30px">LEDGER ENTRIES</span><br>
    <span class="mono-n" style="font-size:150px;font-weight:300;color:#5ef2a8">70</span><span class="mono" style="font-size:28px;margin-left:30px">WITH A NAMED INDEPENDENT REVIEWER</span>`, { left: '1240px', top: '760px', lineHeight: '1.05' });
  title = new Title(ctx.ui, { en: 'No agent grades its own work.', zh: '没有任何智能体审查自己的工作', y: 1000, size: 150 });
  chapter = new Chapter(ctx.ui, '03', 'CHECKS & BALANCES', '制衡');

  cases.push(caseBlock(ctx.ui, { kicker: 'CASE · SOURCE QUALIFICATION · NON-AUTHOR COLD READ', en: '9 valid hand positions had been erased.', zh: '非作者冷读：发现 9 个有效位置被 NaN 覆盖',
    lines: ['A full-pose NaN overwrote positions that were valid on their own.', 'Fix: position and orientation are qualified separately — the missing orientation is never invented.'] }));
  cases.push(caseBlock(ctx.ui, { kicker: 'CASE · REPLAY AT THE ORIGINAL CLOCK', en: 'The block sank 3.226 mm into the table.', zh: '原速回放：物块穿入桌面 3.226 mm，运行停止',
    lines: ['Root cause traced to the scene, not the policy: the CAD block was shifted 13.497 mm inward.', 'Status: open — kept as an unresolved finding, never written up as a success.'] }));
  cases.push(caseBlock(ctx.ui, { kicker: 'CASE · DATA MIGRATION UNDER INDEPENDENT REVIEW', en: '15,221 files. Every one compared.', zh: '33 个目录 · 15,221 个文件 · 逐文件比对',
    lines: ['33 directories · 76.48 GB · manifest and metadata compared file by file.', 'The reviewer reproduced late-write and recovery bugs first; 14 independent tests then passed.'] }));
  // per-case instrument labels
  cases.forEach((c) => { c.inst = el(ctx.ui, 'abs mono', '', { left: '1900px', top: '1700px', fontSize: '30px', color: '#eef3ff', whiteSpace: 'nowrap', textTransform: 'none', lineHeight: '1.6' }); });
  const r = rng(5);
  cases[0].miss = []; while (cases[0].miss.length < 144) { const k = Math.floor(r() * 1144); if (!cases[0].miss.includes(k)) cases[0].miss.push(k); }
  cases[0].nine = cases[0].miss.slice(0, 9);
}

function drawCase1(t, a, b) {
  const k = Math.min(smooth((t - a - 0.3) / 0.6), smooth((b - t) / 0.4));
  if (k <= 0) return;
  const cols = 52, rows = 22, cell = 32, x0 = 1900, y0 = 560;
  const found = smooth(remap(t, a + 2.0, a + 2.6)), fixed = smooth(remap(t, a + 3.6, a + 4.2));
  const C = cases[0];
  for (let i = 0; i < 1144; i++) {
    const cx = x0 + (i % cols) * cell, cy = y0 + Math.floor(i / cols) * cell;
    const appear = smooth(remap(t, a + 0.3 + (i % cols) * 0.012, a + 0.8 + (i % cols) * 0.012));
    const nine = C.nine.includes(i), miss = C.miss.includes(i);
    let fill = miss ? 'rgba(238,243,255,0.06)' : 'rgba(116,215,255,0.75)';
    g2.globalAlpha = k * appear;
    g2.fillStyle = fill; g2.fillRect(cx, cy, cell - 6, cell - 6);
    if (nine) {
      const pulse = 0.5 + 0.5 * Math.sin(t * 10);
      if (fixed > 0.5) { g2.fillStyle = 'rgba(94,242,168,0.9)'; g2.fillRect(cx, cy, (cell - 6) / 2, cell - 6); g2.strokeStyle = '#5ef2a8'; g2.lineWidth = 3; g2.strokeRect(cx + 1.5, cy + 1.5, cell - 9, cell - 9); }
      else if (found > 0) { g2.strokeStyle = `rgba(255,181,71,${0.6 + 0.4 * pulse})`; g2.lineWidth = 4; g2.strokeRect(cx - 4, cy - 4, cell + 2, cell + 2); }
    }
  }
  g2.globalAlpha = 1;
  const pos = Math.round(1000 + 9 * fixed);
  C.inst.innerHTML = `HAND FRAMES 1,144<br>POSITION QUALIFIED &nbsp;<span style="color:#5ef2a8;font-size:44px">${pos.toLocaleString('en-US')}</span> / 1,144<br>FULL ORIENTATION &nbsp;&nbsp;<span style="color:#74d7ff;font-size:44px">1,000</span> / 1,144 <span style="color:rgba(238,243,255,0.5)">· unchanged, not faked</span>`;
  C.inst.style.top = (y0 + rows * cell + 50) + 'px';
}

function drawCase2(t, a, b) {
  const k = Math.min(smooth((t - a - 0.3) / 0.6), smooth((b - t) / 0.4));
  if (k <= 0) return;
  g2.globalAlpha = k;
  const x0 = 1950, y0 = 1180, w = 1700;
  // table surface
  g2.strokeStyle = 'rgba(238,243,255,0.5)'; g2.lineWidth = 3; g2.beginPath(); g2.moveTo(x0, y0); g2.lineTo(x0 + w, y0); g2.stroke();
  g2.fillStyle = 'rgba(116,140,200,0.08)'; g2.fillRect(x0, y0, w, 220);
  const sink = easeInOutCubic(remap(t, a + 0.8, a + 2.2));
  const bx = x0 + 760, bs = 260;
  // observed block (sinks 3.226 mm, exaggerated scale)
  g2.fillStyle = 'rgba(255,154,77,0.85)'; g2.fillRect(bx, y0 - bs + sink * 46, bs, bs);
  g2.strokeStyle = '#ff4d5e'; g2.lineWidth = 4;
  if (sink > 0.98) { g2.setLineDash([]); g2.strokeRect(bx, y0 - bs + 46, bs, bs); g2.fillStyle = 'rgba(255,77,94,0.35)'; g2.fillRect(bx, y0, bs, 46); }
  // CAD block (dashed) offset 13.497 mm
  const cad = smooth(remap(t, a + 2.6, a + 3.3));
  g2.setLineDash([16, 12]); g2.strokeStyle = `rgba(116,215,255,${cad})`; g2.lineWidth = 4; g2.strokeRect(bx - 200 * cad, y0 - bs, bs, bs); g2.setLineDash([]);
  g2.font = "400 26px 'JetBrains Mono'"; g2.fillStyle = 'rgba(255,154,77,0.95)'; g2.fillText('OBSERVED', bx + 40, y0 - bs - 20 + (cad > 0.5 ? -60 : 0));
  if (cad > 0.5) { g2.fillStyle = '#74d7ff'; g2.fillText('CAD MODEL  13.497 mm', bx - 420, y0 - bs - 100); }
  if (cad > 0.5) { g2.strokeStyle = '#74d7ff'; g2.lineWidth = 3; g2.beginPath(); g2.moveTo(bx - 200, y0 - bs - 60); g2.lineTo(bx, y0 - bs - 60); g2.stroke(); g2.beginPath(); g2.moveTo(bx - 200, y0 - bs - 75); g2.lineTo(bx - 200, y0 - bs - 45); g2.moveTo(bx, y0 - bs - 75); g2.lineTo(bx, y0 - bs - 45); g2.stroke(); }
  // reprojection gauge
  const gy = y0 + 330, gw = 1500, gx = x0 + 100;
  const rp = easeOutExpo(remap(t, a + 3.4, a + 4.6));
  g2.fillStyle = 'rgba(238,243,255,0.1)'; g2.fillRect(gx, gy, gw, 26);
  const pxScale = gw / 24;
  g2.fillStyle = 'rgba(116,215,255,0.9)'; g2.fillRect(gx, gy, Math.min(20.405 * rp, 12) * pxScale, 26);
  if (20.405 * rp > 12) { g2.fillStyle = '#ff4d5e'; g2.fillRect(gx + 12 * pxScale, gy, (20.405 * rp - 12) * pxScale, 26); }
  g2.strokeStyle = '#eef3ff'; g2.lineWidth = 3; g2.beginPath(); g2.moveTo(gx + 12 * pxScale, gy - 20); g2.lineTo(gx + 12 * pxScale, gy + 46); g2.stroke();
  g2.globalAlpha = 1;
  const C = cases[1];
  C.inst.style.top = (gy + 60) + 'px'; C.inst.style.left = gx + 'px';
  C.inst.innerHTML = `REPROJECTION &nbsp;<span style="color:#ff4d5e;font-size:44px">${(20.405 * rp).toFixed(3)} px</span> &nbsp;&gt;&nbsp; declared 12 px` +
    (cad > 0.5 ? `<br><span style="color:#74d7ff">CAD OFFSET 13.497 mm</span> &nbsp;·&nbsp; <span style="color:#ff4d5e">PENETRATION 3.226 mm</span> &nbsp;·&nbsp; <span style="color:#ffb547">STATUS: OPEN</span>` : '');
}

function drawCase3(t, a, b) {
  const k = Math.min(smooth((t - a - 0.3) / 0.6), smooth((b - t) / 0.4));
  if (k <= 0) return;
  const N = 15221, cols = 151, cell = 12, x0 = 1880, y0 = 500;
  const wave = remap(t, a + 0.8, a + 4.4);
  let done = 0;
  for (let i = 0; i < N; i++) {
    const c = i % cols, r = Math.floor(i / cols);
    const ph = (c + r * 0.6) / (cols + 101 * 0.6);
    const ok = ph < wave;
    if (ok) done++;
    g2.globalAlpha = k * (ok ? 0.95 : 0.25);
    g2.fillStyle = ok ? (Math.abs(ph - wave) < 0.02 ? '#ffffff' : '#5ef2a8') : 'rgba(238,243,255,0.5)';
    g2.fillRect(x0 + c * cell, y0 + r * cell, cell - 4, cell - 4);
  }
  g2.globalAlpha = 1;
  const C = cases[2];
  const bytes = Math.round(76484981235 * done / N);
  C.inst.style.top = (y0 + 101 * cell + 40) + 'px';
  C.inst.innerHTML = `FILES VERIFIED &nbsp;<span style="color:#5ef2a8;font-size:44px">${done.toLocaleString('en-US')}</span> / 15,221 &nbsp;&nbsp; BYTES &nbsp;<span style="color:#eef3ff;font-size:44px">${bytes.toLocaleString('en-US')}</span><br><span style="color:rgba(238,243,255,0.55)">independent SHA sample 3,718,669,750 bytes · 33 directories</span>`;
}

export async function render(t, ctx) {
  camera.position.set(0, 0, 5); camera.lookAt(0, 0, 0);
  // ledger crawl: tilted, scrolling; recedes behind the cases
  const sc = t * 95;
  const back = smooth(remap(t, 5.2, 6.4));
  crawl.style.transform = `translateY(${(1650 - sc).toFixed(1)}px) translateZ(${(-300 - 1400 * back).toFixed(1)}px) rotateX(${(38 + 6 * back).toFixed(2)}deg)`;
  crawl.style.opacity = (smooth(remap(t, 0.2, 1.5)) * (1 - 0.82 * back) * (1 - smooth(remap(t, 25.2, 26)))).toFixed(3);
  rowsEl.forEach((R, i) => { if (R.rev) R.row.style.background = `rgba(94,242,168,${(0.05 + 0.05 * Math.sin(t * 3 + i)).toFixed(3)})`; });
  fadeEl(stat, smooth(remap(t, 3.5, 4.1)) * (1 - smooth(remap(t, 5.5, 6.0))), { blur: 10, dy: 20 });
  title.update(t, 0.6, 3.5);
  chapter.update(t, 0.3, 25.6);
  ctx.clear2d();
  showCase(cases[0], t, ...C1); showCase(cases[1], t, ...C2); showCase(cases[2], t, ...C3);
  cases.forEach((c, i) => { const [a, b] = [C1, C2, C3][i]; fadeEl(c.inst, Math.min(smooth((t - a - 0.8) / 0.6), smooth((b - t) / 0.4))); });
  drawCase1(t, ...C1); drawCase2(t, ...C2); drawCase3(t, ...C3);
  ctx.grade.uFade.value = smooth(remap(t, 0, 0.5)) * (1 - easeInCubic(remap(t, 25.4, 26)));
  ctx.bloomCfg.strength = 0.6;
  ctx.render(scene, camera);
}
