"""The dot table: entities as rows, conditions as columns. A column is a panel of dots on its own x axis, or a text
column of numbers. Rows are zebra-striped; each role colour in a panel is named by its word above the first row; a
status tag sits on its row's reserved second line, inside the span of the cells it belongs to, and the panel's lines
stop at that line so no tag crosses one.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field

from matplotlib.patches import Rectangle

from styles_plot._model import ColumnGroup, Count, DotColumn, DotTable, Est, Gutter, Missing, TextColumn
from styles_plot._grid import STRIP_GAP, place_in_line, widen
from styles_plot._render import LANE_INDENT, BuildError, Canvas, Ctx, Plan
from styles_plot._tags import tag
from styles_plot._text import PT, line_h

TOP = 0.08  # inches above the first header line
SUB_GAP = 0.06  # inches of air inside a row's second line
RIGHT = 0.1  # inches right of the last column
MIN_PANEL = 0.7  # inches: the narrowest a shared panel may get
TIE_PT = 0.5  # a value label's two sides nearer than this (points) are a tie, and it goes right


@dataclass
class _Col:
    spec: DotColumn | TextColumn | Gutter
    group: ColumnGroup | None
    x: float = 0.0
    w: float = 0.0
    pid: int = -1  # panel id, for matching a panel with its axis title and cue
    header: list[str] = field(default_factory=list)
    header_role: str | None = None  # the header is this role's word: drawn in its colour, no colour word above
    title: list[str] = field(default_factory=list)
    cue: list[str] = field(default_factory=list)
    title_span: tuple[float, float] | None = None  # a title shared by a group's panels: centred over this span
    title_panels: list = field(default_factory=list)  # the panels a shared title names
    strip: list = field(default_factory=list)  # [(x_left, level, word, colour, weight, size, tags)]
    texts: dict = field(default_factory=dict)  # text column: row -> [(text, colour, weight, tags)]

    @property
    def is_panel(self) -> bool:
        return isinstance(self.spec, DotColumn)

    @property
    def is_text(self) -> bool:
        return isinstance(self.spec, TextColumn)

    def dx(self, v: float) -> float:
        """A data x of this panel, in inches from the panel's left edge."""
        lo, hi = self.spec.xlim
        return (v - lo) / (hi - lo) * self.w

    def per_inch(self) -> float:
        lo, hi = self.spec.xlim
        return (hi - lo) / self.w


@dataclass
class _Row:
    key: str
    name: str
    top: float = 0.0
    h: float = 0.0
    tags: list = field(default_factory=list)  # [(x0, lines, cell, claim, full text, line key)]
    notes: list = field(default_factory=list)  # [(column, words, line key)]
    lines: list = field(default_factory=list)  # [(cell key, lane label, y offset from top)]: one per lane, or the row
    bands: list = field(default_factory=list)  # word bands under a line: [(y offset, height, items)]
    name_dy: float = 0.0

    @property
    def mid(self) -> float:
        return self.top + self.name_dy

    @property
    def keys(self) -> list:
        return [k for k, _label, _dy in self.lines]


@dataclass
class _Layout:
    table: DotTable
    rows: list[_Row]
    cols: list[_Col]
    groups: list[ColumnGroup]
    width: float
    note_h: float = 0.0
    group_lines: dict = field(default_factory=dict)  # id(group) -> wrapped header lines
    group_h: float = 0.0
    head: float = 0.0  # top of the strip, inches from the block top
    strip_h: float = 0.0
    body_end: float = 0.0
    tick_h: float = 0.0
    title_h: float = 0.0
    height: float = 0.0
    slack: float = 0.0  # inches the columns leave free (only when every panel has a fixed width)
    header_min: dict = field(default_factory=dict)  # id(free panel) -> the narrowest width that keeps its header within


# ---- plan ------------------------------------------------------------------------------------------------------------
def plan(t: DotTable, ctx: Ctx, width: float, label_w: float) -> Plan:
    ctx.check_rows(t.kind, t.rows)
    _validate(t, ctx)
    if not any(isinstance(c, DotColumn) for c, _g in t.flat_columns()):
        ctx.findings.append(("SP612", "a table of numbers only (no dot column): write it as a markdown table, not a "
                                      "figure"))  # fmt: skip
    rows = [_Row(r, ctx.entity_name(t.kind, r)) for r in t.rows]
    for r in rows:  # the cell keys of each row: the row itself, or (row, lane) per lane
        r.lines = [((r.key, ln.key), ln.label, 0.0) for ln in t.lanes] if t.lanes else [(r.key, "", 0.0)]
    lay = _Layout(t, rows, [_Col(c, g) for c, g in t.flat_columns()], [], width)
    for c in lay.cols:
        if c.group is not None and not any(g is c.group for g in lay.groups):
            lay.groups.append(c.group)
    _text_cells(lay, ctx)
    _widths(lay, ctx, label_w)
    for c in lay.cols:
        if c.is_panel:
            c.spec = _ranges(c.spec, c.w, t, ctx)
    enc = _statuses(lay, ctx)
    _vertical(lay, ctx)
    return Plan(lay.height, lambda cv: _draw(cv, ctx, lay), enc)


def _validate(t: DotTable, ctx: Ctx) -> None:
    for c, _g in t.flat_columns():
        if isinstance(c, (DotColumn, TextColumn)):
            ctx.unit(c.unit)
        if isinstance(c, TextColumn) and c.role:
            ctx.role_hex(c.role)
        if not isinstance(c, DotColumn):
            continue
        if ctx.unit(c.unit).scale == "log":
            raise BuildError(f"{ctx.figure_id}: column {c.header!r}: a dot-table panel is linear; unit {c.unit!r} is "
                             "log scale. Use a Sweep for a log axis, or a unit of the log values")  # fmt: skip
        if not c.series:
            raise BuildError(f"{ctx.figure_id}: column {c.header!r} has no series")
        if not c.weight > 0:
            raise BuildError(f"{ctx.figure_id}: column {c.header!r} has weight {c.weight!r}; it must be positive")
        if c.width is not None and c.weight != 1.0:
            raise BuildError(f"{ctx.figure_id}: column {c.header!r} sets both width= (inches) and weight= (a share of "
                             "the free width); keep one")  # fmt: skip
        if c.xlim is not None and c.xlim[1] <= c.xlim[0]:
            raise BuildError(f"{ctx.figure_id}: column {c.header!r} has xlim {c.xlim}")
        for s in c.series:
            ctx.role_hex(s.role)
            if s.role == "control" and not s.control:
                raise BuildError(f"{ctx.figure_id}: a control series needs control=<a [controls] name> ({c.header!r})")
        if c.connect and not all(any(s.role == r for s in c.series) for r in c.connect):
            raise BuildError(f"{ctx.figure_id}: connect={c.connect} names a role with no series in {c.header!r}")
        keys = [(r, ln.key) for r in t.rows for ln in t.lanes] if t.lanes else list(t.rows)
        for k in keys:
            roles = [s.role for s in c.series if isinstance(s.cells.get(k), Est)]
            twice = sorted({r for r in roles if roles.count(r) > 1})
            if twice:
                what = "two grey control dots" if twice[0] == "control" else f"two estimates of {twice[0]!r}"
                raise BuildError(f"{ctx.figure_id}: {what} on one line of column {c.header!r} ({k!r}); one colour "
                                 "means one estimate per line: give the second its own column (or lane), header and "
                                 "axis (GRAMMAR.md, D)")  # fmt: skip


def _text_cells(lay: _Layout, ctx: Ctx) -> None:
    """Format every text-column cell once (numbers are logged here)."""
    for c in lay.cols:
        if c.is_text:
            for key in (k for r in lay.rows for k in r.keys):
                c.texts[key] = text_parts(ctx, c.spec, key)


def text_parts(ctx: Ctx, col: TextColumn, key) -> list:
    """A text column's cell as [(text, colour, weight, tags)]: a value and its interval, a count, or missing words."""
    muted = ctx.chrome("muted")
    ink = ctx.role_hex(col.role) if col.role else ctx.chrome("text")
    meta_role = {"role": col.role} if col.role else {}
    val = col.cells.get(key)
    if val is None:
        return []
    if isinstance(val, Missing):
        return [(val.words, muted, "normal", {"kind": "missing"})]
    if isinstance(val, Count):
        return [(ctx.count(val.k, val.n, val.key), ink, "normal",
                 {"kind": "value", "key": val.key, "cell": val.cell, "unit": col.unit, **meta_role})]  # fmt: skip
    parts = [(ctx.value(col.unit, val.value, val.key), ink, "normal",
              {"kind": "value", "key": val.key, "cell": val.cell, "unit": col.unit, **meta_role})]  # fmt: skip
    if val.lo is not None:
        parts.append((" " + ctx.interval(col.unit, val.lo, val.hi, val.key), muted, "normal",
                      {"kind": "value", "key": f"{val.key}.interval", "cell": val.cell, "unit": col.unit}))  # fmt: skip
    return parts


def _widths(lay: _Layout, ctx: Ctx, label_w: float) -> None:
    th, sz = ctx.theme, ctx.sizes
    fixed = 0.0
    for c in lay.cols:
        if isinstance(c.spec, Gutter):
            c.w = c.spec.width
        elif c.is_text:
            ws = [sum(ctx.measure(s, sz.value, wt)[0] for s, _c, wt, _m in parts) for parts in c.texts.values()]
            longest_word = max((ctx.measure(w, sz.header, "bold")[0] for w in c.spec.header.split()), default=0.0)
            c.w = max([*ws, longest_word, 0.5]) + 0.05
        elif c.spec.width is not None:
            c.w = c.spec.width
        fixed += c.w
    free = [c for c in lay.cols if c.is_panel and c.spec.width is None]
    avail = lay.width - label_w - RIGHT - fixed - th.pad * len(lay.cols)
    if free:
        total = sum(c.spec.weight for c in free)
        for c in free:
            c.w = avail * c.spec.weight / total
        narrowest = min(c.w for c in free)
        if narrowest < MIN_PANEL:
            raise BuildError(f"{ctx.figure_id}: the table does not fit {lay.width} in ({narrowest:.2f} in for a panel)")
    elif avail < -1e-6:
        raise BuildError(f"{ctx.figure_id}: the table is {-avail:.2f} in wider than {lay.width} in")
    else:
        lay.slack = avail
    x, pid = label_w, 0
    for c in lay.cols:
        c.x = x
        x += c.w + th.pad
        if c.is_panel:
            c.pid, pid = pid, pid + 1


def _ranges(spec: DotColumn, w: float, t: DotTable, ctx: Ctx) -> DotColumn:
    """The column's xlim and xticks: its own, else its unit's, else computed from what it draws."""
    if spec.xlim is not None and spec.xticks is not None:
        return spec
    unit = ctx.unit(spec.unit)
    xlim, xticks = spec.xlim or unit.lim, spec.xticks
    if xlim is None:
        xlim = _computed(spec, w, t, ctx)
    if xticks is None:
        own = [v for v in unit.ticks if xlim[0] <= v <= xlim[1]] if unit.ticks and spec.xlim is None else None
        xticks = own or _interior_ticks(xlim, w, ctx)
    return dataclasses.replace(spec, xlim=tuple(xlim), xticks=tuple(xticks))


def _interior_ticks(xlim, w: float, ctx: Ctx) -> list[float]:
    """Round ticks inside the range, none within a quarter step of its ends (a label there would meet the next
    panel's), as many as the panel's width holds with their labels apart."""
    import math

    from matplotlib.ticker import MaxNLocator

    lo, hi = xlim
    best: list[float] = []
    for n in (4, 3, 2, 1):
        vals = MaxNLocator(n, steps=[1, 2, 2.5, 5, 10]).tick_values(lo, hi)
        step = float(vals[1] - vals[0])
        first = math.ceil((lo + step / 4) / step) * step
        tv = [round(first + i * step, 12) for i in range(int((hi - step / 4 - first) / step + 1e-9) + 1)]
        tv = [0.0 if abs(x) < 1e-12 else x for x in tv]
        if not tv:
            continue
        widest = max(ctx.measure(ctx.tick(x), ctx.sizes.tick)[0] for x in tv)
        if len(tv) == 1 or step / (hi - lo) * w >= widest + 0.15:
            return tv
        best = best or tv[:1]
    return best or [round((lo + hi) / 2, 12)]


def _data_span(spec: DotColumn, t: DotTable) -> tuple[list[float], list[tuple[float, Est]]]:
    """Every x the column draws, and its labelled estimates (with the x their label starts from)."""
    keys = [(r, ln.key) for r in t.rows for ln in t.lanes] if t.lanes else list(t.rows)
    xs, labelled = [], []
    for s in spec.series:
        for k in keys:
            v = s.cells.get(k)
            if isinstance(v, Est):
                xs += [v.value] + ([v.lo, v.hi] if v.lo is not None else [])
                if v.label:
                    labelled.append((v.hi if v.hi is not None else v.value, v))
    xs += list(spec.ticks.values()) + [r.x for r in spec.rules] + (list(spec.band) if spec.band else [])
    return xs, labelled


def _step(lo: float, hi: float) -> float:
    from matplotlib.ticker import MaxNLocator

    vals = MaxNLocator(3, steps=[1, 2, 2.5, 5, 10]).tick_values(lo, hi)
    return float(vals[1] - vals[0])


def _computed(spec: DotColumn, w: float, t: DotTable, ctx: Ctx) -> tuple[float, float]:
    """A range from the data: padded by at least 0.4 of a tick step, its ends snapped out to a quarter step (panels on
    similar data share a range), widened until the rightmost value label fits right of its mark."""
    import math

    xs, labelled = _data_span(spec, t)
    if not xs:
        raise BuildError(f"{ctx.figure_id}: column {spec.header!r} draws nothing to range its axis on; give xlim")
    dlo, dhi = min(xs), max(xs)
    step = _step(dlo, dhi) if dhi > dlo else (abs(dhi) or 1.0)
    pad = max(0.05 * (dhi - dlo), 0.4 * step)
    q = step / 4
    lo, hi = math.floor((dlo - pad) / q) * q, math.ceil((dhi + pad) / q) * q
    for _ in range(4):  # widen until the rightmost label fits right of its mark, inside the panel's right pad
        need = hi
        for right, v in labelled:
            text = ctx.vocab.format(v.value, spec.unit)
            k = ctx.measure(text, ctx.sizes.value)[0] + (ctx.marks.dot_size / 2 + 6) * PT - 0.7 * ctx.theme.pad
            if k > 0:
                need = max(need, right + k * (hi - lo) / w)
        if need <= hi + 1e-9:
            break
        hi = math.ceil(need / q) * q
    return lo, hi


def _sizing(c: _Col, lay: _Layout) -> dict:
    """What sets a panel's width, and the most it can get, for a fix that widens it (`_grid.widen`). Widening one
    panel shrinks the free panels in proportion; the most is where the first of them reaches its own minimum (its
    header within the lines it has now, and `MIN_PANEL`), so a fix never breaks a neighbour's header."""
    free = [x for x in lay.cols if x.is_panel and x.spec.width is None]
    others = [x for x in free if x is not c]

    def floor(x: _Col) -> float:  # a header already past its lines is its own problem: only MIN_PANEL holds it
        m = lay.header_min.get(id(x), MIN_PANEL)
        return max(m if m <= x.w + 1e-9 else MIN_PANEL, MIN_PANEL)

    shrink = max((floor(x) / x.w for x in others), default=1.0)  # the least the others may keep, as a fraction
    room = sum(x.w for x in others) * (1 - shrink)
    if c.spec.width is not None:
        return {"fixed": True, "max_in": round(c.w + lay.slack + room, 4)}
    return {"weight": c.spec.weight, "free_weight": sum(x.spec.weight for x in free),
            "free_in": round(sum(x.w for x in free), 4), "max_in": round(c.w + room, 4)}  # fmt: skip


def _header_min(c: _Col, ctx: Ctx) -> float:
    """The narrowest width (to 0.01 in) at which a panel's header wraps to the target's lines at most."""
    sz, most = ctx.sizes, ctx.theme.max_header_lines
    lo, hi = MIN_PANEL, max(MIN_PANEL, ctx.measure(c.spec.header, sz.header, "bold")[0] + 0.01)
    if not c.spec.header or len(ctx.wrap(c.spec.header, lo, sz.header, "bold")) <= most:
        return lo
    while hi - lo > 0.01:
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if len(ctx.wrap(c.spec.header, mid, sz.header, "bold")) <= most else (mid, hi)
    return hi


def _header_finding(c: _Col, lay: _Layout, ctx: Ctx) -> None:
    """SP613: a header that wraps past the target's limit, with the width or weight that keeps it within."""
    sz, most = ctx.sizes, ctx.theme.max_header_lines
    need = c.w
    while len(ctx.wrap(c.spec.header, need, sz.header, "bold")) > most and need < 20:
        need += 0.05
    if c.is_panel:
        wider = widen(_sizing(c, lay), need)
        fix = f"{wider}, or shorten the header" if wider else "shorten the header"
    else:  # a text column is as wide as its numbers
        fix = f"a header that fits {c.w:.2f} in on {ctx.theme.max_header_lines} lines"
    ctx.findings.append(("SP613", f"header {c.spec.header!r} wraps to {len(c.header)} lines (at most {most})",
                         {"subject": c.spec.header, "fix": f"{fix}, or move the qualifier into the unit title"}))  # fmt: skip


def _cells(col: DotColumn, row: str):
    for s in col.series:
        v = s.cells.get(row)
        if v is not None:
            yield s, v


def _statuses(lay: _Layout, ctx: Ctx) -> set:
    """The encodings the table draws, and each row's status tags (spanning their cells' group) and notes."""
    enc: set = set()
    spans: dict[tuple[str, str], list] = {}  # (row, cell) -> [x0, x1, status]
    for c in lay.cols:
        if not (c.is_panel or c.is_text):
            continue
        members = [m for m in lay.cols if c.group is not None and m.group is c.group] or [c]
        gx0, gx1 = min(m.x for m in members), max(m.x + m.w for m in members)
        for r in lay.rows:
            vals = [(k, v) for k in r.keys for v in (_cells(c.spec, k) if c.is_panel else [(None, c.spec.cells.get(k))])]
            for k, (s, val) in vals:
                if not isinstance(val, (Est, Count)):
                    continue
                st = ctx.status(val.cell)
                if c.is_panel:
                    if st.hollow:
                        enc.add(("post_hoc",))
                    if val.lo is not None:
                        enc.add(("whisker", val.interval))
                    if s.role == "control":
                        enc.add(("control", s.control))
                if st.claim != "claimed" and val.cell:
                    sp = spans.setdefault((r.key, val.cell), [gx0, gx1, st, k])
                    sp[0], sp[1] = min(sp[0], gx0), max(sp[1], gx1)
                if isinstance(val, Est) and val.note:
                    r.notes.append((c, val.note, k))
        if c.is_panel and c.spec.ticks:
            enc.add(("tick",))
        if c.is_panel and c.spec.band:
            enc.add(("band", c.spec.band_name))
    sz = ctx.sizes
    for r in lay.rows:
        for (rk, cell), (x0, x1, st, k) in spans.items():
            if rk != r.key:
                continue
            full = ctx.words.descriptive if st.claim == "descriptive" else ctx.words.not_claimed.format(st.claim_reason)
            r.tags.append((x0, ctx.wrap(full, x1 - x0, sz.tag), cell, st.claim, full, k))
        r.h = _lanes(r, ctx, lay.table.row_sub.get(r.key, ""))
    return enc


def _band(ctx: Ctx, tags, notes, row_sub: str) -> tuple[float, list]:
    """A word band under a line: its tags left-aligned in their cells' span, its notes right-aligned at their column's
    end (on the next line when they would touch a tag), the row's grey sub-line in the label column."""
    sz = ctx.sizes
    lh = line_h(sz.tag)
    items = [("tag", x0, lines, cell, claim, full) for x0, lines, cell, claim, full, _k in tags]
    n = max((len(lines) for _x0, lines, *_r in tags), default=0)
    spans = [(x0, x0 + max(ctx.measure(t, sz.tag)[0] for t in lines)) for x0, lines, *_r in tags]
    extra = 0
    for c, words, _k in notes:
        a, b = c.x + c.w - ctx.measure(words, sz.tag)[0], c.x + c.w
        line = n if any(a < y1 + 0.1 and y0 - 0.1 < b for y0, y1 in spans) else 0
        extra = max(extra, line + 1)
        items.append(("note", c, words, line))
    if row_sub:
        items.append(("row_sub", row_sub))
    lines = max(n, extra, 1 if row_sub else 0)
    if not lines:
        return 0.0, []
    return max(ctx.theme.sub_h, lines * lh + SUB_GAP), items


def _lanes(r: _Row, ctx: Ctx, row_sub: str) -> float:
    """Lay out a row's lines and word bands; returns the row's height. A row without lanes has one line and its band
    under it. Labelled lanes sit under the row's name, each on its own line; unlabelled lanes share the row's height,
    named by colour words above the table. A lane's tags and notes go in a band right under that lane."""
    rh = ctx.theme.row_h
    keyed = lambda k: ([t for t in r.tags if t[5] == k], [n for n in r.notes if n[2] == k])  # noqa: E731
    if len(r.lines) == 1 and not r.lines[0][1]:
        k = r.lines[0][0]
        r.lines = [(k, "", rh / 2)]
        r.name_dy = rh / 2
        h, items = _band(ctx, r.tags, r.notes, row_sub)
        r.bands = [(rh, h, items)] if items else []
        return rh + h
    labelled = any(label for _k, label, _dy in r.lines)
    lane_h = rh * (0.8 if labelled else 0.62)
    head = rh * 0.85 if labelled else 0.0
    bands = [_band(ctx, *keyed(k), "") for k, _l, _dy in r.lines]
    plain = not any(items for _h, items in bands)
    y = head if labelled or not plain else max(0.0, (rh - len(r.lines) * lane_h) / 2)
    out, r.bands = [], []
    for (k, label, _dy), (h, items) in zip(r.lines, bands):
        out.append((k, label, y + lane_h / 2))
        y += lane_h
        if items:
            r.bands.append((y, h, items))
            y += h
    r.lines = out
    h, items = _band(ctx, [], [], row_sub)
    if items:
        r.bands.append((y, h, items))
        y += h
    total = max(y, rh)
    r.name_dy = head / 2 if labelled else (out[0][2] + out[-1][2]) / 2
    return total


def _vertical(lay: _Layout, ctx: Ctx) -> None:
    """Headers, the strip of role words above the first row, rows, and the bottom (ticks, unit titles, cues)."""
    sz, v = ctx.sizes, ctx.vocab
    lay.note_h = line_h(sz.tag) + 0.06 if lay.table.note else 0.0
    lay.group_lines = {}
    for g in lay.groups:
        members = [c for c in lay.cols if c.group is g]
        span = members[-1].x + members[-1].w - members[0].x
        lay.group_lines[id(g)] = ctx.wrap(g.header, span, sz.header, "bold")
    lay.group_h = max((len(v) for v in lay.group_lines.values()), default=0) * line_h(sz.header) + (0.06 if lay.groups else 0.0)
    if sum(c.is_panel for c in lay.cols) > 1:  # what each shared panel may give up, for fixes that widen another
        lay.header_min = {id(c): _header_min(c, ctx) for c in lay.cols if c.is_panel and c.spec.width is None}
    for c in lay.cols:
        if c.is_panel or c.is_text:
            c.header = ctx.wrap(c.spec.header, c.w, sz.header, "bold") if c.spec.header else []
            if len(c.header) > ctx.theme.max_header_lines:
                _header_finding(c, lay, ctx)
            u = v.unit(c.spec.unit)
            show = c.is_panel or c.spec.unit_title
            c.title = ctx.wrap(u.title, c.w + ctx.theme.pad * 0.8, sz.axis) if show else []
            if c.is_panel and u.cue:
                c.cue = ctx.wrap(v.cue(u.name), c.w + ctx.theme.pad * 0.8, sz.cue)
    for g in lay.groups:  # small multiples: a group's panels on one unit share one axis title and one cue
        members = [c for c in lay.cols if c.group is g and c.is_panel]
        if len(members) > 1 and len({c.spec.unit for c in members}) == 1 and all(c.group is g for c in members):
            u = v.unit(members[0].spec.unit)
            x0, x1 = members[0].x, members[-1].x + members[-1].w
            first = members[0]
            first.title_span, first.title_panels = (x0, x1), [c.pid for c in members]
            first.title = ctx.wrap(u.title, x1 - x0, sz.axis)
            first.cue = ctx.wrap(v.cue(u.name), x1 - x0, sz.cue) if u.cue else []
            for c in members[1:]:
                c.title, c.cue = [], []
    header_h = max((len(c.header) for c in lay.cols), default=0) * line_h(sz.header) + 0.08
    seen_rules: set = set()  # an identical rule (same place and words) is labelled over its first column only
    levels = max((_strip(c, lay, ctx, seen_rules) for c in lay.cols if c.is_panel), default=0)
    lay.head = TOP + lay.note_h + lay.group_h + header_h
    lay.strip_h = levels * line_h(sz.role_word) + 0.1
    y = lay.head + lay.strip_h
    for r in lay.rows:
        r.top = y
        y += r.h
    lay.body_end = y
    lay.tick_h = line_h(sz.tick) + 0.06 if any(c.is_panel for c in lay.cols) else 0.0
    lay.title_h = max((len(c.title) for c in lay.cols), default=0) * line_h(sz.axis)
    cue_lines = max((len(c.cue) for c in lay.cols), default=0)
    cue_h = cue_lines * line_h(sz.cue) + 0.04 if cue_lines else 0.0
    lay.height = lay.body_end + lay.tick_h + lay.title_h + cue_h + 0.12


def _strip(c: _Col, lay: _Layout, ctx: Ctx, seen_rules: set) -> int:
    """A panel's role words on one line above the first row, in the order their dots appear (left to right), and its
    rule labels on the line above them where they would collide. Returns the number of lines."""
    sz = ctx.sizes
    first = {k: (i, j) for i, r in enumerate(lay.rows) for j, k in enumerate(r.keys)}
    words, seen = [], set()
    for s in c.spec.series:  # a header that is a role's word names that role: no colour word above the rows
        if s.role != "control" and c.spec.header and c.spec.header == (s.word or ctx.vocab.role(s.role).word):
            c.header_role = s.role
    for s in c.spec.series:
        word = None if s.role == "control" else (s.word or ctx.vocab.role(s.role).word)
        if word is None or word in seen or (c.header_role == s.role and word == c.spec.header):
            continue
        xs = sorted((first[rk], val.value) for rk, val in s.cells.items() if isinstance(val, Est) and rk in first)
        if not xs:
            continue
        seen.add(word)
        words.append((c.dx(xs[0][1]), ctx.measure(word, sz.role_word, "bold")[0],
                      (word, ctx.role_hex(s.role), "bold", sz.role_word, {"kind": "role_word", "role": s.role})))  # fmt: skip
    need = sum(w for _xc, w, _p in words) + STRIP_GAP * max(len(words) - 1, 0)
    if words and need > c.w + ctx.theme.pad * 0.7:  # one line is the rule: say so instead of overlapping silently
        words = [(xc, w, (*p[:4], {**p[4], "line_full": (round(need, 2), round(c.w, 2)), "sizing": _sizing(c, lay)})) for xc, w, p in words]
    line = place_in_line(words, c.w)
    occupied = [(x0, x0 + ctx.measure(p[0], sz.role_word, "bold")[0], 0) for x0, p in line]
    c.strip = [(x0, 0, *p) for x0, p in line]
    levels = 1 if line else 0
    # rule labels: wrapped to the panel's width, each a block of consecutive levels clear of the words and each other
    for rl in sorted((rl for rl in c.spec.rules if rl.label), key=lambda rl: rl.x):
        if (rl.x, rl.label, rl.unit) in seen_rules:
            continue
        seen_rules.add((rl.x, rl.label, rl.unit))
        text = rule_label(ctx, rl)
        lines = ctx.wrap(text, c.w, sz.tag)
        w = max(ctx.measure(t, sz.tag)[0] for t in lines)
        x0 = min(max(c.dx(rl.x) - w / 2, 0.0), max(c.w - w, 0.0))
        level = 0
        while any(lv in range(level, level + len(lines)) and x0 < b + STRIP_GAP and a < x0 + w + STRIP_GAP
                  for a, b, lv in occupied):  # fmt: skip
            level += 1
        meta = {"kind": "rule_label", "full": text, **({"key": rl.key} if rl.key else {})}
        for i, t in enumerate(lines):  # the first line on top
            lv = level + len(lines) - 1 - i
            occupied.append((x0, x0 + w, lv))
            c.strip.append((x0, lv, t, ctx.chrome("muted"), "normal", sz.tag, meta))
        levels = max(levels, level + len(lines))
    return levels


# ---- draw ------------------------------------------------------------------------------------------------------------
def _draw(cv: Canvas, ctx: Ctx, lay: _Layout) -> None:
    sz = ctx.sizes
    ink, muted = ctx.chrome("text"), ctx.chrome("muted")

    # zebra stripes across the table, cut at gutters
    spans, x0 = [], 0.0
    for c in lay.cols:
        if isinstance(c.spec, Gutter):
            spans.append((x0, c.x - ctx.theme.pad / 2))
            x0 = c.x + c.w + ctx.theme.pad / 2
    spans.append((x0, lay.width))
    for i, r in enumerate(lay.rows):
        if i % 2 == 0:
            for a, b in spans:
                cv.rect(a, r.top, b - a, r.h, ctx.chrome("zebra"), kind="zebra")

    for r in lay.rows:
        cv.text(0.08, r.mid, r.name, kind="row_label", size=sz.label, weight="bold", color=ink)
        for _k, label, dy in r.lines:
            if label:
                cv.text(0.08 + LANE_INDENT, r.top + dy, label, kind="lane_label", size=sz.tag, color=muted)


    if lay.table.note:
        cv.text(0.08, TOP + lay.note_h / 2, lay.table.note, kind="subtitle", size=sz.tag, color=muted)
    top = TOP + lay.note_h
    for g in lay.groups:
        gx = min(c.x for c in lay.cols if c.group is g)
        for i, t in enumerate(lay.group_lines[id(g)]):
            cv.text(gx, top + (i + 0.5) * line_h(sz.header), t, kind="header", size=sz.header, weight="bold",
                    color=ink, full=g.header)  # fmt: skip
    for c in lay.cols:
        named = {"kind": "role_word", "role": c.header_role, "color": ctx.role_hex(c.header_role)} if c.header_role \
            else {"kind": "header", "color": ink}  # fmt: skip
        for i, s in enumerate(c.header):
            cv.text(c.x, top + lay.group_h + (i + 0.5) * line_h(sz.header), s, size=sz.header, weight="bold",
                    full=c.spec.header, **named)  # fmt: skip

    for c in lay.cols:
        if c.is_panel:
            _panel(cv, ctx, lay, c)
        elif c.is_text:
            for r in lay.rows:
                for k, _label, dy in r.lines:
                    cv.rich(c.x, r.top + dy, c.texts[k], size=sz.value)

    for r in lay.rows:
        for dy, _h, items in r.bands:
            y0 = r.top + dy + SUB_GAP / 2
            for item in items:
                if item[0] == "tag":
                    _k, x0, lines, cell, claim, full = item
                    for i, s in enumerate(lines):
                        cv.text(x0, y0 + (i + 0.5) * line_h(sz.tag), s, kind="status_tag", size=sz.tag, color=muted,
                                cell=cell, claim=claim, full=full)  # fmt: skip
                elif item[0] == "note":
                    _k, c, words, line = item
                    cv.text(c.x + c.w, y0 + (line + 0.5) * line_h(sz.tag), words, kind="note", size=sz.tag,
                            color=muted, ha="right")  # fmt: skip
                else:
                    cv.text(0.08, y0 + 0.5 * line_h(sz.tag), item[1], kind="row_sub", size=sz.tag, color=muted)

    _bottom(cv, ctx, lay)


def _bottom(cv: Canvas, ctx: Ctx, lay: _Layout) -> None:
    sz, muted = ctx.sizes, ctx.chrome("muted")
    for c in lay.cols:
        if not (c.is_panel or c.is_text):
            continue
        if c.is_panel:
            for tv in c.spec.xticks:
                cv.text(c.x + c.dx(tv), lay.body_end + 0.06 + line_h(sz.tick) / 2, ctx.tick(tv), kind="tick_label",
                        size=sz.tick, color=muted, ha="center", panel=c.pid)  # fmt: skip
        y = lay.body_end + lay.tick_h
        cx = (c.title_span[0] + c.title_span[1]) / 2 if c.title_span else c.x + c.w / 2
        panels = {"panels": c.title_panels} if c.title_panels else {}
        for i, s in enumerate(c.title):
            cv.text(cx, y + (i + 0.5) * line_h(sz.axis), s, kind="axis_title", size=sz.axis, color=muted, ha="center",
                    panel=c.pid, unit=c.spec.unit, full=ctx.vocab.unit(c.spec.unit).title, **panels)  # fmt: skip
        full = ctx.vocab.cue(c.spec.unit)
        for i, s in enumerate(c.cue):
            cv.text(cx, y + lay.title_h + (i + 0.5) * line_h(sz.cue), s, kind="cue", size=sz.cue, color=muted,
                    ha="center", panel=c.pid, axis="x", full=full, **panels)  # fmt: skip


def _segments(a: float, b: float, cuts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """The interval [a, b] minus the cut intervals."""
    out, cur = [], a
    for c0, c1 in sorted(cuts):
        if c1 <= cur or c0 >= b:
            continue
        if c0 > cur:
            out.append((cur, c0))
        cur = max(cur, c1)
    if cur < b:
        out.append((cur, b))
    return out


def _panel(cv: Canvas, ctx: Ctx, lay: _Layout, c: _Col) -> None:
    mk = ctx.marks
    spec: DotColumn = c.spec
    total = lay.body_end - lay.head
    ax = cv.axes(c.x, lay.head, c.w, total)
    ax.set_xlim(*spec.xlim)
    ax.set_ylim(total, 0)  # y: inches down from the top of the strip
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color(ctx.chrome("faint"))
    ax.set_xticks(list(spec.xticks), labels=[""] * len(spec.xticks))
    ax.tick_params(axis="x", length=3, color=ctx.chrome("faint"), pad=0)
    tag(ax, kind="panel", pid=c.pid, unit=spec.unit, cue=ctx.vocab.unit(spec.unit).cue, header=spec.header,
        **_sizing(c, lay))  # fmt: skip

    # vertical lines stop at a row's second line where a tag spans this panel
    cuts = [(r.top + dy - lay.head, r.top + dy + h - lay.head) for r in lay.rows for dy, h, items in r.bands
            if _band_in(items, c, ctx)]  # fmt: skip
    b0, b1 = lay.strip_h, total
    for tv in spec.xticks:
        for a, b in _segments(b0, b1, cuts):
            tag(ax.plot([tv, tv], [a, b], color=ctx.chrome("grid"), lw=0.8, zorder=0), kind="grid")
    lo, hi = spec.xlim
    vlines = [rl.x for rl in spec.rules]
    if lo < 0 < hi:
        vlines.append(0.0)
        for a, b in _segments(b0, b1, cuts):
            tag(ax.plot([0, 0], [a, b], color=ctx.chrome("muted"), lw=0.9, zorder=1), kind="zero")
    if spec.band:
        rect = Rectangle((spec.band[0], b0), spec.band[1] - spec.band[0], b1 - b0, facecolor=ctx.chrome("band"),
                         edgecolor="none", lw=0, zorder=0.5)  # fmt: skip
        ax.add_patch(rect)
        tag(rect, kind="band", band=spec.band_name)
    for rl in spec.rules:
        for a, b in _segments(b0, b1, cuts):
            tag(ax.plot([rl.x, rl.x], [a, b], color=ctx.chrome("rule"), lw=mk.rule_lw, ls=(0, mk.rule_dash), zorder=1),
                kind="rule")  # fmt: skip

    for r in lay.rows:
        for key, _label, dy in r.lines:
            _line(cv, ax, ctx, c, key, r.top + dy, lay.head, vlines)

    for x0, level, word, colr, weight, size, meta in c.strip:
        cv.text(c.x + x0, lay.head + lay.strip_h - 0.05 - (level + 0.5) * line_h(ctx.sizes.role_word), word,
                size=size, color=colr, weight=weight, **meta)  # fmt: skip


def _line(cv: Canvas, ax, ctx: Ctx, c: _Col, key, y_abs: float, head: float, vlines) -> None:
    """One line of a panel (a row, or a lane of a row): connector, grey tick, dots, missing words, value labels."""
    mk, spec = ctx.marks, c.spec
    y = y_abs - head
    ests ={s.role: val for s, val in _cells(spec, key) if isinstance(val, Est)}
    spans: list[tuple[float, float, float]] = []  # what a label on this line may not touch: data x0, x1, inches of pad
    if spec.connect and all(k in ests for k in spec.connect):
        a, b = ests[spec.connect[0]].value, ests[spec.connect[1]].value
        tag(ax.plot([a, b], [y, y], color=ctx.chrome("connector"), lw=mk.connector_lw, solid_capstyle="round",
                    zorder=2), kind="connector")  # fmt: skip
        spans.append((min(a, b), max(a, b), (mk.connector_lw / 2 + 2) * PT))
    if key in spec.ticks:
        tx, half = spec.ticks[key], mk.tick_half * ctx.theme.row_h
        tag(ax.plot([tx, tx], [y - half, y + half], color=ctx.palette.control, lw=mk.tick_lw, zorder=3), kind="tick",
            role="control")  # fmt: skip
        spans.append((tx, tx, (mk.tick_lw / 2 + 2) * PT))
    labels, missing = [], []
    r = (mk.dot_size / 2 + mk.hollow_edge + 4) * PT  # a dot's radius and the check's clearance
    for s, val in _cells(spec, key):
        if isinstance(val, Missing):
            missing.append(val.words)
            continue
        _dot(ax, ctx, s, val, y)
        spans.append((val.value, val.value, r))
        if val.lo is not None:
            spans.append((val.lo, val.hi, 0.0))
        if val.label:
            labels.append((val, s.role))
    for words in missing:  # after the marks: missing words keep clear of them too
        _missing(cv, ctx, c, y_abs, words, vlines, spans)
    _value_labels(cv, ctx, c, y_abs, labels, spans, vlines)


def _missing(cv: Canvas, ctx: Ctx, c: _Col, y: float, words: str, vlines, spans=()) -> None:
    """Missing-cell words where they touch no vertical line and no mark of their line: at the panel's left, else
    right-aligned at its right, else in the first gap wide enough."""
    w = ctx.measure(words, ctx.sizes.tag)[0]
    clear = 4 * PT
    blocked = sorted([(c.dx(v), c.dx(v)) for v in vlines] + [(c.dx(a) - e, c.dx(b) + e) for a, b, e in spans])
    candidates = [0.04, c.w - 0.04 - w]
    edges = [(0.0, 0.0), *blocked, (c.w, c.w)]
    candidates += [e0[1] + clear for e0, e1 in zip(edges, edges[1:]) if e1[0] - e0[1] - 2 * clear >= w]
    best = next((x0 for x0 in candidates if not any(a - clear < x0 + w and x0 - clear < b for a, b in blocked)), None)
    meta = {}
    if best is None:  # no free span is wide enough: say so (SP610) rather than cross a line quietly
        widest = max((e1[0] - e0[1] - 2 * clear for e0, e1 in zip(edges, edges[1:])), default=0.0)
        meta = {"no_room": (round(w, 2), round(max(widest, 0.0), 2))}
        best = candidates[0]
    cv.text(c.x + best, y, words, kind="missing", size=ctx.sizes.tag, color=ctx.chrome("muted"), **meta)


def rule_label(ctx: Ctx, rl) -> str:
    """A rule's label, its number (if any) printed in the rule's unit and logged under its key."""
    if rl.unit is None:
        return rl.label
    if rl.label.count("{}") != 1:
        raise BuildError(f"{ctx.figure_id}: rule label {rl.label!r} needs one {{}} for its number")
    return rl.label.format(ctx.value(rl.unit, rl.x, rl.key))


def _band_in(items, c: _Col, ctx: Ctx) -> bool:
    """Whether a word band holds words inside this panel's span (the panel's lines stop there)."""
    spans = []
    for item in items:
        if item[0] == "tag":
            spans.append((item[1], item[1] + max(ctx.measure(t, ctx.sizes.tag)[0] for t in item[2])))
        elif item[0] == "note":
            n = item[1]
            spans.append((n.x + n.w - ctx.measure(item[2], ctx.sizes.tag)[0], n.x + n.w))
    return any(a < c.x + c.w and c.x < b for a, b in spans)


def _dot(ax, ctx: Ctx, s, val: Est, y: float) -> list[float]:
    """A dot and its whisker; returns the x extents they cover."""
    mk, bg = ctx.marks, ctx.palette.chrome["background"]
    col = ctx.role_hex(s.role)
    st = ctx.status(val.cell)
    meta = {"role": s.role, "cell": val.cell, "timing": st.timing, "claim": st.claim}
    if s.role == "control":
        meta["control"] = s.control
    out = [val.value]
    if val.lo is not None:
        tag(ax.plot([val.lo, val.hi], [y, y], color=col, lw=mk.whisker_lw, solid_capstyle="butt", zorder=3),
            kind="whisker", interval=val.interval, **meta)  # fmt: skip
        out += [val.lo, val.hi]
    tag(ax.plot([val.value], [y], marker=mk.marker, ls="none", ms=mk.dot_size, color=col, mfc=bg if st.hollow else col,
                mec=col, mew=mk.hollow_edge if st.hollow else 0, zorder=4), kind="dot", hollow=st.hollow, **meta)  # fmt: skip
    return out


def _room(c: _Col, ctx: Ctx, value: float, label_in: float, marks) -> float | None:
    """The narrowest panel (inches) in which a value label `label_in` wide has a free gap beside its dot `value`, the
    xlim kept: a gap's data span grows with the panel, its marks' pads and the label do not. `marks` are (data x0, data
    x1, inches of pad); None when no width gives room (marks that touch in data never part)."""
    lo, hi = c.spec.xlim
    clear = 3 * PT
    ends = sorted(marks)
    need = []
    cur, pad = lo, 0.0
    for a, b, e in ends:
        if a > cur and (a <= value or cur >= value):
            need.append((label_in + pad + e + 2 * clear) * (hi - lo) / (a - cur))
        if b >= cur:
            cur, pad = b, e
    over = label_in + pad + clear - ctx.theme.pad * 0.7  # the right end: the label may run 0.7 pad past the axis
    if cur >= value and hi > cur:
        need.append(over * (hi - lo) / (hi - cur) if over > 0 else c.w)
    fits = [w for w in need if w > c.w]
    return math.ceil(min(fits) * 100) / 100 if fits else None


def _value_labels(cv: Canvas, ctx: Ctx, c: _Col, y: float, labels, spans, vlines) -> None:
    """The printed values of one line. Every mark, whisker, connector, tick, vertical line and placed label is an
    obstacle; each value goes into the free gap nearest its own dot (the right side on a tie: sides within `TIE_PT`
    of each other), from the rightmost dot
    leftwards, so the outer values take the outer sides. With no gap wide enough it sits right of its dot and the
    layout check reports it."""
    per = c.per_inch()
    lo, hi = c.spec.xlim
    clear = 3 * PT * per
    right_end = hi + ctx.theme.pad * 0.7 * per
    blocked = [(a - e * per, b + e * per) for a, b, e in spans] + [(xv, xv) for xv in vlines]
    marks = [*spans, *((xv, xv, 0.0) for xv in vlines)]

    def gaps() -> list[tuple[float, float]]:
        out, cur = [], lo
        for s0, e in sorted((s0 - clear, e + clear) for s0, e in blocked):
            if s0 > cur:
                out.append((cur, s0))
            cur = max(cur, e)
        if cur < right_end:
            out.append((cur, right_end))
        return out

    for val, role in sorted(labels, key=lambda lr: -lr[0].value):
        text = ctx.value(c.spec.unit, val.value, val.key)
        col = ctx.chrome("muted") if role == "control" else ctx.role_hex(role)
        wd = ctx.measure(text, ctx.sizes.value)[0] * per
        meta = {"kind": "value", "key": val.key, "cell": val.cell, "unit": c.spec.unit, "role": role}
        cands = []  # (distance, left side?, start x)
        for g0, g1 in gaps():
            if g1 - g0 < wd:
                continue
            if g0 >= val.value:  # right of the dot: as near as the gap allows
                cands.append((g0 - val.value, 0, g0))
            elif g1 <= val.value:  # left of the dot
                cands.append((val.value - g1, 1, g1 - wd))
        best = None
        if cands:  # sides within half a point of each other are a tie, and a tie goes right: float noise never decides
            near = min(d for d, _s, _x in cands) + TIE_PT * PT * per
            best = min((c for c in cands if c[0] <= near), key=lambda c: (c[1], c[0]))
        if best is None:  # no room at this width: the width that has room, for the check's fix
            room = _room(c, ctx, val.value, wd / per, marks)
            if room is not None:
                meta["room_w"] = room
        x0 = best[2] if best is not None else min(val.value + (ctx.marks.dot_size / 2 + 5) * PT * per, right_end - wd)
        blocked.append((x0, x0 + wd))
        cv.text(c.x + c.dx(x0), y, text, size=ctx.sizes.value, color=col, **meta)
