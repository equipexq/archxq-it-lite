"""LAYERS HIDDEN in the 3D (PLANO_OCULTAR_CAMADAS.md, his OK 2026-11-02):
the eye on a layer's row — the siding and the OSB off, the studs seen.

Kept in the document (``doc["hidden_layers"]``)::

    {owner: [key, …]}
    owner = a wall / slab TYPE's id (every element of it) — or the
            element's own id (layers of its own)
    key   = a layer's id; a light-framed core: «studs» / «fill»

Only the 3D: plans, sections, sheets, quantities and an Explode see the
element whole (``structure.build`` reads ``_hide``, set by ``mark``; the
others build from records without it).

Pure: no Qt.
"""
from __future__ import annotations

#: a light-framed core's two parts, each its own eye
STUDS, FILL = "studs", "fill"


def clean(raw, doc: dict) -> dict:
    """As stored: owners that still exist, keys as strings."""
    if not isinstance(raw, dict):
        return {}
    owners = {t.get("id") for t in doc.get("wall_types") or ()} \
        | {t.get("id") for t in doc.get("slab_types") or ()} \
        | {w.get("id") for w in doc.get("walls") or ()} \
        | {e.get("id") for e in doc.get("structure") or ()}
    out = {}
    for k, v in raw.items():
        if k in owners and isinstance(v, (list, tuple, set)):
            keys = sorted({str(x) for x in v if x})
            if keys:
                out[str(k)] = keys
    return out


def owner(doc: dict, kind: str, el: dict) -> str | None:
    """Whose eyes an element's layers follow: its type's (every element
    of it), else its own."""
    if not el:
        return None
    if kind == "wall":
        if el.get("cw"):
            return None
        tid = el.get("type")
        types = doc.get("wall_types") or ()
    else:
        tid = el.get("stype")
        types = doc.get("slab_types") or ()
    if tid and any(t.get("id") == tid for t in types):
        return tid
    return el.get("id")


def hidden(doc: dict, who) -> set:
    return set((doc.get("hidden_layers") or {}).get(who or "", ()))


def hidden_of(doc: dict, kind: str, el: dict) -> set:
    return hidden(doc, owner(doc, kind, el))


def set_key(doc: dict, who: str, key: str, off: bool) -> dict:
    """``doc`` with ``key`` of ``who`` hidden (``off``) or shown."""
    hl = {k: list(v) for k, v in (doc.get("hidden_layers") or {}).items()}
    keys = set(hl.get(who, ()))
    if off:
        keys.add(key)
    else:
        keys.discard(key)
    if keys:
        hl[who] = sorted(keys)
    else:
        hl.pop(who, None)
    return dict(doc, hidden_layers=hl)


def show_all(doc: dict, who: str | None = None) -> dict:
    """Every layer shown — of ``who``, or of everything."""
    hl = {k: list(v) for k, v in (doc.get("hidden_layers") or {}).items()
          if who is not None and k != who}
    return dict(doc, hidden_layers=hl)


def mark(doc: dict, kind: str, el: dict) -> dict:
    """The element as ``structure.build`` builds it for the 3D: ``_hide``
    = its hidden keys (none: the record as it is)."""
    keys = hidden_of(doc, kind, el)
    return dict(el, _hide=sorted(keys)) if keys else el


def nothing_shown(doc: dict, kind: str, el: dict) -> bool:
    """Every eye of the element off: the 3D builds it no faces, so it has
    no group, and that does NOT mean it was deleted (his video, 04/11: all
    the eyes of a wall type off, the next click took the walls and their
    windows out of the file). A framed core's eyes are its studs and its
    insulation; one left empty has no insulation to hide."""
    keys = hidden_of(doc, kind, el)
    layers = (el or {}).get("layers")
    if not keys or not layers:
        return False
    fr = el.get("frame")
    for la in layers:
        if la.get("id") in keys:
            continue
        if la.get("role") == "core" and isinstance(fr, dict) \
                and STUDS in keys \
                and (FILL in keys or fr.get("fill") == "empty"):
            continue
        return False
    return True


def indexes(layers, keys) -> set:
    """The layers' indexes hidden by ``keys`` (a framed core's «studs» /
    «fill» are not layers: read by the build)."""
    keys = set(keys or ())
    return {i for i, la in enumerate(layers or ()) if la.get("id") in keys}
