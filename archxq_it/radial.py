"""The RADIAL MENU at the mouse — his «very important» ask (2026-10-09,
built 2026-10-10): a ring of round buttons round the element just clicked,
as ArchiCAD's Pet Palette. Its actions DRIVE THE HOST'S OWN GESTURES, the
ones ArchXQ already adopts (``edits.py``): Move (M), a copy (Move + Ctrl),
an array (a copy, then «x3» / «/3»), Rotate (Q) — and the element's own
window. Never below the host: no gesture of our own.

It shows for the elements those gestures move (columns, beams, footings,
slabs, ramps, stairs); it goes on Esc, a click elsewhere, an action picked,
or the pointer going well away from it.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QKeyEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QToolButton, QWidget

INK = QColor("#e6e8eb")
ACCENT = QColor("#e8742c")
#: the kinds the host's Move / Rotate move (their records follow: edits.py)
MOVABLE = {"column", "beam", "footing", "slab", "ramp", "stair"}
R = 50            # the ring's radius (px)
B = 34            # a button's size

BUTTON_CSS = ("QToolButton { background: rgba(32, 35, 40, 235); "
              "border: 1px solid #4a5058; border-radius: 17px; }"
              "QToolButton:hover { border: 2px solid #e8742c; "
              "background: rgba(74, 51, 36, 245); }")


def _icon(kind: str) -> QIcon:
    s = 44
    pm = QPixmap(s, s)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(INK, 3.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    c = s / 2
    if kind == "move":                       # four arrows
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            tip = QPointF(c + dx * 15, c + dy * 15)
            p.drawLine(QPointF(c, c), tip)
            nx, ny = -dy, dx
            p.drawLine(tip, QPointF(tip.x() - dx * 6 + nx * 5,
                                    tip.y() - dy * 6 + ny * 5))
            p.drawLine(tip, QPointF(tip.x() - dx * 6 - nx * 5,
                                    tip.y() - dy * 6 - ny * 5))
    elif kind == "copy":                     # two boxes, one over the other
        p.drawRect(QRectF(8, 14, 18, 18))
        p.setPen(QPen(ACCENT, 3.2))
        p.drawRect(QRectF(18, 8, 18, 18))
    elif kind == "array":                    # three in a row
        for i in range(3):
            if i == 2:
                p.setPen(QPen(ACCENT, 3.2))
            p.drawRect(QRectF(5 + i * 12, 15, 10, 14))
    elif kind == "rotate":                   # an arc and its arrow
        p.drawArc(QRectF(9, 9, 26, 26), 40 * 16, 280 * 16)
        a = math.radians(40)
        tip = QPointF(c + 13 * math.cos(a), c - 13 * math.sin(a))
        p.setPen(QPen(ACCENT, 3.2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(tip, QPointF(tip.x() - 8, tip.y() - 2))
        p.drawLine(tip, QPointF(tip.x() + 1, tip.y() + 8))
    elif kind == "edit":                     # a pencil
        p.drawLine(QPointF(12, 32), QPointF(30, 14))
        p.drawLine(QPointF(30, 14), QPointF(34, 18))
        p.drawLine(QPointF(34, 18), QPointF(16, 36))
        p.setPen(QPen(ACCENT, 3.2))
        p.drawLine(QPointF(12, 32), QPointF(10, 38))
        p.drawLine(QPointF(10, 38), QPointF(16, 36))
    elif kind == "close":                    # ×
        p.drawLine(QPointF(14, 14), QPointF(30, 30))
        p.drawLine(QPointF(30, 14), QPointF(14, 30))
    p.end()
    return QIcon(pm)


#: (key, tooltip) — clockwise from the top
ACTIONS = (("move", "Move (M) — click a point, then where it goes"),
           ("copy", "Copy — Move with Ctrl: click a point, then where the "
                    "copy goes"),
           ("array", "Array — place ONE copy, then type x3 + Enter (with "
                     "the x; «3» alone is a distance) · /3: three between"),
           ("rotate", "Rotate (Q)"),
           ("edit", "Its window — sizes and details"),
           ("close", "Close (Esc)"))


class RadialMenu(QWidget):
    """The ring itself: a child of the 3D view, round the click."""

    def __init__(self, viewport, owner) -> None:
        super().__init__(viewport)
        self.viewport = viewport
        self.owner = owner
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        side = 2 * R + B + 4
        self.resize(side, side)
        self.centre = QPointF(side / 2, side / 2)
        self.buttons = {}
        n = len(ACTIONS)
        for i, (key, tip) in enumerate(ACTIONS):
            b = QToolButton(self)
            b.setIcon(_icon(key))
            b.setIconSize(QSize(22, 22))
            b.setFixedSize(B, B)
            b.setToolTip(tip)
            b.setStyleSheet(BUTTON_CSS)
            b.setCursor(Qt.ArrowCursor)
            b.setFocusPolicy(Qt.NoFocus)
            a = -math.pi / 2 + 2 * math.pi * i / n
            b.move(int(self.centre.x() + R * math.cos(a) - B / 2),
                   int(self.centre.y() + R * math.sin(a) - B / 2))
            b.clicked.connect(lambda _c=False, k=key: self._act(k))
            self.buttons[key] = b
        # in the middle: «?» — what it is, F9, the Settings (his ask)
        from .help import show_help
        q = QToolButton(self)
        q.setText("?")
        q.setFixedSize(20, 20)
        q.setToolTip("About this ring — F9 switches it on / off")
        q.setFocusPolicy(Qt.NoFocus)
        q.setCursor(Qt.ArrowCursor)
        q.setStyleSheet("QToolButton { color: white; font-weight: bold; "
                        "font-size: 11px; background: #e8742c; border: none; "
                        "border-radius: 10px; padding: 0; }"
                        "QToolButton:hover { background: #ff8a3d; }")
        q.move(int(self.centre.x() - 10), int(self.centre.y() - 10))
        q.clicked.connect(lambda: show_help("radial", q))
        self.help = q
        self.at = None
        self.hide()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(232, 116, 44, 150), 1.5, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(self.centre, R, R)          # (its «?» marks the click)

    def popup(self, x: float, y: float) -> None:
        """Round the point clicked (kept inside the view)."""
        w, h = self.width(), self.height()
        vw, vh = self.viewport.width(), self.viewport.height()
        left = int(min(max(x - w / 2, 0), max(vw - w, 0)))
        top = int(min(max(y - h / 2, 0), max(vh - h, 0)))
        self.move(left, top)
        self.at = (x, y)
        self.show()
        self.raise_()

    def dismiss(self) -> None:
        if self.isVisible():
            self.hide()
        self.at = None

    def far(self, x: float, y: float) -> bool:
        """The pointer well away from it (it goes)."""
        if self.at is None:
            return False
        return math.dist((x, y), self.at) > R + 110

    def _act(self, key: str) -> None:
        self.dismiss()
        if key != "close":
            QTimer.singleShot(0, lambda: self.owner.radial_action(key))


def trigger(viewport, text: str) -> bool:
    """The host's own menu action named ``text`` (Move, Rotate…)."""
    from PySide6.QtGui import QAction
    for act in viewport.window().findChildren(QAction):
        if act.text().replace("&", "").strip().lower() == text.lower() \
                and act.isEnabled():
            act.trigger()
            return True
    return False


def tap_ctrl(viewport) -> None:
    """Ctrl tapped in the 3D view: the host's Move turns into a copy."""
    for t in (QEvent.KeyPress, QEvent.KeyRelease):
        QApplication.sendEvent(viewport, QKeyEvent(t, Qt.Key_Control,
                                                   Qt.ControlModifier))
