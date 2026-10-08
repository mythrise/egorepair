// S12 — EgoRepair Studio: the real product UI on floating glass panels.
import { THREE, el, clamp, lerp, remap, smooth, easeOutCubic, easeInOutCubic, easeInCubic, loadImage } from '@engine/core.js';
import { makePanel, makeHaze, makeHalo } from '@engine/fx.js';
import { Title, fadeEl } from '@engine/ui.js';

export const duration = 12;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const SHOTS = ['studio_M2_多智能体协作.jpg', 'studio_M7_机器人轨迹.jpg', 'studio_M6_物理回放.jpg'];
let scene, camera, panels = [], refl = [], title, chips;

export async function init(ctx) {
  scene = new THREE.Scene();
  scene.add(makeHaze({ top: '#070b16', bottom: '#010203', glow: '#141a3a', glowDir: V(0, 0.3, -1), glowK: 0.35 }));
  camera = new THREE.PerspectiveCamera(30, ctx.W / ctx.H, 0.05, 100);
  const W = 1.51, H = 1.0;
  for (let i = 0; i < SHOTS.length; i++) {
    const tx = new THREE.Texture(await loadImage(`/assets/stills/${encodeURIComponent(SHOTS[i])}`)); tx.colorSpace = THREE.SRGBColorSpace; tx.anisotropy = 8; tx.needsUpdate = true;
    const p = makePanel(W, H, { radius: 0.022, border: 0.003, borderColor: '#cfe0ff', borderI: 0.5 });
    p.userData.setMap(tx); scene.add(p); panels.push(p);
    const r = makePanel(W, H, { radius: 0.022 }); r.userData.setMap(tx); r.scale.y = -1; scene.add(r); refl.push(r);
  }
  const glow = makeHalo({ size: 6, color: '#3d5bff', intensity: 0.12 }); glow.position.set(0, 0.2, -1.2); scene.add(glow);
  title = new Title(ctx.ui, { en: 'EgoRepair Studio', zh: '用八个协作模块，把第一人称演示转化为可回放的机器人训练数据', y: 300, size: 150, kicker: 'THE PRODUCT' });
  chips = el(ctx.ui, 'abs center', ['M0 证据捆绑', 'M1 空间理解', 'M2 冲突裁决', 'M3 接触先验', 'M4 扩散修复', 'M5 可行性投影', 'M6 物理回放', 'M7 质量评估'].map((c) => `<span class="tag" style="margin:0 10px;font-family:'Noto Sans SC';letter-spacing:0.08em">${c}</span>`).join(''), { left: '0px', width: '3840px', top: '1930px' });
}

export async function render(t, ctx) {
  const k = easeInOutCubic(remap(t, 0, 12));
  camera.position.set(lerp(-0.9, 0.9, k), lerp(0.35, 0.25, k), lerp(5.6, 5.1, k));
  camera.lookAt(0, -0.02, 0);
  const lay = [[-1.62, 0.0, -0.25, 0.42], [0, 0.05, 0.1, 0], [1.62, 0.0, -0.25, -0.42]];
  panels.forEach((p, i) => {
    const [x, y, z, ry] = lay[i];
    const a = easeOutCubic(remap(t, 0.3 + i * 0.25, 1.6 + i * 0.25));
    p.position.set(x, y + (1 - a) * -0.3 + Math.sin(t * 0.6 + i) * 0.01, z); p.rotation.y = ry;
    p.userData.mat.uniforms.uOpacity.value = a * (1 - smooth(remap(t, 11.2, 12)));
    p.userData.mat.uniforms.uBright.value = 0.92;
    const r = refl[i];
    r.position.set(x, -1.06 - (y + (1 - a) * -0.3), z); r.rotation.y = ry;
    r.userData.mat.uniforms.uOpacity.value = 0.06 * a * (1 - smooth(remap(t, 11.2, 12)));
  });
  title.update(t, 0.6, 11.6);
  fadeEl(chips, smooth(remap(t, 2.0, 3.0)) * (1 - smooth(remap(t, 11.0, 11.8))), { blur: 10, dy: 16 });
  ctx.grade.uFade.value = smooth(remap(t, 0, 0.5)) * (1 - easeInCubic(remap(t, 11.5, 12)));
  ctx.bloomCfg.strength = 0.5; ctx.bloomCfg.threshold = 0.95;
  ctx.render(scene, camera);
}
