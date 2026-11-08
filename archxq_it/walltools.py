# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Drawing WALLS in the 3D view — on the current level's floor.

Every shape of the options bar is a tool here; all show the walls LIVE
as you draw (their real thickness, joined to the walls already there),
so the side they grow to is seen before clicking. Each one hands the
finished walls to ``on_done(records)`` and stays out for the next.

- WallChainTool  «Point by point»: click point after point; a typed
  number lays the next point that far along the cursor's way; C or a
  click on the first point closes; Enter / double-click ends it open.
- WallRectTool / WallCentreRectTool / WallRotRectTool: the plot's three
  rectangles (corner to corner · from the centre · rotated), as four
  walls round a room.
- WallArc3Tool  «Curved — 3 points»: start, end, a point on the curve.
- WallArcCentreTool «Curved — from its centre»: centre, start, end (the
  way the mouse turns; past a half circle too).
- WallCircleTool «Round wall»: centre, radius (clicked or typed).
Tab turns an open run / a curve to the other side; Backspace takes the
last point back; Esc drops what is being drawn (Esc again: the tool ends).
"""
from __future__ import annotations

import copy
import math

from PySide6.QtCore import Qt

from . import compat, plottools, walls as W
from . import place3d as P3
from .plottools import CLOSE_PX, _PlotTool, _m

PREVIEW_INK = "#e8742c"
TOOL_NAME = "ArchXQ wall"          # ui knows the wall tools by this name
#: a point this near a wall's end IS that end (his «S», 2026-11-01: the
#: host's corner snap landed 0.7 mm off it — a joint off by a hair)
END_SNAP_M = 0.002
#: a curve leaving a wall's end within ~25° of its way continues it
CONTINUES_DOT = 0.9


def _end_points(w: dict) -> list:
    """[(end "a" | "b", role, point, way)]: where a wall can be continued
    from — the end of its line drawn ("drawn") and the corners of its two
    faces there ("outside", "inside": where its outside / inside layers
    are), with the way it runs on past that end. A round wall: none. (His
    «S», 2026-11-01: the second curve began on the first one's INSIDE
    corner, was not seen as going on from it, and took its layers
    inside out.)"""
    if w.get("kind", "line") == "circle":
        return []
    try:
        cen = W.centre(w)
        s = float(w.get("side", 1))
        h = float(w["t"]) / 2.0
        out = []
        for end, f in (("a", 0.0), ("b", 1.0)):
            u = cen.tangent(f)
            way = (-u[0], -u[1]) if end == "a" else u
            c = cen.at(f)
            n = (-u[1], u[0])                # the left of the way it runs
            out.append((end, "drawn", tuple(w[end]), way))
            # the outside layers are on the side away from ``side``
            out.append((end, "outside", (c[0] - s * h * n[0],
                                         c[1] - s * h * n[1]), way))
            out.append((end, "inside", (c[0] + s * h * n[0],
                                        c[1] + s * h * n[1]), way))
        return out
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return []


def _wall_at(existing, p, tol: float):
    """(distance, wall, end, role, point) of the wall end — its line's end
    or a face's corner there (``_end_points``) — nearest p within tol, or
    None. On a tie the line's end wins (it comes first)."""
    best = None
    for w in existing():
        for end, role, q, _way in _end_points(w):
            d = math.dist(q, p)
            if d <= tol and (best is None or d < best[0] - 1e-9):
                best = (d, w, end, role, q)
    return best


def _turn(pts, closed: bool) -> float:
    """Signed area of the run (closed or not): > 0 turns left."""
    loop = list(pts)
    n = len(loop)
    if n < 3:
        return 0.0
    s = sum(loop[i][0] * loop[(i + 1) % n][1] - loop[(i + 1) % n][0]
            * loop[i][1] for i in range(n if closed else n - 1))
    if not closed:          # close it in thought to read which way it turns
        s += loop[-1][0] * loop[0][1] - loop[0][0] * loop[-1][1]
    return s / 2.0


class _WallShape:
    """What every wall tool shares: the options, the walls already on the
    level, the records it makes and the live drawing of them."""
    name = TOOL_NAME
    axq_element = "wall"          # the options bar it belongs to (ui)
    noun = "Wall"
    claimed_keys = frozenset({Qt.Key_C, Qt.Key_Tab})

    #: where the building's inside is — the plot's centre (set by ui);
    #: an open run's walls take that side of their FIRST line, and keep it
    inside_ref = None

    def _setup(self, z: float, opts, existing) -> None:
        """``opts()`` → the options bar's choices; ``existing()`` → the
        walls already on this level (what is drawn joins them live)."""
        self.z = z
        self.opts = opts
        self.existing = existing
        self.flip = False

    def open_side(self, a, b) -> int:
        """An open run's inside: the side of its first line the plot's
        centre is on (left without a plot). Decided by the first line and
        KEPT — it used to follow the way the run turned, and the walls
        jumped across when the second line turned right (his complaint,
        2026-10-02). Tab turns it round."""
        ref = self.inside_ref
        if ref is None:
            return 1
        cr = (b[0] - a[0]) * (ref[1] - a[1]) - (b[1] - a[1]) * (ref[0] - a[0])
        return 1 if cr >= 0 else -1

    #: the DXF's «lanes» under the level (tracing.py, 0.15.0 B8) — set by ui
    lanes = None
    #: a run started in a lane: its width (the wall between the lines)
    t_lane = None

    def _rec(self, kind: str, side: int, **geo) -> dict:
        o = self.opts()
        t, align = o["t"], o["align"]
        if self.t_lane:                  # traced: between the drawing's lines
            t, align = self.t_lane, "centre"
        rec = dict(geo, kind=kind, t=t, align=align,
                   side=-side if self.flip else side, id=f"~{id(geo)}",
                   name="~")
        if o.get("wtype") and not o.get("cw"):
            rec["type"] = o["wtype"]     # one of YOUR types (its layers)
        return rec

    def line_records(self, pts, closed: bool) -> list[dict]:
        """A run of straight walls (a room when ``closed``: its inside is
        the room's)."""
        if closed:
            side = 1 if _turn(pts, closed) >= 0 else -1
            side = -side if self.flip else side      # undone in _rec
        elif len(pts) >= 2:
            side = self.open_side(pts[0], pts[1])
        else:
            side = 1
        segs = list(zip(pts, pts[1:]))
        if closed and len(pts) >= 3:
            segs.append((pts[-1], pts[0]))
        out = []
        for k, (a, b) in enumerate(segs):
            if math.dist(a, b) > 1e-6:
                r = self._rec("line", side, a=list(a), b=list(b))
                r["id"] = f"~{k}"
                out.append(r)
        return out

    def _pick(self, ctx) -> list[float]:
        """The cursor; within END_SNAP_M of a wall's end (its line's, or a
        face's corner there), that point exactly."""
        p = super()._pick(ctx)
        got = _wall_at(self.existing, p, END_SNAP_M)
        return [round(got[4][0], 4), round(got[4][1], 4)] if got else p

    def _continue(self, rec: dict):
        """A curve starting or ending at a wall's end, along it, CONTINUES
        that wall: the same type, thickness and alignment, on the same
        side, so the faces run on with no step (his «S», 2026-11-01: the
        wall Outside, the curve Centre — half a thickness off, a crooked
        joint). Started on a face's CORNER, that face is its line: Outside
        or Inside as that face is, so every layer stays on its own side
        (the S's second curve came out inside out). The options bar is
        left as it is. → the wall it continues, or None."""
        if self.t_lane:
            return None
        for key, f in (("a", 0.0), ("b", 1.0)):
            got = _wall_at(self.existing, rec[key], 1e-3)
            if got is None:
                continue
            _d, w, end, role, _q = got
            try:
                ta = W.drawn(rec).tangent(f)
                tw = W.drawn(w).tangent(0.0 if end == "a" else 1.0)
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                continue
            dot = ta[0] * tw[0] + ta[1] * tw[1]
            if abs(dot) < CONTINUES_DOT:
                continue                 # a corner, not a continuation
            side = int(w.get("side", 1)) * (1 if dot > 0 else -1)
            rec["align"] = w.get("align", "centre") if role == "drawn" \
                else role
            rec["side"] = -side if self.flip else side
            # the same wall going on: its type and thickness too (a thinner
            # curve's inner face ran back into the wall, looking for it)
            rec["t"] = w.get("t", rec["t"])
            for k in ("type", "layers"):
                if w.get(k):
                    rec[k] = copy.deepcopy(w[k])
                else:
                    rec.pop(k, None)
            return w
        return None

    def _say_continues(self, p) -> None:
        """A click on a wall's end whose alignment is not the bar's: say
        the curve takes the wall's."""
        got = _wall_at(self.existing, p, 1e-3)
        if got is None:
            return
        w, role = got[1], got[3]
        o = self.opts()
        al = w.get("align", "centre") if role == "drawn" else role
        if al != o.get("align") or abs(float(w.get("t", 0)) - o["t"]) > 1e-6 \
                or (w.get("type") or None) != (o.get("wtype") or None):
            name = {"centre": "Centre", "inside": "Inside",
                    "outside": "Outside", "core_out": "Core outside"}.get(
                        al, al)
            compat.flash(self.viewport, f"On the end of {w.get('name', 'a '
                         'wall')}: a curve running on from it is the same "
                         f"wall — its type, {compat.fmt_len(w.get('t', 0))} "
                         f"and «{name}» — so the faces run on with no step",
                         6000)

    def preview(self):
        """[records] of what is being drawn now (with the cursor)."""
        return []

    def _done_records(self, recs) -> None:
        if not recs:
            return
        self._reset()
        self.viewport.update()
        self.on_done(recs)            # the tool stays out for the next

    def _wall_key(self, viewport, key) -> bool:
        """Tab: the other side (an open run, a curve)."""
        if key == Qt.Key_Tab and not compat.typed_value(viewport):
            self.flip = not self.flip
            viewport.update()
            return True
        return False

    # -- the walls, live (LINES only: see compat — fills are not safe) ---------------
    def draw_overlay(self, viewport, painter) -> None:
        self._draw_walls(viewport, painter)
        self._draw_lane(viewport, painter)
        super().draw_overlay(viewport, painter)

    def _draw_lane(self, viewport, painter) -> None:
        """The DXF lane under the cursor: its middle, dashed (tracing)."""
        la = getattr(self, "lane", None)
        if not la:
            return
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen
        a = compat.to_pixel(viewport, la["a"][0], la["a"][1], self.z)
        b = compat.to_pixel(viewport, la["b"][0], la["b"][1], self.z)
        if not a or not b:
            return
        painter.save()
        pen = QPen(QColor("#22a6c8"), 1.6)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(*a), QPointF(*b))
        painter.restore()

    def _draw_walls(self, viewport, painter) -> None:
        try:
            recs = self.preview()
            if not recs:
                return
            res = W.plan(list(self.existing()) + recs)
        except Exception:  # noqa: BLE001 — a preview never breaks the paint
            return
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(PREVIEW_INK), 2.0))
        for r in recs:
            for pc in res.get(r["id"], ()):
                for loop in [pc["outer"]] + list(pc["holes"]):
                    px = [compat.to_pixel(viewport, x, y, self.z)
                          for x, y in loop]
                    for a, b in zip(px, px[1:] + px[:1]):
                        if a and b:
                            painter.drawLine(QPointF(a[0], a[1]),
                                             QPointF(b[0], b[1]))
        painter.restore()


# ---- Point by point -----------------------------------------------------------------
class WallChainTool(_WallShape, _PlotTool):
    icon = "geopath"
    vcb_label = "Length"
    diagonal = True

    def __init__(self, on_done, on_cancelled, z: float, opts, existing):
        _PlotTool.__init__(self, on_done, on_cancelled)
        self._setup(z, opts, existing)

    def _reset(self) -> None:
        self.pts: list[list[float]] = []
        self.flip = False
        self.diag = None
        self.t_lane = None
        self.lane = None
        self._sync()

    def _traced(self, ctx, p):
        """Over a DXF: p moved to the middle of the lane it is in (a corner:
        where two lanes' middles cross) — else p."""
        if not self.lanes:
            self.lane = None
            return p
        from . import tracing
        raw = [ctx.world.x(), ctx.world.y()]
        got = tracing.snap(self.lanes, raw)
        if got is None:
            self.lane = None
            return p
        self.lane = got[1]
        return got[0]

    def _busy(self) -> bool:
        return bool(self.pts)

    def _anchor(self):
        return self.pts[-1] if self.pts else None

    def _align_sources(self):
        return list(self.pts) + _wall_ends(self.existing)

    def _sync(self) -> None:
        self._sync_protocol(self.pts, self.hover)

    def records(self, pts, closed: bool) -> list[dict]:
        return self.line_records(pts, closed)

    def preview(self):
        if not self.pts or self.hover is None:
            return []
        pts = list(self.pts)
        closing = len(pts) >= 3 and self.hover == list(pts[0])
        if not closing and math.dist(pts[-1], self.hover) > 1e-6:
            pts.append(self.hover)
        return self.line_records(pts, closing)

    def _near_first(self, p, ctx=None) -> bool:
        if len(self.pts) < 3:
            return False
        a = compat.to_pixel(self.viewport, self.pts[0][0], self.pts[0][1],
                            self.z)
        if a is None:
            return False
        here = []
        scr = getattr(ctx, "screen", None)
        if scr is not None:
            here.append((scr.x(), scr.y()))
        b = compat.to_pixel(self.viewport, p[0], p[1], self.z)
        if b is not None:
            here.append(b)
        return any(math.dist(a, h) <= CLOSE_PX for h in here)

    def _add(self, p) -> None:
        if self.pts and math.dist(self.pts[-1], p) <= 1e-3:
            return
        self.pts.append(p)
        self._sync()
        self._show_hint()

    def on_hover(self, ctx) -> None:
        super().on_hover(ctx)
        if self.lanes and self.hover is not None:
            self.hover = self._traced(ctx, self.hover)
            self._sync()
        if self._near_first(self.hover, ctx):
            self.hover = list(self.pts[0])
            self._sync()

    def on_click(self, ctx) -> None:
        p = self._traced(ctx, self._pick(ctx))
        if self._near_first(p, ctx):
            self._finish_run(closed=True)
            return
        if not self.pts and self.lane is not None:
            # a run started in a lane: its walls between the drawing's lines
            self.t_lane = self.lane["w"]
            compat.flash(self.viewport, "Over the DXF: the wall between its two "
                         f"lines — {compat.fmt_cm(self.t_lane, 1)}, centred",
                         4000)
        self._add(p)

    def on_double_click(self, ctx) -> None:
        if len(self.pts) >= 2:
            self._finish_run(closed=False)

    def on_value(self, viewport, value) -> bool:
        if not self.pts or not isinstance(value, (int, float)) \
                or self.hover is None:
            return False
        last = self.pts[-1]
        dx, dy = self.hover[0] - last[0], self.hover[1] - last[1]
        d = math.hypot(dx, dy)
        if d < 1e-9:
            return False
        L = float(value)
        self._add([round(last[0] + dx / d * L, 4),
                   round(last[1] + dy / d * L, 4)])
        return True

    def on_key(self, viewport, key, modifiers) -> bool:
        if compat.typed_value(viewport):
            return False             # Enter / Backspace belong to the value
        if self._wall_key(viewport, key):
            return True
        if key == Qt.Key_C:
            if len(self.pts) >= 3:
                self._finish_run(closed=True)
            else:
                compat.flash(viewport, "Three points at least to close", 3000)
            return True
        if key in (Qt.Key_Return, Qt.Key_Enter) and len(self.pts) >= 2:
            self._finish_run(closed=False)
            return True
        if key == Qt.Key_Backspace and self.pts:
            self.pts.pop()
            self._sync()
            viewport.update()
            return True
        return False

    def _finish_run(self, closed: bool) -> None:
        self._done_records(self.line_records([list(p) for p in self.pts],
                                             closed))

    def rubber_band_lines(self):
        segs = [(self._P(a), self._P(b)) for a, b in zip(self.pts,
                                                          self.pts[1:])]
        if self.pts and self.hover is not None:
            segs.append((self._P(self.pts[-1]), self._P(self.hover)))
        return segs

    def value_label(self):
        if not self.pts or self.hover is None:
            return None
        return (compat.fmt_len(math.dist(self.pts[-1], self.hover)), None)

    def status_clause(self) -> str:
        if not self.pts and self.lanes:
            return ("Wall: click the first point — over the DXF, between a "
                    "wall's two lines: it goes in their middle, as wide as "
                    "they are  ·  Esc = done")
        if not self.pts:
            return "Wall: click the first point  ·  Esc = done"
        tail = ("  ·  Tab = other side  ·  Backspace = undo point  ·  "
                "Esc = drop")
        if len(self.pts) < 3:
            return ("Wall: click the next point, or type a length + Enter  "
                    "·  Enter / double-click = end here" + tail)
        return ("Wall: next point  ·  C or the first point = close  ·  "
                "Enter / double-click = end here" + tail)

    def _labels(self):
        if not self.pts or self.hover is None:
            return []
        return [((self.pts[-1], self.hover),
                 _m(math.dist(self.pts[-1], self.hover)), None)]


# ---- The three rectangles: the plot's tools, making a room of walls ---------------
class _WallRect(_WallShape):
    """Mixed in before a plottools rectangle: what it finishes becomes
    four walls; what it shows becomes the walls, live."""

    def _finish(self, corners) -> None:
        self._done_records(self.line_records([list(c) for c in corners],
                                             True))

    def preview(self):
        segs = self.rubber_band_lines()
        if len(segs) == 4:
            return self.line_records([[s[0].x(), s[0].y()] for s in segs],
                                     True)
        if len(segs) == 1:                   # the rotated one's first side
            a, b = segs[0]
            return self.line_records([[a.x(), a.y()], [b.x(), b.y()]], False)
        return []

    def on_key(self, viewport, key, modifiers) -> bool:
        if self._wall_key(viewport, key):
            return True
        return super().on_key(viewport, key, modifiers)


def _rect_tool(base):
    class T(_WallRect, base):
        noun = "Walls"

        def __init__(self, on_done, on_cancelled, z, opts, existing):
            base.__init__(self, on_done, on_cancelled)
            self._setup(z, opts, existing)
    T.__name__ = "Wall" + base.__name__.replace("Plot", "")
    return T


WallRectTool = _rect_tool(plottools.PlotRectTool)
WallCentreRectTool = _rect_tool(plottools.PlotCentreRectTool)
WallRotRectTool = _rect_tool(plottools.PlotRotRectTool)


# ---- Curves -----------------------------------------------------------------------
#: the bulge sticks to a tangent / half circle within this (screen px)
BULGE_PX = 14.0
TANGENT_INK = "#0a84ff"
#: the centre tool's sweep sticks to 90° / 180° / 270° within this
SWEEP_PULL_DEG = 3.0
#: the centre's pull onto the line square to a wall's end: only for ends
#: this near the cursor, and that far along the line at most
PERP_REACH_PX, PERP_REACH_M = 320.0, 20.0


def _arc_side(a, m, b) -> int:
    """A curved wall's inside is its hollow (the centre's side)."""
    return 1 if (m[0] - a[0]) * (b[1] - m[1]) - (m[1] - a[1]) \
        * (b[0] - m[0]) > 0 else -1


def _wall_ends(existing) -> list:
    """The ends of the walls already on the level (a round one has none):
    what the cursor lines up with."""
    ends = []
    for w in existing():
        if w.get("kind", "line") != "circle":
            ends += [w["a"], w["b"]]
    return ends


def _all_end_ways(existing) -> list:
    """[(point, unit (dx, dy))]: every wall end on the level — its line's
    end and its faces' corners there — with the way the wall would run on
    past it: a curve leaving the point this way meets the wall with no
    kink."""
    out = []
    for w in existing():
        out += [(q, way) for _e, _r, q, way in _end_points(w)]
    return out


def _end_ways(existing, p, tol: float = 1e-3) -> list:
    """[unit (dx, dy)]: those of the walls ending at p."""
    return [t for e, t in _all_end_ways(existing) if math.dist(e, p) <= tol]


def _tangent_mid(a, u, b):
    """The middle of the arc that leaves a along u (unit) and ends at b —
    None when b lies on that line (no arc)."""
    n = (-u[1], u[0])
    ab = (a[0] - b[0], a[1] - b[1])
    den = 2.0 * (n[0] * ab[0] + n[1] * ab[1])
    if abs(den) < 1e-9:
        return None
    s = -(ab[0] ** 2 + ab[1] ** 2) / den      # the centre: a + n·s
    C = (a[0] + n[0] * s, a[1] + n[1] * s)
    th_a = math.atan2(a[1] - C[1], a[0] - C[0])
    th_b = math.atan2(b[1] - C[1], b[0] - C[0])
    if s > 0:                                # the centre on the left: ccw
        sweep = (th_b - th_a) % (2 * math.pi)
    else:
        sweep = -((th_a - th_b) % (2 * math.pi))
    th = th_a + sweep / 2.0
    return [round(C[0] + abs(s) * math.cos(th), 4),
            round(C[1] + abs(s) * math.sin(th), 4)]


def _draw_ray(viewport, painter, z, p, d, ink, length: float = 4.0) -> None:
    """A dashed guide from p along d (both ways), ``length`` m each side."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QPen
    a = compat.to_pixel(viewport, p[0] - d[0] * length, p[1] - d[1] * length,
                        z)
    b = compat.to_pixel(viewport, p[0] + d[0] * length, p[1] + d[1] * length,
                        z)
    if not a or not b:
        return
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(ink), 1.4, Qt.DashLine))
    painter.drawLine(QPointF(*a), QPointF(*b))
    painter.restore()


def _screen(tool, ctx, p):
    """The cursor on screen (px), or p's pixel."""
    scr = getattr(ctx, "screen", None)
    if scr is not None:
        return (scr.x(), scr.y())
    return compat.to_pixel(tool.viewport, p[0], p[1], tool.z)


class WallArc3Tool(_WallShape, _PlotTool):
    """Start, end, then a point on the curve (the bulge)."""
    icon = "arc3"
    vcb_label = "Length"
    bulge_hit = None
    _bulge_rays = ()
    _bulge_m = _bulge_c = None       # held: the curve's middle, its centre

    def __init__(self, on_done, on_cancelled, z, opts, existing):
        _PlotTool.__init__(self, on_done, on_cancelled)
        self._setup(z, opts, existing)

    def _reset(self) -> None:
        self.a = self.b = None
        self.flip = False
        self.diag = None
        self.bulge_hit = None            # "Tangent" | "Half circle" | None
        self._bulge_rays = []            # [(end, way)] drawn as guides
        self._bulge_m = self._bulge_c = None
        self._sync()

    def _busy(self) -> bool:
        return self.a is not None

    def _anchor(self):
        return self.b if self.b is not None else self.a

    def _align_sources(self):
        """The red / green guides of the straight wall (his ask, 2026-11-01:
        the end of a curve could not be lined up with its start)."""
        return [p for p in (self.a, self.b) if p is not None] \
            + _wall_ends(self.existing)

    def _bulges(self) -> list:
        """[(name, bulge point, [(end, way)])]: the curve tangent to a wall
        ending at its start or its end, and the half circle."""
        a, b = self.a, self.b
        out = []
        for t in _end_ways(self.existing, a):
            m = _tangent_mid(a, t, b)
            if m is not None:
                out.append(("Tangent", m, [(a, t)]))
        for t in _end_ways(self.existing, b):
            m = _tangent_mid(b, t, a)
            if m is not None:
                out.append(("Tangent", m, [(b, t)]))
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        h = math.dist(a, b) / 2.0
        if h > 1e-6:
            n = (-(b[1] - a[1]) / (2 * h), (b[0] - a[0]) / (2 * h))
            for s in (1.0, -1.0):
                out.append(("Half circle", [round(mid[0] + n[0] * h * s, 4),
                                            round(mid[1] + n[1] * h * s, 4)],
                            []))
        # the same point twice (tangent at both ends, a half circle…): one
        merged = []
        for name, m, rays in out:
            for k, (n0, m0, r0) in enumerate(merged):
                if math.dist(m, m0) <= 1e-3:
                    names = n0 if name in n0 else f"{n0} · {name.lower()}"
                    merged[k] = (names, m0, r0 + rays)
                    break
            else:
                merged.append((name, m, list(rays)))
        return merged

    def _pick(self, ctx) -> list[float]:
        """The bulge sticks to a tangent / half circle ANYWHERE along that
        curve, not only at its middle: every point on it is the same curve
        (his screen, 2026-11-01: the cursor sat on the half circle, 35 px
        from its middle, and nothing held it)."""
        p = super()._pick(ctx)
        self.bulge_hit = None
        self._bulge_rays = []
        self._bulge_m = self._bulge_c = None
        if self.a is None or self.b is None or self.viewport is None:
            return p
        from .plottools import _xy
        raw = _xy(ctx)
        here = _screen(self, ctx, raw)
        if not here:
            return p
        a, b = self.a, self.b
        ab = (b[0] - a[0], b[1] - a[1])

        def side(q):
            return ab[0] * (q[1] - a[1]) - ab[1] * (q[0] - a[0])
        best = None
        for name, m, rays in self._bulges():
            got = W._circle3(tuple(a), tuple(m), tuple(b))
            if got is None:
                continue
            C, R = got
            v = (raw[0] - C[0], raw[1] - C[1])
            L = math.hypot(*v)
            if L < 1e-9:
                continue
            q = (C[0] + v[0] / L * R, C[1] + v[1] / L * R)
            if side(q) * side(m) <= 0:
                continue                 # the other side of the chord
            px = compat.to_pixel(self.viewport, q[0], q[1], self.z)
            if px:
                d = math.dist(here, px)
                if d <= BULGE_PX and (best is None or d < best[0]):
                    best = (d, name, m, rays, q, C)
        if best is None:
            return p
        _d, self.bulge_hit, self._bulge_m, self._bulge_rays, q, C = best
        self._bulge_c = C
        self._aligned = []
        self._guide_hit = "cross"            # the loud ring: it holds here
        return [round(q[0], 4), round(q[1], 4)]

    def draw_overlay(self, viewport, painter) -> None:
        for p, d in self._bulge_rays:
            _draw_ray(viewport, painter, self.z, p, d, TANGENT_INK)
        if self.bulge_hit and self._bulge_c is not None and self.hover:
            self._draw_hold(viewport, painter)
        super().draw_overlay(viewport, painter)

    def _draw_hold(self, viewport, painter) -> None:
        """Held on a tangent / half circle: its centre, the radius to the
        cursor dashed, and the name by the cursor — seen without looking
        down at the measure box."""
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QColor, QFont, QPen
        c = compat.to_pixel(viewport, self._bulge_c[0], self._bulge_c[1],
                            self.z)
        h = compat.to_pixel(viewport, self.hover[0], self.hover[1], self.z)
        if not c or not h:
            return
        ink = QColor(TANGENT_INK)
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        painter.setPen(QPen(ink, 1.4, Qt.DashLine))
        painter.drawLine(QPointF(*c), QPointF(*h))
        painter.setPen(QPen(ink, 1.6))
        painter.drawLine(QPointF(c[0] - 6, c[1]), QPointF(c[0] + 6, c[1]))
        painter.drawLine(QPointF(c[0], c[1] - 6), QPointF(c[0], c[1] + 6))
        font = QFont(painter.font())
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        text = self.bulge_hit
        w, ht = fm.horizontalAdvance(text) + 14, fm.height() + 6
        r = QRectF(h[0] + 18, h[1] + 14, w, ht)
        painter.setPen(Qt.NoPen)
        painter.setBrush(ink)
        painter.drawRoundedRect(r, 4, 4)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(r, Qt.AlignCenter, text)
        painter.restore()

    def _sync(self) -> None:
        pts = [p for p in (self.a, self.b) if p is not None]
        self._sync_protocol(pts, self.hover)
        self.chain_first_point = None

    def _arc(self, m):
        if self.bulge_hit and self._bulge_m is not None:
            m = self._bulge_m            # held: the curve's exact middle
        if W._circle3(tuple(self.a), tuple(m), tuple(self.b)) is None:
            return self.line_records([self.a, self.b], False)
        r = self._rec("arc", _arc_side(self.a, m, self.b), a=list(self.a),
                      b=list(self.b), m=list(m))
        self._continue(r)
        return [r]

    def preview(self):
        if self.a is None or self.hover is None:
            return []
        if self.b is None:
            return self.line_records([self.a, self.hover], False)
        return self._arc(self.hover)

    def on_click(self, ctx) -> None:
        p = self._pick(ctx)
        if self.a is None:
            self.a = p
            self._say_continues(p)
        elif self.b is None:
            if math.dist(self.a, p) <= 1e-3:
                return
            self.b = p
            self._say_continues(p)
        else:
            self._done_records(self._arc(p))
            return
        self._sync()
        self._show_hint()

    def on_value(self, viewport, value) -> bool:
        """The chord's length (start → end) along the cursor's way."""
        if self.a is None or self.b is not None or self.hover is None \
                or not isinstance(value, (int, float)):
            return False
        dx, dy = self.hover[0] - self.a[0], self.hover[1] - self.a[1]
        d = math.hypot(dx, dy)
        if d < 1e-9:
            return False
        L = abs(float(value))
        self.b = [round(self.a[0] + dx / d * L, 4),
                  round(self.a[1] + dy / d * L, 4)]
        self._sync()
        self._show_hint()
        return True

    def on_key(self, viewport, key, modifiers) -> bool:
        if self._wall_key(viewport, key):
            return True
        if key == Qt.Key_Backspace and not compat.typed_value(viewport):
            if self.b is not None:
                self.b = None
            elif self.a is not None:
                self.a = None
            self._sync()
            viewport.update()
            return True
        return super().on_key(viewport, key, modifiers)

    def rubber_band_lines(self):
        if self.a is None or self.hover is None:
            return []
        if self.b is None:
            return [(self._P(self.a), self._P(self.hover))]
        return [(self._P(self.a), self._P(self.b))]

    def value_label(self):
        if self.a is None or self.hover is None:
            return None
        if self.b is None:
            return (compat.fmt_len(math.dist(self.a, self.hover)), None)
        got = W._circle3(tuple(self.a), tuple(self.hover), tuple(self.b))
        text = f"R {compat.fmt_len(got[1])}" if got else "straight"
        if self.bulge_hit:
            text += f"  ·  {self.bulge_hit}"
        return (text, None)

    def status_clause(self) -> str:
        if self.a is None:
            return "Curved wall: click where it starts  ·  Esc = done"
        if self.b is None:
            return ("Curved wall: click where it ends (it lines up with the "
                    "start and the walls' ends), or type the length + Enter  "
                    "·  Esc = drop")
        return ("Curved wall: click a point on the curve (how much it "
                "bulges) — it sticks where the curve meets a wall with no "
                "kink, and to a half circle  ·  Tab = other side  ·  "
                "Esc = drop")


class WallArcCentreTool(_WallShape, _PlotTool):
    """Centre, start (the radius), end — the way the mouse turns, also
    past a half circle; a typed number = the angle in degrees."""
    icon = "center_arc"
    vcb_label = "Angle"
    _perp = None                     # (wall end, way) the centre sits on

    def __init__(self, on_done, on_cancelled, z, opts, existing):
        _PlotTool.__init__(self, on_done, on_cancelled)
        self._setup(z, opts, existing)

    def _reset(self) -> None:
        self.c = self.a = None
        self.sweep = 0.0
        self._last = None
        self._perp = None
        self.flip = False
        self.diag = None
        self._sync()

    def _busy(self) -> bool:
        return self.c is not None

    def _anchor(self):
        return self.c

    def _align_sources(self):
        return [p for p in (self.c, self.a) if p is not None] \
            + _wall_ends(self.existing)

    def _pick(self, ctx) -> list[float]:
        """The centre sticks to the line square to a wall at its end: a
        curve started at that end then leaves the wall with no kink."""
        p = super()._pick(ctx)
        self._perp = None
        if self.c is not None or self.viewport is None:
            return p
        from .plottools import GUIDE_LINE_PX, _xy
        raw = _xy(ctx)               # the cursor itself, not a pulled point
        here = _screen(self, ctx, raw)
        if not here:
            return p
        best = None
        for e, t in _all_end_ways(self.existing):
            n = (-t[1], t[0])
            s = (raw[0] - e[0]) * n[0] + (raw[1] - e[1]) * n[1]
            if abs(s) < 1e-3 or abs(s) > PERP_REACH_M:
                continue                     # on the end itself: the host's
            ep = compat.to_pixel(self.viewport, e[0], e[1], self.z)
            if not ep or math.dist(ep, here) > PERP_REACH_PX:
                continue                     # only the ends near the cursor
            q = [round(e[0] + n[0] * s, 4), round(e[1] + n[1] * s, 4)]
            px = compat.to_pixel(self.viewport, q[0], q[1], self.z)
            if px:
                d = math.dist(here, px)
                if d <= GUIDE_LINE_PX and (best is None or d < best[0]):
                    best = (d, q, (e, n))
        if best is None:
            return p
        # it wins over a red / green alignment: two ends a hair apart (his
        # «S», 1.2 mm) must not put the centre off the wall's square
        self._perp = best[2]
        self._aligned = []
        self._guide_hit = "line"
        return best[1]

    def _turned(self) -> float:
        """The sweep, stuck to 90° / 180° / 270° when near one."""
        q = math.pi / 2.0
        k = round(self.sweep / q)
        if 0 < abs(k) < 4 and abs(self.sweep - k * q) \
                <= math.radians(SWEEP_PULL_DEG):
            return k * q
        return self.sweep

    def draw_overlay(self, viewport, painter) -> None:
        if self._perp is not None:
            _draw_ray(viewport, painter, self.z, self._perp[0], self._perp[1],
                      TANGENT_INK, length=max(4.0, math.dist(
                          self._perp[0], self.hover or self._perp[0]) * 1.5))
        super().draw_overlay(viewport, painter)

    def _sync(self) -> None:
        pts = [p for p in (self.c, self.a) if p is not None]
        self._sync_protocol(pts, self.hover)
        self.chain_first_point = None

    def _ang(self, p) -> float:
        return math.atan2(p[1] - self.c[1], p[0] - self.c[0])

    def on_hover(self, ctx) -> None:
        super().on_hover(ctx)
        if self.a is not None and self.hover is not None:
            now = self._ang(self.hover)
            if self._last is not None:
                d = (now - self._last + math.pi) % (2 * math.pi) - math.pi
                self.sweep = max(-2 * math.pi + 0.02,
                                 min(2 * math.pi - 0.02, self.sweep + d))
            self._last = now

    def _arc(self, sweep: float):
        if abs(sweep) < 1e-3:
            return []
        r = math.dist(self.c, self.a)
        t0 = self._ang(self.a)

        def at(t):
            return [self.c[0] + r * math.cos(t), self.c[1] + r * math.sin(t)]
        a, m, b = at(t0), at(t0 + sweep / 2), at(t0 + sweep)
        r = self._rec("arc", 1 if sweep > 0 else -1, a=a, b=b, m=m)
        self._continue(r)
        return [r]

    def preview(self):
        if self.c is None or self.hover is None:
            return []
        if self.a is None:
            return []
        return self._arc(self._turned())

    def on_click(self, ctx) -> None:
        p = self._pick(ctx)
        if self.c is None:
            self.c = p
        elif self.a is None:
            if math.dist(self.c, p) <= 1e-3:
                return
            self.a = p
            self.sweep = 0.0
            self._last = self._ang(p)
            self._say_continues(p)
        else:
            self._done_records(self._arc(self._turned()))
            return
        self._sync()
        self._show_hint()

    def on_value(self, viewport, value) -> bool:
        if self.a is None or not isinstance(value, (int, float)):
            return False
        deg = max(-359.0, min(359.0, float(value)))
        sign = -1.0 if self.sweep < 0 else 1.0
        self._done_records(self._arc(math.radians(abs(deg)) * sign))
        return True

    def on_key(self, viewport, key, modifiers) -> bool:
        if self._wall_key(viewport, key):
            return True
        return super().on_key(viewport, key, modifiers)

    def rubber_band_lines(self):
        if self.c is None or self.hover is None:
            return []
        if self.a is None:
            return [(self._P(self.c), self._P(self.hover))]
        return [(self._P(self.c), self._P(self.a))]

    def value_label(self):
        if self.c is None or self.hover is None:
            return None
        if self.a is None:
            return (f"R {compat.fmt_len(math.dist(self.c, self.hover))}", None)
        return (f"{math.degrees(abs(self._turned())):.1f}°", None)

    def status_clause(self) -> str:
        if self.c is None:
            return ("Curved wall: click its centre — it sticks square to a "
                    "wall's end, for a curve with no kink  ·  Esc = done")
        if self.a is None:
            return "Curved wall: click where it starts (the radius)"
        return ("Curved wall: turn the mouse round and click where it ends, "
                "or type the angle (°) + Enter  ·  Tab = other side")


class WallCircleTool(_WallShape, _PlotTool):
    """A round wall: centre, then the radius (clicked or typed)."""
    icon = "circle"
    vcb_label = "Radius"

    def __init__(self, on_done, on_cancelled, z, opts, existing):
        _PlotTool.__init__(self, on_done, on_cancelled)
        self._setup(z, opts, existing)

    def _reset(self) -> None:
        self.c = None
        self.diag = None
        self._sync()

    def _busy(self) -> bool:
        return self.c is not None

    def _anchor(self):
        return self.c

    def _sync(self) -> None:
        self._sync_protocol([self.c] if self.c else [], self.hover)
        self.chain_first_point = None

    def _ring(self, r: float):
        if r < 1e-3:
            return []
        rec = self._rec("circle", 1, c=list(self.c), r=r)
        rec["side"] = 1
        return [rec]

    def preview(self):
        if self.c is None or self.hover is None:
            return []
        return self._ring(math.dist(self.c, self.hover))

    def on_click(self, ctx) -> None:
        p = self._pick(ctx)
        if self.c is None:
            self.c = p
            self._sync()
            self._show_hint()
            return
        self._done_records(self._ring(math.dist(self.c, p)))

    def on_value(self, viewport, value) -> bool:
        if self.c is None or not isinstance(value, (int, float)):
            return False
        self._done_records(self._ring(abs(float(value))))
        return True

    def rubber_band_lines(self):
        if self.c is None or self.hover is None:
            return []
        return [(self._P(self.c), self._P(self.hover))]

    def value_label(self):
        if self.c is None or self.hover is None:
            return None
        r = math.dist(self.c, self.hover)
        return (f"R {compat.fmt_len(r)}   (Ø {compat.fmt_len(2 * r)})", None)

    def status_clause(self) -> str:
        return ("Round wall: click its centre  ·  Esc = done"
                if self.c is None else
                "Round wall: click the radius, or type it + Enter  ·  "
                "Esc = drop")


#: the options bar's shapes → their tools
class OnFloor(P3.OnPlane):
    """Mixin (first among the bases): a wall tool drawing in 3D TOO
    (PLANO_PAREDE_3D.md, his OK 31/10). Picked, it goes to the plan as
    ever; out of the plan it is NOT dropped — it draws on the ACTIVE level's
    floor (``z``), wherever the ray meets the model (his condition: «on
    level 5, it lands on level 5»); a grazing ray refuses and says why."""
    stays_in_view = False           # sent to the plan when picked
    draws_in_3d = True              # kept when the plan is left

    def _traced(self, ctx, p):
        # the DXF's lanes: from the plan only (in 3D the raw cursor is
        # wherever the ray hit the model, not on the floor)
        if P3.in_3d(self.viewport):
            self.lane = None
            return p
        return super()._traced(ctx, p)


def _on_floor(cls):
    # (its module said: compat.ours knows ArchXQ's tools by it — made by
    # type() under ABCMeta it read «abc»)
    return type(cls.__name__, (OnFloor, cls),
                {"__doc__": cls.__doc__, "__module__": cls.__module__})


#: the options bar's shapes — each drawing in the plan AND in 3D (the
#: plain classes stay as they are: the beam is a chain of its own)
TOOLS = {k: _on_floor(c) for k, c in (
    ("chain", WallChainTool), ("rect", WallRectTool),
    ("rect_c", WallCentreRectTool), ("rect_r", WallRotRectTool),
    ("arc3", WallArc3Tool), ("arc_c", WallArcCentreTool),
    ("circle", WallCircleTool))}
