# Adopting styles-plot in a project

## 1. Install, pinned to a tag

Start with `styles-plot init` (once installed as below): it writes a starter `plotstyle.toml`, `status.csv` and `first_figure.py` that passes
strict; run it, then rename the roles, units and entities and replace the synthetic data with yours. The sections below
are the hand-written route and explain every table the starter uses.

```
# uv / pyproject.toml
styles-plot @ git+https://github.com/danorel/styles-plot@v0.1.15
# pip / requirements.txt
styles-plot @ git+https://github.com/danorel/styles-plot@v0.1.15
```

Add the `[check]` extra (`styles-plot[check] @ git+…`) only if you change palette hexes: the colour-vision distances of
the default slots ship with the library; custom hexes are computed with colorspacious.

## 2. Write the vocabulary: `plotstyle.toml`

Everything that names a concept of your project, and every style choice you change, lives here. Start from
[`examples/plotstyle.toml`](../examples/plotstyle.toml). The tables:

| table | what | required |
|---|---|---|
| `[project]` | `name` | yes |
| `[roles.<name>]` | `slot` (a palette slot), `word` (printed above the first row), `meaning` (on the key figure) | for every coloured thing |
| `[controls]` | `names`: the grey things, as printed in "grey: …" | if you draw controls |
| `[key]` | `tick`, `band`: what the grey tick and the grey band mean | if you draw them |
| `[intervals]` | `<kind> = "<phrase>"`: what a whisker or shading means ("95% interval" is built in as `ci95`) | for other kinds |
| `[formats.<name>]` | `decimals`, `suffix`, `style`; defaults: accuracy 0, points 1, share 2, ratio 2, z 0, count "k of n" | to override |
| `[units.<name>]` | `title` (axis title with the unit), `quantity` (for the cue), `format`, `scale`, `cue` | for every axis |
| `[terms]` | `canonical` words, `templates` (`{num}`, `{entity}`, `{count}`), `missing` words, `not_claimed` reasons, `[[terms.banned]]` | yes |
| `[[entities.<kind>]]` | ordered rows: `key`, `name`, optional `id` | for every row kind |
| `[registry]` | `path` to the status CSV, relative to the toml | for publishable figures |
| `[palette]` | `slots` (change or add hexes), `chrome`, `colour_vision` floors | optional |
| `[style]` | `font` | optional |
| `[targets.<name>]` | any target field (`width_in`, `dpi`, `height_in`, `aspect`, `min_pt`, `sizes`, `title`, `caption`…); a new name is a new target | optional |
| `[marks]` | marker, dot size, line widths, shading alpha | optional |
| `[phrases]` | the key's wording, status tags, cues (for another language) | optional |

`sp.load` fails on a mistake with the table and key at fault. Configuring in Python instead: `sp.from_dict({...})`,
or `dataclasses.replace(vocab, ...)` on a loaded one.

## 3. Write the status registry

One row per drawn cell; the figure id is the `Figure`'s id, the cell id is what you pass as `cell=`:

```
figure,cell,timing,claim,claim_reason,reason,source
fig01,band.q9,fixed_in_advance,claimed,,fixed before the run,notes/plan.md
fig01,band.mu,post_hoc,not_claimed,shared with the logit lens,run after the data,README Fig. 1
fig04,keep.q9,fixed_in_advance,descriptive,,a description under a fixed label,README Fig. 4
```

`timing` decides hollow vs filled; `claim` decides the grey tag; `claim_reason` must be one of `[terms].not_claimed`.

## 4. Port a script

Keep the data loading. Replace the drawing with a declaration, then save:

```python
import styles_plot as sp

v = sp.load("plotstyle.toml")
rows = [e.key for e in v.entities("methods")]            # vocabulary order, not sorted by value

def est(r):
    return sp.Est(r["avg"], r["avg"] - r["sem"], r["avg"] + r["sem"], interval="sem",
                  cell=f"direct.{r['key']}", key=f"direct.{r['key']}.avg", label=True)

col = sp.DotColumn("auditor accuracy", "accuracy", (40, 100), (50, 75, 100),
                   series=[sp.Series("method", {"ours": est(data["ours"])}),
                           sp.Series("control", {k: est(data[k]) for k in rows if k != "ours"},
                                     control="the paper's baselines")],
                   rules=[sp.Rule(50, "chance")])
fig = sp.Figure("reproduction_direct", v, title="…one claim…", caption="…what was done, n, sources…")
fig.add(sp.DotTable(rows, [col], kind="methods"))
sp.save_bundle(fig, "figures", targets=("post", "slide", "readme"))
```

- Every number comes from your data by code; `key=` names it so `styles-plot check` can tell when one key prints two
  strings across figures.
- A rule label with a number is a template: `sp.Rule(15, "bar fixed in advance: {}", unit="points", key="bar")`.
  The key figure's sentence likewise: `sp.key_figure(v, example=..., read_aloud="… drops {a} points …",
  numbers={"a": (value, "points", "ko.q27.drop")})`.
- A lane named by its condition rather than its role: `sp.Series("recall", cells, word="knock-out")`.
- Start a migration with `mode="compat"`: it writes the figure, warns, and records each problem in the sidecar. Fix
  them, then drop `compat`.
- `fig.render("notebook")` gives a matplotlib figure for a quick look; a notebook PNG is never publishable.

## 5. Check and review

A figure set can keep its folder clean for GitHub: `[output] sidecar_dir = "_meta"` in plotstyle.toml and
`sp.save(fig, "figures/writeup/main/fig01.png", "post", root="figures/writeup")` put the sidecar at
`figures/writeup/_meta/main/fig01.styles.json`; contact sheets go to `_sheets/` with `sheet -o`.


```
styles-plot check figures/post --vocab plotstyle.toml    # size, palette, staleness, one key one string
styles-plot sheet figures/post                            # contact_sheet.png and contact_sheet_gray.png
styles-plot key --vocab plotstyle.toml -o figures/post/key.png
styles-plot palette --vocab plotstyle.toml                # which of your roles may not share a figure
```

## Figure types

| type | for | rows | notes |
|---|---|---|---|
| `DotTable` | estimates per entity and condition | entities | `DotColumn` panels, `TextColumn` numbers, `ColumnGroup`, `Gutter` |
| `Sweep` | a quantity over depth | entities, stacked | lines with optional interval bands; `Point`s on lines |
| `Distribution` | histograms or strips | entities, stacked; conditions as columns | `count_unit` names a histogram's counts |
| `Stack` | 100% splits | entities | at most 4 segments, each named in words |
| `Scatter` | embeddings, or two quantities | panels side by side | clouds named next to them; controls grey |
| `Schematic` | boxes, arrows, coloured words | — | `direct_labels=True` for a figure of schematics and cards |
| `Card` | a real item: prompt, answers per condition, a note | readers | `direct_labels=True`; words verbatim |
