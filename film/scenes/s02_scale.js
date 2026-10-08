// S02 — Scale: pull back from one demonstration into a galaxy of them; then the red verdict.
import { THREE, el, clamp, lerp, remap, smooth, easeOutCubic, easeInOutCubic, easeInCubic, easeOutExpo, rng, loadImage, loadJSON } from '@engine/core.js';
import { makeHaze } from '@engine/fx.js';
import { Title, Stat, fadeEl } from '@engine/ui.js';

export const duration = 16;
let scene, camera, tiles, atlas, A, N = 3000, seeds = [], title, verdict, stats = [], src;

export async function init(ctx) {
  scene = new THREE.Scene();
  scene.add(makeHaze({ top: '#050811', bottom: '#010203', glow: '#0f1630', glowK: 0.45 }));
  camera = new THREE.PerspectiveCamera(32, ctx.W / ctx.H, 0.01, 200);
  A = await loadJSON('/assets/atlas/ego_atlas.json');
  const tex = new THREE.Texture(await loadImage('/assets/atlas/ego_atlas.jpg'));
  tex.colorSpace = THREE.SRGBColorSpace; tex.minFilter = THREE.LinearMipmapLinearFilter; tex.generateMipmaps = true; tex.anisotropy = 8; tex.needsUpdate = true;
  const geo = new THREE.InstancedBufferGeometry().copy(new THREE.PlaneGeometry(0.256, 0.144));
  const cell = new Float32Array(N * 2), state = new Float32Array(N * 2);
  geo.setAttribute('cell', new THREE.InstancedBufferAttribute(cell, 2));
  geo.setAttribute('state', new THREE.InstancedBufferAttribute(state, 2));
  const mat = new THREE.ShaderMaterial({
    uniforms: { tAtlas: { value: tex }, uGrid: { value: new THREE.Vector2(A.cols, A.rows) }, uOpacity: { value: 1 } },
    vertexShader: `attribute vec2 cell; attribute vec2 state; varying vec2 vUv; varying vec2 vS; varying vec2 vL; varying float vFog;
      void main(){ vec2 uv = uv; vL = uv; vUv = (cell + uv) / vec2(${A.cols}.0, ${A.rows}.0); vUv.y = 1.0 - ((cell.y + (1.0-uv.y)) / ${A.rows}.0); vS = state;
        vec4 mv = modelViewMatrix * instanceMatrix * vec4(position,1.0); vFog = exp(-max(-mv.z - 1.5, 0.0) * 0.16);
        gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform sampler2D tAtlas; uniform float uOpacity; varying vec2 vUv; varying vec2 vS; varying vec2 vL; varying float vFog;
      void main(){ vec3 c = texture2D(tAtlas, vUv).rgb * 1.15;
        float l = dot(c, vec3(0.2126,0.7152,0.0722));
        vec3 red = vec3(l*1.2+0.03, l*0.25, l*0.3);
        c = mix(c, red, vS.y);
        vec2 e = min(vL, 1.0-vL); float edge = smoothstep(0.0, 0.02, min(e.x*1.0, e.y*1.6));
        float b = vS.x;
        gl_FragColor = vec4(c * b * edge * uOpacity * vFog, 1.0); }`,
  });
  tiles = new THREE.InstancedMesh(geo, mat, N);
  tiles.frustumCulled = false;
  // layout: tile 0 at the origin facing the camera; the rest on a huge curved wall around it
  const r = rng(12), m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(1, 1, 1);
  for (let i = 0; i < N; i++) {
    let p;
    if (i === 0) p = new THREE.Vector3(0, 0, 0);
    else {
      // galaxy disk: golden-angle spiral, tilted away from the viewer, thicker toward the core
      const ring = Math.sqrt(i) * 0.24 + 0.25;
      const a = i * 2.39996;
      const dx = Math.cos(a) * ring, dz = Math.sin(a) * ring;
      const thick = 0.25 * Math.exp(-ring * 0.35) * (r() - 0.5);
      p = new THREE.Vector3(dx, thick, dz).applyAxisAngle(new THREE.Vector3(1, 0, 0), 1.05).add(new THREE.Vector3(0, -0.2, -1.2));
    }
    const look = new THREE.Vector3(0, 1.2, 8).sub(p).normalize();
    q.setFromUnitVectors(new THREE.Vector3(0, 0, 1), look);
    m.compose(p, q, s); tiles.setMatrixAt(i, m);
    seeds.push({ off: i === 0 ? 8 * 16 + 4 : Math.floor(r() * A.n), sp: 0.4 + r() * 1.2, d: p.length(), red: r(), hit: r() });
  }
  scene.add(tiles);
  src = el(ctx.ui, 'abs mono', 'EgoDex · Apple, 2025 · one public egocentric dexterity dataset', { left: '150px', top: '1960px', fontSize: '24px', color: 'rgba(238,243,255,0.55)' });
  stats.push(new Stat(ctx.ui, { x: 150, y: 1440, value: 829, suffix: ' h', en: 'EGOCENTRIC VIDEO', zh: '小时第一人称视频', size: 190 }));
  stats.push(new Stat(ctx.ui, { x: 1450, y: 1440, value: 194, en: 'TABLETOP TASKS', zh: '种桌面操作任务', size: 190 }));
  stats.push(new Stat(ctx.ui, { x: 2650, y: 1440, value: 90, prefix: '~', suffix: ' M', en: 'FRAMES AT 30 FPS', zh: '帧', size: 190 }));
  title = new Title(ctx.ui, { en: 'Egocentric data is scaling fast.', zh: '第一人称数据正在快速规模化', y: 360, size: 128 });
  verdict = new Title(ctx.ui, { en: 'Almost none of it is robot-ready.', zh: '但几乎没有一帧能直接用于机器人训练', y: 1080, size: 150 });
}

export async function render(t, ctx) {
  // pull back from the single tile (matches the end of s01) to the full field
  const pb = easeInOutCubic(remap(t, 0, 9));
  const dist = lerp(0.3, 7.2, Math.pow(pb, 1.5));
  camera.position.set(Math.sin(t * 0.08) * 0.4 * pb, lerp(0, 1.4, pb), dist);
  camera.lookAt(0, lerp(0, -0.6, pb), lerp(0, -2.2, pb));
  camera.fov = lerp(28, 36, pb); camera.updateProjectionMatrix();
  const st = tiles.geometry.attributes.state, ce = tiles.geometry.attributes.cell;
  const scan = remap(t, 10.0, 12.6); // red sweep across the field (left -> right)
  for (let i = 0; i < N; i++) {
    const S = seeds[i];
    const fi = Math.floor((S.off + t * 30 * S.sp / 4)) % A.n;
    ce.setXY(i, fi % A.cols, Math.floor(fi / A.cols));
    const appear = i === 0 ? 1 : smooth(remap(t, 0.5 + S.d * 0.35, 1.3 + S.d * 0.35));
    const m = tiles.instanceMatrix.array; const x = m[i * 16 + 12];
    const reached = smooth(remap(scan * 14 - 7, x - 0.3, x + 0.3));
    const redK = reached * (S.red < 0.985 ? 1 : 0.0);
    const txt = 1 - 0.45 * Math.max(smooth(remap(t, 4.4, 5.2)) * (1 - smooth(remap(t, 9.4, 10.2))), smooth(remap(t, 11.0, 11.8)));
    st.setXY(i, appear * (1 - 0.4 * redK) * (i === 0 ? 1 : 0.8) * (i === 0 ? 1 : txt), redK);
  }
  st.needsUpdate = true; ce.needsUpdate = true;
  tiles.material.uniforms.uOpacity.value = 1 - smooth(remap(t, 15.2, 16));
  title.update(t, 2.2, 9.6);
  stats.forEach((S, i) => S.update(t, 4.6 + i * 0.5, 9.6));
  fadeEl(src, smooth(remap(t, 4.6, 5.4)) * (1 - smooth(remap(t, 9.2, 9.8))));
  verdict.update(t, 11.2, 15.8);
  ctx.grade.uFade.value = 1 - smooth(remap(t, 15.3, 16));
  ctx.grade.uTint.value.set(1, 1, 1);
  ctx.bloomCfg.strength = 0.5; ctx.bloomCfg.threshold = 0.9;
  ctx.render(scene, camera);
}
