# Pictionary Runner

A tiny FastAPI service that runs `python main.py` on demand, behind a token-authed HTTP endpoint, so the OpenClaw `pictionary-biweekly` skill can fire it.

## What it does

- Listens on `127.0.0.1:18790` (loopback only).
- Exposes one endpoint: `POST /run-pictionary` (token-authed).
- On call: snapshots `bulk_upload_csvs/`, runs `python main.py` in the `ai_pictionary` directory, blocks until it exits, then returns the two new CSVs (translated to openclaw-container paths).
- Refuses to run a second job in parallel (returns 409).
- Logs each run to a per-run file under `log_dir`.

## Spec / plan

- Spec: `../docs/superpowers/specs/2026-04-12-pictionary-biweekly-openclaw-design.md`
- Plan: `../docs/superpowers/plans/2026-04-12-pictionary-biweekly-openclaw.md`
- Skill format notes: `./openclaw-skill-format-notes.md`

## Deployment notes

**OpenClaw stack location:** `/home/adr2370/openclaw/` inside the WSL2 distro (Docker Desktop's WSL2 backend mounts this automatically).

- `docker-compose.yml` lives at `/home/adr2370/openclaw/docker-compose.yml`.
- The `openclaw` service block currently has two volume mounts (`./config:/home/node/.openclaw` and `./workspace:/home/node/.openclaw/workspace`).
- It does **not** have an `extra_hosts:` entry — Task 11 of the implementation plan adds both the new bind mount and `extra_hosts: ["host.docker.internal:host-gateway"]` so the skill can reach this runner via `http://host.docker.internal:18790`.
- The new bind mount uses the **WSL path** style: `/mnt/c/Users/adr23/Projects/ai_pictionary/bulk_upload_csvs:/home/node/uploads:ro` (NOT the Windows `C:/Users/...` style — the compose file is parsed inside WSL so it expects WSL paths).

## Install

See `install_windows.md` (created by Task 9 of the plan).
