"""Rendering. A Figure's blocks are planned first (size, positions, what each draws); the key is built from the plans;
then everything is drawn into one matplotlib figure, one subfigure per section, so the checks see the whole figure.

Every artist the library draws is tagged (`_tags.tag`) with what it means: kind, role, cell, status, encoding. The
checks read meaning from those tags, not from pixels.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure as MplFigure
from matplotlib.patches import Rectangle

from styles_plot import _numbers
from styles_plot import _registry as R
from styles_plot._model import Distribution, DotTable, Scatter, Schematic, Stack, Sweep
from styles_plot._tags import tag
from styles_plot._text import line_h, text_size, wrap
from styles_plot._theme import Theme
from styles_plot._vocab import Vocab

MARGIN = 0.12  # inches left and right of the title, key and caption


class BuildError(ValueError):
    """A figure declaration that cannot be drawn: an unknown role, unit, row or target; a table that does not fit."""


# ---- per-render state ------------------------------------------------------------------------------------------------
@dataclass
class Ctx:
    vocab: Vocab
    theme: Theme
    figure_id: str
    registry: R.Registry | None
    numbers: list[tuple[str, str]] = field(default_factory=list)  # (data key, printed string)

    @property
    def palette(self):
        return self.vocab.palette

    @property
    def marks(self):
        return self.vocab.marks

    @property
    def words(self):
        return self.vocab.words

    @property
    def sizes(self):
        return self.theme.sizes

    def chrome(self, name: str) -> str:
        return self.vocab.palette.chrome[name]

    def role_hex(self, role: str) -> str:
        if role == "control":
            return self.palette.control
        if role == "other":
            return self.palette.other
        try:
            return self.vocab.role(role).hex
        except KeyError as e:
            raise BuildError(str(e)) from None

    def unit(self, name: str):
        try:
            return self.vocab.unit(name)
        except KeyError as e:
            raise BuildError(f"{self.figure_id}: {e}") from None

    def entity_name(self, kind: str, key: str) -> str:
        try:
            return self.vocab.entity(kind, key).name
        except KeyError as e:
            raise BuildError(f"{self.figure_id}: {e}") from None

    def check_rows(self, kind: str, rows) -> None:
        try:
            self.vocab.check_order(kind, rows)
        except (KeyError, ValueError) as e:
            raise BuildError(f"{self.figure_id}: {e}") from None

    def status(self, cell: str | None) -> R.Status:
        """A cell's status. A cell the registry lacks draws filled and untagged; the status check reports it."""
        if cell is None or self.registry is None:
            return R.Status()
        return self.registry.get(self.figure_id, cell) or R.Status()

    # numbers: every printed number goes through here and is logged by its data key
    def _log(self, key: str | None, s: str) -> str:
        if key:
            self.numbers.append((key, s))
        return s

    def value(self, unit: str, value: float, key: str | None) -> str:
        return self._log(key, self.vocab.format(value, unit))

    def interval(self, unit: str, lo: float, hi: float, key: str | None) -> str:
        return self._log(f"{key}.interval" if key else None, self.vocab.format_interval(lo, hi, unit))

    def count(self, k: int, n: int, key: str | None) -> str:
        return self._log(key, self.vocab.format_count(k, n))

    @staticmethod
    def tick(v: float) -> str:
        return _numbers.tick(v)

    def measure(self, s: str, size: float, weight: str = "normal") -> tuple[float, float]:
        return text_size(s, size, weight, self.theme.font)

    def wrap(self, s: str, width: float, size: float, weight: str = "normal") -> list[str]:
        return wrap(s, width, size, weight, self.theme.font)


# ---- canvas: an inch-based view of a subfigure -----------------------------------------------------------------------
class Canvas:
    """Positions in inches: x from the left edge, y from the top edge of the subfigure."""

    def __init__(self, sub, width: float, height: float, ctx: Ctx):
        self.sub, self.w, self.h, self.ctx = sub, width, height, ctx

    def fx(self, x: float) -> float:
        return x / self.w

    def fy(self, y: float) -> float:
        return 1 - y / self.h

    def text(self, x, y, s, *, kind, size, color=None, weight="normal", ha="left", va="center", **meta):
        t = self.sub.text(self.fx(x), self.fy(y), s, ha=ha, va=va, fontsize=size, fontweight=weight,
                          color=color or self.ctx.chrome("text"), fontfamily=self.ctx.theme.font)  # fmt: skip
        return tag(t, kind=kind, **meta)

    def rich(self, x, y, parts, *, size, ha="left"):
        """Texts side by side, [(text, colour, weight, tags)], measured so they abut."""
        total = sum(self.ctx.measure(s, size, wt)[0] for s, _c, wt, _m in parts)
        cx = x - total if ha == "right" else x - total / 2 if ha == "center" else x
        for s, col, wt, meta in parts:
            if s:
                self.text(cx, y, s, size=size, color=col, weight=wt, **{"kind": "text", **meta})
            cx += self.ctx.measure(s, size, wt)[0]

    def rect(self, x, y, w, h, color, *, kind, zorder=-5, **meta):
        r = Rectangle((self.fx(x), self.fy(y + h)), w / self.w, h / self.h, transform=self.sub.transSubfigure,
                      facecolor=color, edgecolor="none", lw=0, zorder=zorder)  # fmt: skip
        self.sub.add_artist(r)
        return tag(r, kind=kind, **meta)

    def axes(self, x, y, w, h):
        """Bare axes at a position in inches: no spines, no ticks, transparent."""
        ax = self.sub.add_axes((self.fx(x), self.fy(y + h), w / self.w, h / self.h))
        ax.patch.set_alpha(0)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_xticks([])
        ax.set_yticks([])
        return ax


@dataclass
class Plan:
    """A block laid out: its height, the encodings it draws (for the key), and how to draw it."""

    height: float
    encodings: set
    draw: Callable[[Canvas], None]


@dataclass(frozen=True)
class RenderInfo:
    """What the checks and the sidecar need to know about a render, attached to the matplotlib figure."""

    figure: str
    target: str
    theme: Theme
    vocab: Vocab
    registry: R.Registry | None
    numbers: tuple[tuple[str, str], ...]
    direct_labels: bool
    natural_height: float
    blocks: tuple[str, ...]
    encodings: frozenset


def info(fig) -> RenderInfo:
    """The RenderInfo of a figure rendered by styles-plot."""
    i = getattr(fig, "_sp_info", None)
    if not isinstance(i, RenderInfo):
        raise ValueError("not a figure rendered by styles-plot (Figure.render)")
    return i


# ---- the key ---------------------------------------------------------------------------------------------------------
def key_items(ctx: Ctx, enc: set) -> list[tuple[str, str, str, tuple]]:
    """(mark, mark colour, phrase, encoding) for each drawn encoding, in the grammar's fixed order: controls, tick,
    post hoc, whiskers and shading per interval kind, median, band."""
    w, v = ctx.words, ctx.vocab
    out = []
    controls = sorted(e[1] for e in enc if e[0] == "control")
    if controls:
        out.append((w.control_mark, ctx.palette.control, w.control.format(" · ".join(controls)), ("control",)))
    if ("tick",) in enc:
        if not v.key_tick:
            raise BuildError("a grey tick is drawn but the vocabulary has no [key].tick")
        out.append(("", "", w.tick.format(v.key_tick), ("tick",)))
    if ("post_hoc",) in enc:
        out.append(("", "", w.post_hoc, ("post_hoc",)))
    kinds = {e[1] for e in enc if e[0] in ("whisker", "shading")}
    unknown = kinds - set(v.intervals)
    if unknown:
        raise BuildError(f"interval kinds {sorted(unknown)} are not in the vocabulary's [intervals]")
    for kind in v.intervals:
        for what in ("whisker", "shading"):
            if (what, kind) in enc:
                out.append(("", "", getattr(w, what).format(v.intervals[kind]), (what, kind)))
    if ("median",) in enc:
        out.append(("", "", w.median, ("median",)))
    if ("band",) in enc:
        if not v.key_band:
            raise BuildError("a grey band is drawn but the vocabulary has no [key].band")
        out.append(("", "", w.band.format(v.key_band), ("band",)))
    return out


def _key_lines(ctx: Ctx, items, width: float) -> list[list[tuple]]:
    size, gap = ctx.sizes.key, 0.3
    lines: list[list[tuple]] = []
    used = 0.0
    for it in items:
        mark, _c, phrase, _e = it
        wd = ctx.measure(f"{mark} {phrase}" if mark else phrase, ctx.sizes.key)[0]
        if not lines or used + gap + wd > width:
            lines.append([])
            used = -gap
        used += gap + wd
        lines[-1].append(it)
    return lines


def _draw_key(cv: Canvas, lines, controls: tuple[str, ...]) -> None:
    ctx, size = cv.ctx, cv.ctx.sizes.key
    for i, line in enumerate(lines):
        x, y = MARGIN, 0.1 + (i + 0.5) * line_h(size)
        for mark, col, phrase, enc in line:
            meta = {"encoding": enc, "controls": controls} if enc == ("control",) else {"encoding": enc}
            if mark:
                cv.text(x, y, mark, kind="key_mark", size=size, color=col, role="control", **meta)
                x += ctx.measure(mark + " ", size)[0]
            cv.text(x, y, phrase, kind="key", size=size, color=ctx.chrome("muted"), **meta)
            x += ctx.measure(phrase, size)[0] + 0.3


# ---- sections other than blocks -----------------------------------------------------------------------------------------
def _lines_section(ctx: Ctx, text: str, width: float, size: float, kind: str, weight: str, color: str):
    lines = ctx.wrap(text, width, size, weight)
    height = len(lines) * line_h(size) + 0.2

    def draw(cv: Canvas) -> None:
        for i, s in enumerate(lines):
            cv.text(MARGIN, 0.1 + (i + 0.5) * line_h(size), s, kind=kind, size=size, weight=weight, color=color,
                    full=text)  # fmt: skip

    return height, draw


def _planner(block) -> Callable:
    from styles_plot import _dist, _scatter, _schematic, _stack, _sweep, _table

    planners = {DotTable: _table.plan, Sweep: _sweep.plan, Distribution: _dist.plan, Stack: _stack.plan,
                Scatter: _scatter.plan, Schematic: _schematic.plan}  # fmt: skip
    for kind, plan in planners.items():
        if isinstance(block, kind):
            return plan
    raise BuildError(f"not a figure block: {type(block).__name__}")


def _label_width(ctx: Ctx, block) -> float:
    """The row-label column every block shares: the widest entity name or row sub-line."""
    rows = getattr(block, "rows", None)
    if not rows:
        return 0.0
    kind = block.kind
    widths = [ctx.measure(ctx.entity_name(kind, r), ctx.sizes.label, "bold")[0] for r in rows]
    widths += [ctx.measure(s, ctx.sizes.tag)[0] for s in getattr(block, "row_sub", {}).values()]
    return max(widths) + 0.25


# ---- figure ----------------------------------------------------------------------------------------------------------
class Figure:
    """Blocks stacked top to bottom with one key under the last. `title` (one claim) and `caption` (the detailed
    explanation) are drawn only by targets whose theme asks for them; `subtitle` is one grey vocabulary term above the
    blocks ("synthetic data"). `direct_labels` exempts a schematic-only figure from the colour-vision floors; every
    coloured element then needs its word right next to it."""

    def __init__(self, id: str, vocab: Vocab, *, title: str = "", caption: str = "", subtitle: str = "",
                 direct_labels: bool = False, registry: R.Registry | None = None):  # fmt: skip
        if not id or "/" in id:
            raise BuildError(f"bad figure id {id!r}")
        self.id = id
        self.vocab = vocab
        self.title = title
        self.caption = caption
        self.subtitle = subtitle
        self.direct_labels = direct_labels
        self.blocks: list = []
        self._registry = registry

    def add(self, *blocks) -> Figure:
        self.blocks.extend(blocks)
        return self

    @property
    def registry(self) -> R.Registry | None:
        """The registry passed in, else the vocabulary's [registry].path when that file exists."""
        if self._registry is None and self.vocab.registry_path and Path(self.vocab.registry_path).exists():
            self._registry = R.load(self.vocab.registry_path)
        return self._registry

    def status(self, cell: str) -> R.Status | None:
        reg = self.registry
        return None if reg is None else reg.get(self.id, cell)

    def render(self, target: str = "notebook") -> MplFigure:
        """Lay out and draw for a target. The returned matplotlib figure carries a RenderInfo for the checks."""
        try:
            theme = self.vocab.target(target)
        except KeyError as e:
            raise BuildError(str(e)) from None
        if not self.blocks:
            raise BuildError(f"figure {self.id!r} has no blocks")
        ctx = Ctx(self.vocab, theme, self.id, self.registry)
        W, inner = theme.width_in, theme.width_in - 2 * MARGIN
        muted = ctx.chrome("muted")

        label_w = max(_label_width(ctx, b) for b in self.blocks)
        plans = [_planner(b)(b, ctx, W, label_w) for b in self.blocks]
        enc = frozenset().union(*(p.encodings for p in plans))
        k_lines = _key_lines(ctx, key_items(ctx, set(enc)), inner)
        controls = tuple(sorted(e[1] for e in enc if e[0] == "control"))

        sections: list[tuple[float, Callable]] = []
        if theme.title and self.title:
            sections.append(_lines_section(ctx, self.title, inner, theme.title_size, "title", "bold",
                                           ctx.chrome("text")))  # fmt: skip
        if self.subtitle:
            sections.append(_lines_section(ctx, self.subtitle, inner, ctx.sizes.tag, "subtitle", "normal", muted))
        sections += [(p.height, p.draw) for p in plans]
        key_h = len(k_lines) * line_h(ctx.sizes.key) + (0.2 if k_lines else 0.05)
        sections.append((key_h, lambda cv: _draw_key(cv, k_lines, controls)))
        if theme.caption and self.caption:
            sections.append(_lines_section(ctx, self.caption, inner, theme.caption_size, "caption", "normal", muted))

        natural = sum(h for h, _ in sections)
        height = natural
        if theme.height_in is not None:
            height = max(natural, theme.height_in)
        elif theme.aspect is not None:
            height = max(natural, W / theme.aspect[1])  # too wide for the target: white space under the key
        if height > natural + 1e-9:
            sections.append((height - natural, lambda cv: None))

        with matplotlib.rc_context({"font.family": theme.font, "svg.fonttype": "none"}):
            fig = MplFigure(figsize=(W, height), dpi=theme.dpi, facecolor=self.vocab.palette.chrome["background"])
            FigureCanvasAgg(fig)
            subs = fig.subfigures(len(sections), 1, height_ratios=[h for h, _ in sections], hspace=0, wspace=0)
            for (h, draw), sub in zip(sections, [subs] if len(sections) == 1 else subs):
                sub.set_facecolor("none")
                draw(Canvas(sub, W, h, ctx))
        fig._sp_info = RenderInfo(
            figure=self.id, target=target, theme=theme, vocab=self.vocab, registry=self.registry,
            numbers=tuple(ctx.numbers), direct_labels=self.direct_labels, natural_height=natural,
            blocks=tuple(type(b).__name__ for b in self.blocks), encodings=enc,
        )  # fmt: skip
        return fig
