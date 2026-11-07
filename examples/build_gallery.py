"""Build the gallery: every example for every published target, strict, then the contact sheets and the key figure.

    python examples/build_gallery.py [OUT_DIR]      # default: gallery/

Exits 1 when any figure breaks the grammar (strict mode writes nothing for it).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import styles_plot as sp

HERE = Path(__file__).resolve().parent
EXAMPLES = ("dot_table", "sweep", "distribution", "stack", "scatter", "schematic")
TARGETS = ("post", "slide", "readme")
# a five-row table with two column groups needs more height than a 12.3 x 5.3 in slide offers
ONLY = {"dot_table": ("post", "readme")}


def _module(name: str):
    spec = importlib.util.spec_from_file_location(f"examples_{name}", HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else HERE.parent / "gallery"
    v = sp.load(HERE / "plotstyle.toml")
    failed = 0
    figures = [build(v) for name in EXAMPLES for build in _module(name).FIGURES]
    figures.append(sp.key_figure(v))
    for fig in figures:
        try:
            sp.save_bundle(fig, out, ONLY.get(fig.id, TARGETS))
            print(f"ok    {fig.id}")
        except sp.StyleError as e:
            failed += 1
            print(f"FAIL  {fig.id}\n{e}")
        except sp.BuildError as e:
            failed += 1
            print(f"FAIL  {fig.id}: {e}")
    for t in TARGETS:
        pngs = sorted(p for p in (out / t).glob("*.png") if not p.name.startswith("contact_sheet"))
        if pngs:
            sp.contact_sheets(pngs, out / t, width=720)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
