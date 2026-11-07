"""Every check: a figure that passes, and for each code a figure that fails it."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

import styles_plot as sp
from styles_plot import _checks
from styles_plot._registry import Registry, Status
from styles_plot._tags import tag, tags

from .conftest import codes, example

M3 = ["m1", "m2", "m3"]


def run(fig, target="post"):
    mpl = fig.render(target)
    return mpl, _checks.run(mpl)


def simple(v, fid="methods", **col_kw):
    """A one-panel table whose cells are in the examples' registry (figure 'methods')."""
    kw = {"series": [sp.Series("second", {m: sp.Est(60 + i, 58 + i, 62 + i, cell=f"acc.{m}") for i, m in
                                         enumerate(M3)})]}  # fmt: skip
    kw.update(col_kw)
    col = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 75, 100), **kw)
    return sp.Figure(fid, v).add(sp.DotTable(M3, [col]))


@pytest.mark.parametrize("name", ["dot_table", "sweep", "distribution", "stack", "scatter", "schematic"])
def test_examples_pass(vocab, name):
    for build in example(name).FIGURES:
        _mpl, problems = run(build(vocab))
        assert problems == [], [str(p) for p in problems]


def test_key_figure_passes(vocab):
    _mpl, problems = run(sp.key_figure(vocab))
    assert problems == []


# ---- colour ----------------------------------------------------------------------------------------------------------
def test_untagged_role_colour_and_foreign_hue(vocab):
    mpl = simple(vocab).render("post")
    ax = mpl.axes[0]
    ax.plot([50, 60], [0.5, 0.5], color=vocab.role("second").hex)
    ax.plot([50, 60], [0.6, 0.6], color="#00ff00")
    assert {"SP102", "SP103"} <= codes(_checks.run(mpl))


def test_tagged_mark_in_wrong_colour(vocab):
    mpl = simple(vocab).render("post")
    dot = next(a for a in mpl.axes[0].lines if tags(a).get("kind") == "dot")
    dot.set_color(vocab.role("first").hex)
    dot.set_markerfacecolor(vocab.role("first").hex)
    assert "SP101" in codes(_checks.run(mpl))


def test_role_without_its_word_and_word_without_role(vocab):
    mpl = simple(vocab).render("post")
    for t in mpl.findobj(lambda a: tags(a).get("kind") == "role_word"):
        t.set_visible(False)
    assert "SP104" in codes(_checks.run(mpl))
    mpl = simple(vocab).render("post")
    t = mpl.subfigs[0].text(0.5, 0.5, "probe", color=vocab.role("probe").hex)
    tag(t, kind="role_word", role="probe")
    assert "SP104" in codes(_checks.run(mpl))


# ---- status ----------------------------------------------------------------------------------------------------------
def test_hollow_disagrees_with_registry(vocab):
    fig = simple(vocab)
    mpl = fig.render("post")
    dot = next(a for a in mpl.axes[0].lines if tags(a).get("kind") == "dot")
    tags(dot)["hollow"] = True
    assert "SP201" in codes(_checks.run(mpl))


def test_status_tag_disagrees_with_registry(vocab):
    mpl, problems = run(example("dot_table").dot_table(vocab))
    assert problems == []
    for t in mpl.findobj(lambda a: tags(a).get("kind") == "status_tag"):
        t.set_visible(False)
    assert "SP202" in codes(_checks.run(mpl))


def test_cell_missing_from_registry_and_no_cell(vocab):
    fig = simple(vocab, series=[sp.Series("second", {"m1": sp.Est(60, cell="acc.unknown"), "m2": sp.Est(61)})])
    assert {"SP203", "SP204"} <= codes(run(fig)[1])


def test_no_registry(vocab):
    fig = sp.Figure("methods", dataclasses.replace(vocab, registry_path=None))
    fig.add(sp.DotTable(M3, [sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100),
                                          [sp.Series("second", {"m1": sp.Est(60, cell="acc.m1")})])]))  # fmt: skip
    assert "SP203" in codes(run(fig)[1])


def test_registry_hollow_and_claim_are_drawn(vocab):
    reg = Registry({("f", "c1"): Status("post_hoc", "not_claimed", "shared with a baseline"),
                    ("f", "c2"): Status("fixed_in_advance", "descriptive")})  # fmt: skip
    col = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100),
                       [sp.Series("second", {"m1": sp.Est(60, cell="c1"), "m2": sp.Est(70, cell="c2")})])  # fmt: skip
    fig = sp.Figure("f", vocab, registry=reg).add(sp.DotTable(["m1", "m2"], [col]))
    mpl, problems = run(fig)
    assert problems == []
    texts = {t.get_text() for t in mpl.findobj(lambda a: tags(a).get("kind") in ("status_tag", "key"))}
    assert {"not claimed: shared with a baseline", "descriptive", "○ post hoc"} <= texts


# ---- key -------------------------------------------------------------------------------------------------------------
def test_key_drawn_but_not_named_and_named_but_not_drawn(vocab):
    mpl = simple(vocab).render("post")
    for t in mpl.findobj(lambda a: tags(a).get("kind") == "key"):
        t.set_visible(False)
    assert "SP301" in codes(_checks.run(mpl))
    mpl = simple(vocab).render("post")
    t = mpl.subfigs[-1].text(0.6, 0.5, "grey band: within 0.10 of a random direction", color="#6b6b6b")
    tag(t, kind="key", encoding=("band", ""))
    assert "SP302" in codes(_checks.run(mpl))


def test_legend_box(vocab):
    mpl = simple(vocab).render("post")
    ax = mpl.axes[0]
    tag(ax.plot([50], [0.5], marker="o", color="#6b5bd2", label="beta"), kind="dot", role="second", cell="acc.m1")
    ax.legend()
    assert "SP303" in codes(_checks.run(mpl))


# ---- words and cues --------------------------------------------------------------------------------------------------
def test_words_banned_unknown_ids_arrows(vocab):
    mpl = simple(vocab).render("post")
    sub = mpl.subfigs[0]
    tag(sub.text(0.1, 0.9, "an ablation"), kind="text")
    tag(sub.text(0.3, 0.9, "made-up words"), kind="text")
    tag(sub.text(0.5, 0.9, "run qwen35_9b_x6"), kind="text")
    tag(sub.text(0.7, 0.9, "← less"), kind="text")
    assert {"SP401", "SP402", "SP403", "SP405"} <= codes(_checks.run(mpl))


def test_verbatim_and_prose_skip_vocabulary(vocab):
    mpl = simple(vocab).render("post")
    tag(mpl.subfigs[0].text(0.1, 0.9, "Any prompt text at all"), kind="schematic_word", verbatim=True)
    assert "SP401" not in codes(_checks.run(mpl))


def test_cue_problems(vocab):
    mpl = simple(vocab).render("post")
    for t in mpl.findobj(lambda a: tags(a).get("kind") == "cue"):
        t.set_text("more accuracy")
        tags(t)["full"] = "more accuracy"
    assert "SP404" in codes(_checks.run(mpl))
    mpl = simple(vocab).render("post")
    for t in mpl.findobj(lambda a: tags(a).get("kind") in ("cue", "axis_title")):
        t.set_visible(False)
    assert {"SP406", "SP407"} <= codes(_checks.run(mpl))


# ---- numbers ---------------------------------------------------------------------------------------------------------
def test_hand_typed_number_and_one_key_two_strings(vocab):
    mpl = simple(vocab).render("post")
    mpl.subfigs[0].text(0.5, 0.5, "0.534", color="#1a1a1a")
    assert "SP501" in codes(_checks.run(mpl))
    col = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100),
                       [sp.Series("second", {"m1": sp.Est(60, cell="acc.m1", key="k", label=True),
                                             "m2": sp.Est(70, cell="acc.m2", key="k", label=True)})])  # fmt: skip
    assert "SP502" in codes(run(sp.Figure("methods", vocab).add(sp.DotTable(["m1", "m2"], [col])))[1])


def test_value_without_key(vocab):
    mpl = simple(vocab).render("post")
    tag(mpl.subfigs[0].text(0.5, 0.5, "61"), kind="value")
    assert "SP501" in codes(_checks.run(mpl))


# ---- layout ----------------------------------------------------------------------------------------------------------
def test_layout_problems(vocab):
    mpl = simple(vocab).render("post")
    ax = mpl.axes[0]
    tag(ax.text(60, ax.get_ylim()[0] * 0.85, "Model 1", fontsize=11), kind="text")  # on the m-row's dot line
    tag(mpl.subfigs[0].text(1.2, 0.5, "Model 2"), kind="row_label")
    tag(mpl.subfigs[0].text(0.5, 0.5, "Model 3", fontsize=6), kind="row_label")
    tag(mpl.subfigs[0].text(0.3, 0.3, "Model 1", rotation=90), kind="row_label")
    mpl.suptitle("Model 1")
    ax.add_line(Line2D([50], [0.5], marker="s", color="#6b5bd2"))
    r = Rectangle((50, 0), 1, 1, hatch="//", facecolor="#ffffff")
    ax.add_patch(r)
    found = codes(_checks.run(mpl))
    assert {"SP602", "SP603", "SP605", "SP607", "SP608"} <= found


def test_text_on_a_mark_and_overlap(vocab):
    mpl = simple(vocab).render("post")
    ax = mpl.axes[0]
    dot = next(a for a in ax.lines if tags(a).get("kind") == "dot")
    x, y = dot.get_xdata()[0], dot.get_ydata()[0]
    tag(ax.text(x, y, "Model 1", ha="center", va="center"), kind="row_label")
    tag(ax.text(x, y, "Model 2", ha="center", va="center"), kind="row_label")
    found = codes(_checks.run(mpl))
    assert {"SP601", "SP606"} <= found


def test_too_tall_for_a_slide(vocab):
    rows = ["m1", "m2", "m3", "m4", "m5"]
    col = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100),
                       [sp.Series("second", {m: sp.Est(60, cell=f"acc.{m}") for m in rows})])  # fmt: skip
    fig = sp.Figure("methods", vocab, subtitle="synthetic data").add(*[sp.DotTable(rows, [col])] * 3)
    assert "SP604" in codes(run(fig, "slide")[1])


def test_notebook_skips_layout(vocab):
    mpl = simple(vocab).render("notebook")
    mpl.suptitle("anything")
    assert "SP607" not in codes(_checks.run(mpl))


# ---- colour vision ---------------------------------------------------------------------------------------------------
def test_pair_that_may_not_share_a_figure(vocab_dir):
    text = (vocab_dir / "plotstyle.toml").read_text() + '\n[roles.ident]\nslot = "blue"\nword = "identity"\n'
    (vocab_dir / "plotstyle.toml").write_text(text)
    v = sp.load(vocab_dir / "plotstyle.toml")
    col = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100),
                       [sp.Series("second", {"m1": sp.Est(60, cell="acc.m1")}),
                        sp.Series("ident", {"m2": sp.Est(70, cell="acc.m2")})])  # fmt: skip
    problems = run(sp.Figure("methods", v).add(sp.DotTable(["m1", "m2"], [col])))[1]
    assert "SP701" in codes(problems)
    assert any("may not share a figure" in p.message for p in problems)


def test_control_floor(vocab_dir):
    text = (vocab_dir / "plotstyle.toml").read_text() + "\n[palette.colour_vision]\ncontrol = 60\n"
    (vocab_dir / "plotstyle.toml").write_text(text)
    v = sp.load(vocab_dir / "plotstyle.toml")
    fig = example("dot_table").methods(v)
    assert "SP702" in codes(run(fig)[1])


def test_uncomputable_distance(vocab, monkeypatch):
    monkeypatch.setattr(type(vocab.palette), "distances", lambda self, a, b: None)
    assert "SP700" in codes(run(example("dot_table").methods(vocab))[1])


def test_direct_labels(vocab):
    lonely = sp.Schematic(1.5, [sp.Box(0.3, 0.3, 1.0, 0.6, role="first"), sp.Words(5.0, 1.2, [("alpha", "first")])])
    assert "SP703" in codes(run(sp.Figure("s", vocab, direct_labels=True).add(lonely))[1])
    table = simple(vocab)
    table.direct_labels = True
    assert "SP704" in codes(run(table)[1])


# ---- saved PNG -------------------------------------------------------------------------------------------------------
def test_png_checks(tmp_path, vocab):
    from PIL import Image

    from styles_plot._png import check_png

    p = tmp_path / "x.png"
    a = np.full((400, 1000, 4), 255, np.uint8)
    a[:200, :, :3] = (0, 200, 0)
    a[0, 0, 3] = 0
    Image.fromarray(a).save(p)
    found = codes(check_png(p, vocab.target("post"), vocab.palette))
    assert {"SP801", "SP803", "SP804"} <= found
    found = codes(check_png(p, vocab.target("slide"), vocab.palette))
    assert "SP802" in found


# ---- v0.1.1 ----------------------------------------------------------------------------------------------------------
def test_cue_word_larger(vocab_dir):
    p = vocab_dir / "plotstyle.toml"
    p.write_text(p.read_text().replace('title = "gap: A − B (points)"\nquantity = "gap"', 'title = "gap: A − B (points)"\nquantity = "gap"\ncue_word = "larger"'))
    v = sp.load(p)
    assert v.cue("gap") == "→ larger gap"
    mpl, problems = run(example("dot_table").dot_table(v))
    assert problems == []
    cues = {t._styles_plot.get("full") for t in mpl.findobj(lambda a: tags(a).get("kind") == "cue")}
    assert "→ larger gap" in cues and "→ more accuracy drop" in cues


def test_role_words_in_one_line_in_dot_order(vocab):
    mpl, problems = run(example("dot_table").dot_table(vocab))
    assert problems == []
    ax0 = mpl.axes[0]
    words = [t for t in mpl.findobj(lambda a: tags(a).get("kind") == "role_word")]
    first_panel = [t for t in words if t.get_window_extent().x0 < ax0.get_window_extent().x1]
    ys = {round(t.get_window_extent().y0) for t in first_panel}
    assert len(ys) == 1  # one line
    order = [t.get_text() for t in sorted(first_panel, key=lambda t: t.get_window_extent().x0)]
    assert order == ["beta", "alpha"]  # beta's dots are left of alpha's


def test_whole_line_status_is_a_panel_tag(vocab_dir):
    with (vocab_dir / "status.csv").open("a") as f:
        f.write("sweep2,line.c1,post_hoc,descriptive,,,\nsweep2,line.c2,post_hoc,claimed,,,\n")
    v = sp.load(vocab_dir / "plotstyle.toml")
    lines = [sp.Line(r, "second", [0, 1, 2], [300, 200, 100], cell=f"line.{r}") for r in ("c1", "c2")]
    fig = sp.Figure("sweep2", v).add(sp.Sweep(["c1", "c2"], "layer", "rank", lines, kind="checkpoints"))
    mpl, problems = run(fig)
    assert problems == []
    texts = {t.get_text() for t in mpl.findobj(lambda a: tags(a).get("kind") == "status_tag")}
    assert texts == {"post hoc · descriptive", "post hoc"}
    for t in mpl.findobj(lambda a: tags(a).get("kind") == "status_tag"):
        t.set_visible(False)
    assert "SP202" in codes(_checks.run(mpl))


def test_key_figure_with_example_row(vocab):
    gal = example("build_gallery")
    mpl, problems = run(gal.key(vocab))
    assert problems == []
    kinds = {tags(a).get("kind") for a in mpl.findobj(lambda a: bool(tags(a)))}
    assert {"tick", "band", "read_aloud", "dot"} <= kinds
    assert not mpl.findobj(lambda a: tags(a).get("kind") == "key_mark")  # no key line repeated under it
    hollow = [a for a in mpl.findobj(lambda a: tags(a).get("kind") == "swatch" and tags(a).get("hollow"))]
    assert hollow and hollow[0].get_markeredgecolor() != vocab.palette.control


def test_key_figure_arguments(vocab):
    with pytest.raises(sp.BuildError, match="one row"):
        sp.key_figure(vocab, example=sp.DotTable(["m1", "m2"], []))
    with pytest.raises(sp.BuildError, match="example="):
        sp.key_figure(vocab, read_aloud="read: …")


def test_slide_fits_a_five_row_table(vocab):
    assert run(example("dot_table").dot_table(vocab), "slide")[1] == []
    assert vocab.target("slide").height_in == 6.5


# ---- v0.1.2: lanes, table notes, signed formats ----------------------------------------------------------------------
def test_lanes_labelled_and_unlabelled(vocab):
    lanes = [sp.Lane("a", "set one"), sp.Lane("b", "set two")]
    col = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100), [
        sp.Series("second", {("m1", "a"): sp.Est(60, cell="acc.m1", key="l.m1.a", label=True),
                             ("m1", "b"): sp.Est(70, cell="acc.m1", key="l.m1.b", label=True),
                             ("m2", "a"): sp.Est(65, cell="acc.m2")}),
        sp.Series("control", {("m2", "b"): sp.Est(55, cell="acc.m2")}, control="shuffled labels")])  # fmt: skip
    t = sp.DotTable(["m1", "m2"], [col], lanes=lanes, note="synthetic data")
    mpl, problems = run(sp.Figure("methods", vocab).add(t))
    assert problems == []
    labels = [a.get_text() for a in mpl.findobj(lambda a: tags(a).get("kind") == "lane_label")]
    assert labels == ["set one", "set two", "set one", "set two"]
    ys = sorted({round(float(d.get_ydata()[0]), 3) for d in mpl.findobj(lambda a: tags(a).get("kind") == "dot")})
    assert len(ys) == 4  # every lane on its own line
    plain = sp.DotTable(["m1"], [sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100), [
        sp.Series("second", {("m1", "a"): sp.Est(60, cell="acc.m1")}),
        sp.Series("first", {("m1", "b"): sp.Est(70, cell="acc.m1")})])], lanes=[sp.Lane("a"), sp.Lane("b")])  # fmt: skip
    assert run(sp.Figure("methods", vocab).add(plain))[1] == []


def test_signed_format(vocab_dir):
    p = vocab_dir / "plotstyle.toml"
    p.write_text(p.read_text() + '\n[formats.diff]\ndecimals = 1\nsign = true\n[units.diff]\ntitle = "difference (points)"\nquantity = "difference"\nformat = "diff"\n')
    v = sp.load(p)
    assert v.format(3.25, "diff") == "+3.2" and v.format(-1.0, "diff") == "−1.0" and v.format(0.01, "diff") == "0.0"
    assert v.format_interval(-1, 2, "diff") == "[−1.0, 2.0]"  # bounds never signed


# ---- v0.1.3 ----------------------------------------------------------------------------------------------------------
BIG = """
[project]
name = "big"
[controls]
names = ["rotated", "logit lens", "PCA", "a random part", "energy-matched random", "a random vector",
         "layout-only probe", "10 random heads", "no change"]
[key]
tick = "the largest same-size control"
band = "within 0.10 of a random part"
[units.drop]
title = "accuracy drop (points)"
quantity = "accuracy drop"
format = "points"
[terms]
canonical = ["accuracy drop"]
templates = ["read: on {entity}, recall drops {num} points"]
[[entities.models]]
key = "m"
name = "Model"
"""


def test_key_figure_at_project_scale(tmp_path):
    roles = "".join(f'[roles.r{i}]\nslot = "{s}"\nword = "role {i}"\nmeaning = "a fairly long meaning for role {i}, '
                    f'one line"\n' for i, s in enumerate(("ink", "violet", "teal", "amber", "blue", "brick", "slate")))
    (tmp_path / "status.csv").write_text("figure,cell,timing,claim,claim_reason,reason,source\nkey,c,fixed_in_advance,claimed,,,\n")
    v = sp.loads(BIG + roles + '[registry]\npath = "status.csv"\n', root=tmp_path)
    col = sp.DotColumn("accuracy drop", "drop", (0, 70), (0, 30, 60),
                       [sp.Series("r0", {"m": sp.Est(46.6, 40, 50, cell="c")})], ticks={"m": 10})  # fmt: skip
    fig = sp.key_figure(v, example=sp.DotTable(["m"], [col]), read_aloud="read: on Model, recall drops {x} points",
                        numbers={"x": (46.6, "drop", "ko.m")})  # fmt: skip
    mpl, problems = run(fig)
    assert problems == [], [str(p) for p in problems]
    w, h = mpl.get_size_inches()
    assert w / h >= 1.0
    assert ("ko.m", "46.6") in mpl._sp_info.numbers
    with pytest.raises(sp.BuildError, match="field without a number"):
        sp.key_figure(v, example=sp.DotTable(["m"], [col]), read_aloud="read: {y}").render("post")


def test_series_word_rule_number_missing_and_unit_title(vocab):
    col = sp.DotColumn("accuracy", "accuracy", (-20, 100), (0, 50, 100), [
        sp.Series("second", {"m1": sp.Est(60, cell="acc.m1"), "m2": sp.Missing("no run")}, word="probe")],
        rules=[sp.Rule(50, "bar fixed in advance: {}", unit="accuracy", key="bar")])  # fmt: skip
    tc = sp.TextColumn("answers", "prompts", {"m1": sp.Count(3, 4, cell="acc.m1", key="n.m1")}, unit_title=False)
    mpl, problems = run(sp.Figure("methods", vocab).add(sp.DotTable(["m1", "m2"], [col, tc])))
    assert problems == [], [str(p) for p in problems]
    words = {t.get_text(): tags(t) for t in mpl.findobj(lambda a: tags(a).get("kind") == "role_word")}
    assert "probe" in words and words["probe"]["role"] == "second"
    assert ("bar", "50") in mpl._sp_info.numbers
    assert "prompts" not in {t.get_text() for t in mpl.findobj(lambda a: tags(a).get("kind") == "axis_title")}


def test_sheet_order(tmp_path, vocab):
    from styles_plot._cli import main

    for build in (example("stack").stack, example("dot_table").methods):
        sp.save(build(vocab), tmp_path / f"{build.__name__}.png", "post")
    (tmp_path / "order.txt").write_text("stack\nmethods.png\n")
    assert main(["sheet", str(tmp_path), "--order", str(tmp_path / "order.txt")]) == 0
    (tmp_path / "bad.txt").write_text("nope\n")
    assert main(["sheet", str(tmp_path), "--order", str(tmp_path / "bad.txt")]) == 2


# ---- v0.1.4 ----------------------------------------------------------------------------------------------------------
def test_control_distribution_needs_its_name(vocab):
    data = {"c1": [0.1, 0.2, 0.3], "c2": [0.2, 0.3]}
    cells = {"c1": "strip.c1", "c2": "strip.c2"}
    ok = sp.Distribution(["c1", "c2"], "score", data, "control", kind="checkpoints", style="strip", cells=cells,
                         control="a random direction", xlim=(-1, 1), xticks=[-1, 0, 1])  # fmt: skip
    mpl, problems = run(sp.Figure("strip", vocab).add(ok))
    assert problems == []
    assert any("a random direction" in t.get_text() for t in mpl.findobj(lambda a: tags(a).get("kind") == "key"))
    with pytest.raises(sp.BuildError, match="control="):
        run(sp.Figure("strip", vocab).add(dataclasses.replace(ok, control=None)))
    mpl = sp.Figure("strip", vocab).add(ok).render("post")
    for a in mpl.findobj(lambda a: tags(a).get("kind") == "point"):
        tags(a).pop("control")
    assert "SP304" in codes(_checks.run(mpl))


def test_sweep_hrule_window_median_words_and_point_label(vocab_dir):
    p = vocab_dir / "plotstyle.toml"
    p.write_text(p.read_text().replace('[key]\n', '[key.bands]\nchosen = "the layers fixed in advance"\n[key]\n', 1)
                 .replace('"chance", "layer 11",', '"chance", "layer 11", "early", "late",'))
    v = sp.load(p)
    xs = list(range(0, 25))
    lines = [sp.Line("c1", "second", xs, [1000 / (1 + x) + 50 for x in xs], cell="line.c1", median=True, word="early"),
             sp.Line("c1", "second", xs, [3000 / (1 + x) + 90 for x in xs], cell="line.c1", word="late"),
             sp.Line("c2", "second", xs, [2000 / (1 + x) + 70 for x in xs], cell="line.c2", median=True)]
    s = sp.Sweep(["c1", "c2"], "layer", "rank", lines, kind="checkpoints",
                 points=[sp.Point("c1", "second", 11, cell="pick.c1", key="p.c1", label=True),
                         sp.Point("c2", "second", 11, cell="pick.c2", key="p.c2", label=True)],
                 hrules=[sp.Rule(100, "chance")], windows=[(9, 13, "chosen")], xticks=[0, 10, 20])  # fmt: skip
    mpl, problems = run(sp.Figure("sweep", v).add(s))
    assert problems == [], [str(p) for p in problems]
    words = {t.get_text() for t in mpl.findobj(lambda a: tags(a).get("kind") == "role_word")}
    assert {"early", "late"} <= words
    keys = {t.get_text() for t in mpl.findobj(lambda a: tags(a).get("kind") == "key")}
    assert {"line: median", "grey band: the layers fixed in advance"} <= keys


def test_two_band_meanings_in_one_figure(vocab_dir):
    p = vocab_dir / "plotstyle.toml"
    p.write_text(p.read_text().replace('[key]\n', '[key.bands]\nrange = "the range of 200 random vectors"\n[key]\n', 1))
    v = sp.load(p)
    a = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100), [sp.Series("second", {"m1": sp.Est(60, cell="acc.m1")})],
                     band=(45, 55))  # fmt: skip
    b = dataclasses.replace(a, band=(70, 80), band_name="range")
    assert "SP305" in codes(run(sp.Figure("methods", v).add(sp.DotTable(["m1"], [a, b])))[1])
    assert run(sp.Figure("methods", v).add(sp.DotTable(["m1"], [b])))[1] == []
    with pytest.raises(sp.BuildError, match="grey band"):
        run(sp.Figure("methods", v).add(sp.DotTable(["m1"], [dataclasses.replace(a, band_name="nope")])))


def test_value_labels_of_several_series_and_lines_on_the_clearance(vocab):
    col = sp.DotColumn("accuracy", "accuracy", (0, 100), (0, 50, 100), [
        sp.Series("first", {"m1": sp.Est(40, cell="acc.m1", key="a", label=True)}),
        sp.Series("second", {"m1": sp.Est(42, cell="acc.m1", key="b", label=True)}),
        sp.Series("probe", {"m1": sp.Est(44, cell="acc.m1", key="c", label=True)})],
        rules=[sp.Rule(47.3), sp.Rule(52.1), sp.Rule(97)])  # fmt: skip
    mpl, problems = run(sp.Figure("methods", vocab).add(sp.DotTable(["m1"], [col])))
    assert [p for p in problems if p.code in ("SP601", "SP606")] == [], [str(p) for p in problems]
    assert len(mpl.findobj(lambda a: tags(a).get("kind") == "value")) == 3


def test_scatter_header_numbers_arrow_label_bold_part_and_entities_in_code(vocab_dir):
    p = vocab_dir / "plotstyle.toml"
    p.write_text(p.read_text().replace('templates = [\n', 'templates = [\n    "PCA (PC1 {num}, PC2 {num})",\n', 1))
    v = sp.load(p)
    import numpy as np

    xy = np.random.default_rng(0).normal(size=(12, 2))
    panel = sp.ScatterPanel([sp.Cloud("beta", "second", xy, cell="pca.method")], embedding="PCA",
                            header="PCA (PC1 {a}, PC2 {b})", numbers={"a": (0.42, "share", "pc1"), "b": (0.18, "share", "pc2")})  # fmt: skip
    mpl, problems = run(sp.Figure("scatter", v).add(sp.Scatter([panel], panel_h=2.5)))
    assert problems == [] and ("pc1", "0.42") in mpl._sp_info.numbers
    sch = sp.Schematic(1.4, [sp.Box(0.3, 0.3, 1.2, 0.6, "model", role="first"),
                             sp.Arrow((1.6, 0.6), (3.0, 0.6), role="swap", label="swap"),
                             sp.Words(3.2, 0.6, [("The capital of ", None), ("France", "first", True)], verbatim=True)])  # fmt: skip
    assert run(sp.Figure("s", v, direct_labels=True).add(sch))[1] == []
    v2 = v.with_entities("heads", [("L12H3", "L12H3"), ("L14H0", "L14H0")])
    assert [e.name for e in v2.entities("heads")] == ["L12H3", "L14H0"]
    with pytest.raises(sp.VocabError, match="duplicate"):
        v.with_entities("heads", [("a", "x"), ("b", "x")])


@pytest.mark.parametrize("both", [True, False])
def test_labels_beside_a_connector_and_a_near_control(vocab, both):
    # fig08a: two series joined by a connector; fig10: a labelled value with a control dot close to it
    rows = ["m1", "m2", "m3", "m4"]
    vals = {"m1": (0.08, 0.27), "m2": (0.10, 0.05), "m3": (0.06, 0.12), "m4": (0.93, 0.90)}
    a = sp.Series("swap", {m: sp.Est(vals[m][0], cell=f"acc.{m}", key=f"a.{m}", label=True) for m in rows})
    b = sp.Series("control", {m: sp.Est(vals[m][1], cell=f"acc.{m}", key=f"b.{m}", label=both) for m in rows},
                  control="a random direction")  # fmt: skip
    col = sp.DotColumn("score", "score", (-0.1, 1.0), (0, 0.5, 1), [b, a], connect=("control", "swap"),
                       band=(-0.1, 0.1))  # fmt: skip
    problems = run(sp.Figure("methods", vocab).add(sp.DotTable(rows, [col])))[1]
    assert [p for p in problems if p.code in ("SP601", "SP606")] == [], [str(p) for p in problems]


def test_diagonal_arrow_label_is_off_its_line(vocab):
    sch = sp.Schematic(2.4, [sp.Box(0.3, 0.2, 1.2, 0.5, "model", role="first"),
                             sp.Arrow((1.5, 0.5), (3.5, 2.0), role="swap", label="swap")])  # fmt: skip
    mpl, problems = run(sp.Figure("s", vocab, direct_labels=True).add(sch))
    assert problems == [], [str(p) for p in problems]
    # the check sees the arrow: a word laid on it fails
    arrow = next(a for a in mpl.findobj(lambda a: tags(a).get("kind") == "arrow"))
    (x0, y0), (x1, y1) = tags(arrow)["seg"]
    tag(arrow.figure.text((x0 + x1) / 2, (y0 + y1) / 2, "swap", ha="center", va="center", fontsize=11), kind="text")
    assert "SP601" in codes(_checks.run(mpl))


# ---- v0.1.6 (grammar decisions) --------------------------------------------------------------------------------------
def test_one_estimate_per_colour_per_line(vocab):
    two = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100), [
        sp.Series("second", {"m1": sp.Est(60, cell="acc.m1")}),
        sp.Series("second", {"m1": sp.Est(70, cell="acc.m1")})])  # fmt: skip
    with pytest.raises(sp.BuildError, match="its own column"):
        run(sp.Figure("methods", vocab).add(sp.DotTable(["m1"], [two])))
    a = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100), [sp.Series("second", {"m1": sp.Est(60, cell="acc.m1")})])
    b = sp.DotColumn("answers", "accuracy", (40, 100), (50, 100), [sp.Series("second", {"m1": sp.Est(70, cell="acc.m1")})])
    assert run(sp.Figure("methods", vocab).add(sp.DotTable(["m1"], [a, b])))[1] == []  # across columns: allowed


def test_header_that_is_the_role_word(vocab_dir):
    p = vocab_dir / "plotstyle.toml"
    p.write_text(p.read_text() + '\n[roles.diff]\nslot = "slate"\nword = "gap"\nmeaning = "a quantity of no role"\n')
    v = sp.load(p)
    col = sp.DotColumn("gap", "gap", (-4, 98), (0, 30, 60), [sp.Series("diff", {"m1": sp.Est(40, cell="acc.m1")})])
    mpl, problems = run(sp.Figure("methods", v).add(sp.DotTable(["m1"], [col])))
    assert problems == [], [str(p) for p in problems]
    words = [t for t in mpl.findobj(lambda a: tags(a).get("kind") == "role_word")]
    assert len(words) == 1 and words[0].get_text() == "gap" and words[0].get_color() == v.role("diff").hex


def test_stack_with_a_text_column(vocab):
    st = example("stack")
    fig = st.stack(vocab)
    block = fig.blocks[0]
    tc = sp.TextColumn("correct", "share", {m: sp.Est(0.6, 0.55, 0.65, cell=f"correct.{m}", key=f"tc.{m}")
                                            for m in block.rows}, unit_title=False)  # fmt: skip
    fig.blocks[0] = dataclasses.replace(block, columns=[tc])
    mpl, problems = run(fig)
    assert problems == [], [str(p) for p in problems]
    assert ("tc.m1.interval", "[0.55, 0.65]") in mpl._sp_info.numbers


def test_sweep_point_with_its_own_value_and_interval(vocab):
    xs = list(range(0, 25))
    ln = sp.Line("c1", "second", xs, [1000 / (1 + x) + 50 for x in xs], cell="line.c1")
    pt = sp.Point("c1", "second", 11, cell="pick.c1", value=300, lo=200, hi=450, key="pt", label=True)
    mpl, problems = run(sp.Figure("sweep", vocab).add(sp.Sweep(["c1"], "layer", "rank", [ln], kind="checkpoints",
                                                                  points=[pt], xticks=[0, 10, 20])))  # fmt: skip
    assert problems == [], [str(p) for p in problems]
    assert any(tags(a).get("kind") == "whisker" for a in mpl.findobj(lambda a: bool(tags(a))))
    with pytest.raises(sp.BuildError, match="value, lo and hi"):
        run(sp.Figure("sweep", vocab).add(sp.Sweep(["c1"], "layer", "rank", [ln], kind="checkpoints",
                                                   points=[sp.Point("c1", "second", 11, lo=1, hi=2)])))  # fmt: skip


# ---- 0.1.6: layout bugs from the bridge port -------------------------------------------------------------------------
def test_left_fallback_starts_at_its_own_dot(vocab):
    # fig10: a labelled value near the right edge with a control dot just left of it
    col = sp.DotColumn("accuracy", "accuracy", (0, 100), (0, 50, 100), [
        sp.Series("control", {"m1": sp.Est(40, cell="acc.m1")}, control="shuffled labels"),
        sp.Series("second", {"m1": sp.Est(95, cell="acc.m1", key="v", label=True)})])  # fmt: skip
    mpl, problems = run(sp.Figure("methods", vocab).add(sp.DotTable(["m1"], [col])))
    assert [p for p in problems if p.code in ("SP601", "SP606")] == [], [str(p) for p in problems]
    label = next(t for t in mpl.findobj(lambda a: tags(a).get("kind") == "value"))
    dots = {tags(d)["role"]: d for d in mpl.findobj(lambda a: tags(a).get("kind") == "dot")}
    r = mpl.canvas.get_renderer()
    ctrl_x = dots["control"].get_transform().transform([[40, dots["control"].get_ydata()[0]]])[0][0]
    assert label.get_window_extent(r).x0 > ctrl_x  # between the control and its own dot, not left of everything


def test_tag_and_note_on_one_row_and_tags_under_their_lane(vocab_dir):
    with (vocab_dir / "status.csv").open("a") as f:
        f.write("lanes,x.m1,fixed_in_advance,descriptive,,,\nlanes,y.m1,fixed_in_advance,claimed,,,\n")
    v = sp.load(vocab_dir / "plotstyle.toml")
    note = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100),
                        [sp.Series("second", {"m1": sp.Est(60, cell="x.m1", note="no interval")})])  # fmt: skip
    mpl, problems = run(sp.Figure("lanes", v).add(sp.DotTable(["m1"], [note])))
    assert [p for p in problems if p.code in ("SP601", "SP606")] == [], [str(p) for p in problems]
    lanes = sp.DotTable(["m1"], [sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100), [
        sp.Series("second", {("m1", "a"): sp.Est(60, cell="y.m1"), ("m1", "b"): sp.Est(70, cell="x.m1")})])],
        lanes=[sp.Lane("a", "set one"), sp.Lane("b", "set two")])  # fmt: skip
    mpl, problems = run(sp.Figure("lanes", v).add(lanes))
    assert problems == [], [str(p) for p in problems]
    r = mpl.canvas.get_renderer()
    y = {t.get_text(): t.get_window_extent(r).y0 for t in mpl.findobj(lambda a: tags(a).get("kind") in ("lane_label", "status_tag"))}
    assert y["set one"] > y["set two"] > y["descriptive"]  # the tag sits under lane b, the descriptive one


def test_colour_words_that_do_not_fit_one_line(vocab):
    col = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100), [
        sp.Series("first", {"m1": sp.Est(50, cell="acc.m1")}, word="a linear probe of the same signal"),
        sp.Series("second", {"m1": sp.Est(60, cell="acc.m1")}, word="anything measured under a swap")], width=1.2)  # fmt: skip
    assert "SP609" in codes(run(sp.Figure("methods", vocab).add(sp.DotTable(["m1"], [col])))[1])
