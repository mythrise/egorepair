// DOM typography layer (design space 3840x2160). Everything is driven by explicit time, never CSS animation.
import { el, splitChars, revealChars, clamp, remap, smooth, easeOutCubic, easeInCubic, easeOutExpo } from './core.js';

// Bilingual title: English display headline + Chinese subtitle.
export class Title {
  constructor(ui, { en, zh = '', x = 1920, y = 1080, align = 'center', size = 150, weight = 600, zhSize = 50, width = 3400, gap = 46, grad = false, kicker = '' }) {
    this.root = el(ui, 'abs', '', { left: '0px', top: '0px', width: '3840px', height: '2160px' });
    const left = align === 'center' ? x - width / 2 : align === 'right' ? x - width : x;
    this.box = el(this.root, 'abs', '', { left: left + 'px', top: y + 'px', width: width + 'px', textAlign: align, transform: 'translateY(-50%)' });
    if (kicker) {
      this.kick = el(this.box, 'mono', kicker, { fontSize: '30px', marginBottom: '38px', color: 'rgba(238,243,255,0.55)' });
    }
    this.h = el(this.box, 'h1' + (grad ? ' grad' : ''), '', { fontSize: size + 'px', fontWeight: weight, whiteSpace: 'pre-wrap' });
    this.spans = splitChars(this.h, en);
    if (grad) this.spans.forEach((s) => s.classList.add('grad'));
    if (zh) {
      this.z = el(this.box, 'zh', zh, { fontSize: zhSize + 'px', marginTop: gap + 'px' });
    }
    this.root.style.opacity = 0;
  }
  // inT..outT in seconds; t current time
  update(t, inT, outT, { inDur = 1.1, outDur = 0.7, stagger = 0.028 } = {}) {
    const p = remap(t, inT, inT + inDur + stagger * this.spans.length);
    const o = remap(t, outT - outDur, outT);
    const vis = t >= inT && t <= outT;
    this.root.style.opacity = vis ? 1 : 0;
    if (!vis) return;
    revealChars(this.spans, p, { stagger, dur: 0.55, rise: 46, blur: 22 });
    const oe = easeInCubic(o);
    this.box.style.filter = oe > 0.01 ? `blur(${(oe * 26).toFixed(1)}px)` : 'none';
    this.box.style.opacity = (1 - oe).toFixed(3);
    this.box.style.transform = `translateY(calc(-50% - ${(oe * 40).toFixed(1)}px))`;
    if (this.z) {
      const zp = easeOutCubic(remap(t, inT + 0.45, inT + 1.6));
      this.z.style.opacity = zp.toFixed(3);
      this.z.style.letterSpacing = (0.62 - 0.3 * zp).toFixed(3) + 'em';
      this.z.style.filter = zp < 0.99 ? `blur(${((1 - zp) * 10).toFixed(1)}px)` : 'none';
    }
    if (this.kick) {
      const kp = easeOutCubic(remap(t, inT - 0.2, inT + 0.8));
      this.kick.style.opacity = (kp * 0.9).toFixed(3);
      this.kick.style.letterSpacing = (0.45 - 0.25 * kp).toFixed(3) + 'em';
    }
  }
}

// Chapter mark, top-left: "01   THE GAP   鸿沟"
export class Chapter {
  constructor(ui, num, en, zh) {
    this.e = el(ui, 'abs', `<span class="mono" style="color:rgba(238,243,255,0.85);font-size:30px">${num}</span>` +
      `<span style="display:inline-block;width:90px;height:2px;background:rgba(238,243,255,0.4);margin:0 34px;vertical-align:middle"></span>` +
      `<span class="mono" style="color:rgba(238,243,255,0.85);font-size:30px">${en}</span>` +
      `<span class="zh-s" style="margin-left:34px;font-size:30px;letter-spacing:0.3em">${zh}</span>`, { left: '150px', top: '120px' });
    this.e.style.opacity = 0;
  }
  update(t, a, b) { const k = Math.min(smooth((t - a) / 0.8), smooth((b - t) / 0.6)); this.e.style.opacity = k.toFixed(3); this.e.style.transform = `translateX(${((1 - k) * -30).toFixed(1)}px)`; }
}

// Small anchored label with leader line (anchor in design px).
export class Callout {
  constructor(ui, { title, sub = '', color = '#74d7ff', side = 'right', dx = 260, dy = -150, mono = true, size = 40, width = 900 }) {
    this.color = color; this.side = side; this.dx = dx; this.dy = dy;
    this.root = el(ui, 'abs', '', { left: '0px', top: '0px', width: '3840px', height: '2160px' });
    this.svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    this.svg.setAttribute('width', '3840'); this.svg.setAttribute('height', '2160');
    this.svg.style.position = 'absolute'; this.svg.style.left = '0'; this.svg.style.top = '0';
    this.root.appendChild(this.svg);
    this.line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    this.line.setAttribute('fill', 'none'); this.line.setAttribute('stroke', color); this.line.setAttribute('stroke-width', '3');
    this.dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    this.dot.setAttribute('r', '9'); this.dot.setAttribute('fill', color);
    this.ring = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    this.ring.setAttribute('fill', 'none'); this.ring.setAttribute('stroke', color); this.ring.setAttribute('stroke-width', '2');
    this.svg.append(this.line, this.ring, this.dot);
    this.box = el(this.root, 'abs', '', { width: width + 'px' });
    this.t = el(this.box, mono ? 'mono' : 'h3', title, { color, fontSize: size + 'px', letterSpacing: mono ? '0.08em' : '-0.01em', textTransform: mono ? 'uppercase' : 'none', whiteSpace: 'nowrap' });
    if (sub) this.s = el(this.box, 'zh-s', sub, { fontSize: '34px', marginTop: '14px', letterSpacing: '0.16em' });
    this.root.style.opacity = 0;
  }
  update(ax, ay, k, t = 0) {
    this.root.style.opacity = k > 0.001 ? 1 : 0;
    if (k <= 0.001) return;
    const kk = easeOutCubic(k);
    const ex = ax + this.dx, ey = ay + this.dy;
    const hx = ex + (this.side === 'right' ? 60 : -60);
    const lp = clamp(kk * 1.6);
    const mx = ax + (ex - ax) * lp, my = ay + (ey - ay) * lp;
    const pts = lp < 1 ? `${ax},${ay} ${mx},${my}` : `${ax},${ay} ${ex},${ey} ${ax + (hx - ax) * 1},${ey}`;
    this.line.setAttribute('points', pts);
    this.line.setAttribute('opacity', kk.toFixed(3));
    this.dot.setAttribute('cx', ax); this.dot.setAttribute('cy', ay);
    const pr = 18 + 10 * Math.sin(t * 4);
    this.ring.setAttribute('cx', ax); this.ring.setAttribute('cy', ay); this.ring.setAttribute('r', pr.toFixed(1)); this.ring.setAttribute('opacity', (0.6 * kk).toFixed(3));
    const bk = clamp((kk - 0.45) / 0.55);
    this.box.style.left = (this.side === 'right' ? hx + 20 : hx - 20 - parseFloat(this.box.style.width)) + 'px';
    this.box.style.top = (ey - 30) + 'px';
    this.box.style.textAlign = this.side === 'right' ? 'left' : 'right';
    this.box.style.opacity = bk.toFixed(3);
    this.box.style.transform = `translateX(${((1 - bk) * (this.side === 'right' ? -20 : 20)).toFixed(1)}px)`;
  }
}

export function fmtInt(n) { return Math.round(n).toLocaleString('en-US'); }

// Big statistic: number that counts up + caption.
export class Stat {
  constructor(ui, { x, y, value, decimals = 0, suffix = '', prefix = '', en, zh, size = 210, color = '#eef3ff', align = 'left' }) {
    this.value = value; this.decimals = decimals; this.suffix = suffix; this.prefix = prefix;
    this.root = el(ui, 'abs', '', { left: x + 'px', top: y + 'px', textAlign: align, width: '1100px', marginLeft: align === 'center' ? '-550px' : '0' });
    this.n = el(this.root, 'h1', '', { fontSize: size + 'px', fontWeight: 300, letterSpacing: '-0.04em', color, fontVariantNumeric: 'tabular-nums' });
    this.c = el(this.root, 'mono', en, { fontSize: '30px', marginTop: '20px', color: 'rgba(238,243,255,0.7)' });
    if (zh) this.z = el(this.root, 'zh-s', zh, { fontSize: '32px', marginTop: '12px' });
    this.root.style.opacity = 0;
  }
  update(t, a, b, countDur = 1.6) {
    const k = Math.min(smooth((t - a) / 0.6), smooth((b - t) / 0.6));
    this.root.style.opacity = k.toFixed(3);
    if (k <= 0) return;
    const p = easeOutExpo(remap(t, a, a + countDur));
    const v = this.value * p;
    this.n.textContent = this.prefix + (this.decimals ? v.toFixed(this.decimals) : fmtInt(v)) + this.suffix;
    this.root.style.transform = `translateY(${((1 - smooth((t - a) / 0.8)) * 30).toFixed(1)}px)`;
  }
}

export function fadeEl(e, k, { blur = 0, dy = 0 } = {}) {
  e.style.opacity = clamp(k).toFixed(3);
  e.style.display = k <= 0.001 ? 'none' : '';
  if (blur) e.style.filter = k < 0.99 ? `blur(${((1 - k) * blur).toFixed(1)}px)` : 'none';
  if (dy) e.style.transform = `translateY(${((1 - k) * dy).toFixed(1)}px)`;
}
