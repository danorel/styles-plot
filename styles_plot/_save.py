"""Saving: render for a target, run every check, refuse to write in strict mode on any problem, else write the PNG and
its sidecar (`<stem>.styles.json`: what the figure draws and means, read back by `styles-plot check`).

`save_bundle` renders one figure for several targets (post, slide, readme...) into `<out_dir>/<target>/<id>.png`;
in strict mode it writes nothing unless every target passes.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import replace
import warnings
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from styles_plot import _checks
from styles_plot._checks._base import Problem
from styles_plot._png import check_png, pixels_sha256
from styles_plot._render import Figure, RenderInfo, info
from styles_plot._tags import DATA_KINDS, tags

MODES = ("strict", "compat")
SIDECAR_SUFFIX = ".styles.json"


class StyleError(ValueError):
    """A figure that breaks the grammar; nothing was written."""

    def __init__(self, problems: list[Problem], target: str | None = None):
        self.problems = list(problems)
        lines = "\n".join(f"  {p}" for p in self.problems)
        hint = f'\nsee them drawn: sp.debug(fig, "{target}")' if target else "\nsee them drawn: sp.debug(fig, target)"
        super().__init__(f"{len(self.problems)} problem(s), nothing written:\n{lines}{hint}")


class StyleWarning(UserWarning):
    """A problem reported in compat mode (or on the notebook target) instead of refusing the figure."""


@dataclass
class SaveReport:
    path: Path
    sidecar: Path
    target: str
    problems: list[Problem] = field(default_factory=list)
    waived: list[dict] = field(default_factory=list)  # {code, subject, reason} per waived problem


def sidecar_path(png: str | Path, root: str | Path | None = None, sidecar_dir: str = "") -> Path:
    """Beside the PNG, or with a sidecar_dir under the figure set's root, keeping the PNG's path relative to it:
    <root>/main/fig01.png -> <root>/_meta/main/fig01.styles.json."""
    png = Path(png)
    if not sidecar_dir:
        return png.with_name(png.stem + SIDECAR_SUFFIX)
    root = Path(root) if root is not None else png.parent
    rel = png.relative_to(root)
    return root / sidecar_dir / rel.with_name(rel.stem + SIDECAR_SUFFIX)


def find_sidecar(png: Path, top: Path, sidecar_dirs=("_meta",)) -> Path | None:
    """A saved PNG's sidecar, wherever `save` may have put it: beside the PNG, else under <folder>/<sidecar_dir>/ of
    the PNG's own folder and of each folder above it, up to `top` (the folder being checked). The first hit wins."""
    png, top = Path(png), Path(top)
    beside = sidecar_path(png)
    if beside.exists():
        return beside
    folder = png.parent
    while True:
        for d in sidecar_dirs:
            if d and (side := sidecar_path(png, folder, d)).exists():
                return side
        if folder == top or top not in folder.parents:
            return None
        folder = folder.parent


DEBUG_DIR = "_debug"
DEBUG_RED = "#d62728"  # the debug picture's own colour: never published, so outside the palette by design


def debug(fig: Figure, target: str = "post", out: str | Path = ".") -> list[Problem]:
    """Render a figure for a target, run every check, and write <out>/_debug/<id>.<target>.png: the figure with each
    problem's subject boxed in red, its obstacle boxed in dashed red, and the code beside it. Never publishable: no
    sidecar, and `styles-plot check` and `sheet` skip _debug/. Returns the problems."""
    from matplotlib.patches import Rectangle

    mpl = fig.render(target)
    problems = _checks.run(mpl)  # waived problems are not drawn
    w, h = mpl.get_size_inches()
    for p in problems:
        for box, style in ((p.bbox_in, "-"), (p.obstacle_in, "--")):
            if not box:
                continue
            x0, y0, x1, y1 = box
            mpl.add_artist(Rectangle((x0 / w, y0 / h), (x1 - x0) / w, (y1 - y0) / h, transform=mpl.transFigure,
                                     fill=False, edgecolor=DEBUG_RED, lw=1.4, ls=style, zorder=100))  # fmt: skip
        if p.bbox_in:
            mpl.text(p.bbox_in[2] / w + 0.003, p.bbox_in[3] / h, p.code, transform=mpl.transFigure, color=DEBUG_RED,
                     fontsize=8, va="bottom", zorder=101)  # fmt: skip
    path = Path(out) / DEBUG_DIR / f"{fig.id}.{target}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    mpl.savefig(path, dpi=info(mpl).theme.dpi, facecolor=info(mpl).vocab.palette.chrome["background"])
    return problems


def check_figure(fig: Figure, target: str) -> list[Problem]:
    """Render a figure for a target and return every problem not waived, writing nothing."""
    return _checks.run(fig.render(target))


def save(fig: Figure, path: str | Path, target: str, *, mode: str = "strict",
         root: str | Path | None = None) -> SaveReport:  # fmt: skip
    """Render, check and write one figure for one target. Strict mode raises StyleError on any problem and writes
    nothing; compat mode (and the notebook target) warns and writes, recording the problems in the sidecar. `root` is
    the figure set's folder: with [output].sidecar_dir the sidecar goes under it (default: the PNG's folder)."""
    _mode(mode)
    mpl, problems, waived = _prepare(fig, target)
    return _write(mpl, problems, waived, Path(path), mode, root)


def save_bundle(fig: Figure, out_dir: str | Path, targets: Iterable[str] = ("post", "slide", "readme"), *,
                mode: str = "strict") -> dict[str, SaveReport]:  # fmt: skip
    """One figure for several targets, at <out_dir>/<target>/<figure id>.png. In strict mode every target is checked
    before anything is written, so a bundle is never half-saved."""
    _mode(mode)
    prepared = {t: _prepare(fig, t) for t in targets}
    if mode == "strict":
        blocking = [p for t, (mpl, ps, _) in prepared.items() if info(mpl).theme.publishable for p in _tagged(ps, t)]
        if blocking:
            raise StyleError(blocking)
    return {t: _write(mpl, ps, wv, Path(out_dir) / t / f"{fig.id}.png", mode, Path(out_dir) / t)
            for t, (mpl, ps, wv) in prepared.items()}  # fmt: skip


def _mode(mode: str) -> None:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")


def _tagged(problems: list[Problem], target: str) -> list[Problem]:
    return [replace(p, figure=f"{p.figure} [{target}]") for p in problems]


def _prepare(fig: Figure, target: str):
    mpl = fig.render(target)
    return (mpl, *_checks.evaluate(mpl))


def _write(mpl, problems: list[Problem], waived: list[dict], path: Path, mode: str,
           root: str | Path | None = None) -> SaveReport:  # fmt: skip
    i = info(mpl)
    strict = mode == "strict" and i.theme.publishable
    if problems and strict:
        raise StyleError(problems, i.target)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".png", dir=path.parent)
    os.close(fd)
    try:
        # no "Software" stamp: the PNG's bytes should not change with the matplotlib version
        mpl.savefig(tmp, dpi=i.theme.dpi, facecolor=i.vocab.palette.chrome["background"], metadata={"Software": None})
        png_problems = check_png(tmp, i.theme, i.vocab.palette, i.text_only) if i.theme.strict_layout else []
        png_problems = [Problem(p.code, p.message, i.figure) for p in png_problems]
        if png_problems and strict:
            raise StyleError(png_problems, i.target)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    problems = problems + png_problems
    for p in problems:
        warnings.warn(str(p), StyleWarning, stacklevel=3)
    side = sidecar_path(path, root, i.vocab.sidecar_dir)
    side.parent.mkdir(parents=True, exist_ok=True)
    meta = _sidecar(mpl, i, path, mode, problems)
    if waived:
        meta["waived"] = waived
    side.write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")
    return SaveReport(path, side, i.target, problems, waived)


def _sha(path: Path | None) -> str | None:
    if path is None or not Path(path).exists():
        return None
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _sidecar(mpl, i: RenderInfo, png: Path, mode: str, problems: list[Problem]) -> dict:
    from styles_plot import __version__

    marks, cells, roles, controls = [], {}, set(), set()
    for a in mpl.findobj(lambda a: tags(a).get("kind") in DATA_KINDS):
        t = tags(a)
        marks.append({k: t.get(k) for k in ("kind", "role", "cell", "timing", "claim", "hollow") if k in t})
        if t.get("cell"):
            cells[t["cell"]] = {"timing": t.get("timing"), "claim": t.get("claim")}
        if t.get("role") not in (None, "control", "other"):
            roles.add(t["role"])
        if t.get("control"):
            controls.add(t["control"])
    key = sorted({a.get_text() for a in mpl.findobj(lambda a: tags(a).get("kind") == "key")})
    reg = i.registry.path if i.registry is not None else None
    shown = None
    if reg is not None:  # relative to the vocabulary file: a sidecar never records a machine's paths
        base = i.vocab.source.parent if i.vocab.source else None
        try:
            shown = str(Path(os.path.relpath(reg, base))) if base else Path(reg).name
        except ValueError:  # pragma: no cover - another drive on Windows
            shown = Path(reg).name
    return {
        "styles_plot": __version__,
        "vocab": {"project": i.vocab.project, "sha256": _sha(i.vocab.source)},
        "registry": {"path": shown, "sha256": _sha(reg)},
        "figure": i.figure,
        "target": i.target,
        "mode": mode,
        "publishable": i.theme.publishable,
        "text_only": i.text_only,
        "png": {"pixels_sha256": pixels_sha256(png), "dpi": i.theme.dpi},
        "roles": sorted(roles),
        "controls": sorted(controls),
        "cells": dict(sorted(cells.items())),
        "marks": marks,
        "key": key,
        "numbers": dict(i.numbers),
        "problems": [p.as_dict() for p in problems],
    }
