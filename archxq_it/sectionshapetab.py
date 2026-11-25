# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The «Shape» tab of a column's / a pad footing's window (the shape editor,
phase 1 — 17/11/2026): its section seen from above, in its own frame, its
control corners to drag, and the wall Shape tab's tools — Round corner,
Chamfer, Notch, Bend side, Back to rectangle. The data and every refusal
are sectionshape.py's; this only draws and asks.

``add_tab(dlg, el, row)`` puts the tab in an ElementDialog (``dlg.sshape``);
``ShapeTab.apply(e)`` writes what it made into the record (OK: one Ctrl+Z,
as the rest of the window). Editing is the Pro's; the Lite shows the
drawing."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QPushButton, QSizePolicy, QWidget

from . import look as L
from . import sectionshape as SS
from .i18n import tr

BLUE = "#2f7df6"            # the Tools mock-up's blue (his choice, 2026-11)
HIT = 8                     # px: a click this close takes a corner / side
SNAP = 6                    # px: a drag this close to a line snaps to it
GRID = 0.005                # m: no snap: this step (5 mm)

TOOLS = (("select", "Points"), ("round", "Round corner"),
         ("chamfer", "Chamfer"), ("notch", "Notch"), ("bend", "Bend side"))
SIZE_OF = {"round": ("Radius", SS.ROUND_R), "chamfer": ("Size", SS.CHAMFER),
           "notch": ("Corner radius", SS.NOTCH_R),
           "bend": ("Bulge", SS.BEND)}
TIPS = {"select": "Drag a corner or the middle of a side · Double-click a "
                  "side: a new point · Del: delete the point",
        "round": "Click a corner to round it (a radius of half the side, on "
                 "every corner of a square: a circle)",
        "chamfer": "Click a corner to cut it off",
        "notch": "Drag a rectangle over an edge of the section: it is cut "
                 "away (over a corner: an «L»; over a side: a «U»)",
        "bend": "Click a side to bend it into an arc (a negative bulge: "
                "outwards)"}
WHY_ROW = ("A footing of a row: its pads are square, sized by the row (the "
           "Row part of its window)")


# ---- the drawing ------------------------------------------------------------------------
class SectionCanvas(QWidget):
    """The section from above, in its own frame: x across, y up, its
    insertion point marked."""

    def __init__(self, tab) -> None:
        super().__init__()
        self.tab = tab
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.drag = None            # ("corner", i, base) | ("side", …) | …
        self.hover = None
        self._fr = None             # the frame, held while dragging

    # -- the mapping --------------------------------------------------------------------
    def _frame(self):
        if self.drag is not None and self._fr is not None:
            return self._fr         # (still while a drag lasts)
        x0, y0, x1, y1 = SS.box(self.tab.prof)
        x0, y0 = min(x0, 0.0), min(y0, 0.0)
        x1, y1 = max(x1, 0.0), max(y1, 0.0)
        pad = max(x1 - x0, y1 - y0) * 0.18 + 0.02
        x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
        m = 24.0
        w = max(self.width() - 2 * m, 10)
        h = max(self.height() - 2 * m - 14, 10)
        k = min(w / max(x1 - x0, 1e-3), h / max(y1 - y0, 1e-3))
        ox = m + (w - k * (x1 - x0)) / 2 - x0 * k
        oy = m + (h + k * (y1 - y0)) / 2 + y0 * k
        self._fr = (k, ox, oy)
        return self._fr

    def to_px(self, x: float, y: float) -> QPointF:
        k, ox, oy = self._frame()
        return QPointF(ox + x * k, oy - y * k)

    def to_xy(self, pt) -> tuple:
        k, ox, oy = self._frame()
        return ((pt.x() - ox) / k, (oy - pt.y()) / k)

    # -- what is under the mouse ------------------------------------------------------------
    def corner_at(self, pt) -> int | None:
        best = None
        for i, (x, y) in enumerate(self.tab.prof["ctrl"]):
            q = self.to_px(x, y)
            d = math.dist((pt.x(), pt.y()), (q.x(), q.y()))
            if d <= HIT and (best is None or d < best[0]):
                best = (d, i)
        return None if best is None else best[1]

    def side_mid(self, i: int) -> QPointF:
        """A side's middle on the screen — on its arc when it is bent."""
        ctrl = self.tab.prof["ctrl"]
        n = len(ctrl)
        a, b = ctrl[i], ctrl[(i + 1) % n]
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        h = (self.tab.prof.get("curves") or {}).get("arc", {}).get(str(i))
        if h:
            Ls = math.dist(a, b) or 1.0
            mx -= (b[1] - a[1]) / Ls * float(h)
            my += (b[0] - a[0]) / Ls * float(h)
        return self.to_px(mx, my)

    def side_at(self, pt, mid_only: bool = False) -> int | None:
        ctrl = self.tab.prof["ctrl"]
        n = len(ctrl)
        best = None
        for i in range(n):
            if mid_only:
                m = self.side_mid(i)
                d = math.dist((pt.x(), pt.y()), (m.x(), m.y()))
            else:
                a = self.to_px(*ctrl[i])
                b = self.to_px(*ctrl[(i + 1) % n])
                dx, dy = b.x() - a.x(), b.y() - a.y()
                LL = dx * dx + dy * dy or 1.0
                t = min(max(((pt.x() - a.x()) * dx + (pt.y() - a.y()) * dy)
                            / LL, 0.0), 1.0)
                d = math.dist((pt.x(), pt.y()),
                              (a.x() + dx * t, a.y() + dy * t))
                m = self.side_mid(i)
                d = min(d, math.dist((pt.x(), pt.y()), (m.x(), m.y())))
            if d <= HIT and (best is None or d < best[0]):
                best = (d, i)
        return None if best is None else best[1]

    def snapped(self, x: float, y: float, skip=()) -> tuple:
        """(x, y) on the nearest corner's x / y or the insertion point's
        axes within SNAP px — else on the 5 mm step."""
        k, _ox, _oy = self._frame()
        tol = SNAP / max(k, 1e-6)
        pts = [p for i, p in enumerate(self.tab.prof["ctrl"]) if i not in skip]
        xs = [p[0] for p in pts] + [0.0]
        ys = [p[1] for p in pts] + [0.0]
        out = []
        for v, cand in ((x, xs), (y, ys)):
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
        # its own axes through its insertion point
        o = self.to_px(0.0, 0.0)
        p.setPen(L.pen(L.DIM, 1.0, True))
        p.drawLine(QPointF(0, o.y()), QPointF(self.width(), o.y()))
        p.drawLine(QPointF(o.x(), 0), QPointF(o.x(), self.height()))
        # the section
        path = QPainterPath()
        for j, (x, y) in enumerate(SS.fine(prof)):
            q = self.to_px(x, y)
            path.moveTo(q) if j == 0 else path.lineTo(q)
        path.closeSubpath()
        p.setPen(QPen(L.colour(L.INK), 1.6))
        p.setBrush(QBrush(QColor(47, 125, 246, 40)))
        p.drawPath(path)
        # the insertion point: a small cross in a circle
        p.setPen(QPen(L.colour(L.MUTED), 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(o, 5, 5)
        p.drawLine(QPointF(o.x() - 8, o.y()), QPointF(o.x() + 8, o.y()))
        p.drawLine(QPointF(o.x(), o.y() - 8), QPointF(o.x(), o.y() + 8))
        # its box, below
        x0, y0, x1, y1 = SS.box(prof)
        from . import compat
        L.text(p, 10, self.height() - 8,
               f"{compat.fmt_len(x1 - x0)} × {compat.fmt_len(y1 - y0)}  ·  "
               f"{SS.area(prof):.4f} m²", L.MUTED)
        if not self.tab.editable:
            p.end()
            return
        # the control corners (squares) and the sides' middles (diamonds)
        ctrl = prof["ctrl"]
        n = len(ctrl)
        sel = self.tab.sel
        for i, (x, y) in enumerate(ctrl):
            q = self.to_px(x, y)
            hot = i == sel or self.hover == ("corner", i)
            p.setPen(QPen(QColor(BLUE), 1.4))
            p.setBrush(QBrush(QColor(BLUE) if hot else L.colour(L.FIELD)))
            p.drawRect(QRectF(q.x() - 4, q.y() - 4, 8, 8))
        if self.tab.tool in ("select", "bend"):
            for i in range(n):
                m = self.side_mid(i)
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
            x, y = ctrl[sel]
            q = self.to_px(x, y)
            L.text(p, q.x() + 8, q.y() - 8,
                   f"{compat.fmt_len(x)} · {compat.fmt_len(y)}", BLUE)
        p.end()

    # -- the mouse ---------------------------------------------------------------------------
    def mousePressEvent(self, e) -> None:  # noqa: N802
        if not self.tab.editable or e.button() != Qt.LeftButton:
            return
        self._fr = None
        self._frame()
        pt = e.position()
        tool = self.tab.tool
        i = self.corner_at(pt)
        if tool == "notch" and i is not None:
            # a POINT taken with the Notch on: it moves (as the wall's
            # Shape, 20/11/2026)
            self.tab.select(i)
            self.drag = ("corner", i, self.tab.prof)
            return
        if tool == "notch":
            self.drag = ("notch", self.snapped(*self.to_xy(pt)), None)
            return
        if tool in ("round", "chamfer"):
            if i is not None:
                v = self.tab.size_value()
                fn = SS.round_corner if tool == "round" else SS.chamfer
                self.tab.attempt(fn(self.tab.prof, i, v))
            return
        if tool == "bend":
            k = self.side_at(pt)
            if k is not None:
                self.tab.attempt(SS.bend_side(self.tab.prof, k,
                                              self.tab.size_value()))
            return
        if i is not None:
            self.tab.select(i)
            self.drag = ("corner", i, self.tab.prof)
            return
        k = self.side_at(pt, mid_only=True)
        if k is not None:
            self.drag = ("side", k, self.tab.prof, self.to_xy(pt))
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
        if not (e.buttons() & Qt.LeftButton):
            # its release never came (as the wall's Shape, 20/11/2026):
            # finished now
            self.mouseReleaseEvent(e)
            return
        kind = self.drag[0]
        if kind == "corner":
            _k, i, base = self.drag
            x, y = self.snapped(*self.to_xy(pt), skip=(i,))
            self.tab.attempt(SS.move_point(base, i, x, y), live=True)
        elif kind == "side":
            _k, i, base, start = self.drag
            ctrl = base["ctrl"]
            a, b = ctrl[i], ctrl[(i + 1) % len(ctrl)]
            Ls = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
            nx, ny = -(b[1] - a[1]) / Ls, (b[0] - a[0]) / Ls
            x, y = self.to_xy(pt)
            d = round(((x - start[0]) * nx + (y - start[1]) * ny) / GRID) \
                * GRID
            self.tab.attempt(SS.move_side(base, i, d), live=True)
        elif kind == "notch":
            self.drag = ("notch", self.drag[1], self.snapped(*self.to_xy(pt)))
            self.update()

    def mouseReleaseEvent(self, _e) -> None:  # noqa: N802
        d, self.drag = self.drag, None
        if d and d[0] == "notch" and d[2] is not None:
            (x0, y0), (x1, y1) = d[1], d[2]
            self.tab.attempt(SS.notch(self.tab.prof, x0, y0, x1, y1,
                                      self.tab.size_value()))
        self._fr = None
        self.update()

    def mouseDoubleClickEvent(self, e) -> None:  # noqa: N802
        if not self.tab.editable or self.tab.tool != "select":
            return
        k = self.side_at(e.position())
        if k is not None:
            self.tab.attempt(SS.add_point(self.tab.prof, k,
                                          self.to_xy(e.position())))

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if self.tab.editable and e.key() in (Qt.Key_Delete,
                                             Qt.Key_Backspace) \
                and self.tab.sel is not None:
            got = SS.delete_point(self.tab.prof, self.tab.sel)
            if got[0] is not None:
                self.tab.select(None)
            self.tab.attempt(got)
            return
        super().keyPressEvent(e)


# ---- the tab ----------------------------------------------------------------------------
class ShapeTab:
    """The tab's state: the shape being made (``prof``), the tool, the
    corner selected; whether it was changed here."""

    def __init__(self, dlg, el: dict, row=None) -> None:
        from . import edition
        self.dlg = dlg
        self.why = WHY_ROW if (el.get("type") == "footing" and row) else None
        self.editable = self.why is None and not edition.lite()
        self.prof = SS.from_record(el)
        #: where its frame hangs: the insertion point the shape was read
        #: off (the window may move it — «Back to rectangle»…)
        self.origin = (float(el.get("x", 0.0)), float(el.get("y", 0.0)))
        self.tool = "select"
        self.sel = None
        self.changed = False
        self.canvas = None
        self.status = None
        self.size = None
        self.size_label = None
        self.f_x = self.f_y = None
        self._busy = False
        # its FORM (a column's — sectionlib.py, phase 4): a tube, narrowing,
        # entasis; written by ``apply`` when changed here
        from . import sectionlib as SL
        self.is_col = el.get("type") == "column"
        self.form = {"hollow": SL.hollow(el), "tp": SL.taper(el),
                     "ent": SL.entasis(el)}
        self.form_changed = False
        self.arm = None
        self.f_hollow = self.f_tp = self.f_ent = None
        self.f_fam = self.f_size = None

    # -- in step with the window ----------------------------------------------------------
    def follow(self, e: dict) -> None:
        """Not changed here: the shape the window's numbers make now."""
        if self.changed:
            return
        try:
            self.prof = SS.from_record(e)
            self.origin = (float(e["x"]), float(e["y"]))
        except (KeyError, TypeError, ValueError):
            return
        self.sel = None
        self._fields()
        if self.canvas is not None:
            self.canvas.update()

    def reset(self) -> None:
        """The window's own section chosen again (Rectangle, Round, «Back
        to square»): what was made here is dropped."""
        self.changed = False

    def apply(self, e: dict) -> dict:
        """The record with the shape made here (as it is when untouched)."""
        if self.form_changed and self.editable and self.is_col:
            from . import sectionlib as SL
            e = SL.clean_form(e, self.form)
        if not self.changed or not self.editable:
            return e
        # (its own frame: off the insertion point it was read off, turned
        # by the angle the window has now)
        return SS.to_record(dict(e, x=self.origin[0], y=self.origin[1]),
                            self.prof)

    # -- an edit ------------------------------------------------------------------------
    def attempt(self, got, live: bool = False) -> None:
        prof, why = got
        if not why and self.is_col and self.form["hollow"] > 0:
            # a tube: room left inside the new outline (its wall as it is)
            from . import sectionlib as SL
            if SL.inner(SS.fine(prof), self.form["hollow"]) is None:
                why = SL.WHY_HOLLOW
        if why:
            self.say(tr(why), bad=True)
            return
        self.prof = prof
        self.changed = True
        self.say("")
        if self.sel is not None and self.sel >= len(prof["ctrl"]):
            self.sel = None
        self._fields()
        self.canvas.update()
        self._told()

    def _told(self) -> None:
        """The window's Geometry and its view follow the shape."""
        self._busy = True
        try:
            self.dlg._shape_edited(self)
        except Exception:  # noqa: BLE001 — the numbers only
            pass
        finally:
            self._busy = False

    def say(self, text: str, bad: bool = False) -> None:
        if self.status is not None:
            self.status.setText(text or tr(TIPS[self.tool]))
            self.status.setStyleSheet(f"color: {L.ORANGE if bad else L.MUTED};")

    def select(self, i) -> None:
        self.sel = i
        self._fields()
        self.canvas.update()

    def size_value(self) -> float:
        return float(self.size.value()) if self.size is not None else 0.05

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
        if self.f_x is None:
            return
        on = self.sel is not None
        for f in (self.f_x, self.f_y):
            f.setEnabled(on and self.editable)
        if on:
            x, y = self.prof["ctrl"][self.sel]
            for f, v in ((self.f_x, x), (self.f_y, y)):
                f.blockSignals(True)
                f.setValue(v)
                f.blockSignals(False)

    def typed(self, *_a) -> None:
        if self.sel is None:
            return
        self.attempt(SS.move_point(self.prof, self.sel, self.f_x.value(),
                                   self.f_y.value()))

    def to_rect(self) -> None:
        """«Back to rectangle»: the box round the shape, where it is."""
        x0, y0, x1, y1 = SS.box(self.prof)
        self.sel = None
        self.attempt((SS.make([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]),
                      None))

    # -- the section library (phase 4) ---------------------------------------------------
    def _centred(self, prof: dict) -> dict:
        """``prof`` (centred on 0, 0) moved to the middle of the box the
        shape has now: the library's section stands where the column is."""
        x0, y0, x1, y1 = SS.box(self.prof)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        return SS.make([[p[0] + cx, p[1] + cy] for p in prof["ctrl"]],
                       prof.get("curves"))

    def put_ready(self, kind: str) -> None:
        """An «L», a «T», a «Cross» filling the box the shape has now."""
        from . import sectionlib as SL
        x0, y0, x1, y1 = SS.box(self.prof)
        prof, why = SL.ready(kind, x1 - x0, y1 - y0,
                             self.arm.value() if self.arm is not None
                             else SL.ARM)
        self.sel = None
        self.attempt((self._centred(prof) if prof else None, why))

    def put_steel(self) -> None:
        """The steel section picked (its family and size), at the table's
        sizes, where the column is."""
        from . import sectionlib as SL
        name = f"{self.f_fam.currentText()} {self.f_size.currentText()}"
        prof = SL.steel(name)
        if prof is None:
            return
        self.sel = None
        self.attempt((self._centred(prof), None))
        if self.changed and SL.steel_of({"shape": "poly",
                                         "pts": self.prof["ctrl"],
                                         "curves": self.prof["curves"]}):
            self.say(tr("{n}: its table sizes").format(n=name))

    def fill_sizes(self) -> None:
        """The family's sizes in the size list."""
        from . import sectionlib as SL
        tab = dict(SL.FAMILIES)[self.f_fam.currentText()]
        self.f_size.blockSignals(True)
        self.f_size.clear()
        self.f_size.addItems([str(n) for n in tab])
        self.f_size.setCurrentIndex(min(2, len(tab) - 1))
        self.f_size.blockSignals(False)

    def form_typed(self, *_a) -> None:
        """Tube, Narrows to, Entasis: a form refused stays as it was."""
        from . import sectionlib as SL
        f = {"hollow": round(self.f_hollow.value(), 4),
             "tp": round(self.f_tp.value() / 100.0, 3),
             "ent": self.f_ent.isChecked()}
        self.f_ent.setEnabled(f["tp"] < 1.0)
        rec = SL.clean_form({}, f)
        why = SL.why_form(rec, SS.fine(self.prof)) if rec else None
        if f["hollow"] > 0 and "hollow" not in rec:
            why = SL.WHY_HOLLOW            # (under 3 mm: no tube)
        if why:
            self.say(tr(why), bad=True)
            return
        self.form = {"hollow": rec.get("hollow", 0.0),
                     "tp": rec.get("tp", 1.0), "ent": bool(rec.get("ent"))}
        self.form_changed = True
        self.say("")
        try:                               # (the window's view, its numbers)
            self.dlg._sync()
        except Exception:  # noqa: BLE001
            pass


def _library(st: ShapeTab, lay, el: dict) -> None:
    """A column's SECTION LIBRARY and its FORM (phase 4): ready concrete
    sections, the steel tables, a tube, narrowing, entasis. The Lite reads
    its form only."""
    from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout,
                                   QSpinBox)
    from . import sectionlib as SL
    if not st.editable:
        bits = []
        if st.form["hollow"] > 0:
            bits.append(tr("Tube, its wall {t} mm").format(
                t=f"{round(st.form['hollow'] * 1000, 1):g}"))
        if st.form["tp"] < 1.0:
            bits.append(tr("narrows to {p} %").format(
                p=round(st.form["tp"] * 100)))
            if st.form["ent"]:
                bits.append(tr("with entasis"))
        if bits:
            lay.addWidget(L.hint(" · ".join(bits)))
        return
    fold = L.Fold("Section library", "column.library")
    fl = fold.form()
    lay.addWidget(fold)
    # concrete: L, T, Cross over the box it has, its arms typed
    row = QWidget()
    rl = QHBoxLayout(row)
    rl.setContentsMargins(0, 0, 0, 0)
    rl.setSpacing(6)
    for key, text in SL.READY:
        b = QPushButton(tr(text))
        b.setObjectName("axqChip")
        b.setToolTip(tr("Fills the box the section has now, its arms as "
                        "thick as «Arms» — then drag and type as any "
                        "shape"))
        b.clicked.connect(lambda _c=False, k=key: st.put_ready(k))
        rl.addWidget(b)
    rl.addStretch(1)
    fl.addRow(tr("Concrete"), row)
    st.arm = L.metres(SL.ARM, SL.MIN_ARM, 2.0, 0.01)
    st.arm.setToolTip(tr("The thickness of the L's, T's or Cross's arms"))
    fl.addRow(tr("Arms"), st.arm)
    # steel: the European tables (EN 10365)
    row = QWidget()
    rl = QHBoxLayout(row)
    rl.setContentsMargins(0, 0, 0, 0)
    rl.setSpacing(6)
    st.f_fam = QComboBox()
    st.f_fam.addItems([fam for fam, _t in SL.FAMILIES])
    st.f_size = QComboBox()
    put = QPushButton(tr("Put"))
    put.setObjectName("axqChip")
    put.setToolTip(tr("The steel section at its table sizes (depth, width, "
                      "web, flange and root radius), where the column is: "
                      "its depth up, its width across — turn it with the "
                      "column's angle"))
    for w in (st.f_fam, st.f_size, put):
        rl.addWidget(w)
    rl.addStretch(1)
    fl.addRow(tr("Steel"), row)
    st.fill_sizes()
    st.f_fam.currentIndexChanged.connect(lambda _i: st.fill_sizes())
    put.clicked.connect(st.put_steel)
    # its form: a tube, narrowing, entasis
    fold = L.Fold("Tube and narrowing", "column.form")
    ff = fold.form()
    lay.addWidget(fold)
    st.f_hollow = L.metres(st.form["hollow"], 0.0, 1.0, 0.001)
    st.f_hollow.setToolTip(tr("A tube: its wall's thickness, the inside its "
                              "outline moved in by it (0: solid)"))
    ff.addRow(tr("Tube wall"), st.f_hollow)
    st.f_tp = QSpinBox()
    st.f_tp.setRange(round(SL.TAPER_MIN * 100), 100)
    st.f_tp.setSuffix(" %")
    st.f_tp.setValue(round(st.form["tp"] * 100))
    st.f_tp.setToolTip(tr("Its top as a share of its foot: the section "
                          "scaled round its centre (100 %: straight)"))
    ff.addRow(tr("Narrows to"), st.f_tp)
    st.f_ent = QCheckBox(tr("Entasis"))
    st.f_ent.setChecked(st.form["ent"])
    st.f_ent.setEnabled(st.form["tp"] < 1.0)
    st.f_ent.setToolTip(tr("The classical swelling: straight for its lower "
                           "third, then a gentle curve to its top"))
    ff.addRow("", st.f_ent)
    ff.addRow(L.hint(tr("A base and a capital stay as they are; the shaft "
                        "between them narrows.")))
    st.f_hollow.valueChanged.connect(st.form_typed)
    st.f_tp.valueChanged.connect(st.form_typed)
    st.f_ent.toggled.connect(st.form_typed)


def add_tab(dlg, el: dict, row=None) -> None:
    """The «Shape» tab on a column's / a pad footing's window
    (``dlg.sshape``)."""
    st = ShapeTab(dlg, el, row)
    dlg.sshape = st
    pg, lay = L.page()
    fold = L.Fold("Section seen from above", f"{el['type']}.shape")
    fl = fold.form()
    st.canvas = SectionCanvas(st)
    lay.addWidget(fold)
    fl.addRow(st.canvas)
    if st.why:
        fl.addRow(L.hint(tr(st.why)))
    elif not st.editable:
        fl.addRow(L.hint(tr("Editing the shape is in ArchXQ IT Pro")))
    if st.editable:
        tools = L.Chips(wrap=3, width=96)
        for v, text in TOOLS:
            tools.addItem(text, v)
        tools.setCurrentIndex(0)
        fl.addRow("Tool", tools)
        # (one row each: the page stays as narrow as the window's)
        st.size_label = QLabel("")
        st.size = L.metres(0.05, -2.0, 5.0, 0.01)
        fl.addRow(st.size_label, st.size)
        st.f_x = L.metres(0.0, -10.0, 10.0, 0.01)
        st.f_y = L.metres(0.0, -10.0, 10.0, 0.01)
        for f in (st.f_x, st.f_y):
            f.setToolTip(tr("Click a point of the shape, then type where "
                            "it goes"))
        fl.addRow(tr("Point across"), st.f_x)
        fl.addRow(tr("Point up"), st.f_y)
        back = QPushButton(tr("Back to rectangle"))
        back.setObjectName("axqChip")
        back.setToolTip(tr("The box round the shape, where it is (OK keeps "
                           "it; Ctrl+Z undoes it)"))
        back.clicked.connect(st.to_rect)
        fl.addRow(back)
        fl.addRow(L.hint(tr("Its own frame: across and up as it stands before "
                            "its angle; the cross is its insertion point. "
                            "A base and a capital are built on a rectangle "
                            "and a round column only.")))
        tools.currentIndexChanged.connect(
            lambda _i: st.set_tool(tools.currentData()))
        st.f_x.valueChanged.connect(st.typed)
        st.f_y.valueChanged.connect(st.typed)
        st.set_tool("select")
        st._fields()
    st.status = L.hint("")
    fl.addRow(st.status)
    st.say("")
    if st.is_col:
        _library(st, lay, el)
    lay.addStretch(1)
    dlg.sshape_tab = dlg.tabs.addTab(pg, "Shape", "geometry")
