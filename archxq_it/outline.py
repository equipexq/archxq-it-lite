"""«Slab from outline» (PLANO_CURVAS_E_FORMAS.md, F3a — 13/11/2026): lines
or a flat face drawn in IngeTrazo become a real ArchXQ slab. Pure: no Qt,
no host.

    loops_from_segments  the selected lines → closed level loops (or why not)
    nest                 loops → [(outline, [openings])] (inside = opening)
    fit                  a loop's points → (ctrl, curves): the runs of points
                         on one circle become ARCS (curved.py), an arc that
                         meets two straight sides tangent becomes a corner's
                         RADIUS — editable like any slab drawn with arcs
    level_for            the loop's height → (level index, top offset)
"""
from __future__ import annotations

import math

from . import curved as CV

TOL = 0.001            # a point off the circle by at most this: on the arc
JOIN = 1e-4            # two line ends this close: the same point
FLAT = 0.001           # a loop's heights within this: level
MAX_STEP_DEG = 24.0    # an arc's pieces turn at most this each (a square's
                       # corners lie on a circle too: 90°; a 12-sided one
                       # 30° — not arcs; IngeTrazo's Arc: 16 pieces)
TANGENT_DEG = 0.5      # an arc meeting a straight side this close: tangent


# ---- the lines → loops ---------------------------------------------------------------
def _k(p) -> tuple:
    return (round(p[0] / JOIN), round(p[1] / JOIN), round(p[2] / JOIN))


def loops_from_segments(segs) -> tuple[list, str | None]:
    """([loop of (x, y, z)…], why not): every line used once, each point
    meeting exactly two lines — closed loops, nothing branching, nothing
    left open."""
    if not segs:
        return [], "Select the lines of a closed outline"
    pos, nbr = {}, {}
    for a, b in segs:
        ka, kb = _k(a), _k(b)
        if ka == kb:
            continue
        pos.setdefault(ka, tuple(map(float, a)))
        pos.setdefault(kb, tuple(map(float, b)))
        nbr.setdefault(ka, []).append(kb)
        nbr.setdefault(kb, []).append(ka)
    if not nbr:
        return [], "Select the lines of a closed outline"
    if any(len(v) == 1 for v in nbr.values()):
        return [], "The lines don't close — an end is left open"
    if any(len(v) != 2 for v in nbr.values()):
        return [], "The lines branch — select one closed outline (or a few)"
    seen, loops = set(), []
    for start in nbr:
        if start in seen:
            continue
        loop, prev, cur = [], None, start
        while True:
            seen.add(cur)
            loop.append(pos[cur])
            a, b = nbr[cur]
            nxt = a if a != prev else b
            prev, cur = cur, nxt
            if cur == start:
                break
        if len(loop) >= 3:
            loops.append(loop)
    if not loops:
        return [], "Select the lines of a closed outline"
    return loops, None


def level_loops(loops) -> tuple[float | None, str | None]:
    """(their height, why not): every loop level, all at one height."""
    zs = [p[2] for lp in loops for p in lp]
    if not zs:
        return None, "Select the lines of a closed outline"
    if max(zs) - min(zs) > FLAT:
        return None, "Not level — the outline must lie flat, at one height"
    return sum(zs) / len(zs), None


# ---- loops → slabs with their openings ----------------------------------------------
def area2(pts) -> float:
    """Signed area (counter-clockwise +)."""
    return sum(p[0] * q[1] - q[0] * p[1]
               for p, q in zip(pts, pts[1:] + pts[:1])) / 2


def _inside(pt, poly) -> bool:
    x, y = pt
    c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and \
                x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def _seg_cross(s, t) -> bool:
    """Two sides crossing (touching ends aside)."""
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    (p1, p2), (q1, q2) = s, t
    d1, d2 = side(q1, q2, p1), side(q1, q2, p2)
    d3, d4 = side(p1, p2, q1), side(p1, p2, q2)
    return ((d1 > 1e-12 and d2 < -1e-12) or (d1 < -1e-12 and d2 > 1e-12))         and ((d3 > 1e-12 and d4 < -1e-12) or (d3 < -1e-12 and d4 > 1e-12))


def _sides(lp) -> list:
    return list(zip(lp, lp[1:] + lp[:1]))


def _crosses(a, b) -> bool:
    """Two loops' sides crossing."""
    return any(_seg_cross(s, t) for s in _sides(a) for t in _sides(b))


def _self_crossing(lp) -> bool:
    sides = _sides(lp)
    n = len(sides)
    return any(_seg_cross(sides[i], sides[j]) for i in range(n)
               for j in range(i + 2, n) if not (i == 0 and j == n - 1))


def nest(loops) -> tuple[list, str | None]:
    """[(outline, [openings])], why not — plan loops (x, y): a loop inside
    another is its opening, one inside an opening a slab again (an island)."""
    lps = [[(float(p[0]), float(p[1])) for p in lp] for lp in loops]
    for lp in lps:
        if abs(area2(lp)) < 1e-4:
            return [], "Too small for a slab"
        if _self_crossing(lp):
            return [], "The outline crosses itself"
    for i in range(len(lps)):
        for j in range(i + 1, len(lps)):
            if _crosses(lps[i], lps[j]):
                return [], "Two of the outlines cross each other"
    order = sorted(range(len(lps)), key=lambda i: -abs(area2(lps[i])))
    parent = {}
    for pos, i in enumerate(order):
        parent[i] = None
        for j in reversed(order[:pos]):            # the smallest around it
            if _inside(lps[i][0], lps[j]):
                parent[i] = j
                break
    depth = {}

    def d(i):
        if i not in depth:
            depth[i] = 0 if parent[i] is None else d(parent[i]) + 1
        return depth[i]
    out = []
    for i in order:
        if d(i) % 2 == 0:
            holes = [ccw(lps[k]) for k in order
                     if parent[k] == i and d(k) == d(i) + 1]
            out.append((ccw(lps[i]), holes))
    return out, None


def ccw(lp) -> list:
    lp = [tuple(p) for p in lp]
    return lp if area2(lp) > 0 else lp[::-1]


# ---- a loop's points → corners + arcs (curved.py) -----------------------------------
def clean(lp) -> list:
    """No repeated points, no point in the middle of a straight side."""
    pts = []
    for p in lp:
        if not pts or math.dist(p, pts[-1]) > JOIN:
            pts.append((float(p[0]), float(p[1])))
    if len(pts) > 1 and math.dist(pts[0], pts[-1]) <= JOIN:
        pts.pop()
    changed = True
    while changed and len(pts) > 3:
        changed = False
        for i in range(len(pts)):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            L = math.dist(a, c)
            if L < JOIN:
                continue
            off = abs((c[0] - a[0]) * (b[1] - a[1])
                      - (c[1] - a[1]) * (b[0] - a[0])) / L
            dot = (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1])
            if off < 1e-5 and dot > 0:
                pts.pop(i)
                changed = True
                break
    return pts


def _circle(a, b, c):
    """(centre, radius) through three points — None in line."""
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay)
          + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx)
          + (cx * cx + cy * cy) * (bx - ax)) / d
    return (ux, uy), math.dist((ux, uy), a)


def _turn(a, b, c) -> float:
    """The signed turn at b (radians, left +)."""
    t1 = math.atan2(b[1] - a[1], b[0] - a[0])
    t2 = math.atan2(c[1] - b[1], c[0] - b[0])
    return (t2 - t1 + math.pi) % (2 * math.pi) - math.pi


def _arc_run(P, i, j):
    """The circle of the points P[i..j] (indices may pass the end) when
    they make ONE arc: (centre, R) — else None."""
    n = len(P)
    pts = [P[k % n] for k in range(i, j + 1)]
    if len(pts) < 4:
        return None
    circ = _circle(pts[0], pts[len(pts) // 2], pts[-1])
    if circ is None:
        return None
    c, R = circ
    if any(abs(math.dist(c, p) - R) > TOL for p in pts):
        return None
    lim = math.radians(MAX_STEP_DEG)
    turns = [_turn(pts[k - 1], pts[k], pts[k + 1])
             for k in range(1, len(pts) - 1)]
    if any(abs(t) > lim or abs(t) < 1e-9 for t in turns):
        return None
    if not (all(t > 0 for t in turns) or all(t < 0 for t in turns)):
        return None
    for p, q in zip(pts, pts[1:]):              # each piece's own angle
        if 2 * math.asin(min(1.0, math.dist(p, q) / (2 * R))) > lim:
            return None
    return c, R


def _sag(a, b, c, R, left: bool) -> float:
    """The sagitta of the arc a → b about c (``left``: turning left)."""
    L = math.dist(a, b)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    nx, ny = -uy, ux                              # left of a → b
    # the arc's middle: on the circle, on the side it bulges
    d = (c[0] - mx) * nx + (c[1] - my) * ny       # the centre's side
    half = math.sqrt(max(R * R - (L / 2) ** 2, 0.0))
    # turning left (ccw) the arc bulges to the RIGHT of the chord
    side = -1.0 if left else 1.0
    # the middle of the arc lies at centre + R·(the bulge direction)
    if (d > 0) == left:              # the short arc (centre on the turn side)
        h = R - half
    else:                            # the long one (more than half a circle)
        h = R + half
    return side * h


def _pieces_of(c, R, a, b, left: bool, sweep: float) -> list:
    """The arc a → b split where it turns past 240° (a side's arc goes at
    most its chord deep — 253°): [(start, end)…] on the circle."""
    k = max(1, math.ceil(abs(sweep) / math.radians(240) - 1e-9))
    a0 = math.atan2(a[1] - c[1], a[0] - c[0])
    out, p = [], a
    for m in range(1, k + 1):
        if m == k:
            q = b
        else:
            t = a0 + sweep * m / k
            q = (c[0] + R * math.cos(t), c[1] + R * math.sin(t))
        out.append((p, q))
        p = q
    return out


def _start_index(P) -> int | None:
    """A point no arc goes through: the sharpest corner; with none sharp,
    the start of the longest side. None: the loop is one circle."""
    n = len(P)
    turns = [abs(_turn(P[i - 1], P[i], P[(i + 1) % n])) for i in range(n)]
    k = max(range(n), key=lambda i: turns[i])
    if turns[k] > math.radians(MAX_STEP_DEG):
        return k
    if n >= 8:
        circ = _circle(P[0], P[n // 3], P[2 * n // 3])
        if circ and all(abs(math.dist(circ[0], p) - circ[1]) <= TOL
                        for p in P):
            return None
    return max(range(n), key=lambda i: math.dist(P[i], P[(i + 1) % n]))


def fit(lp) -> tuple[list, dict]:
    """(ctrl, curves) for a plan loop (counter-clockwise): its arcs found,
    its tangent arcs between straight sides made a corner's radius."""
    P = clean(lp)
    n = len(P)
    if n < 3:
        return [list(p) for p in P], {}
    s = _start_index(P)
    if s is None:                                 # a whole circle
        c, R = _circle(P[0], P[n // 3], P[2 * n // 3])
        a0 = math.atan2(P[0][1] - c[1], P[0][0] - c[0])
        ctrl = [[c[0] + R * math.cos(a0 + k * 2 * math.pi / 3),
                 c[1] + R * math.sin(a0 + k * 2 * math.pi / 3)]
                for k in range(3)]
        left = area2(P) > 0
        arc = {str(i): _sag(ctrl[i], ctrl[(i + 1) % 3], c, R, left)
               for i in range(3)}
        return ctrl, CV.clean({"arc": arc})
    P = P[s:] + P[:s]
    # the pieces: ("line", p, q) / ("arc", p, q, c, R, sweep)
    pieces, i = [], 0
    while i < n:
        best = None
        j = i + 3
        while j <= n and _arc_run(P, i, j) is not None:
            best = (j, _arc_run(P, i, j))
            j += 1
        if best is None:
            pieces.append(("line", P[i], P[(i + 1) % n]))
            i += 1
            continue
        j, (c, R) = best
        R = round(R, 3)              # to the mm (the points: within 1 mm)
        sweep = sum(_turn(P[(k - 1) % n], P[k % n], P[(k + 1) % n])
                    for k in range(i + 1, j))
        # the turns at the inner points add to the sweep less one piece's
        step = sweep / max(j - i - 1, 1)
        sweep += step
        a, b = P[i], P[j % n]
        pieces.append(("arc", a, b, c, R, sweep))
        i = j
    ctrl, arcs, rads = [], {}, {}
    plain = []                                   # (the arcs kept as arcs)
    for pc in pieces:
        if pc[0] == "line":
            plain.append(("line", pc[1]))
        else:
            _t, a, b, c, R, sweep = pc
            for p, q in _pieces_of(c, R, a, b, sweep > 0, sweep):
                plain.append(("arc", p, q, c, R, sweep > 0))
    for k, pc in enumerate(plain):
        ctrl.append([pc[1][0], pc[1][1]])
        if pc[0] == "arc":
            arcs[str(k)] = _sag(pc[1], pc[2], pc[3], pc[4], pc[5])
    curves = CV.clean({"arc": arcs})
    rounded = _fillets(plain)
    if rounded is not None:
        return rounded
    return ctrl, curves


def _fillets(plain):
    """The same outline with every arc that meets two straight sides
    tangent (and turns less than half a circle) as that corner's radius —
    None when there is none, or it wouldn't stand."""
    n = len(plain)
    if n < 3:
        return None
    lim = math.radians(TANGENT_DEG)

    def dirn(p, q):
        return math.atan2(q[1] - p[1], q[0] - p[0])

    def end_of(k):                               # the end point of piece k
        return plain[(k + 1) % n][1]
    take = set()
    for k, pc in enumerate(plain):
        if pc[0] != "arc":
            continue
        pv, nx = plain[k - 1], plain[(k + 1) % n]
        if pv[0] != "line" or nx[0] != "line" or (k - 1) % n in take:
            continue
        a, b, c, R, left = pc[1], pc[2], pc[3], pc[4], pc[5]
        # the arc's tangent at a and at b (turning left: ccw about c)
        ta = math.atan2(a[1] - c[1], a[0] - c[0]) + (math.pi / 2 if left
                                                     else -math.pi / 2)
        tb = math.atan2(b[1] - c[1], b[0] - c[0]) + (math.pi / 2 if left
                                                     else -math.pi / 2)
        d_in = dirn(pv[1], a)
        d_out = dirn(b, end_of((k + 1) % n))

        def same(x, y):
            return abs((x - y + math.pi) % (2 * math.pi) - math.pi) <= lim
        if not (same(ta, d_in) and same(tb, d_out)):
            continue
        turn = (d_out - d_in + math.pi) % (2 * math.pi) - math.pi
        if abs(turn) >= math.pi - 1e-6 or abs(turn) < 1e-6:
            continue
        take.add(k)
    if not take:
        return None
    ctrl, rads, arcs = [], {}, {}
    k = 0
    order = list(range(n))
    for k in order:
        pc = plain[k]
        if k in take:
            continue
        if pc[0] == "line" and (k - 1) % n in take:
            # the corner where the line before the arc meets this one
            arcp = plain[(k - 1) % n]
            pv = plain[(k - 2) % n]
            X = _meet(pv[1], arcp[1], arcp[2], end_of(k))
            if X is None:
                return None
            ctrl.append([X[0], X[1]])
            # its radius from where the arc leaves the two sides (exact:
            # those points ARE on the sides), not from the fitted circle
            d_in = math.atan2(arcp[1][1] - pv[1][1], arcp[1][0] - pv[1][0])
            d_out = math.atan2(end_of(k)[1] - arcp[2][1],
                               end_of(k)[0] - arcp[2][0])
            tau = abs((d_out - d_in + math.pi) % (2 * math.pi) - math.pi)
            t = (math.dist(X, arcp[1]) + math.dist(X, arcp[2])) / 2
            rads[str(len(ctrl) - 1)] = round(t / math.tan(tau / 2), 4)
            continue
        ctrl.append([pc[1][0], pc[1][1]])
        if pc[0] == "arc":
            arcs[str(len(ctrl) - 1)] = _sag(pc[1], pc[2], pc[3], pc[4], pc[5])
    # the line before a taken arc: its end is now the corner (it was the
    # arc's start) — already so, as ctrl holds starts only
    curves = CV.clean({"r": rads, "arc": arcs})
    if CV.why_not(ctrl, curves) is not None:
        return None
    return ctrl, curves


def _meet(p1, p2, q1, q2):
    """Where the line p1 → p2 meets the line q1 → q2 (None: parallel)."""
    d1 = (p2[0] - p1[0], p2[1] - p1[1])
    d2 = (q2[0] - q1[0], q2[1] - q1[1])
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-12:
        return None
    t = ((q1[0] - p1[0]) * d2[1] - (q1[1] - p1[1]) * d2[0]) / den
    return (p1[0] + d1[0] * t, p1[1] + d1[1] * t)


def off_by(lp, ctrl, curves) -> float:
    """The farthest the loop's points stand off the made outline."""
    poly = CV.expand(ctrl, curves)
    worst = 0.0
    for p in lp:
        best = math.inf
        for a, b in zip(poly, poly[1:] + poly[:1]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, (
                (p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
            best = min(best, math.hypot(p[0] - a[0] - dx * t,
                                        p[1] - a[1] - dy * t))
        worst = max(worst, best)
    return worst


def shape(lp) -> tuple[list, dict]:
    """(ctrl, curves) for a loop — its arcs only when the outline they make
    keeps every one of its points (else its corners as they are)."""
    ccw_lp = ccw(lp)
    try:
        ctrl, curves = fit(ccw_lp)
    except (ValueError, ZeroDivisionError):
        ctrl, curves = [list(p) for p in clean(ccw_lp)], {}
    curves = CV.clean(curves)
    if (curves["r"] or curves["arc"]) and (
            CV.why_not(ctrl, curves) is not None
            or off_by(ccw_lp, ctrl, curves) > 2 * TOL):
        return [list(p) for p in clean(ccw_lp)], {}
    return ctrl, curves


# ---- the level by the height --------------------------------------------------------
def level_for(z: float, elevs: list) -> tuple[int, float]:
    """(the level's index, the slab top's offset over its floor): the
    highest floor at or under the outline (a hair over allowed — a floor
    drawn 1 mm high is that floor's), else the lowest level."""
    best = None
    for i, e in enumerate(elevs):
        if e <= z + 0.05 and (best is None or e > elevs[best]):
            best = i
    if best is None:
        best = min(range(len(elevs)), key=lambda i: elevs[i])
    return best, round(z - elevs[best], 4) + 0.0
