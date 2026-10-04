"""ArchXQ ROOMS — found from the walls, named by the architect.

A room is a space ENCLOSED by walls: a hole in the union of a level's
joined wall plans (the walls engine closes every corner, T and crossing,
and doors don't cut the plans — so a room behind a door is still closed).
Nothing to draw: they are found again on every change of the walls.

What the architect gives them is kept in ``doc["rooms"]``: {"id",
"level", "x", "y" (a point inside), "name"}. A room found takes the name
of the record whose point lies in it; a record whose room is gone (the
walls moved over its point) is dropped when names are saved.
"""
from __future__ import annotations

from . import walls as W

MIN_AREA = 0.5          # m² — less is a gap between walls, not a room
_cache: dict = {}


def found(walls: list[dict]) -> list[dict]:
    """The rooms the walls enclose: [{"poly": shapely Polygon, "area",
    "perimeter", "at": (x, y) label point}], largest first."""
    key = repr(sorted((w["id"], w.get("a"), w.get("b"), w.get("m"),
                       w.get("c"), w.get("r"), w.get("t"), w.get("align"),
                       w.get("side"), w.get("kind")) for w in walls))
    if key in _cache:
        return _cache[key]
    from shapely.geometry import Polygon
    from shapely.ops import polylabel, unary_union
    polys = []
    for pcs in W.plan(walls).values():
        for pc in pcs:
            p = Polygon(pc["outer"], pc["holes"])
            polys.append(p if p.is_valid else p.buffer(0))
    out = []
    if polys:
        # close the hairline seams between joined pieces
        u = unary_union(polys).buffer(1e-4, join_style=2).buffer(
            -1e-4, join_style=2)
        comps = list(getattr(u, "geoms", [u]))
        filled = [Polygon(g.exterior) for g in comps]
        for g in comps:
            for ring in g.interiors:
                hole = Polygon(ring)
                # less the walls standing loose inside it (a core in a
                # garage) — FILLED: their own rooms are counted on their own
                inner = [f for f in filled if f.area < hole.area - 1e-6
                         and hole.contains(f.representative_point())]
                room = hole.difference(unary_union(inner)) if inner \
                    else hole
                for r in getattr(room, "geoms", [room]):
                    if r.geom_type != "Polygon" or r.area < MIN_AREA:
                        continue
                    try:
                        at = polylabel(r, tolerance=0.05)
                    except Exception:  # noqa: BLE001 — any inside point
                        at = r.representative_point()
                    out.append({"poly": r, "area": r.area,
                                "perimeter": r.exterior.length,
                                "at": (at.x, at.y)})
    out.sort(key=lambda r: -r["area"])
    if len(_cache) > 64:
        _cache.clear()
    _cache[key] = out
    return out


def gross(walls: list[dict]) -> float:
    """The level's gross area: inside the walls' outer faces."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = [Polygon(pc["outer"], pc["holes"]).buffer(0)
             for pcs in W.plan(walls).values() for pc in pcs]
    if not polys:
        return 0.0
    u = unary_union(polys).buffer(1e-4, join_style=2).buffer(
        -1e-4, join_style=2)
    return sum(Polygon(g.exterior).area for g in getattr(u, "geoms", [u]))


def of_level(doc: dict, level_id: str) -> list[dict]:
    """The level's rooms with their names: [{"name", "area", "perimeter",
    "at", "poly", "rec" (the record, or None)}]. Unnamed: «Room N»."""
    from shapely.geometry import Point
    walls = [w for w in doc.get("walls") or [] if w["level"] == level_id]
    recs = [r for r in doc.get("rooms") or [] if r["level"] == level_id]
    out, n = [], 0
    for room in found(walls):
        rec = next((r for r in recs
                    if room["poly"].contains(Point(r["x"], r["y"]))), None)
        if rec is None:
            n += 1
        out.append(dict(room, rec=rec,
                        name=rec["name"] if rec else f"Room {n}"))
    return out


def label(room: dict) -> str:
    return f"{room['name']}\n{room['area']:.2f} m²"
