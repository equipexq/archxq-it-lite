"""YOUR wall / slab type in a window of its own (PLANO_NOVO_TIPO_CAMADAS.md,
his OK 2026-10-28): its name, its LAYERS — the same editor as a wall's
Layers tab — and its section drawn LARGE beside them (his: «at a real
wall's thickness the layers can't be seen; zoomed, they can»).

«+ New type» opens it empty (or with the selected wall's layers): the type
is born ready, no wall needed. A card's double-click / «Edit…» opens it with
the type: Save changes every element of it.

The rows are the wall window's own code (``dialogs.WallDialog``'s layer
methods, borrowed as they are — that window is not touched)."""
from __future__ import annotations

import copy

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QVBoxLayout,
                               QWidget)

from . import look as L
from .dialogs import ElementDialog, WallDialog
from .i18n import tr

class _Total:
    """The window's «thickness box» for the borrowed code: just the sum."""

    def __init__(self) -> None:
        self.v = 0.0

    def value(self) -> float:
        return self.v

    def setValue(self, v: float) -> None:  # noqa: N802 — a box's name
        self.v = float(v)


class TypeDialog(QDialog):
    """``kind`` "wall" | "slab"; ``ty`` the type to edit (None: a new one);
    ``layers`` to start a new one with; ``n`` its elements (editing).
    ``result()`` after ``exec()`` → {"name", "layers", "t", "frame"} (a
    wall's core: solid — None — or light-framed, framing.py)."""

    #: the rows, as a wall's Layers tab draws and changes them
    _build_rows = WallDialog._build_rows
    _add_layer = WallDialog._add_layer
    _move = WallDialog._move
    _remove = WallDialog._remove
    _layer_name = WallDialog._layer_name
    _layer_t = WallDialog._layer_t
    _layers_changed = WallDialog._layers_changed
    #: the eye (layerview.py): a type being edited — ui gives ``layer_eye``
    _eye_owner = WallDialog._eye_owner
    _eye_keys = WallDialog._eye_keys
    _eye_buttons = WallDialog._eye_buttons
    _eye_click = WallDialog._eye_click
    _eye_show_all = WallDialog._eye_show_all

    def __init__(self, kind: str, ty: dict | None, layers: list | None,
                 n: int = 0, from_sel: bool = False, frame=None,
                 parent=None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.LW = ElementDialog.LW if kind == "slab" else WallDialog.LW
        self.editing = ty is not None
        src = ty["layers"] if ty is not None else layers
        self.layers = copy.deepcopy(list(src or [])) or [
            {"id": "core", "name": "", "t": 0.15, "role": "core"}]
        for k, la in enumerate(self.layers):
            la.setdefault("id", f"l{k}")
        self._tot = _Total()
        self.setWindowTitle(
            (tr("Slab type «{n}»", n=ty["name"]) if kind == "slab"
             else tr("Wall type «{n}»", n=ty["name"])) if self.editing else
            tr("New slab type") if kind == "slab" else tr("New wall type"))
        self.setMinimumWidth(660)
        L.dress(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(8)
        head = QHBoxLayout()
        lab = QLabel(tr("Name"))
        lab.setStyleSheet(f"color:{L.GOLD};font-weight:600;")
        head.addWidget(lab)
        self.f_name = QLineEdit(ty["name"] if ty is not None else "")
        self.f_name.setPlaceholderText(
            tr("For example «Slab 20»") if kind == "slab"
            else tr("For example «Exterior 25»"))
        self.f_name.setMaxLength(40)
        head.addWidget(self.f_name, 1)
        lay.addLayout(head)
        slab = kind == "slab"
        if self.editing and n:
            who = (tr("1 slab of this type changes with it") if slab
                   else tr("1 wall of this type changes with it")) \
                if n == 1 else \
                (tr("{n} slabs of this type change with it", n=n) if slab
                 else tr("{n} walls of this type change with it", n=n))
        elif from_sel:
            who = (tr("Starts from the slab selected — it becomes of this "
                      "type") if slab else
                   tr("Starts from the wall selected — it becomes of this "
                      "type"))
        else:
            who = ""
        if who:
            w = QLabel(who)
            w.setStyleSheet("background:#2a2620;border:1px solid #5a4630;"
                            "border-radius:5px;padding:5px 8px;"
                            "color:#e9d6b8;")
            lay.addWidget(w)
        body = QHBoxLayout()
        body.setSpacing(14)
        left = QVBoxLayout()
        self.fold_layers = L.Fold(tr("Layers"))
        self._rows_host = QWidget()
        self._rows = QVBoxLayout(self._rows_host)
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(4)
        self.fold_layers.box.addWidget(self._rows_host)
        add = QHBoxLayout()
        for (text, tip, _n), at in zip(self.LW["add"], (0, -1)):
            b = QPushButton(tr(text))
            b.setObjectName("axqChip")
            b.setToolTip(tr(tip))
            b.clicked.connect(lambda _c=False, at=at: self._add_layer(at))
            add.addWidget(b)
        add.addStretch(1)
        self.l_total = QLabel()
        add.addWidget(self.l_total)
        self.fold_layers.box.addLayout(add)
        left.addWidget(self.fold_layers)
        self.frame_box = None
        if kind == "wall":               # its core: solid or a frame
            from .framebox import FrameBox
            self.frame_box = FrameBox(
                ty.get("frame") if ty is not None else frame,
                lambda: self._build_rows())
            left.addWidget(self.frame_box)
        left.addWidget(L.hint(
            tr("Top first: the finished floor. The core carries; each "
               "finish's material: the slab's window, «Material».")
            if kind == "slab" else
            tr("Outside at the top, inside at the bottom. The core is the "
               "structure; each finish's material: the wall's window, "
               "«Material».")))
        left.addStretch(1)
        body.addLayout(left, 1)
        right = QVBoxLayout()
        cap = QLabel(tr("Its section"))
        cap.setStyleSheet(f"color:{L.MUTED};font-size:11px;")
        right.addWidget(cap)
        self.cut = L.Drawing(L.draw_layers_cut, 210, 280)
        self.cut.set(sides=self.LW["sides"])
        right.addWidget(self.cut)
        right.addStretch(1)
        body.addLayout(right)
        lay.addLayout(body, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        L.ok_button(bb)
        bb.button(QDialogButtonBox.Ok).setText(
            tr("Save") if self.editing else tr("Create"))
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._build_rows()

    # what the borrowed rows call on a wall's window ---------------------------------
    def _type_gate(self) -> None:          # (no type to leave: it IS one)
        pass

    def _show_type(self) -> None:
        pass

    def _t_box(self):
        return self._tot

    def _layers_refresh(self) -> None:
        if getattr(self, "cut", None) is None:
            return
        self.cut.set(layers=[dict(la) for la in self.layers],
                     frame=self.frame_box.value() if self.frame_box
                     else None)

    # ---------------------------------------------------------------------------------
    def _ok(self) -> None:
        if not self.f_name.text().strip():
            self.f_name.setStyleSheet(f"border:1px solid {L.ORANGE};")
            self.f_name.setFocus()
            return
        self.accept()

    def result(self) -> dict:
        ls = [dict(la) for la in self.layers]
        return {"name": self.f_name.text().strip()[:40], "layers": ls,
                "t": round(sum(float(la["t"]) for la in ls), 4),
                "frame": self.frame_box.value() if self.frame_box else None}
