"""Figure sets and the build command.

A `FigureSet` names a project's figures: each is a function that receives a ready `Figure` (its id, vocabulary, title
and caption) and adds its blocks. `styles-plot build module:SET` (or `SET.build()`) saves every figure for its targets,
all or nothing per figure, writes `<out>/_meta/index.json` and `<out>/_meta/problems.json`, and goes on past a figure
that fails. With `jobs > 1` the figures are built in worker processes (the `spawn` start method): each worker imports
the set's module itself and gets figure ids, never pickled figures. No cache: the library cannot see which data files a
builder reads, so a cache would go stale without a word; `only=` covers the edit loop.
"""

from __future__ import annotations

import fnmatch
import importlib
import importlib.util
import json
import multiprocessing
import os
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from styles_plot._render import BuildError, Figure

INDEX = "index.json"


@dataclass
class _Entry:
    id: str
    make: Callable
    order: float | None
    title: str
    caption: str
    targets: tuple[str, ...] | None
    figure: dict = field(default_factory=dict)  # more Figure(...) keywords: subtitle, read, numbers, waive...


class FigureSet:
    """A project's figures, saved together: `out` is the folder (each target in `<out>/<target>/`), `targets` the
    default targets, `mode` "strict" or "compat".

        WRITEUP = sp.FigureSet("writeup", vocab, out="figures/writeup", targets=("post", "readme"))

        @WRITEUP.figure("fig01_main_split", order=1, title="…", caption="…")
        def fig01(fig: sp.Figure) -> None:
            fig.add(table)
    """

    def __init__(self, name: str, vocab, out, targets: Iterable[str] = ("post",), mode: str = "strict"):
        self.name = name
        self.vocab = vocab
        self.out = Path(out)
        self.targets = tuple(targets)
        self.mode = mode
        self._entries: dict[str, _Entry] = {}
        self._source = _caller_file()

    def figure(self, id: str, order: float | None = None, title: str = "", caption: str = "",
               targets: Iterable[str] | None = None, **figure) -> Callable:  # fmt: skip
        """Register a builder: it receives `Figure(id, vocab, title=, caption=, **figure)` and adds blocks to it (or
        returns a Figure of the same id, built its own way). `targets` overrides the set's."""

        def register(make: Callable) -> Callable:
            if id in self._entries:
                raise BuildError(f"figure set {self.name!r}: figure {id!r} is registered twice")
            self._entries[id] = _Entry(id, make, order, title, caption, tuple(targets) if targets else None, figure)
            return make

        return register

    def ids(self) -> list[str]:
        """The figure ids in order: by `order`, then in the order they were registered."""
        regs = list(self._entries.values())
        return [e.id for e in sorted(regs, key=lambda e: (e.order is None, e.order or 0, regs.index(e)))]

    def make(self, id: str) -> Figure:
        """The figure with this id, built."""
        try:
            e = self._entries[id]
        except KeyError:
            raise BuildError(f"figure set {self.name!r} has no figure {id!r}") from None
        fig = Figure(id, self.vocab, title=e.title, caption=e.caption, **e.figure)
        made = e.make(fig)
        if made is None:
            return fig
        if not isinstance(made, Figure) or made.id != id:
            raise BuildError(f"figure set {self.name!r}: the builder of {id!r} returned {made!r}; add blocks to the "
                             "figure it receives, or return a Figure with the same id")  # fmt: skip
        return made

    def targets_of(self, id: str) -> tuple[str, ...]:
        return self._entries[id].targets or self.targets

    def select(self, only: Iterable[str] | None = None) -> list[str]:
        """The ids matching any of the glob patterns (all when none)."""
        pats = list(only or [])
        ids = self.ids()
        if not pats:
            return ids
        chosen = [i for i in ids if any(fnmatch.fnmatchcase(i, p) for p in pats)]
        if not chosen:
            raise BuildError(f"figure set {self.name!r}: no figure matches {', '.join(pats)}")
        return chosen

    def build(self, only: Iterable[str] | None = None, targets: Iterable[str] | None = None, jobs: int = 1,
              mode: str | None = None, out: str | Path | None = None) -> BuildReport:  # fmt: skip
        """Save the selected figures (all their targets, or nothing, each) and write the index; see the module."""
        out = Path(out) if out is not None else self.out
        ids = self.select(only)
        want = tuple(targets) if targets else None
        mode = mode or self.mode
        start = time.perf_counter()
        if jobs <= 1:
            results = [_build_one(self, i, want, mode, out) for i in ids]
        else:
            if self._source is None:
                raise BuildError(f"figure set {self.name!r}: jobs > 1 needs the set defined in a module file")
            ctx = multiprocessing.get_context("spawn")
            with ProcessPoolExecutor(max_workers=jobs, mp_context=ctx) as pool:
                results = list(pool.map(_work, [(str(self._source), self.name, i, want, mode, str(out)) for i in ids]))
        seconds = time.perf_counter() - start
        from styles_plot._save import Problem, record_problems

        for r in results:  # one writer for problems.json and index.json, whatever the number of workers
            if r["problems"]:
                record_problems(out, r["id"], {t: [Problem(**_problem_args(p)) for p in ps]
                                               for t, ps in r["problems"].items()})  # fmt: skip
        _write_index(out, self, results)
        return BuildReport(results, seconds, out)


@dataclass
class BuildReport:
    figures: list[dict]
    seconds: float
    out: Path

    @property
    def failed(self) -> list[dict]:
        return [f for f in self.figures if not f["ok"]]


def _problem_args(d: dict) -> dict:
    out = {k: d[k] for k in ("code", "message", "figure", "subject", "where", "fix") if k in d}
    for k in ("bbox_in", "obstacle_in"):
        if d.get(k):
            out[k] = tuple(d[k])
    return out


def _caller_file() -> Path | None:
    """The file of the module that made the set (for workers to import it again)."""
    frame = sys._getframe(2)
    f = frame.f_globals.get("__file__")
    return Path(f).resolve() if f else None


def _build_one(fs: FigureSet, id: str, want, mode: str, out: Path) -> dict:
    from styles_plot._save import StyleError, bundle

    targets = tuple(t for t in fs.targets_of(id) if want is None or t in want)
    rec = {"id": id, "targets": list(targets), "ok": True, "error": "", "png": {}, "problems": {}, "waived": {},
           "title": "", "caption": "", "order": fs._entries[id].order}  # fmt: skip
    try:
        fig = fs.make(id)
        rec["title"], rec["caption"] = fig.title, fig.caption
        if targets:
            reports = bundle(fig, out, targets, mode, record=False)
            for t, r in reports.items():
                rec["png"][t] = str(r.path.relative_to(out))
                rec["problems"][t] = [p.as_dict() for p in r.problems]
                rec["waived"][t] = r.waived
    except StyleError as e:
        rec["ok"], rec["error"] = False, str(e)
        rec["problems"] = _by_target(e.problems, targets)
    except Exception as e:  # a builder's own bug: say which figure, keep going
        rec["ok"] = False
        rec["error"] = f"{type(e).__name__}: {e}"
    return rec


def _by_target(problems, targets) -> dict:
    """A strict refusal's problems, back per target ("figure [target]" names them in a bundle)."""
    out: dict[str, list] = {t: [] for t in targets}
    for p in problems:
        t = next((t for t in targets if p.figure.endswith(f"[{t}]")), targets[0] if targets else "")
        d = p.as_dict()
        d["figure"] = p.figure.split(" [")[0]
        out.setdefault(t, []).append(d)
    return out


_MODULES: dict[str, object] = {}


def load_set(source: str, name: str | None = None) -> FigureSet:
    """A FigureSet from `module:NAME`, `path/to/file.py:NAME`, or a file and a set name."""
    if name is None:
        source, _, name = source.rpartition(":")
        if not source:
            raise BuildError("give the set as module:NAME or path/to/file.py:NAME")
    mod = _MODULES.get(source)
    if mod is None:
        if source.endswith(".py") or os.sep in source or "/" in source:
            path = Path(source).resolve()
            if not path.exists():
                raise BuildError(f"no such file: {source}")
            spec = importlib.util.spec_from_file_location(f"styles_plot_set_{abs(hash(str(path)))}", path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            sys.path.insert(0, str(path.parent))
            spec.loader.exec_module(mod)
        else:
            if "" not in sys.path and os.getcwd() not in sys.path:
                sys.path.insert(0, os.getcwd())
            mod = importlib.import_module(source)
        _MODULES[source] = mod
    obj = getattr(mod, name, None)
    if not isinstance(obj, FigureSet):
        sets = [k for k, v in vars(mod).items() if isinstance(v, FigureSet)]
        obj = next((v for v in vars(mod).values() if isinstance(v, FigureSet) and v.name == name), None)
        if obj is None:
            raise BuildError(f"{source} has no FigureSet {name!r} (it has: {', '.join(sets) or 'none'})")
    return obj


def _work(args) -> dict:
    """A worker: import the set's module (once per process) and build one figure."""
    source, name, id, want, mode, out = args
    fs = load_set(source, name)
    return _build_one(fs, id, want, mode, Path(out))


def _write_index(out: Path, fs: FigureSet, results: list[dict]) -> Path:
    """<out>/_meta/index.json: one entry per figure, in the set's order; a partial build (`only=`) updates its
    figures and keeps the others."""
    path = out / "_meta" / INDEX
    old = {}
    if path.exists():
        try:
            old = {f["id"]: f for f in json.loads(path.read_text()).get("figures", [])}
        except (json.JSONDecodeError, KeyError, TypeError):
            old = {}
    for r in results:
        old[r["id"]] = {k: r[k] for k in ("id", "order", "title", "caption", "targets", "png", "problems", "waived",
                                          "ok", "error")}  # fmt: skip
    rank = {i: n for n, i in enumerate(fs.ids())}
    figures = sorted(old.values(), key=lambda f: (rank.get(f["id"], len(rank)), f["id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".json", dir=path.parent)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps({"set": fs.name, "figures": figures}, indent=1, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return path
