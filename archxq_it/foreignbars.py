"""Another extension's bar in ArchXQ's corner of the 3D view.

Extensions float their bars over the view too, and more than one starts at the
top left (OpenTrace BIM, 2026-11-05): ArchXQ's bar covered it, on or off. Nothing
to set: when a bar is where ArchXQ's would go, ArchXQ's goes under it, and follows
it as it grows and shrinks. The other bar is only read, never moved.
"""
from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QWidget

# ArchXQ's own pieces, the host's, and Qt's plain widgets (a rubber band, a field
# in place) are not somebody's bar
_NOT_A_BAR = {(__package__ or "archxq_it").split(".")[0], "views", "core",
              "PySide6", "shiboken6"}


def foreign_bars(viewport) -> list:
    """The other extensions' widgets showing over the 3D view."""
    return [c for c in viewport.children()
            if isinstance(c, QWidget) and not c.isWindow() and not c.isHidden()
            and type(c).__module__.split(".")[0] not in _NOT_A_BAR]


def top_inset(viewport, box: QRect, gap: int, watcher=None) -> int:
    """How far from the top ``box`` (where ArchXQ's bar would sit) must go to
    clear the other bars. A panel taller than a third of the view is not a bar in
    a corner: it never pushes ArchXQ down, nor does the push pass that third.
    ``watcher`` also gets each bar's moves and size changes."""
    limit = viewport.height() // 3
    bars = foreign_bars(viewport)
    if watcher is not None:
        for bar in bars:
            bar.installEventFilter(watcher)
    y = box.top()
    for rect in sorted((b.geometry() for b in bars), key=QRect.top):
        if rect.height() > limit:
            continue
        if rect.intersects(QRect(box.left(), y, box.width(), box.height())):
            y = rect.bottom() + 1 + gap
    return min(y, max(box.top(), limit))
