# unfurl-skills

Agent skills for **unfurl**, the single-URL document publisher. Publish Markdown or HTML and get back one unguessable Share link.

## What is unfurl?

[**unfurl**](https://unfurl.anmuji.com) is the last-mile sharing tool for AI-generated content: paste Markdown or HTML, get back one unguessable **Share link**, and anyone who opens it can read the rendered page — no login, no app, no download. The link is stable; edit the content and the same link keeps updating in place.

- **No login for viewers** — open the link and read. No sign-up wall, no pop-ups; the reading experience *is* the content.
- **Markdown or HTML** — Markdown is sanitized through a whitelist; a full HTML page renders inside a sandboxed iframe, so neither escapes.
- **Unique & unlisted** — every link is one of a kind and not indexed by search engines. Only people you hand it to can open it.
- **Built to be read** — the reading page ships serif headings, light/dark themes, and code highlighting, and it's mobile-friendly.

## Skills

| Skill | Description |
|-------|-------------|
| [`unfurl-share`](./skills/unfurl-share) | Publish Markdown or HTML to an unfurl instance and get back the Share link. |

## Install

Install a skill with the [open agent skills CLI](https://github.com/vercel-labs/skills) (`npx skills`). It auto-detects your coding agent (Claude Code, Codex, Cursor, and [70+ others](https://github.com/vercel-labs/skills#supported-agents)):

```sh
# interactive — pick the skill and the agent(s)
npx skills add jwma/unfurl-skills

# non-interactive examples
npx skills add jwma/unfurl-skills --skill unfurl-share -a claude-code -g -y  # Claude Code, global
npx skills add jwma/unfurl-skills --skill unfurl-share -a codex -y           # Codex, project-local
```

Scope flags:

| Flag | Meaning |
|------|---------|
| `-g, --global` | Install to the user directory (available across all projects) instead of the current project |
| `-a, --agent <name>` | Target a specific agent (`claude-code`, `codex`, `cursor`, …) |
| `-s, --skill <name>` | Install a specific skill by name |
| `-y, --yes` | Skip all confirmation prompts |
| `--copy` | Copy files instead of symlinking |

List skills without installing, or install all of them:

```sh
npx skills add jwma/unfurl-skills --list
npx skills add jwma/unfurl-skills --all
```

## Configure

`unfurl-share` reads one environment variable every run. Add it to your shell profile (e.g. `~/.zshrc`):

```sh
export UNFURL_API_KEY="..."        # a Creator's API key from the unfurl dashboard (Dashboard → API keys)
```

The unfurl instance is fixed at `https://unfurl.anmuji.com`. Set `UNFURL_BASE_URL` (or pass `--base-url`) only to target a self-hosted instance.

See the skill's [`SKILL.md`](./skills/unfurl-share/SKILL.md) for full usage, flags, and the error-code reference.

## Usage

Once the skill is installed and `UNFURL_API_KEY` is set, you don't run any command — you just **talk to your agent**. It recognizes the intent, runs the skill behind the scenes, and hands back the Share link. For example:

| You say … | … and the agent replies |
|-----------|--------------------------|
| "Publish `notes.md` to unfurl as *Project notes*." | `https://unfurl.anmuji.com/p/abc123` |
| "Turn this into a share link: `# Sprint 13 retro …`" | `https://unfurl.anmuji.com/p/def456` |
| "Post this HTML to unfurl: `<h1>Demo</h1>…`" | `https://unfurl.anmuji.com/p/ghi789` |
| "把这篇周报分享成链接。" | `https://unfurl.anmuji.com/p/jkl012` |

It triggers on *publish / share / post to unfurl*, *make a share link*, or any mention of **unfurl** — in any language. Point it at a file, paste the content inline, or just describe what to share; the agent picks the format and runs the script for you.

The underlying flags (`--format`, `--title`, `--file`, …) and the full error-code reference are in [`SKILL.md`](./skills/unfurl-share/SKILL.md) — you won't normally need them.

## Develop

Each skill is self-contained under `skills/<name>/`. The `unfurl-share` script is Python 3 standard-library only — no dependencies. Run its offline test suite:

```sh
python3 skills/unfurl-share/scripts/unfurl-share.test.py
```

## License

[MIT](./LICENSE)
