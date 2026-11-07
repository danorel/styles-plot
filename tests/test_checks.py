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
    tag(t, kind="key", encoding=("band",))
    assert "SP302" in codes(_checks.run(mpl))


def test_legend_box(vocab):
    mpl = simple(vocab).render("post")
    ax = mpl.axes[0]
    tag(ax.plot([50], [0.5], marker="o", color="#6b5bd2", label="method B"), kind="dot", role="second", cell="acc.m1")
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
    lonely = sp.Schematic(1.5, [sp.Box(0.3, 0.3, 1.0, 0.6, role="first"), sp.Words(5.0, 1.2, [("method A", "first")])])
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
