"""A first figure on synthetic data. Replace the data with yours and register each cell in status.csv."""

from pathlib import Path

import numpy as np

import styles_plot as sp

HERE = Path(__file__).resolve().parent
v = sp.load(HERE / "plotstyle.toml")
models = [e.key for e in v.entities("models")]  # rows in the vocabulary's order

rng = np.random.default_rng(0)  # synthetic data
ours = {m: 72 + 8 * i + rng.normal(0, 2) for i, m in enumerate(models)}
base = {m: 56 + rng.normal(0, 3) for m in models}
half = {m: 3 + rng.uniform(0, 2) for m in models}  # half the width of a 95% interval
right = {m: round(ours[m] / 100 * 40) for m in models}  # correct answers out of 40 prompts


def est(acc, m, key=None):
    return sp.Est(acc[m], acc[m] - half[m], acc[m] + half[m], cell=f"acc.{m}", key=key, label=key is not None)


col = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 75, 100),
                   series=[sp.Series("control", {m: est(base, m) for m in models}, control="shuffled labels"),
                           sp.Series("method", {m: est(ours, m, f"acc.{m}") for m in models})],
                   rules=[sp.Rule(50, "chance")])  # fmt: skip
counts = sp.TextColumn("answers", "prompts", {m: sp.Count(right[m], 40, cell=f"acc.{m}", key=f"n.{m}") for m in models})

fig = sp.Figure("first_figure", v, subtitle="synthetic data",
                title="Our method beats the shuffled-label baseline on every model",
                caption="Synthetic data. Each row is a model; whiskers are 95% intervals; Model 3 was run after the data.")
fig.add(sp.DotTable(models, [col, counts], kind="models"))
for target, report in sp.save_bundle(fig, HERE / "figures", targets=("post", "readme")).items():
    print(f"{target}: {report.path}")
