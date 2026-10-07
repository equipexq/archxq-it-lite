"""ArchXQ for IngeTrazo — architecture workflow by phases (PROTOTYPE).

``setup(app)`` is the IngeTrazo entry point. ``reload(window)`` tears the
live UI down and rebuilds it from fresh code, without restarting the app
(development only).
"""
from __future__ import annotations

import importlib
import sys

__version__ = "0.9.4-lite"

_instance = None


def setup(app) -> None:
    global _instance
    from .ui import ArchXQ
    _instance = ArchXQ(app)


def teardown() -> None:
    global _instance
    if _instance is not None:
        _instance.teardown()
        _instance = None


def reload(window) -> None:
    """Dev: drop the UI, re-import every archxq_it module, build again."""
    teardown()
    # dependencies first: a module is reloaded after the ones it imports
    import importlib.util
    for short in ("edition", "compat", "prefs", "model", "plotgeo",
                  "terrain", "walls",
                  "structure", "spaces",
                  "phases", "style", "survey",
                  "icons",
                  "help", "guide", "about", "dialogs", "surveydlg", "plottools", "plotedit",
                  "walltools", "walledit", "structtools", "guidetools", "ramps", "stairs", "autoslabs",
                  "openingtools", "docs",
                  "doctools", "docsdxf", "importdxf",
                  "demo",
                  "hub", "panels", "levelstrip", "outliner", "optionsbar",
                  "ui"):
        name = f"{__name__}.{short}"
        if importlib.util.find_spec(name) is None:
            continue                    # the Lite ships without it
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)
    from . import compat
    setup(compat.make_app(window))
