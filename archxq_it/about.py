"""«About ArchXQ IT» — what opens from the hub's globe (his idea,
2026-10-04; before, the globe went straight to the site). A small popup
under the button: the edition and the version (the build writes it —
the first thing to ask when someone writes in), a line on what it is,
and the links: the site, Get Pro (Lite) or the updates (Pro), the source
(Lite), the manual, the videos, and where to report a problem. Closes on
any click outside it or on Esc; it never blocks the work behind it.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout

from . import edition
from .style import BLUE

SITE = "https://www.xq.com.br/archxq-it"
SUPPORT = "https://www.xq.com.br/support"
GITHUB = "https://github.com/equipexq/archxq-it-lite"
UPDATES = "https://app.gumroad.com/library"      # the buyer's Gumroad library
VIDEOS = "https://www.youtube.com/@landosouzza"


def _version() -> str:
    from . import __version__
    if "prototype" in __version__:           # the source, not a build
        return "dev"
    return __version__.removesuffix("-lite").removesuffix("-pro")


def _links() -> list[tuple[str, str, str]]:
    """(label, target, note) — target «guide» = the in-app manual."""
    out = [("Website", SITE, "xq.com.br/archxq-it")]
    if edition.lite():
        out.append(("Get Pro", edition.PRO_URL,
                    "beams, slabs, openings, roof, sheets, PDF / DXF"))
        out.append(("Source code", GITHUB, "GitHub — free, GPL-3.0"))
    else:
        out.append(("Updates", UPDATES, "your Gumroad library"))
    # the support form arrives with the product and the version filled in
    # (the site's inbox shows which product a request is about)
    from urllib.parse import quote
    ed = "Lite" if edition.lite() else "Pro"
    support = f"{SUPPORT}?product=archxq-it&version={quote(ed + ' ' + _version())}"
    out += [("Manual", "guide", "the Help of every tool"),
            ("Videos", VIDEOS, "tutorials on YouTube"),
            ("Report a problem", support, "xq.com.br/support")]
    return out


class _About(QFrame):
    def __init__(self, owner, parent=None) -> None:
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.owner = owner
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setObjectName("axq_about")
        self.setStyleSheet(
            "QFrame#axq_about { background: #1d2025; border: 1px solid "
            f"{BLUE}; border-radius: 8px; }}"
            "QLabel { color: #d6d9dd; background: transparent; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(6)
        name = "Lite" if edition.lite() else "Pro"
        head = QLabel(
            "<span style='font-size:18px; font-weight:bold; color:white'>"
            "Arch<span style='color:#8FA6FF'>XQ</span> "
            "<span style='color:#FF6B1A'>IT</span></span>"
            f"&nbsp;&nbsp;<span style='color:#22D3EE'>{name} "
            f"{_version()}</span>")
        head.setTextFormat(Qt.RichText)
        lay.addWidget(head)
        what = QLabel("Architecture for IngeTrazo — from the plot to the "
                      "printed sheets.")
        what.setWordWrap(True)
        what.setFixedWidth(330)
        lay.addWidget(what)
        # one label per cell: a rich-text table in one label was measured
        # short — its last row ran under the footer
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(7)
        for r, (label, t, note) in enumerate(_links()):
            a = QLabel(f"<a href='{t}' style='color:#8fd3ff; "
                       f"text-decoration:none'><b>{label}</b></a>")
            a.setTextFormat(Qt.RichText)
            a.setTextInteractionFlags(Qt.TextBrowserInteraction)
            a.linkActivated.connect(self._go)
            n = QLabel(note)
            n.setStyleSheet("color: #9aa5b1;")
            grid.addWidget(a, r, 0)
            grid.addWidget(n, r, 1)
        lay.addSpacing(4)
        lay.addLayout(grid)
        foot = QLabel("© Orlando Souza · XQ  ·  GPL-3.0-or-later")
        foot.setStyleSheet("color: #6b7480; font-size: 11px;")
        lay.addSpacing(6)
        lay.addWidget(foot)

    def _go(self, target: str) -> None:
        self.close()
        if target == "guide":
            from .guide import open_guide
            open_guide(getattr(self.owner, "element", None) or "plot",
                       self.owner.viewport.window())
        else:
            QDesktopServices.openUrl(QUrl(target))


def show_about(owner, anchor) -> None:
    pop = _About(owner, anchor)
    pop.adjustSize()
    pos = anchor.mapToGlobal(QPoint(0, anchor.height() + 4))
    screen = anchor.screen().availableGeometry()
    x = min(pos.x(), screen.right() - pop.width() - 8)
    pop.move(max(screen.left() + 8, x), pos.y())
    pop.show()
