"""The GUIDE — a small manual per tool, in a large window (his idea,
2026-10-04: «a help icon as the last item of each tool menu, opening a
big, complete help about that tool — for when you forget how it works»).

Opened from the last item of the left strip (``Help``) and from the end of
the options bar. The window lists the tools of the current phase on the
left and shows the picked one's manual on the right: what it is for, step
by step for each way of drawing it, tips, common mistakes, keys.

The short «?» popups (help.py) stay for quick hints; a tool with no guide
written yet shows its short help and its ways of drawing, so every tool
has a page from day one. The same texts feed the site's manual and the
video scripts.
"""
from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QTextBrowser,
    QVBoxLayout,
)

from . import edition
from .help import HELP
from .phases import ELEMENTS, PHASES, is_pro
from .style import BLUE

IMAGES = Path(__file__).with_name("guide_img")      # pictures, when there are

# ---- the pages --------------------------------------------------------------
# key = an ELEMENTS key. Every field optional except "what".
#   what   : what it is for (HTML)
#   steps  : [(way of drawing — as in the left strip, HTML), …]
#   tips   : [HTML, …]       mistakes : [HTML, …]      keys : [(key, does), …]
#   image  : a file in guide_img/ (shown under the title)
#   video  : a YouTube link
TERRAIN_VIDEO = ""      # set when the Terrain tutorial is out

GUIDES: dict[str, dict] = {
    "plot": {
        "image": "plot.jpg",
        "what": "The plot is the piece of land the project stands on. "
                "<b>Everything sits on it</b>: the ground, the excavations, "
                "the building — and the next phases open only once it "
                "exists. Draw it with its <b>real sizes</b> (from the deed "
                "or the survey).",
        "steps": [
            ("Rectangle", "Click one corner, move, click the opposite "
             "corner — or type the two sides (e.g. <code>24;36</code>) "
             "and Enter (see <b>Typing the sizes</b> above)."),
            ("Rectangle from centre", "Click the centre, then a corner. "
             "Handy when you know where the middle of the plot is."),
            ("Rotated rectangle", "Click the first corner, the second "
             "(that gives the first side and its angle), then the depth."),
            ("Point by point", "Click each corner in order; type a length "
             "+ Enter to fix a side. Close on the first point (or Enter) — "
             "any shape, any number of sides."),
        ],
        "tips": [
            "<b>Ground level</b> (left strip) is the height of the plot's "
            "surface; usually 0.00.",
            "After drawing, the sides can be typed exactly in "
            "<b>Edit plot › Sides &amp; heights…</b> — one pass through the "
            "table closes the plot.",
            "The plot's side lengths are written on the model while you "
            "work on the terrain (Settings › Plot dimensions).",
        ],
        "mistakes": [
            "<b>Drawing a second plot</b>: there is only one — a new "
            "rectangle asks «Replace the plot?». To change it, use "
            "<b>Edit plot</b>.",
            "Drawing in the 3D view: use <b>Plan view</b> (top left) for "
            "exact clicks.",
        ],
        "keys": [("Enter", "accept the typed sizes / close the outline"),
                 ("Esc", "cancel the drawing"),
                 ("Ctrl+Z", "undo")],
    },
    "plot_edit": {
        "image": "plot_edit.jpg",
        "what": "Change the plot after it is drawn: move its corners, add "
                "or delete corners, give each side its exact length and "
                "each corner its height (a <b>sloped</b> plot), fold the "
                "surface on a line.",
        "steps": [
            ("Move points", "Drag a corner. <b>X</b> / <b>Y</b> lock the "
             "move to an axis; <b>Z</b> changes the corner's <b>height</b> "
             "(move the mouse up/down or type the change); Z again frees "
             "it."),
            ("Add point", "Click on a side: a new corner appears there."),
            ("Delete point", "Click a corner to remove it."),
            ("Sides & heights…", "A table: one row per corner and the side "
             "that leaves it. Type the <b>lengths</b> from the deed (any "
             "order), the <b>angles</b> only if the deed gives them, the "
             "<b>height</b> of each corner. The row you are on lights up "
             "in blue on the model. <b>Apply</b> = one Ctrl+Z."),
            ("Fold line", "Draw a line across the plot: the sloped surface "
             "folds there instead of the smoothest way."),
            ("Delete plot", "Removes the plot — and its excavations and "
             "fills (it asks first)."),
        ],
        "tips": [
            "Double-click the plot to open <b>Sides &amp; heights</b>.",
            "Different corner heights slope the <b>surface</b>; the bottom "
            "of the ground stays flat.",
            "If the lengths cannot close the plot, the table says by how "
            "much.",
        ],
        "mistakes": [
            "Moving points by eye when the deed gives the sizes — type them "
            "in the table instead.",
        ],
        "keys": [("X / Y", "lock the move to the red / green axis"),
                 ("Z", "change the corner's height (again: free)"),
                 ("Ctrl+Z", "undo")],
    },
    "survey": {
        "what": "The ground <b>as measured</b>: points inside the plot, "
                "each with its elevation. The ground passes through every "
                "point and every plot corner (the surveyor's triangles — a "
                "TIN). Excavations and fills follow the new ground.",
        "steps": [
            ("Add point", "Click on the plot — or rest the cursor where it "
             "goes, type an elevation + Enter. Over an existing point, type "
             "a number + Enter to change its elevation."),
            ("Delete point", "Click a point."),
            ("Points & import…", "A table of the points, and <b>Import "
             "file…</b>: a text file from the surveyor (CSV / TXT) — one "
             "point per line: name (optional), X, Y, elevation; commas, "
             "semicolons, tabs or spaces. Choose the column order (some "
             "files give North first), which elevation is your ±0.00, and "
             "where they go (far points, e.g. UTM, are moved onto the "
             "plot)."),
        ],
        "tips": [
            "Points outside the plot are kept but don't count (greyed).",
            "Fold lines of the plot are kept by the triangles.",
        ],
        "mistakes": [
            "Importing with X and Y swapped: check the column order in the "
            "import window.",
        ],
        "keys": [("Enter", "set the typed elevation"),
                 ("Ctrl+Z", "undo")],
    },
    "setbacks": {
        "image": "setbacks.jpg",
        "what": "How far from the plot's edges you may build — the city's "
                "rule. The <b>buildable area</b> shows dashed on the model.",
        "steps": [
            ("Mark front sides", "Click the side that faces the street (a "
             "corner plot: both). The side facing away becomes the "
             "<b>back</b>, the others the <b>sides</b>. Their distances are "
             "<b>Front</b>, <b>Back</b> and <b>Sides</b> in the left strip."),
        ],
        "tips": [
            "A side with a rule of its own: point at it with the tool, type "
            "the distance + Enter. <b>Delete</b> gives it back its role's "
            "distance.",
            "An excavation drawn past the buildable area gets a warning.",
        ],
        "keys": [("Enter", "set the typed distance on the side pointed"),
                 ("Delete", "back to the side's role distance")],
    },
    "excavation": {
        "image": "excavation.jpg",
        "what": "A pit opened in the ground — for a basement, a foundation, "
                "a ramp. Choose its <b>bottom</b> in the options bar "
                "<b>before</b> drawing, then draw it inside the plot.",
        "steps": [
            ("Rectangle", "Two opposite corners — aligned to the axes (or "
             "to the plot's sides with <b>Align</b> in the options bar)."),
            ("Rectangle from centre", "The centre, then a corner."),
            ("Rotated rectangle", "First side (two clicks), then the depth."),
            ("Point by point", "Each corner in order; close on the first."),
            ("Circle", "The centre, then the radius."),
            ("Ramp", "Click where the ramp starts, then which way it goes "
             "down: its length comes from the <b>slope (%)</b>."),
        ],
        "tips": [
            "<b>Bottom</b>: a <b>depth</b> under the ground, <b>under a "
            "level</b>'s floor (it follows the level), <b>at an "
            "elevation</b>, or <b>per corner</b> — each corner its own "
            "bottom: a sloped pit or a ramp.",
            "For basements, <b>add the basement levels first</b> (Project › "
            "Levels › Add basement): «Under ‹level›» lists only the levels "
            "that exist. Then pick «Under Basement 2» — the field <b>below "
            "its floor</b> appears (slab + base under the floor, usually "
            "0.30) — and the pit follows if a basement's height changes.",
            "On a <b>sloped plot</b> prefer «Under ‹level›»: «Depth below "
            "ground» measures from the lowest ground around the pit, not "
            "from the building's ±0.00.",
            "The <b>slabs</b> of the basements it holds (and of the ground "
            "floor over them) appear by themselves and follow the pit's "
            "outline — delete one you do not want.",
            "<b>Wall</b> of each side: 90° = vertical (a retaining wall); "
            "less = a <b>slope</b> opening outward (45° is a usual batter).",
            "Overlapping excavations <b>merge</b>, each part dug to the "
            "deepest.",
            "Double-click an excavation (or its row in the outliner) to "
            "open its window: corners, depths, walls.",
            "<b>Exactly placed</b>: the <b>Guides</b> icon on the top bar "
            "(two crossed dashed lines) ▸ <b>Guide line</b> (or <b>T</b>): "
            "click a side of the plot, move inward and type the distance + "
            "Enter. Two guides (a front and a side) cross where the "
            "excavation's corner goes: its corners snap to the guides and "
            "to their crossing. The same menu deletes <b>a guide</b> (click "
            "it) or <b>all</b> of them.",
        ],
        "mistakes": [
            "A corner's bottom <b>above</b> the ground: it is held at the "
            "ground, with a warning (it is a fill's job to raise ground).",
            "Drawing it outside the plot: it is kept but not dug.",
            "The right size in the wrong place: set guides from the plot's "
            "sides first (Tape Measure, <b>T</b>) and start on their "
            "crossing.",
        ],
        "keys": [("T", "a guide line at a typed distance (Guides ▸ Guide "
                       "line)"),
                 ("Ctrl+Z", "undo every change")],
    },
    "fill": {
        "what": "Earth brought in: the ground raised to a <b>platform</b> — "
                "to level a sloping plot, lift a terrace, build an "
                "embankment. Choose its <b>top</b> in the options bar first.",
        "steps": [
            ("Rectangle", "Two opposite corners."),
            ("Rectangle from centre", "The centre, then a corner."),
            ("Rotated rectangle", "First side, then the depth."),
            ("Point by point", "Each corner in order."),
            ("Circle", "The centre, then the radius."),
        ],
        "tips": [
            "<b>Top</b>: a height over the ground, under a level's floor, "
            "at an elevation, or per corner (a sloped platform).",
            "<b>Edge</b>: 90° = a retaining wall; less = a slope down to "
            "the ground.",
            "Where the ground is already higher than the top, nothing is "
            "added. A fill and an excavation can overlap: the excavation "
            "wins.",
        ],
        "keys": [("Ctrl+Z", "undo")],
    },
    "excavation_edit": {
        "image": "excavation_edit.jpg",
        "what": "Change an excavation or a fill after it is drawn: its "
                "corners, or remove it.",
        "steps": [
            ("Move points", "Drag a corner of an excavation or a fill."),
            ("Add point", "Click on a side to add a corner."),
            ("Delete point", "Click a corner to remove it."),
            ("Delete excavation", "Click an excavation or a fill to remove "
             "it (it turns red under the cursor)."),
        ],
        "tips": [
            "Depths and wall angles are in the excavation's window — "
            "double-click it.",
        ],
        "keys": [("Ctrl+Z", "undo")],
    },
    "ground": {
        "what": "The block of earth under the plot. Its <b>thickness</b> is "
                "how deep it goes below the surface; basements and "
                "excavations cut into it.",
        "tips": ["Make it deeper than your deepest excavation."],
    },
}


GUIDES.update({
    # ---- Project ---------------------------------------------------------
    "project_settings": {
        "what": "The data every drawing and sheet reads: the project's "
                "name, client, address, author, the <b>structural "
                "system</b>, the <b>north</b>, the ground floor level and "
                "the sheets' defaults. Nothing in the model is drawn here.",
        "steps": [
            ("Edit project…", "Opens the project window. Fill in what you "
             "know now; everything can be changed later."),
        ],
        "tips": [
            "<b>Structural system</b>: <b>Frame</b> (columns and beams "
            "carry the building — Structure comes before Walls) or "
            "<b>Load-bearing walls</b> (Walls come first). The phases are a "
            "guide, never a lock.",
            "<b>North</b> turns the north arrow on the sheets and the sun — "
            "never the model.",
            "The title block of every sheet is filled from here.",
        ],
    },
    "levels": {
        "image": "levels.jpg",
        "what": "The storeys of the building, from the lowest basement to "
                "the top floor. Each one has a <b>height</b> (floor to "
                "floor); the <b>elevations</b> are worked out for you from "
                "the ground floor.",
        "steps": [
            ("Add floor above", "A new level on top, with the height of the "
             "one under it."),
            ("Add basement", "A new level under the lowest one."),
            ("Edit levels…", "The table of levels: names and heights."),
        ],
        "tips": [
            "The level you work on is picked in the <b>levels strip</b> "
            "(key <b>N</b> shows / hides it), or by selecting something on "
            "the model.",
            "Default names (Level 2, Basement 1…) renumber themselves.",
            "A level can be deleted only when empty, never the ground "
            "floor; Ctrl+Z brings it back.",
        ],
        "keys": [("N", "show / hide the levels strip"),
                 ("Ctrl+Z", "undo")],
    },
    # ---- Structure -------------------------------------------------------
    "column": {
        "image": "column.jpg",
        "what": "A column stands on its level's floor and goes up to the "
                "<b>underside of the slab above</b> (it follows the slab), "
                "or to a height of its own. Rectangular or round; drawn one "
                "by one, in a row, in a grid — or at every wall corner in "
                "one click. All its choices are in the <b>options bar</b>.",
        "steps": [
            ("Stamp", "The column rides the cursor; each click places one. "
             "<b>Esc</b> when done."),
            ("Draw", "Two opposite corners: its size and its place (the "
             "size is kept for the next)."),
            ("Row", "Click the first and the last: <b>By count</b> or <b>By "
             "spacing</b>; <b>Ends</b> says if the clicked points get a "
             "column (First + last, First only, Last only, Between only). "
             "The last row follows the bar until you draw the next."),
            ("Grid", "Two opposite corners, «Columns» × «Rows»."),
            ("At the wall corners", "One click: a column wherever this "
             "level's walls meet."),
        ],
        "tips": [
            "<b>Insertion point</b> (◉ Centre, ↙ Lower left…): which point "
            "of the column sits on the cursor — a corner or a side's middle "
            "lays it flush with a face.",
            "Near a wall, a plot side or another column, the column is "
            "<b>pulled to the faces</b> (orange dashed guides).",
            "<b>In walls · Fit inside</b>: on a wall it takes the wall's "
            "thickness and hides in it (the usual case). <b>As drawn</b>: "
            "its own sizes, to show.",
            "<b>Base</b>: 0 = on the floor; negative = down into the ground "
            "(to a footing).",
        ],
        "mistakes": [
            "A column «that did not appear» on a wall: it was fitted and is "
            "hidden inside the wall — in plan it shows filled grey.",
        ],
        "keys": [("Esc", "stop stamping"), ("Ctrl+Z", "undo")],
    },
    "beam": {
        "image": "beam.jpg",
        "what": "A beam hangs under the <b>slab above</b>: its top at the "
                "slab's underside, its <b>height</b> going down. Beams join "
                "one another like walls (corners, T, crossings).",
        "steps": [
            ("Point by point", "Click from support to support, beam after "
             "beam."),
            ("Along the walls", "One click: a beam over every straight wall "
             "of this level."),
        ],
        "tips": [
            "<b>In walls · Fit inside</b>: a beam along a wall takes its "
            "thickness and hides in it; a wider one shows.",
            "Width and Height are in the options bar.",
        ],
        "keys": [("Esc", "stop drawing"), ("Ctrl+Z", "undo")],
    },
    "slab": {
        "image": "slab.jpg",
        "what": "A slab's <b>top</b> is its level's floor (or the offset "
                "you give it); its <b>thickness</b> goes down. The walls, "
                "columns and beams of the level below stop at its underside.",
        "steps": [
            ("Inside the walls", "One click: the slab under this level's "
             "walls, to their outer faces."),
            ("Rectangle", "Corner to corner (also from the centre, or "
             "rotated)."),
            ("Point by point", "Any outline."),
            ("Opening in a slab", "Draw a rectangle inside a slab: a hole "
             "for a stair, a lift, a void."),
        ],
        "tips": ["<b>Top</b>: 0 = the floor itself; a small negative value "
                 "sinks it (a bathroom, a terrace).",
                 "<b>Automatic slabs</b>: an excavation makes the slabs of "
                 "the basements it holds and of the ground floor over them, "
                 "following its outline (its window says «Automatic»). "
                 "Delete one you do not want: it stays away — Ctrl+Z brings "
                 "it back. A slab you draw over it on that level takes its "
                 "place.",
                 "Ramps and stairs open their way through the slabs by "
                 "themselves."],
        "keys": [("Ctrl+Z", "undo")],
    },
    "footing": {
        "image": "footing.jpg",
        "what": "Footings hang under their level's slab: a <b>pad</b> under "
                "each column, a <b>strip</b> under each wall. <b>Depth</b> "
                "goes down from the slab's underside.",
        "steps": [
            ("Under the columns", "One click: a pad under every column of "
             "this level (never narrower than the column + 0.20)."),
            ("Under the walls", "One click: a strip footing under every "
             "wall of this level."),
        ],
        "tips": ["Make them on the lowest level (usually the basement)."],
        "keys": [("Ctrl+Z", "undo")],
    },
    # ---- Walls -----------------------------------------------------------
    "wall": {
        "image": "wall.jpg",
        "what": "A wall is the <b>line you draw</b>, a <b>thickness</b> and "
                "a <b>height</b>. Its joins with the walls it meets are made "
                "for you (corners, T, crossings) and made again whenever "
                "one changes. Everything is in the <b>options bar</b>.",
        "steps": [
            ("Point by point", "Click point after point; type a length + "
             "Enter to lay the next point that far. <b>C</b> (or a click on "
             "the first point) closes the room; <b>Enter</b> or a "
             "double-click ends it open."),
            ("Rectangle", "Four walls, corner to corner (also from the "
             "centre, or rotated)."),
            ("Curved wall", "Start, end and a point on the curve — or from "
             "its centre."),
            ("Round wall", "A whole circle."),
        ],
        "tips": [
            "<b>Alignment</b> — Outside, Centre, Inside: which face sits on "
            "the line you draw; a new thickness never moves that face. A "
            "rectangle or a circle knows its inside; an open run takes the "
            "side the cursor is on.",
            "<b>Height</b>: the level's (it follows the level) or "
            "<b>Custom</b> (a low wall, a parapet).",
            "A partition is simply a thinner wall.",
            "To move a wall's end afterwards: <b>Edit walls › Move points</b>"
            ", or <b>Start / End</b> in its window (double-click it).",
        ],
        "mistakes": [
            "Walls on the wrong side of the line: press <b>Tab</b> while "
            "drawing, or change <b>Alignment</b>.",
        ],
        "keys": [("number + Enter", "the next point that far"),
                 ("C", "close the run (a room)"),
                 ("Enter", "end the run open"),
                 ("Tab", "the walls to the other side of the line"),
                 ("Backspace", "take the last point back"),
                 ("Esc", "drop what is drawn (again: the tool ends)"),
                 ("Ctrl+Z", "undo")],
    },
    "wall_edit": {
        "what": "Change where a straight wall starts or ends, with the "
                "mouse. The walls that end at the same corner <b>follow</b>, "
                "so a corner stays a corner — the joins are made again by "
                "themselves.",
        "steps": [
            ("Move points", "The walls' ends show as dots. Click one: it "
             "follows the cursor (it snaps to edges, guides and their "
             "crossings). Click where it goes — or type a distance + Enter. "
             "<b>X</b> / <b>Y</b> keep it on an axis."),
        ],
        "tips": [
            "Exact numbers instead: double-click the wall — its window has "
            "<b>Start</b> and <b>End</b> (X, Y) and <b>Length</b>, kept in "
            "step; <b>Apply</b> shows it without closing.",
            "Curved and round walls: change them in their window.",
            "Doors and windows keep their distance from the wall's start.",
        ],
        "keys": [("X / Y", "keep the move on the red / green axis"),
                 ("number + Enter", "move it that far, toward the cursor"),
                 ("Esc", "put it back (again: the tool ends)"),
                 ("Ctrl+Z", "undo the move")],
    },
    "wall_import": {
        "what": "Raise the walls of an existing plan. <b>Load</b> a DXF "
                "onto the current level — drawn over the view as a "
                "reference — then <b>Make walls</b> from its lines.",
        "steps": [
            ("Load", "Pick the DXF file: it appears over the current level "
             "(the model is not changed — you can also trace by hand)."),
            ("Make walls", "Every pair of <b>parallel lines</b> between "
             "<b>Min</b> and <b>Max</b> apart is a wall; a gap in its lines "
             "is an opening (up to 1.00 m a door, wider a window)."),
            ("Clear", "Removes the drawing from this level."),
        ],
        "tips": [
            "Pick the drawing's <b>Layer</b> of the walls when it has one.",
            "Curved walls are not found yet — draw them by hand. DWG: save "
            "it as DXF first.",
        ],
    },
    # ---- Openings --------------------------------------------------------
    "door": {
        "image": "door.jpg",
        "what": "A door sits in a straight wall: move along the wall and "
                "click. The wall is cut for it and a frame and a leaf go in; "
                "in plan it shows its leaf open and its swing.",
        "steps": [("On a wall", "Move along a wall, click where it goes. "
                   "<b>Tab</b> puts the hinge on the other side.")],
        "tips": ["Width and Height in the options bar; <b>Hinge</b>: the "
                 "jamb it hangs on. It opens to the wall's inside."],
        "keys": [("Tab", "hinge on the other side"), ("Ctrl+Z", "undo")],
    },
    "window": {
        "image": "window.jpg",
        "what": "A window sits in a straight wall, its <b>sill</b> measured "
                "from the level's floor: the wall is cut for it (sill and "
                "lintel) and a frame with glass goes in.",
        "steps": [("On a wall", "Move along a wall, click where it goes.")],
        "tips": ["Width, Height and Sill in the options bar."],
        "keys": [("Ctrl+Z", "undo")],
    },
    "void": {
        "image": "void.jpg",
        "what": "An opening with nothing in it — a passage, an arch without "
                "a door: the wall is simply cut, from its sill to its head.",
        "steps": [("On a wall", "Move along a wall, click where it goes.")],
        "keys": [("Ctrl+Z", "undo")],
    },
    # ---- Roof ------------------------------------------------------------
    "roof": {
        "image": "roof.jpg",
        "what": "A roof rests on the <b>top of its level's walls</b> — put "
                "it on the top floor. <b>Gable</b>: two slopes and a "
                "triangle of wall at each end; <b>Hip</b>: four slopes; "
                "<b>Flat</b>: a slab with a parapet if you like.",
        "steps": [
            ("Over the walls", "One click: a roof over this level's walls "
             "(a pitched one over the rectangle round them)."),
            ("Rectangle", "Corner to corner (also from the centre, or "
             "rotated)."),
            ("Point by point", "Any outline (a pitched roof takes the "
             "rectangle round it)."),
        ],
        "tips": [
            "<b>Slope</b> in degrees; <b>Overhang</b>: how far the eaves "
            "reach past the walls.",
            "<b>Ridge</b> (gable): along the long side or the short side.",
            "<b>Parapet</b> (flat): its height over the roof; 0 = none.",
        ],
        "keys": [("Ctrl+Z", "undo")],
    },
    # ---- Documentation ---------------------------------------------------
    "rooms": {
        "what": "Rooms are <b>found from the walls</b> by themselves: every "
                "space the walls close is a room (doors don't open it). "
                "Nothing to draw — move a wall and the rooms follow.",
        "steps": [("Names", "A table of the current level's rooms: give "
                   "each a <b>name</b>; its net <b>area</b> and perimeter "
                   "are read. Ticked, the names go to the same rooms on the "
                   "other levels (typical floors).")],
        "tips": [
            "<b>Labels · In plan</b>: name and area on the plan view.",
            "<b>On sheets</b>: names on the plans and a sheet with the "
            "<b>area schedule</b> (net and gross per level).",
        ],
    },
    "sheets": {
        "what": "One click makes the building's drawings on IngeTrazo's own "
                "<b>sheets</b>: a <b>plan</b> of every level, the four "
                "<b>elevations</b> and the <b>sections</b> A-A and B-B — "
                "each on a sheet with its frame at scale, the title block "
                "filled from the project, a scale bar and the north.",
        "steps": [
            ("Make", "Makes (or makes again) the drawings and their sheets. "
             "Made again, it replaces only the sheets ArchXQ made; your own "
             "sheets stay."),
            ("Open", "Opens IngeTrazo's sheet composer — add dimensions, "
             "level marks, labels, notes."),
        ],
        "tips": [
            "<b>Paper</b> A1–A4 (landscape); <b>Scale</b> Auto = the largest "
            "that holds the building.",
            "<b>Cut</b>: where the plans are cut, from each level's floor.",
            "<b>Dimensions · Outside</b>: a chain through the openings and "
            "the overall size, on each side of the plans.",
        ],
    },
    "section": {
        "image": "section.jpg",
        "what": "Draw a section where you want it: two clicks in plan. "
                "Its sheet (C-C, D-D…) is made at once and its mark appears "
                "on the plans.",
        "steps": [
            ("Section line", "Two clicks in plan. You look across the line "
             "to its <b>left</b>; <b>Tab</b> turns the look round — the "
             "arrows at its ends show it."),
            ("Remove", "Removes the sections you drew (and their sheets). "
             "A-A and B-B are always made."),
        ],
        "keys": [("Tab", "look the other way")],
    },
    "export": {
        "what": "Take the documents out of IngeTrazo.",
        "steps": [
            ("PDF", "Every sheet in ONE PDF, each page at its own paper."),
            ("DXF", "Each drawing ArchXQ made in its own file, true size in "
             "metres; layers by line (A-CUT, A-PROFILE, A-EDGE, A-HIDDEN) "
             "plus room names, dimensions and levels. About 2 s per "
             "drawing."),
        ],
    },
})


# ---- Building elements (a section of their own, under the methods) ----------
GUIDES["ramp"] = {
    "what": "A <b>ramp</b> is a sloped concrete slab from a level — or from "
            "the ground — down (or up) to another level or an elevation. Its "
            "<b>length follows from the drop and the slope</b>: you never "
            "work it out.",
    "steps": [
        ("Its window", "Click <b>Ramp</b> under «Building elements». Choose "
         "its <b>Top level</b> (a level, or <b>the terrain</b>: the ground's "
         "height at its top) over its <b>Bottom level</b> (a level or an "
         "elevation), and <b>Starts at</b> — where your click is: its bottom "
         "(going up) or its top (going down — a ramp from the street). Then "
         "the <b>width</b>, the <b>slope</b> and the <b>thickness</b>. The "
         "side view shows it live. For a special case, type the "
         "<b>Length</b> instead: the slope then follows from it."),
        ("Its shape", "<b>Straight</b>; <b>L</b>: two runs and a level "
         "landing, the second run turned 90°; <b>U</b>: the second run comes "
         "back beside the first, the landing across both. <b>Turn</b>: the "
         "side it turns to; <b>Landing</b>: its length. The length (or "
         "slope) is the two runs together — the landing apart; the drop is "
         "split evenly between them."),
        ("Where it starts", "OK opens the plan. Click its <b>first edge</b> "
         "(bottom or top, as «Starts at» says)."),
        ("The way it goes", "Move the mouse: the ramp turns with it, at its "
         "length. Click to build it. The tool stays out for the next one; "
         "<b>Esc</b> ends."),
        ("Change it", "A <b>double-click</b> on a ramp opens its window: "
         "top / bottom, sizes, where it starts and its direction, Hide, "
         "Delete."),
        ("Insert at / stacked", "<b>Insert at</b>: the click on its first "
         "edge's left corner, middle or right corner. <b>Repeat above ▲ / "
         "below ▼</b> (its window): the same ramp, in the same place, one "
         "level up / down — a garage's ramps stacked."),
    ],
    "typing": [
        ("Its direction", "after the first click, type the angle in degrees "
                          "+ Enter (<code>0</code> = along the red axis, "
                          "<code>90</code> = along the green)"),
    ],
    "tips": [
        "Slopes: about <b>20 %</b> for cars (with gentler ends in real "
        "projects), <b>8 %</b> for people (accessibility).",
        "Add the levels first (Project › Levels): the ramp runs between "
        "them.",
        "Into an excavation from the street: <b>Top</b> = the terrain (or "
        "Level 1), <b>Bottom</b> = the basement, <b>Starts at</b> = its top.",
        "A ramp or stair belongs to its <b>bottom level</b> — the storey "
        "whose space it takes (the outliner lists it there).",
        "The <b>slab</b> it goes through (the floor it leaves, and any in "
        "between) gets its <b>hole by itself</b>, 1 cm round the ramp. Move "
        "the ramp and the hole follows; delete it and the slab closes.",
    ],
    "keys": [("Tab", "an L / U turns the other way (while placing it)"),
             ("Backspace", "start again (after the first click)"),
             ("Esc", "drop it / end the tool"), ("Ctrl+Z", "undo")],
}


GUIDES["stair"] = {
    "what": "A <b>stair</b> from a level — or from the ground — to another "
            "level or an elevation. Its <b>steps are worked out</b>: the "
            "count of risers from the highest riser you allow, the tread "
            "from <b>Blondel's rule</b> (2 risers + 1 tread = 63 cm).",
    "steps": [
        ("Its window", "Click <b>Stair</b> under «Building elements». "
         "Choose its <b>Top level</b> over its <b>Bottom level</b>, "
         "<b>Starts at</b> (the bottom step — usual — or the top), the "
         "<b>width</b> and the <b>riser "
         "(max)</b> — 18 cm is usual. The line under it says what you get: "
         "«17 risers × 17.6 cm · tread 27.7 cm · 2h+p = 63.0 cm · run "
         "4.43 m». The side view draws the steps."),
        ("The tread", "<b>Blondel</b> on: worked out (kept between 25 and "
         "32 cm). Type a tread and it stays (Blondel off)."),
        ("Its shape", "<b>Straight</b>; <b>L</b>: two flights and a landing, "
         "turned 90°; <b>U</b>: the second flight back beside the first. "
         "The risers are split between the two flights."),
        ("Where it starts", "OK opens the plan: click its first step's edge "
         "(bottom or top, as «Starts at» says), then the way it goes — the "
         "treads are drawn as you turn it."),
        ("Insert at", "Where your click sits on its first step's edge, "
         "walking it: the <b>left corner</b>, the <b>middle</b> or the "
         "<b>right corner</b> — a corner puts it straight into a stair "
         "shaft's corner."),
        ("Change it", "A <b>double-click</b> on a stair opens its window "
         "again."),
        ("Stacked flights", "In a stair's window, <b>Repeat above ▲</b> / "
         "<b>Repeat below ▼</b> make the same stair, in the same place, one "
         "level up / down — a fire stair is one click per floor."),
    ],
    "typing": [
        ("Its direction", "after the first click, type the angle in degrees "
                          "+ Enter"),
    ],
    "tips": [
        "Going down from a floor: its first step starts at the edge of the "
        "hole in the slab — the slab gets that hole by itself.",
        "A comfortable stair: risers 16–18 cm, treads 27–30 cm.",
        "No level over the highest one yet? <b>To</b> = «Top of ‹level›» "
        "(its floor + its height): the stair goes up inside it.",
    ],
    "keys": [("Tab", "an L / U turns the other way (while placing it)"),
             ("Backspace", "start again (after the first click)"),
             ("Esc", "drop it / end the tool"), ("Ctrl+Z", "undo")],
}


# ---- typed sizes (his ask, 2026-10-05: «used a lot, and easy to forget») ----
# checked against the tools' on_value and the host's _parse_value_buffer
_T_RECT = ("Rectangle", "click the first corner, move toward where it "
           "grows, type <code>40;30</code> + Enter — along the red axis ; "
           "along the green")
_T_CENTRE = ("Rectangle from centre", "click the centre, type "
             "<code>40;30</code> + Enter — the whole width ; depth")
_T_ROT = ("Rotated rectangle", "click the first corner, aim, type the first "
          "side + Enter; then type the other side + Enter")
_T_POINTS = ("Point by point", "after each corner, aim and type the next "
             "side's length + Enter")
_T_CIRCLE = ("Circle", "click the centre, type the radius + Enter")
_T_MOVE = ("Move points", "click the corner, aim, type how far + Enter "
           "(X / Y keep it on an axis)")
_T_GUIDE = ("Guide line (T)", "click an edge, move off it, type the "
            "distance + Enter")
GUIDES["plot"]["typing"] = [_T_RECT, _T_CENTRE, _T_ROT, _T_POINTS]
GUIDES["plot_edit"]["typing"] = [_T_MOVE]
GUIDES["excavation"]["typing"] = [
    _T_RECT, _T_CENTRE, _T_ROT, _T_POINTS, _T_CIRCLE,
    ("Ramp", "click where it starts, aim downhill, type its length + Enter "
             "(or let the slope give it)"), _T_GUIDE,
    ("Its depth", "not typed while drawing: <b>Bottom</b> in the options "
                  "bar, before you start")]
GUIDES["fill"]["typing"] = [_T_RECT, _T_CENTRE, _T_ROT, _T_POINTS, _T_CIRCLE,
                            ("Its top", "<b>Top</b> in the options bar, "
                                        "before you start")]
GUIDES["excavation_edit"]["typing"] = [_T_MOVE]
GUIDES["wall"]["typing"] = [
    ("Point by point", "after each point, aim and type the wall's length + "
                       "Enter; <b>C</b> closes the room"),
    _T_RECT, _T_CENTRE, _T_ROT,
    ("Curved, 3 points", "click the start, aim, type the length start → end "
                         "+ Enter, then click the bulge"),
    ("Curved from centre", "centre, start, then type the angle in degrees + "
                           "Enter (<code>90</code>)"),
    ("Circle", "click the centre, type the radius + Enter"),
    ("Thickness, height", "in the options bar, before you start")]
GUIDES["wall_edit"]["typing"] = [_T_MOVE]
GUIDES["column"]["typing"] = [
    ("Draw", "click a corner, type <code>0,30;0,50</code> + Enter — its "
             "width ; depth"),
    ("Row", "click the first one, aim, type the row's length + Enter — the "
            "count in the options bar"),
    ("Grid", "click the first one, type <code>20;15</code> + Enter — the "
             "grid's width ; depth"),
    ("Single", "its size in the options bar, then a click")]
GUIDES["beam"]["typing"] = [
    ("Point by point", "after each point, aim and type the beam's length + "
                       "Enter")]
GUIDES["slab"]["typing"] = [_T_RECT, _T_CENTRE, _T_ROT, _T_POINTS]
GUIDES["roof"]["typing"] = [_T_RECT, _T_CENTRE, _T_ROT, _T_POINTS]


# ---- the window -------------------------------------------------------------
_CSS = (
    "QDialog { background: #1d2025; }"
    "QListWidget { background: #23262b; color: #d6d9dd; border: none; "
    "font-size: 13px; padding: 6px 0; outline: 0; }"
    "QListWidget::item { padding: 7px 14px; }"
    f"QListWidget::item:selected {{ background: {BLUE}; color: white; }}"
    "QTextBrowser { background: #1d2025; color: #e8eaed; border: none; "
    "font-size: 14px; padding: 8px 18px; }")

_PAGE_CSS = (
    "h1 { color: white; font-size: 22px; margin: 4px 0 2px 0; }"
    ".phase { color: #9aa5b1; font-size: 12px; letter-spacing: 2px; }"
    "h2 { color: #e8742c; font-size: 15px; margin: 18px 0 6px 0; }"
    "p, li { line-height: 140%; }"
    "td { padding: 4px 10px 4px 0; vertical-align: top; }"
    "td.k { color: white; font-weight: bold; white-space: nowrap; }"
    "code { color: #8fd3ff; }"
    "a { color: #8fd3ff; }")


#: the «Building elements» — a section of their own, apart from the phases
BUILDING = {"ramp": "Ramp", "stair": "Stair"}


def _elements_of(element: str) -> tuple[str, list[str]]:
    """The phase holding ``element`` and its elements (in phase order)."""
    if element in BUILDING:
        return "Building elements", list(BUILDING)
    for ph in PHASES.values():
        if element in ph.elements:
            return ph.label, list(ph.elements)
    return "", [element]


def _label(key: str) -> str:
    el = ELEMENTS.get(key)
    return el.label if el else BUILDING.get(key, key)


def page_html(key: str) -> str:
    el = ELEMENTS.get(key)
    label = _label(key)
    phase, _ = _elements_of(key)
    g = GUIDES.get(key)
    if g is None:                       # no guide yet: the short help + ways
        title, body = HELP.get(key, (label, ""))
        g = {"what": body or "No guide written yet."}
        if el and el.methods:
            g["steps"] = [(m.label, "") for m in el.methods]
    out = [f"<style>{_PAGE_CSS}</style>",
           f"<div class='phase'>{phase.upper()}</div><h1>{label}</h1>"]
    if is_pro(key) and edition.lite():       # the page reads; the tool waits
        out.append(f"<p style='background:#3b2a6b; color:white; padding:8px'>"
                   f"<b>This tool is in ArchXQ IT Pro.</b> &nbsp;"
                   f"<a href='{edition.PRO_URL}'>Get Pro</a></p>")
    if g.get("image") and (IMAGES / g["image"]).exists():
        url = QUrl.fromLocalFile(str(IMAGES / g["image"])).toString()
        # both sizes: with the width alone Qt keeps the file's height
        # (1120×560 figures, shown at half size — sharp on hi-dpi)
        # in a div, not a <p>: the paragraphs' 140 % line height stretched
        # the picture's line (a gap under it)
        out.append(f"<div style='margin: 8px 0 4px 0'><img src='{url}' "
                   "width='560' height='280'></div>")
    out.append(f"<p>{g['what']}</p>")
    if g.get("typing"):           # typed sizes: easy to forget — in front
        out.append("<table width='100%' cellpadding='10' style='margin:10px 0;"
                   "background:#2b2418;border-left:4px solid #e8742c'><tr><td>"
                   "<span style='color:#ffb26b;font-weight:bold;font-size:15px'>"
                   "&#9000;&nbsp; Typing the sizes</span><table "
                   "cellpadding='3' style='margin-top:6px'>")
        for what, how in g["typing"]:
            out.append(f"<tr><td class='k'>{html.escape(what)}</td>"
                       f"<td>{how}</td></tr>")
        out.append("</table><p style='color:#c9b79a;margin:6px 0 0 0'>"
                   "Type without clicking — the numbers show in IngeTrazo's "
                   "measurements box (bottom right), Enter applies. Two "
                   "numbers: always separate them with <b>;</b> — then a "
                   "decimal comma is never taken for a separator. Decimals "
                   "with a comma or a point (<code>40,5;30</code>). Units "
                   "work too: "
                   "<code>350cm</code>, <code>4000mm</code>.</p></td></tr>"
                   "</table>")
    if g.get("steps"):
        out.append("<h2>Step by step</h2><table>")
        for name, how in g["steps"]:
            out.append(f"<tr><td class='k'>{html.escape(name)}</td>"
                       f"<td>{how}</td></tr>")
        out.append("</table>")
    for field, head in (("tips", "Tips"), ("mistakes", "Common mistakes")):
        if g.get(field):
            out.append(f"<h2>{head}</h2><ul>")
            out += [f"<li>{t}</li>" for t in g[field]]
            out.append("</ul>")
    if g.get("keys"):
        out.append("<h2>Keys</h2><table>")
        out += [f"<tr><td class='k'>{k}</td><td>{d}</td></tr>"
                for k, d in g["keys"]]
        out.append("</table>")
    video = g.get("video") or (TERRAIN_VIDEO if phase == "Terrain" else "")
    if video:
        out.append(f"<h2>Video</h2><p><a href='{video}'>Watch it on "
                   "YouTube</a></p>")
    return "".join(out)


class GuideWindow(QDialog):
    def __init__(self, element: str, parent=None) -> None:
        super().__init__(parent)
        phase, keys = _elements_of(element)
        self.setWindowTitle(f"ArchXQ — Help · {phase or 'Tools'}")
        self.setStyleSheet(_CSS)
        self.resize(QSize(940, 660))
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.list = QListWidget()
        self.list.setFixedWidth(210)
        self.text = QTextBrowser()
        self.text.setOpenExternalLinks(True)
        lay.addWidget(self.list)
        right = QVBoxLayout()
        right.addWidget(self.text)
        lay.addLayout(right, 1)
        for k in keys:
            it = QListWidgetItem(_label(k))
            it.setData(Qt.UserRole, k)
            self.list.addItem(it)
        self.list.currentItemChanged.connect(
            lambda it, _old: it and self.text.setHtml(
                page_html(it.data(Qt.UserRole))))
        self.list.setCurrentRow(keys.index(element) if element in keys else 0)


def open_guide(element: str | None, parent=None) -> None:
    if not element:
        return
    GuideWindow(element, parent).exec()
