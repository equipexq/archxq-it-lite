"""ArchXQ structure — the ENGINE. Pure: no IngeTrazo, no Qt.

Columns, beams, slabs and footings, and how they sit with the walls,
level by level. ``build(doc, union)`` gives every element of the
building (walls too) with its faces, at its true heights:

- a level's SLAB has its top at the level's floor (+ its offset); the
  walls, columns and beams of the level BELOW stop at its underside —
  nothing passes through a slab;
- COLUMNS and BEAMS are 1 mm smaller on every face: inside a wall of the
  same width they hide (no two faces in one plane, nothing flickers);
  wider, they read as pilasters / downstand beams;
- a FOOTING hangs under its level's slab (its top at the slab's
  underside, or at the floor without a slab).

Records (``doc["structure"]``): {"id", "name", "type", "level", …}
    column  x, y, shape "rect"|"round", w, d (rect; round: w = Ø),
            angle (°), anchor "centre"|"corner", height "level"|m
    beam    a, b, w (width), h (height)
    slab    corners [[x, y]…], t, offset
    footing kind "pad": x, y, w, d (depth), angle
            kind "strip": a, b (or an arc's "m"), w, d
    roof    kind "gable"|"hip"|"flat", corners, slope, overhang, t,
            ridge "long"|"short", parapet, pt — on its level's wall tops
"""
from __future__ import annotations

import math

from . import walls as W

SHRINK = 0.001          # m off every face of columns and beams
#: …and of the ones FITTED inside a wall: the host draws edges with a
#: small depth offset, and 1 mm behind a wall's face their lines showed
#: through it (seen on the demo, 2026-10-03) — 1 cm hides them, and a
#: hidden structure 2 cm slimmer is never seen
FIT_SHRINK = 0.01
ROUND_SEGS = 24         # a round column's sides
TYPES = ("column", "beam", "slab", "footing", "roof", "ramp", "stair")
LABEL = {"column": "Column", "beam": "Beam", "slab": "Slab",
         "footing": "Footing", "wall": "Wall", "roof": "Roof",
         "ramp": "Ramp", "stair": "Stair"}


# ---- levels ------------------------------------------------------------------------
def levels_info(doc: dict, elevations) -> dict:
    """Per level id: z0 (floor), height, the slab thickness ON it, and
    ``under`` = where things of this level stop (the next level's slab
    underside; the level's top without one)."""
    levels = doc["levels"]
    ground = doc["project"]["ground_level"] if doc.get("project") else 0.0
    elev = elevations(levels, ground)
    slab_t = {}
    for s in doc.get("structure") or []:
        if s["type"] == "slab":
            slab_t[s["level"]] = max(slab_t.get(s["level"], 0.0),
                                     float(s["t"]) - float(s.get("offset", 0)))
    out = {}
    for i, lv in enumerate(levels):
        top = elev[i] + float(lv["height"])
        above = levels[i + 1]["id"] if i + 1 < len(levels) else None
        out[lv["id"]] = {"z0": elev[i], "height": float(lv["height"]),
                         "slab": slab_t.get(lv["id"], 0.0),
                         "under": top - (slab_t.get(above, 0.0) if above
                                         else 0.0)}
    return out


# ---- plans ---------------------------------------------------------------------------
def _rot(p, c, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * ca - y * sa, c[1] + x * sa + y * ca)


def column_outline(c: dict, shrink: float = SHRINK) -> list:
    """The column's section in plan, counter-clockwise."""
    x, y = float(c["x"]), float(c["y"])
    w = float(c["w"]) - 2 * shrink
    if c.get("shape") == "round":
        r = w / 2.0
        return [(x + r * math.cos(2 * math.pi * k / ROUND_SEGS),
                 y + r * math.sin(2 * math.pi * k / ROUND_SEGS))
                for k in range(ROUND_SEGS)]
    d = float(c["d"]) - 2 * shrink
    ang = math.radians(float(c.get("angle", 0.0)))
    # (x, y) is the column's insertion point: its centre, a corner or a
    # side's middle (``anchor``) — the section's middle sits off it
    ax, ay = ANCHORS.get(c.get("anchor", "centre"), (0, 0))
    W, D = float(c["w"]), float(c["d"])
    mx, my = x - ax * W / 2, y - ay * D / 2
    pts = [(mx - w / 2, my - d / 2), (mx + w / 2, my - d / 2),
           (mx + w / 2, my + d / 2), (mx - w / 2, my + d / 2)]
    return [_rot(p, (x, y), ang) for p in pts]


#: the insertion points of a rectangular column: (−1|0|1 across, along)
#: — «corner» (older files) is the lower left one
ANCHORS = {"centre": (0, 0), "sw": (-1, -1), "corner": (-1, -1),
           "s": (0, -1), "se": (1, -1), "e": (1, 0), "ne": (1, 1),
           "n": (0, 1), "nw": (-1, 1), "w": (-1, 0)}


def column_centre(c: dict):
    """Where the column's axis is (off-centre insertion: the section's
    middle)."""
    if c.get("anchor", "centre") == "centre" or c.get("shape") == "round":
        return (float(c["x"]), float(c["y"]))
    pts = column_outline(c, 0.0)
    return (sum(p[0] for p in pts) / 4, sum(p[1] for p in pts) / 4)


def pad_outline(f: dict) -> list:
    x, y, w = float(f["x"]), float(f["y"]), float(f["w"])
    ang = math.radians(float(f.get("angle", 0.0)))
    pts = [(x - w / 2, y - w / 2), (x + w / 2, y - w / 2),
           (x + w / 2, y + w / 2), (x - w / 2, y + w / 2)]
    return [_rot(p, (x, y), ang) for p in pts]


def _ccw(loop):
    a = 0.5 * sum(p[0] * q[1] - q[0] * p[1]
                  for p, q in zip(loop, loop[1:] + loop[:1]))
    return list(loop) if a >= 0 else list(reversed(loop))


def as_wall(e: dict, width_key: str = "w", shrink: float = SHRINK) -> dict:
    """A beam or a strip footing, as a centre-aligned «wall» — the walls
    engine joins them (L, T, X) exactly as it joins walls."""
    rec = {"id": e["id"], "name": e.get("name", ""),
           "kind": "arc" if e.get("m") else "line",
           "a": list(e["a"]), "b": list(e["b"]),
           "t": float(e[width_key]) - 2 * shrink, "align": "centre",
           "side": 1}
    if e.get("m"):
        rec["m"] = list(e["m"])
    return rec


def why_not(e: dict) -> str | None:
    """Why an element can't be built (None = it can)."""
    t = e.get("type")
    try:
        if t == "column":
            if float(e["w"]) < 0.05 or (e.get("shape") != "round"
                                        and float(e["d"]) < 0.05):
                return "A column needs a section of 5 cm at least"
        elif t == "beam":
            if float(e["w"]) < 0.05 or float(e["h"]) < 0.05:
                return "A beam needs a width and a height"
            if math.dist(e["a"], e["b"]) < max(float(e["w"]), 0.1):
                return "Too short for a beam"
        elif t == "slab":
            if len(e["corners"]) < 3 or float(e["t"]) < 0.02:
                return "A slab needs three corners and a thickness"
            if abs(_area(e["corners"])) < 0.05:
                return "Too small for a slab"
        elif t == "footing":
            if float(e["w"]) < 0.1 or float(e["d"]) < 0.05:
                return "A footing needs a width and a depth"
            if e.get("kind") == "strip" and math.dist(e["a"], e["b"]) < 0.1:
                return "Too short for a footing"
        elif t == "roof":
            if len(e["corners"]) < 3 or abs(_area(e["corners"])) < 1.0:
                return "Too small for a roof"
            if e.get("kind") in ("gable", "hip") and not \
                    5.0 <= float(e["slope"]) <= 75.0:
                return "A pitched roof needs a slope of 5° to 75°"
        elif t == "ramp":                  # a «Building element» (ramps.py)
            from .ramps import why_not as ramp_why
            return ramp_why(e)
        elif t == "stair":                 # a «Building element» (stairs.py)
            from .stairs import why_not as stair_why
            return stair_why(e)
        else:
            return "Unknown element"
    except (KeyError, TypeError, ValueError):
        return "Incomplete element"
    return None


def _area(pts) -> float:
    return 0.5 * sum(p[0] * q[1] - q[0] * p[1]
                     for p, q in zip(pts, list(pts[1:]) + [pts[0]]))


# ---- structure INSIDE the walls (the usual case — his rule, 2026-10-03) ---------------
FIT_TOL = 0.02          # m past a wall's face that still counts as on it


def _walls_at(p, walls: list[dict]) -> list[tuple]:
    """[(wall, centre seg, fraction)] of the walls whose body holds p."""
    out = []
    for w in walls:
        if W.why_not(w) is not None:
            continue
        s = W.centre(w)
        f, off = s.project(p)
        if (W.is_closed(w) or -1e-6 <= f <= 1 + 1e-6) \
                and abs(off) <= float(w["t"]) / 2 + FIT_TOL:
            out.append((w, s, f % 1.0 if W.is_closed(w) else f))
    return out


def fit_column(c: dict, walls: list[dict]) -> dict:
    """A column standing on a wall goes INSIDE it: as thick as the wall,
    turned with it, on its centre line (its length along the wall kept).
    Where walls meet (a corner, a T): a square as thick as the thinnest.
    Off the walls: as it was drawn."""
    p = column_centre(c)
    here = _walls_at(p, walls)
    if not here:
        return dict(c, fit=False)
    # from here on its insertion point is its middle (an off-centre one —
    # a corner — moved there: it kept the corner's place before)
    c = dict(c, anchor="centre", fit=True, x=round(p[0], 4),
             y=round(p[1], 4))
    dirs = []
    for w, s, f in here:
        u = s.tangent(f)
        if not any(abs(u[0] * v[1] - u[1] * v[0]) < 0.05 for v in dirs):
            dirs.append(u)
    t = min(float(w["t"]) for w, _s, _f in here)
    w0, s0, f0 = here[0]
    if len(dirs) >= 2:                          # walls meeting: a square
        c.update(w=t, d=t)
    else:                                       # on one wall: in its line
        q = s0.at(min(max(f0, 0.0), 1.0))
        c.update(x=round(q[0], 4), y=round(q[1], 4),
                 w=max(float(c["w"]), float(c.get("d", c["w"]))), d=t)
        if c.get("shape") == "round":
            c.update(w=t, d=t)
    u = s0.tangent(f0)
    c["angle"] = round(math.degrees(math.atan2(u[1], u[0])), 3)
    if c.get("shape") == "round":
        c["w"] = c["d"] = t
    return c


def fit_beam(b: dict, walls: list[dict]) -> dict:
    """A beam on the line of a wall (along all of it, or running past it
    into the next room) takes the wall's thickness — where the wall is,
    it hides in it; past it, it reads as a downstand beam of the same
    width."""
    ax, ay = b["a"]
    bx, by = b["b"]
    L = math.hypot(bx - ax, by - ay)
    if L < 1e-9:
        return dict(b, fit=False)
    u = ((bx - ax) / L, (by - ay) / L)
    best = None
    for w in walls:
        if W.why_not(w) is not None or w.get("kind", "line") != "line":
            continue
        s = W.centre(w)
        if abs(u[0] * s.u[1] - u[1] * s.u[0]) > 0.01:
            continue                             # not the same way
        f0, off0 = s.project(b["a"])
        f1, off1 = s.project(b["b"])
        tol = float(w["t"]) / 2 + FIT_TOL
        if abs(off0) > tol or abs(off1) > tol:
            continue                             # not on its line
        if max(f0, f1) < 0.0 or min(f0, f1) > 1.0:
            continue                             # beside it, not along it
        t = float(w["t"])
        best = t if best is None else min(best, t)
    if best is None:
        return dict(b, fit=False)
    return dict(b, w=best, fit=True)


# ---- derived from the walls ----------------------------------------------------------
def wall_corners(walls: list[dict]) -> list:
    """Where the level's walls MEET (corners, T, X) — on their centre
    lines, so a column there sits in the middle of the walls (an outside-
    aligned wall's drawn corner is its outer corner: a column there would
    hang half out)."""
    good = [w for w in walls if W.why_not(w) is None and not W.is_closed(w)]
    centres = [W.centre(w) for w in good]
    ends = []                                  # (drawn point, wall index)
    for i, w in enumerate(good):
        d = W.drawn(w)
        ends += [(d.at(0.0), i), (d.at(1.0), i)]
    groups: list = []
    for p, i in ends:
        for g in groups:
            if math.dist(g[0], p) <= W.JOIN_TOL:
                g[1].add(i)
                break
        else:
            groups.append([p, {i}])
    # an end on another wall's body is a corner too (a T)
    for g in groups:
        if len(g[1]) == 1:
            for j, s in enumerate(centres):
                if j in g[1]:
                    continue
                f, off = s.project(g[0])
                if 0.0 < f < 1.0 and abs(off) <= good[j]["t"] / 2 + W.BODY_TOL:
                    g[1].add(j)
    out = []
    for p, ids in groups:
        if len(ids) < 2:
            continue
        ids = sorted(ids)
        pt = None
        for a in ids:
            for b in ids:
                if b <= a or centres[a].kind != "line" \
                        or centres[b].kind != "line":
                    continue
                got = W._meet(("line", centres[a].p0, centres[a].u),
                              ("line", centres[b].p0, centres[b].u))
                if got and math.dist(got[0], p) <= max(
                        good[a]["t"], good[b]["t"]) + W.JOIN_TOL:
                    pt = got[0]
                    break
            if pt:
                break
        out.append(tuple(pt) if pt else tuple(p))
    return out


def inside_walls(walls: list[dict], union) -> list | None:
    """A slab's outline from the level's walls: the outer contour of all
    of them together (``union(polygons) → outer loop`` is the host's
    shapely, handed in). None without walls."""
    plans = W.plan([w for w in walls if W.why_not(w) is None])
    polys = [pc for pieces in plans.values() for pc in pieces]
    if not polys:
        return None
    loop = union(polys)
    if not loop or len(loop) < 3:
        return None
    return [[round(p[0], 4), round(p[1], 4)] for p in _ccw(loop)]


def along_walls(walls: list[dict]) -> list[tuple]:
    """Beams over the level's straight walls: on each wall's centre line,
    end to end (curved / round walls are left out)."""
    out = []
    for w in walls:
        if W.why_not(w) is not None or w.get("kind", "line") != "line":
            continue
        s = W.centre(w)
        out.append(([round(s.p0[0], 4), round(s.p0[1], 4)],
                    [round(s.p1[0], 4), round(s.p1[1], 4)]))
    return out


def strips_under(walls: list[dict]) -> list[dict]:
    """Strip footings under the walls: on each wall's centre line (a
    curved wall's too)."""
    out = []
    for w in walls:
        if W.why_not(w) is not None or W.is_closed(w):
            continue
        s = W.centre(w)
        rec = {"a": [round(s.at(0.0)[0], 4), round(s.at(0.0)[1], 4)],
               "b": [round(s.at(1.0)[0], 4), round(s.at(1.0)[1], 4)]}
        if s.kind == "arc":
            m = s.at(0.5)
            rec["m"] = [round(m[0], 4), round(m[1], 4)]
        out.append(rec)
    return out


# ---- openings: doors, windows, voids in the walls -----------------------------------
#: an opening: {"id", "name", "kind": "door" | "window" | "void",
#:   "wall": wall id, "pos": its centre along the wall's line (m from the
#:   wall's start), "w", "h", "sill" (from the level's floor),
#:   "swing": "left" | "right" (a door's hinge, seen from inside)}
OPENING_LABEL = {"door": "Door", "window": "Window", "void": "Opening"}
FRAME = 0.05            # m, a frame's face width
FRAME_DEPTH = 0.07      # m, a frame's depth through the wall
LEAF = 0.04             # m, a door leaf
FRAME_COLOR = (0.94, 0.94, 0.92, 1.0)
GLASS_COLOR = (0.62, 0.80, 0.90, 0.35)
LEAF_COLOR = (0.58, 0.42, 0.28, 1.0)
END_GAP = 0.10          # m kept between an opening and its wall's end


def opening_room(o: dict, wall: dict, others: list[dict],
                 wall_height: float) -> str | None:
    """Why an opening can't go there (None = it can): it must sit on a
    straight wall, wholly, clear of the wall's ends and of the wall's
    other openings, under the wall's top."""
    if wall.get("kind", "line") != "line":
        return "Openings go in straight walls (curved: not yet)"
    L = W.drawn(wall).L
    half = float(o["w"]) / 2
    if float(o["w"]) < 0.2 or float(o["h"]) < 0.2:
        return "Too small for an opening"
    if o["pos"] - half < END_GAP or o["pos"] + half > L - END_GAP:
        return "It doesn't fit in that wall"
    if float(o.get("sill", 0)) + float(o["h"]) > wall_height - 0.05:
        return "Too tall for that wall"
    for p in others:
        if p.get("id") == o.get("id") or p["wall"] != o["wall"]:
            continue
        if abs(p["pos"] - o["pos"]) < (float(p["w"]) + float(o["w"])) / 2 \
                + 0.05:
            return "It runs into another opening of that wall"
    return None


def _clip(poly, p0, u, s, keep_more: bool) -> list:
    """The part of a plan polygon on one side of the line across the
    wall's axis at distance s (Sutherland–Hodgman, one half-plane)."""
    def d(p):
        return ((p[0] - p0[0]) * u[0] + (p[1] - p0[1]) * u[1] - s) * \
            (1 if keep_more else -1)
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        da, db = d(a), d(b)
        if da >= 0:
            out.append(a)
        if (da >= 0) != (db >= 0):
            t = da / (da - db)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out if len(out) >= 3 and abs(_area(out)) > 1e-9 else []


def wall_with_openings(piece: dict, seg, ops: list[dict], z0: float,
                       b: float, top: float) -> list:
    """A straight wall's solid with its openings, made as a plan draws
    it: each long face is ONE face with the openings cut out of it (a
    window: a hole; a door: a notch from the floor) — no seams running
    floor to ceiling past the jambs; then the openings' own faces (jambs,
    head, sill); the top and bottom faces lose what the openings take."""
    from shapely.geometry import Polygon, box
    from shapely.geometry.polygon import orient
    from shapely.ops import unary_union

    p0, u = seg.p0, seg.u
    poly = _ccw(list(piece["outer"]))
    eps = 1e-4
    spans = []                       # (s0, s1, zs, zt) — clipped to the wall
    for o in ops:
        zs = max(b, z0 + float(o.get("sill", 0.0)))
        zt = min(top, z0 + float(o.get("sill", 0.0)) + float(o["h"]))
        if zt - zs > 0.01:
            spans.append((o["pos"] - o["w"] / 2, o["pos"] + o["w"] / 2,
                          zs, zt))

    def S(p):
        return (p[0] - p0[0]) * u[0] + (p[1] - p0[1]) * u[1]

    faces = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        L = math.dist(p, q)
        if L < 1e-9:
            continue
        d = ((q[0] - p[0]) / L, (q[1] - p[1]) / L)
        along = abs(d[0] * u[1] - d[1] * u[0]) < 1e-6
        if not along:                # an end (square, mitred): whole
            faces.append([(p[0], p[1], b), (q[0], q[1], b),
                          (q[0], q[1], top), (p[0], p[1], top)])
            continue
        # this long face in its own (t along p→q, z) plane
        sp, sign = S(p), 1.0 if (d[0] * u[0] + d[1] * u[1]) > 0 else -1.0
        cut = []
        for s0, s1, zs, zt in spans:
            t0, t1 = sorted(((s0 - sp) * sign, (s1 - sp) * sign))
            if t1 > eps and t0 < L - eps:
                cut.append(box(t0, zs - (eps if zs <= b + eps else 0),
                               t1, zt + (eps if zt >= top - eps else 0)))
        region = box(0, b, L, top)
        if cut:
            region = region.difference(unary_union(cut))
        for g in getattr(region, "geoms", [region]):
            if g.is_empty or g.area < 1e-8:
                continue
            g = orient(g, 1.0)

            def P3(tz):
                t, z = tz
                return (p[0] + d[0] * t, p[1] + d[1] * t, z)
            faces.append({"loop": [P3(c) for c in list(g.exterior.coords)
                                   [:-1]],
                          "holes": [[P3(c) for c in list(r.coords)[:-1]]
                                    for r in g.interiors]})
    # the openings' own faces: jambs, head, sill (across the wall)
    nrm = (-u[1], u[0])
    for s0, s1, zs, zt in spans:
        # where the two long faces are at s (the faces' across offsets)
        offs = sorted({round((pt[0] - p0[0]) * nrm[0]
                             + (pt[1] - p0[1]) * nrm[1], 6) for pt in poly})
        c_lo, c_hi = offs[0], offs[-1]

        def P(s, c, z):
            return (p0[0] + u[0] * s + nrm[0] * c,
                    p0[1] + u[1] * s + nrm[1] * c, z)
        # jambs: at s0 facing +u, at s1 facing −u (into the opening);
        # (u, n, z) is right-handed: n × z = u
        faces.append([P(s0, c_lo, zs), P(s0, c_hi, zs), P(s0, c_hi, zt),
                      P(s0, c_lo, zt)])
        faces.append([P(s1, c_lo, zs), P(s1, c_lo, zt), P(s1, c_hi, zt),
                      P(s1, c_hi, zs)])
        if zt < top - eps:                       # the head, facing down
            faces.append([P(s0, c_lo, zt), P(s0, c_hi, zt), P(s1, c_hi, zt),
                          P(s1, c_lo, zt)])
        if zs > b + eps:                         # the sill, facing up
            faces.append([P(s0, c_lo, zs), P(s1, c_lo, zs), P(s1, c_hi, zs),
                          P(s0, c_hi, zs)])
    # top and bottom: the plan, less what reaches them
    for z, up in ((top, True), (b, False)):
        plan = Polygon(poly)
        bands = [box(min(s0, s1), -1e3, max(s0, s1), 1e3)
                 for s0, s1, zs, zt in spans
                 if (zt >= top - eps if up else zs <= b + eps)]
        if bands:
            from shapely import affinity
            ang = math.degrees(math.atan2(u[1], u[0]))
            band = affinity.rotate(unary_union(bands), ang, origin=(0, 0))
            band = affinity.translate(band, p0[0], p0[1])
            plan = plan.difference(band)
        for g in getattr(plan, "geoms", [plan]):
            if g.is_empty or g.area < 1e-8:
                continue
            g = orient(g, 1.0)
            loop = [(c[0], c[1], z) for c in list(g.exterior.coords)[:-1]]
            holes = [[(c[0], c[1], z) for c in list(r.coords)[:-1]]
                     for r in g.interiors]
            if not up:                           # the bottom faces down
                loop = list(reversed(loop))
                holes = [list(reversed(h)) for h in holes]
            faces.append({"loop": loop, "holes": holes})
    return faces


def _box(p0, u, n, sa, sb, ca, cb, za, zb, color) -> list:
    """A box along a wall: axial sa..sb, across ca..cb (n side), height
    za..zb — six faces, outward, each with its colour."""
    def P(s, c, z):
        return (p0[0] + u[0] * s + n[0] * c, p0[1] + u[1] * s + n[1] * c, z)
    c = [P(sa, ca, za), P(sb, ca, za), P(sb, cb, za), P(sa, cb, za),
         P(sa, ca, zb), P(sb, ca, zb), P(sb, cb, zb), P(sa, cb, zb)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
             (2, 3, 7, 6), (3, 0, 4, 7)]
    # (u, n, z) is right-handed: these loops face outward
    return [{"loop": [c[i] for i in q], "holes": [], "color": color}
            for q in quads]


def opening_parts(o: dict, seg, z0: float) -> list:
    """The frame (and glass / leaf) of an opening, on the wall's centre
    line: faces with their colours. A void has none."""
    if o["kind"] == "void":
        return []
    p0, u = seg.p0, seg.u
    n = (-u[1], u[0])
    s0, s1 = o["pos"] - o["w"] / 2, o["pos"] + o["w"] / 2
    zs = z0 + float(o.get("sill", 0.0))
    zt = zs + float(o["h"])
    hd = FRAME_DEPTH / 2
    f = FRAME
    parts = [_box(p0, u, n, s0, s0 + f, -hd, hd, zs, zt, FRAME_COLOR),
             _box(p0, u, n, s1 - f, s1, -hd, hd, zs, zt, FRAME_COLOR),
             _box(p0, u, n, s0 + f, s1 - f, -hd, hd, zt - f, zt,
                  FRAME_COLOR)]
    if o["kind"] == "window":
        parts.append(_box(p0, u, n, s0 + f, s1 - f, -hd, hd, zs, zs + f,
                          FRAME_COLOR))
        parts.append(_box(p0, u, n, s0 + f, s1 - f, -0.005, 0.005,
                          zs + f, zt - f, GLASS_COLOR))
    else:                                            # a door: its leaf
        parts.append(_box(p0, u, n, s0 + f, s1 - f, -LEAF / 2, LEAF / 2,
                          zs + 0.01, zt - f, LEAF_COLOR))
    return [face for p in parts for face in p]


# ---- roofs ---------------------------------------------------------------------------
#: a roof: {"type": "roof", "kind": "gable" | "hip" | "flat",
#:   "corners": its outline (a pitched roof: a rectangle, 4 corners),
#:   "slope" (°), "overhang", "t" (thickness), "ridge": "long" | "short"
#:   (a gable's), "parapet" (m over a flat roof, 0 = none), "pt" (its
#:   thickness)} — it rests on the top of its level's walls.
ROOF_COLOR = (0.66, 0.36, 0.27, 1.0)       # tiles
FLAT_COLOR = (0.72, 0.73, 0.74, 1.0)       # a flat roof (concrete)
GABLE_COLOR = (0.88, 0.86, 0.82, 1.0)      # the gable walls (as walls)


def rect_frame(corners):
    """(centre, unit along the first side, half-length, unit across,
    half-width) of a 4-corner rectangle outline."""
    c = [tuple(p) for p in corners]
    cx = sum(p[0] for p in c) / 4
    cy = sum(p[1] for p in c) / 4
    e0 = (c[1][0] - c[0][0], c[1][1] - c[0][1])
    e1 = (c[2][0] - c[1][0], c[2][1] - c[1][1])
    a, b = math.hypot(*e0), math.hypot(*e1)
    u0 = (e0[0] / a, e0[1] / a) if a > 1e-9 else (1.0, 0.0)
    return (cx, cy), u0, a / 2, (-u0[1], u0[0]), b / 2


def _sweep(section, x0, x1, P, color) -> list:
    """A section (y, z), counter-clockwise, swept along x from x0 to x1:
    its two caps and its sides, outward."""
    faces = [{"loop": [P(x1, y, z) for y, z in section], "holes": [],
              "color": color},
             {"loop": [P(x0, y, z) for y, z in reversed(section)],
              "holes": [], "color": color}]
    n = len(section)
    for i in range(n):
        (py, pz), (qy, qz) = section[i], section[(i + 1) % n]
        faces.append({"loop": [P(x0, py, pz), P(x0, qy, qz), P(x1, qy, qz),
                               P(x1, py, pz)], "holes": [], "color": color})
    return faces


def _faces(raw, color) -> list:
    return [dict(f, color=color) if isinstance(f, dict) else
            {"loop": f, "holes": [], "color": color} for f in raw]


def roof_faces(r: dict, base: float, wall_t: float = 0.20) -> list:
    """A roof's faces, resting on ``base`` (its level's wall tops): a
    pitched roof's underside passes through the walls' outer top edge."""
    kind = r.get("kind", "flat")
    t = float(r.get("t", 0.20))
    o = float(r.get("overhang", 0.0))
    if kind == "flat":
        from shapely.geometry import Polygon
        from shapely.geometry.polygon import orient
        poly = Polygon(r["corners"])
        if o > 1e-6:
            poly = poly.buffer(o, join_style=2)
        poly = orient(poly, 1.0)
        outer = list(poly.exterior.coords)[:-1]
        faces = _faces(W.solid({"outer": outer, "holes": []}, base,
                               base + t), FLAT_COLOR)
        ph, pt = float(r.get("parapet", 0.0)), float(r.get("pt", 0.15))
        inner = poly.buffer(-pt, join_style=2) if ph > 1e-6 else None
        if inner is not None and inner.geom_type == "Polygon" \
                and inner.area > 0.1:                # the parapet: a ring
            hole = list(orient(inner, 1.0).exterior.coords)[:-1]
            ring = {"outer": outer, "holes": [list(reversed(hole))]}
            faces += _faces(W.solid(ring, base + t, base + t + ph),
                            GABLE_COLOR)
        return faces
    (cx, cy), u0, ha, v0, hb = rect_frame(r["corners"])
    # x along the ridge (the longer side; a gable may be asked the other
    # way), y across, z up — a right-handed frame
    along = ha >= hb
    if kind == "gable" and r.get("ridge", "long") == "short":
        along = not along
    ux, A, B = (u0, ha, hb) if along else (v0, hb, ha)
    uy = (-ux[1], ux[0])
    ang = math.radians(float(r.get("slope", 30.0)))
    tan, dz = math.tan(ang), t / math.cos(ang)

    def P(x, y, z):
        return (cx + ux[0] * x + uy[0] * y, cy + ux[1] * x + uy[1] * y, z)
    if kind == "gable":
        Y, X = B + o, A + o

        def zb(y):
            return base + (B - abs(y)) * tan
        # counter-clockwise in (y, z): along the underside, up the eave,
        # back along the top
        section = [(-Y, zb(-Y)), (0, zb(0)), (Y, zb(Y)), (Y, zb(Y) + dz),
                   (0, zb(0) + dz), (-Y, zb(-Y) + dz)]
        faces = _sweep(section, -X, X, P, ROOF_COLOR)
        # the gable walls: a triangle on each end wall, as thick as it —
        # 2 mm under the roof and 1 mm off the wall's faces (no coplanar
        # faces), its foot 1 mm down into the wall
        d = 0.002
        b2 = B - d / tan
        tri = [(-b2, base - 0.001), (b2, base - 0.001), (0, zb(0) - d)]
        faces += _sweep(tri, A - wall_t + 0.001, A - 0.001, P, GABLE_COLOR)
        faces += _sweep(tri, -A + 0.001, -A + wall_t - 0.001, P,
                        GABLE_COLOR)
        return faces
    # a hip roof: four planes of one slope, the ridge along x
    Ao, Bo = A + o, B + o
    ze, zr = base - o * tan, base + B * tan
    r1, r2 = (-(A - B), 0.0), ((A - B), 0.0)
    sw, se, ne, nw = (-Ao, -Bo), (Ao, -Bo), (Ao, Bo), (-Ao, Bo)
    eaves = (sw, se, ne, nw)
    faces = []
    for loop in ([sw, se, r2, r1], [se, ne, r2], [ne, nw, r1, r2],
                 [nw, sw, r1]):
        pts = []
        for q in loop:
            if all(math.dist(q, p) > 1e-9 for p in pts):
                pts.append(q)
        zt = [ze if q in eaves else zr for q in pts]
        faces.append({"loop": [P(q[0], q[1], z + dz)
                               for q, z in zip(pts, zt)], "holes": [],
                      "color": ROOF_COLOR})
        faces.append({"loop": [P(q[0], q[1], z) for q, z in
                               reversed(list(zip(pts, zt)))], "holes": [],
                      "color": ROOF_COLOR})
    for i in range(4):                           # the eaves' fascias
        p, q = eaves[i], eaves[(i + 1) % 4]
        faces.append({"loop": [P(p[0], p[1], ze), P(q[0], q[1], ze),
                               P(q[0], q[1], ze + dz), P(p[0], p[1], ze + dz)],
                      "holes": [], "color": ROOF_COLOR})
    return faces


def roof_outline(walls: list[dict], union, kind: str):
    """A roof's outline from its level's walls: their outer contour; a
    pitched roof's, the rectangle round it (turned with the building)."""
    loop = inside_walls(walls, union)
    return roof_corners(loop, kind) if loop else loop


def roof_corners(corners, kind: str) -> list:
    """A roof's corners as stored: a flat roof's as drawn; a pitched
    roof's, the rectangle round them (turned with them)."""
    pts = _ccw([tuple(p) for p in corners])
    if kind != "flat":
        from shapely.geometry import Polygon
        rect = Polygon(pts).minimum_rotated_rectangle
        pts = _ccw(list(rect.exterior.coords)[:-1])
    return [[round(p[0], 4), round(p[1], 4)] for p in pts]


# ---- everything, with its faces ----------------------------------------------------
def build(doc: dict, elevations) -> list[dict]:
    """[{"kind", "id", "name", "level", "faces"}] for every wall and
    structural element of the building, at its true heights."""
    info = levels_info(doc, elevations)
    out = []
    walls = doc.get("walls") or []
    struct = doc.get("structure") or []
    openings = doc.get("openings") or []
    # the ramps open their way through the slabs they cross — the hole is
    # not stored: it follows the ramp, and goes with it (ramps.py)
    ramp_cuts: dict = {}
    for r in struct:
        if r.get("type") in ("ramp", "stair") and why_not(r) is None:
            from . import ramps as R
            if r["type"] == "ramp":
                zs, ze = R.heights(r, doc, elevations)
                polys = R.footprints(r, zs, ze, R.length_of(r, zs, ze))
            else:
                from . import stairs as ST
                polys = ST.footprints(r, doc, elevations)
            for lid in R.through_levels(r, doc, elevations):
                ramp_cuts.setdefault(lid, []).extend(polys)
    for lid, li in info.items():
        z0, under = li["z0"], li["under"]
        # walls — cut by their openings
        mine = [w for w in walls if w["level"] == lid]
        plans = W.plan(mine)
        for w in mine:
            pieces = plans.get(w["id"])
            if not pieces:
                continue
            b = z0 + float(w.get("base", 0.0))
            top = under if w.get("height", "level") == "level" \
                else z0 + float(w["height"])
            if top - b < 0.01:
                continue
            ops = [o for o in openings if o["wall"] == w["id"]
                   and opening_room(o, w, openings, top - z0) is None]
            if ops:
                seg = W.centre(w)
                faces = [f for pc in pieces
                         for f in wall_with_openings(pc, seg, ops, z0, b,
                                                     top)]
                for o in ops:
                    parts = opening_parts(o, seg, z0)
                    if parts:
                        out.append({"kind": "opening", "id": o["id"],
                                    "name": o["name"], "level": lid,
                                    "okind": o["kind"], "faces": parts})
            else:
                faces = [f for pc in pieces for f in W.solid(pc, b, top)]
            out.append({"kind": "wall", "id": w["id"], "name": w["name"],
                        "level": lid, "faces": faces})
        els = [e for e in struct if e["level"] == lid and why_not(e) is None]
        # columns
        for c in (e for e in els if e["type"] == "column"):
            top = (under if c.get("height", "level") == "level"
                   else z0 + float(c["height"])) - SHRINK
            sh = FIT_SHRINK if c.get("fit") else SHRINK
            piece = {"outer": _ccw(column_outline(c, sh)), "holes": []}
            bot = z0 + float(c.get("base", 0.0)) + SHRINK   # its base
            if top - bot < 0.05:
                continue
            out.append(dict(_el(c, lid, W.solid(piece, bot, top)),
                            inwall=in_one_wall(c, mine)))
        # beams: joined among themselves like walls
        beams = [e for e in els if e["type"] == "beam"]
        bplans = W.plan([as_wall(e, shrink=FIT_SHRINK if e.get("fit")
                                 else SHRINK) for e in beams])
        for e in beams:
            top = under - SHRINK
            bot = top - float(e["h"]) + 2 * SHRINK
            out.append(dict(_el(e, lid, [f for pc in bplans.get(e["id"], ())
                                         for f in W.solid(pc, bot, top)]),
                            inwall=in_one_wall(e, mine)))
        # slabs
        for s in (e for e in els if e["type"] == "slab"):
            top = z0 + float(s.get("offset", 0.0))
            piece = {"outer": _ccw([tuple(p) for p in s["corners"]]),
                     # openings wound the other way round
                     "holes": [list(reversed(_ccw([tuple(p) for p in h])))
                               for h in s.get("holes") or []]}
            parts = [piece]
            if ramp_cuts.get(lid):
                from . import ramps as R
                cut = R.cut_slab(piece["outer"], piece["holes"],
                                 ramp_cuts[lid])
                if cut is not None:
                    parts = cut
            out.append(_el(s, lid, [f for pc in parts for f in W.solid(
                pc, top - float(s["t"]), top)]))
        # footings: under the slab of their level
        ftop = z0 - li["slab"]
        pads = [e for e in els if e["type"] == "footing"
                and e.get("kind") == "pad"]
        for f in pads:
            piece = {"outer": _ccw(pad_outline(f)), "holes": []}
            out.append(_el(f, lid, W.solid(piece, ftop - float(f["d"]),
                                           ftop)))
        strips = [e for e in els if e["type"] == "footing"
                  and e.get("kind") == "strip"]
        splans = W.plan([as_wall(e, shrink=0.0) for e in strips])
        for f in strips:
            # 1 mm under the pads' top: where a strip runs into a pad the
            # two tops would share one plane (and flicker)
            out.append(_el(f, lid, [pc_f for pc in splans.get(f["id"], ())
                                    for pc_f in W.solid(
                                        pc, ftop - float(f["d"]),
                                        ftop - SHRINK)]))
        # roofs: on the top of the level's walls
        wall_t = max((float(w["t"]) for w in mine), default=0.20)
        for r in (e for e in els if e["type"] == "roof"):
            out.append(_el(r, lid, roof_faces(r, under, wall_t)))
        # ramps: from this level (or the ground) to another (ramps.py)
        rmps = [e for e in els if e["type"] == "ramp"]
        if rmps:
            from . import ramps as R
            for r in rmps:
                out.append(_el(r, lid, R.faces(r, doc, elevations)))
        # stairs: the same, with steps (stairs.py)
        sts = [e for e in els if e["type"] == "stair"]
        if sts:
            from . import stairs as ST
            for r in sts:
                out.append(_el(r, lid, ST.faces(r, doc, elevations)))
    return [e for e in out if e["faces"]]


def hole_place(slabs: list[dict], hole) -> tuple:
    """(slab, reason): the slab an opening drawn at ``hole`` goes
    through — the one that holds it all, clear of its other openings."""
    from shapely.geometry import Polygon
    h = Polygon(hole)
    if not h.is_valid or h.area < 0.01:
        return None, "Too small for an opening"
    for s in slabs:
        outer = Polygon(s["corners"])
        if not outer.is_valid:
            outer = outer.buffer(0)
        if not outer.buffer(1e-6).contains(h):
            continue
        if any(Polygon(o).intersects(h) for o in s.get("holes") or []):
            return None, "It runs into another opening of that slab"
        return s, None
    return None, "Draw the opening inside a slab of this level"


def in_one_wall(e: dict, walls: list[dict]) -> bool:
    """A fitted column, or a beam lying wholly within one wall: it is
    INSIDE the wall — hidden while the walls are shown (its lines showed
    through them in a raking view; nothing of it is to be seen anyway)."""
    if not e.get("fit"):
        return False
    if e["type"] == "column":
        return True                     # fitted = inside by construction
    for w in walls:
        if W.why_not(w) is not None or w.get("kind", "line") != "line":
            continue
        s = W.centre(w)
        if all((-1e-6 <= f <= 1 + 1e-6) and
               abs(off) <= float(w["t"]) / 2 + FIT_TOL
               for f, off in (s.project(e["a"]), s.project(e["b"]))):
            return True
    return False


def _el(e: dict, lid: str, faces) -> dict:
    return {"kind": e["type"], "id": e["id"], "name": e["name"],
            "level": lid, "faces": faces}
