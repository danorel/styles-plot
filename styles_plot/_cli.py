"""The styles-plot command.

    styles-plot check <dir> [--vocab plotstyle.toml] [--target post]   saved PNGs: size, background, palette; with
                                                                       sidecars: meaning, staleness, one key one string
    styles-plot sheet <dir> [--width 720] [-o DIR] [--order FILE]      contact sheets, colour and gray
    styles-plot key --vocab plotstyle.toml [-o key.png] [--target post] the project's key figure
    styles-plot palette [--vocab plotstyle.toml]                       colour-vision table of the slots
    styles-plot init [DIR] [--name NAME] [--force]                     a starter vocabulary, registry and figure
    styles-plot todo <out> [--vocab plotstyle.toml] [--write-vocab [FILE]]  what the last saves left to fix
    styles-plot vocab lint --vocab plotstyle.toml                      near-duplicate canonical terms
    styles-plot build module:SET [--only GLOB] [--target T] [--jobs N] [--mode M]   save a figure set
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from importlib.resources import files
from pathlib import Path

from styles_plot._checks import ERROR_FROM, is_warning
from styles_plot._palette import Palette
from styles_plot._png import check_png, pixels_sha256
from styles_plot._registry import load as load_registry
from styles_plot._save import PROBLEMS, StyleError, find_sidecar, save
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
    lines, warnings, notes, numbers, records, waived = [], [], [], defaultdict(dict), [], 0
    pngs = figures_in(root)
    sidecar_dirs = tuple(dict.fromkeys([vocab.sidecar_dir if vocab else "", "_meta"]))
    for png in pngs:
        rel = png.relative_to(root)
        side = find_sidecar(png, root, sidecar_dirs)
        meta = json.loads(side.read_text()) if side else None
        if meta is None:  # a warning while ERROR_FROM says so: it can fail a run that passed before
            line = f"{rel}: SP906 no sidecar: meaning and staleness not checked (only the PNG)"
            (warnings if is_warning("SP906") else lines).append(line)
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
        stale = _vocab_changed(meta, vocab) if vocab is not None else None
        if stale is not None:
            (warnings if is_warning("SP907") else lines).append(f"{rel}: SP907 {stale}")
        if meta.get("waived"):  # not a problem: a person looked and accepted it; said per figure and in the summary
            waived += len(meta["waived"])
            codes = ", ".join(sorted({w["code"] for w in meta["waived"]}))
            notes.append(f"{rel}: {len(meta['waived'])} waived ({codes})")
        for p in meta.get("problems", []):
            if is_warning(p["code"]):
                fix = f" → {p['fix']}" if p.get("fix") else ""
                warnings.append(f"{rel}: {p['code']} {p['message']} (a warning until {ERROR_FROM[p['code']]}){fix}")
                continue
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
    for line in lines + warnings + notes:
        print(line)
    n_side = sum(": SP906 " in w for w in warnings)
    n_vocab = sum(": SP907 " in w for w in warnings)
    no_side = f", {n_side} without a sidecar (SP906, a warning)" if n_side else ""
    no_side += f", {n_vocab} saved with another vocabulary (SP907, a warning)" if n_vocab else ""
    rest = len(warnings) - n_side - n_vocab
    no_side += f", {rest} warning(s)" if rest else ""
    print(f"styles-plot check: {len(pngs)} figure(s), {len(lines)} problem(s){no_side}"
          + (f", {waived} waived" if waived else ""))  # fmt: skip
    return 1 if lines else 0


def _vocab_changed(meta: dict, vocab) -> str | None:
    """SP907's message when the sidecar's vocabulary hash is not the given vocabulary's, else None. A sidecar from
    0.2.1 or earlier hashed the files' bytes: it matches either hash (until 0.3), and a comment edit since then shows
    as a change, since a byte hash cannot tell a comment from a term."""
    rec = meta.get("vocab") or {}
    sha = rec.get("sha256")
    if not sha:
        return None
    if rec.get("hash") == "meaning":
        if sha == vocab.meaning_sha256:
            return None
        return "vocabulary changed since save: meaning checks ran against the current vocabulary"
    from styles_plot._save import bytes_sha

    if sha in (vocab.meaning_sha256, bytes_sha(vocab)):
        return None
    return ("vocabulary changed since save: meaning checks ran against the current vocabulary (this sidecar hashed "
            "the file's bytes, so a comment edit counts too: save again to record its meaning)")


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


def _todo(args) -> int:
    root = Path(args.dir)
    files = sorted(root.rglob(f"_meta/{PROBLEMS}"))
    if not files:
        print(f"styles-plot todo: no _meta/{PROBLEMS} under {root} (save, save_bundle and build write it)",
              file=sys.stderr)  # fmt: skip
        return 2
    words: dict[str, None] = {}
    cells: dict[str, None] = {}
    rest: list[str] = []
    clean = figures = 0
    for f in files:
        for fig, by_target in json.loads(f.read_text()).items():
            figures += 1
            clean += all(not ps for ps in by_target.values())
            for target, ps in sorted(by_target.items()):
                for p in ps:
                    if p["code"] == "SP401" and p.get("subject"):
                        words[p["subject"]] = None
                    elif p["code"] == "SP203" and p.get("subject"):
                        cells[f"{p['figure'] or fig},{p['subject']},<timing>,<claim>,,,"] = None
                    else:
                        fix = f" → {p['fix']}" if p.get("fix") else ""
                        rest.append(f"{fig} [{target}]: {p['code']} {p['message']}{fix}")
    if words:
        print("words to add (plotstyle.toml [terms]; or --write-vocab):")
        print("  canonical = [..., " + ", ".join(json.dumps(w, ensure_ascii=False) for w in words) + "]")
    if cells:
        print("cells to register (status.csv; a status is a decision: fill in timing and claim):")
        for line in cells:
            print(f"  {line}")
    if rest:
        print("the rest:")
        for line in dict.fromkeys(rest):
            print(f"  {line}")
    print(f"styles-plot todo: {figures} figure(s), {clean} clean; {len(words)} word(s), {len(cells)} cell(s), "
          f"{len(dict.fromkeys(rest))} other problem(s)")  # fmt: skip
    if args.write_vocab is not None:
        return _write_vocab(args, list(words))
    return 0


ADDED = "plotstyle.added.toml"


def _write_vocab(args, words: list[str]) -> int:
    """Append the missing words to FILE (beside the vocabulary), each with the date it was added; refuse banned ones;
    never touch the registry."""
    import datetime

    if not args.vocab:
        print("styles-plot todo --write-vocab: needs --vocab plotstyle.toml", file=sys.stderr)
        return 2
    vocab = load(args.vocab)
    target = Path(args.vocab).parent / (args.write_vocab or ADDED)
    have: dict[str, str] = {}
    if target.exists():
        for line in target.read_text(encoding="utf-8").splitlines():
            m = re.match(r'\s*("(?:[^"\\]|\\.)*"),\s*#\s*(.*)$', line)
            if m:
                have[json.loads(m.group(1))] = m.group(2)
    today = datetime.date.today().isoformat()
    added, refused = [], []
    for w in words:
        if vocab.banned_hits(w):
            refused.append(f"{w!r} ({', '.join(vocab.banned_hits(w))})")
        elif w not in have and w not in vocab.canonical:
            have[w] = f"added by styles-plot todo, {today}"
            added.append(w)
    body = "".join(f"    {json.dumps(w, ensure_ascii=False)},  # {note}\n" for w, note in have.items())
    target.write_text("# Words styles-plot todo found missing. Review them in the diff; move them to plotstyle.toml "
                      "when you like.\n[terms]\ncanonical = [\n" + body + "]\n", encoding="utf-8")  # fmt: skip
    for r in refused:
        print(f"refused (banned): {r}")
    print(f"wrote {target}: {len(added)} word(s) added")
    included = {Path(p).resolve() for p in vocab.includes}
    if target.resolve() not in included:
        print(f'add to {args.vocab}:\n  [include]\n  files = ["{target.name}"]')
    return 1 if refused else 0


def _vocab(args) -> int:
    from styles_plot._lint import near_duplicates

    pairs = near_duplicates(load(args.vocab).canonical)
    for a, b, why in pairs:
        print(f"{a!r} / {b!r}: {why}")
    print(f"styles-plot vocab lint: {len(pairs)} near-duplicate pair(s) (a report: nothing fails)")
    return 0


def _build(args) -> int:
    from styles_plot._build import load_set
    from styles_plot._render import BuildError

    try:
        fs = load_set(args.set)
        report = fs.build(only=args.only, targets=args.target, jobs=args.jobs, mode=args.mode)
    except BuildError as e:
        print(f"styles-plot build: {e}", file=sys.stderr)
        return 2
    for f in report.figures:
        if f["ok"]:
            warned = sum(len(ps) for ps in f["problems"].values())
            print(f"ok    {f['id']}" + (f"  ({warned} problem(s) recorded)" if warned else ""))
        else:
            print(f"FAIL  {f['id']}\n" + "\n".join(f"      {line}" for line in f["error"].splitlines()))
    n, bad = len(report.figures), len(report.failed)
    print(f"styles-plot build: {n} figure(s), {bad} failed, {report.seconds:.1f} s at --jobs {args.jobs}; "
          f"index: {report.out / '_meta' / 'index.json'}")  # fmt: skip
    return 1 if bad else 0


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
    t = sub.add_parser("todo", help="what the last saves under a folder left to fix, grouped")
    t.add_argument("dir")
    t.add_argument("--vocab", help="the vocabulary (needed by --write-vocab)")
    t.add_argument("--write-vocab", nargs="?", const="", default=None, metavar="FILE",
                   help=f"write the missing words to FILE beside the vocabulary (default {ADDED})")  # fmt: skip
    vc = sub.add_parser("vocab", help="vocabulary upkeep")
    vsub = vc.add_subparsers(dest="vocab_cmd", required=True)
    lint = vsub.add_parser("lint", help="near-duplicate canonical terms (a report)")
    lint.add_argument("--vocab", required=True)
    b = sub.add_parser("build", help="save a FigureSet's figures and write its index")
    b.add_argument("set", help="module:NAME or path/to/file.py:NAME")
    b.add_argument("--only", nargs="+", metavar="GLOB", help="figure ids matching any of these patterns")
    b.add_argument("--target", nargs="+", help="only these targets")
    b.add_argument("--jobs", type=int, default=1, help="worker processes (default 1)")
    b.add_argument("--mode", choices=("strict", "compat"), help="override the set's mode")
    i = sub.add_parser("init", help="write a starter plotstyle.toml, status.csv and first_figure.py")
    i.add_argument("dir", nargs="?", default=".")
    i.add_argument("--name", help="the project's name (default: the folder's name)")
    i.add_argument("--force", action="store_true", help="overwrite the three files if they exist")
    args = ap.parse_args(argv)
    try:
        return {"check": _check, "sheet": _sheet, "key": _key, "palette": _palette, "init": _init,
                "todo": _todo, "vocab": _vocab, "build": _build}[args.cmd](args)
    except VocabError as e:
        print(f"styles-plot: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
