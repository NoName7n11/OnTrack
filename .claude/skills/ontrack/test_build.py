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
            '{"type":"dependency","name":"leftpad","source":"package.json","detected_at":"x"}\n'
            '{"type":"file_extension","name":"tsx","source":"App.tsx","detected_at":"x"}\n'
            '{"type":"file_extension","name":"py","source":"main.py","detected_at":"x"}\n'
            '{"type":"file_extension","name":"md","source":"notes.md","detected_at":"x"}\n')

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

        # Evidence is the source of truth: current repo facts with no evidence
        # should not appear in inventory.
        (root / ".ontrack" / "evidence.jsonl").write_text("")
        assert build.build_inventory(root) == {"items": []}

        # C-family IDs must not collide.
        (root / ".ontrack" / "evidence.jsonl").write_text(
            '{"type":"file_extension","name":"c","source":"a.c","detected_at":"x"}\n'
            '{"type":"file_extension","name":"cpp","source":"a.cpp","detected_at":"x"}\n'
            '{"type":"file_extension","name":"cs","source":"a.cs","detected_at":"x"}\n')
        (root / "a.c").write_text("int main() { return 0; }")
        (root / "a.cpp").write_text("int main() { return 0; }")
        (root / "a.cs").write_text("class A {}")
        ids = {i["id"] for i in build.build_inventory(root)["items"]}
        assert {"language:c", "language:cpp", "language:csharp"} <= ids, ids

    print("ok: confirmed inventory built, stale dropped, noise skipped, no churn")


def test_concept_merge():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "package.json").write_text('{"dependencies":{"react":"^18"}}')
        (root / "App.tsx").write_text("export {}")
        (root / ".ontrack").mkdir()
        (root / ".ontrack" / "evidence.jsonl").write_text(
            '{"type":"dependency","name":"react","source":"package.json","detected_at":"x"}\n')
        # concepts authored by the LLM pass
        (root / ".ontrack" / "concepts.json").write_text(json.dumps({"concepts": [
            # valid: parent confirmed (library:react), file exists
            {"id": "concept:react/useeffect", "name": "useEffect",
             "parent": "library:react", "confidence": "inferred",
             "what": "side effects", "where": ["App.tsx:3"], "search": "react useeffect"},
            # possible confidence is kept (dashboard hides it, build keeps it)
            {"id": "concept:react/suspense", "name": "Suspense",
             "parent": "library:react", "confidence": "possible", "where": []},
            # orphan: parent not confirmed -> dropped
            {"id": "concept:vue/ref", "name": "ref",
             "parent": "library:vue", "confidence": "inferred", "where": []},
            # bad confidence -> dropped
            {"id": "concept:react/x", "name": "x",
             "parent": "library:react", "confidence": "confirmed", "where": []},
            # where file missing -> pruned to empty, concept still kept
            {"id": "concept:react/memo", "name": "memo",
             "parent": "library:react", "confidence": "inferred",
             "where": ["gone.tsx:9"]},
        ]}), encoding="utf-8")

        inv = build.build_inventory(root)
        by_id = {i["id"]: i for i in inv["items"]}

        assert "library:react" in by_id, "confirmed parent present"
        assert by_id["concept:react/useeffect"]["kind"] == "concept"
        assert by_id["concept:react/useeffect"]["where"] == ["App.tsx:3"], "existing file kept"
        assert "concept:react/suspense" in by_id, "possible concept is kept in inventory"
        assert "concept:vue/ref" not in by_id, "orphan concept (no confirmed parent) dropped"
        assert "concept:react/x" not in by_id, "non-inferred/possible confidence dropped"
        assert by_id["concept:react/memo"]["where"] == [], "missing where file pruned"
        # every concept points at a real confirmed parent
        conf = {i["id"] for i in inv["items"] if i["confidence"] == "confirmed"}
        for it in inv["items"]:
            if it["kind"] == "concept":
                assert it["parent"] in conf, it

    print("ok: concepts merged, orphans/bad-confidence dropped, missing where pruned")


if __name__ == "__main__":
    test_build_inventory()
    test_concept_merge()
