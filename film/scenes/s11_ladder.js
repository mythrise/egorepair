// S11 — Release levels (spec M10.3) and the risk-certification bound (spec M10.2).
import { THREE, el, clamp, lerp, remap, smooth, easeOutCubic, easeInOutCubic, easeInCubic, easeOutExpo, rng } from '@engine/core.js';
import { makeHaze, makePanel, Ribbon, makePoints, toScreen, spectralColor } from '@engine/fx.js';
import { Title, Chapter, fadeEl } from '@engine/ui.js';

export const duration = 16;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const LV = [
  ['REFERENCE_ONLY', 'source-bound reference', '仅参考', '#9aa6bd'],
  ['MODEL_QUALIFIED', 'model & kinematic gates passed', '模型合格', '#74d7ff'],
  ['SIM_REPLAY_QUALIFIED', 'unassisted physics replay passed', '仿真回放合格', '#67e3c9'],
  ['POLICY_EVALUATED', 'frozen-protocol policy evaluation', '策略已评测', '#a98bff'],
  ['RISK_CERTIFIED', 'statistical risk bound met', '风险认证', '#ffb27a'],
];
let scene, camera, pillars = [], labels = [], samples, title, chapter, chartT, chartBox, g2, note, ladderSub;

export async function init(ctx) {
  scene = new THREE.Scene();
  scene.add(makeHaze({ top: '#060b18', bottom: '#010204', glow: '#141a3a', glowK: 0.4 }));
  camera = new THREE.PerspectiveCamera(32, ctx.W / ctx.H, 0.05, 200);
  g2 = ctx.g2;
  LV.forEach(([n, d, z, c], i) => {
    const h = 0.45 + i * 0.32;
    const p = makePanel(0.62, h, { radius: 0.025, border: 0.006, borderColor: c, borderI: 1.4 });
    p.userData.mat.uniforms.uBright.value = 0; p.userData.h = h;
    p.position.set(-2.0 + i * 1.0, h / 2, 0); scene.add(p);
    const cap = new Ribbon([V(-0.31, h, 0.001), V(0.31, h, 0.001)].map((v) => v.add(V(-2.0 + i * 1.0, 0, 0))), { width: 8, color: c, intensity: 3, glow: 0.5 }); scene.add(cap.mesh);
    pillars.push({ p, cap, c, h, x: -2.0 + i * 1.0 });
    labels.push(el(ctx.ui, 'abs', `<div class="mono" style="font-size:25px;color:${c};letter-spacing:0.06em">${n}</div><div style="font-size:30px;font-weight:300;margin-top:10px;color:rgba(238,243,255,0.85)">${d}</div><div class="zh-s" style="font-size:28px;margin-top:8px">${z}</div>`, { width: '560px', textAlign: 'center' }));
  });
  // samples distributed by the level each has actually earned (illustrative counts, not a dataset statistic)
  const r = rng(3), N = 340; samples = makePoints(N, { soft: 0.4 }); scene.add(samples);
  samples.seeds = [];
  for (let i = 0; i < N; i++) {
    const u = r(); const lvl = u < 0.42 ? 0 : u < 0.72 ? 1 : u < 0.9 ? 2 : u < 0.985 ? 3 : 4;
    samples.seeds.push([lvl, (r() - 0.5) * 0.5, r(), (r() - 0.5) * 0.2, r()]);
    samples.geometry.attributes.size.setX(i, 0.022);
  }
  title = new Title(ctx.ui, { en: 'Every sample earns its level.', zh: '每条数据，凭各自的证据获得发布级别', y: 300, size: 132 });
  ladderSub = el(ctx.ui, 'abs mono', 'FIVE RELEASE LEVELS · EACH GATED INDEPENDENTLY · VERSIONS ARE NEVER OVERWRITTEN IN PLACE', { left: '0px', width: '3840px', textAlign: 'center', top: '1980px', fontSize: '24px', color: 'rgba(238,243,255,0.55)' });
  chapter = new Chapter(ctx.ui, '04', 'THE RESULT', '成果');
  chartT = new Title(ctx.ui, { en: 'Risk is certified, not claimed.', zh: '风险必须被认证，而不是被宣称', y: 300, size: 132 });
  note = el(ctx.ui, 'abs', '', { left: '2380px', top: '760px', width: '1350px' });
}

function drawChart(t, a) {
  const k = smooth(remap(t, a, a + 0.6)) * (1 - smooth(remap(t, 15.4, 16)));
  if (k <= 0) { note.style.opacity = 0; return; }
  const x0 = 360, y0 = 1820, W = 1880, H = 1080; // plot area (design px)
  const nMax = 600, uMax = 0.05;
  const X = (n) => x0 + n / nMax * W, Y = (u) => y0 - u / uMax * H;
  g2.globalAlpha = k;
  g2.strokeStyle = 'rgba(238,243,255,0.25)'; g2.lineWidth = 2;
  g2.beginPath(); g2.moveTo(x0, y0 - H - 20); g2.lineTo(x0, y0); g2.lineTo(x0 + W + 20, y0); g2.stroke();
  g2.font = "400 24px 'JetBrains Mono'"; g2.fillStyle = 'rgba(238,243,255,0.55)';
  for (const n of [0, 100, 200, 300, 400, 500, 600]) { g2.fillText(String(n), X(n) - 18, y0 + 44); g2.fillRect(X(n), y0, 2, 10); }
  for (const u of [0, 0.01, 0.02, 0.03, 0.04, 0.05]) { g2.fillText((u * 100).toFixed(0) + '%', x0 - 80, Y(u) + 8); }
  g2.fillText('INDEPENDENT ACCEPTED GROUPS WITH ZERO HARM  (n)', x0 + 400, y0 + 100);
  g2.save(); g2.translate(x0 - 130, y0 - H / 2 + 260); g2.rotate(-Math.PI / 2); g2.fillText('95% UPPER BOUND ON HARM RATE', 0, 0); g2.restore();
  // 1% target line
  g2.setLineDash([14, 12]); g2.strokeStyle = 'rgba(255,178,122,0.8)'; g2.lineWidth = 3;
  g2.beginPath(); g2.moveTo(x0, Y(0.01)); g2.lineTo(x0 + W, Y(0.01)); g2.stroke(); g2.setLineDash([]);
  g2.fillStyle = '#ffb27a'; g2.fillText('TARGET 1%', x0 + W - 170, Y(0.01) - 18);
  // curve u(n) = 1 - alpha^(1/n)
  const draw = easeInOutCubic(remap(t, a + 0.5, a + 3.0));
  const nEnd = draw * nMax;
  g2.strokeStyle = '#eef3ff'; g2.lineWidth = 5; g2.shadowColor = '#74d7ff'; g2.shadowBlur = 18;
  g2.beginPath();
  const n0 = Math.log(0.05) / Math.log(1 - uMax);
  for (let n = n0; n <= Math.max(nEnd, n0 + 1); n += 2) { const u = 1 - Math.pow(0.05, 1 / n); const px = X(n), py = Y(u); if (n === n0) g2.moveTo(px, py); else g2.lineTo(px, py); }
  g2.stroke(); g2.shadowBlur = 0;
  // 299 marker
  const m = smooth(remap(t, a + 2.2, a + 2.8));
  if (m > 0) {
    const px = X(299), py = Y(1 - Math.pow(0.05, 1 / 299));
    g2.globalAlpha = k * m;
    g2.strokeStyle = '#ffb27a'; g2.lineWidth = 3; g2.beginPath(); g2.moveTo(px, py); g2.lineTo(px, y0); g2.stroke();
    g2.fillStyle = '#ffb27a'; g2.beginPath(); g2.arc(px, py, 14 + 4 * Math.sin(t * 6), 0, Math.PI * 2); g2.fill();
    g2.font = "300 120px 'Inter Display'"; g2.fillStyle = '#ffffff'; g2.fillText('299', px + 30, py - 50);
  }
  g2.globalAlpha = 1;
  const nk = smooth(remap(t, a + 2.6, a + 3.3));
  note.style.opacity = (k * nk).toFixed(3);
  note.innerHTML = `<div class="mono" style="font-size:26px;color:#ffb27a;letter-spacing:0.14em">RISK_CERTIFIED · ONE-SIDED CLOPPER–PEARSON · α = 0.05</div>
    <div style="font-size:58px;font-weight:300;margin-top:30px;line-height:1.25">Zero harm across <b style="font-weight:600">299</b> independent accepted groups — not 299 frames — before claiming a risk below 1%.</div>
    <div class="zh-s" style="font-size:36px;margin-top:30px;line-height:1.6">299 个独立接受组零伤害，才可声称风险 &lt; 1%</div>
    <div class="mono" style="font-size:26px;margin-top:40px;color:rgba(238,243,255,0.7);text-transform:none">Evidence short of that → <span style="color:#ff4d5e">risk_certified = false</span>. Reported, never rounded up.</div>`;
}

export async function render(t, ctx) {
  const A = 7.6; // chart starts
  const cam = smooth(remap(t, 0, 7.5));
  camera.position.set(lerp(-1.4, 0.6, cam), lerp(1.1, 1.5, cam), lerp(5.8, 5.2, cam));
  camera.lookAt(lerp(-0.4, 0.2, cam), 0.85, 0);
  const ladK = smooth(remap(t, 0.8, 1.6)) * (1 - smooth(remap(t, 7.0, 7.7)));
  pillars.forEach((P, i) => {
    const on = smooth(remap(t, 1.0 + i * 0.55, 1.6 + i * 0.55));
    const u = P.p.userData.mat.uniforms;
    u.uOpacity.value = 0.55 * ladK * on; u.uBorderI.value = 1.6 * on;
    P.p.scale.y = lerp(0.02, 1, easeOutCubic(on)); P.p.position.y = P.h * P.p.scale.y / 2;
    P.cap.mesh.position.y = (P.p.scale.y - 1) * P.h;
    P.cap.set({ opacity: ladK * on });
    const s = toScreen(V(P.x, P.h * P.p.scale.y + 0.18, 0), camera);
    const lk = ladK * smooth(remap(t, 1.4 + i * 0.55, 2.0 + i * 0.55));
    labels[i].style.left = (s.x - 280) + 'px'; labels[i].style.top = (s.y - 150) + 'px'; labels[i].style.opacity = lk.toFixed(3);
    labels[i].style.display = lk > 0.01 ? '' : 'none';
  });
  const g = samples.geometry;
  samples.seeds.forEach(([lvl, dx, ph, dz, sp], i) => {
    const P = pillars[lvl];
    const rise = easeOutCubic(remap(t, 3.4 + ph * 1.2, 4.8 + ph * 1.2));
    const y = 0.04 + (P.h - 0.1) * ((ph * 7.3 + t * 0.05 * sp) % 1) * rise;
    g.attributes.position.setXYZ(i, P.x + dx * 0.9, y, dz);
    const c = new THREE.Color(P.c);
    g.attributes.color.setXYZ(i, c.r * 2.2, c.g * 2.2, c.b * 2.2);
    g.attributes.alpha.setX(i, ladK * smooth(remap(t, 3.2 + ph, 3.6 + ph)) * (lvl === 4 ? 1 : 0.85));
  });
  for (const a of ['position', 'color', 'alpha']) g.attributes[a].needsUpdate = true;
  title.update(t, 0.4, 7.4);
  fadeEl(ladderSub, smooth(remap(t, 2.0, 2.8)) * (1 - smooth(remap(t, 7.0, 7.6))));
  chartT.update(t, A, 15.8);
  chapter.update(t, 0.3, 15.6);
  ctx.clear2d();
  drawChart(t, A + 0.3);
  ctx.grade.uFade.value = smooth(remap(t, 0, 0.5)) * (1 - easeInCubic(remap(t, 15.4, 16)));
  ctx.bloomCfg.strength = 0.8;
  ctx.render(scene, camera);
}
