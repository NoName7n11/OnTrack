#!/usr/bin/env python3
"""Self-check for server.py — run: python .claude/skills/ontrack/test_server.py"""
import json
import tempfile
from pathlib import Path

import server


def test_set_status():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / ".ontrack").mkdir()
        (root / ".ontrack" / "inventory.json").write_text(json.dumps({
            "items": [
                {"id": "library:react"},
                {"id": "language:python"},
            ]
        }), encoding="utf-8")

        # valid status writes personal.json (and only that)
        server.set_status(root, "library:react", "known")
        p = root / ".ontrack" / "personal.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["status"]["library:react"] == "known", data
        assert {x.name for x in (root / ".ontrack").iterdir()} == {
            "inventory.json", "personal.json"
        }, "only personal.json added by server"

        # second write merges, doesn't clobber
        server.set_status(root, "language:python", "to_learn")
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["status"] == {"library:react": "known",
                                  "language:python": "to_learn"}, data

        # overwrite same id
        server.set_status(root, "library:react", "somewhat")
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["status"]["library:react"] == "somewhat"

        # invalid status rejected, file unchanged
        before = p.read_text(encoding="utf-8")
        for bad in ("learning", "", None, "KNOWN"):
            try:
                server.set_status(root, "x", bad)
                assert False, f"should reject {bad!r}"
            except ValueError:
                pass
        assert p.read_text(encoding="utf-8") == before, "bad status must not write"

        # empty id rejected
        try:
            server.set_status(root, "", "known")
            assert False, "should reject empty id"
        except ValueError:
            pass

        # unknown inventory id rejected
        try:
            server.set_status(root, "library:missing", "known")
            assert False, "should reject unknown item id"
        except ValueError:
            pass

        # inventory.json is never created/touched by the server
        inventory_before = (root / ".ontrack" / "inventory.json").read_text(encoding="utf-8")
        server.set_status(root, "language:python", "ignored")
        assert (root / ".ontrack" / "inventory.json").read_text(
            encoding="utf-8") == inventory_before

    print("ok: set_status validates, merges, writes only personal.json atomically")


if __name__ == "__main__":
    test_set_status()
