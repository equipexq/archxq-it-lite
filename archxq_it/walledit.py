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

from . import compat, paintlog
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
        return (compat.fmt_len(math.dist(self.origin, self.hover)), None)

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
            paintlog.failed()
        painter.restore()
        super().draw_overlay(viewport, painter)


# ---- Align, as Revit's (0.15.0, B1/B2 — align.py) -------------------------------------
EDGE_PX = 10            # a click this close to an edge picks it


class AlignTool(_PlotTool):
    """Click a REFERENCE edge (a wall's face, a column's side, a beam's or
    a slab's edge), then the EDGE of the element to line up: it moves
    across, square to the reference, onto its line. ``only``: the ids it
    may move (the radial menu's selection); empty = any."""
    name = "ArchXQ align"
    icon = "align"
    vcb_label = "Distance"
    creates = False
    noun = "Element"

    def __init__(self, get_doc, level_id, on_change, on_cancelled, z: float,
                 only=()) -> None:
        self.get_doc = get_doc
        self.level_id = level_id
        self.on_change = on_change
        self.z = z
        self.only = set(only or ())
        super().__init__(lambda _c: None, on_cancelled)

    def _reset(self) -> None:
        self.ref = None               # the reference edge (p, q, kind, id)
        self.hot = None               # the edge under the cursor
        self.hover = None
        self._edges = None
        self._sync()

    def _busy(self) -> bool:
        return self.ref is not None

    def _sync(self) -> None:
        self._sync_protocol([], self.hover)

    def _all_edges(self):
        if self._edges is None:
            from . import align as AL
            try:
                self._edges = AL.edges(self.get_doc(), self.level_id)
            except Exception:  # noqa: BLE001 — none to pick
                self._edges = []
        return self._edges

    def _find(self, mouse):
        """The edge nearest the pointer (px), within EDGE_PX — in step 2
        only the movable ones (another element than the reference's)."""
        from . import align as AL
        best = None
        for e in self._all_edges():
            if self.ref is not None:
                if e[3] == self.ref[3]:
                    continue
                if self.only and e[3] not in self.only:
                    continue
            a = compat.to_pixel(self.viewport, e[0][0], e[0][1], self.z)
            b = compat.to_pixel(self.viewport, e[1][0], e[1][1], self.z)
            if not a or not b:
                continue
            d = AL.seg_dist(mouse, a, b)
            if d <= EDGE_PX and (best is None or d < best[0]):
                best = (d, e)
        return best[1] if best else None

    def on_hover(self, ctx) -> None:
        self.hover = [round(ctx.world.x(), 4), round(ctx.world.y(), 4)]
        self.hot = self._find((ctx.screen.x(), ctx.screen.y()))
        self._sync()
        self._show_hint()
        self.viewport.update()

    def on_click(self, ctx) -> None:
        from . import align as AL
        self.on_hover(ctx)
        if self.hot is None:
            compat.flash(self.viewport, "Click ON an edge — a wall's face, a "
                         "column's side, a beam's or a slab's edge", 3500)
            return
        if self.ref is None:
            self.ref = self.hot
            self.hot = None
            self._show_hint()
            self.viewport.update()
            return
        d = AL.shift(self.ref, self.hot)
        if isinstance(d, str):
            compat.flash(self.viewport, d, 4000)
            return
        if math.hypot(*d) < 1e-5:
            compat.flash(self.viewport, "Already lined up", 3000)
            return
        kind, eid = self.hot[2], self.hot[3]
        doc = AL.moved(self.get_doc(), kind, eid, d)
        self._edges = None           # (they move with it)
        self.hot = None
        self.on_change(doc, kind, eid)
        compat.flash(self.viewport, f"Lined up — moved {compat.fmt_len(math.hypot(*d))}"
                     " · Ctrl+Z puts it back · the next edge to the same "
                     "reference, or Esc", 5000)

    def on_cancel(self, viewport) -> None:
        if self.ref is not None:
            self._reset()
            self._show_hint()
            viewport.update()
            return
        if self.on_cancelled:
            self.on_cancelled()

    def status_clause(self) -> str:
        if self.ref is None:
            return ("Align: click the REFERENCE — an edge to line up with  ·  "
                    "Esc = done")
        return ("Now click the edge of the element to line up (it moves onto "
                "the reference)  ·  Esc = another reference")

    def value_label(self):
        from . import align as AL
        if self.ref is None or self.hot is None:
            return None
        d = AL.shift(self.ref, self.hot)
        return None if isinstance(d, str) else (
            compat.fmt_len(math.hypot(*d)), None)

    def draw_overlay(self, viewport, painter) -> None:
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen
        from . import align as AL
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)

        def line(p, q, color, w, dash=False):
            a = compat.to_pixel(viewport, p[0], p[1], self.z)
            b = compat.to_pixel(viewport, q[0], q[1], self.z)
            if a and b:
                pen = QPen(QColor(color), w)
                if dash:
                    pen.setStyle(Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(QPointF(*a), QPointF(*b))
        try:
            if self.ref is not None:
                p, q = self.ref[0], self.ref[1]
                ux, uy = q[0] - p[0], q[1] - p[1]
                # the reference's line, drawn on past its ends
                line((p[0] - ux * 2, p[1] - uy * 2), (q[0] + ux * 2,
                                                      q[1] + uy * 2),
                     HOT, 1.4, dash=True)
                line(p, q, HOT, 3.0)
            if self.hot is not None:
                line(self.hot[0], self.hot[1], DOT, 3.0)
                if self.ref is not None:
                    d = AL.shift(self.ref, self.hot)
                    if not isinstance(d, str):
                        (a, b) = self.hot[0], self.hot[1]
                        line((a[0] + d[0], a[1] + d[1]),
                             (b[0] + d[0], b[1] + d[1]), HOT, 2.0, dash=True)
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()
        painter.restore()
        super().draw_overlay(viewport, painter)


# ---- Split / Trim / Extend (0.15.0, B1 — wallops.py) ---------------------------------
def _outline(painter, viewport, walls, wid, z, color, width=2.4) -> None:
    """A wall's plan (joined), drawn over the view."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QPen
    painter.setPen(QPen(QColor(color), width))
    for pc in W.plan(walls).get(wid, ()):
        for loop in [pc["outer"]] + list(pc["holes"]):
            px = [compat.to_pixel(viewport, x, y, z) for x, y in loop]
            for a, b in zip(px, px[1:] + px[:1]):
                if a and b:
                    painter.drawLine(QPointF(*a), QPointF(*b))


class WallSplitTool(_PlotTool):
    """Walls › Edit walls › Split: a click on a straight wall cuts it in
    two there (its doors and windows go with their half)."""
    name = "ArchXQ split walls"
    icon = "wall_split"
    vcb_label = "Distance"
    creates = False
    noun = "Wall"

    def __init__(self, get_parts, on_change, on_cancelled, z: float) -> None:
        """``get_parts()`` → (this level's walls, the openings);
        ``on_change(walls, openings)`` → stored, one Ctrl+Z."""
        self.get_parts = get_parts
        self.on_change = on_change
        self.z = z
        super().__init__(lambda _c: None, on_cancelled)

    def _reset(self) -> None:
        self.hot = None               # (wall, distance along)
        self.hover = None
        self._sync()

    def _busy(self) -> bool:
        return False

    def _sync(self) -> None:
        self._sync_protocol([], self.hover)

    def on_hover(self, ctx) -> None:
        from . import wallops as WO
        self.hover = [round(ctx.world.x(), 4), round(ctx.world.y(), 4)]
        walls, _o = self.get_parts()
        self.hot = WO.nearest_wall(walls, self.hover, 0.05)
        self._sync()
        self._show_hint()
        self.viewport.update()

    def on_click(self, ctx) -> None:
        from . import wallops as WO
        self.on_hover(ctx)
        if self.hot is None:
            compat.flash(self.viewport, "Click ON a straight wall — where it "
                         "is cut in two", 3000)
            return
        walls, ops = self.get_parts()
        w, s = self.hot
        got = WO.split(walls, ops, w["id"], s)
        if isinstance(got, str):
            compat.flash(self.viewport, got, 4000)
            return
        self.hot = None
        self.on_change(*got)
        compat.flash(self.viewport, f"«{w['name']}» split in two · Ctrl+Z "
                     "puts it back", 4000)

    def on_value(self, viewport, value) -> bool:
        """A typed distance: the cut that far from the wall's start."""
        from . import wallops as WO
        if self.hot is None or not isinstance(value, (int, float)):
            return False
        w, _s = self.hot
        walls, ops = self.get_parts()
        got = WO.split(walls, ops, w["id"], float(value))
        if isinstance(got, str):
            compat.flash(viewport, got, 4000)
            return True
        self.hot = None
        self.on_change(*got)
        return True

    def status_clause(self) -> str:
        return ("Split: click on a wall where it is cut in two (or point at "
                "it and type the distance from its start + Enter)  ·  Esc = "
                "done")

    def value_label(self):
        if self.hot is None:
            return None
        return (compat.fmt_len(self.hot[1]), None)

    def draw_overlay(self, viewport, painter) -> None:
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        try:
            if self.hot is not None:
                w, s = self.hot
                walls, _o = self.get_parts()
                _outline(painter, viewport, walls, w["id"], self.z, DOT)
                a, b = w["a"], w["b"]
                L = max(math.dist(a, b), 1e-9)
                ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
                h = float(w["t"]) * 0.9 + 0.1
                c = W.centre(w).at(s / L)
                p1 = compat.to_pixel(viewport, c[0] - uy * h, c[1] + ux * h,
                                     self.z)
                p2 = compat.to_pixel(viewport, c[0] + uy * h, c[1] - ux * h,
                                     self.z)
                if p1 and p2:
                    painter.setPen(QPen(QColor(HOT), 3.0))
                    painter.drawLine(QPointF(*p1), QPointF(*p2))
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()
        painter.restore()
        super().draw_overlay(viewport, painter)


class WallTrimTool(_PlotTool):
    """Walls › Edit walls › Trim / Extend: click a wall near the END that
    goes, then the wall it goes to — the end lands on that wall's line
    (shortened or lengthened); the joins are made again."""
    name = "ArchXQ trim / extend walls"
    icon = "wall_trim"
    vcb_label = "Distance"
    creates = False
    noun = "Wall"

    def __init__(self, get_walls, on_change, on_cancelled, z: float) -> None:
        self.get_walls = get_walls
        self.on_change = on_change
        self.z = z
        super().__init__(lambda _c: None, on_cancelled)

    def _reset(self) -> None:
        self.first = None             # (wall id, end) — the end that goes
        self.hot = None               # the wall under the cursor
        self.preview = None           # the walls with it gone there
        self.hover = None
        self._sync()

    def _busy(self) -> bool:
        return self.first is not None

    def _sync(self) -> None:
        self._sync_protocol([], self.hover)

    def on_hover(self, ctx) -> None:
        from . import wallops as WO
        self.hover = [round(ctx.world.x(), 4), round(ctx.world.y(), 4)]
        walls = [dict(w) for w in self.get_walls()]
        got = WO.nearest_wall(walls, self.hover, 0.05)
        self.hot = got[0] if got else None
        self.preview = None
        if self.first is not None and self.hot is not None:
            res = WO.trim_extend(walls, self.first[0], self.first[1],
                                 self.hot["id"])
            self.preview = res if isinstance(res, list) else None
        self._sync()
        self._show_hint()
        self.viewport.update()

    def on_click(self, ctx) -> None:
        from . import wallops as WO
        self.on_hover(ctx)
        walls = [dict(w) for w in self.get_walls()]
        if self.hot is None:
            compat.flash(self.viewport, "Click ON a straight wall", 3000)
            return
        if self.first is None:
            L = math.dist(self.hot["a"], self.hot["b"])
            s = WO.along(self.hot, self.hover)
            self.first = (self.hot["id"], "a" if s < L / 2 else "b")
            self._show_hint()
            self.viewport.update()
            return
        res = WO.trim_extend(walls, self.first[0], self.first[1],
                             self.hot["id"])
        if isinstance(res, str):
            compat.flash(self.viewport, res, 4000)
            return
        name = next((w["name"] for w in walls if w["id"] == self.first[0]),
                    "Wall")
        self._reset()
        self.on_change(res)
        compat.flash(self.viewport, f"«{name}» reaches the wall · Ctrl+Z puts "
                     "it back", 4000)

    def on_cancel(self, viewport) -> None:
        if self.first is not None:
            self._reset()
            self._show_hint()
            viewport.update()
            return
        if self.on_cancelled:
            self.on_cancelled()

    def status_clause(self) -> str:
        if self.first is None:
            return ("Trim / Extend: click the wall to change, near the END "
                    "that goes  ·  Esc = done")
        return ("Now click the wall it goes to (its end lands on that wall's "
                "line)  ·  Esc = another one")

    def draw_overlay(self, viewport, painter) -> None:
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        try:
            walls = [dict(w) for w in self.get_walls()]
            if self.first is not None:
                w = next((x for x in walls if x["id"] == self.first[0]), None)
                if w is not None:
                    _outline(painter, viewport, self.preview or walls,
                             w["id"], self.z, HOT)
                    q = w[self.first[1]]
                    px = compat.to_pixel(viewport, q[0], q[1], self.z)
                    if px:
                        painter.setPen(Qt.NoPen)
                        painter.setBrush(QColor(HOT))
                        painter.drawEllipse(QPointF(*px), 6.5, 6.5)
            if self.hot is not None and (self.first is None
                                         or self.hot["id"] != self.first[0]):
                _outline(painter, viewport, walls, self.hot["id"], self.z,
                         DOT)
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()
        painter.restore()
        super().draw_overlay(viewport, painter)
