"""The OPTIONS bar — the choices a creation tool needs BEFORE you start
(ArchiCAD's Info Box; his idea: a wall aligned by its centre, inside or
outside…). It shows while such a tool is out, under the phases row (or
in a bar of its own), and is the same piece for every tool: the tool
hands a list of options, the bar draws them, a change goes back through
``on_change(key, value)``.

An option: {"key", "label", "kind": "choice" | "len" | "int" | "icons" |
            "segments", "value", "choices": [(value, text)…] (choice,
            segments) / [(value, icon key, tip)…] (icons),
            "min", "max", "step", "suffix", "tip"}

"icons" = a row of picture buttons, one lit (how to draw: a rectangle,
point by point, an arc…) — every choice in sight; "segments" = ONE
button showing the choice made («Centre ▾»): the others open under it
when the mouse comes over (ArchiCAD's Info Box — his call, 2026-10-03:
the bar had grown too long, it ran into the levels strip).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSpinBox,
)

from .style import CSS


class OptionsBar(QFrame):
    """Its options flow in ROWS: each one (caption + field) is a block
    that never splits; what does not fit the width given (``max_width``)
    goes to the next row — the column's bar ran past the 3D view's edge."""

    def __init__(self, owner) -> None:
        from PySide6.QtWidgets import QVBoxLayout
        super().__init__()
        self.owner = owner
        self.setObjectName("axq_viewbar")          # the same pill look
        # captions closer to their fields than in the view bar: the bar
        # must stay short (one row on a usual screen)
        self.setStyleSheet(CSS + "QLabel#axq_caption { padding: 0 1px 0 "
                                 "5px; }")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(8, 3, 8, 3)
        self.lay.setSpacing(2)
        self.on_change = lambda _k, _v: None
        self.options: list[dict] = []
        self._items: list = []          # the blocks, in order
        self._rows: list = []           # the row widgets holding them
        self._trash: list = []
        self.max_width = 100000         # set by ui: the room there is

    def _block(self, caption: str, field) -> "QFrame":
        from PySide6.QtWidgets import QWidget
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        if caption:
            cap = QLabel(caption)
            cap.setObjectName("axq_caption")
            row.addWidget(cap)
        if field is not None:
            row.addWidget(field)
        return box

    def fill(self, title: str, options: list[dict], on_change) -> None:
        self.on_change = on_change
        self.options = options
        # the old fields leave the bar NOW (hidden) but are destroyed only
        # when the event loop says: the one clicked may be the very one
        # whose click is running this (a shape's icon) — destroying it
        # inside its own signal would bring the host down
        self._trash = list(self._rows)
        for r in self._rows:
            r.hide()
            r.deleteLater()
        self._rows = []
        t = QLabel(title)
        t.setObjectName("axq_title")
        self._items = [self._block("", t)]
        for o in options:
            if o["kind"] == "icons":
                field = self._buttons(o)
            elif o["kind"] == "segments":
                field = self._popup(o)
            elif o["kind"] == "note":            # a line of words
                field = QLabel(o["text"])
                field.setObjectName("axq_caption")
            elif o["kind"] == "button":          # one action, in words
                field = self._action(o)
            else:
                field = self._editor(o)
            self._items.append(self._block(o["label"], field))
        self.fit()

    def _popup(self, o: dict):
        """One button with the choice made; the others in a menu that
        opens when the mouse comes over it (or on a click)."""
        from PySide6.QtCore import QEvent, QObject, QTimer
        from PySide6.QtGui import QActionGroup
        from PySide6.QtWidgets import QMenu, QPushButton
        text = dict(o["choices"])
        b = QPushButton(f"{text.get(o['value'], '—')}  ▾")
        b.setProperty("axq", "chip")
        b.setFocusPolicy(Qt.NoFocus)
        b.setToolTip(o.get("tip", ""))
        menu = QMenu(b)
        menu.setObjectName("axq_menu")
        menu.setStyleSheet(CSS)
        group = QActionGroup(menu)
        group.setExclusive(True)
        for value, label in o["choices"]:
            a = menu.addAction(label)
            a.setCheckable(True)
            a.setChecked(value == o["value"])
            group.addAction(a)
            a.triggered.connect(
                lambda _=False, v=value, t=label, key=o["key"]: (
                    b.setText(f"{t}  ▾"), self.on_change(key, v)))
        hover_menu(b, menu)
        return b

    def _action(self, o: dict):
        """A plain button: a click says ``on_change(key, True)``."""
        from PySide6.QtWidgets import QPushButton
        b = QPushButton(o["text"])
        b.setProperty("axq", "chip")
        b.setFocusPolicy(Qt.NoFocus)
        b.setToolTip(o.get("tip", ""))
        b.clicked.connect(lambda _=False, key=o["key"]: self.on_change(key,
                                                                       True))
        return b

    def _buttons(self, o: dict):
        """A row of buttons, one lit — pictures (icons) or words."""
        from PySide6.QtCore import QSize
        from PySide6.QtWidgets import QButtonGroup, QPushButton, QWidget
        from . import icons
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        group = QButtonGroup(box)
        group.setExclusive(True)
        for item in o["choices"]:
            value = item[0]
            b = QPushButton()
            b.setProperty("axq", "chip")
            b.setCheckable(True)
            b.setFocusPolicy(Qt.NoFocus)
            if o["kind"] == "icons":
                b.setIcon(icons.icon(item[1]))
                b.setIconSize(QSize(22, 22))
                b.setToolTip(item[2] if len(item) > 2 else "")
            else:
                b.setText(item[1])
                b.setToolTip(o.get("tip", ""))
            b.setChecked(value == o["value"])
            b.clicked.connect(
                lambda _=False, v=value, key=o["key"]: self.on_change(key, v))
            group.addButton(b)
            row.addWidget(b)
        return box

    def fit(self) -> None:
        """Lay the blocks in rows that fit ``max_width``, then measure
        (once laid out — measured before, it shrank to a black dot)."""
        from PySide6.QtWidgets import QWidget
        for w in self.findChildren(QLabel) + [self]:
            w.ensurePolished()
        for it in self._items:
            it.ensurePolished()
            it.adjustSize()
        room = max(200, self.max_width - 16)
        rows, cur, width = [], [], 0
        for it in self._items:
            w = it.sizeHint().width() + 6
            if cur and width + w > room:
                rows.append(cur)
                cur, width = [], 0
            cur.append(it)
            width += w
        if cur:
            rows.append(cur)
        sig = [[id(it) for it in items] for items in rows]
        if sig == getattr(self, "_sig", None) and self._rows:
            self.lay.activate()          # same rows: only measure again
            self.resize(self.sizeHint())
            return
        self._sig = sig
        old = self._rows
        self._rows = []
        for items in rows:
            r = QWidget()
            lay = QHBoxLayout(r)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(6)
            for it in items:
                lay.addWidget(it)
                it.show()
            lay.addStretch(1)
            self.lay.addWidget(r)
            self._rows.append(r)
        for r in old:                    # empty now: their blocks moved
            self.lay.removeWidget(r)
            r.hide()
            self._trash.append(r)
            r.deleteLater()
        self.lay.activate()
        self.resize(self.sizeHint())

    def _editor(self, o: dict):
        kind = o["kind"]
        if kind == "choice":
            w = QComboBox()
            for value, text in o["choices"]:
                w.addItem(text, value)
            i = next((k for k, (v, _t) in enumerate(o["choices"])
                      if v == o["value"]), 0)
            w.setCurrentIndex(i)
            w.currentIndexChanged.connect(
                lambda k, w=w, key=o["key"]: self.on_change(key,
                                                            w.itemData(k)))
        elif kind == "int":
            w = QSpinBox()
            w.setRange(int(o.get("min", 0)), int(o.get("max", 999)))
            w.setValue(int(o["value"]))
            w.setKeyboardTracking(False)
            w.setMaximumWidth(64)                    # as wide as its value
            w.valueChanged.connect(
                lambda v, key=o["key"]: self.on_change(key, int(v)))
        else:                                        # a length (m)
            w = QDoubleSpinBox()
            w.setDecimals(2)
            w.setRange(float(o.get("min", -1000.0)),
                       float(o.get("max", 1000.0)))
            w.setSingleStep(float(o.get("step", 0.05)))
            w.setSuffix(o.get("suffix", " m"))
            w.setValue(float(o["value"]))
            w.setKeyboardTracking(False)
            # as wide as a value — its range (to 1000) made it far wider
            w.setMaximumWidth(80)
            w.valueChanged.connect(
                lambda v, key=o["key"]: self.on_change(key, round(v, 3)))
        w.setToolTip(o.get("tip", ""))
        w.setFocusPolicy(Qt.ClickFocus)
        # a field over the 3D view: while it has the keyboard, no key may
        # reach the host's shortcuts (the lesson of the stuck rename field)
        w.installEventFilter(self)
        edit = getattr(w, "lineEdit", None)
        if callable(edit) and edit() is not None:
            edit().installEventFilter(self)
        return w

    def eventFilter(self, obj, event) -> bool:
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.ShortcutOverride:
            event.accept()
            return True
        return False


def hover_menu(b, menu) -> None:
    """``menu`` opens under the button ``b`` when the mouse rests on it (or
    on a click), and closes when the mouse leaves both (his request,
    2026-10-02: it stayed open, and the next one could not open). A popup,
    not exec: nothing waits on it."""
    from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QTimer
    from PySide6.QtGui import QCursor

    def open_menu() -> None:
        if not b.isVisible() or menu.isVisible():
            return
        menu.popup(b.mapToGlobal(QPoint(0, b.height())))
        watch.start()

    def check() -> None:
        if not menu.isVisible():
            watch.stop()
            return
        p = QCursor.pos()
        br = QRect(b.mapToGlobal(QPoint(0, 0)), b.size()).adjusted(
            -2, -2, 2, 4)
        if menu.geometry().adjusted(-6, -6, 6, 6).contains(p) or \
                br.contains(p):
            watch.away = 0
            return
        watch.away += 1
        if watch.away >= 2:              # ~0.3 s out: close
            watch.away = 0
            menu.close()
            watch.stop()
    watch = QTimer(b)
    watch.setInterval(150)
    watch.away = 0
    watch.timeout.connect(check)
    b._watch = watch
    b.clicked.connect(open_menu)

    class _Hover(QObject):
        """Opens the menu when the mouse rests on the button."""

        def eventFilter(self, obj, event) -> bool:
            if event.type() in (QEvent.Enter, QEvent.HoverMove) \
                    and not menu.isVisible() and not self.pending:
                self.pending = True

                def later():
                    self.pending = False
                    if b.underMouse():
                        open_menu()
                QTimer.singleShot(180, later)
            return False
    b.setAttribute(Qt.WA_Hover)
    b._hover = _Hover(b)
    b._hover.pending = False
    b.installEventFilter(b._hover)
