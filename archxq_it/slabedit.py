"""Structure › Edit slabs — a drawn slab's outline with the mouse (his ask,
2026-10-12, before recording: the floors' corners and SIDES, as the plot's
and the walls' are edited).

The excavations' tool (``plotedit.DigEditTool``) over the current level's
drawn slabs — Move points / Add point / Delete point, the one under the
cursor taken — and one more mode, «Move side»: click a side, it moves
PARALLEL to itself (its two corners together) as the cursor goes, the
host's snap and alignments helping; click where it goes, or type a
distance + Enter. Esc puts it back. One Ctrl+Z per change.

An excavation's slab follows its excavation: not edited here.
"""
from __future__ import annotations

import math

from . import compat
from .plotedit import DigEditTool

#: the left strip's methods → the tool's mode
SLAB_EDIT = {"Move points": "move", "Move side": "side",
             "Add point": "add", "Delete point": "delete"}


class SlabEditTool(DigEditTool):
    name = "ArchXQ edit slab"

    def __init__(self, mode: str, get_slabs, on_change, on_cancelled,
                 check) -> None:
        self.side_mode = mode == "side"
        self.side = None          # (k, grab point, normal, corners as taken)
        self.dside = 0.0
        # «Move side» finds a side as «Add point» does
        super().__init__("add" if self.side_mode else mode, get_slabs,
                         on_change, on_cancelled, 0.0, check)
        if self.side_mode:
            self.icon = "move"

    def _reset(self) -> None:
        self.side = None
        self.dside = 0.0
        super()._reset()

    # -- «Move side» ---------------------------------------------------------------
    def _side_pts(self, d: float):
        k, _o, n, pts0 = self.side
        pts = [list(q) for q in pts0]
        m = len(pts)
        for i in (k, (k + 1) % m):
            pts[i] = [round(pts[i][0] + n[0] * d, 4),
                      round(pts[i][1] + n[1] * d, 4)]
        return pts

    def _side_place(self, d: float) -> None:
        pts = self._side_pts(d)
        why = self.check(pts)
        if why:
            compat.flash(self.viewport, f"{why} — pick another place", 4000)
            return
        _p, hs, cl, br = self.pending
        self._reset()
        self.on_change(pts, hs, cl, br)
        self._show_hint()

    def on_hover(self, ctx) -> None:
        if not (self.side_mode and self.side is not None):
            super().on_hover(ctx)
            return
        self.mouse = (ctx.screen.x(), ctx.screen.y())
        p = self._pick(ctx)
        self.hover = p
        _k, o, n, _pts0 = self.side
        self.dside = (p[0] - o[0]) * n[0] + (p[1] - o[1]) * n[1]
        _p, hs, cl, br = self.pending
        self.pending = (self._side_pts(self.dside), hs, cl, br)
        self._show_hint()
        self.viewport.update()

    def on_click(self, ctx) -> None:
        if not self.side_mode:
            super().on_click(ctx)
            return
        self.mouse = (ctx.screen.x(), ctx.screen.y())
        if self.side is not None:
            self.on_hover(ctx)
            self._side_place(self.dside)
            return
        self.hover = [round(ctx.world.x(), 4), round(ctx.world.y(), 4)]
        self._find()
        st = self._state()
        if st is None or self.hot_side is None:
            return
        k, p = self.hot_side
        pts = [list(q) for q in st[0]]
        a, b = pts[k], pts[(k + 1) % len(pts)]
        L = math.dist(a, b) or 1.0
        n = (-(b[1] - a[1]) / L, (b[0] - a[0]) / L)
        self.side = (k, list(p), n, pts)
        self.origin = list(p)
        self.pending = tuple(st)
        self.hot_side = None
        self._show_hint()
        self.viewport.update()

    def on_value(self, viewport, value) -> bool:
        if self.side_mode and self.side is not None \
                and isinstance(value, (int, float)):
            sign = -1.0 if self.dside < 0 else 1.0
            self._side_place(sign * abs(float(value)))
            return True
        return super().on_value(viewport, value)

    def on_cancel(self, viewport) -> None:
        if self.side is not None:
            self._reset()
            self._show_hint()
            viewport.update()
            return
        super().on_cancel(viewport)

    def value_label(self):
        if self.side is not None:
            return (compat.fmt_len(abs(self.dside)), None)
        return super().value_label()

    def rubber_band_lines(self):
        return [] if self.side is not None else super().rubber_band_lines()

    def status_clause(self) -> str:
        if self.side_mode:
            if self.side is not None:
                return ("Move side: click where it goes, or type a distance "
                        "+ Enter  ·  Esc = put it back")
            return "Move side: click a slab's side  ·  Esc = finish"
        return super().status_clause().replace("Edit plot", "Edit slab")
