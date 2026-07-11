#!/usr/bin/env python3
"""Self-check for track.py — run: python .claude/hooks/test_track.py"""
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

        # append writes one JSON line per observation
        track.append_evidence(root, obs)
        lines = (root / ".ontrack" / "evidence.jsonl").read_text().strip().splitlines()
        assert len(lines) == len(obs), (len(lines), len(obs))
        assert all(json.loads(ln) for ln in lines), "every line is valid JSON"

        # dedup is within-scan: no duplicate (type,name) pairs
        keys = [(o["type"], o["name"]) for o in obs]
        assert len(keys) == len(set(keys)), "no in-scan duplicates"

    print("ok: scan detects deps + extensions, skips node_modules, no confidence field")


if __name__ == "__main__":
    test_scan_and_append()
