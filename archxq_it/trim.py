# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""TRIM and SILL round doors and windows (his ask, 2026-10-17 / 2026-10-19:
«janela e porta com contorno» — the façades' finish, much seen in renders).

- **Trim** (``trim``): a raised moulding round the opening — on the wall's
  OUTSIDE face, or on both faces. ``trim_w``: its face width; ``trim_d``:
  how far it stands out of the wall. Round a window it goes all round (on
  the sill when there is one); round a door, down to the floor.
- **Sill** (``sill_k`` = "stone", windows): the stone under the window,
  from the frame out past the wall's face (``sill_d``), ``sill_t`` thick,
  ``sill_x`` past the opening on each side — as on site. With a trim
  outside, both are counted from the trim (the sill runs past it).

Each part has a colour of its own (``TRIM_COLOR``, ``SILL_COLOR``): the
materials tell the parts apart by it (``part_of_color``), so each takes a
material of its own (the window's «Material» tab).

Pure geometry — the faces are built with ``structure._box`` on the wall's
centre line (the opening's frame).
"""
from __future__ import annotations

#: the record's keys and their defaults (none: an opening as before)
DEFAULTS = {"trim": "none", "trim_w": 0.08, "trim_d": 0.03,
            "sill_k": "none", "sill_d": 0.04, "sill_t": 0.03, "sill_x": 0.03}
TRIMS = ("none", "out", "both")
SILLS = ("none", "stone")
#: (min, max) of each measure, metres
LIMITS = {"trim_w": (0.02, 0.40), "trim_d": (0.005, 0.15),
          "sill_d": (0.0, 0.20), "sill_t": (0.01, 0.12),
          "sill_x": (0.0, 0.20)}
TRIM_COLOR = (0.97, 0.97, 0.96, 1.0)      # a white moulding
SILL_COLOR = (0.20, 0.20, 0.21, 1.0)      # dark granite
GAP = 0.001             # m: into the wall / over the sill (no shared face)
OVERLAP = 0.01          # m: a door's trim over its lining's edge


def keys_of(o: dict, kind: str) -> dict:
    """The trim / sill keys of a record, clean — ``{}`` when it has none
    (an opening as before: nothing stored)."""
    t = o.get("trim") if o.get("trim") in TRIMS else "none"
    s = o.get("sill_k") if o.get("sill_k") in SILLS else "none"
    if not sill_ok(o, kind):
        s = "none"                         # a sill: plain windows only
    if t == "none" and s == "none":
        return {}
    out = {"trim": t, "sill_k": s}
    for k, (lo, hi) in LIMITS.items():
        try:
            v = float(o.get(k, DEFAULTS[k]))
        except (TypeError, ValueError):
            v = DEFAULTS[k]
        out[k] = round(min(max(v, lo), hi), 4)
    return out


def own_sill(o: dict) -> float:
    """Its sill over ITS floor — a raised wall's lift (walls.lifted) taken
    off: an Opening on a raised floor is still on the floor."""
    try:
        return float(o.get("sill", 0.0) or 0.0) - float(o.get("_lift", 0.0))
    except (TypeError, ValueError):
        return 0.0


def sill_ok(o: dict, kind: str) -> bool:
    """A stone sill: under a plain window — and under an Opening (a void)
    off the floor, a grid's window or a cobogó (his ask, 2026-10-28)."""
    if kind == "void":
        return own_sill(o) > 1e-6
    return kind == "window" and o.get("op") != "shop"


#: a GRID's library edits its host's trim and sill (the Opening or the
#: window it fills — the trim is the hole's): its options' keys → the
#: host's (2026-10-28)
HOST = {"op_trim": "trim", "op_trim_w": "trim_w", "op_trim_d": "trim_d",
        "op_sill_k": "sill_k", "op_sill_d": "sill_d", "op_sill_t": "sill_t",
        "op_sill_x": "sill_x"}


def host_opts(o: dict) -> dict:
    """A host opening's trim / sill as a grid's options (``HOST``)."""
    k = dict(DEFAULTS, **keys_of(o, o.get("kind", "")))
    return {gk: k[hk] for gk, hk in HOST.items()}


def on_host(o: dict, changes: dict) -> dict:
    """Opening ``o`` with a grid's trim / sill ``changes`` (``HOST`` keys)
    — clean: none set, no key kept."""
    k = dict(DEFAULTS, **keys_of(o, o.get("kind", "")))
    k.update({HOST[gk]: v for gk, v in changes.items() if gk in HOST})
    out = {key: v for key, v in o.items() if key not in DEFAULTS}
    out.update(keys_of(dict(out, **k), o.get("kind", "")))
    return out


def part_of_color(color) -> str:
    """An opening face's part, by the colour it was built with: «trim»,
    «sill», «glass» (see-through, or the glass colour), «leaf» (a door's
    wooden leaf) or «frame» (everything else — frames, glazed leaves'
    frames, a garage door's panels)."""
    from . import structure as S
    c = tuple(round(v, 3) for v in (color or (0, 0, 0))[:3])
    if c == tuple(round(v, 3) for v in TRIM_COLOR[:3]):
        return "trim"
    if c == tuple(round(v, 3) for v in SILL_COLOR[:3]):
        return "sill"
    if color is not None and len(color) > 3 and color[3] < 1.0 or \
            c == tuple(round(v, 3) for v in S.GLASS_COLOR[:3]):
        return "glass"
    if c == tuple(round(v, 3) for v in S.LEAF_COLOR[:3]):
        return "leaf"
    # a white / grey / black leaf, a handle (openfinish.py, 2026-10-27)
    from .openfinish import part_of_color as finish_part
    return finish_part(color) or "frame"


def parts(o: dict, seg, z0: float, wall: dict | None,
          top: float | None = None) -> list:
    """The trim's and the sill's faces of opening ``o`` (in a straight
    wall's segment ``seg``, its floor at ``z0``; ``top``: the wall's, for
    an arch) — [] for none."""
    from . import structure as S
    k = keys_of(o, o.get("kind", ""))
    if not k or wall is None or wall.get("cw"):
        return []
    arc = S.door_arch(o, z0, top)
    if arc is not None:
        return _arch_trim(k, seg, z0 + float(o.get("_lift", 0.0)), wall,
                          arc)                 # its jambs from ITS floor
    from . import shapes as SH
    loop = SH.outline(o, z0)
    if loop is not None:
        return _shaped_trim(k, o, seg, wall, loop)
    p0, u = seg.p0, seg.u
    n = (-u[1], u[0])
    t = float(wall.get("t", 0.2))
    inside = 1.0 if float(wall.get("side", 1)) >= 0 else -1.0
    s0, s1 = o["pos"] - o["w"] / 2, o["pos"] + o["w"] / 2
    zs = z0 + float(o.get("sill", 0.0))
    zt = zs + float(o["h"])
    is_win = o.get("kind") == "window" or (o.get("kind") == "void"
                                           and own_sill(o) > 0)
    stone = k["sill_k"] == "stone"
    out = []

    def box(sa, sb, ca, cb, za, zb, color):
        if sb - sa < 1e-4 or zb - za < 1e-4:
            return
        out.extend(S._box(p0, u, n, sa, sb, min(ca, cb), max(ca, cb), za, zb,
                          color))
    # ---- the sill: from the frame out past the outer face ----------------
    # (with a trim outside: past the TRIM — its ends and its face; the trim
    # stood past a narrower sill, his test window 2026-10-19)
    if stone:
        hd = S.FRAME_DEPTH / 2
        trimmed = k["trim"] != "none"
        xw = k["trim_w"] if trimmed else 0.0
        xd = k["trim_d"] if trimmed else 0.0
        c_frame = -inside * hd               # the frame's outer face
        c_out = -inside * (t / 2 + xd + k["sill_d"])
        box(s0 - xw - k["sill_x"], s1 + xw + k["sill_x"], c_frame, c_out,
            zs - k["sill_t"], zs + GAP, SILL_COLOR)
    # ---- the trim: on the outer face (and the inner one) ------------------
    if k["trim"] != "none":
        tw, td = k["trim_w"], k["trim_d"]
        # a door's trim laps OVER its lining's edge (the frame lines the
        # whole wall: structure.door_lined) — no joint left in sight
        ov = OVERLAP if S.door_lined(o, wall) else 0.0
        faces = [-inside] + ([inside] if k["trim"] == "both" else [])
        for side in faces:
            c_face = side * t / 2
            ca = c_face - side * GAP          # 1 mm into the wall
            cb = c_face + side * td           # out of it
            outside = side == -inside
            if not is_win:                    # a door: down to ITS floor
                zb = z0 + float(o.get("_lift", 0.0))    # (a raised wall's)
            elif stone and outside:           # on the sill
                zb = zs + GAP
            else:                             # a piece under it too
                zb = zs - tw
                box(s0 - tw, s1 + tw, ca, cb, zb, zs, TRIM_COLOR)
                zb = zs
            box(s0 - tw + ov, s0 + ov, ca, cb, zb, zt + tw - ov,
                TRIM_COLOR)                                        # jambs
            box(s1 - ov, s1 + tw - ov, ca, cb, zb, zt + tw - ov, TRIM_COLOR)
            box(s0 + ov, s1 - ov, ca, cb, zt - ov, zt + tw - ov,
                TRIM_COLOR)                                        # head
    return out


def _shaped_trim(k: dict, o: dict, seg, wall: dict, loop: list) -> list:
    """An opening with a SHAPE (shapes.py, 2026-10-31): its trim a band
    all round its outline — the outline taken OUT by ``tw``, side by side
    with it — on the outer face (and the inner one); its stone sill under
    it as a plain window's, when its foot is a straight side (not a round,
    an oval)."""
    from . import shapes as S2
    from . import structure as S
    p0, u = seg.p0, seg.u
    n = (-u[1], u[0])
    t = float(wall.get("t", 0.2))
    inside = 1.0 if float(wall.get("side", 1)) >= 0 else -1.0
    out = []
    zs = min(z for _s, z in loop)
    flat_foot = S2.shape_of(o) not in ("circle", "oval")
    stone = k["sill_k"] == "stone" and flat_foot
    if stone:
        s0, s1 = o["pos"] - o["w"] / 2, o["pos"] + o["w"] / 2
        trimmed = k["trim"] != "none"
        xw = k["trim_w"] if trimmed else 0.0
        xd = k["trim_d"] if trimmed else 0.0
        ca, cb = sorted((-inside * S.FRAME_DEPTH / 2,
                         -inside * (t / 2 + xd + k["sill_d"])))
        out += S._box(p0, u, n, s0 - xw - k["sill_x"], s1 + xw + k["sill_x"],
                      ca, cb, zs - k["sill_t"], zs + GAP, SILL_COLOR)
    if k["trim"] == "none":
        return out
    tw, td = k["trim_w"], k["trim_d"]
    outer = S2.inset(loop, -tw)
    m = len(loop)
    for side in [-inside] + ([inside] if k["trim"] == "both" else []):
        c_face = side * t / 2
        ca, cb = sorted((c_face - side * GAP, c_face + side * td))
        lo = zs + GAP if stone and side == -inside else None
        for i in range(m):
            j = (i + 1) % m
            quad = [outer[i], outer[j], loop[j], loop[i]]
            if lo is not None:          # on the stone sill: not into it
                quad = S2.clip_above(quad, lo)
                if not quad or abs(S2.area(quad)) < 1e-8:
                    continue
            out += S._sz_prism(p0, u, n, quad, ca, cb, TRIM_COLOR)
    return out


def _arch_trim(k: dict, seg, z0: float, wall: dict, arc) -> list:
    """An ARCHED door's trim (his test, 2026-10-28: «the trim does not
    work on this door»): the jambs from the floor to where the arch
    springs, then a band round the arch — ``tw`` wide, the curve's own
    steps — on the outer face (and the inner one)."""
    from . import structure as S
    if k["trim"] == "none":
        return []
    spring, r, sc = arc
    p0, u = seg.p0, seg.u
    n = (-u[1], u[0])
    t = float(wall.get("t", 0.2))
    inside = 1.0 if float(wall.get("side", 1)) >= 0 else -1.0
    tw, td = k["trim_w"], k["trim_d"]
    s0, s1 = sc - r, sc + r
    out = []
    faces = [-inside] + ([inside] if k["trim"] == "both" else [])
    for side in faces:
        c_face = side * t / 2
        ca, cb = sorted((c_face - side * GAP, c_face + side * td))
        out += S._box(p0, u, n, s0 - tw, s0, ca, cb, z0, spring, TRIM_COLOR)
        out += S._box(p0, u, n, s1, s1 + tw, ca, cb, z0, spring, TRIM_COLOR)
        outer = S.arch_points(spring, r + tw, sc)
        inner = S.arch_points(spring, r, sc)
        for i in range(S.ARCH_STEPS):
            out += S._sz_prism(p0, u, n, [outer[i], outer[i + 1],
                                          inner[i + 1], inner[i]],
                               ca, cb, TRIM_COLOR)
    return out
