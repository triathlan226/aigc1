"""合成背景音樂與音效（純 numpy，無外部素材，無版權問題）。"""
import numpy as np, wave
from timeline import DUR, MILESTONE_TIMES, FOLD_TIMES, HIT_TIME, RISER_START

SR = 44100
N = int(DUR * SR)
rng = np.random.default_rng(7)


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def add(buf, start, sig):
    i = int(start * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i]


def lowpass(x, k):
    ker = np.hanning(k)
    return np.convolve(x, ker / ker.sum(), mode="same")


def gain_curve(pts):
    t = np.arange(N) / SR
    xs, ys = zip(*pts)
    return np.interp(t, xs, ys)


BAR = 2.4  # 100 BPM, 4/4
PROG = [[60, 64, 67], [59, 62, 67], [57, 60, 64], [57, 60, 65]]  # C  G/B  Am  F/A
ROOTS = [36, 43, 45, 41]

pad = np.zeros(N); arp = np.zeros(N); bass = np.zeros(N)
kick = np.zeros(N); hat = np.zeros(N); sfx = np.zeros(N)

nbars = int(DUR / BAR) + 1
for b in range(nbars):
    t0 = b * BAR
    chord = PROG[b % 4]
    # pad
    L = BAR + 0.5
    tt = np.arange(int(L * SR)) / SR
    env = np.minimum(1, tt / 0.35) * np.minimum(1, (L - tt) / 0.5)
    for m in chord:
        f = mtof(m)
        s = np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 1.004 * tt) \
            + 0.2 * np.sin(2 * np.pi * 2 * f * tt)
        add(pad, t0, s * env / 3)
    # arp: 8 個八分音符
    seq = [chord[0], chord[1], chord[2], chord[0] + 12, chord[2], chord[1], chord[0] + 12, chord[2] + 12]
    for k, m in enumerate(seq):
        f = mtof(m + 12)
        tt = np.arange(int(0.45 * SR)) / SR
        s = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt)) * np.exp(-tt * 7)
        add(arp, t0 + k * 0.3, s)
    # bass + drums：每拍
    for q in range(4):
        tq = t0 + q * 0.6
        f = mtof(ROOTS[b % 4])
        tt = np.arange(int(0.55 * SR)) / SR
        s = (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * 2 * f * tt)) * np.exp(-tt * 4)
        add(bass, tq, s)
        tt = np.arange(int(0.35 * SR)) / SR
        ph = 2 * np.pi * np.cumsum(45 + 90 * np.exp(-tt * 30)) / SR
        add(kick, tq, np.sin(ph) * np.exp(-tt * 9))
        tt = np.arange(int(0.06 * SR)) / SR
        nz = np.diff(rng.standard_normal(len(tt) + 1))
        add(hat, tq + 0.3, nz * np.exp(-tt * 70))

# 里程碑「叮」
for tm in MILESTONE_TIMES:
    tt = np.arange(int(1.2 * SR)) / SR
    s = (np.sin(2 * np.pi * 1318.5 * tt) + 0.6 * np.sin(2 * np.pi * 1975.5 * tt)) * np.exp(-tt * 4)
    add(sfx, tm, s * 0.20)

# 折紙「咻」
for tf in FOLD_TIMES:
    L = 0.4
    tt = np.arange(int(L * SR)) / SR
    nz = lowpass(rng.standard_normal(len(tt)), 12)
    env = np.sin(np.pi * tt / L) ** 2
    add(sfx, tf, nz * env * 0.5)

# 1000 次前的上升音 + 爆點
L = HIT_TIME - RISER_START
tt = np.arange(int(L * SR)) / SR
p = tt / L
freq = 150 * 2 ** (p * 4)
riser = 0.5 * np.sin(2 * np.pi * np.cumsum(freq) / SR) + 0.6 * lowpass(rng.standard_normal(len(tt)), 6)
add(sfx, RISER_START, riser * p ** 2 * 0.45)
tt = np.arange(int(3.0 * SR)) / SR
boom = np.sin(2 * np.pi * np.cumsum(40 + 60 * np.exp(-tt * 6)) / SR) * np.exp(-tt * 1.6)
crash = lowpass(rng.standard_normal(len(tt)), 3) * np.exp(-tt * 1.8)
add(sfx, HIT_TIME, boom * 0.9 + crash * 0.35)

pad_g = gain_curve([(0, 0), (1.5, 0.8), (60, 0.8), (62, 0.5), (66, 1.0), (93, 1.0), (DUR, 0)])
arp_g = gain_curve([(0, 0.35), (6, 0.6), (18, 0.8), (60, 0.8), (61, 0.0), (66, 0.0), (67.5, 0.5),
                    (87, 0.6), (93, 0.6), (DUR, 0)])
drum_g = gain_curve([(0, 0), (17.9, 0), (18.2, 1), (59.6, 1), (60.1, 0), (88, 0), (88.5, 0.55),
                     (94, 0.55), (96, 0)])
bass_g = gain_curve([(0, 0), (5.8, 0), (6.5, 0.5), (18, 0.9), (59.6, 0.9), (60.1, 0), (66.2, 0),
                     (67, 0.6), (93, 0.6), (DUR, 0)])

mix = (pad * pad_g * 0.10 + arp * arp_g * 0.085 + bass * bass_g * 0.13
       + kick * drum_g * 0.38 + hat * drum_g * 0.035 + sfx)
right = mix.copy()
d = int(0.014 * SR)
right[d:] = 0.85 * mix[d:] + 0.15 * (pad * pad_g * 0.10)[:-d]
st = np.stack([mix, right], 1)
st = np.tanh(st / np.abs(st).max() * 1.3) * 0.85
fade = gain_curve([(0, 1), (DUR - 2.5, 1), (DUR, 0)])
st *= fade[:, None]

with wave.open("music.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype("<i2").tobytes())
print("music.wav", DUR, "s")
