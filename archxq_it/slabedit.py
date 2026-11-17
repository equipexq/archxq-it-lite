# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Structure › Edit slabs — a drawn slab's outline with the mouse (his ask,
2026-10-12, before recording: the floors' corners and SIDES, as the plot's
and the walls' are edited).

The excavations' tool (``plotedit.DigEditTool``) over the current level's
drawn slabs — Move points / Add point / Delete point, the one under the
cursor taken — and one more mode, «Move side»: click a side, it moves
PARALLEL to itself (its two corners together) as the cursor goes, the
host's snap and alignments helping; click where it goes, or type a
distance + Enter. Esc puts it back. One Ctrl+Z per change.

ARCS and ROUNDED CORNERS (PLANO_CURVAS_E_FORMAS F1, promised to a customer
2026-11-13; ``curved.py``): a slab with curves is edited on its CLICKED
corners (``ctrl``), its curves following them; two more modes —
«Round corner»: click a corner, the arc's middle follows the cursor along
the corner's bisector; click, or type the radius + Enter (0 = sharp again).
«Bend side»: click a side, its middle follows the cursor; click, or type
the radius + Enter (0 = straight again).

An excavation's slab follows its excavation: not edited here.
"""
from __future__ import annotations

import math

from . import compat
from . import curved as CV
from .plotedit import ACTIVE, DigEditTool, RED

#: the left strip's methods → the tool's mode
SLAB_EDIT = {"Move points": "move", "Move side": "side",
             "Add point": "add", "Delete point": "delete",
             "Round corner": "round", "Bend side": "bend"}


class SlabEditTool(DigEditTool):
    name = "ArchXQ edit slab"

    def __init__(self, mode: str, get_slabs, on_change, on_cancelled,
                 check) -> None:
        self.side_mode = mode == "side"
        self.curve_mode = mode if mode in ("round", "bend") else None
        self.side = None          # (k, grab point, normal, corners as taken)
        self.dside = 0.0
        self.bend = None          # (k, corners, curves) — a corner / a side
        self.bend_v = None        # the radius (round) / the sagitta (bend)
        self.bend_raw = None      # the round's radius before it is held in
        #: the curves a round / bend leaves — read by the change (ui.py)
        self.curves_out = None
        # «Move side» and «Bend side» find a side as «Add point» does;
        # «Round corner» a corner, as «Move points»
        base = {"side": "add", "bend": "add", "round": "move"}.get(mode, mode)
        super().__init__(base, get_slabs, on_change, on_cancelled, 0.0, check)
        if self.side_mode:
            self.icon = "move"
        elif self.curve_mode:
            self.icon = "round_corner" if mode == "round" else "bend_side"

    def _reset(self) -> None:
        self.side = None
        self.dside = 0.0
        self.bend = None
        self.bend_v = None
        self.bend_raw = None
        super()._reset()

    def _curves(self) -> dict:
        st = self.get_digs().get(self.target) if self.target else None
        return CV.clean((st or {}).get("curves"))

    # -- «Move side» ---------------------------------------------------------------
    def _side_pts(self, d: float):
        k, _o, n, pts0 = self.side
        pts = [list(q) for q in pts0]
        m = len(pts)
        for i in (k, (k + 1) % m):
            pts[i] = [round(pts[i][0] + n[0] * d, 4),
                      round(pts[i][1] + n[1] * d, 4)]
        return pts

    def _side_place(self, d: float) -> None:
        pts = self._side_pts(d)
        why = self.check(pts)
        if why:
            compat.flash(self.viewport, f"{why} — pick another place", 4000)
            return
        _p, hs, cl, br = self.pending
        self._reset()
        self.on_change(pts, hs, cl, br)
        self._show_hint()

    # -- «Round corner» / «Bend side» ------------------------------------------------
    def _bend_curves(self, v):
        """The curves with this corner's radius / this side's sagitta."""
        k, _pts, cv = self.bend
        out = CV.clean(cv)
        part = "r" if self.curve_mode == "round" else "arc"
        out[part].pop(str(k), None)
        if v and abs(v) > 1e-6:
            out[part][str(k)] = round(float(v), 4)
        return out

    def _bend_from(self, p) -> None:
        """The cursor's point → the radius / the sagitta, live."""
        k, pts, cv = self.bend
        n = len(pts)
        if self.curve_mode == "round":
            prev, c, nxt = pts[k - 1], pts[k], pts[(k + 1) % n]
            u1 = CV._unit(prev[0] - c[0], prev[1] - c[1])
            u2 = CV._unit(nxt[0] - c[0], nxt[1] - c[1])
            b = CV._unit(u1[0] + u2[0], u1[1] + u2[1])
            d = max(0.0, (p[0] - c[0]) * b[0] + (p[1] - c[1]) * b[1])
            r = CV.radius_through(prev, c, nxt, d)
            self.bend_raw = r
            self.bend_v = round(min(r, CV.max_radius(pts, cv, k)), 3)
        else:
            a, b = pts[k], pts[(k + 1) % n]
            L = math.dist(a, b) or 1.0
            nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L     # the left
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            h = (p[0] - mx) * nx + (p[1] - my) * ny
            self.bend_v = round(max(-L, min(L, h)), 3)

    def _bend_why(self, cv) -> str | None:
        _k, pts, _cv = self.bend
        why = CV.why_not(pts, cv)
        if why:
            return why
        try:
            from shapely.geometry import Polygon
            poly = Polygon(CV.expand(pts, cv))
            if not poly.is_valid:
                return "The sides would cross"
        except ImportError:
            pass
        return None

    def _bend_place(self, v) -> None:
        cv = self._bend_curves(v)
        why = self._bend_why(cv)
        if why:
            if self.curve_mode == "round" and why.startswith("The radius"):
                k, pts, cv0 = self.bend
                why += (" — " + compat.fmt_len(CV.max_radius(pts, cv0, k))
                        + " at most here")
            compat.flash(self.viewport, f"{why} — try another", 5000)
            return
        _k, pts, _cv = self.bend
        st = self.pending
        self._reset()
        self.curves_out = cv
        try:
            self.on_change([list(q) for q in pts], st[1], st[2], st[3])
        finally:
            self.curves_out = None
        what = ("Corner" if self.curve_mode == "round" else "Side")
        compat.flash(self.viewport, f"{what} done — Ctrl+Z puts it back", 3000)
        self._show_hint()

    def _bend_click(self, ctx) -> None:
        self.mouse = (ctx.screen.x(), ctx.screen.y())
        here = [round(ctx.world.x(), 4), round(ctx.world.y(), 4)]
        if self.bend is not None:
            self._bend_from(here)
            if self.curve_mode == "round" and self.bend_raw is not None \
                    and self.bend_raw > self.bend_v + 1e-3:
                self._bend_place(self.bend_raw)      # said why, kept going
                return
            self._bend_place(self.bend_v)
            return
        self.hover = here
        self._find()
        st = self._state()
        if st is None:
            return
        if self.curve_mode == "round":
            if self.hot_corner is None:
                return
            k = self.hot_corner
        else:
            if self.hot_side is None:
                return
            k = self.hot_side[0]
        pts = [list(q) for q in st[0]]
        cv = self._curves()
        if self.curve_mode == "round" and (CV._key(cv["arc"], k - 1)
                                           or CV._key(cv["arc"], k)):
            compat.flash(self.viewport, "A rounded corner needs two straight "
                         "sides — straighten the arc first (Bend side, 0)",
                         5000)
            return
        self.bend = (k, pts, cv)
        self.pending = tuple(st)
        self.bend_v = CV._key(cv["r" if self.curve_mode == "round"
                                 else "arc"], k) or 0.0
        self.hot_corner = self.hot_side = None
        self._bend_from(here)
        self._show_hint()
        self.viewport.update()

    # -- host protocol ----------------------------------------------------------------
    def on_hover(self, ctx) -> None:
        if self.curve_mode and self.bend is not None:
            self.mouse = (ctx.screen.x(), ctx.screen.y())
            self.hover = [round(ctx.world.x(), 4), round(ctx.world.y(), 4)]
            self._bend_from(self.hover)
            self._show_hint()
            self.viewport.update()
            return
        if not (self.side_mode and self.side is not None):
            super().on_hover(ctx)
            return
        self.mouse = (ctx.screen.x(), ctx.screen.y())
        p = self._pick(ctx)
        self.hover = p
        _k, o, n, _pts0 = self.side
        self.dside = (p[0] - o[0]) * n[0] + (p[1] - o[1]) * n[1]
        _p, hs, cl, br = self.pending
        self.pending = (self._side_pts(self.dside), hs, cl, br)
        self._show_hint()
        self.viewport.update()

    def on_click(self, ctx) -> None:
        if self.curve_mode:
            self._bend_click(ctx)
            return
        if not self.side_mode:
            super().on_click(ctx)
            return
        self.mouse = (ctx.screen.x(), ctx.screen.y())
        if self.side is not None:
            self.on_hover(ctx)
            self._side_place(self.dside)
            return
        self.hover = [round(ctx.world.x(), 4), round(ctx.world.y(), 4)]
        self._find()
        st = self._state()
        if st is None or self.hot_side is None:
            return
        k, p = self.hot_side
        pts = [list(q) for q in st[0]]
        a, b = pts[k], pts[(k + 1) % len(pts)]
        L = math.dist(a, b) or 1.0
        n = (-(b[1] - a[1]) / L, (b[0] - a[0]) / L)
        self.side = (k, list(p), n, pts)
        self.origin = list(p)
        self.pending = tuple(st)
        self.hot_side = None
        self._show_hint()
        self.viewport.update()

    def on_value(self, viewport, value) -> bool:
        if self.curve_mode and self.bend is not None \
                and isinstance(value, (int, float)):
            R = abs(float(value))
            if self.curve_mode == "round" or R < 1e-6:
                self._bend_place(R)
                return True
            k, pts, _cv = self.bend
            a, b = pts[k], pts[(k + 1) % len(pts)]
            h = CV.sagitta_for_radius(a, b, R, self.bend_v or 1.0)
            if h is None:
                compat.flash(viewport, "An arc on this side needs a radius of "
                             + compat.fmt_len(math.dist(a, b) / 2)
                             + " at least", 5000)
                return True
            self._bend_place(h)
            return True
        if self.side_mode and self.side is not None \
                and isinstance(value, (int, float)):
            sign = -1.0 if self.dside < 0 else 1.0
            self._side_place(sign * abs(float(value)))
            return True
        return super().on_value(viewport, value)

    def on_cancel(self, viewport) -> None:
        if self.side is not None or self.bend is not None:
            self._reset()
            self._show_hint()
            viewport.update()
            return
        super().on_cancel(viewport)

    def value_label(self):
        if self.bend is not None and self.bend_v is not None:
            if self.curve_mode == "round":
                return ("R " + compat.fmt_len(self.bend_v), None)
            k, pts, _cv = self.bend
            a, b = pts[k], pts[(k + 1) % len(pts)]
            R = CV.radius_of_sagitta(a, b, self.bend_v)
            return (("R " + compat.fmt_len(R)) if R else "straight", None)
        if self.side is not None:
            return (compat.fmt_len(abs(self.dside)), None)
        return super().value_label()

    def rubber_band_lines(self):
        if self.side is not None or self.bend is not None:
            return []
        return super().rubber_band_lines()

    def status_clause(self) -> str:
        if self.curve_mode == "round":
            if self.bend is not None:
                return ("Round corner: move along the corner, click — or type "
                        "the radius + Enter (0 = sharp)  ·  Esc = put it back")
            return "Round corner: click a slab's corner  ·  Esc = finish"
        if self.curve_mode == "bend":
            if self.bend is not None:
                return ("Bend side: pull its middle, click — or type the "
                        "radius + Enter (0 = straight)  ·  Esc = put it back")
            return "Bend side: click a slab's side  ·  Esc = finish"
        if self.side_mode:
            if self.side is not None:
                return ("Move side: click where it goes, or type a distance "
                        "+ Enter  ·  Esc = put it back")
            return "Move side: click a slab's side  ·  Esc = finish"
        return super().status_clause().replace("Edit plot", "Edit slab")

    # -- drawn: the outlines as they are, curves and all ------------------------------
    def _outline_px(self, pts, cv, z: float):
        loop = CV.expand(pts, cv) if (cv.get("r") or cv.get("arc")) else pts
        return [compat.to_pixel(self.viewport, q[0], q[1], z) for q in loop]

    def draw_overlay(self, viewport, painter) -> None:
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QColor, QPen
        # the base draws the CLICKED corners (the control outline) and the
        # grips; the true outline — arcs, rounded corners — over it
        super().draw_overlay(viewport, painter)
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        for sid, st in self.get_digs().items():
            cv = CV.clean(st.get("curves"))
            z = st["heights"][0] if st.get("heights") else 0.0
            pts = st["corners"]
            live = sid == self.target
            if live and self.bend is not None and self.bend_v is not None:
                pts = self.bend[1]
                cv = self._bend_curves(self.bend_v)
                bad = self._bend_why(cv) is not None
            elif live and self.pending is not None:
                pts = self.pending[0]
                cv, _d = CV.remap(st["corners"], pts, cv)
                bad = CV.why_not(pts, cv) is not None
                if bad:
                    cv = {"r": {}, "arc": {}}
            else:
                bad = False
            if not (cv["r"] or cv["arc"]):
                continue                     # straight: the base drew it
            try:
                px = self._outline_px(pts, cv, z)
            except Exception:  # noqa: BLE001 — a passing bad shape
                continue
            col = QColor(RED if bad else ACTIVE)
            painter.setPen(QPen(col, 2.6 if live else 1.6,
                                Qt.SolidLine if live else Qt.DashLine))
            for a, b in zip(px, px[1:] + px[:1]):
                if a and b:
                    painter.drawLine(QPointF(*a), QPointF(*b))
        painter.restore()
