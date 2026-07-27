#!/usr/bin/env python3
"""Structural check for the plugin + marketplace manifests.

`claude plugin validate` checks manifest SHAPE; this checks that what the
manifests POINT AT actually exists — the failure mode this repo has actually hit
(files moved during the plugin restructure, a hook command left pointing at a
path that no longer exists). Stdlib only, so CI never depends on npm or auth.

Run: python tools/check_manifests.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "ontrack"

errors = []


def err(msg):
    errors.append(msg)


def load(path):
    if not path.exists():
        err(f"missing manifest: {path.relative_to(ROOT)}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        err(f"{path.relative_to(ROOT)} is not valid JSON: {e}")
        return None


def check_plugin():
    data = load(PLUGIN_DIR / ".claude-plugin" / "plugin.json")
    if data is None:
        return
    for key in ("name", "description", "version"):
        if not data.get(key):
            err(f"plugin.json is missing required key: {key}")
    version = data.get("version", "")
    if version and not re.fullmatch(r"\d+\.\d+\.\d+", version):
        err(f"plugin.json version is not X.Y.Z: {version!r}")


def check_marketplace():
    data = load(ROOT / ".claude-plugin" / "marketplace.json")
    if data is None:
        return
    for key in ("name", "owner", "plugins"):
        if not data.get(key):
            err(f"marketplace.json is missing required key: {key}")
    for entry in data.get("plugins", []) or []:
        source = entry.get("source")
        if not source:
            err("marketplace.json plugin entry has no source")
            continue
        target = (ROOT / source).resolve()
        if not target.is_dir():
            err(f"marketplace source does not exist: {source}")
        elif not (target / ".claude-plugin" / "plugin.json").exists():
            err(f"marketplace source has no plugin.json: {source}")


def check_hook_commands():
    """Every ${CLAUDE_PLUGIN_ROOT}/... path a hook runs must exist."""
    data = load(PLUGIN_DIR / "hooks" / "hooks.json")
    if data is None:
        return
    found = False
    for event, groups in (data.get("hooks") or {}).items():
        for group in groups or []:
            for hook in group.get("hooks", []) or []:
                command = hook.get("command", "")
                for rel in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"'\s]+)", command):
                    found = True
                    if not (PLUGIN_DIR / rel).exists():
                        err(f"{event} hook points at a missing file: {rel}")
    if not found:
        err("hooks.json declares no ${CLAUDE_PLUGIN_ROOT} command to check")


def check_skill_files():
    """The skill's own runtime files must be present in the packaged plugin."""
    skill = PLUGIN_DIR / "skills" / "ontrack"
    for name in ("SKILL.md", "build.py", "server.py", "dashboard.html"):
        if not (skill / name).exists():
            err(f"skill file missing from the plugin: skills/ontrack/{name}")


def main():
    check_plugin()
    check_marketplace()
    check_hook_commands()
    check_skill_files()
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        print(f"\n{len(errors)} manifest problem(s)", file=sys.stderr)
        return 1
    print("ok: manifests valid and every referenced file exists")
    return 0


if __name__ == "__main__":
    sys.exit(main())
