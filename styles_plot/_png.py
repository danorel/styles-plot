"""Checks on a saved PNG: pixel width, width : height, an opaque background, and hues that lie on the palette.

SP801 width in pixels differs from the target's
SP802 width : height outside the target's
SP803 transparent pixels, or a corner that is not the background colour
SP804 saturated pixels off the palette (more than TOLERANCE of them farther than DIST from every slot's line to white)
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

from styles_plot._checks._base import Problem
from styles_plot._palette import Palette
from styles_plot._theme import Theme

CHROMA, DIST, TOLERANCE = 40, 22, 0.05  # anti-aliasing between two slots is not a hue of its own


def pixels_sha256(png: str | Path) -> str:
    """A hash of what a PNG shows, not of its bytes: mode, size and decoded RGBA pixels. Two machines that draw the
    same pixels agree, whatever their zlib makes of them."""
    import hashlib

    im = Image.open(png).convert("RGBA")
    h = hashlib.sha256(f"RGBA {im.width}x{im.height}\n".encode())
    h.update(im.tobytes())
    return h.hexdigest()


def _rgb(hexes) -> np.ndarray:
    return np.array([[int(h[i : i + 2], 16) for i in (1, 3, 5)] for h in hexes], dtype=float)


def off_palette(png: Path, palette: Palette) -> tuple[float, str, int]:
    """(share of the saturated pixels that match no slot or its tint toward the background, the most common such
    colour, the number of saturated pixels)."""
    im = np.asarray(Image.open(png).convert("RGB"), dtype=float).reshape(-1, 3)
    sat = im[im.max(1) - im.min(1) > CHROMA]
    if len(sat) == 0:
        return 0.0, "", 0
    bg = _rgb([palette.chrome["background"]])[0]
    d = np.full(len(sat), np.inf)
    for a in _rgb(sorted({*palette.slots.values(), *palette.chrome.values()})):
        seg = bg - a
        t = np.clip(((sat - a) @ seg) / max(seg @ seg, 1e-9), 0, 1)
        d = np.minimum(d, np.sqrt(((sat - (a + t[:, None] * seg)) ** 2).sum(-1)))
    bad = sat[d > DIST]
    top = ""
    if len(bad):
        (r, g, b), _n = Counter(map(tuple, (bad // 16 * 16 + 8).astype(int))).most_common(1)[0]
        top = f"#{r:02x}{g:02x}{b:02x}"
    return len(bad) / len(sat), top, len(sat)


def check_png(png: str | Path, theme: Theme, palette: Palette, wide_ok: bool = False) -> list[Problem]:
    png = Path(png)
    name = png.name
    im = Image.open(png)
    w, h = im.size
    out = []
    want = theme.px_width
    if abs(w - want) > 1:
        out.append(Problem("SP801", f"{w} px wide, the target {theme.name!r} is {want} px", name))
    if theme.height_in is not None and abs(h - round(theme.height_in * theme.dpi)) > 1:
        out.append(Problem("SP802", f"{h} px high, the target {theme.name!r} is {round(theme.height_in * theme.dpi)} px",
                           name))  # fmt: skip
    if theme.aspect is not None and not (theme.aspect[0] - 0.01 <= w / h and (wide_ok or w / h <= theme.aspect[1] + 0.01)):
        out.append(Problem("SP802", f"width : height {w / h:.2f} outside {theme.aspect[0]:g}-{theme.aspect[1]:g}", name))
    a = np.asarray(im.convert("RGBA"))
    if (a[..., 3] < 255).any():
        out.append(Problem("SP803", "transparent pixels", name))
    bg = tuple(int(palette.chrome["background"][i : i + 2], 16) for i in (1, 3, 5))
    if any(tuple(a[y, x, :3]) != bg for y in (0, -1) for x in (0, -1)):
        out.append(Problem("SP803", "a corner is not the background colour", name))
    share, top, n = off_palette(png, palette)
    if share > TOLERANCE:
        out.append(Problem("SP804", f"{share:.1%} of {n} saturated pixels are off the palette, e.g. {top}", name))
    return out
