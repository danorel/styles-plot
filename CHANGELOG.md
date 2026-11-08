# Changelog

Versions follow semver. A grammar or palette change is a minor version with a migration note here; a change that makes
figures that passed strict checks fail them is a major version. Projects pin a tag.

## 0.1.15

A first figure in five minutes.

- `styles-plot init [DIR] [--name NAME] [--force]` writes a starter `plotstyle.toml` (two roles, one control, the
  units, three entities, the terms it prints, the registry path, sidecars under `_meta`), a `status.csv` (two cells
  fixed in advance, one post hoc) and a `first_figure.py` (a dot table with a role, a grey control, a chance line and
  counts) that passes strict on `post` and `readme`. It refuses to overwrite any of the three (exit 2) unless
  `--force`. The templates ship in the wheel (`styles_plot/data/init/`).
- The README shows four figures (`examples/figures/readme/`, committed, rebuilt by `make readme-images`), a quick
  start, and two blocks generated from code by `make readme`: the starter builder and the `StyleError` of `examples/strict/refused.py`.
  `make readme-check` (in `make check` and CI) fails when a block is stale, an image's sidecar means something else
  than a fresh build's, a link is broken, or an image fails `check`. CI also installs the wheel into a clean venv and
  runs `init` and the first figure in an empty folder.
- `examples/` is grouped: `blocks/` (one module per figure type), `strict/` (a figure strict mode refuses),
  `figures/` (the committed README images), the shared `plotstyle.toml` and `status.csv`, and `build_gallery.py`,
  which takes `--only ID ...`, `--no-sheets` and `--sidecar-dir`.
- The `sweep` and `methods` examples carry a title and a caption, so their `readme` PNGs change; no other figure does.

*Migration:* nothing to change.

## 0.1.14

- A 100% stack's segment that is zero in every row is neither drawn nor named above the bars (its word would sit
  over nothing); when its absence is the finding, print it in a text column beside the stack.

## 0.1.13

From the bridge-jspace example cards.

- Card prompts take paragraphs: a list of part-lists, each starting a new line with a small gap; a leading part such
  as ("Lookup:", "lookup", True) labels a paragraph in its role's colour.
- Card text keeps its own spacing: a part that starts with punctuation sticks to the word before it ("frog.", not
  "frog ."). Card prompt and answer text is verbatim and exempt from the run-id check (SP403); an item's own ids may
  appear in it.
- A figure of cards only is as short as its text: no padding to the target's widest proportion (its narrowest still
  holds), in the layout check and the PNG check alike.
- A 100% stack's rows may sum to 1 within ±0.001 (shares stored to a few decimals).

## 0.1.12

From the bridge-jspace README brief.

- `sp.Card` / `sp.CardRow`: an example item as an image (the prompt verbatim with some words bold or coloured, each
  reader's answer per condition in its colour, a small grey note that may carry the item's id). Cards go in a figure
  with `direct_labels=True`, alone or with schematics.
- `Figure(read="read: …{x}…", numbers={"x": (value, unit, key)})`: one sentence under any figure that walks through
  one value, its numbers printed in their units and logged by key (the key figure's read-aloud, for every figure).
- Small multiples: the panels of one `ColumnGroup` on one unit share a single axis title and cue, centred under the
  group (tick labels stay per panel).
- `[marks] max_segments` (default 4) sets how many segments a 100% stack may have; segments of one role are allowed
  when their names differ (two segments may not share a name).

## 0.1.11

From the esk-audit review (a Linux rebuild drew identical pixels into different PNG bytes).

- Sidecars record `png.pixels_sha256`, a hash of the decoded image (mode, size, RGBA pixels), instead of the file's
  byte hash; `styles-plot check` compares pixels (SP902), so another machine's zlib no longer reads as a change.
- A dot table without a dot column (numbers only) fails SP612: such a table belongs in markdown, not in an image.
- PNGs carry no "Software" metadata stamp, so their bytes do not change with the matplotlib version.
- Migration: sidecars written before 0.1.11 have no pixel hash; `styles-plot check` reports SP902 for them until the
  figures are rebuilt once on 0.1.11. PNG bytes can still differ between machines (zlib); compare pixels, not files.

## 0.1.10

From the bridge-jspace depth sweeps.

- `Sweep(windows={row: [(x0, x1, band)]})`: grey windows per row (each model's gated layers); a plain list still
  applies to every row.
- Stacked sweep and distribution panels keep a tick label's height between them, so the top tick of one panel never
  touches the bottom tick of the next.
- A sweep line's word pushed more than 1.5 lines from its line's end (several lines ending at one value) fails SP611:
  it cannot be matched to its line; split the panel.
- A dot-table panel on a log-scale unit fails to build (the panel is linear), instead of drawing a linear axis.
- Lane keys type-check: `Series.cells`, `DotColumn.ticks` and `TextColumn.cells` are `Mapping[Hashable, ...]`.
- SP601 counts only the drawn part of a clipped line: an interval reaching past the axis no longer "crosses" the
  tick labels outside the panel.

## 0.1.9

- All post hoc, said once: when every estimate of a figure is post hoc in the registry, its marks are drawn filled and
  the key reads "all estimates post hoc" instead of "○ post hoc" (a sweep line's panel tag drops "post hoc"). Decided
  in the esk-audit review. Migration: such figures change from hollow to filled marks; the registry is unchanged.

## 0.1.8

Fixes from the bridge-jspace port on 0.1.7.

- Dot-table value labels go into the free gap nearest their own dot (the right side on a tie), placing from the
  rightmost dot leftwards; every mark, whisker, connector, tick, vertical line and placed label is an obstacle on
  both sides. 0.1.6–0.1.7 could drop a label on the panel's left edge across the zero line when its right side was
  taken by a neighbour's label. With no gap wide enough, the label sits right of its dot and the check reports it.
- Sweep margin words moved off their line's end (two lines ending at one value) get a thin grey leader to that end.
- Missing-cell words wider than their line's free span fail with SP610, naming the width needed and the width free.

## 0.1.7

From the bridge-jspace breadth port.

- Sweep: a line with its own word (`Line(word=...)`) is named at its last point, in the panel's right margin, the
  words pushed apart so two nearly overlapping lines of one role are told apart; lines without a word keep the role
  word above the panel.
- Dot table: a rule that repeats in several columns (same place, same words) is labelled over its first column only.

## 0.1.6

Grammar decisions of 7 Nov.

- One colour, one estimate per line: two estimates of one role in one row are allowed only in different columns (each
  with its own header and axis); two on one line of a column fail to build.
- A column whose header is its single role's word (a gap drawn in the neutral role) shows that header in the role's
  colour and no colour word above the rows.
- Stacks carry no whiskers: `Stack(columns=[TextColumn(...)])` prints a segment's interval beside the bars.
- Sweep points measured on their own: `Point(value=..., lo=..., hi=...)` with a vertical whisker; the line itself
  carries no status.
- Layout fixes from the bridge port: a value label's left fallback starts at its own dot (it used to jump left of
  every mark, onto a near control); a status tag and a note on one row no longer overlap (the note moves to the next
  line); on a row with lanes a tag sits right under its cell's lane; colour words that do not fit one line above a
  panel fail with SP609 and say why.
- More from the bridge port: a sweep's grey control line names its control (`Line(role="control", control=...)`,
  "grey: …" in the key); missing-cell words keep clear of their line's marks; rule labels wrap inside their panel on
  levels of their own and group headers wrap inside their span (no overlap across adjacent columns); the key figure
  lists the controls across its full width, so a long list no longer pushes it below the target's proportions; two
  grey control dots on one line of a column fail like two of one role.
- Figure sets in folders: `[output] sidecar_dir = "_meta"` puts sidecars under the set's root keeping each PNG's path
  (`save(..., root=<set>)`: main/fig01.png -> _meta/main/fig01.styles.json); `styles-plot check` and `sheet` take PNGs
  in subfolders, skip folders starting with "_" (_meta, _sheets), find sidecars beside a PNG or under _meta, and an
  `--order` file may list paths under the set ("main/fig01_main_split").

## 0.1.5

Fixes a 0.1.4 regression and two placement gaps.

- Dot-table value labels: every dot (with its radius and the check's clearance), whisker, connector and grey tick on
  the line is an obstacle; a label goes right of its own dot in the first gap that touches none of them, else left of
  the line's marks. 0.1.4 placed a label "beside its own dot" across a connector or on a neighbouring dot.
- Sweep point labels stay within two steps of their dot; with no clear spot that near, the layout check fails
  (SP601) instead of a label landing a layer away, where it reads as another dot's.
- Schematic arrow labels sit off the arrow along its normal; arrows are now obstacles in the crossing check (SP601),
  so a word laid on an arrow fails.

## 0.1.4

From the esk-audit port and the wider bridge-jspace port.

Fixes:
- Value labels: no more hang when a vertical line sits on the clearance boundary; the labels of one row (or lane)
  are placed together, each beside its own dot when that covers no other mark, else after the row's marks, else left
  of them, never past the panel's left edge.
- Text is measured at the target's dpi, so side-by-side texts (a value and its interval) no longer overlap by a
  pixel.
- A grey (control) distribution names its control: `Distribution(control=...)`; a control data mark without a name
  fails the new check SP304 (it used to pass silently, with no "grey: …" in the key).

New:
- Sweep: `hrules` (horizontal dashed rules such as chance, labelled in the right margin), `windows` (grey x-ranges
  with a band definition), `Line(median=True)` (the key says "line: median"), `Line(word=...)` (two lines of one role
  named at their ends), point labels that keep clear of lines.
- Named grey bands: `[key.bands] <name> = "<definition>"`, `DotColumn(band_name=...)`; two band meanings in one
  figure fail SP305.
- `ScatterPanel(header="PCA (PC1 {a}, PC2 {b})", numbers={...})`: numbers in a header, printed and logged by key.
- Schematic: `Arrow(label=...)`; a `Words` part may be `(text, role, bold)`.
- `vocab.with_entities(kind, [(key, name)])`: rows read from data (head ids), still ordered and checked.

## 0.1.3

From the bridge-jspace pilot port.

- Key figure: the legend sits in two columns (roles left, marks right) on a page 6 in or wider, and every phrase wraps
  in its column (a long controls line no longer runs off the figure). The read-aloud sentence takes its numbers as
  `numbers={name: (value, unit, data key)}`: printed in the unit's format and logged by key.
- `Series(word=...)`: a series' colour word other than its role's (a lane's condition), in the role's colour.
- `Rule(x, "bar fixed in advance: {}", unit=..., key=...)`: a rule label's number is printed and logged like any other.
- Missing-cell words avoid vertical lines (left, else right-aligned, else the widest gap).
- An interval's bounds are never signed, also under a signed format: "+6.2 [3.2, 8.9]". Migration: none needed;
  0.1.2 printed "[+3.2, +8.9]".
- `TextColumn(unit_title=False)`: no unit title under a text column whose header names the quantity.
- `styles-plot sheet --order FILE`: the figures in reading order.
- pillow is a declared dependency (it always came with matplotlib).

## 0.1.2

What the bridge-jspace pilot port needs; no change to existing figures.

- Dot table lanes (`sp.Lane`): sub-rows of every entity row, labelled in grey under the row's name or named by colour
  words only; cells keyed (row, lane).
- `DotTable(note=...)`: one grey line above a table, for figures stacked from several tables.
- `[formats.<name>].sign = true`: a "+" before positive values, for differences.

## 0.1.1

- Key figure: adds the grey tick, the grey band and one example row from the data read aloud
  (`key_figure(vocab, example=..., read_aloud=...)`); draws the post hoc and whisker samples in ink; no key line
  repeated under it.
- Cue word per unit: `cue_word = "larger"` gives "→ larger gap". Migration: a project that overrides `[phrases].cue`
  or `cue_y` writes `{word}` and `{quantity}` instead of `{}` ("→ {word} {quantity}").
- Colour words above a panel sit on one line, in the order their dots appear.
- Slide target: 12.3 × 6.5 in. A figure that does not fit fails strict; split it.
- Sweep: a whole line's status is a grey panel tag ("post hoc", "descriptive", joined with " · "); a post hoc line no
  longer fails to build. Points keep hollow or filled.
- `examples/build_gallery.py` takes `--out` and `--targets`.

## 0.1.0

First release.

- Vocabulary file `plotstyle.toml`: roles, controls, key definitions, interval kinds, formats, units, terms, entities,
  registry; style parameters with defaults: palette, font, targets, marks, phrases.
- Status registry with two columns: timing (hollow ↔ post hoc) and claim (grey tag).
- Figure types: dot table, sweep, distribution, 100% stack, scatter, schematic; composite figures as one matplotlib
  figure; a key built from what was drawn; a key figure.
- Targets post, slide, readme (title and caption), notebook; `save`, `save_bundle`, strict and compat modes; sidecar
  metadata.
- Checks SP101–SP904; colour-vision table of the default slots shipped; six default slot pairs may not share a figure.
- CLI: `check`, `sheet`, `key`, `palette`.
