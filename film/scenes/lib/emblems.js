// Agent emblems: distinct luminous instruments (not circles-with-labels).
import { THREE, clamp, smooth } from '@engine/core.js';
import { Ribbon, makePoints, makeHalo, circlePoints } from '@engine/fx.js';
import { RobotArm, robotMaterials } from '@engine/robot.js';

const V = (x, y, z) => new THREE.Vector3(x, y, z);
function ringPts(r, n = 96, a0 = 0, a1 = Math.PI * 2) { const p = []; for (let i = 0; i <= n; i++) { const a = a0 + (a1 - a0) * i / n; p.push(V(Math.cos(a) * r, Math.sin(a) * r, 0)); } return p; }

class Emblem {
  constructor(color) { this.g = new THREE.Group(); this.color = new THREE.Color(color); this.rbs = []; this.k = 0; }
  rb(pts, o = {}) { const r = new Ribbon(pts, { color: this.color, intensity: 2.2, width: 4, ...o }); this.g.add(r.mesh); this.rbs.push(r); return r; }
  base() {
    const r = this.rb(circlePoints(0.2, 96, -0.2), { width: 2.5, intensity: 1.2 });
    const r2 = this.rb(circlePoints(0.26, 96, -0.2), { width: 1.5, intensity: 0.5 });
    this.halo = makeHalo({ size: 0.9, color: '#' + this.color.getHexString(), intensity: 0.25 });
    this.g.add(this.halo);
  }
  fade(k, act = 0) {
    this.k = k;
    for (const r of this.rbs) r.set({ opacity: k * (r.op ?? 1) * (0.55 + 0.45 * act) });
    if (this.halo) { this.halo.userData.mat.uniforms.uI.value = 0.22 * k * (0.35 + act); }
    this.g.visible = k > 0.001;
  }
  face(cam) { if (this.halo) this.halo.quaternion.copy(cam.quaternion); }
}

export class Orrery extends Emblem {
  constructor(color) {
    super(color); this.base();
    this.rings = [0.17, 0.135, 0.1].map((r, i) => { const grp = new THREE.Group(); const rr = this.rb(ringPts(r), { width: 3.5 - i * 0.6 }); this.g.remove(rr.mesh); grp.add(rr.mesh); this.g.add(grp); return grp; });
    const core = new THREE.Mesh(new THREE.SphereGeometry(0.03, 32, 16), new THREE.MeshBasicMaterial({ color: this.color.clone().multiplyScalar(4) }));
    this.core = core; this.g.add(core);
    this.nodes = makePoints(6, { soft: 0.3 }); this.g.add(this.nodes);
  }
  update(t, act) {
    this.rings[0].rotation.set(t * 0.6, 0.4, 0); this.rings[1].rotation.set(1.1, t * 0.9, 0.3); this.rings[2].rotation.set(0.3, 1.2, t * 1.3);
    this.core.scale.setScalar(this.k * (1 + 0.15 * Math.sin(t * 5) * act));
    const g = this.nodes.geometry;
    for (let i = 0; i < 6; i++) { const a = t * (0.8 + i * 0.13) + i; const r = 0.17 - (i % 3) * 0.035; g.attributes.position.setXYZ(i, Math.cos(a) * r, Math.sin(a * 1.3) * r * 0.6, Math.sin(a) * r); g.attributes.color.setXYZ(i, 3, 3, 3.5); g.attributes.size.setX(i, 0.02); g.attributes.alpha.setX(i, this.k); }
    g.attributes.position.needsUpdate = true; g.attributes.alpha.needsUpdate = true; g.attributes.color.needsUpdate = true;
  }
}

export class Iris extends Emblem {
  constructor(color) {
    super(color); this.base();
    this.arcs = [];
    for (let i = 0; i < 5; i++) {
      const r = 0.05 + i * 0.03, grp = new THREE.Group();
      for (let s = 0; s < 3; s++) { const a0 = s * 2.094 + i * 0.4; const rr = this.rb(ringPts(r, 32, a0, a0 + 1.3 - i * 0.12), { width: 4 - i * 0.4 }); this.g.remove(rr.mesh); grp.add(rr.mesh); }
      this.g.add(grp); this.arcs.push(grp);
    }
    this.scan = this.rb([V(-0.24, 0, 0.001), V(0.24, 0, 0.001)], { width: 2.5, intensity: 3 });
    this.scan.mesh.position.z = 0;
  }
  update(t, act) {
    this.arcs.forEach((a, i) => (a.rotation.z = t * (i % 2 ? -0.5 : 0.7) * (1 + i * 0.2)));
    this.scan.mesh.position.y = Math.sin(t * 2.2) * 0.17;
  }
}

export class Lattice extends Emblem {
  constructor(color) {
    super(color); this.base();
    const s = 0.11, c = [];
    for (const x of [-s, s]) for (const y of [-s, s]) for (const z of [-s, s]) c.push(V(x, y, z));
    const E = [[0, 1], [2, 3], [4, 5], [6, 7], [0, 2], [1, 3], [4, 6], [5, 7], [0, 4], [1, 5], [2, 6], [3, 7]];
    this.cube = new THREE.Group(); this.g.add(this.cube);
    for (const [a, b] of E) { const r = this.rb([c[a], c[b]], { width: 3 }); this.g.remove(r.mesh); this.cube.add(r.mesh); }
    const T = [V(0, 0.08, 0), V(-0.07, -0.05, 0.04), V(0.07, -0.05, 0.04), V(0, -0.05, -0.08)];
    this.tet = new THREE.Group(); this.g.add(this.tet);
    for (const [a, b] of [[0, 1], [0, 2], [0, 3], [1, 2], [2, 3], [3, 1]]) { const r = this.rb([T[a], T[b]], { width: 2.5, intensity: 3 }); this.g.remove(r.mesh); this.tet.add(r.mesh); }
  }
  update(t) { this.cube.rotation.set(t * 0.25, t * 0.4, 0); this.tet.rotation.set(-t * 0.5, t * 0.7, t * 0.2); }
}

export class Helix extends Emblem {
  constructor(color) {
    super(color); this.base();
    this.n = 44; this.pts = makePoints(this.n * 2, { soft: 0.2 }); this.g.add(this.pts);
    this.rungs = [];
    for (let i = 0; i < this.n; i += 4) { const r = this.rb([V(0, 0, 0), V(0.01, 0, 0)], { width: 2, intensity: 1.2 }); r.i = i; this.rungs.push(r); }
  }
  update(t) {
    const g = this.pts.geometry;
    for (let i = 0; i < this.n; i++) {
      const y = -0.17 + 0.34 * i / (this.n - 1), a = i * 0.32 + t * 1.2;
      for (let s = 0; s < 2; s++) {
        const aa = a + s * Math.PI, j = i * 2 + s;
        g.attributes.position.setXYZ(j, Math.cos(aa) * 0.08, y, Math.sin(aa) * 0.08);
        g.attributes.color.setXYZ(j, this.color.r * 2.5, this.color.g * 2.5, this.color.b * 2.5);
        g.attributes.size.setX(j, 0.016); g.attributes.alpha.setX(j, this.k);
      }
    }
    for (const r of this.rungs) { const i = r.i, y = -0.17 + 0.34 * i / (this.n - 1), a = i * 0.32 + t * 1.2; r.setPoints([V(Math.cos(a) * 0.08, y, Math.sin(a) * 0.08), V(Math.cos(a + Math.PI) * 0.08, y, Math.sin(a + Math.PI) * 0.08)]); }
    for (const k of ['position', 'color', 'size', 'alpha']) g.attributes[k].needsUpdate = true;
  }
}

export class MiniArm extends Emblem {
  constructor(color) {
    super(color); this.base();
    this.arm = new RobotArm({ scale: 0.42, mats: robotMaterials({ accent: '#' + this.color.getHexString(), accentI: 4 }) });
    this.arm.root.position.y = -0.2; this.g.add(this.arm.root);
  }
  update(t) {
    const a = this.arm; a.q = [Math.sin(t * 0.8) * 0.9, 0.7 + 0.25 * Math.sin(t * 1.1), -1.3 + 0.3 * Math.sin(t * 1.3 + 1), 0.5 + 0.3 * Math.sin(t), t * 0.5]; a.apply(); a.setGripper(0.5 + 0.5 * Math.sin(t * 2));
  }
  fade(k, act) { super.fade(k, act); this.arm.root.visible = k > 0.05; }
}

export class Bars extends Emblem {
  constructor(color) {
    super(color); this.base();
    this.cols = ['#5ef2a8', '#9aa6bd', '#ff4d5e', '#ffb547'];
    this.bars = this.cols.map((c, i) => this.rb([V(-0.09 + i * 0.06, -0.15, 0), V(-0.09 + i * 0.06, 0.1, 0)], { color: c, width: 10, intensity: 2, additive: true }));
  }
  update(t) { this.bars.forEach((b, i) => b.set({ head: 0.45 + 0.4 * (0.5 + 0.5 * Math.sin(t * (0.9 + i * 0.37) + i * 1.7)) })); }
}

export class Seal extends Emblem {
  constructor(color) {
    super(color); this.base();
    const hex = []; for (let i = 0; i <= 6; i++) { const a = i / 6 * Math.PI * 2 + Math.PI / 6; hex.push(V(Math.cos(a) * 0.17, Math.sin(a) * 0.17, 0)); }
    this.hex = this.rb(hex, { width: 4 });
    this.notch = new THREE.Group(); this.g.add(this.notch);
    for (let i = 0; i < 12; i++) { const a0 = i / 12 * Math.PI * 2; const r = this.rb(ringPts(0.12, 8, a0, a0 + 0.3), { width: 3.5 }); this.g.remove(r.mesh); this.notch.add(r.mesh); }
    this.check = this.rb([V(-0.05, 0.0, 0), V(-0.012, -0.04, 0), V(0.06, 0.05, 0)], { width: 6, intensity: 3, color: '#5ef2a8' });
    this.check.op = 0;
  }
  update(t, act, sealed = 0) { this.notch.rotation.z = -t * 0.4 * (1 - sealed); this.check.op = sealed; }
}
