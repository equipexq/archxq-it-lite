# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The doors' and windows' cards, drawn from the front (04/11/2026,
PLANO_PORTAS_JANELAS_CARTOES.md): a card tells at a glance what it is — its
frame, glass, leaves, how each opens. ``window(p, **spec)``, ``door(p, **spec)``
paint on the library's 96 × 96 picture."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainterPath, QPen

INK = QColor("#d6d9dd")
ACCENT = QColor("#e8742c")
BLUE = QColor("#8fc3dd")
WOOD = QColor("#a8743f")
WOOD_DARK = QColor("#6e4a27")
STEEL = QColor("#9ea5ac")


def _pen(c=INK, w=2.5, dash=False) -> QPen:
    pen = QPen(c, w)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    if dash:
        pen.setStyle(Qt.DashLine)
    return pen


def _glass() -> QColor:
    g = QColor(BLUE)
    g.setAlpha(150)
    return g


def _pane(p, x0, y0, x1, y1, brush=None, ink=INK, w=2.0) -> None:
    p.setPen(_pen(ink, w))
    p.setBrush(brush if brush is not None else _glass())
    p.drawRect(QRectF(x0, y0, x1 - x0, y1 - y0))


def _bars(p, x0, y0, x1, y1, nx, nz, ink=INK) -> None:
    p.setPen(_pen(ink, 1.3))
    for i in range(nx):
        x = x0 + (x1 - x0) * (i + 1) / (nx + 1)
        p.drawLine(QPointF(x, y0), QPointF(x, y1))
    for i in range(nz):
        y = y0 + (y1 - y0) * (i + 1) / (nz + 1)
        p.drawLine(QPointF(x0, y), QPointF(x1, y))


def _hinge(p, x0, y0, x1, y1, right: bool) -> None:
    """The drawings' triangle: its tip on the hinge's side."""
    hx, fx = (x1, x0) if right else (x0, x1)
    p.setPen(_pen(ACCENT, 1.8, True))
    p.drawLine(QPointF(fx, y0), QPointF(hx, (y0 + y1) / 2))
    p.drawLine(QPointF(fx, y1), QPointF(hx, (y0 + y1) / 2))


def _arrow(p, x0, y0, x1, y1) -> None:
    import math
    p.setPen(_pen(ACCENT, 2.4))
    p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
    a = math.atan2(y1 - y0, x1 - x0)
    for s in (-1, 1):
        p.drawLine(QPointF(x1, y1), QPointF(x1 - 7 * math.cos(a + s * 0.55),
                                            y1 - 7 * math.sin(a + s * 0.55)))


def _louvres(p, x0, y0, x1, y1) -> None:
    p.setPen(_pen(INK, 1.3))
    y = y0 + 4
    while y < y1 - 2:
        p.drawLine(QPointF(x0 + 1, y), QPointF(x1 - 1, y))
        y += 5


def window(p, op="fixed", n=1, roles="", widths=(), bars=(0, 0), top=False,
           louvred=0, dark=False, box=(12, 16, 84, 80)) -> None:
    """A window from the front: ``op`` fixed | sliding | casement | awning |
    pivot | hung; ``roles`` a casement's (L R F); ``widths`` its leaves'
    shares (0: alike); ``louvred`` how many of its leaves are louvres."""
    x0, y0, x1, y1 = box
    ink = QColor("#1b1d20") if dark else INK
    p.setPen(_pen(ink, 3.8 if dark else 3.2))
    p.setBrush(_glass())
    p.drawRect(QRectF(x0, y0, x1 - x0, y1 - y0))
    if top:
        ym = y0 + (y1 - y0) * 0.30
        p.setPen(_pen(INK, 2.4))
        p.drawLine(QPointF(x0, ym), QPointF(x1, ym))
        y0 = ym
    nx, nz = bars
    if op == "fixed":
        _bars(p, x0, y0, x1, y1, nx, nz, ink if dark else INK)
        return
    if op == "hung":
        ym = (y0 + y1) / 2
        p.setPen(_pen(INK, 2.4))
        p.drawLine(QPointF(x0, ym), QPointF(x1, ym))
        _bars(p, x0, y0, x1, ym, nx, nz)
        _bars(p, x0, ym, x1, y1, nx, nz)
        _arrow(p, x1 - 11, y1 - 5, x1 - 11, ym + 5)
        return
    if op == "awning":
        _hinge_h(p, x0, y0, x1, y1)
        return
    if op == "pivot":
        k = 4
        for i in range(k):
            ya = y0 + (y1 - y0) * i / k
            yb = y0 + (y1 - y0) * (i + 1) / k
            if i:
                p.setPen(_pen(INK, 2.0))
                p.drawLine(QPointF(x0, ya), QPointF(x1, ya))
            p.setPen(_pen(ACCENT, 1.5, True))
            p.drawLine(QPointF(x0 + 3, (ya + yb) / 2),
                       QPointF(x1 - 3, (ya + yb) / 2))
        return
    k = len(roles) if op == "casement" and roles else n
    shares = [float(s) for s in widths] if widths else [1.0] * k
    tot = sum(shares) or 1.0
    xs, x = [], x0
    for s in shares:
        xs.append((x, x + (x1 - x0) * s / tot))
        x = xs[-1][1]
    for i, (a, b) in enumerate(xs):
        if i:
            p.setPen(_pen(INK, 2.4))
            p.drawLine(QPointF(a, y0), QPointF(a, y1))
        if i < louvred:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#50565d"))
            p.drawRect(QRectF(a + 1, y0 + 1, b - a - 2, y1 - y0 - 2))
            _louvres(p, a, y0, b, y1)
        _bars(p, a, y0, b, y1, nx, nz)
        if op == "casement" and roles and roles[i] != "F":
            _hinge(p, a, y0, b, y1, roles[i] == "R")
    if op == "sliding":
        m = (x0 + x1) / 2
        _arrow(p, m + 9, y1 - 9, m - 9, y1 - 9)


def _hinge_h(p, x0, y0, x1, y1) -> None:
    """A leaf hinged at its top: the triangle's tip up."""
    p.setPen(_pen(ACCENT, 1.8, True))
    m = (x0 + x1) / 2
    p.drawLine(QPointF(x0, y1), QPointF(m, y0))
    p.drawLine(QPointF(x1, y1), QPointF(m, y0))


def shaped(p, shape: str, op: str = "fixed") -> None:
    """A window with a shape: its outline, glass in it — ``op`` casement: the
    leaves under the spring."""
    from . import shapes as SH
    o = {"kind": "window", "shape": shape, "pos": 0.5, "sill": 0.0,
         "w": 0.72 if shape == "oval" else 1.0, "h": 1.0}
    o.update(SH.clean(o))
    if shape == "pentagon":
        o["rise"] = 0.36
    if shape == "seg_arch":
        o["rise"] = 0.24
    if shape == "pointed":
        o["rise"] = 0.60
    if shape == "trapezoid":
        o["top_w"] = 0.55
    loop = SH.outline(o, 0.0, steps=24) or [(0, 0), (1, 0), (1, 1), (0, 1)]
    m, s = 14.0, 68.0
    path = QPainterPath()
    for i, (x, z) in enumerate(loop):
        q = QPointF(m + x * s, m + (1 - z) * s)
        path.moveTo(q) if i == 0 else path.lineTo(q)
    path.closeSubpath()
    p.setPen(_pen(INK, 3.2))
    p.setBrush(_glass())
    p.drawPath(path)
    if op == "casement":
        zp = SH.spring(o, 0.0)
        if zp is not None:
            y = m + (1 - zp) * s
            mid = m + s / 2
            p.setPen(_pen(INK, 2.4))
            p.drawLine(QPointF(m, y), QPointF(m + s, y))
            p.drawLine(QPointF(mid, y), QPointF(mid, m + s))
            _hinge(p, m, y, mid, m + s, False)
            _hinge(p, mid, y, m + s, m + s, True)


# ---- doors -----------------------------------------------------------------
def _leaf(p, x0, y0, x1, y1, style: str) -> None:
    if style == "glass":
        _pane(p, x0, y0, x1, y1)
        return
    wood = QColor(WOOD)
    _pane(p, x0, y0, x1, y1, wood, INK, 2.0)
    w, h = x1 - x0, y1 - y0
    p.setBrush(Qt.NoBrush)
    if style == "half":
        _pane(p, x0 + w * .16, y0 + h * .09, x1 - w * .16, y0 + h * .48)
    elif style == "panels":
        p.setPen(_pen(WOOD_DARK, 1.6))
        p.drawRect(QRectF(x0 + w * .18, y0 + h * .08, w * .64, h * .36))
        p.drawRect(QRectF(x0 + w * .18, y0 + h * .52, w * .64, h * .38))
    elif style == "six":
        p.setPen(_pen(WOOD_DARK, 1.4))
        pw, ph = w * .32, h * .23
        for i in (0, 1):
            for j in (0, 1, 2):
                p.drawRect(QRectF(x0 + w * (.12 + i * .44),
                                  y0 + h * (.07 + j * .30), pw, ph))
    elif style == "planks":
        p.setPen(_pen(WOOD_DARK, 1.2))
        k = max(3, round(w / 6))
        for i in range(1, k):
            x = x0 + w * i / k
            p.drawLine(QPointF(x, y0), QPointF(x, y1))
        p.setPen(_pen(WOOD_DARK, 2.4))
        for f in (.12, .5, .88):
            p.drawLine(QPointF(x0 + 1, y0 + h * f), QPointF(x1 - 1, y0 + h * f))
        p.drawLine(QPointF(x0 + 2, y0 + h * .88), QPointF(x1 - 2, y0 + h * .5))
    elif style == "dutch":
        p.setPen(_pen(QColor("#1b1d20"), 2.0))
        p.drawLine(QPointF(x0, y0 + h * .5), QPointF(x1, y0 + h * .5))
        p.setPen(_pen(INK, 2.6))
        p.drawLine(QPointF(x0 - 1, y0 + h * .54), QPointF(x1 + 1, y0 + h * .54))


def door(p, style="solid", n=1, op="swing", top=False, wide=False) -> None:
    """A door from the front: its frame on the floor, its leaf or leaves in
    ``style``; ``top``: a glass light over it; ``op`` sliding: the rail and
    the arrow."""
    x0, x1 = (16, 80) if n == 2 or wide else (28, 68)
    y0, y1 = 8, 90
    p.setPen(_pen(INK, 2.5))
    p.drawLine(QPointF(8, y1), QPointF(88, y1))
    if op == "sliding" and style != "glass":
        x0, x1 = x0 - 8, x1 - 8
        p.setPen(_pen(ACCENT, 2.8))
        p.drawLine(QPointF(x0 - 3, y0 + 2), QPointF(92, y0 + 2))
        y0 += 5
    ya = y0
    if top:
        ya = y0 + 16
        _pane(p, x0, y0, x1, ya)
    if n == 2:
        m = (x0 + x1) / 2
        _leaf(p, x0, ya, m, y1, style)
        _leaf(p, m, ya, x1, y1, style)
    else:
        _leaf(p, x0, ya, x1, y1, style)
    zh = ya + (y1 - ya) * .56
    if op == "sliding":
        m = (x0 + x1) / 2
        _arrow(p, m - 11, zh, m + 13, zh)
        return
    p.setPen(_pen(ACCENT, 2.6))
    if n == 2:
        m = (x0 + x1) / 2
        p.drawLine(QPointF(m - 5, zh), QPointF(m - 1.5, zh))
        p.drawLine(QPointF(m + 1.5, zh), QPointF(m + 5, zh))
    else:
        p.drawLine(QPointF(x1 - 9, zh), QPointF(x1 - 3, zh))


def door_arched(p) -> None:
    """A swing door under a round arch: a half-round glass light over it."""
    p.setPen(_pen(INK, 2.5))
    p.drawLine(QPointF(8, 90), QPointF(88, 90))
    path = QPainterPath(QPointF(26, 34))
    path.arcTo(QRectF(26, 12, 44, 44), 180, -180)
    path.closeSubpath()
    p.setPen(_pen(INK, 2.2))
    p.setBrush(_glass())
    p.drawPath(path)
    _leaf(p, 26, 34, 70, 90, "solid")
    p.setPen(_pen(ACCENT, 2.6))
    p.drawLine(QPointF(61, 62), QPointF(67, 62))


def garage(p, kind: str = "sectional") -> None:
    p.setPen(_pen(INK, 2.5))
    p.drawLine(QPointF(4, 88), QPointF(92, 88))
    _pane(p, 8, 28, 88, 88, QColor("#6d747c"), INK, 3.0)
    p.setPen(_pen(INK, 1.2 if kind == "rollup" else 1.8))
    if kind == "rollup":
        p.setBrush(QColor("#50565d"))
        p.drawRect(QRectF(6, 18, 84, 10))
        for y in range(32, 88, 5):
            p.drawLine(QPointF(9, y), QPointF(87, y))
    elif kind == "tilt":
        for x in (28, 48, 68):
            p.drawLine(QPointF(x, 29), QPointF(x, 87))
    else:
        for y in (43, 58, 73):
            p.drawLine(QPointF(9, y), QPointF(87, y))
    _arrow(p, 48, 76, 48, 44)


# ---- the «By market» cards (04/11/2026): what it stands on at a glance — its
# frame in small 3D (timber or steel C, deep as it is), its market and its
# size in a seal, its layers in a band at the foot
#: (market seal, size seal) per card
SEALS = {"us2x4": ("US", "2×4"), "us2x6": ("US", "2×6"), "usint": ("US", "2×4"),
         "eutimber": ("EU", "16 cm"), "lsf": ("", "C90"), "drywall": ("", "CW75"),
         "ukcavity": ("UK", ""), "etics": ("EU", ""),
         "rus2x8": ("US", "2×8"), "reutimber": ("EU", "18 cm"),
         "rsteel": ("", "C200"), "rcold": ("", "16 cm"),
         "rustruss": ("US", "24 in"), "reutruss": ("EU", ""),
         "fus2x10": ("US", "2×10"), "feutimber": ("EU", ""), "fsteel": ("", ""),
         "fraised": ("", "")}
TIMBER = QColor("#d8b27a")
TIMBER_EDGE = QColor("#7c5c34")
STEEL_C = QColor("#b4bbc3")
STEEL_EDGE = QColor("#59616a")
WOOL = QColor("#edcc78")
#: a layer's colour by what its name says (a roof's and a floor's have no «mat»)
_BY_NAME = (("asphalt", "#4b4e54"), ("clay", "#b5603c"), ("tile", "#c9c4b8"),
            ("metal", "#a9b0b8"), ("batten", "#b08a58"), ("osb", "#cca86b"),
            ("sheath", "#cca86b"), ("fibre", "#9a7047"), ("gypsum", "#efeee6"),
            ("plaster", "#efeee6"), ("siding", "#dfdcd0"), ("cladding", "#8d9299"),
            ("render", "#e8e4da"), ("brick", "#b5654a"), ("block", "#9a9ea2"),
            ("cavity", "#30343a"), ("eps", "#f6f6f0"), ("masonry", "#c0784f"),
            ("floor", "#a8743f"), ("timber", "#a8743f"), ("screed", "#a7a9a6"),
            ("underlay", "#55585c"), ("sub", "#cca86b"), ("plywood", "#cca86b"))


def _layer_colour(la: dict) -> QColor:
    mat = la.get("mat") or {}
    if mat.get("color"):
        r, g, b = mat["color"][:3]
        return QColor.fromRgbF(r, g, b)
    name = str(la.get("name") or "").lower()
    lib = str(mat.get("lib") or "")
    for word, col in (("white_wood", "#dfdcd0"), ("gray_wood", "#8d9299"),
                      ("roughcast", "#e8e4da"), ("brick_red", "#b5654a"),
                      ("concrete_blocks", "#9a9ea2"),
                      ("brick_clay", "#c0784f")):
        if word in lib:
            return QColor(col)
    for word, col in _BY_NAME:
        if word in name:
            return QColor(col)
    return QColor("#b5654a" if la.get("role") == "core" else "#d9d4c7")


def _seal(p, x, y, text: str, fill: str, right: bool = False) -> None:
    from PySide6.QtGui import QFont
    f = QFont("Arial")
    f.setBold(True)
    f.setPixelSize(12)
    p.setFont(f)
    w = p.fontMetrics().horizontalAdvance(text) + 7
    r = QRectF(x - w if right else x, y, w, 15)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(fill))
    p.drawRoundedRect(r, 3, 3)
    p.setPen(QColor("#ffffff"))
    p.drawText(r, Qt.AlignCenter, text)


def _poly(p, *pts) -> None:
    from PySide6.QtGui import QPolygonF
    p.drawPolygon(QPolygonF([QPointF(*q) for q in pts]))


def _bar3d(p, x0, y0, x1, y1, dx, dy, face, edge) -> None:
    """A piece in oblique: its front, its top and its side, ``dx``, ``dy``
    deep."""
    p.setPen(_pen(edge, 0.9))
    p.setBrush(face.lighter(115))
    _poly(p, (x0, y0), (x1, y0), (x1 + dx, y0 - dy), (x0 + dx, y0 - dy))
    p.setBrush(face.darker(125))
    _poly(p, (x1, y0), (x1 + dx, y0 - dy), (x1 + dx, y1 - dy), (x1, y1))
    p.setBrush(face)
    p.drawRect(QRectF(x0, y0, x1 - x0, y1 - y0))


def _frame_3d(p, frame: dict, depth: float) -> None:
    """A wall's frame: plates and studs, deep as its core (a 2×6 is seen
    deeper than a 2×4), in timber or in steel C."""
    steel = frame.get("kind") == "steel"
    face, edge = (STEEL_C, STEEL_EDGE) if steel else (TIMBER, TIMBER_EDGE)
    d = 6 + min(depth, 0.2) * 70                    # px of depth
    dx, dy = d * 0.85, d * 0.55
    x0, x1, yt, yb = 8.0, 88.0 - dx, 26.0, 60.0
    k = 3 if float(frame.get("s", 0.4)) > 0.5 else 4
    sw = 5.0
    if frame.get("fill") != "empty":                # the insulation behind
        p.setPen(Qt.NoPen)
        p.setBrush(WOOL)
        p.drawRect(QRectF(x0 + dx * .4, yt - dy * .4, x1 - x0, yb - yt))
    _bar3d(p, x0, yb - 4, x1, yb, dx, dy, face, edge)
    for i in range(k + 1):
        x = x0 + (x1 - x0 - sw) * i / k
        _bar3d(p, x, yt, x + sw, yb - 4, dx, dy, face, edge)
        if steel:                                   # the C's open side
            p.setPen(_pen(STEEL_EDGE, 1.0))
            p.drawLine(QPointF(x + 1.6, yt + 1), QPointF(x + 1.6, yb - 5))
            p.drawLine(QPointF(x + sw - 1.6, yt + 1),
                       QPointF(x + sw - 1.6, yb - 5))
    _bar3d(p, x0, yt - 4, x1, yt, dx, dy, face, edge)


def _masonry(p, layers) -> None:
    """Masonry: its leaves side by side, courses on them."""
    x, y0, y1 = 12.0, 22.0, 60.0
    tot = sum(float(la["t"]) for la in layers) or 1.0
    for la in layers:
        w = max(72.0 * float(la["t"]) / tot, 3.0)
        col = _layer_colour(la)
        p.setPen(_pen(QColor("#30343a"), 0.8))
        p.setBrush(col)
        p.drawRect(QRectF(x, y0, w, y1 - y0))
        n = str(la.get("name") or "").lower()
        if any(s in n for s in ("brick", "block", "masonry")):
            p.setPen(_pen(col.darker(150), 0.9))
            step = 5.0 if "block" not in n else 8.0
            yy, row = y0 + step, 0
            while yy < y1:
                p.drawLine(QPointF(x, yy), QPointF(x + w, yy))
                if w > 8:
                    q = x + w * (.3 if row % 2 else .7)
                    p.drawLine(QPointF(q, yy), QPointF(q, min(yy + step, y1)))
                yy += step
                row += 1
        x += w


def _roof_3d(p, frame, depth: float) -> None:
    steel = (frame or {}).get("kind") == "steel"
    face, edge = (STEEL_C, STEEL_EDGE) if steel else (TIMBER, TIMBER_EDGE)
    if (frame or {}).get("system") == "trusses":     # a Fink truss
        L, R, T = (8.0, 58.0), (88.0, 58.0), (48.0, 22.0)
        for a, b, w, c in ((L, T, 4.2, edge), (T, R, 4.2, edge),
                           (L, R, 4.2, edge), (L, T, 2.6, face),
                           (T, R, 2.6, face), (L, R, 2.6, face)):
            p.setPen(_pen(c, w))
            p.drawLine(QPointF(*a), QPointF(*b))
        p.setPen(_pen(face, 2.2))
        for a, b in (((35, 58), (28, 40)), ((61, 58), (68, 40)),
                     ((35, 58), (48, 22)), ((61, 58), (48, 22))):
            p.drawLine(QPointF(*a), QPointF(*b))
        return
    # rafters climbing in oblique, deep as they are
    d = 3.0 + min(depth, 0.25) * 22
    for i in range(4):
        x = 6.0 + i * 15.0
        y = 56.0
        p.setPen(_pen(edge, 0.9))
        p.setBrush(face)
        _poly(p, (x, y), (x + 34, y - 32), (x + 34, y - 32 + d), (x, y + d))
        if steel:
            p.setPen(_pen(STEEL_EDGE, 1.0))
            p.drawLine(QPointF(x + 2, y + d / 2 - 1),
                       QPointF(x + 32, y - 32 + d / 2 + 1))


def _floor_3d(p, frame, layers, depth: float) -> None:
    """A floor in section: the deck on its joists."""
    steel = (frame or {}).get("kind") == "steel"
    face, edge = (STEEL_C, STEEL_EDGE) if steel else (TIMBER, TIMBER_EDGE)
    p.setPen(_pen(edge, 0.9))
    p.setBrush(_layer_colour(layers[0]))
    p.drawRect(QRectF(8, 22, 80, 6))
    jh = 10.0 + min(depth, 0.3) * 80
    for i in range(4):
        x = 12.0 + i * 22.0
        _bar3d(p, x, 28, x + 6, 28 + jh, 3, 2, face, edge)
        if steel:
            p.setPen(_pen(STEEL_EDGE, 1.0))
            p.drawLine(QPointF(x + 1.5, 29), QPointF(x + 1.5, 27 + jh))
            p.drawLine(QPointF(x + 4.5, 29), QPointF(x + 4.5, 27 + jh))


def market(p, m, what: str = "wall") -> None:
    """A «By market» card: ``m`` markets.TYPES / ROOFS / FLOORS's row."""
    key, layers, frame = m[0], list(m[3]), m[4]
    core = next((la for la in layers if la.get("role") == "core"), None)
    depth = float(core["t"]) if core else 0.1
    if what == "roof":
        _roof_3d(p, frame, depth)
    elif what == "floor":
        _floor_3d(p, frame, layers, depth)
    elif frame:
        _frame_3d(p, frame, depth)
    else:
        _masonry(p, layers)
    # the layers, across, at the foot (each one seen, however thin) — a
    # wall's outside at the bottom, a roof's and a floor's top on top
    order = list(reversed(layers)) if what == "wall" else layers
    y0, y1 = 66.0, 92.0
    tot = sum(max(float(la["t"]), 0.022) for la in order) or 1.0
    y = y0
    for la in order:
        h = (y1 - y0) * max(float(la["t"]), 0.022) / tot
        if la.get("role") == "core" and frame:
            from .look import paint_frame
            paint_frame(p, QRectF(8, y, 80, h), frame, float(la["t"]))
        else:
            p.fillRect(QRectF(8, y, 80, h), _layer_colour(la))
        y += h
    p.setPen(_pen(INK, 1.4))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(8, y0, 80, y1 - y0))
    mk, size = SEALS.get(key, ("", ""))
    if mk:
        _seal(p, 2, 2, mk, {"US": "#2f5fb3", "EU": "#1f7a55",
                            "UK": "#a33a3a"}.get(mk, "#555555"))
    if size:
        _seal(p, 94, 2, size, "#3a3f45", right=True)
