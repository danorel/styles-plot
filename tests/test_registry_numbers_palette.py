from __future__ import annotations

import pytest

import styles_plot as sp
from styles_plot import _numbers
from styles_plot._cvd import ciede2000

HEAD = "figure,cell,timing,claim,claim_reason,reason,source\n"


def write(tmp_path, body, head=HEAD):
    p = tmp_path / "status.csv"
    p.write_text(head + body)
    return p


def test_registry_loads(tmp_path):
    reg = sp.load_registry(write(tmp_path, "f,a,post_hoc,claimed,,,\nf,b,fixed_in_advance,not_claimed,why,,\n"))
    assert reg.get("f", "a").hollow
    assert reg.get("f", "b").claim_reason == "why"
    assert ("f", "a") in reg and len(reg) == 2 and reg.get("f", "z") is None


@pytest.mark.parametrize(
    "body, head, message",
    [
        ("f,a,later,claimed,,,\n", HEAD, "timing"),
        ("f,a,post_hoc,maybe,,,\n", HEAD, "claim"),
        ("f,a,post_hoc,not_claimed,,,\n", HEAD, "needs a claim_reason"),
        ("f,a,post_hoc,claimed,why,,\n", HEAD, "only for not_claimed"),
        ("f,a,post_hoc,claimed,,,\nf,a,post_hoc,claimed,,,\n", HEAD, "duplicate"),
        (",a,post_hoc,claimed,,,\n", HEAD, "must not be empty"),
        ("f,a,post_hoc\n", "figure,cell,status\n", "missing columns"),
    ],
)
def test_registry_errors(tmp_path, body, head, message):
    with pytest.raises(sp.RegistryError, match=message):
        sp.load_registry(write(tmp_path, body, head))


def test_numbers():
    assert _numbers.decimal(-0.0001, 2) == "0.00"
    assert _numbers.decimal(-1.5, 1) == "−1.5"
    assert _numbers.decimal(3, 0, "%") == "3%"
    assert _numbers.interval(-1, 2, 1) == "[−1.0, 2.0]"
    assert _numbers.tick(-0.5) == "−0.5"
    with pytest.raises(ValueError):
        _numbers.decimal(float("nan"), 1)
    for k, n in ((3, 2), (-1, 4), (1.5, 3)):
        with pytest.raises(ValueError):
            _numbers.count(k, n)


def test_shipped_pairs_that_may_not_share_a_figure():
    pairs = {(a, b) for a, b, _d in sp.Palette().incompatible_pairs()}
    assert pairs == {("violet", "blue"), ("teal", "blue"), ("teal", "pink"), ("blue", "pink"), ("brick", "brown"),
                     ("brown", "pink")}  # fmt: skip


def test_shipped_table_matches_a_fresh_computation():
    pytest.importorskip("colorspacious")
    from styles_plot._cvd import table

    fresh = {(r["a"], r["b"]): r for r in table(sp.Palette().slots)}
    pal = sp.Palette()
    for (a, b), row in fresh.items():
        shipped = pal.distances(a, b)
        for v in ("normal", "deutan", "protan", "tritan"):
            assert shipped[v] == pytest.approx(row[v], abs=0.01)


def test_custom_hex_is_computed():
    pytest.importorskip("colorspacious")
    pal = sp.Palette.from_dict({"slots": {"blue": "#00aaff"}})
    assert pal.distance("violet", "blue") > 12
    assert pal.hex("blue") == "#00aaff"
    with pytest.raises(KeyError):
        pal.hex("nope")
    with pytest.raises(ValueError, match="unknown keys"):
        sp.Palette.from_dict({"colours": {}})


# Sharma, Wu and Dalal (2005), Table 1: CIEDE2000 test pairs
SHARMA = [
    ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
    ((50.0, 3.1571, -77.2803), (50.0, 0.0, -82.7485), 2.8615),
    ((50.0, 2.8361, -74.0200), (50.0, 0.0, -82.7485), 3.4412),
    ((50.0, 0.0, 0.0), (50.0, -1.0, 2.0), 2.3669),
    ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
    ((50.0, 2.5, 0.0), (61.0, -5.0, 29.0), 22.8977),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
]


@pytest.mark.parametrize("a, b, want", SHARMA)
def test_ciede2000_reference_pairs(a, b, want):
    assert ciede2000(a, b) == pytest.approx(want, abs=1e-4)
    assert ciede2000(b, a) == pytest.approx(want, abs=1e-4)
