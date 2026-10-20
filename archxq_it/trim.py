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


def keys_of(o: dict, kind: str) -> dict:
    """The trim / sill keys of a record, clean — ``{}`` when it has none
    (an opening as before: nothing stored)."""
    t = o.get("trim") if o.get("trim") in TRIMS else "none"
    s = o.get("sill_k") if o.get("sill_k") in SILLS else "none"
    if kind != "window" or o.get("op") == "shop":
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
    return "frame"


def parts(o: dict, seg, z0: float, wall: dict | None) -> list:
    """The trim's and the sill's faces of opening ``o`` (in a straight
    wall's segment ``seg``, its floor at ``z0``) — [] for none."""
    from . import structure as S
    k = keys_of(o, o.get("kind", ""))
    if not k or wall is None or wall.get("cw"):
        return []
    p0, u = seg.p0, seg.u
    n = (-u[1], u[0])
    t = float(wall.get("t", 0.2))
    inside = 1.0 if float(wall.get("side", 1)) >= 0 else -1.0
    s0, s1 = o["pos"] - o["w"] / 2, o["pos"] + o["w"] / 2
    zs = z0 + float(o.get("sill", 0.0))
    zt = zs + float(o["h"])
    is_win = o.get("kind") == "window" or (o.get("kind") == "void"
                                           and float(o.get("sill", 0)) > 0)
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
        faces = [-inside] + ([inside] if k["trim"] == "both" else [])
        for side in faces:
            c_face = side * t / 2
            ca = c_face - side * GAP          # 1 mm into the wall
            cb = c_face + side * td           # out of it
            outside = side == -inside
            if not is_win:                    # a door: down to the floor
                zb = z0
            elif stone and outside:           # on the sill
                zb = zs + GAP
            else:                             # a piece under it too
                zb = zs - tw
                box(s0 - tw, s1 + tw, ca, cb, zb, zs, TRIM_COLOR)
                zb = zs
            box(s0 - tw, s0, ca, cb, zb, zt + tw, TRIM_COLOR)      # jambs
            box(s1, s1 + tw, ca, cb, zb, zt + tw, TRIM_COLOR)
            box(s0, s1, ca, cb, zt, zt + tw, TRIM_COLOR)           # head
    return out
