# styles-plot: design

The living design document: how the library is built and why. The rules a figure follows are in
[GRAMMAR.md](GRAMMAR.md), their use in [ADOPTING.md](ADOPTING.md), each release's changes in
[../CHANGELOG.md](../CHANGELOG.md). The stage-1 design of 0.1 (the audit of the first two projects, the draft
vocabularies, the decisions of 7 Nov) is kept as history in [archive/DESIGN-stage-1.md](archive/DESIGN-stage-1.md).

# Proposed changes

Status: for review, no code yet. Base: `main` at 0.1.14 (`c65a96e`). Every 0.1.14 call keeps working and draws the same
pixels; no meaning check (SP1xx–SP5xx, SP7xx, SP8xx) is relaxed. New public names are marked *experimental* where the
brief asks (B1); they may change in a minor release.

## A. Failures that explain themselves

**A1.** `Problem(code, message, figure="", subject="", where=None, bbox_in=None, obstacle_in=None, fix="")`, frozen;
`where` is a dict `{target, block, row, column}` (keys present when known), `bbox_in`/`obstacle_in` are
`(x0, y0, x1, y1)` in inches from the figure's bottom-left. `str()` appends `→ <fix>`. The layout check already holds
both boxes in pixels; for an obstacle inside a dot-table or sweep panel it maps them through that panel's
`transData.inverted()` and proposes the smallest change that clears it: crossing the right/left spine → `xlim upper ≥ v`
(lower ≤ v), or the `weight` (C4) that gives the label room; touching a mark or a vertical line → move the range by the
overlap, or waive (A3). SP401 → the exact TOML line under `[terms]`; SP203 → `fig,cell,<timing>,<claim>,,,` (never a
filled-in status); SP609/SP613 → the width needed and "shorten the header, or move the qualifier into the unit title".
`styles-plot check --json`: one object per problem (`dataclasses.asdict`).

**A2.** `sp.debug(fig, target="post", out=".") -> list[Problem]` writes `<out>/_debug/<id>.<target>.png`: the figure,
each subject and obstacle boxed in red, the code beside it; no sidecar. `check`, `sheet` and `build` skip any folder
starting with `_` (they already skip `_meta`, `_sheets`). `StyleError`'s message ends with
`sp.debug(fig, "<target>")`.

**A3.** `sp.Waive(code, text, reason)`; `Figure(..., waive=[...])`. Waivable: **SP601, SP606, SP610, SP613** — text
placement only. Any other code raises `BuildError("SP603 cannot be waived")` when the Figure is made; SP609/SP611 stay
non-waivable (those words tie a colour or a line to its name). A waiver matches a problem when the codes are equal and
`text` equals the subject's **whole** text (a wrapped header or tag is matched by its full text; for SP606, either of
the two texts). A waiver that matches nothing in the render is **SP905 stale waiver**, an error at once (E1: it cannot
fail an old figure). The sidecar gains `waived: [{code, subject, reason}]`; `check` prints `N waived`. Built: the
waiver is checked when made (`Waive.__post_init__`), and takes `targets=()` (all): a placement is usually tight on
one target only, and without it a waiver needed on readme would be stale on post. SP606 keeps its second text in
`where["other"]`. On a target without layout checks (notebook) no waiver is stale.

## B. Projects extend the library (experimental)

A block is any object with `plan(ctx: sp.BlockContext, width: float) -> sp.Plan`; the nine built-ins keep their
internal planners. `sp.BlockContext` is a read-only view: `vocab`, `target` (the Theme), `label_width`,
`measure(text, size, weight)`, `wrap(...)`, `unit(name)`, `role(name)`, `status(cell)`. `sp.Plan(height, draw,
encodings=None)`. `sp.Canvas` (inches from the block's top-left, as today) adds meaning primitives that tag exactly as
the built-ins do: `word(x, y, text, role=None, size="value")`, `number(x, y, value, unit, key, role=None)`,
`panel(x, y, w, h, unit, xlim=None, xticks=None) -> Panel` (the library's axis title and cue), and on a `Panel`:
`dot(y, est, role, control=None)` (hollow from the registry, whisker from `est`), `tick(x, y)`, `rule(x, label="")`,
`band(lo, hi, name="")`, `connector(a, b, y)`. `sp.Custom(height, draw)` wraps the common case.

**How the key stays right.** When a plan has `encodings=None` (always for `Custom`), the renderer runs `draw` once on a
throwaway Agg figure of the block's size and reads the encodings from the tagged artists with the *same* function SP301
and SP302 use (`drawn_encodings`). The key and its check therefore share one definition of "drawn", a project never lists
encodings by hand, and drift is impossible rather than merely caught. Cost: one extra draw of that block (milliseconds).
Raw matplotlib inside `draw` is checked like everything else (SP103, SP401, SP501). Built as proposed, plus: `Panel.x(value)`
(a data value in inches, to place a word at it), `BlockContext.line_height`, `axis_height` and `figure_id`; a project
block's words are kind `word` (a role word when coloured); a figure with a project block never takes the "all
estimates post hoc" shortcut, since its cells are known only once it draws; one `Plan` class serves both sides.

## C. Less ceremony

**C1.** A row `*,cell,…` applies to `cell` in every figure. An exact `(figure, cell)` row may override `claim` and
`claim_reason` only; a different `timing` for the same cell is a `RegistryError` naming both lines. `Registry.get`
returns the resolved status everywhere (status checks, SP904, sidecar). Two `*` rows for one cell are duplicates.

**C2.** `Series(role, cells, control=None, word=None, *, cell=None, key=None, label=None, interval=None)`. `cells` is a
mapping or a callable `row -> value` (`(row, lane) -> value` with lanes), called for each row of the table. Coercion: a
number → `Est(v)`; `(v, lo, hi)` → `Est(v, lo, hi)`; a mapping with `value`/`lo`/`hi` → `Est`; `Est`/`Missing` as is;
`None` → `BuildError` naming the row. Templates `{row}`, `{id}` (entity id, else key), `{lane}`, `{role}` fill `cell`
and `key` of coerced values and of an `Est` whose own field is `None`; an `Est`'s own value always wins. Applies to
**`Series.cells`, `TextColumn.cells` (same keyword defaults) and `Segment.shares`**; not to `Sweep`, `Distribution` or
`Scatter`, whose data are arrays, not cells. Built: bindings are resolved once per render (`_bind.resolve`) into the plain
mappings the planners always saw, so nothing downstream changed; `Est(label=True)` keeps its check when made, so a
hand-made labelled `Est` carries its own `key` (a template fills only what an `Est` leaves `None`).

**C3.** `DotColumn(header, unit, xlim=None, xticks=None, series=(), ...)`: positional calls keep working; empty `series`
is a `BuildError` at plan time. Resolution: the column's own value → `[units.<name>] lim = [lo, hi]`, `ticks = [...]` →
computed from values, intervals, grey ticks, band and rules with `_grid.padded`/`_grid.ticks`, widened on the right so
the outermost value label clears the spine (the label width is known once the column width is). Built with two changes: the ends snap out to a quarter of a tick step (not to a tick),
and computed ticks stay a quarter step inside the ends, as many as the panel's width holds: a tick label on a panel's
edge met the next panel's in the examples.

**C4.** `DotColumn(weight=1.0)`; `width=` and a non-default `weight` together raise `BuildError`.
`Theme.max_header_lines = 2`; a longer header is **SP613** (with the weight that would fit it), a warning in 0.2 (E1).

**C5.** `save`/`save_bundle`/`build` write `<out>/_meta/problems.json` (`{figure: {target: [problem, ...]}}`, empty
lists when clean, strict failures included). `styles-plot todo <out>` groups: words to add (TOML), cells to register (CSV
stubs with placeholders), the rest with fixes. `--write-vocab [FILE]` (default `plotstyle.added.toml`) appends missing
words with a dated comment, refuses banned words, prints the `[include]` line if missing, never touches the registry.
**Include merge rule:** `[include] files = [...]` relative to the including file, one level deep. The list-valued
`[terms]` keys (`canonical`, `templates`, `missing`, `not_claimed`, `banned`) concatenate in file order (base first),
dropping exact repeats. Every other key is defined once: the same key (a role, a unit, an entity kind, a `[key]` field,
a palette slot, …) in two files is a `VocabError` naming both files. `styles-plot vocab lint` reports near-duplicate
canonical terms (case, plural -s, hyphen/space, edit distance ≤ 2 on words of 6+ letters); report only.

**C6.** `sp.FigureSet(name, vocab, out, targets=("post",), mode="strict")` and
`@SET.figure(id, order=None, title="", caption="", targets=None)` (the decorated function receives a ready `Figure`).
`styles-plot build module:SET [--only GLOB] [--target T] [--jobs N] [--mode M]`: a `ProcessPoolExecutor` with the
`spawn` context; each worker imports the module and builds the ids it is given (nothing pickled but ids and problem
dicts); each figure is all its targets or nothing; `<out>/_meta/index.json` lists id, order, title, caption, targets,
PNG paths, problems, waivers; a failing figure does not stop the others; exit 1 if any failed. No cache. Built: a builder may also
return a Figure of the same id (projects with whole-figure functions register them as they are); `**figure` passes
the other Figure keywords (subtitle, read, waive); `jobs=1` builds in the calling process; the parent alone writes
`index.json` and `problems.json`, so workers never race on them.

**C7.** `Figure._repr_png_()` (notebook target) and `fig.preview(target="post") -> Preview` with `_repr_html_` (the PNG,
with the A2 overlay when there are problems, and the problem list). Nothing is written to disk. Built as proposed; `sp.Preview` also has `_repr_png_`.

## E. Release discipline

**E1.** `_checks/__init__.py` keeps `ERROR_FROM = {"SP613": "0.3"}`: a listed code is a `StyleWarning` (figure written,
problem in the sidecar and `check`) until that version. New features' own checks (SP905) are errors at once. The
module docstring and the CHANGELOG header state the policy. **E2.** ADOPTING.md: install editable from a local checkout
while project and library change together; pin the tag again before the project branch is merged.

## What I would do differently, and why

1. `Problem.obstacle_in` is added beside `bbox_in`: A2 boxes both, and a fix for "touches a mark" needs the mark's box.
2. B1: `encodings=None` triggers the dry run for **any** public block, not only `Custom`, so no public block ever
   declares encodings by hand.
3. A3: waivers match the subject's full text rather than the wrapped line; an exact line match would break when a
   target rewraps the text.
4. C3: the computed range is snapped to the unit's ticks after padding, so two panels on one unit computed from
   similar data share a range rather than differing by a few hundredths.
5. Two process questions: (a) the pilot (step 3) edits bridge-jspace's `danorel` branch, which another session works
   in; I propose to run it in my own clone of that branch, push nothing there, and report the numbers (or hand it to the
   bridge session with my branch installed editable); (b) CI runs only on pushed commits: may I push the styles-plot
   `danorel` branch (not `main`, no tag) so each item is tested on the full matrix?
