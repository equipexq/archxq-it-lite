# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A layered wall's LAYERS on the drawings, and the wall types' legend
(PLANO_DOCUMENTACAO_ESTILOS_VISTAS.md, phase B).

The host fills every cut alike. Where a layered wall is cut, this lays over
it — as the light frames' symbols do — each layer's own polygon (its fill
taken off, in the sheet's see-through picture), the layers' divisions and a
hatch by what the layer is made of, read from its name.

A plain wall stays as it is. Pure but for shapely: no Qt, no host.
"""
from __future__ import annotations

import math

from . import docstyle as DS
from . import framing as FR
from . import walls as W

#: a layer's class, from words in its name (pt, en, de, es)
WORDS = (
    ("insulation", ("insul", "isol", "dämm", "daemm", "wool", " lã", "foam",
                    "eps", "xps", "pur", "pir", "aisla")),
    ("air", ("air", "cavity", "gap", "câmara", "camara", "luft")),
    ("brick", ("brick", "tijolo", "alven", "masonry", "ziegel", "mauerwerk",
               "ladrillo")),
    ("block", ("block", "bloco", "cmu", "stein ", "bloque")),
    ("concrete", ("concrete", "concreto", "beton", "hormig")),
    ("stone", ("stone", "pedra", "granit", "mármore", "marmore", "marble",
               "naturstein", "piedra")),
    ("wood", ("wood", "madeira", "timber", "holz", "osb", "ply", "compensado",
              "madera")),
    ("plaster", ("plaster", "reboco", "gesso", "drywall", "gypsum", "putz",
                 "stucco", "render", "yeso", "emboço", "emboco", "paint",
                 "pintura", "tile", "azulejo", "cerâm", "ceram", "fliese")),
)

#: per class: (fill, hatch families [(angle °, spacing on paper, mm)])
HATCH = {
    "brick": ("#ffffff", ((45.0, 1.5),)),
    "block": ("#ffffff", ((45.0, 3.0), (135.0, 3.0))),
    "concrete": ("#d6d6d6", ((45.0, 3.0),)),
    "insulation": ("#ffffff", ((45.0, 2.4), (135.0, 2.4))),
    "stone": ("#ececec", ((135.0, 1.2),)),
    "wood": ("#ffffff", ((135.0, 2.0),)),
    "plaster": ("#ffffff", ()),
    "air": ("#ffffff", ()),
    "core": ("#ffffff", ((45.0, 2.5),)),
    "finish": ("#ffffff", ()),
}

#: keys of what this lays on a sheet, not kept on the sheet's record (a wall
#: of hatch lines there would swell the file — ``hostsheet.placed``)
PREFIX = "wl:"


def classify(name: str, role: str = "finish") -> str:
    low = f" {str(name or '').lower()} "
    for cls, words in WORDS:
        if any(w in low for w in words):
            return cls
    return "core" if role == "core" else "finish"


def drawn_at(style: dict, n: int) -> bool:
    """Are a sheet's layers drawn at 1:``n``? (the style's choice; auto:
    from 1:50 up close — further off the hatch would be a smudge)"""
    mode = (style.get("show") or {}).get("wall_layers", "auto")
    if mode == "off":
        return False
    return mode == "on" or n <= FR.SYMBOL_SCALE


def hatch_lines(geom, families) -> list:
    """The hatch inside a shape on paper: [((x, y), (x, y))]. Its phase is
    the page's, so neighbouring pieces line up."""
    from shapely.geometry import LineString
    if geom.is_empty or not families:
        return []
    x0, y0, x1, y1 = geom.bounds
    out = []
    for ang, step in families:
        a = math.radians(ang)
        ux, uy = math.cos(a), math.sin(a)
        nx, ny = -uy, ux
        ds = [c[0] * nx + c[1] * ny for c in ((x0, y0), (x1, y0), (x1, y1),
                                              (x0, y1))]
        ts = [c[0] * ux + c[1] * uy for c in ((x0, y0), (x1, y0), (x1, y1),
                                              (x0, y1))]
        lo, hi = min(ts) - 1.0, max(ts) + 1.0
        for k in range(math.floor(min(ds) / step),
                       math.ceil(max(ds) / step) + 1):
            d = k * step
            ln = LineString([(nx * d + ux * lo, ny * d + uy * lo),
                             (nx * d + ux * hi, ny * d + uy * hi)])
            got = ln.intersection(geom)
            for g in getattr(got, "geoms", [got]):
                if g.geom_type == "LineString" and g.length > 0.05:
                    cs = list(g.coords)
                    out.append((cs[0], cs[-1]))
    return out


def _polys(geom) -> list:
    if geom is None or geom.is_empty:
        return []
    return [g for g in getattr(geom, "geoms", [geom])
            if g.geom_type == "Polygon" and g.area > 1e-6]


def _segments(boundary) -> list:
    out = []
    for g in getattr(boundary, "geoms", [boundary]):
        if g.geom_type in ("LineString", "LinearRing"):
            cs = list(g.coords)
            out += list(zip(cs, cs[1:]))
    return out


def paint(pc, parts: list) -> int:
    """The layers on the sheet. ``parts``: [(wall id, layer index, class,
    shape on paper)]. Each layer's fill, its hatch, the divisions; round
    them all the cut's own pen. Returns the lines laid."""
    from shapely.ops import unary_union
    if not parts:
        return 0
    n_lines = 0
    shapes = [g for *_x, g in parts if not g.is_empty]
    whole = unary_union(shapes).buffer(1e-3, join_style=2)
    edge = whole.boundary
    near = edge.buffer(0.02)
    seen: dict = {}
    for wid, i, cls, geom in parts:
        fill, fams = HATCH.get(cls, HATCH["finish"])
        for poly in _polys(geom):
            k = seen.get((wid, i), 0)
            seen[(wid, i)] = k + 1
            key = f"{PREFIX}{wid}:{i}:{k}"
            pc.items.append({
                "kind": "fill", "key": key + ":b",
                "poly": list(poly.exterior.coords),
                "holes": [list(r.coords) for r in poly.interiors],
                "color": fill, "opacity": 1.0})
            for j, (a, b) in enumerate(hatch_lines(poly, fams)):
                pc.line(f"{key}:h{j}", a, b, "symbol")
                n_lines += 1
            inner = poly.boundary.difference(near)
            for j, (a, b) in enumerate(_segments(inner)):
                pc.line(f"{key}:d{j}", a, b, "symbol")
                n_lines += 1
    for j, (a, b) in enumerate(_segments(edge)):
        pc.line(f"{PREFIX}edge:{j}", a, b, "cut")
        n_lines += 1
    return n_lines


def _layered(walls: list) -> list:
    return [w for w in walls if len(W.layers_of(w)) > 1]


def plan_parts(doc: dict, lid: str, walls: list, openings: list, P,
               z0: float, top_of_level: float, cut: float,
               symbols: bool) -> list:
    """What a plan cut at ``cut`` shows of its layered walls: the
    ``paint`` parts, on paper through ``P``. ``symbols``: the light frames
    draw their own core (their finishes come from here)."""
    from shapely.geometry import Polygon
    from shapely.ops import transform

    from . import structure as S
    mine = _layered(walls)
    if not mine:
        return []
    bands = W.plan_layers(walls)
    out = []
    for w in mine:
        b = z0 + float(w.get("base", 0.0))
        top = top_of_level if w.get("height", "level") == "level" \
            else z0 + float(w["height"])
        if not b <= cut <= max(top, cut if W.top_of(w) else top):
            continue
        ops = [f for f in (S.fitted(o, w, openings, top - z0)
                           for o in openings if o["wall"] == w["id"])
               if f is not None]
        gaps = []
        try:
            G = FR.Geo(w)
            half = float(w["t"]) / 2 + 0.02
            for s0, s1, zs, zt in FR.spans_of(ops, z0, b, top):
                if not zs < cut < zt:
                    continue
                ss = [s0 + (s1 - s0) * k / 8 for k in range(9)]
                ring = [G.P(s, -half) for s in ss] + \
                    [G.P(s, half) for s in reversed(ss)]
                gaps.append(Polygon(ring).buffer(0))
        except Exception:  # noqa: BLE001 — no gaps worked out: the wall whole
            gaps = []
        ls = W.layers_of(w)
        framed = symbols and FR.frame_of(w) is not None
        for i, part in bands.get(w["id"]) or []:
            if i >= len(ls) or (framed and ls[i]["role"] == "core"):
                continue
            g = Polygon(part["outer"], part.get("holes") or [])
            g = g if g.is_valid else g.buffer(0)
            for gp in gaps:
                g = g.difference(gp)
            if g.is_empty:
                continue
            paper = transform(lambda x, y, z=None: P((x, y)), g)
            out.append((w["id"], i, classify(ls[i]["name"], ls[i]["role"]),
                        paper))
    return out


def section_parts(doc: dict, elevations, info: dict, q, nrm, X, Y, right,
                  symbols: bool) -> list:
    """What a vertical cut through ``q`` (normal ``nrm`` in plan) shows of
    the layered walls: a band up each wall per layer it crosses. ``X``, ``Y``:
    along the right vector / height → paper."""
    from shapely.geometry import LineString, Polygon, box

    from . import structure as S
    nl = math.hypot(nrm[0], nrm[1]) or 1.0
    tx, ty = -nrm[1] / nl, nrm[0] / nl
    far = 1e4
    line = LineString([(q[0] - tx * far, q[1] - ty * far),
                       (q[0] + tx * far, q[1] + ty * far)])
    rx, ry = right
    ops_all = doc.get("openings") or []
    out = []
    for lid, li in info.items():
        walls = [w for w in doc.get("walls") or [] if w.get("level") == lid]
        mine = _layered(walls)
        if not mine:
            continue
        z0 = li["z0"]
        bands = W.plan_layers(walls)
        plans = W.plan(walls)
        try:
            drops = S.level_drops(doc, elevations, lid, walls, plans)
        except Exception:  # noqa: BLE001 — from its floor
            drops = {}
        for w in mine:
            ls = W.layers_of(w)
            framed = symbols and FR.frame_of(w) is not None
            b = z0 + float(w.get("base", 0.0)) - drops.get(w["id"], 0.0)
            top = li["under"] if w.get("height", "level") == "level" \
                else z0 + float(w["height"])
            ops = [f for f in (S.fitted(o, w, ops_all, top - z0)
                               for o in ops_all if o["wall"] == w["id"])
                   if f is not None]
            try:
                G = FR.Geo(w)
                spans = FR.spans_of(ops, z0, b, top)
            except Exception:  # noqa: BLE001 — a broken wall: not drawn
                continue
            for i, part in bands.get(w["id"]) or []:
                if i >= len(ls) or (framed and ls[i]["role"] == "core"):
                    continue
                poly = Polygon(part["outer"], part.get("holes") or [])
                poly = poly if poly.is_valid else poly.buffer(0)
                got = line.intersection(poly)
                for seg in getattr(got, "geoms", [got]):
                    if seg.geom_type != "LineString" or seg.length < 1e-3:
                        continue
                    (ax, ay), (cx, cy) = seg.coords[0], seg.coords[-1]
                    mid = ((ax + cx) / 2, (ay + cy) / 2)
                    s = G.S(mid)
                    high = top
                    if W.top_of(w) is not None:
                        high = z0 + W.top_h(w, s)
                    x0, x1 = sorted((X(ax * rx + ay * ry),
                                     X(cx * rx + cy * ry)))
                    if high <= b or x1 - x0 < 1e-3:
                        continue
                    g = box(x0, Y(high), x1, Y(b))
                    for s0, s1, zs, zt in spans:
                        if s0 <= s <= s1:
                            g = g.difference(box(x0 - 1, Y(zt), x1 + 1, Y(zs)))
                    if not g.is_empty:
                        out.append((w["id"], i,
                                    classify(ls[i]["name"], ls[i]["role"]), g))
    return out


# ---- the wall types' legend -----------------------------------------------------------
def _stack(w: dict) -> tuple:
    return tuple((str(L.get("name") or ""), round(float(L["t"]), 3),
                  L.get("role", "finish")) for L in W.layers_of(w))


def types_used(doc: dict, level_ids: list) -> list:
    """The wall types a sheet's levels use, thickest first: [{"name", "t",
    "layers" [(name, t, role)], "plain"}] — when none is layered: [] (one
    fill for all: nothing for a legend to say)."""
    walls = [w for w in doc.get("walls") or [] if w.get("level") in level_ids]
    if not _layered(walls):
        return []
    named = {}
    for ty in doc.get("wall_types") or []:
        try:
            named[_stack(ty)] = str(ty.get("name") or "")
        except (KeyError, TypeError, ValueError):
            continue
    seen: dict = {}
    for w in walls:
        plain = len(W.layers_of(w)) < 2
        k = ("plain", round(float(w["t"]), 3)) if plain else _stack(w)
        if k not in seen:
            st = _stack(w)
            seen[k] = {"name": "" if plain else named.get(st, ""),
                       "t": float(w["t"]), "layers": st, "plain": plain}
    return sorted(seen.values(), key=lambda t: (t["plain"], -t["t"]))


def _cm(t: float) -> str:
    """A wall's or a layer's thickness: «20» (cm), «7 7/8"» in feet / inches."""
    return DS.small(t) if DS.imperial() else f"{round(t * 100, 1):g}"


#: the legend's rows on a sheet: the rest is told as «… +n»
MAX_ROWS = 8
ROW_MM = 10.0
SWATCH = (22.0, 7.0)


def legend(pc, doc: dict, level_ids: list, x: float, y: float,
           width: float) -> float:
    """The wall types at (x, y): a sample of each drawn from its layers,
    its name, its thickness, its layers. Returns the y under it."""
    from shapely.geometry import box
    style = pc.style
    if not (style.get("show") or {}).get("wall_legend", True):
        return y
    types = types_used(doc, level_ids)
    if not types:
        return y
    Wd = DS.words(style)
    pc.text("wtypes:head", x, y, Wd["wall_types"], "heading")
    y += 6.5
    sw, sh = SWATCH
    tx = x + sw + 3.0
    for r, ty in enumerate(types[:MAX_ROWS]):
        key = f"wtypes:{r}"
        total = sum(t for _n, t, _r in ty["layers"]) or 1.0
        if ty["plain"]:
            pc.rect(key + ":s", x, y, x + sw, y + sh, "symbol",
                    fill=style["colors"]["cut_fill"])
        else:
            at = y
            for i, (name, t, role) in enumerate(ty["layers"]):
                h = sh * t / total
                cls = classify(name, role)
                fill, fams = HATCH.get(cls, HATCH["finish"])
                pc.rect(f"{key}:s{i}", x, at, x + sw, at + h, "symbol",
                        fill=fill)
                for j, (a, b) in enumerate(hatch_lines(
                        box(x, at, x + sw, at + h), fams)):
                    pc.line(f"{key}:h{i}:{j}", a, b, "symbol")
                at += h
        name = Wd["simple_wall"] if ty["plain"] else ty["name"] or \
            " + ".join(n for n, _t, _r in ty["layers"] if n)
        tail = "" if DS.imperial() else " cm"
        pc.text(key + ":n", tx, y, f"{name} — {_cm(ty['t'])}{tail}", "table",
                w=width - sw - 3.0)
        if not ty["plain"]:
            pc.text(key + ":l", tx, y + 4.0, " · ".join(
                f"{n or '—'} {_cm(t)}" for n, t, _r in ty["layers"]), "note",
                w=width - sw - 3.0)
        y += ROW_MM
    if len(types) > MAX_ROWS:
        pc.text("wtypes:more", x, y, f"… +{len(types) - MAX_ROWS}", "table")
        y += 4.6
    return y + 3.0
