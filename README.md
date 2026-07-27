# OnTrack

[![CI](https://github.com/NoName7n11/OnTrack/actions/workflows/ci.yml/badge.svg)](https://github.com/NoName7n11/OnTrack/actions/workflows/ci.yml)

**Know what you built.**

People build projects with AI agents (Claude Code, Codex) but often don't know
what's inside them — the agent picks the libraries, writes the auth, wires the
config. OnTrack passively tracks what your project actually uses, works out the
concepts behind it, then **asks you a short placement quiz** to gauge what you
know. From your answers it builds a **step-by-step learning path** — what to go
learn, pitched to your level.

OnTrack's job is **a route, not a course**. It tells you *what exists* and *what
to search for*; you learn elsewhere (YouTube, docs). It doesn't teach the
material, and it doesn't guess your level — it derives it from your answers.

> **Status:** alpha. The full loop works end-to-end — passive tracking, concept
> inference, a placement quiz that derives your level, and a local dashboard that
> turns the gaps into a level-pitched learning path.
>
> **Testing it? Start with [ALPHA_TESTING.md](ALPHA_TESTING.md)** — install steps,
> what files get written, known limitations, and how to report what breaks.

## Install

OnTrack is packaged as a Claude Code plugin. This repo is its marketplace.

```
/plugin marketplace add NoName7n11/OnTrack
/plugin install ontrack@ontrack
```

Then in any project, run `/ontrack` to scan the project, generate the questions,
and open the dashboard. A `SessionEnd` hook records observations automatically.
(Requires Python 3.11+ on PATH.)

### Updating

Installing a plugin copies it — a new release does **not** reach an existing
install on its own. Run `/plugin` to see the version you actually have; if it is
older than the current one, update it:

```
/plugin marketplace update ontrack
/plugin uninstall ontrack@ontrack
/plugin install ontrack@ontrack
```

Current version: **0.3.0**. Anything older is missing the fixes that keep your
answers in the right project and out of git — update before testing.

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
     (React → `useEffect`, JSX; a JWT dep → signing, verify, expiry), plus a few
     `foundational` prerequisites a beginner would need (e.g. "Python basics").
   - **questions** → `.ontrack/questions.json`: a small compulsory **placement**
     set (spans difficulty) that places your level, plus optional, skippable
     probes. `graded` multiple-choice where there's a clean answer, or
     `self_report` (Confident / Shaky / New) for judgment topics.

   `build.py` validates everything against the current repo and writes
   `.ontrack/inventory.json`. Stale deps and orphaned concepts/questions drop out.
3. A **local dashboard** (`localhost:3874`) runs the assessment. You pick a
   starting level (Beginner / Intermediate / Expert), answer the placement set,
   and OnTrack **derives your real level** from the answers (the hardest tier you
   mostly get right wins — being rusty on basics doesn't demote you; the quiz
   overrides your declared pick). The **learning path** is then pitched to that
   level: things you got wrong always show; untested concepts appear filtered to
   your level (a Beginner sees basics + foundational prereqs, an Expert only
   advanced gaps). Each step has a one-line *what*, the *file:line* it's used in,
   and a search link. Your level + answers save to `.ontrack/personal.json`,
   which OnTrack keeps out of git for you (see below).

Each project gets its own dashboard: if 3874 is already serving another project,
OnTrack moves to 3875, 3876, … and prints the URL it actually bound. Use the
printed one — answers always go to the project you are looking at.

The graded answer key never reaches the browser — the server strips it and grades
server-side.

Data files, by owner:

| File                      | Owner                      | Committed? |
|---------------------------|----------------------------|------------|
| `.ontrack/evidence.jsonl` | hook (observations)        | yes        |
| `.ontrack/concepts.json`  | `/ontrack` (LLM)           | yes        |
| `.ontrack/questions.json` | `/ontrack` (LLM)           | yes        |
| `.ontrack/inventory.json` | `build.py` (derived)       | yes        |
| `.ontrack/.gitignore`     | `build.py` (written for you) | yes      |
| `.ontrack/personal.json`  | you (level + answers)      | **no**     |
| `.ontrack/state.json`     | `build.py` (resume cursor) | **no**     |

You don't need to touch your own `.gitignore`: OnTrack writes a nested
`.ontrack/.gitignore` that hides `personal.json` (your level and answers) and
`state.json` (a per-machine cursor), while the shared project truth beside them
still commits normally. Nothing outside `.ontrack/` is ever written.

The project's tech **is** your knowledge map — that's why tracking the project
tells you what you need to know.

## Running the dashboard by hand

`/ontrack` does this for you, but you can drive the pieces directly (handy for
alpha testing). From a project that already has an `.ontrack/` folder:

```
python ontrack/skills/ontrack/server.py
```

It serves the current directory's `.ontrack/` on `127.0.0.1:3874`, moving to the
next free port if that one is taken. Open the printed URL; `Ctrl-C` stops it. To
replay the level prompt, reset your answers: overwrite `.ontrack/personal.json`
with `{"answers":{}}`.

To regenerate the data from scratch: run `ontrack/hooks/track.py` in the project
(records evidence), then `ontrack/skills/ontrack/build.py` (builds inventory +
validates questions). The concept/question authoring in between is the model's
job — that's what `/ontrack` orchestrates.

## Development

No dependencies — the tests are stdlib Python and run directly:

```
python ontrack/hooks/test_track.py            # evidence capture + hook cwd guard
python ontrack/skills/ontrack/test_build.py   # inventory, concepts, questions, cursor
python ontrack/skills/ontrack/test_server.py  # grading, level, whitelist, answer stripping
python tools/check_manifests.py               # manifests point at files that exist
```

CI runs all of these on Linux and Windows (Python 3.11 and 3.12) plus
`claude plugin validate` for the plugin and the marketplace, on every push and PR.
Before cutting a release, walk **[RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)** —
it covers the data-safety checks and a manual smoke test that CI can't do.

## Design

Full architecture, data model, and rationale: **[PLAN.md](PLAN.md)**.

## Contributing

This is an open-source project — contributions welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache License 2.0](LICENSE).
