"""Check 4: the key names everything drawn and nothing else; no legend box.

SP301 an encoding drawn but not named in the key
SP302 an encoding named in the key but not drawn
SP303 a legend box
SP304 a grey (control) data mark that does not say which control it is
SP305 two grey bands with different meanings in one figure (a reader cannot tell them apart)
"""

from __future__ import annotations

from styles_plot._checks._base import CheckCtx, Problem
from styles_plot._tags import tags


def drawn_encodings(cx: CheckCtx) -> set[tuple]:
    enc: set[tuple] = {("all_post_hoc",)} if cx.info.all_post_hoc else set()
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
            enc.add(("band", t.get("band", "")))
        elif kind == "median" or (kind == "line" and t.get("median")):
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
    from styles_plot._tags import DATA_KINDS

    drawn, named = drawn_encodings(cx), named_encodings(cx)
    unnamed = {tags(a)["kind"] for a in cx.marks if tags(a).get("kind") in DATA_KINDS
               and tags(a).get("role") == "control" and not tags(a).get("control")}  # fmt: skip
    out = [cx.problem("SP301", f"{_say(e)} is drawn but the key does not name it") for e in sorted(drawn - named)]
    out += [cx.problem("SP302", f"the key names {_say(e)} but it is not drawn") for e in sorted(named - drawn)]
    bands = sorted(e[1] for e in drawn if e[0] == "band")
    if len(bands) > 1:
        out.append(cx.problem("SP305", f"grey bands of {len(bands)} meanings in one figure: {bands}; split the figure"))
    out += [cx.problem("SP304", f"a grey {k} without its control's name: the key cannot say 'grey: …'")
            for k in sorted(unnamed)]  # fmt: skip
    for ax in cx.fig.axes:
        if ax.get_legend() is not None:
            out.append(cx.problem("SP303", "a legend box (name encodings with words and the key line instead)"))
    for sub in [cx.fig, *cx.fig.subfigs]:
        if getattr(sub, "legends", None):
            out.append(cx.problem("SP303", "a figure legend box"))
    return out


def _say(e: tuple) -> str:
    return {"post_hoc": "a hollow (post hoc) mark", "tick": "a grey tick", "median": "a median line"}.get(e[0]) or (
        f"the grey band {e[1]!r}" if e[0] == "band" and e[1] else "the grey band" if e[0] == "band" else f"{e[0]} ({e[1]})")
