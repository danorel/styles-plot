"""The checks. Each family reads a rendered figure's tagged artists and returns problems; `run` runs them all.

Codes are stable across releases; a new check that can fail an old figure is a major version.
SP1xx colour by role · SP2xx status · SP3xx key · SP4xx words and cues · SP5xx numbers · SP6xx layout ·
SP7xx colour vision · SP8xx saved PNG.
"""

from __future__ import annotations

from styles_plot._checks import _colour, _keys, _layout, _numbers, _status, _vision, _words
from styles_plot._checks._base import CheckCtx, Problem

_FAMILIES = (_colour.check, _status.check, _keys.check, _words.check, _numbers.check, _layout.check, _vision.check)


def run(fig) -> list[Problem]:
    """Every check on a figure rendered by styles-plot, duplicates dropped, in family order."""
    cx = CheckCtx.of(fig)
    out: list[Problem] = []
    seen: set[tuple[str, str]] = set()
    for family in _FAMILIES:
        for p in family(cx):
            if (p.code, p.message) not in seen:
                seen.add((p.code, p.message))
                out.append(p)
    return out
