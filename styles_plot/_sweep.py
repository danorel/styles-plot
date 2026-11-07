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
        if ln.role == "control" and ln.control not in ctx.vocab.controls:
            raise BuildError(f"{ctx.figure_id}: a control line needs control=<one of [controls].names>")
        lines[ln.row].append(ln)
    xs = np.concatenate([np.asarray(ln.x, float) for ln in s.lines])
    ys = np.concatenate([np.asarray(v, float) for ln in s.lines for v in (ln.y, *(ln.band or ()))]
                        + [np.asarray([v for v in (p.value, p.lo, p.hi) if v is not None], float) for p in s.points])
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
        if (p.lo is None) != (p.hi is None) or (p.lo is not None and p.value is None):
            raise BuildError(f"{ctx.figure_id}: a point's own interval needs value, lo and hi")
        if p.value is None:
            idx = [i for i, xv in enumerate(ln.x) if abs(xv - p.x) < 1e-9]
            if not idx:
                raise BuildError(f"{ctx.figure_id}: point x={p.x} is not one of the line's x values; give value= for "
                                 "a point measured on its own (GRAMMAR.md, C)")  # fmt: skip
            yv = float(ln.y[idx[0]])
        else:
            yv = float(p.value)
        st = ctx.status(p.cell)
        if st.hollow:
            enc.add(("post_hoc",))
        if p.lo is not None:
            enc.add(("whisker", p.interval))
        points.append((p, yv, st))
    for ln in s.lines:
        if ln.band is not None:
            enc.add(("shading", ln.interval))
        if ln.median:
            enc.add(("median",))
        if ln.role == "control":
            enc.add(("control", ln.control))
    for _x0, _x1, name in s.windows:
        enc.add(("band", name))
    hlabels = [(rl, rule_label(ctx, rl) if rl.label else "") for rl in s.hrules]
    for rl, _t in hlabels:
        if yu.scale == "log" and rl.x <= 0:
            raise BuildError(f"{ctx.figure_id}: a horizontal rule at {rl.x} on a log axis")

    ytw = y_tick_width(ctx, yt)
    px0 = label_w + ytw
    right = max([RIGHT, *(ctx.measure(t, sz.tag)[0] + 0.15 for _rl, t in hlabels if t)])
    pw = width - px0 - right
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
        word = None if ln.role == "control" else (ln.word or ctx.vocab.role(ln.role).word)
        if word is None or word in seen:
            continue
        seen.add(word)
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
            for x0w, x1w, name in s.windows:
                win = ax.axvspan(x0w, x1w, facecolor=ctx.chrome("band"), edgecolor="none", lw=0, zorder=0.5)
                tag(win, kind="band", band=name)
            for tv in xt:
                tag(ax.plot([tv, tv], ylim, color=ctx.chrome("grid"), lw=0.8, zorder=0), kind="grid")
            for tv in yt:
                tag(ax.plot(xlim, [tv, tv], color=ctx.chrome("grid"), lw=0.8, zorder=0), kind="grid")
                yy = top + (1 - _frac(tv, ylim, yu.scale)) * panel_h
                cv.text(px0 - 0.06, yy, ctx.tick(tv), kind="tick_label", size=sz.tick, color=muted, ha="right")
            for rl in s.rules:
                tag(ax.plot([rl.x, rl.x], ylim, color=ctx.chrome("rule"), lw=ctx.marks.rule_lw,
                            ls=(0, ctx.marks.rule_dash), zorder=1), kind="rule")  # fmt: skip
            for rl, text in hlabels:
                tag(ax.plot(xlim, [rl.x, rl.x], color=ctx.chrome("rule"), lw=ctx.marks.rule_lw,
                            ls=(0, ctx.marks.rule_dash), zorder=1), kind="rule")  # fmt: skip
                if text and row == s.rows[0]:  # labelled once, in the margin right of the first panel
                    yy = top + (1 - _frac(rl.x, ylim, yu.scale)) * panel_h
                    cv.text(px0 + pw + 0.08, yy, text, kind="rule_label", size=sz.tag, color=muted,
                            **({"key": rl.key} if rl.key else {}))  # fmt: skip
            for ln in lines[row]:
                _line(ax, ctx, ln)
            def to_in(xs, ys, top=top):
                xs, ys = np.asarray(xs, float), np.asarray(ys, float)
                fx = (xs - xlim[0]) / (xlim[1] - xlim[0]) * pw + px0
                fy = top + (1 - np.array([_frac(v, ylim, yu.scale) for v in ys])) * panel_h
                return fx, fy

            obstacles = [to_in(ln.x, ln.y) for ln in lines[row]]
            obstacles += [to_in([rl.x, rl.x], ylim) for rl in s.rules]
            obstacles += [to_in(xlim, [rl.x, rl.x]) for rl, _t in hlabels]
            obstacles.append(([px0, px0 + pw], [top + panel_h, top + panel_h]))  # the panel's bottom spine
            for p, yv, st in points:
                if p.row == row:
                    _point(cv, ax, ctx, p, yv, st, s.y_unit, to_in, obstacles, (px0, top, pw, panel_h))
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
    meta = {"role": ln.role, "cell": ln.cell, "timing": st.timing, "claim": st.claim, "median": ln.median,
            **({"control": ln.control} if ln.role == "control" else {})}  # fmt: skip
    if ln.band is not None:
        lo, hi = ln.band
        poly = ax.fill_between(ln.x, lo, hi, color=col, alpha=ctx.marks.shading_alpha, lw=0, zorder=1)
        tag(poly, kind="shading", interval=ln.interval, **meta)
    tag(ax.plot(ln.x, ln.y, color=col, lw=ctx.marks.line_lw, solid_capstyle="round", zorder=2), kind="line", **meta)


def _point(cv, ax, ctx: Ctx, p, yv, st, unit, to_in, obstacles, panel) -> None:
    mk, bg = ctx.marks, ctx.palette.chrome["background"]
    col = ctx.role_hex(p.role)
    if p.lo is not None:  # the point's own interval, vertical
        tag(ax.plot([p.x, p.x], [p.lo, p.hi], color=col, lw=mk.whisker_lw, solid_capstyle="butt", zorder=3),
            kind="whisker", interval=p.interval, role=p.role, cell=p.cell)  # fmt: skip
        obstacles = [*obstacles, to_in([p.x, p.x], [p.lo, p.hi])]
    tag(ax.plot([p.x], [yv], marker=mk.marker, ls="none", ms=mk.dot_size, color=col, mfc=bg if st.hollow else col,
                mec=col, mew=mk.hollow_edge if st.hollow else 0, zorder=4),
        kind="dot", role=p.role, cell=p.cell, timing=st.timing, claim=st.claim, hollow=st.hollow)  # fmt: skip
    if not p.label:
        return
    if not p.key:
        raise BuildError(f"{ctx.figure_id}: a printed point needs key=")
    s = ctx.value(unit, yv, p.key)
    w, h = ctx.measure(s, ctx.sizes.value)
    (cx,), (cy,) = to_in([p.x], [yv])
    g = (mk.dot_size / 2 + 4) * PT
    # nearest first: the four diagonals and straight above / below, at one and two steps. No farther: a value a
    # layer away from its dot reads as another dot's, so with no clear spot near it the layout check fails instead
    candidates = []
    for k in (1, 2):
        d = k * g
        candidates += [(cx + d, cy - d - h), (cx - d - w, cy - d - h), (cx + d, cy + d), (cx - d - w, cy + d),
                       (cx - w / 2, cy - d - g - h), (cx - w / 2, cy + d + g)]  # fmt: skip
    pad = (mk.line_lw / 2 + 2.5) * PT  # the layout check's clearance (half the line, 1.5 pt) and a margin
    best = min(candidates, key=lambda c: _label_cost(c, w, h, obstacles, panel, pad))  # min keeps the nearest tie
    cv.text(best[0], best[1] + h / 2, s, kind="value", size=ctx.sizes.value, color=col, key=p.key, cell=p.cell,
            unit=unit, role=p.role)  # fmt: skip


def _label_cost(pos, w, h, obstacles, panel, pad) -> tuple:
    """(leaves the panel, touches a line): a label's spot is best when inside its panel and clear of every line."""
    x0, y0 = pos
    px0, top, pw, ph = panel
    outside = x0 < px0 or x0 + w > px0 + pw or y0 < top or y0 + h > top + ph
    hits = 0
    for xs, ys in obstacles:
        for i in range(len(xs) - 1):  # sample each segment densely: a point inside the padded box is a crossing
            t = np.linspace(0, 1, 24)
            sx, sy = xs[i] + t * (xs[i + 1] - xs[i]), ys[i] + t * (ys[i + 1] - ys[i])
            hits += int(np.any((sx > x0 - pad) & (sx < x0 + w + pad) & (sy > y0 - pad) & (sy < y0 + h + pad)))
    return (outside, hits)
