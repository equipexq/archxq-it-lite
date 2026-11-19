# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A straight wall's SHAPE seen from the front (PLANO_CURVAS_E_FORMAS.md, F2 —
promised to a customer on 2026-11-13: a wall with a rounded top corner, a
«C» cut open to its end with a curved corner).

The wall record keeps, optionally:
    ``profile`` = {"ctrl":   [[s, z], …]  — control corners, anti-clockwise,
                               s along the line drawn (a = 0, b = L), z from
                               the wall's FOOT (its Base offset already in);
                   "curves": {"r": {i: radius}, "arc": {i: sagitta}} — the
                               format of curved.py (slabs, F1);
                   "L":      its length when it was saved;
                   "was":    "level" | a height — what «Back to rectangle»
                               gives back}
``ctrl[0] = (0, 0)`` and ``ctrl[1] = (L, 0)``: the foot is always whole and
straight, so the plan, the joints, floors, rooms and slabs never change.
No fine polygon is stored: ``outline`` expands it when the wall is built.
A wall without ``profile`` is today's, byte for byte.

Every edit returns (profile, None) or (None, why) — the «why» in English, as
the screen shows it. Pure: math, curved.py and shapely; no host, no Qt."""
from __future__ import annotations

import math

from . import curved as C

EPS = 1e-9
TOL = 1e-6              # m: two points this close are one
MIN_PART = 0.05         # m: no part of the wall thinner than this
MAX_PEAK = 50.0         # m: no higher than this
NOTCH_R = 0.30          # m: a notch's inner corners, by default
CHAMFER = 0.30          # m: a chamfer, by default
ROUND_R = 0.50          # m: a rounded corner, by default

WHY_CROSS = "The shape crosses itself"
WHY_FOOT = "The foot of the wall stays whole — change its length in the plan"
WHY_PAST = "Past the wall's end — change its length in the plan"
WHY_THIN = "Somewhere it's thinner than 5 cm"
WHY_HIGH = "Higher than 50 m"
WHY_CHAMFER_SIDES = "A chamfer needs two straight sides"
WHY_CHAMFER_FIT = "The chamfer doesn't fit the sides"
WHY_NOTCH_CURVE = "A notch cuts straight sides only — straighten that side first"
WHY_NOTCH_INSIDE = ("Inside the wall: that's an opening — use an Opening "
                    "with the \"Rounded top\" shape")
WHY_TWO = "It would cut the wall in two"
WHY_SPLIT_CURVE = "Not through a curve of its shape — click beside it"
WHY_SPLIT_FLOAT = "A piece of its shape would float — click beside it"
WHY_LENGTH = "Its shape doesn't fit that length"
WHY_KIND = "Shape: straight walls only (not curved, nor a curtain wall)"
WHY_TOP_ONLY = ("A grid, clad or light-framed wall takes a shape cut from "
                "its top only — not into its sides")
#: walls whose shape is their TOP (the shape editor, phase 3 — 17/11/2026):
#: built as ever, then cut under it (walls.topped), as a gable end
TOP_ONLY = ("gw", "frame", "clad")
STEP = 0.001            # m: a sheer step in such a top, 1 mm wide
WHY_POINT = "No such point"
WHY_FEW = "A shape needs three points at least"


# ---- the data ------------------------------------------------------------------------
def why_no_shape(w: dict | None) -> str | None:
    """Why this wall can't take a shape (None = it can): only a straight,
    solid wall — not curved, a curtain wall, a Grid wall, light-framed or
    clad in boards."""
    w = w or {}
    if w.get("kind", "line") != "line":
        return WHY_KIND
    if w.get("cw"):
        return WHY_KIND
    return None


def top_only(w: dict | None) -> bool:
    """A grid / clad / light-framed wall: its shape is its top."""
    return any((w or {}).get(k) for k in TOP_ONLY)


def _top_chain(prof: dict) -> list | None:
    """Its top seen from the front as [(s, z)], s growing — None when the
    shape is not a top over a whole foot (cut into a side: a «C»)."""
    pts, _arcs = outline(prof, 0.0)
    L = float(prof["L"])
    if len(pts) < 4:
        return None
    k = next((i for i, p in enumerate(pts)
              if abs(p[0] - L) < 1e-6 and abs(p[1]) < 1e-9), None)
    if k is None or pts[0] != (0.0, 0.0):
        return None
    chain = pts[k + 1:]
    if not chain:
        return None
    # each step s goes back (or stands — a sheer step): never forward
    if any(q[0] > p[0] + 1e-6 for p, q in zip([pts[k]] + chain, chain)):
        return None
    if any(p[1] <= 1e-9 for p in chain):
        return None
    while len(chain) > 1 and abs(chain[1][0] - L) < 1e-6:
        chain.pop(0)                  # (its end B side, straight up)
    while len(chain) > 1 and abs(chain[-2][0]) < 1e-6:
        chain.pop()                   # (its end A side, straight down)
    if abs(chain[0][0] - L) > 1e-6 or abs(chain[-1][0]) > 1e-6:
        return None
    return list(reversed(chain))


def why_not_top(prof: dict) -> str | None:
    """Why that shape can't be a grid / clad / framed wall's (None = it
    can): it must be its top over its whole foot."""
    return None if _top_chain(prof) is not None else WHY_TOP_ONLY


def as_top(prof: dict, base: float = 0.0) -> dict | None:
    """The shape as the wall's own top (walls.top_of): {"kind": "poly",
    "pts": [[s, h]…]} — h from the level's floor (its Base offset in), s
    along the line drawn; a sheer step 1 mm wide (STEP: one plane each
    side of it). None: not a top."""
    chain = _top_chain(prof)
    if chain is None:
        return None
    out = []
    for s, z in chain:
        if out and s < out[-1][0] + STEP:
            s = out[-1][0] + STEP
        out.append([round(s, 6), round(base + z, 6)])
    return {"kind": "poly", "pts": out}


def _pt(p) -> list:
    return [round(float(p[0]), 4) + 0.0, round(float(p[1]), 4) + 0.0]


def clean(raw, L: float | None = None, height="level") -> dict | None:
    """``profile`` as stored, or None (not one). Keeps what was saved even
    when its length no longer matches the wall's (``stretched`` mends that
    when it is built) — nothing the user made is thrown away on load."""
    if not isinstance(raw, dict):
        return None
    try:
        ctrl = [_pt(p) for p in raw.get("ctrl") or ()]
        Lp = float(raw.get("L", ctrl[1][0] if len(ctrl) > 1 else 0.0))
    except (TypeError, ValueError, IndexError):
        return None
    if len(ctrl) < 3 or Lp <= MIN_PART:
        return None
    was = raw.get("was", height)
    try:
        was = "level" if was == "level" else round(float(was), 4)
    except (TypeError, ValueError):
        was = "level"
    out = {"ctrl": ctrl, "curves": C.clean(raw.get("curves")),
           "L": round(Lp, 4), "was": was}
    return out if why_not(out) is None else None


def profile_of(w: dict | None) -> dict | None:
    """The wall's shape, or None (a plain wall, as always)."""
    if not w or not w.get("profile") or why_no_shape(w):
        return None
    p = w["profile"]
    return p if isinstance(p, dict) and p.get("ctrl") else None


def peak(prof: dict) -> float:
    """Its highest point, from the wall's foot (exact, arcs included)."""
    return max(p[1] for p in C.expand(prof["ctrl"], prof.get("curves")))


def area_exact(prof: dict) -> float:
    """Its area seen from the front, exact (circular sectors, segments)."""
    return C.area(prof["ctrl"], prof.get("curves"))


def is_rect(prof: dict) -> float | None:
    """Its height when it is just a rectangle (a plain wall again), else
    None."""
    if C.is_curved(prof) or len(prof["ctrl"]) != 4:
        return None
    (s0, z0), (s1, z1), (s2, z2), (s3, z3) = prof["ctrl"]
    L = prof["L"]
    if abs(s2 - L) < TOL and abs(s3) < TOL and abs(z2 - z3) < TOL:
        return z2
    return None


# ---- what the wall is built from --------------------------------------------------------
def _tagged(ctrl, curves) -> list:
    """The outline as [(point, arc index or None for the piece it starts)]
    — the same points as curved.expand, so the arcs line up with it."""
    out = []
    k = 0
    for pc in C.pieces(ctrl, curves):
        if pc[0] == "arc":
            _kind, a, b, c, R, sw = pc
            pts = [a] + C._arc_pts(c, R, a, sw) + [b]
            out.append(("arc", pts))
            k += 1
        else:
            out.append(("line", [pc[1], pc[2]]))
    return out


def outline(prof: dict, z_foot: float, b: float | None = None) -> tuple:
    """(outline, arcs): the shape in (s, z) with z ABSOLUTE — its foot at
    ``z_foot`` (the level's floor + the wall's lift), and the foot's points
    taken down to ``b`` (the real foot: a wall going down through its slab)
    — and each arc as the run of outline points it is made of
    (profilecut.wall_faces' ``arcs``)."""
    b = z_foot if b is None else b

    def put(p):
        s = round(p[0], 4) + 0.0
        z = round(p[1], 4) + 0.0
        return (s, b if abs(z) < 1e-9 else z_foot + z)
    def same(p, q):
        return abs(p[0] - q[0]) <= 1e-9 and abs(p[1] - q[1]) <= 1e-9
    pts, arcs = [], []
    for kind, run in _tagged(prof["ctrl"], prof.get("curves")):
        seq = []
        for p in map(put, run):
            if not seq or not same(p, seq[-1]):
                seq.append(p)
        for p in seq[:-1]:
            if not pts or not same(p, pts[-1]):
                pts.append(p)
        if kind == "arc" and len(seq) > 1:
            arcs.append(seq)
    if len(pts) > 1 and same(pts[0], pts[-1]):
        pts.pop()
    return pts, arcs


def slice_at(prof: dict, s: float) -> list:
    """[(z0, z1), …] from the foot: where the shape stands at ``s`` along
    the line (one interval for a plain end; two past a «C»)."""
    from shapely.geometry import LineString, Polygon
    P = Polygon(C.expand(prof["ctrl"], prof.get("curves")))
    zt = peak(prof) + 1.0
    g = P.intersection(LineString([(s, -1.0), (s, zt)]))
    out = []
    for part in getattr(g, "geoms", [g]):
        if part.is_empty or part.geom_type != "LineString":
            continue
        zs = [c[1] for c in part.coords]
        if max(zs) - min(zs) > 1e-7:
            out.append((min(zs), max(zs)))
    return sorted(out)


def from_top(w: dict, span: tuple | None = None) -> dict | None:
    """The shape a wall's ``top`` (sloped, a gable) or its flat height
    makes — the starting point of the Shape tab. Past its clear ends
    (``span``) its top runs level, as built (the same solid)."""
    from . import walls as W
    L = W.drawn(w).L
    if L <= MIN_PART:
        return None
    lift = float(w.get("base", 0.0) or 0.0)     # its foot, from the floor
    ww = dict(w)
    if span:
        ww["_span"] = list(span)
    top = W.top_of(ww)
    if top is None:
        h = w.get("height", "level")
        if h == "level":
            return None
        H = float(h) - lift
        ctrl = [[0.0, 0.0], [L, 0.0], [L, H], [0.0, H]]
        was = h
    else:
        sa, sb = W.top_span(ww)
        ss = [L, sb]
        if top["kind"] == "gable":
            ss.append(min(max(top["at"] * L, sa), sb))
        ss += [sa, 0.0]
        ctrl = [[0.0, 0.0], [L, 0.0]]
        for s in ss:
            p = [s, W.top_h(ww, s) - lift]
            if abs(p[0] - ctrl[-1][0]) > TOL or abs(p[1] - ctrl[-1][1]) > TOL:
                ctrl.append(p)
        was = top.get("was", "level")
    prof = {"ctrl": _straighten([_pt(p) for p in ctrl]),
            "curves": {"r": {}, "arc": {}}, "L": round(L, 4), "was": was}
    return prof if why_not(prof) is None else None


def _straighten(ctrl: list) -> list:
    """Drop the points in a straight line between their neighbours (never
    the foot's two)."""
    out = list(ctrl)
    i = 2
    while i < len(out) and len(out) > 3:
        p, q, r = out[i - 1], out[i], out[(i + 1) % len(out)]
        cr = (q[0] - p[0]) * (r[1] - q[1]) - (q[1] - p[1]) * (r[0] - q[0])
        if abs(cr) < 1e-9 and (q[0] - p[0]) * (r[0] - q[0]) \
                + (q[1] - p[1]) * (r[1] - q[1]) > 0:
            out.pop(i)
        else:
            i += 1
    return out


# ---- is it a shape? ----------------------------------------------------------------------
def _poly(prof: dict):
    from shapely.geometry import Polygon
    return Polygon(C.expand(prof["ctrl"], prof.get("curves")))


def why_not(prof: dict) -> str | None:
    """Why this can't be a wall's shape (None = it can)."""
    ctrl = prof.get("ctrl") or []
    if len(ctrl) < 3:
        return WHY_FEW
    L = float(prof.get("L", 0.0))
    (s0, z0), (s1, z1) = ctrl[0], ctrl[1]
    if abs(s0) > TOL or abs(z0) > TOL or abs(s1 - L) > TOL or abs(z1) > TOL:
        return WHY_FOOT
    curves = prof.get("curves") or {}
    rs, arcs = curves.get("r") or {}, curves.get("arc") or {}
    if C._key(rs, 0) or C._key(rs, 1) or C._key(arcs, 0):
        return WHY_FOOT
    for s, z in ctrl[2:]:
        if s < -TOL or s > L + TOL:
            return WHY_PAST
        if z < MIN_PART - TOL:
            return WHY_FOOT if 0.0 < s < L else WHY_THIN
    why = C.why_not(ctrl, curves)
    if why:
        return why
    fine = C.expand(ctrl, curves)
    if any(p[0] < -TOL or p[0] > L + TOL for p in fine):
        return WHY_PAST
    if any(p[1] < -TOL for p in fine):
        return WHY_FOOT
    if max(p[1] for p in fine) > MAX_PEAK + TOL:
        return WHY_HIGH
    a = sum(ctrl[i][0] * ctrl[(i + 1) % len(ctrl)][1]
            - ctrl[(i + 1) % len(ctrl)][0] * ctrl[i][1]
            for i in range(len(ctrl)))
    P = _poly(prof)
    if a <= 0 or not P.is_valid:
        return WHY_CROSS
    # thinner than 5 cm somewhere: eroding by half of it and growing back
    # loses a piece (a fin, a neck) — or splits it
    core = P.buffer(-MIN_PART / 2 + 1e-6, join_style="mitre")
    if core.is_empty or core.geom_type != "Polygon":
        return WHY_THIN
    back = core.buffer(MIN_PART / 2 - 1e-6, join_style="mitre",
                       mitre_limit=50.0)
    if P.difference(back).area > 1e-4:
        return WHY_THIN
    return None


def _done(prof: dict) -> tuple:
    why = why_not(prof)
    return (None, why) if why else (prof, None)


def _copy(prof: dict, ctrl=None, curves=None) -> dict:
    return {"ctrl": [_pt(p) for p in (ctrl if ctrl is not None
                                       else prof["ctrl"])],
            "curves": C.clean(curves if curves is not None
                              else prof.get("curves")),
            "L": prof["L"], "was": prof.get("was", "level")}


# ---- the edits ---------------------------------------------------------------------------
def move_point(prof: dict, i: int, s: float, z: float) -> tuple:
    """Control corner ``i`` to (s, z)."""
    n = len(prof["ctrl"])
    if not 0 <= i < n:
        return None, WHY_POINT
    if i in (0, 1):
        return None, WHY_FOOT
    if s < -TOL or s > prof["L"] + TOL:
        return None, WHY_PAST
    ctrl = [list(p) for p in prof["ctrl"]]
    ctrl[i] = [s, z]
    return _done(_copy(prof, ctrl))


def move_side(prof: dict, i: int, d: float) -> tuple:
    """Side ``i`` (corner i → i+1) moved ``d`` square to itself (+ = to its
    left, into the wall — the sign of curved.py)."""
    ctrl = [list(p) for p in prof["ctrl"]]
    n = len(ctrl)
    if not 0 <= i < n:
        return None, WHY_POINT
    j = (i + 1) % n
    if i in (0, 1) or j in (0, 1):
        return None, WHY_FOOT
    p, q = ctrl[i], ctrl[j]
    L = math.hypot(q[0] - p[0], q[1] - p[1])
    if L < EPS:
        return None, WHY_POINT
    nx, nz = -(q[1] - p[1]) / L, (q[0] - p[0]) / L
    for k in (i, j):
        ctrl[k] = [ctrl[k][0] + nx * d, ctrl[k][1] + nz * d]
    return _done(_copy(prof, ctrl))


def add_point(prof: dict, i: int, at) -> tuple:
    """A new control corner on side ``i``, at the point of it nearest
    ``at`` (s, z). An arc on that side is dropped (as on slabs)."""
    ctrl = [list(p) for p in prof["ctrl"]]
    n = len(ctrl)
    if not 0 <= i < n:
        return None, WHY_POINT
    if i == 0:
        return None, WHY_FOOT
    p, q = ctrl[i], ctrl[(i + 1) % n]
    dx, dz = q[0] - p[0], q[1] - p[1]
    LL = dx * dx + dz * dz
    t = 0.5 if LL < EPS else ((at[0] - p[0]) * dx + (at[1] - p[1]) * dz) / LL
    t = min(max(t, 0.05), 0.95)
    new = ctrl[:i + 1] + [[p[0] + dx * t, p[1] + dz * t]] + ctrl[i + 1:]
    curves, _dropped = C.remap(ctrl, new, prof.get("curves"))
    return _done(_copy(prof, new, curves))


def delete_point(prof: dict, i: int) -> tuple:
    """Control corner ``i`` taken off."""
    ctrl = [list(p) for p in prof["ctrl"]]
    if not 0 <= i < len(ctrl):
        return None, WHY_POINT
    if i in (0, 1):
        return None, WHY_FOOT
    if len(ctrl) <= 3:
        return None, WHY_FEW
    new = ctrl[:i] + ctrl[i + 1:]
    curves, _dropped = C.remap(ctrl, new, prof.get("curves"))
    return _done(_copy(prof, new, curves))


def round_corner(prof: dict, i: int, r: float = ROUND_R) -> tuple:
    """Corner ``i`` rounded with radius ``r`` (0: square again)."""
    if not 0 <= i < len(prof["ctrl"]):
        return None, WHY_POINT
    if i in (0, 1):
        return None, WHY_FOOT
    curves = C.clean(prof.get("curves"))
    curves["r"].pop(str(i), None)
    if r > EPS:
        curves["r"][str(i)] = r
    return _done(_copy(prof, curves=curves))


def bend_side(prof: dict, i: int, h: float) -> tuple:
    """Side ``i`` bent into an arc whose middle stands ``h`` off it (+ =
    into the wall; 0: straight again)."""
    if not 0 <= i < len(prof["ctrl"]):
        return None, WHY_POINT
    if i == 0:
        return None, WHY_FOOT
    curves = C.clean(prof.get("curves"))
    curves["arc"].pop(str(i), None)
    if abs(h) > EPS:
        curves["arc"][str(i)] = h
    return _done(_copy(prof, curves=curves))


def chamfer(prof: dict, i: int, d: float = CHAMFER) -> tuple:
    """Corner ``i`` cut off ``d`` along each of its sides."""
    ctrl = [list(p) for p in prof["ctrl"]]
    n = len(ctrl)
    if not 0 <= i < n:
        return None, WHY_POINT
    if i in (0, 1):
        return None, WHY_FOOT
    curves = C.clean(prof.get("curves"))
    rs, arcs = curves["r"], curves["arc"]
    if C._key(arcs, i - 1 if i else n - 1) or C._key(arcs, i) \
            or C._key(rs, i):
        return None, WHY_CHAMFER_SIDES
    prev, p, nxt = ctrl[i - 1], ctrl[i], ctrl[(i + 1) % n]
    out = []
    for q in (prev, nxt):
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        if d <= EPS or d >= L - TOL:
            return None, WHY_CHAMFER_FIT
        out.append([p[0] + (q[0] - p[0]) * d / L,
                    p[1] + (q[1] - p[1]) * d / L])
    new = ctrl[:i] + out + ctrl[i + 1:]
    shifted = {"r": {}, "arc": {}}
    for part in ("r", "arc"):
        for k, v in curves[part].items():
            k = int(k)
            shifted[part][str(k + 1 if k > i else k)] = v
    prof2 = _copy(prof, new, shifted)
    # the radii of the neighbours still have to fit their shorter sides
    why = C.why_not(prof2["ctrl"], prof2["curves"])
    if why:
        return None, WHY_CHAMFER_FIT
    return _done(prof2)


def _curve_zones(prof: dict) -> list:
    """Polygons covering each curve of the shape (a rounded corner: its
    arc and its corner; an arc on a side: arc and chord)."""
    from shapely.geometry import Polygon
    ctrl, curves = prof["ctrl"], prof.get("curves")
    out = []
    corners = {i: tuple(ctrl[i]) for i in range(len(ctrl))}
    rs = (curves or {}).get("r") or {}
    for kind, run in _tagged(ctrl, curves):
        if kind != "arc":
            continue
        ring = list(run)
        # a rounded corner: close it through its own corner
        for i, p in corners.items():
            if C._key(rs, i):
                f = C.fillet(ctrl[i - 1], p, ctrl[(i + 1) % len(ctrl)],
                             C._key(rs, i))
                if f and math.dist(f[0], run[0]) < 1e-6:
                    ring = ring + [p]
                    break
        if len(ring) >= 3:
            out.append(Polygon(ring).buffer(0))
        else:
            from shapely.geometry import LineString
            out.append(LineString(ring).buffer(1e-6))
    return out


def _from_poly(poly, prof: dict, radii: dict) -> tuple:
    """A shapely polygon back to a profile: its foot first, anti-clockwise,
    the old curves kept on the corners and sides that are still there and
    ``radii`` ({(s, z): r}) on new corners."""
    from shapely.geometry.polygon import orient
    if poly.geom_type != "Polygon":
        return None, WHY_TWO
    if len(poly.interiors):
        return None, WHY_NOTCH_INSIDE
    ring = [(round(x, 4) + 0.0, round(y, 4) + 0.0)
            for x, y in list(orient(poly, 1.0).exterior.coords)[:-1]]
    L = prof["L"]
    k = next((j for j, p in enumerate(ring)
              if abs(p[0]) < 1e-6 and abs(p[1]) < 1e-6), None)
    if k is None:
        return None, WHY_FOOT
    ring = ring[k:] + ring[:k]
    if abs(ring[1][0] - L) > 1e-6 or abs(ring[1][1]) > 1e-6:
        return None, WHY_FOOT
    ring = _straighten([list(p) for p in ring])
    old = [tuple(p) for p in prof["ctrl"]]
    curves = C.clean(prof.get("curves"))

    def find(p):
        return next((j for j, q in enumerate(old)
                     if abs(q[0] - p[0]) < 1e-6 and abs(q[1] - p[1]) < 1e-6),
                    None)
    out = {"r": {}, "arc": {}}
    n, m = len(ring), len(old)
    for j, p in enumerate(ring):
        o = find(p)
        if o is not None and str(o) in curves["r"]:
            out["r"][str(j)] = curves["r"][str(o)]
        for (rs, rz), r in radii.items():
            if abs(rs - p[0]) < 1e-6 and abs(rz - p[1]) < 1e-6 and r > EPS:
                out["r"][str(j)] = r
        o2 = find(ring[(j + 1) % n])
        if o is not None and o2 == (o + 1) % m and str(o) in curves["arc"]:
            out["arc"][str(j)] = curves["arc"][str(o)]
    return _done(_copy(prof, ring, out))


def notch(prof: dict, s0: float, z0: float, s1: float, z1: float,
          r: float = NOTCH_R) -> tuple:
    """The rectangle [s0, s1] × [z0, z1] cut off an EDGE of the shape (the
    top: a «U»; an end: the «C»; a corner: a step), its corners left
    inside the wall rounded with ``r``."""
    from shapely.geometry import box
    s0, s1 = sorted((s0, s1))
    z0, z1 = sorted((z0, z1))
    if s1 - s0 < MIN_PART or z1 - z0 < MIN_PART:
        return None, WHY_THIN
    if z0 < TOL:
        return None, WHY_FOOT
    P = _poly(prof)
    B = box(s0, z0, s1, z1)
    if not P.intersects(B) or P.intersection(B).area < 1e-9:
        return None, WHY_POINT
    if P.buffer(-1e-6).contains(B):
        return None, WHY_NOTCH_INSIDE
    for zone in _curve_zones(prof):
        if zone.intersection(B).area > 1e-9:
            return None, WHY_NOTCH_CURVE
    from shapely.geometry import Polygon
    Pc = Polygon([tuple(p) for p in prof["ctrl"]])
    got = Pc.difference(B)
    if got.geom_type != "Polygon":
        return None, WHY_TWO
    inner = P.buffer(-1e-6)
    radii = {}
    for c in ((s0, z0), (s1, z0), (s1, z1), (s0, z1)):
        from shapely.geometry import Point
        if inner.contains(Point(c)):
            radii[(round(c[0], 4), round(c[1], 4))] = r
    return _from_poly(got, prof, radii)


def to_rect(prof: dict):
    """«Back to rectangle»: the height it gives back (``was``)."""
    return prof.get("was", "level")


# ---- the length, a scale, a split -------------------------------------------------------------
def stretched(prof: dict, L: float) -> dict | None:
    """The shape on a wall now ``L`` long (the anchor rule): the points in
    its first half stay where they are from a, the others keep their place
    from b — the ends moving with their end. None: it no longer fits."""
    L0 = prof["L"]
    if abs(L - L0) < TOL:
        return prof
    d = L - L0
    ctrl = [[p[0] + d if p[0] > L0 / 2 + EPS else p[0], p[1]]
            for p in prof["ctrl"]]
    out = _copy(prof, ctrl)
    out["L"] = round(L, 4)
    out["ctrl"][1] = [out["L"], 0.0]
    return out if why_not(out) is None else None


def scaled(prof: dict, fs: float, fz: float) -> dict | None:
    """The shape scaled ``fs`` along the wall, ``fz`` up; radii and arcs
    with it (a radius by the smaller factor; an arc's sagitta by the
    stretch square to its side). None: it no longer fits."""
    ctrl = [[p[0] * fs, p[1] * fz] for p in prof["ctrl"]]
    curves = C.clean(prof.get("curves"))
    n = len(ctrl)
    out = {"r": {k: v * min(abs(fs), abs(fz)) for k, v in curves["r"].items()},
           "arc": {}}
    for k, h in curves["arc"].items():
        i = int(k)
        p, q = prof["ctrl"][i], prof["ctrl"][(i + 1) % n]
        dx, dz = q[0] - p[0], q[1] - p[1]
        L = math.hypot(dx, dz)
        if L < EPS:
            continue
        along = math.hypot(fs * dx / L, fz * dz / L)
        out["arc"][k] = h * abs(fs * fz) / max(along, EPS)
    res = _copy(prof, ctrl, out)
    res["L"] = round(prof["L"] * fs, 4)
    if isinstance(res["was"], float):
        res["was"] = round(res["was"] * fz, 4)
    res["ctrl"][1] = [res["L"], 0.0]
    return res if why_not(res) is None else None


def split_at(prof: dict, s: float) -> tuple:
    """(first, second, None) — the shape cut at ``s`` along the wall, each
    part a shape of its own (the second's s from the cut) or a height when
    it is just a rectangle — or (None, None, why)."""
    from shapely.geometry import LineString, Polygon, box
    L = prof["L"]
    if not MIN_PART <= s <= L - MIN_PART:
        return None, None, WHY_PAST
    line = LineString([(s, -1.0), (s, MAX_PEAK + 10.0)])
    for zone in _curve_zones(prof):
        if zone.buffer(1e-6).intersects(line):
            return None, None, WHY_SPLIT_CURVE
    Pc = Polygon([tuple(p) for p in prof["ctrl"]])
    top = MAX_PEAK + 10.0
    parts = []
    for lo, hi, shift in ((-1.0, s, 0.0), (s, L + 1.0, s)):
        got = Pc.intersection(box(lo, -1.0, hi, top))
        if got.geom_type != "Polygon":
            return None, None, WHY_SPLIT_FLOAT
        from shapely.affinity import translate
        got = translate(got, -shift, 0.0)
        half = dict(prof, L=round(s if shift == 0.0 else L - s, 4))
        # the old corners, moved like the part, so the curves follow
        half["ctrl"] = [[p[0] - shift, p[1]] for p in prof["ctrl"]]
        new, why = _from_poly(got, half, {})
        if why:
            return None, None, why
        h = is_rect(new)
        parts.append(h if h is not None else new)
    return parts[0], parts[1], None


# ---- ready shapes (the shape editor, phase 3 — 17/11/2026) -----------------------------
#: the cards over the drawing: (key, its name)
PRESETS = (("gable", "Gable"), ("stepped", "Stepped parapet"),
           ("round_end", "Rounded end"), ("arch_top", "Arched top"),
           ("c", "«C» open at its end"))


def preset(kind: str, L: float, h: float) -> tuple:
    """A ready shape for a wall ``L`` long, ``h`` tall (from its foot):
    (profile, None) or (None, why). Each one a starting point — its
    points drag and its sizes type as any shape's."""
    L, h = float(L), float(h)
    if L < 4 * MIN_PART or h < 4 * MIN_PART:
        return None, WHY_LENGTH
    base = {"curves": {"r": {}, "arc": {}}, "L": round(L, 4),
            "was": "level"}

    def make(ctrl):
        return _done(dict(base, ctrl=[[round(a, 4), round(b, 4)]
                                      for a, b in ctrl]))
    if kind == "gable":                 # a 30° gable over it
        rise = min(L / 2 * math.tan(math.radians(30)), MAX_PEAK - h)
        return make([[0, 0], [L, 0], [L, h], [L / 2, h + rise], [0, h]])
    if kind == "stepped":               # two steps up to its middle
        st = min(0.30, h / 4)
        f = L / 5
        return make([[0, 0], [L, 0], [L, h], [4 * f, h], [4 * f, h + st],
                     [3 * f, h + st], [3 * f, h + 2 * st],
                     [2 * f, h + 2 * st], [2 * f, h + st], [f, h + st],
                     [f, h], [0, h]])
    if kind == "round_end":             # its top corner at end B rounded
        prof, why = make([[0, 0], [L, 0], [L, h], [0, h]])
        if prof is None:
            return None, why
        return round_corner(prof, 2, round(min(h, L) / 2, 3))
    if kind == "arch_top":              # its top an arc up, its ends as tall
        prof, why = make([[0, 0], [L, 0], [L, h], [0, h]])
        if prof is None:
            return None, why
        return bend_side(prof, 2, -round(min(L / 6, MAX_PEAK - h), 3))
    if kind == "c":                     # cut open at end B, curved inside
        z0, z1 = h * 0.3, h * 0.7
        prof, why = make([[0, 0], [L, 0], [L, z0], [L * 0.4, z0],
                          [L * 0.4, z1], [L, z1], [L, h], [0, h]])
        if prof is None:
            return None, why
        r = round(min(0.3, (z1 - z0) / 2 - 0.01), 3)
        for i in (3, 4):
            got, why = round_corner(prof, i, r)
            if got is None:
                return None, why
            prof = got
        return prof, None
    return None, WHY_POINT
