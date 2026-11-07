"""The sweep: a quantity over depth (layers), one panel per entity, stacked with a shared x axis.

Lines are drawn only when x is depth. The value axis is vertical: its quantity is named above the panels (a header,
the unit's title, and the cue "↑ more <quantity>"); a log scale says so in the unit's title. An interval band on a
line is the line's colour at the theme's shading alpha, named in the key ("shading: <interval>"). A point on a line
is a dot whose fill comes from the registry. A line is never hollow: a whole line's status is a grey tag above its
panel ("post hoc", "descriptive", "not claimed: …"), like a dot table's tags (GRAMMAR.md, C).
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from styles_plot._grid import (
    claim_tags,
    draw_tags,
    draw_x_bottom,
    padded,
    place_in_line,
    place_on_levels,
    ticks,
    x_bottom_height,
    y_tick_width,
)
from styles_plot._model import Sweep
from styles_plot._render import BuildError, Canvas, Ctx, Plan
from styles_plot._table import rule_label
from styles_plot._tags import tag
from styles_plot._text import PT, line_h

RIGHT = 0.3  # room for the last tick label


def plan(s: Sweep, ctx: Ctx, width: float, label_w: float) -> Plan:
    ctx.check_rows(s.kind, s.rows)
    xu, yu = ctx.unit(s.x_unit), ctx.unit(s.y_unit)
    sz, th = ctx.sizes, ctx.theme
    lines = defaultdict(list)
    for ln in s.lines:
        if ln.row not in s.rows:
            raise BuildError(f"{ctx.figure_id}: line for {ln.row!r}, which is not a row")
        if len(ln.x) != len(ln.y) or len(ln.x) < 2:
            raise BuildError(f"{ctx.figure_id}: a line needs matching x and y with at least two points")
        ctx.role_hex(ln.role)
        lines[ln.row].append(ln)
    xs = np.concatenate([np.asarray(ln.x, float) for ln in s.lines])
    ys = np.concatenate([np.asarray(v, float) for ln in s.lines for v in (ln.y, *(ln.band or ()))])
    xlim = s.xlim or (float(xs.min()), float(xs.max()))
    try:
        ylim = s.ylim or padded(float(ys.min()), float(ys.max()), yu.scale)
    except ValueError as e:
        raise BuildError(f"{ctx.figure_id}: {e}") from None
    xt = list(s.xticks) if s.xticks is not None else ticks(xlim)
    yt = list(s.yticks) if s.yticks is not None else ticks(ylim, yu.scale, 3)

    enc: set = set()
    points = []
    for p in s.points:
        ln = next((ln for ln in lines[p.row] if ln.role == p.role), None)
        if ln is None:
            raise BuildError(f"{ctx.figure_id}: point at x={p.x} on {p.row!r} has no {p.role!r} line (a point marks a "
                             "cell on a line; a whole line's status is a panel tag: GRAMMAR.md, C)")  # fmt: skip
        idx = [i for i, xv in enumerate(ln.x) if abs(xv - p.x) < 1e-9]
        if not idx:
            raise BuildError(f"{ctx.figure_id}: point x={p.x} is not one of the line's x values (GRAMMAR.md, C)")
        st = ctx.status(p.cell)
        if st.hollow:
            enc.add(("post_hoc",))
        points.append((p, float(ln.y[idx[0]]), st))
    for ln in s.lines:
        if ln.band is not None:
            enc.add(("shading", ln.interval))

    ytw = y_tick_width(ctx, yt)
    px0 = label_w + ytw
    pw = width - px0 - RIGHT
    panel_h = s.panel_h or th.row_h * 2.4
    header = s.header or yu.quantity
    head_lines = ctx.wrap(header, pw, sz.header, "bold") if header else []
    title_parts = [(yu.title, "axis_title")] + ([(ctx.vocab.cue(yu.name, "y"), "cue")] if yu.cue else [])
    head_h = 0.08 + len(head_lines) * line_h(sz.header) + line_h(sz.axis) * (1 + _cue_wraps(ctx, title_parts, pw)) + 0.04

    # strip: role words at each line's end in the first panel, rule labels at their x
    def dx(v):
        return (v - xlim[0]) / (xlim[1] - xlim[0]) * pw

    items, seen = [], set()
    for ln in lines[s.rows[0]]:
        if ln.role in seen or ln.role == "control":
            continue
        seen.add(ln.role)
        word = ctx.vocab.role(ln.role).word
        items.append((dx(ln.x[-1]), ctx.measure(word, sz.role_word, "bold")[0],
                      (word, ctx.role_hex(ln.role), "bold", sz.role_word, {"kind": "role_word", "role": ln.role})))  # fmt: skip
    for rl in s.rules:
        if rl.label:
            text = rule_label(ctx, rl)
            items.append((dx(rl.x), ctx.measure(text, sz.tag)[0],
                          (text, ctx.chrome("muted"), "normal", sz.tag, {"kind": "rule_label"})))  # fmt: skip
    role_items = [it for it in items if it[2][4]["kind"] == "role_word"]
    line = place_in_line(role_items, pw)
    occupied = [(x0, x0 + ctx.measure(p[0], sz.role_word, "bold")[0], 0) for x0, p in line]
    placed, levels = place_on_levels([it for it in items if it not in role_items], pw, occupied)
    strip = [(x0, 0, p) for x0, p in line] + placed
    levels = max(levels, 1 if line else 0)
    strip_h = levels * line_h(sz.role_word) + 0.08
    bottom_h, xtitle, xcue = x_bottom_height(ctx, xu, pw)
    gap = 0.12
    line_cells = frozenset(ln.cell for ln in s.lines if ln.cell)
    row_tags = {r: claim_tags(ctx, [ln.cell for ln in lines[r]] + [p.cell for p, _y, _st in points if p.row == r],
                              line_cells) for r in s.rows}  # fmt: skip
    tag_h = {r: len(t) * line_h(sz.tag) + (0.04 if t else 0) for r, t in row_tags.items()}
    body_top = head_h + strip_h
    tops, y = {}, body_top
    for r in s.rows:
        tops[r] = y + tag_h[r]
        y = tops[r] + panel_h + gap
    height = y - gap + bottom_h

    def draw(cv: Canvas) -> None:
        muted = ctx.chrome("muted")
        y = 0.08
        for i, t in enumerate(head_lines):
            cv.text(px0, y + (i + 0.5) * line_h(sz.header), t, kind="header", size=sz.header, weight="bold",
                    full=header)  # fmt: skip
        y += len(head_lines) * line_h(sz.header)
        _title_line(cv, ctx, px0, y, pw, title_parts, yu)
        for x0, level, (word, colr, weight, size, meta) in strip:
            cv.text(px0 + x0, body_top - 0.04 - (level + 0.5) * line_h(sz.role_word), word, size=size, color=colr,
                    weight=weight, **meta)  # fmt: skip
        for row in s.rows:
            top = tops[row]
            draw_tags(cv, ctx, px0, top - tag_h[row], row_tags[row])
            cv.text(0.08, top + panel_h / 2, ctx.entity_name(s.kind, row), kind="row_label", size=sz.label,
                    weight="bold")  # fmt: skip
            ax = cv.axes(px0, top, pw, panel_h)
            ax.set_xlim(*xlim)
            if yu.scale == "log":
                ax.set_yscale("log")
                ax.minorticks_off()
            ax.set_ylim(*ylim)
            ax.set_yticks([])
            ax.set_xticks([])
            ax.spines["bottom"].set_visible(True)
            ax.spines["bottom"].set_color(ctx.chrome("faint"))
            for tv in xt:
                tag(ax.plot([tv, tv], ylim, color=ctx.chrome("grid"), lw=0.8, zorder=0), kind="grid")
            for tv in yt:
                tag(ax.plot(xlim, [tv, tv], color=ctx.chrome("grid"), lw=0.8, zorder=0), kind="grid")
                yy = top + (1 - _frac(tv, ylim, yu.scale)) * panel_h
                cv.text(px0 - 0.06, yy, ctx.tick(tv), kind="tick_label", size=sz.tick, color=muted, ha="right")
            for rl in s.rules:
                tag(ax.plot([rl.x, rl.x], ylim, color=ctx.chrome("rule"), lw=ctx.marks.rule_lw,
                            ls=(0, ctx.marks.rule_dash), zorder=1), kind="rule")  # fmt: skip
            for ln in lines[row]:
                _line(ax, ctx, ln)
            for p, yv, st in points:
                if p.row == row:
                    _point(cv, ax, ctx, p, yv, st, s.y_unit, px0, pw, top, panel_h, xlim, ylim, yu.scale)
        draw_x_bottom(cv, ctx, px0, pw, tops[s.rows[-1]] + panel_h, xlim, xt, xu, xtitle, xcue, pid=None)

    return Plan(height, enc, draw)


def _cue_wraps(ctx: Ctx, parts, width: float) -> int:
    total = sum(ctx.measure(t, ctx.sizes.axis)[0] for t, _k in parts) + 0.3 * (len(parts) - 1)
    return 1 if total > width and len(parts) > 1 else 0


def _title_line(cv: Canvas, ctx: Ctx, x: float, y: float, width: float, parts, unit) -> None:
    """The value axis's title, then its cue on the same line when it fits, else on the next."""
    sz, muted = ctx.sizes, ctx.chrome("muted")
    lh = line_h(sz.axis)
    title, cue = parts[0][0], parts[1][0] if len(parts) > 1 else None
    cv.text(x, y + lh / 2, title, kind="axis_title", size=sz.axis, color=muted, unit=unit.name)
    if cue:
        tw = ctx.measure(title, sz.axis)[0]
        if tw + 0.3 + ctx.measure(cue, sz.cue)[0] <= width:
            cv.text(x + tw + 0.3, y + lh / 2, cue, kind="cue", size=sz.cue, color=muted, axis="y")
        else:
            cv.text(x, y + 1.5 * lh, cue, kind="cue", size=sz.cue, color=muted, axis="y")


def _frac(v: float, lim, scale: str) -> float:
    if scale == "log":
        return (np.log10(v) - np.log10(lim[0])) / (np.log10(lim[1]) - np.log10(lim[0]))
    return (v - lim[0]) / (lim[1] - lim[0])


def _line(ax, ctx: Ctx, ln) -> None:
    col = ctx.role_hex(ln.role)
    st = ctx.status(ln.cell)
    meta = {"role": ln.role, "cell": ln.cell, "timing": st.timing, "claim": st.claim}
    if ln.band is not None:
        lo, hi = ln.band
        poly = ax.fill_between(ln.x, lo, hi, color=col, alpha=ctx.marks.shading_alpha, lw=0, zorder=1)
        tag(poly, kind="shading", interval=ln.interval, **meta)
    tag(ax.plot(ln.x, ln.y, color=col, lw=ctx.marks.line_lw, solid_capstyle="round", zorder=2), kind="line", **meta)


def _point(cv, ax, ctx: Ctx, p, yv, st, unit, px0, pw, top, panel_h, xlim, ylim, scale) -> None:
    mk, bg = ctx.marks, ctx.palette.chrome["background"]
    col = ctx.role_hex(p.role)
    tag(ax.plot([p.x], [yv], marker=mk.marker, ls="none", ms=mk.dot_size, color=col, mfc=bg if st.hollow else col,
                mec=col, mew=mk.hollow_edge if st.hollow else 0, zorder=4),
        kind="dot", role=p.role, cell=p.cell, timing=st.timing, claim=st.claim, hollow=st.hollow)  # fmt: skip
    if p.label:
        if not p.key:
            raise BuildError(f"{ctx.figure_id}: a printed point needs key=")
        s = ctx.value(unit, yv, p.key)
        x = px0 + (p.x - xlim[0]) / (xlim[1] - xlim[0]) * pw + (mk.dot_size / 2 + 5) * PT
        y = top + (1 - _frac(yv, ylim, scale)) * panel_h - (mk.dot_size / 2 + 5) * PT - line_h(ctx.sizes.value) / 2
        cv.text(x, y, s, kind="value", size=ctx.sizes.value, color=col, key=p.key, cell=p.cell, unit=unit, role=p.role)
