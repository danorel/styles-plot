"""`styles-plot init`: the starter files load, draw a strict-passing figure, and are never overwritten by accident."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from importlib.resources import files

import pytest

import styles_plot as sp
from styles_plot._cli import INIT_FILES, main


def test_init_then_first_figure_passes_strict(tmp_path, capsys):
    assert main(["init", str(tmp_path), "--name", "demo"]) == 0
    out = capsys.readouterr().out
    assert "python first_figure.py" in out and "styles-plot check figures/post --vocab plotstyle.toml" in out
    run = subprocess.run([sys.executable, "first_figure.py"], cwd=tmp_path, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    for t in ("post", "readme"):
        assert (tmp_path / "figures" / t / "first_figure.png").exists()
        assert (tmp_path / "figures" / t / "_meta" / "first_figure.styles.json").exists()
    assert main(["check", str(tmp_path / "figures" / "post"), "--vocab", str(tmp_path / "plotstyle.toml")]) == 0
    assert sp.load(tmp_path / "plotstyle.toml").project == "demo"
    capsys.readouterr()
    # the parent of post/ and readme/: both sidecars are found (figures/<target>/_meta/), so both figures are checked
    assert main(["check", str(tmp_path / "figures"), "--vocab", str(tmp_path / "plotstyle.toml")]) == 0
    assert capsys.readouterr().out.strip() == "styles-plot check: 2 figure(s), 0 problem(s)"
    # the numbers agree: accuracy is k/n of the printed counts
    meta = json.loads((tmp_path / "figures" / "post" / "_meta" / "first_figure.styles.json").read_text())
    for m in ("m1", "m2", "m3"):
        k, n = map(int, meta["numbers"][f"n.{m}"].split(" of "))
        assert meta["numbers"][f"acc.{m}"] == f"{100 * k / n:.0f}"


def test_init_refuses_to_overwrite(tmp_path, capsys):
    assert main(["init", str(tmp_path)]) == 0
    (tmp_path / "status.csv").write_text("mine\n")
    before = {f: (tmp_path / f).read_bytes() for f in INIT_FILES}
    assert main(["init", str(tmp_path)]) == 2
    assert "status.csv" in capsys.readouterr().err
    assert {f: (tmp_path / f).read_bytes() for f in INIT_FILES} == before
    assert main(["init", str(tmp_path), "--force"]) == 0
    assert (tmp_path / "status.csv").read_text().startswith("figure,cell,timing")


def test_init_into_a_new_folder_named_after_it(tmp_path):
    assert main(["init", str(tmp_path / "new-project")]) == 0
    assert sp.load(tmp_path / "new-project" / "plotstyle.toml").project == "new-project"


def _templates():
    return {f: (files("styles_plot") / "data" / "init" / f).read_text(encoding="utf-8") for f in INIT_FILES}


def test_templates_load_and_name_no_project(tmp_path):
    for f, text in _templates().items():
        (tmp_path / f).write_text(text)
    v = sp.load(tmp_path / "plotstyle.toml")
    assert set(v.roles) == {"method"} and v.controls == ("shuffled labels",)  # only what the starter draws
    assert "# [roles.variant]" in _templates()["plotstyle.toml"]  # a second role, shown commented out
    assert [e.name for e in v.entities("models")] == ["Model 1", "Model 2", "Model 3"]
    reg = sp.load_registry(tmp_path / "status.csv")
    assert reg.get("first_figure", "acc.m3").timing == "post_hoc"
    assert sum(reg.get("first_figure", f"acc.m{i}").timing == "fixed_in_advance" for i in (1, 2, 3)) == 2
    text = "\n".join(_templates().values()).lower()
    for word in ("bridge", "jspace", "esk", "audit", "danyil", "orel"):
        assert word not in text
    assert not re.search(r"\b\d{8}T\d{4,6}Z?\b", text)  # no run stamps
    assert len(_templates()["first_figure.py"].splitlines()) <= 40


@pytest.mark.parametrize("marker", ["# CHANGE", "# [[terms.banned]]", "ADOPTING.md"])
def test_template_vocab_is_commented(marker):
    assert marker in _templates()["plotstyle.toml"]
