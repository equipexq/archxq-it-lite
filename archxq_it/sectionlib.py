# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The SECTION LIBRARY and a column's FORM (the shape editor, phase 4 —
17/11/2026). Pure: no Qt, no host.

* Ready sections for a column (its Shape tab's cards): «L», «T», «Cross»,
  fitted to the box the column has, with the arms' thickness typed.
* Steel I / H sections from the European tables (EN 10365): IPE, HEA, HEB
  — depth h, width b, web tw, flange tf and the root radius r exactly as
  the tables give them (the root fillets are curves of the outline: its
  area is the table's). Depth up the column's own frame, width across.
* A column's FORM, on top of any section:
  ``hollow`` — a tube: its wall's thickness (m), the inside its outline
  moved in by it (every face exactly that far off its own);
  ``tp`` — it NARROWS upwards: its top section the foot's scaled by tp
  (0.5 to under 1) round the section's centre;
  ``ent`` — the classical ENTASIS: straight for its lower third, then a
  gentle curve to its top (only with tp).
  No key: the column as it ever was.
"""
from __future__ import annotations

import math

from . import sectionshape as SS

# ---- steel: the tables -----------------------------------------------------------------
#: (h, b, tw, tf, r) in mm — EN 10365 (IPE, HEA, HEB). Only the sizes a
#: section can be: its web 5 mm at least (sectionshape.MIN_PART) and its
#: area 25 cm² at least (sectionshape.MIN_AREA) — from IPE 200, HEA 120
IPE = {200: (200, 100, 5.6, 8.5, 12), 220: (220, 110, 5.9, 9.2, 12),
       240: (240, 120, 6.2, 9.8, 15), 270: (270, 135, 6.6, 10.2, 15),
       300: (300, 150, 7.1, 10.7, 15), 330: (330, 160, 7.5, 11.5, 18),
       360: (360, 170, 8.0, 12.7, 18), 400: (400, 180, 8.6, 13.5, 21),
       450: (450, 190, 9.4, 14.6, 21), 500: (500, 200, 10.2, 16.0, 21),
       550: (550, 210, 11.1, 17.2, 24), 600: (600, 220, 12.0, 19.0, 24)}
HEA = {120: (114, 120, 5.0, 8.0, 12),
       140: (133, 140, 5.5, 8.5, 12), 160: (152, 160, 6.0, 9.0, 15),
       180: (171, 180, 6.0, 9.5, 15), 200: (190, 200, 6.5, 10.0, 18),
       220: (210, 220, 7.0, 11.0, 18), 240: (230, 240, 7.5, 12.0, 21),
       260: (250, 260, 7.5, 12.5, 24), 280: (270, 280, 8.0, 13.0, 24),
       300: (290, 300, 8.5, 14.0, 27), 320: (310, 300, 9.0, 15.5, 27),
       340: (330, 300, 9.5, 16.5, 27), 360: (350, 300, 10.0, 17.5, 27),
       400: (390, 300, 11.0, 19.0, 27), 450: (440, 300, 11.5, 21.0, 27),
       500: (490, 300, 12.0, 23.0, 27)}
HEB = {100: (100, 100, 6.0, 10.0, 12), 120: (120, 120, 6.5, 11.0, 12),
       140: (140, 140, 7.0, 12.0, 12), 160: (160, 160, 8.0, 13.0, 15),
       180: (180, 180, 8.5, 14.0, 15), 200: (200, 200, 9.0, 15.0, 18),
       220: (220, 220, 9.5, 16.0, 18), 240: (240, 240, 10.0, 17.0, 21),
       260: (260, 260, 10.0, 17.5, 24), 280: (280, 280, 10.5, 18.0, 24),
       300: (300, 300, 11.0, 19.0, 27), 320: (320, 300, 11.5, 20.5, 27),
       340: (340, 300, 12.0, 21.5, 27), 360: (360, 300, 12.5, 22.5, 27),
       400: (400, 300, 13.5, 24.0, 27), 450: (450, 300, 14.0, 26.0, 27),
       500: (500, 300, 14.5, 28.0, 27)}
FAMILIES = (("IPE", IPE), ("HEA", HEA), ("HEB", HEB))
STEEL_KG_M3 = 7850.0            # kg/m³ — the tables' mass per metre

# ---- concrete: the ready sections ------------------------------------------------------
READY = (("L", "L"), ("T", "T"), ("cross", "Cross"))
ARM = 0.15                      # m: the arms' thickness, by default
MIN_ARM = 0.05                  # m: thinner, refused
WHY_ARM = "The arms: 5 cm at least, and narrower than the column"

# ---- the form --------------------------------------------------------------------------
HOLLOW_MIN = 0.003              # m: a tube's wall, at least
TAPER_MIN = 0.5                 # its top: half its foot, at most that narrow
ENT_STEPS = 8                   # the entasis' curve: bands over its upper 2/3
WHY_HOLLOW = "The tube's wall: 3 mm at least, and room left inside"
WHY_TAPER = "Narrows to: between 50 % and 100 %"
WHY_ENT = "Entasis: the column must narrow (Narrows to under 100 %)"


# ---- steel ---------------------------------------------------------------------------
def steel_names() -> list:
    """Every table section's name, family by family: «IPE 200»…"""
    return [f"{fam} {n}" for fam, tab in FAMILIES for n in tab]


def steel_dims(name: str) -> tuple | None:
    """(h, b, tw, tf, r) in metres of a table section — None: no such."""
    try:
        fam, n = str(name).split()
        tab = dict(FAMILIES)[fam]
        h, b, tw, tf, r = tab[int(n)]
    except (ValueError, KeyError):
        return None
    return h / 1000, b / 1000, tw / 1000, tf / 1000, r / 1000


def steel(name: str) -> dict | None:
    """A table section's shape, centred on its insertion point: its depth
    up (y), its width across (x), the root fillets as curves."""
    d = steel_dims(name)
    if d is None:
        return None
    h, b, tw, tf, r = d
    x, y, w, f = b / 2, h / 2, tw / 2, h / 2 - tf
    ctrl = [[-x, -y], [x, -y], [x, -f], [w, -f], [w, f], [x, f], [x, y],
            [-x, y], [-x, f], [-w, f], [-w, -f], [-x, -f]]
    # the root fillets: the four inner corners (web ↔ flange)
    return SS.make(ctrl, {"r": {"3": r, "4": r, "9": r, "10": r},
                          "arc": {}})


def steel_area(name: str) -> float:
    """The table's area (m²): 2·b·tf + (h − 2·tf)·tw + (4 − π)·r²."""
    h, b, tw, tf, r = steel_dims(name)
    return 2 * b * tf + (h - 2 * tf) * tw + (4 - math.pi) * r * r


def steel_of(e: dict) -> str | None:
    """The table section a column's own outline is, exactly (wherever its
    insertion point) — None: none of them (edited, or never one)."""
    if e.get("shape") != "poly" or len(e.get("pts") or ()) != 12:
        return None
    try:
        pts = [(float(p[0]), float(p[1])) for p in e["pts"]]
    except (TypeError, ValueError, IndexError):
        return None
    cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
    cy = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    got = [(x - cx, y - cy) for x, y in pts]
    cv = e.get("curves") or {}
    rs = {str(k): float(v) for k, v in (cv.get("r") or {}).items()}
    if cv.get("arc"):
        return None
    for name in steel_names():
        prof = steel(name)
        want = prof["ctrl"]
        if all(abs(a[0] - b[0]) < 2e-6 and abs(a[1] - b[1]) < 2e-6
               for a, b in zip(got, want)) and rs == {
                   k: float(v) for k, v in prof["curves"]["r"].items()}:
            return name
    return None


# ---- concrete ------------------------------------------------------------------------
def ready(kind: str, w: float, d: float, a: float = ARM) -> tuple:
    """(shape, why): an «L», a «T» or a «Cross» filling a w × d box
    (centred), its arms ``a`` thick."""
    if a < MIN_ARM - 1e-9 or a > min(w, d) - MIN_ARM + 1e-9:
        return None, WHY_ARM
    x, y = w / 2, d / 2
    if kind == "L":                     # its corner at the lower left
        ctrl = [[-x, -y], [x, -y], [x, -y + a], [-x + a, -y + a],
                [-x + a, y], [-x, y]]
    elif kind == "T":                   # its flange on top
        h = a / 2
        ctrl = [[-h, -y], [h, -y], [h, y - a], [x, y - a], [x, y],
                [-x, y], [-x, y - a], [-h, y - a]]
    elif kind == "cross":
        h = a / 2
        ctrl = [[-h, -y], [h, -y], [h, -h], [x, -h], [x, h], [h, h],
                [h, y], [-h, y], [-h, h], [-x, h], [-x, -h], [-h, -h]]
    else:
        return None, WHY_ARM
    prof = SS.make(ctrl)
    why = SS.why_not(prof)
    return (None, why) if why else (prof, None)


# ---- the form ------------------------------------------------------------------------
def hollow(e: dict) -> float:
    """A tube's wall (m) — 0: solid."""
    try:
        return max(0.0, float(e.get("hollow") or 0.0))
    except (TypeError, ValueError):
        return 0.0


def taper(e: dict) -> float:
    """Its top's scale (1: it doesn't narrow)."""
    try:
        t = float(e.get("tp") or 1.0)
    except (TypeError, ValueError):
        return 1.0
    return t if TAPER_MIN - 1e-9 <= t < 1.0 - 1e-9 else 1.0


def entasis(e: dict) -> bool:
    return bool(e.get("ent")) and taper(e) < 1.0


def has_form(e: dict) -> bool:
    return hollow(e) > 0 or taper(e) < 1.0


def inner(outer, t: float):
    """The inside of a tube whose outline is ``outer`` (counter-clockwise):
    moved in by ``t`` everywhere, counter-clockwise — None when nothing is
    left (or it falls apart)."""
    from shapely.geometry import Polygon
    try:
        p = Polygon(outer).buffer(0).buffer(-t, join_style=2,
                                            mitre_limit=10.0)
    except Exception:  # noqa: BLE001
        return None
    if p.is_empty or p.geom_type != "Polygon" or p.area < 1e-6:
        return None
    from shapely.geometry.polygon import orient
    return [tuple(q) for q in list(orient(p, 1.0).exterior.coords)[:-1]]


def why_form(e: dict, outer=None) -> str | None:
    """Why its form can't be (None = it can, or it has none). ``outer``:
    its section in plan (counter-clockwise), to check the tube's inside."""
    if e.get("hollow") not in (None, 0, 0.0):
        try:
            t = float(e["hollow"])
        except (TypeError, ValueError):
            return WHY_HOLLOW
        if t < HOLLOW_MIN - 1e-9:
            return WHY_HOLLOW
        if outer is not None:
            # (its wall 5 mm at least where the outline is: no sliver)
            if inner(outer, t) is None:
                return WHY_HOLLOW
    if e.get("tp") is not None:
        try:
            tp = float(e["tp"])
        except (TypeError, ValueError):
            return WHY_TAPER
        if not TAPER_MIN - 1e-9 <= tp <= 1.0 + 1e-9:
            return WHY_TAPER
    if e.get("ent") and taper(e) >= 1.0:
        return WHY_ENT
    return None


def clean_form(e: dict, src: dict) -> dict:
    """``e`` with ``src``'s form when it is one (kept only whole): its
    keys set, or gone."""
    r = {k: v for k, v in e.items() if k not in ("hollow", "tp", "ent")}
    try:
        t = round(float(src.get("hollow") or 0.0), 4)
    except (TypeError, ValueError):
        t = 0.0
    try:
        tp = round(float(src.get("tp") or 1.0), 3)
    except (TypeError, ValueError):
        tp = 1.0
    if t >= HOLLOW_MIN - 1e-9:
        r["hollow"] = t
    if TAPER_MIN - 1e-9 <= tp < 1.0 - 1e-9:
        r["tp"] = tp
        if src.get("ent"):
            r["ent"] = True
    return r


def scales(e: dict) -> list:
    """[(f, s)]: up its height (f 0 → 1), its section's scale — straight
    from 1 to tp, or the entasis' curve; [(0, 1), (1, 1)] when it doesn't
    narrow."""
    tp = taper(e)
    if tp >= 1.0:
        return [(0.0, 1.0), (1.0, 1.0)]
    if not entasis(e):
        return [(0.0, 1.0), (1.0, tp)]
    out = [(0.0, 1.0), (1 / 3, 1.0)]
    for k in range(1, ENT_STEPS + 1):
        u = k / ENT_STEPS
        out.append((1 / 3 + u * 2 / 3, 1.0 - (1.0 - tp) * u * u))
    return out


def volume_factor(e: dict) -> float:
    """Its volume ÷ (its foot's section × its height): each band a
    frustum (the sections similar: s0² + s0·s1 + s1², a third)."""
    v = 0.0
    sc = scales(e)
    for (f0, s0), (f1, s1) in zip(sc, sc[1:]):
        v += (f1 - f0) * (s0 * s0 + s0 * s1 + s1 * s1) / 3
    return v


def section_area(e: dict, outer_area: float, outer=None) -> float:
    """Its section at the foot (m²): its outline's area less a tube's
    inside — exact for a rectangle and a circle, from ``outer`` (its
    outline in fine steps) otherwise."""
    t = hollow(e)
    if t <= 0:
        return outer_area
    if e.get("shape") == "round":
        r = float(e["w"]) / 2 - t
        return outer_area - math.pi * max(r, 0.0) ** 2
    if e.get("shape") != "poly":
        return outer_area - max(float(e["w"]) - 2 * t, 0.0) * \
            max(float(e["d"]) - 2 * t, 0.0)
    if outer is None:
        return outer_area
    from shapely.geometry import Polygon
    ins = inner(outer, t)
    return outer_area - (Polygon(ins).area if ins else 0.0)


def faces(piece: dict, z0: float, z1: float, sc: list, centre) -> list:
    """A shaft from z0 to z1, its section (``piece``: outer + holes, as
    walls.solid takes it) scaled up its height by ``sc`` round ``centre``:
    its foot, its top, and each band's sides (planar: a side's edges stay
    parallel as the section scales). Outward, as walls.solid. Each side
    marked ``curve``: a round shaft's facets and an entasis' bands read
    as one surface under 25° (compat._soften_flat_seams) — a sloped
    facet isn't upright, so it drew a line otherwise (live 2026-11-17);
    a corner stays drawn."""
    from . import walls as W
    if all(abs(s - 1.0) < 1e-12 for _f, s in sc):
        return W.solid(piece, z0, z1)
    cx, cy = centre

    def at(loop, s):
        return [(cx + (x - cx) * s, cy + (y - cy) * s) for x, y in loop]

    def lift(loop, z):
        return [(x, y, z) for x, y in loop]
    outer, holes = piece["outer"], piece.get("holes") or []
    st = sc[-1][1]
    out = [{"loop": lift(at(outer, st), z1),
            "holes": [lift(at(h, st), z1) for h in holes]},
           {"loop": lift(list(reversed(outer)), z0),
            "holes": [lift(list(reversed(h)), z0) for h in holes]}]
    for (f0, s0), (f1, s1) in zip(sc, sc[1:]):
        za, zb = z0 + (z1 - z0) * f0, z0 + (z1 - z0) * f1
        for loop in [outer] + list(holes):
            lo, hi = at(loop, s0), at(loop, s1)
            n = len(loop)
            for i in range(n):
                j = (i + 1) % n
                out.append({"loop": [(lo[i][0], lo[i][1], za),
                                     (lo[j][0], lo[j][1], za),
                                     (hi[j][0], hi[j][1], zb),
                                     (hi[i][0], hi[i][1], zb)],
                            "holes": [], "curve": True})
    return out
