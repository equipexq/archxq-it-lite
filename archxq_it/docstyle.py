# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The DOCUMENTATION STYLE — how a sheet looks, as data (his idea,
2026-10-22: «a deeper level, in the background, a saved preset»).

The beginner never sees it: the built-in style makes a good sheet in one
click. Underneath, everything is a value that can be changed: the type
(font and height ON PAPER, NBR 8402), the pens and colours, what comes on
by default, the numbering, the language of the sheets.

Three layers, the lower one wins: the OFFICE's style (a ``.axqstyle``
file, every project), THIS PROJECT's changes (``doc["docs"]["style"]``),
THIS SHEET's changes (on the sheet's own record). ``resolve`` joins them.

Pure: no Qt, no host — it runs in the tests as it is.
"""
from __future__ import annotations

import copy
import json

#: the file a style is saved to / read from (shared with the team)
FILE_KEY = "archxq_doc_style"
EXT = ".axqstyle"
#: NBR 8402: no text on a sheet under this height (mm on paper)
MIN_TEXT_MM = 2.5

EXECUTIVE_BW = {
    "name": "Executive B&W",
    "lang": "pt",
    # the type: family, height on paper (mm), weight — NBR 8402
    "text": {
        "title":   {"font": "Arial", "mm": 7.0, "bold": True},
        "subtitle": {"font": "Arial", "mm": 3.5, "bold": False},
        "room":    {"font": "Arial", "mm": 3.5, "bold": True},
        "area":    {"font": "Arial", "mm": 2.5, "bold": False},
        "level":   {"font": "Arial", "mm": 2.5, "bold": False},
        "dim":     {"font": "Arial", "mm": 2.5, "bold": False},
        "tag":     {"font": "Arial", "mm": 2.5, "bold": True},
        "heading": {"font": "Arial", "mm": 3.5, "bold": True},
        "table":   {"font": "Arial", "mm": 2.5, "bold": False},
        "label":   {"font": "Arial", "mm": 2.5, "bold": True},
        "value":   {"font": "Arial", "mm": 3.5, "bold": False},
        "note":    {"font": "Arial", "mm": 2.5, "bold": False},
    },
    # pens, mm on paper (the view's three are the host's own)
    "pens": {"cut": 0.50, "profile": 0.35, "edge": 0.18, "dim": 0.13,
             "symbol": 0.18, "border": 0.70, "hair": 0.18},
    "colors": {"ink": "#111111", "dim": "#333333", "cut_fill": "#1d1f22",
               "mute": "#555555"},
    # the rooms' colour by use (M0, 2026-10-22: a see-through picture over
    # the view — under it the view hides it)
    "room_fill": {"on": False, "opacity": 0.55,
                  "uses": {"room": "#f6e7cf", "hall": "#dcebf7",
                           "wet": "#d8f0ea", "stair": "#e6e6ea"}},
    # what a plan sheet carries by default
    "show": {"dims_out": 3,            # 0 none · 1 total · 2 · 3 rows
             "dims_in": "across",      # none · across
             "rooms": True, "room_level": True,
             "tags": True, "schedule": True, "north": True,
             "scalebar": True, "levels_key": True, "legend": True,
             "notes": True, "typical": True,
             # a section / elevation sheet
             "sec_marks": "both",      # both · left · none (level marks)
             "sec_heights": True,      # floor-to-floor dimensions
             "sec_rooms": True,        # the cut rooms' names (named ones)
             "key_plan": True,         # the key plan in the side column
             "auto_sections": True,    # A-A and B-B through the middle
             "schedule_sheet": True,   # the area schedule (A-001)
             "sched_rooms": True,      # …with each level's rooms
             "elevations": True,       # the four elevations in the set
             # a layered wall's layers where it is cut (``wallsheet``):
             # auto = 1:50 or closer · on · off
             "wall_layers": "auto",
             "wall_legend": True},     # the wall types in the side column
    "sheet": {"paper": "auto", "scale": "auto", "prefer_scale": 100,
              "papers": ["A3", "A2", "A1", "A0"],
              "scales": [50, 75, 100, 125, 200, 250, 500],
              # NBR 10068: 25 mm on the left (binding), 10 on the others
              "margin_left": 25.0, "margin": 10.0,
              "side_w": 175.0,          # the side column = the title block
              "dim_rows_mm": [9.0, 16.0, 23.0],
              "cut": 1.20},
    "names": {"prefix": "A-", "plan_group": 1,
              "plan_title": "{plan} — {level}",
              "typical_title": "{typical} ({first} – {last})",
              "section_group": 2, "elevation_group": 3, "schedule_group": 0,
              "board_group": 4,
              "section_title": "{section} {s}-{s}",
              "elevation_title": "{elevation} {side}"},
    "office": {"name": "", "line2": "", "line3": "", "logo": ""},
    "notes": None,                      # None = the language's own
}

#: the other built-in styles: only what each changes on the Executive
_VARIANTS = {
    # what a city hall reads: the cut heavy, few dimensions, no colour
    "municipal": {
        "name": "Municipal approval",
        "pens": {"cut": 0.60, "profile": 0.35, "edge": 0.13, "dim": 0.13,
                 "symbol": 0.13, "border": 0.70},
        "show": {"dims_out": 2, "dims_in": "none", "wall_layers": "off"}},
    # for the client: colour by use, the cut soft, little text
    "presentation": {
        "name": "Presentation",
        "pens": {"cut": 0.35, "profile": 0.25, "edge": 0.13, "dim": 0.10,
                 "symbol": 0.13, "border": 0.35},
        "colors": {"ink": "#2a2e33", "dim": "#5a6068", "cut_fill": "#4a4f57",
                   "mute": "#7a8088"},
        "room_fill": {"on": True, "opacity": 0.70},
        "show": {"dims_out": 1, "dims_in": "none", "tags": False,
                 "schedule": False, "notes": False, "wall_layers": "off",
                 "wall_legend": False}},
    # for the site: every dimension, thin lines, the layers always drawn
    "construction": {
        "name": "Construction",
        "pens": {"cut": 0.40, "profile": 0.25, "edge": 0.13, "dim": 0.10,
                 "symbol": 0.13, "border": 0.50},
        "colors": {"cut_fill": "#55595f"},
        "sheet": {"prefer_scale": 50},
        "show": {"dims_out": 3, "wall_layers": "on"}},
}

BUILTIN = {"executive_bw": EXECUTIVE_BW}

#: the line sets of the style window: every pen times this
PEN_SETS = {"fine": 0.75, "standard": 1.0, "heavy": 1.35}
#: the pens the style window offers (the view's three, then the sheet's)
PEN_KEYS = ("cut", "profile", "edge", "dim", "symbol", "border")

#: the words written ON the sheet, per language of the sheets
WORDS = {
    "pt": {"plan": "PLANTA BAIXA", "typical": "PAVIMENTO TIPO",
           "scale": "ESCALA", "level": "NÍVEL", "net": "ÁREA ÚTIL",
           "graphic_scale": "ESCALA GRÁFICA", "levels": "PAVIMENTOS",
           "legend": "LEGENDA", "schedule": "QUADRO DE ESQUADRIAS",
           "notes": "NOTAS", "type": "TIPO", "size": "L × H (m)",
           "sill": "PEITORIL", "qty": "QTD.", "desc": "DESCRIÇÃO",
           "door": "Porta", "window": "Janela",
           "cut_wall": "Parede cortada", "glass_guard": "Guarda-corpo",
           "PROJECT": "PROJETO", "CLIENT": "CLIENTE",
           "LOCATION": "ENDEREÇO", "DRAWING": "CONTEÚDO",
           "SCALE": "ESCALA", "DATE": "DATA", "REVISION": "REVISÃO",
           "SHEET": "FOLHA", "AUTHOR": "AUTOR", "rev_first": "Emissão inicial",
           "roof": "COBERTURA",
           "ops": {"shop": "vitrine / caixilho", "swing": "de abrir",
                   "sliding": "de correr", "casement": "de abrir",
                   "garage": "de garagem", "pivot": "pivotante",
                   "hung": "guilhotina",
                   "folding": "camarão", "awning": "maxim-ar",
                   "fixed": "fixa"},
           "uses": {"room": "Ambientes", "hall": "Halls e circulação",
                    "wet": "Sanitários", "stair": "Escadas"},
           "notes_default": [
               "1. Cotas em metros; níveis em relação ao piso do térreo (±0,00).",
               "2. Áreas de piso medidas pelas faces internas das paredes.",
               "3. Esquadrias: ver quadro; medidas do vão em osso.",
               "4. Não medir no desenho; prevalecem as cotas escritas."]},
    "en": {"plan": "FLOOR PLAN", "typical": "TYPICAL FLOOR",
           "scale": "SCALE", "level": "LEVEL", "net": "NET AREA",
           "graphic_scale": "GRAPHIC SCALE", "levels": "LEVELS",
           "legend": "LEGEND", "schedule": "DOOR & WINDOW SCHEDULE",
           "notes": "NOTES", "type": "TYPE", "size": "W × H (m)",
           "sill": "SILL", "qty": "QTY", "desc": "DESCRIPTION",
           "door": "Door", "window": "Window",
           "cut_wall": "Cut wall", "glass_guard": "Guard rail",
           "PROJECT": "PROJECT", "CLIENT": "CLIENT",
           "LOCATION": "ADDRESS", "DRAWING": "DRAWING",
           "SCALE": "SCALE", "DATE": "DATE", "REVISION": "REVISION",
           "SHEET": "SHEET", "AUTHOR": "AUTHOR", "rev_first": "First issue",
           "roof": "ROOF",
           "ops": {"shop": "shopfront", "swing": "hinged",
                   "sliding": "sliding", "casement": "casement",
                   "garage": "garage", "pivot": "pivot", "hung": "sash",
                   "folding": "folding", "awning": "awning",
                   "fixed": "fixed"},
           "uses": {"room": "Rooms", "hall": "Halls & circulation",
                    "wet": "Toilets", "stair": "Stairs"},
           "notes_default": [
               "1. Dimensions in metres; levels from the ground floor (±0.00).",
               "2. Floor areas measured to the inner faces of the walls.",
               "3. Doors & windows: see the schedule; rough openings.",
               "4. Do not scale the drawing; written dimensions prevail."]},
    "de": {"plan": "GRUNDRISS", "typical": "REGELGESCHOSS",
           "scale": "MASSSTAB", "level": "HÖHE", "net": "NUTZFLÄCHE",
           "graphic_scale": "MASSSTABSLEISTE", "levels": "GESCHOSSE",
           "legend": "LEGENDE", "schedule": "TÜR- UND FENSTERLISTE",
           "notes": "HINWEISE", "type": "TYP", "size": "B × H (m)",
           "sill": "BRÜSTUNG", "qty": "ANZ.", "desc": "BESCHREIBUNG",
           "door": "Tür", "window": "Fenster",
           "cut_wall": "Geschnittene Wand", "glass_guard": "Geländer",
           "PROJECT": "PROJEKT", "CLIENT": "BAUHERR",
           "LOCATION": "ADRESSE", "DRAWING": "INHALT",
           "SCALE": "MASSSTAB", "DATE": "DATUM", "REVISION": "INDEX",
           "SHEET": "PLAN", "AUTHOR": "VERFASSER", "rev_first": "Erstausgabe",
           "roof": "DACH",
           "ops": {"shop": "Schaufenster", "swing": "Drehflügel",
                   "sliding": "Schiebe", "casement": "Drehflügel",
                   "garage": "Garagentor", "pivot": "Schwing",
                   "hung": "Hebe",
                   "folding": "Falt", "awning": "Klapp",
                   "fixed": "Festverglasung"},
           "uses": {"room": "Räume", "hall": "Flure", "wet": "Sanitär",
                    "stair": "Treppen"},
           "notes_default": [
               "1. Maße in Metern; Höhen bezogen auf das Erdgeschoss (±0,00).",
               "2. Flächen bis zu den Innenseiten der Wände.",
               "3. Türen und Fenster: siehe Liste; Rohbaumaße.",
               "4. Nicht abgreifen; es gelten die eingeschriebenen Maße."]},
}

#: the sections' and elevations' words (PLANO_DOCUMENTACAO_CORTES.md)
_SECTION_WORDS = {
    "pt": {"section": "CORTE", "elevation": "FACHADA",
           "sides": {"S": "SUL", "E": "LESTE", "N": "NORTE", "W": "OESTE"},
           "key_plan": "PLANTA-CHAVE", "heights": "ALTURAS", "top": "TOPO",
           "area_schedule": "QUADRO DE ÁREAS",
           "rooms_by_level": "AMBIENTES POR PAVIMENTO",
           "col_level": "PAVIMENTO", "col_elev": "NÍVEL",
           "col_net": "ÁREA ÚTIL (m²)", "col_gross": "ÁREA BRUTA (m²)",
           "col_rooms": "AMBIENTES", "total": "TOTAL",
           "notes_schedule": [
               "1. Área útil: pelas faces internas das paredes.",
               "2. Área bruta: pelo contorno externo das paredes e varandas.",
               "3. Níveis em relação ao piso do térreo (±0,00)."],
           "notes_section": [
               "1. Níveis em relação ao piso do térreo (±0,00).",
               "2. Cotas verticais em metros, de piso a piso.",
               "3. Não medir no desenho; prevalecem as cotas escritas."]},
    "en": {"section": "SECTION", "elevation": "ELEVATION",
           "sides": {"S": "SOUTH", "E": "EAST", "N": "NORTH", "W": "WEST"},
           "key_plan": "KEY PLAN", "heights": "HEIGHTS", "top": "TOP",
           "area_schedule": "AREA SCHEDULE",
           "rooms_by_level": "ROOMS BY LEVEL",
           "col_level": "LEVEL", "col_elev": "ELEV.",
           "col_net": "NET AREA (m²)", "col_gross": "GROSS AREA (m²)",
           "col_rooms": "ROOMS", "total": "TOTAL",
           "notes_schedule": [
               "1. Net area: to the inner faces of the walls.",
               "2. Gross area: to the outer outline of walls and balconies.",
               "3. Levels from the ground floor (±0.00)."],
           "notes_section": [
               "1. Levels from the ground floor (±0.00).",
               "2. Vertical dimensions in metres, floor to floor.",
               "3. Do not scale the drawing; written dimensions prevail."]},
    "de": {"section": "SCHNITT", "elevation": "ANSICHT",
           "sides": {"S": "SÜD", "E": "OST", "N": "NORD", "W": "WEST"},
           "key_plan": "ÜBERSICHT", "heights": "HÖHEN", "top": "OBERKANTE",
           "area_schedule": "FLÄCHENAUFSTELLUNG",
           "rooms_by_level": "RÄUME JE GESCHOSS",
           "col_level": "GESCHOSS", "col_elev": "HÖHE",
           "col_net": "NUTZFLÄCHE (m²)", "col_gross": "BRUTTOFLÄCHE (m²)",
           "col_rooms": "RÄUME", "total": "SUMME",
           "notes_schedule": [
               "1. Nutzfläche: bis zu den Innenseiten der Wände.",
               "2. Bruttofläche: bis zum Außenumriss von Wänden und Balkonen.",
               "3. Höhen bezogen auf das Erdgeschoss (±0,00)."],
           "notes_section": [
               "1. Höhen bezogen auf das Erdgeschoss (±0,00).",
               "2. Vertikale Maße in Metern, Geschoss zu Geschoss.",
               "3. Nicht abgreifen; es gelten die eingeschriebenen Maße."]},
}
for _lang, _w in _SECTION_WORDS.items():
    WORDS[_lang].update(_w)

#: the wall types' legend, the views sheet (PLANO_DOCUMENTACAO_ESTILOS_VISTAS)
_BOARD_WORDS = {
    "pt": {"wall_types": "TIPOS DE PAREDE", "simple_wall": "Parede simples",
           "board": "FOLHA DE VISTAS"},
    "en": {"wall_types": "WALL TYPES", "simple_wall": "Plain wall",
           "board": "VIEWS SHEET"},
    "de": {"wall_types": "WANDTYPEN", "simple_wall": "Einfache Wand",
           "board": "PLANÜBERSICHT"},
}
for _lang, _w in _BOARD_WORDS.items():
    WORDS[_lang].update(_w)


#: the notes that name the unit, in a feet / inches document
_IMPERIAL_NOTES = {
    "pt": (("Cotas verticais em metros", "Cotas verticais em pés e polegadas"),
           ("Cotas em metros", "Cotas em pés e polegadas")),
    "en": (("Vertical dimensions in metres",
            "Vertical dimensions in feet and inches"),
           ("Dimensions in metres", "Dimensions in feet and inches")),
    "de": (("Vertikale Maße in Metern", "Vertikale Maße in Fuß und Zoll"),
           ("Maße in Metern", "Maße in Fuß und Zoll")),
}
#: the ground floor's level in a feet / inches document
ZERO_IN = "±0'-0\""


def _imperial_note(line: str, lang: str) -> str:
    for old, new in _IMPERIAL_NOTES.get(lang, ()):
        line = line.replace(old, new)
    return line.replace("±0,00", ZERO_IN).replace("±0.00", ZERO_IN)


def words(style: dict) -> dict:
    """The sheet's words in the style's language (English if unknown). A
    feet / inches document: no metres in them (each area says its unit)."""
    lang = style.get("lang", "pt")
    base = WORDS.get(lang, WORDS["en"])
    if not imperial():
        return base
    out = dict(base)
    for key in ("size", "col_net", "col_gross"):
        out[key] = base[key].replace(" (m²)", "").replace(" (m)", "")
    for key in ("notes_default", "notes_schedule", "notes_section"):
        out[key] = [_imperial_note(ln, lang) for ln in base[key]]
    return out


def comma(style: dict) -> bool:
    """A decimal comma (pt, de) or point (en)."""
    return style.get("lang", "pt") != "en"


def num(v: float, style: dict, dec: int = 2) -> str:
    s = f"{v:.{dec}f}"
    return s.replace(".", ",") if comma(style) else s


# ---- the document's unit (Arnon Moscona's ticket #90, 2026-11-06) --------------------
# A metres document reads exactly as before. Imported here, not at the top:
# the style stays pure, and without a host it is a metres document.
def imperial() -> bool:
    """The open document is in feet / inches."""
    try:
        from . import compat
        return bool(compat.imperial())
    except Exception:  # noqa: BLE001 — no host (the pure tests): metres
        return False


def length(v: float, style: dict) -> str:
    """A length on a sheet: «3,20» in metres, «10'6"» in feet / inches."""
    if imperial():
        from . import compat
        return compat.fmt_num(v)
    return num(v, style)


def small(v: float) -> str:
    """A small length in feet / inches, in inches: «6 7/8"»."""
    from . import compat
    return compat.fmt_cm(v)


def area(v: float, style: dict) -> str:
    """An area with its unit: «12,50 m²», «134.55 ft²»."""
    if imperial():
        from . import compat
        return compat.fmt_area(v)
    return f"{num(v, style)} m²"


def area_cell(v: float, style: dict) -> str:
    """An area in a table: its column says m²; in feet / inches, it says
    its own unit (the document may keep areas in another one)."""
    return area(v, style) if imperial() else num(v, style)


def scales(style: dict) -> list:
    """The scales a sheet picks from: the style's, or the architect's and
    the engineer's in a feet / inches document."""
    if imperial():
        from . import docs
        return sorted(docs.SCALES_IN)
    return sorted(int(s) for s in style["sheet"]["scales"])


def prefer_scale(style: dict) -> int:
    """The scale a sheet starts from: the style's, or the nearest one of
    the architect's (1:100 → 1/8", 1:96; 1:50 → 1/4", 1:48)."""
    want = int(style["sheet"].get("prefer_scale", 100))
    if imperial():
        return min(scales(style), key=lambda n: abs(n - want))
    return want


def scale_text(n) -> str:
    """«1:100», or «1/4" = 1'-0"» in a feet / inches document."""
    if imperial():
        from . import docs
        return docs.scale_label(n)
    return f"1:{n}"


def merge(base: dict, over: dict | None) -> dict:
    """``over`` laid on ``base``, dicts deep (a change of one font size
    keeps the rest of «text»); lists and values replace."""
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def resolve(office: dict | None = None, project: dict | None = None,
            sheet: dict | None = None, base: str = "executive_bw") -> dict:
    """The style a sheet is drawn with: the built-in, the office's, the
    project's changes, the sheet's changes — the lower one wins. A layer's
    «base» names the built-in underneath (the lowest layer's)."""
    for layer in (office, project, sheet):
        if (layer or {}).get("base") in BUILTIN:
            base = layer["base"]
    s = copy.deepcopy(BUILTIN.get(base, EXECUTIVE_BW))
    for layer in (office, project, sheet):
        s = merge(s, layer)
    s["base"] = base if base in BUILTIN else "executive_bw"
    return s


def with_pens(pens: dict, line_set: str) -> dict:
    """The Executive's pens times a line set («fine», «standard», «heavy»)
    — the ones a city hall or a plotter tells apart: 2 decimals, ≥ 0.05."""
    k = PEN_SETS.get(line_set, 1.0)
    return {p: max(round(float(v) * k, 2), 0.05) for p, v in pens.items()}


def looks_sig(style: dict) -> str:
    """What makes a drawn sheet look as it does (not what it carries: those
    are its own choices) — to tell a sheet made with another style."""
    return json.dumps([style.get(k) for k in ("pens", "colors", "text",
                                              "room_fill")], sort_keys=True)


def diff(base: dict, mine: dict) -> dict:
    """Only what ``mine`` changes from ``base`` — what a layer keeps."""
    out = {}
    for k, v in mine.items():
        b = base.get(k)
        if isinstance(v, dict) and isinstance(b, dict):
            d = diff(b, v)
            if d:
                out[k] = d
        elif v != b:
            out[k] = copy.deepcopy(v)
    return out


for _key, _over in _VARIANTS.items():
    BUILTIN[_key] = merge(EXECUTIVE_BW, _over)


def too_small(style: dict) -> list[str]:
    """The text kinds under the NBR 8402 minimum (2.5 mm)."""
    return [k for k, t in (style.get("text") or {}).items()
            if float(t.get("mm", 0)) < MIN_TEXT_MM - 1e-6]


def text(style: dict, kind: str) -> dict:
    """{"font", "mm", "bold"} of a kind of text (a missing kind: «note»)."""
    t = style["text"].get(kind) or style["text"]["note"]
    return {"font": t.get("font", "Arial"), "mm": float(t.get("mm", 2.5)),
            "bold": bool(t.get("bold", False))}


# ---- the file -----------------------------------------------------------------------
def dumps(style: dict, name: str = "") -> str:
    return json.dumps({FILE_KEY: 1, "name": name or style.get("name", ""),
                       "style": style}, ensure_ascii=False, indent=1)


def loads(raw: str) -> dict:
    """A style file's style (laid on the built-in: a file of an older
    version gets the keys it lacks). ValueError when it is not one."""
    data = json.loads(raw)
    if not isinstance(data, dict) or FILE_KEY not in data \
            or not isinstance(data.get("style"), dict):
        raise ValueError("not an ArchXQ documentation style")
    return merge(BUILTIN.get(data["style"].get("base"), EXECUTIVE_BW),
                 data["style"])
