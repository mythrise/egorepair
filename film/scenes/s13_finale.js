// S13 — Finale: a tracked human hand and the robot gripper meet inside the ring. Tagline + logo.
import { THREE, el, clamp, lerp, remap, smooth, easeOutCubic, easeInOutCubic, easeInCubic, easeOutExpo, splitChars, revealChars, loadJSON } from '@engine/core.js';
import { makeRing, makeHalo, makePoints, Ribbon, makeHaze, spectralColor } from '@engine/fx.js';
import { fadeEl } from '@engine/ui.js';
import { RobotArm, robotMaterials } from '@engine/robot.js';
import { envLights } from './lib/world.js';

export const duration = 16;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
let scene, camera, ring, halo, hand, bones = [], joints, arm, spark, tag, zh, logo, sub, dust;
const R = 1.25;

export async function init(ctx) {
  scene = new THREE.Scene();
  scene.add(makeHaze({ top: '#060914', bottom: '#010103', glow: '#191433', glowDir: V(0, 0, 1), glowK: 0.5 }));
  camera = new THREE.PerspectiveCamera(30, ctx.W / ctx.H, 0.05, 200);
  envLights(scene, ctx.renderer, { envI: 0.55 });
  ring = makeRing({ radius: R, tube: 0.012, intensity: 4.5 }); scene.add(ring);
  halo = makeHalo({ size: R * 3.2, ringR: 0.62, ringW: 0.035, intensity: 0.35 }); halo.userData.mat.uniforms.uSpectral.value = 1; halo.userData.mat.uniforms.uCenterW.value = 0; scene.add(halo);

  // real tracked hand: EgoDex frame 107, open flat hand (highest finger extension in the MediaPipe track)
  const H = await loadJSON('/assets/data/hands_ego_raw.json');
  const best = H.frames[107][0].world;
  const P = best.map(([x, y, z]) => V(x, -y, -z));
  const f = P[9].clone().sub(P[0]).normalize();
  let s = P[5].clone().sub(P[17]); s.sub(f.clone().multiplyScalar(s.dot(f))).normalize();
  const n = new THREE.Vector3().crossVectors(f, s);
  const basis = new THREE.Matrix4().makeBasis(f, s, n).invert(); // hand frame -> canonical (x = fingers, y = across palm, z = normal)
  const tilt = new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(0.45, -0.35, -0.08));
  const tip = P[8].clone().applyMatrix4(basis);
  hand = new THREE.Group(); scene.add(hand);
  const scale = 6.0;
  const HP = P.map((p) => p.clone().applyMatrix4(basis).sub(tip).applyMatrix4(tilt).multiplyScalar(scale));
  for (const [a, b] of H.edges) {
    const rb = new Ribbon([HP[a], HP[b]], { width: 7, color: '#bfe6ff', intensity: 2.2, glow: 0.5 });
    const vol = new Ribbon([HP[a], HP[b]], { width: 70, color: '#7fb8ff', intensity: 0.22, glow: 1.0 });
    hand.add(vol.mesh, rb.mesh); bones.push(rb, vol);
  }
  // translucent palm
  const pg = new THREE.BufferGeometry().setFromPoints([0, 1, 5, 0, 5, 9, 0, 9, 13, 0, 13, 17].map((i) => HP[i]));
  const palm = new THREE.Mesh(pg, new THREE.MeshBasicMaterial({ color: new THREE.Color('#6fa8ff').multiplyScalar(0.18), transparent: true, opacity: 1, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
  hand.add(palm); hand.userData.palm = palm;
  joints = makePoints(21, { soft: 0.35 }); hand.add(joints);
  HP.forEach((p, i) => { joints.geometry.attributes.position.setXYZ(i, p.x, p.y, p.z); joints.geometry.attributes.color.setXYZ(i, 2.4, 2.8, 3.2); joints.geometry.attributes.size.setX(i, [4, 8, 12, 16, 20].includes(i) ? 0.07 : 0.05); });
  joints.geometry.attributes.position.needsUpdate = true; joints.geometry.attributes.color.needsUpdate = true;
  hand.userData.tip = V(0, 0, 0);

  // robot arm reaching from the right
  arm = new RobotArm({ scale: 3.0, mats: robotMaterials({ accent: '#9fd8ff', accentI: 3.5 }) });
  arm.root.position.set(2.5, -1.75, -0.6); scene.add(arm.root);
  spark = makeHalo({ size: 0.5, color: '#ffffff', intensity: 0 }); scene.add(spark);
  // dust
  const N = 1400; dust = makePoints(N, { soft: 0.8 }); dust.seed = [];
  for (let i = 0; i < N; i++) { const a = Math.random() * 6.283, r = R * (0.95 + Math.random() * 0.1) + (Math.random() < 0.15 ? Math.random() * 0.6 : 0); dust.seed.push([a, r, (Math.random() - 0.5) * 0.15, 0.04 + Math.random() * 0.12]); const c = spectralColor(a / 6.283); dust.geometry.attributes.color.setXYZ(i, c.r * 1.8, c.g * 1.8, c.b * 1.8); dust.geometry.attributes.size.setX(i, 0.006 + Math.random() * 0.01); }
  dust.geometry.attributes.color.needsUpdate = true; scene.add(dust);

  tag = el(ctx.ui, 'abs h1 center', '', { left: '0px', width: '3840px', top: '1720px', fontSize: '112px', fontWeight: 500, letterSpacing: '-0.03em' });
  tag.spans = splitChars(tag, 'Let every demonstration reach the future.');
  zh = el(ctx.ui, 'abs center', '让演示，触达未来。', { left: '0px', width: '3840px', top: '1890px', fontFamily: "'Noto Sans SC'", fontWeight: 400, fontSize: '64px', letterSpacing: '0.3em', color: 'rgba(238,243,255,0.9)' });
  logo = el(ctx.ui, 'abs center', `<svg width="190" height="120" viewBox="0 0 190 120" style="vertical-align:middle;margin-right:46px"><defs><linearGradient id="lg" x1="0" x2="1"><stop offset="0" stop-color="#ffb27a"/><stop offset="0.35" stop-color="#ff7eb6"/><stop offset="0.6" stop-color="#a98bff"/><stop offset="1" stop-color="#67e3c9"/></linearGradient></defs><path d="M10 92 L70 22 L104 22 L44 92 Z" fill="url(#lg)"/><path d="M86 98 L146 28 L180 28 L120 98 Z" fill="#eef3ff"/></svg><span style="font-family:'Inter Display';font-weight:600;font-size:190px;letter-spacing:-0.04em;vertical-align:middle">EgoRepair</span><span style="font-family:'Inter Display';font-weight:300;font-size:190px;letter-spacing:-0.03em;vertical-align:middle;margin-left:40px;color:rgba(238,243,255,0.75)">Studio</span>`, { left: '0px', width: '3840px', top: '860px' });
  sub = el(ctx.ui, 'abs center', `<div class="mono" style="font-size:30px;letter-spacing:0.3em;color:rgba(238,243,255,0.7)">FROM HUMAN DEMONSTRATION TO ROBOT-READY DATA</div><div class="zh-s" style="font-size:38px;margin-top:26px">从人类演示，到机器人可训练数据</div>`, { left: '0px', width: '3840px', top: '1180px' });
}

export async function render(t, ctx) {
  const push = easeInOutCubic(remap(t, 0, 9));
  camera.position.set(lerp(0.3, 0, push), lerp(0.25, 0.05, push), lerp(7.6, 5.6, push) + easeInCubic(remap(t, 9.2, 10.6)) * -3.5);
  camera.lookAt(0, lerp(-0.2, -0.32, push), 0);
  camera.updateMatrixWorld();
  const ign = remap(t, 0.3, 2.2), arc = easeOutExpo(ign);
  const ru = ring.userData.mat.uniforms;
  ru.uTime.value = t; ru.uArc.value = arc; ru.uArcStart.value = 0.25 - arc * 0.5;
  const meet = 5.4;
  const flare = Math.exp(-Math.pow((t - meet - 0.25) * 2.2, 2));
  ru.uIntensity.value = 4.5 + 10 * flare; ru.uOpacity.value = smooth(remap(t, 0.2, 0.6));
  halo.userData.mat.uniforms.uI.value = (0.35 + 0.6 * flare) * smooth(remap(t, 1.2, 2.6)); halo.userData.mat.uniforms.uTime.value = t;
  // hand approaches from the left, robot from the right; they stop a breath apart
  const ap = easeOutCubic(remap(t, 1.0, meet));
  hand.position.set(lerp(-3.4, -0.07, ap), lerp(-0.5, 0.02, ap) + Math.sin(t * 1.3) * 0.01, lerp(0.6, 0.0, ap));
  const hk = smooth(remap(t, 1.0, 2.2)) * (1 - smooth(remap(t, 9.4, 10.2)));
  bones.forEach((b) => b.set({ opacity: hk }));
  joints.userData.mat.uniforms.uOpacity.value = hk;
  hand.userData.palm.material.opacity = hk;
  const tcp = V(lerp(2.2, 0.075, ap), lerp(-0.4, 0.02, ap), lerp(0.4, 0.0, ap));
  arm.solve(tcp.clone().sub(arm.root.position), V(-1, -0.05, 0).normalize(), Math.PI / 2);
  arm.setGripper(0.5 + 0.3 * smooth(remap(t, meet, meet + 1)));
  arm.root.visible = t < 10.2;
  arm.root.traverse((o) => { if (o.material && o.material.opacity !== undefined) { o.material.transparent = true; o.material.opacity = smooth(remap(t, 1.0, 2.2)) * (1 - smooth(remap(t, 9.4, 10.2))); } });
  spark.position.set(0, 0.02, 0.02); spark.quaternion.copy(camera.quaternion);
  spark.userData.mat.uniforms.uI.value = 2.2 * flare;
  const g = dust.geometry;
  dust.seed.forEach(([a0, r, w, sp], i) => { const a = a0 + t * sp; const b = 1 + 0.4 * flare; g.attributes.position.setXYZ(i, Math.cos(a) * r * b, Math.sin(a) * r * b, w); g.attributes.alpha.setX(i, smooth(remap(t, 1.5, 3)) * (1 - smooth(remap(t, 13.8, 15)))); });
  g.attributes.position.needsUpdate = true; g.attributes.alpha.needsUpdate = true;
  revealChars(tag.spans, remap(t, 6.0, 8.2), { stagger: 0.03, dur: 0.6, rise: 40, blur: 22 });
  const tagOut = easeInCubic(remap(t, 9.2, 9.9));
  tag.style.opacity = (1 - tagOut).toFixed(3); tag.style.filter = tagOut > 0.01 ? `blur(${(tagOut * 20).toFixed(1)}px)` : 'none';
  fadeEl(zh, smooth(remap(t, 7.0, 8.2)) * (1 - tagOut), { blur: 14, dy: 16 });
  const lk = smooth(remap(t, 10.4, 11.6)) * (1 - smooth(remap(t, 14.6, 15.6)));
  fadeEl(logo, lk, { blur: 24 });
  logo.style.transform = `scale(${(1.04 - 0.04 * easeOutCubic(remap(t, 10.4, 12.5))).toFixed(4)})`;
  fadeEl(sub, smooth(remap(t, 11.3, 12.4)) * (1 - smooth(remap(t, 14.6, 15.6))), { blur: 10, dy: 14 });
  ctx.grade.uFade.value = smooth(remap(t, 0, 0.5)) * (1 - smooth(remap(t, 15.2, 16)));
  ctx.bloomCfg.strength = 1.0; ctx.bloomCfg.threshold = 0.75;
  ctx.render(scene, camera);
}
