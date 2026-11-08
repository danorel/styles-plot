from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")

import styles_plot as sp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


@pytest.fixture
def vocab_dir(tmp_path: Path) -> Path:
    """A copy of the examples' vocabulary and registry, safe to edit."""
    shutil.copy(EXAMPLES / "plotstyle.toml", tmp_path / "plotstyle.toml")
    shutil.copy(EXAMPLES / "status.csv", tmp_path / "status.csv")
    return tmp_path


@pytest.fixture
def vocab(vocab_dir: Path) -> sp.Vocab:
    return sp.load(vocab_dir / "plotstyle.toml")


def example(name: str):
    """An example module: a figure type from examples/blocks/, else examples/<name>.py (gallery)."""
    path = EXAMPLES / "blocks" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"example_{name}", path if path.exists() else EXAMPLES / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # a dataclass in the module looks itself up here
    spec.loader.exec_module(mod)
    return mod


def codes(problems) -> set[str]:
    return {p.code for p in problems}

