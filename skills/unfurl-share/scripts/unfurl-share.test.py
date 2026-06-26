#!/usr/bin/env python3
"""unfurl-share.test.py — self-contained test for unfurl-share.py (stdlib only).

Stubs the HTTP layer with a local threaded server (loopback only, no Supabase,
no real upstream). Runs the subject script as a subprocess and asserts on
stdout / stderr / exit code plus the captured request shape. This is the Python
port of the bash suite it replaced; it keeps the same coverage:

  - request shape (POST, /api/v1/docs, Bearer header, payload fields, no-title)
  - success extraction (md default, html+title, JSON quote round-trip)
  - 2xx-but-no-share_link
  - every structured error-code -> mapped message
  - unknown code / no code / oversized non-JSON body truncation vs UNFURL_DEBUG
  - transport failure (dead port)
  - config / arg validation (exit 2, no request made)
  - timeout knobs and the max(MAX_TIME, CONNECT_TIMEOUT) semantics

  python3 scripts/unfurl-share.test.py
Exits nonzero if any assertion fails.
"""

import http.server
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SUBJECT = os.path.join(SCRIPT_DIR, "unfurl-share.py")

# Canned responses keyed by case: (http_status, body, sleep_seconds).
# The handler reads CURRENT_CASE (set per-run by the test) to pick one.
RESPONSES = {
    "success":           (201, '{"share_link":"https://unfurl.test/p/abc123","token":"abc123","moderation_status":"clean"}', 0),
    "success_quoted":    (201, '{"share_link":"https://unfurl.test/p/a-b_c","token":"a-b_c","moderation_status":"flagged"}', 0),
    "no_link":           (201, '{"token":"abc123"}', 0),
    "unauthorized":      (401, '{"error":"unauthorized"}', 0),
    "invalid_key":       (401, '{"error":"invalid_key"}', 0),
    "invalid_format":    (400, '{"error":"invalid_format"}', 0),
    "empty_content":     (400, '{"error":"empty_content"}', 0),
    "bad_request":       (400, '{"error":"bad_request"}', 0),
    "content_too_large": (413, '{"error":"content_too_large"}', 0),
    "rate_limited":      (429, '{"error":"rate_limited"}', 0),
    "render_failed":     (422, '{"error":"render_failed"}', 0),
    "lookup_failed":     (500, '{"error":"lookup_failed"}', 0),
    "create_failed":     (500, '{"error":"create_failed"}', 0),
    "unknown_code":      (400, '{"error":"who_knows"}', 0),
    "no_code":           (502, "<html>502 Bad Gateway</html>", 0),
    "long_no_code":      (502, "<html><body>" + "X" * 400 + "</body></html>", 0),
    "slow_short":        (201, '{"share_link":"https://unfurl.test/p/slow","token":"slow"}', 1.5),
    "slow_long":         (201, '{"share_link":"https://unfurl.test/p/slow","token":"slow"}', 2.0),
}

# The case the stub server should serve next. Snapshot by the handler at request
# time so a still-sleeping prior handler can't race a later run. Guarded by _lock.
CURRENT_CASE = "success"
LAST_REQUEST = {}
_lock = threading.Lock()


class StubHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        global LAST_REQUEST
        with _lock:
            case = CURRENT_CASE
        status, body, sleep_s = RESPONSES.get(case, RESPONSES["success"])
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length).decode("utf-8", "replace") if length else ""
        with _lock:
            LAST_REQUEST = {
                "method": self.command,
                "path": self.path,
                "auth": self.headers.get("Authorization", ""),
                "body": raw,
            }
        if sleep_s:
            time.sleep(sleep_s)
        body_b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_b)))
        self.end_headers()
        self.wfile.write(body_b)

    def log_message(self, *args):
        pass  # silence default request logging


def start_server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return "http://127.0.0.1:%d" % srv.server_address[1]


def dead_base_url():
    """A loopback URL on a port nothing is listening on (bind + close)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return "http://127.0.0.1:%d" % port


PASS = 0
FAIL = 0
FAILURES = []


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append("FAIL " + label)


def eq(label, want, got):
    check("%s [want=%r got=%r]" % (label, want, got), want == got)


def parse_body(raw):
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {}


def run_case(label, want_rc, stub, input_str, args=None, base_url=None, env_extra=None):
    """Run the subject as a subprocess; capture OUT/ERR/RC and the served request.

    base_url defaults to the live stub server. Pass a dead URL for transport
    failures. env_extra overrides the defaults (e.g. unset the key, set DEBUG).
    """
    global CURRENT_CASE, LAST_REQUEST
    args = list(args or ())
    with _lock:
        CURRENT_CASE = stub
        LAST_REQUEST = {}
    env = {
        # Keep PATH etc. so sys.executable + subject resolve; layer our knobs on top.
        "PATH": os.environ.get("PATH", ""),
        "UNFURL_API_KEY": "test-key-abcdef",
        "UNFURL_BASE_URL": base_url if base_url is not None else BASE_URL,
    }
    for k in ("UNFURL_DEBUG", "UNFURL_MAX_TIME", "UNFURL_CONNECT_TIMEOUT", "STUB_CASE"):
        env.pop(k, None)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, SUBJECT, *args],
        input=input_str.encode("utf-8"),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    OUT = proc.stdout.decode("utf-8", "replace").strip()
    ERR = proc.stderr.decode("utf-8", "replace").strip()
    RC = proc.returncode
    with _lock:
        REQ = dict(LAST_REQUEST)
    eq(label + " exit", want_rc, RC)
    return OUT, ERR, RC, REQ


def main():
    global BASE_URL
    BASE_URL = start_server()

    print("== unfurl-share.py suite (stubbed urllib, loopback only) ==")

    # success: prints only the share link, exit 0, and a correct request shape.
    OUT, ERR, RC, REQ = run_case("success", 0, "success", "# Hello")
    eq("success stdout is the link", "https://unfurl.test/p/abc123", OUT)
    eq("success sent POST", "POST", REQ.get("method", ""))
    eq("success hit endpoint", "/api/v1/docs", REQ.get("path", ""))
    eq("success sent Bearer", "Bearer test-key-abcdef", REQ.get("auth", ""))
    body = parse_body(REQ.get("body", ""))
    eq("success sent md format", "md", body.get("format"))
    eq("success sent content", "# Hello", body.get("content"))
    check("success omitted title when none", "title" not in body)

    # html + title: format and title threaded through.
    OUT, ERR, RC, REQ = run_case("html+title", 0, "success_quoted", "<b>hi</b>",
                                 ["--format", "html", "--title", "Greeting"])
    eq("html+title stdout", "https://unfurl.test/p/a-b_c", OUT)
    body = parse_body(REQ.get("body", ""))
    eq("html+title format", "html", body.get("format"))
    eq("html+title title", "Greeting", body.get("title"))

    # content with a double quote round-trips through the JSON body intact.
    OUT, ERR, RC, REQ = run_case("quote-escaping", 0, "success", 'say "hi"')
    body = parse_body(REQ.get("body", ""))
    eq("quote-escaping content round-trip", 'say "hi"', body.get("content"))

    # --file reads from a file instead of stdin; content round-trips.
    fd, md_path = tempfile.mkstemp(suffix=".md")
    os.write(fd, "# from file".encode("utf-8"))
    os.close(fd)
    try:
        OUT, ERR, RC, REQ = run_case("--file", 0, "success", "", ["--file", md_path])
        eq("--file stdout", "https://unfurl.test/p/abc123", OUT)
        body = parse_body(REQ.get("body", ""))
        eq("--file sent content", "# from file", body.get("content"))
    finally:
        os.unlink(md_path)

    # a non-UTF-8 file degrades via errors="replace" — no traceback, exit 0.
    fd, bad_path = tempfile.mkstemp(suffix=".md")
    os.write(fd, b"\xff\xfe# not valid utf-8 \x80")
    os.close(fd)
    try:
        OUT, ERR, RC, REQ = run_case("--file non-utf8", 0, "success", "", ["--file", bad_path])
        eq("--file non-utf8 exit", 0, RC)
        check("--file non-utf8 no traceback", "Traceback" not in ERR)
    finally:
        os.unlink(bad_path)

    # 2xx but no share_link -> failure, message on stderr.
    OUT, ERR, RC, REQ = run_case("no_link", 1, "no_link", "x")
    check("no_link mentions share_link", "no share_link" in ERR.lower())

    # every structured error code -> exit 1 + a non-empty message.
    for code in ["unauthorized", "invalid_key", "invalid_format", "empty_content",
                 "bad_request", "content_too_large", "rate_limited", "render_failed",
                 "lookup_failed", "create_failed"]:
        OUT, ERR, RC, REQ = run_case("err:" + code, 1, code, "irrelevant")
        check("err:%s has message" % code, bool(ERR))
    # spot-check a couple of mappings read naturally.
    OUT, ERR, RC, REQ = run_case("err:rate_limited msg", 1, "rate_limited", "x")
    check("rate_limited wording", "rate limit" in ERR.lower())
    OUT, ERR, RC, REQ = run_case("err:content_too_large msg", 1, "content_too_large", "x")
    check("content_too_large wording", "size cap" in ERR.lower())

    # unknown structured code + no code at all -> still a clean failure.
    OUT, ERR, RC, REQ = run_case("err:unknown_code", 1, "unknown_code", "x")
    check("unknown_code mentions code", "code: who_knows" in ERR)
    OUT, ERR, RC, REQ = run_case("err:no_code", 1, "no_code", "x")
    check("no_code mentions status", "HTTP 502" in ERR)

    # oversized non-JSON body is truncated by default (not dumped in full).
    OUT, ERR, RC, REQ = run_case("err:long_no_code", 1, "long_no_code", "x")
    FULL = "X" * 400
    check("long_no_code not full body", FULL not in ERR)
    check("long_no_code truncated", "..." in ERR)
    # UNFURL_DEBUG=1 prints the full body instead of the truncated hint.
    OUT, ERR, RC, REQ = run_case("debug full body", 1, "long_no_code", "x",
                                 env_extra={"UNFURL_DEBUG": "1"})
    check("debug shows full body", FULL in ERR)

    # transport failure (connection refused at a dead port) -> message, exit 1.
    OUT, ERR, RC, REQ = run_case("transport_fail", 1, "success", "x",
                                 base_url=dead_base_url())
    check("transport_fail mentions reach", "could not reach unfurl" in ERR.lower())
    check("transport_fail made no captured request", REQ == {})

    # --- config / arg validation (no request made) ---
    OUT, ERR, RC, REQ = run_case("missing API_KEY", 2, "success", "x",
                                 env_extra={"UNFURL_API_KEY": ""})
    eq("missing API_KEY exit", 2, RC)
    check("missing API_KEY made no request", REQ == {})

    OUT, ERR, RC, REQ = run_case("missing BASE_URL", 2, "success", "x",
                                 env_extra={"UNFURL_BASE_URL": ""})
    eq("missing BASE_URL exit", 2, RC)

    OUT, ERR, RC, REQ = run_case("bad format", 2, "success", "x", ["--format", "pdf"])
    eq("bad format exit", 2, RC)
    check("bad format message", "invalid --format" in ERR.lower())

    OUT, ERR, RC, REQ = run_case("empty stdin", 2, "success", "")
    eq("empty stdin exit", 2, RC)

    # a flag with no value -> argparse error, clean exit 2, no request.
    OUT, ERR, RC, REQ = run_case("missing flag value", 2, "success", "x", ["--format"])
    eq("missing flag value exit", 2, RC)
    check("missing flag value message", "expected one argument" in ERR.lower())
    check("missing flag value made no request", REQ == {})

    # --- timeout knobs ---
    # The script uses a single socket timeout = max(MAX_TIME, CONNECT_TIMEOUT),
    # so both must be small to force a timeout. slow_long sleeps 2s.
    OUT, ERR, RC, REQ = run_case("timeout fires", 1, "slow_long", "x",
                                 env_extra={"UNFURL_MAX_TIME": "1", "UNFURL_CONNECT_TIMEOUT": "1"})
    check("timeout mentions reach", "could not reach unfurl" in ERR.lower())
    # The larger knob wins: a tiny MAX_TIME with a larger CONNECT_TIMEOUT does
    # NOT cap the request (slow_short's 1.5s fits under the 20s effective limit).
    OUT, ERR, RC, REQ = run_case("timeout max-of-knobs", 0, "slow_short", "x",
                                 env_extra={"UNFURL_MAX_TIME": "1", "UNFURL_CONNECT_TIMEOUT": "20"})
    eq("timeout max-of-knobs link", "https://unfurl.test/p/slow", OUT)

    print()
    print("----")
    print("passed=%d failed=%d" % (PASS, FAIL))
    if FAIL > 0:
        print("\n".join(FAILURES))
        sys.exit(1)
    print("all green")


if __name__ == "__main__":
    main()
