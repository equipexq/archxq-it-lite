"""Help popups: a small «?» button next to a title opens a short, plain
explanation. The popup closes on any click outside it or on Esc; it never
blocks the work behind it."""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QFrame, QLabel, QToolButton, QVBoxLayout

from .style import BLUE

HELP: dict[str, tuple[str, str]] = {
    "project": (
        "Project",
        "The data every drawing and sheet of the building reads: its name, "
        "who it is for, where it is, and how it is built.<br><br>"
        "<b>Start a project</b> once; edit it any time with "
        "<b>Edit project…</b>. Nothing in the model is created or "
        "changed by this phase."),
    "levels": (
        "Levels",
        "The storeys of the building, from the lowest basement to the top "
        "floor. Each one has a <b>height</b> (floor to floor); the "
        "<b>elevation</b> of each floor is worked out for you, starting "
        "from the ground floor's level.<br><br>"
        "The floor you work on is picked in <b>Floor</b>, on the top bar."),
    "system": (
        "Structural system",
        "<b>Frame</b>: columns and beams carry the building; walls only "
        "close it. The Structure phase is shown before Walls.<br><br>"
        "<b>Load-bearing walls</b>: the walls ARE the structure. The Walls "
        "phase is shown first.<br><br>The phases are a guide, never a "
        "lock: every one is always open."),
    "column": (
        "Column",
        "A column stands on its level's floor and goes up to the "
        "<b>underside of the slab above</b> (it follows the slab), or to "
        "a height of its own.<br><br>Its <b>section</b> is a rectangle "
        "(width × depth, turned by its angle) or round (Ø). Drawn one by "
        "one, in a row, in a grid — or <b>at the wall corners</b> in one "
        "click."),
    "beam": (
        "Beam",
        "A beam's <b>height includes the slab above</b>: its top is flush "
        "with the slab's top, the rest hangs under it (a 20×60 beam under a "
        "20 cm slab shows 40 cm below it). Beams join one another "
        "like walls (corners, T, crossings).<br><br>A beam over a wall of "
        "the same width hides inside it; a wider one shows."),
    "slab": (
        "Slab",
        "A slab's <b>top</b> is its level's floor (or the offset you give "
        "it); its <b>thickness</b> goes down. The walls and columns of the "
        "level below stop at its underside; the beams go up into it, flush "
        "with its top.<br><br><b>Inside the "
        "walls</b> makes it in one click, to the walls' outer faces."
        "<br><br>An <b>excavation</b> makes its own slabs: on every basement "
        "it holds and on the ground floor over them, following its outline. "
        "Delete one you do not want — it stays away."),
    "footing": (
        "Footing",
        "Footings hang under their level's slab: a <b>pad</b> under each "
        "column (square, never narrower than the column + 0.20), a "
        "<b>strip</b> under each wall or along each <b>row of columns</b>. "
        "<b>Depth</b> = how thick, going down from the slab's underside; in "
        "an excavation deeper than the floor, from its floor."),
    "ramp": (
        "Ramp",
        "A sloped slab between two levels — or the ground and a level. Set "
        "its <b>Top</b> and <b>Bottom</b> level, where your click is "
        "(<b>Starts at</b>: its bottom, or its top — a ramp from the "
        "street), the <b>width</b> and the "
        "<b>slope</b> (20 % for cars, 8 % for people): the length "
        "follows (or type the <b>length</b>: the slope follows). "
        "<b>Straight</b>, <b>L</b> (a 90° turn) or <b>U</b> (back beside "
        "itself), with a level <b>landing</b> between the two runs. Then "
        "click where it starts and the way it "
        "goes; <b>Tab</b> turns an L / U the other way.<br><br>The slab it "
        "goes through gets its hole by itself. A double-click on a ramp "
        "opens this window again."),
    "stair": (
        "Stair",
        "A stair between two levels, defined from the bottom up. Set its "
        "<b>Top</b> and <b>Bottom</b> level, where your click is "
        "(<b>Starts at</b>: the bottom step, usually), the <b>width</b> and "
        "the highest "
        "<b>riser</b>: the count of risers follows, and the <b>tread</b> "
        "comes from Blondel's rule (2 risers + 1 tread = 63 cm) — or type "
        "it. <b>Straight</b>, <b>L</b> or <b>U</b>, with a landing; then "
        "click where it starts and the way it goes (<b>Tab</b> turns an L / "
        "U the other way).<br><br>The slab it goes through gets its hole by "
        "itself."),
    "sheets": (
        "Drawings & sheets",
        "One click makes the building's drawings on IngeTrazo's own "
        "<b>sheets</b> (the <b>+</b> beside <b>Model</b>, down left): a "
        "<b>plan</b> of every level, cut at <b>Cut</b> over its floor; the "
        "four <b>elevations</b>; the <b>sections</b> A-A and B-B through the "
        "building. Each sheet has its frame at scale, the title block "
        "filled from the project, a scale bar and (plans) the north.<br><br>"
        "Go on in the sheet composer: dimensions, level marks, labels, "
        "notes. <b>Made again</b>, ArchXQ replaces only the sheets it made "
        "(what you added on them goes with them); your own sheets stay."),
    "wall_import": (
        "Walls from DXF",
        "Raise the walls of an existing plan. <b>Load</b> a DXF onto the "
        "current level: it is drawn over the view as a reference (the "
        "model doesn't change; you can trace over it by hand too).<br><br>"
        "<b>Make walls</b>: every pair of <b>parallel lines</b> between "
        "<b>Min</b> and <b>Max</b> apart is a wall — its thickness their "
        "distance, its line between them; walls are carried to the walls "
        "they meet and joined. A <b>gap</b> in a wall's lines is an "
        "opening: up to 1.00 m a door, wider a window (change them after). "
        "Pick the drawing's <b>layer</b> of the walls when it has one.<br>"
        "<br>Curved walls are not found yet (draw them by hand). DWG: "
        "later — save it as DXF."),
    "rooms": (
        "Rooms",
        "Rooms are <b>found from the walls</b> by themselves: every space "
        "the walls close is a room (doors don't open it). Nothing to draw "
        "— move a wall and the rooms follow.<br><br>The table gives each "
        "room of the current level a <b>name</b>; its <b>area</b> (net, "
        "inside the walls) and perimeter are read. Ticked, the names go to "
        "the same rooms on the other levels (typical floors).<br><br>In the "
        "plan view each room shows its name and area; on the sheets too, "
        "with an <b>area schedule</b> (net and gross per level)."),
    "section": (
        "Section line",
        "Draw a section where you want it: two clicks in plan. You look "
        "across the line to its <b>left</b> (drawn left to right, you look "
        "up the plan); <b>Tab</b> turns the look round — the arrows at its "
        "ends show it. The section (C-C, D-D…) and its sheet are made at "
        "once, its mark appears on the plans.<br><br>The eraser removes "
        "the sections you drew; A-A and B-B are always made."),
    "export": (
        "Export",
        "<b>PDF</b>: every sheet of the document in ONE PDF, each page at "
        "its own paper — the sheet composer's own export.<br><br><b>DXF</b>"
        ": each drawing ArchXQ made in its own file (named as its sheet), "
        "true size in metres — a plan in the model's x, y; an elevation or "
        "a section with its true heights. Layers by line: A-CUT, A-PROFILE, "
        "A-EDGE, A-HIDDEN (dashed); and A-ANNO-ROOMS (names, areas), "
        "A-ANNO-DIMS (dimensions), A-ANNO-LEVELS. About 2 s per drawing."),
    "roof": (
        "Roof",
        "A roof rests on the <b>top of its level's walls</b> — put it on "
        "the top floor. <b>Over the walls</b> makes it in one click.<br><br>"
        "<b>Gable</b>: two slopes, the ridge along the long side (or the "
        "short), a triangle of wall closing each end. <b>Hip</b>: four "
        "slopes. A pitched roof covers the <b>rectangle</b> round what you "
        "draw. <b>Flat</b>: a slab as drawn, with a <b>parapet</b> round "
        "it (0 = none).<br><br><b>Slope</b> in degrees; <b>overhang</b>: "
        "how far the eaves reach past the walls."),
    "door": (
        "Door",
        "A door sits in a straight wall: move along the wall and click. "
        "The wall is cut through for it (floor to its head) and a frame "
        "and leaf go in.<br><br><b>Hinge</b>: the jamb it hangs on; it "
        "opens to the wall's inside. In the plan it is drawn with its "
        "leaf open and its swing."),
    "window": (
        "Window",
        "A window sits in a straight wall, its <b>sill</b> measured from "
        "the level's floor: the wall is cut for it (with its sill and "
        "lintel), and a frame with glass goes in."),
    "void": (
        "Opening",
        "An opening with nothing in it — a passage, an arch without a "
        "door: the wall is simply cut, from its sill to its head."),
    "wall": (
        "Wall",
        "A wall is the <b>line you drew</b>, a <b>thickness</b> and a "
        "<b>height</b>. Its joins with the walls it meets are made for you "
        "(corners, T, crossings), and made again whenever one changes.<br><br>"
        "<b>Alignment</b> puts its outer face, its centre or its inner face "
        "on the line drawn — so a new thickness never moves that face. "
        "<b>Side</b> says which side of the line is the building's inside.<br>"
        "<br><b>Height</b>: the level's (it follows the level) or its own (a "
        "low wall, a parapet). <b>Length</b> stretches a straight wall from "
        "its end; its start stays."),
    "north": (
        "North",
        "The angle of the project north, clockwise from the top of the "
        "plan (the green axis). It turns the north arrow on the sheets and "
        "the sun; it never turns the model."),
    "ground_level": (
        "Ground floor level",
        "The height of the finished ground floor relative to the plot "
        "datum (0.00). Usually 0.00, or a few steps up (e.g. 0.15)."),
    "documentation": (
        "Sheet defaults",
        "Paper, orientation and scale used when sheets are generated. Each "
        "sheet can still be changed on its own later."),
    "terrain": (
        "Terrain",
        "Draw the plot first: everything sits on it, and the next phases "
        "open once it exists."),
    "settings": (
        "Settings",
        "Your preferences for ArchXQ: what is shown while you work and the "
        "default sizes of new things. They are kept on this computer and "
        "apply to every project; the project's own data lives in its "
        "file."),
    "plot_dims": (
        "Plot dimensions",
        "The length of each side of the plot, written on the model.<br><br>"
        "<b>In the Terrain phase</b>: only while you work on the terrain "
        "(temporary). <b>Always</b>: whenever ArchXQ is on. <b>Off</b>: "
        "never."),
    "ground_thickness": (
        "Ground thickness",
        "How deep the ground block under the plot goes, from the plot "
        "surface down. Used for new plots; a drawn plot changes it in "
        "Terrain › Ground."),
    "ground": (
        "Ground",
        "The block of earth under the plot. Its thickness is how deep it "
        "goes below the surface; basements and excavations will cut into "
        "it."),
    "plot_table": (
        "Plot — sides and heights",
        "Each row is a corner (its number is on the model) and the side "
        "that leaves it. The row you are on lights up on the model in "
        "<b>blue</b>: its corner and its side.<br><br>"
        "<b>Length</b>: type each side's length from the deed, in any "
        "order. Every other side keeps its length; the <b>closing</b> side "
        "(dashed) and the side before it swing to close the plot, so one "
        "pass through the table is enough.<br><br>"
        "<b>Angle</b>: comes from your drawing. Set it only if the deed "
        "gives it; the angles around the closing side are worked out.<br>"
        "<b>Height</b>: the ground at that corner. Different heights slope "
        "the plot's surface; the bottom of the ground stays flat. The "
        "surface is cut the smoothest way; to make it fold on a line of "
        "your own, use <b>Edit plot › Fold line</b>.<br><br>"
        "If the lengths cannot close, the table says by how much. "
        "<b>Apply</b> is one Ctrl+Z. Double-click the plot to open this "
        "table."),
    "setbacks": (
        "Setbacks",
        "How far from the plot's edges you may build — the city's rule. "
        "With <b>Mark front sides</b>, click the side that faces the street "
        "(a corner plot: both). The side facing away becomes the "
        "<b>back</b>, the others the <b>sides</b>; each takes its distance "
        "from here.<br><br>"
        "A side with a rule of its own: point at it with the tool, type the "
        "distance + Enter (Delete gives it back its role's).<br><br>"
        "The <b>buildable area</b> shows dashed on the model, always; the "
        "setback figures follow the Settings' plot dimensions."),
    "excavation": (
        "Excavation",
        "A pit opened in the ground — for a basement, a foundation, a "
        "ramp. Draw it inside the plot (Terrain › Excavation, on the left); "
        "the options bar sets its bottom before you start.<br><br>"
        "<b>Bottom</b>: a <b>depth</b> under the ground (flat, under the "
        "lowest ground around it), <b>under a level</b>'s floor (it "
        "follows the level), <b>at an elevation</b>, or <b>per corner</b> "
        "— each corner its own bottom: a <b>ramp</b>, a sloped pit. A "
        "corner at the ground's own height starts the ramp from the "
        "surface.<br><br>"
        "<b>Wall</b> (each side): 90° = a vertical wall (a retaining "
        "wall); less = a <b>slope</b> opening outward until it meets the "
        "ground (45° is a usual batter).<br>"
        "<b>Ramp</b> (on the left): click where it starts, then which way "
        "it goes down — its length comes from the slope (%).<br>"
        "Excavations that overlap <b>merge</b>: each part dug to the "
        "deepest one.<br><br>"
        "Double-click the excavation (or its row in the outliner) to open "
        "this window; Ctrl+Z undoes every change."),
    "survey": (
        "Survey points",
        "The ground <b>as measured</b>: points inside the plot, each with "
        "its elevation. The ground then passes through every one of them "
        "and through the plot's corners — the surveyor's triangles (a "
        "TIN); fold lines are kept.<br><br>"
        "<b>Import file…</b>: a text file from the surveyor (CSV, TXT): "
        "one point per line — a name or number (optional), X, Y, "
        "elevation; commas, semicolons, tabs or spaces. Pick the order "
        "(some files give North first), the elevation that is your "
        "±0.00 (the lowest metre by default, for absolute elevations), "
        "and where they go: points far from the plot (UTM) are moved onto "
        "it.<br>"
        "<b>Add point</b> (on the left): click on the plot — or type an "
        "elevation + Enter with the cursor where it goes. Over a point, "
        "type a number + Enter to change its elevation.<br>"
        "<b>Delete point</b>: click it.<br><br>"
        "Points outside the plot are kept but don't count (greyed). "
        "Excavations and fills follow the new ground. Ctrl+Z undoes every "
        "change."),
    "fill": (
        "Fill / Platform",
        "Earth brought in: the ground raised to a <b>platform</b> — to "
        "level a sloping plot, lift a terrace, build an embankment. Draw "
        "it inside the plot (Terrain › Fill / Platform, on the left); the "
        "options bar sets its top before you start.<br><br>"
        "<b>Top</b>: a <b>height</b> over the ground (flat, over the "
        "highest ground around it), <b>under a level</b>'s floor, <b>at "
        "an elevation</b>, or <b>per corner</b> — a sloped platform. "
        "Where the ground is already higher than the top, nothing is "
        "added.<br><br>"
        "<b>Edge</b> (each side): 90° = a vertical edge (a retaining "
        "wall); less = a <b>slope</b> going down outward until it meets "
        "the ground (45° usual).<br>"
        "A fill and an excavation can overlap: the excavation wins — a pit "
        "dug through the platform.<br><br>"
        "Double-click the fill (or its row in the outliner) to open this "
        "window; Ctrl+Z undoes every change."),
    "level": (
        "Level",
        "One storey of the building. Its <b>height</b> is floor to floor; "
        "the <b>elevation</b> is worked out from the levels under it.<br><br>"
        "<b>+ Level above / below</b> puts a new level right there — the "
        "default names (Level 2, Basement 1…) renumber themselves.<br>"
        "<b>Delete level</b>: only an empty level, and never the ground "
        "floor. Ctrl+Z brings a deleted level back.<br><br>"
        "<b>Show</b>: this level's slabs, columns &amp; beams, footings, "
        "walls, openings, ramps &amp; stairs — untick one and it hides at "
        "once, on this level only (the other levels keep theirs). It stays "
        "in the file; the level's eye turns dim with an open pupil while "
        "something is hidden.<br><br>"
        "<b>Ghost</b> (the two-floors icon on each level's row in the "
        "levels strip): that level drawn in light blue in the plan of the "
        "one you work on — to line walls and columns up with it. Turn on as "
        "many as you like; only seen, never picked.<br><br>"
        "Open this window with the ✎ on the level's row in the levels "
        "strip (N), or double-click the row."),
    "level_height": (
        "Height",
        "Floor to floor: from this level's finished floor to the next "
        "one's. The levels above move with it."),
    "phase_done": (
        "Phase status",
        "A phase is complete when what it needs exists. <b>Project</b> "
        "completes itself when the project is started. Later phases will "
        "check the model the same way; until then this button stands in "
        "for those checks."),
}


class _Popup(QFrame):
    def __init__(self, title: str, body: str, parent=None) -> None:
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setObjectName("axq_help")
        self.setStyleSheet(
            "QFrame#axq_help { background: #23262b; border: 1px solid "
            f"{BLUE}; border-radius: 6px; }}"
            "QLabel { color: #e8eaed; background: transparent; }"
            "QLabel#t { font-weight: bold; color: white; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 12)
        t = QLabel(title)
        t.setObjectName("t")
        lay.addWidget(t)
        b = QLabel(body)
        b.setWordWrap(True)
        b.setTextFormat(Qt.RichText)
        b.setFixedWidth(300)
        lay.addWidget(b)


def show_help(topic: str, anchor) -> None:
    title, body = HELP.get(topic, (topic, "No help written yet."))
    pop = _Popup(title, body, anchor)
    pop.adjustSize()
    pos = anchor.mapToGlobal(QPoint(0, anchor.height() + 4))
    screen = anchor.screen().availableGeometry()
    x = min(pos.x(), screen.right() - pop.width() - 8)
    pop.move(max(screen.left() + 8, x), pos.y())
    pop.show()


def help_button(topic, parent=None) -> QToolButton:
    """``topic``: a HELP key, or a callable returning one (for a panel
    whose subject changes)."""
    b = QToolButton(parent)
    b.setText("?")
    b.setToolTip("Help")
    b.setFocusPolicy(Qt.NoFocus)
    b.setFixedSize(18, 18)
    b.setStyleSheet(
        "QToolButton { color: #9aa5b1; border: 1px solid #5b6470; "
        "border-radius: 9px; font-weight: bold; font-size: 11px; "
        "background: transparent; padding: 0; }"
        f"QToolButton:hover {{ color: white; border-color: {BLUE}; "
        f"background: {BLUE}; }}")
    b.clicked.connect(
        lambda: show_help(topic() if callable(topic) else topic, b))
    return b
