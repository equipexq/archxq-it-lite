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
    "view": {"setbacks": True, "folds": True,
             "plot_dims": None, "setback_dims": None, "dig_dims": None,
             "plot_elev_dims": None, "dig_elev_dims": None,
             "survey_dims": None, "contour_dims": None},
    # excavations opened in the plot (see terrain.py for the fields)
    "digs": [],
    # walls, every level's (see walls.py for the fields; + "level": id,
    # "height": "level" | m, "base": m)
    "walls": [],
    # columns, beams, slabs, footings (see structure.py for the fields)
    "structure": [],
    # doors, windows, voids — each in a wall (structure.py)
    "openings": [],
    # section lines drawn for the documentation: {"id", "symbol", "a",
    # "b", "flip"} (docs.py) — A-A and B-B are made, these are added
    "sections": [],
    # the rooms' names (the rooms themselves are found from the walls —
    # spaces.py): {"id", "level", "x", "y" (a point inside), "name"}
    "rooms": [],
    # 2D drawings imported (DXF) as a reference, per level id: {"name",
    # "layers": [names], "segs": [[x0, y0, x1, y1, layer]…], "layer":
    # the one walls are made from ("" = all)} — importdxf.py
    "underlays": {},
    "plot": None,       # {"corners": [[x, y], ...], "uid": str, "thickness",
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
    doc["walls"] = _walls(raw.get("walls"),
                          {r["id"] for r in doc["levels"]})
    doc["structure"] = _structure(raw.get("structure"),
                                  {r["id"] for r in doc["levels"]})
    doc["openings"] = _openings(raw.get("openings"),
                                {w["id"] for w in doc["walls"]})
    doc["sections"] = _sections(raw.get("sections"))
    doc["rooms"] = _rooms(raw.get("rooms"), {r["id"] for r in doc["levels"]})
    doc["underlays"] = _underlays(raw.get("underlays"),
                                  {r["id"] for r in doc["levels"]})
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


def _walls(raw, level_ids: set) -> list[dict]:
    """The walls, whatever the file holds: a known kind with its points,
    a thickness, an alignment, a level that exists, a unique id."""
    out, ids = [], set()
    for w in raw if isinstance(raw, list) else []:
        if not isinstance(w, dict) or str(w.get("level")) not in level_ids:
            continue
        kind = w.get("kind") if w.get("kind") in ("line", "arc",
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
        except (TypeError, ValueError, KeyError, IndexError):
            continue
        rec["align"] = w.get("align") if w.get("align") in WALL_ALIGNS \
            else "centre"
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


_ST_LABEL = {"column": "Column", "beam": "Beam", "slab": "Slab",
             "footing": "Footing", "roof": "Roof"}


def _pt(p) -> list[float]:
    return [float(p[0]), float(p[1])]


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
                         "layer": layer if layer in layers else ""}
    return out


def next_section_symbol(sections: list[dict]) -> str:
    """C, D, E… (A and B are the made sections), skipping those used."""
    used = {s["symbol"] for s in sections} | {"A", "B"}
    for i in range(2, 26 * 27):
        sym = chr(65 + i) if i < 26 else chr(64 + i // 26) + chr(65 + i % 26)
        if sym not in used:
            return sym
    return "?"


def _structure(raw, level_ids: set) -> list[dict]:
    """Columns, beams, slabs and footings, whatever the file holds: a
    known type with its own fields, a level that exists, a unique id."""
    out, ids = [], set()
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
            elif t == "slab":
                cs = [_pt(p) for p in e["corners"]]
                if len(cs) < 3:
                    continue
                rec.update(corners=cs,
                           t=min(max(float(e["t"]), 0.02), 3.0),
                           offset=float(e.get("offset", 0.0)))
                # openings through it (a stair, a lift, a void)
                rec["holes"] = [[_pt(p) for p in h]
                                for h in e.get("holes") or []
                                if isinstance(h, list) and len(h) >= 3]
            elif t == "roof":
                cs = [_pt(p) for p in e["corners"]]
                if len(cs) < 3:
                    continue
                kind = e.get("kind") if e.get("kind") in (
                    "gable", "hip", "flat") else "flat"
                if kind != "flat" and len(cs) != 4:
                    kind = "flat"           # a pitched roof: a rectangle
                rec.update(kind=kind, corners=cs,
                           slope=min(max(float(e.get("slope", 30.0)), 5.0),
                                     75.0),
                           overhang=min(max(float(e.get("overhang", 0.5)),
                                            0.0), 3.0),
                           t=min(max(float(e.get("t", 0.2)), 0.02), 1.0),
                           ridge="short" if e.get("ridge") == "short"
                           else "long",
                           parapet=min(max(float(e.get("parapet", 0.0)),
                                           0.0), 3.0),
                           pt=min(max(float(e.get("pt", 0.15)), 0.05), 1.0))
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
        except (TypeError, ValueError, KeyError):
            continue
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
        label = _ST_LABEL[r["type"]]
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
