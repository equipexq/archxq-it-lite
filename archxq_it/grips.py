"""On-screen GRIPS (PLANO_PEGAS.md — his OK 2026-10-13, «maravilhoso»).

With the host's Select tool and ONE ArchXQ element selected, small square
grips stand on it (blue; orange under the mouse). Drag one: the element
changes LIVE (as the library's bars — no undo step); let go: stored, one
Ctrl+Z. While it moves: the value shows by the grip, steps of 5 cm
(Shift = 1 cm), a typed number + Enter = that exact value, Esc = put back.
A click that is not on a grip is the host's, as ever.

A press and release on the same spot (no drag) CARRIES the grip, the
SketchUp way: it follows the mouse, a click puts it down — and typing a
number is easy then.

Phase 1, part 1: straight WALLS (2 ends — the corner's walls follow — and
an arrow across: the joined walls stretch, wallmove) and DOORS / WINDOWS
(sides = width, top = height, bottom = sill, centre = along the wall).

Each grip moves along its OWN axis (the wall's line, the vertical, the
wall's normal): the mouse is read on that axis's image on the screen — a
1-D projective map, solved from three points (exact in perspective too).
An axis seen end-on (the vertical in the plan) has no grip.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from PySide6.QtCore import QEvent, QObject, Qt

from . import walls as W

HALF_PX = 4.5           # a grip's half side (px)
HOT_HALF_PX = 6.0
HIT_PX = 9              # a press this close to a grip takes it
MIN_PX_PER_M = 1.0      # under this on screen the axis can't be read
DRAG_PX = 4             # moved this far with the button down = a drag
STEP, FINE = 0.05, 0.01
TOL = W.JOIN_TOL        # ends this close = one corner (m), as the engine
MAGNET_PX = 12          # an end this near another wall / end sticks to it
PLANE_TOL = 0.05        # m: walls' centres this far apart = one plane
DOT = "#22a6c8"         # walledit's colours
HOT = "#e8742c"
OUTLINE = "#ffffff"
GUIDE = "#c2369b"       # a temporary alignment guide (SketchUp's magenta)


@dataclass
class Grip:
    key: str                    # a | b | across | left | right | top | bottom | pos
    p: tuple                    # its world point
    axis: tuple                 # the unit world direction it moves along
    base: float                 # the value it starts from
    mode: str = "size"          # size: an absolute value · move: a distance
    arrow: bool = False         # drawn as an arrow (a move across)
    tip: str = ""
    extra: dict = field(default_factory=dict)


# ---- the grips of an element ------------------------------------------------------------
def _unit2(v):
    L = math.hypot(v[0], v[1])
    return (v[0] / L, v[1] / L) if L > 1e-12 else (0.0, 0.0)


def straight(w: dict) -> bool:
    return w.get("kind", "line") == "line" and "a" in w and "b" in w


def wall_grips(w: dict, z0: float, top: float) -> list[Grip]:
    """A straight wall's: its two ends (the length) and an arrow across,
    on its top (seen in 3D, in the plan and in the elevations)."""
    if not straight(w):
        return []
    a, b = tuple(w["a"]), tuple(w["b"])
    L = math.dist(a, b)
    if L < 1e-6:
        return []
    u = _unit2((b[0] - a[0], b[1] - a[1]))
    n = (-u[1], u[0])
    z = z0 + top
    m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    return [Grip("a", (a[0], a[1], z), (-u[0], -u[1], 0.0), L,
                 tip="Its length — the corner's walls follow"),
            Grip("b", (b[0], b[1], z), (u[0], u[1], 0.0), L,
                 tip="Its length — the corner's walls follow"),
            Grip("across", (m[0], m[1], z), (n[0], n[1], 0.0), 0.0, "move",
                 True, "Move it across — the walls joined to it stretch")]


def opening_grips(o: dict, w: dict, z0: float) -> list[Grip]:
    """A door's / window's: its sides (width), its top (height), its
    bottom (sill — not a door's) and its centre (along the wall)."""
    if not straight(w):
        return []
    seg = W.centre(w)
    u = seg.u
    pos, ow = float(o["pos"]), float(o["w"])
    sill, h = float(o.get("sill", 0.0)), float(o["h"])

    def at(s, z):
        return (seg.p0[0] + u[0] * s, seg.p0[1] + u[1] * s, z)
    zm = z0 + sill + h / 2
    out = [Grip("left", at(pos - ow / 2, zm), (-u[0], -u[1], 0.0), ow,
                tip="Its width"),
           Grip("right", at(pos + ow / 2, zm), (u[0], u[1], 0.0), ow,
                tip="Its width"),
           Grip("top", at(pos, z0 + sill + h), (0.0, 0.0, 1.0), h,
                tip="Its height")]
    if o["kind"] != "door":
        out.append(Grip("bottom", at(pos, z0 + sill), (0.0, 0.0, 1.0), sill,
                        tip="Its sill — the top stays"))
    out.append(Grip("pos", at(pos, zm), (u[0], u[1], 0.0), 0.0, "move",
                    tip="Slide it along its wall"))
    return out


def _col_axes(c: dict):
    a = math.radians(float(c.get("angle", 0.0)))
    return (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))


def column_grips(c: dict, z: float, z0: float | None = None,
                 bot: float | None = None) -> list[Grip]:
    """A column's grips — at HALF its height (as a door's: his test,
    2026-10-12 — on its top they were lost among each other): its centre
    (a circle: MOVE it; ↑ = up / down), a grip on each face (its width /
    depth — the face opposite stays); its top (its height) and its foot
    (its base). ``z`` = its top, ``z0`` = its level's floor, ``bot`` =
    its foot."""
    from . import structure as S
    cx, cy = S.column_centre(c)
    u, v = _col_axes(c)
    w, d = float(c["w"]), float(c["d"])
    z0 = z if z0 is None else z0
    bot = z0 + float(c.get("base", 0.0)) if bot is None else bot
    zm = (z + bot) / 2 if z > bot else z
    lv = {"z0": z0, "top": z}
    # its centre: MOVE it, free on the level's plane, in its own axes (his
    # test, 2026-10-12: «it can't be dragged»); ↑ while moving: up / down
    move = Grip("m", (cx, cy, zm), (u[0], u[1], 0.0), 0.0, "point",
                tip="Move it — it lines up with the other columns · ↑ = "
                "up / down", extra=dict(lv, e2=(v[0], v[1], 0.0),
                                       shape="circle", z=True))
    ends = [Grip("top", (cx, cy, z), (0.0, 0.0, 1.0), z - z0,
                 tip="Its height — the foot stays", extra=lv),
            Grip("base", (cx, cy, bot), (0.0, 0.0, 1.0), bot - z0,
                 tip="Its foot — the top stays", extra=lv)]
    if c.get("shape") == "round":
        return [move, Grip("r", (cx + u[0] * w / 2, cy + u[1] * w / 2, zm),
                           (u[0], u[1], 0.0), w, tip="Its diameter")] + ends
    out = [move] + ends
    z = zm
    for key, ax, size in (("w+", u, w), ("d+", v, d)):
        for s in (1, -1):
            k = key if s == 1 else key[0] + "-"
            out.append(Grip(k, (cx + ax[0] * s * size / 2,
                                cy + ax[1] * s * size / 2, z),
                            (ax[0] * s, ax[1] * s, 0.0), size,
                            tip="Its " + ("width" if key[0] == "w"
                                          else "depth")
                            + " — the face opposite stays"))
    return out


def beam_grips(b: dict, z: float) -> list[Grip]:
    """A straight beam's: its two ends — FREE on its plane (onto another
    beam's end, a column's centre or corner, off its own line: his test,
    2026-10-12), an arrow across, and under its middle its DEPTH (its top
    stays, in the slab)."""
    if b.get("m") or "a" not in b:
        return []
    a, e = tuple(b["a"]), tuple(b["b"])
    L = math.dist(a, e)
    if L < 1e-6:
        return []
    u = _unit2((e[0] - a[0], e[1] - a[1]))
    n = (-u[1], u[0])
    h = float(b["h"])
    m = ((a[0] + e[0]) / 2, (a[1] + e[1]) / 2)
    return [Grip("a", (a[0], a[1], z), (1.0, 0.0, 0.0), 0.0, "point",
                 tip="Its end — drag it anywhere"),
            Grip("b", (e[0], e[1], z), (1.0, 0.0, 0.0), 0.0, "point",
                 tip="Its end — drag it anywhere"),
            Grip("across", (m[0], m[1], z), (n[0], n[1], 0.0), 0.0, "move",
                 True, "Move it across — onto the columns' centres or faces"),
            Grip("h", (m[0], m[1], z - h), (0.0, 0.0, -1.0), h,
                 tip="Its depth — its top stays in the slab")]


def _outward(pts, k):
    """The outward normal of a polygon's side k (whatever its winding)."""
    n = len(pts)
    a, b = pts[k], pts[(k + 1) % n]
    L = math.dist(a, b) or 1.0
    area = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(pts, pts[1:] + pts[:1]))
    s = 1.0 if area >= 0 else -1.0          # counter-clockwise: the right
    return ((b[1] - a[1]) / L * s, -(b[0] - a[0]) / L * s)


def slab_grips(s: dict, z: float) -> list[Grip]:
    """A drawn slab's: each corner (moves freely on its plane) and each
    side's middle (the side moves parallel to itself)."""
    pts = [tuple(p) for p in s["corners"]]
    out = []
    for i, p in enumerate(pts):
        out.append(Grip(f"v{i}", (p[0], p[1], z), (1.0, 0.0, 0.0), 0.0,
                        "point", tip="Its corner — drag it anywhere"))
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        n = _outward(pts, i)
        out.append(Grip(f"s{i}", ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, z),
                        (n[0], n[1], 0.0), 0.0, "move", True,
                        "Move this side, parallel"))
    # up / down (its «Top») over its middle, its thickness under it
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    t = float(s["t"])
    out.append(Grip("z", (cx, cy, z), (0.0, 0.0, 1.0), 0.0, "move", True,
                    "Up / down — onto the floors and the other slabs"))
    out.append(Grip("t", (cx, cy, z - t), (0.0, 0.0, -1.0), t,
                    tip="Its thickness — its top stays"))
    return out


#: Phase 2 (2026-10-13, his go): stairs, ramps, the roof's eaves
#: «Insert at» → where the click sits across the flight (ramps.axes)
_ANCHOR_K = {"left": 0.5, "right": -0.5}


def flight_grips(r: dict, ps: list, zs: float, ze: float) -> list[Grip]:
    """A ramp's / stair's: its start (MOVE it, free on its plane), its
    WIDTH (on the side away from the click — that side stays), the
    LANDING's length (L / U) and a straight ramp's LENGTH (its end).
    ``ps``: its plan pieces (ramps.pieces / stairs.layout)."""
    from . import ramps as R
    if not ps:
        return []
    (sx, sy), u, n = R.axes(r)
    w = float(r["w"])
    runs = [pc for pc in ps if pc.get("run", True)]
    a = runs[0]
    # the width's grip on its OUTER face (+ = its right): an L / U's away
    # from its turn (on the turn's side it stood between the flights —
    # his screen, 2026-10-13); a straight one's away from the click
    if r.get("shape") in ("L", "U"):
        side = 1.0 if r.get("turn") == "left" else -1.0
    else:
        side = -1.0 if r.get("anchor") == "right" else 1.0
    l1 = float(a["l"])
    zm = (float(a["z0"]) + float(a["z1"])) / 2
    out = [Grip("m", (sx, sy, zs), (u[0], u[1], 0.0), 0.0, "point",
                tip="Move it — drag it anywhere",
                extra={"e2": (n[0], n[1], 0.0), "shape": "circle"}),
           Grip("w", (sx + u[0] * l1 / 2 + n[0] * side * w / 2,
                      sy + u[1] * l1 / 2 + n[1] * side * w / 2, zm),
                (n[0] * side, n[1] * side, 0.0), w,
                tip="Its width — the other side stays",
                extra={"side": side})]
    # the OTHER outer face (his test, 2026-10-13: a U's right face had no
    # grip, so it could not go against its wall): a straight one's other
    # side; a U's second flight's outer side — its WHOLE width
    shape = r.get("shape", "straight")
    if shape not in ("L", "U"):
        out.append(Grip("w2", (sx + u[0] * l1 / 2 - n[0] * side * w / 2,
                               sy + u[1] * l1 / 2 - n[1] * side * w / 2, zm),
                        (-n[0] * side, -n[1] * side, 0.0), w,
                        tip="Its width — the other side stays",
                        extra={"side": -side}))
    elif shape == "U" and len(runs) > 1:
        b = runs[1]
        sg = -side                         # the way the turn goes (n)
        gap = float(r.get("gap", 0.0) or 0.0)
        # a U's two outer faces BOTH measure its whole width, each keeping
        # the OTHER face where it is (his test, 2026-10-13: the first
        # flight's grip grew it both ways — its width is both flights')
        g0 = out[1]
        out[1] = Grip("wl", g0.p, g0.axis, 2 * w + gap,
                      tip="Its whole width (both flights) — the other side "
                      "stays", extra={"sg": sg})
        (bx, by), (dx, dy) = b["c"], b["d"]
        lb = float(b["l"])
        out.append(Grip("wt", (bx + dx * lb / 2 + n[0] * sg * w / 2,
                               by + dy * lb / 2 + n[1] * sg * w / 2,
                               (float(b["z0"]) + float(b["z1"])) / 2),
                        (n[0] * sg, n[1] * sg, 0.0), 2 * w + gap,
                        tip="Its whole width (both flights) — the other "
                        "side stays", extra={"sg": sg}))
    land = next((pc for pc in ps if not pc.get("run", True)), None)
    if land is not None and r.get("shape") in ("L", "U"):
        (cx, cy), (dx, dy) = land["c"], land["d"]
        ll = float(land["l"])
        out.append(Grip("land", (cx + dx * ll, cy + dy * ll,
                                 float(land["z0"])), (dx, dy, 0.0),
                        float(r.get("landing", ll)),
                        tip="The landing's length"))
    if r["type"] == "ramp" and r.get("shape", "straight") == "straight":
        L = l1
        out.append(Grip("len", (sx + u[0] * L, sy + u[1] * L, ze),
                        (u[0], u[1], 0.0), L,
                        tip="Its length — the slope follows"))
    return out


def _wall_faces(doc: dict, lids=None) -> list:
    """(a point, the way, length) of each face of the straight walls of
    these levels (None: of EVERY level — a line seen over another level,
    its ghost, pulls too: his test, 2026-10-13) and each side of the
    slabs' outlines (a stair's well in the slab above)."""
    out = []
    for s in doc.get("structure") or []:
        if s.get("type") != "slab" or (lids is not None
                                       and s["level"] not in lids):
            continue
        pts = [tuple(p) for p in s.get("corners") or []]
        for i, p in enumerate(pts):
            q = pts[(i + 1) % len(pts)]
            L = math.dist(p, q)
            if L > 1e-6:
                out.append((p, ((q[0] - p[0]) / L, (q[1] - p[1]) / L), L))
    for w in doc.get("walls") or []:
        if lids is not None and w["level"] not in lids \
                or not straight(w):
            continue
        cs = W.centre(w)
        wu = cs.u
        nn = (-wu[1], wu[0])
        t = float(w["t"])
        for f in (-1, 1):
            out.append(((cs.p0[0] + nn[0] * f * t / 2,
                         cs.p0[1] + nn[1] * f * t / 2), wu, cs.L))
    return out


def _flight_faces(doc: dict, skip: str) -> list:
    """(a point, the way, length) of each side of the OTHER stairs' /
    ramps' plan pieces, on every level — a flight lined up with the one
    under / over it (his test, 2026-10-13: only the 5 cm steps pulled)."""
    from . import model
    from . import ramps as R
    out = []
    for e in doc.get("structure") or []:
        if e.get("type") not in ("stair", "ramp") or e["id"] == skip:
            continue
        try:
            zs, ze = R.heights(e, doc, model.elevations)
            if e["type"] == "stair":
                from . import stairs as ST
                ps = ST.layout(e, zs, ze)
            else:
                ps = R.pieces(e, zs, ze, R.length_of(e, zs, ze))
        except Exception:  # noqa: BLE001 — a flight not readable: skipped
            continue
        for pc in ps:
            pts = R.piece_corners(pc)
            for i, p in enumerate(pts):
                q = pts[(i + 1) % len(pts)]
                L = math.dist(p, q)
                if L > 1e-6:
                    out.append((p, ((q[0] - p[0]) / L, (q[1] - p[1]) / L),
                                L))
    return out


def flight_magnets(doc: dict, r: dict, key: str, grip, ps: list) -> list:
    """A ramp's / stair's grips onto the WALLS' FACES (his test,
    2026-10-13: its outer face against a wall's inner face, impossible by
    5 cm steps) — of its own level and the one it reaches:
      - «w»: its outer face onto a parallel face beside its first flight
        → (width, anchor);
      - «m»: moved, each way on its own: its sides onto the faces parallel
        to it, its start onto the faces across it → ("x" | "y", d, anchor).
    ``ps``: its plan pieces."""
    from . import ramps as R
    faces = _wall_faces(doc)              # every level's walls and slabs
    faces += _flight_faces(doc, r["id"])  # …and the other stairs / ramps
    (sx, sy), u, n = R.axes(r)
    z = grip.p[2]
    out = []

    def para(wu, ax):
        return abs(wu[0] * ax[1] - wu[1] * ax[0]) <= 0.02

    def anchor(p0, wu, L, P):
        t = min(max((P[0] - p0[0]) * wu[0] + (P[1] - p0[1]) * wu[1], 0.0), L)
        return (p0[0] + wu[0] * t, p0[1] + wu[1] * t, z)
    if key in ("w", "w2", "wt", "wl"):
        a = (grip.axis[0], grip.axis[1])
        P = grip.p
        for p0, wu, L in faces:
            if not para(wu, u):
                continue
            d = (p0[0] - P[0]) * a[0] + (p0[1] - P[1]) * a[1]
            if abs(d) > 3.0:
                continue
            # beside the flight the grip is on (its middle along the wall)
            tp = (P[0] - p0[0]) * wu[0] + (P[1] - p0[1]) * wu[1]
            if not -1.0 <= tp <= L + 1.0:
                continue
            v = grip.base + d
            if v >= 0.5:
                out.append((round(v, 4), anchor(p0, wu, L, P)))
        return out
    if key != "m":
        return out
    # its outline in its own axes (u along, n across) — every piece
    from .ramps import piece_corners
    us, ns = [], []
    for pc in ps:
        for q in piece_corners(pc):
            us.append((q[0] - sx) * u[0] + (q[1] - sy) * u[1])
            ns.append((q[0] - sx) * n[0] + (q[1] - sy) * n[1])
    if not us:
        return out
    # only the faces BESIDE it (their stretch overlapping its own, along
    # them) and near: every level's walls, any face within 3 m, made it
    # jump from one to another, its guide drawn askew to a wall far off
    # (his screen, 2026-10-13)
    u0, u1, n0, n1 = min(us), max(us), min(ns), max(ns)
    cu, cn = (u0 + u1) / 2, (n0 + n1) / 2

    def world(a_u, a_n):
        return (sx + u[0] * a_u + n[0] * a_n, sy + u[1] * a_u + n[1] * a_n)
    for p0, wu, L in faces:
        fu = (p0[0] - sx) * u[0] + (p0[1] - sy) * u[1]
        fn = (p0[0] - sx) * n[0] + (p0[1] - sy) * n[1]
        if para(wu, u):                      # a side onto it
            # the face's stretch along u, against its own
            s = wu[0] * u[0] + wu[1] * u[1]
            a0, a1 = sorted((fu, fu + s * L))
            if a1 < u0 - 0.3 or a0 > u1 + 0.3:
                continue
            # the guide square to the face, from the grip (as a column's)
            A = anchor(p0, wu, L, world(0.0, fn))
            for k in (fn - n1, fn - n0):
                if abs(k) <= 1.5:
                    out.append(("y", round(k, 4), A))
        elif para(wu, n):                    # its start / its end onto it
            s = wu[0] * n[0] + wu[1] * n[1]
            a0, a1 = sorted((fn, fn + s * L))
            if a1 < n0 - 0.3 or a0 > n1 + 0.3:
                continue
            A = anchor(p0, wu, L, world(fu, 0.0))
            for k in (fu - u0, fu - u1):
                if abs(k) <= 1.5:
                    out.append(("x", round(k, 4), A))
    return out


def roof_grips(r: dict, z: float) -> list[Grip]:
    """A roof's EAVES: a grip outside each side, at its overhang — the
    eaves' overhang (all round), a gable roof's gable ends their own. Not
    a hidden roof (behind its parapet)."""
    kind = r.get("kind")
    if kind == "hidden" or not r.get("corners"):
        return []
    pts = [tuple(p) for p in r["corners"]]
    gable = set()
    if kind == "gable" and len(pts) == 4:
        lens = [math.dist(pts[i], pts[(i + 1) % 4]) for i in range(4)]
        short = sorted(range(4), key=lambda i: lens[i])[:2]
        long_ = [i for i in range(4) if i not in short]
        # the ridge along the long sides: the gable ends are the short ones
        gable = set(short if r.get("ridge", "long") == "long" else long_)
    ov = float(r.get("overhang", 0.5))
    go = float(r.get("go", ov))
    out = []
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        nn = _outward(pts, i)
        g = i in gable
        d = go if g else ov
        m = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        out.append(Grip(f"e{i}", (m[0] + nn[0] * d, m[1] + nn[1] * d, z),
                        (nn[0], nn[1], 0.0), d,
                        tip="The gable end's overhang" if g
                        else "The eaves' overhang — all round",
                        extra={"go": g}))
    return out


def flight_changed(doc: dict, e: dict, key: str, v, grip=None):
    """(the document with a ramp's / stair's grip at ``v``, why not)."""
    from . import ramps as R
    r = dict(e)
    (sx, sy), u, n = R.axes(e)
    if key == "m":                        # moved, in its own axes
        r.update(x=round(float(e["x"]) + u[0] * v[0] + n[0] * v[1], 4),
                 y=round(float(e["y"]) + u[1] * v[0] + n[1] * v[1], 4))
    elif key in ("wt", "wl"):             # a U's whole width: 2 w + gap
        w0 = float(e["w"])
        gap = float(e.get("gap", 0.0) or 0.0)
        wn = (v - gap) / 2
        if wn < (0.6 if e["type"] == "stair" else 0.5):
            return doc, "Too narrow"
        sg = (getattr(grip, "extra", None) or {}).get("sg", 1.0)
        # «wt» (the second flight's face): the first flight's outer face
        # stays; «wl» (the first's): the SECOND's outer face stays
        f = 0.5 if key == "wt" else -1.5
        mx = sx + n[0] * sg * f * (wn - w0)
        my = sy + n[1] * sg * f * (wn - w0)
        k = _ANCHOR_K.get(e.get("anchor"), 0.0) * wn
        r.update(w=round(wn, 4), x=round(mx - n[0] * k, 4),
                 y=round(my - n[1] * k, 4))
    elif key in ("w", "w2"):              # its width: the other side stays
        w0 = float(e["w"])
        if v < (0.6 if e["type"] == "stair" else 0.5):
            return doc, "Too narrow"
        side = (getattr(grip, "extra", None) or {}).get("side", 1.0)
        mx = sx + n[0] * side * (v - w0) / 2      # its first edge's middle
        my = sy + n[1] * side * (v - w0) / 2
        k = _ANCHOR_K.get(e.get("anchor"), 0.0) * v
        r.update(w=round(v, 4), x=round(mx - n[0] * k, 4),
                 y=round(my - n[1] * k, 4))
    elif key == "land":
        if v < 0.5:
            return doc, "Too short a landing"
        r["landing"] = round(v, 4)
    elif key == "len":                    # a ramp's length: the slope follows
        if v < 0.5:
            return doc, "Too short"
        r.update(L=round(v, 4), fix="length")
    else:
        return doc, None
    why = R.why_not(r) if e["type"] == "ramp" else None
    if e["type"] == "stair":
        from . import stairs as ST
        why = ST.why_not(r)
    if why:
        return doc, why
    return _struct_set(doc, r), None


# ---- what a grip's value makes of the document ----------------------------------------
def _struct_set(doc: dict, rec: dict) -> dict:
    return dict(doc, structure=[rec if e["id"] == rec["id"] else e
                                for e in doc.get("structure") or []])


def element_changed(doc: dict, eid: str, key: str, v, grip=None):
    """(the document with a column's / beam's / slab's grip at ``v``, why
    not or None). ``grip.extra`` has the column's level floor / top."""
    from . import structure as S
    e = next((x for x in doc.get("structure") or [] if x["id"] == eid), None)
    if e is None:
        return doc, "Gone"
    r = dict(e)
    t = e["type"]
    lv = getattr(grip, "extra", None) or {}
    if t in ("stair", "ramp"):
        return flight_changed(doc, e, key, v, grip)
    if t == "roof" and key.startswith("e"):   # an eave's overhang
        if not 0.0 <= v <= 3.0:
            return doc, "An overhang goes from 0 to 3 m"
        r["go" if lv.get("go") else "overhang"] = round(v, 4)
        if not lv.get("go") and "go" not in e:
            r["go"] = float(e.get("overhang", 0.5))   # the gable ends stay
        return _struct_set(doc, r), None
    if t == "column":
        cx, cy = S.column_centre(e)
        u, vv = _col_axes(e)
        # its height from the floor now (a «level» height: as it stands)
        h_now = float(e["height"]) if e.get("height", "level") != "level" \
            else lv.get("top", 0.0) - lv.get("z0", 0.0)
        base = float(e.get("base", 0.0))
        if key == "m":                    # moved, in its own axes
            r.update(x=round(cx + u[0] * v[0] + vv[0] * v[1], 4),
                     y=round(cy + u[1] * v[0] + vv[1] * v[1], 4),
                     anchor="centre")
            dz = v[2] if len(v) > 2 else 0.0
            if dz:                        # up / down, whole (↑)
                r.update(base=round(base + dz, 4),
                         height=round(h_now + dz, 4))
        elif key == "top":                # its height (the foot stays)
            if v - base < 0.2:
                return doc, "Too short for a column"
            r["height"] = round(v, 4)
        elif key == "base":               # its foot (the top stays)
            if h_now - v < 0.2:
                return doc, "Too short for a column"
            r["base"] = round(v, 4)
            if e.get("height", "level") != "level":
                r["height"] = round(h_now, 4)
        elif key == "r":
            r.update(w=round(v, 4), d=round(v, 4))
        else:
            dim = "w" if key[0] == "w" else "d"
            ax = u if dim == "w" else vv
            s = 1.0 if key[1] == "+" else -1.0
            grow = (v - float(e[dim])) / 2 * s
            cx, cy = cx + ax[0] * grow, cy + ax[1] * grow
            # stored by its centre from now on: the side opposite stays
            r.update({dim: round(v, 4), "x": round(cx, 4), "y": round(cy, 4),
                      "anchor": "centre"})
    elif t == "beam" and key == "across":
        u = _unit2((e["b"][0] - e["a"][0], e["b"][1] - e["a"][1]))
        n = (-u[1], u[0])
        for k in ("a", "b"):
            r[k] = [round(e[k][0] + n[0] * v, 4), round(e[k][1] + n[1] * v, 4)]
    elif t == "beam" and key == "h":
        r["h"] = round(v, 4)
    elif t == "beam":                     # an end, anywhere on its plane
        r[key] = [round(e[key][0] + v[0], 4), round(e[key][1] + v[1], 4)]
    elif t == "slab" and key == "z":      # up / down (its «Top»)
        r["offset"] = round(float(e.get("offset", 0.0)) + v, 4)
    elif t == "slab" and key == "t":      # its thickness
        if v < 0.02:
            return doc, "Too thin for a slab"
        r["t"] = round(v, 4)
    elif t == "slab":
        pts = [list(p) for p in e["corners"]]
        if key.startswith("v"):
            i = int(key[1:])
            pts[i] = [round(pts[i][0] + v[0], 4), round(pts[i][1] + v[1], 4)]
        else:
            i = int(key[1:])
            n = _outward([tuple(p) for p in e["corners"]], i)
            for j in (i, (i + 1) % len(pts)):
                pts[j] = [round(pts[j][0] + n[0] * v, 4),
                          round(pts[j][1] + n[1] * v, 4)]
        try:
            from shapely.geometry import Polygon
            if not Polygon(pts).is_valid:
                return doc, "The sides would cross"
        except Exception:  # noqa: BLE001
            return doc, "Not a slab outline"
        r["corners"] = pts
    why = S.why_not(r)
    if why:
        return doc, why
    return _struct_set(doc, r), None


def _half_along(c: dict, d) -> float:
    """Half a column's size along the plan way ``d``."""
    if c.get("shape") == "round":
        return float(c["w"]) / 2
    cu, cv = _col_axes(c)
    return (abs(cu[0] * d[0] + cu[1] * d[1]) * float(c["w"])
            + abs(cv[0] * d[0] + cv[1] * d[1]) * float(c["d"])) / 2


def beam_magnets(doc: dict, bid: str, key: str, z: float = 0.0) -> list:
    """(value, anchor) — a beam's END onto the columns its line runs
    through (their centre, their faces) and onto the other beams (as a
    wall's end); moved ACROSS: its axis onto the columns' centres, or its
    side flush with their faces (a guide from that column)."""
    from . import structure as S
    st = doc.get("structure") or []
    e = next((x for x in st if x["id"] == bid), None)
    if e is None or e.get("m"):
        return []
    cols = [c for c in st if c.get("type") == "column"
            and c["level"] == e["level"]]
    a, b = tuple(e["a"]), tuple(e["b"])
    if key == "across":
        u = _unit2((b[0] - a[0], b[1] - a[1]))
        n = (-u[1], u[0])
        L, hw = math.dist(a, b), float(e["w"]) / 2
        out = []
        for c in cols:
            cx, cy = S.column_centre(c)
            along = (cx - a[0]) * u[0] + (cy - a[1]) * u[1]
            if not -0.5 <= along <= L + 0.5:
                continue                  # not along it
            q = (cx - a[0]) * n[0] + (cy - a[1]) * n[1]
            h = _half_along(c, n)
            A = (cx, cy, z)
            out.append((q, A))                       # its axis on the centre
            out.append((q + h - hw, A))              # flush with a face
            out.append((q - h + hw, A))
        return [(round(v, 4), A) for v, A in out if abs(v) <= 3.0]
    beams = [S.as_wall(x, shrink=0.0) for x in st
             if x.get("type") == "beam" and x["level"] == e["level"]
             and not x.get("m")]
    fake = {"walls": [dict(bb, level=e["level"]) for bb in beams]}
    out = [(m, None) for m in end_magnets(fake, bid, key)]
    other = "a" if key == "b" else "b"
    O = tuple(e[other])
    u = _unit2((e[key][0] - O[0], e[key][1] - O[1]))
    for c in cols:
        cx, cy = S.column_centre(c)
        along = (cx - O[0]) * u[0] + (cy - O[1]) * u[1]
        off = abs((cx - O[0]) * u[1] - (cy - O[1]) * u[0])
        h = _half_along(c, u)
        if along <= 0 or off > max(h, _half_along(c, (-u[1], u[0]))):
            continue                     # its line doesn't pass the column
        A = (cx, cy, z)
        out.append((along, A))            # its centre
        out.append((along - h, A))        # its near / far face
        out.append((along + h, A))
    return [(round(v, 4), A) for v, A in out if v > 0.1]


NEAR_COL = 8.0          # m: columns whose top / foot a column lines up with
NEAR_BEAM = 6.0         # m: beams whose underside it lines up with


def _nearest_on(a, b, p):
    """The point of segment a–b nearest to p (plan)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, (
        (p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return (a[0] + dx * t, a[1] + dy * t)


def _col_span(doc: dict, c: dict, info: dict):
    """(foot, top) of a column as built — ``info`` = levels_info."""
    li = info.get(c["level"])
    if li is None:
        return None
    top = li["under"] if c.get("height", "level") == "level" \
        else li["z0"] + float(c["height"])
    return li["z0"] + float(c.get("base", 0.0)), top


def vertical_magnets(doc: dict, kind: str, eid: str, key: str,
                     info: dict, p) -> list:
    """(value, anchor) for the grips that go UP / DOWN (his test,
    2026-10-12: «the problem is the vertical»):

    - a column's top / foot: the tops and feet of the columns near it,
      the floors, the slabs' undersides, the beams' undersides of its
      level — value = that height over its floor;
    - a beam's depth: the other beams' of its level;
    - a slab up / down: the floors, the other slabs' tops of its level —
      value = how far; its thickness: the other slabs'."""
    from . import structure as S
    st = doc.get("structure") or []
    e = next((x for x in st if x["id"] == eid), None)
    if e is None or e["level"] not in info:
        return []
    z0 = info[e["level"]]["z0"]
    out = []
    floors = [(li["z0"], None) for li in info.values()] + \
        [(li["under"], None) for li in info.values()]
    if kind == "column" and key in ("top", "base"):
        for o in st:
            if o["id"] == eid or o["level"] not in info:
                continue
            # only what stands NEAR it, the guide to its nearest point —
            # one to a beam's middle far off ran across the view (his
            # screen, 2026-10-12)
            if o.get("type") == "column":
                ox, oy = S.column_centre(o)
                if math.dist((ox, oy), p[:2]) > NEAR_COL:
                    continue
                sp = _col_span(doc, o, info)
                if sp:
                    out += [(zz, (ox, oy, zz)) for zz in sp]
            elif o.get("type") == "beam" and o["level"] == e["level"]:
                q = _nearest_on(o["a"], o["b"], p[:2])
                if math.dist(q, p[:2]) > NEAR_BEAM:
                    continue
                zb = info[o["level"]]["z0"] + info[o["level"]]["height"] \
                    - float(o["h"])
                out.append((zb, (q[0], q[1], zb)))
        out += floors
        return [(round(zz - z0, 4), A) for zz, A in out]
    if kind == "beam" and key == "h":
        for o in st:
            if o.get("type") == "beam" and o["id"] != eid \
                    and o["level"] == e["level"]:
                m = _nearest_on(o["a"], o["b"], p[:2])
                if math.dist(m, p[:2]) > NEAR_BEAM * 2:
                    continue
                zb = info[o["level"]]["z0"] + info[o["level"]]["height"] \
                    - float(o["h"])
                out.append((float(o["h"]), (m[0], m[1], zb)))
        return [(round(v, 4), A) for v, A in out]
    if kind == "slab":
        top = z0 + float(e.get("offset", 0.0))
        for o in st:
            if o.get("type") != "slab" or o["id"] == eid \
                    or o["level"] != e["level"]:
                continue
            cx = sum(q[0] for q in o["corners"]) / len(o["corners"])
            cy = sum(q[1] for q in o["corners"]) / len(o["corners"])
            ot = z0 + float(o.get("offset", 0.0))
            if key == "z":
                out.append((ot - top, (cx, cy, ot)))
            elif key == "t":
                out.append((float(o["t"]), (cx, cy, ot - float(o["t"]))))
        if key == "z":
            out += [(zz - top, A) for zz, A in floors]
        return [(round(v, 4), A) for v, A in out]
    return []


def beam_end_magnets(doc: dict, bid: str, key: str, z: float) -> list:
    """A beam's END, free on its plane: onto a point — another beam's end,
    a column's centre or corner («pt»); else lined up, each way (X / Y),
    with those points (a guide each)."""
    from . import structure as S
    st = doc.get("structure") or []
    e = next((x for x in st if x["id"] == bid), None)
    if e is None:
        return []
    P = tuple(e[key])
    pts = []
    for o in st:
        if o["level"] != e["level"]:
            continue
        if o.get("type") == "beam" and o["id"] != bid and not o.get("m"):
            pts += [tuple(o["a"]), tuple(o["b"])]
        elif o.get("type") == "column":
            pts.append(S.column_centre(o))
            if o.get("shape") != "round":
                pts += [tuple(q) for q in S.column_outline(o, 0.0)]
    # its own other end: square with it
    other = tuple(e["b" if key == "a" else "a"])
    out = [("pt", (Q[0] - P[0], Q[1] - P[1]), (Q[0], Q[1], z)) for Q in pts]
    for Q in pts + [other]:
        out.append(("x", Q[0] - P[0], (Q[0], Q[1], z)))
        out.append(("y", Q[1] - P[1], (Q[0], Q[1], z)))
    return out


def _column_move_magnets(doc: dict, c: dict, z: float) -> list:
    """A column MOVED, in its own axes (u = its width's way, v = its
    depth's): each way on its own — its centre in line with another
    column's centre, its face in line with that column's face (a row
    lined up by its faces), or flush with a wall's face beside it.
    ("x" | "y", value, anchor)."""
    from . import structure as S
    u, v = _col_axes(c)
    cx, cy = S.column_centre(c)
    out = []
    for way, ax in (("x", u), ("y", v)):
        mine = _half_along(c, ax)
        for o in doc.get("structure") or []:
            if o.get("type") != "column" or o["id"] == c["id"] \
                    or o["level"] != c["level"]:
                continue
            ox, oy = S.column_centre(o)
            q = (ox - cx) * ax[0] + (oy - cy) * ax[1]
            if abs(q) > 60.0:
                continue
            h = _half_along(o, ax)
            A = (ox, oy, z)
            out.append((way, q, A))                   # centre on its centre
            if abs(h - mine) > 1e-4:                  # faces on its faces
                out.append((way, q + h - mine, A))
                out.append((way, q - h + mine, A))
        for w in doc.get("walls") or []:          # of every level
            if not straight(w):
                continue
            wu = _unit2((w["b"][0] - w["a"][0], w["b"][1] - w["a"][1]))
            if abs(wu[0] * ax[0] + wu[1] * ax[1]) > 0.02:
                continue                              # not across this way
            cs = W.centre(w)
            t_on = (cx - cs.p0[0]) * wu[0] + (cy - cs.p0[1]) * wu[1]
            if not -0.5 <= t_on <= cs.L + 0.5:
                continue                              # not beside it
            n = (-wu[1], wu[0])
            tt = min(max(t_on, 0.0), cs.L)
            for f in (-1, 1):
                p0 = (cs.p0[0] + n[0] * f * float(w["t"]) / 2,
                      cs.p0[1] + n[1] * f * float(w["t"]) / 2)
                q = (p0[0] - cx) * ax[0] + (p0[1] - cy) * ax[1]
                A = (p0[0] + wu[0] * tt, p0[1] + wu[1] * tt, z)
                for k in (q - mine, q + mine):        # its face on that face
                    if abs(k) <= 3.0:
                        out.append((way, k, A))
    return [(w_, round(k, 4), A) for w_, k, A in out]


def column_magnets(doc: dict, cid: str, key: str, z: float) -> list:
    """A column's face lined up with the faces of the columns in its row
    (the same line across the face) and onto the walls' faces near it."""
    from . import structure as S
    st = doc.get("structure") or []
    c = next((x for x in st if x["id"] == cid), None)
    if c is None or key == "r":
        return []
    if key == "m":
        return _column_move_magnets(doc, c, z)
    u, vv = _col_axes(c)
    dim = "w" if key[0] == "w" else "d"
    s = 1.0 if key[1] == "+" else -1.0
    D = ((u if dim == "w" else vv)[0] * s, (u if dim == "w" else vv)[1] * s)
    cx, cy = S.column_centre(c)
    size = float(c[dim])
    # the face opposite stays: the size is measured from it, along D
    F = (cx - D[0] * size / 2, cy - D[1] * size / 2)
    out = []
    for o in st:                  # the faces of the columns in its row
        if o.get("type") != "column" or o["id"] == cid \
                or o["level"] != c["level"] or o.get("shape") == "round":
            continue
        ou, ov = _col_axes(o)
        if min(abs(ou[0] * D[1] - ou[1] * D[0]),
               abs(ou[0] * D[0] + ou[1] * D[1])) > 0.02:
            continue                      # turned another way
        ox, oy = S.column_centre(o)
        co = (ox - F[0]) * D[0] + (oy - F[1]) * D[1]
        half = (float(o["w"]) if abs(ou[0] * D[0] + ou[1] * D[1]) > 0.5
                else float(o["d"])) / 2
        for q in (co - half, co + half):
            if abs(q - size) <= 1.5:      # near: the row it stands in
                out.append((q, (ox + D[0] * (q - co), oy + D[1] * (q - co),
                                z)))
        # the SAME SIZE as a column near it (its size that way): the guide
        # runs from that column's face (his test, 2026-10-12: a row of
        # equal columns gave nothing to line up with while resizing)
        if math.dist((ox, oy), (cx, cy)) <= NEAR_COL and \
                abs(2 * half - size) > 1e-4:
            out.append((2 * half, (ox + D[0] * half, oy + D[1] * half, z)))
    for b in st:                  # flush with the side of a beam beside it
        if b.get("type") != "beam" or b["level"] != c["level"] \
                or b.get("m"):
            continue
        bu = _unit2((b["b"][0] - b["a"][0], b["b"][1] - b["a"][1]))
        if abs(bu[0] * D[0] + bu[1] * D[1]) > 0.02:
            continue                      # not along the face
        q0 = _nearest_on(b["a"], b["b"], (cx, cy))
        if math.dist(q0, (cx, cy)) > 1.5 + float(b["w"]):
            continue
        for s2 in (-1, 1):
            side = (q0[0] + D[0] * s2 * float(b["w"]) / 2,
                    q0[1] + D[1] * s2 * float(b["w"]) / 2)
            q = (side[0] - F[0]) * D[0] + (side[1] - F[1]) * D[1]
            if abs(q - size) <= 1.5:
                out.append((q, (side[0], side[1], z)))
    for w in doc.get("walls") or []:  # the faces of the walls along it
        if w["level"] != c["level"] or not straight(w):
            continue
        wu = _unit2((w["b"][0] - w["a"][0], w["b"][1] - w["a"][1]))
        if abs(wu[0] * D[0] + wu[1] * D[1]) > 0.02:
            continue                      # not parallel to the face
        cs = W.centre(w)
        t_on = (F[0] - cs.p0[0]) * wu[0] + (F[1] - cs.p0[1]) * wu[1]
        if not -0.5 <= t_on <= cs.L + 0.5:
            continue                      # not beside it
        n = (-wu[1], wu[0])
        for f in (-1, 1):                 # its two faces
            p0 = (cs.p0[0] + n[0] * f * float(w["t"]) / 2,
                  cs.p0[1] + n[1] * f * float(w["t"]) / 2)
            q = (p0[0] - F[0]) * D[0] + (p0[1] - F[1]) * D[1]
            if abs(q - size) <= 1.5:
                tt = min(max(t_on, 0.0), cs.L)
                out.append((q, (p0[0] + wu[0] * tt, p0[1] + wu[1] * tt, z)))
    return [(round(v, 4), A) for v, A in out if v >= 0.05]


def slab_magnets(doc: dict, sid: str, key: str, z: float) -> list:
    """A slab's corner: onto the points of its level (another slab's
    corner, a wall's end, a column's corner) — ("pt", (dx, dy), anchor);
    lined up, each way, with the other corners of its own outline and the
    walls' ends — ("x" | "y", d, anchor). A slab's side: onto the line and
    faces of the walls running parallel to it, near — (d, anchor)."""
    from . import structure as S
    st = doc.get("structure") or []
    s = next((x for x in st if x["id"] == sid), None)
    if s is None:
        return []
    lid = s["level"]
    pts = [tuple(p) for p in s["corners"]]
    # the walls of EVERY level (a line seen over another level pulls too —
    # his test, 2026-10-13)
    walls = [w for w in doc.get("walls") or [] if straight(w)]
    if key.startswith("v"):
        i = int(key[1:])
        P = pts[i]
        others = [tuple(p) for x in st if x.get("type") == "slab"
                  and x["level"] == lid and x["id"] != sid
                  for p in x["corners"]]
        others += [tuple(w[e]) for w in walls for e in ("a", "b")]
        others += [tuple(q) for c in st if c.get("type") == "column"
                   and c["level"] == lid and c.get("shape") != "round"
                   for q in S.column_outline(c, 0.0)]
        out = [("pt", (Q[0] - P[0], Q[1] - P[1]), (Q[0], Q[1], z))
               for Q in others]
        lines = [Q for j, Q in enumerate(pts) if j != i] + \
            [tuple(w[e]) for w in walls for e in ("a", "b")]
        for Q in lines:
            out.append(("x", Q[0] - P[0], (Q[0], Q[1], z)))
            out.append(("y", Q[1] - P[1], (Q[0], Q[1], z)))
        return out
    i = int(key[1:])
    a, b = pts[i], pts[(i + 1) % len(pts)]
    n = _outward(pts, i)
    su = _unit2((b[0] - a[0], b[1] - a[1]))
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    L = math.dist(a, b)
    out = []
    for w in walls:
        wu = _unit2((w["b"][0] - w["a"][0], w["b"][1] - w["a"][1]))
        if abs(wu[0] * su[1] - wu[1] * su[0]) > 0.02:
            continue                          # not parallel to the side
        cs = W.centre(w)
        wn = (-wu[1], wu[0])
        # beside it: their stretches overlap along the side
        t0 = (w["a"][0] - mid[0]) * su[0] + (w["a"][1] - mid[1]) * su[1]
        t1 = (w["b"][0] - mid[0]) * su[0] + (w["b"][1] - mid[1]) * su[1]
        if max(t0, t1) < -L / 2 or min(t0, t1) > L / 2:
            continue
        for p0 in (tuple(w["a"]),
                   (cs.p0[0] + wn[0] * float(w["t"]) / 2,
                    cs.p0[1] + wn[1] * float(w["t"]) / 2),
                   (cs.p0[0] - wn[0] * float(w["t"]) / 2,
                    cs.p0[1] - wn[1] * float(w["t"]) / 2)):
            q = (p0[0] - mid[0]) * n[0] + (p0[1] - mid[1]) * n[1]
            if abs(q) <= 2.0:
                tt = min(max((t0 + t1) / 2, -L / 2), L / 2)
                out.append((q, (mid[0] + n[0] * q + su[0] * tt,
                                mid[1] + n[1] * q + su[1] * tt, z)))
    # the sides of the OTHER slabs of its level, parallel and beside it —
    # two slabs meet without a gap (his test, 2026-10-12)
    for x in st:
        if x.get("type") != "slab" or x["id"] == sid or x["level"] != lid:
            continue
        op = [tuple(p) for p in x["corners"]]
        for j in range(len(op)):
            p, q2 = op[j], op[(j + 1) % len(op)]
            ou = _unit2((q2[0] - p[0], q2[1] - p[1]))
            if abs(ou[0] * su[1] - ou[1] * su[0]) > 0.02:
                continue
            t0 = (p[0] - mid[0]) * su[0] + (p[1] - mid[1]) * su[1]
            t1 = (q2[0] - mid[0]) * su[0] + (q2[1] - mid[1]) * su[1]
            if max(t0, t1) < -L / 2 or min(t0, t1) > L / 2:
                continue                      # not beside it
            d = (p[0] - mid[0]) * n[0] + (p[1] - mid[1]) * n[1]
            if abs(d) <= 3.0:
                tt = min(max((t0 + t1) / 2, -L / 2), L / 2)
                out.append((d, (mid[0] + n[0] * d + su[0] * tt,
                                mid[1] + n[1] * d + su[1] * tt, z)))
    return [(round(v, 4), A) for v, A in out]


def opening_changed(doc: dict, oid: str, key: str, v: float,
                    wall_height: float):
    """(the document with the opening's grip ``key`` at value ``v``, why
    not or None)."""
    from . import structure as S
    ops = doc.get("openings") or []
    o = next((x for x in ops if x["id"] == oid), None)
    w = next((x for x in doc["walls"] if o and x["id"] == o["wall"]), None)
    if o is None or w is None:
        return doc, "Gone"
    pos, ow = float(o["pos"]), float(o["w"])
    sill, h = float(o.get("sill", 0.0)), float(o["h"])
    n = dict(o)
    if key == "left":
        n.update(w=v, pos=pos + ow / 2 - v / 2)
    elif key == "right":
        n.update(w=v, pos=pos - ow / 2 + v / 2)
    elif key == "top":
        n.update(h=v)
    elif key == "bottom":
        n.update(sill=v, h=sill + h - v)
        if v < 0:
            return doc, "Not under the floor"
    elif key == "pos":
        n.update(pos=pos + v)
    for k in ("w", "h", "sill", "pos"):
        if k in n:
            n[k] = round(float(n[k]), 4)
    why = S.opening_room(n, w, ops, wall_height)
    if why:
        return doc, why
    return dict(doc, openings=[n if x["id"] == oid else x for x in ops]), None


def wall_changed(doc: dict, wid: str, key: str, v: float):
    """(the document with the wall's grip ``key`` at value ``v``, why not
    or None). An END: the wall's new length; the corner's walls follow —
    one in line with it keeps its line (it gets shorter / longer), one at
    an angle is MOVED (wallmove: the walls joined to it stretch, the
    rectangle stays a rectangle). ACROSS: moved by v (wallmove)."""
    from . import wallmove
    walls = doc.get("walls") or []
    w = next((x for x in walls if x["id"] == wid), None)
    if w is None or not straight(w):
        return doc, "Gone"
    if key == "across":
        if abs(v) < 1e-9:
            return doc, None
        new, notes = wallmove.move(doc, {wid: wallmove.across(w, v)})
        return new, _short(notes)
    if v < max(float(w.get("t", 0.1)), 0.10):
        return doc, "Too short"
    other = "a" if key == "b" else "b"
    E, O = tuple(w[key]), tuple(w[other])
    uk = _unit2((E[0] - O[0], E[1] - O[1]))
    En = (round(O[0] + uk[0] * v, 4), round(O[1] + uk[1] * v, 4))
    d = (En[0] - E[0], En[1] - E[1])
    if math.hypot(*d) < 1e-6:
        return doc, None
    inline, turned = [], []
    for x in walls:
        if x["id"] == wid or x["level"] != w["level"] or not straight(x):
            continue
        for end in ("a", "b"):
            if math.dist(x[end], E) <= TOL:
                ux = _unit2((x["b"][0] - x["a"][0], x["b"][1] - x["a"][1]))
                cross = abs(uk[0] * ux[1] - uk[1] * ux[0])
                (inline if cross < 0.05 else turned).append((x["id"], end))
    new, notes = doc, []
    if turned:
        new, notes = wallmove.move(doc, {i: d for i, _e in turned})
        why = _short(notes)
        if why:
            return doc, why
    # the wall itself (and one in line at that corner): the end goes there
    # — wallmove may have stretched it already; then this changes nothing
    ends = {(wid, key)} | set(inline)
    out, slid = [], {}
    for x in new["walls"]:
        hit = [e for i, e in ends if i == x["id"]]
        if hit:
            x = dict(x)
            for e in hit:
                if e == "a" and list(x["a"]) != list(En):
                    ux = _unit2((x["b"][0] - x["a"][0],
                                 x["b"][1] - x["a"][1]))
                    slid[x["id"]] = (En[0] - x["a"][0]) * ux[0] + \
                        (En[1] - x["a"][1]) * ux[1]
                x[e] = [En[0], En[1]]
            if math.dist(x["a"], x["b"]) < max(float(x.get("t", 0.1)), 0.10):
                return doc, f"«{x.get('name', 'Wall')}» would get too short"
            why = W.why_not(x)
            if why:
                return doc, why
        out.append(x)
    new = dict(new, walls=out)
    if slid:     # their start slid: openings keep their place in the world
        new["openings"] = [dict(o, pos=round(float(o["pos"]) - slid[o["wall"]],
                                             4)) if o["wall"] in slid else o
                           for o in new.get("openings") or []]
    return new, None


def end_magnets(doc: dict, wid: str, key: str) -> list[float]:
    """The lengths at which a wall's END (``key``) lands exactly on another
    wall of its level — its drawn line, either face, or one of its ends
    lying on this wall's line — so a grip let go there JOINS (his test,
    2026-10-12: a 5 cm step stopped it 1–2 cm off, and it stayed loose)."""
    walls = doc.get("walls") or []
    w = next((x for x in walls if x["id"] == wid), None)
    if w is None or not straight(w):
        return []
    other = "a" if key == "b" else "b"
    O = tuple(w[other])
    u = _unit2((w[key][0] - O[0], w[key][1] - O[1]))
    out = []
    for x in walls:
        if x["id"] == wid or x["level"] != w["level"] or not straight(x):
            continue
        a, b = tuple(x["a"]), tuple(x["b"])
        for P in (a, b):                 # its end on my line: meet it
            v = (P[0] - O[0], P[1] - O[1])
            along = v[0] * u[0] + v[1] * u[1]
            if along > 0 and abs(v[0] * u[1] - v[1] * u[0]) <= TOL:
                out.append(along)
        ux = _unit2((b[0] - a[0], b[1] - a[1]))
        den = u[0] * ux[1] - u[1] * ux[0]
        if abs(den) < 0.05:              # parallel: no crossing
            continue
        n = (-ux[1], ux[0])
        c = W.centre(x)
        Lx = math.dist(a, b)
        for off in (0.0, None, -1, 1):   # its line drawn, centre, faces
            if off is None:
                p0 = c.p0
            elif off == 0.0:
                p0 = a
            else:
                p0 = (c.p0[0] + n[0] * off * float(x["t"]) / 2,
                      c.p0[1] + n[1] * off * float(x["t"]) / 2)
            # O + u s = p0 + ux r
            dx, dy = p0[0] - O[0], p0[1] - O[1]
            s = (dx * ux[1] - dy * ux[0]) / den
            r = (dx * u[1] - dy * u[0]) / den
            if s > 0 and -float(x["t"]) <= r <= Lx + float(x["t"]):
                out.append(s)
    return sorted({round(s, 4) for s in out})


def opening_magnets(doc: dict, z0s: dict, oid: str, key: str) -> list:
    """[(value, anchor)] — where a door's / window's grip lines up with
    the OTHER openings (his ask, 2026-10-12: «without temporary alignment
    guides it is almost impossible»); ``anchor`` = the world point it
    lines up with (the dashed guide is drawn from it).

    - a side or the centre: with the sides and centres of the openings in
      PARALLEL walls — on every level (a façade lined up floor over floor);
    - the top / the sill: with the tops and sills of its level's openings
      (the windows' heads with the doors').
    ``z0s`` = {level id: its floor's height}."""
    ops = doc.get("openings") or []
    walls = {w["id"]: w for w in doc.get("walls") or []}
    o = next((x for x in ops if x["id"] == oid), None)
    w = walls.get(o["wall"]) if o else None
    if w is None or not straight(w) or w["level"] not in z0s:
        return []
    seg = W.centre(w)
    u = seg.u
    pos, ow = float(o["pos"]), float(o["w"])
    sill, h = float(o.get("sill", 0.0)), float(o["h"])
    z0 = z0s[w["level"]]
    out = []
    for p in ops:
        pw = walls.get(p["wall"])
        if p["id"] == oid or pw is None or not straight(pw) \
                or pw["level"] not in z0s:
            continue
        ps = W.centre(pw)
        pu = ps.u
        pz0 = z0s[pw["level"]]
        pp, pwd = float(p["pos"]), float(p["w"])
        psill, ph = float(p.get("sill", 0.0)), float(p["h"])

        def world(s, z, ps=ps, pu=pu):
            return (ps.p0[0] + pu[0] * s, ps.p0[1] + pu[1] * s, z)
        # only in the SAME PLANE: its wall, the walls on its line, the
        # floors above / below (his test, 2026-10-12: parallel walls across
        # a room gave guides at odd angles — too many, no use)
        if abs(u[0] * pu[1] - u[1] * pu[0]) > 0.02:
            continue                           # not parallel
        across = abs((ps.p0[0] - seg.p0[0]) * -u[1]
                     + (ps.p0[1] - seg.p0[1]) * u[0])
        if across > max(float(w["t"]), float(pw["t"])) / 2 + PLANE_TOL:
            continue                           # another plane
        if key in ("left", "right", "pos"):
            if pw["level"] == w["level"]:
                continue                       # its own floor: they'd overlap
            zm = pz0 + psill + ph / 2
            for s2 in (pp - pwd / 2, pp, pp + pwd / 2):
                A = world(s2, zm)
                q = (A[0] - seg.p0[0]) * u[0] + (A[1] - seg.p0[1]) * u[1]
                if key == "left":
                    out.append((pos + ow / 2 - q, A))
                elif key == "right":
                    out.append((q - pos + ow / 2, A))
                else:                          # its centre or a side on it
                    for mine in (0.0, -ow / 2, ow / 2):
                        out.append((q - pos - mine, A, mine))
        elif key in ("top", "bottom") and pw["level"] == w["level"]:
            for z in (pz0 + psill + ph, pz0 + psill):
                if z == pz0 + psill and p["kind"] == "door":
                    continue                   # a door's foot: the floor
                A = world(pp, z)
                out.append(((z - z0 - sill) if key == "top" else (z - z0), A))
    # (value, the point lined up with, how far along the grip's axis from
    # the grip ITS lined-up point is — a side, when the centre is dragged)
    # one per value (a façade repeats the same line floor after floor):
    # the nearest point lined up with — its guide is the shortest
    me = (seg.p0[0] + u[0] * pos, seg.p0[1] + u[1] * pos, z0 + sill + h / 2)
    best: dict = {}
    for m in out:
        v = round(m[0], 4)
        d = math.dist(me, m[1])
        if v not in best or d < best[v][0]:
            best[v] = (d, (v, m[1], m[2] if len(m) > 2 else 0.0))
    out = [b[1] for b in best.values()]
    if key == "pos":
        return out
    return [m for m in out if m[0] >= 0.2 or (key == "bottom"
                                              and m[0] >= 0.0)]


def _short(notes) -> str | None:
    for n in notes or ():
        if n.startswith("not stretched"):
            return "A joined wall would get too short"
    return None


def fits(doc: dict, wall_ids, wall_height) -> str | None:
    """Every opening of these walls still in its wall (a wall shortened)."""
    from . import structure as S
    walls = {w["id"]: w for w in doc["walls"]}
    ops = doc.get("openings") or []
    for o in ops:
        if o["wall"] in wall_ids and o["wall"] in walls:
            why = S.opening_room(o, walls[o["wall"]], ops,
                                 wall_height(walls[o["wall"]]))
            if why:
                return f"«{o.get('name', 'Opening')}»: {why}"
    return None


# ---- the mouse on a grip's axis -----------------------------------------------------------
def axis_param(to_px, p, axis, mouse, h: float = 0.5):
    """How far along ``axis`` from ``p`` (m) the screen point ``mouse``
    lies — None when the axis is seen end-on (or behind the eye).
    ``to_px(x, y, z)`` → (px, py) | None."""
    q = [to_px(p[0] + axis[0] * t, p[1] + axis[1] * t, p[2] + axis[2] * t)
         for t in (-h, 0.0, h)]
    if any(x is None for x in q):
        return None
    dx, dy = q[2][0] - q[0][0], q[2][1] - q[0][1]
    span = math.hypot(dx, dy)
    if span < MIN_PX_PER_M * 2 * h:
        return None
    ex, ey = dx / span, dy / span

    def s(pt):
        return (pt[0] - q[1][0]) * ex + (pt[1] - q[1][1]) * ey
    sm, s1, sp = s(q[0]), 0.0, s(q[2])
    # s(t) = (α t + β) / (γ t + 1), t in units of h; β = s(0) = 0
    if abs(sp - sm) < 1e-9:
        return None
    g = (2 * s1 - sp - sm) / (sp - sm)
    a = sp * (g + 1) - s1
    sv = s(mouse)
    den = a - sv * g
    if abs(den) < 1e-9:
        return None
    return (sv - s1) / den * h


def _solve(A, b):
    """Gaussian elimination (small systems) — None when singular."""
    n = len(b)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-12:
            return None
        M[c], M[piv] = M[piv], M[c]
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]


def _quad_area(px) -> float:
    """The area of the image of a unit square (points 00, 10, 01, 11)."""
    return abs(sum(px[i][0] * px[j][1] - px[j][0] * px[i][1]
                   for i, j in ((0, 1), (1, 3), (3, 2), (2, 0)))) / 2


def plane_param(to_px, p, e1, e2, mouse, h: float = 1.0):
    """(s, t) of the screen point ``mouse`` on the plane through ``p``
    spanned by ``e1`` / ``e2`` (m) — a homography solved from four points
    (exact in perspective). None when the plane is seen edge-on."""
    st = [(0.0, 0.0), (h, 0.0), (0.0, h), (h, h)]
    px = [to_px(p[0] + e1[0] * s + e2[0] * t, p[1] + e1[1] * s + e2[1] * t,
                p[2] + e1[2] * s + e2[2] * t) for s, t in st]
    if any(q is None for q in px):
        return None
    if _quad_area(px) < 1e-6:            # edge-on: a line
        return None
    A, b = [], []
    for (s, t), (x, y) in zip(st, px):
        A.append([s, t, 1, 0, 0, 0, -s * x, -t * x])
        b.append(x)
        A.append([0, 0, 0, s, t, 1, -s * y, -t * y])
        b.append(y)
    H = _solve(A, b)
    if H is None:
        return None
    a_, b_, c_, d_, e_, f_, g_, h_ = H
    X, Y = mouse
    sol = _solve([[a_ - g_ * X, b_ - h_ * X], [d_ - g_ * Y, e_ - h_ * Y]],
                 [X - c_, Y - f_])
    return None if sol is None else (sol[0], sol[1])


E2 = (0.0, 1.0, 0.0)    # a point grip's second way (its plane: level)

END_ON = 0.2           # an axis this short next to the others there: end-on


def _span(to_px, p, d) -> float:
    a = to_px(p[0] - d[0] * 0.5, p[1] - d[1] * 0.5, p[2] - d[2] * 0.5)
    b = to_px(p[0] + d[0] * 0.5, p[1] + d[1] * 0.5, p[2] + d[2] * 0.5)
    return math.dist(a, b) if a and b else 0.0


def seen(to_px, g: Grip) -> bool:
    """The grip shows and its axis is not seen end-on — measured against
    the world's axes AT that point (the far end of a long wall in
    perspective is small, not end-on: his model, 2026-10-12)."""
    if to_px(*g.p) is None:
        return False
    if g.mode == "point":                 # free on its plane: not edge-on
        e2 = g.extra.get("e2", E2)
        q = [to_px(g.p[0] + g.axis[0] * s + e2[0] * t,
                   g.p[1] + g.axis[1] * s + e2[1] * t,
                   g.p[2] + g.axis[2] * s + e2[2] * t)
             for s, t in ((0, 0), (1, 0), (0, 1), (1, 1))]
        if any(x is None for x in q):
            return False
        most = max(_span(to_px, g.p, d) for d in
                   ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        return most > 0 and _quad_area(q) >= (END_ON * most) ** 2
    mine = _span(to_px, g.p, g.axis)
    most = max(_span(to_px, g.p, d) for d in
               ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    return mine >= 1.5 and mine >= END_ON * most and \
        axis_param(to_px, g.p, g.axis, to_px(*g.p)) is not None


def snapped(g: Grip, delta: float, fine: bool) -> float:
    """The grip's value for a move of ``delta`` along its axis: a size to
    the step (5 cm, Shift 1 cm), a move by steps."""
    step = FINE if fine else STEP
    if g.mode == "move":
        return round(round(delta / step) * step, 4)
    return round(round((g.base + delta) / step) * step, 4)


def _nearest(magnets: list, p, point: bool) -> list:
    """One magnet per value, its anchor the NEAREST to the grip: a row of
    columns lines up the same value 40 m away too — the guide went to one
    off the screen and was never seen (his test, 2026-10-12)."""
    best: dict = {}
    for m in magnets:
        if point:
            key, A = (m[0], round(m[1], 4) if m[0] != "pt" else
                      tuple(round(c, 4) for c in m[1])), m[2]
        else:
            key, A = round(m[0], 4), m[1]
        # one with a point to show wins over one without (a floor's height
        # equal to the neighbour column's top hid its guide: his screen,
        # 2026-10-12)
        d = math.dist(p, A) if A is not None else float("inf")
        if key not in best or d < best[key][0]:
            best[key] = (d, m)
    return [b[1] for b in best.values()]


# ---- the mouse over the 3D view ---------------------------------------------------------
class GripControl(QObject):
    """The viewport's event filter (installed last: it sees a press
    first). It takes only a press ON a grip; the rest goes to the host.

    ``owner`` gives: ``grip_targets()`` → (kind, id, [Grip]) | None,
    ``grip_value(kind, id, grip, v)`` → (doc, why), ``grip_live(doc)``,
    ``grip_store(doc, kind, id, note)``, ``grip_back()``, ``viewport``."""

    def __init__(self, owner) -> None:
        super().__init__()
        self.owner = owner
        self.hot = None              # the grip key under the mouse
        self.drag = None             # dict while a grip moves
        self.eat_release = False
        self._typed = ""

    # -- helpers ------------------------------------------------------------------------
    def _px(self, x, y, z):
        from . import compat
        return compat.to_pixel(self.owner.viewport, x, y, z)

    def _targets(self):
        try:
            return self.owner.grip_targets()
        except Exception:  # noqa: BLE001 — never in the host's way
            return None

    def _grip_at(self, x, y):
        t = self._targets()
        if not t:
            return None, None
        best = None
        for g in t[2]:
            if not seen(self._px, g):
                continue
            q = self._px(*g.p)
            d = math.dist(q, (x, y))
            if d <= HIT_PX and (best is None or d < best[0]):
                best = (d, g)
        return t, (best[1] if best else None)

    # -- the drag ---------------------------------------------------------------------
    def _start(self, t, g, x, y) -> None:
        point = g.mode == "point"
        if point:
            t0 = plane_param(self._px, g.p, g.axis, g.extra.get("e2", E2),
                             (x, y)) or (0.0, 0.0)
        else:
            t0 = axis_param(self._px, g.p, g.axis, (x, y)) or 0.0
        try:
            raw = self.owner.grip_magnets(t[0], t[1], g)
            # a point's: ("pt" | "x" | "y", value, anchor) as they come
            # (value, anchor, offset): a (value, anchor) one gets offset 0 —
            # padded to None it broke the drawing when it stuck: no guide,
            # no label (his screen, 2026-10-12)
            magnets = list(raw) if point else [
                (float(m[0]), m[1] if len(m) > 1 else None,
                 float(m[2]) if len(m) > 2 and m[2] is not None else 0.0)
                if isinstance(m, tuple) else (float(m), None, 0.0)
                for m in raw]
        except Exception:  # noqa: BLE001 — without magnets, then
            magnets = []
        magnets = _nearest(magnets, g.p, point)
        self.drag = {"kind": t[0], "id": t[1], "g": g, "t0": t0,
                     "press": (x, y), "moved": False, "carry": False,
                     "v": (0.0, 0.0) if point else
                     (g.base if g.mode == "size" else 0.0),
                     "doc": None, "why": None, "fine": False,
                     "magnets": magnets, "stuck": False, "anchor": None,
                     "anchors": []}
        self._typed = ""
        ring = getattr(self.owner, "radial", None)
        if ring is not None and ring.isVisible():
            ring.dismiss()
        self.owner.viewport.setFocus()

    def _follow_point(self, x, y, fine: bool) -> None:
        """A corner free on its plane: onto a point (another corner, a
        wall's end) — else each way on its own: lined up with a corner of
        its own outline (a guide each), else by steps."""
        d = self.drag
        g = d["g"]
        d["mouse"] = (x, y)
        if d.get("lock") == "z":          # ↑: up / down, whole
            t = axis_param(self._px, g.p, (0.0, 0.0, 1.0), (x, y))
            if t is None:
                return
            step = FINE if fine else STEP
            dz = round(round((t - d["zt0"]) / step) * step, 4)
            d["fine"], d["stuck"], d["anchors"] = fine, False, []
            self._set((0.0, 0.0, dz))
            return
        st = plane_param(self._px, g.p, g.axis, g.extra.get("e2", E2), (x, y))
        if st is None:
            return
        raw = (st[0] - d["t0"][0], st[1] - d["t0"][1])
        if d.get("lock") == "x":          # →: its own first way only
            raw = (raw[0], 0.0)
        elif d.get("lock") == "y":        # ←: the other
            raw = (0.0, raw[1])
        ppm = max(_span(self._px, g.p, g.axis),
                  _span(self._px, g.p, g.extra.get("e2", E2)))
        tol = MAGNET_PX / ppm if ppm > 0 else 0.0
        pts = [m for m in d["magnets"] if m[0] == "pt"
               and math.dist(m[1], raw) <= tol]
        anchors = []
        if pts:          # onto a point: its diamond marks it (no line)
            best = min(pts, key=lambda m: math.dist(m[1], raw))
            v = (round(best[1][0], 4), round(best[1][1], 4))
            stuck = True
            anchors.append(best[2])
        else:
            step = FINE if fine else STEP
            v = [round(round(c / step) * step, 4) for c in raw]
            stuck = False
            for i, way in ((0, "x"), (1, "y")):
                if d.get("lock") in ("x", "y") and d["lock"] != way:
                    continue              # locked: the other way stays 0
                near = [m for m in d["magnets"] if m[0] == way
                        and abs(m[1] - raw[i]) <= tol]
                if near:
                    best = min(near, key=lambda m: abs(m[1] - raw[i]))
                    v[i] = round(best[1], 4)
                    anchors.append(best[2])
                    stuck = True
            v = tuple(v)
        d["fine"], d["stuck"] = fine, stuck
        d["anchor"], d["anchors"] = None, [a for a in anchors if a]
        d["onpoint"] = bool(pts)
        self._set(v)

    def _follow(self, x, y, fine: bool) -> None:
        d = self.drag
        if d["g"].mode == "point":
            self._follow_point(x, y, fine)
            return
        t = axis_param(self._px, d["g"].p, d["g"].axis, (x, y))
        if t is None:
            return
        d["fine"] = fine
        g = d["g"]
        raw = (g.base if g.mode == "size" else 0.0) + t - d["t0"]
        ppm = _span(self._px, g.p, g.axis)          # px per metre there
        near = [m for m in d["magnets"]
                if ppm > 0 and abs(m[0] - raw) * ppm <= MAGNET_PX]
        if near:       # on another wall / lined up with an opening: exactly
            best = min(near, key=lambda m: abs(m[0] - raw))
            d["stuck"], d["anchor"], d["off"] = True, best[1], best[2]
            self._set(best[0])
        else:
            d["stuck"], d["anchor"] = False, None
            self._set(snapped(g, t - d["t0"], fine))

    def _set(self, v) -> None:
        d = self.drag
        if d["doc"] is not None and v == d["v"]:
            return
        doc, why = self.owner.grip_value(d["kind"], d["id"], d["g"], v)
        if why:
            d["why"] = why               # it stops at the last good place
        else:
            d["why"], d["v"], d["doc"] = None, v, doc
            self.owner.grip_live(doc)
        self.owner.viewport.update()

    def _drop(self) -> None:
        d, self.drag = self.drag, None
        self._typed = ""
        if d and d["doc"] is not None:
            g = d["g"]
            self.owner.grip_store(d["doc"], d["kind"], d["id"],
                                  label(g, d["v"]))
        else:
            self.owner.grip_back()
        self.owner.viewport.update()

    def cancel(self) -> None:
        if self.drag is not None:
            self.drag = None
            self._typed = ""
            self.owner.grip_back()
            self.owner.viewport.update()

    # -- events -----------------------------------------------------------------------
    def eventFilter(self, obj, event) -> bool:  # noqa: C901 — one switch
        t = event.type()
        try:
            if t == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                p = event.position()
                if self.drag is not None:          # carried: this click drops it
                    self._follow(p.x(), p.y(), bool(
                        event.modifiers() & Qt.ShiftModifier))
                    self._drop()
                    self.eat_release = True
                    return True
                tg, g = self._grip_at(p.x(), p.y())
                if g is None:
                    return False
                self._start(tg, g, p.x(), p.y())
                self.eat_release = True
                return True
            if t == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                if self.drag is not None and not self.drag["carry"]:
                    if self.drag["moved"]:
                        self._drop()
                    else:                          # a click: it is carried
                        self.drag["carry"] = True
                    self.eat_release = False
                    return True
                if self.eat_release:
                    self.eat_release = False
                    return True
                return False
            if t == QEvent.MouseMove:
                p = event.position()
                if self.drag is not None:
                    d = self.drag
                    if not d["moved"] and math.dist(d["press"], (p.x(), p.y())) \
                            >= DRAG_PX:
                        d["moved"] = True
                    if d["moved"] or d["carry"]:
                        self._follow(p.x(), p.y(), bool(
                            event.modifiers() & Qt.ShiftModifier))
                    return True
                _tg, g = self._grip_at(p.x(), p.y())
                k = g.key if g else None
                if k != self.hot:
                    self.hot = k
                    self.owner.viewport.update()
                return False
            if t == QEvent.MouseButtonDblClick and self.drag is not None:
                self.cancel()        # a double click on a grip: nothing
                self.eat_release = True
                return True
            if t == QEvent.ShortcutOverride and self.drag is not None:
                event.accept()       # its keys (digits, «c», «m»): ours
                return True
            if t == QEvent.KeyPress and self.drag is not None:
                return self._key(event)
        except Exception:  # noqa: BLE001 — never break the host's mouse
            from . import compat
            compat.log_error("grips")
            self.drag = None
        return False

    def _key(self, event) -> bool:
        k = event.key()
        if k == Qt.Key_Escape:
            self.cancel()
            return True
        d = self.drag
        locks = {Qt.Key_Up: "z", Qt.Key_Right: "x", Qt.Key_Left: "y"}
        if k in locks and d["g"].mode == "point" and not self._typed:
            # the host's own Move keys: ↑ = up / down (blue), → / ← = one
            # way only — again: free
            want = locks[k]
            if want == "z" and not d["g"].extra.get("z"):
                return True
            d["lock"] = None if d.get("lock") == want else want
            if d["lock"] == "z":
                m = d.get("mouse") or d["press"]
                t = axis_param(self._px, d["g"].p, (0.0, 0.0, 1.0), m)
                d["zt0"] = t or 0.0
                self._set((0.0, 0.0, 0.0))
            elif d.get("mouse"):
                self._follow_point(*d["mouse"], d.get("fine", False))
            self.owner.viewport.update()
            return True
        if k in (Qt.Key_Return, Qt.Key_Enter):
            from .library import parse_measure
            g = self.drag["g"]
            typed, self._typed = self._typed.strip(), ""
            v = parse_measure(typed, "m" if self.drag["kind"] == "opening"
                              else "len")
            if v is None:
                return True
            if g.mode == "point":       # that far, the way it is going
                cur = self.drag["v"]
                L = math.hypot(*cur)
                if L < 1e-9:
                    return True
                v = tuple(round(c / L * abs(v), 4) for c in cur)
                self.drag["stuck"], self.drag["anchors"] = False, []
                self._set(v)
                if self.drag["why"] is None:
                    self._drop()
                return True
            if g.mode == "move" and typed[:1] not in "+-":
                # a distance: the way the mouse went (a sign typed: that way)
                v = math.copysign(abs(v), self.drag["v"] or 1.0)
            self.drag["stuck"], self.drag["anchor"] = False, None
            self._set(round(v, 4))
            if self.drag["why"] is None:
                self._drop()
            else:
                from . import compat
                compat.flash(self.owner.viewport, self.drag["why"], 3000)
            return True
        if k == Qt.Key_Backspace:
            self._typed = self._typed[:-1]
            self.owner.viewport.update()
            return True
        s = event.text()
        # digits, a unit (cm / mm / m), feet and inches (2'6 1/2")
        if s and (s.isdigit() or s in ".,-/'\" " or s.lower() in "cmftin"):
            self._typed += s
            self.owner.viewport.update()
            return True
        return True                     # nothing else while a grip moves

    # -- drawn over the view ------------------------------------------------------------
    def draw(self, viewport, painter) -> None:
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QFont, QPen
        t = self._targets()
        if not t:
            return
        d = self.drag
        grips = t[2]
        if d is not None:     # the moving one: where its value puts it
            g = d["g"]
            if g.mode == "point":
                e2 = g.extra.get("e2", E2)
                a, b = d["v"][0], d["v"][1]
                dz = d["v"][2] if len(d["v"]) > 2 else 0.0
                moved = tuple(g.p[i] + g.axis[i] * a + e2[i] * b
                              + (dz if i == 2 else 0.0) for i in range(3))
            else:
                off = d["v"] - g.base if g.mode == "size" else d["v"]
                moved = (g.p[0] + g.axis[0] * off, g.p[1] + g.axis[1] * off,
                         g.p[2] + g.axis[2] * off)
            grips = [Grip(g.key, moved, g.axis, g.base, g.mode, g.arrow,
                          g.tip, g.extra)]
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        try:
            for g in grips:
                if not seen(self._px, g):
                    continue
                x, y = self._px(*g.p)
                hot = d is not None or g.key == self.hot
                ink = QColor(HOT if hot else DOT)
                if g.arrow:
                    self._arrow(painter, g, x, y, ink, hot)
                    continue
                r = HOT_HALF_PX if hot else HALF_PX
                painter.setPen(QPen(QColor(OUTLINE), 1.2))
                painter.setBrush(ink)
                if g.extra.get("shape") == "circle":     # a move: round
                    r += 1.5
                    painter.drawEllipse(QRectF(x - r, y - r, 2 * r, 2 * r))
                else:
                    painter.drawRect(QRectF(x - r, y - r, 2 * r, 2 * r))
            try:          # the guides — a failure never takes the label
                for A in (d or {}).get("anchors") or ():  # a corner's guides
                    self._guide(painter, A, grips[0].p)
                if d is not None and d.get("anchor") is not None:
                    g, k = grips[0], d.get("off") or 0.0
                    self._guide(painter, d["anchor"],
                                (g.p[0] + g.axis[0] * k,
                                 g.p[1] + g.axis[1] * k,
                                 g.p[2] + g.axis[2] * k))
            except Exception:  # noqa: BLE001
                from . import compat
                compat.log_error("grips guide")
            if d is not None:
                g = grips[0]
                q = self._px(*g.p)
                if q:
                    text = self._typed + "_" if self._typed else \
                        label(d["g"], d["v"])
                    if d["why"]:
                        text += f"  ·  {d['why']}"
                    elif d.get("stuck") and not self._typed:
                        text += "  ·  joins" if d.get("onpoint") else (
                            "  ·  lined up" if (d.get("anchor")
                                                or d.get("anchors"))
                            else "  ·  joins")
                    if d.get("lock") and not self._typed:
                        text += {"z": "  ·  up / down (↑)",
                                 "x": "  ·  locked (→)",
                                 "y": "  ·  locked (←)"}[d["lock"]]
                    elif d["g"].extra.get("z") and not self._typed:
                        text += "  ·  ↑ = up / down"
                    f = QFont(painter.font())
                    f.setPointSizeF(9.5)
                    f.setBold(True)
                    painter.setFont(f)
                    fm = painter.fontMetrics()
                    wpx = fm.horizontalAdvance(text) + 12
                    box = QRectF(q[0] + 12, q[1] - 26, wpx, 20)
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(30, 34, 40, 225))
                    painter.drawRoundedRect(box, 4, 4)
                    painter.setPen(QColor("#ffb27a" if d["why"] else "#ffffff"))
                    painter.drawText(box, Qt.AlignCenter, text)
        except Exception:  # noqa: BLE001 — never break the host's paint
            pass
        painter.restore()

    def _guide(self, painter, anchor, p) -> None:
        """The temporary alignment guide: dashed, from what it lines up
        with to the grip, a small diamond on that point."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen, QPolygonF
        a, b = self._px(*anchor), self._px(*p)
        if not a or not b:
            return
        ink = QColor(GUIDE)
        pen = QPen(ink, 1.6, Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(*a), QPointF(*b))
        painter.setPen(Qt.NoPen)
        painter.setBrush(ink)
        r = 4.5
        painter.drawPolygon(QPolygonF([
            QPointF(a[0], a[1] - r), QPointF(a[0] + r, a[1]),
            QPointF(a[0], a[1] + r), QPointF(a[0] - r, a[1])]))

    def _arrow(self, painter, g, x, y, ink, hot) -> None:
        """A move across: a short double arrow along its axis."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPen, QPolygonF
        q = self._px(g.p[0] + g.axis[0] * 0.1, g.p[1] + g.axis[1] * 0.1,
                     g.p[2] + g.axis[2] * 0.1)
        if not q:
            return
        dx, dy = q[0] - x, q[1] - y
        L = math.hypot(dx, dy) or 1.0
        ex, ey = dx / L, dy / L
        nx, ny = -ey, ex
        arm = 13 if hot else 11
        head = 6 if hot else 5
        painter.setPen(QPen(ink, 3.0 if hot else 2.4, Qt.SolidLine,
                            Qt.RoundCap))
        painter.drawLine(QPointF(x - ex * arm, y - ey * arm),
                         QPointF(x + ex * arm, y + ey * arm))
        painter.setPen(Qt.NoPen)
        painter.setBrush(ink)
        for s in (1, -1):
            tx, ty = x + s * ex * (arm + head), y + s * ey * (arm + head)
            bx, by = x + s * ex * arm, y + s * ey * arm
            painter.drawPolygon(QPolygonF([
                QPointF(tx, ty), QPointF(bx + nx * head, by + ny * head),
                QPointF(bx - nx * head, by - ny * head)]))


def label(g: Grip, v) -> str:
    if g.mode == "point":
        if len(v) > 2 and v[2]:
            return f"{v[2]:+.2f} m ↑"
        return f"{math.hypot(*v):.2f} m"
    if g.mode == "move":
        return f"{v:+.2f} m"
    return f"{v:.2f} m"
