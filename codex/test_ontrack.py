#!/usr/bin/env python3
"""Self-check for Codex wrapper — run: python codex/test_ontrack.py"""
import json
import tempfile
from pathlib import Path

import ontrack


def test_snapshot_flow():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "package.json").write_text('{"dependencies":{"react":"^18"}}',
                                           encoding="utf-8")
        (root / "App.tsx").write_text("export {}", encoding="utf-8")

        count = ontrack.record(root)
        assert count >= 2, count
        assert (root / ".ontrack" / "evidence.jsonl").exists()

        inventory, changed = ontrack.build_inventory(root)
        assert changed is True
        by_id = {item["id"]: item for item in inventory["items"]}
        assert "library:react" in by_id, by_id
        assert "language:typescript-react" in by_id, by_id

        loaded = json.loads((root / ".ontrack" / "inventory.json").read_text(
            encoding="utf-8"))
        assert loaded == inventory

    print("ok: Codex wrapper records evidence and builds inventory")


if __name__ == "__main__":
    test_snapshot_flow()
