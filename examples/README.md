# Examples

Synthetic data only; every figure is labelled "synthetic data".

| path | what |
|---|---|
| [plotstyle.toml](plotstyle.toml), [status.csv](status.csv) | the vocabulary and status registry every example shares |
| [blocks/](blocks/) | one module per figure type: `dot_table`, `sweep`, `distribution`, `stack`, `scatter`, `schematic`, `card`, and `custom` (a project's own block); each lists its builders in `FIGURES` |
| [strict/](strict/) | `refused.py`: a figure strict mode refuses (its error is shown in the main README) |
| [build_gallery.py](build_gallery.py) | builds every example for every target (`make gallery`) and the README images (`make readme-images`) |
| [figures/](figures/) | the README images, committed: PNGs in `readme/`, sidecars in `readme/_meta/` |
