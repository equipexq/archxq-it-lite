# Changelog — ArchXQ IT Lite

## 0.15.0

**Water in an excavation, one level's walls painted in one go, and Help on every library card.** A pit filled with water; a right-click on a card for its Help; the version in the ArchXQ bar; walls that snap to the centre line of the wall under them, also the ghost's; cleaner wall corners; and a long list of fixes. Tested with IngeTrazo 0.6.3.2. Your projects open as before.

- **NEW: water in an excavation (a pool).** The Excavation window has a new **Water** section under the corners' table. Tick **Fill with water** and the pit gets a water surface, **Below the edge** under its edge (0.15 m to start). It meets the walls exactly, also on sloped sides and on a sloped floor, and follows the pit when its shape or depth changes. Its **Transparency** goes from 0 % (opaque) to almost clear at 100 %. **Apply** keeps the window open, to try a value and change it again. The window tells you the water's level, and says so when it would fall under the floor.
- **NEW: right-click a library card for its Help.** Every card of the library, on the strip and in «More», has a menu on the right-click: **Help: «the type»**, then **Full guide** of the element. The Help shows the card's picture, how the type looks, how to use it, its limits, and what to do when something goes wrong. In English, Portuguese and German.
- **NEW: one level's walls get a colour in one go.** A wall's Material tab has a new box, **All walls on this level (N)**. With it ticked, every wall of that level takes the colour you pick, each as its own, and the walls of the other levels stay as they are. The box stays ticked after Apply.
- **«All walls of type «…»» now starts unticked.** A colour picked for a wall of one of your types goes on that wall only, unless you tick the box. Before, every wall of the type changed on every level.
- **The version in the ArchXQ bar.** Beside «⏻ ArchXQ», the bar now shows which version you have, handy when you follow a video or write to support. Hover it for the full line (edition, IngeTrazo, Windows); click it for the About.
- **FIXED: Apply on the Material tab with several walls selected.** It painted only the wall you had clicked. It now paints all the selected walls, as «Apply to the N selected» does.
- **FIXED: an L-shaped excavation's step wall showed grey, without its material.** The wall at the inner corner of an L (a pool with a step, a pit around a corner) faced the earth instead of the pit. Every wall of a pit now faces the pit, and every edge of a fill faces away from it. An excavation already in a project is fixed the next time the terrain changes.
- **FIXED: an older project's excavation on the boundary now reaches it.** A project made before 0.13.0 kept an excavation that touches the boundary 2 cm inside it, so the ground left a strip there. Opened now, the pit and the ground go right to the boundary (save the project to keep it). Walls and levels are not touched.
- **FIXED: a level left unseen after the Plan view.** Sometimes, back in 3D from one level's plan, the other levels stayed hidden with their eye on, until the eye was clicked off and on. ArchXQ now checks the whole building again a moment after you leave the plan or an elevation.
- **FIXED (German): a board wall's and a wall top's «Flat» no longer read «Flachdach».** The boards' third choice is now **Smooth** (Glatt, Lisa) and a wall's top **Flat top** (Waagerecht).
- **FIXED: «Upgrade to Pro…» on a connection that drops long downloads.** The download stopped partway every time and was said to have arrived damaged. It now asks for the rest of the file, as many times as needed (up to 8), and checks the whole zip before it is put in place.
- **ArchXQ's windows now have a grey edge.** On a dark theme, a window's black came right against IngeTrazo's black behind it, and the window's edge could not be seen. Every ArchXQ window now has a thin grey border (Windows 11).
- **FIXED: no more fields that do nothing in the plot's panel.** «Draw plot» showed a «Ground level» field and «Edit plot» a «Snap to» choice that nothing read: a value set there changed nothing. They are gone — the project's ground level is in «Edit project», the grid's snap is the plan's own switch.
- **FIXED: a measure typed on a grip that cannot be read is said.** Typing on a grip while dragging and pressing Enter with something that is not a measure dropped the text without a word. A message now says it could not be read and how to type it; the drag goes on.
- **FIXED: a number field no longer goes back to its old value without a word.** A number under the field's least (0.05 where 0.10 is the least) put the old value back; it now takes the least. A text the field cannot read keeps the value, and a tip under the field says so.
- **FIXED: a number over 10 typed in a bar is metres where metres fit.** A bare number over 10 was read as centimetres in every bar (meant for doors: «85» = 85 cm), even where it is a normal size in metres. It is now read as centimetres only where it cannot be metres — over what that field takes; «120 cm» / «0.85» read as ever.
- **FIXED: a move typed below the bar goes as far as one typed above it.** In «Move across» / «Move along» (−1…1 m on the bar), «3» moved 3 m but «−2» only −1 m. A typed move now reaches as far back as forward.
- **FIXED: the wall's height in the options bar reaches the selected walls.** With walls selected, the bar's thickness changed them but «Custom 1,10» (or «Level height») did not, and nothing was said. The height now goes to them too, as the thickness does.
- **FIXED: a measure is never changed behind your back.** A window opened only to rename a wall (or look at a column…) and closed with OK wrote its measures back rounded to the field's 2 decimals — an 11.5 cm wall became 12 cm — and a value outside the field's range was cut to it. A window now gives back exactly what the model had unless you change that field, and the length fields take millimetres: «0,115 m» (a round value still reads «0,20 m»).
- **FIXED: a change that cannot be applied says so.** When a change from the bar or a column row following its walls failed, nothing was said and the model stayed as before. Now a message at the foot of the view says what did not follow and why, and the details go to the ArchXQ log.
- **FIXED: a piece of a file that cannot be read is kept, not lost.** A wall or column the file holds but this version cannot read (written by hand, by the AI, by a newer version) was left out — and the next save deleted it for good. It is now kept aside in the file, untouched, a message says how many, and it comes back as soon as it can be read.
- **FIXED: «Repeat level» with nothing to repeat keeps your changes.** When the level had nothing to copy, the new name and height typed in the window were dropped without a word. They are now saved, and a message says that nothing was repeated.
- **A fill / platform as low as 1 cm.** Its height over the ground started at 5 cm, so a path or a patio laid on the ground stood over the doors' sill and the floor. Now it goes down to 1 cm, in the options bar, in its window and in the file.
- **FIXED: on the Terrain row, the levels' ghosts show.** With the Terrain row picked in the plan, turning on the ghost of Level 1 or Level 2 showed nothing — the plot could not be drawn round the house seeing its walls. Now the levels whose ghost is on are drawn there in green, as on any level, and their corners and edges pull the plot's tool.
- **FIXED: a number typed with a point is taken on a Windows set to a comma.** On a Windows in Portuguese, German, French… the number fields wait for «0,20»: «0.20» typed in the options bar or a window was refused without a word, and the field went back to what it had. Now the point and the comma both work, in every number field: sizes, heights, angles.
- **The plan keeps IngeTrazo's Wireframe and X-ray.** The Plan view (and the elevations) drew the walls in their own white hidden line over the file's style, so picking Wireframe or X-ray in IngeTrazo's Style menu did nothing there: the walls already drawn hid the reference image under them, and with it the doors and windows still to place. Now, with the file in Wireframe or X-ray, the plan shows it — at once, without leaving the plan — and you see the image through the walls. Back to Shaded or Textures, the plan's own look comes back. ArchXQ's own X-ray button works as before.
- **A wall's end grip turns the wall at the corner, instead of moving it.** Dragging the end of a wall took the wall at an angle at that corner along, moved whole and square — exactly what that wall's own arrow does, so two grips did one thing. Now the end of a line twists it and its middle pulls it straight: the corner goes along the wall you drag, and the wall at an angle turns on its other end, which stays where it is with the walls joined there — as «Edit walls ▸ Move points» already does. A wall in line at that corner still gets shorter or longer. Its doors and windows keep their distance from the end that stays. To make a room larger and keep it square, drag the middle arrow of the wall at the side.
- **A centred wall's point goes on the centre line of the wall under it.** Drawing a wall «Centre» over a wall already there, the cursor took the other wall's top for a face: the red / green alignments stood aside and the new wall's end landed on its face, not on its middle. Now, over a wall, the point goes straight across onto that wall's centre line — drawn dashed in blue while it holds — near its end it takes the end itself, and along the line the red / green alignments with the corners placed and the other walls' ends work as everywhere else. A real snap of the drawing (an end of a line) still wins. The pull reaches only a few pixels round the centre line: zoomed in, the rest of the wall's thickness is free for its faces and its layers' lines. The walls of another level seen as a ghost pull the same way: turn on the ghost of the floor below and draw the floor above right over its walls, centre on centre — the new walls do not join the ghost's, they only stand over them. Point by point and the rectangles; «Outside» and «Inside» walls are as before.
- **FIXED: a thinner wall going on from an L corner no longer splits the corner.** At the corner of two walls of one thickness (two «MyWall» of 20 cm), a thinner wall (15 cm) going on in line with one of them pushed in between the two: the corner lost a notch on the outside and the walls overlapped. Now the two walls of the L keep their corner, mitred, and the thinner one butts on it — a small step where the thicknesses differ. Found in 13 corners of our own test projects, all better now; every other joint is built exactly as before. The same goes for the thickness: a wall drawn from the corner of an L keeps the thickness you chose (a 15 cm wall from the corner of two 20 cm walls came out 20 cm); carried on straight from a wall's free end it still takes that wall's, so a straight run has no step.
- **FIXED: where four walls cross, the thicker pair runs through whole.** Two 20 cm walls in line, crossed by a 20 cm wall on one side and a 15 cm one on the other: the 20 + 15 went through instead, cut square in the middle — the 20 cm wall was split and two small notches were left where the 15 cm one is narrower. Now the pair that is thick all along goes through, and the two across butt on its faces.

## 0.14.0

**An image on each level, to draw over.** Lay a scan or a photo of a plan on a level, give it its true size in two clicks and trace the walls over it; the ghost of the level below shows its image too, so the floors match. Also columns that show your changes live, and a batch of fixes. Tested with IngeTrazo 0.6.2.1. Your projects open as before.

- **NEW: an image on a level, to draw over.** Walls ▸ «Image / PDF reference» lays a photo or a scan of a plan (PNG, JPG, BMP) on the current level's floor, its lower-left corner on the origin (0,0); a second one comes at the right of the first. It shows only while you work on that level, and it is kept inside the file; a picture icon on the level's row shows or hides it in one click. Laying or matching an image switches to the Plan view; «Plan view» again takes you back to 3D. Click an image in the view and its bar comes out (Walls ▸ Reference, on its level); double-click it and the level's window opens on its References tab. «X» and «Y» in the bar place its lower-left corner exactly — typed, or 1 cm at a time with the arrows, one Ctrl+Z each. Another level's ghost shows that level's images too, faded over the plan: lay the ground floor's plan under the first floor's and match them with «Place» or X and Y. «Measure» gives it its true size: click the two ends of something whose length you know (a wall, a dimension line) and type its real length; a scan drawn a little askew (under 5°) is straightened at the same time. Then click where that first point goes — a corner already drawn, the origin — or Esc to leave it. «Place» moves it by a point, «Show» hides it, and the eraser removes it, each one Ctrl+Z. It comes in whole (100 %) and what you draw stands over it; «Opacity» makes it lighter, so your lines stand out. The level's window has a «References» tab too — the pencil icon in the bar opens it there: every image of the level with its size, its opacity and «Remove», seen in the model as you change them and kept by OK in one Ctrl+Z. A level can hold several images; a level moved up or down takes them with it, and a level renamed keeps them. (A PDF page as a reference, with its lines and walls made from them, is the Pro's.)
- **Columns show your changes live, and Apply is much quicker.** A column's window now shows the change in the model as you make it, as a wall's already did; OK and Apply store it, Cancel puts it back. When a change touches only columns, Apply builds only them, and what joins them, instead of the whole building. And a live preview no longer redraws the whole project at each step, so it follows the mouse while you drag. Columns, beams, footings and walls given a shape in the Pro show that shape in the Lite.
- **FIXED: a wall that almost meets another one's corner stays straight, and keeps its doors and windows.** Drawing over a plan, a wall easily ends a few centimetres off the corner of a wall already there. Its end was pulled straight onto that corner, so the new wall came out slightly slanted, and its doors and windows were no longer cut through it: they showed only as outlines on its faces. Now each wall's end goes along its own line to where the two lines cross: the corner closes exactly, neither wall turns, and the openings are cut as always. Walls that already met are built exactly as before.
- **FIXED: the plan keeps its look.** In the plan view, some changes — the opacity of a reference picture in the level's window, among others — made the view lose the plan's look: textures and colours came back while the Plan button stayed on. The program draws the pictures of your sheets with the same 3D view and left it without the plan's style; now the plan's look is put back after each one.
- **«Apply» in the Level window keeps the window open.** It used to close the window and open it again a moment later. Now it stores what you changed (name, height, references — one Ctrl+Z) and the window stays where it is, on its tab; a Cancel after it keeps what was applied.
- **FIXED: your own objects stay on the plan of their level.** A car, a bench, a fountain — anything modelled or imported in IngeTrazo, not ArchXQ's — placed on a level's floor disappeared from that level's plan as soon as the view changed and came back. An object whose foot stands in a level's height (from its floor to under the next one) now belongs to that level and shows on its plan; objects on the garden, outside every level's height, stay with the Terrain as before.
- **A wall of one of your types can have its own colour.** The Material tab of a wall of a type now has the box «All walls of type «…»», ticked: as before, what you pick goes to every wall of the type and to the next ones drawn with it. Untick it and the colour goes to the selected walls only, as their own — the other walls of the type keep theirs.
- **What you draw always shows.** If a «Show» chip is off (Openings, Walls, Slabs, Stairs, Structure, Roof) and you draw something it hides — a wall, a window, a stair — the chip comes back on by itself and a note says so. Before, the new element was made hidden and seemed not drawn at all. Editing or undoing leaves your chips as they are.
- **FIXED: one click on a field's arrow could run on for minutes.** With a large element selected, every step of a number in the options bar rebuilt it at once, inside the click — the arrow's repeat kept going through the slow rebuilds. A number now applies once it stops changing (a third of a second), in one rebuild and one Ctrl+Z.
- **FIXED: clicking a level's image picked what lay under it.** In 3D, a click on the Level 2 plan selected a wall of Level 1 below it — the work jumped to Level 1 and the picture went out of sight. An image in front of the model now takes the click (a double-click opens its level's References tab); a drag from it is still a box selection. What is in front is read from what the view actually shows: a wall standing on the picture, or a picture switched off, never takes a wall's click.
- **FIXED: a level's picture with «Show» off could stay on screen.** When a file had lost the picture's layer, «Show» could not hide it — it covered the floor and took its clicks. The layer comes back and «Show» works again.
- **A level's image stays sharp in 3D.** Seen at a slant, a plan went grey and blurred a few metres away; images are now drawn with anisotropic filtering (16×) — their lines stay crisp across the whole sheet.
- **The guide sheet of a bare level starts at the origin, and covers the level's images.** A level with nothing on it had its 20 × 20 m blue sheet centred on the origin; its lower-left corner is now on 0,0, where an image comes in. A level with things on it keeps its sheet round them, now stretched over its images too.
- **FIXED: OK in a level's window, with nothing of the level changed, no longer builds the building again.** It stored the level as it was anyway: the walls and the terrain were made again (seconds on a large project) and Ctrl+Z had empty steps to go through before the change you made. Now the name and the height are stored only when one of them changed; the level is still the one you work on after OK.

## 0.13.0

**A sky behind the 3D view, «Join» for walls, a corner column at any angle, 8 more walls and solid panels.** Tested with IngeTrazo 0.6.2.1. Your projects open as before.

- **NEW: a sky behind the 3D view.** The «Sky» chip on the view bar (after «Extents») shows a real sky picture behind your model, in perspective and in parallel views, with a plain ground in the sky's own tone below the horizon. The chip has its own little sun-and-cloud icon. It is on by default, in new projects and in the ones you saved before (where you turn it off, it stays off); it is saved with the project and never shows in the plan or the sheets. (ArchXQ IT Pro adds more than 600 skies to pick, your own pictures, rotation, exposure, horizon and the picture's own ground.)
- **NEW: 8 more walls in the library,** each with its colour from the start: Masonry 25, Concrete 15, Concrete 20, Exposed brick, Concrete block, Vertical boards, Horizontal boards and Glass block. Pick one before you draw, or click it with walls selected. (The Pro gives them their textures.)
- **Timber boards you can see in the drawings:** the vertical boards come with battens over the joints, the horizontal ones as lap siding. «Boards» in the library: Battens, Lap siding or Flat. On a wall with layers they stay, cut in the outer layer (3 cm or more).
- **NEW: the corner column fits the walls at any angle.** A column put where walls meet (L, T, X or Y, at 30°, 60°, 120° or any angle) takes the exact shape of the meeting: nothing sticks out of the walls and nothing is left open. At 90° with walls of the same thickness it is the square it was; with different thicknesses it is their two thicknesses (20 × 15 cm). Columns you already have stay as they are.
- **NEW: Edit walls ▸ «Join»** — the inverse of Split: click a wall, then the one in line with it, end to end, and they become one wall. Their doors and windows stay exactly where they are. Only like walls are joined (thickness, layers, height, alignment, material); otherwise the status bar says what differs. Also with the right click on two selected walls: ArchXQ ▸ «Join walls». Ctrl+Z puts them back.
- **ArchXQ's panels are solid now.** The phase bar, Levels, the view bar, the Plan view and Present buttons, the quick help, the round menu and the labels drawn over the 3D view had a slightly see-through background: on a busy model, its lines showed through the icons and the text. They keep the same colours, with nothing of the model behind them, so they read clearly on any scene.
- **ArchXQ's tab in the side tray shows the XQ mark** instead of a plain «A», beside IngeTrazo 0.6.2's new tab icons (with an earlier IngeTrazo it stays as it was).
- **The ghost of a level is now green, with a thicker line,** so it no longer hides under the blue guide lines.
- **FIXED: a short return between two outside walls.** A wall as long as it is thick, joining two outside walls (a 200 mm step in the façade), overlapped one of them at the mitred corner. Now it meets both on the exact mitre. Found by Drazen on a real project: thank you.
- **FIXED: an excavation on the plot's boundary is dug right to it.** The ground no longer keeps a thin strip of 2 cm along the boundary, and the earth is counted at the real size. Files with the strip written in their data keep it until you move the corners onto the boundary.
- **FIXED: a curved wall no longer fills the outside rows with tiny dimensions.** Each facet of its curve was dimensioned as a corner, and dozens of 2 cm numbers were stacked on each other; now only its two ends are.
- **FIXED: the Update button on some Windows computers.** Where Windows' own list of certificates is out of date, «Update to …» failed with «certificate has expired», and no update came through the button. ArchXQ now checks xq.com.br with the certificate it carries, and only then with Windows'. It works from this version on: if your button fails today, install this one by hand from GitHub, once.
- Walls you already have stay exactly as they are.

## 0.12.1

**Compatibility with the multiple views of IngeTrazo 0.6.1.** With two to four views in a tab, the views now sit inside and ArchXQ around them.

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
