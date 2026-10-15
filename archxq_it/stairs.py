"""STAIRS — the second «Building element» (plan PLANO_RAMPA_ESCADA.md,
steps 3–4): from a level (or the ground) to another, straight, L or U —
its steps worked out by Blondel's rule.

Like a ramp (ramps.py) it is one more type in ``doc["structure"]``
(``type="stair"``) and shares the ramp's plan layout (runs + a level
landing, ``ramps.pieces``), its window's From / To and its tool. What is
its own: the steps.

    risers  n = ceil(drop / riser max)      (riser max 0.18)
    riser   h = drop / n
    tread   p = 0.63 − 2h  (Blondel: 2h + p = 63 cm), kept in 0.25–0.32
            — or typed (``fix_tread``)
    a run of m risers has m − 1 treads: (m − 1) · p long — its last riser
    lands on the landing / the floor.

The record: as a ramp's (start, level, to, to_z, x, y, angle, w, shape,
turn, landing, t) + riser (the max), tread, fix_tread.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QButtonGroup,
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
from . import ramps as R
from .plottools import ACCENT

COLOR = (0.76, 0.76, 0.75)       # concrete
DEFAULT = {"start": "level", "to": "", "to_z": -3.0, "w": 1.20,
           "riser": 0.18, "tread": 0.28, "fix_tread": False, "t": 0.15,
           "shape": "straight", "turn": "right", "landing": 1.20,
           "anchor": "centre", "split": 0, "gap": 0.0, "nosing": 0.0,
           "build": "concrete",
           "cut": True}            # its opening in the slab (False: none)
#: open treads: each tread a board on two steel stringers
TREAD_T = 0.05
STRINGER = (0.60, 0.62, 0.64, 1.0)        # = railings.STEEL: painted as one
STRINGER_T, STRINGER_D = 0.015, 0.25
BLONDEL = 0.63


# ---- the steps -------------------------------------------------------------------------
def steps(r: dict, zs: float, ze: float) -> dict:
    """{n, h (signed: + up), p, n1, n2, l1, l2, L, zm} for this drop."""
    H = ze - zs
    n = max(1, math.ceil(abs(H) / max(float(r.get("riser", 0.18)), 0.05)
                         - 1e-9))
    h = H / n
    if r.get("fix_tread"):
        p = float(r.get("tread", 0.28))
    else:
        p = min(max(BLONDEL - 2 * abs(h), 0.25), 0.32)
    if r.get("shape") in ("L", "U"):
        # the landing after riser N («split», typed) — 0: halfway
        k = int(r.get("split", 0) or 0)
        n1 = min(max(k, 2), n - 2) if k and n >= 4 else math.ceil(n / 2)
        n2 = n - n1
    else:
        n1, n2 = n, 0
    l1 = max(n1 - 1, 0) * p
    l2 = max(n2 - 1, 0) * p
    return {"n": n, "h": h, "p": p, "n1": n1, "n2": n2, "l1": l1, "l2": l2,
            "L": l1 + l2, "zm": zs + n1 * h}


def layout(r: dict, zs: float, ze: float) -> list:
    """The plan pieces (ramps.pieces) with the stair's own runs; each run
    knows its risers ("m") and its riser ("h")."""
    s = steps(r, zs, ze)
    ps = R.pieces(r, zs, ze, s["L"], l1=s["l1"], l2=s["l2"], zm=s["zm"])
    runs = [pc for pc in ps if pc.get("run", True)]
    if runs:
        runs[0]["m"] = s["n1"]
    if len(runs) > 1:
        runs[1]["m"] = s["n2"]
    for pc in ps:
        pc["h"], pc["p"] = s["h"], s["p"]
    return ps


def why_not(r: dict) -> str | None:
    try:
        if float(r["w"]) < 0.6:
            return "A stair needs 60 cm of width at least"
        if not 0.10 <= float(r.get("riser", 0.18)) <= 0.25:
            return "A stair's riser goes from 10 to 25 cm"
        if r.get("fix_tread") and not 0.15 <= float(r["tread"]) <= 0.60:
            return "A stair's tread goes from 15 to 60 cm"
        if float(r["t"]) < 0.05:
            return "A stair needs a thickness of 5 cm at least"
        float(r["x"]), float(r["y"])
    except (KeyError, TypeError, ValueError):
        return "Incomplete stair"
    return None


def _run_profile(m: int, z0: float, h: float, p: float, t: float,
                 nos: float = 0.0) -> list:
    """A run of ``m`` risers from ``z0`` (riser ``h``, signed), its side
    profile (along, z) counter-clockwise: the treads on top, the waist
    under them. Going down it starts on its first tread (the floor's edge
    is the first riser); going up its first riser stands on the floor.
    ``nos``: each tread's nosing — a lip over the riser below it (going
    up at its start, going down at its end), 3 cm thick at most."""
    L = (m - 1) * p
    z1 = z0 + m * h
    tn = min(0.03, abs(h) / 2)
    tops = []
    for k in range(1, m):
        zk = z0 + k * h
        s0, s1 = (k - 1) * p, k * p
        if nos > 1e-4 and h > 0:            # the lip at its start
            tops += [(s0, zk - tn), (s0 - nos, zk - tn), (s0 - nos, zk),
                     (s1, zk)]
        elif nos > 1e-4:                     # going down: at its end
            tops += [(s0, zk), (s1 + nos, zk), (s1 + nos, zk - tn),
                     (s1, zk - tn)]
        else:
            tops += [(s0, zk), (s1, zk)]
    # the waist: under the line through the treads' inner corners
    b0 = z0 + min(h, 0.0) - t
    b1 = z1 - max(h, 0.0) - t
    return [(0.0, b0), (L, b1)] + list(reversed(tops))


def faces(r: dict, doc: dict, elevations) -> list:
    from .structure import _sweep
    zs, ze = R.heights(r, doc, elevations)
    if abs(zs - ze) < 0.05:
        return []
    t = float(r["t"])
    out = []
    ps = layout(r, zs, ze)
    try:
        from . import railings as RL       # its guards (Pro only)
    except ImportError:
        RL = None
    # a low wall keeps to the flight's edge: the body gives way 1 cm there
    lt, rt = RL.body_trim(r, ps, ze > zs, True, doc)[:2] if RL else (0, 0)
    walls = RL.wall_plan(r, ps, ze > zs, True, doc) if RL else None
    nos = min(max(float(r.get("nosing", 0.0) or 0.0), 0.0), 0.05)
    open_ = r.get("build") == "open"
    for pc in ps:
        (cx, cy), (dx, dy) = pc["c"], pc["d"]
        rx, ry = dy, -dx

        def P(x, y, z, cx=cx, cy=cy, dx=dx, dy=dy, rx=rx, ry=ry):
            return (cx + rx * x + dx * y, cy + ry * x + dy * y, z)
        if pc.get("run", True):
            m = pc.get("m", 0)
            if m < 2:
                continue                  # one riser: nothing to tread on
            a0, a1 = -pc["w"] / 2 + lt, pc["w"] / 2 - rt
            if open_:
                out += _open_run(pc, P, a0, a1, nos)
                continue
            prof = _run_profile(m, pc["z0"], pc["h"], pc["p"], t, nos)
        else:
            # the landing: thick enough to meet the next run's first
            # riser; its top 1 mm under (never the floor's plane)
            z = pc["z0"] - 0.001
            tl = t + abs(pc["h"])
            if walls is not None:
                out += landing_round(pc, walls, z - tl, z)
                continue
            prof = [(0.0, z - tl), (pc["l"], z - tl), (pc["l"], z), (0.0, z)]
            a0, a1 = -pc["w"] / 2, pc["w"] / 2
        out += _sweep(prof, a0, a1, P, COLOR + (1.0,))
    if RL is not None:
        out += RL.faces(r, ps, ze > zs, True, doc)
    return out


def _open_run(pc: dict, P, a0: float, a1: float, nos: float) -> list:
    """A run of OPEN treads (his Part B, 2026-10-10 — the modern house's):
    each tread a board ``TREAD_T`` thick, no risers, on two steel
    stringers under its ends; the stringers' top runs under the treads'
    back corners."""
    from .structure import _sweep
    m, z0, h, p = pc["m"], pc["z0"], pc["h"], pc["p"]
    L = (m - 1) * p
    out = []
    for k in range(1, m):
        zk = z0 + k * h
        s0 = (k - 1) * p - (nos if h > 0 else 0.0)
        s1 = k * p + (nos if h < 0 else 0.0)
        out += _sweep([(s0, zk - TREAD_T), (s1, zk - TREAD_T), (s1, zk),
                       (s0, zk)], a0, a1, P, COLOR + (1.0,))
    top0 = z0 + (h if h < 0 else 0.0) - TREAD_T        # its top at s = 0
    topL = top0 + L * h / p
    prof = [(0.0, top0 - STRINGER_D), (L, topL - STRINGER_D), (L, topL),
            (0.0, top0)]
    inset = 0.06
    for b0 in (a0 + inset, a1 - inset - STRINGER_T):
        out += _sweep(prof, b0, b0 + STRINGER_T, P, STRINGER)
    return out


def landing_round(pc: dict, walls, z0: float, z1: float,
                  color=None) -> list:
    """A landing with low walls round it: it gives way to them — its edge
    1 cm INSIDE each wall, never in a wall's face (at an L's inner corner
    its lower faces lay in the wall's: the flush check, 2026-10-10; his
    rule: the inner part gives way)."""
    from shapely.geometry import Polygon

    from .walls import solid
    from .structure import _faces
    rect = Polygon(R.piece_corners(pc))
    try:
        # (2 mm over: on the wall's exact edge the difference left slivers
        # that the 1 cm grew into a strip in the wall's face)
        body = rect.difference(walls.buffer(0.002, join_style=2)) \
            .buffer(0.012, join_style=2).intersection(rect)
        # and 3 cm in from the flight's outer edges under a wall (railings.
        # BODY_IN: its edges showed through the wall's face from afar)
        body = body.difference(rect.exterior.buffer(0.03, join_style=2)
                               .intersection(walls.buffer(0.002,
                                                          join_style=2)))
    except Exception:  # noqa: BLE001 — as it was
        body = rect
    out = []
    for g in getattr(body, "geoms", [body]):
        if g.is_empty or g.geom_type != "Polygon" or g.area < 1e-4:
            continue
        loop = list(g.exterior.coords)[:-1]
        a = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(loop, loop[1:]
                                                         + loop[:1]))
        if a < 0:
            loop.reverse()
        holes = []
        for h in g.interiors:
            hl = list(h.coords)[:-1]
            b = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(hl, hl[1:]
                                                             + hl[:1]))
            holes.append(hl if b < 0 else list(reversed(hl)))
        out += _faces(solid({"outer": loop, "holes": holes}, z0, z1),
                      color or COLOR + (1.0,))
    return out


def footprints(r: dict, doc: dict, elevations) -> list:
    zs, ze = R.heights(r, doc, elevations)
    return [R.piece_corners(pc) for pc in layout(r, zs, ze)]


def well(r: dict, doc: dict, elevations) -> list:
    """What the slab above loses: the footprints, but never back past the
    line where the last flight lands on the upper floor. In a U with an odd
    count the first flight is one tread longer than the second — its foot
    stands under the floor above, with headroom to spare (a customer's
    catch, 2026-10-10: that tread's strip cut the upper floor's beam).
    Going DOWN the first flight leaves the upper floor: nothing to trim."""
    zs, ze = R.heights(r, doc, elevations)
    return well_of(r, layout(r, zs, ze), ze > zs)


def well_of(r: dict, ps: list, up: bool) -> list:
    """``well`` for a stair already laid out (its pieces ``ps``)."""
    ps = list(ps)
    if r.get("shape") == "U" and len(ps) == 3 and up:
        run1, run2 = ps[0], ps[2]
        extra = run1["l"] - run2["l"]
        if extra > 1e-6:
            (cx, cy), (dx, dy) = run1["c"], run1["d"]
            ps[0] = dict(run1, c=(cx + dx * extra, cy + dy * extra),
                         l=run2["l"])
    out = [R.piece_corners(pc) for pc in ps]
    if r.get("shape") == "U" and float(r.get("gap", 0.0) or 0.0) > 0.005:
        # the well between the flights is open too: the whole stretch
        # from the runs' start to the landing
        xs = [p for poly in out for p in poly]
        try:
            from shapely.geometry import MultiPoint
            hull = MultiPoint(xs).convex_hull
            out = [list(hull.exterior.coords)[:-1]]
        except Exception:  # noqa: BLE001 — the pieces as they are
            pass
    return out


# ---- its window ------------------------------------------------------------------------
class _Steps(QWidget):
    """The stair seen from its side (unfolded): its steps, the landing."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(280, 210)
        self.r = None
        self.zs = self.ze = 0.0
        self.known = True

    def set(self, r, zs, ze, known=True) -> None:
        self.r, self.zs, self.ze, self.known = r, zs, ze, known
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#1d2025"))
        if self.r is None or abs(self.zs - self.ze) < 0.05:
            p.setPen(QColor("#9aa0a6"))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "Same height at both ends —\nno steps")
            return
        s = steps(self.r, self.zs, self.ze)
        land = 0.0
        if self.r.get("shape") in ("L", "U"):
            land = max(float(self.r.get("landing", 1.2)), float(self.r["w"])) \
                if self.r["shape"] == "L" else float(self.r.get("landing", 1.2))
        # the steps, unfolded, true to scale
        pts = []
        z, x = self.zs, 0.0
        for run, m in ((1, s["n1"]), (2, s["n2"])):
            if m == 0:
                continue
            for k in range(m):
                pts += [(x, z), (x, z + s["h"])]
                z += s["h"]
                if k < m - 1:
                    pts.append((x + s["p"], z))
                    x += s["p"]
            if run == 1 and s["n2"]:
                pts.append((x + land, z))
                x += land
        W = max(x, 0.5)
        lo, hi = min(self.zs, self.ze), max(self.zs, self.ze)
        rr = self.rect().adjusted(16, 34, -16, -34)
        k = min(rr.width() / W, rr.height() / (hi - lo))
        x0 = rr.left() + (rr.width() - W * k) / 2
        y0 = rr.top() + (rr.height() - (hi - lo) * k) / 2

        def q(a, b):
            return QPointF(x0 + a * k, y0 + (hi - b) * k)
        p.setPen(QPen(QColor(ACCENT), 2.2))
        for a, b in zip(pts, pts[1:]):
            p.drawLine(q(*a), q(*b))
        f = QFont(p.font())
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#e6e6e6"))
        p.drawText(QRectF(x0 - 6, q(0, self.zs).y() - 24, 200, 18),
                   Qt.AlignLeft, f"{self.zs:+.2f}"
                   + ("" if self.known else " (the ground)"))
        end = q(x, self.ze)
        p.drawText(QRectF(end.x() - 194, end.y() + 6, 200, 18),
                   Qt.AlignRight, f"{self.ze:+.2f}")


def summary(s: dict) -> str:
    return (f"{s['n']} risers × {abs(s['h']) * 100:.1f} cm · tread "
            f"{s['p'] * 100:.1f} cm · 2h+p = "
            f"{(2 * abs(s['h']) + s['p']) * 100:.1f} cm")


# ---- its window's drawings (the windows of 0.10.0 — look.py) ---------------------------
def _ic_stair(p, r, _on):
    from . import look as L
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#3a2f1c"))
    p.drawRoundedRect(r, 8, 8)
    L.poly(p, [(7, 32), (13, 32), (13, 26), (19, 26), (19, 20), (25, 20),
               (25, 14), (31, 14), (31, 8)], L.GOLD, 2.6)


def _draw_levels(p, r, hot, d):
    """Its two ends, the height between them."""
    from . import look as L
    p.setPen(L.pen("#8a8f96", 3.0))
    p.drawLine(QPointF(8, 78), QPointF(60, 78))
    p.drawLine(QPointF(90, 22), QPointF(142, 22))
    pts = [(60, 78)]
    for k in range(4):
        x, y = 60 + k * 8, 78 - k * 14
        pts += [(x, y - 14), (x + 8, y - 14)]
    p.setPen(L.pen(L.INK, 1.4, dash=True))
    from PySide6.QtGui import QPolygonF
    p.drawPolyline(QPolygonF([QPointF(*q) for q in pts]))
    L.dim(p, (144, 22), (144, 78), "", hot == "z")
    L.text(p, 139, 54, d.get("h", ""), L.GOLD if hot == "z" else L.BLUE,
           align=Qt.AlignRight)
    L.text(p, 8, 72, d.get("lo", ""), L.MUTED, 7, False)
    L.text(p, 90, 16, d.get("hi", ""), L.MUTED, 7, False)


def _draw_steps(p, r, hot, d):
    """A flight's profile: riser R, tread T, nosing N, thickness t."""
    from . import look as L
    L.poly(p, [(8, 100), (8, 72), (52, 72), (52, 44), (96, 44), (96, 16),
               (142, 16)], L.INK, 2.0)
    L.poly(p, [(8, 100), (142, 30), (142, 16)], L.DIM, 1.2)
    p.setPen(L.pen(L.INK, 2.0))
    for x, y in ((52, 72), (96, 44)):            # the nosings
        p.drawLine(QPointF(x, y), QPointF(x - 4, y))
    L.dim(p, (62, 44), (62, 72), "R", hot == "riser", at=(66, 63))
    L.dim(p, (52, 36), (96, 36), "T", hot == "tread", at=(70, 31))
    L.dim(p, (44, 80), (52, 80), "", hot == "nosing", ticks=False)
    L.text(p, 40, 93, "N", L.GOLD if hot == "nosing" else L.BLUE)
    L.dim(p, (112, 22), (118, 38), "", hot == "t", ticks=False)
    L.text(p, 121, 46, "t", L.GOLD if hot == "t" else L.BLUE)


def _pic_shape(shape):
    def draw(p, r, _on):
        from . import look as L
        lines = L.DIM
        if shape == "straight":
            L.poly(p, [(22, 2), (38, 2), (38, 42), (22, 42)], L.INK, 1.5, close=True)
            p.setPen(L.pen(lines, 1.0))
            for y in (10, 18, 26, 34):
                p.drawLine(QPointF(22, y), QPointF(38, y))
            L.poly(p, [(30, 40), (30, 6)], L.BLUE, 1.4)
            L.poly(p, [(27, 10), (30, 6), (33, 10)], L.BLUE, 1.4)
        elif shape == "L":
            L.poly(p, [(14, 42), (14, 2), (46, 2), (46, 18), (30, 18), (30, 42)],
                   L.INK, 1.5, close=True)
            p.setPen(L.pen(lines, 1.0))
            for y in (26, 34):
                p.drawLine(QPointF(14, y), QPointF(30, y))
            for x in (34, 40):
                p.drawLine(QPointF(x, 2), QPointF(x, 18))
            L.poly(p, [(22, 40), (22, 10), (43, 10)], L.BLUE, 1.4)
        else:
            L.poly(p, [(12, 42), (12, 2), (48, 2), (48, 42), (32, 42), (32, 16),
                       (28, 16), (28, 42)], L.INK, 1.5, close=True)
            p.setPen(L.pen(lines, 1.0))
            for y in (24, 32):
                p.drawLine(QPointF(12, y), QPointF(28, y))
                p.drawLine(QPointF(32, y), QPointF(48, y))
            L.poly(p, [(20, 40), (20, 9), (40, 9), (40, 39)], L.BLUE, 1.4)
    return draw


def _pic_build(kind):
    def draw(p, r, _on):
        from . import look as L
        if kind == "concrete":
            L.poly(p, [(5, 46), (5, 36), (25, 36), (25, 26), (45, 26), (45, 16),
                       (65, 16), (65, 6), (85, 6), (85, 16), (25, 46)],
                   L.INK, 1.0, fill="#8a8f96")
        else:
            p.setPen(L.pen("#9aa6b2", 3.0))
            p.drawLine(QPointF(5, 46), QPointF(90, 8))
            p.setPen(L.pen("#c49a6c", 4.0))
            for x, y in ((8, 38), (28, 29), (48, 20), (68, 11)):
                p.drawLine(QPointF(x, y), QPointF(x + 18, y))
    return draw


def _pic_turn(way):
    def draw(p, r, _on):
        from . import look as L
        sg = 1 if way == "right" else -1
        x0 = 30 - sg * 6
        L.poly(p, [(x0, 22), (x0, 8), (x0 + sg * 14, 8)], L.BLUE, 1.8)
        L.poly(p, [(x0 + sg * 10, 4), (x0 + sg * 14, 8), (x0 + sg * 10, 12)],
               L.BLUE, 1.8)
    return draw


class _Plan(R.FlightPlan):
    """The stair seen from above, live: its flights, their treads, the
    landing, the way up (ramps.FlightPlan)."""

    EMPTY = "Same height at both ends —\nno steps"

    def pieces(self, r) -> list:
        return layout(r, self.zs, self.ze)

class StairDialog(QDialog):
    """Set a stair up (``edit`` False) or change one (``edit`` True).
    ``result_data()`` → (action, record).

    The window of 0.10.0 (look.py; mockup MAQUETAS/janela_escada_v1.html,
    approved 2026-10-13): tabs Geometry · Build · Railing · Position (+
    Material, materials.with_tab), folds with drawings, picture chips, a live
    plan / side preview with its numbers and Blondel's check. The fields and
    the record are the old window's."""

    def __init__(self, rec: dict, doc: dict, elevations, edit: bool = False,
                 parent=None) -> None:
        from . import look as L
        from .dialogs import _metres, ok_apply
        super().__init__(parent)
        self.rec, self.doc, self.elevations = dict(rec), doc, elevations
        self.edit = edit
        self.action = "apply"
        self.setWindowTitle("Stair")
        self.setMinimumWidth(900)
        L.dress(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(6)
        self.head = L.Header(_ic_stair, rec.get("name") or "Stair", "stair",
                             editable=edit)
        self.f_name = self.head.name if edit else None
        lay.addWidget(self.head)
        self.tabs = L.Tabs()
        self._axq_tabs = self.tabs            # materials.with_tab: «Material»
        lay.addWidget(self.tabs.bar)
        lay.addWidget(L.rule())

        # ---- Geometry ------------------------------------------------------------
        geo, gl = L.page()
        self.fold_lv = L.Fold("Levels", "stair.levels")
        self.d_lv = L.Drawing(_draw_levels, 150, 90)
        form = self.fold_lv.form(self.d_lv)
        self.ends = R._Ends(doc, elevations, rec, form, _metres, choice=L.Chips)
        self.d_lv.link(self.ends.f_z, "z")
        gl.addWidget(self.fold_lv)

        self.fold_steps = L.Fold("Steps", "stair.steps")
        self.d_steps = L.Drawing(_draw_steps, 150, 110)
        form = self.fold_steps.form(self.d_steps)
        self.f_w = L.metres(float(rec.get("w", 1.2)), 0.6, 10.0)
        form.addRow("Width", self.f_w)
        self.f_riser = L.metres(float(rec.get("riser", 0.18)), 0.10, 0.25,
                                0.005)
        self.f_riser.setDecimals(3)
        self.f_riser.setToolTip("The highest a riser may be: the count of "
                                "risers follows from it")
        form.addRow("Riser (max)", self.f_riser)
        # the tread: by Blondel, or typed (then it stays)
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        self.f_tread = L.metres(float(rec.get("tread", 0.28)), 0.15, 0.60,
                                0.005)
        self.f_tread.setDecimals(3)
        self.b_auto = QPushButton("Blondel")
        self.b_auto.setObjectName("axqChip")
        self.b_auto.setCheckable(True)
        self.b_auto.setChecked(not rec.get("fix_tread"))
        self.b_auto.setToolTip("The tread from Blondel's rule (2 risers + 1 "
                               "tread = 63 cm) — off: the tread typed")
        rl.addWidget(self.f_tread, 1)
        rl.addWidget(self.b_auto)
        form.addRow("Tread", row)
        self.f_nos = L.metres(float(rec.get("nosing", 0.0) or 0.0), 0.0,
                              0.05, 0.005)
        self.f_nos.setDecimals(3)
        self.f_nos.setValue(float(rec.get("nosing", 0.0) or 0.0))
        self.f_nos.setToolTip("Each tread's nosing over the riser below "
                              "(2–3 cm is usual; 0: none)")
        form.addRow("Nosing", self.f_nos)
        self.f_t = L.metres(float(rec.get("t", 0.15)), 0.05, 1.0, 0.01)
        form.addRow("Thickness", self.f_t)
        for w, key in ((self.f_riser, "riser"), (self.f_tread, "tread"),
                       (self.f_nos, "nosing"), (self.f_t, "t")):
            self.d_steps.link(w, key)
        gl.addWidget(self.fold_steps)

        self.fold_shape = L.Fold("Shape", "stair.shape")
        self.f_shape = L.Chips()
        for key, text, tip in (("straight", "Straight", "One flight"),
                               ("L", "L", "Two flights, a landing, a 90° "
                                          "turn"),
                               ("U", "U", "Two flights side by side, a "
                                          "landing across both")):
            self.f_shape.addItem(text, key, tip, pic=_pic_shape(key))
        self.f_shape.setCurrentIndex(max(0, self.f_shape.findData(
            rec.get("shape", "straight"))))
        self.fold_shape.box.addWidget(self.f_shape)
        form = self.fold_shape.form()
        self.f_turn = L.Chips(width=70)
        self.f_turn.addItem("Right", "right")
        self.f_turn.addItem("Left", "left")
        self.f_turn.setCurrentIndex(1 if rec.get("turn") == "left" else 0)
        form.addRow("Turn", self.f_turn)
        self.f_land = L.metres(float(rec.get("landing", 1.2)), 0.6, 20.0)
        form.addRow("Landing", self.f_land)
        from PySide6.QtWidgets import QSpinBox
        self.f_split = QSpinBox()
        self.f_split.setRange(0, 60)
        self.f_split.setSpecialValueText("Auto (halfway)")
        self.f_split.setValue(int(rec.get("split", 0) or 0))
        self.f_split.setToolTip("The landing after this riser — flights of "
                                "your choice (2 risers each at least)")
        form.addRow("Landing after riser", self.f_split)
        self.f_gap = L.metres(float(rec.get("gap", 0.0) or 0.0), 0.0, 2.0)
        self.f_gap.setToolTip("A U's well between its two flights (0: side "
                              "by side) — the floor above opens over it too")
        form.addRow("Gap between flights", self.f_gap)
        gl.addWidget(self.fold_shape)
        gl.addStretch(1)
        self.tabs.addTab(geo, "Geometry", "geometry")

        # ---- Build ---------------------------------------------------------------
        bld, bl = L.page()
        self.fold_build = L.Fold("Structure", "stair.build")
        self.f_build = L.Chips(width=140, pic=(96, 50))
        self.f_build.addItem("Concrete\na slab under the steps", "concrete",
                             pic=_pic_build("concrete"))
        self.f_build.addItem("Open treads\non two steel stringers", "open",
                             pic=_pic_build("open"))
        self.f_build.setCurrentIndex(1 if rec.get("build") == "open" else 0)
        self.fold_build.box.addWidget(self.f_build)
        bl.addWidget(self.fold_build)
        self.fold_cut = L.Fold("Opening in the slab", "stair.cut")
        self.f_cut = L.Chips()
        self.f_cut.addItem("Auto — it opens the slab it passes through", True)
        self.f_cut.addItem("None", False)
        self.f_cut.setCurrentIndex(0 if rec.get("cut", True) else 1)
        self.fold_cut.box.addWidget(self.f_cut)
        self.fold_cut.box.addWidget(L.hint(
            "None: the slab stays whole — draw an opening of your own "
            "(Structure › Slab › Opening, any shape)."))
        bl.addWidget(self.fold_cut)
        bl.addStretch(1)
        self.tabs.addTab(bld, "Build", "build")

        # ---- Railing -------------------------------------------------------------
        rail, rl_ = L.page()
        self.rails = R.RailTab(rec, rl_, L.metres, self._sync, "stair")
        rl_.addStretch(1)
        self.tabs.addTab(rail, "Railing", "railing")

        # ---- Position ------------------------------------------------------------
        pos, pl = L.page()
        self.fold_anchor = L.Fold("Insert at", "stair.anchor")
        self.f_anchor = R._anchor_box(rec, chips=True)
        self.fold_anchor.box.addWidget(self.f_anchor)
        pl.addWidget(self.fold_anchor)
        if edit:
            self.fold_place = L.Fold("Placement", "stair.place")
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
                "step or its top — «Starts at»; a corner or the middle — "
                "«Insert at»), then the way it goes."))
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
        self.plan = _Plan()
        self.view = _Steps()
        self.view.hide()
        card.box.addWidget(self.plan, 1)
        card.box.addWidget(self.view, 1)
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
            acts.addWidget(R._repeat_button(self, "stair"))
            acts.addWidget(hide_button(self))
            b_del = QPushButton("Delete stair")
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
                                        self.f_build, self.f_cut,
                                        self.f_anchor):
            w.currentIndexChanged.connect(self._sync)
        for w in (self.ends.f_z, self.f_w, self.f_riser, self.f_tread,
                  self.f_t, self.f_land, self.f_split, self.f_gap,
                  self.f_nos):
            w.valueChanged.connect(self._sync)
        if edit:
            self.f_a.valueChanged.connect(self._sync)
        self.f_tread.valueChanged.connect(self._typed_tread)
        self.b_auto.toggled.connect(self._sync)
        self._quiet = False
        self._sync()

    def _pick_view(self, *_a) -> None:
        side = self.view_pick.currentData() == "side"
        self.view.setVisible(side)
        self.plan.setVisible(not side)

    def _typed_tread(self, *_a) -> None:
        if not self._quiet and self.b_auto.isChecked():
            self.b_auto.setChecked(False)   # typed: it stays

    def _record(self) -> dict:
        r = dict(self.rec)
        self.ends.write(r)
        # it belongs to the lower of its two levels (the storey it takes)
        r["level"] = R.owner(r, self.doc, self.elevations)
        r["w"] = round(self.f_w.value(), 3)
        r["riser"] = round(self.f_riser.value(), 3)
        r["tread"] = round(self.f_tread.value(), 3)
        r["fix_tread"] = not self.b_auto.isChecked()
        r["t"] = round(self.f_t.value(), 3)
        r["shape"] = self.f_shape.currentData() or "straight"
        r["turn"] = self.f_turn.currentData()
        r["landing"] = round(self.f_land.value(), 3)
        r["anchor"] = self.f_anchor.currentData()
        r["split"] = int(self.f_split.value())
        r["gap"] = round(self.f_gap.value(), 3)
        r["nosing"] = round(self.f_nos.value(), 3)
        r["build"] = self.f_build.currentData()
        self.rails.write(r)
        r["cut"] = bool(self.f_cut.currentData())
        if self.edit:
            r["x"] = round(self.f_x.value(), 4)
            r["y"] = round(self.f_y.value(), 4)
            r["angle"] = round(self.f_a.value(), 3)
            r["name"] = self.f_name.text().strip() or self.rec.get("name")
        return r

    def _drop(self, r):
        r = dict(r)
        r.setdefault("x", 0.0)
        r.setdefault("y", 0.0)
        zs, ze = R.heights(r, self.doc, self.elevations)
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
        self.f_split.setEnabled(turning)
        self.f_gap.setEnabled(r["shape"] == "U")
        zs, ze, known = self._drop(r)
        s = steps(r, zs, ze)
        if not r["fix_tread"]:            # show Blondel's tread
            # kept as it was, not False: setValue runs _sync again inside
            # (a nested _sync ended the quiet early → the tread taken as
            # typed, «Blondel» switched off just by opening the window)
            was, self._quiet = self._quiet, True
            try:
                self.f_tread.setValue(s["p"])
            finally:
                self._quiet = was
        self.view.set(r, zs, ze, known)
        self.plan.set(r, zs, ze, known)
        self._show(r, s, zs, ze, known)

    def _show(self, r, s, zs, ze, known) -> None:
        """The header's summary, the folds' choices, the drawings, the
        numbers and Blondel's check — live."""
        def name(box):
            return box.currentText().split("  (")[0].strip()
        lo, hi = name(self.ends.f_bottom), name(self.ends.f_top)
        n, h, p = s["n"], abs(s["h"]) * 100, s["p"] * 100
        shape = {"straight": "Straight", "L": "L", "U": "U"}.get(
            r["shape"], "Straight")
        if r["shape"] in ("L", "U"):
            shape += f", turning {r['turn']}"
        drop = abs(ze - zs)
        self.head.set_summary([
            f"{lo} → {hi}",
            "{" + f"{drop:.2f} m" + "}" + ("" if known else " ≈"),
            "{" + f"{n} risers" + "}" + f" of {h:.1f} cm",
            "tread {" + f"{p:.0f} cm" + "}", shape,
            self.rails.summary()])
        self.fold_lv.set_pick(f"{lo} → {hi}")
        self.fold_steps.set_pick(f"{r['w']:.2f} wide · {h:.1f} / {p:.0f}")
        self.fold_shape.set_pick(shape)
        self.fold_build.set_pick("Open treads" if r["build"] == "open"
                                 else "Concrete")
        self.fold_cut.set_pick("Auto" if r["cut"] else "None")
        self.fold_anchor.set_pick(self.f_anchor.currentText())
        self.d_lv.set(h=f"{drop:.2f}", lo=lo, hi=hi)
        if self.edit:
            self.fold_place.set_pick(f"{r['x']:.2f}, {r['y']:.2f} · "
                                     f"{r['angle'] % 360:.0f}°")
            self.d_dial.set(a=r["angle"])
        treads = max(s["n1"] - 1, 0) + max(s["n2"] - 1, 0)
        if r["shape"] in ("L", "U"):
            ld = max(r["landing"], r["w"]) if r["shape"] == "L" \
                else r["landing"]
            last = (f"{ld:.2f} m", "landing")
        else:
            last = (f"{r['w']:.2f} m", "wide")
        self.stats.set([(f"{n}", f"risers of {h:.1f} cm"),
                        (f"{treads}", f"treads of {p:.0f} cm"),
                        (f"{s['L']:.2f} m", "run" + ("" if known else " ≈")),
                        last])
        v = 2 * abs(s["h"]) + s["p"]
        ok = 0.625 <= v <= 0.655
        self.badge.set(ok, f"Blondel: 2 R + T = {v * 100:.1f} cm "
                           + ("(NBR 9050: 63–65)" if ok else
                              "— outside 63–65 cm (NBR 9050)"))

    def _ok(self) -> None:
        r = self._record()
        why = self.ends.why_not() or why_not(dict(r, x=r.get("x", 0.0),
                                                   y=r.get("y", 0.0)))
        if why is None and r["start"] != "terrain":
            zs, ze = R.heights(dict(r, x=0.0, y=0.0), self.doc,
                               self.elevations)
            if abs(zs - ze) < 0.05:
                why = "The top and the bottom are at the same height"
        if why:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Stair", why + ".")
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


# ---- its tool: the ramp's, with treads drawn -------------------------------------------
class StairTool(R.RampTool):
    name = "ArchXQ stair"
    axq_element = "stair"
    noun = "Stair"

    def __init__(self, rec, heights_at, on_done, on_cancelled, z) -> None:
        """``heights_at(p)`` → (zs, ze) for a stair starting at p."""
        self.heights_at = heights_at

        def length_at(p):             # its record NOW (the library edits it)
            zs, ze = self.heights_at(p)
            return steps(self.rec, zs, ze)["L"], zs, ze
        super().__init__(rec, length_at, on_done, on_cancelled, z)

    def layout(self, r: dict) -> list:
        zs, ze = self.heights_at((r["x"], r["y"]))
        return layout(r, zs, ze)

    def marks(self, viewport, painter, pc: dict) -> None:
        """The treads' lines across a flight."""
        if not pc.get("run", True) or pc.get("m", 0) < 2:
            return
        (cx, cy), (dx, dy) = pc["c"], pc["d"]
        rx, ry = dy, -dx
        h = pc["w"] / 2
        painter.setPen(QPen(QColor(ACCENT), 1.0))
        for k in range(1, pc["m"] - 1):
            s = k * pc["p"]
            a = compat.to_pixel(viewport, cx + dx * s + rx * h,
                                cy + dy * s + ry * h, self.z)
            b = compat.to_pixel(viewport, cx + dx * s - rx * h,
                                cy + dy * s - ry * h, self.z)
            if a and b:
                painter.drawLine(QPointF(*a), QPointF(*b))

    def value_label(self):
        if self.a is None or self.hover is None:
            return None
        zs, ze = self.heights_at(self.a)
        s = steps(self.rec, zs, ze)
        ang = self._angle(self.hover)
        return (f"{s['n']} risers · run {s['L']:.2f} m  {zs:+.2f} → {ze:+.2f}"
                + (f"   {ang % 360:.0f}°" if ang is not None else ""), None)

    def status_clause(self) -> str:
        return super().status_clause().replace("Ramp:", "Stair:").replace(
            "its first edge", "its first step's edge")
