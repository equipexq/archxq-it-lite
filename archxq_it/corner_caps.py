"""A CORNER OF TWO HEIGHTS (2026-11-01, his question: «on site, doesn't the
higher wall go on and the other come in lower?»). Where two walls meet in
an L at different heights the corner is bonded up to the LOWER one's top;
above it only the higher wall goes on, over the whole corner, and the
lower one stops against it — the step stands upright on the higher wall's
face, never on the mitre's diagonal (as ArchiCAD draws it).

The plan keeps its mitre (cuts, sheets, quantities, layers in plan: all as
they were). Only the 3D changes: the higher wall gets a «cap» — the part
of the lower wall's mitre lying within its own thickness, raised from the
lower wall's top to its own, cut in its own layers and under its own top
(its slope runs on to the corner's far face: ``walls.clear_span`` own);
its end there wears the finish of its outer corner's side, not a stripe
per layer.
Its mitre face above the lower top goes (inside it now), and the lines
across the faces that now run on are hidden (``"joint"``: seams).

Corners of the same height (±``SAME``) stay as they are. Pure: walls in,
faces out — tests/test_corner_heights."""
from __future__ import annotations

import math

from . import walls as W

SAME = 0.001            # m: heights this close are the same (a mitre)
MIN_SIN = 0.34          # walls meeting at under ~20° keep their mitre
CLEAR = 0.005           # m: the higher wall's top stays this far above
ON = 1e-5               # m: a point this close lies on a line


def end_height(w: dict, pieces, end: str, z0: float, under: float):
    """How high (from the level's floor) the wall stands at its end
    ("A" / "B"), as built — its own top (level on its corner piece), its
    height, or up to the slab over the level."""
    if W.top_of(w) is not None:
        ww = dict(w, _span=W.clear_span(w, pieces))
        return W.top_h(ww, 0.0 if end == "A" else W.drawn(w).L)
    if w.get("height", "level") == "level":
        return under - z0
    return float(w["height"])


def _strip(seg, lo: float, hi: float, reach: float):
    """The band between offsets lo and hi from a straight centre, far past
    its ends."""
    from shapely.geometry import Polygon
    u = seg.u
    n = (-u[1], u[0])
    a = (seg.p0[0] - u[0] * reach, seg.p0[1] - u[1] * reach)
    b = (seg.p1[0] + u[0] * reach, seg.p1[1] + u[1] * reach)

    def at(p, o):
        return (p[0] + n[0] * o, p[1] + n[1] * o)
    return Polygon([at(a, lo), at(b, lo), at(b, hi), at(a, hi)])


def _cap_poly(hi_w, lo_pieces, diag):
    """The part of the lower wall's mitre within the higher one's
    thickness, at this corner — None: none to speak of."""
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union
    seg = W.centre(hi_w)
    t = float(hi_w["t"])
    mid = ((diag[0][0] + diag[1][0]) / 2, (diag[0][1] + diag[1][1]) / 2)
    try:
        lower = unary_union([Polygon(pc["outer"], pc.get("holes") or [])
                             .buffer(0) for pc in lo_pieces])
        near = Point(mid).buffer(4 * t + 1.0)
        got = lower.intersection(_strip(seg, -t / 2, t / 2, 50.0)) \
            .intersection(near)
    except Exception:  # noqa: BLE001 — no cap: the mitre as before
        return None
    best = None
    for g in W._polys(got):
        if g.distance(Point(mid)) < 1e-4 and (best is None
                                               or g.area > best.area):
            best = g
    if best is None or best.area < 1e-5:
        return None
    return best


def caps(mine: list[dict], plans: dict, found: list, z0: float,
         under: float) -> dict:
    """{wall id: [cap]} — each L corner (``walls.corners``) of two walls
    standing at different heights gives the higher one a cap: {"poly"
    (shapely), "zl" (the lower top, absolute), "diag", "inner" (the
    diagonal's end the higher wall's face runs on from), "end"}."""
    by_id = {w["id"]: w for w in mine}
    cand = []
    for c in found:
        wa, wb = by_id.get(c["a"]), by_id.get(c["b"])
        if wa is None or wb is None:
            continue
        ua, ub = W.drawn(wa).u, W.drawn(wb).u
        if abs(ua[0] * ub[1] - ua[1] * ub[0]) < MIN_SIN:
            continue
        ha = end_height(wa, plans.get(wa["id"]), c["a_end"], z0, under)
        hb = end_height(wb, plans.get(wb["id"]), c["b_end"], z0, under)
        if ha is None or hb is None or abs(ha - hb) <= SAME:
            continue
        if ha > hb:
            hi, end, lo, h_lo = wa, c["a_end"], wb, hb
        else:
            hi, end, lo, h_lo = wb, c["b_end"], wa, ha
        poly = _cap_poly(hi, plans.get(lo["id"]) or (), c["diag"])
        if poly is None:
            continue
        cand.append({"wall": hi["id"], "end": end, "poly": poly,
                     "zl": z0 + h_lo, "diag": c["diag"],
                     "inner": _inner(hi, poly, c["diag"])})
    # a sloped higher wall: its top, run on over the corner, must stay over
    # the lower one everywhere there (a slope falling into the corner may
    # not) — else that corner keeps its mitre
    for _round in range(3):
        bad = []
        for k, cp in enumerate(cand):
            w = by_id[cp["wall"]]
            if W.top_of(w) is None:
                continue
            own = {x["end"] for x in cand if x["wall"] == cp["wall"]}
            ww = dict(w, _span=W.clear_span(w, plans.get(w["id"]), own))
            seg = W.drawn(w)
            pts = list(cp["poly"].exterior.coords)
            low = min(W.top_h(ww, (p[0] - seg.p0[0]) * seg.u[0]
                              + (p[1] - seg.p0[1]) * seg.u[1]) for p in pts)
            if z0 + low < cp["zl"] + CLEAR:
                bad.append(k)
        if not bad:
            break
        cand = [cp for k, cp in enumerate(cand) if k not in bad]
    out: dict = {}
    for cp in cand:
        out.setdefault(cp["wall"], []).append(cp)
    return out


def _inner(w, poly, diag):
    """The diagonal's end lying on the higher wall's face that goes on
    along the cap (the inner corner of the L)."""
    seg = W.centre(w)
    others = [p for p in poly.exterior.coords
              if min(math.hypot(p[0] - d[0], p[1] - d[1]) for d in diag) > 1e-4]
    if not others:
        return None
    off = [seg.project(d)[1] for d in diag]
    o = [seg.project(p)[1] for p in others]
    k = min((0, 1), key=lambda i: min(abs(off[i] - x) for x in o))
    return tuple(diag[k])


def cap_faces(w: dict, wall_caps: list, top: float, color_of=None) -> list:
    """The caps' solids, from the lower top up to ``top`` (then cut under
    the wall's own top with the rest of it), in the wall's layers
    (``color_of(i)``: layer i's colour; None: a plain wall). Their faces on
    the diagonal are left out (the wall's own mitre face is there)."""
    from shapely.geometry.polygon import orient
    seg = W.centre(w)
    bands = W.layer_bands(w)
    layered = len(bands) > 1 and color_of is not None
    out = []
    for cp in wall_caps:
        if top - cp["zl"] < 1e-4:
            continue
        # its END (on the lower wall's far face) wears the finish of the
        # higher wall's side at the outer corner, as the plaster goes on up
        # there on site — not a stripe per layer (2026-11-01, his call)
        finish = _finish_at(w, bands, cp) if layered else None
        parts = []
        if layered:
            for i, (lo, hi) in enumerate(bands):
                got = cp["poly"].intersection(_strip(seg, lo, hi, 50.0))
                parts += [(i, g) for g in W._polys(got)]
        else:
            parts = [(None, cp["poly"])]
        for i, g in parts:
            g = orient(g, 1.0)
            piece = {"outer": [tuple(p) for p in list(g.exterior.coords)[:-1]],
                     "holes": []}
            edge = W.shared_edge(w, i + 1) if layered else None
            for f in W.solid(piece, cp["zl"], top):
                loop = f["loop"] if isinstance(f, dict) else f
                if edge is not None and all(
                        abs(seg.project(p)[1] - edge) < 1e-5 for p in loop):
                    continue            # the next layer keeps it
                if _on_diag(loop, cp["diag"]) and _upright(loop):
                    continue            # against the wall's own mitre face
                rec = {"loop": loop, "holes": [], "cap": True}
                if layered:
                    rec["color"] = color_of(i)
                    if finish is not None and _upright(loop) \
                            and not _along(loop, seg.u):
                        # (marked as a reveal: the lines between the
                        # layers on it hide — seams.reveal_edges)
                        rec["color"] = color_of(finish)
                        rec["reveal"] = 1
                out.append(rec)
    return out


def _finish_at(w, bands, cp):
    """The layer on the higher wall's face at the outer corner (the
    diagonal's end that is not the inner one)."""
    outer = [d for d in cp["diag"] if cp["inner"] is None
             or not _same_xy(d, cp["inner"])]
    if len(outer) != 1:
        return None
    off = W.centre(w).project(outer[0])[1]
    return min(range(len(bands)), key=lambda i: min(
        abs(off - bands[i][0]), abs(off - bands[i][1])))


def _along(loop, u) -> bool:
    """An upright face running along the wall (its long sides, the faces
    between its layers) — not across it."""
    for k in range(len(loop)):
        a, b = loop[k], loop[(k + 1) % len(loop)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy)
        if n > 1e-6:
            return abs(dx * u[1] - dy * u[0]) / n < 1e-6
    return True


def _on_line(p, a, b) -> bool:
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    return n > 1e-9 and abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / n < ON


def _on_diag(loop, diag) -> bool:
    return all(_on_line(p, diag[0], diag[1]) for p in loop)


def _upright(loop) -> bool:
    zs = [p[2] for p in loop]
    return max(zs) - min(zs) > 1e-6


def _same_xy(p, q) -> bool:
    return abs(p[0] - q[0]) < ON and abs(p[1] - q[1]) < ON


def joined(faces: list, wall_caps: list) -> list:
    """The wall's faces (topped) with its caps put in: its mitre faces cut
    down to the lower top, its uprights at the diagonal's ends split there
    (the edges meet the cap's), and the lines that now run on across one
    face listed hidden (``"joint"``): the lid's diagonal, the inner
    corner's upright above the lower top."""
    out = []
    hide = []
    for f in faces:
        rec = f if isinstance(f, dict) else {"loop": f, "holes": []}
        loop = rec["loop"]
        if rec.get("cap"):
            out.append(f)
            continue
        cut = False
        for cp in wall_caps:
            if _on_diag(loop, cp["diag"]) and _upright(loop):
                loop = _below(loop, cp["zl"])
                cut = True
        if cut and not loop:
            continue
        for cp in wall_caps:
            for d in cp["diag"]:
                loop = _split_at(loop, d, cp["zl"])
        out.append(dict(rec, loop=loop))
    for cp in wall_caps:
        for f in out:
            loop = f["loop"] if isinstance(f, dict) else f
            n = len(loop)
            for k in range(n):
                a, b = loop[k], loop[(k + 1) % n]
                if a[2] < cp["zl"] - 1e-6 or b[2] < cp["zl"] - 1e-6:
                    continue
                if _same_xy(a, b):
                    # the inner corner's upright above the lower top
                    if cp["inner"] is not None and _same_xy(a, cp["inner"]) \
                            and abs(a[2] - b[2]) > 1e-6:
                        hide.append((a, b))
                elif a[2] > cp["zl"] + 1e-6 and b[2] > cp["zl"] + 1e-6 \
                        and _on_line(a, *cp["diag"]) \
                        and _on_line(b, *cp["diag"]):
                    hide.append((a, b))     # the lid's diagonal
    if hide:
        for i, f in enumerate(out):
            if isinstance(f, dict) and f.get("cap"):
                out[i] = dict(f, joint=list(f.get("joint") or []) + hide)
                break
    return out


def _below(loop, zl: float) -> list:
    """An upright face cut down to z ≤ zl (Sutherland–Hodgman on z)."""
    out = []
    n = len(loop)
    for k in range(n):
        p, q = loop[k], loop[(k + 1) % n]
        pin, qin = p[2] <= zl + 1e-9, q[2] <= zl + 1e-9
        if pin:
            out.append(tuple(p))
        if pin != qin:
            t = (zl - p[2]) / (q[2] - p[2])
            out.append(tuple(p[j] + (q[j] - p[j]) * t for j in range(3)))
    clean = []
    for p in out:
        if not clean or any(abs(p[j] - clean[-1][j]) > 1e-9 for j in range(3)):
            clean.append(p)
    if len(clean) > 1 and all(abs(clean[0][j] - clean[-1][j]) < 1e-9
                              for j in range(3)):
        clean.pop()
    return clean if len(clean) >= 3 else []


def _split_at(loop, d, zl: float) -> list:
    """An upright edge standing on point ``d`` across the height zl gets a
    corner there."""
    out = []
    n = len(loop)
    for k in range(n):
        p, q = loop[k], loop[(k + 1) % n]
        out.append(p)
        if _same_xy(p, d) and _same_xy(q, d) and \
                min(p[2], q[2]) + 1e-6 < zl < max(p[2], q[2]) - 1e-6:
            out.append((p[0], p[1], zl))
    return out
