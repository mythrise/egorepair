import { THREE } from '@engine/core.js';
export const duration = 4;
let scene, camera;
export async function init(ctx) {
  scene = new THREE.Scene(); scene.background = new THREE.Color(0x04060a);
  camera = new THREE.PerspectiveCamera(35, ctx.W / ctx.H, 0.1, 200);
  const q = ctx.q;
  if (q.get('pts')) {
    const N = +q.get('pts'); const pos = new Float32Array(N*3);
    for (let i=0;i<N*3;i++) pos[i]=(Math.random()-0.5)*8;
    const g=new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos,3));
    scene.add(new THREE.Points(g, new THREE.PointsMaterial({size:0.02,color:0x88aaff})));
  }
}
export async function render(t, ctx) { camera.position.set(0,0,10); camera.lookAt(0,0,0); ctx.render(scene, camera); }
