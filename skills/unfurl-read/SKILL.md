---
name: unfurl-read
description: Read the verbatim content of an unfurl Doc (Markdown or HTML) from its Share link via the dedicated /source endpoint — minimum tokens, no rendered chrome. Use when the user gives you an unfurl URL (e.g. https://unfurl.anmuji.com/p/abc123) and wants you to read, summarize, answer questions about, discuss, translate, or otherwise reuse the content behind that link.
---

# unfurl-read

Read an unfurl Doc's content straight from its **Source** — the raw Markdown or HTML the Creator wrote — instead of the human-facing Page. The Page is rendered HTML wrapped in unfurl's chrome; fetching it wastes context on boilerplate and forces you to pick the content back out of a page. The Source (`/p/{token}/source`) returns the content verbatim and nothing else: Markdown Docs as original Markdown, HTML Docs as original HTML. Same Share link, a machine-facing representation built for Agents.

A thin, portable Python 3 script does the GET (`scripts/unfurl-read.py`, standard library only); this skill is what tells an Agent when and how to use it.

## Read

Pass the Share link (or a bare token). The script prints a one-line **format**, a **length**, then the verbatim content. Read that output directly — don't fetch the Page yourself and don't try to parse the rendered HTML.

```sh
python3 scripts/unfurl-read.py https://unfurl.anmuji.com/p/abc123   # from a Share link
python3 scripts/unfurl-read.py abc123                                # bare token, default instance
python3 scripts/unfurl-read.py abc123 --base-url http://self-hosted  # self-hosted instance
```

The Share link and its `/source` are siblings — pasting either works (appending `/source` is idempotent). No API key and no account are needed; the Source is token-based, same as the Page, and reading it does **not** count as a View.

## Output

On success (exit 0) the script prints, on stdout:

```
format: markdown
length: 1234 bytes

<verbatim content of the Doc>
```

`format` is `markdown` or `html` (read from the response Content-Type, so you parse the body correctly without sniffing). `length` is the exact **byte** count of the content as served — `0` means a legitimately empty Doc (a live but blank Doc returns 200, not an error), not a failure. Everything after the blank line is the Doc's content exactly as the Creator wrote it, written **byte-for-byte** (raw bytes to stdout — no decode/encode round-trip, no replacement characters, no wrapper, no injected scripts, no metadata).

## Errors

On failure the script exits nonzero and prints **one concise, mapped message** to stderr — relay that to the user; don't surface raw HTTP. Exit codes: `2` for usage the script catches locally (the input isn't an unfurl Share link or token); `1` for runtime/API failures:

| situation | means | fix |
|-----------|-------|-----|
| `404` | Doc is taken down, flagged / under review, or doesn't exist | the Source is hidden whenever the Page is; open the Share link in a browser to check its status |
| other non-2xx | transient server fault or bad gateway | retry shortly |
| could not reach unfurl | network / DNS / timeout | check connectivity, or the base URL for a bare token |

Sanity-check the script any time: `python3 -m py_compile scripts/unfurl-read.py`, and the usage path runs offline without network (e.g. `python3 scripts/unfurl-read.py https://example.com/foo` exits 2 with "Not an unfurl share link").
