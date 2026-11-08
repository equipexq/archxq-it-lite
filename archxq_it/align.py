# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""ALIGN, as Revit's (his ask, 0.15.0 B1/B2 — 2026-10-20): click a
REFERENCE (an edge in plan: a wall's face, a column's side, a beam's or a
slab's edge), then an EDGE of the element to line up — the element moves
across, square to the reference, until that edge lies on it. Pure here (no
Qt): ``walledit.AlignTool`` clicks it.

The edges are the elements' outlines in plan on one level: walls (joined),
columns, beams, footings, slabs. A wall moved this way takes the walls
joined to it along (``wallmove.reshape``), as a wall dragged does.
"""
from __future__ import annotations

import math

from . import walls as W

PARALLEL = math.radians(1.5)     # off parallel, still lined up


def edges(doc: dict, level_id: str) -> list:
    """Every outline edge in plan on the level: [(p, q, kind, id)]."""
    from . import structure as S
    out = []

    def loop_edges(loop, kind, eid):
        n = len(loop)
        for k in range(n):
            p, q = tuple(loop[k]), tuple(loop[(k + 1) % n])
            if math.dist(p, q) > 0.01:
                out.append((p, q, kind, eid))

    walls = [w for w in doc.get("walls") or [] if w["level"] == level_id]
    for wid, pcs in W.plan(walls).items():
        for pc in pcs:
            loop_edges(pc["outer"], "wall", wid)
    els = [e for e in doc.get("structure") or [] if e.get("level") == level_id]
    for e in els:
        try:
            if e["type"] == "column":
                loop_edges(S.column_outline(e, 0.0), "column", e["id"])
            elif e["type"] in ("beam", "footing") and "a" in e:
                for pc in W.plan([S.as_wall(e, "w", shrink=0.0)]).get(
                        e["id"], ()):
                    loop_edges(pc["outer"], e["type"], e["id"])
            elif e["type"] == "slab" and e.get("corners"):
                loop_edges(e["corners"], "slab", e["id"])
        except Exception:  # noqa: BLE001 — an element that can't say: none
            continue
    return out


def seg_dist(p, a, b) -> float:
    """Distance from p to the segment a–b."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return math.dist(p, a)
    f = min(max(((p[0] - ax) * dx + (p[1] - ay) * dy) / L2, 0.0), 1.0)
    return math.dist(p, (ax + dx * f, ay + dy * f))


def shift(ref, edge):
    """The plan vector that puts ``edge`` (p, q) on the line of ``ref``
    (p, q) — square to it; or a str: why not (not parallel)."""
    (a, b), (p, q) = ref[:2], edge[:2]
    ux, uy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(ux, uy)
    vx, vy = q[0] - p[0], q[1] - p[1]
    M = math.hypot(vx, vy)
    if L < 1e-9 or M < 1e-9:
        return "That edge is too short"
    ux, uy, vx, vy = ux / L, uy / L, vx / M, vy / M
    if abs(ux * vy - uy * vx) > math.sin(PARALLEL):
        return "Not parallel to the reference — pick an edge that runs " \
               "along it"
    nx, ny = -uy, ux
    mid = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
    d = (mid[0] - a[0]) * nx + (mid[1] - a[1]) * ny
    return (-d * nx, -d * ny)


def moved(doc: dict, kind: str, eid: str, d) -> dict:
    """``doc`` with the element moved by the plan vector ``d``."""
    import copy
    from . import edits
    doc = copy.deepcopy(doc)
    if kind == "wall":
        from . import wallmove
        w = next((x for x in doc["walls"] if x["id"] == eid), None)
        if w is None:
            return doc
        new = wallmove.shifted(w, d)
        doc, _notes = wallmove.reshape(doc, {eid: new})
        doc["walls"] = [new if x["id"] == eid else x for x in doc["walls"]]
        return doc
    doc["structure"] = [edits.moved(e, (0.0, (d[0], d[1]), 0.0))
                        if e["id"] == eid else e for e in doc["structure"]]
    return doc
