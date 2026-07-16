#!/usr/bin/env python3
"""OnTrack dashboard server (build step 4).

Serves the static dashboard template plus the project's inventory.json and
personal.json, and accepts one POST that records the user's learning status.

Security / scope (see PLAN.md):
- Binds 127.0.0.1 only. A file-writing endpoint must not face the network.
- Serves a fixed whitelist of paths — no arbitrary file access.
- The ONLY file it writes is .ontrack/personal.json (status by item id),
  written atomically. inventory.json / evidence.jsonl are never touched.
"""
import json
import os
import sys
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

STATUSES = {"known", "somewhat", "to_learn", "ignored"}
PORT_START = 3874
PORT_TRIES = 20
PERSONAL_LOCK = Lock()


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


def inventory_ids(root):
    inv = load_json(Path(root) / ".ontrack" / "inventory.json", {"items": []})
    return {item.get("id") for item in inv.get("items", []) if item.get("id")}


def set_status(root, item_id, status):
    """Record status for an inventory item id. Raises ValueError on bad status.

    Writes only .ontrack/personal.json. Returns the updated personal dict.
    """
    if status not in STATUSES:
        raise ValueError(f"invalid status: {status!r}")
    if not item_id or not isinstance(item_id, str):
        raise ValueError("item id required")
    if item_id not in inventory_ids(root):
        raise ValueError(f"unknown item id: {item_id!r}")
    p = Path(root) / ".ontrack" / "personal.json"
    p.parent.mkdir(exist_ok=True)
    with PERSONAL_LOCK:
        data = load_json(p, {"status": {}})
        data.setdefault("status", {})[item_id] = status
        _atomic_write(p, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return data


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

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, self.template.read_text(encoding="utf-8"),
                       "text/html; charset=utf-8")
        elif self.path == "/inventory.json":
            body = json.dumps(load_json(self.root / ".ontrack" / "inventory.json",
                                        {"items": []}))
            self._send(200, body, "application/json")
        elif self.path == "/personal.json":
            body = json.dumps(load_json(self.root / ".ontrack" / "personal.json",
                                        {"status": {}}))
            self._send(200, body, "application/json")
        else:
            self._send(404, "not found", "text/plain")  # whitelist only

    def do_POST(self):
        if self.path != "/status":
            self._send(404, "not found", "text/plain")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("body must be a JSON object")
            data = set_status(self.root, payload.get("id"), payload.get("status"))
        except (json.JSONDecodeError, ValueError) as e:
            self._send(400, json.dumps({"ok": False, "error": str(e)}),
                       "application/json")
            return
        self._send(200, json.dumps({"ok": True, "status": data["status"]}),
                   "application/json")


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
