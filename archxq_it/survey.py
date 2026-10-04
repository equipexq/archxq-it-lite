"""Survey points from a file — pure, no Qt.

What surveyors hand over: a text file, one point per line, the columns
split by commas, semicolons, tabs or spaces; a name / number column or
not; sometimes a header; decimal commas where the columns go by
semicolons or tabs; the order X Y Z (easting, northing) or — the
«PNEZD» habit — northing first. ``read()`` makes sense of it and says
what it guessed, so the import window can show it and let it be changed.
"""
from __future__ import annotations

import math
import re

ORDERS = (("xyz", "X, Y, Z  (East, North, Elevation)"),
          ("yxz", "Y, X, Z  (North, East, Elevation)"))


def _num(s: str, comma: bool):
    s = s.strip().replace("−", "-")
    if comma:
        s = s.replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _split(line: str, sep: str | None) -> list[str]:
    if sep is None:
        return line.split()
    return [c.strip().strip('"').strip("'") for c in line.split(sep)]


def _sniff(lines: list[str]):
    """(separator, decimal comma?) — the one that gives the most lines with
    the same number (≥ 3) of columns."""
    best = (None, False, -1)
    for sep in ("\t", ";", ",", None):
        counts = {}
        for ln in lines[:200]:
            n = len(_split(ln, sep))
            if n >= 3:
                counts[n] = counts.get(n, 0) + 1
        score = max(counts.values()) if counts else 0
        if score > best[2]:
            best = (sep, False, score)
    sep = best[0]
    # a decimal comma: only where commas don't split the columns
    comma = sep != "," and any(re.search(r"\d,\d", ln) for ln in lines[:200])
    return sep, comma


def read(text: str, order: str | None = None) -> dict:
    """→ {"points": [[x, y, z, name]], "order", "skipped": n lines not
    read, "header": bool, "named": bool, "sep": label}. ``order`` None =
    guessed (a header naming N / Northing first → "yxz")."""
    lines = [ln for ln in text.splitlines() if ln.strip()
             and not ln.lstrip().startswith(("#", "//"))]
    sep, comma = _sniff(lines)
    rows = [_split(ln, sep) for ln in lines]
    header = False
    guess = "xyz"
    if rows and sum(_num(c, comma) is not None for c in rows[0]) < 3:
        header = True
        h = [c.lower() for c in rows[0]]
        cols = [c for c in h if c in ("x", "y", "e", "n", "east", "north",
                                      "easting", "northing", "este",
                                      "norte")]
        if cols and cols[0] in ("y", "n", "north", "northing", "norte"):
            guess = "yxz"
        rows = rows[1:]
    order = order or guess
    pts, skipped, named = [], 0, False
    for r in rows:
        nums = [(_num(c, comma), c) for c in r]
        vals = [v for v, _c in nums if v is not None]
        if len(vals) < 3:
            skipped += 1
            continue
        # a name / number in front: the first column when there are 4+,
        # or when it is not a number
        name = ""
        if nums[0][0] is None or len(vals) >= 4:
            name = nums[0][1].strip()
            named = True
            vals = [v for v, _c in nums[1:] if v is not None]
            if len(vals) < 3:
                skipped += 1
                continue
        a, b, z = vals[0], vals[1], vals[2]
        x, y = (b, a) if order == "yxz" else (a, b)
        pts.append([x, y, z, name[:40]])
    labels = {"\t": "tabs", ";": "semicolons", ",": "commas", None: "spaces"}
    return {"points": pts, "order": order, "skipped": skipped,
            "header": header, "named": named,
            "sep": labels[sep] + (", decimal comma" if comma else "")}


def placed(points, dx: float, dy: float, datum: float) -> list:
    """The points moved into the model: shifted by (dx, dy), and their
    elevations measured from ``datum`` (the elevation that is ±0.00)."""
    return [[round(p[0] + dx, 4), round(p[1] + dy, 4),
             round(p[2] - datum, 3), p[3]] for p in points]


def fit_shift(points, plot_pts) -> tuple[float, float]:
    """(dx, dy) that puts the points where the plot is: none when they
    already overlap it (the same coordinates), else their middle on the
    plot's middle (a survey in UTM, a plot drawn near the origin)."""
    if not points or not plot_pts:
        return 0.0, 0.0
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    px, py = [p[0] for p in plot_pts], [p[1] for p in plot_pts]
    if max(xs) >= min(px) and min(xs) <= max(px) \
            and max(ys) >= min(py) and min(ys) <= max(py):
        return 0.0, 0.0
    return (round((min(px) + max(px)) / 2 - (min(xs) + max(xs)) / 2, 3),
            round((min(py) + max(py)) / 2 - (min(ys) + max(ys)) / 2, 3))


def fit_datum(points) -> float:
    """The elevation that becomes ±0.00: none for small numbers (already
    relative), else the lowest point, rounded down to the metre."""
    if not points:
        return 0.0
    zs = [p[2] for p in points]
    if max(abs(z) for z in zs) < 50.0:
        return 0.0
    return float(math.floor(min(zs)))
