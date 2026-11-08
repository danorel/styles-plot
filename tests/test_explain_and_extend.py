"""Problems that explain themselves (A1), debug pictures (A2), waivers (A3), public blocks (B1) and the rest."""

from __future__ import annotations

import json
import re

import pytest

import styles_plot as sp
from styles_plot import _checks
from styles_plot._cli import main

from .conftest import example



def run(fig, target="post"):
    mpl = fig.render(target)
    return mpl, _checks.run(mpl)


def tight(v, upper=1.0, waive=()):
    """A labelled value with no room right of it, its connector and a near control blocking the left: SP601 on "0.97"."""
    col = sp.DotColumn("score", "score", (0.0, upper), (0, 0.5, 1), [
        sp.Series("control", {"m1": sp.Est(0.03, cell="acc.m1")}, control="shuffled labels"),
        sp.Series("second", {"m1": sp.Est(0.97, cell="acc.m1", key="v", label=True)})],
        connect=("control", "second"), width=1.2)  # fmt: skip
    return sp.Figure("methods", v, waive=waive).add(sp.DotTable(["m1"], [col]))


# ---- A1 --------------------------------------------------------------------------------------------------------------
def test_sp601_explains_itself_and_its_fix_works(vocab):
    _mpl, problems = run(tight(vocab))
    p = next(p for p in problems if p.code in ("SP601", "SP606"))
    assert p.subject and p.bbox_in and p.where["target"] == "post" and p.where.get("column") == "score"
    assert p.where.get("row") == "Model 1" and "→" in str(p)
    upper = float(re.search(r"xlim upper ≥ ([\d.]+)", p.fix).group(1))
    assert upper > 1.0
    assert [q for q in run(tight(vocab, upper))[1] if q.code in ("SP601", "SP606")] == []


def test_fixes_for_words_registry_and_line_words(vocab):
    mpl = sp.Figure("methods", vocab).add(sp.DotTable(["m1"], [sp.DotColumn(
        "not a word", "accuracy", (40, 100), (50, 100), [sp.Series("second", {"m1": sp.Est(60, cell="acc.zz")})])])).render("post")  # fmt: skip
    problems = _checks.run(mpl)
    w = next(p for p in problems if p.code == "SP401")
    assert '"not a word"' in w.fix and "[terms]" in w.fix
    r = next(p for p in problems if p.code == "SP203")
    assert r.fix.endswith("methods,acc.zz,<timing>,<claim>,,,")
    d = w.as_dict()
    assert d["code"] == "SP401" and d["fix"] == w.fix


def test_check_json(tmp_path, vocab, capsys):
    with pytest.warns(sp.StyleWarning):
        sp.save(tight(vocab), tmp_path / "t.png", "post", mode="compat")
    assert main(["check", str(tmp_path), "--json"]) == 1
    recs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert recs and all({"path", "code", "message"} <= set(r) for r in recs)
    assert any(r.get("fix") for r in recs)


def test_fix_text_for_overlap_words_missing_and_line_words(vocab, vocab_dir):
    from styles_plot._tags import tag, tags

    mpl = tight(vocab, 1.0).render("post")
    ax = next(a for a in mpl.axes if tags(a).get("kind") == "panel")
    y = ax.get_ylim()[0] * 0.5
    tag(ax.text(0.5, y, "Model 1"), kind="row_label")
    tag(ax.text(0.5, y, "Model 2"), kind="row_label")
    p = next(p for p in _checks.run(mpl) if p.code == "SP606")
    assert "xlim upper ≥" in p.fix and p.obstacle_in
    words = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100), [
        sp.Series("first", {"m1": sp.Est(50, cell="acc.m1")}, word="a linear probe of the same signal"),
        sp.Series("second", {"m1": sp.Est(60, cell="acc.m1")}, word="anything measured under a swap")], width=1.2)  # fmt: skip
    p = next(p for p in run(sp.Figure("methods", vocab).add(sp.DotTable(["m1"], [words])))[1] if p.code == "SP609")
    assert "in wide" in p.fix and "lanes" in p.fix
    toml = vocab_dir / "plotstyle.toml"
    toml.write_text(toml.read_text().replace('missing = ["no run", "no interval", "below gate"]',
                                             'missing = ["no run", "no interval", "below gate", "no comparable run at all"]'))  # fmt: skip
    v = sp.load(toml)
    miss = sp.DotColumn("accuracy", "accuracy", (-20, 100), (0, 50, 100),
                        [sp.Series("second", {"m1": sp.Missing("no comparable run at all")})], width=0.9)  # fmt: skip
    p = next(p for p in run(sp.Figure("methods", v).add(sp.DotTable(["m1"], [miss])))[1] if p.code == "SP610")
    assert "wider" in p.fix
    toml.write_text(toml.read_text().replace('"chance", "layer 11",', '"chance", "layer 11", "one", "two", "three", "four", "five",'))
    v = sp.load(toml)
    xs = list(range(25))
    lines = [sp.Line("c1", "probe", xs, [(k + 1) * 900 / (1 + x) + 100 for x in xs[:-1]] + [100], cell="line.c1",
                     word=n) for k, n in enumerate(["one", "two", "three", "four", "five"])]  # fmt: skip
    p = next(p for p in run(sp.Figure("sweep", v).add(sp.Sweep(["c1"], "layer", "rank", lines, kind="checkpoints",
                                                                 xticks=[0, 10, 20])))[1] if p.code == "SP611")  # fmt: skip
    assert "split the panel" in p.fix


# ---- A2 --------------------------------------------------------------------------------------------------------------
def test_debug_picture(tmp_path, vocab):
    import numpy as np
    from PIL import Image

    problems = sp.debug(tight(vocab), "post", out=tmp_path)
    pic = tmp_path / "_debug" / "methods.post.png"
    assert problems and pic.exists()
    a = np.asarray(Image.open(pic).convert("RGB")).astype(int)
    red = (a[..., 0] > 190) & (a[..., 1] < 80) & (a[..., 2] < 80)
    assert red.sum() > 50  # the boxes are drawn
    assert not list(tmp_path.rglob("*.styles.json"))  # never publishable: no sidecar
    sp.save(sp.Figure("stack", vocab).add(*example("stack").stack(vocab).blocks), tmp_path / "stack.png", "post")
    assert main(["check", str(tmp_path)]) == 0  # _debug/ is skipped
    with pytest.raises(sp.StyleError, match=r'sp\.debug\(fig, "post"\)'):
        sp.save(tight(vocab), tmp_path / "t.png", "post")


# ---- A3 --------------------------------------------------------------------------------------------------------------
def test_waiver_lets_a_looked_at_placement_through(tmp_path, vocab, capsys):
    w = sp.Waive("SP601", "0.97", "the value sits on its own connector; read as one")
    reports = sp.save_bundle(tight(vocab, waive=[w]), tmp_path, targets=("post", "readme"))  # strict
    for r in reports.values():
        assert r.problems == [] and r.waived == [{"code": "SP601", "subject": "0.97", "reason": w.reason}]
        assert json.loads(r.sidecar.read_text())["waived"] == r.waived
    assert main(["check", str(tmp_path / "post")]) == 0
    out = capsys.readouterr().out
    assert "methods.png: 1 waived (SP601)" in out  # per figure
    assert out.strip().endswith("0 problem(s), 1 waived")  # and in the summary


def test_only_text_placement_can_be_waived():
    for code in ("SP603", "SP609", "SP611", "SP101", "SP201", "SP401", "SP501"):
        with pytest.raises(sp.BuildError, match=f"{code} cannot be waived"):
            sp.Waive(code, "x", "because")
    with pytest.raises(sp.BuildError, match="needs a reason"):
        sp.Waive("SP601", "0.97", " ")
    with pytest.raises(sp.BuildError, match="waive= takes"):
        sp.Figure("methods", sp.from_dict({"project": {"name": "p"}}), waive=[("SP601", "0.97", "r")])


def test_waiver_matches_its_code_and_whole_text_only(vocab):
    other_code = sp.Waive("SP606", "0.97", "r")
    part = sp.Waive("SP601", "0.9", "r")
    problems = run(tight(vocab, waive=[other_code, part]))[1]
    assert {p.code for p in problems} == {"SP601", "SP905"}  # neither matched: the problem stays, both are stale
    assert sorted(p.subject for p in problems if p.code == "SP905") == ["0.9", "0.97"]
    stale = next(p for p in problems if p.code == "SP905")
    assert "targets=" in stale.fix


def test_stale_waiver_and_targets(tmp_path, vocab):
    w = sp.Waive("SP601", "0.97", "r", targets=("readme",))
    assert [p.code for p in run(tight(vocab, waive=[w]), "post")[1]] == ["SP601"]  # not for post: neither used nor stale
    assert run(tight(vocab, waive=[w]), "readme")[1] == []
    clean = sp.Waive("SP601", "0.97", "r")
    with pytest.raises(sp.StyleError, match="SP905 stale waiver"):
        sp.save(tight(vocab, 2.0, waive=[clean]), tmp_path / "t.png", "post")
    mpl = tight(vocab, 2.0, waive=[clean]).render("notebook")  # no layout check, so nothing is stale
    assert _checks.run(mpl) == []


def test_overlap_waived_by_either_text(vocab):
    from styles_plot._tags import tag, tags

    for text in ("Model 1", "Model 2"):
        mpl = tight(vocab, waive=[sp.Waive("SP601", "0.97", "r"), sp.Waive("SP606", text, "r")]).render("post")
        ax = next(a for a in mpl.axes if tags(a).get("kind") == "panel")
        y = ax.get_ylim()[0] * 0.5
        tag(ax.text(0.5, y, "Model 1"), kind="row_label")
        tag(ax.text(0.5, y, "Model 2"), kind="row_label")
        problems, waived = _checks.evaluate(mpl)
        assert "SP606" not in {p.code for p in problems} and "SP905" not in {p.code for p in problems}
        assert {"SP601", "SP606"} <= {w["code"] for w in waived}


# ---- B1 --------------------------------------------------------------------------------------------------------------
def test_custom_example_passes_strict_on_every_target(tmp_path, vocab):
    reports = sp.save_bundle(example("custom").custom(vocab), tmp_path, targets=("post", "slide", "readme"))
    for r in reports.values():
        assert r.problems == []
        meta = json.loads(r.sidecar.read_text())
        assert meta["cells"]["score.rank"]["timing"] == "post_hoc"


def _one_dot(est, role="second", **dot):
    def draw(cv):
        cv.word(1.0, 0.15, "beta", role="second", size="role_word", weight="bold")
        p = cv.panel(1.0, 0.35, 5.5, 0.3, "accuracy", (40, 100), (50, 75, 100))
        p.dot(0.15, est, role, **dot)

    return draw


def _key(mpl) -> set[str]:
    from styles_plot._tags import tags

    return {t.get_text() for t in mpl.findobj(lambda a: tags(a).get("kind") == "key")}


def test_custom_encodings_are_read_from_what_is_drawn(vocab):
    est = sp.Est(80, 77, 83, cell="score.rank")  # post hoc in the registry: hollow
    mpl = sp.Figure("custom", vocab).add(sp.Custom(1.4, _one_dot(est))).render("post")
    assert {"○ post hoc", "whiskers: 95% interval"} <= _key(mpl)
    assert _checks.run(mpl) == []


def test_declared_encodings_that_drift_fail_the_key_check(vocab):
    est = sp.Est(80, 77, 83, cell="score.acc")

    class Declared:
        def plan(self, ctx, width):
            return sp.Plan(1.4, _one_dot(est), encodings={("tick",)})  # says a tick, draws a whisker

    codes = {p.code for p in run(sp.Figure("custom", vocab).add(Declared()))[1]}
    assert {"SP301", "SP302"} <= codes


def test_raw_matplotlib_inside_a_custom_block_is_checked(vocab):
    def untagged(cv):
        _one_dot(sp.Est(80, cell="score.acc"))(cv)
        cv.axes(1.0, 0.35, 5.5, 0.3).plot([0, 1], [0, 1], color=vocab.role("second").hex)

    def unknown_word(cv):
        _one_dot(sp.Est(80, cell="score.acc"))(cv)
        cv.word(3.0, 0.15, "a word nobody declared")

    def hand_number(cv):
        _one_dot(sp.Est(80, cell="score.acc"))(cv)
        cv.subfigure.text(0.9, 0.9, "81")

    for draw, code in ((untagged, "SP103"), (unknown_word, "SP401"), (hand_number, "SP501")):
        assert code in {p.code for p in run(sp.Figure("custom", vocab).add(sp.Custom(1.4, draw)))[1]}, code


def test_a_control_dot_must_name_its_control(vocab):
    codes = {p.code for p in run(sp.Figure("custom", vocab).add(
        sp.Custom(1.4, _one_dot(sp.Est(60, cell="score.acc"), role="control"))))[1]}  # fmt: skip
    assert "SP304" in codes


def test_block_context_and_plan_validation(vocab):
    seen = {}

    class Probe:
        rows, kind = ["m1", "m2"], "models"  # rows share the table's label column

        def plan(self, ctx, width):
            seen.update(width=width, label=ctx.label_width, target=ctx.target.name, w=ctx.measure("accuracy")[0],
                        lines=ctx.wrap("a b c d e f", 0.3), status=ctx.status("score.rank").timing,
                        title=ctx.unit("accuracy").title, word=ctx.role("second").word,
                        axis=ctx.axis_height("accuracy", 3.0))  # fmt: skip
            with pytest.raises(sp.BuildError):
                ctx.unit("nothing")
            return sp.Plan(0.5, lambda cv: None)

    table = sp.DotTable(["m1"], [sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100),
                                              [sp.Series("second", {"m1": sp.Est(60, cell="score.acc")})])])  # fmt: skip
    sp.Figure("custom", vocab).add(table, Probe()).render("post")
    assert seen["width"] == 8.0 and seen["target"] == "post" and seen["label"] > 0.5
    assert seen["w"] > 0 and len(seen["lines"]) > 1 and seen["status"] == "post_hoc"
    assert seen["title"] == "accuracy (%)" and seen["word"] == "beta" and seen["axis"] > 0.3

    class Wrong:
        def plan(self, ctx, width):
            return (1.0, lambda cv: None)

    with pytest.raises(sp.BuildError, match="must return sp.Plan"):
        sp.Figure("custom", vocab).add(Wrong()).render("post")
    with pytest.raises(sp.BuildError, match="positive"):
        sp.Figure("custom", vocab).add(sp.Custom(0, lambda cv: None)).render("post")
    with pytest.raises(sp.BuildError, match="not a figure block"):
        sp.Figure("custom", vocab).add(object()).render("post")
    with pytest.raises(sp.BuildError, match="takes an sp.Est"):
        sp.Figure("custom", vocab).add(sp.Custom(1.4, _one_dot(80))).render("post")


def test_a_dry_run_leaves_no_trace(vocab):
    calls = []

    def draw(cv):
        calls.append(1)
        _one_dot(sp.Est(80, cell="score.acc", key="score.acc", label=True))(cv)

    mpl = sp.Figure("custom", vocab).add(sp.Custom(1.4, draw)).render("post")
    assert len(calls) == 2  # once to read its encodings, once for real
    from styles_plot._render import info

    assert info(mpl).numbers == (("score.acc", "80"),)  # the dry run's printed numbers are not logged


# ---- C1 --------------------------------------------------------------------------------------------------------------
HEAD = "figure,cell,timing,claim,claim_reason,reason,source\n"


def test_star_rows_hold_in_every_figure_and_figures_override_the_claim(tmp_path):
    p = tmp_path / "status.csv"
    p.write_text(HEAD + "*,acc.m1,post_hoc,claimed,,run after the data,notes\n"
                 "fig02,acc.m1,post_hoc,not_claimed,shared with a baseline,,\n")  # fmt: skip
    reg = sp.load_registry(p)
    assert reg.get("fig01", "acc.m1").timing == "post_hoc" and reg.get("fig01", "acc.m1").claim == "claimed"
    assert reg.get("fig02", "acc.m1").claim == "not_claimed"
    assert reg.get("fig01", "acc.m2") is None


def test_a_figure_row_may_not_change_the_timing(tmp_path):
    p = tmp_path / "status.csv"
    p.write_text(HEAD + "*,acc.m1,post_hoc,claimed,,,\nfig02,acc.m1,fixed_in_advance,claimed,,,\n")
    with pytest.raises(sp.RegistryError, match=r"status.csv:3: cell 'acc.m1' is fixed_in_advance .* line 2"):
        sp.load_registry(p)
    p.write_text(HEAD + "*,acc.m1,post_hoc,claimed,,,\n*,acc.m1,post_hoc,claimed,,,\n")
    with pytest.raises(sp.RegistryError, match="duplicate row"):
        sp.load_registry(p)


def test_star_rows_draw_and_check_like_figure_rows(tmp_path, vocab, vocab_dir, capsys):
    reg = vocab_dir / "status.csv"
    reg.write_text(HEAD + "*,acc.m1,post_hoc,claimed,,,\n*,acc.m2,fixed_in_advance,claimed,,,\n")
    v = sp.load(vocab_dir / "plotstyle.toml")
    col = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100),
                       [sp.Series("second", {m: sp.Est(60 + 10 * i, cell=f"acc.{m}") for i, m in enumerate(["m1", "m2"])})])
    for fid in ("anyfig", "other"):
        r = sp.save(sp.Figure(fid, v).add(sp.DotTable(["m1", "m2"], [col])), tmp_path / f"{fid}.png", "post")
        assert json.loads(r.sidecar.read_text())["cells"]["acc.m1"]["timing"] == "post_hoc"  # hollow, from the * row
    assert main(["check", str(tmp_path), "--vocab", str(vocab_dir / "plotstyle.toml")]) == 0
    reg.write_text(HEAD + "*,acc.m1,fixed_in_advance,claimed,,,\n*,acc.m2,fixed_in_advance,claimed,,,\n")
    capsys.readouterr()
    assert main(["check", str(tmp_path), "--vocab", str(vocab_dir / "plotstyle.toml")]) == 1
    assert capsys.readouterr().out.count("SP904 cell 'acc.m1' changed") == 2


# ---- C2 --------------------------------------------------------------------------------------------------------------
def _bound(vocab, *series, lanes=(), rows=("m1", "m2")):
    from styles_plot._bind import resolve

    col = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100), list(series))
    t = resolve(sp.DotTable(list(rows), [col], lanes=lanes), vocab, "methods")
    return [s.cells for s in t.columns[0].series]


def test_values_are_coerced(vocab):
    (cells,) = _bound(vocab, sp.Series("second", {"m1": 61, "m2": (70, 65, 75)}))
    assert cells == {"m1": sp.Est(61.0), "m2": sp.Est(70.0, 65.0, 75.0)}
    (cells,) = _bound(vocab, sp.Series("second", {"m1": {"value": 61, "lo": 60, "hi": 62}, "m2": sp.Missing("no run")}))
    assert cells == {"m1": sp.Est(61, 60, 62), "m2": sp.Missing("no run")}
    est = sp.Est(61, cell="own.cell")
    (cells,) = _bound(vocab, sp.Series("second", {"m1": est}, cell="acc.{row}"))
    assert cells["m1"].cell == "own.cell"  # a value's own field wins
    (cells,) = _bound(vocab, sp.Series("second", {"m1": sp.Est(61)}, cell="acc.{row}"))
    assert cells["m1"].cell == "acc.m1"


def test_bad_values_name_their_row(vocab):
    for bad, match in ((None, "no value for row 'm2'.*sp.Missing"), ((1, 2), "a tuple is \\(value, lo, hi\\)"),
                       ("61", "cannot read '61'"), ({"lo": 1}, "needs 'value'"), (True, "cannot read True"),
                       ((70, 75, 65), "lo > hi")):  # fmt: skip
        with pytest.raises(sp.BuildError, match=match):
            _bound(vocab, sp.Series("second", lambda m, bad=bad: 60 if m == "m1" else bad))


def test_callables_and_template_fields(vocab, vocab_dir):
    (cells,) = _bound(vocab, sp.Series("second", lambda m: 60, cell="acc.{row}.{role}", key="k.{row}", label=True,
                                       interval="sem"))  # fmt: skip
    assert cells["m2"] == sp.Est(60.0, cell="acc.m2.second", key="k.m2", label=True, interval="sem")
    lanes = [sp.Lane("a", "set one"), sp.Lane("b", "set two")]
    (cells,) = _bound(vocab, sp.Series("second", lambda m, lane: 60, cell="x.{row}.{lane}"), lanes=lanes)
    assert set(cells) == {("m1", "a"), ("m1", "b"), ("m2", "a"), ("m2", "b")} and cells["m2", "b"].cell == "x.m2.b"
    toml = vocab_dir / "plotstyle.toml"
    toml.write_text(toml.read_text().replace('key = "m1"\nname = "Model 1"', 'key = "m1"\nname = "Model 1"\nid = "q9"'))
    (cells,) = _bound(sp.load(toml), sp.Series("second", {"m1": 60, "m2": 61}, cell="layer.{id}"))
    assert cells["m1"].cell == "layer.q9" and cells["m2"].cell == "layer.m2"  # id, else the key
    with pytest.raises(sp.BuildError, match="no field 'lane'"):
        _bound(vocab, sp.Series("second", {"m1": 60}, cell="x.{lane}"))


def test_text_columns_and_stack_shares_bind_too(vocab):
    from styles_plot._bind import resolve

    counts = sp.TextColumn("answers", "prompts", lambda m: sp.Count(30, 40), cell="acc.{row}", key="n.{row}")
    t = resolve(sp.DotTable(["m1"], [counts]), vocab, "methods")
    assert t.columns[0].cells == {"m1": sp.Count(30, 40, cell="acc.m1", key="n.m1")}
    s = resolve(sp.Stack(["m1"], [sp.Segment("correct", "first", {"m1": 0.7}, cell="s.{row}"),
                                  sp.Segment("wrong", "other", lambda m: 0.3, cell="s.{row}")]), vocab, "stack")  # fmt: skip
    assert [seg.shares["m1"] for seg in s.segments] == [sp.Est(0.7, cell="s.m1"), sp.Est(0.3, cell="s.m1")]


def test_bound_table_draws_as_the_written_out_one(vocab):
    def fig(series):
        col = sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 75, 100), series, rules=[sp.Rule(50, "chance")])
        return sp.Figure("methods", vocab).add(sp.DotTable(["m1", "m2"], [col]))

    acc = {"m1": 61.2, "m2": 72.5}
    long = fig([sp.Series("second", {m: sp.Est(acc[m], acc[m] - 2, acc[m] + 2, cell=f"acc.{m}", key=f"acc.{m}",
                                               label=True) for m in acc})])  # fmt: skip
    short = fig([sp.Series("second", lambda m: (acc[m], acc[m] - 2, acc[m] + 2), cell="acc.{row}", key="acc.{row}",
                           label=True)])  # fmt: skip
    import io

    a, b = io.BytesIO(), io.BytesIO()
    long.render("post").savefig(a, format="png")
    short.render("post").savefig(b, format="png")
    assert a.getvalue() == b.getvalue()


# ---- C3 --------------------------------------------------------------------------------------------------------------
def _panel_range(fig, target="post"):
    from styles_plot._tags import tags

    ax = next(a for a in fig.render(target).axes if tags(a).get("kind") == "panel")
    return tuple(round(x, 6) for x in ax.get_xlim()), [round(t, 6) for t in ax.get_xticks()]


def _acc_fig(v, **col):
    s = sp.Series("second", {"m1": sp.Est(61, 58, 64, cell="acc.m1"), "m2": sp.Est(72, 69, 75, cell="acc.m2")})
    return sp.Figure("methods", v).add(sp.DotTable(["m1", "m2"], [sp.DotColumn("accuracy", "accuracy", series=[s],
                                                                                **col)]))  # fmt: skip


def test_range_from_the_column_then_the_unit_then_the_data(vocab, vocab_dir):
    assert _panel_range(_acc_fig(vocab, xlim=(40, 100), xticks=(50, 100))) == ((40, 100), [50, 100])
    toml = vocab_dir / "plotstyle.toml"
    toml.write_text(toml.read_text().replace('title = "accuracy (%)"', 'title = "accuracy (%)"\nlim = [30, 100]\n'
                                                                     'ticks = [50, 75, 100]'))  # fmt: skip
    v = sp.load(toml)
    assert _panel_range(_acc_fig(v)) == ((30, 100), [50, 75, 100])  # the unit's
    (lo, hi), ticks = _panel_range(_acc_fig(v, xlim=(40, 90)))  # the column's xlim; ticks inside it
    assert (lo, hi) == (40, 90) and ticks and all(40 < t < 90 for t in ticks)
    (lo, hi), ticks = _panel_range(_acc_fig(vocab))  # from the data: 58..75 padded, ticks inside
    assert lo < 58 and hi > 75 and all(lo < t < hi for t in ticks) and len(ticks) >= 2
    assert _checks.run(_acc_fig(vocab).render("post")) == []


def test_a_computed_range_leaves_room_for_the_rightmost_label(vocab):
    s = sp.Series("second", {"m1": sp.Est(0.97, cell="acc.m1", key="v", label=True), "m2": sp.Est(0.2, cell="acc.m2")})
    col = sp.DotColumn("score", "score", series=[s], width=1.2)
    mpl = sp.Figure("methods", vocab).add(sp.DotTable(["m1", "m2"], [col])).render("post")
    assert [p.code for p in _checks.run(mpl)] == []


def test_every_example_table_passes_without_its_ranges(vocab):
    import dataclasses

    def strip(c):
        if isinstance(c, sp.ColumnGroup):
            return dataclasses.replace(c, columns=[strip(x) for x in c.columns])
        return dataclasses.replace(c, xlim=None, xticks=None) if isinstance(c, sp.DotColumn) else c

    for build in example("dot_table").FIGURES:
        fig = build(vocab)
        fig.blocks = [dataclasses.replace(b, columns=[strip(c) for c in b.columns]) for b in fig.blocks]
        for target in ("post", "slide", "readme"):
            assert _checks.run(fig.render(target)) == [], (fig.id, target)


def test_unit_ranges_are_validated_and_an_empty_column_refused(vocab, vocab_dir):
    toml = vocab_dir / "plotstyle.toml"
    base = toml.read_text()
    for bad, match in (("lim = [100, 30]", "lo < hi"), ("lim = [30, 100]\nticks = [10]", "outside lim"),
                       ('ticks = ["a"]', "list of numbers")):  # fmt: skip
        toml.write_text(base.replace('title = "accuracy (%)"', f'title = "accuracy (%)"\n{bad}'))
        with pytest.raises(sp.VocabError, match=match):
            sp.load(toml)
    with pytest.raises(sp.BuildError, match="has no series"):
        sp.Figure("methods", vocab).add(sp.DotTable(["m1"], [sp.DotColumn("accuracy", "accuracy")])).render("post")


# ---- C4 --------------------------------------------------------------------------------------------------------------
def _two_panels(v, header="accuracy", **first):
    s = sp.Series("second", {"m1": sp.Est(61, cell="acc.m1")})
    cols = [sp.DotColumn(header, "accuracy", (40, 100), (50, 100), [s], **first),
            sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100), [s])]
    return sp.Figure("methods", v).add(sp.DotTable(["m1"], cols))


def test_weight_shares_the_free_width(vocab):
    from styles_plot._tags import tags

    axes = [a for a in _two_panels(vocab, weight=2).render("post").axes if tags(a).get("kind") == "panel"]
    w = [a.get_position().width for a in axes]
    assert w[0] / w[1] == pytest.approx(2.0, rel=1e-6)
    with pytest.raises(sp.BuildError, match="both width= .* and weight="):
        _two_panels(vocab, width=2.0, weight=2).render("post")
    with pytest.raises(sp.BuildError, match="must be positive"):
        _two_panels(vocab, weight=0).render("post")


LONG = "switches blocked by the knock-out"


def test_a_header_past_its_lines_warns_with_the_weight_that_fits(tmp_path, vocab, vocab_dir, capsys):
    toml = vocab_dir / "plotstyle.toml"
    toml.write_text(toml.read_text().replace('"switches blocked",', f'"switches blocked", "{LONG}",'))
    v = sp.load(toml)
    p = next(p for p in run(_two_panels(v, LONG, width=0.8))[1] if p.code == "SP613")
    assert "wraps to 4 lines (at most 2)" in p.message and "unit title" in p.fix
    need = float(re.search(r"a column ≥ ([\d.]+) in wide", p.fix).group(1))
    assert 1.3 < need < 2.0  # font metrics differ a little between platforms
    fig = sp.Figure("methods", v).add(sp.DotTable(["m1"], [
        sp.DotColumn(LONG, "accuracy", (40, 100), (50, 100), [sp.Series("second", {"m1": sp.Est(61, cell="acc.m1")})]),
        *(sp.DotColumn("accuracy", "accuracy", (40, 100), (50, 100), [sp.Series("second", {"m1": sp.Est(61, cell="acc.m1")})])
          for _ in range(4))]))  # fmt: skip
    p = next(p for p in run(fig)[1] if p.code == "SP613")
    weight = float(re.search(r"weight ≥ ([\d.]+)", p.fix).group(1))
    with pytest.warns(sp.StyleWarning, match="SP613"):
        r = sp.save(fig, tmp_path / "w.png", "post")  # strict, and still written: a new check warns first (E1)
    assert [q["code"] for q in json.loads(r.sidecar.read_text())["problems"]] == ["SP613"]
    capsys.readouterr()
    assert main(["check", str(tmp_path)]) == 0
    assert "SP613" in capsys.readouterr().out
    import dataclasses

    cols = fig.blocks[0].columns
    fig.blocks[0] = sp.DotTable(["m1"], [dataclasses.replace(cols[0], weight=weight + 0.1), *cols[1:]])
    assert "SP613" not in {q.code for q in run(fig)[1]}


def test_max_header_lines_is_a_target_field_and_the_table_turns_warnings_into_errors(vocab, vocab_dir, monkeypatch):
    toml = vocab_dir / "plotstyle.toml"
    toml.write_text(toml.read_text().replace('"switches blocked",', f'"switches blocked", "{LONG}",')
                    + "\n[targets.post]\nmax_header_lines = 4\n")  # fmt: skip
    assert "SP613" not in {p.code for p in run(_two_panels(sp.load(toml), LONG, width=0.8))[1]}  # 4 lines allowed
    assert _checks.is_warning("SP613") and not _checks.is_warning("SP601")
    monkeypatch.setattr(sp, "__version__", "0.3.0")
    assert not _checks.is_warning("SP613")  # an error from the version in the table


# ---- C5 --------------------------------------------------------------------------------------------------------------
def _refused(v):
    col = sp.DotColumn("recall", "accuracy", (40, 100), (50, 100),
                       [sp.Series("second", {"m1": sp.Est(81, cell="acc.m1"), "m2": sp.Est(77, cell="acc.zz")})])
    return sp.Figure("methods", v).add(sp.DotTable(["m1", "m2"], [col]))


def test_saves_record_their_last_problems(tmp_path, vocab):
    sp.save_bundle(sp.Figure("stack", vocab).add(*example("stack").stack(vocab).blocks), tmp_path, ("post", "readme"))
    with pytest.raises(sp.StyleError):
        sp.save_bundle(_refused(vocab), tmp_path, ("post", "readme"))
    data = json.loads((tmp_path / "_meta" / "problems.json").read_text())
    assert data["stack"] == {"post": [], "readme": []}  # clean: empty lists
    assert {p["code"] for p in data["methods"]["post"]} == {"SP401", "SP203"}  # a strict refusal is recorded too
    sp.save(sp.Figure("stack", vocab).add(*example("stack").stack(vocab).blocks), tmp_path / "one" / "s.png", "post")
    assert json.loads((tmp_path / "one" / "_meta" / "problems.json").read_text()) == {"stack": {"post": []}}


def test_todo_groups_words_cells_and_the_rest(tmp_path, vocab, vocab_dir, capsys):
    with pytest.raises(sp.StyleError):
        sp.save_bundle(_refused(vocab), tmp_path / "figs", ("post",))
    with pytest.warns(sp.StyleWarning):
        sp.save(tight(vocab), tmp_path / "figs" / "other" / "t.png", "post", mode="compat",
                root=tmp_path / "figs" / "other")  # another set: todo reads every _meta/problems.json under the folder
    capsys.readouterr()
    assert main(["todo", str(tmp_path / "figs")]) == 0
    out = capsys.readouterr().out
    assert 'canonical = [..., "recall"]' in out and "methods,acc.zz,<timing>,<claim>,,," in out
    assert "SP601" in out and "xlim upper ≥" in out
    assert main(["todo", str(tmp_path / "nothing")]) == 2

    toml = vocab_dir / "plotstyle.toml"
    assert main(["todo", str(tmp_path / "figs"), "--vocab", str(toml), "--write-vocab"]) == 0
    added = vocab_dir / "plotstyle.added.toml"
    assert '"recall",  # added by styles-plot todo, ' in added.read_text()
    assert 'files = ["plotstyle.added.toml"]' in capsys.readouterr().out
    assert "acc.zz" not in (vocab_dir / "status.csv").read_text()  # a status is a decision: never written
    toml.write_text(toml.read_text() + '\n[include]\nfiles = ["plotstyle.added.toml"]\n')
    v = sp.load(toml)
    assert "recall" in v.canonical and "SP401" not in {p.code for p in run(_refused(v))[1]}
    before = added.read_text()
    assert main(["todo", str(tmp_path / "figs"), "--vocab", str(toml), "--write-vocab"]) == 0
    assert added.read_text() == before  # already there: kept with its date, not repeated
    assert "[include]" not in capsys.readouterr().out.split("wrote")[-1]


def test_write_vocab_refuses_banned_words(tmp_path, vocab, vocab_dir, capsys):
    col = sp.DotColumn("ablation recall", "accuracy", (40, 100), (50, 100),
                       [sp.Series("second", {"m1": sp.Est(81, cell="acc.m1")})])
    with pytest.raises(sp.StyleError):
        sp.save_bundle(sp.Figure("methods", vocab).add(sp.DotTable(["m1"], [col])), tmp_path, ("post",))
    assert main(["todo", str(tmp_path), "--vocab", str(vocab_dir / "plotstyle.toml"), "--write-vocab", "w.toml"]) == 1
    assert "refused (banned): 'ablation recall'" in capsys.readouterr().out
    assert "ablation" not in (vocab_dir / "w.toml").read_text()


def test_include_merges_term_lists_and_refuses_a_key_defined_twice(vocab_dir):
    toml = vocab_dir / "plotstyle.toml"
    base = toml.read_text() + '\n[include]\nfiles = ["more.toml"]\n'
    toml.write_text(base)
    more = vocab_dir / "more.toml"
    more.write_text('[terms]\ncanonical = ["recall", "accuracy"]\nmissing = ["no seed"]\n'
                    '[units.recall]\ntitle = "recall (%)"\nquantity = "recall"\nformat = "accuracy"\n')
    v = sp.load(toml)
    assert {"recall", "accuracy"} <= v.canonical and v.missing[-1] == "no seed" and "recall" in v.units
    assert v.includes == (more,)
    more.write_text('[units.accuracy]\ntitle = "x"\nquantity = "x"\nformat = "accuracy"\n')
    with pytest.raises(sp.VocabError, match=r"more.toml: \[units\] 'accuracy' is also defined in .*plotstyle.toml"):
        sp.load(toml)
    more.write_text('[include]\nfiles = ["x.toml"]\n')
    with pytest.raises(sp.VocabError, match="one level deep"):
        sp.load(toml)
    toml.write_text(base.replace("more.toml", "gone.toml"))
    with pytest.raises(sp.VocabError, match="gone.toml does not exist"):
        sp.load(toml)


def test_the_sidecar_hash_covers_included_files(tmp_path, vocab_dir):
    toml = vocab_dir / "plotstyle.toml"
    toml.write_text(toml.read_text() + '\n[include]\nfiles = ["more.toml"]\n')
    more = vocab_dir / "more.toml"
    shas = []
    for words in ('["recall"]', '["recall", "precision"]'):
        more.write_text(f"[terms]\ncanonical = {words}\n")
        v = sp.load(toml)
        r = sp.save(sp.Figure("stack", v).add(*example("stack").stack(v).blocks), tmp_path / "s.png", "post")
        shas.append(json.loads(r.sidecar.read_text())["vocab"]["sha256"])
    assert shas[0] != shas[1]


def test_vocab_lint_reports_near_duplicates(vocab_dir, capsys):
    from styles_plot._lint import near_duplicates

    pairs = {(a, b): w for a, b, w in near_duplicates(["switch blocked", "switches blocked", "Accuracy", "accuracy",
                                                       "knock-out", "knock out", "baseline", "baselnie", "set one",
                                                       "set two"])}  # fmt: skip
    assert pairs[("switch blocked", "switches blocked")] == "plural -s"
    assert pairs[("Accuracy", "accuracy")] == "differ only by case"
    assert pairs[("knock out", "knock-out")] == "hyphen vs space"
    assert "differ by 2" in pairs[("baseline", "baselnie")]
    assert ("set one", "set two") not in pairs
    toml = vocab_dir / "plotstyle.toml"
    toml.write_text(toml.read_text().replace('"answers",', '"answers", "Answers",'))
    assert main(["vocab", "lint", "--vocab", str(toml)]) == 0  # a report: nothing fails
    assert "'Answers' / 'answers': differ only by case" in capsys.readouterr().out


# ---- C6 --------------------------------------------------------------------------------------------------------------
SET_MODULE = """
from pathlib import Path

import styles_plot as sp

HERE = Path(__file__).resolve().parent
V = sp.load(HERE / "plotstyle.toml")
SET = sp.FigureSet("demo", V, out=HERE / "out", targets=("post", "readme"))


def col(header="accuracy"):
    return sp.DotColumn(header, "accuracy", (40, 100), (50, 100), [sp.Series("second", {"m1": sp.Est(61, cell="acc.m1")})])


@SET.figure("methods", order=2, title="Beta is above chance", caption="Synthetic data.")
def methods(fig):
    fig.add(sp.DotTable(["m1"], [col()]))


@SET.figure("broken", order=1, targets=("post",))
def broken(fig):
    fig.add(sp.DotTable(["m1"], [col("not a word")]))


@SET.figure("crash")
def crash(fig):
    raise RuntimeError("the data file is missing")
"""


@pytest.fixture
def set_module(vocab_dir):
    path = vocab_dir / "figures.py"
    path.write_text(SET_MODULE)
    return path


def test_figure_set_registers_orders_and_makes(set_module):
    from styles_plot._build import load_set

    s = load_set(f"{set_module}:SET")
    assert s.ids() == ["broken", "methods", "crash"]  # by order, then as registered
    fig = s.make("methods")
    assert fig.id == "methods" and fig.title == "Beta is above chance" and fig.caption == "Synthetic data."
    assert s.targets_of("broken") == ("post",) and s.targets_of("methods") == ("post", "readme")
    assert s.select(["meth*", "nothing"]) == ["methods"]
    with pytest.raises(sp.BuildError, match="no figure matches"):
        s.select(["x*"])
    with pytest.raises(sp.BuildError, match="registered twice"):
        s.figure("methods")(lambda fig: None)
    s.figure("other")(lambda fig: sp.Figure("elsewhere", fig.vocab))
    with pytest.raises(sp.BuildError, match="returned"):
        s.make("other")


@pytest.mark.parametrize("jobs", [1, 2])
def test_build_goes_on_past_a_failing_figure_and_writes_the_index(set_module, capsys, jobs):
    out = set_module.parent / "out"
    assert main(["build", f"{set_module}:SET", "--jobs", str(jobs)]) == 1
    printed = capsys.readouterr().out
    assert "ok    methods" in printed and "FAIL  broken" in printed and "RuntimeError: the data file is missing" in printed
    index = json.loads((out / "_meta" / "index.json").read_text())
    assert [f["id"] for f in index["figures"]] == ["broken", "methods", "crash"]
    m = next(f for f in index["figures"] if f["id"] == "methods")
    assert m["ok"] and m["png"] == {"post": "post/methods.png", "readme": "readme/methods.png"}
    assert m["title"] == "Beta is above chance" and m["problems"] == {"post": [], "readme": []}
    assert (out / "readme" / "methods.png").exists() and not (out / "post" / "broken.png").exists()
    problems = json.loads((out / "_meta" / "problems.json").read_text())
    assert {p["code"] for p in problems["broken"]["post"]} >= {"SP401", "SP203"}
    assert problems["methods"] == {"post": [], "readme": []}


def test_build_only_updates_its_figures_in_the_index(set_module, capsys):
    out = set_module.parent / "out"
    main(["build", f"{set_module}:SET"])
    before = json.loads((out / "_meta" / "index.json").read_text())
    assert main(["build", f"{set_module}:SET", "--only", "meth*", "--target", "post"]) == 0
    after = json.loads((out / "_meta" / "index.json").read_text())
    assert [f["id"] for f in after["figures"]] == [f["id"] for f in before["figures"]]
    assert next(f for f in after["figures"] if f["id"] == "methods")["targets"] == ["post"]
    assert main(["build", f"{set_module}:NOPE"]) == 2
