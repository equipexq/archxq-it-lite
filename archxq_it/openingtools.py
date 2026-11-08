# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Placing OPENINGS — doors, windows, voids — in the walls.

OpeningTool: the cursor near a straight wall of the level takes the
opening onto it (its width from the options bar, centred where the cursor
is, kept clear of the wall's ends); a click places it — or says why it
can't (another opening there, too tall…). Tab turns a door's hinge to the
other side. The preview — and the plan, afterwards — draw the opening as
a plan does: its jambs, a window's glass, a door's leaf and its swing.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QObject, Qt

from . import compat, opendims as D, structure as S, walls as W
from .plottools import _PlotTool

REACH = 0.40          # m from a wall's face the cursor still finds it
INK = "#e8742c"       # the preview
PLAN_INK = "#2b3138"  # openings drawn in the plan


def find_wall(p, walls: list[dict]):
    """(wall, centre seg, distance along it) of the straight wall nearest
    the point, or None."""
    best = None
    for w in walls:
        if w.get("kind", "line") != "line" or W.why_not(w) is not None:
            continue
        s = W.centre(w)
        f, off = s.project(p)
        if not 0.0 <= f <= 1.0:
            continue
        gap = abs(off) - float(w["t"]) / 2
        if gap > REACH:
            continue
        if best is None or gap < best[0]:
            best = (gap, w, s, f * s.L)
    return best[1:] if best else None


def symbol_lines(o: dict, wall: dict, seg) -> list:
    """The opening in plan, as lines [((x, y), (x, y))…]: jambs across
    the wall; a window's glass along it; a door's leaf, open 90° to the
    inside, and its swing."""
    p0, u = seg.p0, seg.u
    n = (-u[1], u[0])
    t = float(wall["t"]) / 2
    s0, s1 = o["pos"] - o["w"] / 2, o["pos"] + o["w"] / 2

    def P(s, c):
        return (p0[0] + u[0] * s + n[0] * c, p0[1] + u[1] * s + n[1] * c)
    lines = [(P(s0, -t), P(s0, t)), (P(s1, -t), P(s1, t))]
    if o.get("op") == "shop" and o["kind"] in ("door", "window"):
        from .shopfront import plan_lines
        return plan_lines(o, wall, P, s0, s1, t)
    if o["kind"] == "window" and o.get("op") in S.WIN_KINDS:
        lines += _window_lines(o, wall, P, s0, s1, t, u, n)
    elif o["kind"] == "window":
        for c in (-t / 3, t / 3):
            lines.append((P(s0, c), P(s1, c)))
    elif o["kind"] == "door" and o.get("op") == "garage":
        # a garage door: its leaf, closed, across the opening (2 lines);
        # a roll-up's box on the inside face too
        for c in (-0.02, 0.02):
            lines.append((P(s0, c), P(s1, c)))
        if S.garage_kind(o) == "rollup":
            side = S.door_side(dict(o, out=False), wall)
            c1 = side * (t + S.GARAGE_BOX)
            lines += [(P(s0 - S.GARAGE_GUIDE, side * t),
                       P(s0 - S.GARAGE_GUIDE, c1)),
                      (P(s0 - S.GARAGE_GUIDE, c1), P(s1 + S.GARAGE_GUIDE, c1)),
                      (P(s1 + S.GARAGE_GUIDE, c1),
                       P(s1 + S.GARAGE_GUIDE, side * t))]
    elif o["kind"] == "door" and o.get("op") == "sliding":
        lines += _sliding_lines(o, wall, P, s0, s1, t)
    elif o["kind"] == "door" and int(o.get("leaves", 1) or 1) == 2:
        inside = S.door_side(o, wall)
        m = (s0 + s1) / 2
        for hinge, away in ((s0, 1.0), (s1, -1.0)):   # a pair, each half
            lines += _swing_lines(P, hinge, away, inside, t, m - s0, u, n)
    elif o["kind"] == "door":
        inside = S.door_side(o, wall)
        hinge = s0 if o.get("swing", "left") == "left" else s1
        away = 1.0 if hinge == s0 else -1.0
        h = P(hinge, inside * t)
        r = o["w"]
        tip = (h[0] + n[0] * inside * r, h[1] + n[1] * inside * r)
        lines.append((h, tip))                         # the leaf, open
        a0 = math.atan2(n[1] * inside, n[0] * inside)
        a1 = math.atan2(u[1] * away, u[0] * away)
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        pts = [(h[0] + r * math.cos(a0 + da * k / 12),
                h[1] + r * math.sin(a0 + da * k / 12)) for k in range(13)]
        lines += list(zip(pts, pts[1:]))               # the swing
    return lines


def _window_lines(o, wall, P, s0, s1, t, u, n) -> list:
    """A window with leaves in plan: SLIDING — its leaves in two tracks
    and an arrow; CASEMENT — each leaf's swing, thin, open 90°; AWNING —
    dashes outward from its line (it tilts out)."""
    op, k = o.get("op"), S.window_leaves(o)
    if op == "sliding":
        d, lap = 0.03, 0.05
        lw = (s1 - s0 + (k - 1) * lap) / k
        # a louvred one may have 6 leaves: alternate past the table
        tracks = S.WIN_TRACKS.get(k) or [("B", "F")[i % 2] for i in range(k)]
        out = []
        for i in range(k):
            a = s0 + i * (lw - lap)
            c0, c1 = (0.0, d) if tracks[i] == "F" else (-d, 0.0)
            out += [(P(a, c0), P(a + lw, c0)), (P(a + lw, c0), P(a + lw, c1)),
                    (P(a + lw, c1), P(a, c1)), (P(a, c1), P(a, c0))]
        m = (s0 + s1) / 2
        return out + _arrow(P, m - 0.15, m + 0.15, t + 0.08)
    if op == "casement":
        # each leaf by its role (2026-10-31): a hinged one's swing, a fixed
        # one's glass along the wall — the same widths as in 3D, the plan's
        # leaves meeting with no gap (1 and 2 leaves as they always were)
        inside = S.door_side(o, wall)
        from .openfinish import leaf_shares
        roles = S.casement_roles(o)
        leaves, _m = S.casement_layout(roles, s0, s1, gap=0.0,
                                       shares=leaf_shares(o, len(roles)))
        out = []
        for a, b, r in leaves:
            if r == "F":
                out.append((P(a, 0.0), P(b, 0.0)))
            elif r == "L":
                out += _swing_lines(P, a, 1.0, inside, t, b - a, u, n)
            else:
                out += _swing_lines(P, b, -1.0, inside, t, b - a, u, n)
        return out
    if op == "hung":                   # a sash: its two leaves, one behind
        return [(P(s0, -0.015), P(s1, -0.015)), (P(s0, 0.015), P(s1, 0.015))]
    # awning: three short dashes outward, the way it opens; PIVOT: its
    # panes turn on their middle — dashes to both sides
    so = -S.door_side(dict(o, out=False), wall)
    out = [(P(s0, 0.0), P(s1, 0.0))]
    sides = (so, -so) if op == "pivot" else (so,)
    for f in (0.25, 0.5, 0.75):
        s = s0 + (s1 - s0) * f
        for sd in sides:
            out.append((P(s, sd * (t + 0.03)), P(s, sd * (t + 0.15))))
    return out


def _swing_lines(P, hinge, away, inside, t, r, u, n) -> list:
    """One hinged leaf of width ``r``, open 90° to the inside, and its
    swing."""
    h = P(hinge, inside * t)
    out = [(h, (h[0] + n[0] * inside * r, h[1] + n[1] * inside * r))]
    a0 = math.atan2(n[1] * inside, n[0] * inside)
    a1 = math.atan2(u[1] * away, u[0] * away)
    da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    pts = [(h[0] + r * math.cos(a0 + da * k / 12),
            h[1] + r * math.sin(a0 + da * k / 12)) for k in range(13)]
    return out + list(zip(pts, pts[1:]))


def _sliding_lines(o, wall, P, s0, s1, t) -> list:
    """A sliding door in plan: its leaf (a thin box) and an arrow the way
    it slides — one leaf along the inside face, two inside the wall."""
    def box(a, b, c0, c1):
        return [(P(a, c0), P(b, c0)), (P(b, c0), P(b, c1)),
                (P(b, c1), P(a, c1)), (P(a, c1), P(a, c0))]
    two = int(o.get("leaves", 1) or 1) == 2
    if two or o.get("leaf") == "glass":
        # within the frame, two tracks: two leaves part from the middle; a
        # glazed single one slides over its fixed pane
        m, lap, d = (s0 + s1) / 2, 0.025, 0.04
        out = box(s0, m + lap, -d, 0.0) + box(m - lap, s1, 0.0, d)
        arrows = ((m - 0.10, s0 + 0.10, -d / 2), (m + 0.10, s1 - 0.10, d / 2))
        if not two:
            # the fixed pane (back track) on the side it slides TO, the
            # moving one in front, its arrow going over the fixed one
            left = o.get("swing", "left") == "left"
            if left:
                out = box(s0, m + lap, -d, 0.0) + box(m - lap, s1, 0.0, d)
                arrows = ((s1 - 0.10, m - 0.10, d / 2),)
            else:
                out = box(m - lap, s1, -d, 0.0) + box(s0, m + lap, 0.0, d)
                arrows = ((s0 + 0.10, m + 0.10, d / 2),)
        for a, b, c in arrows:
            out += _arrow(P, a, b, c)
        return out
    inside = S.door_side(o, wall)
    c0, c1 = inside * (t + 0.01), inside * (t + 0.05)
    out = box(s0 - 0.05, s1 + 0.05, c0, c1)
    w = s1 - s0
    left = o.get("swing", "left") == "left"
    a, b = (s0 + w * 0.7, s0 - w * 0.4) if left else (s1 - w * 0.7,
                                                     s1 + w * 0.4)
    return out + _arrow(P, a, b, inside * (t + 0.12))


def _arrow(P, a, b, c) -> list:
    """An arrow along the wall from ``a`` to ``b``, ``c`` across."""
    k = 0.08 if b > a else -0.08
    tip = P(b, c)
    return [(P(a, c), tip), (P(b - k, c - 0.05), tip),
            (P(b - k, c + 0.05), tip)]


PLAN_CUT = 1.20       # m over the floor: where a plan cuts (as the sheets)


def cut_in_plan(o: dict) -> bool:
    """Does a plan cut through it? A door always; a window when the cut
    height falls between its sill and its head — a high window stays
    under the wall, as plans draw it."""
    if o["kind"] != "window":
        return True
    sill = float(o.get("sill", 0.0) or 0.0)
    return sill <= PLAN_CUT < sill + float(o["h"])


def cut_quad(o: dict, wall: dict, seg) -> list:
    """The wall's stretch an opening takes, in plan: 4 (x, y) points —
    painted over in the wall's own colour, the wall reads cut there."""
    p0, u = seg.p0, seg.u
    n = (-u[1], u[0])
    t = float(wall["t"]) / 2
    s0, s1 = o["pos"] - o["w"] / 2, o["pos"] + o["w"] / 2
    return [(p0[0] + u[0] * s + n[0] * c, p0[1] + u[1] * s + n[1] * c)
            for s, c in ((s0, -t), (s1, -t), (s1, t), (s0, t))]


def fill_quads(viewport, painter, quads, z, colour) -> None:
    """Fill each quad and stroke it in the same colour (2 px): the wall's
    face lines, right on its edge, go under it too."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QPen, QPolygonF
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing, False)
    c = QColor(colour)
    painter.setPen(QPen(c, 2.0))
    painter.setBrush(c)
    for q in quads:
        pts = [compat.to_pixel(viewport, x, y, z) for x, y in q]
        if all(pts):
            painter.drawPolygon(QPolygonF([QPointF(p[0], p[1]) for p in pts]))
    painter.restore()


def draw_lines(viewport, painter, lines, z, ink, width=1.6) -> None:
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QPen
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(ink), width))
    for a, b in lines:
        pa = compat.to_pixel(viewport, a[0], a[1], z)
        pb = compat.to_pixel(viewport, b[0], b[1], z)
        if pa and pb:
            painter.drawLine(QPointF(pa[0], pa[1]), QPointF(pb[0], pb[1]))
    painter.restore()


class _TypedEnter(QObject):
    """Enter with a distance typed: the opening tool's, BEFORE the host's
    value box reads it (it takes «60» for 60 m and refuses «1.05c» — tried
    2026-10-25; a tool's ``on_key`` comes after)."""

    def __init__(self, tool) -> None:
        super().__init__()
        self.tool = tool

    def eventFilter(self, obj, event) -> bool:
        try:
            if event.type() == QEvent.KeyPress \
                    and event.key() in (Qt.Key_Return, Qt.Key_Enter):
                typed = compat.typed_value(obj)
                if typed and D.parse(typed) is not None:
                    compat.clear_typed(obj)
                    self.tool.place_typed(typed)
                    obj.update()
                    return True
        except Exception:  # noqa: BLE001 — never in the host's way
            compat.log_error("opening typed distance")
        return False


class OpeningTool(_PlotTool):
    name = "ArchXQ opening"
    noun = "Opening"
    icon = "rectangle"
    claimed_keys = frozenset({Qt.Key_Tab, Qt.Key_Backtab})
    #: placed in the plan OR straight in 3D (PLANO_ABERTURAS_3D.md, his OK
    #: 29/10): in 3D the wall is the one the camera's ray meets (place3d)
    stays_in_view = True
    #: ui sets: every level's shown walls (place3d.wall_entry) and every
    #: level's openings — the ray's walls and the lines to align with
    walls_3d = staticmethod(lambda: [])
    openings_3d = staticmethod(lambda: [])
    level_id = None
    other = None            # 3D: the level of the wall met, not this one
    guides3d: list = []     # 3D: the lines it was pulled into line with
    _ray_wall = None        # 3D: the wall the ray met (this level's)

    def __init__(self, kind, on_done, on_cancelled, z, opts, walls,
                 openings, wall_height):
        """``opts()`` → the options bar's sizes; ``walls()`` / ``openings()``
        → this level's; ``wall_height(wall)`` → how high it stands."""
        super().__init__(on_done, on_cancelled)
        self.kind = kind
        self.axq_element = kind
        self.noun = S.OPENING_LABEL[kind]
        self.z = z
        self.opts = opts
        self.walls = walls
        self.openings = openings
        self.wall_height = wall_height
        self.here = None                 # (wall, seg, record) under cursor
        self.dims = None                 # (face, lo, hi, cursor) of it

    def on_activate(self, viewport) -> None:
        super().on_activate(viewport)
        self._enter = _TypedEnter(self)
        viewport.installEventFilter(self._enter)

    def on_deactivate(self, viewport) -> None:
        f = self.__dict__.pop("_enter", None)
        if f is not None:
            viewport.removeEventFilter(f)
        super().on_deactivate(viewport)

    def _reset(self) -> None:
        self.diag = None
        self.here = None
        self.dims = None
        self._sync()

    def _busy(self) -> bool:
        return False

    def _sync(self) -> None:
        self._sync_protocol([], self.hover)

    def _span(self, wall, pos) -> tuple:
        """``S.opening_span`` for the cursor's bay, kept per wall while the
        tool runs (the walls don't change under it; ~20 ms each)."""
        spans = self.__dict__.setdefault("_spans", {})
        for b0, b1, span in spans.get(wall["id"], ()):
            if b0 - 1e-6 <= pos <= b1 + 1e-6:
                return span
        b0, b1 = S.wall_bay({"walls": self.walls()}, wall, pos)
        span = (b0 + S.END_GAP, b1 - S.END_GAP)
        spans.setdefault(wall["id"], []).append((b0, b1, span))
        return span

    def _pick(self, ctx):
        """In 3D: the point on the face of the wall the camera's ray meets
        — this level's, nothing in front of it — pulled into line with the
        openings above / below / beside it; None: no wall of this level
        there (``other``: the level it is on). The plan: as ever."""
        from . import place3d as P3
        self.other, self.guides3d, self._ray_wall = None, [], None
        if not P3.in_3d(self.viewport):
            return super()._pick(ctx)
        ray = P3.ray_of(self.viewport, ctx)
        if ray is None:
            return super()._pick(ctx)
        entries = self.walls_3d()
        got = P3.walls_hit(entries, ray)
        if got is None:
            return None
        k, e, _h, s, side = got
        near = compat.ray_distance(self.viewport, *ray)
        if near is not None and near < k - 0.05:
            return None                 # something in front: a column, a slab
        if e["level"] != self.level_id:
            self.other = e["name"]
            return None
        w = e["wall"]
        seg = W.centre(w)
        half = float(self.opts()["w"]) / 2
        try:
            lines = P3.lines_on_wall(w, entries, self.openings_3d())
            hx, hy = P3.face_point(w, s, side)
            tol = P3.ALIGN_PX * P3.metres_per_px(
                self.viewport, hx, hy, _h[2], seg.u)
            s2, line = P3.snap_along(s, half, [c[0] for c in lines], tol)
            if line is not None:
                self.guides3d = [c for c in lines if abs(c[0] - line) < 1e-6]
                s = s2
        except Exception:  # noqa: BLE001 — the line is a help, never a stop
            compat.log_error("opening 3D align")
        self._ray_wall = w["id"]
        return P3.face_point(w, min(max(s, 0.0), seg.L), side)

    def record(self, p):
        """The opening the cursor at ``p`` would place, on its wall."""
        if p is None:
            return None
        walls = self.walls()
        if self._ray_wall is not None:      # 3D: the wall the ray met
            walls = [w for w in walls if w["id"] == self._ray_wall]
        got = find_wall(p, walls)
        if got is None:
            return None
        wall, seg, pos = got
        o = dict(self.opts())
        lo, hi = self._span(wall, pos)
        half = o["w"] / 2
        pos = min(max(pos, lo + half), hi - half) if hi - lo > 2 * half \
            else (lo + hi) / 2
        rec = {"kind": self.kind, "wall": wall["id"],
               "pos": round(pos, 4), "w": o["w"], "h": o["h"],
               "sill": 0.0 if self.kind == "door" else o.get("sill", 0.0),
               "swing": o.get("swing", "left")}
        if self.kind == "door":                     # its library type
            rec["op"] = o.get("op", "swing")
            rec["leaves"] = int(o.get("leaves", 1) or 1)
            rec["leaf"] = o.get("leaf", "solid")
            rec["open"] = o.get("open", 0.0)
            rec["out"] = bool(o.get("out", False))   # opens to the outside
            if rec["op"] == "swing" and o.get("top") == "arched":
                rec["top"] = "arched"                # (0.15.0: under an arch)
            if rec["op"] == "garage":                # a garage door's kind
                rec["garage"] = S.garage_kind(o)
                rec["gfinish"] = S.garage_finish(o)
                rec["gwin"] = bool(o.get("gwin"))
                rec["leaves"] = 1
        if self.kind == "window" and o.get("op") in S.WIN_KINDS:
            rec["op"] = o["op"]                      # a window with leaves
            rec["leaves"] = S.window_leaves(o)
            rec["out"] = bool(o.get("out", False))
            rec["open"] = o.get("open", 0.0)
            if o["op"] == "casement" and rec["leaves"] > 1:
                # each leaf fixed or hinged (2026-10-31)
                rec.update({f"role{i + 1}": r for i, r in
                            enumerate(S.casement_roles(o))})
        if o.get("op") == "shop" and self.kind in ("door", "window"):
            from .shopfront import DEFAULTS          # a shopfront's own
            rec["op"] = "shop"
            rec.update({k: o.get(k, v) for k, v in DEFAULTS.items()})
        if o.get("glass") == "opaque":               # opaque panes
            rec["glass"] = "opaque"
        if self.kind in ("window", "void") and rec.get("op") != "shop" \
                and o.get("oshape", "rect") != "rect":   # its shape (10-31)
            from .shapes import clean as shape_keys
            rec.update(shape_keys(dict(rec, shape=o["oshape"],
                                       rise=o.get("rise"),
                                       top_w=o.get("top_w"))))
            if rec.get("shape") == "circle":         # as high as wide
                rec["h"] = rec["w"]
        from .trim import keys_of                    # its trim and sill
        rec.update(keys_of(dict(o, op=rec.get("op")), self.kind))
        from .openfinish import keys_of as finish_keys   # colours, handle
        rec.update(finish_keys(dict(o, kind=self.kind, op=rec.get("op"))))
        return wall, seg, rec

    def _bay(self, wall, pos, face) -> tuple:
        """``wall_bay`` on the cursor's face, kept like ``_span``."""
        bays = self.__dict__.setdefault("_bays", {})
        for b0, b1 in bays.get((wall["id"], face), ()):
            if b0 - 1e-6 <= pos <= b1 + 1e-6:
                return b0, b1
        got = S.wall_bay({"walls": self.walls()}, wall, pos, face)
        bays.setdefault((wall["id"], face), []).append(got)
        return got

    def _dims(self, p, got):
        """(face, lo, hi, cursor along the wall) for the opening ``got``
        previewed under the cursor ``p`` — what its dimensions measure."""
        wall, _seg, rec = got
        face = D.face_of(wall, p)
        cur = W.centre(wall).project(p)[0] * W.centre(wall).L
        lo, hi = D.refs(self.walls(), wall, rec["pos"], face,
                        self.openings(),
                        bay=self._bay(wall, rec["pos"], face))
        return face, lo, hi, cur

    def on_hover(self, ctx) -> None:
        super().on_hover(ctx)
        self.here = self.record(self.hover) if self.hover else None
        try:
            self.dims = self._dims(self.hover, self.here) \
                if self.here else None
        except Exception:  # noqa: BLE001 — dimensions never stop the tool
            self.dims = None

    vcb_label = "Distance"

    def place_typed(self, text: str) -> bool:
        """A typed distance + Enter (PLANO_COTAS_ABERTURAS.md): the edge —
        or, «…c», the centre — that far from the hot dimension's corner
        or neighbour. False: not a distance / nowhere to put it."""
        got = D.parse(text)
        if got is None or self.here is None or self.dims is None:
            return False
        d, centre = got
        wall, _seg, rec = self.here
        face, lo, hi, cur = self.dims
        side = D.hot_side(cur, lo, hi)
        rec = dict(rec, pos=D.pos_for(d, side, lo, hi, rec["w"], centre))
        why = S.opening_room(rec, wall, self.openings(),
                             self.wall_height(wall))
        if why is None and not (lo - 1e-6 <= rec["pos"] - rec["w"] / 2
                                and rec["pos"] + rec["w"] / 2 <= hi + 1e-6):
            why = "It doesn't fit there"
        if why:
            compat.flash(self.viewport, f"{why} — try another distance", 5000)
            return True
        self.viewport.update()
        self.on_done(rec)
        return True

    def on_value(self, viewport, value) -> bool:
        # (the host read the number itself: «60» = 60 m in a metres
        # document — a door's distance over 10 m is centimetres)
        if not isinstance(value, (int, float)):
            return False
        v = float(value)
        if compat.doc_length_unit() == "m" and v > 10:
            v /= 100.0
        return self.place_typed(f"{v}m")

    def _other_say(self) -> str:
        from .place3d import other_level_say
        return other_level_say(self.other)

    def on_click(self, ctx) -> None:
        p = self._pick(ctx)
        got = self.record(p)
        if got is None:
            if self.other:                 # 3D: the level rules (D4)
                compat.flash(self.viewport, self._other_say(), 5000)
                return
            compat.flash(self.viewport, f"{self.noun}: click ON a straight "
                         "wall of this level", 4000)
            return
        wall, _seg, rec = got
        why = S.opening_room(rec, wall, self.openings(),
                             self.wall_height(wall))
        if why:
            compat.flash(self.viewport, f"{why} — try another place", 5000)
            return
        self.viewport.update()
        self.on_done(rec)               # the tool stays for the next

    #: ui sets: the library shown again after a key changed the options
    on_flip = staticmethod(lambda: None)

    def _opens_both_ways(self) -> bool:
        o = self.opts()
        if self.kind == "door":
            return o.get("op", "swing") == "swing"    # (not a garage door)
        return self.kind == "window" and o.get("op") == "casement"

    def on_key(self, viewport, key, modifiers) -> bool:
        typed = compat.typed_value(viewport)
        if typed and key in (Qt.Key_Return, Qt.Key_Enter):
            # read here, not by the host: «60» = 60 cm, «1.05c» = centre
            if D.parse(typed) is not None:
                compat.clear_typed(viewport)
                self.place_typed(typed)
                viewport.update()
                return True
            return False
        if typed:
            return False             # the value box's keys
        backtab = key == Qt.Key_Backtab or (
            key == Qt.Key_Tab and modifiers & Qt.ShiftModifier)
        if backtab and self._opens_both_ways():
            # Shift+Tab: it opens in ↔ out (his ask, 2026-10-15: «I don't
            # remember how it opened in or out» — the library's «Opens»)
            o = self.opts()
            o["out"] = not o.get("out", False)
            if self.hover:
                self.here = self.record(self.hover)
            compat.flash(viewport, "Opens " + ("OUT" if o["out"] else "IN")
                         + " — Shift+Tab: the other way", 2500)
            self.on_flip()
            viewport.update()
            return True
        if key == Qt.Key_Tab and self.kind == "door":
            o = self.opts()
            o["swing"] = "right" if o.get("swing") == "left" else "left"
            if self.hover:
                self.here = self.record(self.hover)
            self.on_flip()
            viewport.update()
            return True
        return super().on_key(viewport, key, modifiers)

    def rubber_band_lines(self):
        return []

    def value_label(self):
        if self.here is None:
            if self.other:
                return (self._other_say(), None)
            return None
        wall, _seg, o = self.here
        text = (f"{o['w']:.2f} × {o['h']:.2f} m"
                if compat.doc_length_unit() == "m" else
                f"{compat.fmt_len(o['w'])} × {compat.fmt_len(o['h'])}")
        try:            # red: why, at the cursor (the flash went unseen)
            why = S.opening_room(o, wall, self.openings(),
                                 self.wall_height(wall))
        except Exception:  # noqa: BLE001
            why = None
        return (text + (f"  —  {why}" if why else ""), None)

    def status_clause(self) -> str:
        tail = "  ·  Tab = hinge on the other side" if self.kind == "door" \
            else ""
        if self._opens_both_ways():
            tail += "  ·  Shift+Tab = opens " + (
                "in" if self.opts().get("out") else "out")
        return (f"{self.noun}: move along a wall and click where it goes "
                f"(or type the distance from the orange corner + Enter)"
                f"{tail}  ·  Esc = done")

    def draw_overlay(self, viewport, painter) -> None:
        if self.here is not None:
            wall, seg, rec = self.here
            try:
                ok = S.opening_room(rec, wall, self.openings(),
                                    self.wall_height(wall)) is None
                draw_lines(viewport, painter, symbol_lines(rec, wall, seg),
                           self.z, INK if ok else "#d23c3c", 2.2)
                from . import place3d as P3
                if P3.in_3d(viewport):
                    # standing in the wall (D5): its outline on both faces
                    zb = self.z + W.opening_lift(wall) + float(
                        rec.get("sill", 0.0) or 0.0)
                    s0 = rec["pos"] - rec["w"] / 2
                    P3.draw3d(viewport, painter, P3.opening_frame(
                        wall, s0, s0 + rec["w"], zb, zb + rec["h"]),
                        INK if ok else "#d23c3c", 2.2)
                    # the line it was pulled into: from the other opening
                    # up / down to this one
                    P3.draw3d(viewport, painter, [
                        ((xy[0], xy[1], min(zlo, zb)),
                         (xy[0], xy[1], max(zhi, zb + rec["h"])))
                        for _s, xy, zlo, zhi in self.guides3d],
                        "#2f7df6", 1.4, dash=True)
                if self.dims is not None:
                    face, lo, hi, cur = self.dims
                    D.draw(viewport, painter, wall, face, self.z, rec["pos"],
                           rec["w"], lo, hi, D.hot_side(cur, lo, hi),
                           compat.typed_value(viewport))
            except Exception:  # noqa: BLE001 — a preview never breaks paint
                pass
        super().draw_overlay(viewport, painter)
