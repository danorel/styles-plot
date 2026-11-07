# Changelog

Versions follow semver. A grammar or palette change is a minor version with a migration note here; a change that makes
figures that passed strict checks fail them is a major version. Projects pin a tag.

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
