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


def wilson(k):
    """Accuracy k/N in % with its Wilson 95% interval: the whisker is what the key says it is."""
    p, z = k / N, 1.96
    mid = (p + z * z / (2 * N)) / (1 + z * z / N)
    half = z * np.sqrt(p * (1 - p) / N + z * z / (4 * N * N)) / (1 + z * z / N)
    return 100 * p, 100 * (mid - half), 100 * (mid + half)  # (value, lo, hi) reads as an sp.Est


# a series is a function of the row; cell and key are templates filled per row ({row}, {id}, {lane}, {role})
method = sp.Series("method", lambda m: wilson(ours[m]), cell="acc.{row}", key="acc.{row}", label=True)
control = sp.Series("control", lambda m: wilson(base[m]), control="shuffled labels", cell="acc.{row}")
col = sp.DotColumn("accuracy", "accuracy", (30, 100), (50, 75, 100), [control, method], rules=[sp.Rule(50, "chance")])
counts = sp.TextColumn("answers", "prompts", lambda m: sp.Count(ours[m], N), cell="acc.{row}", key="n.{row}")

fig = sp.Figure("first_figure", v, subtitle="synthetic data",
                title="Our method beats the shuffled-label baseline on every model",
                caption="Synthetic data. Each row is a model; whiskers are Wilson 95% intervals of k of 200; "
                        "Model 3 was run after the data.")
fig.add(sp.DotTable(models, [col, counts], kind="models"))
for target, report in sp.save_bundle(fig, HERE / "figures", targets=("post", "readme")).items():
    print(f"{target}: {report.path}")
