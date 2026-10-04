"""Plot geometry — pure 2D math on [x, y] corners (metres), no Qt.

The user's mistakes are fixed here, not reported back: repeated clicks
collapse, points on a straight run disappear, a clockwise outline is
turned round. Only what cannot be fixed (edges that cross, no area) is
refused, with a plain reason.
"""
from __future__ import annotations

import math

EPS = 0.001          # 1 mm — two clicks closer than this are the same point
MIN_AREA = 1.0       # m²


def signed_area(pts) -> float:
    a = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        a += x1 * y2 - x2 * y1
    return a / 2.0


def area(pts) -> float:
    return abs(signed_area(pts))


def perimeter(pts) -> float:
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:] + pts[:1]))


def _collinear(a, b, c) -> bool:
    cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return abs(cross) <= EPS * max(math.dist(a, c), EPS)


def clean(pts) -> list[list[float]]:
    """Drop repeated points and points on a straight run; counter-
    clockwise (seen from above, so the face looks up)."""
    out: list[list[float]] = []
    for p in pts:
        p = [round(float(p[0]), 4), round(float(p[1]), 4)]
        if not out or math.dist(out[-1], p) > EPS:
            out.append(p)
    if len(out) > 1 and math.dist(out[0], out[-1]) <= EPS:
        out.pop()
    changed = True
    while changed and len(out) > 3:
        changed = False
        for i in range(len(out)):
            a, b, c = out[i - 1], out[i], out[(i + 1) % len(out)]
            if _collinear(a, b, c):
                del out[i]
                changed = True
                break
    if len(out) >= 3 and signed_area(out) < 0:
        out.reverse()
    return out


def _segments_cross(p1, p2, p3, p4) -> bool:
    def orient(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-12 else (1 if v > 0 else -1)
    o1, o2 = orient(p1, p2, p3), orient(p1, p2, p4)
    o3, o4 = orient(p3, p4, p1), orient(p3, p4, p2)
    return o1 != o2 and o3 != o4 and 0 not in (o1, o2, o3, o4)


def self_crossing(pts, closed: bool = True) -> bool:
    n = len(pts)
    segs = [(pts[i], pts[(i + 1) % n]) for i in range(n if closed else n - 1)]
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            if j == i + 1 or (closed and i == 0 and j == len(segs) - 1):
                continue                     # neighbours share a corner
            if _segments_cross(*segs[i], *segs[j]):
                return True
    return False


def new_edge_crosses(pts, candidate) -> bool:
    """Would the edge last → candidate cross an edge already drawn?"""
    if len(pts) < 3:
        return False
    a, b = pts[-1], candidate
    return any(_segments_cross(a, b, pts[i], pts[i + 1])
               for i in range(len(pts) - 2))


def why_not(pts) -> str | None:
    """None when the outline makes a valid plot, else the plain reason."""
    if len(pts) < 3:
        return "A plot needs at least 3 corners"
    if self_crossing(pts):
        return "The plot's edges cross each other"
    if area(pts) < MIN_AREA:
        return "The plot is too small (under 1 m²)"
    return None


def rectangle(a, b) -> list[list[float]]:
    (x1, y1), (x2, y2) = a, b
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


# ---- Editing by sides (the surveyor's traverse) ---------------------------------------
# Side i runs corner i → corner i+1. One side is the CLOSING side c: the
# outline is rebuilt from the corner after it (c+1, which never moves),
# walking every other side with its own length and direction; the last
# two sides (c-1 and c) keep their LENGTHS and swing on the corner
# between them (c) to close. So typing every side's length once, in any
# order, gives the exact outline — no going round the table again.

def side_lengths(pts) -> list[float]:
    return [math.dist(a, b) for a, b in zip(pts, pts[1:] + pts[:1])]


def directions(pts) -> list[float]:
    """Direction of each side, radians from +X."""
    return [math.atan2(b[1] - a[1], b[0] - a[0])
            for a, b in zip(pts, pts[1:] + pts[:1])]


def interior_angles(pts) -> list[float]:
    """Inside angle at each corner, degrees (CCW outline)."""
    d = directions(pts)
    return [(math.degrees(d[i - 1] + math.pi - d[i])) % 360.0
            for i in range(len(pts))]


def free_angles(n: int, closing: int) -> set[int]:
    """Corners whose angle the user may set: both their sides are walked.
    The three corners around the closing side are the result."""
    c = closing % n
    return {i for i in range(n) if i not in (c, (c + 1) % n, (c - 1) % n)}


def rebuild(pts, lengths, dirs, closing: int):
    """The outline from side lengths + directions, closed by the hinge at
    corner ``closing``. Returns (corners, gap): gap 0 = closes exactly;
    > 0 = the lengths cannot close (the closing side then keeps its
    direction and is ``gap`` metres off the length asked)."""
    n = len(pts)
    c = closing % n
    out = [list(p) for p in pts]
    k = (c + 1) % n
    q = list(pts[k])                                  # the anchor
    for _ in range(n - 2):                            # sides c+1 … c-2
        q = [q[0] + lengths[k] * math.cos(dirs[k]),
             q[1] + lengths[k] * math.sin(dirs[k])]
        k = (k + 1) % n
        out[k] = q
    # corner c: |P[c-1] → P[c]| = L[c-1] and |P[c] → P[c+1]| = L[c]
    p0, p1 = out[(c - 1) % n], out[(c + 1) % n]
    r0, r1 = lengths[(c - 1) % n], lengths[c]
    d = math.dist(p0, p1)
    if d > 1e-9 and abs(r0 - r1) <= d <= r0 + r1:
        a = (r0 * r0 - r1 * r1 + d * d) / (2 * d)
        h = math.sqrt(max(r0 * r0 - a * a, 0.0))
        ux, uy = (p1[0] - p0[0]) / d, (p1[1] - p0[1]) / d
        mx, my = p0[0] + a * ux, p0[1] + a * uy
        s1 = [mx - h * uy, my + h * ux]
        s2 = [mx + h * uy, my - h * ux]
        old = pts[c]
        out[c] = min((s1, s2), key=lambda s: math.dist(s, old))
        gap = 0.0
    else:
        dc = dirs[(c - 1) % n]
        out[c] = [p0[0] + r0 * math.cos(dc), p0[1] + r0 * math.sin(dc)]
        gap = abs(math.dist(out[c], p1) - r1)
    return [[round(x, 4), round(y, 4)] for x, y in out], gap


def set_length(pts, side: int, value: float, closing: int):
    """Side ``side`` becomes ``value`` long; every other side keeps its
    length. → (corners, gap)."""
    L = side_lengths(pts)
    L[side % len(pts)] = float(value)
    return rebuild(pts, L, directions(pts), closing)


def set_angle(pts, corner: int, degrees: float, closing: int):
    """The inside angle at ``corner`` (a free one) becomes ``degrees``:
    the sides after it turn together, up to the closing pair."""
    n = len(pts)
    c = closing % n
    d = directions(pts)
    delta = math.radians(interior_angles(pts)[corner] - float(degrees))
    k = corner
    while k != (c - 1) % n:                 # sides corner … c-2 turn
        d[k] += delta
        k = (k + 1) % n
    return rebuild(pts, side_lengths(pts), d, closing)


def diagonal_ok(pts, i: int, j: int) -> bool:
    """Corners i and j can be joined inside the plot (a fold line)."""
    n = len(pts)
    if i == j or (i - j) % n in (1, n - 1):
        return False                               # same corner / a side
    a, b = pts[i], pts[j]
    for k in range(n):
        c, d = pts[k], pts[(k + 1) % n]
        if k in (i, j) or (k + 1) % n in (i, j):
            continue                               # sides touching a or b
        if _segments_cross(a, b, c, d):
            return False
    # and it runs INSIDE (a concave plot has outside chords too)
    m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    return _inside(m, pts)


def _inside(p, pts) -> bool:
    x, y = p
    inside = False
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        if (y1 > y) != (y2 > y):
            if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


def terrain_triangles(pts, heights, breaks=()) -> list[tuple[int, int, int]]:
    """How a sloped plot is cut into triangles: of every possible way, the
    one with the SMALLEST surface (no needless creases or steps), a touch
    in favour of well-shaped triangles; every fold line in ``breaks``
    ([i, j] corner pairs) is kept. Dynamic programming, O(n³)."""
    n = len(pts)
    if n < 3:
        return []
    forced = [tuple(sorted(b)) for b in breaks
              if len(b) == 2 and diagonal_ok(pts, b[0], b[1])]
    P = [(x, y, h) for (x, y), h in zip(pts, heights)]

    ok = [[False] * n for _ in range(n)]
    for i in range(n):
        ok[i][(i + 1) % n] = ok[(i + 1) % n][i] = True     # sides
    for i in range(n):
        for j in range(i + 2, n):
            if (i, j) == (0, n - 1) or not diagonal_ok(pts, i, j):
                continue
            if any(_segments_cross(pts[i], pts[j], pts[a], pts[b])
                   for a, b in forced if not {a, b} & {i, j}):
                continue                           # would cut a fold line
            ok[i][j] = ok[j][i] = True

    def cost(i, k, j) -> float:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = P[i], P[k], P[j]
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        area = 0.5 * math.sqrt((uy * vz - uz * vy) ** 2 +
                               (uz * vx - ux * vz) ** 2 +
                               (ux * vy - uy * vx) ** 2)
        per = (math.dist(pts[i], pts[k]) + math.dist(pts[k], pts[j]) +
               math.dist(pts[j], pts[i]))
        return area + 0.01 * per

    INF = float("inf")
    C = [[0.0 if j - i < 2 else INF for j in range(n)] for i in range(n)]
    K = [[-1] * n for _ in range(n)]
    for span in range(2, n):
        for i in range(0, n - span):
            j = i + span
            if not ok[i][j]:
                continue
            for k in range(i + 1, j):
                if not (ok[i][k] and ok[k][j]):
                    continue
                a, b, c = pts[i], pts[k], pts[j]
                if (b[0] - a[0]) * (c[1] - a[1]) - \
                        (b[1] - a[1]) * (c[0] - a[0]) <= 1e-12:
                    continue                       # flat / turned over
                v = C[i][k] + C[k][j] + cost(i, k, j)
                if v < C[i][j]:
                    C[i][j], K[i][j] = v, k
    if C[0][n - 1] == INF:
        return triangulate(pts)                    # never leave it holed
    tris: list[tuple[int, int, int]] = []
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j - i < 2:
            continue
        k = K[i][j]
        tris.append((i, k, j))
        stack += [(i, k), (k, j)]
    return tris


# ---- Outlines inside the plot (excavations) ------------------------------------------
def inside_polygon(p, pts) -> bool:
    return _inside(p, pts)


def _edges(pts):
    return [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def within(inner, outer, margin: float = 0.01) -> bool:
    """``inner`` lies inside ``outer``: every corner inside, no side
    crossing, and no corner closer than ``margin`` to ``outer``'s sides."""
    if not all(_inside(p, outer) for p in inner):
        return False
    for a, b in _edges(inner):
        if any(_segments_cross(a, b, c, d) for c, d in _edges(outer)):
            return False
    for p in inner:
        for c, d in _edges(outer):
            if _dist_to_segment(p, c, d) < margin:
                return False
    return True


def overlap(a, b) -> bool:
    """Two outlines share some area (crossing sides, or one inside the
    other)."""
    for p, q in _edges(a):
        if any(_segments_cross(p, q, c, d) for c, d in _edges(b)):
            return True
    return _inside(a[0], b) or _inside(b[0], a)


def _dist_to_segment(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx +
                                              (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def circle(centre, radius: float, segments: int = 24) -> list[list[float]]:
    """A circle as a CCW polygon (a corner every 360/segments degrees)."""
    n = max(6, int(segments))
    return [[round(centre[0] + radius * math.cos(2 * math.pi * k / n), 4),
             round(centre[1] + radius * math.sin(2 * math.pi * k / n), 4)]
            for k in range(n)]


# ---- Setbacks: the buildable area ----------------------------------------------------
def outward_normal(a, b):
    """Unit normal of side a→b pointing OUT of a CCW outline (its right)."""
    L = math.dist(a, b) or 1.0
    return ((b[1] - a[1]) / L, -(b[0] - a[0]) / L)


def side_roles(pts, front: list[bool], chosen=None) -> list[str]:
    """«front» where the user said so; «back» for a side facing away from
    a front (normals more than ~135° apart); «side» for the rest — unless
    the user chose a side's role (``chosen[i]`` "back" / "side"). No front
    marked → every side is None (no setbacks yet)."""
    n = len(pts)
    if not any(front):
        return [None] * n
    auto = auto_roles(pts, front)
    return [chosen[i] if chosen and chosen[i] in ("back", "side")
            and not front[i] else auto[i] for i in range(n)]


def auto_roles(pts, front: list[bool]) -> list[str]:
    """The roles ArchXQ works out from the fronts alone."""
    n = len(pts)
    normals = [outward_normal(pts[i], pts[(i + 1) % n]) for i in range(n)]
    fronts = [normals[i] for i in range(n) if front[i]]
    roles = []
    for i in range(n):
        if front[i]:
            roles.append("front")
        elif any(nx * fx + ny * fy < -0.7
                 for fx, fy in fronts for nx, ny in [normals[i]]):
            roles.append("back")
        else:
            roles.append("side")
    return roles


def side_distances(pts, front, custom, dist: dict,
                   chosen=None) -> list[float | None]:
    """The setback of each side: its own (typed) value, else its role's."""
    key = {"front": "front", "back": "back", "side": "sides"}
    out = []
    for i, r in enumerate(side_roles(pts, front, chosen)):
        if r is None:
            out.append(None)
        else:
            out.append(custom[i] if custom[i] is not None else dist[key[r]])
    return out


def setbacks_of(plot: dict):
    """(roles, distances, buildable outline | None) of a stored plot."""
    pts = plot["corners"]
    chosen = plot.get("sb_role")
    roles = side_roles(pts, plot["sb_front"], chosen)
    dists = side_distances(pts, plot["sb_front"], plot["sb_custom"],
                           plot["sb_dist"], chosen)
    return roles, dists, (buildable(pts, dists) if any(roles) else None)


def buildable(pts, dists):
    """The outline moved in, each side by its own distance: every side's
    line pushed inwards, neighbours meeting at the new corners. None when
    nothing is left (the setbacks swallow the plot, or fold it over)."""
    n = len(pts)
    if n < 3 or any(d is None for d in dists):
        return None
    lines = []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        nx, ny = outward_normal(a, b)
        d = dists[i]
        lines.append(((a[0] - nx * d, a[1] - ny * d),
                      (b[0] - nx * d, b[1] - ny * d)))
    out = []
    for i in range(n):
        (p1, p2), (p3, p4) = lines[i - 1], lines[i]
        d1 = (p2[0] - p1[0], p2[1] - p1[1])
        d2 = (p4[0] - p3[0], p4[1] - p3[1])
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-9:                      # straight on: keep the point
            out.append([p3[0], p3[1]])
            continue
        t = ((p3[0] - p1[0]) * d2[1] - (p3[1] - p1[1]) * d2[0]) / den
        out.append([p1[0] + t * d1[0], p1[1] + t * d1[1]])
    if signed_area(out) <= MIN_AREA or self_crossing(out):
        return None
    # pushed too far, a side turns over (a plot flipped both ways even
    # looks the right way round): every side must keep its direction
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        c, d = out[i], out[(i + 1) % n]
        if (b[0] - a[0]) * (d[0] - c[0]) + (b[1] - a[1]) * (d[1] - c[1]) \
                <= 0:
            return None
    return [[round(x, 4), round(y, 4)] for x, y in out]


def height_at(pts, heights, breaks, p, survey=()) -> float:
    """The ground's height at a point of the plot (the same triangles the
    surface is built from — survey points included). A point on the
    border — or a hair outside, where rounding puts it — takes the
    nearest triangle's plane (never a corner's height: that bent a ramp
    where it met a pit)."""
    tin = ground_tin(pts, heights, breaks, survey)
    if tin["flat"]:
        return tin["P"][0][2]
    return tin_height(tin, p)


# ---- The natural ground as a TIN (corners + survey points) ---------------------------
_TIN_CACHE: dict = {}


def _orient(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _in_circle(a, b, c, d) -> float:
    """> 0 when d lies inside the circle through a, b, c (counter-
    clockwise)."""
    ax, ay = a[0] - d[0], a[1] - d[1]
    bx, by = b[0] - d[0], b[1] - d[1]
    cx, cy = c[0] - d[0], c[1] - d[1]
    return ((ax * ax + ay * ay) * (bx * cy - cx * by)
            - (bx * bx + by * by) * (ax * cy - cx * ay)
            + (cx * cx + cy * cy) * (ax * by - bx * ay))


def survey_inside(pts, survey) -> list:
    """The survey points that shape the ground: inside the plot, not on
    a corner (nor on another point) — the rest are kept, not used."""
    out, seen = [], [tuple(p) for p in pts]
    for s in survey or ():
        q = (float(s[0]), float(s[1]))
        if not _inside(q, pts):
            continue
        if any(math.dist(q, o) < 0.01 for o in seen):
            continue
        if min(_dist_to_segment(q, pts[i], pts[(i + 1) % len(pts)])
               for i in range(len(pts))) < 0.01:
            continue                                 # on the border: skip
        seen.append(q)
        out.append(s)
    return out


def ground_tin(pts, heights, breaks=(), survey=()) -> dict:
    """The natural ground: the corners' triangles (``terrain_triangles``,
    fold lines kept), each survey point inside put in and the triangles
    around it made Delaunay — the surveyor's TIN; the plot's sides and
    the fold lines are never flipped. → {"P": [(x, y, z)], "tris":
    [(i, j, k)] counter-clockwise, "hard": {frozenset((i, j))} the fold
    lines (split where a point fell on one), "flat": bool}. Cached."""
    key = (tuple(map(tuple, pts)), tuple(heights),
           tuple(map(tuple, breaks)),
           tuple(tuple(s[:3]) for s in survey or ()))
    tin = _TIN_CACHE.get(key)
    if tin is not None:
        return tin
    n = len(pts)
    P = [(float(x), float(y), float(h)) for (x, y), h in zip(pts, heights)]
    inside = survey_inside(pts, survey)
    P += [(float(s[0]), float(s[1]), float(s[2])) for s in inside]
    zs = [p[2] for p in P]
    flat = max(zs) - min(zs) < 1e-6
    tris: list = []
    for t in terrain_triangles(pts, heights, breaks):
        i, j, k = t
        tris.append([i, j, k] if _orient(P[i], P[j], P[k]) > 0
                    else [i, k, j])
    fixed = {frozenset((i, (i + 1) % n)) for i in range(n)}
    hard = {frozenset(b) for b in breaks if len(b) == 2}
    edges: dict = {}

    def add(t):
        tid = len(tris)
        tris.append(t)
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            edges.setdefault(frozenset((a, b)), set()).add(tid)
        return tid

    def drop(tid):
        t = tris[tid]
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            edges[frozenset((a, b))].discard(tid)
        tris[tid] = None

    base, tris = tris, []
    for t in base:
        add(t)

    def legalize(stack):
        guard = 0
        while stack and guard < 100000:
            guard += 1
            e = stack.pop()
            if e in fixed or e in hard:
                continue
            ts = [t for t in edges.get(e, ()) if tris[t] is not None]
            if len(ts) != 2:
                continue
            a, b = tuple(e)
            t1, t2 = tris[ts[0]], tris[ts[1]]
            c = next(v for v in t1 if v not in e)
            d = next(v for v in t2 if v not in e)
            # the quadrilateral must be convex for the other diagonal
            if _orient(P[c], P[d], P[a]) * _orient(P[c], P[d], P[b]) >= 0:
                continue
            x, y, z = t1
            if _in_circle(P[x], P[y], P[z], P[d]) <= 1e-9:
                continue
            drop(ts[0])
            drop(ts[1])
            for tri in ([a, d, c], [b, c, d]):
                if _orient(P[tri[0]], P[tri[1]], P[tri[2]]) < 0:
                    tri[1], tri[2] = tri[2], tri[1]
                add(tri)
            stack += [frozenset((a, c)), frozenset((c, b)),
                      frozenset((b, d)), frozenset((d, a))]

    for q in range(n, len(P)):
        p = P[q]
        host, on = None, None
        for tid, t in enumerate(tris):
            if t is None:
                continue
            A, B, C = P[t[0]], P[t[1]], P[t[2]]
            w = (_orient(B, C, p), _orient(C, A, p), _orient(A, B, p))
            area2 = _orient(A, B, C)
            tol = 1e-9 * max(1.0, abs(area2))
            if min(w) >= -tol:
                host = tid
                small = [k for k in range(3) if abs(w[k]) <= tol * 10 + 1e-7]
                if small:
                    # on the edge opposite that corner
                    k = small[0]
                    on = frozenset((t[(k + 1) % 3], t[(k + 2) % 3]))
                break
        if host is None:
            continue
        if on is None:
            i, j, k = tris[host]
            drop(host)
            for tri in ([i, j, q], [j, k, q], [k, i, q]):
                add(tri)
            stack = [frozenset((i, j)), frozenset((j, k)), frozenset((k, i))]
        else:
            a, b = tuple(on)
            stack = []
            for tid in [t for t in edges.get(on, ()) if tris[t] is not None]:
                c = next(v for v in tris[tid] if v not in on)
                drop(tid)
                for tri in ([a, q, c], [q, b, c]):
                    if _orient(P[tri[0]], P[tri[1]], P[tri[2]]) < 0:
                        tri[1], tri[2] = tri[2], tri[1]
                    add(tri)
                stack += [frozenset((a, c)), frozenset((b, c))]
            for s in (fixed, hard):
                if on in s:                          # a side / fold split
                    s.discard(on)
                    s.add(frozenset((a, q)))
                    s.add(frozenset((q, b)))
        legalize(stack)

    live = [tuple(t) for t in tris if t is not None]
    tin = {"P": P, "tris": live, "hard": hard, "flat": flat,
           "sides": fixed, "survey": inside}
    if len(_TIN_CACHE) > 32:
        _TIN_CACHE.clear()
    _TIN_CACHE[key] = tin
    return tin


def contours(tin: dict, step: float, major_every: int = 5) -> list:
    """The ground's contour lines every ``step`` m (multiples of it, from
    ±0.00): → [(z, major?, [(x, y, z), ...] a polyline)], each line one
    run through the triangles (joined end to end). Every
    ``major_every``-th level is a major one. Cached on the TIN."""
    if tin["flat"] or step <= 0:
        return []
    key = ("contours", round(step, 4), major_every)
    if key in tin:
        return tin[key]
    P = tin["P"]
    zs = [p[2] for p in P]
    lo = math.ceil(min(zs) / step - 1e-9)
    hi = math.floor(max(zs) / step + 1e-9)
    if hi - lo > 2000:                     # a silly step: don't freeze
        tin[key] = []
        return []
    out = []
    for k in range(lo, hi + 1):
        z = round(k * step, 6)
        segs = []
        for t in tin["tris"]:
            a, b, c = P[t[0]], P[t[1]], P[t[2]]
            cut = []
            for u, v in ((a, b), (b, c), (c, a)):
                du, dv = u[2] - z, v[2] - z
                if (du < 0) != (dv < 0) and du != dv:
                    s = du / (du - dv)
                    cut.append((round(u[0] + (v[0] - u[0]) * s, 4),
                                round(u[1] + (v[1] - u[1]) * s, 4)))
            if len(cut) == 2 and cut[0] != cut[1]:
                segs.append(tuple(cut))
        # join the pieces into runs
        ends: dict = {}
        for i, (p, q) in enumerate(segs):
            ends.setdefault(p, []).append(i)
            ends.setdefault(q, []).append(i)
        used = [False] * len(segs)
        for i in range(len(segs)):
            if used[i]:
                continue
            used[i] = True
            line = list(segs[i])
            for grow_front in (False, True):
                while True:
                    tip = line[0] if grow_front else line[-1]
                    nxt = next((j for j in ends.get(tip, ()) if not used[j]),
                               None)
                    if nxt is None:
                        break
                    used[nxt] = True
                    p, q = segs[nxt]
                    other = q if p == tip else p
                    if grow_front:
                        line.insert(0, other)
                    else:
                        line.append(other)
            out.append((z, k % major_every == 0,
                        [(x, y, z) for x, y in line]))
    tin[key] = out
    return out


def tin_height(tin: dict, p) -> float:
    """z of the TIN at (x, y): the triangle it falls in, else the nearest
    triangle's plane (a point a hair outside)."""
    P = tin["P"]
    if "planes" not in tin:
        # each triangle once: its box and its barycentric terms
        pl = []
        for i, j, k in tin["tris"]:
            (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = P[i], P[j], P[k]
            den = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
            if abs(den) < 1e-12:
                continue
            pl.append((min(x1, x2, x3) - 1e-6, max(x1, x2, x3) + 1e-6,
                       min(y1, y2, y3) - 1e-6, max(y1, y2, y3) + 1e-6,
                       x1, y1, z1, x2, y2, z2, x3, y3, z3, den))
        tin["planes"] = pl
    x, y = p[0], p[1]
    best = None
    for (lx, hx, ly, hy, x1, y1, z1, x2, y2, z2, x3, y3, z3,
         den) in tin["planes"]:
        boxed = lx <= x <= hx and ly <= y <= hy
        if not boxed and best is not None and best[0] > -0.05:
            continue                     # far away, and a near one is known
        w1 = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / den
        w2 = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / den
        w3 = 1 - w1 - w2
        m = min(w1, w2, w3)
        if m >= -1e-6:
            return w1 * z1 + w2 * z2 + w3 * z3
        if best is None or m > best[0]:
            best = (m, w1 * z1 + w2 * z2 + w3 * z3)
    if best is not None:
        return best[1]
    near = min(P, key=lambda q: math.dist(q[:2], p))
    return near[2]


def carry_sides(old_pts, new_pts, values, merge=None):
    """Per-side values (front marks, own setbacks) across an edit of the
    corners: same count → as they were; one corner more → the split side's
    value goes to both halves; one less → the two merged sides give one
    (``merge(a, b)``, default the first). Anything else → None (the
    caller starts afresh)."""
    n, m = len(old_pts), len(new_pts)
    if m == n:
        return list(values)
    if m == n + 1:
        k = next((i for i in range(n) if old_pts[i] != new_pts[i]), n)
        # corner k is new: old side k-1 became sides k-1 and k
        return values[:k] + [values[k - 1]] + values[k:]
    if m == n - 1:
        i = next((q for q in range(m) if old_pts[q] != new_pts[q]), m)
        # corner i went: old sides i-1 and i became side i-1
        a, b = values[i - 1], values[i % n]
        merged = (merge or (lambda x, _y: x))(a, b)
        out = [v for q, v in enumerate(values) if q != i % n]
        out[(i - 1) % m] = merged
        return out
    return None


# ---- Corners added / removed: what hangs on the corner numbers follows ------------
def _keep_breaks(pts, breaks):
    """Fold lines that still run inside the plot (a corner moved can turn
    one into a side or push it outside)."""
    out = []
    for b in breaks:
        b = sorted(b)
        if b not in out and diagonal_ok(pts, b[0], b[1]):
            out.append(b)
    return out


def insert_corner(pts, heights, closing, breaks, side: int, p):
    """A new corner ``p`` on side ``side`` (between corners side and
    side+1). Its height is read off the side; the fold lines renumber;
    the closing side stays the same stretch of boundary."""
    n = len(pts)
    a, b = pts[side], pts[(side + 1) % n]
    L = math.dist(a, b)
    t = 0.0 if L < 1e-9 else math.dist(a, p) / L
    h = heights[side] + (heights[(side + 1) % n] - heights[side]) * t
    k = side + 1                                     # its index
    pts2 = pts[:k] + [[round(p[0], 4), round(p[1], 4)]] + pts[k:]
    hs2 = heights[:k] + [round(h, 3)] + heights[k:]
    cl2 = closing + 1 if closing >= k else closing
    br2 = [[i + (i >= k), j + (j >= k)] for i, j in breaks]
    return pts2, hs2, cl2, _keep_breaks(pts2, br2)


def remove_corner(pts, heights, closing, breaks, i: int):
    """Corner ``i`` goes: its two sides become one; fold lines ending
    there go too."""
    n = len(pts)
    pts2 = pts[:i] + pts[i + 1:]
    hs2 = heights[:i] + heights[i + 1:]
    if closing == i:
        cl2 = (i - 1) % (n - 1)                     # the merged side
    else:
        cl2 = closing - 1 if closing > i else closing
    br2 = [[a - (a > i), b - (b > i)] for a, b in breaks if i not in (a, b)]
    return pts2, hs2, cl2 % (n - 1), _keep_breaks(pts2, br2)


def move_corner(pts, breaks, i: int, p):
    pts2 = [list(q) for q in pts]
    pts2[i] = [round(p[0], 4), round(p[1], 4)]
    return pts2, _keep_breaks(pts2, breaks)


def triangulate(pts) -> list[tuple[int, int, int]]:
    """Ear clipping of a simple CCW outline → corner-index triangles."""
    idx = list(range(len(pts)))
    tris: list[tuple[int, int, int]] = []

    def inside(p, a, b, c) -> bool:
        def s(p1, p2, p3):
            return (p1[0] - p3[0]) * (p2[1] - p3[1]) - \
                (p2[0] - p3[0]) * (p1[1] - p3[1])
        d1, d2, d3 = s(p, a, b), s(p, b, c), s(p, c, a)
        return not ((d1 < 0 or d2 < 0 or d3 < 0)
                    and (d1 > 0 or d2 > 0 or d3 > 0))

    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for j in range(len(idx)):
            i0, i1, i2 = idx[j - 1], idx[j], idx[(j + 1) % len(idx)]
            a, b, c = pts[i0], pts[i1], pts[i2]
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) \
                    <= 1e-12:
                continue                              # reflex / flat
            if any(inside(pts[m], a, b, c) for m in idx
                   if m not in (i0, i1, i2)):
                continue
            tris.append((i0, i1, i2))
            del idx[j]
            break
        else:
            break                                     # degenerate: stop
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris
