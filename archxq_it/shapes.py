# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""OPENINGS WITH A SHAPE (PLANO_ABERTURAS_FORMA.md, his OK 2026-10-30 — a
YouTube ask, MUZWalls 29/10: «round, oval, arched, gable… openings»).

A window or an Opening (a void) may carry ``"shape"``; none = the
rectangle of always. Its ``w`` × ``h`` (at ``pos``, from ``sill``) stay
the shape's BOX — dimensions, types, grips and quantities read them as
before. The shapes:

- ``round_arch``  a rectangle under a half circle (rise = w / 2)
- ``seg_arch``    under a segment of a circle, ``rise`` high
- ``pointed``     under a pointed (gothic) arch, ``rise`` high
- ``pentagon``    under a gable, ``rise`` high
- ``trapezoid``   its top ``top_w`` wide, centred
- ``triangle``    its apex at the middle of its top
- ``circle``      the round in its box (its diameter: the smaller side)
- ``oval``        the ellipse in its box

Every shape is CONVEX: its outline is one loop, counter-clockwise in the
wall's own plane (s along the wall, z up) — the hole cut in the wall,
the reveal round it, the frame (the outline taken in), the trim (taken
out) all come from it. The shapes with a rectangle at the bottom (the
arches, the pentagon) keep their LEAVES there, a fixed light over them
(as the arched door); the others are fixed glass.

Pure: no IngeTrazo, no Qt.
"""
from __future__ import annotations

import math

SHAPES = ("rect", "round_arch", "seg_arch", "pointed", "pentagon",
          "trapezoid", "triangle", "circle", "oval")
#: the shapes with a rise of their own (m), and theirs when none is set
RISE = {"seg_arch": 1 / 6, "pointed": 0.6, "pentagon": 1 / 3}   # × w
#: the shapes whose leaves stand in the rectangle under the curve
WITH_LEAVES = ("round_arch", "seg_arch", "pointed", "pentagon")
STEPS = 24              # a half circle in this many steps
MIN_RECT = 0.30         # m — under this the leaves don't fit: fixed glass
MIN_FOOT = 0.01         # m — a round / an oval at least this over the floor


def shape_of(o: dict) -> str:
    """Its shape — the rectangle for a door, a shopfront, anything else."""
    s = o.get("shape")
    if s not in SHAPES or o.get("kind") not in ("window", "void") \
            or o.get("op") == "shop":
        return "rect"
    return s


def clean(o: dict) -> dict:
    """The shape keys of a record, clean — {} for the rectangle."""
    s = o.get("shape")
    if s not in SHAPES or s == "rect" or o.get("kind") not in ("window",
                                                              "void"):
        return {}
    out = {"shape": s}
    w, h = float(o["w"]), float(o["h"])
    if s in RISE:
        try:
            r = float(o.get("rise", RISE[s] * w))
        except (TypeError, ValueError):
            r = RISE[s] * w
        out["rise"] = round(min(max(r, 0.05), h), 4)
    if s == "trapezoid":
        try:
            tw = float(o.get("top_w", w / 2))
        except (TypeError, ValueError):
            tw = w / 2
        out["top_w"] = round(min(max(tw, 0.05), w), 4)
    return out


def rise(o: dict) -> float:
    s = shape_of(o)
    w, h = float(o["w"]), float(o["h"])
    if s == "round_arch":
        return min(w / 2, h)
    if s in RISE:
        return min(max(float(o.get("rise", RISE[s] * w)), 0.05), h)
    return 0.0


def spring(o: dict, z0: float) -> float | None:
    """Where its rectangle ends and its top shape starts (z) — None for
    a shape with no rectangle under it."""
    if shape_of(o) not in WITH_LEAVES:
        return None
    return z0 + float(o.get("sill", 0.0)) + float(o["h"]) - rise(o)


def outline(o: dict, z0: float, steps: int = STEPS) -> list | None:
    """The shape's outline [(s, z)…], counter-clockwise in the wall's
    plane, from its bottom left — None for the rectangle."""
    s = shape_of(o)
    if s == "rect":
        return None
    w, h = float(o["w"]), float(o["h"])
    sc = float(o["pos"])
    s0, s1 = sc - w / 2, sc + w / 2
    zs = z0 + float(o.get("sill", 0.0))
    zt = zs + h
    hw = w / 2
    if s == "triangle":
        return [(s0, zs), (s1, zs), (sc, zt)]
    if s == "trapezoid":
        tw = min(max(float(o.get("top_w", hw)), 0.05), w) / 2
        return [(s0, zs), (s1, zs), (sc + tw, zt), (sc - tw, zt)]
    if s in ("circle", "oval"):
        rx, rz = (hw, h / 2) if s == "oval" else (min(w, h) / 2,) * 2
        # (never ON the floor: touching it at one point, the wall's foot
        # would pinch — 1 cm over it at least)
        zc = max(zs, z0 + MIN_FOOT) + h / 2
        k = 2 * steps
        return [(sc + rx * math.cos(-math.pi / 2 + 2 * math.pi * i / k),
                 zc + rz * math.sin(-math.pi / 2 + 2 * math.pi * i / k))
                for i in range(k)]
    r = rise(o)
    zp = zt - r                         # the spring
    base = [(s0, zs), (s1, zs)] if zp > zs + 1e-9 else []
    if s == "pentagon":
        return base + [(s1, zp), (sc, zt), (s0, zp)] if base else \
            [(s0, zp), (s1, zp), (sc, zt)]
    if s == "round_arch" and r >= hw - 1e-9:
        top = [(sc + hw * math.cos(math.pi * i / steps),
                zp + hw * math.sin(math.pi * i / steps))
               for i in range(steps + 1)]
    elif s in ("round_arch", "seg_arch"):
        # a circle's segment through both springs and the crown
        R = (hw * hw + r * r) / (2 * r)
        zc = zt - R
        a0 = math.atan2(zp - zc, hw)
        top = [(sc + R * math.cos(a0 + (math.pi - 2 * a0) * i / steps),
                zc + R * math.sin(a0 + (math.pi - 2 * a0) * i / steps))
               for i in range(steps + 1)]
    else:
        # POINTED: two arcs meeting at the apex — the right one centred on
        # the spring line R left of its spring, the left one its mirror
        R = (hw * hw + r * r) / (2 * hw)
        cx = s1 - R
        a1 = math.atan2(r, R - hw)
        n = max(steps // 2, 4)
        right = [(cx + R * math.cos(a1 * i / n), zp + R * math.sin(a1 * i / n))
                 for i in range(n + 1)]
        right[-1] = (sc, zt)
        left = [(2 * sc - q[0], q[1]) for q in reversed(right)]
        top = right + left[1:]
    out = base + top if base else top
    # a closed loop: no point repeated at the end
    if math.dist(out[0], out[-1]) < 1e-9:
        out = out[:-1]
    return _dedupe(out)


def _dedupe(loop: list) -> list:
    out = []
    for p in loop:
        if not out or math.dist(out[-1], p) > 1e-7:
            out.append(p)
    if len(out) > 1 and math.dist(out[0], out[-1]) < 1e-7:
        out.pop()
    return out


def area(loop: list) -> float:
    """Signed area (> 0 counter-clockwise)."""
    return 0.5 * sum(p[0] * q[1] - q[0] * p[1]
                     for p, q in zip(loop, loop[1:] + loop[:1]))


def inset(loop: list, d: float) -> list:
    """A CONVEX counter-clockwise loop taken in by ``d`` (out: d < 0) —
    each side moved parallel, the corners where they meet: as many points
    as it has (a ring between the two is quads, side by side)."""
    k = len(loop)
    lines = []
    for i in range(k):
        a, b = loop[i], loop[(i + 1) % k]
        L = math.dist(a, b) or 1.0
        nx, nz = -(b[1] - a[1]) / L, (b[0] - a[0]) / L     # the inside
        lines.append(((a[0] + nx * d, a[1] + nz * d),
                      ((b[0] - a[0]) / L, (b[1] - a[1]) / L)))
    out = []
    for i in range(k):
        (p, u), (q, v) = lines[i - 1], lines[i]
        den = u[0] * v[1] - u[1] * v[0]
        if abs(den) < 1e-9:             # in line: the point moved across
            out.append(q)
            continue
        t = ((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / den
        out.append((p[0] + u[0] * t, p[1] + u[1] * t))
    return out


def clip_above(loop: list, z: float) -> list:
    """The part of a convex loop over the height ``z`` (its light over
    the leaves)."""
    out = []
    k = len(loop)
    for i in range(k):
        a, b = loop[i], loop[(i + 1) % k]
        if a[1] >= z:
            out.append(a)
        if (a[1] >= z) != (b[1] >= z):
            t = (z - a[1]) / (b[1] - a[1])
            out.append((a[0] + (b[0] - a[0]) * t, z))
    return _dedupe(out) if len(out) >= 3 else []
