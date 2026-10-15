"""Walls MOVED — the walls joined to them stretch (his ask, 2026-10-10: his
retaining walls had to go out to the columns' face; «move the wall and the
perpendicular ones stretch», as SketchUp does).

A wall shifted (the host's Move on it, or the library's «Move across»
bar): its record goes with it, its openings too. Every OTHER straight wall
of its level with an end on it (a corner, a T: the end on its line or in
its body) keeps that end on it — the end slides along its own line, so the
wall gets longer or shorter. Openings in a wall whose START end slid keep
their place in the world (their position runs from that end). A turn
(Rotate) or an end moved: ``reshape`` (2026-10-14) — a corner's end goes
with it, a T's end slides onto the new line.

Pure data — no Qt; ``edits.py`` and ``ui.py`` use it.
"""
from __future__ import annotations

import copy
import math

from . import walls as W

#: m — an end «on» a wall: on its line or in its body. As far as the walls
#: engine still DRAWS it joined (W.SNAP_TOL): at 5 mm a partition that
#: stopped 1–2 cm short looked joined, and a move left it behind (his
#: test of the grips, 2026-10-12)
TOUCH = W.SNAP_TOL


def _unit(v):
    L = math.hypot(v[0], v[1])
    return (v[0] / L, v[1] / L) if L > 1e-12 else (0.0, 0.0)


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1]


def shifted(rec: dict, d) -> dict:
    """A wall's record moved by the plan vector ``d``."""
    r = copy.deepcopy(rec)
    for key in ("a", "b", "m", "c"):
        if key in r:
            r[key] = [round(float(r[key][0]) + d[0], 4),
                      round(float(r[key][1]) + d[1], 4)]
    return r


def _bodies(walls: list[dict]) -> dict:
    """{wall id: shapely geometry} — the line drawn and the joined body."""
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union
    out = {}
    plans = W.plan(walls)
    for w in walls:
        geo = []
        if w.get("kind", "line") == "line":
            geo.append(LineString([tuple(w["a"]), tuple(w["b"])]))
        for pc in plans.get(w["id"], ()):
            try:
                geo.append(Polygon(pc["outer"]).buffer(0))
            except Exception:  # noqa: BLE001
                pass
        if geo:
            out[w["id"]] = unary_union(geo)
    return out


def move(doc: dict, shifts: dict) -> tuple[dict, list[str]]:
    """(the document with the walls ``shifts`` = {wall id: (dx, dy)} moved
    and their neighbours stretched, notes). Openings follow."""
    from shapely.geometry import Point
    walls = doc.get("walls") or []
    by_id = {w["id"]: w for w in walls}
    shifts = {i: tuple(d) for i, d in shifts.items()
              if i in by_id and math.hypot(*d) > 1e-6}
    if not shifts:
        return doc, []
    new = {i: shifted(by_id[i], d) for i, d in shifts.items()}
    slid: dict = {}            # neighbour id → how far its START end slid
    short = []
    for lid in {by_id[i]["level"] for i in shifts}:
        mine = [w for w in walls if w["level"] == lid]
        bodies = _bodies(mine)
        movers = [by_id[i] for i in shifts if by_id[i]["level"] == lid
                  and by_id[i].get("kind", "line") == "line"]
        for n in mine:
            if n["id"] in shifts or n.get("kind", "line") != "line":
                continue
            a, b = tuple(n["a"]), tuple(n["b"])
            dn = _unit((b[0] - a[0], b[1] - a[1]))
            rec = dict(new.get(n["id"], n))
            for key, E in (("a", a), ("b", b)):
                for m in movers:
                    body = bodies.get(m["id"])
                    if body is None or body.distance(Point(E)) > TOUCH:
                        continue
                    d = shifts[m["id"]]
                    um = _unit((m["b"][0] - m["a"][0], m["b"][1] - m["a"][1]))
                    nm = (-um[1], um[0])
                    den = _dot(dn, nm)
                    if abs(den) > 0.1:     # across it: keep the end on it
                        t = _dot(d, nm) / den
                    else:                  # in line with it: follow along
                        t = _dot(d, dn)
                    rec[key] = [round(E[0] + dn[0] * t, 4),
                                round(E[1] + dn[1] * t, 4)]
                    if key == "a":
                        slid[n["id"]] = t
                    break
            if rec["a"] != list(n["a"]) or rec["b"] != list(n["b"]):
                L = _dot((rec["b"][0] - rec["a"][0],
                          rec["b"][1] - rec["a"][1]), dn)
                if L < max(float(n["t"]), 0.05):
                    short.append(n["name"])      # it would vanish / flip
                    slid.pop(n["id"], None)
                    continue
                new[n["id"]] = rec
        # a wall IN LINE with a stretched one, end to end with it (the
        # same run of wall drawn in two pieces): its end goes along with
        # the joint — else a gap opened there (his corner, 2026-10-12:
        # Wall 13 stretched to the moved shop wall, Wall 25 over it stayed)
        for n in mine:
            if n["id"] in shifts or n["id"] not in new \
                    or n.get("kind", "line") != "line":
                continue
            body = bodies.get(n["id"])
            dn = _unit((n["b"][0] - n["a"][0], n["b"][1] - n["a"][1]))
            for key in ("a", "b"):
                E, En = n[key], new[n["id"]][key]
                mv = (En[0] - E[0], En[1] - E[1])
                if math.hypot(*mv) < 1e-6:
                    continue
                for m in mine:
                    if m["id"] in shifts or m["id"] in new or m["id"] == \
                            n["id"] or m.get("kind", "line") != "line":
                        continue
                    um = _unit((m["b"][0] - m["a"][0], m["b"][1] - m["a"][1]))
                    if abs(um[0] * dn[1] - um[1] * dn[0]) > 0.05:
                        continue                     # not in line
                    for mk in ("a", "b"):
                        P = m[mk]
                        # on n's body, at the joint (not along its middle)
                        if body is None or body.distance(Point(P)) > TOUCH:
                            continue
                        if abs(_dot((P[0] - E[0], P[1] - E[1]), dn)) > \
                                float(n["t"]) / 2 + TOUCH:
                            continue
                        rec = dict(m)
                        rec[mk] = [round(P[0] + mv[0], 4),
                                   round(P[1] + mv[1], 4)]
                        L = math.dist(rec["a"], rec["b"])
                        if L < max(float(m["t"]), 0.05):
                            short.append(m["name"])
                            continue
                        if mk == "a":
                            slid[m["id"]] = _dot(mv, um)
                        new[m["id"]] = rec
    out = dict(doc, walls=[new.get(w["id"], w) for w in walls])
    if slid:
        out["openings"] = [
            dict(o, pos=round(float(o["pos"]) - slid[o["wall"]], 4))
            if o["wall"] in slid else o for o in doc.get("openings") or []]
    notes = []
    k = len(shifts)
    notes.append(f"{k} wall{'s' if k > 1 else ''} moved")
    stretched = len(new) - k
    if stretched:
        notes.append(f"{stretched} joined wall{'s' if stretched > 1 else ''}"
                     " stretched")
    if short:
        notes.append("not stretched (too short): " + ", ".join(short))
    return out, notes


def reshape(doc: dict, changes: dict) -> tuple[dict, list[str]]:
    """(the document with the straight walls ``changes`` = {wall id: its
    new record} — TURNED (the host's Rotate) or an end moved (its window's
    Start / End) — and the walls joined to them following, notes).

    A user on YouTube, 2026-10-14: «changing a wall's direction, the other
    walls don't follow and the corner isn't updated». Each OTHER straight
    wall of its level with an end on it:
      - at one of its ENDS (a corner): that end goes with it — the corner
        stays closed, the neighbour turns about its far end;
      - on its body (a T): the end slides along its own line onto the new
        line (as a move does) — the neighbour keeps its direction.
    Openings of a neighbour whose START end moved keep their place in the
    world (their position runs from that end)."""
    from shapely.geometry import Point
    walls = doc.get("walls") or []
    by_id = {w["id"]: w for w in walls}
    changes = {i: r for i, r in changes.items()
               if i in by_id and by_id[i].get("kind", "line") == "line"
               and r.get("kind", "line") == "line"}
    if not changes:
        return doc, []
    new = {i: copy.deepcopy(r) for i, r in changes.items()}
    slid: dict = {}
    short = []
    for lid in {by_id[i]["level"] for i in changes}:
        mine = [w for w in walls if w["level"] == lid]
        bodies = _bodies(mine)
        movers = [by_id[i] for i in changes if by_id[i]["level"] == lid]
        for n in mine:
            if n["id"] in changes or n.get("kind", "line") != "line":
                continue
            a, b = tuple(n["a"]), tuple(n["b"])
            dn = _unit((b[0] - a[0], b[1] - a[1]))
            rec = dict(n)
            for key, E in (("a", a), ("b", b)):
                for m in movers:
                    body = bodies.get(m["id"])
                    if body is None or body.distance(Point(E)) > TOUCH:
                        continue
                    nm_rec = new[m["id"]]
                    reach = float(m["t"]) / 2 + float(n["t"]) / 2 + TOUCH
                    # a corner: E by one of m's ends
                    end = next((k for k in ("a", "b")
                                if math.dist(E, m[k]) <= reach), None)
                    if end is not None:
                        d = (nm_rec[end][0] - m[end][0],
                             nm_rec[end][1] - m[end][1])
                        P = (E[0] + d[0], E[1] + d[1])
                    else:                  # a T: onto the new line
                        um = _unit((nm_rec["b"][0] - nm_rec["a"][0],
                                    nm_rec["b"][1] - nm_rec["a"][1]))
                        nrm = (-um[1], um[0])
                        den = _dot(dn, nrm)
                        if abs(den) < 0.1:
                            break          # now in line with it: leave it
                        # the end's offset from m's old centre line, kept
                        o_um = _unit((m["b"][0] - m["a"][0],
                                      m["b"][1] - m["a"][1]))
                        off = _dot((E[0] - m["a"][0], E[1] - m["a"][1]),
                                   (-o_um[1], o_um[0]))
                        Q = nm_rec["a"]
                        t = (_dot((Q[0] - E[0], Q[1] - E[1]), nrm) + off) / den
                        P = (E[0] + dn[0] * t, E[1] + dn[1] * t)
                    rec[key] = [round(P[0], 4), round(P[1], 4)]
                    if key == "a":
                        slid[n["id"]] = _dot((P[0] - E[0], P[1] - E[1]), dn)
                    break
            if rec["a"] != list(n["a"]) or rec["b"] != list(n["b"]):
                if math.dist(rec["a"], rec["b"]) < max(float(n["t"]), 0.05):
                    short.append(n["name"])     # it would vanish / flip
                    slid.pop(n["id"], None)
                    continue
                new[n["id"]] = rec
    out = dict(doc, walls=[new.get(w["id"], w) for w in walls])
    if slid:
        out["openings"] = [
            dict(o, pos=round(float(o["pos"]) - slid[o["wall"]], 4))
            if o["wall"] in slid else o for o in doc.get("openings") or []]
    notes = []
    follow = len(new) - len(changes)
    if follow:
        notes.append(f"{follow} joined wall{'s' if follow > 1 else ''} "
                     "followed")
    if short:
        notes.append("not followed (too short): " + ", ".join(short))
    return out, notes


def across(w: dict, dist: float):
    """The plan vector of ``dist`` across a straight wall (+ = to the left
    of its line drawn, a → b)."""
    u = _unit((w["b"][0] - w["a"][0], w["b"][1] - w["a"][1]))
    return (-u[1] * dist, u[0] * dist)
