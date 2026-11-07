"""Number strings: one formatter per format kind, so one value prints one string everywhere.

A minus is U+2212, zero is never signed ("−0.0" prints "0.0"), an interval is "[lo, hi]" at the value's precision,
and a count is "k of n".
"""

from __future__ import annotations

import math

MINUS = "−"
NUM = r"[−+]?\d+(?:\.\d+)?%?"  # a number as figures print it


def decimal(value: float, decimals: int, suffix: str = "", sign: bool = False) -> str:
    """A number at a precision; `sign` prints "+" before a positive value (a difference)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        raise ValueError("cannot print a missing number; draw sp.Missing instead")
    s = f"{value:.{decimals}f}"
    if set(s.lstrip("-")) <= set("0."):  # no signed zero after rounding
        s = s.lstrip("-")
    elif sign and not s.startswith("-"):
        s = "+" + s
    return s.replace("-", MINUS) + suffix


def interval(lo: float, hi: float, decimals: int, suffix: str = "") -> str:
    """An interval at the value's precision; its bounds are never signed ("+6.2 [3.2, 8.9]")."""
    return f"[{decimal(lo, decimals, suffix)}, {decimal(hi, decimals, suffix)}]"


def count(k: int, n: int) -> str:
    if int(k) != k or int(n) != n or not 0 <= k <= n:
        raise ValueError(f"a count is k of n with integers 0 <= k <= n, got {k} of {n}")
    return f"{int(k)} of {int(n)}"


def tick(value: float) -> str:
    """An axis tick: the shortest exact form ("0", "0.5", "30"), with the true minus."""
    return f"{value:g}".replace("-", MINUS)
