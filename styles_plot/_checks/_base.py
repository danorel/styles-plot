"""What every check needs: the rendered figure, its tagged artists, and the render's info."""

from __future__ import annotations

from dataclasses import dataclass, field

from matplotlib.collections import Collection
from matplotlib.colors import to_hex, to_rgba
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.text import Text

from styles_plot._render import RenderInfo, info
from styles_plot._tags import tags


@dataclass(frozen=True)
class Problem:
    """One violation: a stable code, a message, the figure it was found in, and, when known, what is at fault
    (`subject`), where (`where`: target, block, row, column), its box and its obstacle's box (inches from the figure's
    bottom-left), and one line that fixes it (`fix`)."""

    code: str
    message: str
    figure: str = ""
    subject: str = ""
    where: dict | None = field(default=None, compare=False, hash=False)
    bbox_in: tuple | None = None
    obstacle_in: tuple | None = None
    fix: str = ""

    def __str__(self) -> str:
        head = f"{self.figure}: {self.code} {self.message}" if self.figure else f"{self.code} {self.message}"
        return f"{head} → {self.fix}" if self.fix else head

    def as_dict(self) -> dict:
        d = {"code": self.code, "message": self.message, "figure": self.figure}
        for k in ("subject", "where", "bbox_in", "obstacle_in", "fix"):
            v = getattr(self, k)
            if v:
                d[k] = list(v) if isinstance(v, tuple) else v
        return d


@dataclass
class CheckCtx:
    fig: object
    info: RenderInfo
    texts: list  # every visible, non-empty Text
    marks: list  # every visible Line2D, Patch and Collection, minus figure, subfigure and axes backgrounds
    renderer: object

    @classmethod
    def of(cls, fig) -> CheckCtx:
        i = info(fig)
        fig.canvas.draw()
        texts = [t for t in fig.findobj(Text) if t.get_visible() and t.get_text().strip()]
        return cls(fig, i, texts, marks_of(fig), fig.canvas.get_renderer())

    @property
    def name(self) -> str:
        return self.info.figure

    @property
    def vocab(self):
        return self.info.vocab

    @property
    def theme(self):
        return self.info.theme

    def problem(self, code: str, message: str, **detail) -> Problem:
        if "where" in detail or detail:
            detail.setdefault("where", {"target": self.info.target})
        return Problem(code, message, self.name, **detail)

    def inches(self, bb) -> tuple[float, float, float, float]:
        """A display box (pixels) in inches from the figure's bottom-left."""
        d = self.fig.dpi
        return tuple(round(float(v) / d, 3) for v in (bb.x0, bb.y0, bb.x1, bb.y1))

    def tagged(self, *kinds: str) -> list:
        return [a for a in [*self.marks, *self.texts] if tags(a).get("kind") in kinds]


def marks_of(fig) -> list:
    """Every visible Line2D, Patch and Collection of a figure, minus the figure, subfigure and axes backgrounds and the
    axes' own tick marks (chrome drawn by matplotlib)."""
    own = {id(fig.patch), *(id(s.patch) for s in fig.subfigs), *(id(ax.patch) for ax in fig.axes)}
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis):
            own |= {id(t) for t in (*axis.get_ticklines(), *axis.get_ticklines(minor=True))}
    return [a for a in fig.findobj(lambda a: isinstance(a, (Line2D, Patch, Collection)))
            if id(a) not in own and a.get_visible()]  # fmt: skip


def full_text(t) -> str:
    """A text's whole phrase: wrapped lines carry it in their tags."""
    return tags(t).get("full") or t.get_text()


def _hex(c) -> str | None:
    if c is None or (isinstance(c, str) and c.lower() == "none"):
        return None
    try:
        rgba = to_rgba(c)
    except (ValueError, TypeError):
        return None
    return to_hex(rgba[:3]).lower() if rgba[3] > 0 else None


def colours(a) -> set[str]:
    """The opaque colours an artist paints with, as lower-case hex (alpha ignored; invisible parts dropped)."""
    found: list = []
    if isinstance(a, Text):
        found.append(a.get_color())
    elif isinstance(a, Line2D):
        if a.get_linestyle() not in ("None", "none", "", " ") and len(a.get_xdata()) > 1:
            found.append(a.get_color())
        if a.get_marker() not in (None, "None", "none", "", " "):
            found.append(a.get_markerfacecolor())
            if a.get_markeredgewidth() > 0:
                found.append(a.get_markeredgecolor())
    elif isinstance(a, Patch):
        found.append(a.get_facecolor())
        if a.get_linewidth() > 0:
            found.append(a.get_edgecolor())
    elif isinstance(a, Collection):
        found += [tuple(c) for c in a.get_facecolors()]
        widths = a.get_linewidths()
        if widths is not None and len(widths) and max(widths) > 0:
            found += [tuple(c) for c in a.get_edgecolors()]
    return {h for h in map(_hex, found) if h}


def library_phrases(vocab) -> set[str]:
    """Whole phrases the library prints from the vocabulary: key entries, status tags, cues."""
    w = vocab.words
    out = {w.post_hoc, w.median, w.descriptive, w.control_mark, w.key_roles, w.key_marks}
    out.add(w.key_missing.format(" · ".join(vocab.missing)))
    if vocab.controls:
        out.add(w.control.format(" · ".join(vocab.controls)))
    out |= {w.not_claimed.format(r) for r in vocab.not_claimed}
    if vocab.key_tick:
        out.add(w.tick.format(vocab.key_tick))
    for band in (vocab.key_band, *vocab.key_bands.values()):
        if band:
            out.add(w.band.format(band))
    for phrase in vocab.intervals.values():
        out |= {w.whisker.format(phrase), w.shading.format(phrase)}
    out.add(w.post_hoc_tag)
    out.add(w.all_post_hoc)
    claims = [w.descriptive, *(w.not_claimed.format(r) for r in vocab.not_claimed)]
    out |= {w.tag_join.join((w.post_hoc_tag, c)) for c in claims}  # a whole line's timing and claim
    return out
