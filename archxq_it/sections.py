# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""SECTION LINES IN THE SCENE — seen in the plan and moved with grips (his
ask, 23/10: «mover a linha de corte na cena»; ``PLANO_LINHA_DE_CORTE.md``,
5 decisions approved 24/10).

The lines are the sheets' (``sheetset.section_lines``): A-A and B-B made
through the building's middle, then the ones he drew (``doc["sections"]``).
In the Documentation phase, plan view, each is drawn dash-dot with its
letters and look arrows; a click picks one, its grips move it:

    a / b     its ends, anywhere on the plan (point grips)
    across    the whole line sideways (an arrow, a distance)
    look      the small arrow a quarter along it: a click flips the look

A made line moved is FROZEN where it was left: a record in
``doc["sections"]`` with its own id («A» / «B») — it stops following the
building's middle until «Back to automatic» (``unfreeze``).
"""
from __future__ import annotations

import math

#: px — a click this close to a line picks it
PICK_PX = 8
#: plan metres — the look arrows' length (as the drawing tool's)
ARROW_M = 1.0
INK = "#8e3fb4"         # (the plan's guides are blue dashes: not theirs)
HOT = "#f28c28"
AUTO_IDS = ("A", "B")


# ---- the lines -----------------------------------------------------------------------
def lines(doc: dict, style: dict) -> list[dict]:
    """Every section line of the set (``sheetset.section_lines``)."""
    from . import sheetset as SS
    return SS.section_lines(doc, style)


def look(line: dict) -> tuple:
    """The unit plan direction it looks in (to its left; flip: right)."""
    (ax, ay), (bx, by) = line["a"], line["b"]
    L = math.hypot(bx - ax, by - ay) or 1.0
    s = -1.0 if line.get("flip") else 1.0
    return (-(by - ay) / L * s, (bx - ax) / L * s)


def _seg_dist(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx
                                              + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def nearest(found: list[dict], p, reach: float):
    """The line nearest ``p`` (within ``reach`` m), or None."""
    best = None
    for ln in found:
        d = _seg_dist(p, ln["a"], ln["b"])
        if d <= reach and (best is None or d < best[0]):
            best = (d, ln)
    return best[1] if best else None


#: where the flip arrow stands along the line — a quarter in (the middle
#: holds the grip's arrow across)
FLIP_AT = 0.25


def flip_foot(line: dict) -> tuple:
    (ax, ay), (bx, by) = line["a"], line["b"]
    return (ax + (bx - ax) * FLIP_AT, ay + (by - ay) * FLIP_AT)


def look_tip(line: dict) -> tuple:
    """Where the flip arrow points to (a click on it flips the look)."""
    lx, ly = look(line)
    m = flip_foot(line)
    return (m[0] + lx * ARROW_M, m[1] + ly * ARROW_M)


# ---- changing one ----------------------------------------------------------------------
def store(doc: dict, line: dict) -> dict:
    """``doc`` with ``line`` stored as it is now — a drawn one replaced,
    a made one (A / B) FROZEN there (a record with its id)."""
    rec = {"id": line["id"], "symbol": line["symbol"],
           "a": [round(float(v), 4) for v in line["a"]],
           "b": [round(float(v), 4) for v in line["b"]],
           "flip": bool(line.get("flip"))}
    old = list(doc.get("sections") or [])
    if any(s["id"] == rec["id"] for s in old):
        new = [rec if s["id"] == rec["id"] else s for s in old]
    else:
        new = old + [rec]
    return dict(doc, sections=new)


def unfreeze(doc: dict, lid: str) -> dict:
    """A made line (A / B) back to following the building's middle."""
    return dict(doc, sections=[s for s in doc.get("sections") or []
                               if s["id"] != lid])


def moved(line: dict, key: str, v) -> tuple:
    """(the line with its grip ``key`` moved by ``v``, why not or None) —
    an end by (dx, dy), the whole line ``across`` by a distance."""
    a, b = list(line["a"]), list(line["b"])
    if key in ("a", "b"):
        p = a if key == "a" else b
        p = [p[0] + float(v[0]), p[1] + float(v[1])]
        if key == "a":
            a = p
        else:
            b = p
    elif key == "across":
        L = math.dist(a, b) or 1.0
        nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        a = [a[0] + nx * float(v), a[1] + ny * float(v)]
        b = [b[0] + nx * float(v), b[1] + ny * float(v)]
    else:
        return line, "Gone"
    if math.dist(a, b) < 0.5:
        return line, "A section line needs 0.50 m at least"
    return dict(line, a=a, b=b), None


def changed(doc: dict, line: dict, key: str, v) -> tuple:
    """(``doc`` with the line's grip moved, why not or None)."""
    new, why = moved(line, key, v)
    if why:
        return doc, why
    return store(doc, new), None


def grips(line: dict, z: float) -> list:
    """Its ends (free on the plan) and an arrow across at its middle."""
    from .grips import Grip
    (ax, ay), (bx, by) = line["a"], line["b"]
    L = math.hypot(bx - ax, by - ay) or 1.0
    n = (-(by - ay) / L, (bx - ax) / L)
    m = ((ax + bx) / 2, (ay + by) / 2)
    return [Grip("a", (ax, ay, z), (1.0, 0.0, 0.0), 0.0, "point",
                 tip="Its end — drag it anywhere"),
            Grip("b", (bx, by, z), (1.0, 0.0, 0.0), 0.0, "point",
                 tip="Its end — drag it anywhere"),
            Grip("across", (m[0], m[1], z), (n[0], n[1], 0.0), 0.0, "move",
                 True, "Move the section line across")]


# ---- the plan ----------------------------------------------------------------------
def draw(viewport, painter, found: list[dict], z: float,
         picked: str | None = None) -> None:
    """Dash-dot, its letters at the ends, the look arrows (the one picked:
    thicker, orange, with its flip arrow at the middle)."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QPen

    from . import compat
    if not found:
        return
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    f = QFont(painter.font())
    f.setBold(True)
    f.setPointSizeF(10)
    painter.setFont(f)
    for ln in found:
        hot = ln["id"] == picked
        col = QColor(HOT if hot else INK)
        pa = compat.to_pixel(viewport, ln["a"][0], ln["a"][1], z)
        pb = compat.to_pixel(viewport, ln["b"][0], ln["b"][1], z)
        if not (pa and pb):
            continue
        pen = QPen(col, 2.6 if hot else 1.8)
        pen.setStyle(Qt.DashDotLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(*pa), QPointF(*pb))
        lx, ly = look(ln)
        pen.setStyle(Qt.SolidLine)
        painter.setPen(pen)
        ends = [(ln["a"], pa), (ln["b"], pb)]
        if hot:
            ends.append((flip_foot(ln), None))
        for p, px in ends:
            q = compat.to_pixel(viewport, p[0] + lx * ARROW_M,
                                p[1] + ly * ARROW_M, z)
            o = px or compat.to_pixel(viewport, p[0], p[1], z)
            if not (o and q):
                continue
            painter.drawLine(QPointF(*o), QPointF(*q))
            _head(painter, o, q)
            if px is not None:          # its letter, past the end
                painter.drawText(QRectF(px[0] - 14, px[1] - 24, 28, 18),
                                 int(Qt.AlignCenter), ln["symbol"])
    painter.restore()


def _head(painter, o, q) -> None:
    """An arrow head at ``q`` (from ``o``)."""
    from PySide6.QtCore import QPointF
    dx, dy = q[0] - o[0], q[1] - o[1]
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return
    ux, uy = dx / L, dy / L
    for s in (1, -1):
        painter.drawLine(QPointF(*q), QPointF(q[0] - ux * 8 + uy * 5 * s,
                                              q[1] - uy * 8 - ux * 5 * s))
