"""Meaning attached to matplotlib artists. matplotlib has no metadata slot (`gid` is a single string), so the library
stores a dict on the artist; only `tag` writes it and only `tags` reads it."""

from __future__ import annotations

_ATTR = "_styles_plot"

# kinds of data marks: each carries a role and a registry cell
DATA_KINDS = frozenset({"dot", "bin", "segment", "point", "line"})


def tag(artists, **meta):
    """Tag one artist or each of a list; returns the (first) artist."""
    items = artists if isinstance(artists, (list, tuple)) else [artists]
    for a in items:
        setattr(a, _ATTR, dict(meta))
    return items[0] if items else None


def tags(artist) -> dict:
    return getattr(artist, _ATTR, None) or {}
