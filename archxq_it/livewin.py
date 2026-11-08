# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""THE LIVE WINDOW (PLANO_JANELA_AO_VIVO.md — his rule, 2026-10-31): while
an element's window is open, the model shows what it says — ONLY that
element (and what it carries: a window's hole in its wall, a wall's doors
and windows), redrawn without an undo step and without storing anything.
OK / Apply store it as always (one Ctrl+Z); Cancel puts it back as built.
«To all of them» (the selection, every wall of a type) is a choice of its
own, made on OK — it takes the time it takes, with ``busy`` showing it.

Generic: ``Live`` reads the window (``read() -> (record, material change)``)
a few times a second and, once what it says has stood still for a tick
(a number being typed is not redrawn at every key), hands it to ``draw``.
"""
from __future__ import annotations

import traceback
from contextlib import contextmanager

from PySide6.QtCore import QObject, Qt, QTimer

TICK_MS = 120           # read the window this often; redrawn once it stands


class Live(QObject):
    """Ties ``dlg`` to the model. ``read()``: what the window says now (any
    repr-able value; it raising = nothing to show yet); ``draw(*read())``:
    show it; ``back()``: the model as built again. The window's
    ``_apply_now`` (Apply, window kept open — ui._in_place) is wrapped: the
    model goes back to as built, then it is stored."""

    def __init__(self, dlg, read, draw, back) -> None:
        super().__init__(dlg)
        self.dlg, self.read, self.draw, self.back = dlg, read, draw, back
        self.on = True
        self.shown = self.seen = self._sig()      # as built
        self.timer = QTimer(self)
        self.timer.setInterval(TICK_MS)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        dlg.finished.connect(self._end)           # OK / Cancel / X / Esc
        now = getattr(dlg, "_apply_now", None)
        if callable(now):
            def applied() -> None:
                self.back()
                now()
                self.shown = self.seen = self._sig()
            dlg._apply_now = applied
        dlg._axq_live = self

    def _sig(self):
        try:
            return repr(self.read())
        except Exception:  # noqa: BLE001 — a window half filled: not yet
            return None

    def _tick(self) -> None:
        if not self.on or not self.dlg.isVisible():
            return
        s = self._sig()
        if s is None:
            return
        if s != self.seen:                # still changing: wait a tick
            self.seen = s
            return
        if s == self.shown:
            return
        self.shown = s
        try:
            self.draw(*self.read())
        except Exception:  # noqa: BLE001 — a preview never breaks the window
            traceback.print_exc()
            self.on = False
            self.back()

    def _end(self, _r=None) -> None:
        self.timer.stop()
        self.on = False
        self.back()


@contextmanager
def busy(parent, text: str):
    """A small bar while «to all of them» is applied (the host does it in
    one go: the bar only says it is working, the cursor waits)."""
    from PySide6.QtWidgets import QApplication, QProgressDialog
    bar = None
    try:
        bar = QProgressDialog(text, None, 0, 0, parent)
        bar.setWindowTitle("ArchXQ")
        bar.setWindowModality(Qt.ApplicationModal)
        bar.setMinimumDuration(0)
        bar.setCancelButton(None)
        bar.show()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        for _ in range(3):                # painted before the work starts
            QApplication.processEvents()
    except Exception:  # noqa: BLE001 — the work matters, not the bar
        bar = None
    try:
        yield
    finally:
        try:
            QApplication.restoreOverrideCursor()
        except Exception:  # noqa: BLE001
            pass
        if bar is not None:
            bar.close()
            bar.deleteLater()
