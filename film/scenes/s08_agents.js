// S08 — The agent team at work: a one-take orbit around a live reconstruction of a real EgoDex episode.
import { THREE, el, clamp, lerp, remap, smooth, smoother, easeOutCubic, easeInOutCubic, easeOutExpo, easeInCubic, rng, SeqTexture, loadImage, loadJSON } from '@engine/core.js';
import { makePoints, Ribbon, makeTriad, makeGrid, makePanel, makeHalo, makeHaze, toScreen, arcPoints, circlePoints, spectralColor, COL } from '@engine/fx.js';
import { Title, Chapter, fadeEl } from '@engine/ui.js';
import { RobotArm, robotMaterials } from '@engine/robot.js';
import { loadCloud, makeHandPath, envLights, poseAt, pixelToTable } from './lib/world.js';
import { Orrery, Iris, Lattice, Helix, MiniArm, Bars, Seal } from './lib/emblems.js';
import { StateRail, Budget, counter } from './lib/hud.js';

export const duration = 60;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const deg = (d) => d * Math.PI / 180;
const RX = 2830, RY = 700; // right-hand instrument readout column

const ST = [
  { id: 'coord', name: 'Coordinator', model: 'DeepSeek-V4.1-Flash · deterministic state graph', zh: '总调度', color: '#a98bff', phi: 0, r: 1.25, y: 1.3, E: Orrery,
    en: 'Plans the task graph — but cannot waive a single check.', zhl: '规划任务图，但无权豁免任何一项检查', t: [4.5, 12] },
  { id: 'evid', name: 'Evidence Agent', model: 'Qwen · Visual-Jev', zh: '证据智能体', color: '#74d7ff', phi: -52, r: 1.8, y: 0.62, E: Iris,
    en: 'Reads the original frames. Never invents missing geometry.', zhl: '只读原始帧，绝不补造缺失的几何', t: [12, 20] },
  { id: 'spat', name: 'Spatial Expert', model: 'SenseNova-SI-1.3 · InternVL3-8B', zh: '空间专家', color: '#67e3c9', phi: -104, r: 1.8, y: 0.66, E: Lattice,
    en: 'Answers with provenance, reference frames and uncertainty.', zhl: '空间证据必须注明来源、坐标系与不确定度', t: [20, 28] },
  { id: 'repr', name: 'Repair Agent', model: 'conditional residual diffusion · M5 projector', zh: '修复智能体', color: '#ffb27a', phi: -156, r: 1.8, y: 0.62, E: Helix,
    en: 'Bounded residual edits. Raw and projected versions both kept.', zhl: '有界残差修改，原始与投影版本均保留', t: [28, 37] },
  { id: 'simu', name: 'Simulation Agent', model: 'M6 controlled physics worker · 500 Hz', zh: '仿真智能体', color: '#6cb8ff', phi: 152, r: 1.8, y: 0.62, E: MiniArm,
    en: 'Actual commands, actual contacts. No teleport, no hidden support.', zhl: '真实指令与接触，不允许瞬移或隐藏支撑', t: [37, 46] },
  { id: 'crit', name: 'Critic / Data Agent', model: 'PreCritic · PostCritic · exporter', zh: '评审与数据', color: '#ff7eb6', phi: 100, r: 1.8, y: 0.62, E: Bars,
    en: 'Model confidence cannot override a numeric violation.', zhl: '模型置信度不能推翻数值违规，失败与未知全部保留', t: [46, 52] },
  { id: 'comm', name: 'Committer', model: 'deterministic service · hash read-back · CAS', zh: '确定性提交', color: '#eef3ff', phi: 50, r: 1.8, y: 0.66, E: Seal,
    en: 'Reads back every hash. Publishes atomically — or not at all.', zhl: '逐一读回哈希，原子发布，否则不发布', t: [52, 59] },
];
const stPos = (s) => V(Math.sin(deg(s.phi)) * s.r, s.y, Math.cos(deg(s.phi)) * s.r);

// one-take camera: [t, angleDeg, radius, height, target]
const CAM = [
  [0, 186, 3.9, 2.3, V(0, 0.3, 0.1)],
  [5, 180, 2.75, 1.25, V(0, 0.62, 0.25)],
  [11, 160, 2.6, 1.0, V(0.05, 0.42, 0.1)],
  [16, 128, 2.45, 0.95, V(-0.18, 0.28, -0.05)],
  [24, 76, 2.35, 1.75, V(-0.1, 0.05, -0.08)],
  [32, 24, 2.05, 0.95, V(-0.08, 0.1, -0.12)],
  [41, -28, 2.1, 0.9, V(-0.05, 0.18, -0.12)],
  [49, -82, 2.5, 1.05, V(0.25, 0.2, 0.05)],
  [55.5, -128, 2.6, 1.15, V(0.3, 0.4, 0.15)],
  [60, -176, 4.2, 2.4, V(0, 0.3, 0.05)],
];
function hermite(p0, p1, m0, m1, s) { const s2 = s * s, s3 = s2 * s; return (2 * s3 - 3 * s2 + 1) * p0 + (s3 - 2 * s2 + s) * m0 + (-2 * s3 + 3 * s2) * p1 + (s3 - s2) * m1; }
function camAt(t) {
  const K = CAM; let i = 0; while (i < K.length - 2 && t > K[i + 1][0]) i++;
  const k0 = K[Math.max(i - 1, 0)], k1 = K[i], k2 = K[i + 1], k3 = K[Math.min(i + 2, K.length - 1)];
  const dt = k2[0] - k1[0], s = clamp((t - k1[0]) / dt);
  const f = (j, get) => {
    const p0 = get(k0), p1 = get(k1), p2 = get(k2), p3 = get(k3);
    const m1 = (p2 - p0) / Math.max(k2[0] - k0[0], 1e-3) * dt, m2 = (p3 - p1) / Math.max(k3[0] - k1[0], 1e-3) * dt;
    return hermite(p1, p2, i === 0 ? 0 : m1, i + 2 >= K.length ? 0 : m2, s);
  };
  const ang = f(0, (k) => k[1]), rad = f(0, (k) => k[2]), h = f(0, (k) => k[3]);
  const tx = f(0, (k) => k[4].x), ty = f(0, (k) => k[4].y), tz = f(0, (k) => k[4].z);
  return { pos: V(Math.sin(deg(ang)) * rad, h, Math.cos(deg(ang)) * rad), tgt: V(tx, ty, tz) };
}

let scene, camera, cloud, meta, curve, stations = [], labels = [], captions = [], packets = [], rail, budget, title, chapter;
let footnote, grid, dag, film, spatial, repair, sim, critic, commit, trajRb, triads = [], floorRing;

// ---------------------------------------------------------------- packets (typed artifacts in flight)
class Packet {
  constructor(ui, a, b, t0, dur, label, color, lift = 0.45) {
    this.t0 = t0; this.dur = dur;
    const pts = arcPoints(a, b, lift, 64);
    this.path = new Ribbon(pts, { width: 2, color, intensity: 0.9 });
    this.head = new Ribbon(pts, { width: 7, color, intensity: 5, glow: 0.6 });
    this.curve = new THREE.CatmullRomCurve3(pts);
    scene.add(this.path.mesh, this.head.mesh);
    this.lab = el(ui, 'abs mono', `<span style="display:inline-block;width:14px;height:14px;background:${color};margin-right:14px;box-shadow:0 0 14px ${color}"></span>${label}`,
      { fontSize: '24px', letterSpacing: '0.06em', color: '#eef3ff', whiteSpace: 'nowrap', textTransform: 'none' });
  }
  update(t) {
    const p = (t - this.t0) / this.dur;
    const vis = p > -0.05 && p < 1.6;
    const k = Math.min(smooth(p / 0.1), 1 - smooth((p - 1.1) / 0.4));
    this.path.set({ head: clamp(p * 1.4), opacity: vis ? 0.6 * k : 0 });
    const hp = easeInOutCubic(clamp(p));
    this.head.set({ head: hp, tail: hp - 0.09, opacity: vis && p < 1.02 ? 1 : 0 });
    if (vis && p < 1.0 && p > 0.02) {
      const s = toScreen(this.curve.getPointAt(hp), camera);
      this.lab.style.display = s.behind ? 'none' : '';
      this.lab.style.left = (s.x + 26) + 'px'; this.lab.style.top = (s.y - 44) + 'px';
      this.lab.style.opacity = (Math.min(smooth(p / 0.12), smooth((1 - p) / 0.12))).toFixed(3);
    } else this.lab.style.display = 'none';
  }
}

// ---------------------------------------------------------------- caption block (lower-left)
class Caption {
  constructor(ui, i, s) {
    this.s = s;
    this.root = el(ui, 'abs', '', { left: '150px', top: '1450px', width: '2300px' });
    this.idx = el(this.root, 'mono', `0${i + 1} / 07 &nbsp;&nbsp;<span style="color:${s.color}">●</span>&nbsp; ${s.zh}`, { fontSize: '26px', color: 'rgba(238,243,255,0.6)', marginBottom: '18px' });
    this.name = el(this.root, 'h2', s.name, { fontSize: '92px', fontWeight: 500 });
    this.model = el(this.root, 'mono', s.model, { fontSize: '26px', color: s.color, marginTop: '16px', letterSpacing: '0.1em', textTransform: 'none' });
    this.en = el(this.root, '', s.en, { fontSize: '50px', fontWeight: 300, marginTop: '34px', color: 'rgba(238,243,255,0.92)', letterSpacing: '-0.005em' });
    this.zhl = el(this.root, 'zh-s', s.zhl, { fontSize: '36px', marginTop: '14px' });
  }
  update(t) {
    const [a, b] = this.s.t;
    const k = Math.min(smooth((t - a - 0.3) / 0.7), smooth((b - t - 0.1) / 0.5));
    this.root.style.display = k <= 0.001 ? 'none' : '';
    if (k <= 0.001) return;
    const parts = [this.idx, this.name, this.model, this.en, this.zhl];
    parts.forEach((p, j) => { const kk = Math.min(smooth((t - a - 0.3 - j * 0.12) / 0.6), smooth((b - t - 0.1) / 0.5)); p.style.opacity = kk.toFixed(3); p.style.transform = `translateX(${((1 - kk) * -24).toFixed(1)}px)`; p.style.filter = kk < 0.98 ? `blur(${((1 - kk) * 10).toFixed(1)}px)` : 'none'; });
  }
}

export async function init(ctx) {
  scene = new THREE.Scene();
  scene.add(makeHaze({ top: '#071020', bottom: '#020306', glow: '#13203d', glowK: 0.4 }));
  camera = new THREE.PerspectiveCamera(34, ctx.W / ctx.H, 0.02, 1000);
  envLights(scene, ctx.renderer, { envI: 0.45 });

  cloud = await loadCloud('/assets/scene/ego0', { darken: 0.8, sat: 0.8, size: 0.0046 });
  meta = cloud.userData.meta;
  scene.add(cloud);
  curve = makeHandPath(meta);

  grid = makeGrid({ size: 8, cell: 0.1, major: 5, color: '#6f8cff', opacity: 0.22, fade: 2.6 });
  grid.position.y = -0.002; scene.add(grid);
  floorRing = new Ribbon(circlePoints(1.8, 256, -0.001), { width: 2, color: '#6f8cff', intensity: 0.6 }); scene.add(floorRing.mesh);

  // stations
  for (const s of ST) {
    const e = new s.E(s.color); e.g.position.copy(stPos(s)); scene.add(e.g); e.s = s; stations.push(e);
    const lab = el(ctx.ui, 'abs', `<div class="h3" style="font-size:40px;font-weight:500;white-space:nowrap">${s.name}</div><div class="zh-s" style="font-size:28px;margin-top:6px;letter-spacing:0.2em">${s.zh}</div>`, { textAlign: 'center', width: '700px' });
    labels.push(lab);
    // tether from station to the table centre
    e.tether = new Ribbon(arcPoints(stPos(s), V(0, 0.06, 0), 0.25, 48), { width: 2, color: s.color, intensity: 0.8 });
    scene.add(e.tether.mesh);
  }
  ST.forEach((s, i) => captions.push(new Caption(ctx.ui, i, s)));

  // trajectory (EEF) + triads
  const tp = curve.getSpacedPoints(240);
  trajRb = new Ribbon(tp, { width: 5, color: '#ffffff', intensity: 1.6, glow: 0.3 });
  scene.add(trajRb.mesh);
  for (let i = 0; i <= 24; i++) { const tr = makeTriad(0.035, 3, 2.0); const { p, q } = poseAt(curve, i / 24); tr.position.copy(p); tr.quaternion.copy(q); tr.u = i / 24; triads.push(tr); scene.add(tr); }

  buildDAG(ctx); await buildFilm(ctx); await buildSpatial(ctx); buildRepair(ctx); buildSim(ctx); buildCritic(ctx); buildCommit(ctx);

  // packets: [from, to, t0, dur, label, color]
  const P = (a, b, t0, d, lab, col, lift) => packets.push(new Packet(ctx.ui, a, b, t0, d, lab, col, lift));
  const S = (id) => stPos(ST.find((s) => s.id === id));
  P(S('coord'), S('evid'), 9.2, 1.8, 'TaskDAG → evidence batch', '#a98bff', 0.3);
  P(S('evid'), S('coord'), 15.6, 1.4, 'InteractionSketch · evidence gap', '#ffb547', 0.3);
  P(S('coord'), S('evid'), 17.2, 1.2, 'REQUEST_EVIDENCE', '#ffb547', 0.25);
  P(S('coord'), S('spat'), 19.4, 1.6, 'spatial question · frames 0–301', '#a98bff', 0.35);
  P(S('spat'), S('coord'), 25.4, 1.6, 'SpatialEvidenceReport', '#67e3c9', 0.35);
  P(S('coord'), S('repr'), 27.6, 1.8, 'RepairIntent (bounded)', '#a98bff', 0.4);
  P(S('repr'), S('simu'), 35.6, 1.6, 'candidates · raw + projected', '#ffb27a', 0.3);
  P(S('simu'), S('crit'), 44.6, 1.5, 'ExecutionRecord × 6', '#6cb8ff', 0.3);
  P(S('crit'), S('comm'), 50.8, 1.4, 'DatasetVersion draft', '#ff7eb6', 0.3);

  rail = new StateRail(ctx.ui);
  budget = new Budget(ctx.ui);
  title = new Title(ctx.ui, { en: 'Seven roles. Separated powers.', zh: '七个角色 · 权责分离', y: 1000, size: 150 });
  chapter = new Chapter(ctx.ui, '02', 'THE SYSTEM', '系统');
  footnote = el(ctx.ui, 'abs mono', 'Visualization of the V5 agent protocol on a real EgoDex episode · caps per spec M8.2 · reconstruction approximate', { right: '150px', top: '2090px', fontSize: '19px', color: 'rgba(238,243,255,0.32)', letterSpacing: '0.08em', textTransform: 'none' });
}

// ---------------------------------------------------------------- coordinator DAG
function buildDAG(ctx) {
  const N = [
    ['EPISODE', V(0, 1.18, 0.62)],
    ['AUDIT', V(-0.42, 1.0, 0.62)], ['EVIDENCE', V(0, 1.0, 0.62)], ['SPATIAL', V(0.42, 1.0, 0.62)],
    ['REPAIR_INTENT', V(0, 0.84, 0.62)],
    ['GENERATE', V(-0.3, 0.7, 0.62)], ['PROJECT', V(0.3, 0.7, 0.62)],
    ['SIMULATE', V(0, 0.58, 0.62)], ['COMPARE', V(-0.25, 0.46, 0.62)], ['COMMIT', V(0.25, 0.46, 0.62)],
  ];
  const E = [[0, 1], [0, 2], [0, 3], [1, 4], [2, 4], [3, 4], [4, 5], [4, 6], [5, 7], [6, 7], [7, 8], [8, 9], [5, 6]];
  dag = { nodes: [], edges: [] };
  N.forEach(([name, p], i) => {
    const hex = []; for (let j = 0; j <= 6; j++) { const a = j / 6 * Math.PI * 2 + Math.PI / 6; hex.push(V(p.x + Math.cos(a) * 0.026, p.y + Math.sin(a) * 0.026, p.z)); }
    const rb = new Ribbon(hex, { width: 3, color: '#a98bff', intensity: 2.2 });
    const dot = makeHalo({ size: 0.09, color: '#c9bcff', intensity: 0.0 }); dot.position.copy(p);
    scene.add(rb.mesh, dot);
    const lab = el(ctx.ui, 'abs mono', name, { fontSize: '21px', color: 'rgba(225,215,255,0.9)', whiteSpace: 'nowrap', letterSpacing: '0.08em' });
    dag.nodes.push({ name, p, rb, dot, lab, t: 5.2 + i * 0.22 });
  });
  E.forEach(([a, b], i) => {
    const pa = N[a][1], pb = N[b][1];
    const rb = new Ribbon([pa, pa.clone().lerp(pb, 0.5).add(V(0, 0, -0.02)), pb], { width: 2, color: '#a98bff', intensity: 1.2 });
    rb.mat.uniforms.uPulseK.value = 3;
    scene.add(rb.mesh);
    dag.edges.push({ rb, t: 5.6 + i * 0.18 });
  });
}
function updateDAG(t, activeName) {
  const vis = (1 - 0.8 * smooth(remap(t, 12.5, 14))) * (1 - smooth(remap(t, 58.5, 59.5)));
  dag.nodes.forEach((n) => {
    const k = smooth(remap(t, n.t, n.t + 0.6)) * vis;
    const act = n.name === activeName ? 1 : 0;
    n.rb.set({ opacity: k * (0.7 + 0.3 * act), color: act ? '#ffffff' : '#a98bff', intensity: act ? 3.5 : 2.2 });
    n.dot.userData.mat.uniforms.uI.value = act ? 0.9 * (0.7 + 0.3 * Math.sin(t * 6)) * smooth(remap(t, n.t, n.t + 0.6)) : 0.15 * k;
    n.dot.quaternion.copy(camera.quaternion);
    const s = toScreen(n.p, camera);
    const lk = k * (t < 13 ? 1 : act ? 1 : 0);
    n.lab.style.display = lk > 0.01 && !s.behind ? '' : 'none';
    n.lab.style.left = (s.x + 30) + 'px'; n.lab.style.top = (s.y - 14) + 'px'; n.lab.style.opacity = lk.toFixed(3);
    n.lab.style.color = act ? '#ffffff' : 'rgba(225,215,255,0.9)';
  });
  dag.edges.forEach((e) => { const k = smooth(remap(t, e.t, e.t + 0.5)); e.rb.set({ head: k, opacity: 0.8 * vis, time: t, pulse: 0.8 }); });
}

// ---------------------------------------------------------------- evidence filmstrip (real frames)
async function buildFilm(ctx) {
  const idx = [0, 34, 68, 100, 132, 164, 200, 240, 286];
  const s = ST[1]; const c = deg(s.phi);
  film = { panels: [], tags: [] };
  for (let i = 0; i < idx.length; i++) {
    const a = c + deg((i - (idx.length - 1) / 2) * 13.5);
    const p = V(Math.sin(a) * 0.98, 0.36, Math.cos(a) * 0.98);
    const m = makePanel(0.2, 0.1125, { radius: 0.008, border: 0.0025, borderColor: '#74d7ff', borderI: 0.6 });
    m.position.copy(p); m.lookAt(V(0, 0.36, 0)); m.rotateY(Math.PI);
    const tex = new THREE.Texture(await loadImage(`/assets/footage/ego_raw/${String(idx[i]).padStart(4, '0')}.jpg`));
    tex.colorSpace = THREE.SRGBColorSpace; tex.needsUpdate = true;
    m.userData.setMap(tex);
    scene.add(m); film.panels.push({ m, p, frame: idx[i] });
  }
  film.scan = new Ribbon([V(0, 0, 0), V(0, 0.16, 0)], { width: 6, color: '#bfeaff', intensity: 4, glow: 0.5 });
  scene.add(film.scan.mesh);
  const TAGS = [[1, 'REACH', '#74d7ff'], [3, 'GRASP', '#74d7ff'], [5, 'EVIDENCE GAP · OCCLUDED', '#ffb547'], [6, 'LIFT', '#74d7ff'], [8, 'PLACE', '#74d7ff']];
  for (const [i, name, col] of TAGS) {
    const lab = el(ctx.ui, 'abs mono', `<span style="color:${col}">▲</span> ${name}<br><span style="color:rgba(238,243,255,0.5);font-size:20px">frame ${idx[i]} · ${(idx[i] / 30).toFixed(2)} s</span>`, { fontSize: '22px', color: '#eef3ff', whiteSpace: 'nowrap', letterSpacing: '0.06em', textTransform: 'none' });
    film.tags.push({ i, name, col, lab });
  }
  // extra frames requested to close the gap
  film.extra = [];
  for (let j = 0; j < 3; j++) {
    const m = makePanel(0.09, 0.0506, { radius: 0.004, border: 0.0018, borderColor: '#ffb547', borderI: 0.9 });
    const tex = new THREE.Texture(await loadImage(`/assets/footage/ego_raw/${String(170 + j * 8).padStart(4, '0')}.jpg`)); tex.colorSpace = THREE.SRGBColorSpace; tex.needsUpdate = true;
    m.userData.setMap(tex); scene.add(m); film.extra.push(m);
  }
}
function updateFilm(t) {
  const k = smooth(remap(t, 11.0, 12.4)) * (1 - smooth(remap(t, 20.5, 22.5)));
  const scanP = remap(t, 12.6, 16.2);
  const n = film.panels.length;
  film.panels.forEach((P, i) => {
    const u = P.m.userData.mat.uniforms;
    const hit = Math.exp(-Math.pow((scanP * (n - 1) - i) * 1.4, 2));
    u.uOpacity.value = k * smooth(remap(t, 11.0 + i * 0.12, 11.6 + i * 0.12));
    u.uBright.value = 0.7 + 0.6 * hit; u.uBorderI.value = 0.35 + 1.6 * hit;
    const gap = i === 5 ? smooth(remap(t, 15.0, 15.4)) * (1 - smooth(remap(t, 19.0, 19.6))) : 0;
    u.uBorderColor.value.set(gap > 0.5 ? '#ffb547' : '#74d7ff');
    u.uSat.value = 1 - 0.5 * gap;
  });
  // scanner bar travels along the arc
  const s = ST[1]; const c = deg(s.phi);
  const a = c + deg((scanP * (n - 1) - (n - 1) / 2) * 13.5);
  const p = V(Math.sin(a) * 0.985, 0.28, Math.cos(a) * 0.985);
  film.scan.setPoints([p, p.clone().add(V(0, 0.16, 0))]);
  film.scan.set({ opacity: k * (scanP > 0 && scanP < 1 ? 1 : 0) });
  film.tags.forEach((g) => {
    const P = film.panels[g.i];
    const tt = 12.6 + (g.i / (n - 1)) * 3.6;
    const kk = smooth(remap(t, tt, tt + 0.4)) * (1 - smooth(remap(t, 19.8, 20.6)));
    const s2 = toScreen(P.p.clone().add(V(0, 0.09, 0)), camera);
    g.lab.style.display = kk > 0.01 && !s2.behind ? '' : 'none';
    g.lab.style.left = (s2.x - 60) + 'px'; g.lab.style.top = (s2.y - 70) + 'px'; g.lab.style.opacity = kk.toFixed(3);
    if (g.i === 5) { const res = smooth(remap(t, 18.6, 19.2)); g.lab.innerHTML = res > 0.5 ? `<span style="color:#5ef2a8">▲</span> GAP CLOSED · +3 FRAMES<br><span style="color:rgba(238,243,255,0.5);font-size:20px">batch 2 / 2</span>` : `<span style="color:#ffb547">▲</span> EVIDENCE GAP · OCCLUDED<br><span style="color:rgba(238,243,255,0.5);font-size:20px">frame 164 · 5.47 s</span>`; }
  });
  const P5 = film.panels[5];
  film.extra.forEach((m, j) => {
    const kk = smooth(remap(t, 17.9 + j * 0.15, 18.4 + j * 0.15)) * (1 - smooth(remap(t, 20.5, 22)));
    m.position.copy(P5.p).add(V(0, -0.1 - 0.0, 0)); m.quaternion.copy(P5.m.quaternion); m.translateX((j - 1) * 0.1);
    m.userData.mat.uniforms.uOpacity.value = kk;
  });
}

// ---------------------------------------------------------------- spatial: support polygon + fixed-base search
async function buildSpatial(ctx) {
  const sup = await loadJSON('/assets/data/support.json');
  const map = (nx, nz) => V(lerp(-0.56, 0.46, nx), 0.005, lerp(-0.4, 0.3, nz));
  spatial = { polys: [], cands: [], beam: null };
  for (const poly of sup.polys) {
    const pts = poly.map(([x, z]) => map(x, z)); pts.push(pts[0].clone());
    const rb = new Ribbon(pts, { width: 4, color: '#5ef2a8', intensity: 1.8 }); scene.add(rb.mesh); spatial.polys.push(rb);
  }
  // candidates spread over the near half of the support (robot must mount on the table)
  const r = rng(21); const N = 150;
  spatial.pts = makePoints(N, { soft: 0.2 }); scene.add(spatial.pts);
  const reach = 0.78;
  const samples = curve.getSpacedPoints(60);
  const chosen = map(sup.bases[0][0], sup.bases[0][1]);
  spatial.chosen = chosen;
  for (let i = 0; i < N; i++) {
    const p = V(lerp(-0.58, 0.58, r()), 0.006, lerp(-0.44, 0.0, r()));
    let ok = 0; for (const s of samples) if (s.distanceTo(p) < reach && s.distanceTo(p) > 0.16) ok++;
    const cov = ok / samples.length;
    spatial.cands.push({ p, cov, t: 21.2 + r() * 2.6 });
  }
  spatial.cands.push({ p: chosen, cov: 1, t: 23.6, best: true });
  spatial.pts.geometry.setDrawRange(0, spatial.cands.length);
  spatial.beam = new Ribbon([chosen.clone(), chosen.clone().add(V(0, 0.9, 0))], { width: 10, color: '#67e3c9', intensity: 3, glow: 0.8 });
  spatial.ring = new Ribbon(circlePoints(0.06, 64, 0).map((v) => v.add(chosen)), { width: 4, color: '#67e3c9', intensity: 3 });
  scene.add(spatial.beam.mesh, spatial.ring.mesh);
  spatial.label = el(ctx.ui, 'abs mono', 'FIXED BASE · SELECTED<br><span style="color:rgba(238,243,255,0.55);font-size:20px">full-footprint support ✓ · reach coverage rank 1</span>', { fontSize: '24px', color: '#67e3c9', whiteSpace: 'nowrap', letterSpacing: '0.06em', textTransform: 'none' });
  spatial.cov = el(ctx.ui, 'abs mono', '', { fontSize: '24px', color: '#eef3ff', whiteSpace: 'nowrap', textTransform: 'none' });
}
function updateSpatial(t) {
  const k = smooth(remap(t, 19.8, 21.0)) * (1 - smooth(remap(t, 28.5, 30)));
  spatial.polys.forEach((rb, i) => rb.set({ head: smooth(remap(t, 20.0 + i * 0.3, 21.4 + i * 0.3)), opacity: k }));
  grid.userData.mat.uniforms.uOpacity.value = 0.22 + 0.5 * k * (1 - smooth(remap(t, 27, 29)));
  const g = spatial.pts.geometry; let tested = 0, passed = 0;
  spatial.cands.forEach((c, i) => {
    const ap = smooth(remap(t, 20.6 + (i % 30) * 0.02, 21.0 + (i % 30) * 0.02));
    const tested_ = t > c.t;
    const pass = c.cov > 0.999;
    let col = [0.6, 0.7, 0.9];
    if (tested_) { tested++; if (pass) { passed++; col = [0.3, 2.2, 1.2]; } else col = [2.2, 0.35, 0.45]; }
    if (c.best && t > c.t) col = [0.8, 3.5, 3.0];
    g.attributes.position.setXYZ(i, c.p.x, c.p.y, c.p.z);
    g.attributes.color.setXYZ(i, ...col);
    const flash = tested_ ? Math.exp(-Math.pow((t - c.t) * 4, 2)) : 0;
    g.attributes.size.setX(i, (c.best ? 0.03 : 0.014) * (1 + flash));
    g.attributes.alpha.setX(i, ap * k * (tested_ && !pass ? 0.55 : 1));
  });
  for (const a of ['position', 'color', 'size', 'alpha']) g.attributes[a].needsUpdate = true;
  const bk = smooth(remap(t, 23.6, 24.4)) * (1 - smooth(remap(t, 36, 37.5)));
  spatial.beam.set({ head: easeOutCubic(remap(t, 23.6, 24.4)), opacity: bk * (0.8 + 0.2 * Math.sin(t * 5)) });
  spatial.ring.set({ opacity: bk });
  const s = toScreen(spatial.chosen.clone().add(V(0, 0.32, 0)), camera);
  const lk = smooth(remap(t, 24.0, 24.6)) * (1 - smooth(remap(t, 27.8, 28.6)));
  spatial.label.style.display = lk > 0.01 && !s.behind ? '' : 'none';
  spatial.label.style.left = (s.x - 760) + 'px'; spatial.label.style.textAlign = 'right'; spatial.label.style.width = '720px'; spatial.label.style.top = (s.y - 30) + 'px'; spatial.label.style.opacity = lk.toFixed(3);
  const ck = smooth(remap(t, 21.0, 21.5)) * (1 - smooth(remap(t, 27.8, 28.6)));
  spatial.cov.style.display = ck > 0.01 ? '' : 'none';
  spatial.cov.style.left = RX + 'px'; spatial.cov.style.top = RY + 'px'; spatial.cov.style.opacity = ck.toFixed(3);
  spatial.cov.innerHTML = `FIXED-BASE SEARCH · FULL FOOTPRINT ⊂ SUPPORT<br><br>CANDIDATES TESTED &nbsp;<span style="color:#fff">${tested}</span> / ${spatial.cands.length}<br><span style="color:#5ef2a8">FULL COVERAGE ${passed}</span>&nbsp;&nbsp;<span style="color:#ff4d5e">REJECTED ${tested - passed}</span>`;
}

// ---------------------------------------------------------------- repair: defects, diffusion candidates, projection
const CANDS = [
  { name: 'A', col: '#67e3c9', amp: 0.012, ph: 0.3 },
  { name: 'B', col: '#ffb27a', amp: 0.03, ph: 1.7, dip: true },
  { name: 'C', col: '#a98bff', amp: 0.022, ph: 3.1 },
  { name: 'D', col: '#6cb8ff', amp: 0.016, ph: 4.4 },
];
function candPoint(c, u, raw = true) {
  const p = curve.getPointAt(u).clone();
  const w = Math.sin(u * Math.PI);
  p.x += Math.sin(u * 9 + c.ph) * c.amp * w; p.z += Math.cos(u * 7 + c.ph) * c.amp * w; p.y += Math.sin(u * 5 + c.ph * 2) * c.amp * 0.5 * w;
  if (c.dip && raw) p.y -= 0.05 * Math.exp(-Math.pow((u - 0.31) / 0.035, 2)); // raw candidate dips through the table
  const gu = Math.exp(-Math.pow((u - 0.31) / 0.05, 2));
  if (!raw) p.y = Math.max(p.y, 0.022 * gu + 0.004);
  return p;
}
function buildRepair(ctx) {
  repair = { cands: [], defects: [] };
  // defective original: penetration at grasp + tracking jitter during transport
  const n = 240, pts = [];
  for (let i = 0; i <= n; i++) {
    const u = i / n; const p = curve.getPointAt(u).clone();
    p.y -= 0.035 * Math.exp(-Math.pow((u - 0.31) / 0.03, 2));
    const j = smooth(remap(u, 0.52, 0.56)) * (1 - smooth(remap(u, 0.68, 0.72)));
    p.x += Math.sin(i * 2.7) * 0.012 * j; p.y += Math.cos(i * 3.9) * 0.01 * j; p.z += Math.sin(i * 1.9 + 1) * 0.01 * j;
    pts.push(p);
  }
  repair.orig = new Ribbon(pts, { width: 5, intensity: 1.6, colors: (i, u) => {
    const bad = Math.max(Math.exp(-Math.pow((u - 0.31) / 0.035, 2)), smooth(remap(u, 0.5, 0.55)) * (1 - smooth(remap(u, 0.7, 0.74))));
    return [lerp(1, 1.0, bad), lerp(1, 0.27, bad), lerp(1, 0.33, bad), 1]; } });
  scene.add(repair.orig.mesh);
  repair.labels = [
    [0.31, 'TABLE PENETRATION', -0.04], [0.62, 'TRACKING JITTER', 0.05], [0.78, 'ORIENTATION MISSING', 0.05],
  ].map(([u, txt, dy]) => ({ u, dy, e: el(ctx.ui, 'abs mono', '✕ ' + txt, { fontSize: '27px', color: '#ff4d5e', whiteSpace: 'nowrap', letterSpacing: '0.08em' }) }));
  const r = rng(77);
  CANDS.forEach((c, ci) => {
    const N = 180; const pts = makePoints(N, { soft: 0.3 }); const seeds = [];
    for (let i = 0; i < N; i++) seeds.push([i / (N - 1), (r() - 0.5) * 2, (r() - 0.5) * 2, (r() - 0.5) * 2]);
    const col = new THREE.Color(c.col);
    for (let i = 0; i < N; i++) { pts.geometry.attributes.color.setXYZ(i, col.r * 2.5, col.g * 2.5, col.b * 2.5); pts.geometry.attributes.size.setX(i, 0.009); }
    pts.geometry.attributes.color.needsUpdate = true;
    scene.add(pts);
    const raw = [], prj = [];
    for (let i = 0; i <= 160; i++) { raw.push(candPoint(c, i / 160, true)); prj.push(candPoint(c, i / 160, false)); }
    const rawRb = new Ribbon(raw, { width: 3, color: c.col, intensity: 1.0 });
    const prjRb = new Ribbon(prj, { width: 5, color: c.col, intensity: 2.2, glow: 0.3 });
    rawRb.mat.uniforms.uPulseK.value = 60;
    scene.add(rawRb.mesh, prjRb.mesh);
    const lab = el(ctx.ui, 'abs mono', `CANDIDATE ${c.name}`, { fontSize: '22px', color: c.col, whiteSpace: 'nowrap', letterSpacing: '0.08em' });
    repair.cands.push({ c, pts, seeds, rawRb, prjRb, lab, t0: 29.0 + ci * 0.45 });
  });
  // projection constraint plane glow (table surface)
  repair.plane = makePanel(1.4, 0.9, { radius: 0.02, border: 0.003, borderColor: '#ffb27a', borderI: 1 });
  repair.plane.rotation.x = -Math.PI / 2; repair.plane.position.y = 0.003;
  repair.plane.userData.mat.uniforms.uBright.value = 0; scene.add(repair.plane);
  repair.tag = el(ctx.ui, 'abs mono', '', { fontSize: '24px', color: '#eef3ff', whiteSpace: 'nowrap', textTransform: 'none' });
}
function updateRepair(t) {
  const showOrig = smooth(remap(t, 27.6, 28.6)) * (1 - smooth(remap(t, 36.5, 38)));
  repair.orig.set({ opacity: showOrig * (1 - 0.6 * smooth(remap(t, 31.5, 33))) });
  trajRb.set({ opacity: (smooth(remap(t, 19.5, 21)) * (1 - smooth(remap(t, 27.4, 28.2)))) * 0.9 });
  triads.forEach((tr) => { const miss = tr.u > 0.74 && tr.u < 0.83; const k = smooth(remap(t, 20, 21.5)) * (1 - smooth(remap(t, 36.5, 38))) * (miss && t > 27.6 ? 0.0 : 1); tr.userData.ribbons.forEach((r) => r.set({ opacity: k * 0.85 })); tr.visible = k > 0.01; });
  repair.labels.forEach((L, i) => {
    const k = smooth(remap(t, 28.2 + i * 0.3, 28.7 + i * 0.3)) * (1 - smooth(remap(t, 31.5, 32.3)));
    const s = toScreen(curve.getPointAt(L.u).clone().add(V(0, L.dy + 0.04, 0)), camera);
    L.e.style.display = k > 0.01 && !s.behind ? '' : 'none'; L.e.style.left = (s.x + 20) + 'px'; L.e.style.top = (s.y - 20) + 'px'; L.e.style.opacity = k.toFixed(3);
  });
  const end = 1 - smooth(remap(t, 46.5, 48.5));
  repair.cands.forEach((R, ci) => {
    const g = R.pts.geometry;
    const sig = 0.22 * Math.pow(1 - easeOutCubic(remap(t, R.t0, R.t0 + 2.6)), 1.4);
    const vis = smooth(remap(t, R.t0 - 0.2, R.t0 + 0.3)) * (1 - smooth(remap(t, R.t0 + 2.6, R.t0 + 3.4)));
    R.seeds.forEach(([u, a, b, c], i) => {
      const p = candPoint(R.c, u, true);
      g.attributes.position.setXYZ(i, p.x + a * sig, p.y + Math.abs(b) * sig * 0.6, p.z + c * sig);
      g.attributes.alpha.setX(i, vis);
    });
    g.attributes.position.needsUpdate = true; g.attributes.alpha.needsUpdate = true;
    const drawn = smooth(remap(t, R.t0 + 2.0, R.t0 + 3.0));
    const proj = smooth(remap(t, 33.0 + ci * 0.2, 34.0 + ci * 0.2));
    R.rawRb.set({ head: drawn, opacity: drawn * (proj > 0 ? 0.45 : 1) * end, pulse: proj > 0 ? 0.0 : 0, time: t });
    R.prjRb.set({ head: proj, opacity: proj * end * (t > 37 ? 0.5 : 1) });
    const s = toScreen(candPoint(R.c, 0.5 + ci * 0.05, false).add(V(0, 0.03, 0)), camera);
    const lk = smooth(remap(t, R.t0 + 2.2, R.t0 + 2.8)) * (1 - smooth(remap(t, 36.4, 37.2)));
    R.lab.style.display = lk > 0.01 && !s.behind ? '' : 'none'; R.lab.style.left = (s.x + 16) + 'px'; R.lab.style.top = (s.y - 40) + 'px'; R.lab.style.opacity = lk.toFixed(3);
  });
  const pk = smooth(remap(t, 32.6, 33.2)) * (1 - smooth(remap(t, 35.4, 36.4)));
  repair.plane.userData.mat.uniforms.uOpacity.value = pk * 0.9;
  repair.plane.userData.mat.uniforms.uBorderI.value = 1.5 * pk;
  const tk = smooth(remap(t, 29.2, 29.8)) * (1 - smooth(remap(t, 36.4, 37.2)));
  repair.tag.style.display = tk > 0.01 ? '' : 'none'; repair.tag.style.left = RX + 'px'; repair.tag.style.top = RY + 'px'; repair.tag.style.opacity = tk.toFixed(3);
  const nC = Math.min(4, Math.floor(counter(t, [31.4, 31.85, 32.3, 32.75])));
  repair.tag.innerHTML = `REPAIR ROUND 1 / 3<br><span style="color:rgba(238,243,255,0.6)">diffusion candidates this round</span> <span style="color:#ffb27a">${nC} / 4</span>` +
    (t > 33 ? `<br><br>M5 FEASIBILITY PROJECTION<br><span style="color:#ffb27a">raw</span> + <span style="color:#fff">projected</span> versions retained<br><span style="color:rgba(238,243,255,0.6)">original reference never moved</span>` : '');
}

// ---------------------------------------------------------------- simulation: replays at the chosen base
function buildSim(ctx) {
  sim = {};
  sim.arm = new RobotArm({ scale: 1.0, mats: robotMaterials({ accent: '#6cb8ff', accentI: 3 }) });
  scene.add(sim.arm.root);
  sim.ghosts = [0, 1].map(() => { const a = new RobotArm({ scale: 1.0, mats: robotMaterials({ body: '#9fc4ff', joint: '#334466', accent: '#6cb8ff', accentI: 1.5 }) });
    a.root.traverse((o) => { if (o.material) { o.material = o.material.clone(); o.material.transparent = true; o.material.opacity = 0.18; o.material.depthWrite = false; } }); scene.add(a.root); return a; });
  sim.obj = new THREE.Mesh(new THREE.BoxGeometry(0.035, 0.035, 0.035), new THREE.MeshPhysicalMaterial({ color: '#ff9a4d', roughness: 0.3, emissive: '#ff6a1a', emissiveIntensity: 0.4 }));
  scene.add(sim.obj);
  sim.flash = makeHalo({ size: 0.32, color: '#ff4d5e', intensity: 0 }); scene.add(sim.flash);
  sim.runs = [
    { c: 1, t0: 37.6, dur: 2.4, res: 'FAIL', why: 'TABLE CONTACT · STOP', col: '#ff4d5e' },
    { c: 2, t0: 40.2, dur: 2.4, res: 'FAIL', why: 'OBJECT SLIPPED', col: '#ff4d5e' },
    { c: 0, t0: 42.8, dur: 3.0, res: 'PASS', why: 'TASK COMPLETE · UNASSISTED', col: '#5ef2a8' },
  ];
  sim.lab = el(ctx.ui, 'abs mono', '', { fontSize: '26px', color: '#eef3ff', whiteSpace: 'nowrap', textTransform: 'none' });
  sim.res = el(ctx.ui, 'abs', '', { fontSize: '64px', fontWeight: 600, letterSpacing: '0.02em', whiteSpace: 'nowrap' });
}
function armTo(arm, base, p, open) {
  arm.root.position.copy(base);
  const local = p.clone().sub(base);
  const tilt = V(local.x, 0, local.z).normalize().multiplyScalar(0.35);
  arm.solve(local, V(tilt.x, -1, tilt.z).normalize(), 0);
  arm.setGripper(open);
}
function updateSim(t) {
  const base = spatial.chosen.clone().setY(0);
  const vis = smooth(remap(t, 36.6, 37.6)) * (1 - smooth(remap(t, 47, 48.5)));
  const show = vis > 0.01;
  sim.arm.root.visible = show; sim.ghosts.forEach((g) => (g.root.visible = show && t < 46));
  sim.obj.visible = show;
  const grasp = curve.getPointAt(0.31).clone().setY(0.018);
  let run = sim.runs[0]; for (const r of sim.runs) if (t >= r.t0) run = r;
  const p = clamp((t - run.t0) / run.dur);
  const R = repair.cands[run.c];
  const u = lerp(0.18, 0.92, easeInOutCubic(p));
  let target = candPoint(R.c, u, run.c === 1);
  let open = u < 0.3 ? 1 : 0.15;
  let objPos = grasp.clone();
  if (run.c === 1) { if (u > 0.29) { target = candPoint(R.c, 0.305, true); open = 0.6; } }
  if (run.c === 2) { if (u > 0.31 && u < 0.55) objPos = target.clone().add(V(0, -0.03, 0)); if (u >= 0.55) { const f = remap(u, 0.55, 0.62); objPos = candPoint(R.c, 0.55, false).add(V(0, -0.03, 0)).lerp(V(target.x, 0.018, target.z), easeInCubic(f)); } }
  if (run.c === 0) { if (u > 0.31) objPos = target.clone().add(V(0, -0.03, 0)); if (u > 0.9) open = 1; }
  if (!(t >= sim.runs[0].t0)) { target = curve.getPointAt(0.18); }
  armTo(sim.arm, base, target, open);
  sim.obj.position.copy(objPos); sim.obj.position.y = Math.max(sim.obj.position.y, 0.018);
  // onion-skin ghosts trailing behind
  sim.ghosts.forEach((g, i) => { const uu = lerp(0.18, 0.92, easeInOutCubic(clamp(p - 0.08 * (i + 1)))); armTo(g, base, candPoint(R.c, uu, run.c === 1), 0.5); });
  const fail = run.res === 'FAIL';
  const ft = run.t0 + run.dur * (run.c === 1 ? 0.42 : 0.6);
  sim.flash.position.copy(run.c === 1 ? candPoint(R.c, 0.31, true) : objPos);
  sim.flash.quaternion.copy(camera.quaternion);
  sim.flash.userData.mat.uniforms.uI.value = fail ? 0.8 * Math.exp(-Math.pow((t - ft) * 4, 2)) : 0;
  const s = toScreen(base.clone().add(V(0, 0.95, 0)), camera);
  sim.lab.style.display = show ? '' : 'none';
  sim.lab.style.left = RX + 'px'; sim.lab.style.top = RY + 'px'; sim.lab.style.opacity = vis.toFixed(3);
  sim.lab.innerHTML = `REPLAY · CANDIDATE <span style="color:${R.c.col}">${R.c.name}</span> · seed ${sim.runs.indexOf(run)} · 500 Hz`;
  const rk = t > ft ? smooth(remap(t, ft, ft + 0.25)) * (1 - smooth(remap(t, run.t0 + run.dur + 0.1, run.t0 + run.dur + 0.4))) * vis : 0;
  sim.res.style.display = rk > 0.01 ? '' : 'none';
  sim.res.style.left = RX + 'px'; sim.res.style.top = (RY + 60) + 'px'; sim.res.style.opacity = rk.toFixed(3);
  sim.res.innerHTML = `<span style="color:${run.col};text-shadow:0 0 30px ${run.col}">${run.res}</span><br><span class="mono" style="font-size:24px;color:rgba(238,243,255,0.8)">${run.why}</span>`;
}

// ---------------------------------------------------------------- critic: help / neutral / harm / unknown
function buildCritic(ctx) {
  critic = { bins: [], tokens: [] };
  const s = stPos(ST[5]);
  const names = [['HELP', '#5ef2a8'], ['NEUTRAL', '#9aa6bd'], ['HARM', '#ff4d5e'], ['UNKNOWN', '#ffb547']];
  const dir = V(-s.x, 0, -s.z).normalize(); const side = V(-dir.z, 0, dir.x);
  names.forEach(([n, c], i) => {
    const center = s.clone().multiplyScalar(0.7).setY(0.2).addScaledVector(side, (i - 1.5) * 0.26);
    const w = 0.1, h = 0.15;
    const corners = [V(-w, -h, 0), V(w, -h, 0), V(w, h, 0), V(-w, h, 0), V(-w, -h, 0)].map((v) => v.applyAxisAngle(V(0, 1, 0), Math.atan2(side.x, side.z)).add(center));
    const rb = new Ribbon(corners, { width: 4, color: c, intensity: 2 }); scene.add(rb.mesh);
    const pane = makePanel(0.2, 0.3, { radius: 0.01, border: 0.0, borderI: 0 }); pane.position.copy(center); pane.rotation.y = Math.atan2(side.x, side.z);
    pane.userData.mat.uniforms.uBright.value = 0; pane.userData.mat.uniforms.uTint.value.set(1, 1, 1); scene.add(pane);
    const lab = el(ctx.ui, 'abs mono', n, { fontSize: '28px', color: c, whiteSpace: 'nowrap', letterSpacing: '0.12em' });
    const cnt = el(ctx.ui, 'abs mono-n', '0', { fontSize: '56px', color: '#eef3ff' });
    critic.bins.push({ n, c, center, rb, lab, cnt, count: 0, pane });
  });
  // tokens: candidates A..D + the original (noop) which is always in the pool
  const T = [['A', 0, '#67e3c9', 46.4], ['NOOP', 1, '#eef3ff', 46.8], ['D', 1, '#6cb8ff', 47.2], ['B', 2, '#ffb27a', 47.6], ['C', 2, '#a98bff', 48.0], ['C·seed2', 3, '#a98bff', 48.4]];
  for (const [n, b, c, t0] of T) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.018, 24, 12), new THREE.MeshBasicMaterial({ color: new THREE.Color(c).multiplyScalar(3) }));
    scene.add(m); critic.tokens.push({ n, b, m, t0, i: critic.tokens.filter((x) => x.b === b).length });
  }
  critic.note = el(ctx.ui, 'abs mono', 'POOL = 4 CANDIDATES + ORIGINAL (NOOP)<br><br><span style="color:#ff7eb6">FAILURES AND UNKNOWNS ARE KEPT</span><br><span style="color:rgba(238,243,255,0.6)">never deleted · never relabelled</span>', { fontSize: '24px', color: 'rgba(238,243,255,0.85)', whiteSpace: 'nowrap' });
}
function updateCritic(t) {
  const k = smooth(remap(t, 45.6, 46.4)) * (1 - smooth(remap(t, 52.4, 53.6)));
  const from = spatial.chosen.clone().setY(0.4);
  const counts = [0, 0, 0, 0];
  critic.tokens.forEach((T) => {
    const p = easeInOutCubic(remap(t, T.t0, T.t0 + 0.9));
    const bin = critic.bins[T.b];
    const dst = bin.center.clone().add(V(0, -0.1 + T.i * 0.05, 0));
    const pos = from.clone().lerp(dst, p); pos.y += Math.sin(p * Math.PI) * 0.35;
    T.m.position.copy(pos); T.m.visible = t > T.t0 - 0.1 && k > 0.02;
    if (p >= 1) counts[T.b]++;
  });
  critic.bins.forEach((B, i) => {
    B.rb.set({ opacity: k });
    B.pane.userData.mat.uniforms.uOpacity.value = 0.35 * k;
    const s = toScreen(B.center.clone().add(V(0, -0.17, 0)), camera);
    const vis = k > 0.01 && !s.behind;
    B.lab.style.display = B.cnt.style.display = vis ? '' : 'none';
    B.lab.style.left = (s.x - 70) + 'px'; B.lab.style.top = (s.y + 16) + 'px'; B.lab.style.opacity = k.toFixed(3);
    const s3 = toScreen(B.center.clone().add(V(0, 0.2, 0)), camera);
    B.cnt.style.left = (s3.x - 14) + 'px'; B.cnt.style.top = (s3.y - 60) + 'px'; B.cnt.style.opacity = k.toFixed(3);
    B.cnt.textContent = counts[i];
  });
  const nk = smooth(remap(t, 49.2, 49.8)) * (1 - smooth(remap(t, 52, 52.8)));
  critic.note.style.display = nk > 0.01 ? '' : 'none'; critic.note.style.left = RX + 'px'; critic.note.style.top = RY + 'px'; critic.note.style.opacity = nk.toFixed(3);
}

// ---------------------------------------------------------------- committer: hash read-back, CAS, atomic publish
function buildCommit(ctx) {
  commit = {};
  const H = [
    ['candidate.npz', '4141108d51e4…3b501db'], ['ExecutionRecord', 'b9398507e0bd…82cfe6'], ['context.lock', '3e9e0524c1f7…a90d12'],
    ['labels.parquet', '21ce568b7d02…e44c71'], ['ledger.json', '8f204bc9aa31…5d08fe'],
  ];
  commit.lines = H.map(([n, h], i) => el(ctx.ui, 'abs mono', `<span style="color:rgba(238,243,255,0.55)">${n.padEnd(16, ' ')}</span> sha256 ${h} <span class="ok" style="color:#5ef2a8;opacity:0">✓</span>`,
    { fontSize: '23px', color: '#eef3ff', whiteSpace: 'pre', textTransform: 'none', letterSpacing: '0.02em' }));
  commit.plate = el(ctx.ui, 'abs', `<div class="mono" style="font-size:24px;color:#5ef2a8;letter-spacing:0.2em">CAS · PARENT MATCHED · ATOMIC</div>
    <div class="h2" style="font-size:96px;margin-top:10px">DatasetVersion published</div>
    <div class="zh-s" style="margin-top:14px">版本已原子发布 · 可追溯、不可原地覆盖</div>`, { whiteSpace: 'nowrap' });
  commit.wave = new Ribbon(circlePoints(1, 200, 0.003), { width: 6, color: '#5ef2a8', intensity: 3, glow: 0.6 });
  scene.add(commit.wave.mesh);
}
function updateCommit(t) {
  const anchor = stPos(ST[6]).clone().add(V(0, 0.32, 0));
  const s = toScreen(anchor, camera);
  commit.lines.forEach((e, i) => {
    const k = smooth(remap(t, 52.4 + i * 0.35, 52.8 + i * 0.35)) * (1 - smooth(remap(t, 58.2, 59)));
    e.style.display = k > 0.01 ? '' : 'none'; e.style.opacity = k.toFixed(3);
    e.style.left = RX + 'px'; e.style.top = (RY + i * 46) + 'px';
    e.querySelector('.ok').style.opacity = smooth(remap(t, 52.9 + i * 0.35, 53.1 + i * 0.35)).toFixed(3);
  });
  const pk = smooth(remap(t, 55.0, 55.6)) * (1 - smooth(remap(t, 58.6, 59.6)));
  commit.plate.style.display = pk > 0.01 ? '' : 'none'; commit.plate.style.opacity = pk.toFixed(3);
  commit.plate.style.left = '150px'; commit.plate.style.top = '640px';
  commit.plate.style.filter = pk < 0.98 ? `blur(${((1 - pk) * 14).toFixed(1)}px)` : 'none';
  const w = remap(t, 55.0, 57.5);
  const R = lerp(0.05, 3.2, easeOutCubic(w));
  commit.wave.mesh.scale.set(R, 1, R); commit.wave.mesh.position.set(0, 0, 0);
  commit.wave.set({ opacity: w > 0 && w < 1 ? (1 - w) : 0 });
}

// ---------------------------------------------------------------- render
const SCHED = [[0, 0], [2.4, 1], [5.0, 2], [12.0, 3], [20.0, 4], [26.0, 5], [29.0, 6], [33.0, 7], [37.0, 8], [46.0, 9], [52.0, 10], [57.0, 11]];
const BRANCH = [[16.9, 18.8, 0]];
const ACTIVE_NODE = [[5, 'EPISODE'], [12, 'EVIDENCE'], [20, 'SPATIAL'], [26, 'REPAIR_INTENT'], [29, 'GENERATE'], [33, 'PROJECT'], [37, 'SIMULATE'], [46, 'COMPARE'], [52, 'COMMIT']];

export async function render(t, ctx) {
  const c = camAt(t);
  camera.position.copy(c.pos); camera.lookAt(c.tgt);
  camera.updateMatrixWorld();

  // reconstruction: walls fade to a ghostly scan once the system starts working
  const wallK = 1 - 0.55 * smooth(remap(t, 3, 7));
  if (cloud.userData.wallK !== wallK.toFixed(3)) {
    const W = cloud.userData.wall, BA = cloud.userData.baseAlpha, A = cloud.geometry.attributes.alpha.array;
    for (let i = 0; i < A.length; i++) A[i] = W[i] ? BA[i] * wallK : BA[i];
    cloud.geometry.attributes.alpha.needsUpdate = true; cloud.userData.wallK = wallK.toFixed(3);
  }
  cloud.userData.mat.uniforms.uOpacity.value = smooth(remap(t, 0, 1.2)) * (1 - 0.25 * smooth(remap(t, 20, 22)) + 0.25 * smooth(remap(t, 37, 39)));
  floorRing.set({ opacity: 0.25 * smooth(remap(t, 0.5, 2.5)) });

  // stations
  let activeIdx = -1;
  ST.forEach((s, i) => { if (t >= s.t[0] && t < s.t[1]) activeIdx = i; });
  stations.forEach((e, i) => {
    const on = smooth(remap(t, 0.8 + i * 0.35, 1.6 + i * 0.35));
    const act = i === activeIdx ? 1 : 0;
    e.actK = lerp(e.actK || 0, act, 0.25);
    if (e.update) e.update(t, e.actK, i === 6 ? smooth(remap(t, 54.6, 55.2)) : 0);
    const camD = e.g.position.distanceTo(camera.position);
    e.fade(on * smooth(remap(camD, 0.9, 1.5)), e.actK);
    e.face(camera);
    e.g.scale.setScalar(1 + 0.18 * e.actK);
    e.tether.set({ opacity: on * (0.05 + 0.5 * e.actK), time: t, pulse: e.actK > 0.5 ? 0.9 : 0, pulseK: 4 });
    const sp = toScreen(e.g.position.clone().add(V(0, -0.36, 0)), camera);
    const L = labels[i];
    const lk = on * Math.max(smooth(remap(t, 3.4, 3.9)) * (1 - smooth(remap(t, 5.0, 5.6))), smooth(remap(t, 57.6, 58.4))) * (1 - smooth(remap(t, 59.3, 60)));
    L.style.display = lk > 0.01 && !sp.behind ? '' : 'none';
    L.style.left = (sp.x - 350) + 'px'; L.style.top = (sp.y) + 'px'; L.style.opacity = lk.toFixed(3);
  });
  captions.forEach((cp) => cp.update(t));

  let activeNode = ''; for (const [tt, n] of ACTIVE_NODE) if (t >= tt) activeNode = n;
  updateDAG(t, activeNode); updateFilm(t); updateSpatial(t); updateRepair(t); updateSim(t); updateCritic(t); updateCommit(t);
  packets.forEach((p) => p.update(t));

  const hudK = smooth(remap(t, 1.5, 3)) * (1 - smooth(remap(t, 59.2, 60)));
  rail.update(t, SCHED, BRANCH, hudK);
  budget.update([
    counter(t, [6.0, 17.0, 26.6, 46.2]), counter(t, [9.4, 13.0, 17.6, 20.2, 22.6, 29.2, 33.2, 37.8, 40.4, 43.0, 46.4, 52.4]),
    counter(t, [20.2, 22.6]), counter(t, [13.0, 17.6]), counter(t, [31.4, 31.85, 32.3, 32.75]), counter(t, [37.8, 38.6, 40.4, 41.2, 43.0, 44.0]), counter(t, [28.8]),
  ], hudK, t);
  title.update(t, 0.5, 3.6);
  chapter.update(t, 0.4, 59.4);
  footnote.style.opacity = (0.9 * hudK).toFixed(3);

  ctx.grade.uFade.value = smooth(remap(t, 0, 0.6)) * (1 - easeInCubic(remap(t, 59.4, 60)));
  ctx.bloomCfg.strength = 0.85; ctx.bloomCfg.threshold = 0.9;
  ctx.render(scene, camera);
}
