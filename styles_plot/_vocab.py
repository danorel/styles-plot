"""A project's vocabulary and style, read from plotstyle.toml.

The library owns the grammar (how a role becomes a colour, what a hollow mark means, how a key and a number are
written). The vocabulary owns every word that names a project concept, and every style parameter a project changes:

    [project]          name
    [roles.<name>]     slot, word, meaning
    [controls]         names: the grey things
    [key]              tick, band: definitions behind the key's fixed phrases
    [intervals]        <kind> = phrase ("95% interval", "± 1 SEM (bootstrap)")
    [formats.<name>]   decimals, suffix, style ("decimal" | "k of n")
    [units.<name>]     title, quantity, format, scale ("linear" | "log"), cue, cue_word ("more" | "larger")
    [terms]            canonical, templates, missing, not_claimed, [[terms.banned]] pattern/use/regex
    [[entities.<kind>]] key, name, id: ordered rows
    [registry]         path: the status CSV, relative to this file
    [palette]          slots, chrome, colour_vision
    [style]            font
    [targets.<name>]   any Theme field; a new name defines a new target
    [marks]            any MarkStyle field
    [phrases]          any Phrases field: the key's wording, status tags, cues

`load` validates the file and fails naming the table and key at fault.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from styles_plot import _numbers
from styles_plot._palette import RESERVED, Palette
from styles_plot._theme import MarkStyle, Phrases, Theme, marks_from, phrases_from, targets_from

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python 3.10
    import tomli as tomllib

DEFAULT_FORMATS = {
    "accuracy": {"decimals": 0},
    "points": {"decimals": 1},
    "share": {"decimals": 2},
    "ratio": {"decimals": 2},
    "z": {"decimals": 0},
    "count": {"style": "k of n"},
}
DEFAULT_INTERVALS = {"ci95": "95% interval"}
DEFAULT_MISSING = ("no run", "no interval")
_TOP_LEVEL = {"project", "roles", "controls", "key", "intervals", "formats", "units", "terms", "entities", "registry",
              "palette", "style", "targets", "marks", "phrases"}  # fmt: skip


class VocabError(ValueError):
    """A vocabulary the library cannot use."""


@dataclass(frozen=True)
class Role:
    name: str
    slot: str
    word: str  # the coloured word that names the role in a figure
    meaning: str  # one line, shown on the key figure
    hex: str


@dataclass(frozen=True)
class Format:
    name: str
    decimals: int = 0
    style: str = "decimal"  # "decimal" | "k of n"
    suffix: str = ""


@dataclass(frozen=True)
class Unit:
    name: str
    title: str  # the axis title: the unit and its denominator
    quantity: str  # the cue's quantity: "→ more <quantity>"
    format: str
    scale: str = "linear"
    cue: bool = True
    cue_word: str = "more"  # "→ more gap" or "→ larger gap"


@dataclass(frozen=True)
class Entity:
    key: str
    name: str  # the printed row label
    id: str  # a short id for cell names


@dataclass(frozen=True)
class Banned:
    pattern: str
    use: str
    regex: bool = False

    @cached_property
    def compiled(self) -> re.Pattern:
        if self.regex:
            return re.compile(self.pattern)
        return re.compile(rf"(?<![\w+-]){re.escape(self.pattern)}(?![\w+-])")


@dataclass(frozen=True)
class Vocab:
    project: str
    roles: dict[str, Role] = field(default_factory=dict)
    controls: tuple[str, ...] = ()
    key_tick: str = ""
    key_band: str = ""
    intervals: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_INTERVALS))
    formats: dict[str, Format] = field(default_factory=dict)
    units: dict[str, Unit] = field(default_factory=dict)
    canonical: frozenset[str] = frozenset()
    templates: tuple[str, ...] = ()
    missing: tuple[str, ...] = DEFAULT_MISSING
    not_claimed: tuple[str, ...] = ()
    banned: tuple[Banned, ...] = ()
    entity_kinds: dict[str, tuple[Entity, ...]] = field(default_factory=dict)
    registry_path: Path | None = None
    palette: Palette = field(default_factory=Palette)
    targets: dict[str, Theme] = field(default_factory=lambda: targets_from(None))
    marks: MarkStyle = field(default_factory=MarkStyle)
    words: Phrases = field(default_factory=Phrases)
    source: Path | None = None

    # ---- lookups -------------------------------------------------------------------------------------------------
    def role(self, name: str) -> Role:
        try:
            return self.roles[name]
        except KeyError:
            raise KeyError(f"no role {name!r} in the vocabulary; roles are {', '.join(self.roles)}") from None

    def unit(self, name: str) -> Unit:
        try:
            return self.units[name]
        except KeyError:
            raise KeyError(f"no unit {name!r} in the vocabulary; units are {', '.join(self.units)}") from None

    def target(self, name: str) -> Theme:
        try:
            return self.targets[name]
        except KeyError:
            raise KeyError(f"no target {name!r}; targets are {', '.join(self.targets)}") from None

    def entities(self, kind: str) -> tuple[Entity, ...]:
        try:
            return self.entity_kinds[kind]
        except KeyError:
            raise KeyError(f"no entity kind {kind!r}; kinds are {', '.join(self.entity_kinds)}") from None

    def entity(self, kind: str, key: str) -> Entity:
        for e in self.entities(kind):
            if e.key == key:
                return e
        raise KeyError(f"no entity {key!r} among {kind}")

    def check_order(self, kind: str, keys) -> None:
        """Rows follow the vocabulary's order for their kind (a subset is fine, a repeat is not)."""
        order = {e.key: i for i, e in enumerate(self.entities(kind))}
        unknown = [k for k in keys if k not in order]
        if unknown:
            raise KeyError(f"rows {unknown} are not {kind} in the vocabulary")
        idx = [order[k] for k in keys]
        if idx != sorted(set(idx)):
            raise ValueError(f"rows {list(keys)} are not in the vocabulary's {kind} order (or repeat)")

    # ---- numbers -------------------------------------------------------------------------------------------------
    def format(self, value: float, unit: str) -> str:
        """A value as every figure prints it for its unit."""
        f = self.formats[self.unit(unit).format]
        if f.style == "k of n":
            raise ValueError(f"unit {unit!r} prints counts; use format_count")
        return _numbers.decimal(value, f.decimals, f.suffix)

    def format_interval(self, lo: float, hi: float, unit: str) -> str:
        f = self.formats[self.unit(unit).format]
        return _numbers.interval(lo, hi, f.decimals, f.suffix)

    @staticmethod
    def format_count(k: int, n: int) -> str:
        return _numbers.count(k, n)

    def cue(self, unit: str, axis: str = "x") -> str:
        """The direction cue of a unit's axis: "→ more <quantity>" (or the unit's cue word)."""
        u = self.unit(unit)
        return self.words.cue_text(u.quantity, u.cue_word, axis)

    # ---- words ---------------------------------------------------------------------------------------------------
    @cached_property
    def allowed_phrases(self) -> frozenset[str]:
        """Every whole text a figure may print, apart from numbers, templates and the library's phrases."""
        words = set(self.canonical) | set(self.controls) | set(self.missing)
        words |= {r.word for r in self.roles.values()} | {r.meaning for r in self.roles.values()}
        words |= {u.title for u in self.units.values()} | {u.quantity for u in self.units.values()}
        words |= {self.cue(u.name, axis) for u in self.units.values() if u.quantity for axis in ("x", "y")}
        words |= {e.name for es in self.entity_kinds.values() for e in es}
        return frozenset(w for w in words if w)

    @cached_property
    def template_re(self) -> re.Pattern:
        names = [re.escape(e.name) for es in self.entity_kinds.values() for e in es]
        entity = f"(?:{'|'.join(names)})" if names else "(?!)"
        parts = []
        for t in self.templates:
            rx = re.escape(t)
            rx = rx.replace(re.escape("{num}"), _numbers.NUM).replace(re.escape("{entity}"), entity)
            rx = rx.replace(re.escape("{count}"), rf"{_numbers.NUM} of {_numbers.NUM}")
            parts.append(f"(?:{rx})")
        return re.compile("|".join(parts) or "(?!)")

    def banned_hits(self, text: str) -> list[str]:
        return [f"{b.pattern!r} (use {b.use!r})" for b in self.banned if b.compiled.search(text)]


# ---- loading ---------------------------------------------------------------------------------------------------------
def load(path: str | Path) -> Vocab:
    """Load a project's plotstyle.toml."""
    path = Path(path)
    return loads(path.read_text(encoding="utf-8"), root=path.parent, source=path)


def loads(text: str, root: Path | None = None, source: Path | None = None) -> Vocab:
    """Parse a vocabulary from TOML text; `root` resolves the registry path."""
    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise VocabError(f"{source or '<string>'}: {e}") from None
    return from_dict(doc, root=root, source=source)


def from_dict(doc: dict, root: Path | None = None, source: Path | None = None) -> Vocab:
    """Build a vocabulary from a dict shaped like plotstyle.toml (for projects that configure in Python)."""
    where = str(source or "plotstyle.toml")
    unknown = set(doc) - _TOP_LEVEL
    if unknown:
        raise VocabError(f"{where}: unknown tables {sorted(unknown)}")
    try:
        palette = Palette.from_dict(doc.get("palette"), "[palette]")
        targets = targets_from(doc.get("targets"), (doc.get("style") or {}).get("font"))
        marks = marks_from(doc.get("marks"))
        words = phrases_from(doc.get("phrases"))
    except (ValueError, TypeError) as e:
        raise VocabError(f"{where}: {e}") from None

    formats = _formats(doc.get("formats") or {}, where)
    terms = doc.get("terms") or {}
    banned = _banned(terms.get("banned", []), where)
    canonical = frozenset(_strs(terms.get("canonical", []), f"{where} [terms].canonical"))
    for t in canonical:
        hits = [b.pattern for b in banned if b.compiled.search(t)]
        if hits:
            raise VocabError(f"{where} [terms]: canonical term {t!r} matches the banned pattern {hits[0]!r}")
    reg = (doc.get("registry") or {}).get("path")
    key = doc.get("key") or {}
    return Vocab(
        project=_need(_need(doc, "project", where), "name", f"{where} [project]"),
        roles=_roles(doc.get("roles") or {}, palette, where),
        controls=_strs((doc.get("controls") or {}).get("names", []), f"{where} [controls].names"),
        key_tick=key.get("tick", ""),
        key_band=key.get("band", ""),
        intervals={**DEFAULT_INTERVALS, **(doc.get("intervals") or {})},
        formats=formats,
        units=_units(doc.get("units") or {}, formats, words.cue_words, where),
        canonical=canonical,
        templates=_strs(terms.get("templates", []), f"{where} [terms].templates"),
        missing=_strs(terms.get("missing", list(DEFAULT_MISSING)), f"{where} [terms].missing"),
        not_claimed=_strs(terms.get("not_claimed", []), f"{where} [terms].not_claimed"),
        banned=banned,
        entity_kinds=_entities(doc.get("entities") or {}, where),
        registry_path=None if not reg else (Path(reg) if root is None else root / reg),
        palette=palette,
        targets=targets,
        marks=marks,
        words=words,
        source=source,
    )


def _need(table: dict, key: str, where: str):
    if key not in table:
        raise VocabError(f"{where}: missing key {key!r}")
    return table[key]


def _strs(value, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise VocabError(f"{where}: expected a list of strings")
    return tuple(value)


def _roles(doc: dict, palette: Palette, where: str) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    owner: dict[str, str] = {}
    for name, r in doc.items():
        w = f"{where} [roles.{name}]"
        if name in RESERVED:
            raise VocabError(f"{w}: {' and '.join(RESERVED)} are reserved slots, not roles")
        slot = _need(r, "slot", w)
        if slot not in palette.role_slots:
            raise VocabError(f"{w}: slot {slot!r} is not a role slot ({', '.join(palette.role_slots)})")
        if slot in owner:
            raise VocabError(f"{w}: slot {slot!r} is already the role {owner[slot]!r} (one meaning per colour)")
        owner[slot] = name
        roles[name] = Role(name, slot, r.get("word", name), r.get("meaning", ""), palette.role_slots[slot])
    return roles


def _formats(doc: dict, where: str) -> dict[str, Format]:
    raw = {k: dict(v) for k, v in DEFAULT_FORMATS.items()}
    for k, v in doc.items():
        raw.setdefault(k, {}).update(v)
    out = {}
    for k, v in raw.items():
        w = f"{where} [formats.{k}]"
        style = v.get("style", "decimal")
        if style not in ("decimal", "k of n"):
            raise VocabError(f"{w}: style must be 'decimal' or 'k of n'")
        dec = v.get("decimals", 0)
        if not isinstance(dec, int) or not 0 <= dec <= 6:
            raise VocabError(f"{w}: decimals must be an integer 0-6")
        out[k] = Format(k, dec, style, v.get("suffix", ""))
    return out


def _units(doc: dict, formats: dict[str, Format], cue_words: tuple[str, ...], where: str) -> dict[str, Unit]:
    out = {}
    for name, u in doc.items():
        w = f"{where} [units.{name}]"
        fmt = _need(u, "format", w)
        if fmt not in formats:
            raise VocabError(f"{w}: format {fmt!r} is not in [formats] ({', '.join(formats)})")
        scale = u.get("scale", "linear")
        if scale not in ("linear", "log"):
            raise VocabError(f"{w}: scale must be 'linear' or 'log'")
        title = _need(u, "title", w)
        if scale == "log" and not title.endswith("(log scale)"):
            raise VocabError(f"{w}: a log-scale unit's title ends with '(log scale)'")
        cue, quantity = bool(u.get("cue", True)), u.get("quantity", "")
        if cue and not quantity:
            raise VocabError(f"{w}: a unit with a cue needs a quantity; set cue = false for an axis with no direction")
        word = u.get("cue_word", cue_words[0])
        if word not in cue_words:
            raise VocabError(f"{w}: cue_word {word!r} is not one of {', '.join(cue_words)}")
        out[name] = Unit(name, title, quantity, fmt, scale, cue, word)
    return out


def _banned(items: list, where: str) -> tuple[Banned, ...]:
    out = []
    for i, b in enumerate(items):
        w = f"{where} [[terms.banned]] #{i + 1}"
        item = Banned(_need(b, "pattern", w), _need(b, "use", w), bool(b.get("regex", False)))
        try:
            item.compiled  # noqa: B018 - compile now to report a bad pattern at load
        except re.error as e:
            raise VocabError(f"{w}: bad regex: {e}") from None
        out.append(item)
    return tuple(out)


def _entities(doc: dict, where: str) -> dict[str, tuple[Entity, ...]]:
    out = {}
    for kind, items in doc.items():
        w = f"{where} [[entities.{kind}]]"
        if not isinstance(items, list):
            raise VocabError(f"{w}: expected an array of tables")
        es = tuple(Entity(_need(e, "key", w), _need(e, "name", w), e.get("id", e["key"])) for e in items)
        for attr in ("key", "name", "id"):
            vals = [getattr(e, attr) for e in es]
            dup = sorted({x for x in vals if vals.count(x) > 1})
            if dup:
                raise VocabError(f"{w}: duplicate {attr} {dup}")
        out[kind] = es
    return out
