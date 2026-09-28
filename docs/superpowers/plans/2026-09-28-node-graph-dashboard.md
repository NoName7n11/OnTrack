# Node-Graph Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `dashboard.html`'s post-intake flat-list view with a 3-panel
dark-theme layout: a draggable force-directed node graph of the inventory
(colored by the user's quiz-derived confidence), a two-column questions
panel, and a grouped tools rail — all in the same single self-contained HTML
file, no server or JSON-shape changes.

**Architecture:** One file (`ontrack/skills/ontrack/dashboard.html`) grows
from ~415 to ~900-1000 lines. New pure math (force simulation step) is
written as free functions inside the existing `<script>` block so it stays
zero-build/zero-dependency; those functions are unit-tested by a small Node
script that extracts and evals the inline `<script>` in a sandboxed `vm`
context (Node's stdlib `vm` module — no test framework, no new dependency).
Everything else (rendering, DOM, drag) is verified manually in a browser, in
line with this file's existing convention of having no JS test harness for
its rendering layer.

**Tech Stack:** Vanilla JS, inline SVG, CSS custom properties. Node.js stdlib
`vm` module for the one automated test. No new dependency, no build step,
no server change.

**Spec:**
`docs/superpowers/specs/2026-09-28-node-graph-dashboard-design.md`
(read this first — it has the full rationale) and
`docs/superpowers/specs/2026-09-28-node-graph-dashboard-agent-prompt.md`
(the detailed visual/behavioral reference, including the "Data availability"
section listing which Figma-reference details have no backing data and how
to adapt them — **treat that file as a reference to draw from, not a literal
spec to match pixel-for-pixel**).

## Global Constraints

- No new external dependency of any kind (no CDN script, no npm package, no
  iframe). Everything ships inline in `dashboard.html`, as it does today.
- No server or build-step changes. `/inventory.json`, `/questions.json`,
  `/personal.json` fetch shapes, and the `/level`/`/answer` POST contracts,
  are unchanged — reuse `setLevel`, `submitAnswer`, `postJSON`, `stateOf`,
  `derivedLevel`, `ytLink`, `el` verbatim; do not reimplement them.
  (`ontrack/skills/ontrack/server.py` whitelists exactly `/`, `/index.html`,
  `/inventory.json`, `/questions.json`, `/personal.json`, `/favicon.ico` for
  GET, and `/answer`, `/level` for POST — there is no route for a second
  static file, which is why everything stays in one file.)
- The level-intake screen (`intakeCard()`, shown when `!personal.level`) is
  completely unchanged.
- Treat the Figma-derived visual reference as a starting point: match its
  structure, palette, and component ideas, but adapt where it conflicts with
  this file's existing CSS variable system, where a literal field has no
  backing data (see "Data availability" in the agent-prompt doc), or where a
  simpler solution is clearly better.
- This dashboard view is dark-only going forward (see agent-prompt doc,
  "Color system" section) — this is a deliberate, explicit scope decision:
  the existing light/dark toggle (`prefers-color-scheme`, `data-theme`)
  stays in the CSS variable system, but the new dark palette values are the
  only ones this rework adds; do not attempt to also design a light variant
  of the graph/questions/tools panels.
- Never fabricate data the inventory doesn't carry. Where the Figma reference
  shows a field OnTrack has no data for (dependency/use counts, tool version
  numbers, live "Detected" status), either derive a real substitute from
  actual data (e.g. edge counts) or drop the field — never hardcode a
  plausible-looking placeholder value.

## Review Focus

- **Zero inventory items** (fresh project, nothing scanned): the graph panel
  must show a clear empty state, not a blank `<svg>` or a JS error from
  iterating an empty array through the force sim.
- **Zero questions**: the stat bar's Learned/Learn/Review/Untested counts
  must still compute (everything falls into "Untested"), and the Questions
  panel must show its existing empty-state message, not break. The count
  rule is `q ? stateOf(q) : "untested"` — the same rule as the graph node
  color, so the two views never disagree.
- **An inventory item whose `from` provenance points at a `(type, name)` pair
  that resolves to no current inventory item** (stale/partial evidence,
  possible after a manifest is edited): the edge-building code must skip it,
  not throw or draw a dangling edge to `undefined`.
- **A concept answered via self-report vs. graded**: `stateOf(q)` already
  branches on `q.mode`; the graph node coloring must call this exact
  function rather than re-deriving state, so both answer types recolor
  correctly.
- **Window resize across the ~900px breakpoint while the graph is running**:
  the SVG and force sim must not throw when the panel's pixel dimensions
  change (e.g. center-pull target recomputed, not stale from initial mount).

---

## File Structure

Single file modified: `ontrack/skills/ontrack/dashboard.html`.

New test file: `ontrack/skills/ontrack/test_dashboard_graph.mjs` — a small
Node script (run via `node test_dashboard_graph.mjs`, no framework) that:
1. Reads `dashboard.html`, extracts the `<script>...</script>` contents via
   a regex.
2. Runs it in a `vm.Script` inside a `vm.createContext` stub that provides
   just enough fake globals (`document` with stub `getElementById`,
   `createElement`, etc.; `fetch` returning rejected promises since `load()`
   auto-runs at the bottom of the script — see Task 2 for the exact stub) so
   the script evaluates without throwing, exposing its top-level `function`
   declarations on the sandbox's global object.
3. Calls the exposed pure functions (`forceStep`, `buildGraphNodes`,
   `buildGraphEdges` — defined in Task 2/3) directly and asserts on their
   output.

No other files change. `build.py`/`track.py`/server-side tests are untouched
(this rework touches no Python).

---

## Task 1: Dark-theme CSS variables + derived-level stat bar

**Files:**
- Modify: `ontrack/skills/ontrack/dashboard.html` (the `<style>` block, and
  `render()` around `dashboard.html:347-353` where the old `.levelbar` is
  built)

**Interfaces:**
- Consumes: `personal.level`, `derivedLevel()` (existing, unchanged),
  `inventory.items`, `qByConcept` (existing globals).
- Produces: a new CSS class block for the dark graph-view chrome (`.gv-*`
  prefix, to avoid colliding with any surviving light-mode class names), and
  a new function `computeStateCounts()` returning
  `{learned:N, learn:N, review:N, untested:N}` by iterating
  `inventory.items.filter(i => i.kind !== "tool")` and tallying each item's
  `qByConcept[item.id] ? stateOf(qByConcept[item.id]) : "untested"`. Later
  tasks (2, 3) reuse this exact function so the stat bar and the graph nodes
  never disagree on a node's state.

- [ ] **Step 1: Add the dark palette CSS variables**

Add a new block right after the existing `:root[data-theme="dark"]` rule in
the `<style>` section (`dashboard.html:23-25`):

```css
/* graph-view dark chrome (always dark, independent of the light/dark toggle
   above — see spec's Global Constraints for why) */
.gv {
  --gv-bg:#1a1a1a; --gv-panel:#1e1e1e; --gv-panel2:#1e2530; --gv-well:#171717;
  --gv-border:#333; --gv-border2:#2d3748; --gv-border3:#374151;
  --gv-accent:#236ca1; --gv-accent-soft:rgba(35,108,161,0.2);
  --gv-text:#f9fafb; --gv-text2:#d1d5db; --gv-muted:#9ca3af; --gv-faint:#6b7280;
  --gv-learned:#10b981; --gv-learn:#3b82f6; --gv-review:#f59e0b; --gv-untested:#4b5563;
  --gv-danger:#dc2626; --gv-purple:#8b5cf6;
  background:var(--gv-bg); color:var(--gv-text2);
}
```

- [ ] **Step 2: Add the stat-bar markup styles**

```css
.gv-statbar { background:#1c2b3a; border-bottom:2px solid var(--gv-accent);
  display:flex; align-items:center; gap:16px; height:44px; padding:0 24px; }
.gv-pill { background:var(--gv-accent); color:#fff; font:600 11px var(--mono);
  letter-spacing:.05em; text-transform:uppercase; padding:3px 10px; border-radius:4px; }
.gv-derived { color:#93c5fd; font-size:13px; }
.gv-counts { display:flex; gap:16px; margin-left:auto; }
.gv-count { display:flex; align-items:center; gap:5px; font-size:12px; color:var(--gv-muted); }
.gv-dot { width:8px; height:8px; border-radius:4px; flex:none; }
.gv-count b { font-weight:600; }
.gv-recalc { background:var(--gv-accent); color:#fff; border:none; border-radius:6px;
  padding:5px 12px; font:600 12px var(--sans); cursor:pointer; display:flex; align-items:center; gap:6px; }
```

- [ ] **Step 3: Write `computeStateCounts()`**

Add near `stateOf()` (`dashboard.html:182-188`):

```javascript
function computeStateCounts() {
  const counts = { learned: 0, learn: 0, review: 0, untested: 0 };
  for (const item of inventory.items || []) {
    if (item.kind === "tool") continue;
    const q = qByConcept[item.id];
    const st = q ? stateOf(q) : "untested";
    counts[st === "unanswered" ? "untested" : st]++;
  }
  return counts;
}
```

- [ ] **Step 4: Build the stat-bar DOM and wire it into `render()`**

Add a new function:

```javascript
function statBar() {
  const bar = el("div", "gv-statbar");
  const d = derivedLevel();
  const pill = el("span", "gv-pill", "Derived level");
  bar.appendChild(pill);
  bar.appendChild(el("span", "gv-derived",
    (LEVEL_LABEL[d.level] || d.level) + " · " + d.why));
  const counts = computeStateCounts();
  const wrap = el("div", "gv-counts");
  const rows = [["learned","Learned","--gv-learned"],["learn","Learn","--gv-learn"],
    ["review","Review","--gv-review"],["untested","Untested","--gv-untested"]];
  for (const [key, label, cssVar] of rows) {
    const row = el("div", "gv-count");
    const dot = el("span", "gv-dot"); dot.style.background = `var(${cssVar})`;
    row.appendChild(dot);
    row.appendChild(el("span", null, label + " "));
    row.appendChild(el("b", null, String(counts[key])));
    wrap.appendChild(row);
  }
  bar.appendChild(wrap);
  const recalc = el("button", "gv-recalc", "Recalculate");
  recalc.addEventListener("click", render);
  bar.appendChild(recalc);
  return bar;
}
```

In `render()` (`dashboard.html:335-345`), replace the old `.levelbar` block
(`dashboard.html:347-353`) with a call to `statBar()`, and wrap the whole
post-intake output in a `<div class="gv">` container so the dark variables
apply. Keep `derivedLevel()` itself untouched — `statBar()` only consumes it.

- [ ] **Step 5: Manual verification**

Run the dashboard server against a project with existing `.ontrack/` data
(or the fixtures under `ontrack/skills/ontrack/test_build.py` if you build a
temp project), open the dashboard in a browser, set a level, and confirm:
the stat bar renders with correct counts (cross-check against
`inventory.json`/`personal.json` by hand for a small fixture), the
Recalculate button re-renders without error, and the dark background applies
only within the post-intake view (the intake screen before a level is set is
unaffected, per Global Constraints).

- [ ] **Step 6: Commit**

```bash
git add ontrack/skills/ontrack/dashboard.html
git commit -m "Add dark-theme stat bar to dashboard graph view

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 2: Force-simulation math (pure functions) + Node test harness

**Files:**
- Modify: `ontrack/skills/ontrack/dashboard.html` (add pure sim functions to
  the `<script>` block)
- Create: `ontrack/skills/ontrack/test_dashboard_graph.mjs`

**Interfaces:**
- Consumes: nothing external — pure math over plain objects.
- Produces (for Task 3 to consume):
  - `buildGraphNodes(inventory, qByConcept)` → array of
    `{id, label, kind, where, what, search, state, x, y, vx, vy, fixed}`
    (one entry per `inventory.items` where `item.kind !== "tool"`; `x`/`y`
    start at a deterministic pseudo-random position seeded by `id` so
    re-renders before the sim settles don't jump wildly; `vx`/`vy` start at
    `0`; `fixed` starts `false`).
  - `buildGraphEdges(nodes)` → array of `{source, target}` (both are node
    `id` strings), built from each node's originating inventory item's
    `from` array, resolved via a `{type,name} -> id}` index. An edge whose
    `from` entry resolves to no known node id is skipped (Review Focus: dangling
    provenance).
  - `forceStep(nodes, edges, width, height, dt)` → mutates each non-`fixed`
    node's `x`/`y`/`vx`/`vy` in place by one simulation tick (repulsion +
    spring + center-pull + damping) and returns nothing. Pure aside from
    that in-place mutation — no DOM, no globals besides its arguments.

- [ ] **Step 1: Write the failing test**

Create `ontrack/skills/ontrack/test_dashboard_graph.mjs`:

```javascript
// Self-check for dashboard.html's inline graph math — run:
// node ontrack/skills/ontrack/test_dashboard_graph.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const __dirname = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(__dirname, "dashboard.html"), "utf8");
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) throw new Error("no <script> block found in dashboard.html");
const src = scriptMatch[1];

// Minimal DOM/fetch stub so the script's top-level load() call (and any
// other DOM access at parse time) doesn't throw when evaluated outside a
// browser. We never let load()'s promise resolve or reject observably —
// we only need the script body to finish executing so its function
// declarations land on the sandbox global.
function stubEl() {
  return { appendChild(){}, addEventListener(){}, style:{}, classList:{toggle(){}},
    set textContent(v){}, set className(v){}, set href(v){}, set target(v){},
    set rel(v){}, set placeholder(v){}, set rows(v){}, set disabled(v){} };
}
const sandbox = {
  document: { getElementById: () => stubEl(), createElement: () => stubEl() },
  fetch: () => new Promise(() => {}),  // never resolves; load() just hangs, harmlessly
  console,
};
vm.createContext(sandbox);
new vm.Script(src, { filename: "dashboard.html-inline-script" }).runInContext(sandbox);

const { buildGraphNodes, buildGraphEdges, forceStep } = sandbox;

function test_buildGraphNodes_excludes_tools() {
  const inventory = { items: [
    { id: "library:react", kind: "library", name: "React" },
    { id: "tool:docker", kind: "tool", name: "Docker" },
  ] };
  const nodes = buildGraphNodes(inventory, {});
  const ids = nodes.map(n => n.id);
  if (!ids.includes("library:react")) throw new Error("expected library node present");
  if (ids.includes("tool:docker")) throw new Error("tool must not become a graph node");
  console.log("ok: buildGraphNodes excludes kind:tool items");
}

function test_buildGraphEdges_skips_dangling_provenance() {
  const inventory = { items: [
    { id: "library:react", kind: "library", name: "React" },
    { id: "concept:react/useeffect", kind: "concept", name: "useEffect",
      from: [{ type: "dependency", name: "react" }] },
    { id: "concept:orphan", kind: "concept", name: "Orphan",
      from: [{ type: "dependency", name: "nonexistent-package" }] },
  ] };
  const nodes = buildGraphNodes(inventory, {});
  const edges = buildGraphEdges(nodes, inventory);
  if (edges.length !== 1) throw new Error(`expected 1 resolvable edge, got ${edges.length}`);
  if (edges[0].source !== "library:react" || edges[0].target !== "concept:react/useeffect")
    throw new Error("edge did not resolve to the expected source/target");
  console.log("ok: buildGraphEdges resolves provenance and skips dangling from-entries");
}

function test_forceStep_moves_repelling_nodes_apart() {
  const nodes = [
    { id:"a", x:100, y:100, vx:0, vy:0, fixed:false },
    { id:"b", x:105, y:100, vx:0, vy:0, fixed:false },
  ];
  const before = Math.hypot(nodes[0].x - nodes[1].x, nodes[0].y - nodes[1].y);
  forceStep(nodes, [], 800, 600, 0.016);
  const after = Math.hypot(nodes[0].x - nodes[1].x, nodes[0].y - nodes[1].y);
  if (!(after > before)) throw new Error(`expected nodes to repel apart: ${before} -> ${after}`);
  console.log("ok: forceStep repels two close nodes apart");
}

function test_forceStep_skips_fixed_nodes() {
  const nodes = [
    { id:"a", x:100, y:100, vx:0, vy:0, fixed:true },
    { id:"b", x:105, y:100, vx:0, vy:0, fixed:false },
  ];
  forceStep(nodes, [], 800, 600, 0.016);
  if (nodes[0].x !== 100 || nodes[0].y !== 100)
    throw new Error("fixed node must not move");
  console.log("ok: forceStep leaves fixed (dragged) nodes in place");
}

test_buildGraphNodes_excludes_tools();
test_buildGraphEdges_skips_dangling_provenance();
test_forceStep_moves_repelling_nodes_apart();
test_forceStep_skips_fixed_nodes();
console.log("PASS");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node ontrack/skills/ontrack/test_dashboard_graph.mjs`
Expected: fails with something like
`TypeError: buildGraphNodes is not a function` (the functions don't exist
yet in `dashboard.html`).

- [ ] **Step 3: Write the minimal implementation**

Add to `dashboard.html`'s `<script>` block, near `buildPath()`
(`dashboard.html:286-309`):

```javascript
// Deterministic pseudo-random start position, seeded by id, so repeated
// renders before the sim settles don't jump the layout around.
function seedXY(id, width, height) {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0;
  const rx = ((h >>> 0) % 1000) / 1000;
  const ry = (((h >>> 8) >>> 0) % 1000) / 1000;
  return { x: width * (0.2 + 0.6 * rx), y: height * (0.2 + 0.6 * ry) };
}

function buildGraphNodes(inv, qByC, width, height) {
  width = width || 800; height = height || 600;
  const nodes = [];
  for (const item of (inv.items || [])) {
    if (item.kind === "tool") continue;
    const q = qByC[item.id];
    const state = q ? stateOf(q) : "untested";
    const { x, y } = seedXY(item.id, width, height);
    nodes.push({
      id: item.id, label: item.name || item.id, kind: item.kind,
      where: item.where || [], what: item.what, search: item.search,
      state: state === "unanswered" ? "untested" : state,
      x, y, vx: 0, vy: 0, fixed: false,
    });
  }
  return nodes;
}

function buildGraphEdges(nodes, inv) {
  const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
  const bySource = {};  // "{type}::{name}" -> node.id, for items that ARE a dep/language
  for (const item of (inv.items || [])) {
    if (item.kind === "library") bySource[`dependency::${item.name}`] = item.id;
    if (item.kind === "language") bySource[`file_extension::${item.name}`] = item.id;
  }
  const edges = [];
  for (const item of (inv.items || [])) {
    if (!byId[item.id]) continue;
    for (const prov of (item.from || [])) {
      const srcId = bySource[`${prov.type}::${prov.name}`];
      if (srcId && byId[srcId]) edges.push({ source: srcId, target: item.id });
    }
  }
  return edges;
}

// One simulation tick: repulsion between all pairs, spring attraction along
// edges, weak center-pull, velocity damping. Mutates node x/y/vx/vy in place.
// ponytail: O(n^2) repulsion, fine at tens of nodes; add spatial partitioning
// if a real project's inventory ever makes this visibly slow.
function forceStep(nodes, edges, width, height, dt) {
  const REPEL = 6000, SPRING = 0.02, REST = 90, CENTER = 0.002, DAMP = 0.85;
  for (const n of nodes) { if (!n.fixed) { n.fx = 0; n.fy = 0; } }
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j];
      let dx = a.x - b.x, dy = a.y - b.y;
      let dist2 = dx * dx + dy * dy;
      if (dist2 < 1) dist2 = 1;
      const force = REPEL / dist2;
      const dist = Math.sqrt(dist2);
      const fx = (dx / dist) * force, fy = (dy / dist) * force;
      if (!a.fixed) { a.fx += fx; a.fy += fy; }
      if (!b.fixed) { b.fx -= fx; b.fy -= fy; }
    }
  }
  const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
  for (const e of edges) {
    const a = byId[e.source], b = byId[e.target];
    if (!a || !b) continue;
    const dx = b.x - a.x, dy = b.y - a.y;
    const dist = Math.max(1, Math.hypot(dx, dy));
    const stretch = dist - REST;
    const fx = (dx / dist) * stretch * SPRING, fy = (dy / dist) * stretch * SPRING;
    if (!a.fixed) { a.fx += fx; a.fy += fy; }
    if (!b.fixed) { b.fx -= fx; b.fy -= fy; }
  }
  for (const n of nodes) {
    if (n.fixed) continue;
    n.fx += (width / 2 - n.x) * CENTER;
    n.fy += (height / 2 - n.y) * CENTER;
    n.vx = (n.vx + n.fx * dt) * DAMP;
    n.vy = (n.vy + n.fy * dt) * DAMP;
    n.x += n.vx; n.y += n.vy;
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node ontrack/skills/ontrack/test_dashboard_graph.mjs`
Expected: all four `ok:` lines print, then `PASS`.

- [ ] **Step 5: Commit**

```bash
git add ontrack/skills/ontrack/dashboard.html ontrack/skills/ontrack/test_dashboard_graph.mjs
git commit -m "Add force-simulation math for the node graph, with a Node test harness

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: SVG graph rendering, drag, and node-detail card

**Files:**
- Modify: `ontrack/skills/ontrack/dashboard.html` (`<style>` block; new
  render functions in `<script>`; `render()`)

**Interfaces:**
- Consumes: `buildGraphNodes`, `buildGraphEdges`, `forceStep` (Task 2);
  `ytLink`, `el` (existing).
- Produces: `graphPanel()` → a DOM element containing the `<svg>`, legend,
  zoom controls, and node-detail card container, plus a `startSim()` call
  that begins the `requestAnimationFrame` loop. `render()` calls this once
  per full render and must NOT start a second overlapping animation loop on
  re-render (Review Focus: resize/re-render must not throw or leak loops —
  guard with a module-level `let simRunning = false` cancel/restart, or a
  single persistent loop keyed by a generation counter that discards stale
  loops after a re-render replaces the SVG).

- [ ] **Step 1: Add graph panel CSS**

```css
.gv-graph { position:relative; background:var(--gv-well); border-right:2px solid var(--gv-accent);
  overflow:hidden; height:60vh; min-height:360px; }
.gv-graph svg { width:100%; height:100%; display:block; }
.gv-edge { stroke-width:1; }
.gv-node circle { cursor:grab; }
.gv-node text { fill:#fff; font:700 10px var(--sans); text-anchor:middle;
  dominant-baseline:middle; pointer-events:none; }
.gv-legend { position:absolute; top:16px; left:16px; background:rgba(30,30,30,0.8);
  border:1px solid var(--gv-border); border-radius:8px; padding:10px 12px;
  display:flex; flex-direction:column; gap:6px; font-size:11px; }
.gv-legend .lt { color:var(--gv-muted); font:600 10px var(--mono); letter-spacing:.05em;
  text-transform:uppercase; }
.gv-legend .lr { display:flex; align-items:center; gap:8px; color:var(--gv-text2); }
.gv-legend .ld { width:10px; height:10px; border-radius:5px; flex:none; }
.gv-zoom { position:absolute; bottom:16px; right:16px; background:rgba(30,30,30,0.8);
  border:1px solid var(--gv-border); border-radius:8px; padding:6px; display:flex;
  flex-direction:column; gap:4px; }
.gv-zoom button { width:28px; height:28px; background:#242424; border:none; border-radius:6px;
  color:var(--gv-muted); font-size:16px; cursor:pointer; }
.gv-detail { position:absolute; top:16px; right:16px; width:244px; background:var(--gv-panel2);
  border:1px solid var(--gv-accent); border-radius:12px; overflow:hidden; }
.gv-detail .hd { background:var(--gv-accent); display:flex; align-items:center;
  justify-content:space-between; padding:12px 14px; }
.gv-detail .hd .name { color:#fff; font-weight:700; font-size:13px; display:flex; align-items:center; gap:8px; }
.gv-detail .hd .dot { width:10px; height:10px; border-radius:5px; }
.gv-detail .hd .badge { background:rgba(255,255,255,0.13); color:#93c5fd; font:600 10px var(--sans);
  padding:3px 8px; border-radius:4px; text-transform:uppercase; }
.gv-detail .bd { padding:14px; display:flex; flex-direction:column; gap:12px; }
.gv-detail .what { color:var(--gv-text2); font-size:12px; }
.gv-detail .files-lt { color:var(--gv-muted); font:600 10px var(--mono); letter-spacing:.05em;
  text-transform:uppercase; }
.gv-detail .file-row { background:#12181f; border:1px solid var(--gv-border2); border-radius:5px;
  padding:5px 8px; font-size:11px; color:#93c5fd; overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap; margin-top:4px; }
.gv-detail .yt { background:var(--gv-danger); color:#fff; border:none; border-radius:8px;
  padding:8px 12px; font:600 12px var(--sans); cursor:pointer; width:100%; text-align:center;
  text-decoration:none; display:block; box-sizing:border-box; }
.gv-empty { color:var(--gv-faint); font-size:13.5px; font-style:italic; padding:24px; }
```

- [ ] **Step 2: Write `graphPanel()` and the render/sim loop**

Add to the `<script>` block:

```javascript
let graphState = null;  // { nodes, edges, selectedId, gen } — survives re-renders in-session

function graphPanel() {
  const panel = el("div", "gv-graph");
  const width = 800, height = 600;  // logical viewBox size; CSS scales the <svg> to its panel

  if (!graphState || graphState.stale) {
    const nodes = buildGraphNodes(inventory, qByConcept, width, height);
    const edges = buildGraphEdges(nodes, inventory);
    const gen = (graphState ? graphState.gen : 0) + 1;
    const selectedId = graphState ? graphState.selectedId : null;
    graphState = { nodes, edges, selectedId, gen };
  }
  const gs = graphState;

  if (!gs.nodes.length) {
    panel.appendChild(el("div", "gv-empty",
      "Nothing to graph yet. Run /ontrack to scan the project first."));
    return panel;
  }

  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  panel.appendChild(svg);

  const edgeEls = gs.edges.map(e => {
    const line = document.createElementNS(svgNS, "line");
    line.setAttribute("class", "gv-edge");
    const src = gs.nodes.find(n => n.id === e.source);
    line.setAttribute("stroke", `var(--gv-${src ? src.state : "untested"})`);
    line.setAttribute("stroke-opacity", "0.33");
    svg.appendChild(line);
    return { e, line };
  });

  const RADIUS = { concept: 26, library: 34, language: 34 };
  const nodeEls = gs.nodes.map(n => {
    const g = document.createElementNS(svgNS, "g");
    g.setAttribute("class", "gv-node");
    const circle = document.createElementNS(svgNS, "circle");
    const r = RADIUS[n.kind] || 26;
    circle.setAttribute("r", String(r));
    circle.setAttribute("fill", `var(--gv-${n.state})`);
    if (n.kind === "concept") {
      circle.setAttribute("stroke", "#4b5563"); circle.setAttribute("stroke-width", "1.5");
    }
    if (gs.selectedId === n.id) {
      circle.setAttribute("stroke", "#60a5fa"); circle.setAttribute("stroke-width", "3");
    }
    g.appendChild(circle);
    const text = document.createElementNS(svgNS, "text");
    text.textContent = n.label.length > 12 ? n.label.slice(0, 11) + "…" : n.label;
    g.appendChild(text);
    svg.appendChild(g);

    g.addEventListener("pointerdown", (ev) => {
      n.fixed = true;
      const move = (mv) => {
        const rect = svg.getBoundingClientRect();
        n.x = (mv.clientX - rect.left) / rect.width * width;
        n.y = (mv.clientY - rect.top) / rect.height * height;
      };
      const up = () => {
        n.fixed = false;
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    });
    g.addEventListener("click", () => {
      gs.selectedId = n.id;
      renderGraphOnly();
    });
    return { n, g, circle, text };
  });

  function tick() {
    forceStep(gs.nodes, gs.edges, width, height, 0.4);
    for (const { n, g } of nodeEls) g.setAttribute("transform", `translate(${n.x},${n.y})`);
    for (const { e, line } of edgeEls) {
      const src = gs.nodes.find(x => x.id === e.source), dst = gs.nodes.find(x => x.id === e.target);
      if (!src || !dst) continue;
      line.setAttribute("x1", src.x); line.setAttribute("y1", src.y);
      line.setAttribute("x2", dst.x); line.setAttribute("y2", dst.y);
    }
    if (graphState === gs) requestAnimationFrame(tick);  // stale loop stops itself after a re-render
  }
  requestAnimationFrame(tick);

  const legend = el("div", "gv-legend");
  legend.appendChild(el("div", "lt", "Confidence"));
  for (const [key, label] of [["learned","Learned"],["learn","Learn"],["review","Review"],["untested","Untested"]]) {
    const row = el("div", "lr");
    const dot = el("span", "ld"); dot.style.background = `var(--gv-${key})`;
    row.appendChild(dot); row.appendChild(el("span", null, label));
    legend.appendChild(row);
  }
  panel.appendChild(legend);

  const zoom = el("div", "gv-zoom");
  const zin = el("button", null, "+"), zout = el("button", null, "−");
  let scale = 1;
  const applyZoom = () => svg.setAttribute("viewBox",
    `${width/2 - (width/2)/scale} ${height/2 - (height/2)/scale} ${width/scale} ${height/scale}`);
  zin.addEventListener("click", () => { scale = Math.min(3, scale * 1.2); applyZoom(); });
  zout.addEventListener("click", () => { scale = Math.max(0.4, scale / 1.2); applyZoom(); });
  zoom.appendChild(zin); zoom.appendChild(zout);
  panel.appendChild(zoom);

  if (gs.selectedId) {
    const n = gs.nodes.find(x => x.id === gs.selectedId);
    if (n) panel.appendChild(nodeDetailCard(n));
  }

  return panel;
}

function nodeDetailCard(n) {
  const card = el("div", "gv-detail");
  const hd = el("div", "hd");
  const name = el("div", "name");
  const dot = el("span", "dot"); dot.style.background = `var(--gv-${n.state})`;
  name.appendChild(dot); name.appendChild(el("span", null, n.label));
  hd.appendChild(name);
  hd.appendChild(el("span", "badge", n.state.toUpperCase()));
  card.appendChild(hd);
  const bd = el("div", "bd");
  if (n.what) bd.appendChild(el("div", "what", n.what));
  if (n.where && n.where.length) {
    bd.appendChild(el("div", "files-lt", "Related files"));
    for (const w of n.where) bd.appendChild(el("div", "file-row", w));
  }
  const yt = el("a", "yt", "Search on YouTube");
  yt.href = ytLink(n.search || n.label); yt.target = "_blank"; yt.rel = "noopener";
  bd.appendChild(yt);
  card.appendChild(bd);
  return card;
}

// Re-render just the graph panel in place, without rebuilding the whole
// page (used after selecting a node, so Questions/Tools don't flicker).
function renderGraphOnly() {
  const old = document.querySelector(".gv-graph");
  if (old && old.parentNode) old.parentNode.replaceChild(graphPanel(), old);
}
```

- [ ] **Step 3: Wire `graphPanel()` into `render()`**

In `render()`, after `app.appendChild(statBar())` (from Task 1), replace the
old placement/optional/learning-path block layout with:

```javascript
const layout = el("div", "gv-layout");
layout.appendChild(graphPanel());
// Task 4/5 append the questions and tools panels here in later steps.
app.appendChild(layout);
```

Add matching layout CSS:

```css
.gv-layout { display:grid; grid-template-columns:1fr 300px; grid-template-rows:auto auto; }
@media (max-width: 900px) { .gv-layout { grid-template-columns:1fr; } }
```

(Task 4 and 5 will place their panels into this grid's remaining cells —
this step only needs the graph occupying the top-left cell without breaking
layout.)

- [ ] **Step 4: Manual verification**

Open the dashboard with a fixture that has at least 3-4 concepts with `from`
provenance pointing at a library, plus a couple of unanswered/answered
questions. Confirm: nodes render, drift apart via the force sim rather than
stacking, edges connect the right nodes, dragging a node holds it under the
pointer and releasing lets it rejoin the sim, clicking a node opens the
detail card with correct `what`/`where`/YouTube link, clicking a different
node updates the card (doesn't stack a second one), zoom +/- buttons change
the visible scale.

- [ ] **Step 5: Commit**

```bash
git add ontrack/skills/ontrack/dashboard.html
git commit -m "Render the draggable SVG node graph with node-detail card

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: Tools panel

**Files:**
- Modify: `ontrack/skills/ontrack/dashboard.html`

**Interfaces:**
- Consumes: `inventory.items` (existing global), `el` (existing).
- Produces: `toolsPanel()` → a DOM element for the right rail, appended into
  `.gv-layout` by `render()`.

- [ ] **Step 1: Add tools-panel CSS**

```css
.gv-tools { grid-column:2; grid-row:1 / span 2; background:var(--gv-bg);
  border-left:2px solid var(--gv-accent); overflow-y:auto; }
@media (max-width: 900px) { .gv-tools { grid-column:1; grid-row:auto; border-left:none;
  border-top:2px solid var(--gv-accent); } }
.gv-tools-hd { background:var(--gv-panel2); border-bottom:1px solid var(--gv-accent);
  display:flex; align-items:center; gap:8px; padding:0 16px; height:48px; }
.gv-tools-hd .title { color:var(--gv-text); font-weight:600; font-size:14px; }
.gv-tools-hd .count { background:var(--gv-accent-soft); color:#60a5fa; font-size:10px;
  padding:2px 7px; border-radius:10px; }
.gv-tools-filter { padding:10px 12px; border-bottom:1px solid var(--gv-border2); }
.gv-tools-filter input { width:100%; box-sizing:border-box; background:#242424;
  border:1px solid var(--gv-border); border-radius:6px; padding:7px 10px; color:var(--gv-text2);
  font-size:12px; }
.gv-tools-cat { color:var(--gv-faint); font:600 10px var(--mono); letter-spacing:.06em;
  text-transform:uppercase; padding:10px 14px 4px; }
.gv-tool-row { display:flex; gap:10px; align-items:center; padding:10px 14px;
  border-bottom:1px solid var(--gv-border2); }
.gv-tool-badge { width:36px; height:36px; border-radius:8px; flex:none; display:flex;
  align-items:center; justify-content:center; background:var(--gv-accent-soft); color:#60a5fa;
  font:700 10px var(--sans); }
.gv-tool-name { color:var(--gv-text); font-weight:600; font-size:13px; }
.gv-tool-where { color:var(--gv-faint); font-size:11px; overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap; }
```

- [ ] **Step 2: Write a name-to-category lookup and `toolsPanel()`**

Add near `CONFIG_TOOL`-equivalent data (there's no server-side category
field, so this is a display-only client lookup, matching
`ontrack/skills/ontrack/build.py`'s `CONFIG_TOOL` labels by name):

```javascript
const TOOL_CATEGORY = {
  Docker: "Containers", Make: "Build Tools", Procfile: "Process Config",
  Vagrant: "Virtualization", Rake: "Build Tools", Jenkins: "CI/CD",
};

function toolsPanel() {
  const panel = el("div", "gv-tools");
  const tools = (inventory.items || []).filter(i => i.kind === "tool");

  const hd = el("div", "gv-tools-hd");
  hd.appendChild(el("span", "title", "Tools"));
  hd.appendChild(el("span", "count", String(tools.length)));
  panel.appendChild(hd);

  const filterWrap = el("div", "gv-tools-filter");
  const input = document.createElement("input");
  input.placeholder = "Filter tools...";
  filterWrap.appendChild(input);
  panel.appendChild(filterWrap);

  const list = el("div", null);
  panel.appendChild(list);

  function draw(filterText) {
    list.innerHTML = "";
    if (!tools.length) { list.appendChild(el("div", "gv-empty", "No tooling detected yet")); return; }
    const byCat = {};
    for (const t of tools) {
      if (filterText && !(t.name || t.id).toLowerCase().includes(filterText)) continue;
      const cat = TOOL_CATEGORY[t.name] || "Tools";
      (byCat[cat] = byCat[cat] || []).push(t);
    }
    const cats = Object.keys(byCat).sort();
    if (!cats.length) { list.appendChild(el("div", "gv-empty", "No tools match that filter")); return; }
    for (const cat of cats) {
      list.appendChild(el("div", "gv-tools-cat", cat));
      for (const t of byCat[cat]) {
        const row = el("div", "gv-tool-row");
        const badge = el("div", "gv-tool-badge", (t.name || t.id).slice(0, 3));
        row.appendChild(badge);
        const info = el("div", null);
        info.appendChild(el("div", "gv-tool-name", t.name || t.id));
        info.appendChild(el("div", "gv-tool-where", (t.where || []).join(", ")));
        row.appendChild(info);
        list.appendChild(row);
      }
    }
  }
  draw("");
  input.addEventListener("input", () => draw(input.value.trim().toLowerCase()));

  return panel;
}
```

- [ ] **Step 3: Append it in `render()`**

In the `layout` block added in Task 3 Step 3:

```javascript
layout.appendChild(graphPanel());
layout.appendChild(toolsPanel());
```

- [ ] **Step 4: Manual verification**

With a fixture that has `kind:"tool"` items (e.g. from
`ontrack/hooks/test_track.py`'s Dockerfile/Makefile fixtures run through
`build.py`), confirm: tools group under the right category headers, the
filter input narrows the list live, and an empty-tools fixture shows
"No tooling detected yet" instead of an empty panel.

- [ ] **Step 5: Commit**

```bash
git add ontrack/skills/ontrack/dashboard.html
git commit -m "Add grouped, filterable tools rail to dashboard graph view

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: Two-column questions panel + graph recolor on answer

**Files:**
- Modify: `ontrack/skills/ontrack/dashboard.html`

**Interfaces:**
- Consumes: `questionCard` (existing, unchanged), `submitAnswer` (existing —
  gets one addition described below), `skipped` (existing global).
- Produces: `questionsPanel()` → a DOM element for the bottom-left cell of
  `.gv-layout`.

- [ ] **Step 1: Add two-column questions CSS**

```css
.gv-questions { grid-column:1; background:var(--gv-bg); border-top:2px solid var(--gv-accent);
  border-right:2px solid var(--gv-accent); display:grid; grid-template-columns:1fr 1fr; }
@media (max-width: 900px) { .gv-questions { grid-template-columns:1fr; border-right:none; } }
.gv-qcol { border-right:1px solid var(--gv-border2); display:flex; flex-direction:column; }
.gv-qcol:last-child { border-right:none; }
.gv-qcol-hd { background:var(--gv-panel); display:flex; align-items:center; gap:8px;
  padding:10px 20px; }
.gv-qcol-hd .bar { width:3px; height:14px; border-radius:2px; }
.gv-qcol-hd .lbl { color:var(--gv-muted); font:600 12px var(--sans); letter-spacing:.03em;
  text-transform:uppercase; }
.gv-qcol-hd .opt-pill { background:rgba(139,92,246,0.13); color:#a78bfa; font-size:10px;
  padding:2px 6px; border-radius:4px; }
.gv-qcol-body { padding:10px 16px; display:flex; flex-direction:column; gap:8px;
  max-height:220px; overflow-y:auto; }
```

- [ ] **Step 2: Write `questionsPanel()`**

Reuses `questionCard()` exactly as it exists today — this is a layout wrapper,
not a rewrite:

```javascript
function questionsPanel() {
  const panel = el("div", "gv-questions");
  const unanswered = questions.filter(q => !personal.answers[q.id]);
  const placement = unanswered.filter(q => q.placement);
  const optional = unanswered.filter(q => !q.placement && !skipped.has(q.id));

  const left = el("div", "gv-qcol");
  const lhd = el("div", "gv-qcol-hd");
  const lbar = el("span", "bar"); lbar.style.background = "var(--gv-accent)";
  lhd.appendChild(lbar); lhd.appendChild(el("span", "lbl", "Place your level"));
  left.appendChild(lhd);
  const lbody = el("div", "gv-qcol-body");
  if (placement.length) for (const q of placement) lbody.appendChild(questionCard(q, false));
  else lbody.appendChild(el("div", "done", questions.length
    ? "Placement done — your level above reflects your answers."
    : "No questions yet. Run /ontrack to scan the project and generate them."));
  left.appendChild(lbody);
  panel.appendChild(left);

  const right = el("div", "gv-qcol");
  const rhd = el("div", "gv-qcol-hd");
  const rbar = el("span", "bar"); rbar.style.background = "var(--gv-purple)";
  rhd.appendChild(rbar); rhd.appendChild(el("span", "lbl", "Sharpen the path"));
  rhd.appendChild(el("span", "opt-pill", "optional"));
  right.appendChild(rhd);
  const rbody = el("div", "gv-qcol-body");
  if (optional.length) for (const q of optional) rbody.appendChild(questionCard(q, true));
  else rbody.appendChild(el("div", "done", "No more questions right now."));
  right.appendChild(rbody);
  panel.appendChild(right);

  return panel;
}
```

- [ ] **Step 3: Recolor the graph immediately on answer**

`submitAnswer()` (`dashboard.html:174-180`) already calls `render()` on
success, which already rebuilds `graphPanel()` from scratch — but
`graphPanel()` as written in Task 3 only rebuilds `graphState.nodes` when
`graphState` is null or `graphState.stale` is true, to avoid resetting node
drag positions on every unrelated re-render. Mark it stale specifically when
an answer changes the underlying state, so the color updates without also
scrambling the layout on every render:

In `submitAnswer()`, right before the existing `render()` call, add:
```javascript
if (graphState) graphState.stale = true;
```

- [ ] **Step 4: Append it in `render()`**

```javascript
layout.appendChild(graphPanel());
layout.appendChild(toolsPanel());
layout.appendChild(questionsPanel());
```

Adjust the `.gv-layout` grid-template-rows from Task 3 if needed so the
questions panel occupies row 2 under the graph (row 1), both in column 1,
while tools spans both rows in column 2 — the CSS in Task 3 Step 3
(`grid-template-rows:auto auto`) combined with `.gv-tools`'s
`grid-row:1 / span 2` and `.gv-questions`'s implicit row-2 placement
achieves this; verify visually in Step 5.

- [ ] **Step 5: Manual verification — full flow**

This is the integration check for the whole feature:
1. Load a fixture project, set a level (intake screen unchanged).
2. Confirm the 3-panel layout renders: graph top-left, questions
   bottom-left (2 columns), tools right (full height).
3. Answer a placement question. Confirm: the question card disappears from
   the placement column, the stat bar's counts update, AND the
   corresponding graph node recolors — all without a page reload.
4. Resize the browser below ~900px. Confirm the layout stacks to one column
   (graph, then questions, then tools) without clipped or overlapping
   content.
5. Confirm `kind:"tool"` items never appear in the graph, only in the tools
   rail (cross-check against Task 4's test project).
6. Run `node ontrack/skills/ontrack/test_dashboard_graph.mjs` one more time
   to confirm the earlier pure-math changes still pass after all the
   rendering code was added around them.

- [ ] **Step 6: Update project docs**

Add a `PROGRESS.md` entry (per this project's convention — see existing
entries in `PROGRESS.md` for the format) describing the dashboard rework,
what was built, and pointing at this plan + the two spec docs.

- [ ] **Step 7: Commit**

```bash
git add ontrack/skills/ontrack/dashboard.html PROGRESS.md
git commit -m "Add two-column questions panel; recolor graph nodes on answer

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Final Verification (whole-plan)

Before considering this plan done:

- [ ] `node ontrack/skills/ontrack/test_dashboard_graph.mjs` passes.
- [ ] Existing Python suites still pass (this plan touches no Python, but
  confirm nothing was accidentally broken):
  `python ontrack/hooks/test_track.py && python ontrack/skills/ontrack/test_build.py && python ontrack/skills/ontrack/test_server.py && python tools/check_manifests.py`
- [ ] Full manual walkthrough from Task 5 Step 5 passes end to end on a real
  project (not just a synthetic fixture) — dogfood it against this repo's
  own `.ontrack/` data if populated, or a small scanned test project.
- [ ] Every item in this plan's Review Focus section has a concrete manual
  or automated check that was actually exercised (not just written).
