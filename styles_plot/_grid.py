"""Layout pieces shared by the blocks: words placed on levels without overlap, tick choice, and the bottom of an x
axis (tick labels, unit title, cue)."""

from __future__ import annotations

import math

from matplotlib.ticker import MaxNLocator

from styles_plot._render import Canvas, Ctx
from styles_plot._text import line_h

STRIP_GAP = 0.12  # inches between two words on one level


def place_on_levels(items, width: float) -> tuple[list, int]:
    """Place items (x_centre, w, payload) on levels so no two overlap, clamped inside [0, width].
    Returns ([(x_left, level, payload)], number of levels)."""
    placed: list[tuple[float, float, int]] = []
    out = []
    for xc, w, payload in sorted(items, key=lambda it: it[0]):
        x0 = min(max(xc - w / 2, 0.0), max(width - w, 0.0))
        level = 0
        while any(lv == level and x0 < b + STRIP_GAP and a < x0 + w + STRIP_GAP for a, b, lv in placed):
            level += 1
        placed.append((x0, x0 + w, level))
        out.append((x0, level, payload))
    return out, max((lv for *_ab, lv in placed), default=-1) + 1


def ticks(lim: tuple[float, float], scale: str = "linear", n: int = 4) -> list[float]:
    lo, hi = lim
    if scale == "log":
        return [10.0**e for e in range(math.ceil(math.log10(lo) - 1e-9), math.floor(math.log10(hi) + 1e-9) + 1)]
    return [t for t in MaxNLocator(n).tick_values(lo, hi) if lo - 1e-9 <= t <= hi + 1e-9]


def padded(lo: float, hi: float, scale: str = "linear") -> tuple[float, float]:
    if scale == "log":
        if lo <= 0:
            raise ValueError("a log scale needs positive values")
        return lo / 1.25, hi * 1.25
    span = (hi - lo) or abs(hi) or 1.0
    return lo - 0.05 * span, hi + 0.05 * span


def x_bottom_height(ctx: Ctx, unit, width: float) -> tuple[float, list[str], list[str]]:
    """Height under an x axis, with the wrapped unit title and cue lines."""
    sz = ctx.sizes
    title = ctx.wrap(unit.title, width, sz.axis)
    cue = ctx.wrap(ctx.words.cue.format(unit.quantity), width, sz.cue) if unit.cue else []
    h = line_h(sz.tick) + 0.06 + len(title) * line_h(sz.axis) + len(cue) * line_h(sz.cue) + 0.12
    return h, title, cue


def draw_x_bottom(cv: Canvas, ctx: Ctx, x0: float, w: float, y: float, xlim, xticks, unit, title, cue, pid) -> None:
    sz, muted = ctx.sizes, ctx.chrome("muted")
    lo, hi = xlim
    for tv in xticks:
        cv.text(x0 + (tv - lo) / (hi - lo) * w, y + 0.06 + line_h(sz.tick) / 2, ctx.tick(tv), kind="tick_label",
                size=sz.tick, color=muted, ha="center", panel=pid)  # fmt: skip
    y += line_h(sz.tick) + 0.06
    for i, s in enumerate(title):
        cv.text(x0 + w / 2, y + (i + 0.5) * line_h(sz.axis), s, kind="axis_title", size=sz.axis, color=muted,
                ha="center", panel=pid, unit=unit.name, full=unit.title)  # fmt: skip
    y += len(title) * line_h(sz.axis)
    full = ctx.words.cue.format(unit.quantity)
    for i, s in enumerate(cue):
        cv.text(x0 + w / 2, y + (i + 0.5) * line_h(sz.cue), s, kind="cue", size=sz.cue, color=muted, ha="center",
                panel=pid, axis="x", full=full)  # fmt: skip


def y_tick_width(ctx: Ctx, values) -> float:
    return max((ctx.measure(ctx.tick(v), ctx.sizes.tick)[0] for v in values), default=0.0) + 0.1


def claim_tags(ctx: Ctx, cells) -> list[tuple[tuple[str, ...], str, str]]:
    """[(cells, claim, words)]: one grey tag per distinct wording, naming every cell it covers, in order."""
    groups: dict[str, list] = {}
    for cell in dict.fromkeys(c for c in cells if c):
        st = ctx.status(cell)
        if st.claim == "descriptive":
            words = ctx.words.descriptive
        elif st.claim == "not_claimed":
            words = ctx.words.not_claimed.format(st.claim_reason)
        else:
            continue
        groups.setdefault(words, [st.claim, []])[1].append(cell)
    return [(tuple(cs), claim, words) for words, (claim, cs) in groups.items()]


def draw_tags(cv: Canvas, ctx: Ctx, x: float, y: float, tags_) -> None:
    """Status tags one per line from y (inches from the top) down."""
    sz = ctx.sizes.tag
    for i, (cells, claim, words) in enumerate(tags_):
        cv.text(x, y + (i + 0.5) * line_h(sz), words, kind="status_tag", size=sz, color=ctx.chrome("muted"),
                cells=cells, claim=claim, full=words)  # fmt: skip
