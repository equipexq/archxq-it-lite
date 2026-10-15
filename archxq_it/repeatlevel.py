"""REPEAT a level upwards (his ask, 2026-10-11: draw one floor of the tower,
then replicate it up — «it's very quick»).

``repeat(doc, level_id, n)``: ``n`` new levels right above the level, as
high as it, each one holding a copy of what stands on it — its walls (a
curtain wall too) with their doors and windows, its columns, beams and
drawn slabs, its rooms' names, the materials picked for them — and its
stairs / ramps going UP to the next level (each copy to the level over
it; the original now reaches the first new one). Levels that were above
it go up by as much. Not copied: flights joining other levels, an
excavation's slabs, footings, roofs (the top only).

Pure data — no Qt; ``ui.repeat_level`` stores it (one Ctrl+Z).
"""
from __future__ import annotations

import copy

from . import model

#: the structure copied with its level
COPIED = ("column", "beam", "slab")


def repeat(doc: dict, level_id: str, n: int) -> tuple[dict, list[str], list]:
    """(the new document, the new levels' ids, notes)."""
    levels = doc["levels"]
    ids = [r["id"] for r in levels]
    if level_id not in ids or n < 1:
        return doc, [], []
    i = ids.index(level_id)
    new_levels = list(levels)
    for k in range(n):
        new_levels = model.insert_level(new_levels, i + k, True,
                                        levels[i]["height"])
    new_ids = [r["id"] for r in new_levels if r["id"] not in ids]
    above = ids[i + 1] if i + 1 < len(ids) else None
    targets = [(nid, new_ids[k + 1] if k + 1 < len(new_ids) else above)
               for k, nid in enumerate(new_ids)]
    out, notes = _copy(doc, level_id, targets, new_levels,
                       relink=new_ids[0] if new_ids else None)
    return out, new_ids, notes


def copy_to(doc: dict, level_id: str, target: str) -> tuple[dict, list]:
    """(the new document, notes): what stands on ``level_id`` copied onto
    the EXISTING level ``target`` — added to what is there (his ask,
    2026-10-12: the architect picks the level, one at a time — his
    alternating floors). A stair up from it goes up from the target to the
    level over the target."""
    ids = [r["id"] for r in doc["levels"]]
    if level_id not in ids or target not in ids or target == level_id:
        return doc, []
    j = ids.index(target)
    nxt = ids[j + 1] if j + 1 < len(ids) else None
    # what the target ALREADY has is left alone (his ask, 2026-10-14: his
    # floors differ — the terrace left on one, right on the next — so he
    # copies to a level, and copies again to fill in what was forgotten,
    # with no doubles)
    return _copy(doc, level_id, [(target, nxt)], doc["levels"],
                 skip_existing=True)


#: m — «the same place»: within this, an element is already there
SAME = 0.02


def _near(p, q) -> bool:
    return abs(float(p[0]) - float(q[0])) <= SAME \
        and abs(float(p[1]) - float(q[1])) <= SAME


def _same_wall(a: dict, b: dict) -> bool | None:
    """Is ``b`` the wall ``a`` (the same place, kind, thickness, type)?
    None = no; True = yes, drawn the same way; False = yes, drawn the
    other way round (its openings' positions run from the other end)."""
    if a.get("kind", "line") != b.get("kind", "line") \
            or abs(float(a["t"]) - float(b["t"])) > 0.005 \
            or bool(a.get("cw")) != bool(b.get("cw")):
        return None
    kind = a.get("kind", "line")
    if kind == "circle":
        return True if _near(a["c"], b["c"]) \
            and abs(float(a["r"]) - float(b["r"])) <= SAME else None
    if kind == "arc" and not _near(a["m"], b["m"]):
        return None
    if _near(a["a"], b["a"]) and _near(a["b"], b["b"]):
        return True
    if _near(a["a"], b["b"]) and _near(a["b"], b["a"]):
        return False
    return None


def _same_element(a: dict, b: dict) -> bool:
    """A column / beam / slab / stair / ramp already in that place."""
    if a.get("type") != b.get("type"):
        return False
    t = a.get("type")
    try:
        if t == "column":
            return _near((a["x"], a["y"]), (b["x"], b["y"]))
        if t == "beam":
            return (_near(a["a"], b["a"]) and _near(a["b"], b["b"])) or \
                (_near(a["a"], b["b"]) and _near(a["b"], b["a"]))
        if t == "slab":
            ca, cb = a["corners"], b["corners"]
            return len(ca) == len(cb) and all(any(_near(p, q) for q in cb)
                                              for p in ca)
        if t in ("stair", "ramp"):
            return _near((a["x"], a["y"]), (b["x"], b["y"])) \
                and abs(float(a.get("angle", 0)) - float(b.get("angle", 0))) \
                < 1.0
    except (KeyError, TypeError, IndexError):
        return False
    return False


def _copy(doc: dict, level_id: str, targets: list, new_levels: list,
          relink: str | None = None,
          skip_existing: bool = False) -> tuple[dict, list]:
    """Copy ``level_id``'s contents onto each (level, the level over it)
    of ``targets``; ``relink``: the original's flights going UP now reach
    that level (new levels were put in between). ``skip_existing``: what
    the target already has in the same place is not copied again (a wall
    there gets only the openings it lacks)."""
    ids = [r["id"] for r in doc["levels"]]
    i = ids.index(level_id)
    walls = list(doc.get("walls") or [])
    ops = list(doc.get("openings") or [])
    st = list(doc.get("structure") or [])
    rooms = list(doc.get("rooms") or [])
    mats = copy.deepcopy((doc.get("materials") or {}).get("el") or {})
    src_w = [w for w in walls if w["level"] == level_id]
    src_ids = {w["id"] for w in src_w}
    src_o = [o for o in ops if o["wall"] in src_ids]
    src_s = [e for e in st if e["level"] == level_id
             and e.get("type") in COPIED and not e.get("auto")]
    # stairs / ramps going from this level UP to the next (or to its own
    # top): copied too, each copy from its level to the one over it (his
    # tower's two stairs, 2026-10-12) — others join given levels: they stay
    above = ids[i + 1] if i + 1 < len(ids) else None
    TOP = "top:"

    def role(end):
        if end == level_id:
            return "self"
        if above is not None and end == above:
            return "up"
        if end == TOP + level_id:
            return "top"
        return None
    flights, skipped = [], 0
    for e in st:
        if e.get("type") not in ("stair", "ramp") or e["level"] != level_id:
            continue
        ends = (role(e.get("from") or e.get("level")), role(e.get("to")))
        if e.get("start") != "terrain" and None not in ends \
                and "self" in ends:
            flights.append((e, ends))
        else:
            skipped += 1
    # the original now reaches the FIRST new level (the old one above went
    # up by n storeys)
    if relink and flights:
        fixed = {}
        for e, (a, b) in flights:
            r = dict(e)
            if a == "up":
                r["from"] = relink
            if b == "up":
                r["to"] = relink
            fixed[e["id"]] = r
        st = [fixed.get(e["id"], e) for e in st]
        flights = [(fixed[e["id"]], ends) for e, ends in flights]
    src_r = [r for r in rooms if r.get("level") == level_id]

    def bare(r):
        return {k: v for k, v in copy.deepcopy(r).items()
                if k not in ("id", "name")}
    import math
    there = 0                       # already in the target: not copied again
    for nid, nxt in targets:
        have_w = [w for w in walls if w["level"] == nid] \
            if skip_existing else []
        have_s = [e for e in st if e.get("level") == nid] \
            if skip_existing else []
        have_r = [r for r in rooms if r.get("level") == nid] \
            if skip_existing else []
        made_f, from_f = [], []
        for e, (a, b) in flights:
            if any(_same_element(e, h) for h in have_s):
                there += 1
                continue
            def where(r, nid=nid, nxt=nxt):
                if r == "self":
                    return nid
                if r == "top" or nxt is None:
                    return TOP + nid
                return nxt
            made_f.append(dict(bare(e), level=nid, **{"from": where(a),
                                                      "to": where(b)}))
            from_f.append(e)
        made_fl = model.new_elements(st, made_f)
        st += made_fl
        for old, new in zip(from_f, made_fl):
            if old["id"] in mats:
                mats[new["id"]] = copy.deepcopy(mats[old["id"]])
        # walls: one already in its place is kept — it gets only the
        # openings it lacks (positions turned if it was drawn the other way)
        wmap, flip, new_src = {}, {}, []
        for w in src_w:
            hit = next(((h, s) for h in have_w
                        for s in [_same_wall(w, h)] if s is not None), None)
            if hit is None:
                new_src.append(w)
            else:
                there += 1
                wmap[w["id"]], flip[w["id"]] = hit[0]["id"], not hit[1]
        made_w = model.new_walls(walls, [dict(bare(w), level=nid)
                                         for w in new_src])
        walls += made_w
        for w, m in zip(new_src, made_w):
            wmap[w["id"]] = m["id"]
        by_id_w = {w["id"]: w for w in src_w}
        add_o = []
        for o in src_o:
            rec = dict(bare(o), wall=wmap[o["wall"]])
            if o["wall"] in flip:            # into a wall that was there
                w = by_id_w[o["wall"]]
                if flip[o["wall"]] and w.get("kind", "line") == "line":
                    L = math.dist(w["a"], w["b"])
                    rec["pos"] = round(L - float(o["pos"]), 4)
                if any(x["wall"] == rec["wall"] and x["kind"] == o["kind"]
                       and abs(float(x["pos"]) - float(rec["pos"])) <= SAME
                       and abs(float(x["w"]) - float(o["w"])) <= SAME
                       for x in ops):
                    there += 1
                    continue
            add_o.append(rec)
        ops += model.new_openings(ops, add_o)
        new_s = []
        for e in src_s:
            if any(_same_element(e, h) for h in have_s):
                there += 1
            else:
                new_s.append(e)
        made_s = model.new_elements(st, [dict(bare(e), level=nid)
                                         for e in new_s])
        st += made_s
        for r in src_r:
            if any(h.get("name") == r.get("name")
                   and math.hypot(float(h["x"]) - float(r["x"]),
                                  float(h["y"]) - float(r["y"])) < 2.0
                   for h in have_r):
                there += 1
                continue
            # (a room IS its name: kept — bare() dropped it and the copy
            # was thrown away, so rooms were never copied)
            rooms.append(dict(copy.deepcopy(r), id="", level=nid))
        for old, new in list(zip(new_src, made_w)) + list(zip(new_s, made_s)):
            if old["id"] in mats:
                mats[new["id"]] = copy.deepcopy(mats[old["id"]])
    out = dict(doc, levels=new_levels, walls=walls, openings=ops,
               structure=st, rooms=model._rooms(rooms, {r["id"] for r in
                                                       new_levels}))
    if mats:
        out["materials"] = dict(doc.get("materials") or {}, el=mats)
    notes = []
    if there:
        notes.append(f"{there} already there — left as they were")
    if flights:
        notes.append(f"{len(flights)} stair / ramp up to the next level "
                     "copied")
    if skipped:
        notes.append(f"{skipped} stair / ramp not copied (they join other "
                     "levels)")
    return out, notes
