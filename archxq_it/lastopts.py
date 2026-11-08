# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The LAST choice of each element — its type and sizes — kept from one
session to the next (his call, 2026-10-28: «picked a column, that column and
its sizes until it is changed»). The user's, for every project (QSettings
``archxq/last/<name>``), as the favourites.

YOUR wall / slab types (``wtype`` / ``stype``) are NOT kept: they are the
document's — another project has none of them (the ready-made one then).

Pure but for ``load`` / ``save``.
"""
from __future__ import annotations

import json

#: the ArchXQ attributes kept (the libraries' and the tools' options)
NAMES = ("wall_opts", "col_opts", "beam_opts", "slab_opts", "foot_opts",
         "guard_opts", "street_opts", "glazing_opts", "roof_opts",
         "bstair_opts", "bramp_opts", "op_opts", "profile_opts", "copy_opts")
#: keys never kept (the document's own — an object copied along a path,
#: taken from the model: «src»)
DROP = frozenset({"wtype", "stype", "src"})


def _fits(default, value) -> bool:
    """``value`` may stand for ``default``: the same kind of thing."""
    if isinstance(default, bool) or isinstance(value, bool):
        return isinstance(default, bool) and isinstance(value, bool)
    if isinstance(default, (int, float)):
        return isinstance(value, (int, float))
    if default is None:
        return value is None or isinstance(value, (str, int, float, list))
    if isinstance(default, str):
        return isinstance(value, str)
    if isinstance(default, list):
        return isinstance(value, list)
    return False


def merge(defaults: dict, saved) -> dict:
    """``defaults`` with what was kept on top — only keys it knows, of the
    same kind (a key from an older ArchXQ, a wrong value: the default). A
    dict inside (the openings' door / window / void): the same, one level
    down."""
    out = dict(defaults)
    if not isinstance(saved, dict):
        return out
    for k, v in saved.items():
        if k in DROP or k.startswith("_") or k not in defaults:
            continue
        d = defaults[k]
        if isinstance(d, dict):
            out[k] = merge(d, v)
        elif _fits(d, v):
            out[k] = float(v) if isinstance(d, float) \
                and not isinstance(v, bool) else v
    return out


def kept(opts: dict) -> dict:
    """What is written: JSON-able keys, the document's own left out."""
    out = {}
    for k, v in opts.items():
        if k in DROP or k.startswith("_"):
            continue
        if isinstance(v, dict):
            v = kept(v)
        try:
            json.dumps(v)
        except (TypeError, ValueError):
            continue
        out[k] = v
    return out


# ---- the user's (QSettings) --------------------------------------------------------
def _name(name: str) -> str:
    return f"archxq/last/{name}"


def load(name: str):
    try:
        from PySide6.QtCore import QSettings
        raw = QSettings().value(_name(name), "")
        d = json.loads(raw) if raw else None
        return d if isinstance(d, dict) else None
    except Exception:  # noqa: BLE001 — none kept: the defaults
        return None


def save(name: str, d: dict) -> None:
    try:
        from PySide6.QtCore import QSettings
        QSettings().setValue(_name(name), json.dumps(d))
    except Exception:  # noqa: BLE001 — not kept: the session still works
        pass
