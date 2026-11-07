"""Distributions on synthetic data: histograms per checkpoint (rows) and prompt set (columns), and a strip per
checkpoint with its median."""

from __future__ import annotations

import numpy as np

import styles_plot as sp


def distribution(v: sp.Vocab) -> sp.Figure:
    rng = np.random.default_rng(4)
    data, cells = {}, {}
    for r in ("c1", "c2"):
        for c, name in (("one", "set one"), ("two", "set two")):
            n = 60
            bimodal = np.concatenate([rng.beta(8, 2, n // 2), rng.beta(2, 8, n // 2)])
            data[(r, name)] = bimodal * 100
            cells[(r, name)] = f"dist.{r}.{c}"
    d = sp.Distribution(["c1", "c2"], "accuracy", data, role="first", kind="checkpoints", columns=["set one", "set two"],
                        cells=cells, count_unit="prompts", bins=list(range(0, 101, 10)), xlim=(0, 100),
                        xticks=[0, 50, 100])  # fmt: skip
    return sp.Figure("distribution", v, subtitle="synthetic data").add(d)


def strip(v: sp.Vocab) -> sp.Figure:
    rng = np.random.default_rng(5)
    data = {"c1": rng.normal(0.4, 0.15, 80), "c2": rng.normal(-0.3, 0.2, 80)}
    d = sp.Distribution(["c1", "c2"], "score", data, role="probe", kind="checkpoints", style="strip", median=True,
                        cells={"c1": "strip.c1", "c2": "strip.c2"}, xlim=(-1, 1), xticks=[-1, 0, 1])  # fmt: skip
    return sp.Figure("strip", v, subtitle="synthetic data").add(d)


FIGURES = (distribution, strip)
