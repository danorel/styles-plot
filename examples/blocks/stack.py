"""A 100% stack on synthetic data: each model's answers split into correct, wrong and no answer."""

from __future__ import annotations

import styles_plot as sp

SHARES = {"m1": (0.62, 0.30), "m2": (0.48, 0.41), "m3": (0.71, 0.18)}


def stack(v: sp.Vocab) -> sp.Figure:
    segs = []
    for i, (name, role, cell) in enumerate((("correct", "first", "correct"), ("wrong", "second", "wrong"),
                                            ("no answer", "other", "none"))):  # fmt: skip
        shares = {}
        for m, (c, w) in SHARES.items():
            value = (c, w, round(1 - c - w, 10))[i]
            shares[m] = sp.Est(value, cell=f"{cell}.{m}", key=f"{cell}.{m}", label=True)
        segs.append(sp.Segment(name, role, shares))
    return sp.Figure("stack", v, subtitle="synthetic data").add(sp.Stack(list(SHARES), segs, header="answers"))


FIGURES = (stack,)
