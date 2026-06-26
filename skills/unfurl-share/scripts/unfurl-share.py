#!/usr/bin/env python3
"""unfurl-share.py — publish Markdown/HTML to unfurl and print the Share link.

Python 3 standard-library only (no third-party deps). Flags, env vars,
error-code mapping, and output contract:

  success → the absolute Share link on stdout (exit 0)
  failure → a concise, code-mapped message on stderr (exit nonzero)

Credentials come from the environment so the same script serves a human at a
terminal and an Agent driving it programmatically:

  UNFURL_API_KEY   A Creator's API key (from the unfurl dashboard). Required.
  UNFURL_BASE_URL  Optional. Overrides the default instance (https://unfurl.anmuji.com),
                   e.g. for a self-hosted unfurl. Trailing slash is fine.

Optional:
  UNFURL_MAX_TIME         request socket timeout, seconds (default 30). The effective
                         value is max(UNFURL_MAX_TIME, UNFURL_CONNECT_TIMEOUT), so a
                         larger CONNECT_TIMEOUT can raise it.
  UNFURL_CONNECT_TIMEOUT  accepted for parity; folded into the timeout above.
  UNFURL_DEBUG=1          print full response bodies on unexpected errors.

Usage:
  echo '# Hello' | UNFURL_API_KEY=… unfurl-share.py
  echo '<b>hi</b>' | unfurl-share.py --format html --title "Greeting"
  unfurl-share.py --file ./note.md --title "Notes"
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import NoReturn

ENDPOINT_PATH = "/api/v1/docs"
DEFAULT_FORMAT = "md"
DEFAULT_BASE_URL = "https://unfurl.anmuji.com"

# Exit codes: 2 == bad usage/config (caller's fault), 1 == runtime/API failure.
EXIT_USAGE = 2
EXIT_FAIL = 1


def die(msg, code=EXIT_FAIL) -> NoReturn:
    """Print a concise message to stderr and exit."""
    print(msg, file=sys.stderr)
    sys.exit(code)


# Turn a structured API error code into a concise, actionable message. The
# Agent relays this verbatim to the user, so keep it short and fix-oriented.
# Codes mirror POST /api/v1/docs (src/lib/api/errors.ts).
def map_error(code, raw):
    table = {
        "unauthorized": "Missing or unknown API key. Set UNFURL_API_KEY to a valid Creator key from your unfurl dashboard.",
        "invalid_key": "Your API key has been revoked. Generate a new one in the unfurl dashboard.",
        "invalid_format": "Invalid format. Use 'md' (Markdown) or 'html'.",
        "empty_content": "Content is empty. Provide Markdown or HTML body.",
        "bad_request": 'Malformed request body. Send JSON like {"format":"md","content":"..."}.',
        "content_too_large": "Content exceeds the size cap (~1 MiB). Trim or split it.",
        "rate_limited": "Rate limit hit for this key (per-hour quota). Wait and retry, or rotate to another key.",
        "render_failed": "Content could not be rendered. Check for malformed Markdown or HTML.",
        "lookup_failed": "Server could not verify the key right now (transient). Retry in a moment.",
        "create_failed": "Server failed to save the Doc right now (transient). Retry in a moment.",
    }
    return table.get(
        code,
        "Unexpected error from unfurl (code: {}). Response: {}".format(code, raw_hint(raw)),
    )


def raw_hint(raw):
    """Render a raw response body for a diagnostic stderr line.

    By default a single truncated, whitespace-collapsed hint so it doesn't drown
    out the actionable message. UNFURL_DEBUG=1 prints the body unchanged.
    """
    if raw is None:
        return ""
    if os.environ.get("UNFURL_DEBUG", "0") == "1":
        return raw
    one_line = re.sub(r"[\s]+", " ", raw).strip()
    return one_line[:200] + "..." if len(one_line) > 200 else one_line


def extract_field(body, field):
    """Pull a top-level string field out of a JSON response body.

    json.loads when the body is valid JSON; a regex fallback otherwise (e.g. an
    HTML error page from a proxy), correct for the flat, string-valued fields
    this API returns.
    """
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            val = data.get(field)
            return val if isinstance(val, str) else None
    except (ValueError, TypeError):
        pass
    m = re.search(r'"%s"\s*:\s*"([^"]*)"' % re.escape(field), body or "")
    return m.group(1) if m else None


def positive_int(value, default):
    try:
        n = int(value)
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


def parse_args():
    p = argparse.ArgumentParser(
        prog="unfurl-share.py",
        add_help=True,
        description="Reads content from stdin (or --file), POSTs it to unfurl, prints the Share link.",
    )
    p.add_argument("--format", default=DEFAULT_FORMAT, help="md (default) or html")
    p.add_argument("--title", default="")
    p.add_argument("--file", default="")
    p.add_argument("--base-url", dest="base_url", default=os.environ.get("UNFURL_BASE_URL", DEFAULT_BASE_URL))
    p.add_argument("--api-key", dest="api_key", default=os.environ.get("UNFURL_API_KEY", ""))
    # argparse exits 2 on unknown args / missing values, matching the bash script.
    return p.parse_args()


def main():
    args = parse_args()

    # --- validate config -----------------------------------------------------
    if not args.api_key:
        die("UNFURL_API_KEY is not set. Create a key in your unfurl dashboard and export it.", EXIT_USAGE)
    if not args.base_url:
        die("Base URL is empty. It defaults to the unfurl instance; pass --base-url (or set UNFURL_BASE_URL) to override it.", EXIT_USAGE)
    base_url = args.base_url.rstrip("/")  # tolerate a trailing slash
    if args.format not in ("md", "html"):
        die("Invalid --format '%s'. Use 'md' or 'html'." % args.format, EXIT_USAGE)

    # --- read content --------------------------------------------------------
    if args.file:
        try:
            # errors="replace" mirrors stdin decoding so a non-UTF-8 file degrades
            # to a readable string instead of crashing with a traceback.
            with open(args.file, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError:
            die("Cannot read file: %s" % args.file, EXIT_USAGE)
    else:
        content = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    if not content.strip():
        die("No content provided (stdin or --file is empty).", EXIT_USAGE)

    # --- build payload -------------------------------------------------------
    payload = {"format": args.format, "content": content}
    if args.title:
        payload["title"] = args.title
    data = json.dumps(payload).encode("utf-8")

    # --- send ----------------------------------------------------------------
    url = base_url + ENDPOINT_PATH
    # urllib uses a single socket timeout; honor the larger of the two knobs so
    # neither artificially caps the request. Defaults match the bash script.
    timeout = max(
        positive_int(os.environ.get("UNFURL_MAX_TIME"), 30),
        positive_int(os.environ.get("UNFURL_CONNECT_TIMEOUT"), 10),
    )
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": "Bearer " + args.api_key,
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            http_code = resp.getcode()
            response = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        # Non-2xx: curl-equivalent path. The error body carries the code.
        http_code = e.code
        response = e.read().decode("utf-8", errors="replace") if e.fp else ""
        _report_non_2xx(http_code, response)
    except urllib.error.URLError as e:
        die("Could not reach unfurl at %s: %s" % (url, getattr(e, "reason", e)))
    except (TimeoutError, OSError) as e:
        die("Could not reach unfurl at %s: %s" % (url, e))

    # --- interpret success ---------------------------------------------------
    if 200 <= http_code < 300:
        link = extract_field(response, "share_link")
        if link:
            print(link)
            sys.exit(0)
        die("Published, but the response had no share_link. Response: %s" % raw_hint(response))

    # urlopen would have raised for non-2xx, but be defensive.
    _report_non_2xx(http_code, response)


def _report_non_2xx(http_code, response) -> NoReturn:
    code = extract_field(response, "error")
    if code:
        die(map_error(code, response))
    die("unfurl returned HTTP %s with no error code. Response: %s" % (http_code, raw_hint(response)))


if __name__ == "__main__":
    main()
