"""The other ArchXQ pieces, each built ONCE and placed by compat.place:

- SideStrip (left): how to draw the picked element (its methods).
- ViewBar (bottom): what is shown and how — parts, view, camera.
- PropsPanel (right, a tab of the side tray): the picked element's
  properties, and the current phase's status.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import icons, model
from .help import HELP, help_button
from .phases import ELEMENTS, PHASES, SYSTEMS, VISIBLE_PARTS
from .style import BLUE, CSS


class _WheelGuard(QObject):
    """The mouse wheel over a field: it scrolls the panel unless the field
    was clicked (has the keyboard)."""

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Wheel and not obj.hasFocus():
            event.ignore()
            return True
        return False


_WHEEL_GUARD = _WheelGuard()


def _chip(text: str, checkable: bool = True) -> QPushButton:
    b = QPushButton(text)
    b.setProperty("axq", "chip")
    b.setCheckable(checkable)
    b.setFocusPolicy(Qt.NoFocus)
    return b


def _vsep() -> QFrame:
    f = QFrame()
    f.setObjectName("axq_vsep")
    return f


def _caption(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("axq_caption")
    return lab


# ---- Left: drawing methods ------------------------------------------------------
class SideStrip(QFrame):
    def __init__(self, owner) -> None:
        super().__init__()
        self.owner = owner
        self.setObjectName("axq_strip")
        self.setStyleSheet(CSS)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 6)
        lay.setSpacing(1)
        self.title = QLabel()
        self.title.setObjectName("axq_title")
        lay.addWidget(self.title)
        self.box = QVBoxLayout()
        self.box.setSpacing(1)
        lay.addLayout(self.box)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)

    def fill(self, element: str | None, method: str | None) -> bool:
        """Show the element's methods; False when there is nothing to show."""
        self._trash = []                # off now, deleted by the loop
        while self.box.count():
            w = self.box.takeAt(0).widget()
            if w is not None:
                self.group.removeButton(w)
                w.hide()
                self._trash.append(w)
                w.deleteLater()
        el = ELEMENTS.get(element) if element else None
        if el is None or not el.methods:
            return False
        self.title.setText(el.label)
        for m in el.methods:
            b = QPushButton(m.label)
            b.setFlat(True)
            b.setCheckable(True)
            b.setChecked(m.label == method)
            b.setProperty("axq", "item")
            ico = icons.icon(m.icon)
            if not ico.isNull():
                b.setIcon(ico)
                b.setIconSize(QSize(22, 22))
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setToolTip(f"{el.label} — {m.label.lower()}")
            b.clicked.connect(
                lambda _=False, n=m.label: self.owner.on_method(n))
            self.group.addButton(b)
            self.box.addWidget(b)
        # the last item: the tool's guide (his idea, 2026-10-04) — always
        # the same place, so the hand finds it without looking
        h = QPushButton("Help")
        h.setFlat(True)
        h.setProperty("axq", "item")
        h.setIcon(icons.icon("help"))
        h.setIconSize(QSize(22, 22))
        h.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        h.setToolTip(f"{el.label} — how it works (the guide)")
        h.clicked.connect(lambda _=False, k=el.key: self._guide(k))
        self.box.addWidget(h)
        self.adjustSize()
        # measured again once the new buttons are styled: measured now, it
        # kept the title's size alone — the menu squashed (his screen,
        # 2026-10-02: «Draw plot» shrunk while drawing in plan)
        QTimer.singleShot(0, self._fit)
        return True

    def _fit(self) -> None:
        try:
            self.layout().activate()
            self.resize(self.sizeHint())
        except RuntimeError:            # gone meanwhile (reload)
            pass

    def _guide(self, key: str) -> None:
        from .guide import open_guide
        open_guide(key, self.window())


# ---- Left, under the methods: the «Building elements» -------------------------------
#: (key, label, icon, tip) — a section of its own, apart from the phases
#: (his call, 2026-10-05, mockup C): ramps and stairs first, a low wall,
#: roof types… later. Only what is built shows (no placeholders).
BUILDING_ELEMENTS = [
    ("ramp", "Ramp", "ramp", "A ramp from a level (or the ground) to another "
                             "— set it up, then click where it starts"),
    ("stair", "Stair", "stair", "A stair from a level (or the ground) to "
                                "another — its steps by Blondel's rule"),
]


class ElementsBox(QFrame):
    """«Building elements»: tools that stand apart from the phases menus —
    each opens its own window, then draws in plan on its level."""

    def __init__(self, owner) -> None:
        super().__init__()
        self.owner = owner
        self.setObjectName("axq_strip")
        self.setStyleSheet(CSS)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 6)
        lay.setSpacing(1)
        title = QLabel("Building elements")
        title.setObjectName("axq_title")
        lay.addWidget(title)
        for key, label, ico, tip in BUILDING_ELEMENTS:
            b = QPushButton(label)
            b.setFlat(True)
            b.setProperty("axq", "item")
            i = icons.icon(ico)
            if not i.isNull():
                b.setIcon(i)
                b.setIconSize(QSize(22, 22))
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, k=key: owner.start_element(k))
            lay.addWidget(b)
        # the guide, last — as in the methods above
        h = QPushButton("Help")
        h.setFlat(True)
        h.setProperty("axq", "item")
        h.setIcon(icons.icon("help"))
        h.setIconSize(QSize(22, 22))
        h.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        h.setToolTip("Building elements — how they work (the guide)")
        h.clicked.connect(self._guide)
        lay.addWidget(h)
        self.adjustSize()

    def _guide(self) -> None:
        from .guide import open_guide
        open_guide(BUILDING_ELEMENTS[0][0], self.window())


# ---- Left, on top: the plan view switch --------------------------------------------
class PlanSwitch(QPushButton):
    """PLAN VIEW — a piece of its own, right under the ⏻ ArchXQ switch and
    above the drawing methods: where you edit (top, parallel). Orbiting
    leaves it for the 3D view; a click brings it back."""

    def __init__(self, owner) -> None:
        super().__init__("▦   Plan view")
        self.setObjectName("axq_plan")
        self.setStyleSheet(CSS)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip("Plan view: from the top, to draw and edit — "
                        "locked to the top (pan and zoom freely).\n"
                        "The icons under it: the plan and the four "
                        "elevations, square with the building.\n"
                        "Click again = back to the 3D view.")
        self.clicked.connect(lambda: owner.toggle_plan())

    def set_plan(self, on: bool) -> None:
        self.setChecked(bool(on))


#: the plan and the four sides (his idea, 2026-10-10): shown under «Plan
#: view» while it is on — (key, tooltip)
#: the sides CLOCKWISE round the square, as the eye goes (his call,
#: 2026-10-10): left, top (the back), right, bottom (the front)
VIEWS = (("plan", "Plan — from the top"),
         ("left", "Left elevation"), ("back", "Back elevation"),
         ("right", "Right elevation"), ("front", "Front elevation"))


def _view_icon(key: str, size: int = 22):
    """A square drawn in light ink: the plan, four squares; a side, the
    square with that side in orange."""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
    ink, accent = QColor("#d6d9dd"), QColor("#e8742c")
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size * 2
    m = s * 0.18
    r = QRectF(m, m, s - 2 * m, s - 2 * m)
    p.setPen(QPen(ink, s * 0.07))
    p.setBrush(Qt.NoBrush)
    if key == "plan":
        h = r.width() / 2
        for i in range(2):
            for j in range(2):
                p.drawRect(QRectF(r.left() + i * h, r.top() + j * h, h, h))
    elif key == "xray":
        # two boxes seen through each other: the one behind, dashed
        d = r.width() * 0.28
        front = QRectF(r.left(), r.top() + d, r.width() - d, r.height() - d)
        back = QRectF(r.left() + d, r.top(), r.width() - d, r.height() - d)
        p.setPen(QPen(ink, s * 0.06, Qt.DashLine))
        p.drawRect(back)
        p.setPen(QPen(accent, s * 0.07))
        p.drawRect(front)
    else:
        p.drawRect(r)
        a, b = {"front": (r.bottomLeft(), r.bottomRight()),
                "back": (r.topLeft(), r.topRight()),
                "left": (r.topLeft(), r.bottomLeft()),
                "right": (r.topRight(), r.bottomRight())}[key]
        p.setPen(QPen(accent, s * 0.16, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(a), QPointF(b))
    p.end()
    return QIcon(pm)


class ViewsStrip(QFrame):
    """The plan and the four elevations — five icons, no text, under the
    «Plan view» switch while it is on; the one shown is lit."""

    def __init__(self, owner) -> None:
        super().__init__()
        self.owner = owner
        self.setObjectName("axq_strip")
        self.setStyleSheet(CSS)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 3, 4, 3)
        lay.setSpacing(2)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        from PySide6.QtWidgets import QToolButton
        for key, tip in VIEWS:
            b = QToolButton()
            b.setIcon(_view_icon(key))
            b.setIconSize(QSize(20, 20))
            b.setCheckable(True)
            b.setAutoRaise(True)
            b.setFocusPolicy(Qt.NoFocus)
            b.setToolTip(tip)
            b.setStyleSheet("QToolButton { border: 1px solid transparent; "
                            "border-radius: 4px; padding: 2px; }"
                            "QToolButton:hover { border-color: #6b7178; }"
                            "QToolButton:checked { border: 1px solid "
                            "#e8742c; background: #4a3324; }")
            b.clicked.connect(lambda _c=False, k=key: owner.show_view(k))
            self.group.addButton(b)
            self.buttons[key] = b
            lay.addWidget(b)
        # after them, apart: X-RAY — the faces see-through, to pick and
        # place what lies behind (his ask, 2026-10-10: a side view is of no
        # use for precise edits without it)
        lay.addWidget(_vsep())
        self.xray = QToolButton()
        self.xray.setIcon(_view_icon("xray"))
        self.xray.setIconSize(QSize(20, 20))
        self.xray.setCheckable(True)
        self.xray.setAutoRaise(True)
        self.xray.setFocusPolicy(Qt.NoFocus)
        self.xray.setToolTip("X-ray: see through the faces — pick and move "
                             "what lies behind (the plan and the "
                             "elevations)")
        self.xray.setStyleSheet(self.buttons["plan"].styleSheet())
        self.xray.toggled.connect(lambda on: owner.toggle_xray(on))
        lay.addWidget(self.xray)

    def set_current(self, key: str | None, tips: dict | None = None,
                    xray: bool | None = None) -> None:
        for k, b in self.buttons.items():
            b.setChecked(k == key)
            if tips and k in tips:
                b.setToolTip(tips[k])
        if xray is not None and self.xray.isChecked() != xray:
            self.xray.blockSignals(True)
            self.xray.setChecked(xray)
            self.xray.blockSignals(False)


# ---- Bottom: view controls --------------------------------------------------------
class ViewBar(QFrame):
    def __init__(self, owner) -> None:
        super().__init__()
        self.owner = owner
        self.setObjectName("axq_viewbar")
        self.setStyleSheet(CSS)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(3)

        # (levels are shown / hidden in the levels strip — N)
        lay.addWidget(_caption("Show"))
        self.parts: dict[str, QPushButton] = {}
        for key in VISIBLE_PARTS:
            b = _chip(PHASES[key].label)
            b.setChecked(True)
            b.setToolTip(f"Show / hide the {PHASES[key].label.lower()}")
            b.toggled.connect(
                lambda on, k=key: owner.on_view_option(f"show:{k}", on))
            self.parts[key] = b
            lay.addWidget(b)
        lay.addWidget(_vsep())

        lay.addWidget(_caption("View"))
        self.views = QButtonGroup(self)
        for i, text in enumerate(("3D", "Plan", "Section", "Elevation")):
            b = _chip(text)
            b.setChecked(i == 0)
            self.views.addButton(b, i)
            lay.addWidget(b)
        self.views.idClicked.connect(
            lambda i: owner.on_view_kind(("3d", "plan", "section",
                                          "elevation")[i]))
        lay.addWidget(_vsep())

        lay.addWidget(_caption("Camera"))
        self.persp = _chip("Perspective")
        self.persp.setToolTip("Perspective / parallel projection")
        self.persp.toggled.connect(owner.on_perspective)
        lay.addWidget(self.persp)
        for name, text in (("top", "Top"), ("front", "Front"),
                           ("right", "Right"), ("iso", "Iso")):
            b = _chip(text, checkable=False)
            b.clicked.connect(lambda _=False, n=name: owner.on_camera(n))
            lay.addWidget(b)
        ext = _chip("Extents", checkable=False)
        ext.setToolTip("Zoom to the whole model")
        ext.clicked.connect(lambda: owner.on_camera("extents"))
        lay.addWidget(ext)

    def sync_view(self, plan: bool) -> None:
        """3D / Plan lit as the plan view switch stands."""
        b = self.views.button(1 if plan else 0)
        if b is not None:
            b.setChecked(True)

    def sync_camera(self, perspective: bool) -> None:
        self.persp.blockSignals(True)
        self.persp.setChecked(perspective)
        self.persp.blockSignals(False)


# ---- Right: properties ---------------------------------------------------------------
class PropsPanel(QWidget):
    def __init__(self, owner) -> None:
        super().__init__()
        self.owner = owner
        self.values: dict[tuple[str, str], object] = {}   # prototype memory
        lay = QVBoxLayout(self)
        self.crumb = QLabel()
        self.crumb.setEnabled(False)
        lay.addWidget(self.crumb)
        self.title = QLabel()
        f = self.title.font()
        f.setPointSize(f.pointSize() + 3)
        f.setBold(True)
        self.title.setFont(f)
        head = QHBoxLayout()
        head.addWidget(self.title)
        head.addStretch()
        self._topic = "project"
        head.addWidget(help_button(lambda: self._topic))
        lay.addLayout(head)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)
        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        self.form.setContentsMargins(0, 8, 0, 8)
        lay.addWidget(self.form_host)
        self.actions = QVBoxLayout()
        lay.addLayout(self.actions)
        lay.addStretch(1)
        # (the prototype's «Phase: … Mark phase complete» section is gone —
        # his call, 2026-10-09: the phases are a guide on the top bar)

    def show_for(self, phase: str, element: str | None, done: bool,
                 doc: dict) -> None:
        ph = PHASES[phase]
        el = ELEMENTS.get(element) if element else None
        self.crumb.setText(ph.label + (f"  ›  {el.label}" if el else ""))
        self.title.setText(el.label if el else ph.label)
        self._topic = next((t for t in (element, phase) if t in HELP),
                           "project")
        while self.form.rowCount():
            self.form.removeRow(0)
        while self.actions.count():
            w = self.actions.takeAt(0).widget()
            if w is not None:
                w.deleteLater()

        if phase == "project":
            self._project_summary(element, doc)
        else:
            self.hint.setText(ph.hint if el is None
                              else "Pick how to draw it on the left; set "
                                   "its properties here.")
            if phase == "terrain" and element in ("plot", "plot_edit",
                                                  "ground"):
                self._plot_summary(doc)
            elif phase == "terrain" and element == "setbacks":
                self._setback_summary(doc)
            elif phase == "terrain" and element == "survey":
                self._survey_summary(doc)
            elif phase == "terrain" and element in ("excavation", "fill"):
                self._dig_summary(doc, fill=element == "fill")
            if el is not None:
                for prop in el.props:
                    self.form.addRow(prop.name,
                                     self._editor(el.key, prop, doc))

    # -- project phase: a summary + the buttons that open the dialog ---------------
    def _action(self, text: str, fn, primary: bool = False) -> None:
        b = QPushButton(text)
        if primary:
            b.setStyleSheet(f"QPushButton {{ background: {BLUE}; color: "
                            "white; font-weight: bold; padding: 6px 12px; "
                            "border-radius: 4px; }")
        b.clicked.connect(fn)
        self.actions.addWidget(b)

    def _row(self, label: str, value: str) -> None:
        v = QLabel(value or "—")
        v.setWordWrap(True)
        v.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.form.addRow(label, v)

    def _project_summary(self, element: str | None, doc: dict) -> None:
        if not model.has_project(doc):
            self.hint.setText("No project yet. Start one: name, levels and "
                              "sheet defaults, in a single form.")
            self._action("Start a new project…",
                         lambda: self.owner.edit_project("project"),
                         primary=True)
            return
        p, levels = doc["project"], doc["levels"]
        if element == "levels":
            self.hint.setText("Storeys, top to bottom. Elevations are "
                              "worked out from the ground floor level.")
            elev = model.elevations(levels, p["ground_level"])
            for i in range(len(levels) - 1, -1, -1):
                lv = levels[i]
                self._row(lv["name"], f"{elev[i]:+.2f} m   ·   "
                          f"h {lv['height']:.2f} m")
            self._action("Edit levels…", self.owner.edit_current_level)
            return
        self.hint.setText("The data every drawing and sheet reads.")
        self._row("Name", p["name"])
        self._row("Client", p["client"])
        self._row("Location", p["location"])
        self._row("Author", p["author"])
        self._row("Date", p["date"] or "(the day a sheet is exported)")
        self._row("System", SYSTEMS[doc["system"]])
        nb, nf = model.count(levels, "basement"), model.count(levels, "floor")
        parts = ([f"{nb} basement" + ("s" if nb > 1 else "")] if nb else []) \
            + ["ground floor"] \
            + ([f"{nf} floor" + ("s" if nf > 1 else "") + " above"]
               if nf else [])
        self._row("Levels", " · ".join(parts))
        self._row("Ground level", f"{p['ground_level']:+.2f} m")
        self._row("North", f"{p['north_deg']:.1f}°")
        self._row("Sheets", f"{p['paper']} {p['orientation'].lower()}, "
                  f"{p['scale']}")
        self._action("Edit project…",
                     lambda: self.owner.edit_project("project"))

    def _plot_summary(self, doc: dict) -> None:
        from . import plotgeo
        plot = doc.get("plot")
        if not doc.get("_has_plot") or not plot:
            self.hint.setText("No plot yet. Pick how to draw it on the left: "
                              "a rectangle, or point by point. Type exact "
                              "sizes while drawing.")
            return
        pts = plot["corners"]
        self.hint.setText("The plot everything sits on.")
        self._row("Area", f"{plotgeo.area(pts):,.2f} m²")
        self._row("Perimeter", f"{plotgeo.perimeter(pts):,.2f} m")
        self._row("Corners", str(len(pts)))
        self._row("Ground", f"{plot.get('thickness', 0):.2f} m deep")

    def _setback_summary(self, doc: dict) -> None:
        from . import plotgeo
        plot = doc.get("plot")
        if not doc.get("_has_plot") or not plot:
            self.hint.setText("Draw the plot first.")
            return
        self._action("Edit setbacks…", self.owner.edit_setbacks)
        if not any(plot["sb_front"]):
            self.hint.setText("Pick «Mark front sides» on the left, then "
                              "click the side of the plot that faces the "
                              "street — or set it in «Edit setbacks…». The "
                              "back and the sides follow.")
            return
        roles, _dists, area = plotgeo.setbacks_of(plot)
        self.hint.setText("The area you may build on (dashed on the "
                          "model). Every side in detail: «Edit setbacks…».")
        self._row("Fronts", str(roles.count("front")))
        self._row("Buildable", f"{plotgeo.area(area):,.2f} m²" if area
                  else "none — the setbacks leave nothing")
        own = sum(1 for c in plot["sb_custom"] if c is not None)
        if own:
            self._row("Own setbacks", f"{own} side" + ("s" if own > 1
                                                       else ""))

    def _survey_summary(self, doc: dict) -> None:
        from . import plotgeo
        plot = doc.get("plot")
        if not doc.get("_has_plot") or not plot:
            self.hint.setText("Draw the plot first.")
            return
        self._action("Points & import…", self.owner.edit_survey)
        pts = plot.get("survey") or []
        if not pts:
            self.hint.setText("The ground as measured: import the "
                              "surveyor's file («Points & import…») or click "
                              "points on the plot («Add point») — the ground "
                              "then passes through them.")
            return
        used = plotgeo.survey_inside(plot["corners"], pts)
        self.hint.setText("The ground passes through these points (and the "
                          "plot's corners). Type an elevation + Enter over a "
                          "point to change it.")
        self._row("Points", str(len(pts)))
        self._row("Shaping the ground", str(len(used)))
        if used:
            zs = [p[2] for p in used]
            self._row("Elevations", f"{min(zs):+.2f} … {max(zs):+.2f} m")
        if len(used) < len(pts):
            self._row("Not used", f"{len(pts) - len(used)} — outside the "
                      "plot")

    def _dig_summary(self, doc: dict, fill: bool = False) -> None:
        """The excavations (or the fills): each one's earth, the total —
        and the other kind's total, so cut against fill reads at once."""
        from . import terrain
        if not doc.get("_has_plot"):
            self.hint.setText("Draw the plot first.")
            return
        every = doc.get("digs") or []
        digs = [d for d in every if terrain.is_fill(d) == fill]
        if not digs:
            self.hint.setText(
                "No fill yet. Pick how to draw it on the left; set its top "
                "in the bar that opens (1 m over the ground by default)."
                if fill else
                "No excavation yet. Pick how to draw it on the left; set its "
                "bottom in the bar that opens (3 m deep by default).")
        else:
            self.hint.setText(
                "Double-click a fill (on the model or in the outliner) to "
                "edit it — a sloped platform: «Per corner»." if fill else
                "Double-click an excavation (on the model or in the "
                "outliner) to edit it — a ramp: «Per corner».")
        from . import compat
        opened = {d["id"] for d in terrain.opened(doc)}
        vols = compat.dig_volumes(doc)          # merged ones counted once
        total = {True: 0.0, False: 0.0}
        for d in every:
            if d["id"] in opened:
                total[terrain.is_fill(d)] += vols.get(d["id"], 0.0)
        for d in digs:
            if d["id"] in opened:
                self._row(d["name"], f"{vols.get(d['id'], 0.0):,.1f} m³")
            else:
                self._row(d["name"], "not built — outside the plot now")
        if len(digs) > 1:
            self._row("Total", f"{total[fill]:,.1f} m³")
        if total[True] and total[False]:
            # the balance: earth out against earth in
            self._row("Cut / fill", f"{total[False]:,.1f} out · "
                      f"{total[True]:,.1f} in")

    # -- one editor per property kind --------------------------------------------
    def _editor(self, ekey: str, prop, doc: dict | None = None) -> QWidget:
        w = self._editor_of(ekey, prop, doc)
        if isinstance(w, (QDoubleSpinBox, QSpinBox, QComboBox)):
            # the wheel changes it only once clicked (his test, 2026-10-11:
            # scrolling over the panel changed values unseen)
            w.setFocusPolicy(Qt.StrongFocus)
            w.installEventFilter(_WHEEL_GUARD)
        return w

    def _editor_of(self, ekey: str, prop, doc: dict | None = None) -> QWidget:
        # real document values
        if ekey == "setbacks" and prop.name in ("Front", "Back", "Sides"):
            plot = (doc or {}).get("plot")
            has = bool((doc or {}).get("_has_plot") and plot)
            key = prop.name.lower()
            w = QDoubleSpinBox()
            w.setDecimals(2)
            w.setRange(0.0, 100.0)
            w.setSingleStep(0.5)
            w.setSuffix(" m")
            w.setValue(float(plot["sb_dist"][key]) if has else prop.default)
            w.setEnabled(has)
            w.setKeyboardTracking(False)
            w.setToolTip(f"Setback from the {key} of the plot"
                         if has else "Draw the plot first")
            w.valueChanged.connect(lambda v, k=key: self.owner.set_setbacks(
                dist={k: round(v, 3)}))
            return w
        if ekey == "ground" and prop.name == "Thickness":
            plot = (doc or {}).get("plot")
            w = QDoubleSpinBox()
            w.setDecimals(2)
            w.setRange(0.0, 20.0)
            w.setSingleStep(0.05)
            w.setSuffix(" m")
            has = bool((doc or {}).get("_has_plot") and plot)
            w.setValue(float(plot["thickness"]) if has else 0.5)
            w.setEnabled(has)
            w.setToolTip("How deep the ground goes under the plot"
                         if has else "Draw the plot first")
            w.editingFinished.connect(
                lambda w=w: self.owner.set_ground_thickness(w.value()))
            return w

        key = (ekey, prop.name)
        val = self.values.get(key, prop.default)
        store = lambda v, k=key: self.values.__setitem__(k, v)  # noqa: E731
        if prop.kind in ("len", "angle"):
            w = QDoubleSpinBox()
            w.setDecimals(2)
            w.setRange(-1000.0, 1000.0)
            w.setSingleStep(0.05 if prop.kind == "len" else 1.0)
            w.setSuffix(" m" if prop.kind == "len" else "°")
            w.setValue(float(val or 0.0))
            w.valueChanged.connect(store)
            return w
        if prop.kind == "int":
            w = QSpinBox()
            w.setRange(0, 999)
            w.setValue(int(val or 0))
            w.valueChanged.connect(store)
            return w
        if prop.kind == "choice":
            w = QComboBox()
            w.addItems(list(prop.options))
            w.setCurrentText(str(val))
            w.currentTextChanged.connect(store)
            return w
        if prop.kind == "check":
            w = QCheckBox()
            w.setChecked(bool(val))
            w.toggled.connect(store)
            return w
        w = QLineEdit(str(val or ""))
        w.textChanged.connect(store)
        return w
