# Changelog — ArchXQ IT Lite

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
