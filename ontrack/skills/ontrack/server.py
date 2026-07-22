#!/usr/bin/env python3
"""OnTrack dashboard server (build step 6).

Serves the static dashboard template plus the project's inventory.json,
questions.json, and personal.json, and accepts the answers/level the user
submits from the dashboard.

Security / scope (see PLAN.md):
- Binds 127.0.0.1 only. A file-writing endpoint must not face the network.
- Serves a fixed whitelist of paths — no arbitrary file access.
- The served questions.json has the graded `answer` key STRIPPED, so the MCQ
  key never reaches the browser. The server grades; the client only learns
  whether it got the question right.
- The ONLY file it writes is .ontrack/personal.json (level + answers), written
  atomically. inventory.json / questions.json / evidence.jsonl are never touched.
"""
import json
import os
import sys
from datetime import datetime, timezone
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

LEVELS = {"beginner", "intermediate", "senior"}
PORT_START = 3874
PORT_TRIES = 20
PERSONAL_LOCK = Lock()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _atomic_write(path, text):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)  # atomic on same filesystem


def questions_index(root):
    """Return {question_id: question} from questions.json (raw, incl. answer key)."""
    data = load_json(Path(root) / ".ontrack" / "questions.json", {"questions": []})
    out = {}
    for q in data.get("questions", []):
        if isinstance(q, dict) and q.get("id"):
            out[q["id"]] = q
    return out


def public_questions(root):
    """questions.json for the browser — with the graded `answer` key removed."""
    data = load_json(Path(root) / ".ontrack" / "questions.json", {"questions": []})
    safe = []
    for q in data.get("questions", []):
        if isinstance(q, dict):
            safe.append({k: v for k, v in q.items() if k != "answer"})
    return {"questions": safe}


def _write_personal(root, mutate):
    """Load personal.json, apply mutate(dict), atomic-write. Returns the dict."""
    p = Path(root) / ".ontrack" / "personal.json"
    p.parent.mkdir(exist_ok=True)
    with PERSONAL_LOCK:
        data = load_json(p, {})
        if not isinstance(data, dict):
            data = {}
        data.setdefault("answers", {})
        mutate(data)
        _atomic_write(p, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return data


def set_level(root, level):
    """Record the intake level. Raises ValueError on a bad value."""
    if level not in LEVELS:
        raise ValueError(f"invalid level: {level!r}")
    return _write_personal(root, lambda d: d.__setitem__("level", level))


def set_answer(root, question_id, choice=None, self_rating=None, note=None):
    """Record one answer, grading graded questions server-side.

    graded      -> requires `choice` (int in range); stores {choice, correct, at}.
    self_report -> requires `self_rating` in the question's options; stores
                   {self, note?, at}. Raises ValueError on anything invalid.
    Only .ontrack/personal.json is written.
    """
    if not question_id or not isinstance(question_id, str):
        raise ValueError("question id required")
    q = questions_index(root).get(question_id)
    if q is None:
        raise ValueError(f"unknown question id: {question_id!r}")

    options = q.get("options") or []
    mode = q.get("mode")
    entry = {"at": _now()}

    if mode == "graded":
        if not isinstance(choice, int) or isinstance(choice, bool):
            raise ValueError("choice (int) required for a graded question")
        if not (0 <= choice < len(options)):
            raise ValueError("choice out of range")
        entry["choice"] = choice
        entry["correct"] = (choice == q.get("answer"))  # server grades, key stays here
    elif mode == "self_report":
        if self_rating not in options:
            raise ValueError("self rating must be one of the question's options")
        entry["self"] = self_rating
        if note is not None:
            if not isinstance(note, str):
                raise ValueError("note must be text")
            note = note.strip()
            if note:
                entry["note"] = note[:500]  # bound stored free text
    else:
        raise ValueError(f"question has unknown mode: {mode!r}")

    return _write_personal(root, lambda d: d["answers"].__setitem__(question_id, entry))


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *a, root=None, template=None, **kw):
        self.root = Path(root)
        self.template = Path(template)
        super().__init__(*a, **kw)

    def log_message(self, *a):  # keep the terminal quiet
        pass

    def _send(self, code, body, ctype):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj), "application/json")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, self.template.read_text(encoding="utf-8"),
                       "text/html; charset=utf-8")
        elif self.path == "/inventory.json":
            self._json(200, load_json(self.root / ".ontrack" / "inventory.json",
                                      {"items": []}))
        elif self.path == "/questions.json":
            self._json(200, public_questions(self.root))  # answer key stripped
        elif self.path == "/personal.json":
            self._json(200, load_json(self.root / ".ontrack" / "personal.json",
                                      {"answers": {}}))
        else:
            self._send(404, "not found", "text/plain")  # whitelist only

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("body must be a JSON object")
        return payload

    def do_POST(self):
        try:
            payload = self._read_body()
            if self.path == "/answer":
                data = set_answer(self.root, payload.get("question_id"),
                                  choice=payload.get("choice"),
                                  self_rating=payload.get("self"),
                                  note=payload.get("note"))
            elif self.path == "/level":
                data = set_level(self.root, payload.get("level"))
            else:
                self._send(404, "not found", "text/plain")
                return
        except (json.JSONDecodeError, ValueError) as e:
            self._json(400, {"ok": False, "error": str(e)})
            return
        self._json(200, {"ok": True, "level": data.get("level"),
                         "answers": data.get("answers", {})})


def run(root, template, port_start=PORT_START):
    root, template = Path(root), Path(template)
    handler = partial(Handler, root=root, template=template)
    last = None
    for port in range(port_start, port_start + PORT_TRIES):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
        except OSError as e:
            last = e
            continue
        print(f"OnTrack dashboard: open http://localhost:{port}", file=sys.stderr)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nontrack: dashboard stopped", file=sys.stderr)
        return
    raise SystemExit(f"no free port in {port_start}..{port_start + PORT_TRIES}: {last}")


def main():
    root = Path.cwd()
    template = Path(__file__).resolve().parent / "dashboard.html"
    run(root, template)


if __name__ == "__main__":
    main()
