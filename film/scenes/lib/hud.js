// Live system HUD: state-machine rail and budget ledger (values from the V5 agent spec M8.2).
import { el, clamp, smooth, remap } from '@engine/core.js';

export const STATES = ['INGEST', 'QUALIFY_INPUT', 'BUILD_GRAPH', 'AUDIT', 'SPECIALIST_REPORT', 'COORDINATE', 'GENERATE', 'PROJECT', 'SIMULATE', 'COMPARE', 'COMMIT', 'EXPORT'];
export const BRANCHES = ['REQUEST_EVIDENCE', 'NOOP', 'REJECT', 'HUMAN_REVIEW'];

export class StateRail {
  constructor(ui, { y = 1985 } = {}) {
    this.root = el(ui, 'abs', '', { left: '150px', top: y + 'px', width: '3540px' });
    this.line = el(this.root, 'abs', '', { left: '0px', top: '-26px', width: '3540px', height: '2px', background: 'rgba(238,243,255,0.16)' });
    this.prog = el(this.root, 'abs', '', { left: '0px', top: '-26px', width: '0px', height: '2px', background: 'linear-gradient(90deg,#74d7ff,#9d8cff)', boxShadow: '0 0 18px #74d7ff' });
    const w = 3540 / STATES.length;
    this.w = w;
    this.items = STATES.map((s, i) => el(this.root, 'abs mono', s, { left: (i * w) + 'px', top: '0px', width: w + 'px', fontSize: '21px', letterSpacing: '0.05em', color: 'rgba(238,243,255,0.3)', whiteSpace: 'nowrap' }));
    this.ticks = STATES.map((s, i) => el(this.root, 'abs', '', { left: (i * w) + 'px', top: '-33px', width: '16px', height: '16px', borderRadius: '50%', background: '#04060a', border: '2px solid rgba(238,243,255,0.3)' }));
    this.br = el(this.root, 'abs', '', { left: '0px', top: '52px', width: '3540px' });
    this.bitems = BRANCHES.map((s, i) => el(this.br, 'abs mono', '↳ ' + s, { left: (i * 520) + 'px', top: '0px', fontSize: '20px', color: 'rgba(238,243,255,0.18)', whiteSpace: 'nowrap' }));
    this.root.style.opacity = 0;
  }
  // schedule: [[time, stateIndex]], branchEvents: [[t0,t1,branchIndex]]
  update(t, schedule, branchEvents = [], vis = 1) {
    this.root.style.opacity = vis.toFixed(3);
    let cur = -1, since = 0;
    for (const [tt, i] of schedule) if (t >= tt) { cur = i; since = t - tt; }
    this.items.forEach((e, i) => {
      const done = i < cur, act = i === cur;
      e.style.color = act ? '#ffffff' : done ? 'rgba(160,215,255,0.75)' : 'rgba(238,243,255,0.28)';
      e.style.textShadow = act ? '0 0 22px rgba(116,215,255,0.9)' : 'none';
      const tk = this.ticks[i];
      tk.style.background = act ? '#74d7ff' : done ? 'rgba(116,215,255,0.55)' : '#04060a';
      tk.style.borderColor = act || done ? '#74d7ff' : 'rgba(238,243,255,0.3)';
      tk.style.boxShadow = act ? `0 0 ${(20 + 10 * Math.sin(t * 6)).toFixed(0)}px #74d7ff` : 'none';
    });
    const px = cur < 0 ? 0 : cur * this.w + Math.min(since * 120, this.w * 0.0);
    this.prog.style.width = px + 'px';
    this.bitems.forEach((e, i) => {
      let k = 0;
      for (const [a, b, j] of branchEvents) if (j === i) k = Math.max(k, Math.min(smooth((t - a) / 0.3), smooth((b - t) / 0.5)));
      e.style.color = k > 0.01 ? `rgba(255,181,71,${(0.3 + 0.7 * k).toFixed(3)})` : 'rgba(238,243,255,0.18)';
      e.style.textShadow = k > 0.01 ? `0 0 ${(20 * k).toFixed(0)}px rgba(255,181,71,0.9)` : 'none';
    });
  }
}

// Budget ledger: rows with segmented bars. caps from spec: responses<=6, tools<=20, spatial<=4, Jev<=2, diffusion 8, replays 16, rounds 3.
export const BUDGET_ROWS = [
  ['COORDINATOR RESPONSES', 6], ['TOOL EXECUTIONS', 20], ['SPATIAL EXPERT CALLS', 4], ['JEV BATCHES', 2],
  ['DIFFUSION CANDIDATES', 8], ['SELECTION REPLAYS', 16], ['REPAIR ROUND', 3],
];
export class Budget {
  constructor(ui, { x = 2830, y = 120 } = {}) {
    this.root = el(ui, 'abs', '', { left: x + 'px', top: y + 'px', width: '870px' });
    el(this.root, 'mono', 'EPISODE BUDGET LEDGER', { fontSize: '22px', color: 'rgba(238,243,255,0.55)', marginBottom: '22px', letterSpacing: '0.2em' });
    this.rows = BUDGET_ROWS.map(([name, cap]) => {
      const r = el(this.root, '', '', { position: 'relative', height: '50px' });
      el(r, 'abs mono', name, { left: '0px', top: '6px', fontSize: '19px', letterSpacing: '0.08em', color: 'rgba(238,243,255,0.6)', whiteSpace: 'nowrap' });
      const segs = [];
      const bw = 300, gap = 4, sw = (bw - gap * (cap - 1)) / cap;
      for (let i = 0; i < cap; i++) segs.push(el(r, 'abs', '', { left: (460 + i * (sw + gap)) + 'px', top: '10px', width: sw + 'px', height: '14px', borderRadius: '2px', background: 'rgba(238,243,255,0.12)' }));
      const v = el(r, 'abs mono-n', '0/' + cap, { left: '780px', top: '2px', fontSize: '24px', color: '#eef3ff', width: '90px', textAlign: 'right' });
      return { segs, v, cap };
    });
    this.root.style.opacity = 0;
  }
  // values: array of numbers (may be fractional for animation)
  update(values, vis = 1, t = 0) {
    this.root.style.opacity = vis.toFixed(3);
    this.rows.forEach((r, i) => {
      const val = values[i] || 0;
      r.segs.forEach((s, j) => {
        const f = clamp(val - j);
        s.style.background = f > 0.01 ? `rgba(116,215,255,${(0.25 + 0.75 * f).toFixed(3)})` : 'rgba(238,243,255,0.12)';
        s.style.boxShadow = f > 0.5 && val - j < 1.6 ? '0 0 14px rgba(116,215,255,0.8)' : 'none';
      });
      r.v.textContent = Math.floor(val + 1e-6) + '/' + r.cap;
    });
  }
}

// step function helper: count of events with time <= t, with a short ramp
export function counter(t, times, ramp = 0.25) { let v = 0; for (const tt of times) v += clamp((t - tt) / ramp); return v; }
