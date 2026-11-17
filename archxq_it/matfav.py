# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The materials' FAVOURITES and the RECENTLY USED (his ask, 12/11: «not only
for this project — kept fixed, not having to look for the ones I use»).

The user's, for every project (QSettings, JSON lists of refs):
    ``archxq/materials/fav``     the ones he starred, in the order starred
    ``archxq/materials/recent``  the last ones applied, the newest first

A ref is one of the gallery's (materials.py): ``{"lib": file}``, a web or
own texture (webtex), ``{"color": [r, g, b], "name"}``. One texture is ONE
favourite whatever its size (``key_of``); a favourite is kept at its own
size, a recent one at the size it was used.

Pure but for ``_load`` / ``_save`` (``_STORE`` stands in for QSettings in
the tests).
"""
from __future__ import annotations

import json

from . import webtex as WT

#: the recently used kept (two rows of the gallery)
RECENT_MAX = 12
#: favourites kept at most (more than anyone stars)
FAV_MAX = 200
_NAMES = {"fav": "archxq/materials/fav", "recent": "archxq/materials/recent"}
_CACHE: dict = {}
_STORE: dict | None = None      # tests: a dict in place of QSettings


# ---- refs ---------------------------------------------------------------------------
def key_of(ref) -> str | None:
    """One texture / colour, whatever its size; None: «Default» or junk."""
    if not isinstance(ref, dict):
        return None
    if isinstance(ref.get("lib"), str) and ref["lib"]:
        return "lib:" + ref["lib"]
    if WT.is_ref(ref):
        return ("web:" + str(ref["web"])) if "web" in ref \
            else ("own:" + str(ref.get("own")))
    try:
        rgb = [float(v) for v in ref["color"][:3]]
    except (KeyError, TypeError, ValueError):
        return None
    return "rgb:" + ",".join(f"{v:.4f}" for v in rgb) if len(rgb) == 3 \
        else None


def kept(ref, own_size: bool) -> dict | None:
    """The ref as stored — at its own size (a favourite) or as used."""
    if key_of(ref) is None:
        return None
    if "lib" in ref:
        out = {"lib": ref["lib"]}
        if not own_size and "sw" in ref and "sh" in ref:
            try:
                out.update(sw=float(ref["sw"]), sh=float(ref["sh"]))
            except (TypeError, ValueError):
                pass
        return out
    if WT.is_ref(ref):
        got = WT.clean_ref(ref)
        if got is None:
            return None
        return WT.sized(got, got["w0"]) if own_size else got
    out = {"color": [round(float(v), 4) for v in ref["color"][:3]]}
    if ref.get("name"):
        out["name"] = str(ref["name"])[:120]
    return out


def _clean(rows) -> list:
    out, seen = [], set()
    for r in rows if isinstance(rows, list) else ():
        k = key_of(r)
        got = kept(r, False) if k else None
        if got is not None and k not in seen:
            seen.add(k)
            out.append(got)
    return out


# ---- the lists ------------------------------------------------------------------------
def favs() -> list:
    return list(_get("fav"))


def recent() -> list:
    return list(_get("recent"))


def is_fav(ref) -> bool:
    k = key_of(ref)
    return k is not None and any(key_of(r) == k for r in _get("fav"))


def toggle(ref) -> bool:
    """Starred ↔ not; True: it is a favourite now."""
    k = key_of(ref)
    if k is None:
        return False
    rows = _get("fav")
    if any(key_of(r) == k for r in rows):
        _put("fav", [r for r in rows if key_of(r) != k])
        return False
    _put("fav", (rows + [kept(ref, True)])[-FAV_MAX:])
    return True


def note_used(ref) -> None:
    """Applied: first of the recently used (once, at the size used)."""
    k = key_of(ref)
    got = kept(ref, False) if k else None
    if got is None:
        return
    rows = [got] + [r for r in _get("recent") if key_of(r) != k]
    _put("recent", rows[:RECENT_MAX])


def note_change(change) -> None:
    """A material change committed (materials.merge's): its refs used."""
    try:
        parts = (change or {}).get("parts") or {}
        for ref in parts.values():
            note_used(ref)
    except Exception:  # noqa: BLE001 — a list not kept never stops a commit
        pass


# ---- the user's (QSettings) --------------------------------------------------------
def _get(which: str) -> list:
    if which not in _CACHE:
        _CACHE[which] = _clean(_load(_NAMES[which]))
    return _CACHE[which]


def _put(which: str, rows: list) -> None:
    _CACHE[which] = rows
    _save(_NAMES[which], rows)


def _load(name: str):
    try:
        if _STORE is not None:
            raw = _STORE.get(name, "")
        else:
            from PySide6.QtCore import QSettings
            raw = QSettings().value(name, "")
        return json.loads(raw) if raw else []
    except Exception:  # noqa: BLE001 — nothing kept: an empty list
        return []


def _save(name: str, rows: list) -> None:
    try:
        raw = json.dumps(rows)
        if _STORE is not None:
            _STORE[name] = raw
        else:
            from PySide6.QtCore import QSettings
            QSettings().setValue(name, raw)
    except Exception:  # noqa: BLE001 — not kept: the gallery still works
        pass
