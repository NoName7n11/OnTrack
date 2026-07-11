---
name: ontrack
description: Show what this project uses so you know what to learn. Regenerates the OnTrack inventory from tracked evidence (validated against the current repo) and displays it. Trigger on "/ontrack", "what does this project use", "what should I learn here", "ontrack".
---

# /ontrack

Surface what the project uses so the user can spot what they don't know and go
learn it. OnTrack reports **what exists + what to search for** — it does NOT teach,
and it does NOT claim to know what the user already knows. See `PLAN.md`.

> Build step 2: this shows the deterministic **confirmed** inventory as text.
> The local dashboard + status marking (`personal.json`) arrive in a later step.

## Steps

1. Regenerate the inventory from evidence, validated against the current repo:
   ```
   python .claude/skills/ontrack/build.py
   ```
   This rewrites `.ontrack/inventory.json` (only if changed). Stale evidence
   (removed deps, deleted file types) is dropped automatically.

2. Read `.ontrack/inventory.json` and present it grouped by `kind`
   (languages, libraries, ...). For each item show:
   - **name** and a one-line **what**
   - **where** it's used (real file paths in this repo)
   - a ready **search** query the user can paste into YouTube/Google

3. Keep it scannable. Do not explain the technologies or teach them — the whole
   point is that the user decides what they don't know and learns it elsewhere.

## Boundaries

- Never hand-edit `inventory.json` — it is derived; rerun `build.py` instead.
- `confirmed` items only exist here yet; `inferred`/`possible` concepts come with
  the later LLM pass.
