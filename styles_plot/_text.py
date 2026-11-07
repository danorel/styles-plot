"""Measuring and wrapping text in inches, with the same font machinery matplotlib draws with."""

from __future__ import annotations

from functools import lru_cache

from matplotlib.backends.backend_agg import RendererAgg
from matplotlib.font_manager import FontProperties

PT = 1 / 72  # inches per point
LINE = 1.3  # line height as a multiple of the font size


@lru_cache(maxsize=8)
def _renderer(dpi: float) -> RendererAgg:
    return RendererAgg(100, 100, dpi)


@lru_cache(maxsize=16384)
def text_size(s: str, size: float, weight: str = "normal", family: str = "DejaVu Sans",
              dpi: float = 200) -> tuple[float, float]:  # fmt: skip
    """(width, height) of one line of text, in inches, as drawn at `dpi` (glyph hinting depends on it)."""
    if not s:
        return 0.0, size * PT
    prop = FontProperties(family=family, size=size, weight=weight)
    w, h, _d = _renderer(dpi).get_text_width_height_descent(s, prop, ismath=False)
    return w / dpi, h / dpi


def wrap(s: str, width: float, size: float, weight: str = "normal", family: str = "DejaVu Sans",
         dpi: float = 200) -> list[str]:  # fmt: skip
    """Word-wrap to a width in inches; a word wider than the width keeps its own line."""
    out: list[str] = []
    for para in s.split("\n"):
        line = ""
        for word in para.split(" "):
            cand = f"{line} {word}" if line else word
            if line and text_size(cand, size, weight, family, dpi)[0] > width:
                out.append(line)
                line = word
            else:
                line = cand
        out.append(line)
    return out


def line_h(size: float) -> float:
    """The height of one line of text at a font size, in inches."""
    return size * PT * LINE
