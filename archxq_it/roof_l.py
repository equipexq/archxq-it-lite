"""L-SHAPED pitched roofs — hip and gable (his go 2026-10-16: Badis needs
one for his building permit; PLANO_TELHADO_L.md).

An L is two WINGS — rectangles crossing in the corner square — each with
the roof of its own: the L's roof is, at every point, the HIGHER of the
two (their upper envelope), as one draws it by hand: a hip at the outer
corner, a valley at the inner one; a narrower wing's lower ridge dies on
the other's slope.

    hip    both wings whole (the corner square in each)
    gable  the MAIN wing whole, its gable facing out at the corner; the
           other wing from its free end to the main wing's ridge (its end
           there is under the main roof)

Each top face of a wing keeps the part where no other wing is higher —
planes cut by half-planes (shapely) — so the mesh has no face inside
another (clean sections). The underside is the same pieces lowered by the
slab's vertical thickness; the eaves' fascias and the gables' verges go
round the outline of it all; the outside walls are filled up to the
underside (gable triangles, the eave walls' wedges). Pure: no Qt.

A roof record stays as it is (structure.py): kind "gable" | "hip",
"corners" = the walls' OUTER outline, 6 corners at right angles; + "main":
"long" | "other" (a gable L: which wing keeps its gable at the corner).
"""
from __future__ import annotations

import math

#: two points this close are one; a point this close to a segment is on it
EPS = 1e-6
#: a face smaller than this (m²) is a sliver of the clipping: left out
SLIVER = 1e-5
#: the outside walls filled to 2 mm under the roof, 1 mm off their faces,
#: their foot 1 mm into the wall (no coplanar faces — the roofs' rule)
GAP = 0.002


# ---- is it an L? -------------------------------------------------------------------------
def _clean(pts):
    """Its corners without repeats and without points on a straight run."""
    out = []
    for p in pts:
        if not out or math.dist(out[-1], p) > 1e-4:
            out.append(p)
    if len(out) > 1 and math.dist(out[0], out[-1]) <= 1e-4:
        out.pop()
    changed = True
    while changed and len(out) > 3:
        changed = False
        for i in range(len(out)):
            a, b, c = out[i - 1], out[i], out[(i + 1) % len(out)]
            cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            if abs(cr) <= 1e-6 * max(math.dist(a, b) * math.dist(b, c), 1e-9):
                out.pop(i)
                changed = True
                break
    return out


def frame(corners):
    """(origin, u, v, local corners) — an L at right angles (6 corners,
    counter-clockwise), in the frame of its longest side; None: not an L."""
    from shapely.geometry import Polygon
    from shapely.geometry.polygon import orient
    pts = _clean([(float(p[0]), float(p[1])) for p in corners])
    if len(pts) != 6:
        return None
    try:
        poly = Polygon(pts)
        if not poly.is_valid or poly.area < 1.0:
            return None
        pts = list(orient(poly, 1.0).exterior.coords)[:-1]
    except Exception:  # noqa: BLE001
        return None
    edges = [(pts[i], pts[(i + 1) % 6]) for i in range(6)]
    a, b = max(edges, key=lambda e: math.dist(*e))
    n = math.dist(a, b)
    u = ((b[0] - a[0]) / n, (b[1] - a[1]) / n)
    v = (-u[1], u[0])
    o = pts[0]
    loc = [[(p[0] - o[0]) * u[0] + (p[1] - o[1]) * u[1],
            (p[0] - o[0]) * v[0] + (p[1] - o[1]) * v[1]] for p in pts]
    # every side along u or v (within 0.5°) — then made exactly so
    kinds = []
    for i in range(6):
        p, q = loc[i], loc[(i + 1) % 6]
        dx, dy = q[0] - p[0], q[1] - p[1]
        L = math.hypot(dx, dy)
        if L < 0.05:
            return None
        if abs(dy) / L < 0.009:
            kinds.append("h")
        elif abs(dx) / L < 0.009:
            kinds.append("v")
        else:
            return None
    if any(kinds[i] == kinds[(i + 1) % 6] for i in range(6)):
        return None
    for i in range(6):
        p, q = loc[i], loc[(i + 1) % 6]
        if kinds[i] == "h":
            p[1] = q[1] = (p[1] + q[1]) / 2
        else:
            p[0] = q[0] = (p[0] + q[0]) / 2
    return o, u, v, [tuple(p) for p in loc]


def is_l(corners) -> bool:
    return frame(corners) is not None


def wings(loc, kind: str, main: str = "long"):
    """The two wings, in the L's frame: [{"rect": (xa, xb, ya, yb), "axis":
    "x" | "y", "eaves": {side: True}, "ends": {side: overhang kind}}].
    Sides: "xa" "xb" "ya" "yb"."""
    xs = [p[0] for p in loc]
    ys = [p[1] for p in loc]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    # the inner (reflex) corner: turning right, counter-clockwise
    rx = ry = None
    for i in range(6):
        a, b, c = loc[i - 1], loc[i], loc[(i + 1) % 6]
        cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if cr < 0:
            rx, ry = b
    if rx is None:
        return None
    # the missing corner of the box round it (the notch): the one whose
    # quadrant past the inner corner is outside the L
    from shapely.geometry import Point, Polygon
    poly = Polygon(loc)
    nx = ny = None
    for cx in (x0, x1):
        for cy in (y0, y1):
            q = Point((cx + rx) / 2, (cy + ry) / 2)
            if not poly.contains(q):
                nx, ny = cx, cy
    if nx is None:
        return None
    fx = x1 if nx == x0 else x0             # the outer corner's sides
    fy = y1 if ny == y0 else y0
    h = {"rect": (x0, x1, min(fy, ry), max(fy, ry)), "axis": "x",
         "free": "xb" if nx == x1 else "xa",
         "corner": "xa" if nx == x1 else "xb"}
    v = {"rect": (min(fx, rx), max(fx, rx), y0, y1), "axis": "y",
         "free": "yb" if ny == y1 else "ya",
         "corner": "ya" if ny == y1 else "yb"}
    for w in (h, v):
        xa, xb, ya, yb = w["rect"]
        w["len"] = (xb - xa) if w["axis"] == "x" else (yb - ya)
        w["width"] = (yb - ya) if w["axis"] == "x" else (xb - xa)
    if kind == "hip":
        for w in (h, v):
            w["eaves"] = ("xa", "xb", "ya", "yb")
            w["gables"] = ()
            w["cut"] = None
        return [h, v]
    # gable: the main wing whole, the other one up to its ridge
    long_ = h if h["len"] >= v["len"] else v
    other = v if long_ is h else h
    m, s = (long_, other) if main != "other" else (other, long_)
    for w in (m, s):
        w["eaves"] = ("ya", "yb") if w["axis"] == "x" else ("xa", "xb")
        w["gables"] = ("xa", "xb") if w["axis"] == "x" else ("ya", "yb")
    mxa, mxb, mya, myb = m["rect"]
    xa, xb, ya, yb = s["rect"]
    if m["axis"] == "x":                     # s runs along y: cut in y
        ridge = (mya + myb) / 2
        if s["free"] == "yb":
            ya = ridge
        else:
            yb = ridge
    else:
        ridge = (mxa + mxb) / 2
        if s["free"] == "xb":
            xa = ridge
        else:
            xb = ridge
    s["rect"] = (xa, xb, ya, yb)
    s["cut"] = s["corner"]                   # no overhang, no gable there
    m["cut"] = None
    # across the main wing's span the other one stays INSIDE the main
    # roof: its eaves' overhang would run on past the main gable (a stub
    # seen on the test file, 2026-10-16)
    s["inside"] = m
    return [m, s]


# ---- planes -------------------------------------------------------------------------------
def _plane(side, rect, base, tan):
    """The underside plane rising from the eave on ``side`` (its wall's
    outer top edge at ``base``): z = a x + b y + c."""
    xa, xb, ya, yb = rect
    n, q = {"xa": ((1, 0), (xa, 0)), "xb": ((-1, 0), (xb, 0)),
            "ya": ((0, 1), (0, ya)), "yb": ((0, -1), (0, yb))}[side]
    a, b = tan * n[0], tan * n[1]
    return (a, b, base - a * q[0] - b * q[1])


def _z(pl, x, y):
    return pl[0] * x + pl[1] * y + pl[2]


def _half(a, b, c):
    """The half-plane a x + b y + c >= 0 (a big polygon)."""
    from shapely.geometry import Polygon, box
    R = 1.0e5
    n2 = a * a + b * b
    if n2 < 1e-18:
        return box(-R, -R, R, R) if c >= 0 else Polygon()
    L = math.sqrt(n2)
    nx, ny = a / L, b / L
    p0 = (-c * a / n2, -c * b / n2)
    dx, dy = -ny, nx
    return Polygon([(p0[0] - dx * R, p0[1] - dy * R),
                    (p0[0] + dx * R, p0[1] + dy * R),
                    (p0[0] + dx * R + nx * R, p0[1] + dy * R + ny * R),
                    (p0[0] - dx * R + nx * R, p0[1] - dy * R + ny * R)])


def _polys(g):
    """The polygons of a shapely result (slivers left out)."""
    if g is None or g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g] if g.area > SLIVER else []
    out = []
    for x in getattr(g, "geoms", []):
        out += _polys(x)
    return out


def _outline(w, o, go):
    """A wing's roof outline in plan: its rectangle grown by the eaves'
    overhang (``o``) and the gable ends' (``go``), not at a cut end."""
    from shapely.geometry import box
    xa, xb, ya, yb = w["rect"]
    grow = {}
    for s in ("xa", "xb", "ya", "yb"):
        grow[s] = 0.0 if s == w.get("cut") else (
            o if s in w["eaves"] else go)
    return box(xa - grow["xa"], ya - grow["ya"], xb + grow["xb"],
               yb + grow["yb"])


def wing_faces(w, base, tan, o, go):
    """[(plan Polygon, underside plane)] — one wing's roof, each face where
    its plane is the lowest (the roof over a rectangle: min of planes)."""
    from shapely.geometry import box
    outline = _outline(w, o, go)
    m = w.get("inside")
    if m is not None:                    # a gable L's other wing
        mxa, mxb, mya, myb = m["rect"]
        R = 1.0e4
        band = box(-R, mya, R, myb) if m["axis"] == "x" \
            else box(mxa, -R, mxb, R)
        outline = outline.difference(band.difference(_outline(m, o, go)))
    planes = [_plane(s, w["rect"], base, tan) for s in w["eaves"]]
    out = []
    for k, pk in enumerate(planes):
        reg = outline
        for m, pm in enumerate(planes):
            if m != k:                     # pk <= pm
                reg = reg.intersection(_half(pm[0] - pk[0], pm[1] - pk[1],
                                             pm[2] - pk[2]))
        for p in _polys(reg):
            out.append((p, pk))
    return out


def envelope(faces_by_wing):
    """[(Polygon, plane)] — every wing's faces where no other wing is
    higher: the L's roof seen from above."""
    from shapely.ops import unary_union
    out = []
    for i, faces in enumerate(faces_by_wing):
        for poly, pl in faces:
            higher = []
            for j, other in enumerate(faces_by_wing):
                if j == i:
                    continue
                for p2, q in other:
                    # where q is above pl (by more than a hair)
                    h = p2.intersection(_half(q[0] - pl[0], q[1] - pl[1],
                                              q[2] - pl[2] - 1e-7))
                    if not h.is_empty:
                        higher.append(h)
            vis = poly.difference(unary_union(higher)) if higher else poly
            # (where two planes only TOUCH along a line the difference
            # leaves a zero-wide spike: opened away)
            vis = vis.buffer(-1e-6, join_style=2, mitre_limit=10).buffer(
                1e-6, join_style=2, mitre_limit=10)
            for p in _polys(vis):
                out.append((p, pl))
    # one plane, one face: the outer corner's slope is ONE plane in both
    # wings (a seam there drew a false hip)
    groups = []
    for p, pl in out:
        for g in groups:
            q = g[1]
            if all(abs(pl[k] - q[k]) < 1e-7 for k in range(3)):
                g[0].append(p)
                break
        else:
            groups.append(([p], pl))
    merged = []
    for ps, pl in groups:
        u = unary_union([p.buffer(1e-9, join_style=2) for p in ps]).buffer(
            -1e-9, join_style=2)
        for p in _polys(u.simplify(1e-7)):
            merged.append((p, pl))
    return merged


# ---- faces ---------------------------------------------------------------------------------
def _ring_pts(ring):
    return [(x, y) for x, y in list(ring.coords)[:-1]]


def _flat_faces(pieces, zfun, up: bool, color):
    """Each piece as a face at z = zfun(plane, x, y): up = seen from above
    (counter-clockwise from above), else from below."""
    from shapely.geometry.polygon import orient
    out = []
    for poly, pl in pieces:
        g = orient(poly, 1.0)
        ext = _ring_pts(g.exterior)
        holes = [_ring_pts(h) for h in g.interiors]
        if not up:
            ext = list(reversed(ext))
            holes = [list(reversed(h)) for h in holes]
        out.append({"loop": [(x, y, zfun(pl, x, y)) for x, y in ext],
                    "holes": [[(x, y, zfun(pl, x, y)) for x, y in h]
                              for h in holes], "color": color})
    return out


def _on_seg(v, p, q) -> bool:
    L = math.dist(p, q)
    if L < EPS:
        return False
    t = ((v[0] - p[0]) * (q[0] - p[0]) + (v[1] - p[1]) * (q[1] - p[1])) / L ** 2
    if t <= 1e-9 or t >= 1 - 1e-9:
        return False
    px, py = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
    return math.hypot(v[0] - px, v[1] - py) < 1e-6


def _sides(pieces, ztop, zbot, color):
    """The vertical faces round the outline of all the pieces together,
    each stretch between the pieces' own corners — its top / bottom from
    the piece it bounds (outward)."""
    from shapely.geometry import Point
    from shapely.geometry.polygon import orient
    from shapely.ops import unary_union
    U = unary_union([p.buffer(1e-9, join_style=2) for p, _ in pieces])
    U = U.buffer(-1e-9, join_style=2)
    verts = []
    for p, _ in pieces:
        verts += _ring_pts(p.exterior)
        for h in p.interiors:
            verts += _ring_pts(h)
    out = []
    for g in _polys(U):
        g = orient(g, 1.0)
        for ring in [g.exterior, *g.interiors]:
            cs = _ring_pts(ring)
            seq = []
            for i in range(len(cs)):
                p, q = cs[i], cs[(i + 1) % len(cs)]
                on = sorted({v for v in verts if _on_seg(v, p, q)},
                            key=lambda v: math.dist(p, v))
                seq.append(p)
                seq += on
            for i in range(len(seq)):
                p, q = seq[i], seq[(i + 1) % len(seq)]
                L = math.dist(p, q)
                if L < 1e-5:
                    continue
                # inside is on the left (exterior CCW, holes CW)
                mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
                nx, ny = -(q[1] - p[1]) / L, (q[0] - p[0]) / L
                inner = Point(mx + nx * 1e-4, my + ny * 1e-4)
                pl = next((pl for poly, pl in pieces
                           if poly.buffer(1e-7).contains(inner)), None)
                if pl is None:
                    pl = min(pieces, key=lambda t: t[0].distance(inner))[1]
                out.append({"loop": [(p[0], p[1], zbot(pl, *p)),
                                     (q[0], q[1], zbot(pl, *q)),
                                     (q[0], q[1], ztop(pl, *q)),
                                     (p[0], p[1], ztop(pl, *p))],
                            "holes": [], "color": color})
    return out


def _steps(pieces, ztop, zbot, color):
    """Where one wing's outline ends INSIDE another's, the two surfaces
    meet at different heights: the vertical step between them, closed
    (a slit showed the faces' backs — test file, 2026-10-16). Made from
    the LOW side: the top step faces it, the bottom step the high side."""
    from shapely.geometry import Point
    from shapely.ops import unary_union
    U = unary_union([p.buffer(1e-9, join_style=2) for p, _ in pieces])
    outline = U.buffer(-1e-9, join_style=2).boundary
    verts = []
    for p, _ in pieces:
        verts += _ring_pts(p.exterior)
    out = []
    for poly, pl in pieces:
        cs = _ring_pts(poly.exterior)
        if poly.exterior.is_ccw is False:
            cs = list(reversed(cs))           # inside on the left
        seq = []
        for i in range(len(cs)):
            p, q = cs[i], cs[(i + 1) % len(cs)]
            seq.append(p)
            seq += sorted({v for v in verts if _on_seg(v, p, q)},
                          key=lambda v: math.dist(p, v))
        for i in range(len(seq)):
            p, q = seq[i], seq[(i + 1) % len(seq)]
            L = math.dist(p, q)
            if L < 1e-5:
                continue
            mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
            if outline.distance(Point(mx, my)) < 1e-6:
                continue                       # on the outline: _sides
            nx, ny = (q[1] - p[1]) / L, -(q[0] - p[0]) / L   # to the right
            outer = Point(mx + nx * 1e-4, my + ny * 1e-4)
            other = next((pl2 for poly2, pl2 in pieces if poly2 is not poly
                          and poly2.buffer(1e-7).contains(outer)), None)
            if other is None:
                continue
            lo_p, lo_q = ztop(pl, *p), ztop(pl, *q)
            hi_p, hi_q = ztop(other, *p), ztop(other, *q)
            if max(hi_p - lo_p, hi_q - lo_q) < 1e-5 or \
                    min(hi_p - lo_p, hi_q - lo_q) < -1e-5:
                continue                       # level, or this is the high side
            # the top step, facing this (low) side: walked q → p
            out.append({"loop": [(q[0], q[1], lo_q), (p[0], p[1], lo_p),
                                 (p[0], p[1], hi_p), (q[0], q[1], hi_q)],
                        "holes": [], "color": color})
            bl_p, bl_q = zbot(pl, *p), zbot(pl, *q)
            bh_p, bh_q = zbot(other, *p), zbot(other, *q)
            if max(bh_p - bl_p, bh_q - bl_q) > 1e-5:
                # the bottom step, facing the high side: walked p → q
                out.append({"loop": [(p[0], p[1], bl_p), (q[0], q[1], bl_q),
                                     (q[0], q[1], bh_q), (p[0], p[1], bh_p)],
                            "holes": [], "color": color})
    return out


def faces(r: dict, base: float, wall_t: float, roof_color, wall_color):
    """An L roof's faces (world coordinates): the roof slab over the
    envelope of its wings + the outside walls filled up to its underside.
    [] when its corners are not an L."""
    from shapely.geometry import Polygon
    fr = frame(r["corners"])
    if fr is None:
        return []
    o_, u, v, loc = fr
    kind = r.get("kind", "hip")
    ang = math.radians(float(r.get("slope", 30.0)))
    tan = math.tan(ang)
    dz = float(r.get("t", 0.20)) / math.cos(ang)
    o = float(r.get("overhang", 0.0))
    go = float(r.get("go", o))
    ws = wings(loc, kind, r.get("main", "long"))
    if not ws:
        return []
    env = envelope([wing_faces(w, base, tan, o, go) for w in ws])
    if not env:
        return []

    def top(pl, x, y):
        return _z(pl, x, y) + dz

    def under(pl, x, y):
        return _z(pl, x, y)
    out = _flat_faces(env, top, True, roof_color)
    out += _flat_faces(env, under, False, roof_color)
    out += _sides(env, top, under, roof_color)
    out += _steps(env, top, under, roof_color)
    # the outside walls up to the roof's underside: the ring of the walls
    # (1 mm off both faces), where the underside is over the wall's top
    L_ = Polygon(loc)
    ring = L_.buffer(-0.001, join_style=2).difference(
        L_.buffer(-(wall_t - 0.001), join_style=2))
    fill = []
    for poly, pl in env:
        part = poly.intersection(ring).intersection(
            _half(pl[0], pl[1], pl[2] - GAP - (base + 0.0005)))
        for p in _polys(part):
            fill.append((p, pl))
    if fill:
        def ftop(pl, x, y):
            return _z(pl, x, y) - GAP

        def fbot(_pl, _x, _y):
            return base - 0.001
        out += _flat_faces(fill, ftop, True, wall_color)
        out += _flat_faces(fill, fbot, False, wall_color)
        out += _sides(fill, ftop, fbot, wall_color)
        out += _steps(fill, ftop, fbot, wall_color)
    # back to the world
    def W(p):
        x, y, z = p
        return (o_[0] + u[0] * x + v[0] * y, o_[1] + u[1] * x + v[1] * y, z)
    return [{"loop": [W(p) for p in f["loop"]],
             "holes": [[W(p) for p in h] for h in f["holes"]],
             "color": f["color"]} for f in out]


def gable_sides(r: dict) -> set:
    """The indexes of the stored corners' sides (i → i+1) that are GABLE
    ends of a gable L (their overhang is «go») — empty for a hip one."""
    if r.get("kind") != "gable":
        return set()
    fr = frame(r["corners"])
    if fr is None:
        return set()
    loc = fr[3]
    ws = wings(loc, "gable", r.get("main", "long"))
    out = set()
    for i in range(len(loc)):
        p, q = loc[i], loc[(i + 1) % len(loc)]
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        for w in ws or ():
            xa, xb, ya, yb = w["rect"]
            for s in w["gables"]:
                if s == w.get("cut"):
                    continue
                if s in ("xa", "xb") and abs(mx - (xa if s == "xa" else xb)) \
                        < 1e-6 and ya - 1e-6 <= my <= yb + 1e-6:
                    out.add(i)
                if s in ("ya", "yb") and abs(my - (ya if s == "ya" else yb)) \
                        < 1e-6 and xa - 1e-6 <= mx <= xb + 1e-6:
                    out.add(i)
    return out


def plan_lines(r: dict):
    """The hips, valleys and ridges of an L roof in plan (world), for the
    Plan view / sheets: [((x, y), (x, y))] — the edges where two of its
    faces meet."""
    fr = frame(r["corners"])
    if fr is None:
        return []
    o_, u, v, loc = fr
    ang = math.radians(float(r.get("slope", 30.0)))
    ws = wings(loc, r.get("kind", "hip"), r.get("main", "long"))
    if not ws:
        return []
    from shapely.ops import linemerge, unary_union
    env = envelope([wing_faces(w, 0.0, math.tan(ang), 0.0, 0.0)
                    for w in ws])
    if not env:
        return []
    U = unary_union([p.buffer(1e-9, join_style=2) for p, _ in env])
    inner = unary_union([p.boundary for p, _ in env]).difference(
        U.boundary.buffer(1e-4))
    try:
        inner = linemerge(inner)
    except Exception:  # noqa: BLE001 — as it is
        pass
    out = []
    for seg in getattr(inner, "geoms", [inner]):
        if seg.geom_type != "LineString" or seg.length < 0.01:
            continue
        cs = list(seg.coords)
        for a, b in zip(cs, cs[1:]):
            if math.dist(a, b) < 0.01:
                continue
            out.append(((o_[0] + u[0] * a[0] + v[0] * a[1],
                         o_[1] + u[1] * a[0] + v[1] * a[1]),
                        (o_[0] + u[0] * b[0] + v[0] * b[1],
                         o_[1] + u[1] * b[0] + v[1] * b[1])))
    return out
