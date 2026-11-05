# 配樂（五聲音階撥弦，類古箏）＋音效＋人聲，輸出 mix.wav 與 subs.srt
import json, numpy as np, wave
from sil import load
SR = 24000
d = json.load(open("timeline.json")); tl = d["tl"]; total = d["total"]
N = int(total * SR) + SR
voice = np.zeros(N)
for s in tl:
    x = load(f"aud2/{s['id']}.wav") / 32768; i = int((s["t0"] + 0.25) * SR); voice[i:i + len(x)] += x
nt = lambda m: 440 * 2 ** ((m - 69) / 12)
rng = np.random.default_rng(7); music = np.zeros(N)
bpm = 72; beat = 60 / bpm
scale = [62, 64, 66, 69, 71, 74, 76, 78, 81]  # D 宮五聲
roots = [50, 47, 43, 45]  # D Bm G A
def pluck(t0, m, v):
    i = int(t0 * SR); L = int(1.6 * SR)
    if i + L >= N: return
    tp = np.arange(L) / SR; f = nt(m)
    y = (np.sin(2 * np.pi * f * tp) + .35 * np.sin(4 * np.pi * f * tp) + .12 * np.sin(6 * np.pi * f * tp)) * np.exp(-tp * 3.2)
    y *= np.minimum(1, tp / .004)
    music[i:i + L] += v * y
bar = beat * 4; b = 0
while b * bar < total:
    r = roots[b % 4]; s0 = int(b * bar * SR); L = int(bar * SR)
    if s0 + L < N:
        tp = np.arange(L) / SR
        music[s0:s0 + L] += .10 * (np.sin(2 * np.pi * nt(r) * tp) + .5 * np.sin(2 * np.pi * nt(r + 7) * tp)) * np.minimum(1, tp / .5) * np.minimum(1, (bar - tp) / .6)
    for k in range(8):
        if rng.random() < .72: pluck(b * bar + k * beat / 2, scale[rng.integers(0, len(scale))], .07 + .03 * rng.random())
    b += 1
e = np.convolve(np.abs(voice), np.ones(SR // 5) / (SR // 5), 'same')
duck = np.convolve(np.where(e > .01, .35, 1.), np.ones(SR // 4) / (SR // 4), 'same')
music *= duck * .6
fi = int(1.5 * SR); music[:fi] *= np.linspace(0, 1, fi)
end = int(total * SR); fo = int(3 * SR); music[end - fo:end] *= np.linspace(1, 0, fo); music[end:] = 0
sfx = np.zeros(N)
def gong(t0, f=220, v=.22):
    i = int(t0 * SR); L = int(2 * SR); tp = np.arange(L) / SR
    sfx[i:i + L] += v * sum(np.sin(2 * np.pi * f * h * tp) * np.exp(-tp * (1.5 + h)) / h for h in (1, 2.4, 3.9))
def wood(t0, v=.3):
    i = int(t0 * SR); L = int(.12 * SR); tp = np.arange(L) / SR
    sfx[i:i + L] += v * np.sin(2 * np.pi * 900 * tp) * np.exp(-tp * 45)
S = {s["id"]: s for s in tl}
g = lambda sid, k, o=0: S[sid]["t0"] + S[sid]["seg"][k] + o
for s in tl: wood(s["t0"] + .05)
gong(g("hook", 4)); gong(g("bg", 3), 160); gong(g("m4", 5), 180); gong(g("end_war", 4), 220)
for sid in ("m1", "m2", "m3", "m4"): wood(S[sid]["t0"] + .3, .4)
mixd = voice + music + sfx
mixd = mixd[:int((total + .2) * SR)]; mixd /= max(1, np.abs(mixd).max() / .95)
with wave.open("mix.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mixd * 32767).astype(np.int16).tobytes())
def ts(x): return f"{int(x//3600):02}:{int(x%3600//60):02}:{int(x%60):02},{int((x%1)*1000):03}"
out = []; n = 1
for s in tl:
    for k, sub in enumerate(s["subs"]):
        a = s["t0"] + s["seg"][k]; b2 = s["t0"] + (s["segend"][k] if k < len(s["subs"]) - 1 else s["len"] - .3)
        out.append(f"{n}\n{ts(a)} --> {ts(b2)}\n{sub}\n"); n += 1
open("subs.srt", "w").write("\n".join(out)); print("mix ok", round(total, 1))
