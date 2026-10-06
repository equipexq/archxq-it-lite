"""GUIDE LINES from inside ArchXQ (his ask, 2026-10-05: «inside ArchXQ,
using IngeTrazo's Edit menu mixes things up»). The guides ARE IngeTrazo's
own construction guides — the same lines, the same snap (the snap engine
takes them as edges: their crossings too) — ArchXQ only puts the buttons
where the work is: the hub's Guides menu.

- Guide line  → IngeTrazo's Tape Measure: click an edge, move, type the
  distance + Enter — a guide parallel to that edge (an axis, a plot side
  at any angle).
- Delete a guide → GuideEraseTool here: the guide under the cursor shows
  in red, a click deletes it — guides ONLY (the host's Eraser also erases
  the model when the click misses). One Ctrl+Z each.
- Delete all guides → one Ctrl+Z.
"""
from __future__ import annotations

from tools.base import Tool

from . import compat

RED = "#e5484d"


def guides(viewport) -> list:
    return list(getattr(viewport.scene, "guides", None) or [])


def delete(viewport, gs) -> int:
    """Delete ``gs`` (the host's command: one Ctrl+Z)."""
    from core.history import DeleteGuidesCommand
    gs = [g for g in gs if g in guides(viewport)]
    if gs:
        viewport.history.execute(DeleteGuidesCommand(gs))
        viewport.update()
    return len(gs)


def tape(viewport) -> None:
    """IngeTrazo's Tape Measure — a guide at a typed distance from an edge."""
    viewport.window()._activate_tool("tape")
    compat.flash(viewport, "Guide line: click an edge, move off it and type "
                 "the distance + Enter  ·  Esc = done", 8000)


class GuideEraseTool(Tool):
    """Delete guide lines one by one: the one under the cursor turns red,
    a click deletes it. Stays out for the next; Esc = done."""
    name = "ArchXQ delete guide"
    icon = "eraser"
    uses_snap = False
    creates = False

    def __init__(self, on_cancelled) -> None:
        super().__init__()
        self.on_cancelled = on_cancelled
        self.viewport = None
        self.hot = None

    def on_activate(self, viewport) -> None:
        self.viewport = viewport
        compat.flash(viewport, "Delete guide: click a guide line  ·  Esc = "
                     "done", 600000)

    def on_deactivate(self, viewport) -> None:
        compat.flash(viewport, "", 1)

    def _under(self, ctx):
        s = getattr(ctx, "screen", None)
        if s is None or self.viewport is None:
            return None
        return self.viewport.pick_guide(s.x(), s.y())

    def on_hover(self, ctx) -> None:
        g = self._under(ctx)
        if g is not self.hot:
            self.hot = g
            self.viewport.update()

    def on_click(self, ctx) -> None:
        g = self._under(ctx)
        if g is None:
            compat.flash(self.viewport, "Not on a guide — click right on the "
                         "dashed line", 3000)
            return
        self.hot = None
        delete(self.viewport, [g])
        left = len(guides(self.viewport))
        compat.flash(self.viewport, f"Guide deleted — {left} left  ·  "
                     "Ctrl+Z brings it back  ·  Esc = done", 4000)
        if not left and self.on_cancelled:       # nothing more to delete
            self.on_cancelled()

    def on_cancel(self, viewport) -> None:
        if self.on_cancelled:
            self.on_cancelled()

    def draw_overlay(self, viewport, painter) -> None:
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen
        g = self.hot
        if g is None or g not in guides(viewport):
            return
        seg = viewport._guide_snap_segment(g)
        if not seg:
            return
        a = viewport._world_to_pixel(seg[0])
        b = viewport._world_to_pixel(seg[1])
        if not (a and b):
            return
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(RED), 3))
        painter.drawLine(QPointF(*a), QPointF(*b))
        painter.restore()
