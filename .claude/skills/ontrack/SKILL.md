---
name: ontrack
description: Show what this project uses so you know what to learn. Regenerates the OnTrack inventory from tracked evidence (validated against the current repo) and displays it. Trigger on "/ontrack", "what does this project use", "what should I learn here", "ontrack".
---

# /ontrack

Surface what the project uses so the user can spot what they don't know and go
learn it. OnTrack reports **what exists + what to search for** — it does NOT teach,
and it does NOT claim to know what the user already knows. See `PLAN.md`.

## Steps

1. Regenerate the inventory from evidence, validated against the current repo:
   ```
   python .claude/skills/ontrack/build.py
   ```
   This rewrites `.ontrack/inventory.json` (only if changed). Stale evidence
   (removed deps, deleted file types) is dropped automatically.

2. Start the dashboard server **in the background** (it blocks while serving):
   ```
   python .claude/skills/ontrack/server.py
   ```
   It binds `127.0.0.1` and prints the URL (default
   `http://localhost:3874`, incrementing if the port is busy).

3. Tell the user to open that URL. On the dashboard they mark each item's status
   (Known / Somewhat / To learn / Ignore); items sort into **To Review /
   Learning / Learned / Ignored**. Marks save to `.ontrack/personal.json`.

You may also give a quick text summary of the inventory, but the dashboard is the
primary view. Do not explain or teach the technologies — the point is the user
decides what they don't know and learns it elsewhere.

## Boundaries

- Never hand-edit `inventory.json` — it is derived; rerun `build.py` instead.
- The server writes only `.ontrack/personal.json`; `inventory.json` is read-only to it.
- `confirmed` items only exist here yet; `inferred`/`possible` concepts come with
  the later LLM pass.
