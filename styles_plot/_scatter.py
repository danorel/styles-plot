"""Scatter panels side by side, e.g. an embedding (UMAP, PCA). Colour by role; each role cloud is named by a word in its
colour next to it (no legend box); a control cloud is grey and named in the key. An embedding's axes have no ticks
and no cue, and are titled "<name> 1" and "<name> 2". A cloud may be joined in order by a grey connector, with words
at its two ends.
"""

from __future__ import annotations

import numpy as np

from styles_plot._grid import claim_tags, draw_tags, draw_x_bottom, padded, ticks, x_bottom_height
from styles_plot._model import Scatter
from styles_plot._render import BuildError, Canvas, Ctx, Plan
from styles_plot._tags import tag
from styles_plot._text import line_h

GAP = 0.45  # inches between panels
LABEL_PAD = 0.06  # inches between a cloud and its word


def plan(sc: Scatter, ctx: Ctx, width: float, label_w: float) -> Plan:
    sz, n = ctx.sizes, len(sc.panels)
    if not n:
        raise BuildError(f"{ctx.figure_id}: a scatter needs at least one panel")
    for p in sc.panels:
        if (p.embedding is None) == (p.units is None):
            raise BuildError(f"{ctx.figure_id}: a scatter panel takes either embedding= or units=")
        if p.embedding is not None and p.embedding not in ctx.vocab.canonical:
            raise BuildError(f"{ctx.figure_id}: embedding name {p.embedding!r} is not a [terms].canonical term")
        for c in p.clouds:
            ctx.role_hex(c.role)
            if c.role == "control" and c.name not in ctx.vocab.controls:
                raise BuildError(f"{ctx.figure_id}: control cloud {c.name!r} is not in [controls].names")
            if np.asarray(c.xy, float).ndim != 2 or np.asarray(c.xy).shape[1] != 2:
                raise BuildError(f"{ctx.figure_id}: cloud {c.name!r} needs an (n, 2) array")
    pw = (width - 0.3 - GAP * (n - 1)) / n
    side = min(pw, sc.panel_h or pw)
    enc: set = set()
    for p in sc.panels:
        for c in p.clouds:
            if ctx.status(c.cell).hollow:
                enc.add(("post_hoc",))
            if c.role == "control":
                enc.add(("control", c.name))
    head_lines = max((len(ctx.wrap(p.header, pw, sz.header, "bold")) for p in sc.panels if p.header), default=0)
    panel_tags = [claim_tags(ctx, [c.cell for c in p.clouds]) for p in sc.panels]
    n_tags = max(len(t) for t in panel_tags)
    head_h = 0.08 + head_lines * line_h(sz.header) + n_tags * line_h(sz.tag) + line_h(sz.axis) + 0.06
    bottoms = []
    for p in sc.panels:
        if p.units:
            bottoms.append(x_bottom_height(ctx, ctx.unit(p.units[0]), pw))
        else:
            bottoms.append((line_h(sz.axis) + 0.15, [f"{p.embedding} 1"], []))
    bottom_h = max(b[0] for b in bottoms)
    height = head_h + side + bottom_h

    def draw(cv: Canvas) -> None:
        muted = ctx.chrome("muted")
        for j, p in enumerate(sc.panels):
            x0 = 0.15 + j * (pw + GAP)
            y = 0.08
            if p.header:
                for i, s in enumerate(ctx.wrap(p.header, pw, sz.header, "bold")):
                    cv.text(x0, y + (i + 0.5) * line_h(sz.header), s, kind="header", size=sz.header, weight="bold",
                            full=p.header)  # fmt: skip
            y = 0.08 + head_lines * line_h(sz.header)
            draw_tags(cv, ctx, x0, y, panel_tags[j])
            y += n_tags * line_h(sz.tag)
            ax = cv.axes(x0, head_h, pw, side)
            pts = np.concatenate([np.asarray(c.xy, float) for c in p.clouds])
            xlim = padded(float(pts[:, 0].min()), float(pts[:, 0].max()))
            ylim = padded(float(pts[:, 1].min()), float(pts[:, 1].max()))
            ax.set_xlim(*xlim)
            ax.set_ylim(*ylim)
            for s_ in ("bottom", "left"):
                ax.spines[s_].set_visible(True)
                ax.spines[s_].set_color(ctx.chrome("faint"))
            if p.embedding:
                cv.text(x0, y + line_h(sz.axis) / 2, f"{p.embedding} 2", kind="axis_title", size=sz.axis, color=muted)
                cv.text(x0 + pw / 2, head_h + side + 0.08 + line_h(sz.axis) / 2, f"{p.embedding} 1",
                        kind="axis_title", size=sz.axis, color=muted, ha="center")  # fmt: skip
            else:
                xu, yu = ctx.unit(p.units[0]), ctx.unit(p.units[1])
                cue = f"   {ctx.words.cue_y.format(yu.quantity)}" if yu.cue else ""
                cv.text(x0, y + line_h(sz.axis) / 2, yu.title, kind="axis_title", size=sz.axis, color=muted)
                if cue:
                    cv.text(x0 + ctx.measure(yu.title, sz.axis)[0] + 0.3, y + line_h(sz.axis) / 2, cue.strip(),
                            kind="cue", axis="y", size=sz.cue, color=muted)  # fmt: skip
                _, title, xcue = bottoms[j]
                draw_x_bottom(cv, ctx, x0, pw, head_h + side, xlim, ticks(xlim), xu, title, xcue, pid=None)
                for tv in ticks(ylim):
                    yy = head_h + (1 - (tv - ylim[0]) / (ylim[1] - ylim[0])) * side
                    cv.text(x0 - 0.06, yy, ctx.tick(tv), kind="tick_label", size=sz.tick, color=muted, ha="right")
            labels = []
            for c in p.clouds:
                labels += _cloud(ax, ctx, c)
            _direct_labels(cv, ax, ctx, p, labels, x0, head_h, pw, side, xlim, ylim, pts)

    return Plan(height, enc, draw)


def _cloud(ax, ctx: Ctx, c) -> list:
    mk, bg = ctx.marks, ctx.palette.chrome["background"]
    col = ctx.role_hex(c.role)
    st = ctx.status(c.cell)
    xy = np.asarray(c.xy, float)
    meta = {"role": c.role, "cell": c.cell, "timing": st.timing, "claim": st.claim, "hollow": st.hollow}
    if c.role == "control":
        meta["control"] = c.name
    if c.path:
        tag(ax.plot(xy[:, 0], xy[:, 1], color=ctx.chrome("connector"), lw=1.4, zorder=1), kind="connector")
    coll = ax.scatter(xy[:, 0], xy[:, 1], s=mk.point_size, marker=mk.marker, facecolors=bg if st.hollow else col,
                      edgecolors=col, linewidths=1.2 if st.hollow else 0, zorder=3)  # fmt: skip
    tag(coll, kind="point", **meta)
    out = []
    if c.role != "control":
        out.append((ctx.vocab.role(c.role).word, col, xy, {"kind": "role_word", "role": c.role}, "bold"))
    if c.path and c.ends:
        out.append((c.ends[0], ctx.chrome("muted"), xy[:1], {"kind": "path_end"}, "normal"))
        out.append((c.ends[1], ctx.chrome("muted"), xy[-1:], {"kind": "path_end"}, "normal"))
    return out


def _direct_labels(cv, ax, ctx: Ctx, p, labels, x0, top, pw, side, xlim, ylim, pts) -> None:
    """Each word next to its points, at the first candidate spot that covers no point and stays in the panel."""
    sz = ctx.sizes

    def to_in(xy):
        return (x0 + (xy[:, 0] - xlim[0]) / (xlim[1] - xlim[0]) * pw,
                top + (1 - (xy[:, 1] - ylim[0]) / (ylim[1] - ylim[0])) * side)  # fmt: skip

    dense = [pts]
    for c in p.clouds:  # a path's segments are obstacles too
        if c.path:
            xy = np.asarray(c.xy, float)
            t = np.linspace(0, 1, 12)[:, None]
            dense += [a + t * (b - a) for a, b in zip(xy[:-1], xy[1:])]
    px, py = to_in(np.concatenate(dense))
    rad = (ctx.marks.point_size**0.5) / 2 / 72 + 0.04
    taken: list[tuple[float, float, float, float]] = []
    for word, col, xy, meta, weight in labels:
        w, h = ctx.measure(word, sz.role_word if weight == "bold" else sz.tag, weight)
        cx, cy = to_in(xy)
        bx0, bx1, by0, by1 = cx.min(), cx.max(), cy.min(), cy.max()
        mx, my = (bx0 + bx1) / 2, (by0 + by1) / 2
        candidates = []
        for d in (LABEL_PAD + rad, LABEL_PAD + rad + 0.15, LABEL_PAD + rad + 0.35):
            candidates += [(mx - w / 2, by0 - d - h), (mx - w / 2, by1 + d), (bx1 + d, my - h / 2),
                           (bx0 - d - w, my - h / 2), (bx1 + d, by0 - d - h), (bx0 - d - w, by0 - d - h),
                           (bx1 + d, by1 + d), (bx0 - d - w, by1 + d)]  # fmt: skip

        def cost(pos):
            lx, ly = pos
            outside = not (x0 <= lx and lx + w <= x0 + pw and top <= ly and ly + h <= top + side)
            covered = int(np.sum((px > lx - rad) & (px < lx + w + rad) & (py > ly - rad) & (py < ly + h + rad)))
            overlap = any(lx < b and a < lx + w and ly < dd and c < ly + h for a, b, c, dd in taken)
            return (outside, overlap, covered)

        best = min(candidates, key=cost)
        taken.append((best[0], best[0] + w, best[1], best[1] + h))
        cv.text(best[0], best[1] + h / 2, word, size=sz.role_word if weight == "bold" else sz.tag, color=col,
                weight=weight, **meta)  # fmt: skip
