# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A wall with a PROFILE — its outline seen from the front (PLANO_CURVAS_E_
FORMAS.md, F2). Pure: no host, no Qt, nothing of ArchXQ — the standard
library and shapely only. Tested on its own (``tests/test_profilecut.py``).

The wall has a frame: ``p0`` (a point of its centre line, s = 0), ``u``
(unit, along it) and n = (−uy, ux), its left. A point is (s, c, z): along,
across (+ = left), up. Its PLAN is a polygon in (s, c); its ELEVATION a
region R in (s, z): the outline inside the clear span, its end SLICES
carried on past it (a corner's mitre stays level at the end's height), less
the openings. The solid is {(s, c, z): (s, c) in plan and (s, z) in R}, and
its skin is made of two kinds of faces:
- one per side of the plan (``side`` along the wall, ``end`` across it):
  R between that side's two ends, stood on it;
- one strip through the thickness per segment of R's boundary (``edge``
  from the outline, ``reveal`` from an opening): the plan between that
  segment's two ends, lifted onto it.
Every face is counter-clockwise seen from outside, its holes the other way
— as ``walls.solid`` and ``structure.wall_with_openings`` give them."""
from __future__ import annotations

import bisect
import math

from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

EPS = 1e-9             # two numbers the same
PT_TOL = 1e-7          # two points the same
AREA_MIN = 1e-8        # m² — a smaller face is dropped
ALONG_TOL = 1e-6       # a plan side this close to u runs ALONG the wall
ON_TOL = 1e-7          # a segment's middle this close to a line is ON it
PROBE = 1e-5           # m off a segment, to see what lies beside it
JOINT_TOL = 1e-6       # a long face this close to ``joint_c`` is the joint's
REACH = 1000.0         # m — how far past the span the end slices are carried


# ---- shapely, tidied ---------------------------------------------------------------
def _poly(loop) -> Polygon:
    """A loop of (s, z) as a valid polygon, whichever way it turns."""
    g = Polygon([(float(p[0]), float(p[1])) for p in loop])
    return g if g.is_valid else g.buffer(0)


def _polys(g) -> list:
    """The polygons in whatever shapely gave back (lines and points out)."""
    if g is None or g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    out = []
    for part in getattr(g, "geoms", ()):
        out += _polys(part)
    return out


def _whole(g):
    """A Polygon or a MultiPolygon of what is solid in g."""
    ps = _polys(g)
    if not ps:
        return Polygon()
    return ps[0] if len(ps) == 1 else MultiPolygon(ps)


def _lines(g) -> list:
    """The (first point, last point) of each line in g."""
    if g is None or g.is_empty:
        return []
    if g.geom_type in ("LineString", "LinearRing"):
        cs = list(g.coords)
        return [(cs[0], cs[-1])]
    out = []
    for part in getattr(g, "geoms", ()):
        out += _lines(part)
    return out


def _joined(spans: list) -> list:
    """Intervals sorted, the ones touching made one, the empty ones out."""
    out = []
    for lo, hi in sorted(spans):
        if out and lo <= out[-1][1] + EPS:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return [(lo, hi) for lo, hi in out if hi - lo > EPS]


def _rings_of(g) -> list:
    """A polygon's rings as open lists of points, the outer one first."""
    return [list(r.coords)[:-1] for r in [g.exterior] + list(g.interiors)]


# ---- the region R ------------------------------------------------------------------
def _slice(P, s: float) -> list:
    """The z intervals of the CLOSED outline on the line s (a side standing
    on that very line is part of it)."""
    zlo, zhi = P.bounds[1], P.bounds[3]
    got = P.intersection(LineString([(s, zlo - 1.0), (s, zhi + 1.0)]))
    return _joined([(min(a[1], b[1]), max(a[1], b[1]))
                    for a, b in _lines(got)])


def _snapped(z: float, known: list) -> float:
    """z, or the value of ``known`` it is — one number for one height."""
    for k in known:
        if abs(k - z) <= EPS:
            return k
    return z


def _base(outline, span):
    """R before the openings: the outline inside the span and, past each
    end, that end's slice carried on."""
    sa, sb = float(span[0]), float(span[1])
    P = _poly(outline)
    if P.is_empty:
        return Polygon()
    zlo, zhi = P.bounds[1], P.bounds[3]
    core = _polys(P.intersection(box(sa, zlo - 1.0, sb, zhi + 1.0)))
    parts = list(core)
    for s, far in ((sa, sa - REACH), (sb, sb + REACH)):
        known = [p[1] for g in core for r in _rings_of(g) for p in r
                 if abs(p[0] - s) <= EPS]
        for z0, z1 in _slice(P, s):
            parts.append(box(min(s, far), _snapped(z0, known),
                             max(s, far), _snapped(z1, known)))
    return _whole(unary_union(parts)) if parts else Polygon()


def _less(base, cuts: list):
    """The region with the openings taken out."""
    if not cuts or base.is_empty:
        return _whole(base)
    return _whole(base.difference(unary_union(cuts)))


def region(outline, span, holes=()):
    """R: the wall's elevation region — the outline inside the clear span,
    its end SLICES carried on past it, less the holes."""
    return _less(_base(outline, span), [_poly(h) for h in holes])


# ---- reading R ---------------------------------------------------------------------
def spans_at(outline, span, z, holes=(), lo=None, hi=None) -> list:
    """[(s0, s1), …] sorted: where the level line at height z crosses R
    (clipped to lo..hi when given). Touching at one point: nothing."""
    lo = float(span[0]) if lo is None else float(lo)
    hi = float(span[1]) if hi is None else float(hi)
    if hi - lo <= EPS:
        return []
    R = region(outline, span, holes)
    got = R.intersection(LineString([(lo, float(z)), (hi, float(z))]))
    return _joined([(min(a[0], b[0]), max(a[0], b[0]))
                    for a, b in _lines(got)])


def room_above(outline, span, s0, s1, z, holes=()) -> float:
    """The largest h with the box [s0, s1] × [z, z + h] inside R (0.0 when
    the bottom edge itself is not inside R). Openings use it to fit."""
    s0, s1, z = float(s0), float(s1), float(z)
    R = region(outline, span, holes)
    if s1 - s0 <= EPS or R.is_empty:
        return 0.0
    if not R.covers(LineString([(s0, z), (s1, z)])):
        return 0.0
    top = R.bounds[3]
    if top - z <= EPS:
        return 0.0
    free = box(s0, z, s1, top + 1.0).difference(R)
    stops = [g.bounds[1] for g in _polys(free) if g.area > AREA_MIN]
    return max(0.0, (min(stops) if stops else top) - z)


# ---- the frame, the plan -----------------------------------------------------------
class _Frame:
    """The wall's own axes: (x, y) ↔ (s, c)."""

    def __init__(self, p0, u):
        L = math.hypot(u[0], u[1]) or 1.0
        self.x, self.y = float(p0[0]), float(p0[1])
        self.ux, self.uy = u[0] / L, u[1] / L

    def sc(self, p) -> tuple:
        dx, dy = p[0] - self.x, p[1] - self.y
        return (dx * self.ux + dy * self.uy, dy * self.ux - dx * self.uy)

    def xyz(self, q) -> tuple:
        s, c, z = q
        return (self.x + s * self.ux - c * self.uy,
                self.y + s * self.uy + c * self.ux, z)


def _tidy(ring: list) -> list:
    """A ring without its repeated points (the last against the first too)."""
    out = []
    for p in ring:
        if not out or math.dist(p, out[-1]) > PT_TOL:
            out.append(p)
    while len(out) > 1 and math.dist(out[0], out[-1]) <= PT_TOL:
        out.pop()
    return out


def _area2(ring: list) -> float:
    return sum(p[0] * q[1] - q[0] * p[1]
               for p, q in zip(ring, ring[1:] + ring[:1])) / 2.0


def _plan_sc(frame: _Frame, plan) -> list:
    """The plan in (s, c), counter-clockwise, its s values one number each
    (a square end: exactly one s)."""
    pts = _tidy([frame.sc(p) for p in plan])
    if len(pts) < 3 or abs(_area2(pts)) < AREA_MIN:
        return []
    if _area2(pts) < 0:
        pts.reverse()
    keys = []
    for s in sorted(p[0] for p in pts):
        if not keys or s - keys[-1] > EPS:
            keys.append(s)
    return [(_snap(p[0], keys), p[1]) for p in pts]


def _snap(s: float, keys: list) -> float:
    """s, or the plan's own s it stands on."""
    i = bisect.bisect_left(keys, s)
    for k in keys[max(0, i - 1):i + 1]:
        if abs(k - s) <= EPS:
            return k
    return s


class _Part:
    """A piece of the plan the strips are cut from: its polygon, its rings,
    its reach along the wall and across it, and the side of ``split_c`` it
    lies on (None: not split)."""

    def __init__(self, poly, rings, mark=None):
        self.poly, self.rings, self.mark = poly, rings, mark
        self.s0, self.c0, self.s1, self.c1 = poly.bounds


def _parts(pts: list, split_c) -> list:
    """The plan whole, or cut in two at ``split_c`` (−1: c under it)."""
    Q = Polygon(pts)
    if split_c is None:
        return [_Part(Q, [pts])]
    c0, c1 = Q.bounds[1], Q.bounds[3]
    if split_c >= c1 - EPS:
        return [_Part(Q, [pts], -1)]
    if split_c <= c0 + EPS:
        return [_Part(Q, [pts], 1)]
    s0, s1 = Q.bounds[0] - 1.0, Q.bounds[2] + 1.0
    out = []
    for mark, half in ((-1, box(s0, c0 - 1.0, s1, split_c)),
                       (1, box(s0, split_c, s1, c1 + 1.0))):
        for g in _polys(Q.intersection(half)):
            if g.area >= AREA_MIN:
                out.append(_Part(g, _rings_of(orient(g, 1.0)), mark))
    return out


# ---- cutting along one line --------------------------------------------------------
def _cuts(rings: list, x: float, before: bool) -> list:
    """The intervals of the rings' inside on the upright line a hair BEFORE
    x (or after it) — even–odd, so a side standing on x itself counts only
    from the side its inside is on."""
    ys = []
    for ring in rings:
        for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
            a = x0 < x if before else x0 <= x
            b = x1 < x if before else x1 <= x
            if a != b:
                ys.append(y0 + (y1 - y0) * (x - x0) / (x1 - x0))
    ys.sort()
    return [(ys[i], ys[i + 1]) for i in range(0, len(ys) - 1, 2)
            if ys[i + 1] - ys[i] > EPS]


def _both(a: list, b: list) -> list:
    """What two lists of intervals share."""
    out = []
    for lo0, hi0 in a:
        for lo1, hi1 in b:
            lo, hi = max(lo0, lo1), min(hi0, hi1)
            if hi - lo > EPS:
                out.append((lo, hi))
    return out


def _band(part: _Part, lo: float, hi: float) -> list:
    """The part between s = lo and s = hi: a list of polygons, each its
    rings (the outer first)."""
    if hi <= part.s0 + EPS or lo >= part.s1 - EPS:
        return []
    if lo <= part.s0 + EPS and hi >= part.s1 - EPS:
        return [part.rings]
    cut = part.poly.intersection(box(lo, part.c0 - 1.0, hi, part.c1 + 1.0))
    return [_rings_of(orient(g, 1.0)) for g in _polys(cut)]


# ---- R's boundary, segment by segment ----------------------------------------------
def _region_rings(R, keys: list) -> list:
    """R's rings — its inside on the LEFT of each — their s values the
    plan's own where they stand on them."""
    out = []
    for g in _polys(R):
        for ring in _rings_of(orient(g, 1.0)):
            ring = _tidy([(_snap(p[0], keys), p[1]) for p in ring])
            if len(ring) >= 3:
                out.append(ring)
    return out


def _in_box(b, p, tol: float) -> bool:
    return b[0] - tol <= p[0] <= b[2] + tol and b[1] - tol <= p[1] <= b[3] + tol


def _tag(a, b, cuts: list, lines: list) -> tuple:
    """What a boundary segment came from, by where it lies (never by the
    order of shapely's rings): ("reveal", opening k, None) on an opening's
    outline with that opening beside it; else ("edge", None, arc k | None)."""
    mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    L = math.dist(a, b)
    out = ((b[1] - a[1]) / L, (a[0] - b[0]) / L)     # its right: off R
    beside = Point(mid[0] + out[0] * PROBE, mid[1] + out[1] * PROBE)
    for k, (poly, rim, bounds) in enumerate(cuts):
        if _in_box(bounds, mid, ON_TOL) \
                and rim.distance(Point(mid)) <= ON_TOL \
                and poly.contains(beside):
            return ("reveal", k, None)
    for k, (line, bounds) in enumerate(lines):
        if _in_box(bounds, mid, ON_TOL) \
                and line.distance(Point(mid)) <= ON_TOL \
                and line.distance(Point(a)) <= ON_TOL \
                and line.distance(Point(b)) <= ON_TOL:
            return ("edge", None, k)
    return ("edge", None, None)


def _runs_on(f: tuple, g: tuple) -> bool:
    """g goes on from f in one straight line, and came from the same thing
    (an arc's steps are never joined)."""
    if f[2:] != g[2:] or f[4] is not None:
        return False
    a, b, c = f[0], f[1], g[1]
    L = math.dist(a, c)
    if L <= PT_TOL:
        return False
    off = ((c[0] - a[0]) * (b[1] - a[1]) - (c[1] - a[1]) * (b[0] - a[0])) / L
    on = (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1])
    return abs(off) <= EPS and on > 0


def _merged(segs: list) -> list:
    """A ring's segments, the ones running on in a line made one (the top
    of a wall and of its corner piece: one strip, no seam)."""
    n = len(segs)
    start = next((i for i in range(n) if not _runs_on(segs[i - 1], segs[i])),
                 0)
    out = []
    for k in range(n):
        g = segs[(start + k) % n]
        if out and _runs_on(out[-1], g):
            out[-1] = (out[-1][0], g[1]) + out[-1][2:]
        else:
            out.append(g)
    return out


def _segments(rings: list, cuts: list, arcs) -> list:
    """Every segment of R's boundary: (a, b, part, opening, arc)."""
    marked = [(g, g.boundary, g.bounds) for g in cuts]
    lines = []
    for arc in arcs or ():
        pts = [(float(p[0]), float(p[1])) for p in arc]
        if len(pts) >= 2:
            line = LineString(pts)
            lines.append((line, line.bounds))
        else:                                  # (keeps the arcs' indexes)
            lines.append((LineString(), (0.0, 0.0, -1.0, -1.0)))
    out = []
    for ring in rings:
        out += _merged([(a, b) + _tag(a, b, marked, lines)
                        for a, b in zip(ring, ring[1:] + ring[:1])])
    return out


# ---- the faces ---------------------------------------------------------------------
def _area_vec(loop: list) -> tuple:
    nx = ny = nz = 0.0
    for a, b in zip(loop, loop[1:] + loop[:1]):
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return (nx / 2.0, ny / 2.0, nz / 2.0)


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _face(frame: _Frame, rings: list, out: tuple, part: str,
          marks: dict | None = None):
    """One face from its rings in (s, c, z), the outer first: turned so its
    normal is ``out``, its holes the other way; None when there is none
    (too small)."""
    loop = _tidy(rings[0])
    if len(loop) < 3:
        return None
    holes = [h for h in (_tidy(r) for r in rings[1:]) if len(h) >= 3]
    vec = _area_vec(loop)
    area = math.sqrt(_dot(vec, vec)) - sum(
        math.sqrt(_dot(v, v)) for v in (_area_vec(h) for h in holes))
    if area < AREA_MIN:
        return None
    if _dot(vec, out) < 0:
        loop.reverse()
    for h in holes:
        if _dot(_area_vec(h), out) > 0:
            h.reverse()
    face = {"loop": [frame.xyz(p) for p in loop],
            "holes": [[frame.xyz(p) for p in h] for h in holes],
            "part": part}
    face.update(marks or {})
    return face


def _stood(p, q):
    """(s, z) → (s, c, z) on the plan side p → q (its ends exactly its own)."""
    ds, dc = q[0] - p[0], q[1] - p[1]

    def lift(sz):
        s, z = sz[0], sz[1]
        if abs(s - p[0]) <= EPS:
            return (p[0], p[1], z)
        if abs(s - q[0]) <= EPS:
            return (q[0], q[1], z)
        return (s, p[1] + dc * (s - p[0]) / ds, z)
    return lift


def _lifted(a, b):
    """(s, c) → (s, c, z) on the boundary segment a → b (not upright)."""
    k = (b[1] - a[1]) / (b[0] - a[0])

    def lift(sc):
        s, c = sc[0], sc[1]
        if abs(s - a[0]) <= EPS:
            return (a[0], c, a[1])
        if abs(s - b[0]) <= EPS:
            return (b[0], c, b[1])
        return (s, c, a[1] + k * (s - a[0]))
    return lift


def _joint_edges(frame: _Frame, g, lift, rim) -> list:
    """The face's edges lying on the widened openings' outline."""
    out = []
    for ring in [g.exterior] + list(g.interiors):
        cs = list(ring.coords)
        for a, b in zip(cs, cs[1:]):
            mid = Point((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            if rim.distance(mid) < JOINT_TOL:
                out.append((frame.xyz(lift(a)), frame.xyz(lift(b))))
    return out


def _end_square(frame: _Frame, p, q, rings: list) -> list:
    """A square end (one s): the slice of R just INSIDE it, as rectangles."""
    dc = q[1] - p[1]
    out = (1.0 if dc > 0 else -1.0, 0.0, 0.0)
    faces = []
    for z0, z1 in _cuts(rings, p[0], dc > 0):
        faces.append(_face(frame, [[(p[0], p[1], z0), (q[0], q[1], z0),
                                    (q[0], q[1], z1), (p[0], p[1], z1)]],
                           out, "end"))
    return faces


def _plan_faces(frame: _Frame, pts: list, R, rings: list, joint) -> list:
    """The faces standing on the plan's sides: ``side`` along the wall,
    ``end`` across it. ``joint``: None or (c, R with the openings widened,
    their outline)."""
    faces = []
    zlo, zhi = R.bounds[1] - 1.0, R.bounds[3] + 1.0
    for p, q in zip(pts, pts[1:] + pts[:1]):
        ds, dc = q[0] - p[0], q[1] - p[1]
        L = math.hypot(ds, dc)
        if abs(ds) <= EPS:
            faces += _end_square(frame, p, q, rings)
            continue
        along = abs(dc) / L < ALONG_TOL
        on_joint = along and joint is not None \
            and abs(p[1] - joint[0]) < JOINT_TOL \
            and abs(q[1] - joint[0]) < JOINT_TOL
        src = joint[1] if on_joint else R
        lift = _stood(p, q)
        out = (dc / L, -ds / L, 0.0)
        band = box(min(p[0], q[0]), zlo, max(p[0], q[0]), zhi)
        for g in _polys(src.intersection(band)):
            g = orient(g, 1.0)
            face = _face(frame, [[lift(c) for c in r] for r in _rings_of(g)],
                         out, "side" if along else "end")
            if face is not None and on_joint:
                face["joint"] = _joint_edges(frame, g, lift, joint[2])
            faces.append(face)
    return [f for f in faces if f is not None]


def _strip_marks(seg: tuple, part: _Part) -> dict:
    marks = {}
    if seg[2] == "reveal":
        marks["hole"] = seg[3]
        if part.mark is not None:
            marks["reveal"] = part.mark
    elif seg[4] is not None:
        marks["curve"] = seg[4]
    return marks


def _strip(frame: _Frame, seg: tuple, part: _Part) -> list:
    """One boundary segment's faces through one part of the plan."""
    a, b = seg[0], seg[1]
    ds, dz = b[0] - a[0], b[1] - a[1]
    L = math.hypot(ds, dz)
    out = (dz / L, 0.0, -ds / L)                 # R is on the segment's left
    marks = _strip_marks(seg, part)
    faces = []
    if abs(ds) <= EPS:
        # upright: where the plan runs on BOTH sides of that s (a square
        # end standing there is the end's own face, never a strip)
        s = a[0]
        for c0, c1 in _both(_cuts(part.rings, s, True),
                            _cuts(part.rings, s, False)):
            faces.append(_face(frame, [[(s, c0, a[1]), (s, c1, a[1]),
                                        (s, c1, b[1]), (s, c0, b[1])]],
                               out, seg[2], marks))
        return faces
    lift = _lifted(a, b)
    for rings in _band(part, min(a[0], b[0]), max(a[0], b[0])):
        faces.append(_face(frame, [[lift(c) for c in r] for r in rings],
                           out, seg[2], marks))
    return faces


def _strip_faces(frame: _Frame, pts: list, segs: list, split_c) -> list:
    """The strips through the thickness: ``edge`` whole, ``reveal`` cut at
    ``split_c``. A segment off the plan gives none."""
    whole = _parts(pts, None)
    halves = whole if split_c is None else _parts(pts, float(split_c))
    faces = []
    for seg in segs:
        for part in (halves if seg[2] == "reveal" else whole):
            faces += _strip(frame, seg, part)
    return [f for f in faces if f is not None]


def _joint(base, cuts: list, joint_c, joint_gap: float):
    """(c, R with the openings cut ``joint_gap`` wider, their outline) —
    None without a joint or without openings."""
    if joint_c is None or not cuts:
        return None
    wide = unary_union(cuts).buffer(joint_gap, join_style="mitre")
    return (float(joint_c), _whole(base.difference(wide)), wide.boundary)


def wall_faces(plan, p0, u, outline, span, holes=(), arcs=(),
               split_c=None, joint_c=None, joint_gap=0.001) -> list:
    """The closed solid {(s, c, z): (s, c) in plan and (s, z) in R}, as faces."""
    frame = _Frame(p0, u)
    pts = _plan_sc(frame, plan)
    if not pts:
        return []
    base = _base(outline, span)
    cuts = [_poly(h) for h in holes]
    R = _less(base, cuts)
    if R.is_empty:
        return []
    rings = _region_rings(R, sorted({p[0] for p in pts}))
    faces = _plan_faces(frame, pts, R, rings,
                        _joint(base, cuts, joint_c, joint_gap))
    return faces + _strip_faces(frame, pts, _segments(rings, cuts, arcs),
                                split_c)


__all__ = ["region", "wall_faces", "spans_at", "room_above"]
