# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""WHAT A CHANGE REBUILDS (his test, 18/11/2026: a beam's Apply took ~2.9 s
on the corporate building — the whole building, 515 pieces, computed again
for one beam). Pure: no Qt, no host.

``struct_only(old, new)``: when the ONLY difference between two documents
is in columns, beams and footings, the ids that must be built again — the
changed ones and what is built FROM them — else None (the whole building,
as ever). What reads them, in ``structure.build``:

- a level's BEAMS are joined among themselves (``W.plan`` of all of them):
  one changed, the level's beams all;
- its STRIP footings likewise;
- its PROFILES «by element» run round its columns and beams (along.py):
  the level's profiles all;
- a GRID wall reads its level's columns and beams (gridwall.context), a
  light-FRAMED wall its beams (``frame_marks``): then the level's WALLS all
  (with their doors and windows) — all of them, not only those: a wall's
  joints with its neighbours are drawn from the neighbours' faces
  (seams.hidden_edges, one level at a time).

Nothing on another level reads them; the ground under the deepest footing
follows in ``ui._commit_all`` (``_ground_follows``), as before."""
from __future__ import annotations

#: what this path rebuilds alone
KINDS = ("column", "beam", "footing")
#: what is never compared (rebuilt from the rest: ``ui._with_built``)
SKIP = ("structure", "built")


def bare(v):
    """``v`` with every dict's keys set to None left out: a key at None is
    the key not there (a typed wall comes out of ``model.typed`` with
    «frame»: None, the stored one without it — every document with wall
    types read as «the walls changed», and nothing took the quick path:
    his corporate building, 18/11/2026)."""
    if isinstance(v, dict):
        return {k: bare(x) for k, x in v.items() if x is not None}
    if isinstance(v, (list, tuple)):
        return [bare(x) for x in v]
    return v


def same(a, b) -> bool:
    """``a`` and ``b`` the same, a key at None being no key."""
    return a == b or bare(a) == bare(b)


def struct_only(old: dict, new: dict):
    """The ids to build again (a set), or None: rebuild it all."""
    keys = (set(old) | set(new)) - set(SKIP)
    if any(not same(old.get(k), new.get(k)) for k in keys):
        return None
    a = {e.get("id"): e for e in old.get("structure") or []}
    b = {e.get("id"): e for e in new.get("structure") or []}
    if None in a or None in b:
        return None
    diff = {i for i in set(a) | set(b) if not same(a.get(i), b.get(i))}
    if not diff:
        return None
    recs = [e for i in diff for e in (a.get(i), b.get(i)) if e is not None]
    if any(e.get("type") not in KINDS for e in recs):
        return None
    lids = {e.get("level") for e in recs}
    beams = {e.get("level") for e in recs if e.get("type") == "beam"}
    walls = new.get("walls") or []
    if any(w.get("id") is None for w in walls):
        return None
    # the levels whose walls read what changed: a grid wall (columns and
    # beams), a framed wall (beams)
    read = {w.get("level") for w in walls
            if (w.get("level") in lids and w.get("gw") and not w.get("cw"))
            or (w.get("level") in beams and w.get("frame"))}
    redo = {w["id"] for w in walls if w.get("level") in read}
    # (a wall is built with its doors and windows: their groups go too)
    out = set(diff) | redo | {o.get("id") for o in new.get("openings") or []
                              if o.get("wall") in redo}
    strips = {e.get("level") for e in recs if e.get("type") == "footing"
              and e.get("kind") == "strip"}
    for e in new.get("structure") or []:
        lv, t = e.get("level"), e.get("type")
        if (t == "beam" and lv in beams) \
                or (t == "footing" and e.get("kind") == "strip"
                    and lv in strips) \
                or (t == "profile" and lv in lids):
            out.add(e["id"])
    return out
