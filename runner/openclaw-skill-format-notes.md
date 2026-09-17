# OpenClaw SKILL.md format — discovery notes

Captured 2026-04-12 from the live OpenClaw container (`ghcr.io/openclaw/openclaw:latest`) and the public skills registry mounted at `/tmp/openclaw-skills/`.

## File layout

- A skill is a directory containing **at least** a `SKILL.md` file.
- Skill directories live under `<workspace>/.openclaw/skills/<skill-name>/` (workspace bind = `/home/adr2370/openclaw/workspace`).
- Sibling files (config JSON, scripts, helper docs) are allowed and accessible via relative paths from inside the skill.

System skills also exist under `/home/node/.openclaw/extensions/<name>/SKILL.md` — same format.

## Frontmatter

YAML between `---` markers at the top of the file. Required and optional fields observed in the wild:

```yaml
---
name: pictionary-biweekly                        # REQUIRED, kebab-case identifier
description: One-line summary of what the skill does.   # REQUIRED, used by the agent for skill selection
version: 1.0                                     # OPTIONAL
metadata:                                        # OPTIONAL
  openclaw:
    emoji: "🎨"                                  # OPTIONAL, shown in UI
---
```

Both example skills I read used kebab-case names; the registry contains hundreds with `name: <kebab-case>`. Stick to it.

## Body

Free-form markdown. No required sections. Headings are conventional but not enforced. The agent reads this as natural-language guidance and uses its judgment.

Common patterns observed:
- `## What it does` — one-paragraph framing
- `## Inputs` — what the skill expects (credentials, config files, etc.)
- `## Steps` — numbered procedure (the agent follows this in order)
- `## Failure handling` — what to do when something breaks
- `## Hard rules` — explicit "never do X" constraints

The wechat-publisher skill (a browser-driven publishing skill, similar shape to ours) uses a `### 1. Install`, `### 2. Configure`, `### 3. Publish` structure with example commands inline. The context-compactor skill uses an architecture diagram + config table format.

## How credentials are referenced

Skills reference credentials by name from OpenClaw's credentials store (e.g., `socialchamp.email`). The agent fetches the value at runtime — the literal value never appears in the SKILL.md.

## How tools are invoked

Skills do NOT specify "use the browser tool" or "use the telegram tool" explicitly — they just describe the action ("Navigate to https://..." / "DM the user on Telegram"). The agent picks the right tool based on its plugins. Plugins enabled in this gateway: `anthropic`, `ollama`, `browser`, `openrouter`, `context-compactor`. Telegram is enabled as a *channel*, which the agent reaches via channel APIs rather than a discrete tool name.

## Skill discovery

The OpenClaw gateway scans `<workspace>/.openclaw/skills/` (and `~/.openclaw/extensions/` for system skills) on startup. To register a new skill, drop the directory in place and either restart the gateway or wait for it to rescan (some versions auto-reload).

## Implications for `pictionary-biweekly`

- Place at `/home/adr2370/openclaw/workspace/.openclaw/skills/pictionary-biweekly/` (host path) = `/home/node/.openclaw/workspace/.openclaw/skills/pictionary-biweekly/` inside the openclaw container.
- Frontmatter: name + description + emoji.
- Body: free-form, follow the structure already drafted in the implementation plan.
- Reference credentials by name (`socialchamp.email`, `socialchamp.password`, `runner.token`).
- For the file upload step in Step 4/5: the path must be a path *inside the openclaw container* (i.e., `/home/node/uploads/...`), because the openclaw browser plugin reads the file bytes itself and ships them to chromium via `DOM.setFileInputFiles`. The chromium container does not need direct access.
