#!/usr/bin/env python3
"""Self-check for server.py — run: python .claude/skills/ontrack/test_server.py"""
import json
import http.client
import tempfile
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

import server


def test_set_status():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / ".ontrack").mkdir()
        (root / ".ontrack" / "inventory.json").write_text(json.dumps({
            "items": [
                {"id": "library:react"},
                {"id": "language:python"},
            ]
        }), encoding="utf-8")

        # valid status writes personal.json (and only that)
        server.set_status(root, "library:react", "known")
        p = root / ".ontrack" / "personal.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["status"]["library:react"] == "known", data
        assert {x.name for x in (root / ".ontrack").iterdir()} == {
            "inventory.json", "personal.json"
        }, "only personal.json added by server"

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

        # unknown inventory id rejected
        try:
            server.set_status(root, "library:missing", "known")
            assert False, "should reject unknown item id"
        except ValueError:
            pass

        # inventory.json is never created/touched by the server
        inventory_before = (root / ".ontrack" / "inventory.json").read_text(encoding="utf-8")
        server.set_status(root, "language:python", "ignored")
        assert (root / ".ontrack" / "inventory.json").read_text(
            encoding="utf-8") == inventory_before

    print("ok: set_status validates, merges, writes only personal.json atomically")


def test_http_status_route():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / ".ontrack").mkdir()
        (root / ".ontrack" / "inventory.json").write_text(json.dumps({
            "items": [{"id": "library:react"}]
        }), encoding="utf-8")
        template = root / "dashboard.html"
        template.write_text("<!doctype html><title>OnTrack</title>", encoding="utf-8")

        handler = partial(server.Handler, root=root, template=template)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        port = httpd.server_address[1]

        def post(body, content_type="application/json", content_length=None):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            headers = {"Content-Type": content_type}
            if content_length is not None:
                headers["Content-Length"] = content_length
                conn.putrequest("POST", "/status")
                for k, v in headers.items():
                    conn.putheader(k, v)
                conn.endheaders()
                conn.send(body)
            else:
                conn.request("POST", "/status", body=body, headers=headers)
            res = conn.getresponse()
            data = res.read()
            conn.close()
            return res.status, data

        try:
            status, _ = post(b'{"id":"library:react","status":"known"}')
            assert status == 200, status

            status, _ = post(b'{"id":"library:missing","status":"known"}')
            assert status == 400, status

            for body in (b"[]", b"123", b"null"):
                status, _ = post(body)
                assert status == 400, (body, status)

            status, _ = post(b"{}", content_length="not-a-number")
            assert status == 400, status

            data = json.loads((root / ".ontrack" / "personal.json").read_text(
                encoding="utf-8"))
            assert data["status"] == {"library:react": "known"}, data
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    print("ok: HTTP /status handles valid, unknown, non-object, malformed length")


def test_http_get_whitelist():
    """GET serves only the 3 whitelisted paths; everything else is 404.

    Guards the "no arbitrary file access" property — a refactor that widens the
    whitelist or resolves the request path against the filesystem must fail here.
    """
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / ".ontrack").mkdir()
        (root / ".ontrack" / "inventory.json").write_text(
            '{"items":[{"id":"library:react"}]}', encoding="utf-8")
        (root / ".ontrack" / "personal.json").write_text(
            '{"status":{"library:react":"known"}}', encoding="utf-8")
        # a secret sitting next to the served files — must never be reachable
        (root / "secret.txt").write_text("TOP SECRET", encoding="utf-8")
        template = root / "dashboard.html"
        template.write_text("<!doctype html><title>OnTrack</title>", encoding="utf-8")

        handler = partial(server.Handler, root=root, template=template)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        port = httpd.server_address[1]

        def get(path):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            # putrequest(skip_host/accept) keeps the raw path unnormalized so a
            # traversal attempt actually reaches the handler as-is.
            conn.putrequest("GET", path, skip_host=False, skip_accept_encoding=True)
            conn.endheaders()
            res = conn.getresponse()
            body = res.read()
            conn.close()
            return res.status, body

        try:
            for path in ("/", "/index.html"):
                status, body = get(path)
                assert status == 200 and b"OnTrack" in body, (path, status)
            for path in ("/inventory.json", "/personal.json"):
                status, body = get(path)
                assert status == 200 and json.loads(body), (path, status)
            # anything off the whitelist — including traversal — is 404, and the
            # secret's contents never appear in any response body.
            for path in ("/secret.txt", "/../secret.txt", "/../../etc/passwd",
                         "/.ontrack/evidence.jsonl", "/nope"):
                status, body = get(path)
                assert status == 404, (path, status)
                assert b"TOP SECRET" not in body, f"leaked via {path}"
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    print("ok: HTTP GET serves only the whitelist; traversal and unknown paths 404")


if __name__ == "__main__":
    test_set_status()
    test_http_status_route()
    test_http_get_whitelist()
