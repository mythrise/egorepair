"""Original score + sound design for the EgoRepair film, synthesized from scratch and synced to timeline.json.

usage: score.py TIMELINE_JSON OUT_WAV
Instruments are vectorized numpy synths; space and glue come from pedalboard (reverb, delay, compression, limiting).
"""
import json, math, sys
import numpy as np
from scipy import signal
from pedalboard import Pedalboard, Reverb, Compressor, Limiter, Delay, HighpassFilter, LowpassFilter, Chorus, LowShelfFilter, PeakFilter, HighShelfFilter

SR = 48000
rng = np.random.default_rng(7)
TL = json.load(open(sys.argv[1]))
START = {}
acc = 0.0
for s in TL["scenes"]:
    START[s["id"]] = acc
    acc += s["dur"]
TOTAL = acc
N = int((TOTAL + 2.0) * SR)
BPM = 60.0 / (2.2 / 4)          # 109.09: one bar per pipeline gate (2.2 s)
BEAT = 60.0 / BPM
S = lambda sid, t: START[sid] + t   # scene-relative -> absolute seconds

BUS = {k: np.zeros((2, N), np.float32) for k in ["pad", "keys", "arp", "bass", "drums", "fx", "ui", "big", "dry"]}


def mf(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def place(bus, x, t0, gain=1.0, pan=0.0):
    if x.ndim == 1:
        a = (pan + 1) * math.pi / 4
        x = np.stack([x * math.cos(a), x * math.sin(a)])
    i0 = int(round(t0 * SR))
    if i0 >= N:
        return
    if i0 < 0:
        x = x[:, -i0:]; i0 = 0
    n = min(x.shape[1], N - i0)
    BUS[bus][:, i0:i0 + n] += (x[:, :n] * gain).astype(np.float32)


# ---------------------------------------------------------------- oscillators & helpers
def saw(freq, n, ph0=0.0):
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (n,))
    dt = f / SR
    ph = (ph0 + np.cumsum(dt)) % 1.0
    y = 2.0 * ph - 1.0
    m = ph < dt
    x = ph[m] / dt[m]; y[m] -= (2 * x - x * x - 1)
    m = ph > 1 - dt
    x = (ph[m] - 1) / dt[m]; y[m] -= (x * x + 2 * x + 1)
    return y


def sine(freq, n, ph0=0.0):
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (n,))
    return np.sin(2 * np.pi * (np.cumsum(f) / SR + ph0))


def env(n, a=0.01, d=0.1, s=0.7, r=0.3, hold=None):
    """ADSR with release starting at `hold` seconds (default: n - r)."""
    t = np.arange(n) / SR
    hold = (n / SR - r) if hold is None else hold
    e = np.where(t < a, t / max(a, 1e-6), s + (1 - s) * np.exp(-(t - a) / max(d, 1e-6)))
    rel = np.clip((t - hold) / max(r, 1e-6), 0, 1)
    return e * (1 - rel) ** 2


def lp(x, fc, order=2):
    sos = signal.butter(order, min(fc, SR * 0.45), "low", fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=-1)


def hp(x, fc, order=2):
    sos = signal.butter(order, fc, "high", fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=-1)


def bp(x, f1, f2, order=2):
    sos = signal.butter(order, [f1, min(f2, SR * 0.45)], "band", fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=-1)


def lp_sweep(x, fc_fn, block=512):
    """time-varying 2nd-order lowpass; fc_fn(t_seconds_array)->Hz"""
    y = np.zeros_like(x)
    zi = np.zeros((1, 2))
    for i in range(0, len(x), block):
        tt = (i + block / 2) / SR
        fc = float(np.clip(fc_fn(tt), 30, SR * 0.45))
        sos = signal.butter(2, fc, "low", fs=SR, output="sos")
        y[i:i + block], zi = signal.sosfilt(sos, x[i:i + block], zi=zi)
    return y


def stereo(y, width=0.0, delay_ms=9.0):
    d = int(delay_ms * SR / 1000)
    r = np.concatenate([np.zeros(d), y[:-d]]) if d > 0 else y
    return np.stack([y, (1 - width) * y + width * r])


# ---------------------------------------------------------------- instruments
def pad(notes, dur, att=1.5, rel=2.5, cutoff=1800, voices=5, det=14, bright_fn=None, gain=0.08):
    n = int((dur + rel) * SR)
    out = np.zeros((2, n))
    for m in notes:
        f = mf(m)
        for v in range(voices):
            d = ((v - (voices - 1) / 2) / max((voices - 1) / 2, 1)) * det
            y = saw(f * 2 ** (d / 1200), n, rng.random())
            p = ((v / max(voices - 1, 1)) * 2 - 1) * 0.8
            a = (p + 1) * math.pi / 4
            out[0] += y * math.cos(a); out[1] += y * math.sin(a)
    if bright_fn is None:
        out = lp(out, cutoff)
    else:
        out = np.stack([lp_sweep(out[0], bright_fn), lp_sweep(out[1], bright_fn)])
    e = env(n, a=att, d=1.0, s=1.0, r=rel, hold=dur)
    return out * e * gain / max(len(notes), 1) ** 0.5


def sub(m, dur, att=0.8, rel=1.5, gain=0.25):
    n = int((dur + rel) * SR)
    f = mf(m)
    y = sine(f, n) + 0.25 * sine(2 * f, n) + 0.12 * lp(saw(f, n), 300)
    return y * env(n, a=att, d=1, s=1, r=rel, hold=dur) * gain


def keys(m, dur=3.5, vel=1.0, bright=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = mf(m)
    y = np.zeros(n)
    for r_, a, k in [(1, 1.0, 1.0), (2.001, 0.42, 1.6), (3.003, 0.2, 2.3), (4.008, 0.11, 3.1), (5.02, 0.05, 4.0), (6.04, 0.03, 5.2)]:
        if f * r_ > SR * 0.45:
            continue
        y += a * bright ** (r_ - 1) * np.sin(2 * np.pi * f * r_ * t + rng.random()) * np.exp(-t * k * (0.9 + 0.25 * (m - 60) / 12))
    click = hp(rng.standard_normal(n) * np.exp(-t * 400), 2000) * 0.05
    e = np.minimum(t / 0.004, 1) * np.clip((dur - t) / 0.3, 0, 1)
    return (y + click) * e * vel * 0.16


def pluck(m, dur=0.45, cutoff=3200, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = saw(mf(m), n, rng.random()) * 0.6 + 0.4 * saw(mf(m) * 1.003, n, rng.random())
    y = lp_sweep(y, lambda tt: 300 + cutoff * math.exp(-tt * 14))
    return y * np.exp(-t * 7) * np.minimum(t / 0.002, 1) * vel * 0.14


def kick(vel=1.0, dur=0.5):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 28)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)
    y += hp(rng.standard_normal(n) * np.exp(-t * 300), 1500) * 0.15
    return np.tanh(y * 1.4) * vel * 0.5


def hat(vel=1.0, dur=0.08, open_=False):
    n = int((0.35 if open_ else dur) * SR); t = np.arange(n) / SR
    y = hp(rng.standard_normal(n), 7500) * np.exp(-t * (12 if open_ else 60))
    return y * vel * 0.09


def tom(m=40, vel=1.0, dur=1.2):
    n = int(dur * SR); t = np.arange(n) / SR
    f = mf(m) * (1 + 0.6 * np.exp(-t * 20))
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.5) + lp(rng.standard_normal(n), 900) * np.exp(-t * 18) * 0.4
    return np.tanh(y * 1.5) * vel * 0.4


def impact(vel=1.0, dur=4.0):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 28 + 90 * np.exp(-t * 9)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.1)
    y += lp(rng.standard_normal(n), 2500) * np.exp(-t * 6) * 0.5
    y += hp(rng.standard_normal(n), 4000) * np.exp(-t * 14) * 0.2
    return np.tanh(y * 1.6) * vel * 0.55


def braam(root=26, dur=4.0, vel=1.0):
    n = int((dur + 1.5) * SR); t = np.arange(n) / SR
    y = np.zeros(n)
    for m, a in [(root, 1.0), (root + 12, 0.8), (root + 19, 0.5), (root + 24, 0.35)]:
        for d in (-9, 0, 9):
            y += a * saw(mf(m) * 2 ** (d / 1200), n, rng.random())
    y = lp_sweep(y, lambda tt: 120 + 2600 * (1 - math.exp(-tt * 9)) * math.exp(-tt * 1.3))
    y = np.tanh(y * 0.6)
    return y * env(n, a=0.04, d=0.8, s=0.7, r=1.5, hold=dur) * vel * 0.22


def bp_sweep(x, fc_fn, q=0.7, block=256):
    y = np.zeros_like(x)
    zi = np.zeros((2, 2))
    for i in range(0, len(x), block):
        c = float(np.clip(fc_fn((i + block / 2) / SR), 60, SR * 0.4))
        sos = signal.butter(2, [c * (1 - q * 0.5), min(c * (1 + q), SR * 0.45)], "band", fs=SR, output="sos")
        y[i:i + block], zi = signal.sosfilt(sos, x[i:i + block], zi=zi)
    return y


def riser(dur, f0=250, f1=7000, vel=1.0, pitch=True):
    n = int(dur * SR); t = np.arange(n) / SR; u = t / dur
    nz = rng.standard_normal(n)
    y = bp_sweep(nz, lambda tt: f0 * (f1 / f0) ** (tt / dur), q=0.7)
    if pitch:
        y += 0.25 * sine(110 * 2 ** (u * 3), n) + 0.15 * sine(165 * 2 ** (u * 3), n)
    return y * (u ** 2.2) * vel * 0.35


def whoosh(dur=1.0, vel=1.0, up=True):
    n = int(dur * SR); t = np.arange(n) / SR; u = t / dur
    nz = rng.standard_normal(n)
    fc_lo, fc_hi = (400, 5000) if up else (5000, 400)
    y = bp_sweep(nz, lambda tt: fc_lo * (fc_hi / fc_lo) ** (tt / dur), q=0.8)
    a = np.sin(np.pi * u) ** 1.5
    return stereo(y * a * vel * 0.4, 0.6, 12)


def rev_cymbal(dur=2.0, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR; u = t / dur
    y = hp(rng.standard_normal(n), 3500) * (u ** 3)
    return y * vel * 0.25


def shimmer(notes, dur, vel=1.0, att=1.2):
    n = int((dur + 2) * SR); t = np.arange(n) / SR
    y = np.zeros(n)
    for m in notes:
        for o, a in [(24, 1.0), (36, 0.4)]:
            f = mf(m + o)
            if f > SR * 0.42:
                continue
            y += a * np.sin(2 * np.pi * f * t + rng.random()) * (0.6 + 0.4 * np.sin(2 * np.pi * (3 + rng.random() * 3) * t))
    return y * env(n, a=att, d=1, s=1, r=2, hold=dur) * vel * 0.02 / max(len(notes), 1) ** 0.5


def blip(f=1800, dur=0.07, vel=1.0, chirp=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    fr = f * chirp ** (t / dur)
    return np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t * 55) * np.minimum(t / 0.001, 1) * vel * 0.12


def tick(vel=1.0):
    n = int(0.012 * SR); t = np.arange(n) / SR
    return hp(rng.standard_normal(n), 3000) * np.exp(-t * 600) * vel * 0.25


def glitch(dur=0.22, vel=1.0):
    n = int(dur * SR); y = np.zeros(n)
    i = 0
    while i < n:
        L = int(rng.uniform(0.008, 0.035) * SR)
        f = rng.uniform(180, 900)
        seg = np.sign(np.sin(2 * np.pi * f * np.arange(min(L, n - i)) / SR))
        y[i:i + L] = seg * rng.uniform(0.4, 1.0) * (rng.random() > 0.2)
        i += L
    y = np.round(y * 6) / 6
    y = lp(y, 4500)
    t = np.arange(n) / SR
    return y * np.exp(-t * 6) * vel * 0.09


def chime(m, vel=1.0):
    return keys(m + 24, dur=3.0, vel=vel * 0.9, bright=0.6)


# ---------------------------------------------------------------- harmony
CH = {  # bass, pad voicing
    "Dm": (26, [50, 57, 60, 64, 65]), "Bb": (34, [53, 57, 58, 62]), "F": (29, [53, 57, 60, 64]),
    "C": (36, [55, 60, 62, 64]), "Gm": (31, [55, 58, 62, 65]), "A": (33, [57, 61, 64, 69]), "Asus": (33, [57, 62, 64, 69]),
    "Eb": (27, [55, 58, 62, 63]), "Dmaj": (26, [50, 57, 62, 66, 69]),
}


def chord_pad(name, t0, dur, cutoff=1500, gain=0.08, att=1.2, rel=2.0, bus="pad", bright_fn=None, sub_gain=0.18):
    b, v = CH[name]
    place(bus, pad(v, dur, att=att, rel=rel, cutoff=cutoff, gain=gain, bright_fn=bright_fn), t0)
    if sub_gain:
        place("bass", sub(b, dur, att=min(att, 0.6), rel=rel * 0.8, gain=sub_gain), t0)


def arp_bar(name, t0, bars=1, pattern=(0, 2, 1, 3, 2, 1, 3, 2), step=0.5, oct_=12, vel=1.0, cutoff=2600, pan_swing=0.4):
    _, v = CH[name]
    k = 0
    tt = t0
    while tt < t0 + bars * 4 * BEAT - 1e-6:
        m = v[pattern[k % len(pattern)] % len(v)] + oct_
        place("arp", pluck(m, 0.5, cutoff, vel * (0.85 + 0.3 * (k % 4 == 0))), tt, pan=pan_swing * math.sin(k * 1.3))
        k += 1; tt += step * BEAT


def drums(t0, t1, kick_every=1.0, hat_every=0.5, vel=1.0, open_hat_off=True, fill=False):
    tt = t0
    while tt < t1 - 1e-6:
        place("drums", kick(vel), tt)
        tt += kick_every * BEAT
    tt = t0
    k = 0
    while tt < t1 - 1e-6:
        if open_hat_off and k % 2 == 1:
            place("drums", hat(vel * 0.8, open_=True), tt, pan=0.2)
        else:
            place("drums", hat(vel * 0.6), tt, pan=-0.2)
        tt += hat_every * BEAT; k += 1


def duck_env(times, depth=0.55, rel=0.35):
    e = np.ones(N, np.float32)
    t = np.arange(int(rel * 3 * SR)) / SR
    shape = 1 - depth * np.exp(-t / rel * 2.2)
    for tt in times:
        i0 = int(tt * SR); n = min(len(shape), N - i0)
        if n > 0:
            e[i0:i0 + n] = np.minimum(e[i0:i0 + n], shape[:n])
    return e


KICKS = []


def drive(t0, t1, vel=1.0, hats=True):
    tt = t0
    while tt < t1 - 1e-6:
        KICKS.append(tt); place("drums", kick(vel), tt); tt += BEAT
    if hats:
        tt = t0 + BEAT / 2
        while tt < t1 - 1e-6:
            place("drums", hat(vel * 0.7, open_=True), tt, pan=0.15); tt += BEAT
        tt = t0
        while tt < t1 - 1e-6:
            place("drums", hat(vel * 0.35), tt + BEAT / 4, pan=-0.25); tt += BEAT / 2


# ================================================================== CUES
# ---- s01 open
a = S("s01_open", 0)
place("pad", stereo(sub(26, 13, att=3.0, rel=2.5, gain=0.16) + sub(33, 13, att=4, rel=2.5, gain=0.07), 0.3), a + 0.2)
place("fx", shimmer([69, 76, 81], 3.0, vel=1.2, att=0.8), a + 0.3)
place("fx", whoosh(2.2, 0.9), a + 1.4)
chord_pad("Dm", a + 3.0, 5.0, cutoff=900, gain=0.06, att=2.5, sub_gain=0)
chord_pad("Bb", a + 8.0, 4.6, cutoff=1000, gain=0.06, att=1.5, sub_gain=0)
for tt, m in [(3.8, 74), (4.7, 69), (5.6, 77), (7.0, 76), (8.6, 74), (9.4, 72), (10.3, 69), (11.6, 70)]:
    place("keys", keys(m, 4.0, 0.9), a + tt, pan=0.15 * math.sin(tt))
place("fx", rev_cymbal(1.6, 0.7), a + 12.4)

# ---- s02 scale: pulse emerges, filter opens; red verdict
a = S("s02_scale", 0)
prog = ["Dm", "Bb", "F", "C", "Dm", "Bb"]
for i, c in enumerate(prog):
    t0 = a + i * 4 * BEAT
    if t0 > a + 10.0:
        break
    open_ = lambda tt, i=i: 500 + 2200 * min((i * 2.2 + tt) / 10.0, 1)
    chord_pad(c, t0, 4 * BEAT, gain=0.07, att=0.6, rel=1.2, bright_fn=open_, sub_gain=0.12)
    arp_bar(c, t0, 1, step=0.5, vel=0.55 + 0.08 * i, cutoff=1500 + 400 * i)
for k, tt in enumerate([4.6, 5.1, 5.6]):
    place("ui", chime(72 + 3 * k, 0.6), a + tt)
# red scan: dissonant cluster + boom at verdict
place("pad", pad([50, 51, 57, 58], 6.0, att=0.4, rel=2.0, cutoff=1200, gain=0.09), a + 10.0)
place("fx", riser(1.3, 300, 3000, 0.6), a + 9.9)
place("big", impact(0.75), a + 11.2)
place("bass", sub(26, 4.0, att=0.02, rel=1.5, gain=0.2), a + 11.2)
place("fx", whoosh(1.2, 0.6, up=False), a + 15.0)

# ---- s03 anatomy: analysis pulse
a = S("s03_anatomy", 0)
place("big", tom(38, 0.6), a + 0.3)
prog = ["Dm", "Dm", "Bb", "Bb", "Gm", "Gm", "Asus", "A", "Dm", "Dm", "Bb", "Bb", "Gm", "A"]
for i, c in enumerate(prog):
    t0 = a + i * 4 * BEAT
    if t0 >= a + 29.5:
        break
    chord_pad(c, t0, 4 * BEAT, cutoff=900 + 200 * (i % 4), gain=0.055, att=0.8, rel=1.4, sub_gain=0.1)
tt = a + 1.0
while tt < a + 25.0:
    place("ui", tick(0.35 if int((tt - a) / (BEAT / 2)) % 2 else 0.55), tt, pan=0.3 * math.sin(tt))
    tt += BEAT / 2
tt = a + 4.4
while tt < a + 25.0:
    place("bass", sub(26, 0.25, att=0.005, rel=0.3, gain=0.18), tt); tt += 2 * BEAT
for k, tt in enumerate([4.4, 9.6, 14.8, 19.8]):
    place("fx", whoosh(0.9, 0.5), a + tt - 0.4)
    place("ui", blip(1400 + 300 * k, 0.12, 0.8, chirp=1.8), a + tt)
    place("keys", keys(62 + [0, 3, 5, 7][k], 3.0, 0.7), a + tt + 0.1)
# freeze at depth beat
place("fx", rev_cymbal(1.2, 0.4), a + 13.6)
# verdict
place("big", impact(0.6), a + 25.6)
chord_pad("Dm", a + 25.6, 4.0, cutoff=700, gain=0.07, att=0.05, rel=1.5, sub_gain=0.15)

# ---- s04 EEF: darker, heartbeat, red failure glitches
a = S("s04_eef", 0)
for i, c in enumerate(["Gm", "Eb", "Gm", "Eb", "Dm", "Bb", "Gm", "A", "A", "A", "A", "A"]):
    t0 = a + i * 4 * BEAT
    if t0 >= a + 25.5:
        break
    chord_pad(c, t0, 4 * BEAT, cutoff=700 + 120 * i, gain=0.055, att=0.6, rel=1.2, sub_gain=0.11)
tt = a + 0.5
while tt < a + 25:
    place("drums", kick(0.45), tt); place("drums", kick(0.3), tt + 0.28); tt += 2 * BEAT
place("fx", whoosh(2.4, 0.7, up=False), a + 7.2)
place("fx", shimmer([62, 69], 4.0, 0.8), a + 8.5)
for i in range(6):
    t0 = a + 14.2 + i * 1.45
    place("ui", glitch(0.25, 0.9), t0, pan=0.4 * (-1) ** i)
    place("bass", sub(25 + (i % 2), 0.4, att=0.005, rel=0.4, gain=0.14), t0)
place("fx", riser(6.0, 200, 4000, 0.5), a + 20.0)

# ---- s05 storm: escalate to a hard cut
a = S("s05_storm", 0)
place("fx", riser(9.7, 150, 9000, 1.1), a + 0.0)
place("pad", pad([38, 39, 45, 46, 50, 51], 9.6, att=3.0, rel=0.05, cutoff=1400, gain=0.12, bright_fn=lambda tt: 300 + 3000 * (tt / 9.6) ** 2), a + 0.05)
tt = a + 0.4; step = 2 * BEAT
while tt < a + 9.55:
    place("drums", tom(36, 0.5 + 0.5 * (tt - a) / 9.6), tt); tt += step; step = max(step * 0.88, BEAT / 4)
for k in range(30):
    place("ui", glitch(0.12, 0.6), a + 1.0 + k * 0.29 + rng.random() * 0.1, pan=rng.uniform(-0.8, 0.8))
CUT = a + 9.62

# ---- s06 title: silence, ignition, braam, hope
a = S("s06_title", 0)
place("fx", shimmer([62, 69, 74], 2.0, 1.6, att=1.5), a + 0.5)
place("fx", riser(2.15, 600, 9000, 0.6, pitch=True), a + 0.5)
place("fx", rev_cymbal(2.1, 0.9), a + 0.55)
place("big", impact(1.0), a + 2.65)
place("big", braam(26, 3.5, 1.0), a + 2.65)
chord_pad("Dm", a + 2.65, 3.0, cutoff=2200, gain=0.08, att=0.05, rel=2.0, sub_gain=0.2)
chord_pad("Bb", a + 5.5, 3.0, cutoff=2400, gain=0.08, att=1.0, rel=2.0, sub_gain=0.16)
chord_pad("F", a + 8.4, 4.5, cutoff=2600, gain=0.08, att=1.0, rel=2.0, sub_gain=0.16)
place("fx", shimmer([65, 69, 72, 77], 6.0, 1.3), a + 5.6)
for tt, m in [(5.7, 77), (6.4, 81), (7.2, 79), (8.5, 77), (9.6, 76), (10.4, 72)]:
    place("keys", keys(m, 3.5, 0.8), a + tt)
place("fx", riser(1.6, 300, 6000, 0.7), a + 11.4)
place("fx", whoosh(1.4, 0.8), a + 11.6)

# ---- s07 pipeline: drive at 109 BPM, one bar per gate
a = S("s07_pipeline", 0)
prog = ["Dm", "Bb", "F", "C"]
for i in range(11):
    t0 = a + 1.0 + i * 4 * BEAT
    c = prog[i % 4]
    chord_pad(c, t0, 4 * BEAT, cutoff=1800 + 100 * i, gain=0.06, att=0.3, rel=0.8, sub_gain=0)
    place("bass", sub(CH[c][0] + 12, 4 * BEAT - 0.1, att=0.01, rel=0.2, gain=0.14), t0)
    arp_bar(c, t0, 1, step=0.25, vel=0.5 + 0.03 * i, cutoff=2400, pattern=(0, 1, 2, 3, 2, 1, 3, 1))
drive(a + 1.0, a + 22.6, vel=0.85)
for i in range(8):
    tg = a + 4.03 + 2.2 * i
    place("fx", whoosh(0.7, 0.75), tg - 0.35)
    place("ui", chime(62 + [0, 2, 3, 5, 7, 8, 10, 12][i], 0.7), tg)
place("fx", riser(1.4, 400, 5000, 0.5), a + 22.6)

# ---- s08 agents: layered hero sequence
a = S("s08_agents", 0)
prog = ["Dm", "Bb", "F", "C"]
nb = int(58.0 / (4 * BEAT))
for i in range(nb):
    t0 = a + i * 4 * BEAT
    c = prog[i % 4]
    lvl = min(1.0, 0.45 + i * 0.03)
    chord_pad(c, t0, 4 * BEAT, cutoff=1300 + 60 * i, gain=0.055 * lvl, att=0.4, rel=1.0, sub_gain=0)
    if t0 >= a + 4.5:   # coordinator: bass
        place("bass", sub(CH[c][0] + 12, 4 * BEAT - 0.05, att=0.01, rel=0.2, gain=0.15), t0)
    if t0 >= a + 12.0:  # evidence: arp
        arp_bar(c, t0, 1, step=0.5, vel=0.5, cutoff=2200, pattern=(0, 2, 3, 1))
    if t0 >= a + 28.0:  # repair: 16th arp brighter
        arp_bar(c, t0, 1, step=0.25, vel=0.32, cutoff=3800, oct_=24, pattern=(3, 2, 1, 0, 1, 2))
drive(a + 4.5, a + 12.0, vel=0.5, hats=False)
drive(a + 12.0, a + 54.5, vel=0.8, hats=True)
for i in range(10):  # DAG nodes pop
    place("ui", pluck(74 + [0, 2, 3, 5, 7, 9, 10, 12, 14, 15][i], 0.4, 4000, 0.8), a + 5.2 + i * 0.22, pan=0.5 * math.sin(i))
place("fx", whoosh(3.6, 0.35), a + 12.6)  # evidence scan
for tt in [13.0, 14.0, 15.0, 16.2, 16.8]:
    place("ui", blip(2000, 0.06, 0.6), a + tt)
place("ui", blip(900, 0.18, 0.9, chirp=1.5), a + 15.0); place("ui", blip(1350, 0.18, 0.9, chirp=1.5), a + 15.25)  # gap alert
for k in range(150):  # base candidate tests
    place("ui", tick(0.25 + 0.2 * rng.random()), a + 21.2 + rng.random() * 2.6, pan=rng.uniform(-0.7, 0.7))
place("ui", chime(69, 0.9), a + 23.6); place("big", tom(38, 0.6), a + 23.6)
place("fx", shimmer([69, 72, 76, 81], 3.5, 1.5, att=0.6), a + 29.0)  # diffusion
place("drums", tom(45, 0.6), a + 33.0); place("ui", blip(600, 0.15, 0.8, chirp=0.5), a + 33.0)  # projection snap
for t0, ok in [(37.6 + 2.4 * 0.42, False), (40.2 + 2.4 * 0.6, False), (42.8 + 3.0 * 0.6, True)]:
    if ok:
        place("ui", chime(74, 1.0), a + t0); place("ui", chime(78, 0.8), a + t0 + 0.08); place("ui", chime(81, 0.8), a + t0 + 0.16)
    else:
        place("ui", glitch(0.3, 1.0), a + t0); place("big", tom(33, 0.7), a + t0)
for i, t0 in enumerate([46.4, 46.8, 47.2, 47.6, 48.0, 48.4]):
    place("ui", pluck(81 - i * 2, 0.6, 3000, 0.7), a + t0 + 0.9)
for i in range(5):  # hash read-back
    place("ui", blip(2400, 0.05, 0.7), a + 52.9 + i * 0.35)
place("fx", riser(1.6, 400, 7000, 0.7), a + 53.4)
place("big", impact(0.95), a + 55.0)
chord_pad("F", a + 55.0, 4.0, cutoff=3200, gain=0.09, att=0.05, rel=2.5, sub_gain=0.2)
place("fx", shimmer([65, 69, 72, 77], 4.0, 1.5, att=0.2), a + 55.0)
# packets
for t0 in [9.2, 15.6, 17.2, 19.4, 25.4, 27.6, 35.6, 44.6, 50.8]:
    place("ui", blip(1600, 0.09, 0.55, chirp=2.0), a + t0, pan=rng.uniform(-0.5, 0.5))

# ---- s09 review: reflective
a = S("s09_review", 0)
for i, c in enumerate(["Bb", "F", "Gm", "Dm", "Bb", "F", "Gm", "A", "Bb", "F", "C", "Dm"]):
    t0 = a + i * 2.2
    if t0 > a + 25:
        break
    chord_pad(c, t0, 2.2, cutoff=1100, gain=0.05, att=0.5, rel=1.4, sub_gain=0.08)
for tt, m in [(0.6, 74), (1.6, 72), (2.6, 69), (4.4, 70), (6.6, 72), (7.7, 69), (8.8, 65), (11.0, 67), (13.2, 69), (14.3, 70), (15.4, 72),
              (17.6, 74), (19.8, 77), (20.9, 76), (22.0, 74), (24.2, 72)]:
    place("keys", keys(m, 3.5, 0.75), a + tt, pan=0.2 * math.sin(tt))
for k in range(9):
    place("ui", blip(1800 + 40 * k, 0.05, 0.4), a + 8.0 + k * 0.07)
for k in range(60):
    place("ui", tick(0.18), a + 19.8 + k * 0.06, pan=-0.6 + k / 50)

# ---- s10 result: building
a = S("s10_result", 0)
for i, c in enumerate(["Dm", "Bb", "F", "C", "Dm", "Bb", "F", "C", "Gm", "Gm", "Asus", "A"]):
    t0 = a + i * 4 * BEAT
    if t0 > a + 25.5:
        break
    chord_pad(c, t0, 4 * BEAT, cutoff=1500 + 120 * i, gain=0.06, att=0.4, rel=1.2, sub_gain=0.14)
    if i < 8:
        arp_bar(c, t0, 1, step=0.5, vel=0.45, cutoff=2400, pattern=(0, 2, 1, 3))
place("fx", shimmer([62, 69, 74, 77], 4.0, 1.6, att=0.4), a + 2.4)
place("fx", whoosh(4.0, 0.6), a + 2.4)
place("big", tom(41, 0.6), a + 8.6); place("ui", chime(69, 0.8), a + 10.4)
drive(a + 8.8, a + 17.4, vel=0.6, hats=True)
place("big", impact(0.6), a + 17.6)
for k in range(25):
    place("ui", tick(0.3), a + 17.6 + k / 3.2)

# ---- s11 ladder: confidence
a = S("s11_ladder", 0)
for i, c in enumerate(["Bb", "C", "Dm", "F", "Bb", "C", "Dm", "Dm"]):
    t0 = a + i * 2.2
    if t0 > a + 15:
        break
    chord_pad(c, t0, 2.2, cutoff=1800 + 150 * i, gain=0.06, att=0.3, rel=1.4, sub_gain=0.14)
drive(a + 0.0, a + 15.4, vel=0.55, hats=True)
for i in range(5):
    place("ui", chime(69 + [0, 2, 3, 5, 7][i], 0.75), a + 1.0 + i * 0.55)
place("fx", riser(2.6, 300, 4000, 0.4, pitch=True), a + 8.1)
place("big", tom(38, 0.8), a + 10.6); place("ui", chime(81, 0.9), a + 10.6)

# ---- s12 studio: warm
a = S("s12_studio", 0)
for i, c in enumerate(["Bb", "F", "C", "Dm", "Bb", "C"]):
    t0 = a + i * 2.2
    chord_pad(c, t0, 2.2, cutoff=2200, gain=0.06, att=0.3, rel=1.4, sub_gain=0.12)
    arp_bar(c, t0, 1, step=0.25, vel=0.35, cutoff=3000, oct_=24, pattern=(0, 1, 2, 3))
drive(a + 0.0, a + 11.0, vel=0.5, hats=True)
for i in range(3):
    place("fx", whoosh(0.9, 0.4), a + 0.2 + i * 0.25)

# ---- s13 finale
a = S("s13_finale", 0)
place("fx", shimmer([62, 69, 74], 2.5, 1.6, att=1.0), a + 0.3)
place("fx", riser(5.2, 200, 7000, 0.7, pitch=True), a + 0.2)
chord_pad("Bb", a + 0.5, 2.6, cutoff=1200, gain=0.06, att=1.5, rel=1.5, sub_gain=0.12)
chord_pad("C", a + 3.1, 2.3, cutoff=1600, gain=0.07, att=0.8, rel=1.5, sub_gain=0.14)
place("fx", rev_cymbal(2.4, 1.0), a + 3.25)
place("big", impact(1.0), a + 5.65)
place("big", braam(29, 3.0, 0.8), a + 5.65)
chord_pad("F", a + 5.65, 4.0, cutoff=3200, gain=0.09, att=0.05, rel=2.0, sub_gain=0.2)
place("fx", shimmer([65, 69, 72, 77, 81], 9.0, 1.6, att=0.4), a + 5.65)
for tt, m in [(6.2, 77), (6.9, 81), (7.6, 84), (8.8, 81), (9.7, 79)]:
    place("keys", keys(m, 4.0, 0.8), a + tt)
chord_pad("Bb", a + 9.7, 1.6, cutoff=2600, gain=0.07, att=0.4, rel=1.2, sub_gain=0.15)
place("big", tom(41, 0.7), a + 10.4)
chord_pad("F", a + 10.4, 4.4, cutoff=2400, gain=0.085, att=0.6, rel=3.0, sub_gain=0.18)
place("keys", keys(65, 6.0, 0.8), a + 10.5); place("keys", keys(72, 6.0, 0.6), a + 10.55); place("keys", keys(77, 6.0, 0.6), a + 10.6)

# ================================================================== MIX
duck = duck_env(KICKS, depth=0.45, rel=0.18)
BUS["pad"] *= duck; BUS["arp"] *= (0.5 + 0.5 * duck); BUS["bass"] *= duck

def fx(board, x):
    return board(x.astype(np.float32), SR)

mix = np.zeros((2, N), np.float32)
mix += fx(Pedalboard([Reverb(room_size=0.88, damping=0.45, wet_level=0.38, dry_level=0.72, width=1.0)]), BUS["pad"])
mix += fx(Pedalboard([Chorus(rate_hz=0.4, depth=0.15, mix=0.25), Reverb(room_size=0.75, damping=0.5, wet_level=0.3, dry_level=0.8)]), BUS["keys"])
mix += fx(Pedalboard([Delay(delay_seconds=BEAT * 0.75, feedback=0.32, mix=0.22), Reverb(room_size=0.6, wet_level=0.2, dry_level=0.85)]), BUS["arp"])
mix += fx(Pedalboard([LowpassFilter(cutoff_frequency_hz=900)]), BUS["bass"])
mix += fx(Pedalboard([Compressor(threshold_db=-14, ratio=3, attack_ms=5, release_ms=80), Reverb(room_size=0.3, wet_level=0.08, dry_level=0.95)]), BUS["drums"])
mix += fx(Pedalboard([Reverb(room_size=0.95, damping=0.3, wet_level=0.45, dry_level=0.7, width=1.0)]), BUS["fx"])
mix += fx(Pedalboard([Reverb(room_size=0.5, damping=0.5, wet_level=0.22, dry_level=0.85)]), BUS["ui"])
mix += fx(Pedalboard([Reverb(room_size=0.97, damping=0.25, wet_level=0.5, dry_level=0.8, width=1.0)]), BUS["big"])
mix += BUS["dry"]

# hard cut into silence before the title ignition
i0, i1 = int(CUT * SR), int((S("s06_title", 0) + 0.45) * SR)
ramp = int(0.012 * SR)
mix[:, i0:i0 + ramp] *= np.linspace(1, 0, ramp)
mix[:, i0 + ramp:i1] = 0

# section dynamics (dB) — keyframes on absolute time; the score breathes with the edit
DYN = [(0, -12), (S("s01_open", 3), -9), (S("s01_open", 12), -7), (S("s02_scale", 0), -5), (S("s02_scale", 11), -2), (S("s03_anatomy", 0), -6), (S("s03_anatomy", 25), -4),
       (S("s04_eef", 0), -6), (S("s04_eef", 20), -4), (S("s05_storm", 0), -4), (S("s05_storm", 9.5), 1.5), (S("s06_title", 2.5), 0), (S("s06_title", 6), -2),
       (S("s07_pipeline", 0), -3), (S("s08_agents", 0), -4), (S("s08_agents", 50), -2), (S("s08_agents", 55.5), 0), (S("s08_agents", 59), -4),
       (S("s09_review", 0), -7), (S("s09_review", 25), -6), (S("s10_result", 0), -5), (S("s10_result", 16), -2), (S("s11_ladder", 0), -3),
       (S("s12_studio", 0), -3), (S("s13_finale", 0), -4), (S("s13_finale", 5.6), 1), (S("s13_finale", 12), -1), (TOTAL, -3)]
tk = np.array([d[0] for d in DYN]); gk = np.array([d[1] for d in DYN])
g = 10 ** (np.interp(np.arange(N) / SR, tk, gk) / 20)
mix *= g.astype(np.float32)
master = Pedalboard([HighpassFilter(cutoff_frequency_hz=28), LowShelfFilter(cutoff_frequency_hz=90, gain_db=-3.0), PeakFilter(cutoff_frequency_hz=2800, gain_db=2.5, q=0.7), HighShelfFilter(cutoff_frequency_hz=7000, gain_db=2.0), Compressor(threshold_db=-16, ratio=1.6, attack_ms=30, release_ms=300),
                     Limiter(threshold_db=-1.0, release_ms=150)])
import pyloudnorm as pyln
meter = pyln.Meter(SR)
pre = master(mix.astype(np.float32), SR)
lufs = meter.integrated_loudness(pre.T[: int(TOTAL * SR)])
mix *= 10 ** ((-16.0 - lufs) / 20)
out = master(mix.astype(np.float32), SR)
out *= (10 ** (-1.3 / 20)) / max(float(np.max(np.abs(out))), 1e-9)  # true-peak safety margin for AAC
# fade the very end
L = int((TOTAL) * SR)
out = out[:, :L]
fo = int(1.2 * SR)
out[:, -fo:] *= np.linspace(1, 0, fo) ** 2
import soundfile as sf
sf.write(sys.argv[2], out.T, SR, subtype="PCM_24")
pk = float(np.max(np.abs(out)))
print(f"wrote {sys.argv[2]}  {TOTAL:.1f}s  peak {20*math.log10(pk):.2f} dBFS  rms {20*math.log10(float(np.sqrt(np.mean(out**2)))):.2f} dBFS")
