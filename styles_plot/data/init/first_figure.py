"""A first figure on synthetic data: python first_figure.py (or styles-plot build first_figure.py:FIGURES)."""

from pathlib import Path

import numpy as np

import styles_plot as sp

HERE = Path(__file__).resolve().parent
v = sp.load(HERE / "plotstyle.toml")
FIGURES = sp.FigureSet("first", v, out=HERE / "figures", targets=("post", "readme"))
models = [e.key for e in v.entities("models")]  # rows in the vocabulary's order

N, rng = 200, np.random.default_rng(0)  # synthetic data: correct answers out of N prompts per model
ours = {m: int(rng.binomial(N, 0.70 + 0.08 * i)) for i, m in enumerate(models)}
base = {m: int(rng.binomial(N, 0.5)) for m in models}


def wilson(k):  # accuracy k/N in % with its Wilson 95% interval: the whisker is what the key says it is
    p, z = k / N, 1.96
    mid = (p + z * z / (2 * N)) / (1 + z * z / N)
    half = z * np.sqrt(p * (1 - p) / N + z * z / (4 * N * N)) / (1 + z * z / N)
    return 100 * p, 100 * (mid - half), 100 * (mid + half)  # (value, lo, hi) reads as an sp.Est


@FIGURES.figure("first_figure", title="Our method beats the shuffled-label baseline on every model",
                caption="Synthetic data. Each row is a model; whiskers are Wilson 95% intervals of k of 200; "
                        "Model 3 was run after the data.", subtitle="synthetic data")  # fmt: skip
def first_figure(fig: sp.Figure) -> None:
    # a series is a function of the row; cell and key are templates ({row}, {id}, {lane}, {role}); range: [units]
    method = sp.Series("method", lambda m: wilson(ours[m]), cell="acc.{row}", key="acc.{row}", label=True)
    control = sp.Series("control", lambda m: wilson(base[m]), control="shuffled labels", cell="acc.{row}")
    col = sp.DotColumn("accuracy", "accuracy", series=[control, method], rules=[sp.Rule(50, "chance")])
    counts = sp.TextColumn("answers", "prompts", lambda m: sp.Count(ours[m], N), cell="acc.{row}", key="n.{row}")
    fig.add(sp.DotTable(models, [col, counts], kind="models"))


if __name__ == "__main__":
    for f in FIGURES.build().figures:  # each figure: all its targets, or nothing and the reason
        print(f["id"], *([f"figures/{png}" for png in f["png"].values()] if f["ok"] else [f["error"]]))
