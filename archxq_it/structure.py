"""ArchXQ structure — the ENGINE. Pure: no IngeTrazo, no Qt.

Columns, beams, slabs and footings, and how they sit with the walls,
level by level. ``build(doc, union)`` gives every element of the
building (walls too) with its faces, at its true heights:

- a level's SLAB has its top at the level's floor (+ its offset); the
  walls and columns of the level BELOW stop at its underside; a BEAM's
  height includes the slab: its top is flush with the slab's top, the rest
  hangs under it (how a 20×60 beam is specified);
- COLUMNS and BEAMS are 1 mm smaller on every face: inside a wall of the
  same width they hide (no two faces in one plane, nothing flickers);
  wider, they read as pilasters / downstand beams;
- a FOOTING hangs under its level's slab (its top at the slab's
  underside, or at the floor without a slab).

Records (``doc["structure"]``): {"id", "name", "type", "level", …}
    column  x, y, shape "rect"|"round", w, d (rect; round: w = Ø),
            angle (°), anchor "centre"|"corner", height "level"|m
    beam    a, b, w (width), h (height)
    slab    corners [[x, y]…], t, offset
    footing kind "pad": x, y, w, d (depth), angle
            kind "strip": a, b (or an arc's "m"), w, d
    roof    kind "gable"|"hip"|"flat"|"shed"|"hidden", corners, slope,
            overhang, go, t, fall, slopes, pauto, gutter,
            ridge "long"|"short", parapet, pt — on its level's wall tops
"""
from __future__ import annotations

import math

from . import walls as W

SHRINK = 0.001          # m off every face of columns and beams
#: …and of the ones FITTED inside a wall: the host draws edges with a
#: small depth offset, and 1 mm behind a wall's face their lines showed
#: through it (seen on the demo, 2026-10-03) — 1 cm hides them, and a
#: hidden structure 2 cm slimmer is never seen
FIT_SHRINK = 0.01
#: a beam's / a tall column's top under a FLOOR: 1 cm (at 1 mm their edges
#: showed through the slab's top surface — his screen, 2026-10-09)
TOP_GAP = 0.01
ROUND_SEGS = 24         # a round column's sides
TYPES = ("column", "beam", "slab", "footing", "roof", "ramp", "stair")
LABEL = {"column": "Column", "beam": "Beam", "slab": "Slab",
         "footing": "Footing", "wall": "Wall", "roof": "Roof",
         "ramp": "Ramp", "stair": "Stair"}


# ---- levels ------------------------------------------------------------------------
def levels_info(doc: dict, elevations) -> dict:
    """Per level id: z0 (floor), height, the slab thickness ON it, and
    ``under`` = where things of this level stop (the next level's slab
    underside; the level's top without one)."""
    levels = doc["levels"]
    ground = doc["project"]["ground_level"] if doc.get("project") else 0.0
    elev = elevations(levels, ground)
    slab_t = {}
    for s in doc.get("structure") or []:
        if s["type"] == "slab":
            slab_t[s["level"]] = max(slab_t.get(s["level"], 0.0),
                                     float(s["t"]) - float(s.get("offset", 0)))
    out = {}
    for i, lv in enumerate(levels):
        top = elev[i] + float(lv["height"])
        above = levels[i + 1]["id"] if i + 1 < len(levels) else None
        out[lv["id"]] = {"z0": elev[i], "height": float(lv["height"]),
                         "slab": slab_t.get(lv["id"], 0.0),
                         "under": top - (slab_t.get(above, 0.0) if above
                                         else 0.0)}
    return out


def ground_under(doc: dict, info: dict, lid: str, p) -> float | None:
    """The excavation's floor under a point of level ``lid``, when it lies
    BELOW that level's floor and no other floor comes between — the
    lowest basement sitting in a pit 30 cm deeper than its floor. Its
    columns and footings reach down to that ground instead of hanging in
    the air (his ask, 2026-10-06: «Base −0.30, Height 6.30» by hand was
    confusing). None = nothing to reach for."""
    from . import plotgeo
    from . import terrain as T
    z0 = info[lid]["z0"]
    low = None
    for d in doc.get("digs") or []:
        if T.is_fill(d) or not plotgeo.inside_polygon(p, d["corners"]):
            continue
        z = T.bottom_at(d, doc, p)
        low = z if low is None else min(low, z)
    if low is None or low >= z0 - 1e-4:
        return None
    if any(low - 1e-4 <= v["z0"] < z0 - 1e-4 for k, v in info.items()
           if k != lid):
        return None                    # a floor in between holds it
    return low


def deepest_below(doc: dict, elevations) -> float | None:
    """The lowest point the structure reaches into the ground — its
    footings' bottoms, its columns' feet — as ``build`` makes them; None
    = no footing nor column. The terrain's ground goes down under it (a
    customer's report, 2026-10-13: footings poked out under the ground's
    bottom, and showed in the sections)."""
    info = levels_info(doc, elevations)
    low = None
    for e in doc.get("structure") or []:
        lid = e.get("level")
        if lid not in info or why_not(e):
            continue
        li = info[lid]
        z = None
        if e["type"] == "footing":
            if e.get("kind") == "strip":
                p = ((e["a"][0] + e["b"][0]) / 2, (e["a"][1] + e["b"][1]) / 2)
            else:
                p = (float(e["x"]), float(e["y"]))
            top = li["z0"] - li["slab"]
            g = ground_under(doc, info, lid, p)
            top = top if g is None else min(top, g)
            z = top - float(e["d"])
        elif e["type"] == "column":
            z = li["z0"] + float(e.get("base", 0.0))
            if float(e.get("base", 0.0)) <= 0:
                g = ground_under(doc, info, lid, column_centre(e))
                z = z if g is None else min(z, g)
        if z is not None:
            low = z if low is None else min(low, z)
    return low


# ---- plans ---------------------------------------------------------------------------
def _rot(p, c, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * ca - y * sa, c[1] + x * sa + y * ca)


def column_outline(c: dict, shrink: float = SHRINK) -> list:
    """The column's section in plan, counter-clockwise."""
    x, y = float(c["x"]), float(c["y"])
    w = float(c["w"]) - 2 * shrink
    if c.get("shape") == "round":
        r = w / 2.0
        return [(x + r * math.cos(2 * math.pi * k / ROUND_SEGS),
                 y + r * math.sin(2 * math.pi * k / ROUND_SEGS))
                for k in range(ROUND_SEGS)]
    d = float(c["d"]) - 2 * shrink
    ang = math.radians(float(c.get("angle", 0.0)))
    # (x, y) is the column's insertion point: its centre, a corner or a
    # side's middle (``anchor``) — the section's middle sits off it
    ax, ay = ANCHORS.get(c.get("anchor", "centre"), (0, 0))
    W, D = float(c["w"]), float(c["d"])
    mx, my = x - ax * W / 2, y - ay * D / 2
    pts = [(mx - w / 2, my - d / 2), (mx + w / 2, my - d / 2),
           (mx + w / 2, my + d / 2), (mx - w / 2, my + d / 2)]
    return [_rot(p, (x, y), ang) for p in pts]


#: the insertion points of a rectangular column: (−1|0|1 across, along)
#: — «corner» (older files) is the lower left one
ANCHORS = {"centre": (0, 0), "sw": (-1, -1), "corner": (-1, -1),
           "s": (0, -1), "se": (1, -1), "e": (1, 0), "ne": (1, 1),
           "n": (0, 1), "nw": (-1, 1), "w": (-1, 0)}


def column_centre(c: dict):
    """Where the column's axis is (off-centre insertion: the section's
    middle)."""
    if c.get("anchor", "centre") == "centre" or c.get("shape") == "round":
        return (float(c["x"]), float(c["y"]))
    pts = column_outline(c, 0.0)
    return (sum(p[0] for p in pts) / 4, sum(p[1] for p in pts) / 4)


def pad_outline(f: dict) -> list:
    x, y, w = float(f["x"]), float(f["y"]), float(f["w"])
    ang = math.radians(float(f.get("angle", 0.0)))
    pts = [(x - w / 2, y - w / 2), (x + w / 2, y - w / 2),
           (x + w / 2, y + w / 2), (x - w / 2, y + w / 2)]
    return [_rot(p, (x, y), ang) for p in pts]


def _ccw(loop):
    a = 0.5 * sum(p[0] * q[1] - q[0] * p[1]
                  for p, q in zip(loop, loop[1:] + loop[:1]))
    return list(loop) if a >= 0 else list(reversed(loop))


def as_wall(e: dict, width_key: str = "w", shrink: float = SHRINK) -> dict:
    """A beam or a strip footing, as a centre-aligned «wall» — the walls
    engine joins them (L, T, X) exactly as it joins walls."""
    rec = {"id": e["id"], "name": e.get("name", ""),
           "kind": "arc" if e.get("m") else "line",
           "a": list(e["a"]), "b": list(e["b"]),
           "t": float(e[width_key]) - 2 * shrink, "align": "centre",
           "side": 1}
    if e.get("m"):
        rec["m"] = list(e["m"])
    return rec


def why_not(e: dict) -> str | None:
    """Why an element can't be built (None = it can)."""
    t = e.get("type")
    try:
        if t == "column":
            if float(e["w"]) < 0.05 or (e.get("shape") != "round"
                                        and float(e["d"]) < 0.05):
                return "A column needs a section of 5 cm at least"
        elif t == "beam":
            if float(e["w"]) < 0.05 or float(e["h"]) < 0.05:
                return "A beam needs a width and a height"
            if math.dist(e["a"], e["b"]) < max(float(e["w"]), 0.1):
                return "Too short for a beam"
        elif t == "slab":
            if len(e["corners"]) < 3 or float(e["t"]) < 0.02:
                return "A slab needs three corners and a thickness"
            if abs(_area(e["corners"])) < 0.05:
                return "Too small for a slab"
        elif t == "footing":
            if float(e["w"]) < 0.1 or float(e["d"]) < 0.05:
                return "A footing needs a width and a depth"
            if e.get("kind") == "strip" and math.dist(e["a"], e["b"]) < 0.1:
                return "Too short for a footing"
        elif t == "roof":
            if len(e["corners"]) < 3 or abs(_area(e["corners"])) < 1.0:
                return "Too small for a roof"
            if e.get("kind") != "flat" and not \
                    5.0 <= float(e["slope"]) <= 75.0:
                return "A pitched roof needs a slope of 5° to 75°"
            if e.get("kind") == "hidden" and len(e["corners"]) == 4:
                _c, _u, ha, _v, hb = rect_frame(e["corners"])
                room = min(ha, hb) - float(e.get("pt", 0.15))
                need = float(e.get("gutter", 0.30)) * (
                    2 if int(e.get("slopes", 2)) == 2 else 1) / 2 + 0.30
                if room < need:
                    return "Too narrow for a hidden roof (its parapet and " \
                           "gutter take the room)"
        elif t == "ramp":                  # a «Building element» (ramps.py)
            from .ramps import why_not as ramp_why
            return ramp_why(e)
        elif t == "stair":                 # a «Building element» (stairs.py)
            from .stairs import why_not as stair_why
            return stair_why(e)
        else:
            return "Unknown element"
    except (KeyError, TypeError, ValueError):
        return "Incomplete element"
    return None


def _area(pts) -> float:
    return 0.5 * sum(p[0] * q[1] - q[0] * p[1]
                     for p, q in zip(pts, list(pts[1:]) + [pts[0]]))


# ---- structure INSIDE the walls (the usual case — his rule, 2026-10-03) ---------------
FIT_TOL = 0.02          # m past a wall's face that still counts as on it


def _walls_at(p, walls: list[dict]) -> list[tuple]:
    """[(wall, centre seg, fraction)] of the walls whose body holds p."""
    out = []
    for w in walls:
        if W.why_not(w) is not None:
            continue
        s = W.centre(w)
        f, off = s.project(p)
        if (W.is_closed(w) or -1e-6 <= f <= 1 + 1e-6) \
                and abs(off) <= float(w["t"]) / 2 + FIT_TOL:
            out.append((w, s, f % 1.0 if W.is_closed(w) else f))
    return out


def fit_column(c: dict, walls: list[dict]) -> dict:
    """A column standing on a wall goes INSIDE it: as thick as the wall,
    turned with it, on its centre line (its length along the wall kept).
    Where walls meet (a corner, a T): a square as thick as the thinnest.
    Off the walls: as it was drawn."""
    p = column_centre(c)
    here = _walls_at(p, walls)
    if not here:
        return dict(c, fit=False)
    # from here on its insertion point is its middle (an off-centre one —
    # a corner — moved there: it kept the corner's place before)
    c = dict(c, anchor="centre", fit=True, x=round(p[0], 4),
             y=round(p[1], 4))
    dirs = []
    for w, s, f in here:
        u = s.tangent(f)
        if not any(abs(u[0] * v[1] - u[1] * v[0]) < 0.05 for v in dirs):
            dirs.append(u)
    t = min(float(w["t"]) for w, _s, _f in here)
    w0, s0, f0 = here[0]
    if len(dirs) >= 2:                          # walls meeting: a square
        c.update(w=t, d=t)
    else:                                       # on one wall: in its line
        q = s0.at(min(max(f0, 0.0), 1.0))
        c.update(x=round(q[0], 4), y=round(q[1], 4),
                 w=max(float(c["w"]), float(c.get("d", c["w"]))), d=t)
        if c.get("shape") == "round":
            c.update(w=t, d=t)
    u = s0.tangent(f0)
    c["angle"] = round(math.degrees(math.atan2(u[1], u[0])), 3)
    if c.get("shape") == "round":
        c["w"] = c["d"] = t
    return c


def fit_beam(b: dict, walls: list[dict]) -> dict:
    """A beam on the line of a wall (along all of it, or running past it
    into the next room) takes the wall's thickness — where the wall is,
    it hides in it; past it, it reads as a downstand beam of the same
    width."""
    ax, ay = b["a"]
    bx, by = b["b"]
    L = math.hypot(bx - ax, by - ay)
    if L < 1e-9:
        return dict(b, fit=False)
    u = ((bx - ax) / L, (by - ay) / L)
    best = None
    for w in walls:
        if W.why_not(w) is not None or w.get("kind", "line") != "line":
            continue
        s = W.centre(w)
        if abs(u[0] * s.u[1] - u[1] * s.u[0]) > 0.01:
            continue                             # not the same way
        f0, off0 = s.project(b["a"])
        f1, off1 = s.project(b["b"])
        tol = float(w["t"]) / 2 + FIT_TOL
        if abs(off0) > tol or abs(off1) > tol:
            continue                             # not on its line
        if max(f0, f1) < 0.0 or min(f0, f1) > 1.0:
            continue                             # beside it, not along it
        t = float(w["t"])
        best = t if best is None else min(best, t)
    if best is None:
        return dict(b, fit=False)
    return dict(b, w=best, fit=True)


# ---- derived from the walls ----------------------------------------------------------
def wall_corners(walls: list[dict]) -> list:
    """Where the level's walls MEET (corners, T, X) — on their centre
    lines, so a column there sits in the middle of the walls (an outside-
    aligned wall's drawn corner is its outer corner: a column there would
    hang half out)."""
    good = [w for w in walls if W.why_not(w) is None and not W.is_closed(w)]
    centres = [W.centre(w) for w in good]
    ends = []                                  # (drawn point, wall index)
    for i, w in enumerate(good):
        d = W.drawn(w)
        ends += [(d.at(0.0), i), (d.at(1.0), i)]
    groups: list = []
    for p, i in ends:
        for g in groups:
            if math.dist(g[0], p) <= W.JOIN_TOL:
                g[1].add(i)
                break
        else:
            groups.append([p, {i}])
    # an end on another wall's body is a corner too (a T)
    for g in groups:
        if len(g[1]) == 1:
            for j, s in enumerate(centres):
                if j in g[1]:
                    continue
                f, off = s.project(g[0])
                if 0.0 < f < 1.0 and abs(off) <= good[j]["t"] / 2 + W.BODY_TOL:
                    g[1].add(j)
    out = []
    for p, ids in groups:
        if len(ids) < 2:
            continue
        ids = sorted(ids)
        pt = None
        for a in ids:
            for b in ids:
                if b <= a or centres[a].kind != "line" \
                        or centres[b].kind != "line":
                    continue
                got = W._meet(("line", centres[a].p0, centres[a].u),
                              ("line", centres[b].p0, centres[b].u))
                if got and math.dist(got[0], p) <= max(
                        good[a]["t"], good[b]["t"]) + W.JOIN_TOL:
                    pt = got[0]
                    break
            if pt:
                break
        out.append(tuple(pt) if pt else tuple(p))
    return out


def inside_walls(walls: list[dict], union) -> list | None:
    """A slab's outline from the level's walls: the outer contour of all
    of them together (``union(polygons) → outer loop`` is the host's
    shapely, handed in). None without walls."""
    plans = W.plan([w for w in walls if W.why_not(w) is None])
    polys = [pc for pieces in plans.values() for pc in pieces]
    if not polys:
        return None
    loop = union(polys)
    if not loop or len(loop) < 3:
        return None
    return [[round(p[0], 4), round(p[1], 4)] for p in _ccw(loop)]


def along_walls(walls: list[dict]) -> list[tuple]:
    """Beams over the level's straight walls: on each wall's centre line,
    end to end (curved / round walls are left out)."""
    out = []
    for w in walls:
        if W.why_not(w) is not None or w.get("kind", "line") != "line":
            continue
        s = W.centre(w)
        out.append(([round(s.p0[0], 4), round(s.p0[1], 4)],
                    [round(s.p1[0], 4), round(s.p1[1], 4)]))
    return out


def strips_under(walls: list[dict]) -> list[dict]:
    """Strip footings under the walls: on each wall's centre line (a
    curved wall's too)."""
    out = []
    for w in walls:
        if W.why_not(w) is not None or W.is_closed(w):
            continue
        s = W.centre(w)
        rec = {"a": [round(s.at(0.0)[0], 4), round(s.at(0.0)[1], 4)],
               "b": [round(s.at(1.0)[0], 4), round(s.at(1.0)[1], 4)]}
        if s.kind == "arc":
            m = s.at(0.5)
            rec["m"] = [round(m[0], 4), round(m[1], 4)]
        out.append(rec)
    return out


def footing_plans(struct: list[dict], lid: str) -> list[tuple]:
    """[(id, [loop…])] — the footings of level ``lid`` in plan, as built
    (pads square, strips joined like walls): what the plan draws dashed,
    hidden under the floor."""
    els = [e for e in struct if e["level"] == lid and e["type"] == "footing"
           and why_not(e) is None]
    out = [(f["id"], [pad_outline(f)]) for f in els if f.get("kind") == "pad"]
    strips = [e for e in els if e.get("kind") == "strip"]
    plans = W.plan([as_wall(e, shrink=0.0) for e in strips])
    for f in strips:
        out.append((f["id"], [pc["outer"] for pc in plans.get(f["id"], ())]))
    return out


def level_plan_loops(doc: dict, lid: str) -> list:
    """Every outline of level ``lid`` in plan — walls (joined), columns,
    beams, slabs, footings: what the GHOST of a level draws under the one
    worked on (Revit's underlay, ArchiCAD's ghost story)."""
    struct = doc.get("structure") or []
    loops = []
    walls = [w for w in doc.get("walls") or [] if w["level"] == lid]
    for pieces in W.plan(walls).values():
        for pc in pieces:
            loops.append(pc["outer"])
            loops += list(pc.get("holes") or [])
    els = [e for e in struct if e["level"] == lid and why_not(e) is None]
    loops += [column_outline(c, 0.0) for c in els if c["type"] == "column"]
    beams = [e for e in els if e["type"] == "beam"]
    for pieces in W.plan([as_wall(e, shrink=0.0) for e in beams]).values():
        loops += [pc["outer"] for pc in pieces]
    for s in (e for e in els if e["type"] == "slab"):
        loops.append([tuple(p) for p in s["corners"]])
        loops += [[tuple(p) for p in h] for h in s.get("holes") or []]
    for _fid, ls in footing_plans(struct, lid):
        loops += ls
    # ramps and stairs, their outline in plan (his screen, 2026-10-07: the
    # ghost of Basement 1 did not show its entrance ramps)
    rs = [e for e in els if e["type"] in ("ramp", "stair")]
    if rs:
        from . import model
        from . import ramps as R
        for r in rs:
            try:
                if r["type"] == "ramp":
                    zs, ze = R.heights(r, doc, model.elevations)
                    polys = R.footprints(r, zs, ze, R.length_of(r, zs, ze))
                else:
                    from . import stairs as ST
                    polys = ST.footprints(r, doc, model.elevations)
            except Exception:  # noqa: BLE001 — a ghost never breaks
                continue
            loops += [[tuple(p[:2]) for p in poly] for poly in polys]
    return loops


def rows_of(c: dict, columns: list) -> list:
    """The rows a column stands in («Select its row», his call,
    2026-10-09): the ids of its level's columns whose centres lie on the
    line through it along its width, or across it — within half its larger
    side. A row is two columns at least. No row is stored: it is read."""
    a = math.radians(float(c.get("angle", 0.0)))
    tol = max(float(c["w"]), float(c.get("d", c["w"]))) / 2
    out = []
    for u in ((math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))):
        ids = [o["id"] for o in columns
               if o["type"] == "column" and o["level"] == c["level"]
               and abs((float(o["x"]) - float(c["x"])) * u[1]
                       - (float(o["y"]) - float(c["y"])) * u[0]) <= tol]
        if len(ids) >= 2 and ids not in out:
            out.append(ids)
    return out


def push_inside(outline, pits, along=None) -> tuple:
    """(dx, dy) that brings a footing crossing an excavation's side back
    inside it, its face flush with the side — a boundary (eccentric)
    footing: on site it cannot reach past the retaining face (his call,
    2026-10-06). Only the pit its middle stands in; ``along`` (a unit
    vector) = only the sides parallel to it (a strip moves across)."""
    from . import plotgeo
    n = len(outline)
    c = (sum(p[0] for p in outline) / n, sum(p[1] for p in outline) / n)
    dx = dy = 0.0
    for poly in pits:
        if not plotgeo.inside_polygon(c, poly):
            continue
        area = sum(poly[i][0] * poly[(i + 1) % len(poly)][1]
                   - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))
        sgn = 1.0 if area > 0 else -1.0          # counter-clockwise: +
        for i in range(len(poly)):
            p, q = poly[i], poly[(i + 1) % len(poly)]
            L = math.dist(p, q)
            if L < 1e-9:
                continue
            u = ((q[0] - p[0]) / L, (q[1] - p[1]) / L)
            if along is not None and abs(u[0] * along[1]
                                         - u[1] * along[0]) > 0.02:
                continue
            nout = (u[1] * sgn, -u[0] * sgn)
            ss = [(o[0] - p[0]) * u[0] + (o[1] - p[1]) * u[1] for o in outline]
            if max(ss) <= 0 or min(ss) >= L:      # beside this side, not on it
                continue
            over = max((o[0] - p[0]) * nout[0] + (o[1] - p[1]) * nout[1]
                       for o in outline)
            if over > 1e-4:
                dx -= nout[0] * over
                dy -= nout[1] * over
        break
    return dx, dy


ROW_GAP = 8.5           # m — columns further apart are not one row


def strips_under_columns(cols: list[dict], width: float,
                         pits=()) -> list[dict]:
    """Strip footings under the ROWS of columns (his ask, 2026-10-06: the
    columns along an excavation share one continuous footing, which the
    retaining wall later stands on too). A row = 2+ columns on one line
    (within half a strip — a corner column a few cm off still counts),
    none more than ROW_GAP from the next. Each strip runs end column to
    end column, half its width past them; an end near another row's line
    stops ON it, so the strips meet in clean corners. [{"a", "b", "w"}]"""
    pts = [column_centre(c) for c in cols]
    if len(pts) < 2:
        return []
    dirs = set()
    for c in cols:
        a = float(c.get("angle", 0.0)) % 180.0
        for d in (a, (a + 90.0) % 180.0):
            dirs.add(round(d * 2) / 2 % 180.0)        # to ½°
    tol = width / 2
    lines = []          # (u, n, t, s0, s1, w)
    for d in sorted(dirs):
        r = math.radians(d)
        u, n = (math.cos(r), math.sin(r)), (-math.sin(r), math.cos(r))
        st = sorted(((p[0] * n[0] + p[1] * n[1], p[0] * u[0] + p[1] * u[1], k)
                     for k, p in enumerate(pts)))
        groups, cur = [], [st[0]]
        for e in st[1:]:
            if e[0] - cur[-1][0] <= tol:
                cur.append(e)
            else:
                groups.append(cur)
                cur = [e]
        groups.append(cur)
        for g in groups:
            g = sorted(g, key=lambda e: e[1])
            runs, run = [], [g[0]]
            for e in g[1:]:
                if e[1] - run[-1][1] <= ROW_GAP:
                    run.append(e)
                else:
                    runs.append(run)
                    run = [e]
            runs.append(run)
            for run in runs:
                if len(run) < 2:
                    continue
                ts = sorted(e[0] for e in run)
                t = ts[len(ts) // 2]                  # the row's own line
                w = max([width] + [min(float(cols[e[2]]["w"]),
                                       float(cols[e[2]]["d"])) + 0.20
                                   for e in run])
                if pits:          # along a pit's side: flush inside it
                    s0, s1 = run[0][1], run[-1][1]
                    rect = [(n[0] * tt + u[0] * ss, n[1] * tt + u[1] * ss)
                            for tt, ss in ((t - w / 2, s0), (t + w / 2, s0),
                                           (t + w / 2, s1), (t - w / 2, s1))]
                    sx, sy = push_inside(rect, pits, along=u)
                    t += sx * n[0] + sy * n[1]
                lines.append([u, n, t, run[0][1], run[-1][1], w])
    # the same row found from two directions (a square grid): once
    seen, uniq = set(), []
    for ln in lines:
        key = (round(ln[1][0], 3), round(ln[1][1], 3), round(ln[2], 2),
               round(ln[3], 2), round(ln[4], 2))
        if key not in seen:
            seen.add(key)
            uniq.append(ln)
    out = []
    for i, (u, n, t, s0, s1, w) in enumerate(uniq):
        ends = []
        for s, sign in ((s0, -1.0), (s1, 1.0)):
            p = (n[0] * t + u[0] * s, n[1] * t + u[1] * s)
            best = None
            for j, (u2, n2, t2, a2, b2, w2) in enumerate(uniq):
                den = u[0] * n2[0] + u[1] * n2[1]
                if j == i or abs(den) < 0.2:          # parallel: no corner
                    continue
                k = (t2 - (p[0] * n2[0] + p[1] * n2[1])) / den
                x = (p[0] + u[0] * k, p[1] + u[1] * k)
                s2 = x[0] * u2[0] + x[1] * u2[1]
                if abs(k) <= ROW_GAP and a2 - w2 <= s2 <= b2 + w2 \
                        and (best is None or abs(k) < abs(best[0])):
                    best = (k, x)
            if best is not None:                      # meets that row
                ends.append(best[1])
            else:                                     # half a strip past
                ends.append((p[0] + u[0] * sign * w / 2,
                             p[1] + u[1] * sign * w / 2))
        a, b = ends
        if math.dist(a, b) > 0.05:
            out.append({"a": [round(a[0], 4), round(a[1], 4)],
                        "b": [round(b[0], 4), round(b[1], 4)],
                        "w": round(w, 3)})
    return out


# ---- openings: doors, windows, voids in the walls -----------------------------------
#: an opening: {"id", "name", "kind": "door" | "window" | "void",
#:   "wall": wall id, "pos": its centre along the wall's line (m from the
#:   wall's start), "w", "h", "sill" (from the level's floor),
#:   "swing": "left" | "right" (a door's hinge, seen from inside — a
#:   sliding door: the side it slides to), a door's "op": "swing" |
#:   "sliding" and "leaves": 1 | 2 (the library's types, 2026-10-08)}
OPENING_LABEL = {"door": "Door", "window": "Window", "void": "Opening"}
RAIL = 0.04             # m, a sliding door's rail (height and depth)
FRAME = 0.05            # m, a frame's face width
FRAME_DEPTH = 0.07      # m, a frame's depth through the wall
LEAF = 0.04             # m, a door leaf
FRAME_COLOR = (0.94, 0.94, 0.92, 1.0)
GLASS_COLOR = (0.62, 0.80, 0.90, 0.35)
LEAF_COLOR = (0.58, 0.42, 0.28, 1.0)
END_GAP = 0.10          # m kept between an opening and its wall's end


def opening_room(o: dict, wall: dict, others: list[dict],
                 wall_height: float) -> str | None:
    """Why an opening can't go there (None = it can): it must sit on a
    straight wall, wholly, clear of the wall's ends and of the wall's
    other openings, under the wall's top."""
    if wall.get("kind", "line") != "line":
        return "Openings go in straight walls (curved: not yet)"
    L = W.drawn(wall).L
    half = float(o["w"]) / 2
    if float(o["w"]) < 0.2 or float(o["h"]) < 0.2:
        return "Too small for an opening"
    if o["pos"] - half < END_GAP or o["pos"] + half > L - END_GAP:
        return "It doesn't fit in that wall"
    if float(o.get("sill", 0)) + float(o["h"]) > wall_height - 0.05:
        return "Too tall for that wall"
    for p in others:
        if p.get("id") == o.get("id") or p["wall"] != o["wall"]:
            continue
        if abs(p["pos"] - o["pos"]) < (float(p["w"]) + float(o["w"])) / 2 \
                + 0.05:
            return "It runs into another opening of that wall"
    return None


def _clip(poly, p0, u, s, keep_more: bool) -> list:
    """The part of a plan polygon on one side of the line across the
    wall's axis at distance s (Sutherland–Hodgman, one half-plane)."""
    def d(p):
        return ((p[0] - p0[0]) * u[0] + (p[1] - p0[1]) * u[1] - s) * \
            (1 if keep_more else -1)
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        da, db = d(a), d(b)
        if da >= 0:
            out.append(a)
        if (da >= 0) != (db >= 0):
            t = da / (da - db)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out if len(out) >= 3 and abs(_area(out)) > 1e-9 else []


def wall_with_openings(piece: dict, seg, ops: list[dict], z0: float,
                       b: float, top: float, dropped: bool = False) -> list:
    """A straight wall's solid with its openings, made as a plan draws
    it: each long face is ONE face with the openings cut out of it (a
    window: a hole; a door: a notch from the floor) — no seams running
    floor to ceiling past the jambs; then the openings' own faces (jambs,
    head, sill); the top and bottom faces lose what the openings take."""
    from shapely.geometry import Polygon, box
    from shapely.geometry.polygon import orient
    from shapely.ops import unary_union

    p0, u = seg.p0, seg.u
    poly = _ccw(list(piece["outer"]))
    eps = 1e-4
    spans = []                       # (s0, s1, zs, zt) — clipped to the wall
    for o in ops:
        zs = max(b, z0 + float(o.get("sill", 0.0)))
        # a wall gone down through its slab: a door's sill face 1 cm under
        # the floor — on it, it would share the slab's top; down to the
        # wall's foot, a 20 cm pit showed under every door
        if dropped and float(o.get("sill", 0.0)) <= 0:
            zs = max(b, z0 - 0.01)
        zt = min(top, z0 + float(o.get("sill", 0.0)) + float(o["h"]))
        if zt - zs > 0.01:
            spans.append((o["pos"] - o["w"] / 2, o["pos"] + o["w"] / 2,
                          zs, zt))

    def S(p):
        return (p[0] - p0[0]) * u[0] + (p[1] - p0[1]) * u[1]

    faces = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        L = math.dist(p, q)
        if L < 1e-9:
            continue
        d = ((q[0] - p[0]) / L, (q[1] - p[1]) / L)
        along = abs(d[0] * u[1] - d[1] * u[0]) < 1e-6
        if not along:                # an end (square, mitred): whole
            faces.append([(p[0], p[1], b), (q[0], q[1], b),
                          (q[0], q[1], top), (p[0], p[1], top)])
            continue
        # this long face in its own (t along p→q, z) plane
        sp, sign = S(p), 1.0 if (d[0] * u[0] + d[1] * u[1]) > 0 else -1.0
        cut = []
        for s0, s1, zs, zt in spans:
            t0, t1 = sorted(((s0 - sp) * sign, (s1 - sp) * sign))
            if t1 > eps and t0 < L - eps:
                cut.append(box(t0, zs - (eps if zs <= b + eps else 0),
                               t1, zt + (eps if zt >= top - eps else 0)))
        region = box(0, b, L, top)
        if cut:
            region = region.difference(unary_union(cut))
        for g in getattr(region, "geoms", [region]):
            if g.is_empty or g.area < 1e-8:
                continue
            g = orient(g, 1.0)

            def P3(tz):
                t, z = tz
                return (p[0] + d[0] * t, p[1] + d[1] * t, z)
            faces.append({"loop": [P3(c) for c in list(g.exterior.coords)
                                   [:-1]],
                          "holes": [[P3(c) for c in list(r.coords)[:-1]]
                                    for r in g.interiors]})
    # the openings' own faces: jambs, head, sill (across the wall)
    nrm = (-u[1], u[0])
    for s0, s1, zs, zt in spans:
        # where the two long faces are at s (the faces' across offsets)
        offs = sorted({round((pt[0] - p0[0]) * nrm[0]
                             + (pt[1] - p0[1]) * nrm[1], 6) for pt in poly})
        c_lo, c_hi = offs[0], offs[-1]

        def P(s, c, z):
            return (p0[0] + u[0] * s + nrm[0] * c,
                    p0[1] + u[1] * s + nrm[1] * c, z)
        # jambs: at s0 facing +u, at s1 facing −u (into the opening);
        # (u, n, z) is right-handed: n × z = u
        faces.append([P(s0, c_lo, zs), P(s0, c_hi, zs), P(s0, c_hi, zt),
                      P(s0, c_lo, zt)])
        faces.append([P(s1, c_lo, zs), P(s1, c_lo, zt), P(s1, c_hi, zt),
                      P(s1, c_hi, zs)])
        if zt < top - eps:                       # the head, facing down
            faces.append([P(s0, c_lo, zt), P(s0, c_hi, zt), P(s1, c_hi, zt),
                          P(s1, c_lo, zt)])
        if zs > b + eps:                         # the sill, facing up
            faces.append([P(s0, c_lo, zs), P(s1, c_lo, zs), P(s1, c_hi, zs),
                          P(s0, c_hi, zs)])
    # top and bottom: the plan, less what reaches them
    for z, up in ((top, True), (b, False)):
        plan = Polygon(poly)
        bands = [box(min(s0, s1), -1e3, max(s0, s1), 1e3)
                 for s0, s1, zs, zt in spans
                 if (zt >= top - eps if up else zs <= b + eps)]
        if bands:
            from shapely import affinity
            ang = math.degrees(math.atan2(u[1], u[0]))
            band = affinity.rotate(unary_union(bands), ang, origin=(0, 0))
            band = affinity.translate(band, p0[0], p0[1])
            plan = plan.difference(band)
        for g in getattr(plan, "geoms", [plan]):
            if g.is_empty or g.area < 1e-8:
                continue
            g = orient(g, 1.0)
            loop = [(c[0], c[1], z) for c in list(g.exterior.coords)[:-1]]
            holes = [[(c[0], c[1], z) for c in list(r.coords)[:-1]]
                     for r in g.interiors]
            if not up:                           # the bottom faces down
                loop = list(reversed(loop))
                holes = [list(reversed(h)) for h in holes]
            faces.append({"loop": loop, "holes": holes})
    return faces


def _box(p0, u, n, sa, sb, ca, cb, za, zb, color) -> list:
    """A box along a wall: axial sa..sb, across ca..cb (n side), height
    za..zb — six faces, outward, each with its colour."""
    def P(s, c, z):
        return (p0[0] + u[0] * s + n[0] * c, p0[1] + u[1] * s + n[1] * c, z)
    c = [P(sa, ca, za), P(sb, ca, za), P(sb, cb, za), P(sa, cb, za),
         P(sa, ca, zb), P(sb, ca, zb), P(sb, cb, zb), P(sa, cb, zb)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
             (2, 3, 7, 6), (3, 0, 4, 7)]
    # (u, n, z) is right-handed: these loops face outward
    return [{"loop": [c[i] for i in q], "holes": [], "color": color}
            for q in quads]


def door_side(o: dict, wall: dict | None) -> float:
    """The side a door opens to (its leaf, its rail): +1 / −1 across its
    wall — the wall's inside, turned for a door that opens OUT (``out``:
    read from a CAD's swing, 2026-10-09 — a wall holds doors opening
    both ways)."""
    inside = 1.0 if wall is None or float(wall.get("side", 1)) >= 0 \
        else -1.0
    return -inside if o.get("out") else inside


class _Frame:
    """Boxes along a wall (``_box`` in its frame) — and, turned about a
    hinge, in a leaf's own frame (the shopfront's doors)."""

    def __init__(self, p0, u, n) -> None:
        self.p0, self.u, self.n = p0, u, n

    def __call__(self, sa, sb, ca, cb, za, zb, color) -> list:
        return _box(self.p0, self.u, self.n, sa, sb, ca, cb, za, zb, color)

    def turned(self, hinge, back: bool, side: float, th: float):
        p0, u, n = self.p0, self.u, self.n
        h = (p0[0] + u[0] * hinge, p0[1] + u[1] * hinge)
        base = (-u[0], -u[1]) if back else u
        d = (math.cos(th) * base[0] + math.sin(th) * side * n[0],
             math.cos(th) * base[1] + math.sin(th) * side * n[1])
        return _Frame(h, d, (-d[1], d[0]))


def opening_parts(o: dict, seg, z0: float, wall: dict | None = None,
                  top: float | None = None) -> list:
    """The frame (and glass / leaves) of an opening — ``_opening_parts`` —
    its glass made OPAQUE when ``o["glass"] == "opaque"`` (his ask,
    2026-10-14: IngeTrazo has no reflections, and it draws the lines
    behind any see-through glass; an opaque pane reads as glass at a
    distance and hides them). Every see-through face of it: alpha 1."""
    faces = _opening_parts(o, seg, z0, wall, top)
    if o.get("glass") != "opaque":
        return faces
    out = []
    for f in faces:
        c = f.get("color") if isinstance(f, dict) else None
        if c is not None and len(c) > 3 and c[3] < 1.0:
            f = dict(f, color=tuple(c[:3]) + (1.0,))
        out.append(f)
    return out


def _opening_parts(o: dict, seg, z0: float, wall: dict | None = None,
                   top: float | None = None) -> list:
    """The frame (and glass / leaves) of an opening, on the wall's centre
    line: faces with their colours. A void has none. A door: one or two
    leaves, hinged («swing») or SLIDING — one leaf runs on a rail on the
    wall's inside face, two part in the middle within the frame."""
    if o["kind"] == "void":
        return []
    p0, u = seg.p0, seg.u
    n = (-u[1], u[0])
    s0, s1 = o["pos"] - o["w"] / 2, o["pos"] + o["w"] / 2
    zs = z0 + float(o.get("sill", 0.0))
    zt = zs + float(o["h"])
    if o.get("op") == "shop":       # a shopfront / shop window (shopfront.py)
        from . import shopfront
        return [face for p in shopfront.parts(o, _Frame(p0, u, n), s0, s1,
                                              zs, zt, wall, top)
                for face in p]
    hd = FRAME_DEPTH / 2
    f = FRAME
    parts = [_box(p0, u, n, s0, s0 + f, -hd, hd, zs, zt, FRAME_COLOR),
             _box(p0, u, n, s1 - f, s1, -hd, hd, zs, zt, FRAME_COLOR),
             _box(p0, u, n, s0 + f, s1 - f, -hd, hd, zt - f, zt,
                  FRAME_COLOR)]
    if o["kind"] == "window":
        parts.append(_box(p0, u, n, s0 + f, s1 - f, -hd, hd, zs, zs + f,
                          FRAME_COLOR))
        if o.get("op") in WIN_KINDS:      # sliding / casement / awning
            return [face for p in parts for face in p] + _window_leaves(
                o, p0, u, n, s0 + f, s1 - f, zs + f, zt - f, wall)
        parts.append(_box(p0, u, n, s0 + f, s1 - f, -0.005, 0.005,
                          zs + f, zt - f, GLASS_COLOR))
    else:                                            # a door: its leaves
        parts += _door_leaves(o, p0, u, n, s0 + f, s1 - f, zs + 0.01,
                              zt - f, zt, wall)
    return [face for p in parts for face in p]


ALU_COLOR = (0.23, 0.25, 0.27, 1.0)   # a glazed leaf's slim frame
ALU = 0.045                            # m, its face width


def _leaf(p0, u, n, a, b, c0, c1, za, zb, glass: bool,
          color=ALU_COLOR) -> list:
    """One leaf: solid wood, or GLAZED — a slim frame round a pane (dark:
    the curtain wall's look, his ask 2026-10-08; a window's: white)."""
    if not glass:
        return [_box(p0, u, n, a, b, c0, c1, za, zb, LEAF_COLOR)]
    f = min(ALU, (b - a) / 4, (zb - za) / 4)
    cm = (c0 + c1) / 2
    return [_box(p0, u, n, a, a + f, c0, c1, za, zb, color),
            _box(p0, u, n, b - f, b, c0, c1, za, zb, color),
            _box(p0, u, n, a + f, b - f, c0, c1, za, za + f * 2, color),
            _box(p0, u, n, a + f, b - f, c0, c1, zb - f, zb, color),
            _box(p0, u, n, a + f, b - f, cm - 0.004, cm + 0.004,
                 za + f * 2, zb - f, GLASS_COLOR)]


# ---- WINDOWS with leaves (his customers' ask, 2026-10-12 — PLANO_JANELAS.md)
WIN_LEAF = 0.025        # m, a window leaf's depth
WIN_COLOR = (0.93, 0.93, 0.91, 1.0)   # white aluminium (Brazil's usual)
WIN_KINDS = ("sliding", "casement", "awning")
#: a sliding window's leaves, back (B) or front (F) track, left to right —
#: neighbours always in different tracks
WIN_TRACKS = {2: "BF", 3: "FBF", 4: "BFBF"}


def window_leaves(o: dict) -> int:
    """How many leaves a window of its type has: sliding 2–4, casement
    1–2, awning 1 — whatever the record says."""
    op = o.get("op")
    try:
        n = int(o.get("leaves") or 0)
    except (TypeError, ValueError):
        n = 0
    if op == "sliding":
        return min(max(n or 2, 2), 4)
    if op == "casement":
        return 1 if n == 1 else 2
    return 1


def _mbox(M, sa, sb, ca, cb, ta, tb, color) -> list:
    """A box given in ANY frame: ``M(s, c, t)`` → a world point; its faces
    turned outward whatever the frame's handedness (a tilted leaf)."""
    c = [M(sa, ca, ta), M(sb, ca, ta), M(sb, cb, ta), M(sa, cb, ta),
         M(sa, ca, tb), M(sb, ca, tb), M(sb, cb, tb), M(sa, cb, tb)]
    mid = tuple(sum(p[i] for p in c) / 8 for i in range(3))
    out = []
    for q in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
              (2, 3, 7, 6), (3, 0, 4, 7)):
        loop = [c[i] for i in q]
        a, b, d = loop[0], loop[1], loop[2]
        e1 = [b[i] - a[i] for i in range(3)]
        e2 = [d[i] - a[i] for i in range(3)]
        nrm = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2],
               e1[0] * e2[1] - e1[1] * e2[0])
        fc = [sum(p[i] for p in loop) / 4 - mid[i] for i in range(3)]
        if sum(nrm[i] * fc[i] for i in range(3)) < 0:
            loop.reverse()
        out.append({"loop": loop, "holes": [], "color": color})
    return out


def _window_leaves(o, p0, u, n, a, b, za, zb, wall) -> list:
    """A window's leaves as FACES (see ``_window_boxes``)."""
    out = []
    for x in _window_boxes(o, p0, u, n, a, b, za, zb, wall):
        out += x if isinstance(x, list) else [x]
    return out


def _window_boxes(o, p0, u, n, a, b, za, zb, wall) -> list:
    """A window's leaves within its frame's clear opening a..b, za..zb:
    SLIDING (2–4 glazed leaves in two tracks, 5 cm over each other),
    CASEMENT (1–2 hinged on the jambs, In / Out) or AWNING (one, hinged at
    its top, pushed out) — shown as open as «Open» says."""
    op, k = o.get("op"), window_leaves(o)
    opn = opened(o)
    d, g = WIN_LEAF, 0.003
    if op == "sliding":
        lap = 0.05
        lw = (b - a + (k - 1) * lap) / k
        tracks = WIN_TRACKS[k]
        # which leaves slide, and which way: 2 — the front one left, over
        # the back one; 3 — the first one right, over the middle one, up
        # to just short of the third (the same track); 4 — the second one
        # left over the first, the third right under the fourth (never two
        # in one track over each other: coplanar faces flicker)
        moves = {2: {1: -1}, 3: {0: 1}, 4: {1: -1, 2: 1}}[k]
        run = lw - lap if k != 3 else lw - 2 * lap - 0.005
        out = []
        for i in range(k):
            s0 = a + i * (lw - lap)
            s = moves.get(i, 0) * opn * run
            c0, c1 = (g, g + d) if tracks[i] == "F" else (-g - d, -g)
            out += _leaf(p0, u, n, s0 + s, s0 + lw + s, c0, c1, za, zb, True,
                         WIN_COLOR)
        return out
    if op == "casement":
        side = door_side(o, wall)
        th = opn * math.pi / 2
        F = _Frame(p0, u, n)
        if k == 1:
            left = o.get("swing", "left") == "left"
            hinge, back = (a, False) if left else (b, True)
            fr = F.turned(hinge, back, side, th)
            return _leaf(fr.p0, fr.u, fr.n, 0.0, b - a, -d / 2, d / 2, za, zb,
                         True, WIN_COLOR)
        half = (b - a) / 2 - 0.0025
        out = []
        for hinge, back in ((a, False), (b, True)):
            fr = F.turned(hinge, back, side, th)
            out += _leaf(fr.p0, fr.u, fr.n, 0.0, half, -d / 2, d / 2, za, zb,
                         True, WIN_COLOR)
        return out
    # AWNING: hinged at its top, the bottom pushed OUT (up to 35°)
    so = -door_side(dict(o, out=False), wall)
    th = opn * math.radians(35)
    H = zb - za

    def M(s, c, t):
        # t: 0 at the hinge (top) … H at the bottom edge, down the leaf
        cc = c * math.cos(th) + t * math.sin(th) * so
        zz = zb - t * math.cos(th) + c * math.sin(th) * so
        return (p0[0] + u[0] * s + n[0] * cc, p0[1] + u[1] * s + n[1] * cc,
                zz)
    f = min(ALU, (b - a) / 4, H / 4)
    out = []
    for sa, sb, ta, tb in ((a, a + f, 0, H), (b - f, b, 0, H),
                           (a + f, b - f, 0, f), (a + f, b - f, H - 2 * f, H)):
        out += _mbox(M, sa, sb, -d / 2, d / 2, ta, tb, WIN_COLOR)
    out += _mbox(M, a + f, b - f, -0.004, 0.004, f, H - 2 * f, GLASS_COLOR)
    return out


def opened(o: dict) -> float:
    """How open a door is shown: 0 closed … 1 wide open (the library's
    «Open» slider, 2026-10-08)."""
    try:
        return min(max(float(o.get("open", 0.0)), 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


def _swung(p0, u, n, hinge_s, back: bool, inside: float, theta: float,
           length, za, zb) -> list:
    """A hinged leaf turned ``theta`` radians from closed, about its hinge
    on the wall's centre line, towards the inside."""
    h = (p0[0] + u[0] * hinge_s, p0[1] + u[1] * hinge_s)
    base = (-u[0], -u[1]) if back else u
    d = (math.cos(theta) * base[0] + math.sin(theta) * inside * n[0],
         math.cos(theta) * base[1] + math.sin(theta) * inside * n[1])
    return _box(h, d, (-d[1], d[0]), 0.0, length, -LEAF / 2, LEAF / 2, za,
                zb, LEAF_COLOR)


def _room(wall, a, b) -> tuple:
    """How far a sliding leaf may run past ``a`` (back) and ``b`` (on)
    and stay in its wall — 10 cm short of the wall's ends (seen
    2026-10-08: a door near a corner slid its leaf out of the house)."""
    if wall is None:
        return 1e9, 1e9
    L = W.centre(wall).L
    return max(a - 0.10, 0.0), max(L - b - 0.10, 0.0)


def _door_leaves(o, p0, u, n, a, b, za, zb, zt, wall) -> list:
    """A door's leaves between ``a`` and ``b`` along the wall (its clear
    opening), ``za``..``zb`` high — by its type (``op``, ``leaves``,
    ``leaf``: solid | glass) and how open it is shown (``open``)."""
    two = int(o.get("leaves", 1) or 1) == 2
    op = opened(o)
    if o.get("leaf") == "glass":
        return _glass_leaves(o, p0, u, n, a, b, za, zb, zt, wall, two)
    if o.get("op") != "sliding":
        inside = door_side(o, wall)
        th = op * math.pi / 2                       # up to 90°, inwards
        if not two:
            left = o.get("swing", "left") == "left"
            return [_swung(p0, u, n, a if left else b, not left, inside,
                           th, b - a, za, zb)]
        half = (b - a) / 2 - 0.0025                  # a pair, 5 mm apart
        return [_swung(p0, u, n, a, False, inside, th, half, za, zb),
                _swung(p0, u, n, b, True, inside, th, half, za, zb)]
    if two:
        # two leaves parting in the middle, each in its own track within
        # the frame's depth, overlapping 5 cm when closed — open, they run
        # into the wall
        m, lap = (a + b) / 2, 0.025
        g = 0.003
        back, on = _room(wall, a, b)
        sl, sr = min(op * (m - a), back), min(op * (m - a), on)
        return [_box(p0, u, n, a - sl, m + lap - sl, -LEAF - g, -g, za, zb,
                     LEAF_COLOR),
                _box(p0, u, n, m - lap + sr, b + sr, g, LEAF + g, za, zb,
                     LEAF_COLOR)]
    # one leaf on the inside face, on a rail that runs on past the side it
    # slides to — the length of the leaf again
    t = float(wall["t"]) / 2 if wall else FRAME_DEPTH / 2
    side = door_side(o, wall)
    c0, c1 = sorted((side * (t + 0.005), side * (t + 0.005 + LEAF)))
    lap = 0.05                                       # over the jambs
    w = b - a + 2 * lap
    left = o.get("swing", "left") == "left"
    back, on = _room(wall, a - lap, b + lap)
    run = min(w, back if left else on)        # the rail stays on its wall
    s = op * run * (-1.0 if left else 1.0)
    leaf = _box(p0, u, n, a - lap + s, b + lap + s, c0, c1, za, zt + 0.005,
                LEAF_COLOR)
    r0, r1 = (a - lap - run, b + lap) if left else (a - lap, b + lap + run)
    rc0, rc1 = sorted((side * (t + 0.002), side * (t + 0.002 + RAIL)))
    rail = _box(p0, u, n, r0, r1, rc0, rc1, zt + 0.01, zt + 0.01 + RAIL,
                FRAME_COLOR)
    return [leaf, rail]


def _glass_leaves(o, p0, u, n, a, b, za, zb, zt, wall, two) -> list:
    """A GLAZED sliding door: its leaves in two tracks within the frame —
    one fixed pane and one sliding over it, or two sliding apart from the
    middle — the curtain wall's look."""
    g, d = 0.003, LEAF
    op = opened(o)
    m, lap = (a + b) / 2, 0.025
    if two:                                  # open: into the wall
        back, on = _room(wall, a, b)
        sl, sr = min(op * (m - a), back), min(op * (m - a), on)
        return (_leaf(p0, u, n, a - sl, m + lap - sl, -d - g, -g, za, zb,
                      True)
                + _leaf(p0, u, n, m - lap + sr, b + sr, g, d + g, za, zb,
                        True))
    # one: the fixed pane on the side it slides TO, the moving one in the
    # front track, sliding over it
    left = o.get("swing", "left") == "left"
    s = op * (m - a) * (-1.0 if left else 1.0)
    fixed = (a, m + lap) if left else (m - lap, b)
    moving = (m - lap + s, b + s) if left else (a + s, m + lap + s)
    return (_leaf(p0, u, n, *fixed, -d - g, -g, za, zb, True)
            + _leaf(p0, u, n, *moving, g, d + g, za, zb, True))


# ---- roofs ---------------------------------------------------------------------------
#: a roof: {"type": "roof", "kind": "gable" | "hip" | "flat" | "shed" |
#:   "hidden", "corners": its outline (a pitched roof: a rectangle, 4
#:   corners), "slope" (°), "overhang" (the eaves'), "go" (the gable
#:   ends'), "t" (thickness; a hidden roof's: its slab), "ridge": "long" |
#:   "short" (a gable's), "fall": "right" | "left" (the low side of a
#:   shed / a one-slope hidden roof), "slopes": 1 | 2 (a hidden roof's),
#:   "parapet" (m over a flat roof, 0 = none; a hidden roof's when not
#:   "pauto"), "pauto" (a hidden roof's parapet just hides its ridge),
#:   "pt" (the parapet's thickness), "gutter" (a hidden roof's gutter
#:   width)} — it rests on the top of its level's walls.
ROOF_KINDS = ("gable", "hip", "flat", "shed", "hidden")
ROOF_COLOR = (0.66, 0.36, 0.27, 1.0)       # tiles
FLAT_COLOR = (0.72, 0.73, 0.74, 1.0)       # a flat roof (concrete)
GABLE_COLOR = (0.88, 0.86, 0.82, 1.0)      # the gable walls (as walls)
SHEET_COLOR = (0.60, 0.63, 0.66, 1.0)      # a hidden roof's sheets
GUTTER_COLOR = (0.50, 0.53, 0.57, 1.0)     # its gutter (sheet metal)
SHEET_T = 0.05             # a hidden roof's sheets (metal, fibre cement)
GUTTER_DEPTH = 0.15        # its gutter, inside
PARAPET_CLEAR = 0.10       # an «Auto» parapet: this much over the ridge


def rect_frame(corners):
    """(centre, unit along the first side, half-length, unit across,
    half-width) of a 4-corner rectangle outline."""
    c = [tuple(p) for p in corners]
    cx = sum(p[0] for p in c) / 4
    cy = sum(p[1] for p in c) / 4
    e0 = (c[1][0] - c[0][0], c[1][1] - c[0][1])
    e1 = (c[2][0] - c[1][0], c[2][1] - c[1][1])
    a, b = math.hypot(*e0), math.hypot(*e1)
    u0 = (e0[0] / a, e0[1] / a) if a > 1e-9 else (1.0, 0.0)
    return (cx, cy), u0, a / 2, (-u0[1], u0[0]), b / 2


def _sweep(section, x0, x1, P, color) -> list:
    """A section (y, z), counter-clockwise, swept along x from x0 to x1:
    its two caps and its sides, outward."""
    faces = [{"loop": [P(x1, y, z) for y, z in section], "holes": [],
              "color": color},
             {"loop": [P(x0, y, z) for y, z in reversed(section)],
              "holes": [], "color": color}]
    n = len(section)
    for i in range(n):
        (py, pz), (qy, qz) = section[i], section[(i + 1) % n]
        faces.append({"loop": [P(x0, py, pz), P(x0, qy, qz), P(x1, qy, qz),
                               P(x1, py, pz)], "holes": [], "color": color})
    return faces


def _faces(raw, color) -> list:
    return [dict(f, color=color) if isinstance(f, dict) else
            {"loop": f, "holes": [], "color": color} for f in raw]


def roof_faces(r: dict, base: float, wall_t: float = 0.20) -> list:
    """A roof's faces, resting on ``base`` (its level's wall tops): a
    pitched roof's underside passes through the walls' outer top edge."""
    kind = r.get("kind", "flat")
    t = float(r.get("t", 0.20))
    o = float(r.get("overhang", 0.0))
    if kind == "flat":
        from shapely.geometry import Polygon
        from shapely.geometry.polygon import orient
        poly = Polygon(r["corners"])
        if o > 1e-6:
            poly = poly.buffer(o, join_style=2)
        poly = orient(poly, 1.0)
        outer = list(poly.exterior.coords)[:-1]
        faces = _faces(W.solid({"outer": outer, "holes": []}, base,
                               base + t), FLAT_COLOR)
        ph, pt = float(r.get("parapet", 0.0)), float(r.get("pt", 0.15))
        inner = poly.buffer(-pt, join_style=2) if ph > 1e-6 else None
        if inner is not None and inner.geom_type == "Polygon" \
                and inner.area > 0.1:                # the parapet: a ring
            hole = list(orient(inner, 1.0).exterior.coords)[:-1]
            ring = {"outer": outer, "holes": [list(reversed(hole))]}
            faces += _faces(W.solid(ring, base + t, base + t + ph),
                            GABLE_COLOR)
        return faces
    (cx, cy), u0, ha, v0, hb = rect_frame(r["corners"])
    # x along the ridge (the longer side; a gable may be asked the other
    # way), y across, z up — a right-handed frame
    along = ha >= hb
    if kind == "gable" and r.get("ridge", "long") == "short":
        along = not along
    ux, A, B = (u0, ha, hb) if along else (v0, hb, ha)
    if kind in ("shed", "hidden") and r.get("fall") == "left":
        ux = (-ux[0], -ux[1])        # turned half round: the low side swaps
    uy = (-ux[1], ux[0])
    ang = math.radians(float(r.get("slope", 30.0)))
    tan, dz = math.tan(ang), t / math.cos(ang)
    go = float(r.get("go", o))       # the gable ends' overhang

    def P(x, y, z):
        return (cx + ux[0] * x + uy[0] * y, cy + ux[1] * x + uy[1] * y, z)
    if kind == "hidden":
        return _hidden_roof(r, base, A, B, P)
    if kind == "shed":
        return _shed_roof(base, A, B, o, go, tan, dz, wall_t, P)
    if kind == "gable":
        Y, X = B + o, A + go

        def zb(y):
            return base + (B - abs(y)) * tan
        # counter-clockwise in (y, z): along the underside, up the eave,
        # back along the top
        section = [(-Y, zb(-Y)), (0, zb(0)), (Y, zb(Y)), (Y, zb(Y) + dz),
                   (0, zb(0) + dz), (-Y, zb(-Y) + dz)]
        faces = _sweep(section, -X, X, P, ROOF_COLOR)
        # the gable walls: a triangle on each end wall, as thick as it —
        # 2 mm under the roof and 1 mm off the wall's faces (no coplanar
        # faces), its foot 1 mm down into the wall
        d = 0.002
        b2 = B - d / tan
        tri = [(-b2, base - 0.001), (b2, base - 0.001), (0, zb(0) - d)]
        faces += _sweep(tri, A - wall_t + 0.001, A - 0.001, P, GABLE_COLOR)
        faces += _sweep(tri, -A + 0.001, -A + wall_t - 0.001, P,
                        GABLE_COLOR)
        # the EAVE walls up to the roof's underside: it passes over their
        # outer top edge, so a wedge was left open over their thickness —
        # seen in the sections (a customer's report, 2026-10-13)
        faces += _eave_wedge(+1, B, wall_t, base, zb, d, A, P)
        faces += _eave_wedge(-1, B, wall_t, base, zb, d, A, P)
        return faces
    # a hip roof: four planes of one slope, the ridge along x
    Ao, Bo = A + o, B + o
    ze, zr = base - o * tan, base + B * tan
    r1, r2 = (-(A - B), 0.0), ((A - B), 0.0)
    sw, se, ne, nw = (-Ao, -Bo), (Ao, -Bo), (Ao, Bo), (-Ao, Bo)
    eaves = (sw, se, ne, nw)
    faces = []
    for loop in ([sw, se, r2, r1], [se, ne, r2], [ne, nw, r1, r2],
                 [nw, sw, r1]):
        pts = []
        for q in loop:
            if all(math.dist(q, p) > 1e-9 for p in pts):
                pts.append(q)
        zt = [ze if q in eaves else zr for q in pts]
        faces.append({"loop": [P(q[0], q[1], z + dz)
                               for q, z in zip(pts, zt)], "holes": [],
                      "color": ROOF_COLOR})
        faces.append({"loop": [P(q[0], q[1], z) for q, z in
                               reversed(list(zip(pts, zt)))], "holes": [],
                      "color": ROOF_COLOR})
    for i in range(4):                           # the eaves' fascias
        p, q = eaves[i], eaves[(i + 1) % 4]
        faces.append({"loop": [P(p[0], p[1], ze), P(q[0], q[1], ze),
                               P(q[0], q[1], ze + dz), P(p[0], p[1], ze + dz)],
                      "holes": [], "color": ROOF_COLOR})
    return faces


def _eave_wedge(side, B, wall_t, base, zb, d, A, P) -> list:
    """The eave wall's top filled up to the roof's underside (a wedge as
    thick as the wall, ``side`` +1 / −1 across), between the end walls —
    2 mm under the roof, 1 mm off the wall's faces, its foot 1 mm into the
    wall (nothing coplanar)."""
    yo, yi = side * (B - 0.001), side * (B - wall_t + 0.001)
    if zb(yi) - d <= base + 0.002:
        return []                         # a slope too low to leave a gap
    tri = [(yi, base - 0.001), (yo, base - 0.001), (yi, zb(yi) - d)]
    if side < 0:                          # counter-clockwise in (y, z)
        tri = [(yo, base - 0.001), (yi, base - 0.001), (yi, zb(yi) - d)]
    return _sweep(tri, -A + wall_t, A - wall_t, P, GABLE_COLOR)


def _shed_roof(base, A, B, o, go, tan, dz, wall_t, P) -> list:
    """One slope, low on −y: its underside passes through the low wall's
    outer top edge. The end walls rise to it (a trapezoid each) and the
    high wall goes up under it — 2 mm under the roof, 1 mm off the walls'
    faces (nothing coplanar)."""
    Y, X = B + o, A + go

    def zb(y):
        return base + (y + B) * tan
    faces = _sweep([(-Y, zb(-Y)), (Y, zb(Y)), (Y, zb(Y) + dz),
                    (-Y, zb(-Y) + dz)], -X, X, P, ROOF_COLOR)
    d = 0.002
    y0 = -B + 2 * d / tan                  # where the end wall starts
    y1 = B - 0.001
    trap = [(y0, base - 0.001), (y1, base - 0.001), (y1, zb(y1) - d),
            (y0, zb(y0) - d)]
    faces += _sweep(trap, A - wall_t + 0.001, A - 0.001, P, GABLE_COLOR)
    faces += _sweep(trap, -A + 0.001, -A + wall_t - 0.001, P, GABLE_COLOR)
    # the high wall, between the end walls
    h0 = B - wall_t + 0.001
    high = [(h0, base - 0.001), (y1, base - 0.001), (y1, zb(y1) - d),
            (h0, zb(h0) - d)]
    faces += _sweep(high, -A + wall_t, A - wall_t, P, GABLE_COLOR)
    # the low wall up to the roof's underside (see _eave_wedge)
    faces += _eave_wedge(-1, B, wall_t, base, zb, d, A, P)
    return faces


def hidden_parts(r: dict, A: float, B: float) -> dict:
    """A hidden roof's measures, in its frame (x along, y across, from its
    centre; z over the walls' top): the room inside the parapet, the
    gutters' spans, the sheets' low and high edges, the ridge's top and
    the parapet's height."""
    t = float(r.get("t", 0.20))
    pt = float(r.get("pt", 0.15))
    gw = float(r.get("gutter", 0.30))
    two = int(r.get("slopes", 2)) == 2
    tan = math.tan(math.radians(float(r.get("slope", 10.0))))
    ai, bi = A - pt, B - pt                    # inside the parapet
    g0 = t + 0.001                             # the gutters' floor
    gutters = [(-bi + 0.001, -bi + 0.001 + gw)]
    if two:
        gutters.append((bi - 0.001 - gw, bi - 0.001))
    y_low = -bi + 0.001 + gw / 2               # over the gutter's middle
    z_low = g0 + GUTTER_DEPTH + 0.02           # over its lip
    run = (-y_low) if two else (bi - 0.01 - y_low)
    top = z_low + run * tan + SHEET_T / math.cos(math.atan(tan))
    ph = (top + PARAPET_CLEAR if r.get("pauto", True)
          else float(r.get("parapet", 1.0)))
    return {"ai": ai, "bi": bi, "t": t, "g0": g0, "gutters": gutters,
            "y_low": y_low, "z_low": z_low, "two": two, "tan": tan,
            "top": top, "ph": ph}


def hidden_height(r: dict) -> float:
    """A hidden roof's parapet height (over the walls' top), as built."""
    _c, _u, ha, _v, hb = rect_frame(r["corners"])
    A, B = (ha, hb) if ha >= hb else (hb, ha)
    return round(hidden_parts(r, A, B)["ph"], 2)


def _hidden_roof(r: dict, base: float, A: float, B: float, P) -> list:
    """A HIDDEN roof (telhado embutido): the walls go on up as a parapet;
    inside it, a slab, the gutter(s) on it along the low side(s), and one
    or two slopes of sheets falling into them — under the parapet's top
    («Auto»: its ridge + 10 cm). 1 mm between every two parts."""
    from . import walls as W
    m = hidden_parts(r, A, B)
    ai, bi, tan = m["ai"], m["bi"], m["tan"]

    def rect(a, b):
        return [P(x, y, 0)[:2] for x, y in ((-a, -b), (a, -b), (a, b),
                                             (-a, b))]
    faces = _faces(W.solid({"outer": rect(A, B),
                            "holes": [list(reversed(rect(ai, bi)))]},
                           base, base + m["ph"]), GABLE_COLOR)
    faces += _faces(W.solid({"outer": rect(ai - 0.001, bi - 0.001),
                             "holes": []}, base, base + m["t"]), FLAT_COLOR)
    e, gd, z0 = 0.02, GUTTER_DEPTH, base + m["g0"]
    for y0, y1 in m["gutters"]:                # a U, open on top
        u = [(y0, z0), (y1, z0), (y1, z0 + gd), (y1 - e, z0 + gd),
             (y1 - e, z0 + e), (y0 + e, z0 + e), (y0 + e, z0 + gd),
             (y0, z0 + gd)]
        faces += _sweep(u, -ai + 0.001, ai - 0.001, P, GUTTER_COLOR)
    dz = SHEET_T / math.cos(math.atan(tan))
    yl, zl = m["y_low"], base + m["z_low"]
    if m["two"]:
        def zb(y):
            return zl + (-yl - abs(y)) * tan
        sec = [(yl, zb(yl)), (0, zb(0)), (-yl, zb(-yl)), (-yl, zb(-yl) + dz),
               (0, zb(0) + dz), (yl, zb(yl) + dz)]
    else:
        yh = bi - 0.01

        def zb(y):
            return zl + (y - yl) * tan
        sec = [(yl, zb(yl)), (yh, zb(yh)), (yh, zb(yh) + dz),
               (yl, zb(yl) + dz)]
    faces += _sweep(sec, -ai + 0.01, ai - 0.01, P, SHEET_COLOR)
    return faces


def roof_outline(walls: list[dict], union, kind: str):
    """A roof's outline from its level's walls: their outer contour; a
    pitched roof's, the rectangle round it (turned with the building)."""
    loop = inside_walls(walls, union)
    return roof_corners(loop, kind) if loop else loop


def roof_corners(corners, kind: str) -> list:
    """A roof's corners as stored: a flat roof's as drawn; a pitched
    roof's, the rectangle round them (turned with them)."""
    pts = _ccw([tuple(p) for p in corners])
    if kind != "flat":
        from shapely.geometry import Polygon
        rect = Polygon(pts).minimum_rotated_rectangle
        pts = _ccw(list(rect.exterior.coords)[:-1])
    return [[round(p[0], 4), round(p[1], 4)] for p in pts]


# ---- everything, with its faces ----------------------------------------------------
#: a slab stops this far inside the outer face of the outside walls over it
#: (his rule, 2026-10-10: 1 mm still showed lines; 1 cm showed them from
#: afar too — the host draws edges with a depth offset: 3 cm, as railings'
#: BODY_IN)
SLAB_IN = 0.03


def outside_walls(mine: list[dict], plans: dict):
    """(ids, cutter, foot) of a level's OUTSIDE walls — those with a face
    on the outer contour of all its walls together — the 1 cm strip,
    inside that contour, under them: where a slab under them gives way —
    and that contour filled (``foot``; None without walls). Such a
    wall goes down through its level's slab (his ask, 2026-10-10: with the
    slab hidden a gap showed under it; in a real building no slab edge
    shows on the façade). Partitions stay on the slab."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = {}
    for wid, pcs in plans.items():
        for pc in pcs:
            try:
                p = Polygon(pc["outer"], pc.get("holes") or []).buffer(0)
            except Exception:  # noqa: BLE001
                continue
            if not p.is_empty:
                polys.setdefault(wid, []).append(p)
    if not polys:
        return set(), None, None
    union = unary_union([p for ps in polys.values() for p in ps])
    foot = unary_union([Polygon(g.exterior)
                        for g in getattr(union, "geoms", [union])])
    edge = foot.boundary.buffer(0.003)
    t = {w["id"]: float(w["t"]) for w in mine}
    ids = {wid for wid, ps in polys.items()
           if sum(p.exterior.intersection(edge).length for p in ps)
           > max(0.3, 2 * t.get(wid, 0.2))}
    if not ids:
        return ids, None, foot
    strip = foot.difference(foot.buffer(-SLAB_IN, join_style=2))
    under = unary_union([p for wid in ids for p in polys[wid]]).buffer(0.002)
    cut = strip.intersection(under)
    # a CURTAIN wall: the slab runs into it up to 1 cm short of its band
    # (the band hides the slab's edge; stopped at its inner face, a dark
    # slot showed along the floor) — curtain.py
    by_id = {w["id"]: w for w in mine}
    extra = []
    for wid in ids:
        w = by_id.get(wid)
        if not w or not w.get("cw") or w.get("kind", "line") != "line":
            continue
        from shapely import affinity
        from shapely.geometry import Point, box as _bx
        from . import curtain
        seg = W.centre(w)
        nx, ny = -seg.u[1], seg.u[0]
        mx, my = seg.at(0.5)
        t = float(w["t"])
        out = 1.0 if not foot.contains(Point(mx + nx * (t / 2 + 0.02),
                                             my + ny * (t / 2 + 0.02))) \
            else -1.0
        # the band on the OUTER face (2026-10-14): the slab up to 1 cm
        # behind it
        k = t / 2 - (curtain.FACE + curtain.BAND_T + 0.01)
        c0, c1 = (k, t) if out > 0 else (-t, -k)
        g = _bx(-1e4, c0, 1e4, c1)
        g = affinity.rotate(g, math.degrees(math.atan2(seg.u[1], seg.u[0])),
                            origin=(0, 0))
        g = affinity.translate(g, seg.p0[0], seg.p0[1])
        extra.append(unary_union(polys[wid]).buffer(0.002).intersection(g))
    if extra:
        cut = unary_union([cut] + extra)
    return ids, cut.buffer(0), foot


def _depth_under(doc: dict, info: dict, lid: str):
    """p → how far under level ``lid``'s floor the excavation's floor is
    there (None: no pit under it) — for ``wall_drops``."""
    z0 = info[lid]["z0"]

    def depth(p):
        g = ground_under(doc, info, lid, p)
        return None if g is None else z0 - g
    return depth


def wall_drops(mine: list[dict], plans: dict, slabs: list[dict],
               slab_t: float, ground=None) -> dict:
    """{wall id: how far it goes below its floor} — an outside wall with
    no base of its own (0), over a slab of its level: that slab's
    thickness — or down to the excavation's floor when that lies deeper
    (``ground(p)`` → its depth under the floor at p, or None; his screen,
    2026-10-10: a 10 cm gap over the footings, which stand on the pit's
    floor). ``build`` and a bar dragged (``wall_live``) agree."""
    if slab_t <= 0 or not slabs:
        return {}
    from shapely.geometry import Polygon
    ids, _cut, foot = outside_walls(mine, plans)
    out = {}
    try:
        floor = [Polygon(s["corners"]).buffer(0) for s in slabs]
    except Exception:  # noqa: BLE001
        return {}
    # a slab INSIDE the walls' contour: every outside wall goes down through
    # it, standing on the slab or not — a wall dragged off the slab's edge
    # (a grip; the slab stays) lost its drop and «shrank upwards» from its
    # foot (his screen, 2026-10-13)
    floored = foot is not None and any(
        f.intersection(foot).area > 1e-4 for f in floor)
    for w in mine:
        if w["id"] not in ids or abs(float(w.get("base", 0.0))) > 1e-9:
            continue
        if floored:
            out[w["id"]] = slab_t
        for pc in () if floored else plans.get(w["id"], ()):
            try:
                p = Polygon(pc["outer"]).buffer(0)
            except Exception:  # noqa: BLE001
                continue
            if any(f.intersection(p).area > 1e-4 for f in floor):
                out[w["id"]] = slab_t
                break
        if w["id"] in out and ground is not None:
            # read on its centre line, inside its ends (its outer face may
            # stand on the pit's edge)
            c = W.centre(w)
            deep = [ground(c.at(f)) for f in (0.25, 0.5, 0.75)]
            deep = [x for x in deep if x is not None]
            if deep:
                out[w["id"]] = max(slab_t, max(deep))
    return out


def trim_slab(parts: list, cutter) -> list:
    """A slab's pieces with the strip under the outside walls taken out —
    only a slab that stays inside the walls' contour (one running past
    them, a balcony, would be cut in two: left whole)."""
    if cutter is None or cutter.is_empty:
        return parts
    from shapely.geometry import Polygon
    out = []
    for pc in parts:
        try:
            poly = Polygon(pc["outer"], pc.get("holes") or []).buffer(0)
            if not poly.intersects(cutter):
                out.append(pc)
                continue
            rest = poly.difference(cutter)
        except Exception:  # noqa: BLE001
            out.append(pc)
            continue
        for g in getattr(rest, "geoms", [rest]):
            if g.is_empty or g.area < 1e-6:
                continue
            out.append({"outer": _ccw(list(g.exterior.coords)[:-1]),
                        "holes": [list(reversed(_ccw(list(r.coords)[:-1])))
                                  for r in g.interiors]})
    return out


#: a ramp's way through a wall starts this far under its surface: the cut's
#: bottom hides in the ramp's body, never in the plane of its top
RAMP_WALL_DIP = 0.03


def ramp_runs(doc: dict, elevations) -> list:
    """Every ramp's pieces in plan with their top's height: [(outline,
    piece)] — what a wall it crosses gives way to (``ramp_voids``)."""
    from . import ramps as R
    out = []
    for r in doc.get("structure") or []:
        if r.get("type") != "ramp" or why_not(r) is not None:
            continue
        try:
            zs, ze = R.heights(r, doc, elevations)
            L = R.length_of(r, zs, ze)
            if L < 0.1 or abs(zs - ze) < 0.01:
                continue
            for p in R.pieces(r, zs, ze, L):
                out.append((R.piece_corners(p), dict(p, t=float(r["t"]),
                                                     rid=r["id"])))
        except Exception:  # noqa: BLE001 — a ramp that can't say: no cut
            continue
    return out


def ramp_voids(w: dict, pieces, runs: list, z0: float, b: float,
               top: float) -> list:
    """The openings a straight wall takes where a ramp goes THROUGH it (his
    project, 2026-10-10: the street ramp ran into the retaining wall):
    along the wall, the stretch the ramp crosses; from just under the
    ramp's surface up to the wall's top — under the ramp the wall stays
    (it holds the ground). Not stored: they follow the ramp, as the slab's
    hole does. A ramp running under the wall cuts nothing."""
    if not runs or not pieces or w.get("kind", "line") != "line":
        return []
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    try:
        body = unary_union([Polygon(pc["outer"]).buffer(0) for pc in pieces])
    except Exception:  # noqa: BLE001
        return []
    seg = W.centre(w)
    out = []
    for k, (outline, p) in enumerate(runs):
        try:
            cross = body.intersection(Polygon(outline).buffer(0))
        except Exception:  # noqa: BLE001
            continue
        if cross.is_empty or cross.area < 1e-4:
            continue
        pts = [c for g in getattr(cross, "geoms", [cross])
               if hasattr(g, "exterior") for c in g.exterior.coords]
        (cx, cy), (dx, dy) = p["c"], p["d"]

        def z_at(q):
            s = min(max((q[0] - cx) * dx + (q[1] - cy) * dy, 0.0), p["l"])
            return p["z0"] + (p["z1"] - p["z0"]) * s / max(p["l"], 1e-9)
        zs = [z_at(q) for q in pts]
        if max(zs) < b + 0.05 or min(zs) >= top - 0.05:
            continue                     # under the wall, or over it
        bottom = max(min(zs) - min(RAMP_WALL_DIP, p["t"] / 2), b)
        ss = [(q[0] - seg.p0[0]) * seg.u[0] + (q[1] - seg.p0[1]) * seg.u[1]
              for q in pts]
        # 1 cm past the ramp's sides: the jambs never in the plane of its
        # side faces
        s0, s1 = min(ss) - 0.01, max(ss) + 0.01
        if s1 - s0 < 0.07:
            continue
        out.append({"id": f"ramp:{p['rid']}:{k}", "name": "", "kind": "void",
                    "wall": w["id"], "pos": (s0 + s1) / 2, "w": s1 - s0,
                    "sill": bottom - z0, "h": top - bottom + 0.01})
    return out


def wall_parts(w: dict, pieces, openings: list, z0: float, under: float,
               drop: float = 0.0, runs=()):
    """A wall's faces cut by its openings, and each opening's own faces —
    (faces, [(opening, parts)]); None: nothing to build. ``build`` uses it,
    and so does a size bar dragged (the hole follows the door live).
    ``drop``: an outside wall going down through its slab (wall_drops);
    ``runs``: the ramps that may go through it (ramp_runs)."""
    if not pieces:
        return None
    b = z0 + float(w.get("base", 0.0)) - drop
    top = under if w.get("height", "level") == "level" \
        else z0 + float(w["height"])
    if top - b < 0.01:
        return None
    if w.get("cw"):                     # a curtain wall (curtain.py)
        from . import curtain
        return curtain.faces(w, pieces, z0, b, top), []
    ops = [o for o in openings if o["wall"] == w["id"]
           and opening_room(o, w, openings, top - z0) is None]
    ops += ramp_voids(w, pieces, runs, z0, b, top)
    made = []
    if ops:
        seg = W.centre(w)
        faces = [f for pc in pieces
                 for f in wall_with_openings(pc, seg, ops, z0, b, top,
                                             drop > 0)]
        for o in ops:
            parts = opening_parts(o, seg, z0, w, top)
            if parts:
                made.append((o, parts))
    else:
        faces = [f for pc in pieces for f in W.solid(pc, b, top)]
    return faces, made


def wall_bay(doc: dict, wall: dict, pos: float) -> tuple:
    """(s0, s1) along a straight wall: the stretch of its FACE an opening
    at ``pos`` stands in — between the walls that meet or cross it (its
    room's wall, corner face to corner face), not its whole drawn line
    (his test, 2026-10-10: a door «centred» on a wall running past two
    rooms)."""
    seg = W.drawn(wall)
    L = seg.L
    try:
        from shapely.geometry import LineString, Polygon
        from shapely.ops import unary_union
        mine = [x for x in doc["walls"] if x["level"] == wall["level"]]
        plans = W.plan(mine)
        others = [Polygon(pc["outer"]).buffer(0.002)
                  for wid, pcs in plans.items() if wid != wall["id"]
                  for pc in pcs]
        # read 5 mm off its INSIDE face, in the room: the walls meeting it
        # cover that line from their faces (a partition stops on the face;
        # on the axis a mitred corner ends at the axis)
        side = -1.0 if float(wall.get("side", 1)) < 0 else 1.0
        c = W.centre(wall).offset(side * (float(wall["t"]) / 2 + 0.005))
        line = LineString([c.p0, c.p1])
        free = line.difference(unary_union(others)) if others else line
        best = None
        for part in getattr(free, "geoms", [free]):
            if part.is_empty:
                continue
            ss = sorted((p[0] - c.p0[0]) * c.u[0] + (p[1] - c.p0[1]) * c.u[1]
                        for p in part.coords)
            s0, s1 = ss[0], ss[-1]
            if s0 - 1e-6 <= pos <= s1 + 1e-6:
                return (max(s0, 0.0), min(s1, L))
            d = min(abs(pos - s0), abs(pos - s1))
            if best is None or d < best[0]:
                best = (d, (max(s0, 0.0), min(s1, L)))
        if best is not None:
            return best[1]
    except Exception:  # noqa: BLE001 — no faces read: the whole wall
        pass
    return (0.0, L)


def wall_live(doc: dict, elevations, wall_id: str, openings: list):
    """``wall_parts`` of one wall with these openings (a bar dragged)."""
    return walls_live(doc, elevations, [wall_id], openings).get(wall_id)


def walls_live(doc: dict, elevations, wall_ids, openings: list) -> dict:
    """{wall id: ``wall_parts``} of several walls — the joins, the drops
    and the ramps read ONCE per level (a grip dragged: three walls each
    reading them made a step 150 ms, his model, 2026-10-12)."""
    info = levels_info(doc, elevations)
    want = set(wall_ids)
    out = {}
    runs = None
    for lid in {x["level"] for x in doc["walls"] if x["id"] in want}:
        if lid not in info:
            continue
        li = info[lid]
        mine = [x for x in doc["walls"] if x["level"] == lid]
        plans = W.plan(mine)
        slabs = [e for e in doc.get("structure") or []
                 if e.get("type") == "slab" and e["level"] == lid]
        drops = wall_drops(mine, plans, slabs, li["slab"],
                           _depth_under(doc, info, lid))
        if runs is None:
            runs = ramp_runs(doc, elevations)
        for w in mine:
            if w["id"] in want:
                out[w["id"]] = wall_parts(w, plans.get(w["id"]), openings,
                                          li["z0"], li["under"],
                                          drops.get(w["id"], 0.0), runs)
    return out


def elements_live(doc: dict, elevations, ids) -> dict:
    """{id: faces} of these columns / beams / slabs, as ``build`` makes
    them — built from their levels only (a grip dragged). The walls are
    read only when a slab is in it (they trim it); no openings."""
    want = set(ids)
    st = doc.get("structure") or []
    mine = [e for e in st if e["id"] in want]
    lids = {e["level"] for e in mine}
    slabs = any(e["type"] == "slab" for e in mine)
    # every SLAB stays in: the level above's slab sets where a column «to
    # the slab» stops (levels_info) — without it the live column jumped up
    # and down while a face was dragged (his screen, 2026-10-12)
    sub = dict(doc, structure=[e for e in st if e["level"] in lids
                               or e.get("type") in ("ramp", "stair", "slab")],
               walls=[w for w in doc.get("walls") or []
                      if slabs and w["level"] in lids],
               openings=[])
    return {e["id"]: e["faces"] for e in build(sub, elevations)
            if e["id"] in want and e.get("kind") != "wall"}


def build(doc: dict, elevations) -> list[dict]:
    """[{"kind", "id", "name", "level", "faces"}] for every wall and
    structural element of the building, at its true heights."""
    info = levels_info(doc, elevations)
    out = []
    walls = doc.get("walls") or []
    struct = doc.get("structure") or []
    openings = doc.get("openings") or []
    # the ramps open their way through the slabs they cross — the hole is
    # not stored: it follows the ramp, and goes with it (ramps.py)
    ramp_cuts: dict = {}
    for r in struct:
        # «Opening in the slab: None» (``cut`` False — a customer's ask,
        # 2026-10-13): the slab stays whole; a hole is drawn by hand
        if r.get("type") in ("ramp", "stair") and why_not(r) is None \
                and r.get("cut", True):
            from . import ramps as R
            if r["type"] == "ramp":
                zs, ze = R.heights(r, doc, elevations)
                polys = R.footprints(r, zs, ze, R.length_of(r, zs, ze))
            else:
                from . import stairs as ST
                polys = ST.well(r, doc, elevations)
            for lid in R.through_levels(r, doc, elevations):
                ramp_cuts.setdefault(lid, []).extend(polys)
    order = [lv["id"] for lv in doc["levels"]]
    above = {a: b for a, b in zip(order, order[1:])}   # level → next one up
    floors = [v["z0"] for v in info.values()]           # every floor's z
    runs = ramp_runs(doc, elevations)          # what walls give way to
    for lid, li in info.items():
        z0, under = li["z0"], li["under"]
        # walls — cut by their openings
        mine = [w for w in walls if w["level"] == lid]
        plans = W.plan(mine)
        lv_slabs = [e for e in struct if e["level"] == lid
                    and e["type"] == "slab" and why_not(e) is None]
        drops = wall_drops(mine, plans, lv_slabs, li["slab"],
                           _depth_under(doc, info, lid))
        _ids, cutter, foot = outside_walls(mine, plans) if drops \
            else (None, None, None)
        for w in mine:
            made = wall_parts(w, plans.get(w["id"]), openings, z0, under,
                              drops.get(w["id"], 0.0), runs)
            if made is None:
                continue
            faces, ops = made
            for o, parts in ops:
                out.append({"kind": "opening", "id": o["id"],
                            "name": o["name"], "level": lid,
                            "okind": o["kind"], "faces": parts})
            out.append({"kind": "wall", "id": w["id"], "name": w["name"],
                        "level": lid, "faces": faces})
        els = [e for e in struct if e["level"] == lid and why_not(e) is None]
        # columns
        for c in (e for e in els if e["type"] == "column"):
            top = (under if c.get("height", "level") == "level"
                   else z0 + float(c["height"])) - SHRINK
            # a tall column reaching a floor (its top in that slab's top
            # face): 1 cm under it, as a beam — its edges showed through
            for f in floors:
                if f - TOP_GAP < top <= f + 0.002:
                    top = f - TOP_GAP
            sh = FIT_SHRINK if c.get("fit") else SHRINK
            piece = {"outer": _ccw(column_outline(c, sh)), "holes": []}
            bot = z0 + float(c.get("base", 0.0)) + SHRINK   # its base
            if float(c.get("base", 0.0)) <= 0:    # (a raised base: his)
                g = ground_under(doc, info, lid, column_centre(c))
                if g is not None:
                    bot = min(bot, g + SHRINK)  # down to the pit's floor
            if top - bot < 0.05:
                continue
            out.append(dict(_el(c, lid, W.solid(piece, bot, top)),
                            inwall=in_one_wall(c, mine)))
        # beams: joined among themselves like walls
        beams = [e for e in els if e["type"] == "beam"]
        bplans = W.plan([as_wall(e, shrink=FIT_SHRINK if e.get("fit")
                                 else SHRINK) for e in beams])
        # a beam runs IN the slab over it: where that slab is opened (an
        # opening drawn in it, a ramp's or a stair's way through), the beam
        # is cut too (his project, 2026-10-09: the street ramp under the
        # ring of beams — «where the slab opens, the beam opens»)
        cuts = slab_openings(struct, above.get(lid), ramp_cuts)
        for e in beams:
            # its height INCLUDES the slab over it: its top flush with the
            # slab's top, 1 mm down, hidden in it (a customer's catch,
            # 2026-10-06 — it hung whole under the slab: 60 + 20 read 80)
            # 1 cm under the floor above — at 1 mm its top edges showed
            # through the slab's top (his screen, 2026-10-09: the host draws
            # edges with a depth offset; FIT_SHRINK's lesson); its bottom
            # stays where its height puts it
            top = z0 + li["height"] - TOP_GAP
            bot = z0 + li["height"] - float(e["h"]) + SHRINK
            pieces = bplans.get(e["id"], ())
            if cuts:
                pieces = cut_pieces(pieces, cuts)
            out.append(dict(_el(e, lid, [f for pc in pieces
                                         for f in W.solid(pc, bot, top)]),
                            inwall=in_one_wall(e, mine)))
        # slabs
        for s in (e for e in els if e["type"] == "slab"):
            top = z0 + float(s.get("offset", 0.0))
            piece = {"outer": _ccw([tuple(p) for p in s["corners"]]),
                     # openings wound the other way round
                     "holes": [list(reversed(_ccw([tuple(p) for p in h])))
                               for h in s.get("holes") or []]}
            parts = [piece]
            if ramp_cuts.get(lid):
                from . import ramps as R
                cut = R.cut_slab(piece["outer"], piece["holes"],
                                 ramp_cuts[lid])
                if cut is not None:
                    parts = cut
            if cutter is not None:
                # SIDE BY SIDE (his balconies, 2026-10-12): it gives way
                # under the outside walls wherever it ends there — only
                # where it runs on OUT (a balcony) does it go on whole under
                # them (else a slot would cut it in two)
                from shapely.geometry import Polygon
                cut = cutter
                try:
                    spill = Polygon(piece["outer"]).buffer(0).difference(
                        foot.buffer(0.003))
                    if spill.area > 1e-4:
                        reach = max((float(w["t"]) for w in mine),
                                    default=0.2) + 0.10
                        cut = cutter.difference(spill.buffer(reach))
                except Exception:  # noqa: BLE001
                    cut = None
                if cut is not None and not cut.is_empty:
                    parts = trim_slab(parts, cut)
            out.append(_el(s, lid, [f for pc in parts for f in W.solid(
                pc, top - float(s["t"]), top)]))
        # footings: under the slab of their level
        ftop = z0 - li["slab"]
        pads = [e for e in els if e["type"] == "footing"
                and e.get("kind") == "pad"]
        def foot_top(p):
            """In a pit deeper than the floor: its top on the pit's floor
            (which is DRAWN 1 cm lower — terrain.PIT_DRAW_DROP — so the two
            never share a plane)."""
            g = ground_under(doc, info, lid, p)
            return ftop if g is None else min(ftop, g)

        for f in pads:
            piece = {"outer": _ccw(pad_outline(f)), "holes": []}
            t = foot_top((float(f["x"]), float(f["y"])))
            out.append(_el(f, lid, W.solid(piece, t - float(f["d"]), t)))
        strips = [e for e in els if e["type"] == "footing"
                  and e.get("kind") == "strip"]
        splans = W.plan([as_wall(e, shrink=0.0) for e in strips])
        for f in strips:
            # 1 mm under the pads' top: where a strip runs into a pad the
            # two tops would share one plane (and flicker)
            a, b = f["a"], f["b"]
            t = foot_top(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
            out.append(_el(f, lid, [pc_f for pc in splans.get(f["id"], ())
                                    for pc_f in W.solid(
                                        pc, t - float(f["d"]),
                                        t - SHRINK)]))
        # roofs: on the top of the level's walls
        wall_t = max((float(w["t"]) for w in mine), default=0.20)
        for r in (e for e in els if e["type"] == "roof"):
            out.append(_el(r, lid, roof_faces(r, under, wall_t)))
        # ramps: from this level (or the ground) to another (ramps.py)
        rmps = [e for e in els if e["type"] == "ramp"]
        if rmps:
            from . import ramps as R
            for r in rmps:
                out.append(_el(r, lid, R.faces(r, doc, elevations)))
        # stairs: the same, with steps (stairs.py)
        sts = [e for e in els if e["type"] == "stair"]
        if sts:
            from . import stairs as ST
            for r in sts:
                out.append(_el(r, lid, ST.faces(r, doc, elevations)))
    return [e for e in out if e["faces"]]


def beam_magnets(cols: list[dict], tol: float = 0.02) -> list:
    """Where a beam is pulled to, over these columns: each one's centre —
    but where the AXES of two rows of columns (3 or more on one line)
    cross inside a column (a corner), that crossing instead of its centre:
    a ring of beams drawn corner to corner then runs on the side columns'
    axis, whatever the corner column's turn."""
    pts = [tuple(column_centre(c)) for c in cols]

    def axes(i):
        vals = sorted(p[i] for p in pts)
        out, run = [], []
        for v in vals:
            if run and v - run[-1] > tol:
                if len(run) >= 3:
                    out.append(sum(run) / len(run))
                run = []
            run.append(v)
        if len(run) >= 3:
            out.append(sum(run) / len(run))
        return out
    xs, ys = axes(0), axes(1)
    from shapely.geometry import Point, Polygon
    shapes = [Polygon(column_outline(c, 0.0)) for c in cols]
    taken, extra = set(), []
    for x in xs:
        for y in ys:
            q = Point(x, y)
            for k, sh in enumerate(shapes):
                if sh.buffer(1e-4).contains(q):
                    if math.dist(pts[k], (x, y)) > tol:
                        taken.add(k)
                        extra.append((round(x, 4), round(y, 4)))
                    break
    return [p for k, p in enumerate(pts) if k not in taken] + extra


def slab_openings(struct: list[dict], lid, ramp_cuts: dict) -> list:
    """The plan outlines where level ``lid``'s slab is OPEN: the openings
    drawn in its slabs, and the ways ramps / stairs take through it."""
    if lid is None:
        return []
    out = [list(h) for s in struct if s.get("type") == "slab"
           and s.get("level") == lid for h in s.get("holes") or []
           if len(h) >= 3]
    out += [list(p) for p in ramp_cuts.get(lid, ()) if len(p) >= 3]
    return out


def cut_pieces(pieces, cuts) -> list:
    """Plan pieces ({outer, holes}) with the ``cuts`` outlines taken out —
    each piece left a piece of its own (a beam cut in two by an opening)."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    try:
        hole = unary_union([Polygon(c).buffer(0) for c in cuts])
    except Exception:  # noqa: BLE001 — a bad outline cuts nothing
        return list(pieces)
    out = []
    for pc in pieces:
        try:
            poly = Polygon(pc["outer"], pc.get("holes") or []).buffer(0)
            if not poly.intersects(hole):
                out.append(pc)
                continue
            rest = poly.difference(hole)
        except Exception:  # noqa: BLE001
            out.append(pc)
            continue
        for g in getattr(rest, "geoms", [rest]):
            if g.is_empty or g.area < 1e-6:
                continue
            out.append({"outer": _ccw(list(g.exterior.coords)[:-1]),
                        "holes": [list(reversed(_ccw(list(r.coords)[:-1])))
                                  for r in g.interiors]})
    return out


def hole_place(slabs: list[dict], hole) -> tuple:
    """(slab, reason): the slab an opening drawn at ``hole`` goes
    through — the one that holds it all, clear of its other openings."""
    from shapely.geometry import Polygon
    h = Polygon(hole)
    if not h.is_valid or h.area < 0.01:
        return None, "Too small for an opening"
    for s in slabs:
        outer = Polygon(s["corners"])
        if not outer.is_valid:
            outer = outer.buffer(0)
        if not outer.buffer(1e-6).contains(h):
            continue
        if any(Polygon(o).intersects(h) for o in s.get("holes") or []):
            return None, "It runs into another opening of that slab"
        return s, None
    return None, "Draw the opening inside a slab of this level"


def in_one_wall(e: dict, walls: list[dict]) -> bool:
    """A fitted column, or a beam lying wholly within one wall: it is
    INSIDE the wall — hidden while the walls are shown (its lines showed
    through them in a raking view; nothing of it is to be seen anyway)."""
    if not e.get("fit"):
        return False
    if e["type"] == "column":
        return True                     # fitted = inside by construction
    for w in walls:
        if W.why_not(w) is not None or w.get("kind", "line") != "line":
            continue
        s = W.centre(w)
        if all((-1e-6 <= f <= 1 + 1e-6) and
               abs(off) <= float(w["t"]) / 2 + FIT_TOL
               for f, off in (s.project(e["a"]), s.project(e["b"]))):
            return True
    return False


def _el(e: dict, lid: str, faces) -> dict:
    return {"kind": e["type"], "id": e["id"], "name": e["name"],
            "level": lid, "faces": faces}
