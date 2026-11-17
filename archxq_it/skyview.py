# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""THE SKY behind the 3D view (PLANO_FUNDO_HDRI.md, H1–H2, 14/11/2026).

The «Sky» chip on the view bar (after «Extents») shows / hides it; its
arrow opens the sky window. The Lite has the default sky (on / off); the
Pro picks among Poly Haven's skies and your own, turns it, sets its
exposure and horizon, and can show the picture's own ground («Photo»).

The choice is the project's, kept in the file under its own key
(``scene.plugin_data["archxq_sky"]``) — a VIEW setting: not an undo step,
the file not marked unsaved (as the host's layer eyes). A project with no
choice kept yet — a new one or one saved before the sky — starts with the
default sky ON; one where he turned it off opens off.

Drawn by skydraw (in place of the host's own sky) only while ArchXQ is on,
in the 3D view: never in the plan, the elevations, hidden line or x-ray.
"""
from __future__ import annotations

import concurrent.futures
import math
import os
import queue
import re

from . import edition, skydraw, skyimg
from .i18n import N_, tr

KEY = "archxq_sky"
BUILTIN = "builtin"
BUILTIN_NAME = "Kloofendal 48d Partly Cloudy (Pure Sky)"
BUILTIN_FILE = os.path.join(os.path.dirname(__file__), "sky_default.jpg")
DEFAULT = {"on": False, "sky": BUILTIN, "name": BUILTIN_NAME, "rot": 0.0,
           "exp": 0.0, "horizon": 0.0, "ground": "host"}
EXP_STEP = 0.5
_SKY = re.compile(r"^(polyhaven/[A-Za-z0-9][A-Za-z0-9_\-]{0,80}"
                  r"|own/[^\\/:*?\"<>|]{1,120})$")
_HIDE_FACES = ("hidden_line", "xray", "wireframe")

_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=1,
                                              thread_name_prefix="axq-sky")
_Q: queue.Queue = queue.Queue()
_BUSY: dict = {}          # (sky, exp) -> pct (being made)
_FAILED: dict = {}        # (sky, exp) -> why
_TICK = None
_WIN = None


def _pro():
    """skycat (the Pro's skies), None in the Lite."""
    if edition.lite():
        return None
    try:
        from . import skycat
        return skycat
    except ImportError:
        return None


# ---- the project's choice ---------------------------------------------------------
def clean(raw) -> dict:
    out = dict(DEFAULT)
    if not isinstance(raw, dict):
        return out
    out["on"] = bool(raw.get("on"))
    sky = raw.get("sky")
    if sky == BUILTIN or (isinstance(sky, str) and _SKY.match(sky) and ".." not in sky):
        out["sky"] = sky
        out["name"] = str(raw.get("name") or "")[:120] or (
            BUILTIN_NAME if sky == BUILTIN else sky.split("/", 1)[1])
    else:
        out["sky"], out["name"] = BUILTIN, BUILTIN_NAME
    for k, lo, hi in (("exp", -3.0, 3.0), ("horizon", -10.0, 10.0)):
        try:
            v = float(raw.get(k, 0.0))
            out[k] = max(lo, min(hi, v)) if math.isfinite(v) else 0.0
        except (TypeError, ValueError):
            out[k] = 0.0
    out["exp"] = round(out["exp"] / EXP_STEP) * EXP_STEP
    try:
        r = float(raw.get("rot", 0.0))
        out["rot"] = r % 360.0 if math.isfinite(r) else 0.0
    except (TypeError, ValueError):
        out["rot"] = 0.0
    out["ground"] = "photo" if raw.get("ground") == "photo" else "host"
    return out


def effective(st: dict) -> dict:
    """What this edition shows: the Lite, the default sky as it comes."""
    if _pro() is None:
        out = dict(DEFAULT)
        out["on"] = st["on"]
        return out
    return st


def _scene(ui):
    try:
        return ui.viewport.scene
    except Exception:  # noqa: BLE001
        return None


def read(ui) -> dict:
    sc = _scene(ui)
    data = getattr(sc, "plugin_data", None)
    if not isinstance(data, dict):
        return dict(DEFAULT)
    if KEY not in data:
        # no choice kept yet — a new project or one saved before the sky:
        # ON, the best by default (his call, 14/11/2026); one he turned
        # off keeps it off (his choice is kept in the file)
        st = dict(DEFAULT)
        st["on"] = True
        data[KEY] = dict(st)          # (kept, so the saved file has it)
        return st
    return clean(data[KEY])


def write(ui, **change) -> dict:
    """Changes the project's sky (no undo step, the file not marked)."""
    st = read(ui)
    st.update(change)
    st = clean(st)
    sc = _scene(ui)
    if sc is not None and isinstance(getattr(sc, "plugin_data", None), dict):
        sc.plugin_data[KEY] = dict(st)
    apply(ui)
    return st


# ---- when it shows --------------------------------------------------------------------
def host_sky_off(viewport) -> str:
    """'' when IngeTrazo draws a sky in this view; else why it doesn't."""
    st = getattr(viewport, "_frame_style", None) or \
        getattr(getattr(viewport, "scene", None), "display_style", None)
    if st is not None and not getattr(st, "sky", True):
        return tr("The sky is off in this project's display style "
                  "(IngeTrazo): turn it on there to see the picture")
    for name in ("_terrain_showing", "_base_map_showing", "_photo_showing"):
        fn = getattr(viewport, name, None)
        try:
            if callable(fn) and fn():
                return tr("IngeTrazo shows its own terrain or map here, "
                          "so it draws no sky")
        except Exception:  # noqa: BLE001
            pass
    return ""


def _when(ui, viewport):
    def ok() -> bool:
        if not getattr(ui, "alive", False):
            return False
        if not (getattr(ui, "active", False) or getattr(ui, "presenting", False)):
            return False
        if getattr(ui, "viewport", None) is viewport and (
                getattr(ui, "plan_on", False) or getattr(ui, "side_view", None)):
            return False
        st = getattr(viewport, "_frame_style", None)
        return getattr(st, "face_mode", "") not in _HIDE_FACES
    return ok


# ---- the picture ----------------------------------------------------------------------
def picture_path(sky: str, exp: float) -> str | None:
    """The jpg for the view, if it is ready on this computer."""
    if sky == BUILTIN:
        if abs(exp) < 1e-6:
            return BUILTIN_FILE
        p = os.path.join(skyimg.root(), "view", "builtin",
                         skyimg.cache_name("sky_default", exp))
        return p if os.path.isfile(p) else None
    cat = _pro()
    if cat is None:
        return None
    p = cat.picture_path(sky, exp)
    return p if p and os.path.isfile(p) else None


def _make(sky: str, exp: float) -> None:
    """Makes the picture on the worker thread; the result comes in _Q."""
    key = (sky, exp)
    if key in _BUSY:
        return
    _BUSY[key] = 0
    _FAILED.pop(key, None)

    def work() -> None:
        try:
            if sky == BUILTIN:
                out = os.path.join(skyimg.root(), "view", "builtin",
                                   skyimg.cache_name("sky_default", exp))
                if not os.path.isfile(out):
                    skyimg.save_jpg(skyimg.from_file(BUILTIN_FILE, exp), out)
            else:
                cat = _pro()
                if cat is None:
                    raise OSError("Pro")
                cat.make_picture(sky, exp, lambda pct: _Q.put(("pct", key, pct)))
            _Q.put(("done", key, None))
        except Exception as e:  # noqa: BLE001 — the window says so
            _Q.put(("fail", key, str(e) or type(e).__name__))
    _POOL.submit(work)
    _tick().start()


def _tick():
    global _TICK
    if _TICK is None:
        from PySide6.QtCore import QTimer
        _TICK = QTimer()
        _TICK.setInterval(120)
        _TICK.timeout.connect(_drain)
    return _TICK


_UIS: list = []


def _drain() -> None:
    changed = False
    while True:
        try:
            what, key, info = _Q.get_nowait()
        except queue.Empty:
            break
        if what == "pct":
            _BUSY[key] = info
        else:
            _BUSY.pop(key, None)
            if what == "fail":
                _FAILED[key] = info
            changed = True
        if _WIN is not None:
            _WIN.status_changed()
    if changed:
        for ui in list(_UIS):
            try:
                apply(ui)
            except Exception:  # noqa: BLE001
                pass
    if not _BUSY:
        _tick().stop()


def apply(ui) -> None:
    """The view in front shows what its project says (cheap when nothing
    changed: called at each change of the document)."""
    if ui not in _UIS:
        _UIS.append(ui)
    vp = getattr(ui, "viewport", None)
    if vp is None or not getattr(ui, "alive", False):
        return
    st = effective(read(ui))
    _sync_chip(ui, st["on"])
    if not st["on"] or skydraw.available(vp):
        if skydraw.painter(vp) is not None:
            skydraw.hide(vp)
        return
    sky, exp = st["sky"], st["exp"]
    path = picture_path(sky, exp)
    if path is None:
        if (sky, exp) not in _FAILED:
            _make(sky, exp)
        else:                         # it could not be had: the default meanwhile
            path = BUILTIN_FILE
            sky, exp = BUILTIN, 0.0
        if path is None:
            sp = skydraw.painter(vp)
            if sp is not None:        # the one before stays until it is ready
                skydraw.set_view(vp, st["rot"], st["horizon"], st["ground"] == "photo")
            return
    sp = skydraw.painter(vp)
    if sp is not None and getattr(sp, "key", None) == (sky, exp):
        if (sp.rot, sp.lift, sp.photo) != (math.radians(st["rot"]),
                                           math.radians(st["horizon"]),
                                           st["ground"] == "photo"):
            skydraw.set_view(vp, st["rot"], st["horizon"], st["ground"] == "photo")
        return
    from PySide6.QtGui import QImage
    img = QImage(path)
    if img.isNull() or abs(img.width() / max(1, img.height()) - 2.0) > 0.02:
        _FAILED[(sky, exp)] = tr("The sky picture could not be read")
        if sky != BUILTIN:
            write(ui, sky=BUILTIN, name=BUILTIN_NAME)
        return
    sp = skydraw.show(vp, img, st["rot"], st["horizon"], st["ground"] == "photo",
                      when=_when(ui, vp),
                      ground=ground_tone(img, host_ground(vp), has_ground(sky)))
    sp.key = (sky, exp)


# ---- the ground under the horizon (H3) ---------------------------------------------
def host_ground(viewport) -> tuple:
    st = getattr(viewport, "_frame_style", None)
    rgb = getattr(st, "ground_color", None) or getattr(viewport, "_GROUND_RGB", None)         or (0.815, 0.82, 0.815)
    return tuple(float(x) for x in tuple(rgb)[:3])


def has_ground(sky: str) -> bool:
    """The picture shows a real ground (a puresky's lower half is empty)."""
    if sky == BUILTIN:
        return False
    if sky.startswith("own/"):
        return True
    cat = _pro()
    it = cat.find(sky) if cat is not None else None
    return bool(it and it.get("photo"))


def ground_tone(img, host_rgb, real_ground: bool) -> tuple:
    """The ground's colour under the horizon: IngeTrazo's own ground,
    tinted halfway to the picture's ground (its median, 3°–15° below the
    horizon) when the picture has one — so the trees and the fields of the
    picture don't stand on a pale floor."""
    if not real_ground:
        return tuple(host_rgb)
    try:
        import numpy as np
        from PySide6.QtGui import QImage
        q = img.scaled(512, 256).convertToFormat(QImage.Format_RGB888)
        w, h, bpl = q.width(), q.height(), q.bytesPerLine()
        a = np.frombuffer(q.constBits(), np.uint8, bpl * h).reshape(h, bpl)[:, :w * 3]
        a = a.reshape(h, w, 3)
        y0, y1 = int(h * (0.5 + 3 / 180)), int(h * (0.5 + 15 / 180)) + 1
        med = np.median(a[y0:y1].reshape(-1, 3), axis=0) / 255.0
    except Exception:  # noqa: BLE001 — the host's ground then
        return tuple(host_rgb)
    return tuple(float(0.5 * m + 0.5 * hgr) for m, hgr in zip(med, host_rgb))


def _sync_chip(ui, on: bool) -> None:
    bar = getattr(ui, "viewbar", None)
    chip = getattr(bar, "sky", None)
    if chip is not None and chip.isChecked() != on:
        chip.blockSignals(True)
        chip.setChecked(on)
        chip.blockSignals(False)


def closed(scene) -> None:
    """A project tab closes: its view's sky goes."""
    for sp in list(skydraw._PAINTERS.values()):
        try:
            if getattr(sp.vp, "scene", None) is scene:
                skydraw.hide(sp.vp)
        except RuntimeError:
            skydraw._PAINTERS.pop(id(sp.vp), None)


def teardown() -> None:
    """ArchXQ goes away: the host's own sky in every view."""
    global _WIN
    if _WIN is not None:
        try:
            _WIN.close()
        except RuntimeError:
            pass
        _WIN = None
    for sp in list(skydraw._PAINTERS.values()):
        try:
            skydraw.hide(sp.vp)
        except RuntimeError:
            pass
    skydraw._PAINTERS.clear()
    _UIS.clear()


# ---- favourites (the user's, for every project) ------------------------------------
def favs() -> list:
    from PySide6.QtCore import QSettings
    raw = QSettings().value("archxq/sky/fav", [])
    if isinstance(raw, str):
        raw = [raw]
    return [s for s in (raw or []) if isinstance(s, str)
            and (s == BUILTIN or _SKY.match(s))][:60]


def toggle_fav(sky: str) -> bool:
    from PySide6.QtCore import QSettings
    rows = favs()
    if sky in rows:
        rows.remove(sky)
        on = False
    else:
        rows.append(sky)
        on = True
    QSettings().setValue("archxq/sky/fav", rows)
    return on


# ---- the chip's actions ---------------------------------------------------------------
def toggle(ui, on: bool) -> None:
    write(ui, on=bool(on))


def open_window(ui, anchor) -> None:
    global _WIN
    from . import skywin
    if _WIN is not None:
        try:
            _WIN.close()
        except RuntimeError:
            pass
    _WIN = skywin.SkyWindow(ui)
    _WIN.show_at(anchor)


def window_closed(win) -> None:
    global _WIN
    if _WIN is win:
        _WIN = None


def status_of(sky: str, exp: float) -> str:
    key = (sky, exp)
    if key in _BUSY:
        pct = _BUSY[key]
        return tr("Getting the sky… {pct}%", pct=pct) if pct else tr("Getting the sky…")
    if key in _FAILED:
        return tr("Could not get this sky. Check your internet connection "
                  "and try again")
    return ""


def retry(ui) -> None:
    st = read(ui)
    _FAILED.pop((st["sky"], st["exp"]), None)
    apply(ui)


#: the families' names, for the translations («Clear» alone is a glass's)
FAMILY_WORDS = {"Pure skies": N_("Pure skies"), "Clear": N_("Clear sky"),
                "Partly cloudy": N_("Partly cloudy"), "Overcast": N_("Overcast"),
                "Sunrise & sunset": N_("Sunrise & sunset"), "City": N_("City"),
                "Nature": N_("Nature")}


def family_label(fam: str) -> str:
    return tr(FAMILY_WORDS.get(fam, fam))
