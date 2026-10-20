"""PITCHED ROOFS ON ANY PLAN — hip and gable over a T, a U, an oblique or
irregular outline (lot 0.12.0, 2026-10-18; the L stays roof_l.py's).

The roof is a WEIGHTED STRAIGHT SKELETON: every side of the outline
moves inward at the speed of its slope (cot α; a gable end does not move),
and where the moving sides meet the hips, valleys and ridges are born —
the way a roof is drawn by hand. The skeleton, the face walk and the
gable choice are adapted from Pesi's «Roof Tiles» extension for IngeTrazo
(https://github.com/PESI3D/ingetrazo-roof-tiles, roof_tile_tool.py,
GPL-3.0-or-later, © 2026 Pesi, pesi3d.de) — thank you, Pesi.

Its faces are the roof's UNDERSIDE (through the walls' outer top edge at
``base``, as every ArchXQ roof); from there it is built as roof_l's L: the
slab over them, the eaves' fascias and the verges round the outline, the
outside walls filled up to the underside (gable triangles, the eave walls'
wedges). Pure: no Qt.

A roof record (structure.py): kind "gable" | "hip", "corners" = the walls'
OUTER outline as stored (cleaned: counter-clockwise, no repeats, no points
on a straight run); "ridge": "long" | "short" turns a gable's ends to the
other sides.
"""
from __future__ import annotations

import math

#: no more corners than this (a wall outline traced from a messy DXF)
MAX_CORNERS = 60


class SkelError(Exception):
    """A roof the outline and its settings cannot make."""


# ---- the outline ----------------------------------------------------------------------------
def _area(pts) -> float:
    s = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return 0.5 * s


def _span(pts) -> float:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return max(max(xs) - min(xs), max(ys) - min(ys))


def clean_outline(pts, tol: float = 1e-4) -> list:
    """Counter-clockwise, without repeated or collinear points."""
    pts = [tuple(map(float, p[:2])) for p in pts]
    out = []
    for p in pts:
        if not out or math.dist(out[-1], p) > tol:
            out.append(p)
    if len(out) > 1 and math.dist(out[0], out[-1]) <= tol:
        out.pop()
    changed = True
    while changed and len(out) > 3:
        changed = False
        for i in range(len(out)):
            a, b, c = out[i - 1], out[i], out[(i + 1) % len(out)]
            cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            if abs(cr) < tol * max(math.dist(a, b), math.dist(b, c), 1e-9):
                out.pop(i)
                changed = True
                break
    if len(out) >= 3 and _area(out) < 0:
        out.reverse()
    return out


def is_rect(pts) -> bool:
    """4 corners at right angles (the old roofs' rectangle)."""
    c = clean_outline(pts)
    if len(c) != 4:
        return False
    for i in range(4):
        a, b, d = c[i - 1], c[i], c[(i + 1) % 4]
        u = (b[0] - a[0], b[1] - a[1])
        v = (d[0] - b[0], d[1] - b[1])
        lu, lv = math.hypot(*u), math.hypot(*v)
        if lu < 1e-6 or lv < 1e-6 or abs(u[0] * v[0] + u[1] * v[1]) > \
                1e-4 * lu * lv:
            return False
    return True


def ok(pts) -> bool:
    """A simple outline the skeleton can roof (not a rectangle: that one
    is structure.py's own)."""
    c = clean_outline(pts)
    if len(c) < 3 or len(c) > MAX_CORNERS or is_rect(c):
        return False
    try:
        from shapely.geometry import Polygon
        if not Polygon(c).is_valid:
            return False
    except Exception:  # noqa: BLE001 — no shapely: no check
        pass
    return abs(_area(c)) > 0.5


def _convex(pts, i) -> bool:
    a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) > 0


def auto_gables(pts, rotate: bool = False) -> set:
    """The sides that become GABLES: the building's ends (both corners
    convex) no longer than their neighbours — or, turned, the long sides
    (adapted from Roof Tiles)."""
    n = len(pts)
    L = [math.dist(pts[i], pts[(i + 1) % n]) for i in range(n)]
    out = set()
    for i in range(n):
        if not (_convex(pts, i) and _convex(pts, (i + 1) % n)):
            continue
        a, b = L[i - 1], L[(i + 1) % n]
        if not rotate and L[i] <= a + 1e-6 and L[i] <= b + 1e-6:
            out.add(i)
        if rotate and L[i] >= a - 1e-6 and L[i] >= b - 1e-6:
            out.add(i)
    if n == 4:
        return {0, 2} if (L[0] <= L[1] + 1e-9) != rotate else {1, 3}
    for i in sorted(out):                     # never two gables side by side
        if i in out and (i + 1) % n in out:
            out.discard((i + 1) % n)
    return out


def _offset(pts, dists) -> list:
    """Each side i moved OUTWARD by dists[i]; the corners where the moved
    lines meet."""
    n = len(pts)
    lines = []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        nx, ny = dy / ln, -dx / ln               # outward (right of CCW)
        d = dists[i]
        lines.append(((a[0] + nx * d, a[1] + ny * d), (dx / ln, dy / ln)))
    out = []
    for i in range(n):
        (p, d0) = lines[i - 1]
        (q, d1) = lines[i]
        cr = d0[0] * d1[1] - d0[1] * d1[0]
        if abs(cr) < 1e-9:
            out.append(q)
            continue
        wx, wy = q[0] - p[0], q[1] - p[1]
        s = (wx * d1[1] - wy * d1[0]) / cr
        out.append((p[0] + d0[0] * s, p[1] + d0[1] * s))
    return out


# ---- the weighted straight skeleton (adapted from Roof Tiles) --------------------------------
class _V:
    __slots__ = ("p0", "t0", "v", "eL", "eR", "prev", "next", "lav", "alive")

    def __init__(self, p0, t0, eL, eR):
        self.p0, self.t0, self.eL, self.eR = p0, t0, eL, eR
        self.v = (0.0, 0.0)
        self.prev = self.next = None
        self.lav = None
        self.alive = True

    def at(self, t):
        dt = t - self.t0
        return (self.p0[0] + self.v[0] * dt, self.p0[1] + self.v[1] * dt)


class _Line:
    """n·x = c + s·(t − t0) — a side's line moving inward at speed s."""
    __slots__ = ("n", "d", "c", "s", "t0")

    def __init__(self, a, b, s, t0):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        self.d = (dx / ln, dy / ln)
        self.n = (-self.d[1], self.d[0])          # inward (left of CCW)
        self.c = self.n[0] * a[0] + self.n[1] * a[1]
        self.s, self.t0 = s, t0


def _velocity(L1, L2):
    """The velocity of the meeting point of two moving lines."""
    a, b = L1.n
    c, d = L2.n
    det = a * d - b * c
    if abs(det) < 1e-9:
        if a * c + b * d > 0:                     # parallel, same side
            s = 0.5 * (L1.s + L2.s)
            return (L1.n[0] * s, L1.n[1] * s)
        return (0.0, 0.0)                         # opposite: they met
    s1, s2 = L1.s, L2.s
    return ((s1 * d - b * s2) / det, (a * s2 - c * s1) / det)


def skeleton(pts, speeds):
    """[(a3, b3, {side})] — the skeleton's segments (x, y, t) and the
    sides whose faces they bound; a retry breaks a rare near-tie."""
    last = None
    for attempt in range(4):
        try:
            return _skeleton(pts, speeds, attempt)
        except SkelError as e:
            last = e
    raise last


def _skeleton(pts, speeds, attempt=0, eps=1e-9):
    # break the ties of symmetric outlines (several events at one point at
    # one time): a deterministic shake far below a millimetre
    sc = max(_span(pts), 1e-3) * 2e-6 * (1 + 3 * attempt)
    pts = [(x + sc * math.sin(12.9898 * i + 1.3 + attempt),
            y + sc * math.sin(78.233 * i + 2.1 + 2 * attempt))
           for i, (x, y) in enumerate(pts)]
    n = len(pts)
    if _area(pts) < 0:
        raise SkelError("the outline must be counter-clockwise")
    lines = [_Line(pts[i], pts[(i + 1) % n], float(speeds[i]), 0.0)
             for i in range(n)]
    segs = [((pts[i][0], pts[i][1], 0.0),
             (pts[(i + 1) % n][0], pts[(i + 1) % n][1], 0.0), {i})
            for i in range(n)]
    verts = [_V(pts[i], 0.0, (i - 1) % n, i) for i in range(n)]
    lav = {"start": verts[0]}
    for i, v in enumerate(verts):
        v.prev, v.next = verts[i - 1], verts[(i + 1) % n]
        v.lav = lav
        v.v = _velocity(lines[v.eL], lines[v.eR])

    def arc(v, p, t):
        a = (v.p0[0], v.p0[1], v.t0)
        b = (p[0], p[1], t)
        if math.dist(a, b) > 1e-9:
            segs.append((a, b, {v.eL, v.eR}))

    def members(lv):
        out, v = [], lv["start"]
        while True:
            out.append(v)
            v = v.next
            if v is lv["start"] or len(out) > 100000:
                break
        return out

    def degenerate(lv, t):
        ms = members(lv)
        if len(ms) < 3:
            return True
        ps = [m.at(t) for m in ms]
        return abs(_area(ps)) < 1e-10 * max(1.0, _span(ps) ** 2)

    def finalize(lv, t):
        ms = members(lv)
        ps = [m.at(t) for m in ms]
        for m, p in zip(ms, ps):
            arc(m, p, t)
        for i, m in enumerate(ms):
            a, b = ps[i], ps[(i + 1) % len(ms)]
            if math.dist(a, b) > 1e-9:
                segs.append(((a[0], a[1], t), (b[0], b[1], t),
                             {m.eR, ms[(i + 1) % len(ms)].eL}))

    def reflex(v):
        d1, d2 = lines[v.eL].d, lines[v.eR].d
        return d1[0] * d2[1] - d1[1] * d2[0] < -1e-12

    now = 0.0
    active = [lav]
    guard = 0
    while active:
        guard += 1
        if guard > 20000:
            raise SkelError("no convergence")
        best = None                               # (t, kind, data)
        for lv in active:
            ms = members(lv)
            for A in ms:                          # edge events
                B = A.next
                L = lines[A.eR]
                pa = (A.p0[0] - A.v[0] * A.t0, A.p0[1] - A.v[1] * A.t0)
                pb = (B.p0[0] - B.v[0] * B.t0, B.p0[1] - B.v[1] * B.t0)
                c = (pb[0] - pa[0]) * L.d[0] + (pb[1] - pa[1]) * L.d[1]
                k = (B.v[0] - A.v[0]) * L.d[0] + (B.v[1] - A.v[1]) * L.d[1]
                if k < -1e-12:
                    t = -c / k
                    if t >= now - 1e-7:
                        t = max(t, now)
                        if best is None or t < best[0] - eps or (
                                abs(t - best[0]) <= eps and best[1] == 1):
                            best = (t, 0, (A, B))
            for V in ms:                          # split events
                if not reflex(V):
                    continue
                for X in ms:
                    Y = X.next
                    if X is V or Y is V:
                        continue
                    L = lines[X.eR]
                    q = (V.p0[0] - V.v[0] * V.t0, V.p0[1] - V.v[1] * V.t0)
                    den = L.n[0] * V.v[0] + L.n[1] * V.v[1] - L.s
                    if den > -1e-12:
                        continue
                    num = L.c - L.s * L.t0 - (L.n[0] * q[0] + L.n[1] * q[1])
                    t = num / den
                    if t < now - 1e-7:
                        continue
                    t = max(t, now)
                    if best is not None and t > best[0] + eps:
                        continue
                    P = V.at(t)
                    xa, ya = X.at(t)
                    xb, yb = Y.at(t)
                    u = (P[0] - xa) * L.d[0] + (P[1] - ya) * L.d[1]
                    ub = (xb - xa) * L.d[0] + (yb - ya) * L.d[1]
                    if ub < 1e-7 or u < 1e-7 or u > ub - 1e-7:
                        continue
                    if best is None or t < best[0] - eps:
                        best = (t, 1, (V, X, Y))
        if best is None:
            break
        t, kind, data = best
        now = t
        if kind == 0:
            A, B = data
            lv = A.lav
            P = A.at(t)
            Pb = B.at(t)
            P = ((P[0] + Pb[0]) / 2, (P[1] + Pb[1]) / 2)
            arc(A, P, t)
            arc(B, P, t)
            A.alive = B.alive = False
            if A.prev is B.next:                  # a triangle collapses
                C = A.prev
                arc(C, P, t)
                C.alive = False
                active.remove(lv)
                continue
            N = _V(P, t, A.eL, B.eR)
            N.prev, N.next = A.prev, B.next
            A.prev.next = N
            B.next.prev = N
            N.lav = lv
            N.v = _velocity(lines[N.eL], lines[N.eR])
            lv["start"] = N
            ms = members(lv)
            if len(ms) >= 3 and degenerate(lv, t):
                finalize(lv, t)
                active.remove(lv)
            elif len(ms) == 2:
                o = N.next
                po = o.at(t)
                arc(o, po, t)
                if math.dist(P, po) > 1e-9:
                    segs.append(((P[0], P[1], t), (po[0], po[1], t),
                                 {N.eL, N.eR}))
                active.remove(lv)
        else:
            V, X, Y = data
            lv = V.lav
            P = V.at(t)
            arc(V, P, t)
            V.alive = False
            V1 = _V(P, t, V.eL, X.eR)
            V2 = _V(P, t, X.eR, V.eR)
            V1.prev, V1.next = V.prev, Y
            V.prev.next = V1
            Y.prev = V1
            V2.prev, V2.next = X, V.next
            X.next = V2
            V.next.prev = V2
            active.remove(lv)
            for N in (V1, V2):
                N.v = _velocity(lines[N.eL], lines[N.eR])
                nl = {"start": N}
                ms = members(nl)
                for m in ms:
                    m.lav = nl
                if len(ms) >= 3 and degenerate(nl, t):
                    finalize(nl, t)
                elif len(ms) >= 3:
                    active.append(nl)
                elif len(ms) == 2:
                    o = N.next
                    po = o.at(t)
                    arc(o, po, t)
                    if math.dist(P, po) > 1e-9:
                        segs.append(((P[0], P[1], t), (po[0], po[1], t),
                                     {N.eL, N.eR}))
    for lv in active:
        if degenerate(lv, now):
            finalize(lv, now)
        else:
            raise SkelError("the wavefront did not close")
    return segs


def _snap(segs, tol):
    """Points closer than ``tol`` welded; segments that vanish dropped."""
    reps, grid = [], {}

    def rep(p):
        k = (int(math.floor(p[0] / tol)), int(math.floor(p[1] / tol)),
             int(math.floor(p[2] / tol)))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in grid.get((k[0] + dx, k[1] + dy, k[2] + dz), ()):
                        if math.dist(reps[j], p) <= tol:
                            return j
        reps.append(p)
        grid.setdefault(k, []).append(len(reps) - 1)
        return len(reps) - 1
    out, seen = [], {}
    for a, b, f in segs:
        ia, ib = rep(a), rep(b)
        if ia == ib:
            continue
        key = (min(ia, ib), max(ia, ib))
        if key in seen:
            seen[key][2].update(f)
            continue
        item = (reps[ia], reps[ib], set(f))
        seen[key] = item
        out.append(item)
    return out


def _walk(segs):
    adj = {}
    for i, (a, b, _f) in enumerate(segs):
        adj.setdefault(a, []).append((i, b))
        adj.setdefault(b, []).append((i, a))
    used = {0}
    a0, b0, _ = segs[0]
    loop, cur = [a0], b0
    for _ in range(len(segs) + 2):
        if cur == a0:
            return loop, used
        loop.append(cur)
        nxt = next(((i, other) for i, other in adj.get(cur, [])
                    if i not in used), None)
        if nxt is None:
            return None, used
        used.add(nxt[0])
        cur = nxt[1]
    return None, used


def side_faces(pts, speeds, tol=1e-4) -> dict:
    """side index → its face's closed 3D loops (x, y, t)."""
    segs = _snap(skeleton(pts, speeds), tol)
    out = {}
    for f in range(len(pts)):
        rest = [s for s in segs if f in s[2]]
        while rest:
            loop, used = _walk(rest)
            if not used:
                break
            if loop and len(loop) >= 3:
                out.setdefault(f, []).append(loop)
            rest = [s for i, s in enumerate(rest) if i not in used]
    return out


# ---- the roof ---------------------------------------------------------------------------------
def gables_of(r: dict, pts) -> set:
    """The sides of the cleaned outline that are gable ends (none: hip)."""
    if r.get("kind") != "gable":
        return set()
    return auto_gables(pts, r.get("ridge", "long") == "short")


def pieces(r: dict, base: float, overhang: bool = True) -> list:
    """[(Polygon, plane)] — the roof's UNDERSIDE seen from above: every
    sloped face of the skeleton with its plane z = a x + b y + c, through
    the walls' outer top edge at ``base``; [] when it can't be made."""
    from shapely.geometry import Polygon
    pts = clean_outline(r["corners"])
    if len(pts) < 3:
        return []
    n = len(pts)
    ang = math.radians(min(max(float(r.get("slope", 30.0)), 1.0), 85.0))
    tan = math.tan(ang)
    o = float(r.get("overhang", 0.0)) if overhang else 0.0
    go = float(r.get("go", o)) if overhang else 0.0
    gab = gables_of(r, pts)
    if r.get("kind") == "gable" and not gab:
        gab = set()                       # no end fits: it is hipped all round
    speeds = [0.0 if i in gab else 1.0 / tan for i in range(n)]
    out_pts = _offset(pts, [go if i in gab else o for i in range(n)])
    if _area(out_pts) <= 1e-6:
        return []
    T = o * tan                           # the eaves start this much lower
    try:
        F = side_faces(out_pts, speeds)
    except SkelError:
        return []
    got = []
    for loops in F.values():
        for lp in loops:
            p3 = [(x, y, base - T + t) for x, y, t in lp]
            nx = ny = nz = 0.0
            m = len(p3)
            for i in range(m):
                a, b = p3[i], p3[(i + 1) % m]
                nx += (a[1] - b[1]) * (a[2] + b[2])
                ny += (a[2] - b[2]) * (a[0] + b[0])
                nz += (a[0] - b[0]) * (a[1] + b[1])
            area = 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)
            if area < 1e-6 or abs(nz) < 0.04 * 2 * area:
                continue                  # a gable's vertical face
            q = p3[0]
            pl = (-nx / nz, -ny / nz, (nx * q[0] + ny * q[1] + nz * q[2]) / nz)
            poly = Polygon([(x, y) for x, y, _z in p3]).buffer(0)
            from .roof_l import _polys
            for pc in _polys(poly):
                got.append((pc, pl))
    return got


def faces(r: dict, base: float, wall_t: float, roof_color, wall_color):
    """The roof's faces (world): the slab over the skeleton's faces + the
    outside walls filled up to its underside — as roof_l.faces. [] when
    it can't be made (structure.py then falls back to a rectangle)."""
    from shapely.geometry import Polygon

    from .roof_l import GAP, _flat_faces, _half, _polys, _sides, _z
    env = pieces(r, base)
    if not env:
        return []
    ang = math.radians(float(r.get("slope", 30.0)))
    dz = float(r.get("t", 0.20)) / math.cos(ang)

    def top(pl, x, y):
        return _z(pl, x, y) + dz

    def under(pl, x, y):
        return _z(pl, x, y)
    out = _flat_faces(env, top, True, roof_color)
    out += _flat_faces(env, under, False, roof_color)
    out += _sides(env, top, under, roof_color)
    # the outside walls up to the underside: their ring (1 mm off both
    # faces), where the underside is over the walls' top
    P = Polygon(clean_outline(r["corners"]))
    ring = P.buffer(-0.001, join_style=2).difference(
        P.buffer(-(wall_t - 0.001), join_style=2))
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
    return out


def gable_sides(r: dict) -> set:
    """The stored corners' sides (i → i+1) that are gable ends."""
    return gables_of(r, clean_outline(r["corners"]))


def plan_lines(r: dict):
    """Its hips, valleys and ridges in plan: [((x, y), (x, y))] — where
    two of its faces meet (no overhang: over the walls' outline)."""
    env = pieces(r, 0.0, overhang=False)
    if not env:
        return []
    from shapely.ops import linemerge, unary_union
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
            if math.dist(a, b) >= 0.01:
                out.append(((a[0], a[1]), (b[0], b[1])))
    return out
