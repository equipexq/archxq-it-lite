# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A LEVEL'S REFERENCE — an image or a PDF page lying on its floor, to draw
over (PLANO_REFERENCIAS_NIVEL.md — his ask, 18/11/2026: «colocar imagens e
ou PDFs nos níveis… para trabalhar em cima»; support #83: a JPG's scale set
by hand with a rule of three).

The picture itself is the host's own ``ImagePlane`` (``File ▸ Import ▸
Image``: reference, never geometry, kept inside the .igz): ArchXQ puts it
on the level, on that level's own «Reference» layer, and gives it its SCALE
from two points and a length typed, straightened when the line is nearly
level, and placed by a point.

A frame is (origin, u, v), each (x, y, z), the host's ImagePlane
(``core.image_plane``): ``origin`` the picture's BOTTOM-left corner, ``u``
along its width, ``v`` UP its height — its corners origin, +u, +u+v, +v
counter-clockwise seen from its front (its top row at origin + v: seen
live 18/11/2026, a PDF page laid with v down came upside down). The
lengths of u and v are its real size in metres. On a floor: u, v
horizontal, its front up.

A point ON the picture is given as fractions (fu, fv) from its TOP-left
corner (fv down — as a page reads, as pdfread gives its lines).

Pure: no Qt, no host.
"""
from __future__ import annotations

import math
import re

#: the layer a level's references sit on — shown only while that level is
#: the one worked on (as its blue sheet, levelsheet.py)
SUFFIX = " · Reference"
#: (m) over the level's finished floor. Not a hair: 1 mm is lost under the
#: floors already made on the level (plan view from afar: the depth buffer
#: cannot tell them apart — seen live 18/11/2026); 5 cm always reads (the
#: plan view is parallel: nothing shifts; clicks snap to the PDF's lines)
LIFT = 0.05
#: (m) an image's width when it comes in: then it is measured (Measure)
FIRST_W = 20.0
#: (m) between two references of one level, side by side (next_corner)
GAP = 1.0
#: a line this near to level (or plumb) is made exactly so by Measure
STRAIGHT_MAX = 5.0          # degrees
STRAIGHT_MIN = 0.01         # degrees: under it, nothing to turn
#: a PDF page raster: this many dots per inch, the longer side at most
DPI = 300
MAX_PX = 7000
#: the paper scales offered (1:n); the one read from the PDF's text is one
SCALES = (1, 2, 5, 10, 20, 25, 50, 75, 100, 125, 200, 250, 500, 1000,
          2000, 2500, 5000)
PT = 0.0254 / 72.0          # m in a PDF point


def ref_layer(level_layer: str) -> str:
    """The references' layer of the level whose layer is ``level_layer``
    («ArchXQ · Level 1» → «ArchXQ · Level 1 · Reference»)."""
    return level_layer + SUFFIX


def is_ref_layer(name) -> bool:
    return isinstance(name, str) and name.endswith(SUFFIX)


# ---- frames ------------------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def first_frame(aspect: float, centre, z: float, width: float = FIRST_W):
    """An image's frame when it comes in: ``width`` wide, upright as seen
    from above (its top towards +Y), centred on ``centre`` (x, y), at
    ``z``. ``aspect``: its pixel height / width."""
    w = float(width)
    h = w * float(aspect or 1.0)
    cx, cy = centre
    return ((cx - w / 2, cy - h / 2, z), (w, 0.0, 0.0), (0.0, h, 0.0))


def page_frame(w_pt: float, h_pt: float, scale: float, centre, z: float):
    """A PDF page's frame at the paper scale 1:``scale`` — its real size:
    a point is 1/72 in on the paper."""
    w = w_pt * PT * float(scale)
    return first_frame(h_pt / w_pt if w_pt else 1.0, centre, z, w)


def at_z(frame, z: float):
    """The frame lying at ``z`` (a level moved up or down)."""
    o, u, v = frame
    return ((o[0], o[1], z), u, v)


def uv_of(frame, p) -> tuple:
    """Point ``p`` (x, y — on the floor) as fractions of the picture: (0, 0)
    its top-left corner, (1, 1) the opposite one."""
    o, u, v = frame
    dx, dy = p[0] - o[0], p[1] - o[1]
    det = u[0] * v[1] - u[1] * v[0]
    if abs(det) < 1e-18:
        return (0.0, 0.0)
    return ((dx * v[1] - dy * v[0]) / det,
            1.0 - (u[0] * dy - u[1] * dx) / det)


def world_of(frame, f) -> tuple:
    """Fractions ``f`` (fu, fv — from the top-left) of the picture → the
    point (x, y, z)."""
    o, u, v = frame
    return _add(o, _add(_mul(u, f[0]), _mul(v, 1.0 - f[1])))


def _turned(p, c, ang: float):
    ca, sa = math.cos(ang), math.sin(ang)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * ca - y * sa, c[1] + x * sa + y * ca, p[2])


def _turn_vec(d, ang: float):
    ca, sa = math.cos(ang), math.sin(ang)
    return (d[0] * ca - d[1] * sa, d[0] * sa + d[1] * ca, d[2])


def off_axis(a, b) -> float:
    """Degrees the line a→b is off the nearest axis (signed: + turns it
    anticlockwise onto it)."""
    ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    near = round(ang / 90.0) * 90.0
    return near - ang


def measured(frame, a, b, real: float, straighten: bool = True):
    """(new frame, factor, degrees turned): the frame scaled about ``a``
    so that a→b (points on it, x y) measures ``real`` metres — and, when
    the line is under STRAIGHT_MAX off an axis, turned about ``a`` onto it
    (a scan a little askew). None: a and b one point, or no length."""
    d = math.hypot(b[0] - a[0], b[1] - a[1])
    if d < 1e-9 or not real or real <= 0:
        return None
    k = float(real) / d
    o, u, v = frame
    a3 = (a[0], a[1], o[2])
    o2 = _add(a3, _mul(_sub(o, a3), k))
    u2, v2 = _mul(u, k), _mul(v, k)
    turn = 0.0
    if straighten:
        dev = off_axis(a, b)
        if STRAIGHT_MIN <= abs(dev) <= STRAIGHT_MAX:
            turn = dev
            r = math.radians(dev)
            o2 = _turned(o2, a3, r)
            u2, v2 = _turn_vec(u2, r), _turn_vec(v2, r)
    return (o2, u2, v2), k, turn


def centre_of(frame) -> tuple:
    """The picture's middle (x, y)."""
    c = world_of(frame, (0.5, 0.5))
    return (c[0], c[1])


def box_of(frame) -> tuple:
    """(x0, y0, x1, y1): the picture's extent seen from above."""
    o, u, v = frame
    xs = [o[0], o[0] + u[0], o[0] + u[0] + v[0], o[0] + v[0]]
    ys = [o[1], o[1] + u[1], o[1] + u[1] + v[1], o[1] + v[1]]
    return (min(xs), min(ys), max(xs), max(ys))


def corner_at(frame, x: float, y: float):
    """The frame moved so that its lower-left corner lies on (x, y)."""
    x0, y0, _x1, _y1 = box_of(frame)
    o, u, v = frame
    return ((o[0] + x - x0, o[1] + y - y0, o[2]), u, v)


def next_corner(frames) -> tuple:
    """Where a new reference's lower-left corner goes (his call, 18/11):
    the ORIGIN — on a level that has some already, at the right of them
    (GAP between), on the origin's line: never one over the other."""
    frames = list(frames or ())
    if not frames:
        return (0.0, 0.0)
    return (max(box_of(f)[2] for f in frames) + GAP, 0.0)


def scaled(frame, k: float, about=None):
    """The frame ``k`` times as big about point ``about`` (x, y — its
    lower-left corner when None: a page laid at the origin stays there): a
    PDF page put at another paper scale."""
    o, u, v = frame
    c = about or box_of(frame)[:2]
    k = float(k)
    return ((c[0] + (o[0] - c[0]) * k, c[1] + (o[1] - c[1]) * k, o[2]),
            _mul(u, k), _mul(v, k))


def page_scale(frame, w_pt: float) -> float:
    """The paper scale (1:n → n) the page is at now (its width / the
    paper's)."""
    return size_of(frame)[0] / (w_pt * PT) if w_pt else 0.0


def moved(frame, a, to):
    """The frame moved so that its point ``a`` (x, y) lies on ``to``."""
    o, u, v = frame
    return ((o[0] + to[0] - a[0], o[1] + to[1] - a[1], o[2]), u, v)


def size_of(frame) -> tuple:
    """(width, height) in metres."""
    _o, u, v = frame
    return (math.hypot(u[0], u[1], u[2]), math.hypot(v[0], v[1], v[2]))


# ---- a PDF page ----------------------------------------------------------------------
def raster_px(w_pt: float, h_pt: float, dpi: int = DPI,
              cap: int = MAX_PX) -> tuple:
    """(width, height) in pixels of a page drawn at ``dpi``, its longer
    side at most ``cap``."""
    w, h = w_pt / 72.0 * dpi, h_pt / 72.0 * dpi
    big = max(w, h, 1.0)
    if big > cap:
        w, h = w * cap / big, h * cap / big
    return max(1, int(round(w))), max(1, int(round(h)))


#: «1:100», «1 : 50», «1/200», «ESC. 1/50», «Scale 1:100», «M 1:50»,
#: «Maßstab 1:100», «Escala 1:75»
_SCALE = re.compile(r"(?<![\d.,])1\s*[:/]\s*(\d{1,4})(?![\d.,/:])")
_WORD = re.compile(r"(esc|scale|ma(ß|ss)stab|\bm\b|massstab|échelle|echelle)"
                   r"[^\d]{0,12}$", re.I)


def scale_from_text(text: str):
    """The paper scale a PDF's text states (1:n → n), or None. A scale
    written after «Scale / Escala / Maßstab / M» counts first; else the
    one written most often. Only the usual scales (SCALES)."""
    if not text:
        return None
    named, seen = {}, {}
    for m in _SCALE.finditer(text):
        n = int(m.group(1))
        if n not in SCALES or n == 1:
            continue
        word = _WORD.search(text[max(0, m.start() - 16):m.start()])
        # «1/2» alone is a sheet number (sheet 1 of 2), not a scale
        if not word and "/" in m.group(0) and n < 20:
            continue
        seen[n] = seen.get(n, 0) + 1
        if word:
            named[n] = named.get(n, 0) + 1
    pick = named or seen
    if not pick:
        return None
    return max(sorted(pick), key=lambda n: pick[n])


# ---- a PDF page's lines --------------------------------------------------------------
def weight_name(w_mm: float) -> str:
    """A line weight's «layer» name: the pen it was drawn with."""
    return f"{max(0.0, w_mm):.2f} mm"


def weight_layers(items) -> tuple:
    """``items``: [(fu0, fv0, fu1, fv1, w_mm)…] → (names, segs, wall layer):
    the weights as «layers» (thickest first), each item as
    (fu0, fv0, fu1, fv1, its layer's index), and the layer the walls are
    drawn with — the thickest pen carrying a good part (≥ 5 %) of the
    drawing's length (a wall's outline is drawn thicker than the rest)."""
    by: dict = {}
    for it in items:
        name = weight_name(float(it[4]))        # (0.01 mm: the pens' own)
        L = math.hypot(it[2] - it[0], it[3] - it[1])
        by[name] = by.get(name, 0.0) + L
    names = sorted(by, key=lambda n: -float(n.split()[0]))
    idx = {n: i for i, n in enumerate(names)}
    segs = [(it[0], it[1], it[2], it[3],
             idx[weight_name(float(it[4]))])
            for it in items]
    total = sum(by.values()) or 1.0
    wall = next((n for n in names if by[n] >= 0.05 * total
                 and float(n.split()[0]) > 0.0), "")
    return names, segs, wall


def segs_in_world(frame, uv_segs) -> list:
    """The page's lines (fractions of the frame) as the level's drawing:
    (x0, y0, x1, y1, layer) in metres — as a DXF's (importdxf.placed)."""
    out = []
    for s in uv_segs:
        a = world_of(frame, (s[0], s[1]))
        b = world_of(frame, (s[2], s[3]))
        out.append((round(a[0], 5), round(a[1], 5), round(b[0], 5),
                    round(b[1], 5)) + tuple(s[4:5]))
    return out
