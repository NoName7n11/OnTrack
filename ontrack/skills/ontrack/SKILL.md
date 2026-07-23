---
name: ontrack
description: Turn what this project is built on into a study path. Regenerates the OnTrack inventory + concepts from tracked evidence, authors one assessment question per concept, and serves a dashboard where the user declares their level, answers, and gets a learning path. Trigger on "/ontrack", "what does this project use", "what should I learn here", "ontrack".
---

# /ontrack

Turn the project into a **study path**: surface what it's built on, ask the user a
few questions to gauge what they know, and hand back what to learn (grouped by
domain, ordered). OnTrack **points**; it does NOT teach, and it does NOT claim to
know what the user knows — it asks. See `PLAN.md`.

## Steps

1. Refresh the deterministic inventory first, so confirmed parent IDs are current
   (this also validates any existing `questions.json`, but does not advance the
   session cursor yet):
   ```
   python "${CLAUDE_PLUGIN_ROOT}/skills/ontrack/build.py"
   ```
   Optional cost hint: `.ontrack/state.json`'s `last_processed_session` marks the
   last session already interpreted. Sessions after it in `evidence.jsonl` (look
   for `{"type":"session",...}` markers) are new — focus your file reading there.

2. **Concept-inference pass (you, the model, do this).** Read the refreshed
   `.ontrack/inventory.json`, then a sample of the project's own source files
   (skip `node_modules`, `.venv`, build output, `.ontrack`). For each confirmed
   library/language, identify the **specific concepts actually used in this code**
   — under React: `useEffect`, JSX, props; under a JWT dep: token signing, refresh
   flow. Write them to `.ontrack/concepts.json`:
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
     confirmed inventory item; a concept with no confirmed parent is dropped.
   - `confidence: "inferred"` only when you can point at real code (`where` =
     `file:line`). `confidence: "possible"` for a weak guess with no concrete line.
   - `where` paths are **repo-relative, forward slashes** (`src/App.tsx:14`).
     `build.py` drops paths outside the repo and drops an `inferred` concept left
     with no valid `where`.
   - Optional `level`: `"basic"` | `"intermediate"` | `"advanced"` (the concept's
     difficulty — the dashboard orders the path by it AND uses it to filter by the
     user's level, so set it whenever you can judge).
   - Optional `domain` ∈ `language | framework | system-design | security | tooling`
     — the learning-path bucket. Set it: the path groups untested concepts by this,
     and they have no question to borrow a domain from.
   - One line of `what`; a ready `search` query. Do NOT teach.

   **Foundational prerequisites (for beginners).** Also add a few
   `confidence: "foundational"` concepts: the *prerequisites* a detected
   library/language rests on but that aren't a specific code feature — e.g. a
   project using Flask implies "Python basics", "HTTP requests", "JSON". These are
   shown in the path **only when the user's derived level is Beginner**, to make a
   beginner's path denser and steeper. Rules: `parent` must be a confirmed item,
   `level` is normally `"basic"`, set a `domain`, and **no `where`** (they aren't
   code-detected — that's the point). Keep them to genuine foundations of the
   project's stack; this is not a general curriculum.
   ```json
   { "id": "concept:python/basics", "name": "Python basics", "parent": "language:python",
     "confidence": "foundational", "level": "basic", "domain": "language",
     "what": "Variables, functions, control flow", "search": "python for beginners" }
   ```

3. **Question-authoring pass (you, the model, do this).** Load any existing
   `.ontrack/questions.json` and **keep every question already there** (answered
   ones must survive). Questions come in two roles — you do NOT need one per
   concept:
   - **Placement questions** (`placement: true`) — a **small compulsory set** that
     places the user's level. Author roughly **2 per difficulty tier**
     (`basic` / `intermediate` / `advanced`), spread across the main domains — aim
     for ~6, not one per concept. They **must be `graded`** (the level is scored
     from correct/incorrect) and **must carry a `level`**. This is the set the user
     is asked up front; keep it short.
   - **Optional questions** (no `placement`) — deeper, skippable probes for
     specific concepts. Add them for concepts worth pinning down, but the user can
     skip them all; they refine the path, they don't gate it. Don't flood.

   ```json
   { "questions": [
     { "id": "q:react/useeffect", "concept": "concept:react/useeffect",
       "domain": "framework", "mode": "graded", "level": "intermediate", "placement": true,
       "prompt": "What does useEffect do?",
       "options": ["Runs side effects after render", "Styles a component", "Defines a route"],
       "answer": 0 },
     { "id": "q:auth/jwt", "concept": "concept:auth/jwt",
       "domain": "security", "mode": "self_report", "level": "intermediate",
       "prompt": "How comfortable are you with where JWTs are stored and why?",
       "options": ["Confident", "Shaky", "New"] }
   ] }
   ```
   Rules:
   - `concept` MUST be a real inventory `id` (orphans are dropped by `build.py`).
   - `domain` ∈ `language | framework | system-design | security | tooling`.
   - `mode`:
     - `graded` for a **clean, checkable answer**. Give 3 plausible `options` and an
       integer `answer` index (0-based). Fair distractors, not trick questions.
     - `self_report` for a **judgment** concept where "correct" is situational. Use
       `["Confident","Shaky","New"]` (dashboard maps Confident→Learned, Shaky→Review,
       New→Learn). No `answer`. Self-report questions **cannot be placement** (no
       correct answer to score).
   - `level` orders the path AND scores the user's level — always set it on
     placement questions; set it on optional ones when you can.
   - `placement: true` only on graded questions with a `level`. Span the tiers so
     the user can actually be placed as Expert (needs advanced) or Beginner.
   - **Incremental**: never rewrite or re-order an existing question, and never add
     a second question for a concept that already has one.
   - You author the answer key here, but it never reaches the browser — the server
     strips `answer` before serving and grades server-side.

4. Regenerate once more (merges concepts, validates the questions you authored,
   then advances the cursor because authoring succeeded):
   ```
   python "${CLAUDE_PLUGIN_ROOT}/skills/ontrack/build.py" --advance-cursor
   ```
   Stale evidence, orphaned concepts, and invalid/orphaned questions drop out.

5. Start the dashboard server **in the background** (it blocks while serving):
   ```
   python "${CLAUDE_PLUGIN_ROOT}/skills/ontrack/server.py"
   ```
   Binds `127.0.0.1`, prints the URL (default `http://localhost:3874`).

6. Tell the user to open that URL. They pick a starting level (Beginner /
   Intermediate / **Expert**), then answer the short **Placement** set. From those
   answers the dashboard **derives their real level** (the hardest tier they mostly
   get right — the quiz overrides the declared pick) and builds the **Learning
   path**: things they got wrong always appear; untested concepts appear filtered
   to their level (a Beginner sees basics + foundational prereqs, an Expert only
   advanced gaps). Optional deeper questions are skippable. Answers save to
   `.ontrack/personal.json`. Re-run `/ontrack` after more coding — new concepts get
   new questions; answered ones are left alone.

Do not explain or teach the technologies in chat — the dashboard is the view, and
the user learns the path elsewhere.

## Boundaries

- Never hand-edit `inventory.json` — it is derived; rerun `build.py`.
- `concepts.json` and `questions.json` are your authoring output; `build.py`
  validates them against the current inventory (drops orphans/invalid).
- The server writes only `.ontrack/personal.json`; everything else is read-only to
  it, and the graded `answer` key is stripped before questions reach the browser.
- Confidence stays honest: `confirmed` = deterministic evidence, `inferred` =
  code-backed concept, `possible` = weak guess, `foundational` = prerequisite of a
  detected tech (no code line, beginner-only in the path).
- Knowledge state comes only from the user's answers — OnTrack never guesses it.
  The level is derived from the placement answers, not asserted by the tool.
