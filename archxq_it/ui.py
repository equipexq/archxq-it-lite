"""ArchXQ — the conductor.

Screen plan (the user's):
    TOP     phases, horizontal; each phase's elements drop under it on hover
    LEFT    how to draw the picked element (its methods / actions)
    RIGHT   the picked element's properties (a tab of the side tray)
    BOTTOM  what is shown and how: floors, parts, view, camera

The «⏻ ArchXQ» switch is sovereign: off, every ArchXQ piece goes away
and the user works in plain IngeTrazo; the model is never touched.

One content, two placements (``⇅`` swaps them, remembered):
    "viewport" — the pieces float over the 3D view
    "toolbar"  — the pieces sit in bars of their own around the 3D view

Document: ``model.load`` / ``save`` (project, levels, system, done).
Session: on/off, placement, phase, element, method, floor.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QObject, QSettings, Qt, QTimer

from . import compat, edition, model
from .hub import Hub
from .levelstrip import LevelStrip
from .panels import ElementsBox, PropsPanel, SideStrip, ViewBar
from .phases import ELEMENTS, PHASES, is_pro, next_open, order, reachable
from .style import BAR_CSS

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
#: the structure's shapes, in their options bars: (value, icon, tip)
COLUMN_SHAPES = [
    ("single", "col_single", "Stamp columns — it rides the cursor: each "
                             "click places one (Esc = done)"),
    ("draw", "rectangle", "Draw a column — two opposite corners: its size "
                          "and its place (the size is kept for the next)"),
    ("row", "col_row", "A row of columns — click the first and the last "
                       "(by count or spacing, ends in or out; the last row "
                       "follows the bar until the next one)"),
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
    ("hole", "slab_hole", "Opening in a slab — draw a rectangle inside it "
                          "(a stair, a lift, a void)"),
]
FOOTING_SHAPES = [
    ("pads", "foot_pads", "Under the columns — one click: a pad under "
                          "every column of this level"),
    ("strips", "foot_strips", "Under the walls — one click: a strip "
                              "footing under every wall of this level"),
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
                            "level's walls (a pitched one over the rectangle "
                            "round them)"),
    ("rect", "rectangle", "Rectangle — corner to corner"),
    ("rect_c", "rectangle_center", "Rectangle from its centre"),
    ("rect_r", "rotated_rect", "Rotated rectangle"),
    ("chain", "geopath", "Point by point (a pitched roof takes the "
                         "rectangle round it)"),
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
    ("load", "io", "Load a DXF plan onto the current level — a reference "
                   "drawn over the view (the model is not changed)"),
    ("make", "beam_walls", "Make the walls from its lines: each pair of "
                           "parallel lines (thickness between Min and Max) "
                           "is a wall; a gap in its lines, an opening"),
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
                  ("footing", "strips"), ("roof", "walls")}
LEVELS_KEY = Qt.Key_N               # shows / hides the levels strip
TERRAIN_ROW = "terrain"             # the levels strip's row at the ground


class _Watch(QObject):
    """Re-place the floating pieces when the 3D view is resized."""

    def __init__(self, fn) -> None:
        super().__init__()
        self.fn = fn

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Resize:
            QTimer.singleShot(0, self.fn)
        return False


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
            if (type(tool).__module__.startswith("archxq_it")
                    and event.key() in keys
                    and event.modifiers() == Qt.NoModifier):
                event.accept()
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


class _PlotDoubleClick(QObject):
    """Double-click on the plot (Select tool out) opens the plot table
    instead of the host's group editing."""

    def __init__(self, owner) -> None:
        super().__init__()
        self.owner = owner

    def eventFilter(self, obj, event) -> bool:
        o = self.owner
        if (event.type() == QEvent.MouseButtonDblClick
                and event.button() == Qt.LeftButton
                and o.alive and o.active and compat.selecting(o.viewport)):
            doc = o.doc()
            p = event.position()
            hit = compat.group_at(o.viewport, p.x(), p.y())
            wall = o.wall_of(hit) if hit is not None else None
            if wall is not None:                    # a wall: its window
                QTimer.singleShot(0, lambda: o.edit_wall(wall))
                return True
            el = o.element_of(hit) if hit is not None else None
            if el is not None:                      # column, beam, slab…
                QTimer.singleShot(0, lambda: o.edit_element(el))
                return True
            op = o.opening_of(hit) if hit is not None else None
            if op is not None:                      # a door, a window
                QTimer.singleShot(0, lambda: o.edit_opening(op))
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


class ArchXQ:
    def __init__(self, app, placement: str | None = None) -> None:
        placement = placement or str(
            QSettings().value("archxq/placement", "viewport"))
        if placement not in ("viewport", "toolbar"):
            placement = "viewport"
        self.placement = placement
        self.app = app
        self._loader_key = compat.own_key(app)   # data always under "archxq"
        self.window = app.window
        self.viewport = app.viewport
        _docs = _pro_module("docs")
        # the sheets' drawings from the WHOLE model (the host's fast path
        # held a part of it — see docs.full_geometry); the Lite makes none
        if _docs is not None:
            _docs.full_geometry(self.viewport, True)
        self.alive = True
        self.active = False
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

        # RIGHT — a tab of the side tray: the outliner above, the picked
        # element's properties below (Blender's arrangement); the divider
        # is dragged and remembered
        from PySide6.QtWidgets import QSplitter
        from .outliner import Outliner
        self.props = PropsPanel(self)
        self.outliner = Outliner(self)
        self._split = QSplitter(Qt.Vertical)
        self._split.setChildrenCollapsible(False)
        self._split.addWidget(self.outliner)
        self._split.addWidget(self.props)
        sizes = QSettings().value("archxq/outliner_split")
        try:
            self._split.setSizes([int(s) for s in sizes])
        except (TypeError, ValueError):
            self._split.setSizes([320, 380])
        self._split.splitterMoved.connect(lambda *_: QSettings().setValue(
            "archxq/outliner_split", self._split.sizes()))
        self._dock = app.add_panel("ArchXQ", self._split)
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
        from .panels import PlanSwitch
        self.plan_btn = PlanSwitch(self)
        self.plan_bar = compat.place(self.viewport, self.plan_btn, placement,
                                     "left", BAR_CSS)
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
                          "height": "level", "h": 2.80}
        # the structure's choices, the same way
        self.col_opts = {"shape": "single", "section": "rect", "w": 0.30,
                         "d": 0.30, "angle": 0.0, "anchor": "centre",
                         "count": 4, "nx": 3, "ny": 3, "height": "level",
                         "h": 3.00, "fit": "fit", "base": 0.0,
                         "by": "count", "spacing": 5.0, "ends": "both"}
        self._last_row = None     # the row last placed: the bar still edits it
        self.beam_opts = {"shape": "chain", "w": 0.20, "h": 0.45,
                          "fit": "fit"}
        self.slab_opts = {"shape": "walls", "t": 0.15, "offset": 0.0}
        self.foot_opts = {"shape": "pads", "w": 1.20, "sw": 0.60, "d": 0.50}
        # the documentation (paper / scale: the project's, to start)
        self.doc_opts = {"paper": None, "scale": "auto", "cut": 1.20,
                         "elev": "yes", "sect": "yes", "dims": "yes",
                         "rooms": "yes", "prefix": "A-"}
        self.room_labels = True          # names + areas in the plan view
        self.dxf_opts = {"tmin": 0.08, "tmax": 0.40}
        self.roof_opts = {"shape": "walls", "kind": "gable", "slope": 30.0,
                          "overhang": 0.50, "t": 0.20, "ridge": "long",
                          "parapet": 1.00, "pt": 0.15}
        # the openings' sizes, per kind (the usual ones to start)
        self.op_opts = {
            "door": {"shape": "wall", "w": 0.90, "h": 2.10, "sill": 0.0,
                     "swing": "left"},
            "window": {"shape": "wall", "w": 1.20, "h": 1.20, "sill": 1.00},
            "void": {"shape": "wall", "w": 1.00, "h": 2.10, "sill": 0.0}}

        # RIGHT (over the 3D view / own bar) — the levels strip, N
        self.levels_open = str(QSettings().value("archxq/levels_open",
                                                 "1")) != "0"
        self.levels = LevelStrip(self)
        self.levels_bar = compat.place(self.viewport, self.levels, placement,
                                       "right", BAR_CSS)
        self._nkey = _LevelsKey(self)
        self.viewport.installEventFilter(self._nkey)
        # over ArchXQ's pieces the pointer is an arrow — not the drawing
        # tool's pencil the 3D view wears (they are its children)
        self._cursor = _ToolCursorBack(self.viewport)
        for w in (self.hub, self.hub.sub, self.plan_btn, self.strip,
                  self.viewbar, self.levels, self.optbar):
            w.setCursor(Qt.ArrowCursor)
            w.installEventFilter(self._cursor)

        # the viewport's right-click menu: ArchXQ ▸ on ArchXQ's objects
        compat.add_context_menu(app, self._context_menu)

        # the host's Extensions menu: ArchXQ ▸ (also found by F3)
        other = "own bars" if placement == "viewport" else "the 3D view"
        self.menu, self.menu_acts = compat.add_ext_menu(app, "ArchXQ", [
            ("ArchXQ environment", lambda: self.hub.power.toggle(),
             "Enter / leave the ArchXQ environment — the model is not "
             "changed", False),
            ("Levels strip\tN", self.toggle_levels_strip,
             "Show / hide the levels strip on the right (N)",
             self.levels_open),
            (f"Move ArchXQ to {other}", lambda: self.set_placement(
                "toolbar" if self.placement == "viewport" else "viewport"),
             "Over the 3D view, or in bars of its own around it", None),
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
        self._dbl = _PlotDoubleClick(self)
        self.viewport.installEventFilter(self._dbl)

        app.on_document_changed(self._on_doc_changed)
        app.add_overlay(self._overlay)
        doc = self.doc()
        self.current = next_open(self._done(doc), doc["system"])
        self.element = PHASES[self.current].elements[0]
        self.floor = self._ground_index(doc)
        active = str(QSettings().value("archxq/active", "1")) != "0"
        self.hub.power.setChecked(active)
        self.set_active(active)

    # ---- The sovereign switch ------------------------------------------------
    def set_active(self, on: bool) -> None:
        if not self.alive:
            return
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
            self.refresh()
        else:
            self._show_piece(self.plan_btn, self.plan_bar, False)
            self._show_piece(self.strip, self.strip_bar, False)
            self._show_piece(self.elbox, self.elbox_bar, False)
            self._show_piece(self.viewbar, self.view_bar, False)
            self._show_piece(self.levels, self.levels_bar, False)
            self.hide_options()
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
        """Phases complete. Project and Terrain check themselves (a project
        exists / a plot exists); the others still use the stand-in button."""
        stored = set(doc["done"]) - AUTO_PHASES
        if model.has_project(doc):
            stored.add("project")
        if self.has_plot(doc):
            stored.add("terrain")
        # each phase's ✔ is its own (the phases guide, they don't lock)
        return {k for k in order(doc["system"]) if k in stored}

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

    def go(self, key: str) -> None:
        if key == self.current or self._blocked(key):
            return
        self.current = key
        self.element = PHASES[key].elements[0]
        self.method = None
        self.refresh()
        if self._dock is not None:
            self._dock.raise_()

    def pick(self, phase: str, element: str) -> None:
        if phase != self.current:
            if self._blocked(phase):
                return
            self.current = phase
        self.element = element
        self.method = None
        self.refresh()
        if self._dock is not None:
            self._dock.raise_()

    def on_method(self, name: str) -> None:
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

    def on_toggle_done(self) -> None:
        doc = self.doc()
        done = self._done(doc)
        if self.current in done:
            done.discard(self.current)      # its own ✔ only
        else:
            done.add(self.current)
        doc["done"] = sorted(done)
        self.save(doc)
        nxt = next_open(done, doc["system"])
        if self.current in done and nxt != self.current:
            self._enter(nxt)
        self.refresh()

    # ---- Terrain: the plot ----------------------------------------------------------
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
        compat.flash(self.viewport, f"Plot drawn — {plotgeo.area(corners):.1f}"
                     " m². The next phases are open.", 6000)
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
        compat.flash(self.viewport, f"Ground: {value:.2f} m deep")
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
        try:
            ok = dlg.exec()
        finally:
            self._preview_plot(None)
        if not ok:
            return
        if getattr(dlg, "action", "apply") == "delete":
            QTimer.singleShot(0, self.delete_plot)      # it asks first
            return
        corners, heights, closing = dlg.result_data()
        # read again: what changed while the window was open (its «Show on
        # the model» boxes write at once) must not be put back
        doc = self.doc()
        compat.commit_plot(self.viewport, self.app.key, doc, corners,
                           PLOT_Z, PLOT_COLOR, doc["plot"]["thickness"],
                           heights, closing, doc["plot"]["breaks"])
        compat.flash(self.viewport, "Plot updated — Ctrl+Z undoes it", 5000)
        self.refresh()
        self._again(dlg, self.edit_plot_table)

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
        if o["bottom"] not in [c[0] for c in choices]:
            o["bottom"] = "depth"                         # 3 m: his default
        opts = []
        if rect:
            opts.append({"key": "align", "label": "Align", "kind": "choice",
                         "value": o["align"],
                         "choices": [("plot", "Plot sides"),
                                     ("axes", "Red / green axes")],
                         "tip": "Square with the plot's sides, or with the "
                                "model's axes"})
        opts.append({"key": "bottom", "label": "Bottom", "kind": "choice",
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

    def start_dig_tool(self, name: str, kind: str = "cut") -> None:
        from . import plottools
        if not self.has_plot(self.doc()):
            compat.flash(self.viewport, "Draw the plot first")
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
                info = (f"It passes the plot's edge by {d:,.2f} m — on the "
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
        corners = terrain.snug(doc, corners)     # drawn onto the boundary
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
                     f"{bottoms[0]:+.2f} → {min(bottoms):+.2f}. Double-click "
                     "it to adjust; Ctrl+Z undoes it", 7000)
        self.refresh()

    def _on_dig_option(self, key: str, value) -> None:
        self._mod_opts()[key] = value
        if key == "bottom":                  # the fields that follow change
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
        corners = terrain.snug(doc, corners)     # drawn onto the boundary
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
        doc["digs"] = doc["digs"] + [dig]
        doc = self._commit_terrain(doc)
        v = compat.dig_volumes(doc).get(dig["id"], 0.0)
        self.method = None
        compat.back_to_select(self.viewport)
        self.hide_options()
        compat.flash(self.viewport, f"«{dig['name']}» "
                     + ("raised" if kind == "fill" else "dug")
                     + f" — {v:,.1f} m³ of earth "
                     + ("brought in" if kind == "fill" else "taken out")
                     + ". Ctrl+Z undoes it", 6000)
        self.refresh()

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
        try:
            ok = dlg.exec()
        finally:
            self._preview_dig(None)
        if not ok:
            return
        action, new = dlg.result_data()
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
                 "text": "Get Pro", "tip": edition.PRO_URL}]

    def _on_pro_option(self, key: str, value) -> None:
        if key == "get":
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
                     "choices": [("yes", "In plan"), ("no", "Hidden")],
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
                    self._on_doc_option)}
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
             "choices": [("level", f"Level height "
                                   f"({self._level_height():.2f} m)"),
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
        return opts

    def _on_wall_option(self, key: str, value) -> None:
        self.wall_opts[key] = value
        if key == "height":                  # the height field comes / goes
            QTimer.singleShot(0, self._refill_options)
        if key == "shape":
            QTimer.singleShot(0, self.start_wall_tool)

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
                             "its line)"},
                     {"key": "anchor", "label": "", "kind": "segments",
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
                             "tip": "The distance between columns, from "
                                    "the first point"})
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
                {"key": "w", "label": "Width", "kind": "len",
                 "value": o["w"], "min": 0.05, "max": 3.0, "step": 0.05},
                {"key": "h", "label": "Height", "kind": "len",
                 "value": o["h"], "min": 0.05, "max": 5.0, "step": 0.05,
                 "tip": "From the underside of the slab above, downwards"},
                {"key": "fit", "label": "In walls", "kind": "segments",
                 "value": o["fit"],
                 "choices": [("fit", "Fit inside"), ("free", "As drawn")],
                 "tip": "Fit inside: a beam along a wall takes its "
                        "thickness and hides in it. As drawn: its own "
                        "width"}]

    def _slab_options(self) -> list[dict]:
        o = self.slab_opts
        return [{"key": "shape", "label": "", "kind": "icons",
                 "value": self._lit("slab", o), "choices": SLAB_SHAPES},
                {"key": "t", "label": "Thickness", "kind": "len",
                 "value": o["t"], "min": 0.02, "max": 3.0, "step": 0.01},
                {"key": "offset", "label": "Top", "kind": "len",
                 "value": o["offset"], "min": -2.0, "max": 2.0,
                 "step": 0.01, "tip": "Its top, from the level's floor (0 = "
                                      "the floor itself)"}]

    def _footing_options(self) -> list[dict]:
        o = self.foot_opts
        return [{"key": "shape", "label": "", "kind": "icons",
                 "value": None, "choices": FOOTING_SHAPES},
                {"key": "w", "label": "Pad", "kind": "len",
                 "value": o["w"], "min": 0.2, "max": 10.0, "step": 0.05,
                 "tip": "A pad's side (never less than its column + 0.20)"},
                {"key": "sw", "label": "Strip", "kind": "len",
                 "value": o["sw"], "min": 0.2, "max": 5.0, "step": 0.05,
                 "tip": "A strip footing's width"},
                {"key": "d", "label": "Depth", "kind": "len",
                 "value": o["d"], "min": 0.1, "max": 5.0, "step": 0.05,
                 "tip": "How deep, under the level's slab"}]

    def _roof_options(self) -> list[dict]:
        o = self.roof_opts
        flat = o["kind"] == "flat"
        opts = [{"key": "shape", "label": "", "kind": "icons",
                 "value": self._lit("roof", o), "choices": ROOF_SHAPES},
                {"key": "kind", "label": "Type", "kind": "segments",
                 "value": o["kind"],
                 "choices": [("gable", "Gable"), ("hip", "Hip"),
                             ("flat", "Flat")],
                 "tip": "Gable: two slopes, a triangle of wall at each end. "
                        "Hip: four slopes. Flat: a slab, with a parapet if "
                        "you like"}]
        if not flat:
            opts.append({"key": "slope", "label": "Slope", "kind": "len",
                         "value": o["slope"], "min": 5.0, "max": 75.0,
                         "step": 5.0, "suffix": "°"})
        opts += [{"key": "overhang", "label": "Overhang", "kind": "len",
                  "value": o["overhang"], "min": 0.0, "max": 3.0,
                  "step": 0.05, "tip": "How far it reaches past the walls"},
                 {"key": "t", "label": "Thickness", "kind": "len",
                  "value": o["t"], "min": 0.02, "max": 1.0, "step": 0.01}]
        if o["kind"] == "gable":
            opts.append({"key": "ridge", "label": "Ridge", "kind": "segments",
                         "value": o["ridge"],
                         "choices": [("long", "Along the long side"),
                                     ("short", "Along the short side")],
                         "tip": "Which way the ridge runs"})
        if flat:
            opts.append({"key": "parapet", "label": "Parapet", "kind": "len",
                         "value": o["parapet"], "min": 0.0, "max": 3.0,
                         "step": 0.05, "tip": "Its height over the roof "
                                              "(0 = none)"})
        return opts

    # ---- Documentation: drawings on the host's sheets ---------------------------------
    def _doc_paper(self) -> str:
        from . import docs
        if self.doc_opts["paper"] in docs.PAPERS:
            return self.doc_opts["paper"]
        p = (self.doc().get("project") or {}).get("paper", "A3")
        return p if p in docs.PAPERS else "A3"

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
                 "choices": [("auto", "Auto"), ("50", "1:50"),
                             ("75", "1:75"), ("100", "1:100"),
                             ("125", "1:125"), ("200", "1:200")],
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
            QTimer.singleShot(0, {"load": self.import_dxf,
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

    def import_dxf(self) -> None:
        """A DXF plan onto the current level, as a reference (one
        Ctrl+Z); the Walls › «Walls from DXF» bar comes up."""
        if self._pro_only("wall_import"):
            return
        import os

        from PySide6.QtWidgets import QApplication, QFileDialog
        from . import importdxf
        base = compat.document_path(self.window)
        start = os.path.dirname(base) if base else os.path.expanduser("~")
        path, _f = QFileDialog.getOpenFileName(
            self.window, "Import a DXF plan", start, "DXF (*.dxf)")
        if not path:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            data = importdxf.placed(importdxf.read(path))
        except Exception as e:  # noqa: BLE001 — say it
            compat.flash(self.viewport, f"DXF not read — {e}", 8000)
            return
        finally:
            QApplication.restoreOverrideCursor()
        if not data["segs"]:
            compat.flash(self.viewport, "No lines in that DXF", 6000)
            return
        doc = self.doc()
        lv, _u = self._underlay(doc)
        layer = next((n for n in data["layers"]
                      if n.upper() in ("A-CUT", "A-WALL", "WALLS", "PAREDES",
                                       "MUROS", "PAREDE")), "")
        doc["underlays"] = dict(doc.get("underlays") or {})
        doc["underlays"][lv["id"]] = {"name": os.path.basename(path),
                                      "layers": data["layers"],
                                      "segs": data["segs"], "layer": layer}
        self.save(doc)
        self.pick("walls", "wall_import")
        self.enter_plan(quiet=True)
        compat.fit_plan(self.viewport, [(s[0], s[1]) for s in data["segs"]]
                        + [(s[2], s[3]) for s in data["segs"]])
        compat.flash(self.viewport, f"«{os.path.basename(path)}» on "
                     f"«{lv['name']}»: {len(data['segs'])} lines, "
                     f"{len(data['layers'])} layers — «Make walls» raises "
                     "them", 8000)

    def walls_from_dxf(self) -> None:
        """The walls (and their openings) from the level's drawing — one
        Ctrl+Z."""
        if self._pro_only("wall_import"):
            return
        from . import importdxf
        doc = self._live(self.doc())
        lv, u = self._underlay(doc)
        if not u:
            compat.flash(self.viewport, "No drawing on this level — load a "
                         "DXF first", 6000)
            return
        li = u["layers"].index(u["layer"]) if u["layer"] else None
        segs = [s for s in u["segs"] if li is None or s[4] == li]
        walls, ops = importdxf.walls_from(segs, self.dxf_opts["tmin"],
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
        for k, pos, width in ops:
            door = width <= importdxf.DOOR_MAX
            orecs.append({"kind": "door" if door else "window",
                          "wall": made[k]["id"], "pos": round(pos, 4),
                          "w": round(width, 3), "h": 2.10 if door else 1.20,
                          "sill": 0.0 if door else 1.00, "swing": "left"})
        doc["openings"] = doc["openings"] + model.new_openings(
            doc["openings"], orecs)
        self._commit_all(doc)
        compat.flash(self.viewport, f"{len(made)} walls and {len(orecs)} "
                     f"openings on «{lv['name']}» — Ctrl+Z undoes them", 7000)

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
            pass

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
        mine = [{"id": "", "level": lv["id"], "x": round(room["at"][0], 4),
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

    def _draw_room_labels(self, viewport, painter) -> None:
        """In the plan: each room's name and area at its middle."""
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QFont

        from . import openingtools as OT
        from . import spaces
        if not self.room_labels:
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
            z = model.elevations(levels, doc["project"]["ground_level"]
                                 if model.has_project(doc) else 0.0)[
                self.floor]
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
            pass

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
        doc["sections"] = doc["sections"] + [
            {"id": _uuid.uuid4().hex[:8], "a": [round(v, 4) for v in a],
             "b": [round(v, 4) for v in b], "flip": bool(flip),
             "symbol": sym}]
        if self.make_sheets(doc, quiet=True):
            compat.flash(self.viewport, f"Section {sym}-{sym} and its sheet "
                         "made — Ctrl+Z undoes it", 6000)

    def clear_sections(self) -> None:
        doc = self._live(self.doc())
        n = len(doc["sections"])
        if not n:
            compat.flash(self.viewport, "No sections drawn", 4000)
            return
        doc["sections"] = []
        if self.make_sheets(doc, quiet=True):
            compat.flash(self.viewport, f"{n} drawn section"
                         f"{'s' if n > 1 else ''} removed — Ctrl+Z brings "
                         "them back", 6000)

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

    def _on_struct_option(self, element: str, key: str, value) -> None:
        o = self._struct_opts(element)
        o[key] = value
        if key in ("section", "height", "kind", "by") or (
                key == "shape" and element == "column"):
            QTimer.singleShot(0, self._refill_options)   # fields come / go
        # the row just placed follows its bar — live (his ask, 2026-10-03)
        if element == "column" and key in ("count", "spacing", "ends", "by",
                                           "w", "d", "angle", "section",
                                           "anchor", "base", "fit") \
                and self._last_row is not None:
            QTimer.singleShot(0, self._redo_last_row)
        if key == "shape":
            self._last_row = None
            if (element, value) in STRUCT_ACTIONS:
                QTimer.singleShot(0, lambda: self.struct_action(element,
                                                                value))
            else:
                QTimer.singleShot(0, lambda: self.start_struct_tool(element))

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
            opts.append({"key": "swing", "label": "Hinge", "kind": "segments",
                         "value": o["swing"],
                         "choices": [("left", "Left"), ("right", "Right")],
                         "tip": "Which jamb it hangs on (Tab while placing "
                                "turns it round)"})
        return opts

    def _on_opening_option(self, kind: str, key: str, value) -> None:
        self.op_opts[kind][key] = value
        if key == "shape":
            QTimer.singleShot(0, lambda: self.start_opening_tool(kind))

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

    def start_opening_tool(self, kind: str) -> None:
        if self._pro_only(kind):
            return
        from .openingtools import OpeningTool
        _i, lv, z0 = self._work_level()
        doc = self._live(self.doc())
        walls = [w for w in doc["walls"] if w["level"] == lv["id"]]
        ids = {w["id"] for w in walls}
        cache = {"ops": [o for o in doc["openings"] if o["wall"] in ids]}
        tool = OpeningTool(kind, self._opening_done, self._wall_cancelled, z0,
                           lambda: self.op_opts[kind], lambda: walls,
                           lambda: cache["ops"], self._wall_height)
        tool.level_id = lv["id"]
        tool._cache = cache
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
        if not dlg.exec():
            return
        action, new = dlg.result_data()
        if action == "delete":
            self.delete_opening(op_id)
        else:
            self.apply_opening(new)
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
    def _level_struct(self, doc: dict, level_id: str,
                      kind: str | None = None) -> list[dict]:
        return [e for e in doc.get("structure") or []
                if e["level"] == level_id and (kind is None
                                               or e["type"] == kind)]

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
        elif element == "column":
            if o["shape"] not in ("single", "row", "grid"):
                return
            cache = self._level_struct(doc, lv["id"], "column")
            tool = T.ColumnTool(o["shape"], None, self._wall_cancelled, z0,
                                lambda: self.col_opts, lambda: cache)
            tool.on_done = lambda recs, t=tool: self._columns_done(recs, t)
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
        elif element == "beam":
            beams = T.beams_as_walls(self._level_struct(doc, lv["id"],
                                                        "beam"))
            tool = T.BeamTool(self._beams_drawn, self._wall_cancelled, z0,
                              lambda: {"t": self.beam_opts["w"],
                                       "align": "centre"},
                              lambda: beams)
        elif element == "slab":
            if o["shape"] == "hole":             # an opening through one
                tool = T.SLAB_TOOLS["rect"](self._slab_hole_drawn,
                                            self._wall_cancelled, z0)
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

    def _redo_last_row(self) -> None:
        """The last row again, with the bar's count / spacing / ends /
        sizes — in place of the one made (its own Ctrl+Z)."""
        from . import structure as S
        row = self._last_row
        if row is None:
            return
        doc = self._live(self.doc())
        ids = set(row["ids"])
        if not any(e["id"] in ids for e in doc["structure"]):
            self._last_row = None              # undone, or deleted
            return
        _i, lv, _z = self._work_level()
        walls = [w for w in doc["walls"] if w["level"] == lv["id"]]
        tool = row["tool"]
        a, b = row["ab"]
        tool.a = a
        recs = tool.columns(b)
        tool.a = None
        o = self.col_opts
        out = []
        for r in recs:
            r = dict(r, level=lv["id"], base=float(o.get("base", 0.0)))
            r["height"] = "level" if o["height"] == "level" else \
                float(o["h"])
            if o["fit"] == "fit":
                r = S.fit_column(r, walls)
            if not S.why_not(r):
                out.append(r)
        kept = [e for e in doc["structure"] if e["id"] not in ids]
        made = model.new_elements(kept, out)
        doc["structure"] = kept + made
        self._commit_all(doc)
        self._last_row = {"ids": [m["id"] for m in made], "ab": (a, b),
                          "tool": tool}
        compat.flash(self.viewport, f"Row: {len(made)} columns — Ctrl+Z "
                     "goes back a step", 3000)

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
        self._struct_done([{"type": "beam", "a": r["a"], "b": r["b"],
                            "w": o["w"], "h": o["h"]} for r in recs])

    def _slab_drawn(self, corners) -> None:
        o = self.slab_opts
        self._struct_done([{"type": "slab", "corners": corners,
                            "t": o["t"], "offset": o["offset"]}])

    def _roof_rec(self, corners) -> dict:
        from . import structure as S
        o = self.roof_opts
        return {"type": "roof", "kind": o["kind"],
                "corners": S.roof_corners(corners, o["kind"]),
                "slope": o["slope"], "overhang": o["overhang"], "t": o["t"],
                "ridge": o["ridge"],
                "parapet": o["parapet"] if o["kind"] == "flat" else 0.0,
                "pt": o["pt"]}

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
            ca, cb = a["corners"], b["corners"]
            return len(ca) == len(cb) and all(
                any(_m.dist(p, q) < 0.02 for q in cb) for p in ca)
        if a["type"] in ("ramp", "stair"):       # the same one, on top
            return _m.dist((a["x"], a["y"]), (b["x"], b["y"])) < 0.02 and \
                abs((float(a.get("angle", 0)) - float(b.get("angle", 0))
                     + 180) % 360 - 180) < 0.5
        return False

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
            why = "No walls meet on this level"
        elif (element, shape) == ("beam", "walls"):
            o = self.beam_opts
            recs = [{"type": "beam", "a": a, "b": b, "w": o["w"],
                     "h": o["h"]} for a, b in S.along_walls(walls)]
            why = "No straight walls on this level"
        elif (element, shape) == ("slab", "walls"):
            loop = S.inside_walls(walls, compat.outer_loop)
            o = self.slab_opts
            if loop:
                recs = [{"type": "slab", "corners": loop, "t": o["t"],
                         "offset": o["offset"]}]
            why = "No walls on this level to put a slab under"
        elif (element, shape) == ("footing", "pads"):
            o = self.foot_opts
            for c in self._level_struct(doc, lv["id"], "column"):
                cx, cy = S.column_centre(c)
                side = max(float(c["w"]), float(c["d"])) + 0.20
                recs.append({"type": "footing", "kind": "pad",
                             "x": round(cx, 4), "y": round(cy, 4),
                             "w": max(o["w"], side), "d": o["d"],
                             "angle": float(c.get("angle", 0.0))})
            why = "No columns on this level (draw them first)"
        elif (element, shape) == ("footing", "strips"):
            o = self.foot_opts
            recs = [dict(s, type="footing", kind="strip", w=o["sw"],
                         d=o["d"]) for s in S.strips_under(walls)]
            why = "No walls on this level"
        elif (element, shape) == ("roof", "walls"):
            loop = S.inside_walls(walls, compat.outer_loop)
            if loop:
                recs = [self._roof_rec(loop)]
            why = "No walls on this level to put a roof on"
        if not recs:
            compat.flash(self.viewport, f"{why} — nothing built", 5000)
            return
        self._struct_done(recs)
        QTimer.singleShot(0, self._refill_options)

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

    def tool_element(self) -> str | None:
        """The element (wall, column, beam, slab…) whose drawing tool is
        out, or None."""
        tool = getattr(self.viewport, "active_tool", None)
        if not type(tool).__module__.startswith("archxq_it"):
            return None
        return getattr(tool, "axq_element", None)

    def wall_tool_out(self) -> bool:
        return self.tool_element() == "wall"

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
        from . import structure as S
        from . import walls as W
        have = compat.built_ids(self.viewport)
        built = doc.get("built")
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
        doc["walls"] = [w for w in doc["walls"] if not gone(w, W.why_not)]
        from . import autoslabs
        st = doc.get("structure") or []
        # an automatic slab deleted stays away (else the next rebuild made
        # it again)
        off = {autoslabs.key_of(e) for e in st
               if autoslabs.key_of(e) and gone(e, S.why_not)}
        if off:
            doc["auto_off"] = sorted(set(doc.get("auto_off") or []) | off)
        doc["structure"] = [e for e in st if not gone(e, S.why_not)]
        # an opening goes with its wall; a door / window deleted with the
        # host's tools goes too (a void has no object of its own)
        walls = {w["id"]: w for w in doc["walls"]}
        ops = doc.get("openings") or []

        def keep(o) -> bool:
            if o["wall"] not in walls:
                return False
            if o["kind"] == "void" or o["id"] in have:
                return True
            # not built: it no longer fits its wall — kept, it waits
            w = walls[o["wall"]]
            return S.opening_room(o, w, ops, self._wall_height(w)) is not None
        doc["openings"] = [o for o in ops if keep(o)]
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

    def _commit_all(self, doc: dict) -> None:
        """THE way the building is stored: every wall and structural
        element rebuilt from ``doc`` — one Ctrl+Z. The excavations' slabs
        are made / followed first (autoslabs)."""
        from . import autoslabs
        doc = self._with_built(autoslabs.sync(doc, model.elevations))
        compat.commit_build(self.viewport, self.app.key, doc,
                            model.elevations, compat.level_layer)
        self._apply_parts()              # «Show», and what hides in walls
        lv_id = getattr(getattr(self.viewport, "active_tool", None),
                        "level_id", None)
        if lv_id:
            self._wall_cache = self._live_walls(self.doc(), lv_id)
        self._outline_soon()

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

    def _wall_cancelled(self) -> None:
        self.method = None
        compat.back_to_select(self.viewport)
        self.refresh()                       # the shape's icon goes dark

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
                                         "footing", "roof", "ramp", "stair"):
            return None
        rec = (getattr(group, "ext", None) or {}).get(compat.EXT_KEY) or {}
        return rec.get("id")

    def edit_element(self, el_id: str) -> None:
        """A column's / beam's / slab's / footing's window (modal). Apply
        = one Ctrl+Z."""
        from .dialogs import ElementDialog
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
        dlg = ElementDialog(el, lv, self.window)
        if not dlg.exec():
            return
        action, new = dlg.result_data()
        if action == "delete":
            self.delete_element(el_id)
        elif action == "hide":
            self.hide_element(el_id, el["name"])
        else:
            self.apply_element(new)
            self._again(dlg, lambda: self.edit_element(el_id))

    def apply_element(self, new: dict) -> None:
        from . import structure as S
        if new["type"] == "roof":            # pitched now: its rectangle
            new = dict(new, corners=S.roof_corners(new["corners"],
                                                   new["kind"]))
        why = S.why_not(new)
        if why:
            compat.flash(self.viewport, f"«{new['name']}» not changed — "
                         f"{why}", 6000)
            return
        doc = self._live(self.doc())
        doc["structure"] = [new if e["id"] == new["id"] else e
                            for e in doc["structure"]]
        self._commit_all(doc)
        compat.flash(self.viewport, f"«{new['name']}» updated — Ctrl+Z "
                     "undoes it", 5000)

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

    def _ramp_defaults(self, doc: dict, opts=None, kind="ramp") -> dict:
        """The last ramp (stair) set up — or, the first time, from the level
        worked on down to the one under it."""
        rec = dict(self.bramp_opts if opts is None else opts, type=kind)
        from . import ramps as R
        ids = [lv["id"] for lv in doc["levels"]]
        if R.from_level(rec) not in ids:
            # bottom up, as a stair is thought of (his call, 2026-10-05):
            # from the level under the one worked on up to it (the lowest
            # level: from it up to the next one), clicked at its bottom
            i, lv, _z = self._work_level()
            levels = doc["levels"]
            lo, hi = (i - 1, i) if i > 0 else (i, i + 1)
            if hi >= len(levels):
                lo, hi = i, None
            rec["from"] = rec["level"] = levels[lo]["id"]
            rec["start"] = "level"
            rec["to"] = levels[hi]["id"] if hi is not None else "z"
        to = rec.get("to")
        if to not in ids + ["z"] and not (isinstance(to, str) and to.startswith(
                R.TOP) and to[len(R.TOP):] in ids):
            rec["to"] = "z"
        return rec

    def start_ramp(self) -> None:
        """Ramp: its window first (from / to, width, slope…), then the plan
        of its «From» level — click where it starts, click the way it
        goes. The tool stays out for the next one (Esc = done)."""
        if self._pro_only("ramp"):
            return
        from . import ramps as R
        doc = self.doc()
        self.hub.close_sub()
        dlg = R.RampDialog(self._ramp_defaults(doc), doc, model.elevations,
                           edit=False, parent=self.window)
        if not dlg.exec():
            return
        _a, rec = dlg.result_data()
        self.bramp_opts = {k: rec[k] for k in ("start", "from", "level", "to",
                                               "to_z",
                                               "w", "slope", "fix", "L", "t",
                                               "shape", "turn", "landing",
                                               "anchor")}
        self.set_floor(rec["level"], quiet=True)     # drawn on its level
        _i, lv, z0 = self._work_level()

        def length_at(p):
            zs, ze = R.heights(dict(rec, x=p[0], y=p[1]), doc,
                               model.elevations)
            return R.length_of(rec, zs, ze), zs, ze
        tool = R.RampTool(rec, length_at, self._ramp_placed,
                          self._wall_cancelled, z0)
        tool.level_id = lv["id"]
        self._activate(tool)
        compat.flash(self.viewport, f"Ramp from «{lv['name']}» — click where "
                     "it starts", 4000)

    def _ramp_placed(self, rec: dict) -> None:
        rec = {k: v for k, v in rec.items() if k not in ("id", "name")}
        self._struct_done([rec])

    def edit_ramp(self, el: dict) -> None:
        """A ramp's own window: from / to, sizes, where it is; delete."""
        from . import ramps as R
        dlg = R.RampDialog(el, self.doc(), model.elevations, edit=True,
                           parent=self.window)
        if not dlg.exec():
            return
        action, new = dlg.result_data()
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
        """Stair: its window first (from / to, width, riser, tread,
        shape), then the plan of its «From» level — as a ramp."""
        if self._pro_only("stair"):
            return
        from . import ramps as R
        from . import stairs as ST
        doc = self.doc()
        self.hub.close_sub()
        dlg = ST.StairDialog(self._ramp_defaults(doc, self.bstair_opts,
                                                 "stair"),
                             doc, model.elevations, edit=False,
                             parent=self.window)
        if not dlg.exec():
            return
        _a, rec = dlg.result_data()
        self.bstair_opts = {k: rec[k] for k in (
            "start", "from", "level", "to", "to_z", "w", "riser", "tread",
            "fix_tread", "t", "shape", "turn", "landing", "anchor")}
        self.set_floor(rec["level"], quiet=True)
        _i, lv, z0 = self._work_level()

        def heights_at(p):
            return R.heights(dict(rec, x=p[0], y=p[1]), doc,
                             model.elevations)
        tool = ST.StairTool(rec, heights_at, self._ramp_placed,
                            self._wall_cancelled, z0)
        tool.level_id = lv["id"]
        self._activate(tool)
        compat.flash(self.viewport, f"Stair from «{lv['name']}» — click "
                     "where it starts", 4000)

    def edit_stair(self, el: dict) -> None:
        from . import stairs as ST
        dlg = ST.StairDialog(el, self.doc(), model.elevations, edit=True,
                             parent=self.window)
        if not dlg.exec():
            return
        action, new = dlg.result_data()
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
        if el.get("start") == "terrain" or el.get("to") not in order:
            say(f"Repeat works between levels — this {noun.lower()} starts "
                "on the terrain or ends at an elevation.")
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
        dlg = WallDialog(wall, lv, self.window)
        if not dlg.exec():
            return
        action, new = dlg.result_data()
        if action == "delete":
            self.delete_wall(wall_id)
        elif action == "hide":
            self.hide_element(wall_id, wall["name"])
        else:
            self.apply_wall(new)
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
        mine = self._live_walls(self.doc(), new["level"])
        self._commit_level_walls(new["level"], [new if w["id"] == new["id"]
                                                else w for w in mine])
        compat.flash(self.viewport, f"«{new['name']}» updated — Ctrl+Z "
                     "undoes it", 5000)

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
            return
        els = [(g, e) for g, e in ((g, self.element_of(g)) for g in groups)
               if e]
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

    def open_settings(self) -> None:
        from .dialogs import SettingsDialog
        self.hub.close_sub()
        dlg = SettingsDialog(self.window, self.placement)
        if dlg.exec():
            if dlg.placement != self.placement:    # the bars move (rebuilt)
                QTimer.singleShot(0, lambda p=dlg.placement:
                                  self.set_placement(p))
                return
            if self.plan_on:                 # the plan's style, at once
                from . import prefs
                compat.plan_style(self.viewport, False)
                if prefs.get("plan_hidden_line"):
                    compat.plan_style(self.viewport, True)
            self.refresh()
            self.viewport.update()

    # ---- Project -----------------------------------------------------------------
    def edit_project(self, tab: str = "project") -> None:
        """The Project dialog (modal): start a project, or edit it."""
        from .dialogs import ProjectDialog
        doc = self.doc()
        was_new = not model.has_project(doc)
        dlg = ProjectDialog(doc, self.window, tab)
        if not dlg.exec():
            return
        project, levels, system = dlg.result_data()
        doc = self.doc()               # fresh: nothing changed meanwhile lost
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
        if was_new:
            self._enter(next_open(self._done(doc), system))
            compat.flash(self.viewport, f"Project «{project['name']}» "
                         "started — next: draw the plot")
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
        rows = [{"key": r["id"], "name": r["name"], "kind": r["kind"],
                 "elev": elev[i],
                 "current": i == self.floor and not self.terrain_current,
                 "visible": compat.layer_visible(self.viewport, names[i])}
                for i, r in reversed(list(enumerate(levels)))]
        rows.insert(self._terrain_at(rows),
                    {"key": TERRAIN_ROW, "name": "Terrain",
                     "kind": "terrain", "elev": None,
                     "current": self.terrain_current,
                     "visible": compat.layer_visible(self.viewport,
                                                     compat.TERRAIN_LAYER)})
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

    def set_floor(self, key: str, quiet: bool = False) -> None:
        """Work on this level from now on — or on the Terrain."""
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
        # a level's height moves every level above it: the walls and the
        # structure are made again at their new heights
        fresh = self.doc()
        if fresh.get("walls") or fresh.get("structure"):
            self._commit_all(self._live(fresh))
        self.refresh()

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
                          self.window)
        if not dlg.exec():
            return
        action, name, height = dlg.result_data()
        doc = self.doc()               # fresh: nothing changed meanwhile lost
        levels = [dict(r) for r in doc["levels"]]
        levels[i]["name"], levels[i]["height"] = name, height
        if action == "above" or action == "below":
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
            self._save_levels(doc, levels, current=key)
            self._again(dlg, lambda: self.edit_level(key))

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

        def items(groups, parent: str) -> list[dict]:
            cats: dict[str, list] = {}
            for g in groups:
                cat, label = self._category(g)
                cats.setdefault(cat, []).append({
                    "key": f"group:{g.uid}", "label": label, "kind": "item",
                    "visible": not g.hidden,
                    "tip": "Click: select · double-click: edit"})
            out = []
            for cat, rows in cats.items():
                if cat == "Plot":               # a single thing: no folder
                    out += rows
                    continue
                out.append({"key": f"cat:{parent}:{cat}", "label": cat,
                            "kind": "category", "count": len(rows),
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
                    "±0.00" if abs(z) < 0.005 else f"{z:+.2f}"),
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
                    "label": "Setbacks" + (f"  ·  {plotgeo.area(area):,.0f} "
                                           "m² buildable" if area else ""),
                    "visible": doc["view"].get("setbacks", True),
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
        # what is picked in the model decides the level worked on (the
        # plot → the Terrain, a Level 2 object → Level 2) — only at the
        # moment the pick CHANGES: a level clicked afterwards wins, even
        # with the object still selected
        picked = frozenset(g.uid for g in selected)
        if picked != self._last_pick:
            self._last_pick = picked
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

    def toggle_levels_strip(self) -> None:
        if not self.active:
            self._menu_check("Levels strip\tN", self.levels_open)
            return                  # nothing of ArchXQ shows while it is off
        self.levels_open = not self.levels_open
        QSettings().setValue("archxq/levels_open",
                             "1" if self.levels_open else "0")
        self._menu_check("Levels strip\tN", self.levels_open)
        self._show_piece(self.levels, self.levels_bar, self.levels_open)
        self.layout_floating()

    # ---- View bar ----------------------------------------------------------------
    #: the view bar's «Show» chips → the kinds of groups they show / hide
    SHOW_KINDS = {"terrain": ("plot", "dig", "fill"),
                  "structure": ("column", "beam", "slab", "footing", "ramp",
                                "stair"),
                  "walls": ("wall",),
                  "openings": ("opening",),
                  "roof": ("roof",)}

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
        self._apply_parts()

    def _apply_parts(self) -> None:
        """Hide / show the groups of the parts switched off — and the
        structure INSIDE the walls while the walls are shown (its lines
        showed through them; it shows when the walls are hidden)."""
        walls_on = "walls" not in self.hidden_parts
        above = self._levels_above() if self.plan_on else set()
        mine_off = self._hidden_ids()     # hidden one by one (by its id)
        hide, show = [], []
        for g in self.viewport.scene.groups:
            k = compat.kind_of(g)
            for part, kinds in self.SHOW_KINDS.items():
                if k not in kinds:
                    continue
                # (a BOOL: «.get» gave None, None != False was always
                # true — every refresh re-showed 44 groups, the view
                # changed, the host said «document changed», ArchXQ
                # refreshed again: 20 times a second, the bars rebuilt
                # before their buttons could show — 2026-10-03)
                want = bool(part in self.hidden_parts or (
                    part == "structure" and walls_on
                    and compat._rec(g).get("inwall"))
                    # the plan cuts the building at the level worked on:
                    # what stands above it is not seen (his call,
                    # 2026-10-05 — a Level 1 slab hid a basement stair)
                    or compat._rec(g).get("level") in above
                    # its window's «Hide» / the outliner's eye: it holds
                    # through every rebuild
                    or compat._rec(g).get("id") in mine_off)
                if bool(g.hidden) != want:
                    (hide if want else show).append(g)
        if hide:
            compat.set_hidden(self.viewport, hide, True)
        if show:
            compat.set_hidden(self.viewport, show, False)

    def _hidden_ids(self) -> set:
        try:
            return set(self.doc().get("hidden_ids") or [])
        except Exception:  # noqa: BLE001 — nothing hidden
            return set()

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

    def _levels_above(self) -> set:
        """The levels over the one worked on (on the Terrain: over the
        ground floor) — what the plan does not show."""
        try:
            levels = self.doc()["levels"]
            i = self._ground_index({"levels": levels}) \
                if self.terrain_current else self.floor
        except Exception:  # noqa: BLE001 — nothing hidden
            return set()
        return {lv["id"] for k, lv in enumerate(levels) if k > i}

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
        if self.plan_on:
            self.leave_plan()
            # out of the plan = done drawing (his call, 2026-10-02): the
            # ArchXQ tool goes, the pencil leaves the pointer
            tool = getattr(self.viewport, "active_tool", None)
            if type(tool).__module__.startswith("archxq_it"):
                self.method = None
                compat.back_to_select(self.viewport)
                self.refresh()
        else:
            self.enter_plan()

    def enter_plan(self, quiet: bool = False) -> None:
        """From the top, parallel: where you draw and edit. The 3D view
        it came from is kept, to go back to."""
        if self.plan_on:
            return
        cam = compat.camera_state(self.viewport)
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
        from . import prefs
        if prefs.get("plan_hidden_line"):
            compat.plan_style(self.viewport, True)   # a view change only
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

    def _watch_plan(self, viewport) -> None:
        """Every frame (the overlay): has the camera left the plan? The
        orbit is locked, so only a view picked on purpose does it (Front,
        Iso, Perspective…) — that IS the 3D view now."""
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
        self.plan_on = False
        compat.lock_orbit(self.viewport, False)
        compat.plan_style(self.viewport, False)
        self._plan_back = None
        compat.set_perspective(self.viewport, True)
        self._apply_parts()              # the whole building again
        self._sync_plan()

    def _sync_plan(self) -> None:
        self.plan_btn.set_plan(self.plan_on)
        self.viewbar.sync_view(self.plan_on)
        self.viewbar.sync_camera(compat.is_perspective(self.viewport))

    def _activate(self, tool) -> None:
        """Every ArchXQ drawing / editing tool comes out here. A CREATION
        tool works in the plan view, locked (unless the Settings say not
        to); an EDITING tool leaves the camera free — points are dragged
        in 3D too (his call, 2026-10-03)."""
        from . import prefs
        compat.activate_tool(self.viewport, tool)
        if self.active and getattr(tool, "creates", False) \
                and prefs.get("plan_on_tool"):
            self.enter_plan(quiet=True)
        self._sync_lock()

    def _plan_locks(self) -> bool:
        """The plan is locked to the top unless an EDITING tool is out."""
        tool = getattr(self.viewport, "active_tool", None)
        editing = type(tool).__module__.startswith("archxq_it") \
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

    # ---- Refresh -------------------------------------------------------------------
    def _on_doc_changed(self) -> None:
        """The host says the document changed — it says so for every
        change of the scene, view ones too. ArchXQ rebuilds its pieces
        only when ITS data or its objects did change: a refresh that
        touches the view must never feed itself (it once ran 20 times a
        second and the bars never got to show their buttons)."""
        if not (self.alive and self.active):
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

    def refresh(self) -> None:
        if not self.alive or not self.active:
            return
        doc = self.doc()
        done, system = self._done(doc), doc["system"]
        path = order(system)
        if not reachable(self.current, done, system):
            self._enter(next_open(done, system))
        if self.element not in PHASES[self.current].elements:
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

        if not 0 <= self.floor < len(doc["levels"]):
            self.floor = self._ground_index(doc)
        self._fill_levels(doc)
        self._apply_parts()          # rebuilt groups keep the «Show»
        self._outline_soon()

        has_methods = self.strip.fill(self.element, self.method)
        self._show_piece(self.plan_btn, self.plan_bar, True)
        self._show_piece(self.strip, self.strip_bar, has_methods)
        self._show_piece(self.elbox, self.elbox_bar, True)
        self._show_piece(self.viewbar, self.view_bar, True)
        self._sync_plan()
        self.props.show_for(self.current, self.element,
                            self.current in done,
                            dict(doc, _has_plot=self.has_plot(doc)))
        self._element_options()
        self.layout_floating()
        QTimer.singleShot(0, self.layout_floating)

    def _overlay(self, viewport, painter) -> None:
        """ArchXQ's drawings over the 3D view: the active ArchXQ tool's
        marker, live measurements and 45° guide."""
        if not self.alive:
            return
        self._watch_plan(viewport)
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
        if callable(draw) and type(tool).__module__.startswith("archxq_it"):
            try:
                draw(viewport, painter)
            except Exception:  # noqa: BLE001 — never break the host's paint
                pass

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
            pass

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
            for c in doc.get("structure") or []:
                if c["type"] != "column" or c["level"] != lv["id"] \
                        or not c.get("fit"):
                    continue
                pts = [compat.to_pixel(viewport, x, y, top)
                       for x, y in S.column_outline(c, 0.0)]
                if all(pts):
                    painter.drawPolygon(QPolygonF([QPointF(*p)
                                                   for p in pts]))
            painter.restore()
        except Exception:  # noqa: BLE001 — never break the host's paint
            pass

    def _draw_opening_symbols(self, viewport, painter) -> None:
        """In the plan, the current level's openings as a plan draws them
        (jambs, glass, a door's leaf and swing) — the walls' tops hide the
        openings themselves from above. Lines only, over the view."""
        from . import openingtools as OT
        from . import walls as W
        if "openings" in self.hidden_parts:
            return
        try:
            doc = self.doc()
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
            if lines:
                OT.draw_lines(viewport, painter, lines, z, OT.PLAN_INK, 1.3)
        except Exception:  # noqa: BLE001 — never break the host's paint
            pass

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
                pass
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
                pass
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
                pass
            return
        if self.setback_preview is not None:    # the Setbacks window is open
            p, active = self.setback_preview
            try:
                plottools.draw_plot_preview(viewport, painter, p["corners"],
                                            p["heights"], None, PLOT_Z,
                                            active,
                                            dims=self.dims_on("plot_dims"))
                if self.view_on("setbacks"):
                    plottools.draw_setbacks(
                        viewport, painter, p, PLOT_Z,
                        dims=self.dims_on("setback_dims"))
            except Exception:  # noqa: BLE001 — never break the host's paint
                pass
            return
        if not self.terrain_current:
            self._draw_underlay(viewport, painter)
        if self.plan_on:
            self._draw_plan_grid(viewport, painter)
            self._draw_plan_guides(viewport, painter)
        if self.plan_on and not self.terrain_current:
            self._draw_hidden_columns(viewport, painter)
            self._draw_opening_symbols(viewport, painter)
            self._draw_room_labels(viewport, painter)
        if getattr(getattr(viewport, "active_tool", None), "draws_plot",
                   False):
            return                 # the tool draws the plot its own way
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
            # the buildable area shows unless its eye is off (it is the
            # reference for building); its figures have their own switch
            if doc["view"].get("setbacks", True):
                plottools.draw_setbacks(viewport, painter, doc["plot"],
                                        PLOT_Z,
                                        dims=self.dims_on("setback_dims"))
        except Exception:  # noqa: BLE001 — never break the host's paint
            pass

    # ---- Placement of the floating pieces ------------------------------------------
    def _show_piece(self, widget, bar, on: bool) -> None:
        if bar is not None:
            bar.setVisible(on)
        else:
            widget.setVisible(on)

    def layout_floating(self) -> None:
        """"viewport" placement: hub top-left, strip under it on the left,
        view bar centred at the bottom."""
        if not self.alive or self.placement != "viewport":
            return
        vp = self.viewport
        self.hub.move(MARGIN, MARGIN)
        top_row = MARGIN + self.hub.row.height() + MARGIN
        # the plan view switch on its own, then the drawing methods under it
        self.plan_btn.ensurePolished()
        self.plan_btn.adjustSize()
        self.plan_btn.move(MARGIN, top_row)
        self.strip.layout().activate()       # its new buttons, measured
        self.strip.resize(self.strip.sizeHint())
        self.strip.move(MARGIN, top_row + self.plan_btn.height() + MARGIN)
        # the «Building elements» under the methods (under the plan switch
        # when no methods show), a gap between: another section
        self.elbox.adjustSize()
        below = (self.strip.y() + self.strip.height()) \
            if self.strip.isVisible() \
            else top_row + self.plan_btn.height()
        self.elbox.move(MARGIN, below + 2 * MARGIN)
        self.viewbar.adjustSize()
        self.viewbar.move(max(MARGIN, (vp.width() - self.viewbar.width()) // 2),
                          vp.height() - self.viewbar.height() - MARGIN)
        # options: under the phases row, beside the left column
        left = max(self.plan_btn.width() if self.plan_btn.isVisible() else 0,
                   self.strip.width() if self.strip.isVisible() else 0,
                   self.elbox.width() if self.elbox.isVisible() else 0)
        x = MARGIN + (left + MARGIN if left else 0)
        self.optbar.max_width = vp.width() - x - MARGIN   # rows past this
        self.optbar.fit()
        self.optbar.move(x, top_row)
        # levels: right edge, under the phases row, clear of the view bar —
        # and under the options bar when a long one reaches it (the
        # column's bar ran under the strip, «As drawn» hidden)
        top = MARGIN + self.hub.row.height() + MARGIN
        self.levels.fit()
        if self.optbar.isVisible() and x + self.optbar.width() > \
                vp.width() - self.levels.width() - 2 * MARGIN:
            top = top_row + self.optbar.height() + MARGIN
        self.levels.max_height = max(
            120, vp.height() - top - self.viewbar.height() - 3 * MARGIN)
        self.levels.fit()
        self.levels.move(vp.width() - self.levels.width() - MARGIN, top)
        self.optbar.raise_()
        self.hub.raise_()             # the hover submenu stays on top

    # ---- Teardown (dev reload) -------------------------------------------------------
    def teardown(self) -> None:
        self.alive = False
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
        self.viewport.removeEventFilter(self._dbl)
        self.viewport.removeEventFilter(self._nkey)
        self.window.removeEventFilter(self.hub)
        self.hub.sub.hide()
        self.hub.sub.deleteLater()
        for widget, bar in ((self.hub, self.hub.bar),
                            (self.plan_btn, self.plan_bar),
                            (self.strip, self.strip_bar),
                            (self.elbox, self.elbox_bar),
                            (self.viewbar, self.view_bar),
                            (self.levels, self.levels_bar),
                            (self.optbar, self.opt_bar)):
            widget.hide()
            compat.remove_toolbar(self.window, bar)
            widget.deleteLater()
        compat.remove_dock(self.window, self._dock)
        self.viewport.update()
