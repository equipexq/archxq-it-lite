"""The host's own Move / Rotate / Copy on ArchXQ's elements — adopted.

IngeTrazo's Move (M), Ctrl+Move (copy), its arrays (x3, /3) and Rotate (Q)
shift a group's vertices in place, in the same order, and a copy keeps the
group's ``ext`` — ArchXQ's tag. So every element built carries, in its
tag, where three of its vertices were (``ref``); after any host command
the groups whose vertices are no longer there were moved, turned or copied
by the user. Their rigid motion (a turn about Z + a shift) is read from
those three points and applied to the element's RECORD — the record stays
the source of truth: the rebuild puts the element where the user left it,
with its slab openings, materials, stacking, joins (his ask, 2026-10-08:
«never below what IngeTrazo already does»).

The host's Scale (S) works the same way (his rule, 2026-10-08: the basic
tools work EXACTLY as IngeTrazo's): a column, a footing, a beam, a drawn
slab take the sizes their group was stretched to (``reshaped``). What a
record can't hold (stretched askew, tilted, mirrored, a ramp or a stair
stretched — that's its steps: its window) goes back where it was, and
the user is told to use its window. Pure data — no Qt; ui.py hooks it.
"""
from __future__ import annotations

import copy
import math

from . import model

#: the record kinds a host Move / Rotate / Copy is adopted for (walls and
#: openings: next — a wall is joined to its neighbours)
ADOPT = ("column", "beam", "footing", "slab", "roof", "ramp", "stair")
TOL = 0.002                     # m — a vertex «still there»


def _p(v) -> tuple:
    q = v.position
    return (q.x(), q.y(), q.z())


def stamp(group, k: int = 0) -> None:
    """Where three of the group's vertices are now (its first one, the one
    farthest from it in plan, the one farthest in height) — in its tag,
    so a copy carries it too. ``k``: which group of its element it is."""
    from .compat import EXT_KEY
    vs = group.mesh.vertices
    if not vs:
        return
    p0 = _p(vs[0])
    i1 = max(range(len(vs)), key=lambda i: math.hypot(_p(vs[i])[0] - p0[0],
                                                       _p(vs[i])[1] - p0[1]))
    i2 = max(range(len(vs)), key=lambda i: abs(_p(vs[i])[2] - p0[2]))
    ext = dict(group.ext or {})
    rec = dict(ext.get(EXT_KEY) or {})
    rec["ref"] = [[i, *(round(c, 5) for c in _p(vs[i]))]
                  for i in (0, i1, i2)]
    zs = [_p(v)[2] for v in vs]
    rec["zr"] = [round(min(zs), 5), round(max(zs), 5)]   # (Scale: heights)
    rec["k"] = k
    ext[EXT_KEY] = rec
    group.ext = ext


def motion(group):
    """None = where it was built; else ``(theta_deg, (tx, ty), dz)`` — the
    turn about Z (about the origin) and shift that took it from there; or
    "bad" for a motion a record can't hold (scaled, tilted, mirrored)."""
    from .compat import _rec
    ref = _rec(group).get("ref")
    vs = group.mesh.vertices
    if not ref or any(r[0] >= len(vs) for r in ref):
        return None
    was = [tuple(r[1:]) for r in ref]
    now = [_p(vs[r[0]]) for r in ref]
    if all(math.dist(a, b) < TOL for a, b in zip(was, now)):
        return None
    # rigid: every distance kept, and every point rose / sank the same
    for i in range(3):
        for j in range(i + 1, 3):
            if abs(math.dist(was[i], was[j]) - math.dist(now[i], now[j])) \
                    > TOL:
                return "bad"
    dzs = [b[2] - a[2] for a, b in zip(was, now)]
    if max(dzs) - min(dzs) > TOL:
        return "bad"                                    # tilted
    # the turn, from the pair farthest apart in plan
    (a0, a1), (b0, b1) = (was[0], was[1]), (now[0], now[1])
    if math.hypot(a1[0] - a0[0], a1[1] - a0[1]) > 0.01:
        th = math.atan2(b1[1] - b0[1], b1[0] - b0[0]) \
            - math.atan2(a1[1] - a0[1], a1[0] - a0[0])
        # a mirror keeps the distances but flips the turn of the third point
        if _side(was) * _side(now) < -1e-6:
            return "bad"
    else:
        th = 0.0
    c, s = math.cos(th), math.sin(th)
    tx = b0[0] - (c * a0[0] - s * a0[1])
    ty = b0[1] - (s * a0[0] + c * a0[1])
    return (math.degrees(th), (tx, ty), sum(dzs) / 3)


def _same(m1, m2) -> bool:
    return abs(_angle(m1[0] - m2[0])) < 0.01 and \
        math.dist(m1[1], m2[1]) < TOL


def _side(ps) -> float:
    (x0, y0, _), (x1, y1, _), (x2, y2, _) = ps
    return (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)


def _angle(a: float) -> float:
    """−180 < a ≤ 180, rounded."""
    a = (a + 180.0) % 360.0 - 180.0
    return round(180.0 if abs(a + 180.0) < 1e-9 else a, 3)


def moved(rec: dict, m) -> dict:
    """The record taken by the motion ``m`` (see ``motion``) — its points
    turned and shifted, its angle turned. (The height stays: a level's
    elements stay on it.)"""
    th, (tx, ty), _dz = m
    c, s = math.cos(math.radians(th)), math.sin(math.radians(th))

    def pt(p):
        return [round(c * p[0] - s * p[1] + tx, 4),
                round(s * p[0] + c * p[1] + ty, 4)]
    r = copy.deepcopy(rec)
    if "x" in r and "y" in r:
        r["x"], r["y"] = pt((r["x"], r["y"]))
    for key in ("a", "b", "m"):
        if key in r:
            r[key] = pt(r[key])
    if "corners" in r:
        r["corners"] = [pt(p) for p in r["corners"]]
    if "holes" in r:
        r["holes"] = [[pt(p) for p in h] for h in r["holes"]]
    if "angle" in r:
        r["angle"] = _angle(float(r["angle"]) + th)
    return r


# ---- Scale ---------------------------------------------------------------------------
#: the kinds whose sizes the host's Scale can change
RESHAPE = ("column", "footing", "beam", "slab")


def _frame(pts, ang: float):
    """The extents of plan points ``pts`` along the axes turned ``ang``
    radians: (u0, u1, v0, v1)."""
    c, s = math.cos(ang), math.sin(ang)
    us = [x * c + y * s for x, y in pts]
    vs = [-x * s + y * c for x, y in pts]
    return min(us), max(us), min(vs), max(vs)


def _box_ok(pts, ang: float, ext) -> bool:
    """Every plan point on a corner of that box: still a rectangle along
    those axes (a turned column stretched along the world's axes is not)."""
    c, s = math.cos(ang), math.sin(ang)
    u0, u1, v0, v1 = ext
    for x, y in pts:
        u, v = x * c + y * s, -x * s + y * c
        if min(abs(u - u0), abs(u - u1)) > TOL or \
                min(abs(v - v0), abs(v - v1)) > TOL:
            return False
    return True


def _unframe(u: float, v: float, ang: float):
    c, s = math.cos(ang), math.sin(ang)
    return (u * c - v * s, u * s + v * c)


def reshaped(rec: dict, group, doc: dict):
    """The record with the sizes the host's Scale gave its group — the
    same element, wider / taller / longer; None = a shape a record can't
    hold (stretched askew, a square pad made oblong…)."""
    from . import structure as S
    from .compat import _rec
    t = rec.get("type")
    if t not in RESHAPE or rec.get("auto"):
        return None
    pts3 = [_p(v) for v in group.mesh.vertices]
    if not pts3:
        return None
    plan = [(p[0], p[1]) for p in pts3]
    z0n, z1n = min(p[2] for p in pts3), max(p[2] for p in pts3)
    zr = _rec(group).get("zr") or [z0n, z1n]
    lo_moved, hi_moved = abs(z0n - zr[0]) > TOL, abs(z1n - zr[1]) > TOL
    # the vertical factor: the 1 mm kept off the faces grew with it
    fz = (z1n - z0n) / (zr[1] - zr[0]) if zr[1] - zr[0] > 1e-6 else 1.0
    r = copy.deepcopy(rec)
    sh = S.FIT_SHRINK if rec.get("fit") else S.SHRINK

    def size(old: float, was: float, now: float) -> float:
        """The new size: the old one times the stretch (the drawn one is
        ``was`` — a few mm short of the size —, now ``now``)."""
        return round(old * now / was, 4) if was > 1e-6 else old
    if t == "column":
        if rec.get("shape") == "round":
            ext = _frame(plan, 0.0)
            if abs((ext[1] - ext[0]) - (ext[3] - ext[2])) > TOL:
                return None                   # a round column made oval
            r["w"] = size(float(rec["w"]), float(rec["w"]) - 2 * sh,
                          ext[1] - ext[0])
            r["x"] = round((ext[0] + ext[1]) / 2, 4)
            r["y"] = round((ext[2] + ext[3]) / 2, 4)
        else:
            ang = math.radians(float(rec.get("angle", 0.0)))
            ext = _frame(plan, ang)
            if not _box_ok(plan, ang, ext):
                return None
            r["w"] = size(float(rec["w"]), float(rec["w"]) - 2 * sh,
                          ext[1] - ext[0])
            r["d"] = size(float(rec["d"]), float(rec["d"]) - 2 * sh,
                          ext[3] - ext[2])
            # the insertion point follows: the axis lands where it is now
            mid = _unframe((ext[0] + ext[1]) / 2, (ext[2] + ext[3]) / 2, ang)
            cx, cy = S.column_centre(r)
            r["x"] = round(float(r["x"]) + mid[0] - cx, 4)
            r["y"] = round(float(r["y"]) + mid[1] - cy, 4)
        if lo_moved or hi_moved:
            from . import model
            z0 = S.levels_info(doc, model.elevations)[rec["level"]]["z0"]
            if hi_moved:
                r["height"] = round(z1n + S.SHRINK * fz - z0, 4)
            if lo_moved:
                r["base"] = round(z0n - S.SHRINK * fz - z0, 4)
        return r
    if t == "footing":
        if lo_moved or hi_moved:
            r["d"] = size(float(rec["d"]), zr[1] - zr[0], z1n - z0n)
        if rec.get("kind") == "pad":
            ang = math.radians(float(rec.get("angle", 0.0)))
            ext = _frame(plan, ang)
            if not _box_ok(plan, ang, ext) or \
                    abs((ext[1] - ext[0]) - (ext[3] - ext[2])) > TOL:
                return None                   # a pad stays square
            r["w"] = round(ext[1] - ext[0], 4)
            mid = _unframe((ext[0] + ext[1]) / 2, (ext[2] + ext[3]) / 2, ang)
            r["x"], r["y"] = round(mid[0], 4), round(mid[1], 4)
            return r
        if rec.get("m"):
            return r if (lo_moved or hi_moved) else None
        t = "beam"                     # a strip: its width like a beam's
    if t == "beam":
        (ax, ay), (bx, by) = rec["a"], rec["b"]
        ang = math.atan2(by - ay, bx - ax)
        ext = _frame(plan, ang)
        _a0, _a1, v0, v1 = _frame([(ax, ay), (bx, by)], ang)
        width = ext[3] - ext[2]
        old = float(rec["w"]) - (0.0 if rec["type"] == "footing" else 2 * sh)
        if abs(width - old) > TOL:
            r["w"] = size(float(rec["w"]), old, width)
            # the axis moves to the middle of the new width
            shift = (ext[2] + ext[3]) / 2 - v0
            dx, dy = _unframe(0.0, shift, ang)
            r["a"] = [round(ax + dx, 4), round(ay + dy, 4)]
            r["b"] = [round(bx + dx, 4), round(by + dy, 4)]
        if rec["type"] == "beam" and (lo_moved or hi_moved):
            r["h"] = size(float(rec["h"]), zr[1] - zr[0], z1n - z0n)
        return r if r != rec else None
    if t == "slab":
        cs = rec["corners"]
        ox0, ox1 = min(p[0] for p in cs), max(p[0] for p in cs)
        oy0, oy1 = min(p[1] for p in cs), max(p[1] for p in cs)
        nx0, nx1 = min(p[0] for p in plan), max(p[0] for p in plan)
        ny0, ny1 = min(p[1] for p in plan), max(p[1] for p in plan)
        if ox1 - ox0 < 1e-6 or oy1 - oy0 < 1e-6:
            return None
        sx, sy = (nx1 - nx0) / (ox1 - ox0), (ny1 - ny0) / (oy1 - oy0)

        def pt(p):
            return [round(nx0 + (p[0] - ox0) * sx, 4),
                    round(ny0 + (p[1] - oy0) * sy, 4)]
        r["corners"] = [pt(p) for p in cs]
        r["holes"] = [[pt(p) for p in h] for h in rec.get("holes") or []]
        if lo_moved or hi_moved:
            r["t"] = size(float(rec["t"]), zr[1] - zr[0], z1n - z0n)
        return r
    return None


def adopt(doc: dict, groups) -> tuple[dict | None, list[str]]:
    """What the host's tools did to ArchXQ's elements, put into ``doc``:
    (the new document — None when nothing of ours moved —, notes for the
    user). An element moved / turned: its record follows. A copy (a group
    of an element whose original is still in place): a new element, with
    the original's material. A motion a record can't hold: the record
    stays, the rebuild puts it back (noted)."""
    from .compat import _rec, kind_of
    seen: dict = {}
    for g in groups:
        if kind_of(g) not in ADOPT:
            continue
        r = _rec(g)
        if not r.get("id") or not r.get("ref"):
            continue
        seen.setdefault((r["id"], r.get("k", 0)), []).append(g)
    moves: dict = {}            # id → motion of the element itself
    copies: list = []           # (id, motion) — a new element each
    scaled: list = []           # (id, group) — not a rigid motion: Scale?
    for (eid, _k), gs in seen.items():
        ms = [motion(g) for g in gs]
        if not any(ms):
            continue
        stays = None in ms
        for g, m in zip(gs, ms):
            if m is None:
                continue
            if m == "bad":
                scaled.append((eid, g))
            elif not stays:
                stays = True            # the next ones are its copies
                if eid not in moves:
                    moves[eid] = m      # the element itself went there
                elif not _same(moves[eid], m):
                    copies.append((eid, m))
                # (another group of the same element, gone with it: done)
            else:
                copies.append((eid, m))
    # an element of several groups copied once per group: once
    copies = list(dict.fromkeys(
        (i, (round(m[1][0], 3), round(m[1][1], 3), round(m[0], 2)))
        for i, m in copies))
    if not (moves or copies or scaled):
        return None, []
    notes = []
    st = doc.get("structure") or []
    by_id = {e["id"]: e for e in st}
    # the host's Scale: the element's new sizes, read from its group
    resized: dict = {}
    bad = 0
    for eid, g in scaled:
        r = by_id.get(eid)
        r = reshaped(r, g, doc) if r is not None else None
        if r is None:
            bad += 1
        else:
            resized[eid] = r
    auto = [i for i in list(moves) + [i for i, _ in copies]
            if by_id.get(i, {}).get("auto")]
    new_st = []
    for e in st:
        if e["id"] in resized:
            e = resized[e["id"]]
        elif e["id"] in moves and not e.get("auto"):
            e = moved(e, moves[e["id"]])
        new_st.append(e)
    fresh, mats = [], (doc.get("materials") or {}).get("el") or {}
    for eid, key in copies:
        e = by_id.get(eid)
        if e is None or e.get("auto"):
            continue
        m = (key[2], (key[0], key[1]), 0.0)
        r = {k: v for k, v in moved(e, m).items() if k not in ("id", "name")}
        fresh.append((eid, r))
    made = model.new_elements(new_st, [r for _i, r in fresh])
    doc = dict(doc, structure=new_st + made)
    if made and mats:
        el = dict(mats)
        for (eid, _r), n in zip(fresh, made):
            if eid in mats:
                el[n["id"]] = copy.deepcopy(mats[eid])
        doc["materials"] = dict(doc.get("materials") or {}, el=el)
    if auto:
        notes.append("an excavation's slab follows its excavation — it "
                     "stays")
    if resized:
        n = len(resized)
        notes.append(f"{n} element{'s' if n > 1 else ''} resized")
    if bad:
        notes.append("that shape can't be kept on this ArchXQ element "
                     "(stretched askew, tilted, mirrored…) — use its "
                     "window (double-click)")
    n_mv, n_cp = sum(1 for i in moves if not by_id.get(i, {}).get("auto")), \
        len(made)
    if n_mv:
        notes.insert(0, f"{n_mv} element{'s' if n_mv > 1 else ''} moved")
    if n_cp:
        notes.insert(0 if not n_mv else 1,
                     f"{n_cp} cop{'ies' if n_cp > 1 else 'y'} made")
    return doc, notes
