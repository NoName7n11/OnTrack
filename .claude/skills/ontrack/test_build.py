#!/usr/bin/env python3
"""Self-check for build.py — run: python .claude/skills/ontrack/test_build.py"""
import json
import tempfile
from pathlib import Path

import build


def test_build_inventory():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "package.json").write_text('{"dependencies":{"react":"^18"}}')
        (root / "App.tsx").write_text("export {}")
        (root / "main.py").write_text("print(1)")
        (root / "notes.md").write_text("# hi")  # noise ext -> skipped
        # stale evidence: a dep that is NOT in any current manifest
        (root / ".ontrack").mkdir()
        (root / ".ontrack" / "evidence.jsonl").write_text(
            '{"type":"dependency","name":"react","source":"package.json","detected_at":"x"}\n'
            '{"type":"dependency","name":"leftpad","source":"package.json","detected_at":"x"}\n')

        inv = build.build_inventory(root)
        by_id = {i["id"]: i for i in inv["items"]}

        assert "library:react" in by_id, by_id
        assert "language:typescript-react" in by_id, by_id  # .tsx
        assert "language:python" in by_id, by_id            # .py
        assert not any(i["kind"] == "language" and i["name"] == "Markdown" for i in inv["items"])
        # stale dep dropped: leftpad was in evidence but not in the repo now
        assert "library:leftpad" not in by_id, "stale evidence must not survive"
        # confidence assigned here, all confirmed
        assert all(i["confidence"] == "confirmed" for i in inv["items"])
        # provenance links back to evidence
        assert by_id["library:react"]["from"] == [{"type": "dependency", "name": "react"}]

        # stable sort + valid ids
        ids = [i["id"] for i in inv["items"]]
        assert ids == sorted(ids), "items must be id-sorted"
        assert all(":" in i for i in ids), "ids are kind:slug"

        # write-only-if-changed
        assert build.write_inventory(root, inv) is True, "first write happens"
        assert build.write_inventory(root, inv) is False, "no rewrite when unchanged"
        loaded = json.loads((root / ".ontrack" / "inventory.json").read_text(encoding="utf-8"))
        assert loaded == inv, "round-trips through JSON"

    print("ok: confirmed inventory built, stale dropped, noise skipped, no churn")


if __name__ == "__main__":
    test_build_inventory()
