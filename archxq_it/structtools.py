"""Drawing the STRUCTURE in the 3D view — on the current level's floor.

The same habits as the walls: the options bar holds the choices (section,
sizes, how many), the tool shows the result LIVE (outlines, lines only),
hands ``on_done(records)`` and stays out for the next.

- ColumnTool: «single» (click = a column), «row» (start, end: the
  options bar's count, evenly, ends included — or a typed length), «grid»
  (two opposite corners: columns × rows, edges included — or «w;d»).
- BeamTool: point by point, like a run of walls — the walls engine joins
  the beams (L, T, X); width from the options bar.
- slab_tool(base): the plot's outline tools (rectangle, from the centre,
  rotated, point by point) finishing as a slab outline.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt

from . import compat, plottools, structure as S, walls as W
from .plottools import _PlotTool, _m
from .walltools import WallChainTool

INK = "#2f7df6"            # structure previews: blue (walls are orange)


def _draw_loops(viewport, painter, loops, z, fill: bool = False) -> None:
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QPen, QPolygonF
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(INK), 2.0))
    tint = QColor(INK)
    tint.setAlpha(70)
    for loop in loops:
        px = [compat.to_pixel(viewport, x, y, z) for x, y in loop]
        if fill and all(px):           # the column on the cursor: seen
            painter.setBrush(tint)
            painter.drawPolygon(QPolygonF([QPointF(*p) for p in px]))
            continue
        for a, b in zip(px, px[1:] + px[:1]):
            if a and b:
                painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
    painter.restore()


def row_stations(length: float, o: dict) -> list[float]:
    """Where a row's columns stand, as fractions of its line: by COUNT
    (evenly) or by SPACING (from the first point), with the clicked ends
    in or out (``ends``: both | first | last | none)."""
    ends = o.get("ends", "both")
    first, last = ends in ("both", "first"), ends in ("both", "last")
    if length < 1e-9:
        return [0.0]
    if o.get("by", "count") == "spacing":
        s = max(0.05, float(o.get("spacing", 5.0)))
        k = int(math.floor(length / s + 1e-6))
        ts = [i * s / length for i in range(k + 1)]
        if ts and abs(ts[-1] - 1.0) < 1e-6:
            ts[-1] = 1.0
        if not first:
            ts = [t for t in ts if t > 1e-9]
        if last and (not ts or ts[-1] < 1.0 - 1e-6):
            ts.append(1.0)
        if not last:
            ts = [t for t in ts if t < 1.0 - 1e-9]
        return ts
    n = max(1, int(o.get("count", 4)))
    slots = n - 1 + (0 if first else 1) + (0 if last else 1)
    if slots <= 0:
        return [0.0 if first else 1.0]
    start = 0 if first else 1
    return [(start + k) / slots for k in range(n)]


class ColumnDrawTool(plottools.PlotRectTool):
    """DRAW a column: two opposite corners — its size and its place."""
    name = "ArchXQ column"
    axq_element = "column"
    noun = "Column"
    face_x: list = []
    face_y: list = []

    def __init__(self, on_done, on_cancelled, z: float) -> None:
        super().__init__(on_done, on_cancelled)
        self.z = z

    guides: list = []

    def _pick(self, ctx) -> list[float]:
        p = super()._pick(ctx)
        self.guides = []
        if getattr(self, "_aligned", None) or self._guide_hit:
            return p
        dx, dy, self.guides = face_pull(self.viewport, self.z, p, [p[0]],
                                        [p[1]], self.face_x, self.face_y)
        return [round(p[0] + dx, 4), round(p[1] + dy, 4)]

    def draw_overlay(self, viewport, painter) -> None:
        super().draw_overlay(viewport, painter)
        draw_guides(viewport, painter, self.guides, self.hover, self.z)


FACE_PX = 10           # how near (on screen) a face is pulled flush


def _foot(p, a, b, margin: float = 0.0):
    """The foot of ``p`` on the segment a-b (None: beyond its ends by more
    than ``margin`` m — a foot just past an end is pulled back onto it)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return None
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2
    m = margin / math.sqrt(L2)
    if t < -m or t > 1.0 + m:
        return None
    t = min(max(t, 0.0), 1.0)
    return [a[0] + dx * t, a[1] + dy * t]


def face_pull(viewport, z, p, ex, ey, fx, fy):
    """(dx, dy, guides): the shift that lays one of the edges at x ``ex``
    (y ``ey``) flush with a line at x ``fx`` (y ``fy``), when one is
    within FACE_PX on screen — the nearest; guides = [("x"|"y", value)]."""
    if viewport is None or (not fx and not fy):
        return 0.0, 0.0, []
    a = compat.to_pixel(viewport, p[0], p[1], z)
    b = compat.to_pixel(viewport, p[0] + 1.0, p[1], z)
    if not a or not b:
        return 0.0, 0.0, []
    tol = FACE_PX / max(math.dist(a, b), 1e-6)       # in metres
    out, guides = [0.0, 0.0], []
    for k, (edges, lines) in enumerate(((ex, fx), (ey, fy))):
        best = None
        for e in edges:
            for v in lines:
                d = v - e
                if abs(d) <= tol and (best is None or abs(d) < abs(best[0])):
                    best = (d, v)
        if best is not None:
            out[k] = best[0]
            guides.append(("x" if k == 0 else "y", best[1]))
    return out[0], out[1], guides


def draw_guides(viewport, painter, guides, at, z) -> None:
    """The face lines a column was pulled flush with: dashed, along it."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QPen
    if not guides or at is None:
        return
    painter.save()
    painter.setPen(QPen(QColor("#e8742c"), 1.4, Qt.DashLine))
    for axis, v in guides:
        if axis == "x":
            p0 = compat.to_pixel(viewport, v, at[1] - 6.0, z)
            p1 = compat.to_pixel(viewport, v, at[1] + 6.0, z)
        else:
            p0 = compat.to_pixel(viewport, at[0] - 6.0, v, z)
            p1 = compat.to_pixel(viewport, at[0] + 6.0, v, z)
        if p0 and p1:
            painter.drawLine(QPointF(*p0), QPointF(*p1))
    painter.restore()


class ColumnTool(_PlotTool):
    name = "ArchXQ column"
    axq_element = "column"
    adjust = staticmethod(lambda c: c)   # ui: fitted inside the walls
    noun = "Column"
    icon = "rectangle_center"
    vcb_label = "Length"
    diagonal = True

    def __init__(self, mode, on_done, on_cancelled, z, opts, existing):
        """``mode`` single | row | grid; ``opts()`` → the options bar's
        column choices; ``existing()`` → the level's columns."""
        super().__init__(on_done, on_cancelled)
        self.mode = mode
        self.z = z
        self.opts = opts
        self.existing = existing
        if mode == "grid":
            self.vcb_label = "Dimensions"
            self.vcb_comma_lists = True

    def _reset(self) -> None:
        self.a = None
        self.diag = None
        self._sync()

    def _busy(self) -> bool:
        return self.a is not None

    def _anchor(self):
        return self.a

    #: the wall corners / T's of the level (ui sets it): the cursor is
    #: pulled onto them, and squares up with them
    magnets: list = []
    MAGNET_PX = 14

    def _align_sources(self):
        return [list(S.column_centre(c)) for c in self.existing()] \
            + [list(p) for p in self.magnets]

    face_x: list = []
    face_y: list = []
    guides: list = []
    #: the excavations' outlines on this level (ui sets it): a ROW clicked
    #: along a pit's side — its corners, its edge — stands INSIDE it, the
    #: columns' faces flush with the side and the end ones in the corners
    #: (his ask, 2026-10-06: the column turns only after the first click,
    #: so its faces could not be laid flush by hand)
    pits: list = []
    PIT_PX = 12

    def _metres(self, px: float, p) -> float:
        a = compat.to_pixel(self.viewport, p[0], p[1], self.z)
        b = compat.to_pixel(self.viewport, p[0] + 1.0, p[1], self.z)
        if not a or not b:
            return 0.0
        return px / max(math.dist(a, b), 1e-6)

    def _pit_snap(self, p):
        """A row's click pulled onto a pit's corner, else onto its side."""
        tol = self._metres(self.PIT_PX, p)
        best = None
        for poly in self.pits:
            for q in poly:
                d = math.dist(p, q)
                if d <= tol and (best is None or d < best[0]):
                    best = (d, [q[0], q[1]])
        if best is not None:
            return [round(best[1][0], 4), round(best[1][1], 4)]
        for poly in self.pits:
            n = len(poly)
            for i in range(n):
                q = _foot(p, poly[i], poly[(i + 1) % n])
                if q is None:
                    continue
                d = math.dist(p, q)
                if d <= tol and (best is None or d < best[0]):
                    best = (d, q)
        if best is not None:
            return [round(best[1][0], 4), round(best[1][1], 4)]
        return None

    def _pit_inset(self, a, b, o):
        """(a, b) moved inside the pit whose side both lie on: the row's
        line half a column in from the side, its ends half a column in from
        the corners clicked. Not on one side of a pit: as clicked."""
        from . import plotgeo
        L = math.dist(a, b)
        if L < 1e-6:
            return a, b
        u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        along = float(o["w"])
        across = along if o.get("section") == "round" else float(o["d"])
        if abs((float(o.get("angle", 0)) % 180) - 90) < 1e-6:
            along, across = across, along         # turned square to the row
        # a click within a column's depth of the side counts as ON it (his
        # left side, 2026-10-06: both clicks ~17 cm in, the row came out
        # skewed by 0.04° and off the face) — laid back onto the side
        tol = across + 0.05
        for poly in self.pits:
            n = len(poly)
            for i in range(n):
                p, q = poly[i], poly[(i + 1) % n]
                fa, fb = _foot(a, p, q, tol), _foot(b, p, q, tol)
                if fa is None or fb is None or math.dist(a, fa) > tol \
                        or math.dist(b, fb) > tol or math.dist(fa, fb) < 1e-6:
                    continue
                # onto the side, and onto its corner when that near
                a = next((list(c) for c in (p, q) if math.dist(fa, c) <= tol),
                         fa)
                b = next((list(c) for c in (p, q) if math.dist(fb, c) <= tol),
                         fb)
                L = math.dist(a, b)
                u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
                nx, ny = -u[1], u[0]
                m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                if not plotgeo.inside_polygon(
                        (m[0] + nx * 0.01, m[1] + ny * 0.01), poly):
                    nx, ny = -nx, -ny
                h = across / 2
                ka = along / 2 if any(math.dist(a, c) < 0.02 for c in poly) \
                    else 0.0
                kb = along / 2 if any(math.dist(b, c) < 0.02 for c in poly) \
                    else 0.0
                return ([a[0] + nx * h + u[0] * ka, a[1] + ny * h + u[1] * ka],
                        [b[0] + nx * h - u[0] * kb, b[1] + ny * h - u[1] * kb])
        return a, b

    def _pick(self, ctx) -> list[float]:
        p = super()._pick(ctx)
        self.guides = []
        if self.viewport is None or self._guide_hit:
            return p
        if self.mode == "row" and self.pits:
            q = self._pit_snap(p)
            if q is not None:
                self._aligned = []
                return q
        here = compat.to_pixel(self.viewport, p[0], p[1], self.z)
        if not here:
            return p
        best = None
        for q in self.magnets or ():
            px = compat.to_pixel(self.viewport, q[0], q[1], self.z)
            if px:
                d = math.dist(here, px)
                if d <= self.MAGNET_PX and (best is None or d < best[0]):
                    best = (d, q)
        if best is not None:
            self._aligned = []
            return [round(best[1][0], 4), round(best[1][1], 4)]
        # a face laid flush with a wall's / the plot's / another column's
        # (his ask, 2026-10-03: only the centre and the corners pulled) —
        # the column's sides, when it stands square with the axes
        o = self.opts()
        if o.get("section") == "round" or float(o.get("angle", 0)) % 90:
            return p
        pts = S.column_outline(self._col(p), 0.0)
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        dx, dy, self.guides = face_pull(
            self.viewport, self.z, p, [min(xs), max(xs)], [min(ys), max(ys)],
            self.face_x, self.face_y)
        if dx or dy:
            self._aligned = []
        return [round(p[0] + dx, 4), round(p[1] + dy, 4)]

    def _sync(self) -> None:
        self._sync_protocol([self.a] if self.a else [], self.hover)
        self.chain_first_point = None

    # -- the columns -----------------------------------------------------------------
    def _col(self, p, angle=None) -> dict:
        o = self.opts()
        ang = o["angle"] if angle is None else angle
        return {"type": "column", "x": round(p[0], 4), "y": round(p[1], 4),
                "shape": o["section"], "w": o["w"],
                "d": o["w"] if o["section"] == "round" else o["d"],
                "angle": round(ang, 3), "anchor": o["anchor"]}

    def columns(self, b) -> list[dict]:
        """What clicking ``b`` now makes."""
        o = self.opts()
        if self.mode == "single" or self.a is None:
            return [self._col(b)]
        if self.mode == "row":
            a, b = self._pit_inset(self.a, b, o)    # (squared to the side)
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            return [self._col([a[0] + (b[0] - a[0]) * t,
                               a[1] + (b[1] - a[1]) * t],
                              o["angle"] + ang)
                    for t in row_stations(math.dist(a, b), o)]
        nx, ny = max(1, int(o["nx"])), max(1, int(o["ny"]))
        xs = [self.a[0] + (b[0] - self.a[0]) * (k / (nx - 1) if nx > 1 else 0)
              for k in range(nx)]
        ys = [self.a[1] + (b[1] - self.a[1]) * (k / (ny - 1) if ny > 1 else 0)
              for k in range(ny)]
        return [self._col([x, y]) for y in ys for x in xs]

    # -- input -----------------------------------------------------------------------
    def on_click(self, ctx) -> None:
        p = self._pick(ctx)
        if self.mode != "single" and self.a is None:
            self.a = p
            self._sync()
            self._show_hint()
            return
        self.last_ab = (list(self.a), list(p)) if self.a else None
        self._done(self.columns(p))

    def _done(self, cols) -> None:
        self._reset()
        self.viewport.update()
        self.on_done(cols)

    def on_value(self, viewport, value) -> bool:
        if self.a is None or self.hover is None:
            return False
        if self.mode == "row" and isinstance(value, (int, float)):
            dx, dy = self.hover[0] - self.a[0], self.hover[1] - self.a[1]
            d = math.hypot(dx, dy)
            if d < 1e-9:
                return False
            L = abs(float(value))
            self._done(self.columns([self.a[0] + dx / d * L,
                                     self.a[1] + dy / d * L]))
            return True
        if self.mode == "grid" and isinstance(value, tuple) \
                and len(value) >= 2:
            sx = 1 if self.hover[0] >= self.a[0] else -1
            sy = 1 if self.hover[1] >= self.a[1] else -1
            self._done(self.columns([self.a[0] + sx * abs(value[0]),
                                     self.a[1] + sy * abs(value[1])]))
            return True
        return False

    def on_key(self, viewport, key, modifiers) -> bool:
        if key == Qt.Key_Backspace and self.a is not None \
                and not compat.typed_value(viewport):
            self._reset()
            viewport.update()
            return True
        return super().on_key(viewport, key, modifiers)

    # -- the host's protocol / drawing -------------------------------------------------
    def rubber_band_lines(self):
        if self.a is None or self.hover is None:
            return []
        if self.mode == "row":
            return [(self._P(self.a), self._P(self.hover))]
        a, h = self.a, self.hover
        q = [[a[0], a[1]], [h[0], a[1]], [h[0], h[1]], [a[0], h[1]]]
        return [(self._P(q[i]), self._P(q[(i + 1) % 4])) for i in range(4)]

    def value_label(self):
        if self.a is None or self.hover is None:
            return None
        if self.mode == "row":
            return (f"{math.dist(self.a, self.hover):.2f} m", None)
        return (f"{abs(self.hover[0] - self.a[0]):.2f} × "
                f"{abs(self.hover[1] - self.a[1]):.2f} m", None)

    def _labels(self):
        if self.a is None or self.hover is None:
            return []
        if self.mode == "row":
            return [((self.a, self.hover), _m(math.dist(self.a, self.hover)),
                     None)]
        c = [self.hover[0], self.a[1]]
        return [((self.a, c), _m(abs(self.hover[0] - self.a[0])), None),
                ((c, self.hover), _m(abs(self.hover[1] - self.a[1])), None)]

    def status_clause(self) -> str:
        if self.mode == "single":
            return "Column: click where it goes  ·  Esc = done"
        if self.a is None:
            return (f"Columns ({self.mode}): click the first one  ·  "
                    "Esc = done")
        if self.mode == "row":
            return ("Columns (row): click the last one, or type the length + "
                    "Enter — the count is in the options bar  ·  Esc = drop")
        return ("Columns (grid): click the opposite corner, or type w;d + "
                "Enter — columns × rows in the options bar  ·  Esc = drop")

    def draw_overlay(self, viewport, painter) -> None:
        if self.hover is not None:
            try:
                _draw_loops(viewport, painter,
                            [S.column_outline(self.adjust(c), 0.0)
                             for c in self.columns(self.hover)], self.z,
                            fill=True)
            except Exception:  # noqa: BLE001 — a preview never breaks paint
                pass
            draw_guides(viewport, painter, self.guides, self.hover, self.z)
        super().draw_overlay(viewport, painter)


class BeamTool(WallChainTool):
    """Point by point, like a run of walls: each line a beam, joined to
    the level's other beams by the walls engine (the preview too)."""
    name = "ArchXQ beam"
    axq_element = "beam"
    noun = "Beam"
    #: the centres of the columns it may rest on — this level's and the
    #: ones below reaching up to it (ui sets it): the cursor is pulled onto
    #: them, the host's snap only catches their corners and faces (his
    #: ask, 2026-10-06: beams go column to column)
    magnets: list = []
    MAGNET_PX = 14

    def _align_sources(self):
        return super()._align_sources() + [list(p) for p in self.magnets]

    def _pick(self, ctx) -> list[float]:
        p = super()._pick(ctx)
        if self.viewport is None or not self.magnets:
            return p
        here = compat.to_pixel(self.viewport, p[0], p[1], self.z)
        if not here:
            return p
        best = None
        for q in self.magnets:
            px = compat.to_pixel(self.viewport, q[0], q[1], self.z)
            if px:
                d = math.dist(here, px)
                if d <= self.MAGNET_PX and (best is None or d < best[0]):
                    best = (d, q)
        if best is None:
            return p
        self._aligned = []
        return [round(best[1][0], 4), round(best[1][1], 4)]

    def line_records(self, pts, closed):
        recs = super().line_records(pts, closed)
        for r in recs:
            r["align"] = "centre"           # a beam sits on its line
        return recs

    def status_clause(self) -> str:
        return super().status_clause().replace("Wall:", "Beam:")


def slab_tool(base):
    """One of the plot's outline tools, drawing a slab's outline on the
    level's floor."""
    class T(base):
        name = "ArchXQ slab"
        axq_element = "slab"
        noun = "Slab"

        def __init__(self, on_done, on_cancelled, z):
            base.__init__(self, on_done, on_cancelled)
            self.z = z

        def _finish(self, corners) -> None:
            corners = [list(c) for c in corners]
            if abs(S._area(corners)) < 0.05:
                compat.flash(self.viewport, "Too small for a slab", 4000)
                return
            self._reset()
            self.viewport.update()
            self.on_done(corners)            # the tool stays for the next
    T.__name__ = "Slab" + base.__name__.replace("Plot", "")
    return T


SLAB_TOOLS = {"rect": slab_tool(plottools.PlotRectTool),
              "rect_c": slab_tool(plottools.PlotCentreRectTool),
              "rect_r": slab_tool(plottools.PlotRotRectTool),
              "chain": slab_tool(plottools.PlotPolyTool)}


def beams_as_walls(beams: list[dict]) -> list[dict]:
    """The level's beams, as the walls engine sees them (the preview)."""
    return [dict(S.as_wall(b, shrink=0.0)) for b in beams]


def near(p, q, tol: float = 0.01) -> bool:
    return math.dist(p, q) <= tol


__all__ = ["ColumnTool", "BeamTool", "SLAB_TOOLS", "beams_as_walls", "W"]
