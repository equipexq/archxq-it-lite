# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A LEVEL'S REFERENCE, worked on in the view (PLANO_REFERENCIAS_NIVEL.md):

- MEASURE: click two points of something whose length you know (a wall,
  a dimension line), type its real length + Enter — the picture is scaled
  about the first point, and straightened when that line was a little
  askew (a scan, a photo: under 5°). Then click where that first point
  goes (a wall's corner already drawn, the origin…) — or Esc: it stays.
- PLACE: click a point of the picture, then where it goes.
- REMOVE: click a picture — gone (with a PDF's lines).

Each change is one Ctrl+Z. The host's snaps work as in any ArchXQ tool;
on a PDF the ends of its lines pull the cursor too (its corners, its
walls' ends).
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt

from . import compat
from . import refimage as R
from . import refs
from .plottools import GUIDE_CROSS_PX, _m, _PlotTool

MARK = "#2f7df6"          # the picture worked on: its outline


class RefTool(_PlotTool):
    name = "ArchXQ reference"
    icon = "tape"
    vcb_label = "Length"
    noun = "Reference"

    def __init__(self, mode: str, z: float, layer: str, segs_fn,
                 on_done, on_cancelled=None) -> None:
        super().__init__(on_done, on_cancelled)
        self.mode = mode                 # "measure" | "place" | "remove"
        self.z = float(z)
        self.layer = layer               # the level's references' layer
        self.segs_fn = segs_fn           # → the level's drawing (metres)
        self.icon = {"measure": "tape", "place": "move",
                     "remove": "eraser"}.get(mode, "tape")
        self._ends = None                # (cell, {cell: [points]})

    # -- state ------------------------------------------------------------------------
    def _reset(self) -> None:
        self.im = None          # the picture worked on
        self.a = None           # its first point (Measure) / its point (Place)
        self.b = None           # Measure's second point
        self.placing = False    # Measure done: where does A go?
        self.diag = None
        self._sync()

    def _busy(self) -> bool:
        return self.a is not None

    def _anchor(self):
        return self.a

    def _sync(self) -> None:
        pts = [p for p in (self.a, self.b) if p is not None]
        self._sync_protocol(pts, self.hover)
        self.chain_first_point = None

    # -- the pictures -----------------------------------------------------------------
    def _images(self) -> list:
        return refs.images(self.viewport, self.layer) \
            if self.viewport is not None else []

    def _under(self, p):
        """The picture under point ``p`` (the one drawn last first)."""
        for im in reversed(self._images()):
            fu, fv = R.uv_of(refs.frame_of(im), p)
            if -1e-6 <= fu <= 1 + 1e-6 and -1e-6 <= fv <= 1 + 1e-6:
                return im
        return None

    # -- the PDF's ends pull the cursor ---------------------------------------------------
    def _end_grid(self):
        segs = self.segs_fn() or []
        key = (id(segs), len(segs))
        if self._ends is not None and self._ends[0] == key:
            return self._ends[1]
        cell = 0.25
        grid: dict = {}
        for s in segs:
            for q in ((s[0], s[1]), (s[2], s[3])):
                k = (int(math.floor(q[0] / cell)), int(math.floor(q[1] / cell)))
                grid.setdefault(k, []).append(q)
        self._ends = (key, (cell, grid))
        return self._ends[1]

    def _end_pull(self, ctx, p, snap):
        if getattr(snap, "kind", "") not in ("none", "ground", "axis", "",
                                             None):
            return None                      # the host's own snap first
        vp = self.viewport
        cell, grid = self._end_grid()
        if not grid:
            return None
        here = compat.to_pixel(vp, p[0], p[1], self.z)
        if not here:
            return None
        # the reach in metres: GUIDE_CROSS_PX on screen, here
        px1 = compat.to_pixel(vp, p[0] + 1.0, p[1], self.z)
        if not px1:
            return None
        per_m = max(1e-6, math.dist(here, px1))
        reach = GUIDE_CROSS_PX / per_m
        n = int(math.ceil(reach / cell))
        if n > 40:                           # zoomed far out: no pull
            return None
        cx, cy = int(math.floor(p[0] / cell)), int(math.floor(p[1] / cell))
        best = None
        for i in range(cx - n, cx + n + 1):
            for j in range(cy - n, cy + n + 1):
                for q in grid.get((i, j), ()):
                    d = math.hypot(q[0] - p[0], q[1] - p[1])
                    if d <= reach and (best is None or d < best[0]):
                        best = (d, q)
        if best is None:
            return None
        self._guide_hit = "cross"
        return [round(best[1][0], 5), round(best[1][1], 5)]

    def _pick(self, ctx) -> list[float]:
        p = super()._pick(ctx)
        if self._guide_hit or self._ghost_hit or self._aligned:
            return p
        q = self._end_pull(ctx, p, getattr(ctx, "snap", None))
        return q if q is not None else p

    # -- clicks -----------------------------------------------------------------------
    def on_click(self, ctx) -> None:
        p = self._pick(ctx)
        try:
            self._click(p)
        except Exception as e:  # noqa: BLE001 — say it, never lose it
            compat.log_error("RefTool.on_click")
            compat.flash(self.viewport, f"Reference: {type(e).__name__}: "
                         f"{e} (written to the ArchXQ log)", 10000)
            self._reset()
        self.viewport.update()

    def _click(self, p) -> None:
        if self.placing:                    # Measure done: A goes here
            self._place(p)
            return
        if self.a is None:
            im = self._under(p)
            if im is None:
                compat.flash(self.viewport, "Click ON the level's reference "
                             "(its picture)", 4000)
                return
            if self.mode == "remove":
                self._remove(im)
                return
            self.im, self.a = im, p
        elif self.mode == "place":
            self._place(p)
            return
        elif self.b is None:
            if math.hypot(p[0] - self.a[0], p[1] - self.a[1]) < 1e-6:
                return
            self.b = p
        self._sync()
        self._show_hint()

    def on_value(self, viewport, value) -> bool:
        if self.mode != "measure" or self.a is None or self.placing \
                or not isinstance(value, (int, float)):
            return False
        b = self.b or self.hover
        if b is None or float(value) <= 0:
            return False
        got = R.measured(refs.frame_of(self.im), self.a, b, float(value))
        if got is None:
            return False
        frame, k, turn = got
        refs.run(viewport, [refs.frame_cmd(self.im, frame)])
        self.b = None
        self.placing = True
        self._sync()
        self._hint_shown = None
        compat.flash(viewport, f"Measured: ×{k:.4g}"
                     + (f", straightened {abs(turn):.2f}°" if turn else "")
                     + " — now click where that first point goes (Esc: it "
                     "stays) · Ctrl+Z undoes it", 9000)
        viewport.update()
        return True

    def _place(self, to) -> None:
        f = refs.frame_of(self.im)
        refs.run(self.viewport, [refs.frame_cmd(self.im,
                                                R.moved(f, self.a, to))])
        self._reset()
        compat.flash(self.viewport, "Reference placed — Ctrl+Z undoes it",
                     4000)
        if self.on_done:
            self.on_done(None)

    def _remove(self, im) -> None:
        if self.on_done:
            self.on_done(im)             # (the UI takes its lines too)

    def on_cancel(self, viewport) -> None:
        if self.placing:                 # measured, kept where it is
            self._reset()
            viewport.update()
            if self.on_done:
                self.on_done(None)
            return
        super().on_cancel(viewport)

    # -- what is shown ------------------------------------------------------------------
    def _labels(self):
        if self.a is None or self.placing:
            return []
        b = self.b or self.hover
        if b is None:
            return []
        return [((self.a, b), _m(math.hypot(b[0] - self.a[0],
                                            b[1] - self.a[1])), None)]

    def rubber_band_lines(self):
        if self.a is None or self.hover is None:
            return []
        if self.mode == "measure" and not self.placing:
            b = self.b or self.hover
            return [(self._P(self.a), self._P(b))]
        return [(self._P(self.a), self._P(self.hover))]

    def value_label(self):
        if self.mode != "measure" or self.a is None or self.placing:
            return None
        b = self.b or self.hover
        if b is None:
            return None
        return (_m(math.hypot(b[0] - self.a[0], b[1] - self.a[1])), None)

    def draw_overlay(self, viewport, painter) -> None:
        super().draw_overlay(viewport, painter)
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen, QPolygonF
        im = self.im
        if im is None and self.hover is not None:
            im = self._under(self.hover)     # the one a click would take
        if im is None:
            return
        f = refs.frame_of(im)
        pts = [compat.to_pixel(viewport, *R.world_of(f, c)[:2], self.z)
               for c in ((0, 0), (1, 0), (1, 1), (0, 1))]
        if not all(pts):
            return
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        ink = QColor("#d93025" if self.mode == "remove" else MARK)
        painter.setPen(QPen(ink, 2.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawPolygon(QPolygonF([QPointF(*q) for q in pts]))
        for q in (self.a, self.b):
            if q is None:
                continue
            px = compat.to_pixel(viewport, q[0], q[1], self.z)
            if px:
                painter.setPen(Qt.NoPen)
                painter.setBrush(ink)
                painter.drawEllipse(QPointF(*px), 4.0, 4.0)
        painter.restore()

    def status_clause(self) -> str:
        if self.mode == "remove":
            return "Remove a reference: click its picture  ·  Esc = cancel"
        if self.mode == "place":
            return ("Place the reference: click a point of it (a corner, "
                    "a wall's end)" if self.a is None else
                    "…now click where that point goes  ·  Esc = cancel")
        if self.placing:
            return ("Measured — click where the first point goes (a corner "
                    "already drawn, the origin…)  ·  Esc = it stays")
        if self.a is None:
            return ("Measure the reference: click the start of something "
                    "whose length you know (a wall, a dimension)")
        if self.b is None:
            return ("…click its end — or type its REAL length + Enter "
                    "now  ·  Esc = cancel")
        return "…type its REAL length + Enter  ·  Esc = cancel"

