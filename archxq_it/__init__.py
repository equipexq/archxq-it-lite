"""ArchXQ for IngeTrazo — architecture workflow by phases (PROTOTYPE).

``setup(app)`` is the IngeTrazo entry point. ``reload(window)`` tears the
live UI down and rebuilds it from fresh code, without restarting the app
(development only).
"""
from __future__ import annotations

import importlib
import sys

__version__ = "0.10.3-lite"

_instance = None


def setup(app) -> None:
    # ONE ArchXQ in the window: the Pro sets an older copy / the Lite
    # aside (onecopy.py — IngeTrazo 0.5.8's Extension Manager)
    from .onecopy import claim
    if claim(app):
        _start(app)


def _start(app) -> None:
    global _instance
    # the language, once — before any text is made (i18n.py, 0.14.0)
    try:
        from PySide6.QtWidgets import QApplication
        from . import i18n
        i18n.start()
        i18n.install_auto(QApplication.instance())  # (not in English)
    except Exception:  # noqa: BLE001 — English, as before
        pass
    from .ui import ArchXQ
    _instance = ArchXQ(app)


def teardown() -> None:
    global _instance
    if _instance is not None:
        _instance.teardown()
        _instance = None
    try:
        from PySide6.QtWidgets import QApplication
        from . import i18n
        i18n.uninstall_auto(QApplication.instance())
    except Exception:  # noqa: BLE001
        pass


def reload(window) -> None:
    """Dev: drop the UI, re-import every archxq_it module, build again."""
    teardown()
    # dependencies first: a module is reloaded after the ones it imports
    import importlib.util
    for short in ("edition", "compat", "prefs", "model", "plotgeo",
                  "terrain", "walls", "roof_l",
                  "structure", "spaces",
                  "phases", "style", "survey",
                  "icons",
                  "help", "guide", "about", "updater", "dialogs", "surveydlg", "plottools", "plotedit",
                  "walltools", "walledit", "structtools", "guidetools", "ramps", "stairs", "autoslabs",
                  "openingtools", "docs",
                  "doctools", "docsdxf", "importdxf",
                  "demo",
                  "hub", "panels", "levelstrip", "outliner", "optionsbar",
                  "wallmove", "grips", "ui"):
        name = f"{__name__}.{short}"
        if importlib.util.find_spec(name) is None:
            continue                    # the Lite ships without it
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)
    from . import compat
    _start(compat.make_app(window))       # (its own menu may linger: no claim)
