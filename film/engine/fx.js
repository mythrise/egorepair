// Reusable visual primitives: iridescent ring, soft points, AA glow ribbons, triads, grid, video panels.
import { THREE, DW, DH, clamp } from './core.js';

export const GLSL_SPECTRAL = `
vec3 srgb2lin(vec3 c){ return pow(c, vec3(2.2)); }
vec3 spectral(float h){
  h = fract(h) * 6.0;
  vec3 c0=vec3(1.00,0.70,0.48), c1=vec3(1.00,0.49,0.71), c2=vec3(0.66,0.55,1.00),
       c3=vec3(0.42,0.72,1.00), c4=vec3(0.40,0.89,0.79), c5=vec3(0.72,0.94,0.54);
  vec3 c = h<1.0 ? mix(c0,c1,h) : h<2.0 ? mix(c1,c2,h-1.0) : h<3.0 ? mix(c2,c3,h-2.0)
         : h<4.0 ? mix(c3,c4,h-3.0) : h<5.0 ? mix(c4,c5,h-4.0) : mix(c5,c0,h-5.0);
  return srgb2lin(c);
}`;
const SPEC_STOPS = ['#ffb27a', '#ff7eb6', '#a98bff', '#6cb8ff', '#67e3c9', '#b8f08a'];
export function spectralColor(h) {
  h = ((h % 1) + 1) % 1 * 6; const i = Math.floor(h), f = h - i;
  const a = new THREE.Color(SPEC_STOPS[i % 6]), b = new THREE.Color(SPEC_STOPS[(i + 1) % 6]);
  return a.lerp(b, f); // THREE.Color from hex is converted to linear working space
}
export const COL = {
  ink: new THREE.Color('#eef3ff'), cyan: new THREE.Color('#74d7ff'), violet: new THREE.Color('#9d8cff'),
  red: new THREE.Color('#ff4d5e'), amber: new THREE.Color('#ffb547'), green: new THREE.Color('#5ef2a8'),
  blue: new THREE.Color('#4f8cff'), dim: new THREE.Color('#5a6a88'),
};
export const hdr = (c, k) => new THREE.Color(c).multiplyScalar(k);

// ---------------------------------------------------------------- ring
export function makeRing({ radius = 2, tube = 0.012, intensity = 4, tubular = 720 } = {}) {
  const geo = new THREE.TorusGeometry(radius, tube, 12, tubular);
  const mat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uIntensity: { value: intensity }, uOpacity: { value: 1 }, uArc: { value: 1 }, uArcStart: { value: 0 }, uHueShift: { value: 0 } },
    vertexShader: `varying vec2 vUv; varying vec3 vN; varying vec3 vV;
      void main(){ vUv=uv; vec4 mv=modelViewMatrix*vec4(position,1.0); vN=normalize(normalMatrix*normal); vV=normalize(-mv.xyz); gl_Position=projectionMatrix*mv; }`,
    fragmentShader: GLSL_SPECTRAL + `uniform float uTime,uIntensity,uOpacity,uArc,uArcStart,uHueShift; varying vec2 vUv; varying vec3 vN; varying vec3 vV;
      void main(){
        float a = fract(vUv.x - uArcStart);
        if (a > uArc) discard;
        float edge = smoothstep(0.0, 0.015, a) * smoothstep(uArc, uArc-0.015, a);
        float f = pow(abs(dot(vN, vV)), 0.6);
        float sh = 0.75 + 0.25*sin(vUv.x*6.2831*7.0 + uTime*1.7) * sin(vUv.x*6.2831*3.0 - uTime*0.9);
        vec3 c = spectral(vUv.x + uHueShift + uTime*0.02) * uIntensity * sh * (0.35 + 0.65*f);
        gl_FragColor = vec4(c * edge * uOpacity, 1.0);
      }`,
    blending: THREE.AdditiveBlending, depthWrite: false, transparent: true,
  });
  const m = new THREE.Mesh(geo, mat);
  m.userData.mat = mat;
  return m;
}

// Halo: camera-facing soft radial glow disc (additive).
export function makeHalo({ size = 4, color = '#9d8cff', intensity = 0.6, ringR = 0.0, ringW = 0.0 } = {}) {
  const mat = new THREE.ShaderMaterial({
    uniforms: { uColor: { value: new THREE.Color(color) }, uI: { value: intensity }, uRingR: { value: ringR }, uRingW: { value: ringW }, uSpectral: { value: 0 }, uTime: { value: 0 }, uCenterW: { value: 0.25 } },
    vertexShader: `varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }`,
    fragmentShader: GLSL_SPECTRAL + `uniform vec3 uColor; uniform float uI,uRingR,uRingW,uSpectral,uTime,uCenterW; varying vec2 vUv;
      void main(){ vec2 p=vUv*2.0-1.0; float r=length(p);
        float g = exp(-r*r*5.0);
        if (uRingW>0.0) g = exp(-pow((r-uRingR)/uRingW,2.0)) + uCenterW*exp(-r*r*3.0);
        vec3 col = mix(uColor, spectral(atan(p.y,p.x)/6.2831+uTime*0.02), uSpectral);
        gl_FragColor=vec4(col*g*uI*smoothstep(1.0,0.85,r),1.0); }`,
    blending: THREE.AdditiveBlending, depthWrite: false, transparent: true,
  });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(size, size), mat);
  m.userData.mat = mat;
  return m;
}

// ---------------------------------------------------------------- soft points
// attrs: position(3), color(3), size(1), alpha(1). Size in world units.
export function makePoints(N, { additive = true, sizeScale = 1, soft = 1.0, depthTest = true } = {}) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
  g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(N * 3).fill(1), 3));
  g.setAttribute('size', new THREE.BufferAttribute(new Float32Array(N).fill(0.02), 1));
  g.setAttribute('alpha', new THREE.BufferAttribute(new Float32Array(N).fill(1), 1));
  const mat = new THREE.ShaderMaterial({
    uniforms: { uScale: { value: 1000 }, uSize: { value: sizeScale }, uOpacity: { value: 1 }, uSoft: { value: soft }, uMinPx: { value: 1.2 } },
    vertexShader: `attribute vec3 color; attribute float size; attribute float alpha;
      uniform float uScale,uSize,uMinPx; varying vec3 vC; varying float vA; varying float vPs;
      void main(){ vec4 mv=modelViewMatrix*vec4(position,1.0); gl_Position=projectionMatrix*mv;
        float ps = size*uSize*uScale/max(-mv.z,1e-3);
        vA = alpha * clamp(ps/uMinPx, 0.0, 1.0); ps = max(ps, uMinPx);
        gl_PointSize = ps; vPs = ps; vC = color; }`,
    fragmentShader: `uniform float uOpacity,uSoft; varying vec3 vC; varying float vA; varying float vPs;
      void main(){ vec2 c=gl_PointCoord-0.5; float r=length(c)*2.0;
        float hard = clamp((1.0-r)*vPs*0.5, 0.0, 1.0);
        float soft = pow(clamp(1.0-r,0.0,1.0), 1.6);
        float a = mix(hard, soft, uSoft) * vA * uOpacity;
        if (a < 0.003) discard;
        gl_FragColor = vec4(vC*a, a); }`,
    blending: THREE.CustomBlending,
    blendSrc: THREE.OneFactor, blendDst: additive ? THREE.OneFactor : THREE.OneMinusSrcAlphaFactor,
    depthWrite: false, depthTest, transparent: true,
  });
  const p = new THREE.Points(g, mat);
  p.frustumCulled = false;
  p.userData.mat = mat;
  p.onBeforeRender = (r, s, cam) => {
    const H = r.getRenderTarget() ? r.getRenderTarget().height : r.domElement.height;
    mat.uniforms.uScale.value = H / (2 * Math.tan(THREE.MathUtils.degToRad(cam.fov || 35) / 2));
  };
  return p;
}

// ---------------------------------------------------------------- ribbons (AA screen-space lines)
const RIBBON_VS = `
attribute vec3 prev; attribute vec3 next; attribute float side; attribute float u; attribute vec4 rgba; attribute float wmul;
uniform vec2 uRes; uniform float uWidth;
varying float vU; varying float vD; varying float vHalf; varying vec4 vC;
vec2 toPx(vec4 v){ return (v.xy/v.w)*0.5*uRes; }
void main(){
  mat4 mvp = projectionMatrix*modelViewMatrix;
  vec4 c = mvp*vec4(position,1.0); vec4 p = mvp*vec4(prev,1.0); vec4 n = mvp*vec4(next,1.0);
  vec2 cp=toPx(c), pp=toPx(p), np=toPx(n);
  vec2 d1=cp-pp, d2=np-cp;
  if (length(d1)<1e-4) d1=d2; if (length(d2)<1e-4) d2=d1;
  d1=normalize(d1+1e-9); d2=normalize(d2+1e-9);
  vec2 t=d1+d2; t = length(t)<1e-3 ? d1 : normalize(t);
  vec2 nrm=vec2(-t.y,t.x);
  float ml = 1.0/max(dot(nrm, vec2(-d1.y,d1.x)), 0.4);
  float half_ = 0.5*uWidth*wmul*(uRes.y/2160.0);
  float ext = half_ + 1.0;
  vec2 off = nrm*side*ext*min(ml,2.5);
  c.xy += off/(0.5*uRes)*c.w;
  gl_Position = c;
  vU=u; vD=side*ext; vHalf=half_; vC=rgba;
}`;
const RIBBON_FS = `
uniform float uHead, uTail, uOpacity, uGlow, uPulse, uPulseK, uTime, uHeadGlow; uniform vec3 uColor;
varying float vU; varying float vD; varying float vHalf; varying vec4 vC;
void main(){
  if (vU > uHead || vU < uTail) discard;
  float d = abs(vD);
  float a = clamp(vHalf + 0.5 - d, 0.0, 1.0);
  float core = mix(1.0, pow(clamp(1.0 - d/(vHalf+1.0),0.0,1.0), 1.5), uGlow);
  float pulse = 1.0;
  if (uPulse > 0.0) { float ph = fract(vU*uPulseK - uTime*uPulse); pulse = 0.35 + 1.6*pow(ph, 6.0); }
  float head = 1.0 + uHeadGlow*exp(-pow((uHead - vU)*40.0, 2.0));
  float al = a*core*vC.a*uOpacity;
  if (al < 0.002) discard;
  gl_FragColor = vec4(uColor*vC.rgb*pulse*head*al, al);
}`;

export class Ribbon {
  // pts: array of THREE.Vector3; opts.colors: array of [r,g,b,a] per point or function(i,u)
  constructor(pts, { width = 4, color = '#ffffff', intensity = 1, additive = true, glow = 0.0, colors = null, widths = null, depthTest = true } = {}) {
    this.n = pts.length;
    const n = this.n;
    const g = new THREE.BufferGeometry();
    this.pos = new Float32Array(n * 2 * 3); this.prev = new Float32Array(n * 2 * 3); this.next = new Float32Array(n * 2 * 3);
    const side = new Float32Array(n * 2), u = new Float32Array(n * 2), rgba = new Float32Array(n * 2 * 4), wm = new Float32Array(n * 2);
    for (let i = 0; i < n; i++) {
      side[2 * i] = -1; side[2 * i + 1] = 1;
      const c = colors ? (typeof colors === 'function' ? colors(i, i / (n - 1)) : colors[i]) : [1, 1, 1, 1];
      for (let k = 0; k < 2; k++) { rgba.set([c[0], c[1], c[2], c[3] === undefined ? 1 : c[3]], (2 * i + k) * 4); wm[2 * i + k] = widths ? (typeof widths === 'function' ? widths(i, i / (n - 1)) : widths[i]) : 1; }
    }
    const idx = [];
    for (let i = 0; i < n - 1; i++) { const a = 2 * i; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
    g.setIndex(idx);
    g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3));
    g.setAttribute('prev', new THREE.BufferAttribute(this.prev, 3));
    g.setAttribute('next', new THREE.BufferAttribute(this.next, 3));
    g.setAttribute('side', new THREE.BufferAttribute(side, 1));
    g.setAttribute('u', new THREE.BufferAttribute(u, 1));
    g.setAttribute('rgba', new THREE.BufferAttribute(rgba, 4));
    g.setAttribute('wmul', new THREE.BufferAttribute(wm, 1));
    this.u = u;
    this.geo = g;
    this.mat = new THREE.ShaderMaterial({
      uniforms: {
        uRes: { value: new THREE.Vector2(3840, 2160) }, uWidth: { value: width }, uHead: { value: 1.01 }, uTail: { value: -0.01 },
        uOpacity: { value: 1 }, uGlow: { value: glow }, uPulse: { value: 0 }, uPulseK: { value: 6 }, uTime: { value: 0 }, uHeadGlow: { value: 0 },
        uColor: { value: new THREE.Color(color).multiplyScalar(intensity) },
      },
      vertexShader: RIBBON_VS, fragmentShader: RIBBON_FS,
      blending: THREE.CustomBlending,
      blendSrc: THREE.OneFactor, blendDst: additive ? THREE.OneFactor : THREE.OneMinusSrcAlphaFactor,
      transparent: true, depthWrite: false, depthTest, side: THREE.DoubleSide,
    });
    this.mesh = new THREE.Mesh(g, this.mat);
    this.mesh.frustumCulled = false;
    this.mesh.onBeforeRender = (r) => {
      const t = r.getRenderTarget();
      this.mat.uniforms.uRes.value.set(t ? t.width : r.domElement.width, t ? t.height : r.domElement.height);
    };
    this.setPoints(pts);
  }
  setPoints(pts) {
    const n = this.n;
    let L = 0; const acc = [0];
    for (let i = 1; i < n; i++) { L += pts[i].distanceTo(pts[i - 1]); acc.push(L); }
    for (let i = 0; i < n; i++) {
      const p = pts[i];
      const pv = i > 0 ? pts[i - 1] : p.clone().multiplyScalar(2).sub(pts[Math.min(1, n - 1)]);
      const nx = i < n - 1 ? pts[i + 1] : p.clone().multiplyScalar(2).sub(pts[Math.max(n - 2, 0)]);
      for (let k = 0; k < 2; k++) {
        const j = (2 * i + k) * 3;
        this.pos[j] = p.x; this.pos[j + 1] = p.y; this.pos[j + 2] = p.z;
        this.prev[j] = pv.x; this.prev[j + 1] = pv.y; this.prev[j + 2] = pv.z;
        this.next[j] = nx.x; this.next[j + 1] = nx.y; this.next[j + 2] = nx.z;
        this.u[2 * i + k] = L > 0 ? acc[i] / L : i / Math.max(n - 1, 1);
      }
    }
    for (const a of ['position', 'prev', 'next', 'u']) this.geo.attributes[a].needsUpdate = true;
  }
  set(o) {
    const U = this.mat.uniforms;
    if (o.head !== undefined) U.uHead.value = o.head;
    if (o.tail !== undefined) U.uTail.value = o.tail;
    if (o.opacity !== undefined) U.uOpacity.value = o.opacity;
    if (o.time !== undefined) U.uTime.value = o.time;
    if (o.pulse !== undefined) U.uPulse.value = o.pulse;
    if (o.pulseK !== undefined) U.uPulseK.value = o.pulseK;
    if (o.headGlow !== undefined) U.uHeadGlow.value = o.headGlow;
    if (o.width !== undefined) U.uWidth.value = o.width;
    if (o.color !== undefined) U.uColor.value.copy(new THREE.Color(o.color)).multiplyScalar(o.intensity ?? 1);
    this.mesh.visible = U.uOpacity.value > 0.001 && U.uHead.value > U.uTail.value;
    return this;
  }
}

export function arcPoints(a, b, lift = 0.5, n = 48) {
  const mid = a.clone().add(b).multiplyScalar(0.5); mid.y += lift;
  const c = new THREE.QuadraticBezierCurve3(a.clone(), mid, b.clone());
  return c.getPoints(n - 1);
}
export function circlePoints(r, n = 128, y = 0) {
  const pts = []; for (let i = 0; i <= n; i++) { const a = i / n * Math.PI * 2; pts.push(new THREE.Vector3(Math.cos(a) * r, y, Math.sin(a) * r)); } return pts;
}

// ---------------------------------------------------------------- triad (EEF pose glyph)
export function makeTriad(size = 0.12, width = 5, intensity = 2.2) {
  const g = new THREE.Group();
  const axes = [['#ff5a6a', new THREE.Vector3(1, 0, 0)], ['#5ef2a8', new THREE.Vector3(0, 1, 0)], ['#5aa2ff', new THREE.Vector3(0, 0, 1)]];
  g.userData.ribbons = axes.map(([c, d]) => {
    const r = new Ribbon([new THREE.Vector3(), d.clone().multiplyScalar(size)], { width, color: c, intensity, additive: true });
    g.add(r.mesh); return r;
  });
  return g;
}

// ---------------------------------------------------------------- grid floor
export function makeGrid({ size = 40, cell = 0.5, major = 5, color = '#6f8cff', opacity = 0.35, fade = 9 } = {}) {
  const mat = new THREE.ShaderMaterial({
    uniforms: { uCell: { value: cell }, uMajor: { value: major }, uColor: { value: new THREE.Color(color) }, uOpacity: { value: opacity }, uFade: { value: fade }, uCenter: { value: new THREE.Vector2() } },
    vertexShader: `varying vec3 vW; void main(){ vec4 w=modelMatrix*vec4(position,1.0); vW=w.xyz; gl_Position=projectionMatrix*viewMatrix*w; }`,
    fragmentShader: `uniform float uCell,uMajor,uOpacity,uFade; uniform vec3 uColor; uniform vec2 uCenter; varying vec3 vW;
      float gl_(vec2 p){ vec2 g=abs(fract(p-0.5)-0.5)/fwidth(p); return 1.0-min(min(g.x,g.y),1.0); }
      void main(){ vec2 p=vW.xz; float a = gl_(p/uCell)*0.45 + gl_(p/(uCell*uMajor))*0.8;
        float f = exp(-pow(length(p-uCenter)/uFade, 2.0));
        float al = a*f*uOpacity; if (al<0.002) discard; gl_FragColor=vec4(uColor*al, al); }`,
    transparent: true, depthWrite: false, blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor,
    extensions: { derivatives: true },
  });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(size, size), mat);
  m.rotation.x = -Math.PI / 2;
  m.userData.mat = mat;
  return m;
}

// ---------------------------------------------------------------- video / image panel
const PANEL_FS = `uniform sampler2D tMap; uniform float uHasMap; uniform vec2 uSize; uniform float uRadius, uOpacity, uBright, uSat, uBorder, uBorderI, uWipe, uWipeSoft, uDesat;
uniform vec3 uBorderColor, uTint; uniform vec4 uCrop; uniform sampler2D tOver; uniform float uOver; uniform float uScan, uTime, uRedden;
varying vec2 vUv;
float sdRR(vec2 p, vec2 b, float r){ vec2 q=abs(p)-b+r; return min(max(q.x,q.y),0.0)+length(max(q,0.0))-r; }
void main(){
  vec2 p = (vUv-0.5)*uSize;
  float d = sdRR(p, uSize*0.5, uRadius);
  float fw = fwidth(d);
  float inside = 1.0 - smoothstep(-fw, fw, d);
  vec2 uv = uCrop.xy + vUv*uCrop.zw;
  vec3 c = uHasMap > 0.5 ? texture2D(tMap, uv).rgb : vec3(0.02,0.03,0.05);
  float l = dot(c, vec3(0.2126,0.7152,0.0722));
  c = mix(vec3(l), c, uSat) * uBright * uTint;
  c = mix(c, vec3(l)*vec3(1.0,0.32,0.36)*1.4, uRedden);
  if (uOver > 0.0) { vec4 o = texture2D(tOver, vUv); c = c*(1.0-o.a*uOver) + o.rgb*uOver; }
  float wipe = smoothstep(uWipe - uWipeSoft, uWipe, vUv.x);
  float br = (1.0 - smoothstep(0.0, fw*1.5, abs(d + uBorder*0.5) - uBorder*0.5)) * uBorderI;
  float scan = uScan > 0.0 ? exp(-pow((vUv.y - fract(uTime*0.35))*30.0, 2.0))*uScan : 0.0;
  vec3 col = c*inside*(1.0-wipe) + uBorderColor*br + vec3(0.6,0.85,1.0)*scan*inside;
  float a = max(inside*(1.0-wipe), br) * uOpacity;
  gl_FragColor = vec4(col*uOpacity, a);
}`;
export function makePanel(w, h, { radius = 0.04, border = 0.006, borderColor = '#9fb8ff', borderI = 0.0 } = {}) {
  const mat = new THREE.ShaderMaterial({
    uniforms: {
      tMap: { value: null }, uHasMap: { value: 0 }, uSize: { value: new THREE.Vector2(w, h) }, uRadius: { value: radius }, uOpacity: { value: 1 },
      uBright: { value: 1 }, uSat: { value: 1 }, uBorder: { value: border }, uBorderI: { value: borderI }, uBorderColor: { value: new THREE.Color(borderColor) },
      uWipe: { value: 1.2 }, uWipeSoft: { value: 0.02 }, uCrop: { value: new THREE.Vector4(0, 0, 1, 1) }, tOver: { value: null }, uOver: { value: 0 },
      uScan: { value: 0 }, uTime: { value: 0 }, uTint: { value: new THREE.Vector3(1, 1, 1) }, uRedden: { value: 0 }, uDesat: { value: 0 },
    },
    vertexShader: `varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }`,
    fragmentShader: PANEL_FS, transparent: true, depthWrite: false,
    blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor,
    extensions: { derivatives: true }, side: THREE.DoubleSide,
  });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
  m.userData.mat = mat;
  m.userData.setMap = (tex) => { mat.uniforms.tMap.value = tex; mat.uniforms.uHasMap.value = tex ? 1 : 0; };
  return m;
}

// ---------------------------------------------------------------- screen projection for DOM labels
const _v = new THREE.Vector3();
export function toScreen(v, camera) {
  _v.copy(v).project(camera);
  return { x: (_v.x * 0.5 + 0.5) * DW, y: (-_v.y * 0.5 + 0.5) * DH, z: _v.z, behind: _v.z > 1 };
}

// ---------------------------------------------------------------- background haze sphere
export function makeHaze({ top = '#0a1222', bottom = '#020306', glow = '#16234a', glowDir = new THREE.Vector3(0, 0.2, -1), glowK = 0.6 } = {}) {
  const mat = new THREE.ShaderMaterial({
    uniforms: { uTop: { value: new THREE.Color(top) }, uBot: { value: new THREE.Color(bottom) }, uGlow: { value: new THREE.Color(glow) }, uDir: { value: glowDir.clone().normalize() }, uK: { value: glowK } },
    vertexShader: `varying vec3 vD; void main(){ vD=normalize(position); vec4 p=projectionMatrix*vec4(mat3(modelViewMatrix)*position,1.0); gl_Position=p.xyww; }`,
    fragmentShader: `uniform vec3 uTop,uBot,uGlow,uDir; uniform float uK; varying vec3 vD;
      void main(){ vec3 d=normalize(vD); float y=d.y*0.5+0.5; vec3 c=mix(uBot,uTop,smoothstep(0.2,0.9,y));
        c += uGlow*pow(max(dot(d,uDir),0.0),4.0)*uK; gl_FragColor=vec4(c,1.0); }`,
    side: THREE.BackSide, depthWrite: false,
  });
  const m = new THREE.Mesh(new THREE.SphereGeometry(10, 48, 24), mat);
  m.frustumCulled = false; m.renderOrder = -100;
  m.userData.mat = mat;
  return m;
}

// ---------------------------------------------------------------- many polylines, one draw call
const MULTI_VS = RIBBON_VS.replace('attribute vec3 prev;', 'attribute vec2 anim; uniform float uT; varying float vHead;\nattribute vec3 prev;')
  .replace('vU=u; vD=side*ext;', 'vHead=(uT-anim.x)*anim.y; vU=u; vD=side*ext;');
const MULTI_FS = RIBBON_FS.replace('varying float vU;', 'varying float vHead; uniform float uLen; varying float vU;')
  .replace('if (vU > uHead || vU < uTail) discard;', 'if (vU > vHead || vU < vHead - uLen || vU > uHead) discard;')
  .replace('float head = 1.0 + uHeadGlow*exp(-pow((uHead - vU)*40.0, 2.0));', 'float head = 1.0 + uHeadGlow*exp(-pow((vHead - vU)*30.0, 2.0));');
export class MultiRibbon {
  // lines: [{pts:[Vector3], t0, speed, color:[r,g,b,a], width}]
  constructor(lines, { width = 3, color = '#ffffff', intensity = 1, additive = true, len = 10, glow = 0 } = {}) {
    let nv = 0; for (const L of lines) nv += L.pts.length * 2;
    const pos = new Float32Array(nv * 3), prev = new Float32Array(nv * 3), next = new Float32Array(nv * 3);
    const side = new Float32Array(nv), u = new Float32Array(nv), rgba = new Float32Array(nv * 4), wm = new Float32Array(nv), anim = new Float32Array(nv * 2);
    const idx = []; let o = 0;
    for (const L of lines) {
      const P = L.pts, n = P.length; let len_ = 0; const acc = [0];
      for (let i = 1; i < n; i++) { len_ += P[i].distanceTo(P[i - 1]); acc.push(len_); }
      for (let i = 0; i < n; i++) {
        const p = P[i], pv = P[Math.max(i - 1, 0)], nx = P[Math.min(i + 1, n - 1)];
        for (let k = 0; k < 2; k++) {
          const j = o + 2 * i + k;
          pos.set([p.x, p.y, p.z], j * 3); prev.set([pv.x, pv.y, pv.z], j * 3); next.set([nx.x, nx.y, nx.z], j * 3);
          side[j] = k ? 1 : -1; u[j] = acc[i] / Math.max(len_, 1e-6);
          const c = L.color || [1, 1, 1, 1]; rgba.set([c[0], c[1], c[2], c[3] ?? 1], j * 4);
          wm[j] = L.width || 1; anim[j * 2] = L.t0 || 0; anim[j * 2 + 1] = L.speed || 1;
        }
        if (i < n - 1) { const a = o + 2 * i; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
      }
      o += n * 2;
    }
    const g = new THREE.BufferGeometry();
    g.setIndex(idx);
    const A = (a, n) => new THREE.BufferAttribute(a, n);
    g.setAttribute('position', A(pos, 3)); g.setAttribute('prev', A(prev, 3)); g.setAttribute('next', A(next, 3));
    g.setAttribute('side', A(side, 1)); g.setAttribute('u', A(u, 1)); g.setAttribute('rgba', A(rgba, 4)); g.setAttribute('wmul', A(wm, 1)); g.setAttribute('anim', A(anim, 2));
    this.mat = new THREE.ShaderMaterial({
      uniforms: {
        uRes: { value: new THREE.Vector2(3840, 2160) }, uWidth: { value: width }, uHead: { value: 10 }, uTail: { value: -1 }, uOpacity: { value: 1 }, uGlow: { value: glow },
        uPulse: { value: 0 }, uPulseK: { value: 6 }, uTime: { value: 0 }, uHeadGlow: { value: 1.5 }, uT: { value: 0 }, uLen: { value: len },
        uColor: { value: new THREE.Color(color).multiplyScalar(intensity) },
      },
      vertexShader: MULTI_VS, fragmentShader: MULTI_FS, transparent: true, depthWrite: false, side: THREE.DoubleSide,
      blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: additive ? THREE.OneFactor : THREE.OneMinusSrcAlphaFactor,
    });
    this.mesh = new THREE.Mesh(g, this.mat); this.mesh.frustumCulled = false;
    this.mesh.onBeforeRender = (r) => { const t = r.getRenderTarget(); this.mat.uniforms.uRes.value.set(t ? t.width : r.domElement.width, t ? t.height : r.domElement.height); };
  }
}
