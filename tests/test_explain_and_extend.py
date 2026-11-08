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
    assert capsys.readouterr().out.strip().endswith("0 problem(s), 1 waived")


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
