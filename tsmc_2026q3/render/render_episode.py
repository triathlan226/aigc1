#!/usr/bin/env python3
"""JSON-driven vertical (9:16) motion-graphics renderer for 每日X資料解讀.

Usage:
  python render_episode.py EP.json validate          # timeline + layout / reading-time checks
  python render_episode.py EP.json stills [OUT.png]  # contact sheet, one frame per scene
  python render_episode.py EP.json segment K N       # render segment K of N (0-based) to workdir
  python render_episode.py EP.json mux OUT.mp4       # synth audio + join segments -> MP4
  python render_episode.py EP.json all OUT.mp4       # everything in one call (may hit tool timeouts)

See references/schema.md for the episode JSON format.
"""
import cairo, json, math, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from synth_audio import synth  # noqa: E402

W, H = 1080, 1920
CX = W / 2
SANS, SERIF, MONO = "Noto Sans CJK TC", "Noto Serif CJK TC", "Noto Sans Mono CJK TC"
BG = (0.043, 0.059, 0.102)
COL = {"cyan": (0.24, 0.84, 0.96), "amber": (0.95, 0.65, 0.25), "red": (0.96, 0.38, 0.36),
       "white": (0.95, 0.96, 0.97), "dim": (0.78, 0.82, 0.88), "green": (0.35, 0.86, 0.55)}
TOP, BOTTOM = 580, 1540          # content zone for story blocks
SAFE_W = 940
WARN = []

# ---------------- math helpers ----------------
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def seg(t, a, b): return clamp((t - a) / (b - a)) if b > a else float(t >= a)
def eo(x): return 1 - (1 - x) ** 3
def eio(x): return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2
def eback(x, s=1.9): x -= 1; return x * x * ((s + 1) * x + s) + 1
def lerp(a, b, x): return a + (b - a) * x
def c(name): return COL.get(name, COL["white"]) if isinstance(name, str) else tuple(name)

# ---------------- text helpers ----------------
def setfont(ctx, fam, size, bold=True):
    ctx.select_font_face(fam, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)

def fit(ctx, fam, size, s, maxw, bold=True, tag=""):
    setfont(ctx, fam, size, bold)
    w = ctx.text_extents(s)[4]
    if w > maxw:
        ns = size * maxw / w
        if ns < size * 0.8 and tag: WARN.append(f"[文字過長] {tag}: 「{s}」縮到 {ns / size:.0%}，建議刪字")
        setfont(ctx, fam, ns, bold); return ns
    return size

def text_c(ctx, s, x, y, spacing=0.0):
    if spacing == 0:
        xb, yb, w, h, _, _ = ctx.text_extents(s)
        ctx.move_to(x - xb - w / 2, y - yb - h / 2); ctx.show_text(s); return
    ws = [ctx.text_extents(ch)[4] for ch in s]; tot = sum(ws) + spacing * (len(s) - 1)
    _, yb, _, h, _, _ = ctx.text_extents(s); cx = x - tot / 2
    for ch, wd in zip(s, ws):
        ctx.move_to(cx, y - yb - h / 2); ctx.show_text(ch); cx += wd + spacing

def draw_text(ctx, s, fam, size, x, y, col, a=1.0, bold=True, maxw=SAFE_W, tag=""):
    if a <= 0 or not s: return
    fit(ctx, fam, size, s, maxw, bold, tag); ctx.set_source_rgba(*col, a); text_c(ctx, s, x, y)

def rise(ctx, s, fam, size, x, y, col, p, a=1.0, bold=True, maxw=SAFE_W, tag=""):
    if p <= 0: return
    draw_text(ctx, s, fam, size, x, y + 30 * (1 - eo(p)), col, a * eo(p), bold, maxw, tag)

def rrect(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0); ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi); ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()

def pill(ctx, s, x, y, col, size=34, p=1.0, outline=False, tag=""):
    if p <= 0: return
    size = fit(ctx, SANS, size, s, SAFE_W - size * 1.2, True, tag)
    w = ctx.text_extents(s)[4] + size * 1.2; h = size * 1.7
    ctx.save(); ctx.translate(x, y); sc = eback(clamp(p)); ctx.scale(sc, sc)
    rrect(ctx, -w / 2, -h / 2, w, h, h / 2); ctx.set_source_rgba(*col, 1)
    if outline: ctx.set_line_width(3); ctx.stroke()
    else: ctx.fill()
    ctx.set_source_rgb(*(col if outline else BG)); text_c(ctx, s, 0, 0); ctx.restore()

def card(ctx, x, y, w, h, head, body, col, p, a=1.0, tag=""):
    if p <= 0 or a <= 0: return
    off = 60 * (1 - eo(p)); al = eo(p) * a
    ctx.save(); ctx.translate(off, 0)
    rrect(ctx, x, y, w, h, 18); ctx.set_source_rgba(*col, 0.10 * al); ctx.fill_preserve()
    ctx.set_source_rgba(*col, 0.8 * al); ctx.set_line_width(2); ctx.stroke()
    ctx.set_source_rgba(*col, al); ctx.rectangle(x, y + 18, 6, h - 36); ctx.fill()
    draw_text(ctx, head, SANS, 36, x + w / 2, y + h * 0.30, col, al, True, w - 40, tag)
    draw_text(ctx, body, SANS, 46, x + w / 2, y + h * 0.66, COL["white"], al, True, w - 40, tag)
    ctx.restore()

# ---------------- story blocks ----------------
# each: height(spec) and draw(ctx, spec, y_top, lt, a)  (lt = seconds since block appears)
def h_text(s): return {"L": 100, "M": 74, "S": 58}.get(s.get("size", "M"), 74)
def d_text(ctx, s, y, lt, a, tag):
    size = {"L": 64, "M": 48, "S": 38}.get(s.get("size", "M"), 48)
    rise(ctx, s["text"], SERIF if s.get("font") == "serif" else SANS, size, CX, y + h_text(s) / 2,
         c(s.get("color", "white")), seg(lt, 0, 0.4), a, True, tag=tag)

def h_pill(s): return 96
def d_pill(ctx, s, y, lt, a, tag):
    pill(ctx, s["text"], CX, y + 48, c(s.get("color", "amber")), 36, seg(lt, 0, 0.3) * (1 if a > 0.5 else a), s.get("outline", False), tag)

def h_cards(s): return 210
def d_cards(ctx, s, y, lt, a, tag):
    items = s["items"][:2]
    if len(items) == 1: xs, w = [CX - 300], 600
    else: xs, w = [90, 560], 430
    for i, it in enumerate(items):
        card(ctx, xs[i], y + 15, w, 180, it.get("head", ""), it.get("body", ""), c(it.get("color", "cyan")),
             seg(lt, 0.4 * i, 0.4 * i + 0.5), a, tag)

def h_gauge(s): return 260
def d_gauge(ctx, s, y, lt, a, tag):
    lo, hi, st = s["min"], s["max"], s.get("step", (s["max"] - s["min"]) / 5)
    dec, suf, pre = s.get("decimals", 2), s.get("suffix", ""), s.get("prefix", "")
    col = c(s.get("color", "cyan")); yb = y + 120; x0, x1 = 120, 960
    gp = eo(seg(lt, 0, 0.4)); vp = eio(seg(lt, 0.3, 1.9))
    ctx.set_source_rgba(*COL["white"], 0.25 * a * gp); ctx.rectangle(x0, yb - 6, (x1 - x0) * gp, 12); ctx.fill()
    setfont(ctx, MONO, 28, True); n = int(round((hi - lo) / st))
    for k in range(n + 1):
        vv = lo + k * st; xx = lerp(x0, x1, (vv - lo) / (hi - lo))
        ctx.set_source_rgba(*COL["dim"], 0.8 * a * gp); ctx.rectangle(xx - 1, yb + 14, 2, 14); ctx.fill()
        sd = 0 if float(st).is_integer() else len(str(st).split('.')[-1])
        text_c(ctx, f"{vv:.{sd}f}", xx, yb + 52)
    cur = lerp(lo, s["value"], vp); xc = lerp(x0, x1, (cur - lo) / (hi - lo))
    if vp > 0:
        g = cairo.LinearGradient(x0, 0, xc, 0); g.add_color_stop_rgba(0, *col, 0.3 * a); g.add_color_stop_rgba(1, *col, a)
        ctx.set_source(g); ctx.rectangle(x0, yb - 6, xc - x0, 12); ctx.fill()
        ctx.set_source_rgba(*COL["white"], a); ctx.arc(xc, yb, 13, 0, 2 * math.pi); ctx.fill()
        draw_text(ctx, f"{pre}{cur:.{dec}f}{suf}", SANS, 64, clamp(xc, 200, 880), yb - 75, col, a)
    rise(ctx, s.get("caption", ""), SANS, 36, CX, yb + 105, COL["dim"], seg(lt, 1.9, 2.3), a, True, tag=tag)

def h_bignum(s): return 250 + (130 if s.get("icon") else 0)
def d_bignum(ctx, s, y, lt, a, tag):
    col = c(s.get("color", "amber")); yy = y
    if s.get("icon") == "drop":
        dp = eback(seg(lt, 0, 0.4))
        if dp > 0:
            ctx.save(); ctx.translate(CX, y + 70); ctx.scale(dp * 0.9, dp * 0.9)
            ctx.move_to(0, -70); ctx.curve_to(40, -20, 55, 10, 55, 35); ctx.arc(0, 35, 55, 0, math.pi); ctx.curve_to(-55, 10, -40, -20, 0, -70)
            ctx.set_source_rgba(*col, a); ctx.fill(); ctx.restore()
        yy = y + 130
    dec, pre, suf = s.get("decimals", 2), s.get("prefix", ""), s.get("suffix", "")
    v = lerp(s.get("from", s["to"]), s["to"], eio(seg(lt, 0.2, 1.7)))
    done = lt >= 1.7
    draw_text(ctx, f"{pre}{v:.{dec}f}{suf}", SANS, 160, CX, yy + 95, col if done else COL["white"], a * seg(lt, 0.1, 0.4), tag=tag)
    rise(ctx, s.get("caption", ""), SANS, 38, CX, yy + 210, COL["dim"], seg(lt, 1.7, 2.1), a, True, tag=tag)

def h_chain(s): return 120
def d_chain(ctx, s, y, lt, a, tag):
    items = s["items"]; n = len(items); gap = min(290, 880 / max(1, n - 1)) if n > 1 else 0
    yc = y + 60
    for k, w in enumerate(items):
        x = CX + (k - (n - 1) / 2) * gap
        rise(ctx, w, SANS, 60 if n <= 3 else 48, x, yc, c("cyan") if k == n - 1 else COL["white"],
             seg(lt, k * 0.45, k * 0.45 + 0.4), a, maxw=gap * 0.62 if n > 1 else SAFE_W, tag=tag)
        if k < n - 1:
            ap = seg(lt, k * 0.45 + 0.2, k * 0.45 + 0.5)
            if ap > 0:
                xs, xe = x + gap * 0.33, x + gap * 0.67
                ctx.set_source_rgba(*COL["amber"], a); ctx.set_line_width(5)
                ctx.move_to(xs, yc); ctx.line_to(lerp(xs, xe, eo(ap)), yc); ctx.stroke()
                if ap >= 1:
                    ctx.move_to(xe, yc); ctx.line_to(xe - 18, yc - 12); ctx.line_to(xe - 18, yc + 12); ctx.close_path(); ctx.fill()

def h_panel(s): return 330
def d_panel(ctx, s, y, lt, a, tag):
    bx, bw, bh = 250, 580, 300; by = y + 10
    p = eback(seg(lt, 0, 0.5), 1.4)
    if p <= 0: return
    ctx.save(); ctx.translate(CX, by + bh / 2); ctx.scale(1, clamp(p, 0, 1.2)); ctx.translate(-CX, -(by + bh / 2))
    rrect(ctx, bx, by, bw, bh, 20); ctx.set_source_rgba(0.08, 0.11, 0.19, a); ctx.fill_preserve()
    ctx.set_source_rgba(*COL["cyan"], 0.7 * a); ctx.set_line_width(3); ctx.stroke()
    crack_t = 1.1 if s.get("crack") else 1e9
    for i in range(10):
        for j in range(3):
            on = (math.sin(lt * 6 + i * 1.7 + j * 2.3) > -0.2) if lt < crack_t + 0.4 else (math.sin(i * 3.1 + j) > 0.6)
            ctx.set_source_rgba(*(COL["cyan"] if on else COL["dim"]), (0.85 if on else 0.2) * a)
            ctx.rectangle(bx + 40 + i * 52, by + 40 + j * 34, 36, 18); ctx.fill()
    ctx.restore()
    draw_text(ctx, s.get("title", ""), SANS, 54, CX, by + 205, COL["white"], a * seg(lt, 0.3, 0.6), maxw=bw - 40, tag=tag)
    draw_text(ctx, s.get("caption", ""), SANS, 32, CX, by + 260, COL["dim"], a * seg(lt, 0.4, 0.7), True, bw - 40, tag)
    cp = eo(seg(lt, crack_t, crack_t + 0.5))
    if cp > 0:
        pts = [(bx + 330, by - 10), (bx + 290, by + 70), (bx + 350, by + 130), (bx + 300, by + 210), (bx + 345, by + bh + 10)]
        tot = len(pts) - 1; tgt = tot * cp
        ctx.set_source_rgba(*COL["red"], a); ctx.set_line_width(7); ctx.move_to(*pts[0])
        for k in range(tot):
            if tgt >= k + 1: ctx.line_to(*pts[k + 1])
            else:
                r = tgt - k; ctx.line_to(lerp(pts[k][0], pts[k + 1][0], r), lerp(pts[k][1], pts[k + 1][1], r)); break
        ctx.stroke()

def h_calendar(s): return 440
def d_calendar(ctx, s, y, lt, a, tag):
    fp = eo(seg(lt, 0, 0.4))
    if fp <= 0: return
    cx0, cy0, cw, ch = CX - 190, y + 20, 380, 400
    ctx.save(); ctx.translate(CX, cy0); ctx.scale(1, fp); ctx.translate(-CX, -cy0)
    rrect(ctx, cx0, cy0, cw, ch, 24); ctx.set_source_rgba(0.93, 0.95, 0.97, a); ctx.fill()
    ctx.save(); rrect(ctx, cx0, cy0, cw, ch, 24); ctx.clip()
    ctx.set_source_rgba(*c(s.get("color", "cyan")), a); ctx.rectangle(cx0, cy0, cw, 90); ctx.fill(); ctx.restore()
    draw_text(ctx, s.get("month", ""), SANS, 50, CX, cy0 + 47, BG, a, maxw=cw - 40)
    draw_text(ctx, str(s.get("day", "")), SANS, 210, CX, cy0 + 220, BG, a, maxw=cw - 40)
    draw_text(ctx, s.get("weekday", ""), SANS, 40, CX, cy0 + 345, (0.3, 0.33, 0.4), a, False, cw - 40, tag)
    ctx.restore()

def h_balance(s): return 480
def d_balance(ctx, s, y, lt, a, tag):
    px, py = CX, y + 40
    ang = 0.13 * math.sin(lt * 2.4) * math.exp(-lt * 0.25) * seg(lt, 0.4, 0.8)
    bp = eo(seg(lt, 0, 0.4)); L2 = 370 * bp
    ctx.set_source_rgba(*COL["white"], a); ctx.move_to(px, py); ctx.line_to(px - 50, py + 60); ctx.line_to(px + 50, py + 60); ctx.close_path(); ctx.fill()
    ctx.set_source_rgba(*COL["white"], 0.5 * a); ctx.rectangle(px - 3, py + 60, 6, 380); ctx.fill()
    ctx.save(); ctx.translate(px, py); ctx.rotate(ang)
    ctx.set_source_rgba(*COL["white"], a); ctx.rectangle(-L2, -4, 2 * L2, 8); ctx.fill(); ctx.restore()
    for ex, key, dc in ((-L2, "left", "cyan"), (L2, "right", "amber")):
        it = s.get(key, {});
        if bp <= 0 or not it: continue
        col = c(it.get("color", dc))
        wx = px + ex * math.cos(ang); wy = py + ex * math.sin(ang)
        ctx.set_source_rgba(*col, 0.7 * a); ctx.set_line_width(2); ctx.move_to(wx, wy); ctx.line_to(wx, wy + 110); ctx.stroke()
        cw = 300; cx0 = clamp(wx - cw / 2, 50, W - 50 - cw)
        card(ctx, cx0, wy + 110, cw, 170, it.get("head", ""), it.get("body", ""), col, seg(lt, 0.5, 0.9), a, tag)

BLOCKS = {"text": (h_text, d_text), "pill": (h_pill, d_pill), "cards": (h_cards, d_cards),
          "gauge": (h_gauge, d_gauge), "bignum": (h_bignum, d_bignum), "chain": (h_chain, d_chain),
          "panel": (h_panel, d_panel), "calendar": (h_calendar, d_calendar), "balance": (h_balance, d_balance)}

# ---------------- scenes ----------------
def sc_hook(ctx, s, u, D, ep):
    a = 1 - seg(u, D - 0.25, D); col = c(s.get("color", "cyan"))
    land = D * (1.6 / 2.4)
    rise(ctx, s.get("label", ""), SANS, 52, CX, 700, COL["dim"], seg(u, 0.0, 0.3), a, True, tag="hook")
    dec, pre, suf = s.get("decimals", 2), s.get("prefix", ""), s.get("suffix", "")
    v = lerp(s.get("from", s["to"]), s["to"], eio(seg(u, 0.2, land)))
    punch = 1 + 0.18 * math.exp(-max(0, u - land) * 10) if u >= land else 1
    ctx.save(); ctx.translate(CX, 900); ctx.scale(punch, punch)
    draw_text(ctx, f"{pre}{v:.{dec}f}{suf}", SANS, 250, 0, 0, col if u >= land else COL["white"], a, tag="hook")
    ctx.restore()
    if s.get("badge"): pill(ctx, s["badge"], CX, 1110, COL["amber"], 46, seg(u, land, land + 0.3) * a, tag="hook")
    rise(ctx, s.get("note", ""), SANS, 38, CX, 1210, COL["dim"], seg(u, land + 0.15, land + 0.4), a, True, tag="hook")

def block_times(s, D):
    blocks = s.get("blocks", []); n = len(blocks)
    step = min(1.6, max(0.5, (0.62 * D - 0.5) / max(1, n - 1))) if n > 1 else 0
    return [b.get("at", 0.5 + i * step) for i, b in enumerate(blocks)]

def layout(s):
    top = TOP + (50 if s.get("tag") else 0)
    hs = [BLOCKS[b["type"]][0](b) for b in s.get("blocks", [])]
    total = sum(hs) + 24 * max(0, len(hs) - 1)
    avail = BOTTOM - top
    y = top + max(0, (avail - total)) * 0.3
    ys = []
    for h in hs: ys.append(y); y += h + 24
    return ys, total, avail

def sc_story(ctx, s, u, D, ep):
    a = 1 - seg(u, D - 0.3, D); col = c(s.get("color", "cyan"))
    p = eo(seg(u, 0.05, 0.45)); tag = s.get("title", "")
    ctx.save(); ctx.rectangle(0, 330, W, 130); ctx.clip()
    draw_text(ctx, s.get("title", ""), SANS, 74, CX, 400 + 110 * (1 - p), COL["white"], a, tag=tag); ctx.restore()
    ctx.set_source_rgba(*col, a); ctx.rectangle(CX - 60 * p, 465, 120 * p, 5); ctx.fill()
    if s.get("tag"): pill(ctx, s["tag"], CX, 525, COL["amber"], 28, seg(u, 0.3, 0.6) * (1 if a > 0.5 else a), tag=tag)
    ys, _, _ = layout(s)
    for b, y, t0 in zip(s.get("blocks", []), ys, block_times(s, D)):
        if u >= t0: BLOCKS[b["type"]][1](ctx, b, y, u - t0, a, tag)

def sc_kinetic(ctx, s, u, D, ep):
    items = s["items"]; n = len(items); per = D / n
    i = min(n - 1, int(u / per)); lu = u - i * per; it = items[i]
    col = c(it.get("color", "cyan" if i % 2 == 0 else "amber"))
    fam = SERIF if it.get("font", "sans" if i % 2 == 0 else "serif") == "serif" else SANS
    wp = eo(clamp(lu / 0.2)); ctx.set_source_rgba(*col, 0.10)
    if i % 2 == 0: ctx.rectangle(0, 0, W * wp, H)
    else: ctx.rectangle(W * (1 - wp), 0, W * wp, H)
    ctx.fill()
    a = 1 - seg(u, D - 0.25, D)
    draw_text(ctx, s.get("label", "快訊"), SANS, 40, CX, 420, col, a)
    draw_text(ctx, f"{i + 1} / {n}", MONO, 30, CX, 480, COL["dim"], a, True)
    sc = lerp(1.25, 1.0, eo(clamp(lu / 0.16))); off = 12 * (1 - eo(clamp(lu / 0.2)))
    gh = 0.5 * (1 - eo(clamp(lu / 0.3)))
    for dx, cc, al in ((-off, COL["cyan"], gh), (off, COL["amber"], gh), (0, COL["white"], 1.0)):
        ctx.save(); ctx.translate(CX + dx, 900); ctx.scale(sc, sc)
        draw_text(ctx, it["word"], fam, 190, 0, 0, cc, al * a, maxw=760, tag="kinetic"); ctx.restore()
    rise(ctx, it.get("sub", ""), SANS, 46, CX, 1090, col, seg(lu, 0.2, 0.45), a, True, tag="kinetic")

def sc_logo(ctx, s, u, D, ep):
    cfg = ep["config"]; foot = ep.get("footer", {})
    y0 = 860; R = 400; ap = eio(seg(u, 0.05, 0.9)); a = 1 - seg(u, D - 0.4, D) * 0.85
    ctx.set_line_width(3)
    ctx.set_source_rgba(*COL["cyan"], 0.8 * a); ctx.arc_negative(CX, y0, R, -math.pi / 2, -math.pi / 2 - math.pi * ap); ctx.stroke()
    ctx.set_source_rgba(*COL["amber"], 0.8 * a); ctx.arc(CX, y0, R, -math.pi / 2, -math.pi / 2 + math.pi * ap); ctx.stroke()
    hh = 170 * eo(seg(u, 0, 0.3)); ctx.set_source_rgba(*COL["white"], a); ctx.rectangle(CX - 2, y0 - hh / 2, 4, hh); ctx.fill()
    p = eo(seg(u, 0.1, 0.5))
    for txt, fam, colr, side in ((cfg.get("brand_left", "科技"), SANS, COL["cyan"], -1), (cfg.get("brand_right", "人文"), SERIF, COL["amber"], 1)):
        setfont(ctx, fam, 150); w1 = ctx.text_extents(txt)[4]
        ctx.save()
        if side < 0: ctx.rectangle(0, 0, CX - 26, H)
        else: ctx.rectangle(CX + 26, 0, W, H)
        ctx.clip(); ctx.set_source_rgba(*colr, a)
        text_c(ctx, txt, lerp(CX - side * w1 / 2, CX + side * (36 + w1 / 2), p), y0); ctx.restore()
    rise(ctx, cfg.get("tagline", "事實 ｜ 推論 ｜ 觀點"), SANS, 46, CX, y0 + 170, COL["white"], seg(u, 0.6, 1.0), a, False)
    rise(ctx, foot.get("cutoff", ""), SANS, 36, CX, 1360, COL["dim"], seg(u, 0.9, 1.3), a, True)
    rise(ctx, foot.get("sources", ""), SANS, 28, CX, 1425, COL["dim"], seg(u, 1.1, 1.5), a, True, maxw=980)

SCENES = {"hook": sc_hook, "story": sc_story, "kinetic": sc_kinetic, "logo": sc_logo}
DEFAULT_BEATS = {"hook": 4, "story": 16, "logo": 6}

# ---------------- episode ----------------
def load(path):
    ep = json.load(open(path, encoding="utf-8"))
    cfg = ep.setdefault("config", {})
    cfg.setdefault("series", "每日X資料解讀"); cfg.setdefault("bpm", 100); cfg.setdefault("fps", 30)
    if not ep["scenes"] or ep["scenes"][-1]["type"] != "logo": ep["scenes"].append({"type": "logo"})
    beat = 60.0 / cfg["bpm"]; t = 0.0
    for s in ep["scenes"]:
        b = s.get("beats") or (math.ceil(len(s["items"]) * 2.5) if s["type"] == "kinetic" else DEFAULT_BEATS[s["type"]])
        s["beats"] = b; s["start"] = t; s["dur"] = b * beat; t += s["dur"]
        s.setdefault("color", "cyan")
    ep["duration"] = t
    ep["work"] = os.path.join("/home/claude/xreel_work", ep.get("slug", "episode") + "_v2")
    os.makedirs(ep["work"], exist_ok=True)
    return ep

def hud(ctx, ep, t, si):
    cfg = ep["config"]; D = ep["duration"]
    setfont(ctx, SANS, 30, True); ctx.set_source_rgba(*COL["white"], 0.75)
    ctx.move_to(60, 250); ctx.show_text(cfg["series"])
    setfont(ctx, MONO, 28, True); d = cfg.get("date", "")
    ctx.move_to(W - 60 - ctx.text_extents(d)[4], 250); ctx.show_text(d)
    x0, x1, y = 60, W - 60, 1600
    col = c(ep["scenes"][si]["color"])
    ctx.set_source_rgba(*COL["white"], 0.18); ctx.rectangle(x0, y, x1 - x0, 3); ctx.fill()
    ctx.set_source_rgba(*col, 0.9); ctx.rectangle(x0, y, (x1 - x0) * t / D, 3); ctx.fill()
    for s in ep["scenes"][1:]:
        xx = lerp(x0, x1, s["start"] / D)
        ctx.set_source_rgba(*COL["white"], 0.6 if t >= s["start"] else 0.25); ctx.arc(xx, y + 1.5, 5, 0, 2 * math.pi); ctx.fill()

GRID = [(x, y) for x in range(30, W, 120) for y in range(30, H, 60)]

def frame(ep, t):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf); ctx.set_antialias(cairo.ANTIALIAS_BEST)
    fo = cairo.FontOptions(); fo.set_antialias(cairo.ANTIALIAS_GRAY); fo.set_hint_style(cairo.HINT_STYLE_SLIGHT); ctx.set_font_options(fo)
    ctx.set_source_rgb(*BG); ctx.paint()
    sc = ep["scenes"]; si = max(i for i, s in enumerate(sc) if t >= s["start"] - 1e-9)
    s = sc[si]; u = t - s["start"]; col = c(s["color"])
    g = cairo.RadialGradient(CX, 900, 0, CX, 900, 900)
    g.add_color_stop_rgba(0, *col, 0.10); g.add_color_stop_rgba(1, *col, 0); ctx.set_source(g); ctx.paint()
    for (x, y) in GRID:
        ctx.set_source_rgba(*col, 0.12); ctx.arc(x, y, 2, 0, 2 * math.pi); ctx.fill()
    sh = 0
    for s2 in sc[1:]:
        if s2["start"] <= t < s2["start"] + 0.3: sh = 8 * math.exp(-(t - s2["start"]) * 14)
    if sc[0]["type"] == "hook":
        land = sc[0]["dur"] * (1.6 / 2.4)
        if land <= t < land + 0.3: sh = 12 * math.exp(-(t - land) * 14)
    ctx.save(); ctx.translate(sh * math.sin(t * 91), sh * math.cos(t * 77))
    SCENES[s["type"]](ctx, s, u, s["dur"], ep); ctx.restore()
    hud(ctx, ep, t, si)
    if si >= 1 and u < 0.35:
        x = lerp(-300, W + 300, eio(u / 0.35)); gb = cairo.LinearGradient(x - 250, 0, x + 250, 0)
        gb.add_color_stop_rgba(0, *col, 0); gb.add_color_stop_rgba(0.5, *col, 0.35); gb.add_color_stop_rgba(1, *col, 0)
        ctx.set_source(gb); ctx.paint()
    v = cairo.RadialGradient(W / 2, H / 2, H * 0.3, W / 2, H / 2, H * 0.75)
    v.add_color_stop_rgba(0, 0, 0, 0, 0); v.add_color_stop_rgba(1, 0, 0, 0, 0.3); ctx.set_source(v); ctx.paint()
    if t < 0.2: ctx.set_source_rgba(0, 0, 0, 1 - t / 0.2); ctx.paint()
    return surf

def scene_chars(s):
    out = []
    for k in ("title", "tag", "label", "badge", "note"):
        if s.get(k): out.append(s[k])
    for b in s.get("blocks", []):
        for k in ("text", "caption", "title"):
            if b.get(k): out.append(b[k])
        for it in b.get("items", []):
            out.append(it if isinstance(it, str) else it.get("head", "") + it.get("body", ""))
        for side in ("left", "right"):
            if b.get(side): out.append(b[side].get("head", "") + b[side].get("body", ""))
    for it in s.get("items", []):
        if isinstance(it, dict): out.append(it.get("word", "") + it.get("sub", ""))
    return sum(len(x.replace(" ", "")) for x in out)

def validate(ep):
    print(f"總長 {ep['duration']:.1f} 秒｜{ep['config']['bpm']} BPM｜{len(ep['scenes'])} 段")
    ok = True
    for i, s in enumerate(ep["scenes"]):
        line = f"  {s['start']:5.1f}–{s['start'] + s['dur']:5.1f}s  {s['type']:<8} {s.get('title', s.get('label', ''))}"
        if s["type"] == "story":
            _, tot, avail = layout(s)
            if tot > avail:
                ok = False; line += f"  ❌ 版面超出 {tot - avail:.0f}px（刪區塊或拆段）"
            ts = block_times(s, s["dur"])
            if ts and ts[-1] > s["dur"] - 2.0:
                line += f"  ⚠ 最後區塊太晚出現（{ts[-1]:.1f}s），建議加 beats"
        n = scene_chars(s)
        need = n / 9.0 + 1.0
        if s["type"] in ("story",) and need > s["dur"]:
            line += f"  ⚠ 字數 {n}，建議至少 {need:.1f}s"
        print(line)
    for t in [s["start"] + s["dur"] * 0.85 for s in ep["scenes"]]:
        frame(ep, t)
    for w in sorted(set(WARN)): print("  " + w)
    if ep["duration"] > 62: print("  ⚠ 超過 60 秒，超出內容移到補充版")
    print("VALID" if ok else "INVALID"); return ok

def stills(ep, out):
    from PIL import Image
    ims = []
    for s in ep["scenes"]:
        t = s["start"] + (s["dur"] * 0.85 if s["type"] != "kinetic" else s["dur"] / len(s["items"]) * 0.7)
        p = os.path.join(ep["work"], f"still_{t:06.2f}.png"); frame(ep, t).write_to_png(p)
        ims.append(Image.open(p).resize((270, 480)))
    cols = min(5, len(ims)); rows = math.ceil(len(ims) / cols)
    sheet = Image.new("RGB", (270 * cols, 480 * rows))
    for i, im in enumerate(ims): sheet.paste(im, ((i % cols) * 270, (i // cols) * 480))
    sheet.save(out); print("sheet", out)

def ffmpeg_writer(ep, out):
    fps = ep["config"]["fps"]
    return subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
                             "-r", str(fps), "-i", "-", "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
                             "-c:v", "libx264", "-preset", "slow", "-tune", "animation", "-crf", "14",
                             "-x264-params", "aq-mode=3:aq-strength=1.0:deblock=-1,-1",
                             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", out], stdin=subprocess.PIPE)

def segment(ep, k, n):
    fps = ep["config"]["fps"]; NF = int(round(ep["duration"] * fps))
    a = NF * k // n; b = NF * (k + 1) // n
    out = os.path.join(ep["work"], f"seg_{k:02d}_of_{n:02d}.mp4"); ff = ffmpeg_writer(ep, out)
    for f in range(a, b):
        s = frame(ep, f / fps); s.flush(); ff.stdin.write(bytes(s.get_data()))
    ff.stdin.close(); ff.wait(); print("segment", k, n, "frames", a, b, "rc", ff.returncode)

def mux(ep, out):
    segs = sorted(x for x in os.listdir(ep["work"]) if x.startswith("seg_") and x.endswith(".mp4"))
    ns = {x.split("_of_")[1] for x in segs}
    if len(ns) != 1: sys.exit(f"segment sets mixed: {ns}")
    n = int(list(ns)[0].split(".")[0])
    if len(segs) != n: sys.exit(f"missing segments: have {len(segs)} of {n}")
    wav = os.path.join(ep["work"], "music.wav")
    synth([{"start": s["start"], "dur": s["dur"], "type": s["type"]} for s in ep["scenes"]], ep["config"]["bpm"], wav)
    lst = os.path.join(ep["work"], "list.txt")
    open(lst, "w").write("".join(f"file '{os.path.join(ep['work'], x)}'\n" for x in segs))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True)
    print("done", out, f"{ep['duration']:.1f}s")

if __name__ == "__main__":
    ep = load(sys.argv[1]); cmd = sys.argv[2]
    if cmd == "validate": sys.exit(0 if validate(ep) else 1)
    elif cmd == "stills": stills(ep, sys.argv[3] if len(sys.argv) > 3 else os.path.join(ep["work"], "sheet.png"))
    elif cmd == "segment": segment(ep, int(sys.argv[3]), int(sys.argv[4]))
    elif cmd == "mux": mux(ep, sys.argv[3])
    elif cmd == "all":
        for f in os.listdir(ep["work"]):
            if f.startswith("seg_"): os.remove(os.path.join(ep["work"], f))
        n = max(1, math.ceil(ep["duration"] / 13))
        for k in range(n): segment(ep, k, n)
        mux(ep, sys.argv[3])
    else: print(__doc__)
