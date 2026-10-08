// S03 — Anatomy of the gap: a real EgoDex clip dissected with real computer vision.
import { THREE, el, clamp, lerp, remap, smooth, easeOutCubic, easeInOutCubic, easeInCubic, loadImage, loadJSON } from '@engine/core.js';
import { makeHaze } from '@engine/fx.js';
import { Title, Chapter, fadeEl } from '@engine/ui.js';

export const duration = 30;
const VX = 150, VY = 330, VW = 2480, VH = 1395; // video rect (design px)
const CLIP = '/assets/footage/ego_raw', NF = 302;
let scene, camera, g2, hands, flow, depthImg, chapter, steps = [], verdict, head, sub, spark;

// playback map: scene time -> source frame (float). slow-motion with freeze frames for analysis beats.
function srcFrame(t) {
  if (t < 14.5) return clamp(t * 12, 0, 160);          // 0.4x through the reach
  if (t < 19.5) return 0;                               // freeze on frame 0 for depth (matches reconstruction)
  if (t < 25) return 200 + (t - 19.5) * 6;             // slow push through the grasp
  return 233;
}
async function drawFrame(f, alpha = 1) {
  const i = Math.floor(f), fr = f - i;
  const a = await loadImage(`${CLIP}/${String(clamp(i, 0, NF - 1)).padStart(4, '0')}.jpg`);
  g2.imageSmoothingEnabled = true; g2.imageSmoothingQuality = 'high';
  g2.globalAlpha = alpha; g2.drawImage(a, VX, VY, VW, VH);
  if (fr > 0.02 && i + 1 < NF) { const b = await loadImage(`${CLIP}/${String(i + 1).padStart(4, '0')}.jpg`); g2.globalAlpha = alpha * fr; g2.drawImage(b, VX, VY, VW, VH); }
  g2.globalAlpha = 1;
}
const P = (p) => [VX + p[0] * VW, VY + p[1] * VH];

function step(ui, i, en, zh, stat) {
  const e = el(ui, 'abs', `<div class="mono" style="font-size:26px;color:#74d7ff;letter-spacing:0.18em">0${i} </div>
    <div class="h3" style="font-size:66px;margin-top:14px;line-height:1.1">${en}</div>
    <div class="zh-s" style="font-size:36px;margin-top:18px">${zh}</div>
    <div class="mono" style="font-size:24px;margin-top:22px;color:rgba(238,243,255,0.6);text-transform:none;line-height:1.6">${stat}</div>`, { left: '2790px', top: '560px', width: '920px' });
  return e;
}

export async function init(ctx) {
  scene = new THREE.Scene();
  scene.add(makeHaze({ top: '#050912', bottom: '#010204', glow: '#0c1630', glowK: 0.3 }));
  camera = new THREE.PerspectiveCamera(35, ctx.W / ctx.H, 0.1, 100);
  g2 = ctx.g2;
  hands = await loadJSON('/assets/data/hands_ego_raw.json');
  flow = await loadJSON('/assets/data/flow_ego_raw.json');
  depthImg = await loadImage('/assets/scene/ego0_720/depth_turbo.png');
  chapter = new Chapter(ctx.ui, '01', 'THE GAP', '鸿沟');
  head = new Title(ctx.ui, { en: 'A video shows what happened.', zh: '视频记录了发生了什么', x: 2790, y: 760, align: 'left', size: 88, width: 950, zhSize: 40 });
  sub = new Title(ctx.ui, { en: 'Not what a robot needs.', zh: '却没有机器人需要的信息', x: 2790, y: 1180, align: 'left', size: 88, width: 950, zhSize: 40 });
  steps.push(step(ctx.ui, 1, 'Hands are estimated, frame by frame.', '手部关键点只能逐帧估计', '21 landmarks / hand · 599 detections in 302 frames<br>confidence 0.51 – 1.00 · handedness mirrored · jitter'));
  steps.push(step(ctx.ui, 2, 'The camera never holds still.', '相机随头部持续运动', 'dense optical flow · camera ego-motion<br>no fixed world frame without SLAM'));
  steps.push(step(ctx.ui, 3, 'Depth is estimated, not measured.', '深度只能估计，尺度并不确定', 'monocular geometry · metric scale uncertain<br>(planar estimate shown)'));
  steps.push(step(ctx.ui, 4, 'Contact is never observed.', '接触无法直接观测，力从未被记录', 'fingers occlude the object at the moment that matters<br>no forces · no contact labels'));
  verdict = el(ctx.ui, 'abs', `<div class="h2" style="font-size:120px;font-weight:600">Video ≠ robot data.</div><div class="zh" style="margin-top:26px;font-size:46px">视频，不等于机器人数据</div>
    <div class="mono" style="margin-top:50px;font-size:30px;line-height:2.0;color:#ff6b77;text-transform:none">✕ no joint states q &nbsp; ✕ no contact labels &nbsp; ✕ no forces<br>✕ no robot embodiment &nbsp; ✕ no fixed base</div>`, { left: '2790px', top: '620px', width: '1000px' });
  spark = el(ctx.ui, 'abs mono', '', { left: VX + 'px', top: (VY + VH + 40) + 'px', fontSize: '22px', color: 'rgba(238,243,255,0.5)', textTransform: 'none' });
}

function drawHands(f, k, t) {
  const fr = hands.frames[Math.round(f)] || [];
  g2.lineCap = 'round';
  for (const h of fr) {
    const pts = h.img.map(P);
    g2.globalAlpha = k * (0.55 + 0.45 * h.score);
    g2.strokeStyle = '#74d7ff'; g2.lineWidth = 5; g2.shadowColor = '#74d7ff'; g2.shadowBlur = 14;
    g2.beginPath(); for (const [a, b] of hands.edges) { g2.moveTo(...pts[a]); g2.lineTo(...pts[b]); } g2.stroke();
    g2.shadowBlur = 0; g2.fillStyle = '#ffffff';
    for (const p of pts) { g2.beginPath(); g2.arc(p[0], p[1], 7, 0, Math.PI * 2); g2.fill(); }
    g2.font = "500 24px 'JetBrains Mono'"; g2.fillStyle = '#74d7ff';
    g2.fillText(`${h.label.toUpperCase()} ${h.score.toFixed(2)}`, pts[0][0] + 16, pts[0][1] + 40);
  }
  // fingertip trails (index tip) over the last 20 frames show the jitter
  g2.globalAlpha = k * 0.9; g2.strokeStyle = 'rgba(255,181,71,0.9)'; g2.lineWidth = 3; g2.beginPath();
  let first = true;
  for (let j = Math.max(0, Math.round(f) - 24); j <= Math.round(f); j++) { const h = (hands.frames[j] || [])[0]; if (!h) continue; const p = P(h.img[8]); if (first) { g2.moveTo(...p); first = false; } else g2.lineTo(...p); }
  g2.stroke(); g2.globalAlpha = 1;
}
function drawFlow(f, k) {
  const fr = flow.flow[Math.round(f)] || flow.flow[0];
  const gx = flow.gx, gy = flow.gy;
  g2.globalAlpha = k; g2.strokeStyle = 'rgba(238,243,255,0.85)'; g2.lineWidth = 3; g2.fillStyle = 'rgba(238,243,255,0.85)';
  for (let j = 0; j < gy; j++) for (let i = 0; i < gx; i++) {
    const [dx, dy] = fr[j * gx + i];
    const x = VX + (i + 0.5) / gx * VW, y = VY + (j + 0.5) / gy * VH;
    let sx = dx * VW * 7, sy = dy * VH * 7;
    let m = Math.hypot(sx, sy);
    if (m > 70) { sx *= 70 / m; sy *= 70 / m; m = 70; }
    g2.globalAlpha = k * clamp(0.25 + m / 40);
    g2.beginPath(); g2.moveTo(x, y); g2.lineTo(x + sx, y + sy); g2.stroke();
    g2.beginPath(); g2.arc(x, y, 3, 0, Math.PI * 2); g2.fill();
  }
  // sparkline of camera motion over the clip
  const sx0 = VX, sy0 = VY + VH + 160, sw = VW, sh = 90;
  g2.globalAlpha = k; g2.strokeStyle = 'rgba(116,215,255,0.9)'; g2.lineWidth = 3; g2.beginPath();
  flow.global.forEach(([dx, dy], i) => { const m = Math.hypot(dx * 640, dy * 360); const x = sx0 + i / (flow.n - 1) * sw, y = sy0 - Math.min(m / 4, 1) * sh; if (i === 0) g2.moveTo(x, y); else g2.lineTo(x, y); });
  g2.stroke();
  const cx = sx0 + Math.round(f) / (flow.n - 1) * sw; g2.fillStyle = '#ffffff'; g2.fillRect(cx - 2, sy0 - sh - 10, 4, sh + 20);
  g2.globalAlpha = 1;
}
function drawDepth(k) {
  g2.globalAlpha = k * 0.5; g2.drawImage(depthImg, VX, VY, VW, VH); g2.globalAlpha = 1;
  // colour bar (turbo, near -> far)
  const bx = VX + VW - 640, by = VY + VH + 60;
  const grd = g2.createLinearGradient(bx, 0, bx + 600, 0);
  ['#30123b', '#4686fb', '#1be5b5', '#a4fc3c', '#fbb938', '#e4460a', '#7a0403'].forEach((c, i) => grd.addColorStop(i / 6, c));
  g2.globalAlpha = k; g2.fillStyle = grd; g2.fillRect(bx, by, 600, 16);
  g2.font = "400 22px 'JetBrains Mono'"; g2.fillStyle = 'rgba(238,243,255,0.7)'; g2.fillText('NEAR', bx, by + 48); g2.fillText('FAR', bx + 555, by + 48);
  g2.globalAlpha = 1;
}
function drawContact(f, k, t) {
  const h = (hands.frames[Math.round(f)] || [])[0];
  if (!h) return;
  for (const idx of [4, 8, 12]) {
    const [x, y] = P(h.img[idx]);
    const r = 46 + 10 * Math.sin(t * 5 + idx);
    g2.globalAlpha = k; g2.strokeStyle = '#ffb547'; g2.lineWidth = 4; g2.setLineDash([10, 10]);
    g2.beginPath(); g2.arc(x, y, r, 0, Math.PI * 2); g2.stroke(); g2.setLineDash([]);
    g2.font = "600 44px 'Inter Display'"; g2.fillStyle = '#ffb547'; g2.fillText('?', x + r * 0.75, y - r * 0.75);
  }
  g2.globalAlpha = 1;
}

export async function render(t, ctx) {
  camera.position.set(0, 0, 5); camera.lookAt(0, 0, 0);
  ctx.clear2d();
  const vk = smooth(remap(t, 0.2, 1.4)) * (1 - smooth(remap(t, 29.3, 30)));
  const f = srcFrame(t);
  // dim the footage while analysis layers are on, keep it bright during the intro
  const dimK = 1 - 0.28 * smooth(remap(t, 4.0, 5.0)) * (1 - smooth(remap(t, 25.4, 26.4)));
  await drawFrame(f, vk * dimK);
  g2.globalAlpha = vk; g2.strokeStyle = 'rgba(160,190,255,0.35)'; g2.lineWidth = 2; g2.strokeRect(VX, VY, VW, VH); g2.globalAlpha = 1;
  const b1 = Math.min(smooth((t - 4.4) / 0.6), smooth((9.6 - t) / 0.5));
  const b2 = Math.min(smooth((t - 9.6) / 0.6), smooth((14.6 - t) / 0.5));
  const b3 = Math.min(smooth((t - 14.8) / 0.6), smooth((19.6 - t) / 0.5));
  const b4 = Math.min(smooth((t - 19.8) / 0.6), smooth((25.2 - t) / 0.5));
  if (b1 > 0) drawHands(f, b1 * vk, t);
  if (b2 > 0) drawFlow(f, b2 * vk);
  if (b3 > 0) drawDepth(b3 * vk);
  if (b4 > 0) { drawHands(f, b4 * vk * 0.5, t); drawContact(f, b4 * vk, t); }
  [b1, b2, b3, b4].forEach((b, i) => fadeEl(steps[i], b, { blur: 10, dy: 20 }));
  head.update(t, 0.8, 4.3); sub.update(t, 2.2, 4.3);
  fadeEl(verdict, smooth(remap(t, 25.6, 26.4)) * (1 - smooth(remap(t, 29.2, 29.9))), { blur: 14, dy: 20 });
  spark.textContent = `EgoDex · basic_pick_place · frame ${String(Math.round(f)).padStart(3, '0')} / 301 · ${(f / 30).toFixed(2)} s` + (t >= 14.5 && t < 19.5 ? ' · FREEZE' : t < 25 ? ' · 0.4× slow motion' : '');
  fadeEl(spark, vk * 0.9);
  chapter.update(t, 0.4, 29.4);
  ctx.grade.uFade.value = 1;
  ctx.bloomCfg.strength = 0.5;
  ctx.render(scene, camera);
}
