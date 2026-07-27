#!/usr/bin/env python3
"""Self-check for track.py — run: python ontrack/hooks/test_track.py"""
import json
import tempfile
from pathlib import Path

import track


def test_scan_and_append():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "package.json").write_text(json.dumps({
            "dependencies": {"react": "^18.0.0"},
            "devDependencies": {"vite": "^5.0.0"},
        }))
        (root / "requirements.txt").write_text("flask>=2.0  # web\njsonwebtoken\n")
        (root / "pyproject.toml").write_text(
            '[project]\ndependencies = ["requests>=2.0", "rich"]\n')
        (root / "App.tsx").write_text("export {}")
        (root / "main.py").write_text("print(1)")
        # noise that must be skipped
        (root / "node_modules").mkdir()
        (root / "node_modules" / "package.json").write_text('{"dependencies":{"junk":"1"}}')

        obs = track.scan_project(root)
        deps = {o["name"] for o in obs if o["type"] == "dependency"}
        exts = {o["name"] for o in obs if o["type"] == "file_extension"}

        assert {"react", "vite", "flask", "jsonwebtoken", "requests", "rich"} <= deps, deps
        assert "junk" not in deps, "node_modules must be skipped"
        assert {"tsx", "py", "json", "txt", "toml"} <= exts, exts
        assert all("confidence" not in o for o in obs), "observations carry no confidence"
        assert all(o["detected_at"].endswith("Z") for o in obs), "timestamps are UTC Z"
        assert next(o for o in obs if o["type"] == "file_extension" and o["name"] == "py")[
            "source"] == "main.py", "extension source is deterministic"

        # append writes one JSON line per observation, then a session marker
        track.append_evidence(root, obs)
        lines = (root / ".ontrack" / "evidence.jsonl").read_text().strip().splitlines()
        assert len(lines) == len(obs) + 1, (len(lines), len(obs))
        assert all(json.loads(ln) for ln in lines), "every line is valid JSON"
        marker = json.loads(lines[-1])
        assert marker["type"] == "session", "last line is a session boundary marker"
        assert marker["id"] == marker["detected_at"], "marker id is its timestamp"
        assert "name" not in marker, "session marker carries no observation"

        # dedup is within-scan: no duplicate (type,name) pairs
        keys = [(o["type"], o["name"]) for o in obs]
        assert len(keys) == len(set(keys)), "no in-scan duplicates"

    print("ok: scan detects deps + extensions, skips node_modules, no confidence field")


def test_cwd_guard():
    """A malformed/bad payload must never fall back to the process cwd.

    That fallback is how the hook once wrote evidence into an unrelated project.
    """
    import io
    import os
    import sys

    real_stdin = sys.stdin

    def with_stdin(text):
        sys.stdin = io.StringIO(text)
        try:
            return track._cwd_from_stdin()
        finally:
            sys.stdin = real_stdin

    def rejects(text, why):
        try:
            with_stdin(text)
        except ValueError:
            return
        assert False, f"should reject {why}"

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "f.txt").write_text("not a directory")
        # a real cwd in the payload is used as-is
        assert with_stdin(json.dumps({"cwd": str(root)})) == str(root)

        # no payload at all -> process cwd (standalone/test path)
        assert with_stdin("") == os.getcwd()
        assert with_stdin("   \n") == os.getcwd()
        # payload parsed but silent about cwd -> process cwd
        assert with_stdin('{"session_id":"x"}') == os.getcwd()

        # present but unusable -> raise, never guess
        rejects("{not json", "malformed JSON")
        rejects("[]", "non-object payload")
        rejects('"just a string"', "non-object payload")
        rejects(json.dumps({"cwd": str(root / "missing")}), "cwd that isn't a directory")
        rejects(json.dumps({"cwd": 123}), "non-string cwd")
        rejects(json.dumps({"cwd": str(root / "f.txt")}), "cwd pointing at a file")

        # main() reports failure and writes nothing
        sys.stdin = io.StringIO("{not json")
        try:
            code = track.main()
        finally:
            sys.stdin = real_stdin
        assert code == 1, "main signals failure on a bad payload"
        assert not (root / ".ontrack").exists(), "nothing written for a bad payload"

    print("ok: cwd guard refuses malformed/bad payloads instead of writing to the process cwd")


if __name__ == "__main__":
    test_scan_and_append()
    test_cwd_guard()
