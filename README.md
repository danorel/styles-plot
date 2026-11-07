# styles-plot

One figure grammar shared across research projects, for matplotlib. Colour means a role; a hollow mark means post hoc;
the key is built from what was drawn; every word comes from the project's vocabulary; every number goes through its
unit's formatter; and `save` refuses a figure that breaks any of it.

**The library owns the grammar. Each project owns its vocabulary** (`plotstyle.toml`: roles, words, units, entities,
the status registry) **and its style** (palette, marks, fonts, sizes, targets, wording), all with defaults.

```python
import styles_plot as sp

v = sp.load("plotstyle.toml")
col = sp.DotColumn("accuracy drop", "drop", (0, 70), (0, 30, 60),
                   series=[sp.Series("lookup", {m: sp.Est(d[m], lo[m], hi[m], cell=f"band.{m}") for m in rows})])
fig = sp.Figure("fig01", v, title="One claim for the README", caption="What was done, for the README.")
fig.add(sp.DotTable(rows, [col]))
sp.save_bundle(fig, "figures", targets=("post", "slide", "readme"))   # strict: all or nothing
```

Figure types: dot table, sweep, distribution (histogram or strip), 100% stack, scatter (embeddings), schematic. Targets:
post, slide, readme, notebook, or your own.

```
styles-plot check figures/post --vocab plotstyle.toml   # PNGs and sidecars: size, palette, staleness, numbers
styles-plot sheet figures/post                           # contact sheets, colour and gray
styles-plot key --vocab plotstyle.toml                   # the project's grammar on one image
styles-plot palette --vocab plotstyle.toml               # colour-vision distances; pairs that may not share a figure
```

- [docs/GRAMMAR.md](docs/GRAMMAR.md): the rules and the checks.
- [docs/ADOPTING.md](docs/ADOPTING.md): writing a vocabulary, porting a script.
- [docs/DESIGN.md](docs/DESIGN.md): the design and its decisions.
- Gallery: `python examples/build_gallery.py` builds every example for every target into `gallery/` (not committed); CI builds and checks it and uploads it as the `gallery` artifact.

Install from a tag (no PyPI): `styles-plot @ git+https://github.com/danorel/styles-plot@v0.1.12`; add the `[check]`
extra only for custom palette hexes. Python ≥ 3.10, matplotlib ≥ 3.8, numpy ≥ 1.26. The public API is
`styles_plot.__all__`; modules starting with `_` are internal. MIT licence.
