"""LOOK — the edit windows' shared kit (plan PLANO_JANELAS_EDICAO.md, 0.10.0).

His approval of the mockup (MAQUETAS/janela_escada_v1.html, 2026-10-13):
«interface maravilhosa, totalmente intuitiva… sem necessidade de consultar
help» — and every window with its TABS AT THE TOP.

The pieces, the same in every window:

    Header      gold icon + the name (editable) + a live summary + «?»
    Tabs        tabs across the top (a QTabBar over a QStackedWidget, so a
                side panel can sit beside the pages); materials.with_tab
                adds «Material» as one more
    Fold        a section: arrow + gold title + its choice at the right
                (shown when shut); open / shut remembered
    Chips       a choice as chips — a QComboBox's API (addItem, currentData,
                currentIndexChanged…), so the windows' logic stays as it is;
                with pictures (``pic``) they are picture chips
    Drawing     a small drawing beside the fields: the dimension of the field
                under the mouse / in focus turns gold
    Stats       number tiles · Badge  the green / amber check

The colours are the quick-help card's (quickhelp.py). Dark only: in the
host's light theme ArchXQ's widgets are dark islands (style.py).
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, QSettings, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStackedWidget,
    QTabBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

GOLD = "#e8b33c"
BLUE = "#5bc8e8"
ACCENT = "#e8742c"
OK = "#5cc472"
WIN = "#26282c"
PANEL = "#2e3135"
FIELD = "#1f2124"
LINE = "#3c4046"
TEXT = "#e6e6e6"
MUTED = "#9aa0a6"
INK = "#c9cdd2"           # the drawings' lines
DIM = "#6b7078"

#: Every text's colour is given here: under a style sheet the window's
#: palette does not reach its labels — in the host's LIGHT theme they took
#: its near-black (#14161a) on the dark folds (his screen, 2026-10-13).
#: The specific rules carry «QDialog#axqLook» so they beat the general one.
QSS = f"""
QDialog#axqLook {{ background: {WIN}; color: {TEXT}; }}
QDialog#axqLook QLabel {{ color: {INK}; background: transparent; }}
QDialog#axqLook QLabel:disabled {{ color: {DIM}; }}
QDialog#axqLook QCheckBox, QDialog#axqLook QRadioButton {{ color: {INK};
    background: transparent; }}
QDialog#axqLook QCheckBox:disabled {{ color: {DIM}; }}
QDialog#axqLook QCheckBox::indicator {{ width: 15px; height: 15px;
    border: 1px solid #7a8591; border-radius: 3px; background: {FIELD}; }}
QDialog#axqLook QCheckBox::indicator:hover {{ border-color: {BLUE}; }}
QDialog#axqLook QCheckBox::indicator:checked {{ background: {ACCENT};
    border-color: {ACCENT}; }}
QDialog#axqLook QCheckBox::indicator:disabled {{ border-color: #4a4e55;
    background: #2a2c30; }}
QDialog#axqLook QLabel#axqTitle {{ color: {GOLD}; font-size: 17px;
    font-weight: 600; }}
QDialog#axqLook QLineEdit#axqTitle {{ color: {GOLD}; font-size: 17px;
    font-weight: 600; background: transparent; border: 1px solid transparent;
    border-radius: 4px; padding: 0 2px; }}
QDialog#axqLook QLineEdit#axqTitle:hover {{ border-color: {LINE}; }}
QDialog#axqLook QLineEdit#axqTitle:focus {{ border-color: {BLUE};
    background: {FIELD}; }}
QDialog#axqLook QLabel#axqSummary {{ color: {MUTED}; }}
QTabBar#axqTabs {{ qproperty-drawBase: 0; }}
QTabBar#axqTabs::tab {{ background: transparent; color: {MUTED}; border: none;
    border-bottom: 2px solid transparent; padding: 7px 14px 7px 10px;
    margin-right: 2px; }}
QTabBar#axqTabs::tab:selected {{ color: {TEXT}; border-bottom-color: {ACCENT}; }}
QTabBar#axqTabs::tab:hover:!selected {{ color: {TEXT}; }}
QFrame#axqRule {{ background: {LINE}; max-height: 1px; min-height: 1px; border: none; }}
QFrame#axqFold, QFrame#axqCard {{ background: {PANEL}; border: 1px solid {LINE};
    border-radius: 6px; }}
QDialog#axqLook QLabel#axqFoldTitle, QDialog#axqLook QLabel#axqCardTitle {{
    color: {GOLD}; font-weight: 600; background: transparent; border: none; }}
QDialog#axqLook QLabel#axqArrow, QDialog#axqLook QLabel#axqPick {{
    color: {MUTED}; background: transparent; border: none; }}
QFrame#axqFold QLabel {{ border: none; }}
QToolButton#axqChip, QPushButton#axqChip {{ background: #34373c; color: #d5d8dc;
    border: 1px solid {LINE}; border-radius: 5px; padding: 4px 10px; }}
QToolButton#axqChip:hover, QPushButton#axqChip:hover {{ border-color: #5b6470; }}
QToolButton#axqChip:checked, QPushButton#axqChip:checked {{ background: #4a3324;
    border-color: {ACCENT}; color: white; font-weight: bold; }}
QToolButton#axqChip:disabled, QPushButton#axqChip:disabled {{ color: {DIM};
    border-color: #33363b; }}
QDialog#axqLook QLabel#axqStat {{ background: {FIELD}; border: 1px solid {LINE};
    border-radius: 5px; padding: 5px 8px; color: {MUTED}; }}
QDialog#axqLook QLabel#axqBadge[state="ok"] {{ background: #1f3326;
    border: 1px solid #2f5a3a; border-radius: 5px; padding: 6px 9px;
    color: #bfe8c9; }}
QDialog#axqLook QLabel#axqBadge[state="warn"] {{ background: #3a2f1c;
    border: 1px solid #6b5426; border-radius: 5px; padding: 6px 9px;
    color: #f3d9a4; }}
QDialog#axqLook QLabel#axqHint {{ color: {MUTED}; }}
QPushButton#axqOk {{ background: {ACCENT}; border: 1px solid {ACCENT}; color: white;
    font-weight: bold; padding: 5px 24px; border-radius: 5px; }}
QPushButton#axqOk:hover {{ background: #f08a48; }}
QPushButton#axqDanger {{ color: #ff8a80; }}
QDialog#axqLook QTabWidget::pane {{ border: none; border-top: 1px solid {LINE};
    top: -1px; }}
QDialog#axqLook QTabWidget > QTabBar::tab {{ background: transparent;
    color: {MUTED}; border: none; border-bottom: 2px solid transparent;
    padding: 7px 14px; margin-right: 2px; }}
QDialog#axqLook QTabWidget > QTabBar::tab:selected {{ color: {TEXT};
    border-bottom-color: {ACCENT}; }}
QDialog#axqLook QTabWidget > QTabBar::tab:hover:!selected {{ color: {TEXT}; }}
QDialog#axqLook QTableWidget {{ background: {FIELD}; alternate-background-color: #24272b;
    color: {TEXT}; gridline-color: {LINE}; border: 1px solid {LINE};
    border-radius: 5px; selection-background-color: #4a3324;
    selection-color: white; }}
QDialog#axqLook QHeaderView::section {{ background: {PANEL}; color: {GOLD};
    border: none; border-bottom: 1px solid {LINE}; border-right: 1px solid {LINE};
    padding: 5px 8px; font-weight: 600; }}
QDialog#axqLook QTableCornerButton::section {{ background: {PANEL};
    border: none; }}
QDialog#axqLook QScrollBar:vertical {{ background: transparent; width: 10px;
    margin: 0; }}
QDialog#axqLook QScrollBar::handle:vertical {{ background: #4a4e55;
    border-radius: 4px; min-height: 30px; margin: 1px; }}
QDialog#axqLook QScrollBar::handle:vertical:hover {{ background: #5b6470; }}
QDialog#axqLook QScrollBar::add-line:vertical,
QDialog#axqLook QScrollBar::sub-line:vertical {{ height: 0; }}
QDialog#axqLook QScrollBar::add-page:vertical,
QDialog#axqLook QScrollBar::sub-page:vertical {{ background: transparent; }}
"""


class _WheelGuard(QObject):
    """The mouse wheel in a window never changes a measure unseen (his
    test, 2026-10-13 — the same as the library's, 2026-10-11): a BAR never
    takes it; a field / a list only once clicked (it has the keyboard).
    Otherwise the wheel goes on to the page, which scrolls."""

    def eventFilter(self, obj, ev) -> bool:  # noqa: N802
        from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QSlider
        if ev.type() == QEvent.Wheel and isinstance(
                obj, (QSlider, QAbstractSpinBox, QComboBox)) and (
                isinstance(obj, QSlider) or not obj.hasFocus()):
            ev.ignore()
            return True
        if ev.type() == QEvent.Show and obj.property("axq_wheel") is None:
            obj.setProperty("axq_wheel", True)    # once, as it first shows
            guard(obj)
        return False


_GUARD = _WheelGuard()


def guard(root) -> None:
    """Every bar, field and list under ``root`` behind the wheel guard."""
    from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QSlider
    for cls in (QAbstractSpinBox, QComboBox, QSlider):
        for w in root.findChildren(cls):
            if w.property("axq_wheel_g") is None:
                w.setProperty("axq_wheel_g", True)
                w.installEventFilter(_GUARD)
                if not isinstance(w, QSlider):
                    w.setFocusPolicy(Qt.StrongFocus)  # the wheel: no focus


def dress(dlg) -> None:
    """The window in the house look (its children keep the host's fields)
    — and the wheel guarded, its fields' as it first shows."""
    dlg.setObjectName("axqLook")
    dlg.setStyleSheet(QSS)
    dlg.installEventFilter(_GUARD)


def ok_button(bb) -> None:
    """The OK of a QDialogButtonBox filled orange (one per window)."""
    from PySide6.QtWidgets import QDialogButtonBox
    b = bb.button(QDialogButtonBox.Ok)
    if b is not None:
        b.setObjectName("axqOk")
        b.setDefault(True)


def rule() -> QFrame:
    f = QFrame()
    f.setObjectName("axqRule")
    return f


def hint(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("axqHint")
    lab.setWordWrap(True)
    return lab


# ---- small painted pictures ------------------------------------------------------------
def picture(draw, w: int = 60, h: int = 44, on: bool = False) -> QPixmap:
    """A ``draw(painter, QRectF, on)`` painted into a transparent pixmap
    (crisp on a high-DPI screen). Painted HERE, in the window — never
    through the bridge."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    dpr = app.devicePixelRatio() if app is not None else 1.0
    pm = QPixmap(int(w * dpr), int(h * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    try:
        draw(p, QRectF(0, 0, w, h), on)
    finally:
        p.end()
    return pm


def pen(color: str, width: float = 1.5, dash: bool = False) -> QPen:
    pn = QPen(colour(color), width)
    pn.setCapStyle(Qt.RoundCap)
    pn.setJoinStyle(Qt.RoundJoin)
    if dash:
        pn.setStyle(Qt.DashLine)
    return pn


def colour(c: str) -> QColor:
    """A colour from «#rrggbb» or CSS's «#rrggbbaa» — Qt reads an 8-digit
    hex as #AARRGGBB: «#5bc8e830» (light blue, a little alpha) came out
    olive green (the glass in the openings' front view, his screen,
    2026-10-13)."""
    if isinstance(c, str) and c.startswith("#") and len(c) == 9:
        q = QColor(c[:7])
        q.setAlpha(int(c[7:], 16))
        return q
    return QColor(c)


def poly(p: QPainter, pts, color: str = INK, width: float = 1.5,
         close: bool = False, fill: str | None = None) -> None:
    from PySide6.QtGui import QPolygonF
    pg = QPolygonF([QPointF(*q) for q in pts])
    p.setPen(pen(color, width))
    if close or fill:
        p.setBrush(colour(fill) if fill else Qt.NoBrush)
        p.drawPolygon(pg)
        p.setBrush(Qt.NoBrush)
    else:
        p.drawPolyline(pg)


def text(p: QPainter, x: float, y: float, s: str, color: str = BLUE,
         size: int = 8, bold: bool = True, align=Qt.AlignLeft) -> None:
    f = QFont(p.font())
    f.setPointSizeF(size)
    f.setBold(bold)
    p.setFont(f)
    p.setPen(QColor(color))
    if align == Qt.AlignLeft:
        p.drawText(QPointF(x, y), s)
    else:                              # centred / right on x
        w = p.fontMetrics().horizontalAdvance(s)
        p.drawText(QPointF(x - (w / 2 if align == Qt.AlignHCenter else w), y), s)


def dim(p: QPainter, a, b, label: str, hot: bool, at=None, ticks=True) -> None:
    """A dimension a→b (+ its letter at ``at``), gold when ``hot``."""
    c = GOLD if hot else BLUE
    p.setPen(pen(c, 2.0 if hot else 1.2))
    p.drawLine(QPointF(*a), QPointF(*b))
    if ticks:
        import math
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / n * 3, dx / n * 3
        for q in (a, b):
            p.drawLine(QPointF(q[0] - nx, q[1] - ny), QPointF(q[0] + nx, q[1] + ny))
    if label:
        x, y = at if at is not None else ((a[0] + b[0]) / 2 + 4, (a[1] + b[1]) / 2)
        text(p, x, y, label, c)


def draw_dial(p: QPainter, r, hot, d) -> None:
    """A direction as a dial (0° = the red axis) — a Drawing's ``draw``:
    ``d["a"]`` in degrees, ``hot == "a"`` gold."""
    import math
    c = QPointF(75, 52)
    p.setPen(pen(LINE, 2.0))
    p.drawEllipse(c, 38, 38)
    p.setPen(pen(DIM, 1.0))
    for k in range(4):
        a = math.radians(k * 90)
        p.drawLine(QPointF(c.x() + 32 * math.cos(a), c.y() - 32 * math.sin(a)),
                   QPointF(c.x() + 38 * math.cos(a), c.y() - 38 * math.sin(a)))
    a = math.radians(float(d.get("a", 0.0)))
    col = GOLD if hot == "a" else ACCENT
    p.setPen(pen(col, 3.0))
    p.drawLine(c, QPointF(c.x() + 32 * math.cos(a), c.y() - 32 * math.sin(a)))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(col))
    p.drawEllipse(c, 4, 4)
    p.setBrush(Qt.NoBrush)
    text(p, 146, 14, f"{float(d.get('a', 0.0)) % 360:.0f}°", col,
         align=Qt.AlignRight)


# ---- icons for the tabs ----------------------------------------------------------------
def _ic_geometry(p, r, _on):
    poly(p, [(2, 14), (5, 14), (5, 11), (8, 11), (8, 8), (11, 8), (11, 5),
             (14, 5), (14, 2)], GOLD, 1.6)


def _ic_build(p, r, _on):
    poly(p, [(2, 9), (14, 9), (14, 14), (2, 14)], "#8a8f96", 1.0, fill="#8a8f96")
    poly(p, [(2, 9), (14, 3), (14, 9)], "#b8bcc2", 1.0, fill="#b8bcc2")


def _ic_railing(p, r, _on):
    p.setPen(pen(BLUE, 1.6))
    for a, b in (((1, 5), (15, 5)), ((3, 5), (3, 14)), ((8, 5), (8, 14)),
                 ((13, 5), (13, 14))):
        p.drawLine(QPointF(*a), QPointF(*b))


def _ic_position(p, r, _on):
    p.setPen(pen(ACCENT, 1.6))
    p.drawEllipse(QPointF(8, 8), 5.5, 5.5)
    p.setBrush(QColor(ACCENT))
    p.drawEllipse(QPointF(8, 8), 1.6, 1.6)
    p.setBrush(Qt.NoBrush)


def _ic_material(p, r, _on):
    for i, c in enumerate(("#c49a6c", "#8a8f96", BLUE, GOLD)):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(c))
        p.drawRoundedRect(QRectF(1 + (i % 2) * 7.5, 1 + (i // 2) * 7.5, 6.5, 6.5), 1.5, 1.5)
    p.setBrush(Qt.NoBrush)


TAB_ICONS = {"geometry": _ic_geometry, "build": _ic_build, "railing": _ic_railing,
             "position": _ic_position, "material": _ic_material}


def tab_icon(name) -> QIcon:
    draw = TAB_ICONS.get(name) if isinstance(name, str) else name
    if draw is None:
        return QIcon()
    return QIcon(picture(draw, 16, 16))


# ---- the header ------------------------------------------------------------------------
class Header(QWidget):
    """Icon · name (a QLineEdit when ``editable``: renamed in place) · the
    live summary under it · «?»."""

    def __init__(self, icon_draw, name: str, help_topic=None,
                 editable: bool = False) -> None:
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 2)
        lay.setSpacing(12)
        ic = QLabel()
        ic.setPixmap(picture(icon_draw, 40, 40))
        ic.setFixedSize(40, 40)
        lay.addWidget(ic, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(1)
        if editable:
            self.name = QLineEdit(name)
            self.name.setToolTip("Its name — click to change it")
            # not in focus as the window opens (it showed as being typed in
            # — his screen, 2026-10-13): a click renames it
            self.name.setFocusPolicy(Qt.ClickFocus)
        else:
            self.name = QLabel(name)
        self.name.setObjectName("axqTitle")
        col.addWidget(self.name)
        self.summary = QLabel()
        self.summary.setObjectName("axqSummary")
        self.summary.setTextFormat(Qt.RichText)
        self.summary.setWordWrap(True)
        col.addWidget(self.summary)
        lay.addLayout(col, 1)
        if help_topic is not None:
            from .help import help_button
            b = help_button(help_topic)
            b.setFixedSize(24, 24)
            lay.addWidget(b, 0, Qt.AlignTop)

    def set_summary(self, parts) -> None:
        """``parts``: strings — a «{…}» in one is shown in blue."""
        import html
        out = []
        for s in parts:
            if not s:
                continue                   # a part that does not apply
            s = html.escape(s)
            s = s.replace("{", f"<span style='color:{BLUE}'>").replace("}", "</span>")
            out.append(s)
        self.summary.setText(" · ".join(out))


# ---- the tabs --------------------------------------------------------------------------
class Tabs(QObject):
    """Tabs across the top: ``bar`` (put it under the header) and ``stack``
    (put it where the pages go — a side panel may sit beside it). The API
    materials.with_tab uses: addTab, currentIndex, setCurrentIndex,
    currentWidget, count."""

    currentChanged = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.bar = QTabBar()
        self.bar.setObjectName("axqTabs")
        self.bar.setDrawBase(False)
        self.bar.setExpanding(False)
        self.bar.setIconSize(QSize(16, 16))
        self.bar.setFocusPolicy(Qt.NoFocus)
        self.stack = QStackedWidget()
        self.bar.currentChanged.connect(self._go)

    def _go(self, i: int) -> None:
        if 0 <= i < self.stack.count():
            self.stack.setCurrentIndex(i)
        self.currentChanged.emit(i)

    def addTab(self, widget, text: str, icon=None) -> int:  # noqa: N802 — Qt's
        self.stack.addWidget(widget)
        # «&» shown as itself, not a shortcut («Repeat & copy» read
        # «Repeat _copy» — his screen, 2026-10-13)
        i = self.bar.addTab(tab_icon(icon or text.lower()),
                            text.replace("&", "&&"))
        return i

    def count(self) -> int:
        return self.stack.count()

    def currentIndex(self) -> int:  # noqa: N802
        return self.bar.currentIndex()

    def setCurrentIndex(self, i: int) -> None:  # noqa: N802
        self.bar.setCurrentIndex(i)

    def currentWidget(self):  # noqa: N802
        return self.stack.currentWidget()


def page() -> tuple[QWidget, QVBoxLayout]:
    """A tab's page — scrolled when the screen is short (1366×768): its
    folds go in ``lay``; ``lay.addStretch()`` after the last."""
    from PySide6.QtWidgets import QScrollArea
    inner = QWidget()
    inner.setObjectName("axqPage")
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(0, 8, 6, 0)
    lay.setSpacing(8)
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setFrameShape(QFrame.NoFrame)
    sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sc.setStyleSheet("QScrollArea, QWidget#axqPage { background: transparent; }")
    sc.setWidget(inner)
    sc.viewport().setAutoFillBackground(False)
    return sc, lay


# ---- a fold ----------------------------------------------------------------------------
class _Head(QWidget):
    def __init__(self, fold) -> None:
        super().__init__()
        self.fold = fold
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton:
            self.fold.toggle()


class Fold(QFrame):
    """A section: ▾ Title ……… its choice. ``key``: its open / shut state
    remembered (QSettings archxq/folds/<key>). Its body: ``form()`` (a
    QFormLayout, a ``drawing`` beside it if given) or ``box`` (a
    QVBoxLayout)."""

    def __init__(self, title: str, key: str = "", opened: bool = True) -> None:
        super().__init__()
        self.setObjectName("axqFold")
        self.key = key
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        head = _Head(self)
        hl = QHBoxLayout(head)
        hl.setContentsMargins(10, 7, 10, 7)
        hl.setSpacing(8)
        self.arrow = QLabel("▾")
        self.arrow.setObjectName("axqArrow")
        self.arrow.setFixedWidth(10)
        hl.addWidget(self.arrow)
        t = QLabel(title)
        t.setObjectName("axqFoldTitle")
        hl.addWidget(t)
        hl.addStretch(1)
        self.pick = QLabel()
        self.pick.setObjectName("axqPick")
        hl.addWidget(self.pick)
        lay.addWidget(head)
        self.body = QWidget()
        self.box = QVBoxLayout(self.body)
        self.box.setContentsMargins(26, 2, 12, 12)
        self.box.setSpacing(8)
        lay.addWidget(self.body)
        if key:
            v = QSettings().value(f"archxq/folds/{key}")
            if v is not None:
                opened = str(v).lower() in ("true", "1")
        self.set_open(opened)

    def form(self, drawing=None) -> QFormLayout:
        """Its fields' form — the drawing at its left (stacked when narrow
        is not needed: the windows are wide enough)."""
        f = QFormLayout()
        f.setHorizontalSpacing(10)
        f.setVerticalSpacing(6)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        f.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        if drawing is None:
            self.box.addLayout(f)
        else:
            row = QHBoxLayout()
            row.setSpacing(14)
            row.addWidget(drawing, 0, Qt.AlignTop)
            row.addLayout(f, 1)
            self.box.addLayout(row)
        return f

    def set_pick(self, s: str) -> None:
        self.pick.setText(s)

    def is_open(self) -> bool:
        return not self.body.isHidden()

    def set_open(self, on: bool) -> None:
        self.body.setVisible(on)
        self.arrow.setText("▾" if on else "▸")
        self.pick.setVisible(True)

    def toggle(self) -> None:
        self.set_open(not self.is_open())
        if self.key:
            QSettings().setValue(f"archxq/folds/{self.key}", self.is_open())


# ---- chips -----------------------------------------------------------------------------
class Chips(QWidget):
    """One choice, as chips — with a QComboBox's API so a window's code
    reads it as before (``addItem``, ``currentData``, ``currentIndex``,
    ``setCurrentIndex``, ``findData``, ``currentIndexChanged``…). With
    ``pic`` (a ``draw(painter, rect, on)``) a chip is a picture over its
    words."""

    currentIndexChanged = Signal(int)

    PIC = (60, 44)

    def __init__(self, parent=None, wrap: int = 0, width: int = 0,
                 pic: tuple = (60, 44)) -> None:
        super().__init__(parent)
        self.PIC = tuple(pic)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.lay = QHBoxLayout(self) if not wrap else QGridLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(6)
        self.wrap = wrap
        self.width_ = width
        self.datas = []
        self.texts = []
        self.group.idClicked.connect(self._clicked)
        self._tail = None
        if not wrap:
            self.lay.addStretch(1)

    def addItem(self, text: str, data=None, tip: str = "", pic=None) -> None:  # noqa: N802
        b = QToolButton()
        b.setObjectName("axqChip")
        b.setCheckable(True)
        b.setText(text)
        b.setFocusPolicy(Qt.TabFocus)
        b.setCursor(Qt.PointingHandCursor)
        if tip:
            b.setToolTip(tip)
        if pic is not None:
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setIcon(QIcon(picture(pic, *self.PIC)))
            b.setIconSize(QSize(*self.PIC))
            b.setMinimumWidth(self.width_ or 92)
        elif self.width_:
            b.setMinimumWidth(self.width_)
        i = len(self.datas)
        self.group.addButton(b, i)
        if self.wrap:
            self.lay.addWidget(b, i // self.wrap, i % self.wrap)
        else:
            self.lay.insertWidget(self.lay.count() - 1, b)
        self.datas.append(text if data is None else data)
        self.texts.append(text)
        if self.group.checkedId() < 0:
            b.setChecked(True)

    # -- QComboBox's ----------------------------------------------------------------
    def count(self) -> int:
        return len(self.datas)

    def currentIndex(self) -> int:  # noqa: N802
        return self.group.checkedId()

    def currentData(self):  # noqa: N802
        i = self.group.checkedId()
        return self.datas[i] if 0 <= i < len(self.datas) else None

    def currentText(self) -> str:  # noqa: N802
        i = self.group.checkedId()
        return self.texts[i] if 0 <= i < len(self.texts) else ""

    def itemData(self, i: int):  # noqa: N802
        return self.datas[i]

    def findData(self, data) -> int:  # noqa: N802
        for i, d in enumerate(self.datas):
            if d == data:
                return i
        return -1

    def setCurrentIndex(self, i: int) -> None:  # noqa: N802
        b = self.group.button(i)
        if b is None or b.isChecked():
            return
        b.setChecked(True)
        self.currentIndexChanged.emit(i)

    def setItemEnabled(self, i: int, on: bool) -> None:  # noqa: N802
        b = self.group.button(i)
        if b is not None:
            b.setEnabled(on)

    def button(self, i: int):
        return self.group.button(i)

    def _clicked(self, i: int) -> None:
        self.currentIndexChanged.emit(i)


def chips(items, current=None, pics=None, tip: str = "", width: int = 0,
          wrap: int = 0) -> Chips:
    """Chips from ((value, text), …) — ``pics``: {value: draw}."""
    c = Chips(width=width, wrap=wrap)
    for it in items:
        v, t = it[0], it[1]
        c.addItem(t, v, pic=(pics or {}).get(v))
    if tip:
        c.setToolTip(tip)
    i = c.findData(current)
    if i >= 0:
        c.group.button(i).setChecked(True)
    return c


# ---- a measure: a bar + its field ------------------------------------------------------
SLIDER_CSS = ("QSlider::groove:horizontal { height: 6px; border-radius: 3px; "
              "background: #3a3f45; }"
              "QSlider::sub-page:horizontal { height: 6px; border-radius: 3px; "
              f"background: {BLUE}; }}"
              "QSlider::handle:horizontal { width: 16px; height: 16px; "
              "margin: -5px 0; border-radius: 8px; background: #e8eaed; "
              f"border: 2px solid {BLUE}; }}"
              "QSlider::handle:horizontal:hover { background: #ffffff; }"
              "QSlider::groove:horizontal:disabled, "
              "QSlider::sub-page:horizontal:disabled { background: #33363b; }"
              "QSlider::handle:horizontal:disabled { background: #6b7078; "
              "border-color: #4a4e55; }")


class Measure(QWidget):
    """A measure as the library shows it: a BAR to drag + its FIELD to type
    (his ask, 2026-10-13: «você não está usando barras para as medidas?»),
    kept in step. It answers as the QDoubleSpinBox it replaces (value,
    setValue, valueChanged, setDecimals, setRange, setSingleStep,
    setToolTip, setEnabled…), so a window's logic reads it unchanged."""

    valueChanged = Signal(float)

    def __init__(self, value: float, lo: float, hi: float,
                 step: float = 0.05, suffix: str = " m") -> None:
        from PySide6.QtWidgets import QDoubleSpinBox, QSlider
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.bar = QSlider(Qt.Horizontal)
        self.bar.setStyleSheet(SLIDER_CSS)
        self.bar.setFocusPolicy(Qt.NoFocus)
        self.bar.setCursor(Qt.PointingHandCursor)
        self.field = QDoubleSpinBox()
        # millimetre steps (a riser, a nosing) show 3 decimals FROM THE
        # START: set after the value, it was already rounded to 2
        self.field.setDecimals(3 if step < 0.01 - 1e-9 else 2)
        self.field.setSuffix(suffix)
        self.field.setFixedWidth(104)
        self.field.setKeyboardTracking(False)
        lay.addWidget(self.bar, 1)
        lay.addWidget(self.field)
        self._step = step
        self._busy = False
        self.setRange(lo, hi)
        self.field.setSingleStep(step)
        self.field.setValue(value)
        self._to_bar(value)
        self.field.valueChanged.connect(self._typed)
        self.bar.valueChanged.connect(self._dragged)
        self.setFocusProxy(self.field)

    # -- in step ---------------------------------------------------------------------
    def _to_bar(self, v: float) -> None:
        self._busy = True
        try:
            self.bar.setValue(int(round((v - self.field.minimum())
                                        / max(self._step, 1e-6))))
        finally:
            self._busy = False

    def _typed(self, v: float) -> None:
        if not self._busy:
            self._to_bar(v)
        self.valueChanged.emit(v)

    def _dragged(self, i: int) -> None:
        if self._busy:
            return
        v = self.field.minimum() + i * self._step
        self._busy = True
        try:
            self.field.setValue(v)        # emits valueChanged via _typed
        finally:
            self._busy = False

    # -- a QDoubleSpinBox's --------------------------------------------------------------
    def value(self) -> float:
        return self.field.value()

    def setValue(self, v: float) -> None:  # noqa: N802
        self.field.setValue(v)

    def setRange(self, lo: float, hi: float) -> None:  # noqa: N802
        self.field.setRange(lo, hi)
        self.bar.setRange(0, max(1, int(round((hi - lo) / max(self._step,
                                                               1e-6)))))

    def setDecimals(self, n: int) -> None:  # noqa: N802
        self.field.setDecimals(n)

    def setSingleStep(self, s: float) -> None:  # noqa: N802
        self.field.setSingleStep(s)

    def setSuffix(self, s: str) -> None:  # noqa: N802
        self.field.setSuffix(s)

    def setSpecialValueText(self, s: str) -> None:  # noqa: N802
        self.field.setSpecialValueText(s)

    def minimum(self) -> float:
        return self.field.minimum()

    def maximum(self) -> float:
        return self.field.maximum()

    def setToolTip(self, s: str) -> None:  # noqa: N802
        super().setToolTip(s)
        self.field.setToolTip(s)
        self.bar.setToolTip(s)


def metres(value: float, lo: float, hi: float, step: float = 0.05) -> Measure:
    """dialogs._metres' place in the new windows: a bar + its field."""
    return Measure(value, lo, hi, step)


# ---- the drawing beside the fields -----------------------------------------------------
class Drawing(QWidget):
    """``draw(painter, QRectF, hot, data)`` — ``hot``: the key of the field
    under the mouse / in focus (``link``); ``data``: what the window gives
    (``set``)."""

    def __init__(self, draw, w: int = 150, h: int = 110) -> None:
        super().__init__()
        self.draw = draw
        self.hot = None
        self.data = {}
        self._focus = None
        self.setFixedSize(w, h)

    def set(self, **data) -> None:
        self.data.update(data)
        self.update()

    def link(self, widget, key: str) -> None:
        """The field ``widget`` lights up ``key`` in the drawing."""
        f = _Hot(self, key)
        f.setParent(widget)
        widget.installEventFilter(f)
        for e in widget.findChildren(QLineEdit):
            e.installEventFilter(f)

    def _hot(self, key, on: bool, focus: bool = False) -> None:
        if focus:
            self._focus = key if on else (None if self._focus == key else self._focus)
        new = key if on else self._focus
        if new != self.hot:
            self.hot = new
            self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        try:
            self.draw(p, QRectF(self.rect()), self.hot, self.data)
        except Exception:  # noqa: BLE001 — a drawing never breaks the window
            import traceback
            traceback.print_exc()
        finally:
            p.end()


class _Hot(QObject):
    def __init__(self, drawing: Drawing, key: str) -> None:
        super().__init__()
        self.drawing, self.key = drawing, key

    def eventFilter(self, _o, e) -> bool:  # noqa: N802
        t = e.type()
        if t == QEvent.Enter:
            self.drawing._hot(self.key, True)
        elif t == QEvent.Leave:
            self.drawing._hot(self.key, False)
        elif t == QEvent.FocusIn:
            self.drawing._hot(self.key, True, focus=True)
        elif t == QEvent.FocusOut:
            self.drawing._hot(self.key, False, focus=True)
        return False


# ---- the side panel: a card, number tiles, the check -----------------------------------
class Card(QFrame):
    def __init__(self, title: str, right: QWidget | None = None) -> None:
        super().__init__()
        self.setObjectName("axqCard")
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(10, 8, 10, 10)
        self.box.setSpacing(8)
        head = QHBoxLayout()
        t = QLabel(title)
        t.setObjectName("axqCardTitle")
        head.addWidget(t)
        head.addStretch(1)
        if right is not None:
            head.addWidget(right)
        self.box.addLayout(head)


class Stats(QWidget):
    """Number tiles, two a row: ``set([(value, caption), …])``."""

    def __init__(self, n: int = 4) -> None:
        super().__init__()
        g = QGridLayout(self)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(6)
        self.tiles = []
        for i in range(n):
            lab = QLabel()
            lab.setObjectName("axqStat")
            lab.setTextFormat(Qt.RichText)
            g.addWidget(lab, i // 2, i % 2)
            self.tiles.append(lab)

    def set(self, items) -> None:
        for lab, it in zip(self.tiles, list(items) + [None] * len(self.tiles)):
            if it is None:
                lab.hide()
                continue
            v, cap = it
            lab.setText(f"<span style='color:{BLUE};font-size:15px;"
                        f"font-weight:600'>{v}</span><br>{cap}")
            lab.show()


class Badge(QLabel):
    """The check: ``set(ok, text)`` — green ✓ or amber !."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("axqBadge")
        self.setWordWrap(True)
        self.setTextFormat(Qt.RichText)

    def set(self, ok: bool, text_: str) -> None:
        mark = (f"<b style='color:{OK}'>✓</b>" if ok
                else "<b style='color:#f0b44c'>!</b>")
        self.setProperty("state", "ok" if ok else "warn")
        self.style().unpolish(self)
        self.style().polish(self)
        self.setText(f"{mark}&nbsp; {text_}")
