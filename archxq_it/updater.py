"""UPDATE WITH ONE CLICK (his top ask, 2026-10-16; plan
PLANO_ATUALIZAR_UM_CLIQUE.md, 2026-10-18).

- **Pro** — at start (at most once a day, in a thread: never on IngeTrazo's
  own thread) it asks xq.com.br for the latest version. A newer one: an
  orange dot on «⏻ ArchXQ», a line in About, and a small notice that says
  how («Update…» / «Later»; «Later» keeps quiet until the next version).
- **Lite** — «Upgrade to Pro…» (About, the «Get Pro» bar): the buyer pastes
  the Gumroad license key and the Pro installs itself.

The site checks the key with Gumroad (api/archxq-it/license, /download);
the key travels in ``Authorization: Bearer``, never in a URL, and stays in
the user's settings so it is asked only once.

Installing NEVER swaps code in a running IngeTrazo: the new folder is put
in place and IngeTrazo asks to be restarted. The version replaced is kept
beside it as ``.archxq_it_pro.backup-<version>`` (the dot: IngeTrazo's
loader skips it — onecopy.py's convention), and «Restore previous version»
swaps them back. The zip is checked against the site's sha256 before
anything on disk is touched.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import ssl
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from . import edition

API = "https://xq.com.br/api/archxq-it"
WHATS_NEW = "https://www.xq.com.br/archxq-it/whats-new"
LIBRARY = "https://app.gumroad.com/library"
FOLDER = "archxq_it_pro"                 # the Pro's folder in the plugins
BACKUP = f".{FOLDER}.backup-"
CHECK_EVERY = 20 * 3600                  # s — about once a day
_S = "archxq/update/"


# ---- what is installed --------------------------------------------------------
def current() -> str:
    from .about import _version
    return _version()


def _vt(v: str) -> tuple:
    out = []
    for p in str(v).split("."):
        digits = "".join(c for c in p if c.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


def newer(a: str, b: str) -> bool:
    """``a`` is a later version than ``b``."""
    return _vt(a) > _vt(b)


def plugins_dir() -> Path:
    """Where IngeTrazo loads extensions from — the folder this one is in
    (ARCHXQ_UPDATE_DIR: a test folder instead)."""
    test = os.environ.get("ARCHXQ_UPDATE_DIR")
    return Path(test) if test else Path(__file__).resolve().parent.parent


def enabled() -> bool:
    """Not in the developer's source (version «dev»), unless a test asks."""
    return current() != "dev" or bool(os.environ.get("ARCHXQ_UPDATE_DIR"))


def host_version() -> str:
    from .about import _host_version
    return _host_version()


# ---- settings ----------------------------------------------------------------------
def _get(key: str, default=""):
    v = QSettings().value(_S + key, default)
    return default if v is None else v


def _put(key: str, value) -> None:
    QSettings().setValue(_S + key, value)


def saved_key() -> str:
    return str(_get("key", "")).strip()


def latest_known() -> dict:
    try:
        j = json.loads(str(_get("latest", "")) or "{}")
        return j if isinstance(j, dict) else {}
    except ValueError:
        return {}


def available() -> dict:
    """The latest version, if it is newer than this one (Pro), else {}."""
    j = latest_known()
    if edition.lite() or not j.get("version"):
        return {}
    return j if newer(j["version"], current()) else {}


# ---- the network (worker threads only) ------------------------------------------------
class UpdateError(Exception):
    pass


def _ctx():
    ctx = ssl.create_default_context()
    try:                                   # a Python without the system's CAs
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:  # noqa: BLE001
        pass
    return ctx


def _request(path: str, key: str = "") -> urllib.request.Request:
    ed = "Lite" if edition.lite() else "Pro"
    h = {"User-Agent": f"ArchXQ-IT/{current()} ({ed}; IngeTrazo "
                       f"{host_version()})",
         "Accept": "application/json",
         "X-ArchXQ-Version": f"{ed} {current()}"}
    if key:
        h["Authorization"] = f"Bearer {key}"
    return urllib.request.Request(API + path, headers=h)


def _open(req, timeout: float):
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=_ctx())
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error", "")
        except Exception:  # noqa: BLE001
            msg = ""
        raise UpdateError(msg or f"The server answered {e.code}.") from None
    except (urllib.error.URLError, OSError) as e:
        raise UpdateError("No connection to xq.com.br — check the internet "
                          f"and try again. ({getattr(e, 'reason', e)})") from None


def fetch_latest() -> dict:
    with _open(_request("/latest"), 10) as r:
        j = json.loads(r.read().decode("utf-8"))
    if not isinstance(j, dict) or not j.get("version"):
        raise UpdateError("The server's answer was not understood.")
    return j


def check_license(key: str) -> None:
    """Raises UpdateError with the site's words when the key is refused."""
    with _open(_request("/license", key), 20) as r:
        r.read()


def download(key: str, progress=None) -> tuple[Path, str]:
    """The Pro's zip into a temporary file → (path, its version)."""
    with _open(_request("/download", key), 60) as r:
        version = r.headers.get("X-XQ-Version", "")
        sha = (r.headers.get("X-XQ-SHA256", "") or "").lower()
        # (the server may send it compressed, without a length: then the
        # size the site published in latest.json)
        total = int(r.headers.get("Content-Length") or 0) \
            or int(latest_known().get("size") or 0)
        fd, name = tempfile.mkstemp(prefix="archxq_it_pro-", suffix=".zip")
        h = hashlib.sha256()
        got = 0
        with os.fdopen(fd, "wb") as f:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                got += len(chunk)
                if progress and total:
                    progress(min(got, total), total)
    path = Path(name)
    if not sha or h.hexdigest() != sha:
        path.unlink(missing_ok=True)
        raise UpdateError("The download arrived damaged — please try again.")
    return path, version


# ---- the disk ----------------------------------------------------------------------
def backups() -> list[Path]:
    d = plugins_dir()
    return sorted(d.glob(BACKUP + "*"), key=lambda p: p.stat().st_mtime,
                  reverse=True) if d.is_dir() else []


def _version_in(folder: Path) -> str:
    """The version a Pro folder carries (its __init__.py), or «?»."""
    try:
        for line in (folder / "__init__.py").read_text("utf-8").splitlines():
            if line.startswith("__version__"):
                v = line.split("=", 1)[1].strip().strip("\"'")
                return v.removesuffix("-pro").removesuffix("-lite")
    except OSError:
        pass
    return "?"


def install(zip_path: Path) -> str:
    """The zip's ``archxq_it_pro`` put in the plugins folder; the one there
    kept as the backup. Returns the version installed."""
    d = plugins_dir()
    stage = d / f".{FOLDER}.new"
    if stage.exists():
        shutil.rmtree(stage)
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = z.namelist()
            bad = [n for n in names
                   if not n.startswith(FOLDER + "/") or ".." in n.split("/")
                   or n.startswith("/") or ":" in n]
            if bad or f"{FOLDER}/__init__.py" not in names:
                raise UpdateError("The download is not an ArchXQ IT Pro "
                                  "package.")
            z.extractall(stage)
    except zipfile.BadZipFile:
        raise UpdateError("The download arrived damaged — please try "
                          "again.") from None
    new = stage / FOLDER
    version = _version_in(new)
    live = d / FOLDER
    old = None
    try:
        if live.exists():
            # one backup only: the version being replaced
            for b in backups():
                shutil.rmtree(b, ignore_errors=True)
            old = d / (BACKUP + _version_in(live))
            if old.exists():
                shutil.rmtree(old)
            live.replace(old)
        new.replace(live)
    except OSError as e:
        if old is not None and old.exists() and not live.exists():
            old.replace(live)                    # put it back as it was
        raise UpdateError("Windows did not let ArchXQ replace its folder "
                          f"({e.strerror or e}). Close IngeTrazo, then "
                          "install the zip by hand.") from None
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        zip_path.unlink(missing_ok=True)
    _put("just_installed", version)
    return version


def restore() -> str:
    """Swap back to the version kept as the backup. Returns its version."""
    found = backups()
    if not found:
        raise UpdateError("There is no previous version to go back to.")
    d = plugins_dir()
    back, live = found[0], d / FOLDER
    version = _version_in(back)
    keep = d / (BACKUP + _version_in(live)) if live.exists() else None
    if keep is not None and keep == back:
        keep = d / (BACKUP + _version_in(live) + "-now")
    try:
        if keep is not None:
            live.replace(keep)
        back.replace(live)
    except OSError as e:
        raise UpdateError(f"Windows did not let ArchXQ swap the folders "
                          f"({e.strerror or e}).") from None
    _put("just_installed", version)
    _put("later", latest_known().get("version", ""))   # no nagging back
    return version


# ---- thread → Qt ----------------------------------------------------------------------
class _Relay(QObject):
    """Results from a worker thread, delivered on Qt's thread."""
    done = Signal(object, object)        # (callback, result | UpdateError)
    step = Signal(object, int, int)      # (callback, got, total)

    def __init__(self) -> None:
        super().__init__()
        self.done.connect(lambda cb, r: cb(r))
        self.step.connect(lambda cb, a, b: cb(a, b))


_relay: _Relay | None = None


def _run(work, then, progress=None) -> None:
    """``work(progress)`` in a thread; ``then(result_or_error)`` on Qt's."""
    global _relay
    if _relay is None:
        _relay = _Relay()
    relay = _relay
    tick = (lambda a, b: relay.step.emit(progress, a, b)) if progress else None

    def body() -> None:
        try:
            out = work(tick)
        except UpdateError as e:
            out = e
        except Exception as e:  # noqa: BLE001 — never an uncaught thread
            out = UpdateError(f"Unexpected error: {e}")
        relay.done.emit(then, out)
    threading.Thread(target=body, daemon=True,
                     name="archxq-update").start()


# ---- at start ------------------------------------------------------------------------
def start(owner) -> None:
    """Called once ArchXQ is built: the «updated ✓» line, then (Pro) the
    daily check a few seconds later, out of the way of the start."""
    if not enabled():
        return
    just = str(_get("just_installed", ""))
    if just and just == current():
        _put("just_installed", "")
        QTimer.singleShot(2500, lambda: _flash(
            owner, f"ArchXQ IT updated to {just} ✓"))
    if edition.lite():
        return
    _badge(owner)                       # what the last check found
    last = float(_get("last_check", 0) or 0)
    if time.time() - last >= CHECK_EVERY:
        QTimer.singleShot(6000, lambda: check(owner))
    elif available():
        QTimer.singleShot(4000, lambda: _maybe_notice(owner))


def check(owner, then=None) -> None:
    """Ask the site now; keep the answer; dot + notice if newer."""
    def done(r) -> None:
        if isinstance(r, dict):
            _put("latest", json.dumps(r))
            _put("last_check", time.time())
        if getattr(owner, "alive", False):
            _badge(owner)
            if then is None:
                _maybe_notice(owner)
        if then is not None:
            then(r)
    _run(lambda _p: fetch_latest(), done)


def _flash(owner, text: str) -> None:
    if getattr(owner, "alive", False):
        from . import compat
        compat.flash(owner.viewport, text, 6000)


def _badge(owner) -> None:
    hub = getattr(owner, "hub", None)
    if hub is not None and hasattr(hub, "set_update"):
        hub.set_update(available().get("version", ""))


def _maybe_notice(owner) -> None:
    a = available()
    if not a or str(_get("later", "")) == a["version"]:
        return
    if not getattr(owner, "alive", False):
        return
    Notice(owner, a).show_over(owner.viewport)


# ---- the small notice (top right of the 3D view) ------------------------------------
_CARD = ("QFrame#axqUpd { background: #26282c; border: 1px solid #e8742c; "
         "border-radius: 8px; } QLabel { color: #e6e6e6; background: "
         "transparent; } QPushButton { color: #e6e6e6; background: "
         "#3a3d42; border: 1px solid #50545a; border-radius: 5px; "
         "padding: 4px 14px; } QPushButton:hover { background: #474b51; } "
         "QPushButton#axqOk { background: #e8742c; border: 1px solid "
         "#e8742c; color: white; font-weight: bold; } "
         "QPushButton#axqOk:hover { background: #f08a48; }")


class Notice(QFrame):
    """«ArchXQ IT 0.12.0 is available» + Update… / Later — never modal."""

    def __init__(self, owner, latest: dict) -> None:
        super().__init__(owner.viewport)
        self.owner = owner
        self.version = latest["version"]
        self.setObjectName("axqUpd")
        self.setStyleSheet(_CARD)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        t = QLabel(f"<b>ArchXQ IT {self.version}</b> is available "
                   f"<span style='color:#9aa0a6'>(you have {current()})"
                   "</span>")
        t.setTextFormat(Qt.RichText)
        lay.addWidget(t)
        first = (latest.get("notes") or [""])[0]
        if first:
            n = QLabel(first)
            n.setWordWrap(True)
            n.setFixedWidth(300)
            n.setStyleSheet("color: #9aa0a6;")
            lay.addWidget(n)
        how = QLabel("Click <b>Update</b> — it installs itself, then "
                     "restart IngeTrazo.")
        how.setTextFormat(Qt.RichText)
        how.setWordWrap(True)
        how.setFixedWidth(300)
        lay.addWidget(how)
        row = QHBoxLayout()
        row.addStretch()
        later = QPushButton("Later")
        later.setToolTip("Hide this until the next version (the orange dot "
                         "on ⏻ ArchXQ stays)")
        later.clicked.connect(self._later)
        go = QPushButton("Update…")
        go.setObjectName("axqOk")
        go.clicked.connect(self._go)
        row.addWidget(later)
        row.addWidget(go)
        lay.addLayout(row)

    def show_over(self, vp) -> None:
        self.adjustSize()
        self.move(max(8, vp.width() - self.width() - 14), 54)
        self.show()
        self.raise_()

    def _later(self) -> None:
        _put("later", self.version)
        self.deleteLater()

    def _go(self) -> None:
        # hidden NOW: deleteLater waits for the event loop, and the window's
        # own loop (exec) kept the card on screen behind it (real test,
        # 2026-10-18)
        self.hide()
        self.deleteLater()
        open_dialog(self.owner)


# ---- the window -------------------------------------------------------------------------
def open_dialog(owner) -> None:
    dlg = UpdateDialog(owner)
    dlg.exec()


class UpdateDialog(QDialog):
    """Pro: «Update to x» (or «you have the latest»), the key when needed,
    «Restore previous version». Lite: «Upgrade to Pro» with the key."""

    def __init__(self, owner) -> None:
        super().__init__(owner.window)
        from . import look
        self.owner = owner
        self.lite = edition.lite()
        self.busy = False
        look.dress(self)
        self.setWindowTitle("Upgrade to ArchXQ IT Pro" if self.lite
                           else "ArchXQ IT Pro — updates")
        self.setMinimumWidth(440)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(8)
        self.head = QLabel()
        self.head.setTextFormat(Qt.RichText)
        self.head.setWordWrap(True)
        lay.addWidget(self.head)
        self.notes = QLabel()
        self.notes.setTextFormat(Qt.RichText)
        self.notes.setWordWrap(True)
        self.notes.setOpenExternalLinks(True)
        lay.addWidget(self.notes)
        # the license key
        self.key_box = QFrame()
        kl = QVBoxLayout(self.key_box)
        kl.setContentsMargins(0, 6, 0, 0)
        kl.setSpacing(4)
        kl.addWidget(QLabel("<b>License key</b>"))
        self.key = QLineEdit(saved_key())
        self.key.setPlaceholderText("XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX")
        self.key.setClearButtonEnabled(True)
        kl.addWidget(self.key)
        where = look.hint(
            "It is in your Gumroad purchase: the email receipt, or "
            f"<a href='{LIBRARY}' style='color:#8fd3ff'>Gumroad ▸ Library</a>"
            " ▸ ArchXQ IT Pro.")
        where.setTextFormat(Qt.RichText)
        where.setOpenExternalLinks(True)
        kl.addWidget(where)
        lay.addWidget(self.key_box)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.bar.hide()
        lay.addWidget(self.bar)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        self.msg.setTextFormat(Qt.RichText)
        self.msg.setOpenExternalLinks(True)
        self.msg.hide()
        lay.addWidget(self.msg)
        # buttons: the one orange action, centred (the house rule)
        row = QHBoxLayout()
        self.restore_btn = QLabel()
        self.restore_btn.setTextFormat(Qt.RichText)
        self.restore_btn.linkActivated.connect(lambda _t: self._restore())
        row.addWidget(self.restore_btn)
        row.addStretch()
        self.close_btn = QPushButton("Later" if not self.lite else "Close")
        self.close_btn.clicked.connect(self.reject)
        self.go = QPushButton()
        self.go.setObjectName("axqOk")
        self.go.setDefault(True)
        self.go.clicked.connect(self._act)
        row.addWidget(self.close_btn)
        row.addWidget(self.go)
        lay.addSpacing(4)
        lay.addLayout(row)
        self.mode = ""
        self._show_state()
        if not self.lite:                       # always fresh when opened
            self._say("Checking xq.com.br…")
            check(owner, then=self._checked)

    # -- states ------------------------------------------------------------------
    def _show_state(self) -> None:
        b = backups()
        self.restore_btn.setText(
            f"<a href='r' style='color:#8fd3ff; text-decoration:none'>"
            f"Restore previous version ({b[0].name.removeprefix(BACKUP)})</a>"
            if b and not self.lite else "")
        if self.lite:
            self.mode = "upgrade"
            self.head.setText(
                "<span style='font-size:15px; font-weight:bold; "
                "color:white'>Upgrade to ArchXQ IT Pro</span>")
            self.notes.setText(
                "Already bought the Pro? Paste your license key — the Pro "
                "installs itself, then restart IngeTrazo (the Lite is "
                "switched off; your projects keep everything).<br>"
                f"<a href='{edition.PRO_URL}' style='color:#8fd3ff'>"
                "Buy ArchXQ IT Pro →</a>")
            self.go.setText("Install Pro")
            self.key_box.show()
            return
        a = available()
        if a:
            self.mode = "update"
            self.head.setText(
                f"<span style='font-size:15px; font-weight:bold; "
                f"color:white'>Update to {a['version']}</span>"
                f"&nbsp;&nbsp;<span style='color:#9aa0a6'>you have "
                f"{current()}</span>")
            items = "".join(f"<li>{_esc(n)}</li>"
                            for n in (a.get("notes") or [])[:6])
            need = a.get("min_host", "")
            warn = ""
            if need and host_version() != "?" \
                    and newer(need, host_version()):
                warn = (f"<p style='color:#f3d9a4'>⚠ This version needs "
                        f"IngeTrazo {need} or newer (you have "
                        f"{host_version()}). Update IngeTrazo first.</p>")
            self.notes.setText(
                f"<ul style='margin-left:-20px'>{items}</ul>"
                f"<a href='{WHATS_NEW}' style='color:#8fd3ff'>"
                "Everything that changed (What's new) →</a>" + warn)
            self.go.setText("Update")
            self.go.setEnabled(not warn)
            self.key_box.setVisible(not saved_key())
        else:
            self.mode = "latest"
            self.head.setText(
                "<span style='font-size:15px; font-weight:bold; "
                f"color:white'>ArchXQ IT Pro {current()}</span>")
            self.notes.setText("You have the latest version.")
            self.go.setText("Check again")
            self.key_box.hide()
        self.close_btn.setText("Later" if self.mode == "update" else "Close")

    def _checked(self, r) -> None:
        if self.busy or not self.isVisible():
            return
        if isinstance(r, UpdateError):
            self._say(str(r), bad=True)
        else:
            self.msg.hide()
        self._show_state()

    def _say(self, text: str, bad: bool = False, good: bool = False) -> None:
        colour = "#ff8a80" if bad else "#7ee2a8" if good else "#9aa0a6"
        self.msg.setText(f"<span style='color:{colour}'>{text}</span>")
        self.msg.show()

    def _lock(self, on: bool) -> None:
        self.busy = on
        for w in (self.go, self.key, self.close_btn):
            w.setEnabled(not on)
        self.restore_btn.setEnabled(not on)

    # -- actions -------------------------------------------------------------------
    def _act(self) -> None:
        if self.mode == "done":
            self.accept()
            return
        if self.mode == "latest":
            self._say("Checking xq.com.br…")
            check(self.owner, then=self._checked)
            return
        key = self.key.text().strip().upper()
        if not key:
            self.key_box.show()
            self._say("Paste your license key first.", bad=True)
            self.key.setFocus()
            return
        self._lock(True)
        self.bar.setRange(0, 0)
        self.bar.show()
        self._say("Checking your license…" if self.mode == "upgrade"
                  else "Downloading…")
        lite = self.mode == "upgrade"

        def work(progress):
            if lite:
                check_license(key)           # the activation (counts a use)
            path, _v = download(key, progress)
            return install(path)
        _run(work, lambda r: self._installed(r, key), self._progress)

    def _progress(self, got: int, total: int) -> None:
        if self.bar.maximum() != total:
            self.bar.setRange(0, total)
            self._say("Downloading…")
        self.bar.setValue(got)

    def _installed(self, r, key: str) -> None:
        self._lock(False)
        self.bar.hide()
        if isinstance(r, UpdateError):
            self._say(str(r), bad=True)
            if "key" in str(r).lower() or "refund" in str(r).lower():
                self.key_box.show()
            return
        _put("key", key)                       # asked once, kept
        _put("later", "")
        self.mode = "done"
        what = "ArchXQ IT Pro" if self.lite else "ArchXQ IT"
        self._say(f"✓ {what} {r} is installed. <b>Restart IngeTrazo</b> to "
                  "finish (save your work first).", good=True)
        self.key_box.hide()
        self.go.setText("OK")
        self.close_btn.hide()
        if getattr(self.owner, "alive", False):
            self.owner.hub.set_update("")

    def _restore(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        b = backups()
        if not b:
            return
        v = b[0].name.removeprefix(BACKUP)
        if QMessageBox.question(
                self, "Restore previous version",
                f"Go back to ArchXQ IT Pro {v}?\n\nThe version you have "
                f"now ({current()}) is kept, so you can come back to it.",
                QMessageBox.Yes | QMessageBox.Cancel) != QMessageBox.Yes:
            return
        try:
            got = restore()
        except UpdateError as e:
            self._say(str(e), bad=True)
            return
        self.mode = "done"
        self._say(f"✓ ArchXQ IT Pro {got} is back. <b>Restart IngeTrazo</b> "
                  "to finish.", good=True)
        self.go.setText("OK")
        self.close_btn.hide()
        self.restore_btn.setText("")


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))
