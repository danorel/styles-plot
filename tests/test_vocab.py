from __future__ import annotations

import re

import pytest

import styles_plot as sp

BASE = """
[project]
name = "t"
[roles.a]
slot = "violet"
[units.u]
title = "share of things"
quantity = "things"
format = "share"
"""


def test_load_examples(vocab):
    assert vocab.role("second").hex == "#6b5bd2"
    assert vocab.unit("rank").scale == "log"
    assert [e.name for e in vocab.entities("models")][:2] == ["Model 1", "Model 2"]
    assert vocab.registry_path.name == "status.csv"


@pytest.mark.parametrize(
    "extra, message",
    [
        ('[roles.control]\nslot = "teal"', "reserved"),
        ('[roles.b]\nslot = "nope"', "not a role slot"),
        ('[roles.b]\nslot = "violet"', "already the role"),
        ('[units.v]\ntitle = "t"\nquantity = "q"\nformat = "nope"', "not in [formats]"),
        ('[units.v]\ntitle = "t"\nformat = "share"', "needs a quantity"),
        ('[units.v]\ntitle = "rank"\nquantity = "q"\nformat = "z"\nscale = "log"', "(log scale)"),
        ('[units.v]\ntitle = "t"\nquantity = "q"\nformat = "z"\nscale = "sqrt"', "scale must be"),
        ('[formats.f]\ndecimals = 9', "decimals"),
        ('[formats.f]\nstyle = "roman"', "style must be"),
        ('[terms]\ncanonical = ["KO"]\n[[terms.banned]]\npattern = "KO"\nuse = "knock-out"', "matches the banned"),
        ('[[terms.banned]]\npattern = "("\nregex = true\nuse = "x"', "bad regex"),
        ('[[entities.m]]\nkey = "a"\nname = "A"\n[[entities.m]]\nkey = "a"\nname = "B"', "duplicate key"),
        ("[bogus]\nx = 1", "unknown tables"),
        ('[palette.slots]\nviolet = "purple"', "is not a #rrggbb"),
        ('[palette.slots]\nviolet = "#6b5bd2"\nteal = "#6B5BD2"', "share the colour"),
        ('[palette.chrome]\nneon = "#ffffff"', "chrome colours are"),
        ('[targets.poster]\ndpi = 300', "needs width_in and dpi"),
        ('[marks]\nshape = "x"', "unknown keys"),
        ('[phrases]\ntick = "tick"', "placeholder"),
        ('[phrases]\ncue = "← more {}"', "never points left"),
        ("[terms]\ncanonical = [1]", "list of strings"),
    ],
)
def test_load_errors(extra, message):
    with pytest.raises(sp.VocabError, match=re.escape(message)):
        sp.loads(BASE + "\n" + extra)


def test_bad_toml():
    with pytest.raises(sp.VocabError):
        sp.loads("[project\n")


def test_missing_project():
    with pytest.raises(sp.VocabError, match="missing key 'project'"):
        sp.loads("[roles.a]\nslot='ink'")


def test_style_overrides():
    v = sp.loads(BASE + """
[palette.slots]
violet = "#5E4FC4"
green = "#2E8B57"
[palette.colour_vision]
roles = 10
[style]
font = "DejaVu Serif"
[targets.post]
dpi = 300
min_pt = 10
[targets.poster]
width_in = 20
dpi = 100
[marks]
dot_size = 12
[phrases]
post_hoc = "○ nachträglich"
""")
    assert v.role("a").hex == "#5e4fc4"
    assert "green" in v.palette.role_slots
    assert v.palette.floor_roles == 10
    assert v.target("post").dpi == 300 and v.target("post").font == "DejaVu Serif"
    assert v.target("poster").width_in == 20
    assert v.marks.dot_size == 12
    assert v.words.post_hoc == "○ nachträglich"


def test_lookups_and_order(vocab):
    vocab.check_order("models", ["m1", "m3"])
    with pytest.raises(ValueError, match="order"):
        vocab.check_order("models", ["m3", "m1"])
    with pytest.raises(ValueError):
        vocab.check_order("models", ["m1", "m1"])
    with pytest.raises(KeyError):
        vocab.check_order("models", ["zz"])
    for bad in (lambda: vocab.role("x"), lambda: vocab.unit("x"), lambda: vocab.target("x"),
                lambda: vocab.entities("x"), lambda: vocab.entity("models", "x")):  # fmt: skip
        with pytest.raises(KeyError):
            bad()


def test_number_formats(vocab):
    assert vocab.format(42.649, "drop") == "42.6"
    assert vocab.format(-0.04, "drop") == "0.0"
    assert vocab.format(-3.25, "drop") == "−3.2"
    assert vocab.format(67.5, "accuracy") == "68"
    assert vocab.format_interval(0.123, 0.456, "blocked") == "[0.12, 0.46]"
    assert vocab.format_count(18, 30) == "18 of 30"


def test_words(vocab):
    assert "Model 1" in vocab.allowed_phrases
    assert vocab.template_re.fullmatch("12 items")
    assert vocab.template_re.fullmatch("bar fixed in advance: 15")
    assert not vocab.template_re.fullmatch("bar fixed: 15")
    assert vocab.banned_hits("an ablation study")
    assert not vocab.banned_hits("knock-out")
