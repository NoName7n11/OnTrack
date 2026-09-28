# OnTrack — Alpha Testing Guide

Thanks for testing OnTrack. This page is everything you need: install it, run it,
know what it wrote, and tell us what broke.

**What OnTrack is:** it watches what your project actually uses, asks you a short
placement quiz, and turns the gaps into a learning path pitched at your level.
It points you at what to learn — it does not teach it, and it does not guess your
level (it derives it from your answers).

**What we want from you:** whether install → run → answer → path actually works,
and whether the path is *useful* for your real project.

---

## 1. Install

Requires **Python 3.11+** on your PATH and Claude Code.

```
/plugin marketplace add NoName7n11/OnTrack
/plugin install ontrack@ontrack
```

Already have an older copy? Update it, or the old flow keeps running:

```
/plugin marketplace update ontrack
/plugin uninstall ontrack@ontrack
/plugin install ontrack@ontrack
```

Check the version you actually have — this guide describes **0.2.0+**:

```
/plugin
```

## 2. Run it

Open a project you built (ideally one an AI agent helped write), then:

```
/ontrack
```

It will:
1. read what the project uses (deps, languages),
2. read your code and name the concepts behind it,
3. write a short placement quiz,
4. start a local dashboard and print a URL — usually `http://localhost:3874`.

**Use the URL it prints.** If another dashboard is already running, OnTrack moves
to 3875, 3876, … so each project keeps its own.

A `SessionEnd` hook also records observations quietly whenever a Claude Code
session ends. That is normal — it only writes facts, never answers.

## 3. Use the dashboard

1. **Pick a starting level** — Beginner / Intermediate / Expert. This is only a
   starting point.
2. **Answer the placement questions** (~6). This is not a test; it decides how
   dense your path should be.
3. Your **derived level** appears at the top with a one-line reason. It can
   disagree with what you picked — the quiz wins, on purpose. Being rusty on
   basics does not demote you.
4. **Optional questions** are skippable. They sharpen the path; they do not gate it.
5. The **learning path** groups gaps by area, ordered basics-first, each with a
   one-line *what*, the `file:line` it is used in, and a search link.

Want to start over? Overwrite your answers file with `{"answers":{}}` (see below)
and reload the page.

## 4. What files OnTrack creates

Everything lives in a `.ontrack/` folder in **your project**.

| File                      | What it is                                   | Commit it? |
|---------------------------|----------------------------------------------|------------|
| `.ontrack/evidence.jsonl` | Append-only log of observed facts            | **yes**    |
| `.ontrack/inventory.json` | What the project uses now (derived)          | **yes**    |
| `.ontrack/concepts.json`  | Concepts behind your code (AI-authored)      | **yes**    |
| `.ontrack/questions.json` | The quiz (AI-authored)                       | **yes**    |
| `.ontrack/personal.json`  | **Your level and answers**                   | **no**     |
| `.ontrack/state.json`     | Resume cursor for this machine               | **no**     |
| `.ontrack/.gitignore`     | Written by OnTrack so the two above self-ignore | yes     |

You do **not** need to edit your own `.gitignore` — OnTrack writes a nested
`.ontrack/.gitignore` that hides `personal.json` and `state.json` automatically.
If you ever see either of those in `git status`, that is a bug — please report it.

Nothing outside `.ontrack/` is ever written.

## 5. Known limitations (don't report these)

- **Config files covered:** `Dockerfile`, `Makefile`, `Procfile`, `Vagrantfile`,
  `Rakefile`, `Jenkinsfile` (exact filename match). Others without an extension
  are still invisible to the scan.
- **Commands you run are not recorded.** Only manifests, file extensions, and the
  config filenames above.
- **Manifests covered:** `package.json`, `requirements.txt`, `pyproject.toml`,
  `Cargo.toml`, `go.mod`, `Gemfile`, `composer.json`. Others (e.g. `pom.xml`,
  `*.csproj`) are **not** parsed yet.
- **The quiz is generated per project**, so quality varies with how readable your
  code is. Bad questions *are* worth reporting (see below).
- **The dashboard is local-only**, bound to `127.0.0.1`. No accounts, no sync,
  nothing leaves your machine.
- **Level is derived from ~6 questions.** It is a rough pitch, not an assessment.
- **Windows, macOS, Linux** are all expected to work; Windows gets the most testing.

## 6. Reporting feedback

Open an issue: <https://github.com/NoName7n11/OnTrack/issues/new/choose>

The bug template asks for OS, Claude Code version, project type, and where it
broke. The most useful reports are:

- install or run errors (paste the exact message),
- the dashboard not opening,
- **concepts that are wrong or missing** for your project,
- **questions that are wrong, unfair, or trick questions**,
- a derived level that felt clearly unfair,
- a learning path that was useless, or so long it felt pointless,
- anything private showing up in `git status`.

Feel free to attach `.ontrack/concepts.json` and `.ontrack/questions.json` — they
contain no personal data. **Do not** attach `personal.json` unless you want to
share your answers.

## 7. Running the pieces by hand (optional)

Useful if `/ontrack` misbehaves and you want to isolate the step.

```
python <plugin>/hooks/track.py            # record evidence for the current dir
python <plugin>/skills/ontrack/build.py   # rebuild inventory + validate the quiz
python <plugin>/skills/ontrack/server.py  # serve the dashboard from ./.ontrack
```

`Ctrl-C` stops the server. To replay the quiz from scratch, reset your answers:

```powershell
'{"answers":{}}' | Set-Content .\.ontrack\personal.json     # PowerShell
```
```bash
echo '{"answers":{}}' > .ontrack/personal.json              # bash
```

To regenerate the quiz itself, delete `concepts.json`, `questions.json`,
`inventory.json` and `state.json`, then run `/ontrack` again.
