"""The dot table: entities as rows, conditions as columns. A column is a panel of dots on its own x axis, or a text
column of numbers. Rows are zebra-striped; each role colour in a panel is named by its word above the first row; a
status tag sits on its row's reserved second line, inside the span of the cells it belongs to, and the panel's lines
stop at that line so no tag crosses one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from matplotlib.patches import Rectangle

from styles_plot._model import ColumnGroup, Count, DotColumn, DotTable, Est, Gutter, Missing, TextColumn
from styles_plot._render import BuildError, Canvas, Ctx, Plan
from styles_plot._tags import tag
from styles_plot._text import PT, line_h

TOP = 0.08  # inches above the first header line
SUB_GAP = 0.06  # inches of air inside a row's second line
STRIP_GAP = 0.12  # inches between two words on one strip level
RIGHT = 0.1  # inches right of the last column


@dataclass
class _Col:
    spec: DotColumn | TextColumn | Gutter
    group: ColumnGroup | None
    x: float = 0.0
    w: float = 0.0
    pid: int = -1  # panel id, for matching a panel with its axis title and cue
    header: list[str] = field(default_factory=list)
    title: list[str] = field(default_factory=list)
    cue: list[str] = field(default_factory=list)
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
    sub: float = 0.0  # height of the second line; 0 when the row has none
    tags: list = field(default_factory=list)  # [(x0, lines, cell, claim, full text)]
    notes: list = field(default_factory=list)  # [(column, words)]

    @property
    def mid(self) -> float:
        return self.top + (self.h - self.sub) / 2

    @property
    def sub_top(self) -> float:
        return self.top + self.h - self.sub

    @property
    def sub_mid(self) -> float:
        return self.top + self.h - self.sub / 2


@dataclass
class _Layout:
    table: DotTable
    rows: list[_Row]
    cols: list[_Col]
    groups: list[ColumnGroup]
    width: float
    group_h: float = 0.0
    head: float = 0.0  # top of the strip, inches from the block top
    strip_h: float = 0.0
    body_end: float = 0.0
    tick_h: float = 0.0
    title_h: float = 0.0
    height: float = 0.0


# ---- plan ------------------------------------------------------------------------------------------------------------
def plan(t: DotTable, ctx: Ctx, width: float, label_w: float) -> Plan:
    ctx.check_rows(t.kind, t.rows)
    _validate(t, ctx)
    lay = _Layout(t, [_Row(r, ctx.entity_name(t.kind, r)) for r in t.rows], [_Col(c, g) for c, g in t.flat_columns()],
                  [], width)  # fmt: skip
    for c in lay.cols:
        if c.group is not None and not any(g is c.group for g in lay.groups):
            lay.groups.append(c.group)
    _text_cells(lay, ctx)
    _widths(lay, ctx, label_w)
    enc = _statuses(lay, ctx)
    _vertical(lay, ctx)
    return Plan(lay.height, enc, lambda cv: _draw(cv, ctx, lay))


def _validate(t: DotTable, ctx: Ctx) -> None:
    for c, _g in t.flat_columns():
        if isinstance(c, (DotColumn, TextColumn)):
            ctx.unit(c.unit)
        if isinstance(c, TextColumn) and c.role:
            ctx.role_hex(c.role)
        if not isinstance(c, DotColumn):
            continue
        if c.xlim[1] <= c.xlim[0]:
            raise BuildError(f"{ctx.figure_id}: column {c.header!r} has xlim {c.xlim}")
        for s in c.series:
            ctx.role_hex(s.role)
            if s.role == "control" and not s.control:
                raise BuildError(f"{ctx.figure_id}: a control series needs control=<a [controls] name> ({c.header!r})")
        if c.connect and not all(any(s.role == r for s in c.series) for r in c.connect):
            raise BuildError(f"{ctx.figure_id}: connect={c.connect} names a role with no series in {c.header!r}")


def _text_cells(lay: _Layout, ctx: Ctx) -> None:
    """Format every text-column cell once (numbers are logged here)."""
    muted = ctx.chrome("muted")
    for c in lay.cols:
        if not c.is_text:
            continue
        ink = ctx.role_hex(c.spec.role) if c.spec.role else ctx.chrome("text")
        meta_role = {"role": c.spec.role} if c.spec.role else {}
        for r in lay.rows:
            val = c.spec.cells.get(r.key)
            if val is None:
                parts = []
            elif isinstance(val, Missing):
                parts = [(val.words, muted, "normal", {"kind": "missing"})]
            elif isinstance(val, Count):
                parts = [(ctx.count(val.k, val.n, val.key), ink, "normal",
                          {"kind": "value", "key": val.key, "cell": val.cell, "unit": c.spec.unit, **meta_role})]  # fmt: skip
            else:
                parts = [(ctx.value(c.spec.unit, val.value, val.key), ink, "normal",
                          {"kind": "value", "key": val.key, "cell": val.cell, "unit": c.spec.unit, **meta_role})]  # fmt: skip
                if val.lo is not None:
                    parts.append((" " + ctx.interval(c.spec.unit, val.lo, val.hi, val.key), muted, "normal",
                                  {"kind": "value", "key": f"{val.key}.interval", "cell": val.cell,
                                   "unit": c.spec.unit}))  # fmt: skip
            c.texts[r.key] = parts


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
        each = avail / len(free)
        if each < 0.7:
            raise BuildError(f"{ctx.figure_id}: the table does not fit {lay.width} in ({each:.2f} in per panel)")
        for c in free:
            c.w = each
    elif avail < -1e-6:
        raise BuildError(f"{ctx.figure_id}: the table is {-avail:.2f} in wider than {lay.width} in")
    x, pid = label_w, 0
    for c in lay.cols:
        c.x = x
        x += c.w + th.pad
        if c.is_panel:
            c.pid, pid = pid, pid + 1


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
            vals = list(_cells(c.spec, r.key)) if c.is_panel else [(None, c.spec.cells.get(r.key))]
            for s, val in vals:
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
                    sp = spans.setdefault((r.key, val.cell), [gx0, gx1, st])
                    sp[0], sp[1] = min(sp[0], gx0), max(sp[1], gx1)
                if isinstance(val, Est) and val.note:
                    r.notes.append((c, val.note))
        if c.is_panel and c.spec.ticks:
            enc.add(("tick",))
        if c.is_panel and c.spec.band:
            enc.add(("band",))
    sz = ctx.sizes
    for r in lay.rows:
        n_lines = 0
        for (rk, cell), (x0, x1, st) in spans.items():
            if rk != r.key:
                continue
            full = ctx.words.descriptive if st.claim == "descriptive" else ctx.words.not_claimed.format(st.claim_reason)
            lines = ctx.wrap(full, x1 - x0, sz.tag)
            r.tags.append((x0, lines, cell, st.claim, full))
            n_lines = max(n_lines, len(lines))
        if not n_lines and (r.notes or lay.table.row_sub.get(r.key)):
            n_lines = 1
        r.sub = max(ctx.theme.sub_h, n_lines * line_h(sz.tag) + SUB_GAP) if n_lines else 0.0
        r.h = ctx.theme.row_h + r.sub
    return enc


def _vertical(lay: _Layout, ctx: Ctx) -> None:
    """Headers, the strip of role words above the first row, rows, and the bottom (ticks, unit titles, cues)."""
    sz, v = ctx.sizes, ctx.vocab
    lay.group_h = line_h(sz.header) + 0.06 if lay.groups else 0.0
    for c in lay.cols:
        if c.is_panel or c.is_text:
            c.header = ctx.wrap(c.spec.header, c.w, sz.header, "bold") if c.spec.header else []
            u = v.unit(c.spec.unit)
            c.title = ctx.wrap(u.title, c.w + ctx.theme.pad * 0.8, sz.axis)
            if c.is_panel and u.cue:
                c.cue = ctx.wrap(ctx.words.cue.format(u.quantity), c.w + ctx.theme.pad * 0.8, sz.cue)
    header_h = max((len(c.header) for c in lay.cols), default=0) * line_h(sz.header) + 0.08
    levels = max((_strip(c, lay, ctx) for c in lay.cols if c.is_panel), default=0)
    lay.head = TOP + lay.group_h + header_h
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


def _strip(c: _Col, lay: _Layout, ctx: Ctx) -> int:
    """Place a panel's role words (each over its first dot) and rule labels on levels; returns the level count."""
    sz = ctx.sizes
    first = {r.key: i for i, r in enumerate(lay.rows)}
    items, seen = [], set()
    for s in c.spec.series:
        if s.role == "control" or s.role in seen:
            continue
        xs = sorted((first[rk], val.value) for rk, val in s.cells.items() if isinstance(val, Est) and rk in first)
        if not xs:
            continue
        seen.add(s.role)
        word = ctx.vocab.role(s.role).word
        items.append((c.dx(xs[0][1]), ctx.measure(word, sz.role_word, "bold")[0],
                      (word, ctx.role_hex(s.role), "bold", sz.role_word, {"kind": "role_word", "role": s.role})))  # fmt: skip
    for rl in c.spec.rules:
        if rl.label:
            items.append((c.dx(rl.x), ctx.measure(rl.label, sz.tag)[0],
                          (rl.label, ctx.chrome("muted"), "normal", sz.tag, {"kind": "rule_label"})))  # fmt: skip
    placed: list[tuple[float, float, int]] = []
    for xc, w, payload in sorted(items, key=lambda it: it[0]):
        x0 = min(max(xc - w / 2, 0.0), max(c.w - w, 0.0))
        level = 0
        while any(lv == level and x0 < b + STRIP_GAP and a < x0 + w + STRIP_GAP for a, b, lv in placed):
            level += 1
        placed.append((x0, x0 + w, level))
        c.strip.append((x0, level, *payload))
    return max((lv for *_ab, lv in placed), default=-1) + 1


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
        sub = lay.table.row_sub.get(r.key)
        if sub:
            cv.text(0.08, r.sub_mid, sub, kind="row_sub", size=sz.tag, color=muted)

    for g in lay.groups:
        gx = min(c.x for c in lay.cols if c.group is g)
        cv.text(gx, TOP + lay.group_h / 2, g.header, kind="header", size=sz.header, weight="bold", color=ink)
    for c in lay.cols:
        for i, s in enumerate(c.header):
            cv.text(c.x, TOP + lay.group_h + (i + 0.5) * line_h(sz.header), s, kind="header", size=sz.header,
                    weight="bold", color=ink, full=c.spec.header)  # fmt: skip

    for c in lay.cols:
        if c.is_panel:
            _panel(cv, ctx, lay, c)
        elif c.is_text:
            for r in lay.rows:
                cv.rich(c.x, r.mid, c.texts[r.key], size=sz.value)

    for r in lay.rows:
        for x0, lines, cell, claim, full in r.tags:
            for i, s in enumerate(lines):
                cv.text(x0, r.sub_top + SUB_GAP / 2 + (i + 0.5) * line_h(sz.tag), s, kind="status_tag", size=sz.tag,
                        color=muted, cell=cell, claim=claim, full=full)  # fmt: skip
        for c, words in r.notes:
            cv.text(c.x + c.w, r.sub_mid, words, kind="note", size=sz.tag, color=muted, ha="right")

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
        for i, s in enumerate(c.title):
            cv.text(c.x + c.w / 2, y + (i + 0.5) * line_h(sz.axis), s, kind="axis_title", size=sz.axis, color=muted,
                    ha="center", panel=c.pid, unit=c.spec.unit, full=ctx.vocab.unit(c.spec.unit).title)  # fmt: skip
        full = ctx.words.cue.format(ctx.vocab.unit(c.spec.unit).quantity)
        for i, s in enumerate(c.cue):
            cv.text(c.x + c.w / 2, y + lay.title_h + (i + 0.5) * line_h(sz.cue), s, kind="cue", size=sz.cue,
                    color=muted, ha="center", panel=c.pid, axis="x", full=full)  # fmt: skip


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
    mk, pal, th = ctx.marks, ctx.palette, ctx.theme
    spec: DotColumn = c.spec
    total = lay.body_end - lay.head
    ax = cv.axes(c.x, lay.head, c.w, total)
    ax.set_xlim(*spec.xlim)
    ax.set_ylim(total, 0)  # y: inches down from the top of the strip
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color(ctx.chrome("faint"))
    ax.set_xticks(list(spec.xticks), labels=[""] * len(spec.xticks))
    ax.tick_params(axis="x", length=3, color=ctx.chrome("faint"), pad=0)
    tag(ax, kind="panel", pid=c.pid, unit=spec.unit, cue=ctx.vocab.unit(spec.unit).cue)

    def y_of(r: _Row) -> float:
        return r.mid - lay.head

    # vertical lines stop at a row's second line where a tag spans this panel
    cuts = [(r.sub_top - lay.head, r.top + r.h - lay.head) for r in lay.rows if _second_line_in(r, c, ctx)]
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
        tag(rect, kind="band")
    for rl in spec.rules:
        for a, b in _segments(b0, b1, cuts):
            tag(ax.plot([rl.x, rl.x], [a, b], color=ctx.chrome("rule"), lw=mk.rule_lw, ls=(0, mk.rule_dash), zorder=1),
                kind="rule")  # fmt: skip

    for r in lay.rows:
        y = y_of(r)
        ests = {s.role: val for s, val in _cells(spec, r.key) if isinstance(val, Est)}
        if spec.connect and all(k in ests for k in spec.connect):
            a, b = ests[spec.connect[0]].value, ests[spec.connect[1]].value
            tag(ax.plot([a, b], [y, y], color=ctx.chrome("connector"), lw=mk.connector_lw, solid_capstyle="round",
                        zorder=2), kind="connector")  # fmt: skip
        extents = []
        if r.key in spec.ticks:
            tx, half = spec.ticks[r.key], mk.tick_half * th.row_h
            tag(ax.plot([tx, tx], [y - half, y + half], color=pal.control, lw=mk.tick_lw, zorder=3), kind="tick",
                role="control")  # fmt: skip
            extents.append(tx)
        labels = []
        for s, val in _cells(spec, r.key):
            if isinstance(val, Missing):
                cv.text(c.x + 0.04, r.mid, val.words, kind="missing", size=ctx.sizes.tag, color=ctx.chrome("muted"))
                continue
            extents += _dot(ax, ctx, s, val, y)
            if val.label:
                labels.append((val, s.role))
        for val, role in labels:
            col = ctx.chrome("muted") if role == "control" else ctx.role_hex(role)
            _value_label(cv, ctx, c, r.mid, ctx.value(spec.unit, val.value, val.key), col, extents, vlines, val, role)

    for x0, level, word, colr, weight, size, meta in c.strip:
        cv.text(c.x + x0, lay.head + lay.strip_h - 0.05 - (level + 0.5) * line_h(ctx.sizes.role_word), word,
                size=size, color=colr, weight=weight, **meta)  # fmt: skip


def _second_line_in(r: _Row, c: _Col, ctx: Ctx) -> bool:
    """Whether a row's second line holds words inside this panel's span (lines stop there)."""
    spans = [(x0, x0 + max(ctx.measure(s, ctx.sizes.tag)[0] for s in lines)) for x0, lines, *_rest in r.tags]
    spans += [(n.x + n.w - ctx.measure(words, ctx.sizes.tag)[0], n.x + n.w) for n, words in r.notes]
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


def _value_label(cv: Canvas, ctx: Ctx, c: _Col, y: float, s: str, col: str, extents, vlines, val: Est, role) -> None:
    """A value beside its row's marks: right of them if it fits clear of every vertical line, else left."""
    per = c.per_inch()
    lo, hi = c.spec.xlim
    wd = ctx.measure(s, ctx.sizes.value)[0] * per
    gap = (ctx.marks.dot_size / 2 + 5) * PT * per
    clear = 3 * PT * per
    room = ctx.theme.pad * 0.7 * per
    meta = {"kind": "value", "key": val.key, "cell": val.cell, "unit": c.spec.unit, "role": role}

    def blocked(a, b):
        return [xv for xv in vlines if a - clear < xv < b + clear]

    x = max(extents) + gap
    while blocked(x, x + wd) and x + wd <= hi + room:
        x = max(blocked(x, x + wd)) + clear
    if x + wd <= hi + room:
        cv.text(c.x + c.dx(x), y, s, size=ctx.sizes.value, color=col, **meta)
        return
    x = min(extents) - gap
    while blocked(x - wd, x) and x - wd >= lo - room:
        x = min(blocked(x - wd, x)) - clear
    cv.text(c.x + c.dx(x), y, s, size=ctx.sizes.value, color=col, ha="right", **meta)
