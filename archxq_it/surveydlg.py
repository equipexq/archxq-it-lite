"""The survey points' windows: the points table (edit, add, delete) and
the import of a surveyor's file (CSV / TXT)."""
from __future__ import annotations

import copy
import os

from PySide6.QtCore import QEvent, Qt, QTimer
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
    QVBoxLayout,
)

from . import plotgeo, survey
from .dialogs import FIELD_TABLE_CSS, PlotDialog, _metres, _show_row
from .help import help_button

#: the name cells are fields too (the spin boxes' own line edits must not
#: get a second frame, hence the object name)
NAME_CSS = (
    "QTableWidget QLineEdit#axqField { background: #2c3238; border: 1px "
    "solid #56606b; border-radius: 3px; padding: 1px 6px; margin: 3px 6px; }"
    "QTableWidget QLineEdit#axqField:focus { border: 1px solid #2f7df6; "
    "background: #333b44; }")


class SurveyDialog(QDialog):
    """Terrain › Survey points › Points & import…: every point measured on
    the ground — name, X, Y, elevation — typed, added, deleted, or read
    from a surveyor's file; and the contour lines' step. The ground is
    rebuilt through them on Apply (one Ctrl+Z). ``result_data()`` →
    (points, step)."""

    def __init__(self, doc: dict, parent=None, preview=None,
                 view=None) -> None:
        super().__init__(parent)
        self.doc = doc
        self.plot = doc["plot"]
        self.points = copy.deepcopy(self.plot.get("survey") or [])
        self.preview = preview or (lambda _p: None)
        self.active: int | None = None
        self.setWindowTitle("Survey points")
        self.setMinimumSize(620, 520)

        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        title = QLabel("Survey points")
        f = title.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        title.setFont(f)
        head.addWidget(title, 1)
        head.addWidget(help_button("survey"))
        lay.addLayout(head)
        show = _show_row(view, [
            ("plot_elev_dims", "Plot elevations",
             "The ground's elevation at every corner of the plot"),
            ("survey_dims", "Survey points",
             "These points and their elevations, on the model — chosen "
             "here, it rules over the Settings"),
            ("contour_dims", "Contours",
             "The ground's contour lines (every 5th thicker, with its "
             "elevation)")])
        if show is not None:
            lay.addWidget(show)
        row = QHBoxLayout()
        row.addWidget(QLabel("Contour lines every"))
        self.f_step = _metres(float(self.plot.get("contour", 0.5)), 0.05,
                              50.0, 0.25)
        self.f_step.setKeyboardTracking(False)
        self.f_step.setToolTip("The height between two contour lines; "
                               "every 5th one is drawn thicker, with its "
                               "elevation")
        self.f_step.valueChanged.connect(lambda _v: self._status())
        row.addWidget(self.f_step)
        row.addStretch()
        lay.addLayout(row)

        bar = QHBoxLayout()
        imp = QPushButton("Import file…")
        imp.setToolTip("Read the points from a surveyor's file (CSV, TXT): "
                       "name, X, Y, elevation")
        imp.clicked.connect(self._import)
        add = QPushButton("Add point")
        add.setToolTip("A new point in the middle of the plot — type where "
                       "it is and its elevation (or use «Add point» on the "
                       "left, on the model)")
        add.clicked.connect(self._add)
        bar.addWidget(imp)
        bar.addWidget(add)
        bar.addStretch()
        self.clear_btn = QPushButton("Delete all")
        self.clear_btn.clicked.connect(self._clear)
        bar.addWidget(self.clear_btn)
        lay.addLayout(bar)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["#", "Name", "X", "Y", "Elevation", ""])
        hh = self.table.horizontalHeader()
        for c in range(6):
            hh.setSectionResizeMode(c, QHeaderView.Stretch if c in (1, 2, 3, 4)
                                    else QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setStyleSheet(FIELD_TABLE_CSS + NAME_CSS)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        lay.addWidget(self.table, 1)

        self.status = QLabel()
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        from .dialogs import ok_apply
        ok_apply(self, bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._rebuild()

    # ---- the table ---------------------------------------------------------------
    def _rebuild(self) -> None:
        """All the rows again (after an import, an add, a delete)."""
        t = self.table
        t.setRowCount(0)
        t.setRowCount(len(self.points))
        for i, p in enumerate(self.points):
            t.setItem(i, 0, PlotDialog._fixed(str(i + 1)))
            name = QLineEdit(p[3])
            name.setObjectName("axqField")
            name.setFrame(False)
            name.editingFinished.connect(
                lambda i=i, w=name: self._on_name(i, w.text()))
            self._track(name, i)
            t.setCellWidget(i, 1, name)
            for col, k, lo, hi in ((2, 0, -1e7, 1e7), (3, 1, -1e7, 1e7),
                                   (4, 2, -500.0, 500.0)):
                sb = PlotDialog._spin(lo, hi, 0.05 if k == 2 else 0.5,
                                      " m", 3 if k == 2 else 2)
                sb.setValue(p[k])
                sb.valueChanged.connect(
                    lambda v, i=i, k=k: self._on_value(i, k, v))
                self._track(sb, i)
                self._track(sb.lineEdit(), i)
                t.setCellWidget(i, col, sb)
            x = QPushButton("✕")
            x.setFlat(True)
            x.setToolTip("Delete this point")
            x.setFixedWidth(28)
            x.clicked.connect(lambda _c=False, i=i: self._delete(i))
            t.setCellWidget(i, 5, x)
        self._status()

    def _track(self, w, row: int) -> None:
        w.setProperty("axq_row", row)
        w.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        kind = event.type()
        if kind in (QEvent.FocusIn, QEvent.MouseButtonPress,
                    QEvent.MouseButtonRelease):
            row = obj.property("axq_row")
            if row is not None and int(row) != self.active:
                self.active = int(row)
                self._show()
            spin = obj.parent() if isinstance(obj, QLineEdit) \
                and obj.objectName() != "axqField" else obj
            if isinstance(spin, (QDoubleSpinBox, QLineEdit)) and kind != \
                    QEvent.MouseButtonPress:
                QTimer.singleShot(0, spin.selectAll)
        return False

    def _on_name(self, i: int, text: str) -> None:
        if i < len(self.points):
            self.points[i][3] = text.strip()[:40]

    def _on_value(self, i: int, k: int, v: float) -> None:
        if i < len(self.points):
            self.points[i][k] = round(v, 3 if k == 2 else 4)
            self._status()

    def _delete(self, i: int) -> None:
        if i < len(self.points):
            del self.points[i]
            self.active = None
            self._rebuild()

    def _clear(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        if not self.points:
            return
        if QMessageBox.question(
                self, "Delete all points?",
                f"Delete all {len(self.points)} survey points? (Cancel "
                "keeps them; after Apply, Ctrl+Z brings them back)",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel) == QMessageBox.Yes:
            self.points = []
            self.active = None
            self._rebuild()

    def _add(self) -> None:
        from . import terrain
        c = self.plot["corners"]
        mid = [sum(p[0] for p in c) / len(c), sum(p[1] for p in c) / len(c)]
        if not plotgeo.inside_polygon(mid, c):
            mid = list(c[0])                      # a concave plot: a corner
        z = terrain.ground_at(self.plot, mid)
        self.points.append([round(mid[0], 3), round(mid[1], 3), round(z, 3),
                            f"P{len(self.points) + 1}"])
        self.active = len(self.points) - 1
        self._rebuild()
        QTimer.singleShot(0, lambda: self.table.scrollToBottom())

    def _status(self) -> None:
        used = len(plotgeo.survey_inside(self.plot["corners"], self.points))
        n = len(self.points)
        out = n - used
        if not n:
            text = ("No survey points. <b>Import file…</b> reads a "
                    "surveyor's list; <b>Add point</b> types one in; «Add "
                    "point» on the left clicks one on the model.")
        else:
            text = (f"<b>{n}</b> point" + ("s" if n > 1 else "")
                    + f"  ·  {used} shape the ground")
            if out:
                text += (f"  ·  <span style='color:#e5a03b'>{out} outside the "
                         "plot (or on its border / a corner) — kept, not "
                         "used</span>")
        self.status.setText(text)
        self.clear_btn.setEnabled(bool(n))
        self._show()

    def _show(self) -> None:
        step = self.f_step.value() if hasattr(self, "f_step") else None
        self.preview((self.points, self.active, step))

    # ---- import ------------------------------------------------------------------------
    def _import(self) -> None:
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        path, _f = QFileDialog.getOpenFileName(
            self, "Import survey points", "",
            "Survey points (*.csv *.txt *.xyz *.pnt *.asc);;All files (*)")
        if not path:
            return
        text = None
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                with open(path, encoding=enc) as fh:
                    text = fh.read()
                break
            except UnicodeDecodeError:
                continue
            except OSError as e:
                QMessageBox.warning(self, "Import survey points",
                                    f"The file can't be read: {e}")
                return
        if text is None:
            return
        dlg = ImportDialog(text, os.path.basename(path), self.plot,
                           bool(self.points), self,
                           lambda pts: self.preview((pts, None)))
        ok = dlg.exec()
        if not ok:
            self._show()
            return
        pts, replace = dlg.result_data()
        self.points = pts if replace else self.points + pts
        self.active = None
        self._rebuild()

    def result_data(self):
        """(points, contour step)."""
        return [list(p) for p in self.points], round(self.f_step.value(), 3)


class ImportDialog(QDialog):
    """A surveyor's file read: what was found, the columns' order, where
    the points go (moved onto the plot if they are elsewhere — UTM) and
    which elevation is ±0.00; how many fall inside the plot, live, and on
    the model."""

    def __init__(self, text: str, name: str, plot: dict, has: bool,
                 parent=None, preview=None) -> None:
        super().__init__(parent)
        self.text = text
        self.plot = plot
        self.preview = preview or (lambda _p: None)
        self.setWindowTitle("Import survey points")
        self.setMinimumWidth(480)
        self.read = survey.read(text)
        raw = self.read["points"]

        lay = QVBoxLayout(self)
        self.found = QLabel()
        self.found.setWordWrap(True)
        lay.addWidget(self.found)
        form = QFormLayout()
        self.f_order = QComboBox()
        for key, label in survey.ORDERS:
            self.f_order.addItem(label, key)
        self.f_order.setCurrentIndex(self.f_order.findData(
            self.read["order"]))
        self.f_order.currentIndexChanged.connect(self._reread)
        form.addRow("Columns", self.f_order)
        self.f_datum = _metres(survey.fit_datum(raw), -10000.0, 10000.0, 1.0)
        self.f_datum.setDecimals(3)
        self.f_datum.setToolTip("The file's elevation that becomes the "
                                "plot's ±0.00")
        form.addRow("Elevation that is ±0.00", self.f_datum)
        dx, dy = survey.fit_shift(raw, plot["corners"])
        self.f_dx = _metres(dx, -1e7, 1e7, 1.0)
        self.f_dy = _metres(dy, -1e7, 1e7, 1.0)
        for w in (self.f_dx, self.f_dy):
            w.setDecimals(3)
        move = QHBoxLayout()
        move.addWidget(QLabel("X"))
        move.addWidget(self.f_dx)
        move.addWidget(QLabel("Y"))
        move.addWidget(self.f_dy)
        fit = QPushButton("Onto the plot")
        fit.setToolTip("Move the points' middle onto the plot's middle")
        fit.clicked.connect(self._fit)
        move.addWidget(fit)
        form.addRow("Move by", move)
        self.f_mode = QComboBox()
        self.f_mode.addItem("Add to the points there are", False)
        self.f_mode.addItem("Replace the points there are", True)
        self.f_mode.setEnabled(has)
        if has:
            form.addRow("The points there are", self.f_mode)
        lay.addLayout(form)
        for w in (self.f_datum, self.f_dx, self.f_dy):
            w.setKeyboardTracking(False)
            w.valueChanged.connect(self._update)
        self.inside = QLabel()
        self.inside.setWordWrap(True)
        lay.addWidget(self.inside)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.ok = bb.button(QDialogButtonBox.Ok)
        self.ok.setText("Import")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.name = name
        self._update()

    def _reread(self, *_a) -> None:
        self.read = survey.read(self.text, self.f_order.currentData())
        self._update()

    def _fit(self) -> None:
        raw = self.read["points"]
        self.f_dx.blockSignals(True)
        self.f_dy.blockSignals(True)
        self.f_dx.setValue(0.0)
        self.f_dy.setValue(0.0)
        dx, dy = survey.fit_shift(raw, self.plot["corners"])
        if (dx, dy) == (0.0, 0.0) and raw:
            # they overlap already, but by a corner maybe: centre anyway
            xs, ys = [p[0] for p in raw], [p[1] for p in raw]
            px = [p[0] for p in self.plot["corners"]]
            py = [p[1] for p in self.plot["corners"]]
            dx = (min(px) + max(px)) / 2 - (min(xs) + max(xs)) / 2
            dy = (min(py) + max(py)) / 2 - (min(ys) + max(ys)) / 2
        self.f_dx.setValue(dx)
        self.f_dy.setValue(dy)
        self.f_dx.blockSignals(False)
        self.f_dy.blockSignals(False)
        self._update()

    def points(self) -> list:
        return survey.placed(self.read["points"], self.f_dx.value(),
                             self.f_dy.value(), self.f_datum.value())

    def _update(self, *_a) -> None:
        r = self.read
        n = len(r["points"])
        bits = [f"<b>{self.name}</b>: {n} point" + ("s" if n != 1 else "")
                + f" read ({r['sep']}"
                + (", a header line" if r["header"] else "")
                + (", names in the first column" if r["named"] else "")
                + ")"]
        if r["skipped"]:
            bits.append(f"{r['skipped']} line(s) not read — fewer than "
                        "three numbers")
        self.found.setText("<br>".join(bits))
        pts = self.points()
        used = len(plotgeo.survey_inside(self.plot["corners"], pts))
        if not n:
            self.inside.setText("<span style='color:#e5484d'>No points in "
                                "this file — X, Y and an elevation on each "
                                "line are needed.</span>")
        elif not used:
            self.inside.setText("<span style='color:#e5484d'>None of them "
                                "falls inside the plot — move them («Onto "
                                "the plot») or check the columns.</span>")
        else:
            zs = [p[2] for p in pts]
            self.inside.setText(
                f"<b>{used}</b> of {n} inside the plot  ·  elevations "
                f"{min(zs):+.2f} … {max(zs):+.2f} m")
        self.ok.setEnabled(bool(n))
        self.preview(pts)

    def result_data(self):
        return self.points(), bool(self.f_mode.currentData())
