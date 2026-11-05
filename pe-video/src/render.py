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

# ---------- palette (球場：深色＋螢光) ----------
BG1, BG2 = (20, 26, 36), (30, 38, 52)
LIME = (190, 240, 70); ORG = (255, 140, 50); CYAN = (70, 200, 255); WH = (245, 247, 250); GR = (140, 152, 170)
RED = (255, 90, 90); DK = (12, 16, 24); BGC = (25, 32, 44)
Y, C, M, G, P, INK = LIME, RED, CYAN, GR, ORG, WH
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
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
    d = ImageDraw.Draw(img)
    for k in range(4):  # 跑道線
        y = 760 + k * 40
        d.line([(0, y), (W, y)], fill=(48, 60, 80, 255), width=3)
    d.arc((W - 520, -260, W + 260, 520), 90, 180, fill=(48, 60, 80, 255), width=4)  # 三分線意象
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


# ======================= 體育：暖身的正確打開方式 =======================
def A(t, t0, d=0.45): return eo((t - t0) / d)
GROUND = 740

def V(deg, L):
    r = math.radians(deg); return (L * math.sin(r), L * math.cos(r))  # 0=朝下，正=朝前(右)

def figure(c, x, pose, col=WH, s=1., a=1.):
    """側視火柴人；pose 角度皆為絕對角度（0 朝下、正值朝前）"""
    if a <= 0.02: return
    T, TH, SH, UA, FA = 125 * s, 88 * s, 88 * s, 66 * s, 60 * s
    hip_y = GROUND - (TH + SH) + pose.get("dy", 0) * s
    hip = (x, hip_y)
    lean = pose.get("lean", 0)
    neck = (hip[0] + T * math.sin(math.radians(lean)), hip[1] - T * math.cos(math.radians(lean)))
    shoulder = (hip[0] + (T - 12 * s) * math.sin(math.radians(lean)), hip[1] - (T - 12 * s) * math.cos(math.radians(lean)))
    d = ImageDraw.Draw(c); w = int(17 * s)
    def seg(p, ang, L):
        v = V(ang, L); return (p[0] + v[0], p[1] + v[1])
    def stroke(p, q, cc):
        d.line([p, q], fill=cc + (255,), width=w)
        r = w / 2; d.ellipse((q[0] - r, q[1] - r, q[0] + r, q[1] + r), fill=cc + (255,)); d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=cc + (255,))
    back = mix(col, BGC, a * .55); front = mix(col, BGC, a)
    for side, cc in (("R", back), ("L", front)):  # 後側肢體較暗
        k = seg(hip, pose["th" + side], TH); f = seg(k, pose["sh" + side], SH); stroke(hip, k, cc); stroke(k, f, cc)
        if side == "R":
            e = seg(shoulder, pose["ua" + side], UA); h2 = seg(e, pose["fa" + side], FA); stroke(shoulder, e, cc); stroke(e, h2, cc)
    stroke(hip, neck, front)
    e = seg(shoulder, pose["uaL"], UA); h2 = seg(e, pose["faL"], FA); stroke(shoulder, e, front); stroke(e, h2, front)
    hr = 30 * s; hc = (neck[0] + 6 * s * math.sin(math.radians(lean)), neck[1] - hr - 4 * s)
    d.ellipse((hc[0] - hr, hc[1] - hr, hc[0] + hr, hc[1] + hr), fill=front + (255,))

def P_stand(): return dict(thL=0, shL=0, thR=0, shR=0, uaL=8, faL=20, uaR=-8, faR=10, lean=0)
def P_jog(p, amp=1.):
    s = math.sin(2 * math.pi * p) * amp
    return dict(thL=35 * s, shL=35 * s - 55 * max(0, -s) - 20, thR=-35 * s, shR=-35 * s - 55 * max(0, s) - 20,
                uaL=-40 * s, faL=-40 * s + 85, uaR=40 * s, faR=40 * s + 85, lean=6, dy=-12 * abs(s))
def P_highknee(p):
    s = math.sin(2 * math.pi * p); l, r = max(0, s), max(0, -s)
    return dict(thL=90 * l, shL=-5 * l, thR=90 * r, shR=-5 * r, uaL=-45 * s, faL=-45 * s + 90, uaR=45 * s, faR=45 * s + 90, lean=0, dy=-14 * abs(s))
def P_buttkick(p):
    s = math.sin(2 * math.pi * p); l, r = max(0, s), max(0, -s)
    return dict(thL=-8 * l, shL=-168 * l, thR=-8 * r, shR=-168 * r, uaL=-35 * s, faL=-35 * s + 90, uaR=35 * s, faR=35 * s + 90, lean=4, dy=-10 * abs(s))
def P_lunge(p):
    k = (math.sin(2 * math.pi * p - math.pi / 2) * .5 + .5)  # 0 站 → 1 蹲低
    return dict(thL=80 * k, shL=5 * k, thR=-30 * k, shR=-95 * k, uaL=0, faL=0, uaR=0, faR=0, lean=0, dy=70 * k)
def P_armcircle(p, size=1.):
    ang = 360 * p
    return dict(thL=0, shL=0, thR=0, shR=0, uaL=180 + ang, faL=180 + ang, uaR=ang, faR=ang, lean=0)
def P_quad():
    return dict(thL=8, shL=-160, thR=0, shR=0, uaL=-35, faL=-110, uaR=95, faR=95, lean=4)
def P_static_bad():  # 壓腿（弓步前壓）
    return dict(thL=60, shL=-2, thR=-50, shR=-50, uaL=50, faL=60, uaR=50, faR=60, lean=35, dy=60)
def P_shoot(p):
    k = math.sin(math.pi * clamp(p * 1.4)) if p < .72 else 0
    return dict(thL=-5 * k, shL=-5 * k, thR=5 * k, shR=5 * k, uaL=150 + 20 * k, faL=170 + 10 * k, uaR=140 + 20 * k, faR=170, lean=-2, dy=-60 * k)

def chip(c, s, x, y, col=LIME, a=1., sz=40, fill=None):
    p = tpatch(s, sz, DK if fill else col, "K")
    box(c, x, y, p.width + 48, p.height + 26, fill or DK, 235, 28, alpha=a, outline=None if fill else col, ow=3)
    put(c, p, x, y, alpha=a)

def num_badge(c, n, x, y, col, a=1.):
    put(c, circ(56, col), x, y, alpha=a, scale=.7 + .3 * eob(a)); text(c, n, x, y - 4, 70, DK, "K", alpha=a)

def sc_hook(c, t, S, L):
    a = A(t, 0) * (1 - A(t, S[3] - .3, .3))
    if a > 0:
        text(c, "上體育課前，你都怎麼暖身？", 960, 170, 70, WH, "K", alpha=A(t, .1) * a)
        if t < S[1]: figure(c, 960, P_stand(), WH, 1.2, a)
        elif t < S[2]:
            figure(c, 960, P_static_bad(), ORG, 1.2, a)
            ss = min(60, (t - S[1]) * 25); chip(c, f"撐 {ss:.0f} 秒……", 1400, 360, ORG, a, 46)
        else:
            figure(c, 960 + ((t - S[2]) * 260) % 500 - 250, P_jog((t - S[2]) * 1.6), WH, 1.2, a)
            text(c, "跑更慢？跳更低？", 1450, 420, 80, RED, "K", alpha=A(t, S[2] + .2), scale=1.2 - .2 * eo(A(t, S[2] + .2, .3)))
    if t > S[3] - .2:
        ab = A(t, S[3] - .1, .5)
        text(c, "暖身的", 960, 300, 90, WH, "K", alpha=ab)
        text(c, "正確打開方式", 960, 440, 150, LIME, "K", alpha=ab, scale=.85 + .15 * eob(ab))
        figure(c, 1580, P_highknee(t * 1.6), LIME, 1., A(t, S[3] + .4))
        figure(c, 340, P_armcircle(t * .7), CYAN, 1., A(t, S[3] + .6))
        text(c, "高中體育｜運動前後怎麼做", 960, 590, 44, GR, "B", alpha=A(t, S[3] + .8))

def thermo(c, x, y, lvl, a):
    box(c, x, y, 54, 300, (60, 70, 90), 255, 27, alpha=a); put(c, circ(46, (60, 70, 90)), x, y + 160, alpha=a)
    hh = 260 * lvl; box(c, x, y + 130 - hh / 2, 30, hh + 10, RED, 255, 15, alpha=a); put(c, circ(34, RED), x, y + 160, alpha=a)

def sc_why(c, t, S, L):
    text(c, "暖身在暖什麼？", 960, 150, 80, WH, "K", alpha=A(t, .1))
    figure(c, 960, P_jog(t * 1.4, .4 + .6 * clamp((t - S[1]) / 6)), WH, 1.1, A(t, .2))
    if t > S[1]:
        a = A(t, S[1]); thermo(c, 360, 420, .25 + .6 * eo(clamp((t - S[1]) / 3)), a)
        num_badge(c, "1", 360, 230, RED, a); chip(c, "肌溫↑ 彈性↑ 收縮更快", 360, 680, RED, a, 34)
    if t > S[2]:
        a = A(t, S[2]); bpm = 75 + 55 * eo(clamp((t - S[2]) / 3))
        num_badge(c, "2", 1560, 230, ORG, a)
        put(c, circ(int(80 * (1 + .08 * abs(math.sin(t * bpm / 60 * math.pi)))), ORG), 1560, 420, alpha=a)
        text(c, f"{bpm:.0f}", 1560, 410, 64, DK, "K", alpha=a); text(c, "心跳 bpm", 1560, 530, 34, ORG, "K", alpha=a)
        chip(c, "心肺逐步進入狀態", 1560, 680, ORG, a, 34)
    if t > S[3]:
        a = A(t, S[3]); num_badge(c, "3", 960, 290, CYAN, a)
        for jx, jy in ((960, 520), (960, 610), (930, 380)):
            put(c, circ(int(22 + 8 * abs(math.sin(t * 4))), CYAN, 150), jx, jy, alpha=a)
        chip(c, "關節、動作先活動開", 960, 880 - 0, CYAN, a, 34)

def sc_myth(c, t, S, L):
    text(c, "暖身時壓腿撐很久？", 960, 150, 76, WH, "K", alpha=A(t, .1))
    figure(c, 330, P_static_bad(), ORG, .9, A(t, .2))
    X0, Y0 = 760, 300
    if t > S[1] - .2:
        a = A(t, S[1] - .2)
        line(c, (X0 - 40, Y0), (1700, Y0), GR, 3, a); text(c, "0%", X0 - 60, Y0, 30, GR, "B", anc="rm", alpha=a)
        for i, (lab, v, col, t0) in enumerate((("≥ 60 秒", 4.6, RED, S[1] + .4), ("< 60 秒", 1.1, LIME, S[2]))):
            if t < t0 - .1: continue
            ab = A(t, t0 - .1); x = 950 + i * 450; hgt = 70 * v * eo(A(t, t0, 1.))
            box(c, x, Y0 + hgt / 2, 200, max(4, hgt), col, 255, 10, alpha=ab)
            text(c, f"−{v}%", x, Y0 + hgt + 50, 60, col, "K", alpha=ab)
            text(c, lab, x, Y0 - 50, 44, WH, "K", alpha=ab)
        text(c, "靜態伸展（每個肌群）後的運動表現", 1200, 230, 0 + 34, GR, "B", alpha=0)
        text(c, "Behm et al., 2016 回顧研究", 1200, 905, 30, GR, "B", alpha=a)
    if t > S[3]:
        a = A(t, S[3], .4); box(c, 1060, 810, 1300, 100, LIME, 255, 24, alpha=a)
        text(c, "暖身別撐太久，伸展後要接動態活動", 1060, 810, 50, DK, "K", alpha=a)

def sc_step1(c, t, S, L):
    text(c, "正確暖身 3 步驟", 960, 150, 80, WH, "K", alpha=A(t, .1) * (1 - A(t, S[1] - .3, .3)))
    for i, (n, s_, col) in enumerate((("1", "先動起來", RED), ("2", "動態伸展", ORG), ("3", "專項動作", CYAN))):
        a = A(t, .4 + i * .3) * (1 - A(t, S[1] - .3, .3)); x = 520 + i * 440
        num_badge(c, n, x, 380, col, a); text(c, s_, x, 500, 56, WH, "K", alpha=a)
    if t > S[1] - .2:
        a = A(t, S[1] - .2)
        num_badge(c, "1", 200, 160 + 0, RED, a); text(c, "先動起來", 290, 160, 64, WH, "K", anc="lm", alpha=a)
        x = 250 + ((t - S[1]) * 260) % 750
        figure(c, x, P_jog(t * 1.7), WH, 1.1, a)
        chip(c, "慢跑／跳繩 約 5 分鐘", 1350, 260, RED, A(t, S[1] + .5), 44)
        chip(c, "微微發熱、有點流汗", 1350, 360, RED, A(t, S[1] + 1.5), 44)

def sc_step2(c, t, S, L):
    num_badge(c, "2", 200, 160, ORG, A(t, .05)); text(c, "動態伸展：邊動邊拉", 290, 160, 64, WH, "K", anc="lm", alpha=A(t, .1))
    moves = [(S[1], "高抬腿", P_highknee, 1.6), (S[2], "踢臀跑", P_buttkick, 1.6), (S[3], "弓箭步走", P_lunge, .55), (S[4], "手臂繞環", P_armcircle, .8)]
    cur = None
    for i, mv in enumerate(moves):
        if t >= mv[0] - .2: cur = (i, mv)
    if cur is None:
        figure(c, 960, P_jog(t * 1.5, .6), ORG, 1.2, A(t, .2)); chip(c, "每個動作約 10–15 公尺", 960, 330, ORG, A(t, .6), 44)
    else:
        i, (t0, nm, fn, sp) = cur; a = A(t, t0 - .2, .3)
        x = 700 + ((t - t0) * (120 if i < 3 else 0)) % 500
        figure(c, x, fn((t - t0) * sp), ORG, 1.25, a)
        chip(c, nm, 1450, 360, ORG, a, 64, fill=ORG)
        for k, (_, n2, _, _) in enumerate(moves):
            col = ORG if k == i else (70, 80, 100)
            box(c, 1300 + k * 100, 500, 80, 14, col, 255, 7, alpha=A(t, .3))
        if i == 3: chip(c, "由小到大、由慢到快", 1450, 620, LIME, A(t, t0 + 1.2), 40)

def sc_step3(c, t, S, L):
    num_badge(c, "3", 200, 160, CYAN, A(t, .05)); text(c, "專項動作", 290, 160, 64, WH, "K", anc="lm", alpha=A(t, .1))
    p = (t * .55) % 1
    figure(c, 800, P_shoot(p), CYAN, 1.2, A(t, .2))
    if p < .5: bx, by = 860, 330 - 120 * math.sin(math.pi * clamp(p * 1.4))
    else:
        q = (p - .5) / .5; bx = 860 + 600 * q; by = 300 - 260 * math.sin(math.pi * q * .9) + 150 * q
    put(c, circ(28, ORG), bx, by, alpha=A(t, .2))
    box(c, 1480, 330, 120, 10, ORG, 255, 5, alpha=A(t, .2)); line(c, (1540, 250), (1540, 760), GR, 8, A(t, .2))
    chip(c, "打籃球 → 運球、投籃、漸進衝刺", 960, 880 - 0, CYAN, A(t, .8), 40)
    if t > S[1]:
        a = A(t, S[1], .4); box(c, 1500, 560, 520, 160, DK, 235, 28, alpha=a, outline=LIME, ow=4)
        text(c, "全部約", 1500, 520, 40, GR, "B", alpha=a); text(c, "10–15 分鐘", 1500, 590, 70, LIME, "K", alpha=a)

def sc_cool(c, t, S, L):
    text(c, "靜態伸展 → 運動後收操", 960, 150, 76, WH, "K", alpha=A(t, .1))
    figure(c, 620, P_quad(), CYAN, 1.25, A(t, .3))
    if t > S[1]:
        a = A(t, S[1]); sec = 10 + 20 * clamp((t - S[1]) / 3.5)
        put(c, circ(120, (40, 50, 68)), 1300, 400, alpha=a)
        im = Image.new("RGBA", (260, 260), (0, 0, 0, 0)); ImageDraw.Draw(im).arc((10, 10, 250, 250), -90, -90 + 360 * sec / 30, fill=CYAN + (255,), width=18)
        put(c, im, 1300, 400, alpha=a); text(c, f"{sec:.0f}s", 1300, 395, 80, WH, "K", alpha=a)
        chip(c, "每次 10–30 秒 × 2–4 次", 1300, 600, CYAN, a, 44)
    if t > S[2]:
        a = A(t, S[2])
        chip(c, "緊：剛好", 1130, 760, LIME, a, 52, fill=LIME); chip(c, "痛：停！", 1470, 760, RED, A(t, S[2] + 1.2), 56, fill=RED)

def sc_end(c, t, S, L):
    steps = (("1", "先動起來", RED), ("2", "動態伸展", ORG), ("3", "專項動作", CYAN), ("收", "運動後靜態伸展", LIME))
    for i, (n, s_, col) in enumerate(steps):
        a = A(t, .2 + i * .5); x = 330 + i * 420
        num_badge(c, n, x, 300, col, a); text(c, s_, x, 420, 46, WH, "K", alpha=a)
        if i < 3: text(c, "→", x + 210, 300, 60, GR, "K", alpha=a)
    figure(c, 960, P_highknee(t * 1.5), LIME, 1., A(t, .4))
    if t > S[1]:
        text(c, "你最常做哪個暖身動作？留言！", 960, 160, 56, WH, "K", alpha=A(t, S[1]))
        text(c, "下次見！", 1560, 600, 90, LIME, "K", alpha=A(t, S[1] + 2), rot=6)

DRAW = dict(hook=sc_hook, why=sc_why, myth=sc_myth, step1=sc_step1, step2=sc_step2, step3=sc_step3, cool=sc_cool, end=sc_end)

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
    put(c, tpatch("高中體育｜暖身與收操", 30, G, "B"), 50, 50, "lm")
    put(c, tpatch("暖身的正確打開方式", 30, Y, "K"), W - 50, 50, "rm")
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
