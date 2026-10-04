"""The outliner — every item of the model, in the ArchXQ tab of the side
tray (above the properties, Blender's arrangement).

By level first, highest on top (as the levels strip, N), then the Terrain,
then «Other objects» (whatever is not ArchXQ's: things drawn with the
host's own tools, figures…). Levels › categories › items, indented; an
empty category does not show. Every row has an eye; showing / hiding is
view state, never an undo step. A click on an item selects it in the model
and a selection in the model lights its row (and opens the way to it);
a double-click opens the thing's own window. The search box keeps what
matches (and the rows above it).

The tree is data built by the owner (``ui.outline()``):
    {"key", "label", "kind", "visible", "count", "dim", "children"}
kind: "level" | "terrain" | "other" | "category" | "item".
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import icons

KEY = Qt.UserRole
EYE_COL = 1

CSS = """
QTreeWidget { background: #24272c; border: none; }
QTreeWidget::item { padding: 2px 0; }
QTreeWidget::item:selected { background: rgba(47,111,179,150); color: white; }
QLineEdit#axq_search { background: #2c3238; border: 1px solid #56606b;
    border-radius: 3px; padding: 3px 6px; color: #e8eaed; }
QLineEdit#axq_search:focus { border-color: #2f6fb3; }
"""


class Outliner(QWidget):
    def __init__(self, owner) -> None:
        super().__init__()
        self.owner = owner
        self.setStyleSheet(CSS)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 2)
        lay.setSpacing(4)
        self.search = QLineEdit()
        self.search.setObjectName("axq_search")
        self.search.setPlaceholderText("Search the model…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        lay.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setIconSize(QSize(16, 16))
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        h = self.tree.header()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(EYE_COL, QHeaderView.Fixed)
        self.tree.setColumnWidth(EYE_COL, 26)
        self.tree.itemClicked.connect(self._clicked)
        self.tree.itemDoubleClicked.connect(self._double)
        self.tree.itemExpanded.connect(
            lambda it: self._open.__setitem__(it.data(0, KEY), True))
        self.tree.itemCollapsed.connect(
            lambda it: self._open.__setitem__(it.data(0, KEY), False))
        lay.addWidget(self.tree, 1)
        self._open: dict[str, bool] = {}       # expanded state, by key
        self._items: dict[str, QTreeWidgetItem] = {}
        self._syncing = False

    # ---- build ------------------------------------------------------------------
    def build(self, nodes: list[dict]) -> None:
        self._syncing = True
        top = self.tree.verticalScrollBar().value()
        self.tree.clear()
        self._items.clear()
        for n in nodes:
            self._add(None, n, 0)
        self.tree.verticalScrollBar().setValue(top)
        self._syncing = False
        self._filter(self.search.text())

    def _add(self, parent, n: dict, depth: int) -> None:
        text = n["label"] + (f"  ({n['count']})" if n.get("count") is not None
                             else "")
        it = QTreeWidgetItem([text, ""])
        it.setData(0, KEY, n["key"])
        it.setToolTip(0, n.get("tip", ""))
        if n["kind"] in ("level", "terrain", "other"):
            f = QFont(it.font(0))
            f.setBold(True)
            it.setFont(0, f)
        if n.get("current"):
            it.setForeground(0, QBrush(QColor("#7fb3ff")))
        elif n.get("dim") or not n["visible"]:
            it.setForeground(0, QBrush(QColor("#6b7280")))
        if n.get("eye", True):
            it.setIcon(EYE_COL, icons.icon("eye" if n["visible"]
                                           else "eye_off"))
            it.setToolTip(EYE_COL, "Hide" if n["visible"] else "Show")
        if n["kind"] != "item":
            it.setFlags(it.flags() & ~Qt.ItemIsSelectable)
        if parent is None:
            self.tree.addTopLevelItem(it)
        else:
            parent.addChild(it)
        self._items[n["key"]] = it
        for c in n.get("children", []):
            self._add(it, c, depth + 1)
        # levels, the Terrain and Other start open; categories closed
        default = n["kind"] in ("level", "terrain", "other")
        it.setExpanded(self._open.get(n["key"], default))

    # ---- model ↔ outliner --------------------------------------------------------
    def show_selected(self, keys: set[str]) -> None:
        """Light the rows of what is selected in the model, open the way
        to the first and scroll to it."""
        self._syncing = True
        self.tree.clearSelection()
        first = None
        for k in keys:
            it = self._items.get(k)
            if it is None:
                continue
            it.setSelected(True)
            p = it.parent()
            while p is not None:
                p.setExpanded(True)
                p = p.parent()
            first = first or it
        if first is not None:
            self.tree.scrollToItem(first,
                                   QAbstractItemView.EnsureVisible)
        self._syncing = False

    def _clicked(self, it, col: int) -> None:
        key = it.data(0, KEY)
        if col == EYE_COL and it.icon(EYE_COL) and not it.icon(EYE_COL).isNull():
            self.owner.outliner_toggle(key)
            return
        if self._syncing:
            return
        if key.startswith("level:") or key == "terrain":
            self.owner.set_floor(key.split(":", 1)[1] if ":" in key
                                 else "terrain")
            return
        chosen = [i.data(0, KEY) for i in self.tree.selectedItems()]
        self.owner.outliner_select(chosen)

    def _double(self, it, col: int) -> None:
        if col != EYE_COL:
            self.owner.outliner_open(it.data(0, KEY))

    # ---- search -----------------------------------------------------------------------
    def _filter(self, text: str) -> None:
        t = text.strip().lower()

        def walk(it) -> bool:
            own = not t or t in it.text(0).lower()
            kids = [walk(it.child(i)) for i in range(it.childCount())]
            show = own or any(kids)
            it.setHidden(not show)
            if t and any(kids):
                it.setExpanded(True)
            return show

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))
