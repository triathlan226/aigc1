import math, json, sys, subprocess, os, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from script import SCENES
from sil import load, runs

W, H, FPS = 1920, 1080, 30
D = os.path.dirname(os.path.abspath(__file__))
FONTS = {k: f"{D}/NotoSansCJKtc-{v}.otf" for k, v in dict(R="Regular", B="Bold", K="Black").items()}
FONTS.update(S=f"{D}/NotoSerifCJKtc-Bold.otf", SK=f"{D}/NotoSerifCJKtc-Black.otf")
_fc = {}
def font(sz, w="B"):
    k = (sz, w)
    if k not in _fc: _fc[k] = ImageFont.truetype(FONTS[w], sz)
    return _fc[k]

# ---------- palette (宣紙／墨／朱印) ----------
BG1, BG2 = (247, 241, 227), (234, 223, 199)
INK = (43, 38, 33); RED = (178, 40, 36); GRN = (62, 110, 92); GOLD = (170, 122, 44)
GR = (128, 116, 100); PAPER = (252, 248, 238); BGC = (241, 233, 214); BLUE = (58, 88, 140)
WH = (250, 248, 242); DK = INK
Y, C, M, G, P = GOLD, RED, GRN, GR, BLUE
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
    rng = np.random.default_rng(3)
    arr += rng.normal(0, 2.2, (H, W, 1))  # paper grain
    yy, xx = np.mgrid[0:H, 0:W]
    v = np.exp(-(((xx - 960) / 1300) ** 2 + ((yy - 540) / 800) ** 2))
    arr *= (0.9 + 0.1 * v)[..., None]
    # faint mountains (ink wash) bottom-right
    for k, (amp, base, col) in enumerate([(70, 860, 18), (50, 920, 28)]):
        ridge = base - amp * (np.sin(xx[0] / 210 + k) * 0.6 + np.sin(xx[0] / 77 + 2 * k) * 0.25 + 1)
        mask = yy > ridge[None, :]
        arr[mask] -= col * 0.6
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
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
    f = f"{TEMPO_DIR}/{sid}.wav"
    if not os.path.exists(f):  # 尚未配音：用字數估計（預覽用）
        lens = [len([c for c in s if c.isalnum()]) / 4.8 + 0.35 for s, _ in segs]
        st = list(np.cumsum([0] + lens[:-1]))
        return sum(lens), st
    x = load(f); dur = len(x) / 24000
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
OVR={}

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


# ======================= 國文：燭之武退秦師 =======================
def A(t, t0, d=0.45): return eo((t - t0) / d)
def seal(c, s, x, y, sz=44, a=1., rot=0., scale=1.):
    p = tpatch(s, sz, WH, "SK")
    w, h = p.width + sz * .6, p.height + sz * .5
    box(c, x, y, w, h, RED, 255, int(sz * .18), alpha=a, scale=scale)
    put(c, p, x, y, alpha=a, scale=scale, rot=rot)

def quote(c, s, x, y, a=1., sz=60, col=INK, w=None):
    p = tpatch(s, sz, col, "SK")
    bw = w or p.width + 110
    box(c, x, y, bw, p.height + 60, PAPER, 245, 14, alpha=a, outline=(214, 200, 172), ow=2)
    box(c, x - bw / 2 + 10, y, 10, p.height + 34, RED, 255, 4, alpha=a)
    put(c, p, x + 6, y, alpha=a)

def chip(c, s, x, y, col=INK, a=1., sz=38, fill=None, anc="mm"):
    p = tpatch(s, sz, col if fill is None else WH, "B")
    box(c, x, y, p.width + 44, p.height + 26, fill or PAPER, 240, 30, alpha=a, outline=None if fill else col, ow=3, anc=anc)
    dx = 0 if anc == "mm" else (p.width + 44) / 2
    put(c, p, x + dx, y, alpha=a)

def portrait(c, name, x, y, col, a=1., s=1., sub=None):
    put(c, circ(int(78 * s), col), x, y, alpha=a, scale=.7 + .3 * eob(a))
    text(c, name[0], x, y - 4, int(76 * s), WH, "SK", alpha=a)
    text(c, name, x, y + 112 * s, int(36 * s), INK, "B", alpha=a)
    if sub: text(c, sub, x, y + 156 * s, int(28 * s), GR, "R", alpha=a)

def nation(c, ch, x, y, col, a=1., w=240, h=200, scale=1.):
    box(c, x, y, w, h, col, 235, 22, alpha=a, scale=scale)
    text(c, ch, x, y, int(min(w, h) * .62), WH, "SK", alpha=a, scale=scale)

def arrow(c, p0, p1, col, wd=10, a=1., pr=1.):
    if pr <= 0: return
    x = p0[0] + (p1[0] - p0[0]) * pr; y = p0[1] + (p1[1] - p0[1]) * pr
    line(c, p0, (x, y), col, wd, a)
    ang = math.atan2(y - p0[1], x - p0[0]); L = wd * 3
    pts = [(x, y), (x - L * math.cos(ang - .45), y - L * math.sin(ang - .45)), (x - L * math.cos(ang + .45), y - L * math.sin(ang + .45))]
    ImageDraw.Draw(c).polygon(pts, fill=mix(col, BGC, a) + (255,))

def header(c, n, title, t):
    a = A(t, .05)
    seal(c, f"第{n}招", 170, 150, 40, a)
    text(c, title, 290, 150, 62, INK, "SK", anc="lm", alpha=a)

def wall_scene(c, t, t0, a=1., x0=360):
    a = a * A(t, t0)
    if a <= 0: return
    put(c, circ(60, (250, 236, 180)), x0 - 120, 220, alpha=a)  # moon
    box(c, x0 + 200, 640, 420, 420, (150, 136, 116), 255, 6, alpha=a)
    for k in range(5): box(c, x0 + 30 + k * 85, 418, 52, 46, (150, 136, 116), 255, 4, alpha=a)
    for r in range(6):
        for k in range(4): box(c, x0 + 52 + k * 100 + (r % 2) * 50, 470 + r * 66, 90, 4, (128, 114, 96), 255, 1, alpha=a)
    pr = eo(clamp((t - t0 - .3) / 2.5))
    rx = x0 + 420; ry = 430 + 360 * pr
    line(c, (rx, 420), (rx, ry), INK, 4, a)
    put(c, person(INK, 56), rx + 4, ry + 30, alpha=a)

def bubble(c, s, x, y, right=True, a=1., sz=44):
    p = tpatch(s, sz, INK if not right else WH, "B")
    col = GRN if right else PAPER
    box(c, x, y, p.width + 60, p.height + 40, col, 255, 28, alpha=a, scale=.85 + .15 * eob(a), outline=None if right else (200, 186, 160), ow=2)
    put(c, p, x, y, alpha=a)

def sc_hook(c, t, S, L):
    fa = 1 - A(t, S[2] - .3, .3)
    if fa > 0:
        bubble(c, "爸，今天可以晚點回家嗎？拜託啦～", 1180, 330, True, A(t, .2) * fa)
        if t > S[1] + .5: bubble(c, "不行。", 640, 500, False, A(t, S[1] + .5, .3) * fa, 56)
        if t > S[1] + 1.2: text(c, "✕", 1180, 520, 120, RED, "K", alpha=A(t, S[1] + 1.2, .25) * fa, scale=1.4 - .4 * eo(A(t, S[1] + 1.2, .25)))
    fb = A(t, S[2] - .2) * (1 - A(t, S[4] - .3, .3))
    if fb > 0:
        wall_scene(c, t, S[2] - .2, fb, 300)
        text(c, "半夜．垂繩出城", 1250, 300, 72, INK, "SK", alpha=fb)
        if t > S[3]:
            ab = A(t, S[3]) * fb; mv = eo(clamp((t - S[3] - .3) / 2.5)) * 260
            for k in range(4):
                seal(c, "秦", 1060 + k * 150 - mv, 560 + (k % 2) * 90, 50, ab * (1 - .7 * mv / 260))
            arrow(c, (1600, 760), (1060, 760), BLUE, 10, ab, eo(A(t, S[3] + .2, .8)))
            text(c, "秦軍撤退", 1330, 820, 56, BLUE, "K", alpha=ab)
    if t > S[4] - .2:
        a = A(t, S[4] - .1, .6)
        text(c, "燭之武退秦師", 960, 430, 170, INK, "SK", alpha=a, scale=.9 + .1 * eob(a))
        seal(c, "左傳", 1590, 300, 46, A(t, S[4] + .4, .3), rot=-6, scale=1.3 - .3 * eo(A(t, S[4] + .4, .3)))
        box(c, 960, 570, 820 * eo(A(t, S[4] + .2, .5)) + 1, 6, RED, 255, 3, alpha=a)
        text(c, "高中國文｜古文 15 篇｜史上最強說服術", 960, 650, 46, GR, "B", alpha=A(t, S[4] + .5))

def sc_bg(c, t, S, L):
    text(c, "西元前 630 年", 960, 140, 70, INK, "SK", alpha=A(t, .1))
    shake = math.sin(t * 38) * 9 * (A(t, S[3], .2) - A(t, S[3] + 1, .6)) if t > S[3] else 0
    nation(c, "秦", 380, 500, BLUE, A(t, .2))
    nation(c, "晉", 900, 330, GOLD, A(t, .4))
    nation(c, "鄭", 1420 + shake, 560, RED, A(t, .6))
    arrow(c, (510, 520), (1280, 560), BLUE, 9, A(t, .8), eo(A(t, .8, 1.)))
    arrow(c, (1000, 420), (1330, 470), GOLD, 9, A(t, 1.), eo(A(t, 1., 1.)))
    if t > S[1]:
        a = A(t, S[1]); nation(c, "楚", 1000, 760, GR, a, 180, 150)
        for k in range(8): put(c, circ(5, GR), 1120 + k * 30, 740 - k * 18, alpha=a)
        chip(c, "① 曾對晉文公無禮", 1720, 380, RED, A(t, S[1] + .2), 32)
        chip(c, "② 暗中親楚", 1720, 760, RED, A(t, S[1] + 1.5), 32)
    if t > S[2]:
        a = A(t, S[2]); chip(c, "晉軍｜函陵", 1420, 410, GOLD, a, 30, fill=GOLD)
        chip(c, "秦軍｜氾（ㄈㄢˊ）南", 1420, 710, BLUE, A(t, S[2] + .8), 30, fill=BLUE)
    if t > S[3]: seal(c, "危", 1580, 560, 70, A(t, S[3], .2), rot=8, scale=1.5 - .5 * eo(A(t, S[3], .25)))

def sc_hero(c, t, S, L):
    fa = 1 - A(t, S[5] - .3, .3)
    if fa > 0:
        if t < S[4]:
            portrait(c, "佚之狐", 520, 330, GR, A(t, .2) * fa * (1 - A(t, S[1], .4)), sub="鄭國大臣")
            arrow(c, (620, 330), (820, 330), GR, 6, A(t, .7) * (1 - A(t, S[1], .4)), eo(A(t, .7, .6)))
            text(c, "推薦", 720, 290, 32, GR, "B", alpha=A(t, .9) * (1 - A(t, S[1], .4)))
        px = 960 if t < S[1] else 960 - 0 * A(t, S[1])
        portrait(c, "燭之武", 960 if t < S[4] else 960 - 400 * eo(A(t, S[4], .5)), 330, INK, A(t, .4) * fa)
        if t > S[1] and t < S[4] + .5:
            a = A(t, S[1]) * (1 - A(t, S[4], .4))
            chip(c, "滿腹怨氣", 1180, 250, RED, a, 32)
            if t > S[2] - .2:
                ab = A(t, S[2] - .2) * (1 - A(t, S[4], .4))
                quote(c, "臣之壯也，猶不如人；今老矣，無能為也已。", 960, 640, ab, 54)
                if t > S[3]: text(c, "我年輕時都不如人，現在老了，還能做什麼？", 960, 770, 40, GR, "B", alpha=A(t, S[3]) * (1 - A(t, S[4], .4)))
        if t > S[4]:
            a = A(t, S[4] + .2)
            portrait(c, "鄭文公", 1360, 330, GOLD, a * fa, sub="鄭國國君")
            quote(c, "吾不能早用子，今急而求子，是寡人之過也。", 960, 640, A(t, S[4] + .5) * fa, 46)
            quote(c, "然鄭亡，子亦有不利焉。", 960, 780, A(t, S[4] + 2.5) * fa, 46)
            chip(c, "先認錯", 1640, 640, GOLD, A(t, S[4] + .8) * fa, 30, fill=GOLD)
            chip(c, "再講利害", 1500, 780, GOLD, A(t, S[4] + 2.8) * fa, 30, fill=GOLD)
    if t > S[5] - .2:
        wall_scene(c, t, S[5], 1, 300)
        a = A(t, S[5] + .4)
        text(c, "夜縋而出", 1280, 420, 110, INK, "SK", alpha=a, scale=.9 + .1 * eob(a))
        chip(c, "縋（ㄓㄨㄟˋ）：用繩子垂下", 1280, 580, RED, A(t, S[5] + 1), 36)
        portrait(c, "秦穆公", 1280, 760 - 30, BLUE, A(t, S[5] + 2.5), .7)

def sc_m1(c, t, S, L):
    header(c, "一", "先站在對方那邊", t)
    portrait(c, "燭之武", 480, 420, INK, A(t, .3))
    portrait(c, "秦穆公", 1440, 420, BLUE, A(t, .5))
    if t > S[1] - .1:
        q = "秦、晉圍鄭，鄭既知亡矣。" if t < S[4] else "若亡鄭而有益於君，敢以煩執事。"
        a = A(t, S[1] - .1) if t < S[4] else A(t, S[4], .4)
        if t > S[4] - .3 and t < S[4]: a = 1 - A(t, S[4] - .3, .3)
        quote(c, q, 960, 720, a, 60)
    if t > S[2]: chip(c, "不求饒，先承認", 480, 230, RED, A(t, S[2]), 34)
    if t > S[3]:
        a = A(t, S[3]); v = 1 - .75 * eo(clamp((t - S[3] - .2) / 1.6))
        text(c, "防備心", 1440, 220, 34, BLUE, "B", alpha=a)
        box(c, 1440, 270, 300, 30, (220, 210, 190), 255, 15, alpha=a)
        box(c, 1290 + 150 * v, 270, max(20, 300 * v), 30, RED, 255, 15, alpha=a)
    if t > S[4] + .8: text(c, "我知道您也有難處，若真有好處，您就動手吧", 960, 850, 34, GR, "B", alpha=A(t, S[4] + .8))

def sc_m2(c, t, S, L):
    header(c, "二", "滅鄭，對您沒好處", t)
    merge = eo(A(t, S[4], 1.0)) if t > S[4] else 0
    if t > S[1] - .2:
        a = A(t, S[1] - .2)
        nation(c, "秦", 420, 470, BLUE, a)
        jw = 260 + 300 * merge
        nation(c, "晉", 960 + 150 * merge, 470, GOLD, a, jw, 200)
        if merge < .98: nation(c, "鄭", 1500, 470, RED, a * (1 - merge), 260, 200)
        text(c, "西", 220, 470, 40, GR, "B", alpha=a); text(c, "東", 1700, 470, 40, GR, "B", alpha=a)
    if t > S[2] and t < S[4] + .3:
        a = A(t, S[2]) * (1 - A(t, S[4], .3))
        pts = [(420 + 1080 * k / 30, 350 - math.sin(math.pi * k / 30) * 150) for k in range(31)]
        pr = int(30 * eo(A(t, S[2] + .2, 1.2)))
        for k in range(0, pr, 2): line(c, pts[k], pts[k + 1], BLUE, 6, a)
        text(c, "？", 960, 170, 80, BLUE, "K", alpha=a)
        quote(c, "越國以鄙遠，君知其難也。", 960, 740, a, 58)
    if t > S[4]:
        quote(c, "鄰之厚，君之薄也。", 960, 740, A(t, S[4] + .5), 62)
    if t > S[5]:
        a = A(t, S[5], .3)
        text(c, "▲ 變強", 1110, 330, 46, GOLD, "K", alpha=a); text(c, "▼ 變弱", 420, 330, 46, RED, "K", alpha=a)

def sc_m3(c, t, S, L):
    header(c, "三", "給看得見的好處", t)
    a = A(t, S[1] - .3)
    if t > S[1] - .3:
        line(c, (420, 480), (1460, 480), (190, 172, 140), 26, a)
        nation(c, "秦", 300, 480, BLUE, a, 200, 170)
        nation(c, "鄭", 1580, 480, RED, a, 200, 170)
        chip(c, "東道主", 1580, 330, RED, A(t, S[1] + .5), 34, fill=RED)
        quote(c, "若舍鄭以為東道主", 960, 720, A(t, S[1]) * (1 - A(t, S[2], .3)), 58)
    if t > S[2]:
        for k in range(3):
            ph = ((t - S[2]) * .25 + k / 3) % 1
            put(c, person(GOLD, 44), 450 + 1000 * ph, 440, alpha=A(t, S[2]))
        quote(c, "行李之往來，共其乏困", 960, 720, A(t, S[2]), 56)
        chip(c, "行李＝外交使者（不是行李箱！）", 960, 845, GOLD, A(t, S[2] + 1.2), 32)
    if t > S[3]: seal(c, "君亦無所害", 300, 300, 40, A(t, S[3], .3), rot=-5, scale=1.4 - .4 * eo(A(t, S[3], .3)))
    if t > S[4]:
        a = A(t, S[4], .4)
        box(c, 960, 260, 520, 150, PAPER, 250, 20, alpha=a, outline=GOLD, ow=4)
        text(c, "東道主", 960, 260, 92, GOLD, "SK", alpha=a, scale=1.2 - .2 * eob(a))
        seal(c, "成語出處", 1300, 210, 30, a, rot=8)

def sc_m4(c, t, S, L):
    header(c, "四", "翻舊帳，點出真正威脅", t)
    part2 = t > S[3] - .2
    f1 = 1 - A(t, S[3] - .4, .3)
    if f1 > 0:
        nation(c, "秦", 360, 470, BLUE, A(t, S[1] - .3) * f1, 220, 190)
        nation(c, "晉", 820, 470, GOLD, A(t, S[1] - .3) * f1, 220, 190)
        if t > S[1]:
            arrow(c, (700, 400), (480, 400), GOLD, 6, A(t, S[1]) * f1, eo(A(t, S[1], .8)))
            chip(c, "許君焦、瑕", 590, 320, GOLD, A(t, S[1] + .4) * f1, 32)
        if t > S[2] - .2:
            a = A(t, S[2] - .2) * f1
            put(c, circ(60, (240, 170, 70)), 1220, 330, alpha=a); text(c, "朝", 1220, 330, 54, WH, "SK", alpha=a)
            ab = A(t, S[2] + 1.2) * f1
            put(c, circ(60, (90, 96, 130)), 1520, 330, alpha=ab); text(c, "夕", 1520, 330, 54, WH, "SK", alpha=ab)
            nb = int(8 * eo(clamp((t - S[2] - 1.4) / 1.5)))
            for k in range(nb): box(c, 1300 + (k % 4) * 70, 520 - (k // 4) * 40, 64, 34, (150, 136, 116), 255, 4, alpha=f1)
            text(c, "設版＝築牆防秦", 1400, 610, 34, RED, "B", alpha=A(t, S[2] + 2.2) * f1)
            quote(c, "朝濟而夕設版焉", 960, 760, a, 58)
    if part2:
        a = A(t, S[3] - .2)
        nation(c, "秦", 360, 450, BLUE, a, 220, 190); nation(c, "晉", 960, 450, GOLD, a, 220, 190)
        nation(c, "鄭", 1560, 450, RED, a * (1 - .6 * A(t, S[3] + 1.2)), 220, 190)
        arrow(c, (1090, 450), (1430, 450), RED, 12, a, eo(A(t, S[3] + .3, .9)))
        if t > S[4]: arrow(c, (830, 450), (490, 450), RED, 12, 1, eo(A(t, S[4], .9)))
        q = "夫晉，何厭之有？" if t < S[4] else ("若不闕秦，將焉取之？" if t < S[5] else None)
        if q: quote(c, q, 960, 720, A(t, S[3]) if t < S[4] else A(t, S[4]), 58)
        if t > S[5]:
            ab = A(t, S[5], .4)
            box(c, 960, 720, 980, 140, PAPER, 250, 16, alpha=ab, outline=RED, ow=6)
            text(c, "闕秦以利晉，唯君圖之。", 960, 720, 66, RED, "SK", alpha=ab, scale=1.1 - .1 * eob(ab))
            chip(c, "闕：損害", 1560, 860, RED, A(t, S[5] + 1), 30)

def sc_end_war(c, t, S, L):
    f1 = 1 - A(t, S[2] - .3, .3)
    if f1 > 0:
        portrait(c, "秦穆公", 960, 300, BLUE, A(t, .1) * f1)
        chip(c, "說（ㄩㄝˋ）＝悅：很高興", 1330, 240, BLUE, A(t, .5) * f1, 32)
        if t > S[1]:
            a = A(t, S[1]) * f1
            nation(c, "秦", 560, 620, BLUE, a, 200, 160); nation(c, "鄭", 1360, 620, RED, a, 200, 160)
            seal(c, "盟", 960, 620, 64, A(t, S[1] + .4) * f1, scale=1.4 - .4 * eo(A(t, S[1] + .4, .3)))
            for k, nm in enumerate(["杞子", "逢孫", "楊孫"]):
                ab = A(t, S[1] + 1 + k * .3) * f1
                put(c, person(BLUE, 40), 1260 + k * 100, 760, alpha=ab); text(c, nm, 1260 + k * 100, 820, 26, INK, "B", alpha=ab)
            arrow(c, (440, 760), (240, 760), BLUE, 8, A(t, S[1] + 2) * f1, eo(A(t, S[1] + 2, .7)))
            text(c, "撤兵", 340, 820, 32, BLUE, "B", alpha=A(t, S[1] + 2) * f1)
    if t > S[2] - .2 and t < S[4] + .3:
        f2 = A(t, S[2] - .2) * (1 - A(t, S[4], .3))
        portrait(c, "子犯", 520, 330, GOLD, f2, sub="晉國大臣"); chip(c, "追擊秦軍？", 520, 160, GOLD, f2, 32)
        portrait(c, "晉文公", 1400, 330, GOLD, A(t, S[2] + .6) * (1 - A(t, S[4], .3)), sub="晉國國君")
        if t > S[3] - .1:
            ab = A(t, S[3] - .1) * (1 - A(t, S[4], .3))
            quote(c, "微夫人之力不及此。", 960, 680, ab, 66)
            chip(c, "夫（ㄈㄨˊ）人＝那個人（秦穆公）", 960, 820, RED, A(t, S[3] + .8) * (1 - A(t, S[4], .3)), 32)
    if t > S[4]:
        a = A(t, S[4] + .2, .5)
        text(c, "一個老人．一個晚上", 960, 380, 88, INK, "SK", alpha=a)
        text(c, "退了兩國大軍", 960, 520, 110, RED, "SK", alpha=A(t, S[4] + 1, .5), scale=.9 + .1 * eob(A(t, S[4] + 1, .5)))
        seal(c, "鄭存", 1460, 520, 44, A(t, S[4] + 1.6, .3), rot=-8)

def sc_formula(c, t, S, L):
    text(c, "燭之武說服公式", 960, 150, 84, INK, "SK", alpha=A(t, .1))
    items = [("壹", "站在對方立場", "鄭既知亡矣"), ("貳", "說明對他沒好處", "鄰之厚，君之薄"),
             ("參", "給看得見的好處", "東道主"), ("肆", "點出真正威脅", "闕秦以利晉")]
    for i, (n, s, ex) in enumerate(items):
        t0 = S[1] + (0 if i == 0 else 1.8) if i < 2 else S[2] + (0 if i == 2 else 1.8)
        if t < t0: continue
        a = A(t, t0, .4); x = 540 + (i % 2) * 840; y = 360 + (i // 2) * 230
        box(c, x, y, 760, 190, PAPER, 250, 20, alpha=a, scale=.9 + .1 * eob(a), outline=(214, 200, 172), ow=2)
        seal(c, n, x - 300, y, 50, a)
        text(c, s, x - 220, y - 25, 50, INK, "K", anc="lm", alpha=a)
        text(c, "「" + ex + "」", x - 220, y + 45, 34, GR, "S", anc="lm", alpha=a)
    if t > S[3]:
        a = A(t, S[3], .4)
        box(c, 960, 830, 1100, 110, RED, 255, 24, alpha=a, scale=.9 + .1 * eob(a))
        text(c, "講「對你好不好」，不是「拜託你」", 960, 830, 52, WH, "K", alpha=a)

def sc_exam(c, t, S, L):
    text(c, "考試必考字詞", 900, 150, 80, INK, "SK", alpha=A(t, .1)); seal(c, "必考", 1240, 150, 36, A(t, .4), rot=6)
    rows = [("東道主", "東方路上的主人", S[1]), ("行李", "外交使者", S[1] + 2.5),
            ("夫（ㄈㄨˊ）人", "那個人（指秦穆公）", S[2]), ("縋（ㄓㄨㄟˋ）", "用繩子垂下城牆", S[3])]
    for i, (w, m, t0) in enumerate(rows):
        if t < t0 - .1: continue
        a = A(t, t0 - .1, .4); y = 300 + i * 150
        box(c, 960, y, 1300, 120, PAPER, 250, 18, alpha=a, outline=(214, 200, 172), ow=2)
        text(c, w, 380, y, 58, RED, "SK", anc="lm", alpha=a)
        text(c, "→", 900, y, 50, GR, "B", alpha=a)
        text(c, m, 980, y, 50, INK, "K", anc="lm", alpha=a)

def sc_end(c, t, S, L):
    a = A(t, .1, .5)
    box(c, 960, 230, 1400, 170, PAPER, 250, 24, alpha=a, outline=GOLD, ow=4)
    text(c, "先站在對方那邊，再講對他的好處", 960, 230, 64, INK, "SK", alpha=a)
    if t > S[1]:
        bubble(c, "爸，我晚點回家，順路幫你買宵夜好嗎？", 1120, 480, True, A(t, S[1] + .2))
        bubble(c, "好啊！", 600, 620, False, A(t, S[1] + 2.2), 56)
        if t > S[1] + 2.6: seal(c, "成功", 820, 620, 40, A(t, S[1] + 2.6, .3), rot=-10, scale=1.4 - .4 * eo(A(t, S[1] + 2.6, .3)))
    if t > S[2]:
        text(c, "下次見！", 960, 800, 90, RED, "SK", alpha=A(t, S[2] + .3), scale=.9 + .1 * eob(A(t, S[2] + .3, .5)))

DRAW = dict(hook=sc_hook, bg=sc_bg, hero=sc_hero, m1=sc_m1, m2=sc_m2, m3=sc_m3, m4=sc_m4,
            end_war=sc_end_war, formula=sc_formula, exam=sc_exam, end=sc_end)

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
            box(c, 960, 1000 - 0, maxw + 70, h + 10, (30, 26, 22), 190, 18, alpha=al, anc="mm")
            for j, l in enumerate(lines): text(c, l, 960, yb + j * 62, 46, WH, "B", alpha=al)
            break

def chrome(c, gt, total, sc):
    put(c, tpatch("高中國文｜〈燭之武退秦師〉", 30, GR, "B"), 50, 50, "lm")
    put(c, tpatch("說服術", 30, RED, "K"), W - 50, 50, "rm")
    box(c, 0, H - 4, W, 8, (214, 200, 172), 255, 0, anc="lm")
    pw = int(W * gt / total)
    if pw > 2: box(c, 0, H - 4, pw, 8, RED, 255, 0, anc="lm")

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
