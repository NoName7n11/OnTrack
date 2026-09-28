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
