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
| [`unfurl-read`](./skills/unfurl-read) | Read the verbatim content of a shared unfurl Doc from its link — raw Markdown/HTML via the `/source` endpoint, minimum tokens. |

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

See the skill's [`SKILL.md`](./skills/unfurl-share/SKILL.md) for full usage, flags, and the error-code reference. Reading a shared Doc (`unfurl-read`) needs **no** API key — the Share link alone is enough.

## Usage

Once the skill is installed and `UNFURL_API_KEY` is set, you don't run any command — you just **talk to your agent**. It recognizes the intent, runs the skill behind the scenes, and hands back the Share link. It works in any language — English or 中文:

**English**

| You say … | … and the agent replies |
|-----------|--------------------------|
| "Publish `notes.md` to unfurl as *Project notes*." | `https://unfurl.anmuji.com/p/abc123` |
| "Turn this into a share link: `# Sprint 13 retro …`" | `https://unfurl.anmuji.com/p/def456` |
| "Post this HTML to unfurl: `<h1>Demo</h1>…`" | `https://unfurl.anmuji.com/p/ghi789` |

**中文**

| 你说…… | agent 回复 |
|--------|------------|
| "把 `notes.md` 发布到 unfurl，标题《项目周报》。" | `https://unfurl.anmuji.com/p/jkl012` |
| "把这个分享成链接：`# 第 13 期周报……`" | `https://unfurl.anmuji.com/p/mno345` |
| "把这段 HTML 发到 unfurl：`<h1>演示</h1>…`" | `https://unfurl.anmuji.com/p/pqr678` |

**Or chain it into a bigger task.** Describe the whole job and end with the skill — the agent does the work, then publishes the result:

> "Analyze this source file, add Mermaid diagrams to illustrate it, write it up as Markdown, then `/unfurl-share`."

> "分析当前这段源代码，用 Mermaid 画图辅助说明，整理成 md，然后 `/unfurl-share`。"

The agent builds the writeup and hands back the Share link. (Naming the skill directly with `/unfurl-share` is just an explicit trigger — plain intent works too.)

It triggers on *publish / share / post to unfurl*, *make a share link*, or any mention of **unfurl**. Point it at a file, paste the content inline, or just describe what to share; the agent picks the format and runs the script for you.

The underlying flags (`--format`, `--title`, `--file`, …) and the full error-code reference are in [`SKILL.md`](./skills/unfurl-share/SKILL.md) — you won't normally need them.

### Read a shared Doc

Paste an unfurl **Share link** into the conversation and ask about it. The agent fetches the Doc's raw content through the dedicated `/source` endpoint and reads that directly, instead of scraping the rendered page — far fewer tokens, no boilerplate to filter out. **No API key is needed to read**; the Share link alone is enough.

**English**

| You say … | … and the agent does |
|-----------|----------------------|
| "Summarize `https://unfurl.anmuji.com/p/abc123`." | reads the Doc's Markdown/HTML and summarizes it |
| "What does `https://unfurl.anmuji.com/p/abc123` actually say?" | reads and explains it in plain terms |
| "Translate `https://unfurl.anmuji.com/p/abc123` to English." | reads the source and translates |

**中文**

| 你说…… | agent 的反应 |
|--------|--------------|
| "帮我总结一下 `https://unfurl.anmuji.com/p/abc123`。" | 读取原文并总结 |
| "`https://unfurl.anmuji.com/p/abc123` 这篇讲了什么？" | 读取并用大白话讲解 |
| "把 `https://unfurl.anmuji.com/p/abc123` 翻译成英文。" | 读取源文并翻译 |

It triggers whenever you hand the agent an unfurl URL and want the content — summarize, explain, answer questions, translate, or reuse it. See [`unfurl-read/SKILL.md`](./skills/unfurl-read/SKILL.md) for details.

## Develop

Each skill is self-contained under `skills/<name>/`. Both scripts are Python 3 standard-library only — no dependencies. Run their offline test suites (no network, no credentials):

```sh
python3 skills/unfurl-share/scripts/unfurl-share.test.py
python3 skills/unfurl-read/scripts/unfurl-read.test.py
```

## License

[MIT](./LICENSE)
