"""The public CC0 textures of Poly Haven and ambientCG, and your own (his ask,
09/11/2026). Only the short list ships (webtex_catalog.json, made by
make_webtex_catalog.py); pictures and images come when asked for and stay in
~/.archxq/textures. No Qt here: this runs on worker threads too.

A ref is self-contained: {"web": "polyhaven/brick_wall_001" | "own": file,
"name", "w0", "h0" (its own size), "sw", "sh" (the size in use)}. A path NEVER
comes from a ref: a project file is not to be trusted with one.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import urllib.error
import urllib.request
import zipfile

from . import updater

SOURCES = {"polyhaven": "Poly Haven", "ambientcg": "ambientCG"}
SITES = {"polyhaven": "polyhaven.com", "ambientcg": "ambientcg.com"}
DEFAULT_SIZE = 2.0        # metres, when the source does not say
MAX_DOWNLOAD = 250 * 1024 * 1024
MAX_OWN = 64 * 1024 * 1024
OWN_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,80}$")
_OWN = re.compile(r"^[^\\/:*?\"<>|]{1,120}$")
_HOSTS = ("https://dl.polyhaven.org/",)
_DATA = None
_CTX = None


def root() -> str:
    return os.environ.get("ARCHXQ_WEBTEX_DIR") or os.path.join(
        os.path.expanduser("~"), ".archxq", "textures")


# ---- the list -----------------------------------------------------------------------
def _data() -> dict:
    global _DATA
    if _DATA is None:
        try:
            with open(os.path.join(os.path.dirname(__file__),
                                   "webtex_catalog.json"),
                      encoding="utf-8") as f:
                _DATA = json.load(f)
        except (OSError, ValueError):
            _DATA = {"families": []}
    return _DATA


def count(src: str) -> int:
    return len(_data().get(src) or ())


def _item(src: str, row: list) -> dict:
    w, h = float(row[3]), float(row[4])
    if w <= 0 or h <= 0:
        w, h = DEFAULT_SIZE, DEFAULT_SIZE
    return {"src": src, "id": row[0], "name": row[1], "w": w, "h": h}


def families(src: str) -> list:
    """[(family, [item…])], the families in the list's order, none empty."""
    data = _data()
    names = data.get("families") or []
    out = [[] for _n in names]
    for row in data.get(src) or ():
        out[row[2]].append(_item(src, row))
    return [(n, items) for n, items in zip(names, out) if items]


def ref_of(item: dict) -> dict:
    return {"web": f"{item['src']}/{item['id']}", "name": item["name"],
            "w0": item["w"], "h0": item["h"], "sw": item["w"], "sh": item["h"]}


# ---- refs ---------------------------------------------------------------------------
def is_ref(ref) -> bool:
    return isinstance(ref, dict) and ("web" in ref or "own" in ref)


def _split(web) -> tuple | None:
    if not isinstance(web, str) or web.count("/") != 1:
        return None
    src, key = web.split("/")
    return (src, key) if src in SOURCES and _ID.match(key) else None


def _own_ok(name) -> bool:
    return isinstance(name, str) and bool(_OWN.match(name)) \
        and ".." not in name \
        and os.path.splitext(name)[1].lower() in OWN_EXT


def clean_ref(ref) -> dict | None:
    """The ref as stored; None: not a good one."""
    try:
        size = [float(ref[k]) for k in ("w0", "h0", "sw", "sh")]
    except (KeyError, TypeError, ValueError):
        return None
    if not all(0 < v < 1e4 for v in size):
        return None
    if "web" in ref:
        if _split(ref["web"]) is None:
            return None
        out = {"web": ref["web"]}
    else:
        if not _own_ok(ref.get("own")):
            return None
        out = {"own": ref["own"]}
    out["name"] = str(ref.get("name") or "Texture")[:120]
    out.update(zip(("w0", "h0", "sw", "sh"), size))
    return out


def label_of(ref) -> str:
    """How its material is named in the host: says where it came from."""
    if "web" in ref:
        return f"{SOURCES[ref['web'].split('/')[0]]} {ref['name']}"
    return ref["name"]


def sized(ref: dict, width: float) -> dict:
    out = dict(ref)
    if abs(width - ref["w0"]) < 1e-4:
        out.update(sw=ref["w0"], sh=ref["h0"])
    else:
        out.update(sw=round(width, 4),
                   sh=round(width * ref["h0"] / ref["w0"], 4))
    return out


def file_path(src: str, key: str) -> str:
    return os.path.join(root(), src, key + "_2k.jpg")


def thumb_path(src: str, key: str) -> str:
    return os.path.join(root(), "thumbs", src, key + ".img")


def own_path(name: str) -> str:
    return os.path.join(root(), "own", name)


def ref_path(ref) -> str | None:
    """The image of a ref on this computer, None: it is not here."""
    if "web" in ref:
        got = _split(ref["web"])
        path = file_path(*got) if got else None
    else:
        path = own_path(ref["own"]) if _own_ok(ref.get("own")) else None
    return path if path and os.path.isfile(path) else None


# ---- the network --------------------------------------------------------------------
def _get(url: str, progress=None, timeout: float = 40.0) -> bytes:
    global _CTX
    if _CTX is None:
        _CTX = updater._ctx()
    req = urllib.request.Request(url, headers={
        "User-Agent": f"ArchXQ-IT-Pro/{updater.current()} (+https://xq.com.br)"})
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
        total = int(r.headers.get("Content-Length") or 0)
        buf, got = io.BytesIO(), 0
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                return buf.getvalue()
            got += len(chunk)
            if got > MAX_DOWNLOAD:
                raise OSError("too large")
            buf.write(chunk)
            if progress and total:
                progress(min(99, int(got * 100 / total)))


def _store(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    part = f"{path}.{os.getpid()}.part"
    with open(part, "wb") as f:
        f.write(data)
    os.replace(part, path)


def thumb_url(src: str, key: str) -> str:
    if src == "polyhaven":
        return (f"https://cdn.polyhaven.com/asset_img/thumbs/{key}.png"
                "?width=128&height=128")
    return ("https://acg-media.struffelproductions.com/file/ambientCG-Web/"
            f"media/thumbnail/128-PNG/{key}.png")


def fetch_thumb(src: str, key: str) -> str:
    path = thumb_path(src, key)
    if not os.path.isfile(path):
        _store(path, _get(thumb_url(src, key), timeout=20.0))
    return path


def diffuse_url(files: dict) -> str:
    """The 2K colour image in Poly Haven's answer."""
    for name in ("Diffuse", "diffuse", "Color", "diff"):
        url = (((files.get(name) or {}).get("2k") or {}).get("jpg") or {}) \
            .get("url")
        if url:
            if not url.startswith(_HOSTS):
                raise OSError("unexpected host")
            return url
    raise OSError("no colour image")


def colour_of(zipped: bytes) -> bytes:
    """The colour map in an ambientCG zip (read, never extracted)."""
    with zipfile.ZipFile(io.BytesIO(zipped)) as z:
        name = next((n for n in z.namelist()
                     if n.lower().endswith(("_color.jpg", "_color.jpeg"))),
                    None)
        if name is None:
            raise OSError("no colour image")
        return z.read(name)


def fetch_file(src: str, key: str, progress=None) -> str:
    """Brings the texture's image; its path."""
    path = file_path(src, key)
    if os.path.isfile(path):
        return path
    if src == "polyhaven":
        files = json.loads(_get(f"https://api.polyhaven.com/files/{key}",
                                timeout=20.0).decode("utf-8"))
        _store(path, _get(diffuse_url(files), progress))
        return path
    try:
        zipped = _get(f"https://ambientcg.com/get?file={key}_2K-JPG.zip",
                      progress)
    except urllib.error.HTTPError:          # (a few have only 1K)
        zipped = _get(f"https://ambientcg.com/get?file={key}_1K-JPG.zip",
                      progress)
    _store(path, colour_of(zipped))
    return path


# ---- your own -----------------------------------------------------------------------
def add_own(source: str, width: float, height: float) -> dict:
    """Keeps a copy of the image with the others; its ref. ``width`` and
    ``height``: of the picture, for its proportion."""
    if os.path.getsize(source) > MAX_OWN:
        raise OSError("too large")
    with open(source, "rb") as f:
        data = f.read()
    stem, ext = os.path.splitext(os.path.basename(source))
    ext = ext.lower()
    if ext not in OWN_EXT:
        raise OSError("not an image")
    nice = re.sub(r"[^\w\- ]+", "_", stem).strip(" ._")[:60] or "Texture"
    name = f"{nice}__{hashlib.sha1(data).hexdigest()[:8]}{ext}"
    path = own_path(name)
    if not os.path.isfile(path):
        _store(path, data)
    return own_ref(name, width, height)


def own_ref(name: str, width: float, height: float) -> dict:
    w = DEFAULT_SIZE
    h = round(w * height / width, 4) if width > 0 and height > 0 else w
    return {"own": name, "name": name.rsplit("__", 1)[0],
            "w0": w, "h0": h, "sw": w, "sh": h}


def own_files() -> list:
    try:
        names = os.listdir(os.path.join(root(), "own"))
    except OSError:
        return []
    return sorted((n for n in names if _own_ok(n)), key=str.lower)
