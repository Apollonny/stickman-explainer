#!/usr/bin/env python3
"""
stickman-explainer renderer
Storyboard JSON -> 9:16 hand-drawn stick-figure explainer video (mp4).

Usage:
  python render.py storyboard.json out.mp4              # full quality (1080x1920, 30 fps)
  python render.py storyboard.json out.mp4 --draft      # fast preview (no supersampling, 12 fps)
  python render.py storyboard.json --stills outdir      # only write one PNG per scene (final state)
  python render.py storyboard.json out.mp4 --audio vo.mp3

Needs: Python 3.9+, Pillow, numpy, ffmpeg on PATH. Fonts: Poppins + Lora (or any
fonts listed in meta.fonts / --font-dir). See SKILL.md for the storyboard schema.
"""
import argparse, json, math, os, random, shutil, subprocess, sys, zlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageOps

# ----------------------------------------------------------------- palette
PALETTE = {
    "paper": "#f3ebdd", "paper_edge": "#e3dccb", "ink": "#2b2723",
    "accent": "#b8372d", "sun": "#d89d48", "text": "#2e2821", "muted": "#6a645a",
}
W, H, SS = 1080, 1920, 2
POS_X = {"x", "x2"}
POS_Y = {"y", "y2", "ground"}


def hexrgb(h, a=255):
    h = str(h).strip().lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    if len(h) not in (6, 8) or any(c not in "0123456789abcdefABCDEF" for c in h):
        raise SystemExit(f"invalid colour '{h}': use #rgb or #rrggbb")
    al = int(h[6:8], 16) if len(h) == 8 else a
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), al)


# ----------------------------------------------------------------- fonts
FONT_DIRS = [
    "/usr/share/fonts/truetype/google-fonts", "/usr/share/fonts/truetype", "/usr/share/fonts/opentype",
    "/usr/local/share/fonts", os.path.expanduser("~/.fonts"), os.path.expanduser("~/.local/share/fonts"),
    "/Library/Fonts", "/System/Library/Fonts/Supplemental", os.path.expanduser("~/Library/Fonts"),
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"),
    os.path.expanduser("~/AppData/Local/Microsoft/Windows/Fonts"),
    "./fonts", "./assets/fonts",
]
FONT_CANDIDATES = {
    "sans": ["Poppins-Medium.ttf", "Poppins-Regular.ttf", "Montserrat-Medium.ttf", "segoeui.ttf", "Arial.ttf",
             "arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"],
    "sans_bold": ["Poppins-SemiBold.ttf", "Poppins-Bold.ttf", "Montserrat-SemiBold.ttf", "segoeuib.ttf",
                  "Arial Bold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"],
    "sans_light": ["Poppins-Regular.ttf", "Poppins-Medium.ttf", "segoeui.ttf", "Arial.ttf", "arial.ttf",
                   "DejaVuSans.ttf", "LiberationSans-Regular.ttf"],
    "serif": ["PlayfairDisplay-Regular.ttf", "PlayfairDisplay-Variable.ttf", "Lora-Variable.ttf", "georgia.ttf",
              "Georgia.ttf", "Times New Roman.ttf", "times.ttf", "DejaVuSerif.ttf", "LiberationSerif-Regular.ttf"],
}
_font_cache, _font_index, _font_warned = {}, {}, set()


def _index_fonts(extra_dirs):
    """Walk each font dir once; first directory (priority order) wins per file name."""
    for d in list(extra_dirs) + FONT_DIRS:
        if d in _font_index.get("__dirs__", set()) or not os.path.isdir(d):
            continue
        _font_index.setdefault("__dirs__", set()).add(d)
        for root, _, files in os.walk(d):
            for fn in files:
                _font_index.setdefault(fn, os.path.join(root, fn))


def find_font(kind, size, extra_dirs=()):
    key = (kind, size, tuple(extra_dirs))
    if key in _font_cache:
        return _font_cache[key]
    _index_fonts(extra_dirs)
    f = None
    for name in FONT_CANDIDATES[kind]:
        if name in _font_index:
            f = ImageFont.truetype(_font_index[name], size)
            break
    if f is None:
        if kind not in _font_warned:
            _font_warned.add(kind)
            print(f"WARNING: no TrueType font found for '{kind}' (looked for {FONT_CANDIDATES[kind][:3]}...). "
                  "Install Poppins/Playfair Display or pass --font-dir; Turkish characters may be missing.",
                  file=sys.stderr)
        try:
            f = ImageFont.load_default(size)
        except TypeError:
            f = ImageFont.load_default()
    _font_cache[key] = f
    return f


# ----------------------------------------------------------------- ink primitives
class Ink:
    """RGBA layer drawn at SS x supersampling, downsampled with LANCZOS."""

    def __init__(self):
        self.img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def line(self, pts, color, width, closed=False):
        p = [(x * SS, y * SS) for x, y in pts]
        if closed:
            p = p + [p[0]]
        w = max(1, int(round(width * SS)))
        self.d.line(p, fill=color, width=w, joint="curve")
        r = w / 2
        for q in (p[0], p[-1]):
            self.d.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=color)

    def fill(self, pts, color):
        self.d.polygon([(x * SS, y * SS) for x, y in pts], fill=color)

    def out(self):
        """Downsample SSx -> 1x with a premultiplied box filter (correct edge colours, much faster than LANCZOS)."""
        if SS == 1:
            return self.img
        return self.img.convert("RGBa").reduce(SS).convert("RGBA")


def pack(layer):
    """Crop a full-canvas RGBA layer to its visible bbox -> (rgb, alpha, x0, y0). Compositing only touches that box."""
    bb = layer.getbbox()
    if bb is None:
        bb = (0, 0, 1, 1)
    crop = layer.crop(bb)
    return crop.convert("RGB"), crop.getchannel("A"), bb[0], bb[1]


def wobble(pts, rng, amp=2.5, step=16, closed=False):
    """Resample a polyline and push each sample perpendicular by smooth noise (hand-drawn look)."""
    if closed:
        pts = list(pts) + [pts[0]]
    out, n_prev = [], 0.0
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        L = math.hypot(x1 - x0, y1 - y0) or 1e-6
        nx, ny = -(y1 - y0) / L, (x1 - x0) / L
        k = max(1, int(L / step))
        for i in range(k):
            t = i / k
            n_prev = 0.65 * n_prev + 0.35 * rng.uniform(-1, 1)
            out.append((x0 + (x1 - x0) * t + nx * n_prev * amp * 1.6,
                        y0 + (y1 - y0) * t + ny * n_prev * amp * 1.6))
    out.append(pts[-1] if not closed else out[0])
    return out


def stroke(ink, pts, rng, color, width, amp=2.5, closed=False, double=False):
    if double:  # "braided" ink look used on limbs
        for off in (-width * 0.22, width * 0.22):
            q = wobble([(x + off, y + off * 0.4) for x, y in pts], rng, amp, closed=closed)
            ink.line(q, color, width * 0.62, closed)
    else:
        ink.line(wobble(pts, rng, amp, closed=closed), color, width, closed)


def ellipse_pts(cx, cy, rx, ry, rng, jitter=0.03, a0=0, a1=360, n=None):
    n = n or max(24, int(abs(a1 - a0) / 6))
    pts, nz = [], 0.0
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        nz = 0.7 * nz + 0.3 * rng.uniform(-1, 1)
        k = 1 + nz * jitter
        pts.append((cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)))
    return pts


def chaikin(pts, closed=True, ratio=0.2):
    out = []
    n = len(pts)
    for i in range(n if closed else n - 1):
        p, q = pts[i], pts[(i + 1) % n]
        out += [(p[0] * (1 - ratio) + q[0] * ratio, p[1] * (1 - ratio) + q[1] * ratio),
                (p[0] * ratio + q[0] * (1 - ratio), p[1] * ratio + q[1] * (1 - ratio))]
    return out


# ----------------------------------------------------------------- text
def parse_marked(text):
    segs, bold, buf = [], False, ""
    i = 0
    while i < len(text):
        if text.startswith("**", i):
            if buf:
                segs.append((buf, bold))
            buf, bold = "", not bold
            i += 2
        else:
            buf += text[i]
            i += 1
    if buf:
        segs.append((buf, bold))
    return segs


def _wrap(text, caps, widthfn, max_w):
    """Greedy word wrap that keeps **accent** state per character. Returns list of [(char, bold)]."""
    lines = []
    for para in text.split("\n"):
        if caps:
            para = para.upper()
        chars = [(c, b) for seg, b in parse_marked(para) for c in seg]
        words, cur = [], []
        for ch in chars:
            if ch[0] == " ":
                if cur:
                    words.append(cur)
                cur = []
            else:
                cur.append(ch)
        if cur:
            words.append(cur)
        line, lw = [], 0.0
        for w in words:
            ww = sum(widthfn(c, b) for c, b in w)
            sp = widthfn(" ", False)
            if line and lw + sp + ww > max_w:
                lines.append(line)
                line, lw = list(w), ww
            else:
                line = line + [(" ", False)] + w if line else list(w)
                lw += (sp if lw else 0) + ww
        lines.append(line)
    return lines


def draw_text(ink, text, cx, cy, size, font_kind, color, accent, tracking=0, caps=False,
              fonts_dir=(), max_w=None, max_lines=3):
    """Centered text with **accent** markup, letter tracking and word wrap.
    Shrinks only when a word is wider than max_w or there are more than max_lines lines.
    Returns (max line width, number of lines, line height)."""
    limit = max_w or float("inf")
    sz = size
    while True:
        f_norm = find_font(font_kind, max(1, int(sz * SS)), fonts_dir)
        f_bold = find_font("sans_bold" if font_kind.startswith("sans") else font_kind, max(1, int(sz * SS)), fonts_dir)

        def wfn(c, b, fn=f_norm, fb=f_bold):
            return (fb if b else fn).getlength(c) / SS + tracking

        lines = _wrap(text, caps, wfn, limit)
        widths = [max(0.0, sum(wfn(c, b) for c, b in ln) - tracking) for ln in lines]
        if (len(lines) <= max_lines and max(widths) <= limit) or sz <= 22:
            break
        sz *= 0.94
    lh = sz * 1.3
    y0 = cy - lh * (len(lines) - 1) / 2
    for li, ln in enumerate(lines):
        x = cx - widths[li] / 2
        y = y0 + li * lh
        for c, b in ln:
            f = f_bold if b else f_norm
            ink.d.text((x * SS, y * SS), c, font=f, fill=(accent if b else color), anchor="lm")
            x += wfn(c, b)
    return max(widths), len(lines), lh


# ----------------------------------------------------------------- element renderers
class Ctx:
    def __init__(self, pal, fonts_dir, variant):
        self.pal, self.fonts_dir, self.variant = pal, fonts_dir, variant

    def rng(self, el, salt=0):
        return random.Random(el["_seed"] * 7919 + self.variant * 104729 + salt)

    def c(self, name_or_hex):
        v = self.pal.get(name_or_hex, name_or_hex)
        return hexrgb(v)


def r_ground(ink, el, cx, ox, oy):
    rng = cx.rng(el)
    x0 = (el["x"] if "x" in el else 0.02 * W) + ox
    x1 = (el["x2"] if "x2" in el else 0.98 * W) + ox
    y = el["y"] + oy
    stroke(ink, [(x0, y), (x1, y)], rng, cx.c(el.get("color", "ink")), el.get("width", 6), amp=3, double=True)


def r_sun(ink, el, cx, ox, oy):
    rng = cx.rng(el)
    x, y, r = el["x"] + ox, el["y"] + oy, el.get("r", 110)
    col = cx.c(el.get("color", "sun"))
    n = int(r * 3.4 * SS)
    yy, xx = np.mgrid[0:n, 0:n]
    dist = np.hypot(xx - n / 2, yy - n / 2) / (n / 2)
    alpha = (np.clip(1 - dist, 0, 1) ** 1.8 * 110).astype("uint8")
    glow = Image.new("RGBA", (n, n), col[:3] + (0,))
    glow.putalpha(Image.fromarray(alpha))
    ink.img.alpha_composite(glow, (int(x * SS - n / 2), int(y * SS - n / 2)))
    stroke(ink, ellipse_pts(x, y, r, r, rng, 0.035), rng, col, el.get("width", 6), amp=1.2, closed=True)
    rays = el.get("rays", 12)
    for i in range(rays):
        a = 2 * math.pi * i / rays + 0.15
        l0, l1 = r * (1.28 + rng.uniform(0, .06)), r * (1.52 + rng.uniform(-.08, .12))
        stroke(ink, [(x + l0 * math.cos(a), y + l0 * math.sin(a)), (x + l1 * math.cos(a), y + l1 * math.sin(a))],
               rng, col, el.get("width", 6) * 0.9, amp=1)


def r_text(ink, el, cx, ox, oy):
    x, y = el["x"] + ox, el["y"] + oy
    size = el.get("size", 54)
    wmax, nl, lh = draw_text(ink, el["text"], x, y, size, el.get("font", "sans"),
                             cx.c(el.get("color", "text")), cx.c(el.get("accent", "accent")),
                             tracking=el.get("tracking", 0), caps=el.get("caps", False), fonts_dir=cx.fonts_dir,
                             max_w=el.get("max_w", W * 0.86), max_lines=el.get("max_lines", 3))
    if el.get("rules"):  # double rule above/below the text block, sized from the text itself
        rng = cx.rng(el, 3)
        half = el.get("rules_w", wmax / 2 + size * 0.12)
        gap = el.get("rules_gap", size * 0.64)
        top, bot = y - lh * (nl - 1) / 2 - gap, y + lh * (nl - 1) / 2 + gap
        for yy in (top, bot):
            stroke(ink, [(x - half, yy), (x + half, yy)], rng, cx.c("ink"), 6.5, amp=2.5, double=True)


def r_lines(ink, el, cx, ox, oy):
    rng = cx.rng(el)
    for path in el["paths"]:
        pts = [(px + ox + el.get("x", 0), py + oy + el.get("y", 0)) for px, py in path]
        if el.get("smooth"):
            pts = chaikin(pts, closed=el.get("closed", False))
        stroke(ink, pts, rng, cx.c(el.get("color", "ink")), el.get("width", 6), amp=el.get("amp", 2),
               closed=el.get("closed", False))


# --- props (unit-box shapes)
PROPS = {
    "bowl": [(0, 0), (1, 0), (0.78, 1), (0.22, 1)],
    "bucket": [(0.14, 0), (0.86, 0), (1, 1), (0, 1)],
    "house": [(0, 0.42), (0.5, 0), (1, 0.42), (1, 1), (0, 1)],
    "book": [(0, 0.1), (0.48, 0.2), (0.5, 1), (0, 0.9)],
    "box": [(0, 0), (1, 0), (1, 1), (0, 1)],
    "triangle": [(0.5, 0), (1, 1), (0, 1)],
}


def r_prop(ink, el, cx, ox, oy):
    rng = cx.rng(el)
    kind, x, y = el["kind"], el["x"] + ox, el["y"] + oy  # x,y = top-left of bbox
    w, h = el.get("w", 140), el.get("h", 120)
    col = cx.c(el.get("color", "ink"))
    wd = el.get("width", 6)
    if kind == "barrel":  # drum lying on its side, opening on the left (flip=true -> right)
        fl = el.get("flip", False)
        def X(u): return x + (1 - u if fl else u) * w
        body = [(X(0.12), y), (X(1), y + 0.03 * h), (X(1), y + 0.97 * h), (X(0.12), y + h)]
        stroke(ink, body, rng, col, wd, amp=1.5, closed=True)
        for k in (0.34, 0.66):
            stroke(ink, [(X(0.12), y + k * h), (X(1), y + k * h)], rng, cx.c("muted"), wd * 0.55, amp=1)
        ell = ellipse_pts(X(0.12), y + h / 2, w * 0.1, h / 2, rng, 0.02)
        ink.fill(ell, cx.c("ink"))
    elif kind == "coins":
        for i in range(el.get("n", 3)):
            stroke(ink, ellipse_pts(x + w * (0.25 + 0.3 * i), y + h * (0.65 - 0.2 * (i % 2)), w * 0.2, w * 0.2, rng),
                   rng, col, wd, amp=1, closed=True)
    elif kind == "tree":
        stroke(ink, [(x + w / 2, y + h), (x + w / 2, y + h * 0.5)], rng, col, wd * 1.4, amp=1.5, double=True)
        stroke(ink, ellipse_pts(x + w / 2, y + h * 0.3, w * 0.45, h * 0.3, rng, 0.08), rng, col, wd, amp=1, closed=True)
    else:
        pts = [(x + u * w, y + v * h) for u, v in PROPS[kind]]
        stroke(ink, pts, rng, col, wd, amp=1.6, closed=True)
    if el.get("cross"):  # accent X = "none of this"
        m = 0.12
        for a, b in (((-m, -m), (1 + m, 1 + m)), ((1 + m, -m), (-m, 1 + m))):
            stroke(ink, [(x + a[0] * w, y + a[1] * h), (x + b[0] * w, y + b[1] * h)], rng, cx.c("accent"), wd * 1.15, amp=1.5)


def r_thought(ink, el, cx, ox, oy):
    rng = cx.rng(el)
    x, y, w, h = el["x"] + ox, el["y"] + oy, el["w"], el["h"]
    ctrl = [(0.02, 0.06), (0.76, 0.0), (1.0, 0.5), (0.78, 1.0), (0.04, 0.94)]
    pts = chaikin([(x + u * w, y + v * h) for u, v in ctrl], ratio=0.14)
    stroke(ink, pts, rng, cx.c("ink"), 6, amp=2, closed=True)
    tx, ty = el.get("tail_to", (x, y + h + 200))
    ax, ay = x + w * 0.3, y + h
    for t, r in ((0.2, 18), (0.4, 11)):
        px, py = ax + (tx - ax) * t, ay + (ty - ay) * t + 40
        stroke(ink, ellipse_pts(px, py, r, r, rng, 0.04), rng, cx.c("ink"), 5, amp=0.8, closed=True)
    for sub in el.get("inner", []):  # sub-elements in bubble-local px
        sub = dict(sub)
        sub["_seed"] = zlib.crc32((str(el["_seed"]) + sub.get("type", "")).encode()) & 0xffff
        RENDER[sub["type"]](ink, sub, cx, x, y)


def r_figure(ink, el, cx, ox, oy):
    rng = cx.rng(el)
    x, g, h = el["x"] + ox, el["ground"] + oy, el["h"]
    d = el.get("dir", 1)
    r = el.get("head_r", 0.11 * h)
    ink_c, acc = cx.c("ink"), cx.c(el.get("accent", "accent"))
    pose = el.get("pose", "stand")
    lw = el.get("width", 12)
    head = (x, g - h + r)
    neck = (x, g - h + 2 * r)
    sh = (x, neck[1] + 0.05 * h)
    if pose == "sit":
        hip = (x, g - 0.05 * h)
        legs = [[hip, (x + d * 0.22 * h, g - 0.17 * h), (x + d * 0.4 * h, g)],
                [hip, (x + d * 0.12 * h, g - 0.02 * h), (x + d * 0.3 * h, g)]]
    else:
        hip = (x, g - 0.37 * h)
        sp = el.get("stance", 0.06)
        legs = [[hip, (x - sp * h, g)], [hip, (x + sp * h, g)]]
    hands = {"stand": [(-0.125, 0.36), (0.105, 0.36)],
             "arms_open": [(-0.30, 0.15), (0.30, 0.15)],
             "sit": [(-0.30, 0.10), (0.30, 0.10)],
             "point": [(-0.125, 0.36), (0.32, -0.10)],
             "wave": [(-0.125, 0.36), (0.22, -0.28)],
             "think": [(-0.125, 0.36), (0.07, 0.04)],
             "shrug": [(-0.22, 0.20), (0.22, 0.20)]}[pose]
    arms = []
    for hx, hy in hands:
        hx = hx * (d if pose in ("point", "wave") and hx > 0 else 1)
        arms.append([sh, (x + hx * h, sh[1] + hy * h)])
    for lg in legs:
        stroke(ink, lg, rng, ink_c, lw, amp=2, double=True)
    stroke(ink, [neck, hip], rng, ink_c, lw, amp=2, double=True)
    for a in arms:
        stroke(ink, a, rng, ink_c, lw, amp=2, double=True)
    if el.get("cape"):
        cd = el.get("cape_dir", 1)
        stroke(ink, [neck, (x + cd * 0.025 * h, sh[1] + 0.18 * h), (x + cd * 0.04 * h, hip[1] + 0.02 * h)],
               rng, acc, 6, amp=1.5)
    # head
    hp = ellipse_pts(head[0], head[1], r, r * 1.02, rng, 0.035)
    ink.fill(hp, ink_c)
    ink.line(hp, ink_c, 6, True)
    face = cx.c("paper")
    look = el.get("look", 0) * r * 0.18
    fk = el.get("face", "neutral")
    ex, ey, er = r * 0.34, head[1] - r * 0.05, max(3, r * 0.075)
    if fk in ("neutral", "sad", "angry", "surprised"):
        for sx in (-1, 1):
            c = (head[0] + sx * ex + look, ey)
            ink.d.ellipse([(c[0] - er) * SS, (c[1] - er) * SS, (c[0] + er) * SS, (c[1] + er) * SS], fill=face)
    if fk in ("smile", "happy"):
        for sx in (-1, 1):
            c = (head[0] + sx * ex + look, ey)
            ink.line(ellipse_pts(c[0], c[1], r * 0.16, r * 0.1, rng, 0, 20, 160, 8), face, 3.5)
    my = head[1] + r * 0.42
    if fk in ("smile", "happy"):
        ink.line(ellipse_pts(head[0] + look, my - r * 0.16, r * 0.3, r * 0.2, rng, 0, 15, 165, 12), face, 3.5)
    elif fk == "sad":
        ink.line(ellipse_pts(head[0] + look, my + r * 0.12, r * 0.25, r * 0.15, rng, 0, 195, 345, 12), face, 3.5)
    elif fk == "surprised":
        ink.line(ellipse_pts(head[0] + look, my, r * 0.1, r * 0.13, rng, 0), face, 3.5, True)
    elif fk == "angry":
        for sx in (-1, 1):
            ink.line([(head[0] + sx * ex * 1.5, ey - er * 3 - sx * 4), (head[0] + sx * ex * 0.5, ey - er * 2 + sx * 4)], face, 3.5)
        ink.line([(head[0] - r * 0.22 + look, my), (head[0] + r * 0.22 + look, my)], face, 3.5)
    else:
        ink.line([(head[0] - r * 0.16 + look, my), (head[0] + r * 0.16 + look, my)], face, 3.5)
    acc_k = el.get("accessory")
    if acc_k == "helmet":
        stroke(ink, ellipse_pts(head[0], head[1] - r * 0.12, r * 1.3, r * 1.2, rng, 0.02, 188, 352, 22), rng, acc, 8, amp=1)
        stroke(ink, [(head[0] + r * 0.2, head[1] - r * 1.32), (head[0] + r * 0.62, head[1] - r * 1.5),
                     (head[0] + r * 0.5, head[1] - r * 1.2)], rng, acc, 6, amp=1)
    elif acc_k == "crown":
        top = head[1] - r * 0.95
        zz = [(head[0] - r * .8, top), (head[0] - r * .8, top - r * .6), (head[0] - r * .4, top - r * .25),
              (head[0], top - r * .75), (head[0] + r * .4, top - r * .25), (head[0] + r * .8, top - r * .6), (head[0] + r * .8, top)]
        stroke(ink, zz, rng, acc, 7, amp=1)
    elif acc_k == "hat":
        stroke(ink, [(head[0] - r * 1.4, head[1] - r * .75), (head[0] + r * 1.4, head[1] - r * .75)], rng, acc, 8, amp=1)
        stroke(ink, [(head[0] - r * .8, head[1] - r * .75), (head[0] - r * .7, head[1] - r * 1.8),
                     (head[0] + r * .7, head[1] - r * 1.8), (head[0] + r * .8, head[1] - r * .75)], rng, acc, 8, amp=1, closed=False)
    elif acc_k == "glasses":
        for sx in (-1, 1):
            stroke(ink, ellipse_pts(head[0] + sx * ex, ey, r * .26, r * .26, rng, 0.02), rng, face, 3.5, amp=.5, closed=True)


RENDER = {"ground": r_ground, "sun": r_sun, "text": r_text, "lines": r_lines, "prop": r_prop,
          "thought": r_thought, "figure": r_figure}


# ----------------------------------------------------------------- scene prep & compositing
def make_bg(pal):
    xx, yy = np.meshgrid(np.linspace(-1, 1, W), np.linspace(-1, 1, H))
    d = np.sqrt((xx * 0.9) ** 2 + (yy * 0.55) ** 2)
    m = np.clip((d - 0.45) / 0.9, 0, 1) ** 1.6
    a, b = np.array(hexrgb(pal["paper"])[:3], float), np.array(hexrgb(pal["paper_edge"])[:3], float)
    img = a[None, None, :] * (1 - m[..., None]) + b[None, None, :] * m[..., None]
    nz = np.random.RandomState(7).normal(0, 1.6, (H, W, 1))
    return Image.fromarray(np.clip(img + nz, 0, 255).astype("uint8")).convert("RGBA")


def norm_el(el):
    el = dict(el)
    for k in list(el):
        if k in POS_X and isinstance(el[k], (int, float)) and abs(el[k]) <= 2:
            el[k] = el[k] * W
        if k in POS_Y and isinstance(el[k], (int, float)) and abs(el[k]) <= 2:
            el[k] = el[k] * H
    return el


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


TIMING_KEYS = {"at", "dur", "anim", "until", "out_dur", "_tween", "_seed", "_caption", "_karaoke"}


def resolve_carry(scene, si, prev, duration):
    """Elements carried over from the previous scene (same look, same line-wobble seed)."""
    spec = scene.get("carry")
    if not spec:
        return []
    if spec == "all":
        skip = set(scene.get("carry_except", []))
        entries = [{"id": k} for k in prev if k not in skip]
    else:
        entries = [{"id": e} if isinstance(e, str) else dict(e) for e in spec]
    out = []
    for ent in entries:
        i = ent["id"]
        if i not in prev:
            raise SystemExit(f"scene {si + 1}: carry id '{i}' not found in previous scene. "
                             f"Available: {list(prev) or 'none (give elements an \"id\")'}")
        old = prev[i]
        el = dict(old)
        el.update(norm_el(ent.get("set", {})))
        for k in ("until", "out_dur", "_tween"):
            el.pop(k, None)
        el.update(at=ent.get("at", 0.0), dur=ent.get("dur", 0.0), anim=ent.get("anim", "fade"))
        for k in ("until", "out_dur"):
            if k in ent:
                el[k] = ent[k]
        tw = ent.get("tween")
        if tw is not None:
            ky = "y" if "y" in el else "ground"
            el["_tween"] = {"dx": old.get("x", 0) - el.get("x", 0), "dy": old.get(ky, 0) - el.get(ky, 0),
                            "at": tw.get("at", 0.0), "dur": tw.get("dur", 0.8)}
        out.append(el)
    return out


def build_scene(scene, idx, pal, fonts_dir, variants, prev, cache):
    carried = resolve_carry(scene, idx, prev, scene.get("duration", 3.0))
    els = carried + [norm_el(e) for e in scene.get("elements", [])]
    cap = scene.get("caption")
    if cap:
        karaoke = scene.get("karaoke")
        c = norm_el({"type": "text", "text": cap, "x": 0.5, "y": scene.get("caption_y") or 0.775,
                     "size": scene.get("caption_size", 54), "font": "sans", "at": scene.get("caption_at", 0.5),
                     "dur": 0.12 if karaoke else 0.45, "anim": "rise", "color": "text"})
        c["_caption"] = True
        if karaoke:
            c["_karaoke"] = karaoke
        els.append(c)
    built, used = [], set()
    for i, el in enumerate(els):
        if "_seed" not in el:  # carried elements keep their seed -> identical linework across scenes
            key = f"id:{el['id']}" if el.get("id") else f"{idx}:{i}:{el['type']}"
            el["_seed"] = zlib.crc32(key.encode()) & 0xffff
        ck = json.dumps({k: v for k, v in el.items() if k not in TIMING_KEYS}, sort_keys=True, default=str)
        used.add(ck)
        if ck not in cache:
            if el.get("_karaoke") and el["type"] == "text":
                words = el["text"].split()
                states = [el["text"]]
                for wi in range(len(words)):
                    marked = list(words)
                    marked[wi] = f"**{marked[wi]}**"
                    states.append(" ".join(marked))
                state_layers = []
                render_el = dict(el)
                render_el.pop("_karaoke", None)
                for text_state in states:
                    render_el["text"] = text_state
                    layers = []
                    for v in range(variants):
                        ink = Ink()
                        RENDER[el["type"]](ink, render_el, Ctx(pal, fonts_dir, v), 0, 0)
                        layers.append(pack(ink.out()))
                    state_layers.append(layers)
                cache[ck] = state_layers
            else:
                layers = []
                for v in range(variants):
                    ink = Ink()
                    RENDER[el["type"]](ink, el, Ctx(pal, fonts_dir, v), 0, 0)
                    layers.append(pack(ink.out()))
                cache[ck] = layers
        built.append((el, cache[ck]))
    for k in list(cache):  # keep memory bounded: only this scene's layers survive
        if k not in used:
            del cache[k]
    return built


def frame_ops(built, t, boil_fps):
    """Everything needed to draw time t: list of (layer, alpha, wipe_p or None, sx, sy). Cheap to compute."""
    ops = []
    for el, layers in built:
        at, dur = el.get("at", 0.0), el.get("dur", 0.5)
        p = ease((t - at) / dur) if dur > 0 else float(t >= at)
        if p <= 0:
            continue
        fo = 1.0
        if el.get("until") is not None:
            q = (t - el["until"]) / el.get("out_dur", 0.4)
            if q >= 1:
                continue
            fo = 1 - ease(q)
        if el.get("_karaoke") and layers and isinstance(layers[0], list):
            state = 0
            for wi, interval in enumerate(el["_karaoke"]):
                if interval["start"] <= t < interval["end"]:
                    state = wi + 1
                    break
            state_layers = layers[state]
            lay = state_layers[int(t * boil_fps) % len(state_layers)]
        else:
            lay = layers[int(t * boil_fps) % len(layers)]
        anim = el.get("anim", "fade")
        sx = sy = 0
        tw = el.get("_tween")
        if tw:
            r = 1 - ease((t - tw["at"]) / tw["dur"]) if tw["dur"] > 0 else 0.0
            sx, sy = int(tw["dx"] * r), int(tw["dy"] * r)
        if anim in ("rise", "pop"):
            sy += int((1 - p) * (24 if anim == "rise" else 40))
        if anim == "wipe":
            ops.append((lay, fo, p, sx, sy))
        else:
            ops.append((lay, p * fo, None, sx, sy))
    return ops


def ops_key(ops):
    return tuple((id(l), round(a, 3), None if w is None else round(w, 3), sx, sy) for l, a, w, sx, sy in ops)


def render_ops(bg, ops):
    f = bg.copy()  # RGB, opaque
    for (rgb, a, x0, y0), alpha, wipe, sx, sy in ops:
        if wipe is not None:
            mask = Image.new("L", a.size, 0)
            wpx = int(W * wipe) - x0
            if wpx > 0:
                ImageDraw.Draw(mask).rectangle([0, 0, wpx, a.height], fill=255)
            a = ImageChops.multiply(a, mask)
        if alpha < 1:
            a = a.point(lambda v, k=alpha: int(v * k))
        f.paste(rgb, (x0 + sx, y0 + sy), a)
    return f


def frame_at(bg, built, t, boil_fps):
    return render_ops(bg, frame_ops(built, t, boil_fps))


# ----------------------------------------------------------------- validation
ENUMS = {
    "pose": ["stand", "arms_open", "point", "wave", "think", "shrug", "sit"],
    "face": ["neutral", "smile", "happy", "sad", "surprised", "angry"],
    "accessory": ["helmet", "crown", "hat", "glasses"],
    "kind": sorted(set(PROPS) | {"barrel", "coins", "tree"}),
    "font": list(FONT_CANDIDATES),
    "anim": ["fade", "wipe", "rise", "pop"],
}
REQUIRED = {"ground": ["y"], "sun": ["x", "y"], "text": ["text", "x", "y"], "figure": ["x", "ground", "h"],
            "prop": ["kind", "x", "y"], "thought": ["x", "y", "w", "h"], "lines": ["paths"]}
NUMERIC = ["x", "x2", "y", "ground", "h", "w", "r", "size", "head_r", "width", "at", "dur", "until", "out_dur",
           "tracking", "rays", "n", "caption_at", "caption_y", "caption_size"]


def check_el(el, where, errs, inner=False):
    if not isinstance(el, dict):
        errs.append(f"{where}: element must be an object")
        return
    t = el.get("type")
    if t not in RENDER:
        errs.append(f"{where}: unknown or missing 'type' {t!r}. Allowed: {sorted(RENDER)}")
        return
    where = f"{where} ({t})"
    for k in REQUIRED[t]:
        if k not in el:
            errs.append(f"{where}: missing required field '{k}'")
    for k in NUMERIC:
        if k in el and not (el[k] is None and k in ("until", "caption_y")) \
                and (isinstance(el[k], bool) or not isinstance(el[k], (int, float))):
            errs.append(f"{where}: '{k}' must be a number, got {el[k]!r}")
    for k, allowed in ENUMS.items():
        if k in el and el[k] is not None and el[k] not in allowed:
            errs.append(f"{where}: {k}={el[k]!r} is not valid. Allowed: {allowed}")
    if t == "lines":
        for i, path in enumerate(el.get("paths", [])):
            if not isinstance(path, list) or len(path) < 2:
                errs.append(f"{where}: paths[{i}] needs at least 2 points")
    if t == "thought":
        for i, sub in enumerate(el.get("inner", [])):
            check_el(sub, f"{where} inner[{i}]", errs, inner=True)
            if isinstance(sub, dict) and sub.get("type") == "thought":
                errs.append(f"{where} inner[{i}]: thought bubbles cannot be nested")


def validate(sb):
    errs, warns = [], []
    meta = sb.get("meta", {})
    w, h = meta.get("width", 1080), meta.get("height", 1920)
    if not (isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0) or w % 2 or h % 2:
        errs.append(f"meta: width/height must be positive even integers (got {w}x{h}); libx264 needs even sizes")
    scenes = sb.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        errs.append("storyboard needs a non-empty 'scenes' list")
        return errs, warns
    for si, sc in enumerate(scenes):
        wh = f"scene {si + 1}"
        dur = sc.get("duration", 3.0)
        if isinstance(dur, bool) or not isinstance(dur, (int, float)) or dur <= 0:
            errs.append(f"{wh}: 'duration' must be a number > 0 (got {dur!r})")
            dur = 3.0
        ids = set()
        for ei, el in enumerate(sc.get("elements", [])):
            check_el(el, f"{wh}, element {ei + 1}", errs)
            if isinstance(el, dict):
                i = el.get("id")
                if i is not None:
                    if i in ids:
                        errs.append(f"{wh}, element {ei + 1}: duplicate id '{i}' (ids must be unique within a scene)")
                    ids.add(i)
                if isinstance(el.get("at"), (int, float)) and el["at"] >= dur:
                    warns.append(f"{wh}, element {ei + 1}: 'at'={el['at']} is not before the scene ends ({dur}s); it will never appear")
        cap_at = sc.get("caption_at", 0.5)
        if sc.get("caption") and isinstance(cap_at, (int, float)) and cap_at >= dur:
            warns.append(f"{wh}: caption_at={cap_at} is not before the scene ends ({dur}s); the caption will never appear")
        karaoke = sc.get("karaoke")
        if karaoke is not None:
            caption = sc.get("caption")
            if not isinstance(caption, str) or not caption.strip():
                errs.append(f"{wh}: 'karaoke' requires a non-empty caption")
            else:
                word_count = len(caption.split())
                if not isinstance(karaoke, list):
                    errs.append(f"{wh}: 'karaoke' must be a list of {{'start','end'}} objects")
                else:
                    if len(karaoke) != word_count:
                        errs.append(f"{wh}: 'karaoke' needs one interval per caption word ({word_count} expected, got {len(karaoke)})")
                    previous_end = -1.0
                    for ki, interval in enumerate(karaoke):
                        if not isinstance(interval, dict) or "start" not in interval or "end" not in interval:
                            errs.append(f"{wh}: karaoke[{ki}] must contain numeric 'start' and 'end'")
                            continue
                        start, end = interval["start"], interval["end"]
                        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (start, end)):
                            errs.append(f"{wh}: karaoke[{ki}] 'start' and 'end' must be numbers")
                            continue
                        if start < 0 or end <= start or end > dur:
                            errs.append(f"{wh}: karaoke[{ki}] must satisfy 0 <= start < end <= scene duration ({dur}s)")
                        if start < previous_end:
                            errs.append(f"{wh}: karaoke intervals must be in caption order and must not overlap")
                        previous_end = end
            if isinstance(caption, str) and "**" in caption:
                errs.append(f"{wh}: remove static **word** markup when using 'karaoke'; the active word is highlighted automatically")
        for ent in ([] if sc.get("carry") in (None, "all") else sc.get("carry", [])):
            if not (isinstance(ent, str) or (isinstance(ent, dict) and "id" in ent)):
                errs.append(f"{wh}: each carry entry must be an id string or an object with 'id'")
            elif isinstance(ent, dict):
                for k, v in ent.get("set", {}).items():
                    if k in ("type", "id"):
                        errs.append(f"{wh}: carry 'set' cannot change '{k}'")
                    if k in ENUMS and v is not None and v not in ENUMS[k]:
                        errs.append(f"{wh}: carry set {k}={v!r} is not valid. Allowed: {ENUMS[k]}")
    return errs, warns


def probe_duration(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True).stdout.strip()
        return float(out)
    except Exception:
        return None


def main():
    global W, H, SS
    ap = argparse.ArgumentParser(description="Render a stick-figure explainer storyboard to mp4 / stills.")
    ap.add_argument("storyboard")
    ap.add_argument("out", nargs="?", help="output .mp4 (omit when using --stills)")
    ap.add_argument("--draft", action="store_true", help="fast preview: no supersampling, 12 fps")
    ap.add_argument("--stills", metavar="DIR", help="write one PNG per scene (final state) instead of a video")
    ap.add_argument("--audio", help="voice-over / music file to mux")
    ap.add_argument("--font-dir", action="append", default=[])
    a = ap.parse_args()
    if not a.out and not a.stills:
        ap.error("give an output file (out.mp4) or --stills DIR")

    try:
        sb = json.load(open(a.storyboard, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"cannot read storyboard '{a.storyboard}': {e}")
    errs, warns = validate(sb)
    for w_ in warns:
        print("WARNING:", w_, file=sys.stderr)
    if errs:
        raise SystemExit("storyboard errors:\n  - " + "\n  - ".join(errs))

    meta = sb.get("meta", {})
    W, H = meta.get("width", 1080), meta.get("height", 1920)
    fps = meta.get("fps", 30)
    boil = meta.get("boil_fps", 8)
    variants = 3
    pal = {**PALETTE, **meta.get("palette", {})}
    for k, v in pal.items():
        hexrgb(v)  # fail early on bad colours
    if a.draft:
        SS, fps = 1, 12
    bg = make_bg(pal).convert("RGB")
    tf = meta.get("transition", 0.18)
    fonts_dir = a.font_dir + meta.get("font_dirs", [])
    audio = a.audio or meta.get("audio")
    total = sum(sc.get("duration", 3.0) for sc in sb["scenes"])

    proc = None
    if a.out and not a.stills:
        if shutil.which("ffmpeg") is None:
            raise SystemExit("ffmpeg not found on PATH. Install it (e.g. apt install ffmpeg / brew install ffmpeg / winget install ffmpeg), "
                             "or use --stills to preview without it.")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(fps), "-i", "-"]
        if audio:
            if not os.path.isfile(audio):
                raise SystemExit(f"audio file not found: {audio}")
            ad = probe_duration(audio)
            if ad is not None and abs(ad - total) > 0.3:
                print(f"NOTE: audio is {ad:.1f}s but the storyboard is {total:.1f}s; "
                      f"{'audio will be cut' if ad > total else 'silence will be added'} (video length is never changed).",
                      file=sys.stderr)
            cmd += ["-i", audio, "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-af", "apad", "-t", f"{total:.3f}"]
        cmd += ["-c:v", "libx264", "-preset", "ultrafast" if a.draft else "fast", "-pix_fmt", "yuv420p",
                "-crf", "28" if a.draft else "17",
                "-movflags", "+faststart", a.out]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    if a.stills:
        os.makedirs(a.stills, exist_ok=True)

    prev_last = None
    prev, cache = {}, {}
    try:
        for si, scene in enumerate(sb["scenes"]):
            built = build_scene(scene, si, pal, fonts_dir, variants, prev, cache)
            dur = scene.get("duration", 3.0)
            # elements with an "id" can be carried into the next scene (unless they disappear before it ends)
            prev = {el["id"]: el for el, _ in built
                    if el.get("id") and not el.get("_caption") and not (el.get("until") is not None and el["until"] <= dur)}
            tf_scene = scene.get("transition", 0.0 if scene.get("carry") else tf)
            if a.stills:
                frame_at(bg, built, dur, boil).save(os.path.join(a.stills, f"scene_{si + 1:02d}.png"))
                print("still", si + 1)
                continue
            n = max(1, int(round(dur * fps)))
            last_key, last_bytes, last = None, None, None
            for k in range(n):
                t = k / fps
                ops = frame_ops(built, t, boil)
                key = ops_key(ops)
                blending = prev_last is not None and tf_scene > 0 and t < tf_scene
                if not blending and key == last_key:  # nothing changed since the previous frame
                    proc.stdin.write(last_bytes)
                    continue
                fr = render_ops(bg, ops)
                if blending:
                    fr = Image.blend(prev_last, fr, ease(t / tf_scene))
                last = fr
                last_key = None if blending else key
                last_bytes = fr.tobytes()
                proc.stdin.write(last_bytes)
            prev_last = last if last is not None else prev_last
            print(f"scene {si + 1}/{len(sb['scenes'])} done", flush=True)
        if proc:
            proc.stdin.close()
            rc = proc.wait()
            if rc != 0:
                raise SystemExit(f"ffmpeg failed (exit {rc}); see message above")
            print("wrote", a.out)
    except BrokenPipeError:
        proc.wait()
        raise SystemExit("ffmpeg stopped unexpectedly (see its message above); no video written")


if __name__ == "__main__":
    main()

