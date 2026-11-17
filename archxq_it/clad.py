# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""TIMBER BOARDS' RELIEF on a plain wall (PLANO_PAREDE_CAIXILHO.md, Part 1 —
his ask, 11/11/2026: «at least one wall of timber boards»).

A sheet's elevation is drawn from the GEOMETRY, so a texture alone shows no
board: the relief is made. A wall with ``clad``:

- ``"battens"`` — vertical boards with battens over their joints: battens
  BATTEN_W wide, CLAD_D proud, every BATTEN_S on the OUTER face;
- ``"lap"`` — horizontal lap siding: a course every LAP_H, each board's
  foot proud of the one above it (a GROOVE of shadow under each).

The relief takes the outer CLAD_D of the wall's own thickness (the core is
that much thinner): every piece is CUT from the wall's joined plan piece,
so the mitred corners close and nothing sticks out of the wall's plan.
Each relief piece stands on the core's face (back to back, inside the
wall) and stops 1 mm short of the wall's foot / top: no two faces seen
from one side lie in one plane. A door or a window cuts it (1 mm wider
than the opening: never in the jamb's plane).

A wall without ``clad`` is built as ever. Only straight walls take it (not
a curtain / grid wall, not bare studs). With LAYERS the relief is cut in
the OUTER layer and wears its finish (that layer: OUTER_MIN at least).
Pure geometry — ``structure.wall_parts`` calls ``parts``.
"""
from __future__ import annotations

import math

KINDS = ("battens", "lap")
CLAD_D = 0.02            # m, how far the battens / boards stand proud
BATTEN_W = 0.05          # m, a batten's width
BATTEN_S = 0.20          # m, battens' spacing (a board's width)
LAP_H = 0.20             # m, a course of siding
GROOVE = 0.015           # m, the shadow under each board
INTO = 0.001             # m, into the core / short of the foot and top
OUTER_MIN = CLAD_D + 0.01    # m, the outer layer's least thickness for it
REACH = 0.05             # m, a cut-out shape's zone round it (_by_bands)


def kind_of(w: dict) -> str:
    """The relief this wall is built with ("" none)."""
    k = w.get("clad")
    if k not in KINDS or w.get("cw") or w.get("gw") \
            or w.get("kind", "line") != "line":
        return ""
    ls = w.get("layers") or ()
    if len(ls) > 1:
        # a wall with LAYERS: the relief is cut in its OUTER one (it wears
        # that layer's finish) — which must be thick enough to hold it
        try:
            if float(ls[0]["t"]) < OUTER_MIN - 1e-9:
                return ""
        except (KeyError, TypeError, ValueError):
            return ""
    elif w.get("frame"):
        return ""                        # (bare studs: nothing to cut it in)
    try:
        if float(w["t"]) < CLAD_D + 0.02:
            return ""
    except (KeyError, TypeError, ValueError):
        return ""
    return k


def _pieces(g) -> list:
    from shapely.geometry.polygon import orient
    out = []
    for p in getattr(g, "geoms", [g]):
        if p.is_empty or p.geom_type != "Polygon" or p.area < 1e-8:
            continue
        p = orient(p, 1.0)
        out.append({"outer": list(p.exterior.coords)[:-1],
                    "holes": [list(r.coords)[:-1] for r in p.interiors]})
    return out


def holes_of(ops, z0: float) -> list:
    """A wall's openings as (s0, s1, z_lo, z_hi) — 1 mm wider and taller,
    so nothing cut by them lies in an opening's jamb / head plane."""
    holes = []
    for o in ops or ():
        try:
            s0 = float(o["pos"]) - float(o["w"]) / 2 - INTO
            s1 = float(o["pos"]) + float(o["w"]) / 2 + INTO
            zl = z0 + float(o.get("sill", 0.0)) - INTO
            zh = z0 + float(o.get("sill", 0.0)) + float(o["h"]) + INTO
        except (KeyError, TypeError, ValueError):
            continue
        if s1 - s0 > 0.02 and zh - zl > 0.02:
            holes.append((s0, s1, zl, zh))
    return holes


def frame_of(seg):
    """fn(s0, s1, c0, c1) → the plan rectangle s0..s1 along the wall's
    centre line, c0..c1 across it (shapely, world)."""
    from shapely.geometry import box
    from shapely import affinity
    p0, u = seg.p0, seg.u
    ang = math.degrees(math.atan2(u[1], u[0]))

    def frame(s0, s1, ca, cb):
        g = box(s0, ca, s1, cb)
        g = affinity.rotate(g, ang, origin=(0, 0))
        return affinity.translate(g, p0[0], p0[1])
    return frame


def cut_solid(g, za: float, zb: float, holes, frame, out: list,
              color=None, shapes=()) -> None:
    """Plan shape ``g`` raised from za to zb into ``out`` — less every
    opening it meets: beside one it stands whole; over its stretch, only
    under its sill and over its head. ``color``: its faces' (None: the
    wall's material). ``shapes``: [(shapely polygon, z_lo, z_hi)] cut out
    the same way, by their own plan (a column's base round a grid wall)."""
    from . import walls as W
    if g is None or g.is_empty or zb - za < 1e-4:
        return
    todo = [(g, za, zb)]
    for s0, s1, zl, zh in holes:
        band = frame(s0, s1, -1e4, 1e4)
        nxt = []
        for gg, a, e in todo:
            if zh <= a or zl >= e:
                nxt.append((gg, a, e))
                continue
            inside = gg.intersection(band)
            if inside.is_empty:
                nxt.append((gg, a, e))
                continue
            rest = gg.difference(band)
            if not rest.is_empty:
                nxt.append((rest, a, e))
            if zl > a:
                nxt.append((inside, a, min(zl, e)))
            if zh < e:
                nxt.append((inside, max(zh, a), e))
        todo = nxt
    banded = False
    if shapes:
        nxt = [q for gg, a, e in todo for q in _by_bands(gg, a, e, shapes)]
        banded = len(nxt) > len(todo)
        todo = nxt
    made = []
    for gg, a, e in todo:
        for pc in _pieces(gg):
            raw = W.solid(pc, a, e)
            if color is None:
                made.extend(raw)
            else:
                made.extend(dict(f, color=color) if isinstance(f, dict) else
                            {"loop": f, "holes": [], "color": color}
                            for f in raw)
    # cut in bands round a shape: its pieces welded into one skin (their
    # splits on a pane's face showed as lines)
    out.extend(weld(made) if banded else made)


def _by_bands(g, a: float, e: float, shapes) -> list:
    """[(plan, z_lo, z_hi)] of ``g`` from a to e less the ``shapes``
    [(polygon, z_lo, z_hi)] standing in it — band by band in height (each
    band: less the union of those there), bands of one plan joined: one
    solid where nothing changes (no faces inside it — cut one shape after
    another, a glass showed its splits)."""
    from shapely.ops import unary_union
    near = [(p, zl, zh) for p, zl, zh in shapes
            if zl < e and zh > a and p.intersects(g)]
    if not near:
        return [(g, a, e)]
    # only the part of g within the shapes' widest reach (+ REACH) is
    # banded: the rest stands whole (a pane split right across showed as
    # lines on it). REACH: where it divides, never a cut — the divide
    # clear of a piece's own end (a sliver 0.5 mm thick, else)
    reach = unary_union([p for p, _zl, _zh in near]).buffer(
        REACH, join_style=2)
    far, g = g.difference(reach), g.intersection(reach)
    zs = sorted({a, e} | {z for _p, zl, zh in near for z in (zl, zh)
                          if a < z < e})
    out = []
    for z1, z2 in zip(zs, zs[1:]):
        if z2 - z1 < 1e-6:
            continue
        on = [p for p, zl, zh in near if zl < z2 - 1e-9 and zh > z1 + 1e-9]
        gg = g.difference(unary_union(on)) if on else g
        if out and out[-1][2] == z1 and out[-1][0].equals(gg):
            out[-1] = (out[-1][0], out[-1][1], z2)
        else:
            out.append((gg, z1, z2))
    return [(gg, z1, z2) for gg, z1, z2 in [(far, a, e)] + out
            if not gg.is_empty]


def weld(faces: list) -> list:
    """Solids' faces made one skin: in each plane, the faces facing one way
    joined, and where two meet back to back (inside, never seen) both go.
    Faces of one colour (a cut_solid's); a face with holes stays as it is
    when its plane is not shared."""
    from shapely.geometry import Polygon
    from shapely.geometry.polygon import orient
    from shapely.ops import unary_union

    def loop_of(f):
        return f["loop"] if isinstance(f, dict) else f

    def xyz(q):
        return (float(q[0]), float(q[1]), float(q[2]))

    groups, keep = {}, []
    for f in faces:
        p = [xyz(q) for q in loop_of(f)]
        if len(p) < 3:
            continue
        n = [0.0, 0.0, 0.0]
        for a, b in zip(p, p[1:] + p[:1]):
            n[0] += (a[1] - b[1]) * (a[2] + b[2])
            n[1] += (a[2] - b[2]) * (a[0] + b[0])
            n[2] += (a[0] - b[0]) * (a[1] + b[1])
        ln = math.sqrt(sum(c * c for c in n))
        if ln < 1e-12:
            continue
        n = [c / ln for c in n]
        # one key for both ways: the first clear component made positive
        k = next(i for i in range(3) if abs(n[i]) > 1e-6)
        way = 1 if n[k] > 0 else -1
        m = [c * way for c in n]
        d = sum(m[i] * p[0][i] for i in range(3))
        key = (tuple(round(c, 5) for c in m), round(d, 5))
        groups.setdefault(key, []).append((way, f, p, m))
    out = []
    for key, fs in groups.items():
        if len(fs) == 1:
            out.append(fs[0][1])
            continue
        m = fs[0][3]
        # the plane's basis: u, v with u × v = m
        ref = (1.0, 0.0, 0.0) if abs(m[0]) < 0.9 else (0.0, 1.0, 0.0)
        u = (ref[1] * m[2] - ref[2] * m[1], ref[2] * m[0] - ref[0] * m[2],
             ref[0] * m[1] - ref[1] * m[0])
        lu = math.sqrt(sum(c * c for c in u))
        u = tuple(c / lu for c in u)
        v = (m[1] * u[2] - m[2] * u[1], m[2] * u[0] - m[0] * u[2],
             m[0] * u[1] - m[1] * u[0])
        d = key[1]

        def to2(q):
            return (sum(q[i] * u[i] for i in range(3)),
                    sum(q[i] * v[i] for i in range(3)))

        def to3(x, y):
            return tuple(round(d * m[i] + x * u[i] + y * v[i], 9)
                         for i in range(3))
        sides = {1: [], -1: []}
        for way, f, p, _m in fs:
            holes = [[to2(xyz(q)) for q in h]
                     for h in (f.get("holes") or []) if len(h) >= 3] \
                if isinstance(f, dict) else []
            try:
                sides[way].append(Polygon([to2(q) for q in p],
                                          holes).buffer(0))
            except Exception:  # noqa: BLE001 — leave it as it is
                out.append(f)
        col = next((f.get("color") for _w, f, _p, _m in fs
                    if isinstance(f, dict) and f.get("color") is not None),
                   None)
        pos = unary_union(sides[1]) if sides[1] else None
        neg = unary_union(sides[-1]) if sides[-1] else None
        for way, g, other in ((1, pos, neg), (-1, neg, pos)):
            if g is None:
                continue
            if other is not None:
                g = g.difference(other)
            for pg in getattr(g, "geoms", [g]):
                if pg.geom_type != "Polygon" or pg.area < 1e-8:
                    continue
                # (no simplify: a point dropped here, still in the face
                # beside it, would leave a T-junction — a crack)
                pg = orient(pg, 1.0 if way > 0 else -1.0)
                f = {"loop": [to3(x, y) for x, y in
                              list(pg.exterior.coords)[:-1]],
                     "holes": [[to3(x, y) for x, y in list(r.coords)[:-1]]
                               for r in pg.interiors]}
                if col is not None:
                    f["color"] = col
                out.append(f)
    return out


def parts(w: dict, pieces, seg, ops, z0: float, b: float, top: float):
    """(core pieces, relief faces): the wall's plan pieces less the outer
    CLAD_D (built by the caller as the wall itself, with its openings), and
    the relief's faces (no colour: they wear the wall's material)."""
    from shapely.geometry import Polygon

    kind = kind_of(w)
    if not kind or seg.kind != "line":
        return pieces, []
    p0, u = seg.p0, seg.u
    t = float(w["t"])
    # across the wall (its centre line's frame): the inside is +side, the
    # OUTER face at -side·t/2 (as a curtain wall's)
    side = -1.0 if float(w.get("side", 1)) < 0 else 1.0
    c_out = -side * t / 2

    def across(d0, d1):
        a, e = c_out + side * d0, c_out + side * d1
        return min(a, e), max(a, e)

    frame = frame_of(seg)
    holes = holes_of(ops, z0)
    out = []

    def solid(g, za, zb):
        cut_solid(g, za, zb, holes, frame, out)

    # the relief and the core meet back to back at CLAD_D (inside the wall,
    # never seen): a relief running into the core left a 1 mm strip of its
    # end in the core's end plane at a free end — a flicker
    core_band = frame(-1e4, 1e4, *across(CLAD_D, t + 1.0))
    skin = frame(-1e4, 1e4, *across(-1.0, CLAD_D))
    core = []
    for pc in pieces:
        try:
            poly = Polygon(pc["outer"], pc.get("holes") or []).buffer(0)
        except Exception:  # noqa: BLE001
            core.append(pc)
            continue
        if poly.is_empty:
            continue
        core += _pieces(poly.intersection(core_band))
        relief = poly.intersection(skin)
        if relief.is_empty:
            continue
        za, zb = b + INTO, top - INTO
        if kind == "lap":
            n = max(1, int(math.ceil((zb - za) / LAP_H - 1e-9)))
            for i in range(n):
                lo = za + i * LAP_H
                hi = min(lo + LAP_H - GROOVE, zb)
                if hi - lo > 0.005:
                    solid(relief, lo, hi)
            continue
        # battens: along its centre line's stretch, evenly
        line = poly.intersection(frame(-1e4, 1e4, -1e-4, 1e-4))
        if line.is_empty:
            continue
        xs = [(q[0] - p0[0]) * u[0] + (q[1] - p0[1]) * u[1]
              for q in _coords(line)]
        c0, c1 = min(xs), max(xs)
        if c1 - c0 < BATTEN_W:
            continue
        k = max(1, round((c1 - c0) / BATTEN_S))
        step = (c1 - c0) / k
        for i in range(k):
            m = c0 + step * (i + 0.5)
            solid(relief.intersection(frame(m - BATTEN_W / 2,
                                            m + BATTEN_W / 2, -1e4, 1e4)),
                  za, zb)
    return core, out


def _coords(g) -> list:
    out = []
    for p in getattr(g, "geoms", [g]):
        if hasattr(p, "exterior"):
            out += list(p.exterior.coords)
        elif hasattr(p, "coords"):
            out += list(p.coords)
    return out
