"""Placing OPENINGS — doors, windows, voids — in the walls.

OpeningTool: the cursor near a straight wall of the level takes the
opening onto it (its width from the options bar, centred where the cursor
is, kept clear of the wall's ends); a click places it — or says why it
can't (another opening there, too tall…). Tab turns a door's hinge to the
other side. The preview — and the plan, afterwards — draw the opening as
a plan does: its jambs, a window's glass, a door's leaf and its swing.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt

from . import compat, structure as S, walls as W
from .plottools import _PlotTool

REACH = 0.40          # m from a wall's face the cursor still finds it
INK = "#e8742c"       # the preview
PLAN_INK = "#2b3138"  # openings drawn in the plan


def find_wall(p, walls: list[dict]):
    """(wall, centre seg, distance along it) of the straight wall nearest
    the point, or None."""
    best = None
    for w in walls:
        if w.get("kind", "line") != "line" or W.why_not(w) is not None:
            continue
        s = W.centre(w)
        f, off = s.project(p)
        if not 0.0 <= f <= 1.0:
            continue
        gap = abs(off) - float(w["t"]) / 2
        if gap > REACH:
            continue
        if best is None or gap < best[0]:
            best = (gap, w, s, f * s.L)
    return best[1:] if best else None


def symbol_lines(o: dict, wall: dict, seg) -> list:
    """The opening in plan, as lines [((x, y), (x, y))…]: jambs across
    the wall; a window's glass along it; a door's leaf, open 90° to the
    inside, and its swing."""
    p0, u = seg.p0, seg.u
    n = (-u[1], u[0])
    t = float(wall["t"]) / 2
    s0, s1 = o["pos"] - o["w"] / 2, o["pos"] + o["w"] / 2

    def P(s, c):
        return (p0[0] + u[0] * s + n[0] * c, p0[1] + u[1] * s + n[1] * c)
    lines = [(P(s0, -t), P(s0, t)), (P(s1, -t), P(s1, t))]
    if o["kind"] == "window":
        for c in (-t / 3, t / 3):
            lines.append((P(s0, c), P(s1, c)))
    elif o["kind"] == "door":
        inside = 1.0 if float(wall.get("side", 1)) >= 0 else -1.0
        hinge = s0 if o.get("swing", "left") == "left" else s1
        away = 1.0 if hinge == s0 else -1.0
        h = P(hinge, inside * t)
        r = o["w"]
        tip = (h[0] + n[0] * inside * r, h[1] + n[1] * inside * r)
        lines.append((h, tip))                         # the leaf, open
        a0 = math.atan2(n[1] * inside, n[0] * inside)
        a1 = math.atan2(u[1] * away, u[0] * away)
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        pts = [(h[0] + r * math.cos(a0 + da * k / 12),
                h[1] + r * math.sin(a0 + da * k / 12)) for k in range(13)]
        lines += list(zip(pts, pts[1:]))               # the swing
    return lines


def draw_lines(viewport, painter, lines, z, ink, width=1.6) -> None:
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QPen
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(ink), width))
    for a, b in lines:
        pa = compat.to_pixel(viewport, a[0], a[1], z)
        pb = compat.to_pixel(viewport, b[0], b[1], z)
        if pa and pb:
            painter.drawLine(QPointF(pa[0], pa[1]), QPointF(pb[0], pb[1]))
    painter.restore()


class OpeningTool(_PlotTool):
    name = "ArchXQ opening"
    noun = "Opening"
    icon = "rectangle"
    vcb_label = ""
    claimed_keys = frozenset({Qt.Key_Tab})

    def __init__(self, kind, on_done, on_cancelled, z, opts, walls,
                 openings, wall_height):
        """``opts()`` → the options bar's sizes; ``walls()`` / ``openings()``
        → this level's; ``wall_height(wall)`` → how high it stands."""
        super().__init__(on_done, on_cancelled)
        self.kind = kind
        self.axq_element = kind
        self.noun = S.OPENING_LABEL[kind]
        self.z = z
        self.opts = opts
        self.walls = walls
        self.openings = openings
        self.wall_height = wall_height
        self.here = None                 # (wall, seg, record) under cursor

    def _reset(self) -> None:
        self.diag = None
        self.here = None
        self._sync()

    def _busy(self) -> bool:
        return False

    def _sync(self) -> None:
        self._sync_protocol([], self.hover)

    def record(self, p):
        """The opening the cursor at ``p`` would place, on its wall."""
        got = find_wall(p, self.walls())
        if got is None:
            return None
        wall, seg, pos = got
        o = dict(self.opts())
        half = o["w"] / 2 + S.END_GAP
        pos = min(max(pos, half), seg.L - half) if seg.L > 2 * half \
            else seg.L / 2
        rec = {"kind": self.kind, "wall": wall["id"],
               "pos": round(pos, 4), "w": o["w"], "h": o["h"],
               "sill": 0.0 if self.kind == "door" else o.get("sill", 0.0),
               "swing": o.get("swing", "left")}
        return wall, seg, rec

    def on_hover(self, ctx) -> None:
        super().on_hover(ctx)
        self.here = self.record(self.hover) if self.hover else None

    def on_click(self, ctx) -> None:
        p = self._pick(ctx)
        got = self.record(p)
        if got is None:
            compat.flash(self.viewport, f"{self.noun}: click ON a straight "
                         "wall of this level", 4000)
            return
        wall, _seg, rec = got
        why = S.opening_room(rec, wall, self.openings(),
                             self.wall_height(wall))
        if why:
            compat.flash(self.viewport, f"{why} — try another place", 5000)
            return
        self.viewport.update()
        self.on_done(rec)               # the tool stays for the next

    def on_key(self, viewport, key, modifiers) -> bool:
        if key == Qt.Key_Tab and self.kind == "door":
            o = self.opts()
            o["swing"] = "right" if o.get("swing") == "left" else "left"
            if self.hover:
                self.here = self.record(self.hover)
            viewport.update()
            return True
        return super().on_key(viewport, key, modifiers)

    def rubber_band_lines(self):
        return []

    def value_label(self):
        if self.here is None:
            return None
        o = self.here[2]
        return (f"{o['w']:.2f} × {o['h']:.2f} m", None)

    def status_clause(self) -> str:
        tail = "  ·  Tab = hinge on the other side" if self.kind == "door" \
            else ""
        return (f"{self.noun}: move along a wall and click where it goes"
                f"{tail}  ·  Esc = done")

    def draw_overlay(self, viewport, painter) -> None:
        if self.here is not None:
            wall, seg, rec = self.here
            try:
                ok = S.opening_room(rec, wall, self.openings(),
                                    self.wall_height(wall)) is None
                draw_lines(viewport, painter, symbol_lines(rec, wall, seg),
                           self.z, INK if ok else "#d23c3c", 2.2)
            except Exception:  # noqa: BLE001 — a preview never breaks paint
                pass
        super().draw_overlay(viewport, painter)
