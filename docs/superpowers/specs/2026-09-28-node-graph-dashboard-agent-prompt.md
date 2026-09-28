# Agent prompt: OnTrack node-graph dashboard

Paste this whole file as the task prompt for the agent that will build the UI.

---

## What you're building

You are reworking a single HTML file, `ontrack/skills/ontrack/dashboard.html`,
from its current single-column document layout into a 3-panel app layout.
Read the entire existing file first — it is self-contained (inline `<style>`
and `<script>`, no build step, no external dependency), and you must preserve
that property. Do not add npm, a bundler, or any external script/stylesheet
beyond what's already loaded (currently none).

The file currently renders, in order: a "set your level" intake screen, then
(once a level is set) a derived-level banner, placement questions, optional
questions, and a flat text "learning path" grouped by domain. It fetches three
static JSON files at load (`/inventory.json`, `/questions.json`,
`/personal.json`) and POSTs to `/level` and `/answer` when the user interacts.
**None of that data-fetching, POST, or state-derivation logic changes.** You
are replacing how the already-loaded data is *laid out and rendered* after a
level is set — not touching the server, not touching the JSON shapes, not
touching the intake screen.

## Target layout

Once `personal.level` is set, replace everything below the level banner with
a 3-panel layout:

```
+-----------------------------------+------+
|                                   |      |
|           NODE GRAPH              | TOOLS|
|        (big, top-left)            | rail |
|                                   |      |
+-----------------------------------+      |
|           QUESTIONS               |      |
|        (bottom-left)              |      |
+-----------------------------------+------+
```

- Left column ≈ 65% height Node Graph / 35% height Questions, stacked.
- Right column: a fixed-width Tools rail spanning the full height of both.
- Below ~900px viewport width: stack all three panels vertically in the order
  Node Graph → Questions → Tools (graph stays visually primary).
- Keep the existing derived-level banner above this 3-panel block; keep the
  page header (`<h1>OnTrack</h1>` + subtitle) as-is.
- Match the existing visual system: reuse the CSS custom properties already
  defined at the top of the file (`--paper`, `--ink`, `--accent`, `--line`,
  etc., including their light/dark-mode variants) rather than inventing a new
  palette. New panel chrome (borders, radius, spacing) should look like a
  sibling of the existing `.intake`, `.qcard`, `.levelbar` boxes, not a
  visually distinct sub-app.

## Panel 1: Node Graph

**Purpose**: show every topic the project is built on as a node, and let the
user see at a glance what they're confident in, what's a gap, and where in
the codebase that topic shows up.

**Data**: for every item in `inventory.items` where `item.kind !== "tool"`,
create one node:

- `id` = `item.id`
- `label` = `item.name || item.id`
- `kind` = `item.kind` (values seen: `"library"`, `"language"`, `"tool"`
  (excluded here), `"concept"`) — give concepts and library/language nodes a
  distinct look (e.g. shape, border style, or size), but confidence color
  (below) is the dominant visual signal, not kind.
- `where` = `item.where` (array of file path strings) — show this on
  hover/click, not as permanent on-node text (it'll get crowded).
- `what` = `item.what` (one-line description) and `search` = `item.search`
  (a search query string) — also shown on click, same as `where`.
- `state` — compute using the **existing `stateOf(q)` function already
  defined in this file, unmodified**: look up `q = qByConcept[item.id]`; if
  `q` exists, `state = stateOf(q)` (returns `"learned"`, `"learn"`, or
  `"review"`); if no question exists for this item, `state = "untested"`.

**Edges**: for every item with a non-empty `item.from` array (each entry
shaped `{type, name}` — this is the inventory's provenance field, pointing at
the dependency/language observation a concept came from), draw one directed
edge from the inventory item matching that `(type, name)` pair to this item.
Build a `{type,name} -> item.id` lookup once per render to resolve these.
Items with no resolvable `from` (most top-level libraries/languages today
have none) are graph roots — draw them with no incoming edge, don't invent
one.

**Node coloring** (reuse the project's existing CSS variables where the
meaning already matches; these map to states already used elsewhere in this
file for `learn`/`review`/`learned`):

| state | meaning | look |
|---|---|---|
| `learned` | user answered correctly / self-reported confident | `--accent` (green) |
| `learn` | confirmed gap (answered wrong) | a warm/red tone — pick one consistent with the existing palette's contrast in both light and dark mode |
| `review` | self-reported shaky | `--somewhat` (amber, already defined) |
| `untested` | no question yet, or unanswered | `--faint` / grey, visually receding |

**Interaction**:
- Drag: pointer-down on a node picks it up and pins it to the pointer
  position; pointer-up releases it back into the simulation (see below). No
  position persistence needed across page reloads — session-only is fine.
- Click (or hover, your choice — pick whichever reads cleaner) a node: show
  its `what`, `where` (joined, or listed), and a search link
  (`https://www.youtube.com/results?search_query=` + URL-encoded `search`, the
  existing `ytLink()` helper already does this — reuse it) in a small
  tooltip/inline panel. Don't navigate away or replace the whole graph view.

**Rendering approach**: render as an inline `<svg>` sized to fill its panel.
Implement a small force-directed layout yourself — no charting/graph library,
no new script tag. The simulation needs only three forces, on a
`requestAnimationFrame` loop:
1. **Repulsion** between every pair of nodes (inverse-square falloff, capped
   so very close nodes don't fling apart violently).
2. **Spring attraction** along each edge, pulling connected nodes toward a
   consistent rest length.
3. **Center pull** — a weak force pulling every un-pinned node toward the
   panel's center, so the graph doesn't drift off-screen over time.

Run the simulation continuously with velocity damping (it doesn't need to
"finish" and stop — it's cheap at the node counts this tool will see, tens
not thousands). Dragged nodes are excluded from all three forces while held
(fixed position), then rejoin normally on release.

**Empty state**: if there are zero eligible nodes (fresh project, nothing
scanned yet), show a plain message in the panel instead of an empty `<svg>` —
match the tone of this file's other empty states (e.g. the existing `.empty`
class / "No questions yet. Run /ontrack..." message pattern).

## Panel 2: Questions

This is a straight relocation, not a rewrite. The existing placement-question
and optional-question rendering (the functions/logic already producing
`.qcard` elements, the placement/optional split, the "Save answer" / "Skip"
buttons, `submitAnswer()`) moves into this bottom-left panel with **no
behavior change**. Keep the section headers ("Place your level", "Sharpen the
path (optional)") and their lead copy as they are today.

**The one required change**: after a successful `submitAnswer()` call (i.e.
after `personal.answers` updates), the Node Graph panel must re-render so the
just-answered concept's node recolors immediately, without a full page
reload. This is the main "make results feel reflected" improvement — today
answering a question only updates a text list further down the page; now it
should visibly recolor the graph.

## Panel 3: Tools

Right rail. List every item in `inventory.items` where `item.kind === "tool"`
(these are `Dockerfile`, `Makefile`, `Procfile`, etc. — non-code tooling,
deliberately excluded from the graph since "confidence in Docker" isn't a
quiz-driven concept the way a library or language concept is). For each:
show its name and `where` (file path it was found at), plus a search link
using the same `ytLink()` pattern as the graph tooltip and the old path
steps. No confidence coloring, no drag, no graph — just a clean list, visually
consistent with the rest of the page (reuse existing list/card styling
patterns rather than inventing new ones).

**Empty state**: if there are no `kind:"tool"` items, show "No tooling
detected yet" in the rail instead of an empty box.

## What must NOT change

- `/inventory.json`, `/questions.json`, `/personal.json` fetch calls and their
  shapes — read-only inputs, already correct.
- `/level` and `/answer` POST behavior (`setLevel`, `submitAnswer`,
  `postJSON`) — reuse verbatim.
- `stateOf()`, `derivedLevel()`, `ytLink()`, `el()` helper functions — reuse
  verbatim, don't reimplement.
- The level-intake screen (before a level is set) — completely unchanged.
- The derived-level banner — stays, unchanged, above the 3-panel layout.
- No new external dependency of any kind (no CDN script, no npm package, no
  iframe to another tool). Everything ships inline in this one HTML file, as
  it does today.
- The flat "learning path" text view this replaces can be deleted — the graph
  is its replacement. Don't keep both.

## Verification before you consider this done

Manually check, in a real browser (there is no JS test harness in this
project today, so this is the actual bar):

1. A project with a mix of confirmed deps, languages, tools, and concepts,
   plus a mix of answered/unanswered questions — confirm node colors match
   `stateOf()`'s result for answered concepts, and grey for unanswered/no
   question.
2. `kind:"tool"` items appear ONLY in the Tools rail — never as a graph node.
3. Drag a node away, release it, confirm it settles back into the simulation
   instead of staying frozen wherever it was dropped.
4. Answer a question in the Questions panel and confirm the matching graph
   node's color updates immediately, without reloading the page.
5. Resize the window below ~900px and confirm the three panels stack
   vertically and remain usable (no clipped/overlapping content) instead of
   the fixed 3-panel grid.
6. Toggle (or simulate) light/dark mode and confirm all new colors — node
   states, panel borders, tooltip — remain legible in both, using the
   existing `--*` custom properties rather than hardcoded hex values.
