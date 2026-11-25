# ArchXQ IT — Copyright (C) 2026 Orlando Souza · XQ (www.xq.com.br)
# SPDX-License-Identifier: GPL-3.0-or-later
"""HELP NOTES — the author's own text and pictures on the HELP window's
pages (guide.py — his ask, 22/11/2026: «colocar imagem e texto, a minha
experiência, direto no Help, sem gerar fora»; first put on the F1 cards by
my mistake, moved the same day: the Help window has the tools listed on
its left). The first step of a manual written in the program: one folder
per page (an ELEMENTS key), so the whole manual can grow from it (an
index, a search, the site, the AI — later).

    help_notes/<topic>/pt-BR.md    the text (Markdown), one file a language
    help_notes/<topic>/en.md, de.md
    help_notes/<topic>/img_*.png   its pictures (shared by the languages)
    help_notes/<topic>/meta.json   {lang: {"updated": "2026-11-23T14:32",
                                           "version": "0.27.0" | "next",
                                           "from": <pt-BR's updated>,
                                           "title": "Minha experiência"}}

- The section's HEADING is his too, a language each (his ask, 22/11/2026:
  «um campo para eu definir aquele título»); none written: «Tips and
  experience» in the reader's language.

- Every note carries WHEN it was last changed and in WHICH version — shown
  discreetly at the page's foot («Updated 23/11/2026, 14:32 · version 0.27.0»).
  Saved in the source it is «next»: build_pro.ps1 writes the version it
  ships in.
- A translation keeps «from» = the Portuguese it was made from: older
  than the Portuguese now → out of date (the editor says so; the reader
  sees its own, older date).
- WRITING is the AUTHOR's only: the editor (✎ on the Help window) exists when
  ArchXQ runs from its source (``author_mode``) — never in a build a
  customer installs.
"""
from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QUrl, Signal
from PySide6.QtGui import (QFont, QImage, QKeySequence, QPixmap, QShortcut,
                           QTextBlockFormat, QTextCharFormat, QTextCursor,
                           QTextDocument, QTextImageFormat, QTextListFormat)
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QTextEdit, QVBoxLayout)

from .i18n import tr

ROOT = Path(__file__).with_name("help_notes")
SOURCE = "pt-BR"                      # the language he writes in
LANGS = ("pt-BR", "en", "de")
IMG_MAX = 1600                        # px, a picture's widest side kept
#: the notes are DRAFTS until he decides they go live (his call, 22/11/2026:
#: «fica inativo até que se resolva que compensa»): only the author sees
#: them, marked as such, and build_pro.ps1 does not ship the folder.
#: Going live = True here AND $notesLive = $true in build_pro.ps1.
PUBLISHED = False
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
           "Oct", "Nov", "Dec")
_IMG_MD = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")


# ---- who writes -------------------------------------------------------------------
def author_mode() -> bool:
    """ArchXQ runs from its source (the author's): «prototype» in its
    version — every build writes a number there."""
    from . import __version__
    return "prototype" in __version__


# ---- the files ----------------------------------------------------------------------
def folder(topic: str) -> Path:
    return ROOT / topic


def meta(topic: str) -> dict:
    try:
        raw = json.loads((folder(topic) / "meta.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def text(topic: str, lang: str) -> str:
    """The note's Markdown in ``lang`` ("" none)."""
    try:
        return (folder(topic) / f"{lang}.md").read_text("utf-8").strip()
    except OSError:
        return ""


def title(topic: str, lang: str) -> str:
    """The heading he gave the note in ``lang`` ("" none: the standard one)."""
    return str((meta(topic).get(lang) or {}).get("title") or "").strip()


def heading(topic: str, lang: str) -> str:
    """What the Help page shows above the note."""
    return title(topic, lang) or tr("Tips and experience")


def readable(md: str) -> str:
    """``md`` as Qt reads it: a picture with no words between its brackets
    («![](img.png)», as written by hand) would be dropped — given some."""
    return re.sub(r"!\[\]\(", "![image](", md or "")


def lang_for(topic: str, lang: str) -> str | None:
    """The language a reader in ``lang`` gets: their own; a language we
    have no notes in, English; none written: None (no Portuguese to a
    reader who may not read it)."""
    if lang not in LANGS:
        lang = "en"
    return lang if text(topic, lang) else None


def images(md: str) -> list[str]:
    return [m for m in _IMG_MD.findall(md or "") if not m.startswith(
        ("http:", "https:"))]


def stale(topic: str, lang: str) -> bool:
    """A translation made from an older Portuguese than the one now."""
    if lang == SOURCE or not text(topic, lang):
        return False
    m = meta(topic)
    src = (m.get(SOURCE) or {}).get("updated")
    return bool(src) and (m.get(lang) or {}).get("from") != src


def save(topic: str, lang: str, md: str, heading: str | None = None) -> dict:
    """``md`` stored for ``lang``, stamped now («next» version: the build
    writes the real one), with its ``heading`` (None: the one it had; "":
    the standard one). Pictures no language uses any more are removed.
    Returns the topic's meta."""
    f = folder(topic)
    f.mkdir(parents=True, exist_ok=True)
    md = (md or "").strip()
    (f / f"{lang}.md").write_text(md + "\n" if md else "", "utf-8")
    m = meta(topic)
    rec = {"updated": datetime.now().strftime("%Y-%m-%dT%H:%M"),
           "version": "next"}
    if lang != SOURCE:
        rec["from"] = (m.get(SOURCE) or {}).get("updated", "")
    if heading is None:
        heading = (m.get(lang) or {}).get("title") or ""
    heading = " ".join(str(heading).split())
    if heading:
        rec["title"] = heading
    m[lang] = rec
    (f / "meta.json").write_text(json.dumps(m, indent=1, ensure_ascii=False)
                                 + "\n", "utf-8")
    used = set()
    for code in LANGS:
        used.update(images(text(topic, code)))
    for p in f.glob("img_*.png"):
        if p.name not in used:
            try:
                p.unlink()
            except OSError:
                pass
    return m


def save_image(topic: str, img: QImage) -> str | None:
    """A picture (pasted / picked) stored in the topic's folder, its widest
    side IMG_MAX at most — its file name, None if it could not be."""
    if img is None or img.isNull():
        return None
    if max(img.width(), img.height()) > IMG_MAX:
        img = img.scaled(IMG_MAX, IMG_MAX, Qt.KeepAspectRatio,
                         Qt.SmoothTransformation)
    f = folder(topic)
    f.mkdir(parents=True, exist_ok=True)
    name = time.strftime("img_%Y%m%d_%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}.png"
    return name if img.save(str(f / name), "PNG") else None


# ---- its date and version, discreetly -----------------------------------------------
def stamp(topic: str, lang: str) -> str:
    """«Updated 23/11/2026, 14:32 · version 0.27.0» in the reader's
    language ("" none)."""
    rec = meta(topic).get(lang) or {}
    try:
        when = datetime.strptime(rec.get("updated", ""), "%Y-%m-%dT%H:%M")
    except ValueError:
        return ""
    from . import i18n
    ui = i18n.current()
    if ui == "pt-BR":
        day = when.strftime("%d/%m/%Y")
    elif ui == "de":
        day = when.strftime("%d.%m.%Y")
    else:
        day = f"{when.day} {_MONTHS[when.month - 1]} {when.year}"
    hour = when.strftime("%H:%M")
    ver = str(rec.get("version") or "next")
    if ver == "next":
        return tr("Updated {day}, {hour} · next version", day=day, hour=hour)
    return tr("Updated {day}, {hour} · version {version}", day=day,
              hour=hour, version=ver)


# ---- showing it -------------------------------------------------------------------------
def fit_images(doc: QTextDocument, base: Path, width: int) -> None:
    """Every picture of ``doc`` as wide as ``width`` at most (its own size
    when smaller) — Markdown keeps no size."""
    plain = doc.toPlainText()
    for i, ch in enumerate(plain):
        if ch != "￼":
            continue
        cur = QTextCursor(doc)
        cur.setPosition(i)
        cur.setPosition(i + 1, QTextCursor.KeepAnchor)
        fmt = cur.charFormat()
        if not fmt.isImageFormat():
            continue
        f = fmt.toImageFormat()
        img = QImage(str(base / f.name()))
        if img.isNull() or img.width() <= 0:
            continue
        w = min(img.width(), width)
        f.setWidth(w)
        f.setHeight(img.height() * w / img.width())
        cur.setCharFormat(f)


def image_at(edit, pos) -> str | None:
    """The picture's file name under ``pos`` (a viewport point), or None."""
    cur = edit.cursorForPosition(pos)
    for p in (cur.position(), cur.position() - 1):
        if p < 0:
            continue
        c = QTextCursor(edit.document())
        c.setPosition(p)
        c.setPosition(p + 1, QTextCursor.KeepAnchor)
        fmt = c.charFormat()
        if fmt.isImageFormat():
            rect = edit.cursorRect(c)
            f = fmt.toImageFormat()
            h = f.height() or rect.height()
            if rect.left() - 4 <= pos.x() <= rect.left() + f.width() + 4 \
                    and rect.bottom() - h - 4 <= pos.y() <= rect.bottom() + 4:
                return f.name()
    return None


PAGE_W = 560                          # px, a picture's width on a Help page


def reader_lang(topic: str) -> str | None:
    """The language of ``topic``'s note for whoever reads now: their own
    (English for a language we have no notes in); the AUTHOR — his ArchXQ
    in English — also sees the Portuguese he wrote before it is translated.
    None: nothing to show."""
    from . import i18n
    if not PUBLISHED and not author_mode():
        return None                      # drafts: the author's eyes only
    lang = lang_for(topic, i18n.current())
    if lang is None and author_mode() and text(topic, SOURCE):
        lang = SOURCE
    return lang


def page_section(topic: str) -> str:
    """The author's tips as HTML for the Help page (guide.py): a heading,
    his text and pictures, and at its foot, discreet, when and in which
    version it was last changed. "" when there is no note."""
    lang = reader_lang(topic)
    if lang is None:
        return ""
    base = folder(topic)
    doc = QTextDocument()
    doc.setBaseUrl(QUrl.fromLocalFile(str(base) + "/"))
    doc.setMarkdown(readable(text(topic, lang)))
    fit_images(doc, base, PAGE_W)
    m = re.search(r"<body[^>]*>(.*)</body>", doc.toHtml(), re.S)
    body = m.group(1) if m else ""

    def absolute(mm):
        name = mm.group(1)
        if ":" in name or name.startswith("/"):
            return mm.group(0)
        return 'src="' + QUrl.fromLocalFile(str(base / name)).toString() + '"'
    body = re.sub(r'src="([^"]+)"', absolute, body)
    # a picture alone in its paragraph: in a div — the page's 140 % line
    # height made its line ~40 % taller (an empty band under it), as
    # guide.py found for its own figures
    body = re.sub(r"<p[^>]*>\s*(<img[^>]*>)\s*</p>",
                  r"<div style='margin: 8px 0 4px 0'>\1</div>", body)
    foot = stamp(topic, lang)
    draft = "" if PUBLISHED else (
        "<p style='background:#3a3220; color:#e8b33c; padding:6px 10px'>"
        "<b>Draft — not published.</b> Only you see this (the source); a "
        "build does not take it until the notes go live.</p>")
    return ("<h2>" + html.escape(heading(topic, lang)) + "</h2>" + draft + body
            + (f"<p style='color:#8a939d; font-size:11px; margin-top:14px'>"
               f"{foot}</p>" if foot else ""))


class ImageClicks(QObject):
    """On a QTextBrowser: a picture under the mouse shows a hand; a click
    shows it big."""

    def __init__(self, browser) -> None:
        super().__init__(browser)
        self.browser = browser
        browser.viewport().setMouseTracking(True)
        browser.viewport().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        t = event.type()
        if t == QEvent.MouseMove:
            on = image_at(self.browser, event.position().toPoint())
            obj.setCursor(Qt.PointingHandCursor if on else Qt.ArrowCursor)
        elif t == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            name = image_at(self.browser, event.position().toPoint())
            if name:
                path = QUrl(name).toLocalFile() if name.startswith("file:")                     else name
                show_big(Path(path), self.browser.window())
                return True
        return False


def show_big(path: Path, parent=None) -> None:
    """A picture, big — a click or Esc closes it."""
    pix = QPixmap(str(path))
    if pix.isNull():
        return
    d = QDialog(parent, Qt.Dialog | Qt.FramelessWindowHint)
    d.setAttribute(Qt.WA_DeleteOnClose, True)
    d.setStyleSheet("QDialog { background: rgb(20, 22, 25); "
                    "border: 1px solid #3c4148; }")
    lay = QVBoxLayout(d)
    lay.setContentsMargins(8, 8, 8, 8)
    screen = (parent.screen() if parent is not None else None)
    room = screen.availableGeometry().size() * 0.88 if screen is not None \
        else QSize(1400, 900)
    if pix.width() > room.width() or pix.height() > room.height():
        pix = pix.scaled(room, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    lab = QLabel()
    lab.setPixmap(pix)
    lab.setCursor(Qt.PointingHandCursor)
    lab.mousePressEvent = lambda _e: d.close()
    lay.addWidget(lab)
    d.adjustSize()
    if screen is not None:
        g = screen.availableGeometry()
        d.move(g.center() - d.rect().center())
    d.show()


# ---- writing it (the author only) ----------------------------------------------------------
class _Edit(QTextEdit):
    """A text box that takes a pasted picture (Win+Shift+S, then Ctrl+V)
    or a picture file dropped / pasted — stored in the topic's folder."""
    pasted = Signal()

    def __init__(self, topic: str) -> None:
        super().__init__()
        self.topic = topic

    def keyPressEvent(self, event) -> None:
        # Enter at the end of a heading: the next line is plain text (as in
        # any word processor), not another heading in bold
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cur = self.textCursor()
            if cur.blockFormat().headingLevel() and cur.atBlockEnd():
                cur.insertBlock(QTextBlockFormat(), QTextCharFormat())
                self.setTextCursor(cur)
                self.setCurrentCharFormat(QTextCharFormat())
                return
        super().keyPressEvent(event)

    def canInsertFromMimeData(self, src) -> bool:
        return src.hasImage() or src.hasUrls() or \
            super().canInsertFromMimeData(src)

    def insertFromMimeData(self, src) -> None:
        if src.hasImage():
            self.put_image(QImage(src.imageData()))
            return
        if src.hasUrls():
            done = False
            for u in src.urls():
                p = u.toLocalFile()
                if p.lower().endswith((".png", ".jpg", ".jpeg", ".bmp",
                                       ".webp", ".gif")):
                    self.put_image(QImage(p))
                    done = True
            if done:
                return
        super().insertFromMimeData(src)

    def put_image(self, img: QImage) -> None:
        name = save_image(self.topic, img)
        if not name:
            return
        f = QTextImageFormat()
        f.setName(name)
        stored = QImage(str(folder(self.topic) / name))
        w = min(stored.width(), max(200, self.viewport().width() - 30))
        f.setWidth(w)
        f.setHeight(stored.height() * w / max(1, stored.width()))
        cur = self.textCursor()
        cur.insertImage(f)
        cur.insertBlock()
        self.setTextCursor(cur)
        self.pasted.emit()


class NoteEditor(QDialog):
    """«Edit help: Wall» — the page's note in a language: text with bold,
    italics, headings, lists and pictures; Save stamps it."""

    def __init__(self, topic: str, title: str, parent=None,
                 on_saved=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.topic, self.on_saved = topic, on_saved
        self.lang = SOURCE
        self.dirty = False
        title = title.removeprefix("ArchXQ | ")
        self.setWindowTitle(f"Edit help: {title}")
        self.resize(760, 720)
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel(f"<b>{title}</b>  ·  {topic}"))
        top.addStretch(1)
        self.langs = QComboBox()
        for code in LANGS:
            self.langs.addItem(code, code)
        self.langs.currentIndexChanged.connect(self._lang_changed)
        top.addWidget(self.langs)
        lay.addLayout(top)
        # the section's heading on the Help page — his own, a language each
        row = QHBoxLayout()
        row.addWidget(QLabel("Title"))
        self.title = QLineEdit()
        self.title.setToolTip("The heading above this text on the Help page "
                              "— empty: the standard one")
        self.title.setStyleSheet("QLineEdit { border: 1px solid #3c4148; "
                                 "border-radius: 3px; padding: 4px 6px; }")
        self.title.textEdited.connect(self._changed)
        row.addWidget(self.title, 1)
        lay.addLayout(row)
        self.warn = QLabel()
        self.warn.setStyleSheet("color: #e8a33c;")
        lay.addWidget(self.warn)
        bar = QHBoxLayout()
        for label, tip, fn in (("B", "Bold (Ctrl+B)", self._bold),
                               ("I", "Italic (Ctrl+I)", self._italic),
                               ("H", "Heading", self._heading),
                               ("•", "List", self._list),
                               ("Picture…", "A picture from a file", self._pick)):
            b = QPushButton(label)
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(fn)
            if label == "B":
                f = b.font(); f.setBold(True); b.setFont(f)
            if label == "I":
                f = b.font(); f.setItalic(True); b.setFont(f)
            bar.addWidget(b)
        hint = QLabel("A screenshot: Win+Shift+S, then Ctrl+V here")
        hint.setStyleSheet("color: #8a939d;")
        bar.addWidget(hint, 1)
        lay.addLayout(bar)
        self.edit = _Edit(topic)
        self.edit.setAcceptRichText(False)        # pasted text: plain
        self.edit.textChanged.connect(self._changed)
        lay.addWidget(self.edit, 1)
        QShortcut(QKeySequence("Ctrl+B"), self, self._bold)
        QShortcut(QKeySequence("Ctrl+I"), self, self._italic)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save)
        foot = QHBoxLayout()
        self.stamp = QLabel()
        self.stamp.setStyleSheet("color: #8a939d;")
        foot.addWidget(self.stamp, 1)
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        foot.addWidget(self.save_btn)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        foot.addWidget(close)
        lay.addLayout(foot)
        self._load()

    # -- the language ---------------------------------------------------------------------
    def _load(self) -> None:
        base = folder(self.topic)
        doc = self.edit.document()
        doc.setBaseUrl(QUrl.fromLocalFile(str(base) + "/"))
        self.edit.blockSignals(True)
        doc.setMarkdown(readable(text(self.topic, self.lang)))
        fit_images(doc, base, 640)
        self.edit.blockSignals(False)
        self.title.setText(title(self.topic, self.lang))
        # the standard heading in THIS language, as the reader would see it
        from . import i18n
        ui = i18n.current()
        try:
            i18n.start(self.lang)
            std = tr("Tips and experience")
        finally:
            i18n.start(ui)
        self.title.setPlaceholderText(f"{std}  (standard — type your own)")
        self.dirty = False
        self.stamp.setText(stamp(self.topic, self.lang)
                           or "Not written yet")
        if stale(self.topic, self.lang):
            self.warn.setText("Out of date: the Portuguese was changed after "
                              "this translation")
            self.warn.show()
        else:
            self.warn.hide()

    def _lang_changed(self, _i: int) -> None:
        code = self.langs.currentData()
        if code == self.lang:
            return
        if self.dirty and not self._save():
            self.langs.blockSignals(True)
            self.langs.setCurrentIndex(LANGS.index(self.lang))
            self.langs.blockSignals(False)
            return
        self.lang = code
        self._load()

    def _changed(self, *_a) -> None:
        self.dirty = True

    # -- formatting ---------------------------------------------------------------------------
    def _merge(self, fmt: QTextCharFormat) -> None:
        cur = self.edit.textCursor()
        if not cur.hasSelection():
            cur.select(QTextCursor.WordUnderCursor)
        cur.mergeCharFormat(fmt)
        self.edit.mergeCurrentCharFormat(fmt)

    def _bold(self) -> None:
        f = QTextCharFormat()
        on = self.edit.fontWeight() > QFont.Normal
        f.setFontWeight(QFont.Normal if on else QFont.Bold)
        self._merge(f)

    def _italic(self) -> None:
        f = QTextCharFormat()
        f.setFontItalic(not self.edit.fontItalic())
        self._merge(f)

    def _heading(self) -> None:
        cur = self.edit.textCursor()
        b = QTextBlockFormat(cur.blockFormat())
        now = b.headingLevel()
        b.setHeadingLevel(0 if now else 3)
        cur.setBlockFormat(b)
        sel = QTextCursor(cur)
        sel.select(QTextCursor.BlockUnderCursor)
        f = QTextCharFormat()
        f.setFontWeight(QFont.Normal if now else QFont.Bold)
        f.setProperty(QTextCharFormat.FontSizeAdjustment, 0 if now else 1)
        sel.mergeCharFormat(f)
        self.edit.mergeCurrentCharFormat(f)     # what is typed next, too
        self.dirty = True

    def _list(self) -> None:
        cur = self.edit.textCursor()
        lst = cur.currentList()
        if lst is not None:
            lst.remove(cur.block())
            b = QTextBlockFormat(cur.blockFormat())
            b.setIndent(0)
            cur.setBlockFormat(b)
        else:
            cur.createList(QTextListFormat.ListDisc)
        self.dirty = True

    def _pick(self) -> None:
        path, _f = QFileDialog.getOpenFileName(
            self, "A picture", "",
            "Pictures (*.png *.jpg *.jpeg *.bmp *.webp *.gif)")
        if path:
            self.edit.put_image(QImage(path))

    # -- storing --------------------------------------------------------------------------------
    def _save(self) -> bool:
        md = self.edit.document().toMarkdown()
        try:
            save(self.topic, self.lang, md, self.title.text())
        except OSError as e:
            self.warn.setText(f"Not saved: {e}")
            self.warn.show()
            return False
        self.dirty = False
        self.stamp.setText(stamp(self.topic, self.lang))
        if self.lang == SOURCE and any(stale(self.topic, c) for c in LANGS):
            self.warn.setText("Saved — the translations are now out of date")
            self.warn.show()
        if self.on_saved is not None:
            self.on_saved(self.topic)
        return True

    def closeEvent(self, event) -> None:
        if self.dirty:
            self._save()
        super().closeEvent(event)
