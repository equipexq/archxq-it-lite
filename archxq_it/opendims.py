"""The DIMENSIONS of a door / window on its wall (PLANO_COTAS_ABERTURAS.md —
Nazareno, support #60, his OK 2026-10-25: «in my BIM I hover a corner,
type 60, Enter, and the door is 60 cm from it»).

While an opening is placed — and while one selected is moved by its
middle grip — two dimensions run along the wall's face on the cursor's
side: from each EDGE of the opening to the corner of that face (``wall_bay``,
corner face to corner face) or to the nearer edge of a neighbouring
opening. The one nearer the cursor is «hot» (orange): a typed distance +
Enter puts the opening's EDGE that far from its reference; «c» at the end
(``1.05c``) measures to the opening's CENTRE instead.

Pure geometry here (tested in tests/test_opening_dims.py), and the
drawing.
"""
from __future__ import annotations

import math

from . import structure as S, walls as W

HOT = "#e8742c"         # the dimension a typed number uses
COLD = "#0a84ff"        # the other one
GREY = "#5b6470"        # a selected opening's, at rest
OUT = 0.35              # m off the wall's face, into the room
BAY_PAD = 0.002         # structure.wall_bay's buffer round the other walls


def face_of(wall: dict, p) -> float:
    """+1 / −1: the side of the wall's centre line the point is on."""
    _f, off = W.centre(wall).project(p)
    return 1.0 if off >= 0 else -1.0


def refs(walls: list, wall: dict, pos: float, face: float,
         openings: list, skip: str | None = None, bay=None) -> tuple:
    """(lo, hi) along the wall's centre line: what an opening at ``pos``
    is measured from on each side — the corner of the face (``face``) or
    the nearer edge of another opening of the same wall (``skip``: its own
    id). ``bay``: the face's (s0, s1), already read."""
    lo, hi = bay if bay is not None else S.wall_bay({"walls": walls}, wall,
                                                    pos, face)
    # ``wall_bay`` reads the other walls grown by 2 mm (no slit between
    # them): a corner is that much nearer — back on the face, exactly
    if lo > 1e-6:
        lo -= BAY_PAD
    if hi < W.centre(wall).L - 1e-6:
        hi += BAY_PAD
    for o in openings:
        if o.get("wall") != wall["id"] or (skip and o.get("id") == skip):
            continue
        half = float(o["w"]) / 2
        e0, e1 = float(o["pos"]) - half, float(o["pos"]) + half
        if e1 <= pos + 1e-6:
            lo = max(lo, e1)
        elif e0 >= pos - 1e-6:
            hi = min(hi, e0)
    return lo, hi


def hot_side(cursor: float, lo: float, hi: float) -> str:
    """«lo» / «hi»: the reference nearer the cursor."""
    return "lo" if cursor - lo <= hi - cursor else "hi"


def parse(text: str):
    """A typed distance: (metres, to the centre?) or None. «60» = 60 cm
    (a bare number over 10, as everywhere in ArchXQ), «0.6», «60cm»,
    «2'», «1.05c» = to the centre."""
    from .library import parse_measure
    raw = (text or "").strip()
    centre = raw.lower().endswith("c") and not raw.lower().endswith("mc")
    if centre:
        raw = raw[:-1].strip()
    v = parse_measure(raw, "m")
    if v is None or not math.isfinite(v) or v < 0:
        return None
    return v, centre


def pos_for(d: float, side: str, lo: float, hi: float, w: float,
            centre: bool = False) -> float:
    """The opening's centre along the wall: its edge (or its centre) ``d``
    from the reference on ``side``."""
    k = 0.0 if centre else w / 2
    return round(lo + d + k if side == "lo" else hi - d - k, 4)


def gaps(pos: float, w: float, lo: float, hi: float) -> tuple:
    """(left gap, right gap): edge to reference on each side."""
    return pos - w / 2 - lo, hi - pos - w / 2


def draw(viewport, painter, wall: dict, face: float, z: float, pos: float,
         w: float, lo: float, hi: float, hot: str | None,
         typed: str = "") -> None:
    """The two dimensions on the face's side, OUT into the room, at the
    floor: extension marks at both ends, the value in a pill (the hot one
    orange — and showing what is being typed)."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QPen
    from . import compat
    seg = W.centre(wall)
    p0, u = seg.p0, seg.u
    n = (-u[1] * face, u[0] * face)
    t = float(wall["t"]) / 2

    def px(s, c):
        return compat.to_pixel(viewport, p0[0] + u[0] * s + n[0] * c,
                               p0[1] + u[1] * s + n[1] * c, z + 0.02)
    g0, g1 = gaps(pos, w, lo, hi)
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    f = QFont(painter.font())
    f.setPointSizeF(9)
    f.setBold(True)
    painter.setFont(f)
    fm = painter.fontMetrics()
    for side, a, b, g in (("lo", lo, pos - w / 2, g0),
                          ("hi", pos + w / 2, hi, g1)):
        if g < 0.005:
            continue
        ink = QColor(HOT if side == hot else (COLD if hot else GREY))
        A, B = px(a, t + OUT), px(b, t + OUT)
        if not A or not B:
            continue
        painter.setPen(QPen(ink, 1.5))
        painter.drawLine(QPointF(*A), QPointF(*B))
        for s in (a, b):                   # extension marks, face to line
            E0, E1 = px(s, t + 0.04), px(s, t + OUT + 0.08)
            if E0 and E1:
                painter.drawLine(QPointF(*E0), QPointF(*E1))
        text = (typed + "_") if (typed and side == hot) \
            else compat.fmt_num(g)
        bw, bh = fm.horizontalAdvance(text) + 10, fm.height() + 2
        c = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2)
        r = QRectF(c[0] - bw / 2, c[1] - bh / 2, bw, bh)
        painter.setPen(QPen(ink, 1))
        painter.setBrush(QColor(255, 255, 255, 235))
        painter.drawRoundedRect(r, 4, 4)
        painter.setPen(ink)
        painter.drawText(r, Qt.AlignCenter, text)
    painter.restore()
