"""The styles-plot command.

    styles-plot check <dir> [--vocab plotstyle.toml] [--target post]   saved PNGs: size, background, palette; with
                                                                       sidecars: meaning, staleness, one key one string
    styles-plot sheet <dir> [--width 720] [-o DIR] [--order FILE]      contact sheets, colour and gray
    styles-plot key --vocab plotstyle.toml [-o key.png] [--target post] the project's key figure
    styles-plot palette [--vocab plotstyle.toml]                       colour-vision table of the slots
    styles-plot init [DIR] [--name NAME] [--force]                     a starter vocabulary, registry and figure
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from importlib.resources import files
from pathlib import Path

from styles_plot._palette import Palette
from styles_plot._png import check_png, pixels_sha256
from styles_plot._registry import load as load_registry
from styles_plot._save import StyleError, find_sidecar, save
from styles_plot._sheet import contact_sheets, figures_in
from styles_plot._theme import targets_from
from styles_plot._vocab import VocabError, load


def _check(args) -> int:
    root = Path(args.dir)
    if not root.is_dir():
        print(f"styles-plot check: {root} is not a directory", file=sys.stderr)
        return 2
    vocab = load(args.vocab) if args.vocab else None
    targets = vocab.targets if vocab else targets_from(None)
    palette = vocab.palette if vocab else Palette()
    registry = load_registry(vocab.registry_path) if vocab and vocab.registry_path and vocab.registry_path.exists() else None
    lines, warnings, numbers, records, waived = [], [], defaultdict(dict), [], 0
    pngs = figures_in(root)
    sidecar_dirs = tuple(dict.fromkeys([vocab.sidecar_dir if vocab else "", "_meta"]))
    for png in pngs:
        rel = png.relative_to(root)
        side = find_sidecar(png, root, sidecar_dirs)
        meta = json.loads(side.read_text()) if side else None
        if meta is None:  # a warning until 0.3: it can fail a run that passed before
            warnings.append(f"{rel}: SP906 no sidecar: meaning and staleness not checked (only the PNG)")
        target = meta["target"] if meta else args.target
        if target not in targets:
            lines.append(f"{rel}: SP901 unknown target {target!r}")
            continue
        wide_ok = bool(meta and meta.get("text_only"))
        lines += [f"{rel}: {p.code} {p.message}" for p in check_png(png, targets[target], palette, wide_ok)]
        if meta is None:
            continue
        recorded = meta.get("png", {}).get("pixels_sha256")
        if recorded is None:
            lines.append(f"{rel}: SP902 the sidecar records no pixel hash (written by an older styles-plot): rebuild")
        elif pixels_sha256(png) != recorded:
            lines.append(f"{rel}: SP902 the PNG's pixels changed after its sidecar was written")
        if not meta.get("publishable", True):
            lines.append(f"{rel}: SP903 a {target} figure is never published")
        waived += len(meta.get("waived", []))
        for p in meta.get("problems", []):
            fix = f" → {p['fix']}" if p.get("fix") else ""
            lines.append(f"{rel}: {p['code']} {p['message']} (saved in compat mode){fix}")
            records.append({"path": str(rel), **p})
        if registry is not None:
            for cell, st in meta.get("cells", {}).items():
                now = registry.get(meta["figure"], cell)
                if now is None or (now.timing, now.claim) != (st["timing"], st["claim"]):
                    lines.append(f"{rel}: SP904 cell {cell!r} changed in the registry since the figure was drawn")
        for key, s in meta.get("numbers", {}).items():
            numbers[key][s] = rel
    for key, strings in sorted(numbers.items()):
        if len(strings) > 1:
            where = ", ".join(f"{s!r} in {p}" for s, p in sorted(strings.items()))
            lines.append(f"SP502 data key {key!r} prints {len(strings)} strings: {where}")
    if args.json:  # one JSON object per problem; SP906 marked as a warning
        for line in lines + warnings:
            rec = next((r for r in records if line.startswith(f"{r['path']}: {r['code']}")), None)
            if rec is None:
                path, _, rest = line.partition(": ")
                code, _, message = rest.partition(" ")
                rec = {"path": path, "code": code, "message": message}
            if line in warnings:
                rec["warning"] = True
            print(json.dumps(rec, ensure_ascii=False))
        return 1 if lines else 0
    for line in lines + warnings:
        print(line)
    no_side = f", {len(warnings)} without a sidecar (SP906, a warning)" if warnings else ""
    print(f"styles-plot check: {len(pngs)} figure(s), {len(lines)} problem(s){no_side}"
          + (f", {waived} waived" if waived else ""))  # fmt: skip
    return 1 if lines else 0


def _sheet(args) -> int:
    root = Path(args.dir)
    pngs = figures_in(root)
    if args.order:  # one file name (or stem) per line: that order first, the rest after in name order
        wanted = [ln.strip() for ln in Path(args.order).read_text().splitlines() if ln.strip()]
        def name(p: Path) -> str:  # main/fig01_main_split: the path under DIR, without .png
            return p.relative_to(root).with_suffix("").as_posix()

        def wanted_name(n: str) -> str:
            return n[:-4] if n.endswith(".png") else n

        rank = {wanted_name(n): i for i, n in enumerate(wanted)}

        def rank_of(p: Path) -> int:  # by the path under DIR, or by the bare name when that is unique
            return rank.get(name(p), rank.get(p.stem, len(rank)))

        missing = [n for n in wanted if not any(wanted_name(n) in (name(p), p.stem) for p in pngs)]
        if missing:
            print(f"styles-plot sheet: not found under {root}: {', '.join(missing)}", file=sys.stderr)
            return 2
        pngs = sorted(pngs, key=lambda p: (rank_of(p), name(p)))
    if not pngs:
        print(f"styles-plot sheet: no PNGs under {root}", file=sys.stderr)
        return 2
    colour, gray = contact_sheets(pngs, Path(args.out or root), width=args.width, root=root)
    print(f"wrote {colour}\nwrote {gray}")
    return 0


def _key(args) -> int:
    from styles_plot._keyfig import key_figure

    vocab = load(args.vocab)
    out = Path(args.out)
    try:
        save(key_figure(vocab, args.target, out.stem), out, args.target)
    except StyleError as e:
        print(e, file=sys.stderr)
        return 1
    print(f"wrote {out}")
    return 0


def _palette(args) -> int:
    vocab = load(args.vocab) if args.vocab else None
    pal = vocab.palette if vocab else Palette()
    names = [*pal.role_slots, "control"]
    who = {r.slot: r.name for r in vocab.roles.values()} if vocab else {}
    print(f"{'pair':<22}{'normal':>8}{'deutan':>8}{'protan':>8}{'tritan':>8}{'min':>8}{'floor':>7}")
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            d = pal.distances(a, b)
            if d is None:
                print(f"{a}–{b}: needs styles-plot[check]")
                continue
            m, fl = min(d.values()), pal.floor(a, b)
            flag = "  may not share a figure" if m < fl else ""
            roles = f" ({who.get(a, a)} / {who.get(b, b)})" if vocab and (a in who or b in who) else ""
            print(f"{a + '–' + b:<22}" + "".join(f"{d[v]:>8.1f}" for v in ("normal", "deutan", "protan", "tritan"))
                  + f"{m:>8.1f}{fl:>7g}{flag}{roles}")  # fmt: skip
    return 0


INIT_FILES = ("plotstyle.toml", "status.csv", "first_figure.py")
_INIT_NAME = 'name = "my project"'
NEXT_STEPS = """next:
  1. python first_figure.py
  2. open figures/readme/first_figure.png
  3. rename the roles, units and entities in plotstyle.toml
  4. replace the synthetic data with yours and register each cell in status.csv
  5. styles-plot check figures/post --vocab plotstyle.toml"""


def _init(args) -> int:
    root = Path(args.dir)
    existing = [root / f for f in INIT_FILES if (root / f).exists()]
    if existing and not args.force:
        print("styles-plot init: these exist, nothing written (--force overwrites):", file=sys.stderr)
        for p in existing:
            print(f"  {p}", file=sys.stderr)
        return 2
    name = args.name or root.resolve().name or "my project"
    root.mkdir(parents=True, exist_ok=True)
    templates = files("styles_plot") / "data" / "init"
    for f in INIT_FILES:
        text = (templates / f).read_text(encoding="utf-8")
        if f == "plotstyle.toml":
            text = text.replace(_INIT_NAME, f"name = {json.dumps(name, ensure_ascii=False)}", 1)
        (root / f).write_text(text, encoding="utf-8")
        print(f"wrote {root / f}")
    print(NEXT_STEPS if root.resolve() == Path.cwd().resolve() else f"cd {root}\n{NEXT_STEPS}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="styles-plot", description="One figure grammar shared across projects.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check saved PNGs and their sidecars")
    c.add_argument("dir")
    c.add_argument("--vocab")
    c.add_argument("--target", default="post", help="target of PNGs without a sidecar (default post)")
    c.add_argument("--json", action="store_true", help="one JSON object per problem")
    s = sub.add_parser("sheet", help="contact sheets in colour and gray")
    s.add_argument("dir")
    s.add_argument("--width", type=int, default=720)
    s.add_argument("-o", "--out", help="directory for the sheets (default: the figures' directory)")
    s.add_argument("--order", help="a text file: one figure name per line, in reading order")
    k = sub.add_parser("key", help="draw the project's key figure")
    k.add_argument("--vocab", required=True)
    k.add_argument("-o", "--out", default="key.png")
    k.add_argument("--target", default="post")
    p = sub.add_parser("palette", help="colour-vision table of the palette's slots")
    p.add_argument("--vocab")
    i = sub.add_parser("init", help="write a starter plotstyle.toml, status.csv and first_figure.py")
    i.add_argument("dir", nargs="?", default=".")
    i.add_argument("--name", help="the project's name (default: the folder's name)")
    i.add_argument("--force", action="store_true", help="overwrite the three files if they exist")
    args = ap.parse_args(argv)
    try:
        return {"check": _check, "sheet": _sheet, "key": _key, "palette": _palette, "init": _init}[args.cmd](args)
    except VocabError as e:
        print(f"styles-plot: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
