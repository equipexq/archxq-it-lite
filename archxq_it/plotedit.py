"""Editing the drawn plot in the 3D view — IngeTrazo tools.

- FoldLineTool: where a sloped plot folds. Click a corner, then another:
  the ground now folds on that line (a breakline). Click a fold line to
  remove it. Esc drops the first corner, or leaves the tool.
- PlotEditTool: the corners with the mouse — move, add, delete.

Every change goes back through ``on_change`` — one Ctrl+Z each.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt
from tools.base import Tool

from . import compat, plotgeo
from .plottools import (ACTIVE, DIAG_COLOR, _m, _PlotTool, _v,
                        draw_plot_preview)

CORNER_PX = 16          # a click this close to a corner picks it
LINE_PX = 8             # …and this close to a line (side, fold) picks it
RED = "#e5484d"


def _seg_dist(p, a, b) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx +
                                              (p[1] - ay) * dy) / L2))
    return math.dist(p, (ax + t * dx, ay + t * dy))


class FoldLineTool(Tool):
    uses_snap = False
    draws_plot = True        # it draws the plot itself (ArchXQ skips its dims)
    plot_dims = staticmethod(lambda: True)   # ArchXQ sets: show the lengths?

    def __init__(self, get_plot, on_change, on_cancelled, z0: float) -> None:
        super().__init__()
        self.get_plot = get_plot            # → the current doc["plot"]
        self.on_change = on_change          # (breaks) → commits
        self.on_cancelled = on_cancelled
        self.z0 = z0
        self.viewport = None
        self.first: int | None = None
        self.mouse = None                   # screen (x, y)
        self.hot_corner: int | None = None
        self.hot_line: int | None = None    # index in plot["breaks"]

    # -- host protocol -------------------------------------------------------------
    def on_activate(self, viewport) -> None:
        self.viewport = viewport
        self._hint()

    def on_deactivate(self, viewport) -> None:
        compat.flash(viewport, "", 1)

    def drag_plane(self, viewport):
        return compat.vec(0, 0, 0), compat.vec(0, 0, 1)

    def on_hover(self, ctx) -> None:
        self.mouse = (ctx.screen.x(), ctx.screen.y())
        self._find()
        self._hint()
        self.viewport.update()

    def on_click(self, ctx) -> None:
        self.mouse = (ctx.screen.x(), ctx.screen.y())
        self._find()
        plot = self.get_plot()
        if plot is None:
            return
        breaks = [list(b) for b in plot["breaks"]]
        c = self.hot_corner
        if self.first is None:
            if c is not None:
                self.first = c
            elif self.hot_line is not None:
                del breaks[self.hot_line]
                self.hot_line = None
                self.on_change(breaks)
                compat.flash(self.viewport, "Fold line removed", 3000)
                return
            self._hint()
            self.viewport.update()
            return
        if c is None:
            return
        if c == self.first:
            self.first = None               # clicked it again: let go
            self._hint()
            self.viewport.update()
            return
        pair = sorted((self.first, c))
        pts = plot["corners"]
        why = self._why_not(pts, breaks, pair)
        if why:
            compat.flash(self.viewport, why, 4000)
            return
        breaks.append(pair)
        self.first = None
        self.on_change(breaks)
        flat = max(plot["heights"]) - min(plot["heights"]) < 1e-6
        compat.flash(self.viewport, "Fold line added" + (
            " — it shows once the corners have different heights"
            if flat else ""), 4000)

    def on_key(self, viewport, key, modifiers) -> bool:
        return False

    def on_cancel(self, viewport) -> None:
        if self.first is not None:
            self.first = None
            self._hint()
            viewport.update()
            return
        if self.on_cancelled:
            self.on_cancelled()

    # -- helpers ----------------------------------------------------------------------
    @staticmethod
    def _why_not(pts, breaks, pair) -> str | None:
        n = len(pts)
        i, j = pair
        if (i - j) % n in (1, n - 1):
            return "Those two corners share a side — pick corners across " \
                   "the plot"
        if pair in breaks:
            return "That fold line is already there"
        if not plotgeo.diagonal_ok(pts, i, j):
            return "That line would leave the plot"
        for a, b in breaks:
            if {a, b} & {i, j}:
                continue
            if plotgeo._segments_cross(pts[i], pts[j], pts[a], pts[b]):
                return "It would cross another fold line"
        return None

    def _pixels(self):
        plot = self.get_plot()
        if plot is None:
            return None, []
        return plot, [compat.to_pixel(self.viewport, x, y, self.z0 + h)
                      for (x, y), h in zip(plot["corners"], plot["heights"])]

    def _find(self) -> None:
        self.hot_corner = self.hot_line = None
        plot, px = self._pixels()
        if plot is None or self.mouse is None:
            return
        best = None
        for i, p in enumerate(px):
            if p:
                d = math.dist(p, self.mouse)
                if d <= CORNER_PX and (best is None or d < best[0]):
                    best = (d, i)
        if best is not None:
            self.hot_corner = best[1]
            return
        if self.first is None:
            for k, (a, b) in enumerate(plot["breaks"]):
                if px[a] and px[b] and \
                        _seg_dist(self.mouse, px[a], px[b]) <= LINE_PX:
                    self.hot_line = k
                    return

    def _hint(self) -> None:
        if self.viewport is None:
            return
        if self.first is not None:
            text = "Fold line: click the corner where it ends — Esc to let go"
        elif self.hot_line is not None:
            text = "Fold line: click to remove this fold line"
        else:
            text = ("Fold line: click a corner, then another across the plot"
                    " · click a fold line to remove it · Esc to finish")
        if text != getattr(self, "_shown", None):   # don't flood the bar
            self._shown = text
            compat.flash(self.viewport, text, 600000)

    # -- drawn by ArchXQ's overlay --------------------------------------------------------
    def draw_overlay(self, viewport, painter) -> None:
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QColor, QPen
        plot, px = self._pixels()
        if plot is None:
            return
        # fold lines first: the numbered corners stay readable on top
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        for k, (a, b) in enumerate(plot["breaks"]):
            if px[a] and px[b]:
                hot = k == self.hot_line
                pen = QPen(QColor("#e5484d" if hot else DIAG_COLOR),
                           5 if hot else 3, Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(QPointF(*px[a]), QPointF(*px[b]))
        painter.restore()
        draw_plot_preview(viewport, painter, plot["corners"], plot["heights"],
                          plot["closing"], self.z0, None,
                          dims=self.plot_dims())
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        # the line being drawn: first corner → hovered corner / cursor
        if self.first is not None and px[self.first]:
            end = (px[self.hot_corner] if self.hot_corner is not None
                   else self.mouse)
            if end:
                painter.setPen(QPen(QColor(ACTIVE), 3))
                painter.drawLine(QPointF(*px[self.first]), QPointF(*end))
        for i in (self.first, self.hot_corner):
            if i is not None and px[i]:
                p = px[i]
                painter.setPen(QPen(QColor(255, 255, 255), 2))
                painter.setBrush(QColor(ACTIVE))
                painter.drawEllipse(QRectF(p[0] - 13, p[1] - 13, 26, 26))
                painter.setPen(QColor("#ffffff"))
                painter.drawText(QRectF(p[0] - 13, p[1] - 13, 26, 26),
                                 Qt.AlignCenter, str(i + 1))
        painter.restore()


# ---- Setbacks: which side is the front ------------------------------------------------
ROLE_INK = {"front": "#2f7df6", "back": "#9b6bd6", "side": "#8a94a0"}


class SetbackTool(Tool):
    """Click a side of the plot: it becomes a FRONT (click again: not);
    a corner plot can have two. The side facing away becomes the back,
    the rest the sides — each takes its distance from the panel. Hover a
    side and type a number + Enter: that side gets its own distance;
    Delete puts it back to its role's."""
    uses_snap = False
    draws_plot = True
    vcb_label = "Setback"

    def __init__(self, get_plot, on_change, on_cancelled, z0: float,
                 dims=lambda: True, on_open=None) -> None:
        super().__init__()
        self.get_plot = get_plot
        self.on_change = on_change              # (sb_front, sb_custom)
        self.on_cancelled = on_cancelled
        self.z0 = z0
        self.dims = dims                        # () → show the figures?
        self.on_open = on_open                  # double-click: the window
        self.viewport = None
        self.mouse = None
        self.hot: int | None = None

    def on_activate(self, viewport) -> None:
        self.viewport = viewport
        self._hint(force=True)

    def on_deactivate(self, viewport) -> None:
        compat.flash(viewport, "", 1)

    def drag_plane(self, viewport):
        return compat.vec(0, 0, 0), compat.vec(0, 0, 1)

    def _pixels(self, plot):
        return [compat.to_pixel(self.viewport, x, y, self.z0 + h)
                for (x, y), h in zip(plot["corners"], plot["heights"])]

    def _find(self) -> None:
        self.hot = None
        plot = self.get_plot()
        if plot is None or self.mouse is None:
            return
        px = self._pixels(plot)
        n = len(px)
        best = None
        for k in range(n):
            a, b = px[k], px[(k + 1) % n]
            if a and b:
                d = _seg_dist(self.mouse, a, b)
                if d <= LINE_PX * 1.5 and (best is None or d < best[0]):
                    best = (d, k)
        self.hot = best[1] if best else None

    def on_hover(self, ctx) -> None:
        self.mouse = (ctx.screen.x(), ctx.screen.y())
        self._find()
        self._hint()
        self.viewport.update()

    def on_click(self, ctx) -> None:
        self.mouse = (ctx.screen.x(), ctx.screen.y())
        self._find()
        plot = self.get_plot()
        if plot is None or self.hot is None:
            return
        front = list(plot["sb_front"])
        front[self.hot] = not front[self.hot]
        role = list(plot["sb_role"])
        role[self.hot] = None                # a front is a front; off = auto
        self.on_change(front, list(plot["sb_custom"]), role=role)
        compat.flash(self.viewport, "Front marked" if front[self.hot]
                     else "Not a front any more", 3000)

    def on_double_click(self, ctx) -> None:
        """Double-click inside the plot: the Setbacks window (a double
        click on a side has already toggled it twice — no change)."""
        if self.on_open:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self.on_open)

    def on_value(self, viewport, value) -> bool:
        plot = self.get_plot()
        if plot is None or not isinstance(value, (int, float)):
            return False
        if self.hot is None:
            compat.flash(viewport, "Point at a side first, then type its "
                         "setback", 4000)
            return True
        if not any(plot["sb_front"]):
            compat.flash(viewport, "Mark the front first (click a side)",
                         4000)
            return True
        custom = list(plot["sb_custom"])
        custom[self.hot] = round(max(0.0, float(value)), 3)
        self.on_change(list(plot["sb_front"]), custom)
        return True

    def on_key(self, viewport, key, modifiers) -> bool:
        if compat.typed_value(viewport):
            return False
        if key in (Qt.Key_Delete, Qt.Key_Backspace) and self.hot is not None:
            plot = self.get_plot()
            if plot and plot["sb_custom"][self.hot] is not None:
                custom = list(plot["sb_custom"])
                custom[self.hot] = None
                self.on_change(list(plot["sb_front"]), custom)
                compat.flash(viewport, "Side back to its role's setback",
                             3000)
                return True
        return False

    def on_cancel(self, viewport) -> None:
        if self.on_cancelled:
            self.on_cancelled()

    def value_label(self):
        return None

    def _hint(self, force: bool = False) -> None:
        if self.viewport is None:
            return
        plot = self.get_plot()
        if plot is not None and not any(plot["sb_front"]):
            text = ("Setbacks: click the side of the plot that faces the "
                    "street (the front) · Esc = finish")
        elif self.hot is not None:
            text = ("Setbacks: click = front on / off · type a distance + "
                    "Enter = this side's own · Delete = back to its role's")
        else:
            text = ("Setbacks: click a side to make it a front (or not) · "
                    "point at a side and type its own setback · Esc = finish")
        if force or text != getattr(self, "_shown", None):
            self._shown = text
            compat.flash(self.viewport, text, 600000)

    def draw_overlay(self, viewport, painter) -> None:
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QColor, QFont, QPen
        from .plottools import draw_setbacks
        plot = self.get_plot()
        if plot is None:
            return
        roles, dists, _area = plotgeo.setbacks_of(plot)
        px = self._pixels(plot)
        n = len(px)
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        font = QFont(painter.font())
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        for k in range(n):
            a, b = px[k], px[(k + 1) % n]
            if not a or not b:
                continue
            role = roles[k]
            hot = k == self.hot
            col = QColor(ROLE_INK.get(role, "#e8742c"))
            painter.setPen(QPen(col, 7 if hot else (5 if role == "front"
                                                    else 3)))
            painter.drawLine(QPointF(*a), QPointF(*b))
            if role is not None:
                own = plot["sb_custom"][k] is not None
                text = f"{role.upper()}  {dists[k]:.2f}" + ("  ✎" if own
                                                            else "")
                m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                w, h = fm.horizontalAdvance(text) + 10, fm.height() + 3
                r = QRectF(m[0] - w / 2, m[1] + 8, w, h)
                painter.setPen(Qt.NoPen)
                painter.setBrush(col)
                painter.drawRoundedRect(r, 3, 3)
                painter.setPen(QColor("#ffffff"))
                painter.drawText(r, Qt.AlignCenter, text)
        painter.restore()
        draw_setbacks(viewport, painter, plot, self.z0, dims=self.dims())


# ---- Survey points: add / delete on the model ---------------------------------------
POINT_PX = 12           # a click this close to a survey point picks it


class SurveyTool(Tool):
    """Survey points with the mouse. ``mode`` "add": click on the plot =
    a point there at the ground's height; type an elevation + Enter = a
    point under the cursor at that elevation — or, over a point, its new
    elevation. "delete": click a point. Double-click: the points' window.
    Every change → ``on_change(points)`` (one Ctrl+Z)."""
    uses_snap = True
    vcb_label = "Elevation"

    def __init__(self, mode: str, get_plot, ground, on_change, on_cancelled,
                 z0: float, on_open=None) -> None:
        super().__init__()
        self.mode = mode
        self.get_plot = get_plot
        self.ground = ground                    # (x, y) → the ground's z
        self.on_change = on_change
        self.on_cancelled = on_cancelled
        self.z0 = z0
        self.on_open = on_open
        self.viewport = None
        self.mouse = None
        self.where = None                       # the cursor on the plot
        self.hot: int | None = None

    def on_activate(self, viewport) -> None:
        from .plottools import EDGE_SNAP_PX, SNAP_PX
        self.viewport = viewport
        self._snap_before = compat.set_snap_reach(viewport, SNAP_PX,
                                                  EDGE_SNAP_PX)
        self._hint(force=True)

    def on_deactivate(self, viewport) -> None:
        before = getattr(self, "_snap_before", None)
        if before:
            compat.set_snap_reach(viewport, *before)
        compat.flash(viewport, "", 1)

    def drag_plane(self, viewport):
        return compat.vec(0, 0, 0), compat.vec(0, 0, 1)

    def _find(self) -> None:
        self.hot = None
        plot = self.get_plot()
        if plot is None or self.mouse is None:
            return
        best = None
        for i, s in enumerate(plot.get("survey") or []):
            p = compat.to_pixel(self.viewport, s[0], s[1], self.z0 + s[2])
            if p:
                d = math.dist(p, self.mouse)
                if d <= POINT_PX and (best is None or d < best[0]):
                    best = (d, i)
        self.hot = best[1] if best else None

    def _read(self, ctx) -> None:
        self.mouse = (ctx.screen.x(), ctx.screen.y())
        w = ctx.world
        self.where = [round(w.x(), 3), round(w.y(), 3)]
        self._find()

    def on_hover(self, ctx) -> None:
        self._read(ctx)
        self._hint()
        self.viewport.update()

    def _inside(self, plot, p) -> bool:
        return bool(plotgeo.survey_inside(plot["corners"],
                                          [[p[0], p[1], 0.0, ""]]))

    def _add(self, plot, p, z) -> None:
        pts = [list(s) for s in plot.get("survey") or []]
        used = {s[3] for s in pts}
        k = len(pts) + 1
        while f"P{k}" in used:
            k += 1
        pts.append([p[0], p[1], round(float(z), 3), f"P{k}"])
        self.on_change(pts)
        compat.flash(self.viewport, f"Point P{k} at {z:+.2f} m — type an "
                     "elevation + Enter over it to change it · Ctrl+Z "
                     "undoes it", 5000)

    def on_click(self, ctx) -> None:
        self._read(ctx)
        plot = self.get_plot()
        if plot is None:
            return
        if self.mode == "delete":
            if self.hot is None:
                return
            pts = [list(s) for s in plot.get("survey") or []]
            gone = pts.pop(self.hot)
            self.hot = None
            self.on_change(pts)
            compat.flash(self.viewport, f"Point {gone[3] or ''} deleted — "
                         "Ctrl+Z brings it back", 4000)
            return
        if self.hot is not None:
            compat.flash(self.viewport, "A point is already here — type its "
                         "elevation + Enter to change it", 4000)
            return
        if not self._inside(plot, self.where):
            compat.flash(self.viewport, "Inside the plot, please (not on its "
                         "border or a corner)", 4000)
            return
        self._add(plot, self.where, self.ground(self.where))

    def on_double_click(self, ctx) -> None:
        if self.on_open:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self.on_open)

    def on_value(self, viewport, value) -> bool:
        plot = self.get_plot()
        if plot is None or not isinstance(value, (int, float)) \
                or self.mode != "add":
            return False
        if self.hot is not None:
            pts = [list(s) for s in plot.get("survey") or []]
            pts[self.hot][2] = round(float(value), 3)
            self.on_change(pts)
            compat.flash(viewport, f"Point {pts[self.hot][3]} now at "
                         f"{value:+.2f} m", 4000)
            return True
        if self.where is None or not self._inside(plot, self.where):
            compat.flash(viewport, "Point inside the plot, then type the "
                         "elevation", 4000)
            return True
        self._add(plot, self.where, value)
        return True

    def on_key(self, viewport, key, modifiers) -> bool:
        return False

    def on_cancel(self, viewport) -> None:
        if self.on_cancelled:
            self.on_cancelled()

    def value_label(self):
        return None

    def _hint(self, force: bool = False) -> None:
        if self.viewport is None:
            return
        if self.mode == "delete":
            text = ("Delete survey point: click a point · Esc = finish"
                    if self.hot is None else
                    "Delete survey point: click to delete this one")
        elif self.hot is not None:
            text = ("Survey point: type its new elevation + Enter · "
                    "double-click = the points' window")
        else:
            text = ("Survey point: click on the plot (at the ground's height) "
                    "or type an elevation + Enter (a point under the cursor "
                    "at it) · Esc = finish")
        if force or text != getattr(self, "_shown", None):
            self._shown = text
            compat.flash(self.viewport, text, 600000)

    def draw_overlay(self, viewport, painter) -> None:
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen
        plot = self.get_plot()
        if plot is None:
            return
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        if self.hot is not None:
            s = (plot.get("survey") or [])[self.hot]
            p = compat.to_pixel(viewport, s[0], s[1], self.z0 + s[2])
            if p:
                ink = RED if self.mode == "delete" else ACTIVE
                painter.setPen(QPen(QColor(ink), 2.5))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(*p), 9, 9)
        elif self.mode == "add" and self.where is not None \
                and self._inside(plot, self.where):
            z = self.ground(self.where)
            p = compat.to_pixel(viewport, self.where[0], self.where[1],
                                self.z0 + z)
            if p:
                painter.setPen(QPen(QColor(ACTIVE), 2))
                painter.setBrush(QColor(255, 255, 255, 160))
                painter.drawEllipse(QPointF(*p), 5, 5)
        painter.restore()


# ---- Move / Add / Delete a corner --------------------------------------------------
class PlotEditTool(_PlotTool):
    """The plot's corners with the mouse. One tool, three modes:

    - move: click a corner, it follows the cursor (axes, 45°, alignments,
      live length — the drawing tools' help), click where it goes; or type
      a distance + Enter. Esc puts it back.
    - add: hover a side (a marker shows where), click: a new corner is
      born there and follows the cursor until the next click.
    - delete: hover a corner (red), click: it goes — never below three
      corners, never into crossing sides.

    Heights, fold lines and the closing side follow every change
    (``plotgeo``); each change is one Ctrl+Z (``on_change``)."""
    name = "ArchXQ edit plot"
    vcb_label = "Distance"
    diagonal = True
    creates = False             # editing: the camera stays free (3D drags)
    draws_plot = True           # it draws the plot itself (no standing dims)
    plot_dims = staticmethod(lambda: True)   # ArchXQ sets: show the lengths?
    check = staticmethod(plotgeo.why_not)    # → the reason an outline is bad

    #: X / Y / Z lock the corner being moved to an axis (his ask,
    #: 2026-10-02); Z raises / lowers it — the plot's height there
    allow_z = True
    claimed_keys = frozenset({Qt.Key_C, Qt.Key_X, Qt.Key_Y, Qt.Key_Z})
    LOCK_KEYS = {Qt.Key_X: "x", Qt.Key_Y: "y", Qt.Key_Z: "z"}

    def __init__(self, mode: str, get_plot, on_change, on_cancelled,
                 z0: float) -> None:
        self.mode = mode
        self.get_plot = get_plot
        self.on_change = on_change
        self.z0 = z0
        self.moving = None
        self.lock = None
        super().__init__(lambda _c: None, on_cancelled)
        self.icon = {"move": "move", "add": "add_point",
                     "delete": "eraser"}[mode]

    # -- state ---------------------------------------------------------------------
    def _reset(self) -> None:
        self.moving: int | None = None       # corner following the cursor
        self.origin: list[float] | None = None
        self.pending = None                  # (pts, heights, closing, breaks)
        self.hot_corner: int | None = None
        self.hot_side = None                 # (side, point on it)
        self.mouse = None
        self.diag = None
        self.lock = None                     # "x" | "y" | "z" while moving
        self.grab_mouse = None
        self.h0 = 0.0
        self._sync()

    def _busy(self) -> bool:
        return self.moving is not None

    # -- the axis lock ---------------------------------------------------------------
    def _locked(self, p):
        """The cursor's point held to the locked axis (x, y)."""
        if self.lock == "x":
            return [p[0], self.origin[1]]
        if self.lock == "y":
            return [self.origin[0], p[1]]
        return p

    def _z_from_mouse(self) -> float:
        """The height the vertical mouse travel gives (Z lock): the screen
        length of one metre up, at the corner; from the top (no length
        up) one metre across."""
        o = self.origin
        a = compat.to_pixel(self.viewport, o[0], o[1], self.z0 + self.h0)
        b = compat.to_pixel(self.viewport, o[0], o[1], self.z0 + self.h0 + 1)
        ppm = math.dist(a, b) if a and b else 0.0
        if ppm < 4.0:
            c = compat.to_pixel(self.viewport, o[0] + 1, o[1],
                                self.z0 + self.h0)
            ppm = math.dist(a, c) if a and c else 40.0
        dy = (self.grab_mouse[1] - self.mouse[1]) if self.mouse and \
            self.grab_mouse else 0.0
        return round(self.h0 + dy / max(ppm, 1e-6), 3)

    def _set_height(self, h: float) -> None:
        pts, hs, cl, br = self.pending
        hs = list(hs)
        hs[self.moving] = round(min(max(h, -100.0), 100.0), 3)
        self.pending = (pts, hs, cl, br)

    def _state(self):
        """The outline being edited: the pending one while a corner moves."""
        if self.pending is not None:
            return self.pending
        p = self.get_plot()
        if p is None:
            return None
        return (p["corners"], p["heights"], p["closing"], p["breaks"])

    def _anchor(self):
        return self.origin

    def _align_sources(self):
        st = self._state()
        if st is None:
            return []
        return [q for k, q in enumerate(st[0]) if k != self.moving]

    def _sync(self) -> None:
        if self.moving is None or self.pending is None:
            self._sync_protocol([], self.hover)
            self.chain_first_point = None
            return
        others = [q for k, q in enumerate(self.pending[0])
                  if k != self.moving]
        self.chain_vertices = [_v(q) for q in others]
        self.start_point = _v(self.origin)
        self.chain_first_point = None
        self.hover_point = _v(self.hover) if self.hover is not None else None

    # -- picking on screen --------------------------------------------------------
    def _pixels(self, st):
        return [compat.to_pixel(self.viewport, x, y, self.z0 + h)
                for (x, y), h in zip(st[0], st[1])]

    def _find(self) -> None:
        self.hot_corner = self.hot_side = None
        st = self._state()
        if st is None or self.mouse is None or self.moving is not None:
            return
        px = self._pixels(st)
        best = None
        for k, p in enumerate(px):
            if p:
                d = math.dist(p, self.mouse)
                if d <= CORNER_PX and (best is None or d < best[0]):
                    best = (d, k)
        if best is not None and self.mode in ("move", "delete"):
            self.hot_corner = best[1]
            return
        if self.mode != "add" or best is not None:
            return
        n = len(px)
        for k in range(n):
            a, b = px[k], px[(k + 1) % n]
            if a and b and _seg_dist(self.mouse, a, b) <= LINE_PX:
                # where on the side: the cursor's ground point projected on it
                p = self.hover or st[0][k]
                A, B = st[0][k], st[0][(k + 1) % n]
                dx, dy = B[0] - A[0], B[1] - A[1]
                L2 = dx * dx + dy * dy or 1.0
                t = max(0.02, min(0.98, ((p[0] - A[0]) * dx +
                                         (p[1] - A[1]) * dy) / L2))
                self.hot_side = (k, [A[0] + t * dx, A[1] + t * dy])
                return

    # -- host protocol --------------------------------------------------------------
    def on_hover(self, ctx) -> None:
        self.mouse = (ctx.screen.x(), ctx.screen.y())
        if self.moving is not None and self.lock == "z":
            self._set_height(self._z_from_mouse())
        elif self.moving is not None:
            self.hover = self._locked(self._pick(ctx))
            self._drag(self.hover)
        else:
            self.hover = [round(ctx.world.x(), 4), round(ctx.world.y(), 4)]
        self._find()
        self._sync()
        self._show_hint()
        self.viewport.update()

    def _drag(self, p) -> None:
        pts, hs, cl, br = self.pending
        pts = [list(q) for q in pts]
        pts[self.moving] = [round(p[0], 4), round(p[1], 4)]
        self.pending = (pts, hs, cl, br)

    def on_click(self, ctx) -> None:
        self.mouse = (ctx.screen.x(), ctx.screen.y())
        if self.moving is not None and self.lock == "z":
            self._place_height(self._z_from_mouse())
            return
        if self.moving is not None:
            self._place(self._locked(self._pick(ctx)))
            return
        self.hover = [round(ctx.world.x(), 4), round(ctx.world.y(), 4)]
        self._find()
        st = self._state()
        if st is None:
            return
        pts, hs, cl, br = st
        if self.mode == "move" and self.hot_corner is not None:
            self._grab(self.hot_corner, st)
        elif self.mode == "add" and self.hot_side is not None:
            k, p = self.hot_side
            self._grab(k + 1, plotgeo.insert_corner(pts, hs, cl, br, k, p))
        elif self.mode == "delete" and self.hot_corner is not None:
            if len(pts) <= 3:
                compat.flash(self.viewport, "A plot keeps three corners at "
                             "least", 4000)
                return
            new = plotgeo.remove_corner(pts, hs, cl, br, self.hot_corner)
            why = self.check(new[0])
            if why:
                compat.flash(self.viewport, f"{why} — corner kept", 4000)
                return
            self.hot_corner = None
            self.on_change(*new)
            compat.flash(self.viewport, "Corner deleted — Ctrl+Z brings it "
                         "back", 3000)

    def _grab(self, i: int, st) -> None:
        self.moving = i
        self.origin = list(st[0][i])
        self.pending = tuple(st)
        self.lock = None
        self.grab_mouse = self.mouse
        self.h0 = float(st[1][i]) if i < len(st[1]) else 0.0
        self.hover = list(self.origin)
        self.hot_corner = self.hot_side = None
        self._sync()
        self._show_hint()
        self.viewport.update()

    def _place(self, p) -> None:
        pts, hs, cl, br = self.pending
        pts, br = plotgeo.move_corner(pts, br, self.moving, p)
        why = self.check(pts)
        if why:
            compat.flash(self.viewport, f"{why} — pick another place", 4000)
            return
        self._reset()
        self.on_change(pts, hs, cl, br)
        self._show_hint()

    def _place_height(self, h: float) -> None:
        """Z lock: the corner raised / lowered to ``h`` (its place kept)."""
        self._set_height(h)
        pts, hs, cl, br = self.pending
        self._reset()
        self.on_change(pts, hs, cl, br)
        compat.flash(self.viewport, f"Corner at {h:+.2f} m — Ctrl+Z puts "
                     "it back", 4000)

    def on_key(self, viewport, key, modifiers) -> bool:
        lock = self.LOCK_KEYS.get(key)
        if lock and self.moving is not None \
                and not compat.typed_value(viewport) \
                and (lock != "z" or self.allow_z):
            self.lock = None if self.lock == lock else lock
            if self.lock != "z" and self.pending is not None:
                self._set_height(self.h0)        # back to its height
            self.grab_mouse = self.mouse
            self._show_hint()
            viewport.update()
            return True
        return super().on_key(viewport, key, modifiers)

    def on_value(self, viewport, value) -> bool:
        """A typed distance: the corner goes that far from where it was,
        toward the cursor (Z lock: that much up, or down if negative)."""
        if self.moving is not None and self.lock == "z" \
                and isinstance(value, (int, float)):
            self._place_height(self.h0 + float(value))
            return True
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

    def on_cancel(self, viewport) -> None:
        if self.moving is not None:
            self._reset()                    # put it back / drop the new one
            self._show_hint()
            viewport.update()
            return
        if self.on_cancelled:
            self.on_cancelled()

    def rubber_band_lines(self):
        if self.moving is None or self.pending is None:
            return []
        pts = self.pending[0]
        n = len(pts)
        c = pts[self.moving]
        return [(_v(pts[(self.moving - 1) % n]), _v(c)),
                (_v(c), _v(pts[(self.moving + 1) % n]))]

    def value_label(self):
        if self.moving is None or self.hover is None:
            return None
        if self.lock == "z" and self.pending is not None:
            h = self.pending[1][self.moving]
            return (f"Z {h:+.2f} m  (Δ {h - self.h0:+.2f})", None)
        return (f"{math.dist(self.origin, self.hover):.2f} m", None)

    def _labels(self):
        if self.moving is None or self.hover is None:
            return []
        return [((self.origin, self.hover),
                 _m(math.dist(self.origin, self.hover)), None)]

    def status_clause(self) -> str:
        if self.moving is not None:
            if self.lock == "z":
                return ("Edit plot: move the mouse up / down, click — or "
                        "type how much up (− down) + Enter  ·  Z = free  ·  "
                        "Esc = put it back")
            keys = "X / Y / Z = lock to an axis" if self.allow_z else \
                "X / Y = lock to an axis"
            held = f" (held on {self.lock.upper()})" if self.lock else ""
            return (f"Edit plot{held}: click where the corner goes, or type "
                    f"a distance + Enter  ·  {keys}  ·  Esc = put it back")
        return {"move": "Move points: click a corner to move it  ·  Esc = "
                        "finish",
                "add": "Add point: click on a side where the new corner "
                       "goes  ·  Esc = finish",
                "delete": "Delete point: click a corner to delete it  ·  "
                          "Esc = finish"}[self.mode]

    # -- drawn by ArchXQ's overlay -------------------------------------------------
    def draw_overlay(self, viewport, painter) -> None:
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QColor, QPen
        st = self._state()
        if st is None:
            return
        pts, hs, cl, _br = st
        draw_plot_preview(viewport, painter, pts, hs, cl, self.z0, None,
                          dims=self.plot_dims())
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        px = self._pixels(st)
        hot = self.moving if self.moving is not None else self.hot_corner
        if hot is not None and hot < len(px) and px[hot]:
            p = px[hot]
            red = self.mode == "delete" and self.moving is None
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.setBrush(QColor(RED if red else ACTIVE))
            r = QRectF(p[0] - 13, p[1] - 13, 26, 26)
            painter.drawEllipse(r)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(r, Qt.AlignCenter, "×" if red else str(hot + 1))
        if self.hot_side is not None:
            k, q = self.hot_side
            h0, h1 = hs[k], hs[(k + 1) % len(hs)]
            c = compat.to_pixel(viewport, q[0], q[1],
                                self.z0 + (h0 + h1) / 2)
            if c:
                painter.setPen(QPen(QColor(255, 255, 255), 2))
                painter.setBrush(QColor(ACTIVE))
                painter.drawEllipse(QPointF(*c), 8, 8)
                painter.setPen(QPen(QColor("#ffffff"), 2.5))
                painter.drawLine(QPointF(c[0] - 4, c[1]),
                                 QPointF(c[0] + 4, c[1]))
                painter.drawLine(QPointF(c[0], c[1] - 4),
                                 QPointF(c[0], c[1] + 4))
        if self.moving is not None and self.lock:
            # the locked axis through the corner's first place
            o, h = self.origin, self.z0 + self.h0
            far = {"x": ((o[0] - 500, o[1], h), (o[0] + 500, o[1], h)),
                   "y": ((o[0], o[1] - 500, h), (o[0], o[1] + 500, h)),
                   "z": ((o[0], o[1], h - 100), (o[0], o[1], h + 100))}
            col = {"x": QColor(215, 60, 50), "y": QColor(40, 160, 70),
                   "z": QColor(40, 90, 220)}[self.lock]
            ends = []
            for s in (1.0, 0.1, 0.01):          # in front of the camera
                a, b = far[self.lock]
                pa = compat.to_pixel(viewport, o[0] + (a[0] - o[0]) * s,
                                     o[1] + (a[1] - o[1]) * s,
                                     h + (a[2] - h) * s)
                pb = compat.to_pixel(viewport, o[0] + (b[0] - o[0]) * s,
                                     o[1] + (b[1] - o[1]) * s,
                                     h + (b[2] - h) * s)
                if pa and pb:
                    ends = [pa, pb]
                    break
            if ends:
                painter.setPen(QPen(col, 1.6, Qt.DashLine))
                painter.drawLine(QPointF(*ends[0]), QPointF(*ends[1]))
        painter.restore()
        if self.moving is not None:
            super().draw_overlay(viewport, painter)   # guides, live length


class DigEraseTool(Tool):
    """Delete an excavation / fill: the one under the cursor shows in red,
    a click takes it (one Ctrl+Z). Stays out for the next; Esc = done."""
    name = "ArchXQ delete excavation"
    icon = "eraser"
    uses_snap = False
    creates = False

    def __init__(self, get_digs, on_delete, on_cancelled) -> None:
        super().__init__()
        self.get_digs = get_digs
        self.on_delete = on_delete
        self.on_cancelled = on_cancelled
        self.viewport = None
        self.hot = None

    def on_activate(self, viewport) -> None:
        self.viewport = viewport
        compat.flash(viewport, "Delete excavation: click the excavation or "
                     "fill to delete  ·  Esc = done", 600000)

    def on_deactivate(self, viewport) -> None:
        compat.flash(viewport, "", 1)

    def _under(self, x: float, y: float):
        from shapely.geometry import Point, Polygon
        best = None
        for d in self.get_digs():
            try:
                poly = Polygon(d["corners"])
                if poly.buffer(0.05).contains(Point(x, y)) and \
                        (best is None or poly.area < best[0]):
                    best = (poly.area, d)       # the smaller one inside
            except Exception:  # noqa: BLE001
                continue
        return best[1] if best else None

    def drag_plane(self, viewport):
        # the cursor read on the ground plane (z 0), wherever it points
        return compat.vec(0, 0, 0), compat.vec(0, 0, 1)

    def on_hover(self, ctx) -> None:
        if getattr(ctx, "world", None) is None:
            return
        d = self._under(ctx.world.x(), ctx.world.y())
        hot = d["id"] if d else None
        if hot != self.hot:
            self.hot = hot
            self.viewport.update()

    def on_click(self, ctx) -> None:
        d = None if getattr(ctx, "world", None) is None else \
            self._under(ctx.world.x(), ctx.world.y())
        if d is None:
            compat.flash(self.viewport, "Not on an excavation — click inside "
                         "one", 3000)
            return
        self.hot = None
        self.on_delete(d["id"])

    def on_cancel(self, viewport) -> None:
        if self.on_cancelled:
            self.on_cancelled()

    def draw_overlay(self, viewport, painter) -> None:
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen, QPolygonF
        if self.hot is None:
            return
        d = next((x for x in self.get_digs() if x["id"] == self.hot), None)
        if d is None:
            return
        pts = [compat.to_pixel(viewport, q[0], q[1], 0.0) for q in d["corners"]]
        if not all(pts):
            return
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(RED), 3))
        c = QColor(RED)
        c.setAlpha(60)
        painter.setBrush(c)
        painter.drawPolygon(QPolygonF([QPointF(*p) for p in pts]))
        painter.restore()


class DigEditTool(PlotEditTool):
    """The EXCAVATIONS' corners with the mouse — the plot's tool, over all
    of them: the corner (or, adding, the side) nearest the cursor, of
    whichever excavation, is the one taken. ``get_digs()`` → {id: {corners,
    heights (the ground along its rim), closing, breaks}};
    ``on_change(id, corners, …)``; ``check(id, corners)`` → a reason."""
    name = "ArchXQ edit excavation"
    allow_z = False             # an excavation's rim follows the ground

    def __init__(self, mode: str, get_digs, on_change, on_cancelled,
                 z0: float, check) -> None:
        self.get_digs = get_digs
        self.target: str | None = None
        super().__init__(mode, lambda: self.get_digs().get(self.target),
                         lambda *a: on_change(self.target, *a),
                         on_cancelled, z0)
        self.check = lambda pts: check(self.target, pts)

    def _find(self) -> None:
        self.hot_corner = self.hot_side = None
        if self.mouse is None or self.moving is not None:
            return
        best = None                   # (pixels away, id, corner | (side, p))
        for did, st in self.get_digs().items():
            px = self._pixels((st["corners"], st["heights"]))
            n = len(px)
            if self.mode in ("move", "delete"):
                for k, p in enumerate(px):
                    if p:
                        d = math.dist(p, self.mouse)
                        if d <= CORNER_PX and (best is None or d < best[0]):
                            best = (d, did, k)
                continue
            for k in range(n):
                a, b = px[k], px[(k + 1) % n]
                if not (a and b):
                    continue
                d = _seg_dist(self.mouse, a, b)
                if d <= LINE_PX and (best is None or d < best[0]):
                    A, B = st["corners"][k], st["corners"][(k + 1) % n]
                    q = self.hover or A
                    dx, dy = B[0] - A[0], B[1] - A[1]
                    L2 = dx * dx + dy * dy or 1.0
                    t = max(0.02, min(0.98, ((q[0] - A[0]) * dx +
                                             (q[1] - A[1]) * dy) / L2))
                    best = (d, did, (k, [A[0] + t * dx, A[1] + t * dy]))
        if best is None:
            return
        self.target = best[1]
        if self.mode == "add":
            self.hot_side = best[2]
        else:
            self.hot_corner = best[2]

    def draw_overlay(self, viewport, painter) -> None:
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen
        # every excavation's outline, faint — the one under the cursor (or
        # being edited) drawn in full by the plot's tool
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        pen = QPen(QColor(ACTIVE), 1.6, Qt.DashLine)
        painter.setPen(pen)
        for did, st in self.get_digs().items():
            if did == self.target:
                continue
            px = self._pixels((st["corners"], st["heights"]))
            for k in range(len(px)):
                a, b = px[k], px[(k + 1) % len(px)]
                if a and b:
                    painter.drawLine(QPointF(*a), QPointF(*b))
        painter.restore()
        if self.target is not None and self._state() is not None:
            super().draw_overlay(viewport, painter)
