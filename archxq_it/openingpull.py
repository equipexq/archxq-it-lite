# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A SLAB'S CORNERS OVER A DOOR OR A WINDOW: the wall's, not the window's
(his file, 23/11/2026: the corner window «Window 15» took almost all of two
walls; drawing the room's slab, its corner caught the window's trim — 1.5 cm
out of the wall's face — or jumped from line to line: frame, tracks, glass).

The slab tool keeps the host's real snaps (``axis_keep_hard``: a face's
corner stays where it is). Over an opening's span those snaps belong to the
door / window (its trim, frame, sill, glass), so there they no longer lead:
the point is the cursor's, and the wall's own points pull as if the opening
were not there — the corners of its faces where walls meet (``corner``,
from ``walls.plan``) and, as everywhere, its centre line
(``walltools.AxisPull``).

Pure (no Qt): ``zones`` / ``inside`` / ``corners`` / ``on_corner``; the
tool keeps them for its whole run (``Pull``)."""
from __future__ import annotations

import math

from . import walls as W

#: m — how far past an opening's sides and out of its wall's faces its own
#: pieces reach (a trim 5 cm wide stands 1.5 cm out; a sill 5–6 cm out)
REACH = 0.12
#: px — a face's corner pulls within this (the host's own reach is 4)
CORNER_PX = 6.0
#: m — a host point on one of these corners is the wall's own: it stays
SAME = 1e-3
#: the host's snaps that are never the window's (the outline's closing,
#: the origin…): they always stay
KEEP_KINDS = frozenset({"close", "origin", "component_origin"})
#: the host's snaps that do not hold the point (it is the cursor's)
SOFT_KINDS = frozenset({"none", "ground", "axis", ""})


def zones(walls: list, openings: list) -> list:
    """Where the openings' own pieces lie: [(centre Seg, half thickness,
    s0, s1)] — s along the wall's centre line, REACH past each side. A
    corner window gives one on each of its two walls (``cornerwin.split``,
    up to the corner's outside). Straight walls only."""
    if not walls or not openings:
        return []
    try:
        from . import cornerwin as CW
        ops = CW.split(walls, openings, outside=True)
    except Exception:  # noqa: BLE001 — a corner window that can't turn
        ops = list(openings)
    by_id = {w.get("id"): w for w in walls}
    out = []
    for o in ops:
        w = by_id.get(o.get("wall"))
        if w is None or w.get("kind", "line") != "line":
            continue
        try:
            seg = W.centre(w)
            h = float(w["t"]) / 2.0
            pos, width = float(o["pos"]), float(o["w"])
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
        if seg.L < 1e-6 or h <= 0.0 or width <= 0.0:
            continue
        out.append((seg, h, pos - width / 2.0 - REACH,
                    pos + width / 2.0 + REACH))
    return out


def inside(zs: list, p) -> bool:
    """Whether the plan point ``p`` is among an opening's own pieces."""
    for seg, h, s0, s1 in zs:
        f, d = seg.project(p)
        s = f * seg.L
        if s0 <= s <= s1 and abs(d) <= h + REACH:
            return True
    return False


def corners(walls: list) -> list:
    """The corners of the walls' faces, joined (``walls.plan``): where a
    slab's outline meets them — out and in. Each once."""
    out: list = []
    try:
        plans = W.plan(walls)
    except Exception:  # noqa: BLE001
        return out
    for pcs in plans.values():
        for pc in pcs:
            for loop in [pc.get("outer") or []] + list(pc.get("holes") or []):
                for q in loop:
                    q = (round(float(q[0]), 4), round(float(q[1]), 4))
                    if not any(math.dist(q, k) <= SAME for k in out):
                        out.append(q)
    return out


def on_corner(cs: list, p) -> bool:
    """A point on one of the faces' corners (the wall's own)."""
    return any(math.dist(p, k) <= SAME for k in cs)


def nearest(cs: list, here, to_pixel, reach: float = CORNER_PX):
    """The face's corner within ``reach`` px of the cursor (``here``, px;
    ``to_pixel(x, y)`` → px or None) — or None."""
    best = None
    for k in cs:
        px = to_pixel(k[0], k[1])
        if px:
            d = math.dist(here, px)
            if d <= reach and (best is None or d < best[0]):
                best = (d, k)
    return None if best is None else [best[1][0], best[1][1]]


class _Free:
    """The host's snap let go: what the plot tools read of it."""
    kind = "none"
    axis = None
    guide = None
    guides = None
    edge = None

    def __init__(self, point):
        self.point = point


class Unsnapped:
    """The host's tool context, its point the CURSOR's on the working plane
    (not the window's snap). Everything else is the host's."""

    def __init__(self, ctx, world):
        self._ctx = ctx
        self.world = world
        self.snap = _Free(world)

    def __getattr__(self, name):
        return getattr(self._ctx, name)


def cursor_on_plane(viewport, ctx, z: float):
    """The cursor's point on the plane at height ``z`` (the camera ray
    through its pixel) — or None."""
    from . import compat
    scr = getattr(ctx, "screen", None)
    if scr is None or viewport is None:
        return None
    ray = compat.pixel_ray(viewport, scr.x(), scr.y())
    if ray is None:
        return None
    (ox, oy, oz), (dx, dy, dz) = ray
    if abs(dz) < 1e-9:
        return None
    t = (z - oz) / dz
    return compat.vec(ox + dx * t, oy + dy * t, z)
