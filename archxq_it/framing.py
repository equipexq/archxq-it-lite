# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""LIGHT-FRAME WALLS — wood / steel frame (PLANO_PAREDE_ESTRUTURA_LEVE, his
OK 2026-11-02, the MuzWalls picture): a wall's CORE, instead of solid, is
its studs at a spacing, plates under and over them, at each opening a
double stud each side (king + jack), a header over it and a sill under a
window (short studs over / under them) — and the insulation BETWEEN them,
never inside them (no two faces on each other).

``frame`` on the wall (and on its type, which gives it to its walls):

    {"kind": "wood" | "steel", "w": stud width along the wall,
     "s": spacing centre to centre, "top": plates over (1–2),
     "bottom": plates under (1–2), "fill": "insulation" | "empty"}

None = solid, as always. The studs' depth is the core's thickness (a 2×6:
a 14 cm core). Built on a STRAIGHT wall — a sloped / gable top too (phase
3a, 2026-11-02: the studs cut under it, the top plates along it) — and on
a CURVED one (phase 3c: the studs radial, at the spacing along the wall's
centre; the plates and insulation in pieces of at most ``ARC_STEP``); a
full circle stays solid for now (no ends to start the studs from).

A header's depth follows its opening's width (phase 3a — the builder's
rule of thumb, no structural design): see ``header_h``; a wide one has two
jacks each side."""
from __future__ import annotations

import math

from . import walls as W

KINDS = ("wood", "steel")
STUD_W = (0.02, 0.20)          # the stud's width along the wall
SPACING = (0.20, 1.20)         # centre to centre
PLATES = (1, 2)
#: a new frame of each kind (US 2×4 at 16" — a steel C at 60 cm)
DEFAULTS = {"wood": {"kind": "wood", "w": 0.038, "s": 0.40, "top": 2,
                     "bottom": 1, "fill": "insulation"},
            "steel": {"kind": "steel", "w": 0.05, "s": 0.60, "top": 1,
                      "bottom": 1, "fill": "insulation"}}
#: the header over an opening, its depth by the opening's width: up to
#: 1.20 m, up to 1.80 m, wider (wood: a 2×8, 2×10, 2×12)
HEADERS = {"wood": (0.184, 0.235, 0.286), "steel": (0.15, 0.20, 0.25)}
HEADER_SPANS = (1.20, 1.80)
#: wider than this: two jacks each side
WIDE = 1.80
#: the insulation's colour (nothing chosen for it: it keeps this)
FILL_COLOR = (0.93, 0.80, 0.47, 1.0)
#: what the studs wear when nothing is chosen for the core
STUD_MAT = {"wood": {"lib": "wood/raw_pine.jpg"},
            "steel": {"lib": "metal/metal_brushed.png"}}
#: the bottom plate on concrete or masonry (PLANO_PISOS_BARROTES D8 — the
#: SILL PLATE): pressure-treated pine, its own colour and material
TREATED_COLOR = (0.56, 0.62, 0.44, 1.0)
TREATED_MAT = {"color": [0.56, 0.62, 0.44], "name": "Treated pine"}
#: how deep its anchor bolt goes into the concrete (a section's symbol)
BOLT_DEPTH = 0.15
TINY = 0.005


def clean_frame(raw) -> dict | None:
    """A frame as stored — None: not one (a solid core)."""
    if not isinstance(raw, dict) or raw.get("kind") not in KINDS:
        return None
    d = DEFAULTS[raw["kind"]]

    def num(k, lo, hi):
        try:
            return min(max(float(raw.get(k, d[k])), lo), hi)
        except (TypeError, ValueError):
            return d[k]
    fr = {"kind": raw["kind"], "w": round(num("w", *STUD_W), 4),
          "s": round(num("s", *SPACING), 4),
          "top": int(round(num("top", *PLATES))),
          "bottom": int(round(num("bottom", *PLATES))),
          "fill": "empty" if raw.get("fill") == "empty" else "insulation"}
    # a ROOF's core as TRUSSES (PLANO_TELHADO_ASNAS D1): its system and
    # shape — none: rafters (every file before)
    if raw.get("system") == "trusses":
        fr["system"] = "trusses"
        fr["pattern"] = raw.get("pattern") if raw.get("pattern") in \
            TRUSS_PATTERNS else "auto"
    return fr


#: the trusses' shapes (PLANO_TELHADO_ASNAS D2) — "auto": by the span
TRUSS_PATTERNS = ("auto", "kingpost", "fink", "doublefink", "howe")
#: «auto»: a king post up to 6 m between the walls' outer faces, a Fink up
#: to 10, a double Fink beyond — a rule of thumb, no design
TRUSS_SPANS = (("kingpost", 6.0), ("fink", 10.0), ("doublefink", 1e9))


#: their names (the window, the quantities)
TRUSS_NAMES = {"auto": "Auto", "kingpost": "King post", "fink": "Fink",
               "doublefink": "Double Fink", "howe": "Howe", "mono": "Mono"}


def truss_pattern(fr: dict, span: float) -> str:
    """The shape a truss is drawn with over ``span``."""
    p = fr.get("pattern", "auto")
    if p != "auto":
        return p
    return next(k for k, lim in TRUSS_SPANS if span <= lim + 1e-9)


def frame_of(w: dict | None) -> dict | None:
    """The frame a wall is BUILT with — None: its core is solid (none, a
    curtain wall, a full circle)."""
    fr = clean_frame((w or {}).get("frame"))
    if fr is None or w.get("cw") or \
            w.get("kind", "line") not in ("line", "arc", "circle"):
        return None
    return fr


def frame_loop(w: dict, part: dict, G) -> list | None:
    """The plan loop a core piece is framed in: its outline — a FULL
    CIRCLE's ring (a hole in it) opened where it was drawn from (angle 0,
    phase 4c): the ring run round from there and back, so the studs start
    and end there (a double stud at that seam, as on site). None: not
    one to frame."""
    loop = list(part.get("outer") or ())
    if len(loop) < 3:
        return None
    if not part.get("holes"):
        return loop
    if w.get("kind") != "circle" or len(part["holes"]) != 1:
        return None
    C = G.seg.C
    hole = list(part["holes"][0])

    def ang(p):
        return math.atan2(p[1] - C[1], p[0] - C[0]) % (2 * math.pi)

    def rad(ps):
        return sum(math.hypot(p[0] - C[0], p[1] - C[1]) for p in ps) / len(ps)
    ro, ri = rad(loop), rad(hole)
    if ro - ri < 0.005:
        return None
    out = sorted(loop, key=ang)                  # counter-clockwise from 0
    inn = sorted(hole, key=ang)
    e = -1e-6

    def at(R, a):
        return (C[0] + R * math.cos(a), C[1] + R * math.sin(a))
    return [at(ro, 0.0)] + [p for p in out if ang(p) > 1e-9] + \
        [at(ro, e), at(ri, e)] + [p for p in reversed(inn)
                                  if ang(p) > 1e-9] + [at(ri, 0.0)]


def header_h(kind: str, span: float) -> float:
    """A header's depth over an opening ``span`` wide."""
    k = sum(span > lim + 1e-6 for lim in HEADER_SPANS)
    return HEADERS[kind][k]


def jacks(span: float) -> int:
    """Jack studs each side of an opening ``span`` wide."""
    return 2 if span > WIDE + 1e-6 else 1


def top_line(w: dict, z0: float, A: float, B: float) -> list | None:
    """The wall's own top over A…B as [(s, z)] — straight between them (a
    slope, a gable's ridge, the level corner pieces): None, a flat top."""
    top = W.top_of(w)
    if top is None:
        return None
    sa, sb = W.top_span(w)
    xs = {A, B} | {x for x in (sa, sb) if A < x < B}
    if top["kind"] == "gable":
        L = max(W.drawn(w).L, 1e-9)
        sp = min(max(top["at"] * L, sa + 1e-9), sb - 1e-9)
        if A < sp < B:
            xs.add(sp)
    return [(x, z0 + W.top_h(w, x)) for x in sorted(xs)]


def _line_at(line: list, s: float) -> float:
    for (a, za), (c, zc) in zip(line, line[1:]):
        if s <= c + 1e-12:
            f = (s - a) / (c - a) if c - a > 1e-12 else 0.0
            return za + (zc - za) * min(max(f, 0.0), 1.0)
    return line[-1][1]


# ---- along the wall: straight or curved (phase 3c) -----------------------------------
#: a curved wall's long pieces (plates, insulation) cut into pieces of at
#: most this angle — each a wedge from the centre, clipped exactly
ARC_STEP = math.pi / 6


class Geo:
    """A wall's centre as the frame reads it: ``S(p)`` how far along it
    (a curve: along its arc), ``P(s, o)`` the point there ``o`` to its
    left, ``cut(poly, s0, s1)`` a plan polygon between s0 and s1 (a curve:
    between the radii there)."""

    def __init__(self, w: dict) -> None:
        self.seg = seg = W.centre(w)
        self.arc = seg.kind == "arc"
        self.L = seg.L

    def S(self, p) -> float:
        seg = self.seg
        if not self.arc:
            return (p[0] - seg.p0[0]) * seg.u[0] + \
                (p[1] - seg.p0[1]) * seg.u[1]
        return seg.project(p)[0] * self.L

    def P(self, s: float, o: float):
        seg = self.seg
        if not self.arc:
            u = seg.u
            return (seg.p0[0] + u[0] * s - u[1] * o,
                    seg.p0[1] + u[1] * s + u[0] * o)
        th = seg.th0 + seg.sweep * s / self.L
        R = seg.r - seg.d * o
        return (seg.C[0] + R * math.cos(th), seg.C[1] + R * math.sin(th))

    def cut(self, poly: list, s0: float, s1: float) -> list:
        if not self.arc:
            for lim, above in ((s0, True), (s1, False)):
                poly = W._clip(poly, self.S, lim, above, self.seg)
                if len(poly) < 3:
                    return []
            return poly
        seg, C = self.seg, self.seg.C
        t0 = seg.tangent(s0 / self.L)
        t1 = seg.tangent(s1 / self.L)
        thm = seg.th0 + seg.sweep * (s0 + s1) / 2 / self.L
        m = (math.cos(thm), math.sin(thm))
        half = abs(seg.sweep) * (s1 - s0) / self.L / 2
        rin = min(math.hypot(p[0] - C[0], p[1] - C[1]) for p in poly)
        rho = rin * math.cos(min(half, math.pi / 2)) - 1e-6
        # (first the far side and the centre away: then each radius
        # crosses what is left once)
        for f in (lambda p: (p[0] - C[0]) * m[0] + (p[1] - C[1]) * m[1] - rho,
                  lambda p: (p[0] - C[0]) * t0[0] + (p[1] - C[1]) * t0[1],
                  lambda p: -((p[0] - C[0]) * t1[0]
                              + (p[1] - C[1]) * t1[1])):
            poly = _half(poly, f)
            if len(poly) < 3:
                return []
        return poly

    def ends(self, loop: list, w: dict) -> tuple:
        """(A, A2, B2, B) of a plan piece: A…B its whole length (a mitred
        end's tip included), A2…B2 where it is whole — the end studs reach
        from the tip to there. A curve's outline has corners all along
        its faces: there, where each face starts and stops."""
        ss = sorted(self.S(p) for p in loop)
        A, B = ss[0], ss[-1]
        reach = min(2.0 * float(w["t"]) + 0.01, (B - A) / 2)
        if not self.arc:
            return (A, max(v for v in ss if v <= A + reach),
                    min(v for v in ss if v >= B - reach), B)
        offs = [self.seg.project(p)[1] for p in loop]
        starts, stops = [], []
        for face in (min(offs), max(offs)):
            on = [self.S(p) for p, o in zip(loop, offs)
                  if abs(o - face) < 1e-4]
            if on:
                starts.append(min(on))
                stops.append(max(on))
        A2 = min(max(starts), A + reach) if starts else A
        B2 = max(min(stops), B - reach) if stops else B
        return A, A2, B2, B

    def split(self, traps: list) -> list:
        """A curved wall's long pieces in steps of ``ARC_STEP`` at most."""
        if not self.arc:
            return traps
        step = ARC_STEP * self.seg.r
        out = []
        for t in traps:
            k = max(1, math.ceil((t[1] - t[0]) / step - 1e-9))
            if k == 1:
                out.append(t)
                continue
            for j in range(k):
                a = t[0] + (t[1] - t[0]) * j / k
                c = t[0] + (t[1] - t[0]) * (j + 1) / k
                out.append((a, c, z_at(t, a, False), z_at(t, c, False),
                            z_at(t, a, True), z_at(t, c, True)))
        return out


def _half(poly: list, f) -> list:
    """Sutherland–Hodgman: the polygon where f ≥ 0 (f affine — the cut
    exact along a straight edge)."""
    out = []
    n = len(poly)
    for k in range(n):
        p, q = poly[k], poly[(k + 1) % n]
        fp, fq = f(p), f(q)
        if fp >= -1e-12:
            out.append(p)
        if (fp >= -1e-12) != (fq >= -1e-12):
            g = fp / (fp - fq)
            out.append((p[0] + (q[0] - p[0]) * g, p[1] + (q[1] - p[1]) * g))
    clean = []
    for x in out:
        if not clean or math.dist(x, clean[-1]) > 1e-9:
            clean.append(x)
    if len(clean) > 2 and math.dist(clean[0], clean[-1]) <= 1e-9:
        clean.pop()
    return clean


# ---- pieces under a sloped top: trapezoids (s0, s1, lo0, lo1, hi0, hi1) --------------
def trap(r) -> tuple:
    """A rectangle (s0, s1, z0, z1) as a trapezoid; a trapezoid as it is."""
    return r if len(r) == 6 else (r[0], r[1], r[2], r[2], r[3], r[3])


def z_at(t, s: float, hi: bool) -> float:
    """A trapezoid's top (``hi``) / foot at ``s``."""
    s0, s1 = t[0], t[1]
    f = (s - s0) / (s1 - s0) if s1 - s0 > 1e-12 else 0.0
    return t[4] + (t[5] - t[4]) * f if hi else t[2] + (t[3] - t[2]) * f


def _under(r, line: list) -> list:
    """Rectangle r, cut under the line: trapezoids (r itself, wholly
    under)."""
    s0, s1, z0, z1 = r
    xs = [s0] + [x for x, _z in line if s0 + 1e-9 < x < s1 - 1e-9] + [s1]
    if min(_line_at(line, x) for x in xs) >= z1 - 1e-9:
        return [trap(r)]
    # where the line crosses the rectangle's top / foot: split there too
    cuts = set(xs)
    for a, c in zip(xs, xs[1:]):
        fa, fc = _line_at(line, a), _line_at(line, c)
        for z in (z0, z1):
            if (fa - z) * (fc - z) < 0:
                cuts.add(a + (c - a) * (z - fa) / (fc - fa))
    xs = sorted(cuts)
    out = []
    for a, c in zip(xs, xs[1:]):
        if c - a < 1e-6:
            continue
        ha = min(z1, _line_at(line, a))
        hc = min(z1, _line_at(line, c))
        if ha < z0 + TINY and hc < z0 + TINY:
            continue
        ha, hc = max(ha, z0), max(hc, z0)
        t = (a, c, z0, z0, ha, hc)
        if out and abs(out[-1][1] - a) < 1e-9:   # one with its neighbour
            p = out[-1]
            k0 = (p[5] - p[4]) / (p[1] - p[0])
            k1 = (hc - ha) / (c - a)
            if abs(p[5] - ha) < 1e-9 and abs(k0 - k1) < 1e-9:
                out[-1] = (p[0], c, z0, z0, p[4], hc)
                continue
        out.append(t)
    return out


def is_treated(color) -> bool:
    """A face of the treated sill plate (``TREATED_COLOR``)."""
    return tuple(round(v, 3) for v in (color or ())[:3]) == \
        TREATED_COLOR[:3]


def is_fill(color) -> bool:
    return tuple(round(v, 3) for v in (color or ())[:3]) == FILL_COLOR[:3]


# ---- the elevation: rectangles (s0, s1, z0, z1) -------------------------------------
def _minus(p, o) -> list:
    """Rectangle p without rectangle o."""
    s0, s1, z0, z1 = p
    a0, a1, c0, c1 = o
    if a0 >= s1 - 1e-9 or a1 <= s0 + 1e-9 or c0 >= z1 - 1e-9 \
            or c1 <= z0 + 1e-9:
        return [p]
    out = []
    if a0 > s0:
        out.append((s0, a0, z0, z1))
    if a1 < s1:
        out.append((a1, s1, z0, z1))
    m0, m1 = max(s0, a0), min(s1, a1)
    if c0 > z0:
        out.append((m0, m1, z0, c0))
    if c1 < z1:
        out.append((m0, m1, c1, z1))
    return out


#: a stud longer than this between the plates gets a row of BLOCKING
#: (noggins) across, and one more for each such length (PLANO fase 4b —
#: the fire-blocking / buckling rule of thumb; 2.40–2.70 m walls: none)
BLOCK_EVERY = 2.70


def block_rows(zb: float, zt: float, w: float) -> list:
    """The blocking rows' feet between the plates zb…zt (none: short)."""
    h = zt - zb
    if h <= BLOCK_EVERY + 1e-6:
        return []
    n = math.ceil(h / BLOCK_EVERY - 1e-9) - 1
    return [round(zb + h * k / (n + 1) - w / 2, 6) for k in range(1, n + 1)]


def layout(A: float, A2: float, B2: float, B: float, b: float, top: float,
           fr: dict, spans: list, line: list | None = None,
           fixed=()) -> tuple | None:
    """(wood, fill, holes, headers) of a core piece in elevation —
    rectangles (s0, s1, z0, z1). A…B its whole length (a mitred end's tip
    included), A2…B2 where it is whole (the end studs reach from the tip
    to there); b…top its foot and top; ``spans``: its openings (s0, s1,
    zs, zt); ``headers``: [(length, depth)]. None: too small to frame (it
    stays solid).

    ``line``: the wall's own top [(s, z)] (``top_line``) — the pieces then
    TRAPEZOIDS (s0, s1, lo0, lo1, hi0, hi1): the studs and insulation cut
    under the top plates, which run along it.

    Phase 4a: ``fixed`` = full-height studs of its own (s0, s1) — where a
    wall meets it in a T (the backing studs the other one's board is nailed
    to) and under a beam's end (a post of studs): the common studs there
    give way. A MITRED start (A2 > A: an L corner) gets one stud more by
    its end stud — the corner's third. Phase 4b: rows of blocking across a
    tall wall (``block_rows``)."""
    w, s = fr["w"], fr["s"]
    if line:
        top = max(z for _s, z in line)
    zb = b + fr["bottom"] * w
    zt = top - fr["top"] * w
    if zt - zb < 0.10 or B2 - A2 < 2 * w:
        return None
    holes = [(max(s0, A), min(s1, B), max(zs, b), min(z1, top))
             for s0, s1, zs, z1 in spans
             if s1 > A + TINY and s0 < B - TINY and z1 - zs > 0.01]
    wood = []

    def put(r):
        """r, less what is there already and the openings."""
        parts = [r]
        for o in wood + holes:
            parts = [q for p in parts for q in _minus(p, o)]
        wood.extend((max(q[0], A), min(q[1], B), q[2], q[3]) for q in parts
                    if min(q[1], B) - max(q[0], A) > TINY
                    and q[3] - q[2] > TINY)

    for k in range(fr["bottom"]):                    # the plates
        put((A, B, b + k * w, b + (k + 1) * w))
    if not line:                                     # (a sloped top: after)
        for k in range(fr["top"]):
            put((A, B, zt + k * w, zt + (k + 1) * w))
    tops = []                                # (s0, s1, over, under, reach)
    heads = []
    for s0, s1, zs, z1 in holes:
        door = zs <= b + 1e-3
        hh = header_h(fr["kind"], s1 - s0)
        nj = jacks(s1 - s0)
        if z1 < zt - TINY:                           # the header
            put((s0 - nj * w, s1 + nj * w, z1, min(z1 + hh, zt)))
            heads.append((s1 - s0 + 2 * nj * w, hh))
        if not door and zs > zb + w + TINY:          # the sill
            put((s0, s1, zs - w, zs))
        for j in range(nj):                          # jacks
            put((s0 - (j + 1) * w, s0 - j * w, zb, min(z1, zt)))
            put((s1 + j * w, s1 + (j + 1) * w, zb, min(z1, zt)))
        put((s0 - (nj + 1) * w, s0 - nj * w, zb, zt))    # kings
        put((s1 + nj * w, s1 + (nj + 1) * w, zb, zt))
        tops.append((s0, s1, min(z1 + hh, zt),
                     None if door else zs - w, (nj + 1) * w))
    put((A, A2 + w, zb, zt))                         # the ends
    put((B2 - w, B, zb, zt))
    own = []                     # (studs of its own: the commons give way)
    if A2 > A + TINY and B2 - A2 > 4 * w:            # an L corner's third
        own.append((A2 + w, A2 + 2 * w))
    for f0, f1 in fixed:                             # T backing, posts
        f0, f1 = max(f0, A2 + w), min(f1, B2 - w)
        if f1 - f0 > TINY:
            own.append((f0, f1))
    for f0, f1 in own:
        put((f0, f1, zb, zt))
    c = A2 + w / 2 + s
    while c + w / 2 < B2 - w - TINY:                 # the studs between
        lo, hi = c - w / 2, c + w / 2
        if any(lo < f1 - TINY and hi > f0 + TINY for f0, f1 in own):
            c += s
            continue
        for s0, s1, over, under, reach in tops:
            if hi > s0 - reach and lo < s1 + reach:  # at an opening
                if lo >= s0 and hi <= s1:            # short ones
                    put((lo, hi, over, zt))
                    if under is not None:
                        put((lo, hi, zb, under))
                break
        else:
            put((lo, hi, zb, zt))
        c += s
    for z in block_rows(zb, zt, w):                  # blocking (4b)
        put((A, B, z, z + w))
    fill = []
    if fr["fill"] == "insulation":
        busy = wood + holes
        xs = sorted({A, B} | {min(max(v, A), B) for r in busy
                              for v in (r[0], r[1])})
        cols = []
        for s0, s1 in zip(xs, xs[1:]):
            if s1 - s0 < TINY:
                continue
            m = (s0 + s1) / 2
            free, z = [], b
            for z0, z1 in sorted((r[2], r[3]) for r in busy
                                 if r[0] < m < r[1]):
                if z0 > z + TINY:
                    free.append((round(z, 6), round(z0, 6)))
                z = max(z, z1)
            if top > z + TINY:
                free.append((round(z, 6), round(top, 6)))
            if cols and cols[-1][2] == free and abs(cols[-1][1] - s0) < 1e-9:
                cols[-1] = (cols[-1][0], s1, free)   # one with its neighbour
            else:
                cols.append((s0, s1, free))
        fill = [(s0, s1, z0, z1) for s0, s1, free in cols
                for z0, z1 in free]
    if line:                     # under the top plates, which run along it
        under = [(x, z - fr["top"] * w) for x, z in line]
        wood = [t for r in wood for t in _under(r, under)]
        fill = [t for r in fill for t in _under(r, under)]
        for k in range(fr["top"]):
            for (a, za), (c, zc) in zip(line, line[1:]):
                if c - a > TINY:
                    wood.append((a, c, za - (k + 1) * w, zc - (k + 1) * w,
                                 za - k * w, zc - k * w))
    return wood, fill, holes, heads


# ---- where a framed wall is met (phase 4a) ---------------------------------------------
def marks(walls: list, plans: dict, beams=()) -> dict:
    """{wall id: [(s0, s1)…]} — the studs of its own each FRAMED wall of a
    level gets (``layout``'s ``fixed``, along its ``Geo.S``):

    - a wall meeting it in a T (its end on this one's face, away from
      this one's ends): a backing stud at each of its faces — one in the
      middle when it is too thin for two;
    - a beam's end bearing on it (across it, its end within it): a post of
      studs as wide as the beam (two at least).

    ``plans``: ``walls.plan`` of the level; ``beams``: its beam records."""
    out: dict = {}
    framed = [w for w in walls if frame_of(w) is not None
              and plans.get(w["id"])]
    if not framed:
        return out
    try:
        from shapely.geometry import Point, Polygon
        from shapely.ops import unary_union
    except Exception:  # noqa: BLE001 — no marks: the frame as before
        return out

    def shape(wid):
        try:
            return unary_union([Polygon(pc["outer"]).buffer(0)
                                for pc in plans.get(wid) or ()])
        except Exception:  # noqa: BLE001
            return None
    shapes = {w["id"]: shape(w["id"]) for w in walls}
    for w in framed:
        fr = frame_of(w)
        sw = fr["w"]
        G = Geo(w)
        me = shapes.get(w["id"])
        if me is None or me.is_empty:
            continue
        ss = [G.S(p) for pc in plans[w["id"]] for p in pc["outer"]]
        A, B = min(ss), max(ss)
        edge = float(w["t"]) + 0.05            # (an L's mitre: not a T)
        got = []
        for v in walls:
            if v is w or v.get("cw"):
                continue
            sh = shapes.get(v["id"])
            if sh is None or sh.is_empty:
                continue
            try:
                touch = me.buffer(0.01, join_style=2).intersection(sh)
            except Exception:  # noqa: BLE001
                continue
            if touch.is_empty or touch.area < 1e-6:
                continue
            pts = []
            for g in getattr(touch, "geoms", [touch]):
                pts += list(getattr(g, "exterior", g).coords)
            sv = [G.S(p) for p in pts]
            s0, s1 = min(sv), max(sv)
            if s0 < A + edge or s1 > B - edge or s1 - s0 > 1.0:
                continue                       # an end, a long overlap
            if s1 - s0 >= 2 * sw + 0.02:       # one ON each face: the
                # board of this wall's room nails to it either side
                got += [(s0 - sw / 2, s0 + sw / 2),
                        (s1 - sw / 2, s1 + sw / 2)]
            else:
                m = (s0 + s1) / 2
                got.append((m - sw / 2, m + sw / 2))
        for e in beams:
            try:
                a, c = e["a"], e["b"]
                bw = float(e["w"])
            except (KeyError, TypeError, ValueError):
                continue
            d = (c[0] - a[0], c[1] - a[1])
            L = math.hypot(*d)
            if L < 1e-6:
                continue
            for end in (a, c):
                if not me.buffer(0.02).contains(Point(end[0], end[1])):
                    continue
                if not G.arc:                  # along the wall: not a bearing
                    u = G.seg.u
                    if abs((d[0] * u[0] + d[1] * u[1]) / L) > 0.8:
                        continue
                s = G.S(end)
                k = max(2, math.ceil(bw / sw - 1e-6))
                got.append((s - k * sw / 2, s + k * sw / 2))
        if got:
            out[w["id"]] = sorted(got)
    return out


def with_marks(walls: list, plans: dict, beams=()) -> list:
    """The walls, each framed one with its ``_fix`` (``marks``)."""
    m = marks(walls, plans, beams)
    return [dict(w, _fix=m[w["id"]]) if w["id"] in m else w for w in walls]


# ---- the opening spans, as structure.wall_with_openings reads them ------------------
def spans_of(ops: list, z0: float, b: float, top: float,
             dropped: bool = False) -> list:
    """(s0, s1, zs, zt) of each opening along the wall's centre line — a
    shaped / arched one: the box round it (the frame is cut square, as on
    site)."""
    from . import shapes as SH
    from .structure import door_arch
    out = []
    for o in ops:
        loop = SH.outline(o, z0)
        if loop is not None:
            zs = min(z for _s, z in loop)
            zt = max(z for _s, z in loop)
        else:
            zs = max(b, z0 + float(o.get("sill", 0.0)))
            if dropped and float(o.get("sill", 0.0)) <= 0:
                zs = b
            zt = min(top, z0 + float(o.get("sill", 0.0)) + float(o["h"]))
            arc = door_arch(o, z0, top)
            if arc is not None:
                zt = arc[0] + arc[1]
        if zt - zs > 0.01:
            out.append((o["pos"] - o["w"] / 2, o["pos"] + o["w"] / 2,
                        zs, zt))
    return out


# ---- the faces ------------------------------------------------------------------------
def _covered(lo: float, hi: float, spans) -> bool:
    """[lo, hi] covered by the intervals ``spans``."""
    at = lo
    for a, c in sorted(spans):
        if a > at + 1e-6:
            return False
        at = max(at, c)
        if at >= hi - 1e-6:
            return True
    return at >= hi - 1e-6


def faces(w: dict, part: dict, seg, ops: list, z0: float, b: float,
          top: float, color, dropped: bool = False,
          joints=()) -> list | None:
    """The framed core of one plan ``part`` (a layer piece of ``w``): each
    member its own solid, clipped to the part (a mitred corner: the end
    studs follow it), the insulation between. A face that lies against
    another piece is left out (the two would lie on each other). None: too
    small to frame — the caller builds it solid.

    ``joints``: the offsets where a finish lies on the core — the members'
    edges there are inside the wall, yet the host draws them through the
    board: listed in the face's ``"joint"`` (seams.reveal_edges hides
    them); at the wall's ends, top and foot they stay (the joint's line)."""
    fr = frame_of(w)
    if fr is None:
        return None
    G = Geo(w)
    S = G.S
    loop = frame_loop(w, part, G)
    if loop is None:
        return None
    A, A2, B2, B = G.ends(loop, w)
    line = top_line(w, z0, A, B)
    got = layout(A, A2, B2, B, b, top, fr,
                 spans_of(ops, z0, b, top, dropped), line,
                 fixed=w.get("_fix") or ())
    if got is None:
        return None
    wood, fill = got[0], got[1]
    # its studs / insulation HIDDEN in the 3D (layerview.py — the eye): not
    # built, and covering nothing (the other one's faces against them seen)
    hide = set(w.get("_hide") or ())
    # the bottom plate on concrete or masonry (``_treated``, structure.build
    # — a wood frame): pressure-treated, its own colour (D8)
    sill = [r for r in wood if w.get("_treated") and fr["kind"] == "wood"
            and len(r) == 4 and abs(r[2] - b) < 1e-9
            and abs(r[3] - (b + fr["w"])) < 1e-9]
    rest = [r for r in wood if r not in sill]
    pieces = ([] if "studs" in hide else
              [(t, color) for t in G.split([trap(r) for r in rest])]
              + [(t, TREATED_COLOR)
                 for t in G.split([trap(r) for r in sill])]) + \
        ([] if "fill" in hide else
         [(t, FILL_COLOR) for t in G.split([trap(r) for r in fill])])
    traps = [t for t, _c in pieces]

    def on_top(p):                       # on the wall's top (or its foot)
        if abs(p[2] - b) < 1e-6:
            return True
        z = top if line is None else _line_at(line, S(p))
        return abs(p[2] - z) < 1e-6

    # where a finish lies on the core (``joints``): on its offset — on a
    # curve, on the outline's edges there (a wedge's corners lie on the
    # chords, a little inside the arc)
    jsegs = {jj: [(a, c) for a, c in zip(loop, loop[1:] + loop[:1])
                  if abs(seg.project(a)[1] - jj) < 1e-5
                  and abs(seg.project(c)[1] - jj) < 1e-5] for jj in joints}

    def on_j(p, jj) -> bool:
        if not G.arc:
            return abs(seg.project((p[0], p[1]))[1] - jj) < 1e-5
        return any(_on_seg(p, a, c) for a, c in jsegs[jj])

    out = []
    for k, (t, col) in enumerate(pieces):
        s0, s1 = t[0], t[1]
        poly = G.cut(loop, s0, s1)
        if len(poly) < 3 or abs(W._area(poly)) < 1e-8:
            continue
        if W._area(poly) < 0:
            poly.reverse()
        others = traps[:k] + traps[k + 1:]
        flat = abs(t[2] - t[3]) < 1e-9 and abs(t[4] - t[5]) < 1e-9
        made = W.solid({"outer": poly, "holes": []}, t[2], t[4]) if flat \
            else _trap_solid(poly, S, t)
        for f in made:
            pts = f["loop"] if isinstance(f, dict) else f
            if len(pts) < 3:
                continue
            if all(abs(p[2] - z_at(t, S(p), True)) < 1e-6 for p in pts):
                hidden = _lies(t, others, True)          # its top
            elif all(abs(p[2] - z_at(t, S(p), False)) < 1e-6 for p in pts):
                hidden = _lies(t, others, False)         # its foot
            else:                                # an end across the wall
                sv = [S(p) for p in pts]
                hidden = False
                if all(abs(v - s0) < 1e-6 for v in sv):
                    hidden = _covered(t[2], t[4], [
                        (o[3], o[5]) for o in others
                        if abs(o[1] - s0) < 1e-6])
                elif all(abs(v - s1) < 1e-6 for v in sv):
                    hidden = _covered(t[3], t[5], [
                        (o[2], o[4]) for o in others
                        if abs(o[0] - s1) < 1e-6])
            if hidden:
                continue
            face = dict(f, color=col) if isinstance(f, dict) else \
                {"loop": f, "holes": [], "color": col}
            if any(all(on_j(p, jj) for p in pts) for jj in joints):
                face["on_joint"] = True          # a board lies on it
            inner = []
            for p, q in zip(pts, pts[1:] + pts[:1]):
                if any(on_j(p, jj) and on_j(q, jj) for jj in joints) \
                        and not any(abs(S(p) - e) < 1e-6
                                    and abs(S(q) - e) < 1e-6
                                    for e in (A, B)) \
                        and not (on_top(p) and on_top(q)
                                 and (abs(p[2] - b) < 1e-6)
                                 == (abs(q[2] - b) < 1e-6)):
                    inner.append((tuple(p), tuple(q)))
            if inner:
                face["joint"] = inner
            out.append(face)
    return out


def _on_seg(p, a, c) -> bool:
    """Plan point p on the segment a–c."""
    dx, dy = c[0] - a[0], c[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 < 1e-18:
        return math.dist(p[:2], a) < 1e-6
    f = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2
    if f < -1e-6 or f > 1 + 1e-6:
        return False
    return abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / math.sqrt(L2) \
        < 1e-6


def _trap_solid(poly: list, S, t) -> list:
    """A plan polygon (counter-clockwise) from the trapezoid's foot to its
    top — both straight along the wall, so each a plane; outward, as
    ``W.solid``."""
    def lift(p, hi):
        return (p[0], p[1], z_at(t, S(p), hi))
    faces = [[lift(p, True) for p in poly],
             [lift(p, False) for p in reversed(poly)]]
    for p, q in zip(poly, poly[1:] + poly[:1]):
        f = [lift(p, False), lift(q, False), lift(q, True), lift(p, True)]
        # (where foot and top meet, a corner twice: once)
        f = [x for i, x in enumerate(f)
             if max(abs(x[j] - f[i - 1][j]) for j in range(3)) > 1e-9]
        if len(f) >= 3:
            faces.append(f)
    return faces


def _lies(t, others, hi: bool) -> bool:
    """The trapezoid's top (``hi``) / foot wholly against the others' foot
    / top — the same line along the wall."""
    got = []
    for o in others:
        a, c = max(t[0], o[0]), min(t[1], o[1])
        if c - a > 1e-6 and all(abs(z_at(o, x, not hi) - z_at(t, x, hi))
                                < 1e-6 for x in (a, c)):
            got.append((a, c))
    return _covered(t[0], t[1], got)


# ---- counting (quantities) ------------------------------------------------------------
def count(w: dict, pieces, ops: list, z0: float, b: float,
          top: float) -> dict | None:
    """{"studs": n (each upright piece, short ones too), "plates": m
    (lengths of plates and sills), "fill": m³, "headers": {depth: m}} of
    a framed wall's core — None: not framed."""
    fr = frame_of(w)
    if fr is None:
        return None
    G = Geo(w)
    bands = W.layer_bands(w)
    core = next((i for i, la in enumerate(W.layers_of(w))
                 if la["role"] == "core"), 0)
    lo, hi = bands[core]
    depth = hi - lo
    n, plates, fill, blocking = 0, 0.0, 0.0, 0.0
    heads = {}
    spans = spans_of(ops, z0, b, top)
    for pc in pieces:
        loop = frame_loop(w, pc, G)
        if loop is None:
            continue
        A, A2, B2, B = G.ends(loop, w)
        got = layout(A, A2, B2, B, b, top, fr, spans,
                     top_line(w, z0, A, B), fixed=w.get("_fix") or ())
        if got is None:
            continue
        wood, fl, _h, hd = got
        # (its blocking rows on their own — 4b: across, between the studs)
        rows = block_rows(b + fr["bottom"] * fr["w"],
                          (max(z for _s, z in top_line(w, z0, A, B))
                           if top_line(w, z0, A, B) else top)
                          - fr["top"] * fr["w"], fr["w"])
        for r in list(wood):
            if len(r) == 4 and any(abs(r[2] - z) < 1e-6 and
                                   abs(r[3] - z - fr["w"]) < 1e-6
                                   for z in rows):
                blocking += r[1] - r[0]
                wood.remove(r)
        for t in map(trap, wood):
            if max(t[4], t[5]) - min(t[2], t[3]) > t[1] - t[0]:
                n += 1                           # upright: a stud
            else:                                # (along a slope: its length)
                plates += math.hypot(t[1] - t[0], t[4] - t[5])
        for length, h in hd:                     # (the headers on their own)
            plates -= length
            heads[h] = heads.get(h, 0.0) + length
        fill += sum((t[1] - t[0]) * ((t[4] - t[2]) + (t[5] - t[3])) / 2
                    for t in map(trap, fl)) * depth
    return {"studs": n, "plates": round(plates, 3), "fill": round(fill, 4),
            "headers": {h: round(v, 3) for h, v in sorted(heads.items())},
            "blocking": round(blocking, 3)}


# ---- the drawings: its studs / insulation where a plan cuts them (phase 3b) ----------
#: a sheet at this scale or closer draws them (1:50, 1:25, 1:20) — further
#: off the X would be a smudge: the cut stays filled, as any wall
SYMBOL_SCALE = 50


def plan_symbols(w: dict, pieces, ops: list, z0: float, b: float,
                 top: float, cut: float) -> dict | None:
    """What a PLAN cut at ``cut`` shows of a framed core, in plan (x, y):
    {"blank": [polygons] — the pieces cut (their fill taken off), "lines":
    [(a, b)] — each stud's outline and X (wood) / its C (steel), the
    insulation's zigzag between the boards and its edges}. None: not
    framed."""
    fr = frame_of(w)
    if fr is None:
        return None
    G = Geo(w)
    S, P = G.S, G.P
    layers = W.layers_of(w)
    core = next((i for i, la in enumerate(layers) if la["role"] == "core"),
                0)
    lo, hi = W.layer_bands(w)[core] if len(layers) > 1 else \
        (-float(w["t"]) / 2, float(w["t"]) / 2)
    depth = hi - lo
    spans = spans_of(ops, z0, b, top)
    blank, lines = [], []

    def ring(poly):
        return list(zip(poly, poly[1:] + poly[:1]))

    for pc in pieces:
        parts = [part for i, part in W.layer_pieces(w, pc) if i == core] \
            if len(layers) > 1 else [pc]
        for part in parts:
            loop = frame_loop(w, part, G)
            if loop is None:
                continue
            A, A2, B2, B = G.ends(loop, w)
            got = layout(A, A2, B2, B, b, top, fr, spans,
                         top_line(w, z0, A, B),
                         fixed=w.get("_fix") or ())
            if got is None:
                continue
            for t, wood in \
                    [(t, True) for t in G.split(list(map(trap, got[0])))] + \
                    [(t, False) for t in G.split(list(map(trap, got[1])))]:
                m = (t[0] + t[1]) / 2
                if not z_at(t, m, False) < cut < z_at(t, m, True):
                    continue
                poly = G.cut(loop, t[0], t[1])
                if len(poly) < 3 or abs(W._area(poly)) < 1e-8:
                    continue
                blank.append(poly)
                if not wood:                         # the insulation
                    # (its edges along the boards; across, a stud's)
                    lines += [(p, q) for p, q in ring(poly)
                              if abs(S(p) - S(q)) > 1e-6]
                    k = max(2, math.ceil((t[1] - t[0]) / (depth / 2)))
                    h = (t[1] - t[0]) / k
                    e = depth * 0.12
                    zz = [P(t[0] + j * h, (lo + e) if j % 2 == 0
                            else (hi - e)) for j in range(k + 1)]
                    lines += list(zip(zz, zz[1:]))
                elif fr["kind"] == "wood":           # the stud and its X
                    lines += ring(poly)
                    if len(poly) >= 4:
                        lines += [(poly[0], poly[2]), (poly[1], poly[3])]
                else:                                # a steel C
                    lip = min(0.015, depth / 6)
                    c = [P(t[1], lo + lip), P(t[1], lo), P(t[0], lo),
                         P(t[0], hi), P(t[1], hi), P(t[1], hi - lip)]
                    lines += list(zip(c, c[1:]))
    return {"blank": blank, "lines": lines}


def section_symbols(w: dict, pieces, ops: list, z0: float, b: float,
                    top: float, q, nrm) -> dict | None:
    """What a vertical SECTION through ``q`` (normal ``nrm`` in plan) shows
    of a framed core where it crosses it, as (x, y, z): {"blank", "lines"}
    as ``plan_symbols`` — the plates, sills and headers cut across with
    their X (wood) / outlined (steel), the studs cut along outlined, the
    insulation's zigzag up between the boards. None: not framed or not
    crossed."""
    fr = frame_of(w)
    if fr is None:
        return None
    G = Geo(w)
    seg = G.seg
    nl = math.hypot(nrm[0], nrm[1]) or 1.0
    nrm = (nrm[0] / nl, nrm[1] / nl)
    # where the cut crosses the wall's centre: along it (s) — a curve may
    # be crossed twice (phase 4c: a curved wall's cut framed too)
    cuts = []
    if not G.arc:
        p0, u = seg.p0, seg.u
        du = u[0] * nrm[0] + u[1] * nrm[1]
        if abs(du) < 0.05:                # along the cut: not crossed
            return None
        cuts.append(((q[0] - p0[0]) * nrm[0] + (q[1] - p0[1]) * nrm[1]) / du)
    else:
        C, r = seg.C, seg.r
        t = (-nrm[1], nrm[0])             # the cut's line in plan
        f = (q[0] - C[0], q[1] - C[1])
        bq = f[0] * t[0] + f[1] * t[1]
        disc = bq * bq - (f[0] * f[0] + f[1] * f[1] - r * r)
        if disc <= 1e-9:
            return None
        for k in (-1.0, 1.0):
            lam = -bq + k * math.sqrt(disc)
            p = (q[0] + t[0] * lam, q[1] + t[1] * lam)
            rad = ((p[0] - C[0]) / r, (p[1] - C[1]) / r)
            # (nearly along the curve there: not a cut across it)
            if abs(rad[0] * t[0] + rad[1] * t[1]) < 0.3:
                continue
            fq, _o = seg.project(p)
            if -1e-9 <= fq <= 1 + 1e-9 and \
                    math.dist(p, seg.at(fq)) < 1e-4:
                cuts.append(fq * G.L)
    if not cuts:
        return None

    def P(s, o, z):
        x, y = G.P(s, o)
        return (x, y, z)
    S = G.S
    layers = W.layers_of(w)
    core = next((i for i, la in enumerate(layers) if la["role"] == "core"),
                0)
    lo, hi = W.layer_bands(w)[core] if len(layers) > 1 else \
        (-float(w["t"]) / 2, float(w["t"]) / 2)
    depth = hi - lo
    spans = spans_of(ops, z0, b, top)
    blank, lines = [], []
    for sc in cuts:
        for pc in pieces:
            parts = [part for i, part in W.layer_pieces(w, pc) if i == core] \
                if len(layers) > 1 else [pc]
            for part in parts:
                loop = frame_loop(w, part, G)
                if loop is None:
                    continue
                A, A2, B2, B = G.ends(loop, w)
                if not A + 1e-6 < sc < B - 1e-6:
                    continue
                got = layout(A, A2, B2, B, b, top, fr, spans,
                             top_line(w, z0, A, B),
                             fixed=w.get("_fix") or ())
                if got is None:
                    continue
                for t, wood in [(t, True) for t in map(trap, got[0])] + \
                        [(t, False) for t in map(trap, got[1])]:
                    if not t[0] + 1e-9 < sc < t[1] - 1e-9:
                        continue
                    za, zb_ = z_at(t, sc, False), z_at(t, sc, True)
                    if zb_ - za < TINY:
                        continue
                    box = [P(sc, lo, za), P(sc, hi, za), P(sc, hi, zb_),
                           P(sc, lo, zb_)]
                    blank.append(box)
                    if not wood:                         # the insulation
                        lines += [(box[0], box[1]), (box[3], box[2])]
                        k = max(2, math.ceil((zb_ - za) / (depth / 2)))
                        h = (zb_ - za) / k
                        e = depth * 0.12
                        zz = [P(sc, (lo + e) if j % 2 == 0 else (hi - e),
                                za + j * h) for j in range(k + 1)]
                        lines += list(zip(zz, zz[1:]))
                        continue
                    lines += list(zip(box, box[1:] + box[:1]))
                    # across (a plate, a sill, a header): its X; a stud cut
                    # along its length: its outline only
                    if fr["kind"] == "wood" and zb_ - za <= 3 * depth:
                        lines += [(box[0], box[2]), (box[1], box[3])]
                    # the treated sill plate on concrete (D8): its ANCHOR BOLT
                    # — down into what it sits on, a washer over the plate
                    if w.get("_treated") and fr["kind"] == "wood" \
                            and abs(za - b) < 1e-6 \
                            and abs(zb_ - za - fr["w"]) < 1e-6:
                        oc = (lo + hi) / 2
                        lines += [(P(sc, oc, za - BOLT_DEPTH),
                                   P(sc, oc, zb_ + 0.01)),
                                  (P(sc, oc - 0.025, zb_ + 0.002),
                                   P(sc, oc + 0.025, zb_ + 0.002))]
    return {"blank": blank, "lines": lines} if blank else None
