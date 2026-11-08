# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""AUTOMATIC SLABS (his idea, 2026-10-05 — PLANO_RAMPA_ESCADA.md §8;
since 07/11/2026 made only on request — ``sync(create=True)`` — the ones
a file has still follow their dig):
every excavation for basements will have its floors one day, so ArchXQ
makes them at once — the user only hides what he does not want.

For each excavation (cut, dug): a slab on every BASEMENT level it holds
(its floor at or above the dig's bottom) and on the GROUND floor over
them (the basements' roof) — the dig's outline, 1 cm in from its earth
walls. Stored as ordinary slabs (window, Ctrl+Z, ramp / stair holes)
with ``auto = {"dig": id}``; ``sync`` keeps them following their dig.

- Deleted (the window, the Delete key): it stays away — its key goes to
  ``doc["auto_off"]`` (Ctrl+Z brings it back).
- A slab drawn by hand over most of it on that level takes its place.
- The walls' slabs (closed rooms above the ground) come later (§8, 3).
"""
from __future__ import annotations

T = 0.20                 # m, a new automatic slab's thickness (now the
#                          level's own «slab_t» — model.SLAB_T — see new_t)
INSET = 0.01             # m in from the excavation's earth walls


def key(dig_id: str, level_id: str) -> str:
    return f"dig:{dig_id}:{level_id}"


def key_of(e: dict) -> str | None:
    a = e.get("auto")
    if isinstance(a, dict) and a.get("dig"):
        return key(a["dig"], e["level"])
    return None


def _outline(corners) -> list | None:
    """The dig's outline 1 cm in (counter-clockwise), or None."""
    try:
        from shapely.geometry import Polygon
    except ImportError:
        return [list(p) for p in corners]
    p = Polygon(corners)
    if not p.is_valid:
        p = p.buffer(0)
    q = p.buffer(-INSET, join_style=2)
    if q.is_empty or q.geom_type != "Polygon" or q.area < 0.5:
        return None
    pts = [[round(x, 4), round(y, 4)] for x, y in q.exterior.coords[:-1]]
    a = sum(p_[0] * q_[1] - q_[0] * p_[1]
            for p_, q_ in zip(pts, pts[1:] + pts[:1]))
    return pts if a > 0 else list(reversed(pts))


def wanted(doc: dict, elevations) -> dict:
    """{key: (dig, level, corners)} — the slabs the excavations call for."""
    from . import terrain
    levels = doc.get("levels") or []
    if not levels or not doc.get("plot"):
        return {}
    ground = doc["project"]["ground_level"] if doc.get("project") else 0.0
    elev = elevations(levels, ground)
    out = {}
    for d in terrain.opened(doc):
        if d.get("kind") == "fill":
            continue
        try:
            bottom = min(terrain.dig_bottoms(d, doc))
        except Exception:  # noqa: BLE001 — no bottom: no floors
            continue
        corners = _outline(terrain.snug(doc, d["corners"]))
        if corners is None:
            continue
        held = [i for i, lv in enumerate(levels)
                if lv["kind"] == "basement" and elev[i] >= bottom - 0.01]
        if not held:
            continue
        # the ground floor over them: the basements' roof
        held += [i for i, lv in enumerate(levels) if lv["kind"] == "ground"]
        for i in held:
            lv = levels[i]
            out[key(d["id"], lv["id"])] = (d, lv, corners)
    return out


def new_t(dig: dict, lv: dict) -> float:
    """A NEW automatic slab's thickness: the level's own («slab_t», 0.20
    without one) — and the floor slab of the level the pit is dug under
    («Under a level», 0.30 below its floor) reaches down to the pit's
    bottom: 0.30 thick, no strip of earth left between them."""
    from . import model
    b = dig.get("bottom") or {}
    if b.get("mode") == "level" and b.get("level") == lv["id"] \
            and lv.get("kind") == "basement":
        try:
            d = -float(b.get("offset", 0.0))
        except (TypeError, ValueError):
            d = 0.0
        if model.MIN_SLAB_T <= d <= model.MAX_SLAB_T:
            return round(d, 3)
    return model.slab_t(lv)


def _covered(corners, slabs) -> bool:
    """A slab drawn by hand covers most of it (it takes its place)."""
    try:
        from shapely.geometry import Polygon
    except ImportError:
        return False
    a = Polygon(corners)
    if a.area < 1e-6:
        return True
    for s in slabs:
        b = Polygon(s["corners"])
        if not b.is_valid:
            b = b.buffer(0)
        if a.intersection(b).area > 0.5 * a.area:
            return True
    return False


def sync(doc: dict, elevations, create: bool = False) -> dict:
    """``doc`` with its automatic slabs followed or taken away — the
    hand-made ones untouched. ``create`` also MAKES the missing ones.

    (His call, 07/11/2026: an excavation no longer makes its slabs by
    itself — a lid over the pit, drawn on the Terrain, read as a bug to a
    first-time user. The slabs a file already has stay and still follow
    their dig; making them is to come on request, from the Structure
    phase — ``create=True``.)"""
    from . import edition, model
    if edition.lite():                    # slabs are ArchXQ IT Pro's: the
        return doc                        # Lite keeps a Pro file's as they are
    st = list(doc.get("structure") or [])
    off = set(doc.get("auto_off") or [])
    want = wanted(doc, elevations)
    by_key = {key_of(e): e for e in st if key_of(e)}
    manual = [e for e in st if e.get("type") == "slab" and not key_of(e)]
    keep, new = [], []
    for e in st:
        k = key_of(e)
        if k is None:
            keep.append(e)
            continue
        if k not in want or k in off:
            continue                      # its dig / level is gone
        _d, lv, corners = want[k]
        mine = [m for m in manual if m["level"] == lv["id"]]
        if _covered(corners, mine):
            continue                      # a hand-made one in its place
        keep.append(dict(e, corners=corners))
    for k, (d, lv, corners) in (want.items() if create else ()):
        if k in by_key or k in off:
            continue
        mine = [m for m in manual if m["level"] == lv["id"]]
        if _covered(corners, mine):
            continue
        # (support #93, 07/11/2026) only a NEW slab takes these — one that
        # is there keeps its thickness, whatever changed (above: never
        # rewritten), so no file changes on opening and no edit is lost
        new.append({"type": "slab", "level": lv["id"], "corners": corners,
                    "t": new_t(d, lv), "offset": 0.0, "holes": [],
                    "auto": {"dig": d["id"]}})
    if new:
        made = model.new_elements(keep, new)
        keep += made
    if keep == st:
        return doc
    return dict(doc, structure=keep)
