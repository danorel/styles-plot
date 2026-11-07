"""Check 8: layout. Skipped for targets with strict_layout = false (notebook).

SP601 text touching a line (spine, zero line, rule, whisker, connector, tick, data line) or a marker
SP602 text off the figure
SP603 text under the target's minimum size
SP604 the figure's size or width : height outside the target's
SP605 rotated text
SP606 two texts overlapping
SP607 a matplotlib title or suptitle (titles are the target's business, drawn as the figure's title section)
SP608 a marker other than the theme's, or hatching
SP609 colour words that do not fit one line above their panel
SP610 missing-cell words wider than the free span of their line
SP611 a line's word pushed so far from the line's end that it cannot be matched to its line
"""

from __future__ import annotations

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.transforms import Bbox

from styles_plot._checks._base import CheckCtx, Problem, full_text
from styles_plot._tags import tags

MARK_CLEAR = 4.0  # points of white between a marker's edge and any text
LINE_CLEAR = 1.5  # points of white between a line and any text
_EXEMPT_LINES = {"grid"}


def check(cx: CheckCtx) -> list[Problem]:
    th = cx.theme
    if not th.strict_layout:
        return []
    out: list[Problem] = []
    out += _size(cx)
    boxes = []
    fb = cx.fig.bbox
    for t in cx.texts:
        s = full_text(t)[:30]
        if t.get_rotation() not in (0, 0.0):
            out.append(cx.problem("SP605", f"rotated text {s!r}"))
        if t.get_fontsize() < th.min_pt - 1e-6:
            out.append(cx.problem("SP603", f"text under {th.min_pt:g} pt ({t.get_fontsize():g} pt) {s!r}"))
        bb = t.get_window_extent(cx.renderer)
        if bb.x0 < fb.x0 - 1 or bb.x1 > fb.x1 + 1 or bb.y0 < fb.y0 - 1 or bb.y1 > fb.y1 + 1:
            out.append(cx.problem("SP602", f"text off the figure {s!r}"))
        boxes.append((t, bb))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (ta, a), (tb, b) = boxes[i], boxes[j]
            if a.x0 < b.x1 - 1 and b.x0 < a.x1 - 1 and a.y0 < b.y1 - 1 and b.y0 < a.y1 - 1:
                out.append(cx.problem("SP606", f"texts overlap {full_text(ta)[:20]!r} / {full_text(tb)[:20]!r}"))
    obstacles = _obstacles(cx)
    for t, bb in boxes:
        what = _hit(bb, obstacles)
        if what:
            out.append(cx.problem("SP601", f"text {what}: {full_text(t)[:30]!r}"))
    if cx.fig._suptitle is not None and cx.fig._suptitle.get_text():
        out.append(cx.problem("SP607", "a suptitle"))
    for ax in cx.fig.axes:
        if any(ax.get_title(loc=loc) for loc in ("left", "center", "right")):
            out.append(cx.problem("SP607", "an axes title"))
    full = {tags(t)["line_full"] for t in cx.texts if tags(t).get("line_full")}
    for need, have in sorted(full):
        out.append(cx.problem("SP609", f"colour words need {need:g} in on one line above a panel {have:g} in wide: "
                                       "widen the panel, use shorter words, or name the conditions as lanes"))  # fmt: skip
    for t in cx.texts:
        if tags(t).get("far_from_line"):
            out.append(cx.problem("SP611", f"the word {t.get_text()!r} sits {tags(t)['far_from_line']:g} in from its "
                                           "line's end (lines end too close together): split the panel, or name the "
                                           "lines as rows"))  # fmt: skip
        if tags(t).get("no_room"):
            need, have = tags(t)["no_room"]
            out.append(cx.problem("SP610", f"missing words {t.get_text()!r} need {need:g} in; the widest free span of "
                                           f"their line is {have:g} in: widen the panel or shorten the words"))  # fmt: skip
    marker = cx.vocab.marks.marker
    for a in cx.marks:
        if isinstance(a, Line2D) and a.get_marker() not in (None, "None", "none", "", " ", marker):
            out.append(cx.problem("SP608", f"marker {a.get_marker()!r} (the theme's mark is {marker!r})"))
        if isinstance(a, Patch) and a.get_hatch():
            out.append(cx.problem("SP608", "hatching"))
    return out


def _size(cx: CheckCtx) -> list[Problem]:
    th = cx.theme
    w, h = cx.fig.get_size_inches()
    out = []
    if abs(w - th.width_in) > 1e-6:
        out.append(cx.problem("SP604", f"{w:g} in wide, the target {th.name!r} is {th.width_in:g} in"))
    if th.height_in is not None and cx.info.natural_height > th.height_in + 1e-6:
        out.append(cx.problem("SP604", f"needs {cx.info.natural_height:.2f} in of height, the target {th.name!r} "
                                       f"has {th.height_in:g} in"))  # fmt: skip
    wide_ok = cx.info.text_only  # cards may be as short as their text
    if th.aspect is not None and not (th.aspect[0] - 1e-6 <= w / h and (wide_ok or w / h <= th.aspect[1] + 1e-6)):
        out.append(cx.problem("SP604", f"width : height {w / h:.2f} outside {th.aspect[0]:g}-{th.aspect[1]:g}"))
    return out


def _obstacles(cx: CheckCtx):
    """Line paths (with their half widths plus clearance) and marker centres (with radius plus clearance), in display
    pixels. Grid lines are exempt."""
    px = cx.fig.dpi / 72
    paths, marks = [], []
    for ax in cx.fig.axes:
        for s in ax.spines.values():
            if s.get_visible():
                paths.append((s.get_transform().transform_path(s.get_path()), (s.get_linewidth() / 2 + LINE_CLEAR) * px,
                              None))  # fmt: skip
        for ln in ax.lines:
            if not ln.get_visible() or tags(ln).get("kind") in _EXEMPT_LINES:
                continue
            clip = ax.bbox if ln.get_clip_on() else None  # what lies outside the axes is not drawn
            if ln.get_linestyle() not in ("None", "none", "", " ") and len(ln.get_xydata()) > 1:
                half = (ln.get_linewidth() / 2 + LINE_CLEAR) * px
                paths.append((ln.get_transform().transform_path(ln.get_path()), half, clip))
            if ln.get_marker() not in (None, "None", "none", "", " "):
                rad = (ln.get_markersize() + ln.get_markeredgewidth()) * px / 2 + MARK_CLEAR * px
                pts = ln.get_transform().transform(ln.get_xydata())
                marks += [(p, rad) for p in pts if clip is None or clip.contains(*p)]
        for col in ax.collections:
            k = tags(col).get("kind")
            if k == "point":
                sizes = col.get_sizes()
                rad = (np.sqrt(sizes.max() if len(sizes) else 0) / 2 + MARK_CLEAR) * px
                marks += [(p, rad) for p in col.get_offset_transform().transform(col.get_offsets())]
    from matplotlib.path import Path

    for sub in cx.fig.subfigs:  # schematic arrows live on subfigures, not axes
        for a in sub.artists:
            t = tags(a)
            if t.get("kind") == "arrow" and "seg" in t:
                pts = t["trans"].transform(t["seg"])
                paths.append((Path(pts), (a.get_linewidth() / 2 + LINE_CLEAR) * px, None))
    return paths, marks


def _hit(bb, obstacles) -> str:
    if bb.width <= 2 or bb.height <= 2:
        return ""
    paths, marks = obstacles
    for c, rad in marks:
        dx = max(bb.x0 + 1 - c[0], 0, c[0] - bb.x1 + 1)
        dy = max(bb.y0 + 1 - c[1], 0, c[1] - bb.y1 + 1)
        if np.hypot(dx, dy) < rad:
            return "on a mark"
    for path, half, clip in paths:
        box = Bbox.from_extents(bb.x0 + 1 - half, bb.y0 + 1 - half, bb.x1 - 1 + half, bb.y1 - 1 + half)
        if clip is not None:  # only the drawn part of a clipped line counts
            box = Bbox.intersection(box, clip)
            if box is None:
                continue
        if path.intersects_bbox(box, filled=False):
            return "crosses a line"
    return ""
