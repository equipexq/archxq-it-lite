# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A LEVEL'S REFERENCE in the host (PLANO_REFERENCIAS_NIVEL.md — his ask,
18/11/2026): the image or PDF page lying on a level's floor, to draw over.
``refimage`` does the sums; this puts them in the scene.

- The picture is the host's ``ImagePlane`` (reference, never geometry,
  kept inside the .igz), on the level's own layer «ArchXQ · <level> ·
  Reference» — shown only while that level is the one worked on, its eye
  on and its «Show» on (``sync``): as its blue sheet (his call, 31/10:
  several at once confused). Never on a sheet (hostsheet hides the
  «ArchXQ · » layers not of the sheet's level).
- Every change is the host's own command (Add / Transform / Opacity /
  Delete image) — one Ctrl+Z.
- A PDF page (Pro): drawn to a PNG in the host's texture cache at
  300 dpi; its LINES kept as fractions of that picture under ``LINES_KEY``
  (apart from ArchXQ's document: ``doc()`` is read very often, a page of
  lines would weigh on all of it). The level's drawing
  (``doc["underlays"][level]`` with "ref" = the picture's name) is then
  placed WITH the picture: measured, moved, turned — the lines follow, on
  top of it (``drawing``).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import compat
from . import refimage as R

#: a PDF's lines (and its page), apart from ArchXQ's document: {picture
#: name: {"uv": [[fu0, fv0, fu1, fv1, layer]…], "file", "page", "w_pt",
#: "h_pt", "scale"}}
LINES_KEY = compat.KEY + ".pdf_lines"
#: how a reference comes in: whole. The host draws a picture UNDER the
#: model; an opaque one writes depth (LIFT over the floor, it covers the
#: level's floor and terrain, what is drawn stands over it), a faded one
#: writes none — any floor or terrain hides it (seen live 18/11/2026)
OPACITY = 1.0
#: (%) a GHOST level's references over the plan of the level worked on
#: (his ask, 18/11: one level's picture laid over another's, to match them)
GHOST = 40
#: (px) a ghost picture is painted from a copy at most this big (fast)
GHOST_PX = 2048
#: what the file dialog takes
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".bmp")


def _v(t):
    from PySide6.QtGui import QVector3D
    return QVector3D(float(t[0]), float(t[1]), float(t[2]))


def frame_of(im) -> tuple:
    def t(q):
        return (float(q.x()), float(q.y()), float(q.z()))
    return (t(im.origin), t(im.u), t(im.v))


def layer_of(level: dict) -> str:
    return R.ref_layer(compat.level_layer(level["name"]))


def images(viewport, layer: str | None = None) -> list:
    return [im for im in getattr(viewport.scene, "image_planes", None) or ()
            if layer is None or getattr(im, "layer", None) == layer]


def find(viewport, name: str):
    return next((im for im in images(viewport)
                 if getattr(im, "name", "") == name), None)


def unique_name(viewport, base: str) -> str:
    have = {getattr(im, "name", "") for im in images(viewport)}
    if base not in have:
        return base
    k = 2
    while f"{base} ({k})" in have:
        k += 1
    return f"{base} ({k})"


def run(viewport, cmds) -> None:
    """The commands as ONE undo step."""
    cmds = [c for c in cmds if c is not None]
    if not cmds:
        return
    from core.history import CompoundCommand
    viewport.history.execute(cmds[0] if len(cmds) == 1
                             else CompoundCommand(cmds))
    viewport.update()


def add_cmd(path, frame, aspect: float, name: str, layer: str,
            opacity: float = OPACITY):
    from core.history import AddImagePlaneCommand
    from core.image_plane import ImagePlane
    im = ImagePlane(path=str(path), origin=_v(frame[0]), u=_v(frame[1]),
                    v=_v(frame[2]), aspect=float(aspect), name=name,
                    opacity=float(opacity), layer=layer, locked=False)
    return AddImagePlaneCommand(im), im


def frame_cmd(im, frame):
    from core.history import TransformImagePlaneCommand
    return TransformImagePlaneCommand(im, origin=_v(frame[0]),
                                      u=_v(frame[1]), v=_v(frame[2]))


def opacity_cmds(ims, value: float) -> list:
    from core.history import SetImagePlaneOpacityCommand
    return [SetImagePlaneOpacityCommand(im, float(value)) for im in ims
            if abs(float(im.opacity) - float(value)) > 1e-9]


def delete_cmd(ims):
    from core.history import DeleteImagePlanesCommand
    return DeleteImagePlanesCommand(list(ims)) if ims else None


def data_cmd(key: str, data):
    from core.history import SetPluginDataCommand
    return SetPluginDataCommand(key, data)


def lines_data(viewport) -> dict:
    d = (getattr(viewport.scene, "plugin_data", None) or {}).get(LINES_KEY)
    return d if isinstance(d, dict) else {}


# ---- a ghost level's references, painted over the plan ----------------------------
def ghost_opacity(doc: dict) -> float:
    """0..1 — the ghost levels' references (the bar's «Ghost %»)."""
    try:
        return max(0, min(100, int(doc.get("ref_ghost", GHOST)))) / 100.0
    except (TypeError, ValueError):
        return GHOST / 100.0


_PICS: dict = {}


def ghost_picture(im):
    """The picture's image (a copy at most GHOST_PX big), kept while its
    file stays the same. None: it cannot be read."""
    import os
    path = str(getattr(im, "path", "") or "")
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        return None
    got = _PICS.get(path)
    if got is not None and got[0] == stamp:
        return got[1]
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    pic = QImage(path)
    if pic.isNull():
        return None
    if max(pic.width(), pic.height()) > GHOST_PX:
        pic = pic.scaled(GHOST_PX, GHOST_PX, Qt.KeepAspectRatio,
                         Qt.SmoothTransformation)
    _PICS[path] = (stamp, pic)
    return pic


def paint_ghosts(viewport, painter, ims, z: float, alpha: float,
                 to_pixel) -> None:
    """These pictures painted over the view at the height ``z`` (the level
    worked on), ``alpha`` strong — seen, never in the model or the file
    (the host draws its pictures UNDER the model: a lower level's one
    would stay hidden under the floors). ``to_pixel(x, y, z)``."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPainter, QTransform
    if alpha <= 0:
        return
    for im in ims:
        pic = ghost_picture(im)
        if pic is None:
            continue
        o, u, v = frame_of(im)
        # the picture's top-left corner is the frame's origin + v (the
        # host's v goes UP the picture), its top-right + u, its bottom-left
        # the origin
        tl = to_pixel(o[0] + v[0], o[1] + v[1], z)
        tr = to_pixel(o[0] + u[0] + v[0], o[1] + u[1] + v[1], z)
        bl = to_pixel(o[0], o[1], z)
        if not (tl and tr and bl):
            continue
        w, h = float(pic.width()), float(pic.height())
        t = QTransform((tr[0] - tl[0]) / w, (tr[1] - tl[1]) / w,
                       (bl[0] - tl[0]) / h, (bl[1] - tl[1]) / h,
                       tl[0], tl[1])
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setOpacity(alpha)
        painter.setWorldTransform(t, True)
        painter.drawImage(QPointF(0, 0), pic)
        painter.restore()


# ---- sharp in 3D ---------------------------------------------------------------------
#: anisotropic filtering of a reference's picture (the host's own: 1, off —
#: a plan seen at a slant went grey and blurred, his ask 18/11/2026)
ANISO = 16.0


def sharpen(viewport) -> None:
    """The host's textures of the levels' REFERENCES (only those) drawn
    with anisotropic filtering: the GL texture is made by the host's
    ``_get_texture`` while it paints (the context current) — wrapped once
    on this viewport, undone by ``unsharpen``."""
    if "_axq_get_texture" in vars(viewport):
        return
    orig = getattr(viewport, "_get_texture", None)
    if not callable(orig):
        return
    # the paths that are NOT a reference's (materials…): asked once — kept
    # while the pictures in the scene stay the same ones
    plain = {"ims": None, "paths": set()}

    def get_texture(path, *a, **k):
        fade = (vars(viewport).get("_axq_fading") or {}).get(str(path))
        if fade is not None:                       # a faded reference
            tex = _faded_texture(viewport, str(path), fade)
            if tex is not None:
                return tex
        tex = orig(path, *a, **k)
        if tex is None:
            return tex
        try:
            p = str(path)
            ims = getattr(viewport.scene, "image_planes", None) or ()
            mark = tuple(id(im) for im in ims)
            if plain["ims"] != mark:
                plain["ims"], plain["paths"] = mark, set()
            if p in plain["paths"]:
                return tex
            if any(str(getattr(im, "path", "")) == p
                   and R.is_ref_layer(getattr(im, "layer", "") or "")
                   for im in ims):
                if tex.maximumAnisotropy() < ANISO and tex.hasFeature(
                        tex.Feature.AnisotropicFiltering):
                    tex.setMaximumAnisotropy(ANISO)
            else:
                plain["paths"].add(p)
        except Exception:  # noqa: BLE001 — the host's picture, as it was
            pass
        return tex

    viewport._axq_get_texture = orig
    viewport._get_texture = get_texture
    draw = getattr(viewport, "_draw_image_planes", None)
    if callable(draw):
        def draw_image_planes(*a, **k):
            # a reference under 100 % drawn OPAQUE, its picture lightened:
            # the host draws a see-through picture under the whole model,
            # and the floor's slab hid it (his file, 19/11/2026 — the
            # Level 2 plan at 20 % «disappeared», in plan and in 3D)
            back = []
            fading = {}
            try:
                for im in getattr(viewport.scene, "image_planes", None) or ():
                    op = float(getattr(im, "opacity", 1.0))
                    if op < OPAQUE and R.is_ref_layer(
                            getattr(im, "layer", "") or ""):
                        back.append((im, im.opacity))
                        fading[str(getattr(im, "path", ""))] = op
                        im.opacity = 1.0
            except Exception:  # noqa: BLE001 — drawn as the host has it
                pass
            viewport._axq_fading = fading
            try:
                return draw(*a, **k)
            finally:
                for im, op in back:
                    im.opacity = op
                viewport._axq_fading = {}
        viewport._axq_draw_images = draw
        viewport._draw_image_planes = draw_image_planes


#: the host's own test: a picture this opaque or more writes depth
OPAQUE = 0.999


def faded_image(img, fade: float):
    """``img`` lightened towards white, ``fade`` strong (1: as it is, 0:
    white) — its transparency kept."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter
    out = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)
    p = QPainter(out)
    p.setCompositionMode(QPainter.CompositionMode_SourceAtop)
    p.setOpacity(max(0.0, min(1.0, 1.0 - float(fade))))
    p.fillRect(out.rect(), Qt.white)
    p.end()
    return out


def _faded_texture(viewport, path: str, fade: float):
    """The GL texture of a reference's picture, lightened (``faded_image``)
    — made from the host's own decoded picture (mirrored for GL, its size
    capped as the host's), one kept per picture: a new strength replaces
    it. Made while the view paints (its context current). None: the
    host's picture, as it is."""
    import os
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        return None
    key = (round(float(fade), 3), stamp)
    cache = vars(viewport).setdefault("_axq_faded", {})
    got = cache.get(path)
    if got is not None and got[0] == key:
        return got[1]
    try:
        from PySide6.QtOpenGL import QOpenGLTexture
        import views.viewport as VPm
        dec = VPm._decoded_texture(path)
        if not dec or dec[0] is None or dec[0].isNull():
            return None
        tex = QOpenGLTexture(faded_image(dec[0], fade))
        tex.setWrapMode(QOpenGLTexture.Repeat)
        tex.setMinificationFilter(QOpenGLTexture.LinearMipMapLinear)
        tex.setMagnificationFilter(QOpenGLTexture.Linear)
        if tex.hasFeature(QOpenGLTexture.Feature.AnisotropicFiltering):
            tex.setMaximumAnisotropy(ANISO)
    except Exception:  # noqa: BLE001 — the host's picture, as it is
        return None
    if got is not None:
        try:
            got[1].destroy()
        except Exception:  # noqa: BLE001
            pass
    cache[path] = (key, tex)
    return tex


def unsharpen(viewport) -> None:
    if vars(viewport).pop("_axq_get_texture", None) is not None:
        vars(viewport).pop("_get_texture", None)
    if vars(viewport).pop("_axq_draw_images", None) is not None:
        vars(viewport).pop("_draw_image_planes", None)
    vars(viewport).pop("_axq_fading", None)
    for _key, tex in (vars(viewport).pop("_axq_faded", None) or {}).values():
        try:
            tex.destroy()
        except Exception:  # noqa: BLE001
            pass


# ---- what is shown -------------------------------------------------------------------
def sync(viewport, doc: dict, current_id: str | None) -> bool:
    """Each level's references shown only while it is the one worked on,
    its eye on, its «Show» on. True when something changed."""
    off = set(doc.get("ref_off") or [])
    changed = False
    for lv in doc.get("levels") or []:
        name = layer_of(lv)
        L = compat._layer(viewport, name)
        if L is None and not images(viewport, name):
            continue
        want = (lv["id"] == current_id and lv["id"] not in off
                and compat.layer_visible(viewport,
                                         compat.level_layer(lv["name"])))
        # its pictures on a layer the file lost (his file, 18/11/2026: the
        # Level 1 picture over the slab with its «Show» off, taking the
        # slab's clicks): the host draws them all — the layer comes back
        if L is None or bool(L.visible) != want:
            compat.set_layer_visible(viewport, name, want)
            changed = True
    return changed


def follow_levels(viewport, doc: dict, elevations) -> list:
    """The commands that lay each level's references on its floor again
    (a level's height changed)."""
    if not doc.get("levels"):
        return []
    try:
        from . import model
        z = elevations(doc["levels"], doc["project"]["ground_level"]
                       if model.has_project(doc) else 0.0)
    except Exception:  # noqa: BLE001 — no heights: nothing moves
        return []
    cmds = []
    for lv, e in zip(doc["levels"], z):
        for im in images(viewport, layer_of(lv)):
            f = frame_of(im)
            want = float(e) + R.LIFT
            if abs(f[0][2] - want) > 1e-6:
                cmds.append(frame_cmd(im, R.at_z(f, want)))
    return cmds


# ---- the level's drawing from a PDF ------------------------------------------------
def drawing(viewport, doc: dict, level_id: str, cache: dict):
    """The level's drawing as its readers want it ("segs" in metres): a
    DXF's as stored; a PDF's placed with its picture now (cached while
    the picture stays where it is). None: no drawing."""
    u = (doc.get("underlays") or {}).get(level_id)
    if not u or not u.get("ref"):
        return u
    im = find(viewport, u["ref"])
    entry = lines_data(viewport).get(u["ref"])
    if im is None or not isinstance(entry, dict):
        return dict(u, segs=[])           # (its picture deleted: gone too)
    fr = frame_of(im)
    uv = entry.get("uv") or []
    key = (u["ref"], fr, id(uv), len(uv))
    hit = cache.get(level_id)
    if hit is None or hit[0] != key:
        hit = (key, R.segs_in_world(fr, uv))
        cache[level_id] = hit
    return dict(u, segs=hit[1])


# ---- files -----------------------------------------------------------------------
def image_aspect(path) -> float | None:
    """An image file's height / width (None: not an image)."""
    from PySide6.QtGui import QImageReader
    r = QImageReader(str(path))
    s = r.size()
    if not s.isValid() or s.width() <= 0:
        return None
    return s.height() / s.width()


def _cache_dir() -> Path:
    try:
        from core.texture import texture_cache_root
        d = Path(texture_cache_root())
    except Exception:  # noqa: BLE001 — the user's folder then
        d = Path.home() / ".archxq_it" / "refs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def pdf_pages(path) -> list:
    """[(width, height) in points] of each page."""
    from . import pdfread as P
    with P.Pdf(path) as doc:
        return [doc.size(i) for i in range(doc.pages())]


def pdf_page(path, page: int) -> dict:
    """Page ``page`` of the PDF: {"png" (its picture, in the host's
    texture cache), "aspect", "w_pt", "h_pt", "scale" (read from its text,
    or None), "lines" ([(fu0, fv0, fu1, fv1, w_mm)…])}."""
    from PySide6.QtGui import QImage

    from . import pdfread as P
    data = Path(path).read_bytes()
    with P.Pdf(path) as doc:
        w_pt, h_pt = doc.size(page)
        px = R.raster_px(w_pt, h_pt)
        buf, stride = doc.render(page, *px)
        text = doc.text(page)
        lines = doc.lines(page)
    img = QImage(buf, px[0], px[1], stride, QImage.Format_RGB32).copy()
    tag = hashlib.sha1(data + b"|%d|%dx%d" % (page, *px)).hexdigest()[:16]
    out = _cache_dir() / f"archxq_pdf_{tag}.png"
    if not out.is_file():
        if not img.save(str(out), "PNG"):
            raise RuntimeError("its picture could not be written")
    return {"png": out, "aspect": px[1] / px[0], "w_pt": w_pt,
            "h_pt": h_pt, "scale": R.scale_from_text(text), "lines": lines}
