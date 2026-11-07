"""Example cards: a real item as an image. The prompt's text verbatim (some words bold or in a role's colour), then one
row per reader with its answer in each condition, in the reader's colour, then a small grey note (how the item was
picked, its id). Every coloured element is itself words, so a card lives in a figure with direct_labels=True.
"""

from __future__ import annotations

from styles_plot._model import Card
from styles_plot._render import BuildError, Canvas, Ctx, Plan
from styles_plot._tags import tag
from styles_plot._text import line_h

PAD = 0.12  # inches of margin left and right
GAP = 0.15  # inches between the card's parts and between columns
PARA_GAP = 0.08  # inches between two paragraphs of the prompt


def _flow(ctx: Ctx, parts, width: float, size: float) -> list[list[tuple]]:
    """Flow (text, role, bold) parts into lines no wider than `width`, keeping the text's own spacing: a part that
    starts with punctuation sticks to the word before it. Returns [[(token, role, bold, x), ...]] per line."""
    import re

    space = ctx.measure(" ", size)[0] + 0.01
    groups: list[list[tuple]] = [[]]  # words: runs of non-space tokens, possibly across parts
    for part in parts:
        text, role = part[0], part[1]
        bold = len(part) > 2 and bool(part[2])
        for tok in re.findall(r"\s+|\S+", text):
            if tok.isspace():
                if groups[-1]:
                    groups.append([])
            else:
                groups[-1].append((tok, role, bold))
    groups = [g for g in groups if g]
    lines: list[list[tuple]] = [[]]
    x = 0.0
    for g in groups:
        widths = [ctx.measure(t, size, "bold" if b else "normal")[0] for t, _r, b in g]
        w = sum(widths)
        if lines[-1] and x + w > width:
            lines.append([])
            x = 0.0
        for (t, r, b), wt in zip(g, widths):
            lines[-1].append((t, r, b, x))
            x += wt
        x += space
    return lines if lines[-1] else lines[:-1]


def _paragraphs(prompt) -> list[list[tuple]]:
    """A prompt as paragraphs: a list of parts is one paragraph; a list of lists of parts is several."""
    if prompt and isinstance(prompt[0], (list, tuple)) and prompt[0] and isinstance(prompt[0][0], tuple):
        return [list(p) for p in prompt]
    return [list(prompt)]


def plan(card: Card, ctx: Ctx, width: float, label_w: float) -> Plan:
    sz = ctx.sizes
    paragraphs = _paragraphs(card.prompt)
    for part in (p for para in paragraphs for p in para):
        if not isinstance(part, tuple) or len(part) not in (2, 3):
            raise BuildError(f"{ctx.figure_id}: a prompt part is (text, role) or (text, role, bold)")
        if part[1] is not None:
            ctx.role_hex(part[1])
    if not card.columns:
        raise BuildError(f"{ctx.figure_id}: a card needs at least one column")
    for r in card.rows:
        ctx.role_hex(r.role)
        extra = set(r.answers) - set(card.columns)
        if extra:
            raise BuildError(f"{ctx.figure_id}: answers for {sorted(extra)}, which are not the card's columns")
    inner = width - 2 * PAD
    prompt = [_flow(ctx, para, inner, sz.value) for para in paragraphs]
    lab_w = max((ctx.measure(r.label, sz.role_word, "bold")[0] for r in card.rows), default=0.0) + GAP
    col_w = (inner - lab_w - GAP * (len(card.columns) - 1)) / len(card.columns)
    if col_w < 0.6:
        raise BuildError(f"{ctx.figure_id}: {len(card.columns)} columns leave {col_w:.2f} in each")
    headers = [ctx.wrap(h, col_w, sz.header, "bold") for h in card.columns]
    cells = [[ctx.wrap(r.answers.get(h, ""), col_w, sz.value) if r.answers.get(h) else [] for h in card.columns]
             for r in card.rows]  # fmt: skip
    row_hs = [max([1, *(len(c) for c in row)]) * line_h(sz.value) + 0.12 for row in cells]
    note = ctx.wrap(card.note, inner, sz.tag) if card.note else []
    head_h = max(len(h) for h in headers) * line_h(sz.header) + 0.06
    prompt_h = sum(len(lines) for lines in prompt) * line_h(sz.value) + PARA_GAP * (len(prompt) - 1)
    note_h = len(note) * line_h(sz.tag)
    height = 0.1 + prompt_h + GAP + head_h + sum(row_hs) + (GAP + note_h if note else 0.0) + 0.1

    def draw(cv: Canvas) -> None:
        ink, muted = ctx.chrome("text"), ctx.chrome("muted")
        y = 0.1
        for k, lines in enumerate(prompt):
            if k:
                y += PARA_GAP
            for line in lines:
                for word, role, bold, x in line:
                    meta = {"role": role} if role else {}
                    cv.text(PAD + x, y + line_h(sz.value) / 2, word, kind="card_text", size=sz.value,
                            weight="bold" if bold else "normal", color=ctx.role_hex(role) if role else ink,
                            verbatim=True, ids_ok=True, **meta)  # fmt: skip
                y += line_h(sz.value)
        y += GAP
        x0 = PAD + lab_w
        for j, lines in enumerate(headers):
            for i, s in enumerate(lines):
                cv.text(x0 + j * (col_w + GAP), y + (i + 0.5) * line_h(sz.header), s, kind="header", size=sz.header,
                        weight="bold", color=ink, full=card.columns[j])  # fmt: skip
        y += head_h
        for k, (r, row, h) in enumerate(zip(card.rows, cells, row_hs)):
            if k % 2 == 0:
                cv.rect(0.0, y, width, h, ctx.chrome("zebra"), kind="zebra")
            colour = ctx.role_hex(r.role)
            cv.text(PAD, y + 0.06 + line_h(sz.role_word) / 2, r.label, kind="role_word", role=r.role,
                    size=sz.role_word, weight="bold", color=colour)  # fmt: skip
            for j, lines in enumerate(row):
                for i, s in enumerate(lines):
                    cv.text(x0 + j * (col_w + GAP), y + 0.06 + (i + 0.5) * line_h(sz.value), s, kind="card_text",
                            size=sz.value, color=colour, role=r.role, verbatim=True, ids_ok=True,
                            full=r.answers[card.columns[j]])  # fmt: skip
            y += h
        if note:
            y += GAP
            for i, s in enumerate(note):
                t = cv.text(PAD, y + (i + 0.5) * line_h(sz.tag), s, kind="card_note", size=sz.tag, color=muted,
                            verbatim=True, full=card.note)  # fmt: skip
                tag(t, kind="card_note", verbatim=True, ids_ok=True, full=card.note)

    return Plan(height, set(), draw)
