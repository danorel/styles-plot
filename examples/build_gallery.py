"""Build the gallery: every example for every published target, strict, then the contact sheets.

    python examples/build_gallery.py [--out gallery] [--targets post slide readme] [--only ID ...] [--no-sheets]
                                     [--jobs N]

A thin wrapper around the figure set in gallery.py (`styles-plot build examples/gallery.py:GALLERY`), plus contact
sheets. The README images are `--out examples/figures --targets readme --only dot_table key sweep methods --no-sheets`
(`make readme-images`). Exits 1 when any figure breaks the grammar (strict mode writes nothing for it).
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import styles_plot as sp

HERE = Path(__file__).resolve().parent


def _gallery():
    spec = importlib.util.spec_from_file_location("examples_gallery", HERE / "gallery.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.GALLERY


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build and check the gallery.")
    ap.add_argument("--out", type=Path, default=HERE.parent / "gallery", help="output folder (default: gallery/)")
    ap.add_argument("--targets", nargs="+", default=None, help="targets to build (default: each figure's)")
    ap.add_argument("--only", nargs="+", metavar="ID", help="build only these figure ids (globs)")
    ap.add_argument("--no-sheets", action="store_true", help="no contact sheets")
    ap.add_argument("--jobs", type=int, default=1, help="worker processes")
    args = ap.parse_args(argv)
    report = _gallery().build(only=args.only, targets=args.targets, jobs=args.jobs, out=args.out)
    for f in report.figures:
        print(f"ok    {f['id']}" if f["ok"] else f"FAIL  {f['id']}\n{f['error']}")
    for t in [] if args.no_sheets else (args.targets or ("post", "slide", "readme")):
        pngs = sorted(p for p in (args.out / t).glob("*.png") if not p.name.startswith("contact_sheet"))
        if pngs:
            sp.contact_sheets(pngs, args.out / t, width=720)
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
