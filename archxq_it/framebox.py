# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The «Structure» of a wall's core, under its layers (PLANO_PAREDE_ESTRUTURA_
LEVE, his OK 2026-11-02): Solid — or a Wood / Steel frame, its studs' width
and spacing, the plates over and under, insulation between. The same box
in a wall's Layers tab and in the type's window (typedlg); nothing in the
N panel (his: «no room there»)."""
from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout, QWidget)

from . import compat
from . import edition
from . import framing as FR
from . import look as L
from .i18n import tr

#: the usual spacings — metres / a document in feet and inches (16", 24")
SPACINGS_M = ((0.40, "40 cm"), (0.60, "60 cm"), (0.625, "62.5 cm"))
SPACINGS_IN = ((0.4064, '16"'), (0.6096, '24"'))
#: what the light frame does not do yet — said in its tooltips (the
#: «Experimental» tag taken off, his call 2026-11-02: «está lindo»)
FRAME_TIP = ("Studs, blocking and the corners' and T's studs in the 3D; "
             "on the sheets at 1:50 or closer")
#: a full circle's core: solid whatever its frame says (no ends to start
#: the studs from — a curved wall IS framed, phase 3c)
CURVED_NOTE = "Full circle: built solid for now"
#: a ROOF's core (PLANO_TELHADO_CAMADAS 2b): the roofs it is built on
ROOF_TIP = ("Rafters on gable, hip, shed and butterfly roofs, trusses on "
            "gable and shed roofs (a gable or a hip on a rectangle) — the "
            "others solid for now")
ROOF_NOTE = "This kind of roof: built solid for now"
#: a roof whose trusses are not built yet (PLANO_TELHADO_ASNAS D7)
TRUSS_NOTE = "This kind of roof: built with rafters"
#: a truss's spacing when the system turns to trusses (24" / 60 cm)
TRUSS_S_M, TRUSS_S_IN = 0.60, 0.6096
#: a FLOOR's joists (PLANO_PISOS_BARROTES D4): past about 20× their depth,
#: said in yellow — never blocks
SPAN_WARN = ("Longest span {s} — about {m} for this depth: add a beam or a "
             "wall under it")


class FrameBox(QWidget):
    """``frame`` (a stored frame or None); ``changed()`` after each change
    the user makes (the wall window's type question, the drawing)."""

    def __init__(self, frame, changed=None, parent=None,
                 curved: bool = False, roof: bool = False,
                 trusses_ok: bool = True, floor: bool = False,
                 turn: bool = False, span=None) -> None:
        """``roof``: a roof's core (rafters or trusses — no plates;
        ``curved`` then means a roof built solid for now; not
        ``trusses_ok``: its trusses built as rafters — a butterfly).
        ``floor``: a slab's core — joists (PLANO_PISOS_BARROTES 4b): no
        plates, their Direction (``turn``: «Turn 90°»), and ``span(frame,
        turn)`` → (longest span, depth) for the span warning."""
        super().__init__(parent)
        self._curved = curved
        self._roof = roof
        self._floor = floor
        self._span = span
        self._trusses_ok = trusses_ok
        self._changed = changed
        self._quiet = False
        fr = FR.clean_frame(frame)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.fold = L.Fold(tr("Structure"), "layers.frame")
        lay.addWidget(self.fold)
        form = self.fold.form()
        self.f_kind = L.Chips()
        self.f_kind.addItem(tr("Solid"), "")
        self.f_kind.addItem(tr("Wood frame"), "wood")
        self.f_kind.addItem(tr("Steel frame"), "steel")
        self.f_kind.setToolTip(tr(
            "Solid: the core as one block (masonry, concrete). A frame: "
            "studs at a spacing, plates, a header over each opening and "
            "insulation between — the core's thickness is the studs' depth "
            "(a 2×6: 14 cm)"))
        if roof:
            self.f_kind.setToolTip(tr(
                "Solid: the roof's core as one slab. A frame: rafters from "
                "the eaves to the ridge at a spacing, a ridge board, "
                "insulation between — the core's thickness is the rafters' "
                "depth (a 2×8: 18 cm)"))
        if floor:
            self.f_kind.setToolTip(tr(
                "Solid: the slab's core as one block (concrete). A frame: "
                "joists at a spacing across the short way, a rim joist "
                "round it, doubled round each opening, insulation between "
                "— the core's thickness is the joists' depth (a 2×10: "
                "23.5 cm)"))
        else:
            # what it does not do yet: in its tooltip
            self.f_kind.setToolTip(self.f_kind.toolTip() + "\n\n"
                                   + tr(ROOF_TIP if roof else FRAME_TIP))
        form.addRow(tr("Core"), self.f_kind)
        # a FULL CIRCLE: its frame kept, built solid for now — said here,
        # or it reads as a fault (phase 3, D3)
        self.f_curved = QLabel(tr(ROOF_NOTE if roof else CURVED_NOTE))
        self.f_curved.setStyleSheet("color:#ffd58a;font-size:11px;")
        self.f_curved.setWordWrap(True)
        form.addRow("", self.f_curved)
        # a roof's SYSTEM: rafters or trusses, and the trusses' shape
        # (PLANO_TELHADO_ASNAS D8) — two rows, nothing else new
        self.f_sys = L.Chips()
        self.f_sys.addItem(tr("Rafters"), "rafters", tr(
            "Rafters from the eaves to the ridge, insulation between them "
            "— a warm roof (a room or a sloped ceiling under it)"))
        self.f_sys.addItem(tr("Trusses"), "trusses", tr(
            "Prefabricated trusses on the walls: top chords, a bottom "
            "chord, webs — a flat ceiling under them, the insulation on it "
            "(a cold attic). Not a designed truss: its maker does the "
            "design"))
        self.f_pat = L.Chips(wrap=3)
        for key in FR.TRUSS_PATTERNS:
            self.f_pat.addItem(tr(FR.TRUSS_NAMES[key]), key)
        self.f_pat.setToolTip(tr(
            "Auto: by the span between the walls' outer faces — a king "
            "post up to 6 m, a Fink («W») up to 10 m, a double Fink beyond. "
            "A shed roof: mono trusses"))
        self.f_tnote = QLabel(tr(TRUSS_NOTE))
        self.f_tnote.setStyleSheet("color:#ffd58a;font-size:11px;")
        self.f_tnote.setWordWrap(True)
        if roof:
            form.addRow(tr("System"), self.f_sys)
            form.addRow(tr("Shape"), self.f_pat)
            form.addRow("", self.f_tnote)
        # a floor's joists: which way they run, and the span warning
        self.f_dir = L.Chips()
        self.f_dir.addItem(tr("Auto"), False, tr(
            "Across the short way of each part of the slab (an L: each "
            "arm its own) — as it is built"))
        self.f_dir.addItem(tr("Turn 90°"), True, tr(
            "The other way: when what holds them up runs the other way"))
        self.f_dir.setCurrentIndex(1 if turn else 0)
        self.f_warn = QLabel()
        self.f_warn.setStyleSheet("color:#ffd58a;font-size:11px;")
        self.f_warn.setWordWrap(True)
        self.f_warn.setToolTip(tr(
            "A rule of thumb, not a design: a joist goes about 20 times its "
            "depth. Its maker or engineer sizes it"))
        if floor:
            form.addRow(tr("Direction"), self.f_dir)
            form.addRow("", self.f_warn)
        d = fr or FR.DEFAULTS["wood"]
        self.f_w = L.Measure(d["w"], 0.03, 0.10, 0.002, " m")
        self.f_w.setToolTip(tr("The studs' width along the wall (a 2×4 / "
                               "2×6: 38 mm)"))
        if roof:
            self.f_w.setToolTip(tr("The rafters' width along the ridge (a "
                                   "2×8: 38 mm)"))
        if floor:
            self.f_w.setToolTip(tr("The joists' width (a 2×10: 38 mm)"))
        form.addRow(tr("Rafter width" if roof else "Joist width" if floor
                       else "Stud width"), self.f_w)
        self.f_s = L.Measure(d["s"], *FR.SPACING, 0.01, " m")
        # (16" = 0.4064, 62.5 cm: two decimals turned them to 0.41, 0.63)
        self.f_s.setDecimals(4)
        self.f_s.setValue(d["s"])
        self.f_s.setToolTip(tr("From stud to stud, centre to centre — the "
                               "openings bring their own"))
        form.addRow(tr("Spacing"), self.f_s)
        # the usual spacings, one click each (they set the field)
        self.f_sp = QWidget()
        sp = QHBoxLayout(self.f_sp)
        sp.setContentsMargins(0, 0, 0, 0)
        sp.setSpacing(6)
        imperial = compat.doc_length_unit() != "m"
        for v, text in SPACINGS_IN if imperial else SPACINGS_M:
            b = QPushButton(text)
            b.setObjectName("axqChip")
            b.clicked.connect(lambda _c=False, v=v: self.f_s.setValue(v))
            sp.addWidget(b)
        sp.addStretch(1)
        form.addRow("", self.f_sp)
        self.f_top = L.Chips()
        self.f_bot = L.Chips()
        for ch in (self.f_top, self.f_bot):
            ch.addItem("1", 1)
            ch.addItem("2", 2)
        self.f_top.setToolTip(tr("Plates over the studs (American framing: "
                                 "a double top plate)"))
        if not roof and not floor:       # (a roof, a floor: no plates)
            form.addRow(tr("Top plates"), self.f_top)
            form.addRow(tr("Bottom plates"), self.f_bot)
        elif floor:
            self.f_s.setToolTip(tr("From joist to joist, centre to centre"))
        else:
            self.f_s.setToolTip(tr("From rafter to rafter, centre to "
                                   "centre"))
        self.f_fill = QCheckBox(tr(
            "Insulation between the rafters" if roof else
            "Insulation between the joists" if floor else
            "Insulation between the studs"))
        form.addRow("", self.f_fill)
        self._rows = [self.f_w, self.f_s, self.f_sp, self.f_top, self.f_bot,
                      self.f_fill, self.f_sys, self.f_pat, self.f_dir]
        self.set(fr)
        self.f_kind.currentIndexChanged.connect(self._kind)
        self.f_sys.currentIndexChanged.connect(self._system)
        self.f_pat.currentIndexChanged.connect(self._edit)
        for f in (self.f_w, self.f_s):
            f.valueChanged.connect(self._edit)
        self.f_top.currentIndexChanged.connect(self._edit)
        self.f_bot.currentIndexChanged.connect(self._edit)
        self.f_fill.toggled.connect(self._edit)
        self.f_dir.currentIndexChanged.connect(self._edit)
        if edition.lite():
            # frames are the Pro's: seen, not changed — and a frame from a
            # Pro file is kept as it is (``value()`` still reads it)
            self.setEnabled(False)
            self.setToolTip(tr("In ArchXQ IT Pro"))

    # ---------------------------------------------------------------------------------
    def set(self, frame) -> None:
        """Show ``frame`` (no change reported)."""
        fr = FR.clean_frame(frame)
        self._quiet = True
        try:
            self.f_kind.setCurrentIndex(max(0, self.f_kind.findData(
                fr["kind"] if fr else "")))
            if fr:
                self.f_w.setValue(fr["w"])
                self.f_s.setValue(fr["s"])
                self.f_top.setCurrentIndex(self.f_top.findData(fr["top"]))
                self.f_bot.setCurrentIndex(self.f_bot.findData(fr["bottom"]))
                self.f_fill.setChecked(fr["fill"] == "insulation")
                self.f_sys.setCurrentIndex(self.f_sys.findData(
                    fr.get("system", "rafters")))
                self.f_pat.setCurrentIndex(self.f_pat.findData(
                    fr.get("pattern", "auto")))
            self._show()
        finally:
            self._quiet = False

    def value(self) -> dict | None:
        kind = self.f_kind.currentData()
        if not kind:
            return None
        raw = {"kind": kind, "w": self.f_w.value(), "s": self.f_s.value(),
               "top": self.f_top.currentData() or 1,
               "bottom": self.f_bot.currentData() or 1,
               "fill": "insulation" if self.f_fill.isChecked() else "empty"}
        if self._roof and self.f_sys.currentData() == "trusses":
            raw.update(system="trusses", pattern=self.f_pat.currentData())
        return FR.clean_frame(raw)

    def turn(self) -> bool:
        """A floor's joists turned 90° (its record's «jdir»)."""
        return self._floor and bool(self.f_dir.currentData())

    def recheck(self) -> None:
        """The span warning again (its thickness / outline changed)."""
        fr = self.value()
        text = ""
        if self._floor and fr is not None and self._span is not None:
            try:
                sp, depth = self._span(fr, self.turn())
            except Exception:  # noqa: BLE001 — no warning
                sp, depth = 0.0, 0.0
            from .structure import span_limit
            lim = span_limit(depth)
            if depth > 0 and sp > lim + 0.05:
                text = tr(SPAN_WARN, s=compat.fmt_len(sp),
                          m=compat.fmt_len(lim))
        self.f_warn.setText(text)
        self.f_warn.setVisible(bool(text))

    def _trusses(self) -> bool:
        return self._roof and self.f_sys.currentData() == "trusses"

    def _show(self) -> None:
        fr = self.value()
        self.f_curved.setVisible(fr is not None and self._curved)
        for w in self._rows:
            w.setEnabled(fr is not None)
        tru = fr is not None and self._trusses()
        self.f_pat.setVisible(self._roof and tru)
        self.f_tnote.setVisible(self._roof and tru and not self._curved
                                and not self._trusses_ok)
        if self._roof:
            self.f_fill.setText(tr("Insulation on the ceiling" if tru else
                                   "Insulation between the rafters"))
        k = None if fr is None else \
            (tr("Wood frame") if fr["kind"] == "wood" else tr("Steel frame"))
        if tru:
            k = tr("Trusses")
        if self._floor and fr is not None:
            k = tr("Joists")
        self.f_dir.setVisible(self._floor)
        self.recheck()
        self.fold.set_pick("Pro" if edition.lite() else
                           tr("Solid") if fr is None else
                           tr("{k} · every {s}", k=k,
                              s=compat.fmt_cm(fr["s"], 1)))

    def _system(self, _i=None) -> None:
        """Rafters ⇄ trusses: a truss's spacing (24" / 60 cm) when it turns
        to trusses."""
        if self._quiet:
            return
        if self._trusses():
            self._quiet = True
            self.f_s.setValue(TRUSS_S_IN if compat.doc_length_unit() != "m"
                              else TRUSS_S_M)
            self._quiet = False
        self._edit()

    def _kind(self, _i=None) -> None:
        if self._quiet:
            return
        kind = self.f_kind.currentData()
        if kind:                         # a new kind: its usual sizes
            d = FR.DEFAULTS[kind]
            self._quiet = True
            self.f_w.setValue(d["w"])
            self.f_s.setValue(d["s"])
            self.f_top.setCurrentIndex(self.f_top.findData(d["top"]))
            self.f_bot.setCurrentIndex(self.f_bot.findData(d["bottom"]))
            self.f_fill.setChecked(True)
            self._quiet = False
        self._edit()

    def _edit(self, *_a) -> None:
        if self._quiet:
            return
        self._show()
        if self._changed is not None:
            self._changed()
