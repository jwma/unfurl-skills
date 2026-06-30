#!/usr/bin/env python3
"""unfurl-read.test.py — self-contained test for unfurl-read.py (stdlib only).

Stubs the HTTP layer with a local threaded server (loopback only, no upstream).
Runs the subject as a subprocess and asserts on stdout / stderr / exit code plus
the captured request shape (method, path). This is the read-side peer of the
unfurl-share suite; it keeps the same shape and the same coverage philosophy:

  - success: md / html content printed verbatim behind a format + length header
  - request shape (GET, /p/{token}/source)
  - empty live Doc -> 200, length: 0 (not a failure)
  - 404 (taken down / flagged / missing) -> mapped message
  - other non-2xx -> HTTP status surfaced
  - oversized non-JSON error body truncated vs UNFURL_DEBUG
  - transport failure (dead port)
  - usage: not-a-share-link / bad token (exit 2, no request made)
  - bare token resolves against --base-url
  - /source appended idempotently; trailing slash + query stripped

  python3 scripts/unfurl-read.test.py
Exits nonzero if any assertion fails.
"""

import http.server
import os
import socket
import subprocess
import sys
import threading

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SUBJECT = os.path.join(SCRIPT_DIR, "unfurl-read.py")

# Canned responses keyed by case: (http_status, content_type, body).
# The handler reads CURRENT_CASE (set per-run by the test) to pick one.
RESPONSES = {
    "success_md":    (200, "text/markdown; charset=utf-8", "# Hello unfurl\n"),
    "success_html":  (200, "text/html; charset=utf-8", "<b>Hi</b>"),
    "success_empty": (200, "text/markdown; charset=utf-8", ""),
    "not_found":     (404, "text/html; charset=utf-8", "<html>404</html>"),
    "server_error":  (500, "text/html; charset=utf-8", "<html>500 oops</html>"),
    "oversized":     (500, "text/html; charset=utf-8", "X" * 400),
}

# The case the stub server should serve next. Snapshot by the handler at request
# time so a still-sleeping prior handler can't race a later run. Guarded by _lock.
CURRENT_CASE = "success_md"
LAST_REQUEST = {}
_lock = threading.Lock()


class StubHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global LAST_REQUEST
        with _lock:
            case = CURRENT_CASE
        status, ctype, body = RESPONSES.get(case, RESPONSES["success_md"])
        with _lock:
            LAST_REQUEST = {"method": self.command, "path": self.path}
        body_b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", ctype)
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


def run_case(label, want_rc, stub, args, env_extra=None):
    """Run the subject as a subprocess; capture OUT/ERR/RC and the served request.

    UNFURL_BASE_URL is pointed at the live stub by default; a full-URL argument
    embeds its own host. env_extra overrides the defaults (e.g. set DEBUG).
    """
    global CURRENT_CASE, LAST_REQUEST
    args = list(args)
    with _lock:
        CURRENT_CASE = stub
        LAST_REQUEST = {}
    env = {
        "PATH": os.environ.get("PATH", ""),
        "UNFURL_BASE_URL": BASE_URL,
    }
    for k in ("UNFURL_DEBUG", "UNFURL_MAX_TIME", "UNFURL_CONNECT_TIMEOUT"):
        env.pop(k, None)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, SUBJECT, *args],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    OUT = proc.stdout.decode("utf-8", "replace")
    ERR = proc.stderr.decode("utf-8", "replace").strip()
    RC = proc.returncode
    with _lock:
        REQ = dict(LAST_REQUEST)
    eq(label + " exit", want_rc, RC)
    return OUT, ERR, RC, REQ


def main():
    global BASE_URL
    BASE_URL = start_server()

    print("== unfurl-read.py suite (stubbed urllib, loopback only) ==")
    TOKEN = "abc123"

    # success md: GET /p/{token}/source; header + verbatim body.
    BODY_MD = "# Hello unfurl\n"
    OUT, ERR, RC, REQ = run_case("success_md", 0, "success_md",
                                 ["%s/p/%s" % (BASE_URL, TOKEN)])
    eq("success_md method", "GET", REQ.get("method", ""))
    eq("success_md path", "/p/%s/source" % TOKEN, REQ.get("path", ""))
    eq("success_md output", "format: markdown\nlength: %d chars\n\n%s" % (len(BODY_MD), BODY_MD), OUT)

    # success html: format label follows text/html.
    BODY_HTML = "<b>Hi</b>"
    OUT, ERR, RC, REQ = run_case("success_html", 0, "success_html",
                                 ["%s/p/%s" % (BASE_URL, "def456")])
    eq("success_html path", "/p/def456/source", REQ.get("path", ""))
    eq("success_html output", "format: html\nlength: %d chars\n\n%s" % (len(BODY_HTML), BODY_HTML), OUT)

    # empty live Doc -> 200, length: 0, exit 0 (NOT a failure).
    OUT, ERR, RC, REQ = run_case("success_empty", 0, "success_empty",
                                 ["%s/p/%s" % (BASE_URL, "empty1")])
    eq("success_empty output", "format: markdown\nlength: 0 chars\n\n", OUT)

    # 404 -> mapped message, exit 1.
    OUT, ERR, RC, REQ = run_case("not_found", 1, "not_found",
                                 ["%s/p/%s" % (BASE_URL, "ghost")])
    check("not_found message",
          "taken down" in ERR.lower() or "under review" in ERR.lower() or "not exist" in ERR.lower())

    # other non-2xx -> HTTP status surfaced, exit 1.
    OUT, ERR, RC, REQ = run_case("server_error", 1, "server_error",
                                 ["%s/p/%s" % (BASE_URL, "x")])
    check("server_error mentions status", "HTTP 500" in ERR)

    # oversized non-JSON error body truncated by default; full body under DEBUG.
    OUT, ERR, RC, REQ = run_case("oversized", 1, "oversized",
                                 ["%s/p/%s" % (BASE_URL, "x")])
    FULL = "X" * 400
    check("oversized truncated", FULL not in ERR and "..." in ERR)
    OUT, ERR, RC, REQ = run_case("oversized debug", 1, "oversized",
                                 ["%s/p/%s" % (BASE_URL, "x")],
                                 env_extra={"UNFURL_DEBUG": "1"})
    check("oversized debug full body", FULL in ERR)

    # transport failure (connection refused at a dead port) -> message, exit 1.
    OUT, ERR, RC, REQ = run_case("transport_fail", 1, "success_md",
                                 ["%s/p/%s" % (dead_base_url(), TOKEN)])
    check("transport_fail mentions reach", "could not reach unfurl" in ERR.lower())
    check("transport_fail made no request", REQ == {})

    # --- usage / arg validation (no request made) ---
    OUT, ERR, RC, REQ = run_case("not_a_share_link", 2, "success_md",
                                 ["https://example.com/foo"])
    check("not_a_share_link made no request", REQ == {})
    check("not_a_share_link message", "not an unfurl share link" in ERR.lower())

    OUT, ERR, RC, REQ = run_case("bad_token", 2, "success_md", ["has spaces!"])
    check("bad_token made no request", REQ == {})

    # bare token resolves against --base-url -> GET /p/{token}/source.
    OUT, ERR, RC, REQ = run_case("bare_token", 0, "success_md",
                                 [TOKEN, "--base-url", BASE_URL])
    eq("bare_token path", "/p/%s/source" % TOKEN, REQ.get("path", ""))

    # /source already present -> appended idempotently (no /source/source).
    OUT, ERR, RC, REQ = run_case("idempotent_source", 0, "success_md",
                                 ["%s/p/%s/source" % (BASE_URL, TOKEN)])
    eq("idempotent_source path", "/p/%s/source" % TOKEN, REQ.get("path", ""))

    # trailing slash + query stripped -> /p/{token}/source.
    OUT, ERR, RC, REQ = run_case("trailing_and_query", 0, "success_md",
                                 ["%s/p/%s/?utm=1" % (BASE_URL, TOKEN)])
    eq("trailing_and_query path", "/p/%s/source" % TOKEN, REQ.get("path", ""))

    print()
    print("----")
    print("passed=%d failed=%d" % (PASS, FAIL))
    if FAIL > 0:
        print("\n".join(FAILURES))
        sys.exit(1)
    print("all green")


if __name__ == "__main__":
    main()
