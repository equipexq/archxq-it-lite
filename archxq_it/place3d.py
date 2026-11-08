# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""PLACING IN THE 3D VIEW (PLANO_ABERTURAS_3D.md, his OK 29/10: «pode
construir tudo, mas sempre que possível alinhado às linhas que encontrar»).

Doors, windows and grids: the wall is found by the camera's RAY (in 3D the
cursor's x, y says nothing of the height — two storeys share it); a wall of
another level refuses («the level rules»). The opening is pulled into line
with the openings above / below it and beside it (their edges and centres).

Columns and beams: on their working plane — a column on the level's floor,
a beam at its underside (the columns' tops) — the ray meets it; a ray
nearly along the plane (a low camera) refuses rather than throw the point
tens of metres off.

The plan (and any view from straight above): untouched — x, y as ever.
"""
from __future__ import annotations

import math

from . import compat
from . import walls as W

#: a ray flatter than this over a working plane: no point on it (it would
#: land far away — prever o erro do usuário)
GRAZE_DEG = 8.0
#: how near on screen an edge / a centre is pulled into line
ALIGN_PX = 10.0
#: walls lying on one line (one storey's over the other's): their centre
#: lines this far apart at most
SAME_LINE = 0.30
NOWHERE = None


def in_3d(viewport) -> bool:
    """Not looking straight down: the 3D view (the plan is a top view)."""
    if viewport is None:
        return False
    try:
        return not compat.is_top(compat.camera_state(viewport))
    except Exception:  # noqa: BLE001
        return False


def ray_of(viewport, ctx):
    scr = getattr(ctx, "screen", None)
    if scr is None or viewport is None:
        return None
    return compat.pixel_ray(viewport, scr.x(), scr.y())


def plane_point(ray, z: float, graze_deg: float = GRAZE_DEG):
    """[x, y] where the ray meets the level plane ``z`` — None when it runs
    nearly along it (flatter than ``graze_deg``) or away from it."""
    (ox, oy, oz), (dx, dy, dz) = ray
    n = math.sqrt(dx * dx + dy * dy + dz * dz)
    if n < 1e-12 or abs(dz) / n < math.sin(math.radians(graze_deg)):
        return None
    t = (z - oz) / dz
    if t <= 0:
        return None
    return [ox + dx * t, oy + dy * t]


# ---- the walls, every level: which one the ray meets -----------------------------------
def wall_entry(w: dict, z0: float, top: float, level: str, name: str) -> dict:
    """One wall as the ray sees it: its foot (``z0`` + its raised base) to
    its ``top``, its level."""
    return {"wall": w, "z0": z0,
            "zlo": z0 + float(w.get("base", 0.0) or 0.0), "zhi": top,
            "level": level, "name": name}


def walls_hit(entries: list, ray):
    """The nearest wall face the ray meets, between the wall's foot and its
    top: (distance, entry, (x, y, z), s along its centre line, side ±1) —
    or None."""
    (ox, oy, oz), (dx, dy, dz) = ray
    best = None
    for e in entries:
        w = e["wall"]
        if w.get("kind", "line") != "line" or W.why_not(w) is not None:
            continue
        try:
            seg = W.centre(w)
            t = float(w["t"])
        except (KeyError, TypeError, ValueError):
            continue
        u, p0 = seg.u, seg.p0
        n = (-u[1], u[0])
        for side in (1, -1):
            N = (n[0] * side, n[1] * side)
            den = dx * N[0] + dy * N[1]
            if den >= -1e-9:
                continue                      # seen from behind / edge on
            q = (p0[0] + N[0] * t / 2, p0[1] + N[1] * t / 2)
            k = ((q[0] - ox) * N[0] + (q[1] - oy) * N[1]) / den
            if k <= 0 or (best is not None and k >= best[0]):
                continue
            hx, hy, hz = ox + dx * k, oy + dy * k, oz + dz * k
            s = (hx - q[0]) * u[0] + (hy - q[1]) * u[1]
            if 0.0 <= s <= seg.L and e["zlo"] - 1e-3 <= hz <= e["zhi"] + 1e-3:
                best = (k, e, (hx, hy, hz), s, side)
    return best


def face_point(w: dict, s: float, side: int) -> list:
    """The point ``s`` along wall ``w`` on its face ``side`` (a hair inside,
    so the plan's nearest-wall search reads that face)."""
    seg = W.centre(w)
    u, p0 = seg.u, seg.p0
    c = side * (float(w["t"]) / 2 - 1e-4)
    return [p0[0] + u[0] * s - u[1] * c, p0[1] + u[1] * s + u[0] * c]


# ---- aligned with the lines found ------------------------------------------------------
def lines_on_wall(wall: dict, entries: list, openings: list) -> list:
    """The openings on walls lying on the same line as ``wall`` — the storey
    above's and below's (not its own: an edge laid on a neighbour's would
    run into it): [(s along ``wall``, (x, y), z bottom, z top), …] for each
    one's two edges and its centre."""
    seg = W.centre(wall)
    u, p0 = seg.u, seg.p0
    by_id = {e["wall"]["id"]: e for e in entries}
    out = []
    for o in openings:
        e = by_id.get(o.get("wall"))
        if e is None or o.get("wall") == wall.get("id"):
            continue
        w2 = e["wall"]
        if w2.get("kind", "line") != "line" or W.why_not(w2) is not None:
            continue
        s2 = W.centre(w2)
        if abs(u[0] * s2.u[1] - u[1] * s2.u[0]) > 1e-3:
            continue                                   # not parallel
        if abs((s2.p0[0] - p0[0]) * -u[1] + (s2.p0[1] - p0[1]) * u[0]) \
                > SAME_LINE:
            continue                                   # another line
        zb = e["z0"] + W.opening_lift(w2) + float(o.get("sill", 0.0) or 0.0)
        zt = zb + float(o["h"])
        c = (s2.p0[0] + s2.u[0] * float(o["pos"]),
             s2.p0[1] + s2.u[1] * float(o["pos"]))
        sc = (c[0] - p0[0]) * u[0] + (c[1] - p0[1]) * u[1]
        half = float(o["w"]) / 2
        for s in (sc - half, sc, sc + half):
            xy = (p0[0] + u[0] * s, p0[1] + u[1] * s)
            out.append((s, xy, zb, zt))
    return out


def snap_along(s: float, half: float, cands: list, tol: float):
    """(s', the line it took or None): the opening centred at ``s`` (half
    its width ``half``) moved so its centre or one of its edges lies on the
    nearest of ``cands`` within ``tol`` — its centre to a centre, an edge to
    an edge, or an edge to a centre."""
    best = None
    for c in cands:
        for off in (0.0, -half, half):
            d = c - (s + off)
            # a tie: centre on centre wins (the same width above: all
            # three meet at once)
            key = abs(d) - (1e-9 if off == 0.0 else 0.0)
            if abs(d) <= tol and (best is None or key < best[2]):
                best = (d, c, key)
    if best is None:
        return s, None
    return s + best[0], best[1]


def metres_per_px(viewport, x: float, y: float, z: float, u) -> float:
    """How many metres along ``u`` one pixel is, there (∞: unknown)."""
    a = compat.to_pixel(viewport, x, y, z)
    b = compat.to_pixel(viewport, x + u[0], y + u[1], z)
    if not a or not b:
        return math.inf
    return 1.0 / max(math.dist(a, b), 1e-6)


# ---- the tools' cursor on their working plane ------------------------------------------
class _OnPlane:
    """The host's cursor context with ``world`` moved onto the plane."""

    def __init__(self, ctx, world) -> None:
        self._ctx = ctx
        self.world = world
        self.snap = None

    def __getattr__(self, k):
        return getattr(self._ctx, k)


def plane_ctx(tool, ctx):
    """The cursor ``ctx`` for a tool drawing on the plane ``tool.z``: in the
    plan, as it is; in 3D, the host's point when it lies on the plane or
    caught something (a corner, an edge — its x, y are in line with it),
    else the ray's point on the plane; None: the ray grazes the plane."""
    vp = getattr(tool, "viewport", None)
    if not in_3d(vp):
        return ctx
    ray = ray_of(vp, ctx)
    if ray is None:
        return ctx
    q = plane_point(ray, tool.z)
    if q is None:
        return None
    w = getattr(ctx, "world", None)
    if w is not None and (abs(w.z() - tool.z) < 1e-3
                          or getattr(ctx, "snap", None)):
        return ctx
    return _OnPlane(ctx, compat.vec(q[0], q[1], tool.z))


GRAZE_SAY = "Look down at the floor to place it — the view is too low"


def other_level_say(name: str) -> str:
    """D4: the wall the ray met is another level's."""
    from .i18n import tr
    return tr("That wall is on «{name}» — switch to that level to place "
              "there", name=name)


class OnPlane:
    """Mixin (first among the bases) for a tool drawing on its plane
    ``z``: in 3D the cursor is read where the ray meets that plane; a ray
    that grazes it shows nothing and a click says why."""
    #: not sent to the plan view (PLANO_ABERTURAS_3D.md D9 / D10)
    stays_in_view = True
    grazing = False

    def _plane_z(self) -> None:
        """A tool whose plane differs in 3D (a beam) moves it here."""

    def _pick(self, ctx):
        self._plane_z()
        c = plane_ctx(self, ctx)
        self.grazing = c is None
        return super()._pick(ctx if c is None else c)

    def on_hover(self, ctx) -> None:
        self._plane_z()
        if plane_ctx(self, ctx) is None:
            self.grazing = True
            self.hover = None
            self._sync()
            return
        self.grazing = False
        super().on_hover(ctx)

    def _grazes(self, ctx) -> bool:
        """The click's ray grazes the plane: said, and nothing done (a
        tool with an ``on_click`` of its own asks this first)."""
        self._plane_z()
        if plane_ctx(self, ctx) is None:
            compat.flash(self.viewport, GRAZE_SAY, 4000)
            return True
        return False

    def on_click(self, ctx) -> None:
        if self._grazes(ctx):
            return
        super().on_click(ctx)


# ---- drawing in 3D ----------------------------------------------------------------------
def draw3d(viewport, painter, lines, ink, width=1.6, dash=False) -> None:
    """Lines [((x, y, z), (x, y, z)), …] over the view."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QPen
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    pen = QPen(QColor(ink), width)
    if dash:
        pen.setStyle(Qt.DashLine)
    painter.setPen(pen)
    for a, b in lines:
        pa = compat.to_pixel(viewport, *a)
        pb = compat.to_pixel(viewport, *b)
        if pa and pb:
            painter.drawLine(QPointF(pa[0], pa[1]), QPointF(pb[0], pb[1]))
    painter.restore()


def opening_frame(w: dict, s0: float, s1: float, zb: float, zt: float) -> list:
    """An opening's outline on both faces of its wall, and its jambs'
    depth: 3D lines."""
    seg = W.centre(w)
    u, p0 = seg.u, seg.p0
    n = (-u[1], u[0])
    t = float(w["t"]) / 2
    out = []
    corners = {}
    for c in (t, -t):
        pts = []
        for s, z in ((s0, zb), (s1, zb), (s1, zt), (s0, zt)):
            pts.append((p0[0] + u[0] * s + n[0] * c,
                        p0[1] + u[1] * s + n[1] * c, z))
        out += [(pts[i], pts[(i + 1) % 4]) for i in range(4)]
        corners[c] = pts
    out += [(a, b) for a, b in zip(corners[t], corners[-t])]
    return out


def box_lines(loop: list, z0: float, z1: float) -> list:
    """A prism's edges: the loop at ``z0`` and ``z1`` and the uprights."""
    lo = [(p[0], p[1], z0) for p in loop]
    hi = [(p[0], p[1], z1) for p in loop]
    n = len(loop)
    return ([(lo[i], lo[(i + 1) % n]) for i in range(n)]
            + [(hi[i], hi[(i + 1) % n]) for i in range(n)]
            + [(lo[i], hi[i]) for i in range(n)])
