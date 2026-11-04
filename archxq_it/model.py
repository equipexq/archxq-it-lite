"""ArchXQ document model — pure data, no Qt.

Everything ArchXQ keeps in the .igz lives in ONE JSON-safe dict (the
extension's document slot). ``load`` always returns a complete, valid
dict: missing keys get defaults, old prototype data is migrated, and
out-of-range values are corrected instead of refused (the user's mistake
is fixed by the logic, not reported back as homework).

Levels are stored bottom → top. The ground floor is the one with
``kind == "ground"``; its finished floor sits at ``ground_level``;
floors above stack their heights upwards, basements downwards.
"""
from __future__ import annotations

import copy
import datetime
import math
import re
import uuid

MIN_HEIGHT = 2.0          # m — below this a storey is not a storey
MAX_HEIGHT = 12.0
DEFAULT_HEIGHT = 3.0
CONTOUR_STEP = 0.5          # m between the ground's contour lines

PAPERS = ("A1", "A2", "A3", "A4", "Letter", "Tabloid")
SCALES = ("1:50", "1:75", "1:100", "1:200")
UNITS = ("Metric (m)", "Imperial (ft-in)")

#: the parts of ONE level its window shows / hides («Show»): (key, label,
#: the kinds of the elements in it)
LEVEL_PARTS = (("slabs", "Slabs", ("slab",)),
               ("framing", "Columns & beams", ("column", "beam")),
               ("footings", "Footings", ("footing",)),
               ("walls", "Walls", ("wall",)),
               ("openings", "Openings", ("opening",)),
               ("ramps", "Ramps & stairs", ("ramp", "stair")),
               ("guards", "Low walls & guards", ("guard",)),
               ("glazing", "Grids", ("glazing",)),
               # the host's guide lines drawn on that level (at its height)
               # — set aside in «guides_off» while off (his ask, 2026-10-12:
               # one floor's guides cluttered the next)
               ("guides", "Guide lines", ()))

DEFAULT_PROJECT = {
    "name": "", "client": "", "location": "", "author": "",
    "date": "",                 # empty = today, when a sheet is exported
    "units": UNITS[0],
    "north_deg": 0.0,           # project north, clockwise from +Y
    "ground_level": 0.0,        # finished floor of the ground floor (m)
    "paper": "A3", "orientation": "Landscape", "scale": "1:100",
}

DEFAULT_DOC = {
    "done": [],
    "system": "frame",
    "project": None,            # None until the user starts a project
    "levels": [{"name": "Level 1", "kind": "ground",
                "height": DEFAULT_HEIGHT, "id": "lv0"}],
    # what is shown (view state: kept in the file, never an undo step).
    # *_dims: None = the Settings decide; True / False = chosen in the
    # element's own window, and that choice rules
    # setbacks: OFF by default (his ask 2026-10-16 — the dashed outline
    # stood on every new house); always drawn in Terrain › Setbacks
    "view": {"setbacks": False, "folds": True,
             "plot_dims": None, "setback_dims": None, "dig_dims": None,
             "plot_elev_dims": None, "dig_elev_dims": None,
             "survey_dims": None, "contour_dims": None},
    # excavations opened in the plot (see terrain.py for the fields)
    "digs": [],
    # walls, every level's (see walls.py for the fields; + "level": id,
    # "height": "level" | m, "base": m)
    "walls": [],
    # YOUR wall types (0.15.0): {"id", "name", "t", "layers": [...]} — a
    # wall with "type": id takes its layers and thickness (edited once,
    # every wall of it follows)
    "wall_types": [],
    # YOUR slab types (slab layers): the same records, their layers TOP →
    # BOTTOM — a slab with "stype": id takes them
    "slab_types": [],
    # YOUR profiles (Tools ▸ Profile along, made from a face): {"id" «u_…»,
    # "name", "cat", "pts"} — the project's copy (profiles.py)
    "profile_types": [],
    # columns, beams, slabs, footings (see structure.py for the fields)
    "structure": [],
    # doors, windows, voids — each in a wall (structure.py)
    "openings": [],
    # section lines drawn for the documentation: {"id", "symbol", "a",
    # "b", "flip"} (docs.py) — A-A and B-B are made, these are added
    "sections": [],
    # the documentation's sheets (sheetset.py / hostsheet.py): {"style":
    # the project's changes to the style, "sheets": [{"id", "sig" (the
    # model when made), "placed" (what ArchXQ put, per key), "paper",
    # "scale", "cut", "style" (the sheet's own changes)…}]}
    "docs": {"style": {}, "sheets": []},
    # the rooms' names (the rooms themselves are found from the walls —
    # spaces.py): {"id", "level", "x", "y" (a point inside), "name"}
    "rooms": [],
    # ROOM SEPARATORS (separators.py, 2026-10-23): a line between two rooms
    # with no wall — {"id", "level", "pts": [[x, y], …]}; nothing in 3D
    "separators": [],
    # 2D drawings imported (DXF) as a reference, per level id: {"name",
    # "layers": [names], "segs": [[x0, y0, x1, y1, layer]…], "layer":
    # the one walls are made from ("" = all)} — importdxf.py
    "underlays": {},
    # ids of walls / structure / openings built at least once (ui._commit_all)
    # — one built and now without its object was DELETED with the host's
    # tools and must not come back (even when every one was deleted). None
    # = an older file: ui._live falls back to its old rule.
    "built": None,
    # the automatic slabs deleted («dig:<dig id>:<level id>», autoslabs.py):
    # they stay away
    "auto_off": [],
    # the elements hidden (their window's «Hide», the outliner's eye) —
    # view state, written without an undo step (compat.set_hidden_ids)
    "hidden_ids": [],
    # parts of a level switched off in its window («Show»): {level id:
    # [part keys of LEVEL_PARTS]} — view state too (compat.set_hidden_parts)
    "hidden_parts": {},
    # the LAYERS hidden in the 3D (the eye on a layer's row — layerview.py):
    # {type or element id: [layer ids, «studs», «fill»]} — one Ctrl+Z each
    "hidden_layers": {},
    # the levels drawn as a GHOST (light blue) under the plan of the one
    # worked on — the levels strip's per-level icon; view state too
    "ghosts": [],
    # the levels whose GUIDE SHEET shows in 3D (levelsheet.py — the strip's
    # grid icon, 2026-10-31); view state too
    "sheets": [],
    # a level's GUIDE LINES while its «Guide lines» is off: {level id:
    # [the host's guide dicts]} — out of the scene, back when shown
    "guides_off": {},
    # what each element / part is made of (materials.py): {"el": {id:
    # {part: ref}}, "type": {kind: {part: ref}}} — painted at every rebuild
    "materials": {"el": {}, "type": {}},
    "plot": None,    # {"corners": [[x, y], ...], "uid": str, "thickness",
                        #  "heights": [z per corner], "closing": side index,
                        #  "breaks": [[i, j], ...] fold lines,
                        #  "sb_front": [bool per side], "sb_custom": [m |
                        #  None per side], "sb_dist": {front, back, sides},
                        #  "survey": [[x, y, z, name], ...] ground points}
}


# ---- load / save -------------------------------------------------------------------
def load(raw) -> dict:
    """A complete, valid document from whatever the .igz holds."""
    raw = raw if isinstance(raw, dict) else {}
    doc = copy.deepcopy(DEFAULT_DOC)
    for k in ("done", "system"):
        if k in raw:
            doc[k] = raw[k]
    if isinstance(raw.get("project"), dict):
        proj = dict(DEFAULT_PROJECT)
        proj.update({k: v for k, v in raw["project"].items()
                     if k in DEFAULT_PROJECT})
        doc["project"] = proj
    if isinstance(raw.get("levels"), list) and raw["levels"]:
        doc["levels"] = raw["levels"]
    elif isinstance(raw.get("floors"), list) and raw["floors"]:
        # prototype v0.0.x kept only names, ground floor first
        doc["levels"] = [{"name": str(n), "kind": "ground" if i == 0
                          else "floor", "height": DEFAULT_HEIGHT}
                         for i, n in enumerate(raw["floors"])]
    doc["levels"] = fix_levels(doc["levels"])
    plot = raw.get("plot")
    if isinstance(plot, dict) and isinstance(plot.get("corners"), list):
        try:
            corners = [[float(p[0]), float(p[1])] for p in plot["corners"]]
        except (TypeError, ValueError, IndexError):
            corners = []
        try:
            # no key = a plot from v0.3.0, drawn flat
            thick = min(max(float(plot.get("thickness", 0.0)), 0.0), 20.0)
        except (TypeError, ValueError):
            thick = 0.0
        if len(corners) >= 3:
            n = len(corners)
            # height of the ground at each corner (0 = flat); a list that
            # doesn't match the corners (older file, bad data) → flat
            try:
                hs = [min(max(float(h), -100.0), 100.0)
                      for h in plot.get("heights") or []]
            except (TypeError, ValueError):
                hs = []
            if len(hs) != n:
                hs = [0.0] * n
            try:
                closing = int(plot.get("closing", n - 1)) % n
            except (TypeError, ValueError):
                closing = n - 1
            # fold lines: [i, j] pairs of corners, each kept once
            breaks: list[list[int]] = []
            for b in plot.get("breaks") or []:
                try:
                    i, j = sorted((int(b[0]), int(b[1])))
                except (TypeError, ValueError, IndexError):
                    continue
                if 0 <= i < j < n and [i, j] not in breaks:
                    breaks.append([i, j])
            doc["plot"] = {"corners": corners,
                           "uid": str(plot.get("uid") or ""),
                           "thickness": round(thick, 3),
                           "heights": [round(h, 3) for h in hs],
                           "closing": closing,
                           "breaks": breaks}
            doc["plot"].update(_setbacks(plot, n))
            doc["plot"]["survey"] = _survey(plot.get("survey"))
            try:                             # contour lines every … m
                step = float(plot.get("contour", CONTOUR_STEP))
            except (TypeError, ValueError):
                step = CONTOUR_STEP
            doc["plot"]["contour"] = round(min(max(step, 0.05), 50.0), 3)
    doc["digs"] = _digs(raw.get("digs"))
    doc["wall_types"] = wall_types(raw.get("wall_types"))
    doc["walls"] = _walls(raw.get("walls"),
                          {r["id"] for r in doc["levels"]},
                          {t["id"]: t for t in doc["wall_types"]})
    doc["slab_types"] = wall_types(raw.get("slab_types"))
    from . import profiles as PF
    doc["profile_types"] = PF.clean_user(raw.get("profile_types"))
    doc["structure"] = _structure(raw.get("structure"),
                                  {r["id"] for r in doc["levels"]},
                                  {t["id"]: t for t in doc["slab_types"]},
                                  {t["id"] for t in doc["profile_types"]})
    doc["openings"] = _openings(raw.get("openings"),
                                {w["id"] for w in doc["walls"]})
    doc["sections"] = _sections(raw.get("sections"))
    doc["docs"] = _docs(raw.get("docs"))
    doc["rooms"] = _rooms(raw.get("rooms"), {r["id"] for r in doc["levels"]})
    doc["separators"] = _separators(raw.get("separators"),
                                    {r["id"] for r in doc["levels"]})
    doc["underlays"] = _underlays(raw.get("underlays"),
                                  {r["id"] for r in doc["levels"]})
    if isinstance(raw.get("built"), list):
        ids = {r["id"] for r in doc["walls"] + doc["structure"]
               + doc["openings"]}
        doc["built"] = sorted({str(x) for x in raw["built"]} & ids)
    _settle_owners(doc)
    if isinstance(raw.get("hidden_ids"), list):
        doc["hidden_ids"] = sorted({str(x) for x in raw["hidden_ids"]})
    if raw.get("hidden_layers"):
        from . import layerview
        doc["hidden_layers"] = layerview.clean(raw["hidden_layers"], doc)
    if raw.get("materials"):
        from . import materials
        doc["materials"] = materials.clean(raw["materials"], doc)
    if isinstance(raw.get("ghosts"), list):
        lv_ids = {r["id"] for r in doc["levels"]}
        # (the Terrain's row has a ghost too — 2026-10-26)
        doc["ghosts"] = sorted({str(x) for x in raw["ghosts"]}
                               & (lv_ids | {"terrain"}))
    if isinstance(raw.get("sheets"), list):
        lv_ids = {r["id"] for r in doc["levels"]}
        doc["sheets"] = sorted({str(x) for x in raw["sheets"]} & lv_ids)
    if isinstance(raw.get("hidden_parts"), dict):
        lv_ids = {r["id"] for r in doc["levels"]}
        known = {k for k, _l, _kinds in LEVEL_PARTS}
        for lv, parts in raw["hidden_parts"].items():
            keep = sorted({str(p) for p in parts or []} & known) \
                if isinstance(parts, list) else []
            if lv in lv_ids and keep:
                doc["hidden_parts"][lv] = keep
    if isinstance(raw.get("guides_off"), dict):
        # (a level gone: its guides kept under its id — ui gives them back)
        doc["guides_off"] = {str(lv): [g for g in gs if isinstance(g, dict)]
                             for lv, gs in raw["guides_off"].items()
                             if isinstance(gs, list) and gs}
    if isinstance(raw.get("auto_off"), list):
        doc["auto_off"] = sorted({str(x) for x in raw["auto_off"]
                                  if str(x).startswith("dig:")})
    if isinstance(raw.get("view"), dict):
        for k in doc["view"]:
            if k in raw["view"]:
                v = raw["view"][k]
                doc["view"][k] = None if v is None and k.endswith("_dims") \
                    else bool(v)
    if doc["system"] not in ("frame", "masonry"):
        doc["system"] = "frame"
    doc["done"] = [k for k in doc["done"] if isinstance(k, str)]
    return doc


SETBACKS = {"front": 5.0, "back": 3.0, "sides": 1.5}      # m, the defaults


def _digs(raw) -> list[dict]:
    """The excavations, whatever the file holds: a valid outline (3+
    corners), a bottom rule, a unique id and name."""
    out, ids = [], set()
    for d in raw if isinstance(raw, list) else []:
        if not isinstance(d, dict):
            continue
        try:
            corners = [[float(p[0]), float(p[1])] for p in d.get("corners")]
        except (TypeError, ValueError, IndexError):
            continue
        if len(corners) < 3:
            continue
        n = len(corners)
        b = d.get("bottom") if isinstance(d.get("bottom"), dict) else {}
        mode = b.get("mode") if b.get("mode") in ("depth", "height", "level",
                                                  "elev", "corners") \
            else "elev"
        try:
            bottom = {"mode": mode}
            if mode == "depth":
                bottom["d"] = min(max(float(b.get("d", 3.0)), 0.05), 100.0)
            elif mode == "height":
                bottom["h"] = min(max(float(b.get("h", 1.0)), 0.05), 100.0)
            elif mode == "level":
                bottom.update(level=str(b.get("level") or ""),
                              offset=float(b.get("offset", -0.30)))
            elif mode == "elev":
                bottom["z"] = float(b.get("z", -3.0))
            bots = [float(z) for z in d.get("bottoms") or []]
        except (TypeError, ValueError):
            bottom, bots = {"mode": "elev", "z": -3.0}, []
        if len(bots) != n:
            bots = []
        if mode == "corners" and not bots:
            bottom = {"mode": "elev", "z": -3.0}
        did = str(d.get("id") or "") or uuid.uuid4().hex[:8]
        while did in ids:
            did = uuid.uuid4().hex[:8]
        ids.add(did)
        try:
            angles = [min(max(float(a), 5.0), 90.0)
                      for a in d.get("angles") or []]
        except (TypeError, ValueError):
            angles = []
        if len(angles) != n:
            angles = [90.0] * n              # vertical walls
        kind = "fill" if d.get("kind") == "fill" else "cut"
        out.append({"id": did, "kind": kind,
                    "name": str(d.get("name") or f"Excavation {len(out) + 1}"),
                    "corners": corners, "bottom": bottom,
                    "bottoms": [round(z, 3) for z in bots],
                    "angles": angles,
                    "uid": str(d.get("uid") or "")})
    return out


def new_dig(digs: list[dict], corners, bottom: dict,
            base: str = "Excavation", kind: str = "cut") -> dict:
    """A new terrain modification: the next free «Excavation N» (or «Ramp
    N», «Fill N»…); ``kind`` "cut" (dug) or "fill" (raised)."""
    names = {d["name"] for d in digs}
    k = 1
    while f"{base} {k}" in names:
        k += 1
    return {"id": uuid.uuid4().hex[:8], "kind": kind, "name": f"{base} {k}",
            "corners": [list(p) for p in corners], "bottom": dict(bottom),
            "bottoms": [], "angles": [90.0] * len(corners), "uid": ""}


WALL_ALIGNS = ("outside", "centre", "inside")


def wall_types(raw) -> list[dict]:
    """YOUR wall types, whatever the file holds: a unique id, a name, its
    layers (one = a plain thickness) and their sum ``t``."""
    from .walls import clean_layers
    out, ids = [], set()
    for t in raw if isinstance(raw, list) else []:
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id") or "")[:16] or uuid.uuid4().hex[:8]
        if tid in ids:
            continue
        ls = clean_layers(t.get("layers"))
        if ls is None:
            try:
                th = min(max(float(t.get("t", 0.20)), 0.01), 3.0)
            except (TypeError, ValueError):
                continue
            ls = [{"id": "core", "name": "", "t": round(th, 4),
                   "role": "core"}]
        ids.add(tid)
        out.append({"id": tid,
                    "name": str(t.get("name") or f"Type {len(out) + 1}")[:40],
                    "t": round(sum(L["t"] for L in ls), 4), "layers": ls})
        # a LIGHT-FRAME core (framing.py, 2026-11-02): its walls take it
        from .framing import clean_frame
        fr = clean_frame(t.get("frame"))
        if fr is not None:
            out[-1]["frame"] = fr
        # one made from a market card (markets.py): found again by it
        if t.get("market"):
            out[-1]["market"] = str(t["market"])[:16]
    return out


def merge_wall_types(types: list[dict], got: list[dict]) -> tuple:
    """(types + the imported ones that are new, how many) — a type whose
    NAME is here already is kept as it is here; an id taken: a new one."""
    out = [dict(t) for t in types]
    have = {t["name"] for t in out}
    ids = {t["id"] for t in out}
    n = 0
    for t in got:
        if t["name"] in have:
            continue
        if t["id"] in ids:
            t = dict(t, id=uuid.uuid4().hex[:8])
        out.append(t)
        have.add(t["name"])
        ids.add(t["id"])
        n += 1
    return out, n


def typed(w: dict, ty: dict) -> dict:
    """The wall as one of YOUR types makes it: the type's thickness and
    layers (a one-layer type: none)."""
    return dict(w, t=ty["t"], layers=[dict(L) for L in ty["layers"]]
                if len(ty["layers"]) > 1 else None,
                frame=dict(ty["frame"]) if ty.get("frame") else None)


def _walls(raw, level_ids: set, types: dict | None = None) -> list[dict]:
    """The walls, whatever the file holds: a known kind with its points,
    a thickness, an alignment, a level that exists, a unique id. A wall of
    one of YOUR types (``types``: id → type) takes its layers and
    thickness."""
    out, ids = [], set()
    types = types or {}
    for w in raw if isinstance(raw, list) else []:
        if not isinstance(w, dict) or str(w.get("level")) not in level_ids:
            continue
        ty = types.get(str(w.get("type") or "")) if not w.get("cw") else None
        if ty is not None:
            w = typed(w, ty)
        kind =w.get("kind") if w.get("kind") in ("line", "arc",
                                                  "circle") else "line"
        try:
            rec = {"kind": kind}
            if kind == "circle":
                rec["c"] = [float(w["c"][0]), float(w["c"][1])]
                rec["r"] = float(w["r"])
            else:
                rec["a"] = [float(w["a"][0]), float(w["a"][1])]
                rec["b"] = [float(w["b"][0]), float(w["b"][1])]
                if kind == "arc":
                    rec["m"] = [float(w["m"][0]), float(w["m"][1])]
            rec["t"] = min(max(float(w.get("t", 0.15)), 0.01), 3.0)
            h = w.get("height", "level")
            rec["height"] = "level" if h == "level" else \
                min(max(float(h), 0.05), 50.0)
            rec["base"] = float(w.get("base", 0.0))
            # its own TOP (sloped, a gable — straight walls): its height
            # kept at its highest point
            from .walls import clean_top, top_peak
            top = clean_top(w.get("top"), rec["height"]) \
                if kind == "line" and not w.get("cw") else None
            if top is not None:
                rec["top"] = top
                rec["height"] = top_peak(top)
            if w.get("cw"):                  # a curtain wall (curtain.py)
                from . import curtain
                rec["cw"] = True
                rec.update(curtain.clean(w))   # its own sizes and colours
        except (TypeError, ValueError, KeyError, IndexError):
            continue
        # its LAYERS (0.15.0): outside → inside, one core; ``t`` is their
        # sum — a thickness changed elsewhere (a bar, the Geometry tab) goes
        # to the core, the finishes keep theirs
        if not rec.get("cw"):
            from .walls import clean_layers
            ls = clean_layers(w.get("layers"))
            if ls:
                fin = sum(L["t"] for L in ls if L["role"] != "core")
                core = next(L for L in ls if L["role"] == "core")
                if abs(fin + core["t"] - rec["t"]) > 1e-6 \
                        and rec["t"] - fin >= 0.01:
                    core["t"] = round(rec["t"] - fin, 4)
                rec["layers"] = ls
                rec["t"] = round(sum(L["t"] for L in ls), 4)
            # its core LIGHT-FRAMED (framing.py — one layer or many)
            from .framing import clean_frame
            fr = clean_frame(w.get("frame"))
            if fr is not None:
                rec["frame"] = fr
        rec["align"] = w.get("align") if w.get("align") in WALL_ALIGNS \
            else "centre"
        if w.get("align") == "core_out":
            rec["align"] = "core_out" if rec.get("layers") else "outside"
        if ty is not None:
            rec["type"] = ty["id"]
        rec["side"] = -1 if w.get("side") == -1 else 1
        rec["level"] = str(w["level"])
        wid = str(w.get("id") or "") or uuid.uuid4().hex[:8]
        while wid in ids:
            wid = uuid.uuid4().hex[:8]
        ids.add(wid)
        rec["id"] = wid
        rec["name"] = str(w.get("name") or f"Wall {len(out) + 1}")
        out.append(rec)
    return out


_RAIL_CHOICES = {"railing": ("none", "handrail", "steel", "glass", "wall"),
                 "rail_sides": ("auto", "both", "left", "right"),
                 "rail_profile": ("round", "square"),
                 "rail_infill": ("vertical", "bars", "cables"),
                 "rail_fix": ("posts", "frameless")}
_RAIL_SIZES = {"rail_h": (0.80, 1.20), "rail_d": (0.03, 0.08),
               "rail_inset": (0.02, 0.20), "rail_ext": (0.0, 0.60),
               "rail_post": (0.02, 0.10), "rail_gap": (0.60, 2.00),
               "rail_wall_t": (0.08, 0.30),
               # the clear gap between balusters (2026-10-18)
               "rail_clear": (0.05, 1.0),
               # (not a railing's: the slab opening's «Clearance» all round —
               # his ask, 2026-10-15; kept here as «cut» is)
               "clear": (0.0, 1.0)}


def _railing(e: dict) -> dict:
    """A ramp's / stair's railing keys, kept and checked (dropped, the
    railing vanished on «Repeat», on a new stair and on reopening — his
    test, 2026-10-10). Only what the record has: the rest is the default."""
    out = {}
    for k, allowed in _RAIL_CHOICES.items():
        if e.get(k) in allowed:
            out[k] = e[k]
    for k, (lo, hi) in _RAIL_SIZES.items():
        try:
            if e.get(k) is not None:
                out[k] = min(max(float(e[k]), lo), hi)
        except (TypeError, ValueError):
            pass
    # (and «cut»: the opening it makes in the slab — False = none, a
    # customer's ask 2026-10-13; kept here so Repeat / reopen keep it)
    for k in ("rail_low", "rail_wall_top", "rail_floor", "cut"):
        if k in e:
            out[k] = bool(e[k])
    return out


def _top_of_level(end, level_ids) -> bool:
    """«top:<id>» — a ramp / stair ending at the top of a level (ramps)."""
    return isinstance(end, str) and end.startswith("top:") \
        and end[4:] in level_ids


def _settle_owners(doc: dict) -> None:
    """A ramp / stair belongs to the LOWER of its two levels — the storey
    it takes, drawn up or down (as ramps.owner; kept here so the model
    needs no Qt). Files from before 2026-10-05 had it on the start level."""
    levels = doc.get("levels") or []
    if not levels:
        return
    ground = doc["project"]["ground_level"] if has_project(doc) else 0.0
    elev = elevations(levels, ground)
    z = {lv["id"]: elev[i] for i, lv in enumerate(levels)}
    gid = next((lv["id"] for lv in levels if lv["kind"] == "ground"), None)
    height = {lv["id"]: float(lv["height"]) for lv in levels}

    def at(end):                      # (its level, its elevation) or None
        if end in z:
            return end, z[end]
        if isinstance(end, str) and end.startswith("top:") and end[4:] in z:
            return end[4:], z[end[4:]] + height[end[4:]]
        return None
    for e in doc.get("structure") or []:
        if e.get("type") not in ("ramp", "stair"):
            continue
        if e.get("start") == "z":     # «By heights»: the level under its foot
            try:
                lo = min(float(e.get("from_z", 0.0)), float(e.get("to_z", 0.0)))
            except (TypeError, ValueError):
                continue
            under = [(zl, lid) for lid, zl in z.items() if zl <= lo + 0.01]
            e["level"] = max(under)[1] if under else \
                min((zl, lid) for lid, zl in z.items())[1]
            continue
        a = at(gid if e.get("start") == "terrain" and gid else e.get("from"))
        b = at(e.get("to"))
        if a and b:
            e["level"] = a[0] if a[1] <= b[1] else b[0]
        elif a:
            e["level"] = a[0]


_ST_LABEL = {"column": "Column", "beam": "Beam", "slab": "Slab",
             "footing": "Footing", "roof": "Roof", "ramp": "Ramp",
             "stair": "Stair", "guard": "Low wall", "glazing": "Grid",
             "street": "Street", "profile": "Profile", "copy": "Copies"}
#: a grid's choices / sizes kept (glazing.py — here, without Qt); the open
#: kinds (a cobogó, a lattice, slats) since 2026-10-27, cells from 3 cm
_GLAZ_CHOICES = {"place": ("void", "free", "window"),
                 "kind": ("industrial", "aluminium", "partition", "square",
                          "diamond", "lattice", "vslats", "hslats", "bars"),
                 "by": ("size", "count"),
                 "frame": ("black", "dark", "silver", "white", "bronze",
                           "wood"),
                 "bead_c": ("black", "dark", "silver", "white", "bronze"),
                 "glass": ("clear", "blue", "green", "grey", "bronze"),
                 "outside": ("right", "left")}
_GLAZ_SIZES = {"pw": (0.03, 9.0, 0.50), "ph": (0.03, 9.0, 0.50),
               "fw": (0.01, 0.30, 0.03), "fd": (0.01, 0.50, 0.05),
               "mw": (0.005, 0.20, 0.025), "md": (0.005, 0.50, 0.04),
               "foff": (-1.0, 1.0, 0.0), "gpos": (-1.0, 0.50, -1.0),
               "gt": (0.003, 0.05, 0.008), "glass_tr": (0.0, 0.95, 0.70),
               "bw": (0.003, 0.05, 0.012), "bt": (0.002, 0.05, 0.010),
               "h": (0.2, 20.0, 2.10), "base": (-1.0, 10.0, 0.0)}
#: a low wall's / guard's choices kept (guards.py — here, so the model
#: needs no Qt)
_GUARD_CHOICES = {"kind": ("wall", "wallrail", "glass", "steel", "boundary"),
                  "on": ("auto", "floor", "ground", "roof"),
                  "top": ("stepped", "slope"),
                  "rail_top": ("steel", "glass"),
                  "rail_infill": ("vertical", "bars", "cables"),
                  "rail_fix": ("frameless", "posts"),
                  "rail_profile": ("round", "square")}


def _pt(p) -> list[float]:
    return [float(p[0]), float(p[1])]


def _wall_faces(raw) -> list:
    """A profile / copies along walls' faces: [[wall id, side ±1]…], none
    twice."""
    out = []
    for f in raw if isinstance(raw, list) else []:
        try:
            k = [str(f[0]), 1 if int(f[1]) >= 0 else -1]
        except (TypeError, ValueError, IndexError):
            continue
        if k not in out:
            out.append(k)
    return out[:200]


def _last_path(raw) -> list:
    """The path last found along walls' faces: [[pts, closed, side]…]."""
    out = []
    for r in raw if isinstance(raw, list) else []:
        try:
            pts = [[round(float(p[0]), 4), round(float(p[1]), 4)]
                   for p in r[0]]
            if len(pts) >= 2:
                out.append([pts, bool(r[1]), -1 if int(r[2]) < 0 else 1])
        except (TypeError, ValueError, IndexError):
            continue
    return out


def _copy_src(raw) -> dict | None:
    """An object copied along a path, taken from the model (copies.py):
    its faces [{"loop": [[x, y, z]…], "holes", "color"}] — None: none
    usable."""
    if not isinstance(raw, dict):
        return None
    faces = []
    try:
        for f in raw.get("faces") or []:
            loop = [[float(c) for c in p[:3]] for p in f["loop"]]
            if len(loop) < 3:
                continue
            holes = [[[float(c) for c in p[:3]] for p in h]
                     for h in f.get("holes") or [] if len(h) >= 3]
            col = [min(max(float(c), 0.0), 1.0)
                   for c in (f.get("color") or [0.7, 0.7, 0.7, 1.0])][:4]
            faces.append({"loop": loop, "holes": holes,
                          "color": col + [1.0] * (4 - len(col))})
    except (TypeError, ValueError, KeyError, IndexError):
        return None
    if not faces or len(faces) > 4000:
        return None
    return {"name": str(raw.get("name") or "Your object")[:40],
            "faces": faces}


def _crosses(cs) -> bool:
    """Two sides of the loop that are not neighbours touch / cross."""
    n = len(cs)

    def o(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return (v > 1e-12) - (v < -1e-12)

    def on(a, b, c):                 # c on a–b (collinear already)
        return min(a[0], b[0]) - 1e-9 <= c[0] <= max(a[0], b[0]) + 1e-9 \
            and min(a[1], b[1]) - 1e-9 <= c[1] <= max(a[1], b[1]) + 1e-9

    for i in range(n):
        a, b = cs[i], cs[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            c, d = cs[j], cs[(j + 1) % n]
            o1, o2, o3, o4 = o(a, b, c), o(a, b, d), o(c, d, a), o(c, d, b)
            if (o1 != o2 and o3 != o4) or (o1 == 0 and on(a, b, c)) or (
                    o2 == 0 and on(a, b, d)) or (o3 == 0 and on(c, d, a)) \
                    or (o4 == 0 and on(c, d, b)):
                return True
    return False


def clean_loop(cs, tol: float = 0.005) -> list:
    """A slab's outline with its specks gone — corners closer than ``tol``
    (5 mm) to the side joining their neighbours (a corner doubled 1 mm
    off, a 1 mm spike): his Level 5's slab, 2026-10-26 — its sides crossed
    at such a speck, and no grip would move it («The sides would cross»).
    Only for an outline that crosses itself: a sound one is left alone."""
    cs = [list(p) for p in cs]
    if len(cs) < 4 or not _crosses(cs):
        return cs

    def off(p, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        if L2 < 1e-18:
            return ((p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2) ** 0.5
        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy)
                         / L2))
        return ((p[0] - a[0] - t * dx) ** 2
                + (p[1] - a[1] - t * dy) ** 2) ** 0.5

    changed = True
    while changed and len(cs) > 3:
        changed = False
        for i in range(len(cs)):
            a, p, b = cs[i - 1], cs[i], cs[(i + 1) % len(cs)]
            if off(p, a, b) < tol:
                del cs[i]
                changed = True
                break
    return cs


def _docs(raw) -> dict:
    """The documentation's own data (``DEFAULT_DOC["docs"]``): a sheet
    record needs its id; the rest is kept as it was written (plain JSON:
    the style's changes, what was placed, the choices)."""
    raw = raw if isinstance(raw, dict) else {}
    style = raw.get("style") if isinstance(raw.get("style"), dict) else {}
    sheets, seen = [], set()
    for r in raw.get("sheets") or []:
        if isinstance(r, dict) and isinstance(r.get("id"), str) \
                and r["id"] not in seen:
            seen.add(r["id"])
            sheets.append(copy.deepcopy(r))
    return {"style": copy.deepcopy(style), "sheets": sheets}


def _sections(raw) -> list[dict]:
    """The section lines drawn for the sheets: two points, a look side,
    a symbol (C, D… — A and B are the made ones)."""
    out, ids = [], set()
    for s in raw if isinstance(raw, list) else []:
        try:
            a, b = _pt(s["a"]), _pt(s["b"])
        except (TypeError, ValueError, KeyError, IndexError):
            continue
        if (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 < 0.25:
            continue
        sid = str(s.get("id") or "") or uuid.uuid4().hex[:8]
        while sid in ids:
            sid = uuid.uuid4().hex[:8]
        ids.add(sid)
        out.append({"id": sid, "a": a, "b": b, "flip": bool(s.get("flip")),
                    "symbol": str(s.get("symbol") or "")[:3]})
    return out


def _rooms(raw, level_ids: set) -> list[dict]:
    """The rooms' names: a point inside each, on a level that exists."""
    out, ids = [], set()
    for r in raw if isinstance(raw, list) else []:
        try:
            x, y = float(r["x"]), float(r["y"])
            name = str(r["name"]).strip()[:60]
        except (TypeError, ValueError, KeyError):
            continue
        if not name or str(r.get("level")) not in level_ids:
            continue
        rid = str(r.get("id") or "") or uuid.uuid4().hex[:8]
        while rid in ids:
            rid = uuid.uuid4().hex[:8]
        ids.add(rid)
        out.append({"id": rid, "level": str(r["level"]), "x": x, "y": y,
                    "name": name})
    return out


def _separators(raw, level_ids: set) -> list[dict]:
    """The room separators, whatever the file holds: 2 points or more, a
    level that exists, a unique id."""
    out, ids = [], set()
    for r in raw if isinstance(raw, list) else []:
        try:
            pts = [[float(p[0]), float(p[1])] for p in r["pts"]]
        except (TypeError, ValueError, KeyError, IndexError):
            continue
        pts = [p for k, p in enumerate(pts)
               if k == 0 or abs(p[0] - pts[k - 1][0])
               + abs(p[1] - pts[k - 1][1]) > 1e-4]
        if len(pts) < 2 or str(r.get("level")) not in level_ids:
            continue
        sid = str(r.get("id") or "") or uuid.uuid4().hex[:8]
        while sid in ids:
            sid = uuid.uuid4().hex[:8]
        ids.add(sid)
        out.append({"id": sid, "level": str(r["level"]),
                    "pts": [[round(x, 4), round(y, 4)] for x, y in pts]})
    return out


def _underlays(raw, level_ids: set) -> dict:
    """The imported 2D drawings, per level that exists."""
    out = {}
    for lid, u in (raw.items() if isinstance(raw, dict) else []):
        if str(lid) not in level_ids or not isinstance(u, dict):
            continue
        try:
            layers = [str(n) for n in u.get("layers") or []]
            segs = [[float(s[0]), float(s[1]), float(s[2]), float(s[3]),
                     int(s[4]) if len(s) > 4 else 0]
                    for s in u.get("segs") or []]
        except (TypeError, ValueError, IndexError):
            continue
        layer = str(u.get("layer") or "")
        out[str(lid)] = {"name": str(u.get("name") or "")[:120],
                         "layers": layers, "segs": segs,
                         "layer": layer if layer in layers else "",
                         # what else the drawing says (importdxf: blocks,
                         # texts, closed outlines — the «Import CAD»)
                         "blocks": _drawing_list(u.get("blocks"), (
                             "name", "layer", "pts", "arcs")),
                         "texts": _drawing_list(u.get("texts"), (
                             "text", "x", "y", "layer")),
                         "loops": _drawing_list(u.get("loops"), (
                             "pts", "layer"))}
    return out


def _drawing_list(raw, keys) -> list:
    """An imported drawing's blocks / texts / outlines, as read (each one
    with its ``keys``; anything else dropped)."""
    out = []
    for r in raw if isinstance(raw, list) else []:
        if isinstance(r, dict) and all(k in r for k in keys):
            out.append({k: r[k] for k in keys})
    return out


def next_section_symbol(sections: list[dict]) -> str:
    """C, D, E… (A and B are the made sections), skipping those used."""
    used = {s["symbol"] for s in sections} | {"A", "B"}
    for i in range(2, 26 * 27):
        sym = chr(65 + i) if i < 26 else chr(64 + i // 26) + chr(65 + i % 26)
        if sym not in used:
            return sym
    return "?"


def _slab_layers(rec: dict, e: dict, types: dict) -> None:
    """A floor slab's LAYERS (slab layers, 2026-10-23): top → bottom, one
    core; ``t`` is their sum — a thickness changed elsewhere (a bar, a
    grip) goes to the core, the finishes keep theirs. Its top («offset»)
    stays the FINISHED floor: the core sits under the finishes on top."""
    from .walls import clean_layers
    # («stype»: a structure record's «type» is already what it is)
    ty = types.get(str(e.get("stype") or ""))
    if ty is not None:
        rec["stype"] = ty["id"]
        ls = [dict(L) for L in ty["layers"]] if len(ty["layers"]) > 1 \
            else None
        rec["t"] = ty["t"]
    else:
        ls = clean_layers(e.get("layers"))
        if ls:
            fin = sum(L["t"] for L in ls if L["role"] != "core")
            core = next(L for L in ls if L["role"] == "core")
            if abs(fin + core["t"] - rec["t"]) > 1e-6 \
                    and rec["t"] - fin >= 0.01:
                core["t"] = round(rec["t"] - fin, 4)
    if ls:
        rec["layers"] = ls
        rec["t"] = round(sum(L["t"] for L in ls), 4)


def _structure(raw, level_ids: set,
               slab_types: dict | None = None,
               profile_ids: set | None = None) -> list[dict]:
    """Columns, beams, slabs and footings, whatever the file holds: a
    known type with its own fields, a level that exists, a unique id. A
    slab of one of YOUR slab types (``slab_types``: id → type) takes its
    layers and thickness; a profile, one of YOUR profiles (``profile_ids``)
    or a native one."""
    out, ids = [], set()
    slab_types = slab_types or {}
    profile_ids = profile_ids or set()
    for e in raw if isinstance(raw, list) else []:
        if not isinstance(e, dict) or e.get("type") not in _ST_LABEL \
                or str(e.get("level")) not in level_ids:
            continue
        t = e["type"]
        try:
            rec = {"type": t, "level": str(e["level"])}
            if t == "column":
                rec.update(x=float(e["x"]), y=float(e["y"]),
                           shape="round" if e.get("shape") == "round"
                           else "rect",
                           w=min(max(float(e["w"]), 0.05), 5.0),
                           d=min(max(float(e.get("d", e["w"])), 0.05), 5.0),
                           angle=float(e.get("angle", 0.0)),
                           anchor=str(e.get("anchor")) if e.get("anchor") in (
                               "corner", "sw", "s", "se", "e", "ne", "n",
                               "nw", "w") else "centre",
                           # where it starts, from its level's floor (−: under
                           # it, into the ground; his ask 2026-10-03)
                           base=min(max(float(e.get("base", 0.0)), -20.0),
                                    20.0))
                h = e.get("height", "level")
                rec["height"] = "level" if h == "level" else \
                    min(max(float(h), 0.2), 50.0)
            elif t == "beam":
                rec.update(a=_pt(e["a"]), b=_pt(e["b"]),
                           w=min(max(float(e["w"]), 0.05), 3.0),
                           h=min(max(float(e["h"]), 0.05), 5.0))
                # its top: under the slab above (the level's), or at a
                # height of its own over the floor (Badis, 2026-10-18: a
                # lean-to's beams on 2.50 m posts)
                if e.get("zmode") == "own":
                    rec.update(zmode="own", zt=min(max(float(
                        e.get("zt", 2.5)), -20.0), 50.0))
            elif t == "slab":
                cs = clean_loop([_pt(p) for p in e["corners"]])
                if len(cs) < 3:
                    continue
                rec.update(corners=cs,
                           t=min(max(float(e["t"]), 0.02), 3.0),
                           offset=float(e.get("offset", 0.0)))
                # a CEILING (0.15.0, B4): its underside ``ch`` over the
                # floor — its top (the slab's «offset») follows from it
                if e.get("ceiling"):
                    ch = min(max(float(e.get("ch", 2.60)), 1.50), 10.0)
                    rec.update(ceiling=True, ch=round(ch, 4),
                               offset=round(ch + rec["t"], 4))
                # a BLOCK (0.15.0, B5 — his ask 2026-10-18: a platform, a
                # bench, a mass): its height ``t`` (up to 30 m) on its
                # ``base`` over the floor — its top (the «offset») follows
                elif e.get("block"):
                    h = min(max(float(e["t"]), 0.02), 30.0)
                    base = min(max(float(e.get("base", 0.0)), -20.0), 50.0)
                    rec.update(block=True, t=round(h, 4),
                               base=round(base, 4),
                               offset=round(base + h, 4))
                    # each corner's top up / down from it (2026-10-31: his
                    # ask 21/10 — a sloped top): one per corner, or none
                    zc = e.get("zc")
                    if isinstance(zc, list) and len(zc) == len(cs):
                        zc = [round(min(max(float(v), 0.02 - h), 30.0), 4)
                              for v in zc]
                        if any(abs(v) > 1e-6 for v in zc):
                            rec["zc"] = zc
                else:
                    _slab_layers(rec, e, slab_types)
                    # its core LIGHT-FRAMED: joists (PLANO_PISOS_BARROTES
                    # D1) — and which way they run (D3)
                    from .framing import clean_frame
                    # (one of YOUR types: its joists — 4b)
                    ty = slab_types.get(str(rec.get("stype") or ""))
                    fr = clean_frame((ty if ty is not None else e)
                                     .get("frame"))
                    if fr is not None and not rec.get("ceiling"):
                        rec["frame"] = fr
                        if e.get("jdir") == "turn":
                            rec["jdir"] = "turn"
                # openings through it (a stair, a lift, a void)
                rec["holes"] = [[_pt(p) for p in h]
                                for h in e.get("holes") or []
                                if isinstance(h, list) and len(h) >= 3]
                # an automatic slab: the excavation it follows (autoslabs)
                a = e.get("auto")
                if isinstance(a, dict) and a.get("dig"):
                    rec["auto"] = {"dig": str(a["dig"])}
            elif t == "roof":
                cs = [_pt(p) for p in e["corners"]]
                if len(cs) < 3:
                    continue
                kind = e.get("kind") if e.get("kind") in (
                    "gable", "hip", "flat", "shed", "hidden",
                    # (0.15.0, B6 — rectangles)
                    "butterfly", "mansard") else "flat"
                if kind != "flat" and len(cs) != 4:
                    # a pitched roof: a rectangle — or a hip / gable one
                    # over an L (roof_l.py, 2026-10-16) or any other plan
                    # (roof_any.py, 0.12.0)
                    from . import roof_any, roof_l
                    if kind not in ("gable", "hip") or not (
                            roof_l.is_l(cs) or roof_any.ok(cs)):
                        kind = "flat"
                o = min(max(float(e.get("overhang", 0.5)), 0.0), 3.0)
                rec.update(kind=kind, corners=cs,
                           slope=min(max(float(e.get("slope", 30.0)), 5.0),
                                     75.0),
                           overhang=o,
                           # the gable ends' (before: the eaves')
                           go=min(max(float(e.get("go", o)), 0.0), 3.0),
                           fall="left" if e.get("fall") == "left"
                           else "right",
                           slopes=1 if e.get("slopes") == 1 else 2,
                           pauto=bool(e.get("pauto", True)),
                           gutter=min(max(float(e.get("gutter", 0.30)),
                                          0.10), 1.0),
                           t=min(max(float(e.get("t", 0.2)), 0.02), 1.0),
                           ridge="short" if e.get("ridge") == "short"
                           else "long",
                           # a gable L: the wing keeping its gable
                           main="other" if e.get("main") == "other"
                           else "long",
                           parapet=min(max(float(e.get("parapet", 0.0)),
                                           0.0), 3.0),
                           pt=min(max(float(e.get("pt", 0.15)), 0.05), 1.0),
                           # on the walls, or at its own height (a lean-to
                           # — Badis, 2026-10-18)
                           zmode="own" if e.get("zmode") == "own"
                           else "walls",
                           zh=min(max(float(e.get("zh", 2.50)), 0.5), 50.0),
                           # a mansard's break: its steep part's height
                           mh=min(max(float(e.get("mh", 1.20)), 0.3), 6.0))
                # a gable's other side at a slope of its own (Marec,
                # 2026-11-02): none = both sides at «slope»
                if e.get("slope2") is not None:
                    rec["slope2"] = min(max(float(e["slope2"]), 5.0), 75.0)
                # …and its other eave higher (+) or lower (−), m (Marec,
                # 2026-11-02): none = both eaves on the walls' top
                if e.get("eave2") is not None \
                        and abs(float(e["eave2"])) > 1e-6:
                    rec["eave2"] = min(max(float(e["eave2"]), -5.0), 5.0)
                # its LAYERS, top → bottom (PLANO_TELHADO_CAMADAS, his OK
                # 2026-11-02): as a slab's, ``t`` their sum
                _slab_layers(rec, e, {})
                # its core LIGHT-FRAMED: rafters (step 2b, as a wall's)
                from .framing import clean_frame
                fr = clean_frame(e.get("frame"))
                if fr is not None:
                    rec["frame"] = fr
            elif t == "ramp":              # a «Building element» (ramps.py)
                rec.update(start="terrain" if e.get("start") == "terrain"
                           else "level",
                           to=str(e.get("to") or "z"),
                           to_z=min(max(float(e.get("to_z", -3.0)), -100.0),
                                    100.0),
                           x=float(e["x"]), y=float(e["y"]),
                           angle=float(e.get("angle", 0.0)),
                           w=min(max(float(e.get("w", 3.0)), 0.5), 30.0),
                           slope=min(max(float(e.get("slope", 20.0)), 1.0),
                                     50.0),
                           # the length given instead (special cases)
                           fix="length" if e.get("fix") == "length"
                           else "slope",
                           L=min(max(float(e.get("L", 15.0)), 0.5), 500.0),
                           t=min(max(float(e.get("t", 0.15)), 0.05), 1.0),
                           shape=e.get("shape") if e.get("shape") in (
                               "L", "U") else "straight",
                           turn="left" if e.get("turn") == "left"
                           else "right",
                           landing=min(max(float(e.get("landing", 3.0)),
                                           0.5), 50.0),
                           anchor=e.get("anchor") if e.get("anchor") in (
                               "left", "right") else "centre",
                           # a sloped slab, or SOLID down to the floor (his
                           # ask, 2026-10-18)
                           build="solid" if e.get("build") == "solid"
                           else "slab")
                if rec["to"] != "z" and rec["to"] not in level_ids \
                        and not _top_of_level(rec["to"], level_ids):
                    rec["to"] = "z"         # its level is gone: an elevation
            elif t == "stair":              # a «Building element» (stairs.py)
                rec.update(start="terrain" if e.get("start") == "terrain"
                           else "level",
                           to=str(e.get("to") or "z"),
                           to_z=min(max(float(e.get("to_z", -3.0)), -100.0),
                                    100.0),
                           x=float(e["x"]), y=float(e["y"]),
                           angle=float(e.get("angle", 0.0)),
                           w=min(max(float(e.get("w", 1.2)), 0.6), 10.0),
                           riser=min(max(float(e.get("riser", 0.18)), 0.10),
                                     0.25),
                           tread=min(max(float(e.get("tread", 0.28)), 0.15),
                                     0.60),
                           fix_tread=bool(e.get("fix_tread", False)),
                           t=min(max(float(e.get("t", 0.15)), 0.05), 1.0),
                           shape=e.get("shape") if e.get("shape") in (
                               "L", "U") else "straight",
                           turn="left" if e.get("turn") == "left"
                           else "right",
                           landing=min(max(float(e.get("landing", 1.2)),
                                           0.6), 20.0),
                           anchor=e.get("anchor") if e.get("anchor") in (
                               "left", "right") else "centre",
                           # Part B (2026-10-10): the landing after riser N
                           # (0 = halfway), a U's well, nosings, open treads
                           split=max(int(e.get("split", 0) or 0), 0),
                           gap=min(max(float(e.get("gap", 0.0) or 0.0),
                                       0.0), 2.0),
                           nosing=min(max(float(e.get("nosing", 0.0) or 0.0),
                                          0.0), 0.05),
                           build=e.get("build") if e.get("build") in (
                               "open", "solid") else "concrete")
                if rec["to"] != "z" and rec["to"] not in level_ids \
                        and not _top_of_level(rec["to"], level_ids):
                    rec["to"] = "z"
            elif t == "guard":              # a «Building element» (guards.py)
                pts = [_pt(p) for p in e["pts"]]
                if len(pts) < 2:
                    continue
                rec.update(pts=pts, closed=bool(e.get("closed")) and
                           len(pts) > 2,
                           h=min(max(float(e.get("h", 1.10)), 0.3), 3.0),
                           t=min(max(float(e.get("t", 0.15)), 0.05), 0.6),
                           wall_h=min(max(float(e.get("wall_h", 0.40)), 0.1),
                                      2.5),
                           base=min(max(float(e.get("base", 0.0)), -1.0),
                                    60.0),
                           cap=bool(e.get("cap", False)))
                try:            # its stepped top: each step this high at most
                    rec["step_h"] = min(max(float(e.get("step_h", 0.15)),
                                            0.05), 0.50)
                except (TypeError, ValueError):
                    rec["step_h"] = 0.15
                gaps = []       # its gaps: [from, to] along its line (m)
                for g in e.get("gaps") or []:
                    try:
                        s0, s1 = float(g[0]), float(g[1])
                    except (TypeError, ValueError, IndexError):
                        continue
                    if s1 - s0 >= 0.02:
                        gaps.append([round(s0, 4), round(s1, 4)])
                if gaps:
                    rec["gaps"] = gaps
                try:            # a boundary wall's piers (0 = none)
                    rec["pier_s"] = min(max(float(e.get("pier_s", 3.0)), 0.0),
                                        10.0)
                except (TypeError, ValueError):
                    rec["pier_s"] = 3.0
                gates = []      # its gates, each in the gap holding «at»
                for g in e.get("gates") or []:
                    if not gaps or not isinstance(g, dict):
                        break
                    try:
                        at = round(float(g["at"]), 4)
                        op = min(max(float(g.get("open", 0.0)), 0.0), 1.0)
                    except (KeyError, TypeError, ValueError):
                        continue
                    gates.append({
                        "at": at,
                        "kind": g.get("kind") if g.get("kind") in (
                            "swing", "sliding") else "swing",
                        "leaves": 2 if g.get("leaves") == 2 else 1,
                        "style": g.get("style") if g.get("style") in (
                            "bars", "solid", "slats") else "bars",
                        "finish": g.get("finish") if g.get("finish") in (
                            "anthracite", "steel", "white", "wood")
                        else "anthracite",
                        "open": op})
                if gates:
                    rec["gates"] = gates
                for k, allowed in _GUARD_CHOICES.items():
                    rec[k] = e.get(k) if e.get(k) in allowed else allowed[0]
                try:            # the clear gap between balusters (18/10)
                    if e.get("rail_clear") is not None:
                        rec["rail_clear"] = min(max(float(
                            e["rail_clear"]), 0.05), 1.0)
                except (TypeError, ValueError):
                    pass
            elif t == "street":             # «Surroundings» (streets.py)
                edges = sorted({int(k) for k in e.get("edges") or []
                                if int(k) >= 0})
                pts = [_pt(p) for p in e.get("pts") or []]
                if not edges and len(pts) < 2:
                    continue
                if edges:
                    rec["edges"] = edges
                    ext = list(e.get("ext") or [5.0, 5.0])[:2]
                    rec["ext"] = [min(max(float(x), 0.0), 200.0)
                                  for x in ext + [5.0] * (2 - len(ext))]
                if pts:
                    rec["pts"] = pts
                # by its axis: the line drawn its axis or its edge (the
                # street outside / inside it — his ask, 2026-10-28)
                if not edges and e.get("align") in ("out", "in"):
                    rec["align"] = e["align"]
                rec.update(closed=bool(e.get("closed")) and len(pts) > 2,
                           w=min(max(float(e.get("w", 7.0)), 2.0), 40.0),
                           walk=min(max(float(e.get("walk", 2.0)), 0.5),
                                    10.0),
                           curb=min(max(float(e.get("curb", 0.15)), 0.0),
                                    0.40),
                           sides=e.get("sides") if e.get("sides") in (
                               "plot", "none") else "both",
                           r=min(max(float(e.get("r", 5.0)), 0.0), 20.0),
                           base=min(max(float(e.get("base", 0.0)), -50.0),
                                    50.0),
                           line=bool(e.get("line", False)))
            elif t == "profile":            # Tools ▸ Along a path (along.py)
                from . import profiles as PF
                how = e.get("how") if e.get("how") in (
                    "room", "face", "element") else "points"
                rec.update(how=how,
                           profile=e.get("profile") if e.get("profile")
                           in PF.NATIVE or e.get("profile") in profile_ids
                           else "base_flat",
                           anchor=e.get("anchor") if e.get("anchor") in (
                               "ceiling", "height", "top") else "floor",
                           z=min(max(float(e.get("z", 0.90)), -5.0), 60.0),
                           off=min(max(float(e.get("off", 0.001)), 0.0), 1.0),
                           cut=bool(e.get("cut", True)),
                           run="repeat" if e.get("run") == "repeat"
                           else "continuous",
                           piece=min(max(float(e.get("piece", 0.60)), 0.02),
                                     50.0),
                           gap=min(max(float(e.get("gap", 0.30)), 0.0),
                                   50.0))
                if how == "element":
                    els = []
                    for k in e.get("els") or []:
                        if isinstance(k, str) and k not in els:
                            els.append(k)
                    if not els:
                        continue
                    rec["els"] = els[:200]
                elif how == "face":
                    faces = _wall_faces(e.get("faces"))
                    if not faces:
                        continue
                    rec.update(faces=faces, last=_last_path(e.get("last")))
                elif how == "room":
                    seed = e.get("seed") or []
                    if len(seed) < 2:
                        continue
                    rec["seed"] = _pt(seed)
                    rec["rings"] = [[_pt(p) for p in r]
                                    for r in e.get("rings") or []
                                    if isinstance(r, list) and len(r) > 2]
                else:
                    pts = [_pt(p) for p in e.get("pts") or []]
                    if len(pts) < 2:
                        continue
                    rec.update(pts=pts, closed=bool(e.get("closed"))
                               and len(pts) > 2,
                               side=-1 if int(e.get("side", 1) or 1) < 0
                               else 1)
            elif t == "copy":               # Tools ▸ Along a path (copies.py)
                from . import profiles as PF
                how = e.get("how") if e.get("how") in ("room", "face") \
                    else "points"

                def pick(key, items):
                    keys = [k for k, _l in items]
                    return e.get(key) if e.get(key) in keys else keys[0]

                def num(key, lo, hi, dv):
                    try:
                        return min(max(float(e.get(key, dv)), lo), hi)
                    except (TypeError, ValueError):
                        return dv
                src = _copy_src(e.get("src"))
                obj = e.get("obj")
                if obj == PF.COPY_MINE and src is None:
                    continue                 # (its object lost: nothing)
                rec.update(how=how,
                           obj=obj if obj in PF.COPY_OBJECTS
                           or obj == PF.COPY_MINE else "bollard",
                           src=src if obj == PF.COPY_MINE else None,
                           mode=pick("mode", PF.COPY_MODES),
                           by=pick("by", PF.COPY_BY),
                           count=int(num("count", 1, 2000, 5)),
                           spacing=num("spacing", 0.05, 500.0, 2.0),
                           gap=num("gap", 0.0, 500.0, 0.10),
                           ends=bool(e.get("ends", True)),
                           turn=pick("turn", PF.COPY_TURN),
                           rot=num("rot", -360.0, 360.0, 0.0),
                           off=num("off", -50.0, 50.0, 0.0),
                           base=num("base", -50.0, 100.0, 0.0),
                           cut=bool(e.get("cut", True)))
                if how == "face":
                    faces = _wall_faces(e.get("faces"))
                    if not faces:
                        continue
                    rec.update(faces=faces, last=_last_path(e.get("last")))
                elif how == "room":
                    seed = e.get("seed") or []
                    if len(seed) < 2:
                        continue
                    rec["seed"] = _pt(seed)
                    rec["rings"] = [[_pt(p) for p in r]
                                    for r in e.get("rings") or []
                                    if isinstance(r, list) and len(r) > 2]
                else:
                    pts = [_pt(p) for p in e.get("pts") or []]
                    if not pts:
                        continue
                    rec.update(pts=pts, closed=bool(e.get("closed"))
                               and len(pts) > 2,
                               side=-1 if int(e.get("side", 1) or 1) < 0
                               else 1)
            elif t == "glazing":            # a «Building element» (glazing.py)
                for k, allowed in _GLAZ_CHOICES.items():
                    rec[k] = e.get(k) if e.get(k) in allowed else allowed[0]
                for k, (lo, hi, dv) in _GLAZ_SIZES.items():
                    try:
                        rec[k] = min(max(float(e.get(k, dv)), lo), hi)
                    except (TypeError, ValueError):
                        rec[k] = dv
                rec["cols"] = min(max(int(e.get("cols", 4) or 4), 1), 40)
                # (security bars: 0 flat bars is a choice)
                rows = e.get("rows", 4)
                rec["rows"] = min(max(int(4 if rows is None else rows),
                                      0 if rec["kind"] == "bars" else 1), 40)
                rec["opaque"] = bool(e.get("opaque", False))
                rec["bead"] = bool(e.get("bead", True))
                rec["fr_on"] = bool(e.get("fr_on", True))
                if rec["place"] == "free":
                    rec.update(a=_pt(e["a"]), b=_pt(e["b"]))
                else:
                    rec["op"] = str(e.get("op") or "")
                    if not rec["op"]:
                        continue
            else:                                   # footing
                kind = "strip" if e.get("kind") == "strip" else "pad"
                rec.update(kind=kind, w=min(max(float(e["w"]), 0.1), 10.0),
                           d=min(max(float(e["d"]), 0.05), 5.0))
                if kind == "pad":
                    rec.update(x=float(e["x"]), y=float(e["y"]),
                               angle=float(e.get("angle", 0.0)))
                else:
                    rec.update(a=_pt(e["a"]), b=_pt(e["b"]))
                    if e.get("m"):
                        rec["m"] = _pt(e["m"])
        except (TypeError, ValueError, KeyError, IndexError):
            continue
        if t in ("column", "beam"):
            rec["fit"] = bool(e.get("fit", False))   # hidden in a wall
        if t in ("ramp", "stair"):
            rec.update(_railing(e))          # its railing (railings.py)
            # its landing at the top (2026-10-18): 0 = none
            try:
                tl = float(e.get("top_landing", 0.0) or 0.0)
            except (TypeError, ValueError):
                tl = 0.0
            if tl >= 0.01:
                rec["top_landing"] = round(min(tl, 20.0), 4)
            # …and at the bottom (2026-10-23): 0 = none
            try:
                fl = float(e.get("foot_landing", 0.0) or 0.0)
            except (TypeError, ValueError):
                fl = 0.0
            if fl >= 0.01:
                rec["foot_landing"] = round(min(fl, 20.0), 4)
            # the level it starts on («level» = the one it belongs to — the
            # lower; older records had them as one)
            f = str(e.get("from") or e["level"])
            rec["from"] = f if (f in level_ids or _top_of_level(
                f, level_ids)) else rec["level"]
            # «By heights» (2026-10-18): its clicked end at a typed
            # elevation, the other one «to_z»
            if e.get("start") == "z":
                rec["start"] = "z"
                rec["to"] = "z"
                rec["from_z"] = min(max(float(e.get("from_z", 0.0)), -100.0),
                                    100.0)
        eid = str(e.get("id") or "") or uuid.uuid4().hex[:8]
        while eid in ids:
            eid = uuid.uuid4().hex[:8]
        ids.add(eid)
        rec["id"] = eid
        rec["name"] = str(e.get("name") or f"{_ST_LABEL[t]} {len(out) + 1}")
        out.append(rec)
    return out


_OP_LABEL = {"door": "Door", "window": "Window", "void": "Opening"}


def _openings(raw, wall_ids: set) -> list[dict]:
    """Doors, windows, voids, whatever the file holds: a kind, a wall that
    exists (an opening goes with its wall), sizes, a unique id."""
    out, ids = [], set()
    for o in raw if isinstance(raw, list) else []:
        if not isinstance(o, dict) or o.get("kind") not in _OP_LABEL \
                or str(o.get("wall")) not in wall_ids:
            continue
        try:
            rec = {"kind": o["kind"], "wall": str(o["wall"]),
                   "pos": float(o["pos"]),
                   "w": min(max(float(o["w"]), 0.2), 20.0),
                   "h": min(max(float(o["h"]), 0.2), 20.0),
                   "sill": min(max(float(o.get("sill", 0.0)), 0.0), 20.0),
                   "swing": "right" if o.get("swing") == "right"
                   else "left"}
            if o["kind"] == "door":          # its type (library, 0.9.5)
                rec["op"] = o["op"] if o.get("op") in ("sliding", "shop",
                                                       "garage") \
                    else "swing"
                if rec["op"] == "garage":    # sectional / roll-up / tilt
                    from .structure import garage_finish, garage_kind
                    rec["garage"] = garage_kind(o)
                    rec["gfinish"] = garage_finish(o)     # its colour
                    rec["gwin"] = bool(o.get("gwin"))     # a row of windows
                if rec["op"] == "shop":      # a shopfront (shopfront.py)
                    from .shopfront import DEFAULTS
                    for k, v in DEFAULTS.items():
                        got = o.get(k, v)
                        rec[k] = type(v)(got) if not isinstance(v, bool) \
                            else bool(got)
                rec["leaves"] = 2 if str(o.get("leaves")) == "2" else 1
                # solid (plain) / panels / half glass / glass (2026-10-27)
                from .openfinish import LEAF_STYLES
                rec["leaf"] = o.get("leaf") if o.get("leaf") in LEAF_STYLES \
                    else "solid"
                # it opens to its wall's other side (a CAD's swing read)
                rec["out"] = bool(o.get("out"))
                rec["open"] = round(min(max(float(o.get("open", 0.0)),
                                            0.0), 1.0), 3)
                # an ARCHED top (0.15.0, B6): a swing door's leaf up to
                # where the arch springs, a half-round glass light over it
                if o.get("top") == "arched" and rec["op"] == "swing":
                    rec["top"] = "arched"
            elif o["kind"] == "window" and o.get("op") in (
                    "sliding", "casement", "awning", "pivot"):
                # a window with leaves (2026-10-12, PLANO_JANELAS.md)
                from .structure import window_leaves, casement_roles
                rec["op"] = o["op"]
                rec["leaves"] = window_leaves(o)
                if rec["op"] == "casement" and rec["leaves"] > 1:
                    # each leaf fixed or hinged, left to right (2026-10-31)
                    rec.update({f"role{i + 1}": r for i, r in
                                enumerate(casement_roles(o))})
                rec["out"] = bool(o.get("out"))
                rec["open"] = round(min(max(float(o.get("open", 0.0)),
                                            0.0), 1.0), 3)
            elif o["kind"] == "window" and o.get("op") == "shop":
                rec["op"] = "shop"           # a shop window (shopfront.py)
                from .shopfront import DEFAULTS
                for k, v in DEFAULTS.items():
                    got = o.get(k, v)
                    rec[k] = type(v)(got) if not isinstance(v, bool) \
                        else bool(got)
        except (TypeError, ValueError, KeyError):
            continue
        if o.get("glass") == "opaque":       # opaque panes (2026-10-14)
            rec["glass"] = "opaque"
        # its SHAPE (shapes.py, 2026-10-31) — the rectangle: nothing kept;
        # a round is as high as it is wide
        from .shapes import clean as shape_keys
        rec.update(shape_keys(dict(o, kind=rec["kind"], w=rec["w"],
                                   h=rec["h"])))
        if rec.get("shape") == "circle":
            rec["h"] = rec["w"]
        # its trim and stone sill (trim.py, 2026-10-19) — none: nothing kept
        from .trim import keys_of
        rec.update(keys_of(dict(o, **{k: rec[k] for k in ("op",)
                                      if k in rec}), rec["kind"]))
        # colours, handles, louvres, a pivot's panes (openfinish.py) — none
        # set: none kept (an old house as it was)
        from .openfinish import keys_of as finish_keys
        rec.update(finish_keys(dict(o, kind=rec["kind"], op=rec.get("op"))))
        oid = str(o.get("id") or "") or uuid.uuid4().hex[:8]
        while oid in ids:
            oid = uuid.uuid4().hex[:8]
        ids.add(oid)
        rec["id"] = oid
        rec["name"] = str(o.get("name")
                          or f"{_OP_LABEL[o['kind']]} {len(out) + 1}")
        out.append(rec)
    return out


def new_openings(openings: list[dict], recs: list[dict]) -> list[dict]:
    """New openings with the next free «Door N» / «Window N» names."""
    names = {o["name"] for o in openings}
    out = []
    for r in recs:
        label = _OP_LABEL[r["kind"]]
        k = 1
        while f"{label} {k}" in names:
            k += 1
        names.add(f"{label} {k}")
        out.append(dict(r, id=uuid.uuid4().hex[:8], name=f"{label} {k}"))
    return out


def new_elements(structure: list[dict], recs: list[dict]) -> list[dict]:
    """New structural elements with the next free «Column N» / «Beam N»…
    names (per type) and fresh ids."""
    names = {e["name"] for e in structure}
    count: dict = {}
    out = []
    for r in recs:
        label = "Boundary wall" if r["type"] == "guard" and \
            r.get("kind") == "boundary" else _ST_LABEL[r["type"]]
        k = count.get(label, 1)
        while f"{label} {k}" in names:
            k += 1
        names.add(f"{label} {k}")
        count[label] = k + 1
        out.append(dict(r, id=uuid.uuid4().hex[:8], name=f"{label} {k}"))
    return out


def new_walls(walls: list[dict], recs: list[dict]) -> list[dict]:
    """New walls with the next free «Wall N» names and fresh ids."""
    names = {w["name"] for w in walls}
    out = []
    k = 1
    for r in recs:
        while f"Wall {k}" in names:
            k += 1
        names.add(f"Wall {k}")
        out.append(dict(r, id=uuid.uuid4().hex[:8], name=f"Wall {k}"))
    return out


def _setbacks(plot: dict, n: int) -> dict:
    """The plot's setbacks, whatever the file holds: which sides are the
    front (one mark per side), a side's own distance (None = its role's),
    a side's role chosen by hand ("back" / "side", None = worked out),
    and the front / back / sides distances."""
    front = plot.get("sb_front")
    front = [bool(f) for f in front] if isinstance(front, list) \
        and len(front) == n else [False] * n
    custom = plot.get("sb_custom")
    try:
        custom = [None if c is None else round(min(max(float(c), 0.0), 100.0),
                                               3) for c in custom] \
            if isinstance(custom, list) and len(custom) == n else [None] * n
    except (TypeError, ValueError):
        custom = [None] * n
    role = plot.get("sb_role")
    role = [r if r in ("back", "side") else None for r in role] \
        if isinstance(role, list) and len(role) == n else [None] * n
    dist = dict(SETBACKS)
    for k, v in (plot.get("sb_dist") or {}).items():
        if k in dist:
            try:
                dist[k] = round(min(max(float(v), 0.0), 100.0), 3)
            except (TypeError, ValueError):
                pass
    return {"sb_front": front, "sb_custom": custom, "sb_role": role,
            "sb_dist": dist}


def _survey(raw) -> list:
    """Survey points [x, y, z, name] — elevations above the plot's ±0.00;
    a bad row is dropped, never the lot."""
    out = []
    for s in raw if isinstance(raw, list) else []:
        try:
            x, y, z = float(s[0]), float(s[1]), float(s[2])
        except (TypeError, ValueError, IndexError):
            continue
        if not all(math.isfinite(v) for v in (x, y, z)):
            continue
        name = str(s[3]) if len(s) > 3 and s[3] is not None else ""
        out.append([round(x, 4), round(y, 4),
                    round(min(max(z, -500.0), 500.0), 3), name[:40]])
    return out


def new_project(**fields) -> dict:
    proj = dict(DEFAULT_PROJECT)
    proj.update({k: v for k, v in fields.items() if k in DEFAULT_PROJECT})
    return proj


def has_project(doc: dict) -> bool:
    return isinstance(doc.get("project"), dict)


def display_date(project: dict) -> str:
    return project.get("date") or datetime.date.today().isoformat()


# ---- levels --------------------------------------------------------------------------
def fix_levels(levels) -> list[dict]:
    """Exactly one ground floor, basements below it, floors above it,
    heights clamped, names unique and never empty."""
    rows = []
    for lv in levels if isinstance(levels, list) else []:
        if not isinstance(lv, dict):
            continue
        kind = lv.get("kind") if lv.get("kind") in ("basement", "ground",
                                                    "floor") else "floor"
        try:
            h = float(lv.get("height", DEFAULT_HEIGHT))
        except (TypeError, ValueError):
            h = DEFAULT_HEIGHT
        name = str(lv.get("name") or "").strip()
        if _OLD_DEFAULT.fullmatch(name):
            name = ""               # an old default name takes the new one
        rows.append({"name": name, "kind": kind,
                     "height": round(min(max(h, MIN_HEIGHT), MAX_HEIGHT), 3),
                     "id": str(lv.get("id") or "")})
    grounds = [i for i, r in enumerate(rows) if r["kind"] == "ground"]
    if not grounds:
        # promote the lowest non-basement, or add one
        idx = next((i for i, r in enumerate(rows) if r["kind"] != "basement"),
                   None)
        if idx is None:
            rows.append({"name": "", "kind": "ground",
                         "height": DEFAULT_HEIGHT})
        else:
            rows[idx]["kind"] = "ground"
    else:
        for i in grounds[1:]:
            rows[i]["kind"] = "floor"
    g = next(i for i, r in enumerate(rows) if r["kind"] == "ground")
    below = [dict(r, kind="basement") for r in rows[:g]]
    above = [dict(r, kind="floor") for r in rows[g + 1:]]
    rows = below + [rows[g]] + above
    return _name_levels(rows)


#: default names (the prototype's and today's): they are renumbered by
#: place whenever levels change, so inserting one never gives «Level 2 (2)»
_OLD_DEFAULT = re.compile(r"Ground floor|Floor \d+|Level \d+|Basement \d+")


def _name_levels(rows: list[dict]) -> list[dict]:
    """Default names: Level 1 (the ground floor), Level 2, 3… above,
    Basement 1, 2… below. Every level gets a lasting id (its layer
    follows it through renames); an old file's levels get one from their
    place, so reading it twice gives the same ids."""
    g = next(i for i, r in enumerate(rows) if r["kind"] == "ground")
    seen: set[str] = set()
    # the ids levels already have are kept (first come keeps a repeated
    # one); only a level without one gets one — never taken from another
    ids: set[str] = set()
    for r in rows:
        if r.get("id") and r["id"] not in ids:
            ids.add(r["id"])
        else:
            r["id"] = ""
    for i, r in enumerate(rows):
        if not r["id"]:
            r["id"] = f"lv{i - g}" if f"lv{i - g}" not in ids \
                else uuid.uuid4().hex[:8]
            ids.add(r["id"])
        if not r["name"]:
            if r["kind"] == "ground":
                r["name"] = "Level 1"
            elif r["kind"] == "floor":
                r["name"] = f"Level {i - g + 1}"
            else:
                r["name"] = f"Basement {g - i}"
        base, n = r["name"], 2
        while r["name"].lower() in seen:
            r["name"] = f"{base} ({n})"
            n += 1
        seen.add(r["name"].lower())
    return rows


def elevations(levels: list[dict], ground_level: float = 0.0) -> list[float]:
    """Finished-floor elevation of each level (bottom → top)."""
    g = next(i for i, r in enumerate(levels) if r["kind"] == "ground")
    out = [0.0] * len(levels)
    out[g] = ground_level
    for i in range(g + 1, len(levels)):
        out[i] = out[i - 1] + levels[i - 1]["height"]
    for i in range(g - 1, -1, -1):
        out[i] = out[i + 1] - levels[i]["height"]
    return [round(e, 3) for e in out]


def add_floor(levels: list[dict], height: float | None = None) -> list[dict]:
    top = levels[-1]["height"] if levels else DEFAULT_HEIGHT
    return fix_levels(levels + [{"name": "", "kind": "floor",
                                 "height": height or top}])


def add_basement(levels: list[dict], height: float | None = None) -> list[dict]:
    return fix_levels([{"name": "", "kind": "basement",
                        "height": height or DEFAULT_HEIGHT}] + levels)


def insert_level(levels: list[dict], index: int, above: bool,
                 height: float | None = None) -> list[dict]:
    """A new level right above / below ``levels[index]``: a floor when it
    lands at or over the ground floor, a basement under it."""
    g = next(i for i, r in enumerate(levels) if r["kind"] == "ground")
    at = index + 1 if above else index
    kind = "floor" if (above and index >= g) or (not above and index > g) \
        else "basement"
    new = {"name": "", "kind": kind,
           "height": height or levels[index]["height"], "id": ""}
    return fix_levels(levels[:at] + [new] + levels[at:])


def remove_level(levels: list[dict], index: int) -> list[dict]:
    """Every level but the ground floor can go (the caller checks that it
    is empty)."""
    if levels[index]["kind"] == "ground":
        return levels
    return fix_levels(levels[:index] + levels[index + 1:])


def count(levels: list[dict], kind: str) -> int:
    return sum(1 for r in levels if r["kind"] == kind)
