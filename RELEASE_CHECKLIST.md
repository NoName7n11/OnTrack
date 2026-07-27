# Release checklist

Run through this before sharing a build with testers. Most of it is automated —
CI covers the first two blocks on every PR — but re-check manually before a
release, because a green CI run does not prove the *installed plugin* works.

## Automated (CI must be green)

- [ ] `python ontrack/hooks/test_track.py` — evidence capture + hook cwd guard
- [ ] `python ontrack/skills/ontrack/test_build.py` — inventory, concepts, questions, cursor, private gitignore
- [ ] `python ontrack/skills/ontrack/test_server.py` — grading, level, GET whitelist, answer stripping
- [ ] `python tools/check_manifests.py` — every path the manifests reference exists
- [ ] `claude plugin validate ./ontrack`
- [ ] `claude plugin validate .`

## Version + docs

- [ ] `ontrack/.claude-plugin/plugin.json` version bumped (X.Y.Z)
- [ ] `.claude-plugin/marketplace.json` description still matches what the plugin does
- [ ] `README.md` describes the *current* flow (placement quiz → derived level → path)
- [ ] `ALPHA_TESTING.md` install steps and known limitations are still true
- [ ] `PLAN.md` matches the shipped data model

## Data safety (the "no surprises" block)

- [ ] `git status` is clean of `.ontrack/personal.json` and `.ontrack/state.json`
- [ ] `git log --stat` for this release contains **no** `personal.json`
- [ ] A fresh run in a throwaway git repo writes `.ontrack/.gitignore`, and
      `git check-ignore .ontrack/personal.json` confirms it is ignored
- [ ] The server still writes **only** `personal.json` (grep for other write paths)
- [ ] `curl localhost:3874/questions.json` shows **no `answer` key**

## Manual smoke test (do not skip)

Install the plugin the way a tester will — not from the working tree.

- [ ] `/plugin marketplace update ontrack` then reinstall; `/plugin` shows the new version
- [ ] `/ontrack` in a real project completes without an error
- [ ] The dashboard opens at the URL it printed
- [ ] Two projects at once each get their own port (3874 and 3875), and answers
      land in the project you are looking at
- [ ] Placement is short (~6 questions) and spans basic → advanced
- [ ] Answering places you at a sensible level, with a rationale
- [ ] The learning path is non-empty, ordered, and points at real `file:line`s
- [ ] Browser console shows **no errors**

## After release

- [ ] Tag the release / note the version in the PR description
- [ ] Confirm `ALPHA_TESTING.md` links resolve on the default branch
- [ ] Watch the issue tracker for the first install report
