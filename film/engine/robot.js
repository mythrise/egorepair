// Procedural 6-DoF arm with parallel gripper and analytic IK (units: metres, y up).
import { THREE, clamp } from './core.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

export function robotMaterials({ body = '#e9edf3', joint = '#1a2030', accent = '#74d7ff', accentI = 3 } = {}) {
  return {
    body: new THREE.MeshPhysicalMaterial({ color: body, roughness: 0.32, metalness: 0.05, clearcoat: 0.7, clearcoatRoughness: 0.25 }),
    joint: new THREE.MeshPhysicalMaterial({ color: joint, roughness: 0.28, metalness: 0.7, clearcoat: 0.4 }),
    accent: new THREE.MeshBasicMaterial({ color: new THREE.Color(accent).multiplyScalar(accentI), toneMapped: false }),
    finger: new THREE.MeshPhysicalMaterial({ color: '#2a3244', roughness: 0.4, metalness: 0.5 }),
  };
}

function capsuleZ(r, len, mat, seg = 40) {
  // capsule along +z from 0..len
  const g = new THREE.CapsuleGeometry(r, Math.max(len - 2 * r, 0.001), 12, seg);
  g.rotateX(Math.PI / 2); g.translate(0, 0, len / 2);
  return new THREE.Mesh(g, mat);
}
function cylX(r, w, mat, seg = 48) {
  const g = new THREE.CylinderGeometry(r, r, w, seg); g.rotateZ(Math.PI / 2);
  return new THREE.Mesh(g, mat);
}
function ringX(r, w, mat) { const g = new THREE.TorusGeometry(r, w, 8, 64); g.rotateY(Math.PI / 2); return new THREE.Mesh(g, mat); }

export class RobotArm {
  constructor({ scale = 1, mats = robotMaterials(), H0 = 0.17, L1 = 0.34, L2 = 0.3, Lw = 0.075, Lt = 0.12 } = {}) {
    this.H0 = H0 * scale; this.L1 = L1 * scale; this.L2 = L2 * scale; this.Lw = Lw * scale; this.Lt = Lt * scale; this.s = scale;
    const s = scale, M = mats; this.mats = M;
    this.root = new THREE.Group();
    // base
    const base0 = new THREE.Mesh(new THREE.CylinderGeometry(0.1 * s, 0.11 * s, 0.025 * s, 64), M.joint); base0.position.y = 0.0125 * s;
    const base1 = new THREE.Mesh(new THREE.CylinderGeometry(0.075 * s, 0.085 * s, 0.11 * s, 64), M.body); base1.position.y = 0.08 * s;
    const bring = new THREE.Mesh(new THREE.TorusGeometry(0.078 * s, 0.0035 * s, 8, 64), M.accent); bring.rotation.x = Math.PI / 2; bring.position.y = 0.137 * s;
    this.root.add(base0, base1, bring);
    // yaw
    this.yaw = new THREE.Group(); this.root.add(this.yaw);
    const turret = new THREE.Mesh(new THREE.CylinderGeometry(0.065 * s, 0.072 * s, 0.05 * s, 64), M.joint); turret.position.y = 0.14 * s; this.yaw.add(turret);
    // shoulder
    this.sh = new THREE.Group(); this.sh.position.y = this.H0; this.yaw.add(this.sh);
    const shc = cylX(0.062 * s, 0.13 * s, M.body); this.sh.add(shc);
    const shr = ringX(0.063 * s, 0.003 * s, M.accent); shr.position.x = 0.066 * s; this.sh.add(shr);
    const shr2 = ringX(0.063 * s, 0.003 * s, M.accent); shr2.position.x = -0.066 * s; this.sh.add(shr2);
    const up = new THREE.Mesh(new RoundedBoxGeometry(0.085 * s, 0.075 * s, this.L1 + 0.04 * s, 4, 0.03 * s), M.body);
    up.position.z = this.L1 / 2; this.sh.add(up);
    // elbow
    this.el = new THREE.Group(); this.el.position.z = this.L1; this.sh.add(this.el);
    const elc = cylX(0.05 * s, 0.11 * s, M.joint); this.el.add(elc);
    const elr = ringX(0.051 * s, 0.0028 * s, M.accent); elr.position.x = 0.056 * s; this.el.add(elr);
    const fo = capsuleZ(0.036 * s, this.L2, M.body); this.el.add(fo);
    // wrist pitch
    this.wr = new THREE.Group(); this.wr.position.z = this.L2; this.el.add(this.wr);
    const wrc = cylX(0.036 * s, 0.085 * s, M.joint); this.wr.add(wrc);
    const wrr = ringX(0.037 * s, 0.0024 * s, M.accent); wrr.position.x = 0.044 * s; this.wr.add(wrr);
    // wrist roll
    this.roll = new THREE.Group(); this.wr.add(this.roll);
    const wl = capsuleZ(0.03 * s, this.Lw, M.body); this.roll.add(wl);
    // gripper
    this.grip = new THREE.Group(); this.grip.position.z = this.Lw; this.roll.add(this.grip);
    const palm = new THREE.Mesh(new RoundedBoxGeometry(0.09 * s, 0.035 * s, 0.035 * s, 3, 0.008 * s), M.joint); palm.position.z = 0.018 * s; this.grip.add(palm);
    const ga = new THREE.Mesh(new THREE.TorusGeometry(0.03 * s, 0.0025 * s, 8, 48), M.accent); ga.position.z = 0.002 * s; this.grip.add(ga);
    this.fL = new THREE.Mesh(new RoundedBoxGeometry(0.012 * s, 0.03 * s, 0.07 * s, 2, 0.004 * s), M.finger);
    this.fR = this.fL.clone();
    this.fL.position.z = this.fR.position.z = 0.035 * s + 0.035 * s;
    this.grip.add(this.fL, this.fR);
    this.tcp = new THREE.Object3D(); this.tcp.position.z = this.Lt; this.grip.add(this.tcp);
    this.setGripper(0.6);
    this.q = [0, 0.6, -1.2, 0.3, 0];
    this.apply();
  }
  setGripper(open) { const w = (0.008 + 0.03 * clamp(open)) * this.s; this.fL.position.x = w; this.fR.position.x = -w; }
  apply() {
    const [q1, q2, q3, q4, q5] = this.q;
    this.yaw.rotation.y = q1; this.sh.rotation.x = -q2; this.el.rotation.x = -q3; this.wr.rotation.x = -q4; this.roll.rotation.z = q5;
  }
  // IK: target position p (root-local), approach dir a (unit), roll angle. Returns reach error (m).
  solve(p, a = new THREE.Vector3(0, -1, 0), roll = 0, elbowUp = true) {
    const Lt = this.Lw + this.Lt;
    const w = p.clone().sub(a.clone().multiplyScalar(Lt));
    const q1 = Math.atan2(w.x, w.z);
    const r = Math.hypot(w.x, w.z), h = w.y - this.H0;
    const L1 = this.L1, L2 = this.L2;
    let D = (r * r + h * h - L1 * L1 - L2 * L2) / (2 * L1 * L2);
    const err = Math.max(0, Math.abs(D) - 1) * L1;
    D = clamp(D, -1, 1);
    const q3 = elbowUp ? -Math.acos(D) : Math.acos(D);
    const q2 = Math.atan2(h, r) - Math.atan2(L2 * Math.sin(q3), L1 + L2 * Math.cos(q3));
    const ar = a.x * Math.sin(q1) + a.z * Math.cos(q1);
    const phi = Math.atan2(a.y, ar);
    const q4 = phi - (q2 + q3);
    this.q = [q1, q2, q3, q4, roll];
    this.apply();
    return err;
  }
  tcpWorld(v = new THREE.Vector3()) { this.root.updateMatrixWorld(true); return this.tcp.getWorldPosition(v); }
}
