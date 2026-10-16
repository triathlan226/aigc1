#!/usr/bin/env python3
"""投資人短影音 renderer — 9:16 motion graphics (pycairo + ffmpeg + numpy music).

python3 render.py CONTENT.py fonttest OUT.png   check fonts render (no boxes / right weights)
python3 render.py CONTENT.py check              timeline, layout overflow, over-long text
python3 render.py CONTENT.py stills OUT.png     contact sheet (one frame per scene)
python3 render.py CONTENT.py frame T OUT.png    single frame at T seconds
python3 render.py CONTENT.py video OUT.mp4      full render (parallel) + music
"""
import cairo, math, os, subprocess, sys
from multiprocessing import Pool
import importlib.util

def _load(path):
    spec = importlib.util.spec_from_file_location("content", path); m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m); return m

CONTENT_PATH = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples", "jensen_bg2.py")
_C = _load(CONTENT_PATH)
SCENES, META = _C.SCENES, _C.META
WORK = os.path.join(os.path.dirname(CONTENT_PATH), "work_" + os.path.splitext(os.path.basename(CONTENT_PATH))[0])
os.makedirs(WORK, exist_ok=True)
META.setdefault("brand_left", "科技"); META.setdefault("brand_right", "人文"); META.setdefault("tagline", "事實 ｜ 推論 ｜ 觀點")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
W, H, FPS = 1080, 1920, 30
CX = W / 2
# 字型：預設 Noto CJK TC。若本機沒有，可在 CONTENT 的 META["fonts"] 覆寫，例如
# macOS: {"sans": "PingFang TC", "black": "PingFang TC", "med": "PingFang TC", "mono": "Menlo", "serif": "Songti TC"}
# Windows: {"sans": "Microsoft JhengHei", "black": "Microsoft JhengHei", "med": "Microsoft JhengHei", "mono": "Consolas", "serif": "MingLiU"}
_F = {"sans": "Noto Sans CJK TC", "black": "Noto Sans CJK TC Black", "med": "Noto Sans CJK TC Medium",
      "mono": "Noto Sans Mono CJK TC", "serif": "Noto Serif CJK TC Black"}
_F.update(META.get("fonts", {}))
SANS, BLACK, MED, MONO, SERIF = _F["sans"], _F["black"], _F["med"], _F["mono"], _F["serif"]
BG0, BG1 = (0.035, 0.047, 0.086), (0.067, 0.086, 0.149)
COL = {"green": (0.52, 0.86, 0.27), "cyan": (0.30, 0.82, 0.98), "amber": (1.00, 0.72, 0.30),
       "red": (1.00, 0.42, 0.40), "white": (0.97, 0.98, 0.99), "dim": (0.66, 0.71, 0.79),
       "faint": (0.40, 0.45, 0.54)}
TOP, BOTTOM = 560, 1640
SAFE = 960
BPM = 100
BEAT = 60 / BPM
WARN = []

def c(n): return COL[n] if isinstance(n, str) else n
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def seg(t, a, b): return clamp((t - a) / (b - a)) if b > a else float(t >= a)
def eo(x): return 1 - (1 - x) ** 3
def eio(x): return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2
def eback(x, s=1.6): x -= 1; return x * x * ((s + 1) * x + s) + 1
def lerp(a, b, x): return a + (b - a) * x

# ---------------- text ----------------
def font(ctx, fam, size):
    w = cairo.FONT_WEIGHT_BOLD if (fam == SANS or (fam == BLACK and BLACK == SANS)) else cairo.FONT_WEIGHT_NORMAL
    ctx.select_font_face(fam, cairo.FONT_SLANT_NORMAL, w); ctx.set_font_size(size)

def tw(ctx, s): return ctx.text_extents(s)[4]

def fitfont(ctx, fam, size, s, maxw, tag=""):
    font(ctx, fam, size); w = tw(ctx, s)
    if w > maxw:
        ns = size * maxw / w
        if ns < size * 0.85: WARN.append(f"[過長] {tag}「{s}」縮到 {ns/size:.0%}")
        font(ctx, fam, ns); return ns
    return size

def text(ctx, s, fam, size, x, y, col, a=1.0, maxw=SAFE, align="c", tag=""):
    """y is the visual centre line of CJK glyphs."""
    if a <= 0 or not s: return
    sz = fitfont(ctx, fam, size, s, maxw, tag)
    w = tw(ctx, s)
    xx = x - w / 2 if align == "c" else (x if align == "l" else x - w)
    ctx.set_source_rgba(*c(col), a)
    ctx.move_to(xx, y + sz * 0.36); ctx.show_text(s)
    return w

def rise(ctx, s, fam, size, x, y, col, p, a=1.0, maxw=SAFE, align="c", tag=""):
    if p <= 0: return
    text(ctx, s, fam, size, x, y + 36 * (1 - eo(p)), col, a * eo(p), maxw, align, tag)

def rrect(ctx, x, y, w, h, r):
    r = min(r, h / 2, w / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0); ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi); ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()

def pill(ctx, s, x, y, col, size, p, a=1.0, outline=False, fg=None):
    if p <= 0 or a <= 0: return
    sz = fitfont(ctx, SANS, size, s, SAFE - size * 1.4)
    w = tw(ctx, s) + sz * 1.4; h = sz * 1.75
    ctx.save(); ctx.translate(x, y); k = eback(clamp(p)); ctx.scale(k, k)
    rrect(ctx, -w / 2, -h / 2, w, h, h / 2)
    if outline:
        ctx.set_source_rgba(*c(col), 0.12 * a); ctx.fill_preserve()
        ctx.set_source_rgba(*c(col), a); ctx.set_line_width(4); ctx.stroke()
        ctx.set_source_rgba(*c(col), a)
    else:
        ctx.set_source_rgba(*c(col), a); ctx.fill(); ctx.set_source_rgba(*(fg or BG0), a)
    ctx.move_to(-tw(ctx, s) / 2, sz * 0.36); ctx.show_text(s); ctx.restore()

def panel(ctx, x, y, w, h, col, a, fill=0.10, r=22, bar=True):
    rrect(ctx, x, y, w, h, r)
    ctx.set_source_rgba(*c(col), fill * a); ctx.fill_preserve()
    ctx.set_source_rgba(*c(col), 0.55 * a); ctx.set_line_width(3); ctx.stroke()
    if bar:
        ctx.save(); rrect(ctx, x, y, w, h, r); ctx.clip()
        ctx.set_source_rgba(*c(col), a); ctx.rectangle(x, y, 9, h); ctx.fill(); ctx.restore()

# ---------------- blocks: (height, draw(ctx, b, y, lt, a)) ----------------
TS = {"XL": (84, 120), "L": (64, 96), "M": (50, 80), "S": (40, 64)}

def h_text(b): return TS[b.get("size", "M")][1]
def d_text(ctx, b, y, lt, a):
    sz, h = TS[b.get("size", "M")]
    fam = BLACK if b.get("size") in ("XL", "L") else (SANS if b.get("size", "M") == "M" else MED)
    rise(ctx, b["t"], fam, sz, CX, y + h / 2, b.get("color", "white"), seg(lt, 0, 0.45), a, tag=b["t"])

def h_pill(b): return 110
def d_pill(ctx, b, y, lt, a):
    pill(ctx, b["t"], CX, y + 55, b.get("color", "amber"), b.get("sz", 42), seg(lt, 0, 0.35), a, b.get("outline", False))

def h_quote(b): return 70 + 76 * len(b["lines"]) + 56
def d_quote(ctx, b, y, lt, a):
    p = eo(seg(lt, 0, 0.5)); col = b.get("color", "amber")
    if p <= 0: return
    hgt = h_quote(b) - 16
    ctx.save(); ctx.translate(-50 * (1 - p), 0)
    panel(ctx, 70, y, W - 140, hgt, col, a * p, 0.09)
    font(ctx, BLACK, 110); ctx.set_source_rgba(*c(col), 0.30 * a * p); ctx.move_to(W - 170, y + 112); ctx.show_text("“")
    for i, ln in enumerate(b["lines"]):
        rise(ctx, ln, SANS, 50, 130, y + 70 + i * 76, "white", seg(lt, 0.15 + 0.2 * i, 0.6 + 0.2 * i), a, W - 260, "l", ln)
    rise(ctx, "— " + b.get("who", "黃仁勳"), MED, 34, W - 120, y + hgt - 50, col, seg(lt, 0.5, 0.9), a, 500, "r")
    ctx.restore()

def h_cards(b): return b.get("h", 230) + 20
def d_cards(ctx, b, y, lt, a):
    items = b["items"]; n = len(items); gap = 28; ch = b.get("h", 230)
    cw = (W - 120 - gap * (n - 1)) / n
    for i, it in enumerate(items):
        p = seg(lt, 0.25 * i, 0.25 * i + 0.5)
        if p <= 0: continue
        col = it.get("color", "cyan"); x = 60 + i * (cw + gap)
        ctx.save(); ctx.translate(0, 50 * (1 - eo(p)))
        panel(ctx, x, y, cw, ch, col, a * eo(p), 0.11)
        bodysz = it.get("bsz", 64 if n == 2 else 50)
        text(ctx, it["head"], MED, 36 if n == 2 else 34, x + cw / 2 + 4, y + ch * 0.27, col, a * eo(p), cw - 50, tag=it["head"])
        text(ctx, it["body"], BLACK, bodysz, x + cw / 2 + 4, y + ch * 0.58, "white", a * eo(p), cw - 50, tag=it["body"])
        if it.get("sub"):
            text(ctx, it["sub"], MED, 30, x + cw / 2 + 4, y + ch * 0.83, "dim", a * eo(p), cw - 50, tag=it["sub"])
        ctx.restore()

def h_chain(b): return 130
def d_chain(ctx, b, y, lt, a):
    items = b["items"]; n = len(items); yc = y + 65
    sz = b.get("sz", 52 if n <= 3 else 44)
    font(ctx, BLACK, sz); ws = [tw(ctx, s) + 52 for s in items]; arrow = 70
    tot = sum(ws) + arrow * (n - 1)
    if tot > SAFE:
        k = SAFE / tot; sz *= k; ws = [w * k for w in ws]; arrow *= k; tot = SAFE
    x = CX - tot / 2
    for i, s in enumerate(items):
        p = seg(lt, i * 0.35, i * 0.35 + 0.4)
        col = c(b.get("last", "green")) if i == n - 1 else COL["white"]
        if p > 0:
            ctx.save(); ctx.translate(x + ws[i] / 2, yc); k = eback(p); ctx.scale(k, k)
            rrect(ctx, -ws[i] / 2, -sz * 0.95, ws[i], sz * 1.9, 18)
            ctx.set_source_rgba(*col, 0.12 * a); ctx.fill_preserve(); ctx.set_source_rgba(*col, 0.7 * a); ctx.set_line_width(3); ctx.stroke()
            font(ctx, BLACK, sz); ctx.set_source_rgba(*col, a); ctx.move_to(-tw(ctx, s) / 2, sz * 0.36); ctx.show_text(s)
            ctx.restore()
        x += ws[i]
        if i < n - 1:
            ap = seg(lt, i * 0.35 + 0.2, i * 0.35 + 0.5)
            if ap > 0:
                xs, xe = x + arrow * 0.18, x + arrow * 0.82; xm = lerp(xs, xe, eo(ap))
                ctx.set_source_rgba(*COL["amber"], a); ctx.set_line_width(6); ctx.set_line_cap(cairo.LINE_CAP_ROUND)
                ctx.move_to(xs, yc); ctx.line_to(xm - 6, yc); ctx.stroke()
                ctx.move_to(xm + 4, yc); ctx.line_to(xm - 14, yc - 14); ctx.line_to(xm - 14, yc + 14); ctx.close_path(); ctx.fill()
            x += arrow

def h_bignum(b): return 300 if b.get("cap") else 230
def d_bignum(ctx, b, y, lt, a):
    col = b.get("color", "green"); p = seg(lt, 0, 0.3)
    if "to" in b:
        v = lerp(b.get("from", 0), b["to"], eio(seg(lt, 0.1, 1.3)))
        s = f"{b.get('pre', '')}{v:,.{b.get('dec', 0)}f}{b.get('suf', '')}"
    else: s = b["v"]
    done = lt > 1.3 or "to" not in b
    k = 1 + 0.08 * math.exp(-max(0, lt - 1.3) * 9) if "to" in b and lt > 1.3 else 1
    ctx.save(); ctx.translate(CX, y + 110); ctx.scale(k, k)
    text(ctx, s, BLACK, b.get("sz", 190), 0, 0, col if done else "white", a * eo(p), tag=s)
    ctx.restore()
    if b.get("cap"): rise(ctx, b["cap"], MED, 38, CX, y + 255, "dim", seg(lt, 0.8, 1.2), a, tag=b["cap"])

def h_bars(b): return b.get("h", 470)
def d_bars(ctx, b, y, lt, a):
    items = b["items"]; n = len(items); hh = h_bars(b)
    base = y + hh - 70; top = y + 70; maxv = max(it[1] for it in items) * 1.0
    bw = min(220, (SAFE - 80) / n - 50); gap = (SAFE - n * bw) / (n + 1)
    ctx.set_source_rgba(*COL["faint"], 0.8 * a); ctx.rectangle(60, base, SAFE, 3); ctx.fill()
    for i, (lab, v, disp, col) in enumerate(items):
        p = eio(seg(lt, 0.2 + 0.35 * i, 1.0 + 0.35 * i))
        x = 60 + gap + i * (bw + gap); bh = (base - top - 40) * v / maxv * p
        if p > 0:
            g = cairo.LinearGradient(0, base - bh, 0, base)
            g.add_color_stop_rgba(0, *c(col), a); g.add_color_stop_rgba(1, *c(col), 0.45 * a)
            rrect(ctx, x, base - bh, bw, bh + 12, 14); ctx.set_source(g); ctx.fill()
            ctx.set_source_rgba(*BG0, 1); ctx.rectangle(x - 2, base + 1.5, bw + 4, 14); ctx.fill()
            text(ctx, disp, BLACK, b.get("vsz", 54), x + bw / 2, base - bh - 42, col, a * seg(lt, 0.7 + 0.35 * i, 1.0 + 0.35 * i), bw + gap * 0.9, tag=disp)
        text(ctx, lab, MED, 36, x + bw / 2, base + 42, "dim", a * seg(lt, 0.1 + 0.35 * i, 0.4 + 0.35 * i), bw + gap * 0.9, tag=lab)

def h_donut(b): return 440
def d_donut(ctx, b, y, lt, a):
    items = b["items"]; tot = sum(it[1] for it in items)
    cx, cy, R, r = 250, y + 215, 190, 118
    p = eio(seg(lt, 0, 1.4)); ang = -math.pi / 2
    for i, (lab, v, sub, col) in enumerate(items):
        span = 2 * math.pi * v / tot
        e = min(ang + span, -math.pi / 2 + 2 * math.pi * p)
        if e > ang + 0.01:
            ctx.new_path(); ctx.arc(cx, cy, R, ang + 0.02, e - 0.02); ctx.arc_negative(cx, cy, r, e - 0.02, ang + 0.02); ctx.close_path()
            ctx.set_source_rgba(*c(col), a); ctx.fill()
        ang += span
        ly = y + 70 + i * 140; lp = seg(lt, 0.4 + 0.35 * i, 0.8 + 0.35 * i)
        if lp > 0:
            ctx.save(); ctx.translate(40 * (1 - eo(lp)), 0)
            ctx.set_source_rgba(*c(col), a * eo(lp)); rrect(ctx, 500, ly - 26, 16, 52, 8); ctx.fill()
            text(ctx, lab, SANS, 46, 540, ly - 6, "white", a * eo(lp), 500, "l", lab)
            text(ctx, sub, MED, 32, 540, ly + 44, col, a * eo(lp), 500, "l", sub)
            ctx.restore()
    text(ctx, b.get("center", ""), BLACK, 44, cx, cy - 22, "white", a * seg(lt, 1.0, 1.4))
    text(ctx, b.get("center2", ""), MED, 30, cx, cy + 30, "dim", a * seg(lt, 1.0, 1.4))

def h_compare(b): return 300
def d_compare(ctx, b, y, lt, a):
    L, R = b["left"], b["right"]; cy = y + 120
    p1 = seg(lt, 0, 0.4); p2 = seg(lt, 0.9, 1.3); ap = seg(lt, 0.4, 0.9)
    rise(ctx, L[0], MED, 34, 280, cy - 100, "dim", p1, a, 420)
    rise(ctx, L[1], BLACK, b.get("sz", 84), 280, cy, "dim", p1, a, 420, tag=L[1])
    rise(ctx, R[0], MED, 34, 800, cy - 100, b.get("color", "green"), p2, a, 420)
    ctx.save(); ctx.translate(800, cy); k = eback(p2) if p2 > 0 else 0; ctx.scale(max(k, 0.001), max(k, 0.001))
    text(ctx, R[1], BLACK, b.get("sz", 84), 0, 0, b.get("color", "green"), a * clamp(p2 * 2), 420, tag=R[1]); ctx.restore()
    if ap > 0:
        xs, xe = 500, 580; xm = lerp(xs, xe, eo(ap))
        ctx.set_source_rgba(*COL["amber"], a); ctx.set_line_width(7); ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.move_to(xs, cy); ctx.line_to(xm - 6, cy); ctx.stroke()
        ctx.move_to(xm + 6, cy); ctx.line_to(xm - 16, cy - 17); ctx.line_to(xm - 16, cy + 17); ctx.close_path(); ctx.fill()
    if b.get("cap"): rise(ctx, b["cap"], MED, 36, CX, cy + 135, "dim", seg(lt, 1.3, 1.7), a, tag=b["cap"])

def h_list(b): return len(b["items"]) * b.get("row", 128)
def d_list(ctx, b, y, lt, a):
    row = b.get("row", 128); col = b.get("color", "red")
    for i, it in enumerate(b["items"]):
        p = seg(lt, 0.45 * i, 0.45 * i + 0.45)
        if p <= 0: continue
        yy = y + i * row + row / 2 - 8; ctx.save(); ctx.translate(-60 * (1 - eo(p)), 0); al = a * eo(p)
        rrect(ctx, 60, yy - row / 2 + 14, SAFE, row - 20, 18); ctx.set_source_rgba(*c(col), 0.08 * al); ctx.fill()
        ctx.set_source_rgba(*c(col), al); ctx.arc(120, yy, 30, 0, 2 * math.pi); ctx.fill()
        text(ctx, str(i + 1), BLACK, 36, 120, yy, BG0, al)
        head, sub = it if isinstance(it, (list, tuple)) else (it, "")
        if sub:
            text(ctx, head, SANS, 44, 180, yy - 20, "white", al, SAFE - 150, "l", head)
            text(ctx, sub, MED, 33, 180, yy + 28, "dim", al, SAFE - 150, "l", sub)
        else:
            text(ctx, head, SANS, 44, 180, yy, "white", al, SAFE - 150, "l", head)
        ctx.restore()

def h_tags(b): return 110
def d_tags(ctx, b, y, lt, a):
    items = b["items"]; sz = 38; font(ctx, SANS, sz)
    ws = [tw(ctx, s) + 56 for s in items]; gap = 20; tot = sum(ws) + gap * (len(ws) - 1)
    if tot > SAFE:
        k = SAFE / tot; sz *= k; ws = [w * k for w in ws]; gap *= k; tot = SAFE
    x = CX - tot / 2
    for i, s in enumerate(items):
        p = seg(lt, 0.15 * i, 0.15 * i + 0.35)
        pill(ctx, s, x + ws[i] / 2, y + 55, b.get("color", "cyan"), sz, p, a, outline=True); x += ws[i] + gap

def h_gap(b): return b.get("h", 30)
def d_gap(ctx, b, y, lt, a): pass

BLOCKS = {k: (globals()["h_" + k], globals()["d_" + k]) for k in
          ("text", "pill", "quote", "cards", "chain", "bignum", "bars", "donut", "compare", "list", "tags", "gap")}

# ---------------- scenes ----------------
def layout(s):
    blocks = s.get("blocks", []); hs = [BLOCKS[b["type"]][0](b) for b in blocks]
    gap = s.get("gap", 34); tot = sum(hs) + gap * max(0, len(hs) - 1)
    y = TOP + max(0, (BOTTOM - TOP - tot)) * 0.42; ys = []
    for h in hs: ys.append(y); y += h + gap
    return ys, tot

def times(s):
    bl = s.get("blocks", []); D = s["dur"]; n = len(bl)
    step = (0.55 * D - 0.7) / max(1, n - 1) if n > 1 else 0
    step = clamp(step, 0.6, 2.6)
    return [b.get("at", 0.7 + i * step) for i, b in enumerate(bl)]

def sc_chapter(ctx, s, u, D):
    a = 1 - seg(u, D - 0.35, D); col = s.get("color", "green")
    p = eo(seg(u, 0.0, 0.5))
    # chapter badge
    pill(ctx, s["badge"], CX, 285, col, 34, seg(u, 0.05, 0.4), a)
    lines = s["title"] if isinstance(s["title"], list) else [s["title"]]
    for i, ln in enumerate(lines):
        yy = 415 + i * 92 - (46 if len(lines) == 2 else 0) + 20
        ctx.save(); ctx.rectangle(0, yy - 60, W, 120); ctx.clip()
        text(ctx, ln, BLACK, 76, CX, yy + 90 * (1 - eo(seg(u, 0.1 + 0.08 * i, 0.55 + 0.08 * i))), "white", a, tag=ln)
        ctx.restore()
    ly = 415 + (len(lines) - 1) * 92 - (46 if len(lines) == 2 else 0) + 20 + 68
    ctx.set_source_rgba(*c(col), a); rrect(ctx, CX - 70 * p, ly, 140 * p, 7, 3.5); ctx.fill()
    ys, _ = layout(s)
    for b, y, t0 in zip(s.get("blocks", []), ys, times(s)):
        if u >= t0: BLOCKS[b["type"]][1](ctx, b, y, u - t0, a)

def sc_hook(ctx, s, u, D):
    a = 1 - seg(u, D - 0.3, D); land = 2.0
    rise(ctx, s["label"], SANS, 54, CX, 640, "dim", seg(u, 0.1, 0.5), a)
    v = lerp(s.get("from", 0), s.get("to", 100), eio(seg(u, 0.3, land)))
    k = 1 + 0.16 * math.exp(-max(0, u - land) * 9) if u >= land else 1
    ctx.save(); ctx.translate(CX, 900); ctx.scale(k, k)
    if u < land:
        text(ctx, f"{s.get('pre', '')}{v:,.{s.get('dec', 0)}f}", BLACK, 300, 0, 0, "white", a * seg(u, 0.2, 0.4))
    else:
        text(ctx, s["big"], BLACK, 270, 0, 0, "green", a)
    ctx.restore()
    if u >= land:
        g = cairo.RadialGradient(CX, 900, 0, CX, 900, 700)
        g.add_color_stop_rgba(0, *COL["green"], 0.22 * math.exp(-(u - land) * 3)); g.add_color_stop_rgba(1, *COL["green"], 0)
        ctx.set_source(g); ctx.paint()
    pill(ctx, s["badge"], CX, 1120, "amber", 46, seg(u, land + 0.1, land + 0.45), a)
    rise(ctx, s["note"], MED, 40, CX, 1240, "dim", seg(u, land + 0.4, land + 0.8), a)

def sc_title(ctx, s, u, D):
    a = 1 - seg(u, D - 0.4, D)
    rise(ctx, s["kicker"], MED, 40, CX, 560, "green", seg(u, 0.0, 0.4), a)
    for i, ln in enumerate(s["lines"]):
        ctx.save(); ctx.rectangle(0, 680 + i * 150 - 80, W, 160); ctx.clip()
        text(ctx, ln, BLACK, 118 if i == 0 else 96, CX, 680 + i * 150 + 120 * (1 - eo(seg(u, 0.2 + 0.15 * i, 0.7 + 0.15 * i))),
             "white" if i == 0 else "green", a); ctx.restore()
    p = eo(seg(u, 0.7, 1.2)); ctx.set_source_rgba(*COL["amber"], a); rrect(ctx, CX - 110 * p, 990, 220 * p, 8, 4); ctx.fill()
    rise(ctx, s["sub"], SANS, 44, CX, 1100, "white", seg(u, 1.0, 1.4), a)
    rise(ctx, s["sub2"], MED, 34, CX, 1170, "dim", seg(u, 1.2, 1.6), a)
    tags = s.get("legend", [])
    for i, (t, col) in enumerate(tags):
        pill(ctx, t, CX + (i - (len(tags) - 1) / 2) * 290, 1330, col, 34, seg(u, 1.5 + 0.15 * i, 1.85 + 0.15 * i), a, outline=True)

def sc_kinetic(ctx, s, u, D):
    items = s["items"]; n = len(items); per = D / n
    i = min(n - 1, int(u / per)); lu = u - i * per; it = items[i]
    col = it.get("color", "green" if i % 2 == 0 else "amber"); a = 1 - seg(u, D - 0.3, D)
    wp = eo(clamp(lu / 0.25)); ctx.set_source_rgba(*c(col), 0.07)
    if i % 2 == 0: ctx.rectangle(0, 0, W * wp, H)
    else: ctx.rectangle(W * (1 - wp), 0, W * wp, H)
    ctx.fill()
    pill(ctx, s["label"], CX, 330, col, 36, 1.0, a)
    text(ctx, f"{i + 1} / {n}", MONO, 34, CX, 420, "dim", a)
    k = lerp(1.18, 1.0, eo(clamp(lu / 0.22)))
    ctx.save(); ctx.translate(CX, 860); ctx.scale(k, k)
    text(ctx, it["word"], BLACK, it.get("sz", 200), 0, 0, col, a * clamp(lu / 0.12), 980, tag=it["word"]); ctx.restore()
    for j, ln in enumerate(it["sub"]):
        rise(ctx, ln, SANS if j == 0 else MED, 52 if j == 0 else 40, CX, 1090 + j * 80, "white" if j == 0 else "dim",
             seg(lu, 0.25 + 0.15 * j, 0.6 + 0.15 * j), a, tag=ln)

def sc_outro(ctx, s, u, D):
    a = 1 - seg(u, D - 0.6, D) * 0.9
    rise(ctx, s["kicker"], MED, 40, CX, 520, "green", seg(u, 0.0, 0.4), a)
    for i, ln in enumerate(s["lines"]):
        rise(ctx, ln, BLACK, 92, CX, 650 + i * 125, "white" if i == 0 else "green", seg(u, 0.2 + 0.25 * i, 0.7 + 0.25 * i), a, tag=ln)
    p = eo(seg(u, 0.9, 1.4)); ctx.set_source_rgba(*COL["amber"], a); rrect(ctx, CX - 110 * p, 905, 220 * p, 8, 4); ctx.fill()
    for i, ln in enumerate(s["points"]):
        rise(ctx, ln, SANS, 44, CX, 1010 + i * 78, "white", seg(u, 1.2 + 0.25 * i, 1.6 + 0.25 * i), a, tag=ln)
    rise(ctx, s["foot1"], MED, 32, CX, 1400, "dim", seg(u, 2.2, 2.6), a)
    rise(ctx, s["foot2"], MED, 28, CX, 1455, "faint", seg(u, 2.4, 2.8), a)
    rise(ctx, s["foot3"], MED, 28, CX, 1505, "faint", seg(u, 2.5, 2.9), a)

def sc_brand(ctx, s, u, D):
    y0 = 860; R = 380; ap = eio(seg(u, 0.05, 0.9)); a = 1 - seg(u, D - 0.6, D) * 0.9
    ctx.set_line_width(5); ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source_rgba(*COL["cyan"], 0.85 * a); ctx.arc_negative(CX, y0, R, -math.pi / 2, -math.pi / 2 - math.pi * ap); ctx.stroke()
    ctx.set_source_rgba(*COL["amber"], 0.85 * a); ctx.arc(CX, y0, R, -math.pi / 2, -math.pi / 2 + math.pi * ap); ctx.stroke()
    hh = 170 * eo(seg(u, 0, 0.35)); ctx.set_source_rgba(*COL["white"], a); rrect(ctx, CX - 3, y0 - hh / 2, 6, max(hh, 0.1), 3); ctx.fill()
    p = eo(seg(u, 0.15, 0.6))
    for txt, fam, colr, side in ((META["brand_left"], BLACK, COL["cyan"], -1), (META["brand_right"], SERIF, COL["amber"], 1)):
        font(ctx, fam, 150); w1 = tw(ctx, txt)
        ctx.save()
        if side < 0: ctx.rectangle(0, 0, CX - 28, H)
        else: ctx.rectangle(CX + 28, 0, W, H)
        ctx.clip(); ctx.set_source_rgba(*colr, a)
        xc = lerp(CX - side * w1 / 2, CX + side * (40 + w1 / 2), p)
        ctx.move_to(xc - w1 / 2, y0 + 150 * 0.36); ctx.show_text(txt); ctx.restore()
    rise(ctx, s.get("tagline", META["tagline"]), MED, 44, CX, y0 + 180, "white", seg(u, 0.7, 1.1), a)
    rise(ctx, s.get("sub", ""), MED, 32, CX, 1380, "dim", seg(u, 1.0, 1.4), a)

FUN = {"hook": sc_hook, "title": sc_title, "chapter": sc_chapter, "kinetic": sc_kinetic, "outro": sc_outro, "brand": sc_brand}

# ---------------- timeline ----------------
t = 0.0
for s in SCENES:
    s["start"] = t; s["dur"] = s["beats"] * BEAT; t += s["dur"]
DUR = t

def background(ctx, t, col):
    g = cairo.LinearGradient(0, 0, 0, H); g.add_color_stop_rgb(0, *BG1); g.add_color_stop_rgb(1, *BG0)
    ctx.set_source(g); ctx.paint()
    gx = CX + 260 * math.sin(t * 0.21); gy = 820 + 220 * math.cos(t * 0.17)
    r = cairo.RadialGradient(gx, gy, 0, gx, gy, 900)
    r.add_color_stop_rgba(0, *c(col), 0.13); r.add_color_stop_rgba(1, *c(col), 0); ctx.set_source(r); ctx.paint()
    r = cairo.RadialGradient(W - gx * 0.6, H - 300, 0, W - gx * 0.6, H - 300, 700)
    r.add_color_stop_rgba(0, *COL["cyan"], 0.06); r.add_color_stop_rgba(1, *COL["cyan"], 0); ctx.set_source(r); ctx.paint()

CHAPTERS = [s for s in SCENES if s["type"] == "chapter" and s["badge"].startswith("重點")]

def hud(ctx, t, si):
    s = SCENES[si]
    font(ctx, SANS, 34); ctx.set_source_rgba(*COL["white"], 0.92)
    ctx.set_source_rgba(*COL["green"], 1); rrect(ctx, 60, 128, 10, 44, 5); ctx.fill()
    ctx.set_source_rgba(*COL["white"], 0.92); ctx.move_to(88, 163); ctx.show_text(META["series"])
    if s in CHAPTERS:
        k = CHAPTERS.index(s) + 1; lab = f"{k:02d} / {len(CHAPTERS):02d}"
        font(ctx, MONO, 32); ctx.set_source_rgba(*COL["dim"], 1); ctx.move_to(W - 60 - tw(ctx, lab), 162); ctx.show_text(lab)
    # progress
    x0, x1, y = 60, W - 60, 1730
    ctx.set_source_rgba(*COL["white"], 0.16); rrect(ctx, x0, y, x1 - x0, 6, 3); ctx.fill()
    col = c(s.get("color", "green"))
    ctx.set_source_rgba(*col, 1); rrect(ctx, x0, y, max(6, (x1 - x0) * t / DUR), 6, 3); ctx.fill()
    font(ctx, MED, 27); lab = META["disclaimer"]; ctx.set_source_rgba(*COL["dim"], 0.85)
    if s["type"] == "brand":
        ctx.move_to(CX - tw(ctx, lab) / 2, 1800); ctx.show_text(lab); return
    ctx.move_to(60, 1800); ctx.show_text(lab)
    brand_mark(ctx, W - 60, 1790, 30, 0.9)

def brand_mark(ctx, xr, yc, sz, a):
    """Small right-aligned 科技｜人文 mark; yc = visual centre."""
    L, R = META["brand_left"], META["brand_right"]
    font(ctx, SANS, sz); w1 = tw(ctx, L); font(ctx, SERIF, sz); w2 = tw(ctx, R); gap = sz * 0.55
    x = xr - (w1 + w2 + 2 * gap)
    font(ctx, SANS, sz); ctx.set_source_rgba(*COL["cyan"], a); ctx.move_to(x, yc + sz * 0.36); ctx.show_text(L)
    ctx.set_source_rgba(*COL["white"], 0.55 * a); ctx.rectangle(x + w1 + gap - 1.5, yc - sz * 0.5, 3, sz); ctx.fill()
    font(ctx, SERIF, sz); ctx.set_source_rgba(*COL["amber"], a); ctx.move_to(x + w1 + 2 * gap, yc + sz * 0.36); ctx.show_text(R)

def frame(t):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H); ctx = cairo.Context(surf)
    ctx.set_antialias(cairo.ANTIALIAS_BEST)
    fo = cairo.FontOptions(); fo.set_antialias(cairo.ANTIALIAS_GRAY); fo.set_hint_style(cairo.HINT_STYLE_NONE)
    fo.set_hint_metrics(cairo.HINT_METRICS_OFF); ctx.set_font_options(fo)
    si = max(i for i, s in enumerate(SCENES) if t >= s["start"] - 1e-9); s = SCENES[si]; u = t - s["start"]
    background(ctx, t, s.get("color", "green"))
    FUN[s["type"]](ctx, s, u, s["dur"])
    hud(ctx, t, si)
    if si >= 1 and u < 0.4:   # wipe accent at scene change
        x = lerp(-300, W + 300, eio(u / 0.4)); col = c(s.get("color", "green"))
        gb = cairo.LinearGradient(x - 260, 0, x + 260, 0)
        gb.add_color_stop_rgba(0, *col, 0); gb.add_color_stop_rgba(0.5, *col, 0.16); gb.add_color_stop_rgba(1, *col, 0)
        ctx.set_source(gb); ctx.paint()
    if t < 0.25: ctx.set_source_rgba(*BG0, 1 - t / 0.25); ctx.paint()
    return surf

# ---------------- output ----------------
ENC = ["-c:v", "libx264", "-preset", "slow", "-crf", "14", "-tune", "animation", "-profile:v", "high", "-level", "4.2",
       "-pix_fmt", "yuv420p", "-g", "60", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
VF = "scale=out_color_matrix=bt709:out_range=tv:flags=lanczos+accurate_rnd+full_chroma_int"

def render_chunk(args):
    k, a, b, out = args
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-vf", VF] + ENC + [out], stdin=subprocess.PIPE)
    for f in range(a, b):
        s = frame(f / FPS); s.flush(); ff.stdin.write(bytes(s.get_data()))
    ff.stdin.close(); ff.wait(); return out

def video(out):
    work = WORK; os.makedirs(work, exist_ok=True)
    for f in os.listdir(work):
        if f.startswith("seg"): os.remove(os.path.join(work, f))
    NF = int(round(DUR * FPS)); n = 8
    jobs = [(k, NF * k // n, NF * (k + 1) // n, os.path.join(work, f"seg{k:02d}.mp4")) for k in range(n)]
    with Pool(4) as p: segs = p.map(render_chunk, jobs)
    lst = os.path.join(work, "list.txt"); open(lst, "w").write("".join(f"file '{x}'\n" for x in segs))
    from music import synth
    wav = os.path.join(work, "music.wav")
    MAP = {"hook": "hook", "title": "story", "chapter": "story", "kinetic": "kinetic", "outro": "story", "brand": "logo"}
    synth([{"start": s["start"], "dur": s["dur"], "type": MAP[s["type"]]} for s in SCENES], BPM, wav)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-shortest", "-movflags", "+faststart", out], check=True)
    print("done", out, f"{DUR:.1f}s")

def stills(out):
    from PIL import Image
    ims = []
    for s in SCENES:
        if s["type"] == "kinetic":
            ts = [s["start"] + s["dur"] / len(s["items"]) * (j + 0.8) for j in range(len(s["items"]))]
        else: ts = [s["start"] + s["dur"] * 0.9]
        for t in ts:
            im = frame(t); p = os.path.join(WORK, "tmp.png"); os.makedirs(os.path.dirname(p), exist_ok=True)
            im.write_to_png(p); ims.append(Image.open(p).convert("RGB").resize((360, 640), Image.LANCZOS))
    cols = 6; rows = math.ceil(len(ims) / cols)
    sheet = Image.new("RGB", (360 * cols, 640 * rows), (0, 0, 0))
    for i, im in enumerate(ims): sheet.paste(im, ((i % cols) * 360, (i // cols) * 640))
    sheet.save(out)

def fonttest(out):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1000, 520); ctx = cairo.Context(surf)
    ctx.set_source_rgb(*BG0); ctx.paint()
    for i, (name, fam) in enumerate((("sans", SANS), ("black", BLACK), ("med", MED), ("mono", MONO), ("serif", SERIF))):
        font(ctx, fam, 64); ctx.set_source_rgb(1, 1, 1); ctx.move_to(30, 80 + i * 100)
        ctx.show_text(f"{name}：黃仁勳 10億倍 $40B 營收")
    surf.write_to_png(out); print("fonttest", out, _F)

if __name__ == "__main__":
    if len(sys.argv) < 3: print(__doc__); sys.exit(0)
    cmd = sys.argv[2]; sys.argv = [sys.argv[0]] + sys.argv[2:]
    if cmd == "stills": stills(sys.argv[2])
    elif cmd == "fonttest": fonttest(sys.argv[2])
    elif cmd == "frame": frame(float(sys.argv[2])).write_to_png(sys.argv[3])
    elif cmd == "video": video(sys.argv[2])
    elif cmd == "check":
        print(f"總長 {DUR:.1f}s")
        for s in SCENES:
            ys, tot = layout(s) if s["type"] == "chapter" else ([], 0)
            ts = times(s) if s["type"] == "chapter" else []
            flag = " ❌超出 %dpx" % (tot - (BOTTOM - TOP)) if tot > BOTTOM - TOP else ""
            late = f" ⚠最後區塊 {ts[-1]:.1f}s" if ts and ts[-1] > s["dur"] - 4 else ""
            print(f"{s['start']:6.1f}-{s['start'] + s['dur']:6.1f} {s['type']:8} {s.get('badge', '')} h={tot:.0f}{flag}{late}")
        for s in SCENES: frame(s["start"] + s["dur"] * 0.9)
        for w in sorted(set(WARN)): print(w)
