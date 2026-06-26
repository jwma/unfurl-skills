---
name: unfurl-share
description: Publish Markdown or HTML to unfurl and return the Share link. Use when the user wants to publish, post, upload, or share content (a doc, writeup, notes, article, snippet) to unfurl, or mentions unfurl, a share link, or UNFURL_API_KEY.
---

# unfurl-share

Publish Markdown or HTML to an unfurl instance and get back the **Share link** — the single, unguessable URL a Viewer opens to read the rendered Page. A thin, portable Python 3 script does the POST (`scripts/unfurl-share.py`, standard library only); this skill is what tells an Agent when and how to use it.

## Setup

Set one environment variable (the script reads it every run):

- `UNFURL_API_KEY` — a Creator's API key. Create one in the unfurl dashboard (**Dashboard → API keys**). Only a keyed hash is stored server-side; copy the key now.

Add it to your shell profile (e.g. `~/.zshrc`) or export it in the session before the Agent runs. The unfurl instance is fixed at `https://unfurl.anmuji.com`; pass `--base-url` (or set `UNFURL_BASE_URL`) only to target a self-hosted instance.

## Publish

The script reads content from **stdin** (or `--file`) and prints **only the Share link** on success. Relay that URL to the user verbatim. Run it with `python3` (it also has a `#!/usr/bin/env python3` shebang and is `chmod +x`):

```sh
echo '# Hello unfurl' | python3 scripts/unfurl-share.py                   # Markdown (default)
echo '<b>Hi</b>'      | python3 scripts/unfurl-share.py --format html     # HTML
python3 scripts/unfurl-share.py --file ./notes.md --title "Project notes" # from a file
```

Flags: `--format md|html` (default `md`), `--title "…"`, `--file PATH`, `--api-key`, `--base-url` (override the default instance for one call).

The script posts `Authorization: Bearer $UNFURL_API_KEY` to `POST https://unfurl.anmuji.com/api/v1/docs` with a JSON body `{ format, content, title? }`. It uses only the Python 3 standard library (`urllib`, `json`) — no third-party packages, no Node, no `jq`.

## Errors

On failure the script exits nonzero and prints **one concise, mapped message** to stderr — relay that to the user; do not surface raw HTTP. Exit codes: `2` for usage/config the script catches locally (missing key, bad `--format`, empty stdin/`--file`); `1` for runtime/API failures — including the structured error codes below:

| code | means | fix |
|------|-------|-----|
| `unauthorized` | missing/unknown key | set a valid `UNFURL_API_KEY` |
| `invalid_key` | key revoked | generate a new key in the dashboard |
| `invalid_format` | format not `md`/`html` | use `--format md` or `--format html` |
| `empty_content` | blank body | provide content |
| `bad_request` | malformed JSON body | (script handles this; shouldn't happen manually) |
| `content_too_large` | over ~1 MiB | trim or split the content |
| `rate_limited` | per-key hourly quota hit | wait, or rotate to another key |
| `render_failed` | content wouldn't render | fix malformed Markdown/HTML |
| `lookup_failed` / `create_failed` | transient server fault | retry shortly |

Sanity-check the Python script any time: `python3 -m py_compile scripts/unfurl-share.py`, and the config/validation paths run offline without network (e.g. `echo '' | python3 scripts/unfurl-share.py --api-key x --base-url http://x` exits 2 with "No content provided…").
