"""Walls › Edit walls › Split / Trim / Extend (0.15.0, PLANO_0150.md B1) —
the operations, pure (no Qt, no IngeTrazo): ``walledit`` clicks them.

SPLIT: a straight wall cut in two at a point on it; its doors and windows
go with the half they stand in (their place measured from that half's
start). Never inside an opening.

TRIM / EXTEND: a straight wall's end taken on to ANOTHER wall's line drawn
— past it (trim) or short of it (extend); the joins are made again by
themselves.
"""
from __future__ import annotations

import math
import uuid

from . import walls as W

MIN_PART = 0.05          # m: a half shorter than this is no wall


def _straight(w: dict) -> bool:
    return w.get("kind", "line") == "line" and "a" in w and "b" in w


def along(w: dict, p) -> float:
    """How far along a straight wall's drawn line (from a) point p lies."""
    a, b = w["a"], w["b"]
    L = math.dist(a, b)
    if L < 1e-9:
        return 0.0
    return ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / L


def nearest_wall(walls: list, p, tol: float):
    """The straight wall whose body p is on (its drawn line within half
    its thickness + ``tol``): (wall, distance along) or None."""
    best = None
    for w in walls:
        if not _straight(w):
            continue
        L = math.dist(w["a"], w["b"])
        s = along(w, p)
        if not -tol <= s <= L + tol:
            continue
        a, b = w["a"], w["b"]
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        off = abs((p[0] - a[0]) * -uy + (p[1] - a[1]) * ux)
        # (its body: the drawn line moved by its alignment)
        c = W.centre(w)
        off = min(off, abs(c.project(tuple(p))[1]))
        if off <= float(w["t"]) / 2 + tol and (best is None or off < best[0]):
            best = (off, w, min(max(s, 0.0), L))
    return (best[1], best[2]) if best else None


def split(walls: list, openings: list, wid: str, s: float,
          names=None) -> tuple:
    """(walls, openings) with wall ``wid`` cut at ``s`` along it — or a
    str: why not. The second half is a new wall (its own id, the next
    «Wall N» name); the openings past the cut go with it."""
    w = next((x for x in walls if x["id"] == wid), None)
    if w is None or not _straight(w):
        return "Only a straight wall can be split"
    L = math.dist(w["a"], w["b"])
    if s < MIN_PART or s > L - MIN_PART:
        return "Too near its end — click further along it"
    mine = [o for o in openings if o.get("wall") == wid]
    for o in mine:
        if abs(float(o["pos"]) - s) < float(o["w"]) / 2 + 0.01:
            return f"Not through «{o.get('name', 'an opening')}» — click " \
                   "beside it"
    a, b = w["a"], w["b"]
    f = s / L
    p = [round(a[0] + (b[0] - a[0]) * f, 4), round(a[1] + (b[1] - a[1]) * f, 4)]
    used = set(names or ()) | {x["name"] for x in walls}
    k = 1
    while f"Wall {k}" in used:
        k += 1
    first = dict(w, b=p)
    second = dict(w, a=p, id=uuid.uuid4().hex[:8], name=f"Wall {k}")
    out_w = []
    for x in walls:
        if x["id"] == wid:
            out_w += [first, second]
        else:
            out_w.append(x)
    out_o = []
    for o in openings:
        if o.get("wall") == wid and float(o["pos"]) > s:
            o = dict(o, wall=second["id"], pos=round(float(o["pos"]) - s, 4))
        out_o.append(o)
    return out_w, out_o


def trim_extend(walls: list, wid: str, end: str, target: str):
    """walls with wall ``wid``'s end ``end`` ("a" | "b") on ``target``'s
    line drawn — or a str: why not."""
    w = next((x for x in walls if x["id"] == wid), None)
    t = next((x for x in walls if x["id"] == target), None)
    if w is None or t is None or not (_straight(w) and _straight(t)):
        return "Straight walls only"
    if wid == target:
        return "Pick ANOTHER wall to reach"
    a, b = w["a"], w["b"]
    p, r = t["a"], t["b"]
    d1 = (b[0] - a[0], b[1] - a[1])
    d2 = (r[0] - p[0], r[1] - p[1])
    cr = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(cr) < 1e-9:
        return "They run side by side — they never meet"
    u = ((p[0] - a[0]) * d2[1] - (p[1] - a[1]) * d2[0]) / cr
    x = [round(a[0] + d1[0] * u, 4), round(a[1] + d1[1] * u, 4)]
    new = dict(w, **{end: x})
    if math.dist(new["a"], new["b"]) < MIN_PART:
        return "The wall would shrink to nothing"
    # the end must stay on the same side: never turn the wall round
    old_dir = (b[0] - a[0], b[1] - a[1])
    new_dir = (new["b"][0] - new["a"][0], new["b"][1] - new["a"][1])
    if old_dir[0] * new_dir[0] + old_dir[1] * new_dir[1] <= 0:
        return "That wall is behind its other end — pick the end nearer it"
    why = W.why_not(new)
    if why:
        return why
    return [new if x["id"] == wid else x for x in walls]
