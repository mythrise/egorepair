// S05 — The storm: every episode fails differently; repairing by hand does not scale.
import { THREE, el, clamp, lerp, remap, smooth, easeInCubic, easeOutCubic, easeInOutCubic, rng } from '@engine/core.js';
import { MultiRibbon, makeHaze, toScreen } from '@engine/fx.js';
import { Title, fadeEl } from '@engine/ui.js';

export const duration = 10;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
let scene, camera, storm, tags = [], t1, t2, counter;
const FAIL = ['IK FAIL', 'TABLE PENETRATION', 'TRACKING JITTER', 'SCALE UNKNOWN', 'HAND OCCLUDED', 'NO JOINT STATE q', 'OBJECT SLIPPED',
  'ORIENTATION MISSING', 'CLOCK MISALIGNED', 'CONTACT UNVERIFIED', 'BASE UNREACHABLE', 'CAMERA DRIFT', 'COLLISION', 'GRIPPER WIDTH ?'];

export async function init(ctx) {
  scene = new THREE.Scene();
  scene.add(makeHaze({ top: '#0d0710', bottom: '#020203', glow: '#2a0a12', glowK: 0.35 }));
  camera = new THREE.PerspectiveCamera(40, ctx.W / ctx.H, 0.02, 500);
  const r = rng(9), lines = [];
  const N = 1700;
  for (let k = 0; k < N; k++) {
    // order: first line is near the camera, later lines spread wider and deeper
    const tier = k < 1 ? 0 : k < 10 ? 1 : k < 100 ? 2 : 3;
    const spread = [0.2, 1.5, 4, 9][tier];
    const c = V((r() - 0.5) * spread * 2, (r() - 0.5) * spread * 1.1, -2 - r() * spread * 2.2 - tier * 1.5);
    let p = c.clone(), dir = V(r() - 0.5, r() - 0.5, r() - 0.5).normalize();
    const pts = [], n = 70, step = 0.04 + r() * 0.05;
    for (let i = 0; i < n; i++) {
      // smooth hand-like motion with tracking jumps and jitter
      dir.add(V(r() - 0.5, r() - 0.5, r() - 0.5).multiplyScalar(0.5)).normalize();
      p = p.clone().addScaledVector(dir, step);
      const q = p.clone();
      if (r() < 0.06) q.add(V(r() - 0.5, r() - 0.5, r() - 0.5).multiplyScalar(0.25));
      q.add(V(r() - 0.5, r() - 0.5, r() - 0.5).multiplyScalar(0.012));
      pts.push(q);
    }
    const t0 = [0.3, 1.4, 2.6, 3.8][tier] + r() * [0.0, 0.8, 1.0, 2.6][tier];
    const red = 0.55 + 0.45 * r();
    lines.push({ pts, t0, speed: 0.6 + r() * 0.8, color: [1.0, 0.18 + 0.2 * (1 - red), 0.25 + 0.1 * r(), tier === 3 ? 0.42 : 1], width: tier === 0 ? 2.2 : tier === 1 ? 1.4 : 1 });
  }
  storm = new MultiRibbon(lines, { width: 3, color: '#ff5a66', intensity: 1.5, len: 0.65 });
  scene.add(storm.mesh);
  storm.lines = lines;
  // failure tags attached to specific lines
  for (let i = 0; i < 26; i++) {
    const li = i < 3 ? i : 10 + Math.floor(r() * 300);
    const e = el(ctx.ui, 'abs mono', '✕ ' + FAIL[i % FAIL.length], { fontSize: '24px', color: '#ff6b77', whiteSpace: 'nowrap', letterSpacing: '0.1em' });
    tags.push({ e, li, t0: 1.0 + i * 0.22 + r() * 0.2, dur: 1.2 + r() * 1.4 });
  }
  t1 = new Title(ctx.ui, { en: 'Every episode fails differently.', zh: '每一条数据，都以不同的方式失败', y: 920, size: 128 });
  t2 = new Title(ctx.ui, { en: 'Repairing by hand doesn’t scale.', zh: '人工修复，无法规模化', y: 1080, size: 150 });
  counter = el(ctx.ui, 'abs mono-n', '', { left: '150px', top: '1880px', fontSize: '34px', color: 'rgba(255,120,130,0.85)', letterSpacing: '0.1em' });
}

export async function render(t, ctx) {
  const push = easeInOutCubic(remap(t, 0, 10));
  camera.position.set(Math.sin(t * 0.21) * 0.3, Math.cos(t * 0.17) * 0.2, 1.2 - push * 7.5);
  camera.rotation.set(0, 0, Math.sin(t * 0.3) * 0.08);
  camera.updateMatrixWorld();
  storm.mat.uniforms.uT.value = t;
  storm.mat.uniforms.uOpacity.value = smooth(remap(t, 0, 0.5)) * (1 - smooth(remap(t, 9.55, 9.75)));
  storm.mat.uniforms.uLen.value = 0.4 + 0.6 * smooth(remap(t, 2, 6));
  tags.forEach((T) => {
    const L = storm.lines[T.li];
    const head = clamp((t - L.t0) * L.speed, 0, 1);
    const p = L.pts[Math.floor(head * (L.pts.length - 1))];
    const s = toScreen(p, camera);
    const k = Math.min(smooth((t - T.t0) / 0.15), smooth((T.t0 + T.dur - t) / 0.2)) * (t < 9.5 ? 1 : 0);
    const flick = 0.75 + 0.25 * Math.sign(Math.sin(t * 37 + T.li));
    T.e.style.display = k > 0.01 && !s.behind && s.x > 0 && s.x < 3840 && s.y > 0 && s.y < 2160 ? '' : 'none';
    T.e.style.left = (s.x + 18) + 'px'; T.e.style.top = (s.y - 16) + 'px'; T.e.style.opacity = (k * flick).toFixed(3);
  });
  const n = t < 1.4 ? 1 : t < 2.6 ? 10 : t < 3.8 ? 100 : Math.floor(lerp(100, 1700, smooth(remap(t, 3.8, 7))));
  counter.textContent = `${n.toLocaleString('en-US')} ${n === 1 ? 'EPISODE' : 'EPISODES'} · EACH NEEDS ITS OWN DIAGNOSIS`;
  fadeEl(counter, smooth(remap(t, 0.6, 1.2)) * (1 - smooth(remap(t, 9.4, 9.6))));
  t1.update(t, 1.6, 5.2);
  t2.update(t, 5.6, 9.6, { outDur: 0.25 });
  ctx.grade.uFade.value = smooth(remap(t, 0, 0.4)) * (1 - smooth(remap(t, 9.6, 9.75)));
  ctx.grade.uTint.value.set(1.05, 0.95, 0.95);
  ctx.bloomCfg.strength = 0.9; ctx.bloomCfg.threshold = 0.6;
  ctx.render(scene, camera);
}
