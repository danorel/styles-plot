"""The key figure: a project's whole grammar on one image (each role's colour with its word and meaning, the grey of
controls, the hollow mark, the whisker, the grey tick, the grey band, the missing-cell words). Built from the
vocabulary alone, as a schematic with direct labels, and checked like any figure.
"""

from __future__ import annotations

from styles_plot._model import Mark, Schematic, Words
from styles_plot._render import Figure
from styles_plot._text import line_h, text_size
from styles_plot._vocab import Vocab

ROW = 0.36  # inches per line
SWATCH_X = 0.3


def key_figure(vocab: Vocab, target: str = "post", id: str = "key") -> Figure:
    theme = vocab.target(target)
    sz, w = theme.sizes, vocab.words
    word_w = max((text_size(r.word, sz.role_word, "bold", theme.font)[0] for r in vocab.roles.values()), default=0.0)
    meaning_x = SWATCH_X + 0.25 + word_w + 0.3
    el: list = []
    y = 0.1 + line_h(sz.role_word) / 2
    el.append(Words(0.1, y, [(w.key_roles, None)], bold=True))
    y += ROW
    for r in vocab.roles.values():
        el.append(Mark(SWATCH_X, y, r.name))
        el.append(Words(SWATCH_X + 0.2, y, [(r.word, r.name)], bold=True))
        if r.meaning:
            el.append(Words(meaning_x, y, [(r.meaning, None)]))
        y += ROW
    if vocab.controls:
        el.append(Mark(SWATCH_X, y, "control"))
        el.append(Words(SWATCH_X + 0.2, y, [(w.control.format(" · ".join(vocab.controls)), None)]))
        y += ROW
    y += 0.12
    el.append(Words(0.1, y, [(w.key_marks, None)], bold=True))
    y += ROW
    el.append(Mark(SWATCH_X, y, "control", hollow=True))
    el.append(Words(SWATCH_X + 0.4, y, [(w.post_hoc, None)]))
    y += ROW
    el.append(Mark(SWATCH_X, y, "control", interval=(0.18, 0.18)))
    el.append(Words(SWATCH_X + 0.4, y, [(w.whisker.format(vocab.intervals["ci95"]), None)]))
    y += ROW
    el.append(Words(0.1, y, [(w.key_missing.format(" · ".join(vocab.missing)), None)]))
    y += ROW
    return Figure(id, vocab, direct_labels=True).add(Schematic(height=y, elements=el))
