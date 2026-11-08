"""A block the library does not ship, written in the project: a scorecard of one model.

Each row is one quantity on its own scale, so each row is its own panel with its unit's axis title and cue (two
quantities on different scales are two panels, never a twin axis). A dot table cannot draw this: its rows are entities
and a column has one unit. The block uses only the public primitives (`sp.Canvas`, `Panel.dot`, `Panel.rule`,
`Canvas.word`); its key line is read from what it draws.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import styles_plot as sp

ROWS = (  # (header, unit, xlim, xticks, chance)
    ("accuracy", "accuracy", (40, 100), (50, 75, 100), 50),
    ("gap", "lift", (-10, 60), (0, 25, 50), None),  # beta − its shuffled-label baseline
    ("rank", "rank", (10, 10000), None, None),
)


@dataclass(frozen=True)
class Scorecard:
    """One model's quantities, one panel each; `values[header] = (method Est, control Est or None)`."""

    role: str
    control: str
    values: dict

    def plan(self, ctx: sp.BlockContext, width: float) -> sp.Plan:
        x0, w = ctx.label_width or 1.4, width - (ctx.label_width or 1.4) - 0.6
        word_h, rule_h, box = ctx.line_height("role_word"), ctx.line_height("tag"), 0.34
        rows = [(r, rule_h + box + ctx.axis_height(r[1], w) + 0.1) for r in ROWS]

        def draw(cv: sp.Canvas) -> None:
            cv.word(x0, word_h / 2 + 0.05, ctx.role(self.role).word, role=self.role, size="role_word", weight="bold")
            y = word_h + 0.1
            for (header, unit, xlim, xticks, chance), h in rows:
                cv.word(0.1, y + rule_h + box / 2, header, size="label", weight="bold")
                p = cv.panel(x0, y + rule_h, w, box, unit, xlim, xticks)
                if chance is not None:
                    p.rule(chance, "chance")
                method, control = self.values[header]
                if control is not None:
                    p.dot(box / 2, control, "control", control=self.control)
                p.dot(box / 2, method, self.role)
                y += h

        return sp.Plan(word_h + 0.1 + sum(h for _r, h in rows), draw)


def custom(v: sp.Vocab) -> sp.Figure:
    rng = np.random.default_rng(5)
    acc, base = 78 + rng.normal(0, 1), 55 + rng.normal(0, 1)
    gap = acc - base
    values = {
        "accuracy": (sp.Est(acc, acc - 3, acc + 3, cell="score.acc", key="score.acc", label=True),
                     sp.Est(base, base - 3, base + 3, cell="score.acc")),
        "gap": (sp.Est(gap, gap - 5, gap + 5, cell="score.gap", key="score.gap", label=True), None),
        "rank": (sp.Est(140, 90, 230, cell="score.rank", key="score.rank", label=True), None),
    }
    return sp.Figure(
        "custom", v, subtitle="synthetic data",
        title="Beta on Model 2: above chance, a clear gap, and a low rank",
        caption="Synthetic data. One model, one row per quantity, each on its own scale. Whiskers are 95% intervals; "
                "the rank was read at a layer picked after the data, so its dot is hollow.",
    ).add(Scorecard("second", "shuffled labels", values))  # fmt: skip


FIGURES = (custom,)
