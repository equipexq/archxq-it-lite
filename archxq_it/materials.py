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
import sys

from . import edition
from .i18n import tr

#: an element kind's PARTS: (key, label). One part = the whole element.
SLOTS = {
    "plot": (("top", "Top (the ground)"), ("side", "Sides")),
    "dig": (("floor", "Floor"), ("wall", "Walls and slopes")),
    "fill": (("top", "Top"), ("wall", "Slopes")),
    "column": (("all", "Column"),),
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
          "opening": "doors and windows"}
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


def _wall(doc: dict, el_id) -> dict | None:
    return next((w for w in doc.get("walls") or [] if w["id"] == el_id),
                None)


def slots(kind: str, el_id: str | None, doc: dict) -> list:
    """An element's parts — a wall with LAYERS (0.15.0): each layer, outside
    → inside; its core is the wall's own part («all»: «Use for all walls»
    still reaches it), each finish «L:<its id>»."""
    if kind == "wall" and el_id:
        w = _wall(doc, el_id)
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
        self.parts = slots(kind, el_id, doc)
        self.start = {p: resolve(doc, kind, el_id, p) for p, _l in self.parts}
        self.now = dict(self.start)
        self.part = self.parts[0][0]
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
        self.name.setText(f"<b>{tr(label)}</b><br>{tr(ref_label(ref))}")
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
