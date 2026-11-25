# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A beam's SHAPE (the shape editor, phase 2 — 17/11/2026): curved in plan,
inclined, its section (L, T, inverted T, I, U) and its shape in elevation (a
haunch, a notch at its ends, an arched soffit).

The beam record keeps, besides ``a``, ``b``, ``w``, ``h``:
    ``m``    — a point on its arc, halfway (the strip footing's and the
               curved wall's key: structure.as_wall already makes an arc
               of it, so the beams join round a curve as walls do);
    ``ztb``  — at a height of its own (``zmode: own``), its top at end B
               (``zt`` is end A's): the top runs straight from one to the
               other, along the beam — a rafter, a stair's stringer beam, a
               lean-to's beam on posts of two heights;
    ``sec``  — its section: "L" (its web on its left, a → b), "Lr" (on its
               right), "invT" (an inverted T: a ledge each side, at its
               foot), "I" (a flange at its top and at its foot), "T" (a
               flange at its top — the classic T beam; 23/11/2026), "U" (a
               channel: a flange at its top and at its foot, its web on its
               left; 23/11/2026); ``tf`` the
               flange's thickness, ``tw`` the web's width (``w`` stays the
               whole width — its flange's);
    ``elev`` — its shape seen from the side: "haunch" (deeper towards its
               ends: ``ed`` more, over ``el`` from each end), "notch" (less
               deep at its ends: ``ed`` off its foot over ``el``), "arch"
               (its soffit an arc: ``ed`` up at its middle, flat over
               ``el`` at each end); ``eends`` "both" | "a" | "b" (haunch,
               notch).
A beam without them is today's, byte for byte.

Pure: math, shapely and walls.Seg; no host, no Qt."""
from __future__ import annotations

import math

from . import walls as W

EPS = 1e-9
MIN_BULGE = 1e-4        # m: less than this, straight
MAX_SLOPE = 60.0        # °: steeper is refused (a beam, not a post)
MIN_PART = 0.03         # m: a flange, a web, what is left under a notch
ARCH_STEPS = 24         # an arched soffit: so many flat pieces

SECTIONS = ("rect", "L", "Lr", "invT", "I", "T", "U")
ELEVS = ("none", "haunch", "notch", "arch")
ENDS = ("both", "a", "b")

WHY_CURVE = "A beam's curve goes up to a half circle"
WHY_TIGHT = "Too tight a curve for its width"
WHY_STEEP = "Steeper than 60° — that is a column"
WHY_FLANGE = "Its flanges leave no web — thinner flanges, or a deeper beam"
WHY_WEB = "Its web must be narrower than the beam and 3 cm at least"
WHY_ELEV = "That shape doesn't fit the beam — shorter, or less deep"


# ---- the curve ------------------------------------------------------------------------
def _mid(e: dict) -> tuple:
    a, b = e["a"], e["b"]
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _left(e: dict) -> tuple:
    a, b = e["a"], e["b"]
    L = math.dist(a, b) or 1.0
    return (-(b[1] - a[1]) / L, (b[0] - a[0]) / L)


def bulge(e: dict) -> float:
    """How far its arc's middle stands off the chord a → b (+ to the left
    of a → b); 0 when it is straight."""
    if not e.get("m"):
        return 0.0
    m, n = _mid(e), _left(e)
    return (e["m"][0] - m[0]) * n[0] + (e["m"][1] - m[1]) * n[1]


def with_bulge(e: dict, h: float) -> dict:
    """``e`` curved so its middle stands ``h`` off its chord (0: straight
    again)."""
    r = dict(e)
    if abs(h) < MIN_BULGE:
        r.pop("m", None)
        return r
    m, n = _mid(e), _left(e)
    r["m"] = [round(m[0] + n[0] * h, 4), round(m[1] + n[1] * h, 4)]
    return r


def centre(e: dict) -> W.Seg:
    """Its centre line, as drawn: a line or an arc."""
    w = {"kind": "arc" if e.get("m") else "line", "a": list(e["a"]),
         "b": list(e["b"])}
    if e.get("m"):
        w["m"] = list(e["m"])
    return W.drawn(w)


def length(e: dict) -> float:
    """Its length in plan, along its curve."""
    return centre(e).L


def radius(e: dict) -> float | None:
    """Its curve's radius (None: straight)."""
    h = abs(bulge(e))
    if h < MIN_BULGE:
        return None
    s = math.dist(e["a"], e["b"]) / 2
    return (s * s + h * h) / (2 * h)


def why_curve(e: dict) -> str | None:
    """Why its curve can't be (None = it can): more than a half circle, or
    bent tighter than it is wide."""
    if not e.get("m"):
        return None
    c = math.dist(e["a"], e["b"])
    h = abs(bulge(e))
    if h < MIN_BULGE:
        return None
    if h > c / 2 + 1e-6:
        return WHY_CURVE
    if radius(e) < float(e.get("w", 0.2)) - 1e-9:
        return WHY_TIGHT
    return None


# ---- the slope ------------------------------------------------------------------------
def is_sloped(e: dict) -> bool:
    """At its own height with end B's top not end A's."""
    return e.get("zmode") == "own" and e.get("ztb") is not None and \
        abs(float(e["ztb"]) - float(e.get("zt", 2.5))) > 1e-4


def rise(e: dict) -> float:
    """End B's top over end A's (0 when level)."""
    if not is_sloped(e):
        return 0.0
    return float(e["ztb"]) - float(e.get("zt", 2.5))


def why_slope(e: dict) -> str | None:
    L = length(e)
    if is_sloped(e) and math.degrees(math.atan2(abs(rise(e)),
                                                max(L, EPS))) > MAX_SLOPE:
        return WHY_STEEP
    return None


def length3d(e: dict) -> float:
    """Its true length, along its slope (its plan length when level). A
    curved one inclined: a helix's — its rise over its plan length."""
    return math.hypot(length(e), rise(e))


def slope_deg(e: dict) -> float:
    return math.degrees(math.atan2(rise(e), max(length(e), EPS)))


# ---- its section ----------------------------------------------------------------------
def section(e: dict) -> str:
    s = e.get("sec", "rect")
    return s if s in SECTIONS else "rect"


def flange(e: dict) -> float:
    return float(e.get("tf", default_tf(e)))


def web(e: dict) -> float:
    return float(e.get("tw", default_tw(e)))


def default_tf(e: dict) -> float:
    """A flange: a fifth of its depth, 8 to 20 cm."""
    return round(min(max(float(e["h"]) / 5, 0.08), 0.20), 2)


def default_tw(e: dict) -> float:
    """A web: half its width (a third for an I, a U), 3 cm at least."""
    k = 3 if e.get("sec") in ("I", "U") else 2
    return round(max(float(e["w"]) / k, MIN_PART), 2)


def bands(e: dict) -> list:
    """Its section as bands one over the other: (left, right, (anchor,
    off) low, (anchor, off) high) — across from its centre line (+ to the
    left of a → b), up from its foot ("b") or down from its top ("t"). A
    rectangle: one band."""
    s = section(e)
    w = float(e["w"])
    half = w / 2
    if s == "rect":
        return [(-half, half, ("b", 0.0), ("t", 0.0))]
    tf, tw = flange(e), web(e)
    if s == "invT":
        return [(-half, half, ("b", 0.0), ("b", tf)),
                (-tw / 2, tw / 2, ("b", tf), ("t", 0.0))]
    if s in ("L", "Lr"):
        lo, hi = (half - tw, half) if s == "L" else (-half, -half + tw)
        return [(-half, half, ("b", 0.0), ("b", tf)),
                (lo, hi, ("b", tf), ("t", 0.0))]
    if s == "T":                                  # its flange at its top
        return [(-tw / 2, tw / 2, ("b", 0.0), ("t", tf)),
                (-half, half, ("t", tf), ("t", 0.0))]
    if s == "U":                                  # its web on its left
        return [(-half, half, ("b", 0.0), ("b", tf)),
                (half - tw, half, ("b", tf), ("t", tf)),
                (-half, half, ("t", tf), ("t", 0.0))]
    return [(-half, half, ("b", 0.0), ("b", tf)),            # I
            (-tw / 2, tw / 2, ("b", tf), ("t", tf)),
            (-half, half, ("t", tf), ("t", 0.0))]


def flanges_depth(e: dict) -> float:
    """How much of its depth its flanges take."""
    s = section(e)
    if s == "rect":
        return 0.0
    return flange(e) * (2 if s in ("I", "U") else 1)


def section_area(e: dict, depth: float) -> float:
    """Its section's area at that depth."""
    s = section(e)
    w = float(e["w"])
    if s == "rect":
        return w * depth
    tf, tw = flange(e), web(e)
    if s in ("I", "U"):
        return 2 * w * tf + tw * (depth - 2 * tf)
    return w * tf + tw * (depth - tf)


def why_section(e: dict) -> str | None:
    s = section(e)
    if s == "rect":
        return None
    tf, tw, w = flange(e), web(e), float(e["w"])
    if tf < MIN_PART - 1e-9:
        return WHY_FLANGE
    if tw < MIN_PART - 1e-9 or tw > w - 2 * MIN_PART + 1e-9 \
            and s in ("invT", "I", "T") or tw > w - MIN_PART + 1e-9:
        return WHY_WEB
    if min_depth(e) - flanges_depth(e) < MIN_PART - 1e-9:
        return WHY_FLANGE
    return None


# ---- its shape seen from the side -----------------------------------------------------
def elev(e: dict) -> str:
    s = e.get("elev", "none")
    return s if s in ELEVS else "none"


def is_shaped(e: dict) -> bool:
    """Built by this module (not the plain block)."""
    return is_sloped(e) or section(e) != "rect" or elev(e) != "none"


def default_el(e: dict) -> float:
    """A haunch's / a notch's / an arch's flat end: a sixth of it, 20 cm
    to 1.5 m."""
    return round(min(max(length(e) / 6, 0.2), 1.5), 2)


def default_ed(e: dict) -> float:
    """How deep: a haunch, half its depth more; a notch, half off; an
    arch, a third up."""
    h = float(e["h"])
    k = {"haunch": 0.5, "notch": 0.5, "arch": 1 / 3}.get(elev(e), 0.5)
    return round(h * k, 2)


def depth_points(e: dict, h: float) -> list:
    """Its depth along it, (fraction, depth) — straight between; past its
    ends, its first / last stretch goes on. ``h``: its depth as built."""
    L = max(length(e), EPS)
    k = elev(e)
    if k == "none":
        return [(0.0, h), (1.0, h)]
    el = float(e.get("el", default_el(e)))
    ed = float(e.get("ed", default_ed(e)))
    ends = e.get("eends", "both") if k != "arch" else "both"
    at_a, at_b = ends in ("both", "a"), ends in ("both", "b")
    f = min(el / L, 0.5 if at_a and at_b else 1.0)
    if k == "haunch":
        pts = [(0.0, h + ed), (f, h)] if at_a else [(0.0, h)]
        if at_b:
            pts += [(1.0 - f, h), (1.0, h + ed)]
        else:
            pts.append((1.0, h))
        return _dedup(pts)
    if k == "notch":
        pts = []
        if at_a:
            pts += [(0.0, h - ed), (f, h - ed), (f, h)]
        else:
            pts.append((0.0, h))
        if at_b:
            pts += [(1.0 - f, h), (1.0 - f, h - ed), (1.0, h - ed)]
        else:
            pts.append((1.0, h))
        return _dedup(pts)
    # an arched soffit: flat over «el» at each end, a circle's arc between
    f0, f1 = f, 1.0 - f
    span = (f1 - f0) * L
    pts = [(0.0, h), (f0, h)]
    if span > EPS and ed > EPS:
        s = span / 2
        R = (s * s + ed * ed) / (2 * ed)
        for i in range(1, ARCH_STEPS):
            x = -s + span * i / ARCH_STEPS
            up = math.sqrt(max(0.0, R * R - x * x)) - (R - ed)
            pts.append((f0 + (f1 - f0) * i / ARCH_STEPS, h - up))
    pts += [(f1, h), (1.0, h)]
    return _dedup(pts)


def _dedup(pts: list) -> list:
    out = []
    for p in pts:
        if out and abs(p[0] - out[-1][0]) < 1e-12 and \
                abs(p[1] - out[-1][1]) < 1e-12:
            continue
        out.append(p)
    return out


def min_depth(e: dict) -> float:
    return min(d for _, d in depth_points(e, float(e["h"])))


def why_elev(e: dict) -> str | None:
    k = elev(e)
    if k == "none":
        return None
    L = length(e)
    el = float(e.get("el", default_el(e)))
    ed = float(e.get("ed", default_ed(e)))
    if el < 0 or ed < MIN_PART - 1e-9 or ed > 3.0:
        return WHY_ELEV
    two = e.get("eends", "both") == "both" or k == "arch"
    room = L / 2 if two else L
    if k != "haunch":                   # (some of it left at full depth /
        room -= 0.05 if two else 0.1    # some arch)
    if el > room + 1e-9 or (k == "arch" and el < 0.0):
        return WHY_ELEV
    if min_depth(e) < flanges_depth(e) + MIN_PART - 1e-9:
        return WHY_ELEV
    return None


def why_shape(e: dict) -> str | None:
    """Why its shape can't be (None = it can)."""
    return why_curve(e) or why_slope(e) or why_section(e) or why_elev(e)


def volume(e: dict) -> float:
    """Its concrete: along it, its section at each depth (plumb section ×
    plan length: a sloped one is the same prism, sheared)."""
    h = float(e["h"])
    pts = depth_points(e, h)
    L = length(e)
    seg = centre(e)
    v = 0.0
    for lo, hi, zl, zh in bands(e):
        k = 1.0                 # (on a curve: its band's own length)
        if seg.kind == "arc":
            k = (seg.r - seg.d * (lo + hi) / 2) / seg.r

        def tall(d):
            def z(a):
                return a[1] if a[0] == "b" else d - a[1]
            return z(zh) - z(zl)
        for (f0, d0), (f1, d1) in zip(pts, pts[1:]):
            df = f1 - f0
            if df > 0:
                v += (hi - lo) * (tall(d0) + tall(d1)) / 2 * df * L * k
    return v


# ---- its faces --------------------------------------------------------------------------
def _depth_at(pts: list, f: float, fc: float | None = None) -> float:
    """Straight between the points; past the ends, the end stretch goes on
    (a joint cut beyond the end stays on the same plane). ``fc``: where
    the piece it is on stands — its stretch (at a notch's step, two depths
    at one place: the piece's own)."""
    g = f if fc is None else fc
    runs = [(p, q) for p, q in zip(pts, pts[1:]) if q[0] - p[0] > 1e-12]
    if not runs:
        return pts[-1][1]
    if g <= runs[0][0][0]:
        (a, da), (b, db) = runs[0]
    elif g >= runs[-1][1][0]:
        (a, da), (b, db) = runs[-1]
    else:
        for (a, da), (b, db) in runs:
            if a - 1e-12 <= g <= b + 1e-12:
                break
    if b - a < 1e-12:
        return db
    return da + (db - da) * (f - a) / (b - a)


def _flat(ring: list) -> list:
    """A shapely ring → its points, once each (a cut leaves twins a hair
    apart: they would stall the triangles)."""
    out = []
    for x, y in ring:
        p = (round(x, 9), round(y, 9))
        if out and abs(p[0] - out[-1][0]) < 1e-7 and \
                abs(p[1] - out[-1][1]) < 1e-7:
            continue
        out.append(p)
    while len(out) > 1 and abs(out[0][0] - out[-1][0]) < 1e-7 and \
            abs(out[0][1] - out[-1][1]) < 1e-7:
        out.pop()
    return out


def _polys(g) -> list:
    """A shapely geometry → its polygons with no holes (one with a hole is
    split through it)."""
    from shapely.geometry import LineString, Polygon
    from shapely.ops import split
    out, todo = [], []
    if g.is_empty:
        return out
    if g.geom_type == "Polygon":
        todo = [g]
    elif hasattr(g, "geoms"):
        todo = [x for x in g.geoms if x.geom_type == "Polygon"]
    while todo:
        p = todo.pop()
        if p.area < 1e-9:
            continue
        if not p.interiors:
            out.append(p)
            continue
        c = Polygon(p.interiors[0]).centroid
        x0, y0, x1, y1 = p.bounds
        cut = LineString([(c.x, y0 - 1), (c.x, y1 + 1)])
        todo.extend(x for x in split(p, cut).geoms if x.geom_type == "Polygon")
    return out


def _band_ring(seg: W.Seg, lo: float, hi: float, ext: float) -> list:
    """The strip between lo and hi across its centre line, past both ends."""
    if seg.kind == "line":
        a0, a1 = -ext / max(seg.L, EPS), 1 + ext / max(seg.L, EPS)
        s0, s1 = seg.offset(lo), seg.offset(hi)
        return [s0.at(a0), s0.at(a1), s1.at(a1), s1.at(a0)]
    room = (2 * math.pi * 0.95 / max(abs(seg.sweep), EPS) - 1) / 2
    e = max(0.0, min(ext / max(seg.L, EPS), room))
    n = 48
    fs = [-e + (1 + 2 * e) * i / n for i in range(n + 1)]
    s0, s1 = seg.offset(lo), seg.offset(hi)
    return [s0.at(f) for f in fs] + [s1.at(f) for f in reversed(fs)]


def _cut(seg: W.Seg, f: float, half: float) -> list:
    p, t = seg.at(f), seg.tangent(f)
    n = (-t[1], t[0])
    inner = half
    if seg.kind == "arc":
        inner = min(half, seg.r * 0.999)        # (not past its centre)
    # (n: to the left; an arc's left, counter-clockwise, is its centre)
    lo = inner if seg.kind == "arc" and seg.d > 0 else half
    hi = inner if seg.kind == "arc" and seg.d < 0 else half
    return [(p[0] - n[0] * hi, p[1] - n[1] * hi),
            (p[0] + n[0] * lo, p[1] + n[1] * lo)]


def _curved(loop: list) -> dict:
    """A face of a surface that bends (its edges drawn soft — compat's
    «curve»: under 25° to its neighbour, no line)."""
    return {"loop": loop, "holes": [], "curve": True}


def _faces(loop: list, ztop, zbot, soft_under: bool = False) -> list:
    """A plan loop raised: its top at ztop(p), its underside at zbot(p),
    plumb sides; the top / underside one face when it lies in one plane,
    else triangles — drawn as one bending surface, no line over each
    (a curved beam's arched soffit showed its triangles, 22/11/2026).
    ``soft_under``: its underside is a piece of a curve (an arched
    soffit): drawn soft to its neighbours too. Outward, as walls.solid."""
    loop = list(loop)
    if W._area(loop) < 0:
        loop.reverse()
    tops = [(p[0], p[1], ztop(p)) for p in loop]
    bots = [(p[0], p[1], zbot(p)) for p in loop]
    k = len(loop)
    faces = []
    for i in range(k):
        j = (i + 1) % k
        faces.append([bots[i], bots[j], tops[j], tops[i]])
    for ring, flip in ((tops, False), (bots, True)):
        pl = W._plane_of(ring)
        if pl is not None and all(abs(sum(pl[0][j] * t[j] for j in range(3))
                                      - pl[1]) < 1e-6 for t in ring):
            cap = list(reversed(ring)) if flip else list(ring)
            faces.append(_curved(cap) if flip and soft_under else cap)
            continue
        for a, b, c in _tri(loop):
            faces.append(_curved([ring[c], ring[b], ring[a]] if flip
                                 else [ring[a], ring[b], ring[c]]))
    return faces


def _tri(loop: list) -> list:
    """Triangles of a counter-clockwise plan loop, (i, j, k) — its points
    lying on a side (a cut's) left out first: ear clipping stalls on them;
    the triangles' sides then run over them (no gap: the same line)."""
    k = len(loop)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    keep = [i for i in range(k)
            if abs(cross(loop[i - 1], loop[i], loop[(i + 1) % k])) > 1e-12]
    if len(keep) < 3:
        return []
    got = W._ears([loop[i] for i in keep])
    if len(got) < len(keep) - 2:         # (stalled: a fan — its pieces are
        got = [(0, i, i + 1) for i in range(1, len(keep) - 1)]   # convex)
    return [(keep[a], keep[b], keep[c]) for a, b, c in got]


def sloped_faces(outer: list, seg: W.Seg, za: float, zb: float,
                 depth: float) -> list:
    """The faces of a plan piece of a beam whose top runs from ``za`` (its
    end a) to ``zb`` (end b) along ``seg`` — each corner's top by where it
    stands along the beam (past an end, the line goes on: its joint is cut
    on the same slope) — its underside ``depth`` under its top, plumb
    sides."""
    def top(p):
        return za + (zb - za) * seg.project(p)[0]
    return _faces(outer, top, lambda p: top(p) - depth)


def faces(e: dict, pieces: list, za: float, zb: float, depth: float) -> list:
    """A shaped beam's faces: its plan pieces (joined, cut) cut across where
    its depth bends, then into its section's bands; each one's top and
    underside by where it stands along it. ``za`` / ``zb`` its top at its
    ends as built, ``depth`` its depth as built."""
    from shapely.geometry import LineString, Polygon
    from shapely.ops import split
    seg = centre(e)
    pts = depth_points(e, depth)
    w = float(e["w"])
    half = w / 2 + 0.1
    soft_under = elev(e) == "arch"       # (its pieces read as one curve)
    breaks = {f for f, _ in pts if 1e-9 < f < 1 - 1e-9}
    if seg.kind == "arc" and (abs(zb - za) > 1e-9 or len(pts) > 2):
        # curved AND its top or its underside not level: cut in short
        # steps (an arc's own, 7.5°), each piece near flat — no long
        # slivers across it
        n = max(4, math.ceil(abs(seg.sweep) / math.radians(7.5)))
        breaks |= {i / n for i in range(1, n)}
    breaks = sorted(breaks)
    rings = []
    for b in bands(e):
        lo = b[0] if b[0] > -w / 2 + 1e-9 else -w / 2 - 0.05
        hi = b[1] if b[1] < w / 2 - 1e-9 else w / 2 + 0.05
        if seg.kind == "arc":            # (not past the centre)
            lim = seg.r * 0.999 - 1e-6
            if seg.d > 0:
                hi = min(hi, lim)
            else:
                lo = max(lo, -lim)
        rings.append((b, Polygon(_band_ring(seg, lo, hi, 2 * w + 1.0))))

    def top(p):
        return za + (zb - za) * seg.project(p)[0]

    def z_of(anchor, p, fc):
        side, off = anchor
        if side == "t":
            return top(p) - off
        return top(p) - _depth_at(pts, seg.project(p)[0], fc) + off

    out = []
    for pc in pieces:
        g = Polygon(pc["outer"], pc.get("holes") or [])
        if not g.is_valid:
            g = g.buffer(0)
        parts = [g]
        for f in breaks:
            line = LineString(_cut(seg, f, half))
            nxt = []
            for p in parts:
                try:
                    nxt.extend(x for x in split(p, line).geoms
                               if x.geom_type == "Polygon")
                except Exception:  # noqa: BLE001 — not crossed: whole
                    nxt.append(p)
            parts = nxt
        for b, strip in rings:
            # one band of the piece, cut in slices: their caps as they are;
            # their sides met by a neighbour's (the cuts) are inside — gone
            # (a notch's step: the part one shows past the other kept)
            sides: dict = {}
            for p in parts:
                c = p.representative_point()
                fc = seg.project((c.x, c.y))[0]
                for q in _polys(p.intersection(strip)):
                    loop = _flat(list(q.exterior.coords))
                    if len(loop) < 3:
                        continue
                    caps, sd = _solid(
                        loop, lambda pt, b=b, fc=fc: z_of(b[3], pt, fc),
                        lambda pt, b=b, fc=fc: z_of(b[2], pt, fc),
                        soft_under)
                    out.extend(caps)
                    for key, face in sd:
                        sides.setdefault(key, []).append(face)
            for key, got in sides.items():
                if len(got) != 2:
                    out.extend(got)
                    continue
                out.extend(_step(*got))
    return out


def _key(p, q) -> tuple:
    a = (round(p[0], 6), round(p[1], 6))
    c = (round(q[0], 6), round(q[1], 6))
    return (a, c) if a <= c else (c, a)


def _solid(loop: list, ztop, zbot, soft_under: bool = False) -> tuple:
    """_faces, its sides apart: (caps, [(plan edge key, side)])."""
    faces = _faces(loop, ztop, zbot, soft_under)
    k = len(loop)
    lp = list(loop)
    if W._area(lp) < 0:
        lp.reverse()
    sides = [(_key(lp[i], lp[(i + 1) % k]), faces[i]) for i in range(k)]
    return faces[k:], sides


def _step(f1: list, f2: list) -> list:
    """Two slices' sides on the same cut, face to face: what shows of one
    past the other (a notch's step) — nothing when they match. A side:
    [bot p, bot q, top q, top p]."""
    out = []
    for me, other in ((f1, f2), (f2, f1)):
        bp, bq, tq, tp = me
        # the other one's, at my p and my q
        kp, kq = (round(bp[0], 6), round(bp[1], 6)), \
            (round(bq[0], 6), round(bq[1], 6))
        obp = min(v[2] for v in other if (round(v[0], 6),
                                          round(v[1], 6)) == kp)
        obq = min(v[2] for v in other if (round(v[0], 6),
                                          round(v[1], 6)) == kq)
        otp = max(v[2] for v in other if (round(v[0], 6),
                                          round(v[1], 6)) == kp)
        otq = max(v[2] for v in other if (round(v[0], 6),
                                          round(v[1], 6)) == kq)
        if bp[2] < obp - 1e-6 or bq[2] < obq - 1e-6:   # mine lower: shows
            out.append([bp, bq, (bq[0], bq[1], min(obq, tq[2])),
                        (bp[0], bp[1], min(obp, tp[2]))])
        if tp[2] > otp + 1e-6 or tq[2] > otq + 1e-6:   # mine higher: shows
            out.append([(bp[0], bp[1], max(otp, bp[2])),
                        (bq[0], bq[1], max(otq, bq[2])), tq, tp])
    return out
