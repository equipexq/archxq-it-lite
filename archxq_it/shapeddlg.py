# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The window of a piece adopted as it is (shaped.py — F3c): its name,
what it is (its category: the IFC class, the quantities, the «Show»
chip), its level — it stays where it is, its height over the new floor
worked out — and how high. Adopting (``new=True``): the same window,
«Adopt»; editing: Hide / Delete and its Material tab (ui).
``result_data()`` → (action, record)."""
from __future__ import annotations

import copy as _copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from . import compat
from . import shaped as SP
from .i18n import tr


def _ic_shaped(p, r, _on):
    """A free shape held in a frame: «as it is»."""
    from PySide6.QtGui import QColor
    from . import look as L
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#1f3355"))
    p.drawRoundedRect(r, 8, 8)
    L.poly(p, [(7, 30), (11, 16), (20, 10), (31, 13), (34, 24), (26, 32),
               (14, 33), (7, 30)], L.GOLD, 1.8)
    for (x, y) in ((5, 5), (35, 5), (5, 35), (35, 35)):
        L.poly(p, [(x, y), (x + (4 if x < 20 else -4), y)], L.GOLD, 1.4)
        L.poly(p, [(x, y), (x, y + (4 if y < 20 else -4))], L.GOLD, 1.4)


def describe(e: dict) -> str:
    """«1 204 faces · a solid, 0.84 m³» / «… · open faces, 12.5 m²»."""
    n = len(e.get("mesh") or [])
    vol = SP.volume(e)
    if vol > 0:
        what = tr("a solid, {v}", v=compat.fmt_volume(vol, 3))
    else:
        a = SP.area(e)
        what = tr("open faces, {a}", a=compat.fmt_area(a, 2, True))
    return tr("{n} faces", n=f"{n:,}".replace(",", " ")) + " · " + what


class ShapedDialog(QDialog):
    """``levels``: [(id, name, floor z)] — the project's, bottom up."""

    def __init__(self, el: dict, levels, new: bool = False,
                 parent=None) -> None:
        from . import look as L
        from .dialogs import hide_button, ok_apply
        super().__init__(parent)
        self.el = el = _copy.deepcopy(el)
        self.levels = list(levels)
        self.action = "apply"
        self.new = new
        self.setWindowTitle(tr("Adopt as it is") if new
                            else tr("Adopted piece"))
        self.setMinimumWidth(460)
        L.dress(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(6)
        self.head = L.Header(_ic_shaped, el["name"], "shaped", editable=True)
        self.f_name = self.head.name
        lay.addWidget(self.head)
        self.tabs = L.Tabs()
        self._axq_tabs = self.tabs
        lay.addWidget(self.tabs.bar)
        lay.addWidget(L.rule())
        pg, gl = L.page()

        fold = L.Fold(tr("Piece"), "shaped.piece")
        form = fold.form()
        self.f_cat = L.Chips()
        for k in SP.CATS:
            self.f_cat.addItem(tr(SP.CAT_LABEL[k]), k)
        self.f_cat.setCurrentIndex(max(0, self.f_cat.findData(
            el.get("cat", "other"))))
        self.f_cat.setToolTip(tr("What it is: its IFC class, its line in "
                                 "the quantities, the «Show» chip that "
                                 "shows / hides it"))
        self.f_cat.currentIndexChanged.connect(self._sync)
        form.addRow(tr("It is"), self.f_cat)
        self.f_level = QComboBox()
        for lid, name, _z in reversed(self.levels):      # highest on top
            self.f_level.addItem(name, lid)
        self.f_level.setCurrentIndex(max(0, self.f_level.findData(
            el["level"])))
        self.f_level.setToolTip(tr("Its level — it stays where it is: its "
                                   "height over that floor follows"))
        self._lv_was = el["level"]
        self.f_level.currentIndexChanged.connect(self._level_changed)
        form.addRow(tr("Level"), self.f_level)
        self.f_z = L.metres(float(el.get("z", 0.0)), -100.0, 500.0, 0.05)
        self.f_z.setToolTip(tr("Its lowest point over its level's floor"))
        self.f_z.valueChanged.connect(self._sync)
        form.addRow(tr("Over the floor"), self.f_z)
        gl.addWidget(fold)
        self.fold = fold
        self.info = QLabel(describe(el))
        self.info.setWordWrap(True)
        gl.addWidget(self.info)
        gl.addWidget(L.hint(tr(
            "As it is: its faces, colours and textures stay. The host's "
            "Move and Rotate move it; Explode gives its faces back.")))
        gl.addStretch(1)
        self.tabs.addTab(pg, tr("Geometry"), "geometry")
        lay.addWidget(self.tabs.stack, 1)

        lay.addWidget(L.rule())
        acts = QHBoxLayout()
        if not new:
            acts.addWidget(hide_button(self))
            b_del = QPushButton(tr("Delete"))
            b_del.setObjectName("axqDanger")
            b_del.clicked.connect(self._delete)
            acts.addWidget(b_del)
        acts.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        if new:
            okb = bb.button(QDialogButtonBox.Ok)
            okb.setText(tr("Adopt"))
            okb.setObjectName("axqOk")
        else:
            ok_apply(self, bb)
        L.ok_button(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        acts.addWidget(bb)
        lay.addLayout(acts)
        self._sync()

    def _floor(self, lid: str) -> float:
        return next((z for i, _n, z in self.levels if i == lid), 0.0)

    def _level_changed(self, *_a) -> None:
        """Another level: the piece stays where it is — its height over
        the new floor."""
        lid = self.f_level.currentData()
        z = self.f_z.value() + self._floor(self._lv_was) - self._floor(lid)
        self._lv_was = lid
        self.f_z.blockSignals(True)
        self.f_z.setValue(round(z, 4))
        self.f_z.blockSignals(False)
        self._sync()

    def _record(self) -> dict:
        e = dict(self.el)
        e["name"] = (self.f_name.text().strip() or self.el["name"])[:60]
        e["cat"] = self.f_cat.currentData()
        e["level"] = self.f_level.currentData()
        e["z"] = round(self.f_z.value(), 4)
        return e

    def _sync(self, *_a) -> None:
        self.fold.set_pick(self.f_cat.currentText())
        self.head.set_summary([self.f_cat.currentText(),
                               self.f_level.currentText()])

    def _delete(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, tr("Delete?"), tr("Delete «{name}»? (Ctrl+Z brings it "
                                        "back)", name=self.el["name"])) \
                != QMessageBox.Yes:
            return
        self.action = "delete"
        self.accept()

    def result_data(self):
        return self.action, self._record()
