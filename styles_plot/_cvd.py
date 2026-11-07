"""Colour-vision distances: CIEDE2000 (Sharma, Wu and Dalal 2005) between colours as seen with simulated
deuteranopia, protanopia and tritanopia (Machado et al. 2009, severity 100, via colorspacious) and normal vision.

The palette's slots are fixed, so their pairwise table is computed once and shipped as data/cvd.json; checks read the
table and need no extra dependency. Running this module regenerates the table (needs `styles-plot[check]`):

    python -m styles_plot._cvd
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np

KINDS = {"deutan": "deuteranomaly", "protan": "protanomaly", "tritan": "tritanomaly"}


def ciede2000(lab1, lab2) -> float:
    """CIEDE2000 colour difference with kL = kC = kH = 1."""
    L1, a1, b1 = (float(v) for v in lab1)
    L2, a2, b2 = (float(v) for v in lab2)
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cb**7 / (Cb**7 + 25**7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360 if C1p else 0.0
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360 if C2p else 0.0
    dLp, dCp = L2 - L1, C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    else:
        dhp = h2p - h1p - 360 if h2p > h1p else h2p - h1p + 360
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dhp / 2))
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    else:
        hbp = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    T = (
        1
        - 0.17 * np.cos(np.radians(hbp - 30))
        + 0.24 * np.cos(np.radians(2 * hbp))
        + 0.32 * np.cos(np.radians(3 * hbp + 6))
        - 0.20 * np.cos(np.radians(4 * hbp - 63))
    )
    dtheta = 30 * np.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cbp**7 / (Cbp**7 + 25**7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / np.sqrt(20 + (Lbp - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cbp, 1 + 0.015 * Cbp * T
    Rt = -np.sin(np.radians(2 * dtheta)) * Rc
    return float(np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh)))


def _rgb(hexcolour: str) -> np.ndarray:
    return np.array([int(hexcolour[i : i + 2], 16) for i in (1, 3, 5)]) / 255


def lab(hexcolour: str, vision: str = "normal") -> np.ndarray:
    """CIELab (D65) of a colour as seen with a simulated deficiency."""
    from colorspacious import cspace_convert  # the [check] extra

    c = _rgb(hexcolour)
    if vision != "normal":
        c = np.clip(cspace_convert(c, {"name": "sRGB1+CVD", "cvd_type": KINDS[vision], "severity": 100}, "sRGB1"), 0, 1)
    return cspace_convert(c, "sRGB1", "CIELab")


def table(slots: dict[str, str]) -> list[dict]:
    rows = []
    for a, b in itertools.combinations(slots, 2):
        row = {"a": a, "b": b}
        for v in ("normal", *KINDS):
            row[v] = round(ciede2000(lab(slots[a], v), lab(slots[b], v)), 2)
        rows.append(row)
    return rows


def main() -> None:
    from styles_plot._palette import Palette

    SLOTS = Palette().slots

    out = Path(__file__).parent / "data" / "cvd.json"
    doc = {
        "method": "CIEDE2000; Machado 2009 severity 100 via colorspacious; rounded to 0.01",
        "slots": SLOTS,
        "pairs": table(SLOTS),
    }
    out.write_text(json.dumps(doc, indent=1) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
