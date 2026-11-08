# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A card in the middle of a window while a sheet's views are prepared and drawn
(his idea, 2026-11-04: a project of 40, 50, 60 levels waits minutes; a line in
the status bar is not enough). How far, about how long, and a way to stop.

It does not block anything: a child of the window it stands on, the window
answering as before."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QVBoxLayout)

from .i18n import tr

#: fewer views than this are over before a card would help
MIN_VIEWS = 3

CSS = """
QFrame#axqProgress { background: #20242b; border: 1px solid #2f7df6;
                     border-radius: 8px; }
QFrame#axqProgress QLabel { color: #e8ebf0; background: transparent;
                            border: none; }
QFrame#axqProgress QLabel#axqProgressInfo { color: #aab2bd; }
QFrame#axqProgress QProgressBar { background: #343a44; border: none;
                                  border-radius: 4px; max-height: 8px;
                                  min-height: 8px; }
QFrame#axqProgress QProgressBar::chunk { background: #2f7df6;
                                         border-radius: 4px; }
QFrame#axqProgress QPushButton { background: #343a44; color: #e8ebf0;
                                 border: none; border-radius: 4px;
                                 padding: 4px 14px; }
QFrame#axqProgress QPushButton:hover { background: #2f7df6; }
"""


def left_text(elapsed: float, done: int, total: int) -> str:
    """«about 40 s left», once two steps give an idea of the pace."""
    if done < 2 or done >= total:
        return ""
    s = elapsed / done * (total - done)
    if s < 60:
        return tr("about {s} s left", s=max(int(round(s / 5.0) * 5), 5))
    return tr("about {m} min left", m=int(round(s / 60.0)))


class ProgressCard(QFrame):
    """``step(title, done, total)`` shows it; ``finish()`` takes it away."""

    def __init__(self, host, on_stop) -> None:
        super().__init__(host)
        self.setObjectName("axqProgress")
        self.setStyleSheet(CSS)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedSize(380, 112)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)
        self.title = QLabel()
        f = self.title.font()
        f.setBold(True)
        self.title.setFont(f)
        lay.addWidget(self.title)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        lay.addWidget(self.bar)
        row = QHBoxLayout()
        self.info = QLabel()
        self.info.setObjectName("axqProgressInfo")
        row.addWidget(self.info, 1)
        self.stop = QPushButton(tr("Stop"))
        self.stop.setCursor(Qt.PointingHandCursor)
        self.stop.clicked.connect(on_stop)
        row.addWidget(self.stop)
        lay.addLayout(row)
        self._phase = None
        self._t0 = 0.0
        self.hide()

    def step(self, title: str, done: int, total: int) -> None:
        if self._phase != (title, total):       # a new stretch: its own pace
            self._phase = (title, total)
            self._t0 = time.monotonic()
        self.title.setText(title)
        self.bar.setRange(0, max(total, 1))
        self.bar.setValue(done)
        text = tr("{i} of {n} views", i=done, n=total)
        left = left_text(time.monotonic() - self._t0, done, total)
        self.info.setText(f"{text}  ·  {left}" if left else text)
        host = self.parentWidget()
        if host is not None:
            self.move(max((host.width() - self.width()) // 2, 0),
                      max((host.height() - self.height()) // 2, 0))
        self.show()
        self.raise_()

    def finish(self) -> None:
        self._phase = None
        self.hide()
