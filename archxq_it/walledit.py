"""Walls › Edit walls › Move points — a straight wall's ENDS with the mouse
(a customer's ask, 2026-10-05: «after a wall is created I can only change
its properties, not where it starts or ends»).

Click a wall's end (the dots), it follows the cursor — the host's snap,
the axes, alignments, X / Y locks, a typed distance + Enter — click where
it goes. Every wall that ends at that same point goes with it, so the
corner stays a corner (the joins are made again by themselves). Esc puts
it back. One Ctrl+Z per move (``on_change(walls)``).

Straight walls only (a curved or round wall: its window).
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt

from . import compat
from . import walls as W
from .plottools import _PlotTool, _v

END_PX = 14             # a click this close to a wall's end picks it
TOL = 1e-3              # ends closer than this are the same corner (m)
DOT = "#22a6c8"         # the ends you can pick
HOT = "#e8742c"         # the one under the cursor / being moved
PREVIEW_INK = "#e8742c"


def _straight(w: dict) -> bool:
    return w.get("kind", "line") == "line" and "a" in w and "b" in w


class WallEditTool(_PlotTool):
    name = "ArchXQ edit walls"
    icon = "move"
    vcb_label = "Distance"
    diagonal = True
    creates = False             # editing: the camera stays free
    noun = "Wall"
    claimed_keys = frozenset({Qt.Key_C, Qt.Key_X, Qt.Key_Y})
    LOCK_KEYS = {Qt.Key_X: "x", Qt.Key_Y: "y"}

    def __init__(self, get_walls, on_change, on_cancelled, z: float) -> None:
        """``get_walls()`` → this level's walls (live); ``on_change(walls)``
        → the level's walls after a move."""
        self.get_walls = get_walls
        self.on_change = on_change
        self.z = z
        self.moving = None
        super().__init__(lambda _c: None, on_cancelled)

    # -- state -----------------------------------------------------------------
    def _reset(self) -> None:
        self.moving = None           # the corner's point while it moves
        self.origin = None
        self.members = []            # [(wall index, "a" | "b")] at that corner
        self.pending = None          # the level's walls while it moves
        self.hot = None              # an end under the cursor
        self.mouse = None
        self.lock = None
        self.diag = None
        self._sync()

    def _busy(self) -> bool:
        return self.moving is not None

    def _walls(self) -> list[dict]:
        return self.pending if self.pending is not None else \
            [dict(w) for w in self.get_walls()]

    def _ends(self) -> list[list[float]]:
        """Every straight wall's ends, each corner once."""
        out = []
        for w in self._walls():
            if not _straight(w):
                continue
            for p in (w["a"], w["b"]):
                if all(math.dist(p, q) > TOL for q in out):
                    out.append(list(p))
        return out

    def _anchor(self):
        return self.origin

    def _align_sources(self):
        return [q for q in self._ends()
                if self.origin is None or math.dist(q, self.origin) > TOL]

    def _sync(self) -> None:
        self._sync_protocol([self.origin] if self.origin else [], self.hover)

    def _locked(self, p):
        if self.lock == "x":
            return [p[0], self.origin[1]]
        if self.lock == "y":
            return [self.origin[0], p[1]]
        return p

    # -- picking -----------------------------------------------------------------
    def _find(self) -> None:
        self.hot = None
        if self.mouse is None or self.moving is not None:
            return
        best = None
        for q in self._ends():
            px = compat.to_pixel(self.viewport, q[0], q[1], self.z)
            if px:
                d = math.dist(px, self.mouse)
                if d <= END_PX and (best is None or d < best[0]):
                    best = (d, q)
        self.hot = best[1] if best else None

    # -- host protocol -------------------------------------------------------------
    def on_hover(self, ctx) -> None:
        self.mouse = (ctx.screen.x(), ctx.screen.y())
        if self.moving is not None:
            self.hover = self._locked(self._pick(ctx))
            self._drag(self.hover)
        else:
            self.hover = [round(ctx.world.x(), 4), round(ctx.world.y(), 4)]
        self._find()
        self._sync()
        self._show_hint()
        self.viewport.update()

    def _drag(self, p) -> None:
        walls = [dict(w) for w in self.pending]
        for i, end in self.members:
            walls[i][end] = [round(p[0], 4), round(p[1], 4)]
        self.pending = walls
        self.moving = list(p)

    def on_click(self, ctx) -> None:
        self.mouse = (ctx.screen.x(), ctx.screen.y())
        if self.moving is not None:
            self._place(self._locked(self._pick(ctx)))
            return
        self._find()
        if self.hot is None:
            compat.flash(self.viewport, "Click a wall's end — the dots", 3000)
            return
        walls = [dict(w) for w in self.get_walls()]
        self.members = [(i, end) for i, w in enumerate(walls) if _straight(w)
                        for end in ("a", "b")
                        if math.dist(w[end], self.hot) <= TOL]
        self.origin = list(self.hot)
        self.moving = list(self.hot)
        self.pending = walls
        self.lock = None
        self.hover = list(self.hot)
        self.hot = None
        self._sync()
        self._show_hint()
        self.viewport.update()

    def _place(self, p) -> None:
        self._drag(p)
        walls = self.pending
        for i, _end in self.members:
            w = walls[i]
            if math.dist(w["a"], w["b"]) < 0.05:
                compat.flash(self.viewport, "A wall would shrink to nothing — "
                             "pick another place", 4000)
                return
            why = W.why_not(w)
            if why:
                compat.flash(self.viewport, f"«{w.get('name', 'Wall')}»: {why} "
                             "— pick another place", 4000)
                return
        n = len(self.members)
        self._reset()
        self.on_change(walls)
        compat.flash(self.viewport, ("Wall end moved" if n == 1 else
                                     f"Corner moved — {n} walls followed")
                     + " · Ctrl+Z puts it back", 4000)
        self._show_hint()

    def on_value(self, viewport, value) -> bool:
        """A typed distance: the end goes that far, toward the cursor."""
        if self.moving is None or not isinstance(value, (int, float)) \
                or self.hover is None:
            return False
        o = self.origin
        dx, dy = self.hover[0] - o[0], self.hover[1] - o[1]
        d = math.hypot(dx, dy)
        if d < 1e-9:
            return False
        L = float(value)
        self._place([o[0] + dx / d * L, o[1] + dy / d * L])
        return True

    def on_key(self, viewport, key, modifiers) -> bool:
        lock = self.LOCK_KEYS.get(key)
        if lock and self.moving is not None and not compat.typed_value(viewport):
            self.lock = None if self.lock == lock else lock
            self._show_hint()
            viewport.update()
            return True
        return super().on_key(viewport, key, modifiers)

    def on_cancel(self, viewport) -> None:
        if self.moving is not None:
            self._reset()                    # put it back
            self._show_hint()
            viewport.update()
            return
        if self.on_cancelled:
            self.on_cancelled()

    def status_clause(self) -> str:
        if self.moving is None:
            return "Edit walls: click a wall's end (the dots)  ·  Esc = done"
        lock = {"x": "  ·  locked to X", "y": "  ·  locked to Y"}.get(self.lock, "")
        return ("Click where it goes, or type a distance + Enter  ·  X / Y = "
                "lock an axis  ·  Esc = put it back" + lock)

    def value_label(self):
        if self.moving is None or self.hover is None:
            return None
        return (f"{math.dist(self.origin, self.hover):.2f} m", None)

    def rubber_band_lines(self):
        if self.moving is None:
            return []
        return [(_v(self.origin), _v(self.moving))]

    # -- drawn over the view -------------------------------------------------------
    def draw_overlay(self, viewport, painter) -> None:
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        try:
            if self.moving is not None and self.pending is not None:
                ids = {self.pending[i].get("id") for i, _e in self.members}
                res = W.plan(self.pending)
                painter.setPen(QPen(QColor(PREVIEW_INK), 2.0))
                for w in self.pending:
                    if w.get("id") not in ids:
                        continue
                    for pc in res.get(w["id"], ()):
                        for loop in [pc["outer"]] + list(pc["holes"]):
                            px = [compat.to_pixel(viewport, x, y, self.z)
                                  for x, y in loop]
                            for a, b in zip(px, px[1:] + px[:1]):
                                if a and b:
                                    painter.drawLine(QPointF(*a), QPointF(*b))
            for q in self._ends():
                px = compat.to_pixel(viewport, q[0], q[1], self.z)
                if not px:
                    continue
                hot = self.hot is not None and math.dist(q, self.hot) <= TOL
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(HOT if hot else DOT))
                painter.drawEllipse(QPointF(*px), 6.5 if hot else 4.5,
                                    6.5 if hot else 4.5)
        except Exception:  # noqa: BLE001 — never break the host's paint
            pass
        painter.restore()
        super().draw_overlay(viewport, painter)
