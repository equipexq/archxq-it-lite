"""SILENT PAINT FAILURES, kept (his call, 2026-10-26: «take great care not
to go backwards»). The plan's drawings (dimensions, rooms' tint, ghost…)
swallow any error so the host's paint never breaks — and so a broken one
just did not draw: a method defined twice hid the plan's dimensions and
rooms for half an hour, unseen. Each ``except`` there now calls
``failed()``: the error is still swallowed, but recorded here — read by
``tools/smoke_live.py`` after each restart, printed once per place.
"""
from __future__ import annotations

import sys
import time
import traceback

#: "module.function" → {"n": times, "first": its traceback, "last": the
#: last error's text, "t": when last}
ERRORS: dict = {}


def failed() -> None:
    """Called from inside an ``except`` that keeps the paint alive."""
    f = sys._getframe(1)
    where = f"{f.f_globals.get('__name__', '?').rsplit('.', 1)[-1]}." \
            f"{f.f_code.co_name}"
    e = sys.exc_info()[1]
    rec = ERRORS.get(where)
    if rec is None:
        rec = ERRORS[where] = {"n": 0, "first": traceback.format_exc(),
                               "last": "", "t": 0.0}
        print(f"[ArchXQ] a drawing failed silently in {where}: {e!r}",
              file=sys.stderr)
        try:                      # and once into archxq_errors.log, so a
            from . import compat  # customer's report carries it too
            compat.log_error(f"paint: {where}")
        except Exception:  # noqa: BLE001 — the alarm itself never breaks
            pass
    rec["n"] += 1
    rec["last"] = repr(e)
    rec["t"] = time.time()


def clear() -> None:
    ERRORS.clear()


def report() -> str:
    if not ERRORS:
        return "no silent paint failure"
    return "\n".join(f"{k}: {v['n']}× — {v['last']}\n{v['first']}"
                     for k, v in ERRORS.items())
