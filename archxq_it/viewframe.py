# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""ArchXQ around the host's several views (IngeTrazo 0.6.1).

The host can split the model's area in two, three or four views. ArchXQ's
pieces are children of the main view, so they shrank with it: half the room
with two views, a quarter with four, the bars cut off (his screen, 09/11/2026).

With two or more views the pieces go on the host's grid of views — it always
has the whole area — and the grid gets margins: the views inside, ArchXQ around
them (PLANO_VISTAS_MULTIPLAS.md). With one view nothing changes.

The grid is found by its object name, climbing from the view: no private call
of the host. Not found (another host version): as with one view.

``BarScroll``: a bar wider than the room scrolls with the wheel over it, and
two small arrows say there is more. Nothing shows while it fits.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QRegion
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QToolButton

GRID_NAME = "view_grid"


def grid_of(viewport):
    """The host's grid holding this 3D view, or None."""
    w = viewport
    while w is not None:
        if w.objectName() == GRID_NAME:
            return w
        w = w.parentWidget()
    return None


def several(grid) -> bool:
    """Does this grid show more than one view? (Maximizing one view keeps its
    layout: the main view may be the one hidden then, so it counts as several.)"""
    key = getattr(grid, "layout_key", None)
    try:
        key = key() if callable(key) else key
    except Exception:  # noqa: BLE001 — another host: count the views
        key = None
    if isinstance(key, str):
        return key != "single"
    return sum(1 for v in grid.findChildren(QOpenGLWidget) if v.isVisible()) > 1


def extras(grid, main) -> list:
    """The grid's other 3D views."""
    return [v for v in grid.findChildren(QOpenGLWidget) if v is not main]


def set_margins(grid, left: int, top: int, right: int, bottom: int) -> None:
    """The room around the views. Only when it changes: each change resizes
    the views, and a resize places the pieces again."""
    lay = grid.layout()
    if lay is None:
        return
    m = lay.contentsMargins()
    if (m.left(), m.top(), m.right(), m.bottom()) != (left, top, right, bottom):
        lay.setContentsMargins(left, top, right, bottom)


_ARROW_CSS = ("QToolButton { background: #262a30; color: #f0f2f4; border: none;"
              " border-radius: 3px; font-size: 15px; font-weight: bold;"
              " padding: 0; }"
              "QToolButton:hover { background: #2f7df6; }")


class BarScroll(QObject):
    """One horizontal bar that may be wider than the room it has."""

    STEP = 120          # px per wheel notch / arrow click
    ARROW = 16          # px

    def __init__(self, bar, parent, on_change) -> None:
        super().__init__(bar)
        self.bar = bar
        self.on_change = on_change
        self.offset = 0
        self.over = 0
        self.back = self._arrow("‹", -1, parent)
        self.more = self._arrow("›", 1, parent)
        bar.installEventFilter(self)

    def _arrow(self, text: str, way: int, parent) -> QToolButton:
        b = QToolButton(parent)
        b.setText(text)
        b.setStyleSheet(_ARROW_CSS)
        b.setFocusPolicy(Qt.NoFocus)
        b.setCursor(Qt.ArrowCursor)
        b.setAutoRepeat(True)
        b.clicked.connect(lambda _=False: self.scroll(way))
        b.hide()
        return b

    def arrows(self) -> tuple:
        return (self.back, self.more)

    def scroll(self, way: int) -> None:
        new = max(0, min(self.over, self.offset + way * self.STEP))
        if new != self.offset:
            self.offset = new
            self.on_change()

    def eventFilter(self, obj, event) -> bool:
        # (a button of the bar leaves the wheel to its parent: it arrives here)
        if event.type() == QEvent.Wheel and self.over:
            d = event.angleDelta()
            step = d.y() or d.x()
            if step:
                self.scroll(-1 if step > 0 else 1)
            return True
        return False

    def place(self, x: int, y: int, room: int, width: int, height: int) -> None:
        """The bar at (x, y), ``room`` px for its ``width``."""
        self.over = max(0, width - room)
        self.offset = min(self.offset, self.over)
        self.bar.move(x - self.offset, y)
        # what scrolled away must not show beside a neighbour («Present»).
        # Only sideways: the hub's menus open below its row, inside the hub
        if self.over:
            self.bar.setMask(QRegion(self.offset, 0, room, 1 << 16))
        else:
            self.bar.clearMask()
        shown = not self.bar.isHidden()
        self.back.setVisible(shown and self.offset > 0)
        self.more.setVisible(shown and self.offset < self.over)
        if self.back.isVisibleTo(self.back.parentWidget()):
            self.back.setGeometry(x, y, self.ARROW, height)
            self.back.raise_()
        if self.more.isVisibleTo(self.more.parentWidget()):
            self.more.setGeometry(x + room - self.ARROW, y, self.ARROW, height)
            self.more.raise_()
