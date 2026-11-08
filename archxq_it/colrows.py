# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A ROW OF COLUMNS drawn as a PATH, kept as a GROUP (PLANO_LINHA_COLUNAS.md
A + B, his go 07/11/2026). Pure (no Qt).

The options bar's «Row» goes point by point, like a wall: each click fixes a
stretch and its columns are there at once — one column on each corner, never
two; a click on the first point closes it (no column twice at the start).
The path is ONE record in ``doc["colrows"]``:

    id, name «Column row N», level
    path      the points clicked, [[x, y], …] (on the plan, as clicked)
    closed    a loop (the first point clicked again)
    opts      the column options of the bar (ui.col_opts' keys): section,
              w, d, angle, anchor, height («level» | «custom») + h, base,
              cbase, ccap, fit («fit» | «free»), by (count | spacing),
              count, spacing, ends (both | first | last | none)
    omit      the stations left out: a column of the row deleted (or moved
              by hand) stays out at the next edit of the row
    n, sig    how many stations it had, and its layout then — «omit» holds
              only while the layout (path, count / spacing, ends) is the same

Its columns stay ORDINARY column records (``type`` «column»), with ``row``
(the row's id) and ``st`` (its station) more: everything that reads columns —
footings under the columns / the rows, sheets, IFC, quantities, the AI — reads
them as ever. An old row (loose columns, before 0.21.0) stays loose.

Editing a row's column (its window, the options bar, the AI) changes the ROW:
``settle`` takes the change from the column into the row, and every column of
it is made again (else the row's next edit would undo it).
"""
from __future__ import annotations

import copy
import json
import math

#: the column options a row keeps (ui.col_opts' keys)
OPT_KEYS = ("section", "w", "d", "angle", "anchor", "height", "h", "base",
            "cbase", "ccap", "fit", "by", "count", "spacing", "ends",
            "align", "beams", "foots")
DEFAULT_OPTS = {"section": "rect", "w": 0.30, "d": 0.30, "angle": 0.0,
                "anchor": "centre", "height": "level", "h": 3.0, "base": 0.0,
                "cbase": None, "ccap": None, "fit": "fit", "by": "count",
                "count": 4, "spacing": 5.0, "ends": "both", "align": "auto",
                # the row's BEAMS (PLANO_LINHA_COLUNAS C, his OK 08/11/2026):
                # w None = the columns' size across the row (faces flush)
                "beams": {"top": {"on": False, "w": None, "h": 0.50},
                          "foot": {"on": False, "w": None, "h": 0.40},
                          "mid": {"on": False, "w": None, "h": 0.30}},
                # its FOOTINGS (PLANO_LINHA_COLUNAS D, his OK 07/11/2026):
                # pads (one under each column / on each station), a strip
                # along the path, or both (the strip cut at the pads' faces)
                # (pd: the pads' own depth with a strip — deeper than it,
                # his OK 07/11/2026: same depth read as a chain of blocks)
                "foots": {"type": "none", "pw": 1.20, "sw": 0.60,
                          "d": 0.50, "pd": 0.80}}
#: a row's footings: none / pads / a strip / pads + strip
FOOT_TYPES = ("none", "pads", "strip", "both")
#: the footings' parts (a footing record's ``part``)
FOOT_PARTS = ("pad", "strip")
#: what a row is of: COLUMNS (its footings and beams following them) or
#: FOOTINGS only (the footings' «Along a path» — a timber house's pads, with
#: no column over them)
WHATS = ("columns", "footings")
#: the row's beams: on top (under the slab above, as every beam), at the
#: columns' FOOT (a grade beam: its top where they start, under the floor —
#: the excavation's floor when they go down to it), in the MIDDLE (centred
#: at half the columns' height)
BEAM_PARTS = ("top", "foot", "mid")
#: a row's LAYOUT: what changes where its stations are
LAYOUT_KEYS = ("by", "count", "spacing", "ends", "align")
#: a column's keys that, changed on one column of a row, go to the row
#: (column key → the row's option)
SETTLE_KEYS = ("shape", "w", "d", "height", "base", "cbase", "ccap")


# ---- the stations ---------------------------------------------------------------------
def row_stations(length: float, o: dict) -> list[float]:
    """Where a stretch's columns stand, as fractions of its line: by COUNT
    (evenly) or by SPACING (from its first point), with its ends in or out
    (``ends``: both | first | last | none)."""
    ends = o.get("ends", "both")
    first, last = ends in ("both", "first"), ends in ("both", "last")
    if length < 1e-9:
        return [0.0]
    if o.get("by", "count") == "spacing":
        s = max(0.05, float(o.get("spacing", 5.0)))
        k = int(math.floor(length / s + 1e-6))
        ts = [i * s / length for i in range(k + 1)]
        if ts and abs(ts[-1] - 1.0) < 1e-6:
            ts[-1] = 1.0
        if not first:
            ts = [t for t in ts if t > 1e-9]
        if last and (not ts or ts[-1] < 1.0 - 1e-6):
            ts.append(1.0)
        if not last:
            ts = [t for t in ts if t < 1.0 - 1e-9]
        return ts
    n = max(1, int(o.get("count", 4)))
    slots = n - 1 + (0 if first else 1) + (0 if last else 1)
    if slots <= 0:
        return [0.0 if first else 1.0]
    start = 0 if first else 1
    return [(start + k) / slots for k in range(n)]


def _foot(p, a, b, margin: float = 0.0):
    """The foot of ``p`` on the segment a-b (None: beyond its ends by more
    than ``margin`` m — a foot just past an end is pulled back onto it)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return None
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2
    m = margin / math.sqrt(L2)
    if t < -m or t > 1.0 + m:
        return None
    t = min(max(t, 0.0), 1.0)
    return [a[0] + dx * t, a[1] + dy * t]


def _inside(p, poly) -> bool:
    inside = False
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i][:2], poly[(i + 1) % n][:2]
        if (y1 > p[1]) != (y2 > p[1]):
            x = x1 + (p[1] - y1) * (x2 - x1) / (y2 - y1)
            if x > p[0]:
                inside = not inside
    return inside


def _sizes(o: dict) -> tuple:
    """(along, across): the column's size along the row and across it."""
    along = float(o["w"])
    across = along if o.get("section") == "round" else float(o["d"])
    if abs((float(o.get("angle", 0)) % 180) - 90) < 1e-6:
        along, across = across, along         # turned square to the row
    return along, across


def _pit_side(a, b, o: dict, pits):
    """The pit side a stretch lies on: (a, b laid onto the side — onto its
    corners when that near —, the inward normal, the pit) or None."""
    L = math.dist(a, b)
    if L < 1e-6 or not pits:
        return None
    _along, across = _sizes(o)
    # a click within a column's depth of the side counts as ON it (his
    # left side, 2026-10-06: both clicks ~17 cm in, the row came out
    # skewed by 0.04° and off the face) — laid back onto the side
    tol = across + 0.05
    for poly in pits:
        n = len(poly)
        for i in range(n):
            p, q = poly[i], poly[(i + 1) % n]
            fa, fb = _foot(a, p, q, tol), _foot(b, p, q, tol)
            if fa is None or fb is None or math.dist(a, fa) > tol \
                    or math.dist(b, fb) > tol or math.dist(fa, fb) < 1e-6:
                continue
            a2 = next((list(c) for c in (p, q) if math.dist(fa, c) <= tol),
                      fa)
            b2 = next((list(c) for c in (p, q) if math.dist(fb, c) <= tol),
                      fb)
            L = math.dist(a2, b2)
            if L < 1e-6:
                continue
            u = ((b2[0] - a2[0]) / L, (b2[1] - a2[1]) / L)
            nx, ny = -u[1], u[0]
            m = ((a2[0] + b2[0]) / 2, (a2[1] + b2[1]) / 2)
            if not _inside((m[0] + nx * 0.01, m[1] + ny * 0.01), poly):
                nx, ny = -nx, -ny
            return a2, b2, (nx, ny), poly
    return None


def pit_inset(a, b, o: dict, pits) -> tuple:
    """(a, b) moved inside the pit whose side both lie on: the row's line
    half a column in from the side, its ends half a column in from the
    corners clicked. Not on one side of a pit: as clicked."""
    hit = _pit_side(a, b, o, pits)
    if hit is None:
        return a, b
    a2, b2, (nx, ny), poly = hit
    along, across = _sizes(o)
    L = math.dist(a2, b2)
    u = ((b2[0] - a2[0]) / L, (b2[1] - a2[1]) / L)
    h = across / 2
    ka = along / 2 if any(math.dist(a2, c) < 0.02 for c in poly) else 0.0
    kb = along / 2 if any(math.dist(b2, c) < 0.02 for c in poly) else 0.0
    return ([a2[0] + nx * h + u[0] * ka, a2[1] + ny * h + u[1] * ka],
            [b2[0] + nx * h - u[0] * kb, b2[1] + ny * h - u[1] * kb])


#: how a row stands on its line (his ask, 08/11/2026 — the window): its
#: columns' faces flush inside, centred on it, or flush outside. «auto»
#: (a row just drawn): inside along an excavation's sides, else centred
ALIGNS = ("inside", "centre", "outside")


def _turn(pts, closed: bool) -> float:
    """+1: the path's inside is on its LEFT (it turns that way — a closed
    one anticlockwise); −1: on its right. A straight one: left."""
    n = len(pts)
    a2 = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0]
             * pts[i][1] for i in range(n))
    return -1.0 if a2 < -1e-9 else 1.0


def _cross(l1, l2):
    """Where the lines through l1 = (a, b) and l2 cross (None: parallel)."""
    (a, b), (c, d) = l1, l2
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-9 * max(1.0, math.hypot(*r) * math.hypot(*s)):
        return None
    t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / den
    return [a[0] + r[0] * t, a[1] + r[1] * t]


def align_of(path, closed: bool, o: dict, pits=()) -> str:
    """The row's alignment as its window shows it: «auto» read — inside
    when a stretch of it runs along an excavation's side, else centred."""
    al = o.get("align", "auto")
    if al in ALIGNS:
        return al
    pts = [list(p[:2]) for p in path or []]
    segs = list(zip(pts, pts[1:])) + ([(pts[-1], pts[0])] if closed
                                      and len(pts) > 2 else [])
    return "inside" if any(_pit_side(a, b, o, pits) for a, b in segs) \
        else "centre"


def _lines(pts, closed: bool, o: dict, pits) -> list:
    """Each stretch's line, where its columns' centres stand: moved by the
    row's alignment (half a column in / out; «auto» = the pit's inset)."""
    al = o.get("align", "auto")
    along, across = _sizes(o)
    side = _turn(pts, closed)
    segs = list(zip(pts, pts[1:])) + ([(pts[-1], pts[0])] if closed else [])
    out = []
    for a, b in segs:
        if al == "auto":
            out.append(pit_inset(a, b, o, pits))
            continue
        if al == "centre":
            out.append((list(a), list(b)))
            continue
        hit = _pit_side(a, b, o, pits)
        if hit is None and o.get("pit_only"):  # a footing row, off a pit
            out.append((list(a), list(b)))
            continue
        if hit is not None and al == "inside":
            out.append(pit_inset(a, b, o, pits))
            continue
        L = math.dist(a, b)
        if L < 1e-9:
            out.append((list(a), list(b)))
            continue
        if hit is not None:                   # outside the pit: its back
            a, b, (nx, ny), _poly = hit
        else:
            ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            nx, ny = -uy * side, ux * side    # the path's inside
        if al == "outside":
            nx, ny = -nx, -ny
        h = across / 2
        out.append(([a[0] + nx * h, a[1] + ny * h],
                    [b[0] + nx * h, b[1] + ny * h]))
    return out


def _even(length: float, o: dict) -> list[float]:
    """By spacing: the stretch in EQUAL bays, none longer than the spacing
    (his test, 08/11/2026: «from the first point» left a 29 cm bay before
    the corner — two columns side by side)."""
    s = max(0.05, float(o.get("spacing", 5.0)))
    n = max(1, int(math.ceil(length / s - 1e-6)))
    return [i / n for i in range(n + 1)]


def stretches(path, closed: bool, o: dict, pits=()) -> tuple:
    """(closed, [[a, b]], [angle°]) — the path's stretches as the columns'
    centres run along them: moved by the alignment, meeting at the corners
    (where the lines cross). The beams of the row lie on them too."""
    pts = [list(p[:2]) for p in path or []]
    if closed and len(pts) > 2 and math.dist(pts[0], pts[-1]) < 1e-6:
        pts = pts[:-1]
    # (a point clicked twice: once)
    pts = [p for i, p in enumerate(pts) if i == 0
           or math.dist(p, pts[i - 1]) > 1e-6]
    closed = bool(closed) and len(pts) > 2
    if len(pts) < 2:
        return closed, [], []
    lines = _lines(pts, closed, o, pits)
    angs = [math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            for a, b in lines]
    # the corners: where the two stretches' lines cross
    ends = [[list(a), list(b)] for a, b in lines]
    n = len(lines)
    for i in range(n):
        j = i + 1
        if j == n:
            if not closed:
                break
            j = 0
        p = _cross(lines[i], lines[j])
        if p is None:                          # straight on: between them
            p = [(lines[i][1][0] + lines[j][0][0]) / 2,
                 (lines[i][1][1] + lines[j][0][1]) / 2]
        ends[i][1] = p
        ends[j][0] = p
    return closed, ends, angs


def stations(path, closed: bool, o: dict, pits=()) -> list[tuple]:
    """[(x, y, angle°)] — every column of a path, in order (its station
    numbers): by count = so many on EACH stretch (its two ends counted), by
    spacing = equal bays no longer than it, on each stretch. Every corner
    has ONE column, where the stretches' lines meet (flush with both sides
    of an excavation's corner, a re-entrant one too); the path's two ends
    as «ends» says; a closed path has no column twice at its start."""
    closed, ends, angs = stretches(path, closed, o, pits)
    if not ends:
        return []
    n = len(ends)
    end_rule = o.get("ends", "both")
    by_spacing = o.get("by", "count") == "spacing"
    last_i = n - 1
    out = []
    for i, (a2, b2) in enumerate(ends):
        first_in = True if (i > 0 or closed) else end_rule in ("both",
                                                                "first")
        last_in = True if (i < last_i or closed) else end_rule in ("both",
                                                                   "last")
        L = math.dist(a2, b2)
        if by_spacing:
            ts = _even(L, o)
            ts = [t for t in ts if (first_in or t > 1e-9)
                  and (last_in or t < 1.0 - 1e-9)]
        else:
            e = {(True, True): "both", (True, False): "first",
                 (False, True): "last", (False, False): "none"}[
                (first_in, last_in)]
            ts = row_stations(L, dict(o, ends=e))
        for t in ts:
            if t < 1e-9 and i > 0:
                continue          # the corner: the stretch before has it
            if t > 1.0 - 1e-9 and closed and i == last_i:
                continue          # back at the start: it has its column
            out.append((round(a2[0] + (b2[0] - a2[0]) * t, 4),
                        round(a2[1] + (b2[1] - a2[1]) * t, 4),
                        float(o.get("angle", 0.0)) + angs[i]))
    return out


# ---- the row's columns -----------------------------------------------------------------
def opts_of(o: dict) -> dict:
    """The row's options, from ui.col_opts (or a stored row's)."""
    out = copy.deepcopy(DEFAULT_OPTS)
    for k in OPT_KEYS:
        if k in (o or {}) and k not in ("beams", "foots"):
            out[k] = copy.deepcopy(o[k])
    got = (o or {}).get("beams")
    if isinstance(got, dict):
        for part in BEAM_PARTS:
            b = got.get(part)
            if isinstance(b, dict):
                out["beams"][part].update(
                    {k: b[k] for k in ("on", "w", "h") if k in b})
    f = (o or {}).get("foots")
    if isinstance(f, dict):
        out["foots"].update({k: f[k] for k in ("type", "pw", "sw", "d", "pd")
                             if k in f})
        if out["foots"]["type"] not in FOOT_TYPES:
            out["foots"]["type"] = "none"
    return out


def what_of(row: dict | None) -> str:
    """«footings»: a row of footings only; else a row of columns."""
    return "footings" if (row or {}).get("what") == "footings" \
        else "columns"


def geo(row: dict, o: dict) -> dict:
    """The options its stations are laid out with: a row of columns, its
    own; a row of FOOTINGS, a square as wide as its pads (as its strip
    when it has no pads) — inside / outside flush with their faces."""
    if what_of(row) != "footings":
        return o
    # (its own line: «auto» = centred on it, never the pit's inset)
    if o.get("align", "auto") not in ALIGNS:
        o = dict(o, align="centre")
    f = o["foots"]
    side = float(f["pw"]) if f["type"] in ("pads", "both") \
        else float(f["sw"])
    # inside / outside only along an excavation's side (against it); off
    # it, centred on the line clicked (his test, 08/11/2026: «Inside» on
    # an open path set them half a pad off the columns' line)
    return dict(o, section="rect", w=side, d=side, angle=0.0, pit_only=True)


def part_on(o: dict, part: str) -> bool:
    """A part of the row's (a beam's, a footing's) switched on."""
    if part in BEAM_PARTS:
        return bool(o["beams"][part].get("on"))
    t = o["foots"]["type"]
    return t in ("pads", "both") if part == "pad" else t in ("strip", "both")


def foot_recs(row: dict, o: dict, pits=(), span=None, cols=None,
              centre=None, skip=(), ftop=None) -> list[dict]:
    """The row's FOOTINGS: ordinary footing records (+ ``row``, ``part``
    pad | strip, ``seg``). Pads: a row of columns, one under each column
    there (``cols`` {station: column}) — centred on it (``centre(c)``),
    turned with it, never smaller than it + 0.20; a row of footings, one on
    each station. The strip: along each stretch, cut at the pads' faces
    when there are pads (never counted twice); a row of columns' open ends
    half its width past the end columns. With a grade beam at the columns'
    foot, they sit UNDER it (``zt``: their top, over the level's floor).
    ``skip``: the keys («pad:3») left out (deleted)."""
    f = o["foots"]
    typ = f["type"]
    if typ == "none":
        return []
    foots_only = what_of(row) == "footings"
    g = geo(row, o)
    depth = float(f["d"])
    # pads + strip: the pads go deeper than the strip, their own depth
    pdepth = float(f.get("pd") or depth) if typ == "both" else depth
    fb = o["beams"]["foot"]
    under_beam = not foots_only and bool(fb.get("on"))

    def top(p):
        if not under_beam:
            return None
        got = tuple(span(p)) if span is not None else ()
        foot = got[0] if got else float(o.get("base", 0.0) or 0.0)
        return round(foot - float(fb.get("h") or 0.4), 4)
    out, pads = [], []
    if typ in ("pads", "both"):
        for k, (x, y, ang) in enumerate(
                stations(row["path"], row.get("closed"), g, pits)):
            if f"pad:{k}" in skip:
                continue
            if foots_only:
                side, a = float(f["pw"]), ang
            else:
                c = (cols or {}).get(k)
                if c is None:
                    continue           # no column there: no pad
                x, y = centre(c) if centre is not None else (c["x"], c["y"])
                side = max(float(f["pw"]),
                           max(float(c["w"]), float(c.get("d", c["w"])))
                           + 0.20)
                a = float(c.get("angle", 0.0))
            r = {"type": "footing", "kind": "pad", "x": round(x, 4),
                 "y": round(y, 4), "w": round(side, 4), "d": pdepth,
                 "angle": round(a, 3), "level": row["level"],
                 "row": row["id"], "part": "pad", "seg": k}
            zt = top((x, y))
            if zt is not None:
                r["zt"] = zt
            out.append(r)
            pads.append((x, y, side))
    if typ in ("strip", "both"):
        closed, ends, _angs = stretches(row["path"], row.get("closed"), g,
                                        pits)
        sw = float(f["sw"])
        ext = 0.0 if foots_only else max(sw, _sizes(o)[0]) / 2
        n, last = 0, len(ends) - 1
        for j, (a, b) in enumerate(ends):
            L = math.dist(a, b)
            if L < 0.05:
                continue
            u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
            lo = -ext if (j == 0 and not closed) else 0.0
            hi = L + ext if (j == last and not closed) else L
            cuts = []
            if typ == "both":
                for (px, py, side) in pads:
                    dx, dy = px - a[0], py - a[1]
                    if abs(-dx * u[1] + dy * u[0]) > 0.02:
                        continue                 # not on this stretch
                    t = dx * u[0] + dy * u[1]
                    if -side / 2 - 1e-6 <= t <= L + side / 2 + 1e-6:
                        # (1 mm into the pad: never two faces in one plane)
                        cuts.append((t - side / 2 + 0.001,
                                     t + side / 2 - 0.001))
            pieces, cur = [], lo
            for c0, c1 in sorted(cuts):
                if c0 > cur:
                    pieces.append((cur, min(c0, hi)))
                cur = max(cur, c1)
            if cur < hi:
                pieces.append((cur, hi))
            for t0, t1 in pieces:
                if t1 - t0 < 0.05:
                    continue
                p0 = [round(a[0] + u[0] * t0, 4), round(a[1] + u[1] * t0, 4)]
                p1 = [round(a[0] + u[0] * t1, 4), round(a[1] + u[1] * t1, 4)]
                r = {"type": "footing", "kind": "strip", "a": p0, "b": p1,
                     "w": round(sw, 4), "d": depth, "level": row["level"],
                     "row": row["id"], "part": "strip", "seg": n}
                zt = top(((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2))
                if zt is not None:
                    r["zt"] = zt
                out.append(r)
                n += 1
    # a row of footings sits on ONE level (his test, 07/11/2026: drawn on an
    # excavation's edge, half of them were read inside it — the pit's floor
    # — and half outside, 30 cm higher): where the ground under any of them
    # is lower, all of them go down to it. ``ftop(p)``: a footing's top at
    # ``p`` as built, over the level's floor
    if foots_only and ftop is not None and out:
        pts = []
        for r in out:
            if r["kind"] == "pad":
                h = r["w"] / 2
                pts += [(r["x"], r["y"])] + [(r["x"] + sx * h, r["y"] + sy * h)
                                             for sx in (-1, 1)
                                             for sy in (-1, 1)]
            else:
                pts += [tuple(r["a"]), tuple(r["b"]),
                        ((r["a"][0] + r["b"][0]) / 2,
                         (r["a"][1] + r["b"][1]) / 2)]
        tops = [float(ftop(p)) for p in pts]
        if max(tops) - min(tops) > 1e-4:
            for r in out:
                r["zt"] = round(min(tops), 4)
    return out


def span_beams(row: dict) -> bool:
    """A beam at its foot / middle on: it follows the columns' span."""
    b = opts_of(row.get("opts"))["beams"]
    return bool(b["foot"].get("on") or b["mid"].get("on"))


def beam_width(o: dict, part: str) -> float:
    """A row beam's width: its own, else the columns' size across the row."""
    w = o["beams"][part].get("w")
    return float(w) if w else _sizes(o)[1]


def beam_recs(row: dict, o: dict, pits=(), span=None) -> list[dict]:
    """The row's beams, one per stretch and part switched on: ordinary beam
    records (+ ``row``, ``part``, ``seg``). ``span(p)`` → (foot, top) of the
    row's columns at ``p``, over the level's floor (ui: the excavation, the
    level's height); none = the base and the column's own height / 3 m."""
    if not any(o["beams"][p].get("on") for p in BEAM_PARTS):
        return []
    _closed, ends, _angs = stretches(row["path"], row.get("closed"), o, pits)
    out = []
    for part in BEAM_PARTS:
        b = o["beams"][part]
        if not b.get("on"):
            continue
        w, h = beam_width(o, part), float(b.get("h") or 0.3)
        for k, (a, c) in enumerate(ends):
            if math.dist(a, c) < 0.05:
                continue
            r = {"type": "beam", "a": [round(a[0], 4), round(a[1], 4)],
                 "b": [round(c[0], 4), round(c[1], 4)],
                 "w": round(w, 4), "h": round(h, 4), "level": row["level"],
                 "row": row["id"], "part": part, "seg": k}
            # (on top of columns of a height of their own — two floors
            # high, a porch's posts — its top at theirs, not at the slab's)
            if part == "top" and o["height"] != "level":
                r.update(zmode="own", zt=round(float(o["h"]), 4))
            elif part != "top":
                m = ((a[0] + c[0]) / 2, (a[1] + c[1]) / 2)
                got = tuple(span(m)) if span is not None else ()
                foot = got[0] if got else float(o.get("base", 0.0) or 0.0)
                top = got[1] if len(got) > 1 else (
                    float(o["h"]) if o["height"] != "level" else 3.0)
                ceil = got[2] if len(got) > 2 else top   # the level's top
                # the grade beam: its TOP where the columns start — under
                # the floor, as built (his test, 07/11/2026); the middle one
                # centred in the FREE space: between the floor and the top
                # beam's underside (his test, 08/11/2026 — centred on the
                # whole column, the gap over it was 50 cm shorter)
                free = top
                tb = o["beams"]["top"]
                if tb.get("on"):
                    free = (float(o["h"]) if o["height"] != "level"
                            else ceil) - float(tb.get("h") or 0.5)
                zt = foot if part == "foot" else (foot + free) / 2 + h / 2
                r.update(zmode="own", zt=round(zt, 4))
            out.append(r)
    return out


def column_rec(x, y, ang, o: dict) -> dict:
    """A column of the row, as ``ColumnTool._col`` + ``ui._struct_done``
    make one (before it is fitted into a wall)."""
    rnd = o["section"] == "round"
    return {"type": "column", "x": round(x, 4), "y": round(y, 4),
            "shape": o["section"], "w": o["w"],
            "d": o["w"] if rnd else o["d"],
            "angle": round(ang, 3), "anchor": o["anchor"],
            "height": "level" if o["height"] == "level" else float(o["h"]),
            "base": float(o.get("base", 0.0) or 0.0),
            "cbase": o.get("cbase"), "ccap": o.get("ccap")}


def sig(row: dict) -> str:
    """The row's layout: the stations stay the same while it does."""
    o = row.get("opts") or {}
    return json.dumps({"path": row.get("path"),
                       "closed": bool(row.get("closed")),
                       **{k: o.get(k) for k in LAYOUT_KEYS}}, sort_keys=True)


def _prim(row: dict) -> str:
    """The element type a row is made of (its «members»)."""
    return "footing" if what_of(row) == "footings" else "column"


def members(doc: dict, row: dict) -> list[dict]:
    """The row's own elements now (its level's, with its id): a row of
    columns, its columns; a row of footings, its footings."""
    t = _prim(row)
    return [e for e in doc.get("structure") or []
            if e.get("type") == t and e.get("row") == row["id"]
            and e.get("level") == row["level"]]


def prune(doc: dict) -> dict:
    """A row with nothing of its own left (all deleted, Backspace back to
    its first point): it goes, and its beams and footings with it — never
    left behind to be deleted one by one (his test, 07/11/2026)."""
    rows = doc.get("colrows") or []
    if not rows:
        return doc
    prim = {r["id"]: _prim(r) for r in rows}
    alive = {e.get("row") for e in doc.get("structure") or []
             if e.get("row") and prim.get(e.get("row")) == e.get("type")}
    dead = {r["id"] for r in rows if r["id"] not in alive}
    if not dead:
        return doc
    return dict(doc, colrows=[r for r in rows if r["id"] not in dead],
                structure=[e for e in doc.get("structure") or []
                           if not (e.get("type") in ("beam", "footing")
                                   and e.get("row") in dead)])


def beams_of(doc: dict, row: dict) -> list[dict]:
    """What follows the row besides its own elements: its beams and — a
    row of columns — its footings."""
    t = _prim(row)
    return [e for e in doc.get("structure") or []
            if e.get("type") in ("beam", "footing") and e.get("type") != t
            and e.get("row") == row["id"]
            and e.get("level") == row["level"]]


def find(doc: dict, rid) -> dict | None:
    return next((r for r in doc.get("colrows") or [] if r["id"] == rid),
                None)


def of_column(doc: dict, col: dict | None) -> dict | None:
    """The row an element is one OF (None: a loose one): a column of a row
    of columns, a footing of a row of footings."""
    if not col or col.get("type") not in ("column", "footing") \
            or not col.get("row"):
        return None
    r = find(doc, col["row"])
    if r is None or r["level"] != col.get("level") \
            or _prim(r) != col.get("type"):
        return None
    return r


def new_row(doc: dict, level: str, path, closed: bool, o: dict,
            what: str = "columns") -> dict:
    """A new row record (not yet in ``doc``): the next «Column row N» —
    «Footing row N» for a row of footings."""
    import uuid
    noun = "Footing row" if what == "footings" else "Column row"
    names = {r.get("name") for r in doc.get("colrows") or []}
    k = 1
    while f"{noun} {k}" in names:
        k += 1
    ids = {r["id"] for r in doc.get("colrows") or []}
    pre = "fr" if what == "footings" else "cr"
    rid = pre + uuid.uuid4().hex[:6]
    while rid in ids:
        rid = pre + uuid.uuid4().hex[:6]
    out = {"id": rid, "name": f"{noun} {k}", "level": level,
           "path": [[round(p[0], 4), round(p[1], 4)] for p in path],
           "closed": bool(closed), "opts": opts_of(o), "omit": [],
           "dups": [], "n": 0, "sig": ""}
    if what == "footings":
        out["what"] = "footings"
        if out["opts"]["foots"]["type"] == "none":
            out["opts"]["foots"]["type"] = "pads"
    return out


def rebuild(doc: dict, rid: str, pits=(), fit=None, same=None,
            new_elements=None, beams: bool = True, span=None,
            fit_beam=None, fit_foot=None, centre=None,
            ftop=None) -> tuple[dict, dict]:
    """``doc`` with the row ``rid``'s columns made again from it: a station
    that keeps its column keeps its id and name (its material, its «built»);
    new stations get new columns; the ones gone are taken away. ``fit(rec)``
    lays a column into the wall it is on; ``same(a, b)`` — two columns in
    one place: a station over a column that is NOT the row's is left out
    (never two in one place). Returns (doc, info): info = {"made", "kept",
    "gone", "dup", "row"}."""
    doc = dict(doc)
    rows = [dict(r) for r in doc.get("colrows") or []]
    row = next((r for r in rows if r["id"] == rid), None)
    info = {"made": 0, "kept": 0, "gone": 0, "dup": 0,
            "row": row}
    if row is None:
        return doc, info
    o = opts_of(row.get("opts"))
    cols_row = what_of(row) == "columns"
    st_list = stations(row["path"], row.get("closed"), geo(row, o), pits)
    structure = list(doc.get("structure") or [])
    # (a row of footings has no columns: its footings are kept below, by
    # their part and station, as a row of columns' beams)
    mine = members(doc, row) if cols_row else []
    # its stations left out: a column of it deleted — or moved by hand —
    # while the layout stays (a new count / spacing / path: all back)
    now_sig = sig(row)
    omit = set(int(k) for k in row.get("omit") or [])
    held: dict = {}
    loose = set()
    for c in mine:
        k = c.get("st")
        if not isinstance(k, int) or k in held:
            loose.add(id(c))                 # (a copy of one: set free)
            continue
        held[k] = c
    # (one moved by hand — the host's Move — left the row in edits.adopt:
    # its station is missing here, like a deleted one's)
    # (a station over another column was never made: not «deleted»)
    if row.get("sig") == now_sig and row.get("n"):
        was_dup = set(int(k) for k in row.get("dups") or [])
        omit |= {k for k in range(int(row["n"]))
                 if k not in held and k not in was_dup}
    elif row.get("sig") != now_sig:
        omit = set()
    others = [e for e in structure if e.get("type") == "column"
              and e.get("level") == row["level"]
              and (e.get("row") != rid or id(e) in loose)]
    new_by_st: dict = {}
    dups = []
    for k, (x, y, ang) in enumerate(st_list):
        if k in omit or not cols_row:
            continue
        r = dict(column_rec(x, y, ang, o), level=row["level"])
        if fit is not None:
            r = fit(r)
        if same is not None and any(same(r, e) for e in others):
            info["dup"] += 1
            dups.append(k)
            continue
        r["row"], r["st"] = rid, k
        new_by_st[k] = r
    # its BEAMS and FOOTINGS: by (part, stretch / station) — one deleted (or
    # moved alone) stays out while the layout holds, as a column
    def extra(e) -> bool:
        return e.get("type") in ("beam", "footing") and e.get("row") == rid \
            and e.get("level") == row["level"]
    bomit = set(str(k) for k in row.get("bomit") or []) \
        if row.get("sig") == now_sig else set()
    bheld: dict = {}
    for e in structure:
        if extra(e):
            key = f"{e.get('part')}:{e.get('seg')}"
            if key in bheld:
                loose.add(id(e))
            else:
                bheld[key] = e
    if row.get("sig") == now_sig:
        bomit |= {k for k in row.get("bkeys") or [] if k not in bheld}
    # (a part switched off: its deleted ones forgotten — on again, all back)
    bomit = {k for k in bomit if part_on(o, k.split(":")[0])}
    beam_others = [e for e in structure if e.get("type") in ("beam",
                                                             "footing")
                   and e.get("level") == row["level"]
                   and (e.get("row") != rid or id(e) in loose)]
    new_beams: dict = {}
    recs = []
    if beams:
        recs = (beam_recs(row, o, pits, span) if cols_row else []) \
            + foot_recs(row, o, pits, span, cols=new_by_st, centre=centre,
                        skip=bomit, ftop=ftop)
    for r in recs:
        key = f"{r['part']}:{r['seg']}"
        if key in bomit:
            continue
        if r["type"] == "beam" and fit_beam is not None:
            r = fit_beam(r)
        # (a row of footings is its OWN line, everything centred on it —
        # never pushed off it afterwards: his test, 07/11/2026, the pads
        # thrown inside the excavation off the strip, a zigzag. A row of
        # columns' pads: by the excavation's side, kept inside it)
        if r["type"] == "footing" and fit_foot is not None and cols_row:
            r = fit_foot(r)
        if same is not None and any(same(r, e) for e in beam_others):
            info["dup"] += 1
            continue
        new_beams[key] = r
    out = []
    taken = set()
    for e in structure:
        if extra(e) and id(e) not in loose:
            key = f"{e.get('part')}:{e.get('seg')}"
            if key in new_beams and key not in taken:
                keep = {kk: e[kk] for kk in ("id", "name") if kk in e}
                fresh_b = {k2: v for k2, v in e.items()
                           if k2 not in ("zmode", "zt", "fit")}
                out.append(dict(fresh_b, **new_beams[key], **keep))
                taken.add(key)
            continue
        if id(e) in loose:
            e = {k: v for k, v in e.items()
                 if k not in ("row", "st", "part", "seg")}
            out.append(e)
            continue
        if e.get("type") == "column" and e.get("row") == rid \
                and e.get("level") == row["level"]:
            k = e.get("st")
            if k in new_by_st and k not in taken:
                keep = {kk: e[kk] for kk in ("id", "name") if kk in e}
                out.append(dict(e, **new_by_st[k], **keep))
                taken.add(k)
                info["kept"] += 1
            else:
                info["gone"] += 1
            continue
        out.append(e)
    fresh = [new_by_st[k] for k in sorted(new_by_st) if k not in taken] \
        + [new_beams[k] for k in sorted(new_beams) if k not in taken]
    if fresh:
        if new_elements is not None:
            fresh = new_elements(out, fresh)
        out += fresh
        info["made"] = len(fresh)
    # (its «rev» moves on: a rebuild is the ROW's change — settle never
    # takes what it did to the columns for an edit of one of them)
    row.update(omit=sorted(omit), dups=dups, n=len(st_list), sig=now_sig,
               opts=o, rev=int(row.get("rev") or 0) + 1,
               bomit=sorted(bomit), bkeys=sorted(new_beams))
    doc["structure"] = out
    doc["colrows"] = [row if r["id"] == rid else r for r in rows]
    info["row"] = row
    return doc, info


def settle(before: dict, doc: dict) -> tuple[dict, list[str]]:
    """A column of a row changed ON ITS OWN (the options bar, the AI, its
    window's sizes — the row itself the same): the change goes to the ROW.
    Returns (doc, the rows to make again)."""
    rows_now = {r["id"]: r for r in doc.get("colrows") or []}
    if not rows_now:
        return doc, []
    rows_was = {r["id"]: r for r in before.get("colrows") or []}
    was = {e["id"]: e for e in before.get("structure") or []
           if e.get("type") == "column" and e.get("row")}
    todo: dict = {}
    was_b = {e["id"]: e for e in before.get("structure") or []
             if e.get("type") == "beam" and e.get("row")}
    btodo: dict = {}
    was_f = {e["id"]: e for e in before.get("structure") or []
             if e.get("type") == "footing" and e.get("row")}
    for e in doc.get("structure") or []:
        if e.get("type") != "beam" or e.get("row") not in rows_now \
                or e.get("part") not in BEAM_PARTS:
            continue
        rid = e["row"]
        if rows_was.get(rid) != rows_now[rid]:
            continue
        old = was_b.get(e["id"])
        if old is None or old.get("row") != rid:
            continue
        for k in ("w", "h"):
            if old.get(k) != e.get(k):
                btodo.setdefault(rid, {}).setdefault(e["part"], {})[k] = \
                    e.get(k)
    # a row's footing changed on its own: its width / depth go to the row
    # (a pad's width = the pads', a strip's = the strip's)
    ftodo: dict = {}
    for e in doc.get("structure") or []:
        if e.get("type") != "footing" or e.get("row") not in rows_now \
                or e.get("part") not in FOOT_PARTS:
            continue
        rid = e["row"]
        if rows_was.get(rid) != rows_now[rid]:
            continue
        old = was_f.get(e["id"])
        if old is None or old.get("row") != rid:
            continue
        if old.get("w") != e.get("w"):
            ftodo.setdefault(rid, {})["pw" if e["part"] == "pad"
                                      else "sw"] = e.get("w")
        if old.get("d") != e.get("d"):
            both = opts_of(rows_now[rid].get("opts"))["foots"]["type"] \
                == "both"
            ftodo.setdefault(rid, {})["pd" if both and e["part"] == "pad"
                                      else "d"] = e.get("d")
    for e in doc.get("structure") or []:
        if e.get("type") != "column" or e.get("row") not in rows_now:
            continue
        rid = e["row"]
        if rows_was.get(rid) != rows_now[rid]:
            continue              # the row itself was changed: it rules
        old = was.get(e["id"])
        if old is None or old.get("row") != rid:
            continue
        for k in SETTLE_KEYS:
            if old.get(k) != e.get(k):
                todo.setdefault(rid, {})[k] = e.get(k)
    if not todo and not btodo and not ftodo:
        return doc, []
    rows = []
    for r in doc.get("colrows") or []:
        bch = btodo.get(r["id"])
        if bch:
            r = dict(r, opts=opts_of(r.get("opts")))
            for part, kv in bch.items():
                r["opts"]["beams"][part].update(kv)
        fch = ftodo.get(r["id"])
        if fch:
            r = dict(r, opts=opts_of(r.get("opts")))
            r["opts"]["foots"].update(fch)
        ch = todo.get(r["id"])
        if ch:
            r = dict(r, opts=dict(opts_of(r.get("opts"))))
            o = r["opts"]
            if "shape" in ch:
                o["section"] = "round" if ch["shape"] == "round" else "rect"
            for k in ("w", "d", "base", "cbase", "ccap"):
                if k in ch:
                    o[k] = ch[k]
            if "height" in ch:
                if ch["height"] == "level":
                    o["height"] = "level"
                else:
                    o["height"], o["h"] = "custom", float(ch["height"])
        rows.append(r)
    return dict(doc, colrows=rows), list(dict.fromkeys(
        list(todo) + list(btodo) + list(ftodo)))


def from_column(row: dict, old: dict, new: dict, layout: dict | None) -> dict:
    """The row as its column's window leaves it: the column's sizes (and
    its turn, as a change) for every column; the window's «Row» part (by,
    count, spacing, ends) when given."""
    r = dict(row, opts=dict(opts_of(row.get("opts"))))
    o = r["opts"]
    o["section"] = "round" if new.get("shape") == "round" else "rect"
    o["w"] = float(new["w"])
    o["d"] = float(new.get("d", new["w"]))
    h = new.get("height", "level")
    if h == "level":
        o["height"] = "level"
    else:
        o["height"], o["h"] = "custom", float(h)
    o["base"] = float(new.get("base", 0.0) or 0.0)
    o["cbase"], o["ccap"] = new.get("cbase"), new.get("ccap")
    try:
        turn = float(new.get("angle", 0.0)) - float(old.get("angle", 0.0))
    except (TypeError, ValueError):
        turn = 0.0
    if abs(turn) > 1e-6:
        o["angle"] = round(float(o.get("angle", 0.0)) + turn, 3)
    for k in LAYOUT_KEYS:
        if layout and k in layout:
            o[k] = layout[k]
    if layout and isinstance(layout.get("beams"), dict):
        o["beams"] = opts_of({"beams": {
            part: dict(o["beams"][part], **(layout["beams"].get(part) or {}))
            for part in BEAM_PARTS}})["beams"]
    if layout and isinstance(layout.get("foots"), dict):
        o["foots"] = opts_of({"foots": dict(o["foots"],
                                            **layout["foots"])})["foots"]
    return r


def from_footing(row: dict, old: dict, new: dict,
                 layout: dict | None) -> dict:
    """A row of FOOTINGS as one of its footings' window leaves it: its
    width (a pad's: the pads'; a strip's: the strip's) and depth for all of
    them; the window's «Row» part (the layout, what footings) when given."""
    r = dict(row, opts=dict(opts_of(row.get("opts"))))
    o = r["opts"]
    f = dict(o["foots"])
    if old.get("w") != new.get("w"):
        f["pw" if new.get("kind") == "pad" else "sw"] = float(new["w"])
    if old.get("d") != new.get("d") or not old:
        # (with a strip, a pad's depth is the pads' own)
        key = "pd" if (f["type"] == "both" and new.get("kind") == "pad") \
            else "d"
        f[key] = float(new.get("d", f[key]))
    for k in LAYOUT_KEYS:
        if layout and k in layout:
            o[k] = layout[k]
    if layout and layout.get("ftype") in FOOT_TYPES[1:]:
        f["type"] = layout["ftype"]
    o["foots"] = opts_of({"foots": f})["foots"]
    return r


# ---- the file ----------------------------------------------------------------------------
def clean(raw, structure: list[dict], level_ids: set) -> list[dict]:
    """The rows, whatever the file holds: each with a level, a path of two
    points at least and a column of it at least (a row whose columns are all
    gone is gone). Columns pointing to no row — or two on one station — set
    free (``structure`` is changed in place)."""
    out, ids = [], set()
    for r in raw if isinstance(raw, list) else []:
        if not isinstance(r, dict) or str(r.get("level")) not in level_ids:
            continue
        try:
            path = [[float(p[0]), float(p[1])] for p in r.get("path") or []]
        except (TypeError, ValueError, IndexError):
            continue
        rid = str(r.get("id") or "")
        if len(path) < 2 or not rid or rid in ids:
            continue
        o = opts_of(r.get("opts") if isinstance(r.get("opts"), dict) else {})
        try:
            o["w"] = min(max(float(o["w"]), 0.05), 5.0)
            o["d"] = min(max(float(o["d"]), 0.05), 5.0)
            o["angle"] = float(o["angle"])
            o["h"] = min(max(float(o["h"]), 0.2), 50.0)
            o["base"] = min(max(float(o["base"]), -20.0), 20.0)
            o["count"] = min(max(int(o["count"]), 1), 200)
            o["spacing"] = min(max(float(o["spacing"]), 0.2), 100.0)
        except (TypeError, ValueError):
            continue
        o["section"] = "round" if o["section"] == "round" else "rect"
        o["height"] = "custom" if o["height"] == "custom" else "level"
        o["fit"] = "free" if o["fit"] == "free" else "fit"
        o["by"] = "spacing" if o["by"] == "spacing" else "count"
        if o["ends"] not in ("both", "first", "last", "none"):
            o["ends"] = "both"
        if o["align"] not in ALIGNS:
            o["align"] = "auto"
        what = "footings" if r.get("what") == "footings" else "columns"
        try:
            fo = o["foots"]
            fo["pw"] = min(max(float(fo["pw"]), 0.2), 10.0)
            fo["sw"] = min(max(float(fo["sw"]), 0.2), 5.0)
            fo["d"] = min(max(float(fo["d"]), 0.1), 5.0)
            fo["pd"] = min(max(float(fo.get("pd") or 0.8), 0.1), 5.0)
        except (TypeError, ValueError):
            o["foots"] = copy.deepcopy(DEFAULT_OPTS["foots"])
        if what == "footings" and o["foots"]["type"] == "none":
            o["foots"]["type"] = "pads"
        try:
            omit = sorted({int(k) for k in r.get("omit") or []})
            dups = sorted({int(k) for k in r.get("dups") or []})
            n = int(r.get("n") or 0)
            rev = int(r.get("rev") or 0)
        except (TypeError, ValueError):
            omit, dups, n, rev = [], [], 0, 0
        ids.add(rid)
        noun = "Footing row" if what == "footings" else "Column row"
        out.append({"id": rid, "name": str(r.get("name") or noun),
                    "level": str(r["level"]), "path": path,
                    "closed": bool(r.get("closed")) and len(path) > 2,
                    "opts": o, "omit": omit, "dups": dups, "n": n,
                    "sig": str(r.get("sig") or ""), "rev": rev,
                    "bomit": sorted({str(k) for k in r.get("bomit") or []}),
                    "bkeys": sorted({str(k) for k in r.get("bkeys") or []})})
        if what == "footings":
            out[-1]["what"] = "footings"
    lv = {r["id"]: r["level"] for r in out}
    foot_rows = {r["id"] for r in out if r.get("what") == "footings"}
    seen, used = set(), set()
    for e in structure:
        if e.get("type") in ("beam", "footing") and "row" in e:
            parts = BEAM_PARTS if e["type"] == "beam" else FOOT_PARTS
            key = (e.get("row"), e.get("part"), e.get("seg"))
            if lv.get(e.get("row")) != e.get("level") or key in seen \
                    or e.get("part") not in parts \
                    or not isinstance(e.get("seg"), int) \
                    or (e["type"] == "beam" and e.get("row") in foot_rows):
                for k in ("row", "part", "seg"):
                    e.pop(k, None)
            else:
                seen.add(key)
                if e["type"] == "footing" and e.get("row") in foot_rows:
                    used.add(e["row"])          # a row of footings: alive
            continue
        if e.get("type") != "column" or "row" not in e:
            continue
        key = (e.get("row"), e.get("st"))
        if lv.get(e.get("row")) != e.get("level") or key in seen \
                or not isinstance(e.get("st"), int) \
                or e.get("row") in foot_rows:
            e.pop("row", None)
            e.pop("st", None)
            continue
        seen.add(key)
        used.add(e["row"])
    keep = [r for r in out if r["id"] in used]
    ids = {r["id"] for r in keep}
    for e in structure:      # a row gone: its beams and footings set free
        if e.get("type") in ("beam", "footing") and "row" in e \
                and e.get("row") not in ids:
            for k in ("row", "part", "seg"):
                e.pop(k, None)
    return keep
