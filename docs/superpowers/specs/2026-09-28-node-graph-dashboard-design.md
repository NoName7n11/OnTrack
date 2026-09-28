# Node-graph dashboard rework

## Context

`dashboard.html` today is a single-column document: level intake → placement
questions → optional questions → a flat text learning path grouped by domain.
All client-side, fetches `inventory.json` + `questions.json` + `personal.json`,
POSTs to `/level` and `/answer`. No build step, no dependency.

This replaces the post-intake view with a 3-panel layout per the user's sketch:

```
+-----------------------------------+------+
|                                   |      |
|           Node_Graph              | Tools|
|                                   |      |
+-----------------------------------+      |
|           Questions               |      |
+-----------------------------------+------+
```

Level intake (the "Set your level" first-run screen) is unchanged — this
rework applies once `personal.level` is set.

A Figma reference now exists for this layout:
https://www.figma.com/design/cAfSVmxMUZJebm4Nkalf4X/Principles?node-id=63-25&m=dev
(node `63:25`, "Desktop - 3"). It supersedes the ASCII sketch above for visual
detail — dark theme, specific palette, and a few elements not in the original
sketch (a stat bar, a persistent node-detail card, grouped tools with version/
detection status). See the companion agent prompt
(`2026-09-28-node-graph-dashboard-agent-prompt.md`) for the literal spec pulled
from that reference; this section states the intent, that file states the
pixels.

## Goals

- Node_Graph: every confirmed/inferred inventory item (except `kind:"tool"`)
  as a draggable node. Edge = provenance (`item.from`, concept → its source
  library/language). Node color/state = the user's confidence in that topic,
  derived the same way the existing learning path already derives it
  (`stateOf(q)` → `unanswered`/`learn`/`review`/`learned`). Nodes also show
  `where` (file paths) on hover/click, so "where this is used in the codebase"
  is visible.
- Questions: today's placement + optional question cards, unchanged in
  behavior, moved into the bottom-left panel.
- Tools: right rail listing `kind:"tool"` inventory items (Docker, Make, etc.)
  as a simple list — no graph, no confidence coloring, since "how confident
  are you in Docker" isn't the model's job here (may grow scope later, out of
  scope for this rework).
- Learning path panel is removed from this view — replaced by the graph, which
  the node coloring is meant to make redundant (grey/red nodes ARE the gaps).

## Non-goals

- No server/build changes. `inventory.json`/`questions.json`/`personal.json`
  shapes are unchanged; `build.py` output already carries everything needed
  (`id`, `kind`, `domain`, `confidence`, `where`, `from`).
- No new dependency. Force layout + drag hand-rolled in SVG/JS, matching the
  project's existing zero-dependency single-file HTML approach.
- Not building real physics/clustering sophistication — a small, good-enough
  force simulation (repulsion + spring edges + center pull), not a tuned
  layout engine.
- Tools rail is a richer grouped list per the Figma reference (category
  headers, version/detection-status), but still read-only display — no new
  server endpoints, no actual tool invocation from the dashboard.

## Data flow (unchanged inputs, new derivation)

For each item in `inventory.items` where `item.kind !== "tool"`:

- **node.id** = `item.id`
- **node.label** = `item.name || item.id`
- **node.state** = `q = qByConcept[item.id]; q ? stateOf(q) : "untested"` —
  reuses the existing `stateOf` function verbatim.
- **node.where** = `item.where` (array of file paths), shown on click/hover.
- **node.kind** = `item.kind` (`library`/`language`/`concept`/...) — used for
  a secondary visual distinction (e.g. shape or border style) so languages
  read differently from concepts at a glance, but confidence color is
  primary.

For each item with a non-empty `item.from` (provenance array of
`{type, name}`), draw one edge from the node matching that
`(type, name)` pair (look up via a `{type,name} -> item.id` index built once
per render) to `item.id`. Items with no resolvable `from` target are roots
(no incoming edge) — this includes top-level deps/languages, which have no
`from` today.

Color mapping (reuses existing state semantics, new node-specific palette):
- `learned` → accent green (matches existing "knew it" meaning)
- `learn` → red/warm (confirmed gap)
- `review` → amber (self-reported shaky)
- `untested` / `unanswered` → grey (no signal yet)

## Layout & rendering

- CSS grid: two rows in the left column (Node_Graph ~65% height, Questions
  ~35%), Tools as a fixed-width right column spanning both rows. Responsive
  collapse (stack vertically) below ~900px, matching the existing mobile-first
  posture of the current page (it's currently a centered 860px column, so this
  is a new breakpoint concern to add).
- Node_Graph is an `<svg>` sized to its panel. A simple force simulation runs
  on a `requestAnimationFrame` loop:
  - Repulsion between all node pairs (inverse-square, capped).
  - Spring attraction along edges (toward a rest length).
  - Weak pull toward panel center (keeps the graph from drifting off-screen).
  - Simulation runs continuously at low velocity damping (not "settle once and
    stop") since it's cheap at expected node counts (tens, not thousands) —
    ponytail: no adaptive sleep/wake, add if a real project's inventory makes
    this visibly expensive.
- Drag: pointer-down on a node pins it to the pointer (fixed x/y, excluded
  from simulation forces while held); pointer-up releases it back into the
  simulation. No persistence of dragged positions across reloads — session
  only.
- Click a node → a persistent node-detail card (not a transient tooltip, per
  the Figma reference) showing `what`, `where`, dep/use counts, `search` link,
  and quick state-mark buttons.

**Important data caveat**: the Figma reference's node-detail card shows a
"Deps"/"Uses" count pair and Learned/Review quick-mark buttons — these do not
map to any field OnTrack's inventory currently carries (no dependency-count or
manual-override-state concept exists in `inventory.json`/`personal.json`
today). The agent prompt below marks these as adapt-or-drop: reachable
extensions are fine, but they must not block shipping the rest of the graph,
and any answer-writing "quick mark" button must still go through the existing
`/answer` POST contract, not a new ad-hoc state.

## Questions panel

Straight move of the existing placement + optional question rendering
(`questionCard`, the unanswered/placement/optional split, `submitAnswer`) into
the bottom-left panel. No behavior change. Answering a question triggers a
graph re-render so the answered node's color updates immediately — this is
the "better result reflection" the user asked for: the score/state change is
now visible on the graph itself rather than only in a path list.

## Tools panel

Right rail, `inventory.items.filter(i => i.kind === "tool")`, grouped by a
category derived from the item (see agent prompt for the exact grouping rule,
since `inventory.json` has no category field today — this is a display-layer
grouping, not a new data field). Each row shows name + `where`, matching the
Figma reference's row shape minus the fields OnTrack has no data for (version,
live detection status) — see the agent prompt's adapt-or-drop note. Empty
state: "No tooling detected yet" if the list is empty.

## Testing

No Python-side changes, so no new automated test in `test_build.py`/
`test_track.py`. Manual verification (dashboard has no existing JS test
harness — consistent with current project state):
1. Load a project with confirmed deps/languages/tools/concepts + a mix of
   answered/unanswered questions; confirm node colors match `stateOf` for
   answered ones and grey for unanswered.
2. Confirm `kind:"tool"` items appear ONLY in the Tools rail, never as graph
   nodes.
3. Drag a node, release, confirm it rejoins the simulation instead of
   staying stuck off-layout.
4. Answer a question in the Questions panel, confirm the matching graph node
   recolors without a full page reload.
5. Resize below the mobile breakpoint, confirm the 3 panels stack instead of
   overlapping/clipping.
