# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The wall window's «Shape» tab (PLANO_CURVAS_E_FORMAS F2.7, 2026-11-13):
the wall seen from the front, its control corners to drag, and the tools —
Round corner, Chamfer, Notch, Bend side, Back to rectangle. The data and
every refusal are wallshape.py's; this only draws and asks.

``add_tab(dlg, wall, level, openings, joined)`` puts the tab in a
WallDialog; ``values(dlg, w)`` writes what it made into the record (OK:
one Ctrl+Z, as the rest of the window). Editing is the Pro's; the Lite
shows the drawing."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QWidget)

from . import look as L
from . import walls as W
from . import wallshape as WS
from .i18n import tr

BLUE = "#2f7df6"            # the Tools mock-up's blue (his choice, 2026-11)
HIT = 8                     # px: a click this close takes a corner / side
SNAP = 6                    # px: a drag this close to a line snaps to it
GRID = 0.01                 # m: no snap: this step
#: the foot's two corners (A, B): never moved, rounded nor cut
FIXED = (0, 1)


def fixed_side(k: int, n: int) -> bool:
    """Side ``k`` of ``n`` touches the foot (the foot itself, end B's, end
    A's): never moved whole — wallshape.move_side refuses it."""
    return k in (0, 1) or (k + 1) % n in FIXED

TOOLS = (("select", "Points"), ("round", "Round corner"),
         ("chamfer", "Chamfer"), ("notch", "Notch"), ("bend", "Bend side"))
#: (the Notch starts SQUARE — 0, as most are: his ask, 23/11/2026; he had
#: to type 0 over the 0.30 every time. A radius: type it, or Round corner)
SIZE_OF = {"round": ("Radius", WS.ROUND_R), "chamfer": ("Size", WS.CHAMFER),
           "notch": ("Corner radius", 0.0),
           "bend": ("Bulge", 0.30)}
TIPS = {"select": "Drag a corner or the middle of a side · Double-click a "
                  "side: a new point · Del: delete the point",
        "round": "Click a corner to round it",
        "chamfer": "Click a corner to cut it off",
        "notch": "Drag a rectangle over an edge of the wall: it is cut away "
                 "(over the top: a «U»; at an end: a «C»)",
        "bend": "Click a side to bend it into an arc (a negative bulge: "
                "outwards)"}


# ---- the drawing ------------------------------------------------------------------------
class ShapeCanvas(QWidget):
    """The wall from the front: s across, z up, its foot at the bottom."""

    def __init__(self, tab) -> None:
        super().__init__()
        self.tab = tab
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.drag = None            # ("corner", i, base) | ("side", …) | …
        self.hover = None

    # -- the mapping --------------------------------------------------------------------
    def _frame(self):
        prof = self.tab.prof
        Lw = prof["L"]
        top = max(WS.peak(prof), self.tab.ref_h) + 0.3
        m = 30.0
        w, h = max(self.width() - 2 * m, 10), max(self.height() - 2 * m, 10)
        k = min(w / max(Lw + 0.6, 0.1), h / top)
        x0 = m + (w - k * Lw) / 2
        y0 = m + h
        return k, x0, y0

    def to_px(self, s: float, z: float) -> QPointF:
        k, x0, y0 = self._frame()
        if self.tab.mirror:              # seen from the other face: B left
            s = self.tab.prof["L"] - s
        return QPointF(x0 + s * k, y0 - z * k)

    def to_sz(self, pt) -> tuple:
        k, x0, y0 = self._frame()
        s = (pt.x() - x0) / k
        if self.tab.mirror:
            s = self.tab.prof["L"] - s
        return (s, (y0 - pt.y()) / k)

    # -- what is under the mouse ------------------------------------------------------------
    def corner_at(self, pt) -> int | None:
        best = None
        for i, (s, z) in enumerate(self.tab.prof["ctrl"]):
            d = math.dist((pt.x(), pt.y()), (self.to_px(s, z).x(),
                                              self.to_px(s, z).y()))
            if d <= HIT and (best is None or d < best[0]):
                best = (d, i)
        return None if best is None else best[1]

    def side_at(self, pt, mid_only: bool = False) -> int | None:
        ctrl = self.tab.prof["ctrl"]
        n = len(ctrl)
        best = None
        for i in range(n):
            a = self.to_px(*ctrl[i])
            b = self.to_px(*ctrl[(i + 1) % n])
            if mid_only:
                m = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
                d = math.dist((pt.x(), pt.y()), (m.x(), m.y()))
            else:
                dx, dy = b.x() - a.x(), b.y() - a.y()
                LL = dx * dx + dy * dy or 1.0
                t = min(max(((pt.x() - a.x()) * dx + (pt.y() - a.y()) * dy)
                            / LL, 0.0), 1.0)
                d = math.dist((pt.x(), pt.y()),
                              (a.x() + dx * t, a.y() + dy * t))
            if d <= HIT and (best is None or d < best[0]):
                best = (d, i)
        return None if best is None else best[1]

    def snapped(self, s: float, z: float, skip=()) -> tuple:
        """(s, z) on the nearest corner's s / z, a floor, an opening's sill
        or head within SNAP px — else on the 1 cm step."""
        k, _x0, _y0 = self._frame()
        tol = SNAP / max(k, 1e-6)
        ss = [p[0] for i, p in enumerate(self.tab.prof["ctrl"])
              if i not in skip] + [0.0, self.tab.prof["L"]]
        zs = [p[1] for i, p in enumerate(self.tab.prof["ctrl"])
              if i not in skip] + self.tab.lines
        out = []
        for v, cand in ((s, ss), (z, zs)):
            near = min(cand, key=lambda c: abs(c - v), default=None)
            out.append(near if near is not None and abs(near - v) <= tol
                       else round(v / GRID) * GRID)
        return out[0], out[1]

    # -- painting --------------------------------------------------------------------------
    def paintEvent(self, _e) -> None:  # noqa: N802 — Qt's
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), L.colour(L.FIELD))
        prof = self.tab.prof
        Lw = prof["L"]
        # the floor, the slab over the level, the joined walls' tops
        for z, dash in [(0.0, False)] + [(z, True) for z in self.tab.lines
                                          if z not in self.tab.match]:
            a, b = self.to_px(-0.3, z), self.to_px(Lw + 0.3, z)
            p.setPen(L.pen(L.DIM, 1.0, dash))
            p.drawLine(a, b)
        # the joined walls' cuts: blue, their height written at the left
        for z in self.tab.match:
            a, b = self.to_px(-0.3, z), self.to_px(Lw + 0.3, z)
            if a.x() > b.x():
                a, b = b, a
            # (on a whole pixel: between two, the antialiasing halved it —
            # 1.10 came out grey beside a blue 2.40)
            y = round(a.y()) + 0.5
            a, b = QPointF(a.x(), y), QPointF(b.x(), y)
            p.setPen(L.pen(BLUE, 1.0, True))
            p.drawLine(a, b)
            L.text(p, a.x(), a.y() - 3, f"{z:.2f}", BLUE)
        # the wall
        pts, _arcs = WS.outline(prof, 0.0)
        path = QPainterPath()
        for j, (s, z) in enumerate(pts):
            q = self.to_px(s, z)
            path.moveTo(q) if j == 0 else path.lineTo(q)
        path.closeSubpath()
        p.setPen(QPen(L.colour(L.INK), 1.6))
        p.setBrush(QBrush(QColor(47, 125, 246, 40)))
        p.drawPath(path)
        # its openings (light grey)
        p.setBrush(QBrush(QColor(200, 204, 210, 70)))
        p.setPen(L.pen(L.MUTED, 1.0))
        for o in self.tab.openings:
            zs = float(o.get("sill", 0.0)) + self.tab.lift
            half = float(o["w"]) / 2
            a = self.to_px(float(o["pos"]) - half, zs + float(o["h"]))
            b = self.to_px(float(o["pos"]) + half, zs)
            p.drawRect(QRectF(a, b).normalized())
        # A and B
        for s, label in ((0.0, "A"), (Lw, "B")):
            q = self.to_px(s, 0.0)
            L.text(p, q.x() - 4, q.y() + 16, label, L.MUTED)
        if not self.tab.editable:
            p.end()
            return
        # the control corners (squares) and the sides' middles (diamonds).
        # The FOOT's two corners, A and B, never move (the foot stays
        # whole — its length is the plan's): drawn small and grey, never
        # lit — they looked like the others and he tried to drag them (his
        # screen, 18/11/2026)
        ctrl = prof["ctrl"]
        n = len(ctrl)
        sel = self.tab.sel
        for i, (s, z) in enumerate(ctrl):
            q = self.to_px(s, z)
            if i in FIXED:
                p.setPen(QPen(L.colour(L.DIM), 1.0))
                p.setBrush(QBrush(L.colour(L.DIM)))
                p.drawRect(QRectF(q.x() - 3, q.y() - 3, 6, 6))
                continue
            hot = i == sel or self.hover == ("corner", i)
            p.setPen(QPen(QColor(BLUE), 1.4))
            p.setBrush(QBrush(QColor(BLUE) if hot else L.colour(L.FIELD)))
            p.drawRect(QRectF(q.x() - 4, q.y() - 4, 8, 8))
        if self.tab.tool in ("select", "bend"):
            # (the sides from the foot's corners — end A's, as end B's — are
            # never moved whole: no diamond on them)
            for i in range(2, n - 1):
                a, b = self.to_px(*ctrl[i]), self.to_px(*ctrl[(i + 1) % n])
                m = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
                hot = self.hover == ("side", i)
                d = QPainterPath()
                d.moveTo(m.x(), m.y() - 5)
                d.lineTo(m.x() + 5, m.y())
                d.lineTo(m.x(), m.y() + 5)
                d.lineTo(m.x() - 5, m.y())
                d.closeSubpath()
                p.setPen(QPen(QColor(BLUE), 1.2))
                p.setBrush(QBrush(QColor(BLUE) if hot else L.colour(L.FIELD)))
                p.drawPath(d)
        if self.drag and self.drag[0] == "notch" and self.drag[2] is not None:
            a, b = self.to_px(*self.drag[1]), self.to_px(*self.drag[2])
            p.setPen(L.pen(L.ORANGE, 1.4, True))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(a, b).normalized())
        if sel is not None and 0 <= sel < n:
            s, z = ctrl[sel]
            q = self.to_px(s, z)
            L.text(p, q.x() + 8, q.y() - 8, f"{s:.2f} · {z:.2f}", BLUE)
        p.end()

    # -- the mouse ---------------------------------------------------------------------------
    def mousePressEvent(self, e) -> None:  # noqa: N802
        if not self.tab.editable or e.button() != Qt.LeftButton:
            return
        pt = e.position()
        tool = self.tab.tool
        i = self.corner_at(pt)
        if tool == "notch" and (i is None or i in FIXED):
            self.drag = ("notch", self.to_sz(pt), None)
            return
        if tool == "notch":
            # a POINT taken with the Notch on: it moves, as with «Points»
            # (his cut, 20/11/2026: the inner corners of a C could not be
            # moved — the press began another notch, «No such point»)
            self.tab.select(i)
            self.drag = ("corner", i, self.tab.prof)
            return
        if tool in ("round", "chamfer"):
            if i is not None:
                v = self.tab.size_value()
                fn = WS.round_corner if tool == "round" else WS.chamfer
                self.tab.attempt(fn(self.tab.prof, i, v))
            return
        if tool == "bend":
            k = self.side_at(pt)
            if k is not None:
                self.tab.attempt(WS.bend_side(self.tab.prof, k,
                                              self.tab.size_value()))
            return
        if i is not None and i in FIXED:     # A / B: says why, at once
            self.tab.say(tr(WS.WHY_FOOT), bad=True)
            return
        if i is not None:
            self.tab.select(i)
            self.drag = ("corner", i, self.tab.prof)
            return
        k = self.side_at(pt, mid_only=True)
        if k is not None and fixed_side(k, len(self.tab.prof["ctrl"])):
            self.tab.say(tr(WS.WHY_FOOT), bad=True)
            return
        if k is not None:
            self.drag = ("side", k, self.tab.prof, self.to_sz(pt))
            return
        self.tab.select(None)

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        pt = e.position()
        if self.drag is None:
            i = self.corner_at(pt)
            k = None if i is not None else self.side_at(pt, mid_only=True)
            n = len(self.tab.prof["ctrl"])
            hv = (("corner", i) if i not in FIXED else None) \
                if i is not None else \
                (("side", k) if k is not None and not fixed_side(k, n)
                 else None)
            if hv != self.hover:
                self.hover = hv
                self.update()
            return
        if not (e.buttons() & Qt.LeftButton):
            # the button was let go and its release never came here (his
            # Notch, 20/11/2026: the rectangle went on following the pen,
            # nothing cut, nothing said) — finished now, as a release
            self.mouseReleaseEvent(e)
            return
        kind = self.drag[0]
        if kind == "corner":
            _k, i, base = self.drag
            s, z = self.snapped(*self.to_sz(pt), skip=(i,))
            self.tab.attempt(WS.move_point(base, i, s, z), live=True)
        elif kind == "side":
            _k, i, base, start = self.drag
            ctrl = base["ctrl"]
            a, b = ctrl[i], ctrl[(i + 1) % len(ctrl)]
            Ls = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
            nx, nz = -(b[1] - a[1]) / Ls, (b[0] - a[0]) / Ls
            s, z = self.to_sz(pt)
            d = round(((s - start[0]) * nx + (z - start[1]) * nz) / GRID) \
                * GRID
            self.tab.attempt(WS.move_side(base, i, d), live=True)
        elif kind == "notch":
            self.drag = ("notch", self.drag[1], self.snapped(*self.to_sz(pt)))
            self.update()

    def mouseReleaseEvent(self, _e) -> None:  # noqa: N802
        d, self.drag = self.drag, None
        if d and d[0] == "notch" and d[2] is not None:
            (s0, z0), (s1, z1) = self.snapped(*d[1]), d[2]
            self.tab.attempt(WS.notch(self.tab.prof, s0, z0, s1, z1,
                                      self.tab.size_value()))
        self.update()

    def mouseDoubleClickEvent(self, e) -> None:  # noqa: N802
        if not self.tab.editable or self.tab.tool != "select":
            return
        k = self.side_at(e.position())
        if k is not None:
            self.tab.attempt(WS.add_point(self.tab.prof, k,
                                          self.to_sz(e.position())))

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if self.tab.editable and e.key() in (Qt.Key_Delete,
                                             Qt.Key_Backspace) \
                and self.tab.sel is not None:
            got = WS.delete_point(self.tab.prof, self.tab.sel)
            if got[0] is not None:
                self.tab.select(None)
            self.tab.attempt(got)
            return
        super().keyPressEvent(e)


# ---- the tab ----------------------------------------------------------------------------
def seen_mirrored(wall: dict, eye=None) -> bool:
    """The wall drawn with B on the LEFT: the face it is seen from is the
    one on the LEFT of a → b (looking at it from there, A is on the right).
    That face is where the 3D camera stands (``eye`` = its (x, y), given
    when the window opens out of the plan) — else the OUTSIDE face (its
    inside is ``side``: +1 left, −1 right). His wall 57, 21/11/2026: a «C»
    cut at end B, the 3D seen from outside — the editor drew it from the
    inside, the cut looked the wrong way round."""
    try:
        (ax, ay), (bx, by) = wall["a"][:2], wall["b"][:2]
    except (KeyError, TypeError, ValueError):
        return False
    L = math.hypot(bx - ax, by - ay)
    if eye is not None and L > 1e-9:
        ex, ey = float(eye[0]), float(eye[1])
        cross = ((bx - ax) * (ey - ay) - (by - ay) * (ex - ax)) / L
        if abs(cross) > 0.05:            # (on its line: no side to tell)
            return cross > 0
    return float(wall.get("side", 1) or 1) < 0


class ShapeTab:
    """The tab's state: the shape being made (``prof``), the tool, the
    corner selected; whether it changed; whether it is back to a
    rectangle."""

    def __init__(self, wall: dict, level: dict, openings, joined) -> None:
        from . import edition
        from . import structure as S
        self.wall = wall
        self.openings = list(openings or ())
        self.joined = set(joined or ())
        self.lift = W.opening_lift(wall) - float(wall.get("base", 0.0) or 0.0)
        under = float(level.get("_under", level.get("height", 3.0)))
        self.ref_h = under
        self.lines = [under - float(wall.get("base", 0.0) or 0.0)]
        # the cuts of the walls joined to it (WS.match_heights): lines to
        # snap to, their height written — his L balcony, 23/11/2026
        self.match = [h for h in level.get("_match") or ()
                      if all(abs(h - k) > 1e-3 for k in self.lines)]
        self.lines += self.match
        # the «C» of the wall joined at a corner (WS.joined_cut): the ready
        # «C» opens there, as high — None: as it ever was
        self.cut = level.get("_cut")
        self.why_kind = WS.why_no_shape(wall)
        self.editable = self.why_kind is None and not edition.lite()
        prof = S.shape_now(wall) if self.why_kind is None else None
        if prof is None and self.why_kind is None:
            src = wall if wall.get("height", "level") != "level" else \
                dict(wall, height=under)
            prof = WS.from_top(src)
            if prof is not None and wall.get("height", "level") == "level" \
                    and W.top_of(wall) is None:
                prof["was"] = "level"
        if prof is None:                # (a curved wall…: a box to show)
            Lw = max(W.drawn(wall).L, 0.1)
            prof = {"ctrl": [[0, 0], [Lw, 0], [Lw, under], [0, under]],
                    "curves": {"r": {}, "arc": {}}, "L": round(Lw, 4),
                    "was": "level"}
        self.prof = prof
        self.tool = "select"
        self.sel = None
        self.changed = False
        self.rect = False               # «Back to rectangle» pressed
        self.canvas = None
        self.status = None
        self.size = None
        self.size_label = None
        self.f_s = self.f_z = None
        self.on_change = None           # the window's numbers, kept in step
        self.mirror = seen_mirrored(wall, level.get("_eye"))

    # -- checks beyond the shape's own ---------------------------------------------------------
    def _context_why(self, prof: dict) -> str | None:
        from . import structure as S
        if WS.top_only(self.wall):      # a grid / clad / framed wall:
            why = WS.why_not_top(prof)   # its top only (phase 3)
            if why:
                return why
        w = dict(self.wall, profile=prof)
        for o in self.openings:
            if S.opening_room(o, w, self.openings, 3.0) is not None:
                return tr("\"{name}\" would stand outside the wall's shape",
                          name=o.get("name", "Opening"))
        for end, s in (("a", 0.0), ("b", prof["L"])):
            if end in self.joined:
                # (a «C» cut there is fine: the corner stands whole —
                # profilecut._base; its foot must be whole all the same)
                sl = WS.slice_at(prof, s)
                if not sl or sl[0][0] > 1e-6:
                    return tr("That end is joined to another wall — keep it "
                              "whole up to one height there")
        return None

    def attempt(self, got, live: bool = False) -> None:
        prof, why = got
        if prof is not None:
            why = self._context_why(prof)
        if why:
            self.say(tr(why), bad=True)
            return
        self.prof = prof
        self.changed = True
        self.rect = False
        self.say("")
        self._fields()
        self.canvas.update()
        self._told()

    def _told(self) -> None:
        if self.on_change is not None:
            try:
                self.on_change()
            except Exception:  # noqa: BLE001 — the numbers only
                pass

    def say(self, text: str, bad: bool = False) -> None:
        if self.status is not None:
            self.status.setText(text or tr(TIPS[self.tool]))
            self.status.setStyleSheet(f"color: {L.ORANGE if bad else L.MUTED};")

    def select(self, i) -> None:
        self.sel = i if i is not None and i >= 2 else None
        self._fields()
        self.canvas.update()

    def size_value(self) -> float:
        return float(self.size.value()) if self.size is not None else 0.3

    def set_tool(self, tool: str) -> None:
        self.tool = tool
        lab, v = SIZE_OF.get(tool, ("", 0.0))
        on = tool in SIZE_OF
        self.size.setVisible(on)
        self.size_label.setVisible(on)
        if on:
            self.size_label.setText(tr(lab))
            self.size.setValue(v)
        self.say("")
        self.canvas.update()

    def _fields(self) -> None:
        on = self.sel is not None
        for f in (self.f_s, self.f_z):
            f.setEnabled(on and self.editable)
        if on:
            s, z = self.prof["ctrl"][self.sel]
            for f, v in ((self.f_s, s), (self.f_z, z)):
                f.blockSignals(True)
                f.setValue(v)
                f.blockSignals(False)

    def typed(self, *_a) -> None:
        if self.sel is None:
            return
        s, z = self.f_s.value(), self.f_z.value()
        Lw = float(self.prof["L"])
        # a millimetre from an end: ON the end (5.457 typed on a 5.4572 m
        # wall slid the point 0.2 mm off a joined end — refused)
        if abs(s) <= 1e-3:
            s = 0.0
        elif abs(s - Lw) <= 1e-3:
            s = Lw
        # (refused: the reason is said under the drawing; the fields keep
        # what was typed — the other one may make it fit, a point moved
        # on a slant)
        self.attempt(WS.move_point(self.prof, self.sel, s, z))

    def ready(self, kind: str) -> None:
        """A ready shape (a card): over this wall's length, at its height
        now (a shape's: its foot's straight sides' height)."""
        h = self.ref_h - float(self.wall.get("base", 0.0) or 0.0)
        sl = WS.slice_at(self.prof, 0.0)
        if sl:
            h = sl[-1][1]
        got = WS.preset(kind, self.prof["L"], h,
                        cut=self.cut if kind == "c" else None)
        if got[0] is not None:
            got = (dict(got[0], was=self.prof.get("was", "level")), None)
        self.sel = None
        self.attempt(got)

    def flip(self) -> None:
        """«Mirror»: the shape end for end (WS.mirrored) — refused, as any
        edit, when it wouldn't hold its openings or a joined end."""
        self.sel = None
        self.attempt(WS.mirrored(self.prof))

    def to_rect(self) -> None:
        was = WS.to_rect(self.prof)
        h = self.ref_h if was == "level" else float(was) - float(
            self.wall.get("base", 0.0) or 0.0)
        Lw = self.prof["L"]
        self.prof = {"ctrl": [[0, 0], [Lw, 0], [Lw, h], [0, h]],
                     "curves": {"r": {}, "arc": {}}, "L": Lw, "was": was}
        self.rect = True
        self.changed = True
        self.sel = None
        self._fields()
        self.say("")
        self.canvas.update()
        self._told()


from PySide6.QtCore import QSize  # noqa: E402

_ICON = QSize(40, 26)


def _preset_icon(kind: str):
    """A ready shape's little drawing (its outline over a 6 × 3 m wall)."""
    from PySide6.QtGui import QIcon, QPixmap
    pm = QPixmap(_ICON.width() * 2, _ICON.height() * 2)
    pm.fill(Qt.transparent)
    prof, _why = WS.preset(kind, 6.0, 3.0)
    if prof is not None:
        pts, _arcs = WS.outline(prof, 0.0)
        zmax = max(z for _s, z in pts)
        k = min((pm.width() - 8) / 6.0, (pm.height() - 8) / max(zmax, 1e-6))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        L.poly(p, [(4 + s * k, pm.height() - 4 - z * k) for s, z in pts],
               L.INK, 2.0, close=True, fill="#8a8f9655")
        p.end()
    return QIcon(pm)


def add_tab(dlg, wall: dict, level: dict, openings=(), joined=()) -> None:
    """The «Shape» tab on a straight wall's window (``dlg.shape``)."""
    st = ShapeTab(wall, level, openings, joined)
    dlg.shape = st
    st.on_change = getattr(dlg, "_refresh", None)
    pg, lay = L.page()
    fold = L.Fold("Shape seen from the front", "wall.shape")
    fl = fold.form()
    st.canvas = ShapeCanvas(st)
    lay.addWidget(fold)
    fl.addRow(st.canvas)
    if st.why_kind:
        fl.addRow(L.hint(tr(st.why_kind)))
    elif not st.editable:
        fl.addRow(L.hint(tr("Editing the shape is in ArchXQ IT Pro")))
    if st.editable:
        # (3 a row, as the column's and the beam's Shape tabs: in one row
        # the tools and the ready cards made the tab 816 px wide — cut on
        # the right, the drawing pushed right, «Arched top» and «C» out of
        # sight; his screen, 23/11/2026)
        tools = L.Chips(wrap=3, width=120)       # («Arredondar canto» whole)
        for v, text in TOOLS:
            tools.addItem(text, v)
        tools.setCurrentIndex(0)
        tools.lay.setColumnStretch(3, 1)         # (packed to the left)
        # (their names over them, not beside: the labels' column took the
        # width the cards need — «Ferra…» cut, 23/11/2026)
        fl.addRow(QLabel(tr("Tool")))
        fl.addRow(tools)
        # READY SHAPES (phase 3): a card each, a click puts it on
        cards = QWidget()
        cl = QGridLayout(cards)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(6)
        top_only = WS.top_only(wall)
        for n, (key, text) in enumerate(WS.PRESETS):
            b = QPushButton(tr(text))
            b.setObjectName("axqChip")
            b.setIcon(_preset_icon(key))
            b.setIconSize(_ICON)
            if key == "c" and top_only:
                b.setEnabled(False)
                b.setToolTip(tr(WS.WHY_TOP_ONLY))
            else:
                b.setToolTip(tr("Puts this shape on the wall, over its "
                                "length and at its height — then drag "
                                "and type as any shape"))
            b.clicked.connect(lambda _c=False, k=key: st.ready(k))
            cl.addWidget(b, n // 3, n % 3)
        cl.setColumnStretch(3, 1)
        fl.addRow(QLabel(tr("Ready")))
        fl.addRow(cards)
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        st.size_label = QLabel("")
        st.size = L.metres(0.30, -5.0, 10.0, 0.05)
        rl.addWidget(st.size_label)
        rl.addWidget(st.size, 1)
        # their bars over THIS wall: along its length, up to twice its top
        # (0…1000 m made the bar useless — a pixel was metres)
        Lw = float(st.prof["L"])
        st.f_s = L.metres(0.0, 0.0, max(Lw, 0.01), 0.01)
        st.f_z = L.metres(0.0, 0.0, max(10.0, round(
            2.0 * WS.peak(st.prof), 2)), 0.01)
        for f in (st.f_s, st.f_z):
            f.setToolTip(tr("Click a point of the shape, then type where "
                            "it goes"))
        rl.addWidget(QLabel(tr("Point along")))
        rl.addWidget(st.f_s, 1)
        rl.addWidget(QLabel(tr("up")))
        rl.addWidget(st.f_z, 1)
        fl.addRow(row)
        back = QPushButton(tr("Back to rectangle"))
        back.setObjectName("axqChip")
        back.setToolTip(tr("Its shape goes: a plain wall at the height it "
                           "had before"))
        back.clicked.connect(st.to_rect)
        # «Mirror», beside it (his L balcony, 23/11/2026: the «C» opened
        # one way only — any shape now turns end for end, in one click)
        flip = QPushButton(tr("Mirror"))
        flip.setObjectName("axqChip")
        flip.setToolTip(tr("Turns the shape end for end: what is at end A "
                           "goes to end B — a «C» opens the other way"))
        flip.clicked.connect(st.flip)
        ends = QWidget()
        el = QHBoxLayout(ends)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(6)
        el.addWidget(flip, 1)
        el.addWidget(back, 1)
        fl.addRow(ends)
        tools.currentIndexChanged.connect(
            lambda _i: st.set_tool(tools.currentData()))
        st.f_s.valueChanged.connect(st.typed)
        st.f_z.valueChanged.connect(st.typed)
        st.set_tool("select")
        st._fields()
    st.status = L.hint("")
    fl.addRow(st.status)
    st.say("")
    lay.addStretch(1)
    dlg.shape_tab = dlg.tabs.addTab(pg, "Shape", "geometry")


def values(dlg, w: dict) -> None:
    """The record ``w`` with what the tab made (nothing when it wasn't
    touched): a shape — its top gone, its height its peak — or back to a
    plain wall at the height it had."""
    st = getattr(dlg, "shape", None)
    if st is None or not st.changed or not st.editable:
        return
    base = float(w.get("base", 0.0) or 0.0)
    if st.rect:                         # «Back to rectangle»
        w.pop("profile", None)
        w.pop("top", None)
        was = st.prof.get("was", "level")
        w["height"] = was
        return
    h = WS.is_rect(st.prof)
    if h is not None:                   # just a rectangle: a plain wall
        w.pop("profile", None)
        w.pop("top", None)
        w["height"] = round(base + h, 4)
        return
    w["profile"] = WS.clean(st.prof) or st.prof
    w.pop("top", None)
    w["height"] = round(max(base + WS.peak(st.prof), 0.05), 4)
