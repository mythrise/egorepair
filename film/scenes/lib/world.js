// Shared "episode world": reconstructed scene cloud, table frame, hand/EEF trajectory, robot.
import { THREE, loadF32, loadJSON, clamp, lerp, smooth, remap } from '@engine/core.js';
import { makePoints, Ribbon, makeTriad, makeGrid, COL } from '@engine/fx.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

export const OFFSET = new THREE.Vector3(0.12, 0, -0.86); // recenters the table at the origin

export async function loadCloud(dir = '/assets/scene/ego0', { darken = 0.85, sat = 0.85, size = 0.0042, wallKeep = 0.3, wallTint = [0.55, 0.7, 1.0] } = {}) {
  const meta = await loadJSON(dir + '/meta.json');
  const a = await loadF32(dir + '/cloud.f32');
  const n = a.length / 6;
  const pts = makePoints(n, { additive: false, soft: 0.25 });
  const g = pts.geometry;
  const P = g.attributes.position.array, Cc = g.attributes.color.array, Sz = g.attributes.size.array, Al = g.attributes.alpha.array;
  const base = new Float32Array(n * 3);
  const wall = new Uint8Array(n);
  const baseAlpha = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const x = a[i * 6] + OFFSET.x, y = a[i * 6 + 1] + OFFSET.y, z = a[i * 6 + 2] + OFFSET.z;
    P[i * 3] = x; P[i * 3 + 1] = y; P[i * 3 + 2] = z;
    base[i * 3] = x; base[i * 3 + 1] = y; base[i * 3 + 2] = z;
    let r = a[i * 6 + 3], gg = a[i * 6 + 4], b = a[i * 6 + 5];
    const l = 0.2126 * r + 0.7152 * gg + 0.0722 * b;
    const isWall = y > 0.004; wall[i] = isWall ? 1 : 0;
    const h = ((i * 2654435761) >>> 0) / 4294967296;
    if (isWall) { r = l * wallTint[0]; gg = l * wallTint[1]; b = l * wallTint[2]; }
    else { r = lerp(l, r, sat); gg = lerp(l, gg, sat); b = lerp(l, b, sat); }
    Cc[i * 3] = Math.pow(r, 2.2) * darken; Cc[i * 3 + 1] = Math.pow(gg, 2.2) * darken; Cc[i * 3 + 2] = Math.pow(b, 2.2) * darken;
    Sz[i] = size * (0.8 + 0.4 * h) * (isWall ? 0.8 : 1);
    // soft falloff toward the borders of the observed table, sparse translucent walls
    const ex = Math.min(x + 0.58, 0.47 - x), ez = Math.min(z + 0.42, 0.37 - z);
    const edge = smooth(Math.min(ex, ez) / 0.12);
    const wa = isWall ? (h < wallKeep ? 0.55 * (1 - smooth((y - 0.18) / 0.32)) : 0) : 1;
    baseAlpha[i] = isWall ? wa : (0.25 + 0.75 * edge);
    Al[i] = baseAlpha[i];
  }
  g.attributes.position.needsUpdate = true; g.attributes.color.needsUpdate = true; g.attributes.alpha.needsUpdate = true;
  pts.userData.base = base; pts.userData.meta = meta; pts.userData.baseColor = Cc.slice(); pts.userData.wall = wall; pts.userData.baseAlpha = baseAlpha;
  return pts;
}

// project an image pixel (in the 640x360 annotation frame) onto the table plane (world, recentered)
export function pixelToTable(meta, u, v, y = 0) {
  const { pos, pitch, f, w, h } = meta.cam;
  const s = w / 640;
  const x = (u * s - w / 2) / f, yy = (v * s - h / 2) / f;
  const fw = new THREE.Vector3(0, -Math.sin(pitch), Math.cos(pitch));
  const up = new THREE.Vector3(0, Math.cos(pitch), Math.sin(pitch));
  const d = new THREE.Vector3(1, 0, 0).multiplyScalar(x).addScaledVector(up, -yy).add(fw).normalize();
  const o = new THREE.Vector3(...pos);
  const t = (y - o.y) / d.y;
  return o.addScaledVector(d, t).add(OFFSET);
}

// Synthetic stand-in left-hand EEF trajectory (to be replaced by EgoDex HDF5 poses).
export function makeHandPath(meta) {
  const P = (u, v, y) => pixelToTable(meta, u, v, 0).setY(y);
  const keys = [
    P(285, 290, 0.04), P(270, 262, 0.10), P(232, 236, 0.15), P(212, 218, 0.07), P(208, 214, 0.035),
    P(212, 214, 0.04), P(240, 222, 0.16), P(330, 232, 0.24), P(440, 250, 0.22), P(500, 262, 0.16), P(520, 268, 0.12),
    P(505, 262, 0.17), P(420, 262, 0.15), P(330, 285, 0.07),
  ];
  const curve = new THREE.CatmullRomCurve3(keys, false, 'centripetal');
  return curve;
}

export function envLights(scene, renderer, { envI = 0.6 } = {}) {
  const pm = new THREE.PMREMGenerator(renderer);
  const env = pm.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environment = env;
  scene.environmentIntensity = envI;
  const key = new THREE.DirectionalLight('#ffffff', 1.5); key.position.set(2, 4, 3); scene.add(key);
  const rim = new THREE.DirectionalLight('#9fb8ff', 2.0); rim.position.set(-3, 2, -4); scene.add(rim);
  const fill = new THREE.HemisphereLight('#a8c0ff', '#0a0c12', 0.4); scene.add(fill);
  return { key, rim, fill };
}

// orientation frames along a curve (approach mostly downward, rotating with travel)
export function poseAt(curve, u, tw = 0) {
  const p = curve.getPointAt(clamp(u));
  const tan = curve.getTangentAt(clamp(u));
  const z = new THREE.Vector3(0, -1, 0).addScaledVector(tan, 0.35).normalize();
  const x = new THREE.Vector3().crossVectors(tan, z).normalize();
  if (x.lengthSq() < 1e-6) x.set(1, 0, 0);
  const y = new THREE.Vector3().crossVectors(z, x).normalize();
  const m = new THREE.Matrix4().makeBasis(x, y, z);
  const q = new THREE.Quaternion().setFromRotationMatrix(m);
  if (tw) q.multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), tw));
  return { p, q };
}
