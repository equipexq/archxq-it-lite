"""QUICK HELP — a small card in the 3D view, bottom-left, listing what the
tool or feature in use can do: its clicks and keys (PLANO_AJUDA_RAPIDA.md;
his ask 2026-10-10 / 2026-10-13: «essential for beginners»).

- On by default. **F1** switches every card off / on (H is IngeTrazo's Pan).
- «Don't show this one again» on a card hides THAT card only (his idea,
  2026-10-13); F1 on a tool whose card is hidden shows it once more, a peek.
- Settings › Display: «Quick help» (the same switch as F1) and «Show all
  again» (the cards hidden one by one come back).

``QUICK`` = topic → (title, ((keys, what), …)). The owner says which topic
is in use (``ArchXQ.quick_topic()``); the card follows it.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QLabel,
                               QVBoxLayout)

HIDDEN_KEY = "archxq/quick_hidden"        # the cards hidden one by one

QUICK: dict[str, tuple[str, tuple]] = {
    "wall": ("Wall", (
        ("Click", "each corner — the walls join by themselves"),
        ("Type + Enter", "an exact length (3.20 · 320 cm)"),
        ("Enter · double-click", "end the run here"),
        ("C", "close the run (or click its first point)"),
        ("Tab", "the wall on the other side of the line"),
        ("Backspace", "undo the last point"),
        ("Esc", "drop the run · again: done"))),
    "wall_curve": ("Curved / round wall", (
        ("Click", "its points, step by step (see the status bar)"),
        ("Type + Enter", "a length, a radius or an angle"),
        ("Tab", "the wall on the other side"),
        ("Esc", "drop it · again: done"))),
    "wall_edit": ("Edit walls", (
        ("Click a dot", "take a wall's end (the corner's walls follow)"),
        ("Click", "where it goes · or type a distance + Enter"),
        ("X / Y", "lock an axis"),
        ("Esc", "put it back · again: done"))),
    "column": ("Column", (
        ("Click", "where it goes — it snaps to the walls' corners"),
        ("Row / grid", "click the first one, then the last / the corner"),
        ("Type + Enter", "the row's length · the grid's w;d"),
        ("Options bar", "size, angle, count, height"),
        ("Esc", "drop · again: done"))),
    "beam": ("Beam", (
        ("Click", "point after point — it pulls to the columns"),
        ("Type + Enter", "an exact length"),
        ("Enter · double-click", "end the run"),
        ("Tab", "its insert: left · centre · right"),
        ("Esc", "drop · again: done"))),
    "slab": ("Slab", (
        ("Click", "its corners (rectangle, rotated, point by point)"),
        ("Type + Enter", "width;depth or a length"),
        ("Inside the walls", "the first icon: one click"),
        ("Esc", "cancel")),),
    "slab_hole": ("Opening in a slab", (
        ("Drawn (bar)", "rectangle · rotated · points · circle"),
        ("Click", "inside the slab, its corners / centre"),
        ("Type + Enter", "the sizes or the radius"),
        ("Close it", "the slab's window ▸ «Close its opening(s)»"),
        ("Esc", "cancel"))),
    "slab_edit": ("Edit slabs", (
        ("Click", "a corner or a side, then where it goes"),
        ("Type + Enter", "a distance"),
        ("Add / Delete point", "on the left menu"),
        ("Esc", "put it back · again: done"))),
    "opening": ("Door / window", (
        ("Move", "along a wall — it shows where it fits"),
        ("Click", "place it there"),
        ("Tab", "a door: its hinge on the other side"),
        ("Library", "its type: swing, sliding, casement…"),
        ("Esc", "done"))),
    "ramp": ("Ramp / stair", (
        ("Click", "where it starts (its first edge)"),
        ("Click", "the way it goes · or type its direction (°)"),
        ("Tab", "an L / U turns the other way"),
        ("Backspace", "start again"),
        ("Sizes & levels…", "from / to, width, landing"))),
    "terrain": ("Plot / excavation / fill", (
        ("Click", "its corners (or the centre, a circle)"),
        ("Type + Enter", "width;depth, a length or a radius"),
        ("C · Enter", "close a point-by-point outline"),
        ("Backspace", "undo a corner"),
        ("Esc", "cancel"))),
    "point_edit": ("Edit points", (
        ("Click", "a corner, then where it goes"),
        ("Type + Enter", "a distance"),
        ("X / Y / Z", "lock an axis"),
        ("Esc", "put it back · again: done"))),
    "grips": ("Grips — the element selected", (
        ("Drag", "a grip: it changes live, let go = done"),
        ("Click", "a grip: it follows the mouse, click again"),
        ("Type + Enter", "an exact size while a grip moves"),
        ("Shift", "1 cm steps (else 5 cm)"),
        ("↑  →  ←", "a column's circle: up / down, one way"),
        ("Esc", "put it back · Ctrl+Z after"))),
    "radial": ("Radial menu", (
        ("Move · Copy", "IngeTrazo's own Move (Ctrl = copy)"),
        ("Array", "a copy, then x3 or /3 + Enter"),
        ("Rotate · Edit", "turn it · its window"),
        ("Esc", "close it · F9 switches it off"))),
    "views": ("Elevations / X-ray", (
        ("Click", "picks THROUGH the faces — details first"),
        ("Click again", "the next one behind, same spot"),
        ("Shift", "add to the selection"),
        ("Plan view", "back to the plan"))),
}

#: the last row of every card (as the Blender add-ons' «H — Hide / show»)
F1_ROW = ("F1", "Hide / show this help")

#: the look of ArchXQ for Blender's / ContourXQ's cards (his pick,
#: 2026-10-13): a gold title «ArchXQ | Tool», the keys in light blue, the
#: words in white — no boxes
GOLD = "#e8b33c"
KEY = "#5bc8e8"
CARD_CSS = f"""
QFrame#axqQuick {{ background: rgba(30, 32, 36, 235);
                   border: 1px solid #3c4148; border-radius: 6px; }}
QLabel {{ color: #f0f2f4; background: transparent; font-size: 13px; }}
QLabel#axqQuickTitle {{ color: {GOLD}; font-weight: 600; font-size: 14px; }}
QLabel#axqQuickKey {{ color: {KEY}; font-size: 13px; }}
QCheckBox {{ color: #c9d0d7; background: transparent; font-size: 12px;
             spacing: 7px; }}
QCheckBox::indicator {{ width: 13px; height: 13px; border-radius: 3px;
                        border: 1px solid #8a939d; background: #24272c; }}
QCheckBox::indicator:checked {{ background: {KEY}; border-color: {KEY}; }}
QCheckBox::indicator:hover {{ border-color: {KEY}; }}
"""


def hidden_topics() -> set:
    raw = QSettings().value(HIDDEN_KEY, [])
    if isinstance(raw, str):
        raw = [raw] if raw else []
    return set(raw or [])


def set_hidden_topics(topics: set) -> None:
    QSettings().setValue(HIDDEN_KEY, sorted(topics))


class QuickCard(QFrame):
    """The card: a child of the 3D view, bottom-left."""

    def __init__(self, viewport, on_hide_one) -> None:
        super().__init__(viewport)
        self.setObjectName("axqQuick")
        self.setStyleSheet(CARD_CSS)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.ArrowCursor)
        self.topic = None
        self._on_hide_one = on_hide_one
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 16, 10)
        lay.setSpacing(7)
        self.title = QLabel()
        self.title.setObjectName("axqQuickTitle")
        lay.addWidget(self.title)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(22)
        self.grid.setVerticalSpacing(5)
        lay.addLayout(self.grid)
        self.never = QCheckBox("Don't show this one again")
        self.never.setFocusPolicy(Qt.NoFocus)
        self.never.setCursor(Qt.PointingHandCursor)
        self.never.toggled.connect(self._never)
        lay.addWidget(self.never)
        self.hide()

    def fill(self, topic: str) -> None:
        title, rows = QUICK[topic]
        self.topic = topic
        self.title.setText(f"ArchXQ | {title}")
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        for i, (keys, what) in enumerate(tuple(rows) + (F1_ROW,)):
            k = QLabel(keys)
            k.setObjectName("axqQuickKey")
            t = QLabel(what)
            self.grid.addWidget(k, i, 0, Qt.AlignLeft | Qt.AlignVCenter)
            self.grid.addWidget(t, i, 1, Qt.AlignLeft | Qt.AlignVCenter)
        self.never.blockSignals(True)
        self.never.setChecked(False)
        self.never.blockSignals(False)
        self.adjustSize()

    def _never(self, on: bool) -> None:
        if on and self.topic:
            QTimer.singleShot(0, lambda t=self.topic: self._on_hide_one(t))


class QuickHelp:
    """The card's owner: which topic, shown or not, F1, the settings."""

    def __init__(self, owner) -> None:
        self.owner = owner
        self.card = QuickCard(owner.viewport, self.hide_one)
        self.peek = None                  # a hidden topic shown once (F1)
        self.timer = QTimer()
        self.timer.setInterval(300)
        self.timer.timeout.connect(self.sync)
        self.timer.start()

    # -- the settings -------------------------------------------------------------
    @staticmethod
    def on() -> bool:
        from . import prefs
        return bool(prefs.get("quick_help"))

    def hide_one(self, topic: str) -> None:
        """«Don't show this one again»: that card only."""
        from . import compat
        set_hidden_topics(hidden_topics() | {topic})
        self.peek = None
        self.card.hide()
        compat.flash(self.owner.viewport, "That help card is hidden — F1 "
                     "shows it once more · Settings › «Show all again»", 4000)

    def toggle(self) -> None:
        """F1: every card off / on — on a hidden one, a peek."""
        from . import compat, prefs
        topic = self.topic()
        if self.card.isVisible():
            prefs.put("quick_help", False)
            self.peek = None
            self.card.hide()
            compat.flash(self.owner.viewport, "Quick help off — F1 brings it "
                         "back", 3000)
            return
        prefs.put("quick_help", True)
        if topic in hidden_topics():
            self.peek = topic             # shown once, still hidden after
        self.sync()

    # -- following the tool -----------------------------------------------------
    def topic(self):
        try:
            t = self.owner.quick_topic()
        except Exception:  # noqa: BLE001 — never in the way
            return None
        return t if t in QUICK else None

    def sync(self) -> None:
        o = self.owner
        if not (o.alive and o.active):
            self.card.hide()
            return
        t = self.topic()
        if self.peek is not None and t != self.peek:
            self.peek = None              # a peek lasts while its tool does
        show = t is not None and self.on() and (
            t not in hidden_topics() or t == self.peek)
        if not show:
            if self.card.isVisible():
                self.card.hide()
            return
        if self.card.topic != t or not self.card.isVisible():
            self.card.fill(t)
        self.place()
        if not self.card.isVisible():
            self.card.show()
            self.card.raise_()

    def place(self) -> None:
        """Bottom-left of the 3D view, over the bottom bar."""
        from PySide6.QtCore import QPoint
        vp = self.owner.viewport
        bottom = vp.height() - 12
        for name in ("view_bar", "viewbar"):
            bar = getattr(self.owner, name, None)
            try:
                if bar is not None and bar.isVisible():
                    top = bar.mapTo(vp, QPoint(0, 0)).y()
                    if 0 < top < vp.height():
                        bottom = min(bottom, top - 10)
                        break
            except Exception:  # noqa: BLE001 — not a child of the view
                continue
        self.card.move(12, max(bottom - self.card.height(), 60))

    def teardown(self) -> None:
        self.timer.stop()
        self.card.hide()
        self.card.deleteLater()
