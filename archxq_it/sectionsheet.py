# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A SECTION or an ELEVATION sheet, worked out on paper — the same finish
as the plans (PLANO_DOCUMENTACAO_CORTES.md, 2026-10-23): NBR 6492 / 8402.

``make(doc, elevations, sheet, style)`` gives the sheet as NEUTRAL pieces in
paper millimetres (page origin top-left, y down), each with a STABLE key —
``hostsheet`` lays them on the composer and keeps what the architect moved
or hid, as for the plans. Nothing here knows the host.

What the algorithm does: paper and scale that fit; the host's exact view
through a vertical cut (a section) or from a side (an elevation); the level
marks on both sides (finished floors from the ground floor's ±0,00, the roof
on top); the floor-to-floor heights and the overall height on the left; the
cut rooms' names; a ground line when the terrain is off; the title and the
side column — a KEY PLAN with the line (or the side looked at), the levels,
notes and the title block.
"""
from __future__ import annotations

import datetime
import math

from . import docstyle as DS
from . import framing as FR
from . import plansheet as PS
from . import structure as S
from . import walls as W

FOOT_M = 1.0              # shown under the lowest floor (footings, ground)
TOP_M = 0.4               # over the highest point
TOP_STOP_M = 1.0          # a ridge this far over the last floor is measured
#: paper room round the building (mm): the left side carries the level
#: marks and two dimension rows, the right side the level marks
RESERVE_L, RESERVE_R, RESERVE_V = 46.0, 36.0, 8.0
MARK_LINE = (3.0, 22.0)           # a level mark's line, off the building
MARK_TRI = 12.0                   # its triangle, off the building
TRI_W, TRI_H = 2.6, 2.2
DIM_ROWS = (30.0, 38.0)           # heights chain, overall height
#: the openings' height chains (C3), right of the building: the first
#: column past the level marks (or by the wall when the right has none),
#: the next ones this far apart; their witness lines this long (mm)
OPEN_COL = (27.0, 9.0, 6.0)
OPEN_TICK = 3.0
#: the widths under an elevation (C3): the openings, the overall (mm)
WIDTH_ROWS = (6.0, 13.0)
#: what the new chains take on paper, to choose the paper and scale (mm)
OPEN_ROOM_R, WIDTH_ROOM_V = 9.0, 10.0
KEY_H = 52.0                      # the key plan's box height (mm)
SYM_CUT = 8                       # pieces an opening symbol's line is
#                                   tested in (hidden_points)
DASH = (3.0, 1.2)                 # a dashed line on paper (mm)


# ---- the geometry ----------------------------------------------------------------------
def frame_of(doc: dict, elevations, sheet: dict) -> dict | None:
    """Where the sheet looks from and what it holds: {"look", "right",
    "plane" (point, normal) or None, "lo", "hi" (along the page's right,
    absolute), "zlo", "zhi", "line"} — None with no walls."""
    from . import docs as D
    from . import sheetset as SS
    box = D.extents(doc, elevations)
    if box is None:
        return None
    poly = [(box["x0"], box["y0"]), (box["x1"], box["y0"]),
            (box["x1"], box["y1"]), (box["x0"], box["y1"])]
    plane = None
    line = None
    if sheet.get("kind") == "section":
        line = SS.line_of(sheet)
        (ax, ay), (bx, by) = line["a"], line["b"]
        L = math.hypot(bx - ax, by - ay) or 1.0
        ux, uy = (bx - ax) / L, (by - ay) / L
        s = -1.0 if line.get("flip") else 1.0
        lx, ly = -uy * s, ux * s                 # to the line's left
        q = ((ax + bx) / 2, (ay + by) / 2)
        # the side the viewer stands on is cut away: keep (p − q)·n ≤ 0
        plane = {"point": [q[0], q[1], (box["z0"] + box["z1"]) / 2],
                 "normal": [-lx, -ly, 0.0], "symbol": line["symbol"]}
        poly = clip(poly, q, (-lx, -ly)) or poly
    else:
        lx, ly = sheet.get("look") or (0.0, 1.0)
    rx, ry = ly, -lx                             # the page's right, in plan
    along = [p[0] * rx + p[1] * ry for p in poly]
    return {"look": (lx, ly), "right": (rx, ry), "plane": plane,
            "lo": min(along), "hi": max(along), "line": line,
            "zlo": box["z0"] - FOOT_M, "zhi": box["z1"] + TOP_M, "box": box}


def hidden_points(doc: dict, elevations, pts, look) -> list:
    """[True: hidden] for each (owner id, (x, y, z)) seen in an elevation
    looking along ``look``: a face of ANOTHER element ArchXQ builds (a
    wall, a low wall, a column, a slab…) stands between it and the viewer.
    See-through faces (glass) hide nothing. Only what ArchXQ builds is
    known here — a tree, a drawing of the host's own is not. Any trouble:
    nothing hidden (as before)."""
    try:
        from shapely.geometry import Point, Polygon
        lx, ly = look
        rx, ry = -ly, lx
        want = [(wid, p[0] * rx + p[1] * ry, p[2], p[0] * lx + p[1] * ly)
                for wid, p in pts]
        r0 = min(q[1] for q in want) - 0.01
        r1 = max(q[1] for q in want) + 0.01
        z0 = min(q[2] for q in want) - 0.01
        z1 = max(q[2] for q in want) + 0.01
        near = max(q[3] for q in want)
        faces = []
        for el in S.build(doc, elevations):
            eid = el.get("id")
            for f in el.get("faces") or ():
                rec = f if isinstance(f, dict) else {"loop": f}
                col = rec.get("color")
                if col is not None and len(col) > 3 and col[3] < 0.999:
                    continue                  # glass: seen through
                loop = rec["loop"]
                rs = [p[0] * rx + p[1] * ry for p in loop]
                zs = [p[2] for p in loop]
                ds = [p[0] * lx + p[1] * ly for p in loop]
                if max(rs) < r0 or min(rs) > r1 or max(zs) < z0 \
                        or min(zs) > z1 or min(ds) > near:
                    continue
                n = [0.0, 0.0, 0.0]
                for a, b in zip(loop, list(loop[1:]) + [loop[0]]):
                    n[0] += (a[1] - b[1]) * (a[2] + b[2])
                    n[1] += (a[2] - b[2]) * (a[0] + b[0])
                    n[2] += (a[0] - b[0]) * (a[1] + b[1])
                ln = math.sqrt(sum(v * v for v in n))
                if ln < 1e-12:
                    continue
                n = [v / ln for v in n]
                nl_ = n[0] * lx + n[1] * ly
                if abs(nl_) < 1e-3:
                    continue                  # edge-on: hides nothing
                d = sum(n[i] * loop[0][i] for i in range(3))
                faces.append((eid, min(rs), max(rs), min(zs), max(zs),
                              (d, n[0] * rx + n[1] * ry, n[2], nl_),
                              loop, rec.get("holes") or [], [None]))
        out = []
        for wid, r, z, dep in want:
            hit = False
            for eid, a0, a1, c0, c1, (d, nr, nz, nl_), loop, holes, memo \
                    in faces:
                if eid == wid or not (a0 <= r <= a1 and c0 <= z <= c1):
                    continue
                if (d - r * nr - z * nz) / nl_ > dep - 0.02:
                    continue                  # behind it (or in its plane)
                if memo[0] is None:
                    memo[0] = Polygon(
                        [(p[0] * rx + p[1] * ry, p[2]) for p in loop],
                        [[(p[0] * rx + p[1] * ry, p[2]) for p in h]
                         for h in holes if len(h) >= 3]).buffer(0)
                if memo[0].contains(Point(r, z)):
                    hit = True
                    break
            out.append(hit)
        return out
    except Exception:  # noqa: BLE001 — every symbol shown, as before
        return [False] * len(pts)


def clip(poly: list, q, n) -> list:
    """The polygon's part where (p − q)·n ≤ 0."""
    def f(p):
        return (p[0] - q[0]) * n[0] + (p[1] - q[1]) * n[1]
    out = []
    for i, p in enumerate(poly):
        r = poly[(i + 1) % len(poly)]
        fp, fr = f(p), f(r)
        if fp <= 1e-9:
            out.append(p)
        if (fp < 0 < fr) or (fr < 0 < fp):
            t = fp / (fp - fr)
            out.append((p[0] + (r[0] - p[0]) * t, p[1] + (r[1] - p[1]) * t))
    return out


def stops(doc: dict, elevations) -> list[tuple]:
    """The heights a section measures, from the bottom: [(z, level id or
    None, name)] — every level's floor, the top of the last one (the roof
    level) and the highest point when a roof stands over it."""
    info = S.levels_info(doc, elevations)
    levels = doc.get("levels") or []
    out = [(info[lv["id"]]["z0"], lv["id"], lv["name"]) for lv in levels]
    if levels:
        top = levels[-1]
        out.append((info[top["id"]]["z0"] + info[top["id"]]["height"], None,
                    ""))
    return out


def opening_dims_on(style: dict, sheet: dict | None = None) -> tuple:
    """(the openings' heights, the widths below) on a section / elevation
    sheet — the Pro's (C3); the widths only on an elevation."""
    from . import edition
    if edition.lite():
        return False, False
    show = style.get("show") or {}
    elev = (sheet or {}).get("kind") != "section"
    return (bool(show.get("sec_open", True)),
            elev and bool(show.get("sec_width", True)))


def opening_marks(doc: dict, elevations, G: dict, info: dict) -> dict:
    """What the C3 chains measure, from the sheet's frame ``G``:
    {"groups": [{"lid", "ref", "col", "stops": [(z, name)], "ids"}],
    "widths": [(along, name)]}.

    An elevation: the doors and windows of the walls whose outer face looks
    at the viewer and that nothing built hides; a section: the ones the cut
    goes through (and the cut slab's underside joins their chain). Per
    level, the openings with the same sill and head (to the cm) share one
    chain — the most of them in the first column; the widths: every
    opening's two sides seen from the elevation, and the building's ends."""
    rx, ry = G["right"]
    lx, ly = G["look"]
    plane = G["plane"]
    levels = {lv["id"]: lv for lv in doc.get("levels") or []}
    order = [lv["id"] for lv in doc.get("levels") or []]
    byid = {w["id"]: w for w in doc.get("walls") or []}
    seen, probe = [], []
    # (a corner window — cornerwin.py: each of its parts on its own wall)
    from . import cornerwin as CW
    split = CW.split(doc.get("walls") or [], doc.get("openings") or [])
    for o in split:
        w = byid.get(o.get("wall"))
        if w is None or w.get("level") not in levels or \
                w.get("kind", "line") != "line":
            continue
        try:
            seg = W.centre(w)
        except Exception:  # noqa: BLE001 — a broken wall: nothing to measure
            continue
        s0 = float(o["pos"]) - float(o["w"]) / 2
        s1 = float(o["pos"]) + float(o["w"]) / 2
        if o.get("_out"):               # a corner window's part: as SEEN,
            side, e = o["_out"]         # up to the corner's outside
            s0, s1 = (s0, s1 + e) if side == "hi" else (s0 - e, s1)
        if plane:
            (qx, qy), (nx, ny) = plane["point"][:2], plane["normal"][:2]
            un = seg.u[0] * nx + seg.u[1] * ny
            if abs(un) < 0.1:
                continue                      # along the cut: not cut
            s = ((qx - seg.p0[0]) * nx + (qy - seg.p0[1]) * ny) / un
            if not (s0 + 0.01 < s < s1 - 0.01):
                continue
            pc_ = (seg.p0[0] + seg.u[0] * s, seg.p0[1] + seg.u[1] * s)
            if not (G["lo"] - 0.01 <= pc_[0] * rx + pc_[1] * ry
                    <= G["hi"] + 0.01):
                continue
        else:
            sd = -1.0 if float(w.get("side", 1)) < 0 else 1.0
            ox, oy = sd * seg.u[1], -sd * seg.u[0]   # its outer face
            if ox * lx + oy * ly > -0.5:
                continue                      # not facing the viewer
        li = info[w["level"]]
        z0 = li["z0"]
        top = li["under"] if w.get("height", "level") == "level" \
            else z0 + float(w["height"])
        ops = [x for x in split if x.get("wall") == w["id"]]
        f = S.fitted(o, w, ops, top - z0)
        if f is None:
            continue
        zs = z0 + float(o.get("sill", 0.0) or 0.0) + W.opening_lift(w)
        zh = zs + float(f["h"])
        ends = [(seg.p0[0] + seg.u[0] * t, seg.p0[1] + seg.u[1] * t)
                for t in (s0, s1)]
        seen.append({"o": o, "w": w, "lid": w["level"], "zs": zs, "zh": zh,
                     "ends": ends})
        if not plane:                 # what is in front of it hides it
            t = float(w["t"]) / 2
            c = ((ends[0][0] + ends[1][0]) / 2 + ox * t,
                 (ends[0][1] + ends[1][1]) / 2 + oy * t)
            probe.append((w["id"], (c[0], c[1], (zs + zh) / 2)))
    if probe:
        hid = hidden_points(doc, elevations, probe, (lx, ly))
        seen = [x for x, h in zip(seen, hid) if not h]
    groups = []
    for lid in order:
        mine = [x for x in seen if x["lid"] == lid]
        if not mine:
            continue
        li = info[lid]
        z0, nxt = li["z0"], li["z0"] + li["height"]
        sets: dict = {}
        for x in mine:
            key = (round(x["zs"] - z0, 2), round(x["zh"] - z0, 2))
            sets.setdefault(key, []).append(x)
        ranked = sorted(sets.items(), key=lambda kv: (-len(kv[1]), kv[0][1],
                                                      kv[0][0]))
        for col, ((sl, hd), xs) in enumerate(ranked):
            zs, zh = z0 + sl, z0 + hd
            st = [(z0, "floor")]
            if sl > 0.005:
                st.append((zs, "sill"))
            st.append((zh, "head"))
            if plane and zh + 0.005 < li["under"] < nxt - 0.005:
                st.append((li["under"], "slab"))   # the cut slab's underside
            if nxt > st[-1][0] + 0.005:
                st.append((nxt, "next"))
            groups.append({"lid": lid, "col": col,
                           "ref": f"{round(sl * 100)}-{round(hd * 100)}",
                           "stops": st, "ids": [x["o"]["id"] for x in xs]})
    widths = []
    if not plane and seen:
        pos: list = []
        for x in sorted(seen, key=lambda x: order.index(x["lid"])):
            for (px, py), side in zip(x["ends"], ("lo", "hi")):
                pos.append((px * rx + py * ry, f"o:{x['o']['id']}:{side}"))
        pos += [(G["lo"], "end:lo"), (G["hi"], "end:hi")]
        for v, nm in sorted(pos):
            if widths and abs(v - widths[-1][0]) < 0.01:
                continue                      # one place, its first name
            widths.append((v, nm))
    shown = [{"id": x["o"]["id"], "zs": x["zs"], "zh": x["zh"],
              "v": sorted(px * rx + py * ry for px, py in x["ends"])}
             for x in seen]
    return {"groups": groups, "widths": widths, "seen": shown}


def cut_fill(doc: dict, sheet: dict) -> str:
    """How the cut is filled: «solid» or «hatch». Auto: hatched when the
    cut goes through EARTH — the terrain shown and floors under the ground
    (the corporate building's B-B: the earth by the basements came out as
    black masses over their level marks, 2026-10-23). The host fills every
    cut alike, and a second view for the earth alone would hide the first
    (its views are opaque — M0)."""
    fill = sheet.get("fill", "auto") or "auto"
    if fill != "auto":
        return fill
    under = any(lv.get("kind") == "basement" for lv in doc.get("levels") or [])
    if sheet.get("kind") == "section" and sheet.get("terrain", True) and under:
        return "hatch"
    return "solid"


# ---- paper and scale ---------------------------------------------------------------------
def reserves(style: dict, sheet: dict | None = None) -> tuple:
    """(left, right, top and bottom) paper kept round the building (mm):
    the level marks and heights — and room for C3's chains when shown."""
    oh, ow = opening_dims_on(style, sheet)
    return (RESERVE_L, RESERVE_R + (OPEN_ROOM_R if oh else 0.0),
            RESERVE_V + (WIDTH_ROOM_V / 2 if ow else 0.0))


def fits(ext_w: float, ext_h: float, paper: str, n: float,
         style: dict, sheet: dict | None = None) -> bool:
    x0, y0, x1, y1 = PS.layout(paper, style)["area"]
    rl, rr, rv = reserves(style, sheet)
    return ext_w * 1000.0 / n + rl + rr <= x1 - x0 and \
        ext_h * 1000.0 / n + 2 * rv <= y1 - y0


# ---- the sheet -------------------------------------------------------------------------
def make(doc: dict, elevations, sheet: dict, style: dict,
         today: datetime.date | None = None, total: int = 1,
         index: int = 1) -> dict:
    """The section / elevation sheet as neutral pieces: {"paper", "scale",
    "fits", "page", "layout", "view", "items", "tags", "types", "rooms",
    "boxes"} (tags, types, rooms: what the checks read — none here but
    the cut rooms)."""
    W_ = DS.words(style)
    show = style["show"]
    G = frame_of(doc, elevations, sheet)
    if G is None:
        raise ValueError("no walls — nothing to draw")
    info = S.levels_info(doc, elevations)
    ground = float((doc.get("project") or {}).get("ground_level", 0.0) or 0.0)
    wid, hgt = G["hi"] - G["lo"], G["zhi"] - G["zlo"]
    paper, n, ok = PS.choose(wid, hgt, style,
                             sheet.get("paper", "auto") or "auto",
                             sheet.get("scale", "auto") or "auto",
                             fits=lambda *a: fits(*a, sheet=sheet))
    L = PS.layout(paper, style)
    ax0, ay0, ax1, ay1 = L["area"]
    k = 1000.0 / n
    # the building sits between the reserves; the frame is the whole area
    res_l, res_r, _res_v = reserves(style, sheet)
    fcx = ax0 + res_l + (ax1 - ax0 - res_l - res_r) / 2
    fcy = (ay0 + ay1) / 2
    m = (G["lo"] + G["hi"]) / 2                  # the building's middle
    tz = (G["zlo"] + G["zhi"]) / 2
    rx, ry = G["right"]
    lx, ly = G["look"]
    # the camera's target: on the cut (or the box's middle), at m across
    if G["plane"]:
        qx, qy = G["plane"]["point"][:2]
    else:
        b = G["box"]
        qx, qy = (b["x0"] + b["x1"]) / 2, (b["y0"] + b["y1"]) / 2
    d = m - (qx * rx + qy * ry)
    tx, ty = qx + rx * d, qy + ry * d
    # the view frame centred on the target: the area's middle, so it is
    # shifted from the building's place (fcx) — wider on the left
    vw = 2 * min(fcx - ax0, ax1 - fcx)
    view = {"x": fcx - vw / 2, "y": ay0, "w": vw, "h": ay1 - ay0,
            "scale": n, "target": [tx, ty, tz], "look": [lx, ly],
            "right": [rx, ry],
            "plane": G["plane"], "kind": sheet.get("kind", "section"),
            "fill": cut_fill(doc, sheet)}

    def X(along: float) -> float:              # absolute «along r» → page
        return fcx + (along - m) * k

    def Y(z: float) -> float:
        return fcy - (z - tz) * k
    xl, xr = X(G["lo"]), X(G["hi"])
    pc = PS.Pieces(style)
    ink, dimc, pens = style["colors"]["ink"], style["colors"]["dim"], \
        style["pens"]
    bx0, by0, bx1, by1 = L["border"]
    pc.rect("border", bx0, by0, bx1, by1, "border")
    pc.items.append(dict(view, key="view"))
    pc.items[-1]["kind"] = "view"

    # --- light-framed walls the cut crosses, at 1:50 or closer: plates and
    # headers with their X, the studs outlined, the insulation's zigzag —
    # their cut's fill taken off (phase 3b)
    if G["plane"] and n <= FR.SYMBOL_SCALE:
        def PG(p):
            return (X(p[0] * rx + p[1] * ry), Y(p[2]))
        qn = G["plane"]["normal"][:2]
        ops_all = doc.get("openings") or []
        for lid, li in info.items():
            walls = [w for w in doc.get("walls") or []
                     if w.get("level") == lid]
            framed = [w for w in walls if FR.frame_of(w) is not None]
            if not framed:
                continue
            plans = W.plan(walls)
            fix = S.frame_marks(doc, lid, walls, plans)
            z0 = li["z0"]
            # (a sill plate on concrete: its anchor bolt — 4c, D8)
            sill = S._sill_on_masonry(doc.get("walls") or [], walls, plans,
                                      [lv["id"] for lv in doc["levels"]],
                                      lid)
            # (where it is built: down through its slab — its plates there)
            try:
                drops = S.level_drops(doc, elevations, lid, walls, plans)
            except Exception:  # noqa: BLE001 — from its floor, as before
                drops = {}
            for w in framed:
                pcs = plans.get(w["id"])
                if not pcs:
                    continue
                if w["id"] in sill:
                    w = dict(w, _treated=True)
                if w["id"] in fix:                   # (T / beam studs, 4a)
                    w = dict(w, _fix=fix[w["id"]])
                b = z0 + float(w.get("base", 0.0)) - drops.get(w["id"], 0.0)
                top = li["under"] if w.get("height", "level") == "level" \
                    else z0 + float(w["height"])
                ops = [f for f in (S.fitted(o, w, ops_all, top - z0)
                                   for o in ops_all
                                   if o["wall"] == w["id"])
                       if f is not None]
                got = FR.section_symbols(w, pcs, ops, z0, b, top,
                                         (qx, qy), qn)
                if not got:
                    continue
                for j, poly in enumerate(got["blank"]):
                    pc.items.append({"kind": "fill",
                                     "key": f"frame:{w['id']}:b{j}",
                                     "poly": [PG(p) for p in poly],
                                     "color": "#ffffff", "opacity": 1.0})
                for j, (a, c) in enumerate(got["lines"]):
                    pc.line(f"frame:{w['id']}:l{j}", PG(a), PG(c),
                            "symbol")
        # a roof's rafters and insulation (PLANO_TELHADO_CAMADAS 2c)
        for r in doc.get("structure") or []:
            if r.get("type") != "roof" or r.get("level") not in info:
                continue
            got = S.roof_section_symbols(doc, elevations, r, (qx, qy), qn)
            if not got:
                continue
            for j, poly in enumerate(got["blank"]):
                pc.items.append({"kind": "fill",
                                 "key": f"rframe:{r['id']}:b{j}",
                                 "poly": [PG(p) for p in poly],
                                 "color": "#ffffff", "opacity": 1.0})
            for j, (a, c) in enumerate(got["lines"]):
                pc.line(f"rframe:{r['id']}:l{j}", PG(a), PG(c), "symbol")
        # a floor's joists and insulation (PLANO_PISOS_BARROTES D9)
        for e in doc.get("structure") or []:
            if e.get("type") != "slab" or e.get("level") not in info \
                    or S.slab_frame(e) is None:
                continue
            got = S.slab_section_symbols(doc, elevations, e, (qx, qy), qn)
            if not got:
                continue
            for j, poly in enumerate(got["blank"]):
                pc.items.append({"kind": "fill",
                                 "key": f"sframe:{e['id']}:b{j}",
                                 "poly": [PG(p) for p in poly],
                                 "color": "#ffffff", "opacity": 1.0})
            for j, (a, c) in enumerate(got["lines"]):
                pc.line(f"sframe:{e['id']}:l{j}", PG(a), PG(c), "symbol")

    # --- a layered wall's layers where the cut crosses it, with their hatches
    from . import wallsheet as WS
    if G["plane"] and WS.drawn_at(style, n):
        WS.paint(pc, WS.section_parts(doc, elevations, info, (qx, qy),
                                      G["plane"]["normal"][:2], X, Y,
                                      (rx, ry), n <= FR.SYMBOL_SCALE))

    # --- a SECTION through a grid wall (gridwall.py): its rails cut, its
    # glass as a line — the cut's solid fill taken off
    if G["plane"]:
        try:
            from . import gridwall as GX
            cuts = S.grid_reads(doc, elevations)
        except ImportError:                  # (the Lite: no grid walls)
            cuts = []
        gn = G["plane"]["normal"][:2]
        for w, pcs, gz0, gb, gtop, gops, gctx in cuts:
            blanks, glines = GX.section_drawing(
                w, pcs, gz0, gb, gtop, gops, gctx, (qx, qy), gn,
                float(pens["cut"]) / 2 * n / 1000.0 + 0.005)
            for j, poly in enumerate(blanks):
                pc.items.append({"kind": "fill", "key": f"gwsec:{w['id']}:b{j}",
                                 "poly": [(X(p[0] * rx + p[1] * ry), Y(p[2]))
                                          for p in poly],
                                 "color": "#ffffff", "opacity": 1.0})
            for j, (a, c) in enumerate(glines):
                pc.line(f"gwsec:{w['id']}:l{j}",
                        (X(a[0] * rx + a[1] * ry), Y(a[2])),
                        (X(c[0] * rx + c[1] * ry), Y(c[2])), "symbol")

    # --- an ELEVATION: how each window of a grid wall opens (gridwall.py,
    # phase B) — on the grid walls whose outer face looks at the viewer
    if not G["plane"]:
        try:
            from . import gridwall as GX
            reads = S.grid_reads(doc, elevations)
        except ImportError:                  # (the Lite: no grid walls)
            reads = []
        segs = []
        for w, pcs, z0, b, top, ops, ctx in reads:
            seg = W.centre(w)
            if seg.kind != "line":
                continue
            sd = -1.0 if float(w.get("side", 1)) < 0 else 1.0
            # (its outer face: −side across — clad.frame_of's frame)
            ox, oy = sd * seg.u[1], -sd * seg.u[0]
            if ox * lx + oy * ly > -0.5:      # not facing the viewer
                continue
            # (each line in SYM_CUT pieces: one half behind a wall's top
            # is drawn down to that top, not over the wall — his rule,
            # 12/11/2026: looked at on the sheet)
            for j, (a, c) in enumerate(GX.symbols(w, pcs, z0, b, top, ops,
                                                  ctx)):
                # (``m``, never ``k``: k is this sheet's scale factor)
                for m_ in range(SYM_CUT):
                    segs.append((w["id"], f"{j}.{m_}", tuple(
                        a[i] + (c[i] - a[i]) * m_ / SYM_CUT
                        for i in range(3)), tuple(
                        a[i] + (c[i] - a[i]) * (m_ + 1) / SYM_CUT
                        for i in range(3))))
        # a symbol behind something built in front of it (a boundary wall,
        # a column, another wall) is not drawn — each piece by its middle
        hid = hidden_points(doc, elevations, [
            (wid, tuple((a[i] + c[i]) / 2 for i in range(3)))
            for wid, _j, a, c in segs], (lx, ly)) if segs else []
        for (wid, j, a, c), h in zip(segs, hid):
            if not h:
                pc.line(f"gwsym:{wid}:{j}",
                        (X(a[0] * rx + a[1] * ry), Y(a[2])),
                        (X(c[0] * rx + c[1] * ry), Y(c[2])), "symbol")

    # --- level marks, both sides (or the left) --------------------------------------
    marks = show.get("sec_marks", "both")
    sts = stops(doc, elevations)
    roofed = any(s.get("type") == "roof" for s in doc.get("structure") or [])
    mm_l = DS.text(style, "level")
    for i, (z, lid, name) in enumerate(sts):
        if lid is None:          # the top of the last floor
            name = W_.get("roof", "") if roofed else W_.get("top", "")
        val = PS.level_text(z - ground, style)
        y = Y(z)
        for side in (("L", "R") if marks == "both" else
                     ("L",) if marks == "left" else ()):
            sg = -1.0 if side == "L" else 1.0
            edge = xl if side == "L" else xr
            a = edge + sg * MARK_LINE[0]
            b = edge + sg * MARK_LINE[1]
            key = f"lvl:{side}:{i}"
            pc.line(key + "#l", (a, y), (b, y), 0.25, follow=True)
            tx_ = edge + sg * MARK_TRI
            tri = [(tx_, y), (tx_ - TRI_W / 2, y - TRI_H),
                   (tx_ + TRI_W / 2, y - TRI_H)]
            for j in range(3):
                pc.line(f"{key}#t{j}", tri[j], tri[(j + 1) % 3], 0.25,
                        follow=True)
            al = "right" if side == "L" else "left"
            vx = tx_ - TRI_W if side == "L" else tx_ + TRI_W
            pc.text(key + "#v", vx, y - mm_l["mm"] * 1.25 - 0.4, val,
                    "level", al, follow=True)
            pc.text(key + "#n", a if side == "R" else a, y + 0.6, name,
                    "level", "right" if side == "L" else "left",
                    follow=True)

    # --- the heights: floor to floor, and overall --------------------------------------
    if show.get("sec_heights", True):
        zs = sorted({round(z, 4) for z, _lid, _n in sts})
        # what each stop is (C0, PLANO_COTAS_FOLHAS.md): its level, «top»
        # for the last floor's top — the key of a height says what it
        # measures, not its place in the row
        znm: dict = {}
        for z, lid, _n in sts:
            # (``kz``, never ``k``: k is this sheet's scale factor)
            kz, nm = round(z, 4), str(lid) if lid is not None else "top"
            znm[kz] = min(znm.get(kz, nm), nm)
        # a roof's ridge over the last floor (not a parapet's few cm: its
        # stop sat on the roof mark's figure — the corporate building, 0,30)
        if G["box"]["z1"] > zs[-1] + TOP_STOP_M:
            zs.append(round(G["box"]["z1"], 4))
            znm[zs[-1]] = "ridge"
        dmm = DS.text(style, "dim")["mm"]
        rows = [(1, list(zip(zs, zs[1:])))] if len(zs) > 2 else []
        rows.append((2, [(zs[0], zs[-1])]))
        for row, spans in rows:
            off = DIM_ROWS[row - 1]
            for j, (za, zb) in enumerate(spans):
                pa, pb = (xl, Y(za)), (xl, Y(zb))
                label = DS.length(zb - za, style)
                ref = "total" if row == 2 else \
                    f"{znm.get(za, f'@{za:.2f}')}~{znm.get(zb, f'@{zb:.2f}')}"
                pc.items.append({
                    "kind": "dim", "key": f"dim:h:{row}:{ref}",
                    "alias": f"dim:h:{row}:{j}", "run": f"dim:h:{row}",
                    "a": [tx, ty, za], "b": [tx, ty, zb], "pa": pa, "pb": pb,
                    "off": off, "out": (-1.0, 0.0), "mm": dmm,
                    "label": label,
                    "short": abs(pb[1] - pa[1]) < PS._tw(label, dmm) + 1.0,
                    "color": dimc, "pen": pens["dim"]})

    # --- the openings' heights on the right, their widths below (C3,
    # PLANO_COTAS_FOLHAS.md — the Pro's): per level, one chain for each
    # set of heights (floor — sill — head — the floor above; a section: the
    # cut slab's underside too); an elevation: the widths under it
    oh_on, ow_on = opening_dims_on(style, sheet)
    if oh_on or ow_on:
        got = opening_marks(doc, elevations, G, info)
        dmm = DS.text(style, "dim")["mm"]

        def at(v, z):                           # «along r», z → the model
            return [tx + rx * (v - m), ty + ry * (v - m), z]
        col0 = OPEN_COL[0] if marks == "both" else OPEN_COL[2]
        for g in got["groups"] if oh_on else ():
            x = xr + col0 + OPEN_COL[1] * g["col"] - OPEN_TICK
            run = f"dim:oh:{g['lid']}:{g['ref']}"
            for (za, na), (zb, nb) in zip(g["stops"], g["stops"][1:]):
                label = DS.length(zb - za, style)
                pa, pb = (x, Y(za)), (x, Y(zb))
                pc.items.append({
                    "kind": "dim", "key": f"{run}:{na}~{nb}", "run": run,
                    "a": at(G["hi"], za), "b": at(G["hi"], zb),
                    "pa": pa, "pb": pb, "off": OPEN_TICK, "out": (1.0, 0.0),
                    "mm": dmm, "label": label,
                    "short": abs(pb[1] - pa[1]) < PS._tw(label, dmm) + 1.0,
                    "color": dimc, "pen": pens["dim"]})
        stops_w = got["widths"] if ow_on else []
        if len(stops_w) > 2:
            # under the ground floor's ±0,00 when the terrain is drawn (the
            # earth below it is blank — its outline further down crossed
            # the rows); without it, under the lowest point
            zb_ = max(ground, G["box"]["z0"]) if sheet.get("terrain", True) \
                else G["box"]["z0"]
            yb = Y(zb_)
            rows = [(1, list(zip(stops_w, stops_w[1:]))),
                    (2, [(stops_w[0], stops_w[-1])])]
            for row, spans in rows:
                for (va, na), (vb, nb) in spans:
                    label = DS.length(vb - va, style)
                    pa, pb = (X(va), yb), (X(vb), yb)
                    key = "total" if row == 2 else f"{na}~{nb}"
                    pc.items.append({
                        "kind": "dim", "key": f"dim:ow:{row}:{key}",
                        "run": f"dim:ow:{row}", "a": at(va, zb_),
                        "b": at(vb, zb_), "pa": pa, "pb": pb,
                        "off": WIDTH_ROWS[row - 1], "out": (0.0, 1.0),
                        "mm": dmm, "label": label,
                        "short": abs(pb[0] - pa[0]) < PS._tw(label, dmm) + 1.0,
                        "color": dimc, "pen": pens["dim"]})

    # --- the ground line (the terrain off: the ground floor's ±0,00) -------------------
    if not sheet.get("terrain", True):
        y = Y(ground)
        pc.line("ground", (xl - 8.0, y), (xr + 8.0, y), pens["cut"],
                follow=True)

    # --- the cut rooms' names ------------------------------------------------------------
    rooms = []
    if sheet.get("kind") == "section" and show.get("sec_rooms", True):
        rooms = cut_rooms(doc, elevations, G)
        for r in rooms:
            px, py = X(r["along"]), Y(r["z"])
            pc.text(f"room:{r['key']}", px, py, r["name"], "room", "center",
                    follow=True)

    # --- the title, the side column ---------------------------------------------------------
    PS.title_strip(pc, L, sheet, index, n,
                   f"{W_['scale']} {DS.scale_text(n)}")
    sx0, sy0, sx1, sy1 = L["side"]
    pc.rect("side:frame", sx0, sy0, sx1, sy1, 0.5)
    y = sy0 + 6.0
    if show.get("key_plan", True):
        y = key_plan(pc, doc, G, sheet, sx0 + 6.0, y, sx1 - sx0 - 12.0)
    if show.get("levels_key", True):
        y = PS.levels_key(pc, doc, info, ground, [], sx0 + 6.0, y) + 4.0
    if sheet.get("kind") == "section":
        y = WS.legend(pc, doc, sheet["levels"], sx0 + 6.0, y,
                      sx1 - sx0 - 12.0)
    cy0 = sy1 - PS.title_block_mm(style)
    if show.get("notes", True):
        PS.notes(pc, sx0, sx1, y + 2.0, cy0,
                 style.get("notes_section") or W_["notes_section"])
    PS.title_block(pc, doc, L, sheet, n, index, total, today)
    return {"paper": paper, "scale": n, "fits": ok, "page": L["page"],
            "layout": L, "view": view, "items": pc.items, "tags": {},
            "types": [], "rooms": [], "cut_rooms": rooms, "boxes": pc.boxes,
            "anchors": anchors_of(doc, elevations, G, info, sts, X, Y, xl,
                                  xr, n, got if (oh_on or ow_on) else None),
            "extent": (xl, Y(G["zhi"]), xr, Y(G["zlo"]))}


def anchors_of(doc, elevations, G, info, sts, X, Y, xl, xr, n,
               got=None) -> dict:
    """The lines his own dimensions may be tied to on a section or an
    elevation (C4, the Pro's), on the page: {"l": {name: ("h", y, x0, x1)
    | ("v", x, y0, y1)}} — each level's line (as long as its marks reach),
    the ridge, and each opening seen or cut: its sill and head across it,
    its two sides up it; an elevation: the building's two ends."""
    from . import edition
    out: dict = {"p": {}, "l": {}, "scale": n}
    if edition.lite():
        return out
    lines = out["l"]
    reach = MARK_LINE[1]
    for z, lid, _nm in sts:
        lines[f"lvl:{lid if lid is not None else 'top'}"] = (
            "h", round(Y(z), 4), round(xl - reach, 4), round(xr + reach, 4))
    if G["box"]["z1"] > max(z for z, _l, _n in sts) + TOP_STOP_M:
        lines["ridge"] = ("h", round(Y(G["box"]["z1"]), 4), round(xl, 4),
                          round(xr, 4))
    if not G["plane"]:
        for nm, x in (("end:lo", xl), ("end:hi", xr)):
            lines[nm] = ("v", round(x, 4), round(Y(G["zhi"]), 4),
                         round(Y(G["zlo"]), 4))
    try:
        got = got or opening_marks(doc, elevations, G, info)
    except Exception:  # noqa: BLE001 — the levels are still known
        return out
    for s in got.get("seen") or []:
        x0, x1 = X(s["v"][0]), X(s["v"][-1])
        if abs(x1 - x0) < 2.0:                # a cut one: seen edge-on
            x0, x1 = x0 - 1.0, x1 + 1.0
        for part, z in (("sill", s["zs"]), ("head", s["zh"])):
            lines[f"o:{s['id']}:{part}"] = ("h", round(Y(z), 4),
                                           round(min(x0, x1), 4),
                                           round(max(x0, x1), 4))
        if not G["plane"]:
            for side, v in (("lo", s["v"][0]), ("hi", s["v"][-1])):
                lines[f"o:{s['id']}:{side}"] = ("v", round(X(v), 4),
                                                round(Y(s["zh"]), 4),
                                                round(Y(s["zs"]), 4))
    return out


def cut_rooms(doc: dict, elevations, G: dict) -> list[dict]:
    """The NAMED rooms the section line crosses (more than a metre of
    it): [{"key", "name", "along", "z"}] — the name at the crossing's
    middle, 40 % up the floor's height."""
    from shapely.geometry import LineString

    from . import spaces
    line = G["line"]
    if not line:
        return []
    seg = LineString([tuple(line["a"]), tuple(line["b"])])
    info = S.levels_info(doc, elevations)
    rx, ry = G["right"]
    out = []
    for lv in doc.get("levels") or []:
        li = info[lv["id"]]
        for i, r in enumerate(spaces.of_level(doc, lv["id"])):
            if not r.get("rec"):
                continue
            cut = seg.intersection(r["poly"])
            if cut.is_empty or cut.length < 1.0:
                continue
            # the longest piece of the crossing
            piece = max(getattr(cut, "geoms", [cut]), key=lambda g: g.length)
            c = piece.interpolate(0.5, normalized=True)
            rid = r["rec"].get("id") or f"{lv['id']}:{i}"
            out.append({"key": rid, "name": r["name"],
                        "along": c.x * rx + c.y * ry,
                        "z": li["z0"] + li["height"] * 0.4})
    return out


def key_plan(pc, doc: dict, G: dict, sheet: dict, x: float, y: float,
             w: float) -> float:
    """A small plan of the ground floor's walls in the side column with the
    section line (dashed, its letters, the look) or the side looked at
    (an arrow). Returns the y under it."""
    from shapely.ops import unary_union

    W_ = DS.words(pc.style)
    pc.text("key:head", x, y, W_["key_plan"], "heading")
    y += 7.0
    lv = next((lv for lv in doc.get("levels") or []
               if lv.get("kind") == "ground"), None)
    ids = [lv["id"]] if lv else []
    walls = [wl for wl in doc.get("walls") or [] if wl.get("level") in ids] \
        or list(doc.get("walls") or [])
    try:
        U = unary_union(PS._pieces(walls)).simplify(0.05)
    except Exception:  # noqa: BLE001 — no plan to show
        return y
    if U.is_empty:
        return y
    b = G["box"]
    X0, Y0, X1, Y1 = b["x0"], b["y0"], b["x1"], b["y1"]
    pad = 0.12 * max(X1 - X0, Y1 - Y0)
    X0, Y0, X1, Y1 = X0 - pad, Y0 - pad, X1 + pad, Y1 + pad
    s = min(w / (X1 - X0), KEY_H / (Y1 - Y0))
    ox = x + (w - (X1 - X0) * s) / 2
    oy = y + (KEY_H - (Y1 - Y0) * s) / 2

    def P(p):
        return (ox + (p[0] - X0) * s, oy + (Y1 - p[1]) * s)
    j = 0
    for g in getattr(U, "geoms", [U]):
        for ring in [g.exterior] + list(g.interiors):
            pts = list(ring.coords)
            for a, c in zip(pts, pts[1:]):
                pc.line(f"key:w:{j}", P(a), P(c), 0.25)
                j += 1
    lx, ly = G["look"]
    if G["line"]:
        ln = G["line"]
        a, c = P(ln["a"]), P(ln["b"])
        dashed(pc, "key:cut", a, c, 0.5)
        for e, end in (("a", a), ("b", c)):
            # the look: a short stroke from each end, the letter beside it
            tip = (end[0] + lx * 4.0, end[1] - ly * 4.0)
            pc.line(f"key:look:{e}", end, tip, 0.5)
            pc.text(f"key:sym:{e}", tip[0] + lx * 2.5, tip[1] - ly * 2.5 - 1.5,
                    ln["symbol"], "label", "center", box=False)
    else:
        # the side looked at: an arrow from outside toward the building
        cx, cy = (b["x0"] + b["x1"]) / 2, (b["y0"] + b["y1"]) / 2
        far = (cx - lx * ((b["x1"] - b["x0"]) / 2 + pad * 0.9),
               cy - ly * ((b["y1"] - b["y0"]) / 2 + pad * 0.9))
        tip = P(far)
        tail = (tip[0] - lx * 6.0, tip[1] + ly * 6.0)
        pc.line("key:arrow", tail, tip, 0.5)
        for j2, sg in enumerate((1, -1)):
            hx = tip[0] - lx * 2.0 + sg * ly * 1.2
            hy = tip[1] + ly * 2.0 + sg * lx * 1.2
            pc.line(f"key:head:{j2}", tip, (hx, hy), 0.5)
    return y + KEY_H + 6.0


def dashed(pc, key: str, a, b, pen) -> None:
    """A dashed line as short strokes (the composer's lines are solid)."""
    L = math.dist(a, b)
    if L < 1e-6:
        return
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    t, i = 0.0, 0
    while t < L:
        e = min(t + DASH[0], L)
        pc.line(f"{key}:{i}", (a[0] + ux * t, a[1] + uy * t),
                (a[0] + ux * e, a[1] + uy * e), pen)
        t = e + DASH[1]
        i += 1


def spec_of(built: dict) -> dict:
    """The old ``docs`` drawing spec of a built sheet (the DXF writer
    reads it): target, look, cut."""
    v = built["view"]
    return {"kind": v["kind"], "view": "custom", "look": list(v["look"]),
            "target": list(v["target"]), "plane": v["plane"]}
