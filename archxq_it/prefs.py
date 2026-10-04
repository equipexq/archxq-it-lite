"""ArchXQ preferences — the USER's, for every project (QSettings), not the
document's. Read with ``get``; the Settings dialog writes them."""
from __future__ import annotations

from PySide6.QtCore import QSettings

#: key → (default, kind)
DEFAULTS: dict[str, tuple[object, type]] = {
    # Display
    "plot_dims": ("terrain", str),       # off | terrain | always
    "live_dims": (True, bool),           # measurements while drawing
    "diag_pull": (True, bool),           # 45° pull while drawing
    "plan_on_tool": (True, bool),        # a drawing tool starts in plan view
    "plan_hidden_line": (True, bool),    # the plan seen in hidden line
    "plan_grid": (True, bool),           # a grid + the axes in the plan
    "grid_snap": (False, bool),          # the cursor on the plan's grid
    # Warnings
    "warn_setbacks": (True, bool),       # an excavation into the setbacks
    # Defaults for new things
    "ground_thickness": (0.50, float),   # m, under the plot
    "floor_height": (3.00, float),       # m, a new storey
}

PLOT_DIMS = {"off": "Off",
             "terrain": "In the Terrain phase",
             "always": "Always (while ArchXQ is on)"}


def get(key: str):
    default, kind = DEFAULTS[key]
    raw = QSettings().value(f"archxq/prefs/{key}", default)
    try:
        if kind is bool:
            return raw if isinstance(raw, bool) else str(raw).lower() in (
                "1", "true", "yes")
        return kind(raw)
    except (TypeError, ValueError):
        return default


def put(key: str, value) -> None:
    QSettings().setValue(f"archxq/prefs/{key}", value)


def reset() -> None:
    s = QSettings()
    for key in DEFAULTS:
        s.remove(f"archxq/prefs/{key}")
