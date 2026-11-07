"""What a figure shows, declared as plain data. Nothing here draws; `Figure.render` lays the blocks out for a target.

Every data mark carries a `cell`: its id in the status registry, from which the mark's fill (timing) and grey tag
(claim) are read. A printed number carries a `key`: its data key, so one key prints one string everywhere.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
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
    """A dashed grey reference line with a canonical label ("chance")."""

    x: float
    label: str = ""


# ---- dot table ---------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Series:
    role: str  # a vocabulary role, or "control"
    cells: Mapping[str, Est | Missing]
    control: str | None = None  # for role "control": which control ([controls].names)


@dataclass(frozen=True)
class DotColumn:
    header: str
    unit: str
    xlim: tuple[float, float]
    xticks: Sequence[float]
    series: Sequence[Series]
    connect: tuple[str, str] | None = None  # two series' roles joined by a grey connector in each row
    ticks: Mapping[str, float] = field(default_factory=dict)  # grey tick per row
    band: tuple[float, float] | None = None  # the grey band
    rules: Sequence[Rule] = ()
    width: float | None = None  # inches; None shares the remaining width


@dataclass(frozen=True)
class TextColumn:
    header: str
    unit: str
    cells: Mapping[str, Value]
    role: str | None = None  # colour of the printed values; None = ink


@dataclass(frozen=True)
class Gutter:
    width: float = 0.15


@dataclass(frozen=True)
class ColumnGroup:
    header: str
    columns: Sequence[DotColumn | TextColumn]


@dataclass(frozen=True)
class DotTable:
    rows: Sequence[str]
    columns: Sequence[DotColumn | TextColumn | Gutter | ColumnGroup]
    kind: str = "models"
    row_sub: Mapping[str, str] = field(default_factory=dict)  # a grey second line under a row label

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


@dataclass(frozen=True)
class Point:
    """A dot on a line at x (a cell fixed in advance, or a chosen layer)."""

    row: str
    role: str
    x: float
    cell: str | None = None
    key: str | None = None
    label: bool = False


@dataclass(frozen=True)
class Sweep:
    rows: Sequence[str]
    x_unit: str
    y_unit: str
    lines: Sequence[Line]
    kind: str = "models"
    header: str = ""  # a vocabulary term naming the quantity; defaults to the y unit's quantity
    points: Sequence[Point] = ()
    rules: Sequence[Rule] = ()
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


# ---- stack -------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Segment:
    name: str  # a vocabulary term
    role: str  # a role, or "other"
    shares: Mapping[str, Est]


@dataclass(frozen=True)
class Stack:
    rows: Sequence[str]
    segments: Sequence[Segment]
    kind: str = "models"
    unit: str = "share"
    header: str = ""


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
    header: str = ""


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


@dataclass(frozen=True)
class Words:
    x: float
    y: float
    parts: Sequence[tuple[str, str | None]]  # (text, role or None)
    verbatim: bool = False
    bold: bool = False


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


Block = Union[DotTable, Sweep, Distribution, Stack, Scatter, Schematic]
