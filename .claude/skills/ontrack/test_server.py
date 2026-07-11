#!/usr/bin/env python3
"""Self-check for server.py — run: python .claude/skills/ontrack/test_server.py"""
import json
import tempfile
from pathlib import Path

import server


def test_set_status():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)

        # valid status writes personal.json (and only that)
        server.set_status(root, "library:react", "known")
        p = root / ".ontrack" / "personal.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["status"]["library:react"] == "known", data
        assert list((root / ".ontrack").iterdir()) == [p], "only personal.json written"

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

        # inventory.json is never created/touched by the server
        assert not (root / ".ontrack" / "inventory.json").exists()

    print("ok: set_status validates, merges, writes only personal.json atomically")


if __name__ == "__main__":
    test_set_status()
