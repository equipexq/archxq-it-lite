"""A wall EXPLODED with the host's «Explode Group» — its geometry merged
into the loose mesh, to be shaped by hand (a YouTube comment, 2026-10-27:
«explode that element into simple regular geometry … please preserve that
approach»). The wall leaves ArchXQ's record (``ui._live``: its group is
gone) and its doors / windows with it; their frames must NOT vanish at the
next rebuild — they stay as plain groups, as the screen shows them.

Told from a wall DELETED (Delete key, eraser): nothing is left where it
stood, and its doors / windows go with it, as before. Pure: boxes and
points, no host.
"""
from __future__ import annotations

#: m — how near the exploded wall's faces come to a frame (its jambs sit
#: on the hole's sides: 0 m; a little more for the welding)
REACH = 0.05


def box_of(points) -> tuple | None:
    """((x0, y0, z0), (x1, y1, z1)) of ``points`` (x, y, z); None: none."""
    pts = list(points)
    if not pts:
        return None
    return (tuple(min(p[k] for p in pts) for k in range(3)),
            tuple(max(p[k] for p in pts) for k in range(3)))


def _grown(box, d: float):
    lo, hi = box
    return (tuple(v - d for v in lo), tuple(v + d for v in hi))


def inside(box, p) -> bool:
    return all(box[0][k] <= p[k] <= box[1][k] for k in range(3))


def freed(frames: dict, walls: list, loose) -> set:
    """The frames left free: ``frames`` {key: box} — the doors / windows
    whose record is gone; ``walls``: the boxes of ArchXQ's walls still
    standing; ``loose``: the loose mesh's points. A frame is free when no
    ArchXQ wall stands at it (its own was taken away) AND loose geometry
    reaches it (that wall was exploded, not deleted)."""
    out = set()
    if not frames:
        return out
    pts = None
    for key, box in frames.items():
        if box is None:
            continue
        near = _grown(box, REACH)
        # (its centre: a wall meeting its own at a corner never holds it)
        mid = tuple((box[0][k] + box[1][k]) / 2 for k in range(3))
        if any(w is not None and inside(_grown(w, REACH), mid)
               for w in walls):
            continue                      # a wall of ours there: it goes
        if pts is None:
            pts = [tuple(p) for p in loose]
        if any(inside(near, p) for p in pts):
            out.add(key)
    return out
