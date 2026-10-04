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

import math

from PySide6.QtCore import Qt

from . import compat, plottools, walls as W
from .plottools import CLOSE_PX, _PlotTool, _m

PREVIEW_INK = "#e8742c"
TOOL_NAME = "ArchXQ wall"          # ui knows the wall tools by this name


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

    def _rec(self, kind: str, side: int, **geo) -> dict:
        o = self.opts()
        return dict(geo, kind=kind, t=o["t"], align=o["align"],
                    side=-side if self.flip else side, id=f"~{id(geo)}",
                    name="~")

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
        super().draw_overlay(viewport, painter)

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
        self._sync()

    def _busy(self) -> bool:
        return bool(self.pts)

    def _anchor(self):
        return self.pts[-1] if self.pts else None

    def _align_sources(self):
        ends = []
        for w in self.existing():
            if w.get("kind", "line") != "circle":
                ends += [w["a"], w["b"]]
        return list(self.pts) + ends

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
        if self._near_first(self.hover, ctx):
            self.hover = list(self.pts[0])
            self._sync()

    def on_click(self, ctx) -> None:
        p = self._pick(ctx)
        if self._near_first(p, ctx):
            self._finish_run(closed=True)
            return
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
        return (f"{math.dist(self.pts[-1], self.hover):.2f} m", None)

    def status_clause(self) -> str:
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
def _arc_side(a, m, b) -> int:
    """A curved wall's inside is its hollow (the centre's side)."""
    return 1 if (m[0] - a[0]) * (b[1] - m[1]) - (m[1] - a[1]) \
        * (b[0] - m[0]) > 0 else -1


class WallArc3Tool(_WallShape, _PlotTool):
    """Start, end, then a point on the curve (the bulge)."""
    icon = "arc3"
    vcb_label = "Length"

    def __init__(self, on_done, on_cancelled, z, opts, existing):
        _PlotTool.__init__(self, on_done, on_cancelled)
        self._setup(z, opts, existing)

    def _reset(self) -> None:
        self.a = self.b = None
        self.flip = False
        self.diag = None
        self._sync()

    def _busy(self) -> bool:
        return self.a is not None

    def _anchor(self):
        return self.b if self.b is not None else self.a

    def _sync(self) -> None:
        pts = [p for p in (self.a, self.b) if p is not None]
        self._sync_protocol(pts, self.hover)
        self.chain_first_point = None

    def _arc(self, m):
        if W._circle3(tuple(self.a), tuple(m), tuple(self.b)) is None:
            return self.line_records([self.a, self.b], False)
        r = self._rec("arc", _arc_side(self.a, m, self.b), a=list(self.a),
                      b=list(self.b), m=list(m))
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
        elif self.b is None:
            if math.dist(self.a, p) <= 1e-3:
                return
            self.b = p
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
            return (f"{math.dist(self.a, self.hover):.2f} m", None)
        got = W._circle3(tuple(self.a), tuple(self.hover), tuple(self.b))
        return ((f"R {got[1]:.2f} m" if got else "straight"), None)

    def status_clause(self) -> str:
        if self.a is None:
            return "Curved wall: click where it starts  ·  Esc = done"
        if self.b is None:
            return ("Curved wall: click where it ends, or type the length + "
                    "Enter  ·  Esc = drop")
        return ("Curved wall: click a point on the curve (how much it "
                "bulges)  ·  Tab = other side  ·  Esc = drop")


class WallArcCentreTool(_WallShape, _PlotTool):
    """Centre, start (the radius), end — the way the mouse turns, also
    past a half circle; a typed number = the angle in degrees."""
    icon = "center_arc"
    vcb_label = "Angle"

    def __init__(self, on_done, on_cancelled, z, opts, existing):
        _PlotTool.__init__(self, on_done, on_cancelled)
        self._setup(z, opts, existing)

    def _reset(self) -> None:
        self.c = self.a = None
        self.sweep = 0.0
        self._last = None
        self.flip = False
        self.diag = None
        self._sync()

    def _busy(self) -> bool:
        return self.c is not None

    def _anchor(self):
        return self.c

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
        return [self._rec("arc", 1 if sweep > 0 else -1, a=a, b=b, m=m)]

    def preview(self):
        if self.c is None or self.hover is None:
            return []
        if self.a is None:
            return []
        return self._arc(self.sweep)

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
        else:
            self._done_records(self._arc(self.sweep))
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
            return (f"R {math.dist(self.c, self.hover):.2f} m", None)
        return (f"{math.degrees(abs(self.sweep)):.1f}°", None)

    def status_clause(self) -> str:
        if self.c is None:
            return "Curved wall: click its centre  ·  Esc = done"
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
        return (f"R {r:.2f} m   (Ø {2 * r:.2f} m)", None)

    def status_clause(self) -> str:
        return ("Round wall: click its centre  ·  Esc = done"
                if self.c is None else
                "Round wall: click the radius, or type it + Enter  ·  "
                "Esc = drop")


#: the options bar's shapes → their tools
TOOLS = {"chain": WallChainTool, "rect": WallRectTool,
         "rect_c": WallCentreRectTool, "rect_r": WallRotRectTool,
         "arc3": WallArc3Tool, "arc_c": WallArcCentreTool,
         "circle": WallCircleTool}
