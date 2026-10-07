"""Modal editors (QDialog.exec): robust in Qt, used to EDIT structured data.
The permanent regions (top / left / right / bottom) stay the home of the
interface; a dialog opens only to change a set of values and closes."""
from __future__ import annotations

import copy
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import model
from .help import help_button
from .phases import SYSTEMS
from .style import BLUE

KIND_LABEL = {"basement": "Basement", "ground": "Ground", "floor": "Floor"}

#: In every editing table: what can be typed in LOOKS like a field
#: (outline, a lighter fill, blue when typing); what is only information,
#: or worked out, does not.
FIELD_TABLE_CSS = (
    "QTableWidget QDoubleSpinBox, QTableWidget QComboBox { "
    "background: #2c3238; border: 1px solid #56606b; border-radius: 3px; "
    "padding: 1px 6px; margin: 3px 6px; }"
    "QTableWidget QDoubleSpinBox:hover, QTableWidget QComboBox:hover { "
    "border-color: #7a8591; }"
    f"QTableWidget QDoubleSpinBox:focus, QTableWidget QComboBox:focus {{ "
    f"border: 1px solid {BLUE}; background: #333b44; }}"
    "QTableWidget QDoubleSpinBox:disabled { background: transparent; "
    "border: 1px solid transparent; color: #7c848e; }"
    "QTableWidget QRadioButton::indicator { width: 12px; "
    "height: 12px; border-radius: 7px; border: 1px solid #7a8591; "
    "background: #2c3238; }"
    f"QTableWidget QRadioButton::indicator:checked {{ border: 1px "
    f"solid {BLUE}; background: qradialgradient(cx:0.5, cy:0.5, "
    f"radius:0.5, fx:0.5, fy:0.5, stop:0 {BLUE}, stop:0.55 {BLUE}, "
    "stop:0.6 #2c3238, stop:1 #2c3238); }")


def _rule() -> QWidget:
    """A thin horizontal line that sets a section apart."""
    from PySide6.QtWidgets import QFrame
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color: #4a525b;")
    return line


def _with_help(widget: QWidget, topic: str) -> QWidget:
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(widget, 1)
    lay.addWidget(help_button(topic))
    return box


def _show_row(view, items) -> QWidget | None:
    """«Show on the model: ☑ … ☑ …» — what an element's window shows,
    applied at once and ruling over the Settings. ``view`` = (get(name)
    → bool, set(name, on)); items = [(name, label, tip)]."""
    if view is None:
        return None
    from PySide6.QtWidgets import QCheckBox
    get, put = view
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    cap = QLabel("Show on the model:")
    cap.setEnabled(False)
    lay.addWidget(cap)
    for name, label, tip in items:
        c = QCheckBox(label)
        c.setChecked(bool(get(name)))
        c.setToolTip(tip)
        c.toggled.connect(lambda on, n=name: put(n, on))
        lay.addWidget(c)
    lay.addStretch()
    return box


#: windows put back where they were when «Apply» opens them again
_REOPEN: dict[str, object] = {}


def ok_apply(dlg: QDialog, bb: QDialogButtonBox, ok: str = "OK") -> None:
    """«OK» applies and closes; «Apply» applies and keeps the window — it
    is opened again at once, in the same place, with the new values (his
    ask, 2026-10-05: «Apply» used to close it, so every change meant
    opening it again). Apply presses OK itself, so whatever OK runs (a
    window's own checks) runs for both. The caller sees ``dlg.again`` and
    opens it again."""
    from PySide6.QtCore import QTimer
    okb = bb.button(QDialogButtonBox.Ok)
    okb.setText(ok)
    b = bb.addButton("Apply", QDialogButtonBox.ApplyRole)
    b.setToolTip("Apply the changes and keep this window open")
    dlg.again = False

    def go() -> None:
        dlg.again = True
        _REOPEN[type(dlg).__name__] = dlg.geometry()
        okb.click()
        if dlg.isVisible():              # a check said no: nothing applied
            dlg.again = False
            _REOPEN.pop(type(dlg).__name__, None)
    b.clicked.connect(go)
    geo = _REOPEN.pop(type(dlg).__name__, None)
    if geo is not None:                  # once shown (its own sizing first)
        QTimer.singleShot(0, lambda: dlg.isVisible() and dlg.setGeometry(geo))


def hide_button(dlg: QDialog) -> QPushButton:
    """«Hide»: the element out of sight (its changes in the window kept),
    a view change — its eye in the outliner shows it again (his ask,
    2026-10-05). The window closes with action "hide"."""
    b = QPushButton("Hide")
    b.setToolTip("Hide it (a view change, not an undo step) — its eye in "
                 "the outliner shows it again")

    def go() -> None:
        dlg.action = "hide"
        dlg.accept()
    b.clicked.connect(go)
    return b


def _metres(value: float, lo: float, hi: float, step: float = 0.05):
    w = QDoubleSpinBox()
    w.setDecimals(2)
    w.setRange(lo, hi)
    w.setSingleStep(step)
    w.setSuffix(" m")
    w.setValue(value)
    return w


class ProjectDialog(QDialog):
    """New project / Edit project. ``result_data()`` after ``exec()``
    returns (project, levels, system)."""

    def __init__(self, doc: dict, parent=None, tab: str = "project") -> None:
        super().__init__(parent)
        self.is_new = not model.has_project(doc)
        self.project = (copy.deepcopy(doc["project"]) if not self.is_new
                        else model.new_project())
        self.levels = copy.deepcopy(doc["levels"])
        self.system = doc["system"]
        self.setWindowTitle("Start a new project" if self.is_new
                            else "Edit project")
        self.setMinimumSize(560, 470)

        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        title = QLabel("New project" if self.is_new else "Project")
        f = title.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        title.setFont(f)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(help_button("project"))
        lay.addLayout(head)
        if self.is_new:
            intro = QLabel("Fill in what you know — everything can be "
                           "changed later. Nothing is drawn in the model.")
            intro.setWordWrap(True)
            intro.setEnabled(False)
            lay.addWidget(intro)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._project_tab(), "Project")
        levels_tab = self._levels_tab()
        if self.is_new:
            # levels are set up here once; after that they live in the
            # levels strip (N) and each level's own window
            self.tabs.addTab(levels_tab, "Levels")
        else:
            self.proj_form.addRow("Ground floor level",
                                  _with_help(self.f_ground, "ground_level"))
            levels_tab.setParent(self)
            levels_tab.hide()
        self.tabs.addTab(self._docs_tab(), "Documentation")
        order = (["project", "levels", "documentation"] if self.is_new
                 else ["project", "documentation"])
        self.tabs.setCurrentIndex(order.index(tab) if tab in order else 0)
        lay.addWidget(self.tabs, 1)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        if self.is_new:
            bb.button(QDialogButtonBox.Ok).setText("Start project")
            self.again = False
        else:
            ok_apply(self, bb)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    # ---- tabs ------------------------------------------------------------------------
    def _project_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.proj_form = form
        p = self.project
        self.f_name = QLineEdit(p["name"])
        self.f_name.setPlaceholderText("e.g. Silva House")
        form.addRow("Name", self.f_name)
        self.f_client = QLineEdit(p["client"])
        form.addRow("Client", self.f_client)
        self.f_location = QLineEdit(p["location"])
        self.f_location.setPlaceholderText("Address or city")
        form.addRow("Location", self.f_location)
        self.f_author = QLineEdit(p["author"])
        form.addRow("Author", self.f_author)
        self.f_date = QLineEdit(p["date"])
        self.f_date.setPlaceholderText("empty = the day a sheet is exported")
        form.addRow("Date", self.f_date)

        self.f_system = QComboBox()
        for k, label in SYSTEMS.items():
            self.f_system.addItem(label, k)
        self.f_system.setCurrentIndex(self.f_system.findData(self.system))
        form.addRow("Structural system", _with_help(self.f_system, "system"))

        self.f_units = QComboBox()
        self.f_units.addItems(list(model.UNITS))
        self.f_units.model().item(1).setEnabled(False)   # not yet
        self.f_units.setItemData(1, "Coming later", Qt.ToolTipRole)
        self.f_units.setCurrentText(p["units"])
        form.addRow("Units", self.f_units)

        self.f_north = QDoubleSpinBox()
        self.f_north.setRange(-360.0, 360.0)
        self.f_north.setDecimals(1)
        self.f_north.setSuffix("°")
        self.f_north.setValue(float(p["north_deg"]))
        form.addRow("North", _with_help(self.f_north, "north"))
        return w

    def _levels_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        top = QFormLayout()
        self.f_ground = _metres(float(self.project["ground_level"]),
                                -50.0, 50.0, 0.05)
        self.f_ground.valueChanged.connect(self._refresh_elevations)
        top.addRow("Ground floor level", _with_help(self.f_ground,
                                                    "ground_level"))
        lay.addLayout(top)

        head = QHBoxLayout()
        head.addWidget(QLabel("Storeys, top to bottom"))
        head.addStretch()
        head.addWidget(help_button("levels"))
        lay.addLayout(head)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Height", "Elevation", "Type"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in (1, 2, 3):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemChanged.connect(self._on_name_edited)
        self.table.itemSelectionChanged.connect(self._sync_buttons)
        lay.addWidget(self.table, 1)

        row = QHBoxLayout()
        b_up = QPushButton("+ Floor above")
        b_up.clicked.connect(self._add_floor)
        row.addWidget(b_up)
        b_down = QPushButton("+ Basement")
        b_down.clicked.connect(self._add_basement)
        row.addWidget(b_down)
        row.addStretch()
        self.b_remove = QPushButton("Remove")
        self.b_remove.clicked.connect(self._remove)
        row.addWidget(self.b_remove)
        lay.addLayout(row)
        self._fill_table()
        return w

    def _docs_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        p = self.project
        self.f_paper = QComboBox()
        self.f_paper.addItems(list(model.PAPERS))
        self.f_paper.setCurrentText(p["paper"])
        form.addRow("Paper", _with_help(self.f_paper, "documentation"))
        self.f_orient = QComboBox()
        self.f_orient.addItems(["Landscape", "Portrait"])
        self.f_orient.setCurrentText(p["orientation"])
        form.addRow("Orientation", self.f_orient)
        self.f_scale = QComboBox()
        self.f_scale.addItems(list(model.SCALES))
        self.f_scale.setCurrentText(p["scale"])
        form.addRow("Scale", self.f_scale)
        return w

    # ---- levels table ---------------------------------------------------------------
    def _fill_table(self, select: int | None = None) -> None:
        """Rows show top → bottom; self.levels is bottom → top."""
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.levels))
        elev = model.elevations(self.levels, self.f_ground.value())
        n = len(self.levels)
        for row in range(n):
            i = n - 1 - row
            lv = self.levels[i]
            name = QTableWidgetItem(lv["name"])
            name.setData(Qt.UserRole, i)
            self.table.setItem(row, 0, name)
            spin = _metres(lv["height"], model.MIN_HEIGHT, model.MAX_HEIGHT)
            spin.valueChanged.connect(
                lambda v, i=i: self._on_height(i, v))
            self.table.setCellWidget(row, 1, spin)
            e = QTableWidgetItem(f"{elev[i]:+.2f} m")
            e.setFlags(e.flags() & ~Qt.ItemIsEditable)
            e.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, e)
            k = QTableWidgetItem(KIND_LABEL[lv["kind"]])
            k.setFlags(k.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 3, k)
        self.table.blockSignals(False)
        if select is not None:
            self.table.selectRow(n - 1 - select)
        self._sync_buttons()

    def _refresh_elevations(self) -> None:
        elev = model.elevations(self.levels, self.f_ground.value())
        n = len(self.levels)
        self.table.blockSignals(True)
        for row in range(n):
            self.table.item(row, 2).setText(f"{elev[n - 1 - row]:+.2f} m")
        self.table.blockSignals(False)

    def _selected_index(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return len(self.levels) - 1 - rows[0].row()

    def _sync_buttons(self) -> None:
        i = self._selected_index()
        self.b_remove.setEnabled(
            i is not None and self.levels[i]["kind"] != "ground")
        self.b_remove.setToolTip("The ground floor cannot be removed"
                                 if i is not None
                                 and self.levels[i]["kind"] == "ground"
                                 else "Remove the selected storey")

    def _on_name_edited(self, item) -> None:
        if item.column() != 0:
            return
        i = item.data(Qt.UserRole)
        self.levels[i]["name"] = item.text().strip()
        fixed = model.fix_levels(self.levels)        # empty / duplicate
        if [r["name"] for r in fixed] != [r["name"] for r in self.levels]:
            self.levels = fixed
            self._fill_table(select=i)
        else:
            self.levels = fixed

    def _on_height(self, i: int, value: float) -> None:
        self.levels[i]["height"] = round(value, 3)
        self._refresh_elevations()

    def _add_floor(self) -> None:
        from . import prefs
        self.levels = model.add_floor(self.levels, prefs.get("floor_height"))
        self._fill_table(select=len(self.levels) - 1)

    def _add_basement(self) -> None:
        from . import prefs
        self.levels = model.add_basement(self.levels,
                                         prefs.get("floor_height"))
        self._fill_table(select=0)

    def _remove(self) -> None:
        i = self._selected_index()
        if i is None or self.levels[i]["kind"] == "ground":
            return
        del self.levels[i]
        # auto-named storeys renumber themselves
        for r in self.levels:
            if re.fullmatch(r"(Floor|Basement) \d+", r["name"]):
                r["name"] = ""
        self.levels = model.fix_levels(self.levels)
        self._fill_table(select=min(i, len(self.levels) - 1))

    # ---- result ----------------------------------------------------------------------
    def _accept(self) -> None:
        p = self.project
        p["name"] = self.f_name.text().strip() or "Untitled project"
        p["client"] = self.f_client.text().strip()
        p["location"] = self.f_location.text().strip()
        p["author"] = self.f_author.text().strip()
        p["date"] = self.f_date.text().strip()
        p["units"] = self.f_units.currentText()
        p["north_deg"] = round(self.f_north.value(), 1)
        p["ground_level"] = round(self.f_ground.value(), 3)
        p["paper"] = self.f_paper.currentText()
        p["orientation"] = self.f_orient.currentText()
        p["scale"] = self.f_scale.currentText()
        self.system = self.f_system.currentData()
        self.levels = model.fix_levels(self.levels)
        self.accept()

    def result_data(self) -> tuple[dict, list[dict], str]:
        return self.project, self.levels, self.system


class SettingsDialog(QDialog):
    """ArchXQ preferences (the user's, for every project)."""

    def __init__(self, parent=None, placement: str = "viewport") -> None:
        from PySide6.QtWidgets import QCheckBox
        from . import prefs
        super().__init__(parent)
        self.placement = placement
        self.setWindowTitle("ArchXQ settings")
        self.setMinimumSize(480, 330)
        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        title = QLabel("Settings")
        f = title.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        title.setFont(f)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(help_button("settings"))
        lay.addLayout(head)
        note = QLabel("Yours, for every project — not saved in the file.")
        note.setEnabled(False)
        lay.addWidget(note)

        tabs = QTabWidget()
        disp = QWidget()
        form = QFormLayout(disp)
        self.f_place = QComboBox()
        self.f_place.addItem("In the 3D view", "viewport")
        self.f_place.addItem("In the program's toolbars", "toolbar")
        self.f_place.setCurrentIndex(max(0, self.f_place.findData(placement)))
        form.addRow("ArchXQ bars", self.f_place)
        self.f_dims = QComboBox()
        for k, label in prefs.PLOT_DIMS.items():
            self.f_dims.addItem(label, k)
        self.f_dims.setCurrentIndex(self.f_dims.findData(prefs.get("plot_dims")))
        form.addRow("Plot dimensions", _with_help(self.f_dims, "plot_dims"))
        self.f_live = QCheckBox("Show lengths while drawing")
        self.f_live.setChecked(prefs.get("live_dims"))
        form.addRow("Live measurements", self.f_live)
        self.f_diag = QCheckBox("Pull the cursor onto 45°")
        self.f_diag.setChecked(prefs.get("diag_pull"))
        form.addRow("Diagonals", self.f_diag)
        self.f_plan = QCheckBox("Switch to plan view when a drawing tool "
                                "starts")
        self.f_plan.setChecked(prefs.get("plan_on_tool"))
        form.addRow("Plan view", self.f_plan)
        self.f_plan_hl = QCheckBox("Show the plan in Hidden Line")
        self.f_plan_hl.setChecked(prefs.get("plan_hidden_line"))
        form.addRow("", self.f_plan_hl)
        self.f_grid = QCheckBox("A grid and the red / green axes in the plan")
        self.f_grid.setChecked(prefs.get("plan_grid"))
        form.addRow("", self.f_grid)
        self.f_warn_sb = QCheckBox("When an excavation enters the setbacks")
        self.f_warn_sb.setChecked(prefs.get("warn_setbacks"))
        form.addRow("Warn me", self.f_warn_sb)
        tabs.addTab(disp, "Display")

        dflt = QWidget()
        form2 = QFormLayout(dflt)
        self.f_ground = _metres(prefs.get("ground_thickness"), 0.05, 20.0)
        form2.addRow("Ground thickness", _with_help(self.f_ground,
                                                    "ground_thickness"))
        self.f_floor = _metres(prefs.get("floor_height"), model.MIN_HEIGHT,
                               model.MAX_HEIGHT)
        form2.addRow("New floor height", self.f_floor)
        tabs.addTab(dflt, "Defaults")
        lay.addWidget(tabs, 1)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel
                              | QDialogButtonBox.RestoreDefaults)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.RestoreDefaults).clicked.connect(
            self._defaults)
        lay.addWidget(bb)

    def _defaults(self) -> None:
        from . import prefs
        d = {k: v[0] for k, v in prefs.DEFAULTS.items()}
        self.f_dims.setCurrentIndex(self.f_dims.findData(d["plot_dims"]))
        self.f_live.setChecked(d["live_dims"])
        self.f_diag.setChecked(d["diag_pull"])
        self.f_plan.setChecked(d["plan_on_tool"])
        self.f_plan_hl.setChecked(d["plan_hidden_line"])
        self.f_grid.setChecked(d["plan_grid"])
        self.f_warn_sb.setChecked(d["warn_setbacks"])
        self.f_ground.setValue(d["ground_thickness"])
        self.f_floor.setValue(d["floor_height"])

    def _accept(self) -> None:
        from . import prefs
        prefs.put("plot_dims", self.f_dims.currentData())
        prefs.put("live_dims", self.f_live.isChecked())
        prefs.put("diag_pull", self.f_diag.isChecked())
        prefs.put("plan_on_tool", self.f_plan.isChecked())
        prefs.put("plan_hidden_line", self.f_plan_hl.isChecked())
        prefs.put("plan_grid", self.f_grid.isChecked())
        prefs.put("warn_setbacks", self.f_warn_sb.isChecked())
        prefs.put("ground_thickness", round(self.f_ground.value(), 3))
        prefs.put("floor_height", round(self.f_floor.value(), 3))
        self.placement = self.f_place.currentData()
        self.accept()


class PlotDialog(QDialog):
    """The plot by its sides — the surveyor's table. One row per corner:
    its height and inside angle, then the side leaving it and that side's
    length. Typing each side's length once gives the exact outline: the
    CLOSING side (dashed on the model) and the side before it swing on
    their shared corner to close. ``preview((corners, heights, closing))``
    is called on every change; ``result_data()`` after ``exec()``."""

    COLS = ("Corner", "Height", "Angle", "Side", "Length", "Closing")

    def __init__(self, plot: dict, parent=None, preview=None,
                 view=None) -> None:
        from PySide6.QtWidgets import QButtonGroup
        super().__init__(parent)
        self.pts = [list(p) for p in plot["corners"]]
        self.heights = list(plot["heights"])
        self.closing = int(plot["closing"])
        self.preview = preview or (lambda _p: None)
        self.setWindowTitle("Edit plot")
        self.setMinimumSize(620, 420)

        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        title = QLabel("Plot — sides and heights")
        f = title.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        title.setFont(f)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(help_button("plot_table"))
        lay.addLayout(head)
        intro = QLabel("Type the length of each side, in order — the "
                       "closing side (dashed) adjusts to close the plot. "
                       "Angles come from your drawing; set one only if the "
                       "deed gives it.")
        intro.setWordWrap(True)
        intro.setEnabled(False)
        lay.addWidget(intro)
        show = _show_row(view, [
            ("plot_dims", "Plot dimensions",
             "The length of every side of the plot — chosen here, it "
             "rules over the Settings"),
            ("plot_elev_dims", "Plot elevations",
             "The ground's elevation at every corner (the heights you "
             "type here)"),
            ("survey_dims", "Survey points",
             "The measured ground points inside the plot, with their "
             "elevations"),
            ("contour_dims", "Contours",
             "The ground's contour lines (their step: Survey points › "
             "Points & import…)")])
        if show is not None:
            lay.addWidget(show)

        n = len(self.pts)
        self.table = QTableWidget(n, len(self.COLS))
        self.table.setHorizontalHeaderLabels(list(self.COLS))
        hh = self.table.horizontalHeader()
        for c in range(len(self.COLS)):
            hh.setSectionResizeMode(c, QHeaderView.Stretch if c in (1, 2, 4)
                                    else QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        # what can be typed in LOOKS like a field (outline, lighter);
        # what is only information (and the worked-out angles) does not
        self.table.setStyleSheet(FIELD_TABLE_CSS)
        # no row painting: the field's blue outline + the model are enough
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.active: int | None = None   # the row lit on the model
        self.table.currentCellChanged.connect(
            lambda row, *_: self._set_active(row))
        self.group = QButtonGroup(self)
        self.f_h, self.f_a, self.f_l = [], [], []
        for i in range(n):
            self.table.setItem(i, 0, self._fixed(str(i + 1)))
            h = self._spin(-100.0, 100.0, 0.05, " m", 2)
            h.valueChanged.connect(lambda v, i=i: self._on_height(i, v))
            self.f_h.append(h)
            self.table.setCellWidget(i, 1, h)
            a = self._spin(1.0, 359.0, 1.0, "°", 2)
            a.valueChanged.connect(lambda v, i=i: self._on_angle(i, v))
            self.f_a.append(a)
            self.table.setCellWidget(i, 2, a)
            self.table.setItem(i, 3, self._fixed(f"{i + 1} → {(i + 1) % n + 1}"))
            ln = self._spin(0.01, 100000.0, 0.05, " m", 2)
            ln.valueChanged.connect(lambda v, i=i: self._on_length(i, v))
            self.f_l.append(ln)
            self.table.setCellWidget(i, 4, ln)
            from PySide6.QtWidgets import QRadioButton
            rb = QRadioButton()
            rb.setToolTip("This side adjusts to close the plot")
            # entering a field lights its row; a click selects the whole
            # value, so typing replaces it (no deleting digit by digit)
            for w in (h, a, ln, ln.lineEdit(), h.lineEdit(), a.lineEdit(),
                      rb):
                w.setProperty("axq_row", i)
                w.installEventFilter(self)
            self.group.addButton(rb, i)
            cell = QWidget()
            cl = QHBoxLayout(cell)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setAlignment(Qt.AlignCenter)
            cl.addWidget(rb)
            self.table.setCellWidget(i, 5, cell)
        self.group.button(self.closing).setChecked(True)
        self.group.idClicked.connect(self._on_closing)
        lay.addWidget(self.table, 1)

        self.status = QLabel()
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_apply(self, bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        # where the hand looks for it (his ask, 2026-10-05) — ui asks first
        self.action = "apply"
        dele = bb.addButton("Delete plot", QDialogButtonBox.ResetRole)
        dele.setToolTip("Delete the plot (and its excavations and fills) — "
                        "it asks first; Ctrl+Z brings it back")
        dele.clicked.connect(self._delete)
        lay.addWidget(bb)
        self.gap = 0.0
        self._fill()

    # ---- widgets ---------------------------------------------------------------
    @staticmethod
    def _fixed(text: str) -> QTableWidgetItem:
        it = QTableWidgetItem(text)
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        it.setTextAlignment(Qt.AlignCenter)
        return it

    @staticmethod
    def _spin(lo, hi, step, suffix, decimals):
        w = QDoubleSpinBox()
        w.setDecimals(decimals)
        w.setRange(lo, hi)
        w.setSingleStep(step)
        w.setSuffix(suffix)
        w.setKeyboardTracking(False)   # changes on Enter / leaving / wheel
        w.setFrame(False)
        w.setButtonSymbols(QDoubleSpinBox.NoButtons)
        return w

    def _fill(self) -> None:
        from . import plotgeo
        L = plotgeo.side_lengths(self.pts)
        A = plotgeo.interior_angles(self.pts)
        free = plotgeo.free_angles(len(self.pts), self.closing)
        for i in range(len(self.pts)):
            for w, v in ((self.f_h[i], self.heights[i]), (self.f_a[i], A[i]),
                         (self.f_l[i], L[i])):
                w.blockSignals(True)
                w.setValue(v)
                w.blockSignals(False)
            self.f_a[i].setEnabled(i in free)
            self.f_a[i].setToolTip("" if i in free else
                                   "Worked out to close the plot")
        area = plotgeo.area(self.pts)
        text = (f"Area {area:,.2f} m²   ·   perimeter "
                f"{plotgeo.perimeter(self.pts):,.2f} m")
        if self.gap > 0.005:
            text += (f"<br><span style='color:#e5484d'>These lengths cannot "
                     f"close: the closing side is {self.gap:.2f} m off. Check "
                     "the lengths (or set an angle).</span>")
        self.status.setText(text)
        self._send_preview()

    def _send_preview(self) -> None:
        self.preview((self.pts, self.heights, self.closing, self.active))

    def _set_active(self, row) -> None:
        row = row if row is not None and 0 <= row < len(self.pts) else None
        if row == self.active:
            return
        self.active = row
        self._send_preview()

    def eventFilter(self, obj, event) -> bool:
        from PySide6.QtCore import QEvent, QTimer
        from PySide6.QtWidgets import QLineEdit
        kind = event.type()
        if kind in (QEvent.FocusIn, QEvent.MouseButtonPress,
                    QEvent.MouseButtonRelease):
            row = obj.property("axq_row")
            if row is not None:
                self._set_active(int(row))
            # after Qt has placed the cursor for the click, select it all
            spin = obj.parent() if isinstance(obj, QLineEdit) else obj
            if isinstance(spin, QDoubleSpinBox) and kind != \
                    QEvent.MouseButtonPress:
                QTimer.singleShot(0, spin.selectAll)
        return False

    # ---- edits ---------------------------------------------------------------------
    def _apply(self, pts, gap) -> None:
        from . import plotgeo
        reason = plotgeo.why_not(pts)
        if reason:
            self.status.setText(f"<span style='color:#e5484d'>{reason} — "
                                "change not made.</span>")
            self._fill_values_only()
            return
        self.pts, self.gap = pts, gap
        self._fill()

    def _fill_values_only(self) -> None:
        """Put the spins back to the current outline (a refused change)."""
        msg = self.status.text()
        self._fill()
        self.status.setText(msg)

    def _on_length(self, side: int, value: float) -> None:
        from . import plotgeo
        self._apply(*plotgeo.set_length(self.pts, side, value, self.closing))

    def _on_angle(self, corner: int, value: float) -> None:
        from . import plotgeo
        self._apply(*plotgeo.set_angle(self.pts, corner, value, self.closing))

    def _on_height(self, corner: int, value: float) -> None:
        self.heights[corner] = round(value, 3)
        self._fill()

    def _on_closing(self, side: int) -> None:
        self.closing = side
        self.gap = 0.0
        self._fill()

    def result_data(self):
        return self.pts, self.heights, self.closing

    def _delete(self) -> None:
        """Closes with «delete»: ui asks, then takes the plot away."""
        self.action = "delete"
        self.accept()


class LevelDialog(QDialog):
    """One level's own window: its name and height (elevation worked out),
    a level above / below it, and deleting it — never the ground floor,
    never a level with anything on it. ``result_data()`` after ``exec()``
    → (action, name, height); action: "apply" | "above" | "below" |
    "delete"."""

    def __init__(self, doc: dict, index: int, content: int,
                 parent=None, on_show=None) -> None:
        super().__init__(parent)
        self.levels = copy.deepcopy(doc["levels"])
        self.index = index
        self.ground_level = (doc["project"]["ground_level"]
                             if model.has_project(doc) else 0.0)
        self.action = "apply"
        lv = self.levels[index]
        self.setWindowTitle("Level")
        self.setMinimumWidth(440)

        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        title = QLabel(lv["name"])
        f = title.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        title.setFont(f)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(help_button("level"))
        lay.addLayout(head)

        form = QFormLayout()
        self.f_name = QLineEdit(lv["name"])
        form.addRow("Name", self.f_name)
        self.f_height = _metres(lv["height"], model.MIN_HEIGHT,
                                model.MAX_HEIGHT)
        self.f_height.valueChanged.connect(self._refresh)
        form.addRow("Height", _with_help(self.f_height, "level_height"))
        # worked out / information: plain text, no field look
        self.l_elev = QLabel()
        form.addRow("Elevation", self.l_elev)
        form.addRow("Type", QLabel(KIND_LABEL[lv["kind"]] + (
            " floor" if lv["kind"] == "ground" else "")))
        form.addRow("Contains", QLabel(
            "nothing yet" if content == 0 else
            f"{content} object" + ("s" if content > 1 else "")))
        lay.addLayout(form)

        # «Show» — a section of its own, set apart by rules above and below:
        # this level's parts on / off, RIGHT AWAY (a view change: no undo,
        # Cancel keeps it — like the levels' eye)
        if on_show is not None:
            lay.addSpacing(6)
            lay.addWidget(_rule())
            cap = QHBoxLayout()
            t = QLabel("Show")
            ft = t.font()
            ft.setBold(True)
            t.setFont(ft)
            cap.addWidget(t)
            note = QLabel("on this level — changes the view right away")
            note.setEnabled(False)
            cap.addWidget(note)
            cap.addStretch()
            lay.addLayout(cap)
            lay.addLayout(self._show_grid(
                set((doc.get("hidden_parts") or {}).get(lv["id"], ())),
                on_show))
            lay.addWidget(_rule())
            lay.addSpacing(6)

        acts = QHBoxLayout()
        g = next(i for i, r in enumerate(self.levels) if r["kind"] == "ground")
        b_up = QPushButton("+ Level above")
        b_up.clicked.connect(lambda: self._done("above"))
        acts.addWidget(b_up)
        b_down = QPushButton("+ Basement below" if index <= g
                             else "+ Level below")
        b_down.clicked.connect(lambda: self._done("below"))
        acts.addWidget(b_down)
        acts.addStretch()
        self.b_del = QPushButton("Delete level")
        if lv["kind"] == "ground":
            self.b_del.setEnabled(False)
            self.b_del.setToolTip("The ground floor always stays")
        elif content:
            self.b_del.setEnabled(False)
            self.b_del.setToolTip("This level has objects on it — move or "
                                  "delete them first")
        self.b_del.clicked.connect(self._delete)
        acts.addWidget(self.b_del)
        lay.addLayout(acts)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_apply(self, bb)
        bb.accepted.connect(lambda: self._done("apply"))
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._refresh()

    def _show_grid(self, off: set, on_show):
        """Two rows of three ticks; each change goes out at once."""
        from PySide6.QtWidgets import QCheckBox, QGridLayout
        grid = QGridLayout()
        grid.setContentsMargins(12, 2, 0, 4)
        grid.setHorizontalSpacing(18)
        self.f_show = {}
        for n, (key, label, _kinds) in enumerate(model.LEVEL_PARTS):
            c = QCheckBox(label)
            c.setChecked(key not in off)
            c.toggled.connect(lambda _on: on_show(
                {k for k, box in self.f_show.items() if not box.isChecked()}))
            self.f_show[key] = c
            grid.addWidget(c, n // 3, n % 3)
        grid.setColumnStretch(3, 1)
        return grid

    def _refresh(self) -> None:
        levels = copy.deepcopy(self.levels)
        levels[self.index]["height"] = self.f_height.value()
        z = model.elevations(levels, self.ground_level)[self.index]
        self.l_elev.setText("±0.00 m" if abs(z) < 0.005 else f"{z:+.2f} m")

    def _delete(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        name = self.levels[self.index]["name"]
        if QMessageBox.question(
                self, "Delete level?",
                f"Delete «{name}»? The levels above and below close the gap "
                "(Ctrl+Z brings it back).",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel) == QMessageBox.Yes:
            self._done("delete")

    def _done(self, action: str) -> None:
        self.action = action
        self.accept()

    def result_data(self):
        name = self.f_name.text().strip() or self.levels[self.index]["name"]
        return self.action, name, round(self.f_height.value(), 3)


class WallDialog(QDialog):
    """One wall's own window: name, thickness, alignment, which side its
    inside is, height (the level's, or its own), base; the length of a
    straight wall (stretched from its end); delete. ``result_data()``
    after ``exec()`` → (action, wall) — action "apply" | "delete"."""

    ALIGNS = (("outside", "Outside — its outer face on the line drawn"),
              ("centre", "Centre — on the line drawn"),
              ("inside", "Inside — its inner face on the line drawn"))

    def __init__(self, wall: dict, level: dict, parent=None) -> None:
        from PySide6.QtWidgets import QCheckBox
        from . import walls as W
        super().__init__(parent)
        self.wall = copy.deepcopy(wall)
        self.level = level
        self.action = "apply"
        kind = wall.get("kind", "line")
        self.setWindowTitle("Wall")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        title = QLabel(wall["name"])
        f = title.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        title.setFont(f)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(help_button("wall"))
        lay.addLayout(head)

        form = QFormLayout()
        self.f_name = QLineEdit(wall["name"])
        form.addRow("Name", self.f_name)
        self.f_t = _metres(wall["t"], 0.05, 3.0, 0.01)
        self.f_t.valueChanged.connect(self._refresh)
        form.addRow("Thickness", self.f_t)
        self.f_align = QComboBox()
        for v, text in self.ALIGNS:
            self.f_align.addItem(text, v)
        self.f_align.setCurrentIndex(self.f_align.findData(wall["align"]))
        form.addRow("Alignment", self.f_align)
        self.f_flip = QCheckBox("Inside on the other side of the line")
        self.f_flip.setToolTip("Which side of the line drawn is the "
                               "building's inside — it decides where "
                               "«Outside» / «Inside» put the wall")
        if kind == "circle":
            self.f_flip.setEnabled(False)
            self.f_flip.setToolTip("A round wall's inside is its centre")
        form.addRow("Side", self.f_flip)
        self.f_hmode = QComboBox()
        self.f_hmode.addItem(f"Level height ({level['height']:.2f} m)",
                             "level")
        self.f_hmode.addItem("Its own height", "own")
        own = wall.get("height", "level") != "level"
        self.f_hmode.setCurrentIndex(1 if own else 0)
        self.f_h = _metres(float(wall["height"]) if own else level["height"],
                           0.10, 30.0)
        self.f_h.setEnabled(own)
        self.f_hmode.currentIndexChanged.connect(
            lambda i: (self.f_h.setEnabled(i == 1), self._refresh()))
        self.f_h.valueChanged.connect(self._refresh)
        hrow = QWidget()
        hl = QHBoxLayout(hrow)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(self.f_hmode, 1)
        hl.addWidget(self.f_h)
        form.addRow("Height", hrow)
        self.f_base = _metres(float(wall.get("base", 0.0)), -10.0, 10.0)
        self.f_base.setToolTip("Up or down from the level's floor")
        form.addRow("Base offset", self.f_base)
        self.length0 = W.drawn(wall).L if kind != "circle" else 0.0
        self.f_ends = None
        if kind == "line":
            self.f_len = _metres(self.length0, 0.05, 1000.0)
            self.f_len.setToolTip("Stretched or shortened from its end "
                                  "point (the start stays)")
            self.f_len.valueChanged.connect(self._on_length)
            form.addRow("Length", self.f_len)
            # where it starts and ends, typed (a customer's ask, 2026-10-05:
            # «I can only change its properties, not where it starts or
            # ends») — kept in step with Length
            self.f_ends = {}
            for end, label in (("a", "Start"), ("b", "End")):
                row = QWidget()
                rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 0, 0, 0)
                for k, axis in enumerate(("X", "Y")):
                    s = _metres(float(wall[end][k]), -100000.0, 100000.0, 0.05)
                    s.valueChanged.connect(self._on_ends)
                    rl.addWidget(QLabel(axis))
                    rl.addWidget(s, 1)
                    self.f_ends[(end, k)] = s
                form.addRow(label, row)
        else:
            self.f_len = None
            form.addRow("Length" if kind == "arc" else "Radius",
                        QLabel(f"{self.length0:.2f} m" if kind == "arc"
                               else f"{wall['r']:.2f} m"))
        # information: plain text, no field look
        form.addRow("Level", QLabel(level["name"]))
        form.addRow("Type", QLabel({"line": "Straight", "arc": "Curved",
                                    "circle": "Round"}[kind]))
        self.l_area = QLabel()
        form.addRow("Face area", self.l_area)
        lay.addLayout(form)

        acts = QHBoxLayout()
        acts.addStretch()
        acts.addWidget(hide_button(self))
        b_del = QPushButton("Delete wall")
        b_del.clicked.connect(self._delete)
        acts.addWidget(b_del)
        lay.addLayout(acts)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_apply(self, bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._refresh()

    def _height(self) -> float:
        return self.f_h.value() if self.f_hmode.currentIndex() == 1 \
            else float(self.level["height"])

    def _end_pt(self, end: str) -> list[float]:
        return [self.f_ends[(end, 0)].value(), self.f_ends[(end, 1)].value()]

    def _on_ends(self, *_a) -> None:
        """Start / End typed: the Length follows."""
        import math
        L = math.dist(self._end_pt("a"), self._end_pt("b"))
        self.f_len.blockSignals(True)
        self.f_len.setValue(max(L, 0.05))
        self.f_len.blockSignals(False)
        self._refresh()

    def _on_length(self, *_a) -> None:
        """Length typed: the End moves along the wall (the Start stays)."""
        import math
        if self.f_ends:
            a, b = self._end_pt("a"), self._end_pt("b")
            L0 = math.dist(a, b)
            if L0 > 1e-9:
                k = self.f_len.value() / L0
                for i in (0, 1):
                    s = self.f_ends[("b", i)]
                    s.blockSignals(True)
                    s.setValue(a[i] + (b[i] - a[i]) * k)
                    s.blockSignals(False)
        self._refresh()

    def _refresh(self) -> None:
        import math
        kind = self.wall.get("kind", "line")
        if kind == "circle":
            L = 2 * math.pi * float(self.wall["r"])
        elif self.f_len is not None:
            L = self.f_len.value()
        else:
            L = self.length0
        self.l_area.setText(f"{L * self._height():.2f} m²  (one face)")

    def _delete(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, "Delete wall?",
                f"Delete «{self.wall['name']}»? The walls it met join again "
                "without it (Ctrl+Z brings it back).",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel) == QMessageBox.Yes:
            self.action = "delete"
            self.accept()

    def result_data(self):
        w = dict(self.wall)
        w["name"] = self.f_name.text().strip() or self.wall["name"]
        w["t"] = round(self.f_t.value(), 3)
        w["align"] = self.f_align.currentData()
        if self.f_flip.isEnabled() and self.f_flip.isChecked():
            w["side"] = -int(self.wall.get("side", 1))
        w["height"] = "level" if self.f_hmode.currentIndex() == 0 \
            else round(self.f_h.value(), 3)
        w["base"] = round(self.f_base.value(), 3)
        if self.f_ends:              # Start / End (Length is kept in step)
            # a coordinate counts as changed only if it differs from what
            # the field SHOWED (2 decimals): opening and pressing OK must
            # never move a wall by the rounding
            for end in ("a", "b"):
                w[end] = [round(v, 4) if abs(v - round(o, 2)) > 1e-4 else o
                          for v, o in zip(self._end_pt(end), self.wall[end])]
        elif self.f_len is not None and \
                abs(self.f_len.value() - self.length0) > 1e-4:
            a, b = w["a"], w["b"]
            k = self.f_len.value() / max(self.length0, 1e-9)
            w["b"] = [round(a[0] + (b[0] - a[0]) * k, 4),
                      round(a[1] + (b[1] - a[1]) * k, 4)]
        return self.action, w


class ElementDialog(QDialog):
    """A structural element's own window — a column, a beam, a slab, a
    footing: its name and sizes (the fields its type has), what it is and
    where; delete. ``result_data()`` after ``exec()`` → (action, element)
    — action "apply" | "delete"."""

    def __init__(self, el: dict, level: dict, parent=None) -> None:
        import math
        from . import structure as S
        super().__init__(parent)
        self.el = copy.deepcopy(el)
        self.action = "apply"
        t = el["type"]
        label = S.LABEL[t]
        self.setWindowTitle(label)
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        title = QLabel(el["name"])
        f = title.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        title.setFont(f)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(help_button(t))
        lay.addLayout(head)

        form = QFormLayout()
        self.f_name = QLineEdit(el["name"])
        form.addRow("Name", self.f_name)
        self.fields: dict = {}

        def metres(key, label_, lo, hi, step=0.05, suffix=" m"):
            w = _metres(float(el[key]), lo, hi, step)
            w.setSuffix(suffix)
            self.fields[key] = w
            form.addRow(label_, w)

        if t == "column":
            self.f_section = QComboBox()
            self.f_section.addItem("Rectangle", "rect")
            self.f_section.addItem("Round", "round")
            self.f_section.setCurrentIndex(1 if el["shape"] == "round" else 0)
            form.addRow("Section", self.f_section)
            metres("w", "Width / Ø", 0.05, 5.0)
            metres("d", "Depth", 0.05, 5.0)
            metres("angle", "Angle", -180.0, 180.0, 15.0, "°")
            self.f_hmode = QComboBox()
            self.f_hmode.addItem("To the slab above", "level")
            self.f_hmode.addItem("Its own height", "own")
            own = el.get("height", "level") != "level"
            self.f_hmode.setCurrentIndex(1 if own else 0)
            self.f_h = _metres(float(el["height"]) if own else 3.0, 0.2,
                               50.0)
            self.f_h.setEnabled(own)
            self.f_hmode.currentIndexChanged.connect(
                lambda i: self.f_h.setEnabled(i == 1))
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.addWidget(self.f_hmode, 1)
            rl.addWidget(self.f_h)
            form.addRow("Height", row)
        elif t == "beam":
            metres("w", "Width", 0.05, 3.0)
            metres("h", "Height", 0.05, 5.0)
            form.addRow("Length", QLabel(
                f"{math.dist(el['a'], el['b']):.2f} m"))
        elif t == "slab":
            metres("t", "Thickness", 0.02, 3.0, 0.01)
            metres("offset", "Top (from the floor)", -2.0, 2.0, 0.01)
            area = abs(S._area(el["corners"])) - sum(
                abs(S._area(h)) for h in el.get("holes") or [])
            form.addRow("Area", QLabel(f"{area:.2f} m²"))
            auto = (el.get("auto") or {}).get("dig")
            if auto:                    # made by ArchXQ (autoslabs)
                note = QLabel("Automatic — it follows its excavation's "
                              "outline. Delete it and it stays away (Ctrl+Z "
                              "brings it back).")
                note.setWordWrap(True)
                note.setEnabled(False)
                form.addRow("Made", note)
            n = len(el.get("holes") or [])
            self.f_clear = None
            if n:
                from PySide6.QtWidgets import QCheckBox
                self.f_clear = QCheckBox(f"Close its {n} opening"
                                         + ("s" if n > 1 else ""))
                form.addRow("Openings", self.f_clear)
        elif t == "roof":
            self.f_kind = QComboBox()
            for k, text in (("gable", "Gable"), ("hip", "Hip"),
                            ("flat", "Flat")):
                self.f_kind.addItem(text, k)
            self.f_kind.setCurrentIndex(("gable", "hip", "flat").index(
                el["kind"]))
            form.addRow("Type", self.f_kind)
            metres("slope", "Slope", 5.0, 75.0, 5.0, "°")
            metres("overhang", "Overhang", 0.0, 3.0)
            metres("t", "Thickness", 0.02, 1.0, 0.01)
            self.f_ridge = QComboBox()
            self.f_ridge.addItem("Along the long side", "long")
            self.f_ridge.addItem("Along the short side", "short")
            self.f_ridge.setCurrentIndex(0 if el["ridge"] == "long" else 1)
            form.addRow("Ridge (gable)", self.f_ridge)
            metres("parapet", "Parapet (flat)", 0.0, 3.0)
            form.addRow("Covers", QLabel(
                f"{abs(S._area(el['corners'])):.2f} m² (without the eaves)"))
        else:                                     # footing
            metres("w", "Width", 0.1, 10.0)
            metres("d", "Depth", 0.05, 5.0)
            form.addRow("Kind", QLabel("Pad (under a column)"
                                       if el.get("kind") == "pad"
                                       else "Strip (under a wall)"))
        form.addRow("Level", QLabel(level["name"]))
        lay.addLayout(form)

        acts = QHBoxLayout()
        acts.addStretch()
        acts.addWidget(hide_button(self))
        b_del = QPushButton(f"Delete {label.lower()}")
        b_del.clicked.connect(self._delete)
        acts.addWidget(b_del)
        lay.addLayout(acts)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_apply(self, bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _delete(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, "Delete?", f"Delete «{self.el['name']}»? (Ctrl+Z "
                "brings it back)", QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel) == QMessageBox.Yes:
            self.action = "delete"
            self.accept()

    def result_data(self):
        e = dict(self.el)
        e["name"] = self.f_name.text().strip() or self.el["name"]
        for key, w in self.fields.items():
            e[key] = round(w.value(), 3)
        if e["type"] == "column":
            e["shape"] = self.f_section.currentData()
            e["height"] = "level" if self.f_hmode.currentIndex() == 0 \
                else round(self.f_h.value(), 3)
        if e["type"] == "roof":
            e["kind"] = self.f_kind.currentData()
            e["ridge"] = self.f_ridge.currentData()
        if e["type"] == "slab" and getattr(self, "f_clear", None) is not None \
                and self.f_clear.isChecked():
            e["holes"] = []
        return self.action, e


class RoomsDialog(QDialog):
    """The rooms of a level, found from its walls: a name for each (the
    area and perimeter are read). ``result_data()`` → ([(room, name)…],
    same_on_others: bool)."""

    def __init__(self, rooms: list[dict], level: dict, gross: float,
                 parent=None) -> None:
        from PySide6.QtWidgets import QCheckBox
        super().__init__(parent)
        self.rooms = rooms
        self.setWindowTitle("Rooms")
        self.setMinimumSize(460, 420)
        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        title = QLabel(f"Rooms — {level['name']}")
        f = title.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        title.setFont(f)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(help_button("rooms"))
        lay.addLayout(head)
        self.table = QTableWidget(len(rooms), 3)
        self.table.setHorizontalHeaderLabels(["Name", "Area", "Perimeter"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        for i, r in enumerate(rooms):
            self.table.setItem(i, 0, QTableWidgetItem(r["name"]))
            for j, v in ((1, f"{r['area']:.2f} m²"),
                         (2, f"{r['perimeter']:.2f} m")):
                it = QTableWidgetItem(v)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, j, it)
        lay.addWidget(self.table, 1)
        net = sum(r["area"] for r in rooms)
        lay.addWidget(QLabel(f"Net {net:.2f} m²   ·   Gross {gross:.2f} m² "
                             "(to the walls' outer faces)"))
        self.f_same = QCheckBox("The same names on the other levels where "
                                "these rooms are")
        self.f_same.setChecked(True)
        self.f_same.setToolTip("Typical floors: a room of another level that "
                               "holds this room's label point takes its name "
                               "(if it has none of its own yet)")
        lay.addWidget(self.f_same)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_apply(self, bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def result_data(self):
        names = [(r, (self.table.item(i, 0).text() or "").strip())
                 for i, r in enumerate(self.rooms)]
        return names, self.f_same.isChecked()


class OpeningDialog(QDialog):
    """A door's / window's / void's own window: name, width, height, sill
    (a window, a void), hinge (a door), where along its wall; delete.
    ``result_data()`` → (action, opening) — "apply" | "delete"."""

    def __init__(self, op: dict, wall: dict, parent=None) -> None:
        from . import structure as S
        from . import walls as W
        super().__init__(parent)
        self.op = copy.deepcopy(op)
        self.action = "apply"
        label = S.OPENING_LABEL[op["kind"]]
        self.setWindowTitle(label)
        self.setMinimumWidth(400)
        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        title = QLabel(op["name"])
        f = title.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        title.setFont(f)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(help_button(op["kind"]))
        lay.addLayout(head)
        form = QFormLayout()
        self.f_name = QLineEdit(op["name"])
        form.addRow("Name", self.f_name)
        self.f_w = _metres(op["w"], 0.2, 20.0)
        form.addRow("Width", self.f_w)
        self.f_h = _metres(op["h"], 0.2, 20.0)
        form.addRow("Height", self.f_h)
        self.f_sill = None
        if op["kind"] != "door":
            self.f_sill = _metres(op.get("sill", 0.0), 0.0, 20.0)
            form.addRow("Sill (from the floor)", self.f_sill)
        self.f_swing = None
        if op["kind"] == "door":
            self.f_swing = QComboBox()
            self.f_swing.addItem("Left", "left")
            self.f_swing.addItem("Right", "right")
            self.f_swing.setCurrentIndex(0 if op.get("swing") != "right"
                                         else 1)
            form.addRow("Hinge", self.f_swing)
        L = W.drawn(wall).L
        self.f_pos = _metres(op["pos"], 0.0, max(L, 0.1))
        self.f_pos.setToolTip("Its centre, from the start of the wall")
        form.addRow("Along the wall", self.f_pos)
        form.addRow("Wall", QLabel(f"{wall['name']}  ({L:.2f} m)"))
        lay.addLayout(form)
        acts = QHBoxLayout()
        acts.addStretch()
        b_del = QPushButton(f"Delete {label.lower()}")
        b_del.clicked.connect(self._delete)
        acts.addWidget(b_del)
        lay.addLayout(acts)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_apply(self, bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _delete(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, "Delete?", f"Delete «{self.op['name']}»? The wall "
                "closes (Ctrl+Z opens it again)",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel) == QMessageBox.Yes:
            self.action = "delete"
            self.accept()

    def result_data(self):
        o = dict(self.op)
        o["name"] = self.f_name.text().strip() or self.op["name"]
        o["w"] = round(self.f_w.value(), 3)
        o["h"] = round(self.f_h.value(), 3)
        o["pos"] = round(self.f_pos.value(), 3)
        if self.f_sill is not None:
            o["sill"] = round(self.f_sill.value(), 3)
        if self.f_swing is not None:
            o["swing"] = self.f_swing.currentData()
        return self.action, o


class SetbacksDialog(QDialog):
    """The plot's setbacks in detail. On top, the distance of each role
    (front / back / sides); a row per side: its length, its ROLE (a front
    is marked here or by clicking the side; back / side are worked out,
    or chosen by hand) and its SETBACK (typed = that side's own; ↺ gives it
    back its role's). The buildable area below, live; the model previews
    every change, the row you are on lit. ``result_data()`` →
    (sb_front, sb_custom, sb_role, sb_dist)."""

    ROLES = ("—", "Front", "Back", "Side")

    def __init__(self, plot: dict, parent=None, preview=None,
                 view=None) -> None:
        super().__init__(parent)
        self.plot = copy.deepcopy(plot)
        self.preview = preview or (lambda _p: None)
        self.active: int | None = None
        self.setWindowTitle("Setbacks")
        self.setMinimumSize(560, 440)

        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        title = QLabel("Setbacks")
        f = title.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        title.setFont(f)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(help_button("setbacks"))
        lay.addLayout(head)
        intro = QLabel("How far from each edge of the plot you may build. "
                       "Mark the front (the side on the street); the back "
                       "and the sides follow — change any of them here.")
        intro.setWordWrap(True)
        intro.setEnabled(False)
        lay.addWidget(intro)
        show = _show_row(view, [
            ("plot_dims", "Plot dimensions",
             "The length of every side of the plot — chosen here, it "
             "rules over the Settings"),
            ("plot_elev_dims", "Plot elevations",
             "The ground's elevation at every corner of the plot"),
            ("setbacks", "Buildable area",
             "The dashed outline of where you may build"),
            ("setback_dims", "Setback dimensions",
             "The setback figures — chosen here, it rules over the "
             "Settings")])
        if show is not None:
            lay.addWidget(show)

        top = QHBoxLayout()
        self.f_dist = {}
        for key, label in (("front", "Front"), ("back", "Back"),
                           ("sides", "Sides")):
            top.addWidget(QLabel(label))
            w = _metres(self.plot["sb_dist"][key], 0.0, 100.0, 0.5)
            w.setKeyboardTracking(False)
            w.valueChanged.connect(lambda v, k=key: self._on_dist(k, v))
            self.f_dist[key] = w
            top.addWidget(w)
            top.addSpacing(8)
        top.addStretch()
        lay.addLayout(top)

        n = len(self.plot["corners"])
        self.table = QTableWidget(n, 5)
        self.table.setHorizontalHeaderLabels(
            ["Side", "Length", "Role", "Setback", ""])
        hh = self.table.horizontalHeader()
        for c, mode in enumerate((QHeaderView.ResizeToContents,
                                  QHeaderView.ResizeToContents,
                                  QHeaderView.Stretch, QHeaderView.Stretch,
                                  QHeaderView.ResizeToContents)):
            hh.setSectionResizeMode(c, mode)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setStyleSheet(FIELD_TABLE_CSS)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.f_role, self.f_sb, self.b_reset = [], [], []
        from . import plotgeo
        L = plotgeo.side_lengths(self.plot["corners"])
        for i in range(n):
            self.table.setItem(i, 0, PlotDialog._fixed(f"{i + 1} → "
                                                       f"{(i + 1) % n + 1}"))
            self.table.setItem(i, 1, PlotDialog._fixed(f"{L[i]:.2f} m"))
            role = QComboBox()
            role.addItems(list(self.ROLES))
            role.currentIndexChanged.connect(
                lambda k, i=i: self._on_role(i, k))
            self.f_role.append(role)
            self.table.setCellWidget(i, 2, role)
            sb = PlotDialog._spin(0.0, 100.0, 0.5, " m", 2)
            sb.valueChanged.connect(lambda v, i=i: self._on_setback(i, v))
            self.f_sb.append(sb)
            self.table.setCellWidget(i, 3, sb)
            reset = QPushButton("↺")
            reset.setFlat(True)
            reset.setToolTip("Back to its role's setback")
            reset.clicked.connect(lambda _=False, i=i: self._on_reset(i))
            self.b_reset.append(reset)
            self.table.setCellWidget(i, 4, reset)
            for w in (role, sb, sb.lineEdit()):
                w.setProperty("axq_row", i)
                w.installEventFilter(self)
        lay.addWidget(self.table, 1)

        self.status = QLabel()
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_apply(self, bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._fill()

    # ---- showing ----------------------------------------------------------------
    def _fill(self) -> None:
        from . import plotgeo
        p = self.plot
        roles, dists, area = plotgeo.setbacks_of(p)
        for i in range(len(roles)):
            k = self.ROLES.index(roles[i].capitalize()) if roles[i] else 0
            for w, v in ((self.f_role[i], k),):
                w.blockSignals(True)
                w.setCurrentIndex(v)
                w.blockSignals(False)
            sb = self.f_sb[i]
            sb.blockSignals(True)
            sb.setValue(dists[i] or 0.0)
            sb.blockSignals(False)
            sb.setEnabled(roles[i] is not None)
            own = p["sb_custom"][i] is not None
            # (a table re-shows the widgets in its cells: empty, not hidden)
            self.b_reset[i].setText("↺" if own else "")
            self.b_reset[i].setEnabled(own)
            sb.setToolTip("This side's own setback" if own
                          else "The setback of its role")
        if not any(roles):
            text = "Mark a side as <b>Front</b> to start."
        elif area:
            text = (f"Buildable area <b>{plotgeo.area(area):,.2f} m²</b> of "
                    f"{plotgeo.area(p['corners']):,.2f} m² — dashed on the "
                    "model.")
        else:
            text = ("<span style='color:#e5484d'>These setbacks leave no "
                    "buildable area.</span>")
        self.status.setText(text)
        self.preview((p, self.active))

    # ---- edits ----------------------------------------------------------------------
    def _on_dist(self, key: str, v: float) -> None:
        self.plot["sb_dist"][key] = round(v, 3)
        self._fill()

    def _on_role(self, i: int, k: int) -> None:
        p = self.plot
        role = self.ROLES[k].lower()
        p["sb_front"][i] = role == "front"
        p["sb_role"][i] = role if role in ("back", "side") else None
        self._fill()

    def _on_setback(self, i: int, v: float) -> None:
        self.plot["sb_custom"][i] = round(v, 3)
        self._fill()

    def _on_reset(self, i: int) -> None:
        self.plot["sb_custom"][i] = None
        self._fill()

    def eventFilter(self, obj, event) -> bool:
        from PySide6.QtCore import QEvent, QTimer
        from PySide6.QtWidgets import QLineEdit
        kind = event.type()
        if kind in (QEvent.FocusIn, QEvent.MouseButtonPress,
                    QEvent.MouseButtonRelease):
            row = obj.property("axq_row")
            if row is not None and int(row) != self.active:
                self.active = int(row)
                self.preview((self.plot, self.active))
            spin = obj.parent() if isinstance(obj, QLineEdit) else obj
            if isinstance(spin, QDoubleSpinBox) and kind != \
                    QEvent.MouseButtonPress:
                QTimer.singleShot(0, spin.selectAll)
        return False

    def result_data(self):
        p = self.plot
        return (p["sb_front"], p["sb_custom"], p["sb_role"], p["sb_dist"])


class DigDialog(QDialog):
    """One excavation's own window: its name; its BOTTOM — a depth under
    the ground, under a level's floor, at an elevation, or PER CORNER (a
    ramp, a sloped pit: then every corner's bottom is typed in the table);
    a row per corner with the natural ground, the bottom, how deep, and
    the side leaving it; the area and the earth taken out, live. The model
    previews the outline, the row you are on lit. ``result_data()`` →
    (action "apply" | "delete", dig)."""

    MODES = (("depth", "Depth below ground"), ("level", "Under a level"),
             ("elev", "At an elevation"), ("corners", "Per corner (ramps)"))
    FILL_MODES = (("height", "Height above ground"),
                  ("level", "Under a level"), ("elev", "At an elevation"),
                  ("corners", "Per corner (slopes)"))

    def __init__(self, dig: dict, doc: dict, parent=None, preview=None,
                 view=None) -> None:
        super().__init__(parent)
        from . import terrain
        self.doc = doc
        self.dig = copy.deepcopy(dig)
        self.fill = terrain.is_fill(self.dig)
        self.noun = "fill" if self.fill else "excavation"
        self.preview = preview or (lambda _p: None)
        self.active: int | None = None
        self.action = "apply"
        self.ground = [terrain.ground_at(doc["plot"], q)
                       for q in self.dig["corners"]]
        self.setWindowTitle("Fill" if self.fill else "Excavation")
        self.setMinimumSize(600, 480)

        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        self.f_name = QLineEdit(self.dig["name"])
        f = self.f_name.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        self.f_name.setFont(f)
        self.f_name.setToolTip(f"The {self.noun}'s name")
        head.addWidget(self.f_name, 1)
        head.addWidget(help_button("fill" if self.fill else "excavation"))
        lay.addLayout(head)
        show = _show_row(view, [
            ("plot_dims", "Plot dimensions",
             "The length of every side of the plot"),
            ("plot_elev_dims", "Plot elevations",
             "The ground's elevation at every corner of the plot"),
            ("dig_dims", "Excavation / fill dimensions",
             "Each excavation's and fill's sides and depth / height — "
             "chosen here, it rules over the Settings"),
            ("dig_elev_dims", "Excavation / fill elevations",
             "Each floor's or platform's elevation (a ramp: start and "
             "end)")])
        if show is not None:
            lay.addWidget(show)

        # the bottom (a fill: the top): how it is set
        self.modes = self.FILL_MODES if self.fill else self.MODES
        row = QHBoxLayout()
        row.addWidget(QLabel("Top" if self.fill else "Bottom"))
        self.f_mode = QComboBox()
        for key, text in self.modes:
            self.f_mode.addItem(text, key)
        row.addWidget(self.f_mode)
        # a pit's depth, or a fill's height (same field)
        self.f_d = _metres(1.0 if self.fill else 3.0, 0.05, 100.0, 0.10)
        self.f_level = QComboBox()
        for r in reversed(doc["levels"]):
            if r["kind"] in ("ground", "basement"):
                self.f_level.addItem(r["name"], r["id"])
        self.f_off = _metres(0.30, 0.0, 5.0, 0.05)
        self.f_z = _metres(-3.0, -100.0, 50.0, 0.10)
        self.l_off = QLabel("below its floor")
        for w in (self.f_d, self.f_level, self.f_off, self.l_off, self.f_z):
            row.addWidget(w)
        row.addStretch()
        lay.addLayout(row)
        b = self.dig["bottom"]
        self.f_mode.setCurrentIndex(max(0, self.f_mode.findData(b["mode"])))
        if b["mode"] == "depth":
            self.f_d.setValue(b.get("d", 3.0))
        elif b["mode"] == "height":
            self.f_d.setValue(b.get("h", 1.0))
        elif b["mode"] == "level":
            self.f_level.setCurrentIndex(max(0, self.f_level.findData(
                b.get("level"))))
            self.f_off.setValue(-b.get("offset", -0.30))
        elif b["mode"] == "elev":
            self.f_z.setValue(b.get("z", -3.0))
        for w in (self.f_d, self.f_off, self.f_z):
            w.setKeyboardTracking(False)
            w.valueChanged.connect(self._on_bottom)
        self.f_mode.currentIndexChanged.connect(self._on_mode)
        self.f_level.currentIndexChanged.connect(self._on_bottom)

        n = len(self.dig["corners"])
        self.table = QTableWidget(n, 7)
        self.table.setHorizontalHeaderLabels(
            ["Corner", "Ground", "Top" if self.fill else "Bottom",
             "Height" if self.fill else "Depth", "Side", "Length",
             "Edge" if self.fill else "Wall"])
        hh = self.table.horizontalHeader()
        for c in range(7):
            hh.setSectionResizeMode(c, QHeaderView.Stretch if c in (1, 2, 3, 6)
                                    else QHeaderView.ResizeToContents)
        self.table.horizontalHeaderItem(6).setToolTip(
            "The side's edge: 90° = vertical, less = a slope (45° usual)")
        from . import terrain
        self.dig["angles"] = terrain.side_angles(self.dig)
        self.f_wall = []
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setStyleSheet(FIELD_TABLE_CSS)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        from . import plotgeo
        L = plotgeo.side_lengths(self.dig["corners"])
        self.f_bot = []
        for i in range(n):
            self.table.setItem(i, 0, PlotDialog._fixed(str(i + 1)))
            self.table.setItem(i, 1, PlotDialog._fixed(
                f"{self.ground[i]:+.2f}"))
            sb = PlotDialog._spin(-100.0, 50.0, 0.05, " m", 2)
            sb.valueChanged.connect(lambda v, i=i: self._on_corner(i, v))
            sb.setProperty("axq_row", i)
            sb.installEventFilter(self)
            sb.lineEdit().setProperty("axq_row", i)
            sb.lineEdit().installEventFilter(self)
            self.f_bot.append(sb)
            self.table.setCellWidget(i, 2, sb)
            # how deep (a fill: how high) — typed here too, POSITIVE: a «1»
            # typed as the Bottom (an elevation) put the floor above the
            # ground and the ramp came out flat (his test, 2026-10-03)
            dp = PlotDialog._spin(0.0, 100.0, 0.05, " m", 2)
            dp.valueChanged.connect(lambda v, i=i: self._on_depth(i, v))
            dp.setToolTip("How high, above the ground here" if self.fill
                          else "How deep, below the ground here")
            for w in (dp, dp.lineEdit()):
                w.setProperty("axq_row", i)
                w.installEventFilter(self)
            self.f_depth = getattr(self, "f_depth", [])
            self.f_depth.append(dp)
            self.table.setCellWidget(i, 3, dp)
            self.table.setItem(i, 4, PlotDialog._fixed(f"{i + 1} → "
                                                       f"{(i + 1) % n + 1}"))
            self.table.setItem(i, 5, PlotDialog._fixed(f"{L[i]:.2f} m"))
            wall = PlotDialog._spin(5.0, 90.0, 5.0, "°", 0)
            wall.setValue(self.dig["angles"][i])
            wall.valueChanged.connect(lambda v, i=i: self._on_wall(i, v))
            wall.setToolTip("This side's edge: 90° vertical, less = a slope")
            for w in (wall, wall.lineEdit()):
                w.setProperty("axq_row", i)
                w.installEventFilter(self)
            self.f_wall.append(wall)
            self.table.setCellWidget(i, 6, wall)
        lay.addWidget(self.table, 1)

        self.status = QLabel()
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_apply(self, bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        dele = bb.addButton(f"Delete {self.noun}", QDialogButtonBox.ResetRole)
        dele.clicked.connect(self._delete)
        lay.addWidget(bb)
        self._on_mode()

    # ---- the bottom ---------------------------------------------------------------
    def _on_mode(self, *_a) -> None:
        mode = self.f_mode.currentData()
        self.f_d.setVisible(mode in ("depth", "height"))
        for w in (self.f_level, self.f_off, self.l_off):
            w.setVisible(mode == "level")
        self.f_level.setEnabled(self.f_level.count() > 0)
        self.f_z.setVisible(mode == "elev")
        if mode == "corners" and self.dig["bottom"]["mode"] != "corners":
            # start the ramp from what the bottom is now
            from . import terrain
            self.dig["bottoms"] = [round(z, 3) for z in
                                   terrain.dig_bottoms(self.dig, self.doc)]
        self._on_bottom()

    def _on_bottom(self, *_a) -> None:
        mode = self.f_mode.currentData()
        if mode == "depth":
            self.dig["bottom"] = {"mode": "depth",
                                  "d": round(self.f_d.value(), 3)}
        elif mode == "height":
            self.dig["bottom"] = {"mode": "height",
                                  "h": round(self.f_d.value(), 3)}
        elif mode == "level" and self.f_level.count():
            self.dig["bottom"] = {"mode": "level",
                                  "level": self.f_level.currentData(),
                                  "offset": -round(self.f_off.value(), 3)}
        elif mode == "elev":
            self.dig["bottom"] = {"mode": "elev",
                                  "z": round(self.f_z.value(), 3)}
        else:
            self.dig["bottom"] = {"mode": "corners"}
        self._fill()

    def _on_wall(self, i: int, v: float) -> None:
        self.dig["angles"][i] = round(v, 1)
        self._fill()

    def _on_corner(self, i: int, v: float) -> None:
        """A corner's bottom typed: the excavation becomes «Per corner»
        (the others keep what they were) — no need to switch first."""
        if self.dig["bottom"]["mode"] != "corners":
            from . import terrain
            self.dig["bottoms"] = [round(z, 3) for z in
                                   terrain.dig_bottoms(self.dig, self.doc)]
            self.dig["bottom"] = {"mode": "corners"}
            self.f_mode.blockSignals(True)
            self.f_mode.setCurrentIndex(self.f_mode.findData("corners"))
            self.f_mode.blockSignals(False)
            for w in (self.f_d, self.f_level, self.f_off, self.l_off,
                      self.f_z):
                w.setVisible(False)
        # an excavation's floor never above the ground (a fill's top never
        # under it): held there, and said
        g = self.ground[i]
        self._held = None
        if not self.fill and v > g + 1e-6:
            v, self._held = g, i
        elif self.fill and v < g - 1e-6:
            v, self._held = g, i
        self.dig["bottoms"][i] = round(v, 3)
        self._fill()

    def _on_depth(self, i: int, v: float) -> None:
        """A depth (a fill: a height) typed: the corner's bottom follows."""
        g = self.ground[i]
        self._on_corner(i, g + v if self.fill else g - v)

    # ---- showing ----------------------------------------------------------------------
    def _fill(self) -> None:
        from . import plotgeo, terrain
        bots = terrain.dig_bottoms(self.dig, self.doc)
        per = self.dig["bottom"]["mode"] == "corners"
        for i, sb in enumerate(self.f_bot):
            sb.blockSignals(True)
            sb.setValue(bots[i])
            sb.blockSignals(False)
            word = "top" if self.fill else "bottom"
            sb.setToolTip(f"This corner's {word} (elevation)" if per else
                          f"Type a {word} here and the {self.noun} becomes "
                          "«Per corner» (a slope)")
            rise = (bots[i] - self.ground[i] if self.fill
                    else self.ground[i] - bots[i])
            dp = self.f_depth[i]
            dp.blockSignals(True)
            dp.setValue(max(0.0, rise))
            dp.blockSignals(False)
        from . import compat
        area = plotgeo.area(self.dig["corners"])
        trial = dict(self.doc, digs=[self.dig if d["id"] == self.dig["id"]
                                     else d for d in self.doc["digs"]])
        fits = self.dig["id"] in {d["id"] for d in terrain.opened(trial)}
        vol = compat.dig_volumes(trial).get(self.dig["id"], 0.0)
        top = terrain.top_of(self.dig, trial)
        foot = (f" · {'foot' if self.fill else 'open at the ground'} "
                f"{plotgeo.area(top):,.2f} m²"
                if top is not self.dig["corners"] else "")
        if self.fill:
            high = max(z - g for g, z in zip(self.ground, bots))
            text = (f"Platform <b>{area:,.2f} m²</b>{foot}  ·  highest "
                    f"{high:.2f} m  ·  earth brought in "
                    f"<b>{abs(vol):,.1f} m³</b>")
        else:
            deep = max(g - z for g, z in zip(self.ground, bots))
            text = (f"Floor <b>{area:,.2f} m²</b>{foot}  ·  deepest "
                    f"{deep:.2f} m  ·  earth taken out <b>{vol:,.1f} m³</b>")
        held = getattr(self, "_held", None)
        if held is not None:
            text += (f"<br><span style='color:#d97706'>Corner {held + 1}: "
                     + ("a fill's top can't go under the ground" if self.fill
                        else "an excavation's floor can't go above the ground")
                     + " — held at the ground. Type how "
                     + ("high" if self.fill else "deep")
                     + " in «" + ("Height" if self.fill else "Depth")
                     + "» (positive).</span>")
        if not fits:
            text += (f"<br><span style='color:#e5484d'>Its slopes reach past "
                     f"the plot — it won't be built until it fits (steeper "
                     f"edges, or a smaller {'platform' if self.fill else 'floor'}"
                     f").</span>")
        self.status.setText(text)
        self.bots = bots
        self.preview((self.dig["corners"], self.ground, self.active, bots,
                      self.fill))

    def eventFilter(self, obj, event) -> bool:
        from PySide6.QtCore import QEvent, QTimer
        from PySide6.QtWidgets import QLineEdit
        kind = event.type()
        if kind in (QEvent.FocusIn, QEvent.MouseButtonPress,
                    QEvent.MouseButtonRelease):
            row = obj.property("axq_row")
            if row is not None and int(row) != self.active:
                self.active = int(row)
                self.preview((self.dig["corners"], self.ground, self.active,
                              getattr(self, "bots", None), self.fill))
            spin = obj.parent() if isinstance(obj, QLineEdit) else obj
            if isinstance(spin, QDoubleSpinBox) and kind != \
                    QEvent.MouseButtonPress:
                QTimer.singleShot(0, spin.selectAll)
        return False

    def _delete(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, f"Delete {self.noun}?",
                (f"Take «{self.dig['name']}» away, back to the natural "
                 "ground?" if self.fill else
                 f"Fill «{self.dig['name']}» back in?")
                + " (Ctrl+Z brings it back)",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel) == QMessageBox.Yes:
            self.action = "delete"
            self.accept()

    def result_data(self):
        self.dig["name"] = self.f_name.text().strip() or self.dig["name"]
        return self.action, self.dig
