"""Doors and windows, batch 1 (his go 2026-10-27, PLANO_PORTAS_JANELAS.md):
their colours, handles, leaf styles, the pivot window and the louvred
sliding window. Pure (no Qt): ``structure`` builds with it, ``model`` keeps
its keys, ``trim.part_of_color`` tells its parts apart.

Keys of an opening record (none of them = as before 2026-10-27):

- ``frame_c``: white | black | bronze | silver | wood — the frame (and a
  window's leaves, a glazed door's leaf frames). White = the old colours.
- ``leaf_c``: wood | white | grey | black — a door's solid leaf.
- ``leaf``: solid | panels | half | glass — a door's leaf (solid = plain).
- ``handle``: none | lever | knob | pull — and ``hw_c``: silver | black |
  bronze. No key: none (D2 — an old house never changes by itself).
- a window: ``op`` "pivot" (basculante, ``pv_panes``: 0 = by its height),
  ``louvred`` (a sliding window with louvres, 3 or 6 leaves — 2 or 4 of
  them louvred). (Not «shutter» / «panes»: a shop window's own.)

Every colour here is told apart from the others (the Material tab reads a
face's part by its colour): a white leaf is not the frame's white.
"""
from __future__ import annotations

import math

#: the frame — white: the old colours (a door's / a window's own)
FRAMES = {"black": (0.11, 0.11, 0.12, 1.0), "bronze": (0.36, 0.27, 0.19, 1.0),
          "silver": (0.72, 0.74, 0.76, 1.0), "wood": (0.50, 0.34, 0.20, 1.0)}
FRAME_KEYS = ("white", "black", "bronze", "silver", "wood")
#: a door's solid leaf — wood: the old one (structure.LEAF_COLOR)
LEAVES = {"white": (0.95, 0.94, 0.90, 1.0), "grey": (0.55, 0.57, 0.60, 1.0),
          "black": (0.16, 0.16, 0.17, 1.0)}
LEAF_KEYS = ("wood", "white", "grey", "black")
#: handles (their own part, «hardware»)
HARDWARE = {"silver": (0.79, 0.80, 0.81, 1.0), "black": (0.07, 0.07, 0.08, 1.0),
            "bronze": (0.46, 0.34, 0.21, 1.0)}
HANDLES = ("none", "lever", "knob", "pull")
LEAF_STYLES = ("solid", "panels", "half", "glass")
HANDLE_Z = 1.05          # m over the floor, a door's handle


def _rgb(c) -> tuple:
    return tuple(round(v, 3) for v in (c or (0, 0, 0))[:3])


def part_of_color(color) -> str | None:
    """«leaf» / «hardware» for a colour of this module, else None."""
    c = _rgb(color)
    if any(c == _rgb(v) for v in LEAVES.values()):
        return "leaf"
    if any(c == _rgb(v) for v in HARDWARE.values()):
        return "hardware"
    return None


def frame_rgb(o: dict, default):
    return FRAMES.get(o.get("frame_c"), default)


def leaf_rgb(o: dict, default):
    return LEAVES.get(o.get("leaf_c"), default)


def hw_rgb(o: dict):
    return HARDWARE.get(o.get("hw_c"), HARDWARE["silver"])


def handle_of(o: dict) -> str:
    h = o.get("handle")
    return h if h in HANDLES else "none"


def keys_of(o: dict) -> dict:
    """The keys of this module a record keeps — clean; none when unset."""
    out = {}
    if o.get("frame_c") in FRAME_KEYS and o["frame_c"] != "white":
        out["frame_c"] = o["frame_c"]
    if o.get("kind") == "door":
        if o.get("leaf_c") in LEAF_KEYS and o["leaf_c"] != "wood":
            out["leaf_c"] = o["leaf_c"]
        if o.get("handle") in HANDLES:
            out["handle"] = o["handle"]
    elif o.get("kind") == "window" and o.get("op") == "casement" \
            and o.get("handle") in ("none", "lever"):
        out["handle"] = o["handle"]
    if out.get("handle", "none") != "none" and o.get("hw_c") in HARDWARE:
        out["hw_c"] = o["hw_c"]
    if o.get("kind") == "window" and o.get("op") == "sliding" \
            and o.get("louvred") is True:
        out["louvred"] = True
    if o.get("kind") == "window" and o.get("op") == "pivot":
        p = pivot_count(o)
        if p:
            out["pv_panes"] = p
    return out


def pivot_count(o: dict) -> int:
    """A pivot window's panes as set (2–8), 0 = by its height."""
    try:
        p = int(o.get("pv_panes") or 0)
    except (TypeError, ValueError):
        return 0
    return min(max(p, 2), 8) if p else 0


# ---- the parts ------------------------------------------------------------------------
def handle(F, s, c_face, side: float, zh: float, kind: str, color,
           small: bool = False) -> list:
    """A handle on a leaf's face: ``F`` the leaf's frame (``structure._Frame``
    — s along the leaf, c across it), ``s`` where along, ``c_face`` the
    face's c, ``side`` ±1 (which way out of that face), ``zh`` its height.
    Lever: a rosette and a bar towards the hinge (−s); knob: an octagon;
    pull: a bar on two posts. Each part 1 mm into what it stands on."""
    from .structure import _sz_prism
    if kind not in ("lever", "knob", "pull"):
        return []
    k = 0.7 if small else 1.0

    def C(d0, d1):                       # out of the face, sorted
        a, b = c_face + side * d0, c_face + side * d1
        return min(a, b), max(a, b)
    out = []
    if kind == "lever":
        r0, r1 = C(-0.001, 0.008 * k)
        out += F(s - 0.016 * k, s + 0.016 * k, r0, r1, zh - 0.07 * k,
                 zh + 0.07 * k, color)
        b0, b1 = C(0.007 * k, 0.022 * k)
        out += F(s - 0.13 * k, s + 0.012 * k, b0, b1, zh - 0.009 * k,
                 zh + 0.009 * k, color)
    elif kind == "knob":
        r = 0.028
        pts = [(s + r * math.cos(math.pi * j / 4 + math.pi / 8),
                zh + r * math.sin(math.pi * j / 4 + math.pi / 8))
               for j in range(8)]
        c0, c1 = C(-0.001, 0.055)
        out += _sz_prism(F.p0, F.u, F.n, pts, c0, c1, color)
    else:                                   # a pull bar on two posts
        hh = 0.20 if not small else 0.12
        for z in (zh - hh + 0.03, zh + hh - 0.03):
            p0, p1 = C(-0.001, 0.041)
            out += F(s - 0.006, s + 0.006, p0, p1, z - 0.006, z + 0.006,
                     color)
        b0, b1 = C(0.040, 0.058)
        out += F(s - 0.0125, s + 0.0125, b0, b1, zh - hh, zh + hh, color)
    return out


def leaf(F, a, b, c0, c1, za, zb, style: str, color, glass_color) -> list:
    """A door's SOLID leaf a..b × c0..c1 × za..zb in frame ``F``: plain (a
    box), PANELS (raised 4 mm on each face, 1 mm into the leaf — 2 rows, 1
    or 2 columns) or HALF glass (the top half a glass pane in a timber
    frame)."""
    if style == "half":
        H, m = zb - za, min(0.12, (b - a) / 4)
        g0, g1 = za + H * 0.48, zb - m
        cm = (c0 + c1) / 2
        return (F(a, b, c0, c1, za, g0, color)
                + F(a, b, c0, c1, g1, zb, color)
                + F(a, a + m, c0, c1, g0, g1, color)
                + F(b - m, b, c0, c1, g0, g1, color)
                + F(a + m - 0.005, b - m + 0.005, cm - 0.004, cm + 0.004,
                    g0 - 0.005, g1 + 0.005, glass_color))
    out = F(a, b, c0, c1, za, zb, color)
    if style != "panels":
        return out
    W, H = b - a, zb - za
    m = min(0.11, W / 5)
    cols = 2 if W > 0.70 else 1
    pw = (W - m * (cols + 1)) / cols
    mid = za + H * 0.42                     # the lock rail
    rows = ((za + m * 1.6, mid - m / 2), (mid + m / 2, zb - m))
    for i in range(cols):
        s0 = a + m + i * (pw + m)
        for z0, z1 in rows:
            out += F(s0, s0 + pw, c1 - 0.001, c1 + 0.004, z0, z1, color)
            out += F(s0, s0 + pw, c0 - 0.004, c0 + 0.001, z0, z1, color)
    return out


def pivot_panes(o, p0, u, n, a, b, za, zb, out_sign: float, opn: float,
                frame_color, glass_color) -> list:
    """A PIVOT window (basculante): horizontal panes, each turning on a
    horizontal axis at its middle — its bottom out — up to 60°. Each: a
    slim bar top and bottom, the glass between (1 mm into them)."""
    from .structure import _mbox
    H = zb - za
    k = pivot_count(o) or min(max(round(H / 0.28), 2), 8)
    ph = H / k
    th = opn * math.radians(60)
    bar, d = min(0.02, ph / 5), 0.012
    out = []
    for i in range(k):
        zc = za + ph * (i + 0.5)

        def M(s, c, t, zc=zc):
            # t up the pane from its axis; c across; turned about the axis
            cc = c * math.cos(th) - t * math.sin(th) * out_sign
            zz = zc + t * math.cos(th) + c * math.sin(th) * out_sign
            return (p0[0] + u[0] * s + n[0] * cc, p0[1] + u[1] * s + n[1] * cc,
                    zz)
        h = ph / 2 - 0.003
        out += _mbox(M, a, b, -d, d, h - bar, h, frame_color)
        out += _mbox(M, a, b, -d, d, -h, -h + bar, frame_color)
        out += _mbox(M, a + 0.003, b - 0.003, -0.003, 0.003, -h + bar - 0.001,
                     h - bar + 0.001, glass_color)
    return out


#: a louvred sliding window: its 3 tracks (y: + = OUT), leaf depth
TRACKS = {"A": (0.0125, 0.0315), "B": (-0.0095, 0.0095),
          "C": (-0.0315, -0.0125)}
SLAT_W, SLAT_T, SLAT_TILT, SLAT_STEP = 0.045, 0.003, math.radians(20), 0.04


def _louvred(p0, u, n, out_sign, a, b, y0, y1, za, zb, color) -> list:
    """A louvred leaf: its frame (stiles, rails) and slats tilted 20°, 4 cm
    apart, overlapping 2 mm (closed, as on site) — each slat's ends 1 mm in
    the stiles. The leaf's whole depth y0..y1 (out from the wall's middle)."""
    from .structure import _box, _mbox, ALU
    f = min(ALU, (b - a) / 4, (zb - za) / 6)
    c0, c1 = sorted((out_sign * y0, out_sign * y1))
    out = (_box(p0, u, n, a, a + f, c0, c1, za, zb, color)
           + _box(p0, u, n, b - f, b, c0, c1, za, zb, color)
           + _box(p0, u, n, a + f, b - f, c0, c1, za, za + f, color)
           + _box(p0, u, n, a + f, b - f, c0, c1, zb - f, zb, color))
    ym = (y0 + y1) / 2
    lo, hi = za + f, zb - f
    k = max(1, int((hi - lo) / SLAT_STEP))
    step = (hi - lo) / k
    cs, sn = math.cos(SLAT_TILT), math.sin(SLAT_TILT)
    for j in range(k):
        zc = lo + step * (j + 0.5)

        def M(s, w, t, zc=zc):
            # w across the slat's width (up, tilted: its top leans IN), t
            # its thickness
            yy = ym - w * sn + t * cs
            zz = zc + w * cs + t * sn
            cc = out_sign * yy
            return (p0[0] + u[0] * s + n[0] * cc, p0[1] + u[1] * s + n[1] * cc,
                    zz)
        out += _mbox(M, a + f - 0.001, b - f + 0.001, -SLAT_W / 2, SLAT_W / 2,
                     -SLAT_T / 2, SLAT_T / 2, color)
    return out


def louvred_window(o, p0, u, n, out_sign: float, a, b, za, zb, opn: float,
                   frame_color) -> list:
    """A SLIDING window with LOUVRES (the Brazilian veneziana): 3 leaves —
    2 louvred outside, 1 glass inside — or 6 (4 + 2). Open: the louvres
    slide over each other (3: the right one left; 6: the middle two out),
    the glass stays closed behind."""
    from .structure import _leaf
    lap, gap = 0.05, 0.0015
    six = int(o.get("leaves") or 3) >= 6
    out = []

    def gl(sa, sb):
        c0, c1 = sorted((out_sign * TRACKS["C"][0], out_sign * TRACKS["C"][1]))
        return _leaf(p0, u, n, sa, sb, c0, c1, za, zb, True, frame_color)
    m = (a + b) / 2
    if not six:
        run = (m - a) * opn
        out += _louvred(p0, u, n, out_sign, a, m + lap, *TRACKS["B"], za, zb,
                        frame_color)
        out += _louvred(p0, u, n, out_sign, m - lap - run, b - run,
                        *TRACKS["A"], za, zb, frame_color)
        out += gl(m - lap, b)
        return out
    q = (b - a) / 4
    run = q * opn
    out += _louvred(p0, u, n, out_sign, a, a + q + lap, *TRACKS["B"], za, zb,
                    frame_color)
    out += _louvred(p0, u, n, out_sign, b - q - lap, b, *TRACKS["B"], za, zb,
                    frame_color)
    out += _louvred(p0, u, n, out_sign, a + q - lap - run, m - gap - run,
                    *TRACKS["A"], za, zb, frame_color)
    out += _louvred(p0, u, n, out_sign, m + gap + run, b - q + lap + run,
                    *TRACKS["A"], za, zb, frame_color)
    out += gl(a, m - gap) + gl(m + gap, b)
    return out
