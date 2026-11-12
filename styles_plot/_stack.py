"""The 100% stack: one horizontal bar per entity, at most four segments, each named in words above the first row in
its colour; a segment's share is printed inside it when it fits. A post hoc segment is hollow (outlined)."""

from __future__ import annotations

from matplotlib.patches import Rectangle

from styles_plot._grid import STRIP_GAP, claim_tags, draw_tags, draw_x_bottom, place_on_levels, x_bottom_height
from styles_plot._model import Est, Stack
from styles_plot._render import BuildError, Canvas, Ctx, Plan
from styles_plot._table import text_parts
from styles_plot._tags import tag
from styles_plot._text import line_h

RIGHT = 0.3  # room for the last tick label


def plan(s: Stack, ctx: Ctx, width: float, label_w: float) -> Plan:
    ctx.check_rows(s.kind, s.rows)
    unit = ctx.unit(s.unit)
    sz, th = ctx.sizes, ctx.theme
    cap = ctx.marks.max_segments
    if not 1 <= len(s.segments) <= cap:
        raise BuildError(f"{ctx.figure_id}: a stack has 1 to {cap} segments ([marks].max_segments), got "
                         f"{len(s.segments)}")  # fmt: skip
    names = [seg.name for seg in s.segments]
    if len(set(names)) != len(names):
        raise BuildError(f"{ctx.figure_id}: two segments share a name; segments of one role are told apart by words")
    for seg in s.segments:
        ctx.role_hex(seg.role)
    for r in s.rows:
        vals = [seg.shares.get(r) for seg in s.segments]
        if any(not isinstance(v, Est) for v in vals):
            raise BuildError(f"{ctx.figure_id}: row {r!r} lacks a share in some segment")
        total = sum(v.value for v in vals)
        if abs(total - 1) > 1e-3:  # shares stored to a few decimals sum to 0.9999 or 1.0001
            raise BuildError(f"{ctx.figure_id}: row {r!r} sums to {total:.6f}, not 1")

    # a segment that is zero in every row draws nothing, so it is neither drawn nor named (a text column can carry it)
    shown = [seg for seg in s.segments if any(v.value > 0 for v in seg.shares.values())]

    # text columns beside the bars: their numbers formatted once, their widths measured
    cols = []
    for tc in s.columns:
        ctx.unit(tc.unit)
        parts = {r: text_parts(ctx, tc, r) for r in s.rows}
        w = max([sum(ctx.measure(t, sz.value, wt)[0] for t, _c, wt, _m in ps) for ps in parts.values()]
                + [max((ctx.measure(x, sz.header, "bold")[0] for x in tc.header.split()), default=0.0), 0.5]) + 0.05
        cols.append((tc, parts, w))
    cols_w = sum(w + th.pad for _tc, _p, w in cols)
    pw = width - label_w - RIGHT - cols_w
    if pw < 1.0:
        raise BuildError(f"{ctx.figure_id}: the stack's text columns leave {pw:.2f} in for the bars")
    enc: set = set()
    for seg in shown:
        if any(ctx.status(v.cell).hollow for v in seg.shares.values()):
            enc.add(("post_hoc",))
    # segment names over the first row's segments
    first, left, items = s.rows[0], 0.0, []
    muted = ctx.chrome("muted")
    for seg in shown:
        v = seg.shares[first].value
        colr, meta = ((muted, {"kind": "segment_name"}) if seg.role == "other"
                      else (ctx.role_hex(seg.role), {"kind": "role_word", "role": seg.role}))  # fmt: skip
        wd = max(ctx.measure(seg.name, sz.role_word, "bold")[0], ctx.measure(seg.note, sz.tag)[0] if seg.note else 0.0)
        items.append((left * pw, (left + v) * pw, wd, (seg.name, colr, "bold", sz.role_word, meta, seg.note)))  # fmt: skip
        left += v
    strip, levels = _place_names(items, pw)
    level_h = line_h(sz.role_word) + (line_h(sz.tag) if any(seg.note for seg in shown) else 0.0)  # a name, its note
    head = 0.08
    header = ctx.wrap(s.header, pw, sz.header, "bold") if s.header else []
    head += len(header) * line_h(sz.header)
    head_lines = max((len(ctx.wrap(tc.header, w, sz.header, "bold")) for tc, _p, w in cols), default=0)
    strip_h = max(levels * level_h, head_lines * line_h(sz.header)) + 0.08
    body_top = head + strip_h
    row_tags = {r: claim_tags(ctx, [seg.shares[r].cell for seg in shown]) for r in s.rows}
    tops, y = {}, 0.0
    for r in s.rows:
        tops[r] = y
        y += th.row_h + len(row_tags[r]) * line_h(sz.tag)
    body_h = y
    bottom_h, title, cue = x_bottom_height(ctx, unit, pw)
    height = body_top + body_h + bottom_h

    def draw(cv: Canvas) -> None:
        bg, ink = ctx.palette.chrome["background"], ctx.chrome("text")
        x0 = label_w
        for i, t in enumerate(header):
            cv.text(x0, 0.08 + (i + 0.5) * line_h(sz.header), t, kind="header", size=sz.header, weight="bold",
                    full=s.header)  # fmt: skip
        for xl, level, (word, colr, weight, size, meta, note) in strip:
            yw = body_top - 0.04 - (level + 1) * level_h + line_h(sz.role_word) / 2
            cv.text(x0 + xl, yw, word, size=size, color=colr, weight=weight, **meta)
            if note:
                cv.text(x0 + xl, yw + (line_h(sz.role_word) + line_h(sz.tag)) / 2, note, kind="segment_note",
                        size=sz.tag, color=ctx.chrome("muted"))  # fmt: skip
        ax = cv.axes(x0, body_top, pw, body_h)
        ax.set_xlim(0, 1)
        ax.set_ylim(body_h, 0)
        ax.spines["bottom"].set_visible(True)
        ax.spines["bottom"].set_color(ctx.chrome("faint"))
        bar_h = ctx.marks.bar_height * th.row_h
        for r in s.rows:
            yc = tops[r] + th.row_h / 2
            draw_tags(cv, ctx, x0, body_top + tops[r] + th.row_h, row_tags[r])
            cv.text(0.08, body_top + yc, ctx.entity_name(s.kind, r), kind="row_label", size=sz.label, weight="bold")
            left = 0.0
            for seg in shown:
                v = seg.shares[r]
                col = ctx.role_hex(seg.role)
                st = ctx.status(v.cell)
                rect = Rectangle((left, yc - bar_h / 2), v.value, bar_h, facecolor=bg if st.hollow else col,
                                 edgecolor=col if st.hollow else bg, lw=1.6 if st.hollow else 0.8, zorder=2)  # fmt: skip
                ax.add_patch(rect)
                tag(rect, kind="segment", role=seg.role, cell=v.cell, timing=st.timing, claim=st.claim,
                    hollow=st.hollow)  # fmt: skip
                if v.label:
                    text = ctx.value(s.unit, v.value, v.key)
                    if ctx.measure(text, sz.value)[0] + 0.08 <= v.value * pw:
                        on_dark = seg.role != "other" and not st.hollow
                        colour = bg if on_dark else (col if st.hollow and seg.role != "other" else ink)
                        meta = {"role": seg.role} if st.hollow and seg.role != "other" else {}
                        cv.text(x0 + (left + v.value / 2) * pw, body_top + yc, text, kind="value", size=sz.value,
                                color=colour, ha="center", key=v.key, cell=v.cell, unit=s.unit, **meta)  # fmt: skip
                left += v.value
        draw_x_bottom(cv, ctx, x0, pw, body_top + body_h, (0, 1), [0, 0.5, 1], unit, title, cue, pid=None)
        cx = x0 + pw + th.pad
        for tc, parts, w in cols:  # header just above the first row, numbers on each row, unit title under
            for i, t in enumerate(ctx.wrap(tc.header, w, sz.header, "bold")[::-1]):
                cv.text(cx, body_top - 0.06 - (i + 0.5) * line_h(sz.header), t, kind="header", size=sz.header,
                        weight="bold", full=tc.header)  # fmt: skip
            for r in s.rows:
                cv.rich(cx, body_top + tops[r] + th.row_h / 2, parts[r], size=sz.value)
            if tc.unit_title:
                u = ctx.vocab.unit(tc.unit)
                for i, t in enumerate(ctx.wrap(u.title, w + th.pad * 0.8, sz.axis)):
                    cv.text(cx + w / 2, body_top + body_h + 0.06 + line_h(sz.tick) + (i + 0.5) * line_h(sz.axis), t,
                            kind="axis_title", size=sz.axis, color=ctx.chrome("muted"), ha="center", unit=u.name,
                            full=u.title)  # fmt: skip
            cx += w + th.pad

    return Plan(height, draw, enc)


def _place_names(items, pw: float) -> tuple[list, int]:
    """Segment names (with their notes) above the first row. Each may sit at its segment's centre, start or end (inside
    the bars' width): one level if some choice of these fits (the names nearest their centres); else one row in the
    segments' order when the names fit side by side; else the earlier rule (each centred, on the lowest free level). items: (segment start, segment end, width,
    payload) in inches."""
    import itertools

    items = sorted(items, key=lambda it: (it[0] + it[1]) / 2)
    spots_of = [[min(max(x, 0.0), max(pw - w, 0.0)) for x in ((a + b) / 2 - w / 2, a, b - w)] for a, b, w, _p in items]
    if len(items) <= 8:  # one level if any choice of spots fits, the names nearest their segments' centres
        best = None
        for combo in itertools.product(*spots_of):
            spans = sorted((x, x + it[2]) for x, it in zip(combo, items, strict=True))
            if all(q + STRIP_GAP <= p for (_p0, q), (p, _q1) in zip(spans, spans[1:], strict=False)):
                cost = sum(abs(x - sp[0]) for x, sp in zip(combo, spots_of, strict=True))
                if best is None or cost < best[0]:
                    best = (cost, combo)
        if best is not None:
            return [(x, 0, it[3]) for x, it in zip(best[1], items, strict=True)], (1 if items else 0)
    # else, if the names fit side by side, one row in the segments' order: each centred over its segment when that is
    # wide enough for it, else at its start, pushed right of the name before and pulled back from the right edge
    if items and sum(w for _a, _b, w, _p in items) + STRIP_GAP * (len(items) - 1) <= pw:
        xs: list[float] = []
        for a, b, w, _p in items:  # a name over a segment wide enough for it stays centred there, others at the start
            want = min((a + b) / 2 - w / 2 if b - a >= w else a, pw - w)
            xs.append(max(want, xs[-1] + items[len(xs) - 1][2] + STRIP_GAP) if xs else want)
        for i in range(len(items) - 1, -1, -1):
            limit = pw if i == len(items) - 1 else xs[i + 1] - STRIP_GAP
            xs[i] = max(0.0, min(xs[i], limit - items[i][2]))
        return [(x, 0, it[3]) for x, it in zip(xs, items, strict=True)], 1
    # else the earlier rule, unchanged: each name centred over its segment, on the lowest free level
    return place_on_levels([((a + b) / 2, w, payload) for a, b, w, payload in items], pw)


