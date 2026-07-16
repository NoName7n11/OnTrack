#!/usr/bin/env python3
"""Codex-facing OnTrack wrapper.

Claude gets plugin hooks and slash commands. Codex currently uses this local
wrapper: record observations, build inventory, then optionally serve the
dashboard. The source of truth stays the same `.ontrack/` data format.
"""
import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACK_PATH = ROOT / "ontrack" / "hooks" / "track.py"
BUILD_PATH = ROOT / "ontrack" / "skills" / "ontrack" / "build.py"
SERVER_PATH = ROOT / "ontrack" / "skills" / "ontrack" / "server.py"
TEMPLATE_PATH = ROOT / "ontrack" / "skills" / "ontrack" / "dashboard.html"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


track = _load("ontrack_track", TRACK_PATH)
build = _load("ontrack_build", BUILD_PATH)
server = _load("ontrack_server", SERVER_PATH)


def record(project):
    observations = track.scan_project(project)
    track.append_evidence(project, observations)
    return len(observations)


def build_inventory(project):
    inventory = build.build_inventory(project)
    changed = build.write_inventory(project, inventory)
    return inventory, changed


def print_summary(inventory):
    items = inventory.get("items", [])
    print(f"OnTrack inventory: {len(items)} items")
    for item in items:
        where = ", ".join(item.get("where") or [])
        print(f"- {item['id']} [{item.get('confidence')}] {item.get('name')}: {where}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run OnTrack from Codex/local CLI.")
    parser.add_argument("command", choices=["record", "build", "snapshot", "serve"],
                        help="record observations, build inventory, do both, or serve dashboard")
    parser.add_argument("--project", default=".",
                        help="project root to write/read .ontrack data from")
    parser.add_argument("--background", action="store_true",
                        help="for serve: run the dashboard detached, logging stdout/stderr "
                             "to .ontrack/server.out and .ontrack/server.err")
    args = parser.parse_args(argv)

    project = Path(args.project).resolve()
    if args.command == "record":
        print(f"ontrack: recorded {record(project)} observations")
        return 0
    if args.command == "build":
        inventory, changed = build_inventory(project)
        print(f"ontrack: inventory {'updated' if changed else 'unchanged'}")
        print_summary(inventory)
        return 0
    if args.command == "snapshot":
        print(f"ontrack: recorded {record(project)} observations")
        inventory, changed = build_inventory(project)
        print(f"ontrack: inventory {'updated' if changed else 'unchanged'}")
        print_summary(inventory)
        return 0
    if args.command == "serve":
        inventory, changed = build_inventory(project)
        print(f"ontrack: inventory {'updated' if changed else 'unchanged'}", file=sys.stderr)
        if args.background:
            serve_background(project)
        else:
            server.run(project, TEMPLATE_PATH)
        return 0
    return 2


def serve_background(project):
    """Launch the dashboard server detached, logging to .ontrack/server.{out,err}.

    server.run() blocks (serve_forever), which is wrong for an agent that must keep
    working after starting the dashboard. Running server.py as a detached child with
    its output redirected keeps the agent's turn free; the port (and any fallback) is
    recorded in server.err. This is what the .ontrack/server.{out,err} gitignore
    entries exist for.
    """
    ontrack_dir = project / ".ontrack"
    ontrack_dir.mkdir(exist_ok=True)
    out = open(ontrack_dir / "server.out", "w", encoding="utf-8")
    err = open(ontrack_dir / "server.err", "w", encoding="utf-8")
    # server.py uses cwd as the project root and its sibling dashboard.html as template.
    subprocess.Popen([sys.executable, str(SERVER_PATH)], cwd=str(project),
                     stdout=out, stderr=err, start_new_session=True)
    print("ontrack: dashboard starting in background -> http://localhost:3874")
    print("  logs: .ontrack/server.err (actual URL/port if 3874 was busy). "
          "Stop it by killing the python process.")


if __name__ == "__main__":
    raise SystemExit(main())
