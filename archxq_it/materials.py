# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
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

An element's part: its own ref → its kind's → its kind's ``DEFAULTS`` (Pro)
→ none (ArchXQ's plain colour, as before). Solid colours in the Lite; the
textures are the Pro's.
"""
from __future__ import annotations

import copy
import json
import os
import queue
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

from . import edition
from . import matfav as MF
from . import webtex as WT
from .i18n import tr

#: an element kind's PARTS: (key, label). One part = the whole element.
SLOTS = {
    "plot": (("top", "Top (the ground)"), ("side", "Sides")),
    "dig": (("floor", "Floor"), ("wall", "Walls and slopes")),
    "fill": (("top", "Top"), ("wall", "Slopes")),
    "column": (("all", "Column"), ("orn", "Base and capital")),
    "beam": (("all", "Beam"),),
    "slab": (("top", "Top"), ("under", "Underside and edges")),
    # a room's floor on a layered slab (2026-10-23): its finishes on the
    # core — the top one first (``slots`` lists them all)
    "floor": (("top", "Floor finish"),),
    "footing": (("all", "Footing"),),
    "wall": (("all", "Wall"),),
    "ramp": (("top", "Floor"), ("side", "Sides"),
             ("rail", "Railing (posts, handrail)"), ("glass", "Railing glass"),
             ("lowwall", "Low wall")),
    "stair": (("top", "Treads"), ("side", "Sides"),
              ("rail", "Railing (posts, handrail)"), ("glass", "Railing glass"),
              ("lowwall", "Low wall")),
    "guard": (("lowwall", "Wall"), ("pier", "Piers"), ("cap", "Coping"),
              ("rail", "Steel (posts, rails)"), ("glass", "Glass")),
    # a street (streets.py): each part by the colour it is built with
    "street": (("asphalt", "Asphalt"), ("curb", "Curb"),
               ("walk", "Sidewalk"), ("paint", "Centre line")),
    # a profile along a path (along.py): the moulding itself
    "profile": (("all", "Profile"),),
    # copies along a path (copies.py): each object keeps its own colours
    "copy": (("all", "Copies"),),
    # a piece adopted as it is (shaped.py): its own look, until one is chosen
    "shaped": (("all", "Piece"),),
    "roof": (("cover", "Covering (tiles, sheets)"),
             ("parapet", "Parapet and gable walls"),
             ("gutter", "Gutter"), ("slab", "Slab (flat, hidden)")),
    # a door / window: each part its own (trim.py, his ask 2026-10-19 —
    # the glass keeps its own: see-through or opaque, in the library)
    "opening": (("frame", "Frame"), ("leaf", "Leaf (door, sash)"),
                ("trim", "Trim"), ("sill", "Stone sill"),
                ("hardware", "Handles")),
}
PLURAL = {"plot": "plots", "dig": "excavations", "fill": "fills",
          "column": "columns", "beam": "beams", "slab": "slabs",
          "floor": "floors",
          "footing": "footings", "wall": "walls", "ramp": "ramps",
          "stair": "stairs", "roof": "roofs", "guard": "low walls",
          "street": "streets", "profile": "profiles", "copy": "copies",
          "shaped": "adopted pieces", "opening": "doors and windows"}
MAT_PREFIX = "ArchXQ · "
#: kinds whose faces carry colours of their own on purpose (a door's glass
#: and frame) — kept under a material. Ramps and stairs carry their plain
#: concrete per face too, but that one IS what a material replaces (his
#: stair stayed grey under «Use for all», 2026-10-08); a roof's colours
#: tell its PARTS apart (``roof_part``)
#: (a wall: a CURTAIN wall's glass, mullions and band carry their colours;
#: a plain wall's faces carry none — they take its material)
#: (copies: a tree's bark and leaves, an object's own — copies.py)
KEEP_OWN_COLOURS = {"opening", "wall", "copy"}


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
    if WT.is_ref(ref):
        return WT.clean_ref(ref)
    if isinstance(ref.get("lib"), str):
        out = {"lib": ref["lib"]}
        try:
            sw, sh = float(ref["sw"]), float(ref["sh"])
        except (KeyError, TypeError, ValueError):
            return out
        if 0 < sw < 1e4 and 0 < sh < 1e4:  # (not NaN either)
            out.update(sw=sw, sh=sh)
        return out
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


SIZE_MIN, SIZE_MAX = 0.05, 20.0     # how wide one tile of a texture can be


def tex_size(ref) -> tuple | None:
    """(width, height) in metres of one tile of a texture ref (None: not a
    texture) — its own, or the library's."""
    if WT.is_ref(ref):
        return float(ref["sw"]), float(ref["sh"])
    it = lib_item(ref["lib"]) if ref and "lib" in ref else None
    if it is None:
        return None
    if "sw" in ref and "sh" in ref:
        return float(ref["sw"]), float(ref["sh"])
    return it["sw"], it["sh"]


def sized(ref, width: float) -> dict:
    """The texture ref at this width, its proportion kept (his ask, 09/11:
    most come out too small on a wall); at the library's width, a plain ref —
    so a project stays as it was."""
    if WT.is_ref(ref):
        return WT.sized(ref, width)
    it = lib_item(ref["lib"])
    if it is None or abs(width - it["sw"]) < 1e-4:
        return {"lib": ref["lib"]}
    return {"lib": ref["lib"], "sw": round(width, 4),
            "sh": round(width * it["sh"] / it["sw"], 4)}


def _embedded(stem: str) -> str | None:
    """A project opened on another computer: the image the host took out of
    the project file, under any size of this material."""
    try:
        mats = sys.modules[__package__]._instance.viewport.scene.materials
        for name, m in mats.items():
            if name == stem or name.startswith(stem + " · "):
                path = (getattr(m, "texture", None) or {}).get("path")
                if path and os.path.isfile(path):
                    return path
    except Exception:  # noqa: BLE001 — no project yet
        pass
    return None


def attrs(ref) -> tuple[str, dict] | None:
    """(material name, the attrs it paints a face with) — None: nothing
    (an unknown texture, or a texture in the Lite: the plain colour)."""
    from core.materials import Material
    if not ref:
        return None
    if WT.is_ref(ref):
        if not textures_allowed():
            return None
        stem = MAT_PREFIX + WT.label_of(ref)
        path = WT.ref_path(ref) or _embedded(stem)
        if path is None:
            return None
        custom = abs(ref["sw"] - ref["w0"]) >= 1e-4
        m = Material(stem + (f" · {ref['sw']:g} m" if custom else ""),
                     texture={"path": path, "sw": ref["sw"], "sh": ref["sh"]})
        return m.name, m.face_attrs()
    if "lib" in ref:
        it = lib_item(ref["lib"])
        if it is None or not textures_allowed():
            return None
        sw, sh = tex_size(ref)
        # (its size in the name: two sizes are two materials in the host)
        m = Material(MAT_PREFIX + it["name"]
                     + ("" if "sw" not in ref else f" · {sw:g} m"),
                     texture={"path": it["path"], "sw": sw, "sh": sh})
    else:
        m = Material(MAT_PREFIX + ref_label(ref),
                     color=tuple(ref["color"][:3]))
    return m.name, m.face_attrs()


def _wall(doc: dict, el_id) -> dict | None:
    return next((w for w in doc.get("walls") or [] if w["id"] == el_id),
                None)


def _grid_of(w: dict | None) -> dict | None:
    """A grid wall's ``gw`` (cleaned) — None: any other wall, the Lite."""
    if not w or not w.get("gw") or w.get("cw"):
        return None
    try:
        from . import gridwall as GX
    except ImportError:
        return None
    return GX.of(w)


def slots(kind: str, el_id: str | None, doc: dict) -> list:
    """An element's parts — a wall with LAYERS (0.15.0): each layer, outside
    → inside; its core is the wall's own part («all»: «Use for all walls»
    still reaches it), each finish «L:<its id>»."""
    if kind == "column" and el_id:
        # (its base and capital are a part only when it has them)
        c = next((e for e in doc.get("structure") or []
                  if e.get("id") == el_id), None)
        if not (c and (c.get("cbase") or c.get("ccap"))):
            return SLOTS["column"][:1]
    if kind == "wall" and el_id:
        w = _wall(doc, el_id)
        g = _grid_of(w)
        if g is not None:
            # a GRID WALL (gridwall.py): its frame, its glass, its panels
            from . import gridwall as GX
            return [(k, tr(label)) for k, label in GX.PARTS]
        ls = (w or {}).get("layers") or []
        # a LIGHT-FRAMED core (framing.py): its studs are the core's part,
        # the insulation between them one of its own («fill»)
        from .framing import frame_of
        fr = frame_of(w) if w else None
        if len(ls) > 1 or fr is not None:
            out = [("all", tr("{name} (core)",
                              name=la.get("name") or tr("Core")))
                   if la.get("role") == "core"
                   else ("L:" + str(la.get("id")), la.get("name")
                         or "Finish")
                   for la in ls] if len(ls) > 1 else [("all", tr("Studs"))]
            if fr is not None and fr["fill"] == "insulation":
                out.append(("fill", tr("Insulation")))
            return out
    if kind == "slab" and el_id:
        # a slab with LAYERS (top → bottom): the top one is its «Top» (the
        # slabs' «Use for all» paves it), its core its «Underside and
        # edges», each other finish «L:<its id>»
        s = next((e for e in doc.get("structure") or []
                  if e.get("id") == el_id), None)
        ls = (s or {}).get("layers") or []
        # a LIGHT-FRAMED core (joists — PLANO_PISOS_BARROTES): the core's
        # part, its insulation one of its own
        from .structure import slab_frame
        sfr = slab_frame(s) if s else None
        fill = [("fill", tr("Insulation"))]             if sfr is not None and sfr["fill"] == "insulation" else []
        if sfr is not None and not (len(ls) > 1):
            return [("under", tr("Joists"))] + fill
        if len(ls) > 1 and not s.get("ceiling") and not s.get("block"):
            out = []
            for i, la in enumerate(ls):
                name = la.get("name") or ""
                if i == 0 and la.get("role") != "core":
                    out.append(("top", name or tr("Top")))
                elif la.get("role") == "core":
                    out.append(("under", tr("{name} (core)",
                                            name=name or tr("Core"))))
                else:
                    out.append(("L:" + str(la.get("id")), name or "Finish"))
            return out + fill
    if kind == "roof" and el_id:
        # a roof with LAYERS (top → bottom — PLANO_TELHADO_CAMADAS): the
        # top one is its «Covering» (the roofs' «Use for all» reaches it,
        # as before), each other one «L:<its id>»; its gable walls and
        # gutter as before
        r = next((e for e in doc.get("structure") or []
                  if e.get("id") == el_id), None)
        ls = (r or {}).get("layers") or []
        # (a FRAMED core — step 2b: its rafters are the core's part — or
        # «Rafters» with no layers —, the insulation one of its own)
        from .framing import clean_frame
        fr = clean_frame((r or {}).get("frame"))
        if len(ls) > 1 or fr is not None:
            out = [("cover", (ls[0].get("name") if len(ls) > 1 else "")
                    or tr("Covering"))]
            for la in ls[1:]:
                name = la.get("name") or tr("Layer")
                out.append(("L:" + str(la.get("id")),
                            tr("{name} (core)", name=name)
                            if la.get("role") == "core" else name))
            if fr is not None:
                if len(ls) < 2:
                    out.append(("rafters", tr("Rafters")))
                if fr["fill"] == "insulation":
                    out.append(("fill", tr("Insulation")))
            return out + [p for p in SLOTS["roof"]
                          if p[0] in ("parapet", "gutter")]
    if kind == "floor" and el_id:
        # a room's floor: its slab's layers ON the core, the same parts
        # (nothing chosen for the room: the slab's own)
        s = _floor_slab(doc, el_id)
        ls = (s or {}).get("layers") or []
        core = next((i for i, la in enumerate(ls)
                     if la.get("role") == "core"), 0)
        out = [("top" if i == 0 else "L:" + str(la.get("id")),
                la.get("name") or tr("Floor finish"))
               for i, la in enumerate(ls[:core])]
        if out:
            return out
    return list(SLOTS[kind])


def _floor_slab(doc: dict, fid: str) -> dict | None:
    """The slab a room's floor lies on."""
    from .structure import parse_floor_id
    p = parse_floor_id(fid)
    if p is None:
        return None
    return next((e for e in doc.get("structure") or []
                 if e.get("id") == p[0]), None)


def _part_ok(kind: str, eid: str, part: str, doc: dict) -> bool:
    if part in dict(SLOTS[kind]):
        return True
    return kind in ("wall", "slab", "floor") \
        and part in dict(slots(kind, eid, doc))


# ---- where a choice is kept --------------------------------------------------------
def wall_type_of(doc: dict, el_id: str | None) -> str | None:
    """The id of YOUR wall type a wall is of (one that still exists)."""
    w = _wall(doc, el_id) if el_id else None
    tid = (w or {}).get("type")
    if tid and any(t.get("id") == tid for t in doc.get("wall_types") or ()):
        return tid
    return None


def resolve(doc: dict, kind: str, el_id: str | None, part: str):
    """A part's material: the element's own → its WALL TYPE's (the look
    lives in the type: every wall of it, drawn, split or copied, wears it
    — his ask, 31/10) → its kind's («Use for all»)."""
    m = doc.get("materials") or {}
    own = (m.get("el") or {}).get(el_id or "", {})
    if part in own:
        return own[part]
    if kind == "wall":
        tid = wall_type_of(doc, el_id)
        mine = (m.get("wtype") or {}).get(tid) if tid else None
        if mine and part in mine:
            return mine[part]
    ref = ((m.get("type") or {}).get(kind) or {}).get(part)
    if ref is None and kind == "floor" and el_id:
        # nothing chosen for the room's floor: its slab's
        s = _floor_slab(doc, el_id)
        if s is not None:
            return resolve(doc, "slab", s["id"], part)
    return ref


def look_key(doc: dict, kind: str, el_id: str | None) -> str:
    """ALL that ``paint`` reads for one element, as a key: its parts, its
    own, its wall type's, its kind's (a room's floor: its slab's too).
    Equal = painted the same (compat.build_sig: a material changed on one
    wall rebuilt the whole building — 402 groups, 2.3 s — his test 01/11)."""
    m = doc.get("materials") or {}
    els, kinds = m.get("el") or {}, m.get("type") or {}
    parts = [p for p, _l in slots(kind, el_id, doc)] if kind in SLOTS else []
    key = [kind, parts, els.get(el_id or ""), kinds.get(kind)]
    if kind == "wall":
        tid = wall_type_of(doc, el_id)
        key += [tid, (m.get("wtype") or {}).get(tid) if tid else None]
    elif kind == "slab":
        key.append(any(e.get("id") == el_id and e.get("ceiling")
                       for e in doc.get("structure") or ()))
    elif kind == "floor" and el_id:
        s = _floor_slab(doc, el_id)
        if s is not None:
            key += [s["id"], els.get(s["id"]), kinds.get("slab")]
    return repr(key)


def wall_face_mat(doc: dict, el: dict, color) -> str:
    """What a wall's face wears, as ``paint`` gives it — a key, equal for
    the same material (``seams``: a joint between two walls is hidden
    only when both sides match). A layer's finish with nothing chosen
    wears the core's («all»)."""
    part = "all"
    names = [p for p, _l in slots("wall", el.get("id"), doc)]
    if len(names) > 1:
        from .structure import layer_of_color
        i = layer_of_color(color)
        if i is not None and i < len(names):
            part = names[i]
    ref = resolve(doc, "wall", el.get("id"), part)
    if ref is None and part != "all":
        ref = resolve(doc, "wall", el.get("id"), "all")
    return repr(ref)


def kind_of_id(doc: dict) -> dict:
    """{element id: its kind} — everything a material can be given to (a
    room's floor: every NAMED room on a layered slab of its level)."""
    out = {"plot": "plot"} if doc.get("plot") else {}
    for d in doc.get("digs") or []:
        out[d["id"]] = "fill" if d.get("kind") == "fill" else "dig"
    for w in doc.get("walls") or []:
        out[w["id"]] = "wall"
    rooms = doc.get("rooms") or []
    for e in doc.get("structure") or []:
        out[e["id"]] = e["type"]
        if e.get("type") == "slab" and len(e.get("layers") or []) > 1:
            for r in rooms:
                if r.get("level") == e.get("level"):
                    out[f"floor:{e['id']}:{r['id']}"] = "floor"
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
                if r and _part_ok(k, eid, p, doc)}
        if keep:
            out["el"][eid] = keep
    for k, parts in (raw.get("type") or {}).items():
        if k not in SLOTS or not isinstance(parts, dict):
            continue
        keep = {p: r for p, r in ((p, valid_ref(r)) for p, r in parts.items())
                if r and p in dict(SLOTS[k])}
        if keep:
            out["type"][k] = keep
    # YOUR wall types' look (31/10): a type still there, its layers' parts
    # (kept even empty: «nothing chosen» is a choice — see ``lift``)
    types = {t.get("id"): t for t in doc.get("wall_types") or ()}
    wtype = {}
    for tid, parts in (raw.get("wtype") or {}).items():
        if tid not in types or not isinstance(parts, dict):
            continue
        ok = type_parts(types[tid])
        wtype[tid] = {p: r for p, r in ((p, valid_ref(r))
                                        for p, r in parts.items())
                      if r and p in ok}
    out["wtype"] = lift(wtype, out["el"], doc)
    return out


def type_parts(t: dict) -> set:
    """The parts a wall type's look has: its core («all») and each finish
    layer («L:<id>») — as a wall of it (``slots``); a framed core's
    insulation («fill»)."""
    ls = t.get("layers") or []
    fr = t.get("frame") or {}
    return {"all"} | {"L:" + str(la.get("id")) for la in ls
                      if la.get("role") != "core"} \
        | ({"fill"} if fr.get("kind") and fr.get("fill") != "empty"
           else set())


def lift(wtype: dict, els: dict, doc: dict) -> dict:
    """A file from before the type kept the look (31/10): a type with no
    look yet takes the one painted on a wall of it — the wall with the
    most parts painted (the walls keep their own; the others wear it)."""
    out = dict(wtype)
    for t in doc.get("wall_types") or ():
        tid = t.get("id")
        if tid in out:
            continue
        ok = type_parts(t)
        best = {}
        for w in doc.get("walls") or ():
            if w.get("type") != tid:
                continue
            got = {p: r for p, r in (els.get(w["id"]) or {}).items()
                   if p in ok}
            if len(got) > len(best):
                best = got
        if best:
            out[tid] = dict(best)
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
    wtype = {k: dict(v) for k, v in (m.get("wtype") or {}).items()}
    kind, eid = change["kind"], change.get("id") or ""
    kinds = kind_of_id(doc)
    # a wall of YOUR type: its look is the TYPE's — every wall of it
    # follows (theirs let go), the next ones drawn wear it (his ask, 31/10)
    tid = wall_type_of(doc, eid) if kind == "wall" else None
    of_type = [w["id"] for w in doc.get("walls") or ()
               if tid and w.get("type") == tid]
    for part, ref in change["parts"].items():
        # a wall's FINISH layer is its own («for all» reaches the cores)
        if change.get("all") and not part.startswith("L:"):
            t = types.setdefault(kind, {})
            if ref:
                t[part] = ref
            else:
                t.pop(part, None)
            for other, k in kinds.items():
                if k == kind and part in els.get(other, {}):
                    els[other].pop(part)
            if kind == "wall":          # …the types' looks of that part too
                for look in wtype.values():
                    look.pop(part, None)
        elif tid:
            look = wtype.setdefault(tid, {})
            if ref:
                look[part] = ref
            else:
                look.pop(part, None)
            for other in of_type:
                els.get(other, {}).pop(part, None)
        else:
            own = els.setdefault(eid, {})
            if ref:
                own[part] = ref
            else:
                own.pop(part, None)
    doc["materials"] = {"el": {k: v for k, v in els.items() if v},
                        "type": {k: v for k, v in types.items() if v},
                        "wtype": wtype}
    return _shown(doc, kind, eid, change["parts"])


def _shown(doc: dict, kind: str, eid: str, parts: dict) -> dict:
    """``doc`` with the layers given a material SEEN again: a layer hidden
    by its eye (layerview) and dressed now — the material went on, the
    old look stayed (his test, 2026-11-03: a roof's covering picked, OK,
    and it came back plain: its tiles' eye was off)."""
    from . import layerview as LV
    if kind not in ("wall", "roof", "slab") or not doc.get("hidden_layers"):
        return doc
    coll = "walls" if kind == "wall" else "structure"
    el = next((e for e in doc.get(coll) or () if e.get("id") == eid), None)
    if el is None:
        return doc
    ls = el.get("layers") or []
    who = LV.owner(doc, kind, el)
    hid = LV.hidden(doc, who)
    for part, ref in parts.items():
        if not ref:
            continue
        if part == "cover" and kind == "roof" and ls:
            key = ls[0].get("id")             # the covering: its top layer
        elif part.startswith("L:"):
            key = part[2:]
        elif part == "fill":
            key = LV.FILL
        else:
            continue
        if key and key in hid:
            doc = LV.set_key(doc, who, key, False)
            hid.discard(key)
    return doc


def carry(doc: dict, pairs) -> dict:
    """``doc`` with each new element wearing what its source wore as its
    own — (source id, new id) pairs: a split's second half, a copy."""
    m = doc.get("materials") or {}
    els = m.get("el") or {}
    add = {new: copy.deepcopy(els[src]) for src, new in pairs if src in els}
    if not add:
        return doc
    doc = dict(doc)
    doc["materials"] = dict(m, el=dict(els, **add))
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


def _is_ornament(color) -> bool:
    """A face of a column's base or capital (column_orders.ORN_COLOR)."""
    return tuple(round(v, 3) for v in (color or ())[:3]) \
        == (0.701, 0.711, 0.721)


def roof_part(color) -> str:
    """A roof face's part, by the colour ArchXQ built it with (the roof's
    faces are made fresh at every rebuild, before they are painted)."""
    from . import structure as S
    c = tuple(round(v, 3) for v in (color or ())[:3])
    for part, ref in (("parapet", S.GABLE_COLOR), ("gutter", S.GUTTER_COLOR),
                      ("slab", S.FLAT_COLOR)):
        if c == tuple(round(v, 3) for v in ref[:3]):
            return part
    return "cover"


#: the walls' library cards' LOOKS (PLANO_PAREDE_CAIXILHO.md, Part 1 —
#: his ask, 11/11/2026: «more walls, at least one of timber boards»): a
#: card = a thickness + what its faces are made of, there from the start
#: (``doc["materials"]["el"][wall id]``, where the Material tab keeps a
#: wall's own). key → (Pro: IngeTrazo's texture, Lite: a plain colour)
WALL_LOOKS = {
    "render": ({"lib": "wall/white_roughcast.jpg"},
               {"color": [0.95, 0.94, 0.91], "name": "Painted render"}),
    "concrete": ({"lib": "concrete/concrete_exposed.png"},
                 {"color": [0.63, 0.63, 0.61], "name": "Exposed concrete"}),
    "brick": ({"lib": "brick/brick_red.png"},
              {"color": [0.66, 0.31, 0.22], "name": "Exposed brick"}),
    "block": ({"lib": "wall/cinderblock.jpg"},
              {"color": [0.70, 0.70, 0.68], "name": "Concrete block"}),
    "boards_v": ({"lib": "wall/wood_paneling.jpg"},
                 {"color": [0.80, 0.63, 0.40], "name": "Timber boards"}),
    "boards_h": ({"lib": "wall/wood_paneling_3.jpg"},
                 {"color": [0.76, 0.56, 0.35], "name": "Timber siding"}),
    # (no texture of glass blocks: a pale sea-green, the Pro's too)
    "glass_block": ({"color": [0.71, 0.84, 0.84], "name": "Glass block"},
                    {"color": [0.71, 0.84, 0.84], "name": "Glass block"}),
}


def wall_look(key) -> dict | None:
    """A card's look as a wall's own parts ({"all": ref}) — the edition's
    (textures in the Pro, the colour in the Lite); None: not one."""
    got = WALL_LOOKS.get(key or "")
    if got is None:
        return None
    return {"all": copy.deepcopy(got[0] if textures_allowed() else got[1])}


def look_of(doc: dict, wall_id) -> str | None:
    """The card look a wall wears as it came (its own parts equal to one's,
    in this edition) — None: none, or changed in its Material tab."""
    own = ((doc.get("materials") or {}).get("el") or {}).get(wall_id or "")
    if not own:
        return None
    return next((k for k in WALL_LOOKS if wall_look(k) == own), None)


def with_wall_look(doc: dict, ids, key) -> dict:
    """``doc`` with the walls ``ids`` wearing the look ``key`` as their own
    (their part «all»; a part of their own elsewhere is replaced — a card
    picked is what they are made of now)."""
    parts = wall_look(key)
    if parts is None or not ids:
        return doc
    m = dict(doc.get("materials") or {})
    els = dict(m.get("el") or {})
    for i in ids:
        els[i] = dict(parts)
    m["el"] = els
    m.setdefault("type", {})
    return dict(doc, materials=m)


def without_wall_look(doc: dict, ids) -> dict:
    """``doc`` with the walls ``ids`` wearing no card look any more — one
    made a grid wall (its frame / glass / panels wear their own colours):
    only a card's look goes, a material chosen in the Material tab stays."""
    els = (doc.get("materials") or {}).get("el") or {}
    gone = [i for i in ids or () if look_of(doc, i) is not None]
    if not gone:
        return doc
    m = dict(doc.get("materials") or {})
    m["el"] = {k: v for k, v in els.items() if k not in gone}
    return dict(doc, materials=m)


#: a hidden roof's sheets when nothing is chosen for its covering (Pro)
SHEET_DEFAULT = {"lib": "roof/corrugated_sheet.jpg"}
#: what a kind's part is made of when nothing is chosen (Pro: textures).
#: His rule, 2026-10-09: what we make comes with a fitting material.
_EXPOSED = {"lib": "concrete/concrete_exposed.png"}
_SMOOTH = {"lib": "concrete/concrete_smooth.png"}
_PLASTER = {"lib": "wall/white_roughcast.jpg"}
_GRASS = {"lib": "ground/grass_lawn.png"}
_GRAVEL = {"lib": "ground/gravel.png"}
_BRUSHED = {"lib": "metal/metal_brushed.png"}
DEFAULTS = {"stair": {"top": _EXPOSED, "side": _EXPOSED, "rail": _BRUSHED,
                      "lowwall": _PLASTER},
            "ramp": {"top": _EXPOSED, "side": _EXPOSED, "rail": _BRUSHED,
                     "lowwall": _PLASTER},
            # a boundary wall's three parts each its own (his ask,
            # 2026-10-17): white render, stone piers, a dark granite coping
            "guard": {"lowwall": _PLASTER, "rail": _BRUSHED,
                      "pier": {"lib": "stone/stone_ashlar.png"},
                      "cap": {"lib": "misc/dark_granite.jpg"}},
            # a street: the host library's asphalt, concrete and pavers
            "street": {"asphalt": {"lib": "floor/dark_asphalt.jpg"},
                       "curb": {"lib": "concrete/concrete_smooth.png"},
                       "walk": {"lib": "floor/floor_pavers.png"}},
            "column": {"all": _EXPOSED}, "beam": {"all": _EXPOSED},
            "footing": {"all": _EXPOSED},
            "slab": {"top": _SMOOTH, "under": _EXPOSED},
            "floor": {"top": _SMOOTH},
            # a stone sill: dark granite (the trim keeps its white)
            "opening": {"sill": {"lib": "misc/dark_granite.jpg"}},
            "wall": {"all": _PLASTER},
            "plot": {"top": _GRASS, "side": _GRAVEL},
            "dig": {"floor": _GRAVEL, "wall": _GRAVEL},
            "fill": {"top": _GRASS, "wall": _GRAVEL},
            # his own pick for every roof, 2026-10-09 (the hidden roof's
            # sheets keep SHEET_DEFAULT)
            "roof": {"cover": {"lib": "roof/roof_tiles_colonial.png"},
                     "parapet": _PLASTER,
                     "gutter": {"lib": "metal/metal_brushed.png"},
                     "slab": _SMOOTH}}


def _is_sheet(color) -> bool:
    from . import structure as S
    return tuple(round(v, 3) for v in (color or ())[:3]) == \
        tuple(round(v, 3) for v in S.SHEET_COLOR[:3])


def paint(scene, group, kind: str, el_id: str | None, doc: dict) -> None:
    """Paint one rebuilt group with its element's materials (nothing
    chosen: its kind's ``DEFAULTS``, or as ArchXQ always drew it — and a
    hidden roof's sheets, with nothing chosen for the covering, are
    corrugated sheet: ``SHEET_DEFAULT``, his pick, 2026-10-09). Faces with
    a colour of their own (a door's glass, a frame) keep it."""
    if kind not in SLOTS:
        return
    from core.materials import Material, register
    made = {}
    parts = slots(kind, el_id, doc)
    # a CEILING (0.15.0): white board on both faces by default — the slabs'
    # «Use for all» (a floor's paving) never reaches it, its own choice does
    ceiling = kind == "slab" and any(
        e["id"] == el_id and e.get("ceiling")
        for e in doc.get("structure") or [])
    if doc.get("materials"):
        own = ((doc["materials"].get("el") or {}).get(el_id or "") or {})
        for part, _label in parts:
            ref = own.get(part) if ceiling else resolve(doc, kind, el_id,
                                                         part)
            a = attrs(ref)
            if a is not None:
                made[part] = a
    # a LIGHT-FRAMED core with nothing CHOSEN for it: pine / steel studs
    # (the walls' default, white roughcast, stays for its finishes)
    studs = None
    if kind == "wall" and "all" not in made and textures_allowed():
        from .framing import STUD_MAT, frame_of
        fr = frame_of(_wall(doc, el_id)) if el_id else None
        if fr is not None:
            studs = attrs(STUD_MAT[fr["kind"]])
            if studs is not None:
                made["_studs"] = studs
    sheet = None
    if textures_allowed():
        if kind == "roof" and "cover" not in made:   # nothing CHOSEN for it
            sheet = attrs(SHEET_DEFAULT)
        dflt = DEFAULTS.get(kind, {})
        if ceiling:
            dflt = {"top": _PLASTER, "under": _PLASTER}
        for part, ref in dflt.items():
            if part not in made:
                a = attrs(ref)
                if a is not None:
                    made[part] = a
    if not made and sheet is None:
        return
    reg = getattr(scene, "materials", None)
    for name, a in list(made.values()) + ([sheet] if sheet else []):
        if isinstance(reg, dict):
            try:
                register(reg, Material.from_dict(dict(
                    {k: v for k, v in a.items() if k != "mat"}, name=name)))
            except Exception:  # noqa: BLE001 — the paint matters, not the name
                pass
    # FACE by face, even for a one-part element: a group's own material
    # showed at first and was lost at the next redraw (his columns, beams
    # and footings, 2026-10-07) — the faces' attrs are what the host keeps
    keep_own = kind in KEEP_OWN_COLOURS
    layer_part = None
    fallback = "all"
    if kind == "slab" and parts != list(SLOTS["slab"]):
        # a slab with layers: each face's layer by its colour; a finish
        # with nothing chosen: plaster under the core, the floor's on it
        from .structure import layer_of_color
        names = [p for p, _l in parts if p != "fill"]
        core = names.index("under") if "under" in names else len(names)
        if textures_allowed():
            for p in names[core + 1:]:
                if p not in made:
                    a = attrs(_PLASTER)
                    if a is not None:
                        made[p] = a
        for p in names[:core]:
            if p not in made and "top" in made:
                made[p] = made["top"]
        # its JOISTS (a framed core): the core's own choice — pine / steel
        # with none (not the slabs' exposed concrete)
        from .framing import STUD_MAT, is_fill
        from .structure import JOIST_COLOR, slab_frame
        s_ = next((e for e in doc.get("structure") or []
                   if e.get("id") == el_id), None)
        sfr = slab_frame(s_) if s_ is not None else None
        if sfr is not None:
            own = (((doc.get("materials") or {}).get("el") or {})
                   .get(el_id or "") or {}).get("under")
            a = attrs(own) if own else \
                (attrs(STUD_MAT[sfr["kind"]]) if textures_allowed() else None)
            if a is not None:
                made["_joists"] = a
        jc = tuple(round(v, 3) for v in JOIST_COLOR[:3])

        def layer_part(color):
            if sfr is not None and is_fill(color):
                return "fill"
            if sfr is not None and color is not None and \
                    tuple(round(v, 3) for v in color[:3]) == jc:
                return "_joists"
            i = layer_of_color(color)
            return names[i] if i is not None and i < len(names) else None
        fallback = "under"
    elif kind == "roof" and any(p.startswith("L:") or p == "rafters"
                                for p, _l in parts):
        # a roof with layers: each one under the covering by its colour
        # (structure.roof_layer_color); with nothing chosen it keeps its
        # colour — plaster under the core (the ceiling). The covering, the
        # gable walls, the gutter: as before (below)
        from .structure import roof_layer_of_color
        r = next((e for e in doc.get("structure") or []
                  if e.get("id") == el_id), {})
        ls = r.get("layers") or []
        names = ["cover"] + ["L:" + str(la.get("id")) for la in ls[1:]]
        core = next((i for i, la in enumerate(ls)
                     if la.get("role") == "core"), len(ls))
        # its rafters (a framed core, step 2b): the core's part — pine /
        # steel with nothing chosen, as a framed wall's studs
        from .framing import STUD_MAT, clean_frame, is_fill
        from .structure import RAFTER_COLOR
        fr = clean_frame(r.get("frame"))
        raf = (names[core] if 0 < core < len(names) else "rafters") \
            if fr is not None else None
        if textures_allowed():
            for p in names[core + 1:]:
                if p not in made:
                    a = attrs(_PLASTER)
                    if a is not None:
                        made[p] = a
            if raf is not None and raf not in made:
                a = attrs(STUD_MAT[fr["kind"]])
                if a is not None:
                    made[raf] = a
        rc = tuple(round(v, 3) for v in RAFTER_COLOR[:3])
        from .structure import BLOCK_COLOR
        bc = tuple(round(v, 3) for v in BLOCK_COLOR[:3])

        def layer_part(color):
            if is_fill(color):
                return "fill"
            if raf is not None and color is not None and \
                    tuple(round(v, 3) for v in color[:3]) in (rc, bc):
                return raf               # (its fascia, soffit, blocking)
            i = roof_layer_of_color(color)
            return names[i] if i is not None and 0 < i < len(names) \
                else None
        fallback = None
    elif kind == "floor":
        # a room's floor: its layers (the slab's finishes on the core) by
        # their colours; one with nothing chosen wears the floor's top
        from .structure import layer_of_color
        names = [p for p, _l in parts]
        for p in names[1:]:
            if p not in made and "top" in made:
                made[p] = made["top"]

        def layer_part(color):
            i = layer_of_color(color)
            return names[i] if i is not None and i < len(names) else None
        fallback = "top"
    elif kind == "wall" and (len(parts) > 1 or studs is not None):
        # a wall with layers: each face's layer by the colour it is built
        # with (structure.layer_color); a finish with nothing chosen wears
        # the wall's own (its core's) material
        from .framing import TREATED_MAT, is_fill, is_treated
        from .structure import layer_of_color
        names = [p for p, _l in parts if p != "fill"]
        a = attrs(TREATED_MAT)              # (the sill plate: its own)
        if a is not None:
            made["_treated"] = a

        def layer_part(color):
            if is_fill(color):              # the insulation (framing.py)
                return "fill"
            if is_treated(color):           # the treated sill plate (D8)
                return "_treated"
            i = layer_of_color(color)
            return names[i] if i is not None and i < len(names) else None
    if kind == "shaped":
        # a piece adopted as it is (shaped.py): it keeps its own look — a
        # material CHOSEN for it covers every face but the see-through ones
        a = made.get("all")
        if a is not None:
            for f in group.mesh.faces:
                if float(f.attrs.get("opacity", 1.0)) < 1.0:
                    continue
                f.attrs.pop("texture", None)
                f.attrs.update(a[1])
        return
    grid = _grid_of(_wall(doc, el_id)) if kind == "wall" and el_id else None
    if grid is not None:
        # a grid wall: each face's part by the colour it is built with — a
        # part with a material takes it, the others keep their colour (the
        # walls' «Use for all» and their default never reach it)
        from . import gridwall as GX
        for f in group.mesh.faces:
            a = made.get(GX.part_of_color(f.attrs.get("color"), grid))
            if a is not None:
                f.attrs.update(a[1])
        return
    for f in group.mesh.faces:
        if layer_part is not None:
            part = layer_part(f.attrs.get("color"))
            if part is not None:
                # (the insulation with nothing chosen keeps its colour; the
                # studs with nothing chosen: pine / steel)
                if part == "all" and studs is not None:
                    a = studs
                else:
                    a = made.get(part) or (None if part == "fill"
                                           else made.get(fallback))
                if a is not None:
                    f.attrs.update(a[1])
                continue
        if kind == "column":
            # its base and capital, told by their colour: as the shaft until
            # they get a material of their own
            a = made.get("all")
            if _is_ornament(f.attrs.get("color")):
                a = made.get("orn") or a
            if a is not None:
                f.attrs.update(a[1])
            continue
        if kind == "opening":
            # each part by the colour it is built with (trim.py): a part
            # with a material takes it, the others (the glass) keep theirs
            from .trim import part_of_color
            part = part_of_color(f.attrs.get("color"))
            if part in made:
                f.attrs.update(made[part][1])
            continue
        if keep_own and "color" in f.attrs and "mat" not in f.attrs:
            continue                              # its own (glass, frame)
        if kind == "roof":
            part = roof_part(f.attrs.get("color"))
            if sheet and part == "cover" and _is_sheet(f.attrs.get("color")):
                f.attrs.update(sheet[1])
                continue
        else:
            part = None
            if kind == "street":
                try:
                    from .streets import part_of_color as street_part
                    part = street_part(f.attrs.get("color")) or "asphalt"
                except ImportError:
                    part = None
            elif kind in ("stair", "ramp", "guard"):
                # its railing's parts, told by the colours they are built
                # with; the glass keeps its own until one is chosen
                try:
                    if kind == "guard":                   # + piers, coping
                        from .guards import part_of_color
                    else:
                        from .railings import part_of_color   # Pro only
                    part = part_of_color(f.attrs.get("color"))
                except ImportError:
                    part = None
            if part is None:
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
_REOPEN_AT: dict = {}     # a window reopened by Apply: (tab, part row)
_POOL = ThreadPoolExecutor(4, thread_name_prefix="archxq-webtex")
_LAST_PAGE = None         # the gallery's tab last used, while the host is open
_TILE = None              # the class of a gallery tile (with its star)


def thumb(ref, size: int = THUMB):
    """A ref's picture: the texture's image, or a swatch of its colour."""
    QtCore, QtGui, _w = _qt()
    key = (repr(ref), size)
    if key in _PIX:
        return _PIX[key]
    pm = QtGui.QPixmap(size, size)
    if ref and ("lib" in ref or WT.is_ref(ref)):
        if WT.is_ref(ref):
            path = WT.ref_path(ref)
            img = QtGui.QPixmap(path) if path else QtGui.QPixmap()
        else:
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


def _star_poly(c, r: float):
    _c, QtGui, _w = _qt()
    import math
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        k = r if i % 2 == 0 else r * 0.45
        pts.append(_c.QPointF(c.x() + k * math.cos(a),
                              c.y() + k * math.sin(a)))
    return QtGui.QPolygonF(pts)


def _tile_class():
    """A gallery tile with a star in its corner — under the pointer, or lit
    (a favourite): a click on the star keeps / drops it, elsewhere picks."""
    global _TILE
    if _TILE is not None:
        return _TILE
    QtCore, QtGui, W = _qt()

    class Tile(W.QToolButton):
        def __init__(self, ref, tip: str, on_star) -> None:
            super().__init__()
            self.ref, self.tip, self.on_star = ref, tip, on_star
            self.fav = False
            self._over = False
            self._on_star = False
            self.set_fav(MF.is_fav(ref))

        def set_fav(self, on: bool) -> None:
            self.fav = bool(on)
            self.setToolTip(self.tip + "\n" + (
                tr("★ In your favourites — click the star to take it out")
                if self.fav else
                tr("Click the ☆ to keep it in your favourites")))
            self.update()

        def _star(self):
            s = 18
            return QtCore.QRect(self.width() - s - 3, 3, s, s)

        def enterEvent(self, ev):  # noqa: N802
            self._over = True
            self.update()
            super().enterEvent(ev)

        def leaveEvent(self, ev):  # noqa: N802
            self._over = False
            self.update()
            super().leaveEvent(ev)

        def mousePressEvent(self, ev):  # noqa: N802
            if ev.button() == QtCore.Qt.LeftButton and \
                    self._star().contains(ev.position().toPoint()):
                self._on_star = True
                ev.accept()
                return
            super().mousePressEvent(ev)

        def mouseReleaseEvent(self, ev):  # noqa: N802
            if self._on_star:
                self._on_star = False
                ev.accept()
                if self._star().contains(ev.position().toPoint()):
                    self.on_star(self.ref)
                return
            super().mouseReleaseEvent(ev)

        def paintEvent(self, ev):  # noqa: N802
            super().paintEvent(ev)
            if not (self.fav or self._over):
                return
            p = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.Antialiasing)
            r = QtCore.QRectF(self._star())
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(QtGui.QColor(20, 24, 30, 175))
            p.drawEllipse(r)
            poly = _star_poly(r.center(), r.width() * 0.42)
            if self.fav:
                p.setBrush(QtGui.QColor("#f5c518"))
                p.setPen(QtGui.QPen(QtGui.QColor("#8a6d00"), 1))
            else:
                p.setBrush(QtCore.Qt.NoBrush)
                p.setPen(QtGui.QPen(QtGui.QColor("#e8edf2"), 1.4))
            p.drawPolygon(poly)
            p.end()
    _TILE = Tile
    return Tile


def _web_item(ref) -> dict:
    """A web texture's ref as its list's item (to fetch it)."""
    src, key = ref["web"].split("/")
    return {"src": src, "id": key, "name": ref["name"], "w": ref["w0"],
            "h": ref["h0"]}


def _icon_of(ref):
    """A tile's picture: a web texture not fetched yet, its little one."""
    QtCore, QtGui, _w = _qt()
    if WT.is_ref(ref) and "web" in ref and WT.ref_path(ref) is None:
        path = WT.thumb_path(*ref["web"].split("/"))
        key = ("t", path)
        if key not in _PIX:
            img = QtGui.QPixmap(path) if os.path.isfile(path) \
                else QtGui.QPixmap()
            if img.isNull():
                img = QtGui.QPixmap(THUMB, THUMB)
                img.fill(QtGui.QColor("#3a4048"))
            else:
                img = img.scaled(THUMB, THUMB,
                                 QtCore.Qt.KeepAspectRatioByExpanding,
                                 QtCore.Qt.SmoothTransformation)
            _PIX[key] = img
        return _PIX[key]
    return thumb(ref)


def _fav_shown(ref) -> bool:
    """A kept one still here (a texture of the library, your own file)."""
    if "lib" in ref:
        return lib_item(ref["lib"]) is not None
    if WT.is_ref(ref) and "own" in ref:
        return WT.ref_path(ref) is not None
    return True


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
        self.parts = slots(kind, el_id, doc)
        self.start = {p: resolve(doc, kind, el_id, p) for p, _l in self.parts}
        self.now = dict(self.start)
        self.part = self.parts[0][0]
        self._tiles = {}             # a ref's key: its tiles (their stars)
        self.widget = w = W.QWidget()
        w.setMinimumSize(600, 380)
        root = W.QHBoxLayout(w)

        left = W.QVBoxLayout()
        # a wall of YOUR type: its name on top, legible (his ask, 01/11 —
        # nowhere on this tab did it say which type the look belongs to)
        tid = wall_type_of(doc, el_id) if kind == "wall" else None
        tname = next((t.get("name") for t in doc.get("wall_types") or ()
                      if t.get("id") == tid), "") if tid else ""
        if tname:
            head = W.QLabel(tname)
            head.setWordWrap(True)
            head.setMaximumWidth(196)
            head.setToolTip(tr("Your wall type — the look below is the "
                               "type's"))
            head.setStyleSheet("font-size: 15px; font-weight: 600; "
                               "color: #8fb8f9; padding-bottom: 2px;")
            left.addWidget(head)
        self.big = W.QLabel()
        self.big.setFixedSize(132, 132)
        self.big.setScaledContents(True)
        left.addWidget(self.big)
        self.name = W.QLabel()
        self.name.setWordWrap(True)
        self.name.setMaximumWidth(196)
        left.addWidget(self.name)
        self._size_busy = False
        self.size_box = self._size_row()
        left.addWidget(self.size_box)
        self.list = W.QListWidget()
        self.list.setIconSize(QtCore.QSize(28, 28))
        # wide enough for «Railing (posts, handrail)» (cut, a scroll bar
        # under it — his screen, 2026-10-13)
        self.list.setFixedWidth(196)
        self.list.setWordWrap(True)
        self.list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        for p, label in self.parts:
            self.list.addItem(W.QListWidgetItem(tr(label)))
        self.list.setCurrentRow(0)
        self.list.currentRowChanged.connect(self._pick_part)
        if len(self.parts) == 1:
            self.list.hide()
            left.addStretch(1)             # (the size stays under the name)
        left.addWidget(self.list, 1)
        root.addLayout(left)

        right = W.QVBoxLayout()
        self._web_setup()
        scroll, inner = self._page()
        self.sections = W.QVBoxLayout(inner)
        self.sections.setContentsMargins(2, 2, 2, 2)
        self.sections.setSpacing(2)
        cur = self.now.get(self.part) or {}
        cur_cat = (cur.get("lib") or "").split("/")[0]
        if textures_allowed():
            for c in library():
                box = _section(
                    f"{c['name']}  ({len(c['items'])})",
                    lambda body, c=c: self._grid(
                        body, [({"lib": it["file"]}, it["name"])
                               for it in c["items"]]),
                    opened=c["id"] == cur_cat)
                self.sections.addWidget(box)
                if c["id"] == "wall" and not cur_cat:
                    self._open_on_show(inner, box)
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
        self.pages = None
        if textures_allowed():
            self._make_pages(scroll, cur)
            right.addWidget(self.pages, 1)
        else:
            right.addWidget(scroll, 1)
        self.web_note = W.QLabel()
        self.web_note.setWordWrap(True)
        self.web_note.setStyleSheet("color: #8fb8f9;")
        self.web_note.hide()
        right.addWidget(self.web_note)

        row = W.QHBoxLayout()
        own = W.QPushButton("Solid colour…")
        own.clicked.connect(self._own_colour)
        row.addWidget(own)
        if textures_allowed():
            yours = W.QPushButton(tr("Add your own texture…"))
            yours.setToolTip(tr("An image from your computer. It stays in "
                                "your textures, for every project"))
            yours.clicked.connect(self._add_own)
            row.addWidget(yours)
        dflt = W.QPushButton("Default")
        dflt.setToolTip("Back to ArchXQ's default for this part")
        dflt.clicked.connect(lambda: self._choose(None))
        row.addWidget(dflt)
        row.addStretch()
        self.all = W.QCheckBox(tr(f"Use for all {PLURAL.get(kind, kind)}"))
        self.all.setToolTip(f"Every {kind} in the project takes it (one "
                            "that had its own for this part, too)")
        row.addWidget(self.all)
        right.addLayout(row)
        # a wall of YOUR type: the look is the type's (31/10) — said here
        tid = wall_type_of(doc, el_id) if kind == "wall" else None
        if tid:
            name = next((t.get("name") for t in doc.get("wall_types") or ()
                         if t.get("id") == tid), "")
            note = W.QLabel(tr("Type «{name}»: what you pick goes to every "
                               "wall of this type — and to the next ones "
                               "drawn with it", name=name))
            note.setWordWrap(True)
            note.setStyleSheet("color: #8fb8f9;")
            right.addWidget(note)
        root.addLayout(right, 1)
        self._show()

    # -- the size of a texture ---------------------------------------------------------
    def _size_row(self):
        from . import look as L
        _c, _g, W = _qt()
        box = W.QWidget()
        box.setMaximumWidth(196)
        lay = W.QVBoxLayout(box)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(3)
        lay.addWidget(W.QLabel(tr("Texture size")))
        self.size = L.metres(1.0, SIZE_MIN, SIZE_MAX)
        self.size.setToolTip(tr("How wide one tile of this texture is on the "
                                "model. Its proportion is kept"))
        self.size.valueChanged.connect(self._size_typed)
        lay.addWidget(self.size)
        row = W.QHBoxLayout()
        row.setSpacing(4)
        half = W.QPushButton("½×")
        half.setToolTip(tr("Half the size"))
        half.clicked.connect(lambda: self._size_times(0.5))
        row.addWidget(half)
        twice = W.QPushButton("2×")
        twice.setToolTip(tr("Twice the size"))
        twice.clicked.connect(lambda: self._size_times(2.0))
        row.addWidget(twice)
        own = W.QPushButton(tr("Original"))
        own.setToolTip(tr("The texture's own size"))
        own.clicked.connect(self._size_original)
        row.addWidget(own)
        lay.addLayout(row)
        return box

    def _size_typed(self, width: float) -> None:
        ref = self.now.get(self.part)
        if not self._size_busy and tex_size(ref):
            self._choose(sized(ref, width))

    def _size_times(self, k: float) -> None:
        ref = self.now.get(self.part)
        got = tex_size(ref)
        if got:
            self._choose(sized(ref, min(max(got[0] * k, SIZE_MIN),
                                        max(SIZE_MAX, got[0]))))

    def _size_original(self) -> None:
        ref = self.now.get(self.part)
        if WT.is_ref(ref):
            self._choose(WT.sized(ref, ref["w0"]))
        elif tex_size(ref):
            self._choose({"lib": ref["lib"]})

    def _show_size(self, ref) -> None:
        got = tex_size(ref) if textures_allowed() else None
        self.size_box.setVisible(bool(got))
        if got:
            self._size_busy = True
            try:
                self.size.setRange(min(SIZE_MIN, got[0]),
                                   max(SIZE_MAX, got[0]))
                self.size.setValue(got[0])
            finally:
                self._size_busy = False

    # -- Poly Haven, ambientCG, your own ------------------------------------------------
    def _web_setup(self) -> None:
        """Workers only fetch and write files and say so in a queue; the
        pictures are made here, on a timer that dies with the window."""
        QtCore, _g, W = _qt()
        self._web_q = queue.Queue()
        self._web_stop = threading.Event()
        self._web_btn = {}
        self._web_busy = 0
        self._web_want = None
        self._web_offline = False
        self._web_tick = QtCore.QTimer(self.widget)
        self._web_tick.setInterval(120)
        self._web_tick.timeout.connect(self._web_drain)
        self.widget.destroyed.connect(lambda *_a: self._web_stop.set())

    @staticmethod
    def _open_on_show(page, box) -> None:
        """The first group of a tab is open when you get there (his ask,
        09/11: the wall of colours is the «wow») — only then: the window
        opens as fast as ever, and nothing is fetched for a tab not seen."""
        QtCore, _g, W = _qt()
        head = box.findChild(W.QToolButton)

        class Once(QtCore.QObject):
            def eventFilter(self, obj, ev):  # noqa: N802
                if ev.type() == QtCore.QEvent.Show:
                    obj.removeEventFilter(self)
                    QtCore.QTimer.singleShot(0, page, _open)
                return False

        def _open() -> None:
            head.setChecked(True)
        page.installEventFilter(Once(page))

    @staticmethod
    def _page():
        """(its scroll area, the widget to fill)."""
        _c, _g, W = _qt()
        scroll = W.QScrollArea()
        scroll.setWidgetResizable(True)
        inner = W.QWidget()
        scroll.setWidget(inner)
        return scroll, inner

    def _make_pages(self, native, cur) -> None:
        """Where the textures come from, one tab each (his ask, 09/11: in one
        long list they were lost, «even knowing they are there»)."""
        global _LAST_PAGE
        _c, _g, W = _qt()
        self.pages = W.QTabWidget()
        self.pages.setDocumentMode(True)
        # first: YOUR favourites and the recently used, for every project
        # (his ask, 12/11: «not having to look for the ones I use»)
        page, self._fav_box = self._page()
        lay = W.QVBoxLayout(self._fav_box)
        lay.setContentsMargins(8, 8, 8, 8)
        self.pages.addTab(page, "★ " + tr("Favourites"))
        self._fav_fill()
        self.pages.addTab(native, "IngeTrazo")
        for src, title in WT.SOURCES.items():
            page, inner = self._page()
            self._web_source(inner, src)
            inner.layout().addStretch()
            self.pages.addTab(page, f"{title} ({WT.count(src)})")
        page, self._own_box = self._page()
        self._own_page = page
        lay = W.QVBoxLayout(self._own_box)
        lay.setContentsMargins(8, 8, 8, 8)
        self.pages.addTab(page, tr("Your textures"))
        self._own_fill()
        if WT.is_ref(cur) and not self._in_fav_page(cur):
            # (opens where its material came from)
            at = self.pages.indexOf(page) if "own" in cur else \
                2 + list(WT.SOURCES).index(cur["web"].split("/")[0])
        elif _LAST_PAGE is not None:
            at = _LAST_PAGE
        else:                    # the first time: your own, when there are
            at = 0 if (MF.favs() or MF.recent()) else 1
        self.pages.setCurrentIndex(at)

        def remember(i: int) -> None:
            global _LAST_PAGE
            _LAST_PAGE = i
        self.pages.currentChanged.connect(remember)

    def _own_fill(self) -> None:
        _c, _g, W = _qt()
        lay = self._own_box.layout()
        while lay.count():
            w = lay.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        names = WT.own_files()
        if names:
            grid = W.QWidget()
            self._grid(grid, self._own_refs(names))
            lay.addWidget(grid)
        else:
            note = W.QLabel(tr("The images you add with «Add your own "
                               "texture…» stay here, for every project"))
            note.setWordWrap(True)
            note.setEnabled(False)
            lay.addWidget(note)
        lay.addStretch()

    # -- your favourites and the recently used ------------------------------------------
    def _fav_fill(self) -> None:
        _c, _g, W = _qt()
        lay = self._fav_box.layout()
        while lay.count():
            w = lay.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        for title, rows, empty in (
                ("★ " + tr("Favourites"), MF.favs(),
                 tr("Click the ☆ on any texture or colour, in any tab, to "
                    "keep it here — for every project")),
                (tr("Recently used"), MF.recent(),
                 tr("The last ones you apply come here by themselves"))):
            head = W.QLabel(title)
            head.setStyleSheet("font-weight: bold; padding: 4px 2px;")
            lay.addWidget(head)
            rows = [r for r in rows if _fav_shown(r)]
            if rows:
                grid = W.QWidget()
                self._grid(grid, [(r, ref_label(r)) for r in rows],
                           own=False)
                lay.addWidget(grid)
            else:
                note = W.QLabel(empty)
                note.setWordWrap(True)
                note.setEnabled(False)
                lay.addWidget(note)
        lay.addStretch()

    @staticmethod
    def _in_fav_page(ref) -> bool:
        k = MF.key_of(ref)
        return k is not None and any(MF.key_of(r) == k
                                     for r in MF.favs() + MF.recent())

    def _on_star(self, ref) -> None:
        QtCore, _g, _w = _qt()
        on = MF.toggle(ref)
        for t in self._tiles.get(MF.key_of(ref), ()):
            try:
                t.set_fav(on)
            except RuntimeError:           # (a tile gone with its page)
                pass
        # (later: the tile clicked may be one of the page rebuilt)
        QtCore.QTimer.singleShot(0, self.widget, self._fav_fill)

    def _tile(self, ref, tip: str, own: bool = True):
        """A gallery tile; Pro: with its star. ``own``: on the gallery's
        tabs (its star follows a click on the favourites' page)."""
        QtCore, _g, W = _qt()
        if textures_allowed():
            b = _tile_class()(ref, tip, self._on_star)
            if own:
                self._tiles.setdefault(MF.key_of(ref), []).append(b)
        else:
            b = W.QToolButton()
            b.setToolTip(tip)
        b.setIconSize(QtCore.QSize(THUMB, THUMB))
        b.setAutoRaise(True)
        return b

    def _pick_any(self, ref) -> None:
        """A tile clicked: a web texture not on this computer is fetched."""
        if WT.is_ref(ref) and "web" in ref and WT.ref_path(ref) is None:
            self._web_pick(_web_item(ref))
        else:
            self._choose(ref)

    def _own_refs(self, names) -> list:
        _c, QtGui, _w = _qt()
        out = []
        for n in names:
            s = QtGui.QImageReader(WT.own_path(n)).size()
            ref = WT.own_ref(n, s.width(), s.height())
            out.append((ref, ref["name"]))
        return out

    def _add_own(self) -> None:
        _c, QtGui, W = _qt()
        path, _f = W.QFileDialog.getOpenFileName(
            self.widget, tr("Choose a texture image"),
            os.path.expanduser("~"),
            "Images (" + " ".join("*" + e for e in WT.OWN_EXT) + ")")
        if not path:
            return
        s = QtGui.QImageReader(path).size()
        try:
            if s.width() <= 0 or s.height() <= 0:
                raise OSError("not an image")
            ref = WT.add_own(path, s.width(), s.height())
        except OSError:
            self._web_say(tr("That file could not be used as a texture"))
            return
        self._own_fill()
        self.pages.setCurrentIndex(self.pages.indexOf(self._own_page))
        self._choose(ref)

    def _web_source(self, body, src: str) -> None:
        _c, _g, W = _qt()
        lay = W.QVBoxLayout(body)
        lay.setContentsMargins(2, 6, 2, 4)
        lay.setSpacing(2)
        note = W.QLabel(tr("Free CC0 textures from {name} ({site}). Each one "
                           "comes from the internet when you click it",
                           name=WT.SOURCES[src], site=WT.SITES[src]))
        note.setWordWrap(True)
        note.setEnabled(False)
        lay.addWidget(note)
        for n, (fam, items) in enumerate(WT.families(src)):
            box = _section(f"{tr(fam)}  ({len(items)})",
                           lambda b, items=items: self._web_grid(b, items))
            lay.addWidget(box)
            if n == 0:
                self._open_on_show(body, box)

    def _web_grid(self, body, items) -> None:
        QtCore, QtGui, W = _qt()
        g = W.QGridLayout(body)
        g.setContentsMargins(4, 0, 4, 6)
        g.setSpacing(4)
        blank = QtGui.QPixmap(THUMB, THUMB)
        blank.fill(QtGui.QColor("#3a4048"))
        for n, it in enumerate(items):
            b = self._tile(WT.ref_of(it), it["name"])
            b.setIcon(QtGui.QIcon(blank))
            b.clicked.connect(lambda _c=False, i=it: self._web_pick(i))
            g.addWidget(b, n // self.COLS, n % self.COLS)
            key = (it["src"], it["id"])
            self._web_btn[key] = b
            path = WT.thumb_path(*key)
            if os.path.isfile(path):
                self._web_icon(b, path)
            else:
                self._web_job("thumb", key, None)

    def _web_icon(self, button, path: str) -> None:
        QtCore, QtGui, _w = _qt()
        img = QtGui.QPixmap(path)
        if not img.isNull():
            button.setIcon(QtGui.QIcon(img.scaled(
                THUMB, THUMB, QtCore.Qt.KeepAspectRatioByExpanding,
                QtCore.Qt.SmoothTransformation)))

    def _web_job(self, what: str, key, item) -> None:
        q, stop = self._web_q, self._web_stop

        def work() -> None:
            if what == "thumb" and stop.is_set():
                q.put(("skip", key, None))
                return
            try:
                if what == "thumb":
                    got = WT.fetch_thumb(*key)
                else:
                    got = WT.fetch_file(*key, lambda pct: q.put(
                        ("pct", key, pct)))
                q.put((what, key, got))
            except Exception:  # noqa: BLE001 — the window says so
                q.put((what, key, None))
        self._web_busy += 1
        _POOL.submit(work)
        self._web_tick.start()

    def _web_say(self, text: str) -> None:
        self.web_note.setText(text)
        self.web_note.setVisible(bool(text))

    def _web_pick(self, item: dict) -> None:
        key = (item["src"], item["id"])
        self._web_want = None
        if os.path.isfile(WT.file_path(*key)):
            self._web_say("")
            self._choose(WT.ref_of(item))
            return
        self._web_want = item
        self._web_say(tr("Downloading {name}…", name=item["name"]))
        self._web_job("file", key, item)

    def _web_drain(self) -> None:
        while True:
            try:
                what, key, got = self._web_q.get_nowait()
            except queue.Empty:
                break
            want = self._web_want
            hot = want is not None and key == (want["src"], want["id"])
            if what == "pct":
                if hot:
                    self._web_say(tr("Downloading {name}… {pct}%",
                                     name=want["name"], pct=got))
                continue
            self._web_busy -= 1
            if what == "thumb":
                if got and key in self._web_btn:
                    self._web_icon(self._web_btn[key], got)
                elif not got and not self._web_offline:
                    self._web_offline = True
                    self._web_say(tr("The pictures could not be loaded. "
                                     "Check your internet connection"))
            elif what == "file" and hot:
                self._web_want = None
                if got:
                    self._web_say("")
                    self._choose(WT.ref_of(want))
                else:
                    self._web_say(tr("Could not download {name}. Check your "
                                     "internet connection and try again",
                                     name=want["name"]))
        if self._web_busy <= 0:
            self._web_tick.stop()

    # -- the gallery ----------------------------------------------------------------
    def _grid(self, body, refs, own: bool = True) -> None:
        QtCore, QtGui, W = _qt()
        g = W.QGridLayout(body)
        g.setContentsMargins(4, 0, 4, 6)
        g.setSpacing(4)
        for n, (ref, tip) in enumerate(refs):
            b = self._tile(ref, tip, own)
            b.setIcon(QtGui.QIcon(_icon_of(ref)))
            b.clicked.connect(lambda _c=False, r=ref: self._pick_any(r))
            g.addWidget(b, n // self.COLS, n % self.COLS)
        # (a short row: the tiles keep to the left, as in a full one)
        if len(refs) < self.COLS:
            g.setColumnStretch(self.COLS, 1)

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
        self.name.setText(f"<b>{tr(label)}</b><br>{tr(ref_label(ref))}")
        self._show_size(ref)
        for i, (p, _l) in enumerate(self.parts):
            self.list.item(i).setIcon(QtGui.QIcon(thumb(self.now.get(p), 28)))

    # -- the result -----------------------------------------------------------------
    #: ui sets it: commits a change at once (Apply on this tab)
    on_apply = None

    def apply_now(self) -> None:
        """Apply on the Material tab: commit what changed, stay open."""
        ch = self.change()
        if ch is None or self.on_apply is None:
            return
        self.on_apply(ch)
        self.start = dict(self.now)        # applied: no longer a change
        self.all.setChecked(False)

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
    own = getattr(dlg, "_axq_tabs", None)
    if own is not None:                   # a window of 0.10.0 (look.py)
        own.addTab(tab.widget, "Material", "material")
        _hook(dlg, own, tab)
        return
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
    _hook(dlg, tabs, tab)
    for it in keep:
        if it.widget() is not None:
            lay.addWidget(it.widget())
        elif it.layout() is not None:
            sub = it.layout()
            sub.setParent(None)
            lay.addLayout(sub)
        else:
            lay.addItem(it)


def _hook(dlg, tabs, tab: MaterialTab) -> None:
    """The Material tab's ties to its window: back on the same tab / part
    when «Apply» reopens it, and «Apply» on it commits at once."""
    # reopened by «Apply» (the Element tab): back on the tab and the part it
    # was on — it went back to «Element» every time (his test, 2026-10-07)
    key = type(dlg).__name__
    last = _REOPEN_AT.pop(key, None)
    if last is not None:
        tabs.setCurrentIndex(last[0])
        tab.list.setCurrentRow(last[1])

    def remember(_r=0) -> None:
        if getattr(dlg, "again", False):
            _REOPEN_AT[key] = (tabs.currentIndex(), tab.list.currentRow())
    dlg.finished.connect(remember)
    # «Apply» with the Material tab in front: the material goes on AT ONCE,
    # the window stays (no close-and-reopen blink); on the Element tab it is
    # the usual Apply
    b = getattr(dlg, "_apply_btn", None)
    if b is not None and hasattr(b, "_axq_go"):
        b.clicked.disconnect()
        b.clicked.connect(lambda: tab.apply_now()
                          if tabs.currentWidget() is tab.widget
                          and tab.on_apply is not None else b._axq_go())
    dlg._mat_tab = tab
