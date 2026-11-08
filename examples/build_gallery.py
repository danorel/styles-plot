"""Build the gallery: every example in blocks/ for every published target, strict, then the contact sheets.

    python examples/build_gallery.py [--out gallery] [--targets post slide readme] [--only ID ...] [--no-sheets]
                                     [--sidecar-dir _meta]

The README images are `--out examples/figures --targets readme --only dot_table key sweep methods --no-sheets
--sidecar-dir _meta` (`make readme-images`): PNGs in examples/figures/readme/, sidecars in its _meta/.

Exits 1 when any figure breaks the grammar (strict mode writes nothing for it).
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import sys
from pathlib import Path

import styles_plot as sp

HERE = Path(__file__).resolve().parent
EXAMPLES = ("dot_table", "sweep", "distribution", "stack", "scatter", "schematic", "card")
TARGETS = ("post", "slide", "readme")
KEY_TARGETS = ("post", "readme")  # the key figure belongs to a reading page; on a slide it does not fit 6.5 in


def _module(name: str):
    spec = importlib.util.spec_from_file_location(f"examples_{name}", HERE / "blocks" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def key(v: sp.Vocab) -> sp.Figure:
    """The key figure, with one example row from the dot-table example's data, read aloud."""
    dt = _module("dot_table")
    m, (a, b, gap, ctrl) = "m2", dt.example_row()
    col = sp.DotColumn("accuracy drop", "drop", (-4, 70), (0, 30, 60),
                       series=[sp.Series("second", {m: sp.Est(b, cell="band.m2")}),
                               sp.Series("first", {m: sp.Est(a, cell="band.m2")})],
                       connect=("second", "first"), ticks={m: ctrl})  # fmt: skip
    gap_col = sp.DotColumn("gap", "gap", (-4, 98), (0, 30, 60),
                           series=[sp.Series("first", {m: sp.Est(gap, gap - 4, gap + 4, cell="band.m2",
                                                                 key="gap.band.m2", label=True)})])  # fmt: skip
    text = (f"read: on {v.entity('models', m).name}, the knock-out drops alpha {{a}} points and beta {{b}}; the gap "
            "is {gap}, the largest same-size control's {ctrl}")  # fmt: skip
    numbers = {"a": (a, "drop", "drop.alpha.m2"), "b": (b, "drop", "drop.beta.m2"), "gap": (gap, "gap", "gap.band.m2"),
               "ctrl": (ctrl, "gap", "ctrl.band.m2")}  # fmt: skip
    return sp.key_figure(v, example=sp.DotTable([m], [col, gap_col]), read_aloud=text, numbers=numbers)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build and check the gallery.")
    ap.add_argument("--out", type=Path, default=HERE.parent / "gallery", help="output folder (default: gallery/)")
    ap.add_argument("--targets", nargs="+", default=list(TARGETS), help="targets to build")
    ap.add_argument("--only", nargs="+", metavar="ID", help="build only these figure ids")
    ap.add_argument("--no-sheets", action="store_true", help="no contact sheets")
    ap.add_argument("--sidecar-dir", default="", help="sidecars under <out>/<target>/<this>/ instead of beside the PNGs")
    args = ap.parse_args(argv)
    out = args.out
    v = sp.load(HERE / "plotstyle.toml")
    if args.sidecar_dir:
        v = dataclasses.replace(v, sidecar_dir=args.sidecar_dir)
    failed = 0
    figures = [build(v) for name in EXAMPLES for build in _module(name).FIGURES]
    figures.append(key(v))
    if args.only:
        unknown = set(args.only) - {f.id for f in figures}
        if unknown:
            ap.error(f"no such figure: {', '.join(sorted(unknown))}")
        figures = [f for f in figures if f.id in args.only]
    for fig in figures:
        try:
            targets = [t for t in args.targets if fig.id != "key" or t in KEY_TARGETS]
            sp.save_bundle(fig, out, targets)
            print(f"ok    {fig.id}")
        except sp.StyleError as e:
            failed += 1
            print(f"FAIL  {fig.id}\n{e}")
        except sp.BuildError as e:
            failed += 1
            print(f"FAIL  {fig.id}: {e}")
    for t in [] if args.no_sheets else args.targets:
        pngs = sorted(p for p in (out / t).glob("*.png") if not p.name.startswith("contact_sheet"))
        if pngs:
            sp.contact_sheets(pngs, out / t, width=720)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
