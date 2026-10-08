// S07 — Eight modules, one evidence chain: an episode flies through gates M0..M7 and is transformed at each.
import { THREE, el, clamp, lerp, remap, smooth, easeOutCubic, easeInOutCubic, easeInCubic, rng, SeqTexture } from '@engine/core.js';
import { makeRing, makeHalo, makePoints, Ribbon, makePanel, makeHaze, makeGrid, toScreen, spectralColor, circlePoints } from '@engine/fx.js';
import { Title, Chapter, fadeEl } from '@engine/ui.js';
import { RobotArm, robotMaterials } from '@engine/robot.js';
import { loadCloud, makeHandPath, envLights } from './lib/world.js';

export const duration = 24;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const GAP = 2.4, T0 = 3.2, SPEED = GAP / 2.2; // a gate every 2.2 s
const MODS = [
  ['M0', 'Evidence binding & spatiotemporal contract', '证据捆绑与时空合同'],
  ['M1', 'Spatial understanding', '专业空间理解'],
  ['M2', 'Global coordination & conflict arbitration', '全局协调与冲突裁决'],
  ['M3', 'Contact & force priors', '接触与力先验'],
  ['M4', 'Conditional residual diffusion repair', '条件残差扩散修复'],
  ['M5', 'Feasibility projection', '可行性投影'],
  ['M6', 'Physics replay & task acceptance', '物理回放与任务验收'],
  ['M7', 'Quality evaluation & post-training', '质量评估与后训练'],
];

let scene, camera, gates = [], pay, card, seq, cloud, traj, ghostA, ghostB, contacts, noise, tube, arm, tag, hashLbl, title, chapter, rail, railDots = [], modLab, flashes = [];
const gateX = (i) => i * GAP;
const payX = (t) => (t - T0) * SPEED - 0.9;

export async function init(ctx) {
  scene = new THREE.Scene();
  scene.add(makeHaze({ top: '#081024', bottom: '#020306', glow: '#1b1840', glowDir: V(1, 0.1, 0), glowK: 0.5 }));
  camera = new THREE.PerspectiveCamera(36, ctx.W / ctx.H, 0.02, 1000);
  envLights(scene, ctx.renderer, { envI: 0.5 });
  const grid = makeGrid({ size: 60, cell: 0.25, major: 4, color: '#5f7cff', opacity: 0.18, fade: 9 });
  grid.position.set(9, -1.05, 0); grid.userData.mat.uniforms.uCenter.value.set(9, 0); scene.add(grid);
  const spine = new Ribbon([V(-6, -0.98, 0), V(24, -0.98, 0)], { width: 3, color: '#6f8cff', intensity: 0.8 }); scene.add(spine.mesh);

  MODS.forEach((m, i) => {
    const ring = makeRing({ radius: 0.95, tube: 0.008, intensity: 3.2 });
    ring.rotation.y = Math.PI / 2; ring.position.x = gateX(i); ring.userData.mat.uniforms.uHueShift.value = i / 8;
    const halo = makeHalo({ size: 2.6, ringR: 0.73, ringW: 0.05, intensity: 0.0, color: '#8f7dff' });
    halo.userData.mat.uniforms.uSpectral.value = 1; halo.rotation.y = Math.PI / 2; halo.position.x = gateX(i);
    scene.add(ring, halo);
    const lab = el(ctx.ui, 'abs', `<div class="mono" style="font-size:30px;color:#eef3ff;letter-spacing:0.2em">${m[0]}</div>`, { whiteSpace: 'nowrap' });
    gates.push({ ring, halo, lab });
  });

  pay = new THREE.Group(); scene.add(pay);
  // the episode card (real EgoDex video)
  seq = new SeqTexture('/assets/footage/ego_raw', 302, { srcFps: 30 });
  card = makePanel(1.28, 0.72, { radius: 0.03, border: 0.005, borderColor: '#bcd2ff', borderI: 0.9 });
  card.rotation.y = -Math.PI / 2 + 0.0; pay.add(card);
  // reconstruction (appears at M1)
  cloud = await loadCloud('/assets/scene/ego0', { darken: 0.9, sat: 0.9, size: 0.006, wallKeep: 0.25 });
  cloud.scale.setScalar(0.9); cloud.position.set(0, -0.32, 0); cloud.rotation.y = -Math.PI / 2; pay.add(cloud);
  const curve = makeHandPath(cloud.userData.meta);
  const TP = curve.getSpacedPoints(200).map((p) => p.clone().multiplyScalar(0.9).applyAxisAngle(V(0, 1, 0), -Math.PI / 2).add(V(0, -0.32, 0)));
  traj = new Ribbon(TP, { width: 7, color: '#ffffff', intensity: 2, glow: 0.4 }); pay.add(traj.mesh);
  const r = rng(4);
  const wob = (k, a) => TP.map((p, i) => p.clone().add(V(Math.sin(i * 0.11 + k) * a, Math.cos(i * 0.07 + k) * a * 0.6, Math.sin(i * 0.05 + k * 2) * a)));
  ghostA = new Ribbon(wob(1, 0.05), { width: 5, color: '#ff4d5e', intensity: 1.8 }); ghostB = new Ribbon(wob(4, 0.05), { width: 5, color: '#6cb8ff', intensity: 1.8 });
  pay.add(ghostA.mesh, ghostB.mesh); ghostA.TP = wob(1, 0.05); ghostB.TP = wob(4, 0.05); ghostA.T = TP; ghostB.T = TP;
  contacts = makePoints(6, { soft: 0.2 }); pay.add(contacts);
  const cp = TP[62];
  for (let i = 0; i < 6; i++) { const a = i / 6 * Math.PI * 2; contacts.geometry.attributes.position.setXYZ(i, cp.x + Math.cos(a) * 0.035, cp.y - 0.01, cp.z + Math.sin(a) * 0.035); contacts.geometry.attributes.color.setXYZ(i, 3, 1.6, 0.6); contacts.geometry.attributes.size.setX(i, 0.03); }
  contacts.geometry.attributes.position.needsUpdate = true; contacts.geometry.attributes.color.needsUpdate = true;
  contacts.cp = cp;
  const NN = 900; noise = makePoints(NN, { soft: 0.5 }); pay.add(noise); noise.seeds = [];
  for (let i = 0; i < NN; i++) { noise.seeds.push([Math.floor(r() * 200), (r() - 0.5) * 2, (r() - 0.5) * 2, (r() - 0.5) * 2]); const c = spectralColor(r()); noise.geometry.attributes.color.setXYZ(i, c.r * 2.2, c.g * 2.2, c.b * 2.2); noise.geometry.attributes.size.setX(i, 0.012); }
  noise.geometry.attributes.color.needsUpdate = true; noise.TP = TP;
  tube = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(TP), 200, 0.05, 24, false),
    new THREE.MeshBasicMaterial({ color: new THREE.Color('#ffb27a').multiplyScalar(0.25), transparent: true, opacity: 0.0, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide }));
  pay.add(tube);
  arm = new RobotArm({ scale: 0.9, mats: robotMaterials({ accent: '#6cb8ff', accentI: 3 }) });
  arm.root.position.set(0.2, -0.32, 0.25); pay.add(arm.root); arm.curve = TP;
  hashLbl = el(ctx.ui, 'abs mono', '', { fontSize: '24px', color: '#eef3ff', whiteSpace: 'nowrap', textTransform: 'none' });
  tag = el(ctx.ui, 'abs', '', { whiteSpace: 'nowrap' });

  // module progress rail (bottom)
  rail = el(ctx.ui, 'abs', '', { left: '150px', top: '1960px', width: '3540px', height: '120px' });
  el(rail, 'abs', '', { left: '0px', top: '20px', width: '3540px', height: '2px', background: 'rgba(238,243,255,0.15)' });
  MODS.forEach((m, i) => {
    const d = el(rail, 'abs', '', { left: (i * 3540 / 7 - 9) + 'px', top: '12px', width: '18px', height: '18px', borderRadius: '50%', background: '#04060a', border: '2px solid rgba(238,243,255,0.35)' });
    const l = el(rail, 'abs mono', m[0], { left: (i * 3540 / 7 - 40) + 'px', top: '50px', width: '80px', textAlign: 'center', fontSize: '24px' });
    railDots.push({ d, l });
  });
  modLab = el(ctx.ui, 'abs', '', { left: '150px', top: '240px', width: '2600px' });
  modLab.k = el(modLab, 'mono', '', { fontSize: '28px', color: 'rgba(238,243,255,0.6)' });
  modLab.n = el(modLab, 'h2', '', { fontSize: '96px', marginTop: '16px' });
  modLab.z = el(modLab, 'zh-s', '', { fontSize: '40px', marginTop: '18px' });
  title = new Title(ctx.ui, { en: 'Eight modules. One evidence chain.', zh: '八个模块 · 一条证据链', y: 470, size: 140 });
  chapter = new Chapter(ctx.ui, '02', 'THE SYSTEM', '系统');
}

export async function render(t, ctx) {
  const px = payX(t);
  pay.position.set(px, 0, 0);
  // gate index that payload has passed
  const g = (px + 0.0) / GAP; // fractional gate position
  const stage = Math.floor(g + 0.02); // 0 after passing M0 ...
  const sp = (i) => smooth(remap(g, i - 0.08, i + 0.12)); // transition as payload crosses gate i
  // camera: starts behind the payload looking down the rail, swings to a side tracking shot
  const k1 = smooth(remap(t, 0.4, 4.0)), k2 = smooth(remap(t, 15, 24));
  const az = lerp(lerp(2.75, 2.28, k1), 1.95, k2);
  const R = lerp(lerp(3.4, 2.55, k1), 2.8, k2), hh = lerp(lerp(0.85, 0.5, k1), 0.66, k2);
  const look = V(px + lerp(0.9, 0.3, k1) + 0.2 * k2, lerp(0.05, -0.05, k1), lerp(0, 0.35, k1));
  camera.position.set(look.x + Math.cos(az) * R, look.y + hh, Math.sin(az) * R);
  camera.lookAt(look);
  camera.updateMatrixWorld();

  // gates
  gates.forEach((G, i) => {
    const d = px - gateX(i);
    const pass = Math.exp(-Math.pow(d / 0.35, 2));
    G.ring.userData.mat.uniforms.uTime.value = t;
    G.ring.userData.mat.uniforms.uIntensity.value = (d > 0.4 ? 1.1 : 2.6) + 9 * pass;
    G.ring.userData.mat.uniforms.uOpacity.value = smooth(remap(t, 0.2 + i * 0.12, 1.0 + i * 0.12));
    G.halo.userData.mat.uniforms.uI.value = 0.18 + 0.7 * pass;
    G.halo.userData.mat.uniforms.uTime.value = t;
    const s = toScreen(V(gateX(i), 1.12, 0), camera);
    const k = smooth(remap(t, 0.6 + i * 0.12, 1.4 + i * 0.12)) * (s.behind ? 0 : 1) * (1 - smooth(remap(t, 22.6, 23.6)));
    G.lab.style.display = k > 0.01 ? '' : 'none'; G.lab.style.left = (s.x - 30) + 'px'; G.lab.style.top = (s.y - 30) + 'px';
    G.lab.style.opacity = (k * (0.45 + 0.55 * Math.max(pass, d > -0.2 && d < GAP * 0.8 ? 1 : 0))).toFixed(3);
  });

  // payload content by stage
  const tex = await seq.at(t);
  card.userData.setMap(tex);
  const cu = card.userData.mat.uniforms;
  const m1 = sp(1);
  cu.uOpacity.value = 1 - m1; cu.uBright.value = 1.0; cu.uSat.value = 1 - 0.3 * sp(0);
  cu.uBorderI.value = 0.6 + 1.4 * sp(0) * (1 - m1);
  cu.uBorderColor.value.set(sp(0) > 0.5 ? '#74d7ff' : '#bcd2ff');
  card.position.set(0, lerp(0, 0.55, m1), lerp(0, -0.45, m1)); card.scale.setScalar(lerp(1, 0.55, m1));
  cloud.userData.mat.uniforms.uOpacity.value = m1;
  cloud.position.y = -0.32 + (1 - m1) * 0.2; cloud.scale.setScalar(0.9 * lerp(0.6, 1, easeOutCubic(m1)));
  // M2: two conflicting estimates merge into one
  const m2 = sp(2), mg = smooth(remap(g, 2.05, 2.6));
  for (const G of [ghostA, ghostB]) { G.setPoints(G.TP.map((p, i) => p.clone().lerp(G.T[i], mg))); G.set({ opacity: m2 * (1 - smooth(remap(g, 2.5, 2.7))), head: 1 }); }
  traj.set({ opacity: smooth(remap(g, 2.45, 2.65)), head: 1 });
  // M3: contacts
  const m3 = sp(3);
  contacts.userData.mat.uniforms.uOpacity.value = m3 * (0.7 + 0.3 * Math.sin(t * 8));
  // M4: diffusion noise collapses onto the curve
  const m4 = sp(4);
  const sig = 0.35 * (1 - easeOutCubic(remap(g, 4.0, 4.75)));
  const ng = noise.geometry;
  noise.seeds.forEach(([j, a, b, c], i) => { const p = noise.TP[j]; ng.attributes.position.setXYZ(i, p.x + a * sig, p.y + b * sig, p.z + c * sig); ng.attributes.alpha.setX(i, m4 * (1 - smooth(remap(g, 4.7, 5.0)))); });
  ng.attributes.position.needsUpdate = true; ng.attributes.alpha.needsUpdate = true;
  // M5: feasibility tube
  tube.material.opacity = sp(5) * (1 - smooth(remap(g, 5.9, 6.3))) * 0.9;
  // M6: robot replays the repaired reference
  const m6 = sp(6);
  arm.root.visible = m6 > 0.02;
  if (arm.root.visible) {
    const u = clamp(remap(g, 6.0, 6.95));
    const idx = Math.floor(lerp(20, 190, easeInOutCubic(u)));
    const target = arm.curve[idx].clone().sub(arm.root.position);
    arm.solve(target, V(0, -1, 0.25).normalize(), 0); arm.setGripper(u < 0.25 ? 1 : 0.2);
    arm.root.scale.setScalar(0.9 * easeOutCubic(m6));
  }
  // labels: M0 hashes, M6 PASS, M7 export tag
  const pc = toScreen(V(px, 0.1, 0), camera);
  const h0 = sp(0) * (1 - sp(1));
  hashLbl.style.display = h0 > 0.01 ? '' : 'none'; hashLbl.style.opacity = h0.toFixed(3);
  hashLbl.style.left = (pc.x + 760) + 'px'; hashLbl.style.top = (pc.y - 60) + 'px';
  hashLbl.innerHTML = 'src sha256 9c41…e07a <span style="color:#5ef2a8">✓</span><br>PTS · K · crop · split <span style="color:#5ef2a8">locked</span><br><span style="color:rgba(238,243,255,0.55)">302 frames · 30 fps · 10.07 s</span>';
  const tk6 = sp(6) * (1 - sp(7)), tk7 = sp(7);
  tag.style.display = tk6 + tk7 > 0.01 ? '' : 'none';
  tag.style.left = (pc.x + 560) + 'px'; tag.style.top = (pc.y - 80) + 'px';
  tag.innerHTML = tk7 > 0.01 ? `<div class="mono" style="font-size:24px;color:#5ef2a8;opacity:${tk7.toFixed(3)}">QUALITY · HELP / NEUTRAL / HARM / UNKNOWN</div><div class="h3" style="font-size:64px;margin-top:10px;opacity:${tk7.toFixed(3)}">→ LeRobot export</div>`
    : `<div class="h3" style="font-size:70px;color:#5ef2a8;opacity:${tk6.toFixed(3)};text-shadow:0 0 30px #5ef2a8">PASS</div><div class="mono" style="font-size:22px;opacity:${tk6.toFixed(3)}">physics replay · unassisted · task gate</div>`;

  // module caption + rail
  const cur = clamp(Math.floor(g + 0.5), 0, 7);
  const ck = smooth(remap(t, T0 - 0.4, T0 + 0.4)) * (1 - smooth(remap(t, 22.4, 23.4)));
  modLab.style.opacity = ck.toFixed(3);
  if (modLab.cur !== cur) { modLab.cur = cur; modLab.k.textContent = `${MODS[cur][0]}  ·  MODULE ${cur + 1} / 8`; modLab.n.textContent = MODS[cur][1]; modLab.z.textContent = MODS[cur][2]; }
  const fr = g - Math.round(g); const pulse = Math.exp(-Math.pow(fr / 0.12, 2));
  modLab.n.style.transform = `translateX(${(-20 * (1 - smooth(remap(Math.abs(fr), 0, 0.2)))).toFixed(1)}px)`;
  rail.style.opacity = ck.toFixed(3);
  railDots.forEach((R, i) => {
    const done = g > i - 0.05, act = i === cur;
    R.d.style.background = done ? (act ? '#ffffff' : '#74d7ff') : '#04060a';
    R.d.style.borderColor = done ? '#74d7ff' : 'rgba(238,243,255,0.35)';
    R.d.style.boxShadow = act ? `0 0 ${(18 + 16 * pulse).toFixed(0)}px #74d7ff` : 'none';
    R.l.style.color = act ? '#ffffff' : done ? 'rgba(116,215,255,0.8)' : 'rgba(238,243,255,0.35)';
  });
  title.update(t, 0.3, 3.0);
  chapter.update(t, 0.2, 23.4);
  ctx.grade.uFade.value = smooth(remap(t, 0, 0.5)) * (1 - easeInCubic(remap(t, 23.3, 24)));
  ctx.bloomCfg.strength = 0.9; ctx.bloomCfg.threshold = 0.85;
  ctx.render(scene, camera);
}
