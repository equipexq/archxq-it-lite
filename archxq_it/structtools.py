# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Drawing the STRUCTURE in the 3D view — on the current level's floor.

The same habits as the walls: the options bar holds the choices (section,
sizes, how many), the tool shows the result LIVE (outlines, lines only),
hands ``on_done(records)`` and stays out for the next.

- ColumnTool: «single» (click = a column), «row» (a PATH, point by point
  like a wall — each stretch gets the options bar's count / spacing, a
  column on every corner once; the first point again closes it; it is kept
  as a «Column row» group, colrows.py), «grid»
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
from .place3d import OnPlane
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


#: (moved to colrows.py with the path, 07/11/2026 — kept here by name)
from .colrows import row_stations  # noqa: E402,F401


def _upright(viewport, painter, loops, z, rise) -> None:
    """3D: the columns standing — their outlines up to ``rise`` over the
    floor ``z`` (in the plan they are seen from the top: nothing more)."""
    from . import place3d as P3
    if rise and P3.in_3d(viewport):
        P3.draw3d(viewport, painter,
                  [ln for lp in loops for ln in P3.box_lines(lp, z, z + rise)],
                  INK, 1.4)


class ColumnDrawTool(OnPlane, plottools.PlotRectTool):
    """DRAW a column: two opposite corners — its size and its place."""
    name = "ArchXQ column"
    axq_element = "column"
    noun = "Column"
    face_x: list = []
    face_y: list = []
    rise = 0.0                # ui sets: how tall it stands (the 3D preview)

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
        if self.first is not None and self.hover is not None:
            try:
                _upright(viewport, painter,
                         [self._rect(self.first, self.hover)], self.z,
                         self.rise)
            except Exception:  # noqa: BLE001 — a preview never breaks paint
                pass


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


class ColumnTool(OnPlane, _PlotTool):
    name = "ArchXQ column"
    axq_element = "column"
    adjust = staticmethod(lambda c: c)   # ui: fitted inside the walls
    noun = "Column"
    icon = "rectangle_center"
    vcb_label = "Length"
    diagonal = True
    rise = 0.0                # ui sets: how tall they stand (3D preview)

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

    #: ui sets (row mode): (tool, points, closed) → the row made / changed
    #: at each click — its columns are there at once, stretch by stretch
    on_path = None
    CLOSE_PX = 14            # a click this near the first point closes

    #: the level's floor (the plan's plane), and — in 3D, the cursor on a
    #: footing — that footing's top: the preview stands ON it (his test,
    #: 07/11/2026: in the basement it floated 30 cm over the pads)
    z_floor = None
    _foot_z = None

    def _plane_z(self) -> None:
        from . import place3d as P3
        if self.z_floor is None:
            self.z_floor = self.z
        z = self._foot_z if self._foot_z is not None \
            and P3.in_3d(self.viewport) else self.z_floor
        if abs(z - self.z) > 1e-9:
            self.z = z
            self._sync()

    def _on_foot(self, z) -> None:
        """The cursor on a footing (its top ``z``) or not — a row begun on
        one stays at its top to the end."""
        if z is None and (self.a is not None or getattr(self, "pts", None)):
            return
        if z != self._foot_z:
            self._foot_z = z
            self._plane_z()

    def _rise_now(self) -> float:
        """How tall the preview stands: to the same top from a footing."""
        if self.z_floor is None:
            return self.rise
        return self.rise + max(0.0, self.z_floor - self.z)

    def _reset(self) -> None:
        self._foot_z = None
        self.a = None
        self.pts: list = []          # a row's path: the points clicked
        self.row_id = None           # …and the «Column row» it made (ui)
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
            + [list(p[:2]) for p in self.magnets]

    #: the footings' axes ((x, y), (x, y), z top) — ui sets them (as the
    #: beam's: BeamTool._axis_snap)
    axes: list = []

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
        """(a, b) moved inside the pit whose side both lie on (colrows)."""
        from . import colrows
        return colrows.pit_inset(a, b, o, self.pits)

    def _pick(self, ctx) -> list[float]:
        p = super()._pick(ctx)
        self.guides = []
        if self.viewport is None or self._guide_hit:
            return p
        here = compat.to_pixel(self.viewport, p[0], p[1], self.z)
        # the exact points first — a wall's corner, a column / a row's point
        # of the level below or above (his ask, 08/11/2026: a column over
        # another one was set by eye) — then an excavation's side
        best = None
        for q in (self.magnets or ()) if here else ():
            # (a footing's point: seen at its top)
            px = compat.to_pixel(self.viewport, q[0], q[1],
                                 float(q[2]) if len(q) > 2 else self.z)
            if px:
                d = math.dist(here, px)
                if d <= self.MAGNET_PX and (best is None or d < best[0]):
                    best = (d, q)
        if best is not None:
            self._aligned = []
            q = best[1]
            self._on_foot(float(q[2]) if len(q) > 2 else None)
            return [round(q[0], 4), round(q[1], 4)]
        # a footing's line (his test, 07/11/2026: columns on a footing row)
        hit = self._axis_snap(here) if here and self.axes else None
        if hit is not None:
            self._aligned = []
            self._on_foot(hit[2])
            return [hit[0], hit[1]]
        self._on_foot(None)
        if self.mode == "row" and self.pits:
            q = self._pit_snap(p)
            if q is not None:
                self._aligned = []
                return q
        if not here:
            return p
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
        if self.mode == "row" and getattr(self, "pts", None):
            self._sync_protocol(self.pts, self.hover)
        else:
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
            # the whole path with the stretch to ``b``: a corner turns into
            # one with a column of its own as soon as the path goes on
            from . import colrows
            pts = list(getattr(self, "pts", None) or [self.a])
            closed = self._closing(b)
            path = pts if closed else pts + [list(b)]
            return [self._col([x, y], ang) for x, y, ang in
                    colrows.stations(path, closed, o, self.pits)]
        nx, ny = max(1, int(o["nx"])), max(1, int(o["ny"]))
        xs = [self.a[0] + (b[0] - self.a[0]) * (k / (nx - 1) if nx > 1 else 0)
              for k in range(nx)]
        ys = [self.a[1] + (b[1] - self.a[1]) * (k / (ny - 1) if ny > 1 else 0)
              for k in range(ny)]
        return [self._col([x, y]) for y in ys for x in xs]

    # -- input -----------------------------------------------------------------------
    def _closing(self, p, ctx=None) -> bool:
        """The point is the path's first one again (on the screen): the
        row closes — three points at least."""
        pts = getattr(self, "pts", None) or []
        if self.mode != "row" or len(pts) < 3 or p is None:
            return False
        a = compat.to_pixel(self.viewport, pts[0][0], pts[0][1], self.z) \
            if self.viewport is not None else None
        if a is None:
            return math.dist(p, pts[0]) < 1e-3
        here = []
        scr = getattr(ctx, "screen", None)
        if scr is not None:
            here.append((scr.x(), scr.y()))
        b = compat.to_pixel(self.viewport, p[0], p[1], self.z)
        if b is not None:
            here.append(b)
        return any(math.dist(a, h) <= self.CLOSE_PX for h in here)

    def on_hover(self, ctx) -> None:
        super().on_hover(ctx)
        if self._closing(self.hover, ctx):
            self.hover = list(self.pts[0])      # the rubber band closes
            self._sync()

    def _path_add(self, p, ctx=None) -> None:
        """A row's next point: the path so far is made (or changed) at once
        — the first stretch at the 2nd click, as the row of before."""
        if self._closing(p, ctx):
            self._path_end(closed=True)
            return
        if math.dist(p, self.pts[-1]) < 1e-3:   # (a double click's 2nd)
            self._path_end()
            return
        self.pts.append(list(p))
        self.a = list(p)
        self.last_ab = (list(self.pts[-2]), list(self.pts[-1]))
        self._sync()
        if self.on_path is not None:
            self.on_path(self, [list(q) for q in self.pts], False)
        self._show_hint()
        if self.viewport is not None:
            self.viewport.update()

    def _path_end(self, closed: bool = False) -> None:
        """The path done — open (Enter, a double click, Esc) or CLOSED (its
        first point clicked): its columns are already there; the tool stays
        for the next row."""
        pts = [list(q) for q in self.pts]
        if closed and self.on_path is not None and len(pts) >= 3:
            self.on_path(self, pts, True)
        self._reset()
        if self.viewport is not None:
            self.viewport.update()

    def on_double_click(self, ctx) -> None:
        if self.mode != "row":
            self.on_click(ctx)
            return
        if not self.pts:
            return
        p = self._pick(ctx)
        if self._closing(p, ctx):
            self._path_end(closed=True)
            return
        if math.dist(p, self.pts[-1]) >= 1e-3:
            self._path_add(p, ctx)
        if self.pts:
            self._path_end()

    def on_click(self, ctx) -> None:
        if self._grazes(ctx):                # 3D: a ray along the floor
            return
        p = self._pick(ctx)
        if self.mode == "row" and self.pts:
            self._path_add(p, ctx)
            return
        if self.mode == "row":
            self.pts = [list(p)]
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
            self._path_add([round(self.a[0] + dx / d * L, 4),
                            round(self.a[1] + dy / d * L, 4)])
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
        typing = bool(compat.typed_value(viewport))
        if self.mode == "row" and self.pts and not typing:
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._path_end()                 # done, open
                return True
            if key == Qt.Key_Backspace:          # the last point back
                self.pts.pop()
                if self.on_path is not None and self.row_id is not None:
                    self.on_path(self, [list(q) for q in self.pts], False)
                if self.pts:
                    self.a = list(self.pts[-1])
                    self._sync()
                else:
                    self._reset()
                viewport.update()
                return True
        if key == Qt.Key_Backspace and self.a is not None and not typing:
            self._reset()
            viewport.update()
            return True
        return super().on_key(viewport, key, modifiers)

    # -- the host's protocol / drawing -------------------------------------------------
    def rubber_band_lines(self):
        if self.a is None or self.hover is None:
            return []
        if self.mode == "row":
            pts = list(self.pts or [self.a]) + [self.hover]
            return [(self._P(p), self._P(q)) for p, q in zip(pts, pts[1:])]
        a, h = self.a, self.hover
        q = [[a[0], a[1]], [h[0], a[1]], [h[0], h[1]], [a[0], h[1]]]
        return [(self._P(q[i]), self._P(q[(i + 1) % 4])) for i in range(4)]

    def value_label(self):
        if self.a is None or self.hover is None:
            return None
        if self.mode == "row":
            return (compat.fmt_len(math.dist(self.a, self.hover)), None)
        if compat.doc_length_unit() != "m":
            return (f"{compat.fmt_len(abs(self.hover[0] - self.a[0]))} × "
                    f"{compat.fmt_len(abs(self.hover[1] - self.a[1]))}", None)
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
            if len(getattr(self, "pts", None) or []) < 2:
                return ("Columns (row): click the next point, or type the "
                        "length + Enter — the count is in the options bar  ·"
                        "  Esc = drop")
            return ("Columns (row): the next point (a column on each corner)"
                    " · the first point = close · double click / Enter / "
                    "Esc = done · Backspace = back a point")
        return ("Columns (grid): click the opposite corner, or type w;d + "
                "Enter — columns × rows in the options bar  ·  Esc = drop")

    def draw_overlay(self, viewport, painter) -> None:
        if self.hover is not None:
            try:
                loops = [S.column_outline(self.adjust(c), 0.0)
                         for c in self.columns(self.hover)]
                _draw_loops(viewport, painter, loops, self.z, fill=True)
                _upright(viewport, painter, loops, self.z, self._rise_now())
            except Exception:  # noqa: BLE001 — a preview never breaks paint
                pass
            draw_guides(viewport, painter, self.guides, self.hover, self.z)
        super().draw_overlay(viewport, painter)


class BeamTool(OnPlane, WallChainTool):
    """Point by point, like a run of walls: each line a beam, joined to
    the level's other beams by the walls engine (the preview too). In 3D
    it is pointed at its own height — its underside, on the columns' tops
    (PLANO_ABERTURAS_3D.md D10): beams go column to column as seen."""
    name = "ArchXQ beam"
    axq_element = "beam"
    noun = "Beam"
    #: ui sets: the floor (the plan's plane) and () → the beam's underside
    z_floor = None
    under = None

    def _plane_z(self) -> None:
        from . import place3d as P3
        if self.z_floor is None:
            self.z_floor = self.z
        z = self.z_floor
        if self.under is not None and P3.in_3d(self.viewport):
            if self._foot_z is not None:
                # on a footing: drawn at ITS top, where the beam will sit
                # (his test, 07/11/2026: in 3D the line floated 2.50 m up,
                # off the footings it was pulled onto)
                z = self._foot_z
            else:
                try:
                    z = float(self.under())
                except Exception:  # noqa: BLE001 — the floor, as in plan
                    z = self.z_floor
        if abs(z - self.z) > 1e-9:
            self.z = z
            self._sync()            # the points already placed, at it too
    #: the centres of the columns it may rest on — this level's and the
    #: ones below reaching up to it (ui sets it): the cursor is pulled onto
    #: them, the host's snap only catches their corners and faces (his
    #: ask, 2026-10-06: beams go column to column)
    magnets: list = []
    MAGNET_PX = 14

    def _align_sources(self):
        return super()._align_sources() + [list(p[:2]) for p in self.magnets]

    def _pick(self, ctx) -> list[float]:
        p = super()._pick(ctx)
        if self.viewport is None or not (self.magnets or self.axes):
            return p
        here = self._cursor_px(ctx, p)
        if not here:
            return p
        best = None
        for q in self.magnets:
            # a footing's point: seen at ITS top (3D), not at the beam's
            z = float(q[2]) if len(q) > 2 else self.z
            px = compat.to_pixel(self.viewport, q[0], q[1], z)
            if px:
                d = math.dist(here, px)
                if d <= self.MAGNET_PX and (best is None or d < best[0]):
                    best = (d, q)
        if best is None:
            hit = self._axis_snap(here)
            if hit is None:
                self._on_foot(None)
                return p
            self._aligned = []
            self._on_foot(hit[2])
            return [hit[0], hit[1]]
        self._aligned = []
        q = best[1]
        self._on_foot(float(q[2]) if len(q) > 2 else None)
        return [round(q[0], 4), round(q[1], 4)]

    _foot_z = None

    def _on_foot(self, z) -> None:
        """The cursor on a footing (its top ``z``) or not: the plane in 3D
        follows — a beam begun on a footing stays at its top to the end."""
        if z is None and getattr(self, "pts", None):
            return                       # begun: its plane stays
        if z != self._foot_z:
            self._foot_z = z
            self._plane_z()

    def _reset(self) -> None:
        self._foot_z = None
        super()._reset()

    #: the footings' AXES of this level, ((x, y), (x, y), z top) — ui sets
    #: them: the cursor is pulled onto the line (his test, 07/11/2026: a
    #: beam on top of a footing row — a wall's base — had nothing to hold)
    axes: list = []

    def _cursor_px(self, ctx, p):
        """The cursor on the screen (its pixel) — else ``p``'s, which lies
        on its ray on the plane it is drawn at."""
        scr = getattr(ctx, "screen", None)
        if scr is not None:
            try:
                return (float(scr.x()), float(scr.y()))
            except Exception:  # noqa: BLE001
                pass
        return compat.to_pixel(self.viewport, p[0], p[1], self.z)

    def _axis_snap(self, here):
        """The nearest point of a footing's axis, within MAGNET_PX on the
        screen — or None."""
        best = None
        for a, b, z in self.axes:
            pa = compat.to_pixel(self.viewport, a[0], a[1], z)
            pb = compat.to_pixel(self.viewport, b[0], b[1], z)
            if not pa or not pb:
                continue
            dx, dy = pb[0] - pa[0], pb[1] - pa[1]
            L2 = dx * dx + dy * dy
            if L2 < 1e-9:
                continue
            t = max(0.0, min(1.0, ((here[0] - pa[0]) * dx
                                   + (here[1] - pa[1]) * dy) / L2))
            d = math.dist(here, (pa[0] + t * dx, pa[1] + t * dy))
            if d <= self.MAGNET_PX and (best is None or d < best[0]):
                # (the screen's t is the plan's only in a parallel view:
                # the plan point found again on the line, by its pixel)
                best = (d, a, b, z, t)
        if best is None:
            return None
        _d, a, b, z, t = best
        t = self._plan_t(a, b, z, here, t)
        return [round(a[0] + t * (b[0] - a[0]), 4),
                round(a[1] + t * (b[1] - a[1]), 4), z]

    def _plan_t(self, a, b, z, here, t0) -> float:
        """Where on a→b (0..1) the pixel ``here`` falls — a few steps of
        bisection on the screen (perspective bends the screen's t)."""
        lo, hi = 0.0, 1.0
        def px(t):
            return compat.to_pixel(self.viewport, a[0] + t * (b[0] - a[0]),
                                   a[1] + t * (b[1] - a[1]), z)
        pa, pb = px(0.0), px(1.0)
        if not pa or not pb:
            return t0
        dx, dy = pb[0] - pa[0], pb[1] - pa[1]
        def s(t):                       # its screen position along a→b
            q = px(t)
            return ((q[0] - pa[0]) * dx + (q[1] - pa[1]) * dy) if q else 0.0
        goal = (here[0] - pa[0]) * dx + (here[1] - pa[1]) * dy
        for _ in range(30):
            mid = (lo + hi) / 2
            if s(mid) < goal:
                lo = mid
            else:
                hi = mid
        return max(0.0, min(1.0, (lo + hi) / 2))

    def line_records(self, pts, closed):
        # «Insert» (a customer's ask, 2026-10-10): the line drawn is its
        # left or right face — the line is moved half its width over, and
        # the beam is kept by its axis as ever (Tab swaps the sides)
        o = self.opts()
        side = {"left": 1.0, "right": -1.0}.get(o.get("insert"), 0.0)
        if side and len(pts) >= 2:
            pts = offset_chain(pts, (-side if self.flip else side)
                               * float(o["t"]) / 2, closed)
        recs = super().line_records(pts, closed)
        for r in recs:
            r["align"] = "centre"           # a beam sits on its line
        return recs

    def status_clause(self) -> str:
        s = super().status_clause().replace("Wall:", "Beam:")
        if self.opts().get("insert") in ("left", "right"):
            s = s.replace("Tab = other side", "Tab = other face")
        return s


class PadTool(ColumnTool):
    """A pad footing DRAWN: a click each (his ask, 2026-11-01: on a level
    with no columns the one-click pads made nothing, and nothing could be
    drawn). The column tool's square, pulled onto the columns' centres and
    the walls' corners; on a column, ui sizes it round that column."""
    name = "ArchXQ footing"
    axq_element = "footing"
    noun = "Pad footing"

    def __init__(self, on_done, on_cancelled, z, opts, existing):
        super().__init__("single", on_done, on_cancelled, z,
                         lambda: {"section": "rect", "w": opts()["w"],
                                  "d": opts()["w"], "angle": 0.0,
                                  "anchor": "centre"}, existing)

    def status_clause(self) -> str:
        return ("Pad footing: click where it goes — on a column it is "
                "centred under it  ·  Esc = done")


class FootRowTool(ColumnTool):
    """FOOTINGS ALONG A PATH (PLANO_LINHA_COLUNAS D, his OK 07/11/2026): the
    columns' row tool — point by point, corners, the first point closes,
    Backspace, the magnets, flush inside an excavation — its squares the
    PADS, with the strip along it shown too. No column over them (a timber
    house's footings). ui makes the «Footing row» at each click."""
    name = "ArchXQ footing"
    axq_element = "footing"
    noun = "Footing"
    row_what = "footings"

    def __init__(self, on_cancelled, z, opts, existing):
        super().__init__("row", lambda _recs: None, on_cancelled, z, opts,
                         existing)

    def _preview(self) -> list:
        from . import colrows
        o = self.opts()
        ft = o["foots"]["type"]
        loops = []
        if ft in ("pads", "both"):
            loops += [S.column_outline(c, 0.0)
                      for c in self.columns(self.hover)]
        pts = list(getattr(self, "pts", None) or [])
        if ft in ("strip", "both") and pts:
            closed = self._closing(self.hover)
            path = pts if closed else pts + [list(self.hover)]
            h = float(o["foots"]["sw"]) / 2
            for a, b in colrows.stretches(path, closed, o, self.pits)[1]:
                L = math.dist(a, b)
                if L < 1e-6:
                    continue
                nx, ny = -(b[1] - a[1]) / L * h, (b[0] - a[0]) / L * h
                loops.append([(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny),
                              (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)])
        return loops

    def draw_overlay(self, viewport, painter) -> None:
        if self.hover is not None:
            try:
                _draw_loops(viewport, painter, self._preview(), self.z,
                            fill=True)
            except Exception:  # noqa: BLE001 — a preview never breaks paint
                pass
            draw_guides(viewport, painter, self.guides, self.hover, self.z)
        super(ColumnTool, self).draw_overlay(viewport, painter)

    def status_clause(self) -> str:
        if self.a is None:
            return "Footings (path): click the first point  ·  Esc = done"
        if len(getattr(self, "pts", None) or []) < 2:
            return ("Footings (path): click the next point, or type the "
                    "length + Enter  ·  Esc = drop")
        return ("Footings (path): the next point · the first point = close "
                "· double click / Enter / Esc = done · Backspace = back a "
                "point")


class StripTool(BeamTool):
    """A strip footing DRAWN point by point, like a run of walls — joined
    to the level's other strips (L, T, X); width from the bar's «Strip»."""
    name = "ArchXQ footing"
    axq_element = "footing"
    noun = "Strip footing"

    def status_clause(self) -> str:
        return super().status_clause().replace("Beam:", "Strip footing:")


def offset_chain(pts, d: float, closed: bool) -> list:
    """The polyline ``pts`` moved ``d`` to its LEFT (negative: right): each
    corner where the two moved lines cross — the run keeps its joints."""
    n = len(pts)
    segs = list(zip(pts, pts[1:])) + ([(pts[-1], pts[0])] if closed else [])

    def moved(a, b):
        L = math.dist(a, b)
        if L < 1e-9:
            return None
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        return (a[0] - uy * d, a[1] + ux * d), (ux, uy)
    lines = [moved(a, b) for a, b in segs]
    out = []
    for i in range(n):
        before = lines[i - 1] if (i > 0 or closed) else None
        after = lines[i] if i < len(lines) else None
        p = None
        if before and after:
            (p1, u1), (p2, u2) = before, after
            cr = u1[0] * u2[1] - u1[1] * u2[0]
            if abs(cr) > 1e-6:              # a real corner: where they cross
                t = ((p2[0] - p1[0]) * u2[1] - (p2[1] - p1[1]) * u2[0]) / cr
                p = (p1[0] + u1[0] * t, p1[1] + u1[1] * t)
        if p is None:                       # an end, or a straight joint
            near = after or before
            if near is None:                # a point on its own: as it is
                p = tuple(pts[i])
            else:
                u = near[1]
                p = (pts[i][0] - u[1] * d, pts[i][1] + u[0] * d)
        out.append([round(p[0], 4), round(p[1], 4)])
    return out


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
              "chain": slab_tool(plottools.PlotPolyTool),
              # a slab OPENING may be round too (a customer's ask,
              # 2026-10-13: «of any shape, not only rectangular»)
              "circle": slab_tool(plottools.PlotCircleTool)}
#: how a slab OPENING is drawn — the options bar's «Drawn» (shape «hole»)
HOLE_DRAWN = (("rect", "Rectangle"), ("rect_r", "Rotated"),
              ("chain", "Points"), ("circle", "Circle"))


# a column, too, is pulled onto a footing's line (the beam's way)
ColumnTool._axis_snap = BeamTool._axis_snap
ColumnTool._plan_t = BeamTool._plan_t


def beams_as_walls(beams: list[dict]) -> list[dict]:
    """The level's beams, as the walls engine sees them (the preview)."""
    return [dict(S.as_wall(b, shrink=0.0)) for b in beams]


def near(p, q, tol: float = 0.01) -> bool:
    return math.dist(p, q) <= tol


__all__ = ["ColumnTool", "BeamTool", "PadTool", "StripTool", "SLAB_TOOLS",
           "beams_as_walls", "W"]
