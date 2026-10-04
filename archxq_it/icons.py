"""Tool icons for the left strip.

IngeTrazo draws its own icons (views.icons) — reusing them keeps ArchXQ
looking like part of the program. The few ArchXQ needs that the host has
no picture for are drawn here in the same spirit: a plain picture of what
the tool does, light ink with the host's orange accent.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

INK = QColor("#d6d9dd")
ACCENT = QColor("#e8742c")
PX = 64


def _canvas():
    pm = QPixmap(PX, PX)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    return pm, p


def _pen(color=INK, w=4.0, dash=False) -> QPen:
    pen = QPen(color, w)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    if dash:
        pen.setStyle(Qt.DashLine)
    return pen


def _dot(p, x, y, r=5.0, color=ACCENT) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawEllipse(QPointF(x, y), r, r)


def _survey(p) -> None:
    """Scattered survey points, one of them marked."""
    for x, y in ((14, 44), (26, 20), (40, 36), (52, 16), (50, 50),
                 (22, 54)):
        _dot(p, x, y, 4.0, INK)
    p.setPen(_pen(ACCENT, 3.5))
    p.drawLine(QPointF(40, 26), QPointF(40, 46))
    p.drawLine(QPointF(30, 36), QPointF(50, 36))


def _add_point(p) -> None:
    """An edge with a new point on it (+)."""
    p.setPen(_pen())
    p.drawLine(QPointF(8, 48), QPointF(56, 48))
    _dot(p, 8, 48, 4.0, INK)
    _dot(p, 56, 48, 4.0, INK)
    _dot(p, 32, 48, 6.0)
    p.setPen(_pen(ACCENT, 4))
    p.drawLine(QPointF(32, 10), QPointF(32, 32))
    p.drawLine(QPointF(21, 21), QPointF(43, 21))


def _fit(p) -> None:
    """A dashed plot around a small building."""
    p.setPen(_pen(INK, 3.5, dash=True))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(8, 8, 48, 48))
    p.setPen(_pen(ACCENT, 4))
    p.drawRect(QRectF(22, 24, 20, 18))
    p.drawLine(QPointF(20, 26), QPointF(32, 16))
    p.drawLine(QPointF(32, 16), QPointF(44, 26))


def _excavate(p) -> None:
    """Ground line with a stepped pit below it."""
    p.setPen(_pen())
    p.drawLine(QPointF(4, 22), QPointF(18, 22))
    p.drawLine(QPointF(46, 22), QPointF(60, 22))
    p.setPen(_pen(ACCENT, 4))
    p.drawLine(QPointF(18, 22), QPointF(24, 48))
    p.drawLine(QPointF(24, 48), QPointF(40, 48))
    p.drawLine(QPointF(40, 48), QPointF(46, 22))


def _eye_shape(p, color) -> None:
    from PySide6.QtGui import QPainterPath
    path = QPainterPath()
    path.moveTo(6, 32)
    path.quadTo(32, 6, 58, 32)
    path.quadTo(32, 58, 6, 32)
    p.setPen(_pen(color, 4))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)


def _eye(p) -> None:
    """Shown: an open eye."""
    _eye_shape(p, INK)
    _dot(p, 32, 32, 8.0, INK)


def _eye_off(p) -> None:
    """Hidden: a dim eye, struck through."""
    dim = QColor(INK)
    dim.setAlpha(110)
    _eye_shape(p, dim)
    p.setPen(_pen(dim, 4))
    p.drawLine(QPointF(12, 52), QPointF(52, 12))


def _edit(p) -> None:
    """A pencil: open the thing's own window."""
    p.setPen(_pen(INK, 4))
    p.drawLine(QPointF(16, 48), QPointF(46, 18))
    p.drawLine(QPointF(24, 56), QPointF(54, 26))
    p.drawLine(QPointF(46, 18), QPointF(54, 26))
    p.drawLine(QPointF(16, 48), QPointF(12, 60))
    p.drawLine(QPointF(24, 56), QPointF(12, 60))


def _ramp(p) -> None:
    """Ground line, a ramp going down into a pit."""
    p.setPen(_pen())
    p.drawLine(QPointF(4, 20), QPointF(20, 20))
    p.drawLine(QPointF(50, 46), QPointF(60, 46))
    p.drawLine(QPointF(50, 46), QPointF(50, 20))
    p.drawLine(QPointF(50, 20), QPointF(60, 20))
    p.setPen(_pen(ACCENT, 4.5))
    p.drawLine(QPointF(20, 20), QPointF(50, 46))
    p.setPen(_pen(ACCENT, 3))
    p.drawLine(QPointF(30, 46), QPointF(40, 46))      # the arrow: down
    p.drawLine(QPointF(40, 46), QPointF(36, 41))


def _sq(p, x, y, s=10.0, color=ACCENT) -> None:
    """A column's section: a filled square centred on (x, y)."""
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawRect(QRectF(x - s / 2, y - s / 2, s, s))


def _col_single(p) -> None:
    """One column (a square), its axes dashed."""
    p.setPen(_pen(INK, 2.5, dash=True))
    p.drawLine(QPointF(8, 32), QPointF(56, 32))
    p.drawLine(QPointF(32, 8), QPointF(32, 56))
    _sq(p, 32, 32, 18)


def _col_row(p) -> None:
    """Columns in a row."""
    p.setPen(_pen(INK, 2.5, dash=True))
    p.drawLine(QPointF(4, 32), QPointF(60, 32))
    for x in (12, 32, 52):
        _sq(p, x, 32, 12)


def _col_grid(p) -> None:
    """A grid of columns."""
    p.setPen(_pen(INK, 2.0, dash=True))
    for v in (12, 32, 52):
        p.drawLine(QPointF(v, 4), QPointF(v, 60))
        p.drawLine(QPointF(4, v), QPointF(60, v))
    for x in (12, 32, 52):
        for y in (12, 32, 52):
            _sq(p, x, y, 9)


def _col_corners(p) -> None:
    """Walls (an L and a T), a column where they meet."""
    p.setPen(_pen(INK, 5))
    p.drawLine(QPointF(10, 54), QPointF(10, 10))
    p.drawLine(QPointF(10, 10), QPointF(56, 10))
    p.drawLine(QPointF(36, 10), QPointF(36, 54))
    _sq(p, 10, 10, 12)
    _sq(p, 36, 10, 12)


def _beam_walls(p) -> None:
    """A wall (outline) with a beam along its top (orange band)."""
    p.setPen(_pen(INK, 3))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(10, 26, 44, 30))
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawRect(QRectF(6, 14, 52, 11))


def _slab_walls(p) -> None:
    """Walls round a room (outline), the slab filling it."""
    p.setPen(Qt.NoPen)
    c = QColor(ACCENT)
    c.setAlpha(150)
    p.setBrush(c)
    p.drawRect(QRectF(8, 8, 48, 48))
    p.setPen(_pen(INK, 4.5))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(8, 8, 48, 48))
    p.drawLine(QPointF(32, 8), QPointF(32, 34))


def _slab_hole(p) -> None:
    """A slab (filled) with an opening through it (dashed)."""
    c = QColor(INK)
    c.setAlpha(120)
    p.setPen(Qt.NoPen)
    p.setBrush(c)
    path_rect = QRectF(6, 10, 52, 44)
    p.drawRect(path_rect)
    p.setBrush(QColor(0, 0, 0, 0))
    p.setCompositionMode(QPainter.CompositionMode_Clear)
    p.drawRect(QRectF(26, 22, 22, 20))
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.setPen(_pen(ACCENT, 3.5, dash=True))
    p.drawRect(QRectF(26, 22, 22, 20))


def _roof_walls(p) -> None:
    """A house's walls (outline) with a gable roof over them."""
    from PySide6.QtGui import QPolygonF
    c = QColor(ACCENT)
    c.setAlpha(170)
    p.setPen(_pen(ACCENT, 3.5))
    p.setBrush(c)
    p.drawPolygon(QPolygonF([QPointF(4, 32), QPointF(32, 8),
                             QPointF(60, 32)]))
    p.setPen(_pen(INK, 4.5))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(12, 32, 40, 24))


def _sheet(p) -> None:
    """A landscape sheet with its title block."""
    p.setPen(_pen(INK, 3.5))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(4, 12, 56, 40))
    p.drawLine(QPointF(36, 44), QPointF(60, 44))
    p.drawLine(QPointF(36, 44), QPointF(36, 52))


def _doc_sheets(p) -> None:
    """A sheet with a plan on it: make the drawings and sheets."""
    _sheet(p)
    p.setPen(_pen(ACCENT, 3.5))
    p.drawRect(QRectF(12, 18, 18, 20))
    p.drawLine(QPointF(21, 18), QPointF(21, 28))


def _io(p) -> None:
    """A folder with an arrow in and an arrow out: import / export."""
    from PySide6.QtGui import QPolygonF
    p.setPen(_pen(INK, 4))
    p.setBrush(Qt.NoBrush)
    p.drawPolygon(QPolygonF([QPointF(4, 18), QPointF(22, 18), QPointF(28, 24),
                             QPointF(60, 24), QPointF(60, 56),
                             QPointF(4, 56)]))
    p.setPen(_pen(ACCENT, 4.5))
    p.drawLine(QPointF(20, 34), QPointF(20, 50))       # in: down
    p.drawLine(QPointF(14, 44), QPointF(20, 50))
    p.drawLine(QPointF(26, 44), QPointF(20, 50))
    p.drawLine(QPointF(44, 50), QPointF(44, 34))       # out: up
    p.drawLine(QPointF(38, 40), QPointF(44, 34))
    p.drawLine(QPointF(50, 40), QPointF(44, 34))


def _grid_snap(p) -> None:
    """A grid with a magnet dot on a crossing: snap to the grid."""
    p.setPen(_pen(INK, 3))
    for k in (12, 32, 52):
        p.drawLine(QPointF(k, 6), QPointF(k, 58))
        p.drawLine(QPointF(6, k), QPointF(58, k))
    _dot(p, 32, 32, 8.0)


def _web(p) -> None:
    """A globe: the ArchXQ page."""
    p.setPen(_pen(INK, 4))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(32, 32), 24, 24)
    p.drawEllipse(QPointF(32, 32), 10, 24)
    p.drawLine(QPointF(8, 32), QPointF(56, 32))
    p.setPen(_pen(ACCENT, 3.5))
    p.drawLine(QPointF(13, 20), QPointF(51, 20))
    p.drawLine(QPointF(13, 44), QPointF(51, 44))


def _doc_dxf(p) -> None:
    """A page with a drawn corner (lines) and an arrow down: export DXF."""
    from PySide6.QtGui import QPolygonF
    p.setPen(_pen(INK, 3.5))
    p.setBrush(Qt.NoBrush)
    p.drawPolygon(QPolygonF([QPointF(14, 4), QPointF(40, 4), QPointF(50, 14),
                             QPointF(50, 60), QPointF(14, 60)]))
    p.setPen(_pen(ACCENT, 3.5))
    p.drawLine(QPointF(20, 16), QPointF(20, 30))
    p.drawLine(QPointF(20, 30), QPointF(34, 30))
    p.setPen(_pen(ACCENT, 4.5))
    p.drawLine(QPointF(32, 36), QPointF(32, 54))
    p.drawLine(QPointF(25, 47), QPointF(32, 54))
    p.drawLine(QPointF(39, 47), QPointF(32, 54))


def _doc_rooms(p) -> None:
    """A plan cut into rooms, one named (a label line in it)."""
    p.setPen(_pen(INK, 4))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(6, 8, 52, 48))
    p.drawLine(QPointF(32, 8), QPointF(32, 56))
    p.drawLine(QPointF(32, 32), QPointF(58, 32))
    p.setPen(_pen(ACCENT, 4))
    p.drawLine(QPointF(12, 28), QPointF(26, 28))
    p.drawLine(QPointF(14, 36), QPointF(24, 36))


def _doc_open(p) -> None:
    """A sheet with an arrow out of it: open the sheets."""
    _sheet(p)
    p.setPen(_pen(ACCENT, 4))
    p.drawLine(QPointF(14, 38), QPointF(30, 22))
    p.drawLine(QPointF(20, 22), QPointF(30, 22))
    p.drawLine(QPointF(30, 22), QPointF(30, 32))


def _doc_pdf(p) -> None:
    """A page with its corner folded and an arrow down: export a PDF."""
    from PySide6.QtGui import QPolygonF
    p.setPen(_pen(INK, 3.5))
    p.setBrush(Qt.NoBrush)
    p.drawPolygon(QPolygonF([QPointF(14, 4), QPointF(40, 4), QPointF(50, 14),
                             QPointF(50, 60), QPointF(14, 60)]))
    p.setPen(_pen(ACCENT, 4.5))
    p.drawLine(QPointF(32, 20), QPointF(32, 48))
    p.drawLine(QPointF(23, 39), QPointF(32, 48))
    p.drawLine(QPointF(41, 39), QPointF(32, 48))


def _op_door(p) -> None:
    """A door in plan: the wall's two stubs, the leaf open, its swing."""
    p.setPen(_pen(INK, 6))
    p.drawLine(QPointF(4, 48), QPointF(16, 48))
    p.drawLine(QPointF(52, 48), QPointF(60, 48))
    p.setPen(_pen(ACCENT, 4))
    p.drawLine(QPointF(16, 48), QPointF(16, 12))
    p.setPen(_pen(ACCENT, 2.5, dash=True))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(-20, 12, 72, 72), 0 * 16, 90 * 16)


def _op_window(p) -> None:
    """A window in plan: the wall's stubs, the frame, the glass."""
    p.setPen(_pen(INK, 6))
    p.drawLine(QPointF(4, 32), QPointF(14, 32))
    p.drawLine(QPointF(50, 32), QPointF(60, 32))
    p.setPen(_pen(ACCENT, 3))
    p.drawLine(QPointF(14, 24), QPointF(14, 40))
    p.drawLine(QPointF(50, 24), QPointF(50, 40))
    p.drawLine(QPointF(14, 29), QPointF(50, 29))
    p.drawLine(QPointF(14, 35), QPointF(50, 35))


def _op_void(p) -> None:
    """A void: the wall cut, nothing in it (a dashed span)."""
    p.setPen(_pen(INK, 6))
    p.drawLine(QPointF(4, 32), QPointF(16, 32))
    p.drawLine(QPointF(48, 32), QPointF(60, 32))
    p.setPen(_pen(ACCENT, 3, dash=True))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(16, 22, 32, 20))


def _foot_pads(p) -> None:
    """A column standing on a wider pad (section)."""
    p.setPen(Qt.NoPen)
    p.setBrush(INK)
    p.drawRect(QRectF(26, 6, 12, 34))
    p.setBrush(ACCENT)
    p.drawRect(QRectF(10, 40, 44, 14))


def _foot_strips(p) -> None:
    """A wall standing on a strip footing (section)."""
    p.setPen(Qt.NoPen)
    p.setBrush(INK)
    p.drawRect(QRectF(27, 6, 10, 34))
    p.setBrush(ACCENT)
    p.drawRect(QRectF(16, 40, 32, 12))
    p.setPen(_pen(INK, 2.5, dash=True))
    p.drawLine(QPointF(4, 58), QPointF(60, 58))


_CUSTOM = {"survey": _survey, "add_point": _add_point, "fit": _fit,
           "excavate": _excavate, "eye": _eye, "eye_off": _eye_off,
           "edit": _edit, "ramp": _ramp,
           "col_single": _col_single, "col_row": _col_row,
           "col_grid": _col_grid, "col_corners": _col_corners,
           "beam_walls": _beam_walls, "slab_walls": _slab_walls,
           "slab_hole": _slab_hole, "op_door": _op_door,
           "roof_walls": _roof_walls, "doc_sheets": _doc_sheets,
           "doc_open": _doc_open, "doc_pdf": _doc_pdf,
           "doc_rooms": _doc_rooms, "doc_dxf": _doc_dxf, "io": _io,
           "web": _web, "grid_snap": _grid_snap,
           "op_window": _op_window, "op_void": _op_void,
           "foot_pads": _foot_pads, "foot_strips": _foot_strips}
_cache: dict[str, QIcon] = {}


def icon(key: str | None) -> QIcon:
    """The host's icon for ``key`` when it has one, else ours, else none."""
    if not key:
        return QIcon()
    if key in _cache:
        return _cache[key]
    ico = QIcon()
    if key in _CUSTOM:
        pm, p = _canvas()
        _CUSTOM[key](p)
        p.end()
        ico = QIcon(pm)
    else:
        try:
            from views.icons import tool_icon
            ico = tool_icon(key)
        except Exception:  # noqa: BLE001 — a missing icon is not an error
            ico = QIcon()
    _cache[key] = ico
    return ico
