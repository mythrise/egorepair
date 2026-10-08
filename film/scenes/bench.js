import { THREE, el, splitChars, revealChars, rng } from '@engine/core.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

export const duration = 4;
let scene, camera, pts, meshes = [], spans;

export async function init(ctx) {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x04060a);
  const pm = new THREE.PMREMGenerator(ctx.renderer);
  scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
  camera = new THREE.PerspectiveCamera(35, ctx.W / ctx.H, 0.1, 200);
  const N = 300000, r = rng(3);
  const pos = new Float32Array(N * 3), col = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    const a = r() * Math.PI * 2, rr = Math.sqrt(r()) * 6;
    pos[i * 3] = Math.cos(a) * rr; pos[i * 3 + 1] = (r() - 0.5) * 0.3; pos[i * 3 + 2] = Math.sin(a) * rr;
    col[i * 3] = 0.3 + 0.7 * r(); col[i * 3 + 1] = 0.6; col[i * 3 + 2] = 1.0;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  pts = new THREE.Points(g, new THREE.PointsMaterial({ size: 0.02, vertexColors: true }));
  scene.add(pts);
  const mat = new THREE.MeshPhysicalMaterial({ color: 0xdfe6f2, metalness: 0.2, roughness: 0.25, clearcoat: 1 });
  for (let i = 0; i < 6; i++) {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.3, 1.2, 64), mat);
    m.position.set(-3 + i * 1.2, 0.8, 0); meshes.push(m); scene.add(m);
  }
  const ring = new THREE.Mesh(new THREE.TorusGeometry(2.2, 0.02, 16, 256), new THREE.MeshBasicMaterial({ color: new THREE.Color(3, 2, 5) }));
  ring.position.y = 1.5; scene.add(ring);
  scene.add(new THREE.DirectionalLight(0xffffff, 2));
  const h = el(ctx.ui, 'abs h1 center', '', { left: '0px', width: '3840px', top: '1500px' });
  spans = splitChars(h, 'From demonstration to data');
  el(ctx.ui, 'abs zh center', '从人类演示到机器人数据', { left: '0px', width: '3840px', top: '1700px' });
}

export async function render(t, ctx) {
  camera.position.set(Math.sin(t * 0.3) * 9, 3.5, Math.cos(t * 0.3) * 9);
  camera.lookAt(0, 0.6, 0);
  meshes.forEach((m, i) => (m.rotation.z = Math.sin(t + i) * 0.5));
  revealChars(spans, t / 2);
  ctx.render(scene, camera);
}
