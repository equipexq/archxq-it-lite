# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A slab's outline with ARCS and ROUNDED CORNERS (PLANO_CURVAS_E_FORMAS.md,
F1 — promised to a customer on 2026-11-13: «a C with a curved corner»).

The record keeps, besides its ``corners``:
    ``ctrl``   — the control corners, the ones the user clicked;
    ``curves`` — {"r": {i: radius at corner i},
                  "arc": {i: sagitta of the side i → i+1}}
                 (the sagitta signed: + bulges to the LEFT of i → i+1).
``corners`` stays THE FINAL POLYGON — every curve in fine steps (the chord
never more than 1 mm off the arc) — so the 29 modules reading ``corners``
are unchanged, and a slab without ``ctrl`` is today's, byte for byte.
``expand`` is called when the slab is saved or edited, never when read.
Areas and lengths come from ``ctrl`` + ``curves``, exactly (circular
sectors and segments), never from the fine polygon.

Pure: no host, no Qt."""
from __future__ import annotations

import math

TOL = 0.001            # the chord's largest distance off its arc (1 mm)
MAX_STEPS = 720        # steps in one arc, at most
EPS = 1e-9


# ---- the data ------------------------------------------------------------------------
def _key(d: dict, i: int):
    """d's value for corner / side i (JSON turns the keys into text)."""
    if not d:
        return None
    v = d.get(str(i), d.get(i))
    return None if v is None else float(v)


def clean(curves) -> dict:
    """``curves`` as stored: text keys, no zeros, both parts always there."""
    out = {"r": {}, "arc": {}}
    for part in ("r", "arc"):
        for k, v in ((curves or {}).get(part) or {}).items():
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            if abs(v) > 1e-6:
                out[part][str(int(k))] = round(v, 4)
    return out


def is_curved(rec: dict) -> bool:
    """The record has curves (a radius or an arc somewhere)."""
    c = rec.get("curves") or {}
    return bool(rec.get("ctrl")) and bool((c.get("r") or {})
                                          or (c.get("arc") or {}))


# ---- the pieces of the outline ---------------------------------------------------------
def _unit(dx: float, dy: float):
    L = math.hypot(dx, dy)
    return (dx / L, dy / L) if L > EPS else (0.0, 0.0)


def fillet(prev, p, nxt, r: float):
    """The rounded corner at ``p`` (between prev → p → nxt): (tangent point
    on the side coming in, tangent point on the side going out, centre,
    distance from p to each tangent point) — None when there is no corner
    (the sides in a line, or folded back)."""
    u1 = _unit(prev[0] - p[0], prev[1] - p[1])
    u2 = _unit(nxt[0] - p[0], nxt[1] - p[1])
    cosa = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
    a = math.acos(cosa)                     # the angle between the sides
    if a < 1e-4 or a > math.pi - 1e-4:
        return None
    t = r / math.tan(a / 2)
    b = _unit(u1[0] + u2[0], u1[1] + u2[1])
    d = r / math.sin(a / 2)
    t1 = (p[0] + u1[0] * t, p[1] + u1[1] * t)
    t2 = (p[0] + u2[0] * t, p[1] + u2[1] * t)
    c = (p[0] + b[0] * d, p[1] + b[1] * d)
    return t1, t2, c, t


def side_arc(a, b, h: float):
    """The arc from a to b whose middle stands ``h`` off the chord (+ on the
    left of a → b): (centre, radius, signed sweep, counter-clockwise +)."""
    c = math.dist(a, b)
    s = c / 2
    if s < EPS or abs(h) < EPS:
        return None
    R = (s * s + h * h) / (2 * abs(h))
    ux, uy = (b[0] - a[0]) / c, (b[1] - a[1]) / c
    nx, ny = -uy, ux                        # the left of a → b
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    k = h - math.copysign(R, h)             # the centre, along the normal
    centre = (mx + nx * k, my + ny * k)
    sweep = 4 * math.atan(abs(h) / s)
    # bulging left of a → b, the arc turns clockwise about its centre
    return centre, R, (-sweep if h > 0 else sweep)


def _sweep_short(c, p, q) -> float:
    """The signed sweep about c from p to q, the short way."""
    a0 = math.atan2(p[1] - c[1], p[0] - c[0])
    a1 = math.atan2(q[1] - c[1], q[0] - c[0])
    d = (a1 - a0) % (2 * math.pi)
    return d - 2 * math.pi if d > math.pi else d


def steps(R: float, sweep: float, tol: float = TOL) -> int:
    if R <= tol:
        return 1
    da = 2 * math.acos(max(-1.0, 1.0 - tol / R))
    return max(2, min(MAX_STEPS, math.ceil(abs(sweep) / da)))


def _arc_pts(c, R: float, start, sweep: float, tol: float = TOL) -> list:
    """The points strictly between the arc's two ends — a hair OUTSIDE the
    circle (at ρ = R·√(2φ / sin 2φ), 2φ a step), so the fine polygon holds
    the arc's own area (points on the circle lose ⅔ of a mm along all of
    it), every point and every chord's middle still under 1 mm off it."""
    a0 = math.atan2(start[1] - c[1], start[0] - c[0])
    n = steps(R, sweep, tol)
    st = abs(sweep) / n
    rho = R * math.sqrt(st / math.sin(st)) if st > 1e-9 else R
    return [(c[0] + rho * math.cos(a0 + sweep * k / n),
             c[1] + rho * math.sin(a0 + sweep * k / n)) for k in range(1, n)]


def pieces(ctrl, curves) -> list:
    """The outline as pieces, in order: ("line", p, q) and
    ("arc", p, q, centre, radius, signed sweep). Assumes ``why_not`` is
    None (a radius only between two straight sides)."""
    pts = [(float(p[0]), float(p[1])) for p in ctrl]
    n = len(pts)
    rs = (curves or {}).get("r") or {}
    arcs = (curves or {}).get("arc") or {}
    # where each side starts and ends, after the rounded corners
    start = list(pts)
    end = [pts[(i + 1) % n] for i in range(n)]
    corner = [None] * n
    for i in range(n):
        r = _key(rs, i)
        if not r or r <= 0:
            continue
        f = fillet(pts[i - 1], pts[i], pts[(i + 1) % n], r)
        if f is None:
            continue
        t1, t2, c, _t = f
        end[i - 1] = t1                     # the side coming in stops there
        start[i] = t2                       # the side going out starts there
        corner[i] = (t1, t2, c, r)
    out = []
    for i in range(n):
        if corner[i] is not None:
            t1, t2, c, r = corner[i]
            out.append(("arc", t1, t2, c, r, _sweep_short(c, t1, t2)))
        a, b = start[i], end[i]
        h = _key(arcs, i)
        sa = side_arc(a, b, h) if h else None
        if sa is not None:
            c, R, sw = sa
            out.append(("arc", a, b, c, R, sw))
        elif math.dist(a, b) > 1e-6:
            out.append(("line", a, b))
    return out


# ---- what is made of it --------------------------------------------------------------
def expand(ctrl, curves, tol: float = TOL) -> list:
    """The final polygon: [[x, y], …], every curve in fine steps, rounded to
    0.1 mm as the slabs' corners are."""
    if not ctrl:
        return []
    out = []
    for pc in pieces(ctrl, curves):
        out.append(pc[1])
        if pc[0] == "arc":
            _k, a, _b, c, R, sw = pc
            out += _arc_pts(c, R, a, sw, tol)
    res = []
    for p in out:
        q = [round(p[0], 4) + 0.0, round(p[1], 4) + 0.0]
        if not res or abs(q[0] - res[-1][0]) > 1e-9 \
                or abs(q[1] - res[-1][1]) > 1e-9:
            res.append(q)
    if len(res) > 1 and res[0] == res[-1]:
        res.pop()
    return res


def area(ctrl, curves) -> float:
    """The outline's area, exact — the ends' polygon (shoelace) plus each
    arc's circular segment, signed — as a positive number."""
    a = 0.0
    for pc in pieces(ctrl, curves):
        p, q = pc[1], pc[2]
        a += (p[0] * q[1] - q[0] * p[1]) / 2
        if pc[0] == "arc":
            R, sw = pc[4], pc[5]
            a += R * R / 2 * (sw - math.sin(sw))
    return abs(a)


def perimeter(ctrl, curves) -> float:
    """The outline's length, exact (each arc's R·θ)."""
    L = 0.0
    for pc in pieces(ctrl, curves):
        L += pc[4] * abs(pc[5]) if pc[0] == "arc" else math.dist(pc[1], pc[2])
    return L


def why_not(ctrl, curves) -> str | None:
    """Why these curves can't be (None = they can): a radius that doesn't fit
    its sides, a rounded corner beside an arc, an arc too deep."""
    n = len(ctrl or [])
    if n < 3:
        return "Not a slab outline"
    pts = [(float(p[0]), float(p[1])) for p in ctrl]
    rs = (curves or {}).get("r") or {}
    arcs = (curves or {}).get("arc") or {}
    taken = [0.0] * n                    # the side i's length used at each end
    used_end = [0.0] * n
    for i in range(n):
        r = _key(rs, i)
        if not r:
            continue
        if r < 0:
            return "A radius can't be negative"
        if _key(arcs, i - 1) or _key(arcs, i):
            return "A rounded corner needs two straight sides"
        f = fillet(pts[i - 1], pts[i], pts[(i + 1) % n], r)
        if f is None:
            return "No corner there to round"
        t = f[3]
        used_end[(i - 1) % n] += t
        taken[i] += t
    for i in range(n):
        L = math.dist(pts[i], pts[(i + 1) % n])
        if taken[i] + used_end[i] > L + 1e-6:
            return "The radius doesn't fit the sides"
        h = _key(arcs, i)
        if h and abs(h) > L + 1e-6:
            return "The arc is too deep for its side"
    return None


# ---- keeping the curves when the corners change ----------------------------------------
def remap(old_ctrl, new_ctrl, curves) -> tuple[dict, bool]:
    """The curves for ``new_ctrl`` after a corner was moved, added or
    deleted on ``old_ctrl``: (curves, whether some were dropped — the side
    split or joined has no arc left, the corner deleted no radius)."""
    curves = clean(curves)
    n0, n1 = len(old_ctrl or []), len(new_ctrl or [])
    if n0 == n1:
        return curves, False
    old = [tuple(map(float, p)) for p in old_ctrl]
    new = [tuple(map(float, p)) for p in new_ctrl]

    def same(p, q):
        return abs(p[0] - q[0]) < 1e-6 and abs(p[1] - q[1]) < 1e-6
    if n1 == n0 + 1:                     # one corner added, at k
        k = next((j for j in range(n0) if not same(old[j], new[j])), n0)
        if all(same(old[j], new[j + 1]) for j in range(k, n0)):
            out = {"r": {}, "arc": {}}
            for j, v in curves["r"].items():
                j = int(j)
                out["r"][str(j + 1 if j >= k else j)] = v
            dropped = False
            for j, v in curves["arc"].items():
                j = int(j)
                if j == (k - 1) % n0:    # the side split: straight again
                    dropped = True
                    continue
                out["arc"][str(j + 1 if j >= k else j)] = v
            return out, dropped
    if n1 == n0 - 1:                     # one corner deleted, at k
        k = next((j for j in range(n1) if not same(old[j], new[j])), n1)
        if all(same(old[j + 1], new[j]) for j in range(k, n1)):
            out = {"r": {}, "arc": {}}
            dropped = False
            for j, v in curves["r"].items():
                j = int(j)
                if j == k:
                    dropped = True
                    continue
                out["r"][str(j - 1 if j > k else j)] = v
            for j, v in curves["arc"].items():
                j = int(j)
                if j in (k, (k - 1) % n0):   # the two sides joined
                    dropped = True
                    continue
                out["arc"][str(j - 1 if j > k else j)] = v
            return out, dropped
    empty = curves["r"] or curves["arc"]
    return {"r": {}, "arc": {}}, bool(empty)


def with_curves(rec: dict, ctrl, curves) -> dict:
    """``rec`` with these control corners and curves — ``corners`` made from
    them; with no curve left, a plain slab again (no ``ctrl``)."""
    r = dict(rec)
    curves = clean(curves)
    ctrl = [[round(float(p[0]), 4) + 0.0, round(float(p[1]), 4) + 0.0]
            for p in ctrl]
    if curves["r"] or curves["arc"]:
        r["ctrl"] = ctrl
        r["curves"] = curves
        r["corners"] = expand(ctrl, curves)
    else:
        r.pop("ctrl", None)
        r.pop("curves", None)
        r["corners"] = ctrl
    return r


def matches(ctrl, curves, corners, tol: float = 2e-4) -> bool:
    """These curves still make these corners (a tool that knows nothing of
    them changed the corners: the curves are stale, the corners rule)."""
    try:
        ex = expand(ctrl, curves)
    except Exception:  # noqa: BLE001 — bad data: no
        return False
    return len(ex) == len(corners or []) and all(
        abs(a[0] - float(b[0])) <= tol and abs(a[1] - float(b[1])) <= tol
        for a, b in zip(ex, corners))


def live(rec: dict) -> bool:
    """The record's curves are there AND still its corners'."""
    return is_curved(rec) and matches(rec["ctrl"], rec["curves"],
                                      rec.get("corners"))


def slab_area(rec: dict) -> float:
    """A slab's outline area (no openings): exact with curves."""
    if live(rec):
        return area(rec["ctrl"], rec["curves"])
    cs = rec.get("corners") or []
    return abs(sum(float(p[0]) * float(q[1]) - float(q[0]) * float(p[1])
                   for p, q in zip(cs, cs[1:] + cs[:1]))) / 2


def same_loop(a, b, tol: float = 2e-4) -> bool:
    """The same closed outline, whatever corner it starts on and whichever
    way it turns (shapely gives a ring back from anywhere)."""
    n = len(a or [])
    if n != len(b or []) or n < 3:
        return False
    A = [(float(p[0]), float(p[1])) for p in a]
    for B in ([(float(p[0]), float(p[1])) for p in b],
              [(float(p[0]), float(p[1])) for p in b][::-1]):
        for s in range(n):
            if abs(A[0][0] - B[s][0]) > tol or abs(A[0][1] - B[s][1]) > tol:
                continue
            if all(abs(A[k][0] - B[(s + k) % n][0]) <= tol
                   and abs(A[k][1] - B[(s + k) % n][1]) <= tol
                   for k in range(n)):
                return True
    return False


# ---- a slab's OPENINGS with arcs (``hole_curves``, beside ``holes``) ------------------
def hole_entry(rec: dict, j: int):
    """{"ctrl", "curves"} of opening j while it still makes it — else None."""
    hs = rec.get("holes") or []
    hc = rec.get("hole_curves") or []
    if j >= len(hs) or j >= len(hc) or not isinstance(hc[j], dict):
        return None
    ent = hc[j]
    cv = ent.get("curves") or {}
    if not ent.get("ctrl") or not ((cv.get("r") or {}) or
                                   (cv.get("arc") or {})):
        return None
    return ent if matches(ent["ctrl"], cv, hs[j]) else None


def _tidy_holes(r: dict, hc: list) -> dict:
    hc = (list(hc) + [None] * len(r.get("holes") or []))[
        :len(r.get("holes") or [])]
    if any(isinstance(x, dict) for x in hc):
        r["hole_curves"] = hc
    else:
        r.pop("hole_curves", None)
    return r


def with_hole(rec: dict, j: int, ctrl, curves) -> dict:
    """``rec`` with opening j made of these clicked corners and curves (a
    plain opening again with none)."""
    r = dict(rec)
    hs = [list(h) for h in rec.get("holes") or []]
    hc = list(rec.get("hole_curves") or [])
    hc += [None] * (len(hs) - len(hc))
    curves = clean(curves)
    ctrl = [[round(float(p[0]), 4) + 0.0, round(float(p[1]), 4) + 0.0]
            for p in ctrl]
    if curves["r"] or curves["arc"]:
        hs[j] = expand(ctrl, curves)
        hc[j] = {"ctrl": ctrl, "curves": curves}
    else:
        hs[j] = ctrl
        hc[j] = None
    r["holes"] = hs
    return _tidy_holes(r, hc)


def kept_holes(old: dict, holes: list, new=None) -> tuple:
    """(holes, hole_curves) after a cut remade the openings (shapely's
    rings, from any corner): each one that is still a curved opening of
    ``old`` (or the ``new`` one drawn: (loop, ctrl, curves)) gets its exact
    outline and its curves back; the others stay as cut."""
    known = [(e["ctrl"], e["curves"]) for e in
             (hole_entry(old, j) for j in range(len(old.get("holes") or [])))
             if e is not None]
    if new is not None:
        known.append((new[1], new[2]))
    out_h, out_c = [], []
    for ring in holes:
        hit = next(((c, cv) for c, cv in known
                    if same_loop(expand(c, cv), ring)), None)
        if hit is None:
            out_h.append(ring)
            out_c.append(None)
        else:
            out_h.append(expand(*hit))
            out_c.append({"ctrl": [list(p) for p in hit[0]],
                          "curves": clean(hit[1])})
    return out_h, out_c


def hole_area(rec: dict, j: int) -> float:
    ent = hole_entry(rec, j)
    if ent is not None:
        return area(ent["ctrl"], ent["curves"])
    h = (rec.get("holes") or [])[j]
    return abs(sum(float(p[0]) * float(q[1]) - float(q[0]) * float(p[1])
                   for p, q in zip(h, h[1:] + h[:1]))) / 2


def holes_area(rec: dict) -> float:
    return sum(hole_area(rec, j) for j in range(len(rec.get("holes") or [])))


def control(rec: dict) -> list:
    """The corners the user edits: the control ones when there are curves."""
    return [list(p) for p in (rec.get("ctrl") if live(rec)
                              else rec.get("corners") or [])]


def transformed(rec: dict, pt, scale: float | None = 1.0,
                before: dict | None = None) -> dict:
    """The control corners taken by ``pt`` (a motion or a uniform scale by
    ``scale``) and the corners made again. ``scale`` None = a stretch a
    circle can't follow: the curves become the fine polygon (exact, plain).
    ``before``: the record before ``pt`` went over its corners / openings
    (which curved openings are still theirs is judged on it)."""
    r = dict(rec)
    # its curved OPENINGS first (taken from the record as it came: their
    # outlines may have gone through ``pt`` already — remade from ctrl)
    hc = rec.get("hole_curves") or []
    if hc:
        ents = []
        for j, ent in enumerate(hc):
            ok = hole_entry(before or rec, j) is not None
            if ok and scale is not None:
                k = abs(float(scale))
                cv = {part: {i: v * k for i, v in d.items()}
                      for part, d in clean(ent.get("curves")).items()}
                ents.append((j, [pt(p) for p in ent["ctrl"]], cv))
        r.pop("hole_curves", None)
        for j, c, cv in ents:
            if j < len(r.get("holes") or []):
                r = with_hole(r, j, c, cv)
    if not (live(before) if before is not None else is_curved(rec)):
        r.pop("ctrl", None)              # (stale curves: the corners rule)
        r.pop("curves", None)
        return r
    if scale is None:
        r.pop("ctrl", None)
        r.pop("curves", None)
        return r
    cv = clean(rec["curves"])
    k = abs(float(scale))
    cv = {part: {i: v * k for i, v in d.items()} for part, d in cv.items()}
    return with_curves(r, [pt(p) for p in rec["ctrl"]], cv)


# ---- the edits' gestures ----------------------------------------------------------------
def radius_through(prev, p, nxt, d: float) -> float:
    """The corner radius whose arc passes ``d`` off the corner p, along its
    bisector (the cursor's distance — the arc's middle follows it)."""
    u1 = _unit(prev[0] - p[0], prev[1] - p[1])
    u2 = _unit(nxt[0] - p[0], nxt[1] - p[1])
    a = math.acos(max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1])))
    k = 1 / math.sin(a / 2) - 1 if 1e-4 < a < math.pi - 1e-4 else 0.0
    return d / k if k > 1e-9 else 0.0


def max_radius(ctrl, curves, i: int) -> float:
    """The largest radius corner i takes, its neighbours' kept."""
    pts = [(float(p[0]), float(p[1])) for p in ctrl]
    n = len(pts)
    rs = (curves or {}).get("r") or {}
    f1 = fillet(pts[i - 1], pts[i], pts[(i + 1) % n], 1.0)
    if f1 is None:
        return 0.0
    per = f1[3]                          # tangent length per metre of radius

    def used(j, side_pt):
        r = _key(rs, j % n)
        if not r:
            return 0.0
        f = fillet(pts[(j - 1) % n], pts[j % n], pts[(j + 1) % n], r)
        return f[3] if f else 0.0
    room_in = math.dist(pts[i - 1], pts[i]) - used(i - 1, None)
    room_out = math.dist(pts[i], pts[(i + 1) % n]) - used(i + 1, None)
    return max(0.0, min(room_in, room_out) / per)


def sagitta_for_radius(a, b, R: float, side: float) -> float | None:
    """The sagitta of the SHORT arc of radius R on the chord a → b, on
    ``side`` (+ left) — None when R is under half the chord."""
    s = math.dist(a, b) / 2
    if R < s - 1e-9:
        return None
    h = R - math.sqrt(max(0.0, R * R - s * s))
    return math.copysign(h, side)


def radius_of_sagitta(a, b, h: float) -> float:
    s = math.dist(a, b) / 2
    return (s * s + h * h) / (2 * abs(h)) if abs(h) > EPS else 0.0


__all__ = ["expand", "area", "perimeter", "why_not", "remap", "with_curves",
           "control", "transformed", "is_curved", "clean", "pieces",
           "radius_through", "max_radius", "sagitta_for_radius",
           "radius_of_sagitta", "side_arc", "fillet"]


# ---- «Straighten all» (the slab's window) -----------------------------------------
def curve_count(rec: dict) -> tuple[int, int]:
    """(rounded corners, bent sides) in the slab: its outline's and its
    openings' (only the curves that still make them)."""
    nr = na = 0
    if live(rec):
        cv = clean(rec.get("curves"))
        nr, na = len(cv["r"]), len(cv["arc"])
    for j in range(len(rec.get("holes") or [])):
        ent = hole_entry(rec, j)
        if ent is not None:
            cv = clean(ent["curves"])
            nr += len(cv["r"])
            na += len(cv["arc"])
    return nr, na


def keep_open(rec: dict, keep: list) -> dict:
    """``rec`` with only the openings flagged in ``keep`` (the window's
    «Close it») — their curves kept beside them, in step."""
    hs = rec.get("holes") or []
    hc = list(rec.get("hole_curves") or []) + [None] * len(hs)
    r = dict(rec)
    r["holes"] = [h for h, k in zip(hs, keep) if k]
    return _tidy_holes(r, [c for c, k in zip(hc, keep) if k])


def straight(rec: dict, fits=None) -> dict:
    """``rec`` with every curve gone: its outline and its openings back to
    their clicked corners (straight sides, sharp corners). ``fits(r)`` —
    whether a slab can stand (its openings inside it, apart): a part whose
    straightening would break that keeps its curves."""
    def ok(r):
        return fits is None or fits(r)

    r = dict(rec)
    if live(r):
        t = dict(r, corners=[list(p) for p in r["ctrl"]])
        t.pop("ctrl", None)
        t.pop("curves", None)
        if ok(t):
            r = t
    else:                                  # stale: nothing to keep
        r.pop("ctrl", None)
        r.pop("curves", None)
    for j in range(len(r.get("holes") or [])):
        ent = hole_entry(r, j)
        if ent is None:
            continue
        t = with_hole(r, j, ent["ctrl"], {})
        if ok(t):
            r = t
    if not any(hole_entry(r, j) is not None
               for j in range(len(r.get("holes") or []))):
        r.pop("hole_curves", None)
    return r
