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

# ---------- palette (海洋) ----------
BG1, BG2 = (10, 34, 54), (16, 56, 84)
SEA = (22, 64, 96); LAND = (226, 210, 168); LANDE = (170, 152, 112)
Y = (255, 201, 60); C = (255, 107, 107); M = (78, 205, 196); WH = (245, 247, 250)
G = (150, 170, 190); P = (180, 150, 250); DK = (8, 24, 40); BGC = (14, 44, 68); GRN = (110, 200, 120)
INK = WH; RED = C; GOLD = Y; GR = G
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
    v = np.exp(-(((xx - 960) / 1100) ** 2 + ((yy - 480) / 700) ** 2)) * 16
    arr = arr + v[..., None] * np.array([0.5, 0.8, 1.0])
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
    if w < 2 or h < 2: return  # 動畫起點寬度為 0 時 PIL 會報錯
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


# ======================= 地理：地圖投影 =======================
def A(t, t0, d=0.45): return eo((t - t0) / d)

# ---- 國界資料（Natural Earth 1:110m）----
GEO = json.load(open(f"{D}/countries.geojson"))
COUNTRIES = []  # (name, continent, [np.array(N,2) lon/lat])
for f in GEO["features"]:
    pr = f["properties"]; g = f["geometry"]
    if pr["CONTINENT"] == "Antarctica": continue
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    rings = [np.array(p[0], float) for p in polys]
    COUNTRIES.append((pr["NAME"], pr["CONTINENT"], rings))
def rings_of(name): return [r for n, _, rs in COUNTRIES if n == name for r in rs]
AFRICA = [r for n, c, rs in COUNTRIES if c == "Africa" for r in rs]
GREEN = rings_of("Greenland"); RUSSIA = rings_of("Russia")

MS = 190; MCX, MCY = 960, 500; YMID = 0.76
def merc(ll, s=MS, cx=MCX, cy=MCY):
    lon = np.radians(ll[:, 0]); lat = np.radians(np.clip(ll[:, 1], -84, 84))
    return np.stack([cx + s * lon, cy - s * (np.log(np.tan(np.pi / 4 + lat / 2)) - YMID)], 1)

def moll(ll, R=255, cx=MCX, cy=MCY + 20):
    lon = np.radians(ll[:, 0]); lat = np.radians(ll[:, 1]); th = lat.copy()
    for _ in range(12):
        f = 2 * th + np.sin(2 * th) - np.pi * np.sin(lat); th -= f / (2 + 2 * np.cos(2 * th) + 1e-9)
    return np.stack([cx + 2 * np.sqrt(2) / np.pi * R * lon * np.cos(th), cy - np.sqrt(2) * R * np.sin(th)], 1)

def proj(ll, mix_=0.):
    a = merc(ll)
    if mix_ <= 0: return a
    b = moll(ll); return a * (1 - mix_) + b * mix_

def draw_rings(d, rings, fill, outline=None, k=0., sc=1., off=(0, 0)):
    for r in rings:
        p = proj(r, k) * sc + np.array(off)
        if len(p) > 2: d.polygon([tuple(q) for q in p], fill=fill, outline=outline)

_base = {}
def basemap(k=0., alpha=1., sea=True):
    key = round(k, 3)
    if key not in _base:
        im = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        # sea frame
        if k <= 0:
            x0, y0 = merc(np.array([[-180, 84]]))[0] * 2; x1, y1 = merc(np.array([[180, -60]]))[0] * 2
            d.rectangle((x0, y0, x1, y1), fill=SEA + (255,))
        else:
            edge = np.array([[-180, la] for la in range(-90, 91, 3)] + [[180, la] for la in range(90, -91, -3)], float)
            pa = proj(edge, k) * 2; d.polygon([tuple(q) for q in pa], fill=SEA + (255,))
        # graticule
        for lo in range(-180, 181, 30):
            pts = proj(np.array([[lo, la] for la in range(-60, 85, 2)], float), k) * 2
            d.line([tuple(q) for q in pts], fill=(50, 96, 130, 255), width=2)
        for la in range(-60, 81, 30):
            pts = proj(np.array([[lo, la] for lo in range(-180, 181, 3)], float), k) * 2
            d.line([tuple(q) for q in pts], fill=(50, 96, 130, 255) if la else (90, 140, 170, 255), width=2 if la else 3)
        for _, _, rs in COUNTRIES:
            for r in rs:
                p = proj(r, k) * 2
                d.polygon([tuple(q) for q in p], fill=LAND + (255,), outline=LANDE + (255,))
        if len(_base) > 40: _base.clear()
        _base[key] = im.resize((W, H), Image.LANCZOS)
    return _base[key]

def overlay(c, rings, col, a=1., k=0., sc=1., off=(0, 0), outline=None):
    im = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for r in rings:
        p = proj(r, k) * 2
        d.polygon([tuple(q) for q in p], fill=col + (int(255 * a),), outline=(outline + (int(255 * a),)) if outline else None)
    c.alpha_composite(im.resize((W, H), Image.LANCZOS))

def label(c, s, x, y, col=WH, sz=40, a=1., fill=DK):
    p = tpatch(s, sz, col, "K")
    box(c, x, y, p.width + 36, p.height + 22, fill, 210, 18, alpha=a)
    put(c, p, x, y, alpha=a)

def lonlat_xy(lon, lat, k=0.): return proj(np.array([[lon, lat]], float), k)[0]

def rotate_lat(rings, dlat, dlon):
    """沿經線把整塊陸地在球面上剛體旋轉 dlat 度，再繞地軸旋轉 dlon 度（真實大小比較用）"""
    allp = np.vstack(rings); lon0 = np.radians(allp[:, 0].mean())
    k = np.array([-np.sin(lon0), np.cos(lon0), 0.]); th = np.radians(-dlat)
    out = []
    for r in rings:
        lo, la = np.radians(r[:, 0]), np.radians(r[:, 1])
        v = np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], 1)
        v = v * np.cos(th) + np.cross(k, v) * np.sin(th) + np.outer(v @ k, k) * (1 - np.cos(th))
        la2 = np.degrees(np.arcsin(np.clip(v[:, 2], -1, 1))); lo2 = np.degrees(np.arctan2(v[:, 1], v[:, 0])) + dlon
        out.append(np.stack([lo2, la2], 1))
    return out

def globe(c, cx, cy, R, rot, a=1.):
    im = Image.new("RGBA", (2 * R + 4, 2 * R + 4), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse((2, 2, 2 * R + 2, 2 * R + 2), fill=SEA + (255,), outline=(120, 170, 200, 255), width=3)
    l0 = np.radians(rot); p0 = np.radians(15)
    for _, _, rs in COUNTRIES:
        for r in rs:
            lo, la = np.radians(r[:, 0]), np.radians(r[:, 1])
            cosc = np.sin(p0) * np.sin(la) + np.cos(p0) * np.cos(la) * np.cos(lo - l0)
            if (cosc > 0).mean() < .5: continue
            x = R * np.cos(la) * np.sin(lo - l0); y = R * (np.cos(p0) * np.sin(la) - np.sin(p0) * np.cos(la) * np.cos(lo - l0))
            pts = [(R + 2 + xx, R + 2 - yy) for xx, yy in zip(x, y)]
            if len(pts) > 2: d.polygon(pts, fill=LAND + (255,))
    put(c, im, cx, cy, alpha=a)

def sc_hook(c, t, S, L):
    a = A(t, 0, .5) * (1 - A(t, S[3] + 1.2, .4))
    if a > 0:
        put(c, basemap(), W / 2, H / 2, alpha=a)
        if t > S[0] + .3:
            ab = A(t, S[0] + .3) * a
            overlay(c, GREEN, C, .85 * ab); overlay(c, AFRICA, GRN, .85 * ab)
            label(c, "格陵蘭", *lonlat_xy(-42, 74) + [0, -10], C, 40, ab)
            label(c, "非洲", *lonlat_xy(20, 5), GRN, 40, ab * (1 - A(t, S[2], .3)))  # 數字框出現時淡出，避免透出
        if t > S[1]: text(c, "看起來差不多？", 1480, 180, 56, Y, "K", alpha=A(t, S[1]) * a)
        if t > S[2]:
            ab = A(t, S[2], .4) * a
            box(c, 960, 520, 1100, 300, DK, 225, 30, alpha=ab)
            text(c, "非洲 ≈ 14 × 格陵蘭", 960, 450, 92, Y, "K", alpha=ab, scale=.9 + .1 * eob(ab))
            bw = 900
            gw = bw * eo(A(t, S[2] + .4, 1.)); box(c, 510 + gw / 2, 560, gw, 40, GRN, 255, 12, alpha=ab)  # 由左往右長
            box(c, 510 + bw / 28, 620, bw / 14, 40, C, 255, 12, alpha=ab)
            text(c, "非洲 約 3,037 萬 km²", 520, 600 - 100, 0 + 30, WH, "B", anc="lm", alpha=0)
            text(c, "非洲 3,037 萬 km²", 1420, 560, 30, WH, "B", anc="rm", alpha=ab)
            text(c, "格陵蘭 217 萬 km²", 600, 620, 30, WH, "B", anc="lm", alpha=ab)
    if t > S[3] + 1:
        ab = A(t, S[3] + 1.1, .5)
        text(c, "地圖投影", 960, 420, 170, Y, "K", alpha=ab, scale=.85 + .15 * eob(ab))
        text(c, "格陵蘭真的那麼大嗎？", 960, 590, 60, WH, "B", alpha=A(t, S[3] + 1.5))
        text(c, "高一地理｜地圖與地理技能", 960, 680, 40, G, "B", alpha=A(t, S[3] + 1.8))

def sc_why(c, t, S, L):
    rot = 60 + t * 18
    if t < S[1] - .2 or t > S[3]:
        ga = A(t, 0) if t < S[1] else A(t, S[3])
        globe(c, 960, 470, 300, rot, ga)
    if t < S[1] - .2: text(c, "圓的地球", 960, 840, 50, WH, "K", alpha=A(t, .3) * (1 - A(t, S[1] - .5, .3)))
    if S[1] - .3 < t < S[3]:
        a = A(t, S[1] - .3) * (1 - A(t, S[3] - .3, .3))
        sp = eo(A(t, S[1] + .3, 1.6))
        for i in range(8):
            x = 960 + (i - 3.5) * (40 + 140 * sp); w = 150 + 0 * sp
            im = Image.new("RGBA", (int(w), 520), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            d.ellipse((0, 0, w - 1, 519), fill=(255, 160, 60, 255), outline=(220, 120, 30, 255), width=4)
            put(c, im, x, 470, alpha=a, scale=1 - .0 * sp)
        text(c, "壓平橘子皮：不是裂開，就是拉長", 960, 820, 48, Y, "K", alpha=A(t, S[1] + 1) * a)
        if t > S[2]:
            ab = A(t, S[2]) * a
            label(c, "犧牲什麼？", 620, 160, C, 44, ab); label(c, "保留什麼？", 1300, 160, M, 44, A(t, S[2] + .5) * a)
    if t > S[3]:
        ab = A(t, S[3] + .3)
        box(c, 960, 830, 820, 110, DK, 225, 24, alpha=ab, outline=Y, ow=4)
        text(c, "地圖投影 ＝ 把球面畫到平面", 960, 830, 52, Y, "K", alpha=ab)

def sc_merc(c, t, S, L):
    if t < S[1]:
        a = A(t, 0) * (1 - A(t, S[1] - .3, .3))
        text(c, "1569", 960, 330, 200, Y, "K", alpha=a, scale=.9 + .1 * eob(a))
        text(c, "麥卡托投影", 960, 520, 100, WH, "K", alpha=A(t, .4) * (1 - A(t, S[1] - .3, .3)))
        text(c, "Mercator projection", 960, 620, 44, G, "R", alpha=A(t, .7) * (1 - A(t, S[1] - .3, .3)))
    elif t < S[2] - .2:
        a = A(t, S[1]) * (1 - A(t, S[2] - .5, .3))
        globe(c, 960, 480, 220, 100 + t * 10, a)
        box(c, 960, 480, 470, 520, None, 0, 4, alpha=a, outline=Y, ow=4)
        for yy in (220, 740): put(c, rrect(470, 60, 30, None, 0, Y, 4), 960, yy, alpha=a)
        label(c, "圓筒", 1290, 300, Y, 40, a)
    if t > S[2] - .4:
        a = A(t, S[2] - .4, .5)
        put(c, basemap(), W / 2, H / 2, alpha=a)
        if t < S[3]:
            p = lonlat_xy(0, 30)
            ab = A(t, S[2]) * (1 - A(t, S[3] - .2, .3))
            put(c, circ(14, Y), *p, alpha=ab); label(c, "經緯線垂直 90°", p[0] + 230, p[1] - 60, Y, 36, ab)
            label(c, "正形投影：角度正確", 960, 170, Y, 48, A(t, S[2] + .6) * (1 - A(t, S[3] - .2, .3)))
        if t > S[3] - .1:
            ab = A(t, S[3] - .1)
            p0 = lonlat_xy(-9.1, 38.7); p1 = lonlat_xy(-66, 18)  # 里斯本 → 加勒比海
            pr = eo(clamp((t - S[3]) / 3.5))
            q = p0 + (p1 - p0) * pr
            line(c, tuple(p0), tuple(q), Y, 6, ab)
            put(c, circ(12, WH), *p0, alpha=ab); put(c, circ(16, Y), *q, alpha=ab)
            label(c, "里斯本", p0[0] + 70, p0[1] - 40, WH, 30, ab)
            label(c, "固定羅盤方位＝地圖上的直線", 960, 170, Y, 46, ab)
        if t > S[4]:
            label(c, "大航海時代．船長必備", 960, 830, WH, 46, A(t, S[4]))

def sc_cost(c, t, S, L):
    put(c, basemap(), W / 2, H / 2, alpha=A(t, 0) * .55)
    grow = eo(A(t, S[2] - .5, 2.2)) if t > S[1] else 0
    vis = A(t, S[1] - .2)
    if t > S[1] - .2:
        r0 = 18
        for la in (0, 30, 60, 75, -30, -60):
            for lo in range(-150, 181, 60):
                x, y = lonlat_xy(lo, la)
                k = 1 / math.cos(math.radians(la)); r = r0 * (1 + (k - 1) * grow)
                put(c, circ(max(2, int(r)), C, 170), x, y, alpha=vis)
        for la, s_ in ((0, "×1"), (30, "×1.3"), (60, "×4"), (75, "×15")):
            if t > S[2] + (0 if la < 70 else 1.8):
                x, y = lonlat_xy(180, la)
                label(c, s_, x + 70, y, Y if la >= 60 else WH, 34, A(t, S[2] + (0 if la < 70 else 1.8)))
    if t < S[1] + .3: label(c, "緯度越高，面積放越大", 960, 170, Y, 50, A(t, .2))
    else: label(c, "地球上一樣大的圓", 960, 170, WH, 46, A(t, S[1] + .3) * (1 - A(t, S[4] - .3, .3)))
    if t > S[4]:
        a = A(t, S[4]); x, y = lonlat_xy(121, 23.5)
        put(c, circ(14, Y), x, y, alpha=a)
        label(c, "台灣（約北緯 23.5°）≈ ×1.2", x - 150, y - 70, Y, 38, a)

def sc_true(c, t, S, L):
    put(c, basemap(), W / 2, H / 2, alpha=A(t, 0))
    overlay(c, GREEN, C, .35 * A(t, 0))
    pr = eo(clamp((t - S[0] - .6) / (S[2] - S[0] - .8))) if t > S[0] + .6 else 0
    target_lat, target_dlon = 0 - 72 + 8, 14  # 中心約 72°N → 赤道附近，向東移到巴西與非洲之間的大西洋
    g2 = rotate_lat(GREEN, (target_lat) * pr, target_dlon * pr)
    overlay(c, g2, C, .95, outline=WH)
    gp = proj(np.vstack(g2)); cxy = gp.mean(0)
    a2 = A(t, S[2]) if t > S[2] else 0
    label(c, "格陵蘭", cxy[0], gp[:, 1].min() - 34 - 90 * (1 - pr), C, 34, 1 - a2)
    if t > S[2]:
        a = a2; overlay(c, AFRICA, GRN, .8 * a)
        label(c, "非洲 3,037 萬 km²", *lonlat_xy(26, -19), GRN, 34, a)
        lx, ly = 520, 720  # 太平洋空白處，用引線指回格陵蘭
        line(c, (lx + 150, ly - 10), (gp[:, 0].min() + 4, cxy[1]), C, 3, a)
        put(c, circ(6, C), gp[:, 0].min() + 4, cxy[1], alpha=a)
        label(c, "格陵蘭 217 萬 km²", lx, ly, C, 32, a)
    if t > S[3]:
        a = A(t, S[3]); overlay(c, RUSSIA, P, .85 * a)
        box(c, 960, 860, 1240, 150, DK, 225, 24, alpha=a)
        for i, (nm, v, col) in enumerate((("非洲", 3037, GRN), ("俄羅斯", 1710, P))):
            y = 825 + i * 70; bw = 820 * v / 3037 * eo(A(t, S[3] + .3 + i * .3, .8))
            text(c, nm, 470, y, 36, col, "K", anc="rm", alpha=a)
            if bw > 10: box(c, 500 + bw / 2, y, bw, 40, col, 255, 10, alpha=a)
            text(c, f"{v:,} 萬 km²", 1340, y, 32, WH, "B", anc="lm", alpha=a)
    label(c, "把格陵蘭搬到赤道", 960, 150, Y, 48, A(t, .1) * (1 - A(t, S[3] - .3, .3)))

def sc_equal(c, t, S, L):
    k = eo(clamp((t - S[2] - .2) / 2.2)) if t > S[2] else 0
    put(c, basemap(round(k * 20) / 20), W / 2, H / 2, alpha=A(t, 0) * (.35 if t < S[2] else 1))
    if t < S[2] + .2:
        a = A(t, .1) * (1 - A(t, S[2], .3))
        text(c, "完全不變形的地圖？", 960, 220, 80, WH, "K", alpha=a)
        text(c, "沒有！", 960, 340, 100, C, "K", alpha=A(t, S[0] + 1.5, .3) * (1 - A(t, S[2], .3)), scale=1.3 - .3 * eo(A(t, S[0] + 1.5, .3)))
        for i, s_ in enumerate(("面積", "形狀", "距離", "方向")):
            ab = A(t, S[1] + i * .3) * (1 - A(t, S[2], .3))
            box(c, 450 + i * 340, 580, 280, 180, DK, 230, 24, alpha=ab, outline=Y, ow=3)
            text(c, s_, 450 + i * 340, 560, 64, WH, "K", alpha=ab)
            text(c, "無法全部正確" if i == 3 else "", 450 + i * 340, 640, 1 + 0, G, "B", alpha=0)
        text(c, "四者無法同時正確", 960, 760, 48, Y, "K", alpha=A(t, S[1] + 1.5) * (1 - A(t, S[2], .3)))
    if t > S[2]:
        lab = "麥卡托（正形）" if k < .5 else "等積投影（Mollweide）"
        label(c, lab, 960, 110, Y, 46, A(t, S[2]))
        if k > .95:
            overlay(c, GREEN, C, .85, k=1.); overlay(c, AFRICA, GRN, .85, k=1.)
            label(c, "面積對了，形狀被拉歪", 960, 880, Y, 44, A(t, S[2] + 2.6) * (1 - A(t, S[3] - .35, .3)))
    if t > S[3]:
        a = A(t, S[3]); box(c, 960, 880, 1150, 100, DK, 235, 24, alpha=a, outline=Y, ow=4)
        text(c, "重點：你要拿地圖來做什麼？", 960, 880, 52, Y, "K", alpha=a)

def sc_exam(c, t, S, L):
    text(c, "考試重點", 960, 150, 84, WH, "K", alpha=A(t, .1))
    rows = [("麥卡托", "正形投影：角度正確 → 航海", Y, S[1]), ("缺點", "高緯度面積放大 → 不適合比面積", C, S[2]),
            ("分布圖", "人口、物產 → 等積投影", M, S[3])]
    for i, (k_, v, col, t0) in enumerate(rows):
        if t < t0 - .1: continue
        a = A(t, t0 - .1, .4); y = 330 + i * 190
        box(c, 960, y, 1400, 150, DK, 230, 26, alpha=a, scale=.92 + .08 * eob(a), outline=col, ow=4)
        text(c, k_, 330, y, 60, col, "K", anc="lm", alpha=a)
        text(c, v, 640, y, 50, WH, "B", anc="lm", alpha=a)

def sc_end(c, t, S, L):
    a = A(t, .1)
    box(c, 600, 480, 420, 760, (30, 30, 36), 255, 50, alpha=a)
    sub = basemap().crop((560, 190, 900, 840)); put(c, sub.resize((360, 680)), 600, 480, alpha=a)
    label(c, "Web Mercator", 600, 820, Y, 32, a)
    text(c, "很多網路地圖", 1240, 330, 64, WH, "K", alpha=A(t, .4))
    text(c, "也用麥卡托家族", 1240, 420, 64, Y, "K", alpha=A(t, .7))
    if t > S[1]:
        ab = A(t, S[1]); box(c, 1240, 590, 820, 110, DK, 230, 24, alpha=ab, outline=M, ow=4)
        text(c, "每一張地圖，都有它的取捨", 1240, 590, 48, M, "K", alpha=ab)
    if t > S[2]:
        text(c, "想比哪個國家？留言！", 1240, 740, 52, WH, "K", alpha=A(t, S[2]))
        text(c, "下次見！", 1240, 840, 80, Y, "K", alpha=A(t, S[2] + 1.5), scale=.9 + .1 * eob(A(t, S[2] + 1.5, .5)))

DRAW = dict(hook=sc_hook, why=sc_why, merc=sc_merc, cost=sc_cost, true=sc_true, equal=sc_equal, exam=sc_exam, end=sc_end)

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
    put(c, tpatch("高一地理｜地圖投影", 30, G, "B"), 50, 50, "lm")
    put(c, tpatch("格陵蘭真的那麼大？", 30, Y, "K"), W - 50, 50, "rm")
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
