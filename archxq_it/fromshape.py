# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""«Wall from shape» (PLANO_CURVAS_E_FORMAS.md, F3b — promised to a customer
on 2026-11-13): a solid made in IngeTrazo — above all the «Difference» its
Subtract leaves of a wall — read back as an ArchXQ WALL with a shape (F2,
wallshape.py), its holes its openings.

What it takes: a PRISM through a constant thickness — every point of it on
one of two parallel upright planes. That is what a Subtract through a
straight wall leaves. Anything else is said why, never guessed.

Two ways in:
- the wall it was is KNOWN (the Subtract kept its record on the result —
  ui stamps it): its line, thickness, alignment, layers, level stay; its
  ends joined as before (a mitre: the shape is read where both faces have
  it, and its end slice runs on to the line's ends — the rule of F2); its
  doors and windows whose holes are still there come back as they were;
- nothing known: a plain wall on the centre plane, its level by its foot.

The new holes become Openings (voids): a rectangle, or one of the shapes
of shapes.py when every point of the hole lies on it (1 mm) — a hole of
another shape is said why.

Pure: math, shapely and the pure modules (outline, curved, wallshape,
shapes, walls). Faces come in as rings of world points (x, y, z), the
first ring the outline, the others its holes."""
from __future__ import annotations

import math

from . import outline as OL
from . import shapes as SH
from . import wallshape as WS

TOL = 1e-3              # m: a point this close to a plane / a line is on it
NDOT = 1e-4             # how far off a face's normal may stand (sin)
DOOR_GAP = 0.03         # m: a hole's bottom this near the floor is a door's

WHY_EMPTY = "Not a solid — nothing to read"
WHY_UPRIGHT = "Not upright — a wall's faces stand straight up"
WHY_PRISM = ("Not the same through its thickness — only a shape cut "
             "straight through a straight wall")
WHY_TWO = "It's in pieces — one wall at a time"
WHY_FOOT_CUT = ("Its foot isn't whole — a wall stands on its whole length "
                "(cut a door with an Opening)")
WHY_HOLE = ("A hole of a shape openings don't have — an Opening's shapes: "
            "rectangle, arches, round, oval, gable, trapezoid, triangle")
WHY_THIN = "Thinner than 2 cm — not a wall"
WHY_JOINED = ("That end is joined to another wall — keep it whole up to "
              "one height there")


# ---- the faces ----------------------------------------------------------------------------
def face_rings(face) -> list:
    """A host face's closed outlines: the outer one first, then its holes
    (as along.face_rings — here, so the Lite has it: along is Pro)."""
    def xyz(p):
        return getattr(p, "position", p).toTuple()
    return [[xyz(p) for p in face.vertices]] +         [[xyz(p) for p in h] for h in getattr(face, "holes", None) or ()]


def _newell(ring) -> tuple:
    nx = ny = nz = 0.0
    k = len(ring)
    for i in range(k):
        a, b = ring[i], ring[(i + 1) % k]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return (nx / 2, ny / 2, nz / 2)


def _unit(v) -> tuple:
    L = math.sqrt(sum(c * c for c in v))
    return tuple(c / L for c in v) if L > 1e-15 else (0.0, 0.0, 0.0)


def face_area(rings) -> float:
    """A face's area, its holes taken off."""
    out = _newell(rings[0])
    n = _unit(out)
    a = abs(sum(out[i] * n[i] for i in range(3)))
    for h in rings[1:]:
        a -= abs(sum(c * n[i] for i, c in enumerate(_newell(h))))
    return a


def volume(faces) -> float:
    """A closed mesh's volume (outward faces): the divergence sum — each
    hole's ring counted against its face's direction."""
    v = 0.0
    for rings in faces:
        A = _newell(rings[0])
        n = _unit(A)
        v += sum(A[i] * rings[0][0][i] for i in range(3)) / 3
        for h in rings[1:]:
            H = _newell(h)
            sgn = 1.0 if sum(H[i] * n[i] for i in range(3)) > 0 else -1.0
            v -= sgn * sum(H[i] * h[0][i] for i in range(3)) / 3
    return abs(v)


# ---- the prism ----------------------------------------------------------------------------
def prism(faces) -> tuple:
    """(planes, why): the two parallel upright planes every point is on —
    {"n": (nx, ny) the biggest face's outward normal, "d0", "d1" (along
    n, d0 < d1), "t"}."""
    faces = [f for f in faces if f and len(f[0]) >= 3]
    if len(faces) < 4:
        return None, WHY_EMPTY
    big = max(faces, key=face_area)
    n3 = _unit(_newell(big[0]))
    if abs(n3[2]) > NDOT:
        return None, WHY_UPRIGHT
    n = _unit((n3[0], n3[1], 0.0))[:2]
    ds = [p[0] * n[0] + p[1] * n[1] for f in faces for r in f for p in r]
    d0, d1 = min(ds), max(ds)
    if any(min(abs(d - d0), abs(d - d1)) > TOL for d in ds):
        return None, WHY_PRISM
    if d1 - d0 < 0.02:
        return None, WHY_THIN
    return {"n": n, "d0": d0, "d1": d1, "t": d1 - d0}, None


def _sides(faces, pl, frame) -> tuple:
    """(front, back): the shapely regions in (s, z) of the faces on each
    plane — s along ``frame``'s u from its origin."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    n, (ox, oy), (ux, uy) = pl["n"], frame["o"], frame["u"]
    on = ([], [])
    for f in faces:
        fn = _unit(_newell(f[0]))
        if abs(abs(fn[0] * n[0] + fn[1] * n[1]) - 1.0) > NDOT:
            continue
        d = f[0][0][0] * n[0] + f[0][0][1] * n[1]
        side = 0 if abs(d - pl["d0"]) <= TOL else 1

        def sz(r):
            return [((p[0] - ox) * ux + (p[1] - oy) * uy, p[2]) for p in r]
        try:
            P = Polygon(sz(f[0]), [sz(h) for h in f[1:]]).buffer(0)
        except (ValueError, TypeError):
            continue
        if not P.is_empty:
            on[side].append(P)
    return unary_union(on[0]), unary_union(on[1])


def _r4(x: float) -> float:
    return round(float(x), 4) + 0.0


# ---- read it ----------------------------------------------------------------------------
def read(faces, wall: dict | None = None, z_level: float | None = None,
         old_ops=()) -> tuple:
    """(got, why) — the wall a solid makes.

    ``wall``: the record of the wall it was (the Subtract kept it), with
    ``z_level`` its level's floor; None: a plain wall on its centre plane.
    ``old_ops``: that wall's doors / windows / openings — the ones whose
    hole is still there come back.

    got = {"wall": the wall's fields (a, b, t, align, side, base, height,
    profile or none), "openings": [records, no id / wall yet for the new
    ones], "kept": n of the old ones back, "known": bool, "volume": the
    solid's, "z_foot": its foot}."""
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union
    from . import walls as W
    pl, why = prism(faces)
    if why:
        return None, why
    n = pl["n"]
    known = False
    if wall is not None and z_level is not None and wall.get("kind",
                                                               "line") == "line":
        seg = W.drawn(wall)
        a, b = tuple(wall["a"]), tuple(wall["b"])
        L = seg.L
        u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L) if L > 1e-9 else None
        if u is not None and abs(abs(u[0] * n[1] - u[1] * n[0]) - 1.0) < NDOT:
            # its faces where the record has them (moved since: not it)
            left = (-u[1], u[0])
            c = W.centre(wall)
            cd = (c.p0[0] - a[0]) * left[0] + (c.p0[1] - a[1]) * left[1]
            sg = 1.0 if left[0] * n[0] + left[1] * n[1] > 0 else -1.0
            e0 = sg * (pl["d0"] - (a[0] * n[0] + a[1] * n[1]))
            e1 = sg * (pl["d1"] - (a[0] * n[0] + a[1] * n[1]))
            lo, hi = min(e0, e1), max(e0, e1)
            t = float(wall["t"])
            if abs(lo - (cd - t / 2)) <= TOL and abs(hi - (cd + t / 2)) <= TOL:
                known = True
    vol = volume(faces)
    if known:
        frame = {"o": a, "u": u}
        F, B = _sides(faces, pl, frame)
        region = F.intersection(B).buffer(0)
        region = region.intersection(box(0.0, -1e3, L, 1e3))
        lift = W.opening_lift(wall)
        z_foot = z_level + float(wall.get("base", 0.0) or 0.0)
        z_ref = z_level + lift
    else:
        ux, uy = n[1], -n[0]                    # its left normal is n
        frame = {"o": (0.0, 0.0), "u": (ux, uy)}
        F, B = _sides(faces, pl, frame)
        if F.symmetric_difference(B).area > max(F.length, 1.0) * TOL:
            return None, WHY_PRISM              # its ends: not square
        region = F.intersection(B).buffer(0)
    if region.is_empty:
        return None, WHY_EMPTY
    if region.geom_type != "Polygon":
        parts = [p for p in getattr(region, "geoms", []) if p.area > 1e-6]
        if len(parts) != 1:
            return None, WHY_TWO
        region = parts[0]
    s_min, zb, s_max, z_top = region.bounds
    if not known:
        # a wall of its own: its line on its centre plane, s from its
        # left end, its foot its lowest point
        L = s_max - s_min
        from shapely import affinity
        region = affinity.translate(region, -s_min, 0.0)
        cdist = (pl["d0"] + pl["d1"]) / 2
        a = (frame["u"][0] * s_min + n[0] * cdist,
             frame["u"][1] * s_min + n[1] * cdist)
        b = (a[0] + frame["u"][0] * L, a[1] + frame["u"][1] * L)
        z_foot = zb
        z_ref = None                             # (the caller's level)
        s_min, s_max = 0.0, L
    elif zb > z_foot + TOL:
        return None, WHY_FOOT_CUT
    # the ends: its slice there run on to the line's ends (a mitre, a stem
    # cut on another wall's face: built again by the joint)
    for at, out_to in ((s_min, 0.0), (s_max, L)):
        if abs(at - out_to) <= TOL:
            continue
        eps = 1e-4 if out_to == 0.0 else -1e-4
        from shapely.geometry import LineString
        cut = region.intersection(LineString([(at + eps, zb - 1),
                                              (at + eps, z_top + 1)]))
        segs = [g for g in getattr(cut, "geoms", [cut])
                if not g.is_empty and g.geom_type == "LineString"]
        if len(segs) != 1:
            return None, WHY_JOINED
        z0s = min(c[1] for c in segs[0].coords)
        z1s = max(c[1] for c in segs[0].coords)
        x0, x1 = sorted((out_to, at + eps))
        region = unary_union([region, box(x0, z0s, x1, z1s)]).buffer(0)
    if region.geom_type != "Polygon":
        return None, WHY_TWO
    # gaps along the foot: a door's notch (filled: it is the door's) — or,
    # at an end, a foot not whole
    gaps = box(0.0, zb, L, z_top).difference(region)
    notches = []
    for g in getattr(gaps, "geoms", [gaps]):
        if g.is_empty or g.area < 1e-8:
            continue
        gx0, gz0, gx1, gz1 = g.bounds
        if gz0 > zb + TOL:
            continue
        if gx0 <= TOL or gx1 >= L - TOL:
            return None, WHY_FOOT_CUT
        notches.append(g)
    full = unary_union([region] + notches).buffer(0) if notches else region
    if full.geom_type != "Polygon":
        return None, WHY_TWO
    holes = [list(r.coords)[:-1] for r in full.interiors] \
        + [list(g.exterior.coords)[:-1] for g in notches]
    # ---- its shape seen from the front ----
    loop = []
    for s, z in list(full.exterior.coords)[:-1]:
        p = (_r4(min(max(s, 0.0), L)), _r4(max(z - z_foot, 0.0)))
        if not loop or p != loop[-1]:
            loop.append(p)
    if len(loop) > 1 and loop[0] == loop[-1]:
        loop.pop()
    ctrl, curves = OL.shape(loop)
    got = _foot_first(ctrl, curves, _r4(L))
    if got is None:
        return None, WS.WHY_FOOT
    ctrl, curves = got
    height = wall.get("height", "level") if known else "level"
    if known and wall.get("profile"):
        height = (wall["profile"] or {}).get("was", height)
    elif known and wall.get("top"):
        height = (wall["top"] or {}).get("was", height)
    prof = {"ctrl": ctrl, "curves": curves, "L": _r4(L), "was": height}
    why = WS.why_not(prof)
    if why:
        return None, why
    base = float(wall.get("base", 0.0) or 0.0) if known else 0.0
    rec = {"kind": "line", "a": [_r4(a[0]), _r4(a[1])],
           "b": [_r4(b[0]), _r4(b[1])], "t": _r4(pl["t"])}
    H = WS.is_rect(prof)
    if H is not None:
        rec["height"] = _r4(base + H)            # a plain wall again
        rec["profile"] = None
    else:
        rec["profile"] = prof
        rec["height"] = _r4(base + WS.peak(prof))
    out = {"wall": rec, "known": known, "volume": vol, "z_foot": z_foot,
           "holes": holes, "z_ref": z_ref, "L": L}
    if known:
        ops, kept, why = openings(holes, z_ref, old_ops)
        if why:
            return None, why
        out["openings"], out["kept"] = ops, kept
    return out, None


def on_level(got: dict, z_level: float) -> tuple:
    """(got, why): a wall of its own (nothing known) put on its level — its
    Base offset its foot over the floor, its height and its openings from
    there."""
    from . import walls as W
    rec = got["wall"]
    base = _r4(got["z_foot"] - z_level)
    if abs(base) < TOL:
        base = 0.0
    rec["base"] = base
    prof = rec.get("profile")
    rec["height"] = _r4(base + (WS.peak(prof) if prof else
                                rec["height"]))
    z_ref = z_level + W.opening_lift(rec)
    ops, _kept, why = openings(got["holes"], z_ref)
    if why:
        return None, why
    got["openings"], got["kept"], got["z_ref"] = ops, 0, z_ref
    return got, None


def _foot_first(ctrl, curves, L: float):
    """The control corners turned to start at the foot — (0, 0) then
    (L, 0) — and their curves' indices with them; None: no whole foot."""
    k = len(ctrl)
    for i in range(k):
        p, q = ctrl[i], ctrl[(i + 1) % k]
        if abs(p[0]) <= TOL and abs(p[1]) <= TOL \
                and abs(q[0] - L) <= TOL and abs(q[1]) <= TOL:
            out = [list(ctrl[(i + j) % k]) for j in range(k)]
            out[0], out[1] = [0.0, 0.0], [L, 0.0]
            cv = {"r": {}, "arc": {}}
            for key in ("r", "arc"):
                for j, v in ((curves or {}).get(key) or {}).items():
                    cv[key][str((int(j) - i) % k)] = v
            return [[_r4(x), _r4(z)] for x, z in out], cv
    return None


# ---- its holes: openings ----------------------------------------------------------------
def _on_outline(pts, ref, tol: float) -> bool:
    """Every point within ``tol`` of the closed outline ``ref``."""
    k = len(ref)
    for p in pts:
        best = math.inf
        for i in range(k):
            a, b = ref[i], ref[(i + 1) % k]
            dx, dz = b[0] - a[0], b[1] - a[1]
            L2 = dx * dx + dz * dz
            t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, (
                (p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / L2))
            best = min(best, math.hypot(p[0] - a[0] - dx * t,
                                        p[1] - a[1] - dz * t))
            if best <= tol:
                break
        if best > tol:
            return False
    return True


def _same(hole, ref) -> bool:
    """The hole IS this outline: its points on it and the outline's on
    the hole (both ways — 1 mm; an arc's chords: 1 % of its area)."""
    a1, a2 = abs(SH.area(hole)), abs(SH.area(ref))
    if a2 < 1e-9 or abs(a1 - a2) > max(0.01 * a2, 1e-4):
        return False
    return _on_outline(hole, ref, 2 * TOL) and _on_outline(
        [p for p in ref if True], hole, 0.02)


def hole_shape(hole, z_ref: float) -> dict | None:
    """The Opening a hole is — {"pos", "w", "h", "sill", shape keys…} —
    or None: no shape of shapes.py fits it."""
    s0 = min(p[0] for p in hole)
    s1 = max(p[0] for p in hole)
    zlo = min(p[1] for p in hole)
    zhi = max(p[1] for p in hole)
    w = s1 - s0
    door = zlo <= z_ref + DOOR_GAP
    sill = 0.0 if door else zlo - z_ref
    zs = z_ref + sill
    h = zhi - zs
    if w < 0.02 or h < 0.02:
        return None
    base = {"pos": _r4((s0 + s1) / 2), "w": _r4(w), "h": _r4(h),
            "sill": _r4(sill)}
    rect = [(s0, zlo), (s1, zlo), (s1, zhi), (s0, zhi)]
    if _same(hole, rect):
        return base
    # its spring: the highest point on its left side; its top's width
    lefts = [p[1] for p in hole if abs(p[0] - s0) <= TOL]
    spring = max(lefts) if lefts else zs
    rise = zhi - spring
    tops = [p[0] for p in hole if abs(p[1] - zhi) <= TOL]
    top_w = (max(tops) - min(tops)) if tops else 0.0
    for name in ("round_top", "round_arch", "seg_arch", "pointed",
                 "pentagon", "trapezoid", "triangle", "circle", "oval"):
        o = dict(base, kind="void", shape=name)
        if name in SH.RISE:
            o["rise"] = _r4(max(rise, 0.05))
        if name == "trapezoid":
            o["top_w"] = _r4(max(top_w, 0.05))
        o = dict(base, kind="void", **SH.clean(o))   # (its own keys only)
        ref = SH.outline(o, z_ref, steps=96)
        if ref and _same(hole, ref):
            keep = {k: o[k] for k in ("shape", "rise", "top_w") if k in o}
            return dict(base, **keep)
    return None


def openings(holes, z_ref: float, old_ops=()) -> tuple:
    """(records, kept, why): the old doors / windows whose hole is still
    there, as they were; every other hole a new Opening (a void, no id /
    wall yet); why: a hole of no shape."""
    old = list(old_ops or ())
    out, kept, used = [], 0, set()
    for hole in holes:
        hit = None
        for o in old:
            if o["id"] in used:
                continue
            s0, s1 = o["pos"] - o["w"] / 2, o["pos"] + o["w"] / 2
            zs = z_ref + float(o.get("sill", 0.0) or 0.0)
            zt = zs + float(o["h"])
            hs0 = min(p[0] for p in hole)
            hs1 = max(p[0] for p in hole)
            hz0 = min(p[1] for p in hole)
            hz1 = max(p[1] for p in hole)
            if abs(hs0 - s0) > 2 * TOL or abs(hs1 - s1) > 2 * TOL \
                    or abs(hz1 - zt) > 2 * TOL:
                continue
            if zs <= z_ref + 1e-6:                # a door: cut below
                if hz0 > zs + TOL:
                    continue
            elif abs(hz0 - zs) > 2 * TOL:
                continue
            ref = SH.outline(o, z_ref, steps=96)
            if ref is not None and not _same(hole, ref):
                continue
            hit = o
            break
        if hit is not None:
            used.add(hit["id"])
            out.append(dict(hit))
            kept += 1
            continue
        got = hole_shape(hole, z_ref)
        if got is None:
            return None, 0, WHY_HOLE
        out.append(dict(got, kind="void"))
    return out, kept, None
