"""An embedding scatter on synthetic data: a method's direction per layer (joined in layer order) against random
directions, in UMAP-like and PCA-like coordinates. No legend box: each cloud is named next to it."""

from __future__ import annotations

import numpy as np

import styles_plot as sp


def scatter(v: sp.Vocab) -> sp.Figure:
    rng = np.random.default_rng(6)
    t = np.linspace(0, 1, 16)
    method = np.column_stack([4 * t + rng.normal(0, 0.1, 16), np.sin(3 * t) + rng.normal(0, 0.1, 16)])
    random = rng.normal(0, 0.6, (16, 2)) + np.array([1.5, -2.0])
    panels = []
    for name, key in (("UMAP", "umap"), ("PCA", "pca")):
        panels.append(sp.ScatterPanel([
            sp.Cloud("method B", "second", method, cell=f"{key}.method", path=True, ends=("first layer", "last layer")),
            sp.Cloud("a random direction", "control", random, cell=f"{key}.random"),
        ], embedding=name))  # fmt: skip
    return sp.Figure("scatter", v, subtitle="synthetic data").add(sp.Scatter(panels, panel_h=3.0))


FIGURES = (scatter,)
