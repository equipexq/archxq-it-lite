"""A HIP ROOF in its LAYERS, with RAFTERS (PLANO_ESTRUTURA_LEVE_FASE4 4d,
his «faz tudo», 2026-11-03) — a rectangular hip, as the gable's
``_layered_sweep`` does it for a gable.

Each of the four slopes is a region in plan (two trapezoids along the long
sides, two triangles at the ends — the hips and the ridge between them).
A piece lying in one region is DRAPED under its plane: its top and its foot
are the plan polygon lifted onto that slope (each a plane), its sides
upright. So a layer is four draped pieces, meeting on the hips and the
ridge, where their upright faces would lie on each other: left out (the
two halves close on one line — the planes meet there at one height).

The core with a frame:

- a HIP RAFTER on each hip, a RIDGE BOARD on the ridge — bands as wide as
  a rafter, each cut in two by its line, one half in each slope;
- the COMMON RAFTERS square to each long eave between the hips' feet,
  from the eave to the ridge board, and the JACK RAFTERS — the same,
  stopping at a hip (on the long sides and on the ends);
- the insulation between them; 1 mm between all of them (nothing
  coplanar).

Where two layers meet, ONE face stays (the lower one's top); a framed
core sits 1 mm off the layers over / under it. Eyes: «studs» (the
rafters), «fill». No trusses on a hip (the box says «built with
rafters»), no soffit boards (a hip's eaves turn the corners)."""
from __future__ import annotations

import math


def regions(A: float, B: float, o: float) -> dict:
    """The four slopes' plan polygons (x along the ridge, y across), at the
    eaves (A + o, B + o): {"S", "E", "N", "W"} counter-clockwise."""
    Ao, Bo = A + o, B + o
    r1, r2 = (-(A - B), 0.0), ((A - B), 0.0)
    sw, se, ne, nw = (-Ao, -Bo), (Ao, -Bo), (Ao, Bo), (-Ao, Bo)
    out = {"S": [sw, se, r2, r1], "E": [se, ne, r2], "N": [ne, nw, r1, r2],
           "W": [nw, sw, r1]}
    # (a square: the ridge a point — no doubled corner)
    return {k: [p for i, p in enumerate(v)
                if math.dist(p, v[i - 1]) > 1e-9] for k, v in out.items()}


def under_z(side: str, x: float, y: float, A: float, B: float, o: float,
            ze: float, tan: float) -> float:
    """The underside's z over (x, y) on the slope ``side``."""
    Ao, Bo = A + o, B + o
    d = {"S": y + Bo, "N": Bo - y, "E": Ao - x, "W": x + Ao}[side]
    return ze + d * tan


def _lines(A: float, B: float, o: float) -> list:
    """The hips and the ridge in plan: [((x, y), (x, y))]."""
    Ao, Bo = A + o, B + o
    r1, r2 = (-(A - B), 0.0), ((A - B), 0.0)
    out = [((-Ao, -Bo), r1), ((Ao, -Bo), r2), ((Ao, Bo), r2), ((-Ao, Bo), r1)]
    if math.dist(r1, r2) > 1e-9:
        out.append((r1, r2))
    return out


def _on_line(p, q, lines) -> bool:
    """The plan edge p–q lies on a hip / the ridge."""
    for a, b in lines:
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        if L < 1e-9:
            continue
        if all(abs((c[0] - a[0]) * dy - (c[1] - a[1]) * dx) / L < 1e-6
               for c in (p, q)):
            return True
    return False


def _draped(poly, side, lo, hi, A, B, o, ze, tan, P, color, lines,
            top=True, foot=True, inner=True) -> list:
    """A plan polygon (counter-clockwise) draped under the slope ``side``
    from ``lo`` to ``hi`` over its underside (vertical offsets): its top,
    its foot, its upright sides — ``inner`` False: the sides on a hip /
    the ridge left out."""
    def z(p, off):
        return under_z(side, p[0], p[1], A, B, o, ze, tan) + off
    out = []
    if top:
        out.append({"loop": [P(p[0], p[1], z(p, hi)) for p in poly],
                    "holes": [], "color": color})
    if foot:
        out.append({"loop": [P(p[0], p[1], z(p, lo)) for p in reversed(poly)],
                    "holes": [], "color": color})
    for p, q in zip(poly, poly[1:] + poly[:1]):
        if not inner and _on_line(p, q, lines):
            continue
        out.append({"loop": [P(p[0], p[1], z(p, lo)), P(q[0], q[1], z(q, lo)),
                             P(q[0], q[1], z(q, hi)), P(p[0], p[1], z(p, hi))],
                    "holes": [], "color": color})
    return out


def _polys(g) -> list:
    from shapely.geometry.polygon import orient
    out = []
    for q in getattr(g, "geoms", [g]):
        if q.geom_type == "Polygon" and not q.is_empty and q.area > 1e-7:
            q = orient(q, 1.0)
            out.append([tuple(c) for c in list(q.exterior.coords)[:-1]])
    return out


def frame_plan(A: float, B: float, o: float, fr: dict) -> dict:
    """The core's frame in plan, per slope: {side: {"hip": geom (the hip /
    ridge halves), "rafters": geom, "fill": geom}} and "count": {"rafters"
    (n), "rafter_m" (plan m), "hip_m", "ridge_m"} — plan lengths."""
    from shapely.geometry import LineString, Polygon, box
    from shapely.ops import unary_union
    w, s = fr["w"], fr["s"]
    Ao, Bo = A + o, B + o
    regs = {k: Polygon(v) for k, v in regions(A, B, o).items()}
    bands = unary_union([LineString([a, b]).buffer(w / 2, cap_style=2,
                                                    join_style=2)
                         for a, b in _lines(A, B, o)])
    gap = bands.buffer(0.001, join_style=2)
    out, n, rm = {}, 0, 0.0
    for k, reg in regs.items():
        if reg.area < 1e-6:
            continue
        hip = bands.intersection(reg).buffer(0)
        # strips square to this side's eave, at the spacing along it
        strips = []
        if k in ("S", "N"):
            c = -Ao + s / 2
            while c < Ao:
                strips.append(box(c - w / 2, -Bo - 1, c + w / 2, Bo + 1))
                c += s
        else:
            c = -Bo + s / 2
            while c < Bo:
                strips.append(box(-Ao - 1, c - w / 2, Ao + 1, c + w / 2))
                c += s
        raft = unary_union(strips).intersection(reg).difference(gap)
        keep = [q for q in getattr(raft, "geoms", [raft])
                if q.geom_type == "Polygon" and q.area > w * 0.05]
        raft = unary_union(keep).buffer(0) if keep else Polygon()
        fill = reg.difference(gap).difference(
            raft.buffer(0.001, join_style=2)).buffer(0)
        out[k] = {"hip": hip, "rafters": raft, "fill": fill}
        n += len(keep)
        rm += (raft.area / w) if not raft.is_empty else 0.0
    hips = _lines(A, B, o)
    out["count"] = {"rafters": n, "rafter_m": rm,
                    "hip_m": sum(math.dist(a, b) for a, b in hips[:4]),
                    "ridge_m": math.dist(*hips[4]) if len(hips) > 4 else 0.0}
    return out


def faces(r: dict, base: float, A: float, B: float, P, ls: list, k: float,
          hid: set, fr: dict | None, layer_color, rafter_color, fill_color,
          studs_key: str, fill_key: str) -> list:
    """The hip roof's faces, layered (and framed). ``ls``: its layers top
    → bottom (``roof_layers``), ``k``: their thickness scale, ``hid``: the
    hidden ones; ``r["_count"]`` (a dict): its quantities written into
    it."""
    o = float(r.get("overhang", 0.0))
    ang = math.radians(float(r.get("slope", 30.0)))
    tan, sec = math.tan(ang), 1.0 / math.cos(ang)
    ze = base - o * tan
    keys = set(r.get("_hide") or ())
    cnt = r.get("_count") if isinstance(r.get("_count"), dict) else None
    regs = regions(A, B, o)
    lines = _lines(A, B, o)
    n = len(ls)
    core = next(i for i, L in enumerate(ls) if L["role"] == "core")
    t = sum(float(L["t"]) for L in ls) * k
    out, h = [], t * sec                      # (vertical, from the underside)
    plan_area = sum(abs(_area(v)) for v in regs.values())
    for i, L in enumerate(ls):
        lo = 0.0 if i == n - 1 else h - float(L["t"]) * k * sec
        if cnt is not None:
            cnt.setdefault("layers", []).append((L, plan_area * sec))
        if i == core and fr is not None:
            above = i > 0 and i - 1 not in hid
            below = i < n - 1 and i + 1 not in hid
            z0, z1 = lo + (0.001 if below else 0.0), h - (0.001 if above
                                                           else 0.0)
            fp = frame_plan(A, B, o, fr)
            for side, part in fp.items():
                if side == "count":
                    continue
                if studs_key not in keys:
                    for poly in _polys(part["hip"]):
                        out += _draped(poly, side, z0, z1, A, B, o, ze, tan,
                                       P, rafter_color, lines, inner=False)
                    for poly in _polys(part["rafters"]):
                        out += _draped(poly, side, z0, z1, A, B, o, ze, tan,
                                       P, rafter_color, lines)
                if fr["fill"] == "insulation" and fill_key not in keys:
                    for poly in _polys(part["fill"]):
                        out += _draped(poly, side, z0, z1, A, B, o, ze, tan,
                                       P, fill_color, lines)
            if cnt is not None:
                c = fp["count"]
                depth = (h - lo) / sec
                fill = sum(p["fill"].area for s_, p in fp.items()
                           if s_ != "count") * (h - lo) \
                    if fr["fill"] == "insulation" else 0.0
                cnt.update(rafters=c["rafters"], rafter_m=c["rafter_m"] * sec,
                           ridge_m=c["ridge_m"],
                           hip_m=c["hip_m"] * math.sqrt(1 + (tan / math.sqrt(
                               2)) ** 2),
                           fill=fill, kind=fr["kind"], depth=depth)
        elif i not in hid:
            nxt = i + 1
            # (its underside: the next one's top — not over a framed core)
            foot = not (nxt < n and nxt not in hid
                        and not (nxt == core and fr is not None))
            for side, poly in regs.items():
                if len(poly) >= 3:
                    out += _draped(poly, side, lo, h, A, B, o, ze, tan, P,
                                   layer_color(i), lines, foot=foot,
                                   inner=False)
        h = lo
    return out


def _area(poly) -> float:
    return sum(p[0] * q[1] - q[0] * p[1]
               for p, q in zip(poly, poly[1:] + poly[:1])) / 2
