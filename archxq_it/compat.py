"""The ONE place that touches IngeTrazo internals.

IngeTrazo's extension API is 0.x: when an update moves something, only
this file should need fixing. Everything else in ArchXQ talks to these
helpers, never to ``views.*`` / ``core.*`` directly.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt

#: IngeTrazo version this prototype was written against.
TESTED_WITH = "0.5.7"      # (0.3.x → 0.5.6.1 → 0.5.7, 2026-09-30: no changes needed)

_AREAS = {"top": Qt.TopToolBarArea, "left": Qt.LeftToolBarArea,
          "bottom": Qt.BottomToolBarArea, "right": Qt.RightToolBarArea}


#: ArchXQ's own key for its data in the document — never the loader's
#: file name (the host keys an extension by the file that loaded it).
KEY = "archxq"


def make_app(window, key: str = KEY):
    """An ExtensionApp for a live window (dev reload path; at startup the
    host hands us one through ``setup(app)``)."""
    from views.extension_api import ExtensionApp
    return ExtensionApp(window, key)


def own_key(app) -> str:
    """Make ``app`` read and write ArchXQ's data under ``KEY``, whatever
    file loaded us. Returns the key the host gave (for ``adopt_data``)."""
    old = app.key
    app.key = KEY
    return old


def adopt_data(app, old: str) -> None:
    """Data a file keeps under the loader's key (saved before ``own_key``)
    moves to ``KEY`` in memory; the file changes on its next save."""
    if not old or old == KEY:
        return
    data = getattr(app.scene, "plugin_data", None)
    if isinstance(data, dict) and old in data and KEY not in data:
        data[KEY] = data.pop(old)


# ---- Placement of the ArchXQ pieces ------------------------------------------
def place(viewport, widget, placement: str, area: str, css: str = "",
          new_line: bool = True):
    """Put one ArchXQ piece (top hub, left strip, bottom view bar) where
    the placement says. Returns the host toolbar it went into, or None.

    "viewport": the widget becomes a child of the 3D view (QOpenGLWidget
    composes child widgets); the caller positions it.
    "toolbar": the widget goes into a toolbar of its own in the window's
    ``area`` ("top" on a new row under the host's toolbars, "left" beside
    the host's drawing tools, "right" between the 3D view and the side
    tray, "bottom" over the status bar). ``new_line=False``: in the same
    row / column as the piece placed there before (one under the other)."""
    if placement == "viewport":
        widget.setParent(viewport)
        widget.show()
        widget.raise_()
        return None
    if placement != "toolbar":
        raise ValueError(f"unknown placement {placement!r}")
    from PySide6.QtWidgets import QToolBar
    window = viewport.window()
    bar = QToolBar(f"ArchXQ {area}")
    bar.setObjectName(f"archxq_bar_{area}")
    bar.setProperty("axq", "bar")
    bar.setProperty("area", area)
    bar.setMovable(False)
    bar.setFloatable(False)
    if area in ("left", "right"):
        bar.setOrientation(Qt.Vertical)
    if css:
        bar.setStyleSheet(css)
    if new_line and area in ("top", "left", "right"):
        # a row (top) / column (left) of its own, next to the 3D view
        window.addToolBarBreak(_AREAS[area])
    window.addToolBar(_AREAS[area], bar)
    bar.addWidget(widget)
    widget.show()
    return bar


def add_ext_menu(app, title: str, entries):
    """ArchXQ's own submenu in the host's Extensions menu (API 2:
    ``add_menu``). entries: [(text, fn, tip, checked | None) | None=line].
    Returns the QMenu and its checkable actions by text."""
    menu = app.add_menu(title) if hasattr(app, "add_menu") else None
    acts = {}
    if menu is None:
        return None, acts
    for e in entries:
        if e is None:
            menu.addSeparator()
            continue
        text, fn, tip, checked = e
        a = menu.addAction(text)
        a.setStatusTip(tip)
        a.setToolTip(tip)
        if checked is not None:
            a.setCheckable(True)
            a.setChecked(bool(checked))
        # run once the menu has closed: an action that relays the window
        # out (switching ArchXQ on / off) while the menu bar is still in
        # its popup state could leave it unable to open File on the first
        # click (a Pro buyer's report, 2026-10-07)
        a.triggered.connect(
            lambda _=False, f=fn: __import__(
                "PySide6.QtCore", fromlist=["QTimer"]).QTimer.singleShot(0, f))
        acts[text] = a
    return menu, acts


def remove_ext_menu(menu) -> None:
    """Take ArchXQ's submenu out (dev reload builds it again)."""
    import shiboken6
    if menu is None or not shiboken6.isValid(menu):
        return
    act = menu.menuAction()
    for w in list(act.associatedObjects()):
        try:
            w.removeAction(act)
        except Exception:  # noqa: BLE001
            pass
    menu.deleteLater()


def remove_overlay(viewport, fn) -> None:
    """Take an overlay back out (the API adds, never removes: without
    this every dev reload leaves one behind)."""
    for name in ("_ext_overlays",):
        lst = getattr(viewport, name, None)
        if isinstance(lst, list):
            lst[:] = [f for f in lst if f != fn]


def set_view_flag(viewport, key: str, name: str, on) -> None:
    """What is shown (the buildable area, the fold lines…): kept in the
    document's ArchXQ data but written straight in — like a layer's eye,
    never an undo step."""
    data = viewport.scene.plugin_data
    doc = dict(data.get(key) or {})
    view = dict(doc.get("view") or {})
    view[name] = None if on is None else bool(on)
    doc["view"] = view
    data[key] = doc
    bump = getattr(viewport.scene, "bump_view", None)
    if callable(bump):
        bump()
    viewport.update()


def set_hidden_ids(viewport, key: str, ids) -> None:
    """The ArchXQ elements hidden (by their ids — the groups are made anew
    at every rebuild): kept in the document's data, written straight in
    like a layer's eye, never an undo step."""
    data = viewport.scene.plugin_data
    doc = dict(data.get(key) or {})
    doc["hidden_ids"] = sorted({str(i) for i in ids if i})
    data[key] = doc
    bump = getattr(viewport.scene, "bump_view", None)
    if callable(bump):
        bump()
    viewport.update()


def set_hidden_parts(viewport, key: str, parts: dict) -> None:
    """The parts of each level switched off in its window («Show»): {level
    id: [part keys]} — view state, written straight in, never an undo
    step."""
    data = viewport.scene.plugin_data
    doc = dict(data.get(key) or {})
    doc["hidden_parts"] = {lv: sorted(p) for lv, p in parts.items() if p}
    data[key] = doc
    bump = getattr(viewport.scene, "bump_view", None)
    if callable(bump):
        bump()
    viewport.update()


def set_ghosts(viewport, key: str, ids) -> None:
    """The levels drawn as a ghost in the plan — view state, written
    straight in, never an undo step."""
    data = viewport.scene.plugin_data
    doc = dict(data.get(key) or {})
    doc["ghosts"] = sorted({str(i) for i in ids if i})
    data[key] = doc
    bump = getattr(viewport.scene, "bump_view", None)
    if callable(bump):
        bump()
    viewport.update()


def show_folds(viewport, group, corners, breaks, on: bool) -> None:
    """Fold lines drawn or not on the plot's surface, without rebuilding
    it: their edges hard (drawn) or soft (not)."""
    if group is None:
        return
    keep = {frozenset(b) for b in breaks}
    xy = {(round(x, 4), round(y, 4)): i for i, (x, y) in enumerate(corners)}
    for e in group.mesh.edges:
        i = xy.get((round(e.a.x(), 4), round(e.a.y(), 4)))
        j = xy.get((round(e.b.x(), 4), round(e.b.y(), 4)))
        # only the top has diagonals (the bottom is one flat face, the
        # sides' uprights join a corner to itself)
        if i is not None and j is not None and frozenset((i, j)) in keep:
            e.soft = not on
    bump = getattr(viewport.scene, "bump_view", None)
    if callable(bump):
        bump()
    viewport.update()


def remove_toolbar(window, toolbar) -> None:
    if toolbar is None:
        return
    window.removeToolBar(toolbar)
    toolbar.deleteLater()


def remove_dock(window, dock) -> None:
    import shiboken6
    if dock is None or not shiboken6.isValid(dock):
        return                     # never built, or already gone
    docks = getattr(window, "_extension_docks", None)
    if isinstance(docks, list) and dock in docks:
        docks.remove(dock)
    elif isinstance(docks, dict):
        for k, v in list(docks.items()):
            if v is dock:
                del docks[k]
    window.removeDockWidget(dock)
    dock.deleteLater()


def show_host_properties(window) -> None:
    """Bring the host's Properties tab to the front of the side tray."""
    from PySide6.QtWidgets import QDockWidget
    dock = window.findChild(QDockWidget, "tray_properties")
    if dock is not None:
        dock.raise_()


# ---- Tools ------------------------------------------------------------------------
def activate_tool(viewport, tool) -> None:
    viewport.set_active_tool(tool)
    viewport.setFocus()


_HOST_REACH = None


def restore_snap_reach(viewport) -> None:
    """The host's own magnets back (ArchXQ leaving, a reload)."""
    if _HOST_REACH is not None:
        set_snap_reach(viewport, *_HOST_REACH)


def set_snap_reach(viewport, point_px=None, edge_px=None):
    """How far (pixels) the host's snapping pulls the cursor to points and
    to edges. → the previous values, to put back."""
    before = (getattr(viewport, "snap_threshold_px", None),
              getattr(viewport, "edge_snap_threshold_px", None))
    global _HOST_REACH
    if _HOST_REACH is None:
        _HOST_REACH = before                 # the host's own, kept once
    if point_px is not None and before[0] is not None:
        viewport.snap_threshold_px = float(point_px)
    if edge_px is not None and before[1] is not None:
        viewport.edge_snap_threshold_px = float(edge_px)
    return before


def tool_cursor(viewport) -> None:
    """Give the 3D view back the active tool's pointer."""
    for name in ("_reassert_tool_cursor", "_apply_tool_cursor"):
        f = getattr(viewport, name, None)
        if callable(f):
            try:
                f()
            except Exception:  # noqa: BLE001
                pass
            return


def back_to_select(viewport) -> None:
    """Leave the drawing tool the way the user would: pick Select."""
    from PySide6.QtGui import QAction
    for act in viewport.window().findChildren(QAction):
        if act.text().replace("&", "").strip().lower() == "select" \
                and act.isEnabled():
            act.trigger()
            return
    from tools.select import SelectTool
    viewport.set_active_tool(SelectTool())


def typed_value(viewport) -> str:
    """What the user is typing in the measurements box (VCB), or ""."""
    return str(getattr(viewport, "_value_buffer", "") or "")


def to_pixel(viewport, x: float, y: float, z: float = 0.0):
    from PySide6.QtGui import QVector3D
    return viewport._world_to_pixel(QVector3D(x, y, z))


def vec(x: float, y: float, z: float = 0.0):
    from PySide6.QtGui import QVector3D
    return QVector3D(x, y, z)


# ---- Model objects ------------------------------------------------------------------
def find_group(viewport, uid: str):
    if not uid:
        return None
    try:
        return viewport.scene.groups_by_uid().get(uid)
    except Exception:  # noqa: BLE001
        return None


# ---- Layers (the host's tags): one per ArchXQ level, one for the terrain ----------
LAYER_PREFIX = "ArchXQ · "
TERRAIN_LAYER = LAYER_PREFIX + "Terrain"


def level_layer(name: str) -> str:
    return LAYER_PREFIX + name


def _layer(viewport, name: str):
    return next((L for L in viewport.scene.layers if L.name == name), None)


def ensure_layers(viewport, names) -> None:
    """The layers exist (a new one is visible). Not an undo step: like
    the host's own tags, layers are the drawing's organisation."""
    from core.layers import Layer
    for name in names:
        if _layer(viewport, name) is None:
            viewport.scene.layers.append(Layer(name))


def prune_layers(viewport, keep) -> None:
    """Drop ArchXQ's own layers that no level uses any more AND nothing
    sits on (left behind by an undone «+», say). Others' layers are never
    touched."""
    used = {getattr(g, "layer", None) for g in viewport.scene.groups}
    gone = [L for L in viewport.scene.layers
            if L.name.startswith(LAYER_PREFIX) and L.name not in keep
            and L.name not in used]
    for L in gone:
        viewport.scene.layers.remove(L)
    if gone:
        _refresh_host_layers(viewport)


def layer_content(viewport, name: str) -> int:
    """How many things sit on a layer: groups (nested too), loose faces
    and edges. A level with anything on it is never deleted."""
    from core.layers import layer_of
    n = 0
    stack = list(viewport.scene.groups)
    while stack:
        g = stack.pop()
        if getattr(g, "layer", None) == name:
            n += 1
        stack.extend(getattr(g, "children", None) or [])
    mesh = viewport.scene.mesh
    for coll in (getattr(mesh, "faces", ()), getattr(mesh, "edges", ())):
        for e in coll:
            try:
                if layer_of(e) == name:
                    n += 1
            except Exception:  # noqa: BLE001
                pass
    return n


def layer_visible(viewport, name: str) -> bool:
    L = _layer(viewport, name)
    return True if L is None else bool(L.visible)


def set_layer_visible(viewport, name: str, on: bool) -> None:
    """Show / hide a layer — view state, kept in the file, not an undo
    step (the host's Layers panel works the same way)."""
    ensure_layers(viewport, [name])
    _layer(viewport, name).visible = bool(on)
    # what is SHOWN changed: the host's render caches must refresh, or
    # the geometry stays on screen until something else redraws it
    bump = getattr(viewport.scene, "bump_view", None)
    if callable(bump):
        bump()
    _refresh_host_layers(viewport)
    viewport.update()


def set_hidden(viewport, groups, hidden: bool) -> None:
    """Hide / show objects — view state like a layer's eye: not an undo
    step, the render caches refreshed."""
    for g in groups:
        g.hidden = bool(hidden)
    bump = getattr(viewport.scene, "bump_view", None)
    if callable(bump):
        bump()
    viewport.update()


def select(viewport, groups, mode: str = "replace") -> None:
    """Select objects in the model the way a click would."""
    sc = viewport.scene
    if groups:
        sc.select(list(groups), mode=mode)
    elif mode == "replace":
        sc.clear_selection()
    viewport.update()


def selected_groups(viewport) -> list:
    return [e for e in viewport.scene.selection
            if type(e).__name__ == "Group"]


def loose_count(viewport) -> int:
    """Faces and edges drawn outside any group."""
    m = viewport.scene.mesh
    return len(getattr(m, "faces", ())) + len(getattr(m, "edges", ()))


def _refresh_host_layers(viewport) -> None:
    """Tell the host's Layers panel, if it listens, that layers changed."""
    for fn in ("refresh_layers", "layers_changed", "_refresh_layers"):
        f = getattr(viewport.window(), fn, None)
        if callable(f):
            try:
                f()
            except Exception:  # noqa: BLE001
                pass
            return


def save_doc_renaming(viewport, key: str, doc: dict, renames) -> None:
    """Store ``doc`` and rename layers ``[(old, new)]`` (and move what
    sits on them) as ONE undo step — a level renamed keeps its layer."""
    from core.history import Command, CompoundCommand, SetPluginDataCommand

    renames = [(a, b) for a, b in renames if a != b]

    class _Rename(Command):
        def _swap(self, scene, pairs) -> None:
            # in two steps through temporary names: a chain like
            # Level 2 → Level 3, Level 3 → Level 4 never collides
            def rename(a, b) -> None:
                for L in scene.layers:
                    if L.name == a:
                        L.name = b
                stack = list(scene.groups)
                while stack:
                    g = stack.pop()
                    if getattr(g, "layer", None) == a:
                        g.layer = b
                    stack.extend(getattr(g, "children", None) or [])
            for k, (a, _b) in enumerate(pairs):
                rename(a, f"\x00axq-tmp-{k}")
            for k, (_a, b) in enumerate(pairs):
                rename(f"\x00axq-tmp-{k}", b)

        def do(self, scene) -> None:
            self._swap(scene, renames)

        def undo(self, scene) -> None:
            self._swap(scene, [(b, a) for a, b in renames])

    cmds = [SetPluginDataCommand(key, doc)]
    if renames:
        cmds.insert(0, _Rename())
    viewport.history.execute(CompoundCommand(cmds))
    _refresh_host_layers(viewport)
    viewport.update()


def earcut(points, hole_starts=None):
    """The host's earcut: ``points`` = outer ring then each hole's, as
    (x, y); ``hole_starts`` = where each hole begins. → index triangles."""
    from core.triangulate import earcut as _earcut
    return _earcut([tuple(p) for p in points], list(hole_starts or []))


def arrangement(segments):
    """The host's planar arrangement on the ground plane: ``segments`` =
    [((x, y), (x, y))…], crossing / overlapping / touching as they like.
    → the minimal regions they make: [(outer, holes, inside_point)], every
    loop a list of (x, y)."""
    from core.arrangement import planar_arrangement, scan_interior_point
    from PySide6.QtGui import QVector3D as V
    segs = [(V(a[0], a[1], 0.0), V(b[0], b[1], 0.0)) for a, b in segments]
    out = []
    for outer, holes in planar_arrangement(segs, V(0, 0, 0), V(0, 0, 1)):
        o = [(p.x(), p.y()) for p in outer]
        hs = [[(p.x(), p.y()) for p in h] for h in holes]
        out.append((o, hs, scan_interior_point(o, hs)))
    return out


# ---- What an object IS: ArchXQ's record ON the group (API 2: group.ext) -----------
#: ``group.ext["archxq"] = {"type": "plot", …}`` — it survives save/open
#: and travels with copies; the name can be changed by the user freely.
EXT_KEY = "archxq"


def tag(group, kind: str, **data) -> None:
    ext = dict(getattr(group, "ext", None) or {})
    ext[EXT_KEY] = dict(data, type=kind)
    group.ext = ext


def kind_of(group) -> str | None:
    """ArchXQ's type of an object ("plot"…), or None for anything else."""
    rec = (getattr(group, "ext", None) or {}).get(EXT_KEY)
    return rec.get("type") if isinstance(rec, dict) else None


# ---- The viewport's right-click menu (API 2: add_context_menu) ----------------------
def add_context_menu(app, fn) -> None:
    """``fn(menu, selection)`` adds ArchXQ's entries to the right-click
    menu. Open dialogs through ``QTimer.singleShot(0, …)``."""
    if hasattr(app, "add_context_menu"):
        app.add_context_menu(fn)


def remove_context_menu(viewport, fn) -> None:
    """The API adds, never removes: take ours out (dev reload)."""
    lst = getattr(viewport.window(), "_ext_context_menus", None)
    if isinstance(lst, list):
        lst[:] = [f for f in lst if f != fn]


def group_at(viewport, x: float, y: float):
    """The group under the viewport pixel (x, y), or None."""
    try:
        return viewport.pick_group(x, y)
    except Exception:  # noqa: BLE001
        return None


def selecting(viewport) -> bool:
    """The host's Select tool is out (not a drawing tool, not ours)."""
    return type(getattr(viewport, "active_tool", None)).__name__ \
        == "SelectTool"


PLOT_NAME = "ArchXQ Plot"


def find_plot(viewport, uid: str):
    """The plot group: by uid; else — should a reopened file hand out new
    uids — the one tagged «plot»; else (a plot from before the tag) by
    its name. ArchXQ keeps exactly one."""
    g = find_group(viewport, uid)
    if g is not None:
        return g
    groups = viewport.scene.groups
    return (next((g for g in groups if kind_of(g) == "plot"), None)
            or next((g for g in groups
                     if getattr(g, "name", "") == PLOT_NAME), None))


DIG_COLOR = (0.48, 0.40, 0.31)      # the earth inside a pit
FILL_COLOR = (0.66, 0.60, 0.45)     # earth brought in (a fill, a platform)


def _mesh_group(name: str, faces, soft, color, kind: str, **data):
    """A group from ``terrain.build`` faces: loops of (x, y, z) — or
    {"loop", "holes"} for a face with openings — and the ``soft`` edges
    (pairs of points) drawn smooth."""
    from core.group import Group
    from core.mesh import Mesh
    from PySide6.QtGui import QVector3D

    def v(p):
        return QVector3D(p[0], p[1], p[2])

    mesh = Mesh()
    for f in faces:
        if isinstance(f, dict):
            mesh.add_face([v(p) for p in f["loop"]],
                          [[v(p) for p in h] for h in f["holes"]])
        else:
            mesh.add_face([v(p) for p in f])
    if soft:
        key = {frozenset((round(a[0], 4), round(a[1], 4), round(a[2], 4))
                         for a in e) for e in soft}
        for e in mesh.edges:
            k = frozenset(((round(e.a.x(), 4), round(e.a.y(), 4),
                            round(e.a.z(), 4)),
                           (round(e.b.x(), 4), round(e.b.y(), 4),
                            round(e.b.z(), 4))))
            if k in key:
                e.soft = True
    _soften_flat_seams(mesh)
    g = Group(mesh, name=name)
    g.material = {"color": color, "opacity": 1.0}
    g.layer = TERRAIN_LAYER
    tag(g, kind, **data)
    return g


def dig_volumes(doc: dict, z0: float = 0.0) -> dict:
    """Earth each excavation takes out (m³), merged ones counted once."""
    from . import terrain
    if not doc.get("plot") or not doc.get("digs"):
        return {}
    return terrain.build(doc, z0, earcut, arrangement)["volumes"]


def _soften_flat_seams(mesh) -> None:
    """An edge between two faces of ONE plane is no fold — a seam the
    regions left (a pit's floor around a ramp's footprint, a wall cut in
    panels where a ramp meets it): drawn smooth, so it doesn't show. So
    is the joint of two upright panels less than 25° apart (a round
    pit's wall reads as one curve, as SketchUp softens it)."""
    curve = math.cos(math.radians(25))
    for e in mesh.edges:
        fs = list(getattr(e, "faces", ()) or [])
        if len(fs) != 2:
            continue
        n1, n2 = fs[0].normal, fs[1].normal
        n1 = n1() if callable(n1) else n1
        n2 = n2() if callable(n2) else n2
        dot = n1.dotProduct(n1, n2)
        if abs(n1.z()) < 0.05 and abs(n2.z()) < 0.05 and dot >= curve \
                and dot < 0.99995:
            e.soft = True                          # a curved wall
            continue
        if dot < 0.99995:
            continue
        # the same plane, not just parallel: a corner of one lies on the other
        p = fs[1].vertices[0]
        q = fs[0].vertices[0]
        if abs(n1.dotProduct(p - q, n1)) < 1e-3:
            e.soft = True


def terrain_groups(viewport) -> list:
    """Every group the terrain is made of (the plot, the pits)."""
    return [g for g in viewport.scene.groups
            if kind_of(g) in ("plot", "dig", "fill")
            or getattr(g, "name", "") == PLOT_NAME]


def commit_terrain(viewport, key: str, doc: dict, z0: float,
                   color, building=None) -> dict:
    """Rebuild the whole terrain from ``doc`` (its plot and excavations)
    and store ``doc`` — ONE undo step. Returns the stored doc (with the
    new groups' uids). ``building(doc)`` → a ``building_swap`` command,
    run in the same step (slabs that follow an excavation)."""
    from core.history import Command, CompoundCommand, SetPluginDataCommand
    from . import terrain

    ensure_layers(viewport, [TERRAIN_LAYER])
    doc = dict(doc)
    built = terrain.build(doc, z0, earcut, arrangement)
    from . import materials
    plot_g = _mesh_group(PLOT_NAME, built["plot"]["faces"],
                         built["plot"]["soft"], color, "plot")
    materials.paint(viewport.scene, plot_g, "plot", "plot", doc)
    new = [plot_g]
    uids = {}
    for d, faces in built["digs"]:
        fill = d.get("kind") == "fill"
        g = _mesh_group(d["name"], faces, built["dig_soft"].get(d["id"], ()),
                        FILL_COLOR if fill else DIG_COLOR,
                        "fill" if fill else "dig", id=d["id"])
        materials.paint(viewport.scene, g, "fill" if fill else "dig",
                        d["id"], doc)
        new.append(g)
        uids[d["id"]] = g.uid
    doc["plot"] = dict(doc["plot"], uid=plot_g.uid)
    if doc.get("digs") is not None:
        # every one KEPT — one that can't be built now (outside the plot,
        # its slopes past it) waits, with no group, until it fits again
        doc["digs"] = [dict(d, uid=uids.get(d["id"], ""))
                       for d in doc["digs"]]
    p = doc["plot"]
    if not (doc.get("view") or {}).get("folds", True):
        show_folds(viewport, plot_g, p["corners"], p["breaks"], False)
    old = terrain_groups(viewport)

    class _SwapTerrain(Command):
        def do(self, scene) -> None:
            self._at = {id(g): scene.groups.index(g) for g in old
                        if g in scene.groups}
            for g in old:
                if g in scene.groups:
                    scene.groups.remove(g)
            scene.groups.extend(new)
            _unselect(scene, old)

        def undo(self, scene) -> None:
            for g in new:
                if g in scene.groups:
                    scene.groups.remove(g)
            for g in sorted(old, key=lambda g: self._at.get(id(g), 1e9)):
                if g not in scene.groups:
                    scene.groups.insert(min(self._at.get(id(g),
                                                         len(scene.groups)),
                                            len(scene.groups)), g)
            _unselect(scene, new)

    cmds = [_SwapTerrain()]
    if building is not None:
        cmds.append(building(doc))
    viewport.history.execute(CompoundCommand(
        cmds + [SetPluginDataCommand(key, doc)]))
    viewport.update()
    # one that was built and now can't be (the ground rose under a fill by
    # the border, the plot shrank…): say so — it is kept, not lost
    was = {((getattr(g, "ext", None) or {}).get(EXT_KEY) or {}).get("id")
           for g in old}
    gone = [d["name"] for d in doc.get("digs") or []
            if d["id"] in was and not d.get("uid")]
    if gone:
        from PySide6.QtCore import QTimer
        text = (", ".join(gone) + (" reach" if len(gone) > 1 else " reaches")
                + " past the plot now — kept, but not built until it fits "
                "(steeper edges, or move it in) · Ctrl+Z undoes this")
        # after the caller's own message (this one matters more)
        QTimer.singleShot(60, lambda: flash(viewport, text, 9000))
    return doc


def remove_terrain(viewport, key: str, doc: dict, groups) -> None:
    """Take ``groups`` (terrain ones) out of the model and store ``doc`` —
    ONE undo step (deleting the plot, an excavation without a plot)."""
    from core.history import Command, CompoundCommand, SetPluginDataCommand
    old = [g for g in groups if g in viewport.scene.groups]

    class _Remove(Command):
        def do(self, scene) -> None:
            self._at = {id(g): scene.groups.index(g) for g in old
                        if g in scene.groups}
            for g in old:
                if g in scene.groups:
                    scene.groups.remove(g)

        def undo(self, scene) -> None:
            for g in sorted(old, key=lambda g: self._at.get(id(g), 1e9)):
                if g not in scene.groups:
                    scene.groups.insert(min(self._at.get(id(g),
                                                         len(scene.groups)),
                                            len(scene.groups)), g)

    viewport.history.execute(CompoundCommand(
        [_Remove(), SetPluginDataCommand(key, doc)]))
    viewport.update()


def commit_plot(viewport, key: str, doc: dict, corners, z: float,
                color, thickness: float = 0.0, heights=None,
                closing: int | None = None, breaks=(),
                fresh: bool = False, setbacks: dict | None = None) -> str:
    """Replace the plot group AND store ``doc`` (with the new corners) as
    ONE undo step. Returns the new group's uid. No ``heights`` = flat;
    no ``closing`` = the last side; ``breaks`` = fold lines [[i, j]].
    The setbacks ride along (per-side marks carried across a corner added
    or deleted) unless ``setbacks`` gives new ones or the plot is
    ``fresh`` (a new drawing: no front yet)."""
    n = len(corners)
    hs = [round(float(h), 3) for h in (heights or [0.0] * n)]
    breaks = [sorted(b) for b in breaks]
    from . import plotgeo
    before = doc.get("plot") or {}
    sb = {"sb_dist": dict(before.get("sb_dist") or {})}
    if setbacks is not None:
        sb.update(setbacks)
    elif not fresh and before.get("corners"):
        was = before["corners"]
        f = plotgeo.carry_sides(was, corners, before.get("sb_front") or
                                [False] * len(was), lambda a, b: a or b)
        c = plotgeo.carry_sides(was, corners, before.get("sb_custom") or
                                [None] * len(was))
        r = plotgeo.carry_sides(was, corners, before.get("sb_role") or
                                [None] * len(was))
        if f is not None and c is not None and r is not None:
            sb.update(sb_front=f, sb_custom=c, sb_role=r)
    sb.setdefault("sb_front", [False] * n)
    sb.setdefault("sb_custom", [None] * n)
    sb.setdefault("sb_role", [None] * n)
    doc = dict(doc)
    doc["plot"] = {"corners": [list(p) for p in corners], "uid": "",
                   "thickness": round(float(thickness), 3),
                   "heights": hs,
                   "closing": (n - 1 if closing is None else int(closing) % n),
                   "breaks": breaks, **sb,
                   # the survey is the land's, not the outline's: it stays
                   # through any redraw (points left outside just don't count)
                   "survey": [list(s) for s in before.get("survey") or []],
                   "contour": before.get("contour", 0.5)}
    if fresh:
        doc["digs"] = []             # a new plot: its old pits go with it
    doc = commit_terrain(viewport, key, doc, z, color)
    return doc["plot"]["uid"]


# ---- Walls ---------------------------------------------------------------------------
WALL_COLOR = (0.88, 0.86, 0.82)     # a plain wall: warm light grey


#: what the building is made of — every one rebuilt together
BUILT_KINDS = ("wall", "column", "beam", "slab", "footing", "opening",
               "roof", "ramp", "stair")
KIND_COLOR = {
    "roof": (0.66, 0.36, 0.27),        # tiles (each face has its own)
    "opening": (0.94, 0.94, 0.92),     # frames (each face has its own)
    "wall": WALL_COLOR,
    "column": (0.70, 0.71, 0.72),      # concrete
    "beam": (0.66, 0.67, 0.69),
    "slab": (0.76, 0.77, 0.78),
    "footing": (0.58, 0.58, 0.57),
    "ramp": (0.74, 0.74, 0.73),        # concrete, as the slabs (ramps.py)
    "stair": (0.76, 0.76, 0.75),       # concrete (stairs.py)
}


def _rec(g) -> dict:
    return (getattr(g, "ext", None) or {}).get(EXT_KEY) or {}


def wall_groups(viewport, level_id: str | None = None,
                kinds=("wall",)) -> list:
    """The groups of the walls (or other ``kinds``) — of one level."""
    out = []
    for g in viewport.scene.groups:
        if kind_of(g) not in kinds:
            continue
        if level_id is None or _rec(g).get("level") == level_id:
            out.append(g)
    return out


def built_ids(viewport) -> set:
    """The ids of every wall / structural element that has its group."""
    return {_rec(g).get("id") for g in wall_groups(viewport, None,
                                                   BUILT_KINDS)}


def outer_loop(pieces) -> list | None:
    """The outer contour of plan pieces put together (the host's
    shapely): the biggest outline, its holes filled."""
    try:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
    except ImportError:
        return None
    polys = []
    for pc in pieces:
        p = Polygon(pc["outer"], pc["holes"])
        if not p.is_valid:
            p = p.buffer(0)
        polys.append(p)
    u = unary_union(polys).buffer(1e-4, join_style=2).buffer(
        -1e-4, join_style=2)
    if u.is_empty:
        return None
    biggest = max(getattr(u, "geoms", [u]), key=lambda p: p.area)
    coords = list(biggest.exterior.coords)[:-1]
    return Polygon(coords).simplify(1e-4).exterior.coords[:-1]


#: ArchXQ's look at every command the host runs (edits.py): fn(history, cmd)
_AFTER_COMMAND = {"fn": None}


def watch_commands(fn) -> None:
    """``fn(history, cmd)`` runs after every command the host's history
    executes (its Move, Rotate, Copy… on ArchXQ's elements are adopted
    there). The class is wrapped once — a new document's history too —
    and ``fn=None`` takes ArchXQ out again (the wrapper stays, idle)."""
    from core.history import History
    _AFTER_COMMAND["fn"] = fn
    if getattr(History.execute, "_axq", False):
        return
    orig = History.execute

    def execute(self, cmd, *a, **kw):
        out = orig(self, cmd, *a, **kw)
        f = _AFTER_COMMAND["fn"]
        if f is not None:
            try:
                f(self, cmd)
            except Exception:  # noqa: BLE001 — never break the host's undo
                import traceback
                traceback.print_exc()
        return out
    execute._axq = True
    execute._orig = orig
    History.execute = execute


def join_last_steps(history, first) -> None:
    """The last two undo steps (``first`` and what ArchXQ ran right after
    it) become ONE: Ctrl+Z takes back the host's Move and the rebuild
    that followed it together."""
    from core.history import CompoundCommand
    st = history.undo_stack
    if len(st) < 2 or st[-2] is not first:
        return
    second = st.pop()
    both = CompoundCommand([first, second])
    if hasattr(first, "_history_mesh"):
        both._history_mesh = first._history_mesh
    st[-1] = both


def touch_scene(viewport) -> None:
    """The scene's drawing changed outside the undo history (a live
    preview): the host redraws it."""
    sc = viewport.scene
    try:
        sc.version += 1
    except (AttributeError, TypeError):
        pass
    if hasattr(viewport, "notify_scene_changed"):
        viewport.notify_scene_changed()
    else:
        viewport.update()


def select_ids(viewport, ids: set) -> None:
    """Select ArchXQ's groups of these element ids (after a rebuild)."""
    sel = getattr(viewport.scene, "selection", None)
    if not isinstance(sel, set):
        return
    sel.clear()
    sel.update(g for g in viewport.scene.groups if _rec(g).get("id") in ids)
    touch_scene(viewport)


def _unselect(scene, groups) -> None:
    """Groups taken out of the scene leave the selection too — else their
    outline stayed drawn until the next click (his screen, 2026-10-05)."""
    sel = getattr(scene, "selection", None)
    if isinstance(sel, set):
        sel.difference_update(groups)


def commit_build(viewport, key: str, doc: dict, elevations,
                 level_layer_of) -> dict:
    """Rebuild EVERY wall and structural element of the building from
    ``doc`` and store ``doc`` — ONE undo step. (A slab moves the walls
    under it; a wall's ends depend on its neighbours: the whole building
    is made again together.) One group per element, on its level's layer,
    tagged with its kind."""
    from core.history import CompoundCommand, SetPluginDataCommand
    viewport.history.execute(CompoundCommand(
        [building_swap(viewport, doc, elevations, level_layer_of),
         SetPluginDataCommand(key, doc)]))
    viewport.update()
    return doc


def mesh_of(faces):
    """A host mesh from ArchXQ's faces (plain loops, or {loop, holes,
    color} dicts)."""
    from core.mesh import Mesh
    from PySide6.QtGui import QVector3D
    mesh = Mesh()
    for f in faces:
        if isinstance(f, dict):
            face = mesh.add_face([QVector3D(*q) for q in f["loop"]],
                                 [[QVector3D(*q) for q in h]
                                  for h in f["holes"]])
            if f.get("color") is not None and face is not None:
                # glass, leaf… — the host wants RGB in "color" and the
                # alpha apart in "opacity" (the glTF/Blender export
                # unpacks exactly three values)
                c = tuple(f["color"])
                face.attrs["color"] = c[:3]
                if len(c) > 3 and c[3] < 1.0:
                    face.attrs["opacity"] = c[3]
        else:
            mesh.add_face([QVector3D(*q) for q in f])
    _soften_flat_seams(mesh)
    return mesh


def building_swap(viewport, doc: dict, elevations, level_layer_of):
    """The command that puts the building rebuilt from ``doc`` in place of
    the one in the scene (not executed: ``commit_build`` runs it — and the
    terrain's commit, when the slabs follow an excavation)."""
    from core.group import Group
    from core.history import Command
    from core.mesh import Mesh
    from PySide6.QtGui import QVector3D

    from . import edits
    from . import materials
    from . import structure as S

    layers = {lv["id"]: level_layer_of(lv["name"]) for lv in doc["levels"]}
    ensure_layers(viewport, list(layers.values()))
    new = []
    nth: dict = {}               # the groups of one element: 0, 1…
    for e in S.build(doc, elevations):
        g = Group(mesh_of(e["faces"]), name=e["name"])
        g.material = {"color": KIND_COLOR[e["kind"]], "opacity": 1.0}
        g.layer = layers[e["level"]]
        extra = {}
        if e.get("inwall"):              # hidden inside a wall (see ui)
            extra["inwall"] = True
        if e.get("okind"):               # door | window
            extra["okind"] = e["okind"]
        tag(g, e["kind"], id=e["id"], level=e["level"], **extra)
        # where it was built: the host's Move / Rotate / Copy is read from
        # it (edits.py)
        k = nth[e["id"]] = nth.get(e["id"], -1) + 1
        edits.stamp(g, k)
        materials.paint(viewport.scene, g, e["kind"], e["id"], doc)
        new.append(g)
    old = wall_groups(viewport, None, BUILT_KINDS)

    class _SwapWalls(Command):
        def do(self, scene) -> None:
            self._at = {id(g): scene.groups.index(g) for g in old
                        if g in scene.groups}
            for g in old:
                if g in scene.groups:
                    scene.groups.remove(g)
            scene.groups.extend(new)
            _unselect(scene, old)

        def undo(self, scene) -> None:
            for g in new:
                if g in scene.groups:
                    scene.groups.remove(g)
            for g in sorted(old, key=lambda g: self._at.get(id(g), 1e9)):
                if g not in scene.groups:
                    scene.groups.insert(min(self._at.get(id(g),
                                                         len(scene.groups)),
                                            len(scene.groups)), g)
            _unselect(scene, new)

    return _SwapWalls()


# ---- Camera / view ---------------------------------------------------------------
def standard_view(viewport, name: str) -> None:
    """top | front | right | back | left | iso — keeps the projection."""
    cam = viewport.camera
    persp = cam.perspective
    cam.set_view(name)
    cam.perspective = persp
    viewport.update()


#: the camera looks straight down when its pitch is this close to 90° —
#: tight: the host's orbit stops at ~89° (1.553 rad), and ANY orbit out
#: of the plan must read as leaving it
TOP_PITCH_TOL = 0.005        # rad (~0.3°)


def camera_state(viewport) -> dict:
    """Where the camera is: enough to put it back exactly."""
    from PySide6.QtGui import QVector3D
    cam = viewport.camera
    return {"target": QVector3D(cam.target), "yaw": float(cam.yaw),
            "pitch": float(cam.pitch), "distance": float(cam.distance),
            "perspective": bool(cam.perspective)}


def set_camera_state(viewport, s: dict) -> None:
    from PySide6.QtGui import QVector3D
    cam = viewport.camera
    cam.target = QVector3D(s["target"])
    cam.yaw, cam.pitch = s["yaw"], s["pitch"]
    cam.distance = s["distance"]
    cam.perspective = s["perspective"]
    viewport.update()


def is_top(s: dict) -> bool:
    """Looking straight down (any turn about the vertical)."""
    return s["pitch"] >= math.pi / 2 - TOP_PITCH_TOL


def plan_camera(viewport) -> None:
    """The plan: from the top, parallel, over what is looked at now."""
    cam = viewport.camera
    cam.set_view("top")
    cam.perspective = False
    viewport.update()


_STYLE_BEFORE = {}


def plan_style(viewport, on: bool) -> None:
    """The plan seen in HIDDEN LINE (his call, 2026-10-02 — compared with
    the host's «técnico» and Monochrome: the walls read best white on the
    background): the file's own style, face mode «hidden_line», as the 3D
    view's ``style_override`` — a VIEW change only: the document's style,
    the undo and «unsaved» are not touched. Off: what was there before."""
    import dataclasses
    if on:
        if "was" not in _STYLE_BEFORE:
            _STYLE_BEFORE["was"] = getattr(viewport, "style_override", None)
        base = getattr(viewport.scene, "display_style", None)
        if base is not None:
            viewport.style_override = dataclasses.replace(
                base, face_mode="hidden_line")
    elif "was" in _STYLE_BEFORE:
        viewport.style_override = _STYLE_BEFORE.pop("was")
    viewport.update()


_ORBITS = ("orbit", "orbit_about")


def lock_orbit(viewport, on: bool) -> None:
    """The plan is LOCKED to the top (his call, 2026-10-02): the mouse's
    orbit (``camera.orbit`` / ``orbit_about``, called by the 3D view's
    mouse-move) does nothing while it lasts — pan and zoom stay free."""
    cam = viewport.camera
    for name in _ORBITS:
        if on:
            setattr(cam, name, lambda *_a, **_k: None)
        elif name in getattr(cam, "__dict__", {}):
            delattr(cam, name)              # the class's own again


def fit_plan(viewport, points) -> None:
    """Frame these (x, y) points in the view (the plan over the plot)."""
    from PySide6.QtGui import QVector3D
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    viewport.camera.fit_box(QVector3D(min(xs), min(ys), 0.0),
                            QVector3D(max(xs), max(ys), 0.0))
    viewport.update()


def set_perspective(viewport, on: bool) -> None:
    viewport.camera.perspective = bool(on)
    viewport.update()


def is_perspective(viewport) -> bool:
    return bool(viewport.camera.perspective)


def zoom_extents(viewport) -> None:
    fn = getattr(viewport.window(), "_on_zoom_extents", None)
    if callable(fn):
        fn()


GRID_STEPS = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0)


def grid_step(viewport) -> float | None:
    """The plan grid's fine step on screen now (never under 14 px), or
    None out of a plan (a top, parallel view)."""
    import math
    try:
        if not is_top(camera_state(viewport)) or is_perspective(viewport):
            return None
        cam = viewport.camera
        tx, ty = float(cam.target.x()), float(cam.target.y())
        o = to_pixel(viewport, tx, ty, 0.0)
        e = to_pixel(viewport, tx + 1.0, ty, 0.0)
        if not o or not e:
            return None
        ppm = math.dist(o, e)
        return next((s for s in GRID_STEPS if s * ppm >= 14), GRID_STEPS[-1])
    except Exception:  # noqa: BLE001
        return None


def log_error(where: str) -> None:
    """The current exception's traceback, appended to ArchXQ's own log
    (next to the extension: …/ArchXQ_IT/archxq_errors.log)."""
    import datetime
    import traceback
    from pathlib import Path
    try:
        path = Path(__file__).resolve().parent.parent / "archxq_errors.log"
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] "
                    f"{where}\n{traceback.format_exc()}")
    except Exception:  # noqa: BLE001 — a log that can't be written
        pass


def document_path(window) -> str:
    """The open document's file ("" when it was never saved)."""
    return str(getattr(window, "_current_path", None) or "")


def flash(viewport, text: str, ms: int = 4000) -> None:
    try:
        viewport.flash_status(text, ms)
    except Exception:  # noqa: BLE001 — status text is cosmetic
        pass
