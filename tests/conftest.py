from __future__ import annotations

import importlib.util
import shutil
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
    spec = importlib.util.spec_from_file_location(f"example_{name}", EXAMPLES / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def codes(problems) -> set[str]:
    return {p.code for p in problems}

