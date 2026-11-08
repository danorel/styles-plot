"""Every example as one figure set, saved strict for every target into gallery/ (not committed):

    styles-plot build examples/gallery.py:GALLERY --jobs 8
    python examples/build_gallery.py        the same, then the contact sheets (make gallery)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import styles_plot as sp

HERE = Path(__file__).resolve().parent
EXAMPLES = ("dot_table", "sweep", "distribution", "stack", "scatter", "schematic", "card", "custom")
V = sp.load(HERE / "plotstyle.toml")
GALLERY = sp.FigureSet("gallery", V, out=HERE.parent / "gallery", targets=("post", "slide", "readme"))


def _module(name: str):
    spec = importlib.util.spec_from_file_location(f"examples_{name}", HERE / "blocks" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # a dataclass in the module looks itself up here
    spec.loader.exec_module(mod)
    return mod


for _name in EXAMPLES:  # each example module builds whole figures from the vocabulary: register them as they are
    for _make in _module(_name).FIGURES:
        GALLERY.figure(_make.__name__)(lambda fig, make=_make: make(fig.vocab))


def key(v: sp.Vocab) -> sp.Figure:
    """The key figure, with one example row from the dot-table example's data, read aloud."""
    dt = _module("dot_table")
    m, (a, b, gap, ctrl) = "m2", dt.example_row()
    col = sp.DotColumn("accuracy drop", "drop", (-4, 70), (0, 30, 60),
                       series=[sp.Series("second", {m: sp.Est(b, cell="band.m2")}),
                               sp.Series("first", {m: sp.Est(a, cell="band.m2")})],
                       connect=("second", "first"), ticks={m: ctrl})  # fmt: skip
    gap_col = sp.DotColumn(dt.GAP, "gap", (-4, 98), (0, 30, 60),
                           series=[sp.Series("neutral", {m: sp.Est(gap, gap - 4, gap + 4, cell="band.m2",
                                                                   key="gap.band.m2", label=True)}, word=dt.GAP)])  # fmt: skip
    text = (f"read: on {v.entity('models', m).name}, the knock-out drops alpha {{a}} points and beta {{b}}; the gap "
            "is {gap}, the largest same-size control's {ctrl}")  # fmt: skip
    numbers = {"a": (a, "drop", "drop.alpha.m2"), "b": (b, "drop", "drop.beta.m2"), "gap": (gap, "gap", "gap.band.m2"),
               "ctrl": (ctrl, "gap", "ctrl.band.m2")}  # fmt: skip
    return sp.key_figure(v, example=sp.DotTable([m], [col, gap_col]), read_aloud=text, numbers=numbers)


# the key figure belongs to a reading page; on a slide it does not fit 6.5 in
GALLERY.figure("key", targets=("post", "readme"))(lambda fig: key(fig.vocab))
