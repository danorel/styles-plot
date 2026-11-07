"""A schematic: boxes, arrows, coloured words and verbatim prompt text. It uses direct labels, so every coloured element
has its word right beside it, and it is exempt from the colour-vision floors."""

from __future__ import annotations

import styles_plot as sp


def schematic(v: sp.Vocab) -> sp.Figure:
    el = [
        sp.Box(0.3, 0.5, 2.2, 0.7, "The capital of France is", verbatim=True),
        sp.Arrow((2.55, 0.85), (3.25, 0.85)),
        sp.Box(3.3, 0.5, 1.5, 0.7, "model", role="first"),
        sp.Arrow((4.85, 0.85), (5.55, 0.85), role="swap"),
        sp.Words(4.9, 0.6, [("swap", "swap")]),
        sp.Box(5.6, 0.5, 1.6, 0.7, "output"),
        sp.Words(0.3, 0.25, [("input", None)]),
        sp.Words(3.3, 1.45, [("method A", "first")], bold=True),
    ]
    return sp.Figure("schematic", v, subtitle="synthetic data", direct_labels=True).add(sp.Schematic(1.8, el))


FIGURES = (schematic,)
