"""The terrain's geometry, worked out from the data — pure, no Qt.

The ground is the PLOT (its outline, corner heights, fold lines) with the
EXCAVATIONS opened in it. Nothing is cut with booleans (the Blender
version's lesson: a boolean modifier and a hidden cutter were fragile):
every rebuild makes the faces afresh from the data, in one undo step.

Excavations may overlap — a ramp running into a basement's pit, circles
side by side: they MERGE. Their outlines are laid out as a planar
arrangement (the host's); every region of it is dug to the DEEPEST bottom
of the excavations covering it; a wall stands only where two neighbouring
surfaces differ (the pit's edge, the step where a ramp meets the floor).

    build(doc, z0, earcut, arrange) → {"plot": {"faces", "soft"},
                                       "digs": [(dig, faces)],
                                       "volumes": {dig id: m³}}

A face is a loop of (x, y, z), counter-clockwise seen from outside — or
{"loop", "holes"}; "soft" holds the edges drawn smooth. ``earcut(points,
hole_starts)`` and ``arrange(segments)`` are the host's (compat).

An excavation (``doc["digs"]``):
    {"id", "name", "corners": [[x, y]…] (CCW),
     "bottom": {"mode": "depth", "d": 3.0}     (under the lowest ground)
             | {"mode": "level", "level": id, "offset": -0.30}
             | {"mode": "elev", "z": -3.0}
             | {"mode": "corners"},
     "bottoms": [z per corner]   (mode "corners": a ramp, a sloped pit)}
Elevations are the project's: 0 = the ground floor datum.
"""
from __future__ import annotations

import math

from . import model, plotgeo

DEFAULT_ELEV = -3.0        # a pit's bottom when there is no basement
DEFAULT_DEPTH = 3.0        # a new pit: 3 m under the ground (his default)
BELOW_FLOOR = -0.30        # a basement's pit: its floor minus slab + fill
MIN_THICK = 0.30           # ground left under the deepest pit
EPS = 1e-4


# ---- excavations: what the data says ----------------------------------------------
def level_bottom(doc: dict, level_id: str, offset: float) -> float | None:
    levels = doc["levels"]
    ids = [r["id"] for r in levels]
    if level_id not in ids:
        return None
    ground = doc["project"]["ground_level"] if model.has_project(doc) else 0.0
    return model.elevations(levels, ground)[ids.index(level_id)] + offset


def is_fill(dig: dict) -> bool:
    """A FILL (aterro: the ground raised — a platform, an embankment)
    rather than a cut (an excavation)."""
    return dig.get("kind") == "fill"


def dig_bottoms(dig: dict, doc: dict) -> list[float]:
    """The modification's level at each corner (project elevation): a
    pit's bottom, or a fill's top."""
    n = len(dig["corners"])
    b = dig.get("bottom") or {}
    mode = b.get("mode", "elev")
    if mode == "corners" and len(dig.get("bottoms") or []) == n:
        return [float(z) for z in dig["bottoms"]]
    if mode == "height" and doc.get("plot"):
        # a fill: flat, ``h`` over the highest ground along its outline
        high = max(ground_at(doc["plot"], q) for q in dig["corners"])
        return [high + float(b.get("h", 1.0))] * n
    if mode == "level":
        z = level_bottom(doc, b.get("level"), float(b.get("offset",
                                                          BELOW_FLOOR)))
        if z is not None:
            return [z] * n
    if mode == "depth" and doc.get("plot"):
        # flat, ``d`` under the lowest ground along its outline
        low = min(ground_at(doc["plot"], q) for q in dig["corners"])
        return [low - float(b.get("d", DEFAULT_DEPTH))] * n
    return [float(b.get("z", DEFAULT_ELEV))] * n


def surface(dig: dict, doc: dict, ip, bots=None):
    """The pit's surface as a function z(p), for the part of it a point
    ``ip`` lies in: the FLOOR (the corners' bottoms, spread over the same
    triangles the floor is built of), or ONE SIDE's SLOPE — the trapezoid
    between that side and its edge at the ground: the floor along the
    side, rising by the side's tangent with the distance from it. (Each
    slope only by its own side: on a concave pit, another side's line
    cuts across it.)"""
    bots = bots if bots is not None else dig_bottoms(dig, doc)
    pts = dig["corners"]

    def base(p):
        return bots[0] if max(bots) - min(bots) < 1e-6 else \
            plotgeo.height_at(pts, bots, [], p)

    if plotgeo.inside_polygon(ip, pts):
        return base
    tans = slope_tans(dig)
    top = top_of(dig, doc)
    n = len(pts)
    best = None
    for i, t in enumerate(tans):
        if t is None:
            continue
        j = (i + 1) % n
        band = [pts[i], pts[j], top[j], top[i]]
        a, b = pts[i], pts[j]
        nx, ny = plotgeo.outward_normal(a, b)
        out = (ip[0] - a[0]) * nx + (ip[1] - a[1]) * ny
        if out <= 0:
            continue
        inside = plotgeo.inside_polygon(ip, band)
        key = (inside, -out)                  # its own band first
        if best is None or key > best[0]:
            best = (key, a, nx, ny, t)
    if best is None:
        return base
    _k, a, nx, ny, t = best
    sign = -1.0 if is_fill(dig) else 1.0     # a fill's slope runs down

    def slope(p):
        out = max(0.0, (p[0] - a[0]) * nx + (p[1] - a[1]) * ny)
        # the floor's height where this point's foot meets the side
        foot = (p[0] - nx * out, p[1] - ny * out)
        return base(foot) + sign * out * t
    return slope


def bottom_at(dig: dict, doc: dict, p, bots=None) -> float:
    """The pit's surface under a point (floor, or the slope it is on)."""
    return surface(dig, doc, p, bots)(p)


# ---- the sides' slopes (batters): 90° = a vertical wall ----------------------------
def side_angles(dig: dict) -> list[float]:
    """Each side's wall angle (degrees from the horizontal): 90 = vertical
    (a retaining wall), less = a slope (a batter) opening outward."""
    n = len(dig["corners"])
    a = dig.get("angles") or []
    return [float(x) for x in a] if len(a) == n else [90.0] * n


def slope_tans(dig: dict) -> list[float | None]:
    """tan(angle) per side, None for a vertical one."""
    return [None if x >= 89.9 else math.tan(math.radians(max(x, 5.0)))
            for x in side_angles(dig)]


def outline(dig: dict, doc: dict):
    """Where the excavation meets the ground: its drawn outline, pushed
    out on every sloped side as far as the slope climbs to the ground
    (the deepest end of the side decides). None when it can't be made."""
    tans = slope_tans(dig)
    if all(t is None for t in tans):
        return dig["corners"]
    pts = dig["corners"]
    n = len(pts)
    bots = dig_bottoms(dig, doc)
    plot = doc.get("plot")
    offs = []
    for i, t in enumerate(tans):
        if t is None:
            offs.append(0.0)
            continue
        j = (i + 1) % n
        sign = -1.0 if is_fill(dig) else 1.0       # a fill: its height
        depth = max(sign * ((ground_at(plot, pts[k]) if plot else 0.0)
                            - bots[k]) for k in (i, j))
        offs.append(-max(depth, 0.0) / t)          # negative = outward
    top = plotgeo.buildable(pts, offs)
    return top


def reshape(dig: dict, doc: dict, corners) -> dict:
    """The excavation with a new outline (a corner moved, added or
    deleted). A ramp's bottoms follow: a corner kept keeps its bottom (a
    moved one too, by its place when the count is the same), a new corner
    takes the bottom found under it."""
    new = dict(dig, corners=[list(p) for p in corners])
    # each side's wall angle follows it (a split side: both halves; two
    # merged into one: the first's)
    angles = plotgeo.carry_sides(dig["corners"], corners, side_angles(dig))
    new["angles"] = angles if angles is not None else [90.0] * len(corners)
    if (dig.get("bottom") or {}).get("mode") != "corners":
        return new
    old = dig["corners"]
    bots = dig_bottoms(dig, doc)
    if len(corners) == len(old):
        new["bottoms"] = list(bots)
        return new
    at = {(round(p[0], 4), round(p[1], 4)): z for p, z in zip(old, bots)}
    new["bottoms"] = [round(at.get((round(p[0], 4), round(p[1], 4)),
                                   bottom_at(dig, doc, p, bots)), 3)
                      for p in corners]
    return new


def default_bottom(doc: dict) -> dict:
    """A new pit's bottom: 3 m under the ground (his default)."""
    return {"mode": "depth", "d": DEFAULT_DEPTH}


def why_not_dig(doc: dict, corners, ignore: str | None = None) -> str | None:
    """None when this outline can be an excavation, else the plain reason.
    Overlapping another one is fine: they merge."""
    reason = plotgeo.why_not(corners)
    if reason:
        return reason.replace("plot", "excavation")
    plot = doc.get("plot")
    if not plot:
        return "Draw the plot first"
    if not plotgeo.within(corners, plot["corners"]):
        return "The excavation has to stay inside the plot"
    return None


def snug(doc: dict, corners, gap: float = 0.02, reach: float = 0.05):
    """An outline drawn onto the plot's sides (snapped to its corner, its
    side, a guide on it — a basement dug to the boundary, his case
    2026-10-05) has its corners nudged ``gap`` inside, the rim the ground
    keeps (``plotgeo.within``). Corners more than ``reach`` outside are
    left: that one is a real mistake, and is said."""
    plot = doc.get("plot")
    if not plot or len(corners) < 3:
        return corners
    outer = plot["corners"]
    if plotgeo.within(corners, outer):
        return corners
    n = len(outer)
    area2 = sum(outer[i][0] * outer[(i + 1) % n][1]
                - outer[(i + 1) % n][0] * outer[i][1] for i in range(n))
    sign = 1.0 if area2 > 0 else -1.0                # inside = the left
    out = []
    for p in corners:
        q = [float(p[0]), float(p[1])]
        for _ in range(3):                           # a corner: two sides
            moved = False
            for i in range(n):
                a, b = outer[i], outer[(i + 1) % n]
                ex, ey = b[0] - a[0], b[1] - a[1]
                L = math.hypot(ex, ey)
                if L < 1e-9:
                    continue
                t = ((q[0] - a[0]) * ex + (q[1] - a[1]) * ey) / (L * L)
                if t < -reach / L or t > 1 + reach / L:
                    continue
                d = sign * (ex * (q[1] - a[1]) - ey * (q[0] - a[0])) / L
                if -reach <= d < gap - 1e-6:
                    nx, ny = -sign * ey / L, sign * ex / L
                    q = [q[0] + nx * (gap - d), q[1] + ny * (gap - d)]
                    moved = True
            if not moved:
                break
        out.append([round(q[0], 4), round(q[1], 4)])
    return out if plotgeo.within(out, outer) else corners


def top_of(dig: dict, doc: dict):
    """The outline at the ground (its slopes' reach), else its own."""
    return outline(dig, doc) or dig["corners"]


def opened(doc: dict) -> list[dict]:
    """The excavations that can be dug: inside the plot — slopes and all.
    One left outside by an edited plot (or a slope that now reaches past
    it) is kept (its data) but not dug until it fits again — the ground
    never breaks."""
    plot = doc.get("plot")
    if not plot:
        return []
    return [d for d in doc.get("digs") or [] if len(d["corners"]) >= 3
            and plotgeo.within(top_of(d, doc), plot["corners"])]


# ---- the ground at a point -----------------------------------------------------------
def ground_at(plot: dict, p) -> float:
    """Natural ground height (above the plot's datum) at a point."""
    return plotgeo.height_at(plot["corners"], plot["heights"],
                             plot["breaks"], p, plot.get("survey") or ())


def tin_of(plot: dict) -> dict:
    """The natural ground's triangles (corners + survey points)."""
    return plotgeo.ground_tin(plot["corners"], plot["heights"],
                              plot["breaks"], plot.get("survey") or ())


def volume(dig: dict, doc: dict) -> float:
    """Earth this excavation alone takes out (m³) — its floor's triangles ×
    how deep they sit under the ground. (Merged ones: ``build``'s
    "volumes" counts every m³ once.)"""
    plot = doc["plot"]
    pts = dig["corners"]
    bots = dig_bottoms(dig, doc)
    v = 0.0
    for i, j, k in plotgeo.terrain_triangles(pts, bots):
        a = plotgeo.area([pts[i], pts[j], pts[k]])
        depth = sum(max(0.0, ground_at(plot, pts[q]) - bots[q])
                    for q in (i, j, k)) / 3
        v += a * depth
    return v


# ---- the faces -------------------------------------------------------------------------
def _key(p) -> tuple:
    return (round(p[0], 4), round(p[1], 4))


def _tri_faces(outer, holes, zf, earcut):
    """Triangles over a region (outer + holes, in (x, y)), each point
    lifted by ``zf(point)``, all looking up."""
    allp = [tuple(p) for p in outer]
    starts = []
    for h in holes:
        starts.append(len(allp))
        allp += [tuple(p) for p in h]
    out = []
    for i, j, k in earcut(allp, starts):
        a, b, c = allp[i], allp[j], allp[k]
        if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < 0:
            b, c = c, b
        out.append([(a[0], a[1], zf(a)), (b[0], b[1], zf(b)),
                    (c[0], c[1], zf(c))])
    return out


def _plane(pts3):
    """(a, b, c) with z = a·x + b·y + c through the points when they all lie
    on one plane (a ramp's floor), else None."""
    n = len(pts3)
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = (pts3[i], pts3[j],
                                                            pts3[k])
                den = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)
                if abs(den) < 1e-9:
                    continue
                a = ((z2 - z1) * (y3 - y1) - (z3 - z1) * (y2 - y1)) / den
                b = ((x2 - x1) * (z3 - z1) - (x3 - x1) * (z2 - z1)) / den
                c = z1 - a * x1 - b * y1
                # 5 mm: a ramp's top end is held to the ground (2 mm under
                # the datum) — that must not count as a bend
                ok = all(abs(a * x + b * y + c - z) < 0.005
                         for x, y, z in pts3)
                return (a, b, c) if ok else None
    return None


def _region_faces(outer, holes, zf, earcut):
    """A region's surface → (faces, soft edges): ONE face when it lies on
    a plane (flat, or a straight ramp — no line across it), else
    triangles with their inner edges drawn smooth."""
    pts = list(outer) + [p for h in holes for p in h]
    p3 = [(p[0], p[1], zf(p)) for p in pts]
    if _plane(p3) is not None:
        loop = [(p[0], p[1], zf(p)) for p in _ccw(outer)]
        hl = [[(p[0], p[1], zf(p)) for p in h] for h in holes]
        return [{"loop": loop, "holes": hl} if hl else loop], set()
    tris = _tri_faces(outer, holes, zf, earcut)
    border = set()
    for loop in [outer] + holes:
        for a, b in zip(loop, loop[1:] + loop[:1]):
            border.add(frozenset((_key(a), _key(b))))
    soft = set()
    for t in tris:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            if frozenset((_key(a), _key(b))) not in border:
                soft.add(frozenset((a, b)))
    return tris, soft


def _ccw(loop):
    return loop if plotgeo.signed_area([list(p) for p in loop]) > 0 \
        else list(reversed(loop))


def build(doc: dict, z0: float, earcut, arrange) -> dict:
    plot = doc["plot"]
    pts, hs = plot["corners"], plot["heights"]
    thick = float(plot.get("thickness", 0.0))
    digs = opened(doc)
    faces, soft = [], set()
    tin = tin_of(plot)
    flat = tin["flat"]
    TP = tin["P"]
    # a sloped ground with excavations: the ground's own triangles go into
    # the arrangement too, so every piece lies in ONE of them — the ground
    # between survey points (a hill, a hollow) is followed exactly, and a
    # pit's wall bends where the ground does
    whole = bool(digs) and not flat

    memo: dict = {}

    def gz(p):                                   # natural ground (model z)
        k = (p[0], p[1])
        z = memo.get(k)
        if z is None:
            z = memo[k] = z0 + ground_at(plot, p)
        return z

    ring = [(p[0], p[1], z0 + h) for p, h in zip(pts, hs)]

    # -- the excavations as regions of one arrangement ----------------------------
    regions, by_dig = [], {d["id"]: [] for d in digs}
    bots = {d["id"]: dig_bottoms(d, doc) for d in digs}
    tops = {d["id"]: top_of(d, doc) for d in digs}
    if digs:
        segs = []
        if whole:
            done = set()
            for t in tin["tris"]:
                for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                    e = frozenset((a, b))
                    if e not in done:
                        done.add(e)
                        segs.append((TP[a][:2], TP[b][:2]))
        for d in digs:
            c, t = d["corners"], tops[d["id"]]
            segs += [(t[i], t[(i + 1) % len(t)]) for i in range(len(t))]
            if t is not c:
                # a sloped pit: its floor's edges and the corners' ridges
                # too, so every slope is a clean face of its own
                segs += [(c[i], c[(i + 1) % len(c)]) for i in range(len(c))]
                segs += [(c[i], t[i]) for i in range(len(c))
                         if math.dist(c[i], t[i]) > 1e-4]
        for outer, holes, ip in arrange(segs):
            if ip is None:
                continue
            cover = [d for d in digs
                     if plotgeo.inside_polygon(ip, tops[d["id"]])]
            if not cover:
                regions.append({"outer": outer, "holes": holes, "ip": ip,
                                "dig": None})
                continue
            # a cut wins over a fill (one digs through a platform); among
            # cuts the deepest (a ramp meeting a pit: the pit's floor),
            # among fills the highest
            cuts = [d for d in cover if not is_fill(d)]
            if cuts:
                d = min(cuts, key=lambda d: bottom_at(d, doc, ip,
                                                      bots[d["id"]]))
            else:
                d = max(cover, key=lambda d: bottom_at(d, doc, ip,
                                                       bots[d["id"]]))
            regions.append({"outer": outer, "holes": holes, "ip": ip,
                            "dig": d})

    def floor_z(r):
        """The surface of a region: one plane for all its points, chosen
        by its inside point (a point on its border would be ambiguous)."""
        d = r["dig"]
        if d is None:
            return gz
        if "zf" not in r:
            f = surface(d, doc, r["ip"], bots[d["id"]])
            if is_fill(d):                      # never below the ground
                r["zf"] = lambda p, f=f: max(f(p), gz(p))
            else:                               # never above it
                r["zf"] = lambda p, f=f: min(f(p), gz(p))
        return r["zf"]

    # -- the top: the ground, open where the excavations are ------------------------
    side = {}                                    # edge → regions touching it
    for k, r in enumerate(regions):
        for loop in [r["outer"]] + r["holes"]:
            for a, b in zip(loop, loop[1:] + loop[:1]):
                side.setdefault(frozenset((_key(a), _key(b))), []).append(k)
    rim = [(a, b) for e, ks in side.items()
           if sum(1 for k in ks if regions[k]["dig"] is not None) == 1
           and len(ks) == 1
           for a, b in [tuple(e)]]
    openings = ([o for o, _h, _ip in arrange(rim)] if rim and not whole
                else [])
    if whole:
        # every piece of ground is a region of the arrangement (below);
        # the ground's creases between them drawn smooth, fold lines not
        hard2d = set()
        for e in tin["hard"]:
            a, b = tuple(e)
            hard2d.add((TP[a][:2], TP[b][:2]))

        def on_fold(a, b) -> bool:
            for u, v in hard2d:
                if (plotgeo._dist_to_segment(a, u, v) < 1e-4
                        and plotgeo._dist_to_segment(b, u, v) < 1e-4):
                    return True
            return False

        for e, ks in side.items():
            if len(ks) == 2 and all(regions[k]["dig"] is None for k in ks):
                a, b = tuple(e)
                if not on_fold(a, b):
                    soft.add(frozenset(((a[0], a[1], gz(a)),
                                        (b[0], b[1], gz(b)))))
    elif not openings:
        if flat:
            faces.append(ring)
        else:
            keep = tin["hard"] | tin["sides"]
            R = [(p[0], p[1], z0 + p[2]) for p in TP]
            for i, j, k in tin["tris"]:
                faces.append([R[i], R[j], R[k]])
                for a, b in ((i, j), (j, k), (k, i)):
                    if frozenset((a, b)) not in keep:
                        soft.add(frozenset((R[a], R[b])))
    elif flat:
        faces.append({"loop": ring,
                      "holes": [[(p[0], p[1], gz(p)) for p in o]
                                for o in openings]})
    else:
        tris = _tri_faces([p[:2] for p in pts], openings, gz, earcut)
        border = set()
        for loop in [[tuple(p[:2]) for p in pts]] + openings:
            for a, b in zip(loop, loop[1:] + loop[:1]):
                border.add(frozenset((_key(a), _key(b))))
        for t in tris:
            faces.append(t)
            for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                if frozenset((_key(a), _key(b))) not in border:
                    soft.add(frozenset((a, b)))
    # islands of ground left inside merged excavations: ground on top
    for r in regions:
        if r["dig"] is None:
            fs, sf = _region_faces(r["outer"], r["holes"], gz, earcut)
            faces += fs
            soft |= sf

    # -- each region's floor, and the walls where surfaces differ -------------------
    volumes = {d["id"]: 0.0 for d in digs}
    dig_soft = {d["id"]: set() for d in digs}
    lowest = None
    for r in regions:
        if r["dig"] is None:
            continue
        zf = floor_z(r)
        fl, sf = _region_faces(r["outer"], r["holes"], zf, earcut)
        by_dig[r["dig"]["id"]] += fl
        dig_soft[r["dig"]["id"]] |= sf
        for f in fl:
            loop = f["loop"] if isinstance(f, dict) else f
            lo = min(p[2] for p in loop)
            lowest = lo if lowest is None else min(lowest, lo)
        # earth taken out (a cut) or brought in (a fill): triangles × depth
        sign = -1.0 if is_fill(r["dig"]) else 1.0
        for t in _tri_faces(r["outer"], r["holes"], zf, earcut):
            a = plotgeo.area([list(p[:2]) for p in t])
            depth = sum(max(0.0, sign * (gz(p[:2]) - p[2])) for p in t) / 3
            volumes[r["dig"]["id"]] += a * depth
    for e, ks in side.items():
        a, b = tuple(e)
        sides = [regions[k] for k in ks]
        if len(sides) == 1:
            sides.append({"dig": None, "ip": None})   # the ground outside
        ra, rb = sides
        za, zb = floor_z(ra), floor_z(rb)
        da = [za(a), za(b)]
        db = [zb(a), zb(b)]
        if all(abs(x - y) < EPS for x, y in zip(da, db)):
            continue                                  # level: no wall
        low, high = (ra, rb) if sum(da) < sum(db) else (rb, ra)
        owner = low["dig"] or high["dig"]      # a pit's wall / a fill's edge
        if owner is None:
            continue
        zl, zh = floor_z(low), floor_z(high)
        loop = [(a[0], a[1], zl(a)), (b[0], b[1], zl(b)),
                (b[0], b[1], zh(b)), (a[0], a[1], zh(a))]
        loop = [p for k, p in enumerate(loop) if p != loop[k - 1]]
        if len(loop) < 3:
            continue
        # it faces the lower side: toward the open pit, or away from the
        # raised fill (the ground outside has no inside point)
        nx, ny = (b[1] - a[1]), -(b[0] - a[0])       # right of a → b
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        if low["ip"] is not None:
            toward = (low["ip"][0] - mx) * nx + (low["ip"][1] - my) * ny
        else:
            toward = -((high["ip"][0] - mx) * nx + (high["ip"][1] - my) * ny)
        if toward < 0:
            loop = list(reversed(loop))
        by_dig[owner["id"]].append(loop)

    # -- the block: sides down to a flat bottom under everything ---------------------
    if thick > 0:
        zb = z0 + min(p[2] for p in TP) - thick
        if lowest is not None:
            zb = min(zb, lowest - MIN_THICK)
        bot = [(p[0], p[1], zb) for p in pts]
        faces.append(list(reversed(bot)))
        n = len(pts)
        for i in range(n):
            j = (i + 1) % n
            faces.append([bot[i], bot[j], ring[j], ring[i]])

    return {"plot": {"faces": faces, "soft": soft},
            "digs": [(d, by_dig[d["id"]]) for d in digs],
            "dig_soft": dig_soft,
            "volumes": volumes}
