"""What a figure shows, declared as plain data. Nothing here draws; `Figure.render` lays the blocks out for a target.

Every data mark carries a `cell`: its id in the status registry, from which the mark's fill (timing) and grey tag
(claim) are read. A printed number carries a `key`: its data key, so one key prints one string everywhere.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import KW_ONLY, dataclass, field
from typing import Union

import numpy as np


# ---- values ------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Est:
    """An estimate: a dot, with a same-colour whisker when lo and hi are given."""

    value: float
    lo: float | None = None
    hi: float | None = None
    cell: str | None = None  # registry id (required for a publishable figure)
    key: str | None = None  # data key, required when the value is printed
    label: bool = False  # print the value beside the dot
    interval: str = "ci95"  # an [intervals] kind: names the whisker in the key
    note: str | None = None  # grey words for part of the estimate, from [terms].missing ("no interval")

    def __post_init__(self):
        if (self.lo is None) != (self.hi is None):
            raise ValueError("an interval needs both lo and hi")
        if self.lo is not None and not self.lo <= self.hi:
            raise ValueError(f"interval [{self.lo}, {self.hi}] has lo > hi")
        if self.label and not self.key:
            raise ValueError("a printed value needs a data key (key=...)")


@dataclass(frozen=True)
class Missing:
    """A missing cell: grey words from the vocabulary's [terms].missing."""

    words: str


@dataclass(frozen=True)
class Count:
    """A count, printed "k of n"."""

    k: int
    n: int
    cell: str | None = None
    key: str | None = None


Value = Union[Est, Missing, Count]


@dataclass(frozen=True)
class Rule:
    """A dashed grey reference line with a canonical label ("chance"). A label with a number in it is a template with
    one "{}" filled with `x` in `unit`'s format and logged under `key` ("bar fixed in advance: {}")."""

    x: float
    label: str = ""
    unit: str | None = None
    key: str | None = None


# ---- dot table ---------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Series:
    """One role's estimates in a dot column. `cells` maps a row (or (row, lane) in a table with lanes) to a value, or
    is a callable called for every row (`(row, lane)` with lanes). A value is an `Est` or `Missing`, or a number,
    `(value, lo, hi)` or a mapping with value/lo/hi, read as an `Est`. `cell` and `key` are templates for values that
    do not set their own (`{row}`, `{id}`, `{lane}`, `{role}`); `label` and `interval` apply to values read from
    numbers, tuples and mappings."""

    role: str  # a vocabulary role, or "control"
    cells: Mapping[Hashable, object] | Callable  # row, or (row, lane) in a table with lanes -> value
    control: str | None = None  # for role "control": which control ([controls].names)
    word: str | None = None  # the colour word above the first row (a vocabulary term); default: the role's word
    _: KW_ONLY
    cell: str | None = None  # template: "layer.{id}"
    key: str | None = None  # template: "acc.{row}"
    label: bool | None = None
    interval: str | None = None


@dataclass(frozen=True)
class DotColumn:
    """One panel of a dot table. `xlim` and `xticks` come, in this order, from the column, from the unit's `lim` and
    `ticks` in the vocabulary, or from the data (values, intervals, grey ticks, band, rules), padded, snapped to the
    ticks' step, and widened so the rightmost value label clears the right spine."""

    header: str
    unit: str
    xlim: tuple[float, float] | None = None
    xticks: Sequence[float] | None = None
    series: Sequence[Series] = ()
    connect: tuple[str, str] | None = None  # two series' roles joined by a grey connector in each row
    ticks: Mapping[Hashable, float] = field(default_factory=dict)  # grey tick per row (or (row, lane))
    band: tuple[float, float] | None = None  # the grey band
    rules: Sequence[Rule] = ()
    width: float | None = None  # inches; None shares the remaining width
    band_name: str = ""  # which [key.bands] definition the band has; "" = [key].band
    weight: float = 1.0  # this panel's share of the free width (panels without `width`), relative to the others


@dataclass(frozen=True)
class TextColumn:
    """Numbers beside a table: `cells` as in `Series` (a `Count` too); `cell` and `key` templates likewise."""

    header: str
    unit: str
    cells: Mapping[Hashable, object] | Callable
    role: str | None = None  # colour of the printed values; None = ink
    unit_title: bool = True  # False: no unit title under the column (its header already names the quantity)
    _: KW_ONLY
    cell: str | None = None
    key: str | None = None


@dataclass(frozen=True)
class Gutter:
    width: float = 0.15


@dataclass(frozen=True)
class ColumnGroup:
    header: str
    columns: Sequence[DotColumn | TextColumn]


@dataclass(frozen=True)
class Lane:
    """A sub-row of every entity row: a second condition of the same rows, named in words (never a shade). Cells of
    a table with lanes are keyed (row, lane key)."""

    key: str
    label: str = ""  # grey words in the label column (a vocabulary term); "" for lanes named by colour words only


@dataclass(frozen=True)
class DotTable:
    rows: Sequence[str]
    columns: Sequence[DotColumn | TextColumn | Gutter | ColumnGroup]
    kind: str = "models"
    row_sub: Mapping[str, str] = field(default_factory=dict)  # a grey second line under a row label
    lanes: Sequence[Lane] = ()  # sub-rows of every row
    note: str = ""  # one grey line above the table (a vocabulary term or template)

    def flat_columns(self) -> list[tuple[DotColumn | TextColumn | Gutter, ColumnGroup | None]]:
        out = []
        for c in self.columns:
            if isinstance(c, ColumnGroup):
                out += [(cc, c) for cc in c.columns]
            else:
                out.append((c, None))
        return out


# ---- sweep -------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Line:
    row: str
    role: str
    x: Sequence[float]
    y: Sequence[float]
    cell: str | None = None
    band: tuple[Sequence[float], Sequence[float]] | None = None  # interval band (lo, hi) per x
    interval: str = "ci95"  # names the band in the key
    median: bool = False  # the line is a median: the key says "line: median"
    word: str | None = None  # the words at the line's end (a vocabulary term); default: the role's word
    control: str | None = None  # for role "control": which control ([controls].names), named in the key


@dataclass(frozen=True)
class Point:
    """A dot on a line at x (a cell fixed in advance, or a chosen layer). By default it sits on the line's value at x;
    a point measured on its own gives `value` and may carry its own interval as a vertical whisker (lo, hi)."""

    row: str
    role: str
    x: float
    cell: str | None = None
    key: str | None = None
    label: bool = False
    value: float | None = None
    lo: float | None = None
    hi: float | None = None
    interval: str = "ci95"


@dataclass(frozen=True)
class Sweep:
    rows: Sequence[str]
    x_unit: str
    y_unit: str
    lines: Sequence[Line]
    kind: str = "models"
    header: str = ""  # a vocabulary term naming the quantity; defaults to the y unit's quantity
    points: Sequence[Point] = ()
    rules: Sequence[Rule] = ()  # vertical, at x (a chosen layer)
    hrules: Sequence[Rule] = ()  # horizontal, at a value of the y unit (chance); Rule.x holds the value
    # grey x-ranges (x0, x1, band name; "" = [key].band): one list for every row, or {row: [...]} per row
    windows: Sequence[tuple[float, float, str]] | Mapping[str, Sequence[tuple[float, float, str]]] = ()
    xlim: tuple[float, float] | None = None
    ylim: tuple[float, float] | None = None
    xticks: Sequence[float] | None = None
    yticks: Sequence[float] | None = None
    panel_h: float | None = None  # inches per panel


# ---- distribution ------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Distribution:
    rows: Sequence[str]
    unit: str  # the x quantity
    data: Mapping  # row -> values, or (row, column) -> values when columns are given
    role: str
    kind: str = "models"
    style: str = "hist"  # hist | strip
    bins: Sequence[float] | int | None = None
    cells: Mapping = field(default_factory=dict)  # same keys as data -> registry id
    columns: Sequence[str] = ()  # condition names (vocabulary terms)
    count_unit: str | None = None  # the hist's y unit; its title names the count
    xlim: tuple[float, float] | None = None
    xticks: Sequence[float] | None = None
    median: bool = False  # a role-colour line at each median
    panel_h: float | None = None
    control: str | None = None  # for role "control": which control ([controls].names)


# ---- stack -------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Segment:
    """One part of a 100% stack: `shares` as `Series.cells` (row -> share, or a callable); `cell`/`key` templates."""

    name: str  # a vocabulary term
    role: str  # a role, or "other"
    shares: Mapping[str, object] | Callable
    _: KW_ONLY
    cell: str | None = None
    key: str | None = None


@dataclass(frozen=True)
class Stack:
    rows: Sequence[str]
    segments: Sequence[Segment]
    kind: str = "models"
    unit: str = "share"
    header: str = ""
    columns: Sequence[TextColumn] = ()  # numbers beside the bars (a segment's interval: stacks carry no whiskers)


# ---- scatter -----------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Cloud:
    name: str  # direct label (a vocabulary term); for a control, its [controls] name
    role: str  # a role, or "control"
    xy: np.ndarray | Sequence[Sequence[float]]
    cell: str | None = None
    path: bool = False  # join the points in order with a grey connector
    ends: tuple[str, str] | None = None  # words at the path's first and last point


@dataclass(frozen=True)
class ScatterPanel:
    clouds: Sequence[Cloud]
    embedding: str | None = None  # "UMAP": axes "UMAP 1"/"UMAP 2", no ticks, no cue
    units: tuple[str, str] | None = None  # (x unit, y unit) for a scatter with quantities
    header: str = ""  # a vocabulary term or template; "{name}" fields are filled from `numbers`
    numbers: Mapping[str, tuple] = field(default_factory=dict)  # name -> (value, unit, data key)


@dataclass(frozen=True)
class Scatter:
    panels: Sequence[ScatterPanel]
    panel_h: float | None = None


# ---- schematic ---------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float
    text: str = ""
    role: str | None = None
    verbatim: bool = False


@dataclass(frozen=True)
class Arrow:
    start: tuple[float, float]
    end: tuple[float, float]
    role: str | None = None
    label: str = ""  # words beside the arrow's middle, in its colour (a vocabulary term)


@dataclass(frozen=True)
class Words:
    x: float
    y: float
    parts: Sequence[tuple]  # (text, role or None) or (text, role or None, bold)
    verbatim: bool = False
    bold: bool = False  # every part bold, at the role-word size


@dataclass(frozen=True)
class Mark:
    """A single dot in a schematic (the key figure's swatches)."""

    x: float
    y: float
    role: str
    hollow: bool = False
    interval: tuple[float, float] | None = None  # whisker half-widths in inches (left, right)


@dataclass(frozen=True)
class Schematic:
    """Boxes, arrows and coloured words, positioned in inches from the block's top-left corner."""

    height: float
    elements: Sequence[Box | Arrow | Words | Mark]


# ---- example card ------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CardRow:
    label: str  # the reader's word (its role's word, or a vocabulary term)
    role: str  # the reader's role: its label and its answers are in that colour
    answers: Mapping[str, str]  # column -> the answer, verbatim


@dataclass(frozen=True)
class Card:
    """A real item as an image: the prompt verbatim, one row per reader with its answer under each condition, and a
    small grey note (the selection rule, the item's id). Use in a Figure with direct_labels=True."""

    # the prompt, verbatim: parts (text, role or None[, bold]) for one paragraph, or a list of such lists for several
    # (each starts a new line; a leading part such as ("Lookup:", "lookup", True) labels it)
    prompt: Sequence
    columns: Sequence[str]  # condition names (vocabulary terms), e.g. "before", "the whole change"
    rows: Sequence[CardRow]
    note: str = ""  # verbatim; may hold an item id


Block = Union[DotTable, Sweep, Distribution, Stack, Scatter, Schematic, Card]
