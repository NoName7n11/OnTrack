# OnTrack

**Know what you built.**

People build projects with AI agents (Claude Code, Codex) but often don't know
what's inside them — the agent picks the libraries, writes the auth, wires the
config. OnTrack passively tracks what your project actually uses, works out the
concepts behind it, then **asks you a few questions** to see what you already
know. From your answers it builds a **step-by-step learning path** — what to go
learn, grouped by area and ordered.

OnTrack's job is **a route, not a course**. It tells you *what exists* and *what
to search for*; you learn elsewhere (YouTube, docs). It doesn't teach the
material, and it doesn't guess what you know — it asks.

> **Status:** alpha. The full loop works end-to-end — passive tracking, concept
> inference, a hybrid assessment (graded + self-report), and a local dashboard
> that turns your answers into a learning path.

## Install

OnTrack is packaged as a Claude Code plugin. This repo is its marketplace.

```
/plugin marketplace add NoName7n11/OnTrack
/plugin install ontrack@ontrack
```

Then in any project, run `/ontrack` to scan the project, generate the questions,
and open the dashboard. A `SessionEnd` hook records observations automatically.
(Requires Python 3.11+ on PATH.)

To hack on it locally without installing, load the plugin directly:

```
claude --plugin-dir ./ontrack
```

## How it works

1. A Claude Code **`SessionEnd` hook** appends plain observations (deps, file
   types) to `.ontrack/evidence.jsonl` — boring facts, no guessing — plus a
   `session` marker so `/ontrack` can resume where it left off.
2. The **`/ontrack` skill** reads the code and does two authoring passes:
   - **concepts** → `.ontrack/concepts.json`: the specific things in use
     (React → `useEffect`, JSX; a JWT dep → signing, verify, expiry).
   - **questions** → `.ontrack/questions.json`: one assessment question per
     concept. `graded` multiple-choice where there's a clean answer, or
     `self_report` (Confident / Shaky / New) for judgment topics like security
     posture.

   `build.py` then validates everything against the current repo and writes
   `.ontrack/inventory.json` (what the project uses). Stale deps and orphaned
   concepts/questions drop out automatically.
3. A **local dashboard** (`localhost:3874`) runs the assessment. You declare your
   level once, answer the questions, and the **Learning path** fills in — grouped
   by domain (Language / Framework / System design / Security / Tooling) and
   ordered by difficulty. Correct answers (and "Confident") drop out; wrong ones
   (and "New" / "Shaky") become steps to learn, each with a one-line *what*, the
   *file:line* it's used in, and a ready search link. Your level + answers save to
   `.ontrack/personal.json` (private, git-ignored).

The graded answer key never reaches the browser — the server strips it and grades
server-side.

Data files, by owner:

| File                      | Owner                     | Committed? |
|---------------------------|---------------------------|------------|
| `.ontrack/evidence.jsonl` | hook (observations)       | yes        |
| `.ontrack/concepts.json`  | `/ontrack` (LLM)          | yes        |
| `.ontrack/questions.json` | `/ontrack` (LLM)          | yes        |
| `.ontrack/inventory.json` | `build.py` (derived)      | yes        |
| `.ontrack/personal.json`  | you (level + answers)     | **no**     |
| `.ontrack/state.json`     | `build.py` (resume cursor)| **no**     |

The project's tech **is** your knowledge map — that's why tracking the project
tells you what you need to know.

## Running the dashboard by hand

`/ontrack` does this for you, but you can drive the pieces directly (handy for
alpha testing). From a project that already has an `.ontrack/` folder:

```
python ontrack/skills/ontrack/server.py
```

It serves the current directory's `.ontrack/` on `127.0.0.1:3874` (bumps the port
if busy). Open the printed URL; `Ctrl-C` stops it. To replay the level prompt,
reset your answers: overwrite `.ontrack/personal.json` with `{"answers":{}}`.

To regenerate the data from scratch: run `ontrack/hooks/track.py` in the project
(records evidence), then `ontrack/skills/ontrack/build.py` (builds inventory +
validates questions). The concept/question authoring in between is the model's
job — that's what `/ontrack` orchestrates.

## Design

Full architecture, data model, and rationale: **[PLAN.md](PLAN.md)**.

## Contributing

This is an open-source project — contributions welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache License 2.0](LICENSE).
