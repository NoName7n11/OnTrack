# Agent prompt: OnTrack node-graph dashboard

Paste this whole file as the task prompt for the agent that will build the UI.

---

## What you're building

You are reworking a single HTML file, `ontrack/skills/ontrack/dashboard.html`,
from its current single-column document layout into a 3-panel dark-theme app
layout. Read the entire existing file first — it is self-contained (inline
`<style>` and `<script>`, no build step, no external dependency), and you
must preserve that property. Do not add npm, a bundler, or any external
script/stylesheet beyond what's already loaded (currently none).

The file currently renders, in order: a "set your level" intake screen, then
(once a level is set) a derived-level banner, placement questions, optional
questions, and a flat text "learning path" grouped by domain. It fetches three
static JSON files at load (`/inventory.json`, `/questions.json`,
`/personal.json`) and POSTs to `/level` and `/answer` when the user interacts.
**None of that data-fetching, POST, or state-derivation logic changes.** You
are replacing how the already-loaded data is *laid out and rendered* after a
level is set — not touching the server, not touching the JSON shapes, not
touching the intake screen.

## Visual reference

A Figma frame shows the target layout, palette, and component shapes:
https://www.figma.com/design/cAfSVmxMUZJebm4Nkalf4X/Principles?node-id=63-25&m=dev
(node `63:25`, "Desktop - 3"). If you have Figma access, pull this node for
exact spacing/type/color values. If you don't, use the description below —
it was written directly from that reference, including exact hex colors.

**Read the "Data availability" section near the end before implementing the
node-detail card and tools rows** — the reference includes a few fields
OnTrack's data does not currently carry. Do not block on those; the note
tells you exactly what to adapt or drop.

## Target layout

Once `personal.level` is set, replace the level banner + flat learning path
with this structure, top to bottom:

1. **Header row** (already exists — keep it, it's the page `<header>`).
2. **Derived-level stat bar** — a full-width strip directly below the header,
   background `#1c2b3a`, 2px bottom border `#236ca1` (or your existing
   `--accent`/`--line` equivalents — see "Color mapping" below for how to
   fold this into the existing CSS variables rather than hardcoding), height
   ~44px. Contents, left to right:
   - A small pill: `#236ca1` background, "DERIVED LEVEL" label, uppercase,
     11px, with a small CPU-like icon (reuse an inline SVG or drop the icon
     if you don't want to source one — it's decoration, not required).
   - The derived-level text (existing `derivedLevel()` output: level name +
     `why` string), styled roughly `#93c5fd` / 13px.
   - Four small count badges, each a colored dot + label + number: "Learned"
     (`#10b981` dot), "Learn" (`#3b82f6` dot — note: in the Figma reference
     the "Learn" dot is blue, not the warm/red this project's dashboard.html
     otherwise uses for a "gap" state elsewhere; follow the reference's blue
     here since this bar is describing counts, not individual node color —
     see the Color mapping section for where red actually is used), "Review"
     (`#f59e0b` dot), "Untested" (`#4b5563` dot). Compute each count by
     running every inventory item (minus `kind:"tool"`) through the same
     state derivation used for graph nodes (see below) and tallying.
   - A "Recalculate" button, right-aligned, `#236ca1` background, small
     refresh icon + label. **This button re-runs the existing
     `derivedLevel()`/render pipeline client-side — it does not need a new
     server endpoint.** Wire it to just call your render function again;
     it's a manual refresh affordance, not new logic.
3. **Node Graph panel** — big, left, ~668px tall in the reference at 1440px
   width (i.e. roughly 60-65% of the remaining vertical space above the
   Questions panel — don't hardcode 668px, make it proportional to viewport).
4. **Questions panel** — full width of the left column, below the graph,
   ~280px tall in the reference, but should grow/scroll if there are many
   questions rather than clipping.
5. **Tools panel** — right rail, fixed width ~300px, spanning the full height
   of both the Node Graph and Questions panels combined.

Below ~900px viewport width: stack Node Graph → Questions → Tools vertically
instead of the 3-panel grid.

## Color system

The reference is a dark theme with these literal colors:

| role | hex |
|---|---|
| page background | `#1a1a1a` |
| graph panel background | `#171717` (slightly darker well inside the panel) |
| panel/card background | `#1e1e1e` / `#1e2530` (header-ish surfaces) |
| primary accent (borders, active pills, buttons) | `#236ca1` |
| accent-soft text | `#93c5fd` / `#60a5fa` |
| border/line | `#333` / `#2d3748` / `#374151` |
| muted text | `#9ca3af` / `#6b7280` |
| bright text | `#f9fafb` / `#d1d5db` / white |
| state: learned | `#10b981` (green) |
| state: learn (gap) | `#3b82f6` (blue) in the stat-bar dot, but the actual
  graph NODE color for a "learn" (confirmed-wrong) state should stay
  consistent with a warm/red tone if this project's existing dashboard.html
  already uses one elsewhere for that meaning — check `--somewhat` and any
  existing gap-styling in the current file before deciding; don't introduce
  a second, conflicting color for the same state. |
| state: review | `#f59e0b` (amber) |
| state: untested | `#4b5563` (grey) |
| destructive/CTA (YouTube button) | `#dc2626` |
| secondary accent (used for the "optional questions" section marker) | `#8b5cf6` |

This project's existing `dashboard.html` already has a CSS variable system
(`--paper`, `--ink`, `--accent`, `--line`, etc.) with light AND dark mode
support via `prefers-color-scheme` and a `data-theme` override. **Decide
explicitly, and say so in your output, whether this rework:**
(a) keeps that light/dark toggle and adapts these reference colors into new
dark-mode variable values (extending, not replacing, the existing system), or
(b) makes this specific view permanently dark (matching the reference
exactly) regardless of the site's light/dark toggle.
Given the reference is clearly designed dark-only with no light variant
shown, **(b) is the reasonable default** — treat the graph dashboard as a
dark-only view — but flag this choice explicitly rather than silently
dropping the existing light-mode support for the whole page.

## Node Graph panel — detail

**Data**: for every item in `inventory.items` where `item.kind !== "tool"`,
create one node:

- `id` = `item.id`
- `label` = `item.name || item.id`
- `kind` = `item.kind` (`"library"`, `"language"`, `"concept"`) — the
  reference distinguishes "Library / Lang" nodes from "Concept" nodes via a
  small filled-vs-outlined circle in the legend (see Legend below); apply a
  matching visual distinction (e.g. solid fill vs. a ring) rather than
  inventing a third shape system.
- `where` = `item.where` (array of file paths).
- `what` = `item.what`, `search` = `item.search`.
- `state` — reuse the **existing `stateOf(q)` function verbatim**: look up
  `q = qByConcept[item.id]`; if `q` exists, `state = stateOf(q)`; else
  `state = "untested"`.

**Node sizing**: the reference varies node diameter (60-96px) seemingly by
importance/centrality (TypeScript and React, the most-connected nodes, are
largest). Don't try to reverse-engineer a precise formula — a reasonable
proxy is edge count (nodes with more connections render larger, within a
capped min/max range), or you may keep uniform sizing if the extra
complexity isn't worth it for now. This is a nice-to-have, not a hard
requirement.

**Node glow/shadow**: filled nodes in the reference have a colored
`drop-shadow` matching their state color (e.g. green nodes glow green). The
currently-selected/detail node gets a stronger ring + glow (see TypeScript
node in the screenshot — blue ring + larger glow). Reasonable CSS: `filter:
drop-shadow(0 0 8px <state-color-at-40%-alpha>)`.

**Edges**: for every item with a non-empty `item.from` array (each entry
`{type, name}`, pointing at the dependency/language observation a concept
came from), draw one line from the resolved source node to this item. Build
a `{type,name} -> item.id` lookup once per render. Items with no resolvable
`from` are roots (most top-level libraries/languages today) — no incoming
edge. In the reference, edges are thin (~1px), colored to match roughly the
color of one of their endpoint nodes at ~33% opacity — a reasonable
implementation is edge color = the source node's state color at low opacity.

**Rendering**: inline `<svg>` filling the panel. Hand-rolled force simulation
on `requestAnimationFrame` — repulsion between all node pairs, spring
attraction along edges toward a rest length, weak center-pull. Run
continuously with damping (cheap at expected node counts — tens, not
thousands). No graph library, no new dependency.

**Drag**: pointer-down on a node pins it to the pointer; pointer-up releases
it back into the simulation. No cross-reload persistence needed.

**Background**: the reference has a subtle grid-texture overlay at 30%
opacity behind the nodes (`GridOverlay` in the extracted markup). This is
purely decorative — implement with a repeating CSS `background-image`
(e.g. a faint linear-gradient grid pattern) rather than sourcing/hosting an
image asset. Skip it entirely if it adds meaningfully complexity for no
functional value; it's polish, not structure.

**Graph legend**: a small fixed box, top-left inside the graph panel,
semi-transparent dark background (`rgba(30,30,30,0.8)`), bordered `#333`,
listing: a "CONFIDENCE" label + the 4 state colors with labels (Learned/
Learn/Review/Untested), a divider line, then "Library / Lang" and "Concept"
each with their node-shape indicator (see Node sizing/shape above).

**Graph zoom controls**: a small fixed cluster, bottom-right inside the graph
panel — `+` button, `−` button, and a fullscreen/maximize icon button, each a
~28px square dark button. Wire `+`/`−` to a simple SVG viewBox zoom (scale
the viewBox); wire the maximize button to a CSS fullscreen toggle on the
panel, or drop it if fullscreen isn't worth the complexity here — it's a
minor affordance, not core to the feature.

**Node detail card**: clicking a node opens a persistent card (not a
transient tooltip — it stays open until another node is clicked or it's
explicitly closed), positioned top-right inside the graph panel, ~244px
wide, bordered `#236ca1`. Contents, top to bottom:
- Header bar (`#236ca1` background): a dot in the node's state color + the
  node's label (bold), and a small state badge pill on the right (e.g.
  "LEARN" in uppercase, semi-transparent white background).
- Body (`#1e2530` background):
  - The item's `what` description text.
  - "RELATED FILES" label + a list of `item.where` entries, each a small row
    with a file icon + the path (truncate with ellipsis if long).
  - Two small stat tiles side by side ("Deps" / "Uses" in the reference) —
    **see Data availability below, this pair doesn't map to current data;
    adapt or drop per that note.**
  - A red (`#dc2626`) "Search on YouTube" button using the existing
    `ytLink()` helper and the item's `search` field — reuse verbatim, don't
    reimplement the URL construction.
  - Two small quick-action pills ("✓ Learned" / "↺ Review" in the
    reference) — **see Data availability below; these must route through
    the existing `/answer` POST contract if implemented at all, not a new
    ad-hoc state field.**

## Questions panel — detail

Two-column layout at full width (stack to one column below the mobile
breakpoint): left column = placement questions under a "PLACE YOUR LEVEL"
header with a small progress bar (segments = one per placement question,
filled = answered) and an "N / M answered" counter; right column = optional
questions under a "SHARPEN THE PATH" header with an "optional" pill.

This is a **straight relocation** of the existing placement/optional
question-card rendering (`questionCard`, the unanswered/placement/optional
split, `submitAnswer`) into this two-column shell — no behavior change to
the actual question logic, only the layout and card chrome restyled to match
the reference's darker card look (`#1e2530`/`#1e1e1e` cards, `#236ca1`/
`#2d3748` borders depending on answered state).

**The one required behavior change**: after a successful `submitAnswer()`
call, the Node Graph panel must re-render so the just-answered concept's
node recolors immediately, without a full page reload.

## Tools panel — detail

Right rail. Header row: toolbox icon + "Tools" label + a count pill + a
filter icon (decorative unless you want to wire a real client-side text
filter against the list below — that's a reasonable small addition, not
required). Below that, a "Filter tools..." search input — wiring this to
filter the visible rows by name is straightforward and worth doing since the
input is already in the visual design; don't leave it inert if you include
it.

List `inventory.items.filter(i => i.kind === "tool")`, grouped under
category headers (uppercase, muted, e.g. "PACKAGE MANAGERS", "RUNTIMES",
"BUILD TOOLS", "LINTING & FORMATTING", "TESTING" in the reference). **See
Data availability below — OnTrack's `tool_config` items (Dockerfile,
Makefile, etc.) have no built-in category field, so you'll need to derive a
grouping.** Each row: an icon/initials badge, the tool name, its `where`
path, and — **see Data availability** — a version + detection-status dot are
shown in the reference but don't map to current data.

Empty state: "No tooling detected yet" if the list is empty.

## Data availability — what to adapt or drop

The Figma reference was designed generically and includes a few fields
`inventory.json`/`personal.json` do not currently carry. Do not let these
block shipping the rest of the rework — handle each as follows:

1. **Node-detail "Deps" / "Uses" counts** — no such counters exist today.
   Reasonable substitute: count outgoing edges (items this node's `from`
   points to = "Deps") and incoming edges (items whose `from` points to this
   node = "Uses"). If that doesn't feel meaningful for a given node kind,
   drop the stat tiles entirely rather than fabricate numbers.
2. **Node-detail "✓ Learned" / "↺ Review" quick-mark buttons** — there is no
   generic "manually set this concept's state" action in the current
   `/answer` API; answers are tied to specific question IDs. If you
   implement these buttons, they must submit an answer for `qByConcept[item.id]`
   via the existing `submitAnswer()`/`postJSON("/answer", ...)` path (i.e.
   only enabled when a question exists for that node). If no question exists
   for the node, disable or hide the buttons rather than inventing a new
   state-storage mechanism.
3. **Tools panel version numbers + live detection status** ("v10.2.3 ·
   Detected", "v1.41.0 · Not configured") — OnTrack's evidence scan does not
   currently record tool versions or run/config-detection checks, only that
   the config file exists (`tool_config` evidence type, see
   `ontrack/hooks/track.py`). Drop the version and status line, or replace it
   with the one thing you do have — the file path (`item.where`) — styled
   similarly. Do not fabricate version numbers or a "Detected" status.
4. **Tools panel category grouping** ("Package Managers", "Runtimes", "Build
   Tools", etc.) — no category field exists on `kind:"tool"` items today.
   Derive a small client-side mapping from known tool names to a category
   (e.g. a lookup table keyed by the item's name/id, mirroring how
   `CONFIG_TOOL` in `ontrack/skills/ontrack/build.py` maps filenames to
   labels) — this is a display-only grouping in the dashboard's JS, not a
   change to `inventory.json`'s shape. Anything unmapped falls into a
   generic "Tools" group rather than being dropped.

None of these four items should gate finishing the Node Graph and Questions
panels, which are the core of this rework and have complete data support
already.

## What must NOT change

- `/inventory.json`, `/questions.json`, `/personal.json` fetch calls and
  their shapes — read-only inputs, already correct.
- `/level` and `/answer` POST behavior (`setLevel`, `submitAnswer`,
  `postJSON`) — reuse verbatim.
- `stateOf()`, `derivedLevel()`, `ytLink()`, `el()` helper functions — reuse
  verbatim, don't reimplement.
- The level-intake screen (before a level is set) — completely unchanged.
- No new external dependency of any kind (no CDN script, no npm package, no
  iframe). Everything ships inline in this one HTML file, as it does today.
- The flat "learning path" text view this replaces can be deleted — the
  graph + stat bar are its replacement. Don't keep both.

## Verification before you consider this done

Manually check, in a real browser (there is no JS test harness in this
project today, so this is the actual bar):

1. A project with a mix of confirmed deps, languages, tools, and concepts,
   plus a mix of answered/unanswered questions — confirm node colors match
   `stateOf()`'s result, and the stat-bar counts match the graph.
2. `kind:"tool"` items appear ONLY in the Tools rail — never as a graph node.
3. Drag a node away, release it, confirm it settles back into the simulation.
4. Click a node, confirm the detail card opens with correct content; click
   another node, confirm it updates (not stacks).
5. Answer a question in the Questions panel and confirm the matching graph
   node's color AND the stat-bar counts update immediately, without a page
   reload.
6. Resize the window below ~900px and confirm the panels stack vertically
   and remain usable.
7. Confirm every color is legible against its background (the reference is
   dark-only — verify contrast, don't just trust the hex values transcribed
   above).
8. Confirm none of the "Data availability" adaptations fabricate data that
   isn't real (no invented version numbers, no invented "Detected" status).
