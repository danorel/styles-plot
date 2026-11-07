"""Checks 1 and 2: colour by role, one meaning per colour.

SP101 a tagged artist drawn in a colour other than its role's slot
SP102 a colour that is neither a palette slot nor chrome
SP103 an untagged artist in a role, control or stack-remainder colour
SP104 a role drawn but not named by a word in its colour, or a word in a role colour with no mark of that role
"""

from __future__ import annotations

from styles_plot._checks._base import CheckCtx, Problem, colours
from styles_plot._tags import DATA_KINDS, tags

# role-tagged artists whose colour is the role's
_ROLE_KINDS = DATA_KINDS | {"whisker", "shading", "tick", "median", "role_word", "value", "key_mark", "schematic_word",
                            "box", "arrow", "swatch"}  # fmt: skip
_NAMING_KINDS = {"role_word", "schematic_word"}


def check(cx: CheckCtx) -> list[Problem]:
    pal, v = cx.vocab.palette, cx.vocab
    bg = pal.chrome["background"]
    slot_role = {r.hex: r.name for r in v.roles.values()}
    slot_role[pal.control] = "control"
    slot_role[pal.other] = "other"
    chrome = pal.chrome_colours()
    known = chrome | set(pal.slots.values())
    out: list[Problem] = []
    drawn_roles: set[str] = set()
    named_roles: set[str] = set()
    for a in [*cx.marks, *cx.texts]:
        t = tags(a)
        cols = colours(a)
        role = t.get("role")
        if role is not None and t.get("kind") in _ROLE_KINDS:
            want = pal.control if role == "control" else pal.other if role == "other" else v.roles[role].hex
            ok = {want, bg} if t.get("kind") in DATA_KINDS | {"swatch"} else {want}
            if t.get("kind") == "value" and role == "control":
                ok = {pal.chrome["muted"]}
            for c in cols - ok:
                out.append(cx.problem("SP101", f"a {t['kind']} of role {role!r} is drawn in {c}, not {want}"))
            if t.get("kind") in DATA_KINDS and role not in ("control", "other"):
                drawn_roles.add(role)
            if t.get("kind") in _NAMING_KINDS and role not in ("control", "other"):
                named_roles.add(role)
            continue
        for c in cols:
            if c in slot_role and c not in chrome:
                what = t.get("kind", "untagged artist")
                out.append(cx.problem("SP103", f"a {what} without a role is drawn in the {slot_role[c]!r} colour {c}"))
            elif c not in known:
                out.append(cx.problem("SP102", f"colour {c} is not in the palette ({_describe(a)})"))
    for r in sorted(drawn_roles - named_roles):
        out.append(cx.problem("SP104", f"the {r!r} colour is drawn but no word in it names it"))
    for r in sorted(named_roles - drawn_roles):
        if not cx.info.direct_labels:
            out.append(cx.problem("SP104", f"a word names the {r!r} colour but nothing of that role is drawn"))
    return out


def _describe(a) -> str:
    t = tags(a)
    if t:
        return t.get("kind", "?")
    txt = getattr(a, "get_text", None)
    return f"text {txt()[:30]!r}" if txt else type(a).__name__
