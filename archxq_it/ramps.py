"""RAMPS — the first «Building element» (his ask, 2026-10-05; plan in
PLANO_RAMPA_ESCADA.md, mockup C): a sloped concrete slab from one level —
or from the ground — down (or up) to another level or an elevation.

A ramp is one more type in ``doc["structure"]`` (``type="ramp"``): its
level, the Outliner, delete / Ctrl+Z, the «built» bookkeeping and the
double-click come with that for free. This module holds what is its own:

- the numbers: where it starts and ends (heights), how long it runs;
- its faces (``faces``), for ``structure.build``;
- its window (``RampDialog``): to set it up before drawing, and to edit one;
- its tool (``RampTool``): click where it starts, click the way it goes.

The record:
    type "ramp", level (the «From» level — the ground floor when it starts
    on the terrain), start "level" | "terrain", to (a level id) | "z" with
    to_z, x / y (the middle of its top edge), angle (° from the red axis,
    the way it runs), w, slope (%), t, shape "straight".
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import compat
from .plottools import ACCENT, _PlotTool

COLOR = (0.74, 0.74, 0.73)       # concrete, as the slabs
#: «fix»: which of the two is given — the slope (the length follows) or,
#: for special cases, the length (the slope follows; his ask, 2026-10-05)
#: «shape»: straight | L | U — «turn» right | left, «landing» its length
DEFAULT = {"start": "level", "to": "", "to_z": -3.0, "w": 3.0,
           "slope": 20.0, "fix": "slope", "L": 15.0, "t": 0.15,
           "shape": "straight", "turn": "right", "landing": 3.0,
           "anchor": "centre", "build": "slab",
           "cut": True}            # its opening in the slab (False: none)
SLOPE_MIN, SLOPE_MAX = 1.0, 50.0  # % (a car ramp ~20, people ~8)


# ---- the numbers ----------------------------------------------------------------------
def level_z(doc: dict, elevations) -> dict:
    """{level id: its floor's elevation}."""
    ground = doc["project"]["ground_level"] if doc.get("project") else 0.0
    elev = elevations(doc["levels"], ground)
    return {lv["id"]: elev[i] for i, lv in enumerate(doc["levels"])}


TOP = "top:"            # «to» = the top of a level (its floor + height)


def end_z(doc: dict, elevations, end) -> float | None:
    """The elevation of an end: a level's floor, or «top:<id>» — the top
    of that level (the highest one's: a stair up inside it, with no level
    over it yet — his ask, 2026-10-05). None for anything else."""
    zs_of = level_z(doc, elevations)
    if end in zs_of:
        return zs_of[end]
    if isinstance(end, str) and end.startswith(TOP):
        lid = end[len(TOP):]
        lv = next((x for x in doc["levels"] if x["id"] == lid), None)
        if lv is not None:
            return zs_of[lid] + float(lv["height"])
    return None


def from_level(r: dict):
    """The level it starts on — «from» (since 2026-10-05: «level» is the
    level it BELONGS to, the lower one); older records: «level»."""
    return r.get("from") or r.get("level")


def level_under(zs_of: dict, z: float):
    """The level an ELEVATION belongs to: the highest whose floor is at it
    or under it (1 cm), else the lowest — the storey whose space it is."""
    under = [(zl, lid) for lid, zl in zs_of.items() if zl <= z + 0.01]
    if under:
        return max(under)[1]
    return min((zl, lid) for lid, zl in zs_of.items())[1]


def owner(r: dict, doc: dict, elevations):
    """The level a ramp / stair belongs to: the LOWER of its two levels —
    the storey whose space it takes, drawn going up or down (his test,
    2026-10-05: a stair drawn down from Basement 1 sat in Basement 2's
    space but was listed under Basement 1). The start on the terrain: the
    ground floor; an elevation at its end: the level it starts on."""
    zs_of = level_z(doc, elevations)
    if r.get("start") == "z":         # «By heights»: two elevations
        zs, ze = heights(r, doc, elevations)
        return level_under(zs_of, min(zs, ze))
    a = from_level(r)
    if r.get("start") == "terrain":
        a = next((lv["id"] for lv in doc["levels"] if lv["kind"] == "ground"),
                 a)
    b = r.get("to")

    def base(end):                    # a level's top → that level
        return end[len(TOP):] if isinstance(end, str) and \
            end.startswith(TOP) else end
    za, zb = end_z(doc, elevations, a), end_z(doc, elevations, b)
    if za is None or zb is None:
        return base(a)
    return base(a) if za <= zb else base(b)


def heights(r: dict, doc: dict, elevations, at=None) -> tuple[float, float]:
    """(where it starts, where it ends) — the start on the ground is the
    ground's height under its start (``at``: another start, for a preview)."""
    zs_of = level_z(doc, elevations)
    if r.get("start") == "terrain" and doc.get("plot"):
        from .terrain import ground_at
        p = at if at is not None else (float(r["x"]), float(r["y"]))
        zs = ground_at(doc["plot"], p)
    elif r.get("start") == "z":       # «By heights» (2026-10-18): typed
        zs = float(r.get("from_z", 0.0))
    else:
        zs = end_z(doc, elevations, from_level(r))
        if zs is None:
            zs = 0.0
    ze = end_z(doc, elevations, r.get("to"))
    if ze is None:
        ze = float(r.get("to_z", 0.0))
    return zs, ze


def run_length(zs: float, ze: float, slope: float) -> float:
    """How long it runs (plan) for that drop at that slope."""
    return abs(zs - ze) / (max(float(slope), 0.01) / 100.0)


def length_of(r: dict, zs: float, ze: float) -> float:
    """Its length: the one given (``fix`` "length"), else from the slope."""
    if r.get("fix") == "length":
        return float(r.get("L", 0.0))
    return run_length(zs, ze, r["slope"])


def slope_of(r: dict, zs: float, ze: float) -> float:
    """Its slope (%): the one given, else from the length given."""
    if r.get("fix") == "length":
        return abs(zs - ze) / max(float(r.get("L", 0.0)), 0.01) * 100.0
    return float(r["slope"])


#: where the click is on the first step's (top) edge, walking it: its left
#: corner, its middle, its right corner (his ask, 2026-10-05: stairs
#: stacked in a shaft — a corner sits in the shaft's corner)
ANCHORS = (("left", "Left corner"), ("centre", "Middle"),
           ("right", "Right corner"))


def axes(r: dict):
    """(start — the MIDDLE of its first edge, u along, n across to its
    right) in plan; (x, y) is where it was clicked (``anchor``)."""
    a = math.radians(float(r.get("angle", 0.0)))
    u = (math.cos(a), math.sin(a))
    n = (u[1], -u[0])                 # (n, u, z) is right-handed
    x, y = float(r["x"]), float(r["y"])
    k = {"left": 0.5, "right": -0.5}.get(r.get("anchor"), 0.0) \
        * float(r.get("w", 0.0))
    return (x + n[0] * k, y + n[1] * k), u, n


def pieces(r: dict, zs: float, ze: float, L: float, l1=None, l2=None,
           zm=None) -> list[dict]:
    """The ramp as plan pieces: its sloped runs and (L / U) the level
    landing between them. Each {"c": the middle of its start edge, "d": the
    way it runs, "l": length, "w": width, "z0" / "z1": its top at the start
    / end, "run": True for a run}. ``L`` = the sloped runs together (the
    landing apart); the drop is split evenly between the two runs — unless
    ``l1`` / ``l2`` / ``zm`` say otherwise (a stair's runs, stairs.py)."""
    (sx, sy), u, n = axes(r)
    w = float(r["w"])
    shape = r.get("shape", "straight")
    sg = -1.0 if r.get("turn") == "left" else 1.0      # right = +n

    def P(s, a):                      # s along, a across (to the right)
        return (sx + u[0] * s + n[0] * a, sy + u[1] * s + n[1] * a)
    if shape not in ("L", "U"):
        return [{"c": P(0, 0), "d": u, "l": L, "w": w, "z0": zs, "z1": ze,
                 "run": True}]
    l1 = L / 2 if l1 is None else l1
    l2 = L / 2 if l2 is None else l2
    zm = (zs + ze) / 2 if zm is None else zm
    run1 = {"c": P(0, 0), "d": u, "l": l1, "w": w, "z0": zs, "z1": zm,
            "run": True}
    if shape == "L":
        # the landing as long as the ramp is wide at least: the second run
        # leaves from its side, turned 90°
        ld = max(float(r.get("landing", 3.0)), w)
        return [run1,
                {"c": P(l1, 0), "d": u, "l": ld, "w": w, "z0": zm, "z1": zm,
                 "run": False},
                {"c": P(l1 + ld - w / 2, sg * w / 2), "d": (n[0] * sg,
                                                            n[1] * sg),
                 "l": l2, "w": w, "z0": zm, "z1": ze, "run": True}]
    # U: the landing across both lanes, the second run back beside the first
    # — «gap» apart (a stair's well between its flights; 0: side by side)
    ld = max(float(r.get("landing", 3.0)), 0.5)
    gap = max(float(r.get("gap", 0.0) or 0.0), 0.0)
    return [run1,
            {"c": P(l1, sg * (w + gap) / 2), "d": u, "l": ld,
             "w": 2 * w + gap, "z0": zm, "z1": zm, "run": False},
            {"c": P(l1, sg * (w + gap)), "d": (-u[0], -u[1]), "l": l2,
             "w": w, "z0": zm, "z1": ze, "run": True}]


def piece_corners(p: dict) -> list:
    """A piece's four corners in plan, counter-clockwise."""
    (cx, cy), (dx, dy) = p["c"], p["d"]
    rx, ry = dy, -dx                  # its right
    h, l = p["w"] / 2, p["l"]
    pts = [(cx + rx * h, cy + ry * h), (cx + rx * h + dx * l, cy + ry * h + dy * l),
           (cx - rx * h + dx * l, cy - ry * h + dy * l), (cx - rx * h, cy - ry * h)]
    a = sum(p_[0] * q[1] - q[0] * p_[1] for p_, q in zip(pts, pts[1:] + pts[:1]))
    return pts if a > 0 else list(reversed(pts))


def top_piece(r: dict, ps: list, zs: float, ze: float) -> dict | None:
    """Its LANDING AT THE TOP (his idea, 2026-10-18 — a shop's entrance
    steps end on a platform): a level piece ``top_landing`` long at its top
    elevation — going up, past its last run's end; going down, behind its
    first run's start (the click does not move). None: no landing. Kept OUT
    of ``pieces`` (the middle landing's grips, the slab's cut and the guards
    read those): only its build, plan, outline and grip use it."""
    try:
        ln = float(r.get("top_landing", 0.0) or 0.0)
    except (TypeError, ValueError):
        return None
    runs = [p for p in ps if p.get("run", True)]
    if ln < 0.01 or not runs:
        return None
    z = max(zs, ze)
    if ze >= zs:                          # up: the last run's end
        p = runs[-1]
        (cx, cy), (dx, dy) = p["c"], p["d"]
        c = (cx + dx * p["l"], cy + dy * p["l"])
    else:                                 # down: behind the first run
        p = runs[0]
        (cx, cy), (dx, dy) = p["c"], p["d"]
        c = (cx - dx * ln, cy - dy * ln)
    return {"c": c, "d": (dx, dy), "l": ln, "w": p["w"], "z0": z, "z1": z,
            "run": False, "top": True}


def footprints(r: dict, zs: float, ze: float, L: float) -> list:
    """Every piece's outline in plan (what the slab above loses) — its
    landing at the top too (``top_piece``)."""
    ps = pieces(r, zs, ze, L)
    tp = top_piece(r, ps, zs, ze)
    return [piece_corners(p) for p in ps + ([tp] if tp else [])]


def footprint(r: dict, L: float) -> list:
    """The first run's outline (kept for the straight case's callers)."""
    return piece_corners(pieces(r, 0.0, -1.0, L)[0])


def why_not(r: dict) -> str | None:
    try:
        if float(r["w"]) < 0.5:
            return "A ramp needs 50 cm of width at least"
        if r.get("fix") == "length":
            if float(r.get("L", 0.0)) < 0.5:
                return "A ramp needs 50 cm of length at least"
        elif not SLOPE_MIN <= float(r["slope"]) <= SLOPE_MAX:
            return f"A ramp's slope goes from {SLOPE_MIN:g} to {SLOPE_MAX:g} %"
        if float(r["t"]) < 0.05:
            return "A ramp needs a thickness of 5 cm at least"
        float(r["x"]), float(r["y"])
    except (KeyError, TypeError, ValueError):
        return "Incomplete ramp"
    return None


def faces(r: dict, doc: dict, elevations) -> list:
    """The ramp as sloped slabs (and a level landing): each piece's side
    profile (along, z) swept across its width. Empty when it has no drop
    (nothing to ramp)."""
    from .structure import _sweep
    zs, ze = heights(r, doc, elevations)
    L = length_of(r, zs, ze)
    if L < 0.1 or abs(zs - ze) < 0.01:
        return []
    t = float(r["t"])
    out = []
    ps = pieces(r, zs, ze, L)
    try:
        from . import railings as RL       # its guards (Pro only)
    except ImportError:
        RL = None
    # a low wall keeps to the ramp's edge: the slab gives way 1 cm there
    lt, rt = RL.body_trim(r, ps, ze > zs, False, doc)[:2] if RL else (0, 0)
    walls = RL.wall_plan(r, ps, ze > zs, False, doc) if RL else None
    # SOLID (his ask, 2026-10-18): filled down to the lower floor, 1 mm
    # over it — a wedge, not a sloped slab
    solid = r.get("build") == "solid"
    zf = min(zs, ze) + 0.001
    # (its landing at the top, built as the middle one — ``top_piece``)
    tp = top_piece(r, ps, zs, ze)
    for p in ps + ([tp] if tp else []):
        (cx, cy), (dx, dy) = p["c"], p["d"]
        rx, ry = dy, -dx

        def P(x, y, z, cx=cx, cy=cy, dx=dx, dy=dy, rx=rx, ry=ry):
            return (cx + rx * x + dx * y, cy + ry * x + dy * y, z)
        # its top 1 mm under the floor it leaves: never the same plane
        # (black squares — the 1 mm rule)
        z0, z1, l = p["z0"] - 0.001, p["z1"] - 0.001, p["l"]
        b0 = zf if solid else z0 - t + 0.001
        b1 = zf if solid else z1 - t + 0.001
        if p.get("run", True):
            a0, a1 = -p["w"] / 2 + lt, p["w"] / 2 - rt
        elif walls is not None:           # a landing: it gives way to them
            from .stairs import landing_round
            out += landing_round(p, walls, b0, z0, COLOR + (1.0,))
            continue
        else:
            a0, a1 = -p["w"] / 2, p["w"] / 2
        if solid and min(z0, z1) - zf < 0.002:
            # the low end on the floor: a wedge, its thin edge on the floor
            prof = [(0.0, zf), (l, zf), (l, max(z1, zf + 0.002)),
                    (0.0, max(z0, zf + 0.002))]
        else:
            prof = [(0.0, b0), (l, b1), (l, z1), (0.0, z0)]
        out += _sweep(prof, a0, a1, P, COLOR + (1.0,))
    if RL is not None:
        out += RL.faces(r, ps, ze > zs, False, doc)
    return out


def through_levels(r: dict, doc: dict, elevations) -> set:
    """The levels whose slab the ramp goes through: the one it leaves and
    any in between — never the one it arrives on (it lands on that slab)."""
    zs, ze = heights(r, doc, elevations)
    lo, hi = min(zs, ze), max(zs, ze)
    return {lid for lid, z in level_z(doc, elevations).items()
            if lo + 0.01 < z <= hi + 0.01}


HOLE_CLEAR = 0.01        # m round a ramp in the slab it goes through


def cut_slab(outer, holes, polys) -> list | None:
    """The slab piece (outer + holes) less the ramps going through it —
    [{"outer", "holes"}] (it may fall into parts), or None (no shapely /
    nothing cut: the slab as it is)."""
    try:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
    except ImportError:
        return None
    base = Polygon(outer, holes)
    if not base.is_valid:
        base = base.buffer(0)
    cut = unary_union([Polygon(p).buffer(HOLE_CLEAR, join_style=2)
                       for p in polys])
    if not base.intersects(cut):
        return None
    res = base.difference(cut)

    def ccw(loop):
        a = sum(p[0] * q[1] - q[0] * p[1]
                for p, q in zip(loop, loop[1:] + loop[:1]))
        return list(loop) if a >= 0 else list(reversed(loop))
    out = []
    for g in getattr(res, "geoms", [res]):
        if g.is_empty or g.area < 0.01 or g.geom_type != "Polygon":
            continue
        out.append({"outer": ccw([tuple(c) for c in g.exterior.coords[:-1]]),
                    "holes": [list(reversed(ccw([tuple(c) for c in
                                                 i.coords[:-1]])))
                              for i in g.interiors]})
    return out


# ---- its window ------------------------------------------------------------------------
class _Ends:
    """«Top level» over «Bottom level», as a section reads, + «Starts at»
    (where the click is: the bottom step going up, or the top going down)
    — a ramp / stair defined from the bottom up, however it is drawn (his
    call, 2026-10-05: «From / To» followed the drawing and read upside
    down). Stored as before: start / from (the clicked end), to, to_z."""

    def __init__(self, doc: dict, elevations, rec: dict, form, metres,
                 choice=None):
        """``choice``: «Starts at» as chips (look.Chips — the windows of
        0.10.0) instead of a list."""
        self.doc, self.elevations = doc, elevations
        self.form = form
        zs_of = level_z(doc, elevations)
        # HOW its ends are given (his idea, 2026-10-18 — a shop's entrance
        # steps took three hidden rules): by levels (a level, the terrain, an
        # elevation), or by heights — two elevations, nothing else
        self.f_mode = (choice or QComboBox)()
        self.f_mode.addItem("By levels", "levels")
        self.f_mode.addItem("By heights", "heights")
        self.f_mode.setToolTip("By levels: its ends on levels, the terrain "
                               "or an elevation. By heights: just the two "
                               "elevations it goes between — it works out "
                               "the rest")
        self.f_top = QComboBox()
        if doc.get("plot"):
            self.f_top.addItem("The terrain (the ground at its top)",
                               "terrain")
        self.f_bottom = QComboBox()
        if doc.get("plot"):
            # the ground at its FOOT (2026-10-18): an entrance's steps from
            # the pavement — read where it is placed
            self.f_bottom.addItem("The terrain (the ground at its foot)",
                                  "terrain")
        # the highest level's top: a stair up inside it, no level over it
        hi = max(doc["levels"], key=lambda lv: zs_of[lv["id"]])
        self.f_top.addItem(f"Top of {hi['name']}  "
                           f"({compat.fmt_level(zs_of[hi['id']] + float(hi['height']), unit=False)})",  # noqa: E501
                           TOP + hi["id"])
        for box in (self.f_top, self.f_bottom):
            for lv in reversed(doc["levels"]):
                box.addItem(f"{lv['name']}  "
                            f"({compat.fmt_level(zs_of[lv['id']], unit=False)})",
                            lv["id"])
            box.addItem("An elevation", "z")
        self.f_z = metres(float(rec.get("to_z", -3.0)), -100.0, 100.0)
        self.f_start = (choice or QComboBox)()
        if choice is None:
            self.f_start.addItem("Bottom step — going up", "bottom")
            self.f_start.addItem("Top step — going down", "top")
        else:
            self.f_start.addItem("↑ Bottom step", "bottom")
            self.f_start.addItem("↓ Top step", "top")
        self.f_start.setToolTip("Where your click is on the plan: at its "
                                "bottom (the usual way) or at its top (a "
                                "ramp from the street, a slab's edge)")
        # where it is now: the clicked end is «from» (or the terrain)
        a = "terrain" if rec.get("start") == "terrain" else from_level(rec)
        b = rec.get("to") or "z"
        za = None if a == "terrain" else end_z(doc, elevations, a)
        zb = float(rec.get("to_z", 0.0)) if b == "z" else end_z(doc,
                                                               elevations, b)
        if a == "terrain" and doc.get("plot") and "x" in rec:
            # the ground where it is: under the other end → its foot
            try:
                from .terrain import ground_at
                za = ground_at(doc["plot"], (float(rec["x"]),
                                             float(rec["y"])))
            except Exception:  # noqa: BLE001 — as before: the top
                za = None
        top_first = (za is None and a == "terrain") or (
            za is not None and zb is not None and za >= zb)
        top, bottom = (a, b) if top_first else (b, a)
        self.f_top.setCurrentIndex(max(self.f_top.findData(top), 0))
        self.f_bottom.setCurrentIndex(max(self.f_bottom.findData(bottom), 0))
        self.f_start.setCurrentIndex(1 if top_first else 0)
        # «By heights»: the two elevations it has now
        try:
            z0, z1 = heights(dict(rec, x=rec.get("x", 0.0),
                                  y=rec.get("y", 0.0)), doc, elevations)
        except Exception:  # noqa: BLE001
            z0, z1 = 0.0, 1.0
        self.f_lo = metres(round(min(z0, z1), 3), -100.0, 100.0)
        self.f_hi = metres(round(max(z0, z1), 3), -100.0, 100.0)
        self.f_lo.setToolTip("Its foot: the elevation it starts from")
        self.f_hi.setToolTip("Its top: the elevation it reaches")
        if rec.get("start") == "z":
            self.f_mode.setCurrentIndex(1)
            self.f_start.setCurrentIndex(
                1 if float(rec.get("from_z", 0.0)) >= float(
                    rec.get("to_z", 0.0)) else 0)
        # what it climbs, in big: «1.10 m · 7 risers of 15.7 cm»
        self.f_note = QLabel("")
        self.f_note.setStyleSheet("color: #ffb36b; font-weight: bold; "
                                  "font-size: 13px;")
        # «From / To» as he reads them (2026-10-05): «To» — the upper end —
        # over «From» — the lower one — as a section reads
        self.f_top.setToolTip("The upper end: a level, the top of the "
                              "highest level, the terrain or an elevation")
        self.f_bottom.setToolTip("The lower end: a level, the terrain (the "
                                 "ground at its foot) or an elevation")
        form.addRow("Set by", self.f_mode)
        form.addRow("To", self.f_top)
        form.addRow("From", self.f_bottom)
        form.addRow("Elevation", self.f_z)
        form.addRow("Top at", self.f_hi)
        form.addRow("Bottom at", self.f_lo)
        form.addRow("Starts at", self.f_start)
        form.addRow("", self.f_note)

    def widgets(self):
        return (self.f_mode, self.f_top, self.f_bottom, self.f_start)

    def values(self):
        """Its typed fields (``valueChanged``)."""
        return (self.f_z, self.f_lo, self.f_hi)

    def by_heights(self) -> bool:
        return self.f_mode.currentData() == "heights"

    def note(self, text: str) -> None:
        """The window's line of what it climbs (shown By heights)."""
        self.f_note.setText(text)

    def _row(self, w, on: bool) -> None:
        try:
            self.form.setRowVisible(w, on)
        except (AttributeError, TypeError):   # an older Qt
            w.setVisible(on)
            lab = self.form.labelForField(w)
            if lab is not None:
                lab.setVisible(on)

    def sync(self) -> None:
        hts = self.by_heights()
        for w in (self.f_top, self.f_bottom, self.f_z):
            self._row(w, not hts)
        for w in (self.f_hi, self.f_lo, self.f_note):
            self._row(w, hts)
        if hts:                           # either end may be the clicked one
            self.f_start.setEnabled(True)
            return
        top, bot = self.f_top.currentData(), self.f_bottom.currentData()
        self.f_z.setEnabled("z" in (top, bot))
        if top == "terrain":              # the ground is read at the click
            self.f_start.setCurrentIndex(1)
        elif bot == "terrain":            # …its foot: the bottom step
            self.f_start.setCurrentIndex(0)
        self.f_start.setEnabled("terrain" not in (top, bot))

    def write(self, r: dict) -> None:
        """Its ends into the record (start, from, to, to_z — By heights:
        start «z», from_z, to «z», to_z) — a top chosen lower than the
        bottom is turned the right way round."""
        if self.by_heights():
            lo, hi = sorted((round(self.f_lo.value(), 3),
                             round(self.f_hi.value(), 3)))
            at_top = self.f_start.currentData() == "top"
            r["start"] = "z"
            r["from_z"], r["to_z"] = (hi, lo) if at_top else (lo, hi)
            r["to"] = "z"
            r["from"] = level_under(level_z(self.doc, self.elevations), lo)
            return
        r.pop("from_z", None)
        top, bot = self.f_top.currentData(), self.f_bottom.currentData()
        zs_of = level_z(self.doc, self.elevations)
        zt = end_z(self.doc, self.elevations, top)
        zb = end_z(self.doc, self.elevations, bot)
        if zt is not None and zb is not None and zt < zb and \
                not str(top).startswith(TOP):
            top, bot = bot, top
        at_top = top == "terrain" or (bot != "terrain" and
                                      self.f_start.currentData() == "top")
        start, other = (top, bot) if at_top else (bot, top)
        ground = next(lv["id"] for lv in self.doc["levels"]
                      if lv["kind"] == "ground")
        if start == "terrain":
            r["start"], r["from"] = "terrain", ground
        else:
            r["start"] = "level"
            r["from"] = start if (start in zs_of or str(start).startswith(
                TOP)) else ground
        r["to"] = other
        r["to_z"] = round(self.f_z.value(), 3)

    def why_not(self) -> str | None:
        if self.by_heights():
            if abs(self.f_hi.value() - self.f_lo.value()) < 0.05:
                return "The top and the bottom are at the same height"
            return None
        top, bot = self.f_top.currentData(), self.f_bottom.currentData()
        if top == bot:
            return ("The top and the bottom are both the terrain"
                    if top == "terrain" else
                    "The top and the bottom are the same level")
        at_top = top == "terrain" or (bot != "terrain" and
                                      self.f_start.currentData() == "top")
        if (top if at_top else bot) == "z":
            return ("It starts on a level (or the terrain) — an elevation "
                    "can only be its other end")
        return None


def _pic_anchor(k):
    """«Insert at» as a picture: the flight, the click's dot on its first
    edge."""
    def draw(p, r, _on):
        from . import look as L
        L.poly(p, [(20, 4), (40, 4), (40, 40), (20, 40)], L.INK, 1.5, close=True)
        p.setPen(L.pen(L.DIM, 1.0))
        from PySide6.QtCore import QPointF
        for y in (12, 20, 28):
            p.drawLine(QPointF(20, y), QPointF(40, y))
        x = {"left": 20, "centre": 30, "right": 40}[k]
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(L.ACCENT))
        p.drawEllipse(QPointF(x, 40), 4, 4)
    return draw


def _anchor_box(rec: dict, chips: bool = False) -> QComboBox:
    """«Insert at»: where the click is on its first edge (stairs.py too) —
    ``chips``: pictures (the windows of 0.10.0)."""
    if chips:
        from . import look as L
        box = L.Chips()
        for k, text in ANCHORS:
            box.addItem(text, k, pic=_pic_anchor(k))
    else:
        box = QComboBox()
        for k, text in ANCHORS:
            box.addItem(text, k)
    box.setCurrentIndex(max(box.findData(rec.get("anchor", "centre")), 0))
    box.setToolTip("Where the click sits on its first edge, walking it: a "
                   "corner puts it in a corner (a stair shaft, a wall's end)")
    return box


def _repeat_button(dlg, noun: str) -> QWidget:
    """«Repeat above ▲» / «Repeat below ▼»: the same one, in the same
    place, one level up / down (both its ends) — flights stacked (a fire
    stair, a garage's ramps). The window closes with action "repeat_up" /
    "repeat_down" (one button guessing the way was not clear — his test,
    2026-10-05)."""
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    for way, text in (("up", "Repeat above ▲"), ("down", "Repeat below ▼")):
        b = QPushButton(text)
        b.setToolTip(f"A copy of this {noun}, in the same place, one level "
                     f"{'up' if way == 'up' else 'down'} — stacked flights")

        def go(_=False, way=way) -> None:
            dlg.action = f"repeat_{way}"
            dlg.accept()
        b.clicked.connect(go)
        lay.addWidget(b)
    return box


class _Profile(QWidget):
    """The ramp seen from its side: where it starts, where it ends, its
    slope and length — live with the window's numbers."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(260, 200)
        self.zs = self.ze = 0.0
        self.L = 0.0
        self.slope = 20.0
        self.known = True

    def set(self, zs, ze, L, slope, known=True, landing=0.0,
            shape="straight") -> None:
        self.zs, self.ze, self.L, self.slope, self.known = zs, ze, L, slope, known
        self.landing, self.shape = landing, shape
        self.update()

    landing = 0.0
    shape = "straight"

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(14, 30, -14, -30)
        p.fillRect(self.rect(), QColor("#1d2025"))
        if self.L < 0.1:
            p.setPen(QColor("#9aa0a6"))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "Same height at both ends —\nnothing to ramp")
            return
        down = self.ze < self.zs
        # unfolded: run 1, the landing (L / U), run 2 — the drop drawn true
        # to the slope (a 20 % ramp looks 20 %)
        land = self.landing if self.shape in ("L", "U") else 0.0
        total = self.L + land
        k = min(r.width() / total, r.height() / max(abs(self.zs - self.ze),
                                                    0.01))
        w = total * k
        dz = abs(self.zs - self.ze) * k
        x0 = r.left() + (r.width() - w) / 2
        ytop = r.top() + (r.height() - dz) / 2

        def at(s, z):                     # metres along, height → pixels
            hi = max(self.zs, self.ze)
            return QPointF(x0 + s * k, ytop + (hi - z) * k)
        zm = (self.zs + self.ze) / 2
        tops = [at(0, self.zs)]
        if land:
            tops += [at(self.L / 2, zm), at(self.L / 2 + land, zm)]
        tops.append(at(total, self.ze))
        a, b = tops[0], tops[-1]
        th = max(6.0, 0.15 * k)
        poly = QPolygonF(tops + [QPointF(q.x(), q.y() + th)
                                 for q in reversed(tops)])
        p.setPen(QPen(QColor("#5b5f66"), 1))
        p.setBrush(QColor("#b9b9b6"))
        p.drawPolygon(poly)
        p.setPen(QPen(QColor(ACCENT), 2.4))
        for q0, q1 in zip(tops, tops[1:]):
            p.drawLine(q0, q1)
        if land:
            p.setPen(QColor("#9aa0a6"))
            cx = (tops[1].x() + tops[2].x()) / 2
            p.drawText(QRectF(cx - 60, tops[1].y() - 24, 120, 18),
                       Qt.AlignCenter, "landing")
            p.setPen(QPen(QColor(ACCENT), 2.4))
        # the arrow: the way it goes down (or up)
        tip, back = (b, tops[-2]) if down else (a, tops[1])
        ang = math.atan2(tip.y() - back.y(), tip.x() - back.x())
        for s in (-1, 1):
            p.drawLine(tip, QPointF(tip.x() - 12 * math.cos(ang + s * 0.45),
                                    tip.y() - 12 * math.sin(ang + s * 0.45)))
        f = QFont(p.font())
        f.setPointSize(f.pointSize() + 1)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#e6e6e6"))
        zs_txt = compat.fmt_level(self.zs, unit=False) + (
            "" if self.known else " (the ground)")
        p.drawText(QRectF(a.x() - 10, a.y() - 26, 200, 20), Qt.AlignLeft,
                   zs_txt)
        p.drawText(QRectF(b.x() - 190, b.y() + th + 6, 200, 20),
                   Qt.AlignRight, compat.fmt_level(self.ze, unit=False))
        mid = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
        p.setPen(QColor(ACCENT))
        p.drawText(QRectF(mid.x() - 120, mid.y() + (16 if down else -36), 240,
                          20), Qt.AlignCenter,
                   f"{self.slope:g} %  ·  {compat.fmt_len(self.L)}"
                   + (" (runs)" if land else ""))


#: a railing's own sizes (railings.DEFAULT — that module is the Pro's)
RAIL_DEFAULT = {"railing": "none", "rail_h": 0.90, "rail_d": 0.045,
                "rail_low": False, "rail_ext": 0.30, "rail_inset": 0.05,
                "rail_gap": 1.20, "rail_post": 0.04, "rail_wall_t": 0.15}
RAIL_KINDS = (("none", "None"), ("handrail", "Handrail"), ("steel", "Steel"),
              ("glass", "Glass"), ("wall", "Low wall"))


class _RailFields:
    """A stair's / ramp's railing in its window (plan PLANO_GUARDA_CORPO
    A2): its kind and its sizes — the chips (sides, infill…) stay in the
    library. Pro: greyed in the Lite."""

    def __init__(self, rec: dict, metres, on_change) -> None:
        from PySide6.QtWidgets import QCheckBox

        from . import edition
        self.box = QWidget()
        form = QFormLayout(self.box)
        form.setContentsMargins(0, 8, 0, 0)
        # its way through the slab above (a customer's ask, 2026-10-13)
        self.f_cut = QCheckBox("Opens the slab it passes through")
        self.f_cut.setChecked(bool(rec.get("cut", True)))
        self.f_cut.setToolTip("Off: the slab stays whole — draw an opening "
                              "of your own (Structure › Slab › Opening)")
        self.f_cut.toggled.connect(on_change)
        form.addRow("<b>Slab</b>", self.f_cut)
        head = QLabel("<b>Railing</b>" + (" — ArchXQ IT Pro"
                                          if edition.lite() else ""))
        form.addRow(head)

        def get(k):
            v = rec.get(k)
            return RAIL_DEFAULT[k] if v is None else v
        self.f_kind = QComboBox()
        for key, text in RAIL_KINDS:
            self.f_kind.addItem(text, key)
        self.f_kind.setCurrentIndex(max(0, self.f_kind.findData(
            get("railing"))))
        form.addRow("Kind", self.f_kind)
        self.f = {}
        for key, label, lo, hi, step, tip in (
                ("rail_h", "Height", 0.80, 1.20, 0.01,
                 "Its top over the nosings / the floor (NBR 9077: 0.80–0.92 "
                 "for a handrail)"),
                ("rail_d", "Handrail size", 0.03, 0.08, 0.005,
                 "The tube's diameter (or side, square)"),
                ("rail_ext", "Run on at the ends", 0.0, 0.60, 0.05,
                 "The handrail goes on past the first and the last step "
                 "(NBR 9050: 30 cm)"),
                ("rail_inset", "In from the edge", 0.02, 0.20, 0.01,
                 "How far inside the flight's edge it runs"),
                ("rail_gap", "Post spacing (max)", 0.60, 2.00, 0.05,
                 "Posts never further apart — on a stair, each on a tread"),
                ("rail_post", "Post size", 0.02, 0.10, 0.005, ""),
                ("rail_wall_t", "Low wall thickness", 0.08, 0.30, 0.01, "")):
            w = metres(float(get(key)), lo, hi, step)
            if step < 0.01:
                w.setDecimals(3)
                w.setValue(float(get(key)))   # again: 2 decimals rounded it
            if tip:
                w.setToolTip(tip)
            form.addRow(label, w)
            self.f[key] = w
            w.valueChanged.connect(on_change)
        self.f_low = QCheckBox("A second, lower handrail (0.70 m)")
        self.f_low.setChecked(bool(get("rail_low")))
        self.f_low.setToolTip("Ramps and accessible stairs: two heights "
                              "(NBR 9050)")
        form.addRow("", self.f_low)
        self.f_kind.currentIndexChanged.connect(self.sync)
        self.f_kind.currentIndexChanged.connect(on_change)
        self.f_low.toggled.connect(on_change)
        self.box.setEnabled(not edition.lite())
        self.sync()

    def sync(self, *_a) -> None:
        k = self.f_kind.currentData()
        on = k != "none"
        for key, w in self.f.items():
            w.setEnabled(on and (key != "rail_wall_t" or k == "wall")
                         and (key not in ("rail_gap", "rail_post")
                              or k in ("steel", "glass", "handrail")))
        self.f_low.setEnabled(on and k != "wall")

    def write(self, r: dict) -> None:
        r["railing"] = self.f_kind.currentData()
        for key, w in self.f.items():
            r[key] = round(w.value(), 3)
        r["rail_low"] = self.f_low.isChecked()
        r["cut"] = self.f_cut.isChecked()


#: the railing's sizes: (key, label, lo, hi, step, tip) — _RailFields' and
#: RailTab's
RAIL_SIZES = (
    ("rail_h", "Height", 0.80, 1.20, 0.01,
     "Its top over the nosings / the floor (NBR 9077: 0.80–0.92 for a "
     "handrail)"),
    ("rail_d", "Handrail size", 0.03, 0.08, 0.005,
     "The tube's diameter (or side, square)"),
    ("rail_ext", "Run on at the ends", 0.0, 0.60, 0.05,
     "The handrail goes on past the first and the last step (NBR 9050: "
     "30 cm)"),
    ("rail_inset", "In from the edge", 0.02, 0.20, 0.01,
     "How far inside the flight's edge it runs"),
    ("rail_gap", "Post spacing (max)", 0.60, 2.00, 0.05,
     "Posts never further apart — on a stair, each on a tread"),
    ("rail_post", "Post size", 0.02, 0.10, 0.005, ""),
    ("rail_wall_t", "Low wall thickness", 0.08, 0.30, 0.01, ""))


def _pic_rail(kind):
    """A railing kind as a small picture (the Railing tab's chips)."""
    def draw(p, r, _on):
        from . import look as L
        p.setPen(L.pen(L.DIM, 2.0))
        p.drawLine(QPointF(6, 36), QPointF(54, 36))
        if kind == "none":
            p.setPen(L.pen("#ff8a80", 1.5))
            p.drawLine(QPointF(22, 14), QPointF(38, 28))
            p.drawLine(QPointF(38, 14), QPointF(22, 28))
            return
        if kind == "wall":
            L.poly(p, [(8, 14), (52, 14), (52, 36), (8, 36)], L.INK, 1.2,
                   fill="#8a8f96")
            return
        if kind == "glass":
            L.poly(p, [(9, 14), (51, 14), (51, 34), (9, 34)], L.BLUE, 1.0,
                   fill="#5bc8e83a")
        p.setPen(L.pen(L.BLUE, 2.6 if kind == "handrail" else 1.8))
        p.drawLine(QPointF(6, 11), QPointF(54, 11))
        p.setPen(L.pen(L.BLUE, 1.4))
        if kind == "handrail":
            for x in (12, 48):
                p.drawLine(QPointF(x, 11), QPointF(x, 18))
        else:
            for x in (10, 30, 50):
                p.drawLine(QPointF(x, 11), QPointF(x, 36))
            if kind == "steel":
                p.drawLine(QPointF(6, 23), QPointF(54, 23))
    return draw


def _draw_rail_sizes(p, r, hot, d):
    """The railing over a flight, its sizes: H, run on, posts."""
    from . import look as L
    L.poly(p, [(8, 100), (38, 100), (38, 86), (68, 86), (68, 72), (98, 72),
               (98, 58), (142, 58)], L.INK, 1.5)
    p.setPen(L.pen(L.BLUE, 2.6 if hot == "rail_d" else 2.0))
    if hot == "rail_d":
        p.setPen(L.pen(L.GOLD, 3.0))
    p.drawLine(QPointF(2, 52), QPointF(146, 24))
    p.setPen(L.pen(L.GOLD if hot in ("rail_post", "rail_gap") else L.BLUE,
                   1.6 if hot == "rail_post" else 1.1))
    for x, y0 in ((23, 100), (53, 86), (83, 72), (113, 58)):
        yt = 52 - (x - 2) * 28 / 144
        p.drawLine(QPointF(x, yt), QPointF(x, y0))
    L.dim(p, (132, 26), (132, 58), "H", hot == "rail_h", at=(136, 46))
    L.dim(p, (23, 106), (53, 106), "", hot == "rail_gap")
    L.text(p, 38, 118, "posts", L.GOLD if hot == "rail_gap" else L.BLUE,
           align=Qt.AlignHCenter)
    L.dim(p, (2, 60), (23, 60), "", hot == "rail_ext")
    L.text(p, 2, 72, "run on", L.GOLD if hot == "rail_ext" else L.BLUE)


class RailTab:
    """A stair's / ramp's RAILING tab (the windows of 0.10.0): its kind as
    pictures, its options as the library's chips (sides, infill, glass
    fixing, handrail, …), its sizes beside a drawing. Writes the same keys
    as the library and _RailFields. Pro: greyed in the Lite (its kinds)."""

    def __init__(self, rec: dict, lay, metres, on_change, key: str) -> None:
        from PySide6.QtWidgets import QCheckBox

        from . import edition
        from . import library as LB
        from . import look as L
        from . import railings as RL
        self.on_change = on_change
        lite = edition.lite()

        def get(k):
            v = rec.get(k)
            return RL.DEFAULT.get(k, RAIL_DEFAULT.get(k)) if v is None else v
        # its kind
        self.fold_kind = L.Fold("Kind", f"{key}.rail.kind")
        self.f_kind = L.Chips()
        for k, text in RAIL_KINDS:
            self.f_kind.addItem(text, k, pic=_pic_rail(k))
        self.f_kind.setCurrentIndex(max(0, self.f_kind.findData(get("railing"))))
        if lite:
            for i in range(1, self.f_kind.count()):
                self.f_kind.setItemEnabled(i, False)
            self.f_kind.setToolTip("Railings are in ArchXQ IT Pro")
        self.fold_kind.box.addWidget(self.f_kind)
        lay.addWidget(self.fold_kind)
        # its options — the library's chips, shown as they apply
        self.fold_opts = L.Fold("Options", f"{key}.rail.options")
        form = self.fold_opts.form()
        self.opts = []
        for part in LB.RAILING_PARTS:
            if part.key == "railing" or part.kind != "chips":
                continue
            c = L.Chips()
            for ch in part.choices:
                c.addItem(ch[1], ch[0])
            c.setCurrentIndex(max(0, c.findData(get(part.key))))
            lab = QLabel(part.label)
            form.addRow(lab, c)
            c.currentIndexChanged.connect(self._sync)
            self.opts.append((part, lab, c))
        lay.addWidget(self.fold_opts)
        # its sizes
        self.fold_sizes = L.Fold("Sizes", f"{key}.rail.sizes")
        self.drawing = L.Drawing(_draw_rail_sizes, 150, 124)
        form = self.fold_sizes.form(self.drawing)
        self.f = {}
        self.rows = {}
        for k, label, lo, hi, step, tip in RAIL_SIZES:
            w = metres(float(get(k)), lo, hi, step)
            if step < 0.01:
                w.setDecimals(3)
                w.setValue(float(get(k)))
            if tip:
                w.setToolTip(tip)
            lab = QLabel(label)
            form.addRow(lab, w)
            self.f[k] = w
            self.rows[k] = lab
            self.drawing.link(w, k)
            w.valueChanged.connect(self._sync)
        self.f_low = QCheckBox("A second, lower handrail (0.70 m)")
        self.f_low.setChecked(bool(get("rail_low")))
        self.f_low.setToolTip("Ramps and accessible stairs: two heights "
                              "(NBR 9050)")
        form.addRow("", self.f_low)
        self.f_low.toggled.connect(self._sync)
        lay.addWidget(self.fold_sizes)
        self.f_kind.currentIndexChanged.connect(self._sync)
        if lite:
            self.fold_opts.setEnabled(False)
            self.fold_sizes.setEnabled(False)
        self._sync(quiet=True)

    def _record(self) -> dict:
        r = {"railing": self.f_kind.currentData()}
        for part, _lab, c in self.opts:
            r[part.key] = c.currentData()
        for k, w in self.f.items():
            r[k] = round(w.value(), 3)
        r["rail_low"] = self.f_low.isChecked()
        return r

    def _sync(self, *_a, quiet: bool = False) -> None:
        r = self._record()
        k = r["railing"]
        on = k != "none"
        self.fold_opts.setVisible(on)
        self.fold_sizes.setVisible(on)
        for part, lab, c in self.opts:
            shown = part.show is None or bool(part.show(r))
            lab.setVisible(shown)
            c.setVisible(shown)
        for key, w in self.f.items():
            shown = (key != "rail_wall_t" or k == "wall") and (
                key not in ("rail_gap", "rail_post")
                or k in ("steel", "glass", "handrail"))
            w.setVisible(shown)
            self.rows[key].setVisible(shown)
        self.f_low.setVisible(k != "wall")
        self.fold_kind.set_pick(self.f_kind.currentText())
        self.fold_sizes.set_pick(f"{compat.fmt_num(r['rail_h'])} high")
        side = next((c.currentText() for part, _l, c in self.opts
                     if part.key == "rail_sides"), "")
        self.fold_opts.set_pick(f"Sides: {side}" if side else "")
        if not quiet:
            self.on_change()

    def write(self, r: dict) -> None:
        r.update(self._record())

    def summary(self) -> str:
        return ("no railing" if self.f_kind.currentData() == "none"
                else self.f_kind.currentText().lower() + " railing")


class FlightPlan(QWidget):
    """A ramp / stair seen from above, live (the windows of 0.10.0): its
    runs (a stair's treads), the landing, the way it goes from the click —
    drawn upwards on the page, whatever its angle. ``pieces(r)`` gives its
    plan pieces (ramps.pieces / stairs.layout)."""

    EMPTY = "Same height at both ends"

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(280, 230)
        self.r = None
        self.zs = self.ze = 0.0
        self.kw = {}

    def set(self, r, zs, ze, known=True, **kw) -> None:
        self.r, self.zs, self.ze, self.kw = r, zs, ze, kw
        self.update()

    def pieces(self, r) -> list:
        raise NotImplementedError

    def paintEvent(self, _e) -> None:  # noqa: N802
        from . import look as L
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(L.FIELD))
        try:
            self._paint(p, L)
        except Exception:  # noqa: BLE001 — a preview never breaks the window
            import traceback
            traceback.print_exc()
        finally:
            p.end()

    def _paint(self, p, L) -> None:
        if self.r is None or abs(self.zs - self.ze) < 0.05:
            p.setPen(QColor(L.MUTED))
            p.drawText(self.rect(), Qt.AlignCenter, self.EMPTY)
            return
        r = dict(self.r, x=0.0, y=0.0, angle=90.0)
        ps = self.pieces(r)
        tp = top_piece(r, ps, self.zs, self.ze)   # its landing at the top
        ps_all = ps + ([tp] if tp else [])
        polys = [piece_corners(pc) for pc in ps_all]
        xs = [q[0] for pg in polys for q in pg]
        ys = [q[1] for pg in polys for q in pg]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        rr = QRectF(self.rect()).adjusted(18, 16, -18, -26)
        k = min(rr.width() / max(x1 - x0, 0.5), rr.height() / max(y1 - y0, 0.5))
        ox = rr.left() + (rr.width() - (x1 - x0) * k) / 2
        oy = rr.top() + (rr.height() - (y1 - y0) * k) / 2

        def q(x, y):
            return QPointF(ox + (x - x0) * k, oy + (y1 - y) * k)
        for pc, pg in zip(ps_all, polys):
            run = pc.get("run", True)
            p.setPen(L.pen(L.INK, 1.5))
            p.setBrush(QColor("#34373c" if run else "#2a2c30"))
            p.drawPolygon(QPolygonF([q(*a) for a in pg]))
            p.setBrush(Qt.NoBrush)
            if run and pc.get("m", 0) >= 2:       # a stair's treads
                (cx, cy), (dx, dy) = pc["c"], pc["d"]
                rx, ry = dy, -dx
                h = pc["w"] / 2
                p.setPen(L.pen(L.DIM, 1.0))
                for j in range(1, pc["m"] - 1):
                    s = j * pc["p"]
                    p.drawLine(q(cx + dx * s + rx * h, cy + dy * s + ry * h),
                               q(cx + dx * s - rx * h, cy + dy * s - ry * h))
        # the way: along the runs' middles, through the landing
        runs = [pc for pc in ps if pc.get("run", True)]
        a = runs[0]
        (cx, cy), (dx, dy) = a["c"], a["d"]
        path = [(cx, cy), (cx + dx * a["l"], cy + dy * a["l"])]
        if len(runs) > 1:
            b = runs[1]
            (bx, by), (ex, ey) = b["c"], b["d"]
            land = next((pc for pc in ps if not pc.get("run", True)), None)
            if r.get("shape") == "U" and land is not None:
                m = land["l"] / 2
                path += [(path[-1][0] + dx * m, path[-1][1] + dy * m),
                         (bx - ex * m, by - ey * m)]
            else:
                back = b["w"] / 2
                path += [(bx - ex * back, by - ey * back)]
            path += [(bx, by), (bx + ex * b["l"], by + ey * b["l"])]
        up = (self.ze - self.zs) > 0
        L.poly(p, [(q(*a_).x(), q(*a_).y()) for a_ in path], L.BLUE, 2.0)
        e, f = q(*path[-1]), q(*path[-2])
        ang = math.atan2(e.y() - f.y(), e.x() - f.x())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(L.BLUE))
        p.drawPolygon(QPolygonF([
            e, QPointF(e.x() - 9 * math.cos(ang - 0.45),
                       e.y() - 9 * math.sin(ang - 0.45)),
            QPointF(e.x() - 9 * math.cos(ang + 0.45),
                    e.y() - 9 * math.sin(ang + 0.45))]))
        s0 = q(*path[0])
        p.setBrush(QColor(L.ACCENT))
        p.drawEllipse(s0, 5, 5)
        p.setBrush(Qt.NoBrush)
        L.text(p, s0.x(), s0.y() + 19, "UP" if up else "DOWN", L.MUTED, 8,
               False, align=Qt.AlignHCenter)


def _ic_ramp(p, r, _on):
    from . import look as L
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#3a2f1c"))
    p.drawRoundedRect(r, 8, 8)
    L.poly(p, [(6, 31), (34, 31), (34, 12), (6, 31)], L.GOLD, 2.4)


def _draw_ramp_levels(p, r, hot, d):
    """Its two ends, the height between them."""
    from . import look as L
    p.setPen(L.pen("#8a8f96", 3.0))
    p.drawLine(QPointF(8, 78), QPointF(50, 78))
    p.drawLine(QPointF(100, 22), QPointF(142, 22))
    p.setPen(L.pen(L.INK, 1.6, dash=True))
    p.drawLine(QPointF(50, 78), QPointF(100, 22))
    L.dim(p, (144, 22), (144, 78), "", hot == "z")
    L.text(p, 139, 54, d.get("h", ""), L.GOLD if hot == "z" else L.BLUE,
           align=Qt.AlignRight)
    L.text(p, 8, 72, d.get("lo", ""), L.MUTED, 7, False)
    L.text(p, 100, 16, d.get("hi", ""), L.MUTED, 7, False)


def _draw_slope(p, r, hot, d):
    """The ramp from its side: its slope (%), its length, its thickness."""
    from . import look as L
    L.poly(p, [(10, 86), (138, 30), (138, 42), (10, 98)], L.INK, 1.4,
           fill="#4a4d52")
    p.setPen(L.pen(L.DIM, 1.0, dash=True))
    p.drawLine(QPointF(10, 86), QPointF(138, 86))
    L.dim(p, (138, 30), (138, 86), "", hot == "slope", ticks=False)
    L.text(p, 100, 74, d.get("slope", "%"), L.GOLD if hot == "slope"
           else L.BLUE)
    L.dim(p, (10, 104), (138, 104), "", hot == "L")
    L.text(p, 74, 117, d.get("L", "length"), L.GOLD if hot == "L" else L.BLUE,
           align=Qt.AlignHCenter)
    L.dim(p, (40, 73), (45, 85), "", hot == "t", ticks=False)
    L.text(p, 26, 70, "t", L.GOLD if hot == "t" else L.BLUE)


def _pic_ramp_shape(shape):
    def draw(p, r, _on):
        from . import look as L
        if shape == "straight":
            L.poly(p, [(20, 2), (40, 2), (40, 42), (20, 42)], L.INK, 1.5,
                   close=True)
            L.poly(p, [(30, 40), (30, 6)], L.BLUE, 1.4)
            L.poly(p, [(27, 10), (30, 6), (33, 10)], L.BLUE, 1.4)
        elif shape == "L":
            L.poly(p, [(14, 42), (14, 2), (46, 2), (46, 18), (30, 18), (30, 42)],
                   L.INK, 1.5, close=True)
            p.setPen(L.pen(L.DIM, 1.0))
            p.drawLine(QPointF(14, 18), QPointF(30, 18))
            p.drawLine(QPointF(30, 2), QPointF(30, 18))
            L.poly(p, [(22, 40), (22, 10), (43, 10)], L.BLUE, 1.4)
        else:
            L.poly(p, [(12, 42), (12, 2), (48, 2), (48, 42), (32, 42), (32, 16),
                       (28, 16), (28, 42)], L.INK, 1.5, close=True)
            p.setPen(L.pen(L.DIM, 1.0))
            p.drawLine(QPointF(12, 16), QPointF(48, 16))
            L.poly(p, [(20, 40), (20, 9), (40, 9), (40, 39)], L.BLUE, 1.4)
    return draw


class _RampPlan(FlightPlan):
    EMPTY = "Same height at both ends —\nnothing to ramp"

    def pieces(self, r) -> list:
        return pieces(r, self.zs, self.ze, float(self.kw.get("L", 1.0)))


#: the usual slopes, a click each (NBR 9050: 8.33 % for people)
SLOPES = ((8.33, "8.33 % people", "NBR 9050: the most for an accessible "
                                  "ramp"),
          (12.5, "12.5 %", "A short ramp for people (NBR 9050 allows it "
                           "only in a few cases)"),
          (20.0, "20 % cars", "Usual for a garage ramp"))


class RampDialog(QDialog):
    """Set a ramp up (``edit`` False: before drawing it) or change one
    (``edit`` True: its name, where it is, delete). ``result_data()`` →
    (action, record) — action "apply" | "delete".

    The window of 0.10.0 (look.py, as the stair's): tabs Geometry · Build ·
    Railing · Position (+ Material), folds with drawings, picture chips, a
    live plan / side preview with its numbers and the slope's check. The
    fields and the record are the old window's."""

    def __init__(self, rec: dict, doc: dict, elevations, edit: bool = False,
                 parent=None) -> None:
        from PySide6.QtWidgets import QToolButton

        from . import look as L
        from .dialogs import _metres, ok_apply
        super().__init__(parent)
        self.rec = dict(rec)
        self.doc = doc
        self.elevations = elevations
        self.edit = edit
        self.action = "apply"
        self.setWindowTitle("Ramp")
        self.setMinimumWidth(900)
        L.dress(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(6)
        self.head = L.Header(_ic_ramp, rec.get("name") or "Ramp", "ramp",
                             editable=edit)
        self.f_name = self.head.name if edit else None
        lay.addWidget(self.head)
        self.tabs = L.Tabs()
        self._axq_tabs = self.tabs            # materials.with_tab: «Material»
        lay.addWidget(self.tabs.bar)
        lay.addWidget(L.rule())

        # ---- Geometry ------------------------------------------------------------
        geo, gl = L.page()
        self.fold_lv = L.Fold("Levels", "ramp.levels")
        self.d_lv = L.Drawing(_draw_ramp_levels, 150, 90)
        form = self.fold_lv.form(self.d_lv)
        # WHERE — its top over its bottom, and where the click is
        self.ends = _Ends(doc, elevations, rec, form, _metres, choice=L.Chips)
        self.d_lv.link(self.ends.f_z, "z")
        gl.addWidget(self.fold_lv)

        self.fold_size = L.Fold("Slope & size", "ramp.size")
        self.d_size = L.Drawing(_draw_slope, 150, 124)
        form = self.fold_size.form(self.d_size)
        self.f_w = L.metres(float(rec.get("w", 3.0)), 0.5, 30.0)
        form.addRow("Width", self.f_w)
        self.f_slope = L.Measure(float(rec.get("slope", 20.0)), SLOPE_MIN,
                                 SLOPE_MAX, 0.1, suffix=" %")
        self.f_slope.setSingleStep(1.0)
        self.f_slope.setToolTip("How steep: 20 % is usual for cars, 8.33 % "
                                "for people — the length follows from it")
        form.addRow("Slope", self.f_slope)
        presets = QWidget()
        pl_ = QHBoxLayout(presets)
        pl_.setContentsMargins(0, 0, 0, 0)
        pl_.setSpacing(6)
        for v, text, tip in SLOPES:
            b = QToolButton()
            b.setObjectName("axqChip")
            b.setText(text)
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _c=False, v=v: self.f_slope.setValue(v))
            pl_.addWidget(b)
        pl_.addStretch(1)
        form.addRow("", presets)
        # the length too, for special cases: type it and the slope follows
        self.fix = rec.get("fix", "slope")
        self._quiet = False
        self.f_len = L.metres(float(rec.get("L", 15.0)), 0.5, 500.0, 0.10)
        self.f_len.setToolTip("Type a length for a special case: the slope "
                              "then follows from it")
        form.addRow("Length", self.f_len)
        self.f_hint = L.hint("")
        form.addRow("", self.f_hint)
        self.f_t = L.metres(float(rec.get("t", 0.15)), 0.05, 1.0, 0.01)
        form.addRow("Thickness", self.f_t)
        for w, key in ((self.f_slope, "slope"), (self.f_len, "L"),
                       (self.f_t, "t")):
            self.d_size.link(w, key)
        gl.addWidget(self.fold_size)

        # SHAPE — straight, or turning on a level landing (L: 90°, U: back)
        self.fold_shape = L.Fold("Shape", "ramp.shape")
        self.f_shape = L.Chips()
        for key, text, tip in (("straight", "Straight", "One run"),
                               ("L", "L", "Two runs, a landing, a 90° turn"),
                               ("U", "U", "Two runs side by side, a landing "
                                          "across both")):
            self.f_shape.addItem(text, key, tip, pic=_pic_ramp_shape(key))
        self.f_shape.setCurrentIndex(max(0, self.f_shape.findData(
            rec.get("shape", "straight"))))
        self.fold_shape.box.addWidget(self.f_shape)
        form = self.fold_shape.form()
        self.f_turn = L.Chips(width=70)
        self.f_turn.addItem("Right", "right")
        self.f_turn.addItem("Left", "left")
        self.f_turn.setCurrentIndex(1 if rec.get("turn") == "left" else 0)
        self.f_turn.setToolTip("The side the second run goes to (Tab, while "
                               "placing it, swaps it)")
        form.addRow("Turn", self.f_turn)
        self.f_land = L.metres(float(rec.get("landing", 3.0)), 0.5, 50.0)
        self.f_land.setToolTip("The level landing between the two runs (an "
                               "L's is never shorter than the ramp is wide)")
        form.addRow("Landing", self.f_land)
        # its landing at the top (2026-10-18): accessibility wants a level
        # stretch where it arrives — or push the grip on its top edge
        self.f_tland = L.metres(float(rec.get("top_landing", 0.0) or 0.0),
                                0.0, 20.0)
        self.f_tland.setToolTip("A level platform where it arrives, this "
                                "long (0: none) — or push the grip on its "
                                "top edge")
        form.addRow("Landing at the top", self.f_tland)
        gl.addWidget(self.fold_shape)
        gl.addStretch(1)
        self.tabs.addTab(geo, "Geometry", "geometry")

        # ---- Build ---------------------------------------------------------------
        bld, bl = L.page()
        # a sloped slab, or SOLID down to the floor (his ask, 2026-10-18 —
        # a shop's entrance ramp, a block under it)
        self.fold_build = L.Fold("Structure", "ramp.build")
        self.f_build = L.Chips()
        self.f_build.addItem("Slab — a sloped slab", "slab",
                             "A slab of the given thickness, open under it")
        self.f_build.addItem("Solid — filled down to the floor", "solid",
                             "A block under it, down to the lower floor: an "
                             "entrance ramp on the ground")
        self.f_build.setCurrentIndex(1 if rec.get("build") == "solid" else 0)
        self.fold_build.box.addWidget(self.f_build)
        bl.addWidget(self.fold_build)
        self.fold_cut = L.Fold("Opening in the slab", "ramp.cut")
        self.f_cut = L.Chips()
        self.f_cut.addItem("Auto — it opens the slab it passes through", True)
        self.f_cut.addItem("None", False)
        self.f_cut.setCurrentIndex(0 if rec.get("cut", True) else 1)
        self.fold_cut.box.addWidget(self.f_cut)
        # room round it (as a stair's — his ask, 2026-10-15)
        self.f_clear = L.metres(float(rec.get("clear", 0.0) or 0.0), 0.0, 1.0)
        self.f_clear.setToolTip("The opening this much wider round the "
                                "ramp — never on the side where it reaches "
                                "the floor")
        self.fold_cut.form().addRow("Clearance", self.f_clear)
        self.fold_cut.box.addWidget(L.hint(
            "None: the slab stays whole — draw an opening of your own "
            "(Structure › Slab › Opening, any shape)."))
        bl.addWidget(self.fold_cut)
        bl.addStretch(1)
        self.tabs.addTab(bld, "Build", "build")

        # ---- Railing -------------------------------------------------------------
        rail, rl_ = L.page()
        self.rails = RailTab(rec, rl_, L.metres, self._sync, "ramp")
        rl_.addStretch(1)
        self.tabs.addTab(rail, "Railing", "railing")

        # ---- Position ------------------------------------------------------------
        pos, pl = L.page()
        self.fold_anchor = L.Fold("Insert at", "ramp.anchor")
        self.f_anchor = _anchor_box(rec, chips=True)
        self.fold_anchor.box.addWidget(self.f_anchor)
        pl.addWidget(self.fold_anchor)
        if edit:                          # where it is (the tool set it)
            self.fold_place = L.Fold("Placement", "ramp.place")
            self.d_dial = L.Drawing(L.draw_dial, 150, 104)
            form = self.fold_place.form(self.d_dial)
            self.f_x = _metres(float(rec["x"]), -10000.0, 10000.0)
            self.f_y = _metres(float(rec["y"]), -10000.0, 10000.0)
            self.f_a = QDoubleSpinBox()
            self.f_a.setRange(-360.0, 360.0)
            self.f_a.setDecimals(1)
            self.f_a.setSingleStep(15.0)
            self.f_a.setSuffix(" °")
            self.f_a.setValue(float(rec.get("angle", 0.0)))
            form.addRow("Start X", self.f_x)
            form.addRow("Start Y", self.f_y)
            form.addRow("Direction", self.f_a)
            self.d_dial.link(self.f_a, "a")
            pl.addWidget(self.fold_place)
        else:
            pl.addWidget(L.hint(
                "OK: back to the plan — click where it starts (its bottom "
                "or its top — «Starts at»; a corner or the middle — «Insert "
                "at»), then the way it goes."))
        pl.addStretch(1)
        self.tabs.addTab(pos, "Position", "position")
        self._own = self.tabs.count()

        # ---- the pages + the preview beside them ---------------------------------
        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self.tabs.stack, 5)
        self.view_pick = L.Chips()
        self.view_pick.addItem("Plan", "plan")
        self.view_pick.addItem("Side", "side")
        card = L.Card("Preview", self.view_pick)
        self.plan = _RampPlan()
        self.profile = _Profile()
        self.profile.hide()
        card.box.addWidget(self.plan, 1)
        card.box.addWidget(self.profile, 1)
        self.stats = L.Stats(4)
        card.box.addWidget(self.stats)
        self.badge = L.Badge()
        card.box.addWidget(self.badge)
        self.side = card
        body.addWidget(card, 4)
        lay.addLayout(body, 1)
        self.view_pick.currentIndexChanged.connect(self._pick_view)
        self.tabs.currentChanged.connect(
            lambda i: self.side.setVisible(i < self._own))

        # ---- the buttons ---------------------------------------------------------
        lay.addWidget(L.rule())
        acts = QHBoxLayout()
        if edit:
            from .dialogs import hide_button
            acts.addWidget(_repeat_button(self, "ramp"))
            acts.addWidget(hide_button(self))
            b_del = QPushButton("Delete ramp")
            b_del.setObjectName("axqDanger")
            b_del.clicked.connect(self._delete)
            acts.addWidget(b_del)
        acts.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        if edit:
            ok_apply(self, bb)
        L.ok_button(bb)
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        acts.addWidget(bb)
        lay.addLayout(acts)

        for w in self.ends.widgets() + (self.f_turn, self.f_shape,
                                        self.f_cut, self.f_anchor,
                                        self.f_build):
            w.currentIndexChanged.connect(self._sync)
        for w in (*self.ends.values(), self.f_w, self.f_t, self.f_land,
                  self.f_clear, self.f_tland):
            w.valueChanged.connect(self._sync)
        self.f_slope.valueChanged.connect(lambda _v: self._given("slope"))
        self.f_len.valueChanged.connect(lambda _v: self._given("length"))
        if edit:
            for w in (self.f_x, self.f_y, self.f_a):
                w.valueChanged.connect(self._sync)
        self._sync()

    def _pick_view(self, *_a) -> None:
        side = self.view_pick.currentData() == "side"
        self.profile.setVisible(side)
        self.plan.setVisible(not side)

    def _record(self) -> dict:
        r = dict(self.rec)
        self.ends.write(r)
        # it belongs to the lower of its two levels (the storey it takes)
        r["level"] = owner(r, self.doc, self.elevations)
        r["w"] = round(self.f_w.value(), 3)
        r["slope"] = round(self.f_slope.value(), 2)
        r["fix"] = self.fix
        r["L"] = round(self.f_len.value(), 3)
        r["t"] = round(self.f_t.value(), 3)
        r["shape"] = self.f_shape.currentData() or "straight"
        r["turn"] = self.f_turn.currentData()
        r["landing"] = round(self.f_land.value(), 3)
        r["anchor"] = self.f_anchor.currentData()
        self.rails.write(r)
        r["cut"] = bool(self.f_cut.currentData())
        r["clear"] = round(self.f_clear.value(), 3)
        r["build"] = self.f_build.currentData() or "slab"
        tl = round(self.f_tland.value(), 3)
        if tl >= 0.01:
            r["top_landing"] = tl
        else:
            r.pop("top_landing", None)
        if self.edit:
            r["x"] = round(self.f_x.value(), 4)
            r["y"] = round(self.f_y.value(), 4)
            r["angle"] = round(self.f_a.value(), 3)
            r["name"] = self.f_name.text().strip() or self.rec.get("name")
        return r

    def _given(self, which: str) -> None:
        """The slope or the length typed: that one is given, the other one
        follows (not when ``_sync`` itself writes it)."""
        if self._quiet:
            return
        self.fix = which
        self._sync()

    def _drop(self, r: dict):
        """(zs, ze, known): on the terrain and not placed yet, the ground is
        read where it will start — meanwhile, the plot's mean height."""
        r = dict(r)
        r.setdefault("x", 0.0)
        r.setdefault("y", 0.0)
        zs, ze = heights(r, self.doc, self.elevations)
        known = r["start"] != "terrain" or self.edit
        if not known:
            hs = self.doc["plot"].get("heights") or [0.0]
            zs = sum(hs) / len(hs)
        return zs, ze, known

    def _sync(self, *_a) -> None:
        self.ends.sync()
        r = self._record()
        turning = r["shape"] in ("L", "U")
        self.f_turn.setEnabled(turning)
        self.f_land.setEnabled(turning)
        zs, ze, known = self._drop(r)
        L, slope = length_of(r, zs, ze), slope_of(r, zs, ze)
        self._quiet = True                # write the one that follows
        try:
            if self.fix == "length":
                self.f_slope.setValue(min(max(slope, SLOPE_MIN), SLOPE_MAX))
            else:
                self.f_len.setValue(L)
        finally:
            self._quiet = False
        ok = SLOPE_MIN <= slope <= SLOPE_MAX
        approx = "" if known else " ≈ (the ground decides)"
        self.f_hint.setText(
            (f"Slope from the length: {slope:.1f} %{approx}" if
             self.fix == "length" else
             f"Length from the slope{approx}")
            + ("" if ok else f" — too steep (max {SLOPE_MAX:g} %)"
               if slope > SLOPE_MAX else " — too flat"))
        land = 0.0
        if turning:
            land = max(r["landing"], r["w"]) if r["shape"] == "L" \
                else r["landing"]
        self.profile.set(zs, ze, L, round(slope, 1), known, land, r["shape"])
        self.plan.set(r, zs, ze, known, L=L)
        drop = abs(ze - zs)

        def name(box):
            return box.currentText().split("  (")[0].strip()
        lo, hi = name(self.ends.f_bottom), name(self.ends.f_top)
        if self.ends.by_heights():        # two elevations
            lo = compat.fmt_level(min(zs, ze), unit=False)
            hi = compat.fmt_level(max(zs, ze), unit=False)
        self.ends.note(f"{compat.fmt_len(drop)} · {slope:.1f} % · "
                       f"{compat.fmt_len(L)} long")
        shape = {"L": "L", "U": "U"}.get(r["shape"], "Straight")
        if turning:
            shape += f", turning {r['turn']}"
        self.head.set_summary([
            f"{lo} → {hi}", "{" + compat.fmt_len(drop) + "}",
            "{" + f"{slope:.1f} %" + "}", "{" + compat.fmt_len(L) + "} long",
            shape, self.rails.summary()])
        self.fold_lv.set_pick(f"{lo} → {hi}")
        self.fold_size.set_pick(f"{compat.fmt_num(r['w'])} wide · "
                                f"{slope:.1f} %")
        self.fold_shape.set_pick(shape)
        self.fold_build.set_pick("Solid" if r["build"] == "solid" else "Slab")
        self.f_clear.setEnabled(r["cut"])
        self.fold_cut.set_pick(("Auto" + (
            f" {compat.fmt_level(r['clear'], unit=False)}"
            if r["clear"] > 1e-6 else ""))
                               if r["cut"] else "None")
        self.fold_anchor.set_pick(self.f_anchor.currentText())
        self.d_lv.set(h=compat.fmt_num(drop), lo=lo, hi=hi)
        self.d_size.set(slope=f"{slope:.1f} %", L=compat.fmt_len(L))
        if self.edit:
            self.fold_place.set_pick(f"{compat.fmt_num(r['x'])}, "
                                     f"{compat.fmt_num(r['y'])} · "
                                     f"{r['angle'] % 360:.0f}°")
            self.d_dial.set(a=r["angle"])
        self.stats.set([(f"{slope:.1f} %", "slope"),
                        (compat.fmt_len(L), "length"),
                        (compat.fmt_len(drop), "height"),
                        (compat.fmt_len(land), "landing") if turning
                        else (compat.fmt_len(r['w']), "wide")])
        code = "ADA" if compat.imperial() else "NBR 9050"   # (1:12 both)
        if slope <= 8.335:
            self.badge.set(True, f"Accessible: {code} ≤ 8.33 % (1:12)")
        elif slope <= 20.0:
            self.badge.set(True, "Vehicle ramp (≤ 20 %) — steeper than "
                                 f"{code}'s 8.33 % for people")
        else:
            self.badge.set(False, "Steeper than 20 % — check it")

    def _ok(self) -> None:
        r = self._record()
        why = self.ends.why_not() or why_not(dict(r, x=r.get("x", 0.0),
                                                   y=r.get("y", 0.0)))
        if why is None and r["start"] != "terrain":
            zs, ze = heights(dict(r, x=0.0, y=0.0), self.doc, self.elevations)
            if abs(zs - ze) < 0.05:
                why = "The top and the bottom are at the same height"
            elif r["fix"] == "length":
                s = slope_of(r, zs, ze)
                if not SLOPE_MIN <= s <= SLOPE_MAX:
                    why = (f"That length makes it {s:.1f} % — a ramp goes "
                           f"from {SLOPE_MIN:g} to {SLOPE_MAX:g} %")
        if why:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Ramp", why + ".")
            return
        self.accept()

    def _delete(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, "Delete?", f"Delete «{self.rec.get('name')}»? (Ctrl+Z "
                "brings it back)", QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel) == QMessageBox.Yes:
            self.action = "delete"
            self.accept()

    def result_data(self):
        return self.action, self._record()


# ---- its tool --------------------------------------------------------------------------
class RampTool(_PlotTool):
    """Click where it starts (the middle of its top edge), then click the
    way it goes — its length is known (the drop and the slope). A typed
    number = its direction in degrees (from the red axis)."""
    name = "ArchXQ ramp"
    axq_element = "ramp"
    noun = "Ramp"
    icon = "ramp"
    vcb_label = "Angle"
    diagonal = True                    # 45° pull, as the other tools

    def __init__(self, rec: dict, length_at, on_done, on_cancelled,
                 z: float) -> None:
        """``length_at(p)`` → (length, zs, ze) for a ramp starting at p."""
        super().__init__(on_done, on_cancelled)
        self.rec = rec
        self.length_at = length_at
        self.z = z

    def _reset(self) -> None:
        self.a = None
        self.diag = None
        self._sync()

    def _busy(self) -> bool:
        return self.a is not None

    def _anchor(self):
        return self.a

    def _sync(self) -> None:
        self._sync_protocol([self.a] if self.a else [], self.hover)
        self.chain_first_point = None

    def _angle(self, p) -> float | None:
        if self.a is None or p is None or math.dist(self.a, p) < 1e-3:
            return None
        return math.degrees(math.atan2(p[1] - self.a[1], p[0] - self.a[0]))

    def _rec_at(self, ang: float) -> dict:
        return dict(self.rec, x=round(self.a[0], 4), y=round(self.a[1], 4),
                    angle=round(ang, 3))

    def on_click(self, ctx) -> None:
        p = self._pick(ctx)
        if self.a is None:
            self.a = p
            self._sync()
            self._show_hint()
            return
        ang = self._angle(p)
        if ang is None:
            return
        self._done(self._rec_at(ang))

    def on_value(self, viewport, value) -> bool:
        if self.a is None or not isinstance(value, (int, float)):
            return False
        self._done(self._rec_at(float(value)))
        return True

    def _done(self, rec: dict) -> None:
        self._reset()
        self.viewport.update()
        self.on_done(rec)

    claimed_keys = frozenset({Qt.Key_C, Qt.Key_Tab})

    def on_key(self, viewport, key, modifiers) -> bool:
        if compat.typed_value(viewport):
            return super().on_key(viewport, key, modifiers)
        if key == Qt.Key_Tab and self.rec.get("shape") in ("L", "U"):
            # the second run to the other side
            self.rec = dict(self.rec, turn="left" if self.rec.get("turn") !=
                            "left" else "right")
            viewport.update()
            return True
        if key == Qt.Key_Backspace and self.a is not None:
            self._reset()
            viewport.update()
            return True
        return super().on_key(viewport, key, modifiers)

    def rubber_band_lines(self):
        if self.a is None or self.hover is None:
            return []
        return [(self._P(self.a), self._P(self.hover))]

    def value_label(self):
        if self.a is None or self.hover is None:
            return None
        ang = self._angle(self.hover)
        L, zs, ze = self.length_at(self.a)
        return (f"{compat.fmt_len(L)}  {compat.fmt_level(zs, unit=False)} → "
                f"{compat.fmt_level(ze, unit=False)}"
                + (f"   {ang % 360:.0f}°" if ang is not None else ""), None)

    def status_clause(self) -> str:
        if self.a is None:
            return "Ramp: click where it starts (its first edge)"\
                "  ·  Esc = done"
        tab = "  ·  Tab = turn the other way" if self.rec.get("shape") in (
            "L", "U") else ""
        return ("Ramp: click the way it goes — or type its direction (°) + "
                f"Enter{tab}  ·  Backspace = start again  ·  Esc = drop")

    def layout(self, r: dict) -> list:
        """The pieces of the element placed as ``r`` (x, y, angle)."""
        L, zs, ze = self.length_at((r["x"], r["y"]))
        return pieces(r, zs, ze, max(L, 0.01))

    def marks(self, viewport, painter, pc: dict) -> None:
        """Lines drawn on a piece (a stair's treads); none for a ramp."""

    def draw_overlay(self, viewport, painter) -> None:
        super().draw_overlay(viewport, painter)
        p = self.hover if self.a is None else self.a
        if p is None:
            return
        ang = self._angle(self.hover) if self.a is not None else None
        if ang is None:
            ang = float(self.rec.get("angle", 0.0))
        r = dict(self.rec, x=p[0], y=p[1], angle=ang)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        fill = QColor(ACCENT)
        fill.setAlpha(40 if self.a is None else 70)
        for pc in self.layout(r):
            pts = [compat.to_pixel(viewport, x, y, self.z)
                   for x, y in piece_corners(pc)]
            if not all(pts):
                continue
            flat = not pc.get("run", True)
            painter.setBrush(fill)
            painter.setPen(QPen(QColor(ACCENT), 2.0, Qt.DashLine
                                if self.a is None else Qt.SolidLine))
            painter.drawPolygon(QPolygonF([QPointF(*q) for q in pts]))
            self.marks(viewport, painter, pc)
            if flat:                      # the landing: no arrow
                continue
            # the arrow down the run's middle, the way it runs
            (cx, cy), (dx, dy) = pc["c"], pc["d"]
            a0 = compat.to_pixel(viewport, cx, cy, self.z)
            a1 = compat.to_pixel(viewport, cx + dx * pc["l"],
                                 cy + dy * pc["l"], self.z)
            if a0 and a1:
                painter.setPen(QPen(QColor(ACCENT), 2.4))
                painter.drawLine(QPointF(*a0), QPointF(*a1))
                g = math.atan2(a1[1] - a0[1], a1[0] - a0[0])
                for s in (-1, 1):
                    painter.drawLine(QPointF(*a1), QPointF(
                        a1[0] - 14 * math.cos(g + s * 0.45),
                        a1[1] - 14 * math.sin(g + s * 0.45)))
        painter.restore()
