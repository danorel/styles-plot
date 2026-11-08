from __future__ import annotations

import json

import pytest

import styles_plot as sp
from styles_plot._cli import main

from .conftest import example

PUBLIC = {
    "load", "loads", "from_dict", "Vocab", "VocabError", "Role", "Unit", "Format", "Entity", "Palette", "Theme",
    "Sizes", "MarkStyle", "Phrases", "load_registry", "Registry", "RegistryError", "Status", "Figure", "BuildError",
    "key_figure", "DotTable", "DotColumn", "TextColumn", "ColumnGroup", "Gutter", "Lane", "Series", "Rule", "Sweep", "Line",
    "Point", "Distribution", "Stack", "Segment", "Scatter", "ScatterPanel", "Cloud", "Schematic", "Box", "Arrow",
    "Words", "Mark", "Card", "CardRow", "Est", "Missing", "Count", "save", "save_bundle", "check_figure", "SaveReport", "Problem",
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
    meta["png"]["pixels_sha256"] = "0" * 64
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


def test_figure_set_with_meta_and_sheets_folders(tmp_path, vocab_dir, capsys):
    p = vocab_dir / "plotstyle.toml"
    p.write_text(p.read_text() + '\n[output]\nsidecar_dir = "_meta"\n')
    v = sp.load(p)
    root = tmp_path / "writeup"
    sp.save(example("stack").stack(v), root / "main" / "stack.png", "post", root=root)
    sp.save(example("dot_table").methods(v), root / "appendix" / "methods.png", "post", root=root)
    assert (root / "_meta" / "main" / "stack.styles.json").exists()
    assert not (root / "main" / "stack.styles.json").exists()
    (root / "order.txt").write_text("appendix/methods\nmain/stack.png\n")
    assert main(["sheet", str(root), "-o", str(root / "_sheets"), "--order", str(root / "order.txt")]) == 0
    assert (root / "_sheets" / "contact_sheet_gray.png").exists()
    assert main(["check", str(root), "--vocab", str(p)]) == 0
    assert "2 figure(s), 0 problem(s)" in capsys.readouterr().out  # the sheets in _sheets are not figures
    side = root / "_meta" / "main" / "stack.styles.json"
    meta = json.loads(side.read_text())
    meta["png"]["pixels_sha256"] = "0" * 64
    side.write_text(json.dumps(meta))
    assert main(["check", str(root), "--vocab", str(p)]) == 1  # the sidecar in _meta is found
    assert "SP902" in capsys.readouterr().out


@pytest.mark.parametrize("bad", ["meta", "/abs/_meta", "_a/../../x"])
def test_bad_sidecar_dir(vocab_dir, bad):
    p = vocab_dir / "plotstyle.toml"
    p.write_text(p.read_text() + f'\n[output]\nsidecar_dir = "{bad}"\n')
    with pytest.raises(sp.VocabError, match="sidecar_dir"):
        sp.load(p)


def test_sidecar_hashes_pixels_not_bytes(tmp_path, vocab, capsys):
    from PIL import Image

    out = tmp_path / "figs"
    rep = sp.save(example("stack").stack(vocab), out / "stack.png", "post")
    side = json.loads(rep.sidecar.read_text())
    assert "pixels_sha256" in side["png"] and "sha256" not in side["png"]
    Image.open(rep.path).save(rep.path, compress_level=1)  # other bytes, same pixels (another machine's zlib)
    assert main(["check", str(out)]) == 0
    capsys.readouterr()
    im = Image.open(rep.path).convert("RGB")
    im.putpixel((5, 5), (0, 0, 0))
    im.save(rep.path)  # one pixel changed
    assert main(["check", str(out)]) == 1
    assert "SP902" in capsys.readouterr().out


# ---- check finds every sidecar save wrote; a PNG without one is said ------------------------------------------------
def _tamper(png):
    from PIL import Image

    im = Image.open(png).convert("RGB")
    im.putpixel((5, 5), (0, 0, 0))
    im.save(png)


def test_check_finds_sidecars_under_the_targets_meta(tmp_path, vocab, capsys):
    import dataclasses

    v = dataclasses.replace(vocab, sidecar_dir="_meta")
    fig = sp.Figure("stack", v).add(*example("stack").stack(v).blocks)
    sp.save_bundle(fig, tmp_path, targets=("post", "readme"))  # sidecars in <target>/_meta/
    assert (tmp_path / "readme" / "_meta" / "stack.styles.json").exists()
    assert main(["check", str(tmp_path)]) == 0  # from the parent: readme is checked as readme, not as post
    _tamper(tmp_path / "readme" / "stack.png")
    assert main(["check", str(tmp_path / "readme")]) == 1
    assert "SP902" in capsys.readouterr().out


def test_check_finds_sidecars_under_an_ancestors_meta(tmp_path, vocab, capsys):
    import dataclasses

    v = dataclasses.replace(vocab, sidecar_dir="_meta")
    fig = sp.Figure("stack", v).add(*example("stack").stack(v).blocks)
    sp.save(fig, tmp_path / "main" / "stack.png", "post", root=tmp_path)  # <root>/_meta/main/stack.styles.json
    _tamper(tmp_path / "main" / "stack.png")
    assert main(["check", str(tmp_path)]) == 1
    assert "SP902" in capsys.readouterr().out


def test_a_png_without_a_sidecar_is_a_warning(tmp_path, vocab, capsys):
    fig = sp.Figure("stack", vocab).add(*example("stack").stack(vocab).blocks)
    report = sp.save(fig, tmp_path / "stack.png", "post")
    report.sidecar.unlink()
    assert main(["check", str(tmp_path)]) == 0  # a warning in 0.1.x: it does not fail the run
    out = capsys.readouterr().out
    assert "stack.png: SP906 no sidecar: meaning and staleness not checked" in out
    assert out.strip().endswith("0 problem(s), 1 without a sidecar (SP906, a warning)")
