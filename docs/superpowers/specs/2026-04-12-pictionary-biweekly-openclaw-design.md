# Pictionary Biweekly — OpenClaw Automation Design

**Date:** 2026-04-12
**Author:** Alex (with Claude)
**Status:** Approved, pending implementation plan

## Goal

Fully automate the biweekly Pictionary content pipeline so it runs unattended:

1. Generate ~300 new Pictionary videos via `python main.py`
2. Reconnect every social media account in Social Champ (their tokens go stale)
3. Bulk-upload the SHORTS and VIDEO CSVs to Social Champ, each to a different set of target accounts
4. Notify the human on success or failure

The human currently does steps 2–4 by hand every two weeks. After this work, those steps run themselves.

## Key constraints and facts

- `main.py` already produces two CSVs in Social Champ's exact bulk-upload format: `bulk_upload_csvs/ai_pictionary_bulk_upload_SHORTS_<ts>.csv` and `..._VIDEO_<ts>.csv`. No transformation needed.
- `main.py` uses local GPU (ComfyUI + LoRAs) and runs for hours. It cannot run inside the openclaw container.
- Social Champ has no public API. Bulk upload happens through their web UI.
- Social Champ login is email + password, no MFA.
- Reconnecting accounts is a pure click-through OAuth flow — no phone taps, no codes.
- The user already runs an OpenClaw stack on WSL2 with: gateway on `localhost:18789`, browser plugin wired to a `chromium` container via CDP, Telegram channel (`@adr2370`), Home Assistant MCP, Ollama, and a single agent named `main`. Default model is `openrouter/deepseek/deepseek-v3.2`; Anthropic Claude Opus 4.6 is also available.
- The `chromium` container has **no host bind mounts** — it cannot read Windows files directly. The OpenClaw browser plugin uploads files via CDP `DOM.setFileInputFiles`, which reads bytes from the openclaw container's filesystem and ships them to chromium. So files must be readable from inside the openclaw container.
- The user prefers minimal noise, no over-reaching agents, and tightly scoped task definitions (per `MEMORY.md` / `USER.md`).

## Approach

**OpenClaw owns the cadence.** OpenClaw cron fires the workflow; the workflow's first step is calling a tiny HTTP runner on the host that executes `main.py` and waits for completion. This keeps the entire pipeline observable in one place (the OpenClaw Control UI) and gives a single source of truth for scheduling.

Two alternatives were considered and rejected:

- **Host-driven (Windows Task Scheduler is master):** Simpler, but cadence + observability split between two systems.
- **Decoupled flag-file handoff:** No coupling, but two scheduling sources, polling delay, more state.

## Architecture

```
                          ┌──────────────────────────┐
                          │  Windows / WSL host       │
                          │                           │
   ┌─────────┐  HTTP      │  runner.py  ─── runs ───▶ python main.py
   │ openclaw│ ─────────▶ │  (port 18790, loopback)   │  ↓
   │ container│           │                           │  writes CSVs to:
   │ (cron+  │            │                           │  bulk_upload_csvs/
   │ skill)  │            └──────────┬────────────────┘     ↓
   │         │                       │ bind mount             
   │         │ ◀─────────────────────┴── /home/node/uploads (read-only)
   │         │
   │         │ CDP
   │         │ ──▶ chromium-proxy ──▶ chromium ──▶ socialchamp.com
   │         │ ──▶ Telegram (success + failure ping)
   └─────────┘
```

## Components

### 1. `runner.py` — host-side HTTP runner

A small Python service running on the host (Windows or WSL), exposed on `127.0.0.1:18790` only. The openclaw container reaches it via `host.docker.internal:18790`.

- **Endpoint:** `POST /run-pictionary` (token-authenticated via `Authorization: Bearer <runner.token>`)
- **Behavior:** Runs `python main.py` (no arguments — `main.py` is already configured to do the right thing) in the `ai_pictionary` directory, streams stdout/stderr to a per-run log file, blocks until the process exits, then locates the two newest CSVs in `bulk_upload_csvs/` (the `_SHORTS_` and `_VIDEO_` files matching the run's timestamp) and returns them.
- **Response (success):**
  ```json
  {
    "ok": true,
    "exit_code": 0,
    "shorts_csv_path": "/home/node/uploads/ai_pictionary_bulk_upload_SHORTS_20260426_020000.csv",
    "video_csv_path":  "/home/node/uploads/ai_pictionary_bulk_upload_VIDEO_20260426_020000.csv",
    "log_path": "/path/on/host/runner_logs/2026-04-26T02-00-00.log",
    "duration_seconds": 7421
  }
  ```
  Note that the CSV paths returned are the **openclaw container paths** (under `/home/node/uploads`), not the host paths — the runner translates so the agent doesn't have to think about it.
- **Response (failure):** `{"ok": false, "exit_code": N, "log_tail": "...", "log_path": "..."}`
- **Concurrency:** Refuses to start a new run if one is already in progress (returns `409` with the in-progress run id).
- **Lifecycle:** Auto-starts at logon via Windows Task Scheduler (or NSSM if NSSM is already installed). Restarts on crash.
- **Auth:** Single shared token, stored on the host in a config file, mirrored into OpenClaw's credentials store as `runner.token`.

### 2. New bind mount on the `openclaw` container

Add to whatever brings up the openclaw stack (docker-compose):

```yaml
volumes:
  - /c/Users/adr23/Projects/ai_pictionary/bulk_upload_csvs:/home/node/uploads:ro
```

(Path syntax depends on whether docker-compose runs from WSL or from Windows; the spec implementation will handle the path mapping.)

This is read-only because openclaw never writes CSVs — only reads them to upload. Restart the openclaw container once after adding.

### 3. Skill: `pictionary-biweekly`

Lives in the OpenClaw workspace at:

```
/home/adr2370/openclaw/workspace/.openclaw/skills/pictionary-biweekly/
  SKILL.md
  pictionary-config.json
  README.md
```

`SKILL.md` is a procedural guide — high-level enough that the agent's vision/judgment handles UI variation, specific enough that there's no ambiguity. Walks through:

1. **Preflight.** Check for `failed.flag` in the workspace. If present, abort and Telegram-DM "previous run failed and was not cleared — refusing to fire."
2. **Run the generator.** POST to `http://host.docker.internal:18790/run-pictionary` with the runner token. Block until it returns. Parse `shorts_csv_path` and `video_csv_path`. On non-200 or `ok: false`, abort → failure handling.
3. **Open Social Champ and log in.** Browser-tool to `https://socialchamp.com`. Use credentials `socialchamp.email` and `socialchamp.password`. If a saved session is still valid, skip the login form. Screenshot after login as a sanity check.
4. **Reconnect everything.** Navigate to the Social Accounts page. For every connected account, click Reconnect, complete the OAuth popup ("Continue as Alex" → "Authorize"), wait for success, move on. Always do all of them — no smart filtering.
5. **Bulk upload SHORTS.** Go to Bulk Upload. Select the target accounts listed in `pictionary-config.json` under `shorts_target_accounts`. Drag in `shorts_csv_path`. Wait for parse success. Click Schedule. Confirm. Screenshot.
6. **Bulk upload VIDEO.** Same as step 5 but with `video_target_accounts` and `video_csv_path`.
7. **Report success.** Telegram-DM @adr2370: `✅ Pictionary biweekly run complete. SHORTS: N posts → [accounts]. VIDEO: N posts → [accounts]. Next run: <date>.` Update `MEMORY.md` with a one-line note.

The skill explicitly does NOT:
- Try to be clever about which accounts need reconnecting (always all)
- Retry on flake more than once per step
- Re-run `main.py` on its own — only the runner can do that
- Touch any other workspace files

`pictionary-config.json` — captured during the supervised first run, then read on every subsequent run:

```json
{
  "shorts_target_accounts": ["YouTube Shorts Channel", "TikTok @adr2370"],
  "video_target_accounts": ["YouTube Main Channel", "Facebook Page"],
  "known_quirks": [],
  "last_successful_run": "2026-04-26T03:14:00-07:00"
}
```

(Account names above are placeholders; the real ones get filled in during the first run.)

`README.md` — one-paragraph explanation for future humans.

### 4. Cron entry in `cron/jobs.json`

```json
{
  "version": 1,
  "jobs": [
    {
      "id": "pictionary-biweekly",
      "schedule": "0 2 1,15 * *",
      "tz": "America/Los_Angeles",
      "agent": "main",
      "model": "anthropic/claude-opus-4-6",
      "thinking": "high",
      "skill": "pictionary-biweekly",
      "channel": "telegram",
      "enabled": true
    }
  ]
}
```

Schedule: 2:00 AM Pacific, on the 1st and 15th of every month. Close enough to "every 2 weeks" without the `*/14` cron quirk that resets across month boundaries.

Model override: `anthropic/claude-opus-4-6` (instead of the default `openrouter/deepseek/deepseek-v3.2`) because browser work benefits from the strongest available model. `thinking: high` for the same reason.

### 5. Credentials

Added to OpenClaw's `credentials/` store (via the Control UI at `localhost:18789`):

- `socialchamp.email`
- `socialchamp.password`
- `runner.token`

The skill references these by name, never by literal value. The host runner reads its copy of the token from a host-side config file (e.g. `C:/Users/adr23/.openclaw-runner/config.json`) with locked-down permissions.

## Failure handling

- **Any skill step throws or times out:** Telegram-DM @adr2370 with the failing step name, a screenshot of the browser at time of failure, and the last ~50 lines of any relevant log. Write `failed.flag` in the workspace.
- **`failed.flag` present at the next cron firing:** preflight aborts immediately and re-DMs. Saves wasting a 2+ hour `main.py` run.
- **Clearing the flag:** human deletes the file (or tells the agent in chat to clear it).
- **Runner unreachable:** treated as a failure of step 2; same handling.
- **Telegram unavailable:** the agent still writes the failure to its memory file and the workspace flag, so the next interactive session surfaces it.

## Notifications

Telegram DMs to @adr2370 on **both** success and failure (per user preference for awareness without dashboard-checking).

- **Success format:** `✅ Pictionary biweekly run complete. SHORTS: N posts → [accounts]. VIDEO: N posts → [accounts]. Next run: <date>.`
- **Failure format:** `❌ Pictionary biweekly failed at step <name>. Log tail attached. Screenshot attached. Run blocked until you clear failed.flag.`

## Out of scope (explicit cuts)

- **Notification channels other than Telegram.** Telegram is already wired and proven. Email/Slack/etc. can be added later if needed.
- **Smart "only reconnect what needs it" logic.** Always reconnecting everything is dumb but reliable; clicks are free.
- **Alternate scheduling cadences or per-account schedules.** Out of scope.
- **Touching `main.py` itself.** The host runner wraps it; the script stays as it is.
- **Migrating to a Social Champ API.** No public API exists.
- **Replacing the existing TikTok/YouTube uploaders inside `main.py`.** Those are unrelated to Social Champ and stay where they are.

## One-time setup checklist

In execution order:

1. Write `runner.py` and install it as a host startup service.
2. Generate `runner.token`, store on host and in OpenClaw credentials.
3. Add `socialchamp.email` and `socialchamp.password` to OpenClaw credentials.
4. Add the bind mount to the openclaw container; restart openclaw.
5. Drop the skill files (`SKILL.md`, empty `pictionary-config.json`, `README.md`) into the workspace.
6. Add the cron entry to `jobs.json`. Leave `enabled: false` until after the supervised first run.
7. **Supervised first run:** in the OpenClaw Control UI, manually invoke the skill. Watch the agent work through Social Champ end-to-end. As it works, fill in `pictionary-config.json` with the real account names and any UI quirks the agent surfaces.
8. Verify the success DM lands on Telegram.
9. Set the cron entry to `enabled: true`.
10. Done. The next 1st or 15th at 2 AM Pacific runs unattended.

## Open questions for the implementation phase

These are deferred to the implementation plan (writing-plans), not to this design:

- Exact docker-compose path syntax for the bind mount (depends on whether compose runs from WSL vs Windows).
- Whether to use NSSM, Windows Task Scheduler, or a simple `pythonw.exe` launcher for the runner.
- The exact OpenClaw skill discovery path — whether skills go in `workspace/.openclaw/skills/` or elsewhere; the implementation phase verifies against a fresh OpenClaw release.
- Whether `cron/jobs.json` accepts the schema fields above as-written, or needs minor adjustments — the implementation phase verifies against the running gateway and adjusts.
- Format of OpenClaw credentials (env-var-style? per-key files? something else?) — verified during implementation.
