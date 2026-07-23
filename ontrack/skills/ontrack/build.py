#!/usr/bin/env python3
"""OnTrack inventory builder - turn evidence into inventory.json (build step 2).

Confirmed items only: reconstructs current repo facts (reusing the hook's
scanner) and keeps evidence that is STILL true today. Stale evidence (a removed
dep, a deleted file type) drops out, though its line stays in evidence.jsonl.
Confidence is assigned HERE, never in evidence. `inferred`/`possible` concepts
come later (LLM pass, build step 5). See PLAN.md.
"""
import json
import re
import sys
from pathlib import Path

# Reuse the SessionEnd hook's scanner so detection lives in exactly one place.
_HOOKS = Path(__file__).resolve().parents[2] / "hooks"
sys.path.insert(0, str(_HOOKS))
import track  # noqa: E402

# File extensions worth surfacing as "languages/tech to learn", with a one-liner.
# Unmapped extensions (json, md, txt, lock, ...) are noise - skipped on purpose.
EXT_LANG = {
    "py":   ("python", "Python", "Python programming language", "python tutorial"),
    "js":   ("javascript", "JavaScript", "The language of the web", "javascript tutorial"),
    "jsx":  ("javascript-react", "JavaScript (React)", "JSX - React's HTML-in-JS syntax", "react jsx tutorial"),
    "ts":   ("typescript", "TypeScript", "Typed superset of JavaScript", "typescript tutorial"),
    "tsx":  ("typescript-react", "TypeScript (React)", "TSX - typed React components", "react typescript tutorial"),
    "rs":   ("rust", "Rust", "Systems language with memory safety", "rust tutorial"),
    "go":   ("go", "Go", "Google's concurrent systems language", "golang tutorial"),
    "java": ("java", "Java", "JVM object-oriented language", "java tutorial"),
    "rb":   ("ruby", "Ruby", "Dynamic scripting language", "ruby tutorial"),
    "php":  ("php", "PHP", "Server-side web language", "php tutorial"),
    "cs":   ("csharp", "C#", ".NET object-oriented language", "c# tutorial"),
    "cpp":  ("cpp", "C++", "Systems language with OOP", "c++ tutorial"),
    "c":    ("c", "C", "Low-level systems language", "c programming tutorial"),
    "html": ("html", "HTML", "Markup for web pages", "html tutorial"),
    "css":  ("css", "CSS", "Styling for web pages", "css tutorial"),
    "scss": ("sass", "Sass", "CSS with variables and nesting", "sass scss tutorial"),
}


CONCEPT_CONF = {"inferred", "possible"}
LEVELS = {"basic", "intermediate", "advanced"}
DOMAINS = {"language", "framework", "system-design", "security", "tooling"}
MODES = {"graded", "self_report"}


def _slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def _load_concepts(root, confirmed_ids):
    """Load LLM-authored concept items from concepts.json and validate them.

    Concepts are the `inferred`/`possible` layer written by the /ontrack skill's
    inference pass (Claude), kept in a separate file so build.py never clobbers
    them. Validation keeps them honest against the current repo:
    - confidence must be inferred|possible (confirmed is deterministic-only),
    - parent must be a currently-confirmed item id (orphans are dropped),
    - `where` file paths that no longer exist are pruned.
    """
    root = Path(root)
    data = None
    p = root / ".ontrack" / "concepts.json"
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = None
    out = []
    if not isinstance(data, dict):
        return out
    concepts = data.get("concepts", [])
    if not isinstance(concepts, list):
        return out
    for c in concepts:
        if not isinstance(c, dict):
            continue
        conf = c.get("confidence")
        cid = c.get("id")
        parent = c.get("parent")
        if conf not in CONCEPT_CONF:
            continue
        if not cid or ":" not in cid:
            continue
        if parent not in confirmed_ids:
            continue  # orphan concept — its library/language is gone
        where = []
        raw_where = c.get("where") or []
        root_resolved = root.resolve()
        if isinstance(raw_where, list):
            for w in raw_where:
                rel = str(w).split(":", 1)[0]
                path = (root / rel).resolve()
                try:
                    path.relative_to(root_resolved)
                except ValueError:
                    continue
                if path.exists():
                    where.append(w)
        if conf == "inferred" and not where:
            continue
        item = {
            "id": cid,
            "name": c.get("name") or cid,
            "kind": "concept",
            "parent": parent,
            "confidence": conf,
            "what": c.get("what", ""),
            "where": where,
            "search": c.get("search") or c.get("name") or cid,
            "from": c.get("from", []),
        }
        # Optional learning difficulty, used only to order the dashboard's Learning
        # path (basic before advanced). Invalid/absent values are simply omitted.
        if c.get("level") in LEVELS:
            item["level"] = c["level"]
        out.append(item)
    return out


def validate_questions(root, inventory_ids):
    """Load LLM-authored questions.json, keep only valid ones (build step 5).

    Questions are authored by the /ontrack skill (Claude) — one probe per concept.
    build.py is deterministic: it never writes questions, only validates them
    against the current inventory so the dashboard can trust the file.
    - concept must be a current inventory id (orphans dropped, like concepts),
    - mode ∈ graded|self_report, domain ∈ DOMAINS,
    - options is a list of ≥2 labels,
    - graded carries an int `answer` index within range; self_report has none,
    - level ∈ LEVELS is optional (used only to order the path).
    Duplicate ids keep the first. Stable order: sorted by id.
    """
    root = Path(root)
    p = root / ".ontrack" / "questions.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        return []

    out, seen = [], set()
    for q in data["questions"]:
        if not isinstance(q, dict):
            continue
        qid = q.get("id")
        concept = q.get("concept")
        mode = q.get("mode")
        domain = q.get("domain")
        options = q.get("options")
        if not isinstance(qid, str) or not qid or qid in seen:
            continue
        if concept not in inventory_ids:
            continue
        if mode not in MODES or domain not in DOMAINS:
            continue
        if not isinstance(options, list) or len(options) < 2:
            continue
        if not all(isinstance(o, str) and o for o in options):
            continue
        if not q.get("prompt"):
            continue
        item = {
            "id": qid,
            "concept": concept,
            "domain": domain,
            "mode": mode,
            "prompt": q["prompt"],
            "options": options,
        }
        if mode == "graded":
            ans = q.get("answer")
            if not isinstance(ans, int) or isinstance(ans, bool):
                continue
            if not (0 <= ans < len(options)):
                continue
            item["answer"] = ans
        if q.get("level") in LEVELS:
            item["level"] = q["level"]
        seen.add(qid)
        out.append(item)
    return sorted(out, key=lambda x: x["id"])


def write_questions(root, questions):
    """Rewrite questions.json with the validated set, only if changed (anti-churn)."""
    out = Path(root) / ".ontrack" / "questions.json"
    out.parent.mkdir(exist_ok=True)
    new = json.dumps({"questions": questions}, indent=2, ensure_ascii=False) + "\n"
    if out.exists() and out.read_text(encoding="utf-8") == new:
        return False
    out.write_text(new, encoding="utf-8")
    return True


def newest_session(root):
    """Latest `session` marker id in evidence.jsonl, or None if none written yet."""
    ev = Path(root) / ".ontrack" / "evidence.jsonl"
    if not ev.exists():
        return None
    latest = None
    for line in ev.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "session" and e.get("id"):
            if latest is None or e["id"] > latest:
                latest = e["id"]
    return latest


def read_cursor(root):
    """Return last_processed_session from state.json, or None (fresh clone)."""
    p = Path(root) / ".ontrack" / "state.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("last_processed_session")
    except json.JSONDecodeError:
        return None


def write_cursor(root, session_id):
    """Advance state.json's cursor to `session_id` (machine state, gitignored)."""
    if not session_id:
        return
    p = Path(root) / ".ontrack" / "state.json"
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps({"last_processed_session": session_id},
                            indent=2) + "\n", encoding="utf-8")


def build_inventory(root):
    """Return the inventory dict (confirmed items) for the repo at `root`."""
    root = Path(root)
    current = track.scan_project(root)  # fresh repo state for validation
    current_keys = {(o["type"], o["name"]) for o in current}
    current_by_key = {(o["type"], o["name"]): o for o in current}

    # Evidence lines, for provenance ("from") - safe if the file is absent.
    ev_path = root / ".ontrack" / "evidence.jsonl"
    evidence = []
    if ev_path.exists():
        for line in ev_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    evidence.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    def provenance(ev_type, ev_name):
        return [{"type": e["type"], "name": e["name"]}
                for e in evidence if e["type"] == ev_type and e["name"] == ev_name][:1]

    items = []
    # Evidence is the source of truth. Only evidence still true in the current
    # repo can become a confirmed inventory item.
    evidence_keys = sorted({(e.get("type"), e.get("name")) for e in evidence})
    for ev_type, ev_name in evidence_keys:
        if (ev_type, ev_name) not in current_keys:
            continue
        o = current_by_key[(ev_type, ev_name)]
        if o["type"] == "dependency":
            name = o["name"]
            items.append({
                "id": f"library:{_slug(name)}",
                "name": name,
                "kind": "library",
                "confidence": "confirmed",
                "what": f"Dependency `{name}`",
                "where": [o["source"]],
                "search": f"{name} tutorial",
                "from": provenance("dependency", name),
            })
        elif o["type"] == "file_extension":
            mapped = EXT_LANG.get(o["name"])
            if not mapped:
                continue  # skip noise extensions
            lang_id, label, what, search = mapped
            items.append({
                "id": f"language:{lang_id}",
                "name": label,
                "kind": "language",
                "confidence": "confirmed",
                "what": what,
                "where": [o["source"]],
                "search": search,
                "from": provenance("file_extension", o["name"]),
            })

    # Merge the LLM-authored concept layer (inferred/possible), validated against
    # the confirmed items just built. Confirmed wins on id collision (dedup below).
    confirmed_ids = {it["id"] for it in items}
    items.extend(_load_concepts(root, confirmed_ids))

    # Stable order → no churn: sort by id, dedup ids (keep first).
    seen, unique = set(), []
    for it in sorted(items, key=lambda x: x["id"]):
        if it["id"] not in seen:
            seen.add(it["id"])
            unique.append(it)
    return {"items": unique}


def write_inventory(root, inventory):
    """Write inventory.json only if content changed (avoid timestamp-free churn)."""
    out = Path(root) / ".ontrack" / "inventory.json"
    out.parent.mkdir(exist_ok=True)
    new = json.dumps(inventory, indent=2, ensure_ascii=False) + "\n"
    if out.exists() and out.read_text(encoding="utf-8") == new:
        return False
    out.write_text(new, encoding="utf-8")
    return True


def main():
    root = Path.cwd()
    advance_cursor = "--advance-cursor" in sys.argv[1:]
    inv = build_inventory(root)
    changed = write_inventory(root, inv)
    state = "updated" if changed else "unchanged"

    inventory_ids = {it["id"] for it in inv["items"]}
    questions = validate_questions(root, inventory_ids)
    q_changed = write_questions(root, questions)
    if advance_cursor:
        write_cursor(root, newest_session(root))

    print(f"ontrack: inventory {state} - {len(inv['items'])} items; "
          f"questions {'updated' if q_changed else 'unchanged'} - {len(questions)}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
