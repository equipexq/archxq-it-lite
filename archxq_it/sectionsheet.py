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
from . import plansheet as PS
from . import structure as S

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
KEY_H = 52.0                      # the key plan's box height (mm)
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
def fits(ext_w: float, ext_h: float, paper: str, n: float,
         style: dict) -> bool:
    x0, y0, x1, y1 = PS.layout(paper, style)["area"]
    return ext_w * 1000.0 / n + RESERVE_L + RESERVE_R <= x1 - x0 and \
        ext_h * 1000.0 / n + 2 * RESERVE_V <= y1 - y0


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
                             sheet.get("scale", "auto") or "auto", fits=fits)
    L = PS.layout(paper, style)
    ax0, ay0, ax1, ay1 = L["area"]
    k = 1000.0 / n
    # the building sits between the reserves; the frame is the whole area
    fcx = ax0 + RESERVE_L + (ax1 - ax0 - RESERVE_L - RESERVE_R) / 2
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
        # a roof's ridge over the last floor (not a parapet's few cm: its
        # stop sat on the roof mark's figure — the corporate building, 0,30)
        if G["box"]["z1"] > zs[-1] + TOP_STOP_M:
            zs.append(round(G["box"]["z1"], 4))
        dmm = DS.text(style, "dim")["mm"]
        rows = [(1, list(zip(zs, zs[1:])))] if len(zs) > 2 else []
        rows.append((2, [(zs[0], zs[-1])]))
        for row, spans in rows:
            off = DIM_ROWS[row - 1]
            for j, (za, zb) in enumerate(spans):
                pa, pb = (xl, Y(za)), (xl, Y(zb))
                label = DS.num(zb - za, style)
                pc.items.append({
                    "kind": "dim", "key": f"dim:h:{row}:{j}",
                    "a": [tx, ty, za], "b": [tx, ty, zb], "pa": pa, "pb": pb,
                    "off": off, "out": (-1.0, 0.0), "mm": dmm,
                    "label": label,
                    "short": abs(pb[1] - pa[1]) < PS._tw(label, dmm) + 1.0,
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
    PS.title_strip(pc, L, sheet, index, n, f"{W_['scale']} 1:{n}")
    sx0, sy0, sx1, sy1 = L["side"]
    pc.rect("side:frame", sx0, sy0, sx1, sy1, 0.5)
    y = sy0 + 6.0
    if show.get("key_plan", True):
        y = key_plan(pc, doc, G, sheet, sx0 + 6.0, y, sx1 - sx0 - 12.0)
    if show.get("levels_key", True):
        y = PS.levels_key(pc, doc, info, ground, [], sx0 + 6.0, y) + 4.0
    cy0 = sy1 - PS.TITLE_BLOCK_MM
    if show.get("notes", True):
        PS.notes(pc, sx0, sx1, y + 2.0, cy0,
                 style.get("notes_section") or W_["notes_section"])
    PS.title_block(pc, doc, L, sheet, n, index, total, today)
    return {"paper": paper, "scale": n, "fits": ok, "page": L["page"],
            "layout": L, "view": view, "items": pc.items, "tags": {},
            "types": [], "rooms": [], "cut_rooms": rooms, "boxes": pc.boxes}


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
