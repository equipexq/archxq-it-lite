# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The wall window's «Shape» tab (PLANO_CURVAS_E_FORMAS F2.7, 2026-11-13):
the wall seen from the front, its control corners to drag, and the tools —
Round corner, Chamfer, Notch, Bend side, Back to rectangle. The data and
every refusal are wallshape.py's; this only draws and asks.

``add_tab(dlg, wall, level, openings, joined)`` puts the tab in a
WallDialog; ``values(dlg, w)`` writes what it made into the record (OK:
one Ctrl+Z, as the rest of the window). Editing is the Pro's; the Lite
shows the drawing."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QWidget)

from . import look as L
from . import walls as W
from . import wallshape as WS
from .i18n import tr

BLUE = "#2f7df6"            # the Tools mock-up's blue (his choice, 2026-11)
HIT = 8                     # px: a click this close takes a corner / side
SNAP = 6                    # px: a drag this close to a line snaps to it
GRID = 0.01                 # m: no snap: this step

TOOLS = (("select", "Points"), ("round", "Round corner"),
         ("chamfer", "Chamfer"), ("notch", "Notch"), ("bend", "Bend side"))
SIZE_OF = {"round": ("Radius", WS.ROUND_R), "chamfer": ("Size", WS.CHAMFER),
           "notch": ("Corner radius", WS.NOTCH_R),
           "bend": ("Bulge", 0.30)}
TIPS = {"select": "Drag a corner or the middle of a side · Double-click a "
                  "side: a new point · Del: delete the point",
        "round": "Click a corner to round it",
        "chamfer": "Click a corner to cut it off",
        "notch": "Drag a rectangle over an edge of the wall: it is cut away "
                 "(over the top: a «U»; at an end: a «C»)",
        "bend": "Click a side to bend it into an arc (a negative bulge: "
                "outwards)"}


# ---- the drawing ------------------------------------------------------------------------
class ShapeCanvas(QWidget):
    """The wall from the front: s across, z up, its foot at the bottom."""

    def __init__(self, tab) -> None:
        super().__init__()
        self.tab = tab
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.drag = None            # ("corner", i, base) | ("side", …) | …
        self.hover = None

    # -- the mapping --------------------------------------------------------------------
    def _frame(self):
        prof = self.tab.prof
        Lw = prof["L"]
        top = max(WS.peak(prof), self.tab.ref_h) + 0.3
        m = 30.0
        w, h = max(self.width() - 2 * m, 10), max(self.height() - 2 * m, 10)
        k = min(w / max(Lw + 0.6, 0.1), h / top)
        x0 = m + (w - k * Lw) / 2
        y0 = m + h
        return k, x0, y0

    def to_px(self, s: float, z: float) -> QPointF:
        k, x0, y0 = self._frame()
        return QPointF(x0 + s * k, y0 - z * k)

    def to_sz(self, pt) -> tuple:
        k, x0, y0 = self._frame()
        return ((pt.x() - x0) / k, (y0 - pt.y()) / k)

    # -- what is under the mouse ------------------------------------------------------------
    def corner_at(self, pt) -> int | None:
        best = None
        for i, (s, z) in enumerate(self.tab.prof["ctrl"]):
            d = math.dist((pt.x(), pt.y()), (self.to_px(s, z).x(),
                                              self.to_px(s, z).y()))
            if d <= HIT and (best is None or d < best[0]):
                best = (d, i)
        return None if best is None else best[1]

    def side_at(self, pt, mid_only: bool = False) -> int | None:
        ctrl = self.tab.prof["ctrl"]
        n = len(ctrl)
        best = None
        for i in range(n):
            a = self.to_px(*ctrl[i])
            b = self.to_px(*ctrl[(i + 1) % n])
            if mid_only:
                m = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
                d = math.dist((pt.x(), pt.y()), (m.x(), m.y()))
            else:
                dx, dy = b.x() - a.x(), b.y() - a.y()
                LL = dx * dx + dy * dy or 1.0
                t = min(max(((pt.x() - a.x()) * dx + (pt.y() - a.y()) * dy)
                            / LL, 0.0), 1.0)
                d = math.dist((pt.x(), pt.y()),
                              (a.x() + dx * t, a.y() + dy * t))
            if d <= HIT and (best is None or d < best[0]):
                best = (d, i)
        return None if best is None else best[1]

    def snapped(self, s: float, z: float, skip=()) -> tuple:
        """(s, z) on the nearest corner's s / z, a floor, an opening's sill
        or head within SNAP px — else on the 1 cm step."""
        k, _x0, _y0 = self._frame()
        tol = SNAP / max(k, 1e-6)
        ss = [p[0] for i, p in enumerate(self.tab.prof["ctrl"])
              if i not in skip] + [0.0, self.tab.prof["L"]]
        zs = [p[1] for i, p in enumerate(self.tab.prof["ctrl"])
              if i not in skip] + self.tab.lines
        out = []
        for v, cand in ((s, ss), (z, zs)):
            near = min(cand, key=lambda c: abs(c - v), default=None)
            out.append(near if near is not None and abs(near - v) <= tol
                       else round(v / GRID) * GRID)
        return out[0], out[1]

    # -- painting --------------------------------------------------------------------------
    def paintEvent(self, _e) -> None:  # noqa: N802 — Qt's
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), L.colour(L.FIELD))
        prof = self.tab.prof
        Lw = prof["L"]
        # the floor, the slab over the level, the joined walls' tops
        for z, dash in [(0.0, False)] + [(z, True) for z in self.tab.lines]:
            a, b = self.to_px(-0.3, z), self.to_px(Lw + 0.3, z)
            p.setPen(L.pen(L.DIM, 1.0, dash))
            p.drawLine(a, b)
        # the wall
        pts, _arcs = WS.outline(prof, 0.0)
        path = QPainterPath()
        for j, (s, z) in enumerate(pts):
            q = self.to_px(s, z)
            path.moveTo(q) if j == 0 else path.lineTo(q)
        path.closeSubpath()
        p.setPen(QPen(L.colour(L.INK), 1.6))
        p.setBrush(QBrush(QColor(47, 125, 246, 40)))
        p.drawPath(path)
        # its openings (light grey)
        p.setBrush(QBrush(QColor(200, 204, 210, 70)))
        p.setPen(L.pen(L.MUTED, 1.0))
        for o in self.tab.openings:
            zs = float(o.get("sill", 0.0)) + self.tab.lift
            half = float(o["w"]) / 2
            a = self.to_px(float(o["pos"]) - half, zs + float(o["h"]))
            b = self.to_px(float(o["pos"]) + half, zs)
            p.drawRect(QRectF(a, b))
        # A and B
        for s, label in ((0.0, "A"), (Lw, "B")):
            q = self.to_px(s, 0.0)
            L.text(p, q.x() - 4, q.y() + 16, label, L.MUTED)
        if not self.tab.editable:
            p.end()
            return
        # the control corners (squares) and the sides' middles (diamonds)
        ctrl = prof["ctrl"]
        n = len(ctrl)
        sel = self.tab.sel
        for i, (s, z) in enumerate(ctrl):
            q = self.to_px(s, z)
            hot = i == sel or self.hover == ("corner", i)
            p.setPen(QPen(QColor(BLUE), 1.4))
            p.setBrush(QBrush(QColor(BLUE) if hot else L.colour(L.FIELD)))
            p.drawRect(QRectF(q.x() - 4, q.y() - 4, 8, 8))
        if self.tab.tool in ("select", "bend"):
            for i in range(2, n):
                a, b = self.to_px(*ctrl[i]), self.to_px(*ctrl[(i + 1) % n])
                m = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
                hot = self.hover == ("side", i)
                d = QPainterPath()
                d.moveTo(m.x(), m.y() - 5)
                d.lineTo(m.x() + 5, m.y())
                d.lineTo(m.x(), m.y() + 5)
                d.lineTo(m.x() - 5, m.y())
                d.closeSubpath()
                p.setPen(QPen(QColor(BLUE), 1.2))
                p.setBrush(QBrush(QColor(BLUE) if hot else L.colour(L.FIELD)))
                p.drawPath(d)
        if self.drag and self.drag[0] == "notch" and self.drag[2] is not None:
            a, b = self.to_px(*self.drag[1]), self.to_px(*self.drag[2])
            p.setPen(L.pen(L.ORANGE, 1.4, True))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(a, b).normalized())
        if sel is not None and 0 <= sel < n:
            s, z = ctrl[sel]
            q = self.to_px(s, z)
            L.text(p, q.x() + 8, q.y() - 8, f"{s:.2f} · {z:.2f}", BLUE)
        p.end()

    # -- the mouse ---------------------------------------------------------------------------
    def mousePressEvent(self, e) -> None:  # noqa: N802
        if not self.tab.editable or e.button() != Qt.LeftButton:
            return
        pt = e.position()
        tool = self.tab.tool
        i = self.corner_at(pt)
        if tool == "notch":
            self.drag = ("notch", self.to_sz(pt), None)
            return
        if tool in ("round", "chamfer"):
            if i is not None:
                v = self.tab.size_value()
                fn = WS.round_corner if tool == "round" else WS.chamfer
                self.tab.attempt(fn(self.tab.prof, i, v))
            return
        if tool == "bend":
            k = self.side_at(pt)
            if k is not None:
                self.tab.attempt(WS.bend_side(self.tab.prof, k,
                                              self.tab.size_value()))
            return
        if i is not None:
            self.tab.select(i)
            self.drag = ("corner", i, self.tab.prof)
            return
        k = self.side_at(pt, mid_only=True)
        if k is not None:
            self.drag = ("side", k, self.tab.prof, self.to_sz(pt))
            return
        self.tab.select(None)

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        pt = e.position()
        if self.drag is None:
            i = self.corner_at(pt)
            k = None if i is not None else self.side_at(pt, mid_only=True)
            hv = ("corner", i) if i is not None else \
                (("side", k) if k is not None else None)
            if hv != self.hover:
                self.hover = hv
                self.update()
            return
        kind = self.drag[0]
        if kind == "corner":
            _k, i, base = self.drag
            s, z = self.snapped(*self.to_sz(pt), skip=(i,))
            self.tab.attempt(WS.move_point(base, i, s, z), live=True)
        elif kind == "side":
            _k, i, base, start = self.drag
            ctrl = base["ctrl"]
            a, b = ctrl[i], ctrl[(i + 1) % len(ctrl)]
            Ls = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
            nx, nz = -(b[1] - a[1]) / Ls, (b[0] - a[0]) / Ls
            s, z = self.to_sz(pt)
            d = round(((s - start[0]) * nx + (z - start[1]) * nz) / GRID) \
                * GRID
            self.tab.attempt(WS.move_side(base, i, d), live=True)
        elif kind == "notch":
            self.drag = ("notch", self.drag[1], self.snapped(*self.to_sz(pt)))
            self.update()

    def mouseReleaseEvent(self, _e) -> None:  # noqa: N802
        d, self.drag = self.drag, None
        if d and d[0] == "notch" and d[2] is not None:
            (s0, z0), (s1, z1) = self.snapped(*d[1]), d[2]
            self.tab.attempt(WS.notch(self.tab.prof, s0, z0, s1, z1,
                                      self.tab.size_value()))
        self.update()

    def mouseDoubleClickEvent(self, e) -> None:  # noqa: N802
        if not self.tab.editable or self.tab.tool != "select":
            return
        k = self.side_at(e.position())
        if k is not None:
            self.tab.attempt(WS.add_point(self.tab.prof, k,
                                          self.to_sz(e.position())))

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if self.tab.editable and e.key() in (Qt.Key_Delete,
                                             Qt.Key_Backspace) \
                and self.tab.sel is not None:
            got = WS.delete_point(self.tab.prof, self.tab.sel)
            if got[0] is not None:
                self.tab.select(None)
            self.tab.attempt(got)
            return
        super().keyPressEvent(e)


# ---- the tab ----------------------------------------------------------------------------
class ShapeTab:
    """The tab's state: the shape being made (``prof``), the tool, the
    corner selected; whether it changed; whether it is back to a
    rectangle."""

    def __init__(self, wall: dict, level: dict, openings, joined) -> None:
        from . import edition
        from . import structure as S
        self.wall = wall
        self.openings = list(openings or ())
        self.joined = set(joined or ())
        self.lift = W.opening_lift(wall) - float(wall.get("base", 0.0) or 0.0)
        under = float(level.get("_under", level.get("height", 3.0)))
        self.ref_h = under
        self.lines = [under - float(wall.get("base", 0.0) or 0.0)]
        self.why_kind = WS.why_no_shape(wall)
        self.editable = self.why_kind is None and not edition.lite()
        prof = S.shape_now(wall) if self.why_kind is None else None
        if prof is None and self.why_kind is None:
            src = wall if wall.get("height", "level") != "level" else \
                dict(wall, height=under)
            prof = WS.from_top(src)
            if prof is not None and wall.get("height", "level") == "level" \
                    and W.top_of(wall) is None:
                prof["was"] = "level"
        if prof is None:                # (a curved wall…: a box to show)
            Lw = max(W.drawn(wall).L, 0.1)
            prof = {"ctrl": [[0, 0], [Lw, 0], [Lw, under], [0, under]],
                    "curves": {"r": {}, "arc": {}}, "L": round(Lw, 4),
                    "was": "level"}
        self.prof = prof
        self.tool = "select"
        self.sel = None
        self.changed = False
        self.rect = False               # «Back to rectangle» pressed
        self.canvas = None
        self.status = None
        self.size = None
        self.size_label = None
        self.f_s = self.f_z = None
        self.on_change = None           # the window's numbers, kept in step

    # -- checks beyond the shape's own ---------------------------------------------------------
    def _context_why(self, prof: dict) -> str | None:
        from . import structure as S
        w = dict(self.wall, profile=prof)
        for o in self.openings:
            if S.opening_room(o, w, self.openings, 3.0) is not None:
                return tr("\"{name}\" would stand outside the wall's shape",
                          name=o.get("name", "Opening"))
        for end, s in (("a", 0.0), ("b", prof["L"])):
            if end in self.joined:
                sl = WS.slice_at(prof, s)
                if len(sl) != 1 or sl[0][0] > 1e-6:
                    return tr("That end is joined to another wall — keep it "
                              "whole up to one height there")
        return None

    def attempt(self, got, live: bool = False) -> None:
        prof, why = got
        if prof is not None:
            why = self._context_why(prof)
        if why:
            self.say(tr(why), bad=True)
            return
        self.prof = prof
        self.changed = True
        self.rect = False
        self.say("")
        self._fields()
        self.canvas.update()
        self._told()

    def _told(self) -> None:
        if self.on_change is not None:
            try:
                self.on_change()
            except Exception:  # noqa: BLE001 — the numbers only
                pass

    def say(self, text: str, bad: bool = False) -> None:
        if self.status is not None:
            self.status.setText(text or tr(TIPS[self.tool]))
            self.status.setStyleSheet(f"color: {L.ORANGE if bad else L.MUTED};")

    def select(self, i) -> None:
        self.sel = i if i is not None and i >= 2 else None
        self._fields()
        self.canvas.update()

    def size_value(self) -> float:
        return float(self.size.value()) if self.size is not None else 0.3

    def set_tool(self, tool: str) -> None:
        self.tool = tool
        lab, v = SIZE_OF.get(tool, ("", 0.0))
        on = tool in SIZE_OF
        self.size.setVisible(on)
        self.size_label.setVisible(on)
        if on:
            self.size_label.setText(tr(lab))
            self.size.setValue(v)
        self.say("")
        self.canvas.update()

    def _fields(self) -> None:
        on = self.sel is not None
        for f in (self.f_s, self.f_z):
            f.setEnabled(on and self.editable)
        if on:
            s, z = self.prof["ctrl"][self.sel]
            for f, v in ((self.f_s, s), (self.f_z, z)):
                f.blockSignals(True)
                f.setValue(v)
                f.blockSignals(False)

    def typed(self, *_a) -> None:
        if self.sel is None:
            return
        self.attempt(WS.move_point(self.prof, self.sel, self.f_s.value(),
                                   self.f_z.value()))

    def to_rect(self) -> None:
        was = WS.to_rect(self.prof)
        h = self.ref_h if was == "level" else float(was) - float(
            self.wall.get("base", 0.0) or 0.0)
        Lw = self.prof["L"]
        self.prof = {"ctrl": [[0, 0], [Lw, 0], [Lw, h], [0, h]],
                     "curves": {"r": {}, "arc": {}}, "L": Lw, "was": was}
        self.rect = True
        self.changed = True
        self.sel = None
        self._fields()
        self.say("")
        self.canvas.update()
        self._told()


def add_tab(dlg, wall: dict, level: dict, openings=(), joined=()) -> None:
    """The «Shape» tab on a straight wall's window (``dlg.shape``)."""
    st = ShapeTab(wall, level, openings, joined)
    dlg.shape = st
    st.on_change = getattr(dlg, "_refresh", None)
    pg, lay = L.page()
    fold = L.Fold("Shape seen from the front", "wall.shape")
    fl = fold.form()
    st.canvas = ShapeCanvas(st)
    lay.addWidget(fold)
    fl.addRow(st.canvas)
    if st.why_kind:
        fl.addRow(L.hint(tr(st.why_kind)))
    elif not st.editable:
        fl.addRow(L.hint(tr("Editing the shape is in ArchXQ IT Pro")))
    if st.editable:
        tools = L.Chips(width=96)
        for v, text in TOOLS:
            tools.addItem(text, v)
        tools.setCurrentIndex(0)
        fl.addRow("Tool", tools)
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        st.size_label = QLabel("")
        st.size = L.metres(0.30, -5.0, 10.0, 0.05)
        rl.addWidget(st.size_label)
        rl.addWidget(st.size, 1)
        st.f_s = L.metres(0.0, 0.0, 1000.0, 0.01)
        st.f_z = L.metres(0.0, 0.0, 50.0, 0.01)
        rl.addWidget(QLabel(tr("Point along")))
        rl.addWidget(st.f_s, 1)
        rl.addWidget(QLabel(tr("up")))
        rl.addWidget(st.f_z, 1)
        fl.addRow(row)
        back = QPushButton(tr("Back to rectangle"))
        back.setObjectName("axqChip")
        back.setToolTip(tr("Its shape goes: a plain wall at the height it "
                           "had before"))
        back.clicked.connect(st.to_rect)
        fl.addRow(back)
        tools.currentIndexChanged.connect(
            lambda _i: st.set_tool(tools.currentData()))
        st.f_s.valueChanged.connect(st.typed)
        st.f_z.valueChanged.connect(st.typed)
        st.set_tool("select")
        st._fields()
    st.status = L.hint("")
    fl.addRow(st.status)
    st.say("")
    lay.addStretch(1)
    dlg.shape_tab = dlg.tabs.addTab(pg, "Shape", "geometry")


def values(dlg, w: dict) -> None:
    """The record ``w`` with what the tab made (nothing when it wasn't
    touched): a shape — its top gone, its height its peak — or back to a
    plain wall at the height it had."""
    st = getattr(dlg, "shape", None)
    if st is None or not st.changed or not st.editable:
        return
    base = float(w.get("base", 0.0) or 0.0)
    if st.rect:                         # «Back to rectangle»
        w.pop("profile", None)
        w.pop("top", None)
        was = st.prof.get("was", "level")
        w["height"] = was
        return
    h = WS.is_rect(st.prof)
    if h is not None:                   # just a rectangle: a plain wall
        w.pop("profile", None)
        w.pop("top", None)
        w["height"] = round(base + h, 4)
        return
    w["profile"] = WS.clean(st.prof) or st.prof
    w.pop("top", None)
    w["height"] = round(max(base + WS.peak(st.prof), 0.05), 4)
