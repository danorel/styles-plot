# The grammar

These are the rules every figure drawn with styles-plot follows, and that `save` checks. They name no project's
concepts: a project supplies its roles, words, units, entities and statuses in its vocabulary file
(`plotstyle.toml`, see [ADOPTING.md](ADOPTING.md)), and may change any style parameter (colours, marks, fonts, sizes,
wording). What it cannot change is what a colour, a hollow mark or a key line *means*.

## A. Colour = role

- A role is a thing the reader learns once and recognises in every figure (a method, a reader, an intervention). The
  vocabulary maps each role to one palette slot; no two roles share a slot.
- A slot's colour means its role on every mark, word and value in every figure of the project.
- **No shades.** There is no lighter or darker version of a role. A second condition of the same role gets its own
  column or row, named in words, in the same colour.
- **Grey is a control** (or baseline) and nothing else. The light grey `other` is the remainder of a 100% stack.
- Chrome (text, grid, zebra stripes, connectors, rules, the grey band) uses the palette's chrome colours, never a role
  colour.

Default slots:

| slot | hex | slot | hex |
|---|---|---|---|
| ink | `#2B2B2B` | slate | `#4A5F6A` |
| violet | `#6B5BD2` | brown | `#8C6D46` |
| teal | `#1A9E8A` | pink | `#B8689A` |
| amber | `#E08A1E` | control | `#A8A8A8` |
| blue | `#3A7DC9` | other | `#D9D9D9` |
| brick | `#B8433A` | | |

### Colour vision: pairs that may not share a figure

Under simulated deuteranopia, protanopia and tritanopia (Machado et al. 2009, severity 100) and normal vision, two role
colours drawn in one figure must differ by at least **12** (CIEDE2000), and a role colour and control grey by at least
**8**. Nine saturated hues cannot all be that far apart under every deficiency, so the floor is per figure. These
default pairs fail it and **may not share a figure**:

| pair | smallest distance | under |
|---|---:|---|
| brick – brown | 3.4 | deuteranopia |
| violet – blue | 5.1 | deuteranopia |
| teal – pink | 5.9 | deuteranopia |
| teal – blue | 9.5 | tritanopia |
| blue – pink | 9.7 | protanopia |
| brown – pink | 11.3 | tritanopia |

`styles-plot palette` prints the full table (and, with `--vocab`, the project's roles). A figure made only of
schematics may set `direct_labels=True` instead: it is exempt from the floors, and every coloured element must then
have a word in its colour right next to it.

## B. Status is never a colour

Every drawn cell has a row in the project's status registry (`figure, cell, timing, claim, claim_reason, reason,
source`), and every data mark carries its cell id.

- **timing** decides the mark: **hollow (○) = post hoc**, and nothing else. Fixed in advance is filled. When every
  estimate of a figure is post hoc, hollow marks would tell nothing apart: the marks are drawn filled and the key says
  once "all estimates post hoc" (and a sweep line's panel tag drops "post hoc").
- **claim** decides the grey tag in the cell: none for a claimed cell, "descriptive", or "not claimed: <reason>".
- A row for figure `*` holds in every figure; a figure's own row may change the claim, never the timing.
- A **missing cell** says why in grey words from the vocabulary's list ("no run", "no interval"…).

## C. Marks

- **The dot** is an estimate; a same-colour whisker is its interval; a grey connector joins dots of one row.
- **Bars** only in 100% stacks and histograms. A stack carries no whiskers: the interval its claim rests on is
  printed in a text column beside it. A segment that is zero in every row is not drawn or named; a text column says
  so when it matters.
- **Lines** only when x is depth (layers). A line is never hollow: a whole line's status is a grey tag above its panel
  ("post hoc", "descriptive", "not claimed: <reason>", joined with " · "), like a dot table's tags. Points on a line
  are dots that keep their timing: filled when fixed in advance, hollow when post hoc. A point measured on its own
  (fixed in advance, off the line's values) carries its own interval as a vertical whisker.
- **An interval band** on a line is the line's colour at the theme's one shading alpha; it names an interval, never a
  variable.
- **The largest same-size control** (or the project's definition) is a grey tick on the estimate's own axis.
- **Reference lines** are dashed grey with a vocabulary label ("chance"), vertical in a dot table, vertical or
  horizontal in a sweep. **A grey band** has a vocabulary definition: `[key].band`, or a named one in `[key.bands]`.
  One figure shows grey bands of one meaning only (two greys cannot be told apart).
- No marker other than the theme's, no hatching, no violins.

## D. Layout

- **Entities are rows**, in the vocabulary's order; **conditions are columns**. A second condition of the same row is a
  lane (a sub-row), named in grey words under the row's name or by its colour word above the table. Small multiples
  stack in entity order with a shared x axis.
- Two quantities on different scales are two panels with their own axis titles, never a twin axis.
- One colour means one estimate per line: a second estimate of the same role in a row gets its own column, header and
  axis, never a second dot of that colour in the same column.
- A panel header names a quantity, never a claim. All text is horizontal.
- Several blocks in one figure are one matplotlib figure (subfigures) with one key under the last.
- Small multiples on one unit (the panels of one column group) share one axis title and one cue.
- A headline figure may carry one "read:" sentence under it that walks through one value, its numbers from the data.

## E. Keys: every encoding named in the figure

1. Every role colour in a panel is named by a coloured word above its first row (or next to its cloud): one line, in
   the order the dots appear from left to right. Words that do not fit one line fail the layout check. A column whose
   header is its only role's word (a difference drawn in the neutral role) shows that header in the role's colour
   instead.
2. One key line under the figure, in this order, listing only what is drawn:
   `grey: <controls>` · `grey tick: <definition>` · `○ post hoc` · `whiskers: <interval>` · `shading: <interval>` ·
   `line: median` · `grey band: <definition>`. The interval phrase comes from the vocabulary ("95% interval",
   "± 1 SEM (bootstrap)", "interquartile range"); a figure drawing two kinds names both.
3. The key is built from what was drawn: nothing drawn is unnamed, nothing named is undrawn. No legend boxes.

## F. Words

A figure prints only a vocabulary term, a template match, a number in its unit's format, an entity name, a role word,
or a library phrase. Prompt text in a schematic is marked verbatim. Banned variants fail; run ids and timestamps fail.

- **Axis titles** name the unit and its denominator, from the vocabulary.
- **Cues** describe the axis, never what is good: `→ more <quantity>` under an x axis, `↑ more <quantity>` beside a
  sweep's value axis. A unit may say "larger" instead of "more" (`cue_word = "larger"`: "→ larger gap") for gaps,
  differences and z. "Lower is better" goes in the axis title. A log scale ends the title with "(log scale)". No left
  arrows. Embedding axes ("UMAP 1", "UMAP 2") have no ticks and no cue.

## G. Numbers

One format per unit (decimals and suffix from the vocabulary); a minus is "−"; zero is never signed; intervals are
"[lo, hi]" at the value's precision; counts are "k of n". Every printed number has a data key, and one key prints one
string across a figure set.

## H. Targets

A target fixes width, dpi, fonts, minimum text size and whether a title and caption are drawn:

| target | size | dpi | title, caption | checks |
|---|---|---:|---|---|
| post | 8.0 in wide, width : height 1.0–2.6 (cards only: as short as their text) | 200 | no | strict |
| slide | 12.3 × 6.5 in (a 7.5 in slide minus a one-line title) | 200 | no | strict; a figure that does not fit is split across slides |
| readme | 11 in wide, width : height 1.0–3.0 | 160 | yes | strict |
| notebook | 8.0 in wide | 100 | no | relaxed, never published |

Projects change these or add targets in `[targets.<name>]`.

## I. The key figure

`sp.key_figure(vocab, example=..., read_aloud=...)` (or `styles-plot key --vocab plotstyle.toml` without the example)
draws the project's grammar on one image: each role's colour with its word and meaning, the controls' grey, the hollow
mark and the whisker (in ink: grey means control), the grey tick, the grey band, the missing-cell words, and one
example row from the data read aloud. Its marks' phrases are the key, so no key line repeats under it.

## The checks

| codes | rule |
|---|---|
| SP101–SP104 | colour by role; one meaning per colour; every drawn role named by its word |
| SP201–SP204 | hollow ↔ post hoc; grey tag ↔ claim; every drawn cell in the registry; every data mark has a cell |
| SP301–SP305 | key complete both ways; no legend box; every grey mark names its control; one grey-band meaning per figure |
| SP401–SP407 | words from the vocabulary; banned variants; ids; cues; axis titles |
| SP501–SP502 | numbers through formatters; one key, one string |
| SP601–SP612 | text crossing lines or marks, off the figure, too small, overlapping, rotated; size; titles; markers |
| SP613 | a column header that wraps past the target's `max_header_lines` (a warning until 0.3) |
| SP700–SP704 | colour-vision floors; direct labels |
| SP801–SP804 | the saved PNG: width, proportions, background, hues on the palette |
| SP901–SP904 | `styles-plot check`: unknown target, stale sidecar, unpublished target, registry changed since drawing |
| SP905 | a waiver that matches nothing (stale) |
| SP906 | `styles-plot check`: a PNG without a sidecar, so only its pixels are checked (a warning until 0.3) |

Text placement (SP601, SP606, SP610, SP613) may be waived per figure by the text at fault, with a reason
(`sp.Waive`); no meaning check can be. Strict mode (the default) refuses to write a figure with any problem. Compat mode writes it, warns, and records the
problems in its sidecar, for migrating old scripts.
