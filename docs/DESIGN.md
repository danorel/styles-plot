# styles-plot: design (v0.1)

## Decisions taken after stage 1 (7 Nov)

This section overrides the rest of the document where they differ; v0.1 implements it.

- **Registry**: two columns, `timing` (fixed_in_advance | post_hoc; hollow) and `claim` (claimed | descriptive |
  not_claimed, with `claim_reason`; the grey tag). Only this schema loads; there is no older format.
- **Versioning** is the package version alone; neither the vocabulary nor the sidecar carries a schema number.
- **Status** comes from the registry by cell id only; a data mark without a cell id fails in strict mode; only the
  notebook target may draw without a registry.
- **Colour vision**: the nine default hexes stay; the floors apply per figure; the six failing pairs are listed in
  GRAMMAR.md. A schematic-only figure may set `direct_labels=True`.
- **Customisable style**: every hex (and extra slots), chrome, colour-vision floors, font, targets, marks and the
  library's wording are parameters with defaults, set in `plotstyle.toml` or in Python. The rules of meaning are not.
- **Cues**: "→ more <q>" under x axes, "↑ more <q>" beside a sweep's value axis; the arrow never means "better";
  "lower is better" and "(log scale)" go in the axis title.
- **Intervals**: kinds named in the vocabulary and in the key ("whiskers: …", "shading: …"); interval bands on lines
  in the role colour at one alpha from the theme.
- **Bars** only in 100% stacks and histograms; no violins in v0.1. Embedding axes "UMAP 1/2", no ticks, no cue.
- **Composite figures** are one matplotlib figure (subfigures); every check runs on the whole figure.
- **Targets**: post 8.0 in at 200 dpi; slide 12.3 × 5.3 in at 200 dpi; readme 11 in wide at 160 dpi with a title above
  and a caption under; notebook. `save_bundle` writes one figure for several targets, all or nothing.
- **Public API** is `styles_plot.__all__`; every other module is internal (underscore names).
- **Packaging**: tomli on Python < 3.11; CI on 3.10–3.13 × numpy 1.26/2.x × matplotlib 3.8/latest.

---

Status of the rest of this document: the stage-1 draft, kept for the audit and the mappings. This document is the stage-1 deliverable: an audit of
the two first consumers, the API sketch, a draft vocabulary file for each consumer, one current figure from each
mapped onto the API, and what is extracted from the seed code and what stays in the projects. Section 11 lists what
the grammar cannot yet express and Section 12 the decisions that need an answer before v0.1.

Contents

1. Audit: what exists today
2. Colour vision of the default slots
3. Principles
4. Package layout
5. Vocabulary file (`plotstyle.toml`) and status registry
6. API sketch
7. Checks
8. Sidecar metadata and the CLI
9. Draft vocabularies for the two consumers
10. Two current figures mapped onto the API
11. What the grammar cannot express yet
12. Decisions needed
13. Extraction map: what moves, what stays
14. Plan for v0.1
15. Appendix: full colour-vision table

---

## 1. Audit: what exists today

### 1.1 bridge-jspace

Two layers of code exist, in two states.

**Committed, branch `writeup-figures`** (the seed named in the brief):

| file | lines | what it is | generic? |
|---|---:|---|---|
| `figkit/dottable.py` | 320 | the dot-table renderer: `Row`, `Col`, `Table`, marks (`dot`, `connector`, `band`, `vrule`, `head_label`, `rich`) | yes, but driven by module globals (`FS`, `HOLLOW`, `BEFORE_SAVE`, `MIN_ROW_H`, `VALUE_GAP`) that a target patches in place |
| `figkit/lint.py` | 265 | `table_problems` (rotation, overlap, off-figure, min pt, legend, marker, hatch, palette, unlabelled segment, axis title, cue), `crossings` (text over lines or marks), `png_problems` (width, aspect, white) | yes, except `BANNED`, `MODELISH`, `TABLE_NAMES`, `LOSS_WORDS` (project words) |
| `figkit/render.py` + `spec.py` | 214 + 112 | declarative v1 specs (`Bars`, `Multiples`, `Stacked`, `Curves`, `Image`) drawn with a `Theme` | partly: `Bars` and `Multiples` draw bars, which grammar C no longer allows; `Stacked` and `Curves` carry over |
| `figkit/theme.py` | 43 | sizes, fonts, dpi per target, **plus its own `colors` dict** | sizes yes; colours are dropped |
| `palette.py` | 49 | `ROLE`, `SHADE`, chrome greys, `MODELS` | slots yes; `MODELS` is vocabulary |
| `scripts/check_style.py` | 97 | PNG pixel check: saturated pixels must sit on a palette colour or its tint toward white | yes (README scanning stays in the project) |
| `scripts/check_figure_terms.py` | 494 | retired-term regexes over drawn texts and captions | generic half: harvesting texts by intercepting `savefig`, the banned-pattern runner, run-id and UTC-stamp detectors, per-figure verbatim exemptions |
| `build.page_sheet` | 20 | contact sheet at a page width | yes |

The two palettes disagree as the brief says: `theme.py` has control `#BDBDBD` and black whiskers; `palette.py` has
control `#A8A8A8` and same-colour whiskers. The library keeps the second.

**Uncommitted, in the working tree on branch `figure-style-v2`** (not mentioned in the brief, found during the audit):

| file | state | what it is |
|---|---|---|
| `figkit/grammar.py` | new, 273 lines | grammar v2: tagged marks (`mark`, `tick`, `band`, `rule`, `connector`, `role_word`), key built from what was drawn, `num` by unit with a number log, and `check` for meaning checks 1 to 6 |
| `figkit/terms.py` | new, 160 lines | the project's word list: units, cue quantities, key phrases, status tags, missing-cell words, banned variants, regex templates |
| `figkit/colour_vision.py` | new, 76 lines | CVD simulation (colorspacious, Machado 2009, severity 100) and a CIEDE2000 implementation |
| `figkit/writeup_v2.py` | new, 444 lines | the five pilot figures and `key.png` in grammar v2 |
| `scripts/status_registry.py`, `data/figures/status.csv` | new | the registry (101 rows), derived from the figures' existing rules, with a `DISAGREEMENTS` list |
| `docs/shared/figure_style.md` | modified | grammar v2, sections A to I (this is the rule set the library restates) |
| `palette.py`, `dottable.py`, `tables.py`, five pilot PNGs, `pyproject.toml`, `uv.lock` | modified | v2 palette (shades removed), key-as-callable, v2 build hook, colorspacious added |

This is the closest prior art: it already implements most of what the brief asks of the library, inside the project.
The library is extracted from **both** layers: layout from `writeup-figures`, meaning from the working tree. It is
also at risk: none of it is committed. Stage 3 adopts the library on the same branch name (Decision 1).

Two defects in that prior art shape the design:

- **Status tags collide with marks.** In the working-tree `fig01_main_split.png`, "not claimed: shared with the logit
  lens" runs through the "59.9" label and two markers, and "not claimed: gone when scored by probability" runs into the
  next panel. The tag is placed on the row's grey second line, which spans all columns. The library gives status tags
  a reserved line inside the cell group they belong to and checks that they fit (Section 6.3).
- **Composite figures are pasted PNGs.** `writeup_v2._stack` renders each table to a temporary PNG and pastes them with
  PIL, so no check ever sees the composite figure, and the key's "drawn" ledger is a module global shared across the
  parts. The library composes blocks in one matplotlib figure (Section 6.2).

The global-state pattern (`FIGURE`, `DRAWN`, `NUMBERS`, `HOLLOW`, `FS`, `BEFORE_SAVE`) is also the main thing not to
extract as is: it makes figures order-dependent and untestable in isolation.

The brief's attachment `figure_style_v2_brief.md` was not attached and is not in either repository or on disk. The pilot
list (fig01, fig04, fig09, fig12, appB_f17, key) is taken from the brief text, and it matches `writeup_v2.FIGS`.

### 1.2 esk-audit (`danorel/mats.esk-audit`)

`user_gender/plots/` holds 18 scripts, 2,217 lines. Eleven draw with matplotlib; seven only compute. A local checkout
with the data exists (the GitHub repo ignores `results/`, `*.json` and `*.png`, so a fresh clone cannot run any plot).

| script | draws now | v0.1 figure type | notes |
|---|---|---|---|
| `reproduction_bar_chart.py` (**pilot**) | horizontal bars sorted by value, ± bootstrap SEM, "ours" magenta, baselines blue-grey, dashed chance, legend | dot table: methods × accuracy | whiskers are SEM, not a 95% interval (11.1) |
| `blank_baseline_signal_chart.py` | horizontal bars: accuracy minus each method's blank baseline | dot table, unit points | |
| `attribution_controls_chart.py` | two bar panels: cosines, position gaps | dot table, two column groups; controls grey | **numbers typed into the script** (`DIRECTION_COSINES`, `POSITION_GAPS`) |
| `separability_vs_accuracy_chart.py` | two lines across two categories (direct, standard) on one % axis | dot table: rows = prompt sets, columns = the two metrics | **numbers typed into the script**; the brief's "two metrics over the same x" case. x is categorical, so a dot table rather than stacked panels |
| `layer_rank_sweep_chart.py` (**pilot**) | median rank per layer, IQR band, both checkpoints in one axes, log y, dashed line at layer 11 | sweep, rows = the two checkpoints | lower is better; log scale; the band is an IQR (11.2, 11.3) |
| `projection_separability_sweep.py` | accuracy per layer, chance line, two dotted vertical lines (layer 11, best layer) | sweep | "best layer" is chosen from the plotted data (status question) |
| `bimodal_breakdown_chart.py` | histogram per checkpoint | distribution (hist), rows = checkpoints | x in 0–1, while every other accuracy is in % |
| `bimodal_breakdown_chart_combined.py` | the same, two prompt sets side by side | distribution, rows = checkpoints, columns = prompt sets | |
| `projection_separability_chart.py` | violins by true gender, one panel per variant | distribution (strip) | violins are not a v0.1 type (11.5) |
| `projection_direct_vs_standard_chart.py` | violins, direct vs standard | distribution (strip) | has an uncommitted local edit |
| `direction_vectors_umap.py` | UMAP and PCA scatter, contrastive vs random control (`x` marker), per-point layer numbers, a trajectory line | scatter, two panels | embedding axes have no quantity (11.4) |

Colours are ad hoc: magenta `#c2185b` for "ours" and for female, blue `#1565c0` for male, blue-grey `#90a4ae` for
baselines, all at 150 dpi, with titles, suptitles and legend boxes. Under the grammar the gender colours disappear:
female and male are entities (the two fine-tuned checkpoints) or data categories, never roles, so they become rows or
small multiples in one role colour.

Python: `requirements.txt` pins numpy 1.26.4, matplotlib 3.10.3, scipy 1.15.3 and `async-timeout` (which aiohttp only
pulls on Python < 3.11), so the pinned environment is Python 3.10. The local virtualenv that has the data runs
**Python 3.13 with numpy 2.5.2**, which those pins cannot install. The library therefore supports 3.10 to 3.13 and numpy
1.26 and 2.x (CI matrix in Section 14).

bridge-jspace requires Python `>=3.12,<3.13`.

---

## 2. Colour vision of the default slots

I ran the check from the brief now, before the API, because a failing pair changes the palette. Method: simulate
deuteranopia, protanopia and tritanopia (Machado et al. 2009 at severity 100, via colorspacious 1.1.2), convert to
CIELab D65, compute CIEDE2000; also normal vision. Floors: 12 between two role colours, 8 between a role colour and
control grey. **6 of 45 pairs fail; every role colour clears the control floor.**

| pair | normal | deutan | protan | tritan | min | floor |
|---|---:|---:|---:|---:|---:|---:|
| brick–brown | 22.6 | **3.4** | **7.7** | 15.7 | 3.4 | 12 |
| violet–blue | 16.9 | **5.1** | **8.2** | 13.5 | 5.1 | 12 |
| teal–pink | 47.8 | **5.9** | 22.2 | 54.5 | 5.9 | 12 |
| teal–blue | 32.6 | 22.4 | 29.5 | **9.5** | 9.5 | 12 |
| blue–pink | 33.7 | 17.5 | **9.7** | 56.4 | 9.7 | 12 |
| brown–pink | 35.3 | 27.6 | 32.9 | **11.3** | 11.3 | 12 |

The full 45-pair table is in Section 15.

**Is there a small fix?** I searched the sRGB grid (step 4) for the colour nearest each failing slot (by CIEDE2000)
that clears every floor against the other slots, under all four visions, with a contrast on white no lower than
the original's (role words are coloured text).

| order replaced | result |
|---|---|
| blue, then brown, then pink | blue `#3A7DC9`→`#504088` (shift 25.1), brown `#8C6D46`→`#543404` (19.9), pink `#B8689A`→`#8478A4` (15.3) |
| pink, then brown, then blue | pink→`#742484` (23.8), brown→`#4C3400` (20.7), blue→`#002440` (31.5) |

No small fix exists. "Blue" has to become a dark purple to clear violet under deuteranopia and teal under tritanopia
at the same time. Nine saturated hues plus grey cannot all be pairwise distinguishable under all three dichromacies at
these floors. This is expected: the brief scopes the floor to **two role colours in one figure**, and that scope is
load-bearing.

**Recommendation: keep all nine hexes.** Enforce the floor per figure, as the brief specifies. The library ships the
precomputed pair table and documents the six pairs that **may not share a figure** (GRAMMAR.md). Where bridge-jspace
co-draws them today (a text scan of the layout modules, so approximate):

| figure | roles co-drawn | failing pair |
|---|---|---|
| `fig00_schematic`, `fig03_tools` | lens part + identity | teal–blue (tritan 9.5) |
| `figA1_agents` | lookup + identity, lens part + identity | violet–blue (deutan 5.1), teal–blue |
| `appB_f9_where` | mention + question | brown–pink (tritan 11.3) |

None of the five pilots co-draws a failing pair. The four figures above will fail strict mode when ported in the
project's steps 4–5 and need a layout answer (split panels) or a palette decision then (Decision 3).

---

## 3. Principles

1. **The library owns the grammar; a project owns its vocabulary.** No project word appears in library code, docs or
   examples. Anything that contains a project concept, even inside a "fixed" phrase, comes from the vocabulary:
   for example "within 0.10 of a random part" and "the largest same-size control" (11.6).
2. **Figures are declared, then rendered.** A figure is a tree of plain dataclasses (blocks → columns → series →
   estimates). `save(fig, path, target)` lays it out for the target, draws it, runs the checks and writes the files.
   Why: the key must be known before layout (the seed renders every table twice to find out); one declaration renders
   to post, slide and readme; and the checks read meaning from the declaration and the artist tags, not from pixels or
   module globals.
3. **Every mark carries meaning.** Each artist the library draws is tagged with `kind`, `role`, `cell` and `status`.
   Untagged artists in a role colour are a violation, so an escape hatch cannot bypass the checks.
4. **One source of truth per fact.** Colour: the role's slot. Status: the registry row for `(figure, cell)`. Words: the
   vocabulary. Number strings: the unit's formatter. Nothing is restated at a call site.
5. **No module-level mutable state.** Theme, ledger, number log and registry live on the `Figure` or the render context.
6. **matplotlib only, a few figure types done well.** No general plotting framework. A figure the six types cannot draw
   is raised (Section 11), not hacked in.

---

## 4. Package layout

```
styles_plot/
  __init__.py       public API: load, Figure, block types, Est/Missing/Count, save, fmt
  vocab.py          plotstyle.toml loader and schema validation -> Vocab (frozen)
  registry.py       status CSV loader -> Registry; schema v1 (brief) and v2 (two axes, Decision 2)
  palette.py        the 11 slots, chrome greys, the shipped colour-vision pair table
  theme.py          Theme (sizes, fonts, text levels; never a colour) and the four targets
  marks.py          tagged primitives: dot, whisker, connector, tick, band, rule, line, area, bar segment, role word
  ledger.py         what a render drew (encodings, roles, cells, numbers, texts): feeds key + checks + sidecar
  table.py          DotTable layout engine (rows × columns, groups, gutters, zebra, sub-lines)
  sweep.py  dist.py  stack.py  scatter.py  schematic.py
  key.py            role words above the first row; the key line from the ledger
  text.py           three text levels, rich (multi-colour) text, cue builder
  numbers.py        formatters per format kind; interval and count strings
  save.py           save(), render(), sidecar writer
  sheet.py          contact sheet, colour and gray
  checks/           one module per check family (Section 7); each exposes check(ctx) -> list[Problem]
  cli.py            styles-plot check | sheet | key | palette
docs/   GRAMMAR.md  ADOPTING.md  DESIGN.md
examples/  one script per figure type; synthetic data, labelled "synthetic" in the figure
gallery/   PNGs and sidecars built by CI
tests/
```

Dependencies: `matplotlib>=3.8`, `numpy>=1.26`. Pillow comes with matplotlib (a hard dependency) and is used for the
PNG checks and sheets. TOML parsing needs `tomllib` (3.11+), so 3.10 needs `tomli` (Decision 6).
Extra `[check]`: `colorspacious` (used only to regenerate and verify the shipped pair table; Section 7, check 9).

---

## 5. Vocabulary file and status registry

### 5.1 `plotstyle.toml` schema (v1)

```toml
[project]
name = "example"
schema = 1                       # vocabulary schema version; the library refuses an unknown one

# ---- roles: name -> palette slot, coloured word, one-line meaning ------------------------------------------------------
[roles.<name>]
slot = "violet"                  # one of: ink violet teal amber blue brick slate brown pink   (control/other are reserved)
word = "lookup"                  # the coloured word above the first row; defaults to the role name
meaning = "the lookup reader"    # shown on the key figure

# ---- controls: the grey things ("grey: <name>") ----------------------------------------------------------------------
[controls]
names = ["a random part", "rotated"]

# ---- definitions behind the library's fixed key phrases ----------------------------------------------------------------
[key]
tick = "the largest same-size control"      # -> "grey tick: <tick>"
band = "within 0.10 of a random part"       # -> "grey band: <band>"

[intervals]                       # interval kinds a project draws -> phrase (see 11.1; default only ci95)
ci95 = "95% interval"

# ---- number formats (defaults shown; a project may override decimals, suffix) ------------------------------------------
[formats]
accuracy = { decimals = 0 }       # "68"   (the axis title carries "(%)")
points   = { decimals = 1 }       # "42.6"
share    = { decimals = 2 }       # "0.53"
ratio    = { decimals = 2 }       # "1.07"
z        = { decimals = 0 }       # "12"
count    = { style = "k of n" }   # "18 of 30"

# ---- units: axis title, cue quantity, format, scale --------------------------------------------------------------------
[units.<name>]
title = "accuracy drop (points)" # x-axis title: the unit and its denominator
quantity = "accuracy drop"       # the cue: "→ more <quantity>"
format = "points"                # a key of [formats]
scale = "linear"                 # linear | log
cue = true                       # false only for an axis with no direction (depth, embedding): Section 11

# ---- words -----------------------------------------------------------------------------------------------------------
[terms]
canonical = ["lens part", "knock-out"]              # every header, condition and sub-row word a figure may print
templates = ["{num} items", "bar fixed in advance: {num}"]   # {num} {entity} {count} placeholders
missing = ["no run", "no interval"]                 # the only words a missing cell may print
not_claimed = ["shared with the logit lens"]        # allowed reasons in "not claimed: <reason>"

[[terms.banned]]
pattern = "KO"                   # whole word by default; regex = true for a raw pattern
use = "knock-out"

# ---- entities: ordered rows per kind ---------------------------------------------------------------------------------
[[entities.models]]
key = "qwen3.5-9b"
name = "Qwen 9B"                 # the printed row label
id = "q9"                        # optional short id for cell names

# ---- statuses and registry -------------------------------------------------------------------------------------------
[statuses]
use = ["fixed_in_advance", "post_hoc", "descriptive", "not_claimed"]   # subset of the four the grammar defines

[registry]
path = "data/figures/status.csv" # relative to the toml file
```

Validation at `load` (each failure names the file, the table and the key):
- a slot that does not exist, two roles on one slot, a role named `control` or `other`;
- a unit whose `format` is not in `[formats]`; a cue quantity that is empty while `cue = true`;
- a canonical term that matches a banned pattern;
- duplicate entity keys or names within a kind;
- a status outside the four the grammar defines (v0.1 cannot draw a fifth; Section 11.8);
- a registry path that does not exist (an error at `save`, not at `load`, so a notebook can load without one).

The library adds its own words to the allowed set: the fixed key prefixes, "○", "●", "post hoc", "descriptive",
"not claimed: …", "chance", "→ more …", the entity names and role words from the file, and numbers in the declared
formats.

### 5.2 Status registry

The brief's columns: `figure, cell, status, reason, source`. The bridge-jspace working tree already added a `tag` column,
because one cell can be **post hoc and not claimed at once** (`fig01_main_split, band.mu`: post hoc, "not claimed:
shared with the logit lens"). A single `status` column cannot say that.

Proposed schema v2 (Decision 2): split the two questions the four statuses mix.

| column | values | drives |
|---|---|---|
| `figure`, `cell` | ids | the key `(figure, cell)` |
| `timing` | `fixed_in_advance` \| `post_hoc` | hollow ↔ `post_hoc` |
| `claim` | `claimed` \| `descriptive` \| `not_claimed` | the grey tag: none, "descriptive", "not claimed: <reason>" |
| `reason` | free text (not printed) | why |
| `tag_reason` | a `terms.not_claimed` entry, when `claim = not_claimed` | the printed reason |
| `source` | free text | where the status comes from |

The loader also reads the brief's v1 schema (single `status`, optional `tag`) and maps it: `post_hoc` → timing
post hoc, claimed; `descriptive` → fixed in advance, descriptive; `not_claimed` → fixed in advance, not claimed; a v1
`tag` of "not claimed: X" sets claim. bridge-jspace's current CSV therefore loads unchanged.

---

## 6. API sketch

```python
import styles_plot as sp

v = sp.load("plotstyle.toml")                  # -> sp.Vocab
fig = sp.Figure("fig01_main_split", vocab=v)   # id = the registry's `figure` column
fig.add(block)                                 # blocks stack vertically and share one key line
report = sp.save(fig, "out/fig01_main_split.png", target="post")   # mode="strict" (default) | "compat"
mpl = fig.render(target="notebook")            # a matplotlib Figure; nothing written
```

### 6.1 Values

```python
sp.Est(value, lo=None, hi=None, *, cell, key=None, label=False, interval="ci95", note=None)
#   cell:     registry id; the status is read from the registry, never passed
#   key:      data key for the number log (required when label=True or printed in a text column)
#   label:    print the value beside the dot, in the unit's format
#   interval: an [intervals] kind; names the whisker in the key
#   note:     a missing-word for part of the estimate, e.g. note="no interval"
sp.Missing("no run")           # a whole missing cell: grey words from terms.missing
sp.Count(k, n, *, cell, key)   # printed "k of n"
```

`status=` is not a parameter (the brief says every call takes `status=`). Passing the status beside the cell id would
restate the registry at every call site, and a check comparing the two would only catch typos. The registry stays the
only source; `fig.status(cell)` reads it for code that needs it. A figure built without a registry (notebook target)
takes `Est(..., status="post_hoc")` and is never publishable. This deviation is Decision 4.

### 6.2 Figure and composition

```python
class Figure:
    def __init__(self, id: str, vocab: Vocab, *, verbatim: Sequence[str] = ()): ...
    def add(self, block: Block) -> "Figure": ...      # DotTable | Sweep | Distribution | Stack | Scatter | Schematic
    def render(self, target: str = "notebook") -> matplotlib.figure.Figure: ...
    def status(self, cell: str) -> Status: ...
```

Several blocks stack top to bottom in one matplotlib figure, with shared left label width and one key line under the
last block. This replaces pasting PNGs together.

### 6.3 Dot table

```python
sp.DotTable(
    rows: Sequence[str],                     # entity keys; must be in the vocabulary's order for that kind
    columns: Sequence[DotColumn | TextColumn | Gutter],
    *, kind: str = "models",                 # which [entities.<kind>]
    groups: Sequence[ColumnGroup] = (),      # bold headers over several columns ("Band of layers · fact passages")
    row_sub: Mapping[str, str] = {},         # grey second line under a row label (a vocabulary term)
)
sp.DotColumn(
    header: str, unit: str, xlim: tuple[float, float], xticks: Sequence[float],
    series: Sequence[Series],                # sp.Series(role, cells: Mapping[row, Est | Missing], control=None)
    *, connect: tuple[str, str] | None = None,   # grey connector between two series' dots in each row
    ticks: Mapping[str, float] = {},         # grey tick on the estimate's axis
    band: tuple[float, float] | None = None, # grey band, named by [key].band
    rules: Sequence[Rule] = (),              # dashed grey reference line; sp.Rule(x, "chance")
    width: float | None = None,              # inches; None shares the remaining width
)
sp.TextColumn(header, unit, cells: Mapping[row, Est | Count | Missing])
sp.ColumnGroup(header, columns=[...]) ; sp.Gutter()
```

A series with `role="control"` takes `control="<a [controls] name>"`. The library draws: zebra rows; bold row labels;
one coloured role word per role above the first row of each panel; dots, filled or hollow from the registry;
same-colour whiskers; the grey connector, tick, band and rules; the value label clear of every line and mark; grey
missing-cell words; the status tag. Header, axis title and cue come from `unit`.

**Status-tag placement.** A row with a "descriptive" or "not claimed: …" cell gets a reserved second line. The tag is
drawn inside the horizontal span of the cell's column group, left-aligned, and the dots of that row sit on the upper
line. If the tag is wider than its span, the layout tries in order: wrap to two lines inside the span, then shorten
the column group's neighbours' value labels to the other side; if it still does not fit, the save fails with
`SP602 status tag does not fit in its cell` rather than drawing over a mark.

### 6.4 Sweep

```python
sp.Sweep(
    rows: Sequence[str], *, kind: str,       # one panel per entity, stacked, shared x (small multiples)
    x_unit: str, y_unit: str,                # x is depth or layer (cue = false); y is the quantity
    lines: Sequence[Line],                   # sp.Line(row, role, x, y, band=(lo, hi) | None, interval="iqr")
    points: Sequence[Point] = (),            # sp.Point(row, x, cell, key=None, label=False): a dot on the line
    rules: Sequence[Rule] = (),              # vertical dashed grey (a chosen layer)
    columns: Sequence[str] = (),             # optional conditions as columns
)
```

Lines only when x is depth (grammar C). The y quantity is named by the panel header and a horizontal y-axis title.
The y cue is Decision 5.

### 6.5 Distribution, stack, scatter, schematic

```python
sp.Distribution(rows, *, kind, unit, data: Mapping[row, ArrayLike], role,
                style="hist" | "strip", bins=None, columns=(), column_data=None)
#   small multiples in entity order, shared x; hist bars in the role colour; strip = jittered dots + grey median tick

sp.Stack(rows, *, kind, segments: Sequence[Segment])   # sp.Segment(name, role | "other", shares: Mapping[row, float])
#   100% horizontal bars, at most 4 segments, each row sums to 1 (±1e-6); each segment named in words, inside the
#   bar when it fits, else in its colour above the first row

sp.Scatter(clouds: Sequence[Cloud], *, axes="embedding" | (x_unit, y_unit), path: str | None = None)
#   sp.Cloud(name, role, xy, order=None, cell=None); a direct label per cloud at its edge, no legend box;
#   path = a cloud name whose points are joined in `order` by a grey connector; embedding axes: no ticks, no cue

sp.Schematic(width, height)
    .box(x, y, w, h, text, role=None) .arrow(a, b) .words(x, y, parts=[(text, role | None)], verbatim=False)
```

### 6.6 Key, text, numbers

- **Role words**: one per role drawn in a panel, above its first row, in the role colour, bold.
- **Key line** under the last block, built from the ledger, in this order, only what is drawn:
  `grey: <controls joined by " · ">` · `grey tick: <key.tick>` · `○ post hoc` · `whiskers: <interval phrase>`
  (one entry per interval kind drawn) · `shading: <interval phrase>` (bands on lines) · `grey band: <key.band>`.
  It wraps to a second line by measured width, not by character count.
- **Text levels**: bold ink `#1A1A1A` (headers, row labels), ink (values), grey `#6B6B6B` (units, cues, key, tags,
  missing words). Sizes per level come from the target's `Theme`.
- **Cue**: `→ more <unit.quantity>` under each x-axis title whose unit has `cue = true`.
- **Numbers**: `sp.fmt(value, unit, vocab)`; U+2212 minus; never "−0.0"; intervals `[lo, hi]` at the value's
  precision; counts "k of n". Every printed number is logged as `(key, string)`.

### 6.7 Targets

| target | size | dpi | pixels | width:height | min text | checks |
|---|---|---:|---|---|---:|---|
| `post` | 8.0 in wide | 200 | 1600 wide | 1.0–2.6 | 11 pt | all, strict |
| `slide` | 12.8 × 7.2 in | 150 | 1920 × 1080 | 16:9 (±1%) | 14 pt | all, strict |
| `readme` | 8.8 in wide | 200 | 1760 wide (2× an 880 px column) | 1.0–3.0 | 11 pt | all, strict |
| `notebook` | 8.0 in wide | 100 | | any | none | meaning checks warn; layout checks off; sidecar `publishable: false` |

`post` is from the brief and the project's existing write-up target. `slide` and `readme` geometry are proposals
(Decision 7). A notebook PNG fails `styles-plot check`, so it cannot slip into a published directory.

### 6.8 save

```python
def save(fig: Figure, path: str | Path, target: str, *, mode: Literal["strict", "compat"] = "strict") -> SaveReport
```

The steps:

1. Render for the target.
2. Run every check.
3. In strict mode, any problem raises `sp.StyleError(problems)` and nothing is written, neither PNG nor sidecar. In
   compat mode, each problem is a `StyleWarning` and the files are written with the problems recorded in the sidecar.
4. Write the PNG with an opaque white background, and `<stem>.styles.json` beside it (Section 8).

The sidecar is not named `<stem>.json`, because esk-audit's scripts already write `<stem>.json` data files next to
their PNGs.

---

## 7. Checks

Each check is a function `check(ctx) -> list[Problem]`. `ctx` holds the rendered figure, the ledger, the vocabulary,
the registry and the target. A `Problem` has a code, a message and the artist or text involved. Codes are stable across
versions; a new strict check is a major version (brief, semver).

| # | check | code | reads | ported from |
|---|---|---|---|---|
| 1 | Colour by role: a tagged artist's colour equals its role's slot; no hue outside the slots, chrome greys and white | SP101, SP102 | artist tags, colours | `grammar.check`, `lint._palette` |
| 2 | One meaning per colour: a role colour only on artists tagged with that role; an untagged artist in a role colour fails; every drawn role has its role word, and every role word has a mark | SP103, SP104 | tags, text colours | `grammar.check` |
| 3 | Status: hollow ↔ registry `post_hoc`; tag text ↔ registry claim; a drawn cell absent from the registry fails | SP201–SP203 | tags, registry | `grammar.check` |
| 4 | Key completeness: every drawn encoding is named in the key, nothing named is undrawn; no legend box | SP301–SP303 | ledger, key texts | `grammar.check`, `lint` |
| 5 | Words: every text is a vocabulary term, template match, number in a declared format, entity name, role word, library phrase, or verbatim text; banned variants fail; run ids and UTC stamps fail anywhere | SP401–SP403 | all texts | `terms.allowed`, `check_figure_terms` |
| 6 | Cues: every cue matches `^→ more `; no `←` anywhere | SP404, SP405 | cue texts | `grammar.check` |
| 7 | Numbers: each logged string matches its unit's formatter; across a directory, one key never prints two strings | SP501, SP502 | number log; sidecars (CLI) | `grammar.num`, the project's test |
| 8 | Layout: text crossing a line, whisker or marker; text off the figure; overlapping texts; rotated text; under the target's minimum size; size and aspect; marker other than "o"; hatch; title or suptitle | SP601–SP610 | rendered artists | `lint.table_problems`, `lint.crossings`, `lint.png_problems` |
| 9 | Colour vision: role pairs in this figure ≥ 12, role vs control ≥ 8, under the three simulations and normal vision | SP701, SP702 | roles drawn | `colour_vision.failures` |
| 10 | Grayscale: not pass/fail; the gray contact sheet | n/a | PNGs | new |

Notes:

- **Check 9 needs no runtime dependency.** The slots are fixed, so the 55 pairs (11 slots) under four visions are
  precomputed and shipped as `palette_cvd.json`. At save time the check is a table lookup. The `[check]` extra
  (colorspacious) regenerates the table, and a CI test checks that the shipped table equals a fresh computation. The
  CIEDE2000 code is tested against the 34 reference pairs of Sharma, Wu and Dalal (2005).
- **Check 1 on PNGs** (CLI, no sidecar needed) is the pixel test from `check_style.py`: saturated pixels must lie on the
  segment from a slot to white, with 5% tolerance for anti-aliasing.
- **Check 3 again at `styles-plot check`** compares each sidecar's recorded statuses with the current registry. A
  status changed after the figure was rendered marks the figure stale.
- **Check 5 detectors** for ids are generic: UTC stamps (`\d{8}T\d{6}Z`), snake_case tokens containing a digit, and
  the project's own banned patterns. People's names are not detectable generically; a project lists them as banned
  patterns.

---

## 8. Sidecar metadata and the CLI

`<stem>.styles.json`, written by `save`:

```json
{
  "styles_plot": "0.1.0", "schema": 1,
  "vocab": {"project": "bridge-jspace", "sha256": "…"},
  "registry": {"path": "data/figures/status.csv", "sha256": "…"},
  "figure": "fig01_main_split", "target": "post", "mode": "strict", "publishable": true,
  "png": {"sha256": "…", "px": [1600, 1180], "dpi": 200},
  "roles": ["lookup", "recall"], "controls": [],
  "marks": [{"kind": "dot", "role": "lookup", "cell": "band.q9", "timing": "fixed_in_advance", "claim": "claimed",
             "hollow": false}],
  "key": ["grey tick: the largest same-size control", "○ post hoc", "whiskers: 95% interval",
          "grey band: within 0.10 of a random part"],
  "numbers": {"ko.q9.mk": "42.6"},
  "problems": []
}
```

CLI:

- `styles-plot check <dir> [--vocab plotstyle.toml]`:
  - Every PNG: size, aspect, opaque white background, pixel palette.
  - With a sidecar: PNG hash matches (no stale sidecar), not a notebook figure, registry agrees with the recorded
    statuses, the recorded problems are empty.
  - Across the directory: one data key, one string.
  - Exit code 1 on any failure; one line per problem, `path: CODE message`.
- `styles-plot sheet <dir> [--width 720] [-o DIR]` writes `contact_sheet.png` and `contact_sheet_gray.png`. Figures
  are scaled to the reading width, stacked with their file names, in name order or the order given by
  `--order file.txt`.
- `styles-plot key --vocab plotstyle.toml [-o key.png] [--target post]` draws the project's key figure: each role with
  its word and meaning, grey = control, ○ = post hoc, a whisker, the grey band, the grey tick, the missing-cell words,
  and one synthetic example row read aloud. It shows each role on its own row, so the per-figure colour-vision check
  treats it as a legend of separate swatches and skips SP701.
- `styles-plot palette [--vocab plotstyle.toml]` prints the colour-vision table. With a vocabulary, it lists the
  project's role pairs that may not share a figure.

---

## 9. Draft vocabularies for the two consumers

### 9.1 bridge-jspace

```toml
[project]
name = "bridge-jspace"
schema = 1

[roles.recall]
slot = "ink"
meaning = "the recall reader, and what it loses"

[roles.lookup]
slot = "violet"
meaning = "the lookup reader"

[roles.lens]
slot = "teal"
word = "lens part"
meaning = "the lens part: J++ directions read at a word"

[roles.address]
slot = "amber"
meaning = "the address and the position route"

[roles.identity]
slot = "blue"
meaning = "the identity route; a change of item"

[roles.answer]
slot = "brick"
meaning = "the answer span; the answers' own directions"

[roles.neutral]
slot = "slate"
meaning = "a method of no role (a probe's subspace)"

[roles.mention]
slot = "brown"
meaning = "the bridge's mention, as a place in the prompt"

[roles.question]
slot = "pink"
meaning = "the question, as a place in the prompt"

[controls]
names = ["rotated", "logit lens", "PCA", "a random part", "energy-matched random", "a random vector",
         "layout-only probe", "10 random heads", "no change"]

[key]
tick = "the largest same-size control"
band = "within 0.10 of a random part"

[intervals]
ci95 = "95% interval"

[formats]
ratio = { decimals = 2 }          # "× the full damage"

[units.drop]
title = "accuracy drop (points)"
quantity = "accuracy drop"
format = "points"

[units.gap]
title = "gap: recall − lookup (points)"
quantity = "gap"
format = "points"

[units.gap_share]
title = "gap: recall − lookup (share of switches)"
quantity = "gap"
format = "share"

[units.switches]
title = "share of switches"
quantity = "switches blocked"
format = "share"

[units.accuracy]
title = "accuracy (%)"
quantity = "answers right"
format = "accuracy"

[units.damage]
title = "× the full damage"
quantity = "of the damage"
format = "ratio"

[units.z]
title = "z against 200 random vectors"
quantity = "distance from random"
format = "z"

[units.depth]
title = "share of the depth"
quantity = ""
format = "share"
cue = false
# … plus lookups, rebuilt, lookups_switched, moved, attention, cut: carried over from figkit/terms.py UNIT / CUE_OF

[terms]
canonical = ["lens part", "knock-out", "removed from the patch", "swapped in", "the whole change", "a change of item",
             "another entity", "switches blocked beyond random", "address", "identity", "position", "the number",
             "answer span", "answer span kept", "answer span removed", "Band of layers · fact passages",
             "One layer · locker scenes", "accuracy drop", "gap: recall − lookup", "switches blocked",
             "locker sentence first", "locker sentence after"]   # … the rest of terms.CONDITIONS
templates = ["{num} items", "{num} / {num} items", "bar fixed in advance: {num}", "{entity} · {num} / {num} items"]
missing = ["no run", "no comparable run", "below gate", "too few switches", "no interval"]
not_claimed = ["shared with the logit lens", "gone when scored by probability"]

[[terms.banned]]
pattern = "J++ part"
use = "lens part"

[[terms.banned]]
pattern = "J-part"
use = "lens part"

[[terms.banned]]
pattern = "KO"
use = "knock-out"

[[terms.banned]]
pattern = "ablat"
regex = true
use = "knock-out"

[[terms.banned]]
pattern = "donor"
use = "another entity"

[[terms.banned]]
pattern = "registered"
use = "fixed in advance"

[[terms.banned]]
pattern = "pts"
use = "points"
# … the rest of terms.BANNED and lint.LOSS_WORDS

[[entities.models]]
key = "qwen3.5-9b"
name = "Qwen 9B"
id = "q9"

[[entities.models]]
key = "qwen3.6-27b"
name = "Qwen 27B"
id = "q27"

[[entities.models]]
key = "muse-glimmer-30b"
name = "Muse 30B"
id = "mu"

[[entities.models]]
key = "nemotron-3.5-lightning"
name = "Lightning"
id = "nl"

[[entities.models]]
key = "qwen3.5-122b-a10b"
name = "Qwen 122B"
id = "q122"
# then DeepSeek, Ministral, Bolt, OLMo (breadth only)

[statuses]
use = ["fixed_in_advance", "post_hoc", "descriptive", "not_claimed"]

[registry]
path = "data/figures/status.csv"
```

### 9.2 esk-audit

Roles are the project's to choose. This draft is a starting point, not a decision.

```toml
[project]
name = "esk-audit"
schema = 1

[roles.method]
slot = "violet"
word = "gender direction"
meaning = "the gender-direction method"

[roles.readout]
slot = "teal"
word = "sign-separability"
meaning = "a linear readout of the same direction"

[controls]
names = ["the paper's baselines", "a random direction", "a blank-evidence baseline", "other directions"]

[key]
tick = "the largest control"        # unused in the two pilots
band = ""                           # no grey band in this project yet

[intervals]
sem = "± 1 SEM (bootstrap)"         # reproduction_bar_chart: see 11.1
iqr = "middle half (25th–75th percentile)"   # layer_rank_sweep_chart: see 11.3
ci95 = "95% interval"

[units.accuracy]
title = "auditor accuracy (%)"
quantity = "accuracy"
format = "accuracy"

[units.rank]
title = "rank of the best gender word"
quantity = "rank"
format = "count"                    # integer; see 11.2 for log scale and "lower is better"
scale = "log"

[units.layer]
title = "layer"
quantity = ""
format = "z"                        # integer
cue = false

[units.cosine]
title = "cosine with the fine-tuning change"
quantity = "cosine"
format = "share"

[units.prompts]
title = "unique prompts"
quantity = "prompts"
format = "z"

[terms]
canonical = ["direct set", "standard set", "chance", "layer 11", "contrastive", "random control"]
missing = ["no run"]

[[terms.banned]]
pattern = "Gender Direction"
use = "gender direction"

[[terms.banned]]
pattern = "ours"
use = "gender direction"

[[entities.methods]]
key = "io"
name = "I/O (no evidence)"

[[entities.methods]]
key = "logit_lens"
name = "logit lens tokens"

[[entities.methods]]
key = "residual_tokens"
name = "activation tokens"

[[entities.methods]]
key = "sae_tokens"
name = "SAE tokens"

[[entities.methods]]
key = "sae_feature_descriptions"
name = "SAE descriptions"

[[entities.methods]]
key = "gender_direction"
name = "gender direction (layer 11)"

[[entities.checkpoints]]
key = "female"
name = "female checkpoint"

[[entities.checkpoints]]
key = "male"
name = "male checkpoint"

[[entities.prompt_sets]]
key = "direct"
name = "direct set"

[[entities.prompt_sets]]
key = "standard"
name = "standard set"

[statuses]
use = ["fixed_in_advance", "post_hoc", "descriptive"]

[registry]
path = "user_gender/plots/status.csv"
```

The method display names ("logit lens tokens", "activation tokens"…) are a proposed lower-case restyling of the
current labels ("Logit Lens Tokens", "Acts Tokens"). That choice is the project's.

---

## 10. Two current figures mapped onto the API

### 10.1 bridge-jspace `fig01_main_split`

Now: `writeup_v2.fig01_main_split` builds a `dottable.Table` from callbacks that draw on raw axes. Row positions are
shifted by hand (`LIFT`) to make room for tags, and an `extra` hook re-finds the tag texts to tag them for the checks.

With the library (the data accessors `D.b`, `S.ctrl`, `S.conflict`, `D.x` stay in the project):

```python
v = sp.load("plotstyle.toml")
M = [e.key for e in v.entities("models")][:5]
ID = {e.key: e.id for e in v.entities("models")}

def est(t, cell, key=None, label=False):
    return sp.Est(t[0], t[1], t[2], cell=cell, key=key, label=label)

band = lambda m: f"band.{ID[m]}"
layer = lambda m: f"layer.{ID[m]}"

def layer_gap(m):
    g = D.x(f"contrast_{D.SHORT.get(m, '-')}")
    if g is None:   # aggregate only: no interval, said in the cell
        rc, lk = S.conflict(m, "recall")[0], S.conflict(m, "lookup")[0]
        return sp.Est(rc - lk, cell=layer(m), key=f"contrast.{ID[m]}", label=True, note="no interval")
    return est(g, layer(m), key=f"contrast.{ID[m]}", label=True)

table = sp.DotTable(rows=M, kind="models", groups=[
    sp.ColumnGroup("Band of layers · fact passages", [
        sp.DotColumn("accuracy drop", "drop", (-4, 70), (0, 30, 60),
            series=[sp.Series("lookup", {m: est(D.b(f"ko.{ID[m]}.lostK"), band(m)) for m in M}),
                    sp.Series("recall", {m: est(D.b(f"ko.{ID[m]}.lostM"), band(m)) for m in M})],
            connect=("lookup", "recall")),
        sp.DotColumn("gap: recall − lookup", "gap", (-4, 98), (0, 30, 60),
            series=[sp.Series("recall", {m: est(D.b(f"ko.{ID[m]}.mk"), band(m), f"ko.{ID[m]}.mk", True) for m in M})],
            ticks={m: S.ctrl(ID[m]) for m in M}),
    ]),
    sp.Gutter(),
    sp.ColumnGroup("One layer · locker scenes", [
        sp.DotColumn("switches blocked", "switches", (-0.25, 1.0), (0, 0.5, 1),
            series=[sp.Series("lookup", {m: est(S.conflict(m, "lookup"), layer(m)) for m in M}),
                    sp.Series("recall", {m: est(S.conflict(m, "recall"), layer(m)) for m in M})],
            connect=("lookup", "recall"), band=(-0.1, 0.1)),
        sp.DotColumn("gap: recall − lookup", "gap_share", (-0.1, 1.1), (0, 0.5, 1),
            series=[sp.Series("recall", {m: layer_gap(m) for m in M})]),
    ]),
])
sp.save(sp.Figure("fig01_main_split", v).add(table), "figures/writeup/fig01_main_split.png", target="post")
```

The library supplies the rest:

- Hollow dots for `band.mu`, `band.q122`, `layer.nl`, read from the registry.
- "not claimed: shared with the logit lens" and "not claimed: gone when scored by probability", inside the band
  group's span on those rows, from the registry's claim.
- The role words "lookup" and "recall" above each panel.
- The key line: "grey tick: the largest same-size control · ○ post hoc · whiskers: 95% interval · grey band: within
  0.10 of a random part".
- The cues and axis titles, from the units.

The project drops `LIFT`, the `tag` hook, `_val`, `_col` and the `G.begin`/`G.key` plumbing.

### 10.2 esk-audit `reproduction_bar_chart.py`

Now: sorted horizontal bars, magenta for the method, blue-grey for baselines, SEM error bars in dark grey,
"68.5%" labels, a legend box for chance, a title. The data loading and bootstrap stay; only the drawing (about 20 lines)
changes:

```python
v = sp.load("plotstyle.toml")
order = [e.key for e in v.entities("methods")]               # vocabulary order, no longer sorted by value
rows = {r["key"]: r for r in computed_rows}                   # the script's existing rows, plus a "key" field

def est(r):
    return sp.Est(r["avg"], r["avg"] - r["sem"], r["avg"] + r["sem"], interval="sem",
                  cell=f"{prompt_set}.{r['key']}", key=f"{prompt_set}.{r['key']}.avg", label=True)

base = [k for k in order if k != "gender_direction"]
table = sp.DotTable(rows=order, kind="methods", columns=[
    sp.DotColumn("auditor accuracy", "accuracy", (40, 100), (50, 75, 100),
        series=[sp.Series("method", {"gender_direction": est(rows["gender_direction"])}),
                sp.Series("control", {k: est(rows[k]) for k in base}, control="the paper's baselines")],
        rules=[sp.Rule(50, "chance")]),
])
sp.save(sp.Figure(f"reproduction_{prompt_set}", v).add(table), args.output_png, target="post")
```

What changes visibly:

- Bars become dots on one axis. The baselines are grey and the method is violet, with the role word "gender
  direction" above the first row.
- The key reads "grey: the paper's baselines · whiskers: ± 1 SEM (bootstrap)".
- Values print as "69", "64"…: integer accuracy, per the grammar's default.
- The title and the legend box go.
- Rows follow the vocabulary order instead of the value order.

The axis is 40–100 instead of 0–108, so dots are distinguishable. That changes the scale, not a number. Each of these
is presentation only; the values are the script's own.

Integer accuracy collapses differences under a point. Today the closest pair is 63.3 vs 64.2: "63" vs "64", still
distinct. A project that needs one decimal sets `accuracy = { decimals = 1 }` in its own file.

---

## 11. What the grammar cannot express yet

These are raised here instead of bent quietly. Each has a proposal; the decisions are in Section 12.

1. **Whiskers that are not a 95% interval.** The grammar fixes "whiskers: 95% interval".
   - esk-audit's bars show ± bootstrap SEM. Converting SEM to a 95% interval would be a new statistic, not
     presentation.
   - Proposal: interval kinds declared in `[intervals]`; the key names each kind drawn ("whiskers: ± 1 SEM
     (bootstrap)"). A figure that draws two kinds lists both.
2. **A value axis that is vertical.** Cues are defined only as "→ more <q>" under x-axes.
   - A sweep's quantity is on y. bridge-jspace's depth curves have no cue today.
   - esk-audit's rank is also log-scaled, and lower is better.
   - Proposal: allow `↑ more <q>` beside the y-axis title of a sweep only. The cue states the axis, not what is
     good, so a rank reads "↑ more rank" (honest, if plain). The project may instead declare the quantity as
     something where "more" reads naturally.
   - Log scale is a unit property (`scale = "log"`), with ticks at powers of ten in the unit's format.
3. **Interval bands on lines.** The only band the grammar names is the grey "within 0.10 of a random part".
   - esk-audit's sweep draws a role-coloured IQR band.
   - Proposal: "shading: <interval phrase>" in the key, in the line's role colour at fixed alpha. This is the one
     place a tint appears, and it means "interval", never a variable. It needs an explicit ruling, because grammar A
     says "no shades".
4. **Axes without a quantity.** UMAP and PCA axes have no unit and no direction.
   - Proposal: `axes="embedding"`, with no ticks, no cue and the axis titles "UMAP 1" / "UMAP 2". The PCA panel's
     explained-variance shares become numbers in the share format inside the axis title template.
5. **Violins.** Two esk-audit scripts draw violins; v0.1 has histogram and strip.
   - Proposal: strip (each prompt a dot, grey median tick), which shows the bimodality the project cares about better
     than a smoothed violin. Otherwise add violins in v0.2.
6. **"Fixed" key phrases that contain project concepts.**
   - "within 0.10 of a random part" (a threshold and a bridge-jspace control) and "the largest same-size control"
     cannot be library constants under the "library never names a project concept" rule.
   - Proposal: the library fixes the prefix and the order ("grey band: …", "grey tick: …"); `[key]` supplies the
     definition.
   - The missing-cell list is the same case: "below gate" and "too few switches" become `terms.missing`.
7. **One cell, two statuses.** bridge-jspace has cells that are post hoc and not claimed. See 5.2 and Decision 2.
8. **A fifth status.** v0.1 accepts only the four statuses, each with a fixed mark meaning. A project with "exploratory"
   or "pre-registered elsewhere" cannot express it without a grammar change.
9. **Histograms are bars.** Grammar C allows bars only for 100% stacks; the brief's distribution type is a histogram.
   - Proposal: GRAMMAR.md allows histogram bins inside the distribution type only. They are in one role colour with
     white edges and have no value labels.
10. **Per-point labels in a scatter.** `direction_vectors_umap.py` labels every point with its layer at 7 pt. At 11 pt,
    sixteen labels collide.
    - Proposal: a grey connector in layer order, and labels on the first and last point only ("layer 10", "layer 25").
    - This drops information (the intermediate layer numbers), so it is the project's call.
11. **Gender as colour.** esk-audit codes female/male in magenta/blue. The grammar forbids colour for an entity or a
    category: it becomes rows or small multiples. This is intended, but it is the most visible change in that project.
12. **Ink as a role colour.** bridge-jspace's recall role uses `ink` `#2B2B2B`, and text ink is `#1A1A1A`.
    - The checks tell them apart by hex, but a reader cannot: the role word "recall" reads as ordinary bold text.
    - The grammar allows it, and the project has used it since v1. GRAMMAR.md notes that the `ink` role is
      "the default reader", named by position as much as by colour.

Not grammar gaps, but found while auditing; to report at stage 3, not to fix:

- esk-audit: `separability_vs_accuracy_chart.py` and `attribution_controls_chart.py` **type their numbers into the
  script**. Porting them under "every number is read from data files by code" needs a data source first.
- esk-audit: `layer_rank_sweep_chart.py` computes p25/p75 as `vals[len // 4]` and `vals[3 * len // 4]`, which are
  not interpolated percentiles. The port keeps these numbers; this is noted only.
- esk-audit: `separability_vs_accuracy_chart.py` gives the direct set's decoded accuracy as 68.05;
  `reproduction_bar_chart_direct.png` shows the gender direction at 68.5. These may be different quantities (the
  latter averages female and male). To check before both figures are in one set, because check 7 would flag them if
  they share a data key.
- esk-audit: "layer 11 (best single point)" and "best layer" are picked from the plotted data. Whether those cells are
  `post_hoc` is a registry decision for the project.

---

## 12. Decisions needed

1. **The uncommitted v2 work in bridge-jspace.** Seven new files and eleven modified files on `figure-style-v2` are not
   committed. Stage 3 targets the same branch name.
   - Recommendation: commit them as they are on that branch (or say whose they are) before stage 3. The adoption
     commit then shows the library replacing `grammar.py`/`terms.py` in a reviewable diff.
   - I have not touched that working tree.
2. **Registry schema: two axes (timing, claim) or the brief's single status?**
   - Recommendation: two axes, as v2 of the schema, with v1 still readable.
3. **The six failing colour pairs.**
   - Recommendation: keep all nine hexes, enforce per figure, ship the "never in one figure" list.
   - The alternative is a palette change with large shifts (Section 2), which is a minor version with a migration
     note. That alternative recolours already published bridge-jspace figures.
4. **`status=` on drawing calls.** The brief asks for it; this design reads status from the registry by `cell=`.
   - Recommendation: as designed. `status=` is accepted only without a registry (notebook).
5. **The y-axis cue for sweeps, the interval band shading and interval kinds** (11.1–11.3).
   - Recommendation: as proposed. Grammar A's "no shades" needs an explicit exception for interval shading.
6. **`tomli` on Python 3.10.** The brief allows matplotlib and numpy only, and 3.10 has no `tomllib`.
   - Options: a conditional dependency `tomli; python_version < "3.11"` (pure Python, 1 file), or a floor of 3.11.
   - The floor of 3.11 would exclude esk-audit's pinned environment.
   - Recommendation: the conditional dependency.
7. **Slide and readme geometry** (Section 6.7). These are proposals; the brief gives only "16:9" and "readme".
8. **Repository setup.** `danorel/styles-plot` exists and is public, but it has **no licence and no commits**; the brief
   says it is created with an MIT licence.
   - I committed this document locally on `main` and have **not pushed**.
   - Either add the licence on GitHub and I rebase onto it, or confirm I should add `LICENSE` (MIT) myself and push.

---

## 13. Extraction map: what moves, what stays

| source (bridge-jspace) | goes to | how |
|---|---|---|
| `palette.ROLE` hexes (+ `SHADE.answer/neutral/mention/question` from `writeup-figures`) | `palette.py` slots | renamed to neutral slot names; project role names move to the vocabulary |
| `palette` chrome (`INK`, `MUTED`, `FAINT`, `GRID`, `ZEBRA`, `BAND`, connector, rule greys) | `palette.py` chrome | constants; never a role |
| `palette.SHADE` light/dark variants, `GREYS` grab bag | dropped | grammar A: no shades |
| `palette.MODELS`, `BREADTH_ONLY` | bridge `plotstyle.toml` `[entities.models]` | vocabulary |
| `theme.Theme` sizes, fonts, dpi; `WRITEUP_*` | `theme.py` + targets | `colors`, `whisker` colour, `control_scale` dropped |
| `dottable.Table/Row/Col` layout, `rich`, `runs` | `table.py`, `text.py` | globals become `Theme` + render context; draw callbacks become declared columns |
| `dottable.dot/connector/band/vrule/head_label/under` | `marks.py` | tagged; colours from slots |
| `lint.table_problems`, `crossings`, `drawn_obstacles`, `hit`, `png_problems` | `checks/layout.py` | project word lists move to vocabulary |
| `lint.problems` (v1 bar lint), `_redgreen` | dropped | grammar v2 checks replace it |
| `render.stacked`, `render.curves` | `stack.py`, `sweep.py` | rebuilt on tagged marks |
| `render.bars`, `render.multiples`, `spec.Bars/Multiples/Image` | dropped | bars are not in grammar v2; `Image` is a project concern |
| `check_style.off_palette` | `checks/pixels.py`, CLI `check` | README discovery stays |
| `check_figure_terms`: text harvesting, banned runner, id detectors, verbatim exemptions | `checks/words.py` | term tables become vocabulary |
| `build.page_sheet` | `sheet.py` | plus a gray version |
| working tree `grammar.py` (tags, key, num, check) | `marks.py`, `ledger.py`, `key.py`, `numbers.py`, `checks/meaning.py` | |
| working tree `terms.py` | bridge `plotstyle.toml` | as data |
| working tree `colour_vision.py` | `checks/colour_vision.py` + `[check]` extra | |

**Stays in bridge-jspace**, rebuilt on the library in stage 3 and its own steps 4–5: `writeup_*.py`, `writeup_v2.py`,
`deck_figs.py`, `claim_figs.py`, `depth_figs.py`, `curve_figs.py`, `ledger_tables.py`, `exemplars.py`, `tables.py`,
`build.py`, `specs.py`, `data.py`, `scripts/status_registry.py` (it derives statuses from project rules), README
discovery in `check_style.py`, the retired-term tables.

**Stays in esk-audit**: all data loading, bootstraps and summaries in the 11 scripts; only their drawing sections change.

---

## 14. Plan for v0.1

| step | contents | done when |
|---|---|---|
| 1 | `pyproject.toml` (hatchling, version from tag), `vocab.py`, `registry.py`, `palette.py` + shipped CVD table, `theme.py`, `numbers.py` | schema validation and formatter tests pass |
| 2 | `marks.py`, `ledger.py`, `table.py` (port of the dot-table layout), `key.py`, `text.py`, `save.py` + sidecar | `fig01`-shaped synthetic example saves strict, at post target |
| 3 | `checks/` 1–9 | each check has failing and passing fixtures; `checks/` line coverage ≥ 85% |
| 4 | `sweep.py`, `dist.py`, `stack.py`, `scatter.py`, `schematic.py` | one example each in `examples/`, strict-clean |
| 5 | `cli.py` (`check`, `sheet`, `key`, `palette`); `GRAMMAR.md`, `ADOPTING.md`; gallery | `styles-plot check gallery/` clean in CI |
| 6 | CI; `CHANGELOG.md`; tag `v0.1.0` | green matrix |

**Tests.**
- Checks are tested on small synthetic figures built through the public API, plus raw-matplotlib fixtures that
  violate each rule. They assert on problem codes, not on messages or pixels.
- No golden-image comparisons, because rendering differs across matplotlib versions. Layout is tested through the
  layout checks themselves, on the gallery.
- Formatters get table-driven tests: minus sign, "−0", rounding at .5, intervals, counts.
- CIEDE2000 is tested against Sharma et al.'s 34 pairs.
- Registry v1 to v2 mapping is tested on bridge-jspace's current CSV shape, with synthetic rows (no project data in
  this repo).

**CI matrix.**
- Python 3.10, 3.11, 3.12, 3.13 × matplotlib 3.8.\* and latest. 3.13 is added for esk-audit's local environment.
- 3.13 × 3.8 is excluded, because matplotlib 3.8 has no 3.13 wheels.
- numpy 1.26 with matplotlib 3.8; latest numpy 2.x with latest matplotlib.
- Gallery rebuilt and `styles-plot check gallery/` run on one cell (3.12, latest).

Rough size: about 2,500 lines of library and 1,500 of tests, from about 1,200 lines of extracted seed.

---

## 15. Appendix: full colour-vision table

CIEDE2000 between slot pairs; Machado 2009 at severity 100 via colorspacious 1.1.2; floor 12 between roles, 8 against
control. "min" is the smallest of the four columns.

| pair | normal | deutan | protan | tritan | min | floor | |
|---|---:|---:|---:|---:|---:|---:|---|
| ink–violet | 35.4 | 33.8 | 35.2 | 28.0 | 28.0 | 12 | ok |
| ink–teal | 42.3 | 33.1 | 38.5 | 43.2 | 33.1 | 12 | ok |
| ink–amber | 50.5 | 53.0 | 45.5 | 49.1 | 45.5 | 12 | ok |
| ink–blue | 35.9 | 34.9 | 38.0 | 37.2 | 34.9 | 12 | ok |
| ink–brick | 33.3 | 31.8 | 21.3 | 34.6 | 21.3 | 12 | ok |
| ink–slate | 18.7 | 17.7 | 18.4 | 21.0 | 17.7 | 12 | ok |
| ink–brown | 30.0 | 30.7 | 28.1 | 30.3 | 28.1 | 12 | ok |
| ink–pink | 38.9 | 33.8 | 31.0 | 39.0 | 31.0 | 12 | ok |
| ink–control | 47.3 | 47.3 | 47.3 | 47.3 | 47.3 | 8 | ok |
| violet–teal | 42.0 | 26.2 | 35.2 | 21.6 | 21.6 | 12 | ok |
| violet–amber | 57.4 | 63.9 | 60.7 | 47.1 | 47.1 | 12 | ok |
| violet–blue | 16.9 | 5.1 | 8.2 | 13.5 | 5.1 | 12 | **fail** |
| violet–brick | 38.1 | 51.6 | 44.9 | 47.4 | 38.1 | 12 | ok |
| violet–slate | 13.4 | 19.7 | 21.2 | 12.5 | 12.5 | 12 | ok |
| violet–brown | 45.4 | 48.0 | 46.6 | 36.5 | 36.5 | 12 | ok |
| violet–pink | 22.8 | 21.7 | 13.9 | 40.9 | 13.9 | 12 | ok |
| violet–control | 34.4 | 33.8 | 32.1 | 24.7 | 24.7 | 8 | ok |
| teal–amber | 45.0 | 30.8 | 22.6 | 57.2 | 22.6 | 12 | ok |
| teal–blue | 32.6 | 22.4 | 29.5 | 9.5 | 9.5 | 12 | **fail** |
| teal–brick | 58.0 | 23.9 | 24.7 | 63.3 | 23.9 | 12 | ok |
| teal–slate | 28.4 | 18.8 | 24.7 | 24.0 | 18.8 | 12 | ok |
| teal–brown | 34.1 | 21.0 | 18.3 | 45.1 | 18.3 | 12 | ok |
| teal–pink | 47.8 | 5.9 | 22.2 | 54.5 | 5.9 | 12 | **fail** |
| teal–control | 25.3 | 10.6 | 8.3 | 24.8 | 8.3 | 8 | ok (margin 0.3) |
| amber–blue | 51.2 | 59.0 | 54.5 | 63.3 | 51.2 | 12 | ok |
| amber–brick | 30.5 | 19.6 | 26.6 | 19.3 | 19.3 | 12 | ok |
| amber–slate | 44.6 | 46.4 | 40.2 | 47.5 | 40.2 | 12 | ok |
| amber–brown | 20.8 | 20.7 | 18.7 | 19.6 | 18.7 | 12 | ok |
| amber–pink | 44.5 | 37.9 | 44.3 | 12.7 | 12.7 | 12 | ok |
| amber–control | 27.4 | 26.5 | 27.3 | 25.5 | 25.5 | 8 | ok |
| blue–brick | 43.3 | 48.2 | 42.6 | 67.3 | 42.6 | 12 | ok |
| blue–slate | 18.2 | 19.3 | 21.6 | 17.6 | 17.6 | 12 | ok |
| blue–brown | 40.3 | 44.8 | 42.8 | 51.5 | 40.3 | 12 | ok |
| blue–pink | 33.7 | 17.5 | 9.7 | 56.4 | 9.7 | 12 | **fail** |
| blue–control | 27.3 | 29.1 | 25.2 | 25.3 | 25.2 | 8 | ok |
| brick–slate | 36.9 | 31.1 | 22.2 | 43.4 | 22.2 | 12 | ok |
| brick–brown | 22.6 | 3.4 | 7.7 | 15.7 | 3.4 | 12 | **fail** |
| brick–pink | 24.9 | 30.6 | 32.8 | 15.0 | 15.0 | 12 | ok |
| brick–control | 33.6 | 26.8 | 32.8 | 35.0 | 26.8 | 8 | ok |
| slate–brown | 27.8 | 28.5 | 25.0 | 35.8 | 25.0 | 12 | ok |
| slate–pink | 29.5 | 17.6 | 13.3 | 37.6 | 13.3 | 12 | ok |
| slate–control | 30.1 | 30.5 | 28.4 | 31.5 | 28.4 | 8 | ok |
| brown–pink | 35.3 | 27.6 | 32.9 | 11.3 | 11.3 | 12 | **fail** |
| brown–control | 25.4 | 24.3 | 26.1 | 26.0 | 24.3 | 8 | ok |
| pink–control | 26.8 | 13.3 | 20.6 | 26.4 | 13.3 | 8 | ok |

Near misses worth watching: teal–control clears its floor by 0.3 under protanopia, violet–slate by 0.5 under
tritanopia, amber–pink by 0.7 under tritanopia. The `other` slot (`#D9D9D9`) is chrome and is not in the table.
