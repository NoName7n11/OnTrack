# Contributing to OnTrack

Thanks for your interest. OnTrack is early-stage — the design is settled in
[PLAN.md](PLAN.md); implementation is just beginning.

## Before you start

Read [PLAN.md](PLAN.md). It defines the architecture and the invariants that keep
the design honest. A few are non-negotiable:

- **The hook writes observations only** — no confidence, no interpretation. Facts in.
- **`inventory.json` is derived**, regenerated from evidence + current repo state.
  Never hand-edit it.
- **`personal.json` is the only file the dashboard writes**, and it holds user
  status only. It is git-ignored and never committed.
- **OnTrack does not teach.** It surfaces what a project uses and a search term.
  Learning happens elsewhere. Keep features on the right side of that line.

## Workflow

1. Fork and branch from `main` (`feature/short-name`).
2. Keep changes small and focused. Match the surrounding style.
3. Non-trivial logic ships with one runnable check.
4. Open a PR describing *what* and *why*. Link any related issue.

## Reporting bugs / ideas

Open a GitHub issue. For bugs, include repro steps and your OS. For design changes,
say which PLAN.md invariant they touch, if any.

## License

By contributing, you agree your contributions are licensed under the
[Apache License 2.0](LICENSE).
