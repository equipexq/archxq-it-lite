"""ArchXQ phase model — pure data, no Qt.

The workflow is a path of phases shown all at once on top — a guide, not
a lock: every phase is always open, each one's ✔ is its own progress.
Structure and Walls swap places with the structural system (frame vs
load-bearing walls).

Each phase offers ELEMENTS (its submenu). Picking an element shows its
drawing METHODS on the left and its PROPERTIES on the right.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Prop:
    name: str
    kind: str                     # len | int | angle | choice | text | check
    default: object = None
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class Method:
    label: str
    icon: str | None = None       # icons.icon() key (host's or ArchXQ's)


@dataclass(frozen=True)
class Element:
    key: str
    label: str                    # the submenu says WHAT (a verb when drawn)
    methods: tuple[Method, ...]   # the left strip says HOW
    props: tuple[Prop, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Phase:
    key: str
    label: str
    hint: str
    elements: tuple[str, ...]


def _e(key, label, methods, *props) -> Element:
    """methods: "Label" or ("Label", "icon_key")."""
    ms = tuple(Method(*m) if isinstance(m, tuple) else Method(m)
               for m in methods)
    return Element(key, label, ms, tuple(props))


L, I, A, C, T, K = "len", "int", "angle", "choice", "text", "check"
MATERIALS = ("Concrete", "Brick", "Block", "Wood", "Steel")

ELEMENTS: dict[str, Element] = {e.key: e for e in (
    # -- Project
    # (edited in the Project dialog — the panel shows a summary)
    _e("project_settings", "Project settings", ("Edit project…",)),
    _e("levels", "Levels", ("Add floor above", "Add basement",
                            "Edit levels…")),
    # -- Terrain: the submenu says what, the left strip how
    _e("plot", "Draw plot", (("Rectangle", "rectangle"),
                             ("Rectangle from centre", "rectangle_center"),
                             ("Rotated rectangle", "rotated_rect"),
                             ("Point by point", "geopath")),
       # («From survey points» comes back once it is made: a survey mixes
       # boundary and inner points — which ones close the plot is his call)
       Prop("Ground level", L, 0.0)),
    _e("plot_edit", "Edit plot", (("Move points", "move"),
                                  ("Add point", "add_point"),
                                  ("Delete point", "eraser"),
                                  ("Sides & heights…", "comp_nivel"),
                                  ("Fold line", "line"),
                                  ("Delete plot", "eraser")),
       Prop("Snap to", C, "Grid", ("Grid", "Survey points", "None"))),
    # the ground as measured: points inside the plot (a file, or clicked)
    _e("survey", "Survey points", (("Add point", "add_point"),
                                   ("Delete point", "eraser"),
                                   ("Points & import…", "survey"))),
    _e("setbacks", "Setbacks", (("Mark front sides", "offset"),),
       Prop("Front", L, 5.0), Prop("Back", L, 3.0), Prop("Sides", L, 1.5)),
    # (the bottom is chosen in the options bar, before drawing)
    _e("excavation", "Excavation", (("Rectangle", "rectangle"),
                                    ("Rectangle from centre",
                                     "rectangle_center"),
                                    ("Rotated rectangle", "rotated_rect"),
                                    ("Point by point", "geopath"),
                                    ("Circle", "circle"),
                                    ("Ramp", "ramp"))),
    # (the top — a height, a level, an elevation — in the options bar)
    _e("fill", "Fill / Platform", (("Rectangle", "rectangle"),
                                   ("Rectangle from centre",
                                    "rectangle_center"),
                                   ("Rotated rectangle", "rotated_rect"),
                                   ("Point by point", "geopath"),
                                   ("Circle", "circle"))),
    _e("excavation_edit", "Edit excavation / fill", (("Move points", "move"),
                                              ("Add point", "add_point"),
                                              ("Delete point", "eraser"),
                                              ("Delete excavation",
                                               "eraser"))),
    _e("ground", "Ground", (),
       Prop("Thickness", L, 0.5)),
    # -- Structure
    # -- Structure: how and how big — all in the options bar, as the walls
    _e("column", "Column", ()),
    _e("beam", "Beam", ()),
    _e("slab", "Slab", ()),
    _e("footing", "Footing", ()),
    # -- Walls
    # HOW it is drawn (rectangle, point by point, arc, circle…), its
    # alignment, thickness and height: all in the options bar (ArchiCAD's
    # Info Box) — the left strip has nothing to repeat. A partition is a
    # thinner wall; walls join by themselves.
    _e("wall", "Wall", (),
       Prop("Material", C, "Brick", MATERIALS)),
    _e("wall_import", "Walls from DXF", ()),
    # -- Openings
    # -- Openings: placed on a wall; sizes in the options bar
    _e("door", "Door", ()),
    _e("window", "Window", ()),
    _e("void", "Opening", ()),
    # -- Roof: one element; its type (gable, hip, flat + parapet), slope,
    # overhang… in the options bar, as the walls
    _e("roof", "Roof", ()),
    # -- Documentation
    # -- Documentation: made on the host's own sheets (the «+» by «Model»)
    # — options in the bar; the sheets are edited in the host's composer
    _e("rooms", "Rooms", ()),
    _e("sheets", "Drawings & sheets", ()),
    _e("section", "Section line", ()),
    _e("export", "Export (PDF / DXF)", ()),
)}

PHASES: dict[str, Phase] = {p.key: p for p in (
    Phase("project", "Project",
          "Name, floors, floor height, structural system, units.",
          ("project_settings", "levels")),
    Phase("terrain", "Terrain",
          "Draw the plot and the ground. Nothing else can start before it.",
          ("plot", "plot_edit", "survey", "setbacks", "excavation", "fill",
           "excavation_edit", "ground")),
    Phase("structure", "Structure",
          "Columns, beams, slabs and footings of the current floor.",
          ("column", "beam", "slab", "footing")),
    Phase("walls", "Walls",
          "Walls of the current floor, by axis, thickness and height.",
          ("wall", "wall_import")),
    Phase("openings", "Openings",
          "Doors and windows placed on the walls.",
          ("door", "window", "void")),
    Phase("roof", "Roof",
          "Roofs, eaves and parapets over the top floor.",
          ("roof",)),
    Phase("documentation", "Documentation",
          "Plans, sections and elevations on sheets, exported to PDF.",
          ("rooms", "sheets", "section", "export")),
)}

#: What the Lite leaves to ArchXQ IT Pro (his call, 2026-10-04): the
#: Lite draws the project, the terrain, the walls and the columns.
PRO_ELEMENTS = frozenset({
    "beam", "slab", "footing",
    "wall_import",
    "door", "window", "void",
    "roof",
    "rooms", "sheets", "section", "export",
})


def is_pro(key: str | None) -> bool:
    """True when ``key`` is an element only ArchXQ IT Pro draws."""
    return key in PRO_ELEMENTS


SYSTEMS = {
    "frame": "Frame (columns + beams)",
    "masonry": "Load-bearing walls",
}

#: The phases whose model parts can be shown / hidden in the view bar.
VISIBLE_PARTS = ("terrain", "structure", "walls", "openings", "roof")


def order(system: str) -> list[str]:
    """The phase path for a structural system."""
    mid = (["walls", "structure"] if system == "masonry"
           else ["structure", "walls"])
    return ["project", "terrain", *mid, "openings", "roof", "documentation"]


def reachable(key: str, done: set[str], system: str) -> bool:
    """Every phase is always open (his call, 2026-10-02): the phases are a
    GUIDE — the order and the ✔ show the way — never a lock. Real work is
    not linear (document the survey before the building, go back to the
    ground after the walls). What truly needs something first is the TOOL,
    and it says what is missing ("Draw the plot first")."""
    return key in PHASES


def next_open(done: set[str], system: str) -> str:
    """The first phase not yet done (the one the user should be on)."""
    for k in order(system):
        if k not in done:
            return k
    return order(system)[-1]
