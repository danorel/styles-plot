"""A sweep on synthetic data: a rank over layers for two checkpoints, median with an interquartile band, log scale
(lower is easier, said in the axis title), and the layer picked from this sweep marked post hoc."""

from __future__ import annotations

import numpy as np

import styles_plot as sp

LAYERS = list(range(0, 25))


def sweep(v: sp.Vocab) -> sp.Figure:
    rng = np.random.default_rng(3)
    lines, points = [], []
    for k, row in enumerate(("c1", "c2")):
        base = 3000 * np.exp(-np.array(LAYERS) / (5 + k)) + 80 + 40 * k
        med = base * np.exp(rng.normal(0, 0.15, len(LAYERS)))
        lines.append(sp.Line(row, "second", LAYERS, list(med), cell=f"line.{row}",
                             band=(list(med / 2.2), list(med * 2.2)), interval="iqr"))  # fmt: skip
        points.append(sp.Point(row, "second", 11, cell=f"pick.{row}", key=f"rank.l11.{row}", label=True))
    s = sp.Sweep(["c1", "c2"], "layer", "rank", lines, kind="checkpoints", header="rank", points=points,
                 rules=[sp.Rule(11, "layer 11")], xticks=[0, 5, 10, 15, 20])  # fmt: skip
    return sp.Figure(
        "sweep", v, subtitle="synthetic data",
        title="The target word's rank falls with depth on both checkpoints",
        caption="Synthetic data. Each panel is a checkpoint; the line is the median rank over prompts and the shading "
                "its interquartile range. Layer 11 was picked from this sweep, so its dot is hollow.",
    ).add(s)  # fmt: skip


FIGURES = (sweep,)
