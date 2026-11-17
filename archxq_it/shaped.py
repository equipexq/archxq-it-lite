# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""F3c «Adopt as it is» (PLANO_CURVAS_E_FORMAS.md, 13/11/2026): ANY group of
the model becomes one of ArchXQ's elements just as it is — a «shaped»
element of ``doc["structure"]``. Its faces, their colours / textures and
its drawn edges (soft, hidden) are frozen in the record round its plan's
middle (``x``, ``y``), its heights over its level's floor + ``z``: it moves
and turns with the host's tools, counts in the quantities, goes to the IFC
by its category, is cut in the plans and sections as the rest (the host
cuts the 3D) — and LOOKS the same as before (nothing remade).

    {"type": "shaped", "id", "name", "level", "x", "y", "z", "angle",
     "cat": wall | slab | column | railing | other,
     "mesh": [{"loop": [[x, y, z]…], "holes": [[…]…],
               "a": {"color", "opacity", "mat", "texture"},
               "ef": [[p, q, "shc"]…]}…]}

``ef``: the face's edges drawn otherwise (s = soft, h = hidden, c =
curve) — each edge on ONE face. Pure (no Qt, no host): the Lite opens and
shows it; making one is the Pro's.
"""
from __future__ import annotations

import math

from .fromshape import face_area, volume as _volume


def N_(text: str) -> str:
    """A text to translate where it is shown (i18n_extract reads it)."""
    return text


#: the most faces a piece adopted may have (a whole furnished room is no
#: «piece»: the model slows, the file grows)
MAX_FACES = 20000
CATS = ("wall", "slab", "column", "railing", "other")
CAT_LABEL = {"wall": N_("Wall"), "slab": N_("Slab"), "column": N_("Column"),
             "railing": N_("Railing"), "other": N_("Other")}
#: the IFC class by category (``ifctags``)
IFC_CLASS = {"wall": "IfcWall", "slab": "IfcSlab", "column": "IfcColumn",
             "railing": "IfcRailing", "other": "IfcBuildingElementProxy"}
#: the «Show» chip that shows / hides it, by category (ui.SHOW_KINDS)
SHOW_PART = {"wall": "walls", "slab": "slabs", "column": "structure",
             "railing": "structure", "other": "structure"}
EDGE_FLAGS = "shc"
WHY_EMPTY = N_("No faces in it to adopt")
WHY_BIG = N_("Too big to adopt as one piece (at most 20 000 faces)")
WHY_OURS = N_("Something of ArchXQ's is in it — explode it first")
ND = 5                                  # decimals kept (1/100 mm)


def _num(v, lo=-1e6, hi=1e6) -> float:
    v = float(v)
    if not math.isfinite(v):
        raise ValueError("not a number")
    return min(max(v, lo), hi)


def _p3(p) -> list:
    return [round(_num(c), ND) for c in list(p)[:3]] if len(p) >= 3 \
        else None


# ---- what a face looks like ---------------------------------------------------------------
def clean_attrs(a) -> dict:
    """A face's look, kept as the host has it: its colour, see-through,
    the material it was painted with, its texture (path and size)."""
    out: dict = {}
    if not isinstance(a, dict):
        return out
    try:
        c = a.get("color")
        if c is not None and len(list(c)) >= 3:
            out["color"] = [round(_num(v, 0.0, 1.0), 4) for v in list(c)[:4]]
    except (TypeError, ValueError):
        pass
    try:
        if a.get("opacity") is not None:
            out["opacity"] = round(_num(a["opacity"], 0.0, 1.0), 4)
    except (TypeError, ValueError):
        pass
    if isinstance(a.get("mat"), str) and a["mat"]:
        out["mat"] = a["mat"][:160]
    tx = a.get("texture")
    if isinstance(tx, dict) and isinstance(tx.get("path"), str):
        t = {}
        for k, v in tx.items():          # (path, sw, sh — and whatever
            if isinstance(v, bool):      # else the host keeps: plain values)
                t[str(k)] = v
            elif isinstance(v, (int, float)) and math.isfinite(float(v)):
                t[str(k)] = v
            elif isinstance(v, str):
                t[str(k)] = v[:1000]
        out["texture"] = t
    return out


# ---- from the model ----------------------------------------------------------------------
def edge_key(a, b) -> frozenset:
    """As ``seams.edge_key`` (here: the Lite's, pure)."""
    return frozenset((tuple(round(c, 4) for c in a[:3]),
                      tuple(round(c, 4) for c in b[:3])))


def from_loops(loops, edges=()) -> dict | None:
    """The piece's frozen mesh from the model's faces — ``loops``:
    [(outer, holes, attrs)] in the model's metres, ``edges``: [(p, q,
    flags)] its edges drawn otherwise. → {"x", "y", "z" (its lowest point,
    in the model), "mesh"}; None: nothing usable."""
    loops = [(o, hs, a) for o, hs, a in loops if len(o) >= 3]
    if not loops or len(loops) > MAX_FACES:
        return None
    pts = [p for o, _h, _a in loops for p in o]
    cx = (max(p[0] for p in pts) + min(p[0] for p in pts)) / 2
    cy = (max(p[1] for p in pts) + min(p[1] for p in pts)) / 2
    z0 = min(p[2] for p in pts)
    cx, cy, z0 = round(cx, 4), round(cy, 4), round(z0, 4)

    def mv(p):
        return [round(p[0] - cx, ND), round(p[1] - cy, ND),
                round(p[2] - z0, ND)]
    flags = {}
    for p, q, fl in edges or ():
        fl = "".join(ch for ch in EDGE_FLAGS if ch in str(fl))
        if fl:
            flags[edge_key(p, q)] = (p, q, fl)
    used = set()
    mesh = []
    for o, hs, a in loops:
        ef = []
        for ring in [o] + [h for h in hs if len(h) >= 3]:
            for i in range(len(ring)):
                k = edge_key(ring[i], ring[(i + 1) % len(ring)])
                if k in flags and k not in used:
                    used.add(k)
                    p, q, fl = flags[k]
                    ef.append([mv(p), mv(q), fl])
        f = {"loop": [mv(p) for p in o],
             "holes": [[mv(p) for p in h] for h in hs if len(h) >= 3],
             "a": clean_attrs(a)}
        if ef:
            f["ef"] = ef
        mesh.append(f)
    return {"x": cx, "y": cy, "z": z0, "mesh": mesh}


def clean_mesh(raw) -> list | None:
    """The mesh whatever the file holds (``model``): None — none usable."""
    if not isinstance(raw, list) or not raw or len(raw) > MAX_FACES:
        return None
    out = []
    try:
        for f in raw:
            loop = [_p3(p) for p in f["loop"]]
            if len(loop) < 3 or any(p is None for p in loop):
                continue
            holes = []
            for h in f.get("holes") or []:
                ring = [_p3(p) for p in h]
                if len(ring) >= 3 and all(p is not None for p in ring):
                    holes.append(ring)
            rec = {"loop": loop, "holes": holes, "a": clean_attrs(f.get("a"))}
            ef = []
            for e in f.get("ef") or []:
                p, q = _p3(e[0]), _p3(e[1])
                fl = "".join(ch for ch in EDGE_FLAGS if ch in str(e[2]))
                if p is not None and q is not None and fl:
                    ef.append([p, q, fl])
            if ef:
                rec["ef"] = ef
            out.append(rec)
    except (TypeError, ValueError, KeyError, IndexError):
        return None
    return out or None


def why_not(e: dict) -> str | None:
    mesh = e.get("mesh")
    if not isinstance(mesh, list) or not mesh:
        return WHY_EMPTY
    if len(mesh) > MAX_FACES:
        return WHY_BIG
    float(e["x"]), float(e["y"])
    return None


# ---- in the model ------------------------------------------------------------------------
def _placer(e: dict, z0: float):
    ang = math.radians(float(e.get("angle", 0.0)))
    c, s = math.cos(ang), math.sin(ang)
    x, y = float(e["x"]), float(e["y"])
    zb = z0 + float(e.get("z", 0.0))

    def mv(p):
        return (round(x + p[0] * c - p[1] * s, 6),
                round(y + p[0] * s + p[1] * c, 6), round(zb + p[2], 6))
    return mv


def faces(e: dict, z0: float = 0.0) -> list:
    """Its faces where it stands — its level's floor at ``z0`` — each
    with its own look (``attrs``) and edges (``ef``): ``compat.mesh_of``
    puts them back exactly (no seam softened of its own)."""
    mv = _placer(e, z0)
    out = []
    for f in e.get("mesh") or []:
        a = dict(f.get("a") or {})
        d = {"loop": [mv(p) for p in f["loop"]],
             "holes": [[mv(p) for p in h] for h in f.get("holes") or []],
             "attrs": a,
             "ef": [(mv(p), mv(q), fl) for p, q, fl in f.get("ef") or []]}
        if a.get("color"):
            c = list(a["color"])[:3]
            d["color"] = tuple(c) + (float(a.get("opacity", 1.0)),)
        out.append(d)
    return out


def rings(e: dict) -> list:
    """Each face's rings (outer, holes), unplaced — sizes, volume."""
    return [[f["loop"]] + list(f.get("holes") or [])
            for f in e.get("mesh") or []]


def closed(e: dict) -> bool:
    """Every edge between exactly two faces: a solid (its volume counts)."""
    n: dict = {}
    for rs in rings(e):
        for r in rs:
            for i in range(len(r)):
                k = edge_key(r[i], r[(i + 1) % len(r)])
                n[k] = n.get(k, 0) + 1
    return bool(n) and all(v == 2 for v in n.values())


def volume(e: dict) -> float:
    """m³ — a closed piece's; an open one (faces only): 0."""
    return _volume(rings(e)) if closed(e) else 0.0


def area(e: dict) -> float:
    """Its faces' area, m² (holes taken off)."""
    return sum(face_area(rs) for rs in rings(e))


def size(e: dict) -> tuple:
    """(its plan's long side, its short side, its height) — the smallest
    rectangle round its plan, whatever its turn."""
    pts = [p for f in e.get("mesh") or [] for p in f["loop"]]
    if not pts:
        return 0.0, 0.0, 0.0
    h = max(p[2] for p in pts) - min(p[2] for p in pts)
    try:
        from shapely.geometry import MultiPoint
        r = MultiPoint([(p[0], p[1]) for p in pts]).minimum_rotated_rectangle
        cs = list(r.exterior.coords)[:4] if hasattr(r, "exterior") else []
    except Exception:  # noqa: BLE001 — its box along the axes
        cs = []
    if len(cs) == 4:
        a, b = math.dist(cs[0], cs[1]), math.dist(cs[1], cs[2])
    else:
        a = max(p[0] for p in pts) - min(p[0] for p in pts)
        b = max(p[1] for p in pts) - min(p[1] for p in pts)
    return max(a, b), min(a, b), h


def guess_cat(e: dict) -> str:
    """What it most likely is, by its sizes: thin and lying = a slab,
    thin and standing = a wall (low = a railing), tall and slender = a
    column — else «Other». Only the window's first pick: his to change."""
    long, short, h = size(e)
    if long < 1e-6:
        return "other"
    if h <= 0.6 and h * 4 <= short:
        return "slab"
    if h >= 1.5 and long <= 1.2 and h >= 2.5 * long:
        return "column"
    if short <= 0.6 and long >= 3 * short and long >= 0.5:
        if h >= 1.5:
            return "wall"
        if h >= 0.5:
            return "railing"
    return "other"

