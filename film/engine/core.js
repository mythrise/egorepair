// Core runtime for deterministic, frame-by-frame film rendering in headless Chromium.
import * as THREE from 'three';

export { THREE };
export const DW = 3840, DH = 2160; // design space

// ---------- math / easing ----------
export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const remap = (x, a, b) => clamp((x - a) / (b - a));
export const smooth = (t) => { t = clamp(t); return t * t * (3 - 2 * t); };
export const smoother = (t) => { t = clamp(t); return t * t * t * (t * (t * 6 - 15) + 10); };
export const easeOutCubic = (t) => 1 - Math.pow(1 - clamp(t), 3);
export const easeInCubic = (t) => Math.pow(clamp(t), 3);
export const easeInOutCubic = (t) => { t = clamp(t); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
export const easeOutExpo = (t) => { t = clamp(t); return t === 1 ? 1 : 1 - Math.pow(2, -10 * t); };
export const easeInOutExpo = (t) => { t = clamp(t); if (t === 0 || t === 1) return t; return t < 0.5 ? Math.pow(2, 20 * t - 10) / 2 : (2 - Math.pow(2, -20 * t + 10)) / 2; };
export const easeOutQuint = (t) => 1 - Math.pow(1 - clamp(t), 5);
export const easeOutBack = (t, s = 1.4) => { t = clamp(t) - 1; return t * t * ((s + 1) * t + s) + 1; };
// window: rises over [a,a+fi], holds, falls over [b-fo,b]
export const win = (t, a, b, fi = 0.5, fo = 0.5) => Math.min(smooth((t - a) / fi), smooth((b - t) / fo));

export function rng(seed = 1) {
  let s = seed >>> 0 || 1;
  return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; };
}
export function hash(n) { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); }

// ---------- DOM helpers ----------
export function el(parent, cls = '', html = '', style = {}) {
  const e = document.createElement('div');
  if (cls) e.className = cls;
  if (html) e.innerHTML = html;
  Object.assign(e.style, style);
  parent.appendChild(e);
  return e;
}
export function setStyle(e, s) { for (const k in s) e.style[k] = s[k]; }

// Split text into per-character spans for reveal animations.
export function splitChars(e, text) {
  e.innerHTML = '';
  const spans = [];
  for (const ch of text) {
    const s = document.createElement('span');
    s.textContent = ch === ' ' ? ' ' : ch;
    s.style.display = 'inline-block';
    e.appendChild(s);
    spans.push(s);
  }
  return spans;
}
// Cinematic per-character reveal: blur -> sharp, rise, fade. p in [0,1].
export function revealChars(spans, p, { stagger = 0.035, dur = 0.5, rise = 40, blur = 18, out = 0 } = {}) {
  const n = spans.length;
  const total = dur + stagger * (n - 1);
  for (let i = 0; i < n; i++) {
    const local = clamp((p * total - i * stagger) / dur);
    const e = easeOutCubic(local);
    const o = out > 0 ? 1 - easeInCubic(clamp((out * total - i * stagger * 0.5) / dur)) : 1;
    spans[i].style.opacity = (e * o).toFixed(3);
    spans[i].style.transform = `translateY(${((1 - e) * rise).toFixed(1)}px)`;
    const b = (1 - e) * blur + (1 - o) * blur;
    spans[i].style.filter = b > 0.3 ? `blur(${b.toFixed(1)}px)` : 'none';
  }
}

// ---------- assets ----------
const imgCache = new Map();
export function loadImage(url) {
  if (imgCache.has(url)) return imgCache.get(url);
  const p = new Promise((res, rej) => {
    const im = new Image();
    im.crossOrigin = 'anonymous';
    im.onload = () => im.decode().then(() => res(im), () => res(im));
    im.onerror = () => rej(new Error('img ' + url));
    im.src = url;
  });
  imgCache.set(url, p);
  return p;
}
export async function loadJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error('json ' + url); return r.json(); }
export async function loadF32(url) { const r = await fetch(url); if (!r.ok) throw new Error('f32 ' + url); return new Float32Array(await r.arrayBuffer()); }

// Image-sequence video texture: frames at `${dir}/%04d.jpg`, played at srcFps.
export class SeqTexture {
  constructor(dir, count, { srcFps = 30, ext = 'jpg', start = 0, loop = true } = {}) {
    this.dir = dir; this.count = count; this.srcFps = srcFps; this.ext = ext; this.start = start; this.loop = loop;
    this.tex = new THREE.Texture();
    this.tex.colorSpace = THREE.SRGBColorSpace;
    this.tex.minFilter = THREE.LinearFilter; this.tex.magFilter = THREE.LinearFilter; this.tex.generateMipmaps = false;
    this.cur = -1;
    this.image = null;
  }
  indexAt(t) {
    let i = Math.floor(t * this.srcFps + 1e-6) + this.start;
    if (this.loop) i = ((i % this.count) + this.count) % this.count; else i = clamp(i, 0, this.count - 1);
    return i;
  }
  url(i) { return `${this.dir}/${String(i).padStart(4, '0')}.${this.ext}`; }
  async at(t) {
    const i = this.indexAt(t);
    if (i !== this.cur) {
      const im = await loadImage(this.url(i));
      this.image = im; this.tex.image = im; this.tex.needsUpdate = true; this.cur = i;
      // free old cache entries far away
      if (imgCache.size > 120) { const k = imgCache.keys().next().value; imgCache.delete(k); }
    }
    return this.tex;
  }
}

// ---------- lean post pipeline ----------
// scene -> HDR target (W x H) ; bloom computed at 1/4 and 1/8 res ; one final composite pass to screen.
const VS = `varying vec2 vUv; void main(){ vUv=uv; gl_Position=vec4(position.xy,0.0,1.0); }`;
const DOWN_FS = `uniform sampler2D tSrc; uniform vec2 uTexel; uniform float uThresh, uKnee; uniform float uPrefilter; varying vec2 vUv;
  vec3 pf(vec3 c){ if(uPrefilter<0.5) return c; float br=max(c.r,max(c.g,c.b)); float rq=clamp(br-uThresh+uKnee,0.0,2.0*uKnee); rq=rq*rq/(4.0*uKnee+1e-4);
    float w=max(rq,br-uThresh)/max(br,1e-4); return c*w; }
  void main(){ vec2 o=uTexel; vec3 c = texture2D(tSrc,vUv+vec2(-o.x,-o.y)).rgb + texture2D(tSrc,vUv+vec2(o.x,-o.y)).rgb
     + texture2D(tSrc,vUv+vec2(-o.x,o.y)).rgb + texture2D(tSrc,vUv+vec2(o.x,o.y)).rgb; gl_FragColor=vec4(pf(c*0.25),1.0); }`;
const BLUR_FS = `uniform sampler2D tSrc; uniform vec2 uDir; varying vec2 vUv;
  void main(){ vec3 c = texture2D(tSrc,vUv).rgb*0.2270270270;
    c += (texture2D(tSrc,vUv+uDir*1.3846153846).rgb+texture2D(tSrc,vUv-uDir*1.3846153846).rgb)*0.3162162162;
    c += (texture2D(tSrc,vUv+uDir*3.2307692308).rgb+texture2D(tSrc,vUv-uDir*3.2307692308).rgb)*0.0702702703;
    gl_FragColor=vec4(c,1.0); }`;
const FINAL_FS = `uniform sampler2D tScene, tB1, tB2, tB3; uniform float uBloom, uVignette, uCA, uExposure, uFade, uSat, uGrain;
  uniform vec3 uLift, uTint; uniform vec2 uRes; varying vec2 vUv;
  float h12(vec2 p){ vec3 p3=fract(vec3(p.xyx)*.1031); p3+=dot(p3,p3.yzx+33.33); return fract((p3.x+p3.y)*p3.z); }
  vec3 aces(vec3 x){ const float a=2.51,b=0.03,c=2.43,d=0.59,e=0.14; return clamp((x*(a*x+b))/(x*(c*x+d)+e),0.0,1.0); }
  vec3 toSRGB(vec3 c){ return mix(c*12.92, 1.055*pow(c,vec3(1.0/2.4))-0.055, step(0.0031308,c)); }
  void main(){
    vec2 d=vUv-0.5; float r2=dot(d,d);
    vec3 c;
    if (uCA > 0.0) { vec2 off=d*uCA*(1.0+4.0*r2);
      c=vec3(texture2D(tScene,vUv-off).r, texture2D(tScene,vUv).g, texture2D(tScene,vUv+off).b); }
    else c=texture2D(tScene,vUv).rgb;
    vec3 b = texture2D(tB1,vUv).rgb*0.55 + texture2D(tB2,vUv).rgb*0.75 + texture2D(tB3,vUv).rgb*1.0;
    c += b*uBloom;
    c *= uExposure*uTint;
    c = aces(c);
    c = toSRGB(c);
    float l=dot(c,vec3(0.2126,0.7152,0.0722)); c=mix(vec3(l),c,uSat);
    c = c + uLift*(1.0-c);
    c *= (1.0 - uVignette*smoothstep(0.08,0.62,r2*1.55)) * uFade;
    float n=h12(gl_FragCoord.xy)+h12(gl_FragCoord.xy+17.17)-1.0;
    c += n/255.0*0.9;
    gl_FragColor=vec4(c,1.0);
  }`;

function makeRT(w, h, samples = 0) {
  return new THREE.WebGLRenderTarget(w, h, { type: THREE.HalfFloatType, samples, depthBuffer: true,
    minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, generateMipmaps: false });
}

export async function createContext(W, H, q) {
  const stage = document.getElementById('stage');
  stage.style.width = W + 'px'; stage.style.height = H + 'px';
  const canvas = document.getElementById('gl');
  const c2d = document.getElementById('c2d');
  c2d.width = W; c2d.height = H; c2d.style.width = W + 'px'; c2d.style.height = H + 'px';
  const ui = document.getElementById('ui');
  ui.style.transform = `scale(${W / DW})`;
  const g2 = c2d.getContext('2d');
  const S = W / DW;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(1);
  renderer.setSize(W, H, true);
  renderer.toneMapping = THREE.NoToneMapping;
  renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
  renderer.autoClear = true;

  const samples = +(q.get('msaa') || 0);
  const rtScene = makeRT(W, H, samples);
  const w4 = Math.round(W / 4), h4 = Math.round(H / 4), w8 = Math.round(W / 8), h8 = Math.round(H / 8), w16 = Math.round(W / 16), h16 = Math.round(H / 16);
  const rA = makeRT(w4, h4), rB = makeRT(w4, h4), rC = makeRT(w8, h8), rD = makeRT(w8, h8), rE = makeRT(w16, h16), rF = makeRT(w16, h16);
  for (const r of [rA, rB, rC, rD, rE, rF]) r.depthBuffer = false;

  const quadScene = new THREE.Scene();
  const quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), null);
  quad.frustumCulled = false;
  quadScene.add(quad);
  const mk = (fs, u) => new THREE.ShaderMaterial({ vertexShader: VS, fragmentShader: fs, uniforms: u, depthTest: false, depthWrite: false, toneMapped: false });
  const down = mk(DOWN_FS, { tSrc: { value: null }, uTexel: { value: new THREE.Vector2() }, uThresh: { value: 0.85 }, uKnee: { value: 0.35 }, uPrefilter: { value: 1 } });
  const blur = mk(BLUR_FS, { tSrc: { value: null }, uDir: { value: new THREE.Vector2() } });
  const fin = mk(FINAL_FS, {
    tScene: { value: rtScene.texture }, tB1: { value: rA.texture }, tB2: { value: rC.texture }, tB3: { value: rE.texture },
    uBloom: { value: 0.9 }, uVignette: { value: 0.35 }, uCA: { value: 0.0 }, uExposure: { value: 1.0 }, uFade: { value: 1.0 },
    uSat: { value: 1.0 }, uGrain: { value: 0 }, uLift: { value: new THREE.Vector3(0, 0, 0) }, uTint: { value: new THREE.Vector3(1, 1, 1) },
    uRes: { value: new THREE.Vector2(W, H) },
  });
  const pass = (mat, target) => { quad.material = mat; renderer.setRenderTarget(target); renderer.render(quadScene, quadCam); };
  const grade = fin.uniforms;
  const bloomCfg = { threshold: 0.85, knee: 0.35, strength: 0.9 };

  function bloomChain() {
    // 1/4: prefilter + downsample (src texel = 1/W so 4 taps at +-1px cover a 4x4 block)
    down.uniforms.tSrc.value = rtScene.texture; down.uniforms.uTexel.value.set(1 / W, 1 / H);
    down.uniforms.uThresh.value = bloomCfg.threshold; down.uniforms.uKnee.value = bloomCfg.knee; down.uniforms.uPrefilter.value = 1;
    pass(down, rA);
    blur.uniforms.tSrc.value = rA.texture; blur.uniforms.uDir.value.set(1 / w4, 0); pass(blur, rB);
    blur.uniforms.tSrc.value = rB.texture; blur.uniforms.uDir.value.set(0, 1 / h4); pass(blur, rA);
    down.uniforms.tSrc.value = rA.texture; down.uniforms.uTexel.value.set(0.5 / w4, 0.5 / h4); down.uniforms.uPrefilter.value = 0;
    pass(down, rC);
    blur.uniforms.tSrc.value = rC.texture; blur.uniforms.uDir.value.set(1.5 / w8, 0); pass(blur, rD);
    blur.uniforms.tSrc.value = rD.texture; blur.uniforms.uDir.value.set(0, 1.5 / h8); pass(blur, rC);
    down.uniforms.tSrc.value = rC.texture; down.uniforms.uTexel.value.set(0.5 / w8, 0.5 / h8);
    pass(down, rE);
    blur.uniforms.tSrc.value = rE.texture; blur.uniforms.uDir.value.set(2.5 / w16, 0); pass(blur, rF);
    blur.uniforms.tSrc.value = rF.texture; blur.uniforms.uDir.value.set(0, 2.5 / h16); pass(blur, rE);
  }

  const ctx = {
    W, H, S, q, ui, g2, renderer, grade, bloomCfg, rtScene,
    preview: W < 3000,
    // Render a 3D scene through the cinematic pipeline. Optionally pass an array of [scene,camera] layers.
    render(scene, camera, { bloom = true, layers = null } = {}) {
      renderer.setRenderTarget(rtScene);
      if (layers) {
        renderer.autoClear = false; renderer.clear();
        for (const [s, c, clearDepth] of layers) { if (clearDepth) renderer.clearDepth(); renderer.render(s, c); }
        renderer.autoClear = true;
      } else renderer.render(scene, camera);
      const useBloom = bloom && !q.get('nobloom');
      if (useBloom) bloomChain();
      grade.uBloom.value = useBloom ? bloomCfg.strength : 0;
      pass(fin, null);
    },
    blank(color = 0x04060a) { renderer.setRenderTarget(null); renderer.setClearColor(color, 1); renderer.clear(); },
    clear2d() { g2.setTransform(1, 0, 0, 1, 0, 0); g2.clearRect(0, 0, W, H); g2.setTransform(S, 0, 0, S, 0, 0); },
    present() {},
  };
  ctx.clear2d();
  return ctx;
}
