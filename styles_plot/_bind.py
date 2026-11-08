"""Data binding: a table's cells as a callable or loose values, turned into plain `Est`/`Missing`/`Count` before
anything is laid out, so the planners and the checks see exactly what they saw before.

Where it applies: `Series.cells` and `TextColumn.cells` in a dot table, `Segment.shares` in a stack. Not `Sweep`,
`Distribution` or `Scatter`, whose data are arrays, not cells.

- `cells` may be a mapping (row, or (row, lane) with lanes, to a value) or a callable called for every row (with
  `(row, lane)` for every lane in a table with lanes).
- A value may be an `Est`, `Missing` or `Count` as is; a number (→ `Est(v)`); a 3-tuple (→ `Est(v, lo, hi)`); a mapping
  with `value` and optional `lo`, `hi` (→ `Est`). `None` is an error naming the row: a missing cell says why.
- The owner's `cell` and `key` templates fill a value's `cell`/`key` when the value does not set its own; its `label`
  and `interval` apply to coerced values. Fields: `{row}` (entity key), `{id}` (entity id, else its key), `{lane}`,
  `{role}`.
"""

from __future__ import annotations

import dataclasses
import numbers
from collections.abc import Mapping

from styles_plot._model import ColumnGroup, Count, DotColumn, DotTable, Est, Missing, Stack, TextColumn
from styles_plot._render import BuildError


def resolve(block, vocab, figure_id: str):
    """The block with every binding resolved; blocks without bindings come back as they are."""
    if isinstance(block, DotTable):
        return _table(block, vocab, figure_id)
    if isinstance(block, Stack):
        return _stack(block, vocab, figure_id)
    return block


def _keys(rows, lanes) -> list:
    return [(r, ln.key) for r in rows for ln in lanes] if lanes else list(rows)


def _fields(vocab, kind: str, key, role: str | None) -> dict:
    row, lane = (key if isinstance(key, tuple) else (key, None))
    try:
        ent_id = vocab.entity(kind, row).id or row
    except KeyError:  # an unknown row fails later with the table's own message
        ent_id = row
    out = {"row": row, "id": ent_id, "role": role or ""}
    if lane is not None:
        out["lane"] = lane
    return out


def _fill(template: str | None, f: dict, where: str) -> str | None:
    if template is None:
        return None
    try:
        return template.format(**f)
    except KeyError as e:
        raise BuildError(f"{where}: template {template!r} has no field {e} (fields: {', '.join(sorted(f))})") from None


def _value(v, f: dict, owner, where: str, allowed: tuple):
    """One cell: coerced, its templates filled."""
    cell_t, key_t = getattr(owner, "cell", None), getattr(owner, "key", None)
    if v is None:
        raise BuildError(f"{where}: no value for row {f['row']!r}"
                         + (f", lane {f['lane']!r}" if "lane" in f else "")
                         + "; a missing cell says why: return sp.Missing(...)")  # fmt: skip
    if isinstance(v, Missing):
        return v
    if isinstance(v, (Est, Count)):
        if not isinstance(v, allowed):
            raise BuildError(f"{where}: a {type(v).__name__} is not a value here")
        changes = {}
        if v.cell is None and cell_t is not None:
            changes["cell"] = _fill(cell_t, f, where)
        if v.key is None and key_t is not None:
            changes["key"] = _fill(key_t, f, where)
        return dataclasses.replace(v, **changes) if changes else v
    if Est not in allowed:
        raise BuildError(f"{where}: row {f['row']!r}: {v!r} is not a value here")
    if isinstance(v, bool) or not isinstance(v, (numbers.Real, tuple, Mapping)):
        raise BuildError(f"{where}: row {f['row']!r}: cannot read {v!r} as an estimate (a number, (value, lo, hi), "
                         "a mapping with value/lo/hi, sp.Est or sp.Missing)")  # fmt: skip
    if isinstance(v, numbers.Real):
        value, lo, hi = float(v), None, None
    elif isinstance(v, tuple):
        if len(v) != 3:
            raise BuildError(f"{where}: row {f['row']!r}: a tuple is (value, lo, hi), got {len(v)} items")
        value, lo, hi = (float(x) for x in v)
    else:
        if "value" not in v:
            raise BuildError(f"{where}: row {f['row']!r}: a mapping needs 'value' (and optional 'lo', 'hi')")
        value, lo, hi = v["value"], v.get("lo"), v.get("hi")
    kw = {"cell": _fill(cell_t, f, where), "key": _fill(key_t, f, where)}
    if getattr(owner, "label", None) is not None:
        kw["label"] = owner.label
    if getattr(owner, "interval", None) is not None:
        kw["interval"] = owner.interval
    try:
        return Est(value, lo, hi, **kw)
    except ValueError as e:
        raise BuildError(f"{where}: row {f['row']!r}: {e}") from None


def _cells(cells, owner, keys: list, vocab, kind: str, role: str | None, where: str, allowed: tuple) -> dict:
    lanes = bool(keys) and isinstance(keys[0], tuple)
    if callable(cells) and not isinstance(cells, Mapping):
        raw = {k: (cells(*k) if lanes else cells(k)) for k in keys}
    else:
        raw = dict(cells)
    templated = any(getattr(owner, a, None) is not None for a in ("cell", "key", "label", "interval"))
    if not templated and all(isinstance(v, (*allowed, Missing)) for v in raw.values()):
        return cells if isinstance(cells, Mapping) else raw  # nothing to bind: the very same mapping
    return {k: _value(v, _fields(vocab, kind, k, role), owner, where, allowed) for k, v in raw.items()}


def _table(t: DotTable, vocab, figure_id: str) -> DotTable:
    keys = _keys(t.rows, t.lanes)

    def col(c):
        if isinstance(c, ColumnGroup):
            return dataclasses.replace(c, columns=[col(cc) for cc in c.columns])
        if isinstance(c, DotColumn):
            series = [dataclasses.replace(s, cells=_cells(s.cells, s, keys, vocab, t.kind, s.role,
                                                          f"{figure_id}: {c.header!r} {s.role}", (Est,)))
                      for s in c.series]  # fmt: skip
            return dataclasses.replace(c, series=series)
        if isinstance(c, TextColumn):
            return dataclasses.replace(c, cells=_cells(c.cells, c, keys, vocab, t.kind, c.role,
                                                       f"{figure_id}: {c.header!r}", (Est, Count)))  # fmt: skip
        return c

    return dataclasses.replace(t, columns=[col(c) for c in t.columns])


def _stack(s: Stack, vocab, figure_id: str) -> Stack:
    segs = [dataclasses.replace(seg, shares=_cells(seg.shares, seg, list(s.rows), vocab, s.kind, seg.role,
                                                   f"{figure_id}: {seg.name!r}", (Est,)))
            for seg in s.segments]  # fmt: skip
    cols = [dataclasses.replace(c, cells=_cells(c.cells, c, list(s.rows), vocab, s.kind, c.role,
                                                f"{figure_id}: {c.header!r}", (Est, Count))) for c in s.columns]  # fmt: skip
    return dataclasses.replace(s, segments=segs, columns=cols)

