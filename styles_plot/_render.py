"""Rendering. A Figure's blocks are planned first (size, positions, what each draws); the key is built from the plans;
then everything is drawn into one matplotlib figure, one subfigure per section, so the checks see the whole figure.

Every artist the library draws is tagged (`_tags.tag`) with what it means: kind, role, cell, status, encoding. The
checks read meaning from those tags, not from pixels.
"""

from __future__ import annotations

import dataclasses
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
LANE_INDENT = 0.25  # inches a lane's label sits right of its row's name


class BuildError(ValueError):
    """A figure declaration that cannot be drawn: an unknown role, unit, row or target; a table that does not fit."""


WAIVABLE = frozenset({"SP601", "SP606", "SP610", "SP613"})  # text placement only: never a meaning check


@dataclass(frozen=True)
class Waive:
    """Accept one layout problem a person has looked at: `code` (text placement only: SP601, SP606, SP610, SP613),
    `text` the whole text at fault (a wrapped text by its full text; for SP606 either of the two), and why. `targets`
    limits it to some targets (default: all). A waiver that matches nothing on a target it applies to is SP905."""

    code: str
    text: str
    reason: str
    targets: tuple[str, ...] = ()

    def __post_init__(self):
        if self.code not in WAIVABLE:
            raise BuildError(f"{self.code} cannot be waived (only text placement: {', '.join(sorted(WAIVABLE))})")
        if not self.text.strip():
            raise BuildError(f"a {self.code} waiver needs the text it waives")
        if not self.reason.strip():
            raise BuildError(f"the waiver of {self.code} {self.text!r} needs a reason")
        object.__setattr__(self, "targets", (self.targets,) if isinstance(self.targets, str) else tuple(self.targets))

    def applies_to(self, target: str) -> bool:
        return not self.targets or target in self.targets


# ---- per-render state ------------------------------------------------------------------------------------------------
@dataclass
class Ctx:
    vocab: Vocab
    theme: Theme
    figure_id: str
    registry: R.Registry | None
    numbers: list[tuple[str, str]] = field(default_factory=list)  # (data key, printed string)
    all_post_hoc: bool = False  # every estimate is post hoc: marks drawn filled, the key says so once
    findings: list[tuple] = field(default_factory=list)  # (code, message[, detail]) a block reports while laid out
    next_pid: int = 1000  # panel ids for project blocks' panels (a table numbers its own from 0)

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
        st = self.registry.get(self.figure_id, cell) or R.Status()
        if self.all_post_hoc and st.timing == "post_hoc":
            st = dataclasses.replace(st, drawn_filled=True)
        return st

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
        return text_size(s, size, weight, self.theme.font, self.theme.dpi)

    def wrap(self, s: str, width: float, size: float, weight: str = "normal") -> list[str]:
        return wrap(s, width, size, weight, self.theme.font, self.theme.dpi)


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
            cx += self.ctx.measure(s, size, wt)[0] + 0.01  # a hair between parts: no rounding overlap

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
    """A block laid out: its height in inches, how to draw it, and the encodings it draws (for the key line).
    *Experimental* as public API (`sp.Plan`): may change in a minor release.

    A project's block returns one from `plan(ctx, width)`; leave `encodings` as None and the renderer finds them by
    drawing the block once on a throwaway figure and reading what its primitives tagged, with the same function the
    key check uses, so the key and what is drawn cannot drift apart."""

    height: float
    draw: Callable
    encodings: set | None = None


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
    key_figure: bool = False
    all_post_hoc: bool = False
    text_only: bool = False  # cards only: exempt from the target's widest proportion
    findings: tuple[tuple, ...] = ()  # (code, message[, detail]) a block reported while laid out
    waivers: tuple[Waive, ...] = ()  # those that apply to this target


def info(fig) -> RenderInfo:
    """The RenderInfo of a figure rendered by styles-plot."""
    i = getattr(fig, "_sp_info", None)
    if not isinstance(i, RenderInfo):
        raise ValueError("not a figure rendered by styles-plot (Figure.render)")
    return i


# ---- the key ---------------------------------------------------------------------------------------------------------
KEY_AIR = 0.15  # inches above a key laid out one item per line


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
    if ("all_post_hoc",) in enc:
        out.append(("", "", w.all_post_hoc, ("all_post_hoc",)))
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
    for name in sorted({e[1] for e in enc if e[0] == "band"}):
        try:
            out.append(("", "", w.band.format(v.band(name)), ("band", name)))
        except KeyError as e:
            raise BuildError(f"a grey band is drawn but {e.args[0]}") from None
    return out


def _key_lines(ctx: Ctx, items, width: float) -> list[list[tuple]]:
    gap = 0.3
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


def _draw_key(cv: Canvas, lines, controls: tuple[str, ...], air: float = 0.0) -> None:
    ctx, size = cv.ctx, cv.ctx.sizes.key
    for i, line in enumerate(lines):
        x, y = MARGIN, air + 0.1 + (i + 0.5) * line_h(size)
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
    from styles_plot import _card, _dist, _keyfig, _scatter, _schematic, _stack, _sweep, _table
    from styles_plot._model import Card

    planners = {DotTable: _table.plan, Sweep: _sweep.plan, Distribution: _dist.plan, Stack: _stack.plan,
                Scatter: _scatter.plan, Schematic: _schematic.plan, Card: _card.plan,
                _keyfig.KeyLegend: _keyfig.plan_legend, _keyfig.ReadAloud: _keyfig.plan_read_aloud}  # fmt: skip
    for kind, plan in planners.items():
        if isinstance(block, kind):
            return plan
    from styles_plot import _custom

    if _custom.is_block(block):
        return _custom.plan
    raise BuildError(f"not a figure block: {type(block).__name__} (a block has plan(ctx, width) -> sp.Plan)")


def _estimate_cells(block) -> list:
    """The registry cells of a block's estimates (the marks that could be hollow, and sweep lines)."""
    from styles_plot._model import DotColumn, Est

    if isinstance(block, DotTable):
        return [v.cell for c, _g in block.flat_columns() if isinstance(c, DotColumn) for s in c.series
                for v in s.cells.values() if isinstance(v, Est)]  # fmt: skip
    if isinstance(block, Sweep):
        return [ln.cell for ln in block.lines] + [p.cell for p in block.points]
    if isinstance(block, Distribution):
        return list(block.cells.values()) if block.cells else [None]
    if isinstance(block, Stack):
        return [v.cell for seg in block.segments for v in seg.shares.values()]
    if isinstance(block, Scatter):
        return [c.cell for p in block.panels for c in p.clouds]
    return []


def _all_post_hoc(fig, registry, blocks) -> bool:
    """Whether every estimate of a figure is post hoc in the registry (then hollow marks would say nothing)."""
    from styles_plot import _custom

    if any(_custom.is_block(b) for b in blocks):  # a project block's cells are unknown before it draws: stay hollow
        return False
    cells = [c for b in blocks for c in _estimate_cells(b)]
    if not cells or registry is None or any(c is None for c in cells):
        return False
    return all((st := registry.get(fig.id, c)) is not None and st.timing == "post_hoc" for c in cells)


def _label_width(ctx: Ctx, block) -> float:
    """The row-label column every block shares: the widest entity name, row sub-line, lane or row-group label."""
    rows = getattr(block, "rows", None)
    if not rows or not hasattr(block, "kind"):  # entity rows only (a card's rows are readers, not entities)
        return 0.0
    kind = block.kind
    grouped = {k for g in getattr(block, "groups", ()) for k in g.rows}  # indented under their group's header
    widths = [(LANE_INDENT if r in grouped else 0.0) + ctx.measure(ctx.entity_name(kind, r), ctx.sizes.label, "bold")[0]
              for r in rows]  # fmt: skip
    widths += [ctx.measure(s, ctx.sizes.tag)[0] for s in getattr(block, "row_sub", {}).values()]
    widths += [LANE_INDENT + ctx.measure(ln.label, ctx.sizes.tag)[0] for ln in getattr(block, "lanes", ()) if ln.label]
    widths += [ctx.measure(g.label, ctx.sizes.tag, "bold")[0] for g in getattr(block, "groups", ())]
    return max(widths) + 0.25


# ---- figure ----------------------------------------------------------------------------------------------------------
class Figure:
    """Blocks stacked top to bottom with one key under the last. `title` (one claim) and `caption` (the detailed
    explanation) are drawn only by targets whose theme asks for them; `subtitle` is one grey vocabulary term above the
    blocks ("synthetic data"); `read` is one sentence under the blocks that walks through one value, its numbers given
    as `numbers={name: (value, unit, data key)}` and printed in the unit's format. `direct_labels` exempts a figure of
    schematics and cards from the colour-vision floors; every coloured element then needs its word right next to it.
    `waive` lists `Waive`s: layout problems a person has looked at and accepted. `key_layout` "flow" fills the key's
    lines left to right; "column" puts each item on its own line, with air above the key."""

    def __init__(self, id: str, vocab: Vocab, *, title: str = "", caption: str = "", subtitle: str = "",
                 direct_labels: bool = False, registry: R.Registry | None = None, read: str = "",
                 numbers: dict | None = None, waive=(), key_layout: str = "flow"):  # fmt: skip
        if key_layout not in ("flow", "column"):
            raise BuildError(f"key_layout={key_layout!r}: use 'flow' or 'column'")
        self.key_layout = key_layout
        if not id or "/" in id:
            raise BuildError(f"bad figure id {id!r}")
        self.waive = tuple(waive)
        for w in self.waive:
            if not isinstance(w, Waive):
                raise BuildError(f"waive= takes sp.Waive(code, text, reason), got {w!r}")
        self.id = id
        self.vocab = vocab
        self.title = title
        self.caption = caption
        self.subtitle = subtitle
        self.direct_labels = direct_labels
        self.read = read  # one sentence under the blocks that walks through one value (a vocabulary template)
        self.read_numbers = dict(numbers or {})  # name -> (value, unit, data key), filled into "{name}" in `read`
        self.blocks: list = []
        self._registry = registry
        self._key_figure = False  # set by key_figure(): its legend is the key, so no key line is drawn

    def add(self, *blocks) -> Figure:
        self.blocks.extend(blocks)
        return self

    @property
    def registry(self) -> R.Registry | None:
        """The registry passed in, else the vocabulary's [registry].path when that file exists."""
        if self._registry is None and self.vocab.registry_path and Path(self.vocab.registry_path).exists():
            self._registry = R.load(self.vocab.registry_path)
        return self._registry

    def _text_only(self) -> bool:
        """A figure of example cards only: text, as wide and as short as its lines (no padding to the target's widest
        proportion; the narrowest still holds)."""
        from styles_plot._model import Card

        return bool(self.blocks) and all(isinstance(b, Card) for b in self.blocks)

    def status(self, cell: str) -> R.Status | None:
        reg = self.registry
        return None if reg is None else reg.get(self.id, cell)

    def preview(self, target: str = "post"):
        """This figure as `target` would publish it, checked: shows the PNG (problems boxed in red) and the problem
        list in a notebook. Writes nothing."""
        from styles_plot._save import preview

        return preview(self, target)

    def _repr_png_(self) -> bytes:
        """A notebook shows a Figure as its notebook render (never publishable; `preview` checks a real target)."""
        import io

        mpl = self.render("notebook")
        buf = io.BytesIO()
        mpl.savefig(buf, format="png", dpi=mpl.dpi, facecolor=self.vocab.palette.chrome["background"])
        return buf.getvalue()

    def render(self, target: str = "notebook") -> MplFigure:
        """Lay out and draw for a target. The returned matplotlib figure carries a RenderInfo for the checks."""
        try:
            theme = self.vocab.target(target)
        except KeyError as e:
            raise BuildError(str(e)) from None
        if not self.blocks:
            raise BuildError(f"figure {self.id!r} has no blocks")
        from styles_plot._bind import resolve

        bound = [resolve(b, self.vocab, self.id) for b in self.blocks]  # callables and loose values read as Est
        ctx = Ctx(self.vocab, theme, self.id, self.registry, all_post_hoc=_all_post_hoc(self, self.registry, bound))
        W, inner = theme.width_in, theme.width_in - 2 * MARGIN
        muted = ctx.chrome("muted")

        label_w = max(_label_width(ctx, b) for b in bound)
        blocks = list(bound)
        if self.read:
            from styles_plot._keyfig import ReadAloud

            blocks.append(ReadAloud(self.read, tuple((k, *v) for k, v in self.read_numbers.items())))
        plans = [_planner(b)(b, ctx, W, label_w) for b in blocks]
        enc = frozenset().union(*(p.encodings for p in plans)) | ({("all_post_hoc",)} if ctx.all_post_hoc else set())
        items = key_items(ctx, set(enc))
        k_lines = [[it] for it in items] if self.key_layout == "column" else _key_lines(ctx, items, inner)
        k_air = KEY_AIR if self.key_layout == "column" and k_lines else 0.0
        controls = tuple(sorted(e[1] for e in enc if e[0] == "control"))

        sections: list[tuple[float, Callable]] = []
        if theme.title and self.title:
            sections.append(_lines_section(ctx, self.title, inner, theme.title_size, "title", "bold",
                                           ctx.chrome("text")))  # fmt: skip
        if self.subtitle:
            sections.append(_lines_section(ctx, self.subtitle, inner, ctx.sizes.tag, "subtitle", "normal", muted))
        sections += [(p.height, p.draw) for p in plans]
        if not self._key_figure:
            key_h = k_air + len(k_lines) * line_h(ctx.sizes.key) + (0.2 if k_lines else 0.05)
            sections.append((key_h, lambda cv: _draw_key(cv, k_lines, controls, k_air)))
        if theme.caption and self.caption:
            sections.append(_lines_section(ctx, self.caption, inner, theme.caption_size, "caption", "normal", muted))

        natural = sum(h for h, _ in sections)
        height = natural
        if theme.height_in is not None:
            height = max(natural, theme.height_in)
        elif theme.aspect is not None and not self._text_only():
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
            blocks=tuple(type(b).__name__ for b in self.blocks), encodings=enc, key_figure=self._key_figure,
            all_post_hoc=ctx.all_post_hoc, findings=tuple(ctx.findings), text_only=self._text_only(),
            waivers=tuple(w for w in self.waive if w.applies_to(target)),
        )  # fmt: skip
        return fig
