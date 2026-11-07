"""Declarations that cannot be drawn fail at render with a BuildError that names the problem."""

from __future__ import annotations

import re

import pytest

import styles_plot as sp

from .conftest import example


def col(**kw):
    base = dict(header="accuracy", unit="accuracy", xlim=(40, 100), xticks=(50, 100),
                series=[sp.Series("second", {"m1": sp.Est(60, cell="acc.m1")})])  # fmt: skip
    base.update(kw)
    return sp.DotColumn(**base)


def render(v, *blocks, fid="methods"):
    return sp.Figure(fid, v).add(*blocks).render("post")


@pytest.mark.parametrize(
    "block, message",
    [
        (sp.DotTable(["m2", "m1"], [col()]), "order"),
        (sp.DotTable(["m1"], [col(unit="nope")]), "no unit"),
        (sp.DotTable(["m1"], [col(xlim=(1, 1))]), "xlim"),
        (sp.DotTable(["m1"], [col(series=[sp.Series("nope", {})])]), "no role"),
        (sp.DotTable(["m1"], [col(series=[sp.Series("control", {})])]), "control series needs"),
        (sp.DotTable(["m1"], [col(connect=("second", "first"))]), "connect"),
        (sp.DotTable(["m1"], [col(width=9.0)]), "wider than"),
        (sp.DotTable(["m1"], [col(), col(), col(), col(), col(), col(), col(), col()]), "does not fit"),
        (sp.Stack(["m1"], [sp.Segment("correct", "first", {"m1": sp.Est(0.5)})]), "sums to"),
        (sp.Stack(["m1"], [sp.Segment("correct", "first", {"m1": sp.Est(0.2)})] * 5), "1 to 4"),
        (sp.Stack(["m1", "m2"], [sp.Segment("correct", "first", {"m1": sp.Est(1.0)})]), "lacks a share"),
        (sp.Distribution(["c1"], "accuracy", {"c1": [1, 2]}, "first", kind="checkpoints", style="violin"), "violins"),
        (sp.Distribution(["c1"], "accuracy", {"c1": [1, 2]}, "first", kind="checkpoints"), "count_unit"),
        (sp.Distribution(["c1"], "accuracy", {}, "first", kind="checkpoints", count_unit="prompts"), "no data"),
        (sp.Scatter([]), "at least one panel"),
        (sp.Scatter([sp.ScatterPanel([], embedding="UMAP", units=("score", "score"))]), "either"),
        (sp.Scatter([sp.ScatterPanel([], embedding="tSNE")]), "canonical"),
        (sp.Scatter([sp.ScatterPanel([sp.Cloud("x", "control", [[0, 0]])], embedding="UMAP")]), "not in [controls]"),
        (sp.Scatter([sp.ScatterPanel([sp.Cloud("x", "first", [0, 0])], embedding="UMAP")]), "(n, 2)"),
        (sp.Schematic(1.0, [sp.Box(0, 0, 99, 0.5)]), "outside"),
    ],
)
def test_build_errors(vocab, block, message):
    with pytest.raises(sp.BuildError, match=re.escape(message)):
        render(vocab, block)


def test_sweep_errors(vocab):
    line = sp.Line("c1", "second", [0, 1, 2], [3, 2, 1], cell="line.c1")
    for s, message in [
        (sp.Sweep(["c1"], "layer", "rank", [sp.Line("c9", "second", [0, 1], [1, 2])], kind="checkpoints"), "not a row"),
        (sp.Sweep(["c1"], "layer", "rank", [sp.Line("c1", "second", [0], [1])], kind="checkpoints"), "two points"),
        (sp.Sweep(["c1"], "layer", "rank", [line], kind="checkpoints", points=[sp.Point("c1", "first", 1)]), "no 'first'"),
        (sp.Sweep(["c1"], "layer", "rank", [line], kind="checkpoints", points=[sp.Point("c1", "second", 1.5)]), "not one"),
        (sp.Sweep(["c1"], "layer", "rank", [sp.Line("c1", "second", [0, 1], [-1, 2])], kind="checkpoints"), "positive"),
        (sp.Sweep(["c1"], "layer", "rank", [line], kind="checkpoints",
                  points=[sp.Point("c1", "second", 1, label=True)]), "key="),  # fmt: skip
    ]:
        with pytest.raises(sp.BuildError, match=message):
            render(vocab, s, fid="sweep")
    post_hoc = sp.Sweep(["c1"], "layer", "rank", [sp.Line("c1", "second", [0, 1], [1, 2], cell="pick.c1")],
                        kind="checkpoints")  # fmt: skip
    render(vocab, post_hoc, fid="sweep")  # a post hoc line draws, with a panel tag (no hollow line)


def test_figure_errors(vocab):
    with pytest.raises(sp.BuildError, match="bad figure id"):
        sp.Figure("a/b", vocab)
    with pytest.raises(sp.BuildError, match="no blocks"):
        sp.Figure("x", vocab).render("post")
    with pytest.raises(sp.BuildError, match="no target"):
        example("stack").stack(vocab).render("poster")
    with pytest.raises(sp.BuildError, match="not a figure block"):
        sp.Figure("x", vocab).add("table").render("post")


def test_value_errors():
    with pytest.raises(ValueError, match="both lo and hi"):
        sp.Est(1, lo=0)
    with pytest.raises(ValueError, match="lo > hi"):
        sp.Est(1, 2, 0)
    with pytest.raises(ValueError, match="data key"):
        sp.Est(1, label=True)


def test_key_needs_vocabulary_definitions(vocab):
    import dataclasses

    v = dataclasses.replace(vocab, key_tick="", key_band="")
    with pytest.raises(sp.BuildError, match=r"\[key\].tick"):
        render(v, sp.DotTable(["m1"], [col(ticks={"m1": 50})]))
    with pytest.raises(sp.BuildError, match=r"\[key\].band"):
        render(v, sp.DotTable(["m1"], [col(band=(45, 55))]))
    with pytest.raises(sp.BuildError, match="intervals"):
        render(vocab, sp.DotTable(["m1"], [col(series=[sp.Series("second", {"m1": sp.Est(60, 50, 70, cell="acc.m1",
                                                                                            interval="mad")})])]))  # fmt: skip


def test_text_column_and_missing(vocab):
    tc = sp.TextColumn("answers", "prompts", {"m1": sp.Est(3, 1, 5, cell="acc.m1", key="t.m1"),
                                              "m2": sp.Missing("no run")}, role="second")  # fmt: skip
    c = col(series=[sp.Series("second", {"m1": sp.Est(60, cell="acc.m1"), "m2": sp.Missing("no run")})])
    assert sp.check_figure(sp.Figure("methods", vocab).add(sp.DotTable(["m1", "m2"], [c, tc])), "post") == []
