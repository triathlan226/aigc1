"""Beat-synced background score, synthesized with numpy (no samples, no copyright).

synth(sections, bpm, out_path)
  sections: list of dicts {start, dur, type}  (type in hook/story/kinetic/logo)
All section boundaries should sit on the beat grid (multiples of 60/bpm).
"""
import numpy as np, wave
from scipy.signal import lfilter, butter

SR = 44100


def synth(sections, bpm, out_path, seed=3):
    rng = np.random.default_rng(seed)
    total = sections[-1]["start"] + sections[-1]["dur"]
    N = int(SR * total)
    L = np.zeros(N); R = np.zeros(N)
    beat = 60.0 / bpm; bar = beat * 4

    def mf(m): return 440.0 * 2 ** ((m - 69) / 12)
    def idx(t): return int(round(t * SR))
    def lp(x, fc): b, a = butter(2, fc / (SR / 2), 'low'); return lfilter(b, a, x)
    def hp(x, fc): b, a = butter(2, fc / (SR / 2), 'high'); return lfilter(b, a, x)
    def add(sig, t, gl=1.0, gr=1.0):
        i = idx(t)
        if i >= N or i < 0: return
        j = min(N, i + len(sig)); L[i:j] += sig[:j - i] * gl; R[i:j] += sig[:j - i] * gr
    def saw(f, n, ph=0.0):
        t = np.arange(n) / SR; return 2 * ((f * t + ph) % 1.0) - 1
    def kick(a=0.8):
        n = idx(0.45); t = np.arange(n) / SR
        ph = 2 * np.pi * np.cumsum(45 + 100 * np.exp(-t * 28)) / SR
        return a * np.sin(ph) * np.exp(-t * 7) * np.minimum(1, t * 800)
    def hat(a=0.09):
        n = idx(0.07); t = np.arange(n) / SR
        return a * hp(rng.standard_normal(n), 7500) * np.exp(-t * 65)
    def snare(a=0.2):
        n = idx(0.25); t = np.arange(n) / SR
        return a * (0.7 * hp(rng.standard_normal(n), 1800) * np.exp(-t * 20) + 0.4 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30))
    def impact(a=0.5, length=1.4):
        n = idx(length); t = np.arange(n) / SR
        nz = lp(rng.standard_normal(n), 2500) * np.exp(-t * 6) * 0.45
        sub = np.sin(2 * np.pi * np.cumsum(50 * np.exp(-t * 1.5) + 22) / SR) * np.exp(-t * 2.5)
        return a * (nz + sub)
    def click(a=0.1, f=2000):
        n = idx(0.03); t = np.arange(n) / SR
        return a * np.sin(2 * np.pi * f * t) * np.exp(-t * 180)
    def riser(t0, t1, a=0.2):
        if t1 - t0 <= 0.05: return
        n = idx(t1 - t0); x = rng.standard_normal(n); env = np.linspace(0, 1, n) ** 2
        add(a * ((1 - env) * lp(x, 700) + env * hp(x, 3000)) * env, t0, 0.85, 1.0)

    hook = next((s for s in sections if s["type"] == "hook"), None)
    logo = next((s for s in sections if s["type"] == "logo"), None)
    groove_start = sections[1]["start"] if hook and len(sections) > 1 else 0.0
    groove_end = logo["start"] if logo else total

    # hook: accelerating ticks while number rolls, big hit on landing
    if hook:
        land = hook["start"] + 2.0  # matches render.sc_hook landing
        riser(hook["start"], land, 0.18)
        ts = hook["start"] + 0.2; k = 0
        while ts < land - 0.05 and k < 40:
            add(click(0.10, 1800 + 60 * k), ts); ts += 0.13 * (0.93 ** k); k += 1
        add(impact(0.9, 1.6), land)
    # section hits + short risers
    for i, s in enumerate(sections):
        if s["type"] == "hook": continue
        big = s["type"] == "logo" or i == 1
        add(impact(0.7 if big else 0.45), s["start"])
        if i > 1: riser(max(0, s["start"] - 0.9), s["start"], 0.12)
    # groove (half-time)
    t = groove_start; k = 0
    kin = [(s["start"], s["start"] + s["dur"]) for s in sections if s["type"] == "kinetic"]
    while t < groove_end - 1e-6:
        b = k % 4
        if b in (0, 2): add(kick(0.75 if b == 0 else 0.55), t)
        if b in (1, 3): add(snare(0.18), t, 1.0, 0.85)
        add(hat(), t + beat / 2, 0.7, 1.0)
        if any(a <= t < z for a, z in kin):
            for s_ in (0.25, 0.75): add(hat(0.06), t + beat * s_, 1.0, 0.6)
        t += beat; k += 1
    # harmony
    prog = [(45, [57, 60, 64, 67]), (41, [53, 57, 60, 64]), (36, [48, 55, 60, 62, 64]), (43, [55, 59, 62, 67])]
    mid_a = groove_start + (groove_end - groove_start) * 0.4
    t0 = 0.0; bi = 0
    while t0 < groove_end - 1e-6:
        root, notes = prog[bi % 4]
        b = min(t0 + bar, groove_end)
        n = idx(b - t0) + idx(0.25); tt = np.arange(n) / SR
        env = np.minimum(1, tt / (1.2 if t0 == 0 else 0.08)) * np.clip((b - t0 + 0.25 - tt) / 0.25, 0, 1)
        pl = np.zeros(n); pr = np.zeros(n)
        for m in notes:
            f = mf(m); pl += saw(f * .997, n, .1) + saw(f * 1.004, n, .6); pr += saw(f * 1.003, n, .3) + saw(f * .995, n, .8)
        cut = 900 if t0 < groove_start else 1500
        add(lp(pl, cut) * env * 0.028, t0, 1, 0); add(lp(pr, cut) * env * 0.028, t0, 0, 1)
        if t0 >= groove_start - 1e-6:
            tb = t0
            while tb < b - 1e-6:
                bn = idx(beat * 0.47); bt = np.arange(bn) / SR
                s = lp(saw(mf(root), bn), 450) * np.exp(-bt * 8) * 0.22 + np.sin(2 * np.pi * mf(root) * bt) * np.exp(-bt * 5) * 0.22
                add(s, tb); tb += beat / 2
        if mid_a <= t0:
            arp = notes + [notes[1] + 12]; tb = t0; j = 0
            while tb < b - 1e-6:
                f = mf(arp[j % len(arp)] + 12); pn = idx(0.35); pt = np.arange(pn) / SR
                s = (np.sin(2 * np.pi * f * pt) + 0.3 * np.sin(4 * np.pi * f * pt)) * np.exp(-pt * 12) * 0.06
                pan = 0.5 + 0.4 * np.sin(j); add(s, tb, 1.3 - pan, 0.3 + pan); j += 1; tb += beat / 4
        t0 += bar; bi += 1
    # ending chord + bells
    if logo:
        e0 = logo["start"]; n = idx(logo["dur"]); tt = np.arange(n) / SR
        env = np.minimum(1, tt / 0.05) * np.exp(-tt * 0.6)
        pl = np.zeros(n); pr = np.zeros(n)
        for m in [48, 55, 59, 62, 64, 71]:
            f = mf(m); pl += saw(f * .997, n, .1) + saw(f * 1.004, n, .6); pr += saw(f * 1.003, n, .3) + saw(f * .995, n, .8)
        add(lp(pl, 1600) * env * 0.03, e0, 1, 0); add(lp(pr, 1600) * env * 0.03, e0, 0, 1)
        add(kick(0.9), e0)
        for k, m in enumerate([76, 79, 83, 86]):
            f = mf(m); pn = idx(2.4); pt = np.arange(pn) / SR
            s = (np.sin(2 * np.pi * f * pt) + 0.25 * np.sin(2 * np.pi * f * 2.76 * pt) * np.exp(-pt * 4)) * np.exp(-pt * 1.8) * 0.1
            add(s, e0 + 0.6 + k * 0.3, 1 - k * 0.2, 0.4 + k * 0.2)
    fade = np.ones(N); fs = idx(max(0, total - 1.2)); fade[fs:] = np.linspace(1, 0, N - fs) ** 1.5
    L *= fade; R *= fade
    pk = max(np.abs(L).max(), np.abs(R).max(), 1e-9)
    L = np.tanh(1.2 * L / pk) / np.tanh(1.2) * 0.85; R = np.tanh(1.2 * R / pk) / np.tanh(1.2) * 0.85
    with wave.open(out_path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.stack([L, R], 1) * 32767).astype('<i2').tobytes())
    return total
