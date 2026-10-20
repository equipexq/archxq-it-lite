"""ArchXQ in other LANGUAGES (0.14.0 — PLANO_IDIOMAS.md; Germany and Brazil
are where it sells most).

``tr("Wall")`` gives the text in the language chosen; the KEY is the
English text itself, so English needs no catalogue and a text with no
translation yet stays in English — never empty. Numbers go in by name:
``tr("{n} walls", n=3)``.

The catalogues are ``lang/<code>.json`` (the same form as IngeTrazo's own
``_internal/i18n/*.json``): ``{"English text": "translation"}``; an empty
translation = not translated yet (``tools/i18n_extract.py`` adds the new
texts of each version that way).

The language: Settings ▸ Language — «Auto» follows IngeTrazo's own
(``core.i18n.current_language()``). It is read ONCE, when ArchXQ starts:
a change takes effect when IngeTrazo is restarted (rebuilding the live
interface in place is not safe).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

#: code → the name shown in Settings (in its own language)
LANGUAGES = {"en": "English", "pt-BR": "Português (Brasil)",
             "de": "Deutsch"}
LANG_DIR = Path(__file__).with_name("lang")

_lang: str | None = None
_cat: dict[str, str] = {}


def host_language() -> str:
    """IngeTrazo's own language, as one of ours («en» if it is another)."""
    try:
        from core import i18n as host
        code = str(host.current_language() or "en")
    except Exception:  # noqa: BLE001 — an older IngeTrazo
        return "en"
    if code in LANGUAGES:
        return code
    if code.startswith("pt"):
        return "pt-BR"
    if code.startswith("de"):
        return "de"
    return "en"


def chosen() -> str:
    """The language picked in Settings: «auto» or a code."""
    try:
        from . import prefs
        v = str(prefs.get("language"))
    except Exception:  # noqa: BLE001 — no Qt (tests)
        return "auto"
    return v if v == "auto" or v in LANGUAGES else "auto"


def resolve(choice: str | None = None) -> str:
    choice = chosen() if choice is None else choice
    return host_language() if choice == "auto" else choice


def load(code: str) -> dict:
    """A catalogue (only the texts translated)."""
    if code == "en":
        return {}
    try:
        raw = json.loads((LANG_DIR / f"{code}.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in raw.items()
            if isinstance(k, str) and isinstance(v, str) and v.strip()}


def start(code: str | None = None) -> str:
    """Read the language and its catalogue — once, as ArchXQ starts (and
    in tests, with a code)."""
    global _lang, _cat
    _lang = resolve() if code is None else code
    _cat = load(_lang)
    _done.clear()
    for v in _cat.values():
        _done.update(p.strip() for p in _JOINTS.split(v))
        _done.add(v)
    return _lang


def current() -> str:
    if _lang is None:
        start()
    return _lang or "en"


# ---- the interface translated as it is SHOWN --------------------------------------
#: a combo box item's ENGLISH text, kept when its words are translated
RAW_ROLE = 0x0100 + 77                     # Qt.UserRole + 77


def raw_text(combo, i: int | None = None) -> str:
    """A combo box's choice as the code knows it — in English, whatever
    the language shown (``currentText()`` would give the translation)."""
    i = combo.currentIndex() if i is None else i
    v = combo.itemData(i, RAW_ROLE)
    return v if isinstance(v, str) else combo.itemText(i)


#: an ArchXQ widget: it, or a parent, has one of these object names (the
#: dock, the bars, the windows dressed by look.py — all «axq…»)
_OURS = ("axq", "extension_archxq")
_PROP = "_axq_tr"                 # a widget already gone through


def _ours(w) -> bool:
    k = 0
    while w is not None and k < 40:
        n = w.objectName() or ""
        if n.startswith(_OURS) or w.property("axq_root"):
            return True
        w, k = w.parentWidget(), k + 1
    return False


def _t(s: str) -> str | None:
    """The translation of exactly this text, or None."""
    if not s:
        return None
    v = _cat.get(s)
    if v is None:
        st = s.strip()
        v = _cat.get(st)
        if v is not None and st != s:      # keep the spaces round it
            v = s.replace(st, v)
    if v is None and "&&" in s:            # Qt's «&» written «&&» in a tab
        v = _cat.get(s.replace("&&", "&").strip())
        if v is not None:
            v = v.replace("&", "&&")
    return v


def translate_widget(w) -> None:
    """Its texts swapped for their translation (exact matches only)."""
    from PySide6.QtWidgets import (QAbstractButton, QComboBox, QGroupBox,
                                   QLabel, QLineEdit, QTabBar)
    try:
        for get, put in ((w.toolTip, w.setToolTip),
                         (w.windowTitle, w.setWindowTitle)):
            v = _t(get())
            if v is not None:
                put(v)
        if isinstance(w, (QAbstractButton, QLabel)):
            s = w.text()
            v = tr_parts(s)
            if v != s:
                w.setText(v)
            w.setProperty(_PROP, v)       # (seen: a repaint skips it)
        elif isinstance(w, QGroupBox):
            v = _t(w.title())
            if v is not None:
                w.setTitle(v)
        elif isinstance(w, QLineEdit):
            v = _t(w.placeholderText())
            if v is not None:
                w.setPlaceholderText(v)
        elif isinstance(w, QComboBox):
            for i in range(w.count()):
                s = w.itemText(i)
                v = _t(s)
                if v is not None:
                    # the English kept: code that reads the choice as DATA
                    # asks ``raw_text`` (never the translated words)
                    w.setItemData(i, s, RAW_ROLE)
                    w.setItemText(i, v)
        elif isinstance(w, QTabBar):
            for i in range(w.count()):
                v = _t(w.tabText(i))
                if v is not None:
                    w.setTabText(i, v)
                v = _t(w.tabToolTip(i))
                if v is not None:
                    w.setTabToolTip(i, v)
        from PySide6.QtWidgets import QWidget
        # (Qt's own: a panel of ours may have an «actions» of its own)
        for a in QWidget.actions(w):
            for get, put in ((a.text, a.setText), (a.toolTip, a.setToolTip)):
                v = _t(get())
                if v is not None:
                    put(v)
    except Exception:  # noqa: BLE001 — never break the interface for a text
        pass


def translate_tree(root) -> None:
    from PySide6.QtWidgets import QWidget
    translate_widget(root)
    for c in root.findChildren(QWidget):
        translate_widget(c)


_auto = None


def install_auto(app) -> None:
    """Every ArchXQ widget translated when it is shown — and a tooltip when
    it pops up (set later by the code). Only when the language is not
    English; the texts the code BUILDS (numbers in them) need ``tr()``."""
    global _auto
    if _auto is not None or current() == "en" or not _cat:
        return
    from PySide6.QtCore import QEvent, QObject

    from PySide6.QtWidgets import QAbstractButton, QLabel
    SHOW, TIP, PAINT = QEvent.Show, QEvent.ToolTip, QEvent.Paint
    mine: dict = {}                       # id(widget) → ours?

    def ours(obj) -> bool:
        k = id(obj)
        v = mine.get(k)
        if v is None:
            v = mine[k] = _ours(obj)
            if len(mine) > 20000:
                mine.clear()
        return v

    class _Auto(QObject):
        def eventFilter(self, obj, ev):  # noqa: N802 — Qt's name
            t = ev.type()                  # (every event of the app: be quick)
            if t != SHOW and t != TIP and t != PAINT:
                return False
            try:
                if not obj.isWidgetType() or not ours(obj):
                    return False
                if t == PAINT:
                    # a text the code set AFTER it was shown (a panel's
                    # title, a summary): seen once, translated once
                    if isinstance(obj, (QLabel, QAbstractButton)) and \
                            obj.text() != obj.property(_PROP):
                        translate_widget(obj)
                elif t == TIP:
                    v = tr_parts(obj.toolTip())
                    if v != obj.toolTip():
                        obj.setToolTip(v)
                else:                      # (each child gets its own Show)
                    translate_widget(obj)
            except Exception:  # noqa: BLE001 — never in the way
                pass
            return False
    _auto = _Auto()
    app.installEventFilter(_auto)


def uninstall_auto(app) -> None:
    global _auto
    if _auto is not None:
        try:
            app.removeEventFilter(_auto)
        except RuntimeError:
            pass
        _auto = None


#: the joints messages are built with: each piece between them is
#: translated on its own («Plot updated» + « — Ctrl+Z undoes it»)
_JOINTS = re.compile(r"(\s+·\s+| — | › |\n|<br>)")
#: a count after a name: «Doors (22)»
_COUNT = re.compile(r"^(.*?)(\s*\(\d+\))$", re.S)


def tr_parts(text: str) -> str:
    """A message built of pieces: the whole if it is translated, else each
    piece between « — », « · » and new lines that is (the rest stays)."""
    if not text or current() == "en":
        return text
    v = _t(text)
    if v is not None:
        return v
    parts = _JOINTS.split(text)
    out, hit = [], False
    for i, p in enumerate(parts):
        if i % 2:                       # a joint
            out.append(p)
            continue
        q = _t(p)
        if q is None and p:            # «Doors (22)»: the name, its count kept
            m = _COUNT.match(p)
            if m and _t(m.group(1)) is not None:
                q = _t(m.group(1)) + m.group(2)
        if q is None and p:            # the joint glued to a piece
            q = _t(" — " + p)
            q = q[3:] if q and q.startswith(" — ") else None
        out.append(q if q is not None else p)
        hit = hit or q is not None
        if q is None and len(missing) < 5000 and p not in _done \
                and re.search(r"[A-Za-z]{3}", p):
            missing.add(p)
    return "".join(out) if hit else text


#: texts met on screen with no translation (a developer's list:
#: ``i18n.missing`` read through the bridge, to translate next)
missing: set = set()
_done: set = set()               # the translations themselves (not missing)


#: a long help text's paragraphs (help.py, guide.py)
_PARAS = re.compile(r"(<br><br>)")


def tr_long(text: str) -> str:
    """A help text (HTML): whole, or paragraph by paragraph (split on
    «<br><br>») — a text joined from pieces is still translated."""
    if not text or current() == "en":
        return text
    v = _t(text)
    if v is not None:
        return v
    parts = _PARAS.split(text)
    return "".join(p if i % 2 else (_t(p) or p) for i, p in enumerate(parts))


def wrap_status(tool) -> None:
    """A tool's status line in the language (its ``status_clause``)."""
    if current() == "en" or getattr(tool, "_axq_tr_status", False):
        return
    f = getattr(tool, "status_clause", None)
    if not callable(f):
        return
    try:
        tool.status_clause = lambda f=f: tr_parts(f())
        tool._axq_tr_status = True
    except Exception:  # noqa: BLE001 — a tool that refuses: English
        pass


def N_(text: str) -> str:
    """Marks a text to translate WITHOUT translating it now — for tables
    made when a module is imported (``SLAB_SHAPES``, ``PLOT_DIMS``…): the
    extractor finds it, and the code that SHOWS it calls ``tr(text)``.
    (Rule: translate where a text is shown, never at import time.)"""
    return text


def tr(text: str, **values) -> str:
    """``text`` in the current language; ``{name}`` filled from ``values``."""
    if _lang is None:
        start()
    out = _cat.get(text, text)
    if values:
        try:
            out = out.format(**values)
        except (KeyError, IndexError, ValueError):
            out = text.format(**values)       # a broken translation: English
    return out
