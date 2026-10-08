// S06 — Title: the iridescent ring ignites; broken red trajectories pass through it and leave clean.
import { THREE, el, rng, clamp, remap, smooth, smoother, easeOutCubic, easeInOutCubic, easeOutExpo, easeInCubic, lerp, splitChars, revealChars } from '@engine/core.js';
import { makeRing, makeHalo, makePoints, Ribbon, spectralColor, makeHaze, COL } from '@engine/fx.js';
import { fadeEl } from '@engine/ui.js';

export const duration = 13;
let scene, camera, ring, ring2, halo, halo2, orbit, streams = [], title, sub, zh, flash;
const R = 2.0;

function noise1(x, s) { return Math.sin(x * 1.7 + s) * 0.5 + Math.sin(x * 3.1 + s * 2.3) * 0.3 + Math.sin(x * 7.3 + s * 0.7) * 0.2; }

export async function init(ctx) {
  scene = new THREE.Scene();
  scene.add(makeHaze({ top: '#070b16', bottom: '#010204', glow: '#1a1640', glowDir: new THREE.Vector3(0, 0, 1), glowK: 0.5 }));
  camera = new THREE.PerspectiveCamera(32, ctx.W / ctx.H, 0.05, 1000);

  // ring lies in the YZ plane (axis = +x, the flow direction)
  ring = makeRing({ radius: R, tube: 0.016, intensity: 5 });
  ring.rotation.y = Math.PI / 2;
  scene.add(ring);
  ring2 = makeRing({ radius: R * 1.035, tube: 0.004, intensity: 2.2 });
  ring2.rotation.y = Math.PI / 2;
  scene.add(ring2);
  halo = makeHalo({ size: R * 3.4, ringR: 0.59, ringW: 0.09, intensity: 0.5, color: '#8f7dff' });
  halo.userData.mat.uniforms.uSpectral.value = 1;
  halo.rotation.y = Math.PI / 2; scene.add(halo);
  halo2 = makeHalo({ size: R * 1.4, intensity: 0.0, color: '#cfd8ff' });
  halo2.rotation.y = Math.PI / 2; scene.add(halo2);

  // orbiting spectral dust
  const N = 5000, r = rng(11);
  orbit = makePoints(N, { additive: true, soft: 0.7 });
  const og = orbit.geometry;
  orbit.userData.seed = [];
  for (let i = 0; i < N; i++) {
    const a = r() * Math.PI * 2, rr = R * (1 + (r() - 0.5) * 0.16 * (r() < 0.8 ? 0.5 : 2.5)), w = (r() - 0.5) * 0.12, sp = 0.08 + r() * 0.2;
    orbit.userData.seed.push([a, rr, w, sp, r()]);
    const c = spectralColor(a / (Math.PI * 2));
    og.attributes.color.setXYZ(i, c.r * 1.6, c.g * 1.6, c.b * 1.6);
    og.attributes.size.setX(i, 0.006 + r() * 0.012);
  }
  scene.add(orbit);

  // streams: broken (red, jagged) before the ring plane x<0, clean (white/cyan) after
  const rs = rng(5);
  for (let k = 0; k < 46; k++) {
    const y0 = (rs() - 0.5) * 7, z0 = (rs() - 0.5) * 7, seed = rs() * 100;
    const ang = rs() * Math.PI * 2, rad = Math.sqrt(rs()) * R * 0.78;
    const ye = Math.cos(ang) * rad, ze = Math.sin(ang) * rad;
    const pts = [], n = 160;
    for (let i = 0; i < n; i++) {
      const s = i / (n - 1);
      const x = lerp(-14, 10, s);
      let y, z;
      if (x < 0) {
        const f = smoother(remap(x, -14, -0.3));
        const jag = (1 - f) * 0.9;
        y = lerp(y0, ye, f) + noise1(x * 1.3, seed) * jag + (Math.floor(x * 2.5 + seed) % 2 ? 0.08 : -0.08) * (1 - f);
        z = lerp(z0, ze, f) + noise1(x * 1.1, seed + 5) * jag;
      } else {
        const f = smooth(remap(x, 0, 10));
        y = ye * (1 + f * 0.25); z = ze * (1 + f * 0.25);
      }
      pts.push(new THREE.Vector3(x, y, z));
    }
    const colors = (i, u) => {
      const x = lerp(-14, 10, u);
      const g = smooth(remap(x, -0.6, 0.6));
      const red = [1.0, 0.25, 0.3], cl = k % 3 === 0 ? [0.55, 0.85, 1.0] : [0.92, 0.95, 1.0];
      const a = smooth(remap(u, 0, 0.12)) * smooth(remap(1 - u, 0, 0.15));
      return [lerp(red[0], cl[0], g), lerp(red[1], cl[1], g), lerp(red[2], cl[2], g), a];
    };
    const rb = new Ribbon(pts, { width: 3 + rs() * 3, intensity: 1.6, glow: 0.3, colors });
    rb.speed = 0.6 + rs() * 0.5; rb.delay = rs() * 1.6; rb.len = 0.18 + rs() * 0.2;
    streams.push(rb); scene.add(rb.mesh);
  }

  // typography
  const wrap = el(ctx.ui, 'abs center', '', { left: '0px', width: '3840px', top: '0px', height: '2160px' });
  title = el(wrap, 'abs h1', '', { left: '0px', width: '3840px', top: '880px', fontSize: '330px', fontWeight: 600, letterSpacing: '-0.045em' });
  title.spans = splitChars(title, 'EgoRepair');
  sub = el(wrap, 'abs', 'Multi-agent repair for egocentric robot data', { left: '0px', width: '3840px', top: '1300px', fontSize: '64px', fontWeight: 300, letterSpacing: '0.01em', color: 'rgba(238,243,255,0.86)' });
  zh = el(wrap, 'abs zh', '多智能体协同修复 · 让第一人称视频成为机器人训练数据', { left: '0px', width: '3840px', top: '1420px', fontSize: '46px' });
  flash = el(ctx.ui, 'abs', '', { left: '0px', top: '0px', width: '3840px', height: '2160px', background: 'radial-gradient(circle at 50% 50%, rgba(220,228,255,0.9), rgba(160,140,255,0.25) 30%, rgba(0,0,0,0) 60%)' });
}

export async function render(t, ctx) {
  // camera: oblique flow view -> face-on halo
  const k = easeInOutCubic(remap(t, 3.6, 7.2));
  const az = lerp(0.95, 1.5708, k), el_ = lerp(0.12, 0.0, k), dist = lerp(10.5, 13.2, k) - remap(t, 7.2, 13) * 1.6 - easeInCubic(remap(t, 11.6, 13)) * 9;
  camera.position.set(Math.cos(az) * dist * 1.0 + 0.2, Math.sin(el_) * dist + 0.1, Math.sin(az) * dist);
  // face-on means looking along -x... ring axis is x; we orbit around y so at az=pi/2 we look from +z.
  // rotate ring so that at the end its axis points to camera
  ring.rotation.y = halo.rotation.y = ring2.rotation.y = halo2.rotation.y = lerp(Math.PI / 2, 0, k);
  camera.lookAt(lerp(0.6, 0, k), 0, 0);

  // ignition
  const ign = remap(t, 0.6, 2.6);
  const arc = easeOutExpo(ign);
  for (const rr of [ring, ring2]) {
    const u = rr.userData.mat.uniforms;
    u.uTime.value = t; u.uArc.value = arc; u.uArcStart.value = 0.25 - arc * 0.5;
    u.uOpacity.value = smooth(remap(t, 0.5, 0.9));
  }
  ring.userData.mat.uniforms.uIntensity.value = 5 + 10 * Math.exp(-Math.pow((t - 2.6) * 2.2, 2));
  halo.userData.mat.uniforms.uI.value = 0.55 * smooth(remap(t, 1.6, 3.2)) * (1 + 0.15 * Math.sin(t * 2));
  halo.userData.mat.uniforms.uTime.value = t;
  halo2.userData.mat.uniforms.uI.value = 1.8 * Math.exp(-Math.pow((t - 2.65) * 2.5, 2));

  // orbit dust
  const og = orbit.geometry, S = orbit.userData.seed;
  const dustK = smooth(remap(t, 2.0, 4.0));
  for (let i = 0; i < S.length; i++) {
    const [a0, rr, w, sp, ph] = S[i];
    const a = a0 + t * sp;
    const burst = 1 + 0.35 * Math.exp(-Math.pow((t - 2.7) * 1.6, 2)) * ph;
    // ring local: circle in plane spanned by y and z' (ring rotates with k)
    const cy = Math.cos(a) * rr * burst, cz = Math.sin(a) * rr * burst;
    const ry = ring.rotation.y;
    og.attributes.position.setXYZ(i, w * Math.cos(ry) + cz * Math.sin(ry), cy, -w * Math.sin(ry) + cz * Math.cos(ry));
    og.attributes.alpha.setX(i, dustK * (0.35 + 0.65 * ph) * (0.6 + 0.4 * Math.sin(t * 3 + i)));
  }
  og.attributes.position.needsUpdate = true; og.attributes.alpha.needsUpdate = true;

  // streams flow through the ring
  const sk = 1 - smooth(remap(t, 6.0, 7.4));
  for (const s of streams) {
    const p = (t - 0.4 - s.delay) * s.speed * 0.32;
    s.set({ head: p, tail: p - s.len - 0.25, opacity: sk * smooth(remap(t, 0.0, 1.2)), headGlow: 2.0 });
  }

  // title
  const tp = remap(t, 5.6, 7.4);
  revealChars(title.spans, tp, { stagger: 0.06, dur: 0.5, rise: 60, blur: 30 });
  const out = easeInCubic(remap(t, 11.4, 12.6));
  fadeEl(sub, smooth(remap(t, 6.9, 8.0)) * (1 - out), { blur: 12, dy: 20 });
  fadeEl(zh, smooth(remap(t, 7.4, 8.6)) * (1 - out), { blur: 12, dy: 20 });
  title.style.opacity = (1 - out).toFixed(3);
  title.style.filter = out > 0.01 ? `blur(${(out * 30).toFixed(1)}px)` : 'none';
  title.style.transform = `scale(${(1 + out * 0.08).toFixed(4)})`;
  fadeEl(flash, 0.55 * Math.exp(-Math.pow((t - 2.65) * 3.0, 2)));

  ctx.grade.uFade.value = smooth(remap(t, 0, 0.4)) * (1 - easeInCubic(remap(t, 12.4, 13)));
  ctx.bloomCfg.strength = 1.0; ctx.bloomCfg.threshold = 0.7;
  ctx.render(scene, camera);
}
