# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A STAIR'S CODE CHECK (plan PLANO_ESCADA_NORMA.md, his ask 2026-10-29 —
the idea from MUZWalls' live checks): a stair's numbers held against a
building code's — a GUIDE, never a block (why_not stays for the absurd).

Each code is a row of numbers, not code (metres; None = the code says
nothing of it):

    riser     (lo, hi)        the riser's height
    tread     (lo, hi)        the tread (going)
    blondel   (lo, hi)        2 R + T
    width     lo              the flight's clear width
    flight    ("rise", m) or ("risers", n) — the most one flight climbs
              before a landing
    pitch     hi (degrees)
    headroom  lo              over the treads (a beam crossing above)

Sources (29/10, secondary — the codes' own text to be read before a
release): NBR 9050:2020 6.8 (16–18 / 28–32 / 63–65, a landing every
3.20 m, 1.20 wide), NBR 9077 (63–64, 3.70 m between landings, 1.10 wide,
2.00 headroom), DIN 18065 (homes: 14–20 / 23–37, 59–65, 80 cm, 18 risers,
2.00 m — checked 31/10 against Baunetzwissen and others: Table 1 for homes
of up to two flats, 6.1.2 the 59–65 rule, 6.4 the 2.00 m; the landing
after 18 risers is a «should» for homes, a guide like the rest),
Approved Document K (private: rise ≤ 220, going ≥ 220,
2R+G 550–700, 42°, 2.0 m), IRC R311.7 (7 3/4" / 10", 36", 151", 6'8").
"""
from __future__ import annotations

import math

from .i18n import N_

IN = 0.0254
RULES: dict[str, dict] = {
    "nbr9050": {"name": "NBR 9050", "riser": (0.16, 0.18),
                "tread": (0.28, 0.32), "blondel": (0.63, 0.65),
                "width": 1.20, "flight": ("rise", 3.20), "pitch": None,
                "headroom": 2.10},
    "nbr9077": {"name": "NBR 9077", "riser": (0.16, 0.18),
                "tread": (0.28, 0.32), "blondel": (0.63, 0.64),
                "width": 1.10, "flight": ("rise", 3.70), "pitch": None,
                "headroom": 2.00},
    "din18065": {"name": "DIN 18065", "riser": (0.14, 0.20),
                 "tread": (0.23, 0.37), "blondel": (0.59, 0.65),
                 "width": 0.80, "flight": ("risers", 18), "pitch": None,
                 "headroom": 2.00},
    "partk": {"name": "Part K", "riser": (None, 0.22),
              "tread": (0.22, None), "blondel": (0.55, 0.70),
              "width": None, "flight": None, "pitch": 42.0,
              "headroom": 2.00},
    "irc": {"name": "IRC", "riser": (None, 7.75 * IN),
            "tread": (10 * IN, None), "blondel": None,
            "width": 36 * IN, "flight": ("rise", 151 * IN), "pitch": None,
            "headroom": 80 * IN},
}
#: the choices in the window (the first: by the language and the units)
CHOICES = (("auto", N_("Auto")), ("nbr9050", "NBR 9050"),
           ("nbr9077", N_("NBR 9077 (exits)")), ("din18065", "DIN 18065"),
           ("partk", "UK Part K"), ("irc", "IRC (US)"))
#: a margin for the numbers' rounding (0.1 mm)
EPS = 1e-4


def auto_rule(lang: str, imperial: bool) -> str:
    """The code by the document's units and ArchXQ's language: feet →
    IRC; Portuguese → NBR 9050; German → DIN 18065; else UK Part K."""
    if imperial:
        return "irc"
    if lang.startswith("pt"):
        return "nbr9050"
    if lang.startswith("de"):
        return "din18065"
    return "partk"


def chosen() -> str:
    """The user's choice (Settings, for every project): «auto» or a key."""
    try:
        from . import prefs
        v = str(prefs.get("stair_code"))
    except Exception:  # noqa: BLE001 — no Qt (tests)
        return "auto"
    return v if v == "auto" or v in RULES else "auto"


def auto_rule_now() -> str:
    """«Auto» for this document and this ArchXQ."""
    try:
        from . import compat, i18n
        return auto_rule(i18n.current(), compat.imperial())
    except Exception:  # noqa: BLE001
        return "partk"


def current() -> str:
    """The code in force: the choice, or the automatic one."""
    v = chosen()
    return auto_rule_now() if v == "auto" else v


def flights(s: dict) -> list[int]:
    """The risers of each flight (``stairs.steps``)."""
    return [m for m in (s["n1"], s["n2"]) if m]


def _in(v: float, lo, hi) -> bool:
    return (lo is None or v >= lo - EPS) and (hi is None or v <= hi + EPS)


def _span(lo, hi, f) -> str:
    if lo is not None and hi is not None:
        return f"{f(lo)}–{f(hi)}"
    return f"≤ {f(hi)}" if lo is None else f"≥ {f(lo)}"


def check(r: dict, s: dict, key: str, headroom: float | None = None,
          fmt_cm=None, fmt_len=None) -> list[tuple[bool, str]]:
    """The stair ``r`` (its steps ``s``) against code ``key``: a list of
    (ok, line) — «Riser 17.5 cm (16–18)». ``headroom``: the least clear
    height over its treads (``headroom_of``), None = not known."""
    from .i18n import tr
    rule = RULES[key]
    cm = fmt_cm or (lambda m: f"{m * 100:.1f}".rstrip("0").rstrip(".") + " cm")
    ln = fmt_len or (lambda m: f"{m:.2f} m")
    h, p = abs(s["h"]), s["p"]
    out = []
    if rule["riser"]:
        lo, hi = rule["riser"]
        out.append((_in(h, lo, hi), tr("Riser {v} ({lim})", v=cm(h),
                                       lim=_span(lo, hi, cm))))
    if rule["tread"] and s["n"] > 1:
        lo, hi = rule["tread"]
        out.append((_in(p, lo, hi), tr("Tread {v} ({lim})", v=cm(p),
                                       lim=_span(lo, hi, cm))))
    if rule["blondel"] and s["n"] > 1:
        lo, hi = rule["blondel"]
        v = 2 * h + p
        out.append((_in(v, lo, hi), tr("2 R + T = {v} ({lim})", v=cm(v),
                                       lim=_span(lo, hi, cm))))
    if rule["pitch"] and p > 0:
        a = math.degrees(math.atan2(h, p))
        out.append((a <= rule["pitch"] + 0.05,
                    tr("Pitch {v}° (≤ {lim}°)", v=f"{a:.1f}",
                       lim=f"{rule['pitch']:.0f}")))
    if rule["width"]:
        w = float(r.get("w", 0.0))
        out.append((w >= rule["width"] - EPS,
                    tr("Width {v} (≥ {lim})", v=ln(w),
                       lim=ln(rule["width"]))))
    if rule["flight"]:
        kind, lim = rule["flight"]
        ms = flights(s)
        if kind == "rise":
            v = max(ms) * h
            out.append((v <= lim + EPS,
                        tr("Flight rises {v} (a landing every {lim})",
                           v=ln(v), lim=ln(lim))))
        else:
            v = max(ms)
            out.append((v <= lim, tr("Flight of {v} risers (≤ {lim})",
                                     v=str(v), lim=str(lim))))
    if rule["headroom"] and headroom is not None:
        out.append((headroom >= rule["headroom"] - EPS,
                    tr("Headroom {v} (≥ {lim})", v=ln(headroom),
                       lim=ln(rule["headroom"]))))
    return out


def summary(lines: list, key: str) -> tuple[bool, str]:
    """One line: «✓ NBR 9050» or «2 of 6 outside DIN 18065»."""
    from .i18n import tr
    bad = sum(1 for ok, _t in lines if not ok)
    name = RULES[key]["name"]
    if not bad:
        return True, tr("Within {code}", code=name)
    return False, tr("{n} of {m} outside {code}", n=str(bad),
                     m=str(len(lines)), code=name)


def first_bad(lines: list) -> str | None:
    """The first line outside the code (the tool's label), or None."""
    return next((t for ok, t in lines if not ok), None)


# ---- the headroom: a beam over the treads ----------------------------------------------
def tread_boxes(ps: list) -> list:
    """Each tread of the flights laid out (``stairs.layout``): (its plan
    corners, the height of its top)."""
    out = []
    for pc in ps:
        m = int(pc.get("m", 0) or 0)
        if not pc.get("run", True) or m < 2:
            continue
        (cx, cy), (dx, dy) = pc["c"], pc["d"]
        rx, ry = dy, -dx
        hw, p, h = pc["w"] / 2, pc["p"], pc["h"]
        for j in range(m - 1):
            a, b = j * p, (j + 1) * p
            corners = [(cx + dx * a + rx * hw, cy + dy * a + ry * hw),
                       (cx + dx * b + rx * hw, cy + dy * b + ry * hw),
                       (cx + dx * b - rx * hw, cy + dy * b - ry * hw),
                       (cx + dx * a - rx * hw, cy + dy * a - ry * hw)]
            out.append((corners, pc["z0"] + (j + 1) * h))
    return out


def headroom_of(ps: list, beams: list) -> float | None:
    """The least clear height between a tread and a beam crossing over it
    — ``beams``: (its plan outline, its underside). None: no beam over any
    tread (the slab above is open over the whole stair: its well)."""
    if not beams:
        return None
    try:
        from shapely.geometry import Polygon
    except Exception:  # noqa: BLE001
        return None
    best = None
    shapes = []
    for outline, under in beams:
        try:
            shapes.append((Polygon(outline), under))
        except Exception:  # noqa: BLE001
            continue
    for corners, z in tread_boxes(ps):
        t = Polygon(corners)
        for b, under in shapes:
            if under <= z + 0.01:          # under the tread: not over it
                continue
            if b.intersection(t).area < 1e-4:
                continue
            v = under - z
            best = v if best is None else min(best, v)
    return best


def beams_over(doc: dict, elevations, zs: float, ze: float) -> list:
    """The beams whose underside is over the stair's climb (between its
    bottom and 3 m over its top): (plan outline, underside)."""
    from . import ramps as R
    from . import structure as S
    from . import walls as W
    zs_of = R.level_z(doc, elevations)
    lvs = {lv["id"]: lv for lv in doc.get("levels") or []}
    lo, hi = min(zs, ze), max(zs, ze) + 3.0
    out = []
    for e in doc.get("structure") or []:
        if e.get("type") != "beam" or S.why_not(e) is not None:
            continue
        li = lvs.get(e.get("level"))
        if li is None:
            continue
        under = S.beam_top(e, zs_of[li["id"]], li) - float(e["h"])
        if not lo < under < hi:
            continue
        for pieces in W.plan([S.as_wall(e, shrink=0.0)]).values():
            out += [(pc["outer"], under) for pc in pieces]
    return out
