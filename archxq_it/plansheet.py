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


def outside_dims(walls, openings, U, rows: int) -> list[dict]:
    """[{"side", "row" 1|2|3, "a", "b"}] — row 1: corners and openings,
    row 2: corners, row 3: the overall size; a, b on the box's side."""
    if rows <= 0 or U.is_empty:
        return []
    x0, y0, x1, y1 = U.bounds
    byid = {w["id"]: w for w in walls}
    corners = {s: set() for s in DIRS}
    opens = {s: set() for s in DIRS}
    polys = list(getattr(U, "geoms", [U]))
    for g in polys:
        for ring in [g.exterior] + list(g.interiors):
            for x, y in list(ring.coords)[:-1]:
                for s in DIRS:
                    if seen(U, (x, y), s):
                        corners[s].add(round(x if s in "SN" else y, 4))
    for o in openings:
        w = byid.get(o.get("wall"))
        gp = _gap(o, w) if w else None
        if gp is None:
            continue
        for s in DIRS:
            if any(seen(U, p, s) for p in gp["pts"]):
                vs = [p[0] if s in "SN" else p[1] for p in gp["pts"]]
                opens[s] |= {round(min(vs), 4), round(max(vs), 4)}
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
                out += [{"side": s, "row": row, "a": P(a), "b": P(b)}
                        for a, b in zip(stops, stops[1:]) if b - a > 0.02]
        out.append({"side": s, "row": 3, "a": P(lo), "b": P(hi)})
    return out


def inside_dims(U, rooms) -> list[dict]:
    """One chain across the rooms each way — the clear spans between the
    walls' faces, on the line (through the rooms' label points) that
    crosses the most rooms. [{"axis": "h"|"v", "a", "b"}]."""
    from shapely.geometry import LineString
    if U.is_empty or not rooms:
        return []
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
                out.append({"axis": axis,
                            "a": (a, v) if axis == "h" else (v, a),
                            "b": (b, v) if axis == "h" else (v, b)})
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
    """The title block at the side column's foot: the office (logo, three
    lines), the project's fields, scale · date · revision · sheet."""
    style = pc.style
    W_ = DS.words(style)
    sx0, _sy0, sx1, sy1 = L["side"]
    cy0 = sy1 - TITLE_BLOCK_MM
    proj = doc.get("project") or {}
    off = style.get("office") or {}
    pc.rect("tb:frame", sx0, cy0, sx1, sy1, 0.5)
    if off.get("logo"):
        pc.items.append({"kind": "image", "key": "tb:logo", "x": sx0 + 4.0,
                         "y": cy0 + 4.0, "w": 30.0, "h": 16.0,
                         "path": off["logo"]})
    oy = cy0 + 5.0
    for i, t in enumerate((off.get("name"), off.get("line2"),
                           off.get("line3"))):
        if t:
            pc.text(f"tb:office:{i}", sx0 + (38.0 if off.get("logo")
                                              else 4.0),
                    oy, t, "table" if i else "label")
            oy += 5.0
    today = today or datetime.date.today()
    date = today.strftime("%d/%m/%Y" if DS.comma(style) else "%Y-%m-%d")
    fields = [("PROJECT", proj.get("name", "")),
              ("CLIENT", proj.get("client", "")),
              ("LOCATION", proj.get("location", "")),
              ("DRAWING", sheet["title"].upper())]
    yy = cy0 + 24.0
    mute = style["colors"]["mute"]
    for key, val in fields:
        pc.line(f"tb:rule:{key}", (sx0, yy), (sx1, yy), 0.18)
        pc.text(f"tb:{key}:k", sx0 + 3.0, yy + 1.0, W_[key], "label",
                color=mute)
        pc.text(f"tb:{key}:v", sx0 + 3.0, yy + 4.4, str(val or ""), "value")
        yy += 9.0
    pc.line("tb:rule:cells", (sx0, yy), (sx1, yy), 0.18)
    cw = (sx1 - sx0) / 4
    cells = [("SCALE", DS.scale_text(n) if n else "—"), ("DATE", date),
             ("REVISION", "R00"),
             ("SHEET", f"{sheet['number']} · {index:02d}/{total:02d}")]
    for i, (key, val) in enumerate(cells):
        x = sx0 + i * cw
        if i:
            pc.line(f"tb:col:{i}", (x, yy), (x, yy + 12.0), 0.18)
        pc.text(f"tb:{key}:k", x + 2.5, yy + 1.0, W_[key], "label",
                color=mute)
        pc.text(f"tb:{key}:v", x + 2.5, yy + 5.0, val, "value")
    yy += 12.0
    pc.line("tb:rule:rev", (sx0, yy), (sx1, yy), 0.18)
    pc.text("tb:rev", sx0 + 3.0, yy + 1.5,
            f"R00   {date}   {W_['rev_first']}", "table")


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
            top = li["under"] if w.get("height", "level") == "level"                 else z0 + float(w["height"])
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
    tags, types = opening_types(openings)
    from shapely.geometry import Point
    tt = DS.text(style, "tag")
    tw_, th_ = tt["mm"] * 3.4, tt["mm"] * 2.2
    room_polys = [r["poly"] for r in rooms]
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
            placed = None
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
            for _, _, _, q in cands:
                px, py = P(q)
                bb = (px - tw_ / 2, py - th_ / 2, px + tw_ / 2, py + th_ / 2)
                if not any(_hit(bb, b[1:]) for b in boxes):
                    placed = (px, py, bb)
                    break
            if placed is None and cands:
                q = cands[0][3]
                px, py = P(q)
                placed = (px, py, (px - tw_ / 2, py - th_ / 2,
                                   px + tw_ / 2, py + th_ / 2))
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
        items.append({"kind": "dim", "key": f"dim:{s}:{row}:{i}",
                      "a": [dd["a"][0], dd["a"][1], z0 + cut],
                      "b": [dd["b"][0], dd["b"][1], z0 + cut],
                      "pa": pa, "pb": pb, "off": rows_mm[row - 1],
                      "out": outward[s], "mm": dmm,
                      "short": L_ < _tw(label, dmm) + 1.0,
                      "color": dimc, "pen": pens["dim"]})
    if show.get("dims_in", "across") != "none":
        for i, dd in enumerate(inside_dims(U, rooms)):
            pa, pb = P(dd["a"]), P(dd["b"])
            label = DS.length(math.dist(dd["a"], dd["b"]), style)
            items.append({"kind": "dim", "key": f"dim:in:{dd['axis']}:{i}",
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
    cy0 = sy1 - TITLE_BLOCK_MM
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

    return {"paper": paper, "scale": n, "fits": ok, "page": L["page"],
            "layout": L, "view": view, "items": items, "tags": tags,
            "types": types, "rooms": rooms, "boxes": boxes,
            "level_text": lvl_txt,
            "extent": (*P((X0, Y1)), *P((X1, Y0)))}


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
