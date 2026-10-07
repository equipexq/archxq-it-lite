"""MATERIALS — what each element (and each PART of it) is made of.

His plan (``PLANO_MATERIAIS.md``, approved 2026-10-06): a «Material» tab
in every element's window, a VISUAL gallery of IngeTrazo's own library
(the same images and names its Materials panel shows) or a solid colour;
one material for an element, and «Use for all ‹columns›» for its kind;
PARTS where it makes sense (the plot's top / sides, a pit's floor / walls,
a slab's top / underside…).

The choice is STORED, never only painted: ArchXQ makes its groups anew at
every change, so ``doc["materials"]`` keeps it and every rebuild paints it
again (compat calls ``paint``)::

    doc["materials"] = {"el":   {element id: {part: ref}},   # its own
                        "type": {kind: {part: ref}}}         # «for all»
    ref = {"lib": "concrete/concrete_exposed.png"}   # IngeTrazo's library
        | {"color": [r, g, b], "name": "RAL 7035 Light grey"}

An element's part: its own ref → its kind's → none (ArchXQ's plain colour,
as before). Solid colours in the Lite; the textures are the Pro's.
"""
from __future__ import annotations

import json
import os
import sys

from . import edition

#: an element kind's PARTS: (key, label). One part = the whole element.
SLOTS = {
    "plot": (("top", "Top (the ground)"), ("side", "Sides")),
    "dig": (("floor", "Floor"), ("wall", "Walls and slopes")),
    "fill": (("top", "Top"), ("wall", "Slopes")),
    "column": (("all", "Column"),),
    "beam": (("all", "Beam"),),
    "slab": (("top", "Top"), ("under", "Underside and edges")),
    "footing": (("all", "Footing"),),
    "wall": (("all", "Wall"),),
    "ramp": (("top", "Floor"), ("side", "Sides")),
    "stair": (("top", "Treads"), ("side", "Sides")),
}
PLURAL = {"plot": "plots", "dig": "excavations", "fill": "fills",
          "column": "columns", "beam": "beams", "slab": "slabs",
          "footing": "footings", "wall": "walls", "ramp": "ramps",
          "stair": "stairs"}
MAT_PREFIX = "ArchXQ · "


def textures_allowed() -> bool:
    return not edition.lite()


# ---- IngeTrazo's library ---------------------------------------------------------
_LIB = None
_RAL = None


def _resources() -> str:
    for base in (getattr(sys, "_MEIPASS", None),
                 os.path.join(os.path.dirname(sys.executable), "_internal")):
        if base and os.path.isdir(os.path.join(base, "resources")):
            return os.path.join(base, "resources")
    return ""


CATEGORY_NAMES = {"brick": "Brick", "concrete": "Concrete", "stone": "Stone",
                  "wood": "Wood", "roof": "Roofing", "floor": "Flooring",
                  "metal": "Metal", "ground": "Ground", "glass": "Glass",
                  "water": "Water", "wall": "Wall", "wallpaper": "Wallpaper",
                  "fabric": "Fabric", "rug": "Rug", "sky": "Sky",
                  "misc": "Miscellaneous"}


def library() -> list[dict]:
    """IngeTrazo's texture library: [{"id", "name", "items": [{"file",
    "name", "path", "sw", "sh"}]}] — read once."""
    global _LIB
    if _LIB is None:
        _LIB = []
        root = os.path.join(_resources(), "textures")
        try:
            with open(os.path.join(root, "library.json"), encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, ValueError):
            raw = {}
        for c in raw.get("categories") or []:
            items = []
            for it in c.get("items") or []:
                rel = str(it.get("file", "")).split("/")
                # the images live under textures\library\ (the manifest's
                # paths are relative to it); next to the manifest as well
                path = os.path.join(root, "library", *rel)
                if not os.path.isfile(path):
                    path = os.path.join(root, *rel)
                if os.path.isfile(path):
                    name = str(it.get("name") or rel[-1].rsplit(".", 1)[0])
                    if "_" in name and " " not in name:    # concrete_exposed
                        name = name.replace("_", " ").capitalize()
                    items.append({"file": it["file"], "name": name,
                                  "path": path,
                                  "sw": float(it.get("sw", 1.0)),
                                  "sh": float(it.get("sh", 1.0))})
            if items:
                _LIB.append({"id": c.get("id", ""),
                             "name": CATEGORY_NAMES.get(c.get("id"),
                                                        str(c.get("id"))),
                             "items": items})
    return _LIB


def ral() -> list[dict]:
    """IngeTrazo's RAL Classic colours: [{"name", "colors": [{"code",
    "name", "rgb"}]}]."""
    global _RAL
    if _RAL is None:
        try:
            with open(os.path.join(_resources(), "colors", "ral.json"),
                      encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, ValueError):
            raw = {}
        _RAL = [{"name": fam.get("name", ""), "colors": fam.get("colors") or []}
                for fam in raw.get("families") or []]
    return _RAL


def lib_item(file: str) -> dict | None:
    for c in library():
        for it in c["items"]:
            if it["file"] == file:
                return it
    return None


# ---- refs -------------------------------------------------------------------------
def ref_label(ref) -> str:
    if not ref:
        return "Default"
    if "lib" in ref:
        it = lib_item(ref["lib"])
        return it["name"] if it else ref["lib"]
    return ref.get("name") or "#%02x%02x%02x" % tuple(
        int(round(v * 255)) for v in ref["color"][:3])


def valid_ref(ref) -> dict | None:
    """A ref as stored (None: not one) — a texture only where allowed."""
    if not isinstance(ref, dict):
        return None
    if isinstance(ref.get("lib"), str):
        return {"lib": ref["lib"]}
    c = ref.get("color")
    try:
        rgb = [min(max(float(v), 0.0), 1.0) for v in c][:3]
    except (TypeError, ValueError):
        return None
    if len(rgb) != 3:
        return None
    out = {"color": rgb}
    if ref.get("name"):
        out["name"] = str(ref["name"])
    return out


def attrs(ref) -> tuple[str, dict] | None:
    """(material name, the attrs it paints a face with) — None: nothing
    (an unknown texture, or a texture in the Lite: the plain colour)."""
    from core.materials import Material
    if not ref:
        return None
    if "lib" in ref:
        it = lib_item(ref["lib"])
        if it is None or not textures_allowed():
            return None
        m = Material(MAT_PREFIX + it["name"],
                     texture={"path": it["path"], "sw": it["sw"],
                              "sh": it["sh"]})
    else:
        m = Material(MAT_PREFIX + ref_label(ref),
                     color=tuple(ref["color"][:3]))
    return m.name, m.face_attrs()


# ---- where a choice is kept --------------------------------------------------------
def resolve(doc: dict, kind: str, el_id: str | None, part: str):
    m = doc.get("materials") or {}
    own = (m.get("el") or {}).get(el_id or "", {})
    if part in own:
        return own[part]
    return ((m.get("type") or {}).get(kind) or {}).get(part)


def kind_of_id(doc: dict) -> dict:
    """{element id: its kind} — everything a material can be given to."""
    out = {"plot": "plot"} if doc.get("plot") else {}
    for d in doc.get("digs") or []:
        out[d["id"]] = "fill" if d.get("kind") == "fill" else "dig"
    for w in doc.get("walls") or []:
        out[w["id"]] = "wall"
    for e in doc.get("structure") or []:
        out[e["id"]] = e["type"]
    return out


def clean(raw, doc: dict) -> dict:
    """``doc["materials"]`` as stored, whatever the file holds: refs that
    are refs, elements that still exist, parts their kind has."""
    raw = raw if isinstance(raw, dict) else {}
    kinds = kind_of_id(doc)
    out = {"el": {}, "type": {}}
    for eid, parts in (raw.get("el") or {}).items():
        k = kinds.get(eid)
        if k not in SLOTS or not isinstance(parts, dict):
            continue
        keep = {p: r for p, r in ((p, valid_ref(r)) for p, r in parts.items())
                if r and p in dict(SLOTS[k])}
        if keep:
            out["el"][eid] = keep
    for k, parts in (raw.get("type") or {}).items():
        if k not in SLOTS or not isinstance(parts, dict):
            continue
        keep = {p: r for p, r in ((p, valid_ref(r)) for p, r in parts.items())
                if r and p in dict(SLOTS[k])}
        if keep:
            out["type"][k] = keep
    return out


def merge(doc: dict, change: dict) -> dict:
    """``doc`` with a window's material change in it. ``change`` = {"kind",
    "id", "parts": {part: ref | None}, "all": bool} — «all»: the kind's
    material too, and the other elements of the kind follow it (their own
    choice for that part is let go)."""
    doc = dict(doc)
    m = doc.get("materials") or {}
    els = {k: dict(v) for k, v in (m.get("el") or {}).items()}
    types = {k: dict(v) for k, v in (m.get("type") or {}).items()}
    kind, eid = change["kind"], change.get("id") or ""
    kinds = kind_of_id(doc)
    for part, ref in change["parts"].items():
        if change.get("all"):
            t = types.setdefault(kind, {})
            if ref:
                t[part] = ref
            else:
                t.pop(part, None)
            for other, k in kinds.items():
                if k == kind and part in els.get(other, {}):
                    els[other].pop(part)
        else:
            own = els.setdefault(eid, {})
            if ref:
                own[part] = ref
            else:
                own.pop(part, None)
    doc["materials"] = {"el": {k: v for k, v in els.items() if v},
                        "type": {k: v for k, v in types.items() if v}}
    return doc


# ---- painting a group (compat calls it on every rebuild) ---------------------------
def part_of(kind: str, nz: float) -> str:
    """Which part a face is, by its normal's z."""
    if kind == "plot":
        return "top" if nz > 0.3 else "side"
    if kind == "dig":
        return "floor" if nz > 0.97 else "wall"
    if kind == "fill":
        return "top" if nz > 0.97 else "wall"
    if kind == "slab":
        return "top" if nz > 0.9 else "under"
    if kind in ("ramp", "stair"):
        return "top" if nz > 0.5 else "side"
    return "all"


def paint(scene, group, kind: str, el_id: str | None, doc: dict) -> None:
    """Paint one rebuilt group with its element's materials (nothing
    chosen: as ArchXQ always drew it). Faces with a colour of their own
    (a door's glass, a frame) keep it."""
    if kind not in SLOTS or not doc.get("materials"):
        return
    from core.materials import Material, register
    made = {}
    for part, _label in SLOTS[kind]:
        a = attrs(resolve(doc, kind, el_id, part))
        if a is not None:
            made[part] = a
    if not made:
        return
    reg = getattr(scene, "materials", None)
    for name, a in made.values():
        if isinstance(reg, dict):
            try:
                register(reg, Material.from_dict(dict(
                    {k: v for k, v in a.items() if k != "mat"}, name=name)))
            except Exception:  # noqa: BLE001 — the paint matters, not the name
                pass
    # FACE by face, even for a one-part element: a group's own material
    # showed at first and was lost at the next redraw (his columns, beams
    # and footings, 2026-10-07) — the faces' attrs are what the host keeps
    for f in group.mesh.faces:
        if "color" in f.attrs and "mat" not in f.attrs:
            continue                              # its own (glass, frame)
        n = f.normal() if callable(f.normal) else f.normal
        part = part_of(kind, n.z())
        if part in made:
            f.attrs.update(made[part][1])


# ---- the gallery (the «Material» tab) ----------------------------------------------
def material_tab(kind: str, el_id: str | None, doc: dict):
    """The «Material» tab of an element's window — None when its kind has
    no materials yet."""
    if kind not in SLOTS:
        return None
    return MaterialTab(kind, el_id, doc)


def _qt():
    from PySide6 import QtCore, QtGui, QtWidgets
    return QtCore, QtGui, QtWidgets


THUMB = 64
_PIX: dict = {}


def thumb(ref, size: int = THUMB):
    """A ref's picture: the texture's image, or a swatch of its colour."""
    QtCore, QtGui, _w = _qt()
    key = (repr(ref), size)
    if key in _PIX:
        return _PIX[key]
    pm = QtGui.QPixmap(size, size)
    if ref and "lib" in ref:
        it = lib_item(ref["lib"])
        img = QtGui.QPixmap(it["path"]) if it else QtGui.QPixmap()
        if img.isNull():
            pm.fill(QtGui.QColor("#555"))
        else:
            pm = img.scaled(size, size, QtCore.Qt.KeepAspectRatioByExpanding,
                            QtCore.Qt.SmoothTransformation).copy(0, 0, size,
                                                                 size)
    elif ref:
        pm.fill(QtGui.QColor.fromRgbF(*ref["color"][:3]))
    else:                                  # «Default»: a crossed swatch
        pm.fill(QtGui.QColor("#3a4048"))
        p = QtGui.QPainter(pm)
        p.setPen(QtGui.QPen(QtGui.QColor("#8a939d"), 2))
        p.drawLine(4, size - 4, size - 4, 4)
        p.end()
    _PIX[key] = pm
    return pm


def _section(title: str, fill_fn, opened: bool = False):
    """A foldable section: an arrow + title; its body is built the first
    time it opens (hundreds of images — as IngeTrazo's own panel does)."""
    QtCore, _g, W = _qt()
    box = W.QWidget()
    lay = W.QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    head = W.QToolButton()
    head.setText(title)
    head.setCheckable(True)
    head.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
    head.setStyleSheet("QToolButton { border: none; font-weight: bold; "
                       "padding: 4px 2px; text-align: left; }")
    head.setSizePolicy(W.QSizePolicy.Expanding, W.QSizePolicy.Fixed)
    body = W.QWidget()
    body.hide()
    lay.addWidget(head)
    lay.addWidget(body)
    built = []

    def toggle(on: bool) -> None:
        head.setArrowType(QtCore.Qt.DownArrow if on else QtCore.Qt.RightArrow)
        if on and not built:
            fill_fn(body)
            built.append(True)
        body.setVisible(on)
    head.toggled.connect(toggle)
    head.setArrowType(QtCore.Qt.RightArrow)
    if opened:
        head.setChecked(True)
    return box


class MaterialTab:
    """Left: the element's parts, each with its material; right: the
    gallery (IngeTrazo's textures by category, the RAL colours, a solid
    colour of one's own); under it: «Use for all ‹kind›» and «Default»."""

    COLS = 6

    def __init__(self, kind: str, el_id: str | None, doc: dict) -> None:
        QtCore, QtGui, W = _qt()
        self.kind, self.el_id = kind, el_id
        self.parts = list(SLOTS[kind])
        self.start = {p: resolve(doc, kind, el_id, p) for p, _l in self.parts}
        self.now = dict(self.start)
        self.part = self.parts[0][0]
        self.widget = w = W.QWidget()
        w.setMinimumSize(600, 380)
        root = W.QHBoxLayout(w)

        left = W.QVBoxLayout()
        self.big = W.QLabel()
        self.big.setFixedSize(132, 132)
        self.big.setScaledContents(True)
        left.addWidget(self.big)
        self.name = W.QLabel()
        self.name.setWordWrap(True)
        self.name.setMaximumWidth(150)
        left.addWidget(self.name)
        self.list = W.QListWidget()
        self.list.setIconSize(QtCore.QSize(28, 28))
        self.list.setMaximumWidth(150)
        for p, label in self.parts:
            self.list.addItem(W.QListWidgetItem(label))
        self.list.setCurrentRow(0)
        self.list.currentRowChanged.connect(self._pick_part)
        if len(self.parts) == 1:
            self.list.hide()
        left.addWidget(self.list, 1)
        root.addLayout(left)

        right = W.QVBoxLayout()
        scroll = W.QScrollArea()
        scroll.setWidgetResizable(True)
        inner = W.QWidget()
        self.sections = W.QVBoxLayout(inner)
        self.sections.setContentsMargins(2, 2, 2, 2)
        self.sections.setSpacing(2)
        cur = self.now.get(self.part) or {}
        cur_cat = (cur.get("lib") or "").split("/")[0]
        if textures_allowed():
            for c in library():
                self.sections.addWidget(_section(
                    f"{c['name']}  ({len(c['items'])})",
                    lambda body, c=c: self._grid(
                        body, [({"lib": it["file"]}, it["name"])
                               for it in c["items"]]),
                    opened=c["id"] == cur_cat))
        else:
            note = W.QLabel("Textures are in ArchXQ IT Pro — "
                            f"{edition.PRO_URL}. Solid colours below.")
            note.setWordWrap(True)
            note.setEnabled(False)
            self.sections.addWidget(note)
        for fam in ral():
            self.sections.addWidget(_section(
                f"Colours · {fam['name']}  ({len(fam['colors'])})",
                lambda body, fam=fam: self._grid(
                    body, [({"color": [float(v) for v in c["rgb"]],
                             "name": f"{c['code']} {c['name']}"},
                            f"{c['code']} — {c['name']}")
                           for c in fam["colors"]])))
        self.sections.addStretch()
        scroll.setWidget(inner)
        right.addWidget(scroll, 1)

        row = W.QHBoxLayout()
        own = W.QPushButton("Solid colour…")
        own.clicked.connect(self._own_colour)
        row.addWidget(own)
        dflt = W.QPushButton("Default")
        dflt.setToolTip("Back to ArchXQ's own colour for this part")
        dflt.clicked.connect(lambda: self._choose(None))
        row.addWidget(dflt)
        row.addStretch()
        self.all = W.QCheckBox(f"Use for all {PLURAL.get(kind, kind)}")
        self.all.setToolTip(f"Every {kind} in the project takes it (one "
                            "that had its own for this part, too)")
        row.addWidget(self.all)
        right.addLayout(row)
        root.addLayout(right, 1)
        self._show()

    # -- the gallery ----------------------------------------------------------------
    def _grid(self, body, refs) -> None:
        QtCore, QtGui, W = _qt()
        g = W.QGridLayout(body)
        g.setContentsMargins(4, 0, 4, 6)
        g.setSpacing(4)
        for n, (ref, tip) in enumerate(refs):
            b = W.QToolButton()
            b.setIcon(QtGui.QIcon(thumb(ref)))
            b.setIconSize(QtCore.QSize(THUMB, THUMB))
            b.setToolTip(tip)
            b.setAutoRaise(True)
            b.clicked.connect(lambda _c=False, r=ref: self._choose(r))
            g.addWidget(b, n // self.COLS, n % self.COLS)

    def _own_colour(self) -> None:
        _c, QtGui, W = _qt()
        cur = self.now.get(self.part)
        start = QtGui.QColor.fromRgbF(*cur["color"][:3]) \
            if cur and "color" in cur else QtGui.QColor("#b0b0b0")
        c = W.QColorDialog.getColor(start, self.widget, "Solid colour")
        if c.isValid():
            self._choose({"color": [round(c.redF(), 4), round(c.greenF(), 4),
                                    round(c.blueF(), 4)]})

    # -- the parts ------------------------------------------------------------------
    def _pick_part(self, row: int) -> None:
        if 0 <= row < len(self.parts):
            self.part = self.parts[row][0]
            self._show()

    def _choose(self, ref) -> None:
        self.now[self.part] = ref
        self._show()

    def _show(self) -> None:
        QtCore, QtGui, _w = _qt()
        ref = self.now.get(self.part)
        self.big.setPixmap(thumb(ref, 132))
        label = dict(self.parts)[self.part]
        self.name.setText(f"<b>{label}</b><br>{ref_label(ref)}")
        for i, (p, _l) in enumerate(self.parts):
            self.list.item(i).setIcon(QtGui.QIcon(thumb(self.now.get(p), 28)))

    # -- the result -----------------------------------------------------------------
    def change(self) -> dict | None:
        """What to store (``merge``), None: nothing changed."""
        parts = {p: r for p, r in self.now.items() if r != self.start.get(p)}
        if self.all.isChecked():           # «for all»: every part shown now
            parts = dict(self.now)
        if not parts:
            return None
        return {"kind": self.kind, "id": self.el_id, "parts": parts,
                "all": self.all.isChecked()}


def with_tab(dlg, tab: MaterialTab) -> None:
    """Put a window's content under an «Element» tab and the material
    under «Material» — its buttons (OK, Cancel, Apply…) stay below both."""
    _c, _g, W = _qt()
    lay = dlg.layout()
    page = W.QWidget()
    pl = W.QVBoxLayout(page)
    pl.setContentsMargins(0, 0, 0, 0)
    keep = []
    while lay.count():
        it = lay.takeAt(0)
        w = it.widget()
        if isinstance(w, W.QDialogButtonBox):
            keep.append(it)
            # the rest after the buttons stays after them
            while lay.count():
                keep.append(lay.takeAt(0))
            break
        if w is not None:
            pl.addWidget(w)
        elif it.layout() is not None:
            sub = it.layout()
            sub.setParent(None)
            pl.addLayout(sub)
        else:
            pl.addItem(it)
    tabs = W.QTabWidget()
    tabs.addTab(page, "Element")
    tabs.addTab(tab.widget, "Material")
    lay.addWidget(tabs, 1)
    for it in keep:
        if it.widget() is not None:
            lay.addWidget(it.widget())
        elif it.layout() is not None:
            sub = it.layout()
            sub.setParent(None)
            lay.addLayout(sub)
        else:
            lay.addItem(it)
    dlg._mat_tab = tab
