"""The library's FAVOURITES (0.17.0 — PLANO_BIBLIOTECA_FAVORITOS.md): the
right strip shows only the types he keeps there; «★ All N…» opens every
type (library.AllTypesDialog), where a star pins one.

The user's, for every project (QSettings ``archxq/library/fav/<element>``):
    {"fav": [keys], "known": [keys]}
a ready-made type by its key, one of YOUR types (walls, slabs) as
``u:<id>``. ``known``: every key seen when the list was last kept — a type
come with an update is NOT put on the strip by itself (a «new» dot on the
«All…» button), one of YOUR types not seen yet (just made, or a project
opened with its own) is.

Pure but for ``load`` / ``save``.
"""
from __future__ import annotations

import json

#: up to this many fit the strip without scrolling (3 × 3)
STRIP_MAX = 9


def N_(text: str) -> str:
    """A text to translate where it is shown (i18n_extract reads it)."""
    return text


YOURS = N_("Your types")

#: the window's categories, per element: (name, (type keys…)) — an element
#: not here has one (no chips)
CATS = {
    "door": ((N_("Hinged"), ("swing", "arched")),
             (N_("Sliding"), ("sliding", "glass")),
             (N_("Shop & garage"), ("shop", "garage"))),
    "window": ((N_("Operable"), ("sliding", "casement", "awning", "pivot")),
               (N_("Fixed"), ("fixed", "shop"))),
    "wall": ((N_("Masonry"), ("w15", "w20")),
             (N_("Partitions"), ("w10",)),
             (N_("Glass"), ("curtain",))),
    "slab": ((N_("Structure"), ("s12", "s15", "s20")),
             (N_("Floors"), ("tiles", "timber")),
             (N_("Roof"), ("roofslab",)),
             (N_("Block & ceiling"), ("block", "ceiling"))),
    "roof": ((N_("Pitched"), ("gable", "hip", "shed", "butterfly", "mansard",
                              "lt")),
             (N_("Flat"), ("flat", "hidden"))),
    "guard": ((N_("Low walls"), ("wall", "wallrail", "boundary")),
              (N_("Railings"), ("glass", "steel"))),
    "glazing": ((N_("Glass"), ("industrial", "aluminium", "partition",
                               "arched", "round")),
                (N_("Open (cobogó)"), ("square", "diamond", "lattice",
                                       "vslats", "hslats")),
                (N_("Security"), ("bars",))),
    "profile": ((N_("Baseboards"), ("base_flat", "base_mould")),
                (N_("Crowns"), ("crown_cove", "crown_ogee")),
                (N_("Wall & façade"), ("chair_rail", "cornice", "band"))),
    "copy": ((N_("Street & garden"), ("bollard", "lamp", "tree",
                                      "planter")),
             (N_("Fences"), ("post",)),
             (N_("From the model"), ("mine",))),
}


def ukey(tid: str) -> str:
    return "u:" + str(tid)


def categories(element: str, keys, has_yours: bool = False) -> list:
    """[(name, [keys])] in the window's order — one of YOUR types' keys
    (``u:…``) under «Your types»; an element with no categories: one,
    named after nothing ("")."""
    keys = list(keys)
    out = []
    left = [k for k in keys if not k.startswith("u:")]
    for name, ks in CATS.get(element, ()):
        mine = [k for k in left if k in ks]
        if mine:
            out.append((name, mine))
    placed = {k for _n, ks in out for k in ks}
    rest = [k for k in left if k not in placed]
    if rest:
        out.append((N_("Other") if out else "", rest))
    yours = [k for k in keys if k.startswith("u:")]
    if yours or has_yours:
        out.append((YOURS, yours))
    return out


def every(ready, yours) -> list:
    """Every key the strip may hold: the ready-made that draw (not
    «soon»), then YOUR types — ``ready``: [(key, soon)], ``yours``: ids."""
    return [k for k, soon in ready if not soon] + [ukey(t) for t in yours]


def resolve(saved: dict | None, ready, yours) -> tuple[list, list]:
    """(the favourites, in the catalogue's order; the keys NEW since the
    list was kept — ready-made ones, for the «new» dot). Nothing kept yet:
    every one is a favourite (nobody loses a card with the update)."""
    allk = every(ready, yours)
    if not saved:
        return allk, []
    fav = set(saved.get("fav") or ())
    known = set(saved.get("known") or ())
    # YOUR types not seen yet go on the strip; ready-made ones wait
    fav |= {k for k in allk if k.startswith("u:") and k not in known}
    new = [k for k in allk if not k.startswith("u:") and k not in known]
    favs = [k for k in allk if k in fav]
    if not favs and allk:
        favs = allk[:1]                 # never an empty strip
    return favs, new


def kept(favs, ready, yours, saved: dict | None = None,
         seen: bool = False) -> dict:
    """What to keep: the favourites, and every key known — all of them
    when ``seen`` (the window was opened: the «new» dot goes), else the
    known ones so far plus YOUR types (a deleted type's key stays — it
    harms nothing, and a project opened again finds it)."""
    allk = every(ready, yours)
    known = set((saved or {}).get("known") or ()) if saved else set(allk)
    known |= {k for k in allk if k.startswith("u:")}
    if seen:
        known |= set(allk)
    old_fav = set((saved or {}).get("fav") or ())
    # a favourite of another project (one of YOUR types not here) stays
    fav = [k for k in allk if k in set(favs)] + sorted(
        k for k in old_fav if k.startswith("u:") and k not in allk)
    return {"fav": fav, "known": sorted(known)}


def toggle(favs, key: str) -> list:
    """The favourites with ``key`` put on / taken off — never the last."""
    favs = list(favs)
    if key in favs:
        if len(favs) > 1:
            favs.remove(key)
    else:
        favs.append(key)
    return favs


def strip(favs, current: str | None) -> tuple[list, str | None]:
    """(the cards on the strip, the «in use» one — the type picked or
    selected when it is not a favourite, at the strip's end)."""
    favs = list(favs)
    return favs, (current if current and current not in favs else None)


def can_drop(favs) -> bool:
    """A card may lose its trash: the last favourite keeps the strip."""
    return len(list(favs)) > 1


# ---- the user's (QSettings) --------------------------------------------------------
def _name(element: str) -> str:
    return f"archxq/library/fav/{element}"


def load(element: str) -> dict | None:
    try:
        from PySide6.QtCore import QSettings
        raw = QSettings().value(_name(element), "")
        d = json.loads(raw) if raw else None
        return d if isinstance(d, dict) else None
    except Exception:  # noqa: BLE001 — none kept: every one a favourite
        return None


def save(element: str, d: dict) -> None:
    try:
        from PySide6.QtCore import QSettings
        QSettings().setValue(_name(element), json.dumps(d))
    except Exception:  # noqa: BLE001 — not kept: the strip still works
        pass
