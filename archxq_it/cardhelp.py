"""A library card's HELP — its right-click (his ask 20/11/2026: «the users
get lost… we are losing them»).

His rule for what it says: no «what it is / what it is for» — the user
knows or guesses that. The card is a drawing, not a photo: ONE short line
says how the type LOOKS; the rest is HOW TO USE IT, every detail of its
own, its LIMITS, what can go wrong and the way out — «with every detail of
how to use it, he won't use it wrong».

``COMMON[element]``: what every card of an element shares; ``CARDS``: a
type's own lines, shown first; ``CORNER``: a window turning a corner (Pro).
A card without its own text: its tooltip as its look, and the element's
guide tips (guide.GUIDES) — never an empty page. The texts are translated
where shown (i18n.tr_long); tests/test_card_help.py checks every one is in
the catalogues."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from . import edition

# ---- windows ------------------------------------------------------------------------------
_W_USE = [
    "Move along a straight wall of this level and click. The outline "
    "follows the pointer; <b>red</b> means it can't go there — the reason "
    "is written beside the pointer.",
    "<b>Width</b>, <b>Height</b> and <b>Sill</b> in the options bar on top "
    "or the Library's bars — set them before the click: the next windows "
    "keep them. The Sill counts from this level's floor (a raised wall's: "
    "from its raised foot).",
    "An exact place: two dimensions run from its edges to the corners (or "
    "the next opening). Type a distance + <b>Enter</b>: its edge goes that "
    "far from the <b>orange</b> one — the corner nearer the pointer. "
    "<b>1.05c</b>: to its centre.",
    "In the 3D view too: point at a wall of this level — it lines up with "
    "the windows above and below (a blue dashed line).",
    "Windows already placed: select them — a card or a size in the Library "
    "changes all of them at once. A double-click opens its window: "
    "<b>Type</b>, <b>Size</b>, <b>Trim &amp; sill</b>, <b>Position</b>.",
    "Selected, its grips: each side (the width), the top (the height), the "
    "bottom (the sill — the top stays) and the middle one, that slides it "
    "along the wall: carry it and type a distance, or <b>+0.10</b> / "
    "<b>-0.10</b> to move it by that much.",
    "<b>Glass</b> <b>Opaque</b>: IngeTrazo shows the lines behind "
    "see-through glass; opaque panes read as glass from outside.",
    "<b>Trim</b> round it and a <b>Stone sill</b> under it: in the Library "
    "or the <b>Trim &amp; sill</b> tab. Each part takes a material of its "
    "own in the <b>Material</b> tab: frame, glass, trim, sill.",
]
_W_LIMITS = [
    "Straight walls only — a curved wall takes none yet.",
    "It goes up to the face of a wall met at its end, and keeps 5 cm "
    "from a free end and from the wall's other openings; 20 × 20 cm "
    "at the least.",
    "Sill + Height go up to the wall's top at most — a wall with a top or "
    "a shape of its own: as high as it is THERE.",
]
_W_FIX = [
    ("«It doesn't fit in that wall»",
     "Too wide for that stretch, or too near an end: a smaller Width, or "
     "another wall."),
    ("«Too tall for that wall»",
     "Lower the Sill or the Height: together they go up to the wall's top "
     "at most."),
    ("«It runs into another opening of that wall»",
     "Move along — it keeps 5 cm from its neighbours. Typing a distance "
     "from the orange dimension puts it exactly where you want."),
    ("«Click ON a straight wall of this level»",
     "The pointer is off the wall, on a curved one, or (in 3D) on another "
     "level's wall: pick that level in the level strip first."),
    ("The lines behind the glass show through", "<b>Glass</b>: Opaque."),
]

# a casement's leaves — every casement card's
_CASEMENT = [
    "<b>Leaves</b> 1 to 6. Each <b>Leaf 1…6</b>: Fixed, Hinged left or "
    "Hinged right — counted left to right <b>seen from inside</b>.",
    "<b>Leaf … width</b>: its share of the window in %; 0 shares what the "
    "others leave.",
    "Two leaves that part in the middle meet with no post; other "
    "neighbours get a mullion.",
    "<b>Opens</b> In / Out — or <b>Shift+Tab</b> before the click. "
    "<b>Handle</b>: None or a lever.",
]
_CASEMENT_FIX = [
    ("The hinges are on the wrong side",
     "The leaves are read from INSIDE: seen from outside, left and right "
     "swap. Change the Leaf's Hinged left / right."),
    ("It opens the wrong way", "<b>Opens</b> In / Out on the selected "
     "window (Shift+Tab before the click)."),
]
_BARS = ("<b>Upright bars</b> / <b>Cross bars</b> (0 to 4): glazing bars on "
         "each leaf's glass. <b>Top light</b>: a fixed pane over it, a bar "
         "between (0: none) — inside the window's Height.")
_NO_BARS = "No glazing bars."
_SHAPED = [
    "Its shape is the <b>Shape</b> row in the Library (or the <b>Size</b> "
    "tab); its Height goes to the very top.",
]
_SHAPED_LIMITS = [
    "Fixed glass. A shaped window takes no glazing bars and doesn't turn a "
    "corner.",
]
_RISE = "<b>Rise</b>: how high its top rises over its sides."

#: a window turning a corner into the wall joined there (cornerwin.py, Pro)
CORNER = {
    "use": [
        "Point at the END of a wall joined to another straight wall (within "
        "25 cm of it) and click: the window turns the corner — an L, as "
        "wide on each wall. The value label says «round the corner» while "
        "it does.",
        "Its widths are measured to the corner's OUTSIDE, as the drawings "
        "dimension them: «1.50 + 1.20».",
        "Later, in its window (double-click), <b>Position</b> tab, "
        "<b>Round the corner</b>: No / At its start / At its end, its width "
        "on the other wall, and the corner: <b>A post</b> or <b>Glass to "
        "glass</b>.",
        "Glass to glass is a fixed window's; one with leaves always has a "
        "post at the corner.",
        "Both walls are cut through the corner; the plan, the sheets, the "
        "schedule and the quantities show one window «a + b × h».",
        "Its grips: the far side on each wall, the top and the bottom.",
    ],
    "limits": [
        "Both walls straight and joined at that end — not a curtain, grid, "
        "clad or light-framed wall.",
        "No room round the corner (an opening in the other wall, too tall "
        "there): the click places a plain window 5 cm off the end, with no "
        "message.",
        "A typed distance + Enter always places a plain one.",
    ],
    "fix": [
        ("It didn't turn the corner",
         "Point nearer the end (25 cm), check the two walls are joined "
         "(their ends meet) and the other wall has room there — or turn it "
         "afterwards: its window, Position tab."),
    ],
}

# ---- doors --------------------------------------------------------------------------------
_D_USE = [
    "Move along a straight wall of this level and click. <b>Red</b> means "
    "it can't go there — the reason is written beside the pointer.",
    "<b>Width</b> and <b>Height</b> in the options bar on top or the "
    "Library's bars — set them before the click. A door stands on the "
    "floor: no sill.",
    "<b>Tab</b> before the click: the hinge (or the side it slides to) on "
    "the other jamb. <b>Shift+Tab</b>: it opens In ↔ Out — In is the "
    "wall's inside.",
    "An exact place: two dimensions run from its edges to the corners (or "
    "the next opening). Type a distance + <b>Enter</b>: its edge goes that "
    "far from the <b>orange</b> one. <b>1.05c</b>: to its centre.",
    "In the 3D view too: point at a wall of this level — it lines up with "
    "the doors above and below (a blue dashed line).",
    "Doors already placed: select them — a card, a size, the hinge or "
    "<b>Opens</b> in the Library changes all of them at once. A "
    "double-click opens its window; its front view gives the free width "
    "to pass (NBR 9050).",
    "Selected, its grips: each side (the width), the top (the height) and "
    "the middle one, that slides it along the wall.",
    "<b>Open</b> shows it open in 3D as you drag it. In plan a swing door "
    "shows its leaf and its swing; a sliding one its leaves and an arrow.",
    "Its look in the Library: <b>Leaf</b>, <b>Handle</b> and its colour, "
    "<b>Leaf colour</b>, <b>Frame colour</b>. Each part takes a material "
    "of its own in the <b>Material</b> tab: leaf, handles, frame.",
]
_D_LIMITS = [
    "Straight walls only — a curved wall takes none yet.",
    "It goes up to the face of a wall met at its end, and keeps 5 cm "
    "from a free end and from the wall's other openings; up to the "
    "wall's top at most.",
]
_D_FIX = [
    ("«It doesn't fit in that wall»",
     "Too wide for that stretch, or too near an end: a smaller Width, or "
     "another wall."),
    ("«Too tall for that wall»",
     "Lower the Height — it goes up to the wall's top at most (a top "
     "light is inside the Height)."),
    ("«It runs into another opening of that wall»",
     "Move along — it keeps 5 cm from its neighbours."),
    ("It opens to the wrong side",
     "<b>Opens</b> In / Out on the selected door (Shift+Tab before the "
     "click). The hinge on the wrong jamb: <b>Hinge</b> Left / Right "
     "(Tab)."),
    ("It has no handle",
     "Doors drawn before the handles came keep their look: select them "
     "and pick a <b>Handle</b>."),
]
_SINGLE = ("<b>Hinge</b>: Left / Right — the jamb it hangs on (Tab before "
           "the click). <b>Leaves</b> 2 makes it a double door; this card "
           "picked for a double door makes it single again.")
_LEAF = ("Picked for doors already placed, it changes their leaf only — "
         "their size, hinge and side stay.")
_TWO = ("Two leaves, each on its own jamb: no Hinge to choose. "
        "<b>Leaves</b> 1 turns it into a single door.")
_GARAGE = [
    "<b>Kind</b>: Sectional, Roll-up or Up-and-over; <b>Finish</b>: "
    "Steel, White, Anthracite or Wood.",
    "Width 2.00 to 6.00 m, Height 1.90 to 3.50 m — it comes 2.60 × 2.20. "
    "<b>Open</b> lifts it in 3D.",
]
_GARAGE_LIMITS = ["No hinge, no In / Out: it lifts."]

COMMON = {
    "window": {"use": _W_USE, "limits": _W_LIMITS, "fix": _W_FIX},
    "door": {"use": _D_USE, "limits": _D_LIMITS, "fix": _D_FIX},
}


def _t(look, use=(), limits=(), fix=()):
    return {"look": look, "use": list(use), "limits": list(limits),
            "fix": list(fix)}


CARDS = {
    "window": {
        "fixed": _t("A frame and one fixed pane — nothing opens.", [_BARS]),
        "fixed_bars": _t("A fixed pane with glazing bars in a cross.",
                         [_BARS]),
        "industrial": _t(
            "A black frame and small fixed panes (3 × 3 bars).",
            ["It comes 2.00 × 1.60, sill 0.90, frame black; the bars "
             "change its grid.", _BARS]),
        "shop": _t(
            "A shop's display window: fixed panes from the floor, in a slim "
            "dark frame.",
            ["<b>Bar across</b> (glass over it), <b>Base under the "
             "glass</b>, <b>Roll-up shutter</b>, <b>Sign band</b> — in the "
             "Library.",
             "It comes as high as a shopfront (2.70, sill 0), so their lines "
             "meet round a corner. Width 0.80 to 12 m."],
            ["It doesn't turn a corner; no shape, no glazing bars, no stone "
             "sill."]),
        "sliding": _t(
            "Two glazed leaves in two tracks, one sliding over the other.",
            ["<b>Leaves</b> 2, 3 or 4 (the Sliding 3 and 4 cards). "
             "<b>Louvres</b>: Louvred turns it into a veneziana.", _BARS,
             "<b>Open</b> slides the leaves in 3D."],
            ["It opens to no side: no In / Out."]),
        "sliding3": _t("Three glazed leaves sliding past each other.",
                       ["<b>Leaves</b> 2, 3 or 4.", _BARS],
                       ["It opens to no side: no In / Out."]),
        "sliding4": _t(
            "Four glazed leaves; the middle two slide open.",
            ["<b>Leaves</b> 2, 3 or 4.", _BARS],
            ["It opens to no side: no In / Out."]),
        "slide_top": _t(
            "Three sliding leaves under a fixed pane, a bar between.",
            ["<b>Top light</b>: the fixed pane's height (0: none); the "
             "leaves take the rest of the Height.", _BARS]),
        "louvred3": _t(
            "Veneziana: two louvred leaves outside, one glass leaf inside.",
            ["<b>Leaves</b>: 3 (2 louvred + 1 glass) or 6 (4 + 2) — no "
             "other count.",
             "The louvres run on the outside face, the glass on the inside; "
             "<b>Open</b> slides them and shows the glass."],
            [_NO_BARS]),
        "louvred6": _t(
            "Veneziana: four louvred leaves outside, two of glass inside.",
            ["<b>Leaves</b>: 3 (2 louvred + 1 glass) or 6 (4 + 2) — no "
             "other count.",
             "The louvres run on the outside face, the glass on the inside; "
             "<b>Open</b> slides them and shows the glass."],
            [_NO_BARS]),
        "casement": _t(
            "Two leaves hinged on the jambs, meeting in the middle.",
            _CASEMENT + [_BARS], fix=_CASEMENT_FIX),
        "casement1": _t(
            "One leaf hinged on a jamb.",
            ["<b>Hinge</b>: Left / Right — the jamb it hangs on.",
             "<b>Opens</b> In / Out — or <b>Shift+Tab</b> before the click. "
             "<b>Handle</b>: None or a lever.", _BARS],
            fix=_CASEMENT_FIX[1:]),
        "casement3": _t("Two hinged leaves with a fixed one between them.",
                        _CASEMENT + [_BARS], fix=_CASEMENT_FIX),
        "casement4": _t("Four hinged leaves, in two pairs.",
                        _CASEMENT + [_BARS], fix=_CASEMENT_FIX),
        "fixed_hinged": _t(
            "A wide fixed pane and a narrower hinged leaf beside it.",
            ["Leaf 1 is the fixed one, 65 % of the width: <b>Leaf 1 "
             "width</b> resizes it."] + _CASEMENT, fix=_CASEMENT_FIX),
        "wide_centre": _t(
            "A wide fixed pane between two hinged leaves.",
            ["Leaf 2, in the middle, takes 50 %; the hinged ones share the "
             "rest."] + _CASEMENT, fix=_CASEMENT_FIX),
        "casement_top": _t(
            "Two hinged leaves under a fixed pane.",
            ["<b>Top light</b>: the fixed pane's height (0: none)."]
            + _CASEMENT, fix=_CASEMENT_FIX),
        "french_bars": _t(
            "Two hinged leaves with small panes.",
            [_BARS] + _CASEMENT, fix=_CASEMENT_FIX),
        "sash": _t(
            "Two leaves, one over the other; the lower one slides up "
            "(guilhotina).",
            ["<b>Open</b> lifts the lower leaf in 3D.", _BARS]),
        "sash_bars": _t("A sash window with small panes.",
                        ["<b>Open</b> lifts the lower leaf in 3D.", _BARS]),
        "awning": _t(
            "One leaf hinged at its top, its foot pushed out (maxim-ar).",
            ["It comes small and high — 0.60 × 0.60, sill 1.50 — change "
             "them in the bar.", "<b>Open</b> pushes it out in 3D."],
            [_NO_BARS]),
        "pivot": _t(
            "Horizontal panes, each turning on its middle (basculante).",
            ["<b>Panes</b>: Auto (by its height) or 2 to 6.",
             "<b>Open</b> turns them, up to 60°. It comes 0.60 × 0.80, sill "
             "1.40."],
            [_NO_BARS]),
        "round_arch": _t(
            "A half-round top over straight sides.",
            _SHAPED + ["With leaves under the arch: the <b>Casement under "
                       "arch</b> card."], _SHAPED_LIMITS),
        "round_top": _t("Straight sides, its two top corners rounded.",
                        _SHAPED + ["<b>Rise</b>: the corners' radius."],
                        _SHAPED_LIMITS),
        "seg_arch": _t("A shallow curved top over straight sides.",
                       _SHAPED + [_RISE], _SHAPED_LIMITS),
        "gothic": _t("A pointed arch over straight sides.",
                     _SHAPED + [_RISE], _SHAPED_LIMITS),
        "gable": _t("A top in two slopes, a peak in the middle.",
                    _SHAPED + [_RISE], _SHAPED_LIMITS),
        "bulls_eye": _t("A round window.",
                        _SHAPED + ["Always as high as wide: the Width sets "
                                   "both."], _SHAPED_LIMITS),
        "oval": _t("An upright oval.",
                   _SHAPED + ["Width and Height set the oval."],
                   _SHAPED_LIMITS),
        "triangle": _t("A triangle, its peak in the middle — for under a "
                       "gable.", _SHAPED, _SHAPED_LIMITS),
        "trapezoid": _t("Four sides, its top narrower and centred.",
                        _SHAPED + ["<b>Top width</b>: its top's width, "
                                   "centred."], _SHAPED_LIMITS),
        "arch_casement": _t(
            "Two hinged leaves under a round arch, a fixed light in the "
            "arch.", _SHAPED[:1] + _CASEMENT,
            ["It doesn't turn a corner and takes no glazing bars."],
            _CASEMENT_FIX),
    },
    "door": {
        "swing": _t("One plain leaf hinged on a jamb.", [_SINGLE, _LEAF]),
        "panelled": _t("One leaf with two raised panels on each face.",
                       [_SINGLE, _LEAF]),
        "six": _t("One leaf with six raised panels on each face.",
                  [_SINGLE, _LEAF]),
        "half": _t("Glass over a solid lower half.",
                   ["<b>Glass</b>: See-through or Opaque.", _SINGLE, _LEAF]),
        "french": _t("One glazed leaf in a slim frame.",
                     ["<b>Glass</b>: See-through or Opaque.", _SINGLE,
                      _LEAF]),
        "plank": _t("Vertical boards on the front; ledges and braces on the "
                    "back.", [_SINGLE, _LEAF]),
        "dutch": _t("Two halves, one over the other, a shelf between them.",
                    [_SINGLE, _LEAF]),
        "transom": _t(
            "A plain leaf with a fixed glass pane over it, a bar between.",
            ["<b>Top light</b>: the pane's height; the door's Height "
             "includes it — it comes 2.50 = 2.10 + 0.40.", _SINGLE]),
        "double": _t("Two plain leaves meeting in the middle.",
                     ["It comes 1.60 wide; each leaf takes half.", _TWO]),
        "double_panelled": _t("Two panelled leaves meeting in the middle.",
                              [_TWO]),
        "french2": _t("Two glazed leaves meeting in the middle "
                      "(porta-balcão).",
                      [_TWO, "<b>Glass</b>: See-through or Opaque."]),
        "barn2": _t("Two plank leaves: sheds, gates.",
                    ["It comes 2.00 × 2.20 with pull bars.", _TWO]),
        "sliding": _t(
            "One leaf on a rail along the wall's face.",
            ["<b>Hinge · slides to</b>: the side it opens to (Tab). "
             "<b>Opens</b> In / Out: the face its leaf runs on."]),
        "sliding2": _t("Two leaves parting in the middle.",
                       ["It comes 1.60 wide."],
                       ["No In / Out: the two leaves run inside the "
                        "wall."]),
        "pocket": _t("One leaf that runs into the wall — a pocket door "
                     "(Scrigno type).",
                     ["<b>Hinge · slides to</b>: the side of the wall it "
                      "runs into (Tab). It runs as far as the wall lets it.",
                      "Two leaves into the wall: <b>Sliding double</b>."],
                     ["No In / Out: its leaf runs inside the wall."]),
        "barn": _t("A plank leaf on a rail in sight.",
                   ["<b>Hinge · slides to</b>: the side it opens to (Tab). "
                    "<b>Opens</b> In / Out: the face its leaf runs on."]),
        "glass": _t(
            "Glazed leaves in a slim dark frame, in two tracks.",
            ["One leaf: <b>Opens</b> In / Out is the face its moving pane "
             "runs on. Two: they run inside the wall.",
             "<b>Glass</b>: See-through or Opaque."]),
        "shop": _t(
            "A shop's whole front: fixed glass panes, a glazed door, a "
            "transom and a base.",
            ["<b>Door</b>: 2 leaves, 1 leaf or Sliding; <b>Door at</b> Left "
             "/ Centre / Right; <b>Opens</b> Out (to the street) or In — a "
             "sliding one neither.",
             "<b>Over the door</b>: Glass or Panel; <b>Roll-up shutter</b>; "
             "<b>Sign band</b>; <b>Door height</b>; <b>Base under the "
             "glass</b>.",
             "Width 1.50 to 12 m, Height 2.20 to 4.50 m.",
             "Selected: <b>Fill the bay</b> makes it pier to pier — as wide "
             "as the stretch of wall it stands in.",
             "A <b>Shop window</b> round the corner comes as high: their "
             "lines meet."],
            ["No Hinge, no Tab: its door is set in the Library."]),
        "garage": _t("A sectional garage door: horizontal panels.",
                     _GARAGE + ["<b>Windows</b>: None or a row on top."],
                     _GARAGE_LIMITS),
        "rollup": _t("Slats rolling up into a box, its guides inside.",
                     _GARAGE, _GARAGE_LIMITS + ["No row of windows."]),
        "tilt": _t("One ribbed panel turning up and over.",
                   _GARAGE + ["<b>Windows</b>: None or a row on top."],
                   _GARAGE_LIMITS),
        "arched": _t(
            "A swing leaf up to where the arch springs, a half-round glass "
            "light over it.",
            ["<b>Top</b>: Square or Arched — the Swing card takes the arch "
             "off.", _SINGLE],
            ["No top light under an arch."]),
    },
}


# ---- walls (batch 2, 20/11/2026) ----------------------------------------------------------
_WALL_USE = [
    "Point by point: click point after point; type a length + <b>Enter</b> "
    "to lay the next point that far. <b>C</b> (or a click on the first "
    "point) closes the room; <b>Enter</b> or a double-click ends it open; "
    "<b>Backspace</b> takes the last point back.",
    "The other ways, on the left: <b>Rectangle</b> (corner to corner, from "
    "its centre or rotated), <b>Curved wall</b>, <b>Round wall</b>.",
    "<b>Alignment</b> — Outside, Centre, Inside: which face sits on the "
    "line you draw. <b>Tab</b> while drawing puts the wall on the other "
    "side. A new thickness never moves that face.",
    "<b>Height</b>: the level's (it follows the level) or <b>Custom</b> — "
    "a low wall, a parapet.",
    "Corners, T's and crossings join by themselves, and again whenever a "
    "wall changes — never cut them by hand.",
    "Walls already drawn: select them — a card changes all of them at "
    "once. A double-click opens its window: <b>Geometry</b>, "
    "<b>Position</b> (Start, End, Length), <b>Layers</b>, <b>Shape</b>.",
    "An end moved afterwards: <b>Edit walls › Move points</b> — the walls "
    "meeting there follow, the corner stays a corner. <b>Split</b>, "
    "<b>Join</b> and <b>Trim / Extend</b> are there too. Selected, "
    "<b>Move across</b> / <b>Move along</b> in the Library slide it, its "
    "doors and windows with it.",
]
_WALL_LIMITS = [
    "A card is a whole wall: picked for a wall with layers (or one of your "
    "types), the wall becomes that card's — its layers go. Ctrl+Z brings "
    "them back.",
    "Doors and windows go in straight walls only.",
]
_WALL_FIX = [
    ("The wall is on the wrong side of the line",
     "<b>Tab</b> while drawing — or <b>Alignment</b> on the selected "
     "walls."),
    ("A new thickness moved the wrong face",
     "<b>Alignment</b> decides which face stays: set it first, then the "
     "thickness."),
    ("A corner doesn't close, or the walls cross at it",
     "The ends must meet: <b>Edit walls › Move points</b> snaps an end onto "
     "the other; <b>Trim / Extend</b> lands it on the other wall's line."),
    ("«Three points at least to close»",
     "<b>C</b> closes a run of 3 points or more; one wall alone: end it "
     "with <b>Enter</b>."),
    ("«Build it there anyway?» as it is drawn",
     "It reaches into the plot's setbacks (Terrain): build it anyway, or "
     "draw it inside the dashed area."),
]
_PLAIN = ("Its <b>Thickness</b> is the bar's: any other number makes the "
          "same wall thinner or thicker.")
_LOOK = ("Its faces wear the card's look — a texture in Pro, a colour in "
         "Lite; change it in the wall's <b>Material</b> tab.")
_GRID = [
    "<b>Panes per bay</b>: Auto or 2 to 6. <b>Corners</b>: Mitred (45°, "
    "as PVC or aluminium) or Butt.",
    "<b>Fill a pane</b>: pick what goes in — Glass, Panel, Awning, "
    "Hopper, Pivot, Casement, Sliding, Louvre, Door, Double door, Sliding "
    "door, Empty — then click the panes: only the pane clicked changes. "
    "<b>Esc</b> ends it.",
    "<b>Join panes</b>: Join, then click two panes of one bay — they and "
    "all between them become one (a wide door, a tall glass). Split: "
    "click a joined pane.",
    "<b>Pattern</b>: Copy keeps the selected grid wall's pattern; Paste "
    "puts it on the grid walls selected — their lengths and places stay.",
    "Its window (double-click): <b>Grid</b>, <b>Cells</b>, "
    "<b>Profiles</b> — the panes' widths, the rows, the fills, the frame's "
    "sizes and colours.",
    "Picked for a wall already drawn, it keeps the wall's thickness; a new "
    "one is 10 cm deep. A door or window drawn in it cuts every piece.",
]
_BETWEEN = ("It stands BETWEEN the columns, from the floor to the "
            "underside of the beam (or slab) over it: draw ONE line along "
            "the whole front — each bay fills itself, the columns cut it.")
_OWN_H = ("It stands up to the wall's own height, as any wall — draw it "
          "where the glass goes.")
_GRID_LIMITS = ["No layers: its frame is its section. Its Shape tab "
                "changes its top only."]
_GRID_FIX = [
    ("«Select a grid wall first»",
     "<b>Pattern</b> Copy needs one grid wall selected."),
    ("Its panes are not where you want them",
     "<b>Panes per bay</b>, or its window's <b>Grid</b> tab: the widths "
     "typed, «*» for the rest."),
]
_MARKET = [
    "The first click puts it in YOUR types («… is one of your types "
    "now»); from then on it is picked as yours, under Your types. Ctrl+Z "
    "takes it out again.",
    "Its layers, their thicknesses and its studs: double-click its card "
    "under Your types, or the wall's <b>Layers</b> tab — change them as "
    "yours.",
    "Its faces wear each layer's material; change them in the wall's "
    "<b>Material</b> tab.",
    "<b>Alignment</b> <b>Core face</b>: the line you draw is the "
    "structure's face, whatever the finishes over it.",
]
_FRAMED = ("Studs, blocking and the corners' and T's studs show in the 3D; "
           "on the sheets at 1:50 or closer.")
_FRAMED_LIMITS = ["A full circle is built solid for now."]

COMMON["wall"] = {"use": _WALL_USE, "limits": _WALL_LIMITS,
                  "fix": _WALL_FIX}
CARDS["wall"] = {
    "w15": _t("A plain 15 cm wall — one solid core, no layers.", [_PLAIN]),
    "w20": _t("A plain 20 cm wall — one solid core, no layers.", [_PLAIN]),
    "w10": _t("A plain 10 cm partition — one solid core.",
              ["A partition is just a thinner wall: it joins the outer "
               "walls at a T by itself.", _PLAIN]),
    "curtain": _t(
        None,
        ["<b>Mullions every</b> (0.50 to 3.00 m), <b>Rows of panes per "
         "floor</b> (1 to 4), <b>Band at each floor</b> and <b>Band over "
         "the floor</b> (its height, on the outer face) — in the Library.",
         "With nothing selected, its window sets the next ones drawn; with "
         "curtain walls selected, it changes them.",
         "Doors and windows drawn in it cut through its glass and "
         "mullions."],
        ["No layers, no Shape tab; a corner window doesn't go in it."]),
    **{k: _t(None, [_LOOK]) for k in ("masonry25", "concrete15",
                                      "concrete20", "brick", "cblock",
                                      "glass_block")},
    **{k: _t(None, [_LOOK, "<b>Boards</b>: Battens, Lap siding or Smooth — "
                           "drawn, so a sheet's elevation shows them."])
       for k in ("boards_v", "boards_h")},
    "gw_industrial": _t(None, [_BETWEEN, "<b>Panel height</b> (from the "
                               "floor) and <b>Window band</b> set its "
                               "rows."] + _GRID, _GRID_LIMITS, _GRID_FIX),
    "gw_full": _t(None, [_BETWEEN] + _GRID, _GRID_LIMITS, _GRID_FIX),
    "gw_office": _t(None, [_BETWEEN, "<b>Panel height</b>: the opaque "
                           "sill panel's, from the floor."] + _GRID,
                    _GRID_LIMITS, _GRID_FIX),
    "gw_vent": _t(None, [_BETWEEN] + _GRID, _GRID_LIMITS, _GRID_FIX),
    "gw_storefront": _t(None, [_OWN_H] + _GRID, _GRID_LIMITS, _GRID_FIX),
    "gw_living": _t(None, [_OWN_H] + _GRID, _GRID_LIMITS, _GRID_FIX),
    "gw_partition": _t(None, [_OWN_H] + _GRID, _GRID_LIMITS, _GRID_FIX),
    **{"m_" + k: _t(None, _MARKET + [_FRAMED], _FRAMED_LIMITS)
       for k in ("us2x4", "us2x6", "usint", "eutimber", "lsf", "drywall")},
    **{"m_" + k: _t(None, _MARKET) for k in ("ukcavity", "etics")},
}

# ---- slabs (batch 2, 20/11/2026) ----------------------------------------------------------
_SLAB_USE = [
    "<b>Inside the walls</b>: one click inside the level's walls — the "
    "slab under them, to their outer faces. Or <b>Rectangle</b> (from a "
    "corner, its centre, or rotated) and <b>Point by point</b> for any "
    "outline.",
    "Its <b>Top</b> is the level's floor (0); its thickness goes DOWN from "
    "there. A small negative Top sinks it — a bathroom, a terrace. The "
    "Top stays at most the level's height.",
    "Over a wall, a corner goes onto the wall's centre line (blue dashed "
    "while it holds); a snap on a face's corner or middle keeps the face.",
    "The level below's walls and columns stop at its underside; beams go "
    "up into it, flush with its top; stairs and ramps open their way "
    "through it.",
    "Slabs already drawn: select them — a card changes all of them. A "
    "double-click opens its window: <b>Geometry</b> (Thickness, Top, its "
    "Openings and Curves), <b>Layers</b>.",
    "A hole (a stair, a lift, a void): <b>Opening in a slab</b>, drawn "
    "inside it — a rectangle, point by point or a circle. Selected, each "
    "opening has grips; <b>Delete</b> closes the one picked.",
    "Curves: <b>Edit slabs › Round corner / Bend side</b>, or the round "
    "grips of a picked slab. From lines: draw the outline with "
    "IngeTrazo's lines and arcs, right-click ▸ ArchXQ ▸ <b>Slab from "
    "outline</b>.",
]
_SLAB_LIMITS = [
    "A card is a whole slab: picked for a slab with layers (or one of your "
    "types), the slab becomes that card's — its layers go. Ctrl+Z brings "
    "them back.",
]
_SLAB_FIX = [
    ("The slab stands over the floor, up the doors",
     "Its <b>Top</b> is over 0: type Top 0 — with a point or a comma, "
     "both work."),
    ("«Too small for a slab»",
     "Three corners at least, and an outline more than a few cm across."),
    ("«A slab is already there — nothing new made»",
     "<b>Slab from outline</b> makes one slab per outline: the one there "
     "stays — delete it first to make it again."),
]
_SLAB_PLAIN = ("Its <b>Thickness</b> is the bar's: any other number makes "
               "the same slab thinner or thicker.")
_LAYERED = [
    "Its <b>Top</b> is the FINISHED floor; the layers go down from it, and "
    "the walls stand on the slab.",
    "Its layers — each one's name, thickness and material: the slab's "
    "<b>Layers</b> tab.",
]
_FLOOR = [
    "Its layers and joists go on the selected slabs and on the next ones "
    "drawn; each slab keeps them as its own — its <b>Layers</b> tab.",
    "The joists show in the 3D. A span past about 20× their depth is "
    "said in yellow: add a beam or a wall under it — it never blocks.",
]

COMMON["slab"] = {"use": _SLAB_USE, "limits": _SLAB_LIMITS,
                  "fix": _SLAB_FIX}
CARDS["slab"] = {
    "s12": _t("A plain 12 cm concrete slab — one solid core, no layers.",
              [_SLAB_PLAIN]),
    "s15": _t("A plain 15 cm concrete slab — one solid core, no layers.",
              [_SLAB_PLAIN]),
    "s20": _t("A plain 20 cm concrete slab — one solid core, no layers.",
              [_SLAB_PLAIN]),
    "tiles": _t(None, _LAYERED),
    "timber": _t(None, _LAYERED),
    "roofslab": _t(None, _LAYERED),
    "ceiling": _t(
        None,
        ["<b>Ceiling height</b> (2.00 to 5.00 m): its underside over the "
         "level's floor — what is seen from the room.",
         "<b>Inside the walls</b>: a click in a room gives its ceiling.",
         "A 2 cm board, white unless you change its material."],
        ["It is no floor: the level's slab is drawn apart."]),
    **{"f_" + k: _t(None, _FLOOR)
       for k in ("fus2x10", "feutimber", "fsteel", "fraised")},
}


# ---- columns (batch 3, 24/11/2026) -------------------------------------------------------

_C_USE = [
    "<b>Stamp</b>: it rides the cursor, each click places one (<b>Esc</b> "
    "when done). <b>Draw</b>: two opposite corners, its size and its place."
    " <b>Row</b>: point by point, like a wall — the first point again "
    "closes it. <b>Grid</b>: two opposite corners. <b>At the wall "
    "corners</b>: one click, a column wherever this level's walls meet.",
    "Its size, <b>Angle</b> and <b>Base</b> in the options bar on top — set"
    " them before the click. <b>Base</b>: 0 is the level's floor; negative "
    "goes down into the ground, to a footing.",
    "<b>Height</b> <b>To the slab</b>: up to the underside of the slab "
    "above — it follows it. <b>Custom</b>: a number of its own.",
    "On a wall, <b>In walls</b> <b>Fit inside</b>: it takes the wall's "
    "thickness and line and hides in it. <b>As drawn</b>: its own size, to "
    "show.",
    "Near a wall, a plot side or another column, its faces are pulled flush"
    " (orange dashed guides); its middle is pulled onto the walls' corners "
    "and onto the columns of the levels below and above.",
    "Columns already drawn: select them — a card changes all of them. A "
    "double-click opens the window. A column of a row gives its section and"
    " its sizes to the whole row.",
    "Selected, its grips: its sides (the one opposite stays), its top, its "
    "foot and its middle, that moves it — the arrow ↑ while moving: up and "
    "down.",
]

_C_LIMITS = [
    "Its smallest side: 5 cm.",
]

_C_FIX = [
    ("The column doesn't show on a wall",
     "It was fitted: it is inside the wall — filled grey in plan. Set <b>In"
     " walls</b> to <b>As drawn</b> before drawing it, to show it."),
    ("It doesn't reach the slab",
     "With <b>Custom</b> it keeps its number: set <b>Height</b> to <b>To "
     "the slab</b>. With no slab above yet, it goes to the level's top."),
]

_C_ORDER = [
    "<b>Base</b> and <b>Capital</b> in the Library change its foot and its "
    "head apart: any base with any capital.",
    "Both are sized by the column's width and stand within its height: a "
    "wider column has a taller base.",
]

_C_ORDER_LIM = [
    "They go on a rectangular or a round column — not on an outline of its "
    "own.",
]

_C_SEC = [
    "Its middle goes on the cursor. <b>Angle</b> in the options bar turns "
    "it: 90, 180, -90.",
    "<b>Width</b> and <b>Depth</b> stretch it, its arms with it. Arms of "
    "another thickness: double-click it, the <b>Shape</b> tab, <b>Arms</b>.",
]

_C_SEC_LIM = [
    "Always as drawn: it doesn't take a wall's thickness. No base and no "
    "capital.",
]

_C_STEEL = [
    "At the sizes of the European tables, its root fillets too: the weight "
    "in the quantities is the table's.",
    "Another size: double-click it, the <b>Shape</b> tab, <b>Steel</b> — "
    "IPE from 200, HEA from 120, HEB from 100.",
    "<b>Angle</b> 90 in the options bar turns its web.",
]

_C_STEEL_LIM = [
    "A <b>Width</b> or a <b>Depth</b> of your own stretches it: no longer a"
    " section of the tables.",
]


COMMON["column"] = {"use": _C_USE, "limits": _C_LIMITS, "fix": _C_FIX}
CARDS["column"] = {
    "rect": _t(
        "A plain rectangular column.",
        ["<b>Width</b> and <b>Depth</b>, 5 cm to 5 m. The bar's "
         "<b>Centre</b> list is the point of the column that goes on the "
         "cursor: a corner or a side's middle lays it flush with a face.",
         "Any other outline (Pro): its window's <b>Shape</b> tab, or "
         "right-click ▸ <b>Edit shape…</b>."]),
    "round": _t(
        "A plain round column.",
        ["<b>Diameter</b> in the options bar. On a wall, <b>Fit inside</b> "
         "makes it as thick as the wall."]),
}
if not edition.lite():               # (the Pro's cards)
    CARDS["column"].update({
        **{k: _t(None, _C_ORDER, _C_ORDER_LIM)
           for k in ("round_tuscan", "round_doric", "round_attic",
                     "round_empire", "round_pedestal", "sq_tuscan",
                     "sq_doric", "sq_attic", "sq_deco", "sq_pedestal")},
        **{k: _t(None, _C_SEC, _C_SEC_LIM) for k in ("cL", "cT", "cX")},
        **{k: _t(None, _C_STEEL, _C_STEEL_LIM + _C_SEC_LIM)
           for k in ("cIPE200", "cIPE300", "cHEA200", "cHEA300", "cHEB200",
                     "cHEB300")},
    })

# ---- roofs (batch 3) ---------------------------------------------------------------------

_R_USE = [
    "<b>Over the walls</b>: one click, a roof over this level's walls — on "
    "the top floor. Or <b>Rectangle</b> (from a corner, its centre, or "
    "rotated) and <b>Point by point</b>.",
    "Made over the walls, it follows them: pull a wall out and the roof "
    "goes with it. One whose corners you moved by hand stays as you left "
    "it.",
    "<b>Height</b> <b>On the walls</b>: its eaves at the top of the level's"
    " walls. <b>Its own</b>: <b>Eaves at</b> a height over the level's "
    "floor — a lean-to on columns, a porch lower than the house.",
    "<b>Slope</b>, <b>Overhang</b> and <b>Thickness</b>: in the options bar"
    " or the Library's bars — the selected roofs follow.",
    "Roofs already drawn: select them — a card changes all of them. A "
    "double-click opens the window: <b>Geometry</b> (its type, slope, "
    "height and ridge) and, on the pitched ones, <b>Layers</b>.",
    "Selected, its grips: on the walls' line, each side moves alone; the "
    "grip outside it is the overhang.",
    "Each of its parts takes a material of its own in the <b>Material</b> "
    "tab.",
]

_R_LIMITS = [
    "A pitched roof's <b>Slope</b>: 5° to 75°.",
]

_R_FIX = [
    ("«Draw the walls first, or draw the roof's outline…»",
     "The level you are on has no closed walls: go to the level whose walls"
     " it rests on, or draw its outline."),
    ("The roof stands a floor too low",
     "It rests on the walls of the level it was drawn on: delete it and "
     "draw it on the top floor."),
]

_R_RECT = (
    "On a rectangle: over any other plan it takes the rectangle round the "
    "walls.")

_R_ANY = (
    "Over an L, a T, a U or an oblique plan it follows the walls, its ridges "
    "and valleys by themselves.")

_R_MARKET = [
    "Its layers and its frame go on the selected roofs and on the next ones"
    " drawn; their type (Gable, Hip…) stays.",
    "Change them in the roof's <b>Layers</b> tab: each layer's name and "
    "thickness, the frame's spacing. The eye on a layer hides it, to show "
    "the frame inside.",
]

_R_MARKET_LIM = (
    "Built in its layers on gable, hip, shed and butterfly roofs on a "
    "rectangle; the others are solid for now.")


COMMON["roof"] = {"use": _R_USE, "limits": _R_LIMITS, "fix": _R_FIX}
CARDS["roof"] = {
    "gable": _t(
        None,
        ["<b>Ridge along</b>: the long side or the short side. <b>Gable "
         "ends</b>: how far it passes the end walls — they go up to the "
         "roof by themselves.",
         "Two different slopes, or eaves at two heights: its window, "
         "<b>Other side</b> and <b>Other side's eave</b> — the ridge moves "
         "off the middle by itself. On a rectangle.",
         "Over an L, its window has <b>Main wing</b>: the wing that keeps "
         "its gable at the corner.",
         _R_ANY]),
    "hip": _t(None, [_R_ANY],
              ["One slope for all its sides."]),
    "flat": _t(
        None,
        ["<b>Parapet</b>: its height over the roof (0: none). Any outline, "
         "point by point."]),
    "shed": _t(
        None,
        ["<b>Falls to</b>: which long side is the low one. The high wall "
         "and the end walls rise to it by themselves."],
        [_R_RECT]),
    "hidden": _t(
        None,
        ["It comes at 10°, for sheets. <b>Slopes</b> One or Two; "
         "<b>Gutter</b>: its width, along the low side.",
         "The parapet on <b>Auto</b> just hides the roof; <b>Typed</b>: "
         "your own height, over the walls' top."],
        [_R_RECT, "No overhang: it stays inside its parapet."],
        [("«Too narrow for a hidden roof (its parapet and gutter take the "
          "room)»",
          "Make it wider, its <b>Gutter</b> narrower, or its <b>Slopes</b> "
          "One.")]),
    "butterfly": _t(
        None,
        ["The valley runs along the middle and the walls rise to the high "
         "eaves by themselves: a small <b>Slope</b> keeps them low."],
        [_R_RECT]),
    "mansard": _t(
        None,
        ["<b>Break height</b> (0.30 to 4.00 m): how high the steep part "
         "rises over the walls. <b>Slope</b> is the gentle upper roof's."],
        [_R_RECT]),
    "lt": _t(
        None,
        ["One click on the card builds it: nothing to draw."],
        ["One slope for all its sides."],
        [("«… make a plain rectangle (or no closed outline)…»",
          "Over a rectangle pick <b>Hip</b> or <b>Gable</b>. Walls that "
          "don't close: close them, or draw the roof <b>Point by point</b>.")]),
    "rsolid": _t(
        None,
        ["It takes the layers and the frame off the selected roofs and the "
         "next ones; their type stays."]),
    **{"r_" + k: _t(None, _R_MARKET, [_R_MARKET_LIM])
       for k in ("rus2x8", "reutimber", "rsteel", "rcold")},
    **{"r_" + k: _t(
        None,
        _R_MARKET + ["The ceiling is flat, under the trusses: the walls "
                     "inside the house stop at it."],
        ["Trusses on gable and shed roofs only.",
         _R_MARKET_LIM])
       for k in ("rustruss", "reutruss")},
}


def _corner_ok(element: str, t) -> bool:
    """A window card that can turn a corner (cornerwin.why_not_window)."""
    if element != "window" or t is None or not t.set:
        return False
    return t.set.get("op") != "shop" and t.set.get(
        "oshape", "rect") == "rect"


def texts() -> list[str]:
    """Every text these helps show (the test: all of them translated)."""
    out = []

    def add(d):
        out.extend(d.get("use", ()))
        out.extend(d.get("limits", ()))
        for p, s in d.get("fix", ()):
            out.extend((p, s))
        if d.get("look"):
            out.append(d["look"])
    for d in COMMON.values():
        add(d)
    add(CORNER)
    for cards in CARDS.values():
        for d in cards.values():
            add(d)
    return list(dict.fromkeys(out + ["A type of your own"] + list(HEADS)))


#: the page's headings (shown through tr)
HEADS = ("Using this type", "Placing and changing it", "Limits")


def has_text(element: str, key: str) -> bool:
    return key in CARDS.get(element, {})


def _guide_key(element: str) -> str | None:
    from .guide import GUIDES
    return element if element in GUIDES else None


def _shelf_title(element: str) -> str:
    from .library import CATALOG
    s = CATALOG.get(element)
    return s.title if s else element


# ---- the page -------------------------------------------------------------------------
_CSS = (
    "h1 { color: white; font-size: 21px; margin: 2px 0 2px 0; }"
    ".phase { color: #9aa5b1; font-size: 12px; letter-spacing: 2px; }"
    ".look { color: #cfd6de; font-size: 15px; margin: 2px 0 10px 0; }"
    "h2 { color: #e8742c; font-size: 15px; margin: 16px 0 6px 0; }"
    "p, li { line-height: 140%; }"
    "td { padding: 4px 12px 4px 0; vertical-align: top; }"
    "td.k { color: white; font-weight: bold; }"
    ".pro { background: #3b2a6b; color: white; padding: 6px; }"
    "a { color: #8fd3ff; }")


def page(element: str, t=None, mine: dict | None = None) -> str:
    """The card's help, as HTML in ArchXQ's language."""
    import html

    from .i18n import tr, tr_long
    own = CARDS.get(element, {}).get(t.key) if t is not None else None
    common = COMMON.get(element)
    if t is not None:
        label, look = tr(t.label), (own or {}).get("look") or t.tip
    else:
        label = (mine or {}).get("name") or tr(_shelf_title(element))
        look = "A type of your own"
    out = [f"<style>{_CSS}</style>",
           f"<div class='phase'>{html.escape(tr(_shelf_title(element))).upper()}"
           f"</div><h1>{html.escape(label)}</h1>"]
    if look:
        out.append(f"<p class='look'>{tr_long(look)}</p>")

    def bullets(head: str, lines) -> None:
        if lines:
            out.append(f"<h2>{tr(head)}</h2><ul>")
            out.extend(f"<li>{tr_long(x)}</li>" for x in lines)
            out.append("</ul>")
    if own:
        bullets("Using this type", own["use"])
    if common:
        bullets("Placing and changing it", common["use"])
    else:                       # no text of its own yet: the guide's tips
        from .guide import GUIDES
        g = GUIDES.get(element) or {}
        bullets("Placing and changing it", g.get("tips", ()))
    if _corner_ok(element, t):
        out.append(f"<h2>{tr('Round the corner')}</h2>")
        if edition.lite():
            out.append(f"<p class='pro'><b>{tr('Available in ArchXQ IT Pro')}"
                       f"</b> &nbsp;<a href='{edition.PRO_URL}'>"
                       f"{tr('Get Pro')}</a></p>")
            out.append(f"<ul><li>{tr_long(CORNER['use'][0])}</li></ul>")
        else:
            out.append("<ul>" + "".join(f"<li>{tr_long(x)}</li>"
                                        for x in CORNER["use"]) + "</ul>")
    limits = list((own or {}).get("limits", ())) + list(
        (common or {}).get("limits", ()))
    if _corner_ok(element, t) and not edition.lite():
        limits += CORNER["limits"]
    bullets("Limits", limits)
    fix = list((own or {}).get("fix", ())) + list(
        (common or {}).get("fix", ()))
    if _corner_ok(element, t) and not edition.lite():
        fix += CORNER["fix"]
    if fix:
        out.append(f"<h2>{tr('If something goes wrong')}</h2><table>")
        out.extend(f"<tr><td class='k'>{tr_long(p)}</td>"
                   f"<td>{tr_long(s)}</td></tr>" for p, s in fix)
        out.append("</table>")
    return "".join(out)


# ---- the window -----------------------------------------------------------------------
_WIN_CSS = (
    "QDialog { background: #1d2025; }"
    "QTextBrowser { background: #1d2025; color: #e8eaed; border: none; "
    "font-size: 14px; padding: 4px 12px; }"
    "QLabel#pic { background: #23262b; border-radius: 8px; }"
    "QPushButton { background: #2a2e34; color: #e8eaed; border: 1px solid "
    "#3a3f46; border-radius: 4px; padding: 6px 14px; font-size: 13px; }"
    "QPushButton:hover { border-color: #2f7df6; }")


class CardHelp(QDialog):
    """A card's help: its picture beside the page; «Full guide» opens the
    element's guide (guide.GuideWindow)."""

    def __init__(self, element: str, t=None, mine=None, icon=None,
                 parent=None) -> None:
        super().__init__(parent)
        from .i18n import tr
        self.element = element
        self.go_guide = False
        name = tr(t.label) if t is not None else (mine or {}).get("name", "")
        self.setWindowTitle("ArchXQ — " + tr("Help") + " · " + name)
        self.setStyleSheet(_WIN_CSS)
        self.resize(QSize(780, 640))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 12)
        row = QHBoxLayout()
        row.setSpacing(12)
        pic = QLabel()
        pic.setObjectName("pic")
        pic.setFixedSize(QSize(132, 132))
        pic.setAlignment(Qt.AlignCenter)
        if icon is not None:
            pic.setPixmap(icon.pixmap(QSize(112, 112)))
        col = QVBoxLayout()
        col.addWidget(pic)
        col.addStretch(1)
        row.addLayout(col)
        self.text = QTextBrowser()
        self.text.setOpenExternalLinks(True)
        self.text.setHtml(page(element, t, mine))
        row.addWidget(self.text, 1)
        lay.addLayout(row, 1)
        bar = QHBoxLayout()
        bar.addStretch(1)
        if _guide_key(element):
            g = QPushButton(tr("Full guide: {what}",
                               what=tr(_shelf_title(element))))
            g.clicked.connect(self._guide)
            bar.addWidget(g)
        c = QPushButton(tr("Close"))
        c.clicked.connect(self.accept)
        c.setDefault(True)
        bar.addWidget(c)
        lay.addLayout(bar)

    def _guide(self) -> None:
        self.go_guide = True
        self.accept()


def open_help(element: str, t=None, mine=None, icon=None,
              parent=None) -> None:
    d = CardHelp(element, t, mine, icon, parent)
    d.exec()
    if d.go_guide:
        open_guide(element, parent)


def open_guide(element: str, parent=None) -> None:
    from . import guide
    key = _guide_key(element)
    if key:
        guide.open_guide(key, parent)


def menu_items(element: str, t=None, mine=None, icon=None,
               parent=None) -> list:
    """The card's right-click menu: (text, fn) — Help first."""
    from .i18n import tr
    name = tr(t.label) if t is not None else (mine or {}).get("name", "")
    items = [(tr("Help: {what}", what=name),
              lambda: open_help(element, t, mine, icon, parent))]
    if _guide_key(element):
        items.append((tr("Full guide: {what}", what=tr(_shelf_title(
            element))), lambda: open_guide(element, parent)))
    return items


def attach(card, element: str, t=None, mine=None) -> None:
    """Give a library card its right-click (library.Card.on_menu) and say
    so in its tooltip."""
    from .i18n import tr
    try:
        icon = card.icon()
        card.on_menu = lambda: menu_items(element, t, mine, icon,
                                          card.window())
        tip = card.toolTip()
        hint = tr("Right-click: how to use it")
        if hint not in tip:
            card.setToolTip((tip + "\n\n" if tip else "") + hint)
    except Exception:  # noqa: BLE001 — a card without its menu, never broken
        from . import compat
        compat.log_error("card help")
