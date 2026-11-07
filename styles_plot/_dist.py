"""Distributions: small multiples in entity order (and conditions as columns), a shared x axis.

style="hist": histogram bins in the role colour (bars are allowed here and in 100% stacks only), white edges, no
value labels; the count axis is named above the panels. style="strip": every value a small dot, jittered vertically.
median=True adds a role-colour line at each panel's median, named in the key.
"""

from __future__ import annotations

import numpy as np

from styles_plot._grid import claim_tags, draw_tags, draw_x_bottom, padded, ticks, x_bottom_height, y_tick_width
from styles_plot._model import Distribution
from styles_plot._render import BuildError, Canvas, Ctx, Plan
from styles_plot._tags import tag
from styles_plot._text import line_h

RIGHT = 0.3  # room for the last tick label
STRIP_SIZE = 5.0  # marker size of a strip's dots (pt)


def _key(d: Distribution, row: str, col: str | None):
    return (row, col) if d.columns else row


def plan(d: Distribution, ctx: Ctx, width: float, label_w: float) -> Plan:
    ctx.check_rows(d.kind, d.rows)
    if d.style not in ("hist", "strip"):
        raise BuildError(f"{ctx.figure_id}: style must be 'hist' or 'strip' (no violins)")
    xu = ctx.unit(d.unit)
    cu = ctx.unit(d.count_unit) if d.count_unit else None
    if d.style == "hist" and cu is None:
        raise BuildError(f"{ctx.figure_id}: a histogram needs count_unit= (the unit that names its counts)")
    hexr = ctx.role_hex(d.role)
    if d.role == "control" and d.control not in ctx.vocab.controls:
        raise BuildError(f"{ctx.figure_id}: a control distribution needs control=<one of [controls].names>")
    sz, th = ctx.sizes, ctx.theme
    cols = list(d.columns) or [None]
    data = {}
    for r in d.rows:
        for c in cols:
            k = _key(d, r, c)
            if k not in d.data:
                raise BuildError(f"{ctx.figure_id}: no data for {k!r}")
            data[k] = np.asarray(d.data[k], float)
    allv = np.concatenate(list(data.values()))
    xlim = d.xlim or padded(float(allv.min()), float(allv.max()))
    xt = list(d.xticks) if d.xticks is not None else ticks(xlim)
    bins = d.bins if d.bins is not None else 10
    edges = np.histogram_bin_edges(allv, bins=bins, range=xlim if np.isscalar(bins) else None)
    counts = {k: np.histogram(v, bins=edges)[0] for k, v in data.items()} if d.style == "hist" else {}
    cmax = max((int(c.max()) for c in counts.values()), default=1) or 1
    yt = [t for t in ticks((0, cmax), n=2) if float(t).is_integer()] if d.style == "hist" else []

    enc: set = set()
    for k in data:
        if ctx.status(d.cells.get(k)).hollow:
            enc.add(("post_hoc",))
    if d.median:
        enc.add(("median",))
    if d.role == "control":
        enc.add(("control", d.control))

    ytw = y_tick_width(ctx, yt) if yt else 0.1
    gutter = 0.3
    pw_total = width - label_w - ytw - RIGHT
    pw = (pw_total - gutter * (len(cols) - 1)) / len(cols)
    if pw < 0.8:
        raise BuildError(f"{ctx.figure_id}: {len(cols)} columns do not fit {width} in")
    panel_h = d.panel_h or th.row_h * 2.2
    col_head = max((len(ctx.wrap(c, pw, sz.header, "bold")) for c in cols if c), default=0)
    head_h = 0.08 + col_head * line_h(sz.header) + (line_h(sz.axis) if cu else 0) + line_h(sz.role_word) + 0.08
    bottom_h, xtitle, xcue = x_bottom_height(ctx, xu, pw)
    gap = line_h(sz.tick) + 0.04  # stacked panels: the top tick of one never touches the bottom tick of the next
    row_tags = {r: [claim_tags(ctx, [d.cells.get(_key(d, r, c))]) for c in cols] for r in d.rows}
    tag_h = {r: max(len(t) for t in ts) * line_h(sz.tag) + (0.04 if any(ts) else 0) for r, ts in row_tags.items()}
    tops, y = {}, head_h
    for r in d.rows:
        tops[r] = y + tag_h[r]
        y = tops[r] + panel_h + gap
    height = y - gap + bottom_h
    rng = np.random.default_rng(0)

    def px(j: int) -> float:
        return label_w + ytw + j * (pw + gutter)

    def draw(cv: Canvas) -> None:
        muted = ctx.chrome("muted")
        y = 0.08
        for j, c in enumerate(cols):
            if c:
                for i, s in enumerate(ctx.wrap(c, pw, sz.header, "bold")):
                    cv.text(px(j), y + (i + 0.5) * line_h(sz.header), s, kind="header", size=sz.header,
                            weight="bold", full=c)  # fmt: skip
        y += col_head * line_h(sz.header)
        if cu:
            cv.text(px(0), y + line_h(sz.axis) / 2, cu.title, kind="axis_title", size=sz.axis, color=muted,
                    unit=cu.name)  # fmt: skip
            y += line_h(sz.axis)
        first = data[_key(d, d.rows[0], cols[0])]
        word = ctx.vocab.role(d.role).word if d.role in ctx.vocab.roles else None
        if word:
            xw = (float(np.median(first)) - xlim[0]) / (xlim[1] - xlim[0]) * pw
            ww = ctx.measure(word, sz.role_word, "bold")[0]
            cv.text(px(0) + min(max(xw - ww / 2, 0), pw - ww), y + line_h(sz.role_word) / 2 + 0.02, word,
                    kind="role_word", role=d.role, size=sz.role_word, weight="bold", color=hexr)  # fmt: skip
        for r in d.rows:
            top = tops[r]
            for j in range(len(cols)):
                draw_tags(cv, ctx, px(j), top - tag_h[r], row_tags[r][j])
            cv.text(0.08, top + panel_h / 2, ctx.entity_name(d.kind, r), kind="row_label", size=sz.label,
                    weight="bold")  # fmt: skip
            for j, c in enumerate(cols):
                k = _key(d, r, c)
                ax = cv.axes(px(j), top, pw, panel_h)
                ax.set_xlim(*xlim)
                ax.spines["bottom"].set_visible(True)
                ax.spines["bottom"].set_color(ctx.chrome("faint"))
                st = ctx.status(d.cells.get(k))
                meta = {"role": d.role, "cell": d.cells.get(k), "timing": st.timing, "claim": st.claim,
                        "hollow": st.hollow, **({"control": d.control} if d.role == "control" else {})}  # fmt: skip
                for tv in xt:
                    tag(ax.plot([tv, tv], [0, 1], color=ctx.chrome("grid"), lw=0.8, zorder=0,
                                transform=ax.get_xaxis_transform()), kind="grid")  # fmt: skip
                if d.style == "hist":
                    ax.set_ylim(0, cmax * 1.08)
                    _hist(ax, ctx, edges, counts[k], hexr, meta)
                    if j == 0:
                        for tv in yt:
                            yy = top + (1 - tv / (cmax * 1.08)) * panel_h
                            cv.text(px(0) - 0.06, yy, ctx.tick(tv), kind="tick_label", size=sz.tick, color=muted,
                                    ha="right")  # fmt: skip
                else:
                    ax.set_ylim(0, 1)
                    _strip(ax, ctx, data[k], hexr, meta, rng)
                if d.median:
                    m = float(np.median(data[k]))
                    tag(ax.plot([m, m], [0.08, 0.92], color=hexr, lw=ctx.marks.line_lw, zorder=4,
                                transform=ax.get_xaxis_transform()), kind="median", role=d.role, cell=meta["cell"])  # fmt: skip
        last = tops[d.rows[-1]] + panel_h
        for j in range(len(cols)):
            draw_x_bottom(cv, ctx, px(j), pw, last, xlim, xt, xu, xtitle, xcue, pid=None)

    return Plan(height, enc, draw)


def _hist(ax, ctx: Ctx, edges, counts, colour: str, meta: dict) -> None:
    bg = ctx.palette.chrome["background"]
    hollow = meta["hollow"]
    bars = ax.bar(edges[:-1], counts, width=np.diff(edges), align="edge", color=bg if hollow else colour,
                  edgecolor=colour if hollow else bg, linewidth=1.4 if hollow else 0.8, zorder=2)  # fmt: skip
    for b in bars:
        tag(b, kind="bin", **meta)


def _strip(ax, ctx: Ctx, values, colour: str, meta: dict, rng) -> None:
    bg = ctx.palette.chrome["background"]
    hollow = meta["hollow"]
    jitter = 0.5 + rng.uniform(-0.3, 0.3, size=len(values))
    tag(ax.plot(values, jitter, marker=ctx.marks.marker, ls="none", ms=STRIP_SIZE, color=colour,
                mfc=bg if hollow else colour, mec=colour, mew=1.0 if hollow else 0, zorder=3), kind="point", **meta)  # fmt: skip
