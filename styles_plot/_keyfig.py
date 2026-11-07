"""The key figure: a project's whole grammar on one image, built from its vocabulary.

Top: each role's colour with its word and meaning, and the controls' grey. Then the marks, each drawn beside its
phrase: a hollow (post hoc) dot and a dot with its whisker in ink (grey means control), the grey tick, the grey band,
and the missing-cell words. Optionally, one example row from the project's data (a one-row dot table) and that row
read aloud (a sentence matching one of the vocabulary's templates, its numbers printed by the vocabulary).

The marks' phrases are the key, so no key line is repeated under the figure. The roles are listed one per row with
their words beside them, so the figure is exempt from the colour-vision floors.
"""

from __future__ import annotations

from dataclasses import dataclass

from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from styles_plot._model import DotTable
from styles_plot._render import BuildError, Canvas, Ctx, Figure, Plan
from styles_plot._tags import tag
from styles_plot._text import line_h
from styles_plot._vocab import Vocab

ROW = 0.36  # inches per line of the legend
SWATCH_X = 0.3
PHRASE_X = 0.75
TWO_COLUMNS = 6.0  # inches: a legend this wide puts the marks beside the roles


@dataclass(frozen=True)
class KeyLegend:
    """The legend part of the key figure (internal)."""


@dataclass(frozen=True)
class ReadAloud:
    """One sentence under the example row (internal)."""

    text: str
    numbers: tuple = ()  # ((name, value, unit, key), ...): filled into "{name}" in the text, logged by key


def key_figure(vocab: Vocab, target: str = "post", id: str = "key", *, example: DotTable | None = None,
               read_aloud: str = "", numbers: dict | None = None) -> Figure:  # fmt: skip
    """The project's key figure. `example` is a one-row dot table drawn from the project's data (its cells are rows
    of the registry under figure `id`); `read_aloud` reads that row in words, matching a vocabulary template once
    filled. Its numbers are `{name}` fields filled from `numbers` = {name: (value, unit, data key)}: printed in the
    unit's format and logged by key, like every number on a figure."""
    if example is not None and len(example.rows) != 1:
        raise BuildError("the key figure's example is one row")
    if read_aloud and example is None:
        raise BuildError("read_aloud reads the example row; give example= too")
    fig = Figure(id, vocab)
    fig._key_figure = True
    fig.add(KeyLegend())
    if example is not None:
        fig.add(example)
    if read_aloud:
        fig.add(ReadAloud(read_aloud, tuple((k, *v) for k, v in (numbers or {}).items())))
    return fig


def plan_legend(_b: KeyLegend, ctx: Ctx, width: float, label_w: float) -> Plan:
    """Roles and controls in the left column, marks and the missing-cell words in the right one (one column under
    TWO_COLUMNS inches); every phrase wraps inside its column."""
    v, w, sz = ctx.vocab, ctx.words, ctx.sizes
    ink, muted = ctx.chrome("text"), ctx.chrome("muted")
    two = width >= TWO_COLUMNS
    col_w = (width - 0.2) / 2 if two else width - 0.2
    word_w = max((ctx.measure(r.word, sz.role_word, "bold")[0] for r in v.roles.values()), default=0.0)
    meaning_x = SWATCH_X + 0.25 + word_w + 0.25
    marks: list[tuple[str, str, tuple]] = [("hollow", w.post_hoc, ("post_hoc",)),
                                           ("whisker", w.whisker.format(v.intervals["ci95"]), ("whisker", "ci95"))]  # fmt: skip
    if v.key_tick:
        marks.append(("tick", w.tick.format(v.key_tick), ("tick",)))
    if v.key_band:
        marks.append(("band", w.band.format(v.key_band), ("band",)))
    enc = {e for _k, _p, e in marks} | {("control", c) for c in v.controls}

    def rows_of(text: str, x: float, size: float) -> tuple[list[str], float]:
        lines = ctx.wrap(text, max(col_w - x, 1.0), size)
        return lines, max(ROW, len(lines) * line_h(size) + 0.12)

    # each item: (height, draw(cv, x0, y_top))
    left: list = [(ROW, lambda cv, x0, y: cv.text(x0 + 0.1, y + ROW / 2, w.key_roles, kind="header", size=sz.header,
                                                    weight="bold"))]  # fmt: skip
    for r in v.roles.values():
        lines, h = rows_of(r.meaning, meaning_x, sz.value) if r.meaning else ([], ROW)

        def role(cv, x0, y, r=r, lines=lines):
            yc = y + ROW / 2
            _dot(cv, ctx, x0 + SWATCH_X, yc, r.hex, kind="swatch", role=r.name)
            cv.text(x0 + SWATCH_X + 0.2, yc, r.word, kind="role_word", role=r.name, size=sz.role_word, weight="bold",
                    color=r.hex)  # fmt: skip
            for i, line in enumerate(lines):
                cv.text(x0 + meaning_x, yc + i * line_h(sz.value), line, kind="text", size=sz.value, color=ink,
                        full=r.meaning)  # fmt: skip

        left.append((h, role))
    if v.controls:
        phrase = w.control.format(" · ".join(v.controls))
        lines, h = rows_of(phrase, SWATCH_X + 0.2, sz.key)

        def controls(cv, x0, y, lines=lines, phrase=phrase):
            yc = y + ROW / 2
            _dot(cv, ctx, x0 + SWATCH_X, yc, ctx.palette.control, kind="swatch", role="control",
                 controls=tuple(v.controls))  # fmt: skip
            for i, line in enumerate(lines):
                cv.text(x0 + SWATCH_X + 0.2, yc + i * line_h(sz.key), line, kind="key", size=sz.key, color=muted,
                        encoding=("control",), controls=tuple(v.controls), full=phrase)  # fmt: skip

        left.append((h, controls))

    right: list = [(ROW, lambda cv, x0, y: cv.text(x0 + 0.1, y + ROW / 2, w.key_marks, kind="header", size=sz.header,
                                                     weight="bold"))]  # fmt: skip
    for kind, phrase, e in marks:
        lines, h = rows_of(phrase, PHRASE_X, sz.key)

        def mark(cv, x0, y, kind=kind, phrase=phrase, e=e, lines=lines):
            yc = y + ROW / 2
            if kind == "hollow":
                _dot(cv, ctx, x0 + SWATCH_X, yc, ink, kind="swatch", hollow=True)
            elif kind == "whisker":
                _whisker(cv, ctx, x0 + SWATCH_X, yc, ink)
                _dot(cv, ctx, x0 + SWATCH_X, yc, ink, kind="swatch")
            elif kind == "tick":
                _tick(cv, ctx, x0 + SWATCH_X, yc)
            else:
                _band(cv, ctx, x0 + SWATCH_X, yc)
            for i, line in enumerate(lines):
                cv.text(x0 + PHRASE_X, yc + i * line_h(sz.key), line, kind="key", size=sz.key, color=muted,
                        encoding=e, full=phrase)  # fmt: skip

        right.append((h, mark))
    missing = w.key_missing.format(" · ".join(v.missing))
    m_lines, m_h = rows_of(missing, 0.1, sz.tag)
    right.append((m_h, lambda cv, x0, y: [cv.text(x0 + 0.1, y + ROW / 2 + i * line_h(sz.tag), line, kind="text",
                                                  size=sz.tag, color=muted, full=missing)
                                          for i, line in enumerate(m_lines)]))  # fmt: skip

    columns = [(0.0, left), (col_w + 0.2, right)] if two else [(0.0, left + right)]
    height = 0.1 + max(sum(h for h, _f in items) for _x, items in columns) + 0.15

    def draw(cv: Canvas) -> None:
        for x0, items in columns:
            y = 0.1
            for h, f in items:
                f(cv, x0, y)
                y += h

    return Plan(height, enc, draw)


def plan_read_aloud(b: ReadAloud, ctx: Ctx, width: float, label_w: float) -> Plan:
    try:
        text = b.text.format(**{name: ctx.value(unit, value, key) for name, value, unit, key in b.numbers})
    except (KeyError, IndexError) as e:
        raise BuildError(f"{ctx.figure_id}: read_aloud has a field without a number: {e}") from None
    lines = ctx.wrap(text, width - 0.3, ctx.sizes.value)
    height = len(lines) * line_h(ctx.sizes.value) + 0.2

    def draw(cv: Canvas) -> None:
        for i, s in enumerate(lines):
            cv.text(0.12, 0.1 + (i + 0.5) * line_h(ctx.sizes.value), s, kind="read_aloud", size=ctx.sizes.value,
                    full=text)  # fmt: skip

    return Plan(height, set(), draw)


# ---- swatches ----------------------------------------------------------------------------------------------------------
def _add(cv: Canvas, artist, **meta):
    cv.sub.add_artist(artist)
    return tag(artist, **meta)


def _dot(cv: Canvas, ctx: Ctx, x, y, colour, *, kind, hollow=False, **meta):
    mk, bg = ctx.marks, ctx.palette.chrome["background"]
    dot = Line2D([cv.fx(x)], [cv.fy(y)], transform=cv.sub.transSubfigure, marker=mk.marker, ls="none",
                 ms=mk.dot_size, color=colour, mfc=bg if hollow else colour, mec=colour,
                 mew=mk.hollow_edge if hollow else 0, zorder=4)  # fmt: skip
    _add(cv, dot, kind=kind, hollow=hollow, **meta)


def _whisker(cv: Canvas, ctx: Ctx, x, y, colour):
    ln = Line2D([cv.fx(x - 0.18), cv.fx(x + 0.18)], [cv.fy(y), cv.fy(y)], transform=cv.sub.transSubfigure,
                color=colour, lw=ctx.marks.whisker_lw, solid_capstyle="butt", zorder=3)  # fmt: skip
    _add(cv, ln, kind="whisker", interval="ci95")


def _tick(cv: Canvas, ctx: Ctx, x, y):
    half = ctx.marks.tick_half * ctx.theme.row_h
    ln = Line2D([cv.fx(x), cv.fx(x)], [cv.fy(y - half), cv.fy(y + half)], transform=cv.sub.transSubfigure,
                color=ctx.palette.control, lw=ctx.marks.tick_lw, zorder=3)  # fmt: skip
    _add(cv, ln, kind="tick", role="control")


def _band(cv: Canvas, ctx: Ctx, x, y):
    h = 0.6 * ctx.theme.row_h
    r = Rectangle((cv.fx(x - 0.12), cv.fy(y + h / 2)), 0.24 / cv.w, h / cv.h, transform=cv.sub.transSubfigure,
                  facecolor=ctx.chrome("band"), edgecolor="none", lw=0, zorder=1)  # fmt: skip
    _add(cv, r, kind="band")
