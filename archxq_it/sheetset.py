# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The SET of sheets — which sheets the project has, in the order a set is
read (the drawings' book: from the lowest floor up, A-101 the lowest), with
their numbers, titles and state.

First delivery (PLANO_DOCUMENTACAO_PLANTAS.md): the floor PLANS. Floors
that are the same (the corporate building's 2nd–5th) become ONE sheet, the
«typical floor» — it can be turned off in the style.

A sheet's record lives in ``doc["docs"]["sheets"]``: what the architect
chose for it (paper, scale, cut, its style changes) and the model's
signature when it was made — so the panel can say «the model changed».

Pure: no Qt, no host.
"""
from __future__ import annotations

import hashlib
import json

from . import docstyle as DS

#: plan geometry rounded to this (m) when floors are compared
SIG_ROUND = 3


def _r(v):
    if isinstance(v, float):
        return round(v, SIG_ROUND)
    if isinstance(v, (list, tuple)):
        return [_r(x) for x in v]
    if isinstance(v, dict):
        return {k: _r(x) for k, x in sorted(v.items())}
    return v


#: keys that name a thing, not its shape (two equal floors differ in them)
_NAMES = {"id", "name", "level", "wall", "to", "owner", "type_id"}
#: a wall's keys the PLAN outline already says (a wall drawn the other way
#: round — a and b swapped, side flipped — is the same wall; seen on the
#: corporate building, 2026-10-22: floors 3 and 4 drawn in reverse)
_WALL_GEOM = {"a", "b", "m", "c", "r", "side", "align"}
#: an opening's keys that depend on which way its wall was drawn
_OPEN_GEOM = {"pos", "swing", "hinge", "flip"}


def _pts(v):
    """A list of points, order-free (a slab's corners from another start
    are the same slab)."""
    if isinstance(v, list) and v and all(
            isinstance(p, (list, tuple)) and len(p) in (2, 3)
            and all(isinstance(x, (int, float)) for x in p) for p in v):
        return sorted(tuple(round(float(x), SIG_ROUND) for x in p) for p in v)
    return _r(v)


def _shape(rec: dict, skip=frozenset()) -> dict:
    return {k: _pts(v) for k, v in rec.items()
            if k not in _NAMES and k not in skip}


def _wall_key(w: dict) -> str:
    from . import walls as W
    try:
        outline = sorted(tuple(round(c, SIG_ROUND) for c in p)
                         for pcs in W.plan([w]).values() for pc in pcs
                         for p in pc["outer"])
    except Exception:  # noqa: BLE001 — a broken wall: its record says it
        outline = _pts([w.get("a"), w.get("b")])
    return json.dumps([outline, _shape(w, _WALL_GEOM)], sort_keys=True)


def _opening_key(o: dict, w: dict) -> str:
    from . import plansheet as PS
    gp = PS._gap(o, w)
    centre = [round(c, SIG_ROUND) for c in gp["c"]] if gp else _r(o.get("pos"))
    return json.dumps([centre, _shape(o, _OPEN_GEOM)], sort_keys=True)


def plan_signature(doc: dict, level_id: str) -> str:
    """What a floor's PLAN is made of, without names or ids: its walls (by
    their outline), their openings (by where they stand) and what stands
    on it (not the roof: it is above the cut). Two floors with the same
    signature draw the same plan."""
    walls = [w for w in doc.get("walls") or [] if w.get("level") == level_id]
    byid = {w["id"]: w for w in walls}
    wkey = {w["id"]: _wall_key(w) for w in walls}
    ops = [_opening_key(o, byid[o["wall"]])
           for o in doc.get("openings") or [] if o.get("wall") in wkey]
    st = [json.dumps(_shape(s), sort_keys=True)
          for s in doc.get("structure") or []
          if s.get("level") == level_id and s.get("type") != "roof"]
    raw = json.dumps([sorted(wkey.values()), sorted(ops), sorted(st)])
    return hashlib.blake2b(raw.encode(), digest_size=10).hexdigest()


def state_signature(doc: dict, level_ids: list[str]) -> str:
    """Everything a plan sheet SHOWS of the model: the floors' plans, the
    rooms' names, the project's fields, the levels' heights — when it
    changes, the sheet is out of date."""
    parts = [plan_signature(doc, l) for l in level_ids]
    rooms = sorted(json.dumps(_r(r), sort_keys=True)
                   for r in doc.get("rooms") or []
                   if r.get("level") in level_ids)
    levels = [_r({k: v for k, v in lv.items() if k in ("name", "height")})
              for lv in doc.get("levels") or []]
    payload = [parts, rooms, _r(doc.get("project") or {}), levels]
    # (a separator changes the rooms' names and areas on the sheet; no
    # separator: the signature of the sheets made before stays the same)
    seps = sorted(json.dumps(_r(x.get("pts")))
                  for x in doc.get("separators") or []
                  if x.get("level") in level_ids)
    if seps:
        payload.append(seps)
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.blake2b(raw.encode(), digest_size=10).hexdigest()


def level_name(lv: dict) -> str:
    return str(lv.get("name") or "")


def plans(doc: dict, style: dict) -> list[dict]:
    """The plan sheets, from the lowest floor up: [{"id", "kind": "plan",
    "levels" [ids], "number", "title", "group"}]. Consecutive floors with
    the same plan → one «typical floor» sheet (style: show.typical)."""
    W = DS.words(style)
    names = style["names"]
    has = {w.get("level") for w in doc.get("walls") or []}
    levels = [lv for lv in doc.get("levels") or [] if lv.get("id") in has]
    runs: list[list[dict]] = []
    typical = bool(style["show"].get("typical", True))
    for lv in levels:
        if typical and runs and plan_signature(doc, runs[-1][-1]["id"]) \
                == plan_signature(doc, lv["id"]) \
                and lv.get("kind") == runs[-1][-1].get("kind") == "floor":
            runs[-1].append(lv)
        else:
            runs.append([lv])
    out = []
    g = int(names.get("plan_group", 1))
    for i, run in enumerate(runs):
        first, last = level_name(run[0]), level_name(run[-1])
        if len(run) > 1:
            title = names["typical_title"].format(
                typical=W["typical"], first=first, last=last)
        else:
            title = names["plan_title"].format(plan=W["plan"], level=first)
        out.append({"id": "plan:" + run[0]["id"], "kind": "plan",
                    "levels": [lv["id"] for lv in run],
                    "number": f"{names['prefix']}{g}{i + 1:02d}",
                    "title": title, "group": "plans"})
    return out


def section_lines(doc: dict, style: dict) -> list[dict]:
    """The section lines of the set: A-A and B-B through the building's
    middle (clear of the walls — ``docs.clear_line``; style:
    show.auto_sections), then the ones he drew (``doc["sections"]``).
    [{"id", "symbol", "a", "b", "flip", "auto"}] — the look is to the
    line's left (flip: right). A / B moved with their grips are FROZEN
    there (a record with their id, ``sections.store``: «frozen»)."""
    from . import docs as D
    from . import model
    out = []
    box = None
    if style["show"].get("auto_sections", True):
        try:
            box = D.extents(doc, model.elevations, roofs=False)
        except Exception:  # noqa: BLE001 — a broken model: no auto lines
            box = None
    # A / B moved with their grips: FROZEN where left (sections.py)
    frozen = {s["id"]: s for s in doc.get("sections") or []
              if s["id"] in ("A", "B")}
    if box is not None:
        cx, cy = (box["x0"] + box["x1"]) / 2, (box["y0"] + box["y1"]) / 2
        sy = D.clear_line(doc, 1, cy, box["y0"], box["y1"])
        sx = D.clear_line(doc, 0, cx, box["x0"], box["x1"])
        # A-A seen from the south (looks north), B-B from the east (looks
        # west) — as the earlier «Make» drew them
        for ln in ({"id": "A", "symbol": "A", "auto": True, "flip": False,
                    "a": [box["x0"] - 1.0, sy], "b": [box["x1"] + 1.0, sy]},
                   {"id": "B", "symbol": "B", "auto": True, "flip": False,
                    "a": [sx, box["y0"] - 1.0], "b": [sx, box["y1"] + 1.0]}):
            f = frozen.get(ln["id"])
            if f is not None:
                ln = dict(ln, frozen=True, flip=bool(f.get("flip")),
                          a=list(f["a"]), b=list(f["b"]))
            out.append(ln)
    for s in doc.get("sections") or []:
        if s["id"] in frozen:
            continue
        out.append({"id": s["id"], "symbol": s.get("symbol") or "?",
                    "auto": False, "flip": bool(s.get("flip")),
                    "a": list(s["a"]), "b": list(s["b"])})
    return out


def sections(doc: dict, style: dict) -> list[dict]:
    """The section sheets (A-2xx): one per line."""
    W = DS.words(style)
    names = style["names"]
    g = int(names.get("section_group", 2))
    ids = [lv["id"] for lv in doc.get("levels") or []]
    out = []
    for i, ln in enumerate(section_lines(doc, style)):
        out.append({"id": "section:" + ln["id"], "kind": "section",
                    "levels": ids, "line": ln,
                    "number": f"{names['prefix']}{g}{i + 1:02d}",
                    "title": names["section_title"].format(
                        section=W["section"], s=ln["symbol"]),
                    "group": "sections"})
    return out


#: the elevations, in the set's order — (side, the way it looks in plan)
ELEVATIONS = (("S", (0.0, 1.0)), ("E", (-1.0, 0.0)), ("N", (0.0, -1.0)),
              ("W", (1.0, 0.0)))


def elevations(doc: dict, style: dict) -> list[dict]:
    """The four elevation sheets (A-3xx): south, east, north, west."""
    if not style["show"].get("elevations", True) or not doc.get("walls"):
        return []
    W = DS.words(style)
    names = style["names"]
    g = int(names.get("elevation_group", 3))
    ids = [lv["id"] for lv in doc.get("levels") or []]
    return [{"id": "elev:" + side, "kind": "elevation", "levels": ids,
             "side": side, "look": list(look),
             "number": f"{names['prefix']}{g}{i + 1:02d}",
             "title": names["elevation_title"].format(
                 elevation=W["elevation"], side=W["sides"][side]),
             "group": "elevations"}
            for i, (side, look) in enumerate(ELEVATIONS)]


def schedules(doc: dict, style: dict) -> list[dict]:
    """The area schedule (A-001): the first sheet of the set."""
    if not style["show"].get("schedule_sheet", True) or not doc.get("walls"):
        return []
    W = DS.words(style)
    names = style["names"]
    g = int(names.get("schedule_group", 0))
    return [{"id": "schedule:areas", "kind": "schedule",
             "levels": [lv["id"] for lv in doc.get("levels") or []],
             "number": f"{names['prefix']}{g}01",
             "title": W["area_schedule"], "group": "schedules"}]


def boards(doc: dict, style: dict) -> list[dict]:
    """The views sheets (A-4xx): several views on one paper, in
    ``doc["docs"]["boards"]``: {"id", "title", "members": [sheet ids]}."""
    Wd = DS.words(style)
    names = style["names"]
    g = int(names.get("board_group", 4))
    ids = [lv["id"] for lv in doc.get("levels") or []]
    return [{"id": "board:" + b["id"], "kind": "board", "levels": ids,
             "members": list(b.get("members") or []),
             "number": f"{names['prefix']}{g}{i + 1:02d}",
             "title": b.get("title") or Wd["board"], "group": "boards"}
            for i, b in enumerate((doc.get("docs") or {}).get("boards") or [])
            if isinstance(b, dict) and b.get("id")]


def views_of(doc: dict, style: dict) -> list[dict]:
    """The sheets a views sheet can show — the plans, sections and
    elevations — with their stored choices laid on."""
    recs = records(doc)
    out = []
    for s in plans(doc, style) + sections(doc, style) \
            + elevations(doc, style):
        out.append(_laid(s, recs.get(s["id"]) or {}))
    return out


def line_of(sheet: dict) -> dict | None:
    """A section sheet's line with the studio's «flip» laid on."""
    ln = sheet.get("line")
    if not ln:
        return None
    return dict(ln, flip=bool(sheet.get("flip", ln.get("flip", False))))


def sheet_signature(doc: dict, sheet: dict) -> str:
    """What a sheet shows of the model — a plan its floors; a section or
    an elevation the whole building, its roofs and its line; a views sheet
    each of its views."""
    if sheet.get("kind") == "board":
        known = {v["id"]: v for v in views_of(doc, DS.resolve())}
        raw = json.dumps([[i, sheet_signature(doc, known[i])]
                          for i in sheet.get("members") or [] if i in known])
        return hashlib.blake2b(raw.encode(), digest_size=10).hexdigest()
    if sheet.get("kind", "plan") == "plan":
        return state_signature(doc, sheet["levels"])
    roofs = sorted(json.dumps(_shape(s), sort_keys=True)
                   for s in doc.get("structure") or []
                   if s.get("type") == "roof")
    raw = json.dumps([state_signature(doc, sheet["levels"]), roofs,
                      _r(line_of(sheet)), _r(sheet.get("look"))],
                     sort_keys=True)
    return hashlib.blake2b(raw.encode(), digest_size=10).hexdigest()


def records(doc: dict) -> dict:
    """The sheets' stored records by id (``doc["docs"]["sheets"]``)."""
    return {r["id"]: r for r in (doc.get("docs") or {}).get("sheets") or []
            if isinstance(r, dict) and r.get("id")}


def state(doc: dict, sheet: dict) -> str:
    """«none» (never made) · «ok» (up to date) · «changed» (the model
    changed since)."""
    rec = records(doc).get(sheet["id"])
    if not rec or not rec.get("sig"):
        return "none"
    return "ok" if rec["sig"] == sheet_signature(doc, sheet) else "changed"


def style_sig(style: dict) -> str:
    """The look a sheet was drawn with (kept on its record)."""
    raw = DS.looks_sig(style)
    return hashlib.blake2b(raw.encode(), digest_size=8).hexdigest()


#: what the studio stores on a sheet's record (its choices)
CHOICES = ("paper", "scale", "cut", "style", "terrain", "others", "flip",
           "fill", "members")


def _laid(s: dict, rec: dict) -> dict:
    """A sheet with its stored choices laid on."""
    s = dict(s, **{k: rec[k] for k in CHOICES if k in rec})
    if s["kind"] in ("section", "elevation"):
        # a section / elevation shows the ground line by default
        s.setdefault("terrain", True)
        if s["kind"] == "section":
            s["line"] = line_of(s)
    return s


def the_set(doc: dict, style: dict) -> list[dict]:
    """Every sheet of the set in the book's order — the area schedule
    (A-001), plans (A-1xx), sections (A-2xx), elevations (A-3xx), views
    sheets (A-4xx) — with its stored choices laid on and its state."""
    recs = records(doc)
    out = []
    for s in schedules(doc, style) + plans(doc, style) \
            + sections(doc, style) + elevations(doc, style) \
            + boards(doc, style):
        rec = recs.get(s["id"]) or {}
        s = _laid(s, rec)
        st = state(doc, s)
        # the style changed since it was made: out of date too (a record
        # from before this one has no mark: it stays as it was)
        if st == "ok" and rec.get("style_sig") and \
                rec["style_sig"] != style_sig(DS.merge(style, s.get("style"))):
            st = "changed"
        out.append(dict(s, state=st))
    return out
