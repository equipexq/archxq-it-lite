# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A SECTION's shape (the shape editor, phase 1 — 17/11/2026): the outline
of a column or a pad footing seen from above, edited as a wall's shape is
(wallshape.py) — corners to drag, rounded corners, chamfers, notches, bent
sides — but closed all round: no foot that has to stay.

A shape here is
    {"ctrl":   [[x, y], …] — control corners, ANTI-CLOCKWISE, in the
                             piece's own frame (off its insertion point,
                             before its angle — a «poly» record's ``pts``);
     "curves": {"r": {i: radius}, "arc": {i: sagitta}} — curved.py's
                             format (+ sagitta: into the shape)}.
The record keeps ``pts`` = ctrl and ``curves`` (structure.poly_world
expands them when the piece is built); a record without ``curves`` is
today's, byte for byte.

Every edit returns (shape, None) or (None, why) — the «why» in English, as
the screen shows it. Pure: math, curved.py and shapely; no host, no Qt."""
from __future__ import annotations

import math

from . import curved as C

EPS = 1e-9
TOL = 1e-6              # m: two points this close are one
NEAR = 0.005            # m: two corners closer than this are one
MIN_PART = 0.005        # m: no part thinner than this (a steel flange)
MIN_AREA = 0.05 * 0.05  # m²: structure.POLY_MIN_AREA
MAX_PTS = 64            # control corners, at most (model._outline_pts)
MAX_XY = 10.0           # m off its insertion point, at most
ROUND_R = 0.05          # m: a rounded corner, by default
CHAMFER = 0.03          # m: a chamfer, by default
NOTCH_R = 0.0           # m: a notch's inner corners, by default (square)
BEND = 0.05             # m: a bent side's bulge, by default

WHY_FEW = "A shape needs three points at least"
WHY_MANY = "At most 64 points"
WHY_FAR = "Within 10 m of its insertion point"
WHY_SAME = "Two corners on top of each other"
WHY_CROSS = "The shape crosses itself"
WHY_THIN = "Somewhere it's thinner than 5 mm"
WHY_SMALL = "Too small — 5 × 5 cm at least"
WHY_POINT = "No such point"
WHY_CHAMFER_SIDES = "A chamfer needs two straight sides"
WHY_CHAMFER_FIT = "The chamfer doesn't fit the sides"
WHY_NOTCH_CURVE = "A notch cuts straight sides only — straighten that side first"
WHY_NOTCH_INSIDE = "Inside the shape: that would be a hole — drag over an edge"
WHY_TWO = "It would cut it in two"
WHY_MISS = "Drag the rectangle over an edge of the shape"


# ---- the data ------------------------------------------------------------------------
def _pt(p) -> list:
    return [round(float(p[0]), 6) + 0.0, round(float(p[1]), 6) + 0.0]


def signed_area(ctrl) -> float:
    n = len(ctrl)
    return 0.5 * sum(ctrl[i][0] * ctrl[(i + 1) % n][1]
                     - ctrl[(i + 1) % n][0] * ctrl[i][1] for i in range(n))


def reversed_shape(ctrl, curves) -> tuple:
    """(ctrl, curves) run the other way round: corner i becomes n-1-i, side
    i (i → i+1) becomes n-2-i, its sagitta's sign turned (left ↔ right)."""
    n = len(ctrl)
    cv = C.clean(curves)
    out = {"r": {}, "arc": {}}
    for k, v in cv["r"].items():
        out["r"][str(n - 1 - int(k))] = v
    for k, v in cv["arc"].items():
        out["arc"][str((n - 2 - int(k)) % n)] = -v
    return [list(p) for p in reversed(ctrl)], out


def ccw(ctrl, curves=None) -> tuple:
    """(ctrl, curves) anti-clockwise (as they are when they already are)."""
    if signed_area(ctrl) >= 0:
        return [list(p) for p in ctrl], C.clean(curves)
    return reversed_shape(ctrl, curves)


def make(ctrl, curves=None) -> dict:
    """A shape as kept: points to the micron, the curves clean."""
    return {"ctrl": [_pt(p) for p in ctrl], "curves": C.clean(curves)}


def fine(prof: dict) -> list:
    """The outline in fine steps (each curve within 1 mm)."""
    return C.expand(prof["ctrl"], prof.get("curves"))


def area(prof: dict) -> float:
    """Its area, exact (circular sectors and segments)."""
    return abs(C.area(prof["ctrl"], prof.get("curves")))


def box(prof: dict) -> tuple:
    """(x0, y0, x1, y1) round the shape as built, EXACT: its arcs' own
    farthest points (never the fine steps, a hair outside the circle)."""
    return box_of(prof["ctrl"], prof.get("curves"))


def box_of(ctrl, curves) -> tuple:
    xs, ys = [], []
    for pc in C.pieces(ctrl, curves):
        xs += [pc[1][0], pc[2][0]]
        ys += [pc[1][1], pc[2][1]]
        if pc[0] != "arc":
            continue
        _k, a, _b, c, R, sw = pc
        a0 = math.atan2(a[1] - c[1], a[0] - c[0])
        for k in range(4):                  # the circle's E, N, W, S
            th = k * math.pi / 2
            d = ((th - a0) if sw > 0 else (a0 - th)) % (2 * math.pi)
            if d <= abs(sw) + 1e-12:
                xs.append(c[0] + R * math.cos(th))
                ys.append(c[1] + R * math.sin(th))
    return min(xs), min(ys), max(xs), max(ys)


def is_curved(prof: dict) -> bool:
    c = C.clean(prof.get("curves"))
    return bool(c["r"] or c["arc"])


def as_rect(prof: dict) -> tuple | None:
    """(x0, y0, x1, y1) when the shape is a plain rectangle along its own
    axes; else None."""
    if is_curved(prof) or len(prof["ctrl"]) != 4:
        return None
    pts = prof["ctrl"]
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        if abs(a[0] - b[0]) > TOL and abs(a[1] - b[1]) > TOL:
            return None
    x0, y0, x1, y1 = box(prof)
    if x1 - x0 < TOL or y1 - y0 < TOL:
        return None
    return x0, y0, x1, y1


def as_circle(prof: dict) -> tuple | None:
    """(cx, cy, diameter) when the shape is a circle — a square along its
    axes, each corner rounded with half its side —; else None."""
    pts = prof["ctrl"]
    cv = C.clean(prof.get("curves"))
    if len(pts) != 4 or cv["arc"] or len(cv["r"]) != 4:
        return None
    rect = as_rect({"ctrl": pts, "curves": {}})
    if rect is None:
        return None
    x0, y0, x1, y1 = rect
    s = x1 - x0
    if abs((y1 - y0) - s) > TOL or any(abs(float(v) - s / 2) > TOL
                                       for v in cv["r"].values()):
        return None
    return (x0 + x1) / 2, (y0 + y1) / 2, s


# ---- is it a shape? ------------------------------------------------------------------
def _poly(prof: dict):
    from shapely.geometry import Polygon
    return Polygon(fine(prof))


def why_not(prof: dict) -> str | None:
    """Why this can't be a section's shape (None = it can)."""
    ctrl = prof.get("ctrl") or []
    n = len(ctrl)
    if n < 3:
        return WHY_FEW
    if n > MAX_PTS:
        return WHY_MANY
    if any(abs(v) > MAX_XY + TOL for p in ctrl for v in p):
        return WHY_FAR
    for i in range(n):
        if math.dist(ctrl[i], ctrl[(i + 1) % n]) < NEAR:
            return WHY_SAME
    if signed_area(ctrl) <= 0:
        return WHY_CROSS
    curves = prof.get("curves") or {}
    why = C.why_not(ctrl, curves)
    if why:
        return why
    pts = fine(prof)
    if any(abs(v) > MAX_XY + TOL for p in pts for v in p):
        return WHY_FAR
    if area(prof) < MIN_AREA - 1e-9:
        return WHY_SMALL
    try:
        P = _poly(prof)
    except Exception:  # noqa: BLE001 — not even a ring
        return WHY_CROSS
    if not P.is_valid or C.area(ctrl, curves) <= 0:
        return WHY_CROSS
    # thinner than MIN_PART somewhere: eroding by half of it and growing
    # back loses a piece (a fin, a neck) — or splits it
    core = P.buffer(-MIN_PART / 2 + 1e-7, join_style="mitre")
    if core.is_empty or core.geom_type != "Polygon":
        return WHY_THIN
    back = core.buffer(MIN_PART / 2 - 1e-7, join_style="mitre",
                       mitre_limit=50.0)
    if P.difference(back).area > 1e-6:
        return WHY_THIN
    return None


def _done(prof: dict) -> tuple:
    why = why_not(prof)
    return (None, why) if why else (prof, None)


def _copy(prof: dict, ctrl=None, curves=None) -> dict:
    return make(ctrl if ctrl is not None else prof["ctrl"],
                curves if curves is not None else prof.get("curves"))


# ---- the edits -----------------------------------------------------------------------
def move_point(prof: dict, i: int, x: float, y: float) -> tuple:
    """Control corner ``i`` to (x, y)."""
    if not 0 <= i < len(prof["ctrl"]):
        return None, WHY_POINT
    ctrl = [list(p) for p in prof["ctrl"]]
    ctrl[i] = [x, y]
    return _done(_copy(prof, ctrl))


def move_side(prof: dict, i: int, d: float) -> tuple:
    """Side ``i`` (corner i → i+1) moved ``d`` square to itself (+ = to its
    left, into the shape — the sign of curved.py)."""
    ctrl = [list(p) for p in prof["ctrl"]]
    n = len(ctrl)
    if not 0 <= i < n:
        return None, WHY_POINT
    j = (i + 1) % n
    p, q = ctrl[i], ctrl[j]
    L = math.hypot(q[0] - p[0], q[1] - p[1])
    if L < EPS:
        return None, WHY_POINT
    nx, ny = -(q[1] - p[1]) / L, (q[0] - p[0]) / L
    for k in (i, j):
        ctrl[k] = [ctrl[k][0] + nx * d, ctrl[k][1] + ny * d]
    return _done(_copy(prof, ctrl))


def add_point(prof: dict, i: int, at) -> tuple:
    """A new control corner on side ``i``, at the point of it nearest
    ``at``. An arc on that side is dropped (as on slabs)."""
    ctrl = [list(p) for p in prof["ctrl"]]
    n = len(ctrl)
    if not 0 <= i < n:
        return None, WHY_POINT
    p, q = ctrl[i], ctrl[(i + 1) % n]
    dx, dy = q[0] - p[0], q[1] - p[1]
    LL = dx * dx + dy * dy
    t = 0.5 if LL < EPS else ((at[0] - p[0]) * dx + (at[1] - p[1]) * dy) / LL
    t = min(max(t, 0.05), 0.95)
    new = ctrl[:i + 1] + [[p[0] + dx * t, p[1] + dy * t]] + ctrl[i + 1:]
    curves, _dropped = C.remap(ctrl, new, prof.get("curves"))
    return _done(_copy(prof, new, curves))


def delete_point(prof: dict, i: int) -> tuple:
    """Control corner ``i`` taken off."""
    ctrl = [list(p) for p in prof["ctrl"]]
    if not 0 <= i < len(ctrl):
        return None, WHY_POINT
    if len(ctrl) <= 3:
        return None, WHY_FEW
    new = ctrl[:i] + ctrl[i + 1:]
    curves, _dropped = C.remap(ctrl, new, prof.get("curves"))
    return _done(_copy(prof, new, curves))


def round_corner(prof: dict, i: int, r: float = ROUND_R) -> tuple:
    """Corner ``i`` rounded with radius ``r`` (0: square again)."""
    if not 0 <= i < len(prof["ctrl"]):
        return None, WHY_POINT
    curves = C.clean(prof.get("curves"))
    curves["r"].pop(str(i), None)
    if r > EPS:
        curves["r"][str(i)] = r
    return _done(_copy(prof, curves=curves))


def bend_side(prof: dict, i: int, h: float = BEND) -> tuple:
    """Side ``i`` bent into an arc whose middle stands ``h`` off it (+ =
    into the shape, − = outwards; 0: straight again)."""
    if not 0 <= i < len(prof["ctrl"]):
        return None, WHY_POINT
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
    curves = C.clean(prof.get("curves"))
    rs, arcs = curves["r"], curves["arc"]
    if C._key(arcs, (i - 1) % n) or C._key(arcs, i) or C._key(rs, i):
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
    if C.why_not(prof2["ctrl"], prof2["curves"]):
        return None, WHY_CHAMFER_FIT
    return _done(prof2)


def _tagged(ctrl, curves) -> list:
    """The outline's pieces as («line» | «arc», their points)."""
    out = []
    for pc in C.pieces(ctrl, curves):
        if pc[0] == "arc":
            _kind, a, b, c, R, sw = pc
            out.append(("arc", [a] + C._arc_pts(c, R, a, sw) + [b]))
        else:
            out.append(("line", [pc[1], pc[2]]))
    return out


def _curve_zones(prof: dict) -> list:
    """Polygons covering each curve of the shape (a rounded corner: its
    arc and its corner; an arc on a side: arc and chord)."""
    from shapely.geometry import LineString, Polygon
    ctrl, curves = prof["ctrl"], prof.get("curves")
    rs = (curves or {}).get("r") or {}
    out = []
    for kind, run in _tagged(ctrl, curves):
        if kind != "arc":
            continue
        ring = list(run)
        for i, p in enumerate(ctrl):
            if C._key(rs, i):
                f = C.fillet(ctrl[i - 1], p, ctrl[(i + 1) % len(ctrl)],
                             C._key(rs, i))
                if f and math.dist(f[0], run[0]) < 1e-6:
                    ring = ring + [tuple(p)]
                    break
        if len(ring) >= 3:
            out.append(Polygon(ring).buffer(0))
        else:
            out.append(LineString(ring).buffer(1e-6))
    return out


def _straighten(ctrl: list) -> list:
    """Drop the points in a straight line between their neighbours."""
    out = [list(p) for p in ctrl]
    i = 0
    while i < len(out) and len(out) > 3:
        p, q, r = out[i - 1], out[i], out[(i + 1) % len(out)]
        cr = (q[0] - p[0]) * (r[1] - q[1]) - (q[1] - p[1]) * (r[0] - q[0])
        if abs(cr) < 1e-10 and (q[0] - p[0]) * (r[0] - q[0]) \
                + (q[1] - p[1]) * (r[1] - q[1]) > 0:
            out.pop(i)
        else:
            i += 1
    return out


def _from_poly(poly, prof: dict, radii: dict) -> tuple:
    """A shapely polygon back to a shape: anti-clockwise, starting where the
    old one did when that corner is still there, the old curves kept on the
    corners and sides that are still there and ``radii`` ({(x, y): r}) on
    new corners."""
    from shapely.geometry.polygon import orient
    if poly.geom_type != "Polygon":
        return None, WHY_TWO
    if len(poly.interiors):
        return None, WHY_NOTCH_INSIDE
    ring = [(round(x, 6) + 0.0, round(y, 6) + 0.0)
            for x, y in list(orient(poly, 1.0).exterior.coords)[:-1]]
    ring = _straighten([list(p) for p in ring])
    old = [tuple(p) for p in prof["ctrl"]]

    def find(p, pts):
        return next((j for j, q in enumerate(pts)
                     if abs(q[0] - p[0]) < 1e-6 and abs(q[1] - p[1]) < 1e-6),
                    None)
    k = find(old[0], ring)
    if k is None:                          # the lowest, then leftmost
        k = min(range(len(ring)), key=lambda j: (ring[j][1], ring[j][0]))
    ring = ring[k:] + ring[:k]
    curves = C.clean(prof.get("curves"))
    out = {"r": {}, "arc": {}}
    n, m = len(ring), len(old)
    for j, p in enumerate(ring):
        o = find(p, old)
        if o is not None and str(o) in curves["r"]:
            out["r"][str(j)] = curves["r"][str(o)]
        for (rx, ry), r in radii.items():
            if abs(rx - p[0]) < 1e-6 and abs(ry - p[1]) < 1e-6 and r > EPS:
                out["r"][str(j)] = r
        o2 = find(ring[(j + 1) % n], old)
        if o is not None and o2 == (o + 1) % m and str(o) in curves["arc"]:
            out["arc"][str(j)] = curves["arc"][str(o)]
    return _done(_copy(prof, ring, out))


def notch(prof: dict, x0: float, y0: float, x1: float, y1: float,
          r: float = NOTCH_R) -> tuple:
    """The rectangle [x0, x1] × [y0, y1] cut off an EDGE of the shape (a
    side: a «U» or a «C»; a corner: an «L»), its corners left inside the
    shape rounded with ``r``."""
    from shapely.geometry import Point, Polygon
    from shapely.geometry import box as sbox
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    if x1 - x0 < MIN_PART or y1 - y0 < MIN_PART:
        return None, WHY_THIN
    P = _poly(prof)
    B = sbox(x0, y0, x1, y1)
    if not P.intersects(B) or P.intersection(B).area < 1e-9:
        return None, WHY_MISS
    if P.buffer(-1e-6).contains(B):
        return None, WHY_NOTCH_INSIDE
    for zone in _curve_zones(prof):
        if zone.intersection(B).area > 1e-9:
            return None, WHY_NOTCH_CURVE
    Pc = Polygon([tuple(p) for p in prof["ctrl"]])
    got = Pc.difference(B)
    if got.is_empty:
        return None, WHY_SMALL
    if got.geom_type != "Polygon":
        return None, WHY_TWO
    inner = P.buffer(-1e-6)
    radii = {}
    for c in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        if inner.contains(Point(c)):
            radii[(round(c[0], 6), round(c[1], 6))] = r
    return _from_poly(got, prof, radii)


def scaled(prof: dict, fx: float, fy: float) -> dict | None:
    """The shape scaled ``fx`` along its own x, ``fy`` along its y; radii
    and arcs with it (a radius by the smaller factor; an arc's sagitta by
    the stretch square to its side). A mirror (one factor negative) turns
    it round, so it stays anti-clockwise. None: it no longer fits."""
    ctrl = [[p[0] * fx, p[1] * fy] for p in prof["ctrl"]]
    curves = C.clean(prof.get("curves"))
    n = len(ctrl)
    out = {"r": {k: v * min(abs(fx), abs(fy)) for k, v in curves["r"].items()},
           "arc": {}}
    for k, h in curves["arc"].items():
        i = int(k)
        p, q = prof["ctrl"][i], prof["ctrl"][(i + 1) % n]
        dx, dy = q[0] - p[0], q[1] - p[1]
        L = math.hypot(dx, dy)
        if L < EPS:
            continue
        along = math.hypot(fx * dx / L, fy * dy / L)
        # (the sagitta keeps its side of the line: a mirror swaps it, and
        # turning the loop round below swaps it back)
        out["arc"][k] = h * abs(fx * fy) / max(along, EPS) * \
            (1 if fx * fy > 0 else -1)
    if fx * fy < 0:
        ctrl, out = reversed_shape(ctrl, out)
    res = make(ctrl, out)
    return res if why_not(res) is None else None


# ---- from a record, back to one ------------------------------------------------------
ANCHORS = {"centre": (0, 0), "sw": (-1, -1), "corner": (-1, -1),
           "s": (0, -1), "se": (1, -1), "e": (1, 0), "ne": (1, 1),
           "n": (0, 1), "nw": (-1, 1), "w": (-1, 0)}


def _rect(cx: float, cy: float, w: float, d: float) -> list:
    return [[cx - w / 2, cy - d / 2], [cx + w / 2, cy - d / 2],
            [cx + w / 2, cy + d / 2], [cx - w / 2, cy + d / 2]]


def from_record(e: dict) -> dict:
    """The shape of a column's / a pad's section, in its own frame: its
    outline («poly»), its rectangle (off its insertion point when that is
    a corner or a side's middle), its square (a pad), or its circle (a
    square with each corner rounded by half its side)."""
    if e.get("shape") == "poly" and len(e.get("pts") or ()) >= 3:
        ctrl, cv = ccw([[float(p[0]), float(p[1])] for p in e["pts"]],
                       e.get("curves"))
        return make(ctrl, cv)
    w = float(e.get("w", 0.3))
    if e.get("type") == "footing":
        return make(_rect(0.0, 0.0, w, w))
    if e.get("shape") == "round":
        r = w / 2
        return make(_rect(0.0, 0.0, w, w),
                    {"r": {str(i): r for i in range(4)}, "arc": {}})
    d = float(e.get("d", w))
    ax, ay = ANCHORS.get(e.get("anchor", "centre"), (0, 0))
    return make(_rect(-ax * w / 2, -ay * d / 2, w, d))


def to_record(e: dict, prof: dict) -> dict:
    """``e`` with the shape ``prof`` (in its own frame, as from_record gave
    it): back to a plain circle / rectangle / square when it is one (its
    insertion point to its middle), else its own outline («poly», ``pts`` +
    ``curves``, its box as w, d)."""
    r = {k: v for k, v in e.items() if k not in ("pts", "curves")}
    a = math.radians(float(e.get("angle", 0.0)))
    ca, sa = math.cos(a), math.sin(a)

    def at(cx, cy):
        return (round(float(e["x"]) + cx * ca - cy * sa, 4),
                round(float(e["y"]) + cx * sa + cy * ca, 4))
    pad = e.get("type") == "footing"
    circ = None if pad else as_circle(prof)
    if circ is not None:
        cx, cy, dia = circ
        r["x"], r["y"] = at(cx, cy)
        r.update(shape="round", w=round(dia, 4), d=round(dia, 4),
                 anchor="centre")
        return r
    rect = as_rect(prof)
    if rect is not None:
        x0, y0, x1, y1 = rect
        w_, d_ = x1 - x0, y1 - y0
        if not pad or abs(w_ - d_) < TOL:
            r["x"], r["y"] = at((x0 + x1) / 2, (y0 + y1) / 2)
            r["w"] = round(w_, 4)
            if pad:                        # (a pad's «d» is its depth)
                r.pop("shape", None)
            else:
                r.update(shape="rect", anchor="centre", d=round(d_, 4))
            return r
    x0, y0, x1, y1 = box(prof)
    r["pts"] = [_pt(p) for p in prof["ctrl"]]
    cv = C.clean(prof.get("curves"))
    if cv["r"] or cv["arc"]:
        r["curves"] = cv
    r["shape"] = "poly"
    if not pad:
        r["anchor"] = "centre"
        r["w"], r["d"] = round(x1 - x0, 4), round(y1 - y0, 4)
    else:
        r["w"] = round(max(x1 - x0, y1 - y0), 4)
    return r
