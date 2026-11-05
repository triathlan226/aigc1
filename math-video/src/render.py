import math, json, sys, subprocess, os, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from script import SCENES
from sil import load, runs

W, H, FPS = 1920, 1080, 30
D = os.path.dirname(os.path.abspath(__file__))
FONTS = {k: f"{D}/NotoSansCJKtc-{v}.otf" for k, v in dict(R="Regular", B="Bold", K="Black").items()}
_fc = {}
def font(sz, w="B"):
    k = (sz, w)
    if k not in _fc: _fc[k] = ImageFont.truetype(FONTS[w], sz)
    return _fc[k]

# ---------- palette ----------
BG1, BG2 = (14, 25, 48), (28, 44, 82)
Y = (255, 201, 60); C = (255, 107, 107); M = (78, 205, 196); WH = (245, 247, 250)
G = (138, 152, 178); P = (167, 139, 250); DK = (10, 18, 36); BGC = (21, 34, 64)

def mix(a, b, t): return tuple(int(a[i] * t + b[i] * (1 - t)) for i in range(3))
def clamp(x, a=0., b=1.): return max(a, min(b, x))
def eo(x): x = clamp(x); return 1 - (1 - x) ** 3
def eob(x):  # ease out back
    x = clamp(x); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2

# ---------- background ----------
def make_bg():
    g = np.linspace(0, 1, H)[:, None, None]
    arr = (np.array(BG1) * (1 - g) + np.array(BG2) * g) * np.ones((1, W, 1))
    yy, xx = np.mgrid[0:H, 0:W]
    v = np.exp(-(((xx - 1500) / 900) ** 2 + ((yy - 200) / 600) ** 2)) * 18
    arr = arr + v[..., None] * np.array([0.6, 0.7, 1.0])
    arr[(xx % 60 == 0) & (yy % 60 == 0)] += 28  # notebook dots
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
    return img
BG = None

# ---------- patch helpers ----------
_tc = {}
def tpatch(text, sz, col, w="B", stroke=0, scol=DK):
    k = (text, sz, col, w, stroke, scol)
    if k not in _tc:
        f = font(sz, w)
        bb = f.getbbox(text, stroke_width=stroke)
        im = Image.new("RGBA", (bb[2] - bb[0] + 4, bb[3] - bb[1] + 4), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((2 - bb[0], 2 - bb[1]), text, font=f, fill=col + (255,),
                                stroke_width=stroke, stroke_fill=scol + (255,))
        _tc[k] = im
    return _tc[k]

_ac = {}
def fx(p, alpha=1., scale=1., rot=0.):
    aq, sq, rq = round(alpha * 24) / 24, round(scale * 50) / 50, round(rot)
    if aq <= 0 or sq <= 0: return None
    k = (id(p), aq, sq, rq)
    if k in _ac: return _ac[k]
    q = p
    if sq != 1: q = q.resize((max(1, int(q.width * sq)), max(1, int(q.height * sq))), Image.BICUBIC)
    if rq: q = q.rotate(rq, Image.BICUBIC, expand=True)
    if aq < 1:
        q = q.copy(); a = q.getchannel("A").point([int(i * aq) for i in range(256)]); q.putalpha(a)
    if len(_ac) > 6000: _ac.clear()
    _ac[k] = q
    return q

def put(c, p, x, y, anc="mm", alpha=1., scale=1., rot=0.):
    q = fx(p, alpha, scale, rot)
    if q is None: return
    w, h = q.size
    x0 = int(x - (w / 2 if anc[0] == "m" else (w if anc[0] == "r" else 0)))
    y0 = int(y - (h / 2 if anc[1] == "m" else (h if anc[1] == "b" else 0)))
    sx, sy = max(0, -x0), max(0, -y0)
    ex, ey = min(w, W - x0), min(h, H - y0)
    if ex <= sx or ey <= sy: return
    if (sx, sy, ex, ey) != (0, 0, w, h): q = q.crop((sx, sy, ex, ey))
    c.alpha_composite(q, (x0 + sx, y0 + sy))

def text(c, s, x, y, sz=60, col=WH, w="B", anc="mm", alpha=1., scale=1., rot=0., stroke=0):
    put(c, tpatch(s, sz, col, w, stroke), x, y, anc, alpha, scale, rot)

_rc = {}
def rrect(w, h, r, fill, a=255, outline=None, ow=0):
    k = (w, h, r, fill, a, outline, ow)
    if k not in _rc:
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=fill + (a,) if fill else None,
                                             outline=(outline + (255,)) if outline else None, width=ow)
        _rc[k] = im
    return _rc[k]

def box(c, x, y, w, h, fill, a=255, r=24, alpha=1., scale=1., outline=None, ow=0, anc="mm"):
    put(c, rrect(int(w), int(h), r, fill, a, outline, ow), x, y, anc, alpha, scale)

_pc = {}
def person(col, s=60):
    k = (col, s)
    if k not in _pc:
        im = Image.new("RGBA", (s, int(s * 1.25)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.ellipse((s * .28, 0, s * .72, s * .44), fill=col + (255,))
        d.rounded_rectangle((s * .08, s * .52, s * .92, s * 1.25), int(s * .3), fill=col + (255,))
        _pc[k] = im
    return _pc[k]

def circ(r, col, a=255):
    k = ("c", r, col, a)
    if k not in _pc:
        im = Image.new("RGBA", (2 * r + 2, 2 * r + 2), (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse((1, 1, 2 * r, 2 * r), fill=col + (a,)); _pc[k] = im
    return _pc[k]

def frac(c, num, den, x, y, sz=72, col=WH, alpha=1., scale=1.):
    s = sz * scale
    pn = tpatch(num, sz, col); pd = tpatch(den, sz, col)
    wbar = max(pn.width, pd.width) + 16
    put(c, pn, x, y - sz * 0.62 * scale, alpha=alpha, scale=scale)
    put(c, pd, x, y + sz * 0.62 * scale, alpha=alpha, scale=scale)
    box(c, x, y, wbar * scale, max(3, int(sz * 0.07 * scale)), col, r=2, alpha=alpha)

def line(c, p0, p1, col, w=4, alpha=1.):
    ImageDraw.Draw(c).line([p0, p1], fill=mix(col, BGC, alpha) + (255,), width=w)

def boba(c, x, y, s=1., alpha=1.):
    k = ("boba",)
    if k not in _pc:
        im = Image.new("RGBA", (220, 300), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.line([(120, 0), (100, 120)], fill=C + (255,), width=16)
        d.polygon([(30, 70), (190, 70), (165, 290), (55, 290)], fill=(222, 184, 135, 255))
        d.polygon([(30, 70), (190, 70), (186, 100), (34, 100)], fill=(250, 245, 235, 255))
        for i in range(9):
            px = 72 + (i % 4) * 26 + (i // 4) * 8; py = 225 + (i // 4) * 22
            d.ellipse((px - 11, py - 11, px + 11, py + 11), fill=(60, 35, 25, 255))
        _pc[k] = im
    put(c, _pc[k], x, y, alpha=alpha, scale=s)

# ---------- timing ----------
TEMPO_DIR = f"{D}/aud2"
GAP = 0.35

def align(sid, segs):
    x = load(f"{TEMPO_DIR}/{sid}.wav"); dur = len(x) / 24000
    sil, _ = runs(x, th=300, minf=8)
    cands = [((a + b) / 2, b - a) for a, b in sil if a > 0.05 and b < dur - 0.05]
    lens = [max(1, len([ch for ch in s if ch.isalnum()])) for s, _ in segs]
    tot = sum(lens); cum = np.cumsum(lens)[:-1] / tot
    starts = [0.0]; last = 0.0; used = set()
    for f in cum:
        est = f * dur; best = None
        for i, (m, L) in enumerate(cands):
            if i in used or m <= last + 0.6: continue
            score = abs(m - est) - 0.8 * L
            if abs(m - est) < 1.8 and (best is None or score < best[0]): best = (score, i, m)
        if best: used.add(best[1]); last = best[2]
        else: last = max(est, last + 0.6)
        starts.append(last)
    if sid in OVR:
        for k,v in OVR[sid].items(): starts[k]=v
    return dur, starts
OVR={'exam':{1:2.1}}

def build_timeline():
    tl = []; t = 0.6
    for sid, segs, pad in SCENES:
        dur, st = align(sid, segs)
        sc_len = dur + pad + GAP
        tl.append(dict(id=sid, t0=t, audio=t + 0.25, adur=dur, len=sc_len + 0.25,
                       seg=[s + 0.25 for s in st], segend=[s + 0.25 for s in st[1:]] + [dur + 0.25],
                       subs=[d for _, d in segs]))
        t += sc_len + 0.25
    return tl, t + 0.4

# ---------- scene draws: f(c, t, S, L) ; S = list seg start times (local) ----------
def A(t, t0, d=0.45): return eo((t - t0) / d)

def people_grid(c, t, t0, cols=10, rows=3, cx=960, cy=560, sp=118, sz=70, hl=(), hlcol=C, alpha=1.):
    for i in range(cols * rows):
        r, k = divmod(i, cols)
        x = cx + (k - (cols - 1) / 2) * sp; y = cy + (r - (rows - 1) / 2) * sp * 1.25
        a = A(t, t0 + i * 0.035, 0.35) * alpha
        col = hlcol if i in hl else (M if (i * 7) % 3 else P)
        put(c, person(col, sz), x, y, alpha=a, scale=0.6 + 0.4 * eob(a / max(alpha, 1e-3)))

def sc_hook(c, t, S, L):
    a0 = A(t, 0.1)
    title = "全班 30 人" if t < S[2] else "有兩人同一天生日？"
    text(c, "全班 30 人", 960, 200, 96, WH, "K", alpha=a0 * (1 - A(t, S[2] - 0.3, 0.3)))
    if t >= S[2] - 0.3: text(c, "有兩人同一天生日？", 960, 200, 96, Y, "K", alpha=A(t, S[2] - 0.1, 0.35) * (1 - A(t, S[4] - .2, .3)), scale=0.9 + 0.1 * eob(A(t, S[2] - .1, .4)))
    ga = 1 - A(t, S[4] - 0.2, 0.4)
    hl = (3, 17) if t > S[2] else ()
    people_grid(c, t, 0.2, cx=860, hl=hl, alpha=ga)
    if t > S[2] and ga > 0:  # link arc between two highlighted
        a = A(t, S[2] + .3) * ga
        p0 = (860 + (3 - 4.5) * 118, 560 - 147); p1 = (860 + (7 - 4.5) * 118, 560 + 0)
        box(c, (p0[0] + p1[0]) / 2, 330, 300, 64, C, 255, 32, alpha=a)
        text(c, "同一天生日！", (p0[0] + p1[0]) / 2, 330, 38, WH, alpha=a)
    if t > S[1] - .2 and ga > 0:
        a = eob(A(t, S[1] - .2, .5)) * ga
        boba(c, 1650, 540, 0.9 * max(a, 0.01), alpha=min(1, a))
        text(c, "賭一杯珍奶", 1650, 740, 44, Y, alpha=min(1, a))
    if t > S[3] and ga > 0:
        a = A(t, S[3]) * ga
        text(c, "365 天", 640, 840, 64, M, "K", alpha=a); text(c, "vs", 860, 840, 44, G, alpha=a)
        text(c, "30 人", 1060, 840, 64, P, "K", alpha=a)
    if t > S[4] - .2:
        a = A(t, S[4] - .1, .5)
        text(c, "生日問題", 960, 420, 180, Y, "K", alpha=a, scale=0.8 + 0.2 * eob(A(t, S[4] - .1, .6)))
        box(c, 960, 560, 700 * eo(A(t, S[4] + .2, .5)) + 1, 10, C, r=5, alpha=a)
        text(c, "高一數學｜機率・餘事件", 960, 660, 56, WH, "B", alpha=A(t, S[4] + .4))
        text(c, "Birthday Problem", 960, 750, 40, G, "R", alpha=A(t, S[4] + .6))

def card(c, x, y, lab, val, col, a, hl=0.):
    box(c, x, y, 360, 300, mix(col, DK, 0.18 + 0.25 * hl), 255, 36, alpha=a, scale=0.85 + 0.15 * eob(a) + 0.06 * hl,
        outline=col if hl > 0.5 else None, ow=6)
    text(c, lab, x, y - 80, 48, col, "K", alpha=a)
    text(c, val, x, y + 30, 110, WH, "K", alpha=a)

def sc_guess(c, t, S, L):
    text(c, "直覺猜猜看：機率是多少？", 960, 170, 78, WH, "K", alpha=A(t, .1))
    hlA = A(t, S[2], .3)
    for i, (lab, v, col) in enumerate([("A", "≈ 8%", M), ("B", "≈ 30%", P), ("C", "≈ 70%", C)]):
        card(c, 560 + i * 400, 440, lab, v, col, A(t, .4 + i * .25), hl=hlA if i == 0 else 0)
    if t > S[1]:
        a = A(t, S[1]); text(c, "30 ÷ 365", 820, 760, 96, WH, "K", alpha=a)
        if t > S[2]: text(c, "≈ 8%", 1230, 760, 96, M, "K", alpha=A(t, S[2]))
    if t > S[3] + .6:
        a = A(t, S[3] + .6, .25)
        line(c, (600, 800), (1300, 720), C, 14, a)
        text(c, "錯很大！", 1480, 700, 110, C, "K", alpha=a, rot=-12, scale=1.6 - 0.6 * eo(A(t, S[3] + .6, .3)))

def sc_hard(c, t, S, L):
    a = A(t, .1)
    box(c, 960, 190, 880, 140, DK, 230, 30, alpha=a, outline=Y, ow=4)
    text(c, "至少兩人同一天生日", 960, 190, 72, WH, "K", alpha=a)
    if t > S[1]:
        aa = A(t, S[1], .3)
        put(c, rrect(175, 110, 50, None, 0, Y, 8), 708, 190, alpha=aa, scale=1.3 - .3 * eo(aa))
        text(c, "最麻煩！", 1520, 190, 48, Y, alpha=aa)
    cases = ["恰 1 組 2 人同天", "恰 2 組各 2 人", "3 人同天", "2 人 + 3 人同天", "4 人同天", "⋯⋯ 好多種"]
    shake = 0
    if t > S[3]: shake = math.sin(t * 40) * 8 * (1 - A(t, S[3] + .5, .6))
    gray = A(t, S[3], .5)
    for i, s in enumerate(cases):
        t0 = S[2] + i * (S[3] - S[2]) / 7
        if t < t0: continue
        aa = A(t, t0, .35); x = 520 + (i % 3) * 440 + shake; y = 430 + (i // 3) * 190
        line(c, (960, 262), (x, y - 60), G, 3, aa * (1 - gray * .6))
        col = mix(G, [M, P, C, Y, M, WH][i], gray * .7)
        box(c, x, y, 400, 130, mix(col, DK, .4), 255, 26, alpha=aa, scale=.8 + .2 * eob(aa))
        text(c, s, x, y, 46, mix(WH, G, 1 - gray * .6), alpha=aa)
    if t > S[3] + .3:
        aa = A(t, S[3] + .3, .3)
        text(c, "數到畢業都數不完！", 960, 860, 96, C, "K", alpha=aa, scale=1.4 - .4 * eo(aa), stroke=6)

def sc_comp(c, t, S, L):
    text(c, "主角登場：餘事件", 960, 150, 84, Y, "K", alpha=A(t, .1), scale=.8 + .2 * eob(A(t, .1, .5)))
    text(c, "complement", 960, 225, 36, G, "R", alpha=A(t, .3))
    if t > S[1]:
        aa = A(t, S[1]); box(c, 960, 300, 640, 70, DK, 200, 35, alpha=aa)
        text(c, "正面打不贏 → 繞到後面打", 960, 300, 42, WH, alpha=aa)
    if t > S[2] - .2:
        aa = A(t, S[2] - .2, .5); x0, x1, y0, y1 = 360, 1560, 380, 700
        box(c, 960, 540, 1200, 320, (40, 56, 96), 255, 20, alpha=aa)
        xa = x0 + 1200 * 0.706
        box(c, (x0 + xa) / 2, 540, xa - x0 - 8, 304, mix(C, DK, .55), 255, 16, alpha=aa)
        text(c, "A：至少兩人同天", (x0 + xa) / 2, 540, 54, WH, "K", alpha=aa)
        text(c, "樣本空間（所有可能）", 360, 350, 32, G, "R", anc="lm", alpha=aa)
        if t > S[3] - .1:
            ab = A(t, S[3] - .1, .4)
            box(c, (xa + x1) / 2, 540, x1 - xa - 8, 304, mix(M, DK, .5), 255, 16, alpha=ab, scale=.8 + .2 * eob(ab))
            text(c, "A′：全部", (xa + x1) / 2, 510, 46, WH, "K", alpha=ab)
            text(c, "不同天", (xa + x1) / 2, 570, 46, WH, "K", alpha=ab)
    if t > S[4]:
        aa = A(t, S[4], .5)
        box(c, 960, 840, 1100, 150, DK, 235, 30, alpha=aa, outline=Y, ow=4)
        text(c, "P(A) = 1 − P(A′)", 960, 840, 100, Y, "K", alpha=aa, scale=.9 + .1 * eob(aa))

def sc_calc(c, t, S, L):
    text(c, "P(全部不同天) = ?", 960, 150, 76, WH, "K", alpha=A(t, .1))
    xs = [380, 700, 1020, 1520]; nums = ["365", "364", "363", "336"]; who = ["1", "2", "3", "30"]
    notes = ["哪天都行", "避開 1 天", "避開 2 天", "避開 29 天"]; cols = [M, P, C, Y]
    for i in range(4):
        t0 = S[i + 1] - .15
        if t < t0: continue
        aa = A(t, t0, .45); slide = (1 - eo(aa)) * 120
        put(c, person(cols[i], 80), xs[i], 340 - slide * 0, alpha=aa, scale=.6 + .4 * eob(aa))
        text(c, f"第 {who[i]} 人", xs[i], 420, 34, cols[i], alpha=aa)
        frac(c, nums[i], "365", xs[i] + slide, 560, 76, WH, alpha=aa)
        text(c, notes[i], xs[i], 700, 38, G, alpha=aa)
        if i > 0:
            mx = (xs[i - 1] + xs[i]) / 2 if i < 3 else 1180
            text(c, "×", mx, 560, 70, G, alpha=aa)
        if i == 3:
            text(c, "⋯", 1290, 560, 80, G, alpha=aa); text(c, "×", 1395, 560, 70, G, alpha=aa)
    if t > S[5]:
        aa = A(t, S[5] + .2, .5)
        box(c, 960, 860, 760, 150, DK, 235, 30, alpha=aa, outline=M, ow=4)
        val = 0.294 * eo(A(t, S[5] + .2, 1.2))
        text(c, f"≈ {val:.3f}", 960, 860, 110, M, "K", alpha=aa)

def sc_result(c, t, S, L):
    text(c, "1 − 0.294 =", 960, 230, 96, WH, "K", alpha=A(t, .1))
    if t > S[1] - .1:
        aa = A(t, S[1] - .1, .3); v = 70.6 * eo(A(t, S[1], 1.6))
        text(c, f"{v:.1f}%", 960, 470, 230, Y, "K", alpha=aa, scale=.85 + .15 * eob(aa))
        text(c, "30 人至少兩人同一天生日", 960, 640, 48, WH, alpha=aa)
        bx0, bw = 360, 1200
        box(c, 960, 760, bw, 44, (45, 60, 100), 255, 22, alpha=aa)
        fw = int(bw * v / 100)
        if fw > 30: box(c, bx0 + fw / 2, 760, fw, 44, C, 255, 22, alpha=aa)
    if t > S[2]:
        aa = A(t, S[2]); x8 = 360 + 1200 * .08
        box(c, x8, 760, 8, 90, WH, 255, 3, alpha=aa)
        text(c, "直覺 8%", x8, 830, 38, WH, alpha=aa)
        text(c, "快 9 倍！", 1600, 640, 80, C, "K", alpha=A(t, S[2] + .5, .3), rot=10, scale=1.5 - .5 * eo(A(t, S[2] + .5, .3)), stroke=5)

def bp(n):
    q = 1.
    for i in range(int(n)): q *= (365 - i) / 365
    fr = n - int(n); q2 = q * (365 - int(n)) / 365
    return 1 - (q * (1 - fr) + q2 * fr)

def sc_chart(c, t, S, L):
    X0, X1, YB, YT = 300, 1680, 820, 170
    sx = lambda n: X0 + (X1 - X0) * n / 70; sy = lambda p: YB - (YB - YT) * p
    a = A(t, .05)
    for p in (0, .25, .5, .75, 1):
        line(c, (X0, sy(p)), (X1, sy(p)), (60, 78, 118) if p != .5 else Y, 2 if p != .5 else 3, a)
        text(c, f"{int(p*100)}%", X0 - 20, sy(p), 32, G, "R", anc="rm", alpha=a)
    for n in range(0, 71, 10): text(c, str(n), sx(n), YB + 34, 32, G, "R", alpha=a)
    text(c, "人數", X1 + 50, YB + 34, 32, G, "B", alpha=a)
    text(c, "至少兩人同天的機率", X0, YT - 50, 36, G, "B", anc="lm", alpha=a)
    keys = [(S[0] + .3, 0), (S[1] + .3, 23), (S[2] + .3, 50), (S[3] + .3, 70)]
    n = 0
    for (ta, na), (tb, nb) in zip(keys, keys[1:]):
        if t >= ta: n = na + (nb - na) * eo(clamp((t - ta) / (tb - ta)))
    n = min(70, n)
    if n > 0:
        pts = [(sx(k), sy(bp(k))) for k in np.linspace(0, n, max(2, int(n * 4)))]
        ImageDraw.Draw(c).line(pts, fill=C + (255,), width=8, joint="curve")
        put(c, circ(13, WH), pts[-1][0], pts[-1][1])
    marks = [(23, "23 人：50.7%", Y, -1), (30, "你們班 30 人：70.6%", M, 1), (50, "50 人：97.0%", P, 1), (70, "70 人：99.9%", C, 1)]
    for k, lab, col, side in marks:
        if n >= k - .01:
            aa = A(t, keys[[0, 23, 50, 70].index(k)][0] + .4 if k != 30 else keys[1][0] + .6, .4) if True else 1
            x, y = sx(k), sy(bp(k))
            put(c, circ(15, col), x, y, alpha=aa)
            line(c, (x, y), (x, YB), col, 2, aa * .7)
            if k == 23: text(c, lab, x + 30, y + 50, 40, col, "K", anc="lm", alpha=aa)
            elif k == 30: text(c, lab, x + 30, y + 60, 40, col, "K", anc="lm", alpha=aa)
            elif k == 50: text(c, lab, x, y - 50, 40, col, "K", alpha=aa)
            else: text(c, lab, x - 20, y + 60, 40, col, "K", anc="rm", alpha=aa)

def ring(cx, cy, r, n=30):
    return [(cx + r * math.cos(-math.pi / 2 + 2 * math.pi * i / n), cy + r * math.sin(-math.pi / 2 + 2 * math.pi * i / n)) for i in range(n)]

def sc_why(c, t, S, L):
    text(c, "為什麼直覺差這麼多？", 960, 130, 76, WH, "K", alpha=A(t, .1))
    L1 = ring(500, 520, 230); R1 = ring(1420, 520, 230)
    if t > S[1] - .2:
        aa = A(t, S[1] - .2)
        pr = clamp((t - S[1]) / 1.6)
        for i in range(1, int(29 * pr) + 1): line(c, L1[0], L1[i], Y, 3, aa * .8)
        for i, p in enumerate(L1): put(c, circ(16 if i else 22, Y if i == 0 else G), *p, alpha=aa)
        text(c, "我", L1[0][0], L1[0][1] - 52, 36, Y, "K", alpha=aa)
        text(c, "跟「我」同一天", 500, 830, 50, Y, "K", alpha=aa)
        text(c, "29 組", 500, 520, 64, WH, "K", alpha=A(t, S[1] + 1.6))
    if t > S[2]:
        aa = A(t, S[2]); box(c, 500, 920 - 0, 300, 0 + 1, DK, 0, 1)
        text(c, "≈ 7.6%", 500, 905, 64, WH, "K", alpha=aa)
    if t > S[3] - .2:
        aa = A(t, S[3] - .2)
        pairs = [(i, j) for i in range(30) for j in range(i + 1, 30)]
        pr = clamp((t - S[4]) / 2.8) if t > S[4] else 0
        m = int(len(pairs) * eo(pr))
        for (i, j) in pairs[:m]: line(c, R1[i], R1[j], C, 2, .55)
        for p in R1: put(c, circ(16, C if m else G), *p, alpha=aa)
        text(c, "「任意兩人」同一天", 1420, 830, 50, C, "K", alpha=aa)
        if t > S[4]:
            ab = A(t, S[4]); box(c, 1420, 520, 300, 120, DK, 220, 30, alpha=ab)
            text(c, f"{m} 組", 1420, 520, 72, WH, "K", alpha=ab)
            # C^30_2
            text(c, "C", 1330, 905, 70, Y, "K", alpha=ab); text(c, "30", 1372, 880, 34, Y, "K", alpha=ab)
            text(c, "2", 1366, 930, 34, Y, "K", alpha=ab); text(c, "= 435", 1500, 905, 70, Y, "K", alpha=ab)
    if t > S[5]:
        aa = A(t, S[5], .3)
        text(c, "機會多 15 倍！", 960, 520, 54, Y, "K", alpha=aa, scale=1.3 - .3 * eo(aa), stroke=6)

def alarm(c, t, a):
    fl = 0.75 + 0.25 * math.sin(t * 9)
    box(c, 960, 170, 1500, 130, mix(C, DK, .25 + .2 * fl), 255, 30, alpha=a)
    text(c, "看到「至少」→ 先想餘事件！", 960, 170, 70, WH, "K", alpha=a)

def quiz_card(c, a):
    box(c, 960, 400, 1500, 200, DK, 230, 30, alpha=a, outline=M, ow=4)
    text(c, "練習：公正硬幣丟 5 次，", 960, 360, 58, WH, "K", alpha=a)
    text(c, "至少出現 1 次正面的機率？", 960, 440, 58, Y, "K", alpha=a)

def sc_exam(c, t, S, L):
    if t < S[1]:
        aa = A(t, .05, .3)
        text(c, "考試重點！", 960, 450, 160, Y, "K", alpha=aa, scale=1.3 - .3 * eob(aa), stroke=8)
    else:
        alarm(c, t, A(t, S[1], .3))
    if t > S[2]: quiz_card(c, A(t, S[2]))
    if t > S[3] + .6:
        tc = t - (S[3] + .9); k = 3 - int(max(0, tc))
        if 1 <= k <= 3:
            fr = tc - int(max(0, tc)) if tc > 0 else 0
            put(c, circ(130, mix(Y, DK, .2)), 960, 720, alpha=1)
            text(c, str(k), 960, 715, 170, DK, "K", scale=1.25 - .25 * eo(fr / .3))

def sc_answer(c, t, S, L):
    alarm(c, t, 1); quiz_card(c, 1)
    if t > S[0]:
        aa = A(t, S[0]); text(c, "反面 A′ = 5 次全部反面", 960, 575, 56, M, "K", alpha=aa)
    if t > S[1]:
        aa = A(t, S[1])
        text(c, "P(A′) = (", 760, 700, 64, WH, "K", anc="rm", alpha=aa)
        frac(c, "1", "2", 805, 700, 52, WH, alpha=aa)
        text(c, ")", 850, 700, 64, WH, "K", anc="lm", alpha=aa); text(c, "5", 885, 650, 40, WH, "K", alpha=aa)
        text(c, "=", 950, 700, 64, WH, "K", alpha=aa); frac(c, "1", "32", 1030, 700, 52, M, alpha=aa)
    if t > S[2]:
        aa = A(t, S[2], .5)
        box(c, 960, 845, 1000, 135, DK, 235, 30, alpha=aa, outline=Y, ow=5)
        text(c, "P(A) = 1 −", 820, 845, 64, WH, "K", anc="rm", alpha=aa)
        frac(c, "1", "32", 880, 845, 48, WH, alpha=aa)
        text(c, "=", 960, 845, 64, WH, "K", alpha=aa)
        if t > S[2] + 1.2:
            ab = A(t, S[2] + 1.2, .35)
            frac(c, "31", "32", 1060, 845, 56, Y, alpha=ab, scale=1.2 - .2 * eob(ab))
            text(c, "≈ 96.9%", 1240, 845, 44, G, "B", anc="lm", alpha=ab)

def sc_end(c, t, S, L):
    aa = A(t, .1, .5)
    box(c, 960, 260, 1300, 230, DK, 230, 36, alpha=aa, outline=Y, ow=5)
    text(c, "正面難算，就算反面", 960, 225, 92, Y, "K", alpha=aa, scale=.9 + .1 * eob(aa))
    text(c, "P(A) = 1 − P(A′)　看到「至少」先想它", 960, 315, 40, WH, "B", alpha=A(t, .6))
    if t > S[1]:
        ab = A(t, S[1])
        box(c, 960, 560, 1300, 170, mix(M, DK, .3), 255, 30, alpha=ab)
        text(c, "回家功課", 380, 560, 50, Y, "K", anc="lm", alpha=ab)
        text(c, "明天全班報生日，看你們班有沒有人撞！", 640, 560, 46, WH, "B", anc="lm", alpha=ab)
    if t > S[2]:
        ab = A(t, S[2])
        text(c, "結果留言告訴我！", 960, 720, 54, WH, "K", alpha=ab)
        for i in range(10):
            bounce = abs(math.sin(t * 5 + i * .6)) * 18 * ab
            put(c, person([M, P, C, Y][i % 4], 52), 420 + i * 120, 850 - bounce, alpha=ab)
    if t > L - 1.6:
        text(c, "下次見！", 1600, 720, 70, Y, "K", alpha=A(t, L - 1.6, .3), rot=8)

DRAW = dict(hook=sc_hook, guess=sc_guess, hard=sc_hard, comp=sc_comp, calc=sc_calc, result=sc_result,
            chart=sc_chart, why=sc_why, exam=sc_exam, answer=sc_answer, end=sc_end)

def wrap(s, n=26):
    if len(s) <= n: return [s]
    best = None
    for i, ch in enumerate(s):
        if ch in "，、：；？！—→" and 6 < i < len(s) - 4:
            d = abs(i - len(s) / 2)
            if best is None or d < best[0]: best = (d, i)
    i = best[1] + 1 if best else len(s) // 2
    return [s[:i].strip(), s[i:].strip()]

def draw_subs(c, sc, lt):
    for k, (a, b) in enumerate(zip(sc["seg"], sc["segend"])):
        if a - .05 <= lt < b + .15 or (k == len(sc["seg"]) - 1 and a <= lt < sc["len"] - 0.3):
            lines = wrap(sc["subs"][k])
            al = min(A(lt, a - .05, .15), 1)
            h = 70 + 62 * (len(lines) - 1)
            yb = 1000 - (len(lines) - 1) * 31
            maxw = max(tpatch(l, 46, WH).width for l in lines)
            box(c, 960, 1000 - 0, maxw + 70, h + 10, (0, 0, 0), 150, 18, alpha=al, anc="mm")
            for j, l in enumerate(lines): text(c, l, 960, yb + j * 62, 46, WH, "B", alpha=al)
            break

def chrome(c, gt, total, sc):
    put(c, tpatch("高一數學｜機率・餘事件", 30, G, "B"), 50, 50, "lm")
    put(c, tpatch("生日問題", 30, Y, "K"), W - 50, 50, "rm")
    box(c, 0, H - 4, W, 8, (40, 55, 90), 255, 0, anc="lm")
    pw = int(W * gt / total)
    if pw > 2: box(c, 0, H - 4, pw, 8, Y, 255, 0, anc="lm")

def render_range(args):
    i0, i1, out, tl, total = args
    global BG
    BG = make_bg()
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                          "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for fi in range(i0, i1):
        gt = fi / FPS
        c = BG.copy()
        sc = None
        for s in tl:
            if s["t0"] <= gt < s["t0"] + s["len"]: sc = s
        if sc:
            lt = gt - sc["t0"]
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)) if False else c
            fade = min(A(lt, 0, .25), 1 - A(lt, sc["len"] - .2, .2)) if sc["id"] != "end" else A(lt, 0, .25)
            if fade < 1:
                tmp = BG.copy(); DRAW[sc["id"]](tmp, lt, sc["seg"], sc["len"])
                c = Image.blend(BG, tmp, fade)
            else:
                DRAW[sc["id"]](c, lt, sc["seg"], sc["len"])
            draw_subs(c, sc, lt)
        elif gt < 1:
            pass
        chrome(c, gt, total, sc)
        p.stdin.write(c.tobytes())
    p.stdin.close(); p.wait()
    return out

if __name__ == "__main__":
    tl, total = build_timeline()
    json.dump(dict(tl=tl, total=total), open(f"{D}/timeline.json", "w"), ensure_ascii=False, indent=1)
    print("total", round(total, 1))
    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    if mode == "preview":  # still frames
        global_ = None
        BG = make_bg()
        os.makedirs(f"{D}/prev", exist_ok=True)
        for s in tl:
            for k, frac_ in enumerate([0.3, 0.6, 0.97]):
                lt = s["len"] * frac_; c = BG.copy()
                DRAW[s["id"]](c, lt, s["seg"], s["len"]); draw_subs(c, s, lt); chrome(c, s["t0"] + lt, total, s)
                c.convert("RGB").resize((960, 540)).save(f"{D}/prev/{s['id']}_{k}.jpg", quality=85)
    else:
        from multiprocessing import Pool
        N = int(total * FPS); K = 8
        cuts = [N * i // K for i in range(K + 1)]
        jobs = [(cuts[i], cuts[i + 1], f"{D}/part{i}.mp4", tl, total) for i in range(K)]
        with Pool(4) as pool: parts = pool.map(render_range, jobs)
        open(f"{D}/parts.txt", "w").write("".join(f"file '{x}'\n" for x in parts))
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{D}/parts.txt", "-c", "copy", f"{D}/video.mp4"], check=True)
        print("video done")
