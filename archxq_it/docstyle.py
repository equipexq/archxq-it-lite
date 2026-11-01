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
             "elevations": True},      # the four elevations in the set
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
              "section_title": "{section} {s}-{s}",
              "elevation_title": "{elevation} {side}"},
    "office": {"name": "", "line2": "", "line3": "", "logo": ""},
    "notes": None,                      # None = the language's own
}

BUILTIN = {"executive_bw": EXECUTIVE_BW}

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
                   "garage": "garage", "pivot": "pivot",
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


def words(style: dict) -> dict:
    """The sheet's words in the style's language (English if unknown)."""
    return WORDS.get(style.get("lang", "pt"), WORDS["en"])


def comma(style: dict) -> bool:
    """A decimal comma (pt, de) or point (en)."""
    return style.get("lang", "pt") != "en"


def num(v: float, style: dict, dec: int = 2) -> str:
    s = f"{v:.{dec}f}"
    return s.replace(".", ",") if comma(style) else s


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
    project's changes, the sheet's changes — the lower one wins."""
    s = copy.deepcopy(BUILTIN.get(base, EXECUTIVE_BW))
    for layer in (office, project, sheet):
        s = merge(s, layer)
    return s


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
    return merge(EXECUTIVE_BW, data["style"])
