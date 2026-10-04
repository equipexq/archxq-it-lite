"""The top hub: the sovereign switch and the phases (horizontal).

Hovering a phase drops its submenu (vertical) under it — no click needed;
leaving both the phase and the submenu folds it after a short grace, so
the pointer can travel from the phase down into the menu. Clicking a phase
makes it the current one; clicking a submenu item picks that element (and
its phase, when the item belongs to another reachable phase).
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .phases import ELEMENTS, PHASES
from .style import CSS

MARK = {"done": "✔", "current": "●", "open": "○", "locked": "○"}
SITE = "https://www.xq.com.br/archxq-it"   # ArchXQ IT's page (beta)


def _pro_mark(element: str | None) -> str:
    """The Lite's small «PRO» after an element only the Pro draws (shown,
    never hidden: a Lite that hides them looks poor)."""
    from . import edition
    from .phases import is_pro
    return "   · PRO" if edition.lite() and is_pro(element) else ""


class Hub(QFrame):
    GAP = 4
    GRACE_MS = 280

    def __init__(self, owner, mode: str) -> None:
        super().__init__()
        self.owner = owner
        self.mode = mode              # "viewport" | "toolbar"
        self.bar = None               # host toolbar, in "toolbar" mode
        self._buttons: dict[str, QPushButton] = {}
        self._anchor: QPushButton | None = None
        self._sub_phase: str | None = None
        self.setObjectName("axq_hub")
        self.setStyleSheet(CSS)

        # -- the row ----------------------------------------------------------
        self.row = QFrame(self)
        self.row.setObjectName("axq_row")
        row = QHBoxLayout(self.row)
        row.setContentsMargins(4, 4, 6, 4)
        row.setSpacing(2)

        self.power = QToolButton()
        self.power.setObjectName("axq_power")
        self.power.setText("⏻  ArchXQ")
        self.power.setCheckable(True)
        self.power.setToolTip("Enter / leave the ArchXQ environment "
                              "(the model is not changed)")
        self.power.toggled.connect(owner.set_active)
        self.power.setContextMenuPolicy(Qt.CustomContextMenu)
        self.power.customContextMenuRequested.connect(self._placement_menu)
        row.addWidget(self.power)

        self.env = QWidget()                  # everything hidden when off
        env = QHBoxLayout(self.env)
        env.setContentsMargins(6, 0, 0, 0)
        env.setSpacing(2)
        self.phases = QHBoxLayout()
        self.phases.setSpacing(1)
        env.addLayout(self.phases)
        # (the level you work on is picked in the levels strip — N)
        # import / export: a menu on hover (the place in or out of the
        # 3D view went to the Settings — his call, 2026-10-02)
        from PySide6.QtCore import QSize
        from PySide6.QtWidgets import QMenu

        from . import icons
        from .optionsbar import hover_menu
        io = QToolButton()
        io.setObjectName("axq_swap")
        io.setIcon(icons.icon("io"))
        io.setIconSize(QSize(18, 18))
        io.setToolTip("Import / export")
        menu = QMenu(io)
        menu.setObjectName("axq_menu")
        menu.setStyleSheet(CSS)
        for key, text, el in (("import_dxf", "Import DXF → walls…",
                               "wall_import"), (None, None, None),
                              ("pdf", "Export sheets to PDF…", "export"),
                              ("dxf", "Export drawings to DXF…", "export")):
            if key is None:
                menu.addSeparator()
                continue
            menu.addAction(text + _pro_mark(el)).triggered.connect(
                lambda _=False, k=key: owner.io_action(k))
        hover_menu(io, menu)
        self._io_menu = menu
        env.addWidget(io)
        web = QToolButton()
        web.setObjectName("axq_swap")
        web.setIcon(icons.icon("web"))
        web.setIconSize(QSize(18, 18))
        web.setToolTip(f"ArchXQ on the web — {SITE}")
        web.clicked.connect(lambda: self._open_site())
        env.addWidget(web)
        # the plan grid's pull, on / off (his ask, 2026-10-02)
        from . import prefs
        snap = QToolButton()
        snap.setObjectName("axq_swap")
        snap.setCheckable(True)
        snap.setChecked(bool(prefs.get("grid_snap")))
        snap.setIcon(icons.icon("grid_snap"))
        snap.setIconSize(QSize(18, 18))
        snap.setToolTip("Snap to the plan grid — on / off (in the plan view; "
                        "ends and edges snap first)")
        snap.toggled.connect(owner.set_grid_snap)
        self.grid_snap = snap
        env.addWidget(snap)
        gear = QToolButton()
        gear.setObjectName("axq_gear")
        gear.setText("⚙")
        gear.setToolTip("ArchXQ settings")
        gear.clicked.connect(owner.open_settings)
        env.addWidget(gear)
        row.addWidget(self.env)

        # -- the hover submenu ------------------------------------------------
        self.sub = QFrame(self)
        self.sub.setObjectName("axq_sub")
        self.sub.setStyleSheet(CSS)       # it may be re-parented (toolbar)
        self.sub_lay = QVBoxLayout(self.sub)
        self.sub_lay.setContentsMargins(4, 4, 4, 4)
        self.sub_lay.setSpacing(1)
        self.sub.installEventFilter(self)
        self.sub.hide()
        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self._maybe_close)

    @staticmethod
    def _open_site() -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(SITE))

    # ---- on / off ------------------------------------------------------------
    def set_on(self, on: bool) -> None:
        self.env.setVisible(on)
        if not on:
            self.close_sub()
        self.relayout()
        QTimer.singleShot(0, self.relayout)

    # ---- phases --------------------------------------------------------------
    def fill(self, rows: list[tuple[str, str, str]]) -> None:
        """rows = [(key, label, state)], left to right."""
        self.close_sub()
        # off the bar NOW (hidden: until the loop deletes them they were
        # drawn under the new ones) — but destroyed only by deleteLater: the
        # phase clicked may be the very button whose click runs this
        self._trash = []
        while self.phases.count():
            w = self.phases.takeAt(0).widget()
            if w is not None:
                w.hide()
                self._trash.append(w)
                w.deleteLater()
        self._buttons.clear()
        for i, (key, label, state) in enumerate(rows):
            if i:
                sep = QLabel("›")
                sep.setObjectName("axq_sep")
                self.phases.addWidget(sep)
            b = QPushButton(f"{MARK[state]}  {label}")
            b.setFlat(True)
            b.setProperty("axq", "phase")
            b.setProperty("state", state)
            b.setProperty("phase", key)
            b.setEnabled(state != "locked")
            b.setToolTip(PHASES[key].hint if state != "locked"
                         else "Locked — finish the phases before it")
            b.clicked.connect(lambda _=False, k=key: self.owner.go(k))
            b.installEventFilter(self)
            self.phases.addWidget(b)
            self._buttons[key] = b
        self.relayout()
        QTimer.singleShot(0, self.relayout)

    # ---- hover submenu -------------------------------------------------------
    def open_sub(self, key: str) -> None:
        btn = self._buttons.get(key)
        if btn is None or not btn.isEnabled() or not self.owner.active:
            return
        self._close_timer.stop()
        if self._sub_phase != key:
            while self.sub_lay.count():
                w = self.sub_lay.takeAt(0).widget()
                if w is not None:
                    w.deleteLater()
            for ekey in PHASES[key].elements:
                it = QPushButton(ELEMENTS[ekey].label + _pro_mark(ekey))
                it.setFlat(True)
                it.setCheckable(True)
                it.setChecked(key == self.owner.current
                              and ekey == self.owner.element)
                it.setProperty("axq", "item")
                it.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                it.clicked.connect(
                    lambda _=False, p=key, e=ekey: self._pick(p, e))
                self.sub_lay.addWidget(it)
            self._sub_phase = key
        self._anchor = btn
        self.sub.show()
        self.sub.raise_()
        self.relayout()
        QTimer.singleShot(0, self.relayout)

    def close_sub(self) -> None:
        self._close_timer.stop()
        self._sub_phase = None
        self._anchor = None
        if self.sub.isVisible():
            self.sub.hide()
            self.relayout()

    def _pick(self, phase: str, element: str) -> None:
        self.close_sub()
        self.owner.pick(phase, element)

    def _maybe_close(self) -> None:
        if self.sub.underMouse():
            return
        if any(b.underMouse() for b in self._buttons.values()):
            return
        self.close_sub()

    def eventFilter(self, obj, event) -> bool:
        et = event.type()
        if obj is self.sub:
            if et == QEvent.Enter:
                self._close_timer.stop()
            elif et == QEvent.Leave:
                self._close_timer.start(self.GRACE_MS)
            return False
        key = obj.property("phase") if hasattr(obj, "property") else None
        if key:
            if et == QEvent.Enter:
                self.open_sub(key)
            elif et == QEvent.Leave:
                self._close_timer.start(self.GRACE_MS)
            return False
        # toolbar mode: the window moved things around — re-hang the menu
        if et in (QEvent.Resize, QEvent.Move):
            QTimer.singleShot(0, self.relayout)
        return False

    def _placement_menu(self, pos) -> None:
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self.power)
        for key, text in (("viewport", "Over the 3D view"),
                          ("toolbar", "Own bars around the 3D view")):
            act = menu.addAction(text)
            act.setCheckable(True)
            act.setChecked(self.mode == key)
            act.triggered.connect(
                lambda _=False, k=key: self.owner.set_placement(k))
        menu.exec(self.power.mapToGlobal(pos))

    # ---- geometry ------------------------------------------------------------
    def relayout(self) -> None:
        if not self.owner.alive:
            return
        for w in self.findChildren(QWidget) + self.sub.findChildren(QWidget):
            w.ensurePolished()
        self.row.layout().activate()
        self.row.adjustSize()
        self.row.move(0, 0)
        w, h = self.row.width(), self.row.height()
        btn = self._anchor
        show_sub = self.sub.isVisible() and btn is not None
        if show_sub:
            self.sub.layout().activate()
            self.sub.adjustSize()
            self.sub.resize(max(self.sub.width(), btn.width()),
                            self.sub.height())
        if self.mode == "toolbar":
            self.setFixedSize(w, h)
            if show_sub and self.bar is not None:
                host = self.sub.parentWidget()
                x = btn.mapTo(host, QPoint(0, 0)).x()
                y = self.bar.mapTo(host, QPoint(0, self.bar.height())).y()
                self.sub.move(x, y + self.GAP)
                self.sub.raise_()
            return
        if show_sub:
            x = btn.mapTo(self, QPoint(0, 0)).x()
            self.sub.move(x, h + self.GAP)
            w = max(w, x + self.sub.width())
            h = h + self.GAP + self.sub.height()
        self.resize(w, h)
        self.raise_()
