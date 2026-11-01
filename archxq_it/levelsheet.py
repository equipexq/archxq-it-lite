"""The LEVEL'S GUIDE SHEET (PLANO_PAREDE_3D.md part 2B — his idea 31/10,
from ArchXQ for Blender): a see-through plate at a level's floor with a
1 m grid (every 5th line stronger), switched per level by the grid icon of
the levels strip.

It is PAINTED over the 3D view (as the plan's lines are) — never geometry:
not in the model, the undo, the file's groups, the sheets, the quantities,
and never in the snap's way. His rule: THE ICON RULES — off, that level's
sheet never shows (not even while drawing in 3D); on, it shows — only the
LEVEL WORKED ON's (his call, 31/10: on several at once, over the whole
building, it confused) — a little stronger while a tool draws on it, with a
cross at the cursor's point. Only in 3D: the plan has its own grid.

BEHIND what stands on it (his ask, 31/10): with the camera over the floor,
all that is on the floor or above it (this level's walls, columns, stairs,
the levels over it) is IN FRONT of the sheet, all under it behind — so no
depth buffer is needed: the shapes of everything over the floor, seen from
the camera, are cut out of the sheet (``Occluders`` + ``mask``). Their
faces are clipped at the floor and kept until the model or a visibility
changes; the mask until the camera moves too.

``extent`` / ``grid`` / ``step_for`` / ``clip_up`` are pure (tested
without the host).
"""
from __future__ import annotations

import math

MARGIN = 2.0                # m round what the level has
EMPTY = 10.0                # m — a level with nothing on it: a 20 × 20 sheet
FILL = "#2f7df6"            # the brand's blue (the Tools' — his favourite)


def extent(doc: dict, level_id: str):
    """(x0, y0, x1, y1): the plot and what stands on the level, with a
    margin; a bare level: a square round the origin."""
    xs, ys = [], []
    plot = doc.get("plot") or {}
    for p in plot.get("corners") or ():
        xs.append(p[0])
        ys.append(p[1])
    for w in doc.get("walls") or ():
        if w.get("level") != level_id:
            continue
        if w.get("kind") in ("circle",) and w.get("c") is not None:
            r = float(w.get("r", 0.0))
            xs += [w["c"][0] - r, w["c"][0] + r]
            ys += [w["c"][1] - r, w["c"][1] + r]
            continue
        for k in ("a", "b", "m"):
            p = w.get(k)
            if p is not None:
                xs.append(p[0])
                ys.append(p[1])
    for s in doc.get("structure") or ():
        if s.get("level") != level_id:
            continue
        for p in (s.get("corners") or ()) if isinstance(
                s.get("corners"), list) else ():
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                xs.append(p[0])
                ys.append(p[1])
        p = s.get("at")
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            xs.append(p[0])
            ys.append(p[1])
    if not xs:
        return (-EMPTY, -EMPTY, EMPTY, EMPTY)
    return (min(xs) - MARGIN, min(ys) - MARGIN, max(xs) + MARGIN,
            max(ys) + MARGIN)


def grow(ext, pts) -> tuple:
    """The sheet stretched to the points being drawn (and a margin): the
    wall drawn past the plot still lands ON the sheet."""
    x0, y0, x1, y1 = ext
    for p in pts or ():
        if p is None or len(p) < 2:
            continue
        x0, y0 = min(x0, p[0] - MARGIN), min(y0, p[1] - MARGIN)
        x1, y1 = max(x1, p[0] + MARGIN), max(y1, p[1] + MARGIN)
    return (x0, y0, x1, y1)


def step_for(ext) -> float:
    """1 m; 5 m on a sheet over 150 m (a dense grid only greys it)."""
    big = max(ext[2] - ext[0], ext[3] - ext[1])
    return 1.0 if big <= 150 else 5.0


def grid(ext, step: float | None = None) -> list:
    """[((x, y), (x, y), strong)] — the lines on whole metres (the
    world's, not the sheet's corner), every 5th one strong."""
    step = step or step_for(ext)
    x0, y0, x1, y1 = ext
    out = []
    i = math.ceil(x0 / step - 1e-9)
    while i * step <= x1 + 1e-9:
        x = i * step
        out.append(((x, y0), (x, y1), i % 5 == 0))
        i += 1
    j = math.ceil(y0 / step - 1e-9)
    while j * step <= y1 + 1e-9:
        y = j * step
        out.append(((x0, y), (x1, y), j % 5 == 0))
        j += 1
    return out


FLOOR_EPS = 0.005           # m — a face lying on the floor (the slab's top)


def clip_up(pts, z0: float) -> list:
    """The part of a polygon [(x, y, z)…] at or over the height ``z0``."""
    out = []
    k = len(pts)
    for i in range(k):
        a, b = pts[i], pts[(i + 1) % k]
        ina, inb = a[2] >= z0, b[2] >= z0
        if ina:
            out.append(a)
        if ina != inb:
            t = (z0 - a[2]) / (b[2] - a[2])
            out.append((a[0] + (b[0] - a[0]) * t,
                        a[1] + (b[1] - a[1]) * t, z0))
    return out if len(out) >= 3 else []


def over_floor(polys, z0: float) -> list:
    """The faces' parts over the floor — a face on it (the slab's top) or
    under it (the levels below, the slab's sides) is none."""
    out = []
    for vs in polys:
        if not vs or max(p[2] for p in vs) <= z0 + FLOOR_EPS:
            continue
        c = clip_up(vs, z0) if min(p[2] for p in vs) < z0 else list(vs)
        if c:
            out.append(c)
    return out


class Occluders:
    """Everything shown over a floor, as flat arrays (numpy): its faces
    clipped at the floor — made again only when the model, a level's eye,
    a group's visibility or the floor change."""

    def __init__(self) -> None:
        self.key = None
        self.P = None                 # (n, 3) points
        self.starts = self.lens = None

    @staticmethod
    def _groups(viewport):
        from . import compat
        stack = list(viewport.scene.groups)
        while stack:
            g = stack.pop()
            stack.extend(getattr(g, "children", None) or [])
            if compat.shown(viewport, g):
                yield g

    def update(self, viewport, z0: float) -> None:
        import numpy as np
        from . import compat
        gs = list(self._groups(viewport))
        key = (round(z0, 4), getattr(viewport.scene, "content_version", None),
               tuple(id(g) for g in gs),
               tuple(compat.layer_visible(viewport, g.layer or "")
                     for g in gs))
        if key == self.key:
            return
        polys = []
        for g in gs:
            xf = getattr(g, "xform", None)
            for f in g.mesh.faces:
                vs = f.vertices
                if xf is not None:
                    try:
                        vs = [xf.map(v) for v in vs]
                    except Exception:  # noqa: BLE001 — as it is then
                        pass
                polys.append([(v.x(), v.y(), v.z()) for v in vs])
        polys = over_floor(polys, z0)
        self.key = key
        if not polys:
            self.P = None
            return
        self.lens = np.array([len(p) for p in polys])
        self.starts = np.r_[0, np.cumsum(self.lens)[:-1]]
        self.P = np.array([q for p in polys for q in p], dtype=float)


_OCC = Occluders()
_MASK = {"key": None, "img": None}


def mask(viewport, z0: float):
    """A QImage of the view, opaque where something over the floor ``z0``
    is seen — None: nothing is."""
    import numpy as np
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPolygonF
    from . import compat
    _OCC.update(viewport, z0)
    if _OCC.P is None:
        return None
    W, H = viewport.width(), viewport.height()
    dpr = float(viewport.devicePixelRatioF())
    cam = compat.camera_state(viewport)
    key = (_OCC.key, W, H, dpr, cam["target"].x(), cam["target"].y(),
           cam["target"].z(), cam["yaw"], cam["pitch"], cam["distance"],
           cam["perspective"])
    if key == _MASK["key"]:
        return _MASK["img"]
    M = np.asarray(viewport._np_mvp(), dtype=float)
    P, starts = _OCC.P, _OCC.starts
    hom = np.c_[P, np.ones(len(P))] @ M.T
    w = hom[:, 3]
    safe = np.where(np.abs(w) < 1e-9, 1e-9, w)
    sx = (hom[:, 0] / safe + 1) / 2 * W
    sy = (1 - hom[:, 1] / safe) / 2 * H
    nxt = np.arange(len(P)) + 1
    nxt[starts + _OCC.lens - 1] = starts
    area = np.abs(np.add.reduceat(sx * sy[nxt] - sx[nxt] * sy, starts)) / 2
    seen = (np.maximum.reduceat(sx, starts) > 0) \
        & (np.minimum.reduceat(sx, starts) < W) \
        & (np.maximum.reduceat(sy, starts) > 0) \
        & (np.minimum.reduceat(sy, starts) < H) \
        & (np.minimum.reduceat(w, starts) > 0) & (area > 1.0)
    img = QImage(int(W * dpr), int(H * dpr),
                 QImage.Format_ARGB32_Premultiplied)
    img.setDevicePixelRatio(dpr)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0, 255))
    xs, ys = sx.tolist(), sy.tolist()
    lens = _OCC.lens.tolist()
    for i in np.nonzero(seen)[0].tolist():
        s = int(starts[i])
        p.drawPolygon(QPolygonF([QPointF(xs[j], ys[j])
                                 for j in range(s, s + lens[i])]))
    p.end()
    _MASK.update(key=key, img=img)
    return img


def draw_behind(viewport, painter, ext, z: float, strong: bool = False,
                cursor=None) -> None:
    """The sheet BEHIND what stands on it: drawn on a layer of its own, the
    view's shapes over the floor cut out of it, the layer laid on the view.
    The camera under the floor: no sheet (seen from below it means
    nothing)."""
    from PySide6.QtGui import QImage, QPainter
    from . import compat
    W, H = viewport.width(), viewport.height()
    ray = compat.pixel_ray(viewport, W / 2, H / 2)
    if ray is not None and compat.camera_state(viewport)["perspective"] \
            and ray[0][2] <= z:
        return
    dpr = float(viewport.devicePixelRatioF())
    layer = QImage(int(W * dpr), int(H * dpr),
                   QImage.Format_ARGB32_Premultiplied)
    layer.setDevicePixelRatio(dpr)
    layer.fill(0)
    lp = QPainter(layer)
    draw(viewport, lp, ext, z, strong, cursor=None)
    m = mask(viewport, z)
    if m is not None:
        lp.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        lp.drawImage(0, 0, m)
    lp.end()
    painter.drawImage(0, 0, layer)
    if cursor is not None:              # the cursor's cross: always seen
        draw_cross(viewport, painter, cursor, z)


def draw_cross(viewport, painter, cursor, z: float) -> None:
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QPen
    from . import compat
    c = compat.to_pixel(viewport, cursor[0], cursor[1], z)
    if not c:
        return
    painter.save()
    painter.setPen(QPen(QColor(FILL), 2.0))   # (white vanished on grey)
    painter.drawLine(QPointF(c[0] - 9, c[1]), QPointF(c[0] + 9, c[1]))
    painter.drawLine(QPointF(c[0], c[1] - 9), QPointF(c[0], c[1] + 9))
    painter.restore()


def draw(viewport, painter, ext, z: float, strong: bool = False,
         cursor=None) -> None:
    """One sheet over the view: its plate, its grid, its edge — and the
    cursor's cross on it."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QBrush, QColor, QPen, QPolygonF

    from . import compat
    x0, y0, x1, y1 = ext
    px = [compat.to_pixel(viewport, x, y, z)
          for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    base = QColor(FILL)
    if all(px):
        base.setAlpha(46 if strong else 26)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(base))
        painter.drawPolygon(QPolygonF([QPointF(*p) for p in px]))
    thin, bold = QColor(FILL), QColor(FILL)
    thin.setAlpha(70 if strong else 45)
    bold.setAlpha(150 if strong else 95)
    painter.setBrush(Qt.NoBrush)
    for a, b, heavy in grid(ext):
        pa = compat.to_pixel(viewport, a[0], a[1], z)
        pb = compat.to_pixel(viewport, b[0], b[1], z)
        if pa and pb:
            painter.setPen(QPen(bold if heavy else thin, 1.2 if heavy
                                else 0.8))
            painter.drawLine(QPointF(*pa), QPointF(*pb))
    edge = QColor(FILL)
    edge.setAlpha(190 if strong else 120)
    painter.setPen(QPen(edge, 1.6))
    for a, b in zip(px, px[1:] + px[:1]):
        if a and b:
            painter.drawLine(QPointF(*a), QPointF(*b))
    painter.restore()
    if cursor is not None:
        draw_cross(viewport, painter, cursor, z)
