"""Check 3: marks agree with the status registry.

SP201 a mark hollow where the registry says fixed in advance, or filled where it says post hoc
SP202 a status tag that disagrees with the registry's claim (missing, extra, or other words)
SP203 a drawn cell the registry does not have (or no registry at all)
SP204 a data mark without a cell id
"""

from __future__ import annotations

from styles_plot._checks._base import CheckCtx, Problem, full_text
from styles_plot._grid import tag_words
from styles_plot._tags import DATA_KINDS, tags




def check(cx: CheckCtx) -> list[Problem]:
    reg, fid, words = cx.info.registry, cx.name, cx.vocab.words
    out: list[Problem] = []
    drawn: set[str] = set()
    line_cells: set[str] = set()
    for a in cx.marks:
        t = tags(a)
        if t.get("kind") not in DATA_KINDS:
            continue
        cell = t.get("cell")
        if not cell:
            out.append(cx.problem("SP204", f"a {t['kind']} of role {t.get('role')!r} has no cell id"))
            continue
        drawn.add(cell)
        if t["kind"] == "line":
            line_cells.add(cell)
        if reg is None:
            continue
        st = reg.get(fid, cell)
        if st is None:
            out.append(cx.problem("SP203", f"cell {cell!r} is not in the registry for figure {fid!r}"))
            continue
        if "hollow" in t and t["hollow"] != st.hollow:
            out.append(cx.problem("SP201", f"cell {cell!r} is drawn {'hollow' if t['hollow'] else 'filled'}, the "
                                           f"registry says {st.timing}"))  # fmt: skip
    if reg is None and drawn:
        out.append(cx.problem("SP203", "no status registry: [registry].path is missing or the file does not exist"))
        return out

    tagged: dict[str, str] = {}
    for t_ in cx.texts:
        t = tags(t_)
        if t.get("kind") == "status_tag":
            for cell in t.get("cells") or (t["cell"],):
                tagged[cell] = full_text(t_)
    for cell in sorted(drawn | set(tagged)):
        st = reg.get(fid, cell) if reg is not None else None
        if st is None:
            continue
        want = tag_words(st, words, cell in line_cells)
        have = tagged.get(cell, "")
        if have != want:
            out.append(cx.problem("SP202", f"cell {cell!r} carries {have!r}, the registry says {want!r}"))
    return out
