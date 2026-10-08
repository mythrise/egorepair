// S01 — Cold open: a spectral hairline opens like a shutter onto real first-person footage.
import { THREE, el, clamp, lerp, remap, smooth, easeOutCubic, easeInOutCubic, easeInCubic, easeOutExpo, loadImage } from '@engine/core.js';
import { makeHaze } from '@engine/fx.js';
import { Title, fadeEl } from '@engine/ui.js';

export const duration = 14;
// footage list: when more EgoDex tasks are available, add entries here (dir, frame count, start frame)
const CLIPS = [
  { dir: '/assets/footage/ego_raw', n: 302, from: 0, rate: 0.55, t0: 0, label: 'basic_pick_place_117' },
  { dir: '/assets/footage/m_pour_32', n: 66, from: 0, rate: 0.8, t0: 4.6, label: 'pour_32' },
  { dir: '/assets/footage/m_stack_unstack_cups_5', n: 66, from: 0, rate: 0.8, t0: 6.2, label: 'stack_unstack_cups_5' },
  { dir: '/assets/footage/m_legos_33', n: 66, from: 0, rate: 0.8, t0: 7.8, label: 'assemble_disassemble_legos_33' },
  { dir: '/assets/footage/m_fold_paper_10', n: 66, from: 0, rate: 0.8, t0: 9.3, label: 'fold_unfold_paper_basic_10' },
  { dir: '/assets/footage/m_screw_allen_10', n: 66, from: 0, rate: 0.8, t0: 10.7, label: 'screw_unscrew_allen_fixture_10' },
  { dir: '/assets/footage/m_sort_beads_1', n: 66, from: 0, rate: 0.8, t0: 12.0, label: 'sort_beads_1' },
];
const clipAt = (t) => { let c = CLIPS[0]; for (const k of CLIPS) if (t >= k.t0) c = k; return c; };
let scene, camera, g2, line, t1, t2, lab;

async function drawFootage(t, x, y, w, h, alpha) {
  const C = clipAt(t);
  const f = C.from + (t - C.t0) * 30 * C.rate;
  const i = Math.floor(f), fr = f - i;
  const a = await loadImage(`${C.dir}/${String(clamp(i, 0, C.n - 1)).padStart(4, '0')}.jpg`);
  // cover-fit the 16:9 frame into the window, with a slow push-in
  const zoom = 1.04 + 0.06 * (t / duration);
  const sw = a.naturalWidth / zoom, sh = a.naturalHeight / zoom;
  const ar = w / h, sar = sw / sh;
  let cw = sw, ch = sh; if (ar > sar) ch = sw / ar; else cw = sh * ar;
  const cx = (a.naturalWidth - cw) / 2, cy = (a.naturalHeight - ch) / 2;
  g2.imageSmoothingEnabled = true; g2.imageSmoothingQuality = 'high';
  g2.globalAlpha = alpha; g2.drawImage(a, cx, cy, cw, ch, x, y, w, h);
  if (fr > 0.02 && i + 1 < C.n) { const b = await loadImage(`${C.dir}/${String(i + 1).padStart(4, '0')}.jpg`); g2.globalAlpha = alpha * fr; g2.drawImage(b, cx, cy, cw, ch, x, y, w, h); }
  g2.globalAlpha = 1;
}

export async function init(ctx) {
  scene = new THREE.Scene();
  scene.add(makeHaze({ top: '#03050a', bottom: '#010102', glow: '#0a0f1e', glowK: 0.2 }));
  camera = new THREE.PerspectiveCamera(35, ctx.W / ctx.H, 0.1, 100);
  g2 = ctx.g2;
  line = el(ctx.ui, 'abs', '', { left: '0px', top: '1079px', width: '3840px', height: '3px',
    background: 'linear-gradient(90deg, rgba(0,0,0,0), #ffb27a 15%, #ff7eb6 32%, #a98bff 50%, #6cb8ff 68%, #67e3c9 85%, rgba(0,0,0,0))', boxShadow: '0 0 40px rgba(169,139,255,0.9)' });
  t1 = new Title(ctx.ui, { en: 'Every day, humans demonstrate dexterity.', zh: '人类每天都在演示灵巧的操作', y: 1080, size: 132 });
  t2 = new Title(ctx.ui, { en: 'Robots could learn from all of it.', zh: '机器人，本可以从中学会一切', y: 1080, size: 132 });
  lab = el(ctx.ui, 'abs mono', '', { left: '150px', top: '1960px', fontSize: '24px', color: 'rgba(238,243,255,0.65)', textTransform: 'none' });
}

export async function render(t, ctx) {
  camera.position.set(0, 0, 5); camera.lookAt(0, 0, 0);
  ctx.clear2d();
  // hairline grows, then opens into a 2.39:1 window, then to near full frame; at the end it collapses into a tile
  const grow = easeOutExpo(remap(t, 0.4, 1.8));
  const open = easeInOutCubic(remap(t, 1.6, 3.4));
  const full = easeInOutCubic(remap(t, 7.6, 9.4));
  const shrink = easeInOutCubic(remap(t, 12.4, 14));
  let h = lerp(0, 1606, open); h = lerp(h, 2160, full);
  let w = 3840;
  // collapse into a centred tile (handoff to the next shot)
  w = lerp(w, 256 * 1.6, shrink); h = lerp(h, 144 * 1.6, shrink);
  const x = (3840 - w) / 2, y = (2160 - h) / 2;
  line.style.width = (3840 * grow) + 'px'; line.style.left = ((3840 - 3840 * grow) / 2) + 'px';
  line.style.top = (1079 - h / 2) + 'px';
  line.style.opacity = (smooth(remap(t, 0.3, 0.8)) * (1 - smooth(remap(t, 3.0, 3.8)))).toFixed(3);
  if (h > 1) await drawFootage(t, x, y, w, h, 1);
  // cinematic darkening behind titles
  const dk = Math.max(Math.min(smooth((t - 3.6) / 0.6), smooth((7.6 - t) / 0.6)), Math.min(smooth((t - 8.6) / 0.6), smooth((12.4 - t) / 0.6)));
  if (dk > 0) { const grd = g2.createRadialGradient(1920, 1080, 200, 1920, 1080, 1900); grd.addColorStop(0, `rgba(0,0,0,${0.55 * dk})`); grd.addColorStop(1, `rgba(0,0,0,${0.25 * dk})`); g2.fillStyle = grd; g2.fillRect(x, y, w, h); }
  t1.update(t, 3.6, 7.8);
  t2.update(t, 8.6, 12.4);
  lab.textContent = 'EgoDex · original 1920×1080 · ' + clipAt(t).label;
  fadeEl(lab, smooth(remap(t, 3.0, 4.0)) * (1 - smooth(remap(t, 12.6, 13.0))));
  // brief flash-cut accent between montage clips
  for (const k of CLIPS.slice(1)) { const d = t - k.t0; if (d >= 0 && d < 0.12) { g2.fillStyle = `rgba(255,255,255,${(0.18 * (1 - d / 0.12)).toFixed(3)})`; g2.fillRect(x, y, w, h); } }
  ctx.grade.uFade.value = 1;
  ctx.bloomCfg.strength = 0.4;
  ctx.render(scene, camera);
}
