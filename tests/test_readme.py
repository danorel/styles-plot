"""The README's generated blocks and its link check (docs/readme_blocks.py)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def rb():
    spec = importlib.util.spec_from_file_location("readme_blocks", ROOT / "docs" / "readme_blocks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_blocks_are_the_real_error_and_the_init_template(rb):
    b = rb.blocks()
    assert "SP401 header 'recall'" in b["refused"] and "SP203 cell 'acc.m2'" in b["refused"]
    assert '@FIGURES.figure("first_figure"' in b["first-figure"]
    text = "a\n<!-- refused:start -->\nold\n<!-- refused:end -->\nb\n<!-- first-figure:start -->\n<!-- first-figure:end -->\n"
    out = rb.fill(text, b)
    assert "old" not in out and b["refused"] in out and b["first-figure"] in out
    assert rb.fill(out, b) == out  # idempotent


def test_readme_is_up_to_date_and_its_links_resolve(rb):
    text = (ROOT / "README.md").read_text()
    assert rb.fill(text, rb.blocks()) == text
    assert rb.check_links(text) == []
    assert rb.check_links("[x](docs/nowhere.md) [y](https://example.org) [z](#top)") == [
        "README.md links to docs/nowhere.md, which does not exist"]
