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

# ---------- palette (醫療：白底紅藍) ----------
BG1, BG2 = (250, 251, 253), (234, 240, 247)
RED = (222, 56, 72); BLUE = (34, 98, 170); TEAL = (22, 150, 140); INK = (28, 38, 54); GR = (118, 130, 148)
CARD = (255, 255, 255); SKIN = (240, 196, 160); SHIRT = (90, 130, 190); AEDG = (24, 150, 90); AMB = (245, 166, 35)
WH = (255, 255, 255); DK = INK; BGC = (242, 246, 250)
Y, C, M, G, P = AMB, RED, TEAL, GR, BLUE
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
    arr[(xx % 48 == 0) | (yy % 48 == 0)] -= 6  # 淡格線（病歷紙感）
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


# ======================= 健康與護理：CPR＋AED 叫叫CD =======================
def A(t, t0, d=0.45): return eo((t - t0) / d)
BEAT = 60 / 110

def card(c, x, y, w, h, a=1., outline=None, ow=4, fill=CARD, r=26):
    box(c, x, y + 6, w, h, (200, 210, 225), 120, r, alpha=a)  # shadow
    box(c, x, y, w, h, fill, 255, r, alpha=a, outline=outline, ow=ow)

def heart_patch(s, col):
    k = ("heart", s, col)
    if k not in _pc:
        t = np.linspace(0, 2 * np.pi, 120)
        x = 16 * np.sin(t) ** 3; y = -(13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t))
        im = Image.new("RGBA", (int(36 * s), int(34 * s)), (0, 0, 0, 0))
        ImageDraw.Draw(im).polygon([(18 * s + xx * s, 17 * s + yy * s) for xx, yy in zip(x, y)], fill=col + (255,))
        _pc[k] = im
    return _pc[k]

def badge(c, s, x, y, col, a=1., sz=110, scale=1.):
    put(c, circ(int(sz * .62), col), x, y, alpha=a, scale=scale)
    text(c, s, x, y - 4, sz, WH, "K", alpha=a, scale=scale)

def victim(c, x, y, s=1., a=1., chest_dy=0.):
    """仰躺的人（側視）：頭在左"""
    k = ("victim", s)
    if k not in _pc:
        im = Image.new("RGBA", (int(620 * s), int(200 * s)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.ellipse((10 * s, 60 * s, 110 * s, 160 * s), fill=SKIN + (255,))
        d.rounded_rectangle((100 * s, 80 * s, 360 * s, 175 * s), int(40 * s), fill=SHIRT + (255,))
        d.rounded_rectangle((350 * s, 100 * s, 610 * s, 165 * s), int(30 * s), fill=(70, 80, 100, 255))
        _pc[k] = im
    put(c, _pc[k], x, y + chest_dy, alpha=a)
    put(c, rrect(int(560 * s), 14, 7, (190, 200, 215)), x, y + 100 * s, alpha=a)  # floor

def hands(c, x, y, depth=0., a=1.):
    hy = y - 40 + depth
    line(c, (x - 70, hy - 250), (x - 10, hy - 20), SKIN, 30, a); line(c, (x + 70, hy - 250), (x + 10, hy - 20), SKIN, 30, a)
    put(c, rrect(120, 46, 23, SKIN), x, hy, alpha=a); put(c, rrect(110, 40, 20, (225, 176, 140)), x, hy - 22, alpha=a)

def aed_icon(c, x, y, s=1., a=1.):
    box(c, x, y, 300 * s, 190 * s, AEDG, 255, int(30 * s), alpha=a)
    hx, hy = x - 72 * s, y
    put(c, heart_patch(3.4 * s, WH), hx, hy, alpha=a)
    pts = [(hx + 4 * s, hy - 38 * s), (hx - 16 * s, hy + 4 * s), (hx + 2 * s, hy + 4 * s), (hx - 8 * s, hy + 36 * s), (hx + 20 * s, hy - 8 * s), (hx + 2 * s, hy - 8 * s), (hx + 14 * s, hy - 38 * s)]
    if a > .05: ImageDraw.Draw(c).polygon(pts, fill=mix(AEDG, BGC, a) + (255,))
    text(c, "AED", x + 58 * s, y - 4 * s, int(60 * s), WH, "K", alpha=a)

def speech(c, s, x, y, col=INK, a=1., sz=44):
    p = tpatch(s, sz, col, "K")
    card(c, x, y, p.width + 60, p.height + 40, a, outline=col, ow=3, r=30)
    put(c, p, x, y, alpha=a)

def person_at(c, x, y, col, a=1., s=90):
    put(c, person(col, s), x, y, alpha=a)

def sc_hook(c, t, S, L):
    a = A(t, 0) * (1 - A(t, S[3] - .3, .3))
    if a > 0:
        victim(c, 960, 560, 1.1, a)
        text(c, "？", 760, 330, 120, RED, "K", alpha=A(t, .8) * a, scale=1.3 - .3 * eob(A(t, .8, .4)))
        if t > S[1]:
            for i, x in enumerate((360, 1560)): person_at(c, x, 560, GR, A(t, S[1] + i * .2) * a, 110)
            text(c, "愣住……", 1560, 380, 46, GR, "K", alpha=A(t, S[1] + .4) * a)
        if t > S[2]:
            ab = A(t, S[2]) * a; pr = clamp((t - S[2]) / 4)
            card(c, 960, 200, 620, 140, ab, outline=RED)
            text(c, "腦部缺氧 4–6 分鐘", 960, 200, 64, RED, "K", alpha=ab)
            box(c, 960, 290, 600 * (1 - pr) + 1, 12, RED, 255, 6, alpha=ab)
    if t > S[3] - .2:
        ab = A(t, S[3] - .1, .5)
        text(c, "叫叫 CD", 960, 300, 190, RED, "K", alpha=ab, scale=.85 + .15 * eob(ab))
        for i, (s_, col, lab) in enumerate((("叫", BLUE, "確認意識"), ("叫", BLUE, "求救"), ("C", RED, "壓胸"), ("D", AEDG, "AED"))):
            x = 480 + i * 320; ac = A(t, S[3] + .6 + i * .35, .35)
            badge(c, s_, x, 600, col, ac, 100, .7 + .3 * eob(ac)); text(c, lab, x, 730, 42, INK, "K", alpha=ac)
        text(c, "高中健康與護理｜CPR＋AED", 960, 830, 40, GR, "B", alpha=A(t, S[3] + 2))

def sc_call1(c, t, S, L):
    badge(c, "叫", 170, 170, BLUE, A(t, .05), 90); text(c, "確認意識", 290, 170, 64, INK, "K", anc="lm", alpha=A(t, .1))
    breathe = math.sin(t * 2.2) * 4 * 0  # 無呼吸：胸口不動
    victim(c, 960, 600, 1.1, A(t, .2), breathe)
    if t > S[1]:
        a = A(t, S[1]); tap = abs(math.sin(t * 9)) * 14 if t < S[2] else 0
        put(c, rrect(90, 40, 20, SKIN), 760, 520 - tap, alpha=a)
        speech(c, "你還好嗎？", 700, 380, BLUE, A(t, S[1] + .8))
        chip_ = "① 環境安全"; card(c, 1500, 180, 340, 80, a, outline=TEAL, ow=3); text(c, chip_, 1500, 180, 40, TEAL, "K", alpha=a)
    if t > S[2]:
        a = A(t, S[2]); x, y = 1000, 510
        put(c, rrect(220, 90, 45, None, 0, AMB, 6), x, y, alpha=a * (.6 + .4 * abs(math.sin(t * 3))))
        speech(c, "胸口有起伏嗎？", 1250, 380, AMB, a, 40)
    if t > S[3]:
        a = A(t, S[3], .4)
        card(c, 960, 860, 1300, 120, a, outline=RED, ow=5)
        text(c, "沒呼吸／喘息式呼吸 → 當成心跳停止", 960, 860, 54, RED, "K", alpha=a)

def phone(c, x, y, a=1., s=1.):
    box(c, x, y, 230 * s, 420 * s, INK, 255, int(36 * s), alpha=a)
    box(c, x, y, 200 * s, 360 * s, (236, 242, 250), 255, int(20 * s), alpha=a)
    text(c, "119", x, y - 60 * s, int(90 * s), RED, "K", alpha=a)
    put(c, circ(int(36 * s), RED), x, y + 90 * s, alpha=a); text(c, "撥", x, y + 88 * s, int(36 * s), WH, "K", alpha=a)

def sc_call2(c, t, S, L):
    badge(c, "叫", 170, 170, BLUE, A(t, .05), 90); text(c, "求救", 290, 170, 64, INK, "K", anc="lm", alpha=A(t, .1))
    f = 1 - A(t, S[3] - .3, .3)
    if t > S[1] - .2 and f > 0:
        a = A(t, S[1] - .2) * f
        person_at(c, 960, 520, BLUE, a, 120); text(c, "你", 960, 640, 40, INK, "K", alpha=a)
        person_at(c, 560, 560, GR, A(t, S[1] + .2) * f, 100); person_at(c, 1360, 560, GR, A(t, S[1] + 1.6) * f, 100)
        speech(c, "你，打 119！", 560, 360, RED, A(t, S[1] + .4) * f, 46)
        speech(c, "你，去拿 AED！", 1360, 360, AEDG, A(t, S[1] + 1.8) * f, 46)
    if t > S[2] and f > 0:
        a = A(t, S[2]) * f
        for i in range(5): person_at(c, 560 + i * 200, 850, (170, 180, 195), a, 70)
        card(c, 960, 740, 640, 80, a, outline=GR, ow=3); text(c, "「別人應該打了吧？」", 960, 740, 40, GR, "K", alpha=a)
    if t > S[3] - .2:
        a = A(t, S[3] - .2); phone(c, 760, 520, a)
        card(c, 1240, 440, 520, 110, A(t, S[3] + .4), outline=BLUE); text(c, "開擴音", 1240, 440, 60, BLUE, "K", alpha=A(t, S[3] + .4))
        text(c, "電話中會一步步指導你", 1240, 580, 46, INK, "B", alpha=A(t, S[3] + 1))

def sc_comp(c, t, S, L):
    badge(c, "C", 170, 170, RED, A(t, .05), 90); text(c, "胸外按壓", 290, 170, 64, INK, "K", anc="lm", alpha=A(t, .1))
    f = 1 - A(t, S[2] - .3, .3)
    if f > 0:
        depth = (math.sin(t * 2 * math.pi / BEAT) * .5 + .5) * 30 if t > S[1] else 0
        victim(c, 820, 640, 1.2, A(t, .2) * f)
        if t > S[1]:
            a = A(t, S[1]) * f
            put(c, circ(14, RED), 760, 590, alpha=a)
            hands(c, 760, 600, depth, a)
            for i, s_ in enumerate(("兩乳頭連線中央", "雙手交疊", "手臂打直、用體重下壓")):
                ab = A(t, S[1] + .4 + i * .9) * f
                card(c, 1520, 330 + i * 130, 560, 100, ab, outline=RED, ow=3); text(c, s_, 1520, 330 + i * 130, 44, INK, "K", alpha=ab)
    if t > S[2] - .2:
        items = (("用力壓", "深度 5–6 公分", S[2]), ("快快壓", "每分鐘 100–120 下", S[2] + 2.2),
                 ("胸回彈", "每次完全回彈", S[3]), ("莫中斷", "中斷不超過 10 秒", S[3] + 2.2))
        for i, (k_, v, t0) in enumerate(items):
            if t < t0 - .1: continue
            a = A(t, t0 - .1, .4); x = 560 + (i % 2) * 800; y = 400 + (i // 2) * 250
            card(c, x, y, 720, 200, a, outline=RED, ow=4)
            text(c, k_, x, y - 40, 72, RED, "K", alpha=a, scale=.9 + .1 * eob(a)); text(c, v, x, y + 50, 48, INK, "K", alpha=a)

def sc_rhythm(c, t, S, L):
    text(c, "每分鐘 110 下", 960, 150, 80, INK, "K", alpha=A(t, .1))
    t0 = L - 7.3  # 節拍起點＝段長−7.3 秒（與 mix.py 同一公式：b0 = t0 + len − 7.3）
    on = t0 <= t < t0 + 12 * BEAT  # 共 12 拍，與 mix.py 的 12 下 tick 對齊
    ph = ((t - t0) % BEAT) / BEAT if on else 0
    press = math.exp(-ph * 6) if on else 0
    victim(c, 820, 700, 1.2, A(t, .2))
    hands(c, 760, 660, 34 * press, A(t, .2))
    put(c, heart_patch(9, RED), 1470, 460, alpha=A(t, .3), scale=1 + .18 * press)
    if on:
        n = min(12, int((t - t0) / BEAT) + 1)
        text(c, str(n), 1470, 450, 110, WH, "K", alpha=1)
        text(c, "跟著節拍數！", 1470, 690, 50, RED, "K", alpha=A(t, t0))

def sc_aed(c, t, S, L):
    badge(c, "D", 170, 170, AEDG, A(t, .05), 90); text(c, "AED 電擊", 290, 170, 64, INK, "K", anc="lm", alpha=A(t, .1))
    aed_icon(c, 460, 470, 1.25, A(t, .3))
    text(c, "自動體外心臟電擊去顫器", 460, 640, 38, AEDG, "K", alpha=A(t, .8))
    steps = (("① 打開電源", "語音會一步步教你", S[1]), ("② 貼上貼片", "照圖示貼，自動分析", S[2]),
             ("③ 喊「大家離開！」", "沒人碰觸患者再按電擊", S[3]), ("④ 立刻繼續壓胸", "直到救護人員接手", S[4]))
    for i, (k_, v, t0) in enumerate(steps):
        if t < t0 - .1: continue
        a = A(t, t0 - .1, .4); y = 300 + i * 150; col = RED if i == 2 else AEDG
        card(c, 1260, y, 980, 125, a, outline=col, ow=4)
        text(c, k_, 800, y - 2, 50, col, "K", anc="lm", alpha=a); text(c, v, 1720, y, 36, INK, "B", anc="rm", alpha=a)
    if S[2] - .1 < t < S[3] + .2:
        a = A(t, S[2]) * (1 - A(t, S[3], .3))
        # 貼片位置示意：右上胸、左側腋下
        box(c, 460, 820, 300, 200, (232, 238, 246), 255, 30, alpha=a)
        box(c, 410, 770, 70, 50, AMB, 255, 8, alpha=a); box(c, 520, 860, 70, 50, AMB, 255, 8, alpha=a)
        text(c, "右上胸", 300, 770, 28, INK, "B", alpha=a); text(c, "左側腋下", 640, 860, 28, INK, "B", alpha=a)

def sc_fear(c, t, S, L):
    a = A(t, .1)
    for i, s_ in enumerate(("壓錯怎麼辦？", "會不會被告？")):
        speech(c, s_, 640 + i * 640, 300, GR, A(t, .2 + i * .5), 56)
    if t > S[1]:
        ab = A(t, S[1]); card(c, 960, 520, 1100, 130, ab, outline=RED, ow=5)
        text(c, "什麼都不做，結果才最糟", 960, 520, 66, RED, "K", alpha=ab)
    if t > S[2]:
        ab = A(t, S[2], .5); card(c, 960, 760, 1400, 210, ab, outline=BLUE, ow=5)
        text(c, "《緊急醫療救護法》第 14 條之 2", 960, 715, 50, BLUE, "K", alpha=ab)
        text(c, "善意急救 → 適用民法、刑法緊急避難免責", 960, 800, 50, INK, "K", alpha=A(t, S[2] + .8))

def sc_summary(c, t, S, L):
    text(c, "叫叫 CD", 960, 150, 110, RED, "K", alpha=A(t, .1))
    rows = (("叫", BLUE, "確認意識：拍肩、看呼吸", S[1]), ("叫", BLUE, "求救：指定人打 119、拿 AED", S[1] + 1.6),
            ("C", RED, "壓胸：用力壓、快快壓、胸回彈、莫中斷", S[2]), ("D", AEDG, "AED：開電源、貼貼片、喊離開、按電擊", S[2] + 3))
    for i, (b, col, s_, t0) in enumerate(rows):
        if t < t0 - .1: continue
        a = A(t, t0 - .1, .4); y = 300 + i * 135
        card(c, 1010, y, 1380, 112, a); badge(c, b, 410, y, col, a, 70)
        text(c, s_, 500, y, 46, INK, "K", anc="lm", alpha=a)
    if t > S[3]:
        a = A(t, S[3], .4); box(c, 960, 870, 1250, 100, RED, 255, 24, alpha=a)
        text(c, "看影片 ≠ 學會：去上實作課，親手壓一次", 960, 870, 48, WH, "K", alpha=a)

def sc_end(c, t, S, L):
    aed_icon(c, 600, 430, 1.5, A(t, .1))
    text(c, "學校的 AED", 1250, 330, 80, INK, "K", alpha=A(t, .3))
    text(c, "在哪裡？", 1250, 450, 100, AEDG, "K", alpha=A(t, .6), scale=.9 + .1 * eob(A(t, .6, .5)))
    text(c, "明天找找看，留言告訴我", 1250, 580, 46, GR, "B", alpha=A(t, 1.2))
    if t > S[1]:
        text(c, "下一個救人的，可能就是你", 960, 760, 64, RED, "K", alpha=A(t, S[1]))
        text(c, "下次見！", 960, 870, 70, INK, "K", alpha=A(t, S[1] + 2), scale=.9 + .1 * eob(A(t, S[1] + 2, .5)))

DRAW = dict(hook=sc_hook, call1=sc_call1, call2=sc_call2, comp=sc_comp, rhythm=sc_rhythm, aed=sc_aed,
            fear=sc_fear, summary=sc_summary, end=sc_end)

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
            box(c, 960, 1000 - 0, maxw + 70, h + 10, (28, 38, 54), 215, 18, alpha=al, anc="mm")
            for j, l in enumerate(lines): text(c, l, 960, yb + j * 62, 46, WH, "B", alpha=al)
            break

def chrome(c, gt, total, sc):
    put(c, tpatch("高中健康與護理｜CPR＋AED", 30, GR, "B"), 50, 50, "lm")
    put(c, tpatch("叫叫 CD", 30, RED, "K"), W - 50, 50, "rm")
    box(c, 0, H - 4, W, 8, (210, 218, 230), 255, 0, anc="lm")
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
