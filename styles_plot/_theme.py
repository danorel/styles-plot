"""Style parameters that are not colours: targets (size, dpi, fonts, minimum text), marks (shape, sizes, line widths)
and phrases (the key's wording, status tags, cues). Each has defaults and is overridden from the vocabulary file
([targets.<name>], [marks], [phrases], [style]) or in Python with dataclasses.replace.

A Theme never holds a colour; colours live in the Palette.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace


@dataclass(frozen=True)
class Sizes:
    """Font sizes (pt) per text kind, for the three text levels."""

    header: float = 12.0  # bold ink: panel and group headers
    label: float = 12.0  # bold ink: row labels
    role_word: float = 12.0  # bold, in the role colour
    value: float = 11.0  # ink: values beside marks, text columns
    tick: float = 11.0  # grey
    axis: float = 11.0  # grey: axis titles
    cue: float = 11.0  # grey
    key: float = 11.0  # grey
    tag: float = 11.0  # grey: status tags, missing words, notes, rule labels


@dataclass(frozen=True)
class Theme:
    name: str
    width_in: float
    dpi: int
    aspect: tuple[float, float] | None = (1.0, 2.6)  # width : height bounds; None = any
    height_in: float | None = None  # fixed height (a slide); None = from the layout
    min_pt: float = 11.0  # nothing smaller, anywhere
    font: str = "DejaVu Sans"
    sizes: Sizes = field(default_factory=Sizes)
    row_h: float = 0.42  # inches per table row
    sub_h: float = 0.26  # inches added to a row that carries a status tag or a note
    pad: float = 0.2  # inches between columns
    strict_layout: bool = True  # False: layout checks off (notebook)
    publishable: bool = True  # False: `styles-plot check` refuses the PNG (notebook)
    title: bool = False  # draw the figure's title (one bold claim) above it
    caption: bool = False  # draw the figure's caption (the detailed explanation) under it
    title_size: float = 13.0
    caption_size: float = 11.0

    @property
    def px_width(self) -> int:
        return round(self.width_in * self.dpi)


TARGETS: dict[str, Theme] = {
    # a reading column shown at ~720 px: 8.0 in at 200 dpi, nothing under 11 pt; the post carries title and caption
    "post": Theme("post", 8.0, 200, (1.0, 2.6)),
    # a slide's figure area, 12.3 x 5.3 in at 200 dpi; the slide title carries the claim, the notes the caption
    "slide": Theme("slide", 12.3, 200, None, height_in=5.3, min_pt=12.0,
                   sizes=Sizes(14, 13, 13, 12, 13, 14, 12, 12, 12), row_h=0.5, sub_h=0.3, pad=0.3),  # fmt: skip
    # a README's figure, 11 in at 160 dpi (shown at the 880 px column): a bold claim above, a caption under
    "readme": Theme("readme", 11.0, 160, (1.0, 3.0), sizes=Sizes(13, 12, 12, 11, 12, 13, 11, 11, 11),
                    title=True, caption=True),  # fmt: skip
    # a quick look; never published
    "notebook": Theme("notebook", 8.0, 100, None, min_pt=0.0, strict_layout=False, publishable=False),
}


@dataclass(frozen=True)
class MarkStyle:
    marker: str = "o"  # the estimate's mark; every check compares with this
    dot_size: float = 9.5  # marker size (pt)
    hollow_edge: float = 2.0  # edge width of a hollow (post hoc) mark
    whisker_lw: float = 1.8
    connector_lw: float = 3.2
    tick_lw: float = 2.4
    tick_half: float = 0.3  # half height of the grey tick, as a share of the row height
    rule_lw: float = 1.1
    rule_dash: tuple[float, float] = (4.0, 3.0)
    line_lw: float = 2.2
    shading_alpha: float = 0.18  # an interval band on a line: the line's colour at this alpha
    point_size: float = 30.0  # scatter marker area (pt^2)
    bar_height: float = 0.62  # a stack's bar, as a share of the row height


@dataclass(frozen=True)
class Phrases:
    """The library's fixed wording; `{}` is filled from the vocabulary. Override to change language or wording."""

    control: str = "grey: {}"
    tick: str = "grey tick: {}"
    post_hoc: str = "○ post hoc"
    whisker: str = "whiskers: {}"
    shading: str = "shading: {}"
    band: str = "grey band: {}"
    median: str = "line: median"
    descriptive: str = "descriptive"
    not_claimed: str = "not claimed: {}"
    cue: str = "→ more {}"  # under an x-axis
    cue_y: str = "↑ more {}"  # beside a sweep's value axis
    control_mark: str = "●"  # the grey mark before the key's control phrase

    @property
    def cue_prefixes(self) -> tuple[str, str]:
        return self.cue.split("{}")[0], self.cue_y.split("{}")[0]


def _merge(obj, doc: dict, where: str):
    names = {f.name for f in fields(obj)}
    bad = [k for k in doc if k not in names]
    if bad:
        raise ValueError(f"{where}: unknown keys {bad}; known: {', '.join(sorted(names))}")
    kw = {}
    for k, v in doc.items():
        cur = getattr(obj, k)
        if isinstance(cur, Sizes):
            v = _merge(cur, v, f"{where}.{k}")
        elif isinstance(cur, tuple) and isinstance(v, list):
            v = tuple(v)
        kw[k] = v
    return replace(obj, **kw)


def targets_from(doc: dict | None, font: str | None = None) -> dict[str, Theme]:
    """The default targets merged with [targets.<name>] tables; a new name defines a new target (it needs
    width_in and dpi)."""
    out = dict(TARGETS)
    for name, t in (doc or {}).items():
        where = f"[targets.{name}]"
        if name in out:
            out[name] = _merge(out[name], t, where)
        else:
            if "width_in" not in t or "dpi" not in t:
                raise ValueError(f"{where}: a new target needs width_in and dpi")
            out[name] = _merge(Theme(name, t["width_in"], t["dpi"]), {k: v for k, v in t.items()}, where)
    if font:
        out = {k: replace(v, font=font) for k, v in out.items()}
    for name, t in out.items():
        if "/" in name or not name:
            raise ValueError(f"[targets]: bad target name {name!r}")
        if t.width_in <= 0 or t.dpi <= 0:
            raise ValueError(f"[targets.{name}]: width_in and dpi must be positive")
    return out


def marks_from(doc: dict | None) -> MarkStyle:
    return _merge(MarkStyle(), doc or {}, "[marks]")


def phrases_from(doc: dict | None) -> Phrases:
    p = _merge(Phrases(), doc or {}, "[phrases]")
    for k in ("control", "tick", "whisker", "shading", "band", "not_claimed", "cue", "cue_y"):
        if getattr(p, k).count("{}") != 1:
            raise ValueError(f"[phrases].{k}: needs exactly one {{}} placeholder")
    if "←" in p.cue or "←" in p.cue_y:
        raise ValueError("[phrases]: a cue never points left")
    return p
