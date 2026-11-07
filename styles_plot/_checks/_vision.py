"""Check 9: colour vision. Under simulated deuteranopia, protanopia, tritanopia and normal vision, two role colours
in one figure differ by at least the palette's role floor (CIEDE2000), and a role colour and control grey by at least
the control floor.

A figure made only of schematics may set direct_labels=True instead: it is exempt from the floors, and every coloured
element must then have a word in its colour right next to it.

SP700 a distance that cannot be computed (a custom hex without the [check] extra)
SP701 two role colours under the role floor
SP702 a role colour and control grey under the control floor
SP703 a coloured schematic element without its word next to it
SP704 direct_labels on a figure that is not all schematics
"""

from __future__ import annotations

from styles_plot._checks._base import CheckCtx, Problem
from styles_plot._tags import tags

NEXT_TO = 0.15  # inches between an element and its word, at most

_SCHEMATIC_MARKS = {"box", "arrow", "swatch"}


def check(cx: CheckCtx) -> list[Problem]:
    if cx.info.direct_labels:
        return _direct_labels(cx)
    pal, v = cx.vocab.palette, cx.vocab
    slots: set[str] = set()
    for a in [*cx.marks, *cx.texts]:
        role = tags(a).get("role")
        if role == "control":
            slots.add("control")
        elif role in v.roles:
            slots.add(v.roles[role].slot)
    names = sorted(slots)
    out: list[Problem] = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            d = pal.distances(a, b)
            if d is None:
                out.append(cx.problem("SP700", f"cannot compute colour vision for {a}/{b}: install styles-plot[check]"))
                continue
            vision, worst = min(d.items(), key=lambda kv: kv[1])
            floor = pal.floor(a, b)
            if worst < floor:
                code = "SP702" if "control" in (a, b) else "SP701"
                out.append(cx.problem(code, f"{_who(v, a)} and {_who(v, b)} are {worst:.1f} apart under {vision} "
                                            f"(floor {floor:g}): they may not share a figure"))  # fmt: skip
    return out


def _who(v, slot: str) -> str:
    if slot == "control":
        return "control grey"
    role = next((r.name for r in v.roles.values() if r.slot == slot), slot)
    return f"{role!r} ({slot})"


def _direct_labels(cx: CheckCtx) -> list[Problem]:
    out: list[Problem] = []
    if any(b != "Schematic" for b in cx.info.blocks):
        out.append(cx.problem("SP704", "direct_labels is for figures made only of schematics"))
    px = cx.fig.dpi
    words = [(tags(t).get("role"), t.get_window_extent(cx.renderer)) for t in cx.texts if tags(t).get("role")]
    for a in cx.marks:
        t = tags(a)
        if t.get("kind") not in _SCHEMATIC_MARKS or not t.get("role") or t["role"] == "control":
            continue
        bb = a.get_window_extent(cx.renderer)
        near = [w for r, w in words if r == t["role"] and _gap(bb, w) <= NEXT_TO * px]
        if not near:
            out.append(cx.problem("SP703", f"a {t['kind']} in the {t['role']!r} colour has no {t['role']!r} word "
                                           f"within {NEXT_TO:g} in"))  # fmt: skip
    return out


def _gap(a, b) -> float:
    dx = max(b.x0 - a.x1, a.x0 - b.x1, 0)
    dy = max(b.y0 - a.y1, a.y0 - b.y1, 0)
    return (dx**2 + dy**2) ** 0.5
