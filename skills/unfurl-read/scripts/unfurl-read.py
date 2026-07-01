#!/usr/bin/env python3
"""unfurl-read.py — read the verbatim Source of an unfurl Doc from its Share link.

Python 3 standard-library only (no third-party deps). Given a Share link (or a
bare token), fetches the Doc's /source representation — the raw Markdown or HTML
the Creator wrote, with no rendered chrome — and prints it. This is the
machine-facing peer of the human Page: minimum tokens, no metadata in the body.

Output contract:
  success → a one-line format, a length line, a blank line, then the verbatim
            content on stdout (exit 0)
  failure → a concise, code-mapped message on stderr (exit nonzero)

The Source endpoint is token-based (no API key, no account), exactly like the
Page. It serves only live Docs; flagged / taken_down / missing → 404. Reading it
does not count as a View.

Optional env (parity with unfurl-share.py):
  UNFURL_BASE_URL         default instance for a bare-token argument
                           (https://unfurl.anmuji.com). Ignored for full URLs.
  UNFURL_MAX_TIME         request socket timeout, seconds (default 30). Effective
                           value is max(UNFURL_MAX_TIME, UNFURL_CONNECT_TIMEOUT).
  UNFURL_CONNECT_TIMEOUT  folded into the timeout above.
  UNFURL_DEBUG=1          print full response bodies on unexpected errors.

Usage:
  unfurl-read.py https://unfurl.anmuji.com/p/abc123        # from a Share link
  unfurl-read.py https://unfurl.anmuji.com/p/abc123/source # idempotent
  unfurl-read.py abc123                                     # bare token
  unfurl-read.py abc123 --base-url http://self-hosted       # self-hosted
"""

import argparse
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import NoReturn

DEFAULT_BASE_URL = "https://unfurl.anmuji.com"
USER_AGENT = "unfurl-read/1.0 (agent-skill)"

# Exit codes: 2 == bad usage/config (caller's fault), 1 == runtime/API failure.
EXIT_USAGE = 2
EXIT_FAIL = 1

# A Share path is /p/{token} optionally already followed by /source. Tokens are
# alphanumeric with dashes/underscores (e.g. abc123, a-b_c).
TOKEN_RE = r"[A-Za-z0-9_-]+"
SHARE_PATH_RE = re.compile(r"^/p/(%s)(?:/source)?/?$" % TOKEN_RE)


def die(msg, code=EXIT_FAIL) -> NoReturn:
    """Print a concise message to stderr and exit."""
    print(msg, file=sys.stderr)
    sys.exit(code)


def positive_int(value, default):
    try:
        n = int(value)
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


def raw_hint(raw):
    """Render a raw error body for a diagnostic stderr line.

    By default a single truncated, whitespace-collapsed hint so it doesn't drown
    out the actionable message. UNFURL_DEBUG=1 prints the body unchanged.
    """
    if raw is None:
        return ""
    if os.environ.get("UNFURL_DEBUG", "0") == "1":
        return raw
    one_line = re.sub(r"[\s]+", " ", raw).strip()
    return one_line[:200] + "..." if len(one_line) > 200 else one_line


def to_source_url(arg, default_base):
    """Turn a Share link, a /source URL, or a bare token into the /source URL.

    A full URL is self-contained (its host wins); a bare token resolves against
    the configured instance. Query and fragment are dropped — the Source route is
    keyed only on the token.
    """
    arg = arg.strip()
    if arg.startswith("http://") or arg.startswith("https://"):
        split = urllib.parse.urlsplit(arg)
        m = SHARE_PATH_RE.match(split.path or "")
        if not m:
            die("Not an unfurl share link. Expected a URL like "
                "https://unfurl.anmuji.com/p/{token}; got: %s" % arg, EXIT_USAGE)
        token = m.group(1)
        base = "%s://%s" % (split.scheme, split.netloc)
        return "%s/p/%s/source" % (base, token)
    # Bare token: resolve against the configured instance.
    if not re.fullmatch(TOKEN_RE, arg):
        die("Invalid share token %r. Pass a full Share link or an alphanumeric "
            "token (letters, digits, -, _)." % arg, EXIT_USAGE)
    base = (default_base or "").rstrip("/")
    if not base:
        die("No instance to resolve the bare token against. Pass a full Share "
            "link, or set --base-url (UNFURL_BASE_URL).", EXIT_USAGE)
    return "%s/p/%s/source" % (base, arg)


def format_from_ctype(ctype):
    """Map the response Content-Type to a plain format label for the header."""
    cl = (ctype or "").lower()
    if "markdown" in cl:
        return "markdown"
    if "html" in cl:
        return "html"
    return "text"


def report_non_2xx(http_code, err_body) -> NoReturn:
    if http_code == 404:
        die("No Source for this link — the Doc may be taken down, flagged / under "
            "review, or may not exist. Open the Share link in a browser to check.")
    msg = "unfurl returned HTTP %s for the Source." % http_code
    hint = raw_hint(err_body)
    if hint:
        msg += " " + hint
    die(msg)


def parse_args():
    p = argparse.ArgumentParser(
        prog="unfurl-read.py",
        add_help=True,
        description="Reads an unfurl Doc's verbatim content from its Share link's /source endpoint.",
    )
    p.add_argument("url", help="Share link (https://.../p/{token}), a /source URL, or a bare token")
    p.add_argument("--base-url", dest="base_url",
                   default=os.environ.get("UNFURL_BASE_URL", DEFAULT_BASE_URL),
                   help="instance to resolve a bare token against (default %(default)s)")
    # argparse exits 2 on unknown args / missing values, matching unfurl-share.py.
    return p.parse_args()


def main():
    args = parse_args()

    source_url = to_source_url(args.url, args.base_url)

    # urllib uses a single socket timeout; honor the larger of the two knobs so
    # neither artificially caps the request. Defaults match unfurl-share.py.
    timeout = max(
        positive_int(os.environ.get("UNFURL_MAX_TIME"), 30),
        positive_int(os.environ.get("UNFURL_CONNECT_TIMEOUT"), 10),
    )
    req = urllib.request.Request(source_url, method="GET", headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/markdown, text/html;q=0.9, */*;q=0.1",
    })

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            http_code = resp.getcode()
            ctype = resp.headers.get("Content-Type", "")
            body = resp.read()
    except urllib.error.HTTPError as e:
        # Non-2xx: 404 hides flagged/taken_down/missing identically; others are
        # transient or gateway faults. The body (often an HTML error page) is a hint.
        http_code = e.code
        err_body = e.read().decode("utf-8", "replace") if e.fp else ""
        report_non_2xx(http_code, err_body)
    except urllib.error.URLError as e:
        die("Could not reach unfurl at %s: %s" % (source_url, getattr(e, "reason", e)))
    except (TimeoutError, OSError) as e:
        die("Could not reach unfurl at %s: %s" % (source_url, e))

    if not (200 <= http_code < 300):
        # urlopen raises on non-2xx, but be defensive.
        report_non_2xx(http_code, "")

    # Verbatim: write the Source's exact bytes to the binary stdout buffer so the
    # output is independent of the process stdout encoding and is never altered by
    # a decode/encode round-trip (no errors="replace", no replacement chars). The
    # header is ASCII, so UTF-8-encoding it is lossless; length is the true byte
    # count of the body written below it.
    header = ("format: %s\nlength: %d bytes\n\n"
              % (format_from_ctype(ctype), len(body))).encode("utf-8")
    out = sys.stdout.buffer
    out.write(header)
    out.write(body)
    out.flush()


if __name__ == "__main__":
    main()
