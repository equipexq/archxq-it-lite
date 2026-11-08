# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The CHECKS before a sheet goes out — the algorithm reminds, so the
architect does not have to (his rule, 2026-10-22). Each check says what
it saw and which action puts it right.

Pure: no Qt, no host.
"""
from __future__ import annotations

import copy

from . import docstyle as DS
from . import plansheet as PS

OK, WARN = "ok", "warn"


def unnamed(built: dict) -> list[dict]:
    """The rooms with no name given (still «Room N»)."""
    return [r for r in built["rooms"] if not r.get("rec")]


def near_equal(built: dict) -> int:
    """How many opening sizes differ by only a few cm from another of the
    same type (they are drawn as one type; «Unify» makes them equal)."""
    return sum(t["raw"] - 1 for t in built["types"] if t["raw"] > 1)


def checks(built: dict, style: dict, state: str = "ok") -> list[dict]:
    """[{"code", "level" ok|warn, "n", "action" or None}] in the order
    the studio shows them."""
    out = []
    crowded = built.get("crowded", False)       # (a views sheet: on several)
    out.append({"code": "fits",
                "level": OK if built["fits"] and not crowded else WARN,
                "n": built["scale"],
                "action": "split" if crowded else None if built["fits"]
                else "paper"})
    small = DS.too_small(style)
    out.append({"code": "text_size", "level": WARN if small else OK,
                "n": len(small), "action": "style" if small else None})
    nn = len(unnamed(built))
    out.append({"code": "unnamed", "level": WARN if nn else OK, "n": nn,
                "action": "name_rooms" if nn else None})
    ov = PS.overlaps(built)
    out.append({"code": "overlap", "level": WARN if ov else OK,
                "n": len(ov), "action": "show" if ov else None,
                "pairs": ov})
    ne = near_equal(built)
    out.append({"code": "near_equal", "level": WARN if ne else OK, "n": ne,
                "action": "unify" if ne else None})
    out.append({"code": "state", "level": OK if state == "ok" else WARN,
                "n": 0, "action": None if state == "ok" else "update"})
    return out


ROW_M = 2.0          # rooms whose label points are this close in y: one row


def name_by_pattern(doc: dict, level_ids: list[str], prefix: str,
                    start: int = 1, digits: int = 2, min_area: float = 0.0,
                    max_area: float = 1e9) -> tuple[dict, int]:
    """The UNNAMED rooms of those floors named «PREFIX 01, 02…» in the
    order a plan is read — the top row first, left to right — only those
    whose area is within [min_area, max_area] (the shops, not the WCs).
    Returns (a new doc, how many named); the caller stores it (one
    Ctrl+Z)."""
    import uuid

    from . import spaces
    new = copy.deepcopy(doc)
    prefix = (prefix or "").strip()
    if not prefix:
        return new, 0
    found = []
    for lid in level_ids:
        for r in spaces.of_level(new, lid):
            if r.get("rec") is None and min_area <= r["area"] <= max_area:
                found.append((lid, r))
    found.sort(key=lambda t: (-round(t[1]["at"][1] / ROW_M), t[1]["at"][0]))
    recs = list(new.get("rooms") or [])
    for i, (lid, r) in enumerate(found):
        recs.append({"id": uuid.uuid4().hex[:8], "level": lid,
                     "x": round(float(r["at"][0]), 4),
                     "y": round(float(r["at"][1]), 4),
                     "name": f"{prefix} {start + i:0{digits}d}"})
    new["rooms"] = recs
    return new, len(found)


def unify(doc: dict, level_ids: list[str]) -> tuple[dict, int]:
    """The openings of those floors made EQUAL to their type (the size
    most of the type has): returns (a new doc, how many changed). The
    model changes — the caller stores it as one Ctrl+Z."""
    new = copy.deepcopy(doc)
    walls = {w["id"] for w in new.get("walls") or []
             if w.get("level") in level_ids}
    ops = [o for o in new.get("openings") or [] if o.get("wall") in walls]
    tags, _rows = PS.opening_types(ops)
    by_tag: dict = {}
    for o in ops:
        if o["id"] in tags:             # (a void has no type)
            by_tag.setdefault(tags[o["id"]], []).append(o)
    changed = 0
    for group in by_tag.values():
        sizes: dict = {}
        for o in group:
            key = (round(float(o["w"]), 3), round(float(o["h"]), 3),
                   round(float(o.get("sill", 0.0)), 3))
            sizes[key] = sizes.get(key, 0) + 1
        w, h, s = max(sizes.items(), key=lambda kv: (kv[1], kv[0]))[0]
        for o in group:
            if (round(float(o["w"]), 3), round(float(o["h"]), 3),
                    round(float(o.get("sill", 0.0)), 3)) != (w, h, s):
                o["w"], o["h"], o["sill"] = w, h, s
                changed += 1
    return new, changed
