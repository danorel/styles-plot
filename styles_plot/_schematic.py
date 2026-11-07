"""Schematics: boxes, arrows, coloured words and single marks, positioned in inches from the block's top-left corner.

Words are vocabulary terms unless marked verbatim (prompt text). A schematic-only figure may set direct_labels=True:
it is then exempt from the colour-vision floors, and every coloured element needs a word in its colour beside it.
"""

from __future__ import annotations

from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Rectangle

from styles_plot._model import Arrow, Box, Mark, Schematic, Words
from styles_plot._render import BuildError, Canvas, Ctx, Plan
from styles_plot._tags import tag


def plan(s: Schematic, ctx: Ctx, width: float, label_w: float) -> Plan:
    enc: set = set()
    for e in s.elements:
        role = getattr(e, "role", None)
        if role is not None:
            ctx.role_hex(role)
        if isinstance(e, Words):
            for _text, r in e.parts:
                if r is not None:
                    ctx.role_hex(r)
        if isinstance(e, Mark):
            if e.hollow:
                enc.add(("post_hoc",))
            if e.interval is not None:
                enc.add(("whisker", "ci95"))
        if isinstance(e, Box) and (e.x + e.w > width + 1e-9 or e.y + e.h > s.height + 1e-9):
            raise BuildError(f"{ctx.figure_id}: a box runs outside the schematic ({width} x {s.height} in)")
    return Plan(s.height, enc, lambda cv: _draw(cv, ctx, s))


def _draw(cv: Canvas, ctx: Ctx, s: Schematic) -> None:
    for e in s.elements:
        if isinstance(e, Box):
            box(cv, ctx, e)
        elif isinstance(e, Arrow):
            arrow(cv, ctx, e)
        elif isinstance(e, Words):
            words(cv, ctx, e)
        elif isinstance(e, Mark):
            mark(cv, ctx, e)
        else:
            raise BuildError(f"not a schematic element: {type(e).__name__}")


def box(cv: Canvas, ctx: Ctx, e: Box) -> None:
    col = ctx.role_hex(e.role) if e.role else ctx.chrome("faint")
    r = Rectangle((cv.fx(e.x), cv.fy(e.y + e.h)), e.w / cv.w, e.h / cv.h, transform=cv.sub.transSubfigure,
                  facecolor="none", edgecolor=col, lw=1.6, zorder=2)  # fmt: skip
    cv.sub.add_artist(r)
    tag(r, kind="box", **({"role": e.role} if e.role else {}))
    if e.text:
        meta = {"role": e.role} if e.role else {}
        cv.text(e.x + e.w / 2, e.y + e.h / 2, e.text, kind="schematic_word", size=ctx.sizes.value,
                color=ctx.role_hex(e.role) if e.role else ctx.chrome("text"), ha="center", verbatim=e.verbatim, **meta)  # fmt: skip


def arrow(cv: Canvas, ctx: Ctx, e: Arrow) -> None:
    col = ctx.role_hex(e.role) if e.role else ctx.chrome("rule")
    a = FancyArrowPatch((cv.fx(e.start[0]), cv.fy(e.start[1])), (cv.fx(e.end[0]), cv.fy(e.end[1])),
                        transform=cv.sub.transSubfigure, arrowstyle="-|>", mutation_scale=12, color=col, lw=1.4,
                        shrinkA=0, shrinkB=0)  # fmt: skip
    cv.sub.add_artist(a)
    tag(a, kind="arrow", **({"role": e.role} if e.role else {}))


def words(cv: Canvas, ctx: Ctx, e: Words) -> None:
    weight = "bold" if e.bold else "normal"
    size = ctx.sizes.role_word if e.bold else ctx.sizes.value
    parts = []
    for text, role in e.parts:
        col = ctx.role_hex(role) if role else ctx.chrome("text")
        meta = {"kind": "schematic_word", "verbatim": e.verbatim, **({"role": role} if role else {})}
        parts.append((text, col, weight, meta))
    cv.rich(e.x, e.y, parts, size=size)


def mark(cv: Canvas, ctx: Ctx, e: Mark) -> None:
    mk, bg = ctx.marks, ctx.palette.chrome["background"]
    col = ctx.role_hex(e.role)
    x, y = cv.fx(e.x), cv.fy(e.y)
    if e.interval is not None:
        lo, hi = e.interval
        ln = Line2D([cv.fx(e.x - lo), cv.fx(e.x + hi)], [y, y], transform=cv.sub.transSubfigure, color=col,
                    lw=mk.whisker_lw, solid_capstyle="butt", zorder=3)  # fmt: skip
        cv.sub.add_artist(ln)
        tag(ln, kind="whisker", interval="ci95", role=e.role)
    dot = Line2D([x], [y], transform=cv.sub.transSubfigure, marker=mk.marker, ls="none", ms=mk.dot_size, color=col,
                 mfc=bg if e.hollow else col, mec=col, mew=mk.hollow_edge if e.hollow else 0, zorder=4)  # fmt: skip
    cv.sub.add_artist(dot)
    tag(dot, kind="swatch", role=e.role, hollow=e.hollow)

