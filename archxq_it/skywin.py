# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The SKY window — opened by the arrow of the «Sky» chip on the view bar
(PLANO_FUNDO_HDRI.md, H2). Many skies in sight, by family (no list hidden
behind a button), ★ favourites, your own; Rotation, Exposure, Horizon and
the Ground. The Lite shows its default sky and what the Pro adds.

Everything here is the VIEW: no undo step, the file not marked unsaved.
"""
from __future__ import annotations

import concurrent.futures
import os
import queue

from PySide6.QtCore import QPoint, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import edition, skyimg, skyview
from .i18n import tr
from .style import BLUE

TW, TH = 136, 68              # a card's picture (2:1, like the sky)
COLS = 4
_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4,
                                              thread_name_prefix="axq-skythumb")

CSS = f"""
QFrame#axq_skywin {{ background: rgb(36, 39, 44); border-radius: 8px;
    border: 1px solid rgba(255,255,255,40); }}
QLabel {{ color: #d6d9dd; background: transparent; }}
QLabel#axq_skytitle {{ color: #f3f4f6; font-weight: bold; font-size: 14px; }}
QLabel#axq_skynote {{ color: #9aa5b1; }}
QLabel#axq_skywarn {{ color: #ffc27a; }}
QPushButton[axq="skytab"] {{ color: #d6d9dd; background: rgba(255,255,255,18);
    border: none; border-radius: 4px; padding: 3px 9px; }}
QPushButton[axq="skytab"]:hover {{ background: rgba(255,255,255,40); }}
QPushButton[axq="skytab"]:checked {{ background: {BLUE}; color: white; }}
QToolButton[axq="skycard"] {{ color: #cfd6de; background: transparent;
    border: 2px solid transparent; border-radius: 5px; padding: 2px; }}
QToolButton[axq="skycard"]:hover {{ background: rgba(255,255,255,22); }}
QToolButton[axq="skycard"]:checked {{ border: 2px solid #f07d14; }}
QToolButton[axq="skystar"] {{ color: #ffd24d; background: rgba(0,0,0,90);
    border: none; border-radius: 3px; font-size: 13px; padding: 0 2px; }}
QScrollArea {{ background: transparent; border: none; }}
QWidget#axq_skygrid {{ background: transparent; }}
"""


class SkyWindow(QFrame):
    def __init__(self, ui) -> None:
        super().__init__(ui.window, Qt.Popup | Qt.FramelessWindowHint)
        self.ui = ui
        self.cat = skyview._pro()
        self.setObjectName("axq_skywin")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet(CSS)
        self._q: queue.Queue = queue.Queue()
        self._cards: dict = {}            # sky -> QToolButton
        self._tick = QTimer(self)
        self._tick.setInterval(120)
        self._tick.timeout.connect(self._drain)
        self._jobs = 0
        self._offline = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        head = QHBoxLayout()
        t = QLabel(tr("Sky"))
        t.setObjectName("axq_skytitle")
        head.addWidget(t)
        sub = QLabel(tr("behind the 3D view"))
        sub.setObjectName("axq_skynote")
        head.addWidget(sub)
        head.addStretch(1)
        from .help import help_button
        head.addWidget(help_button("sky", self))
        lay.addLayout(head)
        self.warn = QLabel("")
        self.warn.setObjectName("axq_skywarn")
        self.warn.setWordWrap(True)
        self.warn.hide()
        lay.addWidget(self.warn)
        if self.cat is None:
            self._lite(lay)
        else:
            self._pro(lay)
        self.status = QLabel("")
        self.status.setObjectName("axq_skynote")
        self.status.setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(self.status, 1)
        self.again = QPushButton(tr("Try again"))
        self.again.setProperty("axq", "skytab")
        self.again.clicked.connect(lambda: (skyview.retry(self.ui), self.status_changed()))
        self.again.hide()
        row.addWidget(self.again)
        lay.addLayout(row)
        self.status_changed()

    # ---- the Lite -------------------------------------------------------------------
    def _lite(self, lay) -> None:
        g = QHBoxLayout()
        b = self._card(skyview.BUILTIN, tr("Default sky"))
        g.addWidget(b)
        g.addStretch(1)
        lay.addLayout(g)
        self._thumb_builtin(b)
        b.setChecked(True)
        b.clicked.connect(lambda: skyview.write(self.ui, on=True))
        note = QLabel(tr("ArchXQ IT Pro adds more than 600 skies from Poly Haven "
                         "and your own pictures, with rotation, exposure, horizon "
                         "and the picture's own ground."))
        note.setObjectName("axq_skynote")
        note.setWordWrap(True)
        note.setFixedWidth(COLS * (TW + 14))
        lay.addWidget(note)
        more = QPushButton(tr("About ArchXQ IT Pro…"))
        more.setProperty("axq", "skytab")
        more.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(edition.PRO_URL)))
        lay.addWidget(more, 0, Qt.AlignLeft)

    # ---- the Pro --------------------------------------------------------------------
    def _pro(self, lay) -> None:
        st = skyview.read(self.ui)
        self.tabs = QButtonGroup(self)
        self.tabs.setExclusive(True)
        bar = QHBoxLayout()
        bar.setSpacing(3)
        self._tab_keys = []
        names = [("fav", "★ " + tr("Favourites"))] if skyview.favs() else []
        names.append(("default", tr("Default")))
        names += [(fam, skyview.family_label(fam)) for fam, _items in self.cat.families()]
        names.append(("own", tr("Your skies")))
        rows = [QHBoxLayout(), QHBoxLayout()]
        for n, (key, text) in enumerate(names):
            b = QPushButton(text.replace("&", "&&"))     # (not a shortcut)
            b.setProperty("axq", "skytab")
            b.setCheckable(True)
            b.setFocusPolicy(Qt.NoFocus)
            self.tabs.addButton(b, n)
            self._tab_keys.append(key)
            rows[0 if n < 5 else 1].addWidget(b)
        for r in rows:
            r.addStretch(1)
            r.setSpacing(3)
            lay.addLayout(r)
        self.tabs.idClicked.connect(lambda i: self._show_tab(self._tab_keys[i]))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFixedSize(COLS * (TW + 14) + 18, 3 * (TH + 34) + 6)
        lay.addWidget(self.scroll)
        # the sliders
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        self.rot = self._slider(grid, 0, tr("Rotation"), 0, 359, int(round(st["rot"])),
                                lambda v: f"{v}°")
        self.rot.valueChanged.connect(lambda v: skyview.write(self.ui, rot=float(v)))
        self.exp = self._slider(grid, 1, tr("Exposure"), -6, 6, int(round(st["exp"] * 2)),
                                lambda v: f"{v / 2:+.1f}")
        self.exp.sliderReleased.connect(self._exp_set)
        self.exp.valueChanged.connect(lambda _v: None if self.exp.isSliderDown()
                                      else self._exp_set())
        self.hor = self._slider(grid, 2, tr("Horizon"), -20, 20, int(round(st["horizon"] * 2)),
                                lambda v: f"{v / 2:+.1f}°")
        self.hor.valueChanged.connect(lambda v: skyview.write(self.ui, horizon=v / 2.0))
        lab = QLabel(tr("Ground"))
        grid.addWidget(lab, 3, 0)
        gl = QHBoxLayout()
        self.ground = QButtonGroup(self)
        for n, (key, text, tip) in enumerate((
                ("host", tr("Plain"), tr("The sky above the horizon; below it, a plain "
                                         "ground in the picture's tone (best with a terrain)")),
                ("photo", tr("Photo"), tr("The whole picture, its own ground too")))):
            b = QPushButton(text)
            b.setProperty("axq", "skytab")
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setChecked(st["ground"] == key)
            self.ground.addButton(b, n)
            gl.addWidget(b)
        gl.addStretch(1)
        self.ground.idClicked.connect(
            lambda i: skyview.write(self.ui, ground=("host", "photo")[i]))
        grid.addLayout(gl, 3, 1, 1, 2)
        lay.addLayout(grid)
        # the tab that has the sky in use
        want = "default" if st["sky"] == skyview.BUILTIN else (
            "own" if st["sky"].startswith("own/") else None)
        if want is None:
            it = self.cat.find(st["sky"])
            fams = [f for f, items in self.cat.families() if it in items]
            want = fams[0] if fams else "default"
        self._show_tab(want)

    def _slider(self, grid, row, text, lo, hi, val, fmt):
        grid.addWidget(QLabel(text), row, 0)
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        s.setFixedWidth(330)
        grid.addWidget(s, row, 1)
        v = QLabel(fmt(val))
        v.setMinimumWidth(52)
        grid.addWidget(v, row, 2)
        s.valueChanged.connect(lambda x: v.setText(fmt(x)))
        return s

    def _exp_set(self) -> None:
        skyview.write(self.ui, exp=self.exp.value() / 2.0)
        self.status_changed()

    def _show_tab(self, key: str) -> None:
        i = self._tab_keys.index(key) if key in self._tab_keys else 0
        b = self.tabs.button(i)
        if b is not None and not b.isChecked():
            b.setChecked(True)
        key = self._tab_keys[i]
        body = QWidget()
        body.setObjectName("axq_skygrid")
        g = QGridLayout(body)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(4)
        g.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._cards = {}
        items = self._items(key)
        n = 0
        if key == "own":
            add = QToolButton()
            add.setProperty("axq", "skycard")
            add.setText("+\n" + tr("Add a sky…"))
            add.setFixedSize(TW + 10, TH + 28)
            add.setToolTip(tr("A 2:1 picture of a whole sky: .hdr, .jpg or .png"))
            add.clicked.connect(self._add_own)
            g.addWidget(add, 0, 0)
            n = 1
        for it in items:
            b = self._card(it["sky"], it["name"])
            b.clicked.connect(lambda _c=False, it=it: self._pick(it))
            if it["sky"].startswith("own/"):
                b.setContextMenuPolicy(Qt.CustomContextMenu)
                b.customContextMenuRequested.connect(
                    lambda _p, it=it, b=b: self._own_menu(it, b))
            g.addWidget(b, n // COLS, n % COLS)
            self._thumb(b, it)
            n += 1
        if not items and key != "own":
            empty = QLabel(tr("Click ☆ on a sky to keep it here"))
            empty.setObjectName("axq_skynote")
            g.addWidget(empty, 0, 0, 1, COLS)
        g.setRowStretch(n // COLS + 1, 1)
        self.scroll.setWidget(body)
        self._mark()

    def _items(self, key: str) -> list:
        default = {"sky": skyview.BUILTIN, "name": tr("Default sky"), "photo": False}
        if key == "default":
            return [default]
        if key == "own":
            return self.cat.own_list()
        if key == "fav":
            out = []
            own = {o["sky"]: o for o in self.cat.own_list()}
            for s in skyview.favs():
                it = default if s == skyview.BUILTIN else (self.cat.find(s) or own.get(s))
                if it is not None:
                    out.append(it)
            return out
        for fam, items in self.cat.families():
            if fam == key:
                return items
        return []

    def _card(self, sky: str, name: str) -> QToolButton:
        b = QToolButton()
        b.setProperty("axq", "skycard")
        b.setCheckable(True)
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.setIconSize(QSize(TW, TH))
        b.setFixedSize(TW + 10, TH + 28)
        short = name if len(name) <= 22 else name[:20] + "…"
        b.setText(short.replace("&", "&&"))     # (not a shortcut)
        b.setToolTip(name)
        blank = QPixmap(TW, TH)
        blank.fill(QColor("#3a4048"))
        b.setIcon(QIcon(blank))
        self._cards[sky] = b
        if self.cat is not None:
            star = QToolButton(b)
            star.setProperty("axq", "skystar")
            star.setText("★" if sky in skyview.favs() else "☆")
            star.setToolTip(tr("Favourite: kept in «★ Favourites» for all your projects"))
            star.move(TW - 14, 4)
            star.clicked.connect(lambda _c=False, s=sky, st=star: st.setText(
                "★" if skyview.toggle_fav(s) else "☆"))
        return b

    def _mark(self) -> None:
        st = skyview.read(self.ui)
        for sky, b in self._cards.items():
            b.setChecked(sky == st["sky"])
        if self.cat is not None:
            it = self.cat.find(st["sky"])
            photo_ok = st["sky"].startswith("own/") or (it is not None and it["photo"])
            pb = self.ground.button(1)
            pb.setEnabled(photo_ok or st["ground"] == "photo")
            pb.setToolTip(tr("The whole picture, its own ground too") if photo_ok else
                          tr("This sky has no ground in its picture: pick one from "
                             "Clear, Partly cloudy, Overcast, Sunrise & sunset, "
                             "City or Nature"))

    def _pick(self, it: dict) -> None:
        change = {"sky": it["sky"], "name": it["name"], "on": True}
        if not it.get("photo", True) and skyview.read(self.ui)["ground"] == "photo":
            change["ground"] = "host"
            self.ground.button(0).setChecked(True)
        skyview.write(self.ui, **change)
        self._mark()
        self.status_changed()

    # ---- thumbnails -----------------------------------------------------------------
    def _set_icon(self, b, path: str) -> None:
        img = QPixmap(path)
        if not img.isNull():
            b.setIcon(QIcon(img.scaled(TW, TH, Qt.KeepAspectRatioByExpanding,
                                       Qt.SmoothTransformation).copy(0, 0, TW, TH)))

    def _thumb_builtin(self, b) -> None:
        self._set_icon(b, skyview.BUILTIN_FILE)

    def _thumb(self, b, it: dict) -> None:
        sky = it["sky"]
        if sky == skyview.BUILTIN:
            self._thumb_builtin(b)
            return
        if sky.startswith("polyhaven/"):
            key = sky.split("/", 1)[1]
            path = self.cat.thumb_path(key)
            if os.path.isfile(path):
                self._set_icon(b, path)
                return
            work = lambda: self.cat.fetch_thumb(key)     # noqa: E731
        else:
            name = sky.split("/", 1)[1]
            path = os.path.join(skyimg.root(), "thumbs", "own_" +
                                os.path.splitext(name)[0] + ".jpg")
            if os.path.isfile(path):
                self._set_icon(b, path)
                return
            src = self.cat.source_path(sky)

            def work(src=src, path=path):
                skyimg.save_jpg(skyimg.from_file(src, 0.0, max_w=256), path)
                return path
        q = self._q

        def job():
            try:
                q.put((sky, work()))
            except Exception:  # noqa: BLE001 — offline: the blank stays
                q.put((sky, None))
        self._jobs += 1
        _POOL.submit(job)
        self._tick.start()

    def _drain(self) -> None:
        while True:
            try:
                sky, path = self._q.get_nowait()
            except queue.Empty:
                break
            self._jobs -= 1
            b = self._cards.get(sky)
            if path and b is not None:
                try:
                    self._set_icon(b, path)
                except RuntimeError:
                    pass
            elif not path and not self._offline:
                self._offline = True
                self.status_changed()
        if self._jobs <= 0:
            self._tick.stop()

    # ---- your own -------------------------------------------------------------------
    def _add_own(self) -> None:
        anchor = self.pos()
        self.hide()
        path, _f = QFileDialog.getOpenFileName(
            self.ui.window, tr("Add a sky"), "",
            tr("Sky pictures") + " (*.hdr *.jpg *.jpeg *.png *.webp)")
        self.show()
        self.move(anchor)
        if not path:
            return
        try:
            sky = self.cat.add_own(path)
        except Exception as e:  # noqa: BLE001 — said here
            msg = str(e) if isinstance(e, skyimg.SkyError) else tr(
                "The picture could not be added")
            self.status.setText(tr(msg))
            return
        self._show_tab("own")
        it = next((o for o in self.cat.own_list() if o["sky"] == sky), None)
        if it is not None:
            self._pick(dict(it, photo=True))

    def _own_menu(self, it: dict, b) -> None:
        m = QMenu(self)
        rm = m.addAction(tr("Remove from your skies"))
        if m.exec(b.mapToGlobal(QPoint(TW // 2, TH // 2))) is rm:
            if skyview.read(self.ui)["sky"] == it["sky"]:
                skyview.write(self.ui, sky=skyview.BUILTIN, name=skyview.BUILTIN_NAME)
            self.cat.remove_own(it["sky"])
            self._show_tab("own")

    # ---- the status line --------------------------------------------------------------
    def status_changed(self) -> None:
        try:
            st = skyview.effective(skyview.read(self.ui))
        except RuntimeError:
            return
        why = skyview.host_sky_off(self.ui.viewport)
        if not why and getattr(self.ui, "plan_on", False):
            why = tr("The sky shows in the 3D view, not in the plan")
        self.warn.setText(why)
        self.warn.setVisible(bool(why))
        busy = skyview.status_of(st["sky"], st["exp"])
        self.again.setVisible((st["sky"], st["exp"]) in skyview._FAILED)
        if busy:
            self.status.setText(busy)
        elif self._offline:
            self.status.setText(tr("The pictures could not be loaded. Check your "
                                   "internet connection"))
        elif st["sky"] == skyview.BUILTIN:
            self.status.setText(tr("Default sky") + " · Poly Haven, CC0")
        elif st["sky"].startswith("own/"):
            self.status.setText(st["name"] + " · " + tr("your own"))
        else:
            self.status.setText(st["name"] + " · Poly Haven, CC0")

    # ---- place and close ------------------------------------------------------------
    def show_at(self, anchor) -> None:
        self.adjustSize()
        g = anchor.mapToGlobal(QPoint(anchor.width(), 0))
        x, y = g.x() - self.width(), g.y() - self.height() - 6
        scr = anchor.screen().availableGeometry() if anchor.screen() else None
        if scr is not None:
            x = max(scr.left() + 4, min(x, scr.right() - self.width() - 4))
            y = max(scr.top() + 4, y)
        self.move(x, y)
        self.show()

    def closeEvent(self, e) -> None:
        skyview.window_closed(self)
        super().closeEvent(e)
