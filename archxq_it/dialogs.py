"""Modal editors (QDialog.exec): robust in Qt, used to EDIT structured data.
The permanent regions (top / left / right / bottom) stay the home of the
interface; a dialog opens only to change a set of values and closes."""
from __future__ import annotations

from .i18n import raw_text, tr

import copy
import re

from PySide6.QtCore import QPointF, QRectF, Qt
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

from . import compat, model
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


def _ic_named(name: str):
    """A window's header icon (look.Header): gold on the brown tile."""
    def draw(p, r, _on):
        import math
        from PySide6.QtGui import QColor
        from . import look as L
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#3a2f1c"))
        p.drawRoundedRect(r, 8, 8)
        g = L.GOLD
        if name == "plot":
            L.poly(p, [(7, 28), (14, 9), (33, 13), (31, 31)], g, 2.2,
                   close=True)
        elif name == "setbacks":
            L.poly(p, [(6, 6), (34, 6), (34, 34), (6, 34)], g, 1.6,
                   close=True)
            p.setPen(L.pen(g, 1.4, dash=True))
            p.drawRect(QRectF(12, 12, 16, 16))
        elif name in ("dig", "fill"):
            L.poly(p, [(5, 14), (12, 14), (16, 28), (24, 28), (28, 14),
                       (35, 14)], g, 2.2)
        elif name == "rooms":
            L.poly(p, [(6, 8), (34, 8), (34, 32), (6, 32)], g, 2.0,
                   close=True)
            p.setPen(L.pen(g, 1.8))
            p.drawLine(QPointF(20, 8), QPointF(20, 24))
            p.drawLine(QPointF(6, 20), QPointF(20, 20))
        elif name == "project":
            L.poly(p, [(8, 6), (27, 6), (32, 11), (32, 34), (8, 34)], g, 2.0,
                   close=True)
            p.setPen(L.pen(g, 1.4))
            for y in (16, 22, 28):
                p.drawLine(QPointF(13, y), QPointF(27, y))
        elif name == "settings":
            p.setPen(L.pen(g, 2.2))
            p.drawEllipse(QPointF(20, 20), 6, 6)
            for k in range(8):
                a = k * math.pi / 4
                p.drawLine(QPointF(20 + 9 * math.cos(a), 20 + 9 * math.sin(a)),
                           QPointF(20 + 13 * math.cos(a), 20 + 13 * math.sin(a)))
        elif name == "survey":
            p.setPen(L.pen(g, 2.0))
            for x, y in ((10, 28), (20, 12), (31, 24)):
                p.drawEllipse(QPointF(x, y), 3, 3)
            p.setPen(L.pen(g, 1.2, dash=True))
            p.drawLine(QPointF(10, 28), QPointF(20, 12))
            p.drawLine(QPointF(20, 12), QPointF(31, 24))
        else:                                   # import: a sheet, an arrow
            L.poly(p, [(8, 8), (24, 8), (24, 32), (8, 32)], g, 1.8,
                   close=True)
            p.setPen(L.pen(g, 2.2))
            p.drawLine(QPointF(18, 20), QPointF(34, 20))
            p.drawLine(QPointF(29, 15), QPointF(34, 20))
            p.drawLine(QPointF(29, 25), QPointF(34, 20))
    return draw


def look_head(dlg, lay, icon: str, title: str, topic, sub: str = ""):
    """The new windows' header (look.Header) on a window built the old way:
    the window dressed, its header added to ``lay`` — the tables / forms
    under it keep their own logic. Returns the header."""
    from . import look as L
    L.dress(dlg)
    h = L.Header(_ic_named(icon), title, topic)
    if sub:
        h.set_summary([sub])
    lay.addWidget(h)
    return h


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


def _stay_done(self, r: int) -> None:
    """QDialog.done for a window whose «Apply» works in place: the accept
    that Apply's press of OK makes (after the window's own checks) runs
    ``_apply_now`` and the window STAYS — no close, no reopen."""
    if getattr(self, "_axq_stay", False) and r == QDialog.Accepted:
        self._axq_stay = False
        self._apply_now()
        return
    QDialog.done(self, r)


def ok_apply(dlg: QDialog, bb: QDialogButtonBox, ok: str = "OK") -> None:
    """«OK» applies and closes; «Apply» applies and keeps the window (his
    ask, 2026-10-05: «Apply» used to close it, so every change meant
    opening it again). Apply presses OK itself, so whatever OK runs (a
    window's own checks) runs for both.

    When the caller gives the window ``_apply_now`` (ui._in_place), Apply
    applies with the window OPEN — in its place, on its tab, the model
    changing behind it (his ask, 2026-10-14: the close-and-reopen blinked
    and the window came back centred). Otherwise it is opened again at
    once: the caller sees ``dlg.again`` and opens it again."""
    from PySide6.QtCore import QTimer
    okb = bb.button(QDialogButtonBox.Ok)
    okb.setText(ok)
    okb.setObjectName("axqOk")        # orange in a window of look.py's
    b = bb.addButton("Apply", QDialogButtonBox.ApplyRole)
    b.setToolTip("Apply the changes and keep this window open")
    dlg.again = False
    dlg._apply_btn = b                   # (materials.with_tab takes it over)
    if type(dlg).done is not _stay_done:     # its class, once (C++ calls it)
        type(dlg).done = _stay_done

    def go() -> None:
        if callable(getattr(dlg, "_apply_now", None)):
            dlg._axq_stay = True
            try:
                okb.click()
            finally:
                dlg._axq_stay = False    # a check said no: nothing applied
            return
        dlg.again = True
        _REOPEN[type(dlg).__name__] = dlg.geometry()
        okb.click()
        if dlg.isVisible():              # a check said no: nothing applied
            dlg.again = False
            _REOPEN.pop(type(dlg).__name__, None)
    b.clicked.connect(go)
    b._axq_go = go
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
    from .look import LengthBox          # feet / inches in such a document
    w = LengthBox()
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
        self.setMinimumSize(640, 540)
        from . import look as L

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        look_head(self, lay, "project",
                  "New project" if self.is_new else "Project", "project",
                  "Fill in what you know — everything can be changed later. "
                  "Nothing is drawn in the model." if self.is_new
                  else self.project.get("name") or "")
        # the window of 0.10.0 (look.py): tabs at the top, each a fold
        self.tabs = L.Tabs()
        lay.addWidget(self.tabs.bar)
        lay.addWidget(L.rule())

        def page(widget, title, key):
            pg, pl = L.page()
            fold = L.Fold(title, f"project.{key}")
            fold.box.addWidget(widget)
            pl.addWidget(fold)
            pl.addStretch(1)
            return pg
        proj = self._project_tab()
        levels_tab = self._levels_tab()
        if not self.is_new:
            self.proj_form.addRow("Ground floor level",
                                  _with_help(self.f_ground, "ground_level"))
        self.tabs.addTab(page(proj, "The project", "about"), "Project",
                         "geometry")
        if self.is_new:
            # levels are set up here once; after that they live in the
            # levels strip (N) and each level's own window
            self.tabs.addTab(page(levels_tab, "Storeys", "levels"), "Levels",
                             "build")
        else:
            levels_tab.setParent(self)
            levels_tab.hide()
        self.tabs.addTab(page(self._docs_tab(), "Sheets", "docs"),
                         "Documentation", "material")
        order = (["project", "levels", "documentation"] if self.is_new
                 else ["project", "documentation"])
        self.tabs.setCurrentIndex(order.index(tab) if tab in order else 0)
        lay.addWidget(self.tabs.stack, 1)

        lay.addWidget(L.rule())
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        if self.is_new:
            bb.button(QDialogButtonBox.Ok).setText("Start project")
            L.ok_button(bb)
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

        # the DOCUMENT's units (IngeTrazo asks them for every new document)
        # — shown, not chosen here (feet / inches: 2026-10-16)
        self.f_units = QComboBox()
        self.f_units.addItems(list(model.UNITS))
        self.f_units.setCurrentIndex(1 if compat.imperial() else 0)
        self.f_units.setEnabled(False)
        self.f_units.setToolTip("The document's units — IngeTrazo asks them "
                                "for every new document. ArchXQ shows and "
                                "reads every measure in them.")
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
        self.table.setMinimumHeight(230)       # in a fold: never squeezed
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
            e = QTableWidgetItem(compat.fmt_level(elev[i]))
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
            self.table.item(row, 2).setText(
                compat.fmt_level(elev[n - 1 - row]))
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
        p["units"] = raw_text(self.f_units)
        p["north_deg"] = round(self.f_north.value(), 1)
        p["ground_level"] = round(self.f_ground.value(), 3)
        p["paper"] = raw_text(self.f_paper)
        p["orientation"] = raw_text(self.f_orient)
        p["scale"] = raw_text(self.f_scale)
        self.system = self.f_system.currentData()
        self.levels = model.fix_levels(self.levels)
        self.accept()

    def result_data(self) -> tuple[dict, list[dict], str]:
        return self.project, self.levels, self.system


class SettingsDialog(QDialog):
    """ArchXQ preferences (the user's, for every project).

    The window of 0.10.0 (look.py): tabs Display · Defaults, the ticks
    grouped in folds (the plan, drawing, on screen, warnings)."""

    def __init__(self, parent=None, placement: str = "viewport") -> None:
        from PySide6.QtWidgets import QCheckBox
        from . import look as L
        from . import prefs
        super().__init__(parent)
        self.placement = placement
        self.setWindowTitle(tr("ArchXQ settings"))
        self.setMinimumSize(640, 560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        look_head(self, lay, "settings", tr("Settings"), "settings",
                  tr("Yours, for every project — not saved in the file."))
        tabs = L.Tabs()
        lay.addWidget(tabs.bar)
        lay.addWidget(L.rule())

        def tick(text, key):
            c = QCheckBox(text)
            c.setChecked(prefs.get(key))
            return c

        # ---- Display -------------------------------------------------------------
        pg, dl = L.page()
        # the LANGUAGE (i18n.py, 0.14.0): Auto = IngeTrazo's own
        from . import i18n
        fold = L.Fold(tr("Language"), "settings.language")
        form = fold.form()
        self.f_lang = QComboBox()
        self.f_lang.addItem(tr("Auto — as IngeTrazo ({language})",
                               language=i18n.LANGUAGES[i18n.host_language()]),
                            "auto")
        for code, name in i18n.LANGUAGES.items():
            self.f_lang.addItem(name, code)
        self._lang_was = prefs.get("language")
        k = self.f_lang.findData(self._lang_was)
        self.f_lang.setCurrentIndex(k if k >= 0 else 0)
        form.addRow(tr("ArchXQ in"), self.f_lang)
        form.addRow("", L.hint(tr("Takes effect when IngeTrazo is restarted.")))
        # the SHEETS' words (titles, title block, area schedule): as ArchXQ,
        # or English (an office delivering in English)
        self.f_sheets_lang = QComboBox()
        self.f_sheets_lang.addItem(tr("The same as ArchXQ"), "interface")
        self.f_sheets_lang.addItem("English", "en")
        k = self.f_sheets_lang.findData(prefs.get("sheets_lang"))
        self.f_sheets_lang.setCurrentIndex(k if k >= 0 else 0)
        form.addRow(tr("Sheets in"), self.f_sheets_lang)
        dl.addWidget(fold)

        # the UNITS — the document's own, the same setting as IngeTrazo's
        # Preferences ▸ Units (his ask, 2026-10-20: people look for it here)
        self.f_unit = None
        choices = compat.length_units()
        if choices:
            fold = L.Fold(tr("Units"), "settings.units")
            form = fold.form()
            self.f_unit = QComboBox()
            for code, label in choices:
                self.f_unit.addItem(label, code)
            self._unit_was = compat.doc_length_unit()
            k = self.f_unit.findData(self._unit_was)
            self.f_unit.setCurrentIndex(k if k >= 0 else 0)
            form.addRow(tr("Lengths in"), self.f_unit)
            self.f_unit_new = tick(tr("New documents too"), "units_for_new")
            form.addRow("", self.f_unit_new)
            form.addRow("", L.hint(tr(
                "This document's units, saved in the file — the same setting "
                "as IngeTrazo's Preferences ▸ Units, where the areas, angles "
                "and decimals are.")))
            dl.addWidget(fold)

        fold = L.Fold(tr("Plan"), "settings.plan")
        form = fold.form()
        self.f_plan = tick(tr("Switch to plan view when a drawing tool starts"),
                           "plan_on_tool")
        form.addRow("", self.f_plan)
        self.f_plan_hl = tick(tr("Show the plan in Hidden Line"),
                              "plan_hidden_line")
        form.addRow("", self.f_plan_hl)
        self.f_grid = tick(tr("A grid and the red / green axes in the plan"),
                           "plan_grid")
        form.addRow("", self.f_grid)
        self.f_pdims = tick(tr("Dimensions round the walls in the plan "
                            "(through the openings, and overall)"),
                            "plan_dims")
        form.addRow("", self.f_pdims)
        self.f_tint = tick(tr("Rooms' floors tinted in the plan"), "room_tint")
        form.addRow("", self.f_tint)
        dl.addWidget(fold)

        fold = L.Fold(tr("Drawing"), "settings.drawing")
        form = fold.form()
        # (where ArchXQ's bars sit is no longer a choice: over the 3D view)
        self.f_dims = QComboBox()
        for k, label in prefs.PLOT_DIMS.items():
            self.f_dims.addItem(tr(label), k)
        self.f_dims.setCurrentIndex(self.f_dims.findData(prefs.get("plot_dims")))
        form.addRow(tr("Plot dimensions"), _with_help(self.f_dims, "plot_dims"))
        self.f_live = tick(tr("Show lengths while drawing"), "live_dims")
        form.addRow("", self.f_live)
        self.f_diag = tick(tr("Pull the cursor onto 45°"), "diag_pull")
        form.addRow("", self.f_diag)
        dl.addWidget(fold)

        fold = L.Fold(tr("On screen"), "settings.screen")
        form = fold.form()
        self.f_radial = tick(tr("A ring of actions at the mouse when a column, "
                             "beam, slab, stair… is clicked (F9)"),
                             "radial_menu")
        form.addRow(tr("Radial menu"), self.f_radial)
        self.f_grips = tick(tr("Grips on the element selected — drag them to "
                            "change it"), "grips")
        grips_row = QHBoxLayout()
        grips_row.setContentsMargins(0, 0, 0, 0)
        grips_row.addWidget(self.f_grips)
        grips_row.addWidget(help_button("grips"))
        grips_row.addStretch(1)
        form.addRow(tr("Grips"), grips_row)
        # the QUICK HELP cards (quickhelp.py): all on / off — F1 too — and
        # the ones hidden one by one, back
        self.f_quick = tick(tr("A card with the tool's clicks and keys, "
                            "bottom-left (F1)"), "quick_help")
        quick_row = QHBoxLayout()
        quick_row.setContentsMargins(0, 0, 0, 0)
        quick_row.addWidget(self.f_quick)
        from .quickhelp import hidden_topics, set_hidden_topics
        b_all = QPushButton(tr("Show all again"))
        b_all.setObjectName("axqChip")
        b_all.setToolTip(tr("The cards you hid one by one («Don't show this one "
                         "again») come back"))
        b_all.setEnabled(bool(hidden_topics()))

        def _all_again() -> None:
            set_hidden_topics(set())
            self.f_quick.setChecked(True)
            b_all.setEnabled(False)
        b_all.clicked.connect(_all_again)
        quick_row.addWidget(b_all)
        quick_row.addStretch(1)
        form.addRow(tr("Quick help"), quick_row)
        dl.addWidget(fold)

        fold = L.Fold(tr("Warnings"), "settings.warn")
        form = fold.form()
        self.f_warn_sb = tick(tr("When an excavation enters the setbacks"),
                              "warn_setbacks")
        form.addRow(tr("Warn me"), self.f_warn_sb)
        dl.addWidget(fold)
        dl.addStretch(1)
        tabs.addTab(pg, tr("Display"), "material")

        # ---- Defaults ------------------------------------------------------------
        pg, fl = L.page()
        fold = L.Fold(tr("New projects and levels"), "settings.defaults")
        form = fold.form()
        self.f_ground = L.metres(prefs.get("ground_thickness"), 0.05, 5.0)
        self.f_ground.field.setMaximum(20.0)
        self.f_ground.setValue(prefs.get("ground_thickness"))
        form.addRow(tr("Ground thickness"), _with_help(self.f_ground,
                                                   "ground_thickness"))
        self.f_floor = L.metres(prefs.get("floor_height"), model.MIN_HEIGHT,
                                min(model.MAX_HEIGHT, 10.0))
        self.f_floor.field.setMaximum(model.MAX_HEIGHT)
        self.f_floor.setValue(prefs.get("floor_height"))
        form.addRow(tr("New floor height"), self.f_floor)
        fl.addWidget(fold)
        fl.addStretch(1)
        tabs.addTab(pg, tr("Defaults"), "geometry")
        lay.addWidget(tabs.stack, 1)

        lay.addWidget(L.rule())
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel
                              | QDialogButtonBox.RestoreDefaults)
        L.ok_button(bb)
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
        self.f_pdims.setChecked(d["plan_dims"])
        self.f_tint.setChecked(d["room_tint"])
        self.f_warn_sb.setChecked(d["warn_setbacks"])
        self.f_radial.setChecked(d["radial_menu"])
        self.f_grips.setChecked(d["grips"])
        self.f_quick.setChecked(d["quick_help"])
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
        prefs.put("plan_dims", self.f_pdims.isChecked())
        prefs.put("room_tint", self.f_tint.isChecked())
        prefs.put("warn_setbacks", self.f_warn_sb.isChecked())
        prefs.put("radial_menu", self.f_radial.isChecked())
        prefs.put("grips", self.f_grips.isChecked())
        prefs.put("quick_help", self.f_quick.isChecked())
        prefs.put("ground_thickness", round(self.f_ground.value(), 3))
        prefs.put("floor_height", round(self.f_floor.value(), 3))
        prefs.put("sheets_lang", self.f_sheets_lang.currentData())
        if self.f_unit is not None:
            prefs.put("units_for_new", self.f_unit_new.isChecked())
            viewport = getattr(self.parent(), "viewport", None)
            if viewport is not None and self.f_unit.currentData() != self._unit_was:
                compat.set_doc_length_unit(viewport, self.f_unit.currentData(),
                                           self.f_unit_new.isChecked())
        lang = self.f_lang.currentData()
        prefs.put("language", lang)
        if lang != self._lang_was:
            from PySide6.QtWidgets import QMessageBox
            from . import i18n
            QMessageBox.information(
                self, tr("Language"),
                tr("ArchXQ will be in {language} the next time IngeTrazo "
                   "starts.", language=i18n.LANGUAGES[i18n.resolve(lang)]))
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
        lay.setContentsMargins(14, 10, 14, 12)
        look_head(self, lay, "plot", "Plot — sides and heights", "plot_table",
                  "Type the length of each side, in order — the closing "
                  "side (dashed) adjusts to close the plot. Angles come from "
                  "your drawing; set one only if the deed gives it.")
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
             "Points & import…)"),
            # here too: he looked for it in THIS window (2026-10-16)
            ("setbacks", "Setback outline",
             "The dashed outline of where you may build (the buildable "
             "area) — off by default")])
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
        from .look import LengthBox      # « m»: feet / inches if so
        w = LengthBox()
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
        text = (f"Area {compat.fmt_area(area, group=True)}   ·   perimeter "
                f"{compat.fmt_len(plotgeo.perimeter(self.pts), group=True)}")
        if self.gap > 0.005:
            text += (f"<br><span style='color:#e5484d'>These lengths cannot "
                     f"close: the closing side is {compat.fmt_len(self.gap)} "
                     "off. Check "
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


def _ic_level(p, r, _on):
    from PySide6.QtGui import QColor
    from . import look as L
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#3a2f1c"))
    p.drawRoundedRect(r, 8, 8)
    p.setPen(L.pen(L.GOLD, 2.4))
    for y in (11, 20, 29):
        p.drawLine(QPointF(8, y), QPointF(32, y))
    p.setPen(L.pen(L.GOLD, 1.4))
    p.drawLine(QPointF(12, 11), QPointF(12, 29))
    p.drawLine(QPointF(28, 11), QPointF(28, 29))


class _LevelStack(QWidget):
    """The building in section, live: its levels stacked, this one lit,
    each with its elevation; the ground line."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(260, 240)
        self.rows = []                     # (name, z, height, kind)
        self.cur = 0

    def set(self, rows, cur) -> None:
        self.rows, self.cur = rows, cur
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        from PySide6.QtGui import QColor, QPainter
        from . import look as L
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(L.FIELD))
        try:
            self._paint(p, L)
        except Exception:  # noqa: BLE001 — a preview never breaks the window
            import traceback
            traceback.print_exc()
        finally:
            p.end()

    def _paint(self, p, L) -> None:
        if not self.rows:
            return
        z0 = min(z for _n, z, _h, _k in self.rows)
        z1 = max(z + h for _n, z, h, _k in self.rows)
        rr = QRectF(self.rect()).adjusted(16, 14, -16, -14)
        k = rr.height() / max(z1 - z0, 0.5)
        x0, x1 = rr.left() + 70, rr.right() - 20

        def y(z):
            return rr.bottom() - (z - z0) * k
        for i, (name, z, h, kind) in enumerate(self.rows):
            on = i == self.cur
            L.poly(p, [(x0, y(z + h)), (x1, y(z + h)), (x1, y(z)), (x0, y(z))],
                   L.ACCENT if on else L.LINE, 2.0 if on else 1.0,
                   close=True, fill="#e8742c33" if on else
                   ("#2e313599" if kind != "basement" else "#26282c"))
            L.text(p, x0 + 8, (y(z) + y(z + h)) / 2 + 4, name,
                   L.TEXT if on else L.MUTED, 8, on)
            from .plottools import elev_text      # ±0.00 / +3.20 / +10'6"
            L.text(p, x0 - 6, y(z) + 4, elev_text(z).replace("−", "-"),
                   L.GOLD if on else L.BLUE, 7,
                   align=Qt.AlignRight)
        g = next((z for _n, z, _h, kd in self.rows if kd == "ground"), None)
        if g is not None:
            p.setPen(L.pen("#5cc472", 1.6, dash=True))
            p.drawLine(QPointF(x0 - 4, y(g)), QPointF(x1 + 10, y(g)))


class LevelDialog(QDialog):
    """One level's own window: its name and height (elevation worked out),
    what it shows, a level above / below it, repeating or copying it, and
    deleting it — never the ground floor, never a level with anything on
    it. ``result_data()`` after ``exec()`` → (action, name, height);
    action: "apply" | "above" | "below" | "repeat" | "copy" | "delete".

    The window of 0.10.0 (look.py): tabs Level · Show · Repeat & copy, the
    height on a bar, the building's levels stacked beside (this one lit)."""

    def __init__(self, doc: dict, index: int, content: int,
                 parent=None, on_show=None) -> None:
        from PySide6.QtWidgets import QSpinBox
        from . import look as L
        super().__init__(parent)
        self.levels = copy.deepcopy(doc["levels"])
        self.index = index
        self.ground_level = (doc["project"]["ground_level"]
                             if model.has_project(doc) else 0.0)
        self.action = "apply"
        lv = self.levels[index]
        self.setWindowTitle("Level")
        self.setMinimumWidth(820)
        L.dress(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(6)
        self.head = L.Header(_ic_level, lv["name"], "level", editable=True)
        self.f_name = self.head.name
        lay.addWidget(self.head)
        self.tabs = L.Tabs()
        lay.addWidget(self.tabs.bar)
        lay.addWidget(L.rule())

        # ---- Level ---------------------------------------------------------------
        pg, gl = L.page()
        self.fold_h = L.Fold("Height", "level.height")
        form = self.fold_h.form()
        self.f_height = L.metres(lv["height"], model.MIN_HEIGHT,
                                 min(model.MAX_HEIGHT, 10.0))
        self.f_height.field.setMaximum(model.MAX_HEIGHT)
        self.f_height.setValue(lv["height"])
        self.f_height.valueChanged.connect(self._refresh)
        form.addRow("Height", _with_help(self.f_height, "level_height"))
        self.l_elev = QLabel()
        form.addRow("Elevation", self.l_elev)
        gl.addWidget(self.fold_h)
        gl.addWidget(L.hint(
            KIND_LABEL[lv["kind"]] + (" floor" if lv["kind"] == "ground"
                                      else "") + " · contains "
            + ("nothing yet" if content == 0 else
               f"{content} object" + ("s" if content > 1 else ""))))
        gl.addStretch(1)
        self.tabs.addTab(pg, "Level", "geometry")

        # ---- Show ----------------------------------------------------------------
        if on_show is not None:
            pg, sl = L.page()
            fold = L.Fold("Show on this level", "level.show")
            fold.box.addWidget(L.hint("Changes the view right away (no "
                                      "undo, Cancel keeps it — like the "
                                      "levels' eye)."))
            fold.box.addLayout(self._show_grid(
                set((doc.get("hidden_parts") or {}).get(lv["id"], ())),
                on_show))
            sl.addWidget(fold)
            sl.addStretch(1)
            self.tabs.addTab(pg, "Show", "material")

        # ---- Repeat & copy -------------------------------------------------------
        pg, rl_ = L.page()
        g = next(i for i, r in enumerate(self.levels) if r["kind"] == "ground")
        fold = L.Fold("Add a level", "level.add")
        row = QHBoxLayout()
        b_up = QPushButton("+ Level above")
        b_up.setObjectName("axqChip")
        b_up.clicked.connect(lambda: self._done("above"))
        row.addWidget(b_up)
        b_down = QPushButton("+ Basement below" if index <= g
                             else "+ Level below")
        b_down.setObjectName("axqChip")
        b_down.clicked.connect(lambda: self._done("below"))
        row.addWidget(b_down)
        row.addStretch(1)
        fold.box.addLayout(row)
        rl_.addWidget(fold)
        # REPEAT it upwards (repeatlevel.py — his ask, 2026-10-11): one
        # floor drawn, the tower made
        fold = L.Fold("Repeat above", "level.repeat")
        row = QHBoxLayout()
        self.f_times = QSpinBox()
        self.f_times.setRange(1, 60)
        self.f_times.setValue(1)
        self.f_times.setSuffix(" ×")
        self.f_times.setToolTip("How many copies of this level, one above "
                                "the other")
        b_rep = QPushButton("Repeat above")
        b_rep.setObjectName("axqChip")
        b_rep.setToolTip("New levels right above this one, as high as it, "
                         "each with a copy of its walls, doors, windows, "
                         "columns, beams and slabs (stairs and ramps "
                         "stay). One Ctrl+Z")
        b_rep.setEnabled(content > 0)
        if not content:
            b_rep.setToolTip("Nothing on this level to repeat yet")
        b_rep.clicked.connect(lambda: self._done("repeat"))
        row.addWidget(QLabel("Copies"))
        row.addWidget(self.f_times)
        row.addWidget(b_rep)
        row.addStretch(1)
        fold.box.addLayout(row)
        rl_.addWidget(fold)
        # …or COPY it onto a level you pick (his ask, 2026-10-12: alternate
        # floors — the architect chooses, one at a time)
        fold = L.Fold("Copy to a level", "level.copy")
        row = QHBoxLayout()
        self.f_target = QComboBox()
        for r in reversed(self.levels):               # top first, as listed
            if r["id"] != lv["id"]:
                self.f_target.addItem(r["name"], r["id"])
        # it opens on the level right ABOVE this one (below it, at the top)
        near = self.levels[index + 1]["id"] if index + 1 < len(self.levels) \
            else (self.levels[index - 1]["id"] if index > 0 else None)
        k = self.f_target.findData(near)
        if k >= 0:
            self.f_target.setCurrentIndex(k)
        b_cp = QPushButton("Copy")
        b_cp.setObjectName("axqChip")
        b_cp.setToolTip("Its walls, doors, windows, columns, beams and slabs "
                        "copied onto that level — added to what is there "
                        "(a stair up from it goes up from there). One Ctrl+Z")
        b_cp.setEnabled(content > 0 and self.f_target.count() > 0)
        b_cp.clicked.connect(lambda: self._done("copy"))
        row.addWidget(QLabel("Level"))
        row.addWidget(self.f_target, 1)
        row.addWidget(b_cp)
        fold.box.addLayout(row)
        rl_.addWidget(fold)
        rl_.addStretch(1)
        self._rep_tab = self.tabs.addTab(pg, "Repeat & copy", "build")
        # what the user touched last on that tab — the orange OK there
        # then does it (his trap, 2026-10-18: a level picked, OK pressed,
        # nothing copied — only the «Copy» chip copied)
        self._rep_intent = "copy"
        self._rep_ok = content > 0
        self.f_times.valueChanged.connect(
            lambda _v: setattr(self, "_rep_intent", "repeat"))
        self.f_target.currentIndexChanged.connect(
            lambda _i: setattr(self, "_rep_intent", "copy"))

        # ---- the pages + the stack beside them -----------------------------------
        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self.tabs.stack, 5)
        card = L.Card("The building's levels")
        self.stack = _LevelStack()
        card.box.addWidget(self.stack, 1)
        self.stats = L.Stats(2)
        card.box.addWidget(self.stats)
        body.addWidget(card, 4)
        lay.addLayout(body, 1)

        # ---- the buttons ---------------------------------------------------------
        lay.addWidget(L.rule())
        acts = QHBoxLayout()
        self.b_del = QPushButton("Delete level")
        self.b_del.setObjectName("axqDanger")
        if lv["kind"] == "ground":
            self.b_del.setEnabled(False)
            self.b_del.setToolTip("The ground floor always stays")
        elif content:
            self.b_del.setEnabled(False)
            self.b_del.setToolTip("This level has objects on it — move or "
                                  "delete them first")
        self.b_del.clicked.connect(self._delete)
        acts.addWidget(self.b_del)
        acts.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_apply(self, bb)
        L.ok_button(bb)
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        acts.addWidget(bb)
        lay.addLayout(acts)
        self._refresh()

    def _ok(self) -> None:
        """OK. On the «Repeat & copy» tab it asks whether to do what is
        set up there — never a silent «only the name and height»."""
        if self.tabs.currentIndex() != self._rep_tab or not self._rep_ok:
            self._done("apply")
            return
        from PySide6.QtWidgets import QMessageBox
        if self._rep_intent == "repeat":
            n = self.times()
            what, act = (f"Repeat this level {n}× above?", "repeat")
            label = "Repeat"
        else:
            if self.target() is None:
                self._done("apply")
                return
            what, act = (f"Copy this level onto «{self.f_target.currentText()}»?",
                         "copy")
            label = "Copy"
        box = QMessageBox(self)
        box.setWindowTitle("Level")
        box.setText(what)
        box.setInformativeText("Its walls, doors, windows, columns, beams and "
                               "slabs. One Ctrl+Z.")
        b_do = box.addButton(label, QMessageBox.AcceptRole)
        b_keep = box.addButton("Only save name and height",
                               QMessageBox.DestructiveRole)
        box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(b_do)
        box.exec()
        if box.clickedButton() is b_do:
            self._done(act)
        elif box.clickedButton() is b_keep:
            self._done("apply")

    def _show_grid(self, off: set, on_show):
        """Two rows of three ticks; each change goes out at once."""
        from PySide6.QtWidgets import QCheckBox, QGridLayout
        grid = QGridLayout()
        grid.setContentsMargins(0, 2, 0, 4)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        self.f_show = {}
        for n, (key, label, _kinds) in enumerate(model.LEVEL_PARTS):
            c = QCheckBox(label.replace("&", "&&"))   # «&»: not a shortcut
            c.setChecked(key not in off)
            c.toggled.connect(lambda _on: on_show(
                {k for k, box in self.f_show.items() if not box.isChecked()}))
            self.f_show[key] = c
            grid.addWidget(c, n // 3, n % 3)
        grid.setColumnStretch(3, 1)
        return grid

    def _refresh(self, *_a) -> None:
        levels = copy.deepcopy(self.levels)
        levels[self.index]["height"] = self.f_height.value()
        zs = model.elevations(levels, self.ground_level)
        z = zs[self.index]
        el = ("±0.00 m" if compat.doc_length_unit() == "m" else "±0") \
            if abs(z) < 0.005 else compat.fmt_level(z)
        self.l_elev.setText(el)
        h = self.f_height.value()
        self.head.set_summary(["{" + compat.fmt_len(h) + "} high",
                               "at " + el])
        self.fold_h.set_pick(compat.fmt_len(h))
        self.stack.set([(r["name"], zs[i], float(r["height"]), r["kind"])
                        for i, r in enumerate(levels)], self.index)
        self.stats.set([(compat.fmt_len(h), "height"), (el, "elevation")])

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

    def times(self) -> int:
        """How many copies «Repeat above» makes."""
        return int(self.f_times.value())

    def target(self) -> str | None:
        """The level «Copy» copies onto."""
        return self.f_target.currentData()


def _ic_wall(p, r, _on):
    from PySide6.QtGui import QColor
    from . import look as L
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#3a2f1c"))
    p.drawRoundedRect(r, 8, 8)
    L.poly(p, [(7, 12), (33, 12), (33, 30), (7, 30)], L.GOLD, 2.2,
           close=True)
    p.setPen(L.pen(L.GOLD, 1.4))
    for y in (18, 24):
        p.drawLine(QPointF(7, y), QPointF(33, y))
    for x, y0, y1 in ((16, 12, 18), (24, 18, 24), (16, 24, 30)):
        p.drawLine(QPointF(x, y0), QPointF(x, y1))


def _pic_align(a):
    """Where the wall stands on the line drawn (dashed): its band in plan,
    the inside (the building) up."""
    def draw(p, r, _on):
        from . import look as L
        y0 = {"outside": 12, "centre": 18, "inside": 24}[a]
        L.poly(p, [(8, y0), (52, y0), (52, y0 + 12), (8, y0 + 12)], L.INK,
               1.6, fill="#8a8f9655")
        p.setPen(L.pen(L.ACCENT, 2.0, dash=True))
        p.drawLine(QPointF(4, 24), QPointF(56, 24))
        L.text(p, 30, 9, "in", L.MUTED, 6, False, align=Qt.AlignHCenter)
    return draw


def _draw_wall_size(p, r, hot, d):
    """The wall cut across: its thickness on the line drawn, its height,
    its base."""
    from . import look as L
    a = d.get("align", "centre")
    floor = 100
    off = {"outside": 0, "centre": -9, "inside": -18}[a]
    x0 = 66 + off
    top = 18
    base = d.get("base", 0.0)
    yb = floor - max(-14, min(14, base * 20))
    L.poly(p, [(x0, top), (x0 + 18, top), (x0 + 18, yb), (x0, yb)], L.INK,
           1.8, fill="#8a8f9655")
    p.setPen(L.pen(L.DIM, 1.6))
    p.drawLine(QPointF(10, floor), QPointF(140, floor))
    p.setPen(L.pen(L.ACCENT, 1.6, dash=True))
    p.drawLine(QPointF(66, 8), QPointF(66, 112))
    L.dim(p, (x0, top - 8), (x0 + 18, top - 8), "t", hot == "t",
          at=(x0 + 22, top - 5))
    L.dim(p, (118, top), (118, yb), "H", hot == "h",
          at=(123, (top + yb) / 2 + 4))
    if abs(base) > 1e-6 or hot == "base":
        L.dim(p, (34, floor), (34, yb), "", hot == "base", ticks=False)
        L.text(p, 12, (floor + yb) / 2 + 4, "base",
               L.GOLD if hot == "base" else L.BLUE, 7)
    L.text(p, 12, floor - 4, "floor", L.MUTED, 7, False)


def _draw_cw_plan(p, r, hot, d):
    """A curtain wall in plan, cut through: the end post (left) and a
    mullion, their widths and depths from the outer face (below), the
    glass where it sits."""
    from . import look as L
    if not d:
        return
    t = float(d.get("t", 0.15))
    k = 70.0 / max(t, 0.15)                    # px per metre: the wall's depth
    k = min(k, 400.0)
    yo = 96.0                                  # the outer face
    yi = yo - t * k                            # the inner face
    # the wall's band, light
    L.poly(p, [(8, yi), (142, yi), (142, yo), (8, yo)], L.MUTED, 0.8,
           fill="#8a8f9622")
    p.setPen(L.pen(L.ACCENT, 1.2, dash=True))
    p.drawLine(QPointF(8, yo), QPointF(142, yo))
    L.text(p, 104, yo + 14, "outside", L.MUTED, 7, False)
    # the glass
    gm = d.get("md", t) / 2 if d.get("glass") == "centre" else 0.026
    yg = yo - gm * k
    p.setPen(L.pen("#7fb3c8", 2.2))
    p.drawLine(QPointF(8, yg), QPointF(142, yg))
    # the end post (left) and a mullion (middle)
    pw, pd = d.get("pw", 0.05) * k, d.get("pd", t) * k
    mw, md = d.get("mw", 0.05) * k, d.get("md", t) * k
    x_m = 92.0
    L.poly(p, [(8, yo - pd), (8 + pw, yo - pd), (8 + pw, yo), (8, yo)],
           L.INK, 1.4, fill="#30343a")
    L.poly(p, [(x_m - mw / 2, yo - md), (x_m + mw / 2, yo - md),
               (x_m + mw / 2, yo), (x_m - mw / 2, yo)], L.INK, 1.4,
           fill="#30343a")
    # their sizes
    L.dim(p, (8, yo + 6), (8 + pw, yo + 6), "", hot == "pw")
    L.dim(p, (8 + pw + 6, yo - pd), (8 + pw + 6, yo), "", hot == "pd")
    L.dim(p, (x_m - mw / 2, yo + 6), (x_m + mw / 2, yo + 6), "", hot == "mw")
    L.dim(p, (x_m + mw / 2 + 6, yo - md), (x_m + mw / 2 + 6, yo), "",
          hot == "md")
    L.text(p, 8, yi - 6, "post", L.GOLD if hot in ("pw", "pd") else L.BLUE, 7)
    L.text(p, x_m - 14, yi - 6, "mullion",
           L.GOLD if hot in ("mw", "md", "s") else L.BLUE, 7)


def _draw_cw_elev(p, r, hot, d):
    """A curtain wall seen from outside, one floor: the band over the
    floor, the transom on it, the rows of panes."""
    from . import look as L
    if not d:
        return
    h = max(float(d.get("h", 3.0)), 0.5)
    k = 96.0 / h
    floor, top = 108.0, 108.0 - h * k
    x0, x1 = 30.0, 120.0
    p.setPen(L.pen(L.DIM, 1.6))
    p.drawLine(QPointF(10, floor), QPointF(140, floor))
    L.text(p, 8, floor - 4, "floor", L.MUTED, 7, False)
    L.poly(p, [(x0, top), (x1, top), (x1, floor), (x0, floor)], L.INK, 1.4,
           fill="#7fb3c833")
    p.setPen(L.pen(L.INK, 1.4))
    p.drawLine(QPointF((x0 + x1) / 2, top), QPointF((x0 + x1) / 2, floor))
    tw = max(d.get("tw", 0.05) * k, 1.5)
    lo = floor
    if d.get("band"):
        bh = d.get("band_h", 0.10) * k
        L.poly(p, [(x0, floor - bh), (x1, floor - bh), (x1, floor + 6),
                   (x0, floor + 6)], L.INK, 1.0, fill="#16181b")
        L.poly(p, [(x0, floor - bh - tw), (x1, floor - bh - tw),
                   (x1, floor - bh), (x0, floor - bh)], L.INK, 1.0,
               fill="#30343a")
        L.dim(p, (x1 + 8, floor), (x1 + 8, floor - bh), "", hot == "band")
        lo = floor - bh - tw
    rows = int(d.get("rows", 0) or 0)
    for i in range(1, rows + 1):
        y = lo + (top - lo) * i / (rows + 1)
        L.poly(p, [(x0, y - tw / 2), (x1, y - tw / 2), (x1, y + tw / 2),
                   (x0, y + tw / 2)], L.INK, 1.0, fill="#30343a")
        if i == 1:
            L.dim(p, (x0 - 8, y - tw / 2), (x0 - 8, y + tw / 2), "",
                  hot in ("tw", "td"))


class _WallPlan(QWidget):
    """The wall in plan, live: the line drawn (dashed), its band as the
    alignment puts it, the inside marked."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(280, 200)
        self.w = None

    def set(self, w: dict) -> None:
        self.w = w
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        from PySide6.QtGui import QColor, QPainter
        from . import look as L
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(L.FIELD))
        try:
            if self.w is not None:
                self._paint(p, L)
        except Exception:  # noqa: BLE001 — a preview never breaks the window
            import traceback
            traceback.print_exc()
        finally:
            p.end()

    def _paint(self, p, L) -> None:
        from . import walls as W
        w = self.w
        pcs = W.plan([w]).get(w["id"]) or []
        pts = [tuple(q) for pc in pcs for q in pc["outer"]]
        if w.get("kind", "line") == "line":
            pts += [tuple(w["a"]), tuple(w["b"])]
        if not pts:
            return
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        rr = QRectF(self.rect()).adjusted(24, 24, -24, -24)
        k = min(rr.width() / max(x1 - x0, 0.5), rr.height() / max(y1 - y0,
                                                                   0.5))
        ox = rr.center().x() - (x1 - x0) * k / 2
        oy = rr.center().y() + (y1 - y0) * k / 2

        def q(x, y):
            return (ox + (x - x0) * k, oy - (y - y0) * k)
        for pc in pcs:
            L.poly(p, [q(*c) for c in pc["outer"]], L.INK, 1.6, close=True,
                   fill="#8a8f9655")
        if w.get("kind", "line") == "line":
            a, b = q(*w["a"]), q(*w["b"])
            p.setPen(L.pen(L.ACCENT, 1.8, dash=True))
            p.drawLine(QPointF(*a), QPointF(*b))
            p.setPen(Qt.NoPen)
            p.setBrush(L.colour(L.ACCENT))
            p.drawEllipse(QPointF(*a), 4, 4)
            p.setBrush(Qt.NoBrush)


class WallDialog(QDialog):
    """One wall's own window: name, thickness, alignment, which side its
    inside is, height (the level's, or its own), base; the length of a
    straight wall (stretched from its end); delete. ``result_data()``
    after ``exec()`` → (action, wall) — action "apply" | "delete" | "hide".

    The window of 0.10.0 (look.py): tabs Geometry · Position (+ Material);
    alignment as pictures, bars for the sizes, a live plan of the wall and
    its numbers. The record is the old window's."""

    ALIGNS = (("outside", "Outside"), ("centre", "Centre"),
              ("inside", "Inside"))

    def __init__(self, wall: dict, level: dict, parent=None) -> None:
        from PySide6.QtWidgets import QCheckBox
        from . import look as L
        from . import walls as W
        super().__init__(parent)
        self.wall = copy.deepcopy(wall)
        self.level = level
        self.action = "apply"
        kind = wall.get("kind", "line")
        self.kind = kind
        self.setWindowTitle("Wall")
        self.setMinimumWidth(840)
        L.dress(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(6)
        self.head = L.Header(_ic_wall, wall["name"], "wall", editable=True)
        self.f_name = self.head.name
        lay.addWidget(self.head)
        self.tabs = L.Tabs()
        self._axq_tabs = self.tabs
        lay.addWidget(self.tabs.bar)
        lay.addWidget(L.rule())

        # ---- Geometry ------------------------------------------------------------
        pg, gl = L.page()
        self.fold_t = L.Fold("Thickness & alignment", "wall.thickness")
        self.d_size = L.Drawing(_draw_wall_size, 150, 120)
        self.f_align = L.Chips(width=86)
        for v, text in self.ALIGNS:
            self.f_align.addItem(text, v, pic=_pic_align(v))
        self.f_align.setCurrentIndex(max(0, self.f_align.findData(
            wall["align"])))
        self.f_align.setToolTip("Where the wall stands on the line drawn: "
                                "its outer face, its centre or its inner "
                                "face on it")
        self.fold_t.box.addWidget(self.f_align)
        form = self.fold_t.form(self.d_size)
        self.f_t = L.metres(wall["t"], 0.05, 0.60, 0.01)
        self.f_t.field.setMaximum(3.0)
        self.f_t.setValue(wall["t"])
        form.addRow("Thickness", self.f_t)
        self.d_size.link(self.f_t, "t")
        self.f_flip = QCheckBox("Inside on the other side of the line")
        self.f_flip.setToolTip("Which side of the line drawn is the "
                               "building's inside — it decides where "
                               "«Outside» / «Inside» put the wall")
        if kind == "circle":
            self.f_flip.setEnabled(False)
            self.f_flip.setToolTip("A round wall's inside is its centre")
        form.addRow("Side", self.f_flip)
        gl.addWidget(self.fold_t)

        self.fold_h = L.Fold("Height", "wall.height")
        form = self.fold_h.form()
        self.f_hmode = L.Chips()
        self.f_hmode.addItem(f"Level height "
                             f"({compat.fmt_len(level['height'])})",
                             "level")
        self.f_hmode.addItem("Its own height", "own")
        own = wall.get("height", "level") != "level"
        self.f_hmode.setCurrentIndex(1 if own else 0)
        form.addRow("Height", self.f_hmode)
        h0 = float(wall["height"]) if own else float(level["height"])
        self.f_h = L.metres(h0, 0.10, 10.0)
        self.f_h.field.setMaximum(30.0)
        self.f_h.setValue(h0)
        self.f_h.setEnabled(own)
        form.addRow("Its own", self.f_h)
        self.d_size.link(self.f_h, "h")
        self.f_base = L.metres(float(wall.get("base", 0.0)), -2.0, 2.0)
        self.f_base.field.setRange(-10.0, 10.0)
        self.f_base.setValue(float(wall.get("base", 0.0)))
        self.f_base.setToolTip("Up or down from the level's floor")
        form.addRow("Base offset", self.f_base)
        self.d_size.link(self.f_base, "base")
        gl.addWidget(self.fold_h)
        gl.addWidget(L.hint(f"Level: {level['name']} · "
                            + {"line": "Straight", "arc": "Curved",
                               "circle": "Round"}[kind] + " wall"))
        gl.addStretch(1)
        self.tabs.addTab(pg, "Geometry", "geometry")

        # ---- Position ------------------------------------------------------------
        pg, pl = L.page()
        self.fold_pos = L.Fold("Length & ends", "wall.ends")
        form = self.fold_pos.form()
        self.length0 = W.drawn(wall).L if kind != "circle" else 0.0
        self.f_ends = None
        if kind == "line":
            self.f_len = L.metres(self.length0, 0.05, 50.0)
            self.f_len.field.setMaximum(1000.0)
            self.f_len.setValue(self.length0)
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
                    s = _metres(float(wall[end][k]), -100000.0, 100000.0,
                                0.05)
                    s.valueChanged.connect(self._on_ends)
                    rl.addWidget(QLabel(axis))
                    rl.addWidget(s, 1)
                    self.f_ends[(end, k)] = s
                form.addRow(label, row)
        else:
            self.f_len = None
            form.addRow("Length" if kind == "arc" else "Radius",
                        QLabel(compat.fmt_len(self.length0) if kind == "arc"
                               else compat.fmt_len(wall['r'])))
        pl.addWidget(self.fold_pos)
        pl.addStretch(1)
        self.tabs.addTab(pg, "Position", "position")
        self.cw = None
        cw_tab = None
        if wall.get("cw"):
            self._curtain_tab(wall)
            cw_tab = self.tabs.count() - 1
            # a curtain wall's window is ITS window (his ask, 2026-10-14:
            # a double-click opened it as a masonry wall's, on Geometry)
            self.setWindowTitle("Curtain wall")
        self._own = self.tabs.count()

        # ---- the pages + the plan beside them ------------------------------------
        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self.tabs.stack, 5)
        card = L.Card("Plan")
        self.plan = _WallPlan()
        card.box.addWidget(self.plan, 1)
        self.stats = L.Stats(4)
        card.box.addWidget(self.stats)
        self.side = card
        body.addWidget(card, 4)
        lay.addLayout(body, 1)
        self.tabs.currentChanged.connect(
            lambda i: self.side.setVisible(i < self._own))

        # ---- the buttons ---------------------------------------------------------
        lay.addWidget(L.rule())
        acts = QHBoxLayout()
        acts.addWidget(hide_button(self))
        b_del = QPushButton("Delete wall")
        b_del.setObjectName("axqDanger")
        b_del.clicked.connect(self._delete)
        acts.addWidget(b_del)
        acts.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_apply(self, bb)
        L.ok_button(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        acts.addWidget(bb)
        lay.addLayout(acts)

        self.f_t.valueChanged.connect(self._refresh)
        self.f_h.valueChanged.connect(self._refresh)
        self.f_base.valueChanged.connect(self._refresh)
        self.f_hmode.currentIndexChanged.connect(self._refresh)
        self.f_align.currentIndexChanged.connect(self._refresh)
        self.f_flip.toggled.connect(self._refresh)
        self._refresh()
        if cw_tab is not None:
            self.tabs.setCurrentIndex(cw_tab)   # it opens on its own tab

    def _curtain_tab(self, wall: dict) -> None:
        """A CURTAIN wall's own tab (his ask, 2026-10-14 — the corporate
        building's glass floor): the width and depth of the mullions, the
        transoms and the corner / end posts (depths from the OUTER face),
        the band at each floor and its height, where the glass sits, the
        colours (Pro)."""
        from . import curtain as CW
        from . import edition
        from . import look as L
        c = CW.clean(wall)
        t = float(wall["t"])
        sz = CW.sizes(wall)
        f = {}
        pg, cl = L.page()

        def measure(form, key, label, v, lo, hi, step, tip, drawing, hot):
            m = L.metres(v, lo, hi, step)
            m.setToolTip(tip)
            form.addRow(label, m)
            drawing.link(m, hot)
            m.valueChanged.connect(self._refresh)
            f[key] = m
            return m

        def chips(form, key, items, cur, label=None, box=None):
            ch = L.Chips()
            for v, text in items:
                ch.addItem(text, v)
            ch.setCurrentIndex(max(0, ch.findData(cur)))
            ch.currentIndexChanged.connect(self._refresh)
            if box is not None:
                box.addWidget(ch)
            else:
                form.addRow(label, ch)
            f[key] = ch
            return ch

        self.d_cw_plan = L.Drawing(_draw_cw_plan, 150, 120)
        self.d_cw_elev = L.Drawing(_draw_cw_elev, 150, 120)
        depth_tip = ("From the wall's OUTER face inwards — the frame stays "
                     f"flush with a wall below (up to its "
                     f"{compat.fmt_cm(t, 0)})")
        fold = L.Fold("Mullions", "cw.mullions")
        form = fold.form(self.d_cw_plan)
        measure(form, "cw_s", "Every", c["cw_s"], 0.30, 3.00, 0.05,
                "Their spacing, about (evened out along the wall)",
                self.d_cw_plan, "s")
        measure(form, "cw_mw", "Width", sz["mw"], 0.02, 0.30, 0.005,
                "Seen from outside", self.d_cw_plan, "mw")
        measure(form, "cw_md", "Depth", sz["md"], 0.02, 0.60, 0.005,
                depth_tip, self.d_cw_plan, "md")
        cl.addWidget(fold)
        self.fold_cw_m = fold

        fold = L.Fold("Corner & end posts", "cw.posts")
        form = fold.form()
        measure(form, "cw_pw", "Width", sz["pw"], 0.02, 0.30, 0.005,
                "The posts at its ends and corners (a corner's is cut on "
                "the mitre)", self.d_cw_plan, "pw")
        measure(form, "cw_pd", "Depth", sz["pd"], 0.02, 0.60, 0.005,
                depth_tip, self.d_cw_plan, "pd")
        cl.addWidget(fold)
        self.fold_cw_p = fold

        fold = L.Fold("Transoms & band", "cw.transoms")
        form = fold.form(self.d_cw_elev)
        chips(form, "cw_rows", ((0, "1"), (1, "2"), (2, "3"), (3, "4"),
                                (4, "5"), (5, "6")), c["cw_rows"],
              "Rows of panes")
        measure(form, "cw_tw", "Height", sz["tw"], 0.02, 0.30, 0.005,
                "The transoms' height, seen from outside", self.d_cw_elev,
                "tw")
        measure(form, "cw_td", "Depth", sz["td"], 0.02, 0.60, 0.005,
                "From 1 cm in from the outer face inwards",
                self.d_cw_elev, "td")
        chips(form, "cw_band", ((True, "Yes"), (False, "No")), c["cw_band"],
              "Band at each floor")
        measure(form, "cw_band_h", "Band over the floor", c["cw_band_h"],
                0.0, 1.50, 0.01,
                "How high the dark band rises over the floor (it covers the "
                "slab's edge under it) — 1.10 makes a parapet",
                self.d_cw_elev, "band")
        cl.addWidget(fold)
        self.fold_cw_t = fold

        fold = L.Fold("Glass", "cw.glass")
        form = fold.form()
        chips(form, "cw_glass", (("centre", "In the middle"),
                                 ("outside", "Near the outside")),
              c["cw_glass"], "Glass")
        # its transparency, in % (his ask, 2026-10-14)
        f_seen = L.Measure(round(c["cw_glass_tr"] * 100), 0, 95, 1, " %")
        f_seen.field.setDecimals(0)
        # (IngeTrazo draws the LINES behind a see-through face over it, so
        # any transparency still shows them; 0 % = a plain face that hides
        # everything behind — his test, 2026-10-14)
        f_seen.setToolTip("How much you see through it. 0 % = opaque glass "
                          "that hides everything behind it, the lines too "
                          "(IngeTrazo shows the lines behind any see-through "
                          "glass)")
        f_seen.valueChanged.connect(self._refresh)
        form.addRow("Transparency", f_seen)
        f["cw_glass_tr"] = f_seen
        if not edition.lite():
            chips(form, "cw_frame", (("dark", "Dark grey"),
                                     ("black", "Black"),
                                     ("silver", "Silver"),
                                     ("white", "White"),
                                     ("bronze", "Bronze")),
                  c["cw_frame"], "Frame")
            chips(form, "cw_glass_c", (("blue", "Blue"), ("clear", "Clear"),
                                       ("green", "Green"), ("grey", "Grey"),
                                       ("bronze", "Bronze")),
                  c["cw_glass_c"], "Tint")
            chips(form, "cw_band_c", (("dark", "Dark"), ("black", "Black"),
                                      ("grey", "Grey"), ("white", "White"),
                                      ("frame", "As the frame")),
                  c["cw_band_c"], "Band")
        cl.addWidget(fold)
        self.fold_cw_g = fold
        cl.addStretch(1)
        self.cw = f
        self.tabs.addTab(pg, "Curtain wall", "build")

    def _cw_values(self) -> dict:
        """The Curtain wall tab's values, as the record keeps them (a
        depth equal to the wall's thickness = 0: it follows the wall)."""
        if not self.cw:
            return {}
        t = round(self.f_t.value(), 3)
        out = {}
        for k, wdg in self.cw.items():
            if hasattr(wdg, "currentData"):
                out[k] = wdg.currentData()
            else:
                v = round(wdg.value(), 3)
                if k in ("cw_md", "cw_pd") and abs(v - t) < 1e-4:
                    v = 0.0
                if k == "cw_td" and abs(v - (t - 0.02)) < 1e-4:
                    v = 0.0
                if k == "cw_glass_tr":       # shown in %
                    v = round(wdg.value() / 100.0, 3)
                out[k] = v
        return out

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

    def _refresh(self, *_a) -> None:
        import math
        kind = self.wall.get("kind", "line")
        if kind == "circle":
            L = 2 * math.pi * float(self.wall["r"])
        elif self.f_len is not None:
            L = self.f_len.value()
        else:
            L = self.length0
        h = self._height()
        own = self.f_hmode.currentIndex() == 1
        self.f_h.setEnabled(own)
        _a, w = self.result_data()
        al = self.f_align.currentText()
        t_ = compat.fmt_cm(w['t'], 0)
        self.head.set_summary(["{" + t_ + "}", al,
                               f"{compat.fmt_len(L)} long",
                               "{" + compat.fmt_len(h) + "} high"])
        self.fold_t.set_pick(f"{t_} · {al}")
        self.fold_h.set_pick(("level" if not own else compat.fmt_len(h))
                             + (" · base "
                                + compat.fmt_level(w['base'], unit=False)
                                if abs(w["base"]) > 1e-6 else ""))
        self.fold_pos.set_pick(compat.fmt_len(L))
        self.d_size.set(align=w["align"], base=w["base"])
        self.plan.set(w)
        self.stats.set([(compat.fmt_len(L), "length"),
                        (compat.fmt_len(h), "height"),
                        (t_, "thickness"),
                        (compat.fmt_area(L * h), "face area")])
        self._cw_refresh(w, h)

    def _cw_refresh(self, w: dict, h: float) -> None:
        """The Curtain wall tab's drawings and fold lines, live."""
        if self.cw:
            from . import curtain as CW
            c, sz = CW.clean(w), CW.sizes(w)
            data = dict(sz, t=w["t"], s=c["cw_s"], glass=c["cw_glass"],
                        band=c["cw_band"], band_h=c["cw_band_h"],
                        rows=c["cw_rows"], h=h)
            self.d_cw_plan.set(**data)
            self.d_cw_elev.set(**data)
            self.fold_cw_m.set_pick(f"{compat.fmt_len(c['cw_s'])} · "
                                    + compat.fmt_cm2(sz['mw'], sz['md']))
            self.fold_cw_p.set_pick(compat.fmt_cm2(sz['pw'], sz['pd']))
            self.fold_cw_t.set_pick(
                f"{c['cw_rows'] + 1} row" + ("s" if c["cw_rows"] else "")
                + (f" · band {compat.fmt_num(c['cw_band_h'])}"
                   if c["cw_band"] else " · no band"))
            self.fold_cw_g.set_pick(("middle" if c["cw_glass"] == "centre"
                                     else "outside")
                                    + f" · {c['cw_glass_tr'] * 100:.0f} %")

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
        w.update(self._cw_values())  # a curtain wall's own (its tab)
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


class CurtainDialog(QDialog):
    """«More…» of a curtain wall with none selected (his ask, 2026-10-14):
    the same «Curtain wall» tab as a wall's own window, for the NEXT ones
    drawn. ``values()`` after ``exec()`` → the curtain keys (curtain.KEYS)."""

    _curtain_tab = WallDialog._curtain_tab
    _cw_values = WallDialog._cw_values
    _cw_refresh = WallDialog._cw_refresh

    class _T:                               # the wall's thickness, fixed here
        def __init__(self, t):
            self.t = t

        def value(self):
            return self.t

    def __init__(self, opts: dict, parent=None, count: int = 0) -> None:
        from . import look as L
        super().__init__(parent)
        self.opts = dict(opts)
        self.f_t = self._T(float(opts.get("t", 0.15)))
        self.cw = None
        self.setWindowTitle("Curtain wall")
        self.setMinimumWidth(560)
        L.dress(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(6)
        self.head = L.Header(_ic_wall, f"{count} curtain walls" if count > 1
                             else "Curtain wall", "wall")
        lay.addWidget(self.head)
        if count > 1:
            # several selected (his ask, 2026-10-14): the last edit's values;
            # OK = only what you change goes to all of them
            text = (f"Opened with the last curtain wall you edited. What you "
                    f"CHANGE here goes to all {count} selected — the rest of "
                    "each stays as it is. Depths are measured from the outer "
                    "face.")
        else:
            text = ("The details of the NEXT curtain walls you draw (a wall "
                    "drawn: double-click it — the same tab). Depths are "
                    "measured from the outer face.")
        lay.addWidget(L.hint(text))
        self.tabs = L.Tabs()
        lay.addWidget(self.tabs.bar)
        lay.addWidget(L.rule())
        self._curtain_tab(dict(self.opts, cw=True, side=1))
        lay.addWidget(self.tabs.stack, 1)
        lay.addWidget(L.rule())
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        L.ok_button(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._refresh()

    def values(self) -> dict:
        return self._cw_values()

    def _refresh(self, *_a) -> None:
        if not self.cw:
            return
        w = dict(self.opts, cw=True, side=1, **self._cw_values())
        h = 3.0
        self._cw_refresh(w, h)
        from . import curtain as CW
        c = CW.clean(w)
        self.head.set_summary([f"mullions every {compat.fmt_len(c['cw_s'])}",
                               "band " + (compat.fmt_len(c['cw_band_h'])
                                          if c["cw_band"] else "off"),
                               f"glass {c['cw_glass_tr'] * 100:.0f} %"])


def _ic_struct(t):
    def draw(p, r, _on):
        from PySide6.QtGui import QColor
        from . import look as L
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#3a2f1c"))
        p.drawRoundedRect(r, 8, 8)
        if t == "column":
            L.poly(p, [(15, 7), (25, 7), (25, 33), (15, 33)], L.GOLD, 2.2,
                   close=True)
        elif t == "beam":
            L.poly(p, [(5, 13), (35, 13), (35, 22), (5, 22)], L.GOLD, 2.2,
                   close=True)
            p.setPen(L.pen(L.GOLD, 2.0))
            p.drawLine(QPointF(9, 22), QPointF(9, 33))
            p.drawLine(QPointF(31, 22), QPointF(31, 33))
        elif t == "slab":
            L.poly(p, [(5, 17), (35, 17), (35, 24), (5, 24)], L.GOLD, 2.2,
                   close=True)
        elif t == "roof":
            L.poly(p, [(4, 28), (20, 10), (36, 28)], L.GOLD, 2.4)
            L.poly(p, [(9, 28), (9, 34), (31, 34), (31, 28)], L.GOLD, 1.8)
        else:
            L.poly(p, [(13, 6), (27, 6), (27, 22), (13, 22)], L.GOLD, 2.0,
                   close=True)
            L.poly(p, [(6, 22), (34, 22), (34, 32), (6, 32)], L.GOLD, 2.2,
                   close=True)
    return draw


def hole_text(h) -> str:
    """A slab opening in a few words: «1.20 × 2.40 m · 2.88 m²», «round
    Ø 0.80 m · 0.50 m²», «6 corners · 3.10 m²»."""
    import math
    from . import grips as G
    from . import structure as S
    pts = [tuple(p) for p in h]
    area = abs(S._area(pts))
    rnd = G.round_hole(pts)
    if rnd:
        return (f"round Ø {compat.fmt_len(rnd[2] * 2)} · "
                f"{compat.fmt_area(area)}")
    if len(pts) == 4:
        a, b = math.dist(pts[0], pts[1]), math.dist(pts[1], pts[2])
        return f"{compat.fmt_wh(a, b)} · {compat.fmt_area(area)}"
    return f"{len(pts)} corners · {compat.fmt_area(area)}"


def _pic_section(shape):
    def draw(p, r, _on):
        from . import look as L
        if shape == "round":
            p.setPen(L.pen(L.INK, 2.0))
            p.setBrush(L.colour("#8a8f9655"))
            p.drawEllipse(QPointF(30, 22), 15, 15)
            p.setBrush(Qt.NoBrush)
        else:
            L.poly(p, [(16, 8), (44, 8), (44, 36), (16, 36)], L.INK, 2.0,
                   fill="#8a8f9655")
    return draw


def _pic_roof(kind):
    def draw(p, r, _on):
        from . import look as L
        ink, acc = L.INK, L.ACCENT
        p.setPen(L.pen(L.DIM, 1.4))
        p.drawLine(QPointF(10, 38), QPointF(50, 38))
        if kind == "gable":
            L.poly(p, [(8, 26), (30, 8), (52, 26)], acc, 2.2)
            L.poly(p, [(12, 26), (12, 38), (48, 38), (48, 26)], ink, 1.6)
        elif kind == "hip":
            L.poly(p, [(8, 26), (22, 12), (38, 12), (52, 26)], acc, 2.2)
            L.poly(p, [(12, 26), (12, 38), (48, 38), (48, 26)], ink, 1.6)
        elif kind == "flat":
            L.poly(p, [(8, 22), (52, 22), (52, 26), (8, 26)], acc, 2.0,
                   close=True)
            L.poly(p, [(12, 26), (12, 38), (48, 38), (48, 26)], ink, 1.6)
        elif kind == "shed":
            L.poly(p, [(8, 26), (52, 12)], acc, 2.2)
            L.poly(p, [(12, 24), (12, 38), (48, 38), (48, 14)], ink, 1.6)
        else:                                       # hidden: a parapet
            L.poly(p, [(12, 14), (12, 38), (48, 38), (48, 14)], ink, 1.6)
            L.poly(p, [(14, 24), (30, 19), (46, 24)], acc, 2.0)
    return draw


def _draw_el_size(p, r, hot, d):
    """The element's section / thickness, its sizes hot."""
    from . import look as L
    t = d.get("t")
    if t == "column":
        if d.get("round"):
            p.setPen(L.pen(L.INK, 1.8))
            p.setBrush(L.colour("#8a8f9640"))
            p.drawEllipse(QPointF(70, 58), 34, 34)
            p.setBrush(Qt.NoBrush)
            L.dim(p, (36, 104), (104, 104), "Ø", hot == "w", at=(66, 118))
        else:
            L.poly(p, [(36, 24), (104, 24), (104, 92), (36, 92)], L.INK, 1.8,
                   fill="#8a8f9640")
            L.dim(p, (36, 104), (104, 104), "W", hot == "w", at=(66, 118))
            L.dim(p, (116, 24), (116, 92), "D", hot == "d", at=(121, 62))
    elif t == "beam":
        p.setPen(L.pen(L.DIM, 1.4))
        p.drawLine(QPointF(10, 26), QPointF(140, 26))
        L.poly(p, [(48, 26), (96, 26), (96, 94), (48, 94)], L.INK, 1.8,
               fill="#8a8f9640")
        L.dim(p, (48, 106), (96, 106), "W", hot == "w", at=(66, 120))
        L.dim(p, (108, 26), (108, 94), "H", hot == "h", at=(113, 64))
        L.text(p, 12, 20, "slab", L.MUTED, 7, False)
    elif t in ("slab", "roof"):
        L.poly(p, [(14, 48), (136, 48), (136, 66), (14, 66)], L.INK, 1.8,
               fill="#8a8f9640")
        L.dim(p, (124, 48), (124, 66), "t", hot == "t", at=(110, 61))
        p.setPen(L.pen(L.DIM, 1.2, dash=True))
        p.drawLine(QPointF(8, 84), QPointF(142, 84))
        L.text(p, 10, 98, "floor", L.MUTED, 7, False)
        if t == "slab":
            L.dim(p, (30, 48), (30, 84), "", hot == "offset")
            L.text(p, 34, 80, "top", L.GOLD if hot == "offset" else L.BLUE)
    else:                                            # footing
        L.poly(p, [(58, 14), (82, 14), (82, 46), (58, 46)], L.INK, 1.4)
        L.poly(p, [(26, 46), (114, 46), (114, 88), (26, 88)], L.INK, 1.8,
               fill="#8a8f9640")
        L.dim(p, (26, 100), (114, 100), "W", hot == "w", at=(66, 114))
        L.dim(p, (126, 46), (126, 88), "D", hot == "d", at=(131, 70))


class _ElView(QWidget):
    """The element at a glance, live: a column's section, a beam's cut, a
    slab's / roof's outline (its openings), a footing's plan."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(280, 220)
        self.e = None

    def set(self, e: dict) -> None:
        self.e = e
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        from PySide6.QtGui import QColor, QPainter
        from . import look as L
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(L.FIELD))
        try:
            if self.e is not None:
                self._paint(p, L)
        except Exception:  # noqa: BLE001 — a preview never breaks the window
            import traceback
            traceback.print_exc()
        finally:
            p.end()

    def _fit(self, pts):
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        rr = QRectF(self.rect()).adjusted(24, 20, -24, -20)
        k = min(rr.width() / max(x1 - x0, 1e-3), rr.height() / max(y1 - y0,
                                                                   1e-3))
        ox = rr.center().x() - (x1 - x0) * k / 2
        oy = rr.center().y() + (y1 - y0) * k / 2
        return lambda x, y: (ox + (x - x0) * k, oy - (y - y0) * k)

    def _paint(self, p, L) -> None:
        import math

        from . import structure as S
        e, t = self.e, self.e["type"]
        if t in ("slab", "roof"):
            outer = [tuple(c) for c in e["corners"]]
            holes = [[tuple(c) for c in h] for h in e.get("holes") or []] \
                if t == "slab" else []
            q = self._fit(outer)
            L.poly(p, [q(*c) for c in outer], L.INK, 1.8, close=True,
                   fill="#8a8f9640" if t == "slab" else "#e8742c26")
            for h in holes:
                L.poly(p, [q(*c) for c in h], L.ACCENT, 1.6, close=True,
                       fill="#1f2124")
            if t == "roof" and e.get("kind") in ("gable", "hip") \
                    and S.pitched_plan(e) != "rect":
                # an L / any plan: its hips / valleys / ridges
                p.setPen(L.pen(L.ACCENT, 1.4, dash=True))
                for a, b in S.roof_plan_lines(e):
                    p.drawLine(QPointF(*q(*a)), QPointF(*q(*b)))
            elif t == "roof" and e.get("kind") in ("gable", "hip"):
                cx = sum(c[0] for c in outer) / len(outer)
                cy = sum(c[1] for c in outer) / len(outer)
                p.setPen(L.pen(L.ACCENT, 1.4, dash=True))
                for c in outer:
                    a, b = q(*c), q(cx, cy)
                    p.drawLine(QPointF(*a), QPointF(*b))
            return
        if t == "beam":
            a, b = e["a"], e["b"]
            ln = math.dist(a, b)
            q = self._fit([(0, -0.6), (ln, 0.6)])
            L.poly(p, [q(0, -float(e["w"]) / 2), q(ln, -float(e["w"]) / 2),
                       q(ln, float(e["w"]) / 2), q(0, float(e["w"]) / 2)],
                   L.INK, 1.8, close=True, fill="#8a8f9640")
            L.text(p, self.width() / 2, self.height() - 10,
                   compat.fmt_len(ln),
                   L.BLUE, 9, True, align=Qt.AlignHCenter)
            return
        w = float(e.get("w", 0.3))
        d = w if t == "column" and e.get("shape") == "round" \
            else float(e.get("d", 0.3))
        q = self._fit([(-0.75, -0.75), (0.75, 0.75)] if max(w, d) < 1.5
                      else [(-w / 2 - 0.2, -d / 2 - 0.2), (w / 2 + 0.2,
                                                           d / 2 + 0.2)])
        if t == "column" and e.get("shape") == "round":
            c = q(0, 0)
            rad = abs(q(w / 2, 0)[0] - c[0])
            p.setPen(L.pen(L.INK, 1.8))
            p.setBrush(L.colour("#8a8f9640"))
            p.drawEllipse(QPointF(*c), rad, rad)
            p.setBrush(Qt.NoBrush)
            return
        ang = math.radians(float(e.get("angle", 0.0) or 0.0)) \
            if t == "column" else 0.0
        pts = []
        for x, y in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2),
                     (-w / 2, d / 2)):
            pts.append(q(x * math.cos(ang) - y * math.sin(ang),
                         x * math.sin(ang) + y * math.cos(ang)))
        L.poly(p, pts, L.INK, 1.8, close=True, fill="#8a8f9640")


#: the roof's types in its chips
ROOF_KINDS = (("gable", "Gable"), ("hip", "Hip"), ("flat", "Flat"),
              ("shed", "Shed"), ("hidden", "Hidden"))


class ElementDialog(QDialog):
    """A structural element's own window — a column, a beam, a slab, a
    footing, a roof: its sizes (the fields its type has), what it is and
    where; delete. ``result_data()`` after ``exec()`` → (action, element)
    — action "apply" | "delete" | "hide" | "pick:<i>".

    The window of 0.10.0 (look.py, as the stair's): a Geometry tab with
    folds and drawings (+ Selection, + Material), bars for the sizes, a live
    view of the element and its numbers. The record is the old window's."""

    def __init__(self, el: dict, level: dict, parent=None,
                 picks=()) -> None:
        """``picks``: «Select its row (5 columns)», «Select all … on this
        level» — a button each; it closes with action "pick:<i>"."""
        import math
        from . import look as L
        from . import structure as S
        super().__init__(parent)
        self.el = el = copy.deepcopy(el)     # defaults filled in: its own
        self.action = "apply"
        t = el["type"]
        self.t = t
        label = S.LABEL[t]
        self.setWindowTitle(label)
        self.setMinimumWidth(820)
        L.dress(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(6)
        self.head = L.Header(_ic_struct(t), el["name"], t, editable=True)
        self.f_name = self.head.name
        lay.addWidget(self.head)
        self.tabs = L.Tabs()
        self._axq_tabs = self.tabs
        lay.addWidget(self.tabs.bar)
        lay.addWidget(L.rule())
        self.fields: dict = {}
        self.rows: dict = {}

        pg, gl = L.page()
        self.d_size = L.Drawing(_draw_el_size, 150, 124)
        self.d_size.set(t=t, round=el.get("shape") == "round")

        def measure(form, key, label_, lo, hi, step=0.05, suffix=" m",
                    hot=None, fmax=None):
            """A bar over the usual sizes; the field takes up to ``fmax``
            (the old window's limit)."""
            w = L.Measure(float(el[key]), lo, hi, step, suffix)
            if fmax is not None:
                w.field.setMaximum(fmax)
                w.field.setValue(float(el[key]))
            self.fields[key] = w
            lab = QLabel(label_)
            form.addRow(lab, w)
            self.rows[key] = lab
            if hot:
                self.d_size.link(w, hot)
            w.valueChanged.connect(self._sync)
            return w

        if t == "column":
            fold = L.Fold("Section", "column.section")
            self.f_section = L.Chips(width=92)
            self.f_section.addItem("Rectangle", "rect", pic=_pic_section("rect"))
            self.f_section.addItem("Round", "round", pic=_pic_section("round"))
            self.f_section.setCurrentIndex(1 if el["shape"] == "round" else 0)
            fold.box.addWidget(self.f_section)
            form = fold.form(self.d_size)
            measure(form, "w", "Width / Ø", 0.05, 2.0, hot="w", fmax=5.0)
            measure(form, "d", "Depth", 0.05, 2.0, hot="d", fmax=5.0)
            gl.addWidget(fold)
            self.fold_main = fold
            fold = L.Fold("Height", "column.height")
            form = fold.form()
            self.f_hmode = L.Chips()
            self.f_hmode.addItem("To the slab above", "level")
            self.f_hmode.addItem("Its own height", "own")
            own = el.get("height", "level") != "level"
            self.f_hmode.setCurrentIndex(1 if own else 0)
            form.addRow("Height", self.f_hmode)
            self.f_h = L.metres(float(el["height"]) if own else 3.0, 0.2,
                                20.0)
            self.f_h.field.setMaximum(50.0)
            self.f_h.setValue(float(el["height"]) if own else 3.0)
            form.addRow("Its own", self.f_h)
            self.f_h.setEnabled(own)
            self.f_hmode.currentIndexChanged.connect(self._sync)
            self.f_h.valueChanged.connect(self._sync)
            self.f_section.currentIndexChanged.connect(self._sync)
            gl.addWidget(fold)
            self.fold_h = fold
            fold = L.Fold("Placement", "column.place")
            self.d_dial = L.Drawing(L.draw_dial, 150, 104)
            form = fold.form(self.d_dial)
            w = L.Measure(float(el["angle"]), -180.0, 180.0, 15.0, "°")
            w.setDecimals(1)
            self.fields["angle"] = w
            form.addRow("Angle", w)
            self.d_dial.link(w, "a")
            w.valueChanged.connect(self._sync)
            gl.addWidget(fold)
            self.fold_place = fold
        elif t == "beam":
            fold = L.Fold("Size", "beam.size")
            form = fold.form(self.d_size)
            measure(form, "w", "Width", 0.05, 1.5, hot="w", fmax=3.0)
            measure(form, "h", "Height", 0.05, 2.5, hot="h", fmax=5.0)
            form.addRow("Length", QLabel(
                compat.fmt_len(math.dist(el['a'], el['b']))))
            gl.addWidget(fold)
            self.fold_main = fold
            # its TOP (Badis, 2026-10-18: a lean-to's beams on 2.50 m
            # posts): under the slab above, or at a height of its own
            fold = L.Fold("Top", "beam.top")
            form = fold.form()
            self.f_zmode = L.Chips()
            self.f_zmode.addItem("Under the slab", "level",
                                 tip="Its top in the slab above, under the "
                                     "next floor (as before)")
            self.f_zmode.addItem("Its own height", "own",
                                 tip="Its top at the height you give, over "
                                     "the level's floor — a lean-to's beams "
                                     "on posts, a pergola")
            self.f_zmode.setCurrentIndex(1 if S.beam_own(el) else 0)
            form.addRow("Top", self.f_zmode)
            el.setdefault("zt", 2.50)
            measure(form, "zt", "Top at", 0.2, 6.0, fmax=50.0)
            self.f_zmode.currentIndexChanged.connect(self._sync)
            gl.addWidget(fold)
            self.fold_top = fold
        elif t == "slab":
            fold = L.Fold("Size", "slab.size")
            form = fold.form(self.d_size)
            measure(form, "t", "Thickness", 0.02, 1.0, 0.01, hot="t",
                    fmax=3.0)
            # up to 10 m: a slab as a CEILING (a plenum over it — a
            # customer's ask, 2026-10-13); the bar over the usual -2…4
            measure(form, "offset", "Top (from the floor)", -2.0, 4.0, 0.01,
                    hot="offset")
            self.fields["offset"].field.setRange(-5.0, 10.0)
            self.fields["offset"].setValue(float(el.get("offset", 0.0)))
            gl.addWidget(fold)
            self.fold_main = fold
            auto = (el.get("auto") or {}).get("dig")
            if auto:                    # made by ArchXQ (autoslabs)
                gl.addWidget(L.hint("Automatic — it follows its "
                                    "excavation's outline. Delete it and it "
                                    "stays away (Ctrl+Z brings it back)."))
            holes = el.get("holes") or []
            n = len(holes)
            self.f_clear = None
            self.f_holes = []
            if n:
                from PySide6.QtWidgets import QCheckBox
                fold = L.Fold("Openings", "slab.openings")
                form = fold.form()
                # each one on its own row: close just that one (his ask,
                # 2026-10-15 — before, only all of them at once)
                for i, h in enumerate(holes):
                    cb = QCheckBox("Close it")
                    cb.toggled.connect(self._sync)
                    form.addRow(f"{i + 1}  ·  {hole_text(h)}", cb)
                    self.f_holes.append(cb)
                if n > 1:
                    self.f_clear = QCheckBox(f"Close all {n}")
                    self.f_clear.toggled.connect(
                        lambda on: [cb.setChecked(on) for cb in self.f_holes])
                    form.addRow("", self.f_clear)
                form.addRow(L.hint(
                    "Select the slab: each opening has grips — its corners, "
                    "sides and middle."))
                fold.set_pick(f"{n}")
                gl.addWidget(fold)
        elif t == "roof":
            from PySide6.QtWidgets import QCheckBox
            fold = L.Fold("Type", "roof.type")
            self.f_kind = L.Chips(width=86)
            for k, text in ROOF_KINDS:
                self.f_kind.addItem(text, k, pic=_pic_roof(k))
            self.f_kind.setCurrentIndex(max(0, self.f_kind.findData(
                el["kind"])))
            fold.box.addWidget(self.f_kind)
            gl.addWidget(fold)
            self.fold_kind = fold
            fold = L.Fold("Slope & overhangs", "roof.size")
            form = fold.form(self.d_size)
            measure(form, "slope", "Slope", 5.0, 75.0, 5.0, "°")
            self.fields["slope"].setSingleStep(5.0)
            measure(form, "overhang", "Eaves overhang", 0.0, 3.0)
            el.setdefault("go", el.get("overhang", 0.5))
            measure(form, "go", "Gable ends' overhang", 0.0, 3.0)
            measure(form, "t", "Thickness", 0.02, 1.0, 0.01, hot="t")
            gl.addWidget(fold)
            self.fold_main = fold
            # HEIGHT (Badis, 2026-10-18: a lean-to lower than the house):
            # on the walls' top, or its eaves at a height of their own
            fold = L.Fold("Height", "roof.height")
            form = fold.form()
            self.f_zmode = L.Chips()
            self.f_zmode.addItem("On the walls", "walls",
                                 tip="It rests on the top of its level's "
                                     "walls (and fills the wall up to it)")
            self.f_zmode.addItem("Its own height", "own",
                                 tip="Its eaves at the height you give, over "
                                     "the level's floor — a lean-to on "
                                     "columns, a porch lower than the house. "
                                     "No wall is filled up to it")
            self.f_zmode.setCurrentIndex(1 if S.own_height(el) else 0)
            form.addRow("Height", self.f_zmode)
            el.setdefault("zh", 2.50)
            measure(form, "zh", "Eaves at", 0.5, 12.0, fmax=50.0)
            self.rows["zh"].setToolTip(
                "The height of its eaves (the low edge, for a Shed) over the "
                "level's floor — where its underside meets the walls' / "
                "beams' outer line")
            self.zh_note = L.hint("")
            form.addRow("", self.zh_note)
            self.f_zmode.currentIndexChanged.connect(self._sync)
            gl.addWidget(fold)
            self.fold_height = fold
            fold = L.Fold("Ridge & fall", "roof.ridge")
            form = fold.form()
            self.f_ridge = L.Chips()
            self.f_ridge.addItem("Along the long side", "long")
            self.f_ridge.addItem("Along the short side", "short")
            self.f_ridge.setCurrentIndex(0 if el["ridge"] == "long" else 1)
            self.rows["ridge"] = QLabel("Ridge")
            form.addRow(self.rows["ridge"], self.f_ridge)
            # an L (roof_l.py — Badis's permit, 2026-10-16): which wing
            # keeps its gable at the corner; the other runs into it
            from . import roof_l
            self._is_l = roof_l.is_l(el["corners"])
            self.f_main = L.Chips()
            self.f_main.addItem("The long one", "long",
                                tip="The longer wing keeps its gable at the "
                                    "corner; the other one runs into it")
            self.f_main.addItem("The other one", "other",
                                tip="The shorter wing keeps its gable at the "
                                    "corner")
            self.f_main.setCurrentIndex(1 if el.get("main") == "other" else 0)
            self.rows["main"] = QLabel("Main wing")
            form.addRow(self.rows["main"], self.f_main)
            from . import roof_any
            if self._is_l or (len(el["corners"]) >= 3 and not
                              roof_any.is_rect(el["corners"])):
                # an L / any plan: hip or gable (or flat)
                for i in range(self.f_kind.count()):
                    if self.f_kind.itemData(i) in ("shed", "hidden"):
                        self.f_kind.setItemEnabled(i, False)
            self.f_fall = L.Chips()
            self.f_fall.addItem("This side", "right")
            self.f_fall.addItem("The other side", "left")
            self.f_fall.setCurrentIndex(1 if el.get("fall") == "left" else 0)
            self.rows["fall"] = QLabel("Falls to")
            form.addRow(self.rows["fall"], self.f_fall)
            self.f_slopes = L.Chips(width=60)
            self.f_slopes.addItem("Two", 2)
            self.f_slopes.addItem("One", 1)
            self.f_slopes.setCurrentIndex(1 if el.get("slopes") == 1 else 0)
            self.rows["slopes"] = QLabel("Slopes")
            form.addRow(self.rows["slopes"], self.f_slopes)
            gl.addWidget(fold)
            self.fold_ridge = fold
            fold = L.Fold("Parapet & gutter", "roof.hidden")
            form = fold.form()
            el.setdefault("gutter", 0.30)
            measure(form, "gutter", "Gutter", 0.10, 1.0)
            self.f_pauto = QCheckBox("Auto — just hides the roof")
            self.f_pauto.setChecked(bool(el.get("pauto", True)))
            self.rows["pauto"] = QLabel("")
            form.addRow(self.rows["pauto"], self.f_pauto)
            if el["kind"] == "hidden" and el.get("pauto", True):
                el["parapet"] = S.hidden_height(el)  # what it is now
            measure(form, "parapet", "Parapet", 0.0, 3.0)
            gl.addWidget(fold)
            self.fold_hidden = fold
            for c in (self.f_kind, self.f_ridge, self.f_fall, self.f_slopes,
                      self.f_main):
                c.currentIndexChanged.connect(self._sync)
            self.f_pauto.toggled.connect(self._sync)
        else:                                     # footing
            fold = L.Fold("Size", "footing.size")
            form = fold.form(self.d_size)
            measure(form, "w", "Width", 0.1, 5.0, hot="w", fmax=10.0)
            measure(form, "d", "Depth", 0.05, 3.0, hot="d", fmax=5.0)
            form.addRow("Kind", QLabel("Pad (under a column)"
                                       if el.get("kind") == "pad"
                                       else "Strip (under a wall)"))
            gl.addWidget(fold)
            self.fold_main = fold
        gl.addWidget(L.hint(f"Level: {level['name']}"))
        gl.addStretch(1)
        self.tabs.addTab(pg, "Geometry", "geometry")

        if picks:          # select the others, then change them all at once
            pg, sl = L.page()
            fold = L.Fold("Select others", f"{t}.picks")
            for i, text in enumerate(picks):
                b = QPushButton(text)
                b.setObjectName("axqChip")
                b.setToolTip("Closes this window with them selected: the "
                             "options bar and the library change them all "
                             "(one Ctrl+Z)")
                b.clicked.connect(lambda _c=False, i=i: self._pick(i))
                fold.box.addWidget(b)
            sl.addWidget(fold)
            sl.addStretch(1)
            self.tabs.addTab(pg, "Selection", "position")
        self._own = self.tabs.count()

        # ---- the pages + the view beside them ------------------------------------
        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self.tabs.stack, 5)
        card = L.Card("Plan" if t in ("slab", "roof") else
                      "Section" if t in ("column", "beam") else "Plan")
        self.view = _ElView()
        card.box.addWidget(self.view, 1)
        self.stats = L.Stats(4)
        card.box.addWidget(self.stats)
        self.side = card
        body.addWidget(card, 4)
        lay.addLayout(body, 1)
        self.tabs.currentChanged.connect(
            lambda i: self.side.setVisible(i < self._own))

        # ---- the buttons ---------------------------------------------------------
        lay.addWidget(L.rule())
        acts = QHBoxLayout()
        acts.addWidget(hide_button(self))
        b_del = QPushButton(tr(f"Delete {label.lower()}"))
        b_del.setObjectName("axqDanger")
        b_del.clicked.connect(self._delete)
        acts.addWidget(b_del)
        acts.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_apply(self, bb)
        L.ok_button(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        acts.addWidget(bb)
        lay.addLayout(acts)
        self._sync()

    # -- live ------------------------------------------------------------------------
    def _sync(self, *_a) -> None:
        import math
        from . import structure as S
        e = self._record()
        t = e["type"]
        self.view.set(e)
        if t == "column":
            rnd = e["shape"] == "round"
            self.d_size.set(round=rnd)
            self.fields["d"].setVisible(not rnd)
            self.rows["d"].setVisible(not rnd)
            self.f_h.setEnabled(e["height"] != "level")
            metric = compat.doc_length_unit() == "m"
            h = "to the slab" if e["height"] == "level" \
                else compat.fmt_len(e['height'])
            if metric:
                sec = (f"Ø {e['w']:.2f}" if rnd
                       else f"{e['w']:.2f} × {e['d']:.2f}")
                sec_m = sec + " m"
            else:                       # feet / inches: the marks say it
                sec = sec_m = (f"Ø {compat.fmt_len(e['w'])}" if rnd
                               else compat.fmt_wh(e['w'], e['d']))
            self.head.set_summary(["{" + sec_m + "}", h,
                                   f"{e['angle'] % 360:.0f}°"])
            self.fold_main.set_pick(sec)
            self.fold_h.set_pick(h)
            self.fold_place.set_pick(f"{e['angle'] % 360:.0f}°")
            self.d_dial.set(a=e["angle"])
            area = math.pi * e["w"] ** 2 / 4 if rnd else e["w"] * e["d"]
            self.stats.set([(sec_m, "section"),
                            (compat.fmt_area(area, 3), "area"),
                            (h, "height")])
        elif t == "beam":
            ln = math.dist(e["a"], e["b"])
            self.head.set_summary(["{" + compat.fmt_wh(e['w'], e['h']) + "}",
                                   f"{compat.fmt_len(ln)} long"])
            self.fold_main.set_pick(
                f"{e['w']:.2f} × {e['h']:.2f}"
                if compat.doc_length_unit() == "m"
                else compat.fmt_wh(e['w'], e['h']))
            self.stats.set([(compat.fmt_len(e['w']), "width"),
                            (compat.fmt_len(e['h']), "height"),
                            (compat.fmt_len(ln), "length"),
                            (compat.fmt_volume(e['w'] * e['h'] * ln, 2,
                                               group=False), "concrete")])
            own = e.get("zmode") == "own"
            self.fields["zt"].setEnabled(own)
            self.fold_top.set_pick(compat.fmt_len(e["zt"]) if own
                                   else "Under the slab")
        elif t == "slab":
            area = abs(S._area(e["corners"])) - sum(
                abs(S._area(h)) for h in e.get("holes") or [])
            n = len(e.get("holes") or [])
            self.head.set_summary(["{" + compat.fmt_area(area) + "}",
                                   f"{compat.fmt_cm(e['t'], 0)} thick",
                                   f"{n} opening" + ("" if n == 1 else "s")])
            self.fold_main.set_pick(compat.fmt_cm(e['t'], 0))
            self.stats.set([(compat.fmt_area(area), "area"),
                            (compat.fmt_len(e['t']), "thickness"),
                            (compat.fmt_volume(area * e['t'], 2,
                                               group=False), "concrete"),
                            (f"{n}", "openings")])
        elif t == "roof":
            k = e["kind"]
            self.fold_kind.set_pick(self.f_kind.currentText())
            sloped = k in ("gable", "hip", "shed")
            is_l = getattr(self, "_is_l", False)
            for key, on in (("slope", sloped or k == "hidden"),
                            ("overhang", k != "hidden"),
                            ("go", k == "gable"),
                            ("ridge", k == "gable" and not is_l),
                            ("main", k == "gable" and is_l),
                            ("fall", k in ("shed", "hidden")),
                            ("slopes", k == "hidden")):
                (self.fields.get(key) or getattr(self, f"f_{key}")
                 ).setVisible(on)
                self.rows[key].setVisible(on)
            self.fold_ridge.setVisible(k in ("gable", "shed", "hidden"))
            self.fold_hidden.setVisible(k in ("flat", "hidden"))
            own = self.f_zmode.currentData() == "own"
            self.fields["zh"].setEnabled(own)
            self.fold_height.set_pick(compat.fmt_len(e["zh"]) if own
                                      else "On the walls")
            self.zh_note.setText(self._roof_heights(e) if own else
                                 "Its eaves at the top of the level's walls.")
            hid = k == "hidden"
            for key in ("gutter",):
                self.fields[key].setVisible(hid)
                self.rows[key].setVisible(hid)
            self.f_pauto.setVisible(hid)
            self.fields["parapet"].setEnabled(
                not (hid and self.f_pauto.isChecked()))
            area = abs(S._area(e["corners"]))
            self.head.set_summary([self.f_kind.currentText(),
                                   "{" + f"{e['slope']:.0f}°" + "}"
                                   if sloped else "", compat.fmt_area(area)])
            self.fold_main.set_pick(f"{e['slope']:.0f}° · "
                                    f"{compat.fmt_len(e['overhang'])}")
            self.stats.set([(compat.fmt_area(area), "covers (no eaves)"),
                            (f"{e['slope']:.0f}°", "slope"),
                            (compat.fmt_len(e['overhang']), "eaves")])
        else:
            self.head.set_summary(["{" + compat.fmt_wh(e['w'], e['d']) + "}",
                                   "pad" if e.get("kind") == "pad"
                                   else "strip"])
            self.fold_main.set_pick(
                f"{e['w']:.2f} × {e['d']:.2f}"
                if compat.doc_length_unit() == "m"
                else compat.fmt_wh(e['w'], e['d']))
            self.stats.set([(compat.fmt_len(e['w']), "width"),
                            (compat.fmt_len(e['d']), "depth")])

    @staticmethod
    def _roof_heights(e: dict) -> str:
        """Where its top lands, at its own height: a Shed's high edge, a
        gable / hip's ridge (over the level's floor, to the underside)."""
        import math
        from . import structure as S
        zh, k = float(e["zh"]), e["kind"]
        if k not in ("shed", "gable", "hip") or len(e["corners"]) != 4:
            return f"Its underside at {compat.fmt_len(zh)} over the floor."
        _c, _u, ha, _v, hb = S.rect_frame(e["corners"])
        along = ha >= hb
        if k == "gable" and e.get("ridge", "long") == "short":
            along = not along
        across = 2 * (hb if along else ha)          # the span between eaves
        tan = math.tan(math.radians(float(e["slope"])))
        if k == "shed":
            return (f"Low edge {compat.fmt_len(zh)} → high edge "
                    f"{compat.fmt_len(zh + across * tan)} (over the floor, "
                    "at the walls' line).")
        return (f"Eaves {compat.fmt_len(zh)} → ridge "
                f"{compat.fmt_len(zh + across / 2 * tan)} (over the floor).")

    def _pick(self, i: int) -> None:
        self.action = f"pick:{i}"
        self.accept()

    def _delete(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, "Delete?", f"Delete «{self.el['name']}»? (Ctrl+Z "
                "brings it back)", QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel) == QMessageBox.Yes:
            self.action = "delete"
            self.accept()

    def _record(self) -> dict:
        e = dict(self.el)
        e["name"] = self.f_name.text().strip() or self.el["name"]
        for key, w in self.fields.items():
            e[key] = round(w.value(), 3)
        if e["type"] == "column":
            e["shape"] = self.f_section.currentData()
            e["height"] = "level" if self.f_hmode.currentIndex() == 0 \
                else round(self.f_h.value(), 3)
        if e["type"] == "beam":
            e["zmode"] = self.f_zmode.currentData()
        if e["type"] == "roof":
            was = self.el["kind"]
            e["kind"] = self.f_kind.currentData()
            e["ridge"] = self.f_ridge.currentData()
            if getattr(self, "_is_l", False):
                e["main"] = self.f_main.currentData()
            e["fall"] = self.f_fall.currentData()
            e["slopes"] = int(self.f_slopes.currentData())
            e["pauto"] = self.f_pauto.isChecked()
            e["zmode"] = self.f_zmode.currentData()
            # turned hidden: sheets' 10° / back from hidden: tiles' 30° —
            # unless the slope was changed here too
            if e["kind"] != was and abs(e["slope"] - self.el["slope"]) < 1e-6:
                if e["kind"] == "hidden":
                    e["slope"] = 10.0
                elif was == "hidden" and e["kind"] != "flat":
                    e["slope"] = 30.0
        if e["type"] == "slab" and getattr(self, "f_holes", None):
            e["holes"] = [h for h, cb in zip(self.el.get("holes") or [],
                                             self.f_holes)
                          if not cb.isChecked()]
        return e

    def result_data(self):
        return self.action, self._record()


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
        lay.setContentsMargins(14, 10, 14, 12)
        look_head(self, lay, "rooms", f"Rooms — {level['name']}", "rooms",
                  "Found from the walls: a name for each one.")
        self.table = QTableWidget(len(rooms), 3)
        self.table.setHorizontalHeaderLabels(["Name", "Area", "Perimeter"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        for i, r in enumerate(rooms):
            self.table.setItem(i, 0, QTableWidgetItem(r["name"]))
            for j, v in ((1, compat.fmt_area(r['area'])),
                         (2, compat.fmt_len(r['perimeter']))):
                it = QTableWidgetItem(v)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, j, it)
        lay.addWidget(self.table, 1)
        net = sum(r["area"] for r in rooms)
        lay.addWidget(QLabel(f"Net {compat.fmt_area(net)}   ·   Gross "
                             f"{compat.fmt_area(gross)} "
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


def _lib_pic(fn):
    """A library card's picture (drawn in 96×96) as a chip's (look.Chips)."""
    def draw(p, r, _on):
        s = min(r.width(), r.height()) / 96.0
        p.translate(r.center().x() - 48 * s, r.center().y() - 48 * s)
        p.scale(s, s)
        fn(p)
    return draw


def _ic_opening(kind):
    def draw(p, r, _on):
        from PySide6.QtGui import QColor
        from . import look as L
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#3a2f1c"))
        p.drawRoundedRect(r, 8, 8)
        if kind == "door":
            L.poly(p, [(12, 33), (12, 8), (28, 8), (28, 33)], L.GOLD, 2.4)
            p.setPen(L.pen(L.GOLD, 2.0))
            p.drawLine(QPointF(24, 20), QPointF(24, 23))
        else:
            L.poly(p, [(8, 9), (32, 9), (32, 31), (8, 31)], L.GOLD, 2.4,
                   close=True)
            p.setPen(L.pen(L.GOLD, 1.8))
            p.drawLine(QPointF(20, 9), QPointF(20, 31))
    return draw


def _draw_size(p, r, hot, d):
    """The opening from the front: its width, height and sill."""
    from . import look as L
    door = d.get("door", False)
    floor = 104
    x0, x1 = 34, 116
    top, bot = (22, floor) if door else (20, 66)
    p.setPen(L.pen(L.DIM, 2.0))
    p.drawLine(QPointF(8, floor), QPointF(142, floor))
    L.poly(p, [(x0, top), (x1, top), (x1, bot), (x0, bot)], L.INK, 1.6,
           fill="#5bc8e826")
    L.dim(p, (x0, 12), (x1, 12), "W", hot == "w", at=(70, 9))
    L.dim(p, (128, top), (128, bot), "H", hot == "h", at=(132, (top + bot) / 2 + 4))
    if not door:
        L.dim(p, (20, bot), (20, floor), "", hot == "sill")
        L.text(p, 4, (bot + floor) / 2 + 4, "sill",
               L.GOLD if hot == "sill" else L.BLUE, 7)


def _draw_on_wall(p, r, hot, d):
    """The wall from the front, the opening on it: where along it."""
    from . import look as L
    L.poly(p, [(8, 30), (142, 30), (142, 92), (8, 92)], L.INK, 1.4,
           fill="#8a8f9626")
    f = max(0.0, min(1.0, float(d.get("f", 0.5))))
    w = max(10.0, min(60.0, float(d.get("wf", 0.2)) * 134))
    cx = 8 + f * 134
    L.poly(p, [(cx - w / 2, 46), (cx + w / 2, 46), (cx + w / 2, 92),
               (cx - w / 2, 92)], L.ACCENT, 1.8, fill="#e8742c33")
    L.dim(p, (8, 104), (cx, 104), "", hot == "pos")
    L.text(p, (8 + cx) / 2, 118, "along", L.GOLD if hot == "pos" else L.BLUE,
           7, align=Qt.AlignHCenter)
    p.setPen(L.pen(L.GOLD if hot == "pos" else L.BLUE, 1.0, dash=True))
    p.drawLine(QPointF(cx, 40), QPointF(cx, 104))


class _Front(QWidget):
    """The opening seen from the front, live: its frame, its leaves (how
    they open), a shopfront's door, transom, base, sign and shutter."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(280, 230)
        self.o = None

    def set(self, o: dict) -> None:
        self.o = o
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        from PySide6.QtGui import QColor, QPainter
        from . import look as L
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(L.FIELD))
        try:
            if self.o is not None:
                self._paint(p, L)
        except Exception:  # noqa: BLE001 — a preview never breaks the window
            import traceback
            traceback.print_exc()
        finally:
            p.end()

    def _paint(self, p, L) -> None:
        from PySide6.QtGui import QColor
        o = self.o
        w, h = float(o["w"]), float(o["h"])
        sill = 0.0 if o["kind"] == "door" else float(o.get("sill", 0.0))
        shop = o.get("op") == "shop"
        sign = shop and bool(o.get("sign"))
        top = sill + h + (0.45 if sign else 0.0) + (0.25 if shop and
                                                    o.get("shutter") else 0)
        rr = QRectF(self.rect()).adjusted(22, 16, -22, -24)
        k = min(rr.width() / max(w, 0.3), rr.height() / max(top, 0.3)) * 0.92
        ox = rr.center().x() - w * k / 2
        oy = rr.bottom()

        def q(x, z):
            return QPointF(ox + x * k, oy - z * k)

        def box(x0, z0, x1, z1, col=L.INK, fill=None, width=1.6):
            L.poly(p, [(q(x0, z0).x(), q(x0, z0).y()), (q(x1, z0).x(), q(x1, z0).y()),
                       (q(x1, z1).x(), q(x1, z1).y()), (q(x0, z1).x(), q(x0, z1).y())],
                   col, width, close=True, fill=fill)
        glass = "#5bc8e830"
        p.setPen(L.pen(L.DIM, 2.0))
        p.drawLine(QPointF(rr.left() - 10, oy), QPointF(rr.right() + 10, oy))
        z0, z1 = sill, sill + h
        if shop:
            base = float(o.get("base", 0.0) or 0.0)
            dh = float(o.get("dh", 2.2) or 2.2)
            # from its sill: a shop window may start above the floor (his
            # screen, 2026-10-13: drawn from the floor at sill 0.65)
            if base > 0.01:
                box(0, z0, w, z0 + base, L.INK, "#8a8f9655")
            box(0, z0 + base, w, z1, L.INK, glass)
            dh = min(z0 + dh, z1)
            if o["kind"] == "door":
                dw = min(1.8 if o.get("shop_door", "double") != "single"
                         else 1.0, w * 0.8)
                at = o.get("door_at", "centre")
                dx = {"left": 0.15, "right": w - dw - 0.15}.get(
                    at, (w - dw) / 2)
                dx = max(0.0, min(dx, w - dw))
                box(dx, z0, dx + dw, dh, L.ACCENT, None, 2.2)
                if o.get("shop_door", "double") == "double":
                    p.setPen(L.pen(L.ACCENT, 1.6))
                    p.drawLine(q(dx + dw / 2, z0), q(dx + dw / 2, dh))
                if o.get("transom", True):
                    p.setPen(L.pen(L.INK, 1.4))
                    p.drawLine(q(0, dh), q(w, dh))
            elif o.get("transom", True):
                p.setPen(L.pen(L.ACCENT, 2.0))
                p.drawLine(q(0, dh), q(w, dh))
            if sign:
                box(0, z1, w, z1 + 0.45, L.INK, "#c9cdd240")
            if o.get("shutter"):
                zt = z1 + (0.45 if sign else 0.0)
                box(0, zt, w, zt + 0.25, L.INK, "#6b707866")
            return
        op = o.get("op") or ("swing" if o["kind"] == "door" else "fixed")
        box(0, z0, w, z1, L.INK, glass if o["kind"] == "window"
            or o.get("leaf") == "glass" else "#8a8f9633")
        n = int(o.get("leaves", 1) or 1)
        if o["kind"] == "door" and op == "garage":
            # its panels / slats across, as the front shows them
            gk = o.get("garage", "sectional")      # (k is the drawing's scale)
            rows = 1 if gk == "tilt" else (12 if gk == "rollup" else 4)
            p.setPen(L.pen(L.INK, 1.0 if gk == "rollup" else 1.4))
            for i in range(1, rows):
                z = z0 + (z1 - z0) * i / rows
                p.drawLine(q(0, z), q(w, z))
            if gk == "tilt":
                for i in range(1, 4):
                    p.drawLine(q(w * i / 4, z0), q(w * i / 4, z1))
            if o.get("gwin") and gk != "rollup":       # its row of windows
                k_ = max(3, round(w / 0.62))
                hh = min(0.36, (z1 - z0) * 0.17)
                for i in range(k_):
                    cx = w * (i + 0.5) / k_
                    hw = w / k_ * 0.34
                    box(cx - hw, z1 - 0.10 - hh, cx + hw, z1 - 0.10, L.INK,
                        glass)
            self._arrow(p, L, q(w * 0.5, z0 + (z1 - z0) * 0.25),
                        q(w * 0.5, z0 + (z1 - z0) * 0.75))
            return
        if o["kind"] == "door":
            if op == "sliding":
                n = max(n, 1)
                for i in range(n + 1):
                    x = w * i / max(n, 1)
                    p.setPen(L.pen(L.INK, 1.4))
                    p.drawLine(q(x, z0), q(x, z1))
                self._arrow(p, L, q(w * 0.3, (z0 + z1) / 2), q(w * 0.7, (z0 + z1) / 2))
            else:
                hinge_r = o.get("swing") == "right"
                for i in range(n):
                    a, b = w * i / n, w * (i + 1) / n
                    if n == 2:
                        hinge_r = i == 1
                    hx, fx = (b, a) if hinge_r else (a, b)
                    p.setPen(L.pen(L.BLUE, 1.2, dash=True))
                    p.drawLine(q(fx, z0), q(hx, (z0 + z1) / 2))
                    p.drawLine(q(fx, z1), q(hx, (z0 + z1) / 2))
                    p.setPen(L.pen(L.INK, 1.4))
                    p.drawLine(q(b, z0), q(b, z1))
            return
        if op == "sliding":
            for i in range(1, n):
                p.setPen(L.pen(L.INK, 1.6))
                p.drawLine(q(w * i / n, z0), q(w * i / n, z1))
            self._arrow(p, L, q(w * 0.35, (z0 + z1) / 2), q(w * 0.65, (z0 + z1) / 2))
        elif op == "casement":
            for i in range(n):
                a, b = w * i / n, w * (i + 1) / n
                hinge_r = (o.get("swing") == "right") if n == 1 else i == 1
                hx, fx = (b, a) if hinge_r else (a, b)
                p.setPen(L.pen(L.BLUE, 1.2, dash=True))
                p.drawLine(q(fx, z0), q(hx, (z0 + z1) / 2))
                p.drawLine(q(fx, z1), q(hx, (z0 + z1) / 2))
                p.setPen(L.pen(L.INK, 1.4))
                p.drawLine(q(b, z0), q(b, z1))
        elif op == "awning":
            p.setPen(L.pen(L.BLUE, 1.2, dash=True))
            p.drawLine(q(0, z0), q(w / 2, z1))
            p.drawLine(q(w, z0), q(w / 2, z1))

    @staticmethod
    def _arrow(p, L, a, b) -> None:
        import math
        p.setPen(L.pen(L.ACCENT, 2.2))
        p.drawLine(a, b)
        ang = math.atan2(b.y() - a.y(), b.x() - a.x())
        for s in (-1, 1):
            p.drawLine(b, QPointF(b.x() - 9 * math.cos(ang + s * 0.5),
                                  b.y() - 9 * math.sin(ang + s * 0.5)))


#: the types in the window's chips: (value, label, library picture)
DOOR_TYPES = ((("swing", "solid"), "Swing", "_door_swing"),
              (("sliding", "solid"), "Sliding", "_door_sliding"),
              (("sliding", "glass"), "Glass sliding", "_door_glass"),
              (("shop", "glass"), "Shopfront", "_door_shop"),
              (("garage", "solid"), "Garage door", "_door_garage"))
WINDOW_TYPES = (("fixed", "Fixed", "_win_fixed"),
                ("sliding", "Sliding", "_win_sliding"),
                ("casement", "Casement", "_win_casement"),
                ("awning", "Awning", "_win_awning"),
                ("shop", "Shop window", "_win_shop"))


class OpeningDialog(QDialog):
    """A door's / window's / void's own window. ``result_data()`` →
    (action, opening) — "apply" | "delete".

    The window of 0.10.0 (look.py, as the stair's): tabs Type · Size ·
    Position; the types as the library's pictures, the leaves and how they
    open, a shopfront's / shop window's own options (the library's parts),
    sizes and place beside drawings, a live front view with its numbers and
    — a door — NBR 9050's free width. The record is the old window's (+ the
    library's keys it now edits too: open, the shopfront's)."""

    def __init__(self, op: dict, wall: dict, parent=None) -> None:
        from . import library as LB
        from . import look as L
        from . import structure as S
        from . import walls as W
        super().__init__(parent)
        self.op = copy.deepcopy(op)
        self.action = "apply"
        self.kind = op["kind"]
        label = S.OPENING_LABEL[op["kind"]]
        self.label = label
        self.setWindowTitle(label)
        self.setMinimumWidth(860)
        L.dress(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(6)
        self.head = L.Header(_ic_opening("door" if self.kind == "door"
                                         else "window"),
                             op["name"], op["kind"], editable=True)
        self.f_name = self.head.name
        lay.addWidget(self.head)
        self.tabs = L.Tabs()
        self._axq_tabs = self.tabs
        lay.addWidget(self.tabs.bar)
        lay.addWidget(L.rule())

        # ---- Type ----------------------------------------------------------------
        self.f_type = None
        self.parts = []                       # (Part, label, Chips)
        self.sizes = {}                       # a shop's dh / base
        if self.kind in ("door", "window"):
            pg, tl = L.page()
            self.fold_type = L.Fold("Type", f"{self.kind}.type")
            self.f_type = L.Chips(width=96)
            types = DOOR_TYPES if self.kind == "door" else WINDOW_TYPES
            for val, text, pic in types:
                self.f_type.addItem(text, val, pic=_lib_pic(getattr(LB, pic)))
            if self.kind == "door":
                cur = ("shop", "glass") if op.get("op") == "shop" else (
                    ("garage", "solid")) if op.get("op") == "garage" else (
                    ("sliding", "glass" if op.get("leaf") == "glass"
                     else "solid") if op.get("op") == "sliding"
                    else ("swing", "solid"))
            else:
                cur = op.get("op") or "fixed"
            self.f_type.setCurrentIndex(max(0, self.f_type.findData(cur)))
            self.fold_type.box.addWidget(self.f_type)
            tl.addWidget(self.fold_type)
            # the leaves and how they open
            self.fold_leaves = L.Fold("Leaves & opening", f"{self.kind}.leaves")
            form = self.fold_leaves.form()
            self.f_leaves = L.Chips(width=48)
            for k in (1, 2, 3, 4):
                self.f_leaves.addItem(str(k), k)
            from .structure import window_leaves
            n = window_leaves(op) if self.kind == "window" else (
                2 if int(op.get("leaves", 1) or 1) == 2 else 1)
            self.f_leaves.setCurrentIndex(self.f_leaves.findData(n))
            self.r_leaves = QLabel("Leaves")
            form.addRow(self.r_leaves, self.f_leaves)
            self.f_swing = L.Chips(width=70)
            self.f_swing.addItem("Left", "left")
            self.f_swing.addItem("Right", "right")
            self.f_swing.setCurrentIndex(1 if op.get("swing") == "right" else 0)
            self.r_swing = QLabel("Hinge")
            form.addRow(self.r_swing, self.f_swing)
            self.f_out = L.Chips(width=70)
            self.f_out.addItem("In", False)
            self.f_out.addItem("Out", True)
            self.f_out.setCurrentIndex(1 if op.get("out") else 0)
            self.f_out.setToolTip("The side it opens to: the wall's inside "
                                  "or its outside")
            self.r_out = QLabel("Opens")
            form.addRow(self.r_out, self.f_out)
            # a garage door's kind (Badis, 2026-10-18)
            from .structure import garage_kind
            self.f_garage = L.Chips(width=96)
            for k, text in (("sectional", "Sectional"), ("rollup", "Roll-up"),
                            ("tilt", "Up-and-over")):
                self.f_garage.addItem(text, k)
            self.f_garage.setCurrentIndex(max(0, self.f_garage.findData(
                garage_kind(op))))
            self.r_garage = QLabel("Kind")
            form.addRow(self.r_garage, self.f_garage)
            from .structure import garage_finish
            self.f_gfinish = L.Chips(width=96)
            for k, text in (("steel", "Steel"), ("white", "White"),
                            ("anthracite", "Anthracite"), ("wood", "Wood")):
                self.f_gfinish.addItem(text, k)
            self.f_gfinish.setCurrentIndex(max(0, self.f_gfinish.findData(
                garage_finish(op))))
            self.r_gfinish = QLabel("Finish")
            form.addRow(self.r_gfinish, self.f_gfinish)
            self.f_gwin = L.Chips(width=96)
            self.f_gwin.addItem("None", False)
            self.f_gwin.addItem("A row on top", True)
            self.f_gwin.setCurrentIndex(1 if op.get("gwin") else 0)
            self.r_gwin = QLabel("Windows")
            form.addRow(self.r_gwin, self.f_gwin)
            from PySide6.QtWidgets import QSpinBox
            self.f_open = QSpinBox()
            self.f_open.setRange(0, 100)
            self.f_open.setSuffix(" %")
            self.f_open.setValue(int(round(float(op.get("open", 0.0) or 0.0)
                                           * 100)))
            self.f_open.setToolTip("How far it is shown open (0: closed)")
            self.r_open = QLabel("Open")
            form.addRow(self.r_open, self.f_open)
            tl.addWidget(self.fold_leaves)
            # a shopfront's / shop window's own (the library's parts)
            self.fold_shop = L.Fold("Shopfront" if self.kind == "door"
                                    else "Shop window", f"{self.kind}.shop")
            form = self.fold_shop.form()
            shop_parts = LB.SHOP_PARTS if self.kind == "door" \
                else LB.SHOP_WINDOW_PARTS
            for part in shop_parts:
                if part.kind == "chips":
                    c = L.Chips()
                    for ch in part.choices:
                        c.addItem(ch[1], ch[0])
                    c.setCurrentIndex(max(0, c.findData(op.get(
                        part.key, part.choices[0][0]))))
                    lab = QLabel(part.label)
                    form.addRow(lab, c)
                    c.currentIndexChanged.connect(self._sync)
                    self.parts.append((part, lab, c))
                elif part.kind == "size" and part.key in ("dh", "base"):
                    lo, hi, step, dflt = part.size
                    f = L.metres(float(op.get(part.key, dflt)), lo, hi, step)
                    lab = QLabel(part.label)
                    form.addRow(lab, f)
                    f.valueChanged.connect(self._sync)
                    self.sizes[part.key] = (part, lab, f)
            tl.addWidget(self.fold_shop)
            tl.addStretch(1)
            self.tabs.addTab(pg, "Type", "build")

        # ---- Size ----------------------------------------------------------------
        pg, sl = L.page()
        self.fold_size = L.Fold("Size", f"{self.kind}.size")
        self.d_size = L.Drawing(_draw_size, 150, 112)
        self.d_size.set(door=self.kind == "door")
        form = self.fold_size.form(self.d_size)
        # the bars run over the usual sizes (the field still takes 20 m)
        # (the value set again once the field takes it: before, it was cut
        # to the bar's end)
        self.f_w = L.metres(op["w"], 0.2, 12.0)
        self.f_w.field.setMaximum(20.0)
        self.f_w.setValue(op["w"])
        form.addRow("Width", self.f_w)
        self.f_h = L.metres(op["h"], 0.2, 5.0)
        self.f_h.field.setMaximum(20.0)
        self.f_h.setValue(op["h"])
        form.addRow("Height", self.f_h)
        self.f_sill = None
        if self.kind != "door":
            self.f_sill = L.metres(op.get("sill", 0.0), 0.0, 3.0)
            self.f_sill.field.setMaximum(20.0)
            self.f_sill.setValue(op.get("sill", 0.0))
            form.addRow("Sill (from the floor)", self.f_sill)
            self.d_size.link(self.f_sill, "sill")
        self.d_size.link(self.f_w, "w")
        self.d_size.link(self.f_h, "h")
        sl.addWidget(self.fold_size)
        sl.addStretch(1)
        self.tabs.addTab(pg, "Size", "geometry")

        # ---- Trim & sill (trim.py, his ask 2026-10-19) ---------------------------
        from . import trim as TR
        k = dict(TR.DEFAULTS, **TR.keys_of(op, self.kind))
        pg, tl2 = L.page()
        self.fold_trim = L.Fold("Trim", f"{self.kind}.trim")
        form = self.fold_trim.form()
        self.f_trim = L.Chips(width=96)
        for val, text in (("none", "None"), ("out", "Outside"),
                          ("both", "Both sides")):
            self.f_trim.addItem(text, val)
        self.f_trim.setCurrentIndex(max(0, self.f_trim.findData(k["trim"])))
        self.f_trim.setToolTip("A moulding round the opening, standing out of "
                               "the wall")
        form.addRow("Trim", self.f_trim)
        lo, hi = TR.LIMITS["trim_w"]
        self.f_trim_w = L.metres(k["trim_w"], lo, hi, 0.01)
        form.addRow("Width", self.f_trim_w)
        lo, hi = TR.LIMITS["trim_d"]
        self.f_trim_d = L.metres(k["trim_d"], lo, hi, 0.005)
        self.f_trim_d.setToolTip("How far it stands out of the wall's face")
        form.addRow("Projection", self.f_trim_d)
        tl2.addWidget(self.fold_trim)
        self.f_sill_k = None
        if self.kind == "window":
            self.fold_sill = L.Fold("Stone sill", "window.sill_k")
            form = self.fold_sill.form()
            self.f_sill_k = L.Chips(width=96)
            self.f_sill_k.addItem("None", "none")
            self.f_sill_k.addItem("Stone", "stone")
            self.f_sill_k.setCurrentIndex(
                1 if k["sill_k"] == "stone" else 0)
            self.f_sill_k.setToolTip("The stone under the window, outside")
            form.addRow("Sill", self.f_sill_k)
            self.f_sill_sz = {}
            # (not «label»: it names the delete button further down)
            for key, row, tip in (
                    ("sill_d", "Projection", "How far it stands out past the "
                                             "wall's face (or the trim's)"),
                    ("sill_t", "Thickness", ""),
                    ("sill_x", "Past the sides", "How far it runs past the "
                                                 "opening (or the trim) on "
                                                 "each side")):
                lo, hi = TR.LIMITS[key]
                f = L.metres(k[key], lo, hi, 0.005)
                if tip:
                    f.setToolTip(tip)
                form.addRow(row, f)
                self.f_sill_sz[key] = f
            tl2.addWidget(self.fold_sill)
        tl2.addWidget(L.hint("Each part takes a material of its own: the "
                             "«Material» tab (frame, leaf, trim, sill)."))
        tl2.addStretch(1)
        self.tabs.addTab(pg, "Trim & sill", "material")

        # ---- Position ------------------------------------------------------------
        pg, pl = L.page()
        self.wall_L = W.drawn(wall).L
        self.fold_pos = L.Fold("On the wall", f"{self.kind}.pos")
        self.d_pos = L.Drawing(_draw_on_wall, 150, 124)
        form = self.fold_pos.form(self.d_pos)
        self.f_pos = L.metres(op["pos"], 0.0, max(self.wall_L, 0.1))
        self.f_pos.setToolTip("Its centre, from the start of the wall")
        form.addRow("Along the wall", self.f_pos)
        form.addRow("Wall", QLabel(f"{wall['name']}  "
                                   f"({compat.fmt_len(self.wall_L)})"))
        self.d_pos.link(self.f_pos, "pos")
        pl.addWidget(self.fold_pos)
        pl.addStretch(1)
        self.tabs.addTab(pg, "Position", "position")
        self._own = self.tabs.count()

        # ---- the pages + the front view beside them ------------------------------
        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self.tabs.stack, 5)
        card = L.Card("Front view")
        self.front = _Front()
        card.box.addWidget(self.front, 1)
        self.stats = L.Stats(4)
        card.box.addWidget(self.stats)
        self.badge = L.Badge()
        card.box.addWidget(self.badge)
        self.side = card
        body.addWidget(card, 4)
        lay.addLayout(body, 1)
        self.tabs.currentChanged.connect(
            lambda i: self.side.setVisible(i < self._own))

        # ---- the buttons ---------------------------------------------------------
        lay.addWidget(L.rule())
        acts = QHBoxLayout()
        b_del = QPushButton(tr(f"Delete {label.lower()}"))
        b_del.setObjectName("axqDanger")
        b_del.clicked.connect(self._delete)
        acts.addWidget(b_del)
        acts.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_apply(self, bb)
        L.ok_button(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        acts.addWidget(bb)
        lay.addLayout(acts)

        for w_ in (self.f_w, self.f_h, self.f_pos) + (
                (self.f_sill,) if self.f_sill is not None else ()):
            w_.valueChanged.connect(self._sync)
        # the trim / sill fields
        self.f_trim.currentIndexChanged.connect(self._sync)
        for w_ in (self.f_trim_w, self.f_trim_d):
            w_.valueChanged.connect(self._sync)
        if self.f_sill_k is not None:
            self.f_sill_k.currentIndexChanged.connect(self._sync)
            for w_ in self.f_sill_sz.values():
                w_.valueChanged.connect(self._sync)
        if self.f_type is not None:
            for c in (self.f_type, self.f_leaves, self.f_swing, self.f_out,
                      self.f_garage, self.f_gfinish, self.f_gwin):
                c.currentIndexChanged.connect(self._sync)
            self.f_open.valueChanged.connect(self._sync)
        self._sync()

    # -- the record ------------------------------------------------------------------
    def _record(self) -> dict:
        o = dict(self.op)
        o["name"] = self.f_name.text().strip() or self.op["name"]
        o["w"] = round(self.f_w.value(), 3)
        o["h"] = round(self.f_h.value(), 3)
        o["pos"] = round(self.f_pos.value(), 3)
        if self.f_sill is not None:
            o["sill"] = round(self.f_sill.value(), 3)
        # its trim and stone sill (trim.py) — none: the keys go
        from . import trim as TR
        for key in TR.DEFAULTS:
            o.pop(key, None)
        o["trim"] = self.f_trim.currentData()
        o["trim_w"] = round(self.f_trim_w.value(), 4)
        o["trim_d"] = round(self.f_trim_d.value(), 4)
        if self.f_sill_k is not None:
            o["sill_k"] = self.f_sill_k.currentData()
            for key, f in self.f_sill_sz.items():
                o[key] = round(f.value(), 4)
        if self.f_type is None:
            kept = TR.keys_of(o, self.kind)
            for key in TR.DEFAULTS:
                o.pop(key, None)
            o.update(kept)
            return o
        t = self.f_type.currentData()
        if self.kind == "door":
            o["op"], o["leaf"] = t
            o["leaves"] = 2 if self.f_leaves.currentData() == 2 else 1
            if o["op"] == "garage":
                o["garage"] = self.f_garage.currentData()
                o["gfinish"] = self.f_gfinish.currentData()
                o["gwin"] = bool(self.f_gwin.currentData())
                o["leaves"] = 1
        else:
            o["op"] = t
            o["leaves"] = int(self.f_leaves.currentData())
            from .structure import window_leaves
            o["leaves"] = window_leaves(o)        # within its type's range
        o["swing"] = self.f_swing.currentData()
        o["out"] = bool(self.f_out.currentData())
        o["open"] = round(self.f_open.value() / 100.0, 3)
        if o["op"] == "shop":
            for part, _l, c in self.parts:
                o[part.key] = c.currentData()
            for key, (_p, _l, f) in self.sizes.items():
                o[key] = round(f.value(), 3)
        kept = TR.keys_of(o, self.kind)          # (a shop window: no sill)
        for key in TR.DEFAULTS:
            o.pop(key, None)
        o.update(kept)
        return o

    def _sync(self, *_a) -> None:
        o = self._record()
        if self.f_type is not None:
            self._shown(o)
        # the trim's / sill's sizes: only with one
        on = self.f_trim.currentData() != "none"
        self.f_trim_w.setEnabled(on)
        self.f_trim_d.setEnabled(on)
        self.fold_trim.set_pick({"none": "none", "out": "outside",
                                 "both": "both sides"}[
                                     self.f_trim.currentData()])
        if self.f_sill_k is not None:
            stone = self.f_sill_k.currentData() == "stone" \
                and o.get("op") != "shop"
            self.f_sill_k.setEnabled(o.get("op") != "shop")
            for f in self.f_sill_sz.values():
                f.setEnabled(stone)
            self.fold_sill.set_pick("stone" if stone else "none")
        self.front.set(o)
        # the header, the folds' choices, the drawings, the numbers
        name = self.f_type.currentText() if self.f_type is not None \
            else self.label
        parts = [name, "{" + compat.fmt_wh(o['w'], o['h']) + "}"]
        if self.kind != "door":
            parts.append("sill {" + compat.fmt_len(o.get('sill', 0.0)) + "}")
        if self.f_type is not None and o.get("op") not in ("shop", "fixed"):
            parts.append(f"{o['leaves']} leaf" + ("" if o["leaves"] == 1
                                                   else "s"))
        self.head.set_summary(parts)
        if self.f_type is not None:
            self.fold_type.set_pick(name)
            self.fold_leaves.set_pick(f"{o['leaves']} · "
                                      f"{'out' if o['out'] else 'in'}")
        self.fold_size.set_pick(f"{o['w']:.2f} × {o['h']:.2f}"
                                if compat.doc_length_unit() == "m"
                                else compat.fmt_wh(o['w'], o['h']))
        self.fold_pos.set_pick(f"{compat.fmt_len(o['pos'])} along")
        self.d_pos.set(f=o["pos"] / max(self.wall_L, 0.1),
                       wf=o["w"] / max(self.wall_L, 0.1))
        sill = 0.0 if self.kind == "door" else float(o.get("sill", 0.0))
        self.stats.set([(compat.fmt_len(o['w']), "width"),
                        (compat.fmt_len(o['h']), "height"),
                        (compat.fmt_area(o['w'] * o['h']), "area"),
                        (compat.fmt_len(sill + o['h']), "head (top)")])
        if self.kind == "door" and o.get("op") != "shop" \
                and compat.imperial():
            # an American document: ADA's 32" clear ≈ a 34" door at least
            ok = o["w"] >= 0.8636 - 1e-4
            self.badge.set(ok, "Wide enough for ADA (32\" clear: a 34\" "
                               "door or more)" if ok else
                           "Narrower than ADA asks (32\" clear: a 34\" "
                           "door or more)")
            self.badge.show()
        elif self.kind == "door" and o.get("op") != "shop":
            ok = o["w"] >= 0.80 - 1e-6
            self.badge.set(ok, "Free width: NBR 9050 asks 0.80 m at least"
                           if ok else "Narrower than NBR 9050's 0.80 m "
                           "(accessible doors)")
            self.badge.show()
        else:
            self.badge.hide()

    def _shown(self, o: dict) -> None:
        """Which rows show, for the type picked."""
        t = o.get("op")
        shop = t == "shop"
        garage = t == "garage"
        if self.kind == "door":
            leaves = not shop and not garage
            ok_n = (1, 2)
            swing = not shop and not garage and (t == "sliding"
                                                 or o["leaves"] == 1)
            out = t == "swing"
            opn = t in ("swing", "sliding", "garage")
            self.r_swing.setText("Slides to" if t == "sliding" else "Hinge")
        else:
            leaves = t in ("sliding", "casement")
            ok_n = (2, 3, 4) if t == "sliding" else (1, 2)
            swing = t == "casement" and o["leaves"] == 1
            out = t == "casement"
            opn = t in ("sliding", "casement", "awning")
        for i in range(self.f_leaves.count()):
            self.f_leaves.setItemEnabled(
                i, self.f_leaves.itemData(i) in ok_n)
        for lab, w_, on in ((self.r_leaves, self.f_leaves, leaves),
                            (self.r_swing, self.f_swing, swing),
                            (self.r_out, self.f_out, out),
                            (self.r_open, self.f_open, opn)):
            lab.setVisible(on)
            w_.setVisible(on)
        g_on = self.kind == "door" and t == "garage"
        w_on = g_on and o.get("garage") != "rollup"
        for lab, w_, on in ((self.r_garage, self.f_garage, g_on),
                            (self.r_gfinish, self.f_gfinish, g_on),
                            (self.r_gwin, self.f_gwin, w_on)):
            lab.setVisible(on)
            w_.setVisible(on)
        self.fold_leaves.setVisible(leaves or swing or out or opn)
        self.fold_shop.setVisible(shop)
        for part, lab, c in self.parts:
            on = part.show is None or bool(part.show(o))
            lab.setVisible(on)
            c.setVisible(on)
        for key, (part, lab, f) in self.sizes.items():
            on = part.show is None or bool(part.show(o))
            lab.setVisible(on)
            f.setVisible(on)

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
        return self.action, self._record()


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
        lay.setContentsMargins(14, 10, 14, 12)
        look_head(self, lay, "setbacks", "Setbacks", "setbacks",
                  "How far from each edge of the plot you may build. Mark "
                  "the front (the side on the street); the back and the "
                  "sides follow — change any of them here.")
        show = _show_row(view, [
            ("plot_dims", "Plot dimensions",
             "The length of every side of the plot — chosen here, it "
             "rules over the Settings"),
            ("plot_elev_dims", "Plot elevations",
             "The ground's elevation at every corner of the plot"),
            ("setbacks", "Setback outline",
             "The dashed outline of where you may build (the buildable "
             "area) — off by default"),
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
            self.table.setItem(i, 1, PlotDialog._fixed(compat.fmt_len(L[i])))
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
            text = (f"Buildable area <b>"
                    f"{compat.fmt_area(plotgeo.area(area), group=True)}</b> "
                    f"of {compat.fmt_area(plotgeo.area(p['corners']), group=True)}"
                    " — dashed on the "
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
        lay.setContentsMargins(14, 10, 14, 12)
        from . import look as L
        L.dress(self)
        head = L.Header(_ic_named("fill" if self.fill else "dig"),
                        self.dig["name"],
                        "fill" if self.fill else "excavation", editable=True)
        head.set_summary(["Fill" if self.fill else "Excavation"])
        self.f_name = head.name
        self.f_name.setToolTip(f"The {self.noun}'s name")
        lay.addWidget(head)
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
                compat.fmt_level(self.ground[i], unit=False)))
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
            self.table.setItem(i, 5, PlotDialog._fixed(compat.fmt_len(L[i])))
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
                f"{compat.fmt_area(plotgeo.area(top), group=True)}"
                if top is not self.dig["corners"] else "")
        if self.fill:
            high = max(z - g for g, z in zip(self.ground, bots))
            text = (f"Platform <b>{compat.fmt_area(area, group=True)}</b>"
                    f"{foot}  ·  highest {compat.fmt_len(high)}  ·  earth "
                    f"brought in <b>{compat.fmt_volume(abs(vol))}</b>")
        else:
            deep = max(g - z for g, z in zip(self.ground, bots))
            text = (f"Floor <b>{compat.fmt_area(area, group=True)}</b>{foot}"
                    f"  ·  deepest {compat.fmt_len(deep)}  ·  earth taken out "
                    f"<b>{compat.fmt_volume(vol)}</b>")
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
