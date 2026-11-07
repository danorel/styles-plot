# Changelog

Versions follow semver. A grammar or palette change is a minor version with a migration note here; a change that makes
figures that passed strict checks fail them is a major version. Projects pin a tag.

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
