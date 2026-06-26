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

# Confirm `npx skills` discovers the skill(s) without installing:
npx skills add ./ --list
```

The test file is one self-contained `main()` with no per-case selector. To run a single case, scope `main()` in `skills/unfurl-share/scripts/unfurl-share.test.py` — each case is a `run_case(...)` call keyed by a stub response in `RESPONSES`.

## Architecture

**Skill discovery contract.** `npx skills add` walks `skills/<name>/SKILL.md` one level deep (the "flat layout"). A `SKILL.md` needs `name` + `description` YAML frontmatter. Paths to bundled files inside `SKILL.md` are **relative to the skill root** (where `SKILL.md` lives), per the [Agent Skills spec](https://agentskills.io/specification) — not relative to the agent's cwd. Keep them that way.

**`unfurl-share` is three coupled files:**
- `SKILL.md` — agent-facing: *when* to invoke (the `description` is the trigger), the required env var, the publish commands, and an error-code → fix table. It tells the agent to run the script and relay its output verbatim.
- `scripts/unfurl-share.py` — the implementation. Reads content from stdin or `--file`, POSTs JSON `{format, content, title?}` to `POST /api/v1/docs` on the unfurl instance (default `https://unfurl.anmuji.com`, overridable via `--base-url`/`UNFURL_BASE_URL`) with `Authorization: Bearer $UNFURL_API_KEY`.
- `scripts/unfurl-share.test.py` — a threaded loopback HTTP stub; no upstream, no Supabase.

**Output contract — don't break it.** On success the script prints **only** the absolute Share link on stdout and exits 0. On failure it prints **one** concise, mapped message on stderr and exits nonzero: `2` = usage/config the script caught locally (and made no network request); `1` = runtime/API failure. Both the agent's behavior and the test assertions depend on this exact shape.

**Error codes stay in sync across three places.** The `map_error()` table in `unfurl-share.py`, the error-code table in `SKILL.md`, and the `RESPONSES` map in the test all mirror the structured codes returned by unfurl's `POST /api/v1/docs`. The source of truth for that contract is the **unfurl project** (`src/lib/api/errors.ts` and the `/api/v1/docs` route). If the API changes there, update all three here together.

## Conventions

- Keep `unfurl-share.py` standard-library only (`urllib`, `json`) — that portability is the reason a Python script was chosen over a shell/node tool.
- Add new skills as `skills/<name>/` with their own `SKILL.md`; reference bundled assets with skill-root-relative paths.
