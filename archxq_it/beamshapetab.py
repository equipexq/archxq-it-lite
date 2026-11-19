# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The «Shape» tab of a beam's window (the shape editor, phase 2 —
17/11/2026): its section (rectangle, L, inverted T, I), its shape seen from
the side (a haunch, a notch at its ends, an arched soffit) and its curve
in plan — with a drawing of both views. The data and every refusal are
beamshape.py's; this only draws and asks.

``add_tab(dlg, el, row)`` puts the tab in an ElementDialog (``dlg.bshape``);
``BeamShapeTab.apply(e)`` writes it into the record (OK: one Ctrl+Z, as the
rest of the window). Editing is the Pro's; the Lite shows it. A column
row's beam takes the row's: shown, not edited here."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import beamshape as BS
from . import look as L
from .i18n import tr

FILL = "#8a8f9655"
WHY_ROW = ("One of a column row's beams: it takes the row's — a shaped "
           "beam is a beam of its own")

SECTIONS = (("rect", "Rectangle"), ("L", "L"), ("Lr", "L (other side)"),
            ("invT", "Inverted T"), ("I", "I"))
ELEVS = (("none", "Straight"), ("haunch", "Haunch"), ("notch", "Notch"),
         ("arch", "Arched soffit"))
ENDS = (("both", "Both ends"), ("a", "End A"), ("b", "End B"))
SIDE_LABELS = {"haunch": ("Length", "Deeper by"),
               "notch": ("Length", "Notch depth"),
               "arch": ("Flat at each end", "Rise")}


def _pic_sec(kind):
    def draw(p, r, _on):
        e = {"w": 0.3, "h": 0.6, "sec": kind, "tf": 0.12, "tw": 0.12}
        _section(p, QRectF(14, 4, 32, 36), e, 0.6)
    return draw


def _pic_elev(kind):
    def draw(p, r, _on):
        e = {"a": [0, 0], "b": [4, 0], "w": 0.3, "h": 0.6, "elev": kind,
             "el": 0.9, "ed": 0.3 if kind != "arch" else 0.25}
        _side(p, QRectF(6, 10, 48, 24), e, 0.6, 0.0)
    return draw


def _section(p: QPainter, box: QRectF, e: dict, depth: float) -> None:
    """Its section, centred in ``box`` (left of a → b on the left)."""
    w = float(e["w"])
    k = min(box.width() / max(w, 1e-6), box.height() / max(depth, 1e-6))
    cx = box.center().x()
    y0 = box.center().y() + depth * k / 2           # its foot

    def z(a):
        return a[1] if a[0] == "b" else depth - a[1]
    for lo, hi, zl, zh in BS.bands(e):
        # seen from end A: its left on the left
        x0, x1 = cx - hi * k, cx - lo * k
        L.poly(p, [(x0, y0 - z(zl) * k), (x1, y0 - z(zl) * k),
                   (x1, y0 - z(zh) * k), (x0, y0 - z(zh) * k)],
               L.INK, 1.6, fill=FILL)


def _side(p: QPainter, box: QRectF, e: dict, depth: float,
          rise: float) -> None:
    """Seen from its side, a on the left: its top, its soffit."""
    pts = BS.depth_points(e, depth)
    Lg = max(BS.length(e), 1e-6)
    up = [(f * Lg, rise * f) for f, _d in (pts[0], pts[-1])]
    down = [(f * Lg, rise * f - d) for f, d in reversed(pts)]
    zs = [z for _x, z in up + down]
    zmax, zmin = max(zs), min(zs)
    kx = box.width() / Lg
    # (a long beam's depth a few pixels: up to 3× taller, to be read)
    ky = min(box.height() / max(zmax - zmin, 1e-6), kx * 3)
    y0 = box.center().y() - (zmax - zmin) * ky / 2
    L.poly(p, [(box.left() + x * kx, y0 + (zmax - z) * ky)
               for x, z in up + down], L.INK, 1.6, fill=FILL)


class Preview(QWidget):
    """The two views: from the side (a on the left) and its section."""

    def __init__(self, tab) -> None:
        super().__init__()
        self.tab = tab
        self.e = None
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def show_record(self, e: dict) -> None:
        self.e = dict(e)
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802
        if not self.e:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        e = self.e
        r = QRectF(self.rect()).adjusted(8, 8, -8, -22)
        side = QRectF(r.left(), r.top(), r.width() * 0.68, r.height())
        sec = QRectF(side.right() + 16, r.top(),
                     r.right() - side.right() - 16, r.height())
        try:
            _side(p, side, e, float(e["h"]), BS.rise(e))
            _section(p, sec.adjusted(4, 10, -4, -10), e, BS.min_depth(e)
                     if BS.elev(e) == "notch" else float(e["h"]))
        except Exception:  # noqa: BLE001 — a shape that can't be: nothing
            pass
        p.setPen(L.pen(L.DIM, 1.0))
        y = self.height() - 8
        p.drawText(QPointF(side.left(), y), tr("Seen from the side (A ← → B)"))
        p.drawText(QPointF(sec.left(), y), tr("Section"))
        p.end()


class BeamShapeTab:
    def __init__(self, dlg, el: dict) -> None:
        from . import edition
        self.dlg = dlg
        self.el = dict(el)
        self.why = WHY_ROW if el.get("row") else None
        self.editable = not edition.lite() and self.why is None
        self._busy = False
        self._ed_set = "ed" in el
        self._sec, self._elev = BS.section(el), BS.elev(el)   # (as it was)

    # -- the record ----------------------------------------------------------------
    def apply(self, e: dict) -> dict:
        """``e`` with the tab's shape (as it was, when not editable)."""
        if not self.editable:
            return e
        r = dict(e)
        for k in ("sec", "tf", "tw", "elev", "el", "ed", "eends"):
            r.pop(k, None)
        s = self.f_sec.currentData()
        if s != "rect":
            r.update(sec=s, tf=round(self.f_tf.value(), 3),
                     tw=round(self.f_tw.value(), 3))
        k = self.f_elev.currentData()
        if k != "none":
            r.update(elev=k, el=round(self.f_el.value(), 3),
                     ed=round(self.f_ed.value(), 3))
            if k != "arch":
                r["eends"] = self.f_ends.currentData()
        return BS.with_bulge(r, self.f_bulge.value())

    def show(self, e: dict) -> None:
        """The window's record now: the drawing, why not."""
        self.preview.show_record(e)
        why = BS.why_shape(e) if e.get("type") == "beam" else None
        self.status.setText(tr(why) if why else self._summary(e))

    def _summary(self, e: dict) -> str:
        bits = []
        if BS.section(e) != "rect":
            bits.append(tr(dict(SECTIONS)[BS.section(e)]))
        if BS.elev(e) != "none":
            bits.append(tr(dict(ELEVS)[BS.elev(e)]))
        R = BS.radius(e)
        if R is not None:
            from . import compat
            bits.append("R " + compat.fmt_len(R))
        if BS.is_sloped(e):
            bits.append(f"{BS.slope_deg(e):+.1f}°")
        return " · ".join(bits) if bits else tr("A plain beam")

    # -- the fields ------------------------------------------------------------------
    def changed(self, *_a) -> None:
        if self._busy:
            return
        self._enable()
        self.dlg._sync()

    def sec_changed(self, *_a) -> None:
        """A section chosen: its flange and web for this beam's size."""
        if self._busy:
            return
        e = self.dlg._record()
        s, was = self.f_sec.currentData(), self._sec
        self._sec = s
        if s != "rect" and was != s:
            d = dict(e, sec=s)
            d.pop("tf", None)
            d.pop("tw", None)
            self._busy = True
            self.f_tf.setValue(BS.default_tf(d))
            self.f_tw.setValue(BS.default_tw(d))
            self._busy = False
        self.changed()

    def elev_changed(self, *_a) -> None:
        """A side shape chosen: its usual length and depth (until typed)."""
        if self._busy:
            return
        e = self.dlg._record()
        k, was = self.f_elev.currentData(), self._elev
        self._elev = k
        if k != "none":
            d = dict(e, elev=k)
            d.pop("el", None)
            d.pop("ed", None)
            self._busy = True
            if not self._ed_set or was == "none":
                self.f_ed.setValue(BS.default_ed(d))
                self.f_el.setValue(BS.default_el(d))
            self._busy = False
        self._label_side()
        self.changed()

    def ed_typed(self, *_a) -> None:
        if not self._busy:
            self._ed_set = True
        self.changed()

    def _label_side(self) -> None:
        a, b = SIDE_LABELS.get(self.f_elev.currentData(),
                               ("Length", "Depth"))
        self.l_el.setText(tr(a))
        self.l_ed.setText(tr(b))

    def _enable(self) -> None:
        on = self.editable
        s, k = self.f_sec.currentData(), self.f_elev.currentData()
        for w in (self.f_sec, self.f_elev, self.f_bulge):
            w.setEnabled(on)
        for w in (self.f_tf, self.f_tw):
            w.setEnabled(on and s != "rect")
        for w in (self.f_el, self.f_ed):
            w.setEnabled(on and k != "none")
        self.f_ends.setEnabled(on and k in ("haunch", "notch"))


def add_tab(dlg, el: dict, row=None) -> None:
    """The «Shape» tab on a beam's window (``dlg.bshape``)."""
    from PySide6.QtWidgets import QLabel
    st = BeamShapeTab(dlg, el)
    dlg.bshape = st
    pg, lay = L.page()
    st.preview = Preview(st)
    lay.addWidget(st.preview)
    if st.why:
        lay.addWidget(L.hint(tr(st.why)))
    elif not st.editable:
        lay.addWidget(L.hint(tr("Editing the shape is in ArchXQ IT Pro")))
    # its section
    fold = L.Fold("Section", "beam.shape.section")
    fl = fold.form()
    st.f_sec = L.Chips(wrap=3, width=96)
    for v, text in SECTIONS:
        st.f_sec.addItem(text, v, pic=_pic_sec(v))
    st.f_sec.setCurrentIndex(st.f_sec.findData(BS.section(el)))
    fl.addRow(st.f_sec)
    st.f_tf = L.metres(BS.flange(el), BS.MIN_PART, 0.5, 0.01)
    st.f_tf.field.setMaximum(2.0)
    st.f_tf.setValue(BS.flange(el))
    st.f_tw = L.metres(BS.web(el), BS.MIN_PART, 1.0, 0.01)
    st.f_tw.field.setMaximum(3.0)
    st.f_tw.setValue(BS.web(el))
    fl.addRow(tr("Flange"), st.f_tf)
    fl.addRow(tr("Web"), st.f_tw)
    lay.addWidget(fold)
    # seen from the side
    fold = L.Fold("Seen from the side", "beam.shape.side")
    fl = fold.form()
    st.f_elev = L.Chips(wrap=2, width=120)
    for v, text in ELEVS:
        st.f_elev.addItem(text, v, pic=_pic_elev(v))
    st.f_elev.setCurrentIndex(st.f_elev.findData(BS.elev(el)))
    fl.addRow(st.f_elev)
    st.f_ends = L.Chips()
    for v, text in ENDS:
        st.f_ends.addItem(text, v)
    st.f_ends.setCurrentIndex(max(0, st.f_ends.findData(
        el.get("eends", "both"))))
    fl.addRow(tr("Where"), st.f_ends)
    el_v = float(el.get("el", BS.default_el(el)))
    ed_v = float(el.get("ed", BS.default_ed(el)))
    st.f_el = L.metres(el_v, 0.0, 3.0, 0.05)
    st.f_el.field.setMaximum(50.0)
    st.f_el.setValue(el_v)
    st.f_ed = L.metres(ed_v, BS.MIN_PART, 1.5, 0.01)
    st.f_ed.field.setMaximum(3.0)
    st.f_ed.setValue(ed_v)
    st.l_el, st.l_ed = QLabel(""), QLabel("")
    fl.addRow(st.l_el, st.f_el)
    fl.addRow(st.l_ed, st.f_ed)
    st._label_side()
    lay.addWidget(fold)
    # in plan: its curve
    fold = L.Fold("In plan", "beam.shape.plan")
    fl = fold.form()
    import math
    half = math.dist(el["a"], el["b"]) / 2
    st.f_bulge = L.metres(BS.bulge(el), -min(half, 2.0), min(half, 2.0), 0.05)
    st.f_bulge.field.setMinimum(-half)
    st.f_bulge.field.setMaximum(half)
    st.f_bulge.setValue(round(BS.bulge(el), 4))
    st.f_bulge.setToolTip(tr("How far its middle stands off the straight "
                             "line — 0: straight; negative: it bends the "
                             "other way (up to a half circle)"))
    fl.addRow(tr("Curve"), st.f_bulge)
    fl.addRow(L.hint(tr("Inclined: «Its own height» in Geometry › Top, and "
                        "its top at end B.")))
    lay.addWidget(fold)
    st.status = L.hint("")
    lay.addWidget(st.status)
    lay.addStretch(1)
    st._enable()
    st.f_sec.currentIndexChanged.connect(st.sec_changed)
    st.f_elev.currentIndexChanged.connect(st.elev_changed)
    st.f_ends.currentIndexChanged.connect(st.changed)
    for w in (st.f_tf, st.f_tw, st.f_el, st.f_bulge):
        w.valueChanged.connect(st.changed)
    st.f_ed.valueChanged.connect(st.ed_typed)
    dlg.bshape_tab = dlg.tabs.addTab(pg, "Shape", "geometry")
    st.show(dict(el, type="beam"))
