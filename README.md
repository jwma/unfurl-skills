# unfurl-skills

Agent skills for **unfurl**, the single-URL document publisher. Publish Markdown or HTML and get back one unguessable Share link.

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

`unfurl-share` reads two environment variables every run. Add them to your shell profile (e.g. `~/.zshrc`):

```sh
export UNFURL_API_KEY="..."        # a Creator's API key from the unfurl dashboard (Dashboard → API keys)
export UNFURL_BASE_URL="https://unfurl.example.com"   # your unfurl instance, no path
```

See the skill's [`SKILL.md`](./skills/unfurl-share/SKILL.md) for full usage, flags, and the error-code reference.

## Develop

Each skill is self-contained under `skills/<name>/`. The `unfurl-share` script is Python 3 standard-library only — no dependencies. Run its offline test suite:

```sh
python3 skills/unfurl-share/scripts/unfurl-share.test.py
```

## License

[MIT](./LICENSE)
