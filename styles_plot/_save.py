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
import warnings
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from styles_plot import _checks
from styles_plot._checks._base import Problem
from styles_plot._png import check_png
from styles_plot._render import Figure, RenderInfo, info
from styles_plot._tags import DATA_KINDS, tags

MODES = ("strict", "compat")
SIDECAR_SUFFIX = ".styles.json"


class StyleError(ValueError):
    """A figure that breaks the grammar; nothing was written."""

    def __init__(self, problems: list[Problem]):
        self.problems = list(problems)
        lines = "\n".join(f"  {p}" for p in self.problems)
        super().__init__(f"{len(self.problems)} problem(s), nothing written:\n{lines}")


class StyleWarning(UserWarning):
    """A problem reported in compat mode (or on the notebook target) instead of refusing the figure."""


@dataclass
class SaveReport:
    path: Path
    sidecar: Path
    target: str
    problems: list[Problem] = field(default_factory=list)


def sidecar_path(png: str | Path) -> Path:
    png = Path(png)
    return png.with_name(png.stem + SIDECAR_SUFFIX)


def check_figure(fig: Figure, target: str) -> list[Problem]:
    """Render a figure for a target and return every problem, writing nothing."""
    return _checks.run(fig.render(target))


def save(fig: Figure, path: str | Path, target: str, *, mode: str = "strict") -> SaveReport:
    """Render, check and write one figure for one target. Strict mode raises StyleError on any problem and writes
    nothing; compat mode (and the notebook target) warns and writes, recording the problems in the sidecar."""
    _mode(mode)
    mpl, problems = _prepare(fig, target)
    return _write(mpl, problems, Path(path), mode)


def save_bundle(fig: Figure, out_dir: str | Path, targets: Iterable[str] = ("post", "slide", "readme"), *,
                mode: str = "strict") -> dict[str, SaveReport]:  # fmt: skip
    """One figure for several targets, at <out_dir>/<target>/<figure id>.png. In strict mode every target is checked
    before anything is written, so a bundle is never half-saved."""
    _mode(mode)
    prepared = {t: _prepare(fig, t) for t in targets}
    if mode == "strict":
        blocking = [p for t, (mpl, ps) in prepared.items() if info(mpl).theme.publishable for p in _tagged(ps, t)]
        if blocking:
            raise StyleError(blocking)
    return {t: _write(mpl, ps, Path(out_dir) / t / f"{fig.id}.png", mode) for t, (mpl, ps) in prepared.items()}


def _mode(mode: str) -> None:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")


def _tagged(problems: list[Problem], target: str) -> list[Problem]:
    return [Problem(p.code, p.message, f"{p.figure} [{target}]") for p in problems]


def _prepare(fig: Figure, target: str):
    mpl = fig.render(target)
    return mpl, _checks.run(mpl)


def _write(mpl, problems: list[Problem], path: Path, mode: str) -> SaveReport:
    i = info(mpl)
    strict = mode == "strict" and i.theme.publishable
    if problems and strict:
        raise StyleError(problems)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".png", dir=path.parent)
    os.close(fd)
    try:
        mpl.savefig(tmp, dpi=i.theme.dpi, facecolor=i.vocab.palette.chrome["background"])
        png_problems = check_png(tmp, i.theme, i.vocab.palette) if i.theme.strict_layout else []
        png_problems = [Problem(p.code, p.message, i.figure) for p in png_problems]
        if png_problems and strict:
            raise StyleError(png_problems)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    problems = problems + png_problems
    for p in problems:
        warnings.warn(str(p), StyleWarning, stacklevel=3)
    side = sidecar_path(path)
    side.write_text(json.dumps(_sidecar(mpl, i, path, mode, problems), indent=1, ensure_ascii=False) + "\n")
    return SaveReport(path, side, i.target, problems)


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
    return {
        "styles_plot": __version__,
        "vocab": {"project": i.vocab.project, "sha256": _sha(i.vocab.source)},
        "registry": {"path": str(reg) if reg else None, "sha256": _sha(reg)},
        "figure": i.figure,
        "target": i.target,
        "mode": mode,
        "publishable": i.theme.publishable,
        "png": {"sha256": _sha(png), "dpi": i.theme.dpi},
        "roles": sorted(roles),
        "controls": sorted(controls),
        "cells": dict(sorted(cells.items())),
        "marks": marks,
        "key": key,
        "numbers": dict(i.numbers),
        "problems": [{"code": p.code, "message": p.message} for p in problems],
    }
