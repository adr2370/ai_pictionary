# Pictionary Runner — Windows install

These are the manual steps you (the human) need to run on the Windows host to deploy `runner.py` as a long-lived background service. The code itself is already written and tested in this directory — these steps just wire it up to actually run at logon and survive reboots.

Plan reference: tasks 9–10 of `docs/superpowers/plans/2026-04-12-pictionary-biweekly-openclaw.md`.

---

## 1. Generate a strong token

In any terminal:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output. You'll paste it into:
- `C:/Users/adr23/.openclaw-runner/config.json` (this file, step 3)
- The OpenClaw credentials store as `runner.token` (Task 12 in the plan)

Both copies must match exactly.

## 2. Create the runner config directory

```bash
mkdir -p /c/Users/adr23/.openclaw-runner/logs
```

(Bash form. PowerShell equivalent: `New-Item -ItemType Directory -Path "C:\Users\adr23\.openclaw-runner\logs" -Force`.)

## 3. Write the real config

Create `C:/Users/adr23/.openclaw-runner/config.json` based on `runner/config.example.json`, replacing the token with the one from step 1:

```json
{
  "host": "127.0.0.1",
  "port": 18790,
  "token": "<paste-token-from-step-1>",
  "ai_pictionary_dir": "C:/Users/adr23/Projects/ai_pictionary",
  "main_py_args": [],
  "host_csv_dir": "C:/Users/adr23/Projects/ai_pictionary/bulk_upload_csvs",
  "openclaw_csv_dir": "/home/node/uploads",
  "log_dir": "C:/Users/adr23/.openclaw-runner/logs"
}
```

Forward slashes are fine on Windows for these paths — Python normalizes them.

## 4. Lock the file down

The token is a long-lived secret. In an elevated PowerShell:

```powershell
icacls "C:\Users\adr23\.openclaw-runner\config.json" /inheritance:r /grant:r "$env:USERNAME:(R)"
```

Expected output: `Successfully processed 1 files; Failed processing 0 files`.

## 5. Manual smoke test

Before installing the service, verify it actually runs:

```bash
cd /c/Users/adr23/Projects/ai_pictionary/runner
.venv/Scripts/python.exe -m runner.runner --config C:/Users/adr23/.openclaw-runner/config.json
```

Expected:
- uvicorn logs `Application startup complete.`
- Then `Uvicorn running on http://127.0.0.1:18790`

In a second terminal:
```bash
curl http://127.0.0.1:18790/health
```
Expected: `{"ok":true}`.

Stop the runner with Ctrl+C. **Do NOT hit `/run-pictionary`** during this smoke test — that fires the real `main.py` and starts a real ~hours-long generation run.

## 6. Create the launcher batch file

Create `C:/Users/adr23/.openclaw-runner/launch.bat`:

```bat
@echo off
cd /d C:\Users\adr23\Projects\ai_pictionary\runner
.venv\Scripts\pythonw.exe -m runner.runner --config C:\Users\adr23\.openclaw-runner\config.json
```

`pythonw.exe` is the no-console variant — it runs invisibly so you don't get a stray cmd window at logon.

## 7. Register a Task Scheduler entry

In an elevated PowerShell:

```powershell
$action = New-ScheduledTaskAction -Execute "C:\Users\adr23\.openclaw-runner\launch.bat"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask `
    -TaskName "OpenClawPictionaryRunner" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Limited
```

Expected: task registered, no errors. To inspect later: `Get-ScheduledTask -TaskName OpenClawPictionaryRunner`.

## 8. Start it now (without waiting for next logon)

```powershell
Start-ScheduledTask -TaskName "OpenClawPictionaryRunner"
```

## 9. Verify it's running

```bash
curl http://127.0.0.1:18790/health
```
Expected: `{"ok":true}`.

If you don't get that within 5 seconds:
- `Get-ScheduledTaskInfo -TaskName OpenClawPictionaryRunner` — check `LastTaskResult` (should be `0`)
- `Get-Process pythonw -ErrorAction SilentlyContinue` — should show a pythonw process
- Check logs in `C:/Users/adr23/.openclaw-runner/logs/` — though those only get written *during a run*, not at idle

## 10. Verify openclaw can reach it via host.docker.internal

```bash
MSYS_NO_PATHCONV=1 docker exec openclaw sh -c "wget -qO- http://host.docker.internal:18790/health"
```

Expected: `{"ok":true}`.

**If this fails** (most likely "host.docker.internal: bad address" or similar), the openclaw container doesn't have an `extra_hosts` entry. Add this to the `openclaw` service block in `/home/adr2370/openclaw/docker-compose.yml` *while you're already there for Task 11*:

```yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

Then `docker compose up -d openclaw` to recreate the container.

## Stopping or removing the runner

```powershell
Stop-ScheduledTask -TaskName "OpenClawPictionaryRunner"
Unregister-ScheduledTask -TaskName "OpenClawPictionaryRunner" -Confirm:$false
```

To kill an already-running pythonw process: `Get-Process pythonw | Stop-Process` (be careful — this kills *all* pythonw processes, not just the runner).
