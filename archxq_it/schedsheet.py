# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The AREA SCHEDULE sheet (A-001) of the documentation studio — the one
the earlier «Make» drew, now with the plans' finish (2026-10-23: «Update
all» replaced the old sheets and the schedule was left with none).

``make(doc, elevations, sheet, style)`` gives the sheet as NEUTRAL pieces in
paper millimetres, each with a STABLE key (``hostsheet`` keeps what the
architect moved, hid or retyped). No view: a table — each level as the
building stands (net area, gross area, rooms), the building's totals —
then every level's rooms with their areas, in columns; the side column with
notes and the title block.
"""
from __future__ import annotations

import datetime

from . import docstyle as DS
from . import plansheet as PS
from . import structure as S

ROW_MM = 5.4                       # the main table's rows
ROOM_ROW_MM = 4.4                  # a room's line in the lists
COLS = (0.0, 64.0, 92.0, 128.0, 164.0)     # level · elev · net · gross · n
TABLE_W = 186.0
LIST_W = 78.0                      # a column of the rooms' lists
LIST_GAP = 10.0


def levels_data(doc: dict, elevations) -> list[dict]:
    """Each level with walls, as the building stands (the top first):
    [{"id", "name", "z", "net", "gross", "rooms"}]."""
    from . import spaces
    info = S.levels_info(doc, elevations)
    ground = float((doc.get("project") or {}).get("ground_level", 0.0) or 0.0)
    out = []
    for lv in reversed(doc.get("levels") or []):
        walls = [w for w in doc.get("walls") or [] if w["level"] == lv["id"]]
        if not walls:
            continue
        rooms = spaces.of_level(doc, lv["id"])
        out.append({"id": lv["id"], "name": lv["name"],
                    "z": info[lv["id"]]["z0"] - ground,
                    "net": sum(r["area"] for r in rooms),
                    "gross": gross(walls, rooms), "rooms": rooms})
    return out


def gross(walls: list[dict], rooms: list[dict]) -> float:
    """The level's gross area: the walls' outline AND the rooms closed by
    low walls or guards beyond it (a balcony) — the walls alone gave the
    corporate building's Level 2 a net area over its gross, 2026-10-23."""
    from shapely.ops import unary_union
    from . import spaces
    try:
        return unary_union(PS._pieces(walls)
                           + [r["poly"] for r in rooms]).area
    except Exception:  # noqa: BLE001 — the walls' own
        return spaces.gross(walls)


def _lists_height(data: list[dict]) -> list[float]:
    """Each level's rooms block height (mm)."""
    return [7.0 + ROOM_ROW_MM * (len(d["rooms"]) + 1) + 6.0 for d in data]


def pour(heights: list[float], ncols: int) -> list[int]:
    """Each block's column: in order (the levels as the building stands),
    the columns about even — one long list beside many short ones, not
    all in one column (his first schedule ran down one side, 2026-10-23)."""
    if not heights:
        return []
    ncols = max(1, min(ncols, len(heights)))
    target = max(max(heights), sum(heights) / ncols)
    out, col, used = [], 0, 0.0
    for h in heights:
        if used and used + h > target + 1e-6 and col < ncols - 1:
            col, used = col + 1, 0.0
        out.append(col)
        used += h
    return out


def _fit(heights: list[float], width: float, avail: float) -> bool:
    ncols = int((width + LIST_GAP) // (LIST_W + LIST_GAP))
    if ncols < 1:
        return False
    cols = pour(heights, ncols)
    tall = [0.0] * (max(cols) + 1)
    for h, c in zip(heights, cols):
        tall[c] += h
    return max(tall) <= avail


def _top(y0: float, data: list[dict]) -> float:
    """Where the rooms' lists start: under the table."""
    return y0 + 4.0 + 10.0 + 6.4 + ROW_MM * (len(data) + 1) + 10.6 + 9.0


def choose(data: list[dict], style: dict, paper="auto") -> tuple[str, bool]:
    """(paper, fits): the smallest paper that holds the table and the rooms'
    lists (the one fixed, if he fixed one)."""
    papers = [p for p in style["sheet"]["papers"] if p in PS.PAPERS_MM]
    want = [paper] if paper != "auto" else papers
    rooms = style["show"].get("sched_rooms", True)
    hs = _lists_height(data) if rooms else []
    for p in want:
        x0, y0, x1, y1 = PS.layout(p, style)["area"]
        top = _top(y0, data)
        if top > y1:
            continue
        if not hs or _fit(hs, x1 - x0 - 8.0, y1 - top - 4.0):
            return p, True
    return want[-1], False


def make(doc: dict, elevations, sheet: dict, style: dict,
         today: datetime.date | None = None, total: int = 1,
         index: int = 1) -> dict:
    """The schedule as neutral pieces: {"paper", "scale" (None), "fits",
    "page", "layout", "view" (None), "items", "tags", "types", "rooms",
    "boxes", "levels"}."""
    W_ = DS.words(style)
    data = levels_data(doc, elevations)
    paper, ok = choose(data, style, sheet.get("paper", "auto") or "auto")
    L = PS.layout(paper, style)
    pc = PS.Pieces(style)
    mute = style["colors"]["mute"]
    bx0, by0, bx1, by1 = L["border"]
    pc.rect("border", bx0, by0, bx1, by1, "border")
    ax0, ay0, ax1, ay1 = L["area"]
    x, y = ax0 + 4.0, ay0 + 4.0
    num = lambda v: DS.area_cell(v, style)                  # noqa: E731

    # --- the table: one row per level, the totals --------------------------------
    pc.text("t:head", x, y, W_["area_schedule"], "heading")
    y += 10.0
    heads = ("col_level", "col_elev", "col_net", "col_gross", "col_rooms")
    for c, h in zip(COLS, heads):
        right = h != "col_level"
        pc.text(f"t:th:{h}", x + c + (26.0 if right else 0.0), y, W_[h],
                "label", "right" if right else "left", color=mute)
    y += 5.0
    pc.line("t:rule:head", (x, y), (x + TABLE_W, y), 0.35)
    y += 1.4
    for i, d in enumerate(data):
        vals = (d["name"], PS.level_text(d["z"], style), num(d["net"]),
                num(d["gross"]), str(len(d["rooms"])))
        for j, (c, v) in enumerate(zip(COLS, vals)):
            pc.text(f"t:{d['id']}:{j}", x + c + (26.0 if j else 0.0), y, v,
                    "table", "right" if j else "left")
        y += ROW_MM
        pc.line(f"t:rule:{i}", (x, y - 1.2), (x + TABLE_W, y - 1.2), 0.13)
    y += 0.6
    pc.line("t:rule:total", (x, y - 1.2), (x + TABLE_W, y - 1.2), 0.35)
    tot = (W_["total"], "", num(sum(d["net"] for d in data)),
           num(sum(d["gross"] for d in data)),
           str(sum(len(d["rooms"]) for d in data)))
    for j, (c, v) in enumerate(zip(COLS, tot)):
        if v:
            pc.text(f"t:total:{j}", x + c + (26.0 if j else 0.0), y, v,
                    "label", "right" if j else "left")
    y += ROW_MM + 10.0

    # --- every level's rooms, in columns ----------------------------------------------
    rooms_all = []
    if style["show"].get("sched_rooms", True) and data:
        pc.text("r:head", x, y, W_["rooms_by_level"], "heading")
        y += 9.0
        top = y
        hs = _lists_height(data)
        ncols = int((ax1 - ax0 - 8.0 + LIST_GAP) // (LIST_W + LIST_GAP))
        cols = pour(hs, ncols)
        last = -1
        for d, col in zip(data, cols):
            if col != last:
                cx, y, last = x + col * (LIST_W + LIST_GAP), top, col
            pc.text(f"r:{d['id']}:h", cx, y, f"{d['name']}   "
                    f"{PS.level_text(d['z'], style)}", "label")
            y += 5.6
            for k, r in enumerate(d["rooms"]):
                rid = (r.get("rec") or {}).get("id") or f"{k}"
                pc.text(f"r:{d['id']}:{rid}:n", cx + 2.0, y, r["name"],
                        "table")
                pc.text(f"r:{d['id']}:{rid}:a", cx + LIST_W, y,
                        num(r["area"]), "table", "right")
                y += ROOM_ROW_MM
            pc.line(f"r:{d['id']}:rule", (cx, y + 0.2), (cx + LIST_W, y + 0.2),
                    0.18)
            y += 1.0
            pc.text(f"r:{d['id']}:net", cx + LIST_W, y, num(d["net"]),
                    "label", "right")
            y += ROOM_ROW_MM + 6.0
            rooms_all += d["rooms"]
    else:
        rooms_all = [r for d in data for r in d["rooms"]]

    # --- the title, the side column ---------------------------------------------------
    _title(pc, L, sheet, index)
    sx0, sy0, sx1, sy1 = L["side"]
    pc.rect("side:frame", sx0, sy0, sx1, sy1, 0.5)
    cy0 = sy1 - PS.TITLE_BLOCK_MM
    if style["show"].get("notes", True):
        PS.notes(pc, sx0, sx1, sy0 + 6.0, cy0,
                 style.get("notes_schedule") or W_["notes_schedule"])
    PS.title_block(pc, doc, L, sheet, None, index, total, today)
    return {"paper": paper, "scale": None, "fits": ok, "page": L["page"],
            "layout": L, "view": None, "items": pc.items, "tags": {},
            "types": [], "rooms": rooms_all, "boxes": pc.boxes,
            "levels": data}


def _title(pc, L: dict, sheet: dict, index: int) -> None:
    """The NBR title strip without a scale (a table has none)."""
    style = pc.style
    tx0, ty0, _tx1, _ty1 = L["title"]
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
            (bxc + bub + 6 + max(160.0, PS._tw(sheet["title"], tt_["mm"])
                                 + 10), byc + 1.2), 0.5)
