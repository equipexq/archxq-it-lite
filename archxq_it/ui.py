# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""ArchXQ — the conductor.

Screen plan (the user's):
    TOP     phases, horizontal; each phase's elements drop under it on hover
    LEFT    how to draw the picked element (its methods / actions)
    RIGHT   the picked element's properties (a tab of the side tray)
    BOTTOM  what is shown and how: floors, parts, view, camera

The «⏻ ArchXQ» switch is sovereign: off, every ArchXQ piece goes away
and the user works in plain IngeTrazo; the model is never touched.

ONE placement: the pieces float over the 3D view ("viewport"). The
«toolbar» placement of the prototype (bars of their own around the view)
is no longer offered (2026-10-07); compat.place still knows it.

Document: ``model.load`` / ``save`` (project, levels, system, done).
Session: on/off, phase, element, method, floor.
"""
from __future__ import annotations

import copy
import functools
import math

from PySide6.QtCore import QEvent, QObject, QRect, QSettings, Qt, QTimer
from PySide6.QtWidgets import QDialog

from . import compat, edition, foreignbars, model, paintlog, viewframe
from . import profiles as PF
from .i18n import tr
from .hub import Hub
from .levelstrip import LevelStrip
from .panels import ElementsBox, PropsPanel, SideStrip, ViewBar
from .phases import (ELEMENTS, PHASES, TOOLS, is_pro, next_open, order,
                     reachable)
from .style import BAR_CSS

#: an element → the phase it is drawn in (the library follows the phase)
PHASE_OF = {el: k for k, p in PHASES.items() for el in p.elements}

MARGIN = 4          # gap between the floating pieces and the 3D view's edge
AUTO_PHASES = {"project", "terrain"}     # complete themselves (real checks)
PLOT_Z = -0.002     # the plot sits 2 mm under the ground floor (no z-fight)
PLOT_COLOR = (0.56, 0.63, 0.47)
PLOT_TOOLS = {"Rectangle": "PlotRectTool", "Point by point": "PlotPolyTool",
              "Rectangle from centre": "PlotCentreRectTool",
              "Rotated rectangle": "PlotRotRectTool"}
PLOT_TABLE = "Sides & heights…"     # Edit plot: the table (also double-click)
DIG_TOOLS = {"Rectangle": "PlotRectTool",                  # Excavation: how
             "Rectangle from centre": "PlotCentreRectTool",
             "Rotated rectangle": "PlotRotRectTool",
             "Point by point": "PlotPolyTool",
             "Circle": "PlotCircleTool",
             "Ramp": "PlotRampTool"}
FOLD_LINE = "Fold line"             # Edit plot: where a sloped plot folds
EDIT_POINTS = {"Move points": "move", "Add point": "add",   # Edit plot:
               "Delete point": "delete"}                    # the corners
SETBACK_TOOL = "Mark front sides"   # Setbacks: which sides face the street
SURVEY_TOOLS = {"Add point": "add", "Delete point": "delete"}
SURVEY_TABLE = "Points & import…"
#: how a wall is drawn — picked in its options bar: (value, icon, tip)
WALL_SHAPES = [
    ("chain", "geopath", "Point by point — wall after wall"),
    ("rect", "rectangle", "Rectangle — four walls, corner to corner"),
    ("rect_c", "rectangle_center", "Rectangle from its centre"),
    ("rect_r", "rotated_rect", "Rotated rectangle"),
    ("arc3", "arc3", "Curved wall — start, end, and a point on the curve"),
    ("arc_c", "center_arc", "Curved wall — from its centre"),
    ("circle", "circle", "Round wall — a whole circle"),
]
#: how a ROOM SEPARATOR is drawn (0.17.0): the wall's, without the arcs
SEP_SHAPES = [
    ("chain", "geopath", "Point by point — from wall to wall (C closes it)"),
    ("rect", "rectangle", "Rectangle — a zone inside a room, corner to "
                          "corner"),
    ("rect_c", "rectangle_center", "Rectangle from its centre"),
    ("rect_r", "rotated_rect", "Rotated rectangle"),
    ("circle", "circle", "Circle — a round zone (centre, then its edge or "
                         "a radius)"),
]
#: the structure's shapes, in their options bars: (value, icon, tip)
COLUMN_SHAPES = [
    ("single", "col_single", "Stamp columns — it rides the cursor: each "
                             "click places one (Esc = done)"),
    ("draw", "rectangle", "Draw a column — two opposite corners: its size "
                          "and its place (the size is kept for the next)"),
    ("row", "col_row", "A row of columns — point by point, like a wall: "
                       "each stretch by count or spacing, a column on each "
                       "corner; the first point again closes it. It stays "
                       "a group: double-click a column of it to change "
                       "them all (the last row follows the bar until the "
                       "next one)"),
    ("grid", "col_grid", "A grid of columns — two opposite corners "
                         "(«Columns» × «Rows»)"),
    ("corners", "col_corners", "At the wall corners — one click: a column "
                               "wherever this level's walls meet"),
]
BEAM_SHAPES = [
    ("chain", "geopath", "Point by point — beam after beam"),
    ("walls", "beam_walls", "Along the walls — one click: a beam over "
                            "every straight wall of this level"),
]
SLAB_SHAPES = [
    ("walls", "slab_walls", "Inside the walls — one click: the slab under "
                            "this level's walls, to their outer faces"),
    ("rect", "rectangle", "Rectangle — corner to corner"),
    ("rect_c", "rectangle_center", "Rectangle from its centre"),
    ("rect_r", "rotated_rect", "Rotated rectangle"),
    ("chain", "geopath", "Point by point"),
    ("hole", "slab_hole", "Opening in a slab — draw it inside the slab "
                          "(a stair, a lift, a void): a rectangle, rotated, "
                          "point by point or a circle («Drawn», on the bar)"),
]
FOOTING_SHAPES = [
    ("pads", "foot_pads", "Under the columns — one click: a pad under "
                          "every column of this level"),
    ("strips", "foot_strips", "Under the walls — one click: a strip "
                              "footing under every wall of this level"),
    ("rows", "foot_rows", "Under the column rows — one click: a strip "
                          "footing along every row of columns of this level"),
    # drawn by hand (his ask, 2026-11-01: a new file with no columns or
    # walls had no way to make a footing at all)
    ("pad", "foot_pad", "Pad — drawn: a click each (on a column it is "
                        "centred under it and never smaller than it + 0.20)"),
    ("strip", "foot_strip", "Strip footing — drawn point by point, like a "
                            "run of walls (width: «Strip»)"),
    # (his ask, 07/11/2026: footings with no column over them — a timber
    # house's — drawn as a row of columns is)
    ("path", "foot_path", "Footings along a path — point by point, like a "
                          "row of columns: pads by count or spacing, a "
                          "strip, or both. It stays a group: double-click "
                          "one to change them all"),
]
#: the openings' options bars: one way to place them — on a wall
OPENING_SHAPES = {
    "door": [("wall", "op_door", "A door — move along a wall, click where "
                                 "it goes (Tab: its hinge on the other "
                                 "side)")],
    "window": [("wall", "op_window", "A window — move along a wall, click "
                                     "where it goes")],
    "void": [("wall", "op_void", "An opening with nothing in it — move "
                                 "along a wall, click where it goes")],
}
ROOF_SHAPES = [
    ("walls", "roof_walls", "Over the walls — one click: a roof over this "
                            "level's walls (hip / gable: over an L too; "
                            "otherwise the rectangle round them)"),
    ("rect", "rectangle", "Rectangle — corner to corner"),
    ("rect_c", "rectangle_center", "Rectangle from its centre"),
    ("rect_r", "rotated_rect", "Rotated rectangle"),
    ("chain", "geopath", "Point by point (hip / gable: an L of 6 corners "
                         "at right angles stays an L; otherwise a pitched "
                         "roof takes the rectangle round it)"),
]
#: the documentation's bars: actions, one click each
SHEET_ACTIONS = [
    ("make", "doc_sheets", "Make the drawings and their sheets — one click: "
                           "a plan of every level (cut at «Cut»), the four "
                           "elevations and sections A-A, B-B, each on a "
                           "sheet with its title block. Made again, it "
                           "replaces only the sheets ArchXQ made"),
    ("open", "doc_open", "Open the sheets (IngeTrazo's sheet composer: add "
                         "dimensions, level marks, labels, notes…)"),
]
EXPORT_ACTIONS = [
    ("pdf", "doc_pdf", "Export every sheet to ONE PDF"),
    ("dxf", "doc_dxf", "Export every drawing to DXF — one file per sheet, "
                       "true size in metres, layers by line (cut, profile, "
                       "edge, hidden), room names, dimensions, levels"),
]
DXF_ACTIONS = [
    ("cad", "doc_dxf", "Import a CAD plan — everything at once: load it and "
                       "make the walls, doors and windows (from its blocks), "
                       "columns, stairs and rooms' names (each layer read "
                       "from its name: A-WALL, PAREDE, PORTA, JANELA…)"),
    ("load", "io", "Load a DXF plan onto the current level — a reference "
                   "drawn over the view (the model is not changed)"),
    ("make", "beam_walls", "Make the building from its lines: each pair of "
                           "parallel lines (thickness between Min and Max) "
                           "is a wall; a gap in its lines, an opening (the "
                           "block in it says door or window); the columns, "
                           "stairs and rooms' names too"),
    ("clear", "eraser", "Remove the drawing from this level"),
]
ROOM_ACTIONS = [
    ("names", "doc_rooms", "Name the rooms of the current level — a table "
                           "with their areas and perimeters. The rooms are "
                           "found from the walls by themselves"),
]
SECTION_SHAPES = [
    ("line", "line", "Draw a section line — two clicks in plan; you look "
                     "to its LEFT (Tab: the other way). Its sheet is made "
                     "at once"),
    ("clear", "eraser", "Remove the sections you drew (and their sheets)"),
]
#: shapes that are one click (they act at once — nothing to draw)
STRUCT_ACTIONS = {("column", "corners"), ("beam", "walls"),
                  ("slab", "walls"), ("footing", "pads"),
                  ("footing", "strips"), ("footing", "rows"),
                  ("roof", "walls")}
LEVELS_KEY = Qt.Key_N               # shows / hides the levels strip
TERRAIN_ROW = "terrain"             # the levels strip's row at the ground
PLAN_CUT_TAG = "archxq_plan_cut"    # a group not ArchXQ's, hidden by the plan


class _Watch(QObject):
    """Re-place the floating pieces when the 3D view is resized."""

    def __init__(self, fn) -> None:
        super().__init__()
        self.fn = fn

    def eventFilter(self, obj, event) -> bool:
        # (a new child of the view, or another extension's bar changing:
        # foreignbars.py — ArchXQ's bar goes under it)
        if event.type() in (QEvent.Resize, QEvent.ChildPolished, QEvent.Show,
                            QEvent.Hide, QEvent.Move):
            QTimer.singleShot(0, self.fn)
        return False


class _PresentEsc(QObject):
    """While presenting, Esc brings ArchXQ back — taken before the host's
    own Esc (its select tool) and its shortcuts see it."""

    def __init__(self, owner) -> None:
        super().__init__()
        self.owner = owner

    def eventFilter(self, obj, event) -> bool:
        if not getattr(self.owner, "presenting", False):
            return False
        t = event.type()
        if t in (QEvent.ShortcutOverride, QEvent.KeyPress) \
                and event.key() == Qt.Key_Escape:
            if t == QEvent.KeyPress:
                self.owner.toggle_present()
            event.accept()
            return True
        return False


class _ToolEsc(QObject):
    """Esc with an ArchXQ tool out and something SELECTED: the host's Esc
    only clears the selection (its order: typed value, a busy tool, the
    selection, then the tool) — his test, 29/10: «o ESC não funcionava, eu
    não conseguia sair da ferramenta». The selection goes quietly here,
    and the host's Esc then ends the tool, at the first press."""

    def __init__(self, viewport) -> None:
        super().__init__()
        self.viewport = viewport

    def eventFilter(self, obj, event) -> bool:
        try:
            # (the host's Esc is a menu shortcut, «Cancel current tool»:
            # only its ShortcutOverride comes through, before it fires)
            if event.type() not in (QEvent.ShortcutOverride, QEvent.KeyPress) \
                    or event.key() != Qt.Key_Escape \
                    or event.modifiers() != Qt.NoModifier:
                return False
            vp = self.viewport
            tool = getattr(vp, "active_tool", None)
            if not compat.ours(tool) or compat.typed_value(vp):
                return False
            busy = getattr(vp, "_tool_busy", None)
            if callable(busy) and busy(tool):
                return False                 # Esc drops the step under way
            sel = getattr(vp.scene, "selection", None)
            if isinstance(sel, set) and sel:
                compat.select_ids(vp, set())
        except Exception:  # noqa: BLE001 — never in the host's way
            compat.log_error("tool Esc")
        return False


class _GeoWatch(QObject):
    """The ArchXQ panel, floating: its place and size kept as it is moved
    or resized (back there next time)."""

    def __init__(self, dock) -> None:
        super().__init__()
        self.dock = dock

    def eventFilter(self, obj, event) -> bool:
        if event.type() in (QEvent.Move, QEvent.Resize) and \
                self.dock.isFloating():
            QSettings().setValue("archxq/dock_geometry",
                                 self.dock.saveGeometry())
        return False


class _SpacePan(QObject):
    """SPACE held + the mouse moved = PAN, an ArchXQ tool still out (his
    ask, 2026-10-19: in the plan, panning meant holding the wheel down —
    «tiring, tendinitis»). No button needed; a click meanwhile places
    nothing. With a host tool (or none) Space stays the host's «Select»."""

    def __init__(self, viewport) -> None:
        super().__init__()
        self.viewport = viewport
        self.held = False
        self.last = None
        self.on = None             # the view with the hand on it

    def _ours(self) -> bool:
        return compat.ours(getattr(self.viewport, "active_tool", None))

    @staticmethod
    def _hand_off(view) -> None:
        try:
            view.unsetCursor()
            if hasattr(view, "_apply_nav_cursor"):
                view._apply_nav_cursor()
        except Exception:  # noqa: BLE001 — (a view gone with its layout)
            pass

    def _stop(self) -> None:
        if self.held:
            self.held = False
            self.last = None
            self._hand_off(self.on or self.viewport)
            self.on = None

    def eventFilter(self, obj, event) -> bool:
        t = event.type()
        if t in (QEvent.ShortcutOverride, QEvent.KeyPress, QEvent.KeyRelease):
            if event.key() != Qt.Key_Space or \
                    event.modifiers() != Qt.NoModifier:
                return False
            if t == QEvent.KeyRelease:
                if not event.isAutoRepeat():
                    self._stop()
                    return True
                return self.held
            if not self._ours():
                return False
            event.accept()                 # not the host's «Select»
            if t == QEvent.KeyPress and not self.held:
                self.held = True
                self.last = None
                self.on = self.viewport
                self.viewport.setCursor(Qt.OpenHandCursor)
            return True
        if not self.held:
            return False
        if t == QEvent.WindowDeactivate:   # (Alt+Tab with Space held)
            self._stop()
            return False
        if not isinstance(obj, type(self.viewport)):   # (the window)
            return False
        if t == QEvent.MouseMove:
            p = event.position()
            if obj is not self.on:         # the mouse went to another view
                self._hand_off(self.on or self.viewport)
                self.on = obj
                self.last = None
                obj.setCursor(Qt.OpenHandCursor)
            if self.last is not None:
                dx, dy = p.x() - self.last.x(), p.y() - self.last.y()
                if dx or dy:
                    try:
                        obj.camera.pan(dx, dy, obj.height())
                        obj.update()
                    except Exception:  # noqa: BLE001
                        pass
            self.last = p
            return True                    # the tool's preview stays put
        if t in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease,
                 QEvent.MouseButtonDblClick) and \
                event.button() == Qt.LeftButton:
            return True                    # no point placed while panning
        return False


class _SectionPick(QObject):
    """SECTION LINES in the plan (sections.py, Documentation phase, the
    host's Select tool out): a click on one picks it — its grips then
    move it (``grip_targets``); a click on its small look arrow flips
    its look; Delete removes a drawn one, Esc lets it go. Installed BEFORE
    the grips: a press on a grip never reaches here."""

    def __init__(self, ui) -> None:
        super().__init__()
        self.ui = ui
        self.eat = False

    def _hit(self, x, y):
        """(the line under (x, y), on its flip arrow?) — or (None, False)."""
        from . import sections as SC
        ui = self.ui
        at = ui._plan_level(ui.viewport)
        if at is None:
            return None, False
        z = at[2]
        px = lambda p: compat.to_pixel(ui.viewport, p[0], p[1], z)  # noqa
        best = None
        for ln in ui._sec_lines():
            if ln["id"] == ui._sec_picked:
                tip, m = px(SC.look_tip(ln)), px(SC.flip_foot(ln))
                if tip and m and SC._seg_dist((x, y), m, tip) <= 6:
                    return ln, True
            a, b = px(ln["a"]), px(ln["b"])
            if not (a and b):
                continue
            d = SC._seg_dist((x, y), a, b)
            if d <= SC.PICK_PX and (best is None or d < best[0]):
                best = (d, ln)
        return (best[1] if best else None), False

    def eventFilter(self, obj, event) -> bool:
        ui = self.ui
        t = event.type()
        try:
            on = ui._sec_on()
        except Exception:  # noqa: BLE001 — never in the host's way
            on = False
        if t in (QEvent.ShortcutOverride, QEvent.KeyPress) \
                and getattr(ui, "_cut3d", None) is not None \
                and not ui.plan_on and event.key() == Qt.Key_Escape \
                and event.modifiers() == Qt.NoModifier:
            event.accept()                   # the 3D cut off (Esc)
            if t == QEvent.KeyPress:
                ui._cut3d_off()
            return True
        if t in (QEvent.ShortcutOverride, QEvent.KeyPress):
            if not (on and ui._sec_picked) or event.modifiers() \
                    != Qt.NoModifier or event.key() not in (
                        Qt.Key_Delete, Qt.Key_Escape):
                return False
            event.accept()
            if t == QEvent.KeyPress:
                if event.key() == Qt.Key_Escape:
                    ui._sec_pick(None)
                else:
                    QTimer.singleShot(0, ui._section_delete_picked)
            return True
        if t == QEvent.MouseButtonRelease and self.eat:
            self.eat = False
            return True
        if t == QEvent.MouseButtonDblClick and on \
                and event.button() == Qt.LeftButton:
            # a double-click on a line = its section, in the studio (his
            # call, 24/10: «todo mundo vai querer fazer assim»)
            p = event.position()
            ln, _flip = self._hit(p.x(), p.y())
            if ln is None:
                return False
            self.eat = True
            QTimer.singleShot(0, lambda i=ln["id"]: ui.doc_studio(
                "studio", "section:" + i))
            return True
        if t != QEvent.MouseButtonPress or event.button() != Qt.LeftButton:
            return False
        if not on:
            # (Orbit, Pan… in the plan: the line stays picked — it goes
            # out of the plan, the phase…)
            if ui._sec_picked and not ui._sec_shown():
                ui._sec_pick(None)
            return False
        p = event.position()
        ln, flip = self._hit(p.x(), p.y())
        if ln is None:
            if ui._sec_picked:
                ui._sec_pick(None)
            return False
        self.eat = True
        if flip:
            QTimer.singleShot(0, lambda i=ln["id"]: ui._section_flip(i))
        else:
            ui._sec_pick(ln["id"])
        return True


class _KeyClaim(QObject):
    """A menu shortcut beats the viewport to its key (C opened the host's
    Circle in the middle of a plot). While an ArchXQ tool is out, the keys
    it claims are taken back from the shortcut system — Qt then delivers
    them to the viewport, which hands them to the tool."""

    def __init__(self, viewport) -> None:
        super().__init__()
        self.viewport = viewport

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.ShortcutOverride:
            tool = getattr(self.viewport, "active_tool", None)
            keys = getattr(tool, "claimed_keys", ())
            # (PySide6: modifiers is a Flag — int() of it raises)
            if (compat.ours(tool)
                    and event.key() in keys
                    and (event.modifiers() == Qt.NoModifier
                         or event.key() == Qt.Key_Backtab)):  # Shift+Tab
                event.accept()
                return True
        if event.type() == QEvent.KeyPress \
                and event.key() in (Qt.Key_Tab, Qt.Key_Backtab):
            # Tab / Shift+Tab: Qt's QWidget.event moves the focus on with
            # them and the tool never saw them (2026-10-15: a door's
            # Shift+Tab did nothing) — straight to the viewport's handler
            tool = getattr(self.viewport, "active_tool", None)
            if compat.ours(tool) and event.key() in getattr(
                    tool, "claimed_keys", ()):
                self.viewport.keyPressEvent(event)
                return True
        return False


class _ToolCursorBack(QObject):
    """Leaving an ArchXQ piece (arrow), the pointer goes back to the
    active tool's (the pencil…) — the host only sets it when the tool
    changes."""

    def __init__(self, viewport) -> None:
        super().__init__()
        self.viewport = viewport

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Leave:
            QTimer.singleShot(0, lambda: compat.tool_cursor(self.viewport))
        return False


class _HoverOff(QObject):
    """The pointer leaves the 3D view (over the library, the strips): the
    ArchXQ tool drawing stops following it — its preview and rubber band
    go until it comes back (his test, 2026-10-15: over the right strip the
    low wall kept being drawn to the edge of the view)."""

    def __init__(self, viewport) -> None:
        super().__init__()
        self.viewport = viewport

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Leave:
            tool = getattr(self.viewport, "active_tool", None)
            if compat.ours(tool) and getattr(tool, "hover", None) is not None:
                try:
                    tool.hover = None
                    if hasattr(tool, "_sync"):
                        tool._sync()
                except Exception:  # noqa: BLE001 — a preview only
                    pass
                self.viewport.update()
        return False


class _DialogReaper(QObject):
    """ArchXQ's windows (a wall's, a stair's, a door's…) are made with the
    main window as parent and were never deleted: each one opened stayed in
    memory with its tabs and pictures (~20 wall windows after an afternoon,
    2026-11-01). When a new one shows, those already closed go — by
    deleteLater, so never under code that still reads them (it runs once
    the event loop is back)."""

    ROOT = __name__.split(".")[0]

    def __init__(self) -> None:
        super().__init__()
        self.closed: list = []

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.ChildPolished:
            d = event.child()
            if (isinstance(d, QDialog) and not getattr(d, "_axq_reap", False)
                    and type(d).__module__.split(".")[0] == self.ROOT):
                d._axq_reap = True
                self._reap()
                d.finished.connect(lambda _r=0, d=d: self.closed.append(d))
        return False

    def _reap(self) -> None:
        keep = []
        for d in self.closed:
            try:
                if d.isVisible():             # opened again (exec once more)
                    keep.append(d)
                else:
                    d.deleteLater()
            except RuntimeError:              # already gone
                pass
        self.closed = keep


class _LevelsKey(QObject):
    """N shows / hides the levels strip (Blender's N panel) — only when
    nothing is being typed into the measurements box."""

    def __init__(self, owner) -> None:
        super().__init__()
        self.owner = owner

    def eventFilter(self, obj, event) -> bool:
        o = self.owner
        if (event.type() == QEvent.KeyPress and event.key() == LEVELS_KEY
                and event.modifiers() == Qt.NoModifier and not event.isAutoRepeat()
                and o.alive and o.active
                and not compat.typed_value(o.viewport)):
            o.toggle_levels_strip()
            return True
        return False


PRO_NOTE = "Beams, slabs, openings, roofs, sheets and DXF are in ArchXQ IT Pro"


def _pro_module(name: str):
    """A module only ArchXQ IT Pro ships (docs, importdxf…), or None in
    the Lite — which is built without them."""
    import importlib
    full = f"{__package__}.{name}"
    try:
        return importlib.import_module(full)
    except ModuleNotFoundError as e:
        if e.name != full:              # the module is there, but broken:
            raise                       # never hide a real error
        return None


class _RadialClick(QObject):
    """The radial menu's watch on the 3D view: a plain click of the
    Select tool (no drag) that selects a movable element opens the ring
    there; a press elsewhere, Esc or the pointer going far closes it."""

    def __init__(self, owner) -> None:
        super().__init__()
        self.owner = owner
        self.down = None

    def eventFilter(self, obj, event) -> bool:
        o = self.owner
        ring = getattr(o, "radial", None)
        if ring is None or not o.alive:
            return False
        t = event.type()
        if t == QEvent.MouseButtonPress:
            ring.dismiss()
            if event.button() == Qt.LeftButton:
                p = event.position()
                self.down = (p.x(), p.y())
        elif t == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            p = event.position()
            d, self.down = self.down, None
            if d and math.dist(d, (p.x(), p.y())) < 5 and o.active \
                    and compat.selecting(o.viewport):
                x, y = p.x(), p.y()
                QTimer.singleShot(80, lambda: o.radial_after_click(x, y, obj))
        elif t == QEvent.MouseMove and ring.isVisible():
            p = event.position()
            if ring.far(p.x(), p.y(), obj):
                ring.dismiss()
        elif t == QEvent.KeyPress and event.key() == Qt.Key_Escape \
                and ring.isVisible():
            ring.dismiss()
            return True
        return False


class _PickThrough(QObject):
    """In an elevation (or the X-ray plan) the Select tool's click picks
    THROUGH — ArchXQ's own pick (``ArchXQ.pick_through``); its release is
    swallowed too. Nothing of ours under it: the host's click, as ever."""

    def __init__(self, owner) -> None:
        super().__init__()
        self.owner = owner
        self.eat_release = False

    def eventFilter(self, obj, event) -> bool:
        t = event.type()
        if t == QEvent.MouseButtonRelease and self.eat_release \
                and event.button() == Qt.LeftButton:
            self.eat_release = False
            return True
        if t in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick) \
                and event.button() == Qt.LeftButton:
            # the host's own click takes groups of a level hidden by its eye
            # (his test, 29/10: walls of a hidden level selected, «ghosts»):
            # the click goes to what is SHOWN there, or to nothing
            p = event.position()
            try:
                ghost = self.owner.ghost_under(p.x(), p.y())
            except Exception:  # noqa: BLE001 — the host's click then
                ghost = False
            if ghost:
                if t == QEvent.MouseButtonPress:
                    add = bool(event.modifiers() & (Qt.ShiftModifier
                                                    | Qt.ControlModifier))
                    try:
                        done = self.owner.pick_through(p.x(), p.y(), add)
                    except Exception:  # noqa: BLE001
                        done = False
                    if not done and not add:
                        compat.select(self.owner.viewport, [], "replace")
                self.eat_release = True
                return True
        if t == QEvent.MouseButtonDblClick \
                and event.button() == Qt.LeftButton \
                and not self.owner.picking_through():
            # the plain plan: a door's symbol double-clicked opens ITS
            # window (not the host's editing of the slab under it)
            p = event.position()
            try:
                gid = self.owner.plan_glazing_at(p.x(), p.y())
            except Exception:  # noqa: BLE001
                gid = None
            if gid:                       # a glass grid: its own window
                QTimer.singleShot(0, lambda: self.owner.edit_element(gid))
                self.eat_release = True
                return True
            try:                          # an EMPTY Opening (3D or plan)
                vid = self.owner.void_at(p.x(), p.y())
            except Exception:  # noqa: BLE001
                vid = None
            if vid:
                QTimer.singleShot(0, lambda: self.owner.edit_opening(vid))
                self.eat_release = True
                return True
            try:                          # a SLAB's opening: the slab's window
                hid = self.owner._slab_hole_at(p.x(), p.y())
            except Exception:  # noqa: BLE001
                hid = None
            if hid:
                sid = hid[len(self.owner.HOLE):].rsplit(":", 1)[0]
                QTimer.singleShot(0, lambda: self.owner.edit_element(sid))
                self.eat_release = True
                return True
            try:
                oid = self.owner.plan_opening_at(p.x(), p.y())
            except Exception:  # noqa: BLE001
                oid = None
            if oid:
                QTimer.singleShot(0, lambda: self.owner.edit_opening(oid))
                self.eat_release = True
                return True
        if t == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            o = self.owner
            p = event.position()
            add = bool(event.modifiers() & (Qt.ShiftModifier
                                            | Qt.ControlModifier))
            if not o.picking_through():
                # the plain plan: a click on a door's / window's symbol
                # picks it (the host's took the slab or the plot under it)
                try:
                    done = o.plan_opening_pick(p.x(), p.y(), add)
                except Exception:  # noqa: BLE001 — the host's click then
                    done = False
                if done:
                    self.eat_release = True
                    return True
                return False
            try:
                done = o.pick_through(p.x(), p.y(), add)
            except Exception:  # noqa: BLE001 — the host's click then
                done = False
            if done:
                self.eat_release = True
                return True
        return False


class _PlotDoubleClick(QObject):
    """Double-click on the plot (Select tool out) opens the plot table
    instead of the host's group editing."""

    def __init__(self, owner) -> None:
        super().__init__()
        self.owner = owner
        #: (when, the ids selected) at the last press — a double-click's
        #: first click leaves only the one clicked selected (L1, 31/10)
        self.before = (0.0, set())

    def _batch_back(self, rid) -> None:
        """Double-clicked one of several selected: they are selected again
        — its window changes them all."""
        import time
        when, ids = self.before
        if rid in ids and len(ids) > 1 and time.monotonic() - when < 1.0:
            compat.select_ids(self.owner.viewport, set(ids))

    def eventFilter(self, obj, event) -> bool:
        o = self.owner
        if (event.type() == QEvent.MouseButtonPress
                and event.button() == Qt.LeftButton and o.alive):
            import time
            self.before = (time.monotonic(), {
                compat._rec(g).get("id")
                for g in compat.selected_groups(o.viewport)} - {None})
        if (event.type() == QEvent.MouseButtonDblClick
                and event.button() == Qt.LeftButton
                and o.alive and o.active and compat.selecting(o.viewport)):
            doc = o.doc()
            p = event.position()
            if obj is o.viewport and o.picking_through():
                # through: what the click picked (not the face in front)
                sel = compat.selected_groups(o.viewport)
                cands = [] if sel else o.pick_candidates(p.x(), p.y())
                hit = sel[0] if sel else (cands[0] if cands else None)
            else:
                # (the view double-clicked: several views, each its camera)
                hit = compat.group_at(obj, p.x(), p.y())
            if hit is not None and compat.kind_of(hit) \
                    and compat.locked(o.viewport, hit):
                o.locked_note()                     # IngeTrazo 0.6.0's lock
                return True
            wall = o.wall_of(hit) if hit is not None else None
            if wall is not None:                    # a wall: its window
                self._batch_back(wall)
                QTimer.singleShot(0, lambda: o.keep_strip(
                    lambda: o.edit_wall(wall)))
                return True
            el = o.element_of(hit) if hit is not None else None
            if el is not None:                      # column, beam, slab…
                self._batch_back(el)
                QTimer.singleShot(0, lambda: o.keep_strip(
                    lambda: o.edit_element(el)))
                return True
            op = o.opening_of(hit) if hit is not None else None
            if op is not None:                      # a door, a window
                self._batch_back(op)
                QTimer.singleShot(0, lambda: o.keep_strip(
                    lambda: o.edit_opening(op)))
                return True
            if o.has_plot(doc):
                g = hit
                if g is not None and g is compat.find_plot(
                        o.viewport, doc["plot"]["uid"]):
                    QTimer.singleShot(0, o.open_plot_window)
                    return True
                dig = o.dig_of(g) if g is not None else None
                if dig is not None:                 # an excavation
                    QTimer.singleShot(0, lambda: o.edit_dig(dig))
                    return True
        return False


def _project_first(fn):
    """A tool that MAKES something: on a file with no Project, the Project
    dialog comes first (see ``ArchXQ._project_or_ask``); the tool comes out
    after it, on the levels just set."""
    @functools.wraps(fn)
    def run(self, *args, **kwargs):
        if not self._project_or_ask():
            return None
        return fn(self, *args, **kwargs)
    return run


class ArchXQ:
    # IngeTrazo 0.6.0 opens projects in tabs, each with its own viewport:
    # the host's app.viewport answers the tab in front, so it is read each
    # time (one kept from the start stays the first tab's)
    @property
    def viewport(self):
        return self.app.viewport

    def __init__(self, app, placement: str | None = None) -> None:
        # ONE interface: over the 3D view. The «own bars» placement was a
        # study of the prototype; switching could confuse or break (his
        # call, 2026-10-07) — it is no longer offered, and an old saved
        # choice is ignored
        placement = "viewport"
        self.placement = placement
        self.app = app
        # the host's LIGHT theme: ArchXQ's pieces kept dark and readable
        # (a customer's review, 2026-10-12) — the dark theme: untouched;
        # a switch while it runs is followed (style.install_theme_guard)
        from .style import install_theme_guard
        install_theme_guard()
        self._loader_key = compat.own_key(app)   # data always under "archxq"
        self.window = app.window
        # the 3D view ArchXQ's pieces and key / mouse watchers live on — it
        # follows the project tab in front (_follow_tab); each tab's own
        # session state (phase, level, plan view…) is kept apart
        self._home = app.viewport
        # what ArchXQ's pieces are children of: that view, or — with several
        # views — the host's grid, the views inside and ArchXQ around them
        # (viewframe.py, 09/11/2026)
        self._ui_parent = app.viewport
        self._framed = False
        self._framed_levels = False      # the levels strip open, framed
        self._frame_left = 0             # the room at the left, framed
        self._frame_busy = False
        self._extras_of = None           # the grid whose extra views we watch
        self._tab_state: dict = {}
        _docs = _pro_module("docs")
        # the sheets' drawings from the WHOLE model (the host's fast path
        # held a part of it — see docs.full_geometry); the Lite makes none
        if _docs is not None:
            _docs.full_geometry(self.viewport, True)
        self.alive = True
        self.active = False
        self.presenting = False    # «Present»: every piece hidden for a while
        self.method: str | None = None
        self.plot_preview = None   # (corners, heights, closing, row) — table
        self.terrain_current = False   # working on the Terrain, not a level
        self.setback_preview = None    # (plot, active side) — Setbacks window
        self.dig_preview = None        # (corners, ground, row) — Excavation
        self._syncing = False
        # PLAN VIEW: where you edit. ``_plan_back`` = the 3D camera to go
        # back to; orbiting out of the top view leaves the plan by itself
        self.hidden_parts: set = set()     # «Show» chips switched off
        self.plan_on = False
        self._plan_back = None
        self._plan_cam = None        # the plan's own pan / zoom, kept
        self._plan_leaving = False
        # an ELEVATION shown («front» / «right» / «back» / «left»): parallel,
        # level, squared with the building; each keeps its own pan / zoom
        self.side_view = None
        self._side_cams: dict = {}
        self.xray = False            # the plan / elevations see-through
        self._side_hid_terrain = False   # an elevation hid it: put it back
        self._pick = None            # the pick-through's last click (cycle)

        # RIGHT — a tab of the side tray: the outliner above, the picked
        # element's properties below (Blender's arrangement); the divider
        # is dragged and remembered
        # …and ON TOP, the LIBRARY of the element being drawn / picked —
        # the main piece of the strip (his call, 2026-10-08: the outliner
        # is little used), in a scroll: it will grow
        from PySide6.QtWidgets import QFrame, QScrollArea, QSplitter
        from .library import LibraryPanel
        from .outliner import Outliner
        self.props = PropsPanel(self)
        self.props.library = LibraryPanel(self.library_pick,
                                          self.library_live,
                                          self.library_fit)
        self.props.library.dyn = self.library_dyn
        # YOUR wall types' cards (0.15.0)
        # (one with layers hidden in the 3D: «_hidden» — its card says so)
        self.props.library.your_types = lambda key="wall": (
            self._profile_types() if key == "profile"
            else [dict(t, _hidden=True)
                  if t.get("id") in (self.doc().get("hidden_layers") or {})
                  else t for t in self.doc().get(f"{key}_types") or []])
        self._live_meshes: dict = {}     # groups reshaped while dragging
        self._live_ctx: dict = {}        # a bar's drag: its level's joins
        self._lib_box = QScrollArea()
        self._lib_box.setWidgetResizable(True)
        self._lib_box.setFrameShape(QFrame.NoFrame)
        self._lib_box.setWidget(self.props.library)
        self._lib_box.hide()
        from . import style as _style
        _style.EXTRA.append(self._lib_dark)    # the host turned light later
        self._lib_dark()
        self.outliner = Outliner(self)
        self._split = QSplitter(Qt.Vertical)
        self._split.setChildrenCollapsible(False)
        self._split.addWidget(self._lib_box)
        self._split.addWidget(self.outliner)
        self._split.addWidget(self.props)
        sizes = QSettings().value("archxq/dock_split")
        try:
            self._split.setSizes([int(s) for s in sizes])
        except (TypeError, ValueError):
            self._split.setSizes([380, 200, 240])
        self._split.splitterMoved.connect(lambda *_: QSettings().setValue(
            "archxq/dock_split", self._split.sizes()))
        self._dock = app.add_panel("ArchXQ", self._split)
        self._dock_floatable()
        self._outline_sig = None
        self._last_pick = frozenset()     # the selection last seen
        self._outline_timer = QTimer()
        self._outline_timer.setSingleShot(True)
        self._outline_timer.timeout.connect(self._sync_outliner)
        self.viewport.sceneVersionChanged.connect(self._outline_soon)

        # TOP — the hub
        self.hub = Hub(self, placement)
        self.hub.bar = compat.place(self.viewport, self.hub, placement,
                                    "top", BAR_CSS)
        if self.hub.bar is not None:
            self.hub.sub.setParent(self.window)
            self.hub.sub.hide()
            self.window.installEventFilter(self.hub)
            self.hub.bar.installEventFilter(self.hub)

        # LEFT — the plan view switch on its own, and under it the drawing
        # methods (one column); BOTTOM — view controls
        from .panels import PlanSwitch, ViewsStrip
        self.plan_btn = PlanSwitch(self)
        self.plan_bar = compat.place(self.viewport, self.plan_btn, placement,
                                     "left", BAR_CSS)
        # under it, while it is on: the plan and the four elevations (his
        # idea, 2026-10-10)
        self.views = ViewsStrip(self)
        self.views_bar = compat.place(self.viewport, self.views, placement,
                                      "left", BAR_CSS, new_line=False)
        self._show_piece(self.views, self.views_bar, False)
        self.strip = SideStrip(self)
        self.strip_bar = compat.place(self.viewport, self.strip, placement,
                                      "left", BAR_CSS, new_line=False)
        # under the methods, a section of its own: the «Building elements»
        # (ramps first — his call, 2026-10-05)
        self.elbox = ElementsBox(self)
        self.elbox_bar = compat.place(self.viewport, self.elbox, placement,
                                      "left", BAR_CSS, new_line=False)
        from . import ramps, stairs
        self.bramp_opts = dict(ramps.DEFAULT)    # the last ramp set up
        self.bstair_opts = dict(stairs.DEFAULT)  # …and stair
        self.viewbar = ViewBar(self)
        self.view_bar = compat.place(self.viewport, self.viewbar, placement,
                                     "bottom", BAR_CSS)
        # PRESENT, on its own left of the «Show» bar (his design, 2026-10-18
        # — Karl's client on a 120″ screen): every ArchXQ piece hidden
        from .panels import PresentButton
        self.present_btn = PresentButton(self)
        self.present_bar = compat.place(self.viewport, self.present_btn,
                                        placement, "bottom", BAR_CSS,
                                        new_line=False)
        self._present_esc = _PresentEsc(self)
        self.viewport.installEventFilter(self._present_esc)
        self.window.installEventFilter(self._present_esc)
        # Esc ends an ArchXQ tool even with something selected
        self._tool_esc = _ToolEsc(self.viewport)
        self.viewport.installEventFilter(self._tool_esc)
        self.window.installEventFilter(self._tool_esc)
        # Space + the mouse = pan, an ArchXQ tool still out (2026-10-19)
        self._space_pan = _SpacePan(self.viewport)
        self.viewport.installEventFilter(self._space_pan)
        self.window.installEventFilter(self._space_pan)
        # our windows, once closed, deleted when the next one shows
        self._reaper = _DialogReaper()
        self.window.installEventFilter(self._reaper)
        # the host's «Clean screen» hides its toolbars and menus — and with
        # them every shortcut on them (O = Orbit: his recording, 2026-10-19,
        # «only the wheel works»): while it is on, its actions are put on
        # the window itself, so their keys still work
        self._clean_keys_on = []
        self._clean_act = self._clean_screen_action()
        if self._clean_act is not None:
            self._clean_act.toggled.connect(self._clean_keys)
            if self._clean_act.isChecked():
                self._clean_keys(True)
        # UNDER THE PHASES — the options bar of a creation tool (hidden
        # until a tool that has options is out)
        from .optionsbar import OptionsBar
        self.optbar = OptionsBar(self)
        self.opt_bar = compat.place(self.viewport, self.optbar, placement,
                                    "top", BAR_CSS)
        self._show_piece(self.optbar, self.opt_bar, False)
        self.options_for = None           # the tool class the bar is for
        self.dig_opts = {"bottom": "depth", "d": 3.0, "offset": 0.30,
                         "z": -3.0, "segments": 24, "align": "axes",
                         "wall": 90.0}
        self.ramp_opts = {"width": 3.0, "slope": 20.0, "end": "auto",
                          "offset": 0.30, "z": -3.0}
        self.fill_opts = {"bottom": "height", "h": 1.0, "offset": 0.30,
                          "z": 0.0, "segments": 24, "align": "axes",
                          "wall": 45.0}
        # rectangles square with the red / green axes (as the plan's grid);
        # «Plot sides» on demand — square with the plot's longest side, it
        # looked twisted on a plot whose side leans a little (2026-10-02)
        self.creating = "cut"            # what a terrain tool is making
        # the wall's choices, made BEFORE drawing (and kept while drawing):
        # align = where it sits on the line drawn; height "level" = the
        # level's floor-to-floor, else ``h``
        self.wall_opts = {"shape": "chain", "align": "centre", "t": 0.15,
                          "height": "level", "h": 2.80,
                          # one of YOUR types for the next walls ("" none)
                          "wtype": "",
                          # a curtain wall (curtain.py): glass, mullions
                          # every cw_s, a band at each floor — and its own
                          # sizes and colours (curtain.DEFAULTS)
                          "cw": False}
        from . import curtain as _CW
        self.wall_opts.update(_CW.DEFAULTS)
        # the structure's choices, the same way
        self.col_opts = {"shape": "single", "section": "rect", "w": 0.30,
                         "d": 0.30, "angle": 0.0, "anchor": "centre",
                         "count": 4, "nx": 3, "ny": 3, "height": "level",
                         "h": 3.00, "fit": "fit", "base": 0.0,
                         "by": "count", "spacing": 5.0, "ends": "both",
                         "cbase": "none", "ccap": "none",
                         # how a row stands on its line, its beams (colrows)
                         "align": "auto",
                         "beams": {"top": {"on": False, "w": None, "h": 0.50},
                                   "foot": {"on": False, "w": None,
                                            "h": 0.40},
                                   "mid": {"on": False, "w": None,
                                           "h": 0.30}}}
        self._last_row = None     # the row last placed: the bar still edits it
        self.beam_opts = {"shape": "chain", "w": 0.20, "h": 0.45,
                          "fit": "fit", "insert": "centre",
                          # under the slab above, or its top at a height of
                          # its own (a lean-to's beams — Badis, 2026-10-18)
                          "zmode": "level", "zt": 2.50}
        self.slab_opts = {"shape": "walls", "t": 0.15, "offset": 0.0,
                          "hole_by": "rect",     # an opening: how drawn
                          # a CEILING (0.15.0): its underside over the floor
                          "ceiling": False, "ch": 2.60,
                          # a BLOCK (0.15.0): its bottom over the floor
                          "block": False, "base": 0.0,
                          # its LAYERS (slab layers): one of YOUR types, or
                          # a ready-made card's stack (None: plain) — and its
                          # joists (a «By market» card, PLANO_PISOS_BARROTES)
                          "stype": "", "layers": None, "frame": None}
        self.foot_opts = {"shape": "pads", "w": 1.20, "sw": 0.60, "d": 0.50,
                          # «Along a path» (colrows, PLANO D 07/11/2026): a
                          # row of footings with no columns — what, and how
                          # they stand along it (as a row of columns)
                          "ftype": "pads", "by": "spacing", "count": 4,
                          "spacing": 2.0, "ends": "both", "align": "centre",
                          # with a strip: the pads' own depth (deeper)
                          "pd": 0.80}
        # low walls & guards (guards.py — Pro): the next one drawn
        #: a room separator: how it is drawn (SEP_SHAPES)
        self.sep_opts = {"shape": "chain"}
        self.guard_opts = {"kind": "wall", "h": 1.10, "t": 0.15,
                           "wall_h": 0.40, "base": 0.0, "cap": False,
                           "on": "auto",
                           "rail_top": "steel", "rail_infill": "vertical",
                           "rail_fix": "frameless", "rail_profile": "round",
                           "rail_clear": 0.11,
                           "top": "stepped", "step_h": 0.15,
                           "insert": "centre", "how": "draw", "gap_w": 0.90,
                           "pier_s": 3.00,
                           # the next gate (guards.py, phase C)
                           "gate_kind": "swing", "gate_leaves": 1,
                           "gate_style": "bars", "gate_finish": "anthracite",
                           "gate_open": 0.0}
        # streets («Surroundings», streets.py — Pro): the next one made
        self.street_opts = {"how": "plot", "w": 7.00, "walk": 2.00,
                            "curb": 0.15, "sides": "both", "r": 5.00,
                            "line": False, "align": "centre"}
        # Tools ▸ Along a path ▸ Profile along (along.py — Pro): the next one
        from .profiles import DEFAULT_OPTS as _PF
        self.profile_opts = dict(_PF)
        # … and ▸ Copy along (copies.py — Pro): the next copies made
        from .profiles import COPY_DEFAULT as _CP
        self.copy_opts = dict(_CP)
        # glass grids (glazing.py — Pro): the next one placed (glazing's
        # DEFAULT, here: the Lite has no glazing.py)
        self.glazing_opts = {"kind": "industrial", "by": "size", "pw": 0.50,
                             "ph": 0.50, "fw": 0.03, "fd": 0.05, "mw": 0.025,
                             "md": 0.04, "frame": "black", "bead_c": "black",
                             "place": "void", "cols": 4, "rows": 4,
                             "foff": 0.0, "gpos": -1.0, "gt": 0.008,
                             "glass": "clear", "glass_tr": 0.70,
                             "opaque": False, "bead": True, "bw": 0.012,
                             "bt": 0.010, "h": 2.10, "base": 0.0,
                             "outside": "right", "fr_on": True}
        # the documentation (paper / scale: the project's, to start)
        self.doc_opts = {"paper": None, "scale": "auto", "cut": 1.20,
                         "elev": "yes", "sect": "yes", "dims": "yes",
                         "rooms": "yes", "prefix": "A-"}
        self.room_labels = True          # names + areas in the plan view
        self.dxf_opts = {"tmin": 0.08, "tmax": 0.40}
        self.roof_opts = {"shape": "walls", "kind": "gable", "lplan": False,
                          "slope": 30.0,
                          "overhang": 0.50, "go": 0.50, "t": 0.20,
                          "ridge": "long", "parapet": 1.00, "pt": 0.15,
                          "fall": "right", "slopes": 2, "pauto": True,
                          "gutter": 0.30,
                          # on the walls, or its eaves at a height of their
                          # own (a lean-to — Badis, 2026-10-18)
                          "zmode": "walls", "zh": 2.50,
                          # its layers and rafters (a «By market» card —
                          # PLANO_TELHADO_CAMADAS 2c): none, a solid slab
                          "layers": None, "frame": None}
        # the openings' sizes, per kind (the usual ones to start) — and
        # their trim / stone sill (trim.py: none until picked)
        from .trim import DEFAULTS as TRIM_OPTS
        self.op_opts = {
            "door": {"shape": "wall", "w": 0.90, "h": 2.10, "sill": 0.0,
                     "swing": "left", "op": "swing", "leaves": 1,
                     "leaf": "solid", "open": 0.0, "out": False,
                     "top": "square",            # or «arched» (0.15.0)
                     # a shopfront's own (shopfront.py)
                     "shop_door": "double", "door_at": "centre", "dh": 2.20,
                     "base": 0.0, "transom": True, "panes": 0,
                     "shutter": False, "sign": False, "shop_in": False,
                     "glass": "clear",
                     # a garage door's kind, finish, windows (2026-10-18)
                     "garage": "sectional", "gfinish": "steel",
                     "gwin": False,
                     # a NEW door's handle and colours (openfinish.py,
                     # 2026-10-27 — an old one keeps none)
                     "handle": "lever", "hw_c": "silver", "leaf_c": "wood",
                     "frame_c": "white", "top_h": 0.0, **TRIM_OPTS},
            "window": {"shape": "wall", "w": 1.20, "h": 1.20, "sill": 1.00,
                       # «fixed» | «shop» (a shop window — shopfront.py) |
                       # «sliding» | «casement» | «awning» (PLANO_JANELAS)
                       "op": "fixed", "leaves": 2, "swing": "left",
                       "out": False, "open": 0.0, "dh": 2.20, "base": 0.0,
                       "transom": True, "panes": 0, "shutter": False,
                       "sign": False, "glass": "clear",
                       # «pivot» too, louvres, colours (openfinish.py)
                       "louvred": False, "pv_panes": 0, "handle": "lever",
                       "hw_c": "silver", "frame_c": "white",
                       # its SHAPE (shapes.py, 2026-10-31 — «shape» above is
                       # how it is drawn)
                       "oshape": "rect", "rise": 0.30, "top_w": 0.60,
                       # bars, a top light, a leaf's width (04/11/2026)
                       "bars_x": 0, "bars_z": 0, "top_h": 0.0,
                       **{f"lw{i}": 0.0 for i in range(1, 7)},
                       **TRIM_OPTS},
            "void": {"shape": "wall", "w": 1.00, "h": 2.10, "sill": 0.0,
                     **TRIM_OPTS}}
        # the LAST choice of each element, from the session before (his
        # call, 2026-10-28: «it stays what was picked until changed»)
        from PySide6.QtWidgets import QApplication
        self._opts_kept = None
        self._recall_opts()
        QApplication.instance().aboutToQuit.connect(self._remember_opts)

        # RIGHT (over the 3D view / own bar) — the levels strip, N
        self.levels_open = str(QSettings().value("archxq/levels_open",
                                                 "1")) != "0"
        self.levels = LevelStrip(self)
        self.levels_bar = compat.place(self.viewport, self.levels, placement,
                                       "right", BAR_CSS)
        # the strip hidden: a tab on the right edge brings it back (his
        # ask, 2026-10-23 — a customer hid it with N and was lost)
        from .panels import LevelsTab
        self.levels_tab = LevelsTab(self)
        self.levels_tab_bar = compat.place(self.viewport, self.levels_tab,
                                           placement, "right", BAR_CSS,
                                           new_line=False)
        self._show_piece(self.levels_tab, self.levels_tab_bar, False)
        # a bar wider than the room: the wheel over it scrolls it
        self._hub_scroll = viewframe.BarScroll(self.hub, self.viewport,
                                               self.layout_floating)
        self._viewbar_scroll = viewframe.BarScroll(self.viewbar, self.viewport,
                                                   self.layout_floating)
        self._nkey = _LevelsKey(self)
        self.viewport.installEventFilter(self._nkey)
        # over ArchXQ's pieces the pointer is an arrow — not the drawing
        # tool's pencil the 3D view wears (they are its children)
        self._cursor = _ToolCursorBack(self.viewport)
        # (the Building elements box too — the pencil stayed over it, his
        # note 2026-10-16)
        for w in (self.hub, self.hub.sub, self.plan_btn, self.views,
                  self.strip, self.viewbar, self.levels, self.optbar,
                  self.elbox, self.present_btn, self.levels_tab):
            w.setCursor(Qt.ArrowCursor)
            w.installEventFilter(self._cursor)

        # the viewport's right-click menu: ArchXQ ▸ on ArchXQ's objects
        compat.add_context_menu(app, self._context_menu)

        # the host's Extensions menu: ArchXQ ▸ (also found by F3)
        self.menu, self.menu_acts = compat.add_ext_menu(app, "ArchXQ", [
            ("ArchXQ environment", lambda: self.hub.power.toggle(),
             "Enter / leave the ArchXQ environment — the model is not "
             "changed", False),
            ("Levels strip\tN", self.toggle_levels_strip,
             "Show / hide the levels strip on the right (N)",
             self.levels_open),
            None,
            ("Settings…", self.open_settings,
             "ArchXQ preferences: what is shown while you work, default "
             "sizes", None),
        ] + ([("Build the demo project", self.build_demo,
               "A new document with the demonstration building (4 storeys "
               "and a basement), saved as ArchXQ_Demo.igz", None)]
             if _pro_module("demo") is not None else []))   # not in Lite
        self._watch = _Watch(self.layout_floating)
        self.viewport.installEventFilter(self._watch)
        self._keys = _KeyClaim(self.viewport)
        self.viewport.installEventFilter(self._keys)
        self._hover_off = _HoverOff(self.viewport)
        self.viewport.installEventFilter(self._hover_off)
        self._dbl = _PlotDoubleClick(self)
        self.viewport.installEventFilter(self._dbl)
        # the RADIAL MENU at the mouse (his ask; ArchiCAD's Pet Palette)
        from .radial import RadialMenu
        self.radial = RadialMenu(self.viewport, self)
        self._radial_watch = _RadialClick(self)
        self.viewport.installEventFilter(self._radial_watch)
        from PySide6.QtGui import QKeySequence, QShortcut
        # F9, not Alt+R: NVIDIA's and AMD's overlays take Alt+R before
        # IngeTrazo ever sees it (his PC, 2026-10-10)
        self._radial_key = QShortcut(QKeySequence("F9"), self.window)
        self._radial_key.activated.connect(self.toggle_radial)
        # the QUICK HELP card (quickhelp.py) — F1 (H is IngeTrazo's Pan)
        from .quickhelp import QuickHelp
        self.quick = QuickHelp(self)
        self.quick.card.installEventFilter(self._cursor)   # pencil back
        self._quick_key = QShortcut(QKeySequence("F1"), self.window)
        self._quick_key.activated.connect(self.quick.toggle)
        # the elevations' / X-ray plan's click: through to what lies behind
        # (installed after: it sees the click first)
        self._pickthru = _PickThrough(self)
        self.viewport.installEventFilter(self._pickthru)
        # the on-screen GRIPS of the one element selected (grips.py) —
        # installed last: a press on a grip is theirs, any other the host's
        from .grips import GripControl
        self._grip_read = self._reader(lambda d: d)
        # section lines picked in the plan (BEFORE the grips: a press on a
        # grip is theirs)
        self._marks_off = None       # (scene, marks were shown, its cut)
        self._cut3d = None           # (scene, our plane, cut before, marks)
        self._sec_picked = None
        self._sec_live = None
        self._sec_cache = (None, [])
        self._sec_filter = _SectionPick(self)
        self.viewport.installEventFilter(self._sec_filter)
        self._grips = GripControl(self)
        self.viewport.installEventFilter(self._grips)
        # an Opening's HOLE clicked (PLANO_PEGAS_VAOS.md): the host's own
        # pickables — Esc, a click elsewhere, Supr are its
        self._void_picked = None
        self._void_quiet = False
        compat.add_pickable(self.app, self.viewport, self._void_pick_at,
                            self._void_selected, self._void_delete)

        app.on_document_changed(self._on_doc_changed)
        if hasattr(app, "on_document_closed"):         # IngeTrazo 0.6.0
            app.on_document_closed(self._on_doc_closed)
        # the host's Move / Rotate / Copy on ArchXQ's elements: adopted
        compat.watch_commands(self._after_command, self._before_command)
        self._adopting = False
        self._stamp_old()
        app.add_overlay(self._overlay)
        doc = self.doc()
        self.current = next_open(self._done(doc), doc["system"])
        self.element = PHASES[self.current].elements[0]
        self.floor = self._ground_index(doc)
        active = str(QSettings().value("archxq/active", "1")) != "0"
        self.hub.power.setChecked(active)
        self.set_active(active)
        # the host restores its window layout after the extensions load —
        # once it came back with ArchXQ's tray tab closed (his screen,
        # 2026-10-06): put it back beside Properties
        QTimer.singleShot(2500, self._ensure_dock)
        # UPDATE WITH ONE CLICK (updater.py): «updated ✓», and the Pro's
        # daily look at xq.com.br — in a thread, a few seconds after start
        from . import updater
        updater.start(self)

    def keep_strip(self, open_window) -> None:
        """An element's window opened by a double-click: when it closes,
        ArchXQ's strip is in front again (his recording, 2026-10-14: after
        a curtain wall's window the host's Properties tab had come over it
        — the host's own reaction to the double-click; ours was never
        asked)."""
        try:
            open_window()
        finally:
            def back():
                if self.alive and self.active and self._dock is not None \
                        and self._dock.isVisible():
                    self._dock.raise_()
            QTimer.singleShot(0, back)
            QTimer.singleShot(250, back)    # the host's, if it comes late

    def _ensure_dock(self) -> None:
        from PySide6.QtWidgets import QDockWidget
        if not (self.alive and self.active and self._dock is not None) \
                or self._dock.isVisible():
            return
        props = self.window.findChild(QDockWidget, "tray_properties")
        if props is not None and props is not self._dock:
            self.window.tabifyDockWidget(props, self._dock)
        self._dock.show()
        self._dock.raise_()

    # ---- The sovereign switch ------------------------------------------------
    def set_active(self, on: bool) -> None:
        if not self.alive:
            return
        if self.presenting:               # (the switch wins: presenting ends)
            self._end_present(refresh=False)
        self.active = bool(on)
        QSettings().setValue("archxq/active", "1" if on else "0")
        if self._dock is not None:
            self._dock.setVisible(self.active)
            if self.active:
                self._dock.raise_()
            else:
                compat.show_host_properties(self.window)
        self.hub.set_on(self.active)
        self._menu_check("ArchXQ environment", self.active)
        if self.active:
            # (the Levels box: refresh never shows it — off and on again it
            # stayed away, found 2026-10-18)
            self._show_piece(self.levels, self.levels_bar, self._levels_on())
            self.refresh()
        else:
            self._show_piece(self.plan_btn, self.plan_bar, False)
            self._show_piece(self.views, self.views_bar, False)
            self._show_piece(self.strip, self.strip_bar, False)
            self._show_piece(self.elbox, self.elbox_bar, False)
            self._show_piece(self.viewbar, self.view_bar, False)
            self._show_piece(self.levels, self.levels_bar, False)
            self._show_piece(self.present_btn, self.present_bar, False)
            self.hide_options()
            self._host_marks_sync()          # the host's marks back
        self.layout_floating()               # (several views: the frame on/off)
        self.viewport.update()

    # ---- Present (his design, 2026-10-18) ------------------------------------------
    # ---- the ArchXQ panel, detachable (Karl's ask, 2026-10-19) ----------------------
    def _dock_floatable(self) -> None:
        """Our side panel (library · outliner · properties) can be pulled
        out of the tray — its tab dragged away, or its title double-clicked
        — onto another screen (Karl's second 4K monitor); where it was is
        remembered and it comes back there. Docked by default; the host's
        own panels stay as the host keeps them."""
        from PySide6.QtWidgets import QDockWidget
        d = self._dock
        if not isinstance(d, QDockWidget):
            return
        # (the host lays its trays out after us and takes «floatable» off
        # again: set now, once it is done, and at every refresh)
        self._ensure_floatable()
        QTimer.singleShot(0, self._ensure_floatable)
        QTimer.singleShot(1500, self._ensure_floatable)
        s = QSettings()
        if s.value("archxq/dock_floating", "0") == "1":
            geo = s.value("archxq/dock_geometry")
            QTimer.singleShot(0, lambda: self._dock_float_back(geo))
        d.topLevelChanged.connect(self._dock_floated)

    def _ensure_floatable(self) -> None:
        from PySide6.QtWidgets import QDockWidget
        d = self._dock
        try:
            if isinstance(d, QDockWidget) and not (
                    d.features() & QDockWidget.DockWidgetFloatable):
                d.setFeatures(d.features() | QDockWidget.DockWidgetFloatable)
        except RuntimeError:              # (gone with the host's window)
            pass

    def _dock_float_back(self, geo) -> None:
        d = self._dock
        if d is None or not self.alive:
            return
        d.setFloating(True)
        if geo is not None:
            try:
                d.restoreGeometry(geo)
            except Exception:  # noqa: BLE001 — a screen gone: where Qt puts it
                pass
        # (a screen unplugged since: back onto one that is there)
        from PySide6.QtGui import QGuiApplication
        if QGuiApplication.screenAt(d.geometry().center()) is None:
            d.move(self.window.geometry().center() - d.rect().center())

    def _dock_floated(self, floating: bool) -> None:
        s = QSettings()
        s.setValue("archxq/dock_floating", "1" if floating else "0")
        if floating and self._dock is not None:
            s.setValue("archxq/dock_geometry", self._dock.saveGeometry())
            if not getattr(self, "_dock_geo_watch", None):
                self._dock_geo_watch = _GeoWatch(self._dock)
                self._dock.installEventFilter(self._dock_geo_watch)

    def toggle_present(self) -> None:
        if self.presenting:
            self._end_present()
        else:
            self._start_present()

    def _start_present(self) -> None:
        """Every ArchXQ piece away — phases, plan switch, methods, Building
        elements, options, Levels, Show bar, the right tray's tab, the
        quick help; the drawings over the view stop (``active`` off for the
        while, NOT remembered as the switch's state). Only the Present
        button stays, faint."""
        if not (self.alive and self.active):
            return
        self.presenting = True
        self.active = False
        self._host_marks_sync()
        for widget, bar in ((self.plan_btn, self.plan_bar),
                            (self.views, self.views_bar),
                            (self.strip, self.strip_bar),
                            (self.elbox, self.elbox_bar),
                            (self.viewbar, self.view_bar),
                            (self.levels, self.levels_bar),
                            (self.hub, self.hub.bar)):
            self._show_piece(widget, bar, False)
        self.hub.sub.hide()
        self.hide_options()
        if self._dock is not None:
            self._dock.setVisible(False)
        for extra in ("quick", "radial"):
            try:
                getattr(self, extra).hide()
            except Exception:  # noqa: BLE001 — never in the way
                pass
        from .updater import Notice
        for n in self.viewport.findChildren(Notice):
            n.hide()
        # the host's «Clean screen» (Ctrl+0) too — its own panels away, only
        # the view (his find, 2026-10-18); put back on the way out only if
        # we turned it on
        self._present_clean = None
        act = self._clean_screen_action()
        if act is not None and not act.isChecked():
            act.trigger()
            self._present_clean = act
        if act is not None:
            # the host's own «Exit clean screen» (or Ctrl+0) ends the
            # presenting too — ArchXQ stayed hidden behind it
            act.toggled.connect(self._clean_screen_off)
            self._present_watch = act
        self.present_btn.set_on(True)
        # started by the host's own Ctrl+0: not even our faint button — its
        # «Exit clean screen» is there (Karl's ask, 2026-10-19: «100 %
        # distraction-free with one click»)
        if getattr(self, "_present_by_host", False):
            self._show_piece(self.present_btn, self.present_bar, False)
        self.layout_floating()
        self.viewport.update()

    def _clean_keys(self, on: bool) -> None:
        """Clean screen on: the host's actions with a shortcut (on its now
        hidden toolbars / menus) also on the window, their keys alive; off:
        taken back off it (only the ones put there)."""
        from PySide6.QtGui import QAction
        w = self.window
        try:
            for a in self._clean_keys_on:
                w.removeAction(a)
        except RuntimeError:
            pass
        self._clean_keys_on = []
        if not on:
            return
        have = set(map(id, w.actions()))
        for a in w.findChildren(QAction):
            if a.shortcuts() and id(a) not in have and a.isEnabled():
                w.addAction(a)
                self._clean_keys_on.append(a)
        # the host's clean screen turned on BY HAND (Ctrl+0, its menu):
        # ArchXQ goes too — presenting, with no button of its own (Karl,
        # 2026-10-19); ended by the host's «Exit clean screen»
        if not self.presenting and self.alive and self.active:
            self._present_by_host = True
            try:
                self._start_present()
            finally:
                self._present_by_host = False
            # (left by Esc: the clean screen goes off with it, as it came)
            if self.presenting:
                self._present_clean = self._clean_act

    def _clean_screen_off(self, on: bool) -> None:
        """The host's clean screen switched off while presenting (its
        «Exit clean screen», Ctrl+0): the presenting ends with it."""
        if not on and self.presenting:
            self._present_clean = None     # (already off: leave it)
            QTimer.singleShot(0, self._end_present)

    def _clean_screen_action(self):
        """The host's «Clean screen» (by its shortcut Ctrl+0 — the menu's
        words change with the host's language). None: not found."""
        from PySide6.QtGui import QAction, QKeySequence
        want = QKeySequence("Ctrl+0")
        for a in self.window.findChildren(QAction):
            if a.isCheckable() and any(k == want for k in a.shortcuts()):
                return a
        return None

    def _end_present(self, refresh: bool = True) -> None:
        """Everything back as it was (a click on the faint button, or
        Esc)."""
        if not self.presenting:
            return
        self.presenting = False
        self.active = True
        watched = getattr(self, "_present_watch", None)
        self._present_watch = None
        if watched is not None:
            try:
                watched.toggled.disconnect(self._clean_screen_off)
            except (RuntimeError, TypeError):
                pass
        act = getattr(self, "_present_clean", None)
        self._present_clean = None
        if act is not None:
            try:
                if act.isChecked():
                    act.trigger()          # the host's panels back
            except RuntimeError:           # (gone with the host's window)
                pass
        self.present_btn.set_on(False)
        self._show_piece(self.hub, self.hub.bar, True)
        # (the Levels box is shown by its N switch only — refresh leaves it)
        self._show_piece(self.levels, self.levels_bar, self._levels_on())
        if self._dock is not None:
            self._dock.setVisible(True)
            self._dock.raise_()
        if refresh:
            self.refresh()
        self.viewport.update()

    def set_placement(self, placement: str) -> None:
        """Move every piece (one content, two placements): remembered,
        then rebuilt."""
        QSettings().setValue("archxq/placement", placement)
        from . import reload
        window = self.window
        QTimer.singleShot(0, lambda: reload(window))

    # ---- Document ----------------------------------------------------------------
    def doc(self) -> dict:
        # while ArchXQ paints over the view, the document is read ONCE per
        # frame (his recording, 2026-10-19: orbiting stuttered — a frame
        # read it 8 times, ~3 ms each on his building); a top-level copy,
        # so a drawing that sets a key does not change the next one's
        paint = getattr(self, "_paint_doc", None)
        if paint is not None:
            return dict(paint)
        compat.adopt_data(self.app, self._loader_key)
        doc = model.load(self.app.document_data(None))
        # an excavation / fill whose group was deleted (the Delete key) is
        # gone: it must not come back at the next terrain rebuild (his
        # test, 2026-10-03). One waiting to fit (no group yet: uid "") stays.
        if doc.get("digs"):
            try:
                have = self.viewport.scene.groups_by_uid()
                doc["digs"] = [d for d in doc["digs"]
                               if not d.get("uid") or d["uid"] in have]
            except Exception:  # noqa: BLE001 — keep them all
                pass
        return doc

    def save(self, doc: dict) -> None:
        self.app.set_document_data(doc)     # one undo step, marks unsaved

    def has_plot(self, doc: dict) -> bool:
        """A plot exists: corners stored AND its group still in the model
        (deleted from outside ArchXQ = no plot)."""
        plot = doc.get("plot")
        return bool(plot) and compat.find_plot(
            self.viewport, plot.get("uid", "")) is not None

    def _done(self, doc: dict) -> set[str]:
        """The phases with their ✔ — each checks ITSELF (his call,
        2026-10-09: the stand-in «Mark phase complete» button is gone): a
        project, a plot, structural elements (the automatic slabs of an
        excavation do not count), walls, openings, a roof, sheets. They
        guide, they never lock."""
        has = set()
        if model.has_project(doc):
            has.add("project")
        if self.has_plot(doc):
            has.add("terrain")
        own = [e for e in doc.get("structure") or [] if not e.get("auto")]
        if any(e["type"] in ("column", "beam", "slab", "footing")
               for e in own):
            has.add("structure")
        if doc.get("walls"):
            has.add("walls")
        if doc.get("openings"):
            has.add("openings")
        if any(e["type"] == "roof" for e in own):
            has.add("roof")
        if getattr(self.viewport.scene, "compositions", None):
            has.add("documentation")
        return {k for k in order(doc["system"]) if k in has}

    @staticmethod
    def _ground_index(doc: dict) -> int:
        return next(i for i, r in enumerate(doc["levels"])
                    if r["kind"] == "ground")

    # ---- Phases & elements -----------------------------------------------------
    def _blocked(self, key: str) -> bool:
        doc = self.doc()
        done = self._done(doc)
        if reachable(key, done, doc["system"]):
            return False
        prev = [k for k in order(doc["system"]) if k not in done][0]
        compat.flash(self.viewport, f"Finish «{PHASES[prev].label}» first")
        return True

    def _drop_tool(self) -> None:
        """A phase / element picked: ArchXQ's tool still out goes (back to
        Select) — its library held the right strip while the top bar said
        another (his screen, 2026-11-03: Tools › Along a path, then
        Openings: the Profiles library stayed)."""
        if compat.ours(getattr(self.viewport, "active_tool", None)):
            compat.back_to_select(self.viewport)

    def go(self, key: str) -> None:
        # a Tool on (Tools ▾ keeps the phase): a click on any phase — its
        # own too — leaves it for that phase's first element
        if self.element in TOOLS.elements and not self._blocked(key):
            self._drop_tool()
            if key == self.current:
                self.element = PHASES[key].elements[0]
                self.method = None
                self._sel_at_phase = set(self._lib_picked()[1])
                self.refresh()
                if key != "project":
                    return
        elif key != self.current and not self._blocked(key):
            self._drop_tool()
        # the top bar's «Project» opens its window straight away (his ask,
        # 2026-10-08: as the tutorial shows — not a second click on the
        # right) — also when Project is already the phase on
        if key == "project" and not self._blocked(key):
            if key != self.current:
                self.current = key
                self.element = PHASES[key].elements[0]
                self.method = None
                self.refresh()
            QTimer.singleShot(0, lambda: self.edit_project("project"))
            return
        if key == self.current or self._blocked(key):
            return
        self.current = key
        self.element = PHASES[key].elements[0]
        self.method = None
        self._sel_at_phase = set(self._lib_picked()[1])
        self._row_for_phase(key)          # Terrain ↔ its level (07/11)
        self.refresh()
        if self._dock is not None:
            self._dock.raise_()

    def pick(self, phase: str, element: str) -> None:
        # the Project button's menu ACTS (his call, 07/11/2026): «New
        # project» starts one (in a new tab when this one has a project),
        # «Edit project» opens its window
        if element == "new_project":
            QTimer.singleShot(0, self.new_project)
            return
        if element == "project_settings":
            if phase != self.current and not self._blocked(phase):
                self.current = phase
                self.element = element
                self.method = None
                self.refresh()
            QTimer.singleShot(0, lambda: self.edit_project("project"))
            return
        # the Documentation's two entries ACT (the studio is its own
        # window); the phase is entered, nothing is drawn
        if element in ("studio", "update_all"):
            if phase != self.current and not self._blocked(phase):
                self.current = phase
                self.element = element
                self.method = None
                self.refresh()
            if not self._pro_only(element):
                QTimer.singleShot(0, lambda e=element: self.doc_studio(e))
            return
        if phase != self.current:
            if self._blocked(phase):
                return
            self.current = phase
            self._row_for_phase(phase)    # Terrain ↔ its level (07/11)
        if element != self.element:
            self._drop_tool()             # another element: its tool goes
        self.element = element
        self.method = None
        self._sel_at_phase = set(self._lib_picked()[1])
        if element == "excavation":
            self._to_dig_row()            # its level, at once (07/11)
        self.refresh()
        if self._dock is not None:
            self._dock.raise_()

    def pick_tool(self, element: str) -> None:
        """«Tools ▾» ▸ a tool (his call, 2026-10-29): the phase you are on
        stays; its first method comes out at once."""
        if element not in TOOLS.elements:
            return
        self.element = element
        self.method = None
        self._sel_at_phase = set(self._lib_picked()[1])
        self.refresh()
        methods = ELEMENTS[element].methods
        if methods:
            self.on_method(methods[0].label)

    def on_method(self, name: str) -> None:
        # an excavation is its LEVEL's (his rule, 07/11/2026 — the level is
        # sovereign, PLANO_ESCAVACAO_NIVEL.md): its tool works on a basement
        # or the ground floor, never on the Terrain row
        if self.element == "excavation":
            self._to_dig_row()
        # every other Terrain tool draws on the Terrain row (his ask, 07/11:
        # a plot drawn on «Level 1» was hidden by that level's plan)
        elif self.element in PHASES["terrain"].elements \
                and self.element != "excavation_edit" \
                and not self.terrain_current:
            self._row_for_phase("terrain", now=True)
        # Tools ▸ Along a path: its tools (along.py)
        if self.element == "along" and name == "Profile along":
            self.start_profile()
            return
        if self.element == "along" and name == "Copy along":
            self.start_copy()
            return
        # Project phase: the "methods" are real actions
        if name == "Edit project…":
            self.edit_project("project")
        elif name == "Edit levels…":
            self.edit_current_level()
        elif name == "Add floor above":
            self._change_levels(model.add_floor)
        elif name == "Add basement":
            self._change_levels(model.add_basement)
        elif self.element == "plot" and name in PLOT_TOOLS:
            self.start_plot_tool(name)
            return
        elif self.element == "excavation" and name in DIG_TOOLS:
            self.start_dig_tool(name)
            return
        elif self.element == "fill" and name in DIG_TOOLS:
            self.start_dig_tool(name, kind="fill")
            return
        elif name == PLOT_TABLE:
            self.edit_plot_table()
        elif name == FOLD_LINE:
            self.start_fold_tool()
            return
        elif self.element == "survey" and name in SURVEY_TOOLS:
            self.start_survey_tool(name)
            return
        elif self.element == "survey" and name == SURVEY_TABLE:
            self.edit_survey()
        elif self.element == "wall_edit" and name == "Move points":
            self.start_wall_edit_tool()      # (before the plot's Move points)
            return
        elif self.element == "wall_edit" and name in ("Split",
                                                      "Trim / Extend"):
            self.start_wall_op_tool(name)    # (0.15.0, B1)
            return
        elif self.element == "wall_edit" and name == "Align":
            self.start_align_tool()          # (0.15.0, as Revit's)
            return
        elif self.element == "separator":
            self.start_separator_tool(name)  # (room separators, D5)
            return
        elif self.element == "slab_edit":
            self.start_slab_edit_tool(name)  # (before the plot's Move points)
            return
        elif name in EDIT_POINTS and self.element == "excavation_edit":
            self.start_dig_edit_tool(name)
            return
        elif name in EDIT_POINTS:
            self.start_edit_tool(name)
            return
        elif name == SETBACK_TOOL:
            self.start_setback_tool()
            return
        elif name == "Delete plot":
            QTimer.singleShot(0, self.delete_plot)
            return
        elif name == "Delete excavation":
            self.start_dig_erase_tool()
            return
        else:
            self.method = name
            compat.flash(self.viewport, f"ArchXQ prototype: drawing «{name}» "
                         "is not implemented yet")
            return
        self.method = None
        self.refresh()

    # ---- Terrain: the plot ----------------------------------------------------------
    @_project_first
    def start_plot_tool(self, name: str) -> None:
        from PySide6.QtWidgets import QMessageBox
        from . import plottools
        doc = self.doc()
        if self.has_plot(doc):
            ans = QMessageBox.question(
                self.window, "Replace the plot?",
                "There is already a plot. Drawing a new one replaces it "
                "(Ctrl+Z brings the old one back).",
                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
            if ans != QMessageBox.Yes:
                return
        cls = getattr(plottools, PLOT_TOOLS[name])
        self.method = name
        self._activate(cls(self._plot_done, self._plot_cancelled))
        self.strip.fill(self.element, self.method)
        compat.flash(self.viewport, "Draw the plot on the ground — Esc to "
                     "cancel", 5000)

    def _plot_done(self, corners) -> None:
        from . import plotgeo, prefs
        doc = self.doc()
        doc["done"] = [k for k in doc["done"] if k not in AUTO_PHASES]
        # a replaced plot keeps its ground; a first plot takes the default
        thick = (doc["plot"]["thickness"] if self.has_plot(doc)
                 else prefs.get("ground_thickness"))
        compat.commit_plot(self.viewport, self.app.key, doc, corners,
                           PLOT_Z, PLOT_COLOR, thick, fresh=True)
        self.method = None
        compat.back_to_select(self.viewport)
        compat.flash(self.viewport, "Plot drawn — "
                     f"{compat.fmt_area(plotgeo.area(corners), 1)}. The next "
                     "phases are open.", 6000)
        self.refresh()

    def set_ground_thickness(self, value: float) -> None:
        doc = self.doc()
        if not self.has_plot(doc):
            return
        value = round(min(max(float(value), 0.0), 20.0), 3)
        if abs(value - doc["plot"]["thickness"]) < 1e-6:
            return
        plot = doc["plot"]
        compat.commit_plot(self.viewport, self.app.key, doc, plot["corners"],
                           PLOT_Z, PLOT_COLOR, value, plot["heights"],
                           plot["closing"], plot["breaks"])
        compat.flash(self.viewport, f"Ground: {compat.fmt_len(value)} deep")
        self.refresh()

    # ---- Terrain: editing the plot by its sides ---------------------------------
    def edit_plot_table(self) -> None:
        """The plot table (modal): side lengths, corner angles and heights,
        the closing side. Apply = ONE undo step; while it is open the new
        outline is previewed over the model."""
        from .dialogs import PlotDialog
        doc = self.doc()
        if not self.has_plot(doc):
            compat.flash(self.viewport, "Draw the plot first")
            return
        self.hub.close_sub()
        dlg = PlotDialog(doc["plot"], self.window, self._preview_plot,
                         view=self._view_pair())
        self._mat_tab(dlg, "plot", "plot")
        try:
            ok = dlg.exec()
        finally:
            self._preview_plot(None)
        if not ok:
            return
        if getattr(dlg, "action", "apply") == "delete":
            QTimer.singleShot(0, self.delete_plot)      # it asks first
            return
        self._mat_take(dlg)
        corners, heights, closing = dlg.result_data()
        # read again: what changed while the window was open (its «Show on
        # the model» boxes write at once) must not be put back
        doc = self._with_mats(self.doc())
        compat.commit_plot(self.viewport, self.app.key, doc, corners,
                           PLOT_Z, PLOT_COLOR, doc["plot"]["thickness"],
                           heights, closing, doc["plot"]["breaks"])
        compat.flash(self.viewport, "Plot updated — Ctrl+Z undoes it", 5000)
        self.refresh()
        self._again(dlg, self.edit_plot_table)

    def _lib_dark(self) -> None:
        """The host LIGHT: the library's chips and cards are drawn for a
        dark ground; in its scroll box it stood on the host's white — its
        box darkened too (at start, and when the theme turns light)."""
        from .style import dark_island, host_light
        if not host_light():
            return
        for w in (self._lib_box, self._lib_box.viewport(),
                  self.props.library):
            dark_island(w, fill=True)
            w.setProperty("axq_dark", True)
        # on its dark ground the edges show: a margin, not glued to them
        self.props.library.layout().setContentsMargins(8, 4, 10, 8)

    # ---- Materials: the «Material» tab of the elements' windows ---------------------
    def _mat_tab(self, dlg, kind: str, el_id: str) -> None:
        """Give an element's window its «Material» tab (materials.py)."""
        from . import materials
        try:
            tab = materials.material_tab(kind, el_id, self.doc())
            if tab is not None:
                # Apply on the Material tab: committed at once, window open
                tab.on_apply = lambda ch, k=kind: self._apply_mat_now(ch, k)
                materials.with_tab(dlg, tab)
        except Exception:  # noqa: BLE001 — the window works without it
            import traceback
            traceback.print_exc()

    def _mat_take(self, dlg, action: str = "apply") -> None:
        """The window closed with OK / Apply: its material change goes into
        the SAME commit as the element's (one Ctrl+Z) — and, when nothing
        else commits, into one of its own right after."""
        tab = getattr(dlg, "_mat_tab", None)
        if tab is None or action in ("delete", "hide"):
            return
        ch = tab.change()
        if ch is None:
            return
        self._pending_mat = ch
        QTimer.singleShot(0, lambda k=ch["kind"]: self._flush_mat(k))

    def _apply_mat_now(self, ch: dict, kind: str) -> None:
        """A window's Material tab, Apply: the change stored and painted now
        (one Ctrl+Z), the window stays open."""
        self._pending_mat = ch
        self._flush_mat(kind)

    def _with_mats(self, doc: dict) -> dict:
        """``doc`` with the material change waiting, if any (taken)."""
        ch = getattr(self, "_pending_mat", None)
        if ch is None:
            return doc
        from . import materials
        self._pending_mat = None
        for one in ch if isinstance(ch, list) else [ch]:   # (in turn)
            doc = materials.merge(doc, one)
        return doc

    def _flush_mat(self, kind: str) -> None:
        if getattr(self, "_pending_mat", None) is None:
            return                         # the element's commit took it
        doc = self._live(self.doc())
        if kind in ("plot", "dig", "fill"):
            if self.has_plot(doc):
                self._commit_terrain(doc)
        else:
            self._commit_all(doc)
        compat.flash(self.viewport, "Material applied — Ctrl+Z undoes it",
                     4000)

    def _in_place(self, dlg, apply) -> None:
        """«Apply» on this window applies with it OPEN: ``apply(new)`` (what
        OK does after it) runs, its material change too, and the window
        stays in its place, on its tab (dialogs.ok_apply)."""
        def now() -> None:
            action, new = dlg.result_data()
            self._mat_take(dlg, action)
            apply(new)
            tab = getattr(dlg, "_mat_tab", None)
            if tab is not None:              # applied: no longer a change
                tab.start = dict(tab.now)
                tab.all.setChecked(False)
        dlg._apply_now = now

    def _again(self, dlg, reopen) -> None:
        """«Apply» (not OK) was pressed: the window comes back, in its place,
        with the values just applied (dialogs.ok_apply)."""
        if getattr(dlg, "again", False):
            QTimer.singleShot(0, reopen)

    # ---- Terrain: setbacks ------------------------------------------------------------
    def start_setback_tool(self) -> None:
        from .plotedit import SetbackTool
        if not self.has_plot(self.doc()):
            compat.flash(self.viewport, "Draw the plot first")
            return

        def get_plot():
            doc = self.doc()
            return doc["plot"] if self.has_plot(doc) else None

        self.method = SETBACK_TOOL
        self._activate(SetbackTool(
            get_plot, self.set_setbacks, self._plot_cancelled, PLOT_Z,
            dims=lambda: self.dims_on("setback_dims"),
            on_open=self.edit_setbacks))
        self.strip.fill(self.element, self.method)

    # ---- Terrain: survey points -----------------------------------------------------
    @_project_first
    def start_survey_tool(self, name: str) -> None:
        """Survey points › Add point / Delete point, on the model."""
        from .plotedit import SurveyTool
        from . import terrain
        doc = self.doc()
        if not self.has_plot(doc):
            compat.flash(self.viewport, "Draw the plot first")
            return
        mode = SURVEY_TOOLS[name]
        if mode == "delete" and not doc["plot"].get("survey"):
            compat.flash(self.viewport, "No survey points yet — add or "
                         "import some first", 4000)
            return

        def get_plot():
            d = self.doc()
            return d["plot"] if self.has_plot(d) else None

        def ground(p):
            plot = get_plot()
            return terrain.ground_at(plot, p) if plot else 0.0

        self.method = name
        self._activate(SurveyTool(
            mode, get_plot, ground, self.set_survey, self._plot_cancelled,
            PLOT_Z, on_open=self.edit_survey))
        self.strip.fill(self.element, self.method)

    def set_survey(self, points, step: float | None = None) -> None:
        """New survey points (and the contour step): the ground rebuilt
        through them — one Ctrl+Z."""
        doc = self.doc()
        if not self.has_plot(doc):
            return
        doc["plot"] = dict(doc["plot"], survey=[list(p) for p in points])
        if step is not None:
            doc["plot"]["contour"] = round(float(step), 3)
        self._commit_terrain(doc)
        self.refresh()

    def edit_survey(self) -> None:
        """The survey points' window (modal): the table, the import of a
        file; previewed on the model. Apply = one Ctrl+Z."""
        from .surveydlg import SurveyDialog
        doc = self.doc()
        if not self.has_plot(doc):
            compat.flash(self.viewport, "Draw the plot first")
            return
        self.hub.close_sub()
        dlg = SurveyDialog(doc, self.window, self._preview_survey,
                           view=self._view_pair())
        try:
            ok = dlg.exec()
        finally:
            self._preview_survey(None)
        if not ok:
            return
        points, step = dlg.result_data()
        plot = self.doc()["plot"]
        if points == (plot.get("survey") or []) and \
                abs(step - plot.get("contour", 0.5)) < 1e-6:
            self._again(dlg, self.edit_survey)
            return                                   # nothing changed
        self.set_survey(points, step)
        compat.flash(self.viewport, f"Survey points: {len(points)} — the "
                     "ground follows them · Ctrl+Z undoes it", 5000)
        self._again(dlg, self.edit_survey)

    def _preview_survey(self, preview) -> None:
        """(points, active row) drawn while the Survey window is open."""
        self.survey_preview = preview
        self.viewport.update()

    # ---- Terrain: excavations --------------------------------------------------------
    def _mod_opts(self, kind: str | None = None) -> dict:
        """The options of what is being made: an excavation or a fill."""
        kind = kind or getattr(self, "creating", "cut")
        return self.fill_opts if kind == "fill" else self.dig_opts

    def _dig_options(self, circle: bool, rect: bool = False,
                     kind: str = "cut") -> list[dict]:
        """The options bar of an excavation tool (where its bottom goes) —
        or of a fill tool (where its top goes)."""
        if kind == "fill":
            return self._fill_options(circle, rect)
        doc = self.doc()
        o = self.dig_opts
        # the ground floor too: a house without basement still digs for
        # its foundations — and the list always offers a real choice
        under = [r for r in reversed(doc["levels"])
                 if r["kind"] in ("ground", "basement")]
        choices = [("depth", "Depth below ground")] + \
            [(f"level:{r['id']}", f"Under {r['name']}") for r in under] + \
            [("elev", "At an elevation")]
        # the BEST by default (his rule, 2026-11-03): with basements, the pit
        # starts under the lowest one — tied to it, it follows its height;
        # without, 3 m below the ground. A bottom he picks himself is kept
        basements = [r for r in doc["levels"] if r["kind"] == "basement"]
        best = f"level:{basements[0]['id']}" if basements else "depth"
        if not o.get("bottom_picked") or \
                o["bottom"] not in [c[0] for c in choices]:
            o["bottom"] = best
        opts = []
        if rect:
            opts.append({"key": "align", "label": "Align", "kind": "choice",
                         "value": o["align"],
                         "choices": [("plot", "Plot sides"),
                                     ("axes", "Red / green axes")],
                         "tip": "Square with the plot's sides, or with the "
                                "model's axes"})
        opts.append({"key": "bottom", "label": "Excavation bottom",
                     "kind": "choice",
                     "value": o["bottom"], "choices": choices,
                     "tip": "Where the pit's floor goes: a depth under the "
                            "ground, under a level's floor (it follows the "
                            "level), or at a fixed elevation"})
        if o["bottom"] == "depth":
            opts.append({"key": "d", "label": "Depth", "kind": "len",
                         "value": o["d"], "min": 0.1, "max": 100.0,
                         "tip": "How deep, from the lowest ground around "
                                "the pit"})
        elif o["bottom"].startswith("level:"):
            opts.append({"key": "offset", "label": "below its floor",
                         "kind": "len", "value": o["offset"], "min": 0.0,
                         "max": 5.0, "tip": "Slab and fill under the "
                         "basement floor (usually 0.30)"})
        else:
            opts.append({"key": "z", "label": "Elevation", "kind": "len",
                         "value": o["z"], "min": -100.0, "max": 0.0,
                         "tip": "The pit's floor, from the ground floor "
                                "(±0.00)"})
        opts.append({"key": "wall", "label": "Walls", "kind": "len",
                     "value": o["wall"], "min": 5.0, "max": 90.0,
                     "step": 5.0, "suffix": "°",
                     "tip": "The pit's walls: 90° = vertical (a retaining "
                            "wall); less = a slope opening outward (45° is "
                            "a usual batter)"})
        if circle:
            opts.append({"key": "segments", "label": "Segments",
                         "kind": "int", "value": o["segments"], "min": 6,
                         "max": 96, "tip": "How many straight sides the "
                         "circle is made of"})
        return opts

    def _fill_options(self, circle: bool, rect: bool) -> list[dict]:
        """The options bar of a fill tool: where its top goes."""
        doc = self.doc()
        o = self.fill_opts
        at = [r for r in reversed(doc["levels"])
              if r["kind"] in ("ground", "basement")]
        choices = [("height", "Height above ground")] + \
            [(f"level:{r['id']}", f"Under {r['name']}") for r in at] + \
            [("elev", "At an elevation")]
        if o["bottom"] not in [c[0] for c in choices]:
            o["bottom"] = "height"
        opts = []
        if rect:
            opts.append({"key": "align", "label": "Align", "kind": "choice",
                         "value": o["align"],
                         "choices": [("plot", "Plot sides"),
                                     ("axes", "Red / green axes")],
                         "tip": "Square with the plot's sides, or with the "
                                "model's axes"})
        opts.append({"key": "bottom", "label": "Top", "kind": "choice",
                     "value": o["bottom"], "choices": choices,
                     "tip": "Where the fill's top goes: a height over the "
                            "ground, under a level's floor (a platform for "
                            "it — it follows the level), or an elevation"})
        if o["bottom"] == "height":
            opts.append({"key": "h", "label": "Height", "kind": "len",
                         "value": o["h"], "min": 0.05, "max": 50.0,
                         "tip": "How high, over the highest ground around "
                                "it"})
        elif o["bottom"].startswith("level:"):
            opts.append({"key": "offset", "label": "below its floor",
                         "kind": "len", "value": o["offset"], "min": 0.0,
                         "max": 5.0, "tip": "The slab the floor sits on "
                         "(the fill stops under it)"})
        else:
            opts.append({"key": "z", "label": "Elevation", "kind": "len",
                         "value": o["z"], "min": -50.0, "max": 50.0,
                         "tip": "The fill's top, from the ground floor "
                                "(±0.00)"})
        opts.append({"key": "wall", "label": "Edges", "kind": "len",
                     "value": o["wall"], "min": 5.0, "max": 90.0,
                     "step": 5.0, "suffix": "°",
                     "tip": "The fill's edges: a slope down to the ground "
                            "(45°, or gentler), or 90° = a retaining wall"})
        if circle:
            opts.append({"key": "segments", "label": "Segments",
                         "kind": "int", "value": o["segments"], "min": 6,
                         "max": 96})
        return opts

    @_project_first
    def start_dig_tool(self, name: str, kind: str = "cut") -> None:
        from . import plottools
        if not self.has_plot(self.doc()):
            # by the mouse, not only a line in the status bar (his ask,
            # 2026-11-03: it went unseen)
            self._say_at_cursor(tr("No plot yet — a fill is drawn inside "
                                   "it." if kind == "fill" else
                                   "No plot yet — an excavation is drawn "
                                   "inside it.") + "\n" +
                                tr("Draw the plot first: Terrain › Draw plot."))
            return
        cls = getattr(plottools, DIG_TOOLS[name])
        if name == "Ramp":
            self._start_ramp_tool(cls)
            return
        self.creating = kind
        noun = "Fill" if kind == "fill" else "Excavation"
        o = self._mod_opts(kind)
        tool = cls(self._dig_done, self._dig_cancelled)
        tool.noun = noun
        if name == "Circle":
            tool.segments = lambda: o["segments"]
        rect = name in ("Rectangle", "Rectangle from centre")
        if rect:
            tool.frame = self._plot_frame()
        self.method = name
        self._activate(tool)
        self.strip.fill(self.element, self.method)
        self.show_options(cls, noun,
                          lambda: self._dig_options(name == "Circle", rect,
                                                    kind),
                          self._on_dig_option)
        compat.flash(self.viewport, f"Draw the {noun.lower()} inside the "
                     "plot — Esc to cancel", 5000)

    # ---- Terrain: ramps -----------------------------------------------------------------
    @_project_first
    def _start_ramp_tool(self, cls) -> None:
        from . import terrain
        tool = cls(self._ramp_done, self._dig_cancelled)
        tool.noun = "Ramp"
        o = self.ramp_opts
        tool.width = lambda: o["width"]
        tool.slope = lambda: o["slope"]
        tool.start_z = lambda p: terrain.ground_at(self.doc()["plot"], p)
        tool.end_z = self._ramp_end
        self.method = "Ramp"
        self._activate(tool)
        self.strip.fill(self.element, self.method)
        self.show_options(cls, "Ramp", self._ramp_options,
                          self._on_ramp_option)
        compat.flash(self.viewport, "Click where the ramp starts — Esc to "
                     "cancel", 5000)

    def _ramp_end(self, p) -> float:
        """Where the ramp ends: the floor of the excavation it runs into
        («Meets an excavation»: the deepest one under its end; before the
        end is known, the deepest of all), a level, or an elevation."""
        from . import plotgeo, terrain
        o = self.ramp_opts
        doc = self.doc()
        if o["end"] == "auto":
            digs = terrain.opened(doc)
            if p is not None:
                under = [d for d in digs
                         if plotgeo.inside_polygon(p, d["corners"])]
                if under:
                    return min(terrain.bottom_at(d, doc, p) for d in under)
            if digs:
                return min(min(terrain.dig_bottoms(d, doc)) for d in digs)
            return float(o["z"])
        if o["end"].startswith("level:"):
            z = terrain.level_bottom(doc, o["end"].split(":", 1)[1],
                                     -abs(float(o["offset"])))
            if z is not None:
                return z
        return float(o["z"])

    def _ramp_options(self) -> list[dict]:
        doc = self.doc()
        o = self.ramp_opts
        under = [r for r in reversed(doc["levels"])
                 if r["kind"] in ("ground", "basement")]
        choices = [("auto", "Meets an excavation")] + \
            [(f"level:{r['id']}", f"Under {r['name']}") for r in under] + \
            [("elev", "At an elevation")]
        if o["end"] not in [c[0] for c in choices]:
            o["end"] = "auto"
        opts = [{"key": "width", "label": "Width", "kind": "len",
                 "value": o["width"], "min": 0.5, "max": 30.0, "step": 0.10,
                 "tip": "How wide the ramp is"},
                {"key": "slope", "label": "Slope", "kind": "len",
                 "value": o["slope"], "min": 1.0, "max": 100.0, "step": 1.0,
                 "suffix": " %", "tip": "Its steepness (20% is usual for a "
                 "car ramp) — the length follows from it"},
                {"key": "end", "label": "Ends", "kind": "choice",
                 "value": o["end"], "choices": choices,
                 "tip": "Where it arrives: on the floor of the excavation it "
                        "runs into, under a level's floor, or at an "
                        "elevation"}]
        if o["end"].startswith("level:"):
            opts.append({"key": "offset", "label": "below its floor",
                         "kind": "len", "value": o["offset"], "min": 0.0,
                         "max": 5.0})
        else:
            opts.append({"key": "z", "label": "Elevation" if o["end"] ==
                         "elev" else "or else", "kind": "len",
                         "value": o["z"], "min": -100.0, "max": 0.0,
                         "tip": "Its end's elevation (with «Meets an "
                                "excavation»: when it meets none)"})
        return opts

    def _on_ramp_option(self, key: str, value) -> None:
        self.ramp_opts[key] = value
        if key == "end":
            QTimer.singleShot(0, self._refill_options)
        self.viewport.update()

    def _refuse(self, noun: str, why: str, corners=None) -> None:
        """A drawing that can't be made: said in a window, with why and by
        how much — a line in the status bar went unseen and the tool
        looked broken (his ask, 2026-10-05)."""
        from PySide6.QtWidgets import QMessageBox
        from . import plotgeo
        info = ""
        plot = (self.doc().get("plot") or {}).get("corners")
        if corners and plot:
            out = [p for p in corners if not plotgeo._inside(p, plot)]
            if out:
                far = max(out, key=lambda p: min(
                    plotgeo._dist_to_segment(p, a, b)
                    for a, b in plotgeo._edges(plot)))
                d = min(plotgeo._dist_to_segment(far, a, b)
                        for a, b in plotgeo._edges(plot))
                cx = sum(q[0] for q in plot) / len(plot)
                cy = sum(q[1] for q in plot) / len(plot)
                dx, dy = far[0] - cx, far[1] - cy
                side = (("right" if dx > 0 else "left") if abs(dx) >= abs(dy)
                        else ("top" if dy > 0 else "bottom"))
                info = (f"It passes the plot's edge by "
                        f"{compat.fmt_len(d, group=True)} — on the "
                        f"{side} side (in plan).\n\n")
        box = QMessageBox(self.window)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(f"{noun.capitalize()} not made")
        box.setText(f"{why}.")
        box.setInformativeText(
            info + f"Check the sizes against the plot: draw the {noun} "
            "smaller, start it further in — or, if the plot itself is "
            "wrong, fix it in «Edit plot».")
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()

    def _ramp_done(self, corners, bottoms) -> None:
        from . import terrain
        doc = self.doc()
        corners = terrain.on_boundary(doc, corners)
        why = terrain.why_not_dig(doc, corners)
        if why:
            self._refuse("ramp", why.replace("excavation", "ramp"), corners)
            return
        if not self._ok_with_setbacks(doc, corners):
            return
        ramp = model.new_dig(doc["digs"], corners, {"mode": "corners"},
                             base="Ramp")
        ramp["bottoms"] = list(bottoms)
        doc["digs"] = doc["digs"] + [ramp]
        self._commit_terrain(doc)
        self.method = None
        compat.back_to_select(self.viewport)
        self.hide_options()
        compat.flash(self.viewport, f"«{ramp['name']}» dug — "
                     f"{compat.fmt_level(bottoms[0], unit=False)} → "
                     f"{compat.fmt_level(min(bottoms), unit=False)}. "
                     "Double-click "
                     "it to adjust; Ctrl+Z undoes it", 7000)
        self.refresh()

    def _on_dig_option(self, key: str, value) -> None:
        self._mod_opts()[key] = value
        if key == "bottom":                  # the fields that follow change
            # his own pick: kept over the default from now on
            self._mod_opts()["bottom_picked"] = True
            QTimer.singleShot(0, self._refill_options)
        if key == "align":
            tool = getattr(self.viewport, "active_tool", None)
            if hasattr(tool, "frame"):
                tool.frame = self._plot_frame()
                self.viewport.update()

    def _plot_frame(self) -> float:
        """The angle rectangles square with: the plot's longest side
        («Align: Plot sides»), or 0 (the red / green axes)."""
        if self._mod_opts().get("align") != "plot":
            return 0.0
        doc = self.doc()
        if not self.has_plot(doc):
            return 0.0
        pts = doc["plot"]["corners"]
        n = len(pts)
        i = max(range(n), key=lambda k: math.dist(pts[k], pts[(k + 1) % n]))
        a, b = pts[i], pts[(i + 1) % n]
        return math.atan2(b[1] - a[1], b[0] - a[0])

    def _dig_bottom(self) -> dict:
        o = self._mod_opts()
        if o["bottom"] == "depth":
            return {"mode": "depth", "d": float(o["d"])}
        if o["bottom"] == "height":
            return {"mode": "height", "h": float(o["h"])}
        if o["bottom"] and o["bottom"].startswith("level:"):
            return {"mode": "level", "level": o["bottom"].split(":", 1)[1],
                    "offset": -abs(float(o["offset"]))}
        return {"mode": "elev", "z": float(o["z"])}

    def _dig_done(self, corners) -> None:
        from . import plotgeo, terrain
        doc = self.doc()
        corners = terrain.on_boundary(doc, corners)
        why = terrain.why_not_dig(doc, corners)
        kind = getattr(self, "creating", "cut")
        noun = "fill" if kind == "fill" else "excavation"
        if why:
            self._refuse(noun, why.replace("excavation", noun), corners)
            return                           # the tool stays out: try again
        dig = model.new_dig(doc["digs"], plotgeo.clean(corners),
                            self._dig_bottom(),
                            base="Fill" if kind == "fill" else "Excavation",
                            kind=kind)
        dig["angles"] = [float(self._mod_opts()["wall"])] * len(dig["corners"])
        trial = dict(doc, digs=doc["digs"] + [dig])
        if dig["id"] not in {d["id"] for d in terrain.opened(trial)}:
            # its slopes reach past the plot
            self._refuse(noun, f"With those slopes the {noun} reaches past "
                         "the plot (make its edges steeper, or draw it "
                         "smaller)", terrain.top_of(dig, trial))
            return
        # the setbacks are judged where it opens in the ground (slopes too);
        # grading the ground (a fill) is allowed in them — no warning
        if kind != "fill" and not self._ok_with_setbacks(
                doc, terrain.top_of(dig, trial)):
            return
        # inside another excavation and no deeper: it would dig nothing —
        # stop and offer a pit (his call, 07/11/2026: a 0 m³ excavation
        # «did not happen»; a pop-up, not a passing message)
        if kind != "fill":
            box_in = terrain.container(dig, trial)
            if box_in is not None:
                b = terrain.deeper_bottom(dig, trial)
                if b is None or not self._ask_pit(dig, box_in, b, trial):
                    return                   # the tool stays out
                dig["bottom"] = b
        doc["digs"] = doc["digs"] + [dig]
        doc = self._commit_terrain(doc)
        v = compat.dig_volumes(doc).get(dig["id"], 0.0)
        self.method = None
        compat.back_to_select(self.viewport)
        self.hide_options()
        if kind != "fill" and terrain.above_ground(dig, doc):
            compat.flash(self.viewport, f"«{dig['name']}»: "
                         + tr(terrain.ABOVE_GROUND), 9000)
            self.refresh()
            return
        other = terrain.inside_no_deeper(dig, doc) if kind != "fill" \
            else None
        if other:
            compat.flash(self.viewport, f"«{dig['name']}»: "
                         + tr(terrain.INSIDE_NO_DEEPER, other=other), 9000)
            self.refresh()
            return
        compat.flash(self.viewport, f"«{dig['name']}» "
                     + ("raised" if kind == "fill" else "dug")
                     + f" — {compat.fmt_volume(v)} of earth "
                     + ("brought in" if kind == "fill" else "taken out")
                     + ". Ctrl+Z undoes it", 6000)
        self.refresh()

    def _ask_pit(self, dig: dict, box_in: dict, bottom: dict,
                 doc: dict) -> bool:
        """The pop-up for a cut drawn inside an excavation and no deeper:
        True = make it a pit ``terrain.PIT_DEEPER`` deeper."""
        from PySide6.QtWidgets import QMessageBox

        from . import terrain
        now = min(terrain.dig_bottoms(dig, doc))
        new = min(terrain.dig_bottoms(dict(dig, bottom=bottom), doc))
        box = QMessageBox(self.window)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(tr("Excavation inside «{o}»",
                              o=box_in.get("name", "")))
        box.setText(tr(
            "«{n}» lies inside «{o}» and goes no deeper ({z}): the earth "
            "there is already out, so it would change nothing.",
            n=dig["name"], o=box_in.get("name", ""),
            z=compat.fmt_level(now)))
        box.setInformativeText(tr(
            "A smaller excavation inside another is usually a pit — an "
            "elevator pit, a sump, a footing's pit. Make it a pit {d} "
            "deeper (to {z})? Its bottom can be changed later: double-click "
            "it.", d=compat.fmt_len(terrain.PIT_DEEPER),
            z=compat.fmt_level(new)))
        yes = box.addButton(tr("Make it a pit ({z})",
                               z=compat.fmt_level(new)),
                            QMessageBox.AcceptRole)
        box.addButton(tr("Cancel"), QMessageBox.RejectRole)
        box.setDefaultButton(yes)
        box.exec()
        return box.clickedButton() is yes

    def edit_dig(self, dig_id: str) -> None:
        """An excavation's own window (modal): name, bottom (also per
        corner — ramps), the corners' table, volume; delete. Apply = one
        Ctrl+Z."""
        from .dialogs import DigDialog
        doc = self.doc()
        dig = next((d for d in doc["digs"] if d["id"] == dig_id), None)
        if dig is None or not self.has_plot(doc):
            return
        self.hub.close_sub()
        dlg = DigDialog(dig, doc, self.window, self._preview_dig,
                        view=self._view_pair())
        self._mat_tab(dlg, "fill" if dig.get("kind") == "fill" else "dig",
                      dig_id)
        try:
            ok = dlg.exec()
        finally:
            self._preview_dig(None)
        if not ok:
            return
        action, new = dlg.result_data()
        self._mat_take(dlg, action)
        doc = self.doc()                 # fresh (the window's boxes wrote)
        if action == "delete":
            doc["digs"] = [d for d in doc["digs"] if d["id"] != dig_id]
            msg = (f"«{dig['name']}» taken away — Ctrl+Z brings it back"
                   if dig.get("kind") == "fill" else
                   f"«{dig['name']}» filled back in — Ctrl+Z digs it again")
        else:
            doc["digs"] = [new if d["id"] == dig_id else d
                           for d in doc["digs"]]
            msg = f"«{new['name']}» updated — Ctrl+Z undoes it"
        self._commit_terrain(doc)
        compat.flash(self.viewport, msg, 5000)
        self.refresh()
        if action != "delete":
            self._again(dlg, lambda: self.edit_dig(dig_id))

    def _preview_dig(self, preview) -> None:
        """(corners, ground heights, active corner) while the Excavation
        window is open."""
        self.dig_preview = preview
        self.viewport.update()

    def dig_of(self, group) -> str | None:
        """The terrain modification (excavation or fill) a group stands
        for — its id — or None."""
        if compat.kind_of(group) not in ("dig", "fill"):
            return None
        rec = (getattr(group, "ext", None) or {}).get(compat.EXT_KEY) or {}
        return rec.get("id")

    def start_dig_edit_tool(self, name: str) -> None:
        """Edit excavation › Move / Add / Delete point — on whichever
        excavation is under the cursor."""
        from .plotedit import DigEditTool
        from . import terrain
        if not self.doc()["digs"]:
            compat.flash(self.viewport, "No excavation or fill yet — draw "
                         "one first")
            return

        def get_digs():
            doc = self.doc()
            if not self.has_plot(doc):
                return {}
            plot = doc["plot"]
            return {d["id"]: {"corners": d["corners"],
                              "heights": [terrain.ground_at(plot, q)
                                          for q in d["corners"]],
                              "closing": 0, "breaks": []}
                    for d in terrain.opened(doc)}

        def check(did, corners):
            return terrain.why_not_dig(self.doc(), corners, ignore=did)

        def change(did, corners, _hs, _cl, _br):
            doc = self.doc()
            dig = next((d for d in doc["digs"] if d["id"] == did), None)
            if dig is None:
                return
            new = terrain.reshape(dig, doc, corners)
            doc["digs"] = [new if d["id"] == did else d for d in doc["digs"]]
            self._commit_terrain(doc)

        self.method = name
        tool = DigEditTool(EDIT_POINTS[name], get_digs, change,
                           self._plot_cancelled, PLOT_Z, check)
        tool.noun = "Excavation / fill"
        tool.plot_dims = lambda: self.dims_on("dig_dims")
        self._activate(tool)
        self.strip.fill(self.element, self.method)

    def start_slab_edit_tool(self, name: str) -> None:
        """Structure › Edit slabs › Move points / Move side / Add point /
        Delete point — on the current level's drawn slab under the cursor
        (slabedit.py)."""
        from .slabedit import SLAB_EDIT, SlabEditTool
        from . import structure as S
        if self._pro_only("slab") or name not in SLAB_EDIT:
            return
        _i, lv, z0 = self._work_level()

        def get_slabs():
            doc = self.doc()
            info = S.levels_info(doc, model.elevations).get(lv["id"])
            if info is None:
                return {}
            out = {}
            for e in doc.get("structure") or []:
                if e.get("type") != "slab" or e["level"] != lv["id"] \
                        or e.get("auto"):
                    continue
                top = info["z0"] + float(e.get("offset", 0.0))
                out[e["id"]] = {"corners": e["corners"],
                                "heights": [top] * len(e["corners"]),
                                "closing": 0, "breaks": []}
            return out
        if not get_slabs():
            compat.flash(self.viewport, f"No drawn slab on «{lv['name']}» — "
                         "an excavation's slab follows its excavation", 5000)
            return

        def check(_sid, corners):
            from shapely.geometry import Polygon
            try:
                p = Polygon(corners)
            except Exception:  # noqa: BLE001
                return "Not a slab outline"
            if not p.is_valid:
                return "The sides would cross"
            if p.area < 0.05:
                return "Too small for a slab"
            return None

        def change(sid, corners, _hs, _cl, _br):
            doc = self._live(self.doc())
            doc["structure"] = [dict(e, corners=[[round(q[0], 4),
                                                  round(q[1], 4)]
                                                 for q in corners])
                                if e["id"] == sid else e
                                for e in doc["structure"]]
            self._commit_all(doc)

        self.method = name
        tool = SlabEditTool(SLAB_EDIT[name], get_slabs, change,
                            self._plot_cancelled, check)
        tool.noun = "Slab"
        tool.plot_dims = lambda: True
        self._activate(tool)
        self.strip.fill(self.element, self.method)

    def _ok_with_setbacks(self, doc: dict, corners,
                          noun: str = "excavation") -> bool:
        """An excavation (or a wall) reaching into the setbacks: say so,
        and let the user go on or not (a choice that can be silenced here
        and brought back in the Settings)."""
        from PySide6.QtWidgets import QCheckBox, QMessageBox
        from . import plotgeo, prefs
        if not self.has_plot(doc):
            return True
        roles, _d, area = plotgeo.setbacks_of(doc["plot"])
        if not any(roles) or not prefs.get("warn_setbacks"):
            return True
        wall = noun == "wall"
        if area and (all(plotgeo.within([p], area, margin=0.0)
                         for p in corners) if wall   # loose points
                     else plotgeo.within(corners, area, margin=0.0)):
            return True
        box = QMessageBox(self.window)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Into the setbacks")
        box.setText(f"This {noun} goes outside the buildable area — "
                    "into the setbacks.")
        box.setInformativeText("The setbacks are the city's distances from "
                               "the plot's edges. "
                               + ("Build it there anyway?" if wall
                                  else "Dig there anyway?"))
        box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        box.button(QMessageBox.Ok).setText("Build anyway" if wall
                                           else "Dig anyway")
        box.setDefaultButton(QMessageBox.Cancel)
        quiet = QCheckBox("Don't show this again (Settings bring it back)")
        box.setCheckBox(quiet)
        go = box.exec() == QMessageBox.Ok
        if quiet.isChecked():
            prefs.put("warn_setbacks", False)
        if not go:
            compat.flash(self.viewport, ("Wall not built" if wall else
                                         "Excavation not dug")
                         + " — draw it inside the dashed area", 5000)
        return go

    # ---- Terrain: deleting (his ask, 2026-10-03 — the Delete key left the
    # data behind: a deleted excavation came back) ------------------------------
    def delete_plot(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        doc = self.doc()
        if not self.has_plot(doc):
            compat.flash(self.viewport, "No plot to delete", 4000)
            return
        n = len(doc.get("digs") or [])
        if QMessageBox.question(
                self.window, "Delete the plot?",
                "The plot goes" + (f", and its {n} excavation"
                                   f"{'s' if n > 1 else ''} / fill"
                                   f"{'s' if n > 1 else ''} with it"
                                   if n else "")
                + ". Ctrl+Z brings it back.",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel) != QMessageBox.Yes:
            return
        compat.back_to_select(self.viewport)
        doc = dict(doc, plot=None, digs=[])
        doc["done"] = [k for k in doc["done"] if k not in AUTO_PHASES]
        compat.remove_terrain(self.viewport, self.app.key, doc,
                              compat.terrain_groups(self.viewport))
        self.refresh()
        compat.flash(self.viewport, "Plot deleted — Ctrl+Z brings it back",
                     5000)

    def delete_dig(self, dig_id: str) -> None:
        """One excavation / fill out — the terrain made again without it."""
        doc = self.doc()
        dig = next((d for d in doc.get("digs") or [] if d["id"] == dig_id),
                   None)
        if dig is None:
            return
        doc["digs"] = [d for d in doc["digs"] if d["id"] != dig_id]
        if self.has_plot(doc):
            self._commit_terrain(doc)
        else:
            g = compat.find_group(self.viewport, dig.get("uid", ""))
            compat.remove_terrain(self.viewport, self.app.key, doc,
                                  [g] if g is not None else [])
        self.refresh()
        compat.flash(self.viewport, f"«{dig['name']}» deleted — Ctrl+Z "
                     "brings it back", 5000)

    def start_dig_erase_tool(self) -> None:
        from . import plotedit
        if not (self.doc().get("digs")):
            compat.flash(self.viewport, "No excavations or fills to delete",
                         4000)
            return
        tool = plotedit.DigEraseTool(lambda: self.doc().get("digs") or [],
                                     self.delete_dig, self._plot_cancelled)
        self.method = "Delete excavation"
        self._activate(tool)
        self.strip.fill(self.element, self.method)

    def _dig_cancelled(self) -> None:
        self.hide_options()
        self._plot_cancelled()

    def _commit_terrain(self, doc: dict) -> dict:
        """The terrain rebuilt and stored — one Ctrl+Z. When an excavation
        changes the slabs that follow it (autoslabs), the building is made
        again in the same step."""
        from . import autoslabs
        doc = self._with_mats(doc)
        before = doc.get("structure") or []
        doc = autoslabs.sync(doc, model.elevations)
        building = None
        if (doc.get("structure") or []) != before:
            doc = self._with_built(doc)
            building = lambda d: compat.building_swap(       # noqa: E731
                self.viewport, d, model.elevations, compat.level_layer)
        out = compat.commit_terrain(self.viewport, self.app.key, doc,
                                    PLOT_Z, PLOT_COLOR, building=building)
        if building is not None:
            self._apply_parts()
            self._outline_soon()
        return out

    # ---- The options bar (creation tools) ---------------------------------------------
    def show_options(self, tool_cls, title: str, build, on_change) -> None:
        """Open the options bar for a creation tool: ``build()`` gives the
        options (asked again when one choice changes others)."""
        self.options_for = tool_cls
        self._opt_build = (title, build, on_change)
        self._refill_options()
        self._show_piece(self.optbar, self.opt_bar, True)
        self.layout_floating()
        QTimer.singleShot(0, self.layout_floating)   # once all is laid out

    def _refill_options(self) -> None:
        if self.options_for is None:
            return
        title, build, on_change = self._opt_build
        self.optbar.fill(title, build(), on_change)
        self.layout_floating()
        QTimer.singleShot(0, self.layout_floating)   # once all is laid out

    def hide_options(self) -> None:
        self.options_for = None
        self._show_piece(self.optbar, self.opt_bar, False)

    # ---- Lite / Pro ----------------------------------------------------------------
    def _pro_only(self, element: str | None) -> bool:
        """The Lite, asked for an ArchXQ IT Pro element: say so, do nothing
        (True). Always False in the Pro. Every Pro tool's door asks it —
        the options bar is not the only way in (a shortcut, a double-click,
        the Import/Export menu, a level change)."""
        if not (edition.lite() and is_pro(element)):
            return False
        compat.flash(self.viewport, PRO_NOTE + " — www.xq.com.br/archxq-it",
                     5000)
        return True

    def _pro_options(self) -> list[dict]:
        return [{"key": "note", "label": "", "kind": "note",
                 "text": PRO_NOTE},
                {"key": "get", "label": "", "kind": "button",
                 "text": "Get Pro", "tip": edition.PRO_URL},
                # bought already: the key, and the Pro installs itself
                {"key": "upgrade", "label": "", "kind": "button",
                 "text": "I have a key…",
                 "tip": "Upgrade to Pro — paste your license key"}]

    def _on_pro_option(self, key: str, value) -> None:
        if key == "upgrade":
            from .updater import open_dialog
            open_dialog(self)
        elif key == "get":
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(edition.PRO_URL))

    # ---- The options bar of an ELEMENT (before drawing, and while drawing) --------
    def _element_options(self) -> None:
        """The picked element's own bar — shown as soon as it is picked
        and kept while it is drawn (a terrain tool's bar, tied to its tool,
        is left alone)."""
        if isinstance(self.options_for, type):
            return                               # a tool's bar is out
        if edition.lite() and is_pro(self.element):
            key = ("pro", self.element)          # the Lite: one line + link
            if self.options_for != key:
                self.show_options(key, ELEMENTS[self.element].label,
                                  self._pro_options, self._on_pro_option)
            return
        bars = {"wall": ("Wall", self._wall_options, self._on_wall_option),
                "column": ("Column", self._column_options,
                           lambda k, v: self._on_struct_option("column", k,
                                                               v)),
                "beam": ("Beam", self._beam_options,
                         lambda k, v: self._on_struct_option("beam", k, v)),
                "slab": ("Slab", self._slab_options,
                         lambda k, v: self._on_struct_option("slab", k, v)),
                "footing": ("Footing", self._footing_options,
                            lambda k, v: self._on_struct_option("footing", k,
                                                                v)),
                "roof": ("Roof", self._roof_options,
                         lambda k, v: self._on_struct_option("roof", k, v)),
                "sheets": ("Sheets", self._sheet_options,
                           self._on_doc_option),
                "wall_import": ("DXF", self._dxf_options,
                                self._on_dxf_option),
                "rooms": ("Rooms", lambda: [
                    {"key": "act", "label": "", "kind": "icons",
                     "value": None, "choices": ROOM_ACTIONS},
                    {"key": "labels", "label": "Labels", "kind": "segments",
                     "value": "yes" if self.room_labels else "no",
                     "choices": [("yes", "In plan"), ("no", "Not shown")],
                     "tip": "Each room's name and area in the plan view"},
                    {"key": "rooms", "label": "On sheets", "kind": "segments",
                     "value": self.doc_opts["rooms"],
                     "choices": [("yes", "Names + schedule"),
                                 ("no", "None")],
                     "tip": "On the plans' sheets: each room's name and "
                            "area; and a sheet with the area schedule"}],
                    self._on_room_option),
                "section": ("Section", lambda: [
                    {"key": "shape", "label": "", "kind": "icons",
                     "value": "line" if self.tool_element() == "section"
                     else None, "choices": SECTION_SHAPES}],
                    self._on_section_option),
                "export": ("Export", lambda: [
                    {"key": "act", "label": "", "kind": "icons",
                     "value": None, "choices": EXPORT_ACTIONS}],
                    self._on_doc_option),
                "separator": ("Room separator", lambda: [
                    {"key": "shape", "label": "", "kind": "icons",
                     "value": self.sep_opts["shape"]
                     if self.tool_element() == "separator"
                     and self.method != "Delete" else None,
                     "choices": SEP_SHAPES}],
                    self._on_separator_option)}
        for kind, label in (("door", "Door"), ("window", "Window"),
                            ("void", "Opening")):
            bars[kind] = (label, lambda k=kind: self._opening_options(k),
                          lambda key, v, k=kind: self._on_opening_option(
                              k, key, v))
        key = ("element", self.element)
        if self.element in bars:
            if self.options_for != key:
                title, build, on_change = bars[self.element]
                self.show_options(key, title, build, on_change)
            else:
                self._refill_options()
        elif self.options_for is not None:
            self.hide_options()

    def _level_height(self) -> float:
        levels = self.doc()["levels"]
        i = self.floor if 0 <= self.floor < len(levels) \
            else self._ground_index(self.doc())
        return float(levels[i]["height"])

    def _wall_options(self) -> list[dict]:
        o = self.wall_opts
        opts = [
            # lit only while drawing (the shape is remembered all the same)
            {"key": "shape", "label": "", "kind": "icons",
             "value": o["shape"] if self.wall_tool_out() else None,
             "choices": WALL_SHAPES},
            {"key": "align", "label": "Alignment", "kind": "segments",
             "value": o["align"],
             "choices": [("outside", "Outside"), ("centre", "Centre"),
                         ("inside", "Inside")],
             "tip": "Where the wall sits on the line you draw: its outer "
                    "face on the line, its centre, or its inner face. A "
                    "rectangle or a circle knows its inside; an open run "
                    "of walls takes the side the cursor is on"},
            {"key": "t", "label": "Thickness", "kind": "len",
             "value": o["t"], "min": 0.05, "max": 2.0, "step": 0.01,
             "tip": "The wall's thickness"},
            {"key": "height", "label": "Height", "kind": "choice",
             "value": o["height"],
             "choices": [("level", tr("Level height") + " "
                                   f"({compat.fmt_len(self._level_height())})"),
                         ("custom", "Custom")],
             "tip": "Up to the floor above (it follows the level's "
                    "height), or a height of its own (a low wall, a "
                    "parapet…)"},
        ]
        if o["height"] == "custom":
            opts.append({"key": "h", "label": "", "kind": "len",
                         "value": o["h"], "min": 0.10, "max": 30.0,
                         "step": 0.05, "tip": "The wall's own height, "
                         "from its level's floor"})
        if o.get("cw"):
            # a curtain wall: ALL its details before drawing (his ask,
            # 2026-10-14 — «only after it is drawn» was a contradiction);
            # last, just left of «?»: «more» comes after what is there
            opts.append({"key": "cw_more", "label": "", "kind": "button",
                         "text": "More…", "outline": True,
                         "tip": "The curtain wall's details: mullions, "
                                "posts, transoms, band, glass — set them "
                                "before you draw (the selected ones: their "
                                "own window)"})
        return opts

    def _curtain_preset(self, rec: dict) -> None:
        """A curtain wall's own keys kept as the hidden preset (wall_opts):
        what the next ones drawn take, what «More…» opens with."""
        from . import curtain as CW
        self.wall_opts.update({k: rec[k] for k in CW.KEYS if k in rec})

    def _selected_curtains(self) -> list[str]:
        """The ids of the curtain walls selected (none: [])."""
        key, ids = self._lib_picked()
        if key != "wall":
            return []
        cws = {w["id"] for w in self.doc()["walls"] if w.get("cw")}
        return [i for i in ids if i in cws]

    def curtain_more(self) -> None:
        """«More…» of a curtain wall (his ask, 2026-10-14):
          - ONE selected → its own window (as a double-click);
          - SEVERAL selected → the «Curtain wall» tab with the last edit's
            values; OK = only what was CHANGED goes to all of them (their
            lengths, places, the rest of each stay);
          - none → the details for the NEXT ones drawn.
        Every OK is also the hidden preset (``_curtain_preset``)."""
        from . import curtain as CW
        from . import dialogs
        sel = self._selected_curtains()
        if len(sel) == 1:
            self.edit_wall(sel[0])
            return
        o = self.wall_opts
        dlg = dialogs.CurtainDialog(dict({k: o.get(k, v)
                                          for k, v in CW.DEFAULTS.items()},
                                         t=o["t"]), self.viewport.window(),
                                    count=len(sel))
        before = dlg.values()
        if dlg.exec() != dialogs.QDialog.Accepted:
            return
        after = dlg.values()
        self._curtain_preset(after)
        if not sel:
            self._refill_options()
            self._library_show()
            compat.flash(self.viewport, "Curtain wall: the next ones drawn "
                         "take these details", 3500)
            return
        changed = {k: v for k, v in after.items() if before.get(k) != v}
        if not changed:
            compat.flash(self.viewport, "Nothing changed", 2500)
            return
        doc = self._live(self.doc())
        ids = set(sel)
        doc["walls"] = [dict(w, **changed) if w["id"] in ids else w
                        for w in doc["walls"]]
        self._commit_all(doc)
        self._library_show()
        compat.flash(self.viewport, f"{len(sel)} curtain walls updated — "
                     "Ctrl+Z undoes it", 4000)

    def _on_wall_option(self, key: str, value) -> None:
        if key == "cw_more":
            QTimer.singleShot(0, self.curtain_more)
            return
        self.wall_opts[key] = value
        if key == "height":                  # the height field comes / goes
            QTimer.singleShot(0, self._refill_options)
        if key == "shape":
            QTimer.singleShot(0, self.start_wall_tool)
        self._bar_to_selected("wall", key, value)

    # ---- Structure: the options bars ------------------------------------------------
    def _struct_opts(self, element: str) -> dict:
        return {"column": self.col_opts, "beam": self.beam_opts,
                "slab": self.slab_opts, "footing": self.foot_opts,
                "roof": self.roof_opts}[element]

    def _lit(self, element: str, o: dict):
        """The shape icon is lit only while that element is being drawn."""
        return o["shape"] if self.tool_element() == element else None

    def _column_options(self) -> list[dict]:
        o = self.col_opts
        round_ = o["section"] == "round"
        opts = [{"key": "shape", "label": "", "kind": "icons",
                 "value": self._lit("column", o), "choices": COLUMN_SHAPES},
                {"key": "section", "label": "", "kind": "segments",
                 "value": o["section"],
                 "choices": [("rect", "Rectangle"), ("round", "Round")],
                 "tip": "The column's section: rectangular or round"},
                {"key": "w", "label": "Diameter" if round_ else "Width",
                 "kind": "len", "value": o["w"], "min": 0.05, "max": 5.0,
                 "step": 0.05}]
        if not round_:
            opts += [{"key": "d", "label": "Depth", "kind": "len",
                      "value": o["d"], "min": 0.05, "max": 5.0,
                      "step": 0.05},
                     {"key": "angle", "label": "Angle", "kind": "len",
                      "value": o["angle"], "min": -180.0, "max": 180.0,
                      "step": 15.0, "suffix": "°",
                      "tip": "Turned about its axis (a row also follows "
                             "its line)"}]
        # a single column / a grid: the column's point on the cursor; a ROW:
        # how its columns stand on the line (his ask, 08/11/2026 — the nine
        # points meant nothing on a row, Inside / Outside were only in its
        # window)
        if not round_ and o["shape"] != "row":
            opts += [{"key": "anchor", "label": "", "kind": "segments",
                      "value": "sw" if o["anchor"] == "corner"
                      else o["anchor"],
                      "choices": [("centre", "◉ Centre"),
                                  ("sw", "↙ Lower left"), ("s", "↓ Bottom"),
                                  ("se", "↘ Lower right"), ("e", "→ Right"),
                                  ("ne", "↗ Upper right"), ("n", "↑ Top"),
                                  ("nw", "↖ Upper left"), ("w", "← Left")],
                      "tip": "The column's point that goes on the cursor: "
                             "its centre, a corner or a side's middle (to "
                             "lay it flush with a face)"}]
        if o["shape"] == "row":
            al = o.get("align", "auto")
            if al not in ("inside", "centre", "outside"):
                # (auto: inside along an excavation — the usual case on a
                # level with one — else centred)
                _i, lv, _z = self._work_level()
                al = "inside" if self._pits_on(lv["id"]) else "centre"
            opts.append({"key": "align", "label": "", "kind": "segments",
                         "value": al,
                         "choices": [("inside", "Inside"),
                                     ("centre", "Centre"),
                                     ("outside", "Outside")],
                         "tip": "How the columns stand on the line you "
                                "click: their faces flush with it on the "
                                "inside (in an excavation: against its "
                                "sides), centred on it, or flush on the "
                                "outside"})
            opts.append({"key": "by", "label": "", "kind": "segments",
                         "value": o["by"],
                         "choices": [("count", "By count"),
                                     ("spacing", "By spacing")],
                         "tip": "How many columns, or how far apart"})
            if o["by"] == "count":
                opts.append({"key": "count", "label": "Count",
                             "kind": "int", "value": o["count"], "min": 1,
                             "max": 200, "tip": "How many columns"})
            else:
                opts.append({"key": "spacing", "label": "Every",
                             "kind": "len", "value": o["spacing"],
                             "min": 0.2, "max": 100.0, "step": 0.05,
                             "tip": "At most this far apart — equal bays "
                                    "on each stretch of the row"})
            opts.append({"key": "ends", "label": "", "kind": "segments",
                         "value": o["ends"],
                         "choices": [("both", "First + last"),
                                     ("first", "First only"),
                                     ("last", "Last only"),
                                     ("none", "Between only")],
                         "tip": "Whether the points you click get a column "
                                "(an end on a wall that already has one: "
                                "leave it out)"})
        if o["shape"] == "grid":
            opts += [{"key": "nx", "label": "Columns", "kind": "int",
                      "value": o["nx"], "min": 1, "max": 50},
                     {"key": "ny", "label": "Rows", "kind": "int",
                      "value": o["ny"], "min": 1, "max": 50}]
        opts.append({"key": "fit", "label": "In walls", "kind": "segments",
                     "value": o["fit"],
                     "choices": [("fit", "Fit inside"),
                                 ("free", "As drawn")],
                     "tip": "Fit inside: on a wall, the column takes the "
                            "wall's thickness and line and hides in it (the "
                            "usual case); where walls meet, a square as "
                            "thick as the wall. As drawn: its own sizes "
                            "(a column meant to show)"})
        opts.append({"key": "height", "label": "Height", "kind": "segments",
                     "value": o["height"],
                     "choices": [("level", "To the slab"),
                                 ("custom", "Custom")],
                     "tip": "Up to the underside of the slab above (it "
                            "follows), or a height of its own"})
        if o["height"] == "custom":
            opts.append({"key": "h", "label": "", "kind": "len",
                         "value": o["h"], "min": 0.2, "max": 50.0})
        opts.append({"key": "base", "label": "Base", "kind": "len",
                     "value": o["base"], "min": -20.0, "max": 20.0,
                     "step": 0.05,
                     "tip": "Where it starts, from its level's floor: 0 = "
                            "on the floor; negative = under it, into the "
                            "ground (to a footing)"})
        return opts

    def _beam_options(self) -> list[dict]:
        o = self.beam_opts
        return [{"key": "shape", "label": "", "kind": "icons",
                 "value": self._lit("beam", o), "choices": BEAM_SHAPES},
                {"key": "insert", "label": "Insert", "kind": "segments",
                 "value": o.get("insert", "centre"),
                 "choices": [("left", "Left"), ("centre", "Centre"),
                             ("right", "Right")],
                 "tip": "Where the beam sits on the line you draw: its "
                        "left face, its axis, or its right face — looking "
                        "the way you draw. Tab swaps the faces"},
                {"key": "w", "label": "Width", "kind": "len",
                 "value": o["w"], "min": 0.05, "max": 3.0, "step": 0.05},
                {"key": "h", "label": "Height", "kind": "len",
                 "value": o["h"], "min": 0.05, "max": 5.0, "step": 0.05,
                 "tip": "From its top, downwards"},
                {"key": "zmode", "label": "Top", "kind": "segments",
                 "value": o["zmode"],
                 "choices": [("level", "Under the slab"),
                             ("own", "Its own")],
                 "tip": "Under the slab above (in it), or its top at a "
                        "height of its own over the floor — a lean-to's "
                        "beams on posts, a pergola"}] + (
                [{"key": "zt", "label": "Top at", "kind": "len",
                  "value": o["zt"], "min": 0.2, "max": 50.0, "step": 0.05,
                  "tip": "Its top, over its level's floor"}]
                if o["zmode"] == "own" else []) + [
                {"key": "fit", "label": "In walls", "kind": "segments",
                 "value": o["fit"],
                 "choices": [("fit", "Fit inside"), ("free", "As drawn")],
                 "tip": "Fit inside: a beam along a wall takes its "
                        "thickness and hides in it. As drawn: its own "
                        "width"}]

    def _slab_options(self) -> list[dict]:
        from .structtools import HOLE_DRAWN
        o = self.slab_opts
        if o.get("shape") == "hole" and self.tool_element() == "slab":
            # an OPENING: how it is drawn — any shape (a customer's ask,
            # 2026-10-13); the slab's own sizes don't apply to it
            return [{"key": "shape", "label": "", "kind": "icons",
                     "value": self._lit("slab", o), "choices": SLAB_SHAPES},
                    {"key": "hole_by", "label": "Drawn", "kind": "segments",
                     "value": o.get("hole_by", "rect"),
                     "choices": list(HOLE_DRAWN),
                     "tip": "The opening's shape: a rectangle, a rotated "
                            "one, point by point or a circle"}]
        return [{"key": "shape", "label": "", "kind": "icons",
                 "value": self._lit("slab", o), "choices": SLAB_SHAPES},
                {"key": "t", "label": "Thickness", "kind": "len",
                 "value": o["t"], "min": 0.02, "max": 3.0, "step": 0.01},
                # up to 10 m: a slab may be a CEILING too — its top at
                # 2.80 under the roof's trusses, a plenum over it (a
                # customer's ask, 2026-10-13: «how you make plenum»)
                {"key": "offset", "label": "Top", "kind": "len",
                 "value": o["offset"], "min": -5.0, "max": 10.0,
                 "step": 0.01, "tip": "Its top, from the level's floor (0 = "
                                      "the floor itself; up high: a ceiling)"}]

    def _footing_options(self) -> list[dict]:
        o = self.foot_opts
        path = o["shape"] == "path"
        ft = o.get("ftype", "pads")
        opts = [{"key": "shape", "label": "", "kind": "icons",
                 "value": self._lit("footing", o), "choices": FOOTING_SHAPES}]
        if path:
            # a row of footings (colrows, PLANO D): what, and how they stand
            # on the line — as the columns' row bar
            al = o.get("align", "auto")
            if al not in ("inside", "centre", "outside"):
                al = "centre"          # its own line (his test, 07/11)
            opts += [{"key": "ftype", "label": "", "kind": "segments",
                      "value": ft,
                      "choices": [("pads", "Pads"), ("strip", "Strip"),
                                  ("both", "Pads + strip")],
                      "tip": "Pads on the points of the path, a strip along "
                             "it, or both (the strip running between the "
                             "pads)"},
                     {"key": "align", "label": "", "kind": "segments",
                      "value": al,
                      "choices": [("inside", "Inside"), ("centre", "Centre"),
                                  ("outside", "Outside")],
                      "tip": "How the footings stand on the line you click: "
                             "their faces flush with it on the inside (in "
                             "an excavation: against its sides), centred on "
                             "it, or flush on the outside"}]
            if ft != "strip":
                opts.append({"key": "by", "label": "", "kind": "segments",
                             "value": o.get("by", "spacing"),
                             "choices": [("count", "By count"),
                                         ("spacing", "By spacing")],
                             "tip": "How many pads, or how far apart"})
                if o.get("by", "spacing") == "count":
                    opts.append({"key": "count", "label": "Count",
                                 "kind": "int", "value": o.get("count", 4),
                                 "min": 1, "max": 200,
                                 "tip": "How many pads on each stretch"})
                else:
                    opts.append({"key": "spacing", "label": "Every",
                                 "kind": "len",
                                 "value": o.get("spacing", 2.0),
                                 "min": 0.2, "max": 100.0, "step": 0.05,
                                 "tip": "At most this far apart — equal "
                                        "bays on each stretch"})
                opts.append({"key": "ends", "label": "", "kind": "segments",
                             "value": o.get("ends", "both"),
                             "choices": [("both", "First + last"),
                                         ("first", "First only"),
                                         ("last", "Last only"),
                                         ("none", "Between only")],
                             "tip": "Whether the points you click get a pad"})
        if not path or ft != "strip":
            opts.append({"key": "w", "label": "Pad", "kind": "len",
                         "value": o["w"], "min": 0.2, "max": 10.0,
                         "step": 0.05,
                         "tip": "A pad's side (never less than its column "
                                "+ 0.20)"})
        if not path or ft != "pads":
            opts.append({"key": "sw", "label": "Strip", "kind": "len",
                         "value": o["sw"], "min": 0.2, "max": 5.0,
                         "step": 0.05, "tip": "A strip footing's width"})
        both = path and ft == "both"
        opts.append({"key": "d", "label": "Strip depth" if both else "Depth",
                     "kind": "len", "value": o["d"], "min": 0.1, "max": 5.0,
                     "step": 0.05,
                     "tip": "How deep, under the level's slab"})
        if both:
            opts.append({"key": "pd", "label": "Pad depth", "kind": "len",
                         "value": o.get("pd", 0.80), "min": 0.1, "max": 5.0,
                         "step": 0.05,
                         "tip": "The pads go deeper than the strip — they "
                                "carry the load"})
        return opts

    def _roof_options(self) -> list[dict]:
        o = self.roof_opts
        kind = o["kind"]
        flat, hidden = kind == "flat", kind == "hidden"
        opts = [{"key": "shape", "label": "", "kind": "icons",
                 "value": self._lit("roof", o), "choices": ROOF_SHAPES},
                {"key": "kind", "label": "Type", "kind": "segments",
                 "value": kind,
                 "choices": [("gable", "Gable"), ("hip", "Hip"),
                             ("flat", "Flat"), ("shed", "Shed"),
                             ("hidden", "Hidden"),
                             ("butterfly", "Butterfly"),
                             ("mansard", "Mansard")],
                 "tip": "Gable: two slopes, a triangle of wall at each end. "
                        "Hip: four slopes. Flat: a slab, with a parapet if "
                        "you like. Shed: one slope. Hidden: low slopes "
                        "behind a parapet, with a gutter"}]
        if not flat:
            opts.append({"key": "slope", "label": "Slope", "kind": "len",
                         "value": o["slope"], "min": 5.0, "max": 75.0,
                         "step": 5.0, "suffix": "°"})
        if not hidden:
            opts.append({"key": "overhang",
                         "label": "Eaves" if kind in ("gable", "shed")
                         else "Overhang", "kind": "len",
                         "value": o["overhang"], "min": 0.0, "max": 3.0,
                         "step": 0.05,
                         "tip": "How far it reaches past the walls"
                         + (" along the eaves" if kind in ("gable", "shed")
                            else "")})
        if kind in ("gable", "shed"):
            opts.append({"key": "go", "label": "Gable ends", "kind": "len",
                         "value": o["go"], "min": 0.0, "max": 3.0,
                         "step": 0.05, "tip": "How far it reaches past the "
                                              "end walls"})
        opts.append({"key": "t", "label": "Slab" if hidden else "Thickness",
                     "kind": "len", "value": o["t"], "min": 0.02, "max": 1.0,
                     "step": 0.01,
                     "tip": "The slab under the sheets" if hidden else ""})
        opts.append({"key": "zmode", "label": "Height", "kind": "segments",
                     "value": o["zmode"],
                     "choices": [("walls", "On the walls"),
                                 ("own", "Its own")],
                     "tip": "On the top of the level's walls, or its eaves "
                            "at a height of their own (a lean-to on "
                            "columns, a porch lower than the house)"})
        if o["zmode"] == "own":
            opts.append({"key": "zh", "label": "Eaves at", "kind": "len",
                         "value": o["zh"], "min": 0.5, "max": 50.0,
                         "step": 0.05,
                         "tip": "Its eaves' height over the level's floor "
                                "(a Shed: its low edge)"})
        if kind == "gable":
            opts.append({"key": "ridge", "label": "Ridge", "kind": "segments",
                         "value": o["ridge"],
                         "choices": [("long", "Along the long side"),
                                     ("short", "Along the short side")],
                         "tip": "Which way the ridge runs"})
        if kind == "shed" or hidden and int(o["slopes"]) == 1:
            opts.append({"key": "fall", "label": "Falls to", "kind": "segments",
                         "value": o["fall"],
                         "choices": [("right", "This side"),
                                     ("left", "The other side")],
                         "tip": "Which long side is the low one"})
        if hidden:
            opts.append({"key": "gutter", "label": "Gutter", "kind": "len",
                         "value": o["gutter"], "min": 0.10, "max": 1.0,
                         "step": 0.05, "tip": "The gutter's width, along "
                                              "the low side"})
        if flat or hidden and not o["pauto"]:
            opts.append({"key": "parapet", "label": "Parapet", "kind": "len",
                         "value": o["parapet"], "min": 0.0, "max": 3.0,
                         "step": 0.05, "tip": "Its height over the roof "
                                              "(0 = none)" if flat else
                         "Its height over the walls' top"})
        return opts

    @staticmethod
    def _roof_kind_slope(changes: dict, before: dict) -> dict:
        """A roof turned hidden starts at 10° (sheets); turned back from
        hidden, at 30° (tiles) — unless the slope is set with it."""
        k = changes.get("kind")
        if k is None or "slope" in changes or k == before.get("kind"):
            return changes
        if k == "hidden":
            return dict(changes, slope=10.0)
        if before.get("kind") == "hidden" and k != "flat":
            return dict(changes, slope=30.0)
        return changes

    # ---- Documentation: drawings on the host's sheets ---------------------------------
    def _doc_paper(self) -> str:
        from . import docs
        if self.doc_opts["paper"] in docs.PAPERS:
            return self.doc_opts["paper"]
        p = (self.doc().get("project") or {}).get("paper", "A3")
        return docs.host_paper(p)

    def _sheet_options(self) -> list[dict]:
        o = self.doc_opts
        return [{"key": "act", "label": "", "kind": "icons", "value": None,
                 "choices": SHEET_ACTIONS},
                {"key": "paper", "label": "Paper", "kind": "segments",
                 "value": self._doc_paper(),
                 "choices": [(p, p) for p in ("A1", "A2", "A3", "A4")],
                 "tip": "The sheets' paper (landscape)"},
                {"key": "scale", "label": "Scale", "kind": "segments",
                 "value": o["scale"],
                 # feet / inches: the architect's scales (1/4" = 1'-0")
                 "choices": [("auto", "Auto")] + (
                     [("24", '1/2"'), ("48", '1/4"'), ("64", '3/16"'),
                      ("96", '1/8"')] if compat.imperial() else
                     [("50", "1:50"), ("75", "1:75"), ("100", "1:100"),
                      ("125", "1:125"), ("200", "1:200")]),
                 "tip": "Auto: the largest that holds the building on the "
                        "paper — one for the plans, one for the elevations "
                        "and sections"},
                {"key": "cut", "label": "Cut", "kind": "len",
                 "value": o["cut"], "min": 0.3, "max": 3.0, "step": 0.05,
                 "tip": "Where the plans are cut, from each level's floor"},
                {"key": "dims", "label": "Dimensions", "kind": "segments",
                 "value": o["dims"],
                 "choices": [("yes", "Outside"), ("no", "None")],
                 "tip": "On the plans, round the walls: a chain through "
                        "the openings and the overall size, on each side "
                        "(they follow the model)"},
                {"key": "elev", "label": "Elevations", "kind": "segments",
                 "value": o["elev"],
                 "choices": [("yes", "Four"), ("no", "None")]},
                {"key": "sect", "label": "Sections", "kind": "segments",
                 "value": o["sect"],
                 "choices": [("yes", "A-A and B-B"), ("no", "None")]}]

    def _on_doc_option(self, key: str, value) -> None:
        if key == "act":
            QTimer.singleShot(0, lambda: self.doc_action(value))
            QTimer.singleShot(0, self._refill_options)   # nothing stays lit
            return
        self.doc_opts[key] = value

    # ---- Import / export (the hub's menu) and walls from a DXF ------------------------
    def set_grid_snap(self, on: bool) -> None:
        from . import prefs
        prefs.put("grid_snap", bool(on))
        if on and not prefs.get("plan_grid"):
            prefs.put("plan_grid", True)     # a pull to a grid you see
        self.viewport.update()
        compat.flash(self.viewport, "Snap to the plan grid: "
                     + ("ON — in the plan view" if on else "off"), 3000)

    def io_action(self, key: str) -> None:
        self.hub.close_sub()
        if key == "import_dxf":
            QTimer.singleShot(0, self.import_dxf)
        elif key == "pdf":
            QTimer.singleShot(0, self.export_pdf)
        elif key == "dxf":
            QTimer.singleShot(0, self.export_dxf)
        elif key == "quantities":
            QTimer.singleShot(0, self.export_quantities)

    def _underlay(self, doc: dict | None = None):
        doc = doc or self.doc()
        _i, lv, _z = self._work_level()
        return lv, (doc.get("underlays") or {}).get(lv["id"])

    def _dxf_options(self) -> list[dict]:
        _lv, u = self._underlay()
        opts = [{"key": "act", "label": "", "kind": "icons", "value": None,
                 "choices": DXF_ACTIONS}]
        if u:
            opts.append({"key": "layer", "label": "Layer",
                         "kind": "segments", "value": u["layer"],
                         "choices": [("", "All")] + [(n, n)
                                                     for n in u["layers"]],
                         "tip": "The drawing's layer the walls are made "
                                "from (its walls' lines)"})
        opts += [{"key": "tmin", "label": "Min", "kind": "len",
                  "value": self.dxf_opts["tmin"], "min": 0.03, "max": 1.0,
                  "step": 0.01, "tip": "The thinnest wall to find"},
                 {"key": "tmax", "label": "Max", "kind": "len",
                  "value": self.dxf_opts["tmax"], "min": 0.05, "max": 1.5,
                  "step": 0.01, "tip": "The thickest wall to find"}]
        return opts

    def _on_dxf_option(self, key: str, value) -> None:
        if key == "act":
            QTimer.singleShot(0, {"cad": self.import_cad,
                                  "load": self.import_dxf,
                                  "make": self.walls_from_dxf,
                                  "clear": self.clear_dxf}[value])
            QTimer.singleShot(0, self._refill_options)
        elif key == "layer":
            doc = self.doc()
            lv, u = self._underlay(doc)
            if u:
                doc["underlays"][lv["id"]] = dict(u, layer=value)
                self.save(doc)
                self.viewport.update()
        else:
            self.dxf_opts[key] = value

    @_project_first
    def import_cad(self) -> None:
        """«Import CAD»: the plan loaded AND the building made from it, in
        one go (his ask, 2026-10-09 — as the CAD2IngeTrazo does, with our
        project around it). The walls' layer read from its name; none such:
        the drawing stays loaded, the layer to pick in the bar."""
        if self.import_dxf():
            _lv, u = self._underlay(self.doc())
            if u and u["layer"]:
                self.walls_from_dxf()
            else:
                compat.flash(self.viewport, "Loaded — no layer named as "
                             "walls (A-WALL, PAREDE…): pick it in the bar, "
                             "then «Make»", 8000)

    @_project_first
    def import_dxf(self) -> bool:
        """A DXF plan onto the current level, as a reference (one
        Ctrl+Z); the Walls › «Walls from DXF» bar comes up. True: loaded."""
        if self._pro_only("wall_import"):
            return False
        import os

        from PySide6.QtWidgets import QApplication, QFileDialog
        from . import importdxf
        base = compat.document_path(self.window)
        start = os.path.dirname(base) if base else os.path.expanduser("~")
        path, _f = QFileDialog.getOpenFileName(
            self.window, "Import a DXF plan", start, "DXF (*.dxf)")
        if not path:
            return False
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            data = importdxf.placed(importdxf.read(path))
        except Exception as e:  # noqa: BLE001 — say it
            compat.flash(self.viewport, f"DXF not read — {e}", 8000)
            return False
        finally:
            QApplication.restoreOverrideCursor()
        if not data["segs"]:
            compat.flash(self.viewport, "No lines in that DXF", 6000)
            return False
        doc = self.doc()
        lv, _u = self._underlay(doc)
        # the walls' layer read from its name (A-WALL, PAREDE, MURO…)
        layer = next((n for n in data["layers"]
                      if importdxf.role(n) == "wall"), "")
        doc["underlays"] = dict(doc.get("underlays") or {})
        doc["underlays"][lv["id"]] = {"name": os.path.basename(path),
                                      "layers": data["layers"],
                                      "segs": data["segs"], "layer": layer,
                                      "blocks": data.get("blocks") or [],
                                      "texts": data.get("texts") or [],
                                      "loops": data.get("loops") or []}
        self.save(doc)
        self.pick("walls", "wall_import")
        self.enter_plan(quiet=True)
        compat.fit_plan(self.viewport, [(s[0], s[1]) for s in data["segs"]]
                        + [(s[2], s[3]) for s in data["segs"]])
        compat.flash(self.viewport, f"«{os.path.basename(path)}» on "
                     f"«{lv['name']}»: {len(data['segs'])} lines, "
                     f"{len(data['layers'])} layers — «Make walls» raises "
                     "them", 8000)
        return True

    @_project_first
    def walls_from_dxf(self) -> None:
        """The BUILDING from the level's drawing — one Ctrl+Z
        (PLANO_IMPORT_CAD.md): the walls from its double lines, each
        opening a door or a window as the BLOCK in it says (else its
        width), the columns from the columns' outlines, the stairs from
        the stairs' outlines and their treads, the rooms named from the
        texts in them. What each layer holds is read from its name."""
        if self._pro_only("wall_import"):
            return
        from . import importdxf as X
        from . import ramps as R
        from . import spaces
        from . import stairs as ST
        doc = self._live(self.doc())
        lv, u = self._underlay(doc)
        if not u:
            compat.flash(self.viewport, "No drawing on this level — load a "
                         "DXF first", 6000)
            return
        li = u["layers"].index(u["layer"]) if u["layer"] else None
        segs = [s for s in u["segs"] if li is None or s[4] == li]
        walls, ops = X.walls_from(segs, self.dxf_opts["tmin"],
                                  self.dxf_opts["tmax"])
        if not walls:
            compat.flash(self.viewport, "No walls found — no pairs of "
                         "parallel lines between Min and Max (try another "
                         "layer)", 7000)
            return
        recs = [{"kind": "line", "a": [round(a[0], 4), round(a[1], 4)],
                 "b": [round(b[0], 4), round(b[1], 4)],
                 "t": round(t * 200) / 200, "align": "centre", "side": 1,
                 "height": "level", "base": 0.0, "level": lv["id"]}
                for a, b, t in walls]
        made = model.new_walls(doc["walls"], recs)
        doc["walls"] = doc["walls"] + made
        orecs = []
        kinds = X.opening_kinds(ops, walls, u.get("blocks") or [])
        for (k, _p, _w), op in zip(ops, kinds):
            door = op["kind"] == "door"
            rec = {"kind": op["kind"], "wall": made[k]["id"],
                   "pos": op["pos"], "w": op["w"],
                   "h": 2.10 if door else 1.20,
                   "sill": 0.0 if door else 1.00, "swing": op["swing"]}
            if door:            # sliding (no swing drawn), opening out
                rec.update(op=op["op"], out=op["out"], leaf=op["leaf"],
                           leaves=2 if op["op"] == "sliding"
                           and op["w"] > 2.2 else 1)
            orecs.append(rec)
        doc["openings"] = doc["openings"] + model.new_openings(
            doc["openings"], orecs)
        # the columns, as drawn (their own sizes, to the slab above)
        cols = [dict(c, level=lv["id"], height="level", base=0.0)
                for c in X.columns(u.get("loops") or [])]
        # the stairs: ours, straight, from this level up to the next one
        # (the highest level: up to its top)
        ids = [r["id"] for r in doc["levels"]]
        i = ids.index(lv["id"])
        to = ids[i + 1] if i + 1 < len(ids) else R.TOP + lv["id"]
        sts = [dict(ST.DEFAULT, type="stair", start="level", level=lv["id"],
                    to=to, x=s["x"], y=s["y"], angle=s["angle"], w=s["w"],
                    tread=s["tread"], fix_tread=True, shape="straight",
                    anchor="centre", **{"from": lv["id"]})
               for s in X.stairs(u.get("loops") or [], u["segs"],
                                 u["layers"], u.get("texts") or [])]
        sts = [s for s in sts if ST.why_not(s) is None]
        # the rooms (for the stairs to fit in, and to be named)
        found = spaces.found([w for w in doc["walls"]
                              if w["level"] == lv["id"]])
        from shapely.geometry import Point
        notes, fitted = [], []
        for s in sts:
            room = next((r["poly"] for r in found
                         if r["poly"].buffer(0.05).contains(
                             Point(s["x"], s["y"]))), None)
            s, note = X.fit_stair(s, room, lambda r: ST.footprints(
                r, doc, model.elevations))
            fitted.append(s)
            if note:
                notes.append(note)
        sts = fitted
        doc["structure"] = doc["structure"] + model.new_elements(
            doc["structure"], cols + sts)
        # the rooms' names, from the texts inside them
        names = X.room_names(u.get("texts") or [], found)
        doc["rooms"] = model._rooms(
            (doc.get("rooms") or []) + [{"level": lv["id"], "x": x, "y": y,
                                         "name": n} for x, y, n in names],
            set(ids))
        self._commit_all(doc)
        nd = sum(1 for o in orecs if o["kind"] == "door")
        compat.flash(self.viewport, f"«{lv['name']}»: {len(made)} walls, "
                     f"{nd} doors, {len(orecs) - nd} windows, {len(cols)} "
                     f"columns, {len(sts)} stairs"
                     + (f" ({sum(s['shape'] != 'straight' for s in sts)} "
                        "turned to fit)" if any(s["shape"] != "straight"
                                                for s in sts) else "")
                     + f", {len(names)} rooms named — Ctrl+Z undoes it all"
                     + (f" · ⚠ a stair {notes[0]}" if notes else ""),
                     12000 if notes else 9000)

    def clear_dxf(self) -> None:
        doc = self.doc()
        lv, u = self._underlay(doc)
        if not u:
            return
        doc["underlays"] = {k: v for k, v in doc["underlays"].items()
                            if k != lv["id"]}
        self.save(doc)
        self.viewport.update()
        compat.flash(self.viewport, "Drawing removed — Ctrl+Z brings it "
                     "back", 5000)

    def _draw_underlay(self, viewport, painter) -> None:
        """The level's imported drawing, thin, over the view (its walls'
        layer darker)."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen
        try:
            doc = self.doc()
            levels = doc["levels"]
            if not 0 <= self.floor < len(levels):
                return
            lv = levels[self.floor]
            u = (doc.get("underlays") or {}).get(lv["id"])
            if not u:
                return
            z = model.elevations(levels, doc["project"]["ground_level"]
                                 if model.has_project(doc) else 0.0)[
                self.floor] + 0.01
            li = u["layers"].index(u["layer"]) if u["layer"] else None
            painter.save()
            painter.setRenderHint(painter.RenderHint.Antialiasing)
            dim = QPen(QColor(120, 150, 190, 150), 1.0)
            main = QPen(QColor(40, 90, 160, 230), 1.4)
            for s in u["segs"]:
                pa = compat.to_pixel(viewport, s[0], s[1], z)
                pb = compat.to_pixel(viewport, s[2], s[3], z)
                if not pa or not pb:
                    continue
                painter.setPen(main if li is None or s[4] == li else dim)
                painter.drawLine(QPointF(*pa), QPointF(*pb))
            painter.restore()
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    # ---- Rooms: found from the walls, named here ------------------------------------
    def _on_room_option(self, key: str, value) -> None:
        if key == "act":
            QTimer.singleShot(0, self.edit_rooms)
            QTimer.singleShot(0, self._refill_options)
        elif key == "labels":
            self.room_labels = value == "yes"
            self.viewport.update()
        else:
            self.doc_opts[key] = value

    def edit_rooms(self) -> None:
        """The current level's rooms in a table: their names. One Ctrl+Z.
        Ticked, the names go to the rooms in the same place on the other
        levels too (typical floors) — never over a name given there."""
        if self._pro_only("rooms"):
            return
        from shapely.geometry import Point

        from . import spaces
        from .dialogs import RoomsDialog
        doc = self._live(self.doc())
        _i, lv, _z = self._work_level()
        rooms = spaces.of_level(doc, lv["id"])
        if not rooms:
            compat.flash(self.viewport, f"No rooms on «{lv['name']}» — "
                         "walls enclose them", 5000)
            return
        walls = [w for w in doc["walls"] if w["level"] == lv["id"]]
        dlg = RoomsDialog(rooms, lv, spaces.gross(walls), self.window)
        if not dlg.exec():
            return
        names, same = dlg.result_data()
        recs = [r for r in doc["rooms"] if r["level"] != lv["id"]]
        # a room named before keeps its record's id: its floor's material
        # (materials «floor:<slab>:<room>») stays with it
        mine = [{"id": (room.get("rec") or {}).get("id", ""),
                 "level": lv["id"], "x": round(room["at"][0], 4),
                 "y": round(room["at"][1], 4), "name": name}
                for room, name in names if name]
        copied = 0
        if same:
            for other in doc["levels"]:
                if other["id"] == lv["id"]:
                    continue
                for room in spaces.of_level(doc, other["id"]):
                    if room["rec"] is not None:
                        continue                 # it has its own name
                    for src, name in names:
                        if name and room["poly"].contains(Point(*src["at"])) \
                                and abs(room["area"] - src["area"]) \
                                <= 0.05 * src["area"]:
                            recs.append({"id": "", "level": other["id"],
                                         "x": round(room["at"][0], 4),
                                         "y": round(room["at"][1], 4),
                                         "name": name})
                            copied += 1
                            break
        doc["rooms"] = model._rooms(recs + mine,
                                    {r["id"] for r in doc["levels"]})
        self.save(doc)
        self.viewport.update()
        compat.flash(self.viewport, f"Rooms of «{lv['name']}» named"
                     + (f" · {copied} on other levels" if copied else "")
                     + " — Ctrl+Z undoes it", 6000)
        self._again(dlg, self.edit_rooms)

    ROOM_TINT = (236, 222, 196, 120)    # a warm floor tone, see-through

    def _plan_level(self, viewport):
        """(doc, level, its floor's z) of the level in the plan — None when
        hidden or none. The doc as it STANDS (``_live``): a wall deleted
        with the host's tools takes its dimensions and room with it at
        once, not at the next rebuild (a customer's report, 2026-10-10)."""
        if getattr(self, "_plan_doc", None) is None:
            self._plan_doc = self._reader(lambda d: d)
        doc = self._plan_doc()
        levels = doc["levels"]
        if not 0 <= self.floor < len(levels):
            return None
        lv = levels[self.floor]
        if not compat.layer_visible(viewport, compat.level_layer(lv["name"])):
            return None
        z = model.elevations(levels, doc["project"]["ground_level"]
                             if model.has_project(doc) else 0.0)[self.floor]
        return doc, lv, z

    def _draw_room_tint(self, viewport, painter) -> None:
        """In the plan: each room's floor in a soft warm tone (his ask,
        2026-10-09: a plan without it reads empty) — under the names."""
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QColor, QPolygonF
        from . import prefs
        from . import spaces
        if not prefs.get("room_tint"):
            return
        try:
            at = self._plan_level(viewport)
            if at is None:
                return
            doc, lv, z = at
            painter.save()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(*self.ROOM_TINT))
            for room in spaces.of_level(doc, lv["id"]):
                pts = [compat.to_pixel(viewport, x, y, z)
                       for x, y in list(room["poly"].exterior.coords)[:-1]]
                if all(pts):
                    painter.drawPolygon(QPolygonF([QPointF(*p)
                                                   for p in pts]))
            painter.restore()
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    def _draw_separators(self, viewport, painter) -> None:
        """The level's ROOM SEPARATORS: dashed, thin (separators.py) — not
        while the Delete tool draws them itself (the one under the mouse
        in red)."""
        from . import separators as SP
        if type(getattr(viewport, "active_tool", None)).__name__ == \
                "SeparatorEraseTool":
            return
        try:
            at = self._plan_level(viewport)
            if at is None:
                return
            doc, lv, z = at
            SP.draw(viewport, painter, SP.of_level(doc, lv["id"]), z)
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    DIM_INK = "#4a5058"
    DIM_GAPS = {"chain": 30, "total": 56}     # px out from the walls

    def _draw_plan_dims(self, viewport, painter) -> None:
        """In the plan: the walls' dimensions on every side — a chain
        through the openings' edges, the overall size further out (the
        sheets' own, ``docs.plan_dims``): they follow the walls as they
        move (his ask, 2026-10-09). Pro (the sheets' module)."""
        import math

        from PySide6.QtCore import QPointF, QRectF, Qt
        from PySide6.QtGui import QColor, QFont, QPen
        from . import prefs
        if not prefs.get("plan_dims") or edition.lite():
            return
        try:
            from . import docs
            at = self._plan_level(viewport)
            if at is None:
                return
            doc, lv, z = at
            dims = docs.plan_dims(doc, lv["id"])
            if not dims:
                return
            out_of = {"south": (0, -1), "north": (0, 1), "west": (-1, 0),
                      "east": (1, 0)}
            painter.save()
            painter.setRenderHint(painter.RenderHint.Antialiasing)
            pen = QPen(QColor(self.DIM_INK), 1.0)
            painter.setPen(pen)
            f = QFont()
            f.setPointSizeF(8.0)
            painter.setFont(f)
            for side, a, b, row in dims:
                pa = compat.to_pixel(viewport, a[0], a[1], z)
                pb = compat.to_pixel(viewport, b[0], b[1], z)
                o = out_of[side]
                po = compat.to_pixel(viewport, a[0] + o[0], a[1] + o[1], z)
                if not (pa and pb and po):
                    continue
                ox, oy = po[0] - pa[0], po[1] - pa[1]
                ol = math.hypot(ox, oy) or 1.0
                ox, oy = ox / ol, oy / ol
                g = self.DIM_GAPS[row]
                A = QPointF(pa[0] + ox * g, pa[1] + oy * g)
                B = QPointF(pb[0] + ox * g, pb[1] + oy * g)
                painter.drawLine(A, B)
                for p, q in ((pa, A), (pb, B)):      # extension lines
                    painter.drawLine(QPointF(p[0] + ox * 6, p[1] + oy * 6),
                                     QPointF(q.x() + ox * 4, q.y() + oy * 4))
                    painter.drawLine(QPointF(q.x() - 4, q.y() + 4),
                                     QPointF(q.x() + 4, q.y() - 4))  # tick
                L = math.dist(a, b)
                mid = QPointF((A.x() + B.x()) / 2, (A.y() + B.y()) / 2)
                painter.save()
                painter.translate(mid)
                if side in ("west", "east"):
                    painter.rotate(-90)
                painter.drawText(QRectF(-40, -15, 80, 13),
                                 int(Qt.AlignHCenter | Qt.AlignBottom),
                                 compat.fmt_num(L))
                painter.restore()
            painter.restore()
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    def _draw_room_labels(self, viewport, painter) -> None:
        """In the plan: each room's name and area at its middle."""
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QFont

        from . import openingtools as OT
        from . import spaces
        if not self.room_labels:
            return
        try:
            at = self._plan_level(viewport)
            if at is None:
                return
            doc, lv, z = at
            painter.save()
            f = QFont()
            f.setPointSizeF(8.5)
            painter.setFont(f)
            painter.setPen(QColor(OT.PLAN_INK))
            for room in spaces.of_level(doc, lv["id"]):
                px = compat.to_pixel(viewport, room["at"][0], room["at"][1],
                                     z)
                if not px:
                    continue
                painter.drawText(QRectF(px[0] - 70, px[1] - 16, 140, 32),
                                 0x0084, spaces.label(room))  # AlignCenter
            painter.restore()
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    def _on_section_option(self, key: str, value) -> None:
        if value == "line":
            QTimer.singleShot(0, self.start_section_tool)
        elif value == "clear":
            QTimer.singleShot(0, self.clear_sections)
        QTimer.singleShot(0, self._refill_options)

    def start_section_tool(self) -> None:
        if self._pro_only("section"):
            return
        from . import doctools
        _i, lv, z0 = self._work_level()
        tool = doctools.SectionLineTool(self._section_drawn,
                                        self._wall_cancelled,
                                        z0 + float(self.doc_opts["cut"]))
        self._activate(tool)
        QTimer.singleShot(0, self._refill_options)       # the line lit
        compat.flash(self.viewport, "Section: click where the line starts",
                     4000)

    def _section_drawn(self, a, b, flip) -> None:
        import uuid as _uuid
        doc = self._live(self.doc())
        sym = model.next_section_symbol(doc["sections"])
        sid = _uuid.uuid4().hex[:8]
        doc["sections"] = doc["sections"] + [
            {"id": sid, "a": [round(v, 4) for v in a],
             "b": [round(v, 4) for v in b], "flip": bool(flip),
             "symbol": sym}]
        # ONLY its own sheet, in the documentation studio's set (the
        # earlier «Make» remade every sheet: the old plans came back
        # beside the new ones) — the line and the sheet in one Ctrl+Z
        from . import hostsheet as HS
        from . import sheetset as SS
        from . import studio
        style = studio.style_of(doc)
        book = SS.the_set(doc, style)
        sheet = next((s for s in book if s["id"] == "section:" + sid), None)
        if sheet is None:
            return
        try:
            HS.make_sheet(self, sheet, studio.style_of(doc, sheet),
                          total=len(book), index=book.index(sheet) + 1,
                          doc=doc)
        except Exception as e:  # noqa: BLE001 — say it, keep going
            compat.flash(self.viewport, f"Section not made — {e}", 8000)
            return
        compat.flash(self.viewport, f"Section {sym}-{sym} and its sheet "
                     f"{sheet['number']} made — Ctrl+Z undoes it", 6000)
        st = getattr(self, "_studio", None)
        if st is not None:
            try:
                st.reload(sheet["id"])
                st.show()
                st.raise_()
            except RuntimeError:
                pass
        self._sheets_panel_sync()

    # ---- section lines in the plan: picked, moved, flipped (sections.py) ----------
    def _sec_on(self) -> bool:
        """Section lines pickable: shown (``_sec_shown``) and the host's
        Select tool out."""
        return self._sec_shown() and compat.selecting(self.viewport)

    def _sec_shown(self) -> bool:
        """Section lines drawn: the Documentation phase, the plan — any
        level, the Terrain too —, whatever the tool (Orbit, Pan… — they
        went with any tool but Select, his find 24/10) (Pro)."""
        return bool(self.alive and self.active and self.plan_on
                    and self.current == "documentation"
                    and not edition.lite())

    def _sec_lines(self, doc: dict | None = None) -> list[dict]:
        """The set's section lines with the studio's flips laid on — kept
        while the model they depend on stays the same (the plan paints
        many times a second)."""
        import json
        from . import sheetset as SS
        from . import studio
        doc = self._live(self.doc()) if doc is None else doc
        recs = SS.records(doc)
        try:
            key = json.dumps([doc.get("walls"), doc.get("sections"),
                              doc.get("levels"), [r.get("flip") for r in
                                                  recs.values()],
                              (doc.get("docs") or {}).get("style")],
                             sort_keys=True, default=str)
        except (TypeError, ValueError):
            key = None
        if key is not None and self._sec_cache[0] == key:
            return self._sec_cache[1]
        out = []
        for ln in SS.section_lines(doc, studio.style_of(doc)):
            rec = recs.get("section:" + ln["id"]) or {}
            out.append(dict(ln, flip=bool(rec.get("flip", ln["flip"]))))
        self._sec_cache = (key, out)
        return out

    def _sec_pick(self, lid) -> None:
        if lid != self._sec_picked:
            self._sec_picked = lid
            if lid is not None:
                compat.select_ids(self.viewport, set())
                compat.flash(self.viewport, "Section line: drag its ends or "
                             "its arrow · the small arrow flips its look · "
                             "double-click = its section · Delete · Esc",
                             5000)
        self.viewport.update()

    def _draw_section_lines(self, viewport, painter) -> None:
        """The section lines in the plan (Documentation): dash-dot, their
        letters and look arrows — the one picked orange (its grips: the
        grips' own drawing)."""
        if not self._sec_shown():
            return
        from . import sections as SC
        try:
            at = self._plan_level(viewport)
            if at is None:
                return
            live = self._sec_live
            SC.draw(viewport, painter,
                    self._sec_lines(live) if live is not None
                    else self._sec_lines(), at[2], self._sec_picked)
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    def _sec_sheet(self, doc: dict, lid: str):
        """(the book, the section's sheet in it) — its sheet made yet?"""
        from . import sheetset as SS
        from . import studio
        book = SS.the_set(doc, studio.style_of(doc))
        sheet = next((s for s in book if s["id"] == "section:" + lid), None)
        return book, sheet

    def _section_store(self, doc: dict, lid: str, note: str) -> None:
        """A section line changed (grips, flip, back to automatic): stored
        and its sheet made again in the same Ctrl+Z (his edits on it kept)
        — a sheet never made: only the line."""
        from . import hostsheet as HS
        from . import studio
        book, sheet = self._sec_sheet(doc, lid)
        try:
            if sheet is not None and sheet["state"] != "none":
                HS.make_sheet(self, sheet, studio.style_of(doc, sheet),
                              total=len(book), index=book.index(sheet) + 1,
                              doc=doc)
            else:
                self._commit_all(doc)
        except Exception as e:  # noqa: BLE001 — say it, keep going
            compat.flash(self.viewport, f"Section not made — {e}", 8000)
            return
        compat.flash(self.viewport, f"{note} — Ctrl+Z undoes it", 4000)
        st = getattr(self, "_studio", None)
        if st is not None and sheet is not None:
            try:
                st.reload(sheet["id"])
            except RuntimeError:
                pass
        self._sheets_panel_sync()
        self.viewport.update()

    def _section_flip(self, lid: str) -> None:
        """The picked line's look turned round (= the studio's Flip)."""
        doc = self._live(self.doc())
        _b, sheet = self._sec_sheet(doc, lid)
        if sheet is None:
            return
        flip = not bool(sheet["line"].get("flip"))
        recs = doc.setdefault("docs", {}).setdefault("sheets", [])
        rec = next((r for r in recs if r.get("id") == sheet["id"]), None)
        if rec is None:
            recs.append({"id": sheet["id"], "flip": flip})
        else:
            rec["flip"] = flip
        sym = sheet["line"]["symbol"]
        self._section_store(doc, lid, f"Section {sym}-{sym}: looking the "
                                      "other way")

    # ---- the section seen in 3D (his call, 24/10: no button — the line
    # picked IS the cut; it stays while he works, Esc takes it off) -------
    def _cut3d_from_pick(self) -> None:
        """Out of the plan with a section line picked (Documentation): the
        building cut there in 3D — the sheet's own cut — until Esc, the
        plan again or another phase."""
        lid = self._sec_picked
        if not (lid and self.alive and self.active and not self.plan_on
                and self.current == "documentation" and not edition.lite()):
            return
        try:
            self._cut3d_on(lid)
        except Exception:  # noqa: BLE001 — a view nicety, never in the way
            compat.log_error("3D cut")

    def _cut3d_on(self, lid: str) -> None:
        import copy

        from PySide6.QtGui import QVector3D

        from core.section import SectionPlane

        from . import hostsheet as HS
        from . import studio
        self._cut3d_off(quiet=True)
        doc = self._live(self.doc())
        book, sheet = self._sec_sheet(doc, lid)
        if sheet is None:
            return
        built = HS.engine(sheet).make(copy.deepcopy(doc), model.elevations,
                                      sheet, studio.style_of(doc, sheet),
                                      total=len(book),
                                      index=book.index(sheet) + 1)
        cut = (built.get("view") or {}).get("plane")
        if not cut:
            return
        # (a plane of its own, the sheet's cut worked out again: the one
        # stored with the sheet may be out of date; out of the undo
        # history, gone with the cut)
        sc = self.viewport.scene
        plane = SectionPlane(QVector3D(*cut["point"]),
                             QVector3D(*cut["normal"]),
                             name=HS.MARK + "3D cut", symbol=cut["symbol"])
        prev = sc.active_section()
        shown = bool(getattr(sc, "show_section_planes", False))
        sc.section_planes.append(plane)
        sc.set_active_section(plane)
        if shown:
            compat.show_section_planes(self.viewport, False)
        self._cut3d = (sc, plane, prev, shown)
        self.viewport.update()
        s = cut["symbol"]
        compat.flash(self.viewport, f"{s}-{s} · Cut in 3D — Esc removes it",
                     6000)

    def _cut3d_off(self, quiet: bool = False) -> None:
        c = getattr(self, "_cut3d", None)
        if c is None:
            return
        self._cut3d = None
        sc, plane, prev, shown = c
        if sc is not self.viewport.scene:
            return                           # (another file: gone with it)
        act = sc.active_section()
        sc.section_planes[:] = [p for p in sc.section_planes
                                if p is not plane]
        if act is plane or act is None:
            sc.set_active_section(prev if any(
                p is prev for p in sc.section_planes) else None)
        if shown:
            compat.show_section_planes(self.viewport, True)
        self.viewport.update()
        if not quiet:
            compat.flash(self.viewport, "3D cut off", 2500)

    def _section_unfreeze(self, lid: str) -> None:
        """A-A / B-B moved by hand back to the building's middle."""
        from . import sections as SC
        doc = SC.unfreeze(self._live(self.doc()), lid)
        self._section_store(doc, lid, f"Section {lid}-{lid} back to "
                                      "automatic")

    def _section_delete_picked(self) -> None:
        """Delete with a section line picked: a drawn one goes with its
        sheet (asked first); A-A / B-B are made — hidden in the style."""
        from PySide6.QtWidgets import QMessageBox
        lid = self._sec_picked
        if lid is None:
            return
        doc = self._live(self.doc())
        _b, sheet = self._sec_sheet(doc, lid)
        if sheet is None:
            return
        sym = sheet["line"]["symbol"]
        if sheet["line"].get("auto"):
            compat.flash(self.viewport, f"{sym}-{sym} is made by ArchXQ — "
                         "hide it in the studio's style (Sheet ▸ Show)", 6000)
            return
        ok = QMessageBox.question(
            self.window, tr("Delete"),
            tr("Delete the section line {s}-{s} and its sheet {n}?",
               s=sym, n=sheet["number"]))
        if ok != QMessageBox.Yes:
            return
        self._sec_picked = None
        self.delete_section(sheet)

    def clear_sections(self) -> None:
        doc = self._live(self.doc())
        n = len(doc["sections"])
        if not n:
            compat.flash(self.viewport, "No sections drawn", 4000)
            return
        # each with its sheet (the studio's set — not the earlier «Make»)
        from . import sheetset as SS
        from . import studio
        for s in SS.sections(doc, studio.style_of(doc)):
            if not s["line"]["auto"]:
                self.delete_section(s)

    def delete_section(self, sheet: dict) -> None:
        """A drawn section line out — with its sheet (one Ctrl+Z)."""
        from . import hostsheet as HS
        doc = self._live(self.doc())
        lid = sheet["id"].split(":", 1)[1]
        doc["sections"] = [s for s in doc["sections"] if s["id"] != lid]
        HS.remove_sheet(self, sheet, doc)
        sym = (sheet.get("line") or {}).get("symbol", "")
        compat.flash(self.viewport, f"Section {sym}-{sym} and its sheet "
                     "removed — Ctrl+Z brings them back", 6000)
        self._sheets_panel_sync()

    def make_sheets(self, doc: dict | None = None,
                    quiet: bool = False) -> bool:
        """Make every drawing and sheet again (with ``doc``: store it in
        the same Ctrl+Z — a section line drawn / removed)."""
        if self._pro_only("sheets"):
            return False
        from . import docs
        store = None if doc is None else (self.app.key, doc)
        doc = self._live(self.doc()) if doc is None else doc
        opts = dict(self.doc_opts, paper=self._doc_paper())
        try:
            planes, views, sheets = docs.make(doc, model.elevations, opts)
        except Exception as e:  # noqa: BLE001 — say it, keep going
            compat.flash(self.viewport, f"Sheets not made — {e}", 8000)
            return False
        if not sheets:
            compat.flash(self.viewport, "No walls yet — nothing to draw", 5000)
            return False
        made, replaced = docs.commit(self.viewport, planes, views, sheets,
                                     store)
        docs.refresh_sheets(self.window)
        if not quiet:
            compat.flash(self.viewport, f"{made} sheets made"
                         + (f" (in place of {replaced})" if replaced else "")
                         + " — «Open the sheets» to see them · Ctrl+Z "
                         "undoes it", 7000)
        return True

    def _sheets_panel_sync(self) -> None:
        """The right strip's list of sheets — in the Documentation phase
        only (made the first time it is needed)."""
        show = bool(self.active and self.current == "documentation"
                    and not edition.lite())
        p = getattr(self, "_sheets_panel", None)
        if p is None:
            if not show:
                return
            from .studio import SheetsPanel
            p = self._sheets_panel = SheetsPanel(self)
            self._split.insertWidget(0, p)
        p.setVisible(show)
        if show:
            try:
                p.fill()
            except Exception:  # noqa: BLE001 — a list is never fatal
                pass

    def doc_studio(self, what: str = "studio", sheet_id=None) -> None:
        """The Documentation studio (its own window), or every sheet of
        the set brought up to date."""
        from . import studio
        if what == "update_all":
            n = studio.update_all(self)
            compat.flash(self.viewport, f"{n} sheets updated" if n else
                         "Every sheet is up to date", 5000)
            st = getattr(self, "_studio", None)
            if st is not None:
                try:
                    st.reload()
                except RuntimeError:
                    pass
            self._sheets_panel_sync()
            return
        studio.open_studio(self, sheet_id)

    def doc_action(self, what: str) -> None:
        if self._pro_only("sheets"):
            return
        from . import docs
        win = self.window
        if what == "make":
            self.make_sheets()
            return
        if what == "open":
            sc = self.viewport.scene
            first = next((i for i, c in enumerate(sc.compositions)
                          if docs.is_ours(c)), 0)
            docs.open_sheets(win, first)
        elif what == "pdf":
            self.export_pdf()
        elif what == "dxf":
            self.export_dxf()

    def export_dxf(self) -> None:
        if self._pro_only("export"):
            return
        import os

        from PySide6.QtCore import Qt as _Qt
        from PySide6.QtWidgets import QApplication, QFileDialog
        from . import docs, docsdxf
        sc = self.viewport.scene
        if not any(docs.is_ours(c) and c.frames for c in sc.compositions):
            compat.flash(self.viewport, "No drawings yet — make them first "
                         "(Documentation › Drawings & sheets)", 6000)
            return
        base = compat.document_path(self.window)
        start = os.path.dirname(base) if base else os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self.window, "Export the drawings to DXF — a folder", start)
        if not folder:
            return
        QApplication.setOverrideCursor(_Qt.WaitCursor)
        try:
            res = docsdxf.export_all(self.window, self._live(self.doc()),
                                     model.elevations, folder,
                                     dict(self.doc_opts,
                                          paper=self._doc_paper()))
        except Exception as e:  # noqa: BLE001 — say it
            compat.flash(self.viewport, f"DXF not written — {e}", 8000)
            return
        finally:
            QApplication.restoreOverrideCursor()
        compat.flash(self.viewport, f"{len(res)} DXF files written to "
                     f"{folder}", 8000)

    def export_pdf(self) -> None:
        if self._pro_only("export"):
            return
        import os

        from PySide6.QtWidgets import QFileDialog
        from . import docs
        if not self.viewport.scene.compositions:
            compat.flash(self.viewport, "No sheets yet — make them first "
                         "(Documentation › Drawings & sheets)", 6000)
            return
        win = self.window
        base = compat.document_path(win)
        name = (self.doc().get("project") or {}).get("name") or "ArchXQ"
        start = os.path.join(os.path.dirname(str(base)) if base else
                             os.path.expanduser("~"),
                             "".join(ch for ch in name if ch not in
                                     '\\/:*?"<>|') + ".pdf")
        path, _f = QFileDialog.getSaveFileName(win, "Export sheets to PDF",
                                               start, "PDF (*.pdf)")
        if not path:
            return
        bad = docs.export_pdf(win, path)
        compat.flash(self.viewport, f"PDF written: {path}"
                     + (f" — could not draw: {', '.join(bad)}" if bad
                        else ""), 8000)

    def export_quantities(self) -> None:
        """The building's take-off to a CSV (quantities.py — 0.15.0, D1):
        walls by type and layer, openings, slabs, structure, roofs, rooms,
        earth — next to the document, named after the project."""
        if self._pro_only("export"):
            return
        import os

        from PySide6.QtWidgets import QFileDialog
        from . import quantities as Q
        doc = self.doc()
        win = self.window
        base = compat.document_path(win)
        name = (doc.get("project") or {}).get("name") or "ArchXQ"
        start = os.path.join(os.path.dirname(str(base)) if base else
                             os.path.expanduser("~"),
                             "".join(ch for ch in name if ch not in
                                     '\\/:*?"<>|') + " - "
                             + tr("quantities") + ".csv")
        path, _f = QFileDialog.getSaveFileName(
            win, tr("Export quantities (CSV)"), start, "CSV (*.csv)")
        if not path:
            return
        try:
            vols = compat.dig_volumes(doc)
        except Exception:  # noqa: BLE001 — each excavation's own then
            vols = None
        try:
            n = Q.write(path, Q.take_off(doc, model.elevations, vols),
                        compat.imperial())
        except OSError as e:          # open in Excel, say: it can't write
            compat.flash(self.viewport, tr("Could not write the file — is "
                                           "it open in another program?")
                         + f" ({e.strerror})", 8000)
            return
        compat.flash(self.viewport, tr("Quantities written ({n} rows): {p}",
                                       n=n, p=path), 8000)

    def _on_struct_option(self, element: str, key: str, value) -> None:
        if element == "roof" and key == "kind":
            # as its library card: the slope that suits it, and the roofs
            # selected take it (their outline made a rectangle if pitched)
            self.library_pick("roof", {"kind": value})
            return
        o = self._struct_opts(element)
        o[key] = value
        if key in ("section", "height", "kind", "by", "slopes", "pauto",
                   "zmode", "ftype") or (
                key == "shape" and element in ("column", "slab",
                                               "footing")):
            QTimer.singleShot(0, self._refill_options)   # fields come / go
        if key == "hole_by":                 # a slab opening, drawn anew
            QTimer.singleShot(0, lambda: self.start_struct_tool("slab"))
            return
        # columns SELECTED take it (below); else the row just placed
        # follows its bar — live (his ask, 2026-10-03)
        picked = self._lib_picked()[0] == element
        if element == "column" and key in ("count", "spacing", "ends", "by",
                                           "w", "d", "angle", "section",
                                           "anchor", "base", "fit",
                                           "align") \
                and self._last_row is not None and not picked:
            QTimer.singleShot(0, lambda k=key: self._redo_last_row(k))
        # (a row of footings just drawn follows its bar the same way)
        if element == "footing" and key in ("ftype", "by", "count",
                                            "spacing", "ends", "align", "w",
                                            "sw", "d", "pd") \
                and self._last_row is not None \
                and self._last_row.get("what") == "footings" \
                and (not picked or self._picked_in_last_row()):
            QTimer.singleShot(0, lambda k=key: self._redo_last_row(k))
        self._bar_to_selected(element, key, value)
        if key == "shape":
            self._last_row = None
            if (element, value) in STRUCT_ACTIONS:
                QTimer.singleShot(0, lambda: self.struct_action(element,
                                                                value))
            else:
                QTimer.singleShot(0, lambda: self.start_struct_tool(element))

    # ---- The LIBRARY (the right strip, library.py) --------------------------------------
    def _lib_opts(self, key: str | None) -> dict | None:
        """The options the library of ``key`` reads and sets — the ones the
        options bar and the tool use."""
        return {"door": self.op_opts["door"], "window": self.op_opts["window"],
                "wall": self.wall_opts, "column": self.col_opts,
                "beam": self.beam_opts, "slab": self.slab_opts,
                "stair": self.bstair_opts,
                "ramp": self.bramp_opts, "roof": self.roof_opts,
                "guard": self.guard_opts,
                "glazing": self.glazing_opts,
                "street": self.street_opts,
                "profile": self.profile_opts,
                "copy": self.copy_opts}.get(key)

    def _recall_opts(self) -> None:
        """Each element's options as the last session left them — changed
        IN PLACE (tools and bars hold these very dicts)."""
        from . import lastopts as LO

        def put(target: dict, got: dict) -> None:
            for k, v in got.items():
                if isinstance(target.get(k), dict) and isinstance(v, dict):
                    put(target[k], v)
                else:
                    target[k] = v
        for name in LO.NAMES:
            opts = getattr(self, name, None)
            saved = LO.load(name)
            if isinstance(opts, dict) and saved:
                put(opts, LO.merge(opts, saved))
        self._opts_kept = self._opts_now()

    def _opts_now(self) -> dict:
        from . import lastopts as LO
        return {n: LO.kept(getattr(self, n)) for n in LO.NAMES
                if isinstance(getattr(self, n, None), dict)}

    def _remember_opts(self) -> None:
        """Kept for the next session — only what changed since."""
        from . import lastopts as LO
        try:
            now = self._opts_now()
            old = self._opts_kept or {}
            for name, d in now.items():
                if d != old.get(name):
                    LO.save(name, d)
            self._opts_kept = now
        except Exception:  # noqa: BLE001 — not kept: the session goes on
            pass

    def _lib_picked(self) -> tuple[str | None, list[str]]:
        """(their library key, ids) of the ArchXQ elements selected — when
        they are all of one kind."""
        keys, ids = set(), []
        for g in compat.selected_groups(self.viewport):
            r = compat._rec(g)
            k = compat.kind_of(g)
            if k == "opening":
                k = r.get("okind")
            if not k or not r.get("id"):
                continue
            keys.add(k)
            ids.append(r["id"])
        return (keys.pop(), ids) if len(keys) == 1 else (None, [])

    #: the openings one becomes the other from the library (window ↔ door)
    CROSS = ("door", "window")

    def _lib_cross(self, sel_key, ids) -> bool:
        """Openings of one kind selected and the OTHER kind picked in the
        top bar since (Door with a window selected): the library is the
        picked kind's, and changes them into it. Selected after the pick,
        the selection's own library is back."""
        return (bool(ids) and sel_key in self.CROSS
                and self.element in self.CROSS and self.element != sel_key
                and self.tool_element() is None
                and set(ids) == getattr(self, "_sel_at_phase", None))

    def _converted(self, r: dict, key: str, ch: dict, doc: dict) -> dict:
        """Opening ``r`` (a window / a door) made a ``key`` in its place:
        its wall, place, width and HEAD kept (a window's top is a door's;
        a door made a window takes the windows' sill under the same head),
        the kind's current type and the card's changes on top; a shop
        window's front carried to a shopfront door. Its id kept (it stays
        selected), a name of its new kind."""
        from .shopfront import DEFAULTS as SHOP
        new = {k: v for k, v in self.op_opts[key].items() if k != "shape"}
        for k in ("wall", "pos", "w", "id", "swing"):
            if k in r:
                new[k] = r[k]
        for k in SHOP:
            if k in r:
                new[k] = r[k]
        head = float(r.get("sill", 0.0)) + float(r["h"])
        if key == "door":
            new["sill"], new["h"] = 0.0, head
        else:
            sill = float(self.op_opts["window"].get("sill", 1.0))
            if head - sill < 0.3:
                sill = max(head - float(self.op_opts["window"]["h"]), 0.0)
            new["sill"], new["h"] = sill, head - sill
        new.update(ch)
        new["kind"] = key
        others = [o for o in doc["openings"] if o["id"] != r["id"]]
        new["name"] = model.new_openings(others, [new])[0]["name"]
        wall_ids = {w["id"] for w in doc["walls"]}
        clean = model._openings([new], wall_ids)
        return clean[0] if clean else r

    def _convert_openings(self, key: str, ids: list, changes: dict) -> None:
        """The selected windows made doors (or doors windows) — one Ctrl+Z;
        one that would not fit its wall stays as it was, and says why."""
        from . import library as LB
        from . import structure as S
        doc = self._live(self.doc())
        ch = dict(LB.rec_changes(key, changes))
        walls = {w["id"]: w for w in doc["walls"]}
        new_ops, n, why = [], 0, None
        for o in doc["openings"]:
            if o["id"] in ids:
                c = self._converted(o, key, ch, doc)
                wall = walls.get(c["wall"])
                bad = None if wall is None else S.opening_room(
                    c, wall, doc["openings"], self._wall_height(wall))
                if wall is None or bad:
                    why = why or bad or "its wall is gone"
                    c = o
                else:
                    n += 1
                o = c
            new_ops.append(o)
        if not n:
            compat.flash(self.viewport, f"Not changed — {why}", 6000)
            return
        doc["openings"] = new_ops
        self._commit_all(doc)
        compat.select_ids(self.viewport, set(ids))
        self._sel_at_phase = set(ids)
        noun = "door" if key == "door" else "window"
        compat.flash(self.viewport, f"{n} made a {noun}"
                     + (f" ({why} for the rest)" if why else "")
                     + " — Ctrl+Z undoes it", 5000)

    def _lib_record(self, rid: str) -> dict | None:
        doc = self.doc()
        return next((r for r in doc["walls"] + doc["structure"]
                     + doc["openings"] if r["id"] == rid), None)

    def _phase_won(self, key, ids, te) -> bool:
        """The selection ``ids`` (of kind ``key``) gives the strip up: it was
        there when a phase, an element or a tool (``te``) was picked, and is
        not what was picked."""
        if set(ids) != getattr(self, "_sel_at_phase", None):
            return False
        return (key in PHASE_OF and PHASE_OF[key] != self.current
                or te is not None and te != key
                or bool(ids) and key not in PHASE_OF and te is None
                and self.element in PHASE_OF)

    def _library_show(self) -> None:
        """The right strip's library: of the elements selected (their type
        marked), else of the tool out, else of the element picked."""
        from . import library as LB
        if not self.alive:
            return
        self._remember_opts()            # a card, a bar: kept for next time
        key, ids = self._lib_picked()
        import time as _t
        if not ids and _t.monotonic() - getattr(self, "_lib_from_strip",
                                               0.0) < 0.6:
            # a strip change being stored: its commit unselects for a moment
            # — another library shown in between made the strip «pulse»
            # (his test, 2026-10-15); the selection comes right back
            QTimer.singleShot(650, self._library_show)
            return
        if not ids and getattr(self, "_sel_at_phase", None):
            self._sel_at_phase = set()   # picked again later: its own library
        # still the selection there was when a phase was picked, and of
        # ANOTHER phase (a slab selected, Roof clicked in the top bar — his
        # test, 2026-10-09): the phase he went to wins; selected after, it
        # is shown again. What sits in no phase (a profile, a stair) gives
        # way too (his screen, 06/11: a profile selected, Openings › Window:
        # the profiles' library stayed).
        # The same for a Building element's tool taken out (a stair still
        # selected, Ramp clicked — his test, 2026-10-09): the tool wins.
        te = self.tool_element()
        opts = None
        if self._lib_cross(key, ids):
            # a window selected, «Door» picked in the top bar (or the other
            # way): the DOORS' library, its cards change the selected window
            # into a door in place (his ask, 2026-10-13: he had to delete the
            # shop window to put a shop door there)
            key = self.element
            opts = dict(self._lib_opts(key) or {})
        elif self._phase_won(key, ids, te):
            key, ids = None, []
        if opts is None and key in LB.CATALOG and ids:
            rec = self._lib_record(ids[0])
            if rec is not None:
                back = {v: k for k, v in LB.REC_KEYS.get(key, {}).items()}
                opts = dict(self._lib_opts(key) or {})
                if key in ("door", "window") and "trim" not in rec:
                    # one with no trim / sill: shown as none (not the next
                    # one's)
                    opts.update(trim="none", sill_k="none")
                if key in ("door", "window"):
                    # nor a handle, a colour, louvres it lacks (openfinish:
                    # an old one is shown as it IS, not as the next one)
                    opts.update(handle="none", hw_c="silver",
                                leaf_c="wood", frame_c="white",
                                louvred=False, pv_panes=0, oshape="rect")
                opts.update({back.get(k, k): v for k, v in rec.items()})
                if key == "profile":             # this one's size (below)
                    opts["pw"], opts["ph"] = rec.get("pw"), rec.get("ph")
                    opts["pts"] = rec.get("pts")
                    opts["halign"] = rec.get("halign") or "outside"
                    opts["valign"] = rec.get("valign") or "bottom"
                if key == "wall":                # none of YOUR types: none
                    opts["wtype"] = rec.get("type") or ""
                if key == "slab":                # a plain slab: neither
                    opts["block"] = bool(rec.get("block"))
                    opts["ceiling"] = bool(rec.get("ceiling"))
                    opts["stype"] = rec.get("stype") or ""
                    opts["layers"] = rec.get("layers") or None
                    opts["frame"] = rec.get("frame") or None
                if key == "street":              # as it was made
                    opts["how"] = "plot" if rec.get("edges") else "axis"
                    opts["align"] = rec.get("align") or "centre"
                if key == "glazing" and rec.get("place") != "free":
                    # its Opening's sizes, on its own bars
                    o, _w = self._glazing_void_of(self.doc(), rec)
                    if o is not None:
                        from . import trim as TR
                        opts.update(op_w=o["w"], op_h=o["h"],
                                    op_sill=o.get("sill", 0.0),
                                    **TR.host_opts(o))   # its trim, sill
        if opts is None and not ids and self._void_picked \
                and self.tool_element() is None:
            # an empty Opening (or a slab's) picked: it has no library — none
            # shown, never the next wall's (his call, 2026-10-28: «the
            # library showing another object makes no sense»)
            key = None
        elif opts is None:
            ids = []
            key = self.tool_element() or self._held_library() or self.element
            opts = self._lib_opts(key)
        if key == "profile" and opts is not None:
            # none of its own: the bars show the size it comes with
            opts = dict(opts)
            nat = PF.size(opts.get("profile")) \
                if PF.known(opts.get("profile")) else (0.10, 0.10)
            opts["pw"] = opts.get("pw") or nat[0]
            opts["ph"] = opts.get("ph") or nat[1]
        locked = edition.lite() and is_pro(key)
        self._bar_from_selected()
        lib = self.props.library
        # rebuilt, the strip kept where it was scrolled to (his test,
        # 2026-10-15: it jumped back to the top at every chip and bar)
        # — per library, kept from the user's OWN scrolling only: a commit
        # unselects for a moment (a shorter library in between) and the
        # mark taken then was cut short — the strip «pulsed» (his test,
        # 2026-10-15). And the SAME library with the same parts in sight
        # (a bar let go, a chip of the same look) is not rebuilt at all.
        sb = self._lib_box.verticalScrollBar()
        marks = self.__dict__.setdefault("_lib_scroll", {})
        if not getattr(self, "_lib_sb_hooked", False):
            self._lib_sb_hooked = True

            def scrolled(v):
                if not getattr(self, "_lib_restoring", False) \
                        and self.props.library.key is not None:
                    marks[self.props.library.key] = v
            sb.valueChanged.connect(scrolled)
        shelf = LB.CATALOG.get(key)
        look = None
        if shelf is not None and opts is not None:
            try:
                look = (key, len(ids), tuple(ids), locked,
                        LB.current_type(shelf, opts),
                        tuple(p.key for p in shelf.parts
                              if p.show is None or p.show(opts)),
                        tuple(sorted((k, repr(v)) for k, v in opts.items()
                                     if not isinstance(v, (int, float))
                                     or isinstance(v, bool))))
            except Exception:  # noqa: BLE001 — rebuild then
                look = None
            # a MOVE bar goes back to 0 after it is let go: always rebuilt
            try:
                dyn = self.library_dyn(key, opts) or ()
            except Exception:  # noqa: BLE001
                dyn = ()
            if any(p.key in ("_along", "_across", "_fill") for p in dyn):
                look = None
            elif look is not None:
                look = look + (tuple((p.key, p.size) for p in dyn),)
            if look is not None and key in ("wall", "slab"):
                # YOUR types too: one deleted by its trash (not the marked
                # one) changes nothing else — its card stayed (2026-10-28)
                look = look + (tuple(
                    (t["id"], t["name"], t["t"], len(t["layers"]))
                    for t in self.doc().get(self.TYPE_KIND[key]["types"])
                    or ()),)
        fields = self._lib_fields(key, ids)
        # its numbers too — unless the change came from the strip itself
        # (a bar let go shows its value already); a number changed in a
        # window (Apply) must show here
        nums = None if opts is None else tuple(sorted(
            (k, round(float(v), 6)) for k, v in opts.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)))
        import time as _t
        # (for a moment: the commit's own re-shows come one after another)
        from_strip = _t.monotonic() - getattr(self, "_lib_from_strip", 0.0) \
            < 0.6
        same = (look is not None and look == getattr(self, "_lib_look", None)
                and lib.key == key and fields[1] == lib.fields_ident
                and (from_strip or nums == getattr(self, "_lib_nums", None)))
        self._lib_look = look
        self._lib_nums = nums
        if not same:
            self._lib_restoring = True
            try:
                lib.show_for(key, opts, locked, len(ids))
                lib.set_fields(*fields)
                at = marks.get(key, 0)
                sb.setValue(at)
            finally:
                self._lib_restoring = False
            if marks.get(key, 0):
                def again(at=marks.get(key, 0)):
                    self._lib_restoring = True
                    try:
                        sb.setValue(at)
                    finally:
                        self._lib_restoring = False
                QTimer.singleShot(0, again)
        self._lib_more(lib, ids)
        shown = lib.key is not None
        self._lib_box.setVisible(shown)              # on top of the strip
        self.props.form_host.setVisible(not shown)   # the prototype's form
        # the strip is the library's own while a tool DRAWS (his screen,
        # 2026-10-09: the doors' library shared it, a gap under it) and for
        # a Building element; picked from the outliner, the outliner stays
        # and for elements picked IN THE MODEL (his call, 2026-10-10: the
        # library's bars need the room; «Sizes & details…» has the rest) —
        # picked in the outliner, the outliner stays under the click
        only = shown and (lib.key in LB.BUILDING_ELEMENTS
                          or not ids and self.tool_element() == lib.key
                          or not ids and self._held_library() == lib.key
                          or bool(ids) and set(ids) != getattr(
                              self, "_sel_by_outliner", None))
        self._library_only(only)
        if shown and not only:
            QTimer.singleShot(0, self._fit_library)

    def _lib_more(self, lib, ids) -> None:
        """One selected: the library's link «Select all … on this level
        (14)» — the batch edit found without a right-click (L1, Kamen #68).
        Several, or none: no link."""
        lib.set_more(None)
        if len(ids) != 1:
            return
        try:
            picks = self._select_picks(ids[0])
            rec = self._lib_record(ids[0])
            every = set(self._same_kind(rec, self.doc())) if rec else set()
        except Exception:  # noqa: BLE001 — the library works without it
            return
        level = [p for p in picks if set(p[1]) != every]
        pick = max(level or picks, key=lambda p: len(p[1]), default=None)
        if pick is not None:
            lib.set_more(pick[0], lambda s=pick[1]: self.select_these(s))

    def _fit_library(self) -> None:
        """The library gets the height it needs (up to 82 % of the strip):
        the outliner moves down — its last chips were hidden under it
        (his screen, 2026-10-08; at 70 % a door's «Along the wall» bar was,
        2026-10-10). The outliner keeps 100 px at least."""
        if not self.alive or not self._lib_box.isVisible() \
                or getattr(self, "_lib_only", False):
            return
        sizes = self._split.sizes()
        total = sum(sizes)
        if total <= 0:
            return
        # its cards just rebuilt count only once Qt has shown them (queued):
        # measured before, «Your types» was left out and the outliner came
        # up over the card clicked (his screen, 2026-10-26)
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtWidgets import QWidget
        for c in self.props.library.findChildren(QWidget):
            QCoreApplication.sendPostedEvents(c, QEvent.MetaCall)
        need = self.props.library.sizeHint().height() + 12
        lib = min(need, int(total * 0.82))
        props = min(sizes[2], max(total - lib - 100, 60))
        out = max(total - lib - props, 0)
        if abs(sizes[0] - lib) > 4:
            self._split.setSizes([lib, out, props])

    def _library_only(self, on: bool) -> None:
        """The strip ALL the library's (his call, 2026-10-09); gone, the
        outliner and the panel come back as they were. Not for a selection
        made in the outliner: it must not vanish under the click."""
        if on == getattr(self, "_lib_only", False):
            return
        if on:
            self._split_before = self._split.sizes()
        self.outliner.setVisible(not on)
        self.props.setVisible(not on)
        self._lib_only = on
        before = getattr(self, "_split_before", None)
        if not on and before:
            QTimer.singleShot(0, lambda: self._split.setSizes(before))

    def library_live(self, key: str, changes: dict) -> None:
        """A library slider DRAGGED («Open»): the selected doors redrawn as
        it goes — their groups only, no undo step, nothing stored; let go,
        ``library_pick`` stores it (one Ctrl+Z)."""
        from . import structure as S
        from . import walls as W
        if any(k.startswith("tl:") for k in changes):
            # a type's layer: the selected wall live, every wall of the type
            # when let go (L2 — his rule, 2026-10-31)
            self._type_layer_live(key, changes)
            return
        moves = {k: v for k, v in changes.items() if k in self.MOVE_KEYS}
        sizes = {k: v for k, v in changes.items() if k not in self.MOVE_KEYS}
        tool = getattr(self.viewport, "active_tool", None)
        if isinstance(getattr(tool, "rec", None), dict) \
                and self.tool_element() == key and sizes:
            tool.rec.update(sizes)       # a stair / ramp being placed
            self.viewport.update()
        sel_key, ids = self._lib_picked()
        if sel_key != key or not ids or edition.lite() and is_pro(key):
            return
        doc = self.doc()
        walls = {w["id"]: w for w in doc["walls"]}
        ops = {o["id"]: o for o in doc["openings"]}
        flights = {e["id"]: e for e in doc["structure"]
                   if e.get("type") in ("stair", "ramp")}
        info = S.levels_info(doc, model.elevations)
        if key == "wall":                # walls moved across: live
            self._walls_live(doc, ids, moves)
            return
        # the walls the openings are in: their holes follow too (a door
        # slid along showed its frame moving, its hole staying behind)
        moved_ops = [dict(o, **changes) for o in doc["openings"]
                     if o["id"] in ids] if set(changes) & {
                         "w", "h", "sill", "pos"} else []
        built = {}                       # wall id → its wall_parts (made once)
        if moved_ops:
            by_id = {o["id"]: o for o in moved_ops}
            all_ops = [by_id.get(o["id"], o) for o in doc["openings"]]
            hosts = {o["wall"] for o in moved_ops}
            # every host wall at once — and its openings' parts read from
            # it below (they were made a second time: 0.15.0, C2)
            built = S.walls_live(doc, model.elevations, hosts, all_ops,
                                 self._live_ctx)
            for g in self.viewport.scene.groups:
                rec = compat._rec(g)
                if compat.kind_of(g) != "wall" or rec.get("id") not in hosts:
                    continue
                made = built.get(rec["id"])
                if made and made[0]:
                    self._live_meshes.setdefault(g, g.mesh)
                    g.mesh = compat.mesh_of(made[0])
        # glass grids, low walls and roofs: their bars live too (his test,
        # 2026-10-15: nothing moved while dragging — «as if held back»)
        extras = {e["id"]: e for e in doc["structure"]
                  if e.get("type") in ("glazing", "guard", "roof", "profile")}
        for g in compat.selected_groups(self.viewport):
            rid = compat._rec(g).get("id")
            faces = None
            if rid in extras:
                r = dict(extras[rid], **sizes)
                if S.why_not(r) is None:
                    if r["type"] == "glazing":
                        from . import glazing as GZ
                        d2 = doc
                        opc = {{"op_w": "w", "op_h": "h", "op_sill": "sill"}[k]:
                               float(v) for k, v in sizes.items()
                               if k in ("op_w", "op_h", "op_sill")}
                        if opc and r.get("op"):
                            # its Opening resized: the wall's hole live too
                            ops2 = [dict(o, **opc) if o["id"] == r["op"]
                                    else o for o in doc["openings"]]
                            d2 = dict(doc, openings=ops2)
                            o2 = next((o for o in ops2
                                       if o["id"] == r["op"]), None)
                            for gw in self.viewport.scene.groups:
                                if compat.kind_of(gw) == "wall" and o2 and \
                                        compat._rec(gw).get("id") == o2["wall"]:
                                    made = S.wall_live(d2, model.elevations,
                                                       o2["wall"], ops2)
                                    if made and made[0]:
                                        self._live_meshes.setdefault(
                                            gw, gw.mesh)
                                        gw.mesh = compat.mesh_of(made[0])
                        faces = GZ.faces(r, d2, lambda l_: info[l_]["z0"]
                                         if l_ in info else 0.0)
                    else:
                        d2 = dict(doc, structure=[r if x["id"] == rid else x
                                                  for x in doc["structure"]])
                        faces = S.elements_live(d2, model.elevations,
                                                {rid}).get(rid)
            elif rid in flights:        # a size / move bar of a stair / ramp
                r = self._moved(dict(flights[rid], **sizes), moves)
                if S.why_not(r) is None:
                    if r["type"] == "stair":
                        from . import stairs as ST
                        faces = ST.faces(r, doc, model.elevations)
                    else:
                        from . import ramps as R
                        faces = R.faces(r, doc, model.elevations)
            else:
                o = ops.get(rid)
                w = walls.get(o["wall"]) if o else None
                if w is None or w["level"] not in info:
                    continue
                made = built.get(w["id"])
                if made:
                    faces = next((p for op, p in made[1]
                                  if op["id"] == rid), None)
                else:
                    faces = S.opening_live(doc, model.elevations,
                                           dict(o, **changes),
                                           moved_ops and all_ops or None)
            if not faces:
                continue
            self._live_meshes.setdefault(g, g.mesh)   # put back before storing
            g.mesh = compat.mesh_of(faces)
        compat.touch_scene(self.viewport)

    @staticmethod
    def _bay_fill(doc: dict, op_id: str) -> dict:
        """{pos, w} of an opening made as wide as the stretch of wall it
        stands in (pier to pier — a shopfront), clear of its wall's ends
        and of the other openings there."""
        from . import structure as S
        o = next((x for x in doc["openings"] if x["id"] == op_id), None)
        w = next((x for x in doc["walls"] if o and x["id"] == o["wall"]),
                 None)
        if o is None or w is None:
            return {}
        b0, b1 = S.opening_span(doc, w, float(o["pos"]))
        pos = float(o["pos"])
        for p in doc["openings"]:            # never over a neighbour
            if p["id"] == op_id or p["wall"] != o["wall"]:
                continue
            e0 = float(p["pos"]) - float(p["w"]) / 2 - 0.05
            e1 = float(p["pos"]) + float(p["w"]) / 2 + 0.05
            if e1 <= pos:
                b0 = max(b0, e1)
            elif e0 >= pos:
                b1 = min(b1, e0)
        if b1 - b0 < 0.5:
            return {}
        return {"pos": round((b0 + b1) / 2, 4), "w": round(b1 - b0, 4)}

    def _walls_shifted(self, doc: dict, ids, moves: dict):
        """(doc, notes) with the selected walls moved by «_across» — the
        walls joined to them stretched (wallmove.py)."""
        from . import wallmove
        dist = float(moves.get("_across", 0.0) or 0.0)
        if not dist:
            return doc, []
        shifts = {w["id"]: wallmove.across(w, dist) for w in doc["walls"]
                  if w["id"] in ids and w.get("kind", "line") == "line"}
        return wallmove.move(doc, shifts)

    def _walls_live(self, doc: dict, ids, moves: dict) -> None:
        """The «Move across» bar dragged: the walls it moves and stretches
        redrawn as it goes, their doors and windows too — no undo step,
        nothing stored (``library_pick`` stores it, one Ctrl+Z)."""
        from . import structure as S
        from . import walls as W
        new, _notes = self._walls_shifted(doc, ids, moves)
        old = {w["id"]: w for w in doc["walls"]}
        changed = {w["id"] for w in new["walls"] if w != old.get(w["id"])}
        nops = {o["id"]: o for o in new.get("openings") or []}
        nwalls = {w["id"]: w for w in new["walls"]}
        info = S.levels_info(new, model.elevations)
        for g in self.viewport.scene.groups:
            rec, k = compat._rec(g), compat.kind_of(g)
            faces = None
            if k == "wall" and rec.get("id") in changed:
                made = S.wall_live(new, model.elevations, rec["id"],
                                   new.get("openings") or [])
                faces = made[0] if made else None
            elif k == "opening" and rec.get("id") in nops \
                    and nops[rec["id"]]["wall"] in changed:
                o = nops[rec["id"]]
                faces = S.opening_live(new, model.elevations, o)
            if faces:
                self._live_meshes.setdefault(g, g.mesh)
                g.mesh = compat.mesh_of(faces)
        compat.touch_scene(self.viewport)

    #: a move bar's keys: not options of the next one drawn — what the
    #: SELECTED ones are moved by («_along» / «_across»: a flight's own way)
    MOVE_KEYS = ("pos", "_along", "_across", "_fill")

    def library_dyn(self, key: str, opts: dict) -> tuple:
        """The library's bars for the SELECTION (his ask, 2026-10-10: move
        in real time from the library): one opening → «Along the wall»
        (its edge from the wall's start; double click: centred); stairs /
        ramps → «Move along» / «Move across» their own way, from 0."""
        from . import library as LB
        from . import structure as S
        from . import walls as W
        opt = LB.TYPE_OPT.get(key)
        if opt and opts.get(opt) and key in self.TYPE_KIND:
            # one of YOUR types: its layers' bars — dragged, EVERY wall /
            # slab of the type changes (0.15.0, A2: the global edit)
            ty = next((t for t in self.doc().get(f"{key}_types") or []
                       if t["id"] == opts[opt]), None)
            if ty is None:
                return ()
            every = "Every «{n}» wall follows" if key == "wall" \
                else "Every «{n}» slab follows"
            return tuple(
                LB._size("tl:" + la["id"],
                         # (a core called «Core»: not «Core · core»)
                         tr("Core") if la["role"] == "core" and (
                             la.get("name") or "Core") == "Core" else
                         (la.get("name") or tr("Finish"))
                         + (" · " + tr("core") if la["role"] == "core" else ""),
                         0.005 if la["role"] != "core" else 0.02,
                         0.60, 0.005, float(la["t"]),
                         (0.01, 0.02, 0.03, 0.05, 0.10, 0.15, 0.19, 0.20),
                         tip=tr(every, n=ty["name"]))
                for la in ty["layers"])
        sel_key, ids = self._lib_picked()
        if sel_key != key or not ids:
            return ()
        doc = self.doc()
        if key in ("door", "window", "void") and len(ids) == 1:
            o = next((x for x in doc["openings"] if x["id"] == ids[0]), None)
            w = next((x for x in doc["walls"] if o and x["id"] == o["wall"]),
                     None)
            if o is None or w is None or w.get("kind", "line") != "line":
                return ()
            ow = float(o["w"])
            # the stretch of wall it stands in — its room's, corner face to
            # corner face (a wall's line may run past several rooms): finer
            # on the bar, and its double click centres it THERE; END_GAP
            # off each face (0.15.0, S.opening_span)
            b0, b1 = S.wall_bay(doc, w, float(o["pos"]))
            lo = S.END_GAP                                # shown: from b0
            hi = b1 - S.END_GAP - b0 - ow
            if hi - lo < 0.02:
                return ()
            mid = min(max((b1 - b0 - ow) / 2, lo), hi)
            fill = ()
            if o.get("op") == "shop":           # a shopfront: pier to pier
                fill = (LB.Part("_fill", "Its bay", (("go", "Fill the bay"),),
                                tip="Pier to pier: as wide as the stretch "
                                "of wall it stands in"),)
            return fill + (LB.Part("pos", "Along the wall", (), None, "size",
                            (round(lo, 3), round(hi, 3), 0.01,
                             round(mid, 3)), (round(mid, 3),), "m", (),
                            -ow / 2 - b0, "Its edge from the corner's face. "
                            "Drag: it slides along its wall, the hole with "
                            "it — it stops at the next opening. Shift = cm "
                            "by cm. Double click: centred between the "
                            "corners"),)
        if key == "wall":
            ws = [w for w in doc["walls"] if w["id"] in ids]
            if not ws or any(w.get("kind", "line") != "line" for w in ws):
                return ()
            return (LB.Part("_across", "Move across", (), None, "size",
                            (-1.0, 1.0, 0.05, 0.0), (0.0,), "m", (), 0.0,
                            "Drag: the selected walls move across their "
                            "line — the walls joined to them stretch, the "
                            "doors and windows stay in place. Type an "
                            "exact distance (0.011 · 1.1 cm). Let go: the "
                            "bar is back at 0. Shift = cm by cm"),)
        if key in ("stair", "ramp"):
            tip = ("Drag: the selected ones move {} their own way — let go, "
                   "they stay and the bar is back at 0. Shift = cm by cm")
            return (LB.Part("_along", "Move along", (), None, "size",
                            (-1.0, 1.0, 0.05, 0.0), (0.0,), "m", (), 0.0,
                            tip.format("along")),
                    LB.Part("_across", "Move across", (), None, "size",
                            (-1.0, 1.0, 0.05, 0.0), (0.0,), "m", (), 0.0,
                            tip.format("across")))
        return ()

    @staticmethod
    def _moved(rec: dict, moves: dict) -> dict:
        """A flight's record moved by «_along» / «_across» (its own way)."""
        from . import ramps as R
        al = float(moves.get("_along", 0.0) or 0.0)
        ac = float(moves.get("_across", 0.0) or 0.0)
        if not (al or ac):
            return rec
        _s, u, n = R.axes(rec)
        return dict(rec, x=round(float(rec["x"]) + u[0] * al + n[0] * ac, 4),
                    y=round(float(rec["y"]) + u[1] * al + n[1] * ac, 4))

    @staticmethod
    def _same_place(was: dict, rec: dict) -> dict:
        """A flight given another «Insert at» stays where it is: only the
        point it is held by moves (its first edge's start kept)."""
        from . import ramps as R
        (sx, sy), _u, n = R.axes(was)
        k = {"left": 0.5, "right": -0.5}.get(rec.get("anchor"), 0.0) \
            * float(rec.get("w", 0.0))
        return dict(rec, x=round(sx - n[0] * k, 4), y=round(sy - n[1] * k, 4))

    def library_fit(self, key: str, option: str, value: float) -> float:
        """A size bar's value, as far as the SELECTED openings can take it:
        never past their wall's room (another opening, its ends, its top)
        — the bar stops there instead of a refusal after (prevent the
        error, his rule)."""
        from . import structure as S
        if key == "guard" and option in ("wall_h", "h"):
            # a low wall under a railing: 10 cm at least, 20 cm under its
            # top — the bar stops there instead of a refusal after
            sel_key, ids = self._lib_picked()
            recs = [e for e in self.doc()["structure"] if e["id"] in ids
                    and e.get("kind") == "wallrail"] \
                if sel_key == key else ([self.guard_opts]
                                        if self.guard_opts.get("kind")
                                        == "wallrail" else [])
            if not recs:
                return value
            if option == "wall_h":
                hi = min(float(e.get("h", 1.10)) - 0.20 for e in recs)
                return round(min(max(value, 0.10), hi), 4)
            lo = max(float(e.get("wall_h", 0.40)) + 0.20 for e in recs)
            return round(max(value, lo), 4)
        if key == "glazing" and option in ("op_w", "op_h", "op_sill"):
            # a grid's Opening: as far as its wall lets it (its ends, the
            # other openings, its top) — as a door's bars
            sel_key, ids = self._lib_picked()
            if sel_key != key or not ids:
                return value
            doc = self.doc()
            ok = {"op_w": "w", "op_h": "h", "op_sill": "sill"}[option]
            walls = {w["id"]: w for w in doc["walls"]}
            best = value
            for e in doc["structure"]:
                if e["id"] not in ids or e.get("place") == "free":
                    continue
                o, w = self._glazing_void_of(doc, e)
                if o is None:
                    continue
                top = self._wall_height(w)
                have = float(o.get(ok, 0.0))
                v = best
                while v > have + 1e-6 and S.opening_room(
                        dict(o, **{ok: round(v, 4)}), w, doc["openings"],
                        top) is not None:
                    v -= 0.01
                best = min(best, max(v, have) if best > have else best)
            return round(best, 4)
        if key == "glazing" and option == "gpos":
            # the glass stops at the frame's back (its bar ran on, nothing
            # moving, past a 5 cm frame — his test, 2026-10-15)
            sel_key, ids = self._lib_picked()
            from . import glazing as GZ
            recs = [e for e in self.doc()["structure"] if e["id"] in ids] \
                if sel_key == key else [self.glazing_opts]
            hi = min((float(GZ.opt(e, "fd")) - float(GZ.opt(e, "gt")) / 2
                      - 0.001 for e in recs), default=value)
            lo = max((float(GZ.opt(e, "gt")) / 2 + 0.001 for e in recs),
                     default=0.0)
            return round(min(max(value, lo), hi), 4)
        if key not in ("door", "window", "void") or option not in (
                "w", "h", "sill", "pos"):
            return value
        sel_key, ids = self._lib_picked()
        if sel_key != key or not ids:
            return value
        doc = self.doc()
        walls = {w["id"]: w for w in doc["walls"]}
        if option == "pos":
            # sliding along: from the place asked back towards where it is
            # (which fits) — it stops against the next opening
            o = next((x for x in doc["openings"] if x["id"] == ids[0]), None)
            w = walls.get(o["wall"]) if o else None
            if w is None:
                return value
            have, half = float(o["pos"]), float(o["w"]) / 2
            lo, hi = S.opening_span(doc, w, have)          # off the corners
            lo, hi = min(lo + half, have), max(hi - half, have)
            # never past a neighbour (it doesn't jump over one either)
            for p in doc["openings"]:
                if p["id"] == o["id"] or p["wall"] != o["wall"]:
                    continue
                room = (float(p["w"]) / 2 + half) + 0.05
                if float(p["pos"]) >= have:
                    hi = min(hi, float(p["pos"]) - room)
                else:
                    lo = max(lo, float(p["pos"]) + room)
            return round(min(max(value, lo), max(hi, lo)), 4)
        best = value
        for o in doc["openings"]:
            if o["id"] not in ids or o["wall"] not in walls:
                continue
            w = walls[o["wall"]]
            top = self._wall_height(w)
            have = float(o.get(option, 0.0))
            v = best
            # from the value asked down to the one it has (which fits)
            while v > have + 1e-6 and S.opening_room(
                    dict(o, **{option: round(v, 4)}), w, doc["openings"],
                    top) is not None:
                v -= 0.01
            best = min(best, max(v, have) if best > have else best)
        return round(best, 4)

    def _live_back(self) -> None:
        """The groups a slider reshaped get their own meshes back (the
        stored rebuild replaces them — and Ctrl+Z must find them as built)."""
        for g, m in self._live_meshes.items():
            g.mesh = m
        self._live_meshes.clear()
        self._live_ctx.clear()            # a drag's joins / drops (C2)

    # ---- The LIVE WINDOW (livewin.py — PLANO_JANELA_AO_VIVO.md, L2) -------------------
    def _layer_eyes(self, dlg, el_id: str) -> None:
        """The EYE on ``dlg``'s layer rows (layerview.py, his OK 02/11): a
        layer hidden in the 3D at once — the type's (every element of it)
        or the element's own; one Ctrl+Z each."""
        if getattr(dlg, "_rows", None) is None:
            return
        from . import layerview as LV
        ui = self

        class _Eyes:
            def __init__(self) -> None:
                self.el_id = el_id

            def hidden(self, who) -> set:
                return LV.hidden(ui.doc(), who)

            def set(self, who, key, off) -> None:
                ui._layer_eye_commit(dlg, LV.set_key(
                    ui._live(ui.doc()), who, key, off))

            def show_all(self, who) -> None:
                ui._layer_eye_commit(dlg, LV.show_all(ui._live(ui.doc()),
                                                      who))
        dlg.layer_eye = _Eyes()
        dlg._build_rows()

    def _layer_eye_commit(self, dlg, doc: dict) -> None:
        """An eye clicked: rebuilt, one Ctrl+Z — the window's own changes
        not stored yet drawn again over it (livewin)."""
        self._live_back()
        self._commit_all(doc)
        live = getattr(dlg, "_axq_live", None)
        if live is not None:
            live.shown = None

    def _live_window(self, dlg, kind: str) -> None:
        """``dlg`` (a wall's / an opening's window) shows its element live:
        ONLY it — the others selected, the other walls of its type, on OK
        (his rule, 2026-10-31: live must stay fast)."""
        from . import livewin

        def read():
            _a, rec = dlg.result_data()
            tab = getattr(dlg, "_mat_tab", None)
            return rec, (tab.change() if tab is not None else None)

        def back() -> None:
            if self._live_meshes:
                self._live_back()
                compat.touch_scene(self.viewport)
        draw = {"wall": self._live_wall_rec,
                "profile": self._live_profile_rec}.get(
                    kind, self._live_opening_rec)
        try:
            livewin.Live(dlg, read, draw, back)
        except Exception:  # noqa: BLE001 — the window works without it
            import traceback
            traceback.print_exc()

    #: from this many elements «to all of them» shows its bar
    BUSY_FROM = 2

    def _busy_commit(self, doc: dict, n: int, text: str) -> None:
        """``_commit_all`` of a change that goes to ``n`` elements — a small
        bar while it works when they are many (his ask, 2026-10-31)."""
        if n < self.BUSY_FROM:
            self._commit_all(doc)
            return
        from . import livewin
        with livewin.busy(self.window, tr("Applying — {what}…",
                                          what=tr(text, n=n))):
            self._commit_all(doc)

    def _live_put(self, eid: str, kind: str, faces, doc: dict) -> None:
        """Element ``eid``'s groups shown as ``faces`` (painted with
        ``doc``'s materials) — their meshes as built kept to put back."""
        from . import materials as M
        for g in self.viewport.scene.groups:
            if compat.kind_of(g) != kind or compat._rec(g).get("id") != eid:
                continue
            self._live_meshes.setdefault(g, g.mesh)
            g.mesh = compat.mesh_of(faces)
            try:
                M.paint(self.viewport.scene, g, kind, eid, doc)
            except Exception:  # noqa: BLE001 — the shape matters most
                pass

    def _typed_wall(self, doc: dict, w: dict) -> dict:
        """``w`` with its type's layers, when it has a type and no layers of
        its own (``_commit_all`` builds it so)."""
        types = {t["id"]: t for t in doc.get("wall_types") or []}
        if w.get("type") in types and not w.get("layers") \
                and not w.get("cw"):
            return model.typed(w, types[w["type"]])
        return w

    def _live_wall_rec(self, rec: dict, mat=None) -> None:
        """A wall as its window says, with its doors and windows — the
        joins with its neighbours made again on OK."""
        from . import materials as M
        from . import structure as S
        from . import walls as W
        w = {k: v for k, v in rec.items() if not str(k).startswith("_")}
        if w.get("cw") or W.why_not(w):
            return
        doc = self.doc()
        if not any(x["id"] == w["id"] for x in doc["walls"]):
            return
        w = self._typed_wall(doc, w)
        d2 = dict(doc, walls=[w if x["id"] == w["id"] else x
                              for x in doc["walls"]])
        if mat is not None:
            d2 = M.merge(d2, mat)
        made = S.wall_live(d2, model.elevations, w["id"],
                           d2.get("openings") or [])
        if not made or not made[0]:
            return
        self._live_back()
        self._live_put(w["id"], "wall", made[0], d2)
        for op, parts in made[1]:
            if parts:
                self._live_put(op["id"], "opening", parts, d2)
        compat.touch_scene(self.viewport)

    def _live_profile_rec(self, rec: dict, mat=None) -> None:
        """A profile as its window says."""
        from . import materials as M
        from . import structure as S
        r = {k: v for k, v in rec.items() if not str(k).startswith("_")}
        if S.why_not(r):
            return
        doc = self.doc()
        d2 = dict(doc, structure=[r if x["id"] == r["id"] else x
                                  for x in doc["structure"]])
        if mat is not None:
            d2 = M.merge(d2, mat)
        faces = S.elements_live(d2, model.elevations, {r["id"]}).get(r["id"])
        if not faces:
            return
        self._live_back()
        self._live_put(r["id"], "profile", faces, d2)
        compat.touch_scene(self.viewport)

    def _live_opening_rec(self, o: dict, mat=None) -> None:
        """A door / window / void as its window says, and its wall's hole.
        One that doesn't fit is not shown (OK says why)."""
        from . import materials as M
        from . import structure as S
        doc = self.doc()
        wall = next((w for w in doc["walls"] if w["id"] == o.get("wall")),
                    None)
        if wall is None:
            return
        others = [x for x in doc["openings"] if x["id"] != o["id"]]
        if S.opening_room(o, wall, others, self._wall_height(wall)):
            return
        ops = [o if x["id"] == o["id"] else x for x in doc["openings"]]
        typed = self._typed_wall(doc, wall)
        d2 = dict(doc, openings=ops,
                  walls=[typed if x["id"] == wall["id"] else x
                         for x in doc["walls"]])
        if mat is not None:
            d2 = M.merge(d2, mat)
        made = S.wall_live(d2, model.elevations, wall["id"], ops)
        if not made or not made[0]:
            return
        parts = next((p for op, p in made[1] if op["id"] == o["id"]), None)
        self._live_back()
        self._live_put(wall["id"], "wall", made[0], d2)
        if parts:
            self._live_put(o["id"], "opening", parts, d2)
        compat.touch_scene(self.viewport)

    def _type_layer_live(self, key: str, changes: dict) -> None:
        """A library bar of a wall TYPE's layer dragged: the selected wall of
        the type shows it live (only it — every wall of the type when let
        go, ``library_pick``)."""
        if key != "wall":
            return
        bars = {k[3:]: float(v) for k, v in changes.items()
                if k.startswith("tl:")}
        sel_key, ids = self._lib_picked()
        if not bars or sel_key != "wall" or not ids:
            return
        doc = self.doc()
        w = next((x for x in doc["walls"] if x["id"] in ids and x.get("type")),
                 None)
        ty = next((t for t in doc.get("wall_types") or []
                   if w is not None and t["id"] == w["type"]), None)
        if ty is None:
            return
        ls = [dict(la, t=round(bars[la["id"]], 4)) if la["id"] in bars
              else dict(la) for la in ty["layers"]]
        ty = dict(ty, layers=ls, t=round(sum(la["t"] for la in ls), 4))
        self._live_wall_rec(model.typed(dict(w, layers=None), ty))

    # ---- On-screen GRIPS (grips.py — PLANO_PEGAS.md) ----------------------------------
    def grip_targets(self):
        """(kind, id, [Grip]) of the ONE ArchXQ element selected with the
        host's Select tool — a straight wall, a door / a window — or None."""
        from . import grips as G
        from . import prefs
        from . import structure as S
        vp = self.viewport
        if not (self.alive and self.active and self._selecting()
                and prefs.get("grips")):
            return None
        if self._sec_picked and self._sec_on():   # a section line (plan)
            from . import sections as SC
            at = self._plan_level(vp)
            ln = next((x for x in self._sec_lines(self._grip_read())
                       if x["id"] == self._sec_picked), None)
            if ln is None or at is None:
                return None
            return "section", ln["id"], SC.grips(ln, at[2])
        if self._void_picked:                 # an empty Opening's hole
            return self._void_grips()
        sel = compat.selected_groups(vp)
        if len(sel) != 1 or sel[0].hidden or compat.locked(vp, sel[0]):
            return None                  # (locked: no arrows to pull)
        k, rid = compat.kind_of(sel[0]), compat._rec(sel[0]).get("id")
        if k not in ("wall", "opening", "column", "beam", "slab", "stair",
                     "ramp", "roof", "guard", "glazing", "street") \
                or not rid \
                or edition.lite() and is_pro(k):
            return None
        doc = self._grip_read()
        info = S.levels_info(doc, model.elevations)
        if k == "glazing":                     # a glass grid (glazing.py)
            e = next((x for x in doc["structure"] if x["id"] == rid), None)
            if e is None or e["level"] not in info:
                return None
            if e.get("place") == "free":
                return k, rid, G.glazing_grips(e, info[e["level"]]["z0"])
            # in an Opening: its grips are the OPENING's — it follows
            o, w = self._glazing_void_of(doc, e)
            if o is None or w["level"] not in info:
                return None
            return k, rid, G.opening_grips(o, w, info[w["level"]]["z0"])
        if k == "street":                      # a street (streets.py)
            e = next((x for x in doc["structure"] if x["id"] == rid), None)
            if e is None or e["level"] not in info:
                return None
            from . import streets as SR
            z = info[e["level"]]["z0"] + float(SR.opt(e, "base"))
            return k, rid, SR.grips(e, z, doc.get("plot"))
        if k == "guard":                       # a low wall (guards.py)
            e = next((x for x in doc["structure"] if x["id"] == rid), None)
            if e is None or e["level"] not in info:
                return None
            from . import guards as GD
            z0 = info[e["level"]]["z0"]
            on = GD.opt(e, "on")
            ground = GD.ground_fn(doc) if on in ("ground", "auto") else None
            slabs = GD.slabs_of(doc, e["level"], z0) if on == "auto" else []
            under = info[e["level"]]["under"]
            roofs = GD.roofs_of(doc, e["level"], under, z0) if on == "roof" \
                else []
            foot, _f = GD.support(e, z0, ground, slabs, roofs, under)
            return k, rid, G.guard_grips(e, z0, foot)
        if k in ("stair", "ramp", "roof"):     # phase 2 (2026-10-13)
            e = next((x for x in doc["structure"] if x["id"] == rid), None)
            if e is None or e["level"] not in info:
                return None
            if k == "roof":
                return k, rid, G.roof_grips(e, S.roof_base(
                    e, info[e["level"]]))
            from . import ramps as R
            zs, ze = R.heights(e, doc, model.elevations)
            if k == "stair":
                from . import stairs as ST
                ps = ST.layout(e, zs, ze)
            else:
                ps = R.pieces(e, zs, ze, R.length_of(e, zs, ze))
            return k, rid, G.flight_grips(e, ps, zs, ze)
        if k in ("column", "beam", "slab"):
            e = next((x for x in doc["structure"] if x["id"] == rid), None)
            if e is None or e["level"] not in info:
                return None
            li = info[e["level"]]
            if e.get("auto"):            # an excavation's slab follows it:
                if k != "slab" or not e.get("holes"):    # its openings only
                    return None
                z = li["z0"] + float(e.get("offset", 0.0))
                return k, rid, [g for j, h in enumerate(e["holes"])
                                for g in G.hole_grips(
                                    j, [tuple(p) for p in h], z)]
            if k == "column":
                top = li["under"] if e.get("height", "level") == "level" \
                    else li["z0"] + float(e["height"])
                # its foot as built: down to a pit's floor under it
                bot = li["z0"] + float(e.get("base", 0.0))
                if float(e.get("base", 0.0)) <= 0:
                    gz = S.ground_under(doc, info, e["level"],
                                        S.column_centre(e))
                    if gz is not None:
                        bot = min(bot, gz)
                return k, rid, G.column_grips(e, top, li["z0"], bot)
            if k == "beam":
                return k, rid, G.beam_grips(e, S.beam_top(e, li["z0"], li))
            return k, rid, G.slab_grips(e, li["z0"]
                                        + float(e.get("offset", 0.0)))
        walls = {w["id"]: w for w in doc["walls"]}
        if k == "wall":
            w = walls.get(rid)
            if w is None or w["level"] not in info:
                return None
            return k, rid, G.wall_grips(w, info[w["level"]]["z0"],
                                        self._wall_height(w))
        o = next((x for x in doc["openings"] if x["id"] == rid), None)
        w = walls.get(o["wall"]) if o else None
        if w is None or w["level"] not in info:
            return None
        return k, rid, G.opening_grips(o, w, info[w["level"]]["z0"])

    @staticmethod
    def _glazing_void_of(doc: dict, e: dict):
        """(its Opening, its wall) — a glass grid filling a void; (None,
        None) when gone."""
        o = next((x for x in doc.get("openings") or []
                  if x["id"] == e.get("op")), None)
        w = next((x for x in doc.get("walls") or []
                  if o is not None and x["id"] == o["wall"]), None)
        return (o, w) if w is not None else (None, None)

    def grip_value(self, kind: str, rid: str, grip, v: float):
        """(the document with the grip at ``v``, why not or None)."""
        from . import grips as G
        doc = self._grip_read()
        if kind == "section":
            from . import sections as SC
            ln = next((x for x in self._sec_lines(doc) if x["id"] == rid),
                      None)
            if ln is None:
                return doc, "Gone"
            return SC.changed(doc, ln, grip.key, v)
        if kind == "glazing":
            e = next((x for x in doc["structure"] if x["id"] == rid), None)
            if e is not None and e.get("place") != "free":
                o, w = self._glazing_void_of(doc, e)
                if o is None:
                    return doc, "Its opening is gone"
                return G.opening_changed(doc, o["id"], grip.key, v,
                                         self._wall_height(w))
        if kind in ("column", "beam", "slab", "stair", "ramp", "roof",
                    "guard", "glazing", "street"):
            return G.element_changed(doc, rid, grip.key, v, grip)
        if kind == "opening":
            o = next((x for x in doc["openings"] if x["id"] == rid), None)
            w = next((x for x in doc["walls"] if o and x["id"] == o["wall"]),
                     None)
            if w is None:
                return doc, "Gone"
            return G.opening_changed(doc, rid, grip.key, v,
                                     self._wall_height(w))
        new, why = G.wall_changed(doc, rid, grip.key, v, self._wall_height,
                                  bool(grip.extra.get("carry")))
        if why:
            return doc, why
        old = {w["id"]: w for w in doc["walls"]}
        moved = {w["id"] for w in new["walls"] if w != old.get(w["id"])}
        why = G.fits(new, moved, self._wall_height)
        return (doc, why) if why else (new, None)

    def grip_magnets(self, kind: str, rid: str, grip) -> list:
        """The values a grip sticks to: a wall's end, onto the other
        walls of its level (so it joins them); a door's / window's side,
        centre, top, sill, lined up with the other openings (a dashed
        guide shows it)."""
        from . import grips as G
        from . import structure as S
        if kind == "section":                  # free (a typed value works)
            return []
        doc = self._grip_read()
        if kind in ("stair", "ramp"):          # onto the walls' faces
            e = next((x for x in doc["structure"] if x["id"] == rid), None)
            if e is None:
                return []
            from . import ramps as R
            zs, ze = R.heights(e, doc, model.elevations)
            if kind == "stair":
                from . import stairs as ST
                ps = ST.layout(e, zs, ze)
            else:
                ps = R.pieces(e, zs, ze, R.length_of(e, zs, ze))
            return G.flight_magnets(doc, e, grip.key, grip, ps)
        if kind == "opening":
            info = S.levels_info(doc, model.elevations)
            return G.opening_magnets(doc, {k: v["z0"] for k, v in
                                           info.items()}, rid, grip.key)
        if kind == "slab" and grip.key[:1] == "c":
            # a block's corner up / down: as the whole block's «Top» —
            # onto the floors and the other slabs' tops (how far from it)
            return G.vertical_magnets(doc, kind, rid, "z",
                                      S.levels_info(doc, model.elevations),
                                      grip.p)
        if (kind, grip.key) in (("column", "top"), ("column", "base"),
                                ("beam", "h"), ("slab", "z"), ("slab", "t")):
            # up / down: onto the heights around it
            return G.vertical_magnets(doc, kind, rid, grip.key,
                                      S.levels_info(doc, model.elevations),
                                      grip.p)
        if kind == "column":
            return G.column_magnets(doc, rid, grip.key, grip.p[2])
        if kind == "beam" and grip.key in ("a", "b"):
            return G.beam_end_magnets(doc, rid, grip.key, grip.p[2])
        if kind == "beam":
            return G.beam_magnets(doc, rid, grip.key, grip.p[2])
        if kind == "slab" or (kind == "roof" and grip.key.startswith("s")):
            # (a roof's side: onto the walls' faces, as a slab's side)
            return G.slab_magnets(doc, rid, grip.key, grip.p[2])
        if kind == "guard":
            return G.guard_magnets(doc, rid, grip.key, grip.p[2])
        if kind == "glazing":
            e = next((x for x in doc["structure"] if x["id"] == rid), None)
            if e is not None and e.get("place") != "free":
                o, _w = self._glazing_void_of(doc, e)
                if o is None:
                    return []
                info = S.levels_info(doc, model.elevations)
                return G.opening_magnets(doc, {k: v["z0"] for k, v in
                                               info.items()}, o["id"],
                                         grip.key)
            return []
        if kind == "wall" and grip.key in ("h0", "h1", "hp"):
            # its top's arrows: onto the heights around it and the guides
            from . import guidetools as GT
            return G.wall_top_magnets(
                doc, rid, grip.key, S.levels_info(doc, model.elevations),
                grip.p, self._wall_height, GT.guides(self.viewport))
        if kind != "wall" or grip.key not in ("a", "b"):
            return []
        return G.end_magnets(doc, rid, grip.key)

    def grip_live(self, new: dict) -> None:
        """A grip dragged: the walls and openings it changes redrawn as it
        goes — their groups only, no undo step, nothing stored."""
        from . import structure as S
        from . import walls as W
        old = self._grip_read()
        if new.get("sections") != old.get("sections") and \
                new.get("walls") == old.get("walls") and \
                new.get("structure") == old.get("structure"):
            # a section line dragged: only the plan's drawing follows
            self._sec_live = new
            self.viewport.update()
            return
        self._live_back()                  # from as built, every step
        ow = {w["id"]: w for w in old["walls"]}
        oo = {o["id"]: o for o in old.get("openings") or []}
        ops = new.get("openings") or []
        nops = {o["id"]: o for o in ops}
        nwalls = {w["id"]: w for w in new["walls"]}
        walls_ch = {i for i, w in nwalls.items() if w != ow.get(i)}
        ops_ch = {i for i, o in nops.items() if o != oo.get(i)}
        hosts = walls_ch | {nops[i]["wall"] for i in ops_ch}
        info = S.levels_info(new, model.elevations)
        built = S.walls_live(new, model.elevations, hosts, ops)
        # columns, beams, slabs a grip changed
        oe = {e["id"]: e for e in old.get("structure") or []}
        els = {e["id"] for e in new.get("structure") or []
               if e != oe.get(e["id"])}
        # a glass grid in an Opening that moved / grew: redrawn with it
        els |= {e["id"] for e in new.get("structure") or []
                if e.get("type") == "glazing" and e.get("op") in ops_ch}
        made_els = S.elements_live(new, model.elevations, els) if els else {}
        for g in self.viewport.scene.groups:
            rec, k = compat._rec(g), compat.kind_of(g)
            rid, faces = rec.get("id"), None
            if rid in made_els:
                faces = made_els[rid]
            elif k == "wall" and rid in hosts:
                made = built.get(rid)
                faces = made[0] if made else None
            elif k == "opening" and rid in nops and (
                    rid in ops_ch or nops[rid]["wall"] in walls_ch):
                o = nops[rid]
                w = nwalls.get(o["wall"])
                if w is None or w["level"] not in info:
                    continue
                faces = S.opening_live(new, model.elevations, o, ops)
            if faces:
                self._live_meshes.setdefault(g, g.mesh)
                g.mesh = compat.mesh_of(faces)
        compat.touch_scene(self.viewport)

    def grip_store(self, doc: dict, kind: str, rid: str, note: str) -> None:
        """A grip let go: stored — one Ctrl+Z; it stays selected."""
        if kind == "section":         # the line and its sheet, one Ctrl+Z
            self._sec_live = None
            self._section_store(doc, rid, note)
            return
        keep = kind == "opening" and rid == self._void_picked
        held = self._void_picked if kind == "slab" and str(
            self._void_picked).startswith(f"{self.HOLE}{rid}:") else None
        self._live_back()
        self._commit_all(doc)
        if held:              # a slab's opening: picked again, not the slab
            self._void_repick(held)
        elif keep:            # (our change dropped the host's pick: again)
            self._void_repick(rid)
        else:
            compat.select_ids(self.viewport, {rid})
        compat.flash(self.viewport, f"{note} — Ctrl+Z undoes it", 3000)
        QTimer.singleShot(0, self._library_show)
        self._outline_soon()

    def grip_delete(self, kind: str, rid: str, key: str, do: bool) -> bool:
        """Delete with the pointer on a grip: a low wall's side → a gap
        there, a gap's edge → the gap closed (grips.guard_deleted). False:
        not one of those — Delete as usual (the whole element). ``do``
        False: only whether it is ours (the shortcut held back)."""
        from . import grips as G
        if kind != "guard":
            return False
        doc = self._grip_read()
        e = next((x for x in doc.get("structure") or []
                  if x["id"] == rid), None)
        if e is None:
            return False
        try:
            r, why = G.guard_deleted(e, key)
        except ImportError:                   # (the Lite has no guards.py)
            return False
        if r is None and why is None:
            return False
        if not do:
            return True
        if why:
            compat.flash(self.viewport, why, 4000)
            return True
        new = dict(doc, structure=[r if x["id"] == rid else x
                                   for x in doc["structure"]])
        self.grip_store(new, kind, rid, "Gap closed" if key[:1] == "g"
                        else "That side opened (a gap)")
        return True

    def grip_back(self) -> None:
        """A grip put back (Esc): as it was built."""
        self._sec_live = None
        self._live_back()
        compat.touch_scene(self.viewport)

    # ---- YOUR wall types (0.15.0, A2) ---------------------------------------------
    #: YOUR types of a kind (walls 0.15.0; slabs: slab layers): the doc's
    #: list, the elements, the record's key, the library's option, and the
    #: words each says
    TYPE_KIND = {
        "wall": {"types": "wall_types", "els": "walls", "rk": "type",
                 "opt": "wtype", "new": "New wall type",
                 "updated": "{n} walls of the type updated",
                 "next": "Type «{t}» made — the next walls are of it",
                 "delete": "Delete the type «{t}»? Its {n} walls keep its "
                           "layers as their own (Ctrl+Z brings it back).",
                 "deleted": "Type «{t}» deleted — its walls keep its layers"},
        "slab": {"types": "slab_types", "els": "structure", "rk": "stype",
                 "opt": "stype", "new": "New slab type",
                 "updated": "{n} slabs of the type updated",
                 "next": "Type «{t}» made — the next slabs are of it",
                 "delete": "Delete the type «{t}»? Its {n} slabs keep its "
                           "layers as their own (Ctrl+Z brings it back).",
                 "deleted": "Type «{t}» deleted — its slabs keep its layers"}}

    def _type_opts(self, key: str) -> dict:
        return self.wall_opts if key == "wall" else self.slab_opts

    def _wall_type_pick(self, changes: dict, key: str = "wall") -> dict | None:
        """The walls' / slabs' library and YOUR types: «+ New type» (named,
        from the one selected or the next one's thickness), a type's card
        (its thickness comes with it), a type layer's bar (that type
        changed: every element of it). None: done here; else the changes to
        go on with."""
        K = self.TYPE_KIND[key]
        rk, opts = K["rk"], self._type_opts(key)
        doc = None
        if changes.get("_types"):
            self._wall_types_act(changes["_types"], key,
                                 changes.get("_tid"))
            return None
        if changes.get("_market") and key == "wall":
            # a market card (markets.py, 2026-11-02): the type put in HIS
            # types the first time (its own Ctrl+Z), then picked as his
            from . import markets as MK
            mk = changes["_market"]
            ty = MK.find(self.doc().get(K["types"]), mk)
            if ty is None:
                doc = self._live(self.doc())
                types = list(doc.get(K["types"]) or [])
                ty = MK.new_type(mk, {t["id"] for t in types})
                if ty is None:
                    return None
                doc[K["types"]] = types + [ty]
                # …with what each layer is made of (the type's look: its
                # walls wear it; changed in a wall's «Material» as ever)
                m = dict(doc.get("materials") or {})
                m["wtype"] = dict(m.get("wtype") or {},
                                  **{ty["id"]: MK.look(mk)})
                doc["materials"] = m
                self._commit_all(doc)
                compat.flash(self.viewport, tr(
                    "«{n}» is one of your types now — edit it as yours",
                    n=ty["name"]) + " — Ctrl+Z undoes it", 6000)
            changes = {K["opt"]: ty["id"]}
        if changes.get("_newtype"):
            # its window (typedlg, 28/10): the name, the layers, the section
            # large — from the one selected, else a core of the next one's
            import uuid
            from .typedlg import TypeDialog
            doc = self._live(self.doc())
            _k, ids = self._lib_picked()
            src = next((e for e in doc[K["els"]] if e["id"] in ids), None)
            t = float(src["t"]) if src else float(opts["t"])
            sty = next((y for y in doc.get(K["types"]) or []
                        if src is not None and y["id"] == src.get(rk)), None)
            ls = [dict(la) for la in (sty or src or {}).get("layers") or []] \
                or [{"id": "core", "name": "", "t": t, "role": "core"}]
            dlg = TypeDialog(key, None, ls, from_sel=src is not None,
                             frame=(sty or src or {}).get("frame"),
                             parent=self.window)
            if not dlg.exec():
                return None
            got = dlg.result()
            name, ls, t = got["name"], got["layers"], got["t"]
            tid = uuid.uuid4().hex[:8]
            doc[K["types"]] = list(doc.get(K["types"]) or []) + [
                {"id": tid, "name": name, "layers": ls, "t": t,
                 "frame": got.get("frame")}]
            if src is not None:          # the one it came from is of it
                doc[K["els"]] = [dict(e, **{rk: tid})
                                 if e["id"] == src["id"] else e
                                 for e in doc[K["els"]]]
            self._commit_all(doc)
            if ids:
                compat.select_ids(self.viewport, set(ids))
            opts.update({K["opt"]: tid, "t": t})
            if key == "wall":
                opts["cw"] = False
            else:
                opts.update(layers=None, ceiling=False, block=False)
            compat.flash(self.viewport, tr(K["next"], t=name)
                         + " — Ctrl+Z undoes it", 6000)
            return None
        bars = {k[3:]: float(v) for k, v in changes.items()
                if k.startswith("tl:")}
        if bars:                         # a type's layer: every one of it
            tid = opts.get(K["opt"]) or ""
            _k, ids = self._lib_picked()
            doc = self._live(self.doc())
            if ids:
                tid = next((e.get(rk) for e in doc[K["els"]]
                            if e["id"] in ids and e.get(rk)), tid)
            types = []
            for ty in doc.get(K["types"]) or []:
                if ty["id"] == tid:
                    ls = [dict(la, t=round(bars[la["id"]], 4))
                          if la["id"] in bars else dict(la)
                          for la in ty["layers"]]
                    ty = dict(ty, layers=ls,
                              t=round(sum(la["t"] for la in ls), 4))
                    opts["t"] = ty["t"]
                types.append(ty)
            doc[K["types"]] = types
            many = sum(1 for e in doc[K["els"]] if e.get(rk) == tid)
            self._busy_commit(doc, many, K["updated"])
            if ids:
                compat.select_ids(self.viewport, set(ids))
            n = sum(1 for e in self.doc()[K["els"]] if e.get(rk) == tid)
            compat.flash(self.viewport, tr(K["updated"], n=n)
                         + " — Ctrl+Z undoes it", 4000)
            return None
        tid = changes.get(K["opt"])
        if tid:                          # a type's card: its thickness too
            ty = next((t for t in self.doc().get(K["types"]) or []
                       if t["id"] == tid), None)
            if ty is not None:
                changes = dict(changes, t=ty["t"])
                if key == "wall":
                    changes["cw"] = False
                else:                    # (the type gives its layers)
                    changes.update(layers=None, ceiling=False, block=False)
        return changes

    #: the file YOUR wall types go to / come from (A4)
    TYPES_EXT = "axqtypes"

    def _wall_types_act(self, act: str, key: str = "wall",
                        tid: str | None = None) -> None:
        """Edit (its window: name + layers) / Duplicate / Delete the type
        marked (or ``tid``: a card's double-click, its trash); Import / Export every type (a small JSON file: «.axqtypes» —
        the walls' AND the slabs', slab layers). One Ctrl+Z each."""
        import json
        import uuid
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        K = self.TYPE_KIND[key]
        rk, opts = K["rk"], self._type_opts(key)
        doc = self._live(self.doc())
        types = [dict(t) for t in doc.get(K["types"]) or []]
        _k, ids = self._lib_picked()
        tid = tid or next((e.get(rk) for e in doc[K["els"]]
                           if e["id"] in ids and e.get(rk)), None) \
            or opts.get(K["opt"]) or ""
        ty = next((t for t in types if t["id"] == tid), None)
        msg = None
        if act == "edit" and ty is not None:
            # the type's window: its name and layers — every element of it
            from .typedlg import TypeDialog
            n = sum(1 for e in doc[K["els"]] if e.get(rk) == tid)
            dlg = TypeDialog(key, ty, None, n=n, parent=self.window)
            self._layer_eyes(dlg, tid)
            if not dlg.exec():
                return
            # (its eyes, clicked while it was open, stay as they were set)
            doc["hidden_layers"] = dict(self.doc().get("hidden_layers")
                                        or {})
            got = dlg.result()
            if (got["name"], got["layers"], got.get("frame")) == (
                    ty["name"], ty["layers"], ty.get("frame")):
                return
            ty.update(got)
            if opts.get(K["opt"]) == tid:
                opts["t"] = got["t"]
            msg = tr(K["updated"], n=n) if n else \
                tr("Type «{t}» saved", t=got["name"])
        elif act == "duplicate" and ty is not None:
            new = dict(ty, id=uuid.uuid4().hex[:8],
                       name=(ty["name"] + " " + tr("copy"))[:40],
                       layers=[dict(la) for la in ty["layers"]])
            types.append(new)
            opts[K["opt"]] = new["id"]
            msg = tr(K["next"], t=new["name"])
        elif act == "delete" and ty is not None:
            n = sum(1 for e in doc[K["els"]] if e.get(rk) == tid)
            if QMessageBox.question(
                    self.window, tr("Delete type"),
                    tr(K["delete"], t=ty["name"], n=n),
                    QMessageBox.Yes | QMessageBox.Cancel,
                    QMessageBox.Cancel) != QMessageBox.Yes:
                return
            types = [t for t in types if t["id"] != tid]
            lay = [dict(la) for la in ty["layers"]]
            doc[K["els"]] = [dict({k: v for k, v in e.items() if k != rk},
                                  layers=[dict(la) for la in lay]
                                  if len(lay) > 1 else None, t=ty["t"],
                                  frame=ty.get("frame"))
                             if e.get(rk) == tid else e
                             for e in doc[K["els"]]]
            if opts.get(K["opt"]) == tid:
                opts[K["opt"]] = ""
            msg = tr(K["deleted"], t=ty["name"])
        elif act == "export" and (doc.get("wall_types")
                                  or doc.get("slab_types")):
            # (one file for both: the walls' and the slabs' types)
            path, _f = QFileDialog.getSaveFileName(
                self.window, tr("Export your types"),
                "types." + self.TYPES_EXT,
                tr("ArchXQ types") + f" (*.{self.TYPES_EXT})")
            if not path:
                return
            walls_t = doc.get("wall_types") or []
            slabs_t = doc.get("slab_types") or []
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"archxq_wall_types": 1, "types": walls_t,
                               "slab_types": slabs_t}, f,
                              ensure_ascii=False, indent=1)
            except OSError as e:
                compat.flash(self.viewport, tr("Not exported — {e}", e=e),
                             6000)
                return
            compat.flash(self.viewport, tr("{n} types exported",
                                           n=len(walls_t) + len(slabs_t)),
                         5000)
            return                       # (nothing in the project changed)
        elif act == "import":
            path, _f = QFileDialog.getOpenFileName(
                self.window, tr("Import types"), "",
                tr("ArchXQ types") + f" (*.{self.TYPES_EXT})")
            if not path:
                return
            try:
                with open(path, encoding="utf-8") as f:
                    raw = json.load(f) or {}
                got_w = model.wall_types(raw.get("types"))
                got_s = model.wall_types(raw.get("slab_types"))
            except (OSError, ValueError, AttributeError) as e:
                compat.flash(self.viewport, tr("Not imported — {e}", e=e),
                             6000)
                return
            doc["wall_types"], nw = model.merge_wall_types(
                [dict(t) for t in doc.get("wall_types") or []], got_w)
            doc["slab_types"], ns = model.merge_wall_types(
                [dict(t) for t in doc.get("slab_types") or []], got_s)
            if not nw + ns:
                compat.flash(self.viewport, tr("Nothing new — those types are "
                                               "here already"), 5000)
                return
            types = doc[K["types"]]
            msg = tr("{n} types imported", n=nw + ns)
        else:
            return
        doc[K["types"]] = types
        self._commit_all(doc)
        if ids:
            compat.select_ids(self.viewport, set(ids))
        compat.flash(self.viewport, msg + " — Ctrl+Z undoes it", 5000)

    def library_pick(self, key: str, changes: dict) -> None:
        """A card / chip clicked: the type for the next ones drawn — and,
        with elements of that kind selected, for them (one Ctrl+Z)."""
        from . import library as LB
        self._live_back()
        if self._pro_only(key):
            return
        # (the strip shows this change already: not rebuilt for it)
        import time as _t
        self._lib_from_strip = _t.monotonic()
        from . import structure as S
        opts = self._lib_opts(key)
        if opts is None:
            return
        if key in ("wall", "slab"):
            changes = self._wall_type_pick(changes, key)
            if changes is None:
                QTimer.singleShot(0, self._library_show)
                return
        if key == "profile" and (changes.get("_newtype")
                                 or changes.get("_types")):
            self._profile_type_act(changes.get("_types") or "new",
                                   changes.get("_tid"))
            QTimer.singleShot(0, self._library_show)
            return
        if key == "slab" and changes.get("block") and "t" not in changes \
                and float(opts.get("t", 0.0)) < 0.30:
            changes = dict(changes, t=1.00)   # a block: 1 m to start
        # a move bar moves the SELECTED ones only — nothing to remember for
        # the next one drawn (the bar is back at 0 after)
        moves = {k: v for k, v in changes.items() if k in self.MOVE_KEYS}
        changes = {k: v for k, v in changes.items()
                   if k not in self.MOVE_KEYS}
        given = changes
        if key == "roof":
            # «L plan»: a card's mark, never a roof's field — on: a hip roof
            # over the level's L at once (nothing selected); another type
            # picked: off again
            lplan = changes.get("lplan")
            if lplan is not None or "kind" in changes:
                opts["lplan"] = bool(lplan)
            changes = given = {k: v for k, v in changes.items()
                               if k != "lplan"}
            if lplan and self._lib_picked()[0] != "roof":
                QTimer.singleShot(0, self._roof_lplan)
            changes = self._roof_kind_slope(changes, opts)
        if key == "glazing" and "kind" in changes:
            # a card: that kind's sizes — for the next one placed AND for
            # the selected ones (his test, 2026-10-15: only its kind changed)
            t = next((t for t in LB.CATALOG["glazing"].types
                      if t.set and t.set.get("kind") == changes["kind"]), None)
            if t is not None and t.init:
                changes = dict(t.init, **changes)
        if key == "window" and "leaves" in changes:
            # another count of leaves: the usual roles for it again (each
            # leaf's own pick belongs to the count it was made for)
            # (a card's own roles and widths win: «Fixed + hinged»)
            changes = dict({k: None for k in LB.ROLE_KEYS}, **changes)
        if key == "window" and changes.get("oshape") not in (None, "rect") \
                and "rise" not in changes:
            # a shape's card: its rise / top width for this width
            changes = dict(LB.shape_changes(changes["oshape"], dict(
                opts, **changes)), **changes)
        if key == "guard" and "kind" in changes:
            # a card: that kind's height (a boundary wall 2 m, a coping)
            t = next((t for t in LB.CATALOG["guard"].types
                      if t.set and t.set.get("kind") == changes["kind"]), None)
            if t is not None and t.init:
                changes = dict(t.init, **changes)
        if key == "street" and "how" in changes:
            # along the plot / by its axis: the next one's — that tool
            opts.update(changes)
            QTimer.singleShot(0, self.start_street)
            QTimer.singleShot(0, self._library_show)
            return
        if key == "profile" and "how" in changes:
            # by room / point by point: the next one's — that tool, at once
            opts.update(changes)
            QTimer.singleShot(0, self.start_profile)
            QTimer.singleShot(0, self._library_show)
            return
        if key == "copy" and "how" in changes:
            opts.update(changes)
            QTimer.singleShot(0, self.start_copy)
            QTimer.singleShot(0, self._library_show)
            return
        if key == "copy" and changes.get("obj") == PF.COPY_MINE:
            # «From the model»: what is selected, taken now — nothing
            # selected: a click on it comes next
            if not self._copy_take_selection():
                QTimer.singleShot(0, self._copy_pick)
                QTimer.singleShot(0, self._library_show)
                return
            if not self.copy_opts.get("src"):    # (too big: it was said)
                QTimer.singleShot(0, self._library_show)
                return
            # (copies selected: they get the object too — never «mine»
            # without it)
            changes = dict(changes, src=self.copy_opts["src"])
        if key == "profile" and "profile" in changes:
            # a card: where that profile sits (a crown under the ceiling, a
            # chair rail 90 cm up)
            t = next((t for t in LB.CATALOG["profile"].types
                      if t.set and t.set.get("profile") == changes["profile"]),
                     None)
            if t is not None and t.init:
                changes = dict(t.init, **changes)
            elif PF.is_user(changes["profile"]):     # one of YOURS
                a, z = PF.anchor_of(changes["profile"])
                changes = dict({"anchor": a} | ({"z": z} if a == "height"
                                                else {}), **changes)
            # … and the size it comes with
            d, h = PF.size(changes["profile"])
            changes = dict(changes, pw=d, ph=h)
        if key == "guard" and changes and set(changes) <= {
                "insert", "how", "gap_w", "gate_kind", "gate_leaves",
                "gate_style", "gate_finish", "gate_open"}:
            # how the next one is MADE (drawn, slab edge, round an opening,
            # a gap): the tool's, nothing to change on one made already
            opts.update(changes)
            if "how" in changes:
                QTimer.singleShot(0, self.start_guard)   # that tool, at once
            elif "insert" in changes and self._lib_picked()[0] == "guard":
                compat.flash(self.viewport, "«The line drawn is its…»: for "
                             "the next low wall you draw — move a drawn one "
                             "with its side grips", 5000)
            QTimer.singleShot(0, self._library_show)
            return
        OPK = {"op_w": "w", "op_h": "h", "op_sill": "sill"}
        from . import trim as TR
        if key == "glazing" and set(changes) & (set(OPK) | set(TR.HOST)):
            # a grid's Opening resized from its bars: the OPENING changes,
            # the grid follows (his ask, 2026-10-15: they go together);
            # its trim and sill are the Opening's too (2026-10-28)
            sel_key, sel_ids = self._lib_picked()
            ch = {OPK[k]: round(float(v), 4) for k, v in changes.items()
                  if k in OPK}
            host = {k: v for k, v in changes.items() if k in TR.HOST}
            if sel_key != "glazing" or not sel_ids:
                if host:                     # the next one's Opening
                    opts.update(host)
                    compat.flash(self.viewport, tr(
                        "Trim and sill: for the next grid drawn along a "
                        "wall (its Opening is made) — an Opening or a "
                        "window there already: select its grid"), 6000)
                    QTimer.singleShot(0, self._library_show)
                return
            doc = self._live(self.doc())
            grids = [e for e in doc["structure"] if e["id"] in sel_ids
                     and e.get("place") != "free"]
            vids = {e.get("op") for e in grids}
            walls = {w["id"]: w for w in doc["walls"]}
            new_ops, bad = [], None
            for o in doc["openings"]:
                if o["id"] in vids:
                    o = TR.on_host(dict(o, **ch), host)
                    w = walls.get(o["wall"])
                    why = None if w is None else S.opening_room(
                        o, w, doc["openings"], self._wall_height(w))
                    bad = bad or why
                new_ops.append(o)
            if bad:
                compat.flash(self.viewport, f"Not changed — {bad}", 5000)
                QTimer.singleShot(0, self._library_show)
                return
            doc["openings"] = new_ops
            self._commit_all(doc)
            compat.select_ids(self.viewport, set(sel_ids))
            QTimer.singleShot(0, self._library_show)
            return
        if key == "glazing" and "place" in changes:
            sel_key, sel_ids = self._lib_picked()
            if sel_key == "glazing" and sel_ids \
                    and self.tool_element() == "glazing":
                # the TOOL is out: «Where» is for the next one drawn — the
                # one just placed (still selected) must not leave its wall
                # (his test, 2026-10-16: «Free» pulled it out, and the tool
                # stayed «In an Opening»: nothing could be drawn)
                compat.select_ids(self.viewport, set())
            elif sel_key == "glazing" and sel_ids:
                # the SELECTED ones move: into an Opening (click it) or out
                # of theirs, free where it was (his test, 2026-10-15: «In an
                # Opening» did nothing on a partition)
                opts.update(changes)
                self._glazing_replace(sel_ids, changes["place"])
                return
        opts.update(changes)
        if key in ("profile", "copy"):       # what a click in a room makes
            QTimer.singleShot(0, self._refresh_profile_targets)
        if key == "glazing" and "place" in changes \
                and self.tool_element() == "glazing":
            # in an Opening ↔ free: the other tool, at once
            QTimer.singleShot(0, self.start_glazing)
        tool = getattr(self.viewport, "active_tool", None)
        if isinstance(getattr(tool, "rec", None), dict) \
                and self.tool_element() == key and changes:
            tool.rec.update(changes)            # a stair / ramp being placed
            self.viewport.update()
        sel_key, ids = self._lib_picked()
        if key == self.element and self._lib_cross(sel_key, ids):
            self._convert_openings(key, ids, changes)   # window ↔ door
        elif sel_key == key and ids:
            ch = dict(LB.rec_changes(key, changes))
            if "pos" in moves:                  # an opening slid along
                ch["pos"] = moves["pos"]
            doc = self._live(self.doc())
            if "_fill" in moves and len(ids) == 1:
                ch.update(self._bay_fill(doc, ids[0]))
            n = 0
            for part in ("walls", "structure", "openings"):
                new = []
                for r in doc[part]:
                    if r["id"] in ids:
                        if r.get("type") == "roof":   # its own slope rule
                            rc = self._roof_kind_slope(given, r)
                            if rc.get("pauto") is False and r.get("pauto",
                                                                  True):
                                # typed from now on: from the height it
                                # had, nothing jumps
                                rc = dict(rc, parapet=S.hidden_height(r))
                            r = dict(r, **rc)
                            r["corners"] = S.roof_corners(r["corners"],
                                                          r["kind"])
                        else:
                            was = r
                            r = dict(r, **ch)
                            if r.get("type") == "street":
                                from . import streets as SR
                                r = SR.kept_ground(was, r)
                            if r.get("type") in ("stair", "ramp"):
                                r = self._moved(r, moves)
                                if "anchor" in ch and ch["anchor"] != \
                                        was.get("anchor", "centre"):
                                    r = self._same_place(was, r)
                        n += 1
                    new.append(r)
                doc[part] = new
            wnotes = []
            if key == "wall" and moves.get("_across"):
                doc, wnotes = self._walls_shifted(doc, ids, moves)
            bad = next((S.why_not(r) for r in doc["structure"]
                        if r["id"] in ids and S.why_not(r)), None)
            if bad:
                compat.flash(self.viewport, f"Not changed — {bad}", 5000)
                n = 0
            if n:
                self._commit_all(doc)
                # the rebuilt ones stay selected: the library keeps editing
                # them (a slider, another chip)
                compat.select_ids(self.viewport, set(ids))
                compat.flash(self.viewport, (" · ".join(wnotes) if wnotes
                                             else f"{n} changed")
                             + " — Ctrl+Z undoes it", 4000)
        elif key == self._held_library() and self.tool_element() != key \
                and ("profile" in changes or "obj" in changes):
            # its tool put away, its library still there: a card takes it
            # out again, ready to draw with that one
            QTimer.singleShot(0, self.start_profile if key == "profile"
                              else self.start_copy)
        elif self.tool_element() != key and key in LB.CATALOG and changes:
            # nothing of it selected: it waits for the next one drawn (he
            # thought the chips did nothing, 2026-10-09)
            noun = LB.CATALOG[key].title.lower()
            compat.flash(self.viewport, f"Set for the next {noun} you draw "
                         f"— select {noun} to change them", 5000)
        if self.options_for is not None:
            QTimer.singleShot(0, self._refill_options)
        QTimer.singleShot(0, self._library_show)

    # ---- Openings: doors, windows, voids -------------------------------------------------
    def _opening_options(self, kind: str) -> list[dict]:
        o = self.op_opts[kind]
        opts = [{"key": "shape", "label": "", "kind": "icons",
                 "value": o["shape"] if self.tool_element() == kind
                 else None, "choices": OPENING_SHAPES[kind]},
                {"key": "w", "label": "Width", "kind": "len",
                 "value": o["w"], "min": 0.2, "max": 20.0, "step": 0.05},
                {"key": "h", "label": "Height", "kind": "len",
                 "value": o["h"], "min": 0.2, "max": 20.0, "step": 0.05}]
        if kind != "door":
            opts.append({"key": "sill", "label": "Sill", "kind": "len",
                         "value": o["sill"], "min": 0.0, "max": 20.0,
                         "step": 0.05, "tip": "Its bottom, from the "
                         "level's floor"})
        else:
            sliding = o.get("op") == "sliding"
            if o.get("op") == "garage":         # sectional / roll-up / tilt
                opts.append({"key": "garage", "label": "Kind",
                             "kind": "segments",
                             "value": o.get("garage", "sectional"),
                             "choices": [("sectional", "Sectional"),
                                         ("rollup", "Roll-up"),
                                         ("tilt", "Up-and-over")],
                             "tip": "The garage door's kind"})
            elif sliding or int(o.get("leaves", 1) or 1) == 1:
                opts.append({"key": "swing",
                             "label": "Slides to" if sliding else "Hinge",
                             "kind": "segments", "value": o["swing"],
                             "choices": [("left", "Left"),
                                         ("right", "Right")],
                             "tip": ("The side it slides to" if sliding else
                                     "Which jamb it hangs on")
                             + " (Tab while placing turns it round)"})
        return opts

    def _on_opening_option(self, kind: str, key: str, value) -> None:
        self.op_opts[kind][key] = value
        if key == "garage":                  # the library's card follows
            QTimer.singleShot(0, self._refill_options)
        if key == "shape":
            QTimer.singleShot(0, lambda: self.start_opening_tool(kind))
        self._bar_to_selected(kind, key, value)

    #: the options bar's fields that are also the RECORD's — changed with
    #: elements of that kind selected, they change those elements, live
    BAR_REC = {"door": ("w", "h", "swing", "garage", "gfinish", "gwin"),
               "window": ("w", "h", "sill"),
               "void": ("w", "h", "sill"), "wall": ("t",),
               "column": ("w", "d", "angle", "height", "h", "base"),
               "beam": ("w", "h", "zmode", "zt"),
               "slab": ("t", "offset"),
               "roof": ("slope", "overhang", "go", "t", "ridge", "fall",
                        "gutter", "parapet", "zmode", "zh")}

    def _bar_from_selected(self) -> None:
        """Elements of one kind selected: the options bar shows THEIR sizes
        (the first one's) — what you change there is what they have (and
        the next one drawn starts from it, as a picked-up setting)."""
        from . import library as LB
        key, ids = self._lib_picked()
        if not ids or key not in self.BAR_REC:
            return
        # while that element is being DRAWN, a selection never changes what
        # is drawn (his recording, 2026-10-14: a run of masonry walls closed
        # on the curtain wall — it got selected, the bar took «curtain», and
        # the whole run came out glass)
        if self.tool_element() == key:
            return
        rec = self._lib_record(ids[0])
        opts = self.op_opts.get(key) if key in self.op_opts else \
            self.wall_opts if key == "wall" else self._struct_opts(key)
        if rec is None or opts is None:
            return
        back = {v: k for k, v in LB.REC_KEYS.get(key, {}).items()}
        keys = set(self.BAR_REC[key]) | {"op", "leaves", "leaf", "open",
                                         "shape", "out", "top"}
        if key in ("door", "window"):       # (04/11/2026, cardpics)
            keys |= {"top_h", "bars_x", "bars_z", "louvred", "garage",
                     *(f"lw{i}" for i in range(1, 7))}
            for k, v in (("top_h", 0.0), ("bars_x", 0), ("bars_z", 0),
                         ("louvred", False),
                         *((f"lw{i}", 0.0) for i in range(1, 7))):
                # (none on the record: none on the card, not the last one's)
                if k not in rec and k in opts and opts[k] != v:
                    opts[k] = v
        if key in ("door", "window", "void"):        # its trim and sill
            from .trim import DEFAULTS as _TRIM
            keys |= set(_TRIM)
        if key == "roof":
            keys |= {"kind", "slopes", "pauto"}
        changed = False
        for rk, v in rec.items():
            ok = back.get(rk, rk)
            if rk in keys and ok in opts and opts[ok] != v \
                    and not (key == "wall" and rk == "shape") \
                    and not (key == "column" and rk == "height"):
                opts[ok] = v
                changed = True
        if key == "window" and "op" not in rec and opts.get("op") != "fixed":
            opts["op"] = "fixed"           # a plain window (no «op» kept)
            changed = True
        if key in ("door", "window") and \
                opts.get("glass", "clear") != rec.get("glass", "clear"):
            opts["glass"] = rec.get("glass", "clear")   # (kept only if opaque)
            changed = True
        if key == "wall" and bool(rec.get("cw")) != bool(opts.get("cw")):
            opts["cw"] = bool(rec.get("cw"))   # a curtain wall or not
            from . import curtain as _CW
            for k in _CW.KEYS:
                if k in rec:
                    opts[k] = rec[k]
            changed = True
        if key == "column":
            # its height: «level» (to the slab) or a number — the bar's
            # «Height» choice + its own field
            h = rec.get("height", "level")
            want = ("level", opts["h"]) if h == "level" else \
                ("custom", float(h))
            if (opts["height"], opts["h"]) != want:
                opts["height"], opts["h"] = want
                changed = True
        if key == "beam" and opts.get("zmode") != rec.get("zmode", "level"):
            opts["zmode"] = rec.get("zmode", "level")   # (older: no key)
            changed = True
        if changed and self.options_for is not None:
            QTimer.singleShot(0, self._refill_options)

    def _bar_to_selected(self, element: str, key: str, value) -> None:
        """A field of the options bar changed with elements of its kind
        selected (his ask, 2026-10-08: as the library does): they take it
        at once — the model rebuilt, still selected; a run of changes to
        the same field of the same ones is ONE Ctrl+Z."""
        from . import structure as S
        if key not in self.BAR_REC.get(element, ()):
            return
        sel_key, ids = self._lib_picked()
        if sel_key != element or not ids:
            return
        rk, rv = key, value
        if element == "column" and key in ("height", "h"):
            # the bar's «Height» (To the slab / Custom) + its field → the
            # record's height: "level" or a number (his ask, 2026-10-09)
            o = self.col_opts
            rk = "height"
            rv = "level" if o["height"] == "level" else float(o["h"])
        # a beam put at its own height takes the bar's «Top at» with it
        extra = {"zt": self.beam_opts["zt"]} \
            if element == "beam" and key == "zmode" and rv == "own" else {}
        doc = self._live(self.doc())
        n = 0
        for part in ("walls", "structure", "openings"):
            new = []
            for r in doc[part]:
                if r["id"] in ids and r.get(rk) != rv:
                    r = dict(r, **{rk: rv}, **extra)
                    n += 1
                new.append(r)
            doc[part] = new
        if not n:
            return
        # an opening must still fit its wall
        walls = {w["id"]: w for w in doc["walls"]}
        for o in doc["openings"]:
            if o["id"] in ids and o["wall"] in walls:
                w = walls[o["wall"]]
                why = S.opening_room(o, w, doc["openings"],
                                     self._wall_height(w))
                if why:
                    compat.flash(self.viewport, f"«{o['name']}»: {why}", 5000)
                    return
        hist = self.viewport.history
        last = getattr(self, "_bar_last", None)
        prev = hist.undo_stack[-1] if hist.undo_stack else None
        self._commit_all(doc)
        if last is not None and last[0] == (frozenset(ids), element, key) \
                and last[1] is prev:
            compat.join_last_steps(hist, prev)        # one step for the run
        self._bar_last = ((frozenset(ids), element, key),
                          hist.undo_stack[-1] if hist.undo_stack else None)
        compat.select_ids(self.viewport, set(ids))

    def _wall_height(self, wall: dict) -> float:
        """How high a wall stands over its level's floor (to the slab
        above, or its own height)."""
        from . import structure as S
        info = S.levels_info(self.doc(), model.elevations).get(wall["level"])
        if info is None:
            return 3.0
        if wall.get("height", "level") == "level":
            return info["under"] - info["z0"]
        return float(wall["height"])

    def _walls_3d_reader(self):
        """() → (the SHOWN walls of every level as the camera's ray sees
        them — place3d.wall_entry —, every level's openings): read again
        when the document changed (``_reader``)."""
        from . import place3d as P3
        from . import structure as S

        def make(doc):
            vp = self.viewport
            shown = {compat._rec(g).get("id") for g in vp.scene.groups
                     if compat.kind_of(g) == "wall" and compat.shown(vp, g)}
            info = S.levels_info(doc, model.elevations)
            names = {lv["id"]: lv["name"] for lv in doc["levels"]}
            out = []
            for w in doc["walls"]:
                li = info.get(w["level"])
                if li is None or w["id"] not in shown:
                    continue
                top = li["under"] if w.get("height", "level") == "level" \
                    else li["z0"] + float(w["height"])
                out.append(P3.wall_entry(w, li["z0"], top, w["level"],
                                         names.get(w["level"], "")))
            return out, list(doc.get("openings") or [])
        return self._reader(make)

    @_project_first
    def start_opening_tool(self, kind: str) -> None:
        if self._pro_only(kind):
            return
        from .openingtools import OpeningTool
        _i, lv, z0 = self._work_level()
        cache = {"v": None, "walls": [], "ops": []}

        def live() -> dict:
            """This level's walls and openings, read again whenever the
            document changed (a door undone / deleted stayed in a copy taken
            when the tool came out: «runs into another opening» on an empty
            wall — his test, 2026-10-10)."""
            import time
            # the scene's version — and at most half a second old anyway
            # (an undo may not touch it; a read is ~1 ms)
            v = getattr(self.viewport.scene, "version", None)
            now = time.monotonic()
            if v is None or v != cache["v"] or now - cache.get("t", 0) > 0.5:
                cache["t"] = now
                doc = self._live(self.doc())
                ws = [w for w in doc["walls"] if w["level"] == lv["id"]]
                ids = {w["id"] for w in ws}
                cache.update(v=v, walls=ws, ops=[o for o in doc["openings"]
                                                if o["wall"] in ids])
            return cache
        live()
        tool = OpeningTool(kind, self._opening_done, self._wall_cancelled, z0,
                           lambda: self.op_opts[kind], lambda: live()["walls"],
                           lambda: live()["ops"], self._wall_height)
        tool.level_id = lv["id"]
        tool._cache = cache
        # in 3D: every level's walls the ray may meet, and their openings
        # to line up with (PLANO_ABERTURAS_3D.md)
        every = self._walls_3d_reader()
        tool.walls_3d = lambda: every()[0]
        tool.openings_3d = lambda: every()[1]
        # Tab / Shift+Tab while placing: the library's chips follow
        tool.on_flip = lambda: QTimer.singleShot(0, self._library_show)
        self.method = "wall"
        self._activate(tool)
        QTimer.singleShot(0, self._refill_options)
        compat.flash(self.viewport, f"{tool.noun}s on «{lv['name']}» — move "
                     "along a wall", 3000)

    def _opening_done(self, rec: dict) -> None:
        doc = self._live(self.doc())
        made = model.new_openings(doc["openings"], [rec])
        doc["openings"] = doc["openings"] + made
        self._commit_all(doc)
        tool = getattr(self.viewport, "active_tool", None)
        if getattr(tool, "_cache", None) is not None:
            ids = {w["id"] for w in doc["walls"]
                   if w["level"] == getattr(tool, "level_id", None)}
            tool._cache["ops"] = [o for o in self.doc()["openings"]
                                  if o["wall"] in ids]
            tool._cache["v"] = None             # read again, to be sure
        compat.flash(self.viewport, f"«{made[0]['name']}» placed — Ctrl+Z "
                     "takes it away", 4000)

    @staticmethod
    def opening_of(group) -> str | None:
        if compat.kind_of(group) != "opening":
            return None
        return compat._rec(group).get("id")

    def edit_opening(self, op_id: str) -> None:
        """A door's / window's / void's own window (modal)."""
        if self._pro_only("door"):
            return
        from .dialogs import OpeningDialog
        doc = self.doc()
        op = next((o for o in doc["openings"] if o["id"] == op_id), None)
        if op is None:
            return
        wall = next((w for w in doc["walls"] if w["id"] == op["wall"]), None)
        if wall is None:
            return
        self.hub.close_sub()
        dlg = OpeningDialog(op, wall, self.window)
        # its parts' materials: frame, leaf, trim, sill (trim.py, 2026-10-19)
        self._mat_tab(dlg, "opening", op_id)
        # more of its kind selected: the window changes them all (L1)
        apply = self._batch_window(
            dlg, "opening", op_id, self.apply_opening,
            self.PLURALS.get(op["kind"], "openings"),
            lambda: self.edit_opening(op_id))
        self._in_place(dlg, apply)
        self._live_window(dlg, "opening")      # L2: it, live (livewin.py)
        if not dlg.exec():
            return
        action, new = dlg.result_data()
        self._mat_take(dlg, action)
        if action == "delete":
            self.delete_opening(op_id)
        else:
            apply(new)
            self._again(dlg, lambda: self.edit_opening(op_id))

    def apply_opening(self, new: dict) -> None:
        from . import structure as S
        doc = self._live(self.doc())
        wall = next((w for w in doc["walls"] if w["id"] == new["wall"]), None)
        why = None if wall is None else S.opening_room(
            new, wall, doc["openings"], self._wall_height(wall))
        if wall is None or why:
            compat.flash(self.viewport, f"«{new['name']}» not changed — "
                         f"{why or 'its wall is gone'}", 6000)
            return
        doc["openings"] = [new if o["id"] == new["id"] else o
                           for o in doc["openings"]]
        self._commit_all(doc)
        compat.flash(self.viewport, f"«{new['name']}» updated — Ctrl+Z "
                     "undoes it", 5000)

    def delete_opening(self, op_id: str) -> None:
        doc = self._live(self.doc())
        op = next((o for o in doc["openings"] if o["id"] == op_id), None)
        if op is None:
            return
        doc["openings"] = [o for o in doc["openings"] if o["id"] != op_id]
        self._commit_all(doc)
        compat.flash(self.viewport, f"«{op['name']}» taken away — the wall "
                     "closes (Ctrl+Z opens it again)", 5000)

    # ---- Structure: drawing it ------------------------------------------------------
    def _reader(self, make):
        """A tool's view of the document — ``make(doc)`` again whenever the
        scene changed, half a second old at most (a copy taken when the
        tool came out kept what an undo had taken away)."""
        import time
        box = {"v": object(), "t": 0.0, "val": None}

        def read():
            v = getattr(self.viewport.scene, "version", None)
            now = time.monotonic()
            if v is None or v != box["v"] or now - box["t"] > 0.5:
                box.update(v=v, t=now, val=make(self._live(self.doc())))
            return box["val"]
        return read

    @staticmethod
    def _column_rise(doc: dict, lid: str) -> float:
        """How tall a new column stands on level ``lid`` (to the slab
        above) — the 3D preview's height."""
        from . import structure as S
        li = S.levels_info(doc, model.elevations).get(lid)
        return 0.0 if li is None else max(li["under"] - li["z0"], 0.0)

    def _level_struct(self, doc: dict, level_id: str,
                      kind: str | None = None) -> list[dict]:
        return [e for e in doc.get("structure") or []
                if e["level"] == level_id and (kind is None
                                               or e["type"] == kind)]

    @_project_first
    def start_struct_tool(self, element: str) -> None:
        """The shape picked in a structure options bar, drawing on the
        current level."""
        if self._pro_only(element):
            return
        from . import structtools as T
        o = self._struct_opts(element)
        _i, lv, z0 = self._work_level()
        doc = self._live(self.doc())
        if element == "column" and o["shape"] == "draw":
            tool = T.ColumnDrawTool(self._column_drawn, self._wall_cancelled,
                                    z0)
            tool.face_x, tool.face_y = self._face_lines(doc, lv["id"])
            tool.rise = self._column_rise(doc, lv["id"])
        elif element == "column":
            if o["shape"] not in ("single", "row", "grid"):
                return
            lid = lv["id"]
            tool = T.ColumnTool(o["shape"], None, self._wall_cancelled, z0,
                                lambda: self.col_opts, self._reader(
                                    lambda d: self._level_struct(d, lid,
                                                                 "column")))
            tool.on_done = lambda recs, t=tool: self._columns_done(recs, t)
            if o["shape"] == "row":          # a path, kept as a group
                tool.on_path = self._row_path
            from . import structure as S
            walls = [w for w in doc["walls"] if w["level"] == lv["id"]]
            # its faces pulled flush with the walls', the plot's, the
            # excavations' and the other columns' (his ask, 2026-10-03)
            tool.face_x, tool.face_y = self._face_lines(doc, lv["id"])
            # the preview shows them fitted, as they will be built
            tool.adjust = lambda c: (S.fit_column(c, walls)
                                     if self.col_opts["fit"] == "fit" else c)
            # pulled onto the walls' corners and T's (on their centre
            # lines), and squared up with them
            try:
                tool.magnets = [tuple(p) for p in S.wall_corners(walls)]
            except Exception:  # noqa: BLE001 — no magnets: a plain tool
                tool.magnets = []
            # …and onto the columns of the levels below and above (their
            # centres), a row's onto the rows' points: one column right over
            # another (his ask, 08/11/2026 — it was set by eye)
            try:
                tool.magnets += self._stack_magnets(doc, lid,
                                                    o["shape"] == "row")
            except Exception:  # noqa: BLE001
                compat.log_error("column magnets")
            # …and onto the footings' axes: a pad's centre, a strip's line, a
            # footing row's corners (his test, 07/11/2026: a column row in
            # the basement did not stand on the footing row)
            mags, tool.axes = self._footing_snaps(doc, lid, z0, column=True)
            tool.magnets = list(tool.magnets) + mags
            # a row clicked along an excavation's side stands inside it
            tool.pits = self._pits(doc)
            tool.rise = self._column_rise(doc, lid)
        elif element == "beam":
            lid = lv["id"]
            tool = T.BeamTool(self._beams_drawn, self._wall_cancelled, z0,
                              lambda: {"t": self.beam_opts["w"],
                                       "align": "centre",
                                       "insert": self.beam_opts.get(
                                           "insert", "centre")},
                              self._reader(lambda d: T.beams_as_walls(
                                  self._level_struct(d, lid, "beam"))))
            tool.magnets = self._columns_reaching(doc, lv["id"])
            # …and the footings' axes: a pad's centre, a strip's ends and
            # line, a footing row's points (his test, 07/11/2026: a beam
            # on a footing row — a wall's base — had nothing to hold it)
            mags, tool.axes = self._footing_snaps(doc, lid, z0)
            tool.magnets = list(tool.magnets) + mags
            # in 3D, pointed at its underside — the columns' tops (D10)
            from . import structure as S
            li = S.levels_info(doc, model.elevations)[lid]
            tool.z_floor = z0
            tool.under = lambda: (S.beam_top(self.beam_opts, z0, li)
                                  - float(self.beam_opts["h"]))
        elif element == "footing":
            from . import structure as S
            lid = lv["id"]
            walls = [w for w in doc["walls"] if w["level"] == lid]
            cols = self._reader(lambda d: self._level_struct(d, lid,
                                                             "column"))
            try:
                corners = [tuple(p) for p in S.wall_corners(walls)]
            except Exception:  # noqa: BLE001 — no magnets: a plain tool
                corners = []
            centres = [tuple(S.column_centre(c))
                       for c in self._level_struct(doc, lid, "column")]
            if o["shape"] == "pad":
                tool = T.PadTool(self._pads_drawn, self._wall_cancelled, z0,
                                 lambda: self.foot_opts, cols)
                tool.face_x, tool.face_y = self._face_lines(doc, lid)
                tool.magnets = centres + corners
            elif o["shape"] == "strip":
                tool = T.StripTool(
                    self._strips_drawn, self._wall_cancelled, z0,
                    lambda: {"t": self.foot_opts["sw"], "align": "centre"},
                    self._reader(lambda d: T.beams_as_walls(
                        [e for e in self._level_struct(d, lid, "footing")
                         if e.get("kind") == "strip"])))
                tool.magnets = centres + corners
            elif o["shape"] == "path":
                # a row of footings, with no columns (PLANO D, 07/11/2026):
                # the columns' row tool, its squares the pads
                from . import colrows
                tool = T.FootRowTool(
                    self._wall_cancelled, z0,
                    lambda: colrows.geo({"what": "footings"},
                                        colrows.opts_of(
                                            self._foot_row_opts())),
                    cols)
                tool.on_path = self._row_path
                tool.foots = lambda: dict(self.foot_opts)
                tool.face_x, tool.face_y = self._face_lines(doc, lid)
                tool.magnets = centres + corners
                try:
                    tool.magnets += self._stack_magnets(doc, lid, True)
                except Exception:  # noqa: BLE001
                    compat.log_error("footing magnets")
                tool.pits = self._pits(doc)
            else:
                return
        elif element == "slab":
            if o["shape"] == "hole":             # an opening through one
                # any shape (a customer's ask, 2026-10-13): the bar's «Drawn»
                drawn = o.get("hole_by", "rect")
                tool = T.SLAB_TOOLS.get(drawn, T.SLAB_TOOLS["rect"])(
                    self._slab_hole_drawn, self._wall_cancelled, z0)
                tool.noun = "Opening"
            else:
                cls = T.SLAB_TOOLS.get(o["shape"])
                if cls is None:
                    return
                tool = cls(self._slab_drawn, self._wall_cancelled, z0)
        elif element == "roof":
            cls = T.SLAB_TOOLS.get(o["shape"])
            if cls is None:
                return
            from . import structure as S
            # drawn at the walls' top, where the roof sits (seen over them)
            top = S.levels_info(doc, model.elevations)[lv["id"]]["under"]
            tool = cls(self._roof_drawn, self._wall_cancelled, top)
            tool.noun = "Roof"
            tool.axq_element = "roof"            # its shape lit in its bar
        else:
            return
        tool.level_id = lv["id"]
        self.method = o["shape"]
        self._activate(tool)
        QTimer.singleShot(0, self._refill_options)       # the shape lit
        compat.flash(self.viewport, f"{element.capitalize()}s on "
                     f"«{lv['name']}»", 3000)

    def _face_lines(self, doc: dict, level_id: str) -> tuple:
        """The x's of the upright lines and the y's of the level ones a
        column's face may lie flush with: the level's walls' faces, the
        plot's and the excavations' sides, the other columns' faces —
        those square with the axes."""
        from . import structure as S
        from . import walls as W
        xs, ys = set(), set()

        def edges(loop):
            n = len(loop)
            for k in range(n):
                (ax, ay), (bx, by) = loop[k], loop[(k + 1) % n]
                if abs(ax - bx) < 1e-4 and abs(ay - by) > 1e-3:
                    xs.add(round(ax, 4))
                elif abs(ay - by) < 1e-4 and abs(ax - bx) > 1e-3:
                    ys.add(round(ay, 4))
        mine = [w for w in doc["walls"] if w["level"] == level_id]
        try:
            for pcs in W.plan(mine).values():
                for pc in pcs:
                    edges(pc["outer"])
                    for h in pc["holes"]:
                        edges(h)
        except Exception:  # noqa: BLE001
            pass
        if doc.get("plot"):
            edges([tuple(p) for p in doc["plot"]["corners"]])
        for d in doc.get("digs") or []:
            edges([tuple(p) for p in d["corners"]])
        for c in self._level_struct(doc, level_id, "column"):
            if c.get("shape") != "round":
                edges(S.column_outline(c, 0.0))
        return sorted(xs), sorted(ys)

    def _columns_done(self, recs: list[dict], tool) -> None:
        """Columns placed (stamped, a row, a grid). A row is kept: the bar
        edits it live until the next placement."""
        before = {e["id"] for e in self.doc()["structure"]}
        self._last_row = None
        self._struct_done(recs)
        if tool.mode == "row" and getattr(tool, "last_ab", None):
            made = [e["id"] for e in self.doc()["structure"]
                    if e["id"] not in before]
            if made:
                self._last_row = {"ids": made, "ab": tool.last_ab,
                                  "tool": tool}
        # the faces of the new ones attract the next
        doc = self.doc()
        _i, lv, _z = self._work_level()
        tool.face_x, tool.face_y = self._face_lines(doc, lv["id"])

    def _redo_last_row(self, key: str | None = None) -> None:
        """The last row again, with the bar's count / spacing / ends /
        sizes — the «Column row» changed, its columns made again (its own
        Ctrl+Z)."""
        from . import colrows
        last = self._last_row
        if last is None:
            return
        doc = self._live(self.doc())
        row = colrows.find(doc, last.get("row"))
        if row is None or not colrows.members(doc, row):
            self._last_row = None              # undone, or deleted
            return
        # only what was changed in the bar: the rest stays the row's (its
        # window may have set its spacing — the bar still saying «count»)
        o = colrows.opts_of(row.get("opts"))
        foots = colrows.what_of(row) == "footings"
        if foots != (last.get("what") == "footings"):
            return
        if foots:
            # a row of footings: the footings bar's keys
            fo = self.foot_opts
            for k in colrows.LAYOUT_KEYS:
                if key in (None, k) and k in fo:
                    o[k] = copy.deepcopy(fo[k])
            f = o["foots"]
            for bar, mine in (("ftype", "type"), ("w", "pw"), ("sw", "sw"),
                              ("d", "d"), ("pd", "pd")):
                if key in (None, bar):
                    f[mine] = fo[bar]
            o = colrows.opts_of(o)
        else:
            keys = [key] if key in colrows.OPT_KEYS \
                else list(colrows.OPT_KEYS)
            if key == "section":
                keys.append("d")
            for k in keys:
                o[k] = copy.deepcopy(self.col_opts.get(k, o[k]))
        doc["colrows"] = [dict(r, opts=o) if r["id"] == row["id"] else r
                          for r in doc["colrows"]]
        doc, info = self._row_rebuild(doc, row["id"])
        self._commit_all(doc)
        n = len(colrows.members(self.doc(), info["row"]))
        if foots:
            msg = tr("{r}: {n} footings — Ctrl+Z goes back a step",
                     r=info["row"]["name"], n=n)
        else:
            msg = tr("{r}: {n} columns — Ctrl+Z goes back a step",
                     r=info["row"]["name"], n=n)
        compat.flash(self.viewport, msg, 3000)

    def _row_rebuild(self, doc: dict, rid: str) -> tuple:
        """``doc`` with the row ``rid``'s columns made again (colrows):
        fitted into the walls as its «In walls» says, never over another
        column."""
        from . import colrows
        from . import structure as S
        row = colrows.find(doc, rid)
        if row is None:
            return doc, {"made": 0, "kept": 0, "gone": 0, "dup": 0,
                         "row": None}
        from . import edition
        walls = [w for w in doc["walls"] if w["level"] == row["level"]]
        fit = fit_beam = None
        if colrows.opts_of(row.get("opts"))["fit"] == "fit":
            def fit(r, _w=walls):
                return S.fit_column(r, _w)

            def fit_beam(r, _w=walls):
                return S.fit_beam(r, _w)
        # its beams (Pro): their foot / middle from the columns' own span —
        # the excavation's floor under them, the level's height
        o = colrows.opts_of(row.get("opts"))
        info = S.levels_info(doc, model.elevations)
        lid = row["level"]

        def span(p, _o=o, _li=info.get(lid)):
            if _li is None:
                return float(_o.get("base", 0.0) or 0.0), 3.0
            foot = float(_o.get("base", 0.0) or 0.0)
            if foot <= 0:
                g = S.ground_under(doc, info, lid, p)
                if g is not None:
                    foot = min(foot, g - _li["z0"])
            top = (_li["under"] - _li["z0"]) if _o["height"] == "level" \
                else float(_o["h"])
            # (the level's top: where a top beam «under the slab» ends)
            return foot, top, _li["height"]

        def same(a, b):
            # a row's beam at ANOTHER height is a beam of its own (its foot
            # under its top one, on the same line); every other: as ever
            if a.get("type") == "beam" and b.get("type") == "beam":
                za = (a.get("zmode") == "own", round(float(a.get("zt", 0)), 2))
                zb = (b.get("zmode") == "own", round(float(b.get("zt", 0)), 2))
                if za[0] != zb[0] or (za[0] and abs(za[1] - zb[1]) > 0.05):
                    return False
            return self._same(a, b)
        pits = self._pits(doc)

        def fit_foot(r, _p=pits):
            # a pad by an excavation's side: kept inside it (eccentric), as
            # «Under the columns» does
            if r.get("kind") != "pad" or not _p:
                return r
            sx, sy = S.push_inside(S.pad_outline(r), _p)
            return dict(r, x=round(r["x"] + sx, 4), y=round(r["y"] + sy, 4))
        def ftop(p, _li=info.get(lid)):
            # a footing's top as built (structure.build): under the slab, on
            # the excavation's floor where it is lower — over the floor
            if _li is None:
                return 0.0
            t = -float(_li["slab"])
            g = S.ground_under(doc, info, lid, p)
            return t if g is None else min(t, g - _li["z0"])
        return colrows.rebuild(doc, rid, pits=pits, fit=fit,
                               same=same, new_elements=model.new_elements,
                               beams=not edition.lite(), span=span,
                               fit_beam=fit_beam, fit_foot=fit_foot,
                               centre=S.column_centre, ftop=ftop)

    def _picked_in_last_row(self) -> bool:
        """What is selected is the last row's own (its window leaves them
        selected): the bar still changes the ROW — footings have no bar
        edit of their own (BAR_REC)."""
        from . import colrows
        _k, ids = self._lib_picked()
        last = self._last_row or {}
        row = colrows.find(self.doc(), last.get("row"))
        if row is None or not ids:
            return False
        mine = {e["id"] for e in self.doc()["structure"]
                if e.get("row") == row["id"]}
        return set(ids) <= mine

    def _foot_row_opts(self) -> dict:
        """The footings bar as a row of footings' options (colrows)."""
        fo = self.foot_opts
        o = {k: fo[k] for k in ("by", "count", "spacing", "ends", "align")
             if k in fo}
        o["foots"] = {"type": fo.get("ftype", "pads"), "pw": fo["w"],
                      "sw": fo["sw"], "d": fo["d"],
                      "pd": fo.get("pd", 0.80)}
        return o

    def _row_path(self, tool, pts: list, closed: bool) -> None:
        """The row tool's path so far (each click, its close, Backspace):
        the «Column row» made at the 2nd click — its first stretch's columns
        there at once, as the row of before — and changed at every next one
        (a Ctrl+Z each)."""
        from . import colrows
        _i, lv, _z = self._work_level()
        doc = self._live(self.doc())
        row = colrows.find(doc, tool.row_id) if tool.row_id else None
        if row is None and len(pts) < 2:
            return
        if row is not None and len(pts) < 2:
            # Backspace down to its first point: the row is taken away,
            # its beams too
            gone = {e["id"] for e in colrows.members(doc, row)} | {
                e["id"] for e in colrows.beams_of(doc, row)}
            doc["structure"] = [e for e in doc["structure"]
                                if e["id"] not in gone]
            doc["colrows"] = [r for r in doc["colrows"]
                              if r["id"] != row["id"]]
            self._commit_all(doc)
            tool.row_id = None
            self._last_row = None
            return
        path = [[round(p[0], 4), round(p[1], 4)] for p in pts]
        what = getattr(tool, "row_what", "columns")
        opts = self._foot_row_opts() if what == "footings" else self.col_opts
        on_feet = None
        if what == "columns":
            # drawn on a footing row's axis: centred on it, a column on
            # each of its pads (his test, 07/11/2026: «Inside» put the
            # basement's columns off the footings)
            on_feet = self._on_footing_row(doc, lv["id"], path)
            if on_feet is not None:
                opts = self._cols_on_feet(opts, on_feet)
        if row is None:
            row = colrows.new_row(doc, lv["id"], path, closed, opts, what)
            doc["colrows"] = list(doc.get("colrows") or []) + [row]
        else:
            doc["colrows"] = [dict(r, path=path, closed=bool(closed),
                                   opts=colrows.opts_of(opts))
                              if r["id"] == row["id"] else r
                              for r in doc["colrows"]]
        doc, info = self._row_rebuild(doc, row["id"])
        if not colrows.members(doc, info["row"]):
            compat.flash(self.viewport, "Nothing new to build — already "
                         "there", 4000)
            return
        self._commit_all(doc)
        tool.row_id = row["id"]
        self._last_row = {"row": row["id"], "what": what}
        self._last_made = {e["id"] for e in colrows.members(self.doc(),
                                                             info["row"])}
        n = len(self._last_made)
        if what == "footings":
            msg = tr("{r}: {n} footings — Ctrl+Z undoes the last point",
                     r=info["row"]["name"], n=n)
            if closed:
                msg = tr("{r} closed: {n} footings — double-click one to "
                         "change them all", r=info["row"]["name"], n=n)
        else:
            msg = tr("{r}: {n} columns — Ctrl+Z undoes the last point",
                     r=info["row"]["name"], n=n)
            if closed:
                msg = tr("{r} closed: {n} columns — double-click one to "
                         "change them all", r=info["row"]["name"], n=n)
        if info.get("dup"):
            msg += " " + tr("({d} already there, left out)", d=info["dup"])
        if on_feet is not None:
            msg += " " + tr("— on «{r}»: centred on it, spaced as its pads",
                            r=on_feet["name"])
        compat.flash(self.viewport, msg, 5000)
        # the faces of the new ones attract the next
        tool.face_x, tool.face_y = self._face_lines(self.doc(), lv["id"])

    def _column_drawn(self, corners) -> None:
        """Draw: the rectangle drawn is the column (its size kept in the
        bar for the next ones)."""
        xs = [p[0] for p in corners]
        ys = [p[1] for p in corners]
        w, d = round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3)
        if w < 0.05 or d < 0.05:
            compat.flash(self.viewport, "Too small for a column", 4000)
            return
        o = self.col_opts
        o.update(w=w, d=d, section="rect", angle=0.0)
        rec = {"type": "column", "x": round((min(xs) + max(xs)) / 2, 4),
               "y": round((min(ys) + max(ys)) / 2, 4), "shape": "rect",
               "w": w, "d": d, "angle": 0.0, "anchor": "centre"}
        free = o["fit"]
        o["fit"] = "free"                    # drawn = as drawn
        try:
            self._struct_done([rec])
        finally:
            o["fit"] = free
        QTimer.singleShot(0, self._refill_options)

    def _beams_drawn(self, recs: list[dict]) -> None:
        o = self.beam_opts
        out = [{"type": "beam", "a": r["a"], "b": r["b"], "w": o["w"],
                "h": o["h"], "zmode": o["zmode"], "zt": o["zt"]}
               for r in recs]
        # on footings (a footing row, a wall's base): it sits on their top
        # (his test, 07/11/2026)
        try:
            _i, lv, z0 = self._work_level()
            doc = self._live(self.doc())
            feet = self._footing_tops(doc, lv["id"])
            if feet:
                # a column at an end: the beam goes on the columns, as ever
                # (a beam column to column over pads stays at its height)
                from shapely.geometry import Point, Polygon
                from . import structure as S
                cols = [Polygon(S.column_outline(c, 0.0)).buffer(0.01)
                        for c in self._cols_reaching(doc, lv["id"])]

                def on_col(r):
                    return any(c.contains(Point(float(e[0]), float(e[1])))
                               for e in (r["a"], r["b"]) for c in cols)
                out = [r if on_col(r) else self._beam_on_footings(r, z0, feet)
                       for r in out]
        except Exception:  # noqa: BLE001 — as drawn
            compat.log_error("beam on footings")
        self._struct_done(out)

    def _pads_drawn(self, recs: list[dict]) -> None:
        """Pads clicked: on a column, centred under it, turned with it and
        never smaller than it + 0.20 (as the one-click ones); by an
        excavation's side, kept inside it."""
        _i, lv, _z = self._work_level()
        doc = self._live(self.doc())
        cols = self._level_struct(doc, lv["id"], "column")
        pits = self._pits(doc)
        self._struct_done([self.pad_at(r["x"], r["y"], cols, self.foot_opts,
                                       pits) for r in recs])

    @staticmethod
    def pad_at(x, y, cols: list, o: dict, pits: list) -> dict:
        """The pad clicked at (x, y): on a column — anywhere within it —
        centred under it, turned with it, never smaller than it + 0.20."""
        from . import structure as S
        x, y, ang, side = float(x), float(y), 0.0, 0.0
        for c in cols:
            cx, cy = S.column_centre(c)
            reach = min(float(c["w"]), float(c.get("d", c["w"]))) / 2
            if math.dist((x, y), (cx, cy)) <= max(reach, 0.02):
                x, y = cx, cy
                ang = float(c.get("angle", 0.0))
                side = max(float(c["w"]), float(c.get("d", c["w"]))) + 0.20
                break
        f = {"type": "footing", "kind": "pad", "x": x, "y": y,
             "w": max(float(o["w"]), side), "d": o["d"], "angle": ang}
        sx, sy = S.push_inside(S.pad_outline(f), pits)
        f["x"], f["y"] = round(x + sx, 4), round(y + sy, 4)
        return f

    def _strips_drawn(self, recs: list[dict]) -> None:
        o = self.foot_opts
        self._struct_done([{"type": "footing", "kind": "strip",
                            "a": r["a"], "b": r["b"], "w": o["sw"],
                            "d": o["d"]} for r in recs])

    def _slab_ceiling(self) -> dict:
        """A slab drawn as a CEILING (0.15.0, B4: its own height) or a
        BLOCK (B5: its base over the floor)."""
        o = self.slab_opts
        if o.get("ceiling"):
            return {"ceiling": True, "ch": o.get("ch", 2.60)}
        if o.get("block"):
            return {"block": True, "base": o.get("base", 0.0)}
        # a floor slab: one of YOUR types, or a card's layers (slab layers)
        if o.get("stype"):
            return {"stype": o["stype"]}
        if o.get("layers"):
            got = {"layers": [dict(la) for la in o["layers"]]}
            if o.get("frame"):
                got["frame"] = dict(o["frame"])
            return got
        return {}

    def _slab_drawn(self, corners) -> None:
        o = self.slab_opts
        self._struct_done([dict({"type": "slab", "corners": corners,
                                 "t": o["t"], "offset": o["offset"]},
                                **self._slab_ceiling())])

    def _roof_lplan(self) -> None:
        """The library's «L / T / U plan» card: a hip roof over this
        level's walls when they are not a plain rectangle (roof_l: an L;
        roof_any: any other plan — 0.12.0) — else why, and nothing built."""
        from . import roof_any, roof_l
        from . import structure as S
        _i, lv, _z0 = self._work_level()
        loops = S.inside_walls_all(self._level_walls(lv["id"]))
        if not any(roof_l.is_l(loop) or roof_any.ok(loop) for loop in loops):
            compat.flash(self.viewport, f"The walls of «{lv['name']}» make "
                         "a plain rectangle (or no closed outline) — for a "
                         "rectangle pick Hip or Gable", 7000)
            return
        self.struct_action("roof", "walls")

    def _roof_rec(self, corners) -> dict:
        from . import structure as S
        o = self.roof_opts
        return {"type": "roof", "kind": o["kind"],
                "corners": S.roof_corners(corners, o["kind"]),
                "slope": o["slope"], "overhang": o["overhang"], "go": o["go"],
                "t": o["t"], "ridge": o["ridge"],
                "parapet": o["parapet"] if o["kind"] in ("flat", "hidden")
                else 0.0,
                "pt": o["pt"], "fall": o["fall"], "slopes": o["slopes"],
                "pauto": o["pauto"], "gutter": o["gutter"],
                "zmode": o["zmode"], "zh": o["zh"],
                "layers": [dict(la) for la in o.get("layers") or []]
                or None, "frame": o.get("frame")}

    def _roof_drawn(self, corners) -> None:
        self._struct_done([self._roof_rec(corners)])

    def _slab_hole_drawn(self, corners) -> None:
        """An opening drawn: through the slab of this level that holds
        it (refused, with the reason, anywhere else)."""
        from . import structure as S
        _i, lv, _z0 = self._work_level()
        doc = self._live(self.doc())
        slab, why = S.hole_place(self._level_struct(doc, lv["id"], "slab"),
                                 corners)
        if slab is None:
            compat.flash(self.viewport, f"{why} — draw it again", 5000)
            return
        new = dict(slab, holes=list(slab.get("holes") or [])
                   + [[list(p) for p in corners]])
        doc["structure"] = [new if e["id"] == slab["id"] else e
                            for e in doc["structure"]]
        self._commit_all(doc)
        compat.flash(self.viewport, f"Opening in «{slab['name']}» — Ctrl+Z "
                     "closes it", 5000)

    def _struct_done(self, recs: list[dict], quiet: bool = False) -> int:
        """New structural elements on the current level — one Ctrl+Z.
        Never two columns (pads) in one place, two beams (strips) on one
        line, or a slab over the same outline twice."""
        from . import structure as S
        _i, lv, _z0 = self._work_level()
        doc = self._live(self.doc())
        mine = self._level_struct(doc, lv["id"])
        walls = [w for w in doc["walls"] if w["level"] == lv["id"]]
        out, dup = [], 0
        for r in recs:
            r = dict(r, level=lv["id"])
            if r["type"] == "column":
                o = self.col_opts
                r["height"] = "level" if o["height"] == "level" \
                    else float(o["h"])
                r["base"] = float(o.get("base", 0.0))
                r["cbase"], r["ccap"] = o.get("cbase"), o.get("ccap")
                if o["fit"] == "fit":            # inside the wall it is on
                    r = S.fit_column(r, walls)
            if r["type"] == "beam" and self.beam_opts["fit"] == "fit":
                r = S.fit_beam(r, walls)
            if S.why_not(r):
                continue
            if any(self._same(r, e) for e in mine + out):
                dup += 1
                continue
            out.append(r)
        if not out:
            if not quiet:
                compat.flash(self.viewport, "Nothing new to build"
                             + (" — already there" if dup else ""), 4000)
            return 0
        made = model.new_elements(doc["structure"], out)
        doc["structure"] = doc["structure"] + made
        self._commit_all(doc)
        self._last_made = {m["id"] for m in made}
        n = len(made)
        if not quiet:
            kinds = sorted({S.LABEL[m["type"]].lower() for m in made})
            compat.flash(self.viewport, f"{n} {' / '.join(kinds)}"
                         f"{'s' if n > 1 else ''} on «{lv['name']}» — "
                         "Ctrl+Z undoes " + ("them" if n > 1 else "it")
                         + (f" ({dup} already there, left out)" if dup
                            else ""), 5000)
        return n

    @staticmethod
    def _same(a: dict, b: dict) -> bool:
        """Two elements in the same place — the second would be a copy
        (OVERLAPPING, not only identical: a column 2.5 cm off another one
        is the same column — a 0.25 basement wall moves its corner off the
        0.20 grid of the floors above)."""
        import math as _m
        if a["type"] != b["type"]:
            return False
        if a["type"] == "column" or (a["type"] == "footing"
                                     and a.get("kind") == "pad"
                                     and b.get("kind") == "pad"):
            reach = max(min(float(a["w"]), float(a.get("d", a["w"]))),
                        min(float(b["w"]), float(b.get("d", b["w"])))) / 2
            return _m.dist((a["x"], a["y"]), (b["x"], b["y"])) < max(
                reach, 0.02)
        if a["type"] == "beam" or (a["type"] == "footing"
                                   and a.get("kind") == "strip"
                                   and b.get("kind") == "strip"):
            if "m" in a or "m" in b:             # curved strips: same ends
                return _m.dist(a["a"], b["a"]) < 0.02 and \
                    _m.dist(a["b"], b["b"]) < 0.02
            (ax, ay), (bx, by) = b["a"], b["b"]
            L = _m.hypot(bx - ax, by - ay)
            if L < 1e-9:
                return False
            ux, uy = (bx - ax) / L, (by - ay) / L
            reach = max(float(a["w"]), float(b["w"])) / 2
            fs = []
            for p in (a["a"], a["b"]):
                dx, dy = p[0] - ax, p[1] - ay
                if abs(-dx * uy + dy * ux) > reach:
                    return False                 # not on the same line
                fs.append(dx * ux + dy * uy)
            lo, hi = max(min(fs), 0.0), min(max(fs), L)
            mine = abs(fs[1] - fs[0])
            # most of the new one lies along the old one
            return mine > 1e-9 and (hi - lo) > 0.5 * min(mine, L)
        if a["type"] in ("slab", "roof"):
            # a slab over the same outline at ANOTHER height is a slab of
            # its own: the level's ceiling over its floor (his ask,
            # 2026-10-15 — «Top» 4.00 was taken for the floor's copy)
            if a["type"] == "slab" and abs(float(a.get("offset", 0.0))
                                           - float(b.get("offset", 0.0))) \
                    > 0.02:
                return False
            ca, cb = a["corners"], b["corners"]
            return len(ca) == len(cb) and all(
                any(_m.dist(p, q) < 0.02 for q in cb) for p in ca)
        if a["type"] == "glazing":               # its Opening filled twice
            if a.get("place") != "free" or b.get("place") != "free":
                # (a window's bars and an Opening's grid: two places)
                return a.get("op") == b.get("op") and bool(a.get("op")) \
                    and a.get("place") == b.get("place")
            return _m.dist(a["a"], b["a"]) < 0.02 and \
                _m.dist(a["b"], b["b"]) < 0.02
        if a["type"] == "street":                # the same sides / axis
            if a.get("edges") or b.get("edges"):
                return bool(set(a.get("edges") or ()) & set(
                    b.get("edges") or ()))
            pa, pb = a["pts"], b["pts"]
            return len(pa) == len(pb) and all(
                _m.dist(p, q) < 0.02 for p, q in zip(pa, pb))
        if a["type"] == "guard":                 # the same line, again
            pa, pb = a["pts"], b["pts"]
            return len(pa) == len(pb) and all(
                _m.dist(p, q) < 0.02 for p, q in zip(pa, pb))
        if a["type"] in ("ramp", "stair"):       # the same one, on top
            return _m.dist((a["x"], a["y"]), (b["x"], b["y"])) < 0.02 and \
                abs((float(a.get("angle", 0)) - float(b.get("angle", 0))
                     + 180) % 360 - 180) < 0.5
        return False

    @classmethod
    def _columns_reaching(cls, doc: dict, lid: str) -> list:
        """The centres of the columns standing in level ``lid``: its own,
        and a lower level's that rise into it (a basement column 6 m tall
        holds the floor above too) — a beam's supports."""
        from . import structure as S
        # where two rows' axes cross inside a corner column, the beam goes
        # there — not to that column's own centre (his ring, 2026-10-09:
        # 60×30 columns, the corner one turned, its centre 15 cm in from
        # the side row's axis: the beam hung half off the side columns)
        return S.beam_magnets(cls._cols_reaching(doc, lid))

    @staticmethod
    def _cols_reaching(doc: dict, lid: str) -> list:
        """The columns standing in level ``lid`` (its own, and a lower
        level's rising into it)."""
        from . import structure as S
        info = S.levels_info(doc, model.elevations)
        lo = info[lid]["z0"] + 0.01
        hi = info[lid]["z0"] + info[lid]["height"] - 0.01
        out = []
        for c in doc.get("structure") or []:
            if c["type"] != "column" or c["level"] not in info \
                    or S.why_not(c) is not None:
                continue
            li = info[c["level"]]
            top = li["under"] if c.get("height", "level") == "level" \
                else li["z0"] + float(c["height"])
            bot = li["z0"] + float(c.get("base", 0.0))
            if c["level"] == lid or (top > lo and bot < hi):
                out.append(c)
        return out

    @staticmethod
    def _footing_tops(doc: dict, lid: str) -> list:
        """This level's footings as a beam sees them: [(outline polygon,
        top z, axis points)] — a pad's centre, a strip's two ends (his test,
        07/11/2026: a beam on a footing row, a wall's base)."""
        from shapely.geometry import LineString, Polygon
        from . import structure as S
        info = S.levels_info(doc, model.elevations)
        if lid not in info:
            return []
        li = info[lid]
        z0 = li["z0"]
        out = []
        for f in doc.get("structure") or []:
            if f.get("type") != "footing" or f.get("level") != lid \
                    or S.why_not(f) is not None:
                continue
            try:
                if f.get("kind") == "pad":
                    p = (float(f["x"]), float(f["y"]))
                    poly = Polygon(S.pad_outline(f))
                    axis = [p]
                else:
                    a, b = tuple(f["a"][:2]), tuple(f["b"][:2])
                    p = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                    poly = LineString([a, b]).buffer(float(f["w"]) / 2,
                                                      cap_style=2)
                    axis = [a, b]
                if f.get("zt") is not None:      # as structure.build
                    top = z0 + float(f["zt"])
                else:
                    g = S.ground_under(doc, info, lid, p)
                    top = z0 - li["slab"] if g is None \
                        else min(z0 - li["slab"], g)
                if f.get("kind") != "pad":
                    top -= S.SHRINK
                out.append((poly, top, axis))
            except Exception:  # noqa: BLE001 — one odd footing: the rest
                continue
        return out

    def _footing_snaps(self, doc: dict, lid: str, z0: float,
                       column: bool = False) -> tuple:
        """(magnets, axes) of this level's footings for a beam / column
        tool: a pad's centre, a strip's ends and line, a footing row's
        axis and corners — each at its footing's top (3D). For a COLUMN,
        at where it will stand: the footing's top in a pit, else its floor
        (a column is built from the floor; the footing is under the slab)."""
        mags, axes = [], []
        try:
            feet = self._footing_tops(self._live(doc), lid)
            if column:
                from . import structure as S
                li = S.levels_info(doc, model.elevations)[lid]
                under = z0 - li["slab"] - 0.005   # (a strip: 1 mm under)
                feet = [(poly, top if top < under else z0, ax)
                        for poly, top, ax in feet]
            mags = [(float(p[0]), float(p[1]), top)
                    for _poly, top, ax in feet for p in ax]
            axes = [(ax[0], ax[1], top) for _poly, top, ax in feet
                    if len(ax) == 2]
            for r, segs in self._footing_axes(doc, lid):
                # (the row's footings share one top — colrows ftop)
                top = min((t for _p, t, _a in feet), default=z0)
                axes += [(tuple(a), tuple(b), top) for a, b in segs]
                mags += [(p[0], p[1], top) for s in segs for p in s]
        except Exception:  # noqa: BLE001 — no footing magnets
            compat.log_error("footing magnets")
        return mags, axes

    def _on_footing_row(self, doc: dict, lid: str, path) -> dict | None:
        """The footing row of level ``lid`` whose axis every point of
        ``path`` lies on (1 cm) — or None."""
        for r, segs in self._footing_axes(doc, lid):
            def on(p):
                for a, b in segs:
                    ax, ay = b[0] - a[0], b[1] - a[1]
                    L2 = ax * ax + ay * ay
                    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, (
                        (p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / L2))
                    if math.dist(p, (a[0] + t * ax, a[1] + t * ay)) <= 0.01:
                        return True
                return False
            if all(on(p) for p in path):
                return r
        return None

    @staticmethod
    def _cols_on_feet(opts: dict, frow: dict) -> dict:
        """A column row's options on footing row ``frow``: centred on its
        axis — and, when it has pads, laid out as they are (by, count,
        spacing, ends): a column on each pad."""
        from . import colrows
        o = dict(copy.deepcopy(opts), align="centre")
        fo = colrows.opts_of(frow.get("opts"))
        if colrows.part_on(fo, "pad"):
            for k in colrows.LAYOUT_KEYS:
                if k != "align" and k in fo:
                    o[k] = copy.deepcopy(fo[k])
        return o

    def _footing_axes(self, doc: dict, lid: str) -> list:
        """[(footing row, its axis stretches)] on level ``lid``: the path
        as its footings stand on it (moved by its alignment), the corners
        where the lines cross."""
        from . import colrows
        out = []
        for r in doc.get("colrows") or []:
            if r.get("level") != lid or colrows.what_of(r) != "footings":
                continue
            ro = colrows.opts_of(r.get("opts"))
            _c, segs, _a = colrows.stretches(
                r["path"], r.get("closed"), colrows.geo(r, ro),
                self._pits(doc))
            if segs:
                out.append((r, segs))
        return out

    @staticmethod
    def _beam_on_footings(rec: dict, z0: float, feet: list) -> dict:
        """A beam whose two ends are ON footings of its level (``feet``:
        _footing_tops) sits on them: its height its own, its underside on
        the higher top (built 1 mm over it: never one plane with it)."""
        from shapely.geometry import Point
        try:
            tops = []
            for end in (rec["a"], rec["b"]):
                pt = Point(float(end[0]), float(end[1]))
                t = [top for poly, top, _ax in feet
                     if poly.buffer(0.01).contains(pt)]
                if not t:
                    return rec
                tops.append(max(t))
            under = max(tops)      # (the beam is drawn 1 mm off its faces)
            return dict(rec, zmode="own",
                        zt=round(under + float(rec["h"]) - z0, 4))
        except Exception:  # noqa: BLE001 — as drawn
            return rec

    @staticmethod
    def _stack_magnets(doc: dict, lid: str, row: bool) -> list:
        """Points a column is pulled onto, from the levels next to this one:
        the centres of their columns; drawing a ROW, also the points of the
        rows' paths (this level's too: a row going on from another)."""
        from . import colrows
        from . import structure as S
        ids = [lv["id"] for lv in doc["levels"]]
        if lid not in ids:
            return []
        i = ids.index(lid)
        near = set(ids[max(0, i - 1):i]) | set(ids[i + 1:i + 2])
        out = [tuple(round(v, 4) for v in S.column_centre(e))
               for e in doc.get("structure") or []
               if e.get("type") == "column" and e.get("level") in near]
        if row:
            out += [(float(p[0]), float(p[1]))
                    for r in doc.get("colrows") or []
                    if r.get("level") in near | {lid}
                    for p in r.get("path") or []]
        return list(dict.fromkeys(out))

    def _pits_on(self, lid: str) -> bool:
        """An excavation reaching below this level's floor (its rows stand
        inside it by themselves)."""
        try:
            from . import structure as S
            doc = self.doc()
            info = S.levels_info(doc, model.elevations)
            return any(S.ground_under(doc, info, lid, tuple(p)) is not None
                       for poly in self._pits(doc) for p in poly[:1])
        except Exception:  # noqa: BLE001
            return bool(self._pits(self.doc()))

    @staticmethod
    def _pits(doc: dict) -> list:
        """The excavations' outlines (not the fills')."""
        from . import terrain
        return [[tuple(p) for p in d["corners"]]
                for d in doc.get("digs") or [] if not terrain.is_fill(d)]

    @_project_first
    def struct_action(self, element: str, shape: str) -> None:
        """The one-click shapes: they read this level's walls / columns
        and build at once."""
        if self._pro_only(element):
            return
        from . import structure as S
        _i, lv, _z0 = self._work_level()
        doc = self._live(self.doc())
        walls = [w for w in doc["walls"] if w["level"] == lv["id"]]
        recs: list[dict] = []
        why = None
        if (element, shape) == ("column", "corners"):
            pts = S.wall_corners(walls)
            o = self.col_opts
            recs = [{"type": "column", "x": round(p[0], 4),
                     "y": round(p[1], 4), "shape": o["section"],
                     "w": o["w"], "d": o["w"] if o["section"] == "round"
                     else o["d"], "angle": o["angle"], "anchor": "centre"}
                    for p in pts]
            why = "no walls meet yet"
        elif (element, shape) == ("beam", "walls"):
            o = self.beam_opts
            recs = [{"type": "beam", "a": a, "b": b, "w": o["w"],
                     "h": o["h"]} for a, b in S.along_walls(walls)]
            why = "no straight walls yet"
        elif (element, shape) == ("slab", "walls"):
            # one slab under EACH block of walls (his Level 2 in two wings,
            # 2026-10-15: only the bigger got one)
            o = self.slab_opts
            if o.get("ceiling"):
                # a CEILING: one in each ROOM, between its walls' faces
                from . import spaces
                loops = [[list(p) for p in r["poly"].exterior.coords[:-1]]
                         for r in spaces.found(walls)]
            else:
                loops = S.inside_walls_all(walls)
                if not loops:
                    # a level with no walls yet (his test, 2026-10-23: the
                    # floor of Level 2 before its walls — «nothing built»):
                    # on the walls of the level under it, that hold it
                    loops = S.inside_walls_all(self._walls_below(doc,
                                                                 lv["id"]))
                if not loops:
                    # no walls at all, only the frame (his test, 2026-10-30:
                    # columns and beams on Level 1): over the beams under
                    # this floor — or round the columns
                    loops = S.inside_frame_all(*self._frame_below(doc,
                                                                  lv["id"]))
            recs = [dict({"type": "slab", "corners": loop, "t": o["t"],
                          "offset": o["offset"]}, **self._slab_ceiling())
                    for loop in loops]
            why = "no walls yet (nor beams or columns under it)"
        elif (element, shape) == ("footing", "pads"):
            o = self.foot_opts
            from . import colrows
            padded = {r["id"] for r in doc.get("colrows") or []
                      if colrows.part_on(colrows.opts_of(r.get("opts")),
                                         "pad")}
            for c in self._level_struct(doc, lv["id"], "column"):
                if c.get("row") in padded:
                    continue          # its row has its pads (PLANO D)
                cx, cy = S.column_centre(c)
                side = max(float(c["w"]), float(c["d"])) + 0.20
                r = {"type": "footing", "kind": "pad", "x": cx, "y": cy,
                     "w": max(o["w"], side), "d": o["d"],
                     "angle": float(c.get("angle", 0.0))}
                # by an excavation's side: kept inside it (eccentric)
                sx, sy = S.push_inside(S.pad_outline(r), self._pits(doc))
                r["x"], r["y"] = round(cx + sx, 4), round(cy + sy, 4)
                recs.append(r)
            why = "no columns yet"
        elif (element, shape) == ("footing", "strips"):
            o = self.foot_opts
            recs = [dict(s, type="footing", kind="strip", w=o["sw"],
                         d=o["d"]) for s in S.strips_under(walls)]
            why = "no walls yet"
        elif (element, shape) == ("footing", "rows"):
            o = self.foot_opts
            from . import colrows
            # (a «Column row» with its own footings has them already: its
            # columns left out, never a footing twice — PLANO D)
            own = {r["id"] for r in doc.get("colrows") or []
                   if colrows.opts_of(r.get("opts"))["foots"]["type"]
                   != "none"}
            recs = [dict(s, type="footing", kind="strip", d=o["d"])
                    for s in S.strips_under_columns(
                        [c for c in self._level_struct(doc, lv["id"],
                                                       "column")
                         if c.get("row") not in own],
                        o["sw"], self._pits(doc))]
            why = "no rows of columns yet (2 or more in line)"
        elif (element, shape) == ("roof", "walls"):
            recs = [self._roof_rec(loop) for loop in S.inside_walls_all(walls)]
            why = "no walls yet"
        if not recs:
            self._nothing_under(element, why, lv["name"])
            return
        self._last_made = set()
        if self._struct_done(recs) and self._last_made:
            # what was made stays SELECTED: seen at once, grips on it, one
            # Delete takes it away (his test, 2026-10-15 — a slab made under
            # the walls looked like nothing had happened). Only here: a
            # drawing tool's pieces are not picked up mid-draw.
            compat.select_ids(self.viewport, set(self._last_made))
            if element == "footing" and not self.plan_on:
                # in 3D they are under the ground (D11): say where they went
                compat.flash(self.viewport, tr(
                    "{n} footing(s) made, under the ground — hide the "
                    "Terrain to see them", n=str(len(recs))), 5000)
        QTimer.singleShot(0, self._refill_options)

    #: what to do instead, when a one-click shape found nothing to build on
    NOTHING_UNDER = {
        "column": "Draw the walls first, or place the columns one by one "
                  "(Single / Row / Grid).",
        "beam": "Draw the walls first, or draw the beams point by point.",
        "slab": "Draw the walls first, or draw the slab's outline "
                "(Rectangle / Point by point).",
        "footing": "Draw them first, or draw the footing by hand: «Pad» "
                   "(a click each) or «Strip» (point by point).",
        "roof": "Draw the walls first, or draw the roof's outline "
                "(Rectangle / Point by point).",
    }

    def _nothing_under(self, element: str, why: str, level: str) -> None:
        """A one-click shape with nothing under it: said where it is SEEN
        — by the icon just clicked, not only in the status bar (his new
        file, 2026-11-01: «the icon does nothing — a regression?») — with
        what to do instead."""
        text = (tr("On «{level}»: {why} — nothing built.", level=level,
                   why=tr(why)) + "\n"
                + tr(self.NOTHING_UNDER.get(element, ""))).rstrip()
        self._say_at_cursor(text)

    def _say_at_cursor(self, text: str, ms: int = 9000) -> None:
        """A «not yet» said by the mouse, where the eye is (a balloon, no
        window to close) — and in the status bar too."""
        compat.flash(self.viewport, text.replace("\n", " "), ms)
        try:
            from PySide6.QtCore import QRect
            from PySide6.QtGui import QCursor
            from PySide6.QtWidgets import QToolTip
            QToolTip.showText(QCursor.pos(), text, None, QRect(), ms)
        except Exception:  # noqa: BLE001 — the status bar says it anyway
            pass

    # ---- Walls: drawing them ---------------------------------------------------------
    def _work_level(self):
        """(index, level, floor elevation) of the level walls go on — the
        current one; on the Terrain, the ground floor."""
        doc = self.doc()
        if self.terrain_current:
            self.set_floor(doc["levels"][self._ground_index(doc)]["id"],
                           quiet=True)
        i = self.floor if 0 <= self.floor < len(doc["levels"]) \
            else self._ground_index(doc)
        elev = model.elevations(doc["levels"], doc["project"]["ground_level"]
                                if model.has_project(doc) else 0.0)
        return i, doc["levels"][i], elev[i]

    def _level_walls(self, level_id: str) -> list[dict]:
        return [w for w in self.doc()["walls"] if w["level"] == level_id]

    @staticmethod
    def _walls_below(doc: dict, level_id: str) -> list[dict]:
        """The walls of the nearest level UNDER this one that has any — []
        on the lowest."""
        elev = model.elevations(doc["levels"], doc["project"]["ground_level"]
                                if model.has_project(doc) else 0.0)
        z = {lv["id"]: e for lv, e in zip(doc["levels"], elev)}
        if level_id not in z:
            return []
        for lid in sorted((k for k in z if z[k] < z[level_id] - 1e-6),
                          key=lambda k: -z[k]):
            mine = [w for w in doc["walls"] if w["level"] == lid]
            if mine:
                return mine
        return []

    @staticmethod
    def _frame_below(doc: dict, level_id: str) -> tuple[list, list]:
        """The beams and columns of the level right UNDER this one — the
        frame that holds its floor ([], [] on the lowest)."""
        elev = model.elevations(doc["levels"], doc["project"]["ground_level"]
                                if model.has_project(doc) else 0.0)
        z = {lv["id"]: e for lv, e in zip(doc["levels"], elev)}
        under = [k for k in z if level_id in z and z[k] < z[level_id] - 1e-6]
        if not under:
            return [], []
        lid = max(under, key=lambda k: z[k])
        mine = [e for e in doc.get("structure") or [] if e.get("level") == lid]
        return ([e for e in mine if e["type"] == "beam"],
                [e for e in mine if e["type"] == "column"])

    def tool_element(self) -> str | None:
        """The element (wall, column, beam, slab…) whose drawing tool is
        out, or None."""
        tool = getattr(self.viewport, "active_tool", None)
        if not compat.ours(tool):
            return None
        return getattr(tool, "axq_element", None)

    #: the tools' classes → their quick-help card (quickhelp.QUICK)
    QUICK_BY_CLASS = {"WallEditTool": "wall_edit", "SlabEditTool": "slab_edit",
                      "PlotEditTool": "point_edit", "DigEditTool": "point_edit",
                      "WallArc3Tool": "wall_curve",
                      "WallArcCentreTool": "wall_curve",
                      "WallCircleTool": "wall_curve",
                      "OpeningTool": "opening", "RampTool": "ramp",
                      "StairTool": "ramp", "BeamTool": "beam",
                      "ColumnTool": "column", "ColumnDrawTool": "column",
                      "GuardTool": "guard", "GuardPickTool": "guard_pick",
                      "GlazingTool": "glazing", "VoidPickTool": "glazing",
                      "StreetTool": "street", "PlotSideTool": "street",
                      "ProfileTool": "profile", "RoomPickTool": "profile",
                      "CopyTool": "copy", "CopyRoomTool": "copy",
                      "CopyPathTool": "copy", "CopyLineTool": "copy",
                      "CopyPickTool": "copy",
                      "FacePickTool": "profile", "CopyFaceTool": "copy",
                      "ElementPickTool": "profile",
                      "ProfileFacePickTool": "profile", "PathTool": "profile",
                      "LinePickTool": "profile"}

    def quick_topic(self) -> str | None:
        """The quick-help card for what is in use now (quickhelp.py): the
        ArchXQ tool out — else, with the Select tool, the radial menu, the
        grips of the one element selected, an elevation / X-ray. The AI's
        window, open, comes first: its card says what can be asked."""
        win = getattr(self, "_ai_window", None)
        if win is not None and win.isVisible():
            return "ai"
        tool = getattr(self.viewport, "active_tool", None)
        if compat.ours(tool):
            name = type(tool).__name__
            if name in self.QUICK_BY_CLASS:
                return self.QUICK_BY_CLASS[name]
            el = getattr(tool, "axq_element", None)
            if el == "slab":
                return "slab_hole" if getattr(tool, "noun", "") == "Opening" \
                    else "slab"
            if el == "wall":
                return "wall"
            if el is None and self.current == "terrain":
                return "terrain"
            return None
        if not compat.selecting(self.viewport):
            return None
        ring = getattr(self, "radial", None)
        if ring is not None and ring.isVisible():
            return "radial"
        if self._grips.drag is not None or self.grip_targets():
            return "grips"
        if self.side_view is not None or (self.plan_on and self.xray):
            return "views"
        return None

    def wall_tool_out(self) -> bool:
        return self.tool_element() == "wall"

    @_project_first
    def start_wall_tool(self) -> None:
        """The shape picked in the options bar, drawing on the current
        level."""
        from .walltools import TOOLS
        shape = self.wall_opts["shape"]
        cls = TOOLS.get(shape)
        if cls is None:
            return
        _i, lv, z0 = self._work_level()
        self._wall_cache = self._live_walls(self.doc(), lv["id"])
        tool = cls(self._walls_done, self._wall_cancelled, z0,
                   lambda: self.wall_opts, lambda: self._wall_cache)
        tool.level_id = lv["id"]
        doc = self.doc()
        if self.has_plot(doc):               # the building's inside: the plot
            cs = doc["plot"]["corners"]
            tool.inside_ref = (sum(p[0] for p in cs) / len(cs),
                               sum(p[1] for p in cs) / len(cs))
        # a DXF under this level: its walls' two lines as «lanes» to trace
        # between (0.15.0, B8 — tracing.py); the layer walls come from, or all
        u = (doc.get("underlays") or {}).get(lv["id"])
        if u and u.get("segs") and shape == "chain":
            from . import tracing
            # (a line's layer is kept as its index in «layers»)
            want = u.get("layer") or ""
            k = (u.get("layers") or []).index(want) \
                if want in (u.get("layers") or []) else None
            segs = [s for s in u["segs"] if k is None or (len(s) > 4
                                                           and s[4] == k)]
            try:
                tool.lanes = tracing.lanes(segs)
            except Exception:  # noqa: BLE001 — no lanes: as always
                tool.lanes = None
        self.method = shape
        self._activate(tool)
        # the shape lit: drawing — after the click that brought us here
        # (refilling inside it would pull the clicked icon from under it)
        QTimer.singleShot(0, self._refill_options)
        name = next(t for v, _i, t in WALL_SHAPES if v == shape)
        compat.flash(self.viewport, f"Walls on «{lv['name']}» — "
                     f"{name.split(' — ')[0].lower()}", 4000)

    def _live(self, doc: dict) -> dict:
        """The document without the walls / structural elements whose
        group was deleted with the host's own tools (Delete key, eraser):
        they are gone, they must not come back at the next rebuild. (One
        that can't be built has no group, and stays.)"""
        from . import layerview as LV
        from . import structure as S
        from . import walls as W
        have = compat.built_ids(self.viewport)
        built = doc.get("built")
        # every eye off: no group because nothing is shown, not deleted
        shown_off = doc
        why_wall = lambda r: W.why_not(r) \
            or LV.nothing_shown(shown_off, "wall", r)
        why_el = lambda r: S.why_not(r) \
            or LV.nothing_shown(shown_off, r.get("type") or "slab", r)
        if built is None:               # an older file: the old rule
            if not have:
                return doc              # nothing built yet: keep it all
            gone = lambda r, why: r["id"] not in have and not why(r)
        else:
            # built once and its object gone = deleted — even when EVERY
            # one was deleted (his screen, 2026-10-05: walls deleted came
            # back when basements were added: no object left = «nothing
            # built yet» = keep it all). Never built: kept, it waits.
            built = set(built)
            gone = lambda r, why: r["id"] in built and r["id"] not in have \
                and not why(r)
        doc = dict(doc)
        doc["walls"] = [w for w in doc["walls"] if not gone(w, why_wall)]
        from . import autoslabs
        st = doc.get("structure") or []
        # an automatic slab deleted stays away (else the next rebuild made
        # it again)
        off = {autoslabs.key_of(e) for e in st
               if autoslabs.key_of(e) and gone(e, why_el)}
        if off:
            doc["auto_off"] = sorted(set(doc.get("auto_off") or []) | off)
        doc["structure"] = [e for e in st if not gone(e, why_el)]
        # an opening goes with its wall; a door / window deleted with the
        # host's tools leaves its HOLE — an Opening (a void), as the screen
        # shows it (his demo, 2026-10-16: he deleted a window to put a
        # glass grid in; the plan still drew the window and the hole shut
        # at the next change). Its own window's Delete closes it.
        walls = {w["id"]: w for w in doc["walls"]}
        ops = doc.get("openings") or []
        built_ops = set(built) if built is not None else set()

        def keep(o) -> bool:
            if o["wall"] not in walls:
                return False
            if o["kind"] == "void" or o["id"] in have:
                return True
            # not built: it no longer fits its wall — kept, it waits
            w = walls[o["wall"]]
            return S.opening_room(o, w, ops, self._wall_height(w)) is not None

        names = {o.get("name") for o in ops}

        def hole(o) -> dict:
            if o["kind"] in ("door", "window") and o["id"] in built_ops \
                    and o["id"] not in have and o["wall"] in walls:
                n = 1
                while f"Opening {n}" in names:
                    n += 1
                names.add(f"Opening {n}")
                return {k: o[k] for k in ("id", "wall", "pos", "w", "h",
                                          "sill", "swing") if k in o} | {
                    "kind": "void", "name": f"Opening {n}"}
            return o
        doc["openings"] = [o for o in (hole(o) for o in ops) if keep(o)]
        return doc

    def _live_walls(self, doc: dict, level_id: str) -> list[dict]:
        """The level's walls still standing (see ``_live``)."""
        return [w for w in self._live(doc)["walls"]
                if w["level"] == level_id]

    @staticmethod
    def _with_built(doc: dict) -> dict:
        """What is built now joins «built»: deleted later with the host's
        tools, it stays deleted (see _live)."""
        from . import structure as S
        from . import walls as W
        made = {w["id"] for w in doc.get("walls") or [] if not W.why_not(w)}
        made |= {e["id"] for e in doc.get("structure") or []
                 if not S.why_not(e)}
        made |= {o["id"] for o in doc.get("openings") or []}
        keep = {r["id"] for r in (doc.get("walls") or [])
                + (doc.get("structure") or []) + (doc.get("openings") or [])}
        return dict(doc, built=sorted((set(doc.get("built") or []) | made)
                                      & keep))

    #: the elements nothing else is built from: changed alone, only their
    #: own groups are rebuilt (compat.commit_some)
    LONE = ("guard", "glazing")

    def _lone_changes(self, old: dict, new: dict):
        """The ids of the low walls / glass grids that differ between two
        documents — when NOTHING else does (walls, openings, levels, plot,
        materials, the other elements); else None (rebuild it all)."""
        skip = ("structure", "built")
        keys = (set(old) | set(new)) - set(skip)
        if any(old.get(k) != new.get(k) for k in keys):
            return None
        a = {e["id"]: e for e in old.get("structure") or []}
        b = {e["id"]: e for e in new.get("structure") or []}
        diff = {i for i in set(a) | set(b) if a.get(i) != b.get(i)}
        if not diff:
            return None
        for i in diff:
            for e in (a.get(i), b.get(i)):
                if e is not None and e.get("type") not in self.LONE:
                    return None
        # a glass grid's own Opening is in «openings» (equal here): fine
        return diff

    def _commit_all(self, doc: dict) -> None:
        """THE way the building is stored: every wall and structural
        element rebuilt from ``doc`` — one Ctrl+Z. The excavations' slabs
        are made / followed first (autoslabs)."""
        from . import autoslabs, fitwalls
        before = self.doc()
        if self._touches_locked(before, doc):
            self.locked_note()
            return
        deep_was = self._deepest(before)
        # a column of a «Column row» changed on its own (the options bar,
        # the AI, a batch): the change goes to the row, all made again —
        # else the row's next edit would undo it (colrows.settle)
        if doc.get("colrows"):
            try:
                from . import colrows
                doc = colrows.prune(doc)
                doc, again = colrows.settle(before, doc)
                # the levels, the excavations, the ground changed: the rows
                # with a beam at their foot / middle follow (their span)
                if any(before.get(k) != doc.get(k)
                       for k in ("levels", "digs", "project")):
                    again += [r["id"] for r in doc["colrows"]
                              if r["id"] not in again
                              and (colrows.span_beams(r)
                                   or colrows.what_of(r) == "footings")]
                for rid in again:
                    doc, _info = self._row_rebuild(doc, rid)
            except Exception:  # noqa: BLE001 — never block a commit
                compat.log_error("colrows.settle")
        # the walls of YOUR types built with the type's layers NOW: the wall
        # tool gives only the type's id — they came out one plain block in
        # the core's colour, the layers only on reading the file again (his
        # screen, 31/10: «Exterior de teste»)
        types = {t["id"]: t for t in doc.get("wall_types") or []}
        if any(w.get("type") in types for w in doc.get("walls") or ()):
            doc = dict(doc, walls=[
                model.typed(w, types[w["type"]])
                if w.get("type") in types and not w.get("cw") else w
                for w in doc["walls"]])
        doc = self._with_profiles(doc)
        # slabs / roofs made over the walls follow them (0.13.1)
        try:
            doc, _n = fitwalls.sync(before, doc)
        except Exception:  # noqa: BLE001 — never block a commit
            pass
        doc = self._with_built(autoslabs.sync(self._with_mats(doc),
                                              model.elevations))
        some = self._lone_changes(before, doc)
        if some:
            # only low walls / glass grids changed (nothing depends on them):
            # only their groups made again (his test, 2026-10-15: every chip
            # and bar «pulsed» — the whole building, ~0.7 s)
            compat.commit_some(self.viewport, self.app.key, doc,
                               model.elevations, compat.level_layer, some)
        else:
            compat.commit_build(self.viewport, self.app.key, doc,
                                model.elevations, compat.level_layer)
            self._ground_follows(deep_was)
        self._apply_parts()              # «Show», and what hides in walls
        lv_id = getattr(getattr(self.viewport, "active_tool", None),
                        "level_id", None)
        if lv_id:
            self._wall_cache = self._live_walls(self.doc(), lv_id)
        self._outline_soon()

    # ---- IngeTrazo 0.6.0's lock --------------------------------------------------
    #: the lists of the document whose records are elements with groups
    _LOCK_LISTS = ("walls", "structure", "openings", "guards", "streets",
                   "glazing", "profiles", "copies", "spaces")

    def _touches_locked(self, before: dict, doc: dict) -> bool:
        """``doc`` changes or drops an element whose group is LOCKED (its
        own lock, or its layer's) — refused, as the host refuses to edit
        it. A rebuild a neighbour causes is not this: the locked one's
        record is the same, and its new group keeps the lock."""
        vp = self.viewport
        ids = {compat._rec(g).get("id") for g in vp.scene.groups
               if compat.kind_of(g) and compat.locked(vp, g)} - {None}
        if not ids:
            return False
        for key in self._LOCK_LISTS:
            was = {r.get("id"): r for r in before.get(key) or ()
                   if isinstance(r, dict) and r.get("id") in ids}
            if not was:
                continue
            now = {r.get("id"): r for r in doc.get(key) or ()
                   if isinstance(r, dict) and r.get("id") in was}
            if any(now.get(i) != r for i, r in was.items()):
                return True
        return False

    def locked_note(self) -> None:
        compat.flash(self.viewport, "Locked — right-click ▸ Unlock to "
                     "change it", 5000)

    @staticmethod
    def _deepest(doc: dict):
        from . import structure as S
        try:
            return S.deepest_below(doc, model.elevations)
        except Exception:  # noqa: BLE001
            return None

    def _ground_follows(self, deep_was) -> None:
        """Footings / column feet went deeper (or back up): the terrain's
        ground goes down under them — rebuilt in the SAME Ctrl+Z (a
        customer's report, 2026-10-13: footings poked out under it)."""
        from . import terrain as T
        doc = self.doc()
        if not self.has_plot(doc):
            return
        deep = self._deepest(doc)
        same = deep == deep_was or (deep is not None and deep_was is not None
                                    and abs(deep - deep_was) < 1e-4)
        # a file from before the fix: its ground stops above its footings —
        # set right at the first change of its structure
        bottom = compat.terrain_bottom(self.viewport, doc)
        short = deep is not None and bottom is not None \
            and bottom > deep - T.MIN_THICK + 1e-3
        if same and not short:
            return
        hist = self.viewport.history
        first = hist.undo_stack[-1] if hist.undo_stack else None
        compat.commit_terrain(self.viewport, self.app.key, doc, PLOT_Z,
                              PLOT_COLOR)
        if first is not None:
            compat.join_last_steps(hist, first)

    def _walls_done(self, recs: list[dict]) -> None:
        from . import walls as W
        i, lv, z0 = self._work_level()
        doc = self._live(self.doc())
        o = self.wall_opts
        height = "level" if o["height"] == "level" else float(o["h"])
        mine = [w for w in doc["walls"] if w["level"] == lv["id"]]
        out, refused, carried = [], [], 0
        for k, r in enumerate(recs):
            others = mine + recs[:k] + recs[k + 1:]
            r = W.settle(r, others)          # 2 cm short of a wall: onto it
            # carrying ON a wall straight takes its thickness (a step half
            # way along a straight run reads as a mistake); a branch keeps
            # the one chosen
            t = W.continues(r, mine)
            if t is not None and abs(t - r["t"]) > 1e-6:
                r = dict(r, t=t)
                carried += 1
            why = W.why_not(r)
            if why:
                refused.append(why)
                continue
            r = {key: v for key, v in r.items() if key not in ("id", "name")}
            if o.get("cw"):                  # a curtain wall's own
                from . import curtain as _CW
                r.update(cw=True, **{k: o.get(k, v)
                                     for k, v in _CW.DEFAULTS.items()})
            out.append(dict(r, level=lv["id"], height=height, base=0.0))
        # touching a wall's face by its corner = joining that corner
        out = W._to_corner(mine + out)[len(mine):]
        if not out:
            compat.flash(self.viewport, (refused[0] if refused else
                                         "Nothing to build") + " — draw it "
                         "again", 5000)
            return
        if not self._ok_with_setbacks(doc, [q for r in out
                                            for q in W.points_of(r)],
                                      noun="wall"):
            return                           # the tool stays: draw again
        made = model.new_walls(doc["walls"], out)
        # (a wall deleted with the host's tools leaves the document too)
        doc["walls"] = doc["walls"] + made
        self._commit_all(doc)
        self._wall_cache = self._live_walls(self.doc(), lv["id"])
        n = len(made)
        compat.flash(self.viewport, f"{n} wall{'s' if n > 1 else ''} on "
                     f"«{lv['name']}» — Ctrl+Z undoes "
                     f"{'them' if n > 1 else 'it'}"
                     + (f" · {carried} took the thickness of the wall "
                        "they carry on" if carried else "")
                     + (f" ({len(refused)} too short, left out)"
                        if refused else ""), 6000)
        self._outline_soon()

    #: Tools ▸ Along a path: its tools → their libraries
    HELD_LIBRARY = {"Profile along": "profile", "Copy along": "copy"}

    def _held_library(self) -> str | None:
        """The library that stays on the right after its tool is put away
        (Esc, Select), and its tool lit on top, until another tool or a phase
        is picked (his call, 06/11): it has no element of its own to fall back
        to, and the outliner took its place."""
        return self.HELD_LIBRARY.get(self.method) \
            if self.element == "along" else None

    def _wall_cancelled(self) -> None:
        if self._held_library() is None:
            self.method = None
        compat.back_to_select(self.viewport)
        self.refresh()                       # the shape's icon goes dark

    def start_align_tool(self, only=()) -> None:
        """Align, as Revit's (0.15.0 — align.py): a reference edge, then
        the edge of the element to line up. ``only``: the ids it may move
        (the radial menu's selection) — on their level."""
        from .walledit import AlignTool
        _i, lv, z0 = self._work_level()
        lid = lv["id"]
        if only:
            doc = self.doc()
            rec = next((r for r in doc["walls"] + doc["structure"]
                        if r["id"] in set(only)), None)
            if rec is not None and rec.get("level") != lid:
                ids_ = [r["id"] for r in doc["levels"]]
                if rec.get("level") in ids_:
                    lid = rec["level"]
                    elev = model.elevations(
                        doc["levels"], doc["project"]["ground_level"]
                        if model.has_project(doc) else 0.0)
                    z0 = elev[ids_.index(lid)]

        def store(doc, kind, eid):
            self._commit_all(doc)
            if kind == "wall":
                self._wall_cache = self._live_walls(self.doc(), lid)

        tool = AlignTool(lambda: self._live(self.doc()), lid, store,
                         self._wall_cancelled, z0, only)
        tool.level_id = lid
        self.method = "Align"
        self._activate(tool)

    def start_wall_op_tool(self, name: str) -> None:
        """Walls › Edit walls › Split / Trim / Extend (0.15.0, B1 —
        wallops.py): on the current level's straight walls."""
        from .walledit import WallSplitTool, WallTrimTool, _straight
        _i, lv, z0 = self._work_level()
        if not any(_straight(w) for w in self._live_walls(self.doc(),
                                                          lv["id"])):
            compat.flash(self.viewport, f"No straight walls on «{lv['name']}»",
                         4000)
            return
        lid = lv["id"]

        def walls():
            return self._live_walls(self.doc(), lid)

        if name == "Split":
            def parts():
                return walls(), list(self.doc().get("openings") or [])

            def store(new_walls, new_ops):
                from . import materials
                doc = self._live(self.doc())
                # the second half wears what the wall wore (his Short, 31/10:
                # half of it came back bare) — its source: the wall it
                # starts where it ends
                old = {w["id"] for w in doc["walls"]}
                pairs = []
                for w in new_walls:
                    if w["id"] in old:
                        continue
                    src = next((s for s in new_walls if s["id"] in old
                                and s.get("b") == w.get("a")), None)
                    if src is not None:
                        pairs.append((src["id"], w["id"]))
                doc["walls"] = [w for w in doc["walls"]
                                if w["level"] != lid] + new_walls
                doc["openings"] = new_ops
                doc = materials.carry(doc, pairs)
                self._commit_all(doc)
                self._wall_cache = self._live_walls(self.doc(), lid)
            tool = WallSplitTool(parts, store, self._wall_cancelled, z0)
        else:
            tool = WallTrimTool(
                walls, lambda new: self._commit_level_walls(lid, new),
                self._wall_cancelled, z0)
        tool.level_id = lid
        self.method = name
        self._activate(tool)

    def start_wall_edit_tool(self) -> None:
        """Walls › Edit walls › Move points: a straight wall's ends on the
        current level (walledit) — the walls meeting there follow."""
        from .walledit import WallEditTool, _straight
        _i, lv, z0 = self._work_level()
        if not any(_straight(w) for w in self._live_walls(self.doc(),
                                                          lv["id"])):
            compat.flash(self.viewport, f"No straight walls on «{lv['name']}»"
                         " to edit", 4000)
            return
        tool = WallEditTool(
            lambda: self._live_walls(self.doc(), lv["id"]),
            lambda walls: self._commit_level_walls(lv["id"], walls),
            self._wall_cancelled, z0)
        tool.level_id = lv["id"]
        self.method = "Move points"
        self._activate(tool)
        self.strip.fill(self.element, self.method)

    # ---- Structure: each element's own window ---------------------------------------
    @staticmethod
    def element_of(group) -> str | None:
        """The structural element (its id) a group stands for, or None."""
        if compat.kind_of(group) not in ("column", "beam", "slab",
                                         "footing", "roof", "ramp", "stair",
                                         "guard", "glazing", "street",
                                         "profile", "copy"):
            return None
        rec = (getattr(group, "ext", None) or {}).get(compat.EXT_KEY) or {}
        # a room's floor on a layered slab: its own window (its material)
        return rec.get("floor") or rec.get("id")

    # ---- «Select its row / all … on this level» (his call, 2026-10-09) ----------------
    PLURALS = {"door": "doors", "window": "windows", "void": "voids",
               "wall": "walls"}

    def _select_picks(self, rid: str) -> list:
        """[(text, ids)] — what can be selected with this element: a
        column's rows; every one of its kind on its level. Selected, the
        options bar and the library change them all at once (one Ctrl+Z):
        you SEE what will change before changing it."""
        from . import structure as S
        doc = self.doc()
        rec = self._lib_record(rid)
        if rec is None:
            return []
        out = []
        if rec in doc["openings"]:
            wl = {w["id"]: w["level"] for w in doc["walls"]}
            lv = wl.get(rec["wall"])
            same = [o["id"] for o in doc["openings"]
                    if o["kind"] == rec["kind"] and wl.get(o["wall"]) == lv]
            noun = self.PLURALS.get(rec["kind"], "openings")
        elif rec in doc["walls"]:
            same = [w["id"] for w in doc["walls"]
                    if w["level"] == rec["level"]]
            noun = "walls"
        else:
            st = doc["structure"]
            if rec["type"] == "footing" and rec.get("row"):
                from . import colrows
                grp = colrows.of_column(doc, rec)
                if grp is not None:          # its «Footing row» (the group)
                    ids = [e["id"] for e in colrows.members(doc, grp)]
                    out.append((tr("Select «{r}» ({n} footings)",
                                   r=grp["name"], n=len(ids)), ids))
            if rec["type"] == "column":
                from . import colrows
                grp = colrows.of_column(doc, rec)
                if grp is not None:          # its «Column row» (the group)
                    ids = [e["id"] for e in colrows.members(doc, grp)]
                    out.append((tr("Select «{r}» ({n} columns)",
                                   r=grp["name"], n=len(ids)), ids))
                for ids in S.rows_of(rec, st):
                    out.append((tr("Select its row ({n} columns)",
                                   n=len(ids)), ids))
            same = [e["id"] for e in st if e["type"] == rec["type"]
                    and e["level"] == rec["level"]]
            noun = S.LABEL[rec["type"]].lower() + "s"
        if len(same) > 1:
            out.append((tr(f"Select all {noun} on this level")
                        + f" ({len(same)})", same))
        # the whole building (a tower repeats its floors — L1, 2026-10-31)
        every = self._same_kind(rec, doc)
        if len(every) > len(same) and len(every) > 1:
            out.append((tr(f"Select all {noun} in the project")
                        + f" ({len(every)})", every))
        return out

    @staticmethod
    def _same_kind(rec: dict, doc: dict) -> list:
        """Every one of ``rec``'s kind in the project (its ids)."""
        if rec in doc["openings"]:
            return [o["id"] for o in doc["openings"]
                    if o["kind"] == rec["kind"]]
        if rec in doc["walls"]:
            return [w["id"] for w in doc["walls"]]
        return [e["id"] for e in doc["structure"]
                if e["type"] == rec.get("type")]

    # ---- One window, the whole selection (PLANO_EDICAO_LOTE.md, L1) ------------------
    def _batch_ids(self, rid: str) -> tuple[list, int]:
        """(the ids selected of ``rid``'s kind — itself among them, how
        many of another kind are selected too). ``rid`` not selected: ([],
        0) — its window is its own."""
        by, mine = {}, None
        for g in compat.selected_groups(self.viewport):
            r = compat._rec(g)
            k = compat.kind_of(g)
            if k == "opening":
                k = r.get("okind")
            if not k or not r.get("id") or r.get("floor"):
                continue
            by.setdefault(k, []).append(r["id"])
            if r["id"] == rid:
                mine = k
        if mine is None:
            return [], 0
        ids = list(dict.fromkeys(by[mine]))
        return ids, sum(len(set(v)) for k, v in by.items() if k != mine)

    def _ids_all_in_row(self, rid: str, ids) -> bool:
        """Whether ``ids`` are all elements of ``rid``'s column / footing
        row (beams and footings of a column row count too)."""
        from . import colrows
        try:
            doc = self.doc()
            el = next((e for e in doc["structure"] if e["id"] == rid), None)
            row = colrows.of_column(doc, el) if el is not None else None
            if row is None:
                return False
            mine = {e["id"] for e in doc["structure"]
                    if e.get("row") == row["id"]}
            return set(ids) <= mine
        except Exception:  # noqa: BLE001 — as before: the selection's
            return False

    def _batch_window(self, dlg, family: str, rid: str, apply_one,
                      noun: str, reopen):
        """The apply to give ``dlg``: one element's, or — more of its kind
        selected — the selection's: what is changed in it goes to all.
        With one only: its «Select all …» buttons on top."""
        from PySide6.QtWidgets import QLabel, QPushButton
        ids, others = self._batch_ids(rid)
        lay = dlg.layout()
        if family == "struct" and len(ids) >= 2 and not others \
                and self._ids_all_in_row(rid, ids):
            # the selection IS its row (his test, 07/11/2026: after a first
            # Apply the row is selected; «Apply to the 98 selected» copied
            # width/depth only and dropped the Row part): the row's own
            # window already changes them all
            ids = [rid]
        if len(ids) < 2:
            if family == "struct":           # (its own buttons already)
                return apply_one
            for i, (text, sel) in enumerate(self._select_picks(rid)):
                b = QPushButton(text)
                b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet(self.BATCH_LINK)
                b.setToolTip(tr("Select them — this window then changes "
                                "them all at once (one Ctrl+Z)"))

                def go(_c=False, s=sel):
                    dlg.reject()
                    self._reopen_on(s, reopen)
                b.clicked.connect(go)
                lay.insertWidget(i, b)
            return apply_one
        _a, base = dlg.result_data()
        box = {"base": copy.deepcopy(base)}
        text = tr("{n} {noun} selected — what you change here goes to all "
                  "{n}. Name and place stay each one's own.", n=len(ids),
                  noun=tr(noun))
        if others:
            text += " " + tr("({m} of another kind left out)", m=others)
        mixed = self._batch_mixed(dlg, family, ids, base)
        if mixed:
            text += "\n" + tr("Different among them: {keys} — left as it "
                              "is, each keeps its own.",
                              keys=", ".join(tr(k) for k in mixed))
        lab = QLabel(text)
        lab.setObjectName("axqBatchNote")
        lab.setWordWrap(True)
        lab.setStyleSheet(self.BATCH_NOTE)
        lay.insertWidget(0, lab)
        dlg.setWindowTitle(f"{dlg.windowTitle()} · {len(ids)}")
        place = [getattr(dlg, f, None) for f in ("f_name", "f_pos", "f_len")]
        place += list((getattr(dlg, "f_ends", None) or {}).values())
        for w in place:
            if w is not None and hasattr(w, "setEnabled"):
                w.setEnabled(False)
                w.setToolTip(tr("One at a time — select only this one"))
        # L2 (his rule, 2026-10-31): the change is SEEN on this one only;
        # «to all of them» is a button of its own, named — and «Only this one»
        self._batch_buttons(dlg, box, len(ids), noun)

        def apply(new: dict) -> None:
            if box.pop("one", False):
                apply_one(new)
                return
            from . import livewin
            with livewin.busy(self.window, tr(
                    "Applying to the {n} {noun} selected…", n=len(ids),
                    noun=tr(noun))):
                self._apply_batch(family, ids, box["base"], new, noun)
            box["base"] = copy.deepcopy(new)
        return apply

    def _batch_buttons(self, dlg, box: dict, n: int, noun: str) -> None:
        """A window over N selected: OK reads «Apply to the N selected», and
        «Only this one» beside it (the one clicked, the one seen live)."""
        from PySide6.QtWidgets import QDialogButtonBox, QLabel, QPushButton
        okb = dlg.findChild(QPushButton, "axqOk")
        bb = okb.parent() if okb is not None else None
        if not isinstance(bb, QDialogButtonBox):
            return
        okb.setText(tr("Apply to the {n} selected", n=n))
        okb.setToolTip(tr("What you changed goes to all {n} {noun} — the "
                          "rest of each stays its own", n=n, noun=tr(noun)))
        one = QPushButton(tr("Only this one"))
        one.setToolTip(tr("Only the one you clicked — the one you see "
                          "changing — the others stay as they are"))

        def only() -> None:
            box["one"] = True
            okb.click()
            if dlg.isVisible() and not getattr(dlg, "_axq_stay", False):
                box.pop("one", None)          # a check said no
        one.clicked.connect(only)
        bb.addButton(one, QDialogButtonBox.ActionRole)
        lab = dlg.findChild(QLabel, "axqBatchNote")
        if lab is not None:
            lab.setText(lab.text() + "\n" + tr(
                "You see the change on this one; «Apply to the {n} selected» "
                "takes it to all of them.", n=n))

    #: a mixed value's field label (the banner names them)
    BATCH_LABELS = {"w": "Width", "h": "Height", "sill": "Sill",
                    "t": "Thickness", "height": "Height", "base": "Base",
                    "d": "Depth", "angle": "Angle", "slope": "Slope",
                    "offset": "Offset", "overhang": "Overhang",
                    "trim_w": "Trim width", "trim_d": "Trim depth",
                    "rise": "Rise", "top_w": "Top width",
                    "shape": "Shape", "op": "Type", "leaves": "Leaves",
                    "stype": "Type", "type": "Type", "align": "Alignment"}
    BATCH_MIXED = ("QAbstractSpinBox, QComboBox { border: 1px solid "
                   "#d9a441; border-radius: 3px; }")

    def _batch_mixed(self, dlg, family: str, ids, base: dict) -> list:
        """The labels of the values that differ among the selected — their
        fields outlined amber: left as they are, each keeps its own."""
        from . import batch as B
        doc = self.doc()
        pool = (doc["openings"] if family == "opening" else doc["walls"]
                if family == "wall" else doc["structure"])
        recs = [r for r in pool if r["id"] in set(ids)]
        skip = B.NEVER | B.NEVER_BY.get(family, frozenset())
        out = []
        for k in base:
            if k.startswith("_") or k in skip or k not in self.BATCH_LABELS:
                continue
            vals = {repr(r.get(k)) for r in recs}
            if len(vals) < 2:
                continue
            label = self.BATCH_LABELS[k]
            if label not in out:
                out.append(label)
            w = (getattr(dlg, "fields", None) or {}).get(k) or getattr(
                dlg, "f_h" if k == "height" else f"f_{k}", None)
            w = getattr(w, "field", w)
            if w is not None and hasattr(w, "setStyleSheet"):
                w.setStyleSheet(self.BATCH_MIXED)
                w.setToolTip(tr("Different among the selected — left as it "
                                "is, each keeps its own"))
        return out

    BATCH_NOTE = ("QLabel { background: rgba(47, 125, 246, 40); color: "
                  "#dfe8f7; border: 1px solid #2f7df6; border-radius: 4px; "
                  "padding: 6px 8px; }")
    BATCH_LINK = ("QPushButton { text-align: left; color: #8fb8f9; "
                  "background: transparent; border: none; padding: 2px; }"
                  "QPushButton:hover { color: #2f7df6; "
                  "text-decoration: underline; }")

    def _reopen_on(self, ids, reopen) -> None:
        """«Select all …» in a window: those selected, the window again —
        now changing them all."""
        def later() -> None:
            compat.select_ids(self.viewport, set(ids))
            self._library_show()
            reopen()
        QTimer.singleShot(0, later)

    def _apply_batch(self, family: str, ids: list, base: dict, new: dict,
                     noun: str) -> None:
        """What the window changed (``base`` → ``new``) on every one of
        ``ids``, each by its own rules — one Ctrl+Z. The ones it doesn't
        fit stay as they were, and are named."""
        from . import batch as B
        from . import structure as S
        from . import walls as W
        doc = self._live(self.doc())
        if family == "wall":
            new, _named, _every = self._wall_types(doc, new)
        elif family == "struct":
            new = dict(new)
            new.pop("_type_all", None)
            named = new.pop("_new_type", None)
            new.pop("_host", None)
            if named:
                doc["slab_types"] = self._typed(
                    doc.get("slab_types"), new, "stype", named)
        ch = B.changes(base, new, family)
        mat = getattr(self, "_pending_mat", None)
        self._pending_mat = None
        done, refused = [], []
        want = set(ids)
        if family == "opening":
            walls = {w["id"]: w for w in doc["walls"]}
            ops = list(doc["openings"])
            for i, o in enumerate(ops):
                if o["id"] not in want:
                    continue
                r = new if o["id"] == new["id"] else B.spread(o, ch, family)
                wall = walls.get(r["wall"])
                others = [x for x in ops if x["id"] != r["id"]]
                why = "its wall is gone" if wall is None else S.opening_room(
                    r, wall, others, self._wall_height(wall))
                if why:
                    refused.append((o["name"], why))
                    continue
                ops[i] = r
                done.append(r["id"])
            doc["openings"] = ops
        else:
            key = "walls" if family == "wall" else "structure"
            check = W.why_not if family == "wall" else S.why_not
            out = []
            for e in doc[key]:
                if e["id"] not in want:
                    out.append(e)
                    continue
                r = new if e["id"] == new["id"] else B.spread(e, ch, family)
                if r.get("type") == "roof" and "kind" in ch:
                    r = dict(r, corners=S.roof_corners(r["corners"],
                                                       r["kind"]))
                why = check(r)
                if why:
                    refused.append((e["name"], why))
                    out.append(e)
                    continue
                out.append(r)
                done.append(r["id"])
            doc[key] = out
        if mat is not None and done:
            from . import materials
            for i in ([new["id"]] if mat.get("all") else done):
                doc = materials.merge(doc, dict(mat, id=i))
        if done:
            self._commit_all(doc)
            if family == "wall":
                self._wall_cache = self._live_walls(self.doc(), new["level"])
        # all still SELECTED: an Apply's window comes back on them all
        compat.select_ids(self.viewport, set(ids))
        QTimer.singleShot(0, self._library_show)
        compat.flash(self.viewport, B.summary(done, refused, noun),
                     8000 if refused else 5000)

    def select_these(self, ids) -> None:
        compat.select_ids(self.viewport, set(ids))
        self._library_show()
        compat.flash(self.viewport, tr(
            "{n} selected — the library, the bar on top or a double-click "
            "(its window) change them all (one Ctrl+Z)", n=len(ids)), 5000)

    def _add_picks(self, sub, rid: str) -> None:
        """The «Select …» entries of an element's right-click menu."""
        picks = self._select_picks(rid)
        if picks:
            sub.addSeparator()
        for text, ids in picks:
            a = sub.addAction(text)
            a.triggered.connect(lambda _=False, i=ids: QTimer.singleShot(
                0, lambda: self.select_these(i)))

    def edit_element(self, el_id: str) -> None:
        """A column's / beam's / slab's / footing's window (modal). Apply
        = one Ctrl+Z."""
        from .dialogs import ElementDialog
        if str(el_id).startswith("floor:"):  # a room's floor (its material)
            self.edit_floor(el_id)
            return
        doc = self.doc()
        el = next((e for e in doc["structure"] if e["id"] == el_id), None)
        if el is None or self._pro_only(el.get("type")):
            return
        lv = next((r for r in doc["levels"] if r["id"] == el["level"]), None)
        if lv is None:
            return
        self.hub.close_sub()
        if el["type"] == "ramp":             # its own window (ramps.py)
            self.edit_ramp(el)
            return
        if el["type"] == "stair":            # its own window (stairs.py)
            self.edit_stair(el)
            return
        if el["type"] == "guard":            # its own window (guards.py)
            self.edit_guard(el)
            return
        if el["type"] == "glazing":          # its own window (glazing.py)
            self.edit_glazing(el)
            return
        if el["type"] == "street":           # its own window (streets.py)
            self.edit_street(el)
            return
        if el["type"] == "profile":          # its own window (along.py)
            self.edit_profile(el)
            return
        if el["type"] == "copy":             # its own window (along.py)
            self.edit_copy(el)
            return
        picks = self._select_picks(el_id)
        from . import colrows
        row = colrows.of_column(doc, el)
        if row is not None:
            ro = colrows.opts_of(row.get("opts"))
            row = dict(row, n=len(colrows.members(self._live(doc), row)),
                       bw_auto=colrows._sizes(ro)[1],
                       what=colrows.what_of(row),
                       align_now=colrows.align_of(
                           row["path"], row.get("closed"),
                           colrows.geo(row, ro), self._pits(doc)))
        dlg = ElementDialog(el, lv, self.window,
                            picks=[text for text, _ids in picks],
                            types=self.doc().get("slab_types") or [],
                            row=row)
        self._mat_tab(dlg, el["type"], el_id)
        self._layer_eyes(dlg, el_id)
        from . import structure as S
        apply = self._batch_window(dlg, "struct", el_id, self.apply_element,
                                   S.LABEL[el["type"]].lower() + "s",
                                   lambda: self.edit_element(el_id))
        self._in_place(dlg, apply)
        if not dlg.exec():
            return
        action, new = dlg.result_data()
        self._mat_take(dlg, action)
        if action.startswith("pick:"):       # «Select its row / all …»
            # …and the window again, now changing them all (L1)
            self._reopen_on(picks[int(action[5:])][1],
                            lambda: self.edit_element(el_id))
        elif action == "delete":
            self.delete_element(el_id)
        elif action == "hide":
            self.hide_element(el_id, el["name"])
        else:
            apply(new)
            self._again(dlg, lambda: self.edit_element(el_id))

    def _apply_row_column(self, new: dict) -> None:
        """A «Column row»'s column, from its window: its sizes, height, base
        and capital — its turn, as a change — and the window's «Row» part go
        to the ROW, every column of it made again (one Ctrl+Z). Its name
        stays its own."""
        from . import colrows
        from . import structure as S
        new = dict(new)
        layout = new.pop("_row", None)
        why = S.why_not(new)
        if why:
            compat.flash(self.viewport, f"«{new['name']}» not changed — "
                         f"{why}", 6000)
            return
        doc = self._live(self.doc())
        old = next((e for e in doc["structure"] if e["id"] == new["id"]),
                   None)
        row = colrows.of_column(doc, old)
        if old is None:
            # its element is gone — the window stayed open while the row
            # was made again without it (his test, 07/11/2026: Pads + strip
            # → Strip, the pad of the window went; Apply did nothing after):
            # the ROW still takes the window
            row = colrows.find(doc, new.get("row"))
            if row is not None and colrows._prim(row) == new.get("type"):
                old = dict(new)
            else:
                row = None
        if old is None or row is None:
            compat.flash(self.viewport, tr("That row is gone — nothing "
                                           "changed"), 5000)
            return
        ro = colrows.opts_of(row.get("opts"))
        if layout and ro["align"] == "auto" \
                and layout.get("align") == colrows.align_of(
                    row["path"], row.get("closed"), colrows.geo(row, ro),
                    self._pits(doc)):
            layout = dict(layout, align="auto")   # (as it stands: no change)
        foots = colrows.what_of(row) == "footings"
        r2 = (colrows.from_footing if foots else colrows.from_column)(
            row, old, new, layout)
        doc["colrows"] = [r2 if r["id"] == row["id"] else r
                          for r in doc["colrows"]]
        doc["structure"] = [dict(e, name=new["name"]) if e["id"] == new["id"]
                            else e for e in doc["structure"]]
        doc, info = self._row_rebuild(doc, row["id"])
        self._commit_all(doc)
        # what the window chose is the NEXT row's too — the bar shows it
        # (his test, 07/11/2026: the 2nd row came «By count 3», not the
        # «By spacing 4.70» of the 1st one's window)
        try:
            ro = colrows.opts_of(info["row"].get("opts"))
            if foots:                        # the footings bar
                fo = self.foot_opts
                for k in colrows.LAYOUT_KEYS:
                    fo[k] = copy.deepcopy(ro[k])
                fo.update(ftype=ro["foots"]["type"], w=ro["foots"]["pw"],
                          sw=ro["foots"]["sw"], d=ro["foots"]["d"],
                          pd=ro["foots"]["pd"])
            else:
                for k in colrows.OPT_KEYS:
                    if k in ("beams", "foots"):
                        self.col_opts[k] = copy.deepcopy(ro[k])
                    elif k in ro and k != "angle":  # (a turn: the row's own)
                        self.col_opts[k] = copy.deepcopy(ro[k])
            QTimer.singleShot(0, self._refill_options)
        except Exception:  # noqa: BLE001 — the row is made: never block it
            compat.log_error("row window → bar")
        ids = {e["id"] for e in colrows.members(self.doc(), info["row"])}
        compat.select_ids(self.viewport, {new["id"]} & ids or ids)
        QTimer.singleShot(0, self._library_show)
        if foots:
            msg = tr("{r}: {n} footings updated — Ctrl+Z undoes it",
                     r=row["name"], n=len(ids))
        else:
            msg = tr("{r}: {n} columns updated — Ctrl+Z undoes it",
                     r=row["name"], n=len(ids))
        compat.flash(self.viewport, msg, 5000)

    def edit_floor(self, fid: str) -> None:
        """A ROOM's floor on a layered slab (floor per room, 2026-10-23):
        its window — what it is, and its material (the slab's finishes on
        the core, this room's). One Ctrl+Z."""
        from shapely.geometry import Point

        from . import materials
        from . import spaces
        from . import structure as S
        from .dialogs import FloorDialog
        doc = self.doc()
        p = S.parse_floor_id(fid)
        slab = next((e for e in doc["structure"] if p and e["id"] == p[0]),
                    None)
        if slab is None:
            return
        rid = p[1]
        room = next((r for r in spaces.of_level(doc, slab["level"])
                     if (r["rec"] or {}).get("id") == rid
                     or (isinstance(rid, tuple) and r["rec"] is None
                         and r["poly"].contains(Point(*rid)))), None)
        if room is None:
            compat.flash(self.viewport, "That room is gone — its walls "
                         "changed", 5000)
            return
        self.hub.close_sub()
        dlg = FloorDialog(room, slab, self.window)
        tab = materials.material_tab("floor", fid, doc)
        box = {"room": room, "fid": fid}

        def apply(ch) -> None:
            self._floor_apply(ch, box)
        tab.on_apply = apply
        materials.with_tab(dlg, tab)
        dlg.show_material()

        def now() -> None:
            ch = tab.change()
            if ch is not None:
                apply(ch)
            tab.start = dict(tab.now)
            tab.all.setChecked(False)
        dlg._apply_now = now
        if dlg.exec():
            ch = tab.change()
            if ch is not None:
                apply(ch)

    def _floor_apply(self, ch: dict, box: dict) -> None:
        """A room's floor's material stored and painted — a room with no
        name yet is given its label («Room 3») so its choice has a record
        to stay with."""
        from . import materials
        from . import structure as S
        doc = self._live(self.doc())
        room = box["room"]
        if room["rec"] is None:
            import uuid
            rid = uuid.uuid4().hex[:8]
            doc["rooms"] = list(doc.get("rooms") or []) + [{
                "id": rid, "level": room.get("level") or next(
                    e["level"] for e in doc["structure"]
                    if e["id"] == S.parse_floor_id(box["fid"])[0]),
                "x": round(room["at"][0], 4), "y": round(room["at"][1], 4),
                "name": room["name"]}]
            room = box["room"] = dict(room, rec=doc["rooms"][-1])
            box["fid"] = S.floor_id(S.parse_floor_id(box["fid"])[0], room)
        doc = materials.merge(doc, dict(ch, id=box["fid"]))
        self._commit_all(doc)
        compat.flash(self.viewport, tr("{n}: material applied — Ctrl+Z "
                                       "undoes it", n=f"Floor · "
                                       f"{room['name']}"), 4000)

    def apply_element(self, new: dict) -> None:
        from . import structure as S
        if new.get("type") in ("column", "footing") and new.get("row"):
            from . import colrows
            if colrows.of_column(self.doc(), new) is not None:
                self._apply_row_column(new)
                return
        new = {k: v for k, v in new.items() if k != "_row"}
        if new["type"] == "roof":            # pitched now: its rectangle
            new = dict(new, corners=S.roof_corners(new["corners"],
                                                   new["kind"]))
        why = S.why_not(new)
        if why:
            compat.flash(self.viewport, f"«{new['name']}» not changed — "
                         f"{why}", 6000)
            return
        doc = self._live(self.doc())
        # a slab's TYPE (slab layers): every slab of it changed, or these
        # layers saved as a new type — as a wall's (apply_wall)
        new = dict(new)
        every = new.pop("_type_all", False)
        named = new.pop("_new_type", None)
        host = new.pop("_host", None)
        if host and new.get("op"):           # a grid's Opening: its trim
            from . import trim as TR
            doc["openings"] = [TR.on_host(o, host) if o["id"] == new["op"]
                               else o for o in doc["openings"]]
        msg = None
        if every or named:
            doc["slab_types"] = self._typed(
                doc.get("slab_types"), new, "stype", named)
        doc["structure"] = [new if e["id"] == new["id"] else e
                            for e in doc["structure"]]
        self._commit_all(doc)
        if named:
            msg = tr("Type «{t}» saved — in the library, for the next slabs",
                     t=named["name"])
        elif every:
            msg = tr("{n} slabs of the type updated", n=sum(
                1 for e in self.doc()["structure"]
                if e.get("stype") == new.get("stype")))
        # still SELECTED, its grips on it: you see what you were changing
        # (his test, 2026-10-15: after Apply it came back unselected)
        compat.select_ids(self.viewport, {new["id"]})
        QTimer.singleShot(0, self._library_show)
        compat.flash(self.viewport, (msg + " — Ctrl+Z undoes it") if msg
                     else f"«{new['name']}» updated — Ctrl+Z undoes it", 5000)

    @staticmethod
    def _typed(types, new: dict, key: str, named) -> list:
        """YOUR types after a window's change to an element of one (``new``
        — its «type» / «stype» SET to the new type's id when ``named``):
        the new type added, or its type's layers and thickness = the
        element's (every element of it follows at the next load)."""
        types = [dict(t) for t in types or []]
        ls = [dict(la) for la in new.get("layers") or []] or [
            {"id": "core", "name": "", "t": new["t"], "role": "core"}]
        if named:
            # (its id came with it: an Apply then OK updates the same)
            types = [t for t in types if t["id"] != named["id"]]
            types.append({"id": named["id"], "name": named["name"],
                          "layers": ls, "t": new["t"],
                          "frame": new.get("frame")})   # (its joists, 4b)
            new[key] = named["id"]
        elif new.get(key):
            types = [dict(t, layers=ls, t=new["t"], frame=new.get("frame"))
                     if t["id"] == new[key] else t for t in types]
        return types

    def delete_element(self, el_id: str) -> None:
        from . import autoslabs
        doc = self._live(self.doc())
        el = next((e for e in doc["structure"] if e["id"] == el_id), None)
        if el is None:
            return
        doc["structure"] = [e for e in doc["structure"] if e["id"] != el_id]
        k = autoslabs.key_of(el)
        if k:                                # automatic: it stays away
            doc["auto_off"] = sorted(set(doc.get("auto_off") or []) | {k})
        self._commit_all(doc)
        compat.flash(self.viewport, f"«{el['name']}» deleted — Ctrl+Z "
                     "brings it back", 5000)

    # ---- Building elements: a section apart from the phases (ramps.py) -------------
    def start_element(self, key: str) -> None:
        """A «Building elements» button (the section under the methods)."""
        if key == "ramp":
            self.start_ramp()
        elif key == "stair":
            self.start_stair()
        elif key == "guard":
            self.start_guard()
        elif key == "glazing":
            self.start_glazing()
        elif key == "block":
            self.start_block()
        elif key == "surroundings":
            self.start_street()

    def start_block(self) -> None:
        """«Block» (0.15.0, B5): a slab as a block — 1 m tall to start,
        drawn as a rectangle (the slab's other ways too); its height and
        base on the library's bars."""
        if self._pro_only("slab"):
            return
        o = self.slab_opts
        o.update(block=True, ceiling=False)
        if float(o.get("t", 0.0)) < 0.30:
            o["t"] = 1.00
        if o.get("shape") in ("walls", "hole"):
            o["shape"] = "rect"
        self.hub.close_sub()
        self.start_struct_tool("slab")
        compat.flash(self.viewport, tr("Block: draw it — its height and base "
                                       "on the library's bars"), 5000)

    # ---- Surroundings: streets (streets.py — Pro) -----------------------------------
    @_project_first
    def start_street(self) -> None:
        """«Surroundings» ▸ Street: on the GROUND level — «Along the plot»
        (one click on a side of the plot; the next side clicked joins it
        round the corner) or «By axis» (point by point, as walls). The
        library on the right: its profile. The tool stays out for the
        next one (Esc = done)."""
        if self._pro_only("street"):
            return
        from . import streets as SR
        self.hub.close_sub()
        self._sel_at_phase = set(self._lib_picked()[1])   # the tool wins
        doc = self.doc()
        gi = self._ground_index(doc)
        if self.floor != gi:                 # streets: on the ground level
            self.set_floor(doc["levels"][gi]["id"], quiet=True)
        _i, lv, z0 = self._work_level()
        lid = lv["id"]
        o = self.street_opts
        plot = doc.get("plot")
        z = z0
        g = SR.ground_at(doc)
        if g is not None:
            cs = plot["corners"]
            z = sum(g(c[0], c[1]) for c in cs) / len(cs)
        walls = self._reader(lambda d: [w for w in d["walls"]
                                        if w["level"] == lid])
        if o.get("how", "plot") == "plot" and plot:
            tool = SR.PlotSideTool(lambda *_a: None, self._wall_cancelled,
                                   z, lambda: o, walls)
            tool.targets = SR.side_targets(doc, dict(o))
            tool.on_pick = self._street_side
            say = ("click a side of the plot — the street runs along it, "
                   "outside (the next side clicked turns the corner)")
        else:
            if o.get("how", "plot") == "plot":
                # no plot: by its axis — said so in the library too, its
                # «Line drawn» shown (his test, 2026-10-28: it showed only
                # once one was drawn)
                o["how"] = "axis"
                QTimer.singleShot(0, self._library_show)
                compat.flash(self.viewport, "No plot yet — draw the street "
                             "by its axis (or the plot first)", 5000)
            tool = SR.StreetTool(self._street_drawn, self._wall_cancelled,
                                 z, lambda: o, walls)
            say = ("click its axis point after point (Enter ends it, C "
                   "closes it)")
        tool.level_id = lid
        self._activate(tool)
        compat.flash(self.viewport, f"Street — its profile on the right; "
                     f"{say}", 6000)

    def _street_rec(self) -> dict:
        from . import streets as SR
        return {k: v for k, v in self.street_opts.items()
                if k not in SR.TOOL_KEYS}

    def _street_side(self, k: int) -> None:
        """A side of the plot clicked: a street along it — or the street
        along the side before / after it takes it (round the corner)."""
        from . import streets as SR
        _i, lv, z0 = self._work_level()
        doc = self._live(self.doc())
        st, sid, how = SR.add_side(doc, lv["id"], k, self._street_rec())
        if how == "already":
            compat.flash(self.viewport, "That side has its street already",
                         4000)
            return
        if how == "joined":
            doc["structure"] = st
            self._commit_all(doc)
            compat.select_ids(self.viewport, {sid})
            compat.flash(self.viewport, "The street turns the corner — "
                         "Ctrl+Z undoes it", 5000)
        else:
            rec = dict(self._street_rec(), type="street", edges=[k],
                       ext=[SR.EXT, SR.EXT], level=lv["id"])
            rec["base"] = SR.base_for(doc, rec, z0)
            if self._struct_done([rec]):
                compat.select_ids(self.viewport, set(self._last_made))
        self._refresh_street_targets()

    def _refresh_street_targets(self) -> None:
        tool = getattr(self.viewport, "active_tool", None)
        if type(tool).__name__ == "PlotSideTool" and self.doc().get("plot"):
            from . import streets as SR
            tool.targets = SR.side_targets(self.doc(), dict(self.street_opts))

    def _street_drawn(self, pts, closed) -> None:
        from . import streets as SR
        _i, lv, z0 = self._work_level()
        rec = dict(self._street_rec(), type="street", pts=pts,
                   closed=bool(closed), level=lv["id"])
        rec["base"] = SR.base_for(self.doc(), rec, z0)
        if self._struct_done([rec]):
            compat.select_ids(self.viewport, set(self._last_made))

    def edit_street(self, el: dict) -> None:
        """A street's own window (streets.py)."""
        from . import streets as SR
        doc = self.doc()
        lv = next((r for r in doc["levels"] if r["id"] == el["level"]), None)
        if lv is None:
            return
        dlg = SR.StreetDialog(el, lv, doc.get("plot"), self.window)
        self._mat_tab(dlg, "street", el["id"])
        self._in_place(dlg, self.apply_element)
        if not dlg.exec():
            return
        action, new = dlg.result_data()
        self._mat_take(dlg, action)
        if action == "delete":
            self.delete_element(el["id"])
            return
        if action == "hide":
            self.hide_element(el["id"], el["name"])
            return
        self.apply_element(new)
        self._again(dlg, lambda: self.edit_element(el["id"]))

    # ---- Tools ▸ Along a path: profiles (along.py — Pro) ------------------------------
    def start_profile(self) -> None:
        """«Profile along»: the library on the right says which profile,
        where it sits and HOW — «By room» (a click inside a room: round its
        walls, stopping at the doors) or «Point by point» (along a line
        drawn on a wall's face). The tool stays out (Esc = done)."""
        if self._pro_only("profile"):
            return
        from . import along as AL
        from . import structure as S
        self.hub.close_sub()
        self._sel_at_phase = set(self._lib_picked()[1])   # the tool wins
        _i, lv, z0 = self._work_level()
        lid = lv["id"]
        o = self.profile_opts
        self.element = "along"
        self.method = "Profile along"
        self._profile_types()                # YOUR profiles known
        if not PF.known(o.get("profile")):   # (one deleted since: the plain)
            o.update(profile="base_flat", anchor="floor", pw=None, ph=None)
        if o.get("how") == "line":
            tool = AL.LinePickTool(self._profile_line, self._wall_cancelled,
                                   lambda: o)
            say = ("click a line — the profile runs along it (Alt + click: "
                   "only that stretch, Tab: the other side)")
        elif o.get("how") == "face":
            tool = self._face_tool(AL.FacePickTool, self._profile_face, lid,
                                   z0)
            say = "click a wall's face (Shift + click: the next one joins)"
        elif o.get("how") in ("circle", "rect"):
            tool = AL.ShapePathTool(self._profile_shape, self._wall_cancelled,
                                    z0, lambda: o, o["how"])
            say = ("click the centre on a face, then the radius"
                   if o["how"] == "circle" else
                   "click two opposite corners on a face")
        elif o.get("how") == "element":
            tool = self._face_tool(AL.ElementPickTool, self._profile_element,
                                   lid, z0)
            tool.lines_of = self._element_lines
            say = "click a column or a beam (Shift + click: the next one " \
                  "joins)"
        elif o.get("how", "room") == "room":
            doc = self._live(self.doc())
            under = S.levels_info(doc, model.elevations)[lid]["under"]
            tool = AL.RoomPickTool(lambda *_a: None, self._wall_cancelled, z0,
                                   lambda: {"t": 0.05, "align": "centre"},
                                   self._reader(lambda d: [
                                       w for w in d["walls"]
                                       if w["level"] == lid]))
            tool.targets = AL.room_targets(doc, lid, self._profile_rec(), z0,
                                           under)
            tool.on_pick = self._profile_room
            say = "click inside a room — round its walls"
            if not tool.targets:
                compat.flash(self.viewport, f"No rooms on «{lv['name']}» yet "
                             "— walls round a room first, or draw it point "
                             "by point", 6000)
        else:
            tool = AL.PathTool(self._profile_path, self._wall_cancelled, z0,
                               lambda: o)
            say = ("click point after point, at any height (Enter ends it, "
                   "C closes it, Tab: the other side)")
        tool.level_id = lid
        self._activate(tool)
        self.strip.fill(self.element, self.method)
        compat.flash(self.viewport, f"Profile on «{lv['name']}» — pick it on "
                     f"the right, then {say}", 6000)
        # (his screen, 29/10: the view scrambled until a click — the host's
        # kept frame given back: the next one drawn in full)
        QTimer.singleShot(0, lambda: compat.fresh_frame(self.viewport))

    def _profile_rec(self) -> dict:
        return {k: v for k, v in self.profile_opts.items()
                if k not in PF.TOOL_KEYS}

    def _profile_new_path(self, how: str, path, closed, frame) -> None:
        """A profile of its own path — heights kept over the level, so it
        moves with it."""
        _i, _lv, z0 = self._work_level()
        rec = dict(self._profile_rec(), type="profile", how=how,
                   path=[[round(p[0], 4), round(p[1], 4), round(p[2] - z0, 4)]
                         for p in path],
                   closed=bool(closed),
                   frame=[[round(c, 6) for c in a] for a in frame])
        if self._struct_done([rec]):
            self._line_last = next(iter(self._last_made or ()), None)
            compat.select_ids(self.viewport, set(self._last_made))

    def _profile_path(self, path, closed, frame) -> None:
        self._profile_new_path("points", path, closed, frame)

    def _profile_shape(self, path, closed, frame) -> None:
        """A circle / a rectangle: a closed path like any other — not selected,
        so the library stays on this tool for the next one."""
        self._profile_new_path("points", path, closed, frame)
        compat.select_ids(self.viewport, set())

    def _profile_line(self, path, closed, frame, add: bool = False) -> None:
        """A line clicked: the profile along it; Shift: it joins the one made
        last, where their ends meet."""
        from . import along as AL
        _i, _lv, z0 = self._work_level()
        doc = self._live(self.doc())
        last = next((x for x in doc["structure"]
                     if x["id"] == getattr(self, "_line_last", None)), None)
        if add and last is not None and last.get("path") \
                and not last.get("closed"):
            got = AL.joined(AL.path_of(last, z0), path, closed)
            if got is None:
                compat.flash(self.viewport, "That line does not meet the last "
                             "one — it starts a new profile", 4000)
            else:
                # back where it started: a closed ring
                ring = len(got) > 3 and AL.math.dist(got[0], got[-1]) <= 1e-3
                self.apply_element(dict(last, closed=ring, path=[
                    [round(p[0], 4), round(p[1], 4), round(p[2] - z0, 4)]
                    for p in (got[:-1] if ring else got)]))
                compat.select_ids(self.viewport, {last["id"]})
                return
        self._profile_new_path("line", path, closed, frame)

    def _profile_room(self, k: int) -> None:
        """A room clicked: the profile round its walls — its seed the room's
        label point, its path kept too (shown if the room is ever gone)."""
        from . import along as AL
        tool = getattr(self.viewport, "active_tool", None)
        targets = getattr(tool, "targets", None) or []
        if not 0 <= k < len(targets):
            return
        _shape, _lines, room = targets[k]
        rec = dict(self._profile_rec(), type="profile", how="room",
                   seed=[round(room["at"][0], 4), round(room["at"][1], 4)],
                   rings=[[[round(x, 4), round(y, 4)] for x, y in r]
                          for r in AL.rings_of(room["poly"])])
        if self._struct_done([rec]):
            compat.select_ids(self.viewport, set(self._last_made))
            compat.flash(self.viewport, f"«{room['name']}»: profile round its "
                         "walls — it follows them when they move · Ctrl+Z "
                         "undoes it", 5000)
        self._refresh_profile_targets()

    # ---- «By wall face» (part 5, P5a): a profile / copies along walls' faces ----------------
    def _face_tool(self, cls, on_pick, lid: str, z0: float):
        from . import structure as S
        doc = self._live(self.doc())
        tool = cls(lambda *_a: None, self._wall_cancelled, z0,
                   lambda: {"t": 0.05, "align": "centre"},
                   self._reader(lambda d: [w for w in d["walls"]
                                           if w["level"] == lid]))
        tool.under = S.levels_info(doc, model.elevations)[lid]["under"]
        tool.targets = []
        tool.on_pick = on_pick
        self._face_last = None               # Shift + click joins this one
        return tool

    def _face_made(self, kind: str, rec: dict, face, add: bool) -> None:
        """A face clicked: a new profile / copies along it — Shift: the face
        joins the one made last with this tool (one Ctrl+Z each)."""
        from . import along as AL
        from . import structure as S
        doc = self._live(self.doc())
        _i, lv, z0 = self._work_level()
        info = S.levels_info(doc, model.elevations)[lv["id"]]
        walls = [w for w in doc["walls"] if w["level"] == lv["id"]]
        last = next((e for e in doc["structure"]
                     if e["id"] == getattr(self, "_face_last", None)), None)
        if add and last is not None:
            faces = [list(f) for f in last.get("faces") or []]
            if list(face) in faces:
                compat.flash(self.viewport, "That face is in it already",
                             3000)
                return
            new = dict(last, faces=faces + [list(face)])
        else:
            new = dict(rec, type=kind, how="face", faces=[list(face)])
        found = AL.face_paths(new["faces"], walls)
        new["last"] = [[[[round(x, 4), round(y, 4)] for x, y in p], c, s]
                       for p, c, s in found]
        if not found:
            compat.flash(self.viewport, "Nothing free along that face — "
                         "another wall stands there", 4000)
            return
        if kind == "copy" and not self._copy_check(new):
            return
        if kind == "copy" and (new.get("src") or {}).get("els") \
                and new.get("obj") == PF.COPY_MINE:
            self._copy_finish(new)
            return
        if add and last is not None:
            self.apply_element(new)
            compat.select_ids(self.viewport, {last["id"]})
            return
        if self._struct_done([new]):
            self._face_last = next(iter(self._last_made or ()), None)
            compat.select_ids(self.viewport, set(self._last_made))
            if info:
                compat.flash(self.viewport, "Along the face — it follows the "
                             "wall when it moves · Shift + click: the next "
                             "face joins it", 5000)

    def _element_lines(self, eid: str) -> list:
        """«By element»: what a click on ``eid`` makes (the preview)."""
        from . import along as AL
        from . import structure as S
        doc = self._live(self.doc())
        _i, lv, z0 = self._work_level()
        under = S.levels_info(doc, model.elevations)[lv["id"]]["under"]
        e = dict(self._profile_rec(), how="element", level=lv["id"],
                 els=[eid])
        return [(p, c) for p, c, _s in AL.paths(e, doc, z0, under)]

    def _profile_element(self, eid: str, add: bool = False) -> None:
        """A column / beam clicked: a profile round it — Shift: it joins the
        profile made last with this tool."""
        doc = self._live(self.doc())
        el = next((x for x in doc["structure"] if x["id"] == eid), None)
        if el is None:
            return
        last = next((x for x in doc["structure"]
                     if x["id"] == getattr(self, "_face_last", None)), None)
        if add and last is not None and last.get("how") == "element":
            if eid in (last.get("els") or []):
                compat.flash(self.viewport, "That one has it already", 3000)
                return
            self.apply_element(dict(last, els=list(last["els"]) + [eid]))
            compat.select_ids(self.viewport, {last["id"]})
            return
        if not self._element_lines(eid):
            compat.flash(self.viewport, "Nothing free round it — walls "
                         "stand all round", 4000)
            return
        rec = dict(self._profile_rec(), type="profile", how="element",
                   els=[eid])
        if self._struct_done([rec]):
            self._face_last = next(iter(self._last_made or ()), None)
            compat.select_ids(self.viewport, set(self._last_made))
            compat.flash(self.viewport, f"Round «{el.get('name', '')}» — it "
                         "follows it when it changes · Shift + click: the "
                         "next one joins", 5000)

    def _profile_face(self, face, add: bool = False) -> None:
        self._face_made("profile", self._profile_rec(), face, add)

    def _copy_face(self, face, add: bool = False) -> None:
        self._face_made("copy", self._copy_rec(), face, add)

    def _refresh_profile_targets(self) -> None:
        tool = getattr(self.viewport, "active_tool", None)
        name = type(tool).__name__
        if name not in ("RoomPickTool", "CopyRoomTool"):
            return
        from . import along as AL
        from . import structure as S
        _i, lv, z0 = self._work_level()
        doc = self._live(self.doc())
        under = S.levels_info(doc, model.elevations)[lv["id"]]["under"]
        rec = self._copy_room_rec() if name == "CopyRoomTool" \
            else self._profile_rec()
        tool.targets = AL.room_targets(doc, lv["id"], rec, z0, under)

    def edit_profile(self, el: dict) -> None:
        """A profile's own window (along.py)."""
        from . import along as AL
        from . import structure as S
        doc = self.doc()
        lv = next((r for r in doc["levels"] if r["id"] == el["level"]), None)
        if lv is None:
            return
        info = S.levels_info(doc, model.elevations).get(el["level"])
        try:
            long_ = AL.length(el, doc, info["z0"], info["under"]) if info \
                else 0.0
        except Exception:  # noqa: BLE001 — its length is only shown
            long_ = 0.0
        dlg = AL.ProfileDialog(el, lv, long_, self.window,
                               types=doc.get("profile_types") or [])
        self._mat_tab(dlg, "profile", el["id"])
        self._in_place(dlg, self.apply_element)
        self._live_window(dlg, "profile")      # it, live (livewin.py)
        if not dlg.exec():
            return
        action, new = dlg.result_data()
        self._mat_take(dlg, action)
        if action == "delete":
            self.delete_element(el["id"])
            return
        if action == "hide":
            self.hide_element(el["id"], el["name"])
            return
        self.apply_element(new)
        self._again(dlg, lambda: self.edit_element(el["id"]))

    # ---- Tools ▸ Along a path: copies (copies.py — Pro) --------------------------------------
    def start_copy(self) -> None:
        """«Copy along»: the library says WHAT (a bollard, a tree… or the
        object selected in the model) and how they spread — «By room»
        (round its walls) or «Point by point» (along a line drawn). The
        tool stays out (Esc = done)."""
        if self._pro_only("copy"):
            return
        from . import along as AL
        from . import structure as S
        self.hub.close_sub()
        self._sel_at_phase = set(self._lib_picked()[1])   # the tool wins
        _i, lv, z0 = self._work_level()
        lid = lv["id"]
        o = self.copy_opts
        self.element = "along"
        self.method = "Copy along"
        if o.get("obj") == PF.COPY_MINE and not o.get("src"):
            o["obj"] = "bollard"                 # (none taken yet)
        walls = self._reader(lambda d: [w for w in d["walls"]
                                        if w["level"] == lid])
        if o.get("how") == "face":
            tool = self._face_tool(AL.CopyFaceTool, self._copy_face, lid, z0)
            say = "click a wall's face (Shift + click: the next one joins)"
        elif o.get("how", "points") == "room":
            doc = self._live(self.doc())
            under = S.levels_info(doc, model.elevations)[lid]["under"]
            tool = AL.CopyRoomTool(lambda *_a: None, self._wall_cancelled, z0,
                                   lambda: {"t": 0.05, "align": "centre"},
                                   walls)
            tool.targets = AL.room_targets(doc, lid, self._copy_room_rec(),
                                           z0, under)
            tool.on_pick = self._copy_room
            say = "click inside a room — round its walls"
            if not tool.targets:
                compat.flash(self.viewport, f"No rooms on «{lv['name']}» yet "
                             "— walls round a room first, or draw it point "
                             "by point", 6000)
        elif o.get("how") == "line":
            tool = AL.CopyLineTool(self._copy_line, self._wall_cancelled,
                                   lambda: o)
            say = ("click a line — they stand along it (Alt + click: only "
                   "that stretch, Tab: the other side)")
        else:
            tool = AL.CopyPathTool(self._copy_drawn, self._wall_cancelled, z0,
                                   lambda: o)
            say = ("click the path point after point, at any height (Enter "
                   "ends it, C closes it, Tab: the other side)")
        tool.level_id = lid
        self._activate(tool)
        self.strip.fill(self.element, self.method)
        compat.flash(self.viewport, f"Copies on «{lv['name']}» — pick what "
                     f"on the right, then {say}", 6000)
        QTimer.singleShot(0, lambda: compat.fresh_frame(self.viewport))

    def _copy_rec(self) -> dict:
        return {k: v for k, v in self.copy_opts.items()
                if k not in PF.COPY_TOOL_KEYS}

    def _copy_room_rec(self) -> dict:
        """What the room's outline is read with (copies.runs_of's)."""
        return dict(self._copy_rec(), profile="base_flat", anchor="floor",
                    off=0.0)

    def _copy_check(self, rec: dict) -> bool:
        """Too many copies: said, nothing made."""
        from . import copies as CP
        from . import structure as S
        doc = self._live(self.doc())
        _i, lv, z0 = self._work_level()
        under = S.levels_info(doc, model.elevations)[lv["id"]]["under"]
        try:
            n = CP.count(dict(rec, level=lv["id"]), doc, z0, under)
        except Exception:  # noqa: BLE001 — the build says what is wrong
            return True
        if n > CP.MAX_COPIES:
            compat.flash(self.viewport, f"{n} copies — at most "
                         f"{CP.MAX_COPIES}: a longer spacing", 6000)
            return False
        return True

    def _copy_finish(self, rec: dict) -> None:
        """Copies made: one group of faces — or, of columns and footings from
        the model, real ones. One Ctrl+Z either way."""
        if not self._copy_check(rec):
            return
        if (rec.get("src") or {}).get("els") \
                and rec.get("obj") == PF.COPY_MINE:
            self._copy_real(rec)
        elif self._struct_done([rec]):
            compat.select_ids(self.viewport, set(self._last_made))

    def _copy_real(self, rec: dict) -> None:
        """Real elements (copies.real_records): as they are — what the column
        tool's options say (``_struct_done``) does not reach them."""
        from . import copies as CP
        from . import structure as S
        doc = self._live(self.doc())
        _i, lv, z0 = self._work_level()
        info = S.levels_info(doc, model.elevations)[lv["id"]]
        mine = self._level_struct(doc, lv["id"])
        out, dup = [], 0
        for r in CP.real_records(dict(rec, level=lv["id"]), doc, z0,
                                 info["under"]):
            r = dict(r, level=lv["id"])
            if S.why_not(r):
                continue
            if any(self._same(r, e) for e in mine + out):
                dup += 1
                continue
            out.append(r)
        if not out:
            compat.flash(self.viewport, "Nothing new to build"
                         + (" — already there" if dup else ""), 4000)
            return
        made = model.new_elements(doc["structure"], out)
        doc["structure"] = doc["structure"] + made
        self._commit_all(doc)
        self._last_made = {m["id"] for m in made}
        # (not selected: the library stays on the copies, for the next path)
        compat.flash(self.viewport, f"{len(made)} new on «{lv['name']}», each "
                     "its own — Ctrl+Z undoes them"
                     + (f" ({dup} already there, left out)" if dup else ""),
                     5000)

    def _copy_drawn(self, pts, closed, side) -> None:
        self._copy_path("points", pts, closed, side)

    def _copy_line(self, path, closed, side, _add: bool = False) -> None:
        self._copy_path("line", path, closed, side)

    def _copy_path(self, how: str, path, closed, side) -> None:
        """Copies along a path of their own — heights kept over the level."""
        _i, _lv, z0 = self._work_level()
        self._copy_finish(dict(
            self._copy_rec(), type="copy", how=how,
            path=[[round(p[0], 4), round(p[1], 4), round(p[2] - z0, 4)]
                  for p in path],
            closed=bool(closed), side=side))

    def _copy_pick(self) -> None:
        """«From the model», nothing selected: the next click takes it."""
        from . import along as AL
        tool = AL.CopyPickTool(self._copy_picked, self._wall_cancelled)
        tool.level_id = self._work_level()[1]["id"]
        self._activate(tool)
        self.strip.fill(self.element, self.method)
        compat.flash(self.viewport, "Click the object to copy — a column, a "
                     "footing, any group", 6000)

    def _copy_picked(self, g) -> None:
        if not self._copy_take_selection([g]):
            return
        self.copy_opts["obj"] = PF.COPY_MINE
        self.start_copy()
        QTimer.singleShot(0, self._library_show)

    def _copy_room(self, k: int) -> None:
        from . import along as AL
        tool = getattr(self.viewport, "active_tool", None)
        targets = getattr(tool, "targets", None) or []
        if not 0 <= k < len(targets):
            return
        _shape, _lines, room = targets[k]
        rec = dict(self._copy_rec(), type="copy", how="room",
                   seed=[round(room["at"][0], 4), round(room["at"][1], 4)],
                   rings=[[[round(x, 4), round(y, 4)] for x, y in r]
                          for r in AL.rings_of(room["poly"])])
        if (rec.get("src") or {}).get("els") \
                and rec.get("obj") == PF.COPY_MINE:
            self._copy_finish(rec)
        elif self._copy_check(rec) and self._struct_done([rec]):
            compat.select_ids(self.viewport, set(self._last_made))
            compat.flash(self.viewport, f"«{room['name']}»: copies round its "
                         "walls — they follow them when they move · Ctrl+Z "
                         "undoes it", 5000)
        self._refresh_profile_targets()

    def _copy_take_selection(self, gs=None) -> bool:
        """«From the model»: the faces of the groups selected (or ``gs``, the
        one clicked) kept as the object copied. Columns and pad footings also
        keep their records: their copies are real ones. False: none here."""
        from . import copies as CP
        from . import structure as S
        if gs is None:
            sel = list(getattr(self.viewport.scene, "selection", ()) or ())
            gs = [g for g in sel if type(g).__name__ == "Group"
                  and compat.kind_of(g) != "copy"]
        if not gs:
            return False
        loops = []
        for g in gs:
            xf = getattr(g, "xform", None)   # a component's instance
            mat = getattr(g, "material", None)
            base = tuple((mat or {}).get("color") or CP.CONCRETE) \
                if isinstance(mat, dict) else CP.CONCRETE

            def pt(v, xf=xf):
                v = xf.map(v) if xf is not None else v
                return (v.x(), v.y(), v.z())
            for f in g.mesh.faces:
                outer = [pt(v) for v in f.vertices]
                if len(outer) < 3:
                    continue
                holes = [[pt(v) for v in h] for h in (f.holes or ())]
                col = (getattr(f, "attrs", None) or {}).get("color") or base
                col = tuple(col)[:4]
                loops.append((outer, holes, col + (1.0,) * (4 - len(col))))
        name = str(gs[0].name or "Object")[:40]
        src = CP.from_group(loops)
        if not src:
            compat.flash(self.viewport, f"«{name}»: nothing to copy (too big "
                         f"— at most {CP.MAX_SRC_FACES} faces)", 6000)
            # (said: not asked to click another as if nothing were selected)
            return True
        src["name"] = name
        # all of them columns / pad footings: as themselves
        doc = self.doc()
        recs = [next((e for e in doc["structure"]
                      if e["id"] == compat._rec(g).get("id")), None)
                for g in gs]
        if all(r is not None and CP.is_real(r) for r in recs):
            cx, cy = src["at"][:2]
            els = []
            for r in recs:
                x, y = S.column_centre(r) if r["type"] == "column" \
                    else (r["x"], r["y"])
                at = (0.0, 0.0) if len(recs) == 1 \
                    else (round(x - cx, 4), round(y - cy, 4))
                els.append(dict(r, _at=at))
            src["els"] = els
        self.copy_opts["src"] = src
        self.copy_opts["obj"] = PF.COPY_MINE
        compat.flash(self.viewport, f"«{name}» taken — now its path (the "
                     "original stays where it is)", 5000)
        QTimer.singleShot(0, self._refresh_profile_targets)
        return True

    def edit_copy(self, el: dict) -> None:
        """Copies' own window (along.py)."""
        from . import along as AL
        from . import copies as CP
        from . import structure as S
        doc = self.doc()
        lv = next((r for r in doc["levels"] if r["id"] == el["level"]), None)
        if lv is None:
            return
        info = S.levels_info(doc, model.elevations).get(el["level"])
        try:
            n = CP.count(el, doc, info["z0"], info["under"]) if info else 0
        except Exception:  # noqa: BLE001 — the count is only shown
            n = 0
        dlg = AL.CopyDialog(el, lv, n, self.window)
        self._mat_tab(dlg, "copy", el["id"])
        self._in_place(dlg, self.apply_element)
        if not dlg.exec():
            return
        action, new = dlg.result_data()
        self._mat_take(dlg, action)
        if action == "delete":
            self.delete_element(el["id"])
            return
        if action == "hide":
            self.hide_element(el["id"], el["name"])
            return
        self.apply_element(new)
        self._again(dlg, lambda: self.edit_element(el["id"]))

    # ---- YOUR profiles (D6): made from a face, kept in his library -------------------------
    def _profile_types(self) -> list:
        """YOUR profiles: the library's (every project) and this project's
        copies of others (a file from another computer) — each once."""
        lib = PF.lib_load()
        ids = {t["id"] for t in lib}
        out = lib + [t for t in self.doc().get("profile_types") or []
                     if t["id"] not in ids]
        PF.add(out)
        return out

    def _with_profiles(self, doc: dict) -> dict:
        """The project keeps a copy of every profile of YOURS placed in it
        (the file opens with them on another computer)."""
        used = {e.get("profile") for e in doc.get("structure") or []
                if e.get("type") == "profile" and PF.is_user(e.get("profile"))}
        have = {t["id"] for t in doc.get("profile_types") or []}
        new = [dict(PF.USER[k]) for k in sorted(used - have) if k in PF.USER]
        if new:
            doc = dict(doc, profile_types=list(doc.get("profile_types")
                                               or []) + new)
        return doc

    def _selected_face(self):
        """(the one flat face selected, why not) — a loose face, or a group
        made of one face. (None, None): no face selected."""
        sel = list(getattr(self.viewport.scene, "selection", ()) or ())
        faces = [e for e in sel if type(e).__name__ == "Face"]
        for g in sel:
            if type(g).__name__ == "Group" and len(g.mesh.faces) == 1:
                faces.append(next(iter(g.mesh.faces)))
        if not faces:
            return None, None
        if len(faces) > 1:
            return None, tr("Select one face only ({n} selected)",
                            n=len(faces))
        return faces[0], None

    def _profile_from_face(self, f) -> None:
        """The face → its window → your library."""
        import uuid
        from . import along as AL
        o = self.profile_opts
        pts = PF.from_face([v.toTuple() for v in f.vertices],
                           f.normal().toTuple())
        why = PF.check(pts)
        if why:
            compat.flash(self.viewport, tr(why), 7000)
            return
        dlg = AL.ProfileTypeDialog(
            pts, note=tr("Its holes are left out") if f.holes else "",
            parent=self.window)
        if not dlg.exec():
            return
        t = dict(dlg.result_data(), id="u_" + uuid.uuid4().hex[:8])
        got = PF.clean_user([t])
        if not got:
            compat.flash(self.viewport, tr("Not a profile — its outline "
                                           "crosses itself"), 6000)
            return
        t = got[0]
        PF.lib_save(PF.lib_load() + [t])
        PF.add([t])
        a, z = PF.anchor_of(t["id"])
        o.update(profile=t["id"], anchor=a, pw=None, ph=None,
                 **({"z": z} if a == "height" else {}))
        self._refresh_profile_targets()
        compat.flash(self.viewport, tr("Profile «{t}» made — the next "
                                       "ones are of it; kept in your "
                                       "library", t=t["name"]), 6000)

    def _pick_profile_face(self) -> None:
        """«+ New from a face» with no face selected: the next click takes
        one, so the link works before the face as well as after it (his
        test, 06/11: the click drew the marked profile instead). The drawing
        tool comes back after it, or on Esc."""
        from . import along as AL

        def back() -> None:
            QTimer.singleShot(0, self.start_profile)

        def picked(f) -> None:
            def go() -> None:
                self._profile_from_face(f)
                self.start_profile()
            QTimer.singleShot(0, go)
        self._activate(AL.ProfileFacePickTool(picked, back))

    def _profile_type_act(self, act: str, tid: str | None = None) -> None:
        """«+ New from a face» (the face selected, or the next one clicked),
        «Edit…» (its name, category, side) and the card's trash."""
        from PySide6.QtWidgets import QMessageBox
        if self._pro_only("profile"):
            return
        from . import along as AL
        o = self.profile_opts
        if act == "new":
            f, why = self._selected_face()
            if why:
                compat.flash(self.viewport, why, 7000)
            elif f is None:
                self._pick_profile_face()
            else:
                self._profile_from_face(f)
            return
        tid = tid or o.get("profile")
        t = next((t for t in self._profile_types() if t["id"] == tid), None)
        if t is None:
            return
        lib = PF.lib_load()
        doc = self._live(self.doc())
        n_used = sum(1 for e in doc["structure"]
                     if e["type"] == "profile" and e.get("profile") == tid)
        if act == "edit":
            dlg = AL.ProfileTypeDialog(t["pts"], t["name"], t["cat"], "left",
                                       parent=self.window)
            if not dlg.exec():
                return
            t = dict(t, **dlg.result_data())
            PF.lib_save([t if x["id"] == tid else x for x in lib]
                        if any(x["id"] == tid for x in lib) else lib + [t])
            PF.add([t])
            if any(x["id"] == tid for x in doc.get("profile_types") or []):
                doc["profile_types"] = [t if x["id"] == tid else x
                                        for x in doc["profile_types"]]
                self._commit_all(doc)        # the ones placed: drawn again
            return
        if act == "delete":
            if QMessageBox.question(
                    self.window, tr("Delete?"),
                    tr("Delete the profile «{t}» from your library?", t=t["name"])
                    + ("\n" + tr("This project keeps its copy: {n} placed "
                                 "with it stay.", n=n_used) if n_used else "")
                    ) != QMessageBox.Yes:
                return
            PF.lib_save([x for x in lib if x["id"] != tid])
            if not n_used and any(x["id"] == tid for x in
                                  doc.get("profile_types") or []):
                doc["profile_types"] = [x for x in doc["profile_types"]
                                        if x["id"] != tid]
                self._commit_all(doc)
            if o.get("profile") == tid:
                o.update(profile="base_flat", anchor="floor")

    # ---- Glass grids (glazing.py — Pro) -----------------------------------------------
    @_project_first
    def start_glazing(self) -> None:
        """«Glass grid»: the library says which (industrial, aluminium, a
        partition), how the panes go and WHERE: in an Opening (click a
        wall's void — it fills it) or free (two points). The tool stays
        out for the next one (Esc = done)."""
        if self._pro_only("glazing"):
            return
        from . import glazing as GZ
        self._glazing_moving = None          # (a plain tool: places new ones)
        self.hub.close_sub()
        self._sel_at_phase = set(self._lib_picked()[1])   # the tool wins
        _i, lv, z0 = self._work_level()
        lid = lv["id"]
        o = self.glazing_opts
        walls = self._reader(lambda d: [w for w in d["walls"]
                                        if w["level"] == lid])
        if o.get("kind") == "bars":
            # security bars (D7, 2026-10-27): on a WINDOW, outside
            tool = GZ.VoidPickTool(self._glazing_window, self._wall_cancelled,
                                   z0, lambda: {"t": 0.05, "align": "centre"},
                                   walls)

            def wins():
                d = self._live(self.doc())
                ws = {w["id"]: w for w in d["walls"] if w["level"] == lid
                      and w.get("kind", "line") == "line"}
                return [(op, ws[op["wall"]]) for op in d["openings"]
                        if op["kind"] == "window" and op["wall"] in ws]
            tool.voids = wins
            tool.on_window = True
            say = "click a window"
        elif o.get("place", "void") != "free":
            tool = GZ.VoidPickTool(self._glazing_void, self._wall_cancelled,
                                   z0, lambda: {"t": 0.05, "align": "centre"},
                                   walls)

            def voids():
                d = self._live(self.doc())
                ws = {w["id"]: w for w in d["walls"] if w["level"] == lid}
                return [(op, ws[op["wall"]]) for op in d["openings"]
                        if op["kind"] == "void" and op["wall"] in ws]
            tool.voids = voids
            tool.on_span = self._glazing_span
            say = ("click an Opening (a void) — or twice along a wall: the "
                   "Opening is made there")
        else:
            tool = GZ.GlazingTool(self._glazing_free, self._wall_cancelled,
                                  z0 + float(o.get("base", 0.0)), lambda: o,
                                  walls)
            say = "click where it starts and where it ends"
        tool.level_id = lid
        if isinstance(tool, GZ.VoidPickTool):     # in 3D: the ray's wall
            every = self._walls_3d_reader()
            tool.walls_3d = lambda: every()[0]
        self._activate(tool)
        compat.flash(self.viewport, f"Grid on «{lv['name']}» — pick its "
                     f"type on the right, then {say}", 6000)

    def _glazing_replace(self, ids, place: str) -> None:
        """Selected glass grids → ``place``. «free»: each one out of its
        Opening, standing free where it was (its width, sill, height).
        «void»: the Opening tool comes out — the one clicked takes the
        (first) selected grid, its settings kept."""
        from . import glazing as GZ
        from . import structure as S
        doc = self._live(self.doc())
        info = S.levels_info(doc, model.elevations)

        def zf(l_):
            return info[l_]["z0"] if l_ in info else 0.0
        grids = [e for e in doc["structure"] if e["id"] in ids
                 and e.get("type") == "glazing"]
        if place == "free":
            new, n = [], 0
            for e in doc["structure"]:
                if e in grids and e.get("place") != "free":
                    fr = GZ.frame_of(e, doc, zf)
                    if fr is not None:
                        p0, u, _n, _o, Wd, zb, H = fr
                        e = {k: v for k, v in e.items() if k != "op"}
                        e.update(place="free", a=[round(p0[0], 4),
                                                  round(p0[1], 4)],
                                 b=[round(p0[0] + u[0] * Wd, 4),
                                    round(p0[1] + u[1] * Wd, 4)],
                                 base=round(zb - zf(e["level"]), 4),
                                 h=round(H, 4))
                        n += 1
                new.append(e)
            if not n:
                compat.flash(self.viewport, "Already free", 3000)
                return
            doc["structure"] = new
            self._commit_all(doc)
            compat.select_ids(self.viewport, set(ids))
            compat.flash(self.viewport, f"{n} grid(s) free, where they "
                         "were — Ctrl+Z undoes it", 5000)
            QTimer.singleShot(0, self._library_show)
            return
        moving = next((e for e in grids if e.get("place") == "free"), None)
        if moving is None:
            compat.flash(self.viewport, "Already in an Opening", 3000)
            return
        self.start_glazing()                 # the Opening tool (place void)
        self._glazing_moving = moving["id"]  # (after: start_glazing clears)
        compat.flash(self.viewport, f"Click the Opening (a void) «"
                     f"{moving['name']}» goes into — Esc: it stays free", 6000)

    def _glazing_rec(self) -> dict:
        from . import trim as TR             # (its Opening's, not its own)
        return {k: v for k, v in self.glazing_opts.items()
                if k not in TR.HOST}

    def _glazing_span(self, wall_id: str, pos: float, width: float) -> None:
        """Two clicks along a wall, «In an Opening»: the Opening is made
        there (the grid's sill and height — the moving one's own, else the
        library's), then filled — ONE Ctrl+Z for both."""
        from . import structure as S
        doc = self._live(self.doc())
        w = next((x for x in doc["walls"] if x["id"] == wall_id), None)
        if w is None:
            return
        moving = getattr(self, "_glazing_moving", None)
        src = next((e for e in doc["structure"] if e["id"] == moving),
                   None) if moving else None
        o = src or self.glazing_opts
        top = self._wall_height(w)
        sill = max(float(o.get("base", 0.0)), 0.0)
        h = min(float(o.get("h", 2.10)), top - S.TALL_GAP - sill)
        void = {"kind": "void", "wall": wall_id, "pos": pos, "w": width,
                "h": round(h, 4), "sill": round(sill, 4), "swing": "left"}
        if src is None:                      # the library's trim and sill
            from . import trim as TR
            void = TR.on_host(void, {k: v for k, v in self.glazing_opts.items()
                                     if k in TR.HOST})
        why = S.opening_room(dict(void, id="~"), w, doc["openings"], top)
        if why:
            compat.flash(self.viewport, f"{why} — try another place", 5000)
            return
        made_o = model.new_openings(doc["openings"], [void])
        doc["openings"] = doc["openings"] + made_o
        op_id = made_o[0]["id"]
        if src is not None:                  # the selected one goes in
            self._glazing_moving = None
            new = []
            for e in doc["structure"]:
                if e["id"] == moving:
                    e = {k: v for k, v in e.items() if k not in ("a", "b")}
                    e.update(place="void", op=op_id, level=w["level"])
                new.append(e)
            doc["structure"] = new
            self._commit_all(doc)
            compat.select_ids(self.viewport, {moving})
            compat.flash(self.viewport, "Opening made, the grid moved "
                         "into it — Ctrl+Z undoes both", 5000)
            return
        rec = dict(self._glazing_rec(), type="glazing", place="void",
                   op=op_id, level=w["level"])
        rec.pop("a", None)
        rec.pop("b", None)
        made = model.new_elements(doc["structure"], [rec])
        doc["structure"] = doc["structure"] + made
        self._commit_all(doc)
        compat.flash(self.viewport, f"Opening made and «{made[0]['name']}» in "
                     "it — Ctrl+Z undoes both", 5000)

    def _glazing_void(self, op_id: str) -> None:
        moving = getattr(self, "_glazing_moving", None)
        if moving:                           # a free one goes in there
            self._glazing_moving = None
            doc = self._live(self.doc())
            if any(e.get("type") == "glazing" and e.get("op") == op_id
                   for e in doc["structure"]):
                compat.flash(self.viewport, "That Opening has its grid "
                             "already", 4000)
                return
            o = next((x for x in doc["openings"] if x["id"] == op_id), None)
            w = next((x for x in doc["walls"]
                      if o is not None and x["id"] == o["wall"]), None)
            new = []
            for e in doc["structure"]:
                if e["id"] == moving:
                    e = {k: v for k, v in e.items() if k not in ("a", "b")}
                    e.update(place="void", op=op_id)
                    if w is not None:
                        e["level"] = w["level"]
                new.append(e)
            doc["structure"] = new
            self._commit_all(doc)
            compat.select_ids(self.viewport, {moving})
            compat.flash(self.viewport, "Moved into the Opening — Ctrl+Z "
                         "undoes it", 5000)
            return
        rec = dict(self._glazing_rec(), type="glazing", place="void", op=op_id)
        rec.pop("a", None)
        rec.pop("b", None)
        self._struct_done([rec])

    def _glazing_window(self, op_id: str) -> None:
        """Security bars on window ``op_id`` — one per window."""
        doc = self._live(self.doc())
        if any(e.get("type") == "glazing" and e.get("op") == op_id
               and e.get("place") == "window" for e in doc["structure"]):
            compat.flash(self.viewport, "That window has its bars already",
                         4000)
            return
        rec = dict(self._glazing_rec(), type="glazing", place="window",
                   op=op_id)
        rec.pop("a", None)
        rec.pop("b", None)
        self._struct_done([rec])

    def _glazing_free(self, a, b) -> None:
        # both ends INSIDE one wall (drawn along it): an Opening there,
        # filled — «Free» inside a wall cut nothing, the grid sat buried in
        # it (his test, 2026-10-16). Beside a wall / across: free, as asked
        from .openingtools import find_wall
        _i, lv, _z0 = self._work_level()
        mine = [w for w in self._live(self.doc())["walls"]
                if w["level"] == lv["id"]]
        ga, gb = find_wall(a, mine), find_wall(b, mine)
        if ga and gb and ga[0]["id"] == gb[0]["id"]:
            wall, seg, s0 = ga
            s1 = gb[2]
            inside = all(abs(seg.project(p)[1]) <= float(wall["t"]) / 2
                         + 0.05 for p in (a, b))
            if inside and abs(s1 - s0) >= 0.2:
                self._glazing_span(wall["id"], round((s0 + s1) / 2, 4),
                                   round(abs(s1 - s0), 4))
                return
        rec = dict(self._glazing_rec(), type="glazing", place="free", a=a, b=b)
        rec.pop("op", None)
        self._struct_done([rec])

    def edit_glazing(self, el: dict) -> None:
        """A grid's own window (glazing.py) — glass or open."""
        from . import glazing as GZ
        from . import structure as S
        doc = self.doc()
        lv = next((r for r in doc["levels"] if r["id"] == el["level"]), None)
        if lv is None:
            return
        info = S.levels_info(doc, model.elevations)
        text = GZ.grid_text(el, doc, lambda l_: info[l_]["z0"]
                            if l_ in info else 0.0)
        host = None
        if el.get("place") != "free":        # its Opening's trim and sill
            host, _w = self._glazing_void_of(doc, el)
        dlg = GZ.GlazingDialog(el, lv, text, self.window, host=host)
        self._in_place(dlg, self.apply_element)
        if not dlg.exec():
            return
        action, new = dlg.result_data()
        if action == "delete":
            self.delete_element(el["id"])
            return
        if action == "hide":
            self.hide_element(el["id"], el["name"])
            return
        self.apply_element(new)
        self._again(dlg, lambda: self.edit_element(el["id"]))

    # ---- Low walls & guards (guards.py — Pro) ------------------------------------------
    @_project_first
    def start_guard(self) -> None:
        """«Low wall»: the library on the right says which (a low wall, with
        a railing, glass, steel) and how high; the tool is out at once on
        the plan of the level worked on — point by point, as walls. It
        stays out for the next one (Esc = done)."""
        if self._pro_only("guard"):
            return
        from . import guards as GD
        self.hub.close_sub()
        self._sel_at_phase = set(self._lib_picked()[1])   # the tool wins
        doc = self.doc()
        _i, lv, z0 = self._work_level()
        lid = lv["id"]
        o = self.guard_opts
        if o.get("how", "draw") != "draw":
            self._guard_pick_tool(doc, lv, z0)
            return
        tool = GD.GuardTool(self._guards_drawn, self._wall_cancelled,
                            z0 + float(o.get("base", 0.0)), lambda: o,
                            self._reader(lambda d: [w for w in d["walls"]
                                                    if w["level"] == lid]))
        tool.level_id = lid
        self._activate(tool)
        compat.flash(self.viewport, f"Low wall on «{lv['name']}» — pick its "
                     "type on the right, then click point after point "
                     "(Enter ends it, C closes it)", 6000)

    def start_separator_tool(self, name: str = "Draw") -> None:
        """«Room separator»: a line between two rooms with no wall (an open
        living room and kitchen) — point by point on the level worked on,
        dashed in the plan, nothing in 3D; «Delete»: click one. The tools
        stay out for the next (Esc = done)."""
        if self._pro_only("separator"):
            return
        from . import separators as SP
        self.hub.close_sub()
        _i, lv, z0 = self._work_level()
        lid = lv["id"]
        if name == "Delete":
            if not SP.of_level(self.doc(), lid):
                compat.flash(self.viewport, f"No room separators on "
                             f"«{lv['name']}»", 4000)
                return
            tool = SP.SeparatorEraseTool(
                lambda: SP.of_level(self.doc(), lid), z0,
                self._separator_deleted, self._wall_cancelled)
            self.method = name
            self._activate(tool)
            self.strip.fill(self.element, self.method)
            return
        done = lambda pts, closed, lid=lid: self._separator_drawn(  # noqa: E731
            lid, pts, closed)
        shape = self.sep_opts.get("shape", "chain")
        cls = SP.SHAPE_TOOLS.get(shape)
        if cls is not None:            # a rectangle / a circle (0.17.0)
            tool = cls(done, self._wall_cancelled, z0)
            how = ("click its centre, then its edge (or type the radius + "
                   "Enter)" if shape == "circle" else
                   "click two corners (or type «3.6;2.8» + Enter)")
        else:
            tool = SP.SeparatorTool(
                done, self._wall_cancelled, z0,
                self._reader(lambda d: [w for w in d["walls"]
                                        if w["level"] == lid]))
            how = "click point after point, from wall to wall (Enter ends it)"
        tool.level_id = lid
        self.method = name
        self._activate(tool)
        self.strip.fill(self.element, self.method)
        QTimer.singleShot(0, self._element_options)   # its shape lit
        compat.flash(self.viewport, f"Room separator on «{lv['name']}» — "
                     + how, 6000)

    def _on_separator_option(self, key: str, value) -> None:
        if key == "shape":
            self.sep_opts["shape"] = value
            QTimer.singleShot(0, lambda: self.start_separator_tool("Draw"))
        QTimer.singleShot(0, self._refill_options)

    def _separator_drawn(self, lid: str, pts, closed) -> None:
        from . import separators as SP
        if closed and len(pts) > 2:
            pts = list(pts) + [pts[0]]
        doc = SP.add(self._live(self.doc()), lid, pts)
        self._commit_all(doc)            # the rooms (and their floors) change
        compat.flash(self.viewport, ("Room separator drawn — the zone inside "
                     "is a room of its own" if closed else "Room separator "
                     "drawn — the rooms on each side are two now")
                     + " · Ctrl+Z undoes it", 5000)

    def _separator_deleted(self, sid: str) -> None:
        from . import separators as SP
        self._commit_all(SP.remove(self._live(self.doc()), sid))
        compat.flash(self.viewport, "Room separator deleted — Ctrl+Z brings "
                     "it back", 4000)

    def _guards_drawn(self, pts, closed) -> None:
        from . import guards as GD
        o = self.guard_opts
        rec = {k: v for k, v in o.items() if k not in GD.TOOL_KEYS}
        self._struct_done([dict(rec, type="guard", pts=pts,
                                closed=bool(closed))])

    def _guard_pick_tool(self, doc: dict, lv: dict, z0: float) -> None:
        """«Slab edge» / «Round an opening» / «Add a gap» (guards.py, phase
        B): one click. What a click would make shows under the mouse."""
        from . import guards as GD
        from . import structure as S
        o = self.guard_opts
        how = o.get("how")
        lid = lv["id"]
        t = float(o.get("t", 0.15)) if o.get("kind", "wall") in (
            "wall", "wallrail", "boundary") else 0.06
        tool = GD.GuardPickTool(lambda *_a: None, self._wall_cancelled,
                                z0 + float(o.get("base", 0.0)), lambda: o,
                                self._reader(lambda d: [w for w in d["walls"]
                                                        if w["level"] == lid]))
        tool.level_id = lid
        tool.mode = how
        if how in ("gap", "gate"):
            def gap_at(p):
                d = self.doc()
                best = None
                for e in d["structure"]:
                    if e.get("type") != "guard" or e.get("level") != lid \
                            or e.get("hidden"):
                        continue
                    s, off = GD.along(e, p)
                    reach = float(e.get("t", 0.15)) / 2 + 0.25
                    if off <= reach and (best is None or off < best[0]):
                        best = (off, e, s)
                if best is None:
                    return None
                _off, e, s = best
                w = float(o.get("gap_w", 0.90))
                L = GD.length(e)
                # a gate: in the gap under the mouse, when there is one
                had = next(((a, b) for a, b in GD.gaps_of(e)
                            if a - 0.01 <= s <= b + 0.01), None) \
                    if how == "gate" else None
                if had is not None:
                    a, b = had
                elif w > L - GD.MIN_PIECE:
                    return None
                else:
                    a, b = s - w / 2, s + w / 2
                if had is None and not e.get("closed"):
                    a, b = (0.0, w) if a < 0 else (L - w, L) if b > L \
                        else (a, b)
                ps = [GD.point_at(e, a)[0]]
                (x, y), u = GD.point_at(e, (a + b) / 2)
                ps += [(x, y), GD.point_at(e, b)[0]]
                n = (-u[1], u[0])
                h = float(e.get("t", 0.15)) / 2 + 0.05
                ticks = [([[q[0] + n[0] * h, q[1] + n[1] * h],
                           [q[0] - n[0] * h, q[1] - n[1] * h]], False)
                         for q in (ps[0], ps[-1])]
                return e["id"], s, [([list(q) for q in ps], False)] + ticks
            tool.gap_at = gap_at
            tool.on_pick = self._guard_gap if how == "gap" else \
                self._guard_gate
            self._activate(tool)
            compat.flash(self.viewport, "Add a gap: click on a low wall / "
                         "guard — its width on the right (drag its edges "
                         "after)" if how == "gap" else
                         "Add a gate: click a gap — or a wall: a gap is "
                         "opened with it (its width on the right)", 6000)
            return
        walls = GD.walls_union([w for w in doc["walls"] if w["level"] == lid])
        arrs = GD.arrivals(doc, model.elevations, z0)
        targets = []
        try:
            if how == "edge":
                holes = GD.level_holes(doc, lid, S.flight_cuts(
                    doc, model.elevations).get(lid, []))
                for poly in GD.level_slabs(doc, lid):
                    targets.append((poly, GD.edge_lines(poly, t, walls, arrs,
                                                        holes)))
            else:
                cuts = S.flight_cuts(doc, model.elevations).get(lid, [])
                slabs = GD.level_slabs(doc, lid)
                from shapely.ops import unary_union
                su = unary_union(slabs) if slabs else None
                for hole in GD.level_holes(doc, lid, cuts):
                    targets.append((hole, GD.hole_lines(hole, t, su, walls,
                                                        arrs)))
        except Exception as ex:  # noqa: BLE001 — said, never a crash
            compat.flash(self.viewport, f"Low wall: {ex}", 5000)
            return
        if not targets:
            compat.flash(self.viewport, f"«{lv['name']}» has no slab" if
                         how == "edge" else f"«{lv['name']}»'s slabs have "
                         "no opening", 5000)
        tool.targets = targets
        tool.on_pick = lambda k: self._guard_lines(targets[k][1])
        self._activate(tool)
        compat.flash(self.viewport, (
            f"Low wall along a slab's edge on «{lv['name']}» — click a slab"
            if how == "edge" else
            f"Low wall round an opening on «{lv['name']}» — click one"),
            6000)

    def _guard_lines(self, lines) -> None:
        """The guards a one-click made: stored (one Ctrl+Z), selected."""
        from . import guards as GD
        o = self.guard_opts
        rec = {k: v for k, v in o.items() if k not in GD.TOOL_KEYS}
        if self._struct_done([dict(rec, type="guard", pts=pts,
                                   closed=bool(closed))
                              for pts, closed in lines]):
            compat.select_ids(self.viewport, set(self._last_made))

    def _guard_gap(self, got) -> None:
        """A gap opened in a guard there (one Ctrl+Z)."""
        from . import guards as GD
        gid, s, _lines = got
        doc = self._live(self.doc())
        w = float(self.guard_opts.get("gap_w", 0.90))
        new = []
        for e in doc["structure"]:
            if e["id"] == gid:
                e = GD.with_gap(e, s, w)
            new.append(e)
        doc["structure"] = new
        self._commit_all(doc)
        compat.select_ids(self.viewport, {gid})
        compat.flash(self.viewport, f"A {compat.fmt_len(w)} gap — drag its "
                     "edges to "
                     "move / widen it; Ctrl+Z undoes it", 5000)

    def _guard_gate(self, got) -> None:
        """A gate put in a guard's gap there — a gap opened for it when
        there is none (one Ctrl+Z)."""
        from . import guards as GD
        gid, s, _lines = got
        doc = self._live(self.doc())
        o = self.guard_opts
        w = float(o.get("gap_w", 0.90))
        new = []
        for e in doc["structure"]:
            if e["id"] == gid:
                e = GD.with_gate(e, s, GD.gate_of(o), w)
            new.append(e)
        doc["structure"] = new
        self._commit_all(doc)
        compat.select_ids(self.viewport, {gid})
        compat.flash(self.viewport, "A gate — click another gap for one "
                     "more; other options, then a click on it: changed. "
                     "Ctrl+Z undoes it", 5000)

    def edit_guard(self, el: dict) -> None:
        """A low wall's / guard's own window (guards.py)."""
        from . import guards as GD
        doc = self.doc()
        lv = next((r for r in doc["levels"] if r["id"] == el["level"]), None)
        if lv is None:
            return
        dlg = GD.GuardDialog(el, lv, self.window)
        self._mat_tab(dlg, "guard", el["id"])
        self._in_place(dlg, self.apply_element)
        if not dlg.exec():
            return
        action, new = dlg.result_data()
        self._mat_take(dlg, action)
        if action == "delete":
            self.delete_element(el["id"])
            return
        if action == "hide":
            self.hide_element(el["id"], el["name"])
            return
        self.apply_element(new)
        self._again(dlg, lambda: self.edit_element(el["id"]))

    def _ramp_defaults(self, doc: dict, opts=None, kind="ramp") -> dict:
        """The last ramp (stair) set up — or, the first time, from the level
        worked on up to the one over it: it is born on, and belongs to, the
        level it is drawn on."""
        rec = dict(self.bramp_opts if opts is None else opts, type=kind)
        from . import ramps as R
        ids = [lv["id"] for lv in doc["levels"]]
        # the last one's LEVELS only when it would belong to the level
        # worked on — a stair drawn on Level 2 went down to the basements,
        # where the previous one was (his report, 2026-10-22); its shape,
        # width, steps… are kept all the same
        _i, cur, _z = self._work_level()
        try:
            mine = R.from_level(rec) in ids and R.owner(
                rec, doc, model.elevations) == cur["id"]
        except Exception:  # noqa: BLE001 — a record from an older file
            mine = False
        if not mine:
            # BORN ON THE LEVEL IT IS DRAWN ON (his rule, 2026-10-26: «it
            # starts on the level's floor and ends at its ceiling — it
            # belongs to the level it exists for»). Before, from the level
            # UNDER up to this one (2026-10-05): a stair drawn on Basement 1
            # went to Basement 2, the view jumping there, and with the plan
            # showing its own level only it vanished from the one drawn on.
            i, lv, _z = self._work_level()
            levels = doc["levels"]
            lo, hi = i, i + 1
            if hi >= len(levels):
                hi = None
            rec["from"] = rec["level"] = levels[lo]["id"]
            rec["start"] = "level"
            rec["to"] = levels[hi]["id"] if hi is not None else "z"
            if hi is None:
                # no level above (one level only, or the top one): UP one
                # storey of that level — DEFAULT's −3.00 (a basement ramp)
                # sent a stair on a lone Level 1 three metres DOWN (his
                # report, 2026-10-23, seen twice)
                z_lo = R.level_z(doc, model.elevations)[levels[lo]["id"]]
                rec["to_z"] = round(z_lo + float(
                    levels[lo].get("height") or 3.0), 3)
        to = rec.get("to")
        if to not in ids + ["z"] and not (isinstance(to, str) and to.startswith(
                R.TOP) and to[len(R.TOP):] in ids):
            rec["to"] = "z"
        return rec

    #: what a ramp / stair set up keeps for the next one
    FLIGHT_KEYS = {
        "ramp": ("start", "from", "level", "to", "to_z", "from_z", "w",
                 "slope", "fix", "L", "t", "shape", "turn", "landing",
                 "anchor", "build", "top_landing", "foot_landing"),
        "stair": ("start", "from", "level", "to", "to_z", "from_z", "w",
                  "riser",
                  "tread", "fix_tread", "t", "shape", "turn", "landing",
                  "anchor", "build", "top_landing", "foot_landing")}

    def start_ramp(self) -> None:
        if self._pro_only("ramp"):
            return
        self._start_flight("ramp")

    @_project_first
    def _start_flight(self, kind: str) -> None:
        """Ramp / stair: the LIBRARY on the right sets it up — its type,
        details and fields (his call, 2026-10-09: no window first) — and the
        tool is out at once, on the plan of its level: click where it
        starts, click the way it goes. It stays out for the next one (Esc =
        done)."""
        from . import ramps as R
        from . import stairs as ST
        doc = self.doc()
        self.hub.close_sub()
        self._sel_at_phase = set(self._lib_picked()[1])   # the tool wins
        rec = self._ramp_defaults(doc, self.bramp_opts if kind == "ramp"
                                  else self.bstair_opts, kind)
        # it belongs to the lower of its two levels (as its window says)
        rec["level"] = R.owner(rec, doc, model.elevations)
        self.set_floor(rec["level"], quiet=True)     # drawn on its level
        _i, lv, z0 = self._work_level()
        made = {}

        def heights_at(p):                 # its record NOW: the library
            return R.heights(dict(made["tool"].rec, x=p[0], y=p[1]), doc,
                             model.elevations)
        if kind == "ramp":
            def length_at(p):
                zs, ze = heights_at(p)
                return R.length_of(made["tool"].rec, zs, ze), zs, ze
            tool = R.RampTool(rec, length_at, self._ramp_placed,
                              self._wall_cancelled, z0)
        else:
            tool = ST.StairTool(rec, heights_at, self._ramp_placed,
                                self._wall_cancelled, z0)
        made["tool"] = tool
        tool.level_id = lv["id"]
        self._activate(tool)
        compat.flash(self.viewport, f"{kind.capitalize()} from "
                     f"«{lv['name']}» — set it up on the right, then click "
                     "where it starts", 5000)

    def _flight_changed(self, kind: str, rec: dict) -> None:
        """«Sizes & levels…» changed the ramp / stair being placed: the
        tool draws it so at once — on its level, if that changed."""
        opts = self.bramp_opts if kind == "ramp" else self.bstair_opts
        opts.update({k: rec[k] for k in self.FLIGHT_KEYS[kind] if k in rec})
        tool = getattr(self.viewport, "active_tool", None)
        if self.tool_element() != kind or tool is None:
            return
        tool.rec = {k: v for k, v in rec.items() if k not in ("x", "y",
                                                               "angle")}
        if rec.get("level") and rec["level"] != tool.level_id:
            self.set_floor(rec["level"], quiet=True)
            _i, lv, z0 = self._work_level()
            tool.z, tool.level_id = z0, lv["id"]
        self.viewport.update()

    def _lib_fields(self, key, ids):
        """(make, ident) of the preview under a Building element's cards:
        of the ONE selected, else of the one being placed — made anew when
        its record changes (a card, «Sizes & levels…»)."""
        from . import library as LB
        if edition.lite() and is_pro(key):
            return None, None
        if key == "wall" and not ids and self.wall_opts.get("cw"):
            # a curtain wall to DRAW: its details before (his ask,
            # 2026-10-14), as «More…» in the bar
            return self._curtain_more_box, ("cw_more",)
        if key == "wall" and len(ids) > 1:
            n = len(self._selected_curtains())
            if n == len(ids):
                # several curtain walls selected: edit them all at once
                return (lambda: self._curtain_more_box(n),
                        ("cw_more", n))
        if key not in LB.BUILDING_ELEMENTS:
            # a phase's element: its sizes are the options bar's; ONE
            # selected → its window, as a double-click (his ask, 2026-10-09)
            if len(ids) != 1:
                return None, None
            return (lambda: self._window_button(key, ids[0]),
                    ("win", key, ids[0]))
        if ids:
            rec = self._lib_record(ids[0]) if len(ids) == 1 else None
            if rec is None:
                return None, None
            return (lambda: self._flight_preview(key, rec, ids[0]),
                    ("sel", key, ids[0], repr(sorted(rec.items()))))
        tool = getattr(self.viewport, "active_tool", None)
        if self.tool_element() != key or tool is None:
            return None, None
        rec = dict(tool.rec)
        return (lambda: self._flight_preview(key, rec, None),
                ("new", key, repr(sorted(rec.items()))))

    def _curtain_more_box(self, n: int = 0):
        """Under the curtain wall's choices in the library: what «More…»
        sets, in a line, and the button (orange outline). ``n`` > 1: that
        many curtain walls selected — edited all at once."""
        from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton,
                                       QVBoxLayout, QWidget)
        from . import library as LB
        box = QWidget()
        col = QVBoxLayout(box)
        col.setContentsMargins(0, 4, 0, 0)
        col.setSpacing(6)
        lab = QLabel(f"{n} curtain walls selected: what you change in "
                     "«More…» goes to all of them." if n > 1 else
                     "Mullions, corner posts, transoms — their width and "
                     "depth — the band, the glass and its transparency: "
                     "set them before you draw.")
        lab.setWordWrap(True)
        lab.setObjectName("axq_caption")
        col.addWidget(lab)
        row = QHBoxLayout()
        b = QPushButton("More…")
        b.setStyleSheet(LB.ACTION_CSS)
        b.setToolTip("The curtain wall's details, for the next ones drawn")
        b.clicked.connect(lambda: QTimer.singleShot(0, self.curtain_more))
        row.addStretch(1)
        row.addWidget(b)
        row.addStretch(1)
        col.addLayout(row)
        return box

    def _window_button(self, key: str, rid: str):
        """«Sizes & details…» under the library of a selected element: its
        own window — the one a double-click opens."""
        from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget
        from . import library as LB
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        b = QPushButton("Sizes && details…")       # «&&»: a plain «&»
        b.setStyleSheet(LB.ACTION_CSS)
        b.setToolTip("Its window (as a double-click): every size, its "
                     "material, delete")
        if key == "wall":
            go = self.edit_wall
        elif key in ("door", "window", "void"):
            go = self.edit_opening
        else:
            go = self.edit_element
        b.clicked.connect(lambda: go(rid))
        row.addStretch(1)
        row.addWidget(b)
        row.addStretch(1)
        return box

    @staticmethod
    def _end_name(doc: dict, end) -> str:
        """A ramp's / stair's end, in words: a level, a level's top, the
        terrain, an elevation."""
        from . import ramps as R
        if end == "terrain":
            return "Terrain"
        top = isinstance(end, str) and end.startswith(R.TOP)
        lid = end[len(R.TOP):] if top else end
        lv = next((x for x in doc["levels"] if x["id"] == lid), None)
        if lv is None:
            return "Elevation"
        return ("Top of " if top else "") + lv["name"]

    def _flight_preview(self, key: str, rec: dict, rid):
        """What the ramp / stair will be (or is): its side drawing, a line
        saying it, «Sizes & levels…» — its window. The library says WHAT
        (cards, chips), the window HOW MUCH (his call, 2026-10-09)."""
        from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton,
                                       QVBoxLayout, QWidget)
        from . import library as LB
        from . import ramps as R
        from . import stairs as ST
        doc = self.doc()
        r = dict(rec)
        r.setdefault("x", 0.0)
        r.setdefault("y", 0.0)
        zs, ze = R.heights(r, doc, model.elevations)
        known = r.get("start") != "terrain" or rid is not None
        if not known and doc.get("plot"):     # placed: the ground decides
            hs = doc["plot"].get("heights") or [0.0]
            zs = sum(hs) / len(hs)
        if key == "stair":
            view = ST._Steps()
            view.set(r, zs, ze, known)
            s = ST.steps(r, zs, ze)
            what = (f"{s['n']} risers × {compat.fmt_cm(abs(s['h']))} · tread "
                    f"{compat.fmt_cm(s['p'])} · run {compat.fmt_len(s['L'])}")
        else:
            view = R._Profile()
            L, slope = R.length_of(r, zs, ze), R.slope_of(r, zs, ze)
            land = 0.0
            if r.get("shape") in ("L", "U"):
                land = float(r["landing"])
                if r["shape"] == "L":
                    land = max(land, float(r["w"]))
            view.set(zs, ze, L, round(slope, 1), known, land,
                     r.get("shape", "straight"))
            what = f"{slope:.1f} % · {compat.fmt_len(L)}"
        tl = float(r.get("top_landing", 0.0) or 0.0)
        if tl >= 0.01:                    # its landing at the top
            what += f" · landing {compat.fmt_len(tl)} at the top"
        fl = float(r.get("foot_landing", 0.0) or 0.0)
        if fl >= 0.01:                    # …and at the bottom
            what += f" · landing {compat.fmt_len(fl)} at the bottom"
        view.setMinimumSize(200, 150)
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(view)
        start = r.get("start") if r.get("start") in ("terrain", "z") else \
            R.from_level(r)
        line = QLabel(f"{self._end_name(doc, start)} "
                      f"{compat.fmt_level(zs, unit=False)}  →  "
                      f"{self._end_name(doc, r.get('to'))} "
                      f"{compat.fmt_level(ze, unit=False)}"
                      + ("  (≈ the ground)" if not known else "")
                      + f"\n{what} · width {compat.fmt_len(float(r['w']))}")
        line.setWordWrap(True)
        line.setStyleSheet("color: #d6d9dd;")
        lay.addWidget(line)
        row = QHBoxLayout()
        b = QPushButton("Sizes && levels…")      # «&&»: a plain «&»
        b.setStyleSheet(LB.ACTION_CSS)
        b.setToolTip("Its window: levels, width, " + (
            "riser and tread" if key == "stair" else "slope and length")
            + (", material, repeat, delete" if rid else
               " — for the next one you place"))
        b.clicked.connect(lambda: self.edit_element(rid) if rid
                          else self._flight_setup(key))
        row.addStretch(1)
        row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        return box

    def _flight_setup(self, key: str) -> None:
        """«Sizes & levels…» with nothing selected: the window for the ramp
        / stair being placed — OK, and it is placed so."""
        from . import ramps as R
        from . import stairs as ST
        tool = getattr(self.viewport, "active_tool", None)
        if self.tool_element() != key or tool is None:
            return
        cls = R.RampDialog if key == "ramp" else ST.StairDialog
        dlg = cls(dict(tool.rec), self.doc(), model.elevations, edit=False,
                  parent=self.window)
        if not dlg.exec():
            return
        _a, rec = dlg.result_data()
        self._flight_changed(key, rec)
        QTimer.singleShot(0, self._library_show)

    def _ramp_placed(self, rec: dict) -> None:
        rec = {k: v for k, v in rec.items() if k not in ("id", "name")}
        self._struct_done([rec])

    def edit_ramp(self, el: dict) -> None:
        """A ramp's own window: from / to, sizes, where it is; delete."""
        from . import ramps as R
        dlg = R.RampDialog(el, self.doc(), model.elevations, edit=True,
                           parent=self.window)
        self._mat_tab(dlg, "ramp", el["id"])
        self._in_place(dlg, self.apply_element)
        if not dlg.exec():
            return
        action, new = dlg.result_data()
        self._mat_take(dlg, action)
        if action == "delete":
            self.delete_element(el["id"])
            return
        if action == "hide":
            self.hide_element(el["id"], el["name"])
            return
        if action.startswith("repeat_"):
            self.repeat_element(new, action == "repeat_up")
            return
        self.apply_element(new)
        self._again(dlg, lambda: self.edit_element(el["id"]))

    def start_stair(self) -> None:
        if self._pro_only("stair"):
            return
        self._start_flight("stair")

    def edit_stair(self, el: dict) -> None:
        from . import stairs as ST
        dlg = ST.StairDialog(el, self.doc(), model.elevations, edit=True,
                             parent=self.window)
        self._mat_tab(dlg, "stair", el["id"])
        self._in_place(dlg, self.apply_element)
        if not dlg.exec():
            return
        action, new = dlg.result_data()
        self._mat_take(dlg, action)
        if action == "delete":
            self.delete_element(el["id"])
            return
        if action == "hide":
            self.hide_element(el["id"], el["name"])
            return
        if action.startswith("repeat_"):
            self.repeat_element(new, action == "repeat_up")
            return
        self.apply_element(new)
        self._again(dlg, lambda: self.edit_element(el["id"]))

    def repeat_element(self, el: dict, up: bool) -> None:
        """The same ramp / stair, in the same place, ONE LEVEL up (or down)
        — both its ends move a level, its way (going up or down) kept:
        stacked flights. Its changes in the window come along. When it
        can't, a window says why (a status line went unseen)."""
        from PySide6.QtWidgets import QMessageBox
        from . import ramps as R
        doc = self._live(self.doc())
        noun = el["type"].capitalize()

        def say(text: str) -> None:
            QMessageBox.information(self.window, f"Repeat the {noun.lower()}",
                                    text)
        zs_of = R.level_z(doc, model.elevations)
        order = [lid for _z, lid in sorted((z, lid)
                                           for lid, z in zs_of.items())]
        # past the highest level's floor: its top (a stair up inside it)
        order.append(R.TOP + order[-1])
        if el.get("start") in ("terrain", "z") or el.get("to") not in order:
            say(f"Repeat works between levels — this {noun.lower()} starts "
                "on the terrain, or one of its ends is an elevation.")
            return
        k = 1 if up else -1
        a, b = order.index(R.from_level(el)) + k, order.index(el["to"]) + k
        if not (0 <= a < len(order) and 0 <= b < len(order)):
            names = {lv["id"]: lv["name"] for lv in doc["levels"]}
            edge = names[order[-2] if up else order[0]]
            say(f"There is no level {'above' if up else 'below'} to repeat "
                f"it on — «{edge}» is the {'top' if up else 'lowest'} one"
                + (" and it already reaches its top" if up else "")
                + ". Add a level first (Project › Levels).")
            return
        rec = {k_: v for k_, v in el.items() if k_ not in ("id", "name")}
        rec.update({"from": order[a], "to": order[b], "start": "level"})
        rec["level"] = R.owner(rec, doc, model.elevations)
        self.set_floor(rec["level"], quiet=True)
        if not self._struct_done([rec]):
            say(f"There is already a {noun.lower()} like it there.")

    # ---- Walls: their own window ----------------------------------------------------
    @staticmethod
    def wall_of(group) -> str | None:
        """The wall (its id) a group stands for, or None."""
        if compat.kind_of(group) != "wall":
            return None
        rec = (getattr(group, "ext", None) or {}).get(compat.EXT_KEY) or {}
        return rec.get("id")

    def edit_wall(self, wall_id: str) -> None:
        """A wall's own window (modal): name, thickness, alignment, side,
        height, base, length; delete. Apply = one Ctrl+Z."""
        from .dialogs import WallDialog
        doc = self.doc()
        wall = next((w for w in doc["walls"] if w["id"] == wall_id), None)
        if wall is None:
            return
        lv = next((r for r in doc["levels"] if r["id"] == wall["level"]),
                  None)
        if lv is None:
            return
        self.hub.close_sub()
        # («_under»: how high a level-height wall really stands — under the
        # slab above; a new sloped top starts from it)
        dlg = WallDialog(wall, dict(lv, _under=self._wall_height(
            dict(wall, height="level"))), self.window,
                         types=doc.get("wall_types") or [])
        self._mat_tab(dlg, "wall", wall_id)
        self._layer_eyes(dlg, wall_id)
        apply = self._batch_window(dlg, "wall", wall_id, self.apply_wall,
                                   "walls", lambda: self.edit_wall(wall_id))
        self._in_place(dlg, apply)
        self._live_window(dlg, "wall")         # L2: it, live (livewin.py)
        if not dlg.exec():
            return
        action, new = dlg.result_data()
        self._mat_take(dlg, action)
        if action == "delete":
            self.delete_wall(wall_id)
        elif action == "hide":
            self.hide_element(wall_id, wall["name"])
        else:
            apply(new)
            self._again(dlg, lambda: self.edit_wall(wall_id))

    def _commit_level_walls(self, level_id: str, mine: list[dict]) -> None:
        """Store this level's walls as ``mine`` and rebuild the building
        (joins and all) — one Ctrl+Z."""
        doc = self._live(self.doc())
        doc["walls"] = [w for w in doc["walls"] if w["level"] != level_id] \
            + mine
        self._commit_all(doc)
        self._wall_cache = self._live_walls(self.doc(), level_id)

    def apply_wall(self, new: dict) -> None:
        """A wall changed in its window."""
        from . import walls as W
        why = W.why_not(new)
        if why:
            compat.flash(self.viewport, f"«{new['name']}» not changed — "
                         f"{why}", 6000)
            return
        if new.get("cw"):
            # the LAST edit of a curtain wall = the hidden preset: the next
            # ones drawn (and «More…») take it (his ask, 2026-10-14)
            self._curtain_preset(new)
        # its TYPE (0.15.0, A2): every wall of it changed, or these layers
        # saved as a new type — the types are the document's
        doc = self._live(self.doc())
        self._keep_type_look(doc, new)
        new, named, every = self._wall_types(doc, new)
        if every or named:
            doc["walls"] = [new if w["id"] == new["id"] else w
                            for w in doc["walls"]]
            self._busy_commit(doc, sum(
                1 for w in doc["walls"] if w.get("type") == new.get("type"))
                if every else 1, "{n} walls of the type updated")
            self._wall_cache = self._live_walls(self.doc(), new["level"])
            n = sum(1 for w in self.doc()["walls"]
                    if w.get("type") == new.get("type"))
            compat.flash(self.viewport, (tr("Type «{t}» saved — in the "
                                            "library, for the next walls",
                                            t=named) if named else
                                         tr("{n} walls of the type updated",
                                            n=n))
                         + " — Ctrl+Z undoes it", 6000)
            QTimer.singleShot(0, self._library_show)
            return
        mine = self._live_walls(self.doc(), new["level"])
        old = next((w for w in mine if w["id"] == new["id"]), None)
        more = []
        if old is not None and new.get("kind", "line") == "line" and (
                list(old.get("a", ())) != list(new["a"])
                or list(old.get("b", ())) != list(new["b"])):
            # Start / End typed — its direction may have changed: the walls
            # joined to it follow (a user on YouTube, 2026-10-14: «the
            # other walls don't follow and the corner isn't updated»)
            from . import wallmove
            doc = self._live(self.doc())
            doc, more = wallmove.reshape(doc, {new["id"]: new})
            doc["walls"] = [new if w["id"] == new["id"] else w
                            for w in doc["walls"]]
            self._commit_all(doc)
            self._wall_cache = self._live_walls(self.doc(), new["level"])
        else:
            self._commit_level_walls(new["level"], [new if w["id"] == new["id"]
                                                    else w for w in mine])
        compat.flash(self.viewport, f"«{new['name']}» updated"
                     + (" — " + ", ".join(more) if more else "")
                     + " — Ctrl+Z undoes it", 5000)

    def _keep_type_look(self, doc: dict, new: dict) -> None:
        """«Only this one»: the wall leaves its type — and keeps wearing
        the type's look, now its own (his test, 01/11: its layers edited,
        «only this one», and the wall came out bare — the look lives in
        the type). What the Material tab picked still wins."""
        from . import materials as M
        tid = M.wall_type_of(doc, new["id"])       # (the wall as it was)
        if not tid or new.get("type") or new.get("_new_type"):
            return
        look = ((doc.get("materials") or {}).get("wtype") or {}).get(tid)
        if not look:
            return
        own = ((doc.get("materials") or {}).get("el") or {}).get(new["id"])
        parts = {p: r for p, r in look.items() if p not in (own or {})}
        if not parts:
            return
        carry = {"kind": "wall", "id": new["id"], "all": False,
                 "parts": parts}
        pend = getattr(self, "_pending_mat", None)
        if pend is None:
            self._pending_mat = carry
        elif isinstance(pend, dict) and pend.get("id") == new["id"] \
                and not pend.get("all"):
            carry["parts"].update(pend.get("parts") or {})
            self._pending_mat = carry
        else:                              # «Use for all» too: both, in turn
            self._pending_mat = [carry] + (pend if isinstance(pend, list)
                                           else [pend])

    @staticmethod
    def _wall_types(doc: dict, new: dict) -> tuple[dict, str | None, bool]:
        """(the wall without the window's type marks, the new type's name,
        «every wall of it») — ``doc["wall_types"]`` changed by them: the
        new type added (the wall set to it), or its type's layers = the
        wall's."""
        new = dict(new)
        every = new.pop("_type_all", False)
        named = new.pop("_new_type", None)
        if not (every or named):
            return new, None, False
        types = [dict(t) for t in doc.get("wall_types") or []]
        ls = [dict(la) for la in new.get("layers") or []] or [
            {"id": "core", "name": "", "t": new["t"], "role": "core"}]
        if named:
            # (its id came with it: an Apply then OK updates the same)
            tid = named["id"]
            was = new.get("type")
            types = [t for t in types if t["id"] != tid]
            types.append({"id": tid, "name": named["name"], "layers": ls,
                          "t": new["t"], "frame": new.get("frame")})
            new["type"] = tid
            named = named["name"]
            # the new type wears the look of the one it came from (31/10)
            m = doc.get("materials") or {}
            looks = dict(m.get("wtype") or {})
            if was in looks and tid not in looks:
                looks[tid] = dict(looks[was])
                doc["materials"] = dict(m, wtype=looks)
        elif new.get("type"):
            types = [dict(t, layers=ls, t=new["t"], frame=new.get("frame"))
                     if t["id"] == new["type"] else t for t in types]
        doc["wall_types"] = types
        return new, named, bool(every)

    def delete_wall(self, wall_id: str) -> None:
        """Take a wall away (its neighbours join again without it)."""
        doc = self.doc()
        wall = next((w for w in doc["walls"] if w["id"] == wall_id), None)
        if wall is None:
            return
        mine = [w for w in self._live_walls(doc, wall["level"])
                if w["id"] != wall_id]
        self._commit_level_walls(wall["level"], mine)
        compat.flash(self.viewport, f"«{wall['name']}» deleted — Ctrl+Z "
                     "brings it back", 5000)

    def edit_setbacks(self) -> None:
        """The setbacks' own window (modal): every side's role and
        distance, previewed on the model. Apply = one Ctrl+Z."""
        from .dialogs import SetbacksDialog
        doc = self.doc()
        if not self.has_plot(doc):
            compat.flash(self.viewport, "Draw the plot first")
            return
        self.hub.close_sub()
        dlg = SetbacksDialog(doc["plot"], self.window, self._preview_setbacks,
                             view=self._view_pair())
        try:
            ok = dlg.exec()
        finally:
            self._preview_setbacks(None)
        if ok:
            front, custom, role, dist = dlg.result_data()
            self.set_setbacks(front, custom, dist, role)
            compat.flash(self.viewport, "Setbacks updated — Ctrl+Z undoes "
                         "it", 4000)
            self._again(dlg, self.edit_setbacks)

    def _preview_setbacks(self, preview) -> None:
        """(plot, active side) drawn while the Setbacks window is open."""
        self.setback_preview = preview
        self.viewport.update()

    # ---- What is shown (view state, never an undo step) ------------------------------
    def view_on(self, name: str) -> bool:
        return bool(self.doc()["view"].get(name, True))

    def dims_on(self, name: str) -> bool:
        """Figures on the model (``plot_dims`` / ``setback_dims``): what
        was chosen in the element's own window rules; not chosen yet →
        the Settings (by default: in the Terrain phase)."""
        from . import prefs
        chosen = self.doc()["view"].get(name)
        if chosen is not None:
            return bool(chosen)
        mode = prefs.get("plot_dims")
        return mode == "always" or (mode == "terrain"
                                    and self.current == "terrain")

    def set_view(self, name: str, on) -> None:
        """Set what is shown (from a window's checkbox): never an undo."""
        compat.set_view_flag(self.viewport, self.app.key, name, on)
        if name == "folds":
            doc = self.doc()
            if self.has_plot(doc):
                p = doc["plot"]
                compat.show_folds(self.viewport,
                                  compat.find_plot(self.viewport, p["uid"]),
                                  p["corners"], p["breaks"], bool(on))
        self._outline_soon()

    def _view_pair(self):
        """(get, set) for a window's «Show on the model» checkboxes."""
        def get(name: str) -> bool:
            return self.dims_on(name) if name.endswith("_dims") \
                else self.view_on(name)
        return get, self.set_view

    def open_plot_window(self) -> None:
        """Double-click on the plot: the window of what you are working
        on — Setbacks in Terrain › Setbacks, else the sides table."""
        if self.current == "terrain" and self.element == "setbacks":
            self.edit_setbacks()
        else:
            self.edit_plot_table()

    def toggle_view(self, name: str) -> None:
        self.set_view(name, not self.view_on(name))
        self._sync_outliner(force=True)

    def set_setbacks(self, front=None, custom=None, dist=None,
                     role=None) -> None:
        """Front marks / a side's own distance / the role distances / a
        side's role by hand: the document only (no geometry), one Ctrl+Z."""
        doc = self.doc()
        if not self.has_plot(doc):
            return
        p = doc["plot"]
        if front is not None:
            p["sb_front"] = list(front)
        if custom is not None:
            p["sb_custom"] = list(custom)
        if role is not None:
            p["sb_role"] = list(role)
        if dist is not None:
            p["sb_dist"] = dict(p["sb_dist"], **dist)
        self.save(doc)
        # after the signal that brought us here (the panel's own field is
        # rebuilt by the refresh)
        QTimer.singleShot(0, self.refresh)
        self.viewport.update()

    def _context_menu(self, menu, selection) -> None:
        """Right-click: ArchXQ ▸ what can be done to what is selected — in
        the language set (the host's menu: the auto translation never sees
        it; English in Portuguese, IngeTrazo 0.5.9 test, 2026-10-20)."""
        before = set(menu.actions())
        self._context_menu_build(menu, selection)
        for act in menu.actions():
            sub = act.menu()
            if act in before or sub is None:
                continue
            for a in sub.actions():
                if not a.isSeparator():
                    a.setText(tr(a.text()))
                    if a.statusTip():
                        a.setStatusTip(tr(a.statusTip()))

    def _context_menu_build(self, menu, selection) -> None:
        """Right-click on the plot: ArchXQ ▸ what can be done to it."""
        if not (self.alive and self.active):
            return
        groups = [e for e in selection if type(e).__name__ == "Group"]
        walls = [w for w in (self.wall_of(g) for g in groups) if w]
        if len(walls) == 1:                      # a wall
            sub = menu.addMenu("ArchXQ")
            a = sub.addAction("Wall…")
            a.setStatusTip("Its thickness, alignment, side, height, length")
            a.triggered.connect(lambda _=False, w=walls[0]: QTimer.singleShot(
                0, lambda: self.edit_wall(w)))
            b = sub.addAction("Delete wall")
            b.setStatusTip("Take it away — the walls it met join again "
                           "without it")
            b.triggered.connect(lambda _=False, w=walls[0]: QTimer.singleShot(
                0, lambda: self.delete_wall(w)))
            self._add_picks(sub, walls[0])
            return
        ops = [o for o in (self.opening_of(g) for g in groups) if o]
        if len(ops) == 1:                        # a door, a window
            okind = compat._rec(next(g for g in groups
                                     if self.opening_of(g))).get("okind",
                                                                 "door")
            label = {"door": "Door", "window": "Window"}.get(okind,
                                                              "Opening")
            sub = menu.addMenu("ArchXQ")
            a = sub.addAction(f"{label}…")
            a.triggered.connect(lambda _=False, i=ops[0]: QTimer.singleShot(
                0, lambda: self.edit_opening(i)))
            b = sub.addAction(f"Delete {label.lower()}")
            b.triggered.connect(lambda _=False, i=ops[0]: QTimer.singleShot(
                0, lambda: self.delete_opening(i)))
            self._add_picks(sub, ops[0])
            return
        els = [(g, e) for g, e in ((g, self.element_of(g)) for g in groups)
               if e]
        if len(els) == 1 and els[0][1].startswith("floor:"):   # a room's
            g, eid = els[0]                                      # floor
            sub = menu.addMenu("ArchXQ")
            a = sub.addAction(f"{g.name}…")
            a.setStatusTip("Its material")
            a.triggered.connect(lambda _=False, e=eid: QTimer.singleShot(
                0, lambda: self.edit_element(e)))
            b = sub.addAction("Slab…")
            b.triggered.connect(lambda _=False, e=compat._rec(g).get("id"):
                                QTimer.singleShot(
                                    0, lambda: self.edit_element(e)))
            return
        if len(els) == 1:                        # a column, beam, slab…
            from . import structure as S
            g, eid = els[0]
            label = S.LABEL[compat.kind_of(g)]
            sub = menu.addMenu("ArchXQ")
            a = sub.addAction(f"{label}…")
            a.setStatusTip("Its sizes, its name")
            a.triggered.connect(lambda _=False, e=eid: QTimer.singleShot(
                0, lambda: self.edit_element(e)))
            b = sub.addAction(f"Delete {label.lower()}")
            b.triggered.connect(lambda _=False, e=eid: QTimer.singleShot(
                0, lambda: self.delete_element(e)))
            self._add_picks(sub, eid)
            return
        digs = [d for d in (self.dig_of(g) for g in groups) if d]
        if len(digs) == 1:                       # an excavation
            sub = menu.addMenu("ArchXQ")
            fill = any(compat.kind_of(g) == "fill" for g in groups)
            a = sub.addAction("Fill…" if fill else "Excavation…")
            a.setStatusTip("Its top, edges and volume" if fill else
                           "Its bottom (a ramp: per corner), corners, "
                           "volume")
            a.triggered.connect(lambda _=False, d=digs[0]: QTimer.singleShot(
                0, lambda: self.edit_dig(d)))
            for text in EDIT_POINTS:
                b = sub.addAction(text)
                b.triggered.connect(lambda _=False, t=text: QTimer.singleShot(
                    0, lambda: self._dig_edit_from_menu(t)))
            return
        if not any(compat.kind_of(g) == "plot" for g in groups):
            return
        sub = menu.addMenu("ArchXQ")
        for text, fn, tip in (
                (PLOT_TABLE, self.edit_plot_table,
                 "The plot's sides, angles and heights, in a table"),
                ("Move points", lambda: self._edit_from_menu("Move points"),
                 "Move the plot's corners with the mouse"),
                ("Add point", lambda: self._edit_from_menu("Add point"),
                 "Add a corner on a side of the plot"),
                ("Delete point", lambda: self._edit_from_menu("Delete point"),
                 "Delete a corner of the plot"),
                (FOLD_LINE, lambda: self._edit_from_menu(FOLD_LINE),
                 "Make the sloped ground fold between two corners"),
                ("Setbacks…", self.edit_setbacks,
                 "How far from each edge you may build: every side")):
            a = sub.addAction(text)
            a.setStatusTip(tip)
            a.triggered.connect(lambda _=False, f=fn: QTimer.singleShot(0, f))

    def _dig_edit_from_menu(self, name: str) -> None:
        """An excavation tool from the right-click: Terrain › Edit
        excavation shows it."""
        if self.current != "terrain" or self.element != "excavation_edit":
            self.pick("terrain", "excavation_edit")
        self.on_method(name)

    def _edit_from_menu(self, name: str) -> None:
        """A plot tool from the right-click: Terrain › Edit plot shows it."""
        if self.current != "terrain" or self.element != "plot_edit":
            self.pick("terrain", "plot_edit")
        self.on_method(name)

    def start_edit_tool(self, name: str) -> None:
        """Edit plot › Move points / Add point / Delete point."""
        from .plotedit import PlotEditTool
        if not self.has_plot(self.doc()):
            compat.flash(self.viewport, "Draw the plot first")
            return

        def get_plot():
            doc = self.doc()
            return doc["plot"] if self.has_plot(doc) else None

        def change(corners, heights, closing, breaks) -> None:
            doc = self.doc()
            compat.commit_plot(self.viewport, self.app.key, doc, corners,
                               PLOT_Z, PLOT_COLOR, doc["plot"]["thickness"],
                               heights, closing, breaks)

        self.method = name
        tool = PlotEditTool(EDIT_POINTS[name], get_plot, change,
                            self._plot_cancelled, PLOT_Z)
        tool.plot_dims = lambda: self.dims_on("plot_dims")
        self._activate(tool)
        self.strip.fill(self.element, self.method)

    def start_fold_tool(self) -> None:
        from .plotedit import FoldLineTool
        if not self.has_plot(self.doc()):
            compat.flash(self.viewport, "Draw the plot first")
            return

        def get_plot():
            doc = self.doc()
            return doc["plot"] if self.has_plot(doc) else None

        def change(breaks) -> None:
            doc = self.doc()
            p = doc["plot"]
            compat.commit_plot(self.viewport, self.app.key, doc, p["corners"],
                               PLOT_Z, PLOT_COLOR, p["thickness"],
                               p["heights"], p["closing"], breaks)

        self.method = FOLD_LINE
        tool = FoldLineTool(get_plot, change, self._plot_cancelled, PLOT_Z)
        tool.plot_dims = lambda: self.dims_on("plot_dims")
        self._activate(tool)
        self.strip.fill(self.element, self.method)

    def _preview_plot(self, preview) -> None:
        """(corners, heights, closing, active row) drawn over the model
        while the table is open; None clears it."""
        self.plot_preview = preview
        self.viewport.update()

    def _plot_cancelled(self) -> None:
        self.method = None
        compat.back_to_select(self.viewport)
        self.refresh()

    # ---- Guide lines (the hub's Guides menu) -----------------------------------------
    def guide_action(self, key: str) -> None:
        """IngeTrazo's own construction guides, from inside ArchXQ
        (guidetools): a guide line, delete one, delete all."""
        from . import guidetools as GT
        self.hub.close_sub()
        if key == "tape":
            GT.tape(self.viewport)
        elif key == "erase":
            if not GT.guides(self.viewport):
                compat.flash(self.viewport, "No guide lines to delete", 3000)
                return
            self._activate(GT.GuideEraseTool(self._plot_cancelled))
        elif key == "all":
            n = GT.delete(self.viewport, GT.guides(self.viewport))
            compat.flash(self.viewport, f"{n} guide line{'s' if n != 1 else ''}"
                         " deleted — Ctrl+Z brings them back" if n else
                         "No guide lines to delete", 4000)

    def _enter(self, phase: str) -> None:
        self.current = phase
        self.element = PHASES[phase].elements[0]
        self.method = None
        self._row_for_phase(phase)

    #: the phases that work on a LEVEL (the Terrain phase works on the
    #: Terrain row; Project, Documentation and the Tools leave it as it is)
    _LEVEL_PHASES = ("structure", "walls", "openings", "roof")

    def _row_for_phase(self, phase: str, now: bool = False) -> None:
        """The row worked on follows the phase (his ask, 07/11/2026): the
        Terrain phase works on the Terrain — a plot drawn while on «Level 1»
        was hidden by that level's plan, and looked not drawn — and a
        level's phase goes back to the level (the one worked on before, the
        ground floor by default), so walls never vanish in the Terrain's
        plan either. Only when the phase changes: a row picked by hand
        within a phase stays."""
        if phase == "terrain":
            want = TERRAIN_ROW if not self.terrain_current else None
        elif phase in self._LEVEL_PHASES and self.terrain_current:
            levels = self.doc()["levels"]
            i = self.floor if 0 <= self.floor < len(levels) \
                else self._ground_index(self.doc())
            want = levels[i]["id"]
        else:
            want = None
        if want is None:
            return
        if now:
            self.set_floor(want)
        else:
            QTimer.singleShot(0, lambda: self._row_later(want))

    def _row_later(self, want: str) -> None:
        """The phase's row, once the element picked with it is known: the
        excavation tool, picked from the Terrain phase, works on its level
        (PLANO_ESCAVACAO_NIVEL.md) — the Terrain row does not take it back."""
        if want == TERRAIN_ROW and self.element == "excavation":
            return
        self.set_floor(want)

    # ---- Settings ------------------------------------------------------------------
    def build_demo(self) -> None:
        """A NEW document (the host asks first if this one is unsaved),
        the demonstration building built in it, saved as its own file."""
        from pathlib import Path

        from . import demo
        window = self.window
        before = getattr(window, "_current_path", None)
        if before is not None and Path(before) == demo.FILE:
            # the demo itself is open: it is rebuilt anyway — nothing of it
            # to keep, no question to answer (any other file: the host asks)
            window._saved_version = self.viewport.scene.version
        window._on_new()
        if getattr(window, "_current_path", None) is not None \
                and window._current_path == before:
            return                           # the user kept their document
        compat.back_to_select(self.viewport)
        demo.build(self)
        demo.FILE.parent.mkdir(parents=True, exist_ok=True)
        window._do_save(demo.FILE)
        self.set_floor(next(r["id"] for r in self.doc()["levels"]
                            if r["kind"] == "ground"), quiet=True)
        compat.standard_view(self.viewport, "iso")
        compat.set_perspective(self.viewport, True)
        compat.zoom_extents(self.viewport)
        compat.flash(self.viewport, f"Demo project built and saved: "
                     f"{demo.FILE.name}", 6000)

    def open_ai(self) -> None:
        """The AI's window (aiarch.py) — Pro: the Lite has no button for it."""
        mod = _pro_module("aiarch")
        if mod is not None:
            self.hub.close_sub()
            mod.open_window(self)

    def open_settings(self) -> None:
        from .dialogs import SettingsDialog
        self.hub.close_sub()
        dlg = SettingsDialog(self.window, self.placement)
        if dlg.exec():
            if self.plan_on:                 # the plan's style, at once
                from . import prefs
                compat.plan_style(self.viewport, False)
                if prefs.get("plan_hidden_line"):
                    compat.plan_style(self.viewport, True)
            self.refresh()
            self.viewport.update()

    # ---- Project -----------------------------------------------------------------
    def _project_or_ask(self) -> bool:
        """A new file with no Project: the Project dialog first, filled in
        already (one OK) — the levels, the ground's height and the
        basements decided before anything stands on them (his call,
        2026-11-01: «it is the essence of ArchXQ, and safer»). Cancelled:
        nothing is drawn, and it says why."""
        if model.has_project(self.doc()):
            return True
        compat.flash(self.viewport, "A new file: first its Project — the "
                     "levels and the ground's height (OK keeps the ones "
                     "shown)", 6000)
        self.edit_project(lead=False)
        if model.has_project(self.doc()):
            return True
        compat.flash(self.viewport, "No Project yet — nothing drawn. Start "
                     "one (Project), then draw", 7000)
        return False

    def new_project(self) -> None:
        """The Project menu's «New project» (his call, 07/11/2026): this
        document without a project — its «Start a new project» window; with
        one — a NEW tab (IngeTrazo 0.6: the project here stays as it is),
        and the window there."""
        self.hub.close_sub()
        if not model.has_project(self.doc()):
            self.edit_project("project")
            return
        window = self.window
        before = self.viewport.scene
        try:
            window._on_new()
        except Exception:  # noqa: BLE001 — the host's File ▸ New failed
            compat.flash(self.viewport, "Could not open a new document — use "
                         "File ▸ New", 5000)
            return
        if self.viewport.scene is before:
            return                     # no new document (kept this one)
        # once the new tab is the one in front (its state set up)
        QTimer.singleShot(150, lambda: self.edit_project("project"))

    def edit_project(self, tab: str = "project", lead: bool = True) -> None:
        """The Project dialog (modal): start a project, or edit it. A new
        one leads on to its next phase — not when a tool asked for it
        (``lead`` False: the tool comes out where it was picked)."""
        from .dialogs import ProjectDialog
        doc = self.doc()
        was_new = not model.has_project(doc)
        dlg = ProjectDialog(doc, self.window, tab)
        if not dlg.exec():
            return
        project, levels, system = dlg.result_data()
        doc = self.doc()               # fresh: nothing changed meanwhile lost
        marks = self._level_marks(doc)
        levels = model.fix_levels(levels)
        before = {r["id"]: r["name"] for r in doc["levels"]}
        renames = [(compat.level_layer(before[r["id"]]),
                    compat.level_layer(r["name"]))
                   for r in levels
                   if r["id"] in before and before[r["id"]] != r["name"]]
        if system != doc["system"]:
            # Structure/Walls swap: keep only what still precedes them
            doc["done"] = [k for k in doc["done"] if k in ("project",
                                                          "terrain")]
        doc.update(project=project, levels=levels, system=system)
        # a new project starts every phase afresh; an edit keeps them
        doc["done"] = (["project"] if was_new
                       else sorted(set(doc["done"]) | {"project"}))
        ground = self._ground_index(doc)
        old_id = None
        if 0 <= self.floor < len(self.doc()["levels"]):
            old_id = self.doc()["levels"][self.floor]["id"]
        ids = [r["id"] for r in levels]
        self.floor = ids.index(old_id) if old_id in ids else ground
        compat.save_doc_renaming(self.viewport, self.app.key, doc, renames)
        if was_new and lead:
            self._enter(next_open(self._done(doc), system))
            compat.flash(self.viewport, f"Project «{project['name']}» "
                         "started — next: draw the plot")
        elif was_new:
            compat.flash(self.viewport, f"Project «{project['name']}» started"
                         if project.get("name") else "Project started", 4000)
        elif self._level_marks(self.doc()) != marks:
            self._follow_levels()        # heights / ground level changed
        self.refresh()
        self._again(dlg, lambda: self.edit_project(tab))

    def _change_levels(self, fn) -> None:
        doc = self.doc()
        if not model.has_project(doc):
            self.edit_project("levels")
            return
        from . import prefs
        ids = {r["id"] for r in doc["levels"]}
        levels = fn([dict(r) for r in doc["levels"]],
                    prefs.get("floor_height"))
        new = next((r for r in levels if r["id"] not in ids), None)
        if new is None:
            return
        self._save_levels(doc, levels, current=new["id"])
        compat.flash(self.viewport, f"«{new['name']}» added")

    def on_add_floor(self) -> None:
        self._change_levels(model.add_floor)

    def _add_level_now(self, kind: str) -> list[dict]:
        """The level window's «＋ Level on top» / «＋ Basement» (its window
        stays open — his ask, 2026-11-03): made and stored now, one Ctrl+Z
        each, shown in the levels strip; → the levels as they are now."""
        doc = self.doc()
        ids = {r["id"] for r in doc["levels"]}
        levels = [dict(r) for r in doc["levels"]]
        levels = model.add_floor(levels) if kind == "top" else \
            model.add_basement(levels, levels[0]["height"])
        new = next((r["id"] for r in model.fix_levels(levels)
                    if r["id"] not in ids), None)
        self._save_levels(doc, levels, current=new)
        added = next((r for r in self.doc()["levels"] if r["id"] == new),
                     None)
        if added is not None:
            compat.flash(self.viewport, f"«{added['name']}» added", 3000)
        return [dict(r) for r in self.doc()["levels"]]

    def on_new_level(self) -> None:
        """The levels strip's «＋ New level» (his call, 2026-11-03): the
        window of the level you are on, its «New level» first — on top or
        a basement, never a level made blind."""
        doc = self.doc()
        if not doc["levels"]:
            return
        i = self.floor if 0 <= self.floor < len(doc["levels"]) \
            else self._ground_index(doc)
        self.edit_level(doc["levels"][i]["id"])

    # ---- Levels strip (right, N) ---------------------------------------------------
    def _level_layer(self, key: str, doc: dict) -> str:
        if key == TERRAIN_ROW:
            return compat.TERRAIN_LAYER
        lv = next(r for r in doc["levels"] if r["id"] == key)
        return compat.level_layer(lv["name"])

    def _fill_levels(self, doc: dict) -> None:
        """Top → bottom as a section reads, the Terrain at the ground —
        under the ground floor, over the basements (his eye, 2026-10-05:
        basements listed over the Terrain read as above the ground)."""
        levels = doc["levels"]
        names = [compat.level_layer(r["name"]) for r in levels]
        compat.ensure_layers(self.viewport, names + [compat.TERRAIN_LAYER])
        compat.prune_layers(self.viewport, set(names) | {compat.TERRAIN_LAYER})
        if self.has_plot(doc):       # a plot from before layers / the tag
            g = compat.find_plot(self.viewport, doc["plot"]["uid"])
            if getattr(g, "layer", None) in (None, "", "Layer 0"):
                g.layer = compat.TERRAIN_LAYER
            if compat.kind_of(g) is None:
                compat.tag(g, "plot")
        elev = model.elevations(levels, doc["project"]["ground_level"]
                                if model.has_project(doc) else 0.0)
        off = doc.get("hidden_parts") or {}
        rows = [{"key": r["id"], "name": r["name"], "kind": r["kind"],
                 "elev": elev[i],
                 "current": i == self.floor and not self.terrain_current,
                 "visible": compat.layer_visible(self.viewport, names[i]),
                 # parts switched off in its window: the eye says so
                 "parts_off": [label for key, label, _k in model.LEVEL_PARTS
                               if key in off.get(r["id"], ())],
                 "ghost": r["id"] in (doc.get("ghosts") or ()),
                 "sheet": r["id"] in (doc.get("sheets") or ())}
                for i, r in reversed(list(enumerate(levels)))]
        rows.insert(self._terrain_at(rows),
                    {"key": TERRAIN_ROW, "name": "Terrain",
                     "kind": "terrain", "elev": None,
                     "current": self.terrain_current,
                     "visible": compat.layer_visible(self.viewport,
                                                     compat.TERRAIN_LAYER),
                     "ghost": TERRAIN_ROW in (doc.get("ghosts") or ())})
        self.levels.fill(rows)

    @staticmethod
    def _terrain_at(rows: list[dict]) -> int:
        """Where the Terrain row goes in a top → bottom list of levels:
        right under the ground floor (the basements below it); at the end
        when there is no ground floor."""
        for k, r in enumerate(rows):
            if r.get("kind") == "ground":
                return k + 1
        return len(rows)
        self._show_piece(self.levels, self.levels_bar, self.levels_open)
        QTimer.singleShot(0, self.levels.fit)    # once the rows are styled

    def set_floor(self, key: str, quiet: bool = False,
                  by_hand: bool = False) -> None:
        """Work on this level from now on — or on the Terrain. ``by_hand``:
        the user's own click (the levels strip, the outliner) — only then
        does a basement picked while digging set the pit's bottom."""
        if key == TERRAIN_ROW:
            if self.terrain_current:
                return
            self.terrain_current = True
            name = "the Terrain"
        else:
            levels = self.doc()["levels"]
            i = next((i for i, r in enumerate(levels) if r["id"] == key),
                     None)
            if i is None or (i == self.floor and not self.terrain_current):
                return
            self.floor = i
            self.terrain_current = False
            name = f"«{levels[i]['name']}»"
            if by_hand and self.element == "excavation" \
                    and self.options_for is not None \
                    and self._dig_to_level(key):
                # the pit goes down under the basement picked — drawn on
                # it, where it shows (the level is sovereign)
                quiet = True
                compat.flash(self.viewport, tr(
                    "The excavation goes down under «{n}» — draw it",
                    n=levels[i]["name"]), 4000)
        self.levels.mark_current(key)
        self._outline_soon()
        if self.plan_on:
            self._apply_parts()          # the plan cut at the new level
        if self.options_for is not None:
            self._refill_options()           # «Level height» of this level
        # drawing walls / structure: carry on drawing on the new level
        el = self.tool_element()
        if el == "wall":
            QTimer.singleShot(0, self.start_wall_tool)
        elif el in ("column", "beam", "slab"):
            QTimer.singleShot(0, lambda: self.start_struct_tool(el))
        elif el in ("door", "window", "void"):
            QTimer.singleShot(0, lambda: self.start_opening_tool(el))
        if not quiet:
            compat.flash(self.viewport, f"Working on {name}", 2500)

    def _to_dig_row(self) -> None:
        """The excavation tool works on a level (PLANO_ESCAVACAO_NIVEL.md):
        on a basement or the ground floor it stays; on the Terrain or a
        floor above, it goes to the basement last worked on — else the
        lowest one; without basements, the ground floor. A basement's pit
        goes down under it (the bar's bottom)."""
        levels = self.doc().get("levels") or []
        if not levels:
            return
        here = levels[self.floor] if 0 <= self.floor < len(levels) else None
        if not self.terrain_current and here is not None \
                and here.get("kind") in ("basement", "ground"):
            self._dig_to_level(here["id"])
            return
        if here is not None and here.get("kind") == "basement":
            to = here
        else:
            to = next((r for r in levels if r.get("kind") == "basement"),
                      None) or next((r for r in levels
                                     if r.get("kind") == "ground"), levels[0])
        self.set_floor(to["id"], quiet=True)
        self._dig_to_level(to["id"])
        compat.flash(self.viewport, tr("Excavation on «{n}»", n=to["name"]),
                     3500)

    def _dig_to_level(self, key: str | None) -> bool:
        """A basement picked while digging is where the pit goes (his test,
        07/11/2026: «Basement 2» picked in the strip, the pit kept the bar's
        −3.00 and dug nothing new): the bar's bottom becomes «Under» it.
        True when it did."""
        levels = self.doc().get("levels") or []
        lv = next((r for r in levels if r["id"] == key), None)
        if lv is None or lv.get("kind") != "basement":
            return False
        self.dig_opts["bottom"] = f"level:{key}"
        self.dig_opts["bottom_picked"] = True
        return True

    def current_key(self) -> str | None:
        """The row lit in the strip / outliner: a level's id or «terrain»."""
        if self.terrain_current:
            return TERRAIN_ROW
        levels = self.doc()["levels"]
        return levels[self.floor]["id"] if 0 <= self.floor < len(levels) \
            else None

    def toggle_level(self, key: str) -> None:
        doc = self.doc()
        name = self._level_layer(key, doc)
        compat.set_layer_visible(self.viewport, name,
                                 not compat.layer_visible(self.viewport, name))
        self._fill_levels(doc)
        self._outline_soon()

    def _save_levels(self, doc: dict, levels: list[dict],
                     current: str | None = None) -> None:
        """THE way levels are stored: names fixed, every renamed level's
        layer follows it (default names renumber when a level is put in
        between), one Ctrl+Z. ``current`` = the level to work on after."""
        levels = model.fix_levels(levels)
        before = {r["id"]: r["name"] for r in doc["levels"]}
        renames = [(compat.level_layer(before[r["id"]]),
                    compat.level_layer(r["name"]))
                   for r in levels if r["id"] in before]
        keep = current or (doc["levels"][self.floor]["id"]
                           if 0 <= self.floor < len(doc["levels"]) else None)
        doc["levels"] = levels
        ids = [r["id"] for r in levels]
        self.floor = ids.index(keep) if keep in ids \
            else self._ground_index(doc)
        compat.save_doc_renaming(self.viewport, self.app.key, doc, renames)
        # a level's height moves every level above it
        self._follow_levels()
        self.refresh()

    @staticmethod
    def _level_marks(doc: dict) -> list:
        """What the building's heights hang on: each level's id, floor
        elevation and height."""
        if not model.has_project(doc) or not doc.get("levels"):
            return []
        z = model.elevations(doc["levels"], doc["project"]["ground_level"])
        return [(r["id"], e, r["height"]) for r, e in zip(doc["levels"], z)]

    def _follow_levels(self) -> None:
        """The levels moved: the excavations set under a level, then the
        walls and the structure, are made again at their new heights."""
        doc = self.doc()
        if any((d.get("bottom") or {}).get("mode") == "level"
               for d in doc.get("digs") or []):
            self._commit_terrain(doc)
            doc = self.doc()
        if doc.get("walls") or doc.get("structure"):
            self._commit_all(self._live(doc))

    def edit_current_level(self) -> None:
        doc = self.doc()
        if not model.has_project(doc):
            self.edit_project("levels")
            return
        self.edit_level(doc["levels"][self.floor]["id"])

    def edit_level(self, key: str) -> None:
        """The level's own window (modal): name, height; add a level above
        or below; delete it when nothing sits on it."""
        from .dialogs import LevelDialog
        doc = self.doc()
        ids = [r["id"] for r in doc["levels"]]
        if key not in ids:
            return
        i = ids.index(key)
        layer = compat.level_layer(doc["levels"][i]["name"])
        dlg = LevelDialog(doc, i, compat.layer_content(self.viewport, layer),
                          self.window,
                          on_show=lambda off: self.set_level_parts(key, off),
                          on_add=self._add_level_now)
        if not dlg.exec():
            return
        action, name, height = dlg.result_data()
        doc = self.doc()               # fresh: nothing changed meanwhile lost
        ids = [r["id"] for r in doc["levels"]]
        if key not in ids:
            return
        i = ids.index(key)             # (a basement added under it moved it)
        levels = [dict(r) for r in doc["levels"]]
        levels[i]["name"], levels[i]["height"] = name, height
        if action == "repeat":
            self.repeat_level(key, dlg.times(), name, height)
            return
        if action == "copy":
            self.copy_level(key, dlg.target())
            return
        if action in ("above", "below", "top", "basement"):
            # top / basement (2026-11-03): over the highest / under the
            # lowest, as high as it — whichever level's window it was
            if action == "top":
                levels = model.add_floor(levels)
            elif action == "basement":
                levels = model.add_basement(levels, levels[0]["height"])
            else:
                levels = model.insert_level(levels, i, action == "above")
            new = next(r["id"] for r in model.fix_levels(levels)
                       if r["id"] not in ids)
            self._save_levels(doc, levels, current=new)
            added = next(r for r in self.doc()["levels"] if r["id"] == new)
            compat.flash(self.viewport, f"«{added['name']}» added", 3000)
        elif action == "delete":
            gone = doc["levels"][i]["name"]
            if doc["levels"][i]["kind"] == "ground" or compat.layer_content(
                    self.viewport, compat.level_layer(gone)):
                compat.flash(self.viewport, f"«{gone}» has objects on it — "
                             "it cannot be deleted", 5000)
                return
            self._save_levels(doc, model.remove_level(levels, i))
            compat.flash(self.viewport, f"«{gone}» deleted — Ctrl+Z brings "
                         "it back", 4000)
        else:
            # its slabs typed in the window (support #93, 07/11/2026): the
            # level keeps it for the slabs to come, and its slabs take it —
            # in the same Ctrl+Z as the height
            for lid, t in dlg.slabs().items():
                doc = model.with_level_slab(doc, levels, lid, t)
            self._save_levels(doc, levels, current=key)
            self._again(dlg, lambda: self.edit_level(key))

    def repeat_level(self, key: str, n: int, name: str | None = None,
                     height: float | None = None) -> None:
        """``n`` copies of a level, one above the other, right over it
        (repeatlevel.py) — the levels above go up; one Ctrl+Z."""
        from . import repeatlevel
        doc = self._live(self.doc())
        lv = next((r for r in doc["levels"] if r["id"] == key), None)
        if lv is None:
            return
        if name is not None:              # what the window had changed
            doc = dict(doc, levels=[dict(r, name=name, height=height)
                                    if r["id"] == key else r
                                    for r in doc["levels"]])
        old_levels = doc["levels"]
        new, made, notes = repeatlevel.repeat(doc, key, n)
        if not made:
            return
        hist = self.viewport.history
        before = len(hist.undo_stack)
        self._save_levels(dict(new, levels=old_levels), new["levels"],
                          current=key)
        # the levels and the building rebuilt: ONE Ctrl+Z
        while len(hist.undo_stack) - before > 1:
            n0 = len(hist.undo_stack)
            compat.join_last_steps(hist, hist.undo_stack[-2])
            if len(hist.undo_stack) == n0:
                break
        compat.flash(self.viewport, f"«{lv['name']}» repeated {n}× above"
                     + (" · " + " · ".join(notes) if notes else "")
                     + " — Ctrl+Z undoes it", 6000)

    def copy_level(self, key: str, target: str | None) -> None:
        """What stands on a level copied onto another existing level
        (repeatlevel.copy_to) — added to what is there, after asking when
        that level has things on it; one Ctrl+Z."""
        from PySide6.QtWidgets import QMessageBox
        from . import repeatlevel
        if not target:
            return
        doc = self._live(self.doc())
        names = {r["id"]: r["name"] for r in doc["levels"]}
        if target not in names or key not in names:
            return
        has = compat.layer_content(self.viewport,
                                   compat.level_layer(names[target]))
        if has and QMessageBox.question(
                self.window, "Copy level",
                f"«{names[target]}» already has {has} object"
                f"{'s' if has > 1 else ''} on it. What is already there "
                f"stays as it is — only what «{names[key]}» has and it "
                "lacks is copied. Go on?",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel) != QMessageBox.Yes:
            return
        new, notes = repeatlevel.copy_to(doc, key, target)
        if new is doc:
            return
        self._commit_all(new)
        compat.flash(self.viewport, f"«{names[key]}» copied to "
                     f"«{names[target]}»"
                     + (" · " + " · ".join(notes) if notes else "")
                     + " — Ctrl+Z undoes it", 6000)

    # ---- Outliner (side tray, above the properties) ---------------------------------
    def _outline_soon(self, *_a) -> None:
        """The model changed (geometry, selection…): catch up once it has
        settled — a drag fires this many times."""
        if self.alive:
            self._outline_timer.start(80)

    @staticmethod
    def _category(g) -> tuple[str, str]:
        """(category, label) of an object. ArchXQ's own elements say what
        they are (their record on the group — the name can be anything);
        anything else on a level is an «Object»."""
        kind = compat.kind_of(g)
        if kind == "plot":
            return "Plot", "Plot"
        if kind == "dig":
            return "Excavations", g.name or "Excavation"
        if kind == "fill":
            return "Fills", g.name or "Fill"
        if kind == "wall":
            return "Walls", g.name or "Wall"
        if kind in ("column", "beam", "slab", "footing", "roof", "ramp",
                    "stair"):
            return kind.capitalize() + "s", g.name or kind.capitalize()
        if kind == "guard":
            return "Low walls", g.name or "Low wall"
        if kind == "glazing":
            return "Grids", g.name or "Grid"
        if kind == "opening":
            ok = compat._rec(g).get("okind", "door")
            return ("Windows" if ok == "window" else "Doors"), g.name or ok
        return "Objects", g.name or "Object"

    def outline(self, doc: dict) -> list[dict]:
        vp = self.viewport
        elev = model.elevations(doc["levels"], doc["project"]["ground_level"]
                                if model.has_project(doc) else 0.0)
        by_layer: dict = {}
        for g in vp.scene.groups:
            by_layer.setdefault(getattr(g, "layer", None), []).append(g)

        # the «Column rows» (colrows.py): their columns inside them
        from . import colrows
        row_of = {e["id"]: colrows.of_column(doc, e)
                  for e in doc.get("structure") or [] if e.get("row")}

        def in_rows(rows, parent):
            loose, by_row = [], {}
            for r in rows:
                grp = row_of.get(r.get("eid"))
                if grp is None:
                    loose.append(r)
                else:
                    by_row.setdefault(grp["id"], (grp, []))[1].append(r)
            out = []
            for rid, (grp, mine) in by_row.items():
                out.append({"key": f"crow:{parent}:{rid}",
                            "label": grp["name"], "kind": "category",
                            "count": len(mine),
                            "visible": any(r["visible"] for r in mine),
                            "tip": "Double-click: its window — what you "
                                   "change goes to every column of it",
                            "children": mine})
            return out + loose

        def items(groups, parent: str) -> list[dict]:
            cats: dict[str, list] = {}
            for g in groups:
                cat, label = self._category(g)
                cats.setdefault(cat, []).append({
                    "key": f"group:{g.uid}", "label": label, "kind": "item",
                    "visible": not g.hidden,
                    "eid": compat._rec(g).get("id"),
                    "tip": "Click: select · double-click: edit"})
            out = []
            for cat, rows in cats.items():
                if cat == "Plot":               # a single thing: no folder
                    out += rows
                    continue
                n = len(rows)
                if row_of:
                    rows = in_rows(rows, parent)
                out.append({"key": f"cat:{parent}:{cat}", "label": cat,
                            "kind": "category", "count": n,
                            "visible": any(r["visible"] for r in rows),
                            "children": rows})
            return out

        nodes = []
        for i in range(len(doc["levels"]) - 1, -1, -1):      # highest on top
            lv = doc["levels"][i]
            layer = compat.level_layer(lv["name"])
            kids = items(by_layer.get(layer, []), lv["id"])
            z = elev[i]
            nodes.append({
                "key": f"level:{lv['id']}", "kind": "level",
                "label": f"{lv['name']}   " + (
                    ("±0.00" if compat.doc_length_unit() == "m" else "±0")
                    if abs(z) < 0.005 else compat.fmt_level(z, unit=False)),
                "visible": compat.layer_visible(vp, layer),
                "current": i == self.floor and not self.terrain_current,
                "children": kids, "lvkind": lv["kind"],
                "tip": "Click: work on this level · double-click: edit it"})
        tlayer = compat.TERRAIN_LAYER
        tkids = items(by_layer.get(tlayer, []), "terrain")
        if self.has_plot(doc):
            from . import plotgeo
            p = doc["plot"]
            roles, _d, area = plotgeo.setbacks_of(p)
            if any(roles):
                tkids.append({
                    "key": "setbacks", "kind": "category",
                    "label": "Setbacks" + (
                        f"  ·  {compat.fmt_area(plotgeo.area(area), 0, True)}"
                        " buildable" if area else ""),
                    "visible": doc["view"].get("setbacks", False),
                    "tip": "The buildable area · double-click: edit"})
            if p["breaks"]:
                tkids.append({
                    "key": "folds", "kind": "category",
                    "label": "Fold lines", "count": len(p["breaks"]),
                    "visible": doc["view"].get("folds", True),
                    "tip": "Where the sloped ground folds · double-click: "
                           "draw / remove"})
        # at the ground, as in the levels strip: under the ground floor,
        # over the basements
        at = next((k + 1 for k, n in enumerate(nodes)
                   if n.get("lvkind") == "ground"), len(nodes))
        nodes.insert(at, {"key": "terrain", "label": "Terrain",
                          "kind": "terrain",
                          "visible": compat.layer_visible(vp, tlayer),
                          "current": self.terrain_current,
                          "tip": "Click: work on the Terrain",
                          "children": tkids})
        mine = {compat.level_layer(r["name"]) for r in doc["levels"]} | {tlayer}
        others = [g for g in vp.scene.groups
                  if getattr(g, "layer", None) not in mine]
        kids = [{"key": f"group:{g.uid}", "label": g.name or "Object",
                 "kind": "item", "visible": not g.hidden,
                 "tip": "Click: select"} for g in others]
        loose = compat.loose_count(vp)
        if loose:
            kids.append({"key": "loose", "label": f"Loose geometry "
                         f"({loose} faces and edges)", "kind": "category",
                         "visible": True, "eye": False})
        nodes.append({"key": "other", "label": "Other objects",
                      "kind": "other", "count": len(others),
                      "visible": not others or any(not g.hidden
                                                   for g in others),
                      "children": kids,
                      "tip": "What is not ArchXQ's: drawn with the host's "
                             "tools, figures…"})
        return nodes

    def _sync_outliner(self, force: bool = False) -> None:
        if not self.alive:
            return
        doc = self.doc()
        vp = self.viewport
        sig = (tuple((g.uid, g.name, getattr(g, "layer", None), g.hidden)
                     for g in vp.scene.groups),
               tuple((r["id"], r["name"], r["height"]) for r in doc["levels"]),
               tuple((L.name, L.visible) for L in vp.scene.layers),
               compat.loose_count(vp), self.floor, self.terrain_current,
               repr(doc["view"]),
               repr({k: v for k, v in (doc.get("plot") or {}).items()
                     if k.startswith("sb_") or k in ("breaks", "corners")}))
        selected = compat.selected_groups(vp)
        # nothing of a level hidden by its eye stays selected, however it
        # got there (his test, 29/10: a Level 3 wall selected with Level 3
        # hidden — a Delete would take what he cannot see)
        seen = [g for g in selected
                if not getattr(g, "layer", None)
                or compat.layer_visible(vp, g.layer)]
        if len(seen) != len(selected):
            compat.select(vp, seen, "replace")
            selected = seen
            compat.flash(vp, "Not selected: its level is hidden — open the "
                             "level's eye to pick it", 3500)
        # what is picked in the model decides the level worked on (the
        # plot → the Terrain, a Level 2 object → Level 2) — only at the
        # moment the pick CHANGES: a level clicked afterwards wins, even
        # with the object still selected
        picked = frozenset(g.uid for g in selected)
        if picked != self._last_pick:
            self._last_pick = picked
            QTimer.singleShot(0, self._library_show)  # its type, marked
            # its phase and element too (his ask, 2026-10-02): a wall →
            # Walls › Wall, a window → Openings › Window…
            target = self._element_for(selected)
            if target and target != (self.current, self.element) \
                    and self.tool_element() is None:
                QTimer.singleShot(0, lambda t=target: self.pick(*t))
            where = self._level_of(selected, doc)
            if where is not None and where != self.current_key():
                self.set_floor(where, quiet=True)
                return                     # set_floor schedules the rebuild
        if force or sig != self._outline_sig:
            self._outline_sig = sig
            self.outliner.build(self.outline(doc))
        self.outliner.show_selected({f"group:{g.uid}" for g in selected})

    KIND_ELEMENT = {"wall": ("walls", "wall"), "roof": ("roof", "roof"),
                    "column": ("structure", "column"),
                    "beam": ("structure", "beam"),
                    "slab": ("structure", "slab"),
                    "footing": ("structure", "footing"),
                    "plot": ("terrain", "plot"),
                    "dig": ("terrain", "excavation"),
                    "fill": ("terrain", "fill")}

    def _element_for(self, groups):
        """(phase, element) of the picked ArchXQ objects — when they are
        all of one kind; None otherwise."""
        found = set()
        for g in groups:
            k = compat.kind_of(g)
            if k == "opening":
                ok = compat._rec(g).get("okind", "door")
                found.add(("openings", ok if ok in ("door", "window", "void")
                           else "door"))
            elif k in self.KIND_ELEMENT:
                found.add(self.KIND_ELEMENT[k])
            else:
                return None
        return next(iter(found)) if len(found) == 1 else None

    def _level_of(self, groups, doc: dict) -> str | None:
        """The one level (or «terrain») all these objects sit on, or None
        (nothing picked, not ArchXQ's, or several levels)."""
        by_layer = {compat.TERRAIN_LAYER: TERRAIN_ROW}
        by_layer.update({compat.level_layer(r["name"]): r["id"]
                         for r in doc["levels"]})
        where = {by_layer.get(getattr(g, "layer", None)) for g in groups}
        return next(iter(where)) if len(where) == 1 and None not in where \
            else None

    def _groups_under(self, key: str) -> list:
        """The objects a row stands for (a category, «Other objects»…)."""
        vp = self.viewport
        doc = self.doc()
        if key.startswith("group:"):
            g = compat.find_group(vp, key.split(":", 1)[1])
            return [g] if g is not None else []
        if key == "other":
            mine = {compat.level_layer(r["name"]) for r in doc["levels"]} \
                | {compat.TERRAIN_LAYER}
            return [g for g in vp.scene.groups
                    if getattr(g, "layer", None) not in mine]
        if key.startswith("crow:"):              # a «Column row»
            from . import colrows
            _c, _lv, rid = key.split(":", 2)
            row = colrows.find(doc, rid)
            ids = {e["id"] for e in colrows.members(doc, row)} if row else set()
            return [g for g in vp.scene.groups
                    if compat._rec(g).get("id") in ids]
        if key.startswith("cat:"):
            _c, parent, cat = key.split(":", 2)
            layer = (compat.TERRAIN_LAYER if parent == "terrain" else
                     compat.level_layer(next(r["name"] for r in doc["levels"]
                                             if r["id"] == parent)))
            return [g for g in vp.scene.groups
                    if getattr(g, "layer", None) == layer
                    and self._category(g)[0] == cat]
        return []

    def outliner_toggle(self, key: str) -> None:
        """The eye of any row: a level / the Terrain = its layer (the same
        as the levels strip); anything else = its objects."""
        if key.startswith("level:") or key == "terrain":
            self.toggle_level(TERRAIN_ROW if key == "terrain"
                              else key.split(":", 1)[1])
        elif key in ("setbacks", "folds"):
            self.toggle_view(key)
            return
        else:
            groups = self._groups_under(key)
            if groups:
                hide = any(not g.hidden for g in groups)
                # ArchXQ's own elements by their id (rebuilt groups keep
                # it); anything else as it is
                ids = {compat._rec(g).get("id") for g in groups
                       if compat.kind_of(g)} - {None}
                if ids:
                    cur = self._hidden_ids()
                    compat.set_hidden_ids(self.viewport, self.app.key,
                                          (cur | ids) if hide else cur - ids)
                compat.set_hidden(self.viewport, groups, hide)
                if ids:
                    self._apply_parts()
        self._sync_outliner(force=True)

    def outliner_select(self, keys) -> None:
        groups = []
        for k in keys:
            groups += self._groups_under(k) if k.startswith("group:") else []
        # picked HERE: the outliner stays under the click (the library takes
        # the whole strip only for what is picked in the model)
        self._sel_by_outliner = {compat._rec(g).get("id") for g in groups}
        compat.select(self.viewport, groups)

    def outliner_open(self, key: str) -> None:
        """Double-click: the thing's own window, when it has one."""
        if key.startswith("level:"):
            self.edit_level(key.split(":", 1)[1])
            return
        if key == "setbacks":
            QTimer.singleShot(0, self.edit_setbacks)
            return
        if key == "folds":
            self._edit_from_menu(FOLD_LINE)
            return
        doc = self.doc()
        if key.startswith("crow:"):              # a «Column row»: its window
            from . import colrows
            row = colrows.find(doc, key.split(":", 2)[2])
            mine = colrows.members(self._live(doc), row) if row else []
            if mine:
                QTimer.singleShot(0, lambda i=mine[0]["id"]:
                                  self.edit_element(i))
            return
        if key.startswith("group:") and self.has_plot(doc) \
                and key == f"group:{doc['plot']['uid']}":
            self.edit_plot_table()
            return
        if key.startswith("group:"):
            g = compat.find_group(self.viewport, key.split(":", 1)[1])
            wall = self.wall_of(g) if g is not None else None
            if wall is not None:
                QTimer.singleShot(0, lambda: self.edit_wall(wall))
                return
            el = self.element_of(g) if g is not None else None
            if el is not None:
                QTimer.singleShot(0, lambda: self.edit_element(el))
                return
            op = self.opening_of(g) if g is not None else None
            if op is not None:
                QTimer.singleShot(0, lambda: self.edit_opening(op))
                return
            dig = self.dig_of(g) if g is not None else None
            if dig is not None:
                QTimer.singleShot(0, lambda: self.edit_dig(dig))

    def _menu_check(self, text: str, on: bool) -> None:
        a = getattr(self, "menu_acts", {}).get(text)
        if a is not None:
            a.blockSignals(True)
            a.setChecked(bool(on))
            a.blockSignals(False)

    def toggle_ghost(self, key: str) -> None:
        """A level row's ghost icon: that level drawn in light blue in the
        plan of the one worked on — to line this one up with it. Any
        number of them; a view change (no undo), kept in the file."""
        doc = self.doc()
        cur = set(doc.get("ghosts") or [])
        on = key not in cur
        cur = (cur | {key}) if on else (cur - {key})
        compat.set_ghosts(self.viewport, self.app.key, cur)
        self._fill_levels(self.doc())
        if on and not self.plan_on:
            compat.flash(self.viewport, "Ghost on — it shows in the plan "
                         "view", 4000)
        self.viewport.update()

    def toggle_sheet(self, key: str) -> None:
        """A level row's grid icon: that level's GUIDE SHEET in 3D
        (levelsheet.py) — a view change (no undo), kept in the file. The
        icon rules: off, it never shows."""
        doc = self.doc()
        cur = set(doc.get("sheets") or [])
        on = key not in cur
        cur = (cur | {key}) if on else (cur - {key})
        compat.set_sheets(self.viewport, self.app.key, cur)
        # the sheet is the WORKED level's: switched on on another one, you
        # work on that one now — on, it shows at once (his test, 31/10:
        # switched on on another level, «it doesn't appear»)
        if on and self._lv_id_worked() != key:
            self.set_floor(key, quiet=True)
        self._fill_levels(self.doc())
        if on and self.plan_on:
            compat.flash(self.viewport, "Guide sheet on — it shows in the 3D "
                         "view", 4000)
        elif on:
            name = next((lv["name"] for lv in self.doc()["levels"]
                         if lv["id"] == key), "")
            compat.flash(self.viewport, tr("Guide sheet on — you work on "
                                           "«{name}»", name=name), 4000)
        self.viewport.update()

    def _lv_id_worked(self):
        """The id of the level worked on (None: the Terrain)."""
        levels = self.doc()["levels"]
        if self.terrain_current or not 0 <= self.floor < len(levels):
            return None
        return levels[self.floor]["id"]

    def _draw_level_sheets(self, viewport, painter) -> None:
        """In 3D: the guide sheet of the LEVEL WORKED ON, when its icon is
        on (his call, 31/10: one sheet, the working one) — at its floor,
        BEHIND what stands on it; stronger, with the cursor's cross, while
        a tool draws on it."""
        if self.plan_on or self.side_view is not None \
                or self.terrain_current:
            return
        try:
            doc = self._paint_doc or self.doc()
            levels = doc["levels"]
            if not 0 <= self.floor < len(levels):
                return
            lv = levels[self.floor]
            if lv["id"] not in (doc.get("sheets") or ()) \
                    or not compat.layer_visible(
                        viewport, compat.level_layer(lv["name"])):
                return
            from . import levelsheet as LS
            z = model.elevations(levels, doc["project"]["ground_level"]
                                 if model.has_project(doc)
                                 else 0.0)[self.floor]
            tool = getattr(viewport, "active_tool", None)
            active = compat.ours(tool) and getattr(tool, "creates", False) \
                and getattr(tool, "level_id", None) == lv["id"]
            hover = getattr(tool, "hover", None) if active else None
            if not (isinstance(hover, (list, tuple)) and len(hover) >= 2):
                hover = None
            ext = LS.extent(doc, lv["id"])
            if active:                       # out to what is being drawn
                ext = LS.grow(ext, list(getattr(tool, "pts", None)
                                        or []) + [hover])
            LS.draw_behind(viewport, painter, ext, z, strong=bool(active),
                           cursor=hover)
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    def toggle_levels_strip(self) -> None:
        if not self.active:
            self._menu_check("Levels strip\tN", self.levels_open)
            return                  # nothing of ArchXQ shows while it is off
        if self._framed:            # several views: for now, not remembered
            self._framed_levels = not self._framed_levels
            self._show_piece(self.levels, self.levels_bar, self._framed_levels)
            self.layout_floating()
            return
        self.levels_open = not self.levels_open
        QSettings().setValue("archxq/levels_open",
                             "1" if self.levels_open else "0")
        self._menu_check("Levels strip\tN", self.levels_open)
        self._show_piece(self.levels, self.levels_bar, self.levels_open)
        # just hidden: the tab says for a moment how to bring it back
        self.levels_tab.set_hint(not self.levels_open)
        self.layout_floating()

    # ---- View bar ----------------------------------------------------------------
    #: the view bar's «Show» chips → the kinds of groups they show / hide
    SHOW_KINDS = {"terrain": ("plot", "dig", "fill", "street"),
                  "structure": ("column", "beam", "slab", "footing", "ramp",
                                "stair", "guard", "copy"),
                  # (a profile along a wall shows and hides with it)
                  "walls": ("wall", "profile"),
                  "openings": ("opening", "glazing"),
                  "roof": ("roof",),
                  # the slabs on their own too (his ask, 2026-10-16) — and
                  # THIS chip decides them: «Structure» off with «Slabs» on
                  # showed none (his report, 2026-10-22: «at least the slab
                  # should be there»)
                  "slabs": ("slab",)}

    def on_view_option(self, what: str, value) -> None:
        """«Show: Terrain · Structure · Walls…» — a part of the building
        shown / hidden at once (a VIEW change: not in the undo). It holds
        through every rebuild."""
        part = what.split(":", 1)[1] if what.startswith("show:") else what
        if part not in self.SHOW_KINDS:
            compat.flash(self.viewport, f"Nothing to show yet in "
                         f"«{part.capitalize()}» (its phase comes later)",
                         3000)
            return
        if value:
            self.hidden_parts.discard(part)
        else:
            self.hidden_parts.add(part)
        if part == "terrain":
            self._side_hid_terrain = False   # his own choice from now on
        self._apply_parts()

    def _apply_parts(self) -> None:
        """Hide / show the groups of the parts switched off — and the
        structure INSIDE the walls while the walls are shown (its lines
        showed through them; it shows when the walls are hidden)."""
        walls_on = "walls" not in self.hidden_parts
        mine_off = self._hidden_ids()     # hidden one by one (by its id)
        lv_off = self._hidden_level_kinds()   # a level's window «Show»
        here = self._plan_here()
        # an excavation shows in the plan of the levels it belongs to (the
        # level is sovereign — PLANO_ESCAVACAO_NIVEL.md)
        self._dig_rows = {}
        if here is not None and here != TERRAIN_ROW:
            try:
                from . import terrain
                doc = self.doc()
                self._dig_rows = {d["id"]: terrain.dig_levels(d, doc)
                                  for d in doc.get("digs") or []}
            except Exception:  # noqa: BLE001 — hidden, as before
                self._dig_rows = {}
        hide, show, cut = [], [], []
        for g in self.viewport.scene.groups:
            k = compat.kind_of(g)
            parts = [p for p, kinds in self.SHOW_KINDS.items() if k in kinds]
            if "slabs" in parts:
                parts = ["slabs"]            # its own chip decides a slab
            if parts:
                # (a BOOL: «.get» gave None, None != False was always
                # true — every refresh re-showed 44 groups, the view
                # changed, the host said «document changed», ArchXQ
                # refreshed again: 20 times a second, the bars rebuilt
                # before their buttons could show — 2026-10-03)
                other = bool(any(p in self.hidden_parts for p in parts) or (
                    "structure" in parts and walls_on
                    and compat._rec(g).get("inwall"))
                    # its window's «Hide» / the outliner's eye: it holds
                    # through every rebuild
                    or compat._rec(g).get("id") in mine_off
                    # a part of its level switched off in the level's window
                    or k in lv_off.get(compat._rec(g).get("level"), ()))
                # the plan shows the level worked on ONLY — nothing above,
                # nothing below, whatever hole or stair (his rule,
                # 2026-10-26: the level is sovereign; another one shows as
                # a ghost when its icon is on). The Terrain is a level too.
                want = other or self._not_this_level(g, k, here)
                if want and not other:
                    cut.append(g)
                if bool(g.hidden) != want:
                    (hide if want else show).append(g)
            elif k is None:
                # not ArchXQ's (people, a sidewalk modelled by hand…): of no
                # level, so the Terrain's — on a level's plan it does not
                # show (his rule, 2026-10-26: «não está no nível, não
                # aparece»). Marked on the group when the plan hid it, so
                # one he hid himself is never shown back.
                act = self._foreign_cut(g, here)
                if act in ("hide", "cut"):
                    cut.append(g)
                if act == "hide":
                    hide.append(g)
                elif act == "show":
                    show.append(g)
        if hide:
            compat.set_hidden(self.viewport, hide, True)
        if show:
            compat.set_hidden(self.viewport, show, False)
        # (hidden only by the plan's cut: the sheets still draw them — a
        # section remade in the plan came out with Levels 2–5 missing, his
        # screen 24/10)
        _docs = _pro_module("docs")
        if _docs is not None:
            _docs.PLAN_CUT[:] = cut
        self._host_marks_sync()

    def _host_marks_sync(self) -> None:
        """The purple lines ARE the section lines (his call, 24/10: «não faz
        sentido ter duas linhas de corte»): while ArchXQ is on — every phase,
        plan and 3D, presenting too — the host's planes (the ones our sheets
        need for their pictures, grey lettered dashes, orange when active)
        go out of sight by its own «Section Planes» switch; put back when
        ArchXQ goes off, only if we turned it off (and in the same file).
        A host cut left ACTIVE goes off too (half the building hidden, its
        mark out of sight: no way to see why — his screen, 24/10) and comes
        back with them."""
        try:
            # the 3D cut lives in the Documentation's 3D only (taken off
            # first: the marks' state below must not be the cut's)
            if getattr(self, "_cut3d", None) is not None and not (
                    self.alive and self.active and not self.plan_on
                    and self.current == "documentation"):
                self._cut3d_off(quiet=True)
            sc = self.viewport.scene
            off = bool(self.alive and (self.active or self.presenting)
                       and not edition.lite())
            was = getattr(self, "_marks_off", None)
            if off:
                # (turned back on by hand in here: his — left alone)
                if was is None or was[0] is not sc:
                    act = sc.active_section() if callable(getattr(
                        sc, "active_section", None)) else None
                    shown = bool(getattr(sc, "show_section_planes", False))
                    if not (shown or act is not None):
                        return
                    self._marks_off = (sc, shown, act)
                    if act is not None:
                        sc.set_active_section(None)
                    if shown:
                        compat.show_section_planes(self.viewport, False)
                    self.viewport.update()
            elif was is not None:
                self._marks_off = None
                sc0, shown, act = was
                if sc0 is sc:
                    if act is not None and act in sc.section_planes \
                            and sc.active_section() is None:
                        sc.set_active_section(act)
                    if shown:
                        compat.show_section_planes(self.viewport, True)
                    self.viewport.update()
        except Exception:  # noqa: BLE001 — a view nicety, never in the way
            compat.log_error("host section marks")

    def _hidden_ids(self) -> set:
        try:
            return set(self.doc().get("hidden_ids") or [])
        except Exception:  # noqa: BLE001 — nothing hidden
            return set()

    def _hidden_parts(self) -> dict:
        """{level id: {part keys}} switched off in the levels' windows."""
        try:
            return {lv: set(p) for lv, p in
                    (self.doc().get("hidden_parts") or {}).items()}
        except Exception:  # noqa: BLE001 — nothing hidden
            return {}

    def _hidden_level_kinds(self) -> dict:
        """{level id: {element kinds}} — the parts above, as kinds."""
        out = {}
        for lv, parts in self._hidden_parts().items():
            out[lv] = {k for key, _l, kinds in model.LEVEL_PARTS
                       if key in parts for k in kinds}
        return out

    def set_level_parts(self, level_id: str, off) -> None:
        """A level's window «Show»: its parts in ``off`` hidden, the rest
        shown — a view change (no undo), kept in the file. Right away,
        with the window still open."""
        cur = self._hidden_parts()
        cur[level_id] = set(off)
        compat.set_hidden_parts(self.viewport, self.app.key, cur)
        self._apply_parts()
        self._sync_guides()
        self._fill_levels(self.doc())      # the row's eye tells it
        self._sync_outliner(force=True)

    def _guide_level(self, doc: dict, z: float) -> str | None:
        """The level a guide line belongs to: the highest one whose floor
        is at most 0.5 m over the guide's height (a guide drawn on a pit's
        floor, a few cm under its level, is that level's)."""
        levels = doc["levels"]
        if not levels:
            return None
        zs = model.elevations(levels, doc["project"]["ground_level"]
                              if model.has_project(doc) else 0.0)
        best = None
        for lv, z0 in zip(levels, zs):
            if z0 <= z + 0.5 and (best is None or z0 > best[1]):
                best = (lv["id"], z0)
        return best[0] if best else levels[0]["id"]

    def _guides_to_level(self, cmd) -> None:
        """A guide line just drawn (the Tape) goes to the FLOOR of the level
        worked on — its place in plan kept (his catch, 2026-10-12: the
        shops' guides, taken off the pit's edges, lay on the excavation's
        floor, not on the ground floor's). A level's «Guide lines» then
        tells its own. Upright guides, and the Terrain, are left as drawn."""
        from PySide6.QtGui import QVector3D
        try:
            from core.history import AddGuideCommand
        except ImportError:
            return
        # only the guide THIS command made (the file's own never move)
        new = [cmd.guide] if isinstance(cmd, AddGuideCommand) \
            and getattr(cmd, "guide", None) is not None else []
        if not new or self.terrain_current or not self.active:
            return
        doc = self.doc()
        levels = doc["levels"]
        if not 0 <= self.floor < len(levels):
            return
        z0 = model.elevations(levels, doc["project"]["ground_level"]
                              if model.has_project(doc) else 0.0)[self.floor]
        for g in new:
            p, d = getattr(g, "point", None), getattr(g, "direction", None)
            if p is None or d is None or abs(d.z()) > 1e-6 \
                    or abs(p.z() - z0) < 1e-6:
                continue
            g.point = QVector3D(p.x(), p.y(), z0)
        self.viewport.update()

    def _sync_guides(self) -> None:
        """«Guide lines» off on a level: the host's guides drawn at its
        height leave the scene (kept in ``guides_off``); on again — or the
        level gone —, they come back as they were. View state: no undo."""
        from core.guide import Guide
        sc = self.viewport.scene
        doc = self.doc()
        off = {lv for lv, p in self._hidden_parts().items() if "guides" in p}
        ids = {r["id"] for r in doc["levels"]}
        store = {lv: list(gs) for lv, gs in
                 (doc.get("guides_off") or {}).items()}
        changed = False
        for lv in list(store):
            if lv not in off or lv not in ids:   # shown again: back in
                for d in store.pop(lv):
                    try:
                        sc.guides.append(Guide.from_dict(d))
                    except Exception:  # noqa: BLE001 — a bad one is dropped
                        pass
                changed = True
        if off:
            keep = []
            for g in list(sc.guides):
                p = getattr(g, "point", None)
                lv = self._guide_level(doc, p.z()) if p is not None else None
                if lv in off:
                    store.setdefault(lv, []).append(g.to_dict())
                    changed = True
                else:
                    keep.append(g)
            if len(keep) != len(sc.guides):
                sc.guides[:] = keep
        if changed:
            compat.set_guides_off(self.viewport, self.app.key, store)

    def set_elements_hidden(self, ids, hidden: bool) -> None:
        """Hide / show ArchXQ elements by id — a view change (no undo),
        kept through rebuilds and in the file."""
        cur = self._hidden_ids()
        cur = (cur | set(ids)) if hidden else (cur - set(ids))
        compat.set_hidden_ids(self.viewport, self.app.key, cur)
        self._apply_parts()
        self._sync_outliner(force=True)

    def hide_element(self, el_id: str, name: str = "") -> None:
        """A window's «Hide»: it goes out of sight — its eye in the
        outliner brings it back."""
        self.set_elements_hidden({el_id}, True)
        compat.flash(self.viewport, f"«{name or 'It'}» hidden — its eye in "
                     "the outliner shows it again", 6000)

    #: what the Terrain «level» holds in the plan (the streets too: on the
    #: ground level in the file, outside the building in the plan)
    TERRAIN_KINDS = ("plot", "dig", "fill", "street")

    def _plan_here(self) -> str | None:
        """The row the plan shows: a level's id, TERRAIN_ROW — or None (not
        in the plan: nothing hidden for it)."""
        if not self.plan_on:
            return None
        if self.terrain_current:
            return TERRAIN_ROW
        try:
            return self.doc()["levels"][self.floor]["id"]
        except Exception:  # noqa: BLE001 — nothing hidden
            return None

    @staticmethod
    def _foreign_cut(g, here) -> str | None:
        """A group not ArchXQ's in the plan of the row ``here``: "hide" (the
        plan hides it now, tagged), "cut" (hidden by the plan already),
        "show" (the plan had hidden it: back), None (left alone — one he
        hid himself stays hidden)."""
        want = here is not None and here != TERRAIN_ROW
        ext = getattr(g, "ext", None) or {}
        if want and not g.hidden:
            g.ext = {**ext, PLAN_CUT_TAG: True}
            return "hide"
        if want and ext.get(PLAN_CUT_TAG):
            return "cut"
        if not want and ext.get(PLAN_CUT_TAG):
            g.ext = {a: b for a, b in ext.items() if a != PLAN_CUT_TAG}
            return "show" if g.hidden else None
        return None

    def _not_this_level(self, g, kind, here) -> bool:
        """In the plan: the group is not of the row ``here`` — another
        level's, or the terrain's while on a level (and the other way)."""
        if here is None:
            return False
        if here == TERRAIN_ROW:
            return kind not in self.TERRAIN_KINDS
        if kind == "street":
            # the ground level's plan too: its tool draws there, round the
            # building — hidden, only its selection showed (a «ghost», his
            # test 2026-10-28)
            return compat._rec(g).get("level") != here
        if kind == "dig":
            rows = getattr(self, "_dig_rows", {}).get(compat._rec(g).get("id"))
            return not rows or here not in rows
        if kind in self.TERRAIN_KINDS:
            return True
        lid = compat._rec(g).get("level")
        return lid is not None and lid != here

    def on_view_kind(self, kind: str) -> None:
        # the view bar's 3D / Plan are the plan view switch (one truth)
        if kind == "plan":
            self.enter_plan()
        elif kind == "3d":
            if self.plan_on:
                self.leave_plan()
            else:
                compat.standard_view(self.viewport, "iso")
                compat.set_perspective(self.viewport, True)
        else:
            compat.flash(self.viewport, f"ArchXQ prototype: {kind} view is "
                         "not wired yet")
        self._sync_plan()

    # ---- Plan view (edit) / 3D view (look) ----------------------------------------
    def toggle_plan(self) -> None:
        if self.side_view is not None:     # an elevation: back to the 3D view
            self.leave_side()
            return
        if self.plan_on:
            self.leave_plan()
            # out of the plan = done drawing (his call, 2026-10-02): the
            # ArchXQ tool goes, the pencil leaves the pointer — but not one
            # that works in 3D as well (doors, windows, grids, columns,
            # beams, a profile: PLANO_ABERTURAS_3D.md D2 / D12)
            tool = getattr(self.viewport, "active_tool", None)
            if compat.ours(tool) and getattr(tool, "draws_in_3d", False):
                # a wall tool goes on drawing in 3D, on the level's floor
                # (PLANO_PAREDE_3D.md, his ask 31/10 — the videos)
                self._say_floor_3d(tool)
            elif compat.ours(tool) \
                    and not getattr(tool, "stays_in_view", False):
                self.method = None
                compat.back_to_select(self.viewport)
                self.refresh()
        else:
            self.enter_plan()

    def _say_floor_3d(self, tool) -> None:
        """Where a tool drawing in 3D puts its points: the ACTIVE level's
        floor — said once as the plan is left."""
        from .i18n import tr
        lv = next((r for r in self.doc()["levels"]
                   if r["id"] == getattr(tool, "level_id", None)), None)
        if lv is None:
            return
        compat.flash(self.viewport, tr(
            "Drawing on «{name}»'s floor in 3D — the plan view is more "
            "precise", name=lv["name"]), 5000)

    def enter_plan(self, quiet: bool = False) -> None:
        """From the top, parallel: where you draw and edit. The 3D view
        it came from is kept, to go back to."""
        if self.plan_on:
            return
        cam = compat.camera_state(self.viewport)
        if self.side_view is not None:
            # from an elevation: the 3D view to go back to is still the one
            # before it
            self._end_side()
        else:
            # coming from a top view already: no 3D view to go back to
            self._plan_back = None if compat.is_top(cam) else cam
        if self._plan_cam is not None:
            # the plan keeps its own zoom and place, as the 3D view does
            compat.set_camera_state(self.viewport, self._plan_cam)
        else:
            compat.plan_camera(self.viewport)
            # the first time: the plot (the base of everything), else all
            doc = self.doc()
            if self.has_plot(doc):
                compat.fit_plan(self.viewport, doc["plot"]["corners"])
            elif any(compat.kind_of(g) for g in self.viewport.scene.groups):
                compat.zoom_extents(self.viewport)
            else:
                # nothing yet: the origin in the middle, 40 × 30 m round
                # it — so the plot is drawn where the 3D view looks (his
                # screen, 2026-10-02: a plot drawn far off, out of sight)
                compat.fit_plan(self.viewport, [(-20.0, -15.0),
                                                (20.0, 15.0)])
        self.plan_on = True
        # LOCKED to the top until «Plan view» is clicked again (his call,
        # 2026-10-02): an orbit by accident spoiled the drawing; pan and
        # zoom stay free — not while an editing tool is out (2026-10-03)
        self._sync_lock()
        self._apply_view_style()         # hidden line / X-ray: a view only
        self._apply_parts()              # the levels above: not in the plan
        self._sync_plan()
        if not quiet:
            compat.flash(self.viewport, "Plan view — locked to the top: pan "
                         "and zoom freely; «Plan view» again = the 3D view",
                         4000)

    def leave_plan(self) -> None:
        """Back to the 3D view it came from (the button, the view bar)."""
        if not self.plan_on:
            return
        self.plan_on = False
        compat.lock_orbit(self.viewport, False)
        compat.plan_style(self.viewport, False)
        cam = compat.camera_state(self.viewport)
        if compat.is_top(cam):
            self._plan_cam = cam             # come back to this same plan
        if self._plan_back is not None:
            compat.set_camera_state(self.viewport, self._plan_back)
        else:
            compat.standard_view(self.viewport, "iso")
            compat.set_perspective(self.viewport, True)
        self._apply_parts()              # the whole building again
        self._sync_plan()
        self._cut3d_from_pick()          # a section line picked: cut there

    def _watch_plan(self, viewport) -> None:
        """Every frame (the overlay): has the camera left the plan? The
        orbit is locked, so only a view picked on purpose does it (Front,
        Iso, Perspective…) — that IS the 3D view now."""
        if self.side_view is not None and not self._plan_leaving:
            cam = compat.camera_state(viewport)
            if not cam["perspective"] and abs(cam["pitch"]) < 0.01:
                self._side_cams[self.side_view] = cam   # its pan / zoom
                return
            # another view picked on purpose (Iso, Perspective…): that IS
            # the 3D view now
            self._plan_leaving = True
            QTimer.singleShot(0, self._side_out)
            return
        if not self.plan_on or self._plan_leaving:
            return
        cam = compat.camera_state(viewport)
        if compat.is_top(cam) and not cam["perspective"]:
            self._plan_cam = cam             # where the plan is (pan, zoom)
            return
        self._plan_leaving = True
        QTimer.singleShot(0, self._orbited_out)

    def _orbited_out(self) -> None:
        self._plan_leaving = False
        if not self.alive or not self.plan_on:
            return
        tool = getattr(self.viewport, "active_tool", None)
        if compat.ours(tool) and getattr(tool, "draws_in_3d", False):
            QTimer.singleShot(0, lambda t=tool: self._say_floor_3d(t))
        self.plan_on = False
        compat.lock_orbit(self.viewport, False)
        compat.plan_style(self.viewport, False)
        self._plan_back = None
        compat.set_perspective(self.viewport, True)
        self._apply_parts()              # the whole building again
        self._sync_plan()
        self._cut3d_from_pick()

    def _sync_plan(self) -> None:
        on = self.plan_on or self.side_view is not None
        self.plan_btn.set_plan(on)
        self.viewbar.sync_view(self.plan_on)
        self.viewbar.sync_camera(compat.is_perspective(self.viewport))
        # the plan / elevations icons: while «Plan view» is on
        shown = bool(on and self.active)
        if shown:
            self.views.set_current(self.side_view or "plan",
                                   self._side_tips(), self.xray)
        if shown != self.views.isVisible():
            self._show_piece(self.views, self.views_bar, shown)
            QTimer.singleShot(0, self.layout_floating)

    # ---- Elevations (his idea, 2026-10-10) ---------------------------------------------
    #: a side's outward face, turned from the building's own axes (and the
    #: host's camera yaw for it: front −90°, right 0°, back 90°, left 180°)
    SIDE_TURN = {"front": -math.pi / 2, "right": 0.0, "back": math.pi / 2,
                 "left": math.pi}

    def building_angle(self, doc: dict | None = None) -> float:
        """The building's own axes: the walls' main way (each counted by
        its length, folded into a quarter turn), else the plot's longest
        side, else 0 — kept within ±45° (so «front» faces the −Y side)."""
        doc = doc or self.doc()
        votes: dict = {}
        for w in doc.get("walls") or []:
            if w.get("kind", "line") != "line":
                continue
            a, b = w["a"], w["b"]
            L = math.dist(a, b)
            if L < 0.3:
                continue
            ang = math.atan2(b[1] - a[1], b[0] - a[0]) % (math.pi / 2)
            k = round(math.degrees(ang)) % 90
            votes[k] = votes.get(k, 0.0) + L
        if votes:
            deg = max(votes, key=votes.get)
        elif self.has_plot(doc):
            pts = doc["plot"]["corners"]
            n = len(pts)
            i = max(range(n), key=lambda k: math.dist(pts[k],
                                                      pts[(k + 1) % n]))
            a, b = pts[i], pts[(i + 1) % n]
            deg = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 90
        else:
            deg = 0.0
        if deg > 45:
            deg -= 90
        return math.radians(deg)

    def _side_tips(self) -> dict:
        """The icons' tooltips — with the way each side faces, by the
        project's north (``north_deg``, clockwise from +Y)."""
        from .panels import VIEWS
        tips = dict(VIEWS)
        try:
            doc = self.doc()
            north = float((doc.get("project") or {}).get("north_deg", 0.0))
            th = self.building_angle(doc)
        except Exception:  # noqa: BLE001 — the plain names
            return tips
        names = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
        for side, turn in self.SIDE_TURN.items():
            phi = th + turn                      # its outward face
            # its bearing (clockwise from +Y), then from the project's north
            bearing = (math.degrees(math.atan2(math.cos(phi), math.sin(phi)))
                       - north) % 360
            tips[side] = f"{tips[side]} — facing {names[round(bearing / 45) % 8]}"
        return tips

    def show_view(self, key: str) -> None:
        """An icon of the views strip: the plan, or an elevation — parallel,
        level, squared with the building, framing it (the first time; then
        where you left it); locked like the plan (pan and zoom free)."""
        self.radial.dismiss()
        if key == "plan":
            if self.side_view is not None or not self.plan_on:
                self.enter_plan(quiet=True)
            self._sync_plan()
            return
        if key not in self.SIDE_TURN:
            return
        cam = compat.camera_state(self.viewport)
        if self.plan_on:
            # out of the plan without going back to the 3D view: the 3D
            # view to return to stays the one before the plan
            self.plan_on = False
            compat.plan_style(self.viewport, False)
            if compat.is_top(cam):
                self._plan_cam = cam
        elif self.side_view is None:
            self._plan_back = cam            # the 3D view to go back to
        # (the terrain is NOT hidden by itself — his call, 2026-10-10: too
        # invasive; the «Terrain» chip of the bar below does it)
        self.side_view = key
        if key in self._side_cams:
            compat.set_camera_state(self.viewport, self._side_cams[key])
        else:
            self._frame_side(key)
        compat.lock_orbit(self.viewport, True)
        self._apply_view_style()
        self._apply_parts()                  # every level: a whole side
        self._sync_plan()
        compat.flash(self.viewport, f"{dict(self._side_tips())[key]} — "
                     "pan and zoom freely; «Plan view» = back to 3D", 3500)

    def _frame_side(self, key: str) -> None:
        """The camera level, square on to that side, framing the
        building (its groups; nothing yet: the origin)."""
        from PySide6.QtGui import QVector3D
        cam = self.viewport.camera
        cam.perspective = False
        cam.yaw = self.building_angle() + self.SIDE_TURN[key]
        cam.pitch = 0.0
        lo = hi = None
        for g in self.viewport.scene.groups:
            if not compat.kind_of(g):
                continue
            try:
                for v in g.mesh.vertices:
                    p = v.position if hasattr(v, "position") else v
                    x, y, z = float(p.x()), float(p.y()), float(p.z())
                    lo = (x, y, z) if lo is None else (min(lo[0], x),
                                                       min(lo[1], y),
                                                       min(lo[2], z))
                    hi = (x, y, z) if hi is None else (max(hi[0], x),
                                                       max(hi[1], y),
                                                       max(hi[2], z))
            except Exception:  # noqa: BLE001 — a group we can't read
                continue
        if lo is None:
            lo, hi = (-10.0, -10.0, 0.0), (10.0, 10.0, 6.0)
        try:
            cam.fit_box(QVector3D(*lo), QVector3D(*hi))
        except Exception:  # noqa: BLE001
            cam.target = QVector3D((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2,
                                   (lo[2] + hi[2]) / 2)
        cam.pitch = 0.0
        cam.perspective = False
        self.viewport.update()

    def toggle_xray(self, on: bool) -> None:
        """The views strip's X-ray: faces see-through in the plan and the
        elevations — to pick and place what lies behind."""
        self.xray = bool(on)
        self._apply_view_style()
        compat.flash(self.viewport, "X-ray on — see through the faces"
                     if on else "X-ray off", 2500)

    def _apply_view_style(self) -> None:
        """The plan / elevation's look (a view change only — the file's
        style is not touched): X-ray when it is on, else the plan's hidden
        line (Settings), else the file's own; out of them, the file's."""
        if not (self.plan_on or self.side_view is not None):
            compat.plan_style(self.viewport, False)
            return
        from . import prefs
        if self.xray:
            compat.plan_style(self.viewport, True, "xray")
        elif prefs.get("plan_hidden_line"):
            compat.plan_style(self.viewport, True, "hidden_line")
        else:
            compat.plan_style(self.viewport, False)

    # ---- Picking THROUGH (elevations, the X-ray plan) — his ask, 2026-10-10 --------
    #: who is picked first under the cursor: the details (a stair, a column,
    #: a door…), then walls / slabs / roofs, the terrain last
    PICK_RANK = {"stair": 0, "ramp": 0, "column": 0, "beam": 0, "opening": 0,
                 "footing": 0, "guard": 0, "glazing": 0, "profile": 0,
                 "copy": 0,
                 "wall": 1, "slab": 1,
                 "roof": 1}

    def picking_through(self) -> bool:
        """In an elevation, or the plan with X-ray on, the Select tool's
        click is ArchXQ's: the host's picks the first face in front (the
        terrain, a wall) — what you want lies behind."""
        return bool(self.alive and self.active
                    and (self.side_view is not None
                         or (self.plan_on and self.xray))
                    and compat.selecting(self.viewport))

    def ghost_under(self, x: float, y: float) -> bool:
        """The Select tool's click would take a group of a level hidden by
        its eye — the host's pick does not look at the layers."""
        vp = self.viewport
        if not (self.alive and self.active and compat.selecting(vp)):
            return False
        g = compat.group_at(vp, x, y)
        return g is not None and not compat.shown(vp, g)

    def pick_candidates(self, x: float, y: float) -> list:
        """Every shown ArchXQ element under the screen point — details
        first, then the nearest."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF
        vp = self.viewport
        cam = vp.camera
        try:
            fw, eye = cam.forward(), cam.eye()
        except Exception:  # noqa: BLE001
            return []
        pt = QPointF(x, y)
        found = []
        for g in vp.scene.groups:
            k = compat.kind_of(g)
            if not k or not compat.shown(vp, g):
                continue
            depth = None
            try:
                for f in g.mesh.faces:
                    vs = list(f.vertices)
                    px = [compat.to_pixel(vp, v.x(), v.y(), v.z()) for v in vs]
                    if any(p is None for p in px) or len(px) < 3:
                        continue
                    if not QPolygonF([QPointF(*p) for p in px]).containsPoint(
                            pt, Qt.OddEvenFill):
                        continue
                    cx = sum(v.x() for v in vs) / len(vs)
                    cy = sum(v.y() for v in vs) / len(vs)
                    cz = sum(v.z() for v in vs) / len(vs)
                    d = ((cx - eye.x()) * fw.x() + (cy - eye.y()) * fw.y()
                         + (cz - eye.z()) * fw.z())
                    depth = d if depth is None else min(depth, d)
            except Exception:  # noqa: BLE001 — a group we can't read
                continue
            if depth is not None:
                found.append((self.PICK_RANK.get(k, 2), depth, g))
        found.sort(key=lambda t: (t[0], t[1]))
        return [g for _r, _d, g in found]

    PLAN_PICK_PX = 6         # px from an opening's plan symbol

    def plan_opening_pick(self, x: float, y: float, add: bool) -> bool:
        """In the plain plan (no X-ray), a click on an opening's symbol —
        its stretch of wall, its leaf, its swing — selects that opening
        (his test, 2026-10-11: a shopfront clicked in the plan selected the
        slab under it, then the plot, and the phase jumped to Terrain)."""
        vp = self.viewport
        gid = self.plan_glazing_at(x, y)
        if gid:
            # a glass grid (in its Opening, or free): its plan symbol picks
            # it — the wall over it took the click (his test, 2026-10-15)
            g = next((g for g in vp.scene.groups
                      if compat.kind_of(g) == "glazing"
                      and compat._rec(g).get("id") == gid), None)
            if g is not None:
                compat.select(vp, [g], "add" if add else "replace")
                compat.flash(vp, f"«{g.name}»", 2500)
                return True
        oid = self.plan_opening_at(x, y)
        if not oid:
            return False
        g = next((g for g in vp.scene.groups
                  if compat.kind_of(g) == "opening"
                  and compat._rec(g).get("id") == oid), None)
        if g is None:
            o = next((x_ for x_ in self.doc()["openings"]
                      if x_["id"] == oid), None)
            if o is not None and o["kind"] == "void":
                # an empty Opening: picked as the host's item — its grips
                if compat.take_pick(self.app, vp, oid):
                    return True
                compat.flash(vp, f"«{o['name']}» (an empty Opening) — "
                             "double-click it: its window; «Delete» there "
                             "closes the hole", 6000)
                return True
            return False
        compat.select(vp, [g], "add" if add else "replace")
        compat.flash(vp, f"«{g.name}»", 2500)
        return True

    def void_at(self, x: float, y: float) -> str | None:
        """The id of the empty Opening (a void, no glass grid in it) whose
        hole is under the screen point — in 3D (its rectangle in its wall's
        plane) or in the plan. A void has nothing to pick: this is the way
        to its window, to close the hole (his question, 2026-10-15)."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF
        from . import structure as S
        from . import walls as W
        if not (self.alive and self.active
                and compat.selecting(self.viewport)):
            return None
        vp = self.viewport
        doc = self._live(self.doc())   # a door deleted in the host: a hole
        filled = {e.get("op") for e in doc.get("structure") or []
                  if e.get("type") == "glazing"}
        voids = [o for o in doc.get("openings") or []
                 if o["kind"] == "void" and o["id"] not in filled]
        if not voids:
            return None
        info = S.levels_info(doc, model.elevations)
        walls = {w["id"]: w for w in doc["walls"]}
        hidden = getattr(self, "hidden_parts", set())
        if "openings" in hidden or "walls" in hidden:
            return None
        pt = QPointF(x, y)
        for o in voids:
            w = walls.get(o["wall"])
            if w is None or w.get("kind", "line") != "line" \
                    or w["level"] not in info:
                continue
            if not compat.layer_visible(vp, compat.level_layer(next(
                    (lv["name"] for lv in doc["levels"]
                     if lv["id"] == w["level"]), ""))):
                continue
            seg = W.centre(w)
            u = seg.u
            n = (-u[1], u[0])
            z0 = info[w["level"]]["z0"] + W.opening_lift(w) \
                + float(o.get("sill", 0.0))
            z1 = z0 + float(o["h"])
            s0, s1 = o["pos"] - o["w"] / 2, o["pos"] + o["w"] / 2
            for c in (0.0, float(w["t"]) / 2, -float(w["t"]) / 2):
                def P(s, z, c=c):
                    return compat.to_pixel(
                        vp, seg.p0[0] + u[0] * s + n[0] * c,
                        seg.p0[1] + u[1] * s + n[1] * c, z)
                quad = [P(s0, z0), P(s1, z0), P(s1, z1), P(s0, z1)]
                if any(q is None for q in quad):
                    continue
                if QPolygonF([QPointF(*q) for q in quad]).containsPoint(
                        pt, Qt.OddEvenFill):
                    return o["id"]
        return None

    # ---- an Opening's HOLE picked (PLANO_PEGAS_VAOS.md, his OK 25/10) ----------
    def _void_pick_at(self, viewport, x: float, y: float):
        """The host's Select tool asks (its pickables, before the model):
        the Opening whose HOLE is under (x, y) in 3D — an empty one (its
        grips: ``grip_targets``) or a door's / window's (its group picked
        then); None when something stands in front of the hole, or none.
        The plan picks by the symbol (``plan_opening_pick``)."""
        try:
            hit = self._opening_hole_at(x, y)
            return hit or self._slab_hole_at(x, y)
        except Exception:  # noqa: BLE001 — never in the host's way
            return None

    # a slab's OPENING picked as a wall's empty one is (his ask, 2026-10-26:
    # a click in the hole did nothing; «with its grips too, or we'll have
    # lots of complaints») — its pick id «hole:<slab>:<index>»
    HOLE = "hole:"

    def _hole_of(self, pid, doc=None):
        """(the slab, the opening's index, the slab's top) of a «hole:»
        pick id — None when gone or out of sight."""
        from . import structure as S
        if not (isinstance(pid, str) and pid.startswith(self.HOLE)):
            return None
        try:
            sid, j = pid[len(self.HOLE):].rsplit(":", 1)
            j = int(j)
        except ValueError:
            return None
        doc = doc or self._grip_read()
        e = next((x for x in doc.get("structure") or []
                  if x.get("id") == sid and x.get("type") == "slab"), None)
        info = S.levels_info(doc, model.elevations)
        if e is None or e["level"] not in info \
                or j >= len(e.get("holes") or []):
            return None
        return e, j, info[e["level"]]["z0"] + float(e.get("offset", 0.0))

    def _slab_hole_at(self, x: float, y: float):
        """The «hole:» pick id of the slab opening under (x, y) — in 3D
        and in the plan; None when something stands in front, or none."""
        from . import grips as G
        from . import structure as S
        vp = self.viewport
        if not (self.alive and self.active and compat.selecting(vp)) \
                or edition.lite() and is_pro("slab") \
                or "slabs" in getattr(self, "hidden_parts", set()):
            return None
        ray = compat.pixel_ray(vp, x, y)
        if ray is None:
            return None
        doc = self._live(self.doc())
        shown = {compat._rec(g).get("id") for g in vp.scene.groups
                 if compat.kind_of(g) == "slab" and compat.shown(vp, g)}
        info = S.levels_info(doc, model.elevations)
        best = None
        for e in doc.get("structure") or []:
            if e.get("type") != "slab" or not e.get("holes") \
                    or e["id"] not in shown or e["level"] not in info:
                continue
            top = info[e["level"]]["z0"] + float(e.get("offset", 0.0))
            hit = G.slab_hole_hit(e, top, *ray)
            if hit and (best is None or hit[0] < best[0]):
                best = (hit[0], f"{self.HOLE}{e['id']}:{hit[1]}")
        if best is None:
            return None
        near = compat.ray_distance(vp, *ray)
        if near is not None and near < best[0] - 0.02:
            return None                # something in front: theirs
        return best[1]

    def _opening_hole_at(self, x: float, y: float):
        from . import grips as G
        from . import structure as S
        vp = self.viewport
        if not (self.alive and self.active and compat.selecting(vp)) \
                or self.plan_on or edition.lite() and is_pro("opening"):
            return None
        hidden = getattr(self, "hidden_parts", set())
        if "openings" in hidden or "walls" in hidden:
            return None
        ray = compat.pixel_ray(vp, x, y)
        if ray is None:
            return None
        doc = self._live(self.doc())
        filled = {e.get("op") for e in doc.get("structure") or []
                  if e.get("type") == "glazing"}
        # a FREE grid set in an empty Opening fills it too: the click is the
        # grid's (his test, 2026-10-28: «Free» picked on a grid, the hole in
        # front of it took every click — the library showed the walls')
        filled |= S.voids_with_free_grid(doc)
        shown = {compat._rec(g).get("id") for g in vp.scene.groups
                 if compat.kind_of(g) == "wall" and compat.shown(vp, g)}
        info = S.levels_info(doc, model.elevations)
        walls = {w["id"]: w for w in doc["walls"] if w["id"] in shown}
        best = None
        for o in doc.get("openings") or []:
            w = walls.get(o["wall"])
            if w is None or w["level"] not in info or (
                    o["kind"] == "void" and o["id"] in filled):
                continue
            t = G.opening_hit(o, w, info[w["level"]]["z0"], *ray)
            if t is not None and (best is None or t < best[0]):
                best = (t, o["id"], w)
        if best is None:
            return None
        near = compat.ray_distance(vp, *ray)
        if near is not None and near < best[0] - 0.02:
            return None                # a column, a wall… in front: theirs
        return self._bars_first(doc, best[1], best[2], ray[0]) or best[1]

    GRID = "grid:"

    def _bars_first(self, doc: dict, oid: str, w: dict, origin):
        """A window with SECURITY BARS clicked from outside: the bars (the
        click went between them, onto the glass — his test, 2026-10-28:
        «it is always the window»); clicked again, the window. «grid:<id>»
        or None."""
        from . import walls as W
        bars = next((e for e in doc.get("structure") or []
                     if e.get("type") == "glazing" and e.get("op") == oid
                     and e.get("place") == "window"), None)
        if bars is None:
            return None
        if bars["id"] in {compat._rec(g).get("id")
                          for g in compat.selected_groups(self.viewport)}:
            import time
            from PySide6.QtWidgets import QApplication
            was = getattr(self, "_bars_at", 0.0)
            if time.monotonic() - was \
                    < QApplication.doubleClickInterval() / 1000.0 + 0.15:
                return self.GRID + bars["id"]   # (a double-click: still them)
            return None                  # the bars picked: now the window
        seg = W.centre(w)
        n = (-seg.u[1], seg.u[0])
        c = (origin[0] - seg.p0[0]) * n[0] + (origin[1] - seg.p0[1]) * n[1]
        inside = 1.0 if float(w.get("side", 1)) >= 0 else -1.0
        return self.GRID + bars["id"] if c * inside < 0 else None

    def _void_selected(self, oid) -> None:
        """The host tells what it picked of ours (None: let go)."""
        vp = self.viewport
        # the library follows: none for a hole (never the next wall's), back
        # when it is let go (his call, 2026-10-28)
        QTimer.singleShot(0, self._library_show)
        if oid is None:
            self._void_picked = None
            vp.update()
            return
        if isinstance(oid, str) and oid.startswith(self.GRID):
            # a window's security bars (``_bars_first``): their group
            gid = oid[len(self.GRID):]
            self._void_picked = None
            g = next((g for g in vp.scene.groups
                      if compat._rec(g).get("id") == gid), None)
            if g is not None:
                import time
                self._bars_at = time.monotonic()

                def take_bars(g=g):
                    compat.release_pick(self.app)
                    compat.select(vp, [g], "replace")
                    compat.flash(vp, f"«{g.name}» — click again: its window",
                                 3000)
                QTimer.singleShot(0, take_bars)
            return
        doc = self._live(self.doc())
        hole = self._hole_of(oid, doc)
        if hole is not None:                 # a slab's opening
            self._void_picked = oid
            if not self._void_quiet:
                name = hole[0].get("name") or "the slab"
                compat.flash(vp, f"Opening {hole[1] + 1} of «{name}» — drag "
                             "its corners, sides or middle · double-click = "
                             "the slab's window · Delete closes it · Esc",
                             5000)
            vp.update()
            return
        o = next((x for x in doc.get("openings") or [] if x["id"] == oid),
                 None)
        if o is None:
            self._void_picked = None
            return
        g = next((g for g in vp.scene.groups
                  if compat.kind_of(g) == "opening"
                  and compat._rec(g).get("id") == oid), None)
        if g is not None:
            # a door's / window's hole: the door itself, as a click on it
            self._void_picked = None

            def take(g=g):
                compat.release_pick(self.app)
                compat.select(vp, [g], "replace")
                compat.flash(vp, f"«{g.name}»", 2500)
            QTimer.singleShot(0, take)
            return
        self._void_picked = oid
        if not self._void_quiet:
            compat.flash(vp, f"«{o['name']}» — drag its sides, top, sill or "
                         "centre · double-click = its window · Delete "
                         "closes the hole · Esc", 5000)
        vp.update()

    def _void_repick(self, oid: str) -> None:
        """Our change dropped the host's pick: the Opening picked again."""
        self._void_quiet = True
        try:
            if not compat.take_pick(self.app, self.viewport, oid):
                self._void_picked = oid
        finally:
            self._void_quiet = False

    def _void_delete(self, oid) -> None:
        """Supr on the picked Opening: the hole closed (one Ctrl+Z)."""
        self._void_picked = None
        doc = self._live(self.doc())
        hole = self._hole_of(oid, doc)
        if hole is not None:                 # a slab's opening: closed
            sid, j = hole[0]["id"], hole[1]
            doc["structure"] = [
                dict(x, holes=[h for i, h in enumerate(x["holes"]) if i != j])
                if x.get("id") == sid else x
                for x in doc["structure"]]
            self._commit_all(doc)
            compat.flash(self.viewport, "Opening closed — Ctrl+Z undoes it",
                         3000)
            return
        self.delete_opening(oid)

    def _void_grips(self):
        """(«opening», id, its grips) of the picked empty Opening — None
        (and let go) when it is gone, filled or out of sight."""
        from . import grips as G
        from . import structure as S
        doc = self._grip_read()
        if str(self._void_picked).startswith(self.HOLE):   # a slab's opening
            hole = self._hole_of(self._void_picked, doc)
            if hole is None:
                self._void_picked = None
                return None
            e, j, z = hole
            return "slab", e["id"], G.hole_grips(
                j, [tuple(p) for p in e["holes"][j]], z)
        o = next((x for x in doc.get("openings") or []
                  if x["id"] == self._void_picked), None)
        w = next((x for x in doc["walls"] if o and x["id"] == o["wall"]),
                 None)
        info = S.levels_info(doc, model.elevations)
        if w is None or w["level"] not in info or any(
                e.get("op") == o["id"] for e in doc.get("structure") or []
                if e.get("type") == "glazing"):
            self._void_picked = None
            return None
        return "opening", o["id"], G.opening_grips(o, w,
                                                   info[w["level"]]["z0"])

    def _draw_void_picked(self, viewport, painter) -> None:
        """The picked empty Opening: its hole outlined orange (both faces
        and the jambs — the plan sees its footprint), as a selected element
        is drawn; nothing in the model."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen
        from . import structure as S
        from . import walls as W
        if not self._void_picked or self._grips.drag is not None:
            return
        try:
            doc = self._grip_read()
            hole = self._hole_of(self._void_picked, doc)
            if hole is not None:      # a slab's opening: its outline, top
                e, j, z = hole        # and underside
                rings = []
                for zz in (z, z - float(e.get("t", 0.2))):
                    ring = [compat.to_pixel(viewport, p[0], p[1], zz)
                            for p in e["holes"][j]]
                    if any(q is None for q in ring):
                        return
                    rings.append([QPointF(*q[:2]) for q in ring])
                segs = [(r[i], r[(i + 1) % len(r)]) for r in rings
                        for i in range(len(r))]
                segs += list(zip(rings[0], rings[1]))
                painter.save()
                painter.setRenderHint(painter.RenderHint.Antialiasing)
                halo = QColor(255, 255, 255, 150)
                for color, width in ((halo, 5.0),
                                     (QColor(self.SELECT_INK), 2.4)):
                    painter.setPen(QPen(color, width))
                    for pa, pb in segs:
                        painter.drawLine(pa, pb)
                painter.restore()
                return
            o = next((x for x in doc.get("openings") or []
                      if x["id"] == self._void_picked), None)
            w = next((x for x in doc["walls"] if o and x["id"] == o["wall"]),
                     None)
            info = S.levels_info(doc, model.elevations)
            if w is None or w["level"] not in info:
                return
            seg = W.centre(w)
            u = seg.u
            n = (-u[1], u[0])
            s0, s1 = o["pos"] - o["w"] / 2, o["pos"] + o["w"] / 2
            z0 = info[w["level"]]["z0"] + W.opening_lift(w) \
                + float(o.get("sill", 0.0))
            z1 = z0 + float(o["h"])
            corners = {}
            for c in (float(w["t"]) / 2, -float(w["t"]) / 2):
                for s, z in ((s0, z0), (s1, z0), (s1, z1), (s0, z1)):
                    p = compat.to_pixel(
                        viewport, seg.p0[0] + u[0] * s + n[0] * c,
                        seg.p0[1] + u[1] * s + n[1] * c, z)
                    if p is None:
                        return
                    corners[(c > 0, s, z)] = QPointF(*p)
            ring = ((s0, z0), (s1, z0), (s1, z1), (s0, z1))
            segs = []
            for side in (True, False):
                for a, b in zip(ring, ring[1:] + ring[:1]):
                    segs.append((corners[(side, *a)], corners[(side, *b)]))
            for a in ring:
                segs.append((corners[(True, *a)], corners[(False, *a)]))
            painter.save()
            painter.setRenderHint(painter.RenderHint.Antialiasing)
            halo = QColor(255, 255, 255, 150)
            for color, width in ((halo, 5.0), (QColor(self.SELECT_INK), 2.4)):
                painter.setPen(QPen(color, width))
                for pa, pb in segs:
                    painter.drawLine(pa, pb)
            painter.restore()
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    def plan_glazing_at(self, x: float, y: float) -> str | None:
        """The id of the glass grid whose plan footprint (across its wall,
        a little wider when free) is under the screen point — the plain
        plan, the Select tool. None: none."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF
        if edition.lite() or not (self.alive and self.active and self.plan_on
                                  and self.side_view is None
                                  and compat.selecting(self.viewport)):
            return None
        vp = self.viewport
        at = self._plan_level(vp)
        if at is None:
            return None
        doc, lv, z = at
        grids = [e for e in doc.get("structure") or []
                 if e.get("type") == "glazing" and e.get("level") == lv["id"]]
        if not grids:
            return None
        try:
            from . import glazing as GZ
        except ImportError:
            return None
        walls = {w["id"]: w for w in doc["walls"]}
        pt = QPointF(x, y)
        for e in grids:
            fr = GZ.frame_of(e, doc, lambda _l: z)
            if fr is None:
                continue
            p0, u, n, _o, Wd, _zb, _H = fr
            half = 0.10
            if e.get("place") != "free":
                o, w = self._glazing_void_of(doc, e)
                if w is not None:
                    half = float(w["t"]) / 2
            half = max(half, float(GZ.opt(e, "fd")) / 2 + 0.05)

            def P(s, c):
                return (p0[0] + u[0] * s + n[0] * c,
                        p0[1] + u[1] * s + n[1] * c)
            px = [compat.to_pixel(vp, *P(s, c), z) for s, c in
                  ((0, -half), (Wd, -half), (Wd, half), (0, half))]
            if any(p is None for p in px):
                continue
            if QPolygonF([QPointF(*p) for p in px]).containsPoint(
                    pt, Qt.OddEvenFill):
                return e["id"]
        return None

    def plan_opening_at(self, x: float, y: float) -> str | None:
        """The id of the opening whose plan symbol is under the screen
        point (the plain plan, the Select tool) — None: none."""
        import math as _m

        from . import openingtools as OT
        from . import walls as W
        if not (self.alive and self.active and self.plan_on
                and self.side_view is None
                and compat.selecting(self.viewport)):
            return None
        vp = self.viewport
        at = self._plan_level(vp)
        if at is None:
            return None
        doc, lv, z = at
        doc = self._live(doc)        # a door deleted in the host: its hole
        walls = {w["id"]: w for w in doc["walls"] if w["level"] == lv["id"]
                 and w.get("kind", "line") == "line"}

        def px(q):
            return compat.to_pixel(vp, q[0], q[1], z)

        def near(a, b) -> float:
            pa, pb = px(a), px(b)
            if not pa or not pb:
                return 1e9
            dx, dy = pb[0] - pa[0], pb[1] - pa[1]
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 < 1e-9 else max(0.0, min(1.0, (
                (x - pa[0]) * dx + (y - pa[1]) * dy) / L2))
            return _m.hypot(x - pa[0] - dx * t, y - pa[1] - dy * t)
        best = None
        for o in doc["openings"]:
            w = walls.get(o["wall"])
            # (a VOID too: it has nothing to see, its double-click is the
            # only way to its window — to close its hole: his question,
            # 2026-10-15)
            if w is None:
                continue
            seg = W.centre(w)
            t = float(w["t"]) / 2
            s0, s1 = o["pos"] - o["w"] / 2, o["pos"] + o["w"] / 2

            def P(s, c, p0=seg.p0, u=seg.u):
                return (p0[0] + u[0] * s - u[1] * c,
                        p0[1] + u[1] * s + u[0] * c)
            box = [px(P(s0, -t)), px(P(s1, -t)), px(P(s1, t)), px(P(s0, t))]
            d = 1e9
            if all(box):
                from PySide6.QtCore import QPointF
                from PySide6.QtGui import QPolygonF
                if QPolygonF([QPointF(*q) for q in box]).containsPoint(
                        QPointF(x, y), Qt.OddEvenFill):
                    d = 0.0
            if d > 0:
                d = min([d] + [near(a, b) for a, b in
                               OT.symbol_lines(o, w, seg)])
            if d <= self.PLAN_PICK_PX and (best is None or d < best[0]):
                best = (d, o)
        return best[1]["id"] if best else None

    def pick_through(self, x: float, y: float, add: bool) -> bool:
        """Select what is under the cursor — the same spot clicked again:
        the next one behind. False: nothing of ours there."""
        cands = self.pick_candidates(x, y)
        if not cands:
            self._pick = None
            return False
        ids = [id(g) for g in cands]
        last = self._pick
        if last and abs(x - last["x"]) < 5 and abs(y - last["y"]) < 5 \
                and last["ids"] == ids:
            i = (last["i"] + 1) % len(cands)
        else:
            i = 0
        self._pick = {"x": x, "y": y, "ids": ids, "i": i}
        g = cands[i]
        compat.select(self.viewport, [g], "add" if add else "replace")
        n = len(cands)
        compat.flash(self.viewport, f"«{g.name}»" + (
            f"  ({i + 1} of {n} here) — click again: the next one behind"
            if n > 1 else ""), 3500)
        QTimer.singleShot(80, lambda: self.radial_after_click(x, y))
        return True

    # ---- The radial menu (radial.py) -----------------------------------------------
    def radial_after_click(self, x: float, y: float, view=None) -> None:
        """After a plain click: the ring round it (on the view clicked),
        when what is selected is something the host's gestures move."""
        from . import prefs
        from .radial import MOVABLE
        if not self.alive or not self.active \
                or not compat.selecting(self.viewport) \
                or not prefs.get("radial_menu"):
            return
        sel = compat.selected_groups(self.viewport)
        kinds = {compat.kind_of(g) for g in sel}
        if sel and kinds <= MOVABLE:
            self.radial.popup(x, y, view, self._extras_of)
        else:
            self.radial.dismiss()

    def toggle_radial(self) -> None:
        """F9: the radial menu off / on (kept in the Settings)."""
        from . import prefs
        on = not prefs.get("radial_menu")
        prefs.put("radial_menu", on)
        if not on:
            self.radial.dismiss()
        compat.flash(self.viewport, "Radial menu " + ("ON — click a column, "
                     "beam, stair…" if on else "OFF — F9 brings it "
                     "back"), 3500)

    def radial_action(self, key: str) -> None:
        """A ring's button: the host's own gesture on the selection."""
        from . import radial as RD
        vp = self.viewport
        if key == "edit":
            sel = compat.selected_groups(vp)
            el = self.element_of(sel[0]) if sel else None
            if el is not None:
                self.edit_element(el)
            return
        if key == "align":               # ours (0.15.0): as Revit's
            ids = [compat._rec(g).get("id") for g in compat.selected_groups(vp)]
            self.start_align_tool([i for i in ids if i])
            return
        name = "Rotate" if key == "rotate" else "Move"
        if not RD.trigger(vp, name):
            compat.flash(vp, f"«{name}» not found in IngeTrazo's menus", 4000)
            return
        if key in ("copy", "array"):
            QTimer.singleShot(60, lambda: RD.tap_ctrl(vp))   # the copy mode
        compat.flash(vp, {
            "move": "Move — click a point of it, then where it goes "
                    "(or type the distance + Enter)",
            "copy": "Copy — click a point of it, then where the copy goes "
                    "(Ctrl toggles copy / move)",
            "array": "Array — place ONE copy, then type x3 + Enter (with the "
                     "x: three more, same step — «3» alone is a distance) · "
                     "/3 + Enter: three between",
            "rotate": "Rotate — click the centre, then the angle (or type "
                      "it + Enter)"}[key], 6000)

    def _terrain_for_side(self, entering: bool) -> None:
        """An elevation hides the TERRAIN (its sides covered the building —
        his screen, 2026-10-10); the «Terrain» chip still brings it back.
        Out of the elevations it comes back — if it was the elevation that
        hid it."""
        chip = getattr(self.viewbar, "parts", {}).get("terrain")
        if entering:
            if "terrain" in self.hidden_parts:
                return
            self.hidden_parts.add("terrain")
            self._side_hid_terrain = True
            on = False
        else:
            if not self._side_hid_terrain:
                return
            self._side_hid_terrain = False
            self.hidden_parts.discard("terrain")
            on = True
        if chip is not None:
            chip.blockSignals(True)
            chip.setChecked(on)
            chip.blockSignals(False)

    def _end_side(self) -> None:
        """Out of an elevation (the camera left where it is)."""
        if self.side_view is not None:
            self._side_cams[self.side_view] = compat.camera_state(
                self.viewport)
        self.side_view = None
        self._pick = None
        self._terrain_for_side(False)
        compat.lock_orbit(self.viewport, False)
        compat.plan_style(self.viewport, False)

    def leave_side(self) -> None:
        """«Plan view» clicked in an elevation: back to the 3D view."""
        if self.side_view is None:
            return
        self._end_side()
        if self._plan_back is not None:
            compat.set_camera_state(self.viewport, self._plan_back)
        else:
            compat.standard_view(self.viewport, "iso")
            compat.set_perspective(self.viewport, True)
        self._apply_parts()
        self._sync_plan()

    def _side_out(self) -> None:
        """Another view picked in an elevation: that is the 3D view now."""
        self._plan_leaving = False
        if not self.alive or self.side_view is None:
            return
        self.side_view = None
        self._pick = None
        self._terrain_for_side(False)
        compat.lock_orbit(self.viewport, False)
        compat.plan_style(self.viewport, False)
        self._plan_back = None
        self._apply_parts()
        self._sync_plan()

    def _activate(self, tool) -> None:
        """Every ArchXQ drawing / editing tool comes out here. A CREATION
        tool works in the plan view, locked (unless the Settings say not
        to); an EDITING tool leaves the camera free — points are dragged
        in 3D too (his call, 2026-10-03)."""
        from . import prefs
        if getattr(self, "radial", None) is not None:
            self.radial.dismiss()            # a tool out: the ring goes
        compat.activate_tool(self.viewport, tool)
        # (a finishing tool — a profile round a room — stays in the view it
        # is in: seen in 3D, inside the room — his call, 29/10)
        if self.active and getattr(tool, "creates", False) \
                and not getattr(tool, "stays_in_view", False) \
                and prefs.get("plan_on_tool"):
            self.enter_plan(quiet=True)
        self._sync_lock()
        QTimer.singleShot(0, self._library_show)     # its library, right

    def _plan_locks(self) -> bool:
        """The plan is locked to the top unless an EDITING tool is out."""
        tool = getattr(self.viewport, "active_tool", None)
        editing = compat.ours(tool) \
            and not getattr(tool, "creates", False)
        return self.plan_on and not editing

    def _sync_lock(self) -> None:
        compat.lock_orbit(self.viewport, self._plan_locks())

    def on_perspective(self, on: bool) -> None:
        compat.set_perspective(self.viewport, on)

    def on_camera(self, name: str) -> None:
        if name == "extents":
            compat.zoom_extents(self.viewport)
        else:
            compat.standard_view(self.viewport, name)
            cam = compat.camera_state(self.viewport)
            self._view_marked = (name, cam["yaw"], cam["pitch"])
            self.viewbar.mark_view(name)

    def _watch_view_mark(self, viewport) -> None:
        """Every frame: the lit view chip goes dark once the camera turns
        (a pan or a zoom keeps it)."""
        mark = getattr(self, "_view_marked", None)
        if mark is None:
            return
        cam = compat.camera_state(viewport)
        if abs(cam["yaw"] - mark[1]) > 1e-4 \
                or abs(cam["pitch"] - mark[2]) > 1e-4:
            self._view_marked = None
            QTimer.singleShot(0, lambda: self.viewbar.mark_view(None))

    # ---- The host's own editing tools on ArchXQ's elements -------------------------
    def _after_command(self, history, cmd) -> None:
        """After a command of the host: did its Move / Rotate / Copy take
        ArchXQ's elements somewhere? Their records follow, the building is
        rebuilt — and both are ONE Ctrl+Z (edits.py; his ask, 2026-10-08:
        never below what IngeTrazo already does)."""
        from . import edits
        if self._adopting or not self.alive \
                or history is not self.viewport.history \
                or getattr(history, "last_error", None) \
                or not history.undo_stack or history.undo_stack[-1] is not cmd:
            return
        self._guides_to_level(cmd)
        groups = [g for g in self.viewport.scene.groups
                  if compat.kind_of(g) in edits.ADOPT]
        was = self.doc()
        live = self._live(was)
        doc, notes = edits.adopt(live, groups)
        if doc is None:
            self._after_delete(history, cmd, was, live)
            return
        self._adopting = True
        try:
            self._commit_all(doc)
        finally:
            self._adopting = False
        compat.join_last_steps(history, cmd)
        if notes:
            compat.flash(self.viewport, " · ".join(notes)
                         + " — Ctrl+Z undoes it", 5000)

    def _before_command(self, history, cmd) -> None:
        """Just before a command of the host: an EXPLODE of a wall / slab
        with layers hidden in the 3D gets it WHOLE (layerview.py, his OK
        02/11 — nothing left behind; the explode is the professionals'
        nº 1). Its build's mark dropped: rebuilt at the next change."""
        from core.history import ExplodeGroupCommand
        if not self.alive or history is not self.viewport.history:
            return

        def groups(c):
            if isinstance(c, ExplodeGroupCommand):
                g = getattr(c, "group", None)
                return [g] if g is not None else []
            return [g for k in getattr(c, "commands", None) or ()
                    for g in groups(k)]
        gs = groups(cmd)
        if not gs or not self.doc().get("hidden_layers"):
            return
        from . import model
        for g, mesh in compat.whole_meshes(self.viewport, self.doc(),
                                           model.elevations, gs):
            g.mesh = mesh
            compat._rec(g)["sig"] = None

    def _after_delete(self, history, cmd, doc: dict, live: dict) -> None:
        """A wall deleted with the host's own tools (Delete key, eraser —
        support #64, 2026-10-27): its neighbours stayed mitred to nothing
        until the next change. Rebuilt now, ONE Ctrl+Z with the delete. An
        Explode is left alone (its geometry stays as the screen shows it;
        the next change frees its doors — explode.py)."""
        from core.history import ExplodeGroupCommand

        def explodes(c) -> bool:
            return isinstance(c, ExplodeGroupCommand) or any(
                explodes(k) for k in getattr(c, "commands", None) or ())
        if not doc.get("built") or explodes(cmd):
            return
        if len(live["walls"]) == len(doc["walls"]):
            return                          # no wall of ours went
        self._adopting = True
        try:
            self._commit_all(live)
        finally:
            self._adopting = False
        compat.join_last_steps(history, cmd)

    def _stamp_old(self) -> None:
        """Elements built by an older version (a file opened) carry no
        «where it was built» yet: stamped as they stand — their next host
        Move is adopted too."""
        from . import edits
        nth: dict = {}
        for g in self.viewport.scene.groups:
            if compat.kind_of(g) not in edits.ADOPT:
                continue
            r = compat._rec(g)
            k = nth[r.get("id")] = nth.get(r.get("id"), -1) + 1
            if not r.get("ref") or "zr" not in r:
                edits.stamp(g, k)

    def _paint_old(self) -> None:
        """Elements built before their kind had a default material (a file
        opened — his screen, 2026-10-09: the walls and the ground stayed
        plain while the stairs had theirs): painted as they stand, without
        a rebuild. Only groups with no material on any face — what was
        painted (a choice, a default) is never touched again."""
        from . import materials as M
        if not M.textures_allowed():
            return
        # each group tried ONCE: one that takes no paint (no faces…) must
        # never make the scene change again and again (the refresh loop's
        # lesson)
        tried = self.__dict__.setdefault("_paint_tried", set())
        bare = []
        for g in self.viewport.scene.groups:
            k = compat.kind_of(g)
            if k in M.DEFAULTS and id(g) not in tried and not any(
                    "mat" in f.attrs for f in g.mesh.faces):
                bare.append((g, k))
                tried.add(id(g))
        if not bare:
            return
        doc = self.doc()
        for g, k in bare:
            fl = compat._rec(g).get("floor")      # a room's floor
            M.paint(self.viewport.scene, g, "floor" if fl else k,
                    fl or ("plot" if k == "plot" else
                           compat._rec(g).get("id")), doc)
        compat.touch_scene(self.viewport)

    # ---- Refresh -------------------------------------------------------------------
    #: the next pieces' sizes in a feet / inches document — round American
    #: ones (inches), where the metric defaults would read 2'11 7/16"
    IMPERIAL_DEFAULTS = {
        "wall_opts": {"t": 6, "h": 108},
        "col_opts": {"w": 12, "d": 12},
        "beam_opts": {"w": 8, "h": 18},
        "slab_opts": {"t": 6},
        "foot_opts": {"w": 48, "sw": 24, "d": 18},
        "guard_opts": {"h": 42, "t": 6, "wall_h": 18, "step_h": 6,
                       "gap_w": 36},
        "roof_opts": {"overhang": 18, "go": 12, "t": 8, "parapet": 36},
        "glazing_opts": {"h": 84},
        ("op_opts", "door"): {"w": 36, "h": 80, "dh": 84},
        ("op_opts", "window"): {"w": 36, "h": 48, "sill": 36},
    }

    def _unit_defaults(self) -> None:
        """Another document: its units set the next pieces' sizes — feet /
        inches: IMPERIAL_DEFAULTS; metres: the metric ones as they were
        (kept aside the first time). Sizes already changed by hand in this
        session give way: a new document starts clean."""
        import copy
        imp = compat.imperial()
        if not hasattr(self, "_metric_defaults"):
            self._metric_defaults = {}
            for key in self.IMPERIAL_DEFAULTS:
                name, sub = key if isinstance(key, tuple) else (key, None)
                d = getattr(self, name, None)
                d = d.get(sub) if (d is not None and sub) else d
                if isinstance(d, dict):
                    self._metric_defaults[key] = {
                        k: copy.deepcopy(d[k]) for k in
                        self.IMPERIAL_DEFAULTS[key] if k in d}
        if imp == getattr(self, "_defaults_imperial", False):
            return
        self._defaults_imperial = imp
        for key, vals in self.IMPERIAL_DEFAULTS.items():
            name, sub = key if isinstance(key, tuple) else (key, None)
            d = getattr(self, name, None)
            d = d.get(sub) if (d is not None and sub) else d
            if not isinstance(d, dict):
                continue
            if imp:
                for k, inches in vals.items():
                    if k in d:
                        d[k] = round(inches * 0.0254, 4)
            else:
                d.update(self._metric_defaults.get(key, {}))

    def _on_doc_changed(self) -> None:
        """The host says the document changed — it says so for every
        change of the scene, view ones too. ArchXQ rebuilds its pieces
        only when ITS data or its objects did change: a refresh that
        touches the view must never feed itself (it once ran 20 times a
        second and the bars never got to show their buttons)."""
        if not self.alive:
            return
        self._follow_tab()
        self._stamp_old()
        self._paint_old()
        _ifc = _pro_module("ifctags")
        if _ifc is not None:
            try:
                _ifc.sync(self.viewport.scene.groups)
            except Exception:  # noqa: BLE001 — never in the way
                compat.log_error("ifc tags")
        # ANOTHER FILE opened (or New): the section planes ArchXQ made for
        # the file before stay behind in IngeTrazo 0.5.8 — they go
        path = compat.document_path(self.window)
        if path != getattr(self, "_doc_path", None):
            self._doc_path = path
            self._unit_defaults()
            # the file's own «Section Planes» / active cut came in with it:
            # hidden again (what we noted was the scene before)
            self._marks_off = self._cut3d = None
            self._host_marks_sync()
            _docs = _pro_module("docs")
            if _docs is not None:
                try:
                    _docs.drop_stale_planes(self.viewport)
                except Exception:  # noqa: BLE001 — never in the way
                    compat.log_error("drop stale planes")
        if not self.active:
            return
        try:
            data = repr(self.app.document_data(None))
        except Exception:  # noqa: BLE001
            data = None
        sig = (data, sum(1 for g in self.viewport.scene.groups
                         if compat.kind_of(g)),
               tuple(L.name for L in self.viewport.scene.layers))
        if sig == getattr(self, "_doc_sig", None):
            return
        self._doc_sig = sig
        self.refresh()
        # a new piece's textures (a street's 3): drawn without a camera move
        compat.frames_for_textures(self.viewport)

    # ---- Project tabs (IngeTrazo 0.6.0) -------------------------------------------
    #: what ArchXQ keeps per project, swapped as another tab comes in front
    _TAB_KEYS = ("current", "element", "method", "floor", "terrain_current",
                 "plan_on", "_plan_back", "_plan_cam", "side_view",
                 "_side_cams", "xray", "_side_hid_terrain", "hidden_parts")

    def _pieces(self) -> tuple:
        """Every ArchXQ widget that is a child of the 3D view."""
        return (self.hub, self.plan_btn, self.views, self.strip, self.elbox,
                self.viewbar, self.present_btn, self.levels, self.levels_tab,
                self.optbar, self.radial, self.quick.card,
                *self._hub_scroll.arrows(), *self._viewbar_scroll.arrows())

    def _levels_on(self) -> bool:
        """The levels strip open? With several views it starts folded in its
        tab: a whole column for it would take the views' room."""
        return self._framed_levels if self._framed else self.levels_open

    def _move_pieces(self, host, framed: bool) -> None:
        """ArchXQ's pieces onto ``host`` (the radial menu stays on the view:
        it opens where the mouse is)."""
        old = self._ui_parent
        try:
            if old is not None and old is not host and self._framed:
                viewframe.set_margins(old, 0, 0, 0, 0)
                old.removeEventFilter(self._watch)
        except RuntimeError:     # (its project tab is gone)
            pass
        moving = [w for w in self._pieces() if w is not self.radial]
        shown = {w: not w.isHidden() for w in moving}
        self._frame_busy = True
        try:
            for w in moving:
                w.setParent(host)
                w.setVisible(shown[w])
        finally:
            self._frame_busy = False
        self._ui_parent = host
        self._framed = framed
        self._frame_left = 0
        if framed:
            self._framed_levels = False
            host.installEventFilter(self._watch)
        if self.active:
            self._show_piece(self.levels, self.levels_bar, self._levels_on())

    def _sync_frame(self) -> None:
        """On the view, or around the views: as the host shows them now."""
        home = self._home
        if home is None:
            return
        grid = viewframe.grid_of(home)
        several = grid is not None and viewframe.several(grid)
        if several and grid is not self._extras_of:
            self._watch_extras(grid)
        framed = several and self.active
        host = grid if framed else home
        if host is not self._ui_parent:
            self._move_pieces(host, framed)

    def _watch_extras(self, grid, on: bool = True) -> None:
        """The other views get the keys, the double-click, Space's pan, the
        radial menu and the grips too: the focus may be on any of them (Esc
        did not end «Present» — found 09/11/2026). In the order of
        ``_filters``: the grips last, so they see a press first."""
        for v in viewframe.extras(grid, self._home):
            for f in (self._present_esc, self._tool_esc, self._space_pan,
                      self._nkey, self._keys, self._dbl, self._radial_watch,
                      self._grips):
                v.removeEventFilter(f)
                if on:
                    v.installEventFilter(f)
        self._extras_of = grid if on else None

    def _selecting(self) -> bool:
        """The host's Select tool is out. With another view active the host
        takes the tool off the main view while it paints it: then the views
        that hold the tool say."""
        if getattr(self.viewport, "active_tool", None) is not None:
            return compat.selecting(self.viewport)
        return any(compat.selecting(v) for v in self.each_view())

    def each_view(self) -> list:
        """The project's 3D views: the main one and the host's others."""
        views = [self.viewport]
        if self._extras_of is not None:
            try:
                views += viewframe.extras(self._extras_of, self._home)
            except RuntimeError:     # (its project tab is gone)
                pass
        return views

    def _filters(self) -> tuple:
        """The key / mouse watchers on the 3D view, in the order installed
        (the last one sees an event first)."""
        return (self._present_esc, self._tool_esc, self._space_pan,
                self._nkey, self._watch, self._keys, self._hover_off,
                self._dbl, self._radial_watch, self._pickthru,
                self._sec_filter, self._grips)

    def _follow_tab(self) -> bool:
        """Another project tab came in front (each has its own 3D view):
        ArchXQ's pieces, its watchers and its session state move to it.
        True when they moved."""
        new, old = self.app.viewport, self._home
        if new is None or new is old:
            return False
        try:
            self._leave_tab(old)
            self._home = new
            self._enter_tab(old, new)
        except Exception:  # noqa: BLE001 — never in the host's way
            self._home = new
            compat.log_error("project tab")
        return True

    def _leave_tab(self, old) -> None:
        """What was under way stays in that project: the tool out, a grip
        dragged, the previews; its session state is kept for its return."""
        if old is None:          # (parked as its tab closed: _shown kept)
            return
        if self._ui_parent is not old:   # (several views: back on its view)
            self._move_pieces(old, False)
        self._shown = {w: not w.isHidden() for w in self._pieces()}
        try:
            self._grips.cancel()
        except Exception:  # noqa: BLE001
            pass
        if compat.ours(getattr(old, "active_tool", None)):
            compat.back_to_select(old)
        self.radial.hide()
        self.plot_preview = self.setback_preview = self.dig_preview = None
        self._live_meshes.clear()
        self._live_ctx.clear()
        self._pick = self._void_picked = None
        self._sec_picked = self._sec_live = None
        self._sec_cache = (None, [])
        self._last_row = None
        self._tab_state[id(old.scene)] = {k: getattr(self, k)
                                          for k in self._TAB_KEYS}

    def _enter_tab(self, old, new) -> None:
        shown = getattr(self, "_shown", {})
        for w in self._pieces():
            w.setParent(new)
            w.setVisible(shown.get(w, False))
            if shown.get(w):
                w.raise_()
        self._ui_parent = new
        self._framed = False
        for f in self._filters():
            if old is not None:
                old.removeEventFilter(f)
        for f in self._filters() + (self._cursor,):
            if "viewport" in vars(f):
                f.viewport = new
        self.radial.viewport = new
        for f in self._filters():
            new.installEventFilter(f)
        if old is not None:
            try:
                old.sceneVersionChanged.disconnect(self._outline_soon)
            except (RuntimeError, TypeError):
                pass
        new.sceneVersionChanged.connect(self._outline_soon)
        _docs = _pro_module("docs")
        if _docs is not None:
            if old is not None:
                _docs.full_geometry(old, False)   # the host's fast path back
            _docs.full_geometry(new, True)
        # this project's own state — or, the first time, as a file opens
        st = self._tab_state.get(id(new.scene))
        if st:
            for k, v in st.items():
                setattr(self, k, v)
        else:
            doc = self.doc()
            self.current = next_open(self._done(doc), doc["system"])
            self.element = PHASES[self.current].elements[0]
            self.method = None
            self.floor = self._ground_index(doc)
            # a file opening on the Terrain phase works on the Terrain row
            # (07/11/2026 — see _row_for_phase)
            self.terrain_current = self.current == "terrain"
            self.plan_on = False
            self._plan_back = self._plan_cam = None
            self.side_view = None
            self._side_cams = {}
            self.xray = self._side_hid_terrain = False
            self.hidden_parts = set()
        self._doc_sig = None
        self.layout_floating()

    def _on_doc_closed(self, scene) -> None:
        """A project tab closes: its state goes; if ArchXQ's pieces were on
        its 3D view, they leave it first (they would go with it)."""
        self._tab_state.pop(id(scene), None)
        home = self._home
        if not self.alive or home is None or \
                getattr(home, "scene", None) is not scene:
            return
        try:
            if self.app.viewport is not home:
                self._follow_tab()
            if self._home is home:      # still on it: parked on the window
                self._shown = {w: not w.isHidden() for w in self._pieces()}
                for f in self._filters():
                    home.removeEventFilter(f)
                try:
                    home.sceneVersionChanged.disconnect(self._outline_soon)
                except (RuntimeError, TypeError):
                    pass
                for w in self._pieces():
                    w.hide()
                    w.setParent(self.window)
                self._ui_parent = None
                self._framed = False
                self._home = None
                QTimer.singleShot(0, self._on_doc_changed)
        except Exception:  # noqa: BLE001 — never in the host's way
            compat.log_error("project tab closed")

    def refresh(self) -> None:
        if not self.alive or not self.active:
            return
        self._ensure_floatable()           # (the host takes it off at times)
        doc = self.doc()
        done, system = self._done(doc), doc["system"]
        path = order(system)
        if not reachable(self.current, done, system):
            self._enter(next_open(done, system))
        if self.element not in PHASES[self.current].elements \
                and self.element not in TOOLS.elements:   # (a tool: kept)
            self.element = PHASES[self.current].elements[0]
            self.method = None

        rows = []
        for key in path:
            if key == self.current:
                s = "current"
            elif key in done:
                s = "done"
            elif reachable(key, done, system):
                s = "open"
            else:
                s = "locked"
            rows.append((key, PHASES[key].label, s))
        self.hub.fill(rows)
        self._sheets_panel_sync()

        if not 0 <= self.floor < len(doc["levels"]):
            self.floor = self._ground_index(doc)
        self._fill_levels(doc)
        self._apply_parts()          # rebuilt groups keep the «Show»
        self._outline_soon()

        has_methods = self.strip.fill(self.element, self.method)
        # the Project phase's one entry («Edit project…») is its button's
        # menu already — not a panel left open under «Plan view» (his
        # screen, 2026-10-15)
        if self.current == "project" and self.element not in TOOLS.elements:
            has_methods = False
        self._show_piece(self.plan_btn, self.plan_bar, True)
        self._show_piece(self.strip, self.strip_bar, has_methods)
        self._show_piece(self.elbox, self.elbox_bar, True)
        self._show_piece(self.viewbar, self.view_bar, True)
        self._show_piece(self.present_btn, self.present_bar, True)
        self._sync_plan()
        self.props.show_for(self.current, self.element,
                            self.current in done,
                            dict(doc, _has_plot=self.has_plot(doc)))
        self._library_show()
        self._element_options()
        self.layout_floating()
        QTimer.singleShot(0, self.layout_floating)

    def _overlay(self, viewport, painter) -> None:
        """ArchXQ's drawings over the 3D view: the active ArchXQ tool's
        marker, live measurements and 45° guide."""
        if not self.alive:
            return
        self._paint_doc = None
        try:
            self._paint_doc = self.doc()      # once for the whole frame
        except Exception:  # noqa: BLE001 — each drawing reads it itself
            self._paint_doc = None
        try:
            self._overlay_frame(viewport, painter)
        finally:
            self._paint_doc = None

    def _overlay_frame(self, viewport, painter) -> None:
        self._watch_plan(viewport)
        self._watch_view_mark(viewport)
        self._draw_level_sheets(viewport, painter)   # under the rest
        self._draw_standing(viewport, painter)
        tool = getattr(viewport, "active_tool", None)
        # another tool took over (a host tool, another method): the options
        # bar goes with the tool it belonged to (an element's bar stays)
        if isinstance(self.options_for, type) \
                and type(tool) is not self.options_for:
            QTimer.singleShot(0, self.hide_options)
        # the wall's shape icon is lit only while a wall tool is out — it
        # goes dark however the tool ended (Esc, another tool, Plan view)
        # the plan's lock follows the tool (editing frees it), however the
        # tool changed
        locks = self._plan_locks()
        if locks != getattr(self, "_locked_was", None):
            self._locked_was = locks
            QTimer.singleShot(0, self._sync_lock)
        out = self.tool_element()
        if out != getattr(self, "_wall_was_out", None):
            self._wall_was_out = out
            if isinstance(self.options_for, tuple):
                QTimer.singleShot(0, self._refill_options)
        draw = getattr(tool, "draw_overlay", None)
        if callable(draw) and compat.ours(tool):
            try:
                draw(viewport, painter)
            except Exception:  # noqa: BLE001 — never break the host's paint
                paintlog.failed()
        self._grips.draw(viewport, painter)

    GUIDE_INK = "#2f6fbf"          # the guide lines over the plan

    def _draw_plan_guides(self, viewport, painter) -> None:
        """In the plan: IngeTrazo's guide lines drawn ON TOP (his screen,
        2026-10-05: made, but not seen). The host draws them in the scene,
        and in the plan's hidden-line style the plot's surface — at the
        very height they lie on — covers them; perspective got away with
        it. The snap is the host's either way: this is only their ink."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen
        gs = list(getattr(viewport.scene, "guides", None) or [])
        if not gs:
            return
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        pen = QPen(QColor(self.GUIDE_INK), 1.4, Qt.DashLine)
        painter.setPen(pen)
        for g in gs:
            try:
                if getattr(g, "is_line", True):
                    seg = viewport._guide_snap_segment(g)
                    if not seg:
                        continue
                    a = viewport._world_to_pixel(seg[0])
                    b = viewport._world_to_pixel(seg[1])
                    if a and b:
                        painter.drawLine(QPointF(*a), QPointF(*b))
                else:                              # a guide point: a cross
                    p = viewport._world_to_pixel(g.a)
                    if p:
                        x, y = p
                        painter.drawLine(QPointF(x - 6, y), QPointF(x + 6, y))
                        painter.drawLine(QPointF(x, y - 6), QPointF(x, y + 6))
            except Exception:  # noqa: BLE001 — never break the host's paint
                paintlog.failed()
                continue
        painter.restore()

    GRID_STEPS = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0)

    def _draw_plan_grid(self, viewport, painter) -> None:
        """In the plan: a faint grid (its step follows the zoom: never
        under 14 px; every 5th line stronger) and the red / green axes
        through the origin — the empty plan had nothing to go by (his
        screen, 2026-10-02: a plot drawn far from the origin)."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen

        from . import prefs
        if not prefs.get("plan_grid"):
            return
        try:
            cam = viewport.camera
            tx, ty = float(cam.target.x()), float(cam.target.y())
            o = compat.to_pixel(viewport, tx, ty, 0.0)
            e = compat.to_pixel(viewport, tx + 1.0, ty, 0.0)
            if not o or not e:
                return
            ppm = math.dist(o, e)                    # pixels per metre
            if ppm <= 1e-6:
                return
            w, h = viewport.width(), viewport.height()
            x0 = tx + (0 - o[0]) / ppm
            x1 = tx + (w - o[0]) / ppm
            y1 = ty + (o[1] - 0) / ppm               # screen y runs down
            y0 = ty + (o[1] - h) / ppm
            step = next((s for s in self.GRID_STEPS if s * ppm >= 14),
                        self.GRID_STEPS[-1])
            # the stronger lines on whole metres: 1 m (his ask: the big
            # squares a metre), then 5, 10, 50…
            big = next((m for m in (1.0, 5.0, 10.0, 50.0, 100.0, 500.0)
                        if m >= step * 2 - 1e-9), 1000.0)
            every = max(1, int(round(big / step)))

            def sx(x):
                return o[0] + (x - tx) * ppm

            def sy(y):
                return o[1] - (y - ty) * ppm
            painter.save()
            minor = QPen(QColor(120, 128, 140, 38), 1.0)
            major = QPen(QColor(120, 128, 140, 80), 1.0)
            k0, k1 = math.floor(x0 / step), math.ceil(x1 / step)
            for k in range(k0, k1 + 1):
                painter.setPen(major if k % every == 0 else minor)
                painter.drawLine(QPointF(sx(k * step), 0),
                                 QPointF(sx(k * step), h))
            k0, k1 = math.floor(y0 / step), math.ceil(y1 / step)
            for k in range(k0, k1 + 1):
                painter.setPen(major if k % every == 0 else minor)
                painter.drawLine(QPointF(0, sy(k * step)),
                                 QPointF(w, sy(k * step)))
            # the axes and the origin
            painter.setPen(QPen(QColor(215, 60, 50, 170), 1.6))
            painter.drawLine(QPointF(0, sy(0.0)), QPointF(w, sy(0.0)))
            painter.setPen(QPen(QColor(40, 160, 70, 170), 1.6))
            painter.drawLine(QPointF(sx(0.0), 0), QPointF(sx(0.0), h))
            painter.setPen(QPen(QColor(40, 44, 52, 200), 1.4))
            painter.drawEllipse(QPointF(sx(0.0), sy(0.0)), 5, 5)
            painter.restore()
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    def _draw_hidden_columns(self, viewport, painter) -> None:
        """In the plan, the columns FITTED inside the walls (hidden there,
        their lines showed through) as a plan draws columns: filled. Seen
        2026-10-02: one placed on a wall vanished — he took it as not made."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QBrush, QColor, QPen, QPolygonF

        from . import structure as S
        if "structure" in self.hidden_parts:
            return
        try:
            doc = self.doc()
            levels = doc["levels"]
            if not 0 <= self.floor < len(levels):
                return
            lv = levels[self.floor]
            if not compat.layer_visible(viewport,
                                        compat.level_layer(lv["name"])):
                return
            # (seen from above, at the walls' top)
            top = S.levels_info(doc, model.elevations)[lv["id"]]["under"]
            painter.save()
            painter.setRenderHint(painter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor(40, 44, 52), 1.2))
            painter.setBrush(QBrush(QColor(90, 96, 105, 200)))
            walls = [w for w in doc["walls"] if w["level"] == lv["id"]]
            for c in doc.get("structure") or []:
                if c["type"] != "column" or c["level"] != lv["id"] \
                        or not S.in_one_wall(c, walls):
                    continue
                pts = [compat.to_pixel(viewport, x, y, top)
                       for x, y in S.column_outline(c, 0.0)]
                if all(pts):
                    painter.drawPolygon(QPolygonF([QPointF(*p)
                                                   for p in pts]))
            painter.restore()
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    GHOST_INK = "#6fa8dc"       # the level below, faint

    def _draw_ghost_level(self, viewport, painter) -> None:
        """In the plan: the levels whose ghost is on (not the one worked
        on), their outlines in light blue — seen, never picked."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen
        from . import structure as S
        try:
            # without what was deleted with the host's tools (his screen,
            # 2026-10-23: a stair erased went on showing in the ghost)
            doc = self._live(self.doc())
            levels = doc["levels"]
            if not 0 <= self.floor < len(levels):
                return
            here = TERRAIN_ROW if self.terrain_current \
                else levels[self.floor]["id"]
            ghosts = [r["id"] for r in levels
                      if r["id"] in (doc.get("ghosts") or ()) and
                      r["id"] != here]
            terrain = TERRAIN_ROW in (doc.get("ghosts") or ()) \
                and here != TERRAIN_ROW
            if not ghosts and not terrain:
                return
            cache = getattr(self, "_ghost_cache", {})
            loops = []
            marks = []                 # its doors' / windows' plan symbols
            if terrain:                # the plot, its pits, the streets
                key = (repr((doc.get("plot") or {}).get("corners")),
                       repr([g.get("corners") for g in doc.get("digs")
                             or []]),
                       repr([e for e in doc.get("structure") or []
                             if e.get("type") == "street"]))
                if cache.get(TERRAIN_ROW, (None,))[0] != key:
                    cache[TERRAIN_ROW] = (key, self._terrain_loops(doc), [])
                loops += cache[TERRAIN_ROW][1]
            for lid in ghosts:
                walls = {e["id"]: e for e in doc.get("walls") or []
                         if e["level"] == lid}
                ops = [o for o in doc.get("openings") or []
                       if o.get("wall") in walls]
                key = (repr(list(walls.values())),
                       repr([e for e in doc.get("structure") or []
                             if e["level"] == lid]), repr(ops))
                if cache.get(lid, (None,))[0] != key:
                    cache[lid] = (key, S.level_plan_loops(doc, lid),
                                  self._ghost_marks(walls, ops))
                loops += cache[lid][1]
                marks += cache[lid][2]
            self._ghost_cache = cache
            # their corners and edges pull the tools' cursor (plottools)
            from . import plottools as _PT
            _PT.GHOST["loops"] = loops
            z = model.elevations(levels, doc["project"]["ground_level"]
                                 if model.has_project(doc) else 0.0)[
                self.floor]
            painter.save()
            painter.setRenderHint(painter.RenderHint.Antialiasing)
            ink = QColor(self.GHOST_INK)
            ink.setAlpha(190)
            painter.setPen(QPen(ink, 1.2))
            for loop in loops:
                px = [compat.to_pixel(viewport, p[0], p[1], z) for p in loop]
                for a, b in zip(px, px[1:] + px[:1]):
                    if a and b:
                        painter.drawLine(QPointF(*a), QPointF(*b))
            # its doors and windows, as the plan draws the current level's
            # (his screen, 2026-10-23: Level 1's doors missing in its ghost)
            for a, b in marks:
                pa = compat.to_pixel(viewport, a[0], a[1], z)
                pb = compat.to_pixel(viewport, b[0], b[1], z)
                if pa and pb:
                    painter.drawLine(QPointF(*pa[:2]), QPointF(*pb[:2]))
            painter.restore()
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    @staticmethod
    def _terrain_loops(doc: dict) -> list:
        """The Terrain's ghost: the plot's outline, its excavations' and
        fills', the streets' (asphalt and sidewalks)."""
        loops = []
        plot = doc.get("plot") or {}
        if plot.get("corners"):
            loops.append([tuple(p[:2]) for p in plot["corners"]])
        for g in doc.get("digs") or []:
            if g.get("corners"):
                loops.append([tuple(p[:2]) for p in g["corners"]])
        sts = [e for e in doc.get("structure") or []
               if e.get("type") == "street"]
        if sts:
            try:
                from . import streets as SR       # (Pro)
                by_level: dict = {}
                for e in sts:
                    by_level.setdefault(e["level"], []).append(e)
                for mine in by_level.values():
                    for sh in SR.shapes(mine, doc.get("plot")).values():
                        for part in ("road", "walk", "curb"):
                            for poly in SR._polys(sh[part]):
                                loops.append(list(poly.exterior.coords)[:-1])
            except Exception:  # noqa: BLE001 — the Lite, or none drawn
                pass
        return loops

    @staticmethod
    def _ghost_marks(walls: dict, ops: list) -> list:
        """The plan symbols (``openingtools.symbol_lines``) of a ghost
        level's doors and windows — [] if one cannot be read."""
        from . import openingtools as OT
        from . import walls as W
        out = []
        for o in ops:
            w = walls.get(o.get("wall"))
            if w is None or w.get("kind", "line") != "line":
                continue
            try:
                out += OT.symbol_lines(o, w, W.centre(w))
            except Exception:  # noqa: BLE001 — a ghost never breaks
                continue
        return out

    SELECT_INK = "#e8742c"      # ArchXQ's elements picked: their edges

    def _draw_selected(self, viewport, painter) -> None:
        """ArchXQ's elements SELECTED: their hard edges drawn bold, in the
        accent orange over a light halo — the host's thin blue outline
        drowned among the guide lines (his screen, 2026-10-09: a ramp, a
        stair, a slab picked in the plan could hardly be seen). In the PLAN
        only: in 3D it is drawn over everything, the hidden edges too, and
        hid the model (his screen, 2026-10-09) — the host's own there."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen
        if not self.plan_on:
            return
        try:
            sel = [g for g in compat.selected_groups(viewport)
                   if compat.kind_of(g) in compat.BUILT_KINDS
                   and not g.hidden]
            if not sel:
                return
            segs = []
            for g in sel:
                for e in g.mesh.edges:
                    if getattr(e, "soft", False) or getattr(e, "hidden",
                                                            False):
                        continue
                    a, b = e.v0.position, e.v1.position
                    pa = compat.to_pixel(viewport, a.x(), a.y(), a.z())
                    pb = compat.to_pixel(viewport, b.x(), b.y(), b.z())
                    if pa and pb:
                        segs.append((QPointF(*pa), QPointF(*pb)))
            painter.save()
            painter.setRenderHint(painter.RenderHint.Antialiasing)
            halo = QColor(255, 255, 255, 150)
            for color, width in ((halo, 5.0), (QColor(self.SELECT_INK), 2.4)):
                painter.setPen(QPen(color, width))
                for pa, pb in segs:
                    painter.drawLine(pa, pb)
            painter.restore()
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    HIDDEN_INK = "#3b4048"      # what lies under the floor: dashed

    def _draw_hidden_footings(self, viewport, painter) -> None:
        """In the plan, the current level's footings DASHED, on top — as a
        foundation plan draws them (his ask, 2026-10-06: the earth and the
        slab hid them; hidden = dashed, the drawing convention every other
        program follows). Their outline as built."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen
        from . import structure as S
        try:
            doc = self.doc()
            levels = doc["levels"]
            if not 0 <= self.floor < len(levels):
                return
            lv = levels[self.floor]
            if not compat.layer_visible(viewport,
                                        compat.level_layer(lv["name"])) \
                    or "structure" in self.hidden_parts \
                    or "footings" in self._hidden_parts().get(lv["id"], ()):
                return
            struct = doc.get("structure") or []
            key = (lv["id"], repr([e for e in struct
                                   if e["type"] == "footing"]))
            if getattr(self, "_foot_cache", (None,))[0] != key:
                self._foot_cache = (key, S.footing_plans(struct, lv["id"]))
            off = self._hidden_ids()
            z = model.elevations(levels, doc["project"]["ground_level"]
                                 if model.has_project(doc) else 0.0)[
                self.floor]
            painter.save()
            painter.setRenderHint(painter.RenderHint.Antialiasing)
            pen = QPen(QColor(self.HIDDEN_INK), 1.3)
            pen.setDashPattern([6.0, 4.0])
            painter.setPen(pen)
            for fid, loops in self._foot_cache[1]:
                if fid in off:
                    continue
                for loop in loops:
                    px = [compat.to_pixel(viewport, x, y, z) for x, y in loop]
                    for a, b in zip(px, px[1:] + px[:1]):
                        if a and b:
                            painter.drawLine(QPointF(*a), QPointF(*b))
            painter.restore()
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    def _draw_opening_cuts(self, viewport, painter) -> None:
        """The wall CUT at each opening, as a plan at 1.20 m reads (Badis,
        2026-10-14: «the windows don't cut the partition») — seen from
        above, the lintel hid it. Its stretch is painted over in the wall
        top's own colour BEFORE the plan grid (the grid runs on, as on the
        rest of the wall); the symbol comes on top later. Hidden line only
        (X-ray sees through the wall anyway); a high window stays under
        the wall (openingtools.cut_in_plan)."""
        from . import openingtools as OT
        from . import walls as W
        if "openings" in self.hidden_parts:
            return
        style = getattr(viewport, "style_override", None)
        if getattr(style, "face_mode", "") != "hidden_line":
            return
        try:
            doc = self._live(self.doc())   # a deleted door: its hole
            levels = doc["levels"]
            if not 0 <= self.floor < len(levels):
                return
            lid = levels[self.floor]["id"]
            if not compat.layer_visible(viewport, compat.level_layer(
                    levels[self.floor]["name"])):
                return
            z = model.elevations(levels, doc["project"]["ground_level"]
                                 if model.has_project(doc) else 0.0)[
                self.floor]
            walls = {w["id"]: w for w in doc["walls"] if w["level"] == lid}
            quads = []
            for o in doc.get("openings") or []:
                w = walls.get(o["wall"])
                if w is not None and w.get("kind", "line") == "line" \
                        and OT.cut_in_plan(o):
                    quads.append(OT.cut_quad(o, w, W.centre(w)))
            if quads:
                r, g, b = (getattr(style, "front_color", None)
                           or (1.0, 1.0, 1.0))[:3]
                OT.fill_quads(viewport, painter, quads, z,
                              "#%02x%02x%02x" % (round(r * 255),
                                                 round(g * 255),
                                                 round(b * 255)))
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    def _draw_opening_symbols(self, viewport, painter) -> None:
        """In the plan, the current level's openings as a plan draws them
        (jambs, glass, a door's leaf and swing) — the walls' tops hide the
        openings themselves from above. Lines only, over the view."""
        from . import openingtools as OT
        from . import walls as W
        if "openings" in self.hidden_parts:
            return
        try:
            # a door / window deleted in the host: drawn as its hole
            doc = self._live(self.doc())
            levels = doc["levels"]
            if not 0 <= self.floor < len(levels):
                return
            lid = levels[self.floor]["id"]
            if not compat.layer_visible(viewport, compat.level_layer(
                    levels[self.floor]["name"])):
                return
            z = model.elevations(levels, doc["project"]["ground_level"]
                                 if model.has_project(doc) else 0.0)[
                self.floor]
            walls = {w["id"]: w for w in doc["walls"] if w["level"] == lid}
            lines = []
            for o in doc.get("openings") or []:
                w = walls.get(o["wall"])
                if w is not None and w.get("kind", "line") == "line":
                    lines += OT.symbol_lines(o, w, W.centre(w))
            # the glass grids of this level: their frame, glass, muntins
            # (his test, 2026-10-15: a filled Opening looked empty)
            grids = [e for e in doc.get("structure") or []
                     if e.get("type") == "glazing" and e.get("level") == lid]
            if grids and not edition.lite():
                try:
                    from . import glazing as GZ
                    for e in grids:
                        lines += GZ.plan_lines(e, doc, lambda _l: z)
                except ImportError:
                    pass
            # the gates in the low walls / the plot's wall: leaf and swing,
            # or a sliding one's leaf and run (Pro — empty gaps before)
            gated = [e for e in doc.get("structure") or []
                     if e.get("type") == "guard" and e.get("level") == lid
                     and e.get("gates")]
            if gated and not edition.lite():
                try:
                    from . import guards as GD
                    wu = GD.walls_union(list(walls.values()))
                    for e in gated:
                        lines += GD.gate_plan_lines(e, wu)
                except ImportError:
                    pass
            if lines:
                OT.draw_lines(viewport, painter, lines, z, OT.PLAN_INK, 1.3)
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    def _draw_standing(self, viewport, painter) -> None:
        """Dimensions of what is already drawn, per the Settings."""
        from . import plottools, prefs
        if not self.active:
            return
        if self.plot_preview is not None:       # the plot table is open
            corners, heights, closing, active = self.plot_preview
            try:
                plottools.draw_plot_preview(viewport, painter, corners,
                                            heights, closing, PLOT_Z, active,
                                            dims=self.dims_on("plot_dims"))
                if self.dims_on("plot_elev_dims"):   # the heights being typed
                    plottools.draw_plot_elevations(viewport, painter,
                                                   corners, heights, PLOT_Z)
            except Exception:  # noqa: BLE001 — never break the host's paint
                paintlog.failed()
            return
        if self.dig_preview is not None:        # the Excavation window
            corners, ground, active, bots, *more = self.dig_preview
            fill = bool(more and more[0])
            try:
                plottools.draw_plot_preview(viewport, painter, corners,
                                            ground, None, PLOT_Z, active,
                                            dims=self.dims_on("dig_dims"))
                if bots and self.dims_on("dig_elev_dims"):
                    for q, b, g in zip(corners, bots, ground):
                        z = max(b, g) if fill else min(b, g)
                        if abs(g - z) >= 0.005:
                            plottools.draw_spot(viewport, painter, q[0], q[1],
                                                z, plottools.elev_text(z),
                                                plottools.DIG_INK)
            except Exception:  # noqa: BLE001 — never break the host's paint
                paintlog.failed()
            return
        if getattr(self, "survey_preview", None) is not None:
            points, active, *more = self.survey_preview  # the Survey window
            try:
                doc = self.doc()
                if self.has_plot(doc):
                    if self.dims_on("contour_dims"):
                        plottools.draw_contours(viewport, painter,
                                                doc["plot"], PLOT_Z,
                                                more[0] if more else None,
                                                points)
                    plottools.draw_survey(viewport, painter, doc["plot"],
                                          PLOT_Z, active, points)
            except Exception:  # noqa: BLE001 — never break the host's paint
                paintlog.failed()
            return
        if self.setback_preview is not None:    # the Setbacks window is open
            p, active = self.setback_preview
            try:
                plottools.draw_plot_preview(viewport, painter, p["corners"],
                                            p["heights"], None, PLOT_Z,
                                            active,
                                            dims=self.dims_on("plot_dims"))
                if self.view_on("setbacks") or (
                        self.current == "terrain"
                        and self.element == "setbacks"):
                    plottools.draw_setbacks(
                        viewport, painter, p, PLOT_Z,
                        dims=self.dims_on("setback_dims"))
            except Exception:  # noqa: BLE001 — never break the host's paint
                paintlog.failed()
            return
        if not self.terrain_current and self.plan_on:
            # the CAD drawing is traced over in the PLAN; in 3D it only
            # floated over the model (his demo house, 2026-10-09)
            self._draw_underlay(viewport, painter)
        if self.plan_on:
            if not self.terrain_current:
                self._draw_opening_cuts(viewport, painter)
            self._draw_plan_grid(viewport, painter)
            self._draw_plan_guides(viewport, painter)
        from . import plottools as _PT
        _PT.GHOST["loops"] = []          # (refilled by the ghost, plan only)
        if self.plan_on and not self.terrain_current:
            self._draw_hidden_footings(viewport, painter)
            self._draw_hidden_columns(viewport, painter)
            self._draw_room_tint(viewport, painter)
            # the ghost OVER the rooms' tint (his screen, 2026-10-26: the
            # stairs of Level 2 seen from Level 3 were washed out under it)
            self._draw_ghost_level(viewport, painter)
            self._draw_separators(viewport, painter)
            self._draw_opening_symbols(viewport, painter)
            self._draw_room_labels(viewport, painter)
            self._draw_plan_dims(viewport, painter)
        if self.plan_on:
            # the Terrain too: one cut through the whole building, seen
            # and moved from any level (his call, 24/10)
            self._draw_section_lines(viewport, painter)
        if not self.plan_on and self.element == "separator":
            self._draw_separators(viewport, painter)   # (3D: while on them)
        self._draw_selected(viewport, painter)
        self._draw_void_picked(viewport, painter)
        if getattr(getattr(viewport, "active_tool", None), "draws_plot",
                   False):
            return                 # the tool draws the plot its own way
        if self.plan_on and not self.terrain_current:
            # a level's plan: the Terrain's figures are not of it (his rule,
            # 2026-10-26: «o nível é soberano» — its windows still draw them
            # while open, above) — but its OWN excavations' are (07/11/2026:
            # the pit is the basement's; footings are drawn seeing it)
            self._draw_level_dig_dims(viewport, painter)
            return
        doc = self.doc()
        if not self.has_plot(doc) or not compat.layer_visible(
                viewport, compat.TERRAIN_LAYER):
            return                 # no plot, or the Terrain is hidden
        try:
            if self.dims_on("contour_dims"):          # under everything else
                plottools.draw_contours(viewport, painter, doc["plot"],
                                        PLOT_Z)
            if self.dims_on("plot_dims"):
                plottools.draw_plot_dims(viewport, painter,
                                         doc["plot"]["corners"],
                                         doc["plot"]["heights"], PLOT_Z)
            if self.dims_on("dig_dims"):
                plottools.draw_dig_dims(viewport, painter, doc, PLOT_Z)
            if self.dims_on("plot_elev_dims"):
                plottools.draw_plot_elevations(viewport, painter,
                                               doc["plot"]["corners"],
                                               doc["plot"]["heights"], PLOT_Z)
            if self.dims_on("dig_elev_dims"):
                plottools.draw_dig_elevations(viewport, painter, doc, PLOT_Z)
            # the survey points: by their switch, and always while working
            # on them (Terrain › Survey points)
            if self.dims_on("survey_dims") or (
                    self.current == "terrain" and self.element == "survey"):
                plottools.draw_survey(viewport, painter, doc["plot"], PLOT_Z)
            # the buildable area: by its switch (off by default, his ask
            # 2026-10-16), and always while working on it (Terrain ›
            # Setbacks); its figures have their own switch
            if doc["view"].get("setbacks", False) or (
                    self.current == "terrain" and self.element == "setbacks"):
                plottools.draw_setbacks(viewport, painter, doc["plot"],
                                        PLOT_Z,
                                        dims=self.dims_on("setback_dims"))
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    def _draw_level_dig_dims(self, viewport, painter) -> None:
        """In a level's plan: the figures of the excavations that belong to
        it (``terrain.dig_levels``) — their sides and depth, their floor's
        elevation — by the same switches as on the Terrain."""
        try:
            from . import plottools, terrain
            doc = self.doc()
            if not self.has_plot(doc) or not doc.get("digs"):
                return
            lid = doc["levels"][self.floor]["id"]
            mine = [d for d in doc["digs"]
                    if lid in terrain.dig_levels(d, doc)]
            if not mine:
                return
            part = dict(doc, digs=mine)
            if self.dims_on("dig_dims"):
                plottools.draw_dig_dims(viewport, painter, part, PLOT_Z)
            if self.dims_on("dig_elev_dims"):
                plottools.draw_dig_elevations(viewport, painter, part,
                                              PLOT_Z)
        except Exception:  # noqa: BLE001 — never break the host's paint
            paintlog.failed()

    # ---- Placement of the floating pieces ------------------------------------------
    def _show_piece(self, widget, bar, on: bool) -> None:
        if bar is not None:
            bar.setVisible(on)
        else:
            widget.setVisible(on)
        # the levels strip's tab: there while ArchXQ is on and the strip
        # is hidden by N (not while presenting / switched off)
        if widget is getattr(self, "levels", None) and \
                hasattr(self, "levels_tab"):
            self._show_piece(self.levels_tab, self.levels_tab_bar,
                             self.active and (self._framed
                                              or not self.levels_open))

    def layout_floating(self) -> None:
        """"viewport" placement: hub top-left, strip under it on the left,
        view bar centred at the bottom."""
        if not self.alive or self.placement != "viewport" or self._frame_busy:
            return
        self._sync_frame()
        # the view — or, with several views, the grid: the same placing on
        # the whole area, and the views kept out of the bands (below)
        vp = self._ui_parent or self.viewport
        framed = self._framed
        # another extension's bar in this corner: under it, not over it
        hub_y = foreignbars.top_inset(
            vp, QRect(MARGIN, MARGIN, self.hub.width(), self.hub.row.height()),
            MARGIN, getattr(self, "_watch", None))
        self._hub_scroll.place(MARGIN, hub_y, vp.width() - 2 * MARGIN,
                               self.hub.row.width(), self.hub.row.height())
        top_row = hub_y + self.hub.row.height() + MARGIN
        # the plan view switch on its own, then the drawing methods under it
        self.plan_btn.ensurePolished()
        self.plan_btn.adjustSize()
        self.plan_btn.move(MARGIN, top_row)
        y = top_row + self.plan_btn.height() + MARGIN
        # the plan / elevations icons right BESIDE it, while it is on — one
        # piece with it, not a new item (his call, 2026-10-10)
        if self.views.isVisible():
            self.views.adjustSize()
            self.views.move(MARGIN + self.plan_btn.width() + 4,
                            top_row + (self.plan_btn.height()
                                       - self.views.height()) // 2)
        self.strip.layout().activate()       # its new buttons, measured
        self.strip.resize(self.strip.sizeHint())
        self.strip.move(MARGIN, y)
        # the «Building elements» under the methods (under the plan switch
        # when no methods show), a gap between: another section
        self.elbox.adjustSize()
        below = (self.strip.y() + self.strip.height()) \
            if self.strip.isVisible() else y - MARGIN
        self.elbox.move(MARGIN, below + 2 * MARGIN)
        self.viewbar.adjustSize()
        self.present_btn.adjustSize()
        lead = (self.present_btn.width() + 10
                if not self.present_btn.isHidden() else 0)
        bar_x = max(MARGIN + lead, (vp.width() - self.viewbar.width()) // 2)
        bar_y = vp.height() - self.viewbar.height() - MARGIN
        self._viewbar_scroll.place(bar_x, bar_y, vp.width() - bar_x - MARGIN,
                                   self.viewbar.width(), self.viewbar.height())
        # «Present» on its own, left of the Show bar, its middle on the bar's
        self.present_btn.move(
            max(MARGIN, bar_x - self.present_btn.width() - 10),
            bar_y + (self.viewbar.height() - self.present_btn.height()) // 2)
        self.present_btn.raise_()
        # options: under the phases row, beside the left column
        left = max(self.plan_btn.width() if self.plan_btn.isVisible() else 0,
                   self.plan_btn.width() + 4 + self.views.width()
                   if self.views.isVisible() else 0,
                   self.strip.width() if self.strip.isVisible() else 0,
                   self.elbox.width() if self.elbox.isVisible() else 0)
        x = MARGIN + (left + MARGIN if left else 0)
        tab = getattr(self, "levels_tab", None)
        if framed:
            # around the views: the options in the row under the phases,
            # right of the plan switch; the methods and elements under it
            tab.adjustSize()
            x = MARGIN + self.plan_btn.width() + MARGIN
            if not self.views.isHidden():
                x += self.views.width() + 4
            self.optbar.max_width = vp.width() - x - tab.width() - 3 * MARGIN
        else:
            self.optbar.max_width = vp.width() - x - MARGIN   # rows past this
        self.optbar.fit()
        self.optbar.move(x, top_row)
        band = 0                 # framed: where the views start
        if framed:
            band = top_row + max(
                self.plan_btn.height(),
                self.views.height() if not self.views.isHidden() else 0,
                self.optbar.height() if not self.optbar.isHidden() else 0
            ) + MARGIN
            col = max(self.strip.width() if not self.strip.isHidden() else 0,
                      self.elbox.width() if not self.elbox.isHidden() else 0)
            self._frame_left = MARGIN + (col + MARGIN if col else 0)
            viewframe.set_margins(vp, self._frame_left, band, MARGIN,
                                  self.viewbar.height() + 2 * MARGIN)
        # levels: right edge, under the phases row, clear of the view bar —
        # and under the options bar when a long one reaches it (the
        # column's bar ran under the strip, «As drawn» hidden)
        top = band or top_row
        self.levels.fit()
        if not framed and self.optbar.isVisible() and \
                x + self.optbar.width() > \
                vp.width() - self.levels.width() - 2 * MARGIN:
            top = top_row + self.optbar.height() + MARGIN
        self.levels.max_height = max(
            120, vp.height() - top - self.viewbar.height() - 3 * MARGIN)
        self.levels.fit()
        self.levels.move(vp.width() - self.levels.width() - MARGIN, top)
        if tab is not None:
            tab.adjustSize()
            tab.move(vp.width() - tab.width() - MARGIN,
                     top_row if framed else top)
            tab.raise_()
        if framed:
            self.levels.raise_()
        self.optbar.raise_()
        self.hub.raise_()             # the hover submenu stays on top

    # ---- Teardown (dev reload) -------------------------------------------------------
    def teardown(self) -> None:
        self._remember_opts()
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.instance().aboutToQuit.disconnect(
                self._remember_opts)
        except Exception:  # noqa: BLE001 — never connected
            pass
        self._follow_tab()          # (its watchers come off the view in front)
        if self._home is not None and self._ui_parent is not self._home:
            self._move_pieces(self._home, False)   # the views' margins back
        if self._extras_of is not None:
            try:
                self._watch_extras(self._extras_of, False)
            except RuntimeError:     # (its project tab is gone)
                pass
        self.alive = False
        compat.watch_commands(None)
        from .updater import Notice
        for n in self.viewport.findChildren(Notice):
            n.deleteLater()
        _docs = _pro_module("docs")
        if _docs is not None:
            _docs.full_geometry(self.viewport, False)  # host's fast path back
        compat.lock_orbit(self.viewport, False)    # the host's orbit back
        compat.plan_style(self.viewport, False)    # and the file's style
        compat.remove_ext_menu(getattr(self, "menu", None))
        compat.remove_overlay(self.viewport, self._overlay)
        compat.restore_snap_reach(self.viewport)
        compat.remove_context_menu(self.viewport, self._context_menu)
        self._outline_timer.stop()
        try:
            self.viewport.sceneVersionChanged.disconnect(self._outline_soon)
        except (RuntimeError, TypeError):
            pass
        self.viewport.removeEventFilter(self._watch)
        self.viewport.removeEventFilter(self._keys)
        self.viewport.removeEventFilter(self._present_esc)
        self.window.removeEventFilter(self._present_esc)
        self.viewport.removeEventFilter(self._tool_esc)
        self.window.removeEventFilter(self._tool_esc)
        self.viewport.removeEventFilter(self._space_pan)
        self.window.removeEventFilter(self._space_pan)
        self.window.removeEventFilter(self._reaper)
        if getattr(self, "_clean_act", None) is not None:
            try:
                self._clean_act.toggled.disconnect(self._clean_keys)
            except (RuntimeError, TypeError):
                pass
            self._clean_keys(False)
        self.viewport.removeEventFilter(self._dbl)
        self.viewport.removeEventFilter(self._pickthru)
        self.quick.teardown()
        self._quick_key.setEnabled(False)
        self._quick_key.deleteLater()
        self._grips.cancel()
        self.viewport.removeEventFilter(self._grips)
        self.viewport.removeEventFilter(self._sec_filter)
        compat.remove_pickable(self.app, self.viewport)
        if getattr(self, "_marks_off", None) is not None or \
                getattr(self, "_cut3d", None) is not None:
            self.active = self.presenting = False   # (the host's marks back)
            self._host_marks_sync()
        self.viewport.removeEventFilter(self._radial_watch)
        self.radial.hide()
        self.radial.deleteLater()
        self._radial_key.setEnabled(False)
        self._radial_key.deleteLater()
        from . import style as _style
        _style.remove_theme_guard()
        if self._lib_dark in _style.EXTRA:
            _style.EXTRA.remove(self._lib_dark)
        self.viewport.removeEventFilter(self._nkey)
        self.window.removeEventFilter(self.hub)
        self.hub.sub.hide()
        self.hub.sub.deleteLater()
        for widget, bar in ((self.hub, self.hub.bar),
                            (self.plan_btn, self.plan_bar),
                            (self.views, self.views_bar),
                            (self.strip, self.strip_bar),
                            (self.elbox, self.elbox_bar),
                            (self.viewbar, self.view_bar),
                            (self.present_btn, self.present_bar),
                            (self.levels, self.levels_bar),
                            (self.levels_tab, self.levels_tab_bar),
                            (self.optbar, self.opt_bar)):
            widget.hide()
            compat.remove_toolbar(self.window, bar)
            widget.deleteLater()
        compat.remove_dock(self.window, self._dock)
        self.viewport.update()
