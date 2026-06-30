# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A standalone **agent-skills** collection, installable with the open skills CLI: `npx skills add jwma/unfurl-skills`. It was extracted out of the unfurl monorepo so each skill can ship and install independently. Every skill is its own directory under `skills/<name>/`.

## Commands

The only runtime language is Python 3 — standard library only. There is no build step, no package manager, and no linter configured.

```sh
# Offline test suite for unfurl-share. Stubs HTTP on loopback and sets its own
# env, so it needs NO network and NO credentials.
python3 skills/unfurl-share/scripts/unfurl-share.test.py

# Byte-compile check (catches syntax errors).
python3 -m py_compile skills/unfurl-share/scripts/unfurl-share.py

# Offline usage/config check — exits 2 with a mapped message, makes no request.
echo '' | python3 skills/unfurl-share/scripts/unfurl-share.py --api-key x --base-url http://x

# Actually publish (needs UNFURL_API_KEY; instance defaults to https://unfurl.anmuji.com):
echo '# Hello' | UNFURL_API_KEY=… \
  python3 skills/unfurl-share/scripts/unfurl-share.py

# Offline test suite for unfurl-read (same shape: loopback stub, no network/key).
python3 skills/unfurl-read/scripts/unfurl-read.test.py

# Byte-compile check.
python3 -m py_compile skills/unfurl-read/scripts/unfurl-read.py

# Offline usage check — exits 2 with a mapped message, makes no request.
python3 skills/unfurl-read/scripts/unfurl-read.py https://example.com/foo

# Actually read a Doc (token-based, no key needed):
python3 skills/unfurl-read/scripts/unfurl-read.py https://unfurl.anmuji.com/p/<token>

# Confirm `npx skills` discovers the skill(s) without installing:
npx skills add ./ --list
```

Each test file is one self-contained `main()` with no per-case selector. To run a single case, scope `main()` in the respective `*.test.py` — each case is a `run_case(...)` call keyed by a stub response in `RESPONSES`.

## Architecture

**Skill discovery contract.** `npx skills add` walks `skills/<name>/SKILL.md` one level deep (the "flat layout"). A `SKILL.md` needs `name` + `description` YAML frontmatter. Paths to bundled files inside `SKILL.md` are **relative to the skill root** (where `SKILL.md` lives), per the [Agent Skills spec](https://agentskills.io/specification) — not relative to the agent's cwd. Keep them that way.

**`unfurl-share` is three coupled files:**
- `SKILL.md` — agent-facing: *when* to invoke (the `description` is the trigger), the required env var, the publish commands, and an error-code → fix table. It tells the agent to run the script and relay its output verbatim.
- `scripts/unfurl-share.py` — the implementation. Reads content from stdin or `--file`, POSTs JSON `{format, content, title?}` to `POST /api/v1/docs` on the unfurl instance (default `https://unfurl.anmuji.com`, overridable via `--base-url`/`UNFURL_BASE_URL`) with `Authorization: Bearer $UNFURL_API_KEY`.
- `scripts/unfurl-share.test.py` — a threaded loopback HTTP stub; no upstream, no Supabase.

**Output contract — don't break it.** On success the script prints **only** the absolute Share link on stdout and exits 0. On failure it prints **one** concise, mapped message on stderr and exits nonzero: `2` = usage/config the script caught locally (and made no network request); `1` = runtime/API failure. Both the agent's behavior and the test assertions depend on this exact shape.

**Error codes stay in sync across three places.** The `map_error()` table in `unfurl-share.py`, the error-code table in `SKILL.md`, and the `RESPONSES` map in the test all mirror the structured codes returned by unfurl's `POST /api/v1/docs`. The source of truth for that contract is the **unfurl project** (`src/lib/api/errors.ts` and the `/api/v1/docs` route). If the API changes there, update all three here together.

**`unfurl-read` is the read-side peer — three coupled files:**
- `SKILL.md` — agent-facing: *when* to invoke (the `description` triggers on the user handing over an unfurl URL to read/summarize/discuss), the read commands, and a situation → fix table. It tells the agent to fetch `/source` instead of scraping the rendered Page.
- `scripts/unfurl-read.py` — the implementation. Takes a Share link / `/source` URL / bare token, derives `/p/{token}/source`, and GETs it with **no auth** (token-based, like the Page). Prints a `format:` + `length:` header, a blank line, then the verbatim content.
- `scripts/unfurl-read.test.py` — a threaded loopback HTTP stub; no upstream, no key.

**`/source` contract (unfurl issue #150 / ADR-0017).** `GET /p/{token}/source` serves a live Doc's content verbatim — `text/markdown; charset=utf-8` for Markdown, `text/html; charset=utf-8` for HTML; no frame harness, no JSON envelope. Flagged / taken_down / missing → `404`; a live but empty Doc → `200` with an empty body (not an error). It is `force-dynamic`, sends `X-Robots-Tag: noindex, nofollow`, reads via `loadDocByToken`, and is **not** counted as a View. The bare body is a frozen public contract — future metadata arrives via response headers, never by wrapping the body. Source of truth: the **unfurl project** (`app/p/[token]/source/route.ts`). The read-side output contract mirrors share's: success → header + verbatim content on stdout, exit 0; failure → one mapped message on stderr, `2` = usage (not a share link / bad token, and no request made), `1` = runtime/API (404, other non-2xx, network).

## Conventions

- Keep both scripts standard-library only (`urllib`, `json`, …) — that portability is the reason a Python script was chosen over a shell/node tool. `unfurl-read.py` additionally uses `urllib.parse`.
- Add new skills as `skills/<name>/` with their own `SKILL.md`; reference bundled assets with skill-root-relative paths.
