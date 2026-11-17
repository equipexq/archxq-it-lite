"""The sky picture behind the 3D view (PLANO_FUNDO_HDRI.md, H0, 14/11/2026).

Reads a Radiance .hdr (RGBE, flat or run-length) with numpy, brings it to
8 bits with an exposure (ACES-like curve, then sRGB), and makes it no wider
than the view needs. No Qt here except `save_jpg` (QImage is fine off the
UI thread): this runs on a worker thread when a sky is picked.

A sky picture is equirectangular: 2:1, longitude across (−180°…180°),
latitude down (zenith on the first row, nadir on the last).
"""
from __future__ import annotations

import os
import re

import numpy as np

MAX_W = 4096                       # the picture kept for the view
MAX_FILE = 400 * 1024 * 1024       # a .hdr bigger than this is refused
_RES = re.compile(rb"^([-+])Y\s+(\d+)\s+([-+])X\s+(\d+)\s*$")


class SkyError(ValueError):
    """A picture that is not a sky we can show; the text says why."""


def root() -> str:
    return os.environ.get("ARCHXQ_HDRI_DIR") or os.path.join(
        os.path.expanduser("~"), ".archxq", "hdri")


# ---- reading the .hdr -------------------------------------------------------------
def read_hdr(data: bytes) -> np.ndarray:
    """The .hdr bytes → float32 (h, w, 3), linear light, top row first."""
    if not (data.startswith(b"#?RADIANCE") or data.startswith(b"#?RGBE")):
        raise SkyError("not a Radiance .hdr file")
    pos, fmt = 0, None
    while True:                                   # the header: lines up to a blank one
        end = data.find(b"\n", pos)
        if end < 0:
            raise SkyError("the .hdr header has no end")
        line = data[pos:end].strip()
        pos = end + 1
        if not line:
            break
        if line.startswith(b"FORMAT="):
            fmt = line[7:]
    if fmt not in (None, b"32-bit_rle_rgbe"):
        raise SkyError("only RGB .hdr files are read (this one is %s)"
                       % fmt.decode("ascii", "replace"))
    end = data.find(b"\n", pos)
    m = _RES.match(data[pos:end if end >= 0 else len(data)].strip())
    if not m:
        raise SkyError("the .hdr size line is not the usual one (-Y h +X w)")
    flip_y, h, flip_x, w = m.group(1) == b"+", int(m.group(2)), m.group(3) == b"-", int(m.group(4))
    if not (8 <= w <= 32768 and 4 <= h <= 16384):
        raise SkyError("the .hdr size %d × %d is out of range" % (w, h))
    body = memoryview(data)[end + 1:]
    rgbe = _scanlines(body, w, h)
    if flip_y:
        rgbe = rgbe[::-1]
    if flip_x:
        rgbe = rgbe[:, ::-1]
    return _to_float(rgbe)


def _scanlines(body, w: int, h: int) -> np.ndarray:
    out = np.empty((h, w, 4), np.uint8)
    buf = bytes(body)
    n = len(buf)
    rle = 8 <= w <= 0x7FFF and n >= 4 and buf[0] == 2 and buf[1] == 2 and buf[2] < 128
    if not rle:                                   # flat RGBE, 4 bytes a pixel
        if n < w * h * 4:
            raise SkyError("the .hdr ends before its last row")
        out[:] = np.frombuffer(buf, np.uint8, w * h * 4).reshape(h, w, 4)
        return out
    p = 0
    row = np.empty(w, np.uint8)
    for y in range(h):
        if p + 4 > n or buf[p] != 2 or buf[p + 1] != 2 or ((buf[p + 2] << 8) | buf[p + 3]) != w:
            raise SkyError("the .hdr row %d is broken" % y)
        p += 4
        for c in range(4):
            x = 0
            while x < w:
                if p >= n:
                    raise SkyError("the .hdr ends before its last row")
                k = buf[p]
                p += 1
                if k > 128:                       # a run: one value k−128 times
                    k -= 128
                    if p >= n:
                        raise SkyError("the .hdr ends before its last row")
                    if x + k > w:
                        raise SkyError("the .hdr row %d is broken" % y)
                    row[x:x + k] = buf[p]
                    p += 1
                else:                             # k plain values
                    if p + k > n:
                        raise SkyError("the .hdr ends before its last row")
                    if k == 0 or x + k > w:
                        raise SkyError("the .hdr row %d is broken" % y)
                    row[x:x + k] = np.frombuffer(buf, np.uint8, k, p)
                    p += k
                x += k
            out[y, :, c] = row
    return out


def _to_float(rgbe: np.ndarray) -> np.ndarray:
    e = rgbe[..., 3].astype(np.int32)
    f = np.where(e > 0, np.ldexp(np.float32(1.0), e - 136), 0.0).astype(np.float32)
    return rgbe[..., :3].astype(np.float32) * f[..., None]


# ---- to 8 bits --------------------------------------------------------------------
def tone(rgb: np.ndarray, exposure: float = 0.0) -> np.ndarray:
    """Linear light → sRGB uint8 (h, w, 3). Exposure in stops (−3…+3)."""
    x = rgb * np.float32(2.0 ** max(-6.0, min(6.0, float(exposure))) * 0.6)
    x = (x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14)   # ACES fit (Narkowicz)
    x = np.clip(x, 0.0, 1.0)
    x = np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)
    return (x * 255.0 + 0.5).astype(np.uint8)


def shrink(img: np.ndarray, max_w: int = MAX_W) -> np.ndarray:
    """No wider than max_w, by averaging whole blocks (kept 2:1)."""
    h, w = img.shape[:2]
    k = 1
    while w // k > max_w:
        k *= 2
    if k == 1:
        return img
    h2, w2 = h // k, w // k
    a = img[:h2 * k, :w2 * k].astype(np.float32)
    a = a.reshape(h2, k, w2, k, -1).mean(axis=(1, 3))
    return (a + 0.5).astype(img.dtype) if img.dtype == np.uint8 else a


def check_ratio(w: int, h: int) -> None:
    if h <= 0 or abs(w / h - 2.0) > 0.02:
        raise SkyError("a sky picture is twice as wide as it is tall "
                       "(this one is %d × %d)" % (w, h))


def from_hdr(data: bytes, exposure: float = 0.0, max_w: int = MAX_W) -> np.ndarray:
    """A .hdr → the sRGB picture for the view (h, w, 3) uint8."""
    if len(data) > MAX_FILE:
        raise SkyError("the .hdr is too big")
    rgb = read_hdr(data)
    check_ratio(rgb.shape[1], rgb.shape[0])
    return tone(shrink(rgb, max_w), exposure)


def cache_name(sky_id: str, exposure: float) -> str:
    """The file a picked sky is kept as, one per exposure (0.1 stop)."""
    safe = re.sub(r"[^A-Za-z0-9_\-]", "_", sky_id)[:80] or "sky"
    e = int(round(max(-3.0, min(3.0, float(exposure))) * 10))
    return "%s_e%+03d.jpg" % (safe, e)


def save_jpg(img: np.ndarray, path: str, quality: int = 92) -> None:
    from PySide6.QtGui import QImage
    img = np.ascontiguousarray(img)
    h, w = img.shape[:2]
    q = QImage(img.data, w, h, w * 3, QImage.Format_RGB888)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    if not q.save(tmp, "JPG", quality):
        raise SkyError("the sky picture could not be written")
    os.replace(tmp, path)


# ---- pictures that are already 8 bits (jpg, png: your own, the default) ----------
_LUT = None


def _lin_lut() -> np.ndarray:
    global _LUT
    if _LUT is None:
        x = np.arange(256, dtype=np.float32) / 255.0
        _LUT = np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4).astype(np.float32)
    return _LUT


def gain(img: np.ndarray, exposure: float) -> np.ndarray:
    """An 8-bit sRGB picture made brighter / darker by `exposure` stops
    (in linear light, as a camera would); 0 = the same picture."""
    e = max(-6.0, min(6.0, float(exposure)))
    if abs(e) < 1e-6:
        return img
    lin = _lin_lut()[img] * np.float32(2.0 ** e)
    lin = np.clip(lin, 0.0, 1.0)
    out = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
    return (out * 255.0 + 0.5).astype(np.uint8)


def read_ldr(path: str) -> np.ndarray:
    """A jpg / png / webp → (h, w, 3) uint8 (QImage reads it)."""
    from PySide6.QtGui import QImage
    q = QImage(path)
    if q.isNull():
        raise SkyError("the picture could not be read")
    q = q.convertToFormat(QImage.Format_RGB888)
    w, h, bpl = q.width(), q.height(), q.bytesPerLine()
    a = np.frombuffer(q.constBits(), np.uint8, bpl * h).reshape(h, bpl)
    return a[:, :w * 3].reshape(h, w, 3).copy()


def from_file(path: str, exposure: float = 0.0, max_w: int = MAX_W) -> np.ndarray:
    """Any sky file (.hdr, jpg, png…) → the sRGB picture for the view."""
    if path.lower().endswith(".hdr"):
        if os.path.getsize(path) > MAX_FILE:
            raise SkyError("the .hdr is too big")
        with open(path, "rb") as f:
            return from_hdr(f.read(), exposure, max_w)
    img = read_ldr(path)
    check_ratio(img.shape[1], img.shape[0])
    return gain(shrink(img, max_w), exposure)
