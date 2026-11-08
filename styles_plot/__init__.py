"""styles-plot: one figure grammar shared across research projects.

The public API is exactly the names in `__all__`. Modules whose names start with an underscore are internal and may
change in any release.

    import styles_plot as sp

    v = sp.load("plotstyle.toml")
    fig = sp.Figure("fig01", v).add(sp.DotTable(rows=[...], columns=[...]))
    sp.save(fig, "figures/fig01.png", target="post")
    sp.save_bundle(fig, "figures", targets=("post", "slide", "readme"))
"""

from importlib.metadata import PackageNotFoundError, version

from styles_plot._model import (
    Arrow,
    Box,
    Card,
    CardRow,
    Cloud,
    ColumnGroup,
    Count,
    Distribution,
    DotColumn,
    DotTable,
    Est,
    Gutter,
    Lane,
    Line,
    Mark,
    Missing,
    Point,
    Rule,
    Scatter,
    ScatterPanel,
    Schematic,
    Segment,
    Series,
    Stack,
    Sweep,
    TextColumn,
    Words,
)
from styles_plot._keyfig import key_figure
from styles_plot._palette import Palette
from styles_plot._registry import Registry, RegistryError, Status
from styles_plot._registry import load as load_registry
from styles_plot._render import BuildError, Figure
from styles_plot._sheet import contact_sheets
from styles_plot._save import Problem, SaveReport, StyleError, StyleWarning, check_figure, debug, save, save_bundle
from styles_plot._theme import MarkStyle, Phrases, Sizes, Theme
from styles_plot._vocab import Entity, Format, Role, Unit, Vocab, VocabError, from_dict, load, loads

try:
    __version__ = version("styles-plot")
except PackageNotFoundError:  # pragma: no cover - a source tree without an install
    __version__ = "0+unknown"

__all__ = [
    # vocabulary and style
    "load",
    "loads",
    "from_dict",
    "Vocab",
    "VocabError",
    "Role",
    "Unit",
    "Format",
    "Entity",
    "Palette",
    "Theme",
    "Sizes",
    "MarkStyle",
    "Phrases",
    # status registry
    "load_registry",
    "Registry",
    "RegistryError",
    "Status",
    # figure
    "Figure",
    "BuildError",
    "key_figure",
    # blocks
    "DotTable",
    "DotColumn",
    "TextColumn",
    "ColumnGroup",
    "Gutter",
    "Lane",
    "Series",
    "Rule",
    "Sweep",
    "Line",
    "Point",
    "Distribution",
    "Stack",
    "Segment",
    "Scatter",
    "ScatterPanel",
    "Cloud",
    "Schematic",
    "Box",
    "Arrow",
    "Words",
    "Mark",
    "Card",
    "CardRow",
    # values
    "Est",
    "Missing",
    "Count",
    # saving and checking
    "save",
    "save_bundle",
    "check_figure",
    "debug",
    "SaveReport",
    "Problem",
    "StyleError",
    "StyleWarning",
    "contact_sheets",
]
