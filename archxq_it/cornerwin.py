# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A CORNER WINDOW (janela de canto, 20/11/2026 — a user's ask; his house:
a «C» cut through the corner and two windows did not make it): a window
of its wall that goes on round the corner into the wall joined there.

The record is the window's own, with:

- ``corner``: "a" / "b" — the end of ITS wall it turns at (its wall:
  ``wall``, as any window). Its ``pos`` / ``w`` are its stretch on that
  wall, from its outer jamb to that end of the line drawn.
- ``w2``: how far it runs on the other wall, from that wall's end at the
  corner (default: its own ``w``).
- ``corner_join``: "auto" (default) / "post" / "glass" — what stands at
  the corner: a POST (the frame's), or the two panes meeting glass to
  glass. Glass only for a fixed window (a leaf that opens needs a post to
  close on): asked for another, a post — said nowhere, built right.

Nothing else is stored: the other wall is the one joined at that corner
NOW (``walls.corners`` — a plain L of two straight walls). Unjoined (or
the walls changed so it cannot turn there), it is built as a plain
window on its wall up to 5 cm from that end; joined again, it turns again.

The walls: each gets a hole from the window's jamb on through its end
(the corner piece cut too — as a «C» cut of the Shape editor: the wall
above and below goes on round the corner). Its frame, glass and leaves:
one window on each wall (``structure.opening_parts``), open at the
corner, and the post — or the panes — there.
"""
from __future__ import annotations

ENDS = ("a", "b")
JOINS = ("auto", "post", "glass")
MIN_ARM = 0.30          # m: each of its two parts at least
REACH = 5.0             # m: its hole goes on this far past its wall's end
#: two walls nearer parallel than this (sin of their angle): no corner
SIN_MIN = 0.26
GLASS_HALF = 0.005      # m: half a pane (structure: −0.005 … 0.005)
GAP = 0.001             # m: between two panes (no face on another)


def wanted(o: dict) -> bool:
    """A window that turns a corner (asked: it may not be able to)."""
    return o.get("kind") == "window" and o.get("corner") in ENDS


def keys_of(o: dict, rec: dict) -> dict:
    """The corner keys of a file's record, clean (``model._openings``) —
    ``{}`` for a window that doesn't turn a corner (nothing stored)."""
    if rec.get("kind") != "window" or o.get("corner") not in ENDS:
        return {}
    if why_not_window(rec) is not None:
        return {}
    try:
        w2 = float(o.get("w2", rec["w"]))
    except (TypeError, ValueError):
        w2 = float(rec["w"])
    out = {"corner": o["corner"], "w2": round(min(max(w2, 0.2), 20.0), 6)}
    if o.get("corner_join") in ("post", "glass"):
        out["corner_join"] = o["corner_join"]
    return out


def why_not_window(o: dict) -> str | None:
    """Why this window cannot turn a corner (None: it can)."""
    from . import shapes as SH
    if o.get("op") == "shop":
        return "A shop window doesn't turn a corner"
    if SH.outline(o, 0.0) is not None:
        return "A window with a shape doesn't turn a corner"
    return None


def why_not_wall(w: dict | None) -> str | None:
    """Why a window cannot turn a corner in this wall."""
    from . import wallshape as WS
    if w is None:
        return "No wall joined at that end"
    if w.get("kind", "line") != "line":
        return "Corner windows: straight walls only"
    if w.get("cw") or WS.top_only(w):
        return ("Corner windows: not in a curtain, grid, clad or "
                "light-framed wall")
    return None


def join_of(o: dict) -> str:
    """"post" / "glass": what the corner is built with."""
    from . import structure as S
    j = o.get("corner_join", "auto")
    fixed = o.get("op") not in S.WIN_KINDS
    if j == "glass" or j == "auto":
        return "glass" if fixed else "post"
    return "post"


# ---- the corner, found -------------------------------------------------------------------
def _other(found: list, wid: str, end: str):
    """(other wall id, its end "A"/"B") joined at ``wid``'s ``end``."""
    for c in found:
        if c["a"] == wid and c["a_end"] == end:
            return c["b"], c["b_end"]
        if c["b"] == wid and c["b_end"] == end:
            return c["a"], c["a_end"]
    return None


def _meet(s1, s2):
    """Where two straight segments' lines meet — None: (nearly) parallel."""
    u, v = s1.u, s2.u
    den = u[0] * v[1] - u[1] * v[0]
    if abs(den) < SIN_MIN:
        return None
    dx, dy = s2.p0[0] - s1.p0[0], s2.p0[1] - s1.p0[1]
    t = (dx * v[1] - dy * v[0]) / den
    return (s1.p0[0] + u[0] * t, s1.p0[1] + u[1] * t)


def _s(seg, p) -> float:
    return (p[0] - seg.p0[0]) * seg.u[0] + (p[1] - seg.p0[1]) * seg.u[1]


def straight(o: dict, host: dict) -> dict:
    """The window as a plain one on its wall (its corner can't be built):
    from its outer jamb to 5 cm off that end — the record unchanged."""
    from . import structure as S
    from . import walls as W
    L = W.drawn(host).L
    half = float(o["w"]) / 2
    if o["corner"] == "b":
        a, b = float(o["pos"]) - half, L - S.END_GAP
    else:
        a, b = S.END_GAP, float(o["pos"]) + half
    out = {k: v for k, v in o.items()
           if k not in ("corner", "w2", "corner_join", "_corner")}
    if b - a >= 0.2:
        out.update(pos=round((a + b) / 2, 6), w=round(b - a, 6))
    return out


def resolve(mine: list, found: list, openings: list) -> tuple:
    """({window id: as built — turning (``_corner``) or ``straight``},
    {wall id: [(s0, s1, z_lo, z_hi)…]} — the holes the corner windows cut,
    along each wall's line, heights from the level's floor)."""
    from . import structure as S
    from . import walls as W
    by_id = {w["id"]: w for w in mine}
    ops, holes = {}, {}
    for o in openings:
        if not wanted(o) or o.get("wall") not in by_id:
            continue
        host = by_id[o["wall"]]
        end = o["corner"].upper()
        got = _other(found, host["id"], end)
        other = by_id.get(got[0]) if got else None
        why = (why_not_window(o) or why_not_wall(host)
               or why_not_wall(other))
        corner = None
        if why is None:
            corner = _corner(o, host, other, end, got[1])
        if corner is None:
            ops[o["id"]] = straight(o, host)
            continue
        ops[o["id"]] = dict(o, _corner=corner)
        zl = float(o.get("sill", 0.0)) + W.opening_lift(host)
        zh = zl + float(o["h"])
        for w, s_j, d, L in ((host, corner["s_jh"], corner["dh"],
                              corner["Lh"]),
                             (other, corner["s_jo"], corner["do"],
                              corner["Lo"])):
            span = (s_j, L + REACH) if d > 0 else (-REACH, s_j)
            holes.setdefault(w["id"], []).append(span + (zl, zh))
    return ops, holes


def _corner(o: dict, host: dict, other: dict, end: str, oend: str):
    """The corner's numbers — None: it can't turn there (too short a
    part, the walls too near parallel, its jamb off its wall)."""
    from . import structure as S
    from . import walls as W
    hs, os_ = W.centre(host), W.centre(other)
    K = _meet(hs, os_)
    if K is None:
        return None
    Lh, Lo = W.drawn(host).L, W.drawn(other).L
    dh = 1.0 if end == "B" else -1.0
    do = 1.0 if oend == "B" else -1.0
    half = float(o["w"]) / 2
    s_jh = float(o["pos"]) - half if dh > 0 else float(o["pos"]) + half
    try:
        w2 = float(o.get("w2", o["w"]))
    except (TypeError, ValueError):
        w2 = float(o["w"])
    s_jo = Lo - w2 if do > 0 else w2
    sKh, sKo = _s(hs, K), _s(os_, K)
    if dh * (sKh - s_jh) < MIN_ARM or do * (sKo - s_jo) < MIN_ARM:
        return None
    # its outer jambs ON their walls, 5 cm off the far ends
    for s_j, d, L in ((s_jh, dh, Lh), (s_jo, do, Lo)):
        if (d > 0 and s_j < S.END_GAP - 1e-6) or \
                (d < 0 and s_j > L - S.END_GAP + 1e-6):
            return None
    return {"host": host, "other": other, "dh": dh, "do": do, "K": K,
            "s_jh": s_jh, "s_jo": s_jo, "Lh": Lh, "Lo": Lo}


# ---- for the tools (F2): its ends, its measures, what it runs into ------------------------
#: the pointer this near a wall's joined end (m): a window placed there
#: turns the corner (the library's, ``openingtools``)
SNAP = 0.25


def _level_walls(doc: dict, wall: dict) -> list:
    return [w for w in doc.get("walls") or []
            if w.get("level") == wall.get("level")]


def _outer(host: dict, other: dict, end: str, oend: str):
    """(eh, eo): how far the corner's OUTSIDE is past each wall's line
    drawn, along it — its measures are shown to the outside corner, the
    record keeps them to the line (None: the walls nearly in line)."""
    from . import walls as W
    hs, os_ = W.centre(host), W.centre(other)
    if _meet(hs, os_) is None:
        return None
    dh = 1.0 if end == "B" else -1.0
    do = 1.0 if oend == "B" else -1.0
    away_o = (-do * os_.u[0], -do * os_.u[1])   # along the other, away
    away_h = (-dh * hs.u[0], -dh * hs.u[1])
    nh = (-hs.u[1], hs.u[0])
    no = (-os_.u[1], os_.u[0])
    # each wall's face AWAY from the other wall
    ch = (-1.0 if nh[0] * away_o[0] + nh[1] * away_o[1] > 0 else 1.0) \
        * float(host.get("t", 0.2)) / 2
    co = (-1.0 if no[0] * away_h[0] + no[1] * away_h[1] > 0 else 1.0) \
        * float(other.get("t", 0.2)) / 2
    sh = _cross_at(hs, ch, os_, co)
    so = _cross_at(os_, co, hs, ch)
    Lh, Lo = W.drawn(host).L, W.drawn(other).L
    return (dh * (sh - (Lh if dh > 0 else 0.0)),
            do * (so - (Lo if do > 0 else 0.0)))


def ends_info(doc: dict, wall: dict) -> dict:
    """{"a" / "b": {"other": wall, "oend": "A"/"B", "eh": m, "eo": m} — or
    {"why": why not}} — what each end of ``wall`` offers a corner window:
    the wall joined there, and how far the outside corner is past each
    one's line (``_outer``)."""
    from . import walls as W
    why = why_not_wall(wall)
    found = W.corners(_level_walls(doc, wall))[1] if why is None else []
    by_id = {w["id"]: w for w in doc.get("walls") or []}
    out = {}
    for end in ENDS:
        got = _other(found, wall["id"], end.upper()) if why is None else None
        other = by_id.get(got[0]) if got else None
        w_why = why or why_not_wall(other)
        ex = None
        if w_why is None:
            ex = _outer(wall, other, end.upper(), got[1])
            if ex is None:
                w_why = "Those two walls are nearly in line"
        out[end] = {"why": w_why} if w_why else {
            "other": other, "oend": got[1], "eh": ex[0], "eo": ex[1]}
    return out


def stored(o: dict, wall: dict, end: str, info: dict, w_out: float,
           w2_out: float) -> dict:
    """``o`` turning at ``end``: its width ``w_out`` on its wall and
    ``w2_out`` on the other, both to the OUTSIDE corner — as kept (to the
    lines drawn: ``info`` = ``ends_info``'s for that end)."""
    from . import walls as W
    L = W.drawn(wall).L
    w = max(round(w_out - info["eh"], 4), 0.2)
    return dict(o, corner=end, w=w,
                pos=round(L - w / 2 if end == "b" else w / 2, 4),
                w2=max(round(w2_out - info["eo"], 4), 0.2))


def plain(o: dict, wall: dict) -> dict:
    """``o`` no longer turning: a plain window, as wide, on its wall —
    5 cm off that end."""
    from . import structure as S
    from . import walls as W
    out = {k: v for k, v in o.items()
           if k not in ("corner", "w2", "corner_join", "_corner")}
    if o.get("corner") not in ENDS:
        return out
    L = W.drawn(wall).L
    w = min(float(o["w"]), max(L - 2 * S.END_GAP, 0.2))
    pos = L - S.END_GAP - w / 2 if o["corner"] == "b" else S.END_GAP + w / 2
    return dict(out, w=round(w, 4), pos=round(pos, 4))


def _arm(o: dict, c: dict) -> dict:
    """The corner window's part on the OTHER wall, as an opening of it (up
    to its end at the corner)."""
    s_jo, Lo, do = c["s_jo"], c["Lo"], c["do"]
    a, b = (s_jo, Lo) if do > 0 else (0.0, s_jo)
    return {"kind": "window", "wall": c["other"]["id"], "id": o.get("id"),
            "pos": (a + b) / 2, "w": b - a, "h": o["h"],
            "sill": o.get("sill", 0.0), "corner": "b" if do > 0 else "a"}


def _built(doc: dict, o: dict, ops: list):
    """(``resolve``'s windows of ``o``'s level — ``ops`` among them —,
    ``o``'s wall); (None, None) when its wall is gone."""
    from . import walls as W
    host = next((w for w in doc.get("walls") or []
                 if w["id"] == o.get("wall")), None)
    if host is None:
        return None, None
    mine = _level_walls(doc, host)
    ids = {w["id"] for w in mine}
    lv = [p for p in ops if p.get("wall") in ids]
    built, _h = resolve(mine, W.corners(mine)[1], lv)
    return built, host


def clash(doc: dict, o: dict, height) -> str | None:
    """Why ``o`` can't be there for a corner window's sake (None: it can):
    a corner window that can't turn its corner, or its part on the other
    wall into that wall's openings / over its top; any opening into a
    corner window's part coming round from another wall. ``height(wall)``:
    how high a wall stands (``opening_room``'s)."""
    from . import structure as S
    ops = [p for p in doc.get("openings") or []
           if p.get("id") != o.get("id")]
    if not wanted(o) and not any(wanted(p) for p in ops):
        return None
    me = dict(o, id=o.get("id") or "_new")
    built, host = _built(doc, me, ops + [me])
    if built is None:
        return None
    mine = [me]                          # its stretches: on its wall…
    if wanted(me):
        c = built.get(me["id"], {}).get("_corner")
        if c is None:
            info = ends_info(doc, host).get(me["corner"], {})
            return (why_not_window(me) or info.get("why")
                    or "Too short to turn the corner (each part 30 cm at "
                       "least)")
        other = c["other"]
        arm = _arm(me, c)
        why = S.opening_room(arm, other, ops, height(other))
        if why:
            return f"{why} («{other['name']}», round the corner)"
        mine.append(arm)                 # …and round the corner
    for p in ops:                        # the others' parts round corners
        pc = (built.get(p.get("id")) or {}).get("_corner")
        if pc is None:
            continue
        arm = _arm(p, pc)
        for m in mine:
            if arm["wall"] == m["wall"] and abs(
                    arm["pos"] - float(m["pos"])) < \
                    (arm["w"] + float(m["w"])) / 2 + 0.05:
                return (f"It runs into «{p.get('name', 'a window')}», "
                        "turning the corner")
    return None


def walls_of(doc: dict, o: dict) -> set:
    """The walls a window is built in: its own — and, turning a corner,
    the other one (redrawn with it)."""
    out = {o.get("wall")}
    if not wanted(o):
        return out
    host = next((w for w in doc.get("walls") or []
                 if w["id"] == o.get("wall")), None)
    if host is not None:
        info = ends_info(doc, host).get(o["corner"], {})
        if info.get("other") is not None:
            out.add(info["other"]["id"])
    return out


def ghost(walls: list, o: dict) -> list:
    """[(wall, its centre seg, a part as a plain opening record, its end
    at the corner "lo"/"hi")] — a corner window's two parts, each up to
    the OUTSIDE corner (the placing preview, the grips). [] when it can't
    turn there."""
    from . import walls as W
    doc = {"walls": walls}
    me = dict(o, id=o.get("id") or "_new")
    built, host = _built(doc, me, [me])
    c = (built or {}).get(me["id"], {}).get("_corner")
    if c is None:
        return []
    info = ends_info(doc, host).get(me["corner"], {})
    eh, eo = info.get("eh", 0.0), info.get("eo", 0.0)
    out = []
    for w, s_j, d, L, ex in ((host, c["s_jh"], c["dh"], c["Lh"], eh),
                             (c["other"], c["s_jo"], c["do"], c["Lo"], eo)):
        end = L + ex if d > 0 else -ex
        a, b = sorted((s_j, end))
        rec = {k: v for k, v in me.items()
               if k not in ("corner", "w2", "corner_join", "_corner")}
        rec.update(wall=w["id"], pos=(a + b) / 2, w=b - a)
        out.append((w, W.centre(w), rec, "hi" if d > 0 else "lo"))
    return out


# ---- its frame, glass and leaves ------------------------------------------------------------
def _inside(w: dict) -> float:
    return 1.0 if float(w.get("side", 1)) >= 0 else -1.0


def _map(c: float, frm: dict, to: dict) -> float:
    """An offset across wall ``frm`` (from its centre) as the same place
    across wall ``to``: on the same side (inside / outside); out at a face
    (a trim, a sill's nose) as far out of ITS face."""
    k = _inside(to) / _inside(frm)
    tf, tt = float(frm.get("t", 0.2)) / 2, float(to.get("t", 0.2)) / 2
    if abs(c) >= tf - 0.0015:
        sign = 1.0 if c >= 0 else -1.0
        return k * sign * (abs(c) - tf + tt)
    return k * c


def _cross_at(seg, c_self: float, oseg, c_other: float) -> float:
    """s along ``seg``'s line offset ``c_self`` where it meets ``oseg``'s
    line offset ``c_other`` (offsets to each one's left)."""
    n = (-seg.u[1], seg.u[0])
    m = (-oseg.u[1], oseg.u[0])
    p = (seg.p0[0] + n[0] * c_self, seg.p0[1] + n[1] * c_self)
    den = seg.u[0] * m[0] + seg.u[1] * m[1]
    return (c_other - ((p[0] - oseg.p0[0]) * m[0]
                       + (p[1] - oseg.p0[1]) * m[1])) / den


def _ends(me: dict, seg, d: float, you: dict, oseg, far: bool):
    """``ext(ca, cb)``: where a band of this part (offsets ca…cb across
    its wall) ends at the corner — ``far``: past the other part's same band
    (the part that runs on over the corner), else short of it (the one
    that stops against it)."""
    def ext(ca: float, cb: float) -> float:
        mid = (ca + cb) / 2
        # the other part's same band, its two edges
        ss = [d * _cross_at(seg, mid, oseg, _map(c, me, you))
              for c in (ca, cb)]
        return d * (max(ss) if far else min(ss))
    return ext


def parts(o: dict, z0: float, top: float | None = None) -> list:
    """The corner window's faces: its two parts and its corner."""
    from . import structure as S
    from . import walls as W
    c = o["_corner"]
    host, other = c["host"], c["other"]
    hs, os_ = W.centre(host), W.centre(other)
    dh, do = c["dh"], c["do"]
    joint = join_of(o)
    hd = S.FRAME_DEPTH / 2
    run_h = _ends(host, hs, dh, other, os_, far=True)
    near_h = _ends(host, hs, dh, other, os_, far=False)
    stop_o = _ends(other, os_, do, host, hs, far=False)
    out = []
    zs = z0 + float(o.get("sill", 0.0))
    zt = zs + float(o["h"])
    if joint == "post":
        p_lo, p_hi = near_h(-hd, hd), run_h(-hd, hd)
        end_h = p_lo
        out += S._box(hs.p0, hs.u, (-hs.u[1], hs.u[0]), min(p_lo, p_hi),
                      max(p_lo, p_hi), -hd, hd, zs, zt,
                      _frame_rgb(o))
        pane_h = None
        pane_o = None
    else:
        end_h = run_h(-hd, hd)
        pane_h = run_h(-GLASS_HALF, GLASS_HALF)
        pane_o = stop_o(-GLASS_HALF, GLASS_HALF) - do * GAP
    end_o = stop_o(-hd, hd)
    keep = ("corner", "w2", "corner_join", "_corner")
    base = {k: v for k, v in o.items() if k not in keep}
    for w, seg, d, s_j, s_end, pane, ext in (
            (host, hs, dh, c["s_jh"], end_h, pane_h, run_h),
            (other, os_, do, c["s_jo"], end_o, pane_o, stop_o)):
        a, b = sorted((s_j, s_end))
        arm = dict(base, wall=w["id"], pos=(a + b) / 2, w=b - a,
                   _open_end="hi" if d > 0 else "lo", _ext=ext)
        if pane is not None:
            arm["_pane_end"] = pane
        out += S.opening_parts(arm, seg, z0, w, top)
    return out


def _frame_rgb(o: dict):
    from . import structure as S
    from .openfinish import frame_rgb
    return frame_rgb(o, S.FRAME_COLOR)


# ---- for what reads openings wall by wall (F3) ---------------------------------------------
def split(walls: list, openings: list, outside: bool = False) -> list:
    """The openings as the walls hold them: a corner window that turns now
    as its TWO parts — on its wall (as kept) and on the other one
    (``_arm``), each up to its wall's end at the corner, ``_part_of`` its
    id, ``_out`` = (its end at the corner "lo"/"hi", how far the corner's
    outside is past it); ``outside``: each part on up to there (what is
    SEEN: a dimension chain, an elevation). One that can't turn now: as
    built (``straight``); the others as they are. For what reads openings
    wall by wall: a wall's area less its holes, the dimension chains."""
    if not any(wanted(o) for o in openings):
        return list(openings)
    from . import walls as W
    out, by_lv = [], {}
    for o in openings:
        host = next((w for w in walls if w["id"] == o.get("wall")), None) \
            if wanted(o) else None
        if host is None:
            out.append(o)
            continue
        lid = host.get("level")
        if lid not in by_lv:
            mine = [w for w in walls if w.get("level") == lid]
            by_lv[lid] = (mine, W.corners(mine)[1])
        mine, found = by_lv[lid]
        built, _h = resolve(mine, found, [o])
        b = built.get(o["id"], o)
        c = b.get("_corner")
        if c is None:
            out.append(b)
            continue
        keep = {k: v for k, v in o.items() if k not in ("w2", "corner_join")}
        ex = _outer(c["host"], c["other"], "B" if c["dh"] > 0 else "A",
                    "B" if c["do"] > 0 else "A") or (0.0, 0.0)
        for rec, d, e in ((dict(keep), c["dh"], ex[0]),
                          (dict(keep, **dict(_arm(o, c),
                                             id=f"{o['id']}~2")),
                           c["do"], ex[1])):
            side = "hi" if d > 0 else "lo"
            rec.update(_part_of=o["id"], _out=(side, e))
            if outside:
                rec.update(w=float(rec["w"]) + e,
                           pos=float(rec["pos"]) + (e / 2 if side == "hi"
                                                    else -e / 2))
            out.append(rec)
    return out


def sizes(walls: list, o: dict):
    """(its width on its wall, on the other) to the corner's OUTSIDE — the
    measures a schedule writes («1.50 + 1.20 × 1.20»); None: not a corner
    window that turns now."""
    if not wanted(o):
        return None
    g = ghost(walls, o)
    return (g[0][2]["w"], g[1][2]["w"]) if len(g) == 2 else None
