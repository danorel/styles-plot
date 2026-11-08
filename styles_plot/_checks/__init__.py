"""The checks. Each family reads a rendered figure's tagged artists and returns problems; `run` runs them all.

Codes are stable across releases; a new check that can fail an old figure is a major version.
SP1xx colour by role · SP2xx status · SP3xx key · SP4xx words and cues · SP5xx numbers · SP6xx layout ·
SP7xx colour vision · SP8xx saved PNG · SP9xx check. SP612 (a table of numbers only) is reported by the table while
laid out.

A figure's waivers (`sp.Waive`, text placement only) remove the layout problems they match; a waiver that matches
nothing on a target it applies to is SP905 (stale), an error from the start.
"""

from __future__ import annotations

from styles_plot._checks import _colour, _keys, _layout, _numbers, _status, _vision, _words
from styles_plot._checks._base import CheckCtx, Problem

_FAMILIES = (_colour.check, _status.check, _keys.check, _words.check, _numbers.check, _layout.check, _vision.check)


def run(fig) -> list[Problem]:
    """Every check on a figure rendered by styles-plot, duplicates dropped, in family order; waived ones removed."""
    return evaluate(fig)[0]


def evaluate(fig) -> tuple[list[Problem], list[dict]]:
    """(the problems, the waived ones as {code, subject, reason}). Stale waivers are SP905 problems; on a target that
    does not check layout (notebook) no waiver can match, so none is stale."""
    cx = CheckCtx.of(fig)
    problems = _all(cx)
    waivers = cx.info.waivers
    if not waivers:
        return problems, []
    kept, waived, used = [], [], set()
    for p in problems:
        w = next((w for w in waivers if _matches(w, p)), None)
        if w is None:
            kept.append(p)
        else:
            used.add(w)
            waived.append({"code": p.code, "subject": p.subject, "reason": w.reason})
    if cx.theme.strict_layout:
        for w in waivers:
            if w not in used:
                kept.append(cx.problem("SP905", f"stale waiver: {w.code} {w.text!r} matches nothing on the "
                                                f"{cx.info.target!r} target", subject=w.text,
                                       fix="remove the waiver, or limit it to the targets that need it: "
                                           "sp.Waive(..., targets=(...))"))  # fmt: skip
    return kept, waived


def _matches(w, p: Problem) -> bool:
    if w.code != p.code:
        return False
    return w.text == p.subject or w.text == (p.where or {}).get("other")


def _all(cx: CheckCtx) -> list[Problem]:
    out: list[Problem] = [cx.problem(code, message) for code, message in cx.info.findings]
    seen: set[tuple[str, str]] = {(p.code, p.message) for p in out}
    for family in _FAMILIES:
        for p in family(cx):
            if (p.code, p.message) not in seen:
                seen.add((p.code, p.message))
                out.append(p)
    return out
