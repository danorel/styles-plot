"""Blocks a project writes itself (*experimental*: `BlockContext`, `Canvas`, `Panel`, `Plan` and `Custom` may change in
a minor release).

A block is any object with `plan(ctx: BlockContext, width: float) -> Plan`. Its `draw(cv: Canvas)` draws with meaning
primitives that tag what they draw exactly as the built-in blocks do (a dot's fill comes from the registry, a number
goes through its unit's formatter, a panel carries its unit's axis title and cue), so every check reads it like the
rest. Raw matplotlib inside `draw` is allowed and checked like everything else: an untagged artist in a role colour is
SP103, a word not in the vocabulary SP401, a number no formatter printed SP501.

When a plan leaves `encodings` as None the renderer draws the block once on a throwaway figure of its size and reads
the encodings from what was tagged, with the function the key check (SP301, SP302) uses: the key line is built from
what the block draws, never from a list kept by hand.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure as MplFigure
from matplotlib.patches import Rectangle

from styles_plot import _grid
from styles_plot._model import Est
from styles_plot._render import BuildError, Canvas as _Canvas, Ctx, Plan
from styles_plot._tags import tag
from styles_plot._text import PT, line_h


def _size(ctx: Ctx, size) -> float:
    """A text size: a field of the target's Sizes ("value", "tag", "header"...) or points."""
    if isinstance(size, str):
        try:
            return getattr(ctx.sizes, size)
        except AttributeError:
            raise BuildError(f"no text size {size!r}; one of the target's sizes or points") from None
    return float(size)


class BlockContext:
    """*Experimental.* What a project block may know while it plans: the vocabulary, the target (a Theme), the shared
    row-label width (to align with tables), text measurement and wrapping in the target's font, and lookups that fail
    with a BuildError naming what is missing. A read-only view, not the renderer's state."""

    def __init__(self, ctx: Ctx, label_width: float):
        self._ctx = ctx
        self.label_width = label_width

    @property
    def vocab(self):
        return self._ctx.vocab

    @property
    def target(self):
        return self._ctx.theme

    @property
    def figure_id(self) -> str:
        return self._ctx.figure_id

    def measure(self, text: str, size="value", weight: str = "normal") -> tuple[float, float]:
        """(width, height) in inches."""
        return self._ctx.measure(text, _size(self._ctx, size), weight)

    def wrap(self, text: str, width: float, size="value", weight: str = "normal") -> list[str]:
        return self._ctx.wrap(text, width, _size(self._ctx, size), weight)

    def line_height(self, size="value") -> float:
        return line_h(_size(self._ctx, size))

    def unit(self, name: str):
        return self._ctx.unit(name)

    def role(self, name: str):
        try:
            return self._ctx.vocab.role(name)
        except KeyError as e:
            raise BuildError(f"{self._ctx.figure_id}: {e}") from None

    def status(self, cell: str):
        """A cell's status in the registry (timing, claim); an unregistered cell reads as filled and claimed, and the
        status check reports it."""
        return self._ctx.status(cell)

    def axis_height(self, unit: str, width: float) -> float:
        """The height a panel's tick labels, axis title and cue take under it."""
        return _grid.x_bottom_height(self._ctx, self.unit(unit), width)[0]


class Canvas:
    """*Experimental.* Where a project block draws: inches from the block's top-left (x right, y down). `word`,
    `number` and `panel` tag what they draw; `axes` and `subfigure` give raw matplotlib, checked like the rest."""

    def __init__(self, cv: _Canvas):
        self._cv = cv

    @property
    def width(self) -> float:
        return self._cv.w

    @property
    def height(self) -> float:
        return self._cv.h

    @property
    def subfigure(self):
        return self._cv.sub

    def axes(self, x: float, y: float, w: float, h: float):
        """Bare matplotlib axes at a position in inches: no spines, no ticks, transparent."""
        return self._cv.axes(x, y, w, h)

    def word(self, x: float, y: float, text: str, role: str | None = None, size="value", weight: str = "normal",
             ha: str = "left", va: str = "center"):  # fmt: skip
        """A vocabulary word: ink, or in a role's colour (then it names that role, as a role word does)."""
        ctx = self._cv.ctx
        col = ctx.role_hex(role) if role else ctx.chrome("text")
        meta = {"role": role} if role else {}
        return self._cv.text(x, y, text, kind="word", size=_size(ctx, size), color=col, weight=weight, ha=ha, va=va,
                             **meta)  # fmt: skip

    def number(self, x: float, y: float, value: float, unit: str, key: str, role: str | None = None, size="value",
               ha: str = "left", va: str = "center"):  # fmt: skip
        """A value in its unit's format, logged under its data key (one key prints one string everywhere)."""
        ctx = self._cv.ctx
        text = ctx.value(unit, value, key)
        col = ctx.chrome("muted") if role == "control" else ctx.role_hex(role) if role else ctx.chrome("text")
        meta = {"role": role} if role else {}
        return self._cv.text(x, y, text, kind="value", size=_size(ctx, size), color=col, ha=ha, va=va, key=key,
                             unit=unit, **meta)  # fmt: skip

    def panel(self, x: float, y: float, w: float, h: float, unit: str, xlim: tuple[float, float],
              xticks=None) -> Panel:  # fmt: skip
        """An x axis on one unit: a box of `h` inches for marks, then tick labels, the unit's axis title and its cue
        under it (`BlockContext.axis_height` tells how tall). Marks go on the returned Panel, x in data units, y in
        inches from the panel's top."""
        ctx = self._cv.ctx
        u = ctx.unit(unit)
        if xlim is None:
            raise BuildError(f"{ctx.figure_id}: a panel on {unit!r} needs xlim")
        ticks = list(xticks) if xticks is not None else _grid.ticks(tuple(xlim), u.scale)
        ax = self._cv.axes(x, y, w, h)
        if u.scale == "log":
            ax.set_xscale("log")
        ax.set_xlim(*xlim)
        ax.set_ylim(h, 0)
        ax.spines["bottom"].set_visible(True)
        ax.spines["bottom"].set_color(ctx.chrome("faint"))
        ax.set_xticks(ticks, labels=[""] * len(ticks))
        ax.minorticks_off()
        ax.tick_params(axis="x", length=3, color=ctx.chrome("faint"), pad=0)
        pid = ctx.next_pid
        ctx.next_pid += 1
        tag(ax, kind="panel", pid=pid, unit=unit, cue=u.cue, header="")
        for tv in ticks:
            tag(ax.plot([tv, tv], [0, h], color=ctx.chrome("grid"), lw=0.8, zorder=0), kind="grid")
        _h, title, cue = _grid.x_bottom_height(ctx, u, w)
        _grid.draw_x_bottom(self._cv, ctx, x, w, y + h, tuple(xlim), ticks, u, title, cue, pid)
        return Panel(self._cv, ax, x, y, w, unit, tuple(xlim), u.scale)


class Panel:
    """*Experimental.* Marks on one panel: x in the unit's data values, y in inches from the panel's top."""

    def __init__(self, cv: _Canvas, ax, x0: float, y0: float, w: float, unit: str, xlim: tuple, scale: str):
        self._cv, self.ax, self.unit = cv, ax, unit
        self._x0, self._y0, self._w, self._xlim, self._log = x0, y0, w, xlim, scale == "log"

    def x(self, value: float) -> float:
        """A data value's position in inches from the block's left edge (to place a word at it)."""
        return self._inches(value)

    def _inches(self, v: float) -> float:
        """A data x as inches from the block's left edge."""
        lo, hi = self._xlim
        f = math.log(v / lo) / math.log(hi / lo) if self._log else (v - lo) / (hi - lo)
        return self._x0 + f * self._w

    def _y(self, y: float) -> float:
        """A panel y (inches from its top) as inches from the block's top."""
        return self._y0 + y

    def dot(self, y: float, est: Est, role: str, control: str | None = None) -> None:
        """An estimate: a dot in the role's colour, hollow when its registry cell is post hoc, with a same-colour
        whisker when it has an interval and its value beside it when `est.label`. A control's dot needs `control`,
        the name the key's "grey: …" prints."""
        from styles_plot._table import _dot

        ctx = self._cv.ctx
        if not isinstance(est, Est):
            raise BuildError(f"{ctx.figure_id}: Panel.dot takes an sp.Est, got {type(est).__name__}")
        _dot(self.ax, ctx, SimpleNamespace(role=role, control=control), est, y)
        if est.label:
            right = est.hi if est.hi is not None else est.value
            x = self._inches(right) + (ctx.marks.dot_size / 2 + 4) * PT
            col = ctx.chrome("muted") if role == "control" else ctx.role_hex(role)
            text = ctx.value(self.unit, est.value, est.key)
            self._cv.text(x, self._y(y), text, kind="value", size=ctx.sizes.value, color=col, key=est.key,
                          cell=est.cell, unit=self.unit, role=role)  # fmt: skip

    def tick(self, x: float, y: float) -> None:
        """The grey tick: the vocabulary's `[key].tick` (e.g. the largest same-size control) at x on this line."""
        ctx = self._cv.ctx
        mk = ctx.marks
        half = mk.tick_half * ctx.theme.row_h
        tag(self.ax.plot([x, x], [y - half, y + half], color=ctx.palette.control, lw=mk.tick_lw, zorder=3),
            kind="tick", role="control")  # fmt: skip

    def rule(self, x: float, label: str = "") -> None:
        """A dashed grey reference line across the panel, its vocabulary label above the panel."""
        ctx = self._cv.ctx
        mk = ctx.marks
        h = self.ax.get_ylim()[0]
        tag(self.ax.plot([x, x], [0, h], color=ctx.chrome("rule"), lw=mk.rule_lw, ls=(0, mk.rule_dash), zorder=1),
            kind="rule")  # fmt: skip
        if label:
            size = ctx.sizes.tag
            self._cv.text(self._inches(x), self._y(0) - line_h(size) / 2 - 0.02, label, kind="rule_label", size=size,
                          color=ctx.chrome("muted"), ha="center")  # fmt: skip

    def band(self, lo: float, hi: float, name: str = "") -> None:
        """A grey band from lo to hi: `[key].band`, or a named one from `[key.bands]`."""
        ctx = self._cv.ctx
        h = self.ax.get_ylim()[0]
        rect = Rectangle((lo, 0), hi - lo, h, facecolor=ctx.chrome("band"), edgecolor="none", lw=0, zorder=0.5)
        self.ax.add_patch(rect)
        tag(rect, kind="band", band=name)

    def connector(self, a: float, b: float, y: float) -> None:
        """The grey line joining two estimates of one row."""
        ctx = self._cv.ctx
        tag(self.ax.plot([a, b], [y, y], color=ctx.chrome("connector"), lw=ctx.marks.connector_lw,
                         solid_capstyle="round", zorder=2), kind="connector")  # fmt: skip


@dataclass(frozen=True)
class Custom:
    """*Experimental.* A block of a fixed height drawn by one function `draw(cv: sp.Canvas)`. Its key entries are
    read from what `draw` draws."""

    height: float
    draw: Callable

    def plan(self, ctx: BlockContext, width: float) -> Plan:
        return Plan(self.height, self.draw)


# ---- the renderer's side ---------------------------------------------------------------------------------------------
def is_block(obj) -> bool:
    return callable(getattr(obj, "plan", None))


def plan(block, ctx: Ctx, width: float, label_w: float) -> Plan:
    """Plan a project block: call its `plan`, wrap its draw so it gets a public Canvas, and read its encodings from a
    dry run when it leaves them to the library."""
    p = block.plan(BlockContext(ctx, label_w), width)
    name = type(block).__name__
    if not isinstance(p, Plan):
        raise BuildError(f"{ctx.figure_id}: {name}.plan must return sp.Plan, got {type(p).__name__}")
    if not p.height > 0:
        raise BuildError(f"{ctx.figure_id}: {name} plans a height of {p.height!r} in; it must be positive")
    user_draw = p.draw

    def draw(cv: _Canvas) -> None:
        user_draw(Canvas(cv))

    enc = set(p.encodings) if p.encodings is not None else _dry_run(draw, ctx, width, p.height)
    return Plan(p.height, draw, enc)


def _dry_run(draw, ctx: Ctx, width: float, height: float) -> set:
    """Draw once on a throwaway figure of the block's size, with a copy of the render's state (its printed numbers and
    findings are discarded), and read the encodings from what was tagged."""
    from styles_plot._checks._base import marks_of
    from styles_plot._checks._keys import encodings_of

    dry = dataclasses.replace(ctx, numbers=[], findings=[])
    fig = MplFigure(figsize=(width, height), dpi=ctx.theme.dpi)
    FigureCanvasAgg(fig)
    sub = fig.subfigures(1, 1)
    draw(_Canvas(sub, width, height, dry))
    return encodings_of(marks_of(fig))
