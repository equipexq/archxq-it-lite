# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
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


def N_(text: str) -> str:
    """A text to translate where it is shown (i18n_extract reads it)."""
    return text


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
    if w.get("profile"):
        # its SHAPE (F2) cut there too: each half its part (or, a plain
        # rectangle left, a plain wall of that height)
        from . import wallshape as WS
        shp = WS.profile_of(w)
        shp = WS.stretched(shp, L) if shp is not None else None
        if shp is not None:
            p1, p2, why = WS.split_at(shp, s)
            if why:
                return why
            base = float(w.get("base", 0.0))
            for half, part in ((first, p1), (second, p2)):
                if isinstance(part, dict):
                    half["profile"] = part
                    half["height"] = round(base + WS.peak(part), 4)
                else:
                    half.pop("profile", None)
                    half["height"] = round(base + float(part), 4)
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


# ---- Join (PLANO_CONTORNO_JUNTAS C2a, idea #11.2 — 12/11/2026) ------------------------
#: what may differ between two walls joined: who they are and where
JOIN_FREE = frozenset({"id", "name", "a", "b", "m"})
#: a key that differs → the reason, in his words
JOIN_WHY = (({"t"}, "thickness"), ({"layers", "type"}, "layers"),
            ({"height", "base", "top"}, "height"),
            ({"align", "side"}, "alignment"))
JOIN_TOL = 1e-3          # m: two ends this close are one point; off line


def _reversed(w: dict) -> dict:
    """The same wall drawn the other way (its body, its faces kept)."""
    return dict(w, a=list(w["b"]), b=list(w["a"]),
                side=-int(w.get("side", 1) or 1))


def join(walls: list, openings: list, aid: str, bid: str,
         looks: dict | None = None) -> tuple:
    """(walls, openings, id of the wall made) with walls ``aid`` and ``bid``
    made ONE — the Split's inverse — or a str: why not. They must be
    straight, in line, touching end to end, and the same in all but where
    they are (thickness, layers, height, alignment…: never guessed). The
    first keeps its id and name; the doors and windows of both go on it,
    each at the same place. ``looks``: id → what each wears painted
    (doc["materials"]["el"]) — not the same: not joined."""
    w1 = next((x for x in walls if x["id"] == aid), None)
    w2 = next((x for x in walls if x["id"] == bid), None)
    if w1 is None or w2 is None or aid == bid:
        return "Pick two walls"
    if not (_straight(w1) and _straight(w2)):
        return "Only straight walls can be joined"
    if w1.get("level") != w2.get("level"):
        return "They are on different levels"
    L1, L2 = math.dist(w1["a"], w1["b"]), math.dist(w2["a"], w2["b"])
    if L1 < 1e-9 or L2 < 1e-9:
        return "Only straight walls can be joined"
    u1 = ((w1["b"][0] - w1["a"][0]) / L1, (w1["b"][1] - w1["a"][1]) / L1)
    u2 = ((w2["b"][0] - w2["a"][0]) / L2, (w2["b"][1] - w2["a"][1]) / L2)
    if abs(u1[0] * u2[1] - u1[1] * u2[0]) > 1e-4:
        return "They are not in line"
    ops1 = [o for o in openings if o.get("wall") == aid]
    ops2 = [o for o in openings if o.get("wall") == bid]
    if u1[0] * u2[0] + u1[1] * u2[1] < 0:     # drawn opposite ways
        if ops2 and ops1:
            return ("They were drawn opposite ways and both have doors or "
                    "windows — their sides would swap")
        if ops2:                               # turn the one without any
            w1, w2, ops1, ops2, L1, L2 = w2, w1, ops2, ops1, L2, L1
            aid, bid = w1["id"], w2["id"]
        w2 = _reversed(w2)
    # in line: the second's drawn line on the first's (and so the bodies)
    a1 = w1["a"]
    for p in (w2["a"], w2["b"]):
        off = abs((p[0] - a1[0]) * -u1[1] + (p[1] - a1[1]) * u1[0])
        if off > JOIN_TOL:
            return "They are not in line"
    if math.dist(w1["b"], w2["a"]) <= JOIN_TOL:
        first, second, f_ops, s_ops = w1, w2, ops1, ops2
        La = L1
    elif math.dist(w2["b"], w1["a"]) <= JOIN_TOL:
        first, second, f_ops, s_ops = w2, w1, ops2, ops1
        La = L2
    else:
        return "They don't touch end to end"
    diff = {k for k in (set(w1) | set(w2)) - JOIN_FREE
            if w1.get(k) != w2.get(k)}
    if (w1.get("align", "centre") == "centre" and not w1.get("layers")
            and not w2.get("layers")):
        diff.discard("side")           # (a plain centred wall: no side)
    if diff:
        for keys, word in JOIN_WHY:
            if diff & keys:
                return f"Not the same {word} — only like walls are joined"
        return ("Not the same wall (" + ", ".join(sorted(diff)) +
                ") — only like walls are joined")
    if (looks or {}).get(aid) != (looks or {}).get(bid):
        return "Not the same material — only like walls are joined"
    if W.top_of(w1) is not None:
        return ("A sloped or gable top would change along the joined wall "
                "— not joined")
    if w1.get("profile") or w2.get("profile"):
        return ("A shaped wall would change along the joined wall — not "
                "joined")
    keep = w1
    new = dict(keep, a=list(first["a"]), b=list(second["b"]))
    if "m" in new:
        new.pop("m")
    why = W.why_not(new)
    if why:
        return why
    out_w = []
    for x in walls:
        if x["id"] == keep["id"]:
            out_w.append(new)
        elif x["id"] in (aid, bid):
            continue
        else:
            out_w.append(x)
    moved = {}
    for o in s_ops:            # past the first: as far on, from its start
        moved[o["id"]] = dict(o, wall=new["id"],
                              pos=round(La + float(o["pos"]), 4))
    for o in f_ops:            # on the first: from the same start
        moved[o["id"]] = dict(o, wall=new["id"])
    out_o = [moved.get(o["id"], o) for o in openings]
    return out_w, out_o, new["id"]


# ---- Round the corner (PLANO_CURVAS_E_FORMAS F2b, 13/11/2026) -------------------------
#: an L this near straight (or folded back on itself) has no corner to round
ROUND_MIN_TURN = math.radians(5.0)
#: what may differ between the two walls of the corner (their sides: by
#: where their inside IS — ``_inside``)
ROUND_FREE = JOIN_FREE | {"side"}


def _inside(w: dict, into_corner: bool) -> int:
    """Where a wall's inside is, looking along the run wall 1 → corner →
    wall 2: +1 on the left, −1 on the right (``side`` is along a → b)."""
    side = -1 if int(w.get("side", 1) or 1) < 0 else 1
    return side if into_corner else -side


def corner(walls: list, aid: str, bid: str):
    """The L two walls make — {"w1", "w2", "end1", "end2", "C", "u1",
    "u2", "phi", "r_max"} (``u``: from the corner along each wall; ``phi``:
    the angle between them; ``r_max``: the biggest radius, on the line
    drawn, that leaves both a wall) — or a str: why not."""
    w1 = next((x for x in walls if x["id"] == aid), None)
    w2 = next((x for x in walls if x["id"] == bid), None)
    if w1 is None or w2 is None or aid == bid:
        return "Pick two walls"
    if not (_straight(w1) and _straight(w2)):
        return N_("Only two straight walls make a corner to round")
    if w1.get("level") != w2.get("level"):
        return "They are on different levels"
    ends = [(e1, e2) for e1 in ("a", "b") for e2 in ("a", "b")
            if math.dist(w1[e1], w2[e2]) <= W.JOIN_TOL]
    if len(ends) != 1:
        return N_("They don't meet at a corner")
    e1, e2 = ends[0]
    C = tuple(w1[e1])
    for x in walls:                  # a third wall at the corner: a T, a Y
        if x["id"] in (aid, bid) or x.get("level") != w1.get("level"):
            continue
        if any(k in x and math.dist(x[k], C) <= W.JOIN_TOL
               for k in ("a", "b")):
            return f"«{x.get('name', 'A wall')}» meets them there too — " \
                   "only a corner of two walls is rounded"
    f1, f2 = w1["b" if e1 == "a" else "a"], w2["b" if e2 == "a" else "a"]
    L1, L2 = math.dist(C, f1), math.dist(C, f2)
    if L1 < 1e-6 or L2 < 1e-6:
        return N_("Only two straight walls make a corner to round")
    u1 = ((f1[0] - C[0]) / L1, (f1[1] - C[1]) / L1)
    u2 = ((f2[0] - C[0]) / L2, (f2[1] - C[1]) / L2)
    cos_ = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
    phi = math.acos(cos_)
    if phi > math.pi - ROUND_MIN_TURN:
        return N_("They are in line — there is no corner to round")
    if phi < ROUND_MIN_TURN:
        return N_("They fold back on each other — no corner to round")
    r_max = (min(L1, L2) - MIN_PART) * math.tan(phi / 2)
    if r_max < 0.01:
        return N_("Too short to round")
    return {"w1": w1, "w2": w2, "end1": e1, "end2": e2, "C": C, "u1": u1,
            "u2": u2, "phi": phi, "L1": L1, "L2": L2,
            "r_max": math.floor(r_max * 1000 + 1e-6) / 1000}


def round_corner(walls: list, openings: list, aid: str, bid: str, r: float,
                 looks: dict | None = None, names=None):
    """(walls, openings, the arc wall made) with the L of walls ``aid`` and
    ``bid`` rounded: each shortened to where an ARC of radius ``r`` (on
    the line drawn) leaves it, tangent to both, and that arc a wall like
    them — or a str: why not. Never guessed: the two must be alike
    (thickness, layers, height, alignment, material, their inside on the
    same side); no door or window may stand where the arc goes (their
    places kept, measured from the wall's start)."""
    cn = corner(walls, aid, bid)
    if isinstance(cn, str):
        return cn
    w1, w2, e1, e2 = cn["w1"], cn["w2"], cn["end1"], cn["end2"]
    if W.top_of(w1) is not None or W.top_of(w2) is not None:
        return N_("A sloped or gable top can't go round the corner")
    if w1.get("profile") or w2.get("profile"):
        return N_("A wall with its own shape can't go round the corner")
    if w1.get("gw") or w2.get("gw"):
        return N_("A grid wall's corner is not rounded")
    diff = {k for k in (set(w1) | set(w2)) - ROUND_FREE
            if w1.get(k) != w2.get(k)}
    plain = (w1.get("align", "centre") == "centre" and not w1.get("layers")
             and not w2.get("layers"))
    # (where its inside is — along the run, wall 1 → corner → wall 2)
    in1 = _inside(w1, e1 == "b")
    in2 = _inside(w2, e2 == "a")
    if in1 != in2 and not plain:
        diff.add("side")
    if diff:
        for keys, word in JOIN_WHY:
            if diff & keys:
                return f"Not the same {word} — only a corner of like walls " \
                       "is rounded"
        return ("Not the same wall (" + ", ".join(sorted(diff)) +
                ") — only a corner of like walls is rounded")
    if (looks or {}).get(aid) != (looks or {}).get(bid):
        return "Not the same material — only a corner of like walls is " \
               "rounded"
    try:
        r = float(r)
    except (TypeError, ValueError):
        return N_("Give the radius")
    if r < 0.01:
        return N_("Give the radius")
    if r > cn["r_max"] + 1e-9:
        return f"At most {cn['r_max']:.2f} m for these walls"
    phi, C, u1, u2 = cn["phi"], cn["C"], cn["u1"], cn["u2"]
    tl = r / math.tan(phi / 2)              # from the corner to each tangent
    T1 = [round(C[0] + u1[0] * tl, 4), round(C[1] + u1[1] * tl, 4)]
    T2 = [round(C[0] + u2[0] * tl, 4), round(C[1] + u2[1] * tl, 4)]
    bx, by = u1[0] + u2[0], u1[1] + u2[1]
    bl = math.hypot(bx, by)
    bx, by = bx / bl, by / bl               # the bisector, into the L
    d = r / math.sin(phi / 2)               # corner → the arc's centre
    O = (C[0] + bx * d, C[1] + by * d)
    M = [round(O[0] - bx * r, 4), round(O[1] - by * r, 4)]

    def short(w, end, T, L):
        """The wall with its corner end at T; its openings, or why not."""
        new = dict(w, **{end: T})
        mine = []
        for o in openings:
            if o.get("wall") != w["id"]:
                continue
            pos, half = float(o["pos"]), float(o["w"]) / 2
            if end == "a":                  # its start moves: from there on
                pos -= tl
                if pos - half < -1e-6:
                    return None, (f"«{o.get('name', 'An opening')}» is where "
                                  "the curve goes — move it first, or a "
                                  "smaller radius")
            elif pos + half > L - tl + 1e-6:
                return None, (f"«{o.get('name', 'An opening')}» is where "
                              "the curve goes — move it first, or a smaller "
                              "radius")
            mine.append(dict(o, pos=round(pos, 4)))
        return (new, mine), None
    got1, why = short(w1, e1, T1, cn["L1"])
    if why:
        return why
    got2, why = short(w2, e2, T2, cn["L2"])
    if why:
        return why
    used = set(names or ()) | {x["name"] for x in walls}
    k = 1
    while f"Wall {k}" in used:
        k += 1
    arc = {kk: v for kk, v in w1.items() if kk not in ("m", "profile", "top")}
    arc.update(kind="arc", a=T1, b=T2, m=M, id=uuid.uuid4().hex[:8],
               name=f"Wall {k}", side=in1)
    for x in (got1[0], got2[0], arc):
        why = W.why_not(x)
        if why:
            return why if x is not arc else (
                f"Too tight a curve for walls this thick — {why}")
    out_w = []
    for x in walls:
        if x["id"] == aid:
            out_w.append(got1[0])
        elif x["id"] == bid:
            out_w.append(got2[0])
        else:
            out_w.append(x)
    out_w.append(arc)
    moved = {o["id"]: o for o in got1[1] + got2[1]}
    out_o = [moved.get(o.get("id"), o) for o in openings]
    return out_w, out_o, arc["id"]
