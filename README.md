# styles-plot

One figure grammar shared across research projects, for matplotlib. Colour means a role; a hollow mark means post hoc;
the key is built from what was drawn; every word comes from the project's vocabulary; every number goes through its
unit's formatter; and `save` refuses a figure that breaks any of it.

**The library owns the grammar. Each project owns its vocabulary** (`plotstyle.toml`: roles, words, units, entities,
the status registry) **and its style** (palette, marks, fonts, sizes, targets, wording), all with defaults.

## What you get

![A dot table: two column groups of models, alpha and beta joined by grey connectors](examples/figures/readme/dot_table.png)

Colour is a role; hollow = post hoc; grey tags say what the text does not claim; the key lists only what is drawn.

![The key figure: each role's colour with its word and meaning, the grey control, the hollow mark, the whisker](examples/figures/readme/key.png)

The project's grammar on one image (`styles-plot key`).

![A sweep: a rank over layers for two checkpoints, with an interquartile band and a picked layer](examples/figures/readme/sweep.png)

A quantity over layers; shading names its interval; the picked layer is a dot that keeps its status.

![A methods table: grey baselines, one method in colour, a chance line, counts of correct answers](examples/figures/readme/methods.png)

Grey is a control and nothing else; a chance line; counts print as "k of n".

## Quick start

```
pip install "styles-plot @ git+https://github.com/danorel/styles-plot@v0.2.2"
styles-plot init                 # plotstyle.toml, status.csv, first_figure.py
python first_figure.py           # figures/post/first_figure.png, figures/readme/first_figure.png (strict)
styles-plot check figures/post --vocab plotstyle.toml
```

`first_figure.py`, as `init` writes it:

<!-- first-figure:start -->
```python
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
```
<!-- first-figure:end -->

## What strict mode refuses

A header word missing from the vocabulary and a cell missing from the registry ([examples/strict/refused.py](examples/strict/refused.py)):

<!-- refused:start -->
```
2 problem(s), nothing written:
  refused: SP203 cell 'acc.m2' is not in the registry for figure 'refused' → add a row to the registry: refused,acc.m2,<timing>,<claim>,,,
  refused: SP401 header 'recall' is not in the vocabulary → add "recall" to [terms] canonical in plotstyle.toml: canonical = [..., "recall"]
see them drawn: sp.debug(fig, "post")
```
<!-- refused:end -->

To migrate an old script, save with `mode="compat"`: it writes the figure, warns, and records each problem in the
sidecar until you fix them.

## Make it yours

| what you change | where | how |
|---|---|---|
| what each colour means, and its word | `[roles]` in `plotstyle.toml` | [ADOPTING.md §2](docs/ADOPTING.md#2-write-the-vocabulary-plotstyletoml) |
| axis titles, cues, number formats | `[units]` | [ADOPTING.md §2](docs/ADOPTING.md#2-write-the-vocabulary-plotstyletoml) |
| every other word a figure prints | `[terms]` | [ADOPTING.md §2](docs/ADOPTING.md#2-write-the-vocabulary-plotstyletoml) |
| the rows and their order | `[[entities.<kind>]]` | [ADOPTING.md §2](docs/ADOPTING.md#2-write-the-vocabulary-plotstyletoml) |
| hollow or filled, claimed or not | `status.csv` | [ADOPTING.md §3](docs/ADOPTING.md#3-write-the-status-registry) |

## Figure types

- **Dot table**: estimates per entity and condition, with intervals, connectors, grey ticks and text columns.
- **Sweep**: a quantity over depth, stacked per entity, with interval bands and points.
- **Distribution**: histograms or strips per entity and condition.
- **Stack**: 100% splits per entity.
- **Scatter**: embeddings, or two quantities, with named clouds.
- **Schematic** and **Card**: boxes, arrows and coloured words; a real item's prompt and answers.
- **Your own block** (experimental): drawn with the library's primitives and checked like the rest
  ([ADOPTING.md](docs/ADOPTING.md#a-figure-the-library-cant-draw), [example](examples/blocks/custom.py)).

The full table is in [ADOPTING.md](docs/ADOPTING.md#figure-types).

## Commands

```
styles-plot init [DIR]                                  # a starter vocabulary, registry and figure
styles-plot check figures/post --vocab plotstyle.toml   # PNGs and sidecars: size, palette, staleness, numbers
styles-plot sheet figures/post                          # contact sheets, colour and gray
styles-plot key --vocab plotstyle.toml                  # the project's grammar on one image
styles-plot palette --vocab plotstyle.toml              # colour-vision distances; pairs that may not share a figure
styles-plot todo figures                                # what the last saves left to fix: words, cells, the rest
styles-plot vocab lint --vocab plotstyle.toml           # canonical terms written two ways
styles-plot build figures.py:FIGURES --jobs 8           # a figure set: every figure, all targets or nothing
```

## Rebuild the examples

- `make gallery`: every example for every target into `gallery/` (not committed), with contact sheets; the examples
  are one figure set (`styles-plot build examples/gallery.py:GALLERY --jobs 8`).
- `make readme-images`: the four README images into `examples/figures/`.
- `make readme`: the generated README blocks.
- CI builds and checks the full gallery on every push to `main` and every pull request, and uploads it as the
  `gallery` artifact.

## Docs, install, licence

- [docs/GRAMMAR.md](docs/GRAMMAR.md): the rules and the checks.
- [docs/ADOPTING.md](docs/ADOPTING.md): writing a vocabulary, porting a script.
- [docs/DESIGN.md](docs/DESIGN.md): the design and its decisions ([the stage-1 design](docs/archive/DESIGN-stage-1.md), archived).
- [CHANGELOG.md](CHANGELOG.md): each release, with migration notes.

Install from a tag (no PyPI): `styles-plot @ git+https://github.com/danorel/styles-plot@v0.2.2`; add the `[check]`
extra only for custom palette hexes. Python ≥ 3.10, matplotlib ≥ 3.8, numpy ≥ 1.26. The public API is
`styles_plot.__all__`; modules starting with `_` are internal. MIT licence ([LICENSE](LICENSE)).
