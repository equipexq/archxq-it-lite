# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A PLAN SHEET, worked out on paper — the target is the reference sheet
approved on 2026-10-22 (MAQUETAS\\documentacao_planta_referencia_v2.html):
NBR 6492 / 8402 / 10068.

``make(doc, elevations, sheet, style)`` gives the sheet as NEUTRAL pieces in
paper millimetres (page origin top-left, y down) — each with a STABLE key,
so that a sheet made again finds the pieces the architect moved or hid in
the composer (``hostsheet`` keeps those). Nothing here knows the host.

What the algorithm does for the architect (his rule: «the bureaucracy is
the algorithm's»): paper and scale that fit; outside dimensions in three
rows from what is SEEN from outside; a dimension chain across the rooms;
the rooms' names, areas and levels; door / window tags in a free place and
their schedule (sizes a few cm apart are one type); the side column (north,
the levels as the building stands, legend, schedule, notes) and the title
block.
"""
from __future__ import annotations

import datetime
import math

from . import docstyle as DS
from . import framing as FR
from . import structure as S
from . import walls as W

#: landscape pages, mm (w, h)
PAPERS_MM = {"A4": (297.0, 210.0), "A3": (420.0, 297.0),
             "A2": (594.0, 420.0), "A1": (841.0, 594.0),
             "A0": (1189.0, 841.0)}
TITLE_STRIP_MM = 40.0     # the drawing's title and the scale bar, under it
GAP_MM = 6.0              # between the drawing area and what is round it
#: opening sizes this close are one type (m): width / height and sill
TYPE_TOL = (0.03, 0.06)
TAG_OFF = (0.95, 1.35, 1.75)      # m off the opening, into the room
SEEN_EPS = 0.06                   # m — a point just off a wall's face
#: a room's use, from its name (the fill's colour, the legend)
USES = (("wet", ("WC", "BANH", "SANIT", "LAVAB", "TOILET", "BATH", "BAD",
                 "VESTI")),
        ("stair", ("ESCADA", "STAIR", "TREPPE")),
        ("hall", ("HALL", "CIRC", "CORRED", "FOYER", "FLUR", "LOBBY",
                  "RECEP", "ENTRAD")))


def use_of(name: str) -> str:
    up = (name or "").upper()
    for use, keys in USES:
        if any(k in up for k in keys):
            return use
    return "room"


# ---- the building's plan ----------------------------------------------------------------
def _pieces(walls: list[dict]) -> list:
    from shapely.geometry import Polygon
    out = []
    for pcs in W.plan(walls).values():
        for pc in pcs:
            p = Polygon(pc["outer"], pc["holes"])
            out.append(p if p.is_valid else p.buffer(0))
    return out


def _union(walls: list[dict]):
    from shapely.ops import unary_union
    return unary_union(_pieces(walls)).buffer(1e-4, join_style=2) \
        .buffer(-1e-4, join_style=2)


def _gap(o: dict, w: dict):
    """The opening's rectangle in plan (the wall's two faces), or None."""
    if w.get("kind", "line") != "line":
        return None
    try:
        seg = W.centre(w)
    except Exception:  # noqa: BLE001 — a broken wall: no opening drawn
        return None
    p0, u = seg.p0, seg.u
    n = (-u[1], u[0])
    t = float(w["t"]) / 2
    s0, s1 = float(o["pos"]) - float(o["w"]) / 2, \
        float(o["pos"]) + float(o["w"]) / 2

    def P(s, c):
        return (p0[0] + u[0] * s + n[0] * c, p0[1] + u[1] * s + n[1] * c)
    return {"pts": [P(s0, -t), P(s1, -t), P(s1, t), P(s0, t)],
            "c": P((s0 + s1) / 2, 0.0), "n": n, "u": u}


DIRS = {"S": (0.0, -1.0), "N": (0.0, 1.0), "W": (-1.0, 0.0), "E": (1.0, 0.0)}


def seen(U, p, side: str) -> bool:
    """The point sees out of the building on that side: nothing of the
    walls between it and the far away (the reference's rule — a recessed
    wall's corner is not dimensioned on the outside row)."""
    from shapely.geometry import LineString
    dx, dy = DIRS[side]
    a = (p[0] + dx * SEEN_EPS, p[1] + dy * SEEN_EPS)
    b = (p[0] + dx * 1e4, p[1] + dy * 1e4)
    return not LineString([a, b]).intersects(U)


def _clean(vals, tol=0.04) -> list[float]:
    out: list[float] = []
    for v in sorted(vals):
        if not out or v - out[-1] > tol:
            out.append(v)
    return out


# ---- what a dimension measures (PLANO_COTAS_FOLHAS.md, C0) -----------------------
# A dimension's key is WHAT it measures — a wall's face at one of its ends,
# an opening's side — never its place in a row: a window put in, a wall
# moved, and the dimension he hid or moved is still the same one
# (Kamen #104, «impossible à modifier»: keyed by index, his edits landed
# on another dimension after a change).
def stop_namer(walls: list[dict]):
    """``name(p, ends=True)``: the name of a plan point on the walls'
    outline — «<wall id>.<face L|R>.<end a|b>» (``ends`` False: the face
    only); a point on no wall: its place to the cm."""
    from shapely.geometry import Point, Polygon
    rows = []
    try:
        plan = W.plan(walls)
    except Exception:  # noqa: BLE001 — no plan: names by place only
        plan = {}
    for w in sorted(walls, key=lambda w: str(w["id"])):
        polys = []
        for pc in plan.get(w["id"]) or []:
            try:
                polys.append(Polygon(pc["outer"], pc.get("holes") or []
                                     ).boundary)
            except Exception:  # noqa: BLE001 — a broken piece: skipped
                continue
        if not polys:
            continue
        try:
            seg = W.centre(w)
            line = (seg.p0, seg.u, seg.L) if seg.kind == "line" else None
        except Exception:  # noqa: BLE001 — a broken wall: no axis
            line = None
        rows.append((str(w["id"]), polys, line))

    def name(p, ends: bool = True) -> str:
        q = Point(p)
        for wid, polys, line in rows:
            # (1 mm: the walls' union is buffered ±0,1 mm — ``_union``)
            if not any(b.distance(q) < 1e-3 for b in polys):
                continue
            if line is None:
                return f"{wid}@{p[0]:.2f},{p[1]:.2f}"
            (x0, y0), (ux, uy), L = line
            dx, dy = p[0] - x0, p[1] - y0
            face = "L" if ux * dy - uy * dx > 0 else "R"
            if not ends:
                return f"{wid}.{face}"
            return f"{wid}.{face}.{'a' if dx * ux + dy * uy < L / 2 else 'b'}"
        return f"@{p[0]:.2f},{p[1]:.2f}"
    return name


def _named(names: dict, v: float) -> str:
    """The name of the stop at ``v`` (or the nearest one, the stops
    ``_clean`` joined)."""
    if v in names:
        return names[v]
    if not names:
        return f"@{v:.2f}"
    k = min(names, key=lambda x: abs(x - v))
    return names[k] if abs(k - v) <= 0.0401 else f"@{v:.2f}"


def unique_refs(dims: list[dict]) -> list[dict]:
    """Each dimension's ``ref`` once in its row (a second one alike:
    «#2»)."""
    seen_: dict = {}
    for d in dims:
        r = d["ref"]
        k = (d.get("side"), d.get("row"), d.get("axis"), r)
        n = seen_[k] = seen_.get(k, 0) + 1
        if n > 1:
            d["ref"] = f"{r}#{n}"
    return dims


def outside_dims(walls, openings, U, rows: int) -> list[dict]:
    """[{"side", "row" 1|2|3, "a", "b", "ref"}] — row 1: corners and
    openings, row 2: corners, row 3: the overall size; a, b on the box's
    side; ``ref``: what it measures, from stop to stop (C0)."""
    if rows <= 0 or U.is_empty:
        return []
    x0, y0, x1, y1 = U.bounds
    byid = {w["id"]: w for w in walls}
    corners = {s: set() for s in DIRS}
    opens = {s: set() for s in DIRS}
    names: dict = {s: {} for s in DIRS}
    namer = stop_namer(walls)
    polys = list(getattr(U, "geoms", [U]))
    for g in polys:
        for ring in [g.exterior] + list(g.interiors):
            for x, y in list(ring.coords)[:-1]:
                for s in DIRS:
                    if seen(U, (x, y), s):
                        v = round(x if s in "SN" else y, 4)
                        corners[s].add(v)
                        nm = namer((x, y))
                        # (two corners at one place: the same name always)
                        names[s][v] = min(names[s].get(v, nm), nm)
    # a CURVED wall's outline is many short facets, each one a «corner»:
    # the rows came out as dozens of 2 cm stretches stacked on each other
    # (r_demo's porch, 14/11/2026). Its two far ends only
    for s in DIRS:
        arcs: dict = {}
        for v, nm in names[s].items():
            if "@" in nm and not nm.startswith("@"):
                arcs.setdefault(nm.split("@")[0], []).append(v)
        for vs in arcs.values():
            for v in vs:
                if v not in (min(vs), max(vs)):
                    corners[s].discard(v)
                    names[s].pop(v, None)
    for o in openings:
        w = byid.get(o.get("wall"))
        gp = _gap(o, w) if w else None
        if gp is None:
            continue
        for s in DIRS:
            if any(seen(U, p, s) for p in gp["pts"]):
                vs = [p[0] if s in "SN" else p[1] for p in gp["pts"]]
                lo_, hi_ = round(min(vs), 4), round(max(vs), 4)
                opens[s] |= {lo_, hi_}
                names[s].setdefault(lo_, f"o:{o['id']}:lo")
                names[s].setdefault(hi_, f"o:{o['id']}:hi")
    fixed = {"S": y0, "N": y1, "W": x0, "E": x1}
    out = []
    for s in DIRS:
        lo, hi = (x0, x1) if s in "SN" else (y0, y1)
        if not corners[s]:
            continue
        c = _clean(v for v in corners[s] | {lo, hi} if lo - 1e-6 <= v <= hi + 1e-6)
        full = _clean(v for v in corners[s] | opens[s] | {lo, hi}
                      if lo - 1e-6 <= v <= hi + 1e-6)

        def P(v):
            return (v, fixed[s]) if s in "SN" else (fixed[s], v)
        want = {3: [(1, full), (2, c)], 2: [(1, full)], 1: []}[min(rows, 3)]
        for row, stops in want:
            if row == 1 and rows >= 3 and full == c:
                continue                     # nothing more than the corners
            if len(stops) > 2:
                out += [{"side": s, "row": row, "a": P(a), "b": P(b),
                         "ref": f"{_named(names[s], a)}~"
                                f"{_named(names[s], b)}"}
                        for a, b in zip(stops, stops[1:]) if b - a > 0.02]
        out.append({"side": s, "row": 3, "a": P(lo), "b": P(hi),
                    "ref": "total"})
    return unique_refs(out)


def inside_dims(U, rooms, walls=None) -> list[dict]:
    """One chain across the rooms each way — the clear spans between the
    walls' faces, on the line (through the rooms' label points) that
    crosses the most rooms. [{"axis": "h"|"v", "a", "b", "ref"}] — ``ref``
    the two faces it stands between (C0; ``walls`` none: by place)."""
    from shapely.geometry import LineString
    if U.is_empty or not rooms:
        return []
    namer = stop_namer(walls or [])
    x0, y0, x1, y1 = U.bounds
    out = []
    for axis in ("h", "v"):
        best = None
        for r in rooms:
            v = r["at"][1] if axis == "h" else r["at"][0]
            line = LineString([(x0 - 1, v), (x1 + 1, v)] if axis == "h"
                              else [(v, y0 - 1), (v, y1 + 1)])
            cut = line.intersection(U)
            segs = sorted(([min(c[0] if axis == "h" else c[1]
                                for c in g.coords),
                            max(c[0] if axis == "h" else c[1]
                                for c in g.coords)]
                           for g in getattr(cut, "geoms", [cut])
                           if not g.is_empty and g.length > 1e-6),
                          key=lambda s: s[0])
            spans = [(a[1], b[0]) for a, b in zip(segs, segs[1:])
                     if b[0] - a[1] > 0.3]
            score = (len(spans), -abs(v - ((y0 + y1) / 2 if axis == "h"
                                           else (x0 + x1) / 2)))
            if spans and (best is None or score > best[0]):
                best = (score, v, spans)
        if best:
            _, v, spans = best
            for a, b in spans:
                pa = (a, v) if axis == "h" else (v, a)
                pb = (b, v) if axis == "h" else (v, b)
                out.append({"axis": axis, "a": pa, "b": pb,
                            "ref": f"{namer(pa, ends=False)}~"
                                   f"{namer(pb, ends=False)}"})
    return unique_refs(out)


# ---- the plan from inside (PLANO_COTAS_FOLHAS.md, C1) ------------------------------
# Kamen #104: «trop sommaire» — one chain each way, through the rooms'
# labels, was all the inside had. Now: every room both ways (its clear
# width and length, between the walls' faces, on a line clear of its
# label), rooms in a row on ONE chain, and — «Rooms and walls» — the
# walls' thicknesses on the chain that crosses them and, along each
# interior wall with a door or window, face — opening — face.
def _iv(geom, axis: str) -> list[tuple[float, float]]:
    """A line's cut through ``geom`` as sorted [t0, t1] (t = x along «h»,
    y along «v»)."""
    out = []
    for g in getattr(geom, "geoms", [geom]):
        if g.is_empty or g.length < 1e-6 or g.geom_type != "LineString":
            continue
        ts = [c[0] if axis == "h" else c[1] for c in g.coords]
        out.append((min(ts), max(ts)))
    return sorted(out)


def _filled(U):
    """The building with its rooms: the walls' outlines, the holes filled."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    return unary_union([Polygon(g.exterior)
                        for g in getattr(U, "geoms", [U])
                        if g.geom_type == "Polygon"])


def _chord(poly, axis: str, v: float) -> float:
    """The longest straight stretch of ``poly`` on the line at ``v``."""
    from shapely.geometry import LineString
    x0, y0, x1, y1 = poly.bounds
    line = LineString([(x0 - 1, v), (x1 + 1, v)] if axis == "h"
                      else [(v, y0 - 1), (v, y1 + 1)])
    return max((b - a for a, b in _iv(line.intersection(poly), axis)),
               default=0.0)


def chain_at(U, F, rooms, axis: str, v: float) -> list[list[tuple]]:
    """The building crossed at ``v``: its runs (one per stretch inside the
    building), each [(t0, t1, "wall"|"space")…] — the walls' thicknesses
    and the clear spans between their faces; a span two rooms share (a
    separator, no wall) cut where they meet."""
    from shapely.geometry import LineString
    x0, y0, x1, y1 = F.bounds
    line = LineString([(x0 - 1, v), (x1 + 1, v)] if axis == "h"
                      else [(v, y0 - 1), (v, y1 + 1)])
    solid = _iv(line.intersection(U), axis)
    cuts = []
    for r in rooms:
        for a, b in _iv(line.intersection(r["poly"]), axis):
            cuts += [a, b]
    runs = []
    for f0, f1 in _iv(line.intersection(F), axis):
        run, t = [], f0
        for a, b in solid:
            if b <= f0 + 1e-6 or a >= f1 - 1e-6:
                continue
            a, b = max(a, f0), min(b, f1)
            if a - t > 0.02:
                run.append((t, a, "space"))
            run.append((a, b, "wall"))
            t = b
        if f1 - t > 0.02:
            run.append((t, f1, "space"))
        cut_run = []
        for a, b, kind in run:
            if kind == "space":
                inner = sorted(c for c in cuts if a + 0.02 < c < b - 0.02)
                stops = _clean([a] + inner + [b], 0.02)
                cut_run += [(p, q, "space") for p, q in zip(stops, stops[1:])]
            elif b - a > 0.005:
                cut_run.append((a, b, kind))
        if cut_run:
            runs.append(cut_run)
    return runs


def _free_rooms(U, F) -> list[dict]:
    """No rooms on the sheet: the spaces the walls close, as rooms."""
    out = []
    left = F.difference(U)
    for g in getattr(left, "geoms", [left]):
        if g.geom_type == "Polygon" and g.area > 1.0:
            p = g.representative_point()
            out.append({"poly": g, "at": (p.x, p.y), "name": ""})
    return out


def inside_chains(U, rooms, walls, openings, walls_too: bool, P,
                  label_mm, text_mm: float, boxes) -> list[dict]:
    """The plan's inside dimensions (C1): [{"axis" h|v|wall, "a", "b",
    "ref", "run", "out" (on the page), "off"}].

    Each room both ways — its clear width and length (the longest, if
    the room is not a rectangle), on a chain across the building at a
    place whose numbers fall clear of the labels, tags and the other
    chains (``boxes``, on the page); a chain takes every room it crosses
    whole, so rooms in a row share one. ``walls_too``: the chain carries
    the walls' thicknesses too, and each interior wall with openings gets
    its own chain along a face. ``label_mm(length)``: a number's width on
    the page."""
    from shapely.geometry import Point
    if U.is_empty:
        return []
    F = _filled(U)
    rooms = [r for r in rooms if r.get("poly") is not None
             and not r["poly"].is_empty] or _free_rooms(U, F)
    namer = stop_namer(walls)
    # the host's cota stands its number ~4 mm off the line (measured on
    # its screen, 14/11/2026): the line to the number's far edge
    th = text_mm * 2.6 + 0.4
    # a wall crossed, even slantwise, is no longer than this
    thick = 2 * max((float(w.get("t", 0.2)) for w in walls), default=0.3) \
        + 0.05
    taken: list[tuple] = []              # the chains' numbers so far (page)
    out: list[dict] = []

    def hits(bb, skip=()) -> float:
        """What a number would cover: texts, tags and the other numbers
        in full, a door's swing a tenth (a number on a leaf's arc still
        reads; on a room's name it does not — the baths, r_demo)."""
        area = 0.0
        pad = 0.8                        # (mm: touching is not clear)
        bb = (bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad)
        for b in list(boxes) + [t_ for t_ in taken if id(t_) not in skip]:
            wgt = 0.1 if b[0] == "swing" else 1.0
            b = b[1:] if isinstance(b[0], str) else b
            w_ = min(bb[2], b[2]) - max(bb[0], b[0])
            h_ = min(bb[3], b[3]) - max(bb[1], b[1])
            if w_ > 0 and h_ > 0:
                area += w_ * h_ * wgt
        return area

    axes = {}
    for w in walls:
        try:
            seg = W.centre(w)
            if seg.kind == "line":
                axes[str(w["id"])] = seg.u
        except Exception:  # noqa: BLE001 — a broken wall: not plain
            continue

    def plain(ref, kind, axis) -> bool:
        """A stretch that reads true wherever the chain crosses: a span
        between two straight faces, a wall's thickness taken square to
        it. Not: a curved wall crossed (its «thickness» slantwise, 0,28
        for 0,20) or a span ending on one (it changes along it) — those
        stay off unless they are the measure a room was crossed for
        (r_demo's porch, 14/11/2026)."""
        na, nb = ref.split("~", 1)
        if "@" in na or "@" in nb:
            return False
        if kind != "wall":
            return True
        wa, wb = na.split(".")[0], nb.split(".")[0]
        u = axes.get(wa)
        if wa != wb or u is None:
            return False
        return abs(u[0] if axis == "h" else u[1]) < 0.02

    def P2(axis, v, t):
        return P((t, v) if axis == "h" else (v, t))

    def label_box(axis, v, a, b):
        pa, pb = P2(axis, v, a), P2(axis, v, b)
        L_ = math.dist(pa, pb)
        tw = label_mm(b - a)
        if L_ < tw + 1.0:
            return None, True            # short: its number steps aside
        if axis == "h":
            m = (pa[0] + pb[0]) / 2
            # (to 1 mm past its line: no other line laid on it)
            return (m - tw / 2, pa[1] - th, m + tw / 2, pa[1] + 1.0), False
        m = (pa[1] + pb[1]) / 2
        return (pa[0] - th, m - tw / 2, pa[0] + 1.0, m + tw / 2), False

    for axis in ("h", "v"):
        k = abs(P2(axis, 0.0, 1.0)[0 if axis == "h" else 1]
                - P2(axis, 0.0, 0.0)[0 if axis == "h" else 1])  # mm / m
        band = th / k                    # a number's room across the line
        # each room's longest stretch this way, and where it is
        info = []
        for r in rooms:
            lo, hi = (r["poly"].bounds[1], r["poly"].bounds[3]) if axis == "h" \
                else (r["poly"].bounds[0], r["poly"].bounds[2])
            if hi - lo < 2 * 0.05 + 1e-3:
                info.append(None)
                continue
            n_ = max(8, min(60, int((hi - lo) / 0.05)))
            vs = [lo + (hi - lo) * (i + 0.5) / n_ for i in range(n_)]
            ch = [(_chord(r["poly"], axis, v), v) for v in vs]
            best = max(c for c, _ in ch)
            # the number above (h) / left of (v) the line stays in the room
            keep = [v for c, v in ch if c >= best - 0.01
                    and v - lo >= min(0.25, (hi - lo) / 4)
                    and (hi - v >= band + 0.03 if axis == "h"
                         else v - lo >= band + 0.03)]
            info.append({"best": best, "vs": keep or [v for c, v in ch
                                                     if c >= best - 0.01]})
        chains: dict = {}

        def look(v):
            key = round(v, 3)
            if key not in chains:
                runs = chain_at(U, F, rooms, axis, v)
                # a line that runs INSIDE a wall (along it, not across) is
                # no chain: its «thickness» would be the wall's length
                along = any(kind == "wall" and b - a > thick
                            for run in runs for a, b, kind in run)
                segs = []
                for run in runs:
                    for a, b, kind in run:
                        if kind == "wall" and not walls_too:
                            continue
                        bb, short = label_box(axis, v, a, b)
                        pa = (a, v) if axis == "h" else (v, a)
                        pb = (b, v) if axis == "h" else (v, b)
                        ref = f"{namer(pa, ends=False)}~" \
                              f"{namer(pb, ends=False)}"
                        segs.append({"a": a, "b": b, "kind": kind,
                                     "box": bb, "short": short, "ref": ref,
                                     "same": (ref, round(b - a, 3)),
                                     "plain": plain(ref, kind, axis)})
                chains[key] = (v, segs, not along)
            return chains[key]

        def score(v, todo, force=None):
            """({room: its stretch}, what the numbers cover) — a room
            counts when its own stretch's number is clear."""
            v, segs, ok = look(v)
            # (a chain already laid: its own numbers are not in its way)
            laid = round(v, 3) in {round(p, 3) for p in picked}
            own = {id(s["box"]) for s in segs if s["box"]} if laid else set()
            got, cover = {}, 0.0
            if not ok:
                return got, cover
            for i in todo:
                r, inf = rooms[i], info[i]
                if inf is None or _chord(r["poly"], axis, v) < inf["best"] - 0.01:
                    continue
                for j, s in enumerate(segs):
                    if s["kind"] != "space":
                        continue
                    m = (s["a"] + s["b"]) / 2
                    mid = Point((m, v) if axis == "h" else (v, m))
                    if not r["poly"].buffer(1e-3).contains(mid):
                        continue
                    hit = s["box"] and hits(s["box"], own)
                    if not hit or i == force:
                        got[i] = j
                        cover += hit or 0.0
                    break
            return got, cover

        todo = {i for i, inf in enumerate(info) if inf is not None}
        picked: list[float] = []
        covering: set = set()            # (chain, stretch) that measure a room
        forced = False
        while todo:
            best = None
            for i in sorted(todo):
                vs = info[i]["vs"]
                at = rooms[i]["at"][1] if axis == "h" else rooms[i]["at"][0]
                # places per room: the nearest each side of its label,
                # and the two ends of where it is widest
                # (and ten more along it: a small room packed with its
                # label, a tag and a door has its free band somewhere)
                cands = {vs[0], vs[-1]} | set(vs[::max(1, len(vs) // 10)])
                lower = [v for v in vs if v < at]
                upper = [v for v in vs if v > at]
                if lower:
                    cands.add(lower[-1])
                    cands.add(lower[len(lower) // 2])
                if upper:
                    cands.add(upper[0])
                    cands.add(upper[len(upper) // 2])
                if forced:
                    # (a room no chain measured clear: the chains already
                    # laid across it are tried too — their place is free)
                    cands |= set(picked)
                for v in cands:
                    if v not in picked and any(abs(v - p) < band * 1.4
                                               for p in picked):
                        continue
                    got, cover = score(v, todo, i if forced else None)
                    if i not in got:
                        continue
                    # (the rest, each on its own: what its number covers
                    # first — a door's arc before a room's name)
                    if forced:
                        s = (-round(cover, 1), len(got), -abs(v - at))
                    else:
                        s = (len(got), -cover, -abs(v - at))
                    if best is None or s > best[0]:
                        best = (s, v, got)
            if best is None:
                if forced:
                    break
                forced = True            # the rest: its own number wins
                continue
            _, v, got = best
            new_chain = v not in picked
            if new_chain:
                picked.append(v)
            todo -= set(got)
            covering |= {(round(v, 3), j) for j in got.values()}
            v, segs, _ = look(v)
            for s in segs if new_chain else []:
                if s["box"]:
                    taken.append(s["box"])
        # one measure once: the same two faces at the same distance on a
        # second chain (a wall's thickness, a room crossed again) is left
        # off — the stretch that measures a room whole goes first
        seen_: set = set()
        keep: set = set()
        for key, j in sorted(covering):
            seen_.add(chains[key][1][j]["same"])
            keep.add((key, j))
        for v in picked:
            key = round(v, 3)
            for j, s in enumerate(chains[key][1]):
                if (key, j) not in keep and s["same"] not in seen_ \
                        and s["plain"]:
                    seen_.add(s["same"])
                    keep.add((key, j))
        for v in sorted(picked):
            key = round(v, 3)
            run = f"{axis}:{v:.2f}"
            for j, s in enumerate(chains[key][1]):
                if (key, j) not in keep:
                    continue
                pa = (s["a"], v) if axis == "h" else (v, s["a"])
                pb = (s["b"], v) if axis == "h" else (v, s["b"])
                out.append({"axis": axis, "a": pa, "b": pb, "run": run,
                            "kind": s["kind"],
                            "out": (0.0, -1.0) if axis == "h" else (-1.0, 0.0),
                            "off": 0.0, "ref": s["ref"]})

    if walls_too:
        out += _opening_chains(U, F, walls, openings, namer, P, label_mm,
                               th, hits, taken)
    return unique_refs(out)


def _opening_chains(U, F, walls, openings, namer, P, label_mm, th, hits,
                    taken) -> list[dict]:
    """Along each INTERIOR wall with doors or windows, on the face whose
    numbers fall clearer: face — opening — face (the outside rows already
    measure the outer walls' openings)."""
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import unary_union
    byid = {w["id"]: w for w in walls}
    plan = {}
    try:
        plan = W.plan(walls)
    except Exception:  # noqa: BLE001 — no plan: no chains along the walls
        return []
    free = F.difference(U)
    per: dict = {}
    for o in openings:
        w = byid.get(o.get("wall"))
        gp = _gap(o, w) if w else None
        if gp is None:
            continue
        cx, cy = gp["c"]
        nx, ny = gp["n"]
        t = float(w["t"]) / 2
        inside = all(F.contains(Point(cx + nx * sg * (t + 0.05),
                                      cy + ny * sg * (t + 0.05)))
                     and not U.contains(Point(cx + nx * sg * (t + 0.05),
                                              cy + ny * sg * (t + 0.05)))
                     for sg in (1, -1))
        if inside:
            per.setdefault(w["id"], []).append(o)
    out = []
    for wid in sorted(per):
        w = byid[wid]
        try:
            seg = W.centre(w)
        except Exception:  # noqa: BLE001 — a broken wall: skipped
            continue
        (x0, y0), (ux, uy), L = seg.p0, seg.u, seg.L
        nx, ny = -uy, ux
        t = float(w["t"]) / 2
        try:
            body = unary_union([Polygon(pc["outer"], pc.get("holes") or [])
                                for pc in plan.get(wid) or []])
        except Exception:  # noqa: BLE001
            continue
        if body.is_empty:
            continue
        proj = [(px - x0) * ux + (py - y0) * uy
                for g in getattr(body, "geoms", [body])
                for px, py in g.exterior.coords]
        s_lo, s_hi = min(proj), max(proj)
        ops = sorted(per[wid], key=lambda o: float(o["pos"]))
        best = None
        for sg in (1, -1):
            c = sg * (t + 0.002)

            def Q(s, c=c):
                return (x0 + ux * s + nx * c, y0 + uy * s + ny * c)
            line = LineString([Q(s_lo - 50), Q(s_hi + 50)])
            spans = []
            for g in getattr(line.intersection(free), "geoms",
                             [line.intersection(free)]):
                if g.is_empty or g.geom_type != "LineString":
                    continue
                ss = [(px - x0) * ux + (py - y0) * uy for px, py in g.coords]
                spans.append((max(min(ss), s_lo), min(max(ss), s_hi)))
            mid = float(ops[0]["pos"])
            span = next(((a, b) for a, b in spans if a - 1e-3 <= mid <= b + 1e-3),
                        None)
            if span is None:
                continue
            e0, e1 = span
            stops = [(e0, "")]
            for o in ops:
                s0 = float(o["pos"]) - float(o["w"]) / 2
                s1 = float(o["pos"]) + float(o["w"]) / 2
                if s0 < e0 - 1e-3 or s1 > e1 + 1e-3:
                    continue
                stops += [(s0, f"o:{o['id']}:lo"), (s1, f"o:{o['id']}:hi")]
            stops.append((e1, ""))
            if len(stops) < 3:
                continue
            # the ends: named by the face they stop on
            fa = namer(Q(e0 - 0.003), ends=False)
            fb = namer(Q(e1 + 0.003), ends=False)
            stops[0] = (e0, fa if not fa.startswith("@") else f"{wid}:a")
            stops[-1] = (e1, fb if not fb.startswith("@") else f"{wid}:b")
            pn = P((nx * sg, ny * sg))
            p0_ = P((0.0, 0.0))
            ox, oy = pn[0] - p0_[0], pn[1] - p0_[1]
            on = math.hypot(ox, oy) or 1.0
            ox, oy = ox / on, oy / on
            # its line 2,5 mm off the face — or farther, 7,5 / 12,5 mm,
            # when a room's chain already stands there (two lines 0,3 mm
            # apart read as one, and their numbers overlap: the baths'
            # door on r_demo, 14/11/2026)
            kmm = math.dist(P((0.0, 0.0)), P((1.0, 0.0)))   # mm per m
            for k_, off in enumerate((2.5, 2.5 + th + 1.0,
                                      2.5 + 2 * (th + 1.0))):
                # (its numbers stay in the room: a porch 1,30 deep holds
                # no line 18 mm off at 1:100)
                far = Q((e0 + e1) / 2, sg * (t + (off + th) / kmm))
                if not free.buffer(1e-3).contains(Point(far)):
                    continue
                segs, cost = [], 0.0
                for (a, na), (b, nb) in zip(stops, stops[1:]):
                    if b - a < 0.005:
                        continue
                    pa, pb = P(Q(a, sg * t)), P(Q(b, sg * t))
                    L_ = math.dist(pa, pb)
                    tw = label_mm(b - a)
                    mx, my = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
                    # the line and its number: from 1 mm short of the line
                    # out to the number's far edge
                    half = tw / 2       # (a short one's number too)
                    ux_, uy_ = -oy, ox
                    pts = [(mx + ox * d + ux_ * e, my + oy * d + uy_ * e)
                           for d in (off - 1.0, off + th) for e in (-half, half)]
                    bb = (min(p[0] for p in pts), min(p[1] for p in pts),
                          max(p[0] for p in pts), max(p[1] for p in pts))
                    cost += hits(bb)
                    segs.append((a, b, na, nb, bb))
                # the face of the SMALLER room: a jamb told from its nearest
                # wall (the bath's 1,54, not the living room's 5,40), its
                # line nearest the wall — what is clear first
                rank = (0, e1 - e0, k_) if cost <= 2.0 else (1, cost, k_)
                if best is None or rank < best[0]:
                    best = (rank, sg, segs, (ox, oy), off, Q)
        if best is None:
            continue
        _, sg, segs, outv, off, Q = best
        for a, b, na, nb, bb in segs:
            if bb:
                taken.append(bb)
            out.append({"axis": "wall", "a": Q(a, sg * t), "b": Q(b, sg * t),
                        "run": f"wall:{wid}", "kind": "along", "out": outv,
                        "off": off, "ref": f"{wid}:{na}~{nb}"})
    return out


def inside_mode(show: dict) -> str:
    """The plan's inside dimensions: «none», «rooms», «walls» (rooms and
    walls) — the Pro's; the Lite keeps its one chain each way
    («across»). A style saved with «across» reads as «rooms» in the
    Pro."""
    from . import edition
    mode = show.get("dims_in", "walls")
    if mode == "none":
        return "none"
    if edition.lite():
        return "across"
    return "rooms" if mode == "across" else (
        mode if mode in ("rooms", "walls") else "walls")


#: the size written at each opening (C2): W × H · W · H · W over H · off
SIZE_MODES = ("wxh", "w", "h", "over", "off")


def size_mode(show: dict) -> str:
    """How the plan writes each opening's size — the Pro's (the Lite:
    «off», its schedule keeps the sizes)."""
    from . import edition
    mode = show.get("open_size", "wxh")
    if edition.lite() or mode not in SIZE_MODES:
        return "off" if edition.lite() else "wxh"
    return mode


def size_lines(o: dict, mode: str, style: dict) -> list[str]:
    """The lines written at an opening: «0,90 × 2,10» (or its width, its
    height, or the width over the height — two lines), and a window's sill
    under it («PEI 1,10»). The rough opening, as the schedule."""
    if mode == "off":
        return []
    w = DS.length(float(o["w"]), style)
    h = DS.length(float(o["h"]), style)
    out = {"wxh": [f"{w} × {h}"], "w": [w], "h": [h],
           "over": [w, h]}.get(mode, [f"{w} × {h}"])
    sill = float(o.get("sill", 0.0) or 0.0)
    if o.get("kind") == "window" and sill > 0.005:
        out.append(f"{DS.words(style).get('sill_ab', 'SILL')} "
                   f"{DS.length(sill, style)}")
    return out


def _leaves_key(o: dict) -> str:
    """A window's leaves, part of its type: 1 or 2 casement leaves, or a
    fixed middle one, are not the same window (2026-10-31) — one leaf
    hinged left or right is (the same window, turned)."""
    from . import structure as S
    # (a top light, bars, a leaf's width: another window, 04/11/2026)
    extra = "".join(f"|{k}{o[k]}" for k in ("top_h", "bars_x", "bars_z",
                                            "lw1", "lw2", "lw3", "lw4",
                                            "lw5", "lw6") if o.get(k))
    if o["kind"] != "window" or o.get("op") not in S.WIN_KINDS:
        return extra
    k = S.window_leaves(o)
    if o.get("op") == "casement" and k > 1:
        return S.casement_roles(o) + extra
    return str(k) + extra


def _shape_key(o: dict) -> str:
    """Its shape (shapes.py), part of its type: a round window is not the
    rectangular one of its size (2026-10-31) — the rectangle: nothing."""
    from . import shapes as SH
    s = SH.shape_of(o)
    if s == "rect":
        return ""
    return "|" + s + "".join(f":{round(float(o[k]), 3)}" for k in
                             ("rise", "top_w") if k in o)


def opening_types(openings: list[dict]) -> tuple[dict, list]:
    """Types of door / window: sizes within TYPE_TOL are one type.
    Returns ({opening id: tag}, [{"tag", "kind", "op", "w", "h", "sill",
    "n", "raw" (how many sizes it joins)}]) — doors first (P1…), then
    windows (J1…), each by width then height."""
    snaps = {"w": [], "h": [], "s": []}

    def snap(v, key, tol):
        for s in snaps[key]:
            if abs(s - v) <= tol:
                return s
        snaps[key].append(v)
        return v
    groups: dict = {}
    for o in openings:
        key = (o["kind"], o.get("op") or "",
               snap(round(float(o["w"]), 3), "w", TYPE_TOL[0]),
               snap(round(float(o["h"]), 3), "h", TYPE_TOL[1]),
               snap(round(float(o.get("sill", 0.0)), 3), "s", TYPE_TOL[1]),
               _leaves_key(o) + _shape_key(o))
        g = groups.setdefault(key, {"ids": [], "raw": set()})
        g["ids"].append(o["id"])
        g["raw"].add((round(float(o["w"]), 3), round(float(o["h"]), 3),
                      round(float(o.get("sill", 0.0)), 3)))
    tags, rows = {}, []
    for kind, pre in (("door", "P"), ("window", "J")):
        keys = sorted((k for k in groups if k[0] == kind),
                      key=lambda k: (k[2], k[3], k[1]))
        for i, k in enumerate(keys):
            tag = f"{pre}{i + 1}"
            for oid in groups[k]["ids"]:
                tags[oid] = tag
            rows.append({"tag": tag, "kind": kind, "op": k[1], "w": k[2],
                         "h": k[3], "sill": k[4], "n": len(groups[k]["ids"]),
                         "raw": len(groups[k]["raw"])})
    return tags, rows


# ---- paper and scale ------------------------------------------------------------------
def framing_plan(doc: dict, lid: str) -> list:
    """The FLOOR FRAMING a plan of level ``lid`` shows (4c): the joists of
    the floor above it — [("dash", a, b)] each joist's axis in plan,
    [("arrow", a, b)] along them over each zone (its span), [("text", at,
    "Joists 4×24 @ 40")] — empty: that floor is solid (or none)."""
    from shapely.geometry import Polygon
    from .docs import _s
    order = [lv["id"] for lv in doc.get("levels") or []]
    if lid not in order or order.index(lid) + 1 >= len(order):
        return []
    up = order[order.index(lid) + 1]
    out = []
    for s in doc.get("structure") or []:
        if s.get("type") != "slab" or s.get("level") != up:
            continue
        fr = S.slab_frame(s)
        if fr is None or S.why_not(s) is not None:
            continue
        cnt = S.slab_count(s)
        depth = cnt.get("depth", 0.0)
        try:
            poly = Polygon([tuple(p) for p in s["corners"]],
                           [[tuple(p) for p in h]
                            for h in s.get("holes") or []]).buffer(0)
        except Exception:  # noqa: BLE001
            continue
        for q in getattr(poly, "geoms", [poly]):
            if q.geom_type != "Polygon" or q.is_empty:
                continue
            for z in S.floor_zones(q):
                _rim, joists, _f, v, span = S.joist_layout(
                    z, fr, s.get("jdir") == "turn")
                for jq in getattr(joists, "geoms", [joists]):
                    if jq.geom_type != "Polygon" or jq.is_empty:
                        continue
                    rr = list(jq.minimum_rotated_rectangle.exterior.coords)
                    e0 = math.dist(rr[0], rr[1])
                    e1 = math.dist(rr[1], rr[2])
                    if e0 >= e1:      # its axis: between the short sides' mids
                        a = ((rr[1][0] + rr[2][0]) / 2, (rr[1][1] + rr[2][1]) / 2)
                        b = ((rr[3][0] + rr[0][0]) / 2, (rr[3][1] + rr[0][1]) / 2)
                    else:
                        a = ((rr[0][0] + rr[1][0]) / 2, (rr[0][1] + rr[1][1]) / 2)
                        b = ((rr[2][0] + rr[3][0]) / 2, (rr[2][1] + rr[3][1]) / 2)
                    out.append(("dash", a, b))
                c = z.representative_point()
                h = min(span, 3.0) / 2 * 0.8
                out.append(("arrow", (c.x - v[0] * h, c.y - v[1] * h),
                            (c.x + v[0] * h, c.y + v[1] * h)))
                if DS.imperial():
                    sizes = {"w": DS.small(fr["w"]), "d": DS.small(depth),
                             "s": DS.small(fr["s"])}
                else:
                    sizes = {"w": f"{fr['w'] * 100:.0f}",
                             "d": f"{depth * 100:.0f}",
                             "s": f"{fr['s'] * 100:g}"}
                out.append(("text", (c.x, c.y),
                            _s("Joists {w}×{d} @ {s}", **sizes)))
    return out


def layout(paper: str, style: dict) -> dict:
    """The page's parts (mm): border, side column, drawing area, title
    strip."""
    pw, ph = PAPERS_MM[paper]
    sh = style["sheet"]
    ml, m = float(sh["margin_left"]), float(sh["margin"])
    side_w = min(float(sh["side_w"]), pw * 0.3)
    side_x = pw - m - side_w
    area = (ml + GAP_MM, m + GAP_MM, side_x - GAP_MM,
            ph - m - TITLE_STRIP_MM)
    return {"page": (pw, ph), "border": (ml, m, pw - m, ph - m),
            "side": (side_x, m, pw - m, ph - m), "area": area,
            "title": (ml, ph - m - TITLE_STRIP_MM, side_x, ph - m)}


def _reserve(style: dict) -> float:
    rows = int(style["show"].get("dims_out", 3))
    mm = style["sheet"]["dim_rows_mm"]
    return (mm[min(rows, len(mm)) - 1] if rows else 0.0) + \
        DS.text(style, "dim")["mm"] + 3.0


def fits(ext_w: float, ext_h: float, paper: str, n: float,
         style: dict) -> bool:
    x0, y0, x1, y1 = layout(paper, style)["area"]
    r = 2 * _reserve(style)
    return ext_w * 1000.0 / n + r <= x1 - x0 and \
        ext_h * 1000.0 / n + r <= y1 - y0


def choose(ext_w: float, ext_h: float, style: dict, paper="auto",
           scale="auto", fits=fits) -> tuple[str, int, bool]:
    """(paper, 1:N, fits): what the architect fixed stays; the rest is the
    smallest paper / the largest drawing that holds the plan — the style's
    preferred scale (1:100) first. ``fits``: the sheet kind's own test (a
    section's room round it is not a plan's)."""
    sh = style["sheet"]
    papers = [p for p in sh["papers"] if p in PAPERS_MM]
    scales = DS.scales(style)
    if paper != "auto" and scale != "auto":
        return paper, int(scale), fits(ext_w, ext_h, paper, int(scale), style)
    if paper != "auto":
        for n in scales:
            if fits(ext_w, ext_h, paper, n, style):
                return paper, n, True
        return paper, scales[-1], False
    want = int(scale) if scale != "auto" else DS.prefer_scale(style)
    for p in papers:
        if fits(ext_w, ext_h, p, want, style):
            return p, want, True
    if scale != "auto":
        return papers[-1], want, False
    big = papers[-1]
    for n in scales:
        if n >= want and fits(ext_w, ext_h, big, n, style):
            return big, n, True
    return big, scales[-1], False


# ---- the sheet ------------------------------------------------------------------------
def _tw(text: str, mm: float) -> float:
    """A text's width on paper, roughly (Arial ≈ 0.6 of its height)."""
    return max(len(line) for line in str(text).split("\n")) * mm * 0.6


class Pieces:
    """A sheet's neutral pieces as they are laid — texts, lines, frames —
    and the boxes that must not overlap. Shared by the plan and the
    section / elevation sheets (``sectionsheet``)."""

    def __init__(self, style: dict) -> None:
        self.style = style
        self.items: list[dict] = []
        self.boxes: list[tuple] = []
        self.ink = style["colors"]["ink"]
        self.pens = style["pens"]

    def text(self, key, x, y, s, kind, align="left", color=None,
             follow=False, w=None, box=True):
        t = DS.text(self.style, kind)
        width = w or _tw(s, t["mm"]) + 1.0
        x0 = x - width / 2 if align == "center" else (
            x - width if align == "right" else x)
        it = {"kind": "text", "key": key, "x": x0, "y": y, "w": width,
              "text": s, "font": t["font"], "mm": t["mm"], "bold": t["bold"],
              "align": align, "color": color or self.ink, "follow": follow}
        self.items.append(it)
        if box:
            h = t["mm"] * 1.25 * (str(s).count("\n") + 1)
            self.boxes.append((key, x0, y, x0 + width, y + h))
        return it

    def line(self, key, a, b, pen="hair", color=None, dash=None,
             follow=False):
        self.items.append({"kind": "line", "key": key, "pts": [a, b],
                           "pen": self.pens.get(pen, pen)
                           if isinstance(pen, str) else pen,
                           "color": color or self.ink, "dash": dash,
                           "follow": follow})

    def rect(self, key, x0, y0, x1, y1, pen="hair", fill=None):
        self.items.append({"kind": "rect", "key": key, "x": x0, "y": y0,
                           "w": x1 - x0, "h": y1 - y0,
                           "pen": self.pens.get(pen, pen)
                           if isinstance(pen, str) else pen, "fill": fill,
                           "color": self.ink})


def level_text(z: float, style: dict) -> str:
    """«±0,00», «+3,20», «−3,00» — a level from the ground floor (feet /
    inches: «±0'-0"», «+10'6"», «−9'10"»)."""
    if DS.imperial():
        return DS.ZERO_IN if abs(z) < 0.005 else \
            ("+" if z > 0 else "−") + DS.length(abs(z), style)
    return "±" + DS.num(0.0, style) if abs(z) < 0.005 else \
        ("+" if z > 0 else "−") + DS.num(abs(z), style)


def title_strip(pc: Pieces, L: dict, sheet: dict, index: int, n: int,
                sub: str) -> None:
    """The drawing's title under the view (NBR: the bubble with its number
    and sheet, the title, the scale line) and the graphic scale."""
    style = pc.style
    W_ = DS.words(style)
    tx0, ty0, tx1, _ty1 = L["title"]
    bub = 9.0
    bxc, byc = tx0 + 6 + bub, ty0 + 10 + bub
    pc.items.append({"kind": "bubble", "key": "title:bubble", "x": bxc,
                     "y": byc, "r": bub, "top": f"{index:02d}",
                     "bottom": sheet["number"],
                     "font": DS.text(style, "title")["font"]})
    tt_ = DS.text(style, "title")
    pc.text("title:text", bxc + bub + 6, byc - tt_["mm"] - 1.0,
            sheet["title"].upper(), "title")
    pc.line("title:rule", (bxc + bub + 6, byc + 1.2),
            (bxc + bub + 6 + max(160.0, _tw(sheet["title"], tt_["mm"]) + 10),
             byc + 1.2), 0.5)
    pc.text("title:sub", bxc + bub + 6, byc + 3.0, sub, "subtitle")
    if style["show"].get("scalebar", True):
        pc.items.append({"kind": "scalebar", "key": "scalebar",
                         # the host's bar: 5 segments of a round length,
                         # ≈ 100 mm long — it ends clear of the side column
                         "x": tx1 - 115.0, "y": byc - 2.0, "scale": n,
                         "label": W_["graphic_scale"]})


def levels_key(pc: Pieces, doc: dict, info: dict, ground: float,
               marked: list, kx: float, y: float) -> float:
    """The building's levels as it stands (the roof on top), those in
    ``marked`` filled. Returns the y under it."""
    style = pc.style
    W_ = DS.words(style)
    pc.text("levels:head", kx, y, W_["levels"], "heading")
    ky = y + 6.0
    lv_rows = []
    for lv in reversed(doc.get("levels") or []):
        lv_rows.append((lv["id"], lv["name"], info[lv["id"]]["z0"] - ground))
    if any(s.get("type") == "roof" for s in doc.get("structure") or []):
        top = doc["levels"][-1]
        ztop = info[top["id"]]["z0"] + info[top["id"]]["height"] - ground
        lv_rows.insert(0, (None, W_.get("roof", "—"), ztop))
    for i, (l_id, name, z) in enumerate(lv_rows):
        cur = l_id in marked
        pc.rect(f"levels:row:{i}", kx, ky, kx + 30.0, ky + 4.4, 0.2,
                fill=pc.ink if cur else None)
        pc.text(f"levels:name:{i}", kx + 33.0, ky + 0.6,
                f"{name}   {level_text(z, style)}", "table")
        ky += 5.4
    return ky


def notes(pc: Pieces, sx0: float, sx1: float, y: float, cy0: float,
          lines: list) -> float:
    """The notes, when they fit above the title block."""
    W_ = DS.words(pc.style)
    if y + 6.0 + 4.6 * len(lines) < cy0 - 4.0:
        pc.text("notes:head", sx0 + 6.0, y, W_["notes"], "heading")
        y += 6.5
        for i, t in enumerate(lines):
            pc.text(f"notes:{i}", sx0 + 6.0, y, t, "note",
                    w=sx1 - sx0 - 10.0)
            y += 4.6
    return y


TITLE_BLOCK_MM = 92.0          # the title block, at the side column's foot


def title_block(pc: Pieces, doc: dict, L: dict, sheet: dict, n: int,
                index: int, total: int, today) -> None:
    """The title block at the side column's foot (``titleblock``, Pro)."""
    from . import titleblock as TB
    TB.draw(pc, doc, L, sheet, n, index, total, today)


def title_block_mm(style: dict) -> float:
    """The title block's height with this style."""
    from . import titleblock as TB
    return TB.height(style)


def digs_here(doc: dict, lid: str) -> list[dict]:
    """The excavations (dug, not fills) this level stands in — the same
    levels whose plan on screen shows them (``terrain.dig_levels``)."""
    from . import terrain as T
    return [d for d in T.opened(doc)
            if not T.is_fill(d) and lid in T.dig_levels(d, doc)]


def dashes(a, b, on: float, off: float) -> list:
    """The strokes of a dashed line from ``a`` to ``b``, in mm on paper (the
    composer's lines are solid)."""
    length = math.dist(a, b)
    if length < 1e-6:
        return []
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    out, t = [], 0.0
    while t < length:
        e = min(t + on, length)
        out.append(((a[0] + ux * t, a[1] + uy * t),
                    (a[0] + ux * e, a[1] + uy * e)))
        t = e + off
    return out


def clipped(a, b, box) -> tuple | None:
    """The part of the segment ``a``–``b`` inside ``box`` (x0, y0, x1, y1),
    or None."""
    t0, t1 = 0.0, 1.0
    dx, dy = b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - box[0]), (dx, box[2] - a[0]),
                 (-dy, a[1] - box[1]), (dy, box[3] - a[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    return ((a[0] + t0 * dx, a[1] + t0 * dy), (a[0] + t1 * dx, a[1] + t1 * dy))


def make(doc: dict, elevations, sheet: dict, style: dict,
         today: datetime.date | None = None, total: int = 1,
         index: int = 1) -> dict:
    """The plan sheet ``sheet`` (from ``sheetset``) as neutral pieces:
    {"paper", "scale", "fits", "page", "view", "items", "tags", "types",
    "rooms", "boxes"}."""
    from . import openingtools as OT
    from . import spaces
    from . import terrain as T
    Wd = DS.words(style)
    show = style["show"]
    lid = sheet["levels"][0]
    info = S.levels_info(doc, elevations)
    walls = [w for w in doc.get("walls") or [] if w.get("level") == lid]
    wall_ids = {w["id"] for w in walls}
    openings = [o for o in doc.get("openings") or [] if o.get("wall") in wall_ids]
    U = _union(walls)
    X0, Y0, X1, Y1 = U.bounds
    digs = digs_here(doc, lid)
    CX, CY = (X0 + X1) / 2, (Y0 + Y1) / 2
    paper, n, ok = choose(X1 - X0, Y1 - Y0, style,
                          sheet.get("paper", "auto") or "auto",
                          sheet.get("scale", "auto") or "auto")
    L = layout(paper, style)
    ax0, ay0, ax1, ay1 = L["area"]
    fcx, fcy = (ax0 + ax1) / 2, (ay0 + ay1) / 2
    k = 1000.0 / n
    ground = float((doc.get("project") or {}).get("ground_level", 0.0) or 0.0)
    z0 = info[lid]["z0"]
    cut = float(sheet.get("cut") or style["sheet"]["cut"])

    def P(p):
        return (fcx + (p[0] - CX) * k, fcy - (p[1] - CY) * k)
    ink, dimc = style["colors"]["ink"], style["colors"]["dim"]
    pens = style["pens"]
    pc = Pieces(style)
    items, boxes = pc.items, pc.boxes  # boxes: what must not overlap
    text, line, rect = pc.text, pc.line, pc.rect

    # --- the border and the view -------------------------------------------------
    bx0, by0, bx1, by1 = L["border"]
    rect("border", bx0, by0, bx1, by1, "border")
    view = {"x": ax0, "y": ay0, "w": ax1 - ax0, "h": ay1 - ay0, "scale": n,
            "target": [CX, CY, z0 + cut], "cut_z": z0 + cut, "level": lid}
    items.append(dict(view, kind="view", key="view"))

    # --- light-framed walls at 1:50 or closer: the studs with their X /
    # C, the insulation's zigzag — their cut's fill taken off (phase 3b)
    if n <= FR.SYMBOL_SCALE:
        plans = W.plan(walls)
        li = info[lid]
        fix = S.frame_marks(doc, lid, walls, plans)  # (T / beam studs, 4a)
        for w in walls:
            pcs = plans.get(w["id"])
            if not pcs or FR.frame_of(w) is None:
                continue
            if w["id"] in fix:
                w = dict(w, _fix=fix[w["id"]])
            b = z0 + float(w.get("base", 0.0))
            top = li["under"] if w.get("height", "level") == "level" \
                else z0 + float(w["height"])
            ops = [f for f in (S.fitted(o, w, openings, top - z0)
                               for o in openings if o["wall"] == w["id"])
                   if f is not None]
            got = FR.plan_symbols(w, pcs, ops, z0, b, top, z0 + cut)
            if not got:
                continue
            for j, poly in enumerate(got["blank"]):
                items.append({"kind": "fill", "key": f"frame:{w['id']}:b{j}",
                              "poly": [P(p) for p in poly],
                              "color": "#ffffff", "opacity": 1.0})
            for j, (a, c) in enumerate(got["lines"]):
                line(f"frame:{w['id']}:l{j}", P(a), P(c), "symbol")

    # --- grid walls (gridwall.py): their frame, glass line, mullions and
    # doors as lines — the cut's solid fill taken off (a frame cut at
    # 1.20 m, drawn with the cut pen, read as a solid wall)
    try:
        from . import gridwall as GX
        reads = [r for r in S.grid_reads(doc, elevations)
                 if r[0].get("level") == lid]
    except ImportError:                      # (the Lite: no grid walls)
        reads = []
    for w, pcs, gz0, _b, gtop, gops, gctx in reads:
        blanks, glines = GX.plan_drawing(
            w, pcs, gz0, gtop, gctx, gops,
            float(pens["cut"]) / 2 * n / 1000.0 + 0.005)
        for j, poly in enumerate(blanks):
            items.append({"kind": "fill", "key": f"gw:{w['id']}:b{j}",
                          "poly": [P(p) for p in poly],
                          "color": "#ffffff", "opacity": 1.0})
        for j, (a, c) in enumerate(glines):
            line(f"gw:{w['id']}:l{j}", P(a), P(c), "symbol")

    # --- a layered wall's layers where it is cut, with their hatches
    from . import wallsheet as WS
    if WS.drawn_at(style, n):
        WS.paint(pc, WS.plan_parts(doc, lid, walls, openings, P, z0,
                                   info[lid]["under"], z0 + cut,
                                   n <= FR.SYMBOL_SCALE))

    # --- rooms: fill, name, area, level ------------------------------------------
    rooms = spaces.of_level(doc, lid) if show.get("rooms", True) else []
    lvl_txt = level_text(z0 - ground, style)
    fills = style["room_fill"]
    for i, r in enumerate(rooms):
        rid = (r.get("rec") or {}).get("id") or f"{i}"
        use = use_of(r["name"])
        r["use"] = use
        if fills.get("on"):
            items.append({"kind": "fill", "key": f"fill:{rid}",
                          "poly": [P(p) for p in r["poly"].exterior.coords],
                          "color": fills["uses"].get(use, fills["uses"]["room"]),
                          "opacity": float(fills.get("opacity", 0.55))})
        px, py = P(r["at"])
        tr = DS.text(style, "room")
        ta = DS.text(style, "area")
        text(f"room:{rid}:name", px, py - tr["mm"] * 1.25, r["name"], "room",
             "center", follow=True)
        text(f"room:{rid}:area", px, py + 0.4,
             f"A = {DS.area(r['area'], style)}", "area", "center",
             follow=True)
        if show.get("room_level", True) and r["area"] >= 4.0:
            mx = px - _tw(r["name"], tr["mm"]) / 2 - 3.0
            my = py + ta["mm"] * 1.6 + 2.5
            items.append({"kind": "levelmark", "key": f"room:{rid}:level",
                          "x": mx, "y": my, "r": 1.6, "text": lvl_txt,
                          "mm": DS.text(style, "level")["mm"],
                          "font": DS.text(style, "level")["font"],
                          "follow": True})
            boxes.append((f"room:{rid}:level", mx - 1.6, my - 1.6,
                          mx + 2.4 + _tw(lvl_txt, ta["mm"]), my + 1.6))

    # --- room separators: a thin dashed line between rooms (separators.py) ------
    for sp in doc.get("separators") or []:
        if sp.get("level") != lid:
            continue
        for j, (a, b) in enumerate(zip(sp["pts"], sp["pts"][1:])):
            for i, (s0, s1) in enumerate(dashes(P(a), P(b), 2.0, 1.0)):
                line(f"sep:{sp['id']}:{j}:{i}", s0, s1, "symbol", follow=True)

    # --- the excavations this level stands in: their limit, dashed (below or
    # beyond the cut). Not the terrain's faces: the sheet hides that layer.
    # The walls keep setting the sheet's scale and place (a finished sheet,
    # updated, stays where it was): what passes the drawing's area is cut
    for d in digs:
        ring = d["corners"] + d["corners"][:1]
        for j, (a, b) in enumerate(zip(ring, ring[1:])):
            for i, (s0, s1) in enumerate(dashes(P(a), P(b), 4.0, 1.5)):
                kept = clipped(s0, s1, L["area"])
                if kept:
                    line(f"dig:{d['id']}:{j}:{i}", *kept, "symbol", follow=True)

    # --- the FLOOR FRAMING over it, at 1:50 or closer (PLANO_ESTRUTURA_LEVE_
    # FASE4 4c): the joists of the floor above, dashed (over the cut, as
    # anything above), one line each on its axis, and per zone the joists'
    # size and spacing on an arrow along them — the plan a builder frames
    # the floor from
    if n <= FR.SYMBOL_SCALE:
        try:
            for k, (key, a, b) in enumerate(framing_plan(doc, lid)):
                if key == "dash":
                    pa, pb = P(a), P(b)
                    L_ = math.dist(pa, pb)
                    if L_ < 1e-6:
                        continue
                    ux, uy = (pb[0] - pa[0]) / L_, (pb[1] - pa[1]) / L_
                    t, i = 0.0, 0
                    while t < L_:          # 3 mm strokes, 1.5 mm apart
                        e = min(t + 3.0, L_)
                        line(f"joist:{k}:{i}",
                             (pa[0] + ux * t, pa[1] + uy * t),
                             (pa[0] + ux * e, pa[1] + uy * e), "symbol",
                             follow=True)
                        t, i = e + 1.5, i + 1
                elif key == "arrow":
                    pa, pb = P(a), P(b)
                    line(f"jarrow:{k}", pa, pb, "symbol", follow=True)
                    L_ = math.dist(pa, pb) or 1.0
                    ux, uy = (pb[0] - pa[0]) / L_, (pb[1] - pa[1]) / L_
                    for tip, sg in ((pa, 1.0), (pb, -1.0)):
                        for side in (1.0, -1.0):
                            line(f"jarrow:{k}:{sg}:{side}", tip,
                                 (tip[0] + sg * ux * 2.0 - side * uy * 0.8,
                                  tip[1] + sg * uy * 2.0 + side * ux * 0.8),
                                 "symbol", follow=True)
                elif key == "text":
                    px, py = P(a)
                    text(f"jtext:{k}", px, py + 0.6, b, "area", "center",
                         follow=True)
        except Exception:  # noqa: BLE001 — the plan without it
            pass

    # --- doors' leaves and swings (the cut draws the jambs) ----------------------
    byid = {w["id"]: w for w in walls}
    for o in openings:
        w = byid[o["wall"]]
        swings = o["kind"] == "door" or (o["kind"] == "window"
                                         and o.get("op") == "casement")
        if not swings or w.get("kind", "line") != "line":
            continue
        try:
            segs = OT.symbol_lines(o, w, W.centre(w))[2:]
        except Exception:  # noqa: BLE001 — an opening not drawable: skip
            continue
        for j, (a, b) in enumerate(segs):
            line(f"sym:{o['id']}:{j}", P(a), P(b), "symbol", follow=True)

    # --- door / window tags -------------------------------------------------------
    # with each opening's size by it (C2, the Pro's): «0,90 × 2,10», a
    # window's sill under it — the tag goes where the two fit together:
    # never on a text, a tag or a cut wall (the walls are not in ``boxes``)
    tags, types = opening_types(openings)
    from shapely.geometry import Point
    from shapely.geometry import box as sbox
    tt = DS.text(style, "tag")
    tw_, th_ = tt["mm"] * 3.4, tt["mm"] * 2.2
    room_polys = [r["poly"] for r in rooms]
    smode = size_mode(show)
    td = DS.text(style, "dim")
    lh = td["mm"] * 1.25

    def size_block(o):
        """(lines, width, height, the stroke's gap) on paper, or None."""
        lines_ = size_lines(o, smode, style)
        if not lines_:
            return None
        gap = 0.6 if smode == "over" else 0.0   # W over a stroke over H
        return (lines_, max(_tw(t, td["mm"]) for t in lines_) + 1.0,
                lh * len(lines_) + gap, gap)

    def spots(tb, bw, bh, wide=False):
        """Where a size block may go by a tag: under, over, right, left —
        and ``wide``: the nearest places round it too."""
        cx_t, cy_t = (tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2
        out = [(cx_t - bw / 2, tb[3] + 0.4), (cx_t - bw / 2, tb[1] - 0.4 - bh),
               (tb[2] + 0.8, cy_t - bh / 2), (tb[0] - 0.8 - bw, cy_t - bh / 2)]
        if wide:
            more = []
            reach = int(3.0 * bw // 1.5)
            for gi in range(-reach, reach + 1):
                for gj in range(-8, 9):
                    sx = cx_t - bw / 2 + gi * 1.5
                    sy = cy_t - bh / 2 + gj * lh * 0.5
                    if not _hit((sx, sy, sx + bw, sy + bh), tb):
                        more.append((sx, sy))
            out += sorted(more, key=lambda q: math.hypot(
                q[0] + bw / 2 - cx_t, (q[1] + bh / 2 - cy_t) * 1.3))
        return out

    filled = []                     # the building's outline, made once

    def free(bb, also=(), inside=True):
        """A size block's place: on no text or tag, no cut wall — and by a
        tag in a room, inside the building (outside: the dimension rows)."""
        if any(_hit(bb, b[1:]) for b in boxes):
            return False
        if any(_hit(bb, b) for b in also):
            return False
        mb = sbox(*_model_box(bb, CX, CY, fcx, fcy, k))
        if U.intersects(mb):
            return False
        if inside:
            if not filled:
                filled.append(_filled(U))
            return filled[0].contains(mb)
        return True

    if show.get("tags", True):
        for o in openings:
            if o["id"] not in tags:     # a void: no door / window type
                continue
            gp = _gap(o, byid[o["wall"]])
            if gp is None:
                continue
            cx_, cy_ = gp["c"]
            nx, ny = gp["n"]
            ux, uy = gp["u"]
            sb = size_block(o) if smode != "off" else None
            placed = size_at = None
            cands = []
            for d in TAG_OFF:
                for sgn in (1, -1):
                    for lat in (0.0, 0.7, -0.7):
                        q = (cx_ + nx * d * sgn + ux * lat,
                             cy_ + ny * d * sgn + uy * lat)
                        inroom = any(pl.contains(Point(q)) for pl in room_polys)
                        if U.contains(Point(q)):
                            continue
                        cands.append((0 if inroom else 1, d, abs(lat), q))
            cands.sort(key=lambda c: c[:3])

            def tag_box(q):
                px, py = P(q)
                return px, py, (px - tw_ / 2, py - th_ / 2,
                                px + tw_ / 2, py + th_ / 2)
            # in a room before outside; there, the tag with its size
            # before the tag alone (its size then the nearest free place)
            for side in (0, 1):
                here = [c for c in cands if c[0] == side]
                for _, _, _, q in (here if sb is not None else ()):
                    px, py, bb = tag_box(q)
                    if any(_hit(bb, b[1:]) for b in boxes):
                        continue
                    for sx, sy in spots(bb, sb[1], sb[2]):
                        if free((sx, sy, sx + sb[1], sy + sb[2]), (bb,),
                                inside=side == 0):
                            placed, size_at = (px, py, bb), (sx, sy)
                            break
                    if placed:
                        break
                if placed is None:
                    for _, _, _, q in here:
                        px, py, bb = tag_box(q)
                        if not any(_hit(bb, b[1:]) for b in boxes):
                            placed = (px, py, bb)
                            break
                if placed is not None:
                    break
            if placed is None and cands:
                placed, side = tag_box(cands[0][3]), cands[0][0]
            if placed is None:
                continue
            px, py, bb = placed
            items.append({"kind": "tag", "key": f"tag:{o['id']}",
                          "x": px, "y": py, "w": tw_, "h": th_,
                          "text": tags[o["id"]],
                          "shape": "rect" if o["kind"] == "door" else "ellipse",
                          "mm": tt["mm"], "font": tt["font"], "bold": True,
                          "follow": True})
            boxes.append((f"tag:{o['id']}",) + bb)
            if sb is None:
                continue
            lines_, bw, bh, gap = sb
            if size_at is None:         # no room for both: the nearest
                sp = spots(bb, bw, bh, wide=True)
                size_at = next((q for q in sp if free(
                    (q[0], q[1], q[0] + bw, q[1] + bh), inside=side == 0)),
                    sp[0])
            x0, y0 = size_at
            skey = f"osize:{o['id']}"
            y = y0
            for j, t in enumerate(lines_):
                text(f"{skey}:{j}" if j else skey, x0 + bw / 2, y, t, "dim",
                     "center", color=style["colors"]["dim"], follow=True,
                     box=False)
                y += lh
                if gap and j == 0:
                    ww = _tw(lines_[0], td["mm"]) * 0.9
                    line(f"{skey}:bar", (x0 + bw / 2 - ww / 2, y + 0.1),
                         (x0 + bw / 2 + ww / 2, y + 0.1), "dim",
                         color=style["colors"]["dim"], follow=True)
                    y += gap
            boxes.append((skey, x0, y0, x0 + bw, y0 + bh))

    # --- dimensions ---------------------------------------------------------------
    rows_mm = style["sheet"]["dim_rows_mm"]
    outward = {"S": (0.0, 1.0), "N": (0.0, -1.0), "W": (-1.0, 0.0),
               "E": (1.0, 0.0)}             # on the PAGE (y down)
    dmm = DS.text(style, "dim")["mm"]
    counter: dict = {}
    for dd in outside_dims(walls, openings, U,
                           int(show.get("dims_out", 3))):
        s, row = dd["side"], dd["row"]
        i = counter[(s, row)] = counter.get((s, row), -1) + 1
        pa, pb = P(dd["a"]), P(dd["b"])
        L_ = math.dist(pa, pb)
        label = DS.length(math.dist(dd["a"], dd["b"]), style)
        # its key: what it measures (C0); «alias»: the key by its place in
        # the row the sheets made before 14/11/2026 gave it — read once,
        # so what he did to those sheets is not lost on their next update
        items.append({"kind": "dim", "key": f"dim:{s}:{row}:{dd['ref']}",
                      "alias": f"dim:{s}:{row}:{i}", "run": f"dim:{s}:{row}",
                      "a": [dd["a"][0], dd["a"][1], z0 + cut],
                      "b": [dd["b"][0], dd["b"][1], z0 + cut],
                      "pa": pa, "pb": pb, "off": rows_mm[row - 1],
                      "out": outward[s], "mm": dmm,
                      "short": L_ < _tw(label, dmm) + 1.0,
                      "color": dimc, "pen": pens["dim"]})
    mode = inside_mode(show)
    if mode in ("rooms", "walls"):
        def lab_mm(length):
            return _tw(DS.length(length, style), dmm)
        # the doors' swings too: a number on a leaf's arc reads badly
        swings: dict = {}
        for it in items:
            if it["kind"] == "line" and it["key"].startswith("sym:"):
                oid = it["key"].split(":")[1]
                xs = [q[0] for q in it["pts"]] + swings.get(oid, [[], []])[0]
                ys = [q[1] for q in it["pts"]] + swings.get(oid, [[], []])[1]
                swings[oid] = [xs, ys]
        avoid = list(boxes) + [("swing", min(xs), min(ys), max(xs), max(ys))
                               for xs, ys in swings.values()]
        for dd in inside_chains(U, rooms, walls, openings, mode == "walls",
                                P, lab_mm, dmm, avoid):
            pa, pb = P(dd["a"]), P(dd["b"])
            label = DS.length(math.dist(dd["a"], dd["b"]), style)
            key = (f"dim:wo:{dd['ref']}" if dd["axis"] == "wall"
                   else f"dim:in:{dd['axis']}:{dd['ref']}")
            # (no «alias»: the one inside chain of the sheets made before
            # is not these — an edit read by its place would land on
            # another dimension, the very defect C0 took away)
            items.append({"kind": "dim", "key": key, "run": f"dim:{dd['run']}",
                          "a": [dd["a"][0], dd["a"][1], z0 + cut],
                          "b": [dd["b"][0], dd["b"][1], z0 + cut],
                          "pa": pa, "pb": pb, "off": dd["off"],
                          "out": dd["out"], "mm": dmm,
                          "short": math.dist(pa, pb) < _tw(label, dmm) + 1.0,
                          "color": dimc, "pen": pens["dim"]})
    elif mode == "across":
        for i, dd in enumerate(inside_dims(U, rooms, walls)):
            pa, pb = P(dd["a"]), P(dd["b"])
            label = DS.length(math.dist(dd["a"], dd["b"]), style)
            items.append({"kind": "dim",
                          "key": f"dim:in:{dd['axis']}:{dd['ref']}",
                          "alias": f"dim:in:{dd['axis']}:{i}",
                          "run": f"dim:in:{dd['axis']}",
                          "a": [dd["a"][0], dd["a"][1], z0 + cut],
                          "b": [dd["b"][0], dd["b"][1], z0 + cut],
                          "pa": pa, "pb": pb, "off": 0.0,
                          "out": (0.0, -1.0) if dd["axis"] == "h"
                          else (-1.0, 0.0), "mm": dmm,
                          "short": math.dist(pa, pb) < _tw(label, dmm) + 1.0,
                          "color": dimc, "pen": pens["dim"]})

    # --- the drawing's title and the scale bar ------------------------------------
    W_ = DS.words(style)
    net = sum(r["area"] for r in rooms)
    sub = f"{W_['scale']} {DS.scale_text(n)}   ·   {W_['level']} {lvl_txt}"
    if rooms:
        sub += f"   ·   {W_['net']} {DS.area(net, style)}"
    title_strip(pc, L, sheet, index, n, sub)

    # --- the side column ----------------------------------------------------------
    sx0, sy0, sx1, sy1 = L["side"]
    rect("side:frame", sx0, sy0, sx1, sy1, 0.5)
    y = sy0 + 6.0
    if show.get("north", True):
        north = float((doc.get("project") or {}).get("north_deg", 0.0) or 0.0)
        items.append({"kind": "north", "key": "north", "x": sx0 + 8.0,
                      "y": y, "size": 26.0, "angle": north})
    if show.get("levels_key", True):
        ky = levels_key(pc, doc, info, ground, sheet["levels"], sx0 + 58.0, y)
        y = max(y + 34.0, ky + 4.0)
    if show.get("legend", True):
        text("legend:head", sx0 + 6.0, y, W_["legend"], "heading")
        y += 6.5
        rect("legend:wall", sx0 + 6.0, y, sx0 + 14.0, y + 4.0, 0.2,
             fill=style["colors"]["cut_fill"])
        text("legend:wall:t", sx0 + 17.0, y + 0.4, W_["cut_wall"], "table")
        y += 6.0
        if fills.get("on"):
            for use in sorted({r["use"] for r in rooms}):
                rect(f"legend:{use}", sx0 + 6.0, y, sx0 + 14.0, y + 4.0, 0.2,
                     fill=fills["uses"].get(use))
                text(f"legend:{use}:t", sx0 + 17.0, y + 0.4,
                     W_["uses"].get(use, use), "table")
                y += 6.0
        for i, z in enumerate(sorted({round(min(T.dig_bottoms(d, doc)), 3)
                                      for d in digs})):
            for j, (s0, s1) in enumerate(dashes((sx0 + 6.0, y + 2.0),
                                                (sx0 + 14.0, y + 2.0),
                                                2.4, 0.4)):
                line(f"legend:dig:{i}:{j}", s0, s1, "symbol")
            text(f"legend:dig:{i}:t", sx0 + 17.0, y + 0.4,
                 f"{W_['excavation']} {level_text(z - ground, style)}", "table")
            y += 6.0
        y += 3.0
        y = WS.legend(pc, doc, sheet["levels"], sx0 + 6.0, y,
                      sx1 - sx0 - 12.0)
    cy0 = sy1 - title_block_mm(style)
    if show.get("schedule", True) and types:
        text("sched:head", sx0 + 6.0, y, W_["schedule"], "heading")
        y += 7.0
        cols = (6.0, 20.0, 56.0, 80.0, 94.0)
        for c, h in zip(cols, ("type", "size", "sill", "qty", "desc")):
            text(f"sched:th:{h}", sx0 + c, y, W_[h], "label",
                 color=style["colors"]["mute"])
        y += 5.2
        room_for = int(max(0, (cy0 - 40.0 - y) // 4.6))
        for i, t in enumerate(types[:room_for]):
            desc = (W_["door"] if t["kind"] == "door" else W_["window"]) + \
                (" " + W_.get("ops", {}).get(t["op"], t["op"])
                 if t["op"] else "")
            vals = (t["tag"], f"{DS.length(t['w'], style)} × "
                    f"{DS.length(t['h'], style)}",
                    DS.length(t["sill"], style) if t["sill"] > 0.005 else "—",
                    str(t["n"]), desc)
            for c, v, h in zip(cols, vals, ("type", "size", "sill", "qty",
                                            "desc")):
                text(f"sched:{t['tag']}:{h}", sx0 + c, y, v, "table")
            y += 4.6
        if len(types) > room_for:
            text("sched:more", sx0 + 6.0, y, f"… +{len(types) - room_for}",
                 "table")
            y += 4.6
        y += 4.0
    if show.get("notes", True):
        notes(pc, sx0, sx1, y, cy0, style.get("notes") or W_["notes_default"])
    title_block(pc, doc, L, sheet, n, index, total, today)
    # the points his own dimensions may be tied to (C4), on the page
    cols = [c for c in doc.get("structure") or []
            if c.get("type") == "column" and c.get("level") == lid]
    anchors = {"p": {nm: [round(v, 3) for v in P(p)] for nm, p in
                     known_points(walls, openings, cols).items()},
               "l": {}, "scale": n}

    return {"paper": paper, "scale": n, "fits": ok, "page": L["page"],
            "layout": L, "view": view, "items": items, "tags": tags,
            "types": types, "rooms": rooms, "boxes": boxes,
            "level_text": lvl_txt, "anchors": anchors,
            "extent": (*P((X0, Y1)), *P((X1, Y0)))}


def known_points(walls: list[dict], openings: list[dict],
                 columns: list[dict]) -> dict:
    """The plan's points a dimension of his may stand on (C4), by what they
    are: {name: (x, y)} in the model — each wall face's two ends
    («<wall>.L.a»), the corners along it where another wall meets it
    («<wall>.R@3.20», by its place on the face), each opening's jambs on
    both faces («o:<id>:lo.L»), each column's axis («col:<id>»)."""
    out: dict = {}
    try:
        plan = W.plan(walls)
    except Exception:  # noqa: BLE001 — no plan: no wall corner known
        plan = {}
    byid = {w["id"]: w for w in walls}
    for w in walls:
        if w.get("kind", "line") != "line":
            continue
        try:
            seg = W.centre(w)
        except Exception:  # noqa: BLE001 — a broken wall: nothing on it
            continue
        (x0, y0), (ux, uy) = seg.p0, seg.u
        faces: dict = {"L": [], "R": []}
        for pc in plan.get(w["id"]) or []:
            for ring in [pc["outer"]] + list(pc.get("holes") or []):
                for p in ring:
                    dx, dy = p[0] - x0, p[1] - y0
                    across = ux * dy - uy * dx
                    if abs(abs(across) - float(w["t"]) / 2) > 0.02:
                        continue              # not on a face (a mitre's tip)
                    faces["L" if across > 0 else "R"].append(
                        (dx * ux + dy * uy, (p[0], p[1])))
        for f, pts in faces.items():
            if not pts:
                continue
            pts.sort()
            out[f"{w['id']}.{f}.a"] = pts[0][1]
            out[f"{w['id']}.{f}.b"] = pts[-1][1]
            for s, p in pts[1:-1]:
                out.setdefault(f"{w['id']}.{f}@{s:.2f}", p)
    for o in openings:
        w = byid.get(o.get("wall"))
        gp = _gap(o, w) if w is not None else None
        if gp is None:
            continue
        # (``_gap``: s0 −t, s1 −t, s1 +t, s0 +t — −t the right face)
        for p, nm in zip(gp["pts"], ("lo.R", "hi.R", "hi.L", "lo.L")):
            out[f"o:{o['id']}:{nm}"] = tuple(p)
    for c in columns:
        if c.get("x") is not None and c.get("y") is not None:
            out[f"col:{c.get('id')}"] = (float(c["x"]), float(c["y"]))
    return out


def _model_box(bb, CX, CY, fcx, fcy, k) -> tuple:
    """A box on the page (y down) back in the model (y up), as
    (x0, y0, x1, y1) — the inverse of ``make``'s ``P``."""
    xa, xb = CX + (bb[0] - fcx) / k, CX + (bb[2] - fcx) / k
    ya, yb = CY - (bb[1] - fcy) / k, CY - (bb[3] - fcy) / k
    return (min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb))


def _hit(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def overlaps(built: dict) -> list[tuple[str, str]]:
    """Pairs of texts / tags on the sheet that overlap (the check)."""
    bx = built["boxes"]
    out = []
    for i in range(len(bx)):
        for j in range(i + 1, len(bx)):
            if _hit(bx[i][1:], bx[j][1:]):
                out.append((bx[i][0], bx[j][0]))
    return out
