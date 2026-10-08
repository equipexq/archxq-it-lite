"""The LIBRARY — the «intermediate step» between picking a tool and drawing.

His design, approved 2026-10-08 («maravilhoso… vende»): the right strip
(ArchXQ's tray tab) opens on the library of the element being drawn —
TYPE cards with pictures on top (a stair Straight / L / U, a door Swing /
Sliding / Arched…), PART chips below (the leaves, the hinge, the railing…).
The library says WHAT; the sizes stay in the options bar (HOW MUCH). It is
never a compulsory step: the last type used is already marked — whoever
knows what they want just draws. An element selected: its type is marked,
another card SWAPS it (one Ctrl+Z). «soon» items are greyed: the library
is meant to grow, and the user should see it.

``CATALOG``: per element key, its types and parts; each type / part
choice is a dict of the element's OPTIONS (ui's ``*_opts``) — and, through
``REC_KEYS``, of its records. ``LibraryPanel``: the widget. Pictures are
drawn here, in the icons' spirit (light ink, the host's orange).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QGridLayout, QHBoxLayout,
                               QLabel, QPushButton, QToolButton, QVBoxLayout,
                               QWidget)

INK = QColor("#d6d9dd")
DIM = QColor("#6b7178")
ACCENT = QColor("#e8742c")
PX = 96


@dataclass(frozen=True)
class Type:
    key: str
    label: str
    pic: str                      # a picture of PICS
    set: dict | None              # the options it sets; None = «soon»
    tip: str = ""


@dataclass(frozen=True)
class Part:
    key: str                      # the option it sets
    label: str
    choices: tuple                # (value, label) or (value, label, "soon")
    show: object = None           # fn(opts) → shown?
    kind: str = "chips"           # chips | slider (0…1, live while dragged)


@dataclass(frozen=True)
class Shelf:
    title: str
    types: tuple
    parts: tuple = field(default_factory=tuple)


def _one_leaf(o) -> bool:
    return o.get("op") == "sliding" or int(o.get("leaves", 1) or 1) == 1


CATALOG = {
    "door": Shelf("Doors", (
        Type("swing", "Swing", "door_swing", {"op": "swing", "leaf": "solid"},
             "Hinged on a jamb, opens to the inside"),
        Type("sliding", "Sliding", "door_sliding",
             {"op": "sliding", "leaf": "solid"},
             "One leaf on a rail along the inside face; two part in the "
             "middle"),
        Type("glass", "Glass sliding", "door_glass",
             {"op": "sliding", "leaf": "glass"},
             "Glazed leaves in a slim dark frame, in two tracks — the "
             "curtain wall's look"),
        Type("arched", "Arched", "door_arched", None)),
        (Part("leaves", "Leaves", ((1, "1"), (2, "2"))),
         Part("swing", "Hinge · slides to", (("left", "Left"),
                                              ("right", "Right")),
              _one_leaf),
         Part("open", "Open", (), None, "slider"),
         Part("top", "Top", (("square", "Square"), ("arched", "Arched",
                                                    "soon"))))),
    "window": Shelf("Windows", (
        Type("fixed", "Fixed", "win_fixed", {}, "A frame and its glass"),
        Type("sliding", "Sliding", "win_sliding", None),
        Type("casement", "Casement", "win_casement", None))),
    "wall": Shelf("Walls", (
        Type("w15", "15 cm", "wall_15", {"t": 0.15}, "A 15 cm wall"),
        Type("w20", "20 cm", "wall_20", {"t": 0.20}, "A 20 cm wall"),
        Type("w10", "Partition", "wall_10", {"t": 0.10},
             "A 10 cm partition"),
        Type("curtain", "Curtain wall", "wall_curtain", None))),
    "column": Shelf("Columns", (
        Type("rect", "Rectangular", "col_rect", {"section": "rect"}),
        Type("round", "Round", "col_round", {"section": "round"}))),
    "beam": Shelf("Beams", (
        Type("b1540", "15 × 40", "beam_s", {"w": 0.15, "h": 0.40}),
        Type("b2045", "20 × 45", "beam_m", {"w": 0.20, "h": 0.45}),
        Type("b2060", "20 × 60", "beam_l", {"w": 0.20, "h": 0.60}))),
    "slab": Shelf("Slabs", (
        Type("s12", "12 cm", "slab_12", {"t": 0.12}),
        Type("s15", "15 cm", "slab_15", {"t": 0.15}),
        Type("s20", "20 cm", "slab_20", {"t": 0.20}))),
    "stair": Shelf("Stairs", (
        Type("straight", "Straight", "stair_straight", {"shape": "straight"}),
        Type("L", "L", "stair_l", {"shape": "L"}),
        Type("U", "U", "stair_u", {"shape": "U"})),
        (Part("railing", "Railing", (("none", "None"),
                                     ("handrail", "Handrail", "soon"),
                                     ("wall", "Low wall", "soon"),
                                     ("glass", "Glass", "soon"))),)),
    "ramp": Shelf("Ramps", (
        Type("straight", "Straight", "ramp_straight", {"shape": "straight"}),
        Type("L", "L", "ramp_l", {"shape": "L"}),
        Type("U", "U", "ramp_u", {"shape": "U"}))),
}

#: an option whose RECORD key is another (a column's «section» is its
#: record's «shape»)
REC_KEYS = {"column": {"section": "shape"}}


def rec_changes(key: str, changes: dict) -> dict:
    m = REC_KEYS.get(key, {})
    return {m.get(k, k): v for k, v in changes.items()}


def _same(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-6
    return a == b


def current_type(shelf: Shelf, opts: dict) -> str | None:
    """The type the options are (the first that fits); None = sizes of
    one's own."""
    for t in shelf.types:
        if t.set is not None and all(_same(opts.get(k), v)
                                     for k, v in t.set.items()):
            return t.key
    return None


# ---- the pictures ------------------------------------------------------------------
def _pen(c=INK, w=4.0, dash=False) -> QPen:
    p = QPen(c, w)
    p.setCapStyle(Qt.RoundCap)
    p.setJoinStyle(Qt.RoundJoin)
    if dash:
        p.setStyle(Qt.DashLine)
    return p


def _wall_stubs(p, y=70, a=22, b=74) -> None:
    p.setPen(_pen(INK, 8))
    p.drawLine(QPointF(6, y), QPointF(a, y))
    p.drawLine(QPointF(b, y), QPointF(90, y))


def _door_swing(p) -> None:
    _wall_stubs(p)
    p.setPen(_pen(ACCENT, 5))
    p.drawLine(QPointF(22, 70), QPointF(22, 18))
    p.setPen(_pen(ACCENT, 3, True))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(-30, 18, 104, 104), 0, 90 * 16)


def _door_sliding(p) -> None:
    _wall_stubs(p)
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawRect(QRectF(18, 56, 40, 7))
    p.setBrush(INK)
    p.drawRect(QRectF(46, 46, 40, 7))
    p.setPen(_pen(ACCENT, 3.5))
    p.drawLine(QPointF(30, 34), QPointF(66, 34))
    p.drawLine(QPointF(58, 27), QPointF(66, 34))
    p.drawLine(QPointF(58, 41), QPointF(66, 34))


def _door_glass(p) -> None:
    """A glazed sliding door, front view: two panes in slim dark frames,
    one sliding over the other."""
    glass = QColor("#8fc3dd")
    glass.setAlpha(150)
    p.setPen(_pen(INK, 4))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(10, 12, 76, 76))            # the opening's frame
    p.setPen(_pen(QColor("#3b4046"), 3))
    p.setBrush(glass)
    p.drawRect(QRectF(16, 18, 36, 64))
    p.drawRect(QRectF(44, 18, 36, 64))
    p.setPen(_pen(ACCENT, 3.5))
    p.drawLine(QPointF(66, 50), QPointF(34, 50))
    p.drawLine(QPointF(41, 43), QPointF(34, 50))
    p.drawLine(QPointF(41, 57), QPointF(34, 50))


def _door_arched(p) -> None:
    path = QPainterPath(QPointF(26, 88))
    path.lineTo(26, 40)
    path.arcTo(QRectF(26, 18, 44, 44), 180, -180)
    path.lineTo(70, 88)
    p.setPen(_pen(DIM, 5))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)


def _win_fixed(p) -> None:
    _wall_stubs(p, 48, 20, 76)
    p.setPen(_pen(ACCENT, 4))
    p.drawLine(QPointF(20, 38), QPointF(20, 58))
    p.drawLine(QPointF(76, 38), QPointF(76, 58))
    p.drawLine(QPointF(20, 44), QPointF(76, 44))
    p.drawLine(QPointF(20, 52), QPointF(76, 52))


def _win_sliding(p) -> None:
    _wall_stubs(p, 48, 20, 76)
    p.setPen(_pen(DIM, 4))
    p.drawLine(QPointF(20, 43), QPointF(54, 43))
    p.drawLine(QPointF(42, 53), QPointF(76, 53))


def _win_casement(p) -> None:
    _wall_stubs(p, 60, 20, 76)
    p.setPen(_pen(DIM, 4))
    p.drawLine(QPointF(20, 60), QPointF(36, 26))
    p.drawLine(QPointF(76, 60), QPointF(60, 26))


def _wall(p, t) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawRect(QRectF(48 - t / 2, 10, t, 76))
    p.setPen(_pen(INK, 2.5))
    p.drawLine(QPointF(14, 86), QPointF(82, 86))


def _wall_curtain(p) -> None:
    p.setPen(_pen(DIM, 3))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(18, 12, 60, 74))
    for x in (38, 58):
        p.drawLine(QPointF(x, 12), QPointF(x, 86))
    for y in (37, 62):
        p.drawLine(QPointF(18, y), QPointF(78, y))


def _col_rect(p) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawRect(QRectF(30, 26, 36, 44))
    p.setPen(_pen(INK, 2, True))
    p.drawLine(QPointF(10, 48), QPointF(86, 48))
    p.drawLine(QPointF(48, 10), QPointF(48, 86))


def _col_round(p) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawEllipse(QPointF(48, 48), 22, 22)
    p.setPen(_pen(INK, 2, True))
    p.drawLine(QPointF(10, 48), QPointF(86, 48))
    p.drawLine(QPointF(48, 10), QPointF(48, 86))


def _beam(p, w, h) -> None:
    """A beam's section under its slab."""
    p.setPen(Qt.NoPen)
    p.setBrush(INK)
    p.drawRect(QRectF(8, 20, 80, 10))
    p.setBrush(ACCENT)
    p.drawRect(QRectF(48 - w / 2, 20, w, h))


def _slab(p, t) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawRect(QRectF(8, 40 - t / 2, 80, t))
    p.setBrush(INK)
    for x in (16, 72):
        p.drawRect(QRectF(x, 40 + t / 2, 8, 40 - t / 2))


def _stair_straight(p) -> None:
    p.setPen(_pen(INK, 3))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(34, 8, 28, 80))
    p.setPen(_pen(ACCENT, 2.5))
    for k in range(1, 8):
        y = 8 + k * 10
        p.drawLine(QPointF(34, y), QPointF(62, y))


def _stair_l(p) -> None:
    path = QPainterPath(QPointF(16, 88))
    for x, y in ((16, 14), (82, 14), (82, 40), (42, 40), (42, 88)):
        path.lineTo(x, y)
    path.closeSubpath()
    p.setPen(_pen(INK, 3))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.setPen(_pen(ACCENT, 2.5))
    for y in (50, 60, 70, 80):
        p.drawLine(QPointF(16, y), QPointF(42, y))
    for x in (52, 62, 72):
        p.drawLine(QPointF(x, 14), QPointF(x, 40))


def _stair_u(p) -> None:
    path = QPainterPath(QPointF(12, 88))
    for x, y in ((12, 12), (84, 12), (84, 88), (58, 88), (58, 38),
                 (38, 38), (38, 88)):
        path.lineTo(x, y)
    path.closeSubpath()
    p.setPen(_pen(INK, 3))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.setPen(_pen(ACCENT, 2.5))
    for y in (48, 58, 68, 78):
        p.drawLine(QPointF(12, y), QPointF(38, y))
        p.drawLine(QPointF(58, y), QPointF(84, y))


def _ramp(p, kind) -> None:
    """A ramp's outline in plan — the stair's, without its steps — and
    the way it climbs."""
    outline = {"straight": ((34, 8), (62, 8), (62, 88), (34, 88)),
               "L": ((16, 88), (16, 14), (82, 14), (82, 40), (42, 40),
                     (42, 88)),
               "U": ((12, 88), (12, 12), (84, 12), (84, 88), (58, 88),
                     (58, 38), (38, 38), (38, 88))}[kind]
    path = QPainterPath(QPointF(*outline[0]))
    for x, y in outline[1:]:
        path.lineTo(x, y)
    path.closeSubpath()
    p.setPen(_pen(INK, 3))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    x = {"straight": 48, "L": 29, "U": 25}[kind]
    p.setPen(_pen(ACCENT, 3.5))
    p.drawLine(QPointF(x, 82), QPointF(x, 52))
    p.drawLine(QPointF(x - 6, 60), QPointF(x, 52))
    p.drawLine(QPointF(x + 6, 60), QPointF(x, 52))


PICS = {
    "door_swing": _door_swing, "door_sliding": _door_sliding,
    "door_glass": _door_glass,
    "door_arched": _door_arched,
    "win_fixed": _win_fixed, "win_sliding": _win_sliding,
    "win_casement": _win_casement,
    "wall_15": lambda p: _wall(p, 15), "wall_20": lambda p: _wall(p, 20),
    "wall_10": lambda p: _wall(p, 10), "wall_curtain": _wall_curtain,
    "col_rect": _col_rect, "col_round": _col_round,
    "beam_s": lambda p: _beam(p, 15, 40), "beam_m": lambda p: _beam(p, 20,
                                                                    45),
    "beam_l": lambda p: _beam(p, 20, 60),
    "slab_12": lambda p: _slab(p, 9), "slab_15": lambda p: _slab(p, 12),
    "slab_20": lambda p: _slab(p, 16),
    "stair_straight": _stair_straight, "stair_l": _stair_l,
    "stair_u": _stair_u,
    "ramp_straight": lambda p: _ramp(p, "straight"),
    "ramp_l": lambda p: _ramp(p, "L"), "ramp_u": lambda p: _ramp(p, "U"),
}
_cache: dict = {}


def picture(key: str) -> QIcon:
    if key not in _cache:
        pm = QPixmap(PX, PX)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        PICS.get(key, lambda _p: None)(p)
        p.end()
        _cache[key] = QIcon(pm)
    return _cache[key]


# ---- the panel -------------------------------------------------------------------------
CARD_CSS = ("QToolButton { border: 1px solid #3a3f45; border-radius: 6px; "
            "padding: 4px; color: #d6d9dd; }"
            "QToolButton:hover { border-color: #6b7178; }"
            "QToolButton:checked { border: 2px solid #e8742c; "
            "color: #ffffff; }"
            "QToolButton:disabled { color: #6b7178; }")
CHIP_CSS = ("QPushButton { border: 1px solid #3a3f45; border-radius: 4px; "
            "padding: 3px 10px; color: #d6d9dd; }"
            "QPushButton:hover { border-color: #6b7178; }"
            "QPushButton:checked { border: 2px solid #e8742c; "
            "color: #ffffff; }"
            "QPushButton:disabled { color: #6b7178; }")


SLIDER_CSS = ("QSlider::groove:horizontal { height: 8px; border-radius: 4px; "
              "background: #3a3f45; }"
              "QSlider::sub-page:horizontal { height: 8px; border-radius: 4px; "
              "background: #3d8fd6; }"
              "QSlider::handle:horizontal { width: 18px; height: 18px; "
              "margin: -5px 0; border-radius: 9px; background: #e8eaed; "
              "border: 2px solid #3d8fd6; }"
              "QSlider::handle:horizontal:hover { background: #ffffff; }")


class LibraryPanel(QWidget):
    """The library of one element: type cards, part chips. ``on_pick(key,
    changes)`` gets what was clicked; ``show(key, opts, pro_locked,
    picked)`` (re)fills it — None hides it."""

    def __init__(self, on_pick, on_live=None) -> None:
        super().__init__()
        self.on_pick = on_pick
        self.on_live = on_live        # a slider dragged: (key, changes)
        self.key = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 8)
        lay.setSpacing(6)
        self.head = QLabel()
        f = self.head.font()
        f.setBold(True)
        self.head.setFont(f)
        top = QHBoxLayout()
        top.addWidget(self.head)
        top.addStretch(1)
        from .help import help_button
        top.addWidget(help_button("library"))
        lay.addLayout(top)
        self.sub = QLabel()
        self.sub.setWordWrap(True)
        self.sub.setStyleSheet("color: #8a9099;")
        lay.addWidget(self.sub)
        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(6)
        lay.addWidget(self.body)
        self.hide()

    def _clear(self) -> None:
        def wipe(layout):
            while layout.count():
                it = layout.takeAt(0)
                if it.widget() is not None:
                    it.widget().deleteLater()
                elif it.layout() is not None:
                    wipe(it.layout())
        wipe(self.body_lay)

    def _slider(self, part: Part, opts: dict):
        """0 … 100 %: dragged, the model follows live (``on_live``); let
        go (or a click / a key), it is kept (``on_pick``: one Ctrl+Z)."""
        from PySide6.QtWidgets import QSlider
        row = QHBoxLayout()
        s = QSlider(Qt.Horizontal)
        # well in view (his eye, 2026-10-08: the host's thin one hardly
        # showed): a thick track, the open part in blue, a round handle
        s.setStyleSheet(SLIDER_CSS)
        s.setMinimumHeight(24)
        s.setRange(0, 100)
        s.setValue(int(round(float(opts.get(part.key, 0.0) or 0.0) * 100)))
        s.setToolTip("Drag: the selected ones open and close as you go")
        val = QLabel(f"{s.value()} %")
        val.setFixedWidth(42)
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(s, 1)
        row.addWidget(val)

        def moved(v) -> None:
            val.setText(f"{v} %")
            if s.isSliderDown():
                if self.on_live is not None:
                    self.on_live(self.key, {part.key: v / 100.0})
            else:                                  # a click / a key: kept
                self.on_pick(self.key, {part.key: v / 100.0})
        s.valueChanged.connect(moved)
        s.sliderReleased.connect(
            lambda: self.on_pick(self.key, {part.key: s.value() / 100.0}))
        return row

    def show_for(self, key, opts: dict | None, pro_locked: bool = False,
                 picked: int = 0) -> None:
        shelf = CATALOG.get(key)
        if shelf is None or opts is None:
            self.key = None
            self.hide()
            return
        self.key = key
        self._clear()
        self.head.setText(f"Library · {shelf.title}"
                          + ("   PRO" if pro_locked else ""))
        self.sub.setText(
            f"Click a type to change the {picked} selected" if picked else
            "Pick a type, then draw — the sizes are in the bar on the left")
        grid = QGridLayout()
        grid.setSpacing(6)
        cur = current_type(shelf, opts)
        for i, t in enumerate(shelf.types):
            b = QToolButton()
            b.setStyleSheet(CARD_CSS)
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setIcon(picture(t.pic))
            b.setIconSize(QSize(56, 56))
            b.setFixedSize(QSize(84, 86))
            soon = t.set is None
            b.setText(t.label + ("\nsoon" if soon else ""))
            b.setCheckable(True)
            b.setChecked(t.key == cur)
            b.setEnabled(not soon)
            b.setToolTip("Coming soon — the library keeps growing" if soon
                         else (t.tip or t.label)
                         + ("  (ArchXQ IT Pro)" if pro_locked else ""))
            if not soon:
                b.clicked.connect(lambda _c=False, ch=dict(t.set):
                                  self.on_pick(self.key, ch))
            grid.addWidget(b, i // 3, i % 3)
        self.body_lay.addLayout(grid)
        for part in shelf.parts:
            if part.show is not None and not part.show(opts):
                continue
            lab = QLabel(part.label)
            lab.setStyleSheet("color: #8a9099;")
            self.body_lay.addWidget(lab)
            if part.kind == "slider":
                self.body_lay.addLayout(self._slider(part, opts))
                continue
            row = QHBoxLayout()
            row.setSpacing(4)
            group = QButtonGroup(self)
            group.setExclusive(True)
            value = opts.get(part.key, part.choices[0][0])
            for ch in part.choices:
                v, text = ch[0], ch[1]
                soon = len(ch) > 2 and ch[2] == "soon"
                c = QPushButton(text + (" · soon" if soon else ""))
                c.setStyleSheet(CHIP_CSS)
                c.setCheckable(True)
                c.setChecked(_same(v, value))
                c.setEnabled(not soon)
                if soon:
                    c.setToolTip("Coming soon — the library keeps growing")
                else:
                    c.clicked.connect(lambda _c=False, k=part.key, v=v:
                                      self.on_pick(self.key, {k: v}))
                group.addButton(c)
                row.addWidget(c)
            row.addStretch(1)
            self.body_lay.addLayout(row)
        # the greyed ones, said plainly (his ask, 2026-10-08: not everyone
        # reads «soon» on a grey card)
        if any(t.set is None for t in shelf.types) or any(
                len(c) > 2 for pt in shelf.parts for c in pt.choices):
            note = QLabel("Greyed items are on the way — they switch on "
                          "with the coming updates.")
            note.setWordWrap(True)
            note.setStyleSheet("color: #6b7178; font-size: 11px;")
            self.body_lay.addWidget(note)
        self.show()
