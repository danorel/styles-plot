"""Dot tables on synthetic data.

`dot_table` has the shape of a two-test results figure: two column groups (a band test and a one-layer test), two
readers per row joined by a grey connector, a gap column with its interval and the largest same-size control as a grey
tick, the grey band, post hoc rows, "not claimed" and "descriptive" tags, and a value without an interval. It is the
regression figure for status tags that cross lines and headers that touch.

`methods` compares one method with grey baselines on one accuracy axis, with a chance line and bootstrap SEM whiskers.
"""

from __future__ import annotations

import numpy as np

import styles_plot as sp

MODELS = ["m1", "m2", "m3", "m4", "m5"]


def _band_data():
    rng = np.random.default_rng(1)
    a_drop = {m: 40 + 5 * i + rng.normal(0, 2) for i, m in enumerate(MODELS)}
    b_drop = {m: 3 + rng.normal(0, 1.5) for m in MODELS}
    gap = {m: a_drop[m] - b_drop[m] for m in MODELS}
    ctrl = {m: 8 + 2 * i for i, m in enumerate(MODELS)}
    return a_drop, b_drop, gap, ctrl


def example_row(m: str = "m2") -> tuple[float, float, float, float]:
    """One row of the band test (alpha's drop, beta's drop, the gap, the largest control): the key figure's example."""
    a_drop, b_drop, gap, ctrl = _band_data()
    return a_drop[m], b_drop[m], gap[m], ctrl[m]


def dot_table(v: sp.Vocab) -> sp.Figure:
    b = {m: f"band.{m}" for m in MODELS}
    lyr = {m: f"layer.{m}" for m in MODELS}
    a_drop, b_drop, gap, ctrl = _band_data()
    a_share = {m: 0.45 + 0.08 * i for i, m in enumerate(MODELS)}
    b_share = {m: 0.02 + 0.03 * i for i, m in enumerate(MODELS)}

    drop = sp.DotColumn(
        "accuracy drop", "drop", (-4, 70), (0, 30, 60),
        series=[sp.Series("second", {m: sp.Est(b_drop[m], cell=b[m]) for m in MODELS}),
                sp.Series("first", {m: sp.Est(a_drop[m], cell=b[m]) for m in MODELS})],
        connect=("second", "first"),
    )  # fmt: skip
    gap_col = sp.DotColumn(
        "gap", "gap", (-4, 98), (0, 30, 60),
        series=[sp.Series("first", {m: sp.Est(gap[m], gap[m] - 4, gap[m] + 4, cell=b[m], key=f"gap.band.{m}",
                                              label=True) for m in MODELS})],
        ticks=ctrl,
    )  # fmt: skip
    blocked = sp.DotColumn(
        "switches blocked", "blocked", (-0.25, 1.0), (0, 0.5, 1),
        series=[sp.Series("second", {m: sp.Est(b_share[m], b_share[m] - 0.05, b_share[m] + 0.05, cell=lyr[m])
                                     for m in MODELS}),
                sp.Series("first", {m: sp.Est(a_share[m], a_share[m] - 0.06, a_share[m] + 0.06, cell=lyr[m])
                                    for m in MODELS})],
        connect=("second", "first"), band=(-0.1, 0.1),
    )  # fmt: skip
    layer_gap = sp.DotColumn(
        "gap", "gap_share", (-0.1, 1.1), (0, 0.5, 1),
        series=[sp.Series("first", {
            m: (sp.Est(a_share[m] - b_share[m], cell=lyr[m], key=f"gap.layer.{m}", label=True, note="no interval")
                if m == "m4" else
                sp.Est(a_share[m] - b_share[m], a_share[m] - b_share[m] - 0.07, a_share[m] - b_share[m] + 0.07,
                       cell=lyr[m], key=f"gap.layer.{m}", label=True))
            for m in MODELS})],
    )  # fmt: skip
    table = sp.DotTable(MODELS, [sp.ColumnGroup("Test A · synthetic", [drop, gap_col]), sp.Gutter(),
                                 sp.ColumnGroup("Test B · synthetic", [blocked, layer_gap])])  # fmt: skip
    return sp.Figure(
        "dot_table", v, subtitle="synthetic data",
        title="Method A loses far more than method B under the knock-out, on every model",
        caption="Synthetic data. Each row is a model; the left group is a band test, the right group a one-layer "
                "test. Hollow marks were run after the data; grey tags say which cells the text does not claim.",
    ).add(table)  # fmt: skip


def methods(v: sp.Vocab) -> sp.Figure:
    rng = np.random.default_rng(2)
    acc = {m: 52 + 6 * i + rng.normal(0, 1) for i, m in enumerate(MODELS)}
    sem = {m: 1.0 + 0.2 * i for i, m in enumerate(MODELS)}

    def est(m):
        return sp.Est(acc[m], acc[m] - sem[m], acc[m] + sem[m], cell=f"acc.{m}", key=f"acc.{m}", label=True,
                      interval="sem")  # fmt: skip

    col = sp.DotColumn(
        "accuracy", "accuracy", (40, 100), (50, 75, 100),
        series=[sp.Series("control", {m: est(m) for m in MODELS[:4]}, control="shuffled labels"),
                sp.Series("second", {"m5": est("m5")})],
        rules=[sp.Rule(50, "chance")],
    )  # fmt: skip
    counts = sp.TextColumn("answers", "prompts", {m: sp.Count(30 + i, 40, cell=f"acc.{m}", key=f"n.{m}")
                                                   for i, m in enumerate(MODELS)})  # fmt: skip
    return sp.Figure(
        "methods", v, subtitle="synthetic data",
        title="Beta on Model 5 is the most accurate; the grey baselines sit nearer chance",
        caption="Synthetic data. Each row is a model; grey dots are baselines trained on shuffled labels, the coloured "
                "dot is beta. Whiskers are ± 1 SEM (bootstrap); the right column counts correct answers of 40 prompts.",
    ).add(sp.DotTable(MODELS, [col, counts]))  # fmt: skip


FIGURES = (dot_table, methods)
