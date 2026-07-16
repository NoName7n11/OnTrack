---
name: ontrack
description: Show what this project uses so you know what to learn. Regenerates the OnTrack inventory from tracked evidence (validated against the current repo) and displays it. Trigger on "/ontrack", "what does this project use", "what should I learn here", "ontrack".
---

# /ontrack

Surface what the project uses so the user can spot what they don't know and go
learn it. OnTrack reports **what exists + what to search for** — it does NOT teach,
and it does NOT claim to know what the user already knows. See `PLAN.md`.

## Steps

1. Refresh the deterministic inventory first, so confirmed parent IDs are current:
   ```
   python "${CLAUDE_PLUGIN_ROOT}/skills/ontrack/build.py"
   ```

2. **Concept-inference pass (you, the model, do this).** Look at the confirmed
   libraries/languages the project uses by reading the refreshed
   `.ontrack/inventory.json`, then read a sample of the project's own source
   files (skip `node_modules`, `.venv`, build output, `.ontrack`). For each
   confirmed library/language, identify the **specific concepts actually used in
   this code** — e.g. under React: `useEffect`, `useState`, JSX, props, conditional
   rendering; under a JWT dep: token signing, refresh flow. Write them to
   `.ontrack/concepts.json`:
   ```json
   { "concepts": [
     { "id": "concept:react/useeffect", "name": "useEffect",
       "parent": "library:react", "confidence": "inferred",
       "what": "Run side effects after render",
       "where": ["src/App.tsx:14"], "search": "react useeffect tutorial" }
   ] }
   ```
   Rules — this is where honesty is enforced:
   - `id` = `concept:<parent-slug>/<concept-slug>`. `parent` MUST be the `id` of a
     confirmed inventory item (`library:*` / `language:*`); a concept with no
     confirmed parent is dropped by `build.py`.
   - `confidence: "inferred"` only when you can point at real code (`where` =
     `file:line`). Use `confidence: "possible"` for a weak/ambient guess with no
     concrete line — these are hidden on the dashboard by default.
   - `where` paths are **repo-relative and use forward slashes** (`src/App.tsx:14`,
     not `C:\...` or `\`-separated). `build.py` drops any `where` path that resolves
     outside the repo, and drops an `inferred` concept left with no valid `where`.
   - One line of `what`; a ready `search` query. Do NOT teach or explain.
   - Only list concepts genuinely present in the code. No speculative curriculum.

3. Regenerate the inventory again (merges confirmed evidence + your concepts, each
   validated against the current repo):
   ```
   python "${CLAUDE_PLUGIN_ROOT}/skills/ontrack/build.py"
   ```
   This rewrites `.ontrack/inventory.json` (only if changed). Stale evidence
   (removed deps, deleted file types) and orphaned concepts (parent gone) drop
   out automatically.

4. Start the dashboard server **in the background** (it blocks while serving):
   ```
   python "${CLAUDE_PLUGIN_ROOT}/skills/ontrack/server.py"
   ```
   It binds `127.0.0.1` and prints the URL (default
   `http://localhost:3874`, incrementing if the port is busy).

5. Tell the user to open that URL. On the dashboard they mark each item's status
   (Known / Somewhat / To learn / Ignore); items sort into **To Review /
   Learning / Learned / Ignored**, with concepts nested under their library.
   `possible` concepts are hidden until the user ticks "show possible". Marks save
   to `.ontrack/personal.json`.

You may also give a quick text summary of the inventory, but the dashboard is the
primary view. Do not explain or teach the technologies — the point is the user
decides what they don't know and learns it elsewhere.

## Boundaries

- Never hand-edit `inventory.json` — it is derived; rerun `build.py` instead.
- `concepts.json` is your inference output; `build.py` validates and merges it.
  Confirmed items always win over a concept on id collision.
- The server writes only `.ontrack/personal.json`; `inventory.json` is read-only to it.
- Confidence is honest by construction: `confirmed` = deterministic evidence,
  `inferred` = code-backed concept, `possible` = weak guess (hidden by default).
