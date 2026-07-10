# OnTrack

**Know what you built.**

People build projects with AI agents (Claude Code, Codex) but often don't know
what's inside them — the agent picks the libraries, writes the auth, wires the
config. OnTrack passively tracks what your project actually uses as it grows, then
shows you an inventory you can scan: "here's everything this project uses." Spot
anything you don't recognize, mark where you stand, go learn it.

OnTrack's job is **awareness, not curriculum**. It tells you *what exists* and
*what to search for*. You learn elsewhere (YouTube, docs). It never claims to know
what you know — you mark that yourself.

> **Status:** early development. Design is in [PLAN.md](PLAN.md). Not yet functional.

## How it works

1. A Claude Code **`SessionEnd` hook** appends plain observations (deps, file
   types, commands run) to `.ontrack/evidence.jsonl` — boring facts, no guessing.
2. The **`/ontrack` skill** validates those observations against the current repo,
   runs a light inference pass for concept-level items, and writes
   `.ontrack/inventory.json` (what the project uses).
3. A **local dashboard** (`localhost:3874`) renders the inventory grouped into
   **To Review / Learning / Learned / Ignored**. You mark each item's status; it
   saves to `.ontrack/personal.json` (private, git-ignored).

Two files, two owners:

| File                      | Owner              | Committed? |
|---------------------------|--------------------|------------|
| `.ontrack/evidence.jsonl` | hook (observations)| yes        |
| `.ontrack/inventory.json` | `/ontrack` (derived)| yes       |
| `.ontrack/dashboard.html` | template (source)  | yes        |
| `.ontrack/personal.json`  | you (your status)  | **no**     |

The project's tech **is** your knowledge map — that's why tracking the project
tells you what you need to know.

## Design

Full architecture, data model, and rationale: **[PLAN.md](PLAN.md)**.

## Contributing

This is an open-source project — contributions welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache License 2.0](LICENSE).
