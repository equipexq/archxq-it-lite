# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""ROOM SEPARATORS — a line that splits two rooms with no wall between
them (an open living room and kitchen), as Revit's / ArchiCAD's (his go
to ``PLANO_CAMADAS_LAJE.md``, D5, 2026-10-23).

Nothing in 3D: drawn point by point on a level, dashed in the plan. The
rooms are found as if it were a wall (``spaces.closers``) — each side its
own name, area and floor (floor per room).

    doc["separators"] = [{"id", "level", "pts": [[x, y], …]}]
"""
from __future__ import annotations

import math
import uuid

from PySide6.QtCore import Qt
from tools.base import Tool

from . import compat

try:
    from .guards import GuardTool
except ImportError:      # the Lite has no guards.py: the separators are
    GuardTool = Tool     # still drawn (a Pro file), their tool is the Pro's

#: px — a click this close to one picks it (Delete)
PICK_PX = 10
INK = "#4a5058"
RED = "#e5484d"


# ---- the record (cleaned when read: model._separators) ------------------------------
def of_level(doc: dict, level_id: str) -> list[dict]:
    return [s for s in doc.get("separators") or []
            if s.get("level") == level_id]


def add(doc: dict, level_id: str, pts) -> dict:
    """``doc`` with a new separator (its id made here)."""
    new = {"id": uuid.uuid4().hex[:8], "level": level_id,
           "pts": [[round(p[0], 4), round(p[1], 4)] for p in pts]}
    return dict(doc, separators=list(doc.get("separators") or []) + [new])


def remove(doc: dict, sid: str) -> dict:
    return dict(doc, separators=[s for s in doc.get("separators") or []
                                 if s["id"] != sid])


def _seg_dist(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx
                                              + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def nearest(seps: list[dict], p, reach: float):
    """The separator nearest ``p`` (within ``reach`` m), or None."""
    best = None
    for s in seps:
        d = min(_seg_dist(p, a, b) for a, b in zip(s["pts"], s["pts"][1:]))
        if d <= reach and (best is None or d < best[0]):
            best = (d, s)
    return best[1] if best else None


# ---- the plan ----------------------------------------------------------------------
def draw(viewport, painter, seps: list[dict], z: float, hot=None) -> None:
    """Dashed, thin — a line between rooms, not a wall (``hot``: red)."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QPen
    if not seps:
        return
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    for s in seps:
        pen = QPen(QColor(RED if s["id"] == hot else INK),
                   2.4 if s["id"] == hot else 1.2)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        px = [compat.to_pixel(viewport, x, y, z) for x, y in s["pts"]]
        for a, b in zip(px, px[1:]):
            if a and b:
                painter.drawLine(QPointF(*a), QPointF(*b))
    painter.restore()


# ---- drawing one -------------------------------------------------------------------
class SeparatorTool(GuardTool):
    """Point by point, as the walls: click point after point, Enter /
    double-click ends it, C closes it. ``on_done(pts, closed)``."""
    name = "ArchXQ room separator"
    axq_element = "separator"
    noun = "Room separator"

    #: (the options a guard's tool reads: a hairline on its line)
    OPTS = {"t": 0.02, "kind": "wall", "insert": "centre", "align": "centre"}

    def __init__(self, on_done, on_cancelled, z: float, existing) -> None:
        super().__init__(on_done, on_cancelled, z, lambda: self.OPTS,
                         existing)

    def _width(self) -> float:
        return float(self.OPTS["t"])

    def _centre(self, pts, closed):
        return pts

    def status_clause(self) -> str:
        s = super().status_clause()
        return s.replace("Low wall:", "Room separator:")


class SeparatorEraseTool(Tool):
    """Delete a separator: the one under the cursor shows in red, a click
    takes it (one Ctrl+Z). Stays out for the next; Esc = done."""
    name = "ArchXQ delete room separator"
    icon = "eraser"
    uses_snap = False
    creates = False

    def __init__(self, get_seps, z: float, on_delete, on_cancelled) -> None:
        super().__init__()
        self.get_seps = get_seps
        self.z = z
        self.on_delete = on_delete
        self.on_cancelled = on_cancelled
        self.viewport = None
        self.hot = None

    def on_activate(self, viewport) -> None:
        self.viewport = viewport
        compat.flash(viewport, "Delete room separator: click the dashed line "
                     "·  Esc = done", 600000)

    def on_deactivate(self, viewport) -> None:
        compat.flash(viewport, "", 1)

    def drag_plane(self, viewport):
        # the cursor read on the level's floor
        return compat.vec(0, 0, self.z), compat.vec(0, 0, 1)

    def _under(self, ctx):
        w = getattr(ctx, "world", None)
        if w is None or self.viewport is None:
            return None
        # PICK_PX in metres at the cursor
        a = compat.to_pixel(self.viewport, w.x(), w.y(), self.z)
        b = compat.to_pixel(self.viewport, w.x() + 1.0, w.y(), self.z)
        per_m = math.dist(a, b) if a and b else 50.0
        return nearest(self.get_seps(), (w.x(), w.y()),
                       PICK_PX / max(per_m, 1e-6))

    def on_hover(self, ctx) -> None:
        s = self._under(ctx)
        hot = s["id"] if s else None
        if hot != self.hot:
            self.hot = hot
            self.viewport.update()

    def on_click(self, ctx) -> None:
        s = self._under(ctx)
        if s is None:
            compat.flash(self.viewport, "Not on a room separator — click its "
                         "dashed line", 3000)
            return
        self.hot = None
        self.on_delete(s["id"])

    def on_cancel(self, viewport) -> None:
        if self.on_cancelled:
            self.on_cancelled()

    def draw_overlay(self, viewport, painter) -> None:
        draw(viewport, painter, self.get_seps(), self.z, self.hot)


# ---- drawn as a SHAPE: a rectangle / a circle (0.17.0 — his ask, 2026-10-26) --------
#: sides of a round separator: its area within 0.3 % (24 sides: 1.1 % short
#: — seen in the area schedule)
CIRCLE_SIDES = 48


def area(pts) -> float:
    """The area (m²) a closed outline holds — either way round."""
    return abs(0.5 * sum(p[0] * q[1] - q[0] * p[1]
                         for p, q in zip(pts, list(pts[1:]) + [pts[0]])))


def too_small(pts) -> bool:
    """Less than the smallest room: it would make none."""
    from .spaces import MIN_AREA
    return area(pts) < MIN_AREA


def shape_tool(base):
    """One of the plot's outline tools (a rectangle, from its centre,
    rotated, a circle) drawing a CLOSED room separator on the level's
    floor — a zone inside a room (a dining area, a round lounge): an
    island, its own room. ``on_done(pts, True)``."""
    class T(base):
        name = "ArchXQ room separator"
        axq_element = "separator"
        noun = "Room separator"
        segments = staticmethod(lambda: CIRCLE_SIDES)

        def __init__(self, on_done, on_cancelled, z):
            base.__init__(self, on_done, on_cancelled)
            self.z = z

        def _finish(self, corners) -> None:
            corners = [list(c) for c in corners]
            if too_small(corners):
                compat.flash(self.viewport, "Too small for a room", 4000)
                return
            self._reset()
            self.viewport.update()
            self.on_done(corners, True)      # the tool stays for the next
    T.__name__ = "Separator" + base.__name__.replace("Plot", "")
    return T


def _shape_tools() -> dict:
    from . import plottools as P
    return {"rect": shape_tool(P.PlotRectTool),
            "rect_c": shape_tool(P.PlotCentreRectTool),
            "rect_r": shape_tool(P.PlotRotRectTool),
            "circle": shape_tool(P.PlotCircleTool)}


#: shape → its tool («chain»: SeparatorTool, point by point)
SHAPE_TOOLS = _shape_tools()
