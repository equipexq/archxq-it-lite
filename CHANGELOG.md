# Changelog — ArchXQ IT Lite

## 0.12.0

**A project starts again, and rows of columns are drawn point by point, like a wall.** Please update: in the last versions the Lite could not start a new project.

- **FIXED: «Start a new project» did nothing,** and so no tool could be used:
  the window failed to open. It opens now, and the tools work from there.
- **The level's window and the project's table no longer ask for slabs:**
  slabs are the Pro's. The «Documentation» tab of the project's window went
  for the same reason.
- **A row of columns goes point by point, like a wall:** each click fixes a
  stretch, and its columns are there at once (by count on each stretch, or by
  spacing, again from each corner). Every corner gets one column, never two.
  Click the **first point** again to close the row; double-click, Enter or Esc
  ends it open; Backspace takes the last point back. Two clicks and Esc make
  the same row as before. Along an excavation it still stands inside it.
- **A row stays a group, «Column row 1»:** double-click one of its columns and
  its window changes **every** column of the row (section, sizes, height, angle,
  and a new **Row** part: count or spacing, ends). One Ctrl+Z.
  The options bar changes the whole row too. The outliner shows
  «Column row 1 (12)» with its columns inside. A column of the row you delete
  stays out of it; one you move on its own leaves the row; move them all and
  the row goes with them. Rows made before stay loose columns, as they were.
- **Columns of a row never side by side:** «By spacing» now cuts each stretch
  into equal bays, none longer than the spacing (it used to leave a short bay
  before the corner). At a corner the row has one column where the two lines
  meet, flush with both sides of an excavation, re-entrant corners too.
- **A row on its line: Inside, Centre or Outside** — in its window. Along an
  excavation a row stands inside it, as before; elsewhere, centred. It is on the
  options bar too while you draw a row, and the next row starts as your last one.
- **A column right over another:** drawing columns, the cursor is pulled onto the
  centres of the columns of the level below and above, and a row onto the points
  of the rows.
- **The Terrain phase works on the Terrain:** going to Terrain, or picking any of
  its tools (the excavation apart, see below), now switches to the Terrain
  row by itself. A plot drawn while
  «Level 1» was the level worked on was hidden by that level's plan, and looked
  as if it had not been drawn. Going on to the building's phases brings back the
  level you were on (the ground floor at first).
- **The Project button's menu: «New project» and «Edit project».** «Levels»
  left this menu (the levels live in the levels strip). «New project» starts
  one in this document when it has none; when it already has a project, it
  opens a new tab with the Start window, so the project you have is never
  touched. «Edit project» is greyed out until there is a project.
- **An excavation belongs to its level:** the Excavation tool works on a
  basement (or the ground floor, without basements), not on the Terrain row.
  On «Basement 2» its bottom starts «Under Basement 2»; from the Terrain it
  goes to the basement you last worked on (else the lowest one).
- **The excavation shows in the basements' plans:** each basement it goes
  through shows its outline in plan view, and it can be edited there.
- **Dimensions on by default:** the plot's and the excavations' figures now
  show in every phase («Settings ▸ Plot dimensions ▸ Always»); choose «In the
  Terrain phase» or «Off» there if they bother you.
- **A basement's plan shows its excavations' dimensions** (sides, depth,
  floor elevation).
- **A pit inside an excavation:** one drawn inside another and no deeper
  (0 m³, nothing to see) now opens a window that explains it and offers to
  make it a pit 1.00 m deeper. «Cancel» makes nothing.

## 0.11.2

**A clear «＋ New level» button, and excavations that start at the right depth.** Also: windows that free the memory once closed.

- **NEW: «＋ New level» in the levels strip** — a clear button in place of
  the small «+». It opens the level's window, where «New level» now comes
  first: **＋ Level on top** (over the highest level) or **＋ Basement**
  (under the lowest one), each as high as its neighbour. The window **stays
  open** after each one, so you can add the next without opening it again.
- **Excavations start at the right depth** — when the project has
  basements, a new excavation's bottom is set under the lowest one by
  default (otherwise 3 m below ground, as before). The bottom you pick
  yourself is kept.
- **«No plot yet» shows by the mouse** — trying to draw an excavation or a
  fill before the plot now says so in a balloon by the cursor (and in the
  status bar), not only in the status bar.
- **Closed windows are freed from memory** — after many edits, the
  windows you had closed are now released as new ones open.

## 0.11.1

**Hiding works again on IngeTrazo 0.5.10 and newer (0.5.11, 0.6.0):**
the Walls, Columns, Terrain… buttons at the bottom, the Hide command and
the eyes in the outliner hide and show at once again.

- **The bottom buttons and Hide work at once** — from IngeTrazo 0.5.10,
  the view kept its last picture: a hidden part stayed on screen, came
  back as a white ghost, or could not be clicked any more. Now the view
  is drawn again as soon as a part is hidden or shown, on 0.5.x and 0.6.

## 0.11.0

**An update for IngeTrazo 0.6.0:** ArchXQ IT Lite now works with its
project tabs and respects its lock — please update before you open
projects in tabs. It works with IngeTrazo 0.5.8 and 0.5.9 as before.
Also here: everything since 0.10.3 for what the Lite draws (the plot and
its excavations, levels, walls, columns).

- **Ready for IngeTrazo 0.6.0's project tabs** — ArchXQ works on the
  project in front: its bars, keys and mouse go with the tab, and each
  project keeps its own phase, level and plan view as you switch between
  tabs. Closing a tab is safe. (With 0.10.3, ArchXQ stayed on the first
  tab: in a new tab its bars did not show, and a tool could act on the
  first project.)
- **IngeTrazo 0.6.0's lock is respected** — a locked wall or column (or
  one on a locked layer) is no longer changed by ArchXQ: no arrows to
  pull, its window does not open, and a change that would move or delete
  it is refused. When a neighbour changes, its corner still follows, and
  it stays locked.
- **A new file starts with its Project** — the first tool that makes
  something opens the Project window, already filled in: one OK and the
  tool comes out. The levels and the ground's height are set before
  anything stands on them.
- **Curved walls snap into place** — a curve's end lines up with its
  start and with the walls' ends (the red and green guides); the curve
  sticks where it leaves a wall with no kink, or makes a half circle; from
  its centre, the centre sticks square to a wall's end and the angle to
  90°, 180° and 270°. A curve that runs on from a wall takes that wall's
  thickness and alignment, so its faces run on with no step.
- **NEW: draw walls in 3D too** — a click for the start, a click for the
  end, straight in the 3D view, on the level you work on.
- **NEW: one window edits the whole selection** — select several walls
  (or columns) and change them all at once.
- **NEW: the level's guide sheet** — an icon on each level shows a
  see-through sheet on the level you work on (only an aid: switch it off
  if you prefer).
- **NEW: Split, Trim / Extend and Align walls.**
- **The plan shows only the level you work on**, and walls join clean in
  3D (three joins fixed).
- And many smaller fixes.

## 0.10.3

Everything since 0.10.2, for what the Lite draws (the plot and its
excavations, walls, columns, levels). Tested with IngeTrazo 0.5.8 and
0.5.9 (its experimental Rust engine too).

- **NEW: ArchXQ in Portuguese and German** — **Settings ▸ Language**:
  Auto (as IngeTrazo), English, Português (Brasil) or Deutsch; it takes
  effect when IngeTrazo is restarted. The phases, the bars, the library,
  the windows, the panels, the right-click menu, the status messages and
  the help (the «?» cards, the quick help and every tool's guide). The
  names you gave (levels, rooms) stay as they are.
- **NEW: Units in ArchXQ's Settings** — **Settings ▸ Units ▸ Lengths in**:
  metres, centimetres, millimetres, inches, feet, or feet and inches. It
  is the document's own unit (the same setting as IngeTrazo's
  **Preferences ▸ Units**); with **New documents too**, new documents
  start in it.
- **NEW: pan with Space, without leaving the tool** — drawing a wall or a
  column, hold **Space** and move the mouse: the view pans and the tool
  stays where it was. With IngeTrazo's own tools Space is still «Select».
- **NEW: the ArchXQ panel can float** — drag its tab out of the side tray
  (or double-click its title): on a second monitor, out of the model's
  way. ArchXQ remembers where it was.
- **Feet and inches** — in a document kept in feet / inches, every
  measure shows that way (fields, bars, grips, levels, areas); type
  3'7", 43" or 110 cm. A metres document reads exactly as before.
- **Faster on big projects** — a change swaps only what changed, and the
  undo history no longer keeps a copy of the whole building each time;
  orbiting no longer stutters.
- **Bigger grips**, easier to take; a grip dragged too far stops right at
  the limit and says why.
- **Setback outline off by default** — it shows in **Terrain ›
  Setbacks**; **Setback outline** turns it on for good.
- Fix: in a level's window, **Repeat & copy** — choosing a level and
  pressing **OK** saved only the name and height. Now OK asks.
- Fix: a column fitted inside a wall (**Fit inside**) that was moved off
  it, or whose wall was moved or deleted, disappeared while the walls
  were shown.
- Fix: after **⏻ ArchXQ** off and on, the **Levels** box stayed hidden
  until N was pressed; the quick help card no longer shrinks to its
  title; **Tab / Shift+Tab** reach the tools again.

## 0.10.2

Everything since 0.9.5, for what the Lite draws (the plot and its
excavations, walls, columns, levels):

- **New edit windows** — tabs at the top, folding sections, a small live
  drawing beside the fields, choices as pictures; **Apply** keeps the
  window open. Walls, columns, levels, Settings and the Project.
- **On-screen grips** — select a wall or a column and drag it into shape;
  **magnets** and temporary **guides** line it up with what is around it,
  on every level.
- **Quick help** — a small card in the 3D view lists the keys of the tool
  that is out (F1 hides it); a **radial menu** at the mouse on a click.
- **Walls**: a **curtain wall** type (glass between mullions — their
  sizes, the band at each floor and the glass transparency in its own
  tab, set before drawing with **More…**, several edited at once);
  **Move a wall** with M; walls joined to a turned wall follow it; a run
  of walls keeps its type.
- **Levels**: **Repeat** a level and **Copy to a level** — what the target
  already has is left as it is, only what is missing is copied.
- **Plan view + four elevations** from the view bar; guide lines per level.
- **Size bars** — drag a size or type it in its field.
- IngeTrazo's **light theme** and **0.5.8** (document units, the Extension
  Manager): the panels stay readable, the sizes right.
- **Installed folder = `archxq_it_lite`** (the catalog id), so a hand
  install never lands where the Pro lives. If you installed the Lite by
  hand before, delete the old `archxq_it` folder in the plugins folder.
- ArchXQ's tools are recognised in any install (they were told apart by
  a module name IngeTrazo does not use for extensions) — thanks to the
  catalog maintainer.

## 0.9.5

- **Library** — the strip on the right opens on the library of what you
  draw: **types** in pictures on top, their **parts** below; the sizes stay
  in the bar on the left. Walls (15 cm, 20 cm, partition) and columns
  (rectangular, round); select elements and click another type to change
  them (one Ctrl+Z). The Pro's types (doors, windows, beams, slabs, stairs,
  ramps) show with a PRO badge; greyed items are on the way.
- **The bar edits what is selected**: select walls or columns — the bar
  shows their sizes, and a change goes straight to them (a run of clicks on
  one field = one Ctrl+Z).
- **IngeTrazo's own tools on ArchXQ's columns**: **Move** (M), **Copy**
  (Ctrl + Move, arrays ×3 / 3), **Rotate** (Q) and **Scale** (S) — the
  column's record follows: the same gestures you already know.
- **Material** tab: **Apply** works in place (no closing and reopening).
- **About**: «Version» with a **Copy** button (for support), and a
  **What's new** link.
- The «own bars» placement is gone (one interface, over the 3D view); the
  Extensions ▸ ArchXQ menu opens its items at the first click.

## 0.9.4

- **Materials** — every element's window has a **Material** tab: IngeTrazo's
  colours (RAL), or a solid colour of your own; parts where it makes sense
  (the plot's top / sides, an excavation's floor / walls). «Use for all»
  gives it to every element of the kind. (Textures are in ArchXQ IT Pro.)
- **Show** in each level's window (✎): its slabs, columns & beams,
  footings, walls, openings, ramps & stairs on / off — that level only.
  The level's eye turns dim while something is hidden.
- **Ghost** on each level's row: that level in light blue in the plan of
  the one you work on — to line things up with it.
- **Columns along an excavation**: a row clicked along a dig's side lines
  up inside it, faces flush, the end ones in the corners — and turns with
  the row. On the lowest level, a column reaches the dig's floor by itself.
- The excavation's floor no longer flickers with what stands on it.
- The levels strip no longer shrinks after a click on an eye; ArchXQ's tab
  in the side tray comes back if IngeTrazo closed it.

## 0.9.3

- **Guide lines** from inside ArchXQ (the guides icon on the top bar): make
  one, delete one, delete them all; drawn in the plan, and they pull the
  cursor firmly — their crossings most of all.
- **OK / Apply** in every window: Apply keeps it open.
- **Edit walls**: move a straight wall's ends with the mouse (the walls
  meeting there follow); the wall window has Start / End X Y.
- **Hide** in the element windows; the outliner's eye now holds through
  every rebuild.
- **Plan view cuts the building** at the level worked on: what stands
  above it is not shown.
- An excavation drawn **onto the plot's boundary** is no longer refused —
  it sits 2 cm in. A drawing that can't be made now says why, in a window.
- **Typing the sizes** in every tool's Help: always separate two numbers
  with «;» (`57,40;34,40`).
- **Delete plot** in the plot window; the Terrain row sits under the ground
  floor; deleted walls no longer come back.
- **Building elements** (ramps, stairs) and **automatic slabs** are in
  ArchXQ IT Pro — files made with them open in the Lite with everything
  kept.

## 0.9.2

- **Help** in every tool: the last item of the left menu (and the «?» at
  the end of the options bar) opens a small manual — what the tool is for,
  step by step, tips, common mistakes, keys, with pictures.
- **About** on the globe of the top bar: the version, and the links
  (site, Get Pro, source code, manual, videos, report a problem).
- «From survey points» left the Draw plot menu until it is ready.

## 0.9.1

- The zip now unpacks into the `archxq_it` folder on Linux and macOS too
  (0.9.0 stored its paths with backslashes).
- ArchXQ IT Pro is out: www.xq.com.br/archxq-it

## 0.9.0 — first public beta

- Project & levels, Terrain (plot, survey points, setbacks, excavations and
  fills with ramps), Walls, Columns (stamp, draw, row, grid).
- Files made with ArchXQ IT Pro open with everything visible and kept.
