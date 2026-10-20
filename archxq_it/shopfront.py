"""The SHOPFRONT — a door type that makes a whole shop's front (his ask,
2026-10-10, for the corporate building's ground-floor shops): it fills the
bay between piers with fixed glass panes in a slim dark frame and a glazed
door among them; a transom of glass over the door height, a low base, a
roll-up shutter's box and its guides, a sign band over it all — the things
a shop shows from the street.

A record: a door (``kind`` "door") with ``op`` "shop" and its own keys:
  "shop_door": "double" | "single" | "sliding"   (the door's leaves)
  "door_at":   "left" | "centre" | "right"        (where the door stands)
  "dh":        the door's height (m, from the sill)
  "base":      a solid base under the fixed panes (0 = glass to the floor)
  "transom":   True — a bar across at the door's height, glass over it
  "panes":     fixed panes on EACH side (0 = from the width, ~1.25 m each)
  "shutter":   True — a roll-up shutter's box over it, its guides at the
               jambs (on the street side)
  "sign":      True — a sign band on the wall face over it all
  "shop_in":   True — the door opens to the inside (the default: out, the
               way a shop's exit opens)
The door opens / slides by the library's «Open» slider like any door.
Pure geometry — no Qt; ``structure.opening_parts`` and
``openingtools.symbol_lines`` call it.
"""
from __future__ import annotations

import math

#: what the library's «Shopfront» card starts a NEW one with
DEFAULTS = {"shop_door": "double", "door_at": "centre", "dh": 2.20,
            "base": 0.0, "transom": True, "panes": 0, "shutter": False,
            "sign": False, "shop_in": False}
#: the record keys a shopfront keeps (model._openings)
KEYS = tuple(DEFAULTS)

ALU = 0.05               # m, the frame's / mullions' face width
DEPTH = 0.07             # m, the frame's depth through the wall
PANE = 1.25              # m, a fixed pane's usual width (auto count)
DOOR_W = {"double": 1.60, "single": 0.90, "sliding": 2.00}
SHUTTER_H = 0.30         # m, the shutter's box
SHUTTER_D = 0.28         # m, how far it stands off the wall face
GUIDE = 0.06             # m, a shutter guide (width and depth)
SIGN_H = 0.60            # m, the sign band
SIGN_D = 0.05            # m, its depth off the wall face
HANDLE_H = 0.80          # m, a pull handle's length
OFF = 0.002              # m, off the wall face (never its plane)
#: a solid panel (over a door, a base) this far in from the frame's faces —
#: thick enough that its back never shows through from afar
PANEL_IN = 0.010

ALU_COLOR = (0.18, 0.19, 0.21, 1.0)      # dark anodised aluminium
GLASS_COLOR = (0.55, 0.72, 0.80, 0.30)
BASE_COLOR = (0.30, 0.31, 0.33, 1.0)     # an aluminium panel
STEEL_COLOR = (0.66, 0.68, 0.70, 1.0)    # the shutter (galvanised)
SIGN_COLOR = (0.12, 0.13, 0.15, 1.0)
HANDLE_COLOR = (0.80, 0.81, 0.82, 1.0)   # brushed steel


def opt(o: dict, key: str):
    return o.get(key, DEFAULTS[key])


def has_door(o: dict) -> bool:
    """A shopfront has its door; a SHOP WINDOW (a window, his ask
    2026-10-11: the shops' sides) is all fixed panes."""
    return o.get("kind") == "door"


def layout(o: dict, a: float, b: float) -> tuple:
    """((d0, d1) the door's stretch — None for a shop window —, [fixed panes
    (s0, s1)…]) between the frame's inner faces ``a`` … ``b`` along the
    wall."""
    if not has_door(o):
        return None, _panes(o, a, b)
    dw = min(DOOR_W.get(opt(o, "shop_door"), 1.60), max(b - a - 2 * ALU, 0.6))
    at = opt(o, "door_at")
    if at == "left":
        d0 = a
    elif at == "right":
        d0 = b - dw
    else:
        d0 = (a + b - dw) / 2
    d1 = d0 + dw
    return (d0, d1), _panes(o, a, d0 - ALU) + _panes(o, d1 + ALU, b)


def _panes(o: dict, lo: float, hi: float) -> list:
    """Fixed panes from ``lo`` to ``hi``, a mullion between each two."""
    span = hi - lo
    if span < 0.15:
        return []
    k = int(opt(o, "panes") or 0) or max(1, round(span / PANE))
    w = (span - (k - 1) * ALU) / k
    if w < 0.15:
        k, w = 1, span
    return [(lo + i * (w + ALU), lo + i * (w + ALU) + w) for i in range(k)]


def street(o: dict, wall: dict | None) -> float:
    """The street side across the wall (+1 / −1): the wall's outside."""
    inside = 1.0 if wall is None or float(wall.get("side", 1)) >= 0 \
        else -1.0
    return -inside


def parts(o: dict, box, s0: float, s1: float, zs: float, zt: float,
          wall: dict | None, top: float | None = None) -> list:
    """The shopfront's boxes: ``box(sa, sb, ca, cb, za, zb, color)`` makes
    one along the wall (s), across it (c, from its centre line), in height
    (z). ``top``: the wall's top (the shutter's box and the sign stay
    under it)."""
    f, hd = ALU, DEPTH / 2
    out = [box(s0, s0 + f, -hd, hd, zs, zt, ALU_COLOR),      # jambs, head
           box(s1 - f, s1, -hd, hd, zs, zt, ALU_COLOR),
           box(s0 + f, s1 - f, -hd, hd, zt - f, zt, ALU_COLOR)]
    a, b = s0 + f, s1 - f
    door, panes = layout(o, a, b)
    out.append(box(s0 + f, s1 - f, -hd, hd, zs, zs + f, ALU_COLOR)
               if door is None else [])             # a window's sill bar
    zs0 = zs + (f if door is None else 0.0)         # (its panes stand on it)
    # a door's head / a window's bar across: under the head, over the base
    dh = min(max(float(opt(o, "dh")), 0.3), zt - zs - f)
    zd = zs + dh
    over = zt - f - zd > 0.12                       # room over the door
    base = min(max(float(opt(o, "base") or 0.0), 0.0), 0.6)
    transom = bool(opt(o, "transom")) and over and zd > zs0 + base + 0.3
    if door is not None:
        d0, d1 = door
        # the door's own jambs (mullions) — and its head bar
        for s in (d0 - f, d1):
            if a - 1e-6 <= s and s + f <= b + 1e-6:
                out.append(box(s, s + f, -hd, hd, zs, zt - f, ALU_COLOR))
        if over:
            out.append(box(d0, d1, -hd, hd, zd, zd + f, ALU_COLOR))
            if transom:
                out.append(box(d0, d1, -0.004, 0.004, zd + f, zt - f,
                               GLASS_COLOR))
            else:
                # 5 cm, 1 cm in from the frame's faces: 2 cm let its back
                # face show through from afar (yellow streaks moving with
                # the camera — the depth buffer's grain; his screen,
                # 2026-10-16)
                out.append(box(d0, d1, -(hd - PANEL_IN), hd - PANEL_IN,
                               zd + f, zt - f, BASE_COLOR))
    # the fixed panes: mullions between them, a base, the transom bar
    for i, (pa, pb) in enumerate(panes):
        if i and abs(pa - panes[i - 1][1] - f) < 1e-6:
            out.append(box(pa - f, pa, -hd, hd, zs0, zt - f, ALU_COLOR))
        z = zs0
        if base > 0.02:
            out.append(box(pa, pb, -(hd - PANEL_IN), hd - PANEL_IN, zs0,
                           zs0 + base, BASE_COLOR))
            out.append(box(pa, pb, -hd, hd, zs0 + base, zs0 + base + f,
                           ALU_COLOR))
            z = zs0 + base + f
        if transom:
            out.append(box(pa, pb, -hd, hd, zd, zd + f, ALU_COLOR))
            out.append(box(pa, pb, -0.004, 0.004, z, zd, GLASS_COLOR))
            out.append(box(pa, pb, -0.004, 0.004, zd + f, zt - f,
                           GLASS_COLOR))
        else:
            out.append(box(pa, pb, -0.004, 0.004, z, zt - f, GLASS_COLOR))
    # (the frame's inner faces: how far a sliding leaf may run)
    if door is not None:
        out += _door(dict(o, _a=a, _b=b), box, d0, d1, zs + 0.01, zd, wall)
    out = [p for p in out if p]
    # the street side: a roll-up shutter's guides and box, a sign band
    t = float(wall["t"]) / 2 if wall else hd
    sd = street(o, wall)

    def C(c0, c1):                       # across, from the wall face out
        return tuple(sorted((sd * (t + c0), sd * (t + c1))))
    room = (top - zt) if top is not None else 10.0
    zb = zt
    if opt(o, "shutter"):
        for s in (s0 - GUIDE, s1):
            out.append(box(s, s + GUIDE, *C(OFF, OFF + GUIDE), zs, zt,
                           STEEL_COLOR))
        h = min(SHUTTER_H, room - 0.01)
        if h > 0.08:
            out.append(box(s0 - GUIDE, s1 + GUIDE, *C(OFF, OFF + SHUTTER_D),
                           zt, zt + h, STEEL_COLOR))
            zb = zt + h
    if opt(o, "sign"):
        h = min(SIGN_H, (top - zb - 0.02) if top is not None else SIGN_H)
        if h > 0.12:
            out.append(box(s0 - GUIDE, s1 + GUIDE, *C(OFF, OFF + SIGN_D),
                           zb + 0.01, zb + 0.01 + h, SIGN_COLOR))
    return out


def _door(o, box, d0, d1, za, zb, wall) -> list:
    """The glazed door between ``d0`` and ``d1``: two leaves or one,
    hinged (turned by «Open», to the street unless ``shop_in``) or two
    sliding apart; pull handles on the leaves."""
    from . import structure as S
    kind = opt(o, "shop_door")
    op = S.opened(o)
    if kind == "sliding":
        # the leaves run over the fixed panes — never past the frame (his
        # test, 2026-10-11: a door at the right slid into the wall): with
        # room on both sides they part; else both go where the room is
        m, lap, d, g = (d0 + d1) / 2, 0.025, S.LEAF, 0.003
        half = m - d0
        a, b = o.get("_a", d0), o.get("_b", d1)
        rl, rr = max(d0 - a, 0.0), max(b - d1, 0.0)
        if rl >= half * 0.9 and rr >= half * 0.9:
            sl, sr = op * half * 0.9, op * half * 0.9
        elif rl >= rr:                     # both to the left
            sl = min(op * half, rl)
            sr = -min(op * 2 * half, rl + half)
        else:                              # both to the right
            sl = -min(op * 2 * half, rr + half)
            sr = min(op * half, rr)
        return (_glass(box, d0 - sl, m + lap - sl, -d - g, -g, za, zb)
                + _glass(box, m - lap + sr, d1 + sr, g, d + g, za, zb))
    inside = 1.0 if wall is None or float(wall.get("side", 1)) >= 0 \
        else -1.0
    side = inside if opt(o, "shop_in") else -inside
    th = op * math.pi / 2
    if kind == "single":
        left = o.get("swing", "left") == "left"
        return _swung(box, d0 if left else d1, not left, side, th,
                      d1 - d0, za, zb)
    half = (d1 - d0) / 2 - 0.0025
    return (_swung(box, d0, False, side, th, half, za, zb)
            + _swung(box, d1, True, side, th, half, za, zb))


def _glass(box, a, b, c0, c1, za, zb) -> list:
    """A glazed leaf, in its frame, along the wall."""
    f = min(ALU, (b - a) / 4)
    cm = (c0 + c1) / 2
    return [box(a, a + f, c0, c1, za, zb, ALU_COLOR),
            box(b - f, b, c0, c1, za, zb, ALU_COLOR),
            box(a + f, b - f, c0, c1, za, za + 2 * f, ALU_COLOR),
            box(a + f, b - f, c0, c1, zb - f, zb, ALU_COLOR),
            box(a + f, b - f, cm - 0.004, cm + 0.004, za + 2 * f, zb - f,
                GLASS_COLOR)]


def _swung(box, hinge, back: bool, side: float, th: float, length, za,
           zb) -> list:
    """A hinged glazed leaf, ``length`` long, turned ``th`` from closed
    about ``hinge`` (on the wall's centre line) towards ``side`` — made in
    the leaf's own frame (``box.turned``)."""
    leaf = box.turned(hinge, back, side, th)
    out = _glass(leaf, 0.0, length, -0.02, 0.02, za, zb)
    # the pull handle: near the leaf's free edge, both faces
    h0 = za + max((zb - za) / 2 - HANDLE_H / 2, 0.3)
    e = length - 0.12
    out.append(leaf(e - 0.015, e + 0.015, -0.07, 0.07, h0, h0 + HANDLE_H,
                    HANDLE_COLOR))
    return out


def plan_lines(o: dict, wall: dict, P, s0: float, s1: float,
               t: float) -> list:
    """The shopfront in plan: its frame line through the wall, the fixed
    panes' glass, the mullions, the door's swing (or its sliding leaves)."""
    a, b = s0 + ALU, s1 - ALU
    door, panes = layout(o, a, b)
    out = [(P(s0, -t), P(s0, t)), (P(s1, -t), P(s1, t))]
    for pa, pb in panes:                      # the glass, twin lines
        for c in (-0.01, 0.01):
            out.append((P(pa, c), P(pb, c)))
        out.append((P(pb, -DEPTH / 2), P(pb, DEPTH / 2)))
    if door is None:                          # a shop window: no door
        return out
    d0, d1 = door
    for s in (d0, d1):                        # the door's jambs
        out.append((P(s, -DEPTH / 2), P(s, DEPTH / 2)))
    kind = opt(o, "shop_door")
    if kind == "sliding":
        m = (d0 + d1) / 2
        out += [(P(d0, -0.02), P(m + 0.025, -0.02)),
                (P(m - 0.025, 0.02), P(d1, 0.02))]
        return out
    inside = 1.0 if float(wall.get("side", 1)) >= 0 else -1.0
    side = inside if opt(o, "shop_in") else -inside
    from .openingtools import _swing_lines
    seg_u = _unit(P(1.0, 0.0), P(0.0, 0.0))
    seg_n = _unit(P(0.0, 1.0), P(0.0, 0.0))
    if kind == "single":
        left = o.get("swing", "left") == "left"
        hinge = d0 if left else d1
        out += _swing_lines(lambda s, c: P(s, c), hinge,
                            1.0 if left else -1.0, side, 0.0, d1 - d0,
                            seg_u, seg_n)
    else:
        r = (d1 - d0) / 2
        out += _swing_lines(lambda s, c: P(s, c), d0, 1.0, side, 0.0, r,
                            seg_u, seg_n)
        out += _swing_lines(lambda s, c: P(s, c), d1, -1.0, side, 0.0, r,
                            seg_u, seg_n)
    return out


def _unit(p, q):
    dx, dy = p[0] - q[0], p[1] - q[1]
    L = math.hypot(dx, dy) or 1.0
    return (dx / L, dy / L)
