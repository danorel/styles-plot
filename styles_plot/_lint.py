"""Vocabulary upkeep: canonical terms that are probably one term written two ways. A report, never a save-time check."""

from __future__ import annotations


def _edit(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _plural(a: str, b: str) -> bool:
    return a != b and (a + "s" == b or b + "s" == a or a + "es" == b or b + "es" == a)


def why(a: str, b: str) -> str:
    """Why two terms look like one, or ""."""
    if a == b:
        return ""
    if a.lower() == b.lower():
        return "differ only by case"
    la, lb = a.lower(), b.lower()
    if la.replace("-", " ") == lb.replace("-", " "):
        return "hyphen vs space"
    ta, tb = la.replace("-", " ").split(), lb.replace("-", " ").split()
    if len(ta) != len(tb):
        return ""
    diff = [(x, y) for x, y in zip(ta, tb) if x != y]
    if len(diff) != 1:
        return ""
    x, y = diff[0]
    if _plural(x, y):
        return "plural -s"
    if len(x) >= 6 and len(y) >= 6 and _edit(x, y) <= 2:
        return f"{x!r} and {y!r} differ by {_edit(x, y)} letter(s)"
    return ""


def near_duplicates(terms) -> list[tuple[str, str, str]]:
    terms = sorted(terms)
    return [(a, b, w) for i, a in enumerate(terms) for b in terms[i + 1:] if (w := why(a, b))]
