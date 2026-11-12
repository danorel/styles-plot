"""Palettes: named slots a project maps its roles onto, plus the chrome colours.

The default palette has nine role slots, control grey and the light grey of a stack's remainder. A project may change
any hex, add slots, change the chrome, or change the colour-vision floors in its vocabulary file ([palette]); the
grammar stays the same: one role per slot, a slot's colour means that role in every figure, and there is no API that
returns a lighter or darker version of a slot (a shade never encodes a variable).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import cache
from importlib import resources

DEFAULT_ROLE_SLOTS: dict[str, str] = {
    "ink": "#2b2b2b",
    "violet": "#6b5bd2",
    "teal": "#1a9e8a",
    "amber": "#e08a1e",
    "blue": "#3a7dc9",
    "brick": "#b8433a",
    "slate": "#4a5f6a",
    "brown": "#8c6d46",
    "pink": "#b8689a",
}
DEFAULT_CONTROL = "#a8a8a8"
DEFAULT_OTHER = "#d9d9d9"
# a stack with two or more parts of no role draws them in these greys, in order (the first is DEFAULT_OTHER)
OTHER_SHADES = (DEFAULT_OTHER, "#a3a3a3", "#7a7a7a")
DEFAULT_CHROME: dict[str, str] = {
    "text": "#1a1a1a",  # bold ink and ink
    "muted": "#6b6b6b",  # grey text
    "faint": "#bdbdbd",  # spines, tick marks
    "grid": "#e4e4e4",
    "zebra": "#f5f5f5",
    "band": "#e6e6e6",  # the grey band
    "connector": "#d6d6d6",
    "rule": "#8c8c8c",  # dashed reference lines
    "background": "#ffffff",
}
VISIONS = ("normal", "deutan", "protan", "tritan")
RESERVED = ("control", "other")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _norm(value: str, where: str) -> str:
    if not isinstance(value, str) or not _HEX.match(value):
        raise ValueError(f"{where}: {value!r} is not a #rrggbb colour")
    return value.lower()


@dataclass(frozen=True)
class Palette:
    """Role slots (name -> hex), control grey, the stack remainder, chrome, and the colour-vision floors."""

    role_slots: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_ROLE_SLOTS))
    control: str = DEFAULT_CONTROL
    other: str = DEFAULT_OTHER
    chrome: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_CHROME))
    floor_roles: float = 12.0
    floor_control: float = 8.0

    @classmethod
    def from_dict(cls, doc: dict | None, where: str = "[palette]") -> Palette:
        """A palette from a vocabulary's [palette] table; slots and chrome merge over the defaults:

        [palette.slots]          violet = "#5e4fc4", green = "#2e8b57", control = "#9a9a9a"
        [palette.chrome]         text = "#111111"
        [palette.colour_vision]  roles = 12, control = 8
        """
        doc = doc or {}
        unknown = set(doc) - {"slots", "chrome", "colour_vision"}
        if unknown:
            raise ValueError(f"{where}: unknown keys {sorted(unknown)}")
        given = doc.get("slots") or {}
        slots = dict(DEFAULT_ROLE_SLOTS)
        slots.update({k: _norm(v, f"{where}.slots.{k}") for k, v in given.items() if k not in RESERVED})
        chrome = dict(DEFAULT_CHROME)
        for k, v in (doc.get("chrome") or {}).items():
            if k not in DEFAULT_CHROME:
                raise ValueError(f"{where}.chrome.{k}: chrome colours are {', '.join(DEFAULT_CHROME)}")
            chrome[k] = _norm(v, f"{where}.chrome.{k}")
        floors = doc.get("colour_vision") or {}
        palette = cls(
            role_slots=slots,
            control=_norm(given.get("control", DEFAULT_CONTROL), f"{where}.slots.control"),
            other=_norm(given.get("other", DEFAULT_OTHER), f"{where}.slots.other"),
            chrome=chrome,
            floor_roles=float(floors.get("roles", 12.0)),
            floor_control=float(floors.get("control", 8.0)),
        )
        values = list(palette.slots.values())
        clash = sorted({h for h in values if values.count(h) > 1})
        if clash:
            raise ValueError(f"{where}: two slots share the colour(s) {clash}")
        return palette

    @property
    def slots(self) -> dict[str, str]:
        return {**self.role_slots, "control": self.control, "other": self.other}

    def hex(self, slot: str) -> str:
        try:
            return self.slots[slot]
        except KeyError:
            raise KeyError(f"no palette slot {slot!r}; slots are {', '.join(self.slots)}") from None

    def chrome_colours(self) -> frozenset[str]:
        return frozenset({*self.chrome.values(), "#000000", "#ffffff"})

    # ---- colour vision ---------------------------------------------------------------------------------------------
    def floor(self, a: str, b: str) -> float:
        return self.floor_control if "control" in (a, b) else self.floor_roles

    def distances(self, a: str, b: str) -> dict[str, float] | None:
        """CIEDE2000 between two slots under each vision; None when it cannot be computed (a hex outside the shipped
        table without the [check] extra installed)."""
        return _distances(self.hex(a), self.hex(b))

    def distance(self, a: str, b: str) -> float | None:
        """The smallest CIEDE2000 between two slots over the four visions."""
        d = self.distances(a, b)
        return None if d is None else min(d.values())

    def incompatible_pairs(self) -> list[tuple[str, str, float]]:
        """Slot pairs that may not share a figure: under their floor in at least one vision."""
        names = [*self.role_slots, "control"]
        out = []
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                d = self.distance(a, b)
                if d is not None and d < self.floor(a, b):
                    out.append((a, b, d))
        return out


@cache
def _shipped() -> dict[tuple[str, str], dict[str, float]]:
    raw = json.loads(resources.files("styles_plot").joinpath("data/cvd.json").read_text())
    slots = {k: v.lower() for k, v in raw["slots"].items()}
    out = {}
    for row in raw["pairs"]:
        a, b = slots[row["a"]], slots[row["b"]]
        out[(a, b)] = out[(b, a)] = {v: row[v] for v in VISIONS}
    return out


@cache
def _distances(a: str, b: str) -> dict[str, float] | None:
    hit = _shipped().get((a, b))
    if hit is not None:
        return hit
    try:
        from styles_plot._cvd import ciede2000, lab
    except ImportError:  # pragma: no cover - the [check] extra is installed in tests
        return None
    try:
        return {v: round(ciede2000(lab(a, v), lab(b, v)), 2) for v in VISIONS}
    except ImportError:
        return None
