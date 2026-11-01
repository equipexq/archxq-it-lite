"""ArchXQ walls — the ENGINE. Pure: no IngeTrazo, no Qt.

It takes the walls of one level and gives back each wall's PLAN, already
joined to its neighbours (and, from the plan, the faces of its solid).
Tested on its own (``tests/test_walls.py``) before any wall is drawn.

A WALL (as stored in the document):
    {"id", "name", "kind": "line" | "arc" | "circle",
     "a": [x, y], "b": [x, y]            (line, arc: the line DRAWN)
     "m": [x, y]                          (arc: a point on the curve)
     "c": [x, y], "r": R                  (circle: centre, drawn radius)
     "t": thickness, "align": "outside" | "centre" | "inside",
     "side": +1 | -1, …}
``side`` says where the INSIDE is, looking along the drawing (a → b):
+1 = on the left, −1 = on the right (a closed figure knows; an open run
takes the cursor's side). ``align`` puts the outer face, the centre, or
the inner face ON the line drawn — so changing the thickness never moves
the face that was drawn. A curve is kept as a curve (3 points), never as
segments: the faces of a curved wall are true circles, and they become
segments only when the solid is made.

THE JOINS (ported from the Blender ArchXQ, where they were proven, and
grown to curves). Wall ends meet at a NODE, grouped by the line DRAWN
(two walls aligned by their outer face meet even though their centres
don't). Every end reaches its node with a direction (on a curve, its
tangent) and two faces (a line or a circle); a corner is where two faces
cross — line×line, line×circle, circle×circle:
- 1 end: cut square.
- 2 ends (L): mitred; a very sharp angle is cut square instead.
- 3+ ends with two running opposite (T, X): those two pass through, the
  others (stems) are cut on the face of the one passing — straight or
  curved.
- 3+ ends and no pair running through (Y): they overlap in the middle.
- An end on the BODY of another wall (a partition stopping against the
  outer wall): the outer wall is not split — it joins that node as a
  "ghost" passing through, and the partition is cut on its face.
- Two walls CROSSING mid-way: the thicker passes (same thickness: the
  one drawn first); the other is cut on its faces, in two pieces.
"""
from __future__ import annotations

import math

JOIN_TOL = 0.02          # m: drawn ends this close meet at one node
BODY_TOL = 0.02          # m: an end this far off another wall's body still
                         #    stops against it
SNAP_TOL = 0.03          # m: an end this short of a wall is pulled onto it
MITER_LIMIT = 4.0        # × thickness: past this a mitre is cut square
THROUGH_TOL = math.radians(25.0)   # off straight, still running THROUGH
CONTINUE_TOL = math.radians(10.0)  # off straight, still CONTINUING a wall
CHORD = 0.002            # m: a curve becomes segments this close to it
MAX_STEP = math.radians(10.0)      # …and never coarser than this
ALIGN = {"outside": 1.0, "centre": 0.0, "inside": -1.0}
EPS = 1e-9
#: LAYERS (0.15.0, his plan approved 2026-10-20 — MAQUETAS/
#: parede_camadas_tipos_v1.html): a wall may carry ``"layers"``, outside →
#: inside, ONE «core» and finishes on either side (plaster, cladding,
#: insulation, board); ``t`` stays the whole thickness (their sum). None =
#: one core = the wall of always.
MAX_LAYERS = 6
LAYER_T = (0.005, 2.0)


# ---- small vector kit --------------------------------------------------------------
def _sub(p, q):
    return (p[0] - q[0], p[1] - q[1])


def _add(p, q):
    return (p[0] + q[0], p[1] + q[1])


def _mul(p, s):
    return (p[0] * s, p[1] * s)


def _dot(p, q):
    return p[0] * q[0] + p[1] * q[1]


def _cross(p, q):
    return p[0] * q[1] - p[1] * q[0]


def _len(p):
    return math.hypot(p[0], p[1])


def _unit(p):
    n = _len(p)
    return (p[0] / n, p[1] / n) if n > EPS else (0.0, 0.0)


def _left(u):
    return (-u[1], u[0])


def _dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _wrap(a):
    """An angle into (−π, π]."""
    return (a + math.pi) % (2 * math.pi) - math.pi


# ---- a wall's geometry: a straight or a curved piece -----------------------------
class Seg:
    """A straight piece (p0 → p1) or a circular arc (centre C, radius r,
    from angle th0 sweeping ``sweep`` — positive = counter-clockwise)."""

    def __init__(self, kind, **k):
        self.kind = kind
        if kind == "line":
            self.p0, self.p1 = tuple(k["p0"]), tuple(k["p1"])
            d = _sub(self.p1, self.p0)
            self.L = _len(d)
            self.u = _unit(d)
        else:
            self.C = tuple(k["C"])
            self.r = float(k["r"])
            self.th0 = float(k["th0"])
            self.sweep = float(k["sweep"])
            self.d = 1.0 if self.sweep >= 0 else -1.0
            self.L = abs(self.sweep) * self.r

    # -- along it ---------------------------------------------------------------
    def at(self, f: float):
        if self.kind == "line":
            return _add(self.p0, _mul(_sub(self.p1, self.p0), f))
        th = self.th0 + self.sweep * f
        return (self.C[0] + self.r * math.cos(th),
                self.C[1] + self.r * math.sin(th))

    def tangent(self, f: float):
        """The way it runs (a → b) at fraction f."""
        if self.kind == "line":
            return self.u
        th = self.th0 + self.sweep * f
        return (-math.sin(th) * self.d, math.cos(th) * self.d)

    def sub(self, f0: float, f1: float) -> "Seg":
        if self.kind == "line":
            return Seg("line", p0=self.at(f0), p1=self.at(f1))
        return Seg("arc", C=self.C, r=self.r, th0=self.th0 + self.sweep * f0,
                   sweep=self.sweep * (f1 - f0))

    def offset(self, o: float) -> "Seg":
        """The same piece moved ``o`` to its left (a curve: in radius)."""
        if self.kind == "line":
            n = _mul(_left(self.u), o)
            return Seg("line", p0=_add(self.p0, n), p1=_add(self.p1, n))
        # on a counter-clockwise arc the left is the centre
        return Seg("arc", C=self.C, r=self.r - self.d * o, th0=self.th0,
                   sweep=self.sweep)

    def project(self, p):
        """(fraction along, signed distance to its left) of point p."""
        if self.kind == "line":
            v = _sub(p, self.p0)
            f = _dot(v, self.u) / self.L if self.L > EPS else 0.0
            return f, _cross(self.u, v)
        v = _sub(p, self.C)
        th = math.atan2(v[1], v[0])
        rel = _wrap(th - self.th0) * self.d
        if rel < -1e-9:
            rel += 2 * math.pi
        f = rel / abs(self.sweep) if abs(self.sweep) > EPS else 0.0
        if f > 1.0:              # past the end: the nearer end's side
            back = (2 * math.pi - rel) / abs(self.sweep)
            if back < f - 1.0:
                f = -back
        return f, (self.r - _len(v)) * self.d

    def face(self, side: float, t: float):
        """The face ``side`` (+1 left, −1 right) of a wall of thickness t
        on this centre: ("line", point, dir) | ("circle", C, R)."""
        s = self.offset(side * t / 2.0)
        if s.kind == "line":
            return ("line", s.p0, s.u)
        return ("circle", s.C, s.r)


def _circle3(a, m, b):
    """The circle through three points, or None (in a line)."""
    ax, ay = a
    bx, by = m
    cx, cy = b
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay)
          + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx)
          + (cx * cx + cy * cy) * (bx - ax)) / d
    return (ux, uy), _dist((ux, uy), a)


def drawn(w: dict) -> Seg:
    """The line DRAWN (what the user clicked)."""
    kind = w.get("kind", "line")
    if kind == "circle":
        return Seg("arc", C=w["c"], r=w["r"], th0=0.0, sweep=2 * math.pi)
    a, b = tuple(w["a"]), tuple(w["b"])
    if kind == "arc":
        got = _circle3(a, tuple(w["m"]), b)
        if got is not None:
            C, r = got
            th_a = math.atan2(a[1] - C[1], a[0] - C[0])
            th_b = math.atan2(b[1] - C[1], b[0] - C[0])
            ccw = _cross(_sub(w["m"], a), _sub(b, w["m"])) > 0
            if ccw:
                sweep = (th_b - th_a) % (2 * math.pi)
            else:
                sweep = -((th_a - th_b) % (2 * math.pi))
            return Seg("arc", C=C, r=r, th0=th_a, sweep=sweep)
    return Seg("line", p0=a, p1=b)


def centre(w: dict) -> Seg:
    """The wall's centre: the line drawn, moved by the alignment («core_out»
    — a wall with layers: the line drawn is its CORE's outer face, the
    outer finishes grow outside it)."""
    side = 1.0 if w.get("kind") == "circle" else float(w.get("side", 1))
    if w.get("align") == "core_out":
        o = side * (w["t"] / 2.0 - outer_finish(w))
    else:
        o = ALIGN.get(w.get("align", "centre"), 0.0) * side * w["t"] / 2.0
    return drawn(w).offset(o)


# ---- its openings on a raised wall ---------------------------------------------
def opening_lift(w: dict | None) -> float:
    """How far a wall's doors and windows go up with it: its Base offset
    when positive (a raised room — László #65, 2026-10-29: the doors stayed
    on the level's floor, buried); 0 for a base of 0 or under (a footing, a
    wall going down through its slab)."""
    try:
        return max(float((w or {}).get("base", 0.0) or 0.0), 0.0)
    except (TypeError, ValueError):
        return 0.0


def lifted(o: dict, w: dict | None) -> dict:
    """Opening ``o`` as it is built: its sill measured from the level's
    floor (its own sill + the wall's lift). Nothing stored changes; with no
    lift it is ``o`` itself — the same object, the same faces as before."""
    k = opening_lift(w)
    if k <= 0:
        return o
    # «_lift»: what of its sill is the wall's — «off the floor» (a stone
    # sill under an Opening) still reads its own sill (trim.own_sill)
    return dict(o, sill=float(o.get("sill", 0.0) or 0.0) + k, _lift=k)


# ---- its top: flat, sloped, a gable (PLANO_PAREDE_TOPO, 2026-10-31) -----------
#: ``"top"`` on a STRAIGHT wall (not a curtain wall): absent = flat, as
#: always. {"kind": "slope", "h0", "h1"} — its height at a and at b;
#: {"kind": "gable", "h0", "h1", "hp", "at"} — and a ridge ``hp`` at ``at``
#: (0…1 along a → b). Heights from the level's floor, as ``height``; «was»:
#: the height it had before (Flat gives it back). Its ``height`` is kept at
#: the highest point, so whatever reads the height alone sees its top.
TOP_KINDS = ("slope", "gable")
TOP_H = (0.05, 50.0)
TOP_AT = (0.05, 0.95)


def clean_top(raw, height="level"):
    """A wall's ``top`` as stored, or None (flat). A gable's ridge never
    under its ends (a V would not be one solid)."""
    if not isinstance(raw, dict) or raw.get("kind") not in TOP_KINDS:
        return None
    try:
        def h(v):
            return round(min(max(float(v), TOP_H[0]), TOP_H[1]), 4)
        out = {"kind": raw["kind"], "h0": h(raw["h0"]), "h1": h(raw["h1"])}
        if out["kind"] == "gable":
            out["hp"] = max(h(raw.get("hp", 0.0)), out["h0"], out["h1"])
            out["at"] = round(min(max(float(raw.get("at", 0.5)), TOP_AT[0]),
                                  TOP_AT[1]), 4)
    except (TypeError, ValueError, KeyError):
        return None
    was = raw.get("was", height)
    try:
        out["was"] = "level" if was == "level" else \
            min(max(float(was), TOP_H[0]), TOP_H[1])
    except (TypeError, ValueError):
        out["was"] = "level"
    return out


def top_of(w: dict | None) -> dict | None:
    """The wall's own top, or None: flat (as always), a curve, a curtain
    wall."""
    t = (w or {}).get("top")
    if not t or (w.get("kind", "line") != "line") or w.get("cw"):
        return None
    return t


def top_peak(top: dict) -> float:
    """Its highest point, from the level's floor."""
    return max(top["h0"], top["h1"], top.get("hp", 0.0))


def top_h(w: dict, s: float) -> float:
    """How high the wall stands (from the level's floor) at ``s`` along
    its line drawn — past its ends LEVEL at that end's height: a corner
    piece is flat, as on site, and meets the joined wall's top flush (his
    test, 2026-11-01: the slope ran on into the mitre — a step there)."""
    top = top_of(w)
    if top is None:
        return float(w["height"]) if w.get("height", "level") != "level" \
            else None
    sa, sb = top_span(w)
    s = min(max(s, sa), sb)
    return min(c + k * s for k, c in _planes(w, 0.0))


def top_span(w: dict) -> tuple:
    """Where its top's ends are along its line: its ends drawn (0, L) — or,
    in a building, its CLEAR ends (``_span``, set by structure.wall_parts
    from its plan: the inner corner of a mitre, the face of the wall it
    butts into), so the corner square stays level at the end's height."""
    L = max(drawn(w).L, EPS)
    got = w.get("_span")
    if got and got[1] - got[0] > 0.1:
        return float(got[0]), float(got[1])
    return 0.0, L


def clear_span(w: dict, pieces, own=()) -> tuple:
    """(sa, sb): along its line, where its plan's long sides BOTH still
    run at each end — past it, the corner piece (``top_span``). ``own``:
    its ends ("A" / "B") going on over their corner (a wall higher than
    the one it meets there — structure.corner_caps): its top runs to its
    plan's far end there, the slope with it."""
    seg = drawn(w)
    L, p0, u = seg.L, seg.p0, seg.u
    t = float(w.get("t", 0.2))
    lo_end, hi_end = 0.0, L
    a_in, b_in = [], []
    far = [(p[0] - p0[0]) * u[0] + (p[1] - p0[1]) * u[1]
           for pc in pieces or () for p in pc["outer"]]
    for pc in pieces or ():
        loop = pc["outer"]
        for i in range(len(loop)):
            p, q = loop[i], loop[(i + 1) % len(loop)]
            d = (q[0] - p[0], q[1] - p[1])
            n = math.hypot(*d)
            if n < 1e-9 or abs(d[0] * u[1] - d[1] * u[0]) / n > 1e-6:
                continue                  # not along it
            s1 = (p[0] - p0[0]) * u[0] + (p[1] - p0[1]) * u[1]
            s2 = (q[0] - p0[0]) * u[0] + (q[1] - p0[1]) * u[1]
            lo, hi = min(s1, s2), max(s1, s2)
            if lo < t + 1.0:              # a side reaching its first end
                a_in.append(lo)
            if hi > L - t - 1.0:          # …its last end
                b_in.append(hi)
    if len(a_in) >= 2:
        lo_end = max(a_in)
    if len(b_in) >= 2:
        hi_end = min(b_in)
    if far and "A" in own:
        lo_end = min(far)
    if far and "B" in own:
        hi_end = max(far)
    if hi_end - lo_end < 0.1:
        return 0.0, L
    return lo_end, hi_end


def top_mean(w: dict) -> float:
    """Its mean height along its line (areas, volumes)."""
    top = top_of(w)
    if top["kind"] == "slope":
        return (top["h0"] + top["h1"]) / 2
    a = top["at"]
    return a * (top["h0"] + top["hp"]) / 2 + \
        (1 - a) * (top["hp"] + top["h1"]) / 2


def top_low(w: dict, s0: float, s1: float) -> float:
    """Its lowest height between s0 and s1 (its top is never a V: at one
    of the two)."""
    return min(top_h(w, s0), top_h(w, s1))


def _planes(w: dict, z0: float) -> list:
    """The top's plane(s) as (k, c): z = z0 + c + k·s, s along the line —
    from h0 to h1 between its top's ends (``top_span``); a gable's ridge
    stays where it was drawn (``at`` of its length)."""
    top, L = top_of(w), max(drawn(w).L, EPS)
    sa, sb = top_span(w)
    h0, h1 = top["h0"], top["h1"]
    if top["kind"] == "slope":
        k = (h1 - h0) / max(sb - sa, EPS)
        return [(k, h0 - k * sa)]
    sp = min(max(top["at"] * L, sa + EPS), sb - EPS)
    k1 = (top["hp"] - h0) / max(sp - sa, EPS)
    k2 = (h1 - top["hp"]) / max(sb - sp, EPS)
    return [(k1, h0 - k1 * sa), (k2, top["hp"] - k2 * sp)]


def _zones(w: dict, z0: float) -> list:
    """The top along the line as (s from, s to, planes): before its top's
    first end level at h0, between them ``_planes``, past the last level at
    h1 (top_h) — None: open that way."""
    top = top_of(w)
    sa, sb = top_span(w)
    return [(None, sa, [(0.0, top["h0"])]), (sa, sb, _planes(w, z0)),
            (sb, None, [(0.0, top["h1"])])]


def _plane_of(loop):
    """(normal, d) of a planar 3D loop (Newell): n·p = d."""
    nx = ny = nz = 0.0
    k = len(loop)
    for i in range(k):
        a, b = loop[i], loop[(i + 1) % k]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    m = math.sqrt(nx * nx + ny * ny + nz * nz)
    if m < 1e-12:
        return None
    n = (nx / m, ny / m, nz / m)
    return n, sum(n[i] * loop[0][i] for i in range(3))


def topped(faces: list, w: dict, z0: float) -> list:
    """A wall's faces, built up to its highest point, cut under its own
    top: each face clipped by the top's plane(s) (a gable: two — under
    both), the flat lids at the top swapped for the sloped ones (the plan
    of each lid taken up onto the planes, split at the ridge). Faces
    wholly under it are kept as they are. Keeps each face's other keys
    (its colour). Past its ends (the corner pieces) the top is level at
    that end's height (``_zones``): each face is cut by the three zones and
    put back together — one face, no seam where the slope ends."""
    from shapely.geometry import Polygon
    from shapely.geometry.polygon import orient
    from shapely.ops import unary_union
    seg = drawn(w)
    p0, u = seg.p0, seg.u
    zones = _zones(w, z0)
    ends = top_span(w)
    # (built up to its highest point over its plan — past its ends too)
    zmax = max(p[2] for f in faces
               for p in (f["loop"] if isinstance(f, dict) else f))

    def S(p):
        return (p[0] - p0[0]) * u[0] + (p[1] - p0[1]) * u[1]

    def under(p):                       # ≥ 0: under its top
        return z0 + top_h(w, S(p)) - p[2]

    def checks(rings):
        """The corners, and where an edge crosses an end's line (the top
        bends there: an edge may pass over it between two corners under)."""
        out = []
        for r in rings:
            out += r
            for i in range(len(r)):
                a, b = r[i], r[(i + 1) % len(r)]
                sa, sb = S(a), S(b)
                for e in ends:
                    if (sa - e) * (sb - e) < 0:
                        t = (e - sa) / (sb - sa)
                        out.append(tuple(a[j] + (b[j] - a[j]) * t
                                         for j in range(3)))
        return out

    out, lids = [], []
    for f in faces:
        rec = f if isinstance(f, dict) else {"loop": f, "holes": []}
        loop, holes = rec["loop"], rec.get("holes") or []
        pts = checks([loop] + list(holes))
        if all(under(p) >= -1e-7 for p in pts):
            out.append(f)
            continue
        pl = _plane_of(loop)
        if pl is None:
            continue
        n, d = pl
        if n[2] > 0.999 and all(abs(p[2] - zmax) < 1e-6 for p in loop):
            lids.append(rec)            # a flat lid at the top: made anew
            continue
        if all(under(p) <= 1e-7 for p in pts):
            continue                    # wholly over it
        # clip in the face's own 2D: drop the axis it faces most
        ax = max(range(3), key=lambda i: abs(n[i]))
        keep = [i for i in range(3) if i != ax]

        def to2(p):
            return (p[keep[0]], p[keep[1]])

        def to3(q):
            p = [0.0, 0.0, 0.0]
            p[keep[0]], p[keep[1]] = q
            p[ax] = (d - n[keep[0]] * q[0] - n[keep[1]] * q[1]) / n[ax]
            return tuple(p)
        poly = Polygon([to2(p) for p in loop], [[to2(p) for p in h]
                                                for h in holes]).buffer(0)
        sign = 1.0 if Polygon([to2(p) for p in loop]).exterior.is_ccw \
            else -1.0
        pieces = []
        for lo, hi, zp in zones:
            z = _span(poly, lambda q: S(to3(q)), lo, hi)
            for k, c in zp:
                # under(p) linear in the 2D: g = A·q + B over the face
                def g(q, k=k, c=c):
                    p = to3(q)
                    return z0 + c + k * S(p) - p[2]
                z = _half(z, g)
                if z.is_empty:
                    break
            pieces += _polys(z)
        poly = unary_union(pieces) if pieces else Polygon()
        for part in _polys(poly):
            part = orient(part, sign)
            r = dict(rec, loop=[to3(q) for q in list(part.exterior.coords)
                                [:-1]],
                     holes=[[to3(q) for q in list(i.coords)[:-1]]
                            for i in part.interiors])
            out.append(r)
    for rec in lids:                    # the sloped lids
        poly = Polygon([(p[0], p[1]) for p in rec["loop"]],
                       [[(p[0], p[1]) for p in h]
                        for h in rec.get("holes") or []]).buffer(0)
        parts = []                      # (piece, its plane)
        for lo, hi, zp in zones:        # the level corner pieces apart
            mid = _span(poly, S, lo, hi)
            if len(zp) == 2:            # split at the ridge
                (k1, c1), (k2, c2) = zp
                sp = (c2 - c1) / (k1 - k2) if abs(k1 - k2) > 1e-12 \
                    else top_of(w)["at"] * max(seg.L, EPS)
                parts += [(_half(mid, lambda q: sp - S(q)), zp[0]),
                          (_half(mid, lambda q: S(q) - sp), zp[1])]
            else:
                parts.append((mid, zp[0]))
        for pp, (k, c) in parts:
            for part in _polys(pp):
                part = orient(part, 1.0)

                def up(q, k=k, c=c):
                    return (q[0], q[1], z0 + c + k * S(q))
                out.append(dict(rec, loop=[up(q) for q in list(
                    part.exterior.coords)[:-1]],
                    holes=[[up(q) for q in list(r.coords)[:-1]]
                           for r in part.interiors]))
    return out


def _polys(g) -> list:
    """The polygons of a shapely result (lines and points left out)."""
    if g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g] if g.area > 1e-9 else []
    return [p for x in getattr(g, "geoms", []) for p in _polys(x)]


def _span(poly, s_of, lo, hi):
    """The part of a 2D polygon with ``s_of(q)`` between lo and hi (None:
    open that way)."""
    if lo is not None:
        poly = _half(poly, lambda q: s_of(q) - lo)
    if hi is not None and not poly.is_empty:
        poly = _half(poly, lambda q: hi - s_of(q))
    return poly


def _half(poly, g):
    """The part of a 2D shapely polygon where the linear ``g`` ≥ 0."""
    from shapely.geometry import Polygon
    if poly.is_empty:
        return poly
    x0, y0, x1, y1 = poly.bounds
    pad = 1.0 + (x1 - x0) + (y1 - y0)
    box = [(x0 - pad, y0 - pad), (x1 + pad, y0 - pad), (x1 + pad, y1 + pad),
           (x0 - pad, y1 + pad)]
    keep = []
    for i in range(4):                  # Sutherland–Hodgman on the box
        a, b = box[i], box[(i + 1) % 4]
        ga, gb = g(a), g(b)
        if ga >= 0:
            keep.append(a)
        if (ga >= 0) != (gb >= 0):
            t = ga / (ga - gb)
            keep.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    if len(keep) < 3:
        return Polygon()
    return poly.intersection(Polygon(keep))


# ---- layers -------------------------------------------------------------------
def clean_layers(raw):
    """A wall's layers as stored: [{"id", "name", "t", "role"}] outside →
    inside, 2 to ``MAX_LAYERS``, exactly one «core» (none: the thickest is;
    two: the first) — None when that leaves one layer (a plain wall)."""
    if not isinstance(raw, list):
        return None
    out, ids = [], set()
    for k, L in enumerate(raw[:MAX_LAYERS]):
        if not isinstance(L, dict):
            continue
        try:
            t = min(max(float(L.get("t", 0.0)), LAYER_T[0]), LAYER_T[1])
        except (TypeError, ValueError):
            continue
        lid = str(L.get("id") or "")[:12] or f"l{k}"
        while lid in ids:
            lid += "x"
        ids.add(lid)
        out.append({"id": lid, "name": str(L.get("name") or "")[:40],
                    "t": round(t, 4),
                    "role": "core" if L.get("role") == "core" else "finish"})
    if len(out) < 2:
        return None
    cores = [i for i, L in enumerate(out) if L["role"] == "core"]
    keep = cores[0] if cores else max(range(len(out)),
                                      key=lambda i: out[i]["t"])
    for i, L in enumerate(out):
        L["role"] = "core" if i == keep else "finish"
    return out


def layers_of(w: dict) -> list:
    """The wall's layers, outside → inside — a plain wall: its one core."""
    got = w.get("layers")
    if isinstance(got, list) and len(got) > 1:
        return got
    return [{"id": "core", "name": "", "t": float(w["t"]), "role": "core"}]


def outer_finish(w: dict) -> float:
    """How thick the finishes OUTSIDE the core are."""
    tot = 0.0
    for L in layers_of(w):
        if L["role"] == "core":
            break
        tot += float(L["t"])
    return tot


def layer_bands(w: dict) -> list:
    """Each layer's (lo, hi) offset from the wall's centre (+ = its left),
    outside → inside — scaled to ``t`` should they not add up to it."""
    side = 1.0 if w.get("kind") == "circle" else float(w.get("side", 1))
    t = float(w["t"])
    ls = layers_of(w)
    tot = sum(float(L["t"]) for L in ls) or t
    k = t / tot
    out, at = [], -side * t / 2.0
    for L in ls:
        nxt = at + side * float(L["t"]) * k
        out.append((min(at, nxt), max(at, nxt)))
        at = nxt
    return out


def points_of(w: dict, n: int = 12) -> list:
    """Points along the line drawn (to test where a wall stands)."""
    s = drawn(w)
    k = n if s.kind == "arc" else 1
    return [s.at(i / k) for i in range(k + 1)]


def is_closed(w: dict) -> bool:
    return w.get("kind") == "circle"


def why_not(w: dict) -> str | None:
    """Why this wall can't be built (None = it can)."""
    t = float(w.get("t", 0))
    if t < 0.01:
        return "A wall needs a thickness"
    s = drawn(w)
    if is_closed(w):
        return None if s.r > t else "A round wall needs a radius larger " \
                                    "than its thickness"
    if s.L < max(t, 0.05):
        return "Too short for a wall that thick"
    if s.kind == "arc" and centre(w).r <= t / 2.0:
        return "The curve is too tight for that thickness"
    return None


# ---- crossing faces ----------------------------------------------------------------
def _meet(f1, f2):
    """Points where two faces (lines / circles) cross."""
    if f1[0] == "line" and f2[0] == "line":
        (_k, p, u), (_k2, q, v) = f1, f2
        cr = _cross(u, v)
        if abs(cr) < 1e-9:
            return []
        s = _cross(_sub(q, p), v) / cr
        return [_add(p, _mul(u, s))]
    if f1[0] == "circle" and f2[0] == "line":
        f1, f2 = f2, f1
    if f1[0] == "line":                          # line × circle
        _k, p, u = f1
        _k2, C, R = f2
        w = _sub(p, C)
        b = _dot(w, u)
        c = _dot(w, w) - R * R
        disc = b * b - c
        if disc < -1e-9:
            return []
        disc = math.sqrt(max(disc, 0.0))
        return [_add(p, _mul(u, -b - disc)), _add(p, _mul(u, -b + disc))]
    (_k, C1, R1), (_k2, C2, R2) = f1, f2         # circle × circle
    d = _dist(C1, C2)
    if d < 1e-9 or d > R1 + R2 + 1e-9 or d < abs(R1 - R2) - 1e-9:
        return []
    a = (R1 * R1 - R2 * R2 + d * d) / (2 * d)
    h = math.sqrt(max(R1 * R1 - a * a, 0.0))
    e = _unit(_sub(C2, C1))
    m = _add(C1, _mul(e, a))
    n = _left(e)
    return [_add(m, _mul(n, h)), _add(m, _mul(n, -h))]


def _nearest(points, to):
    return min(points, key=lambda q: _dist(q, to)) if points else None


# ---- pieces and ends -------------------------------------------------------------
class _Piece:
    """A wall, or the part of one between two crossings."""

    def __init__(self, wi, w, seg, f0, f1, real_a, real_b):
        self.wi, self.w = wi, w
        self.t = float(w["t"])
        self.seg = seg                     # centre, this part only
        self.f0, self.f1 = f0, f1          # its stretch of the whole wall
        self.real_a, self.real_b = real_a, real_b   # a true end (not a cut)
        self.corners = {}                  # (end "A"|"B", face ±1) → point
        # where stems are cut on this wall's faces: (face ±1, p, q) — a
        # curved face is drawn THROUGH p and q, so the stem's flat end
        # meets it exactly (not 2 mm in or out of a segment)
        self.notches = []
        # extra points on an end, between its two corners (the outline
        # runs from the corner on the LEFT of the way in to the one on the
        # right through them): the middle of a Y, a bevelled sharp corner
        self.caps = {"A": [], "B": []}


def _crossings(walls, segs):
    """Where walls cross mid-way: {wall index: [fractions to cut at]} —
    the thinner one is cut (same thickness: the later one)."""
    cuts = {}
    n = len(walls)
    for i in range(n):
        for j in range(i + 1, n):
            si, sj = segs[i], segs[j]
            if si is None or sj is None:
                continue
            fi = ("line", si.p0, si.u) if si.kind == "line" \
                else ("circle", si.C, si.r)
            fj = ("line", sj.p0, sj.u) if sj.kind == "line" \
                else ("circle", sj.C, sj.r)
            for x in _meet(fi, fj):
                ok = True
                fr = []
                for s, w in ((si, walls[i]), (sj, walls[j])):
                    f, off = s.project(x)
                    if abs(off) > 1e-6:
                        ok = False
                        break
                    margin = (max(walls[i]["t"], walls[j]["t"]) + JOIN_TOL) \
                        / max(s.L, EPS)
                    closed = is_closed(w)
                    if not closed and not margin < f < 1.0 - margin:
                        ok = False
                        break
                    fr.append(f % 1.0 if closed else f)
                if not ok:
                    continue
                ti, tj = walls[i]["t"], walls[j]["t"]
                loser = j if ti >= tj else i       # equal: the later one
                cuts.setdefault(loser, []).append(fr[0] if loser == i
                                                  else fr[1])
    return cuts


def _pieces(walls):
    segs = [centre(w) for w in walls]
    cuts = _crossings(walls, segs)
    out = []
    for i, (w, s) in enumerate(zip(walls, segs)):
        fs = sorted(set(round(f, 9) for f in cuts.get(i, [])))
        if is_closed(w):
            if not fs:
                out.append(_Piece(i, w, s, 0.0, 1.0, False, False))
                out[-1].closed = True
                continue
            # a ring cut at k points: k arcs, each between two cuts
            for k, f0 in enumerate(fs):
                f1 = fs[(k + 1) % len(fs)] + (1.0 if k + 1 == len(fs) else 0)
                out.append(_Piece(i, w, s.sub(f0, f1), f0, f1, False, False))
            continue
        bounds = [0.0] + fs + [1.0]
        for f0, f1 in zip(bounds, bounds[1:]):
            out.append(_Piece(i, w, s.sub(f0, f1), f0, f1,
                              f0 == 0.0, f1 == 1.0))
    return out


def _ends(pieces):
    """Every open end: where it gathers (the line drawn there, or the
    crossing), the centre's end point, and the way INTO the wall."""
    ends = []
    for pc in pieces:
        if getattr(pc, "closed", False):
            continue
        d = drawn(pc.w)
        for end, f, real in (("A", 0.0, pc.real_a), ("B", 1.0, pc.real_b)):
            p = pc.seg.at(f)
            u = pc.seg.tangent(f)
            if end == "B":
                u = (-u[0], -u[1])
            whole_f = pc.f0 if end == "A" else pc.f1
            c = d.at(whole_f) if real else p
            ends.append({"pc": pc, "end": end, "p": p, "u": u, "c": c,
                         "ghost": False})
    return ends


def _cluster(points, tol):
    ids, centres, counts = [], [], []
    for p in points:
        found = -1
        for k, c in enumerate(centres):
            if _dist(p, c) <= tol:
                found = k
                break
        if found < 0:
            found = len(centres)
            centres.append(p)
            counts.append(0)
        n = counts[found] + 1
        c = centres[found]
        centres[found] = (c[0] + (p[0] - c[0]) / n, c[1] + (p[1] - c[1]) / n)
        counts[found] = n
        ids.append(found)
    return ids, centres


# ---- the faces of an end, the corners ---------------------------------------------
def _face_of(e, rel):
    """The wall-face on the ``rel`` side (+1 left / −1 right) of the way
    into the wall at this end."""
    side = rel if e["end"] == "A" else -rel
    return side, e["pc"].seg.face(side, e["pc"].t)


def _put(e, rel, pt):
    if not e["ghost"]:
        side = rel if e["end"] == "A" else -rel
        e["pc"].corners[(e["end"], side)] = pt


def _square(e, out=0.0):
    """Cut flat across the end (``out`` m past it: the Y overlap)."""
    u = e["u"]
    n = _left(u)
    h = e["pc"].t / 2.0
    base = _add(e["p"], _mul(u, -out))
    _put(e, +1, _add(base, _mul(n, h)))
    _put(e, -1, _add(base, _mul(n, -h)))


def _cap(e, pts) -> None:
    if not e["ghost"]:
        e["pc"].caps[e["end"]].extend(pts)


def _gap(e1, e2) -> float:
    """The angle turning counter-clockwise from e1 to e2, in (0, 2π)."""
    a = math.atan2(e2["u"][1], e2["u"][0]) - math.atan2(e1["u"][1],
                                                        e1["u"][0])
    return a % (2 * math.pi)


def _mitre(node, e1, e2):
    """e1's left face meets e2's right face (e2 lies counter-clockwise of
    e1, so those are the two faces looking into the gap between them).
    Inside a sharp angle the corner is exact (that is where the walls part,
    however far); on the OUTSIDE of a sharp corner the long spike is
    bevelled square across, and the little triangle that leaves goes to
    one of the two walls — no gap, no overlap."""
    _s1, f1 = _face_of(e1, +1)
    _s2, f2 = _face_of(e2, -1)
    pt = _nearest(_meet(f1, f2), node)
    if pt is None:
        # parallel (a wall going on straight): each squares at its end
        n1, n2 = _left(e1["u"]), _left(e2["u"])
        _put(e1, +1, _add(e1["p"], _mul(n1, e1["pc"].t / 2.0)))
        _put(e2, -1, _add(e2["p"], _mul(n2, -e2["pc"].t / 2.0)))
        return
    limit = MITER_LIMIT * max(e1["pc"].t, e2["pc"].t)
    if _gap(e1, e2) < math.pi - 1e-6 or _dist(pt, node) <= limit:
        _put(e1, +1, pt)
        _put(e2, -1, pt)
        return
    s = _unit(_sub(pt, node))                    # the spike's way
    reach = max(e1["pc"].t, e2["pc"].t) / 2.0
    bevel = ("line", _add(node, _mul(s, reach)), _left(s))
    p1 = _nearest(_meet(f1, bevel), node)
    p2 = _nearest(_meet(f2, bevel), node)
    if p1 is None or p2 is None:
        _put(e1, +1, pt)
        _put(e2, -1, pt)
        return
    _put(e1, +1, p1)
    _put(e2, -1, p2)
    if e1["ghost"]:
        _cap(e2, [p1])          # e2's end: inner corner → p1 → p2
    else:
        _cap(e1, [p2])          # e1's end: p1 → p2 → inner corner


def _trim(node, stem, thru):
    """Cut the stem on the face of the wall running through (the T)."""
    side = +1 if _cross(thru["u"], stem["u"]) >= 0 else -1
    wall_side, face = _face_of(thru, side)
    got = []
    for rel in (+1, -1):
        _s2, f = _face_of(stem, rel)
        pt = _nearest(_meet(f, face), node)
        if pt is None or _dist(pt, node) > MITER_LIMIT * max(
                stem["pc"].t, thru["pc"].t) + _dist(stem["p"], node):
            _square(stem)
            return
        got.append(pt)
    _put(stem, +1, got[0])
    _put(stem, -1, got[1])
    if face[0] == "circle":
        thru["pc"].notches.append((wall_side, got[0], got[1]))


def _resolve(node, group):
    n = len(group)
    if n == 1:
        _square(group[0])
        return
    if n == 2:
        _mitre(node, group[0], group[1])
        _mitre(node, group[1], group[0])
        return
    best, score_best = None, None
    for i in range(n):
        for j in range(i + 1, n):
            a, b = group[i], group[j]
            dot = max(-1.0, min(1.0, _dot(a["u"], b["u"])))
            off = abs(math.acos(dot) - math.pi)
            if off > THROUGH_TOL:
                continue
            # a wall only PASSING here must be the one through (we may not
            # touch it); then the thickest, then the straightest
            score = (a["ghost"] and b["ghost"],
                     max(a["pc"].t, b["pc"].t), -off)
            if score_best is None or score > score_best:
                best, score_best = (i, j), score
    if best is None:
        _y(node, group)
        return
    i, j = best
    a, b = group[i], group[j]
    _mitre(node, a, b)
    _mitre(node, b, a)
    for k, s in enumerate(group):
        if k not in (i, j):
            _trim(node, s, a)


def _y(node, group):
    """A true Y (no two walls running through): every two neighbours are
    mitred, and the small polygon those mitres leave in the middle goes to
    the MAIN wall (the thickest; the same: the one drawn first) — its end
    runs round the middle. No hole, no overlap."""
    n = len(group)
    ms = []
    for k in range(n):
        e1, e2 = group[k], group[(k + 1) % n]
        _s1, f1 = _face_of(e1, +1)
        _s2, f2 = _face_of(e2, -1)
        pt = _nearest(_meet(f1, f2), node)
        if pt is None or _dist(pt, node) > MITER_LIMIT * max(
                e1["pc"].t, e2["pc"].t):
            # arms nearly on top of each other: overlap in the middle
            out = max(e["pc"].t for e in group) / 2.0
            for e in group:
                _square(e, out)
            return
        ms.append(pt)
    for k in range(n):
        _put(group[k], +1, ms[k])
        _put(group[(k + 1) % n], -1, ms[k])
    i = max(range(n), key=lambda k: (group[k]["pc"].t, -group[k]["pc"].wi))
    # its end runs: m(main, next) → … round the middle … → m(prev, main)
    _cap(group[i], [ms[(i + k) % n] for k in range(1, n - 1)])


def _ghosts(node, group, pieces):
    """Walls whose BODY the node sits on (a partition stopping against
    them): they join as a pair passing through — never cut themselves."""
    here = {id(e["pc"]) for e in group}
    for pc in pieces:
        if id(pc) in here:
            continue
        f, off = pc.seg.project(node)
        margin = JOIN_TOL / max(pc.seg.L, EPS)
        closed = getattr(pc, "closed", False)
        if not closed and not margin < f < 1.0 - margin:
            continue
        if abs(off) > pc.t / 2.0 + BODY_TOL:
            continue
        f = f % 1.0 if closed else f
        p = pc.seg.at(f)
        u = pc.seg.tangent(f)
        group.append({"pc": pc, "end": "A", "p": p, "u": u, "c": node,
                      "ghost": True})
        group.append({"pc": pc, "end": "B", "p": p,
                      "u": (-u[0], -u[1]), "c": node, "ghost": True})


# ---- the plan of each wall -------------------------------------------------------
def _steps(sweep: float, radius: float) -> int:
    if radius <= CHORD:
        return 8
    da = 2.0 * math.acos(max(-1.0, 1.0 - CHORD / radius))
    da = min(da, MAX_STEP)
    return max(1, int(math.ceil(abs(sweep) / da)))


def _arc_points(C, R, p_from, p_to, d, n):
    """From p_from to p_to on the circle (C, R), turning the way d, in n
    steps (the end points exact)."""
    a0 = math.atan2(p_from[1] - C[1], p_from[0] - C[0])
    a1 = math.atan2(p_to[1] - C[1], p_to[0] - C[0])
    sweep = (a1 - a0) % (2 * math.pi) if d > 0 else \
        -((a0 - a1) % (2 * math.pi))
    if abs(sweep) > 2 * math.pi - 1e-6:
        sweep = 0.0
    pts = [p_from]
    for k in range(1, n):
        a = a0 + sweep * k / n
        pts.append((C[0] + R * math.cos(a), C[1] + R * math.sin(a)))
    pts.append(p_to)
    return pts


def _notched(pc, side, pts, descending=False, cyclic=False):
    """A curved face's points, made to pass THROUGH the points where stems
    are cut on it (the samples between a stem's two corners go: its flat
    end and the face share that chord exactly)."""
    ns = [(p, q) for s, p, q in pc.notches if s == side]
    if not ns:
        return pts

    def fr(p):
        f = pc.seg.project(p)[0]
        return f % 1.0 if cyclic else f

    items = [(fr(p), p) for p in pts]
    for p, q in ns:
        f1, f2 = sorted((fr(p), fr(q)))
        wrap = cyclic and f2 - f1 > 0.5      # a stem across the ring's seam

        def inside(f, f1=f1, f2=f2, wrap=wrap):
            return (f > f2 or f < f1) if wrap else f1 < f < f2
        items = [it for it in items if not inside(it[0])]
        items += [(fr(p), p), (fr(q), q)]
    items.sort(key=lambda it: it[0], reverse=descending)
    out = []
    for _f, p in items:
        if not out or _dist(p, out[-1]) > 1e-7:
            out.append(p)
    return out


def _area(loop):
    return 0.5 * sum(_cross(p, q) for p, q in zip(loop, loop[1:] + loop[:1]))


def _clamped(pc, end, side, pt):
    """A corner may not slide past the middle of its own piece (a short
    wall between two junctions would turn inside out)."""
    f, _off = pc.seg.project(pt)
    if end == "A" and f > 0.45:
        f = 0.45
    elif end == "B" and f < 0.55:
        f = 0.55
    else:
        return pt
    s = pc.seg.offset(side * pc.t / 2.0)
    return s.at(f)


def _outline(pc):
    """The piece's plan: {"outer": loop CCW, "holes": [loops]}."""
    t = pc.t
    seg = pc.seg
    if getattr(pc, "closed", False):
        n = _steps(2 * math.pi, seg.r + t / 2)
        ring = []
        # the ring runs counter-clockwise: its left (+1) is the inner face
        for side, R in ((-1, seg.r + t / 2.0), (+1, seg.r - t / 2.0)):
            pts = [(seg.C[0] + R * math.cos(2 * math.pi * k / n),
                    seg.C[1] + R * math.sin(2 * math.pi * k / n))
                   for k in range(n)]
            ring.append(_notched(pc, side, pts, cyclic=True))
        return {"outer": ring[0], "holes": [list(reversed(ring[1]))]}

    def corner(end, side):
        default = seg.offset(side * t / 2.0).at(0.0 if end == "A" else 1.0)
        return _clamped(pc, end, side, pc.corners.get((end, side), default))

    a_l, a_r = corner("A", +1), corner("A", -1)
    b_l, b_r = corner("B", +1), corner("B", -1)
    # each end: from the corner on the left of the way in, through its caps,
    # to the one on the right (at A that is wall-left → wall-right, at B
    # wall-right → wall-left)
    cap_a, cap_b = pc.caps["A"], pc.caps["B"]
    if seg.kind == "line":
        loop = [a_r, b_r] + cap_b + [b_l, a_l] + cap_a
    else:
        right = seg.offset(-t / 2.0)
        left = seg.offset(+t / 2.0)
        n = _steps(seg.sweep, max(right.r, left.r))
        loop = _notched(pc, -1, _arc_points(right.C, right.r, a_r, b_r,
                                            seg.d, n)) + cap_b + \
            _notched(pc, +1, _arc_points(left.C, left.r, b_l, a_l,
                                         -seg.d, n), descending=True) + cap_a
    clean = [loop[0]]
    for p in loop[1:]:
        if _dist(p, clean[-1]) > 1e-7:
            clean.append(p)
    if len(clean) > 2 and _dist(clean[0], clean[-1]) <= 1e-7:
        clean.pop()
    if _area(clean) < 0:
        clean.reverse()
    return {"outer": clean, "holes": []}


def _to_corner(walls: list[dict]) -> list[dict]:
    """An end that stops on the FACE of another wall right by that wall's
    corner (drawn touching, not overlapping — his case, 2026-10-02: a wall
    carrying on another one's line, started on the face of the wall
    between) is carried onto that corner, so it JOINS it there instead of
    standing alone with a seam. Only when its own line runs into the
    corner: the wall keeps its way, it just reaches the node.

    Also (support #64, 2026-10-27): an end landing in the CORNER of a
    free wall end — its outer or inner corner, or the face right by it —
    is carried onto that end, so a diagonal closes the corner (it stood
    beside it, mismatched or notched). And two ends never swap places
    (a short piece refused between two walls: each was carried onto the
    other's end and they overlapped) — only the later wall moves."""
    ends = []
    for w in walls:
        if w.get("kind", "line") in ("line", "arc"):
            ends += [tuple(w["a"]), tuple(w["b"])]

    def free(p):
        return sum(1 for e in ends if _dist(e, p) <= JOIN_TOL) <= 1

    moves = {}                       # (wall, key) → (other wall, its key, point)
    for wi, w in enumerate(walls):
        if w.get("kind", "line") != "line":
            continue
        d = drawn(w)
        for key, p, back in (("a", d.p0, (-d.u[0], -d.u[1])),
                             ("b", d.p1, d.u)):
            if not free(p):
                continue                         # already meets an end
            best = None
            for oi, o in enumerate(walls):
                if oi == wi or is_closed(o) or why_not(o) is not None:
                    continue
                s = centre(o)
                f, off = s.project(p)
                if abs(off) > o["t"] / 2.0 + BODY_TOL:
                    continue                     # not on its body / face
                od = drawn(o)
                for ek, e in (("a", od.at(0.0)), ("b", od.at(1.0))):
                    v = _sub(e, p)
                    along = _dot(v, back)        # beyond the end, its way
                    across = abs(_cross(back, v))
                    reach = max(o["t"], w["t"]) + JOIN_TOL
                    gap = _dist(e, p)
                    if across <= 0.005 and JOIN_TOL < along <= reach:
                        pass                     # its line runs into it
                    elif s.kind == "line" and free(e) and \
                            abs(_cross(d.u, s.u)) > 0.17 and \
                            JOIN_TOL < gap <= 0.1 * d.L and \
                            abs((f - (0.0 if ek == "a" else 1.0)) * s.L) \
                            <= o["t"] / 2.0 + BODY_TOL:
                        pass                     # in that end's corner
                    else:
                        continue
                    if best is None or gap < best[0]:
                        best = (gap, oi, ek, e)
            if best is not None:
                moves[(wi, key)] = best[1:]
    out = []
    for wi, w in enumerate(walls):
        w = dict(w) if w.get("kind", "line") == "line" else w
        for key in ("a", "b"):
            m = moves.get((wi, key))
            if m is None:
                continue
            oi, ek, e = m
            back = moves.get((oi, ek))
            if back is not None and back[0] == wi and back[1] == key and \
                    oi > wi:
                continue                         # the later one moves
            w[key] = [e[0], e[1]]
        out.append(w)
    return out


def _joined(walls: list[dict], pairs: list | None = None):
    """(the walls built, their pieces with every join resolved).
    ``pairs``: filled with the (end, end) of every corner of just two walls
    (``corners``)."""
    good = _to_corner([w for w in walls if why_not(w) is None])
    pieces = _pieces(good)
    ends = _ends(pieces)
    if ends:
        ids, centres = _cluster([e["c"] for e in ends], JOIN_TOL)
        nodes: dict = {}
        for k, e in enumerate(ends):
            nodes.setdefault(ids[k], []).append(e)
        for nid, group in nodes.items():
            node = centres[nid]
            _ghosts(node, group, pieces)
            group.sort(key=lambda e: math.atan2(e["u"][1], e["u"][0]))
            _resolve(node, group)
            if pairs is not None and len(group) == 2:
                pairs.append(tuple(group))
    return good, pieces


def corners(walls: list[dict]) -> tuple:
    """(``plan``, its plain L corners): [{"a", "a_end", "b", "b_end",
    "diag": (p, q)}] — two straight walls' true ends mitred on one
    diagonal (no bevel, no crossing, no wall passing) — ``corner_caps``
    reads them: the higher wall goes on over the corner."""
    pairs: list = []
    good, pieces = _joined(walls, pairs)
    out: dict = {w["id"]: [] for w in good}
    for pc in pieces:
        out[pc.w["id"]].append(_outline(pc))
    found = []
    for e1, e2 in pairs:
        if e1["ghost"] or e2["ghost"]:
            continue
        p1, p2 = e1["pc"], e2["pc"]
        if p1.w is p2.w or any(
                getattr(p, "closed", False) or p.w.get("kind", "line") != "line"
                or p.w.get("cw") or p.caps[e["end"]]
                or not (p.real_a if e["end"] == "A" else p.real_b)
                for p, e in ((p1, e1), (p2, e2))):
            continue
        d1 = [p1.corners.get((e1["end"], s)) for s in (1, -1)]
        d2 = [p2.corners.get((e2["end"], s)) for s in (1, -1)]
        if None in d1 or None in d2 or _dist(d1[0], d1[1]) < EPS:
            continue
        # one diagonal: the same two points on both ends
        if not all(min(_dist(p, q) for q in d2) < 1e-6 for p in d1):
            continue
        found.append({"a": p1.w["id"], "a_end": e1["end"],
                      "b": p2.w["id"], "b_end": e2["end"],
                      "diag": (tuple(d1[0]), tuple(d1[1]))})
    return out, found


def plan(walls: list[dict]) -> dict:
    """Each wall's plan, joined: {wall id: [pieces]} — a piece is
    {"outer": [(x, y)…] counter-clockwise, "holes": [[(x, y)…]]}. Walls
    that can't be built (``why_not``) are left out."""
    good, pieces = _joined(walls)
    out: dict = {w["id"]: [] for w in good}
    for pc in pieces:
        out[pc.w["id"]].append(_outline(pc))
    return out


def plan_layers(walls: list[dict]) -> dict:
    """Like ``plan``, each piece cut into its wall's LAYERS: {wall id:
    [(layer index, piece)…]} — the whole joined outline sliced in bands
    along the wall, so an L's finishes meet on the mitre and a partition
    stops on the outer wall's inner finish, as the walls themselves do. A
    wall without layers: (0, its pieces)."""
    good, pieces = _joined(walls)
    out: dict = {w["id"]: [] for w in good}
    for pc in pieces:
        whole = _outline(pc)
        bands = layer_bands(pc.w)
        if len(bands) < 2:
            out[pc.w["id"]].append((0, whole))
            continue
        for i, (lo, hi) in enumerate(bands):
            for part in _band(pc, whole, lo, hi):
                out[pc.w["id"]].append((i, part))
    return out


class _Along:
    """What ``_band`` reads of a piece: the line along it, ring or not."""

    def __init__(self, seg, closed):
        self.seg, self.closed = seg, closed


def layer_pieces(w: dict, piece: dict) -> list:
    """One joined plan piece of ``w`` (``plan``'s) cut into its layers:
    [(layer index, piece)] — a plain wall: [(0, piece)]."""
    bands = layer_bands(w)
    if len(bands) < 2:
        return [(0, piece)]
    pc = _Along(centre(w), is_closed(w) and bool(piece.get("holes")))
    out = []
    for i, (lo, hi) in enumerate(bands):
        out += [(i, part) for part in _band(pc, piece, lo, hi)]
    return out


def shared_edge(w: dict, i: int):
    """The offset (from the centre) where layer i meets the layer OUTSIDE
    it — None for the outermost."""
    bands = layer_bands(w)
    if not 0 < i < len(bands):
        return None
    a, b = bands[i - 1], bands[i]
    for x in a:
        for y in b:
            if abs(x - y) < 1e-6:
                return y
    return None


def _band(pc, piece: dict, lo: float, hi: float) -> list:
    """The part of a wall piece between offsets lo and hi from its centre
    (its left +): a ring → a narrower ring; else the outline clipped by the
    two lines (arcs) running along it."""
    seg = pc.seg
    if getattr(pc, "closed", False):
        # the ring runs counter-clockwise: offset o ↔ radius r − o
        n = _steps(2 * math.pi, seg.r - lo)
        rings = []
        for R in (seg.r - lo, seg.r - hi):
            rings.append([(seg.C[0] + R * math.cos(2 * math.pi * k / n),
                           seg.C[1] + R * math.sin(2 * math.pi * k / n))
                          for k in range(n)])
        return [{"outer": rings[0], "holes": [list(reversed(rings[1]))]}]

    def off(p):
        return seg.project(p)[1]

    loop = list(piece["outer"])
    for lim, keep_above in ((lo, True), (hi, False)):
        loop = _clip(loop, off, lim, keep_above, seg)
        if len(loop) < 3:
            return []
    if abs(_area(loop)) < 1e-8:
        return []
    if _area(loop) < 0:
        loop.reverse()
    return [{"outer": loop, "holes": []}]


def _clip(loop, off, lim, keep_above, seg):
    """Sutherland–Hodgman against one line along the wall (off = lim):
    keep off ≥ lim (``keep_above``) or ≤ lim. On a curved wall the cut
    line is an arc: the points along it are filled in."""
    def inside(p):
        return off(p) >= lim - 1e-9 if keep_above else off(p) <= lim + 1e-9

    def cross(p, q):
        a, b = off(p), off(q)
        f = (lim - a) / (b - a) if abs(b - a) > EPS else 0.0
        x = _add(p, _mul(_sub(q, p), f))
        if seg.kind == "arc":                  # onto the arc, exactly
            v = _sub(x, seg.C)
            R = seg.r - seg.d * lim
            x = _add(seg.C, _mul(_unit(v), R))
        return x

    out = []
    n = len(loop)
    for k in range(n):
        p, q = loop[k], loop[(k + 1) % n]
        pi, qi = inside(p), inside(q)
        if pi:
            out.append(p)
            if not qi:
                out.append(cross(p, q))
        elif qi:
            out.append(cross(p, q))
    if seg.kind == "arc" and len(out) > 2:
        out = _fill_arc(out, off, lim, seg)
    clean = []
    for p in out:
        if not clean or _dist(p, clean[-1]) > 1e-7:
            clean.append(p)
    if len(clean) > 2 and _dist(clean[0], clean[-1]) <= 1e-7:
        clean.pop()
    return clean


def _fill_arc(loop, off, lim, seg):
    """Two points in a row on the cut arc, far apart: the arc between."""
    R = seg.r - seg.d * lim
    out = []
    n = len(loop)
    for k in range(n):
        p, q = loop[k], loop[(k + 1) % n]
        out.append(p)
        if abs(off(p) - lim) < 1e-6 and abs(off(q) - lim) < 1e-6 \
                and _dist(p, q) > 4 * CHORD:
            a0 = math.atan2(p[1] - seg.C[1], p[0] - seg.C[0])
            a1 = math.atan2(q[1] - seg.C[1], q[0] - seg.C[0])
            sweep = _wrap(a1 - a0)
            # the way the wall runs, not the shorter one: a curved wall of
            # more than half a circle (his cylinder, 2026-11-01) had its
            # inner layers drawn round the other side
            h = a0 + sweep / 2.0
            f = seg.project((seg.C[0] + R * math.cos(h),
                             seg.C[1] + R * math.sin(h)))[0]
            if not -1e-6 <= f <= 1.0 + 1e-6:
                sweep -= math.copysign(2 * math.pi, sweep)
            m = _steps(sweep, R)
            for j in range(1, m):
                a = a0 + sweep * j / m
                out.append((seg.C[0] + R * math.cos(a),
                            seg.C[1] + R * math.sin(a)))
    return out


# ---- the solid of a plan --------------------------------------------------------
def solid(piece: dict, z0: float, z1: float) -> list:
    """Faces of a plan piece raised from z0 to z1: loops of (x, y, z),
    or {"loop", "holes"} for a face with holes; outward and counter-
    clockwise seen from outside."""
    outer = piece["outer"]
    holes = piece["holes"]

    def lift(loop, z):
        return [(x, y, z) for x, y in loop]

    faces = [{"loop": lift(outer, z1), "holes": [lift(h, z1) for h in holes]},
             {"loop": lift(list(reversed(outer)), z0),
              "holes": [lift(list(reversed(h)), z0) for h in holes]}]
    for loop in [outer] + holes:
        for p, q in zip(loop, loop[1:] + loop[:1]):
            faces.append([(p[0], p[1], z0), (q[0], q[1], z0),
                          (q[0], q[1], z1), (p[0], p[1], z1)])
    return faces


def tilted_solid(outer: list, z0: float, z1: float, dz: list) -> list:
    """A plan polygon raised from z0 to z1, each corner's top moved ``dz``
    (a BLOCK's corners up / down — 2026-10-31): the sides follow, the top
    is one plane when the corners lie in one, else triangles (ear
    clipping, corners only). Outward, as ``solid``."""
    outer = list(outer)
    if _area(outer) < 0:                # counter-clockwise from above
        outer.reverse()
        dz = list(reversed(dz))
    tops = [(x, y, z1 + d) for (x, y), d in zip(outer, dz)]
    faces = [[(x, y, z0) for x, y in reversed(outer)]]
    k = len(outer)
    for i in range(k):
        p, q = outer[i], outer[(i + 1) % k]
        faces.append([(p[0], p[1], z0), (q[0], q[1], z0), tops[(i + 1) % k],
                      tops[i]])
    pl = _plane_of(tops)
    if pl is not None and all(abs(sum(pl[0][j] * t[j] for j in range(3))
                                  - pl[1]) < 1e-6 for t in tops):
        faces.append(tops)              # one plane
        return faces
    for a, b, c in _ears(outer):
        faces.append([tops[a], tops[b], tops[c]])
    return faces


def _ears(poly: list) -> list:
    """Ear clipping of a counter-clockwise polygon: [(i, j, k)] index
    triples, no new points."""
    idx = list(range(len(poly)))
    out = []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def inside(p, a, b, c):
        return cross(a, b, p) >= -1e-12 and cross(b, c, p) >= -1e-12 \
            and cross(c, a, p) >= -1e-12
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        n = len(idx)
        for m in range(n):
            i, j, k = idx[m - 1], idx[m], idx[(m + 1) % n]
            a, b, c = poly[i], poly[j], poly[k]
            if cross(a, b, c) <= 1e-12:
                continue                # a reflex corner: no ear
            if any(inside(poly[r], a, b, c) for r in idx
                   if r not in (i, j, k)):
                continue
            out.append((i, j, k))
            idx.pop(m)
            break
        else:
            break
    if len(idx) == 3:
        out.append(tuple(idx))
    return out


# ---- before a wall is stored --------------------------------------------------
def settle(w: dict, others: list[dict]) -> dict:
    """Pull a straight wall's ends that stop a little SHORT of another
    wall onto its face (a 2 cm gap would read as a mistake). Returns the
    wall, maybe with new ends."""
    if w.get("kind", "line") != "line":
        return w
    w = dict(w)
    d = drawn(w)
    for key, p, out_dir in (("a", d.p0, (-d.u[0], -d.u[1])),
                            ("b", d.p1, d.u)):
        best = None
        for o in others:
            if why_not(o) is not None:
                continue
            s = centre(o)
            for side in (+1, -1):
                face = s.face(side, o["t"])
                for x in _meet(("line", p, out_dir), face):
                    gap = _dot(_sub(x, p), out_dir)
                    if not 1e-6 < gap <= SNAP_TOL:
                        continue
                    f, _off = s.project(x)
                    if not is_closed(o) and not 0.0 <= f <= 1.0:
                        continue
                    if best is None or gap < best[0]:
                        best = (gap, x)
        if best is not None:
            w[key] = [round(best[1][0], 4), round(best[1][1], 4)]
    return w


def continues(w: dict, others: list[dict]):
    """The thickness a wall drawn from w's start should take: carrying ON
    a wall straight (or along a curve's tangent) takes its thickness — a
    step half-way along a straight run reads as a mistake; a branch keeps
    its own. None = nothing continued."""
    d = drawn(w)
    if is_closed(w):
        return None
    u = d.tangent(0.0)
    best = None
    for o in others:
        if is_closed(o) or why_not(o) is not None:
            continue
        od = drawn(o)
        for p, way in ((od.at(0.0), _mul(od.tangent(0.0), -1)),
                       (od.at(1.0), od.tangent(1.0))):
            if _dist(p, d.at(0.0)) > JOIN_TOL:
                continue
            dot = max(-1.0, min(1.0, _dot(u, way)))
            if math.acos(dot) <= CONTINUE_TOL and (best is None
                                                   or o["t"] > best):
                best = o["t"]
    return best
