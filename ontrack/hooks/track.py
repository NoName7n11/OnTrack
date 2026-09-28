#!/usr/bin/env python3
"""OnTrack SessionEnd hook — append observations to .ontrack/evidence.jsonl.

Writes OBSERVATIONS ONLY: boring facts seen at a point in time (dependencies,
file extensions). No confidence, no interpretation — that is /ontrack's job.
See PLAN.md. Runs on Claude Code SessionEnd; also usable standalone for tests.
"""
import json
import os
import sys
from datetime import datetime, timezone

# Directories never worth walking for evidence.
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__",
             "dist", "build", ".ontrack", ".idea", ".vscode"}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _deps_from_package_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    names = []
    for key in ("dependencies", "devDependencies"):
        names.extend((data.get(key) or {}).keys())
    return names


def _deps_from_requirements(path):
    names = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return names
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        # strip version specifiers / extras: "flask[async]>=2.0" -> "flask"
        name = line.split(";")[0]
        for sep in ("==", ">=", "<=", "~=", "!=", ">", "<", "["):
            name = name.split(sep)[0]
        name = name.strip()
        if name:
            names.append(name)
    return names


def _deps_from_pyproject(path):
    # tomllib is stdlib on 3.11+; skip gracefully if unavailable.
    try:
        import tomllib
    except ModuleNotFoundError:
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, Exception):  # tomllib.TOMLDecodeError subclasses Exception
        return []
    names = []
    for dep in (data.get("project", {}).get("dependencies") or []):
        # "requests>=2.0" -> "requests"
        n = dep
        for sep in ("==", ">=", "<=", "~=", "!=", ">", "<", "[", " "):
            n = n.split(sep)[0]
        n = n.strip()
        if n:
            names.append(n)
    return names


def _deps_from_cargo_toml(path):
    try:
        import tomllib
    except ModuleNotFoundError:
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, Exception):  # tomllib.TOMLDecodeError subclasses Exception
        return []
    names = []
    for key in ("dependencies", "dev-dependencies", "build-dependencies"):
        table = data.get(key) or {}
        names.extend(table.keys())
    return names


def _deps_from_go_mod(path):
    # ponytail: line scan, not a full go.mod grammar — module paths only, good enough.
    names = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return names
    in_block = False
    for line in lines:
        line = line.split("//", 1)[0].strip()
        if not line:
            continue
        if line.startswith("require") and line.endswith("("):
            in_block = True
            continue
        if in_block and line == ")":
            in_block = False
            continue
        if in_block:
            parts = line.split()
        elif line.startswith("require "):
            parts = line[len("require "):].split()
        else:
            continue
        if parts:
            names.append(parts[0])
    return names


def _deps_from_gemfile(path):
    import re
    names = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return names
    for line in lines:
        line = line.split("#", 1)[0].strip()
        m = re.match(r"""gem\s+['"]([^'"]+)['"]""", line)
        if m:
            names.append(m.group(1))
    return names


def _deps_from_composer_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    names = []
    for key in ("require", "require-dev"):
        for name in (data.get(key) or {}).keys():
            if name == "php" or name.startswith("ext-"):
                continue  # pseudo-packages, not real dependencies
            names.append(name)
    return names


# manifest filename -> parser
MANIFESTS = {
    "package.json": _deps_from_package_json,
    "requirements.txt": _deps_from_requirements,
    "pyproject.toml": _deps_from_pyproject,
    "Cargo.toml": _deps_from_cargo_toml,
    "go.mod": _deps_from_go_mod,
    "Gemfile": _deps_from_gemfile,
    "composer.json": _deps_from_composer_json,
}

# Config files with no extension (p.suffix misses these entirely) worth
# surfacing as tooling evidence. Exact filename match, case-sensitive.
CONFIG_FILES = {
    "Dockerfile", "Makefile", "Procfile", "Vagrantfile", "Rakefile", "Jenkinsfile",
}


def scan_project(root):
    """Return a de-duplicated list of observation dicts for the repo at `root`.

    Dedup is within this single scan only — cross-session duplicates are the
    hook's job to append (a fact re-seen later is meaningful signal). See PLAN.md.
    """
    from pathlib import Path
    root = Path(root)
    now = _now()
    seen = set()
    obs = []

    def add(o):
        key = (o["type"], o["name"], tuple(o.get("args", [])))
        if key not in seen:
            seen.add(key)
            obs.append(o)

    # Dependencies from manifests (search whole tree, not just root).
    ext_sources = {}
    config_sources = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            rel = str(p.relative_to(root)).replace(os.sep, "/")
            if fn in MANIFESTS:
                for name in MANIFESTS[fn](p):
                    add({"type": "dependency", "name": name,
                         "source": rel, "detected_at": now})
            if fn in CONFIG_FILES:
                config_sources.setdefault(fn, rel)
            ext = p.suffix.lower().lstrip(".")
            if ext:
                ext_sources.setdefault(ext, rel)

    # One observation per distinct extension (first file seen as source).
    for ext in sorted(ext_sources):
        src = ext_sources[ext]
        add({"type": "file_extension", "name": ext,
             "source": src, "detected_at": now})

    # One observation per distinct no-extension config file (Dockerfile, etc).
    for fn in sorted(config_sources):
        src = config_sources[fn]
        add({"type": "tool_config", "name": fn,
             "source": src, "detected_at": now})

    return obs


def append_evidence(root, observations):
    """Append observations, then one `session` boundary marker line.

    The marker carries no observation — it lets /ontrack know where this
    session's facts stop, so it can resume from the last unprocessed session
    instead of re-scanning the whole log. See PLAN.md.
    """
    from pathlib import Path
    out_dir = Path(root) / ".ontrack"
    out_dir.mkdir(exist_ok=True)
    marker_ts = _now()
    with open(out_dir / "evidence.jsonl", "a", encoding="utf-8") as f:
        for o in observations:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
        f.write(json.dumps(
            {"type": "session", "id": marker_ts, "detected_at": marker_ts},
            ensure_ascii=False) + "\n")


def _cwd_from_stdin():
    """Resolve the project root from Claude Code's SessionEnd payload on stdin.

    Guard: a hook that guesses its root writes evidence into whatever directory
    the process happened to start in — which can be an unrelated project. So we
    only fall back to the process cwd when NO payload was supplied (a tty, or
    empty stdin — the standalone/test path). A payload that is present but
    malformed, or names a cwd that isn't a directory, raises instead of guessing.
    """
    if sys.stdin.isatty():
        return os.getcwd()
    raw = sys.stdin.read()
    if not raw.strip():
        return os.getcwd()  # no payload at all — standalone run
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"unreadable SessionEnd payload on stdin: {e}") from e
    if not isinstance(payload, dict):
        raise ValueError("SessionEnd payload must be a JSON object")
    cwd = payload.get("cwd")
    if cwd is None:
        return os.getcwd()  # payload parsed but said nothing about cwd
    if not isinstance(cwd, str) or not os.path.isdir(cwd):
        raise ValueError(f"payload cwd is not an existing directory: {cwd!r}")
    return cwd


def main():
    try:
        root = _cwd_from_stdin()
    except ValueError as e:
        # Write nothing rather than risk polluting an unrelated project.
        print(f"ontrack: skipped - {e}", file=sys.stderr)
        return 1
    obs = scan_project(root)
    append_evidence(root, obs)
    # Hooks stay quiet on success; a short note is fine on stderr.
    print(f"ontrack: recorded {len(obs)} observations", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
