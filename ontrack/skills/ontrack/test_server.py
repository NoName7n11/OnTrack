#!/usr/bin/env python3
"""Self-check for server.py — run: python ontrack/skills/ontrack/test_server.py"""
import json
import http.client
import socket
import tempfile
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

import server

QUESTIONS = {"questions": [
    {"id": "q:react/useeffect", "concept": "concept:react/useeffect",
     "domain": "framework", "mode": "graded", "level": "basic",
     "prompt": "What does useEffect do?",
     "options": ["Runs after render", "Styles", "Routes"], "answer": 0},
    {"id": "q:auth/jwt", "concept": "concept:auth/jwt",
     "domain": "security", "mode": "self_report",
     "prompt": "Comfortable with JWT storage?",
     "options": ["Confident", "Shaky", "New"]},
]}


def _seed(root):
    (root / ".ontrack").mkdir()
    (root / ".ontrack" / "questions.json").write_text(json.dumps(QUESTIONS), encoding="utf-8")


def test_set_answer_and_level():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _seed(root)
        p = root / ".ontrack" / "personal.json"

        # intake level
        server.set_level(root, "beginner")
        assert json.loads(p.read_text())["level"] == "beginner"
        assert {x.name for x in (root / ".ontrack").iterdir()} == {
            "questions.json", "personal.json"}, "only personal.json added"

        # graded: correct choice -> server grades correct
        server.set_answer(root, "q:react/useeffect", choice=0)
        ans = json.loads(p.read_text())["answers"]["q:react/useeffect"]
        assert ans["choice"] == 0 and ans["correct"] is True, ans
        assert "at" in ans

        # graded: wrong choice -> correct False
        server.set_answer(root, "q:react/useeffect", choice=2)
        ans = json.loads(p.read_text())["answers"]["q:react/useeffect"]
        assert ans["correct"] is False, "overwrite + regrade"

        # self_report: rating + note
        server.set_answer(root, "q:auth/jwt", self_rating="Shaky", note="  fuzzy on refresh  ")
        ans = json.loads(p.read_text())["answers"]["q:auth/jwt"]
        assert ans["self"] == "Shaky" and ans["note"] == "fuzzy on refresh", ans
        assert "choice" not in ans and "correct" not in ans, "self_report isn't graded"

        # level survives answer writes (merge, not clobber)
        assert json.loads(p.read_text())["level"] == "beginner"

        # --- rejections, none of which write ---
        before = p.read_text()

        def rejects(**kw):
            try:
                server.set_answer(root, **kw)
            except ValueError:
                return
            assert False, f"should reject {kw}"

        rejects(question_id="q:nope", choice=0)                     # unknown question
        rejects(question_id="q:react/useeffect")                   # graded needs choice
        rejects(question_id="q:react/useeffect", choice=9)         # out of range
        rejects(question_id="q:react/useeffect", choice=True)      # bool != int choice
        rejects(question_id="q:auth/jwt", self_rating="Wizard")    # not an option
        rejects(question_id="q:auth/jwt")                          # self_report needs rating
        rejects(question_id="")                                    # empty id

        for bad in ("expert", "", None, "BEGINNER"):
            try:
                server.set_level(root, bad)
                assert False, f"should reject level {bad!r}"
            except ValueError:
                pass

        assert p.read_text() == before, "rejected calls must not write"

        # questions.json is never touched by the server
        assert json.loads((root / ".ontrack" / "questions.json").read_text()) == QUESTIONS

    print("ok: set_answer grades graded, stores self_report, set_level validates; writes only personal.json")


def _serve(root, template):
    handler = partial(server.Handler, root=root, template=template)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread, httpd.server_address[1]


def test_http_routes():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _seed(root)
        (root / ".ontrack" / "inventory.json").write_text(
            '{"items":[{"id":"concept:react/useeffect"}]}', encoding="utf-8")
        template = root / "dashboard.html"
        template.write_text("<!doctype html><title>OnTrack</title>", encoding="utf-8")
        httpd, thread, port = _serve(root, template)

        def req(method, path, body=None):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request(method, path, body=body,
                         headers={"Content-Type": "application/json"} if body else {})
            res = conn.getresponse()
            data = res.read()
            conn.close()
            return res.status, data

        def raw_bad_length():
            with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
                sock.sendall(
                    b"POST /answer HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Content-Length: not-a-number\r\nConnection: close\r\n\r\n")
                return sock.recv(1024)

        try:
            # served questions have the answer key STRIPPED
            status, body = req("GET", "/questions.json")
            assert status == 200, status
            served = json.loads(body)["questions"]
            assert all("answer" not in q for q in served), "answer key must not reach the browser"
            assert any(q["id"] == "q:react/useeffect" for q in served)

            # POST /level
            assert req("POST", "/level", b'{"level":"senior"}')[0] == 200
            assert req("POST", "/level", b'{"level":"wizard"}')[0] == 400

            # POST /answer
            assert req("POST", "/answer", b'{"question_id":"q:react/useeffect","choice":0}')[0] == 200
            assert req("POST", "/answer", b'{"question_id":"nope","choice":0}')[0] == 400
            for bad in (b"[]", b"123", b"null"):
                assert req("POST", "/answer", bad)[0] == 400, bad

            assert b" 400 " in raw_bad_length().splitlines()[0]

            # unknown POST route -> 404
            assert req("POST", "/status", b'{}')[0] == 404

            data = json.loads((root / ".ontrack" / "personal.json").read_text())
            assert data["level"] == "senior"
            assert data["answers"]["q:react/useeffect"]["correct"] is True
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    print("ok: HTTP /questions strips answer, /level + /answer validate, bad routes/bodies 400/404")


def test_http_get_whitelist():
    """GET serves only whitelisted paths; traversal/unknown -> 404, no leak."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _seed(root)
        (root / ".ontrack" / "inventory.json").write_text(
            '{"items":[{"id":"concept:react/useeffect"}]}', encoding="utf-8")
        (root / ".ontrack" / "personal.json").write_text('{"answers":{}}', encoding="utf-8")
        (root / "secret.txt").write_text("TOP SECRET", encoding="utf-8")
        template = root / "dashboard.html"
        template.write_text("<!doctype html><title>OnTrack</title>", encoding="utf-8")
        httpd, thread, port = _serve(root, template)

        def get(path):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
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
            for path in ("/inventory.json", "/personal.json", "/questions.json"):
                status, body = get(path)
                assert status == 200 and json.loads(body) is not None, (path, status)
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
    test_set_answer_and_level()
    test_http_routes()
    test_http_get_whitelist()
