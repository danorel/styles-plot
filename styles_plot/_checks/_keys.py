"""Check 4: the key names everything drawn and nothing else; no legend box.

SP301 an encoding drawn but not named in the key
SP302 an encoding named in the key but not drawn
SP303 a legend box
"""

from __future__ import annotations

from styles_plot._checks._base import CheckCtx, Problem
from styles_plot._tags import tags


def drawn_encodings(cx: CheckCtx) -> set[tuple]:
    enc: set[tuple] = set()
    for a in cx.marks:
        t = tags(a)
        kind = t.get("kind")
        if t.get("hollow"):
            enc.add(("post_hoc",))
        if kind == "whisker":
            enc.add(("whisker", t["interval"]))
        elif kind == "shading":
            enc.add(("shading", t["interval"]))
        elif kind == "tick":
            enc.add(("tick",))
        elif kind == "band":
            enc.add(("band",))
        elif kind == "median":
            enc.add(("median",))
        if t.get("role") == "control" and t.get("control"):
            enc.add(("control", t["control"]))
        if t.get("role") == "control" and t.get("kind") == "swatch":
            enc |= {("control", c) for c in t.get("controls", ())}
    return enc


def named_encodings(cx: CheckCtx) -> set[tuple]:
    enc: set[tuple] = set()
    for t_ in cx.texts:
        t = tags(t_)
        if t.get("kind") != "key":
            continue
        e = tuple(t["encoding"])
        if e == ("control",):
            enc |= {("control", c) for c in t.get("controls", ())}
        else:
            enc.add(e)
    return enc


def check(cx: CheckCtx) -> list[Problem]:
    drawn, named = drawn_encodings(cx), named_encodings(cx)
    out = [cx.problem("SP301", f"{_say(e)} is drawn but the key does not name it") for e in sorted(drawn - named)]
    out += [cx.problem("SP302", f"the key names {_say(e)} but it is not drawn") for e in sorted(named - drawn)]
    for ax in cx.fig.axes:
        if ax.get_legend() is not None:
            out.append(cx.problem("SP303", "a legend box (name encodings with words and the key line instead)"))
    for sub in [cx.fig, *cx.fig.subfigs]:
        if getattr(sub, "legends", None):
            out.append(cx.problem("SP303", "a figure legend box"))
    return out


def _say(e: tuple) -> str:
    return {"post_hoc": "a hollow (post hoc) mark", "tick": "a grey tick", "band": "the grey band",
            "median": "a median line"}.get(e[0]) or f"{e[0]} ({e[1]})"  # fmt: skip
