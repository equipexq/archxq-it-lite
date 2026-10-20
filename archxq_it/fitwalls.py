"""SLABS AND ROOFS THAT FOLLOW THEIR WALLS (0.13.1 — his project, 2026-10-18:
he pulled Level 4's walls 3 m out and the roof stayed on the old walls).

A slab made «Inside the walls» or a roof made «Over the walls» has as its
outline one of its level's blocks of walls (``structure.inside_walls_all``;
a pitched roof: ``structure.roof_corners`` of it). When that level's walls
change, such a slab / roof is made again over the walls as they are now —
the block that overlaps it most. Nothing is stored to say so: it is read
from the outline itself, so old projects follow too, and a slab or roof
whose corners were moved by hand (its outline no longer the walls') stays
as it is.

Pure data — no Qt; ``ui._commit_all`` runs ``sync`` before storing.
"""
from __future__ import annotations

import json

#: m — the same corner
SAME = 0.02


def _wall_key(w: dict) -> str:
    keep = {k: w.get(k) for k in ("kind", "a", "b", "c", "r", "m", "t",
                                  "align", "side", "cw")}
    return json.dumps(keep, sort_keys=True, default=str)


def _walls_of(doc: dict, lid: str) -> list:
    return [w for w in doc.get("walls") or [] if w.get("level") == lid]


def _sig(doc: dict, lid: str) -> list:
    return sorted(_wall_key(w) for w in _walls_of(doc, lid))


def _same_outline(a, b) -> bool:
    if len(a) != len(b):
        return False
    return all(any(abs(float(p[0]) - float(q[0])) <= SAME
                   and abs(float(p[1]) - float(q[1])) <= SAME for q in b)
               for p in a)


def _outlines(e: dict, walls: list) -> list:
    """The outlines this element would have if made over ``walls``."""
    from . import structure as S
    loops = S.inside_walls_all(walls)
    if e.get("type") == "roof":
        out = []
        for lp in loops:
            try:
                out.append(S.roof_corners(lp, e.get("kind", "flat")))
            except Exception:  # noqa: BLE001
                continue
        return out
    return loops


def _best(e: dict, outlines: list):
    """The outline standing where ``e`` stands (the most overlap)."""
    try:
        from shapely.geometry import Polygon
    except ImportError:
        return None
    src = Polygon(e["corners"])
    if not src.is_valid:
        src = src.buffer(0)
    best, area = None, 0.0
    for c in outlines:
        p = Polygon(c)
        if not p.is_valid:
            p = p.buffer(0)
        a = p.intersection(src).area
        if a > area:
            best, area = c, a
    return best if best is not None and area >= 0.3 * src.area else None


def sync(before: dict, doc: dict) -> tuple[dict, int]:
    """(the document with its wall-made slabs / roofs over the walls as
    they are now, how many followed)."""
    st = doc.get("structure") or []
    targets = [e for e in st if e.get("type") in ("slab", "roof")
               and not e.get("auto") and len(e.get("corners") or []) >= 3]
    if not targets:
        return doc, 0
    old_by_id = {e.get("id"): e for e in before.get("structure") or []}
    changed: dict[str, bool] = {}
    moved = {}
    for e in targets:
        lid = e["level"]
        if lid not in changed:
            changed[lid] = _sig(before, lid) != _sig(doc, lid)
        if not changed[lid]:
            continue
        old = old_by_id.get(e.get("id"))
        # it must have been made over the walls as they WERE (and not just
        # now edited by hand)
        if old is None or not _same_outline(old["corners"], e["corners"]):
            continue
        if not any(_same_outline(e["corners"], c)
                   for c in _outlines(e, _walls_of(before, lid))):
            continue
        now = _best(e, _outlines(e, _walls_of(doc, lid)))
        if now is not None and not _same_outline(now, e["corners"]):
            moved[e["id"]] = now
    if not moved:
        return doc, 0
    out = []
    for e in st:
        if e.get("id") in moved:
            e = dict(e, corners=[list(p) for p in moved[e["id"]]])
            # its holes stay where they were drawn (a stair's opening)
        out.append(e)
    return dict(doc, structure=out), len(moved)
