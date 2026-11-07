"""The status registry: one row per drawn cell, saying when its analysis was fixed and how the text uses it.

Columns: figure, cell, timing, claim, claim_reason, reason, source.

- timing: fixed_in_advance | post_hoc. Decides the mark: hollow only for post_hoc.
- claim: claimed | descriptive | not_claimed. Decides the grey tag: none, "descriptive", "not claimed: <claim_reason>".
- claim_reason: printed in the tag; required for not_claimed and must be one of the vocabulary's [terms].not_claimed.
- reason, source: why and where from; never printed.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

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
        return self.rows.get((figure, cell))

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
        for i, row in enumerate(reader, start=2):
            where = f"{path}:{i}"
            key = (row["figure"].strip(), row["cell"].strip())
            if not all(key):
                raise RegistryError(f"{where}: figure and cell must not be empty")
            if key in rows:
                raise RegistryError(f"{where}: duplicate row for figure {key[0]!r}, cell {key[1]!r}")
            rows[key] = parse_row(row, where)
    return Registry(rows, path)
