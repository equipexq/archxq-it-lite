# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""WALL JOINTS drawn clean (2026-10-25, Cesar's ticket #59: «there is
always a diagonal line between the two walls»). Each wall is its own
group, so the mitre of an L, the end of a partition against a wall, the
joint of two walls in a row left an edge where their faces meet. As in
ArchiCAD / Revit (walls of one material read as one), such an edge is
HIDDEN when the faces on both sides of the joint lie in one plane and
wear the same material: the top of an L reads as one strip, the corner's
upright stays (a real fold). Different heights, different materials: the
line stays — it is real.

Pure: faces in, edge keys out (``compat.mesh_of`` hides them; their keys
go in each group's build fingerprint, so a neighbour's change rebuilds
it). Tested by ``tests/test_seams``."""
from __future__ import annotations

import math

PLANE_TOL = 2e-3            # m: a face this close lies on the other's plane
DOT_TOL = 0.9999            # normals this close are the same direction
INSIDE_TOL = 2e-3           # m: a point this close to a face is on it
BUCKET = 0.005              # m: the planes' index step (± one looked at:
                            # covers PLANE_TOL)


def edge_key(a, b) -> frozenset:
    """An edge's key, as ``compat`` rounds the host's vertices."""
    return frozenset((tuple(round(c, 4) for c in a[:3]),
                      tuple(round(c, 4) for c in b[:3])))


def _loop(f):
    return f["loop"] if isinstance(f, dict) else f


def _normal(loop):
    """Newell's normal (unit), or None for a degenerate loop."""
    nx = ny = nz = 0.0
    n = len(loop)
    for i in range(n):
        x1, y1, z1 = loop[i][:3]
        x2, y2, z2 = loop[(i + 1) % n][:3]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    m = math.sqrt(nx * nx + ny * ny + nz * nz)
    if m < 1e-12:
        return None
    return (nx / m, ny / m, nz / m)


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


class _Face:
    __slots__ = ("loop", "n", "d", "mat", "ax", "poly", "lo", "hi", "_keys")

    def __init__(self, loop, n, mat):
        self._keys = None
        self.loop = loop
        self.n = n
        self.d = _dot(n, loop[0])
        self.mat = mat
        self.ax = max(range(3), key=lambda i: abs(n[i]))
        self.poly = None
        xs, ys, zs = zip(*loop)
        self.lo = (min(xs), min(ys), min(zs))
        self.hi = (max(xs), max(ys), max(zs))

    def holds(self, p) -> bool:
        """``p`` (on its plane) inside or on this face's outline — plain
        Python, no shapely: called thousands of times a build (0.58 s with
        shapely on his corporate building)."""
        if any(p[i] < self.lo[i] - INSIDE_TOL or p[i] > self.hi[i]
               + INSIDE_TOL for i in range(3)):
            return False
        if self.poly is None:              # the loop flattened, once
            u, v = [i for i in range(3) if i != self.ax]
            self.poly = [(q[u], q[v]) for q in self.loop]
        u, v = [i for i in range(3) if i != self.ax]
        x, y = p[u], p[v]
        pts = self.poly
        inside = False
        n = len(pts)
        for k in range(n):
            x1, y1 = pts[k]
            x2, y2 = pts[(k + 1) % n]
            # on the outline (within the tolerance): held
            dx, dy = x2 - x1, y2 - y1
            ll = dx * dx + dy * dy
            t = 0.0 if ll < 1e-18 else max(0.0, min(1.0, ((x - x1) * dx
                                                        + (y - y1) * dy) / ll))
            ex, ey = x1 + t * dx - x, y1 + t * dy - y
            if ex * ex + ey * ey <= INSIDE_TOL * INSIDE_TOL:
                return True
            if (y1 > y) != (y2 > y) and \
                    x < x1 + (y - y1) * dx / (dy or 1e-18):
                inside = not inside
        return inside

    def keys(self) -> set:
        """Its edges' keys (made once, when asked)."""
        if self._keys is None:
            n = len(self.loop)
            self._keys = {edge_key(self.loop[k], self.loop[(k + 1) % n])
                          for k in range(n)}
        return self._keys

    def on_plane(self, p) -> bool:
        return abs(_dot(self.n, p) - self.d) < PLANE_TOL


def _faces(el: dict, mat_of) -> list:
    out = []
    seen = {}                         # colour → material: asked once each
    for f in el["faces"]:
        loop = [tuple(q[:3]) for q in _loop(f)]
        if len(loop) < 3:
            continue
        n = _normal(loop)
        if n is None:
            continue
        color = f.get("color") if isinstance(f, dict) else None
        ck = tuple(color) if color is not None else None
        if ck not in seen:
            seen[ck] = mat_of(el, color)
        out.append(_Face(loop, n, seen[ck]))
    return out


def _touch(f, g) -> bool:
    """Their boxes meet (the cheap test first)."""
    return all(f.lo[i] - INSIDE_TOL <= g.hi[i] and g.lo[i] - INSIDE_TOL
               <= f.hi[i] for i in range(3))


def _box(fs):
    return (tuple(min(f.lo[i] for f in fs) for i in range(3)),
            tuple(max(f.hi[i] for f in fs) for i in range(3)))


def _near(a, b, m=0.01) -> bool:
    (al, ah), (bl, bh) = a, b         # (written out: called ~50 000 times)
    return (al[0] - m <= bh[0] and bl[0] - m <= ah[0]
            and al[1] - m <= bh[1] and bl[1] - m <= ah[1]
            and al[2] - m <= bh[2] and bl[2] - m <= ah[2])


def hidden_edges(built: list, mat_of=None) -> dict:
    """{index in ``built``: {edge key}} — the joint edges of its walls to
    hide. ``built``: ``structure.build``'s list (only its walls are read);
    ``mat_of(element, face colour)``: what a face wears (equal = same
    material; none given: all the same)."""
    mat_of = mat_of or (lambda el, color: None)
    walls = {}
    for i, el in enumerate(built):
        if el.get("kind") == "wall":
            fs = _faces(el, mat_of)
            if fs:
                walls[i] = (el.get("level"), fs, _box(fs))
    # every face by its plane's offset (n·p): a face finds the ones on its
    # plane without trying all of them (~10 000 faces on his corporate
    # building — the openings cut the walls in many)
    idx: dict = {}
    for j, (lv, fs, _box_) in walls.items():
        for g in fs:
            idx.setdefault((lv, round(g.d / BUCKET)), []).append((j, g))

    def on(lv, d, near):
        r = round(d / BUCKET)
        for k in (r - 1, r, r + 1):
            for j, g in idx.get((lv, k), ()):
                if j in near:
                    yield j, g

    out = {}
    for i in walls:
        got = reveal_edges(built[i], mat_of)
        if got:
            out[i] = got
    for i, (lv, fs, box) in walls.items():
        near = {j for j, (olv, _ofs, obox) in walls.items()
                if j != i and olv == lv and _near(box, obox)}
        if not near:
            continue
        boxes = [walls[j][2] for j in near]
        hide = set()
        for f in fs:
            # (a face in the middle of the wall — an opening's reveal —
            # touches no neighbour: skipped at once)
            if not any(_near((f.lo, f.hi), bx, INSIDE_TOL) for bx in boxes):
                continue
            # f: against a neighbour? (a face of it on f's plane, facing
            # back, one of the two holding ALL of the other: a partition's
            # end on a wall's side, a high wall's end on a low one's)
            against = {j for j, g in on(lv, -f.d, near)
                       if _dot(g.n, f.n) < -DOT_TOL and _touch(f, g)
                       and g.on_plane(f.loop[0])
                       and (all(g.holds(p) for p in f.loop)
                            or all(f.holds(p) for p in g.loop))}
            if not against:
                continue
            # the faces of this wall that may share an edge with f
            close = [o for o in fs if o is not f and _touch(o, f)]
            n = len(f.loop)
            for k in range(n):
                a, b = f.loop[k], f.loop[(k + 1) % n]
                key = edge_key(a, b)
                if key in hide:
                    continue
                mid = tuple((a[t] + b[t]) / 2 for t in range(3))
                for side in close:
                    if key not in side.keys():
                        continue
                    # the face beyond the joint: same plane, same way, same
                    # material, running on from ALL of this edge (a wall's
                    # long top only touches a partition's at one point)
                    if any(_dot(g.n, side.n) > DOT_TOL and g.on_plane(mid)
                           and g.mat == side.mat and g.holds(a)
                           and g.holds(b) and g.holds(mid)
                           for _j, g in on(lv, side.d, against)):
                        hide.add(key)
                        break
        if hide:
            out[i] = out.get(i, set()) | hide
    return out


def reveal_edges(el: dict, mat_of=None) -> set:
    """The edges between an opening's reveal faces of ONE wall with layers
    (marked ``"reveal"`` by structure.layered_faces) that lie in one plane,
    face the same way and wear the same material: the plaster turned into
    the reveal reads as one face, not a strip per layer (2026-11-01). The
    line at the frame, between the outer and the inner finish, stays.
    And a layer JOINT's edges round the openings (listed in its
    ``"joint"``: cut 1 mm back from the reveal) — inside the wall, yet
    drawn through the reveal; its lines at the wall's ends, top and foot
    stay."""
    mat_of = mat_of or (lambda el, color: None)
    by_key: dict = {}
    seen = {}
    hide = set()
    for f in el.get("faces") or ():
        if isinstance(f, dict) and f.get("joint"):
            hide.update(edge_key(a, b) for a, b in f["joint"])
        if not isinstance(f, dict) or not f.get("reveal"):
            continue
        loop = [tuple(q[:3]) for q in f["loop"]]
        n = _normal(loop) if len(loop) >= 3 else None
        if n is None:
            continue
        ck = tuple(f["color"]) if f.get("color") is not None else None
        if ck not in seen:
            seen[ck] = mat_of(el, f.get("color"))
        rec = (n, _dot(n, loop[0]), seen[ck])
        for k in range(len(loop)):
            by_key.setdefault(edge_key(loop[k], loop[(k + 1) % len(loop)]),
                              []).append(rec)
    for key, recs in by_key.items():
        if len(recs) < 2:
            continue
        (na, da, ma), (nb, db, mb) = recs[0], recs[1]
        if _dot(na, nb) > DOT_TOL and abs(da - db) < PLANE_TOL and ma == mb:
            hide.add(key)
    return hide
