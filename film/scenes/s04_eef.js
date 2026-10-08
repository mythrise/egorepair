// S04 — Often only absolute end-effector poses survive. Real A2 hybrid output -> EEF triads -> real failure records.
import { THREE, el, clamp, lerp, remap, smooth, easeOutCubic, easeInOutCubic, easeInCubic, SeqTexture, loadJSON } from '@engine/core.js';
import { makePanel, makeTriad, Ribbon, makeHaze, makeGrid, toScreen } from '@engine/fx.js';
import { Title, Chapter, Callout, fadeEl } from '@engine/ui.js';
import { pixelToTable } from './lib/world.js';

export const duration = 26;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
let scene, camera, panel, seq, hands, meta, path = [], triads = [], pathRb, grid, title, t2, chapter, callL, callR, fails = [], foot, insp, inspSeq, inspLab;
const FAILS = [
  ['IK · RIGHT ARM · GEOMETRY FAIL', 'tool-only fallback, static reference', 0.18],
  ['FULL ORIENTATION 1,000 / 1,144', 'hand frames · missing orientation is not invented', 0.34],
  ['QUALIFIED q14 ROWS · 0', 'valid EEF, no qualified joint trajectory', 0.5],
  ['BLOCK–TABLE PENETRATION 3.226 mm', 'replay at original clock · STOP', 0.64],
  ['NET BLOCK MOTION 1.448 mm < 9.665 mm', 'physics gate passed, task not achieved', 0.78],
  ['DIFFUSION GLOBAL MERGE 0 / 7', 'learned repair alone did not close the gap', 0.92],
];

export async function init(ctx) {
  scene = new THREE.Scene();
  scene.add(makeHaze({ top: '#070912', bottom: '#010203', glow: '#1a0e1c', glowK: 0.3 }));
  camera = new THREE.PerspectiveCamera(34, ctx.W / ctx.H, 0.02, 100);
  meta = (await loadJSON('/assets/scene/ego0/meta.json'));
  hands = await loadJSON('/assets/data/hands_ego_raw.json');
  seq = new SeqTexture('/assets/footage/eef_ref', 302, { srcFps: 30 });
  panel = makePanel(1.6, 0.9, { radius: 0.02, border: 0.004, borderColor: '#9fb8ff', borderI: 0.6 });
  scene.add(panel);
  inspSeq = new SeqTexture('/assets/footage/inspect', 302, { srcFps: 30 });
  insp = makePanel(0.64, 0.36, { radius: 0.012, border: 0.003, borderColor: '#ff4d5e', borderI: 1.0 });
  scene.add(insp);

  // real absolute EEF (wrist) poses from the EgoDex HDF5 (ARKit world frame, metres), both hands
  const HD = await loadJSON('/assets/data/hdf5_hands.json');
  const mean = V(0, 0, 0); HD.leftHand.forEach((m) => mean.add(V(m[3], m[7], m[11]))); mean.multiplyScalar(1 / HD.n);
  const toPose = (m) => {
    const p = V(m[3], m[7], m[11]).sub(mean).add(V(-0.12, 0.12, -0.05));
    const R = new THREE.Matrix4().set(m[0], m[1], m[2], 0, m[4], m[5], m[6], 0, m[8], m[9], m[10], 0, 0, 0, 0, 1);
    return { p, q: new THREE.Quaternion().setFromRotationMatrix(R) };
  };
  for (let f = 0; f < HD.n; f++) path.push({ f, ...toPose(HD.leftHand[f]) });
  const right = [toPose(HD.rightHand[0]), toPose(HD.rightHand[150])];
  right.forEach((r) => { const tr = makeTriad(0.035, 3.5, 2.4); tr.position.copy(r.p); tr.quaternion.copy(r.q); tr.u = 0.98; triads.push(tr); scene.add(tr); });
  pathRb = new Ribbon(path.map((a) => a.p), { width: 3, color: '#eef3ff', intensity: 0.9 });
  scene.add(pathRb.mesh);
  let lastP = null;
  for (let i = 0; i < path.length; i += 3) { if (lastP && path[i].p.distanceTo(lastP) < 0.022) continue; lastP = path[i].p; const tr = makeTriad(0.035, 3.5, 2.4); tr.position.copy(path[i].p); tr.quaternion.copy(path[i].q); tr.u = i / path.length; triads.push(tr); scene.add(tr); }
  grid = makeGrid({ size: 6, cell: 0.1, major: 5, color: '#5f6f9f', opacity: 0.0, fade: 1.6 }); scene.add(grid);

  chapter = new Chapter(ctx.ui, '01', 'THE GAP', '鸿沟');
  el(ctx.ui, 'abs mono', 'eef_reference.mp4 · basic_pick_place_117 · absolute EEF reference rendered on the original view', { left: '150px', top: '2010px', fontSize: '22px', color: 'rgba(238,243,255,0.45)', textTransform: 'none' }).id = 'eefsrc';
  title = new Title(ctx.ui, { en: 'Often, all that survives is the end-effector pose.', zh: '很多时候，留下的只有末端位姿', x: 150, y: 250, align: 'left', size: 96, width: 3000, zhSize: 42 });
  t2 = new Title(ctx.ui, { en: 'Absolute poses. No arm. No contact. No scene.', zh: '只有绝对位姿：没有手臂、没有接触、没有场景', x: 150, y: 250, align: 'left', size: 96, width: 3000, zhSize: 42 });
  callL = new Callout(ui(ctx), { title: 'ABSOLUTE EEF POSE · NO ARM', sub: '只有绝对末端位姿，没有手臂', color: '#ff6b77', side: 'right', dx: 260, dy: -380 });
  callR = new Callout(ui(ctx), { title: 'NO JOINT STATES · NO BASE · NO CONTACT', sub: '没有关节状态、没有基座、没有接触', color: '#ff4d5e', side: 'left', dx: -260, dy: 160 });
  FAILS.forEach(([a, b, u], i) => fails.push({ u, c: new Callout(ctx.ui, { title: '✕ ' + a, sub: '', color: '#ff6b77', side: i % 2 ? 'left' : 'right', dx: i % 2 ? -220 : 220, dy: -140 - (i % 3) * 40, size: 34 }), sub: b }));
  fails.forEach((F) => { F.s = el(F.c.box, 'mono', F.sub, { fontSize: '22px', color: 'rgba(238,243,255,0.6)', marginTop: '10px', textTransform: 'none' }); });
  foot = el(ctx.ui, 'abs mono', 'FAILURE RECORDS QUOTED FROM THE PROJECT LEDGER · 以上均为项目台账中的真实失败记录', { left: '150px', top: '2030px', fontSize: '22px', color: 'rgba(238,243,255,0.5)' });
  inspLab = el(ctx.ui, 'abs mono', 'FIXED-BASE INSPECTION · <span style="color:#ff4d5e">GEOMETRY FAIL</span>', { fontSize: '24px', color: '#eef3ff', whiteSpace: 'nowrap' });
}
function ui(ctx) { return ctx.ui; }

export async function render(t, ctx) {
  // A: hybrid video panel facing the camera; B: camera dollies into the pose void
  const kB = easeInOutCubic(remap(t, 7.0, 10.5));
  const orbit = remap(t, 7, 26);
  const ctr = V(-0.12, 0.12, -0.05);
  const camA = V(0, 0.02, 2.25), tgtA = V(0, 0.16, 0);
  const ang = lerp(-0.25, 0.55, orbit);
  const camB = ctr.clone().add(V(Math.sin(ang) * 1.25, 0.55, -Math.cos(ang) * 1.25));
  camera.position.copy(camA.clone().lerp(camB, kB));
  camera.lookAt(tgtA.clone().lerp(ctr, kB));
  camera.updateMatrixWorld();
  // panel lives in front of camA
  panel.position.set(0, 0.08, 0); panel.lookAt(camA);
  const tex = await seq.at(t * 0.9);
  panel.userData.setMap(tex);
  const pu = panel.userData.mat.uniforms;
  pu.uOpacity.value = smooth(remap(t, 0, 0.8)) * (1 - smooth(remap(t, 7.4, 9.6)));
  pu.uBright.value = 1.0 - 0.3 * smooth(remap(t, 6.5, 8));
  // callouts on the hybrid frame: anchor to tracked hands in the same (time-aligned) frame
  const fi = Math.min(Math.floor(t * 0.9 * 30), 301);
  const hs = hands.frames[fi] || [];
  const toPanel = (p) => { const lp = V((p[0] - 0.5) * 1.6, (0.5 - p[1]) * 0.9, 0); return toScreen(lp.applyMatrix4(panel.matrixWorld), camera); };
  if (hs.length) {
    // the resting right hand is the lowest wrist in the frame; the other is the reaching left hand
    const R = hs.reduce((a, b) => (a.img[0][1] > b.img[0][1] ? a : b));
    const L = hs.length > 1 ? hs.find((h) => h !== R) : null;
    const kc = Math.min(smooth((t - 2.2) / 0.6), smooth((7.0 - t) / 0.5));
    const sR = toPanel(R.img[9]); callR.update(sR.x, sR.y, t > 2.2 && t < 7 ? kc : 0, t);
    if (L) { const sL = toPanel(L.img[9]); callL.update(sL.x, sL.y, t > 2.6 && t < 7 ? Math.min(smooth((t - 2.6) / 0.6), smooth((7.0 - t) / 0.5)) : 0, t); } else callL.update(0, 0, 0);
  } else { callR.update(0, 0, 0); callL.update(0, 0, 0); }
  // B: pose void
  const vk = smooth(remap(t, 8.0, 10.0)) * (1 - smooth(remap(t, 25.3, 26)));
  const draw = easeInOutCubic(remap(t, 8.2, 12.5));
  pathRb.set({ head: draw, opacity: vk * 0.5 });
  triads.forEach((tr) => { const k = vk * smooth(remap(draw, tr.u - 0.02, tr.u + 0.02)); tr.visible = k > 0.01; tr.userData.ribbons.forEach((r) => r.set({ opacity: k })); });
  grid.position.set(ctr.x, 0, ctr.z); grid.userData.mat.uniforms.uCenter.value.set(ctr.x, ctr.z); grid.userData.mat.uniforms.uOpacity.value = 0.08 * vk;
  // C: failure records along the path
  fails.forEach((F, i) => {
    const t0 = 14.2 + i * 1.45;
    const k = Math.min(smooth((t - t0) / 0.5), smooth((25.2 - t) / 0.5));
    const p = path[Math.floor(F.u * (path.length - 1))].p;
    const s = toScreen(p, camera);
    const left = i % 2 === 1; F.c.side = left ? 'left' : 'right'; F.c.dx = left ? -300 : 300; F.c.dy = [-420, -300, -180, 200, 320, 440][i];
    F.c.update(s.x, s.y, t > t0 ? k : 0, t);
  });
  fadeEl(foot, smooth(remap(t, 14.5, 15.3)) * (1 - smooth(remap(t, 25.2, 25.8))));
  // inspection panel (real three_view right panel)
  const ik = smooth(remap(t, 11.8, 12.8)) * (1 - smooth(remap(t, 25.0, 25.8)));
  insp.position.copy(ctr).add(V(0.0, 0.62, 0.1)); insp.quaternion.copy(camera.quaternion);
  insp.userData.setMap(await inspSeq.at(t * 0.9));
  insp.userData.mat.uniforms.uOpacity.value = ik;
  const si = toScreen(insp.position.clone().add(V(0, 0.2, 0)), camera);
  inspLab.style.left = (si.x - 220) + 'px'; inspLab.style.top = (si.y - 50) + 'px'; fadeEl(inspLab, ik);
  title.update(t, 0.5, 7.4);
  fadeEl(document.getElementById('eefsrc'), smooth(remap(t, 1, 2)) * (1 - smooth(remap(t, 7, 8))));
  t2.update(t, 9.4, 14.0);
  chapter.update(t, 0.3, 25.6);
  ctx.grade.uFade.value = smooth(remap(t, 0, 0.5)) * (1 - easeInCubic(remap(t, 25.4, 26)));
  ctx.bloomCfg.strength = 0.8;
  ctx.render(scene, camera);
}
