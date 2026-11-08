# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""PROFILES that run along a path — Tools ▸ Along a path ▸ Profile along
(PLANO_TOOLS_CAMINHO.md, his OK 2026-10-29). Pure data, no Qt: the library
draws the cards from it, the model checks the records against it, and
``along.py`` (Pro) sweeps them.

A profile is a closed outline in its own plane, metres:

    u   out from the path (0 = on the line drawn — a wall's face)
    v   up from where it is anchored (0 = its foot)

listed counter-clockwise. Where it is anchored (``ANCHORS``): on the
FLOOR (a baseboard), under the CEILING (a crown: its top 1 mm under the
slab above), or at a HEIGHT over the floor (a chair rail, a cornice).
"""
from __future__ import annotations

import math

#: a moulding's white / a façade's light stone — each its own material
WHITE = (0.96, 0.96, 0.95, 1.0)
STONE = (0.86, 0.84, 0.80, 1.0)

ANCHORS = (("floor", "Floor"), ("ceiling", "Ceiling"), ("height", "Height"),
           ("top", "Wall top"))
HOWS = (("points", "Point by point"), ("line", "On a line"),
        ("circle", "Circle"), ("rect", "Rectangle"),
        ("room", "By room"), ("face", "By wall face"),
        ("element", "By element"))
#: copies: not round a column (part 5)
COPY_HOWS = (("points", "Point by point"), ("line", "On a line"),
             ("room", "By room"), ("face", "By wall face"))
#: these make their own path: where it sits comes from the clicks / the line
FREE_HOWS = ("points", "line", "circle", "rect")
#: continuous, or pieces this long with a gap between (part 5, P5b)
RUNS = (("continuous", "Continuous"), ("repeat", "Repeat"))
#: where its own line runs on it (a path of its own: points, a line)
HALIGNS = (("outside", "Outside"), ("centre", "Centre"), ("inside", "Inside"))
VALIGNS = (("top", "Top"), ("middle", "Middle"), ("bottom", "Bottom"))

#: the options of the TOOL (how the next one is made), never a profile's
TOOL_KEYS = ("how",)
#: the next one made (ui's ``profile_opts``)
DEFAULT_OPTS = {"how": "room", "profile": "base_flat", "anchor": "floor",
                "z": 0.90, "off": 0.001, "cut": True, "run": "continuous",
                "piece": 0.60, "gap": 0.30, "halign": "outside",
                "valign": "bottom"}


def _arc(cx, cy, r, a0, a1, n=8) -> list:
    """``n`` steps of a circle's arc, from angle a0 to a1 (degrees) — its
    first point left out (the outline has it already)."""
    out = []
    for k in range(1, n + 1):
        a = math.radians(a0 + (a1 - a0) * k / n)
        out.append((round(cx + r * math.cos(a), 5),
                    round(cy + r * math.sin(a), 5)))
    return out


def _ogee(u0, u1, h, n=10) -> list:
    """An S curve from (u0, 0) up to (u1, h) — its first point left out."""
    return [(round(u0 + (u1 - u0) * (0.5 - 0.5 * math.cos(math.pi * k / n)),
                   5), round(h * k / n, 5)) for k in range(1, n + 1)]


def _base_mould() -> list:
    # a 12 cm baseboard, its top rounded into the wall
    return [(0.0, 0.0), (0.018, 0.0), (0.018, 0.090)] + \
        _arc(0.0, 0.090, 0.018, 0.0, 90.0, 6)          # up to (0, 0.108)


def _crown_cove() -> list:
    # a 10 × 10 cm cove: concave from the room
    return [(0.0, 0.0), (0.012, 0.0)] + _arc(0.100, 0.0, 0.088, 180.0, 90.0,
                                             10) + [(0.100, 0.100),
                                                    (0.0, 0.100)]


def _crown_ogee() -> list:
    return [(0.0, 0.0), (0.014, 0.0)] + _ogee(0.014, 0.110, 0.110) + \
        [(0.110, 0.122), (0.0, 0.122)]


def _chair_rail() -> list:
    # a 6 cm rail, its face rounded out
    pts = [(0.0, 0.0), (0.008, 0.0)]
    for k in range(1, 10):
        t = k / 10
        pts.append((round(0.008 + 0.014 * math.sin(math.pi * t), 5),
                    round(0.060 * t, 5)))
    return pts + [(0.008, 0.060), (0.0, 0.060)]


#: key → (label, colour, outline, the anchor it comes with, its height when
#: at a height, a tip)
NATIVE = {
    "base_flat": ("Baseboard — straight", WHITE,
                  [(0.0, 0.0), (0.015, 0.0), (0.015, 0.10), (0.0, 0.10)],
                  "floor", 0.0, "A plain 10 cm baseboard"),
    "base_mould": ("Baseboard — moulded", WHITE, None, "floor", 0.0,
                   "A 12 cm baseboard, its top rounded"),
    "crown_cove": ("Crown — cove", WHITE, None, "ceiling", 0.0,
                   "A 10 cm cove where the wall meets the ceiling"),
    "crown_ogee": ("Crown — ogee", WHITE, None, "ceiling", 0.0,
                   "A 12 cm S-curved crown"),
    "chair_rail": ("Chair rail", WHITE, None, "height", 0.90,
                   "A rail along the wall, 90 cm up"),
    "cornice": ("Cornice — façade", STONE,
                [(0.0, 0.0), (0.04, 0.0), (0.04, 0.06), (0.10, 0.06),
                 (0.10, 0.12), (0.18, 0.12), (0.18, 0.20), (0.0, 0.20)],
                "height", 2.80, "A stepped cornice on the outside wall"),
    "band": ("Band / drip", STONE,
             [(0.0, 0.0), (0.06, 0.0), (0.06, 0.045), (0.0, 0.06)],
             "height", 0.95, "A band round the façade, its top sloping out"),
}
_MADE = {"base_mould": _base_mould, "crown_cove": _crown_cove,
         "crown_ogee": _crown_ogee, "chair_rail": _chair_rail}
try:
    from . import mouldings as _MOULD    # the big library (the Lite has none)
    NATIVE.update(_MOULD.natives(WHITE, STONE))
except ImportError:
    _MOULD = None


def free_standing(key: str) -> bool:
    """A section with no wall behind it (a handrail): its card shows none."""
    return bool(_MOULD) and _MOULD.free_standing(key)


#: a column's base and capital (column_orders.py, Pro): the keys both editions
#: keep; "none": a plain shaft
COLUMN_BASES = ("none", "plinth", "tuscan", "doric", "attic", "stepped",
                "pedestal")
COLUMN_CAPS = ("none", "slab", "tuscan", "doric", "empire", "stepped")


# ---- COPY ALONG (D7): the objects copied along a path — the data both
# editions read (the model checks the records); ``copies.py`` (Pro) builds
#: key → (label, tip)
COPY_OBJECTS = {
    "bollard": ("Bollard", "A 90 cm bollard — a path's edge, a car stop"),
    "lamp": ("Garden lamp", "A 3.7 m lamp post — a street, a drive"),
    "tree": ("Tree", "A simple tree, 4.7 m — along a street, a wall"),
    "planter": ("Planter", "A 60 cm concrete planter with its plant"),
    "post": ("Fence post", "A 12 × 12 cm post, 1.2 m — a fence: «Gap»"),
}
#: the copy taken from an object selected in the model
COPY_MINE = "mine"
COPY_MODES = (("path", "Whole path"), ("segment", "Each segment"),
              ("corners", "Corners only"))
COPY_BY = (("count", "Count"), ("spacing", "Spacing"), ("gap", "Gap"))
COPY_TURN = (("follow", "Follows the path"), ("fixed", "Fixed"))
COPY_TOOL_KEYS = ("how",)
COPY_DEFAULT = {"how": "points", "obj": "bollard", "mode": "path",
                "by": "spacing", "count": 5, "spacing": 2.0, "gap": 0.10,
                "ends": True, "turn": "follow", "rot": 0.0, "off": 0.0,
                "base": 0.0, "cut": True, "src": None}

#: YOUR profiles (D6 — made from a face drawn in IngeTrazo), key «u_…» →
#: {"id", "name", "cat", "pts"}: the project's copy (``doc["profile_types"]``)
#: and the user's library (every project of this computer) — ``add``
USER: dict = {}
#: their categories (the favourites' window's) → the anchor they come with
CATS = (("base", "Baseboards"), ("crown", "Crowns"), ("wall", "Wall & façade"))
CAT_ANCHOR = {"base": ("floor", 0.0), "crown": ("ceiling", 0.0),
              "wall": ("height", 0.90)}
LIB_KEY = "archxq/profiles"
MIN_SIZE = 0.005        # m: smaller, no profile (a face drawn by mistake)
MAX_SIZE = 2.0          # m: larger, drawn in the wrong unit
MAX_PTS = 400


def is_user(key) -> bool:
    return isinstance(key, str) and key.startswith("u_")


def known(key) -> bool:
    return key in NATIVE or key in USER


def clean_user(raw) -> list:
    """YOUR profiles, whatever a file holds: a «u_» id, a name, a category,
    an outline that is a profile (``check``) — kept counter-clockwise from
    (0, 0)."""
    out, ids = [], set()
    for t in raw if isinstance(raw, list) else []:
        if not isinstance(t, dict) or not is_user(t.get("id")) \
                or t["id"] in ids:
            continue
        try:
            pts = [(float(p[0]), float(p[1])) for p in t.get("pts") or []]
        except (TypeError, ValueError, IndexError):
            continue
        if check(pts) is not None:
            continue
        ids.add(t["id"])
        out.append({"id": str(t["id"])[:16],
                    "name": str(t.get("name") or "Profile")[:40],
                    "cat": t.get("cat") if t.get("cat") in CAT_ANCHOR
                    else "base",
                    "pts": [[round(u, 5), round(v, 5)]
                            for u, v in _ccw(pts)]})
    return out


def add(types) -> None:
    """These profiles known (a document's, the library's) — never dropped:
    a profile still in a record keeps drawing."""
    for t in types or ():
        USER[t["id"]] = t


def _get(key):
    return NATIVE.get(key) or NATIVE["base_flat"]


def outline(key: str) -> list:
    """The profile's outline (counter-clockwise; u out, v up) — the
    straight baseboard for a key unknown."""
    if key in USER:
        return _ccw(USER[key]["pts"])
    got = _get(key)
    pts = got[2] if got[2] is not None else _MADE[key]()
    return _ccw(pts)


def _ccw(pts) -> list:
    out = []
    for p in pts:                           # (no point twice in a row)
        if not out or math.dist(out[-1], p) > 1e-6:
            out.append(tuple(p))
    if len(out) > 2 and math.dist(out[0], out[-1]) < 1e-6:
        out.pop()
    if _area(out) < 0:
        out.reverse()
    return out


def _area(pts) -> float:
    return 0.5 * sum(p[0] * q[1] - q[0] * p[1]
                     for p, q in zip(pts, list(pts[1:]) + [pts[0]]))


def size(key: str) -> tuple:
    """(depth out of the wall, height) of a profile."""
    pts = outline(key)
    return max(p[0] for p in pts), max(p[1] for p in pts)


def color(key: str) -> tuple:
    if key in USER:
        return STONE if USER[key]["cat"] == "wall" else WHITE
    return _get(key)[1]


def label(key: str) -> str:
    if key in USER:
        return USER[key]["name"]
    return _get(key)[0]


def anchor_of(key: str) -> tuple:
    """(anchor, height) a profile comes with."""
    if key in USER:
        return CAT_ANCHOR[USER[key]["cat"]]
    got = _get(key)
    return got[3], got[4]


# ---- YOUR profile, from a face drawn in IngeTrazo (D6) ------------------------------------
def from_face(loop, normal) -> list:
    """A flat face (its points in 3D, its normal) → its outline in its own
    plane, metres from its lower left corner: v up the face (a face on the
    floor: u along x, v along y, as the plan shows it), u to the right
    seen from the front."""
    nx, ny, nz = normal
    n = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    nx, ny, nz = nx / n, ny / n, nz / n
    if abs(nz) > 0.95:                       # lying flat: as the plan shows
        U, V = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
    else:                                    # up the face, and its right
        ux, uy, uz = -nz * nx, -nz * ny, 1.0 - nz * nz
        k = math.sqrt(ux * ux + uy * uy + uz * uz)
        V = (ux / k, uy / k, uz / k)
        U = (V[1] * nz - V[2] * ny, V[2] * nx - V[0] * nz,
             V[0] * ny - V[1] * nx)
    pts = [(p[0] * U[0] + p[1] * U[1] + p[2] * U[2],
            p[0] * V[0] + p[1] * V[1] + p[2] * V[2]) for p in loop]
    return _simple(pts)


def _simple(pts) -> list:
    """No point twice, none on a straight run; from (0, 0); CCW."""
    out = []
    for p in pts:
        if not out or math.dist(out[-1], p) > 0.0005:
            out.append(tuple(p))
    while len(out) > 2 and math.dist(out[0], out[-1]) <= 0.0005:
        out.pop()
    k = 0
    while len(out) > 3 and k < len(out):
        a, b, c = out[k - 1], out[k], out[(k + 1) % len(out)]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cross) < 1e-9:
            out.pop(k)
        else:
            k += 1
    if not out:
        return []
    u0 = min(p[0] for p in out)
    v0 = min(p[1] for p in out)
    return _ccw([(round(u - u0, 5), round(v - v0, 5)) for u, v in out])


def check(pts) -> str | None:
    """Why that outline is no profile — None: it is one."""
    if len(pts) < 3:
        return "Not a closed outline — draw a face with 3 sides at least"
    if len(pts) > MAX_PTS:
        return f"Too many points for a profile (over {MAX_PTS})"
    try:
        from shapely.geometry import Polygon
        if not Polygon(pts).is_valid:
            return "Its outline crosses itself"
    except ImportError:
        pass
    d = max(p[0] for p in pts) - min(p[0] for p in pts)
    h = max(p[1] for p in pts) - min(p[1] for p in pts)
    if min(d, h) < MIN_SIZE:
        return "Too small for a profile (under 5 mm)"
    if max(d, h) > MAX_SIZE:
        return "Too large for a profile (over 2 m) — drawn in another unit?"
    return None


def wall_side(pts) -> str:
    """Where the wall most likely is: the side the outline is tallest on (a
    baseboard's back is its full height) — «left» / «right»."""
    d = max(p[0] for p in pts)

    def tall(near) -> float:
        vs = [p[1] for p in pts if near(p[0])]
        return max(vs) - min(vs) if vs else 0.0
    return "right" if tall(lambda u: u >= d * 0.9) > tall(
        lambda u: u <= d * 0.1) + 1e-6 else "left"


def fit(pts, wall: str = "left") -> list:
    """The outline with the wall at u = 0: one drawn with the wall on its
    right is mirrored."""
    if wall == "right":
        d = max(p[0] for p in pts)
        pts = [(round(d - u, 5), v) for u, v in pts]
    return _ccw(pts)


# ---- YOUR library (every project of this computer) -----------------------------------------
def lib_load() -> list:
    try:
        import json
        from PySide6.QtCore import QSettings
        raw = QSettings().value(LIB_KEY, "")
        return clean_user(json.loads(raw)) if raw else []
    except Exception:  # noqa: BLE001 — none kept: the project's still work
        return []


def lib_save(types: list) -> None:
    try:
        import json
        from PySide6.QtCore import QSettings
        QSettings().setValue(LIB_KEY, json.dumps(types))
    except Exception:  # noqa: BLE001 — not kept: the project has its copy
        pass
