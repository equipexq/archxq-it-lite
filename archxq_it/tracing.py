"""Walls traced over a DXF (0.15.0, PLANO_0150.md B8 — his note,
2026-10-05: tracing over a DWG, which side of an open run is the inside
looked random). A plan draws a wall as TWO parallel lines; the band
between them is a «lane». With a DXF under the level, the wall tool finds
the lanes 5–60 cm wide: pointed inside one, the point goes to its MIDDLE
(at a corner, where two lanes' middles cross) and the wall takes the lane's
width, centred — so it lies exactly between the drawing's lines, whichever
way it is drawn. Pure (no Qt).
"""
from __future__ import annotations

import math

LO, HI = 0.05, 0.60         # m: how wide a wall drawn as two lines may be
PARALLEL = math.radians(1.0)
MIN_OVERLAP = 0.20          # m: the two lines run side by side at least this


def _unit(dx, dy):
    L = math.hypot(dx, dy)
    return (dx / L, dy / L) if L > 1e-12 else (0.0, 0.0)


def lanes(segs, lo: float = LO, hi: float = HI) -> list:
    """[{"a", "b" (its middle line), "w" (its width), "u" (its way)}] —
    every two drawing lines parallel, ``lo``…``hi`` apart, side by side.
    ``segs``: [(x0, y0, x1, y1), …]."""
    items = []
    for s in segs:
        x0, y0, x1, y1 = (float(v) for v in s[:4])
        L = math.hypot(x1 - x0, y1 - y0)
        if L < MIN_OVERLAP:
            continue
        u = _unit(x1 - x0, y1 - y0)
        if u[0] < -1e-12 or (abs(u[0]) <= 1e-12 and u[1] < 0):
            u = (-u[0], -u[1])                    # one way per direction
        ang = math.atan2(u[1], u[0])
        if ang < -math.pi / 2 + PARALLEL:         # (near-vertical: one side)
            u = (-u[0], -u[1])
            ang = math.atan2(u[1], u[0])
        items.append((ang, (x0, y0), (x1, y1), u, L))
    items.sort(key=lambda it: it[0])
    out = []
    n = len(items)
    for i in range(n):
        ai, p0, p1, u, _L = items[i]
        nx, ny = -u[1], u[0]
        for j in range(i + 1, n):
            aj, q0, q1, _v, _M = items[j]
            if aj - ai > PARALLEL:
                break
            # across: q0's distance from p's line
            d = (q0[0] - p0[0]) * nx + (q0[1] - p0[1]) * ny
            if not lo - 1e-9 <= abs(d) <= hi + 1e-9:
                continue
            # along: where the two overlap
            s = sorted(((p0[0] - p0[0]) * u[0] + (p0[1] - p0[1]) * u[1],
                        (p1[0] - p0[0]) * u[0] + (p1[1] - p0[1]) * u[1]))
            t = sorted(((q0[0] - p0[0]) * u[0] + (q0[1] - p0[1]) * u[1],
                        (q1[0] - p0[0]) * u[0] + (q1[1] - p0[1]) * u[1]))
            a, b = max(s[0], t[0]), min(s[1], t[1])
            if b - a < MIN_OVERLAP:
                continue
            mx, my = p0[0] + nx * d / 2, p0[1] + ny * d / 2
            out.append({"a": (mx + u[0] * a, my + u[1] * a),
                        "b": (mx + u[0] * b, my + u[1] * b),
                        "w": round(abs(d), 4), "u": u})
    # the narrowest first: a wall's two faces, not a face and the next wall
    out.sort(key=lambda la: la["w"])
    return out


def _inside(la, p, slack: float) -> float | None:
    """How far p is off the lane's middle — None: not in it."""
    (ax, ay), u = la["a"], la["u"]
    L = math.dist(la["a"], la["b"])
    s = (p[0] - ax) * u[0] + (p[1] - ay) * u[1]
    if not -la["w"] - slack <= s <= L + la["w"] + slack:
        return None
    off = abs((p[0] - ax) * -u[1] + (p[1] - ay) * u[0])
    return off if off <= la["w"] / 2 + slack else None


def snap(ls: list, p, slack: float = 0.02):
    """(the point on the lanes' middle, the lane) — at a corner, where the
    middles of the two lanes there cross; None: p is in no lane."""
    here = []
    for la in ls:
        off = _inside(la, p, slack)
        if off is not None:
            here.append((off, la))
    if not here:
        return None
    here.sort(key=lambda h: h[0])
    best = here[0][1]
    for _off, other in here[1:]:
        cr = best["u"][0] * other["u"][1] - best["u"][1] * other["u"][0]
        if abs(cr) < math.sin(math.radians(10)):
            continue                              # (side by side)
        a, u, b, v = best["a"], best["u"], other["a"], other["u"]
        t = ((b[0] - a[0]) * v[1] - (b[1] - a[1]) * v[0]) / cr
        x = (a[0] + u[0] * t, a[1] + u[1] * t)
        if math.dist(x, p) <= max(best["w"], other["w"]) + slack:
            return [round(x[0], 4), round(x[1], 4)], best
    (ax, ay), u = best["a"], best["u"]
    s = (p[0] - ax) * u[0] + (p[1] - ay) * u[1]
    return [round(ax + u[0] * s, 4), round(ay + u[1] * s, 4)], best
