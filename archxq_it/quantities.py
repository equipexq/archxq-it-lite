# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""QUANTITIES — the building's take-off, to a CSV a spreadsheet opens (0.15.0,
D1 — PLANO_0150.md: «the natural pair of your own wall types»).

One row per item and level, then the item's total over every level («All
levels») — a table to filter or pivot:

    Category · Item · Level · Count · Length · Area · Volume

    Walls          by YOUR type (its name), else «Wall 20 cm» / «Curtain
                   wall»: length (its drawn line), area (one face, the
                   openings taken out), volume (its joined plan × height,
                   the openings taken out — a corner counted once)
    Wall layers    a type's / a wall's layers, each: area, volume (the
                   stone, the brick, the plaster to order)
    Wall framing   a light-framed core (framing.py): its studs (count, the
                   short ones too), plates / sills / headers (length), the
                   insulation between (volume)
    Doors / Windows / Voids   by kind and size: count, area
    Slabs          by YOUR type, else thickness (Ceiling, Block apart):
                   area (holes out), volume
    Slab layers    a layered slab's layers, each: area (the finishes on
                   top between the walls), volume (the screed to order)
    Floors         each room's floor on a layered slab, by room and its
                   material: area — Floor finishes: by material
    Columns, Beams, Footings   by section: count, length, volume
    Roofs          by kind: the roof's covered area (its top faces, as
                   built — slopes, hips, overhangs)
    Low walls, Grids           by kind: length, area (a grid in an
                               Opening: the opening's)
    Streets        asphalt and sidewalks: area; curbs: length
    Stairs, Ramps  count
    Rooms          area
    Excavations    volume of earth (fills: brought in)

In the document's units (metres; a feet / inches document: ft, ft², ft³).
The items' words are the Library cards' (``type_label``), in ArchXQ's
language; the file's separators are the spreadsheet's there.
"""
from __future__ import annotations

import csv
import math

from . import framing as FR
from . import model
from . import structure as S
from . import walls as W
from .i18n import N_, tr

#: the categories, in the file's order (their words translated as written)
CATEGORIES = (N_("Walls"), N_("Wall layers"), N_("Wall framing"),
              N_("Doors"), N_("Windows"),
              N_("Voids"), N_("Slabs"), N_("Slab layers"),
              N_("Floor framing"), N_("Floors"),
              N_("Floor finishes"), N_("Columns"), N_("Beams"),
              N_("Footings"), N_("Roofs"), N_("Roof layers"),
              N_("Roof framing"), N_("Low walls"),
              N_("Grids"), N_("Stairs"), N_("Ramps"), N_("Streets"),
              N_("Rooms"), N_("Excavations"))
_WORDS = (N_("Curtain wall"), N_("Wall"), N_("Slab"), N_("Ceiling"),
          N_("Block"), N_("Column"), N_("Round column"), N_("Beam"),
          N_("Pad footing"), N_("Strip footing"), N_("Fill"),
          N_("Asphalt"), N_("Sidewalk"), N_("Curb"),
          N_("All levels"), N_("Category"), N_("Item"), N_("Level"),
          N_("Count"), N_("Length"), N_("Area"), N_("Volume"))
FT = 0.3048


def _area(loop) -> float:
    n = len(loop)
    return abs(sum(loop[i][0] * loop[(i + 1) % n][1]
                   - loop[(i + 1) % n][0] * loop[i][1] for i in range(n))) / 2


def _piece_area(pc) -> float:
    return _area(pc["outer"]) - sum(_area(h) for h in pc.get("holes") or [])


def _cm(v: float) -> str:
    v = round(float(v) * 100, 1)
    return f"{v:g} cm"


def _m(v: float) -> str:
    return f"{float(v):.2f}"


def type_label(element: str, rec: dict) -> str:
    """The Library card an element's record answers to, by its words
    («Glass sliding», «Low wall + railing», «Mansard»…) in the language —
    else its raw kind."""
    try:
        from . import library as LB
        shelf = LB.CATALOG[element]
        key = LB.current_type(shelf, rec)
        for t in shelf.types:
            if t.key == key:
                return tr(t.label)
    except Exception:  # noqa: BLE001
        pass
    return tr(str(rec.get("kind") or rec.get("op") or "").capitalize())


class _Sum:
    """Rows summed by (category, item, level)."""

    def __init__(self) -> None:
        self.rows: dict = {}

    def add(self, cat, item, level, n=0, length=0.0, area=0.0, vol=0.0):
        k = (cat, item, level)
        r = self.rows.setdefault(k, [0, 0.0, 0.0, 0.0])
        r[0] += n
        r[1] += length
        r[2] += area
        r[3] += vol


def take_off(doc: dict, elevations=model.elevations, volumes=None) -> list:
    """[{"cat", "item", "level", "n", "length", "area", "volume"}] in
    METRES — per level, then each item's «All levels» total.
    ``volumes``: {dig id: m³} (compat.dig_volumes — IngeTrazo's), else
    each excavation's own."""
    # (a framed wall at a pitched roof's gable end: counted up to the roof,
    # as it is built — structure.roof_tops)
    doc = S.with_roof_tops(doc, elevations)
    info = S.levels_info(doc, elevations)
    names = {lv["id"]: lv["name"] for lv in doc["levels"]}
    order = [lv["id"] for lv in doc["levels"]]
    types = {t["id"]: t for t in doc.get("wall_types") or []}
    s = _Sum()
    walls = doc.get("walls") or []
    ops = doc.get("openings") or []

    # ---- walls (and their layers) ------------------------------------------------
    for lid in order:
        if lid not in info:
            continue
        li = info[lid]
        mine = [w for w in walls if w["level"] == lid]
        if not mine:
            continue
        plans = W.plan(mine)
        fix = S.frame_marks(doc, lid, mine, plans)   # (T / beam studs, 4a)
        for w in mine:
            pcs = plans.get(w["id"])
            if not pcs:
                continue
            if w["id"] in fix:
                w = dict(w, _fix=fix[w["id"]])
            b = li["z0"] + float(w.get("base", 0.0))
            top = li["under"] if w.get("height", "level") == "level" \
                else li["z0"] + float(w["height"])
            h = top - b
            if W.top_of(w) is not None:      # its own top: its mean height
                h = li["z0"] + W.top_mean(w) - b
            if h < 0.01:
                continue
            t = float(w["t"])
            L = W.drawn(w).L
            holes = [f for f in (S.fitted(o, w, ops, top - li["z0"])
                                 for o in ops if o["wall"] == w["id"])
                     if f is not None]
            a_ops = sum(float(o["w"]) * float(o["h"]) for o in holes)
            area = max(L * h - a_ops, 0.0)
            vol = max(sum(_piece_area(p) for p in pcs) * h - a_ops * t, 0.0)
            ty = types.get(str(w.get("type") or ""))
            if w.get("cw"):
                item = tr("Curtain wall")
            elif ty is not None:
                item = ty["name"]
            else:
                item = f"{tr('Wall')} {_cm(t)}"
            s.add("Walls", item, lid, 1, L, area, vol)
            layers = W.layers_of(w)
            if len(layers) > 1 and not w.get("cw"):
                for la in layers:
                    k = float(la["t"]) / t if t > 0 else 0.0
                    name = la.get("name") or tr(la.get("role", ""))
                    s.add("Wall layers", f"{item} · {name} {_cm(la['t'])}",
                          lid, 0, 0.0, area, vol * k)
            fr = FR.count(w, pcs, holes, li["z0"], b, top)
            if fr is not None:               # a light-framed core
                s.add("Wall framing", f"{item} · {tr('Studs')}", lid,
                      fr["studs"], 0.0, 0.0, 0.0)
                s.add("Wall framing",
                      f"{item} · {tr('Plates and sills')}", lid,
                      0, fr["plates"], 0.0, 0.0)
                for h, m in fr["headers"].items():   # by depth (its span)
                    s.add("Wall framing",
                          f"{item} · {tr('Header')} {_cm(h)}", lid,
                          0, m, 0.0, 0.0)
                if fr.get("blocking", 0) > 0:        # (tall walls, 4b)
                    s.add("Wall framing", f"{item} · {tr('Blocking')}",
                          lid, 0, fr["blocking"], 0.0, 0.0)
                if fr["fill"] > 0:
                    s.add("Wall framing", f"{item} · {tr('Insulation')}",
                          lid, 0, 0.0, 0.0, fr["fill"])

    # ---- openings -------------------------------------------------------------------
    by_wall = {w["id"]: w for w in walls}
    for o in ops:
        w = by_wall.get(o["wall"])
        if w is None:
            continue
        cat = {"door": "Doors", "window": "Windows"}.get(o["kind"], "Voids")
        label = type_label(o["kind"], o) + " " \
            if o["kind"] in ("door", "window") else ""
        item = f"{label}{_m(o['w'])} × {_m(o['h'])}"
        s.add(cat, item, w["level"], 1, 0.0,
              float(o["w"]) * float(o["h"]), 0.0)

    # ---- structure -------------------------------------------------------------------
    built_roofs = {}
    roofs = [e for e in doc.get("structure") or [] if e["type"] == "roof"
             and S.why_not(e) is None]
    if roofs:
        try:
            built_roofs = {e["id"]: e["faces"] for e in S.build(
                doc, elevations, only={r["id"] for r in roofs})}
        except Exception:  # noqa: BLE001 — the roofs' plan then
            built_roofs = {}
    slab_types = {t["id"]: t for t in doc.get("slab_types") or []}
    streets = {}                 # {id: (asphalt, sidewalk, curb)} (Pro)
    try:
        from . import streets as SR
        for lid in info:
            mine = [e for e in doc.get("structure") or []
                    if e["type"] == "street" and e["level"] == lid]
            if mine:
                streets.update(SR.measures(mine, doc.get("plot")))
    except Exception:  # noqa: BLE001 — the Lite, or none measured
        streets = {}
    feet: dict = {}

    def walls_of(lid):
        """The level's walls in plan (``S.walls_footprint``), once."""
        if lid not in feet:
            mine = [w for w in walls if w["level"] == lid]
            feet[lid] = S.walls_footprint(W.plan(mine)) if mine else None
        return feet[lid]
    for e in doc.get("structure") or []:
        if S.why_not(e) is not None or e["level"] not in info:
            continue
        lid, li, typ = e["level"], info[e["level"]], e["type"]
        if typ == "slab":
            a = _area(e["corners"]) - sum(_area(hh)
                                          for hh in e.get("holes") or [])
            t = float(e["t"])
            if e.get("ceiling"):
                s.add("Slabs", tr("Ceiling"), lid, 1, 0.0, a, a * t)
            elif e.get("block"):
                s.add("Slabs", tr("Block"), lid, 1, 0.0, a, a * t)
            else:
                ty = slab_types.get(str(e.get("stype") or ""))
                item = ty["name"] if ty is not None \
                    else f"{tr('Slab')} {_cm(t)}"
                s.add("Slabs", item, lid, 1, 0.0, a, a * t)
                if len(S.slab_layers(e)) > 1:
                    _slab_layers(s, doc, e, item, a, walls_of(lid))
                fc = S.slab_count(e)
                if fc:
                    # its joists (PLANO_PISOS_BARROTES D9): how many and
                    # their metres, the rim, doubled round the openings
                    s.add("Floor framing", f"{item} · {tr('Joists')} "
                          f"{_cm(fc['depth'])}", lid, fc["joists"],
                          fc["joist_m"], 0.0, 0.0)
                    s.add("Floor framing", f"{item} · {tr('Rim joist')}",
                          lid, 0, fc["rim_m"], 0.0, 0.0)
                    if fc["header_m"] > 0:
                        s.add("Floor framing",
                              f"{item} · {tr('Doubled round openings')}",
                              lid, 0, fc["header_m"], 0.0, 0.0)
                    if fc.get("blocking_m", 0.0) > 0:    # (mid-span, 4b)
                        s.add("Floor framing",
                              f"{item} · {tr('Blocking')}", lid, 0,
                              fc["blocking_m"], 0.0, 0.0)
                    if fc.get("fill", 0.0) > 0:
                        s.add("Floor framing",
                              f"{item} · {tr('Insulation')}", lid, 0, 0.0,
                              0.0, fc["fill"])
        elif typ == "column":
            base = float(e.get("base", 0.0))
            h = (li["under"] - li["z0"] - base) \
                if e.get("height", "level") == "level" else float(e["height"])
            if e.get("shape") == "round":
                sec = math.pi * (float(e["w"]) / 2) ** 2
                item = f"{tr('Round column')} Ø{_cm(e['w'])}"
            else:
                sec = float(e["w"]) * float(e["d"])
                item = f"{tr('Column')} {_cm(e['w'])} × {_cm(e['d'])}"
            s.add("Columns", item, lid, 1, h, 0.0, sec * h)
        elif typ == "beam":
            L = math.dist(e["a"], e["b"])
            s.add("Beams", f"{tr('Beam')} {_cm(e['w'])} × {_cm(e['h'])}",
                  lid, 1, L, 0.0, L * float(e["w"]) * float(e["h"]))
        elif typ == "footing":
            if e.get("kind") == "strip":
                L = math.dist(e["a"], e["b"])
                s.add("Footings", f"{tr('Strip footing')} {_cm(e['w'])} × "
                      f"{_cm(e['d'])}", lid, 1, L, 0.0,
                      L * float(e["w"]) * float(e["d"]))
            else:
                s.add("Footings", f"{tr('Pad footing')} {_cm(e['w'])} × "
                      f"{_cm(e['w'])} × {_cm(e['d'])}", lid, 1, 0.0, 0.0,
                      float(e["w"]) ** 2 * float(e["d"]))
        elif typ == "roof":
            faces = built_roofs.get(e["id"])
            a = roof_area(faces) if faces else 0.0
            if a <= 0:               # (no tile faces — a flat one: its plan)
                a = _area(e["corners"])
            s.add("Roofs", type_label("roof", e), lid, 1, 0.0, a, 0.0)
            # in layers: each one's area; its rafters (step 2b)
            rc = S.roof_count(doc, elevations, e)
            item = type_label("roof", e)
            fr = rc.get("rafters") is not None or \
                rc.get("trusses") is not None
            for la, la_a in rc.get("layers") or ():
                if len(rc["layers"]) < 2 or (fr and la["role"] == "core"):
                    continue
                name = la.get("name") or tr(la.get("role", ""))
                s.add("Roof layers", f"{item} · {name} {_cm(la['t'])}",
                      lid, 0, 0.0, la_a, la_a * float(la["t"]))
            # its eaves' boards (fascia, soffit — 2026-11-02)
            if rc.get("fascia_m"):
                s.add("Roof framing", f"{item} · {tr('Fascia')}", lid, 0,
                      rc["fascia_m"], 0.0, 0.0)
            if rc.get("soffit_m2"):
                s.add("Roof framing", f"{item} · {tr('Soffit')}", lid, 0,
                      0.0, rc["soffit_m2"], 0.0)
            if rc.get("trusses") is not None:
                # its trusses (PLANO_TELHADO_ASNAS D10): how many, of what
                # shape over what span; their timber, apart
                from .framing import TRUSS_NAMES
                n = rc["trusses"]
                s.add("Roof framing", f"{item} · {tr('Trusses')} "
                      f"{tr(TRUSS_NAMES[rc['pattern']])} "
                      f"{_m(rc['span'])} m", lid, n, 0.0, 0.0, 0.0)
                for key, name in (("top_m", "Top chords"),
                                  ("bottom_m", "Bottom chords"),
                                  ("web_m", "Webs")):
                    if rc[key] > 0:
                        s.add("Roof framing", f"{item} · {tr(name)} "
                              f"{_cm(rc['depth'])}", lid, 0, rc[key],
                              0.0, 0.0)
                if rc["barge"]:
                    s.add("Roof framing", f"{item} · {tr('Barge rafters')}",
                          lid, rc["barge"], rc["barge_m"], 0.0, 0.0)
                if rc.get("fill", 0.0) > 0:
                    s.add("Roof framing", f"{item} · {tr('Insulation')}",
                          lid, 0, 0.0, 0.0, rc["fill"])
            elif fr:
                s.add("Roof framing", f"{item} · {tr('Rafters')} "
                      f"{_cm(rc['depth'])}", lid, rc["rafters"],
                      rc["rafter_m"], 0.0, 0.0)
                if rc["ridge_m"] > 0:
                    s.add("Roof framing", f"{item} · {tr('Ridge board')}",
                          lid, 1, rc["ridge_m"], 0.0, 0.0)
                if rc.get("hip_m", 0) > 0:          # (a hip roof — 4d)
                    s.add("Roof framing", f"{item} · {tr('Hip rafters')}",
                          lid, 4, rc["hip_m"], 0.0, 0.0)
                if rc.get("fill", 0.0) > 0:
                    s.add("Roof framing", f"{item} · {tr('Insulation')}",
                          lid, 0, 0.0, 0.0, rc["fill"])
        elif typ == "guard":
            pts = e.get("pts") or []
            L = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
            if e.get("closed") and len(pts) > 2:
                L += math.dist(pts[-1], pts[0])
            s.add("Low walls", type_label("guard", e), lid,
                  1, L, L * float(e.get("h", 0.0)), 0.0)
        elif typ == "glazing":
            if e.get("a") and e.get("b"):          # free: its two points
                L, h = math.dist(e["a"], e["b"]), float(e.get("h", 0.0))
            else:                                  # in an Opening: its size
                o = next((x for x in ops if x["id"] == e.get("op")), None)
                L, h = ((float(o["w"]), float(o["h"])) if o is not None
                        else (0.0, 0.0))
            s.add("Grids", type_label("glazing", e), lid, 1, L, L * h, 0.0)
        elif typ == "street":
            a, w, c = streets.get(e["id"], (0.0, 0.0, 0.0))
            s.add("Streets", tr("Asphalt"), lid, 1, 0.0, a, 0.0)
            if w > 0:
                s.add("Streets", tr("Sidewalk"), lid, 0, 0.0, w, 0.0)
                s.add("Streets", tr("Curb"), lid, 0, c, 0.0, 0.0)
        elif typ in ("stair", "ramp"):
            cat = "Stairs" if typ == "stair" else "Ramps"
            s.add(cat, f"{type_label(typ, e)} {_m(e['w'])}", lid, 1)

    # ---- rooms ------------------------------------------------------------------------
    try:
        from . import spaces
        for lid in order:
            for room in spaces.of_level(doc, lid):
                s.add("Rooms", room["name"], lid, 1, 0.0, room["area"], 0.0)
    except Exception:  # noqa: BLE001 — no rooms found: none listed
        pass

    # ---- excavations --------------------------------------------------------------------
    if doc.get("plot"):
        from . import terrain
        for g in doc.get("digs") or []:
            try:
                v = (volumes or {}).get(g["id"])
                if v is None:
                    v = terrain.volume(g, doc)
            except Exception:  # noqa: BLE001
                continue
            name = g.get("name") or ""
            if terrain.is_fill(g):
                name = f"{tr('Fill')} — {name}"
            s.add("Excavations", name, "", 1, 0.0, 0.0, abs(float(v)))

    # ---- the rows: per level, then «All levels» ---------------------------------------
    rank = {c: i for i, c in enumerate(CATEGORIES)}
    lrank = {lid: i for i, lid in enumerate(order)}
    groups: dict = {}                   # (cat, item) → its levels' rows
    for (cat, item, lid), (n, L, a, v) in s.rows.items():
        groups.setdefault((cat, item), []).append(
            (lrank.get(lid, -1), {"cat": cat, "item": item,
                                  "level": names.get(lid, ""), "n": n,
                                  "length": L, "area": a, "volume": v}))
    out = []
    # (a build-up reads as it is built: top to bottom, outside to inside —
    # the layers keep the order they were added in, never the alphabet's;
    # sorted() is stable, so each element's stay together in order)
    layered = {"Wall layers", "Slab layers", "Roof layers"}
    for key in sorted(groups, key=lambda k: (
            rank.get(k[0], 99),
            k[1].split(" · ")[0] if k[0] in layered else k[1])):
        rows = [r for _k, r in sorted(groups[key], key=lambda x: x[0])]
        out += rows
        if len(rows) > 1:            # on more than one level: its total
            out.append({"cat": key[0], "item": key[1],
                        "level": tr("All levels"),
                        "n": sum(r["n"] for r in rows),
                        "length": sum(r["length"] for r in rows),
                        "area": sum(r["area"] for r in rows),
                        "volume": sum(r["volume"] for r in rows)})
    return out


def _slab_layers(s: _Sum, doc: dict, e: dict, item: str, a: float,
                 wallfoot) -> None:
    """A slab with LAYERS (slab layers, D7): each layer, area and volume —
    the finishes ON the core laid between the walls (``wallfoot`` out), the
    core and what is under it the whole slab; and each room's FLOOR on it,
    by room and by the material of its top (the floor finish)."""
    from shapely.geometry import Polygon
    lid = e["level"]
    ls = S.slab_layers(e)
    k = float(e["t"]) / (sum(float(L["t"]) for L in ls) or float(e["t"]))
    core = next(i for i, L in enumerate(ls) if L["role"] == "core")
    try:
        poly = Polygon(e["corners"], e.get("holes") or []).buffer(0)
        floor = poly.difference(wallfoot) if wallfoot is not None else poly
        a_top = floor.area
    except Exception:  # noqa: BLE001 — the slab's own area
        floor, a_top = None, a
    framed = S.slab_frame(e) is not None
    for i, L in enumerate(ls):
        if framed and i == core:         # (its joists: «Floor framing»)
            continue
        la = a_top if i < core else a
        t = float(L["t"]) * k
        name = L.get("name") or tr("Core" if L["role"] == "core"
                                   else "Finish")
        s.add("Slab layers", f"{item} · {name} {_cm(t)}", lid, 0, 0.0,
              la, la * t)
    if core == 0 or floor is None:
        return
    from . import materials as MT
    for room in S.level_rooms(doc, lid):
        try:
            ra = floor.intersection(room["poly"]).area
        except Exception:  # noqa: BLE001
            continue
        if ra < 1e-4:
            continue
        fid = S.floor_id(e["id"], room)
        ref = MT.resolve(doc, "floor", fid, "top") \
            or MT.DEFAULTS["floor"]["top"]
        mat = MT.ref_label(ref)
        s.add("Floors", f"{room['name']} · {mat}", lid, 1, 0.0, ra, 0.0)
        s.add("Floor finishes", mat, lid, 0, 0.0, ra, 0.0)


def roof_area(faces) -> float:
    """A roof's covered area: its faces turned UP (the top of its slopes,
    as built: overhangs, hips, valleys) — not its underside nor its
    edges."""
    def newell(loop):
        nx = ny = nz = 0.0
        n = len(loop)
        for i in range(n):
            p, q = loop[i], loop[(i + 1) % n]
            nx += (p[1] - q[1]) * (p[2] + q[2])
            ny += (p[2] - q[2]) * (p[0] + q[0])
            nz += (p[0] - q[0]) * (p[1] + q[1])
        return nx / 2, ny / 2, nz / 2

    total = 0.0
    for f in faces or []:
        loop = f["loop"] if isinstance(f, dict) else f
        holes = (f.get("holes") or []) if isinstance(f, dict) else []
        if isinstance(f, dict) and f.get("color") not in (None,
                                                          S.ROOF_COLOR):
            continue
        nx, ny, nz = newell(loop)
        a = math.sqrt(nx * nx + ny * ny + nz * nz)
        if a > 1e-9 and nz / a > 0.05:                  # faces turned up
            total += a - sum(math.hypot(*newell(h)) for h in holes)
    return total


def delimiter() -> tuple[str, str]:
    """(field separator, decimal mark) a spreadsheet in the language reads:
    «;» and «,» for Portuguese / German (Excel there), else «,» and «.»."""
    from . import i18n
    return (";", ",") if i18n.current() in ("pt-BR", "de") else (",", ".")


def write(path: str, rows: list, imperial: bool = False) -> int:
    """The rows to ``path`` (UTF-8 with a BOM: Excel reads the accents).
    Returns the rows written."""
    sep, dec = delimiter()
    k = 1 / FT if imperial else 1.0
    u = ("ft", "ft²", "ft³") if imperial else ("m", "m²", "m³")

    def num(v, p):
        if not v:
            return ""
        return f"{v:.{p}f}".replace(".", dec)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.writer(fh, delimiter=sep)
        wr.writerow([tr("Category"), tr("Item"), tr("Level"), tr("Count"),
                     f"{tr('Length')} ({u[0]})", f"{tr('Area')} ({u[1]})",
                     f"{tr('Volume')} ({u[2]})"])
        for r in rows:
            wr.writerow([tr(r["cat"]), r["item"], r["level"],
                         r["n"] or "", num(r["length"] * k, 2),
                         num(r["area"] * k * k, 2),
                         num(r["volume"] * k ** 3, 3)])
    return len(rows)
