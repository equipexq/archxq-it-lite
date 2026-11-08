# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Many changed at once from ONE element's window (PLANO_EDICAO_LOTE.md,
L1 — 2026-10-31, Kamen #68: «the batch edit exists, but nobody finds it»).

Several of a kind selected, the window of any of them changes them all:
only what was CHANGED in it goes to the others (what the window gave back
when it opened against what it gives back now) — the rest of each stays
its own. Never in a batch: the name and the place (12 windows on one spot
make no sense; moving many is the library's move bars, relative).
Each one then passes the same rules as alone (fits its wall, why_not).
"""
from __future__ import annotations

import copy

#: never carried to the others — who it is and where it is
NEVER = frozenset({
    "id", "name", "level", "wall", "pos", "a", "b", "c", "r", "corners",
    "holes", "pts", "x", "y", "anchor", "op_id", "on", "from", "to",
    "start", "from_z", "to_z", "auto", "zc"})

#: …and by family: an opening's kind (door ↔ window: the library's), a
#: wall's (line ↔ arc), a structural element's type (a column stays one)
NEVER_BY = {"opening": frozenset({"kind", "wall"}),
            "wall": frozenset({"kind"}),
            "struct": frozenset({"type", "op"})}

#: switched, not set: «Flip side» turns each one round from ITS side
FLIPS = {"wall": frozenset({"side"})}

#: a key the window took away (a wall's sloped top back to flat)
GONE = object()


def changes(base: dict, new: dict, family: str) -> dict:
    """{key: value | GONE} — what the window changed, without who / where
    and the window's own marks («_type_all»…)."""
    skip = NEVER | NEVER_BY.get(family, frozenset())
    out = {}
    for k in set(base) | set(new):
        if k.startswith("_") or k in skip:
            continue
        if k not in new:
            out[k] = GONE
        elif k not in base or base[k] != new[k]:
            out[k] = copy.deepcopy(new[k])
    return out


def spread(rec: dict, ch: dict, family: str) -> dict:
    """``rec`` with the changes on it (a flip turns ITS value round)."""
    flips = FLIPS.get(family, frozenset())
    r = copy.deepcopy(rec)
    for k, v in ch.items():
        if v is GONE:
            r.pop(k, None)
        elif k in flips:
            r[k] = -int(rec.get(k, 1))
        else:
            r[k] = copy.deepcopy(v)
    return r


def summary(done: list[str], refused: list[tuple[str, str]],
            noun: str) -> str:
    """The message after it: «12 windows updated» / «10 of 12 … — 2
    don't fit: W-07 (why), W-11»."""
    from .i18n import tr
    n = len(done) + len(refused)
    noun = tr(noun)
    if not refused:
        return tr("{n} {noun} updated — Ctrl+Z undoes it", n=n, noun=noun)
    names = ", ".join(f"{name} ({why})" if i == 0 else name
                      for i, (name, why) in enumerate(refused[:4]))
    if len(refused) > 4:
        names += " …"
    return tr("{k} of {n} {noun} updated — {m} not changed: {names}",
              k=len(done), n=n, noun=noun, m=len(refused), names=names)
