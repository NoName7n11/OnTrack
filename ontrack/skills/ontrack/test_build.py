#!/usr/bin/env python3
"""Self-check for build.py — run: python ontrack/skills/ontrack/test_build.py"""
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
            # valid: parent confirmed (library:react), file exists, valid level kept
            {"id": "concept:react/useeffect", "name": "useEffect",
             "parent": "library:react", "confidence": "inferred", "level": "basic",
             "what": "side effects", "where": ["App.tsx:3"], "search": "react useeffect"},
            # possible confidence is kept; invalid level is dropped from the item
            {"id": "concept:react/suspense", "name": "Suspense",
             "parent": "library:react", "confidence": "possible", "level": "expert",
             "where": []},
            # orphan: parent not confirmed -> dropped
            {"id": "concept:vue/ref", "name": "ref",
             "parent": "library:vue", "confidence": "inferred", "where": []},
            # bad confidence -> dropped
            {"id": "concept:react/x", "name": "x",
             "parent": "library:react", "confidence": "confirmed", "where": []},
            # where file missing -> inferred concept dropped
            {"id": "concept:react/memo", "name": "memo",
             "parent": "library:react", "confidence": "inferred",
             "where": ["gone.tsx:9"]},
            # where traversal outside repo -> pruned, inferred concept dropped
            {"id": "concept:react/outside", "name": "outside",
             "parent": "library:react", "confidence": "inferred",
             "where": ["../outside.tsx:1"]},
            # malformed entries are ignored
            None,
            [],
        ]}), encoding="utf-8")

        inv = build.build_inventory(root)
        by_id = {i["id"]: i for i in inv["items"]}

        assert "library:react" in by_id, "confirmed parent present"
        assert by_id["concept:react/useeffect"]["kind"] == "concept"
        assert by_id["concept:react/useeffect"]["where"] == ["App.tsx:3"], "existing file kept"
        assert "concept:react/suspense" in by_id, "possible concept is kept in inventory"
        assert "concept:vue/ref" not in by_id, "orphan concept (no confirmed parent) dropped"
        assert "concept:react/x" not in by_id, "non-inferred/possible confidence dropped"
        assert "concept:react/memo" not in by_id, "inferred concept with no evidence dropped"
        assert "concept:react/outside" not in by_id, "outside-repo where path dropped"
        assert by_id["concept:react/useeffect"]["level"] == "basic", "valid level kept"
        assert "level" not in by_id["concept:react/suspense"], "invalid level omitted"
        # every concept points at a real confirmed parent
        conf = {i["id"] for i in inv["items"] if i["confidence"] == "confirmed"}
        for it in inv["items"]:
            if it["kind"] == "concept":
                assert it["parent"] in conf, it

        for bad in ("[]", "null", '"oops"', '{"concepts": {}}'):
            (root / ".ontrack" / "concepts.json").write_text(bad, encoding="utf-8")
            inv = build.build_inventory(root)
            assert all(i["kind"] != "concept" for i in inv["items"]), bad

    print("ok: concepts merged, orphans/bad-confidence dropped, missing where pruned")


def test_validate_questions():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / ".ontrack").mkdir()
        inv_ids = {"concept:react/useeffect", "concept:auth/jwt"}
        (root / ".ontrack" / "questions.json").write_text(json.dumps({"questions": [
            # valid graded: answer index in range, level kept
            {"id": "q:react/useeffect", "concept": "concept:react/useeffect",
             "domain": "framework", "mode": "graded", "level": "basic",
             "prompt": "What does useEffect do?",
             "options": ["Runs after render", "Styles", "Routes"], "answer": 0},
            # valid self_report: no answer needed
            {"id": "q:auth/jwt", "concept": "concept:auth/jwt",
             "domain": "security", "mode": "self_report",
             "prompt": "Comfortable with JWT storage?",
             "options": ["Confident", "Shaky", "New"]},
            # orphan: concept not in inventory -> dropped
            {"id": "q:vue/ref", "concept": "concept:vue/ref", "domain": "framework",
             "mode": "graded", "prompt": "?", "options": ["a", "b"], "answer": 0},
            # graded with out-of-range answer -> dropped
            {"id": "q:bad/answer", "concept": "concept:react/useeffect",
             "domain": "framework", "mode": "graded", "prompt": "?",
             "options": ["a", "b"], "answer": 5},
            # graded missing answer -> dropped
            {"id": "q:bad/noanswer", "concept": "concept:react/useeffect",
             "domain": "framework", "mode": "graded", "prompt": "?",
             "options": ["a", "b"]},
            # bad domain -> dropped
            {"id": "q:bad/domain", "concept": "concept:auth/jwt", "domain": "vibes",
             "mode": "self_report", "prompt": "?", "options": ["a", "b"]},
            # too few options -> dropped
            {"id": "q:bad/opts", "concept": "concept:auth/jwt", "domain": "security",
             "mode": "self_report", "prompt": "?", "options": ["only"]},
            # bool answer must not pass as int
            {"id": "q:bad/bool", "concept": "concept:react/useeffect",
             "domain": "framework", "mode": "graded", "prompt": "?",
             "options": ["a", "b"], "answer": True},
            None, [],
        ]}), encoding="utf-8")

        qs = build.validate_questions(root, inv_ids)
        by_id = {q["id"]: q for q in qs}
        assert set(by_id) == {"q:react/useeffect", "q:auth/jwt"}, by_id
        assert by_id["q:react/useeffect"]["answer"] == 0
        assert by_id["q:react/useeffect"]["level"] == "basic"
        assert "answer" not in by_id["q:auth/jwt"], "self_report has no answer key"
        assert [q["id"] for q in qs] == sorted(q["id"] for q in qs), "id-sorted"

        # write-only-if-changed
        assert build.write_questions(root, qs) is True
        assert build.write_questions(root, qs) is False

        for bad in ("[]", "null", '{"questions": {}}'):
            (root / ".ontrack" / "questions.json").write_text(bad, encoding="utf-8")
            assert build.validate_questions(root, inv_ids) == [], bad

    print("ok: questions validated (orphans/bad-answer/domain/options dropped)")


def test_cursor():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / ".ontrack").mkdir()
        # fresh clone: no state.json
        assert build.read_cursor(root) is None
        assert build.newest_session(root) is None

        (root / ".ontrack" / "evidence.jsonl").write_text(
            '{"type":"dependency","name":"react","source":"p","detected_at":"x"}\n'
            '{"type":"session","id":"2026-07-20T10:00:00Z","detected_at":"2026-07-20T10:00:00Z"}\n'
            '{"type":"file_extension","name":"tsx","source":"a","detected_at":"y"}\n'
            '{"type":"session","id":"2026-07-21T10:00:00Z","detected_at":"2026-07-21T10:00:00Z"}\n')
        assert build.newest_session(root) == "2026-07-21T10:00:00Z", "picks the latest marker"

        build.write_cursor(root, build.newest_session(root))
        assert build.read_cursor(root) == "2026-07-21T10:00:00Z"
        # advancing to None is a no-op (nothing to process)
        build.write_cursor(root, None)
        assert build.read_cursor(root) == "2026-07-21T10:00:00Z"

    print("ok: cursor reads/advances to newest session marker; fresh clone = None")


if __name__ == "__main__":
    test_build_inventory()
    test_concept_merge()
    test_validate_questions()
    test_cursor()
