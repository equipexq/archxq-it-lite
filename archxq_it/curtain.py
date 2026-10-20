"""The CURTAIN WALL — a wall type (his corporate building, 2026-10-12: half
of it is glass, floor to floor, a dark band at every slab).

A wall with ``cw`` True is drawn, joined, moved and stretched as any wall
(its record is a wall's); only its FACES are other: in its joined plan
piece, posts at its two ends (cut on the corner's mitre), mullions every
``cw_s`` m or so, the glass — and, with ``cw_band``, a dark spandrel band
at its foot over the slab's edge (an outside wall goes down through its
slab: ``structure.wall_drops``), a transom on it. The slab stops behind it
(``structure.outside_walls``).

Its own sizes (his ask, 2026-10-14 — the glass floor of the corporate
building: «the width and the depth of the vertical and the horizontal
pieces, and of the corners»): each piece's WIDTH (seen from outside) and
DEPTH, measured from the wall's OUTER face inwards — so the frame stays
flush with a masonry wall below, whatever its depth. The band sits on the
outer face too (it was in the glass plane: a 6 cm step under the masonry's
face) and its height over the floor is the wall's own.

Every piece is CUT from the wall's own plan (shapely), so nothing overlaps
and no two faces share a plane. Pure geometry — ``structure`` calls it.
"""
from __future__ import annotations

ALU = 0.05               # m, a post's / mullion's / transom's usual width
SPACING = 1.25           # m, mullions' usual spacing
GLASS_T = 0.012          # m, the glass
BAND_UP = 0.10           # m, how far the spandrel band rises over the floor
BAND_T = 0.03            # m, the band panel's thickness
INSET = 0.01             # m, a transom kept in from the mullions' faces
FACE = 0.001             # m, the band kept in from the outer face (1 mm)
CAP = 0.02               # m, glass «on the outside»: behind a 2 cm cap

#: the colours offered (key → rgba); the frame's, the glass's, the band's
FRAMES = {"dark": (0.18, 0.19, 0.21, 1.0), "black": (0.05, 0.05, 0.06, 1.0),
          "silver": (0.70, 0.72, 0.74, 1.0), "white": (0.92, 0.92, 0.92, 1.0),
          "bronze": (0.33, 0.25, 0.18, 1.0)}
GLASSES = {"blue": (0.50, 0.66, 0.74, 0.32), "clear": (0.80, 0.88, 0.90, 0.22),
           "green": (0.45, 0.66, 0.60, 0.32), "grey": (0.45, 0.48, 0.50, 0.38),
           "bronze": (0.55, 0.45, 0.35, 0.35)}
BANDS = {"dark": (0.08, 0.09, 0.10, 1.0), "black": (0.03, 0.03, 0.04, 1.0),
         "grey": (0.40, 0.42, 0.45, 1.0), "white": (0.90, 0.90, 0.90, 1.0),
         "frame": None}                     # «as the frame»

ALU_COLOR = FRAMES["dark"]
GLASS_COLOR = GLASSES["blue"]
BAND_COLOR = BANDS["dark"]

#: what a new curtain wall starts with (ui's wall_opts; model._walls). A
#: depth of 0 = the wall's whole thickness (a transom's: less 2 × INSET)
DEFAULTS = {"cw_s": SPACING, "cw_band": True, "cw_rows": 0,
            "cw_band_h": BAND_UP, "cw_glass": "centre",
            "cw_mw": ALU, "cw_md": 0.0, "cw_tw": ALU, "cw_td": 0.0,
            "cw_pw": ALU, "cw_pd": 0.0,
            "cw_frame": "dark", "cw_glass_c": "blue", "cw_band_c": "dark",
            # how much light the glass lets through (his ask, 2026-10-14);
            # 0.68 = the blue glass as it was
            "cw_glass_tr": 0.68}
#: every key of a curtain wall's own (model keeps them, the windows carry)
KEYS = tuple(DEFAULTS)


def clean(w: dict) -> dict:
    """A curtain wall's own keys, read and kept in their ranges (model)."""
    def num(k, lo, hi):
        try:
            v = float(w.get(k, DEFAULTS[k]))
        except (TypeError, ValueError):
            v = DEFAULTS[k]
        return min(max(v, lo), hi)
    out = {"cw_s": num("cw_s", 0.3, 6.0),
           "cw_band": bool(w.get("cw_band", True)),
           "cw_rows": min(max(int(w.get("cw_rows", 0) or 0), 0), 6),
           "cw_band_h": num("cw_band_h", 0.0, 2.0),
           "cw_glass": w.get("cw_glass") if w.get("cw_glass") in
           ("centre", "outside") else "centre"}
    for k in ("cw_mw", "cw_tw", "cw_pw"):
        out[k] = num(k, 0.02, 0.60)
    for k in ("cw_md", "cw_td", "cw_pd"):
        out[k] = num(k, 0.0, 3.0)
    out["cw_glass_tr"] = num("cw_glass_tr", 0.0, 0.95)
    for k, table in (("cw_frame", FRAMES), ("cw_glass_c", GLASSES),
                     ("cw_band_c", BANDS)):
        out[k] = w.get(k) if w.get(k) in table else DEFAULTS[k]
    return out


def _piece_dict(g) -> list:
    """shapely (Multi)Polygon → plan pieces {outer, holes}, ccw."""
    from shapely.geometry.polygon import orient
    out = []
    for p in getattr(g, "geoms", [g]):
        if p.is_empty or p.geom_type != "Polygon" or p.area < 1e-7:
            continue
        p = orient(p, 1.0)
        out.append({"outer": list(p.exterior.coords)[:-1],
                    "holes": [list(r.coords)[:-1] for r in p.interiors]})
    return out


def sizes(w: dict) -> dict:
    """The pieces' sizes for this wall, depths resolved (0 = whole)."""
    c = clean(w)
    t = float(w["t"])
    md = min(c["cw_md"] or t, t)
    return {"mw": c["cw_mw"], "md": md,
            "pw": c["cw_pw"], "pd": min(c["cw_pd"] or t, t),
            "tw": c["cw_tw"],
            "td": min(c["cw_td"] or t - 2 * INSET, t - INSET)}


def faces(w: dict, pieces, z0: float, b: float, top: float,
          ops=()) -> list:
    """The curtain wall's faces (with their colours) in its plan
    ``pieces``, from ``b`` (its foot) to ``top``; ``z0`` its floor.
    ``ops``: its openings (fitted — pos, w, sill, h): every piece of frame,
    glass and band is cut out where one stands (the door / window is built
    in it by ``structure.opening_parts``)."""
    from shapely.geometry import Polygon, box
    from shapely import affinity
    import math

    from . import walls as W
    from .structure import _faces

    seg = W.centre(w)
    if seg.kind != "line":
        return []
    p0, u = seg.p0, seg.u
    ang = math.degrees(math.atan2(u[1], u[0]))
    t = float(w["t"])
    c = clean(w)
    sz = sizes(w)
    mw, md, pw, pd, tw, td = (sz[k] for k in ("mw", "md", "pw", "pd",
                                              "tw", "td"))
    s_gap = max(c["cw_s"], 0.3)
    band_h = c["cw_band_h"]
    band = c["cw_band"] and z0 + band_h + tw < top - 0.3
    rows = c["cw_rows"]
    frame_c = FRAMES[c["cw_frame"]]
    # the tint's colour, its transparency the wall's own
    glass_c = GLASSES[c["cw_glass_c"]][:3] + (round(1.0 - c["cw_glass_tr"],
                                                    3),)
    band_c = BANDS[c["cw_band_c"]] or frame_c
    # across the wall (its frame's «c»): the inside is +side, the OUTER
    # face at -side·t/2; a depth runs from it inwards
    side = -1.0 if float(w.get("side", 1)) < 0 else 1.0
    c_out = -side * t / 2

    def across(d0, d1):
        """From d0 to d1 in from the outer face → (c_lo, c_hi)."""
        a, e = c_out + side * d0, c_out + side * d1
        return min(a, e), max(a, e)
    out = []

    def frame(s0, s1, ca, cb):
        """The plan rectangle s0..s1 along, ca..cb across (wall's frame)."""
        g = box(s0, ca, s1, cb)
        g = affinity.rotate(g, ang, origin=(0, 0))
        return affinity.translate(g, p0[0], p0[1])

    # its openings: (s0, s1, z_lo, z_hi) — 1 mm wider / taller, so no
    # face of the frame lies in the opening's own jamb / head plane
    holes = []
    for o in ops or ():
        try:
            s0 = float(o["pos"]) - float(o["w"]) / 2 - 0.001
            s1 = float(o["pos"]) + float(o["w"]) / 2 + 0.001
            zl = z0 + float(o.get("sill", 0.0)) - 0.001
            zh = z0 + float(o.get("sill", 0.0)) + float(o["h"]) + 0.001
        except (KeyError, TypeError, ValueError):
            continue
        if s1 - s0 > 0.02 and zh - zl > 0.02:
            holes.append((s0, s1, zl, zh))

    def _plain(g, za, zb, color):
        if g.is_empty or zb - za < 1e-4:
            return
        for pc in _piece_dict(g):
            out.extend(_faces(W.solid(pc, za, zb), color))

    def solid(g, za, zb, color):
        """``g`` from za to zb — less every opening it meets: beside an
        opening it stands whole; over its stretch, only under its sill and
        over its head."""
        if g.is_empty:
            return
        parts = [(g, za, zb)]
        for s0, s1, zl, zh in holes:
            nxt = []
            for gg, a, e in parts:
                if zh <= a or zl >= e:
                    nxt.append((gg, a, e))
                    continue
                band_ = frame(s0, s1, -1e4, 1e4)
                inside = gg.intersection(band_)
                if inside.is_empty:
                    nxt.append((gg, a, e))
                    continue
                rest = gg.difference(band_)
                if not rest.is_empty:
                    nxt.append((rest, a, e))
                if zl > a:
                    nxt.append((inside, a, min(zl, e)))
                if zh < e:
                    nxt.append((inside, max(zh, a), e))
            parts = nxt
        for gg, a, e in parts:
            _plain(gg, a, e, color)

    if c["cw_glass"] == "outside":
        g_mid = min(CAP + GLASS_T / 2, md - GLASS_T / 2)
    else:
        g_mid = md / 2
    g_cross = across(g_mid - GLASS_T / 2, g_mid + GLASS_T / 2)
    t_cross = across(INSET, min(INSET + td, t - INSET))
    for pc in pieces:
        try:
            poly = Polygon(pc["outer"], pc.get("holes") or []).buffer(0)
        except Exception:  # noqa: BLE001
            continue
        if poly.is_empty:
            continue
        # its stretch along the centre line (the mitres run past it)
        line = poly.intersection(frame(-1e4, 1e4, -1e-4, 1e-4))
        if line.is_empty:
            continue
        xs = [(q[0] - p0[0]) * u[0] + (q[1] - p0[1]) * u[1]
              for q in _coords(line)]
        c0s, c1s = min(xs), max(xs)
        if c1s - c0s < 2 * pw + 0.05:
            solid(poly, b, top, frame_c)          # too short: all frame
            continue
        lo, hi = c0s + pw, c1s - pw
        # the end posts: everything of the piece past lo / hi (the mitre),
        # as deep as their own depth
        solid(poly.intersection(frame(-1e4, lo, *across(0.0, pd))), b, top,
              frame_c)
        solid(poly.intersection(frame(hi, 1e4, *across(0.0, pd))), b, top,
              frame_c)
        # the mullions between
        k = max(1, round((hi - lo) / s_gap))
        step = (hi - lo) / k
        mull = [lo + step * i for i in range(1, k)]
        for m in mull:
            solid(poly.intersection(frame(m - mw / 2, m + mw / 2,
                                          *across(0.0, md))),
                  b, top, frame_c)
        # between the mullions: glass (and the band, its transom)
        # (each runs 1 cm INTO what holds it: no end face in a mullion's
        # plane — the 1 cm rule)
        cuts = [lo] + mull + [hi]
        zg = b + 0.01
        lo_z = b
        if band:
            lo_z = z0 + band_h + tw
            zg = lo_z - 0.01
        for i in range(len(cuts) - 1):
            a0 = cuts[i] + (0.0 if i == 0 else mw / 2) - 0.01
            a1 = cuts[i + 1] - (0.0 if i == len(cuts) - 2 else mw / 2) + 0.01
            if a1 - a0 < 0.04:
                continue
            if band:
                # on the OUTER face (1 mm in: never a mullion's plane) —
                # flush with a masonry wall below
                solid(poly.intersection(frame(a0, a1, *across(FACE,
                                                              FACE + BAND_T))),
                      b + 0.01, z0 + band_h + 0.01, band_c)
                solid(poly.intersection(frame(a0, a1, *t_cross)),
                      z0 + band_h, z0 + band_h + tw, frame_c)
            solid(poly.intersection(frame(a0, a1, *g_cross)),
                  zg, top - 0.01, glass_c)
            # rows: transoms across the glass, evenly (his render's grid
            # of near-square panes) — kept in from the mullions' faces
            for r in range(1, rows + 1):
                zr = lo_z + (top - lo_z) * r / (rows + 1)
                solid(poly.intersection(frame(a0, a1, *t_cross)),
                      zr - tw / 2, zr + tw / 2, frame_c)
    return out


def _coords(g) -> list:
    out = []
    for p in getattr(g, "geoms", [g]):
        if hasattr(p, "exterior"):
            out += list(p.exterior.coords)
        elif hasattr(p, "coords"):
            out += list(p.coords)
    return out
