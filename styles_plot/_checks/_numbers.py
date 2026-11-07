"""Check 7: numbers are printed by their unit's formatter, and one data key prints one string.

SP501 a number on the figure that no formatter printed (typed by hand), or a printed value without a data key
SP502 one data key printed as two different strings (within a figure; across figures, `styles-plot check`)
"""

from __future__ import annotations

import re
from collections import defaultdict

from styles_plot._checks._base import CheckCtx, Problem, full_text, library_phrases
from styles_plot._numbers import NUM
from styles_plot._tags import tags

_HAS_NUMBER = re.compile(rf"(?<![\w.]){NUM}(?![\w.])")
_PRINTED = {"value", "tick_label"}  # texts the library formats


def conflicts(numbers) -> dict[str, set[str]]:
    seen: dict[str, set[str]] = defaultdict(set)
    for key, s in numbers:
        seen[key].add(s)
    return {k: v for k, v in seen.items() if len(v) > 1}


def check(cx: CheckCtx) -> list[Problem]:
    out: list[Problem] = []
    v = cx.vocab
    allowed = v.allowed_phrases | library_phrases(v)
    for t_ in cx.texts:
        t = tags(t_)
        kind = t.get("kind")
        s = full_text(t_)
        if kind in _PRINTED:
            if kind == "value" and not t.get("key"):
                out.append(cx.problem("SP501", f"value {s!r} has no data key"))
            continue
        if kind in ("title", "caption", "key") or t.get("verbatim") or s in allowed or v.template_re.fullmatch(s):
            continue
        if _HAS_NUMBER.search(s):
            out.append(cx.problem("SP501", f"{kind or 'text'} {s[:40]!r} prints a number no formatter made"))
    for key, strings in sorted(conflicts(cx.info.numbers).items()):
        out.append(cx.problem("SP502", f"data key {key!r} prints {sorted(strings)}"))
    return out
