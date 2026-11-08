"""The status registry: one row per drawn cell, saying when its analysis was fixed and how the text uses it.

Columns: figure, cell, timing, claim, claim_reason, reason, source.

- timing: fixed_in_advance | post_hoc. Decides the mark: hollow only for post_hoc.
- claim: claimed | descriptive | not_claimed. Decides the grey tag: none, "descriptive", "not claimed: <claim_reason>".
- claim_reason: printed in the tag; required for not_claimed and must be one of the vocabulary's [terms].not_claimed.
- reason, source: why and where from; never printed.

A row whose figure is `*` gives a cell's status in every figure: when an analysis was fixed is a fact about the
analysis, not the picture. A row for an exact (figure, cell) may then override `claim` and `claim_reason` only (how one
text uses the number); a different `timing` for the same cell is an error naming both lines.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

ANY = "*"  # the figure column of a row that holds in every figure
TIMINGS = ("fixed_in_advance", "post_hoc")
CLAIMS = ("claimed", "descriptive", "not_claimed")
COLUMNS = ("figure", "cell", "timing", "claim", "claim_reason", "reason", "source")


class RegistryError(ValueError):
    """A registry file that does not follow the schema."""


@dataclass(frozen=True)
class Status:
    timing: str = "fixed_in_advance"
    claim: str = "claimed"
    claim_reason: str = ""
    reason: str = ""
    source: str = ""
    drawn_filled: bool = False  # set by the renderer when every estimate of a figure is post hoc (said once instead)

    @property
    def hollow(self) -> bool:
        return self.timing == "post_hoc" and not self.drawn_filled

    def as_dict(self) -> dict:
        return {"timing": self.timing, "claim": self.claim, "claim_reason": self.claim_reason}


class Registry:
    def __init__(self, rows: dict[tuple[str, str], Status], path: Path | None = None):
        self.rows = rows
        self.path = path

    def get(self, figure: str, cell: str) -> Status | None:
        """The cell's status in this figure: its own row, else the cell's `*` row."""
        return self.rows.get((figure, cell)) or self.rows.get((ANY, cell))

    def __contains__(self, key) -> bool:
        return key in self.rows

    def __len__(self) -> int:
        return len(self.rows)


def parse_row(row: dict, where: str) -> Status:
    timing, claim = (row.get("timing") or "").strip(), (row.get("claim") or "").strip()
    if timing not in TIMINGS:
        raise RegistryError(f"{where}: timing {timing!r} is not one of {', '.join(TIMINGS)}")
    if claim not in CLAIMS:
        raise RegistryError(f"{where}: claim {claim!r} is not one of {', '.join(CLAIMS)}")
    reason = (row.get("claim_reason") or "").strip()
    if claim == "not_claimed" and not reason:
        raise RegistryError(f"{where}: a not_claimed cell needs a claim_reason (printed as 'not claimed: <reason>')")
    if claim != "not_claimed" and reason:
        raise RegistryError(f"{where}: claim_reason is only for not_claimed cells")
    return Status(timing, claim, reason, (row.get("reason") or "").strip(), (row.get("source") or "").strip())


def load(path: str | Path) -> Registry:
    path = Path(path)
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or ())]
        if missing:
            raise RegistryError(f"{path}: missing columns {missing}; the registry's columns are {', '.join(COLUMNS)}")
        rows: dict[tuple[str, str], Status] = {}
        lines: dict[tuple[str, str], int] = {}
        for i, row in enumerate(reader, start=2):
            where = f"{path}:{i}"
            key = (row["figure"].strip(), row["cell"].strip())
            if not all(key):
                raise RegistryError(f"{where}: figure and cell must not be empty")
            if key in rows:
                raise RegistryError(f"{where}: duplicate row for figure {key[0]!r}, cell {key[1]!r} "
                                    f"(first at line {lines[key]})")  # fmt: skip
            rows[key], lines[key] = parse_row(row, where), i
    for (fig, cell), st in rows.items():
        base = rows.get((ANY, cell))
        if fig != ANY and base is not None and base.timing != st.timing:
            raise RegistryError(f"{path}:{lines[(fig, cell)]}: cell {cell!r} is {st.timing} in figure {fig!r} but "
                                f"{base.timing} for every figure at line {lines[(ANY, cell)]}; a figure's row may "
                                "change only claim and claim_reason")  # fmt: skip
    return Registry(rows, path)
