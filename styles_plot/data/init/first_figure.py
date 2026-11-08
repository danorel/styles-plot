"""A first figure on synthetic data. Replace the data with yours and register each cell in status.csv."""

from pathlib import Path

import numpy as np

import styles_plot as sp

HERE = Path(__file__).resolve().parent
v = sp.load(HERE / "plotstyle.toml")
models = [e.key for e in v.entities("models")]  # rows in the vocabulary's order

N = 200  # prompts per model
rng = np.random.default_rng(0)  # synthetic data: correct answers out of N
ours = {m: int(rng.binomial(N, 0.70 + 0.08 * i)) for i, m in enumerate(models)}
base = {m: int(rng.binomial(N, 0.5)) for m in models}


def est(k, m, key=None):
    """Accuracy k/n in % with its Wilson 95% interval: the whisker is what the key says it is."""
    p, z = k / N, 1.96
    mid = (p + z * z / (2 * N)) / (1 + z * z / N)
    half = z * np.sqrt(p * (1 - p) / N + z * z / (4 * N * N)) / (1 + z * z / N)
    return sp.Est(100 * p, 100 * (mid - half), 100 * (mid + half), cell=f"acc.{m}", key=key, label=key is not None)


col = sp.DotColumn("accuracy", "accuracy", (30, 100), (50, 75, 100),
                   series=[sp.Series("control", {m: est(base[m], m) for m in models}, control="shuffled labels"),
                           sp.Series("method", {m: est(ours[m], m, f"acc.{m}") for m in models})],
                   rules=[sp.Rule(50, "chance")])  # fmt: skip
counts = sp.TextColumn("answers", "prompts", {m: sp.Count(ours[m], N, cell=f"acc.{m}", key=f"n.{m}") for m in models})

fig = sp.Figure("first_figure", v, subtitle="synthetic data",
                title="Our method beats the shuffled-label baseline on every model",
                caption="Synthetic data. Each row is a model; whiskers are Wilson 95% intervals of k of 200; "
                        "Model 3 was run after the data.")
fig.add(sp.DotTable(models, [col, counts], kind="models"))
for target, report in sp.save_bundle(fig, HERE / "figures", targets=("post", "readme")).items():
    print(f"{target}: {report.path}")
