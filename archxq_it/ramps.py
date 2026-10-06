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
           "anchor": "centre"}
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


def owner(r: dict, doc: dict, elevations):
    """The level a ramp / stair belongs to: the LOWER of its two levels —
    the storey whose space it takes, drawn going up or down (his test,
    2026-10-05: a stair drawn down from Basement 1 sat in Basement 2's
    space but was listed under Basement 1). The start on the terrain: the
    ground floor; an elevation at its end: the level it starts on."""
    zs_of = level_z(doc, elevations)
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
    ld = max(float(r.get("landing", 3.0)), 0.5)
    return [run1,
            {"c": P(l1, sg * w / 2), "d": u, "l": ld, "w": 2 * w, "z0": zm,
             "z1": zm, "run": False},
            {"c": P(l1, sg * w), "d": (-u[0], -u[1]), "l": l2, "w": w,
             "z0": zm, "z1": ze, "run": True}]


def piece_corners(p: dict) -> list:
    """A piece's four corners in plan, counter-clockwise."""
    (cx, cy), (dx, dy) = p["c"], p["d"]
    rx, ry = dy, -dx                  # its right
    h, l = p["w"] / 2, p["l"]
    pts = [(cx + rx * h, cy + ry * h), (cx + rx * h + dx * l, cy + ry * h + dy * l),
           (cx - rx * h + dx * l, cy - ry * h + dy * l), (cx - rx * h, cy - ry * h)]
    a = sum(p_[0] * q[1] - q[0] * p_[1] for p_, q in zip(pts, pts[1:] + pts[:1]))
    return pts if a > 0 else list(reversed(pts))


def footprints(r: dict, zs: float, ze: float, L: float) -> list:
    """Every piece's outline in plan (what the slab above loses)."""
    return [piece_corners(p) for p in pieces(r, zs, ze, L)]


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
    for p in pieces(r, zs, ze, L):
        (cx, cy), (dx, dy) = p["c"], p["d"]
        rx, ry = dy, -dx

        def P(x, y, z, cx=cx, cy=cy, dx=dx, dy=dy, rx=rx, ry=ry):
            return (cx + rx * x + dx * y, cy + ry * x + dy * y, z)
        # its top 1 mm under the floor it leaves: never the same plane
        # (black squares — the 1 mm rule)
        z0, z1, l = p["z0"] - 0.001, p["z1"] - 0.001, p["l"]
        prof = [(0.0, z0 - t + 0.001), (l, z1 - t + 0.001), (l, z1), (0.0, z0)]
        out += _sweep(prof, -p["w"] / 2, p["w"] / 2, P, COLOR + (1.0,))
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

    def __init__(self, doc: dict, elevations, rec: dict, form, metres):
        self.doc, self.elevations = doc, elevations
        zs_of = level_z(doc, elevations)
        self.f_top = QComboBox()
        if doc.get("plot"):
            self.f_top.addItem("The terrain (the ground at its top)",
                               "terrain")
        self.f_bottom = QComboBox()
        # the highest level's top: a stair up inside it, no level over it
        hi = max(doc["levels"], key=lambda lv: zs_of[lv["id"]])
        self.f_top.addItem(f"Top of {hi['name']}  "
                           f"({zs_of[hi['id']] + float(hi['height']):+.2f})",
                           TOP + hi["id"])
        for box in (self.f_top, self.f_bottom):
            for lv in reversed(doc["levels"]):
                box.addItem(f"{lv['name']}  ({zs_of[lv['id']]:+.2f})",
                            lv["id"])
            box.addItem("An elevation", "z")
        self.f_z = metres(float(rec.get("to_z", -3.0)), -100.0, 100.0)
        self.f_start = QComboBox()
        self.f_start.addItem("Bottom step — going up", "bottom")
        self.f_start.addItem("Top step — going down", "top")
        self.f_start.setToolTip("Where your click is on the plan: at its "
                                "bottom (the usual way) or at its top (a "
                                "ramp from the street, a slab's edge)")
        # where it is now: the clicked end is «from» (or the terrain)
        a = "terrain" if rec.get("start") == "terrain" else from_level(rec)
        b = rec.get("to") or "z"
        za = None if a == "terrain" else end_z(doc, elevations, a)
        zb = float(rec.get("to_z", 0.0)) if b == "z" else end_z(doc,
                                                               elevations, b)
        top_first = a == "terrain" or (za is not None and zb is not None
                                       and za >= zb)
        top, bottom = (a, b) if top_first else (b, a)
        self.f_top.setCurrentIndex(max(self.f_top.findData(top), 0))
        self.f_bottom.setCurrentIndex(max(self.f_bottom.findData(bottom), 0))
        self.f_start.setCurrentIndex(1 if top_first else 0)
        # «From / To» as he reads them (2026-10-05): «To» — the upper end —
        # over «From» — the lower one — as a section reads
        self.f_top.setToolTip("The upper end: a level, the top of the "
                              "highest level, the terrain or an elevation")
        self.f_bottom.setToolTip("The lower end: a level or an elevation")
        form.addRow("To", self.f_top)
        form.addRow("From", self.f_bottom)
        form.addRow("Elevation", self.f_z)
        form.addRow("Starts at", self.f_start)

    def widgets(self):
        return (self.f_top, self.f_bottom, self.f_start)

    def sync(self) -> None:
        top, bot = self.f_top.currentData(), self.f_bottom.currentData()
        self.f_z.setEnabled("z" in (top, bot))
        on_ground = top == "terrain"
        if on_ground:                     # the ground is read at the click
            self.f_start.setCurrentIndex(1)
        self.f_start.setEnabled(not on_ground)

    def write(self, r: dict) -> None:
        """Its ends into the record (start, from, to, to_z) — a top chosen
        lower than the bottom is turned the right way round."""
        top, bot = self.f_top.currentData(), self.f_bottom.currentData()
        zs_of = level_z(self.doc, self.elevations)
        zt = end_z(self.doc, self.elevations, top)
        zb = end_z(self.doc, self.elevations, bot)
        if zt is not None and zb is not None and zt < zb and \
                not str(top).startswith(TOP):
            top, bot = bot, top
        at_top = top == "terrain" or self.f_start.currentData() == "top"
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
        top, bot = self.f_top.currentData(), self.f_bottom.currentData()
        if top == bot:
            return "The top and the bottom are the same level"
        at_top = top == "terrain" or self.f_start.currentData() == "top"
        if (top if at_top else bot) == "z":
            return ("It starts on a level (or the terrain) — an elevation "
                    "can only be its other end")
        return None


def _anchor_box(rec: dict) -> QComboBox:
    """«Insert at»: where the click is on its first edge (stairs.py too)."""
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
        zs_txt = f"{self.zs:+.2f}" + ("" if self.known else " (the ground)")
        p.drawText(QRectF(a.x() - 10, a.y() - 26, 200, 20), Qt.AlignLeft,
                   zs_txt)
        p.drawText(QRectF(b.x() - 190, b.y() + th + 6, 200, 20),
                   Qt.AlignRight, f"{self.ze:+.2f}")
        mid = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
        p.setPen(QColor(ACCENT))
        p.drawText(QRectF(mid.x() - 120, mid.y() + (16 if down else -36), 240,
                          20), Qt.AlignCenter,
                   f"{self.slope:g} %  ·  {self.L:.2f} m"
                   + (" (runs)" if land else ""))


class RampDialog(QDialog):
    """Set a ramp up (``edit`` False: before drawing it) or change one
    (``edit`` True: its name, where it is, delete). ``result_data()`` →
    (action, record) — action "apply" | "delete"."""

    def __init__(self, rec: dict, doc: dict, elevations, edit: bool = False,
                 parent=None) -> None:
        from .dialogs import _metres, ok_apply
        from .help import help_button
        super().__init__(parent)
        self.rec = dict(rec)
        self.doc = doc
        self.elevations = elevations
        self.edit = edit
        self.action = "apply"
        self.setWindowTitle("Ramp")
        self.setMinimumWidth(640)
        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        title = QLabel(rec.get("name") or "Ramp")
        f = title.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        title.setFont(f)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(help_button("ramp"))
        lay.addLayout(head)

        body = QHBoxLayout()
        form = QFormLayout()
        levels = doc["levels"]
        self.f_name = None
        if edit:
            self.f_name = QLineEdit(rec.get("name", ""))
            form.addRow("Name", self.f_name)
        # WHERE — its top over its bottom, and where the click is
        self.ends = _Ends(doc, elevations, rec, form, _metres)
        # SIZE
        self.f_w = _metres(float(rec.get("w", 3.0)), 0.5, 30.0)
        form.addRow("Width", self.f_w)
        self.f_slope = QDoubleSpinBox()
        self.f_slope.setRange(SLOPE_MIN, SLOPE_MAX)
        self.f_slope.setDecimals(1)
        self.f_slope.setSingleStep(1.0)
        self.f_slope.setSuffix(" %")
        self.f_slope.setValue(float(rec.get("slope", 20.0)))
        self.f_slope.setToolTip("How steep: 20 % is usual for cars, 8 % for "
                                "people — the length follows from it")
        form.addRow("Slope", self.f_slope)
        # the length too, for special cases: type it and the slope follows
        self.fix = rec.get("fix", "slope")
        self._quiet = False
        self.f_len = _metres(float(rec.get("L", 15.0)), 0.5, 500.0, 0.10)
        self.f_len.setToolTip("Type a length for a special case: the slope "
                              "then follows from it")
        form.addRow("Length", self.f_len)
        self.f_hint = QLabel()
        self.f_hint.setEnabled(False)
        form.addRow("", self.f_hint)
        self.f_t = _metres(float(rec.get("t", 0.15)), 0.05, 1.0, 0.01)
        form.addRow("Thickness", self.f_t)
        # SHAPE — straight, or turning on a level landing (L: 90°, U: back)
        from PySide6.QtWidgets import QButtonGroup
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        self.g_shape = QButtonGroup(self)
        for key, text, tip in (("straight", "Straight", "One run"),
                               ("L", "L", "Two runs, a landing, a 90° turn"),
                               ("U", "U", "Two runs side by side, a landing "
                                          "across both")):
            b = QPushButton(text)
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setProperty("shape", key)
            b.setChecked(rec.get("shape", "straight") == key)
            self.g_shape.addButton(b)
            rl.addWidget(b)
        rl.addStretch()
        # the shape picked has to be seen at a glance
        row.setStyleSheet(
            f"QPushButton {{ padding: 4px 16px; min-width: 70px; }}"
            f"QPushButton:checked {{ border: 1px solid {ACCENT}; "
            "background: #4a3324; color: white; font-weight: bold; }")
        form.addRow("Shape", row)
        self.f_turn = QComboBox()
        self.f_turn.addItem("Turning right", "right")
        self.f_turn.addItem("Turning left", "left")
        self.f_turn.setCurrentIndex(1 if rec.get("turn") == "left" else 0)
        self.f_turn.setToolTip("The side the second run goes to (Tab, while "
                               "placing it, swaps it)")
        form.addRow("Turn", self.f_turn)
        self.f_land = _metres(float(rec.get("landing", 3.0)), 0.5, 50.0)
        self.f_land.setToolTip("The level landing between the two runs (an "
                               "L's is never shorter than the ramp is wide)")
        form.addRow("Landing", self.f_land)
        self.f_anchor = _anchor_box(rec)
        form.addRow("Insert at", self.f_anchor)
        if edit:                          # where it is (the tool set it)
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
        body.addLayout(form, 1)
        self.profile = _Profile()
        body.addWidget(self.profile, 1)
        lay.addLayout(body)
        if not edit:
            note = QLabel("OK opens the plan: click where it starts (its "
                          "bottom or its top — «Starts at»; a corner or the "
                          "middle — «Insert at»), then the way it goes.")
            note.setWordWrap(True)
            note.setEnabled(False)
            lay.addWidget(note)
        acts = QHBoxLayout()
        acts.addStretch()
        if edit:
            from .dialogs import hide_button
            acts.addWidget(_repeat_button(self, "ramp"))
            acts.addWidget(hide_button(self))
            b_del = QPushButton("Delete ramp")
            b_del.clicked.connect(self._delete)
            acts.addWidget(b_del)
        lay.addLayout(acts)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        if edit:
            ok_apply(self, bb)
        else:
            bb.button(QDialogButtonBox.Ok).setText("OK — place it")
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        for w in self.ends.widgets():
            w.currentIndexChanged.connect(self._sync)
        for w in (self.ends.f_z, self.f_w, self.f_t, self.f_land):
            w.valueChanged.connect(self._sync)
        self.f_turn.currentIndexChanged.connect(self._sync)
        self.g_shape.buttonClicked.connect(self._sync)
        self.f_slope.valueChanged.connect(lambda _v: self._given("slope"))
        self.f_len.valueChanged.connect(lambda _v: self._given("length"))
        if edit:
            for w in (self.f_x, self.f_y):
                w.valueChanged.connect(self._sync)
        self._sync()

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
        b = self.g_shape.checkedButton()
        r["shape"] = b.property("shape") if b is not None else "straight"
        r["turn"] = self.f_turn.currentData()
        r["landing"] = round(self.f_land.value(), 3)
        r["anchor"] = self.f_anchor.currentData()
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
        return (f"{L:.2f} m  {zs:+.2f} → {ze:+.2f}"
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
