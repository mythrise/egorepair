// S10 — The result: human video -> robot reference (ring wipe), synced triptych, recorded physics replay.
import { THREE, el, clamp, lerp, remap, smooth, easeOutCubic, easeInOutCubic, easeInCubic, SeqTexture, loadImage } from '@engine/core.js';
import { makePanel, makeRing, makeHalo, makeHaze, toScreen } from '@engine/fx.js';
import { Title, Chapter, fadeEl } from '@engine/ui.js';

export const duration = 26;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
let scene, camera, ego, hyb, insp, sEgo, sHyb, sInsp, ring, halo, labs = [], title, t2, chapter, simP, simTex = [], bigSim, simLab, simLab2, cap, foot;

export async function init(ctx) {
  scene = new THREE.Scene();
  scene.add(makeHaze({ top: '#060a14', bottom: '#010203', glow: '#141a36', glowK: 0.4 }));
  camera = new THREE.PerspectiveCamera(30, ctx.W / ctx.H, 0.05, 100);
  sEgo = new SeqTexture('/assets/footage/ego_raw', 302); sHyb = new SeqTexture('/assets/footage/robot_hybrid', 302); sInsp = new SeqTexture('/assets/footage/inspect', 302);
  ego = makePanel(1.6, 0.9, { radius: 0.018, border: 0.004, borderColor: '#bcd2ff', borderI: 0.6 });
  hyb = makePanel(1.6, 0.9, { radius: 0.018, border: 0.004, borderColor: '#74d7ff', borderI: 0.6 });
  insp = makePanel(1.6, 0.9, { radius: 0.018, border: 0.004, borderColor: '#67e3c9', borderI: 0.6 });
  scene.add(hyb, ego, insp);
  ring = makeRing({ radius: 0.62, tube: 0.006, intensity: 6 }); ring.rotation.y = Math.PI / 2; scene.add(ring);
  halo = makeHalo({ size: 1.8, ringR: 0.69, ringW: 0.04, intensity: 0.5 }); halo.userData.mat.uniforms.uSpectral.value = 1; halo.userData.mat.uniforms.uCenterW.value = 0; scene.add(halo);
  const L = [['ORIGINAL · EGODEX', '原始第一人称视频', '#bcd2ff'], ['ROBOT REFERENCE · A2 HYBRID', '机器人参考（整臂 / 工具）', '#74d7ff'], ['FIXED-BASE INSPECTION', '固定基座检查', '#67e3c9']];
  L.forEach(([a, b, c]) => labs.push(el(ctx.ui, 'abs', `<div class="mono" style="font-size:26px;color:${c}">${a}</div><div class="zh-s" style="font-size:30px;margin-top:8px">${b}</div>`, { whiteSpace: 'nowrap' })));
  // recorded physics replay (development scene F)
  bigSim = makePanel(1.144, 0.9, { radius: 0.014, border: 0.004, borderColor: '#74d7ff', borderI: 0.8 }); scene.add(bigSim);
  simP = makePanel(1.44, 0.9, { radius: 0.014, border: 0.004, borderColor: '#5ef2a8', borderI: 0.8 }); scene.add(simP);
  bigSim.seq = new SeqTexture('/assets/footage/plan_a1x', 302); simP.seq = new SeqTexture('/assets/footage/mujoco', 141, { srcFps: 16 });
  simLab = el(ctx.ui, 'abs', `<div class="mono" style="font-size:26px;color:#74d7ff">A1X FULL PLANNING TRAJECTORY · SAME EPISODE</div><div class="mono" style="font-size:22px;margin-top:12px;color:rgba(238,243,255,0.6);text-transform:none">kinematics only · dynamics not simulated · task success not certified</div><div class="zh-s" style="font-size:30px;margin-top:12px">完整规划轨迹 · 仅运动学可视化 · 未认证任务成功</div>`, { whiteSpace: 'nowrap' });
  simLab2 = el(ctx.ui, 'abs', `<div class="mono" style="font-size:26px;color:#5ef2a8">RECORDED PHYSICS REPLAY · ORIGINAL FULL TASK PASS</div><div class="mono" style="font-size:22px;margin-top:12px;color:rgba(238,243,255,0.6);text-transform:none">development scene F · recorded policy trial · synthetic sim · not hardware</div><div class="zh-s" style="font-size:30px;margin-top:12px">已记录的仿真回放 · 开发场景 F · 非真机</div>`, { whiteSpace: 'nowrap' });
  title = new Title(ctx.ui, { en: 'From human video to robot reference.', zh: '从人类视频，到机器人参考轨迹', y: 250, size: 120 });
  t2 = new Title(ctx.ui, { en: 'Then it has to survive physics.', zh: '然后，它必须经得起物理检验', y: 250, size: 120 });
  chapter = new Chapter(ctx.ui, '04', 'THE RESULT', '成果');
  cap = el(ctx.ui, 'abs mono', 'SAME EPISODE · SAME CLOCK · 302 FRAMES · 30 FPS', { left: '0px', width: '3840px', textAlign: 'center', top: '1830px', fontSize: '26px', color: 'rgba(238,243,255,0.6)' });
  foot = el(ctx.ui, 'abs mono', 'Left arm: whole-arm IK reference · right hand: tool-only where no feasible arm configuration exists — failures stay visible', { left: '0px', width: '3840px', textAlign: 'center', top: '1890px', fontSize: '22px', color: 'rgba(238,243,255,0.45)', textTransform: 'none' });
}

export async function render(t, ctx) {
  camera.position.set(0, 0.06, lerp(2.75, 2.55, smooth(remap(t, 0, 9)))); camera.lookAt(0, -0.04, 0);
  const pt = t * 0.95;
  ego.userData.setMap(await sEgo.at(pt)); hyb.userData.setMap(await sHyb.at(pt)); insp.userData.setMap(await sInsp.at(pt));
  // phase A: ring wipe reveals the robot reference behind the human video
  const wipe = easeInOutCubic(remap(t, 2.4, 6.4));
  const tri = easeInOutCubic(remap(t, 8.6, 10.6));
  const out = easeInOutCubic(remap(t, 16.4, 17.6));
  const eu = ego.userData.mat.uniforms, hu = hyb.userData.mat.uniforms, iu = insp.userData.mat.uniforms;
  eu.uWipe.value = lerp(1.05, -0.05, wipe); eu.uWipeSoft.value = 0.002;
  // positions: overlapping centre -> triptych
  const sp = 1.72;
  ego.position.set(lerp(0, -sp, tri), lerp(-0.04, 0, tri), lerp(0.001, 0, tri));
  hyb.position.set(0, lerp(-0.04, 0, tri), 0);
  insp.position.set(lerp(0, sp, tri), 0, -0.001);
  const fadeIn = smooth(remap(t, 0, 0.8));
  eu.uOpacity.value = fadeIn * (1 - out); hu.uOpacity.value = fadeIn * (1 - out); iu.uOpacity.value = smooth(remap(t, 9.0, 10.4)) * (1 - out); iu.uBright.value = 0.78;
  // during the triptych, unwipe the original so all three show
  if (tri > 0.001) eu.uWipe.value = lerp(-0.05, 1.2, smooth(remap(tri, 0.0, 0.35)));
  const triScale = lerp(1, 0.94, tri);
  [ego, hyb, insp].forEach((p) => p.scale.setScalar(triScale));
  camera.position.z = lerp(camera.position.z, 5.75, tri);
  // ring rides the wipe edge
  const rx = lerp(0.85, -0.85, wipe);
  ring.position.set(rx, -0.04, 0.02); halo.position.copy(ring.position);
  ring.scale.set(1, 0.92, 1);
  const rk = Math.min(smooth(remap(t, 2.0, 2.6)), 1 - smooth(remap(t, 6.4, 7.2)));
  ring.userData.mat.uniforms.uOpacity.value = rk; ring.userData.mat.uniforms.uTime.value = t;
  halo.userData.mat.uniforms.uI.value = 0.5 * rk; halo.quaternion.copy(camera.quaternion); halo.rotation.y = Math.PI / 2;
  camera.updateMatrixWorld();
  // labels under each panel
  [ego, hyb, insp].forEach((p, i) => {
    const s = toScreen(p.position.clone().add(V(-0.78 * triScale, -0.5 * triScale, 0)), camera);
    const k = smooth(remap(t, 10.2 + i * 0.2, 10.8 + i * 0.2)) * (1 - out);
    labs[i].style.left = s.x + 'px'; labs[i].style.top = s.y + 'px'; fadeEl(labs[i], k);
  });
  fadeEl(cap, smooth(remap(t, 11, 11.8)) * (1 - out)); fadeEl(foot, smooth(remap(t, 11.6, 12.4)) * (1 - out));
  // phase C: physics replay
  const ck = smooth(remap(t, 17.4, 18.4)) * (1 - smooth(remap(t, 25.2, 26)));
  bigSim.position.set(-0.68, -0.05, 0); simP.position.set(0.78, -0.05, 0);
  bigSim.userData.mat.uniforms.uOpacity.value = ck; simP.userData.mat.uniforms.uOpacity.value = ck;
  if (ck > 0) {
    bigSim.userData.setMap(await bigSim.seq.at(Math.max(t - 17.4, 0) * 1.0));
    simP.userData.setMap(await simP.seq.at(Math.max(t - 17.4, 0)));
    camera.position.set(0, 0, lerp(3.25, 3.1, remap(t, 17.4, 26))); camera.lookAt(0, -0.05, 0); camera.updateMatrixWorld();
  }
  const lk = smooth(remap(t, 18.4, 19.2)) * (1 - smooth(remap(t, 25.2, 26)));
  const sl = toScreen(V(-0.68 - 0.572, -0.56, 0), camera), sl2 = toScreen(V(0.78 - 0.72, -0.56, 0), camera);
  simLab.style.left = sl.x + 'px'; simLab.style.top = sl.y + 'px'; fadeEl(simLab, lk);
  simLab2.style.left = sl2.x + 'px'; simLab2.style.top = sl2.y + 'px'; fadeEl(simLab2, lk);
  title.update(t, 0.4, 8.4);
  t2.update(t, 17.6, 25.6);
  chapter.update(t, 0.3, 25.6);
  ctx.grade.uFade.value = smooth(remap(t, 0, 0.4)) * (1 - easeInCubic(remap(t, 25.4, 26)));
  ctx.bloomCfg.strength = 0.7; ctx.bloomCfg.threshold = 0.85;
  ctx.render(scene, camera);
}
