"""Drawing the plot in the 3D view — IngeTrazo tools (tools.base.Tool).

Both read the cursor on the ground plane (z = 0), preview live, take typed
values like every IngeTrazo tool, and hand the finished outline to
``on_done(corners)``; Esc abandons.

- PlotRectTool: corner → opposite corner; or corner + typed «20;30».
- PlotPolyTool: click corner by corner; a typed number lays the next
  corner that far along the cursor's direction; close by clicking the
  first corner, pressing Enter, or double-clicking. Backspace undoes the
  last corner. An edge that would cross the outline is refused.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt
from tools.base import Tool

from . import compat, plotgeo, prefs

CLOSE_PX = 14            # a click this close to the first corner closes
DIAG_PULL_DEG = 3.0      # the cursor sticks to 45° within this (ArchXQ)
ALIGN_PX = 4             # …and to a placed corner's red/green line within
# the host's magnets while an ArchXQ drawing tool is out: its own reach
# (9 px to points, 14 to edges) grabbed the cursor from far away among
# the many edges of the excavations — his complaint, 2026-09-30; 6/7 px
# still too strong (2026-10-01)
SNAP_PX, EDGE_SNAP_PX = 4.0, 4.0
DIAG_COLOR = "#c43bd6"   # magenta: the diagonal, beside the host's red/green
ACCENT = "#e8742c"
ACTIVE = "#2f7df6"       # the plot table's current row, on the model
# the guide lines pull harder than the rest (his ask, 2026-10-05: «too
# subtle, it takes skill to land on it») — the 4 px above are too little
# for a guide; their crossings most of all, the corner one digs to
GUIDE_CROSS_PX = 16.0
GUIDE_LINE_PX = 8.0
GUIDE_MARK = "#0a84ff"   # the plan's guide blue, louder
#: the host's own snaps that stay first (a guide only marks them)
HARD_SNAPS = frozenset({"endpoint", "intersection", "midpoint", "center",
                        "close", "origin", "component_origin",
                        "arc_midpoint"})


def _guide_lines(viewport) -> tuple[list, list]:
    """The model's guides in plan: lines (x, y, dx, dy — unit) and guide
    points (x, y). A guide standing upright has no line in plan."""
    lines, points = [], []
    for g in getattr(getattr(viewport, "scene", None), "guides", None) or []:
        p = getattr(g, "point", None)
        if p is None:
            continue
        if not getattr(g, "is_line", False):
            points.append((p.x(), p.y()))
            continue
        d = g.direction
        L = math.hypot(d.x(), d.y())
        if L < 0.2:
            continue
        lines.append((p.x(), p.y(), d.x() / L, d.y() / L))
    return lines, points


def _cross(l1, l2):
    det = l1[2] * l2[3] - l1[3] * l2[2]
    if abs(det) < 1e-6:
        return None
    t = ((l2[0] - l1[0]) * l2[3] - (l2[1] - l1[1]) * l2[2]) / det
    return (l1[0] + l1[2] * t, l1[1] + l1[3] * t)


def _m(v: float) -> str:
    return f"{v:,.2f} m"


def _xy(ctx) -> list[float]:
    w = ctx.world
    return [round(w.x(), 4), round(w.y(), 4)]


def _v(p):
    return compat.vec(p[0], p[1], 0.0)


class _PlotTool(Tool):
    """Speaks the host's drawing-tool protocol (the Line tool's): the
    viewport reads ``start_point`` / ``hover_point`` / ``chain_first_point``
    / ``chain_vertices`` to draw the live length, colour the rubber band
    on the red / green axes, pull the cursor onto them and onto alignments
    with corners already placed, and snap the close. ``icon`` gives the
    pointer its pencil + shape."""
    uses_snap = True
    #: a CREATION tool (draws something new): it works in the plan view,
    #: LOCKED to the top; editing tools (move / add / delete points…) set
    #: this False — the camera stays free to orbit and drag in 3D (his
    #: call, 2026-10-03)
    creates = True
    noun = "Plot"               # what is drawn (the status bar says it)
    frame = 0.0                 # rectangles square with this angle (rad)
    z = 0.0                     # the working plane: the ground (a level's
                                # floor for the walls)

    def _P(self, p):
        """A plan point on the working plane."""
        return compat.vec(p[0], p[1], self.z)

    def _loc(self, p):
        """World → the tool's frame (turned by ``frame``)."""
        c, s = math.cos(self.frame), math.sin(self.frame)
        return [p[0] * c + p[1] * s, -p[0] * s + p[1] * c]

    def _wld(self, p):
        """The tool's frame → world."""
        c, s = math.cos(self.frame), math.sin(self.frame)
        return [round(p[0] * c - p[1] * s, 4), round(p[0] * s + p[1] * c, 4)]

    def _rect(self, a, b):
        """The rectangle with corners a and b, square with the frame."""
        return [self._wld(q) for q in plotgeo.rectangle(self._loc(a),
                                                        self._loc(b))]
    #: keys this tool takes BEFORE the host's menu shortcuts (C = Circle)
    claimed_keys = frozenset({Qt.Key_C})
    magnetic_axis_deg = 3.0          # same pull as the host's Line tool
    screen_axis_px = 6.0             # (the host's 9 pulled too far)

    def __init__(self, on_done, on_cancelled=None) -> None:
        super().__init__()
        self.on_done = on_done
        self.on_cancelled = on_cancelled
        self.viewport = None
        self.hover: list[float] | None = None
        self.start_point = None
        self.hover_point = None
        self.chain_first_point = None
        self.chain_vertices: list = []
        self.work_plane = None
        self._snap = None
        self._aligned: list = []         # [("x" | "y", corner)]

    def _sync_protocol(self, pts, hover) -> None:
        """Mirror our 2D state into the host's protocol attributes."""
        self.chain_vertices = [self._P(p) for p in pts]
        self.start_point = self.chain_vertices[-1] if pts else None
        self.chain_first_point = self.chain_vertices[0] if pts else None
        self.hover_point = self._P(hover) if hover is not None else None

    def on_activate(self, viewport) -> None:
        self.viewport = viewport
        self._hint_shown = None
        self._snap_before = compat.set_snap_reach(viewport, SNAP_PX,
                                                  EDGE_SNAP_PX)
        self._reset()

    def on_deactivate(self, viewport) -> None:
        self._reset()
        before = getattr(self, "_snap_before", None)
        if before:
            compat.set_snap_reach(viewport, *before)    # the host's again
        compat.flash(viewport, "", 1)

    def drag_plane(self, viewport):
        # always read the cursor on the working plane (the ground, a level)
        return compat.vec(0, 0, self.z), compat.vec(0, 0, 1)

    # -- the cursor point: host snap first, then ArchXQ's 45° pull ----------------
    diagonal = False                 # PlotPolyTool turns the 45° pull on

    def _anchor(self):
        return None

    def _pick(self, ctx) -> list[float]:
        p = _xy(ctx)
        self.diag = None
        a = self._anchor()
        snap = getattr(ctx, "snap", None)
        self._snap = snap                # its alignment guide gets drawn
        g = self._guide_pull(ctx, p, snap)
        if g is not None:
            self._aligned = []
            return g
        on_axis = bool(getattr(snap, "axis", None))
        p = self._align(p, snap)
        if self._aligned:
            return p
        g = self._on_grid(p, snap)
        if g is not None:
            return g
        if not self.diagonal or a is None or on_axis \
                or not prefs.get("diag_pull"):
            return p
        dx, dy = p[0] - a[0], p[1] - a[1]
        d = math.hypot(dx, dy)
        if d < 1e-6:
            return p
        ang = math.degrees(math.atan2(dy, dx)) % 360.0
        for k in (45.0, 135.0, 225.0, 315.0):
            if abs((ang - k + 180.0) % 360.0 - 180.0) <= DIAG_PULL_DEG:
                ux, uy = math.cos(math.radians(k)), math.sin(math.radians(k))
                t = dx * ux + dy * uy
                self.diag = k
                return [round(a[0] + ux * t, 4), round(a[1] + uy * t, 4)]
        return p

    _guide_hit = None        # "cross" | "line": the cursor is on the guides

    def _guide_pull(self, ctx, p, snap):
        """The guides' own pull: a crossing of two (or a guide point)
        within GUIDE_CROSS_PX, else a guide line within GUIDE_LINE_PX.
        Under one of the host's real snaps (an end…) it only marks it."""
        self._guide_hit = None
        vp = self.viewport
        if vp is None:
            return None
        lines, points = _guide_lines(vp)
        if not lines and not points:
            return None
        scr = getattr(ctx, "screen", None)
        here = (scr.x(), scr.y()) if scr is not None \
            else compat.to_pixel(vp, p[0], p[1], self.z)
        if not here:
            return None

        def near(q, reach, best):
            px = compat.to_pixel(vp, q[0], q[1], self.z)
            if px:
                d = math.dist(here, px)
                if d <= reach and (best is None or d < best[0]):
                    return (d, q)
            return best
        best, hit = None, "cross"
        for i in range(len(lines)):
            for j in range(i + 1, len(lines)):
                q = _cross(lines[i], lines[j])
                if q is not None:
                    best = near(q, GUIDE_CROSS_PX, best)
        for q in points:
            best = near(q, GUIDE_CROSS_PX, best)
        if best is None:
            hit = "line"
            for ox, oy, dx, dy in lines:
                t = (p[0] - ox) * dx + (p[1] - oy) * dy
                best = near((ox + dx * t, oy + dy * t), GUIDE_LINE_PX, best)
        if best is None:
            return None
        q = [round(best[1][0], 4), round(best[1][1], 4)]
        if getattr(snap, "kind", "") in HARD_SNAPS:
            here_p = compat.to_pixel(vp, p[0], p[1], self.z)
            there = compat.to_pixel(vp, q[0], q[1], self.z)
            if not here_p or not there or math.dist(here_p, there) > 2.0:
                return None                  # the host's snap is elsewhere
            self._guide_hit = hit
            return None                      # the same spot: keep the host's
        self._guide_hit = hit
        return q

    def _on_grid(self, p, snap):
        """The plan grid's pull (the hub's grid button): the point on the
        grid's crossing — only where nothing real is snapped (an end, an
        edge…); along a red / green axis from the last point, only its free
        coordinate. None: no pull."""
        if self.viewport is None or not prefs.get("grid_snap"):
            return None
        kind = getattr(snap, "kind", "")
        if kind not in ("none", "ground", "axis", "", None):
            return None
        step = compat.grid_step(self.viewport)
        if not step:
            return None
        axis = getattr(snap, "axis", None)
        x, y = p[0], p[1]
        if axis != "y":                       # x free (or both)
            x = round(round(x / step) * step, 4)
        if axis != "x":
            y = round(round(y / step) * step, 4)
        return [x, y]

    def _align(self, p, snap) -> list[float]:
        """SketchUp's «from point» inference, for EVERY corner placed (the
        host only does it for the first): within ALIGN_PX on screen of the
        red or green line through a corner, the cursor sits on it. Along a
        host axis only the free coordinate aligns, so running along red
        from the last corner still squares up with another one."""
        self._aligned = []
        if self.viewport is None:
            return p
        axis = getattr(snap, "axis", None)
        kind = getattr(snap, "kind", "")
        if kind not in ("none", "ground", "axis", "", None):
            return p                         # a real snap wins (endpoint…)
        here = compat.to_pixel(self.viewport, p[0], p[1], self.z)
        if not here:
            return p
        anchor = self._anchor()
        best = {}                            # "x" / "y" → (px, corner)
        for q in self._align_sources():
            if anchor is not None and q == anchor and axis:
                continue                     # the axis already covers it
            for coord in ("x", "y"):
                if axis == "x" and coord == "y":
                    continue                 # y is locked by the red axis
                if axis == "y" and coord == "x":
                    continue
                cand = [q[0], p[1]] if coord == "x" else [p[0], q[1]]
                there = compat.to_pixel(self.viewport, cand[0], cand[1],
                                        self.z)
                if not there:
                    continue
                d = math.dist(here, there)
                if d <= ALIGN_PX and (coord not in best or d < best[coord][0]):
                    best[coord] = (d, q)
        out = list(p)
        for coord, (_d, q) in best.items():
            if coord == "x":
                out[0] = q[0]
            else:
                out[1] = q[1]
            self._aligned.append((coord, q))
        return [round(out[0], 4), round(out[1], 4)]

    def _align_sources(self):
        return []

    def on_hover(self, ctx) -> None:
        self.hover = self._pick(ctx)
        self._sync()
        self._show_hint()

    def _sync(self) -> None: ...

    def on_key(self, viewport, key, modifiers) -> bool:
        # C is the host's Circle: while a plot tool is out it must not
        # swap the tool under the user's hand
        return key == Qt.Key_C and not compat.typed_value(viewport)

    # -- status bar: the step we are in (the host ignores plugin clauses) -------
    def _show_hint(self) -> None:
        text = self.status_clause()
        if text != self._hint_shown and self.viewport is not None:
            self._hint_shown = text
            compat.flash(self.viewport, text, 600000)

    # -- drawn over the 3D view by ArchXQ's overlay --------------------------------
    def draw_overlay(self, viewport, painter) -> None:
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QColor, QFont, QPen
        if self.hover is None:
            return
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        hp = compat.to_pixel(viewport, self.hover[0], self.hover[1], self.z)
        # 45° guide through the anchor
        a = self._anchor()
        if self.diag is not None and a is not None:
            k = math.radians(self.diag)
            # the longest stretch either way that stays in front of the camera
            ends = []
            for sign in (-1.0, 1.0):
                for s in (60.0, 30.0, 15.0, 6.0, 2.0):
                    px = compat.to_pixel(viewport, a[0] + math.cos(k) * s * sign,
                                         a[1] + math.sin(k) * s * sign, self.z)
                    if px:
                        ends.append(px)
                        break
            pa, pb = (ends + [None, None])[:2]
            if pa and pb:
                pen = QPen(QColor(DIAG_COLOR), 1.2, Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(QPointF(*pa), QPointF(*pb))
        # alignment with a corner already placed (the host infers it —
        # «from_point» — but draws no guide for plugin tools)
        for g0, g1, col in self._guides():
            pa = viewport._world_to_pixel(g0)
            pb = viewport._world_to_pixel(g1)
            if pa and pb:
                pen = QPen(col, 1.3, Qt.DotLine)
                painter.setPen(pen)
                painter.drawLine(QPointF(*pa), QPointF(*pb))
                painter.setPen(Qt.NoPen)
                painter.setBrush(col)
                painter.drawEllipse(QPointF(*pa), 3.5, 3.5)
        # the marker on the ground under the cursor
        if hp:
            c = QPointF(*hp)
            painter.setPen(QPen(QColor(ACCENT), 1.6))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(c, 6.0, 6.0)
            painter.drawLine(QPointF(c.x() - 11, c.y()), QPointF(c.x() - 4, c.y()))
            painter.drawLine(QPointF(c.x() + 4, c.y()), QPointF(c.x() + 11, c.y()))
            painter.drawLine(QPointF(c.x(), c.y() - 11), QPointF(c.x(), c.y() - 4))
            painter.drawLine(QPointF(c.x(), c.y() + 4), QPointF(c.x(), c.y() + 11))
            if self._guide_hit:              # on the guides: say it loud
                ink = QColor(GUIDE_MARK)
                painter.setPen(QPen(ink, 2.6))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(c, 13.0, 13.0)
                if self._guide_hit == "cross":
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(ink)
                    painter.drawEllipse(c, 5.0, 5.0)
                painter.setBrush(Qt.NoBrush)
        # live measurements
        font = QFont(painter.font())
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        labels = list(self._labels()) if prefs.get("live_dims") else []
        if self.diag is not None and hp:
            labels.append((None, "45°", (hp[0] + 22, hp[1] - 18)))
        for seg, text, at in labels:
            if seg is not None:
                pa = compat.to_pixel(viewport, seg[0][0], seg[0][1], self.z)
                pb = compat.to_pixel(viewport, seg[1][0], seg[1][1], self.z)
                if not pa or not pb:
                    continue
                at = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2 - 14)
            w, h = fm.horizontalAdvance(text) + 12, fm.height() + 4
            r = QRectF(at[0] - w / 2, at[1] - h / 2, w, h)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(32, 35, 40, 220))
            painter.drawRoundedRect(r, 4, 4)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(r, Qt.AlignCenter, text)
        painter.restore()

    def _labels(self):
        """[(segment | None, text, pixel_at | None)] to draw."""
        return []

    def _guides(self):
        """[(from QVector3D, to QVector3D, QColor)]: the alignment the
        cursor is snapped to — from the aligned corner to the cursor."""
        from PySide6.QtGui import QColor
        snap = getattr(self, "_snap", None)
        if snap is None or self.hover is None:
            return []
        out = []
        cur = self._P(self.hover)
        # ArchXQ's own alignments: x shared = along green, y = along red
        for coord, q in self._aligned:
            out.append((self._P(q), cur, QColor("#43a047" if coord == "x"
                                                else "#e53935")))
        if out:
            return out
        raw = list(getattr(snap, "guides", None) or [])
        if getattr(snap, "guide", None):
            raw.append(snap.guide)
        col = getattr(snap, "guide_color", None) or getattr(snap, "color",
                                                             None)
        qc = (QColor.fromRgbF(*col[:3]) if col and max(col[:3]) > 0
              else QColor("#3b82f6"))
        for g in raw:
            try:
                pts = [q for q in g if hasattr(q, "x")]
            except TypeError:
                continue
            if pts:
                # the aligned corner is the far end; the guide runs to us
                far = max(pts, key=lambda q: (q - cur).length())
                out.append((far, cur, qc))
        # the host found an alignment but gave no geometry: find the corner
        if not out and getattr(snap, "kind", "") == "from_point":
            for q in self.chain_vertices:
                if abs(q.x() - cur.x()) < 1e-3 or abs(q.y() - cur.y()) < 1e-3:
                    red = abs(q.y() - cur.y()) < 1e-3
                    out.append((q, cur, QColor("#e53935" if red
                                               else "#43a047")))
        return out

    def on_cancel(self, viewport) -> None:
        had = self._busy()
        self._reset()
        viewport.update()
        if not had and self.on_cancelled:
            self.on_cancelled()

    def _finish(self, corners) -> None:
        try:
            corners = plotgeo.clean(corners)
            reason = plotgeo.why_not(corners)
            if reason:
                compat.flash(self.viewport, f"Not closed — {reason}", 8000)
                return
            self._reset()
            self.on_done(corners)
        except Exception as e:  # noqa: BLE001 — say it, never lose it
            compat.log_error(f"{type(self).__name__}._finish")
            compat.flash(self.viewport, f"Not drawn — {type(e).__name__}: "
                         f"{e} (written to the ArchXQ log)", 12000)

    # overridden
    def _reset(self) -> None: ...
    def _busy(self) -> bool: return False


def draw_plot_preview(viewport, painter, corners, heights, closing,
                      z0: float = 0.0, active: int | None = None,
                      dims: bool = True) -> None:
    """The plot table's outline over the model: orange sides (the closing
    one dashed), a numbered badge on every corner, side lengths. The
    table's current row (``active``): its corner and the side leaving it
    in blue, thicker."""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QColor, QFont, QPen
    n = len(corners)
    if n < 3:
        return
    px = [compat.to_pixel(viewport, x, y, z0 + h)
          for (x, y), h in zip(corners, heights)]
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    for i in range(n):
        a, b = px[i], px[(i + 1) % n]
        if not a or not b:
            continue
        on = i == active
        pen = QPen(QColor(ACTIVE if on else ACCENT), 6 if on else 3)
        if closing is not None and i == closing % n:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(*a), QPointF(*b))
    font = QFont(painter.font())
    font.setPointSize(9)
    font.setBold(True)
    painter.setFont(font)
    for i, p in enumerate(px):
        if not p:
            continue
        s = 13 if i == active else 10
        r = QRectF(p[0] - s, p[1] - s, 2 * s, 2 * s)
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(QColor(ACTIVE if i == active else ACCENT))
        painter.drawEllipse(r)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(r, Qt.AlignCenter, str(i + 1))
    painter.restore()
    if dims:
        draw_plot_dims(viewport, painter, corners, heights, z0)


SETBACK_INK = "#2f7df6"     # the buildable area and its setbacks
DIG_INK = "#8a5a2b"         # an excavation's figures (earth)


ELEV_INK = "#3f6b2a"        # the ground's elevations (natural terrain)


def elev_text(z: float) -> str:
    """An elevation as a drawing writes it: ±0.00, +1.50, −3.00."""
    if abs(z) < 0.005:
        return "±0.00"
    return f"{'+' if z > 0 else '−'}{abs(z):.2f}"


def draw_spot(viewport, painter, x, y, z, text: str, ink: str) -> None:
    """An elevation mark: a small ▽ on the point, its value beside it."""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QColor, QFont, QPen, QPolygonF
    c = compat.to_pixel(viewport, x, y, z)
    if not c:
        return
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    col = QColor(ink)
    tri = QPolygonF([QPointF(c[0] - 6, c[1] - 10), QPointF(c[0] + 6, c[1] - 10),
                     QPointF(c[0], c[1])])
    painter.setPen(QPen(col, 1.4))
    painter.setBrush(QColor(255, 255, 255, 235))
    painter.drawPolygon(tri)
    f = QFont(painter.font())
    f.setPointSize(8)
    f.setBold(True)
    painter.setFont(f)
    fm = painter.fontMetrics()
    w, h = fm.horizontalAdvance(text) + 8, fm.height() + 2
    r = QRectF(c[0] + 8, c[1] - 10 - h / 2, w, h)
    painter.setPen(QPen(col, 1))
    painter.setBrush(QColor(255, 255, 255, 230))
    painter.drawRoundedRect(r, 3, 3)
    painter.setPen(col)
    painter.drawText(r, Qt.AlignCenter, text)
    painter.restore()


SURVEY_INK = "#1f7a8c"      # survey points (measured ground)
SURVEY_OFF = "#8a8f98"      # a survey point outside the plot (not used)


def draw_survey(viewport, painter, plot, z0: float = 0.0, active=None,
                points=None) -> None:
    """The survey points: a dot on the ground and its elevation; one
    outside the plot greyed (kept, but it doesn't shape the ground).
    ``points`` (a window's preview) stands in for the plot's own;
    ``active`` = the index lit (the window's current row)."""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QColor, QFont, QPen
    pts = points if points is not None else plot.get("survey") or []
    if not pts:
        return
    used = {(round(s[0], 4), round(s[1], 4))
            for s in plotgeo.survey_inside(plot["corners"], pts)}
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    f = QFont(painter.font())
    f.setPointSize(8)
    f.setBold(True)
    painter.setFont(f)
    fm = painter.fontMetrics()
    for i, s in enumerate(pts):
        c = compat.to_pixel(viewport, s[0], s[1], z0 + s[2])
        if not c:
            continue
        ink = QColor(ACTIVE if i == active else SURVEY_INK
                     if (round(s[0], 4), round(s[1], 4)) in used
                     else SURVEY_OFF)
        r = 5.0 if i == active else 3.5
        painter.setPen(QPen(QColor(255, 255, 255, 220), 1.2))
        painter.setBrush(ink)
        painter.drawEllipse(QPointF(c[0], c[1]), r, r)
        text = elev_text(s[2])
        w, h = fm.horizontalAdvance(text) + 6, fm.height()
        box = QRectF(c[0] + 6, c[1] - h - 2, w, h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 200))
        painter.drawRoundedRect(box, 3, 3)
        painter.setPen(ink)
        painter.drawText(box, Qt.AlignCenter, text)
    painter.restore()


CONTOUR_INK = "#9a6a32"     # contour lines: the surveyor's brown


def draw_contours(viewport, painter, plot, z0: float = 0.0,
                  step: float | None = None, points=None) -> None:
    """The natural ground's contour lines (thin; every 5th thicker, with
    its elevation) — where the ground WAS, also across a pit or a fill.
    ``step`` / ``points`` (a window's preview) stand in for the plot's."""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QColor, QFont, QPen
    survey = points if points is not None else plot.get("survey") or ()
    tin = plotgeo.ground_tin(plot["corners"], plot["heights"],
                             plot["breaks"], survey)
    lines = plotgeo.contours(tin, step or plot.get("contour", 0.5))
    if not lines:
        return
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    f = QFont(painter.font())
    f.setPointSize(7)
    f.setBold(True)
    painter.setFont(f)
    fm = painter.fontMetrics()
    ink = QColor(CONTOUR_INK)
    for z, major, pts in lines:
        px = [compat.to_pixel(viewport, x, y, z0 + zz + 0.01)
              for x, y, zz in pts]
        col = QColor(ink)
        col.setAlpha(235 if major else 150)
        painter.setPen(QPen(col, 1.8 if major else 1.0))
        for a, b in zip(px, px[1:]):
            if a and b:
                painter.drawLine(QPointF(*a), QPointF(*b))
        if major and len(px) >= 2:
            m = px[len(px) // 2]
            if m:
                text = elev_text(z)
                w, h = fm.horizontalAdvance(text) + 6, fm.height()
                r = QRectF(m[0] - w / 2, m[1] - h / 2, w, h)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(255, 255, 255, 210))
                painter.drawRoundedRect(r, 3, 3)
                painter.setPen(ink)
                painter.drawText(r, Qt.AlignCenter, text)
    painter.restore()


def draw_plot_elevations(viewport, painter, corners, heights,
                         z0: float = 0.0) -> None:
    """The natural ground's elevation at every corner of the plot."""
    for (x, y), h in zip(corners, heights):
        draw_spot(viewport, painter, x, y, z0 + h, elev_text(h), ELEV_INK)


def draw_dig_elevations(viewport, painter, doc, z0: float = 0.0) -> None:
    """Every excavation's floor elevation at its corners (a ramp: where it
    starts and where it arrives); a corner left at the ground's own height
    shows nothing — the plot's mark says it."""
    from . import terrain
    plot = doc.get("plot")
    if not plot:
        return
    for d in terrain.opened(doc):
        fill = terrain.is_fill(d)
        bots = terrain.dig_bottoms(d, doc)
        shown = set()
        pairs = list(zip(d["corners"], bots))
        if max(bots) - min(bots) < 0.005:
            pairs = pairs[:1]                # a flat floor: one mark is enough
        for q, b in pairs:
            g = terrain.ground_at(plot, q)
            z = max(b, g) if fill else min(b, g)
            if abs(g - z) < 0.005:
                continue                     # at the ground: nothing changed
            key = (round(q[0], 2), round(q[1], 2))
            if key in shown:
                continue
            shown.add(key)
            draw_spot(viewport, painter, q[0], q[1], z, elev_text(z),
                      DIG_INK)


def draw_dig_dims(viewport, painter, doc, z0: float = 0.0) -> None:
    """Every excavation: its sides' lengths (on the ground, outside the
    pit) and how deep it is, in the middle of its floor. A fill: its
    sides on the platform, and how high it stands (▲)."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QFont, QPen
    from . import terrain
    plot = doc.get("plot")
    if not plot:
        return
    for d in terrain.opened(doc):
        fill = terrain.is_fill(d)
        pts = d["corners"]
        ground = [terrain.ground_at(plot, q) for q in pts]
        bots = terrain.dig_bottoms(d, doc)
        draw_plot_dims(viewport, painter, pts,
                       [max(b, g) for b, g in zip(bots, ground)] if fill
                       else ground, z0)
        deep = [(b - g) if fill else (g - b) for g, b in zip(ground, bots)]
        cx = sum(q[0] for q in pts) / len(pts)
        cy = sum(q[1] for q in pts) / len(pts)
        c = compat.to_pixel(viewport, cx, cy, sum(bots) / len(bots))
        if not c:
            continue
        lo, hi = min(deep), max(deep)
        arrow = "▲" if fill else "▼"
        text = (f"{arrow} {hi:.2f}" if hi - lo < 0.005
                else f"{arrow} {lo:.2f} … {hi:.2f}")
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        f = QFont(painter.font())
        f.setPointSize(9)
        f.setBold(True)
        painter.setFont(f)
        fm = painter.fontMetrics()
        w, h = fm.horizontalAdvance(text) + 12, fm.height() + 4
        r = QRectF(c[0] - w / 2, c[1] - h / 2, w, h)
        painter.setPen(QPen(QColor(DIG_INK), 1))
        painter.setBrush(QColor(255, 255, 255, 235))
        painter.drawRoundedRect(r, 4, 4)
        painter.setPen(QColor(DIG_INK))
        painter.drawText(r, Qt.AlignCenter, text)
        painter.restore()


def draw_setbacks(viewport, painter, plot, z0: float = 0.0,
                  dims: bool = True) -> None:
    """The buildable area (dashed, on the ground) and, with ``dims``, each
    setback measured from its side (a short line in, and the distance)."""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QColor, QFont, QPen
    pts, hs, br = plot["corners"], plot["heights"], plot["breaks"]
    _roles, dists, area = plotgeo.setbacks_of(plot)
    if all(d is None for d in dists):
        return

    def px(p):
        return compat.to_pixel(viewport, p[0], p[1],
                               z0 + plotgeo.height_at(pts, hs, br, p,
                                                      plot.get("survey") or ())
                               + 0.02)

    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    ink = QColor(SETBACK_INK)
    if area:
        q = [px(p) for p in area]
        painter.setPen(QPen(ink, 2.2, Qt.DashLine))
        for i in range(len(q)):
            a, b = q[i], q[(i + 1) % len(q)]
            if a and b:
                painter.drawLine(QPointF(*a), QPointF(*b))
    if dims:
        font = QFont(painter.font())
        font.setPointSize(8)
        painter.setFont(font)
        fm = painter.fontMetrics()
        n = len(pts)
        for i in range(n):
            d = dists[i]
            if not d:
                continue
            a, b = pts[i], pts[(i + 1) % n]
            nx, ny = plotgeo.outward_normal(a, b)
            # a third of the way along: clear of the plot's own length label
            m = (a[0] + (b[0] - a[0]) * 0.3, a[1] + (b[1] - a[1]) * 0.3)
            pa, pb = px(m), px((m[0] - nx * d, m[1] - ny * d))
            if not pa or not pb:
                continue
            painter.setPen(QPen(ink, 1.4))
            painter.drawLine(QPointF(*pa), QPointF(*pb))
            for p in (pa, pb):
                painter.setBrush(ink)
                painter.drawEllipse(QPointF(*p), 2.5, 2.5)
            text = f"{d:.2f}"
            w, h = fm.horizontalAdvance(text) + 8, fm.height() + 2
            c = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
            r = QRectF(c[0] + 6, c[1] - h / 2, w, h)
            painter.setPen(QPen(ink, 1))
            painter.setBrush(QColor(255, 255, 255, 230))
            painter.drawRoundedRect(r, 3, 3)
            painter.setPen(ink)
            painter.drawText(r, Qt.AlignCenter, text)
    painter.restore()


def draw_plot_dims(viewport, painter, corners, heights=None,
                   z0: float = 0.0) -> None:
    """The length of every side of a drawn plot, just outside that side
    (light pills: a standing dimension, not a live measurement). Lengths
    are measured in plan, as on a deed."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QFont, QPen
    n = len(corners)
    if n < 3:
        return
    hs = list(heights or []) or [0.0] * n
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    font = QFont(painter.font())
    font.setPointSize(9)
    painter.setFont(font)
    fm = painter.fontMetrics()
    for i in range(n):
        a, b = corners[i], corners[(i + 1) % n]
        L = math.dist(a, b)
        if L < 0.01:
            continue
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        mz = z0 + (hs[i] + hs[(i + 1) % n]) / 2
        # outward (the outline is CCW): to the right of a → b
        nx, ny = (b[1] - a[1]) / L, -(b[0] - a[0]) / L
        pm = compat.to_pixel(viewport, mx, my, mz)
        po = compat.to_pixel(viewport, mx + nx, my + ny, mz)
        if not pm or not po:
            continue
        dx, dy = po[0] - pm[0], po[1] - pm[1]
        dl = math.hypot(dx, dy) or 1.0
        cx, cy = pm[0] + dx / dl * 16, pm[1] + dy / dl * 16
        text = _m(L)
        w, h = fm.horizontalAdvance(text) + 10, fm.height() + 2
        r = QRectF(cx - w / 2, cy - h / 2, w, h)
        painter.setPen(QPen(QColor(0, 0, 0, 60), 1))
        painter.setBrush(QColor(255, 255, 255, 225))
        painter.drawRoundedRect(r, 4, 4)
        painter.setPen(QColor("#1f2937"))
        painter.drawText(r, Qt.AlignCenter, text)
    painter.restore()


class PlotRectTool(_PlotTool):
    name = "ArchXQ plot"
    icon = "rectangle"
    vcb_label = "Dimensions"
    vcb_comma_lists = True

    def _reset(self) -> None:
        self.first: list[float] | None = None
        self.pending = None     # a size typed before the first corner
        self.diag = None
        self._sync()

    def _anchor(self):
        return self.first

    def _sized(self, p) -> list[float]:
        """The opposite corner at the typed size, toward ``p``'s quadrant."""
        a, b = self._loc(self.first), self._loc(p)
        sx = 1 if b[0] >= a[0] else -1
        sy = 1 if b[1] >= a[1] else -1
        return self._wld([a[0] + sx * self.pending[0],
                          a[1] + sy * self.pending[1]])

    def _labels(self):
        if self.first is None or self.hover is None:
            return []
        a, h = self._loc(self.first), self._loc(self.hover)
        c = self._wld([h[0], a[1]])
        return [((self.first, c), _m(abs(h[0] - a[0])), None),
                ((c, self.hover), _m(abs(h[1] - a[1])), None)]

    def _sync(self) -> None:
        # a rectangle has no chain: only its first corner anchors inference
        self._sync_protocol([self.first] if self.first else [], self.hover)
        self.chain_first_point = None

    def _busy(self) -> bool:
        return self.first is not None

    def on_click(self, ctx) -> None:
        p = self._pick(ctx)
        if self.first is None:
            self.first = p
            self._sync()
            self._show_hint()
            return
        self._finish(self._rect(self.first, self._sized(p) if self.pending
                                else p))

    def on_value(self, viewport, value) -> bool:
        if not isinstance(value, tuple) or len(value) < 2:
            return False
        w, h = abs(value[0]), abs(value[1])
        if self.first is None:
            # typed before the first corner (his case, 2026-10-05): kept —
            # the click places it, the side the cursor goes to it grows
            self.pending = (w, h)
            compat.flash(viewport, f"{w:.2f} × {h:.2f} m kept — click the "
                         "first corner, then click the side it grows to", 8000)
            viewport.update()
            return True
        # lay it toward the quadrant the cursor is in (in the tool's frame)
        a = self._loc(self.first)
        hx = self._loc(self.hover) if self.hover else [a[0] + 1, a[1] + 1]
        sx = 1 if hx[0] >= a[0] else -1
        sy = 1 if hx[1] >= a[1] else -1
        self._finish(self._rect(self.first,
                                self._wld([a[0] + sx * w, a[1] + sy * h])))
        return True

    def rubber_band_lines(self):
        if self.first is None or self.hover is None:
            return []
        h = self._sized(self.hover) if self.pending else self.hover
        c = [self._P(p) for p in self._rect(self.first, h)]
        return [(c[i], c[(i + 1) % 4]) for i in range(4)]

    def value_label(self):
        if self.first is None or self.hover is None:
            return None              # the host reads "" as a label
        a = self._loc(self.first)
        b = self._loc(self._sized(self.hover) if self.pending
                      else self.hover)
        w = abs(b[0] - a[0])
        h = abs(b[1] - a[1])
        # the host reads a tuple: (text, …) — a bare str shows its 1st char
        return (f"{w:.2f} × {h:.2f} m   ({w * h:.1f} m²)", None)

    def status_clause(self) -> str:
        if self.pending:
            return (f"{self.noun} {self.pending[0]:.2f} × "
                    f"{self.pending[1]:.2f} m: click "
                    + ("the first corner" if self.first is None else
                       "the side it grows to") + "  ·  Esc = cancel")
        return (f"{self.noun}: click the first corner" if self.first is None
                else f"{self.noun}: click the opposite corner, or type "
                "width;depth "
                "+ Enter  ·  Esc = cancel")


class PlotPolyTool(_PlotTool):
    name = "ArchXQ plot"
    icon = "geopath"
    vcb_label = "Length"
    diagonal = True                   # ArchXQ's 45° pull, beside the axes

    def _reset(self) -> None:
        self.pts: list[list[float]] = []
        self.diag = None
        self._sync()

    def _anchor(self):
        return self.pts[-1] if self.pts else None

    def _align_sources(self):
        return list(self.pts)

    def _labels(self):
        if not self.pts or self.hover is None:
            return []
        return [((self.pts[-1], self.hover),
                 _m(math.dist(self.pts[-1], self.hover)), None)]

    def _sync(self) -> None:
        self._sync_protocol(self.pts, self.hover)

    def _busy(self) -> bool:
        return bool(self.pts)

    def _near_first(self, p, ctx=None) -> bool:
        """The click closes when the MOUSE is by the first corner — read on
        the screen, before any pull: a magnet on a nearby edge (a pit's
        corner under the first one) or the 45° pull moved the picked point
        away and the close was missed (his complaint, 2026-10-01)."""
        if len(self.pts) < 3:
            return False
        a = compat.to_pixel(self.viewport, *self.pts[0])
        if a is None:
            return False
        here = []
        scr = getattr(ctx, "screen", None)
        if scr is not None:
            here.append((scr.x(), scr.y()))
        b = compat.to_pixel(self.viewport, *p)
        if b is not None:
            here.append(b)
        return any(math.dist(a, h) <= CLOSE_PX for h in here)

    def _add(self, p) -> None:
        if self.pts and math.dist(self.pts[-1], p) <= plotgeo.EPS:
            return
        if plotgeo.new_edge_crosses(self.pts, p):
            compat.flash(self.viewport, "That edge would cross the plot — "
                         "pick another point", 4000)
            return
        self.pts.append(p)
        self._sync()
        self._show_hint()

    def on_hover(self, ctx) -> None:
        super().on_hover(ctx)
        if self._near_first(self.hover, ctx):
            # by the first corner: the rubber band shows the close
            self.hover = list(self.pts[0])
            self._sync()

    def on_click(self, ctx) -> None:
        p = self._pick(ctx)
        snap = getattr(ctx, "snap", None)
        if (getattr(snap, "kind", "") == "close" and len(self.pts) >= 3) \
                or self._near_first(p, ctx):
            self._close()
            return
        self._add(p)

    def on_double_click(self, ctx) -> None:
        self.on_click(ctx)
        if len(self.pts) >= 3:
            self._close()

    def _close(self) -> None:
        # closing edge must not cross either
        if len(self.pts) >= 3 and plotgeo.new_edge_crosses(
                self.pts[1:], self.pts[0]):
            compat.flash(self.viewport, "Closing there would cross the plot",
                         4000)
            return
        self._finish(list(self.pts))

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
        typing = bool(compat.typed_value(viewport))
        if typing:
            return False             # Enter / Backspace belong to the value
        if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_C):
            # C closes — and is kept from the host, where C is the Circle
            if len(self.pts) >= 3:
                self._close()
            elif key == Qt.Key_C:
                compat.flash(viewport, "Three corners at least before "
                             "closing", 3000)
            return len(self.pts) >= 3 or key == Qt.Key_C
        if key == Qt.Key_Backspace and self.pts:
            self.pts.pop()
            self._sync()
            viewport.update()
            return True
        return False

    def rubber_band_lines(self):
        # open until closed (C / Enter / first corner): no line back to it
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
            return f"{self.noun}: click the first corner"
        if len(self.pts) < 3:
            return (f"{self.noun}: click the next corner, or type a length "
                    "+ Enter  "
                    "·  Backspace = undo corner  ·  Esc = cancel")
        return (f"{self.noun}: next corner  ·  C, Enter, double-click or the "
                "first "
                "corner = close  ·  Backspace = undo corner  ·  Esc = cancel")


class PlotCentreRectTool(_PlotTool):
    """Rectangle from its centre: click the centre, then a corner — or
    type «width;depth» (the whole sizes) + Enter."""
    name = "ArchXQ plot"
    icon = "rectangle_center"
    vcb_label = "Dimensions"
    vcb_comma_lists = True

    def _reset(self) -> None:
        self.centre: list[float] | None = None
        self.pending = None     # a size typed before the centre
        self.diag = None
        self._sync()

    def _anchor(self):
        return self.centre

    def _corners(self, c, h) -> list[list[float]]:
        lc, lh = self._loc(c), self._loc(h)
        dx, dy = abs(lh[0] - lc[0]), abs(lh[1] - lc[1])
        return [self._wld(q) for q in plotgeo.rectangle(
            [lc[0] - dx, lc[1] - dy], [lc[0] + dx, lc[1] + dy])]

    def _labels(self):
        if self.centre is None or self.hover is None:
            return []
        q = self._corners(self.centre, self.hover)
        return [((q[0], q[1]), _m(math.dist(q[0], q[1])), None),
                ((q[1], q[2]), _m(math.dist(q[1], q[2])), None)]

    def _sync(self) -> None:
        self._sync_protocol([self.centre] if self.centre else [], self.hover)
        self.chain_first_point = None

    def _busy(self) -> bool:
        return self.centre is not None

    def on_click(self, ctx) -> None:
        p = self._pick(ctx)
        if self.centre is None and self.pending:
            self.centre = p                  # the size was typed first
            self._place(*self.pending)
            return
        if self.centre is None:
            self.centre = p
            self._sync()
            self._show_hint()
            return
        self._finish(self._corners(self.centre, p))

    def on_value(self, viewport, value) -> bool:
        if not isinstance(value, tuple) or len(value) < 2:
            return False
        if self.centre is None:
            # typed before the centre: kept — the click places it
            self.pending = (abs(value[0]), abs(value[1]))
            compat.flash(viewport, f"{self.pending[0]:.2f} × "
                         f"{self.pending[1]:.2f} m kept — click its centre",
                         8000)
            viewport.update()
            return True
        self._place(abs(value[0]), abs(value[1]))
        return True

    def _place(self, width: float, depth: float) -> None:
        c = self._loc(self.centre)
        w, d = width / 2, depth / 2
        self._finish([self._wld(q) for q in plotgeo.rectangle(
            [c[0] - w, c[1] - d], [c[0] + w, c[1] + d])])

    def rubber_band_lines(self):
        if self.centre is None or self.hover is None:
            return []
        q = [self._P(p) for p in self._corners(self.centre, self.hover)]
        return [(q[i], q[(i + 1) % 4]) for i in range(4)]

    def value_label(self):
        if self.centre is None or self.hover is None:
            return None
        a, b = self._loc(self.centre), self._loc(self.hover)
        w = 2 * abs(b[0] - a[0])
        d = 2 * abs(b[1] - a[1])
        return (f"{w:.2f} × {d:.2f} m   ({w * d:.1f} m²)", None)

    def status_clause(self) -> str:
        if self.pending and self.centre is None:
            return (f"{self.noun} {self.pending[0]:.2f} × "
                    f"{self.pending[1]:.2f} m: click its centre  ·  "
                    "Esc = cancel")
        return (f"{self.noun}: click the centre" if self.centre is None else
                f"{self.noun}: click a corner, or type width;depth + Enter  ·  "
                "Esc = cancel")


class PlotRotRectTool(_PlotTool):
    """Rotated rectangle: click the first corner, the second (the first
    side — any direction, or a typed length), then how wide (the cursor's
    side, or a typed width)."""
    name = "ArchXQ plot"
    icon = "rotated_rect"
    vcb_label = "Length"
    diagonal = True

    def _reset(self) -> None:
        self.a: list[float] | None = None
        self.b: list[float] | None = None
        self.diag = None
        self._sync()

    def _anchor(self):
        return self.b if self.b is not None else self.a

    def _width(self, h) -> float:
        """Signed width: how far the cursor is from side a→b (left = +)."""
        a, b = self.a, self.b
        L = math.dist(a, b) or 1.0
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        return (h[0] - a[0]) * -uy + (h[1] - a[1]) * ux

    def _corners(self, w: float) -> list[list[float]]:
        a, b = self.a, self.b
        L = math.dist(a, b) or 1.0
        nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        return [list(a), list(b), [b[0] + nx * w, b[1] + ny * w],
                [a[0] + nx * w, a[1] + ny * w]]

    def _labels(self):
        if self.a is None or self.hover is None:
            return []
        if self.b is None:
            return [((self.a, self.hover), _m(math.dist(self.a, self.hover)),
                     None)]
        q = self._corners(self._width(self.hover))
        return [((q[0], q[1]), _m(math.dist(q[0], q[1])), None),
                ((q[1], q[2]), _m(math.dist(q[1], q[2])), None)]

    def _sync(self) -> None:
        pts = [p for p in (self.a, self.b) if p is not None]
        self._sync_protocol(pts, self.hover)
        self.chain_first_point = None

    def _busy(self) -> bool:
        return self.a is not None

    def on_click(self, ctx) -> None:
        p = self._pick(ctx)
        if self.a is None:
            self.a = p
        elif self.b is None:
            if math.dist(self.a, p) <= plotgeo.EPS:
                return
            self.b = p
        else:
            self._finish(self._corners(self._width(p)))
            return
        self._sync()
        self._show_hint()

    def on_value(self, viewport, value) -> bool:
        if self.a is None or self.hover is None \
                or not isinstance(value, (int, float)):
            return False
        L = abs(float(value))
        if self.b is None:                       # the first side's length
            dx, dy = self.hover[0] - self.a[0], self.hover[1] - self.a[1]
            d = math.hypot(dx, dy)
            if d < 1e-9 or L <= plotgeo.EPS:
                return False
            self.b = [round(self.a[0] + dx / d * L, 4),
                      round(self.a[1] + dy / d * L, 4)]
            self._sync()
            self._show_hint()
            return True
        side = 1.0 if self._width(self.hover) >= 0 else -1.0
        self._finish(self._corners(side * L))
        return True

    def rubber_band_lines(self):
        if self.a is None or self.hover is None:
            return []
        if self.b is None:
            return [(self._P(self.a), self._P(self.hover))]
        q = [self._P(p) for p in self._corners(self._width(self.hover))]
        return [(q[i], q[(i + 1) % 4]) for i in range(4)]

    def value_label(self):
        if self.a is None or self.hover is None:
            return None
        if self.b is None:
            return (f"{math.dist(self.a, self.hover):.2f} m", None)
        return (f"{abs(self._width(self.hover)):.2f} m", None)

    def status_clause(self) -> str:
        if self.a is None:
            return f"{self.noun}: click the first corner"
        if self.b is None:
            return (f"{self.noun}: click the second corner (the first side), "
                    "or type its length + Enter  ·  Esc = cancel")
        return (f"{self.noun}: move to the side and click the width, or type "
                "it "
                "+ Enter  ·  Esc = cancel")


class PlotCircleTool(_PlotTool):
    """A circle: click the centre, then the edge — or type the radius +
    Enter. It becomes a polygon of ``segments()`` sides (the options bar
    sets how many)."""
    name = "ArchXQ circle"
    icon = "circle"
    vcb_label = "Radius"
    segments = staticmethod(lambda: 24)

    def _reset(self) -> None:
        self.centre: list[float] | None = None
        self.diag = None
        self._sync()

    def _anchor(self):
        return self.centre

    def _ring(self, r: float):
        return plotgeo.circle(self.centre, r, self.segments())

    def _labels(self):
        if self.centre is None or self.hover is None:
            return []
        return [((self.centre, self.hover),
                 "R " + _m(math.dist(self.centre, self.hover)), None)]

    def _sync(self) -> None:
        self._sync_protocol([self.centre] if self.centre else [], self.hover)
        self.chain_first_point = None

    def _busy(self) -> bool:
        return self.centre is not None

    def on_click(self, ctx) -> None:
        p = self._pick(ctx)
        if self.centre is None:
            self.centre = p
            self._sync()
            self._show_hint()
            return
        r = math.dist(self.centre, p)
        if r > plotgeo.EPS:
            self._finish(self._ring(r))

    def on_value(self, viewport, value) -> bool:
        if self.centre is None or not isinstance(value, (int, float)) \
                or value <= 0:
            return False
        self._finish(self._ring(float(value)))
        return True

    def rubber_band_lines(self):
        if self.centre is None or self.hover is None:
            return []
        r = math.dist(self.centre, self.hover)
        if r <= plotgeo.EPS:
            return []
        q = [self._P(p) for p in self._ring(r)]
        return [(q[i], q[(i + 1) % len(q)]) for i in range(len(q))]

    def value_label(self):
        if self.centre is None or self.hover is None:
            return None
        r = math.dist(self.centre, self.hover)
        return (f"R {r:.2f} m   (Ø {2 * r:.2f} m)", None)

    def status_clause(self) -> str:
        return (f"{self.noun}: click the centre" if self.centre is None else
                f"{self.noun}: click the edge, or type the radius + Enter  ·  "
                "Esc = cancel")


class PlotRampTool(_PlotTool):
    """A RAMP: click where it starts (on the ground — the street side),
    then which way it goes down. Its length comes by itself: the drop
    (start → end) over the slope; a typed length rules instead. The
    options bar gives the width, the slope and where it ends — the floor
    of the excavation it runs into, a level, an elevation.

    ArchXQ hands: ``width()``, ``slope()`` (%), ``start_z(p)`` (the ground
    there), ``end_z(p | None)`` (where it ends — None: before knowing the
    end point); the finished ramp goes to ``on_done(corners, bottoms)``."""
    name = "ArchXQ ramp"
    icon = "line"
    vcb_label = "Length"
    diagonal = True
    width = staticmethod(lambda: 3.0)
    slope = staticmethod(lambda: 20.0)
    start_z = staticmethod(lambda p: 0.0)
    end_z = staticmethod(lambda p: -3.0)

    def _reset(self) -> None:
        self.start: list[float] | None = None
        self.diag = None
        self._sync()

    def _anchor(self):
        return self.start

    def ramp(self, toward, length: float | None = None):
        """(corners CCW, bottoms, length, start z, end z) from the start
        toward a point — or None (no direction yet, or it would not go
        down)."""
        s = self.start
        dx, dy = toward[0] - s[0], toward[1] - s[1]
        d = math.hypot(dx, dy)
        if d < 1e-6:
            return None
        ux, uy = dx / d, dy / d
        nx, ny = -uy, ux
        z0 = self.start_z(s)
        k = max(float(self.slope()), 0.1) / 100.0
        if length is None:
            ze = self.end_z(None)
            L = (z0 - ze) / k
            for _ in range(2):            # it may end inside another pit
                if L <= 0:
                    return None
                ze = self.end_z([s[0] + ux * L, s[1] + uy * L])
                L = (z0 - ze) / k
        else:
            L = float(length)
            ze = self.end_z([s[0] + ux * L, s[1] + uy * L])
        if L <= 0.05 or z0 - ze <= 0.0:
            return None
        e = [s[0] + ux * L, s[1] + uy * L]
        w = max(float(self.width()), 0.5) / 2
        corners = [[s[0] + nx * w, s[1] + ny * w], [s[0] - nx * w, s[1] - ny * w],
                   [e[0] - nx * w, e[1] - ny * w], [e[0] + nx * w, e[1] + ny * w]]
        bottoms = [z0, z0, ze, ze]
        if plotgeo.signed_area(corners) < 0:
            corners.reverse()
            bottoms.reverse()
        corners = [[round(x, 4), round(y, 4)] for x, y in corners]
        return corners, [round(z, 3) for z in bottoms], L, z0, ze

    def _labels(self):
        if self.start is None or self.hover is None:
            return []
        r = self.ramp(self.hover)
        if r is None:
            return []
        _c, _b, L, z0, ze = r
        dx, dy = self.hover[0] - self.start[0], self.hover[1] - self.start[1]
        d = math.hypot(dx, dy) or 1.0
        end = [self.start[0] + dx / d * L, self.start[1] + dy / d * L]
        return [((self.start, end), f"{_m(L)}  ·  {(z0 - ze) / L * 100:.1f}%",
                 None)]

    def _sync(self) -> None:
        self._sync_protocol([self.start] if self.start else [], self.hover)
        self.chain_first_point = None

    def _busy(self) -> bool:
        return self.start is not None

    def _place(self, r) -> None:
        if r is None:
            compat.flash(self.viewport, "The ramp has to go down: its end "
                         "must be lower than where it starts", 5000)
            return
        corners, bottoms = r[0], r[1]
        self._reset()
        self.on_done(corners, bottoms)

    def on_click(self, ctx) -> None:
        p = self._pick(ctx)
        if self.start is None:
            self.start = p
            self._sync()
            self._show_hint()
            return
        self._place(self.ramp(p))

    def on_value(self, viewport, value) -> bool:
        if self.start is None or self.hover is None \
                or not isinstance(value, (int, float)) or value <= 0:
            return False
        self._place(self.ramp(self.hover, float(value)))
        return True

    def rubber_band_lines(self):
        if self.start is None or self.hover is None:
            return []
        r = self.ramp(self.hover)
        if r is None:
            return [(self._P(self.start), self._P(self.hover))]
        q = [self._P(p) for p in r[0]]
        return [(q[i], q[(i + 1) % 4]) for i in range(4)]

    def value_label(self):
        if self.start is None or self.hover is None:
            return None
        r = self.ramp(self.hover)
        if r is None:
            return ("— it must go down —", None)
        _c, _b, L, z0, ze = r
        return (f"{L:.2f} m  ·  {(z0 - ze) / L * 100:.1f}%  ·  "
                f"{z0:+.2f} → {ze:+.2f}", None)

    def status_clause(self) -> str:
        return ("Ramp: click where it starts (the street side, on the ground)"
                if self.start is None else
                "Ramp: click which way it goes down — its length comes from "
                "the slope; or type a length + Enter  ·  Esc = cancel")
