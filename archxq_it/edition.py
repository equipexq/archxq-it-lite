"""Which ArchXQ IT this is: «pro» (the source) or «lite».

The Lite is MADE from this same source by ``ArchXQ_IT_Lite\\build_lite.ps1``,
which writes ``EDITION = "lite"`` here and leaves the Pro-only modules out
(docs, docsdxf, doctools, importdxf, demo). Never edit the Lite by hand.

What the Lite leaves to the Pro is listed in ``phases.PRO_ELEMENTS``; the
Lite still SHOWS (and keeps) every Pro element of a file made with the Pro.
"""
EDITION = "lite"
PRO_URL = "https://www.xq.com.br/archxq-it"


def lite() -> bool:
    return EDITION == "lite"
