"""逐格繪製「A4 紙對折 1000 次」直式動畫（1080x1920）。
用法：python3 render.py <chunk_idx> <n_chunks>  → seg_<idx>.mp4
"""
import math, sys, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from timeline import *

W, H = 1080, 1920
FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
YEL = (255, 213, 74); CYAN = (110, 210, 255); PINK = (255, 120, 160)
WHITE = (255, 255, 255); SOFT = (200, 215, 235); PAPER = (246, 245, 238)
LY = 9.4607e15

_fc = {}
def F(s):
    s = int(s)
    if s not in _fc:
        _fc[s] = ImageFont.truetype(FONT, s)
    return _fc[s]

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return x * x * (3 - 2 * x)
def eout(x): x = clamp(x); return 1 - (1 - x) ** 3
def lerp(a, b, p): return a + (b - a) * p
def lerpc(c1, c2, p): return tuple(int(lerp(a, b, p)) for a, b in zip(c1, c2))

def vis(t, t0, t1=1e9, fi=0.45, fo=0.45):
    if t < t0 or t > t1: return 0.0
    return min(clamp((t - t0) / fi), clamp((t1 - t) / fo))

def A(c, a): return c + (int(255 * clamp(a)),)

def text(d, xy, s, size, col=WHITE, a=1.0, anchor="mm", rise=0.0):
    if a <= 0.01: return
    x, y = xy
    d.text((x, y + (1 - a) * rise), s, font=F(size), fill=A(col, a), anchor=anchor)

def rich(d, cx, cy, segs, size, col=WHITE, a=1.0, rise=0.0):
    """segs: [(字串, 'n'|'u', 顏色或 None)]，'u' 為上標；水平置中。"""
    if a <= 0.01: return
    cy = cy + (1 - a) * rise
    fN, fS = F(size), F(size * 0.55)
    ws = [(fS if s[1] == 'u' else fN).getlength(s[0]) for s in segs]
    x = cx - sum(ws) / 2
    for s, w in zip(segs, ws):
        c = s[2] if len(s) > 2 and s[2] else col
        if s[1] == 'u':
            d.text((x + 2, cy - size * 0.40), s[0], font=fS, fill=A(c, a), anchor="lm")
        else:
            d.text((x, cy), s[0], font=fN, fill=A(c, a), anchor="lm")
        x += w + (4 if s[1] == 'u' else 0)

def card(d, box, a, r=36, col=(10, 16, 34), op=0.78):
    if a <= 0.01: return
    d.rounded_rectangle(box, r, fill=A(col, op * a), outline=A((255, 255, 255), 0.18 * a), width=2)

def grad(c1, c2):
    arr = np.linspace(0, 1, H)[:, None] * (np.array(c2, float) - c1) + np.array(c1, float)
    return Image.fromarray(arr[:, None, :].astype(np.uint8), "RGB").resize((W, H), Image.NEAREST).convert("RGBA")

# ---------- 數字格式 ----------
def sig(x):
    if x >= 100: return f"{x:,.0f}"
    if x >= 10: return f"{x:.1f}"
    return f"{x:.2f}"

def fmt_h(h):
    """回傳 rich segments。"""
    if h < 0.01: return [(f"{sig(h * 1000)} 公釐", 'n')]
    if h < 1: return [(f"{sig(h * 100)} 公分", 'n')]
    if h < 1000: return [(f"{sig(h)} 公尺", 'n')]
    if h < 1e7: return [(f"{sig(h / 1000)} 公里", 'n')]
    if h < 1e11: return [(f"{sig(h / 1e7)} 萬公里", 'n')]
    if h < LY: return [(f"{sig(h / 1e11)} 億公里", 'n')]
    ly = h / LY
    if ly < 1e4: return [(f"{sig(ly)} 光年", 'n')]
    if ly < 1e8: return [(f"{sig(ly / 1e4)} 萬光年", 'n')]
    if ly < 1e12: return [(f"{sig(ly / 1e8)} 億光年", 'n')]
    e = math.floor(math.log10(h))
    return [(f"{h / 10 ** e:.2f} × 10", 'n'), (str(e), 'u'), (" 公尺", 'n')]

def flat(segs): return "".join(s[0] for s in segs)

# ---------- 星空 ----------
srng = np.random.default_rng(3)
STARS = [(srng.uniform(0, W), srng.uniform(0, H), srng.uniform(1, 3.2), srng.uniform(0.4, 1), srng.uniform(0, 6.28))
         for _ in range(320)]

def stars(d, t, a, scroll=0.0):
    if a <= 0.01: return
    for x, y, r, b, ph in STARS:
        yy = (y + scroll * (r / 3)) % H
        tw = 0.75 + 0.25 * math.sin(t * 2.2 + ph)
        d.ellipse((x - r, yy - r, x + r, yy + r), fill=A((255, 255, 255), a * b * tw))

# ---------- 圖示 ----------
def icon(d, kind, cx, y, a):
    if a <= 0.01: return
    if kind == "nail":
        d.rounded_rectangle((cx - 26, y, cx + 26, y + 64), 18, fill=A((255, 196, 196), a), outline=A((200, 120, 130), a), width=3)
        d.rounded_rectangle((cx - 20, y + 4, cx + 20, y + 22), 8, fill=A((255, 240, 240), a))
    elif kind == "hand":
        sk = (238, 196, 160)
        for i, hgt in enumerate([52, 62, 58, 46]):
            x0 = cx - 46 + i * 24
            d.rounded_rectangle((x0, y + 62 - hgt, x0 + 20, y + 80), 10, fill=A(sk, a))
        d.rounded_rectangle((cx - 48, y + 55, cx + 48, y + 150), 26, fill=A(sk, a))
        d.rounded_rectangle((cx + 36, y + 80, cx + 76, y + 104), 12, fill=A(sk, a))
    elif kind == "person":
        c = A((25, 35, 70), a)
        d.ellipse((cx - 20, y, cx + 20, y + 40), fill=c)
        d.line((cx, y + 40, cx, y + 105), fill=c, width=10)
        d.line((cx - 38, y + 80, cx, y + 55, cx + 38, y + 80), fill=c, width=8)
        d.line((cx - 26, y + 155, cx, y + 105, cx + 26, y + 155), fill=c, width=9)
    elif kind == "t101":
        c = A((95, 160, 150), a); c2 = A((60, 120, 115), a)
        d.line((cx, y, cx, y + 22), fill=c, width=4)
        for i in range(8):
            yy = y + 22 + i * 15
            d.polygon([(cx - 16, yy), (cx + 16, yy), (cx + 22, yy + 15), (cx - 22, yy + 15)], fill=c if i % 2 else c2)
        d.rectangle((cx - 28, y + 142, cx + 28, y + 165), fill=c2)
    elif kind == "burj":
        c = A((190, 200, 220), a)
        d.polygon([(cx, y), (cx + 34, y + 165), (cx - 34, y + 165)], fill=c)
        d.polygon([(cx, y + 30), (cx + 50, y + 165), (cx + 28, y + 165)], fill=A((150, 160, 185), a))
    elif kind == "everest":
        d.polygon([(cx - 120, y + 160), (cx, y), (cx + 120, y + 160)], fill=A((105, 110, 140), a))
        d.polygon([(cx - 36, y + 48), (cx, y), (cx + 36, y + 48), (cx + 12, y + 38), (cx - 8, y + 52)], fill=A((250, 250, 255), a))
    elif kind == "moon":
        d.ellipse((cx - 62, y - 62, cx + 62, y + 62), fill=A((205, 205, 212), a))
        for ox, oy, r in [(-20, -15, 14), (22, 10, 18), (-10, 28, 9), (25, -28, 8)]:
            d.ellipse((cx + ox - r, y + oy - r, cx + ox + r, y + oy + r), fill=A((168, 168, 180), a))
    elif kind == "sun":
        for i in range(6, 0, -1):
            r = 75 + i * 14
            d.ellipse((cx - r, y - r, cx + r, y + r), fill=A((255, 170, 40), a * 0.08))
        d.ellipse((cx - 75, y - 75, cx + 75, y + 75), fill=A((255, 205, 70), a))
    elif kind in ("galaxy", "andromeda"):
        for i in range(5, 0, -1):
            r = i * 22
            d.ellipse((cx - r * 1.3, y - r * 0.55, cx + r * 1.3, y + r * 0.55), fill=A((170, 140, 255), a * 0.10))
        for arm in range(2):
            for i in range(160):
                rr = 6 + i * 0.75; th = i * 0.06 + arm * math.pi
                x = cx + rr * math.cos(th) * 1.25; yy = y + rr * math.sin(th) * 0.5
                s = 2.6 - i * 0.01
                d.ellipse((x - s, yy - s, x + s, yy + s), fill=A((255, 215, 175) if kind == "andromeda" else (225, 215, 255), a * 0.9))
        d.ellipse((cx - 14, y - 9, cx + 14, y + 9), fill=A((255, 240, 210), a))
    elif kind == "universe":
        cols = [(70, 50, 180), (110, 70, 200), (190, 90, 170), (240, 140, 110), (255, 200, 120)]
        for i, c in enumerate(cols):
            r = 150 - i * 26
            d.ellipse((cx - r, y - r, cx + r, y + r), fill=A(c, a * 0.85))
        for k in range(60):
            ang = k * 2.4; rr = (k * 37 % 140)
            x = cx + rr * math.cos(ang); yy = y + rr * math.sin(ang)
            d.ellipse((x - 2, yy - 2, x + 2, yy + 2), fill=A((255, 255, 255), a))

OBJS = [  # (高度 m, 圖示, 標籤, x, 是否置中於刻度線)
    (0.0128, "nail", "指甲寬 ~1.3 cm", 640, False),
    (0.10, "hand", "手掌寬 ~10 cm", 640, False),
    (1.7, "person", "大人 ~1.7 m", 640, False),
    (508, "t101", "台北101  508 m", 600, False),
    (828, "burj", "杜拜塔  828 m", 690, False),
    (8849, "everest", "聖母峰  8,849 m", 640, False),
    (3.844e8, "moon", "月球  38.4萬公里", 640, True),
    (1.496e11, "sun", "太陽  1.5億公里", 640, True),
    (1e5 * LY, "galaxy", "銀河系  ~10萬光年", 640, True),
    (2.5e6 * LY, "andromeda", "仙女座星系\n~250萬光年", 640, True),
]

TICKS = [(-4, "0.1 mm"), (-3, "1 mm"), (-2, "1 cm"), (-1, "10 cm"), (0, "1 m"), (1, "10 m"), (2, "100 m"),
         (3, "1 km"), (4, "10 km"), (5, "100 km"), (6, "1千 km"), (7, "1萬 km"), (8, "10萬 km"),
         (9, "100萬 km"), (10, "1千萬 km"), (11, "1億 km"), (12, "10億 km"), (13, "100億 km"),
         (14, "1千億 km"), (15, "1兆 km")]
_ll = math.log10(LY)
for j, s in enumerate(["1 光年", "10 光年", "100 光年", "1千 光年", "1萬 光年", "10萬 光年", "100萬 光年",
                       "1千萬 光年", "1億 光年", "10億 光年", "100億 光年", "1千億 光年"]):
    TICKS.append((_ll + j, s))

BG_STOPS = [(-4, (95, 165, 230), (175, 218, 250)), (2, (70, 140, 220), (150, 200, 245)),
            (4, (25, 50, 120), (70, 120, 200)), (5.3, (8, 12, 35), (20, 35, 80)),
            (7, (3, 5, 15), (8, 12, 30)), (19, (5, 5, 18), (12, 8, 30)),
            (21, (22, 8, 42), (38, 15, 62)), (25, (10, 5, 30), (28, 10, 50)), (27.5, (28, 6, 50), (65, 22, 90))]

def bg_for(L):
    for (l0, a0, b0), (l1, a1, b1) in zip(BG_STOPS, BG_STOPS[1:]):
        if L <= l1:
            p = ease((L - l0) / (l1 - l0))
            return lerpc(a0, a1, p), lerpc(b0, b1, p)
    return BG_STOPS[-1][1], BG_STOPS[-1][2]

# ---------- 折紙俯視動畫 ----------
def paper_dims(w, h, k):
    dims = [(w, h)]
    for _ in range(k):
        w, h = dims[-1]
        dims.append((w, h / 2) if h >= w else (w / 2, h))
    return dims

def draw_fold(d, cx, cy, w0, h0, fold_times, t, dur=0.8):
    dims = paper_dims(w0, h0, len(fold_times))
    k = sum(1 for tf in fold_times if t >= tf + dur)
    cur = None
    for i, tf in enumerate(fold_times):
        if tf <= t < tf + dur:
            cur = (i, (t - tf) / dur)
    edge = A((150, 150, 140), 1)
    if cur is None:
        w, h = dims[k]
        d.rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), fill=A(PAPER, 1), outline=edge, width=3)
        return k
    i, p = cur
    w, h = dims[i]
    e = ease(p)
    shade = lerpc(PAPER, (205, 205, 195), math.sin(math.pi * p))
    if h >= w:  # 上半往下折
        L = cy - h / 4 * e
        d.rectangle((cx - w / 2, L, cx + w / 2, L + h / 2), fill=A(PAPER, 1), outline=edge, width=3)
        c = (h / 2) * math.cos(math.pi * e)
        box = (cx - w / 2, L - c, cx + w / 2, L) if c > 0 else (cx - w / 2, L, cx + w / 2, L - c)
    else:       # 右半往左折
        L = cx + w / 4 * e
        d.rectangle((L - w / 2, cy - h / 2, L, cy + h / 2), fill=A(PAPER, 1), outline=edge, width=3)
        c = (w / 2) * math.cos(math.pi * e)
        box = (L, cy - h / 2, L + c, cy + h / 2) if c > 0 else (L + c, cy - h / 2, L, cy + h / 2)
    d.rectangle(box, fill=A(shade, 1), outline=edge, width=3)
    return i + (1 if p > 0.5 else 0)

# ---------- S3 ----------
def n_at(t):
    for (t0, n0), (t1, n1) in zip(KEYS, KEYS[1:]):
        if t0 <= t <= t1:
            return lerp(n0, n1, ease((t - t0) / (t1 - t0))) if n1 != n0 else n0
    return KEYS[-1][1]

PPD = 230
Y0 = 1060

# ---------- 場景 ----------
def scene1(t, ov, d):
    out = vis(t, 0, 6.0, 0.4, 0.5)
    text(d, (540, 330), "一張 A4 紙", 92, WHITE, vis(t, 0.2) * out, rise=30)
    pa = eout((t - 0.4) / 0.6) * out
    if pa > 0:
        s = 0.7 + 0.3 * pa
        w, h = 300 * s, 424 * s
        cy = 760
        d.rounded_rectangle((540 - w / 2 + 14, cy - h / 2 + 14, 540 + w / 2 + 14, cy + h / 2 + 14), 6, fill=A((0, 0, 0), 0.35 * pa))
        d.rectangle((540 - w / 2, cy - h / 2, 540 + w / 2, cy + h / 2), fill=A(PAPER, pa))
        for i in range(9):
            yy = cy - h / 2 + 60 * s + i * 36 * s
            d.line((540 - w / 2 + 40 * s, yy, 540 + w / 2 - (40 + (i % 3) * 30) * s, yy), fill=A((190, 195, 205), pa), width=4)
        text(d, (540, cy), "A4", 70 * s, (90, 100, 130), pa * 0.9)
        text(d, (540, cy + h / 2 + 50), "厚度約 0.1 mm", 40, SOFT, vis(t, 1.0) * out)
    text(d, (540, 1180), "對折 100 次", 118, YEL, vis(t, 1.4) * out, rise=40)
    text(d, (540, 1320), "會有多高？", 100, WHITE, vis(t, 2.1) * out, rise=40)
    text(d, (540, 1480), "先猜猜看 ——", 48, CYAN, vis(t, 3.0) * out)
    for i, s in enumerate(["A. 比台北101還高", "B. 可以到月球", "C. 飛到宇宙深處"]):
        a = vis(t, 3.3 + i * 0.4) * out
        card(d, (240, 1545 + i * 92, 840, 1625 + i * 92), a, 30, op=0.55)
        text(d, (540, 1585 + i * 92), s, 46, WHITE, a)

def scene2(t, ov, d):
    out = vis(t, 6.0, 18.0, 0.4, 0.5)
    text(d, (540, 190), "規則很簡單", 76, YEL, vis(t, 6.0) * out, rise=30)
    text(d, (540, 285), "一張紙厚約 0.1 mm（差不多一根頭髮粗）", 42, WHITE, vis(t, 6.5) * out)
    text(d, (540, 345), "每對折一次，厚度就變 2 倍", 42, WHITE, vis(t, 7.0) * out)
    pa = vis(t, 7.2, 18.0, 0.4, 0.5)
    if pa > 0:
        k = draw_fold(d, 540, 700, 280, 396, S2_FOLDS, t)
        text(d, (540, 460), "從上面看", 32, SOFT, pa)
        # 側面堆疊
        text(d, (540, 1000), "從側面看（放大）", 32, SOFT, pa)
        prog = k
        for i, tf in enumerate(S2_FOLDS):
            if tf <= t < tf + 0.8:
                prog = i + ease((t - tf) / 0.8)
        layers = 2 ** prog
        th = 6 * layers
        base = 1370
        d.rectangle((360, base - th, 720, base), fill=A(PAPER, pa))
        nl = int(round(layers))
        for j in range(1, nl):
            yy = base - j * th / layers
            d.line((360, yy, 720, yy), fill=A((175, 175, 165), pa), width=1)
        d.line((300, base, 780, base), fill=A(SOFT, pa * 0.6), width=2)
        # 厚度標尺
        d.line((750, base, 750, base - th), fill=A(YEL, pa), width=4)
        mm = 0.1 * 2 ** k
        rich(d, 540, 1450, [(f"第 {k} 次", 'n', CYAN), ("  →  2", 'n'), (str(k), 'u'), (f" 層  →  {mm:g} mm", 'n')], 50, WHITE, pa)
    fa = vis(t, 16.0, 18.0, 0.4, 0.5)
    card(d, (110, 1580, 970, 1820), fa)
    rich(d, 540, 1655, [("高度 = 0.1 mm × 2", 'n'), ("n", 'u')], 64, YEL, fa)
    text(d, (540, 1755), "n = 對折次數", 40, SOFT, fa)

def scene3(t, base, ov, d):
    n = n_at(t)
    h = 1e-4 * 2 ** n
    L = math.log10(h)
    top, bot = bg_for(L)
    base.paste(grad(top, bot))
    out = vis(t, S3_START, S3_END + 0.3, 0.4, 0.5)
    stars(d, t, clamp((L - 4) / 2.5) * out, scroll=L * PPD * 0.3)
    y_of = lambda hh: Y0 - (math.log10(hh) - L) * PPD
    dark = L < 3.2
    ink = (20, 30, 60) if dark else WHITE
    # 刻度
    d.line((80, 0, 80, H), fill=A(ink, 0.5 * out), width=3)
    for lv, lab in TICKS:
        y = Y0 - (lv - L) * PPD
        if -40 < y < H + 40:
            d.line((80, y, 110, y), fill=A(ink, 0.7 * out), width=3)
            text(d, (120, y), lab, 28, ink, 0.85 * out, anchor="lm")
        for m in range(2, 10):
            ym = Y0 - (lv + math.log10(m) - L) * PPD
            if lv < 15.5 and 0 < ym < H:
                d.line((80, ym, 94, ym), fill=A(ink, 0.35 * out), width=2)
    # 參考物
    for hh, kind, lab, x, center in OBJS:
        y = y_of(hh)
        if -200 < y < H + 200:
            d.line((300, y, 1060, y), fill=A(ink, 0.22 * out), width=2)
            icon(d, kind, x, y, out)
            lines = lab.split("\n")
            for i, s in enumerate(lines):
                text(d, (800, y - 22 + i * 40 if not center else y - 20 * (len(lines) - 1) + i * 40), s, 32, ink, out, anchor="lm")
    # 紙堆柱
    yb = min(H + 10, y_of(1e-4) if L - (-4) < 10 else H + 10)
    d.rectangle((330, Y0, 410, yb), fill=A(PAPER, out), outline=A((150, 150, 140), out), width=2)
    for k in range(0, int((yb - Y0) / 18) + 1):
        yy = Y0 + k * 18
        d.line((332, yy, 408, yy), fill=A((215, 215, 205), out), width=1)
    d.line((80, Y0, 470, Y0), fill=A(YEL, out), width=5)
    d.polygon([(480, Y0), (505, Y0 - 14), (505, Y0 + 14)], fill=A(YEL, out))
    # 上方 HUD
    card(d, (150, 50, 930, 370), out, op=0.72)
    text(d, (540, 100), "對折次數", 40, SOFT, out)
    text(d, (540, 205), f"{int(n + 1e-6)}", 150, YEL, out)
    rich(d, 540, 318, [("高度  ", 'n', SOFT)] + fmt_h(1e-4 * 2 ** int(n + 1e-6)), 54, WHITE, out)
    # 里程碑卡
    for (mn, t1, t2), tm in zip(MILESTONES, MILESTONE_TIMES):
        a = vis(t, tm, tm + HOLD - 0.05, 0.3, 0.35)
        if a > 0:
            pop = eout((t - tm) / 0.35)
            dy = (1 - pop) * 60
            card(d, (60, 1490 + dy, 1020, 1810 + dy), a, op=0.82)
            rich(d, 540, 1565 + dy, [(f"第 {mn} 次 ｜ ", 'n', CYAN)] + fmt_h(1e-4 * 2 ** mn), 58, YEL, a)
            text(d, (540, 1660 + dy), t1, 52, WHITE, a)
            text(d, (540, 1745 + dy), t2, 36, SOFT, a)
    # 開場提示
    text(d, (540, 1650), "開始往上疊！", 64, (20, 30, 60), vis(t, S3_START + 0.1, S3_START + S3_INTRO + 0.6, 0.3, 0.4))

def warp(d, t, p):
    cx, cy = 540, 960
    for i, (x, y, r, b, ph) in enumerate(STARS[:200]):
        ang = math.atan2(y - cy, x - cx)
        dist = (math.hypot(x - cx, y - cy) + t * 900 * (0.3 + p * 3) * (r / 3)) % 1100
        l = 20 + p * 260 * (dist / 1100)
        x0, y0 = cx + dist * math.cos(ang), cy + dist * math.sin(ang)
        x1, y1 = cx + (dist + l) * math.cos(ang), cy + (dist + l) * math.sin(ang)
        d.line((x0, y0, x1, y1), fill=A((200, 220, 255), (0.3 + 0.7 * p) * b), width=max(1, int(r * 0.8)))

def scene4(t, base, ov, d):
    base.paste(grad((6, 4, 20), (25, 10, 45)))
    out = vis(t, 60.0, 76.0, 0.3, 0.5)
    if t < HIT_TIME:
        stars(d, t, out)
        text(d, (540, 720), "最後 12 次，全速衝刺……", 64, WHITE, vis(t, 60.2, RISER_START + 0.4, 0.3, 0.3))
        text(d, (540, 860), "對折到第 100 次！", 100, YEL, vis(t, 60.8, RISER_START + 0.4, 0.3, 0.3), rise=30)
        if t >= RISER_START:
            p = clamp((t - RISER_START) / (HIT_TIME - RISER_START))
            warp(d, t, p)
            n = int(88 + 12 * p ** 1.6 + 1e-6)
            sh = 14 * p
            ox = math.sin(t * 91) * sh; oy = math.cos(t * 77) * sh
            card(d, (140 + ox, 700 + oy, 940 + ox, 1220 + oy), 1, op=0.7)
            text(d, (540 + ox, 780 + oy), "對折次數", 44, SOFT)
            text(d, (540 + ox, 900 + oy), f"{n}", 170, YEL)
            rich(d, 540 + ox, 1110 + oy, fmt_h(1e-4 * 2 ** n), 72, WHITE)
        return
    stars(d, t, out * 0.7)
    flash = clamp(1 - (t - HIT_TIME) / 0.5)
    a1 = vis(t, HIT_TIME, 71.0, 0.05, 0.4)
    text(d, (540, 330), "對折 100 次的高度", 54, SOFT, a1)
    sc = 1 + 0.25 * (1 - eout((t - HIT_TIME) / 0.5))
    text(d, (540, 500), "134 億光年", 140 * sc, YEL, a1)
    rich(d, 540, 650, [("≈ 1.27 × 10", 'n'), ("26", 'u'), (" 公尺", 'n')], 52, WHITE, vis(t, 66.5, 71.0))
    a = vis(t, 67.2, 71.0)
    card(d, (60, 790, 1020, 1240), a)
    text(d, (540, 860), "寫成數字是……", 40, CYAN, a)
    digits = "126,765,060,022,822,940,149,670,320"
    k = int(len(digits) * clamp((t - 67.5) / 1.6))
    text(d, (540, 970), digits[:20][:k], 62, WHITE, a)
    text(d, (540, 1060), digits[20:][:max(0, k - 20)], 62, WHITE, a)
    text(d, (540, 1160), "公尺（27 位數）", 40, SOFT, vis(t, 69.2, 71.0))
    a2 = vis(t, 71.0, 76.0, 0.4, 0.5)
    text(d, (540, 300), "宇宙誕生至今約 138 億年", 50, WHITE, a2, rise=20)
    text(d, (540, 380), "光從那時一路跑到今天 ≈ 138 億光年", 46, SOFT, a2, rise=20)
    a3 = vis(t, 72.0, 76.0, 0.4, 0.5)
    card(d, (60, 480, 1020, 860), a3)
    text(d, (540, 560), "這疊紙：134 億光年", 66, YEL, a3)
    text(d, (540, 670), "≈ 光跑完整部宇宙歷史的距離！", 50, PINK, a3)
    text(d, (540, 770), "（約是可觀測宇宙直徑 930 億光年的 1/7）", 32, SOFT, a3)
    a4 = vis(t, 73.4, 76.0, 0.4, 0.5)
    card(d, (60, 940, 1020, 1300), a4)
    text(d, (540, 1000), "再比一個：", 40, CYAN, a4)
    rich(d, 540, 1100, [("紙的層數 2", 'n'), ("100", 'u'), (" ≈ 1.27 × 10", 'n'), ("30", 'u'), (" 層", 'n')], 50, WHITE, a4)
    rich(d, 540, 1200, [("比全宇宙星星總數（估計約 10", 'n'), ("22", 'u'), ("～10", 'n'), ("24", 'u'), (" 顆）還多", 'n')], 36, SOFT, a4)
    text(d, (540, 1450), "只折 100 次，就到了宇宙深處", 58, YEL, vis(t, 74.4, 76.0, 0.4, 0.5), rise=30)
    if flash > 0:
        d.rectangle((0, 0, W, H), fill=A((255, 255, 255), flash * 0.9))

def scene5(t, base, ov, d):
    base.paste(grad((14, 23, 42), (32, 50, 88)))
    out = vis(t, 76.0, 87.0, 0.4, 0.5)
    text(d, (540, 230), "回到現實……", 84, WHITE, vis(t, 76.1) * out, rise=30)
    pa = vis(t, 76.6) * out
    if pa > 0:
        k = draw_fold(d, 540, 640, 340, 480, S5_FOLDS, t, dur=0.42)
        if t >= 77.0:
            text(d, (540, 940), f"第 {k} 次", 48, CYAN, pa)
    text(d, (540, 1060), "一般 A4 紙，徒手大概折 7 次就折不動", 44, WHITE, vis(t, 80.8) * out, rise=20)
    text(d, (540, 1135), "第 7 次：128 層、厚 1.28 cm", 40, SOFT, vis(t, 81.6) * out)
    text(d, (540, 1195), "面積卻只剩約 1.9 × 2.6 cm —— 像一顆方糖", 40, SOFT, vis(t, 82.2) * out)
    a = vis(t, 83.3) * out
    card(d, (80, 1360, 1000, 1720), a)
    text(d, (540, 1440), "世界紀錄：12 次", 66, YEL, a)
    text(d, (540, 1545), "2002 年，美國高中生 Britney Gallivan", 40, WHITE, a)
    text(d, (540, 1610), "用約 1.2 公里長的薄紙才辦到", 40, WHITE, a)
    text(d, (540, 1670), "（金氏世界紀錄）", 30, SOFT, a)

def scene6(t, base, ov, d):
    base.paste(grad((10, 14, 32), (40, 22, 70)))
    stars(d, t, 0.35)
    out = vis(t, 87.0, 96.0, 0.4, 1.2)
    text(d, (540, 250), "每次只是 ×2", 96, YEL, vis(t, 87.2) * out, rise=30)
    text(d, (540, 380), "這就是「指數成長」", 62, WHITE, vis(t, 87.7) * out)
    rows = [(10, "10 公分"), (27, "超過聖母峰"), (42, "到月球"), (83, "橫跨銀河系"), (100, "134 億光年")]
    for i, (n, s) in enumerate(rows):
        a = vis(t, 88.2 + i * 0.45) * out
        y = 560 + i * 115
        text(d, (90, y), f"第 {n} 次", 42, CYAN, a, anchor="lm")
        bw = (14 + 466 * n / 100) * eout((t - 88.2 - i * 0.45) / 0.6)
        if a > 0:
            d.rounded_rectangle((330, y - 18, 330 + bw, y + 18), 18, fill=A(YEL if n == 100 else (120, 170, 255), a))
        if "^" in s:
            segs = [("10", 'n'), ("297", 'u'), (" 公尺", 'n')]
            fN = F(40); w = fN.getlength("10 公尺") + F(22).getlength("297") + 6
            rich(d, 330 + bw + 20 + w / 2, y, segs, 40, WHITE, a)
        else:
            text(d, (330 + bw + 20, y), s, 40, WHITE, a, anchor="lm")
    text(d, (540, 1150), "長條＝折的次數，只是穩定往上加", 34, SOFT, vis(t, 90.4) * out)
    text(d, (540, 1230), "開頭很無感，後面超驚人", 62, PINK, vis(t, 91.0) * out, rise=20)
    text(d, (540, 1320), "複利、病毒擴散、晶片電晶體數量……都是同一個道理", 34, SOFT, vis(t, 91.6) * out)
    a = vis(t, 92.8) * out
    card(d, (90, 1470, 990, 1760), a)
    rich(d, 540, 1560, [("對折 100 次 ≈ 134 億光年", 'n')], 64, YEL, a)
    rich(d, 540, 1670, [("≈ 光從宇宙誕生跑到今天的距離", 'n')], 46, WHITE, a)

def frame(t):
    base = grad((14, 23, 42), (32, 50, 88))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    if t < 6.0:
        scene1(t, ov, d)
    elif t < S3_START:
        scene2(t, ov, d)
    elif t < 60.0:
        scene3(t, base, ov, d)
    elif t < 76.0:
        scene4(t, base, ov, d)
    elif t < 87.0:
        scene5(t, base, ov, d)
    else:
        scene6(t, base, ov, d)
    base.alpha_composite(ov)
    if t > 95.8:
        blk = Image.new("RGBA", (W, H), (0, 0, 0, int(255 * clamp((t - 95.8) / 1.2))))
        base.alpha_composite(blk)
    return base.convert("RGB")

if __name__ == "__main__":
    if sys.argv[1] == "still":
        for s in sys.argv[2:]:
            frame(float(s)).save(f"still_{s}.png")
        sys.exit()
    idx, nch = int(sys.argv[1]), int(sys.argv[2])
    total = int(DUR * FPS)
    a, b = total * idx // nch, total * (idx + 1) // nch
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                          "-crf", "19", "-pix_fmt", "yuv420p", f"seg_{idx}.mp4"], stdin=subprocess.PIPE)
    for f in range(a, b):
        p.stdin.write(frame(f / FPS).tobytes())
    p.stdin.close(); p.wait()
