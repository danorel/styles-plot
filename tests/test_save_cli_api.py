from __future__ import annotations

import json

import pytest

import styles_plot as sp
from styles_plot._cli import main

from .conftest import example

PUBLIC = {
    "load", "loads", "from_dict", "Vocab", "VocabError", "Role", "Unit", "Format", "Entity", "Palette", "Theme",
    "Sizes", "MarkStyle", "Phrases", "load_registry", "Registry", "RegistryError", "Status", "Figure", "BuildError",
    "key_figure", "DotTable", "DotColumn", "TextColumn", "ColumnGroup", "Gutter", "Series", "Rule", "Sweep", "Line",
    "Point", "Distribution", "Stack", "Segment", "Scatter", "ScatterPanel", "Cloud", "Schematic", "Box", "Arrow",
    "Words", "Mark", "Est", "Missing", "Count", "save", "save_bundle", "check_figure", "SaveReport", "Problem",
    "StyleError", "StyleWarning", "contact_sheets",
}  # fmt: skip


def test_public_surface_is_pinned():
    assert set(sp.__all__) == PUBLIC
    assert all(hasattr(sp, n) for n in sp.__all__)
    assert sp.__version__


def bad_figure(v):
    col = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100),
                       [sp.Series("second", {"m1": sp.Est(60, cell="nowhere")})])  # fmt: skip
    return sp.Figure("methods", v).add(sp.DotTable(["m1"], [col]))


def test_strict_refuses_and_writes_nothing(tmp_path, vocab):
    out = tmp_path / "out" / "f.png"
    with pytest.raises(sp.StyleError, match="SP203"):
        sp.save(bad_figure(vocab), out, "post")
    assert not out.parent.exists() or list(out.parent.iterdir()) == []


def test_compat_warns_and_records(tmp_path, vocab):
    out = tmp_path / "f.png"
    with pytest.warns(sp.StyleWarning):
        rep = sp.save(bad_figure(vocab), out, "post", mode="compat")
    side = json.loads(rep.sidecar.read_text())
    assert out.exists() and side["problems"] and side["mode"] == "compat"


def test_notebook_never_refuses(tmp_path, vocab):
    with pytest.warns(sp.StyleWarning):
        rep = sp.save(bad_figure(vocab), tmp_path / "n.png", "notebook")
    assert json.loads(rep.sidecar.read_text())["publishable"] is False


def test_bad_mode(tmp_path, vocab):
    with pytest.raises(ValueError, match="mode"):
        sp.save(bad_figure(vocab), tmp_path / "x.png", "post", mode="lenient")


def test_save_and_sidecar(tmp_path, vocab):
    rep = sp.save(example("dot_table").dot_table(vocab), tmp_path / "dot.png", "post")
    side = json.loads(rep.sidecar.read_text())
    assert rep.sidecar.name == "dot.styles.json"
    assert side["figure"] == "dot_table" and side["target"] == "post" and side["publishable"]
    assert side["cells"]["band.m3"] == {"timing": "post_hoc", "claim": "not_claimed"}
    assert "○ post hoc" in side["key"] and "gap.band.m1" in side["numbers"]
    assert side["roles"] == ["first", "second"]


def test_bundle_is_all_or_nothing(tmp_path, vocab):
    fig = example("dot_table").dot_table(vocab)
    tall = example("dot_table").dot_table(vocab)
    tall.add(*tall.blocks * 2)  # three tables: more than a slide's 6.5 in
    out = tmp_path / "out"
    with pytest.raises(sp.StyleError, match=r"\[slide\]"):
        sp.save_bundle(tall, out, ("post", "slide"))
    assert not out.exists() or not any(out.rglob("*.png"))
    reps = sp.save_bundle(fig, out, ("post", "slide", "readme"))
    assert (out / "slide" / "dot_table.png").exists() and set(reps) == {"post", "slide", "readme"}


def test_targets_differ_in_title_and_caption(vocab):
    fig = example("dot_table").dot_table(vocab)
    kinds = {t: {a._styles_plot.get("kind") for a in fig.render(t).findobj(lambda a: hasattr(a, "_styles_plot"))}
             for t in ("post", "readme")}  # fmt: skip
    assert "title" in kinds["readme"] and "caption" in kinds["readme"]
    assert "title" not in kinds["post"] and "caption" not in kinds["post"]


def test_check_figure(vocab):
    assert sp.check_figure(example("stack").stack(vocab), "post") == []


# ---- CLI ---------------------------------------------------------------------------------------------------------------
@pytest.fixture
def saved(tmp_path, vocab_dir, vocab):
    out = tmp_path / "figs"
    for build in (example("dot_table").dot_table, example("stack").stack):
        sp.save(build(vocab), out / f"{build.__name__}.png", "post")
    return out


def test_cli_check_clean(saved, vocab_dir, capsys):
    assert main(["check", str(saved), "--vocab", str(vocab_dir / "plotstyle.toml")]) == 0
    assert "0 problem(s)" in capsys.readouterr().out


def test_cli_check_stale_and_conflicts(saved, vocab_dir, capsys):
    side = saved / "stack.styles.json"
    meta = json.loads(side.read_text())
    meta["png"]["sha256"] = "0" * 64
    meta["numbers"]["gap.band.m1"] = "99.9"
    meta["cells"]["correct.m1"] = {"timing": "post_hoc", "claim": "claimed"}
    side.write_text(json.dumps(meta))
    assert main(["check", str(saved), "--vocab", str(vocab_dir / "plotstyle.toml")]) == 1
    out = capsys.readouterr().out
    assert "SP902" in out and "SP502" in out and "SP904" in out


def test_cli_check_without_sidecars_and_bad_dir(tmp_path, saved, capsys):
    for s in saved.glob("*.styles.json"):
        s.unlink()
    assert main(["check", str(saved)]) == 0
    assert main(["check", str(tmp_path / "missing")]) == 2


def test_cli_sheet_key_palette(tmp_path, saved, vocab_dir, capsys):
    assert main(["sheet", str(saved), "-o", str(tmp_path / "sheets")]) == 0
    assert (tmp_path / "sheets" / "contact_sheet_gray.png").exists()
    assert main(["sheet", str(tmp_path / "sheets" / "none")]) == 2
    assert main(["key", "--vocab", str(vocab_dir / "plotstyle.toml"), "-o", str(tmp_path / "key.png")]) == 0
    assert (tmp_path / "key.styles.json").exists()
    assert main(["palette", "--vocab", str(vocab_dir / "plotstyle.toml")]) == 0
    assert "may not share a figure" in capsys.readouterr().out
    bad = tmp_path / "bad.toml"
    bad.write_text("[nope]\n")
    assert main(["palette", "--vocab", str(bad)]) == 2
