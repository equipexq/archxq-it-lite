"""ONE ArchXQ in IngeTrazo (2026-10-12, IngeTrazo 0.5.8's Extension
Manager).

The Lite is in the community catalog as ``archxq_it``; the Pro used to
unzip into a folder of that same name — and the manager then offered
«Replace with the catalog version» over a buyer's Pro (it would have put
the Lite 0.9.5 in its place). From 0.9.7.1 the Pro's folder is
``archxq_it_pro``. So that a buyer who just unzips the new one does not
end with TWO copies loaded, the Pro sets the other one aside by itself
(his rule: prevent the user's error, don't hand him instructions):

- a copy installed by hand (an older Pro, a Lite from GitHub): renamed
  with a dot in front — IngeTrazo's own convention, the loader skips
  it, nothing is deleted;
- a Lite installed by the manager: disabled the manager's way
  (``.disabled``), so the manager still shows it and can enable it.

And should another ArchXQ already run in this window (it loaded first),
this one builds nothing: a restart finishes the change.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

OLD = "archxq_it"             # the Lite's id; the Pro's folder until 0.9.6
PRO = "archxq_it_pro"


def _running(window) -> bool:
    """An ArchXQ already in the window (its submenu in Extensions)."""
    from PySide6.QtWidgets import QMenu
    return any(m.title().replace("&", "").strip() == "ArchXQ"
               for m in window.findChildren(QMenu))


LITE = "archxq_it_lite"      # the Lite's catalog id, if it is renamed


def _step_aside(here: Path) -> list[str]:
    """The Pro's folder: the other copies beside it set aside. What was
    done."""
    if here.name != PRO:
        return []                 # the Lite, the developer's loader: nothing
    done = []
    for name in (OLD, LITE):
        done += _aside_one(here.parent / name)
    return done


def _aside_one(other: Path) -> list[str]:
    if not other.is_dir() or other.is_symlink():
        return []
    if (other / "extension.json").is_file():          # the manager's Lite
        mark = other / ".disabled"
        if mark.exists():
            return []
        mark.write_text("", encoding="utf-8")
        return ["the ArchXQ IT Lite was disabled (Extensions ▸ Manage "
                "extensions can enable it again)"]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    aside = other.with_name(f".{other.name}.manual-{stamp}")
    other.replace(aside)
    return [f"the older copy was set aside as «{aside.name}» (not deleted)"]


def claim(app) -> bool:
    """True: this copy runs. False: another ArchXQ runs already — this one
    stays out until IngeTrazo restarts."""
    here = Path(__file__).resolve().parent
    try:
        done = _step_aside(here)
    except OSError:
        done = []
    try:
        busy = _running(app.window)
    except Exception:  # noqa: BLE001
        busy = False
    if done or busy:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QMessageBox
        if done:
            text = ("ArchXQ IT Pro is installed in its own folder now.\n\n"
                    + "".join(f"• {d[:1].upper()}{d[1:]}.\n" for d in done)
                    + "\nRestart IngeTrazo to finish.")
        else:
            text = ("Another copy of ArchXQ is already running, so this one "
                    f"(«{here.name}») stays off.\n\nKeep only one ArchXQ in "
                    "the plugins folder (Extensions ▸ Open plugins folder).")
        QTimer.singleShot(1500, lambda: QMessageBox.information(
            app.window, "ArchXQ IT", text))
    return not busy
