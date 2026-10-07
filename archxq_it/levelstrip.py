"""The levels strip — on the right, like Blender's N panel (N shows / hides
it; remembered).

The building's levels top → bottom, as a section reads: floors, the ground
floor, basements, and the Terrain at the foot. Each row: name · ✎ ·
elevation · ghost (that level in light blue in the plan) · eye. The level you work on is lit; a click on another makes it current.
The ✎ or a double-click opens the level's own window (name,
height, a level above / below, delete). «+» adds a level on top.

Only levels live here — the outliner (every item of the model) is a piece
of its own.
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import icons
from .style import CSS

WIDTH = 250


class _Row(QFrame):
    """One level. A click anywhere but the buttons makes it current; the ✎
    or a double-click opens the level's own window."""

    def __init__(self, strip, row: dict) -> None:
        super().__init__()
        self.strip = strip
        self.row = row
        self.setProperty("axq", "level")
        self.setProperty("current", "true" if row["current"] else "false")
        self.setProperty("kind", row["kind"])
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 3, 3, 3)
        lay.setSpacing(4)
        self.name = QLabel(row["name"])
        self.name.setProperty("axq", "lvname")
        self.name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay.addWidget(self.name, 1)
        self.edit = None
        if row["kind"] != "terrain":
            self.edit = QToolButton()
            self.edit.setProperty("axq", "eye")
            self.edit.setIcon(icons.icon("edit"))
            self.edit.setIconSize(QSize(15, 15))
            self.edit.setToolTip("Edit this level…")
            self.edit.setFocusPolicy(Qt.NoFocus)
            self.edit.clicked.connect(
                lambda: strip.owner.edit_level(row["key"]))
            lay.addWidget(self.edit)            # always shown: THE way in
        if row.get("elev") is not None:
            e = QLabel(_elev(row["elev"]))
            e.setProperty("axq", "lvelev")
            lay.addWidget(e)
        if row["kind"] != "terrain":
            # GHOST: this level drawn faint under the plan of the one
            # worked on (his ask, 2026-10-06: one per level — any of them)
            g = QToolButton()
            g.setProperty("axq", "eye")
            g.setIconSize(QSize(17, 17))
            g.setFocusPolicy(Qt.NoFocus)
            on = bool(row.get("ghost"))
            g.setIcon(icons.icon("ghost_on" if on else "ghost"))
            if on:                         # lit: a blue chip behind it
                g.setStyleSheet("QToolButton { background: "
                                "rgba(111, 168, 220, 70); border-radius: 4px; }")
            if row["current"]:
                g.setEnabled(False)
                g.setToolTip("The level you work on — its ghost shows when "
                             "you work on another one")
            else:
                g.setToolTip("Ghost ON — this level shows in light blue in "
                             "the plan (click: off)" if on else
                             "Ghost — show this level in light blue in the "
                             "plan of the level you work on")
            g.clicked.connect(lambda: strip.owner.toggle_ghost(row["key"]))
            lay.addWidget(g)
        else:
            pad = QWidget()                # the eyes stay in one column
            pad.setFixedWidth(21)
            lay.addWidget(pad)
        eye = QToolButton()
        eye.setProperty("axq", "eye")
        part = row["visible"] and row.get("parts_off")
        eye.setIcon(icons.icon("eye_part" if part else "eye" if row["visible"]
                               else "eye_off"))
        eye.setIconSize(QSize(18, 18))
        eye.setToolTip(
            (", ".join(part) + " hidden on this level — ✎ ▸ Show brings "
             "them back\nClick: hide this level") if part else
            "Hide this level" if row["visible"] else "Show this level")
        eye.setFocusPolicy(Qt.NoFocus)
        eye.clicked.connect(lambda: strip.owner.toggle_level(row["key"]))
        lay.addWidget(eye)
        if not row["visible"]:
            self.name.setProperty("axq", "lvhidden")
        tip = ("Click: work on the Terrain" if row["kind"] == "terrain"
               else "Click: work on this level · double-click or ✎: edit it")
        self.setToolTip(tip)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.strip.owner.set_floor(self.row["key"])
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.row["kind"] != "terrain":
            # after the click's own handling, outside this row's events
            from PySide6.QtCore import QTimer
            key = self.row["key"]
            QTimer.singleShot(0, lambda: self.strip.owner.edit_level(key))


def _elev(z: float) -> str:
    return "±0.00" if abs(z) < 0.005 else f"{z:+.2f}"


class LevelStrip(QFrame):
    def __init__(self, owner) -> None:
        super().__init__()
        self.owner = owner
        self.setObjectName("axq_levels")
        self.setStyleSheet(CSS)
        self.setFixedWidth(WIDTH)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 6)
        lay.setSpacing(2)
        head = QHBoxLayout()
        title = QLabel("Levels")
        title.setObjectName("axq_title")
        head.addWidget(title)
        head.addStretch()
        add = QToolButton()
        add.setObjectName("axq_lvadd")
        add.setText("+")
        add.setToolTip("Add a level on top")
        add.setFocusPolicy(Qt.NoFocus)
        add.clicked.connect(owner.on_add_floor)
        head.addWidget(add)
        lay.addLayout(head)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("axq_levels_scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.body = QWidget()
        self.body.setObjectName("axq_levels_body")
        self.rows = QVBoxLayout(self.body)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(1)
        self.scroll.setWidget(self.body)
        lay.addWidget(self.scroll, 1)
        self.max_height = 10_000

    def fill(self, rows: list[dict]) -> None:
        """rows top → bottom: {key, name, kind, elev, visible, current,
        ghost}."""
        # the old rows go off NOW (until the loop deletes them they were
        # drawn under the new ones: every row looked «current»); kept
        # referenced so deleteLater, not Python, destroys them
        self._trash = []
        while self.rows.count():
            w = self.rows.takeAt(0).widget()
            if w is not None:
                w.hide()
                self._trash.append(w)
                w.deleteLater()
        current = None
        for r in rows:
            row = _Row(self, r)
            self.rows.addWidget(row)
            if r["current"]:
                current = row
        self.fit()
        # once more when the new rows are laid out (his screen, 2026-10-06:
        # an eye's click shrank the strip to 80 px with a scroll bar — it was
        # measured before its rows were)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.fit)
        if current is not None:
            self.scroll.ensureWidgetVisible(current, 0, 20)

    def mark_current(self, key) -> None:
        """Light another row without rebuilding (a rebuild under the mouse
        would swallow the double-click that renames)."""
        for i in range(self.rows.count()):
            row = self.rows.itemAt(i).widget()
            if isinstance(row, _Row):
                on = row.row["key"] == key
                row.row["current"] = on
                row.setProperty("current", "true" if on else "false")
                for w in (row, row.name):
                    w.style().unpolish(w)
                    w.style().polish(w)

    def fit(self) -> None:
        """As tall as its rows, up to ``max_height`` — then it scrolls."""
        self.ensurePolished()
        for i in range(self.rows.count()):
            w = self.rows.itemAt(i).widget()
            if w is not None:
                w.ensurePolished()
        self.body.adjustSize()
        m = self.layout().contentsMargins()
        head = self.layout().itemAt(0).sizeHint().height()
        # the rows' own heights (the body's hint can lag behind a refill)
        ws = [self.rows.itemAt(i).widget() for i in range(self.rows.count())]
        rows_h = sum(w.sizeHint().height() for w in ws if w is not None) \
            + self.rows.spacing() * max(0, len(ws) - 1)
        need = (max(self.body.sizeHint().height(), rows_h) + head + m.top()
                + m.bottom() + self.layout().spacing() + 4)
        self.setFixedHeight(max(80, min(need, self.max_height)))
