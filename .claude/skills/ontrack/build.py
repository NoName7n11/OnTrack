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


def _slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


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
    inv = build_inventory(root)
    changed = write_inventory(root, inv)
    state = "updated" if changed else "unchanged"
    print(f"ontrack: inventory {state} - {len(inv['items'])} items", file=sys.stderr)


if __name__ == "__main__":
    main()
