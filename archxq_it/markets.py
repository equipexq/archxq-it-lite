"""Ready wall types BY MARKET (PLANO_PAREDE_ESTRUTURA_LEVE.md, D5 — phase 2,
2026-11-02): the way a house is built in the US, in Europe, in the UK — its
layers outside → inside and, for a light-framed one, its studs (framing.py).

A card in the walls' library (category «By market»): clicked, the type is
put in the project's types (``doc["wall_types"]``, marked ``market``) — or
the one made before is taken — and picked; from then on it is one of HIS
types: renamed, edited, deleted at will.

Pure: no Qt.
"""
from __future__ import annotations

import uuid

from .framing import clean_frame

IN = 0.0254                      # an inch


#: what each layer is made of (``materials`` refs): textures of IngeTrazo's
#: library where one looks right, plain colours for the boards (the Lite
#: shows those too)
SIDING = {"lib": "wall/white_wood.jpg"}
CLADDING = {"lib": "wall/gray_wood.jpg"}
RENDER = {"lib": "wall/white_roughcast.jpg"}
BRICK = {"lib": "brick/brick_red.png"}
BLOCKS = {"lib": "concrete/concrete_blocks.png"}
CLAY = {"lib": "brick/brick_clay.png"}
OSB = {"color": [0.80, 0.66, 0.42], "name": "OSB"}
GYPSUM = {"color": [0.94, 0.93, 0.90], "name": "Gypsum board"}
PLASTER = {"color": [0.95, 0.94, 0.91], "name": "Plaster"}
FIBRE = {"color": [0.60, 0.44, 0.28], "name": "Wood-fibre board"}
EPS = {"color": [0.97, 0.97, 0.95], "name": "EPS insulation"}
CAVITY = {"color": [0.55, 0.57, 0.60], "name": "Cavity"}


def _l(name: str, t: float, core: bool = False, mat=None) -> dict:
    la = {"name": name, "t": t, "role": "core" if core else "finish"}
    if mat:
        la["mat"] = mat
    return la


def _wood(w: float, s: float, top: int = 2, fill: str = "insulation") -> dict:
    return {"kind": "wood", "w": w, "s": s, "top": top, "bottom": 1,
            "fill": fill}


def _steel(w: float, s: float) -> dict:
    return {"kind": "steel", "w": w, "s": s, "top": 1, "bottom": 1,
            "fill": "insulation"}


#: (key, name, tip, layers outside → inside, frame | None)
TYPES = (
    ("us2x4", "US 2×4 exterior",
     "American light frame: siding · sheathing 11 mm · 2×4 studs (38×89) "
     "every 16\" with insulation · gypsum board 13 mm",
     (_l("Siding", 0.020, mat=SIDING), _l("Sheathing", 0.011, mat=OSB),
      _l("Studs 2×4", 0.089, True), _l("Gypsum board", 0.013, mat=GYPSUM)),
     _wood(0.038, 16 * IN)),
    ("us2x6", "US 2×6 exterior",
     "American light frame, the warmer one: siding · sheathing 11 mm · 2×6 "
     "studs (38×140) every 16\" with insulation · gypsum board 13 mm",
     (_l("Siding", 0.020, mat=SIDING), _l("Sheathing", 0.011, mat=OSB),
      _l("Studs 2×6", 0.140, True), _l("Gypsum board", 0.013, mat=GYPSUM)),
     _wood(0.038, 16 * IN)),
    ("usint", "US interior 2×4",
     "American partition: gypsum board 13 mm · 2×4 studs every 16\", "
     "empty · gypsum board 13 mm",
     (_l("Gypsum board", 0.013, mat=GYPSUM), _l("Studs 2×4", 0.089, True),
      _l("Gypsum board", 0.013, mat=GYPSUM)),
     _wood(0.038, 16 * IN, fill="empty")),
    ("eutimber", "EU timber frame",
     "European timber frame (Holzrahmenbau): render · wood-fibre board "
     "60 mm · OSB 15 · studs 60×160 every 62.5 cm with insulation · OSB "
     "15 · plasterboard 12.5",
     (_l("Render", 0.010, mat=RENDER), _l("Wood-fibre board", 0.060, mat=FIBRE),
      _l("OSB", 0.015, mat=OSB), _l("Studs 60×160", 0.160, True),
      _l("OSB", 0.015, mat=OSB), _l("Plasterboard", 0.0125, mat=GYPSUM)),
     _wood(0.060, 0.625, top=1)),
    ("lsf", "Steel frame (LSF)",
     "Light steel frame: cladding · OSB 12 · C90 steel studs every 60 cm "
     "with insulation · plasterboard 12.5",
     (_l("Cladding", 0.020, mat=CLADDING), _l("OSB", 0.012, mat=OSB),
      _l("Steel studs C90", 0.090, True),
      _l("Plasterboard", 0.0125, mat=GYPSUM)),
     _steel(0.050, 0.60)),
    ("drywall", "Drywall partition",
     "Drywall partition: plasterboard 12.5 · CW75 steel studs every 62.5 cm "
     "with insulation · plasterboard 12.5",
     (_l("Plasterboard", 0.0125, mat=GYPSUM),
      _l("Steel studs CW75", 0.075, True),
      _l("Plasterboard", 0.0125, mat=GYPSUM)),
     _steel(0.050, 0.625)),
    ("ukcavity", "UK cavity wall",
     "British cavity wall: brick 102 · cavity 50 · blockwork 100 · "
     "plaster 13",
     (_l("Brick", 0.102, mat=BRICK), _l("Cavity", 0.050, mat=CAVITY),
      _l("Blockwork", 0.100, True, BLOCKS), _l("Plaster", 0.013, mat=PLASTER)),
     None),
    ("etics", "ETICS (EU)",
     "External insulation (ETICS / WDVS): render · EPS 100 · masonry 200 · "
     "plaster 15",
     (_l("Render", 0.010, mat=RENDER), _l("EPS insulation", 0.100, mat=EPS),
      _l("Masonry", 0.200, True, CLAY), _l("Plaster", 0.015, mat=PLASTER)),
     None),
)

KEYS = tuple(k for k, *_r in TYPES)


def get(key: str):
    """(key, name, tip, layers, frame) — None: no such market type."""
    return next((m for m in TYPES if m[0] == key), None)


def layers_of(key: str) -> list:
    """Its layers as a type keeps them (ids l0, l1…; the core «core»)."""
    m = get(key)
    return [dict({k: v for k, v in la.items() if k != "mat"},
                 id="core" if la["role"] == "core" else f"l{i}")
            for i, la in enumerate(m[3])] if m else []


def look(key: str) -> dict:
    """What its layers are made of, as a type's look keeps it
    (``doc["materials"]["wtype"][id]``: «L:<id>» each finish, «all» a solid
    core — a framed one keeps its pine / steel studs)."""
    m = get(key)
    if m is None:
        return {}
    out = {}
    for la, kept in zip(m[3], layers_of(key)):
        if la.get("mat") and not (la["role"] == "core" and m[4]):
            out["all" if la["role"] == "core" else "L:" + kept["id"]] = \
                dict(la["mat"])
    return out


def find(types, key: str):
    """The project's type made from it before (its mark; else its name) —
    None: not made yet."""
    m = get(key)
    if m is None:
        return None
    types = list(types or ())
    return next((t for t in types if t.get("market") == key), None) or \
        next((t for t in types if t.get("name") == m[1]), None)


def new_type(key: str, taken=()) -> dict | None:
    """The type to put in ``doc["wall_types"]`` (a fresh id)."""
    m = get(key)
    if m is None:
        return None
    tid = uuid.uuid4().hex[:8]
    while tid in set(taken):
        tid = uuid.uuid4().hex[:8]
    ls = layers_of(key)
    ty = {"id": tid, "name": m[1], "layers": ls,
          "t": round(sum(la["t"] for la in ls), 4), "market": key}
    fr = clean_frame(m[4])
    if fr is not None:
        ty["frame"] = fr
    return ty


# ---- ROOFS by market (PLANO_TELHADO_CAMADAS 2c, his OK 2026-11-02) ----------
#: (key, name, tip, layers TOP → BOTTOM, frame | None) — a card in the
#: roofs' library: clicked, its layers and rafters for the selected roofs
#: (one Ctrl+Z) and the next ones drawn. No roof types yet: each roof keeps
#: them as its own (its window's Layers tab)
ROOFS = (
    ("rus2x8", "US 2×8 rafters",
     "American roof: asphalt shingles · sheathing 11 mm · 2×8 rafters "
     "(38×184) every 16\" with insulation · gypsum board 13 mm",
     (_l("Asphalt shingles", 0.010), _l("Sheathing", 0.011),
      _l("Rafters 2×8", 0.184, True), _l("Gypsum board", 0.013)),
     _wood(0.038, 16 * IN, top=1)),
    ("reutimber", "EU tiles on rafters",
     "European pitched roof: clay tiles · battens and counter-battens 50 "
     "mm · wood-fibre board 35 · rafters 80×180 every 62.5 cm with "
     "insulation · plasterboard 12.5",
     (_l("Clay tiles", 0.050), _l("Battens", 0.050),
      _l("Wood-fibre board", 0.035), _l("Rafters 80×180", 0.180, True),
      _l("Plasterboard", 0.0125)),
     _wood(0.08, 0.625, top=1)),
    ("rsteel", "Steel frame, metal sheet",
     "Light steel roof: metal sheet · OSB 15 · steel C rafters 200 mm "
     "every 60 cm with insulation · gypsum board 12.5",
     (_l("Metal sheet", 0.010), _l("OSB", 0.015),
      _l("Steel rafters", 0.200, True), _l("Gypsum board", 0.0125)),
     _steel(0.05, 0.60)),
    ("rcold", "Ventilated attic",
     "A cold roof: clay tiles · battens 40 mm · rafters 80×160 every 62.5 "
     "cm, nothing between — the insulation lies on the ceiling below",
     (_l("Clay tiles", 0.050), _l("Battens", 0.040),
      _l("Rafters 80×160", 0.160, True)),
     _wood(0.08, 0.625, top=1, fill="empty")),
)
# (trusses — PLANO_TELHADO_ASNAS 3c: the ceiling the layers under the
# core, flat under the bottom chords; the insulation on it)
ROOFS += (
    ("rustruss", 'US trusses 24"',
     "American roof on trusses: asphalt shingles · sheathing 11 mm · "
     "2×4 Fink trusses every 24\" · insulation on the ceiling · gypsum "
     "board 13 mm (flat, under the trusses)",
     (_l("Asphalt shingles", 0.010), _l("Sheathing", 0.011),
      _l("Trusses 2×4", 0.089, True), _l("Gypsum board", 0.013)),
     dict(_wood(0.038, 24 * IN), system="trusses", pattern="auto")),
    ("reutruss", "EU nail-plate trusses",
     "European roof on trusses: clay tiles · battens and counter-battens "
     "50 mm · nail-plate trusses 40×120 every 62.5 cm · insulation on the "
     "ceiling · plasterboard 12.5 (flat, under the trusses)",
     (_l("Clay tiles", 0.050), _l("Battens", 0.050),
      _l("Trusses 40×120", 0.120, True), _l("Plasterboard", 0.0125)),
     dict(_wood(0.04, 0.625), system="trusses", pattern="auto")),
)
ROOF_KEYS = tuple(k for k, *_r in ROOFS)


def roof(key: str):
    """(key, name, tip, layers, frame) — None: no such roof."""
    return next((m for m in ROOFS if m[0] == key), None)


def roof_set(key: str) -> dict:
    """What its card sets on a roof (and the next one drawn): its layers
    (ids l0, l1…, the core «core»), their sum, its rafters."""
    m = roof(key)
    if m is None:
        return {}
    ls = [dict({k: v for k, v in la.items() if k != "mat"},
               id="core" if la["role"] == "core" else f"l{i}")
          for i, la in enumerate(m[3])]
    return {"layers": ls, "t": round(sum(la["t"] for la in ls), 4),
            "frame": clean_frame(m[4])}


#: the card that takes them off again: one solid slab (as before 2a)
ROOF_SOLID = {"layers": None, "frame": None, "t": 0.20}


# ---- FLOORS by market (PLANO_PISOS_BARROTES 4b, his OK 2026-11-02) ----------
#: (key, name, tip, layers TOP → BOTTOM, frame) — a card in the slabs'
#: library: clicked, its layers and joists for the selected slabs (one
#: Ctrl+Z) and the next ones drawn
FLOORS = (
    ("fus2x10", 'US 2×10 joists 16"',
     "American floor: hardwood 19 · subfloor OSB 18 · 2×10 joists (38×235) "
     "every 16\" with insulation · gypsum board 13 (the ceiling under it)",
     (_l("Hardwood", 0.019), _l("Subfloor OSB", 0.018),
      _l("Joists 2×10", 0.235, True), _l("Gypsum board", 0.013)),
     _wood(0.038, 16 * IN, top=1)),
    ("feutimber", "EU timber joists",
     "European timber floor (Holzbalkendecke): floorboards 22 · OSB 18 · "
     "joists 60×220 every 62.5 cm with insulation · plasterboard 12.5",
     (_l("Floorboards", 0.022), _l("OSB", 0.018),
      _l("Joists 60×220", 0.220, True), _l("Plasterboard", 0.0125)),
     _wood(0.06, 0.625, top=1)),
    ("fsteel", "Steel joists",
     "Light steel floor: OSB 18 · steel C joists 200 mm every 40 cm with "
     "insulation · plasterboard 12.5",
     (_l("OSB", 0.018), _l("Steel joists C200", 0.200, True),
      _l("Plasterboard", 0.0125)),
     _steel(0.05, 0.40)),
    ("fraised", "Raised floor (crawl space)",
     "The ground floor of a wood house on a low wall: floorboards 20 · OSB "
     "18 · 2×10 joists every 16\" with insulation, nothing under — the "
     "crawl space below, its walls on strip footings",
     (_l("Floorboards", 0.020), _l("Subfloor OSB", 0.018),
      _l("Joists 2×10", 0.235, True)),
     _wood(0.038, 16 * IN, top=1)),
)
FLOOR_KEYS = tuple(k for k, *_r in FLOORS)


def floor(key: str):
    """(key, name, tip, layers, frame) — None: no such floor."""
    return next((m for m in FLOORS if m[0] == key), None)


def floor_set(key: str) -> dict:
    """What its card sets on a slab (and the next one drawn): a floor slab,
    none of YOUR types, its layers (ids l0, l1…, the core «core»), their
    sum, its joists."""
    m = floor(key)
    if m is None:
        return {}
    ls = [dict({k: v for k, v in la.items() if k != "mat"},
               id="core" if la["role"] == "core" else f"l{i}")
          for i, la in enumerate(m[3])]
    return {"t": round(sum(la["t"] for la in ls), 4), "ceiling": False,
            "block": False, "stype": "", "layers": ls,
            "frame": clean_frame(m[4])}
