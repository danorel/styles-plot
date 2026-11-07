"""Checks 5 and 6: every word comes from the vocabulary; cues point one way.

SP401 a text that is not a vocabulary term, a template, a number, an entity name, a role word or a library phrase
SP402 a banned variant
SP403 something that looks like a run id or a UTC stamp
SP404 a cue that does not read "→ more <quantity>" (or "→ larger …"; "↑ …" beside a sweep's value axis)
SP405 a left arrow anywhere
SP406 a panel whose unit has a direction but no cue
SP407 a panel without its axis title
"""

from __future__ import annotations

import re

from styles_plot._checks._base import CheckCtx, Problem, full_text, library_phrases
from styles_plot._numbers import NUM
from styles_plot._tags import tags

_NUMBERISH = re.compile(rf"(?:{NUM}|\[{NUM}, {NUM}\]|{NUM} of {NUM})")
_UTC = re.compile(r"\b\d{8}T\d{4,6}Z?\b")
_SNAKE_ID = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_PROSE = {"title", "caption"}  # free prose: only banned words and ids are checked
_FREE = {"tick_label"}  # library-made numbers


def _control_phrase(cx: CheckCtx, s: str) -> bool:
    prefix, suffix = cx.vocab.words.control.split("{}")
    if not (s.startswith(prefix) and s.endswith(suffix)):
        return False
    names = s[len(prefix) : len(s) - len(suffix) if suffix else None].split(" · ")
    return all(n in cx.vocab.controls for n in names)


def _embedding_title(cx: CheckCtx, s: str) -> bool:
    m = re.fullmatch(r"(.+) ([12])", s)
    return bool(m) and m.group(1) in cx.vocab.canonical


def check(cx: CheckCtx) -> list[Problem]:
    v = cx.vocab
    allowed = v.allowed_phrases | library_phrases(v)
    out: list[Problem] = []
    seen: set[str] = set()
    for t_ in cx.texts:
        t = tags(t_)
        kind = t.get("kind")
        s = full_text(t_).strip()
        if s in seen and kind not in _PROSE:
            continue
        seen.add(s)
        if "←" in s:
            out.append(cx.problem("SP405", f"a left arrow in {s[:40]!r}"))
        if _UTC.search(s) or any("_" in m and re.search(r"\d", m) for m in _SNAKE_ID.findall(s)):
            out.append(cx.problem("SP403", f"looks like a run id or a timestamp: {s[:40]!r}"))
        if not t.get("verbatim"):
            for hit in v.banned_hits(s):
                out.append(cx.problem("SP402", f"banned {hit} in {s[:40]!r}"))
        if kind in _PROSE or kind in _FREE or t.get("verbatim"):
            continue
        ok = (
            s in allowed
            or _NUMBERISH.fullmatch(s)
            or v.template_re.fullmatch(s)
            or (kind == "key" and _control_phrase(cx, s))
            or (kind == "axis_title" and _embedding_title(cx, s))
        )
        if not ok:
            out.append(cx.problem("SP401", f"{kind or 'text'} {s[:50]!r} is not in the vocabulary"))
    out += _cues(cx)
    return out


def _cue_re(template: str, words: tuple[str, ...]) -> re.Pattern:
    rx = re.escape(template).replace(re.escape("{word}"), f"(?:{'|'.join(map(re.escape, words))})")
    return re.compile(rx.replace(re.escape("{quantity}"), r"\S.*"))


def _cues(cx: CheckCtx) -> list[Problem]:
    w = cx.vocab.words
    patterns = {"x": _cue_re(w.cue, w.cue_words), "y": _cue_re(w.cue_y, w.cue_words)}
    out: list[Problem] = []
    cues: dict[int, str] = {}
    titles: set[int] = set()
    for t_ in cx.texts:
        t = tags(t_)
        if t.get("kind") == "cue":
            s = full_text(t_)
            axis = "y" if t.get("axis") == "y" else "x"
            if not patterns[axis].fullmatch(s):
                template = w.cue_y if axis == "y" else w.cue
                out.append(cx.problem("SP404", f"cue {s!r} does not read {template!r} ({' or '.join(w.cue_words)})"))
            if "panel" in t:
                cues[t["panel"]] = s
        elif t.get("kind") == "axis_title" and "panel" in t:
            titles.add(t["panel"])
    for ax in cx.fig.axes:
        p = tags(ax)
        if p.get("kind") != "panel":
            continue
        if p.get("cue") and p["pid"] not in cues:
            out.append(cx.problem("SP406", f"panel {p['pid'] + 1} ({p['unit']}) has no direction cue"))
        if p["pid"] not in titles:
            out.append(cx.problem("SP407", f"panel {p['pid'] + 1} ({p['unit']}) has no axis title"))
    return out
