"""The LIBRARY — the «intermediate step» between picking a tool and drawing.

His design, approved 2026-10-08 («maravilhoso… vende»): the right strip
(ArchXQ's tray tab) opens on the library of the element being drawn —
TYPE cards with pictures on top (a stair Straight / L / U, a door Swing /
Sliding / Arched…), PART chips below (the leaves, the hinge, the railing…).
The library says WHAT; the sizes stay in the options bar (HOW MUCH). It is
never a compulsory step: the last type used is already marked — whoever
knows what they want just draws. An element selected: its type is marked,
another card SWAPS it (one Ctrl+Z). «soon» items are greyed: the library
is meant to grow, and the user should see it.

``CATALOG``: per element key, its types and parts; each type / part
choice is a dict of the element's OPTIONS (ui's ``*_opts``) — and, through
``REC_KEYS``, of its records. ``LibraryPanel``: the widget. Pictures are
drawn here, in the icons' spirit (light ink, the host's orange).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QDialog, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QSlider, QToolButton, QToolTip,
                               QVBoxLayout, QWidget)

from . import edition
from . import favourites as FV
from . import profiles as PF

INK = QColor("#d6d9dd")
DIM = QColor("#6b7178")
ACCENT = QColor("#e8742c")
PX = 96


@dataclass(frozen=True)
class Type:
    key: str
    label: str
    pic: str                      # a picture of PICS
    set: dict | None              # the options it sets; None = «soon»
    tip: str = ""
    #: options it also sets for the NEXT one drawn (nothing selected) —
    #: never matched to mark the card (a shopfront's sizes)
    init: dict | None = None


@dataclass(frozen=True)
class Part:
    key: str                      # the option it sets
    label: str
    choices: tuple                # (value, label) or (value, label, "soon")
    show: object = None           # fn(opts) → shown?
    kind: str = "chips"           # chips | slider (0…1, live while dragged)
    #                               | size (a measure: bar + its field)
    size: tuple = ()              # size: (min, max, step, default)
    snaps: tuple = ()             # size: the usual sizes it is pulled to
    unit: str = "m"               # size: "m" | "%"
    also: tuple = ()              # size: ((key, value), …) set with it
    shift: float = 0.0            # size: shown = the option + shift (an
    #                               opening's edge, not its centre)
    tip: str = ""
    dflt: object = None           # chips: fn(opts) → the value shown while
    #                               unset (else the first choice)


@dataclass(frozen=True)
class Shelf:
    title: str
    types: tuple
    parts: tuple = field(default_factory=tuple)


def _one_leaf(o) -> bool:
    if _shop(o):
        return o.get("shop_door", "double") == "single"
    if _garage(o):
        return False
    return o.get("op") == "sliding" or int(o.get("leaves", 1) or 1) == 1


def _shop(o) -> bool:
    return o.get("op") == "shop"


#: the open grids (glazing.OPEN_KINDS — no Qt import here)
GRID_OPEN = ("square", "diamond", "lattice", "vslats", "hslats", "bars")


def _grid_open_kind(o) -> str:
    """An open grid's kind ("" for a glass one)."""
    k = o.get("kind")
    return k if k in GRID_OPEN else ""


def _not_shop(o) -> bool:
    return not _shop(o)


def _garage(o) -> bool:
    return o.get("op") == "garage"


def _plain_door(o) -> bool:
    """A door with leaves of its own — not a shopfront, not a garage door."""
    return not _shop(o) and not _garage(o)


def _size(key, label, lo, hi, step, default, snaps=(), show=None, unit="m",
          also=(), tip="") -> Part:
    """A measure dragged on a bar, its field beside it (his idea,
    2026-10-10: the spin boxes' arrows are fiddly)."""
    return Part(key, label, (), show, "size", (lo, hi, step, default),
                tuple(snaps), unit, tuple(also), tip=tip)


#: a feet / inches document: the bars' usual sizes, in INCHES, per (shelf,
#: measure) — what an American builder reaches for (3'0" × 6'8" doors, 42"
#: guards…). Others: the metric ones rounded to the inch.
IMPERIAL_SNAPS = {
    ("door", "w"): (24, 28, 30, 32, 36, 48, 60, 72),
    ("door", "h"): (80, 84, 96),
    ("window", "w"): (24, 36, 48, 60, 72),
    ("window", "h"): (24, 36, 48, 60, 72),
    ("window", "sill"): (24, 30, 36, 42),
    ("wall", "cw_s"): (48, 60),
    ("stair", "w"): (36, 42, 48),
    ("stair", "landing"): (36, 42, 48),
    ("stair", "tread"): (10, 11, 12),
    ("ramp", "w"): (36, 48, 60, 120),
    ("ramp", "landing"): (60,),
    ("guard", "h"): (36, 42),
    ("guard", "t"): (4, 6, 8),
    ("guard", "wall_h"): (12, 18, 24),
    ("guard", "gap_w"): (36,),
    ("guard", "step_h"): (4, 6, 8),
    ("street", "w"): (240, 288, 360),
    ("street", "walk"): (60, 72, 96),
    ("street", "curb"): (4, 6, 8),
    ("glazing", "op_w"): (36, 48, 60),
    ("glazing", "op_h"): (48, 80, 84),
    ("glazing", "op_sill"): (0, 36, 42),
}


def parse_measure(s: str, unit: str = "m") -> float | None:
    """A typed measure: «0,85» / «0.85 m» / «85 cm» / «850 mm» — a bare
    number over 10 read as centimetres (nobody means an 85 m door);
    «%» for a slope. None: not a number.

    A LENGTH in a document kept in mm / feet-inches (IngeTrazo 0.5.8 asks
    the units of every new document) — or typed with ' / ": read as the
    host's value box reads it, a bare number in the document's unit
    («3000» = 3 m in a mm document, not 30 m)."""
    if unit in ("m", "len"):
        from . import compat
        raw = (s or "").strip()
        if compat.doc_length_unit() != "m" or "'" in raw or '"' in raw:
            v = compat.parse_host_length(raw)
            if v is not None:
                return v
    t = (s or "").strip().lower().replace(",", ".").replace(" ", "")
    k = 1.0
    for suf, f in (("mm", 0.001), ("cm", 0.01), ("m", 1.0), ("%", 1.0),
                   ("°", 1.0)):
        if t.endswith(suf):
            t, k = t[:-len(suf)], f
            break
    else:
        k = None
    try:
        v = float(t)
    except ValueError:
        return None
    if unit == "m" and k is None and v > 10:
        k = 0.01
    return v * (k or 1.0)


def _turning(o) -> bool:
    return o.get("shape") in ("L", "U")


def _railed(o) -> bool:
    return (o.get("railing") or "none") != "none"


#: a stair's / ramp's way through the slab above (a customer's ask,
#: 2026-10-13): «None» keeps the slab whole — a hole is then drawn by hand
CUT_PART = Part("cut", "Opening in the slab",
                ((True, "Auto"), (False, "None")))
#: where the click is on the first step's edge (ramps.ANCHORS) — it was in
#: the window only (his ask, 2026-10-22: «in the right panel too»)
ANCHOR_PART = Part("anchor", "Insert at",
                   (("left", "Left corner"), ("centre", "Middle"),
                    ("right", "Right corner")))

#: a stair's / ramp's railing (railings.py) — Pro: "pro" chips are greyed
#: in the Lite
RAILING_PARTS = (
    Part("railing", "Railing", (("none", "None"),
                                ("handrail", "Handrail", "pro"),
                                ("steel", "Steel", "pro"),
                                ("glass", "Glass", "pro"),
                                ("wall", "Low wall", "pro"))),
    Part("rail_sides", "Sides (looking up)",
         (("auto", "Auto"), ("both", "Both"), ("left", "Left"),
          ("right", "Right")), _railed),
    Part("rail_infill", "Infill", (("vertical", "Balusters"),
                                   ("bars", "Bars"), ("cables", "Cables")),
         lambda o: o.get("railing") == "steel"),
    # the clear gap between balusters / bars (his ask, 2026-10-18: fewer of
    # them — a lighter model)
    _size("rail_clear", "Gap between bars", 0.05, 0.30, 0.01, 0.11,
          (0.11, 0.15, 0.20, 0.25),
          lambda o: o.get("railing") == "steel",
          tip="The clear gap between balusters (or bars, cables) — 11 cm "
              "is the most NBR 14718 allows where people can fall; wider: "
              "fewer bars, a lighter model"),
    Part("rail_fix", "Glass fixing", (("posts", "On posts"),
                                      ("frameless", "Frameless")),
         lambda o: o.get("railing") == "glass"),
    Part("rail_profile", "Handrail", (("round", "Round"),
                                      ("square", "Square")),
         lambda o: _railed(o) and (o.get("railing") != "wall"
                                   or bool(o.get("rail_wall_top")))),
    Part("rail_wall_top", "Handrail on the wall", ((False, "No"),
                                                   (True, "On top")),
         lambda o: o.get("railing") == "wall"),
    # the guard round the hole upstairs — off for a stair outside the
    # house, arriving at a balcony / a terrace (his test, 2026-10-10)
    Part("rail_floor", "Guard round the floor opening",
         ((True, "On"), (False, "Off")), _railed))

DOOR_SIZES = (
    _size("w", "Width", 0.50, 3.00, 0.05, 0.90,
          (0.60, 0.70, 0.80, 0.90, 1.00, 1.20, 1.60, 2.00, 2.40),
          _plain_door),
    _size("h", "Height", 1.80, 3.00, 0.05, 2.10, (2.10, 2.20, 2.40),
          _plain_door))
#: a GARAGE door (Badis, 2026-10-18): its kind and its sizes
GARAGE_PARTS = (
    Part("garage", "Kind", (("sectional", "Sectional"),
                            ("rollup", "Roll-up"),
                            ("tilt", "Up-and-over")), _garage),
    Part("gfinish", "Finish", (("steel", "Steel"), ("white", "White"),
                               ("anthracite", "Anthracite"),
                               ("wood", "Wood")), _garage),
    Part("gwin", "Windows", ((False, "None"), (True, "A row on top")),
         lambda o: _garage(o) and o.get("garage", "sectional") != "rollup"),
    _size("w", "Width", 2.00, 6.00, 0.05, 2.60,
          (2.40, 2.60, 3.00, 5.00), _garage),
    _size("h", "Height", 1.90, 3.50, 0.05, 2.20, (2.10, 2.20, 2.40),
          _garage))
GARAGE_INIT = {"w": 2.60, "h": 2.20}
#: a door's sizes again, when the next one drawn was a shopfront
DOOR_INIT = {"w": 0.90, "h": 2.10}
#: a SHOPFRONT (shopfront.py, 2026-10-11): the whole shop's front
SHOP_PARTS = (
    Part("shop_door", "Door", (("double", "2 leaves"), ("single", "1 leaf"),
                               ("sliding", "Sliding")), _shop),
    Part("door_at", "Door at", (("left", "Left"), ("centre", "Centre"),
                                ("right", "Right")), _shop),
    Part("shop_in", "Opens", ((False, "Out (to the street)"),
                              (True, "In")),
         lambda o: _shop(o) and o.get("shop_door", "double") != "sliding"),
    Part("transom", "Over the door", ((True, "Glass"), (False, "Panel")),
         _shop),
    Part("shutter", "Roll-up shutter", ((False, "No"), (True, "Yes")),
         _shop),
    Part("sign", "Sign band", ((False, "No"), (True, "Yes")), _shop),
    _size("w", "Width", 1.50, 12.00, 0.05, 4.00, (3.00, 4.00, 5.00, 6.00),
          _shop),
    _size("h", "Height", 2.20, 4.50, 0.05, 2.70, (2.60, 2.70, 3.00), _shop),
    _size("dh", "Door height", 2.00, 3.00, 0.05, 2.20, (2.10, 2.20, 2.40),
          _shop),
    _size("base", "Base under the glass", 0.0, 0.60, 0.05, 0.0,
          (0.0, 0.20, 0.40), _shop))
WINDOW_SIZES = (
    _size("w", "Width", 0.30, 4.00, 0.05, 1.20,
          (0.60, 0.80, 1.00, 1.20, 1.50, 2.00), _not_shop),
    _size("h", "Height", 0.30, 2.50, 0.05, 1.20,
          (0.60, 1.00, 1.20, 1.50, 2.10), _not_shop),
    _size("sill", "Sill", 0.00, 2.20, 0.05, 1.00, (0.90, 1.00, 1.10, 1.60)))
#: a window's sizes again, when the next one drawn was a shop window
WINDOW_INIT = {"w": 1.20, "h": 1.20, "sill": 1.00}
#: the panes see-through or OPAQUE (his ask, 2026-10-14: IngeTrazo has no
#: reflections and shows the lines behind any see-through glass — an opaque
#: pane reads as glass at a distance)
GLASS_PART = Part("glass", "Glass", (("clear", "See-through"),
                                     ("opaque", "Opaque")))
DOOR_GLASS_PART = Part("glass", "Glass", (("clear", "See-through"),
                                          ("opaque", "Opaque")),
                       lambda o: o.get("leaf") in ("glass", "half")
                       or o.get("op") == "shop")
#: doors & windows, batch 1 (openfinish.py, his go 2026-10-27): the leaf's
#: style, a handle, the colours. A record without them: as before
FRAME_COLOURS = (("white", "White"), ("black", "Black"), ("bronze", "Bronze"),
                 ("silver", "Silver"), ("wood", "Wood"))
HARDWARE_PART = Part("hw_c", "Handle colour", (("silver", "Silver"),
                                               ("black", "Black"),
                                               ("bronze", "Bronze")),
                     lambda o: o.get("handle", "none") != "none"
                     and _plain_door(o))


def _solid_leaf(o) -> bool:
    return _plain_door(o) and o.get("leaf", "solid") != "glass"


DOOR_FINISH_PARTS = (
    Part("leaf", "Leaf", (("solid", "Plain"), ("panels", "Panels"),
                          ("half", "Half glass"), ("glass", "Glass")),
         _plain_door, tip="Glass on a swing door: a french door"),
    Part("handle", "Handle", (("none", "None"), ("lever", "Lever"),
                              ("knob", "Knob"), ("pull", "Pull bar")),
         _plain_door),
    HARDWARE_PART,
    Part("leaf_c", "Leaf colour", (("wood", "Wood"), ("white", "White"),
                                   ("grey", "Grey"), ("black", "Black")),
         _solid_leaf),
    Part("frame_c", "Frame colour", FRAME_COLOURS, _plain_door))


def _win_op(*ops):
    return lambda o: o.get("op") in ops


def _trimmed(o) -> bool:
    return o.get("trim", "none") != "none"


def _stone(o) -> bool:
    return o.get("sill_k", "none") == "stone" and not _shop(o)


#: TRIM round a door / window and a STONE SILL under a window (trim.py,
#: his ask 2026-10-19: the façades' finish — each part its own material)
TRIM_PARTS = (
    Part("trim", "Trim", (("none", "None"), ("out", "Outside"),
                          ("both", "Both sides")),
         tip="A moulding round the opening, standing out of the wall"),
    _size("trim_w", "Trim width", 0.02, 0.40, 0.01, 0.08,
          (0.05, 0.08, 0.10, 0.15), _trimmed,
          tip="The moulding's face width"),
    _size("trim_d", "Trim projection", 0.005, 0.15, 0.005, 0.03,
          (0.02, 0.03, 0.05), _trimmed,
          tip="How far it stands out of the wall's face"))
SILL_PARTS = (
    Part("sill_k", "Stone sill", (("none", "None"), ("stone", "Stone")),
         _not_shop, tip="The stone under the window, outside"),
    _size("sill_d", "Sill projection", 0.0, 0.20, 0.01, 0.04,
          (0.03, 0.04, 0.05), _stone,
          tip="How far it stands out past the wall's face (or the trim's)"),
    _size("sill_t", "Sill thickness", 0.01, 0.12, 0.005, 0.03,
          (0.02, 0.03, 0.05), _stone),
    _size("sill_x", "Sill past the sides", 0.0, 0.20, 0.01, 0.03,
          (0.0, 0.03, 0.05), _stone,
          tip="How far it runs past the opening (or the trim) on each side"))


#: a window's SHAPE (shapes.py, PLANO_ABERTURAS_FORMA.md — 2026-10-31): the
#: option «oshape» (a window's «shape» is how it is drawn), its record's
#: «shape»; a card's leaves stay in an arch's rectangle
SHAPE_CHOICES = (("rect", "Rectangle"), ("round_arch", "Round arch"),
                 ("seg_arch", "Segmental arch"), ("pointed", "Pointed arch"),
                 ("pentagon", "Gable top"), ("trapezoid", "Trapezoid"),
                 ("triangle", "Triangle"), ("circle", "Circle"),
                 ("oval", "Oval"))


def _shaped(*shapes):
    return lambda o: not _shop(o) and o.get("oshape", "rect") in shapes


SHAPE_PARTS = (
    Part("oshape", "Shape", SHAPE_CHOICES, _not_shop, kind="icons",
         tip="The arches and the gable keep the leaves in their rectangle, "
             "a fixed light over them; the others are fixed glass"),
    _size("rise", "Rise", 0.05, 2.00, 0.01, 0.30, (0.20, 0.30, 0.40, 0.60),
          _shaped("seg_arch", "pointed", "pentagon"),
          tip="How high its top rises over its sides"),
    _size("top_w", "Top width", 0.05, 4.00, 0.05, 0.60, (0.40, 0.60, 0.80),
          _shaped("trapezoid"), tip="Its top's width, centred"))


def shape_changes(v: str, opts: dict) -> dict:
    """A shape picked: with ITS rise / top width for the window's width
    (the bar would show the last shape's)."""
    from . import shapes as SH
    w = float(opts.get("w", 1.2) or 1.2)
    ch = {"oshape": v}
    if v in SH.RISE:
        ch["rise"] = round(SH.RISE[v] * w, 2)
    if v == "trapezoid":
        ch["top_w"] = round(w / 2, 2)
    return ch


def shape_icon(s: str, px: int = 30, on: bool = False) -> QIcon:
    """The shape's outline, drawn in its box (the rectangle: the box)."""
    from . import shapes as SH
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(ACCENT if on else INK, 1.6))
    m, w, h = 5, px - 10, px - 10
    o = {"kind": "window", "shape": s, "pos": 0.5,
         "w": 0.7 if s == "oval" else 1.0, "h": 1.0, "sill": 0.0}
    o.update(SH.clean(o))
    if s == "pentagon":
        o["rise"] = 0.35
    loop = SH.outline(o, 0.0, steps=16) or [(0, 0), (1, 0), (1, 1), (0, 1)]
    path = QPainterPath()
    for i, (x, z) in enumerate(loop):
        q = QPointF(m + x * w, m + (1 - z) * h)
        path.moveTo(q) if i == 0 else path.lineTo(q)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return QIcon(pm)


#: a GRID's trim and sill — its HOST's (the Opening or the window it
#: fills; trim.HOST): his ask 2026-10-28, «the trim on every opening»
def _in_hole(o) -> bool:
    return o.get("place", "void") != "free"


def _host_trimmed(o) -> bool:
    return _in_hole(o) and o.get("op_trim", "none") != "none"


def _host_sill_ok(o) -> bool:
    return _in_hole(o) and float(o.get("op_sill", 0.0) or 0.0) > 1e-6


def _host_stone(o) -> bool:
    return _host_sill_ok(o) and o.get("op_sill_k", "none") == "stone"


GRID_TRIM_PARTS = (
    Part("op_trim", "Trim", (("none", "None"), ("out", "Outside"),
                             ("both", "Both sides")), _in_hole,
         tip="A moulding round its opening, standing out of the wall"),
    _size("op_trim_w", "Trim width", 0.02, 0.40, 0.01, 0.08,
          (0.05, 0.08, 0.10, 0.15), _host_trimmed,
          tip="The moulding's face width"),
    _size("op_trim_d", "Trim projection", 0.005, 0.15, 0.005, 0.03,
          (0.02, 0.03, 0.05), _host_trimmed,
          tip="How far it stands out of the wall's face"),
    Part("op_sill_k", "Stone sill", (("none", "None"), ("stone", "Stone")),
         _host_sill_ok, tip="The stone under its opening, outside"),
    _size("op_sill_d", "Sill projection", 0.0, 0.20, 0.01, 0.04,
          (0.03, 0.04, 0.05), _host_stone,
          tip="How far it stands out past the wall's face (or the trim's)"),
    _size("op_sill_t", "Sill thickness", 0.01, 0.12, 0.005, 0.03,
          (0.02, 0.03, 0.05), _host_stone),
    _size("op_sill_x", "Sill past the sides", 0.0, 0.20, 0.01, 0.03,
          (0.0, 0.03, 0.05), _host_stone,
          tip="How far it runs past the opening (or the trim) on each side"))


#: a window WITH LEAVES (2026-10-12, PLANO_JANELAS.md)
def _louvred(o) -> bool:
    return o.get("op") == "sliding" and o.get("louvred") is True


def _casement_n(o) -> int:
    from .structure import window_leaves
    return window_leaves(dict(o, op="casement"))


def _leaf_role(i: int) -> Part:
    """«Leaf i»: fixed, or hinged on its left / right — a casement of 2 or
    more leaves (2026-10-31, PLANO_JANELAS_FOLHAS.md)."""
    def roles(o):
        from .structure import casement_roles
        return casement_roles(dict(o, op="casement"))
    return Part(f"role{i}", f"Leaf {i}",
                (("F", "Fixed"), ("L", "Hinged left"), ("R", "Hinged right")),
                lambda o: o.get("op") == "casement" and _casement_n(o) >= i
                and _casement_n(o) > 1,
                tip="Left to right, seen from inside", dflt=lambda o:
                roles(o)[i - 1])


#: the leaves' rows go with their count: picking another count lays the
#: usual ones again (ui.library_pick)
ROLE_KEYS = tuple(f"role{i}" for i in range(1, 7))


WINDOW_LEAF_PARTS = (
    # a sliding one with LOUVRES (the veneziana — 2026-10-27, his: 3 = 2
    # louvred + 1 glass, 6 = 4 + 2). («louvred», not «shutter»: a shop
    # window's roll-up one)
    Part("louvred", "Louvres", ((False, "None"),
                                (True, "Louvred (veneziana)")),
         _win_op("sliding"),
         tip="Louvred leaves outside, the glass inside — the Brazilian "
             "veneziana"),
    Part("leaves", "Leaves", ((3, "3 (2 louvred + 1 glass)"),
                              (6, "6 (4 louvred + 2 glass)")), _louvred),
    Part("leaves", "Leaves", ((2, "2"), (3, "3"), (4, "4")),
         lambda o: o.get("op") == "sliding" and not _louvred(o)),
    Part("leaves", "Leaves", tuple((k, str(k)) for k in range(1, 7)),
         _win_op("casement")),
    *(_leaf_role(i) for i in range(1, 7)),
    # a pivot window (basculante): its panes, 0 = by its height
    Part("pv_panes", "Panes", ((0, "Auto"), (2, "2"), (3, "3"), (4, "4"),
                               (5, "5"), (6, "6")), _win_op("pivot")),
    Part("handle", "Handle", (("none", "None"), ("lever", "Lever")),
         _win_op("casement")),
    Part("hw_c", "Handle colour", (("silver", "Silver"), ("black", "Black"),
                                   ("bronze", "Bronze")),
         lambda o: o.get("op") == "casement"
         and o.get("handle", "none") != "none"),
    Part("frame_c", "Frame colour", FRAME_COLOURS, _not_shop),
    Part("swing", "Hinge", (("left", "Left"), ("right", "Right")),
         lambda o: o.get("op") == "casement" and _casement_n(o) == 1),
    Part("out", "Opens", ((False, "In"), (True, "Out")),
         _win_op("casement")),
    Part("open", "Open", (), _win_op("sliding", "casement", "awning",
                                     "pivot"),
         "slider"))
#: a SHOP WINDOW (shopfront.py, 2026-10-11): the shops' sides
SHOP_WINDOW_PARTS = (
    Part("transom", "Bar across", ((True, "Yes, glass over it"),
                                   (False, "No")), _shop),
    Part("shutter", "Roll-up shutter", ((False, "No"), (True, "Yes")),
         _shop),
    Part("sign", "Sign band", ((False, "No"), (True, "Yes")), _shop),
    _size("w", "Width", 0.80, 12.00, 0.05, 3.00, (2.00, 3.00, 4.00, 5.00),
          _shop),
    _size("h", "Height", 1.00, 4.50, 0.05, 2.70, (2.60, 2.70, 3.00), _shop),
    _size("dh", "Bar height", 1.00, 3.00, 0.05, 2.20, (2.10, 2.20, 2.40),
          lambda o: _shop(o) and bool(o.get("transom", True))),
    _size("base", "Base under the glass", 0.0, 0.60, 0.05, 0.0,
          (0.0, 0.20, 0.40), _shop))


def _slab_stack(*layers) -> list:
    """A ready-made slab's layers, top → bottom: (id, name, t, role)."""
    return [{"id": i, "name": n, "t": t, "role": r} for i, n, t, r in layers]


#: the ready-made slabs with LAYERS (slab layers, 2026-10-23)
SLAB_TILES = _slab_stack(("fl", "Porcelain tiles", 0.01, "finish"),
                         ("mb", "Mortar bed", 0.02, "finish"),
                         ("sc", "Screed", 0.04, "finish"),
                         ("co", "Concrete", 0.12, "core"),
                         ("pl", "Plaster", 0.015, "finish"))
SLAB_TIMBER = _slab_stack(("fl", "Timber boards", 0.02, "finish"),
                          ("ul", "Underlay", 0.005, "finish"),
                          ("sc", "Screed", 0.055, "finish"),
                          ("co", "Concrete", 0.12, "core"),
                          ("pl", "Plaster", 0.015, "finish"))
SLAB_ROOF = _slab_stack(("pr", "Protection", 0.03, "finish"),
                        ("wp", "Waterproofing", 0.01, "finish"),
                        ("sc", "Sloped screed", 0.03, "finish"),
                        ("co", "Concrete", 0.12, "core"),
                        ("pl", "Plaster", 0.015, "finish"))


CATALOG = {
    "door": Shelf("Doors", (
        # «top» square: an arched door is no Swing (the tie, 2026-10-27 —
        # Arched never marked; picking Swing takes the arch off)
        # (a card brings its handle: lever / pull — 2026-10-27)
        Type("swing", "Swing", "door_swing",
             {"op": "swing", "leaf": "solid", "top": "square"},
             "Hinged on a jamb, opens to the inside",
             dict(DOOR_INIT, handle="lever")),
        Type("sliding", "Sliding", "door_sliding",
             {"op": "sliding", "leaf": "solid"},
             "One leaf on a rail along the inside face; two part in the "
             "middle", dict(DOOR_INIT, handle="pull")),
        Type("glass", "Glass sliding", "door_glass",
             {"op": "sliding", "leaf": "glass"},
             "Glazed leaves in a slim dark frame, in two tracks — the "
             "curtain wall's look", dict(DOOR_INIT, handle="pull")),
        Type("shop", "Shopfront", "door_shop", {"op": "shop", "leaf": "glass"},
             "A shop's whole front: fixed glass panes and a glazed door, a "
             "transom, a base — a roll-up shutter and a sign band if you "
             "like. Selected: «Fill the bay» makes it pier to pier",
             {"w": 4.00, "h": 2.70, "sill": 0.0}),
        Type("garage", "Garage door", "door_garage",
             {"op": "garage", "leaf": "solid"},
             "A garage's door in steel: sectional (panels), roll-up (slats, "
             "with its box and guides inside) or up-and-over. «Open» lifts "
             "it", GARAGE_INIT),
        # (0.15.0, B6: its leaf up to the arch's spring, a half-round glass
        # light over it)
        Type("arched", "Arched", "door_arched",
             {"op": "swing", "top": "arched"},
             "A swing door under a round arch: the leaf up to where the arch "
             "springs, a half-round glass light over it",
             dict(DOOR_INIT, handle="lever"))),
        DOOR_FINISH_PARTS +
        (Part("leaves", "Leaves", ((1, "1"), (2, "2")), _plain_door),
         Part("swing", "Hinge · slides to", (("left", "Left"),
                                              ("right", "Right")),
              _one_leaf),
         # a swing door opens IN (the wall's inside) or OUT (a customer's
         # review, 2026-10-12: «it can only be inserted inward»)
         Part("out", "Opens", ((False, "In"), (True, "Out")),
              lambda o: o.get("op", "swing") == "swing"),
         Part("top", "Top", (("square", "Square"), ("arched", "Arched")),
              lambda o: o.get("op", "swing") == "swing"),
         Part("open", "Open", (), None, "slider"), DOOR_GLASS_PART)
        + SHOP_PARTS + GARAGE_PARTS + DOOR_SIZES + TRIM_PARTS),
    "window": Shelf("Windows", (
        Type("fixed", "Fixed", "win_fixed", {"op": "fixed"},
             "A frame and its glass", WINDOW_INIT),
        Type("shop", "Shop window", "win_shop", {"op": "shop"},
             "A shop's display window: fixed panes from the floor, in a "
             "slim dark frame — a bar across with glass over it, a base, a "
             "roll-up shutter and a sign band if you like. As high as the "
             "shopfront, so the lines meet round the corner",
             {"w": 3.00, "h": 2.70, "sill": 0.0}),
        Type("sliding", "Sliding", "win_sliding", {"op": "sliding"},
             "Glazed leaves in two tracks, sliding over each other — 2, 3 "
             "or 4 leaves", dict(WINDOW_INIT, w=1.50, leaves=2)),
        Type("casement", "Casement", "win_casement", {"op": "casement"},
             "Glazed leaves hinged on the jambs, opening in or out — 1 or "
             "2 leaves", dict(WINDOW_INIT, leaves=2)),
        Type("awning", "Awning", "win_awning", {"op": "awning"},
             "One leaf hinged at its top, its bottom pushed out (maxim-ar) "
             "— bathrooms, kitchens",
             {"w": 0.60, "h": 0.60, "sill": 1.50}),
        # (2026-10-27) the basculante
        Type("pivot", "Pivot", "win_pivot", {"op": "pivot"},
             "Horizontal panes, each turning on its middle (basculante) — "
             "bathrooms, service areas",
             {"w": 0.60, "h": 0.80, "sill": 1.40, "pv_panes": 0})),
        SHAPE_PARTS + WINDOW_LEAF_PARTS + (GLASS_PART,) + SHOP_WINDOW_PARTS
        + WINDOW_SIZES + TRIM_PARTS + SILL_PARTS),
    "wall": Shelf("Walls", (
        # (a ready-made card: none of YOUR types — «wtype» "" — and no
        # layers: one picked on a wall with layers makes it a plain one)
        Type("w15", "15 cm", "wall_15",
             {"t": 0.15, "cw": False, "wtype": "", "layers": None},
             "A 15 cm wall"),
        Type("w20", "20 cm", "wall_20",
             {"t": 0.20, "cw": False, "wtype": "", "layers": None},
             "A 20 cm wall"),
        Type("w10", "Partition", "wall_10",
             {"t": 0.10, "cw": False, "wtype": "", "layers": None},
             "A 10 cm partition"),
        Type("curtain", "Curtain wall", "wall_curtain",
             {"cw": True, "t": 0.15, "wtype": "", "layers": None},
             "Glass from floor to floor: mullions, and a dark band over "
             "each slab's edge — drawn, joined and moved as any wall. Its "
             "window (double-click): the mullions', transoms' and posts' "
             "widths and depths, the glass, the colours")),
        (Part("cw_band", "Band at each floor", ((True, "Yes"), (False, "No")),
              lambda o: bool(o.get("cw"))),
         # how high it rises over the floor — on the OUTER face, flush with
         # a wall below (his test, 2026-10-14: it was thick and set back)
         _size("cw_band_h", "Band over the floor", 0.0, 1.50, 0.01, 0.10,
               (0.0, 0.10, 0.30, 1.10),
               lambda o: bool(o.get("cw")) and bool(o.get("cw_band", True))),
         Part("cw_rows", "Rows of panes per floor",
              ((0, "1"), (1, "2"), (2, "3"), (3, "4")),
              lambda o: bool(o.get("cw"))),
         _size("cw_s", "Mullions every", 0.50, 3.00, 0.05, 1.25,
               (1.00, 1.25, 1.50, 2.00), lambda o: bool(o.get("cw"))))),
    "column": Shelf("Columns", (
        Type("rect", "Rectangular", "col_rect", {"section": "rect"}),
        Type("round", "Round", "col_round", {"section": "round"}))),
    "beam": Shelf("Beams", (
        Type("b1540", "15 × 40", "beam_s", {"w": 0.15, "h": 0.40}),
        Type("b2045", "20 × 45", "beam_m", {"w": 0.20, "h": 0.45}),
        Type("b2060", "20 × 60", "beam_l", {"w": 0.20, "h": 0.60}))),
    "slab": Shelf("Slabs", (
        # (a plain card: none of YOUR types — «stype» "" — and no layers)
        Type("s12", "12 cm", "slab_12",
             {"t": 0.12, "ceiling": False, "block": False, "stype": "",
              "layers": None}),
        Type("s15", "15 cm", "slab_15",
             {"t": 0.15, "ceiling": False, "block": False, "stype": "",
              "layers": None}),
        Type("s20", "20 cm", "slab_20",
             {"t": 0.20, "ceiling": False, "block": False, "stype": "",
              "layers": None}),
        # slabs with LAYERS (slab layers, 2026-10-23): its top the finished
        # floor, the finishes on top laid room by room
        Type("tiles", "Floor — tiles", "slab_tiles",
             {"t": 0.205, "ceiling": False, "block": False, "stype": "",
              "layers": SLAB_TILES},
             "A floor of tiles: porcelain 1 · mortar bed 2 · screed 4 on a "
             "12 cm slab, plaster 1.5 under it — its top is the finished "
             "floor; the walls stand on the slab"),
        Type("timber", "Floor — timber", "slab_timber",
             {"t": 0.215, "ceiling": False, "block": False, "stype": "",
              "layers": SLAB_TIMBER},
             "A timber floor: boards 2 · underlay 0.5 · screed 5.5 on a 12 cm "
             "slab, plaster 1.5 under it"),
        Type("roofslab", "Roof slab", "slab_roof",
             {"t": 0.225, "ceiling": False, "block": False, "stype": "",
              "layers": SLAB_ROOF},
             "A flat roof's slab: protection 3 · waterproofing 1 · sloped "
             "screed 3 on a 12 cm slab, plaster 1.5 under it"),
        # a CEILING (0.15.0, B4 — Badis' plenum, 2026-10-13): a board hung
        # at its own height over the floor; drawn as a slab («Inside the
        # walls»: a room's in one click), white by default
        Type("block", "Block", "slab_block", {"block": True, "ceiling": False},
             "A BLOCK — a platform, a bench, a mass: drawn as a slab "
             "(rectangle or point by point), its height and its base over "
             "the floor on the bars below"),
        Type("ceiling", "Ceiling", "slab_ceiling",
             {"ceiling": True, "block": False, "t": 0.02},
             "A suspended ceiling: a board at its own height over the floor "
             "(the plenum above it) — drawn as a slab, «Inside the walls» "
             "gives a room's in one click")),
        (_size("ch", "Ceiling height", 2.00, 5.00, 0.05, 2.60,
               (2.40, 2.50, 2.60, 2.70, 2.80, 3.00),
               lambda o: bool(o.get("ceiling")),
               tip="Its underside over the level's floor — what is seen "
                   "from the room"),
         _size("t", "Height", 0.05, 6.00, 0.05, 1.00,
               (0.15, 0.30, 0.45, 0.50, 0.75, 1.00, 1.10, 2.00, 3.00),
               lambda o: bool(o.get("block")),
               tip="How tall the block is (type more: up to 30 m)"),
         _size("base", "Base over the floor", -3.00, 6.00, 0.05, 0.0,
               (0.0,), lambda o: bool(o.get("block")),
               tip="Its bottom over the level's floor (under it: a pit; "
                   "over it: raised)"))),
    "stair": Shelf("Stairs", (
        Type("straight", "Straight", "stair_straight", {"shape": "straight"}),
        Type("L", "L", "stair_l", {"shape": "L"}),
        Type("U", "U", "stair_u", {"shape": "U"})),
        (Part("turn", "Turns", (("right", "Right"), ("left", "Left")),
              _turning),
         # Part B (2026-10-10): a slab under the steps, or open treads on
         # two steel stringers (the modern house's)
         Part("build", "Build", (("concrete", "Concrete"),
                                 ("open", "Open treads"),
                                 ("solid", "Solid"))),
         ANCHOR_PART,
         CUT_PART,
        ) + RAILING_PARTS + (
         _size("w", "Width", 0.60, 3.00, 0.05, 1.20,
               (0.80, 0.90, 1.00, 1.20, 1.50)),
         _size("gap", "Gap between flights", 0.0, 0.60, 0.05, 0.0,
               (0.0, 0.10, 0.20), lambda o: o.get("shape") == "U"),
         _size("landing", "Landing", 0.60, 3.00, 0.05, 1.20,
               (0.90, 1.00, 1.20, 1.50), _turning),
         # typed, it stays (Blondel's no more — the window's «Blondel»
         # button gives it back)
         _size("tread", "Tread", 0.25, 0.32, 0.005, 0.28, (0.28, 0.30),
               also=(("fix_tread", True),)),
         # a platform where it arrives (his idea, 2026-10-18)
         _size("top_landing", "Landing at the top", 0.0, 6.00, 0.05, 0.0,
               (0.0, 1.20, 1.50, 2.00),
               tip="A level platform where it arrives (0: none) — or push "
                   "the grip on its last step's front face"),
         # …and where it starts (his ask, 2026-10-23: stairs in a shaft)
         _size("foot_landing", "Landing at the bottom", 0.0, 6.00, 0.05,
               0.0, (0.0, 1.20, 1.50, 2.00),
               tip="A level platform where it starts (0: none) — the floor "
                   "the stair carries with it, copied with the level; or "
                   "push the grip on its first step"))),
    "ramp": Shelf("Ramps", (
        Type("straight", "Straight", "ramp_straight", {"shape": "straight"}),
        Type("L", "L", "ramp_l", {"shape": "L"}),
        Type("U", "U", "ramp_u", {"shape": "U"})),
        (Part("turn", "Turns", (("right", "Right"), ("left", "Left")),
              _turning),
         # a sloped slab, or a block down to the floor (2026-10-18)
         Part("build", "Build", (("slab", "Slab"), ("solid", "Solid"))),
         ANCHOR_PART,
         CUT_PART) + RAILING_PARTS + (
         _size("w", "Width", 0.80, 8.00, 0.10, 3.00,
               (1.20, 1.50, 3.00, 3.50, 5.50)),
         _size("landing", "Landing", 0.60, 8.00, 0.10, 3.00, (1.50, 3.00),
               _turning),
         _size("slope", "Slope", 1.0, 25.0, 0.5, 20.0,
               (5.0, 8.33, 12.5, 20.0), unit="%",
               also=(("fix", "slope"),)),
         _size("top_landing", "Landing at the top", 0.0, 6.00, 0.05, 0.0,
               (0.0, 1.20, 1.50, 2.00),
               tip="A level platform where it arrives (0: none) — or push "
                   "the grip on its top edge"),
         _size("foot_landing", "Landing at the bottom", 0.0, 6.00, 0.05,
               0.0, (0.0, 1.20, 1.50, 2.00),
               tip="A level platform where it starts (0: none) — or push "
                   "the grip on its bottom edge"))),
    # low walls & guards (guards.py, his go 2026-10-15 — Pro)
    "guard": Shelf("Low walls & guards", (
        Type("wall", "Low wall", "guard_wall", {"kind": "wall"},
             "Masonry, 1.10 m by default — a coping on top if you like",
             {"h": 1.10}),
        Type("wallrail", "Low wall + railing", "guard_wallrail",
             {"kind": "wallrail"},
             "A low wall with a steel or glass railing over it",
             {"h": 1.10}),
        Type("glass", "Glass", "guard_glass", {"kind": "glass"},
             "Glass in a channel on the floor (or on posts), a top rail",
             {"h": 1.10}),
        Type("steel", "Steel", "guard_steel", {"kind": "steel"},
             "Posts and a top rail — balusters, bars or cables "
             "(11 cm clear at most)", {"h": 1.10}),
        # the plot's wall (phase C, 2026-10-17): 2 m, piers, a coping
        Type("boundary", "Boundary wall", "guard_boundary",
             {"kind": "boundary"},
             "A plot's wall — 2.00 m, piers every 3 m, a coping; gates in "
             "its gaps", {"h": 2.00, "cap": True})),
        (Part("how", "How", (("draw", "Draw"), ("edge", "Slab edge"),
                             ("hole", "Round an opening"),
                             ("gap", "Add a gap"), ("gate", "Add a gate")),
              tip="Draw: point by point. Slab edge: click a slab — its free "
                  "edges (no wall) get one. Round an opening: click a "
                  "slab's opening — open where a stair arrives. Add a gap: "
                  "click on one — a passage there. Add a gate: click a gap "
                  "(or a wall: a gap is opened with it)"),
         _size("gap_w", "Gap width", 0.30, 8.00, 0.05, 0.90,
               (0.80, 0.90, 1.20, 3.00), lambda o: o.get("how") in ("gap",
                                                                  "gate")),
         Part("gate_kind", "Gate", (("swing", "Swing"),
                                    ("sliding", "Sliding")),
              lambda o: o.get("how") == "gate",
              tip="Swing: on hinges at the gap's edges, opening into the "
                  "plot. Sliding: on a rail along the inside face"),
         Part("gate_leaves", "Leaves", ((1, "One"), (2, "Two")),
              lambda o: o.get("how") == "gate"),
         Part("gate_style", "Infill", (("bars", "Bars"), ("solid", "Plate"),
                                       ("slats", "Slats")),
              lambda o: o.get("how") == "gate"),
         Part("gate_finish", "Finish", (("anthracite", "Anthracite"),
                                        ("steel", "Steel"),
                                        ("white", "White"),
                                        ("wood", "Wood")),
              lambda o: o.get("how") == "gate",
              tip="Wood slats come in an anthracite frame — two colours"),
         Part("gate_open", "Shown", ((0.0, "Closed"), (0.35, "Ajar"),
                                     (1.0, "Open")),
              lambda o: o.get("how") == "gate"),
         Part("on", "Stands on", (("auto", "Auto"), ("floor", "Floor"),
                                  ("ground", "Ground"), ("roof", "Roof")),
              tip="Auto: on a slab of its level where there is one, else "
                  "the ground. Floor: flat, on its level's floor. Ground: "
                  "on the terrain point by point — its top that high over "
                  "it. Roof: on top of its level's flat roof (a parapet "
                  "on the building)"),
         _size("base", "Bottom above it", -1.0, 6.0, 0.01, 0.0,
               (0.0, 0.10, 0.20),
               tip="Its bottom face this high over what it stands on (the "
                   "slab, the roof, the ground; Floor: the level's zero). "
                   "0 = sitting on it"),
         Part("top", "Top on a slope", (("stepped", "Stepped"),
                                        ("slope", "Follows the slope")),
              lambda o: o.get("kind", "wall") in ("wall", "wallrail", "boundary")
              and o.get("on", "auto") not in ("floor", "roof"),
              tip="Stepped: level steps, each one at most the step's height "
                  "(masonry). Follows the slope: its top that high over the "
                  "ground the whole way"),
         Part("cap", "Top", ((False, "Plain"), (True, "Coping")),
              lambda o: o.get("kind", "wall") in ("wall", "boundary")),
         Part("rail_top", "Railing", (("steel", "Steel"), ("glass", "Glass")),
              lambda o: o.get("kind") == "wallrail"),
         Part("rail_infill", "Infill", (("vertical", "Balusters"),
                                        ("bars", "Bars"),
                                        ("cables", "Cables")),
              lambda o: o.get("kind") == "steel" or (
                  o.get("kind") == "wallrail"
                  and o.get("rail_top", "steel") == "steel")),
         _size("rail_clear", "Gap between bars", 0.05, 0.30, 0.01, 0.11,
               (0.11, 0.15, 0.20, 0.25),
               lambda o: o.get("kind") == "steel" or (
                   o.get("kind") == "wallrail"
                   and o.get("rail_top", "steel") == "steel"),
               tip="The clear gap between balusters (or bars, cables) — "
                   "11 cm is the most NBR 14718 allows where people can "
                   "fall; wider: fewer bars, a lighter model"),
         Part("rail_fix", "Glass fixing", (("frameless", "Frameless"),
                                           ("posts", "On posts")),
              lambda o: o.get("kind") == "glass"),
         Part("insert", "The line drawn is its", (("centre", "Centre"),
                                                  ("left", "Left face"),
                                                  ("right", "Right face")),
              lambda o: o.get("how", "draw") == "draw",
              tip="Draw along a slab's edge or a wall's face: the line is "
                  "that face (Tab while drawing: the other one)"),
         _size("h", "Height", 0.30, 3.00, 0.05, 1.10,
               (0.90, 1.00, 1.10, 1.20, 1.80, 2.00)),
         _size("t", "Thickness", 0.05, 0.60, 0.01, 0.15,
               (0.10, 0.15, 0.20),
               lambda o: o.get("kind", "wall") in ("wall", "wallrail", "boundary")),
         _size("pier_s", "Piers every", 0.0, 10.0, 0.05, 3.00,
               (0.0, 2.50, 3.00, 4.00), lambda o: o.get("kind") == "boundary",
               tip="Piers at its ends, bends, steps and gaps, and at most "
                   "this far apart — 0 = none"),
         _size("wall_h", "Low wall under it", 0.10, 1.50, 0.05, 0.40,
               (0.30, 0.40, 0.60), lambda o: o.get("kind") == "wallrail"),
         _size("step_h", "Each step at most", 0.05, 0.50, 0.01, 0.15,
               (0.10, 0.15, 0.20, 0.30),
               lambda o: o.get("kind", "wall") in ("wall", "wallrail", "boundary")
               and o.get("on", "auto") not in ("floor", "roof")
               and o.get("top", "stepped") == "stepped"))),
    # «Surroundings» (streets.py, his OK 2026-10-25 — Pro): all that is
    # outside the building; a street first
    "street": Shelf("Surroundings", (
        Type("street", "Street", "street", {},
             "Asphalt, curbs and sidewalks — along a side of the plot in "
             "one click, or by its axis; where two meet, the corner turns "
             "round"),),
        (Part("how", "How", (("plot", "Along the plot"),
                             ("axis", "By axis")),
              tip="Along the plot: click a side of the plot — the street "
                  "runs along it, outside; the next side clicked turns the "
                  "corner. By axis: its axis point by point, as walls"),
         Part("align", "Line drawn", (("centre", "Axis"),
                                      ("out", "Street outside"),
                                      ("in", "Street inside")),
              lambda o: (o.get("how") == "axis") if "how" in o
              else not o.get("edges"),
              tip="By axis: the line you click is the street's axis — or "
                  "its sidewalk's back edge, the whole street outside it "
                  "(round a block: outside the ring) or inside it"),
         Part("sides", "Sidewalks", (("both", "Both"), ("plot", "Plot side"),
                                    ("none", "None"))),
         Part("line", "Centre line", ((False, "None"), (True, "Yellow"))),
         _size("w", "Road width", 2.0, 40.0, 0.10, 7.00,
               (5.00, 6.00, 7.00, 9.00, 12.00)),
         _size("walk", "Sidewalk", 0.50, 10.0, 0.05, 2.00,
               (1.50, 2.00, 2.50, 3.00),
               lambda o: o.get("sides", "both") != "none"),
         _size("curb", "Curb height", 0.0, 0.40, 0.01, 0.15,
               (0.10, 0.15, 0.20),
               lambda o: o.get("sides", "both") != "none",
               tip="The sidewalk's top over the road (0: level with it)"),
         _size("r", "Corner radius", 0.0, 20.0, 0.50, 5.00,
               (3.00, 5.00, 8.00),
               tip="Where two streets meet: the curb turns the corner "
                   "round this radius"))),
    # Tools ▸ Along a path ▸ PROFILES (along.py — Pro, PLANO_TOOLS_CAMINHO.md
    # 2026-10-29): a card = a profile, and where it comes to sit
    "profile": Shelf("Profiles", tuple(
        Type(k, PF.label(k), f"profile_{k}", {"profile": k},
             PF.NATIVE[k][5],
             {"anchor": PF.anchor_of(k)[0]} | (
                 {"z": PF.anchor_of(k)[1]} if PF.anchor_of(k)[0] == "height"
                 else {}))
        for k in PF.NATIVE),
        (Part("how", "How", PF.HOWS,
              tip="By room: click inside a room — the profile runs round its "
                  "walls, stopping at the doors, and follows them when they "
                  "move. Point by point: along a line you draw on a wall's "
                  "face (Tab: the other side). By wall face: click a wall's "
                  "face — all of it (Shift + click: the next face joins). "
                  "By element: click a column or a beam — round it (Floor: "
                  "its base, Ceiling: its top)"),
         Part("anchor", "On", PF.ANCHORS,
              tip="Floor: a baseboard. Ceiling: a crown, its top under the "
                  "slab above. Height: its foot this high over the floor. "
                  "Wall top: its top at the top of the wall it runs along "
                  "(a cornice)"),
         _size("z", "Height", 0.0, 6.0, 0.05, 0.90,
               (0.90, 1.00, 2.80), lambda o: o.get("anchor") == "height",
               tip="Its foot over the level's floor"),
         Part("cut", "Doors & windows", ((True, "Stops at them"),
                                        (False, "Runs on")),
              tip="Where a door or a window crosses it, it stops (round the "
                  "trim) — or runs on over it"),
         Part("run", "Run", PF.RUNS,
              tip="Continuous: one piece. Repeat: pieces this long with a "
                  "gap between them, spread evenly (a broken frieze, deck "
                  "boards)"),
         _size("piece", "Piece", 0.05, 10.0, 0.05, 0.60,
               (0.20, 0.30, 0.60, 1.00), lambda o: o.get("run") == "repeat"),
         _size("gap", "Gap", 0.0, 5.0, 0.01, 0.30,
               (0.05, 0.10, 0.30, 0.50), lambda o: o.get("run") == "repeat"))),
    # Tools ▸ Along a path ▸ COPIES (copies.py — Pro, part 4): a card = the
    # object copied; «Selected object» takes the one selected in the model
    "copy": Shelf("Copies", tuple(
        Type(k, PF.COPY_OBJECTS[k][0], f"copy_{k}", {"obj": k},
             PF.COPY_OBJECTS[k][1])
        for k in PF.COPY_OBJECTS) + (
        Type(PF.COPY_MINE, "Selected object", "copy_mine",
             {"obj": PF.COPY_MINE},
             "Select a group in the model, then this card: it is copied "
             "along the path (its foot on the floor)"),),
        (Part("how", "How", PF.COPY_HOWS,
              tip="By room: click inside a room — the copies run round its "
                  "walls. Point by point: along a line you draw. By wall "
                  "face: along a wall's face (Shift + click: the next face "
                  "joins)"),
         Part("mode", "Where", PF.COPY_MODES,
              tip="Whole path: spread over all of it. Each segment: each "
                  "side on its own, a copy at every corner. Corners only: "
                  "one at each corner"),
         Part("by", "Spread by", PF.COPY_BY,
              lambda o: o.get("mode", "path") != "corners",
              tip="Count: this many. Spacing: at most this far apart, "
                  "evenly. Gap: this clear space between them (a fence)"),
         Part("count", "Count", tuple((n, str(n)) for n in
                                      (2, 3, 4, 5, 6, 8, 10, 12, 16, 20)),
              lambda o: o.get("mode", "path") != "corners"
              and o.get("by", "spacing") == "count"),
         _size("spacing", "Spacing", 0.20, 50.0, 0.05, 2.00,
               (1.00, 1.50, 2.00, 3.00, 5.00),
               lambda o: o.get("mode", "path") != "corners"
               and o.get("by", "spacing") == "spacing"),
         _size("gap", "Gap", 0.0, 10.0, 0.01, 0.10,
               (0.05, 0.10, 0.15, 0.20),
               lambda o: o.get("mode", "path") != "corners"
               and o.get("by", "spacing") == "gap"),
         Part("ends", "Ends", ((True, "A copy at each"), (False, "Inside")),
              lambda o: o.get("mode", "path") != "corners"
              and o.get("by", "spacing") == "count"),
         Part("turn", "Turns", PF.COPY_TURN),
         Part("rot", "Rotation", ((0.0, "0°"), (90.0, "90°"),
                                  (180.0, "180°"), (270.0, "270°"))),
         _size("off", "Off the line", -5.0, 5.0, 0.05, 0.0,
               (0.0, 0.30, 0.50, 1.00),
               tip="How far from the line (or the walls) — the side: Tab "
                   "while drawing"),
         _size("base", "Raised", -2.0, 10.0, 0.05, 0.0, (0.0,),
               tip="Its foot over the level's floor"),
         Part("cut", "Doors", ((True, "Skips them"), (False, "Runs on")),
              lambda o: o.get("how") in ("room", "face"),
              tip="No copy in front of a door"))),
    # GRIDS (glazing.py — Pro): glass grids (his go 2026-10-15) and, since
    # 2026-10-27 (PLANO_GRADES.md), the open ones — a cobogó, a lattice,
    # slats. A card sets its kind's sizes (glazing.KIND_SET, copied here:
    # the library needs no Qt model of its own)
    "glazing": Shelf("Grids", (
        Type("industrial", "Industrial", "glaz_industrial",
             {"kind": "industrial"},
             "Thin black steel, small square panes (about 50 × 50)",
             {"by": "size", "pw": 0.50, "ph": 0.50, "fw": 0.03, "fd": 0.05,
              "mw": 0.025, "md": 0.04, "frame": "black", "fr_on": True}),
        Type("aluminium", "Aluminium", "glaz_aluminium",
             {"kind": "aluminium"},
             "A wider silver frame, big panes (about 1.00 × 1.00)",
             {"by": "size", "pw": 1.00, "ph": 1.00, "fw": 0.05, "fd": 0.07,
              "mw": 0.04, "md": 0.06, "frame": "silver", "fr_on": True}),
        Type("partition", "Partition", "glaz_partition",
             {"kind": "partition"},
             "A glass partition: vertical muntins only",
             {"by": "size", "pw": 0.90, "fw": 0.04, "fd": 0.06, "mw": 0.03,
              "md": 0.05, "frame": "dark", "fr_on": True}),
        Type("arched", "Arched top", "glaz_arched", None, "Coming"),
        Type("round", "Round", "glaz_round", None, "Coming"),
        Type("square", "Square", "grid_square", {"kind": "square"},
             "An open square grid, no glass — black iron bars (about 15 × "
             "15)",
             {"by": "size", "pw": 0.15, "ph": 0.15, "fw": 0.03, "fd": 0.03,
              "mw": 0.02, "md": 0.02, "frame": "black", "fr_on": True}),
        Type("diamond", "Diamond", "grid_diamond", {"kind": "diamond"},
             "An open diamond grid, no glass — black iron bars (cells about "
             "30 × 15)",
             {"by": "size", "pw": 0.30, "ph": 0.15, "fw": 0.03, "fd": 0.03,
              "mw": 0.02, "md": 0.02, "frame": "black", "fr_on": True}),
        Type("lattice", "Lattice", "grid_lattice", {"kind": "lattice"},
             "A timber lattice: flat laths crossed at 45° (about 12 × 12)",
             {"by": "size", "pw": 0.12, "ph": 0.12, "fw": 0.04, "fd": 0.03,
              "mw": 0.04, "md": 0.015, "frame": "wood", "fr_on": True}),
        Type("vslats", "Vertical slats", "grid_vslats", {"kind": "vslats"},
             "Timber slats side by side (4 × 4 cm, 3 cm apart), no frame",
             {"by": "size", "pw": 0.07, "fw": 0.04, "fd": 0.04, "mw": 0.04,
              "md": 0.04, "frame": "wood", "fr_on": False}),
        Type("hslats", "Horizontal slats", "grid_hslats", {"kind": "hslats"},
             "Aluminium louvres one over the other (10 cm, 18 cm apart)",
             {"by": "size", "ph": 0.18, "fw": 0.03, "fd": 0.03, "mw": 0.10,
              "md": 0.02, "frame": "silver", "fr_on": True}),
        # D7 (2026-10-27): on a WINDOW, outside — it follows the window
        Type("bars", "Security bars", "grid_bars", {"kind": "bars"},
             "Security bars on a window, outside: 16 mm bars 12 cm apart "
             "through 2 flat bars — click the window",
             {"by": "size", "pw": 0.12, "fw": 0.03, "fd": 0.02, "mw": 0.016,
              "md": 0.016, "rows": 2, "frame": "black", "fr_on": True})),
        (Part("place", "Where", (("void", "In an Opening"),
                                 ("free", "Free (2 points)")),
              lambda o: o.get("kind") != "bars",
              tip="In an Opening: click a wall's Opening (a void) — it "
                  "fills it, and follows it. Free: two points, a "
                  "partition anywhere"),
         Part("by", "Panes by", (("size", "Their size"),
                                 ("count", "Columns × rows")),
              lambda o: not _grid_open_kind(o)),
         Part("frame", "Frame", (("black", "Black"), ("dark", "Dark"),
                                 ("silver", "Silver"), ("white", "White"),
                                 ("bronze", "Bronze")),
              lambda o: not _grid_open_kind(o)),
         Part("frame", "Colour", (("black", "Black"), ("dark", "Dark"),
                                  ("silver", "Silver"), ("white", "White"),
                                  ("bronze", "Bronze"), ("wood", "Wood")),
              _grid_open_kind),
         Part("fr_on", "Frame", ((True, "Yes"), (False, "No")),
              _grid_open_kind),
         Part("bead", "Glazing bead", ((True, "Both faces"), (False, "None")),
              lambda o: not _grid_open_kind(o)),
         Part("opaque", "Glass", ((False, "See-through"), (True, "Opaque")),
              lambda o: not _grid_open_kind(o)),
         _size("pw", "Pane width", 0.10, 3.00, 0.05, 0.50, (0.30, 0.50, 1.00),
               lambda o: o.get("by", "size") == "size"
               and not _grid_open_kind(o)),
         _size("ph", "Pane height", 0.10, 3.00, 0.05, 0.50, (0.30, 0.50, 1.00),
               lambda o: o.get("by", "size") == "size"
               and o.get("kind") != "partition" and not _grid_open_kind(o)),
         # the open ones: their cell (slats: from one to the next)
         _size("pw", "Cell width", 0.03, 1.50, 0.01, 0.15,
               (0.07, 0.12, 0.15, 0.30),
               lambda o: _grid_open_kind(o) in ("square", "diamond",
                                                "lattice")),
         _size("ph", "Cell height", 0.03, 1.50, 0.01, 0.15,
               (0.12, 0.15, 0.30),
               lambda o: _grid_open_kind(o) in ("square", "diamond",
                                                "lattice")),
         _size("pw", "Slat spacing", 0.03, 1.00, 0.005, 0.07,
               (0.06, 0.07, 0.10),
               lambda o: _grid_open_kind(o) == "vslats",
               tip="From one slat to the next (the slat and its gap)"),
         _size("ph", "Slat spacing", 0.03, 1.00, 0.005, 0.18,
               (0.12, 0.18, 0.25),
               lambda o: _grid_open_kind(o) == "hslats",
               tip="From one louvre to the next (the louvre and its gap)"),
         _size("pw", "Bar spacing", 0.06, 0.30, 0.005, 0.12,
               (0.10, 0.12, 0.15),
               lambda o: _grid_open_kind(o) == "bars",
               tip="From one bar to the next"),
         _size("rows", "Flat bars", 0, 6, 1, 2, (1, 2, 3),
               lambda o: _grid_open_kind(o) == "bars", unit="",
               tip="The flat bars across, evenly spaced"),
         _size("mw", "Bar width", 0.005, 0.20, 0.005, 0.02,
               (0.02, 0.04, 0.10), _grid_open_kind,
               tip="The bar as seen from the front"),
         _size("md", "Bar depth", 0.005, 0.20, 0.005, 0.02,
               (0.015, 0.02, 0.04), _grid_open_kind,
               tip="The bar through the wall"),
         _size("cols", "Columns", 1, 20, 1, 4, (2, 3, 4, 6),
               lambda o: o.get("by") == "count" and not _grid_open_kind(o),
               unit=""),
         _size("rows", "Rows", 1, 20, 1, 4, (2, 3, 4, 6),
               lambda o: o.get("by") == "count"
               and o.get("kind") != "partition" and not _grid_open_kind(o),
               unit=""),
         # his first ask: push the glass in / out inside the frame
         _size("gpos", "Glass from the outer face", 0.0, 0.10, 0.001, 0.025,
               (0.01, 0.025), lambda o: not _grid_open_kind(o)),
         _size("fw", "Frame width", 0.01, 0.15, 0.005, 0.03,
               (0.03, 0.05, 0.08), lambda o: o.get("fr_on", True) is not False
               or not _grid_open_kind(o)),
         _size("fd", "Frame depth", 0.01, 0.20, 0.005, 0.05,
               (0.05, 0.07, 0.10), lambda o: o.get("fr_on", True) is not False
               or not _grid_open_kind(o)),
         # in an Opening: ITS sizes — the opening changes, the grid follows
         # (his test, 2026-10-15: they must go together)
         # (on a window: the WINDOW's — the bars follow it)
         _size("op_w", "Width", 0.30, 6.00, 0.05, 1.20, (0.80, 1.20, 1.60),
               lambda o: o.get("place", "void") != "free"),
         _size("op_h", "Height", 0.30, 4.00, 0.05, 2.00, (1.20, 2.00, 2.10),
               lambda o: o.get("place", "void") != "free"),
         _size("op_sill", "Sill", 0.0, 3.00, 0.05, 0.0, (0.0, 0.90, 1.10),
               lambda o: o.get("place", "void") != "free"),
         _size("h", "Height", 0.20, 6.00, 0.05, 2.10, (1.00, 2.10, 2.60),
               lambda o: o.get("place") == "free"),
         _size("base", "Sill", 0.0, 3.00, 0.05, 0.0, (0.0, 0.90, 1.10),
               lambda o: o.get("place") == "free")) + GRID_TRIM_PARTS),
    "roof": Shelf("Roofs", (
        Type("gable", "Gable", "roof_gable", {"kind": "gable"},
             "Two slopes, a triangle of wall at each end"),
        Type("hip", "Hip", "roof_hip", {"kind": "hip"},
             "Four slopes, eaves all round"),
        Type("flat", "Flat", "roof_flat", {"kind": "flat"},
             "A slab, with a parapet if you like"),
        Type("shed", "Shed", "roof_shed", {"kind": "shed"},
             "One slope; the end walls and the high wall rise to it"),
        Type("hidden", "Hidden", "roof_hidden", {"kind": "hidden"},
             "Low slopes of sheets behind a parapet, falling into a "
             "gutter — the modern house's roof"),
        # (0.15.0, B6 — on a rectangle)
        Type("butterfly", "Butterfly", "roof_butterfly", {"kind": "butterfly"},
             "Two slopes falling to a valley along the middle — high at the "
             "eaves (the walls rise to it)"),
        Type("mansard", "Mansard", "roof_mansard", {"kind": "mansard"},
             "On every side a steep slope, then a gentle hip roof over it — "
             "its «Break height» on the bar"),
        # one click: a hip roof over this level's walls when they are an
        # L (roof_l.py), a T, a U or any other plan (roof_any.py, 0.12.0 —
        # Hip / Gable «Over the walls» make them too)
        Type("lt", "L / T / U plan", "roof_lt",
             {"kind": "hip", "lplan": True},
             "One click: a hip roof over this level's walls, whatever their "
             "plan — L, T, U, oblique: hips outside, valleys inside")),
        (Part("ridge", "Ridge along", (("long", "Long side"),
                                       ("short", "Short side")),
              lambda o: o.get("kind") == "gable"),
         Part("slopes", "Slopes", ((1, "One"), (2, "Two")),
              lambda o: o.get("kind") == "hidden"),
         Part("fall", "Falls to", (("right", "This side"),
                                   ("left", "The other side")),
              lambda o: o.get("kind") == "shed" or (
                  o.get("kind") == "hidden" and int(o.get("slopes", 2)) == 1)),
         Part("pauto", "Parapet height (Auto = just hides the roof)",
              ((True, "Auto"), (False, "Typed")),
              lambda o: o.get("kind") == "hidden"),
         # its measures on bars, as the walls' and the low walls' (his ask,
         # 2026-10-18 — before, only the options bar and «Sizes & details»)
         _size("slope", "Slope", 3.0, 60.0, 0.5, 30.0,
               (10.0, 15.0, 22.5, 30.0, 35.0, 45.0),
               lambda o: o.get("kind") != "flat", unit="°",
               tip="Drag: the selected roofs follow — it pulls to the usual "
                   "slopes; Shift = 0.1° by 0.1°. Double click: 30°"),
         _size("overhang", "Overhang", 0.0, 1.50, 0.05, 0.50,
               (0.30, 0.50, 0.60, 0.80, 1.00),
               lambda o: o.get("kind") != "hidden"),
         _size("mh", "Break height", 0.30, 4.00, 0.05, 1.20,
               (0.80, 1.00, 1.20, 1.50, 2.00),
               lambda o: o.get("kind") == "mansard",
               tip="How high the steep lower part rises over the walls"),
         _size("t", "Thickness", 0.05, 0.60, 0.01, 0.20,
               (0.10, 0.15, 0.20, 0.25, 0.30)),
         _size("parapet", "Parapet", 0.0, 2.00, 0.05, 1.00,
               (0.0, 0.50, 1.00, 1.10),
               lambda o: o.get("kind") == "flat" or (
                   o.get("kind") == "hidden" and not o.get("pauto", True))))),
}

#: the «Building elements» (the left section, not phases): set up in the
#: library — type and details as cards / chips, then a preview; their sizes
#: and levels in their own window (his call, 2026-10-09)
BUILDING_ELEMENTS = ("stair", "ramp")

#: an option whose RECORD key is another (a column's «section» is its
#: record's «shape»)
REC_KEYS = {"column": {"section": "shape"},
            # a wall's TYPE (0.15.0): the option «wtype», the record «type»
            "wall": {"wtype": "type"},
            # a window's SHAPE (2026-10-31): its option «shape» is how it
            # is drawn (on a wall)
            "window": {"oshape": "shape"}}

#: the libraries with YOUR types, and the option that keeps the one picked
#: (a slab's: «stype», its record's too — slab layers, 2026-10-23)
TYPE_OPT = {"wall": "wtype", "slab": "stype", "profile": "profile"}


def rec_changes(key: str, changes: dict) -> dict:
    m = REC_KEYS.get(key, {})
    return {m.get(k, k): v for k, v in changes.items()}


def _same(a, b) -> bool:
    if a in (None, "") and b in (None, ""):     # no type / no layers alike
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-6
    return a == b


#: an option a record may lack, and what it then is (a door before the
#: arch: square)
UNSET = {"top": "square", "oshape": "rect"}
#: a card's value that its variants still fit: a «solid» leaf is also a
#: panelled or a half-glass one (the Swing card stays lit, 2026-10-27)
ALIKE = {("leaf", "solid"): ("solid", "panels", "half")}


def current_type(shelf: Shelf, opts: dict) -> str | None:
    """The type the options are (the first that fits); None = sizes of
    one's own. Two that fit: the one that says MORE wins (the roofs' «L
    plan» = Hip + L, 2026-10-16); equal: the first."""
    best = None
    for t in shelf.types:
        if t.set is not None and all(
                _same(opts.get(k, UNSET.get(k)), v)
                or opts.get(k) in ALIKE.get((k, v), ())
                for k, v in t.set.items()):
            if best is None or len(t.set) > len(best.set):
                best = t
    return best.key if best is not None else None


# ---- the pictures ------------------------------------------------------------------
def _pen(c=INK, w=4.0, dash=False) -> QPen:
    p = QPen(c, w)
    p.setCapStyle(Qt.RoundCap)
    p.setJoinStyle(Qt.RoundJoin)
    if dash:
        p.setStyle(Qt.DashLine)
    return p


def _wall_stubs(p, y=70, a=22, b=74) -> None:
    p.setPen(_pen(INK, 8))
    p.drawLine(QPointF(6, y), QPointF(a, y))
    p.drawLine(QPointF(b, y), QPointF(90, y))


def _door_swing(p) -> None:
    _wall_stubs(p)
    p.setPen(_pen(ACCENT, 5))
    p.drawLine(QPointF(22, 70), QPointF(22, 18))
    p.setPen(_pen(ACCENT, 3, True))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(-30, 18, 104, 104), 0, 90 * 16)


def _door_sliding(p) -> None:
    _wall_stubs(p)
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawRect(QRectF(18, 56, 40, 7))
    p.setBrush(INK)
    p.drawRect(QRectF(46, 46, 40, 7))
    p.setPen(_pen(ACCENT, 3.5))
    p.drawLine(QPointF(30, 34), QPointF(66, 34))
    p.drawLine(QPointF(58, 27), QPointF(66, 34))
    p.drawLine(QPointF(58, 41), QPointF(66, 34))


def _door_glass(p) -> None:
    """A glazed sliding door, front view: two panes in slim dark frames,
    one sliding over the other."""
    glass = QColor("#8fc3dd")
    glass.setAlpha(150)
    p.setPen(_pen(INK, 4))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(10, 12, 76, 76))            # the opening's frame
    p.setPen(_pen(QColor("#3b4046"), 3))
    p.setBrush(glass)
    p.drawRect(QRectF(16, 18, 36, 64))
    p.drawRect(QRectF(44, 18, 36, 64))
    p.setPen(_pen(ACCENT, 3.5))
    p.drawLine(QPointF(66, 50), QPointF(34, 50))
    p.drawLine(QPointF(41, 43), QPointF(34, 50))
    p.drawLine(QPointF(41, 57), QPointF(34, 50))


def _door_shop(p) -> None:
    """A shopfront, front view: a sign band, fixed panes either side of a
    glazed double door, a transom over it."""
    glass = QColor("#8fc3dd")
    glass.setAlpha(150)
    p.setPen(Qt.NoPen)
    p.setBrush(INK)
    p.drawRect(QRectF(8, 10, 80, 12))                 # the sign band
    p.setPen(_pen(QColor("#3b4046"), 3))
    p.setBrush(glass)
    for x0, x1 in ((10, 30), (66, 86)):               # fixed panes
        p.drawRect(QRectF(x0, 26, x1 - x0, 60))
    p.drawRect(QRectF(32, 26, 32, 14))                # the transom
    p.setPen(_pen(ACCENT, 3))
    p.drawRect(QRectF(32, 42, 16, 44))                # the door's leaves
    p.drawRect(QRectF(48, 42, 16, 44))
    p.drawLine(QPointF(45, 58), QPointF(45, 72))      # handles
    p.drawLine(QPointF(51, 58), QPointF(51, 72))


def _door_garage(p) -> None:
    """A sectional garage door, front view: wide and low, horizontal
    panels, a handle."""
    p.setPen(_pen(INK, 4))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(8, 26, 80, 62))                 # the opening
    p.setPen(_pen(ACCENT, 3))
    for y in (41, 56, 71):                            # the panels' joints
        p.drawLine(QPointF(10, y), QPointF(86, y))
    p.setPen(_pen(INK, 3))
    p.drawLine(QPointF(42, 80), QPointF(54, 80))      # the handle


def _door_arched(p) -> None:
    path = QPainterPath(QPointF(26, 88))
    path.lineTo(26, 40)
    path.arcTo(QRectF(26, 18, 44, 44), 180, -180)
    path.lineTo(70, 88)
    p.setPen(_pen(DIM, 5))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)


def _win_fixed(p) -> None:
    _wall_stubs(p, 48, 20, 76)
    p.setPen(_pen(ACCENT, 4))
    p.drawLine(QPointF(20, 38), QPointF(20, 58))
    p.drawLine(QPointF(76, 38), QPointF(76, 58))
    p.drawLine(QPointF(20, 44), QPointF(76, 44))
    p.drawLine(QPointF(20, 52), QPointF(76, 52))


def _win_shop(p) -> None:
    """A shop window, front view: fixed panes from the floor, a bar across
    with glass over it."""
    glass = QColor("#8fc3dd")
    glass.setAlpha(150)
    p.setPen(_pen(QColor("#3b4046"), 3))
    p.setBrush(glass)
    for x0, x1 in ((10, 36), (36, 62), (62, 88)):
        p.drawRect(QRectF(x0, 14, x1 - x0, 18))       # over the bar
        p.drawRect(QRectF(x0, 34, x1 - x0, 54))
    p.setPen(_pen(ACCENT, 3.5))
    p.drawLine(QPointF(10, 33), QPointF(88, 33))      # the bar across


def _win_sliding(p) -> None:
    _wall_stubs(p, 48, 20, 76)
    p.setPen(_pen(DIM, 4))
    p.drawLine(QPointF(20, 43), QPointF(54, 43))
    p.drawLine(QPointF(42, 53), QPointF(76, 53))


def _win_casement(p) -> None:
    _wall_stubs(p, 60, 20, 76)
    p.setPen(_pen(DIM, 4))
    p.drawLine(QPointF(20, 60), QPointF(36, 26))
    p.drawLine(QPointF(76, 60), QPointF(60, 26))


def _win_awning(p) -> None:
    """Side view: the wall cut, the leaf hinged at its top, tilted out."""
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawRect(QRectF(40, 10, 16, 18))            # the wall over it
    p.drawRect(QRectF(40, 70, 16, 18))            # and under it
    p.setPen(_pen(DIM, 4))
    p.drawLine(QPointF(48, 30), QPointF(66, 66))  # the leaf, tilted out
    p.setPen(_pen(DIM, 2))
    p.drawLine(QPointF(48, 30), QPointF(48, 68))  # where it closes


def _win_pivot(p) -> None:
    """Side view: the wall cut, 4 panes each turned on its middle."""
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawRect(QRectF(40, 10, 16, 18))
    p.drawRect(QRectF(40, 70, 16, 18))
    p.setPen(_pen(DIM, 4))
    for zc in (35, 45, 55, 65):
        p.drawLine(QPointF(43, zc - 4), QPointF(53, zc + 4))


def _wall(p, t) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawRect(QRectF(48 - t / 2, 10, t, 76))
    p.setPen(_pen(INK, 2.5))
    p.drawLine(QPointF(14, 86), QPointF(82, 86))


def _wall_curtain(p) -> None:
    """Glass floor to floor: mullions, a dark band at each floor."""
    glass = QColor("#8fc3dd")
    glass.setAlpha(150)
    p.setPen(_pen(QColor("#3b4046"), 3))
    p.setBrush(glass)
    for x0 in (14, 37, 60):
        p.drawRect(QRectF(x0, 16, 23, 30))
        p.drawRect(QRectF(x0, 54, 23, 30))
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawRect(QRectF(12, 46, 72, 8))                  # the band at a floor


def _col_rect(p) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawRect(QRectF(30, 26, 36, 44))
    p.setPen(_pen(INK, 2, True))
    p.drawLine(QPointF(10, 48), QPointF(86, 48))
    p.drawLine(QPointF(48, 10), QPointF(48, 86))


def _col_round(p) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawEllipse(QPointF(48, 48), 22, 22)
    p.setPen(_pen(INK, 2, True))
    p.drawLine(QPointF(10, 48), QPointF(86, 48))
    p.drawLine(QPointF(48, 10), QPointF(48, 86))


def _beam(p, w, h) -> None:
    """A beam's section under its slab."""
    p.setPen(Qt.NoPen)
    p.setBrush(INK)
    p.drawRect(QRectF(8, 20, 80, 10))
    p.setBrush(ACCENT)
    p.drawRect(QRectF(48 - w / 2, 20, w, h))


def _block(p) -> None:
    """A box in perspective — a block on the floor."""
    p.setPen(_pen(INK, 3.0))
    p.setBrush(Qt.NoBrush)
    front = [QPointF(14, 40), QPointF(62, 40), QPointF(62, 76), QPointF(14, 76)]
    top = [QPointF(14, 40), QPointF(34, 22), QPointF(82, 22), QPointF(62, 40)]
    side = [QPointF(62, 40), QPointF(82, 22), QPointF(82, 58), QPointF(62, 76)]
    from PySide6.QtGui import QPolygonF
    p.setBrush(ACCENT)
    p.drawPolygon(QPolygonF(top))
    p.setBrush(Qt.NoBrush)
    p.drawPolygon(QPolygonF(front))
    p.drawPolygon(QPolygonF(side))


def _ceiling(p) -> None:
    """The slab over, a thin board hung under it (the plenum between)."""
    p.setPen(Qt.NoPen)
    p.setBrush(INK)
    p.drawRect(QRectF(8, 14, 80, 10))                # the slab
    p.setPen(_pen(DIM, 2.0))
    for x in (24, 72):                               # the hangers
        p.drawLine(QPointF(x, 24), QPointF(x, 46))
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawRect(QRectF(8, 46, 80, 5))                 # the ceiling board


def _slab_layers(p, layers, top_colour: str) -> None:
    """A slab with layers in section: its top finish (``top_colour``), the
    other finishes light, the core dark — on two walls."""
    tot = sum(la["t"] for la in layers)
    y = 22.0
    for i, la in enumerate(layers):
        dh = 40.0 * la["t"] / tot
        p.setPen(Qt.NoPen)
        p.setBrush(INK if la["role"] == "core" else
                   QColor(top_colour) if i == 0 else QColor("#d9d4c7"))
        p.drawRect(QRectF(8, y, 80, max(dh, 2.5)))
        y += max(dh, 2.5)
    p.setBrush(INK)
    for x in (16, 72):
        p.drawRect(QRectF(x, y, 8, 88 - y))


def _slab(p, t) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawRect(QRectF(8, 40 - t / 2, 80, t))
    p.setBrush(INK)
    for x in (16, 72):
        p.drawRect(QRectF(x, 40 + t / 2, 8, 40 - t / 2))


def _stair_straight(p) -> None:
    p.setPen(_pen(INK, 3))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(34, 8, 28, 80))
    p.setPen(_pen(ACCENT, 2.5))
    for k in range(1, 8):
        y = 8 + k * 10
        p.drawLine(QPointF(34, y), QPointF(62, y))


def _stair_l(p) -> None:
    path = QPainterPath(QPointF(16, 88))
    for x, y in ((16, 14), (82, 14), (82, 40), (42, 40), (42, 88)):
        path.lineTo(x, y)
    path.closeSubpath()
    p.setPen(_pen(INK, 3))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.setPen(_pen(ACCENT, 2.5))
    for y in (50, 60, 70, 80):
        p.drawLine(QPointF(16, y), QPointF(42, y))
    for x in (52, 62, 72):
        p.drawLine(QPointF(x, 14), QPointF(x, 40))


def _stair_u(p) -> None:
    path = QPainterPath(QPointF(12, 88))
    for x, y in ((12, 12), (84, 12), (84, 88), (58, 88), (58, 38),
                 (38, 38), (38, 88)):
        path.lineTo(x, y)
    path.closeSubpath()
    p.setPen(_pen(INK, 3))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.setPen(_pen(ACCENT, 2.5))
    for y in (48, 58, 68, 78):
        p.drawLine(QPointF(12, y), QPointF(38, y))
        p.drawLine(QPointF(58, y), QPointF(84, y))


def _ramp(p, kind) -> None:
    """A ramp's outline in plan — the stair's, without its steps — and
    the way it climbs."""
    outline = {"straight": ((34, 8), (62, 8), (62, 88), (34, 88)),
               "L": ((16, 88), (16, 14), (82, 14), (82, 40), (42, 40),
                     (42, 88)),
               "U": ((12, 88), (12, 12), (84, 12), (84, 88), (58, 88),
                     (58, 38), (38, 38), (38, 88))}[kind]
    path = QPainterPath(QPointF(*outline[0]))
    for x, y in outline[1:]:
        path.lineTo(x, y)
    path.closeSubpath()
    p.setPen(_pen(INK, 3))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    x = {"straight": 48, "L": 29, "U": 25}[kind]
    p.setPen(_pen(ACCENT, 3.5))
    p.drawLine(QPointF(x, 82), QPointF(x, 52))
    p.drawLine(QPointF(x - 6, 60), QPointF(x, 52))
    p.drawLine(QPointF(x + 6, 60), QPointF(x, 52))


def _house(p, top=54) -> None:
    """A house's walls, seen from the front: the roofs sit on them."""
    p.setPen(_pen(INK, 3))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(22, top, 52, 86 - top))


def _poly(p, pts, color=ACCENT, fill=True, w=3.0, dash=False) -> None:
    path = QPainterPath(QPointF(*pts[0]))
    for x, y in pts[1:]:
        path.lineTo(x, y)
    if fill:
        path.closeSubpath()
    p.setPen(_pen(color, w, dash))
    p.setBrush(color if fill else Qt.NoBrush)
    p.drawPath(path)


def _roof(p, kind) -> None:
    if kind == "gable":
        _house(p)
        _poly(p, [(12, 58), (48, 22), (84, 58), (78, 58), (48, 30),
                  (18, 58)])
    elif kind == "hip":
        _house(p)
        _poly(p, [(12, 58), (34, 30), (62, 30), (84, 58)])
    elif kind == "flat":
        _house(p, 46)
        _poly(p, [(18, 40), (78, 40), (78, 46), (18, 46)])
    elif kind == "shed":
        _house(p, 50)
        _poly(p, [(12, 54), (84, 26), (84, 32), (12, 60)])
    elif kind == "hidden":
        _house(p, 36)                            # the parapet: walls go on up
        _poly(p, [(30, 56), (70, 44)], ACCENT, False, 4)   # the sheets
        p.setPen(_pen(DIM, 2, True))
        p.drawLine(QPointF(22, 36), QPointF(74, 36))
        _poly(p, [(26, 54), (26, 62), (34, 62), (34, 54)], INK, False, 2.5)
    elif kind == "butterfly":                    # (0.15.0: no longer «soon»)
        _house(p, 40)
        _poly(p, [(12, 28), (48, 44), (84, 28), (84, 34), (48, 50),
                  (12, 34)])
    elif kind == "mansard":
        _house(p)
        _poly(p, [(12, 58), (22, 34), (34, 26), (62, 26), (74, 34),
                  (84, 58), (78, 58), (69, 37), (59, 32), (37, 32),
                  (27, 37), (18, 58)])
    else:                                        # an L plan
        _poly(p, [(14, 14), (82, 14), (82, 44), (44, 44), (44, 84),
                  (14, 84)], DIM, False, 4)
        p.setPen(_pen(DIM, 2.5))
        p.drawLine(QPointF(29, 29), QPointF(67, 29))
        p.drawLine(QPointF(29, 29), QPointF(29, 70))


def _guard(p, kind) -> None:
    """A low wall / guard seen from the front, on its floor."""
    glass = QColor("#8fc3dd")
    glass.setAlpha(150)
    p.setPen(_pen(INK, 2.5))
    p.drawLine(QPointF(6, 86), QPointF(90, 86))        # the floor
    if kind == "wall":
        p.setPen(Qt.NoPen)
        p.setBrush(ACCENT)
        p.drawRect(QRectF(14, 30, 68, 56))
        p.setBrush(INK)
        p.drawRect(QRectF(10, 24, 76, 7))              # the coping
        return
    if kind == "boundary":
        # a tall wall between two piers, a gate in a gap
        p.setPen(Qt.NoPen)
        p.setBrush(ACCENT)
        p.drawRect(QRectF(6, 22, 40, 64))               # the wall
        p.setBrush(INK)
        for x in (4, 44, 82):                          # the piers
            p.drawRect(QRectF(x, 14, 10, 72))
        p.drawRect(QRectF(4, 19, 50, 4))                # its coping
        p.setPen(_pen(INK, 2.5))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(56, 26, 24, 57))              # the gate
        for x in (62, 68, 74):
            p.drawLine(QPointF(x, 28), QPointF(x, 81))
        return
    base = 86
    if kind == "wallrail":
        p.setPen(Qt.NoPen)
        p.setBrush(ACCENT)
        p.drawRect(QRectF(14, 60, 68, 26))
        base = 60
    p.setPen(_pen(INK, 4))
    p.drawLine(QPointF(12, 22), QPointF(84, 22))       # the top rail
    if kind == "glass":
        p.setPen(_pen(QColor("#3b4046"), 2))
        p.setBrush(glass)
        p.drawRect(QRectF(16, 26, 64, base - 30))
        p.setPen(Qt.NoPen)
        p.setBrush(INK)
        p.drawRect(QRectF(14, base - 6, 68, 6))         # the channel
        return
    p.setPen(_pen(INK, 3))
    for x in (16, 48, 80):
        p.drawLine(QPointF(x, 22), QPointF(x, base))
    p.setPen(_pen(ACCENT if kind == "steel" else INK, 2))
    for x in (24, 32, 40, 56, 64, 72):
        p.drawLine(QPointF(x, 26), QPointF(x, base - 4))


def _profile(p, key) -> None:
    """A profile's cut, the wall on its left, the floor or ceiling it sits
    on."""
    pts = PF.outline(key)
    d, h = PF.size(key)
    k = min(56 / max(d, 1e-3), 64 / max(h, 1e-3))
    x0 = 30
    a = PF.anchor_of(key)[0]
    y0 = 20 + h * k if a == "ceiling" else 80
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#4a4f56"))
    p.drawRect(QRectF(x0 - 14, 8, 14, 80))               # the wall
    if a == "floor":
        p.drawRect(QRectF(x0 - 14, 80, 74, 8))
    elif a == "ceiling":
        p.drawRect(QRectF(x0 - 14, 8, 74, 12))
    path = QPainterPath(QPointF(x0 + pts[0][0] * k, y0 - pts[0][1] * k))
    for u, v in pts[1:]:
        path.lineTo(x0 + u * k, y0 - v * k)
    path.closeSubpath()
    p.setBrush(QColor("#2f7df6"))
    p.setPen(_pen(INK, 2))
    p.drawPath(path)


def _copy(p, key) -> None:
    """An object copied along a path: three of it, side by side, on a line
    seen from the front — the middle one in the accent."""
    p.setPen(_pen(DIM, 2, dash=True))
    p.drawLine(QPointF(4, 84), QPointF(92, 84))         # the path
    for i, x in enumerate((18, 48, 78)):
        ink = QColor("#2f7df6") if i == 1 else INK
        p.setPen(Qt.NoPen)
        p.setBrush(ink)
        if key == "bollard":
            p.drawRoundedRect(QRectF(x - 5, 52, 10, 32), 4, 4)
        elif key == "lamp":
            p.drawRect(QRectF(x - 2, 40, 4, 44))
            p.drawEllipse(QPointF(x, 36), 7, 7)
        elif key == "tree":
            p.setBrush(QColor("#9a6a3e"))
            p.drawRect(QRectF(x - 2, 60, 4, 24))
            p.setBrush(QColor("#5b9a4a") if i != 1 else ink)
            p.drawEllipse(QPointF(x, 46), 13, 17)
        elif key == "planter":
            p.drawRect(QRectF(x - 11, 66, 22, 18))
            p.setBrush(QColor("#5b9a4a"))
            p.drawEllipse(QPointF(x, 62), 9, 7)
        elif key == "post":
            p.drawRect(QRectF(x - 4, 40, 8, 44))
        else:                                           # one of his own
            p.setPen(_pen(ink, 2))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(x - 9, 58, 18, 26))
            p.drawLine(QPointF(x - 9, 58), QPointF(x - 4, 52))
            p.drawLine(QPointF(x + 9, 58), QPointF(x + 14, 52))
            p.drawLine(QPointF(x - 4, 52), QPointF(x + 14, 52))
            p.drawLine(QPointF(x + 14, 52), QPointF(x + 14, 78))
            p.drawLine(QPointF(x + 14, 78), QPointF(x + 9, 84))


def _street(p) -> None:
    """A street seen from above: its asphalt, a curb and a sidewalk each
    side, a corner turning round into a side street."""
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#3a3e45"))
    p.drawRect(QRectF(4, 34, 88, 28))                  # the road
    p.drawRect(QRectF(50, 62, 22, 30))                 # a side street
    p.setBrush(QColor("#b9b2a6"))
    p.drawRect(QRectF(4, 20, 88, 12))                  # the far sidewalk
    p.drawRect(QRectF(4, 64, 44, 12))                  # the near one
    p.drawRect(QRectF(74, 64, 18, 12))
    p.setPen(_pen(ACCENT, 2.5, dash=True))
    p.drawLine(QPointF(8, 48), QPointF(88, 48))         # the centre line


def _glaz(p, kind) -> None:
    """A glass grid seen from the front."""
    glass = QColor("#8fc3dd")
    glass.setAlpha(140)
    dim = kind in ("arched", "round")
    p.setPen(Qt.NoPen)
    p.setBrush(glass if not dim else QColor("#3a3f45"))
    if kind == "round":
        p.drawEllipse(QPointF(48, 48), 36, 36)
        p.setPen(_pen(DIM, 4))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(48, 48), 36, 36)
        return
    p.drawRect(QRectF(14, 12, 68, 74))
    ink = DIM if dim else INK
    p.setPen(_pen(ink, 5 if kind == "aluminium" else 3))
    p.setBrush(Qt.NoBrush)
    if kind == "arched":
        path = QPainterPath(QPointF(14, 86))
        path.lineTo(14, 46)
        path.arcTo(QRectF(14, 12, 68, 68), 180, -180)
        path.lineTo(82, 86)
        path.closeSubpath()
        p.drawPath(path)
        return
    p.drawRect(QRectF(14, 12, 68, 74))
    p.setPen(_pen(ACCENT, 2.5 if kind == "industrial" else 3.5))
    xs = {"industrial": (31, 48, 65), "aluminium": (48,),
          "partition": (37, 59)}[kind]
    for x in xs:
        p.drawLine(QPointF(x, 12), QPointF(x, 86))
    if kind != "partition":
        zs = (30.5, 49, 67.5) if kind == "industrial" else (49,)
        for z in zs:
            p.drawLine(QPointF(14, z), QPointF(82, z))


def _grid_open(p, kind) -> None:
    """An open grid (a cobogó, a lattice, slats) seen from the front: the
    bars on the wall behind, no glass."""
    wood = QColor("#9a6a3e")
    ink = wood if kind in ("lattice", "vslats") else INK
    p.setPen(Qt.NoPen)
    if kind == "bars":                 # the window behind them, its glass
        glass = QColor("#8fc3dd")
        glass.setAlpha(140)
        p.setBrush(glass)
    else:
        p.setBrush(QColor("#4a4f56"))
    p.drawRect(QRectF(14, 12, 68, 74))
    p.save()
    p.setClipRect(QRectF(14, 12, 68, 74))
    if kind == "bars":
        p.setPen(_pen(ink, 3))
        for k in range(1, 7):
            x = 14 + 68 * k / 7
            p.drawLine(QPointF(x, 12), QPointF(x, 86))
        p.setPen(Qt.NoPen)
        p.setBrush(ink)
        for z in (33, 61):
            p.drawRect(QRectF(14, z, 68, 5))
    elif kind == "square":
        p.setPen(_pen(ink, 2.5))
        for k in range(1, 5):
            x, z = 14 + 68 * k / 5, 12 + 74 * k / 5
            p.drawLine(QPointF(x, 12), QPointF(x, 86))
            p.drawLine(QPointF(14, z), QPointF(82, z))
    elif kind in ("diamond", "lattice"):
        dx, dz = (14, 7) if kind == "diamond" else (12, 12)
        p.setPen(_pen(ink, 2.5 if kind == "diamond" else 4.5))
        for k in range(-8, 10):
            x = 14 + k * dx
            run = 74 * dx / dz
            p.drawLine(QPointF(x, 12), QPointF(x + run, 86))
            p.drawLine(QPointF(x, 86), QPointF(x + run, 12))
    elif kind == "vslats":
        p.setPen(Qt.NoPen)
        p.setBrush(wood)
        for k in range(8):
            p.drawRect(QRectF(16 + k * 8.6, 12, 5, 74))
    elif kind == "hslats":
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#b8bcc0"))
        for k in range(6):
            p.drawRect(QRectF(14, 15 + k * 12.4, 68, 6))
    p.restore()
    if kind != "vslats":
        p.setPen(_pen(ink, 4))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(14, 12, 68, 74))


PICS = {
    "grid_square": lambda p: _grid_open(p, "square"),
    "grid_diamond": lambda p: _grid_open(p, "diamond"),
    "grid_lattice": lambda p: _grid_open(p, "lattice"),
    "grid_vslats": lambda p: _grid_open(p, "vslats"),
    "grid_hslats": lambda p: _grid_open(p, "hslats"),
    "grid_bars": lambda p: _grid_open(p, "bars"),
    "glaz_industrial": lambda p: _glaz(p, "industrial"),
    "glaz_aluminium": lambda p: _glaz(p, "aluminium"),
    "glaz_partition": lambda p: _glaz(p, "partition"),
    "glaz_arched": lambda p: _glaz(p, "arched"),
    "glaz_round": lambda p: _glaz(p, "round"),
    "guard_wall": lambda p: _guard(p, "wall"),
    "guard_wallrail": lambda p: _guard(p, "wallrail"),
    "guard_glass": lambda p: _guard(p, "glass"),
    "guard_steel": lambda p: _guard(p, "steel"),
    "guard_boundary": lambda p: _guard(p, "boundary"),
    "street": _street,
    **{f"profile_{k}": (lambda p, k=k: _profile(p, k)) for k in PF.NATIVE},
    **{f"copy_{k}": (lambda p, k=k: _copy(p, k))
       for k in (*PF.COPY_OBJECTS, PF.COPY_MINE)},
    "roof_gable": lambda p: _roof(p, "gable"),
    "roof_hip": lambda p: _roof(p, "hip"),
    "roof_flat": lambda p: _roof(p, "flat"),
    "roof_shed": lambda p: _roof(p, "shed"),
    "roof_hidden": lambda p: _roof(p, "hidden"),
    "roof_butterfly": lambda p: _roof(p, "butterfly"),
    "roof_mansard": lambda p: _roof(p, "mansard"),
    "roof_lt": lambda p: _roof(p, "lt"),
    "door_swing": _door_swing, "door_sliding": _door_sliding,
    "door_glass": _door_glass, "door_shop": _door_shop,
    "door_arched": _door_arched, "door_garage": _door_garage,
    "win_fixed": _win_fixed, "win_sliding": _win_sliding,
    "win_shop": _win_shop,
    "win_casement": _win_casement, "win_awning": _win_awning,
    "win_pivot": _win_pivot,
    "wall_15": lambda p: _wall(p, 15), "wall_20": lambda p: _wall(p, 20),
    "wall_10": lambda p: _wall(p, 10), "wall_curtain": _wall_curtain,
    "col_rect": _col_rect, "col_round": _col_round,
    "beam_s": lambda p: _beam(p, 15, 40), "beam_m": lambda p: _beam(p, 20,
                                                                    45),
    "beam_l": lambda p: _beam(p, 20, 60),
    "slab_12": lambda p: _slab(p, 9), "slab_15": lambda p: _slab(p, 12),
    "slab_20": lambda p: _slab(p, 16),
    "slab_ceiling": lambda p: _ceiling(p),
    "slab_tiles": lambda p: _slab_layers(p, SLAB_TILES, "#e4e9ee"),
    "slab_timber": lambda p: _slab_layers(p, SLAB_TIMBER, "#a8743f"),
    "slab_roof": lambda p: _slab_layers(p, SLAB_ROOF, "#4f6d8a"),
    "slab_block": lambda p: _block(p),
    "stair_straight": _stair_straight, "stair_l": _stair_l,
    "stair_u": _stair_u,
    "ramp_straight": lambda p: _ramp(p, "straight"),
    "ramp_l": lambda p: _ramp(p, "L"), "ramp_u": lambda p: _ramp(p, "U"),
}
_cache: dict = {}


def picture(key: str) -> QIcon:
    if key not in _cache:
        pm = QPixmap(PX, PX)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        PICS.get(key, lambda _p: None)(p)
        p.end()
        _cache[key] = QIcon(pm)
    return _cache[key]


# ---- the panel -------------------------------------------------------------------------
from .look import ACCENT as UI_ACCENT, ACCENT_DARK  # noqa: E402 — the
# interface's picked / active follow IngeTrazo's accent (0.15.0, C3); the
# cards' pictures keep ArchXQ's orange
CARD_CSS = ("QToolButton { border: 1px solid #3a3f45; border-radius: 6px; "
            "padding: 4px; color: #d6d9dd; }"
            "QToolButton:hover { border-color: #6b7178; }"
            f"QToolButton:checked {{ border: 2px solid {UI_ACCENT}; "
            "color: #ffffff; }"
            "QToolButton:disabled { color: #6b7178; }")
#: a type in use that is not a favourite: dashed, at the strip's end
IN_USE_CSS = CARD_CSS.replace("border: 1px solid #3a3f45",
                              "border: 1px dashed #8a9099")
#: the small round buttons ON a card (the trash, the star)
PIN_CSS = ("QToolButton { border: none; border-radius: 9px; padding: 0; "
           "background: #2b2f34; color: #d6d9dd; font-size: 12px; }"
           "QToolButton:hover { background: #4a5058; color: #ffffff; }")
STAR_ON, STAR_OFF = "\u2605", "\u2606"         # ★ ☆
#: the «More» card closing the strip (every type, in a window)
MORE_CSS = ("QToolButton { border: 1px dashed #6b7178; border-radius: 6px; "
            "padding: 4px; color: #d6d9dd; }"
            f"QToolButton:hover {{ border: 1px solid {UI_ACCENT}; "
            f"background: {ACCENT_DARK}; color: #ffffff; }}")
CHIP_CSS = ("QPushButton { border: 1px solid #3a3f45; border-radius: 4px; "
            "padding: 3px 10px; color: #d6d9dd; }"
            "QPushButton:hover { border-color: #6b7178; }"
            f"QPushButton:checked {{ border: 2px solid {UI_ACCENT}; "
            "color: #ffffff; }"
            "QPushButton:disabled { color: #6b7178; }")


SLIDER_CSS = ("QSlider::groove:horizontal { height: 8px; border-radius: 4px; "
              "background: #3a3f45; }"
              "QSlider::sub-page:horizontal { height: 8px; border-radius: 4px; "
              "background: #3d8fd6; }"
              "QSlider::handle:horizontal { width: 18px; height: 18px; "
              "margin: -5px 0; border-radius: 9px; background: #e8eaed; "
              "border: 2px solid #3d8fd6; }"
              "QSlider::handle:horizontal:hover { background: #ffffff; }")


#: an action button in the library (Sizes & levels…): the chips' look,
#: its border always orange (his ask, 2026-10-09)
ACTION_CSS = (f"QPushButton {{ border: 1px solid {UI_ACCENT}; "
              "border-radius: 4px; padding: 3px 14px; color: #d6d9dd; }"
              f"QPushButton:hover {{ background: {ACCENT_DARK}; "
              "color: #ffffff; }"
              f"QPushButton:pressed {{ background: {UI_ACCENT}; "
              "color: #ffffff; }")


def _two_lines(name: str, width: int = 11) -> str:
    """A card's name broken at the space nearest its middle when long."""
    if len(name) <= width or " " not in name:
        return name
    mid = len(name) / 2
    cut = min((i for i, ch in enumerate(name) if ch == " "),
              key=lambda i: abs(i - mid))
    return name[:cut] + "\n" + name[cut + 1:]


def layers_icon(layers, t: float | None = None) -> QIcon:
    """A wall type's card: its layers across, outside at the bottom (as a
    plan with the building up) — the core brick-red, the finishes light."""
    pm = QPixmap(PX, PX)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    tot = sum(float(la["t"]) for la in layers) or float(t or 0.2)
    h = 26.0 + min(tot, 0.5) * 60.0              # thicker wall, taller band
    y = (PX + h) / 2
    for la in layers:                              # outside → inside, upward
        dh = h * float(la["t"]) / tot
        core = la.get("role") == "core"
        p.fillRect(QRectF(12, y - dh, PX - 24, dh),
                   QColor("#b5654a") if core else QColor("#d9d4c7"))
        y -= dh
    p.setPen(_pen(INK, 2.0))
    p.drawRect(QRectF(12, (PX - h) / 2, PX - 24, h))
    p.end()
    return QIcon(pm)


def your_icon(key: str, t: dict) -> QIcon:
    """One of YOUR types' cards: a wall / slab type's layers, a profile's
    cut (never cached: it is his, edited at will)."""
    if key != "profile":
        return layers_icon(t["layers"], t["t"])
    PF.add([t])
    pm = QPixmap(PX, PX)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    _profile(p, t["id"])
    p.end()
    return QIcon(pm)


def type_changes(t: Type, opts: dict, picked: int) -> dict:
    """What a ready-made card sets when clicked."""
    ch = dict(t.set)
    # the next one's sizes, nothing selected: a shopfront's — or a door's
    # again after a shopfront
    if t.init and not picked and (t.key == "shop"
                                  or opts.get("op") == "shop"):
        ch.update(t.init)
    return ch


def new_type_tip(key: str) -> str:
    from .i18n import tr
    if key == "profile":
        return tr("A profile of your own: draw its cut as a flat face with "
                  "IngeTrazo's tools, select the face, click here")
    return (tr("A type of your own, from the wall selected (or the next "
               "one's thickness) — then its layers in the wall's window, "
               "«Layers»") if key == "wall" else
            tr("A type of your own, from the slab selected (or the next "
               "one's thickness) — then its layers in the slab's window, "
               "«Layers»"))


class Card(QToolButton):
    """A type's card. On the strip, the mouse over it shows a small TRASH
    in its corner (off the favourites — 0.17.0); in the window a STAR is
    always there (on / off the favourites)."""

    def __init__(self, size: QSize, css: str = CARD_CSS) -> None:
        super().__init__()
        self.setStyleSheet(css)
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setFixedSize(size)
        self.pin = None
        self.hover_only = False
        self.on_double = None            # (YOUR type's card: its window)

    def mouseDoubleClickEvent(self, e) -> None:  # noqa: N802
        if self.on_double is not None and e.button() == Qt.LeftButton:
            self.on_double()
            return
        super().mouseDoubleClickEvent(e)

    def add_pin(self, text: str, tip: str, on_click, hover_only: bool):
        b = _Pin(self)
        b.setStyleSheet(PIN_CSS)
        b.setText(text)
        b.setToolTip(tip)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedSize(QSize(18, 18))
        b.move(self.width() - 21, 3)
        b.clicked.connect(lambda _c=False: on_click())
        b.setVisible(not hover_only)
        self.pin, self.hover_only = b, hover_only
        return b

    def enterEvent(self, e) -> None:
        if self.pin is not None and self.hover_only:
            self.pin.show()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        # the mouse onto the trash «leaves» the card too (Qt): it stays
        self.hide_pin()
        super().leaveEvent(e)

    def hide_pin(self) -> None:
        from PySide6.QtGui import QCursor
        if self.pin is not None and self.hover_only and not self.rect(
                ).contains(self.mapFromGlobal(QCursor.pos())):
            self.pin.hide()


class _Pin(QToolButton):
    """The trash / star on a card: leaving it off the card hides it."""

    def leaveEvent(self, e) -> None:
        card = self.parent()
        if isinstance(card, Card):
            card.hide_pin()
        super().leaveEvent(e)


def trash_icon() -> QIcon:
    """A small bin, light ink (the trash on a favourite's card)."""
    pm = QPixmap(QSize(28, 28))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(_pen(INK, 2.4))
    p.drawLine(QPointF(6, 8), QPointF(22, 8))
    p.drawLine(QPointF(11, 8), QPointF(12, 5))
    p.drawLine(QPointF(12, 5), QPointF(16, 5))
    p.drawLine(QPointF(16, 5), QPointF(17, 8))
    path = QPainterPath()
    path.moveTo(8, 9)
    path.lineTo(9.5, 23)
    path.lineTo(18.5, 23)
    path.lineTo(20, 9)
    p.drawPath(path)
    p.drawLine(QPointF(12, 12), QPointF(12.4, 20))
    p.drawLine(QPointF(16, 12), QPointF(15.6, 20))
    p.end()
    return QIcon(pm)


def more_icon() -> QIcon:
    """A big plus in a ring, light ink (the «More» card)."""
    pm = QPixmap(QSize(40, 40))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(_pen(INK, 2.4))
    p.drawEllipse(QPointF(20, 20), 16, 16)
    p.setPen(_pen(INK, 3.2))
    p.drawLine(QPointF(20, 11), QPointF(20, 29))
    p.drawLine(QPointF(11, 20), QPointF(29, 20))
    p.end()
    return QIcon(pm)


def _wipe(layout) -> None:
    while layout.count():
        it = layout.takeAt(0)
        if it.widget() is not None:
            it.widget().deleteLater()
        elif it.layout() is not None:
            _wipe(it.layout())


class NoWheelSlider(QSlider):
    """A bar the mouse wheel never moves — the wheel scrolls the strip (his
    test, 2026-10-11: scrolling over the library changed sizes unseen)."""

    def wheelEvent(self, e) -> None:
        e.ignore()


class LibraryPanel(QWidget):
    """The library of one element: type cards, part chips. ``on_pick(key,
    changes)`` gets what was clicked; ``show(key, opts, pro_locked,
    picked)`` (re)fills it — None hides it."""

    def __init__(self, on_pick, on_live=None, fit=None) -> None:
        super().__init__()
        self.on_pick = on_pick
        self.on_live = on_live        # a slider dragged: (key, changes)
        #: fit(key, option, value) → the value the selected ones can take
        #: (a door never wider than its wall's room) — the bar stops there
        self.fit = fit
        #: dyn(key, opts) → more Parts, made for the SELECTION (a door's
        #: «Along the wall», over its own wall; a stair's «Move») — ui's
        self.dyn = None
        #: your_types(key) → YOUR wall / slab types [{"id", "name",
        #: "layers", "t"}] (0.15.0): cards of their own under the
        #: ready-made ones — ui's
        self.your_types = None
        self.key = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 8)
        lay.setSpacing(6)
        self.head = QLabel()
        f = self.head.font()
        f.setBold(True)
        self.head.setFont(f)
        top = QHBoxLayout()
        top.addWidget(self.head)
        top.addStretch(1)
        # (every type, in a window: the «More» card closing the strip —
        # beside the title it went unseen, his note 2026-11-02)
        from .help import help_button
        top.addWidget(help_button("library"))
        #: the last show_for's arguments (a star / a trash shows it again)
        self._args = None
        self._favs, self._new, self._yours, self._ready = [], [], [], []
        self._saved = None
        lay.addLayout(top)
        self.sub = QLabel()
        self.sub.setWordWrap(True)
        self.sub.setStyleSheet("color: #8a9099;")
        lay.addWidget(self.sub)
        # one selected: «Select all windows on this level (14)» — the batch
        # edit found without a right-click (L1, Kamen #68, 2026-10-31)
        self.more = QPushButton()
        self.more.setCursor(Qt.PointingHandCursor)
        self.more.setStyleSheet(
            "QPushButton { text-align: left; color: #8fb8f9; background: "
            "transparent; border: none; padding: 0px; }"
            "QPushButton:hover { color: #2f7df6; text-decoration: "
            "underline; }")
        self._more_fn = None
        self.more.clicked.connect(
            lambda _c=False: self._more_fn and self._more_fn())
        self.more.hide()
        lay.addWidget(self.more)
        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(6)
        lay.addWidget(self.body)
        # a Building element's PREVIEW under its cards (its side drawing,
        # what it will be, «Sizes & levels…»): made anew only when what it
        # shows changes
        self.fields = QWidget()
        self.fields_lay = QVBoxLayout(self.fields)
        self.fields_lay.setContentsMargins(0, 6, 0, 0)
        lay.addWidget(self.fields)
        # given the whole strip (a Building element's), the room left over
        # goes under it — never between its parts (his screen, 2026-10-09)
        lay.addStretch(1)
        self.fields_ident = None
        self.fields.hide()
        self.hide()

    def set_fields(self, make, ident) -> None:
        """``make()`` → the fields' widget, made only when ``ident`` (what
        they edit) changes; ``make`` None: no fields."""
        if make is None:
            ident = None
        if ident == self.fields_ident and (ident is None or
                                           self.fields_lay.count()):
            self.fields.setVisible(ident is not None)
            return
        while self.fields_lay.count():
            w = self.fields_lay.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        self.fields_ident = ident
        if make is not None:
            self.fields_lay.addWidget(make())
        self.fields.setVisible(make is not None)

    def _clear(self) -> None:
        _wipe(self.body_lay)

    def _icon_chips(self, part: Part, opts: dict):
        """A window's shapes as pictures, five to a row — the name in the
        tip (nine chips of words would not fit the strip)."""
        grid = QGridLayout()
        grid.setSpacing(4)
        value = opts.get(part.key) or UNSET.get(part.key)
        group = QButtonGroup(self)
        group.setExclusive(True)
        for i, (v, text) in enumerate(part.choices):
            on = _same(v, value)
            b = QToolButton()
            b.setIcon(shape_icon(v, 30, on))
            b.setIconSize(QSize(30, 30))
            b.setCheckable(True)
            b.setChecked(on)
            b.setToolTip(text)
            b.setStyleSheet(CHIP_CSS.replace("QPushButton", "QToolButton")
                            .replace("padding: 3px 10px", "padding: 2px"))
            b.clicked.connect(lambda _c=False, v=v:
                              self.on_pick(self.key, shape_changes(v, opts)))
            group.addButton(b)
            grid.addWidget(b, i // 5, i % 5)
        grid.setColumnStretch(5, 1)
        return grid

    def _slider(self, part: Part, opts: dict):
        """0 … 100 %: dragged, the model follows live (``on_live``); let
        go (or a click / a key), it is kept (``on_pick``: one Ctrl+Z)."""
        row = QHBoxLayout()
        s = NoWheelSlider(Qt.Horizontal)
        # well in view (his eye, 2026-10-08: the host's thin one hardly
        # showed): a thick track, the open part in blue, a round handle
        s.setStyleSheet(SLIDER_CSS)
        s.setMinimumHeight(24)
        s.setRange(0, 100)
        s.setValue(int(round(float(opts.get(part.key, 0.0) or 0.0) * 100)))
        s.setToolTip("Drag: the selected ones open and close as you go")
        val = QLabel(f"{s.value()} %")
        val.setFixedWidth(42)
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(s, 1)
        row.addWidget(val)

        def moved(v) -> None:
            val.setText(f"{v} %")
            if s.isSliderDown():
                if self.on_live is not None:
                    self.on_live(self.key, {part.key: v / 100.0})
            else:                                  # a click / a key: kept
                self.on_pick(self.key, {part.key: v / 100.0})
        s.valueChanged.connect(moved)
        s.sliderReleased.connect(
            lambda: self.on_pick(self.key, {part.key: s.value() / 100.0}))
        return row

    def _size_bar(self, part: Part, opts: dict):
        """A measure: the bar, dragged, pulls to the usual sizes (Shift:
        cm by cm) and the model follows live; its field shows it and takes
        a typed one (Enter). Let go / Enter: kept, one Ctrl+Z. Double
        click on the bar: its default."""
        from PySide6.QtWidgets import QApplication, QLineEdit, QSlider
        lo, hi, step, default = part.size
        K = 1000                          # the bar counts in thousandths
        pct = part.unit in ("%", "°")     # not a length: a slope, an angle
        # how near a usual size pulls — never more than 2 % of the bar's
        # span (a glass's place, 0…10 cm, was pulled to 1 / 2.5 cm wherever
        # it was dragged — his test, 2026-10-15: «as if held back»)
        lo_, hi_ = part.size[0], part.size[1]
        tol = 0.4 if pct else min(0.025, max(part.size[2],
                                             (hi_ - lo_) * 0.02))

        # a length in a feet-inch / mm document: shown in its unit, the bar
        # on whole inches (1/4", 1/16" for the fine ones), the usual sizes
        # rounded to the inch (his ask, 2026-10-16 — American viewers)
        from . import compat
        from .look import imperial_step
        host = part.unit == "m" and compat.doc_length_unit() != "m"
        inch = compat.imperial()
        if host and inch:
            step = imperial_step(step)
        snaps = tuple(round(q / 0.0254) * 0.0254 for q in part.snaps) \
            if host and inch else part.snaps
        if host and inch and (self.key, part.key) in IMPERIAL_SNAPS:
            snaps = tuple(i * 0.0254
                          for i in IMPERIAL_SNAPS[(self.key, part.key)])
        if host and inch and snaps:            # a double click: the nearest
            default = min(snaps, key=lambda q: abs(q - default))

        def text(v):
            if host:
                return compat.fmt_len(v)
            return f"{v:.1f}" if pct else f"{v:.3f}".rstrip("0").rstrip(".") \
                if step < 0.01 else f"{v:.2f}"

        sh = part.shift

        def changes(v):
            return dict(part.also, **{part.key: round(v - sh, 4)})

        # a TYPED measure goes past the bar's end (his ask, 2026-10-18: a
        # ramp's 6 m landing could not reach the façade) — the bar is the
        # usual sizes; the field, what you mean (a slope / angle: not past)
        typed_hi = hi if pct else hi * 4

        def fitted(v, typed=False):
            v = min(max(v, lo), typed_hi if typed else hi)
            if self.fit is not None:
                v = self.fit(self.key, part.key, v - sh) + sh
            return v

        class Bar(NoWheelSlider):
            def mouseDoubleClickEvent(self, _e):
                keep(default)

        row = QHBoxLayout()
        s = Bar(Qt.Horizontal)
        s.setStyleSheet(SLIDER_CSS)
        s.setMinimumHeight(24)
        s.setRange(int(round(lo * K)), int(round(hi * K)))
        s.setSingleStep(int(round(step * K)))
        s.setPageStep(int(round(step * K)) * 2)
        try:
            now = float(opts[part.key]) + sh
        except (KeyError, TypeError, ValueError):
            now = default
        s.setValue(int(round(now * K)))
        s.setToolTip(part.tip or "Drag: the selected ones follow — it pulls "
                     "to the usual sizes; Shift = "
                     + ("1/4 inch" if host and inch else "centimetre")
                     + " by " + ("1/4 inch" if host and inch else "centimetre")
                     + ". Double click: " + text(default)
                     + ("" if host else f" {part.unit}"))
        f = QLineEdit(text(now))
        f.setFixedWidth(84 if host else 54)
        f.setAlignment(Qt.AlignRight)
        f.setToolTip("Type an exact one + Enter (3'7\" · 43\" · 110 cm)"
                     if host and inch else
                     "Type an exact one + Enter (0.85 · 85 cm · 850 mm"
                     if not pct else "Type an exact one + Enter")
        f.setStyleSheet("QLineEdit { background: #1d2025; border: 1px solid "
                        "#3a3f45; border-radius: 3px; padding: 1px 4px; "
                        "color: #e6e6e6; } QLineEdit:focus { border-color: "
                        f"{UI_ACCENT}; }}")
        u = QLabel("" if host else part.unit)
        u.setStyleSheet("color: #8a9099;")
        row.addWidget(s, 1)
        row.addWidget(f)
        row.addWidget(u)
        quiet = [False]

        def put(v):
            quiet[0] = True
            try:
                s.setValue(int(round(v * K)))
            finally:
                quiet[0] = False
            f.setText(text(v))

        def snapped(raw):
            if QApplication.keyboardModifiers() & Qt.ShiftModifier:
                fine = 0.1 if pct else 0.00635 if host and inch else 0.01
                return round(raw / fine) * fine
            near = min(snaps, key=lambda q: abs(q - raw), default=None)
            if near is not None and abs(near - raw) <= tol:
                return near
            if host and inch:                  # on a whole inch, not from lo
                return round(raw / step) * step
            return lo + round((raw - lo) / step) * step

        def keep(v, typed=False):
            v = fitted(v, typed)
            put(v)
            self.on_pick(self.key, changes(v))

        def moved(iv):
            if quiet[0]:
                return
            v = fitted(snapped(iv / K))
            put(v)
            if s.isSliderDown():
                if self.on_live is not None:
                    self.on_live(self.key, changes(v))
            else:                              # a click on the track / a key
                self.on_pick(self.key, changes(v))
        s.valueChanged.connect(moved)
        s.sliderReleased.connect(lambda: keep(s.value() / K))

        def typed():
            v = parse_measure(f.text(), part.unit)
            if v is None:
                f.setText(text(s.value() / K))
                return
            keep(v, typed=True)
        f.returnPressed.connect(typed)
        return row

    def _your_types(self, opts: dict, pro_locked: bool) -> None:
        """YOUR wall / slab types (0.15.0, A2; slabs: slab layers): a card
        each (its layers drawn) and «+ New type» — picked: the next ones
        take it, the selected ones become it; its layers' bars below edit it
        for every element of it."""
        from .i18n import tr
        opt = TYPE_OPT[self.key]
        try:
            items = list(self.your_types(self.key) or ())
        except Exception:  # noqa: BLE001 — no cards, the rest stays
            items = []
        lab = QLabel(tr("Your types"))
        lab.setStyleSheet("color: #8a9099; font-size: 11px; "
                          "letter-spacing: 1px;")
        self.body_lay.addWidget(lab)
        grid = QGridLayout()
        grid.setSpacing(6)
        cur = opts.get(opt) or ""
        # ALL of them, no favourites: his own, made and deleted at will (his
        # call, 2026-10-28 — «in use» + its star never let him delete one);
        # the trash DELETES the type (asked first; its walls keep the layers)
        if not items:
            lab.hide()
        prof = self.key == "profile"
        for i, t in enumerate(items):
            b = self._card(QSize(84, 86), CARD_CSS)
            b.setIcon(your_icon(self.key, t))
            b.setIconSize(QSize(42, 42))
            # a long name on two lines (his screen: «Exteri… teste»)
            b.setText(_two_lines(t["name"]))
            b.setCheckable(True)
            b.setChecked(t["id"] == cur)
            b.setToolTip(t["name"] + ("  (ArchXQ IT Pro)" if pro_locked
                                      else "") + "\n"
                         + (tr("Double-click: its name and category") if prof
                            else tr("Double-click: its name and layers")))
            b.clicked.connect(lambda _c=False, tid=t["id"]: self.on_pick(
                self.key, {opt: tid}))
            b.on_double = lambda tid=t["id"]: self.on_pick(
                self.key, {"_types": "edit", "_tid": tid})
            p = b.add_pin("", tr("Delete this profile from your library — "
                                 "the ones placed stay") if prof else
                          tr("Delete this type — its elements keep its "
                             "layers"),
                          lambda tid=t["id"]: self.on_pick(
                              self.key, {"_types": "delete", "_tid": tid}),
                          True)
            p.setIcon(trash_icon())
            p.setIconSize(QSize(14, 14))
            grid.addWidget(b, i // 3, i % 3)
        self.body_lay.addLayout(grid)
        # the types' own actions (A4): the one marked edited (its window:
        # name + layers) or duplicated — deleted: its card's trash; every
        # type to a file and back — another project, another PC
        row = QHBoxLayout()
        row.setSpacing(2)
        acts = [("_new", tr("+ New from a face") if prof
                 else tr("+ New type"))]
        if cur and any(t["id"] == cur for t in items):
            acts += [("edit", tr("Edit…"))] + (
                [] if prof else [("duplicate", tr("Duplicate"))])
        if not prof:                     # (a profile: kept in his library)
            acts += [("import", tr("Import…"))]
            if items:
                acts += [("export", tr("Export…"))]
        for act, text in acts:
            b = QPushButton(text)
            b.setFlat(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("QPushButton { color: #5bc8e8; border: none; "
                            "padding: 1px 4px; } QPushButton:hover { "
                            "text-decoration: underline; }")
            if act == "_new":
                b.setToolTip(new_type_tip(self.key))
                b.clicked.connect(lambda _c=False: self.on_pick(
                    self.key, {"_newtype": True}))
            else:
                b.clicked.connect(lambda _c=False, act=act: self.on_pick(
                    self.key, {"_types": act}))
            row.addWidget(b)
        row.addStretch(1)
        self.body_lay.addLayout(row)

    # ---- favourites (0.17.0) ----------------------------------------------------
    def _fav_state(self, shelf: Shelf) -> None:
        """The element's favourites, read: ``_favs``, ``_new``, ``_yours``."""
        self._yours = []
        if self.key in TYPE_OPT and self.your_types is not None:
            try:
                self._yours = list(self.your_types(self.key) or ())
            except Exception:  # noqa: BLE001 — no types of his, the rest
                self._yours = []
        self._ready = [(t.key, t.set is None) for t in shelf.types]
        self._saved = FV.load(self.key)
        # (YOUR types are never favourites — always shown, 2026-10-28)
        self._favs, self._new = FV.resolve(self._saved, self._ready, [])

    def _keep(self, favs, seen: bool = False) -> None:
        d = FV.kept(favs, self._ready, [], self._saved, seen)
        FV.save(self.key, d)
        self._saved = d

    def set_favourite(self, fkey: str, on: bool) -> None:
        favs = list(self._favs)
        if (fkey in favs) != on:
            favs = FV.toggle(favs, fkey)
        self._keep(favs)
        self.refresh()

    def refresh(self) -> None:
        if self._args is not None:
            self.show_for(*self._args)

    def _stair_code(self, opts: dict) -> None:
        """The stair's code check, one line (stairrules.py) — for a storey
        of the new-floor height (Settings): the window has the whole check,
        with its own levels."""
        try:
            from . import compat, prefs
            from . import stairrules as SR
            from . import stairs as ST
            from .i18n import tr
            r = dict(ST.DEFAULT, **{k: v for k, v in opts.items()
                                    if k in ST.DEFAULT})
            hh = float(prefs.get("floor_height"))
            s = ST.steps(r, 0.0, hh)
            key = SR.current()
            ok, text = SR.summary(SR.check(r, s, key, fmt_cm=compat.fmt_cm,
                                           fmt_len=compat.fmt_len), key)
        except Exception:  # noqa: BLE001 — the shelf without its line
            return
        mark = "✓" if ok else "!"
        lab = QLabel(f"{mark}  {text}  ·  "
                     + tr("for a {h} storey — the window checks it all",
                          h=compat.fmt_len(hh)))
        lab.setWordWrap(True)
        lab.setStyleSheet("color: %s; font-size: 11px;"
                          % ("#7fbf7f" if ok else "#f0b44c"))
        lab.setToolTip(tr("A guide, never a rule: check the stair with your "
                          "engineer and your local code"))
        self.body_lay.addWidget(lab)

    def _card(self, size: QSize, css: str) -> Card:
        return Card(size, css)

    def _pin(self, b: Card, fkey: str, in_use: bool) -> None:
        """A card's corner: a star on the «in use» one (pin it), a trash
        on a favourite (off the strip — never the last one)."""
        from .i18n import tr
        if in_use:
            b.add_pin(STAR_OFF, tr("Keep it on this strip (favourites)"),
                      lambda: self.set_favourite(fkey, True), False)
        elif FV.can_drop(self._favs):
            t = b.add_pin("", tr("Off this strip — nothing is deleted; "
                                 "«More» brings it back"),
                          lambda: self._drop(fkey), True)
            t.setIcon(trash_icon())
            t.setIconSize(QSize(14, 14))

    def _drop(self, fkey: str) -> None:
        from PySide6.QtGui import QCursor

        from .i18n import tr
        self.set_favourite(fkey, False)
        QToolTip.showText(QCursor.pos(), tr("Off the favourites — the star "
                                            "in «More» brings it back"))

    def open_all(self) -> None:
        if self._args is None:
            return
        key, opts, pro_locked, picked = self._args
        self._keep(self._favs, seen=True)      # the «new» dot goes
        self.refresh()
        AllTypesDialog(self, key, opts, picked, pro_locked).exec()

    def set_more(self, text: str | None, fn=None) -> None:
        """The link under the hint («Select all … (14)»); None: none."""
        self._more_fn = fn
        if text:
            self.more.setText(text)
        self.more.setVisible(bool(text))

    def show_for(self, key, opts: dict | None, pro_locked: bool = False,
                 picked: int = 0) -> None:
        shelf = CATALOG.get(key)
        if shelf is None or opts is None:
            self.key = None
            self.hide()
            return
        self.key = key
        self._args = (key, opts, pro_locked, picked)
        self._clear()
        from .i18n import tr
        self._fav_state(shelf)
        n = sum(1 for t in shelf.types if t.set is not None) + len(
            self._yours)
        self.head.setText(tr("Library") + " · " + tr(shelf.title)
                          + ("   PRO" if pro_locked else ""))
        apart = key in BUILDING_ELEMENTS
        self.sub.setText(
            tr("Click a type to change the {what} selected — or "
               "double-click one: its window changes them all", what=picked)
            if picked > 1 else
            tr("Click a type to change the {what} selected", what=picked)
            if picked else
            tr("Pick a type, then click where it starts — sizes and levels: "
               "the button below")
            if apart else
            tr("Pick a type, then draw — the sizes are in the options bar on "
               "top, or drag them below")
            if any(pt.kind == "size" for pt in shelf.parts) else
            tr("Pick a type, then draw — the sizes are in the options bar on "
               "top"))
        grid = QGridLayout()
        grid.setSpacing(6)
        cur = current_type(shelf, opts)
        # the FAVOURITES only (0.17.0); the type in use that is not one:
        # dashed, at the end («soon» ones: in the window only)
        favs, use = FV.strip([k for k in self._favs
                              if not k.startswith("u:")], cur)
        by = {t.key: t for t in shelf.types if t.set is not None}
        cards = [by[k] for k in favs if k in by] + (
            [by[use]] if use in by else [])
        for i, t in enumerate(cards):
            in_use = t.key == use
            b = self._card(QSize(84, 86), IN_USE_CSS if in_use else CARD_CSS)
            b.setIcon(picture(t.pic))
            # (smaller in use: its two lines fit under it)
            b.setIconSize(QSize(42, 42) if in_use else QSize(56, 56))
            b.setText(t.label + ("\n" + tr("in use") if in_use else ""))
            b.setCheckable(True)
            b.setChecked(t.key == cur)
            b.setToolTip((t.tip or t.label)
                         + ("  (ArchXQ IT Pro)" if pro_locked else ""))
            ch = type_changes(t, opts, picked)
            b.clicked.connect(lambda _c=False, ch=ch:
                              self.on_pick(self.key, ch))
            self._pin(b, t.key, in_use)
            grid.addWidget(b, i // 3, i % 3)
        # the last card: EVERY type, in a window (favourites — 0.17.0). A
        # card as big as the types', where the eye already is: the small
        # «★ All N…» beside the title went unseen (his note, 2026-11-02)
        m = self._card(QSize(84, 86), MORE_CSS)
        m.setIcon(more_icon())
        m.setIconSize(QSize(40, 40))
        m.setText(tr("More") + ("  •" if self._new else ""))
        m.setToolTip(tr("Every type ({n}) — the star puts one on this strip",
                        n=n) + ("  ·  " + tr("New types")
                                if self._new else ""))
        m.setCursor(Qt.PointingHandCursor)
        m.clicked.connect(lambda _c=False: self.open_all())
        grid.addWidget(m, len(cards) // 3, len(cards) % 3)
        self.more_card = m
        self.body_lay.addLayout(grid)
        if key in TYPE_OPT and self.your_types is not None:
            self._your_types(opts, pro_locked)
        more = ()
        if self.dyn is not None:
            try:
                more = tuple(self.dyn(key, opts) or ())
            except Exception:  # noqa: BLE001 — no extra bars, the rest stays
                more = ()
        for part in shelf.parts + more:
            if part.show is not None and not part.show(opts):
                continue
            lab = QLabel(part.label)
            lab.setStyleSheet("color: #8a9099;")
            self.body_lay.addWidget(lab)
            if part.kind == "slider":
                self.body_lay.addLayout(self._slider(part, opts))
                continue
            if part.kind == "size":
                self.body_lay.addLayout(self._size_bar(part, opts))
                continue
            if part.kind == "icons":
                self.body_lay.addLayout(self._icon_chips(part, opts))
                continue
            row = QHBoxLayout()
            row.setSpacing(4)
            group = QButtonGroup(self)
            group.setExclusive(True)
            value = opts.get(part.key)
            if value is None:
                value = part.dflt(opts) if part.dflt else part.choices[0][0]
            for ch in part.choices:
                v, text = ch[0], ch[1]
                soon = len(ch) > 2 and ch[2] == "soon"
                pro = len(ch) > 2 and ch[2] == "pro" and edition.lite()
                c = QPushButton(text + (" · soon" if soon else
                                        " · Pro" if pro else ""))
                c.setStyleSheet(CHIP_CSS)
                c.setCheckable(True)
                c.setChecked(_same(v, value))
                c.setEnabled(not soon and not pro)
                if pro:
                    c.setToolTip("In ArchXQ IT Pro")
                elif soon:
                    c.setToolTip("Coming soon — the library keeps growing")
                else:
                    c.clicked.connect(lambda _c=False, k=part.key, v=v:
                                      self.on_pick(self.key, {k: v}))
                group.addButton(c)
                row.addWidget(c)
            row.addStretch(1)
            self.body_lay.addLayout(row)
        if key == "stair":
            self._stair_code(opts)
        # the greyed ones, said plainly (his ask, 2026-10-08: not everyone
        # reads «soon» on a grey card)
        if any(len(c) > 2 and c[2] == "soon" for pt in shelf.parts
               for c in pt.choices):
            note = QLabel("Greyed items are on the way — they switch on "
                          "with the coming updates.")
            note.setWordWrap(True)
            note.setStyleSheet("color: #6b7178; font-size: 11px;")
            self.body_lay.addWidget(note)
        self.show()


class AllTypesDialog(QDialog):
    """«★ All N…» — every type of the element (0.17.0): searched by name,
    by category; a STAR on each card puts it on the strip or takes it off
    (at once — the strip behind follows); a click on a card picks it (the
    next one drawn, or the ones selected become it) and closes, WITHOUT
    making it a favourite. «soon» ones live here, greyed."""

    def __init__(self, panel: LibraryPanel, key: str, opts: dict,
                 picked: int, pro_locked: bool) -> None:
        from .i18n import tr
        super().__init__(panel.window())
        self.panel, self.key, self.opts = panel, key, opts
        self.picked, self.pro_locked = picked, pro_locked
        self.shelf = CATALOG[key]
        self.cat = None
        self.setWindowTitle(tr("Library") + " · " + tr(self.shelf.title))
        self.setModal(True)
        self.resize(560, 560)
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.count = QLabel()
        top.addWidget(self.count)
        top.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Search…"))
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(200)
        self.search.textChanged.connect(lambda _t: self.fill())
        top.addWidget(self.search)
        lay.addLayout(top)
        self.chips = QHBoxLayout()
        self.chips.setSpacing(4)
        lay.addLayout(self.chips)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.inner = QWidget()
        self.inner_lay = QVBoxLayout(self.inner)
        self.inner_lay.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.inner)
        lay.addWidget(scroll, 1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close = QPushButton(tr("Close"))
        close.setStyleSheet(CHIP_CSS)
        close.clicked.connect(self.reject)
        bottom.addWidget(close)
        lay.addLayout(bottom)
        self._chips()
        self.fill()

    # ---- what is shown -------------------------------------------------------------
    def _keys(self) -> list:
        return [t.key for t in self.shelf.types] + [
            FV.ukey(t["id"]) for t in self.panel._yours]

    def _cats(self) -> list:
        return FV.categories(self.key, self._keys(),
                             self.key in TYPE_OPT
                             and self.panel.your_types is not None)

    def _chips(self) -> None:
        from .i18n import tr
        cats = self._cats()
        if len(cats) < 2:
            return
        group = QButtonGroup(self)
        for name in [None] + [n for n, _k in cats]:
            # («&» shown as itself, not a shortcut: «Shop & garage»)
            c = QPushButton((tr(name) if name else tr("All"))
                            .replace("&", "&&"))
            c.setStyleSheet(CHIP_CSS)
            c.setCheckable(True)
            c.setChecked(name is None)
            c.clicked.connect(lambda _c=False, n=name: self._pick_cat(n))
            group.addButton(c)
            self.chips.addWidget(c)
        self.chips.addStretch(1)

    def _pick_cat(self, name) -> None:
        self.cat = name
        self.fill()

    def fill(self) -> None:
        from .i18n import tr
        lay = self.inner_lay
        _wipe(lay)
        favs = list(self.panel._favs)
        nf = len(favs)
        self.count.setText(tr("Favourites {n} / {m}", n=nf, m=FV.STRIP_MAX)
                           + ("  —  " + tr("the strip will scroll")
                              if nf > FV.STRIP_MAX else ""))
        self.count.setStyleSheet(
            f"color: {UI_ACCENT if nf > FV.STRIP_MAX else '#8a9099'};")
        q = self.search.text().strip().lower()
        by = {t.key: t for t in self.shelf.types}
        yours = {FV.ukey(t["id"]): t for t in self.panel._yours}
        cur = current_type(self.shelf, self.opts)
        opt = TYPE_OPT.get(self.key)
        cur_u = FV.ukey(self.opts.get(opt)) if opt and self.opts.get(opt) \
            else None
        for name, keys in self._cats():
            if self.cat is not None and name != self.cat:
                continue
            items = []
            for k in keys:
                label = yours[k]["name"] if k in yours else by[k].label
                if q and q not in label.lower() and q not in tr(
                        label).lower():
                    continue
                items.append(k)
            new_card = name == FV.YOURS and not q
            if not items and not new_card:
                continue
            if name:
                h = QLabel(tr(name))
                h.setStyleSheet("color: #8a9099; font-size: 11px; "
                                "letter-spacing: 1px;")
                lay.addWidget(h)
            grid = QGridLayout()
            grid.setSpacing(6)
            cards = [self._card(k, by.get(k), yours.get(k),
                                k in (cur, cur_u), k in favs) for k in items]
            if new_card:
                cards.append(self._new_card())
            for i, b in enumerate(cards):
                grid.addWidget(b, i // 4, i % 4)
            grid.setColumnStretch(4, 1)
            lay.addLayout(grid)
        lay.addStretch(1)

    def _card(self, k, t, mine, on: bool, fav: bool) -> Card:
        from .i18n import tr
        b = Card(QSize(104, 108))
        if mine is not None:
            b.setIcon(your_icon(self.key, mine))
            b.setIconSize(QSize(52, 52))
            b.setText(_two_lines(mine["name"], 13))
            ch = {TYPE_OPT[self.key]: mine["id"]}
        else:
            b.setIcon(picture(t.pic))
            b.setIconSize(QSize(64, 64))
            soon = t.set is None
            b.setText(t.label + ("\nsoon" if soon else ""))
            if soon:
                b.setEnabled(False)
                b.setToolTip(tr("Coming soon — the library keeps growing"))
                return b
            b.setToolTip(t.tip or t.label)
            ch = type_changes(t, self.opts, self.picked)
        b.setCheckable(True)
        b.setChecked(on)
        b.clicked.connect(lambda _c=False, ch=ch: self._pick(ch))
        if mine is not None:                 # his own: no star (2026-10-28)
            return b
        b.add_pin(STAR_ON if fav else STAR_OFF,
                  tr("Off this strip") if fav else
                  tr("Keep it on this strip (favourites)"),
                  lambda k=k, fav=fav: self._star(k, not fav), False)
        if fav:
            b.pin.setStyleSheet(PIN_CSS + f"QToolButton {{ color: "
                                          f"{UI_ACCENT}; }}")
            if not FV.can_drop(self.panel._favs):
                b.pin.setEnabled(False)       # the last one stays
        return b

    def _new_card(self) -> Card:
        from .i18n import tr
        b = Card(QSize(104, 108), IN_USE_CSS)
        b.setText(tr("+ New from a face") if self.key == "profile"
                  else tr("+ New type"))
        b.setToolTip(new_type_tip(self.key))
        b.clicked.connect(lambda _c=False: self._pick({"_newtype": True}))
        return b

    def _star(self, k: str, on: bool) -> None:
        self.panel.set_favourite(k, on)
        self.fill()

    def _pick(self, ch: dict) -> None:
        self.accept()
        self.panel.on_pick(self.key, ch)
