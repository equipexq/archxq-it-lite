"""STAIRS — the second «Building element» (plan PLANO_RAMPA_ESCADA.md,
steps 3–4): from a level (or the ground) to another, straight, L or U —
its steps worked out by Blondel's rule.

Like a ramp (ramps.py) it is one more type in ``doc["structure"]``
(``type="stair"``) and shares the ramp's plan layout (runs + a level
landing, ``ramps.pieces``), its window's From / To and its tool. What is
its own: the steps.

    risers  n = ceil(drop / riser max)      (riser max 0.18)
    riser   h = drop / n
    tread   p = 0.63 − 2h  (Blondel: 2h + p = 63 cm), kept in 0.25–0.32
            — or typed (``fix_tread``)
    a run of m risers has m − 1 treads: (m − 1) · p long — its last riser
    lands on the landing / the floor.

The record: as a ramp's (start, level, to, to_z, x, y, angle, w, shape,
turn, landing, t) + riser (the max), tread, fix_tread.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import compat
from . import ramps as R
from .plottools import ACCENT

COLOR = (0.76, 0.76, 0.75)       # concrete
DEFAULT = {"start": "level", "to": "", "to_z": -3.0, "w": 1.20,
           "riser": 0.18, "tread": 0.28, "fix_tread": False, "t": 0.15,
           "shape": "straight", "turn": "right", "landing": 1.20,
           "anchor": "centre"}
BLONDEL = 0.63


# ---- the steps -------------------------------------------------------------------------
def steps(r: dict, zs: float, ze: float) -> dict:
    """{n, h (signed: + up), p, n1, n2, l1, l2, L, zm} for this drop."""
    H = ze - zs
    n = max(1, math.ceil(abs(H) / max(float(r.get("riser", 0.18)), 0.05)
                         - 1e-9))
    h = H / n
    if r.get("fix_tread"):
        p = float(r.get("tread", 0.28))
    else:
        p = min(max(BLONDEL - 2 * abs(h), 0.25), 0.32)
    if r.get("shape") in ("L", "U"):
        n1 = math.ceil(n / 2)
        n2 = n - n1
    else:
        n1, n2 = n, 0
    l1 = max(n1 - 1, 0) * p
    l2 = max(n2 - 1, 0) * p
    return {"n": n, "h": h, "p": p, "n1": n1, "n2": n2, "l1": l1, "l2": l2,
            "L": l1 + l2, "zm": zs + n1 * h}


def layout(r: dict, zs: float, ze: float) -> list:
    """The plan pieces (ramps.pieces) with the stair's own runs; each run
    knows its risers ("m") and its riser ("h")."""
    s = steps(r, zs, ze)
    ps = R.pieces(r, zs, ze, s["L"], l1=s["l1"], l2=s["l2"], zm=s["zm"])
    runs = [pc for pc in ps if pc.get("run", True)]
    if runs:
        runs[0]["m"] = s["n1"]
    if len(runs) > 1:
        runs[1]["m"] = s["n2"]
    for pc in ps:
        pc["h"], pc["p"] = s["h"], s["p"]
    return ps


def why_not(r: dict) -> str | None:
    try:
        if float(r["w"]) < 0.6:
            return "A stair needs 60 cm of width at least"
        if not 0.10 <= float(r.get("riser", 0.18)) <= 0.25:
            return "A stair's riser goes from 10 to 25 cm"
        if r.get("fix_tread") and not 0.15 <= float(r["tread"]) <= 0.60:
            return "A stair's tread goes from 15 to 60 cm"
        if float(r["t"]) < 0.05:
            return "A stair needs a thickness of 5 cm at least"
        float(r["x"]), float(r["y"])
    except (KeyError, TypeError, ValueError):
        return "Incomplete stair"
    return None


def _run_profile(m: int, z0: float, h: float, p: float, t: float) -> list:
    """A run of ``m`` risers from ``z0`` (riser ``h``, signed), its side
    profile (along, z) counter-clockwise: the treads on top, the waist
    under them. Going down it starts on its first tread (the floor's edge
    is the first riser); going up its first riser stands on the floor."""
    L = (m - 1) * p
    z1 = z0 + m * h
    tops = []
    for k in range(1, m):
        zk = z0 + k * h
        tops += [((k - 1) * p, zk), (k * p, zk)]
    # the waist: under the line through the treads' inner corners
    b0 = z0 + min(h, 0.0) - t
    b1 = z1 - max(h, 0.0) - t
    return [(0.0, b0), (L, b1)] + list(reversed(tops))


def faces(r: dict, doc: dict, elevations) -> list:
    from .structure import _sweep
    zs, ze = R.heights(r, doc, elevations)
    if abs(zs - ze) < 0.05:
        return []
    t = float(r["t"])
    out = []
    for pc in layout(r, zs, ze):
        (cx, cy), (dx, dy) = pc["c"], pc["d"]
        rx, ry = dy, -dx

        def P(x, y, z, cx=cx, cy=cy, dx=dx, dy=dy, rx=rx, ry=ry):
            return (cx + rx * x + dx * y, cy + ry * x + dy * y, z)
        if pc.get("run", True):
            m = pc.get("m", 0)
            if m < 2:
                continue                  # one riser: nothing to tread on
            prof = _run_profile(m, pc["z0"], pc["h"], pc["p"], t)
        else:
            # the landing: thick enough to meet the next run's first
            # riser; its top 1 mm under (never the floor's plane)
            z = pc["z0"] - 0.001
            tl = t + abs(pc["h"])
            prof = [(0.0, z - tl), (pc["l"], z - tl), (pc["l"], z), (0.0, z)]
        out += _sweep(prof, -pc["w"] / 2, pc["w"] / 2, P, COLOR + (1.0,))
    return out


def footprints(r: dict, doc: dict, elevations) -> list:
    zs, ze = R.heights(r, doc, elevations)
    return [R.piece_corners(pc) for pc in layout(r, zs, ze)]


# ---- its window ------------------------------------------------------------------------
class _Steps(QWidget):
    """The stair seen from its side (unfolded): its steps, the landing."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(280, 210)
        self.r = None
        self.zs = self.ze = 0.0
        self.known = True

    def set(self, r, zs, ze, known=True) -> None:
        self.r, self.zs, self.ze, self.known = r, zs, ze, known
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#1d2025"))
        if self.r is None or abs(self.zs - self.ze) < 0.05:
            p.setPen(QColor("#9aa0a6"))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "Same height at both ends —\nno steps")
            return
        s = steps(self.r, self.zs, self.ze)
        land = 0.0
        if self.r.get("shape") in ("L", "U"):
            land = max(float(self.r.get("landing", 1.2)), float(self.r["w"])) \
                if self.r["shape"] == "L" else float(self.r.get("landing", 1.2))
        # the steps, unfolded, true to scale
        pts = []
        z, x = self.zs, 0.0
        for run, m in ((1, s["n1"]), (2, s["n2"])):
            if m == 0:
                continue
            for k in range(m):
                pts += [(x, z), (x, z + s["h"])]
                z += s["h"]
                if k < m - 1:
                    pts.append((x + s["p"], z))
                    x += s["p"]
            if run == 1 and s["n2"]:
                pts.append((x + land, z))
                x += land
        W = max(x, 0.5)
        lo, hi = min(self.zs, self.ze), max(self.zs, self.ze)
        rr = self.rect().adjusted(16, 34, -16, -34)
        k = min(rr.width() / W, rr.height() / (hi - lo))
        x0 = rr.left() + (rr.width() - W * k) / 2
        y0 = rr.top() + (rr.height() - (hi - lo) * k) / 2

        def q(a, b):
            return QPointF(x0 + a * k, y0 + (hi - b) * k)
        p.setPen(QPen(QColor(ACCENT), 2.2))
        for a, b in zip(pts, pts[1:]):
            p.drawLine(q(*a), q(*b))
        f = QFont(p.font())
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#e6e6e6"))
        p.drawText(QRectF(x0 - 6, q(0, self.zs).y() - 24, 200, 18),
                   Qt.AlignLeft, f"{self.zs:+.2f}"
                   + ("" if self.known else " (the ground)"))
        end = q(x, self.ze)
        p.drawText(QRectF(end.x() - 194, end.y() + 6, 200, 18),
                   Qt.AlignRight, f"{self.ze:+.2f}")


def summary(s: dict) -> str:
    return (f"{s['n']} risers × {abs(s['h']) * 100:.1f} cm · tread "
            f"{s['p'] * 100:.1f} cm · 2h+p = "
            f"{(2 * abs(s['h']) + s['p']) * 100:.1f} cm")


class StairDialog(QDialog):
    """Set a stair up (``edit`` False) or change one (``edit`` True).
    ``result_data()`` → (action, record)."""

    def __init__(self, rec: dict, doc: dict, elevations, edit: bool = False,
                 parent=None) -> None:
        from .dialogs import _metres, ok_apply
        from .help import help_button
        super().__init__(parent)
        self.rec, self.doc, self.elevations = dict(rec), doc, elevations
        self.edit = edit
        self.action = "apply"
        self.setWindowTitle("Stair")
        self.setMinimumWidth(680)
        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        title = QLabel(rec.get("name") or "Stair")
        f = title.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        title.setFont(f)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(help_button("stair"))
        lay.addLayout(head)
        body = QHBoxLayout()
        form = QFormLayout()
        self.f_name = None
        if edit:
            self.f_name = QLineEdit(rec.get("name", ""))
            form.addRow("Name", self.f_name)
        # its top over its bottom, and where the click is (as a ramp's)
        self.ends = R._Ends(doc, elevations, rec, form, _metres)
        self.f_w = _metres(float(rec.get("w", 1.2)), 0.6, 10.0)
        form.addRow("Width", self.f_w)
        self.f_riser = _metres(float(rec.get("riser", 0.18)), 0.10, 0.25,
                               0.005)
        self.f_riser.setDecimals(3)
        self.f_riser.setToolTip("The highest a riser may be: the count of "
                                "risers follows from it")
        form.addRow("Riser (max)", self.f_riser)
        # the tread: by Blondel, or typed (then it stays)
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        self.f_tread = _metres(float(rec.get("tread", 0.28)), 0.15, 0.60,
                               0.005)
        self.f_tread.setDecimals(3)
        self.b_auto = QPushButton("Blondel")
        self.b_auto.setCheckable(True)
        self.b_auto.setChecked(not rec.get("fix_tread"))
        self.b_auto.setToolTip("The tread from Blondel's rule (2 risers + 1 "
                               "tread = 63 cm) — off: the tread typed")
        rl.addWidget(self.f_tread, 1)
        rl.addWidget(self.b_auto)
        row.setStyleSheet(
            "QPushButton { padding: 4px 12px; }"
            f"QPushButton:checked {{ border: 1px solid {ACCENT}; "
            "background: #4a3324; color: white; font-weight: bold; }")
        form.addRow("Tread", row)
        self.f_sum = QLabel()
        self.f_sum.setEnabled(False)
        form.addRow("", self.f_sum)
        self.f_t = _metres(float(rec.get("t", 0.15)), 0.05, 1.0, 0.01)
        form.addRow("Thickness", self.f_t)
        # shape — as a ramp's
        srow = QWidget()
        sl = QHBoxLayout(srow)
        sl.setContentsMargins(0, 0, 0, 0)
        self.g_shape = QButtonGroup(self)
        for key, text, tip in (("straight", "Straight", "One flight"),
                               ("L", "L", "Two flights, a landing, a 90° "
                                          "turn"),
                               ("U", "U", "Two flights side by side, a "
                                          "landing across both")):
            b = QPushButton(text)
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setProperty("shape", key)
            b.setChecked(rec.get("shape", "straight") == key)
            self.g_shape.addButton(b)
            sl.addWidget(b)
        sl.addStretch()
        srow.setStyleSheet(
            "QPushButton { padding: 4px 16px; min-width: 70px; }"
            f"QPushButton:checked {{ border: 1px solid {ACCENT}; "
            "background: #4a3324; color: white; font-weight: bold; }")
        form.addRow("Shape", srow)
        self.f_turn = QComboBox()
        self.f_turn.addItem("Turning right", "right")
        self.f_turn.addItem("Turning left", "left")
        self.f_turn.setCurrentIndex(1 if rec.get("turn") == "left" else 0)
        form.addRow("Turn", self.f_turn)
        self.f_land = _metres(float(rec.get("landing", 1.2)), 0.6, 20.0)
        form.addRow("Landing", self.f_land)
        self.f_anchor = R._anchor_box(rec)
        form.addRow("Insert at", self.f_anchor)
        self.f_anchor.currentIndexChanged.connect(self._sync)
        if edit:
            self.f_x = _metres(float(rec["x"]), -10000.0, 10000.0)
            self.f_y = _metres(float(rec["y"]), -10000.0, 10000.0)
            self.f_a = QDoubleSpinBox()
            self.f_a.setRange(-360.0, 360.0)
            self.f_a.setDecimals(1)
            self.f_a.setSingleStep(15.0)
            self.f_a.setSuffix(" °")
            self.f_a.setValue(float(rec.get("angle", 0.0)))
            form.addRow("Start X", self.f_x)
            form.addRow("Start Y", self.f_y)
            form.addRow("Direction", self.f_a)
        body.addLayout(form, 1)
        self.view = _Steps()
        body.addWidget(self.view, 1)
        lay.addLayout(body)
        if not edit:
            note = QLabel("OK opens the plan: click where it starts (its "
                          "bottom step or its top — «Starts at»; a corner or "
                          "the middle — «Insert at»), then the way it goes.")
            note.setWordWrap(True)
            note.setEnabled(False)
            lay.addWidget(note)
        acts = QHBoxLayout()
        acts.addStretch()
        if edit:
            from .dialogs import hide_button
            acts.addWidget(R._repeat_button(self, "stair"))
            acts.addWidget(hide_button(self))
            b_del = QPushButton("Delete stair")
            b_del.clicked.connect(self._delete)
            acts.addWidget(b_del)
        lay.addLayout(acts)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        if edit:
            ok_apply(self, bb)
        else:
            bb.button(QDialogButtonBox.Ok).setText("OK — place it")
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        for w in self.ends.widgets() + (self.f_turn,):
            w.currentIndexChanged.connect(self._sync)
        for w in (self.ends.f_z, self.f_w, self.f_riser, self.f_tread,
                  self.f_t, self.f_land):
            w.valueChanged.connect(self._sync)
        self.f_tread.valueChanged.connect(self._typed_tread)
        self.b_auto.toggled.connect(self._sync)
        self.g_shape.buttonClicked.connect(self._sync)
        self._quiet = False
        self._sync()

    def _typed_tread(self, *_a) -> None:
        if not self._quiet and self.b_auto.isChecked():
            self.b_auto.setChecked(False)   # typed: it stays

    def _record(self) -> dict:
        r = dict(self.rec)
        self.ends.write(r)
        # it belongs to the lower of its two levels (the storey it takes)
        r["level"] = R.owner(r, self.doc, self.elevations)
        r["w"] = round(self.f_w.value(), 3)
        r["riser"] = round(self.f_riser.value(), 3)
        r["tread"] = round(self.f_tread.value(), 3)
        r["fix_tread"] = not self.b_auto.isChecked()
        r["t"] = round(self.f_t.value(), 3)
        b = self.g_shape.checkedButton()
        r["shape"] = b.property("shape") if b is not None else "straight"
        r["turn"] = self.f_turn.currentData()
        r["landing"] = round(self.f_land.value(), 3)
        r["anchor"] = self.f_anchor.currentData()
        if self.edit:
            r["x"] = round(self.f_x.value(), 4)
            r["y"] = round(self.f_y.value(), 4)
            r["angle"] = round(self.f_a.value(), 3)
            r["name"] = self.f_name.text().strip() or self.rec.get("name")
        return r

    def _drop(self, r):
        r = dict(r)
        r.setdefault("x", 0.0)
        r.setdefault("y", 0.0)
        zs, ze = R.heights(r, self.doc, self.elevations)
        known = r["start"] != "terrain" or self.edit
        if not known:
            hs = self.doc["plot"].get("heights") or [0.0]
            zs = sum(hs) / len(hs)
        return zs, ze, known

    def _sync(self, *_a) -> None:
        self.ends.sync()
        r = self._record()
        turning = r["shape"] in ("L", "U")
        self.f_turn.setEnabled(turning)
        self.f_land.setEnabled(turning)
        zs, ze, known = self._drop(r)
        s = steps(r, zs, ze)
        if not r["fix_tread"]:            # show Blondel's tread
            self._quiet = True
            try:
                self.f_tread.setValue(s["p"])
            finally:
                self._quiet = False
        self.f_sum.setText(summary(s) + f" · run {s['L']:.2f} m"
                           + ("" if known else "  (≈)"))
        self.view.set(r, zs, ze, known)

    def _ok(self) -> None:
        r = self._record()
        why = self.ends.why_not() or why_not(dict(r, x=r.get("x", 0.0),
                                                   y=r.get("y", 0.0)))
        if why is None and r["start"] != "terrain":
            zs, ze = R.heights(dict(r, x=0.0, y=0.0), self.doc,
                               self.elevations)
            if abs(zs - ze) < 0.05:
                why = "The top and the bottom are at the same height"
        if why:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Stair", why + ".")
            return
        self.accept()

    def _delete(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, "Delete?", f"Delete «{self.rec.get('name')}»? (Ctrl+Z "
                "brings it back)", QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel) == QMessageBox.Yes:
            self.action = "delete"
            self.accept()

    def result_data(self):
        return self.action, self._record()


# ---- its tool: the ramp's, with treads drawn -------------------------------------------
class StairTool(R.RampTool):
    name = "ArchXQ stair"
    axq_element = "stair"
    noun = "Stair"

    def __init__(self, rec, heights_at, on_done, on_cancelled, z) -> None:
        """``heights_at(p)`` → (zs, ze) for a stair starting at p."""
        self.heights_at = heights_at

        def length_at(p):
            zs, ze = heights_at(p)
            return steps(rec, zs, ze)["L"], zs, ze
        super().__init__(rec, length_at, on_done, on_cancelled, z)

    def layout(self, r: dict) -> list:
        zs, ze = self.heights_at((r["x"], r["y"]))
        return layout(r, zs, ze)

    def marks(self, viewport, painter, pc: dict) -> None:
        """The treads' lines across a flight."""
        if not pc.get("run", True) or pc.get("m", 0) < 2:
            return
        (cx, cy), (dx, dy) = pc["c"], pc["d"]
        rx, ry = dy, -dx
        h = pc["w"] / 2
        painter.setPen(QPen(QColor(ACCENT), 1.0))
        for k in range(1, pc["m"] - 1):
            s = k * pc["p"]
            a = compat.to_pixel(viewport, cx + dx * s + rx * h,
                                cy + dy * s + ry * h, self.z)
            b = compat.to_pixel(viewport, cx + dx * s - rx * h,
                                cy + dy * s - ry * h, self.z)
            if a and b:
                painter.drawLine(QPointF(*a), QPointF(*b))

    def value_label(self):
        if self.a is None or self.hover is None:
            return None
        zs, ze = self.heights_at(self.a)
        s = steps(self.rec, zs, ze)
        ang = self._angle(self.hover)
        return (f"{s['n']} risers · run {s['L']:.2f} m  {zs:+.2f} → {ze:+.2f}"
                + (f"   {ang % 360:.0f}°" if ang is not None else ""), None)

    def status_clause(self) -> str:
        return super().status_clause().replace("Ramp:", "Stair:").replace(
            "its first edge", "its first step's edge")
