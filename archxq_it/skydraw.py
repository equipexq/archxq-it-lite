"""The sky picture drawn behind the 3D view (PLANO_FUNDO_HDRI.md, H0, 14/11/2026).

IngeTrazo paints its gradient sky in `Viewport._draw_sky(mvp)`, called by
`_paint_frame` before the model and only when the sky is on (not in plan
styles, transparent exports, base maps, terrain or photo meshes). We put our
own `_draw_sky` on the INSTANCE (a plain Python method, no Qt virtual):
it lets the host paint its gradient first (its ground stays), then lays the
picture over it with one full-screen triangle whose shader turns each pixel
into a direction (inverse of the camera's mvp) and reads the equirectangular
picture there. Nothing is geometry: no selection, quantities, IFC, Extents
or shadows. Any error puts the host's own sky back for the session.
"""
from __future__ import annotations

import math
import sys

_GL_DEPTH_TEST = 0x0B71
_GL_BLEND = 0x0BE2
_GL_SRC_ALPHA = 0x0302
_GL_ONE_MINUS_SRC_ALPHA = 0x0303
_GL_TRIANGLES = 0x0004

_VS = """#version 330 core
out vec2 ndc;
void main() {
    vec2 p = vec2(gl_VertexID == 1 ? 3.0 : -1.0, gl_VertexID == 2 ? 3.0 : -1.0);
    ndc = p;
    gl_Position = vec4(p, 0.0, 1.0);
}
"""

_FS = """#version 330 core
in vec2 ndc;
uniform mat4 inv;
uniform float rot;
uniform float lift;
uniform int photo;
uniform int ortho;
uniform vec3 fwd;
uniform vec3 rgt;
uniform vec3 upv;
uniform vec2 tanh;
uniform int own_ground;
uniform vec3 gcol;
uniform sampler2D sky;
out vec4 frag;
const float PI = 3.14159265;
void main() {
    vec3 d;
    if (ortho == 1) {            // parallel view: the rays of a 60° camera looking the same way
        d = normalize(fwd + ndc.x * tanh.x * rgt + ndc.y * tanh.y * upv);
    } else {
        vec4 a = inv * vec4(ndc, -1.0, 1.0);
        vec4 b = inv * vec4(ndc, 1.0, 1.0);
        d = normalize(b.xyz / b.w - a.xyz / a.w);
    }
    float lat = asin(clamp(d.z, -1.0, 1.0));
    float s = (atan(d.y, d.x) + rot) / (2.0 * PI);
    float u1 = fract(s);
    float u2 = fract(s + 0.5) - 0.5;
    float ux1 = dFdx(u1), ux2 = dFdx(u2), uy1 = dFdy(u1), uy2 = dFdy(u2);
    float ux = abs(ux1) < abs(ux2) ? ux1 : ux2;
    float uy = abs(uy1) < abs(uy2) ? uy1 : uy2;
    float v = clamp(0.5 + (lat - lift) / PI, 0.0, 1.0);
    vec3 c = textureGrad(sky, vec2(u1, v), vec2(ux, dFdx(v)), vec2(uy, dFdy(v))).rgb;
    float al = photo == 1 ? 1.0 : smoothstep(-0.003, 0.003, lat);
    if (photo != 1 && own_ground == 1) {
        // the ground under the horizon (H3): the picture's horizon at this
        // bearing fades in ~3° into a ground of the picture's own tone, a
        // little darker towards the feet — no «step», no white line
        al = 1.0;
        if (lat < 0.0) {
            float vh = clamp(0.5 + (0.004 - lift) / PI, 0.0, 1.0);
            // (a blurred band: the picture's grass and trunks would
            // otherwise run down in streaks)
            vec3 hz = textureLod(sky, vec2(u1, vh), 6.0).rgb;
            float dep = -lat;
            vec3 g = gcol * (1.0 - 0.18 * smoothstep(0.0, 0.9, dep));
            c = mix(hz, g, smoothstep(0.0, 0.05, dep));
        }
    }
    frag = vec4(c, al);
}
"""

_PAINTERS: dict = {}       # id(viewport) -> SkyPainter
_FAILED = False            # one error: the host's sky for the rest of the session


def _log(msg: str) -> None:
    try:
        sys.stderr.write("[ArchXQ sky] %s\n" % msg)
    except Exception:
        pass


class SkyPainter:
    """One per 3D view: its program, its triangle and its picture."""

    def __init__(self, viewport, image, rotation_deg=0.0, lift_deg=0.0, photo=False,
                 when=None):
        self.vp = viewport
        self.when = when                      # callable: False = the host's sky this frame
        self.image = image                    # QImage, RGB, 2:1
        self.rot = math.radians(rotation_deg)
        self.lift = math.radians(lift_deg)
        self.photo = bool(photo)
        self.ground = None                    # (r, g, b) 0–1: our ground; None: the host's
        self.orig = None
        self.prog = None
        self.vao = None
        self.tex = None
        self.dirty = True
        self.frames = 0
        self.error = None

    # -- the host calls this, inside paintGL, context current ------------------------
    def draw(self, mvp) -> None:
        self.orig(mvp)                        # the host's gradient (its ground stays)
        try:
            if self.when is not None and not self.when():
                return
            self._draw(mvp)
            self.frames += 1
        except Exception as e:                # never break the view
            global _FAILED
            _FAILED = True
            self.error = "%s: %s" % (type(e).__name__, e)
            _log("the sky picture is off for this session — " + self.error)
            self._detach()
            try:
                self.vp._program.bind()
            except Exception:
                pass

    def _draw(self, mvp) -> None:
        from PySide6.QtGui import QVector2D
        from PySide6.QtOpenGL import (QOpenGLShader, QOpenGLShaderProgram,
                                      QOpenGLTexture, QOpenGLVertexArrayObject)
        gl = self.vp._gl
        if self.prog is None:
            p = QOpenGLShaderProgram()
            if not (p.addShaderFromSourceCode(QOpenGLShader.Vertex, _VS)
                    and p.addShaderFromSourceCode(QOpenGLShader.Fragment, _FS)
                    and p.link()):
                raise RuntimeError("shader: " + p.log())
            self.prog = p
            self.vao = QOpenGLVertexArrayObject()
            self.vao.create()
        if self.dirty or self.tex is None:
            if self.tex is not None:
                self.tex.destroy()
            t = QOpenGLTexture(self.image.mirrored(False, True),
                               QOpenGLTexture.GenerateMipMaps)
            t.setMinMagFilters(QOpenGLTexture.LinearMipMapLinear, QOpenGLTexture.Linear)
            t.setWrapMode(QOpenGLTexture.DirectionS, QOpenGLTexture.Repeat)
            t.setWrapMode(QOpenGLTexture.DirectionT, QOpenGLTexture.ClampToEdge)
            t.setMaximumAnisotropy(8.0)
            self.tex = t
            self.dirty = False
        inv, ok = mvp.inverted()
        if not ok:
            return
        basis = _basis(inv, self.vp)
        blend = gl.glIsEnabled(_GL_BLEND)
        gl.glDisable(_GL_DEPTH_TEST)
        gl.glDepthMask(0)
        gl.glEnable(_GL_BLEND)
        gl.glBlendFunc(_GL_SRC_ALPHA, _GL_ONE_MINUS_SRC_ALPHA)
        self.prog.bind()
        self.prog.setUniformValue("inv", inv)
        self.prog.setUniformValue1f("rot", float(self.rot))
        self.prog.setUniformValue1f("lift", float(self.lift))
        self.prog.setUniformValue1i("photo", 1 if self.photo else 0)
        self.prog.setUniformValue1i("sky", 0)
        self.prog.setUniformValue1i("ortho", 1 if basis else 0)
        self.prog.setUniformValue1i("own_ground", 1 if self.ground else 0)
        if self.ground:
            from PySide6.QtGui import QVector3D
            self.prog.setUniformValue("gcol", QVector3D(*self.ground))
        if basis:
            f, r, u, tx, ty = basis
            self.prog.setUniformValue("fwd", f)
            self.prog.setUniformValue("rgt", r)
            self.prog.setUniformValue("upv", u)
            self.prog.setUniformValue("tanh", QVector2D(tx, ty))
        self.tex.bind(0)
        self.vao.bind()
        gl.glDrawArrays(_GL_TRIANGLES, 0, 3)
        self.vao.release()
        self.tex.release(0)
        self.prog.release()
        if not blend:
            gl.glDisable(_GL_BLEND)
        gl.glDepthMask(1)
        gl.glEnable(_GL_DEPTH_TEST)
        self.vp._program.bind()               # the host goes on with its own program

    # -- on / off --------------------------------------------------------------------
    def _attach(self) -> None:
        self.orig = type(self.vp)._draw_sky.__get__(self.vp)
        self.vp._draw_sky = self.draw

    def _detach(self) -> None:
        try:
            if self.vp.__dict__.get("_draw_sky") is not None:
                del self.vp._draw_sky
        except Exception:
            pass

    def free(self) -> None:
        """Let go of the GL objects (its context made current) — and give
        back the context that was current before. «doneCurrent» left NONE
        current: called while the host opens a project (its scene closed,
        ``skyview.closed``), the host's next texture was made with no
        context and IngeTrazo fell (Qt6OpenGL.dll, access violation in
        ``_get_texture`` — every project opened, 14/11/2026)."""
        try:
            from PySide6.QtGui import QOpenGLContext
            prev = QOpenGLContext.currentContext()
            surf = prev.surface() if prev is not None else None
        except Exception:
            prev = surf = None
        try:
            self.vp.makeCurrent()
            if self.tex is not None:
                self.tex.destroy()
            if self.vao is not None:
                self.vao.destroy()
            self.prog = None
        except Exception:
            pass
        try:
            if prev is not None and surf is not None:
                prev.makeCurrent(surf)        # as it was before
            else:
                self.vp.doneCurrent()         # none was: none is
        except Exception:
            pass
        self.tex = self.vao = self.prog = None


def _basis(inv, viewport):
    """For a parallel view, (forward, right, up, tan x, tan y) of a 60°
    camera looking the same way; None for a perspective one."""
    from PySide6.QtGui import QVector3D, QVector4D

    def ray(x, y):
        a = inv.map(QVector4D(x, y, -1.0, 1.0))
        b = inv.map(QVector4D(x, y, 1.0, 1.0))
        if abs(a.w()) < 1e-12 or abs(b.w()) < 1e-12:
            return None
        return (b.toVector3D() / b.w() - a.toVector3D() / a.w()).normalized()

    c, e = ray(0.0, 0.0), ray(0.9, 0.9)
    if c is None or e is None or QVector3D.dotProduct(c, e) < 0.99999:
        return None                               # perspective: the shader does it
    def point(x, y):
        v = inv.map(QVector4D(x, y, 0.0, 1.0))
        return v.toVector3D() / v.w()
    o = point(0.0, 0.0)
    r, u = point(1.0, 0.0) - o, point(0.0, 1.0) - o
    rl, ul = r.length(), u.length()
    if rl < 1e-12 or ul < 1e-12:
        return None
    t = math.tan(math.radians(30.0))
    return c, r / rl, u / ul, t * rl / ul, t          # 60° tall, wide as the view


def available(viewport) -> str:
    """'' when the sky can be drawn in this view, else why not."""
    if _FAILED:
        return "the sky picture stopped after an error in this session"
    if not callable(getattr(type(viewport), "_draw_sky", None)):
        return "this IngeTrazo version has no sky to replace"
    if not hasattr(viewport, "_gl") or not hasattr(viewport, "_program"):
        return "this IngeTrazo version draws in a way we don't know"
    return ""


def show(viewport, image, rotation_deg=0.0, lift_deg=0.0, photo=False,
         when=None, ground=None) -> SkyPainter:
    """Put the picture (a 2:1 QImage) behind this view. `when`: a callable
    asked each frame; False = the host's own sky (plan, elevations, …)."""
    why = available(viewport)
    if why:
        raise RuntimeError(why)
    sp = _PAINTERS.get(id(viewport))
    if sp is None:
        sp = SkyPainter(viewport, image, rotation_deg, lift_deg, photo, when)
        sp._attach()
        _PAINTERS[id(viewport)] = sp
    else:
        sp.image, sp.dirty, sp.when = image, True, when
        sp.rot, sp.lift, sp.photo = (math.radians(rotation_deg),
                                     math.radians(lift_deg), bool(photo))
    sp.ground = tuple(ground) if ground else None
    _refresh(viewport)
    return sp


def set_view(viewport, rotation_deg=None, lift_deg=None, photo=None) -> None:
    sp = _PAINTERS.get(id(viewport))
    if sp is None:
        return
    if rotation_deg is not None:
        sp.rot = math.radians(rotation_deg)
    if lift_deg is not None:
        sp.lift = math.radians(lift_deg)
    if photo is not None:
        sp.photo = bool(photo)
    _refresh(viewport)


def hide(viewport) -> None:
    """The host's own sky again in this view."""
    sp = _PAINTERS.pop(id(viewport), None)
    if sp is not None:
        sp._detach()
        sp.free()
    _refresh(viewport)


def painter(viewport):
    return _PAINTERS.get(id(viewport))


def _refresh(viewport) -> None:
    if hasattr(viewport, "_frame_cache"):
        viewport._frame_cache = None
    viewport.update()
