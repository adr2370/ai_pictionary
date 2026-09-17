# Pictionary Biweekly OpenClaw Automation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Alex's biweekly Pictionary → Social Champ pipeline run unattended, with OpenClaw's `main` agent as the orchestrator, fired by OpenClaw cron, calling a tiny host-side HTTP runner that executes `main.py`.

**Architecture:** OpenClaw cron fires a procedural skill twice a month. Skill calls `host.docker.internal:18790` (the new `runner.py` service on the Windows host) to run `main.py` and get back the two CSVs. Skill then drives the `chromium` container via OpenClaw's browser plugin to log into Social Champ, reconnect every account, and bulk-upload both CSVs. Telegram pings on success or failure.

**Tech Stack:** Python 3.11+ (FastAPI + uvicorn for the runner, pytest + httpx for tests), Docker Desktop with WSL2 backend, OpenClaw (Node.js, runs in container), Chromium (separate container, CDP-driven), OpenClaw's built-in cron, Telegram channel.

**Spec:** `docs/superpowers/specs/2026-04-12-pictionary-biweekly-openclaw-design.md`

---

## File structure

This plan creates files in two locations:

**Inside the `ai_pictionary` repo (Windows host, this directory):**

```
ai_pictionary/
  runner/
    runner.py              # FastAPI service — single file, ~150 lines
    config.py              # Config loader (Pydantic BaseSettings)
    paths.py               # Host↔container path translation
    runs.py                # Subprocess runner + concurrency lock
    requirements.txt       # fastapi, uvicorn, pydantic-settings, httpx (dev)
    config.example.json    # Template for runner config
    install_windows.md     # Manual install steps (Task Scheduler at logon)
    tests/
      __init__.py
      conftest.py
      test_paths.py
      test_runs.py
      test_api.py
    README.md
  docs/superpowers/plans/
    2026-04-12-pictionary-biweekly-openclaw.md   ← THIS FILE
```

**Inside the OpenClaw config volume (`/home/adr2370/openclaw/...` in WSL):**

```
config/
  cron/jobs.json           # ADD a job entry
  credentials/             # ADD socialchamp.email, socialchamp.password, runner.token
workspace/
  .openclaw/skills/pictionary-biweekly/
    SKILL.md
    pictionary-config.json
    README.md
```

Plus a one-line edit to whatever docker-compose file brings up the `openclaw` container (Task 2 finds it).

---

## Conventions

- All `runner/` work is TDD: failing test first, then minimal code, then verify, then commit. The runner is the only piece with non-trivial logic worth testing — the rest is config files and one-time manual operations.
- Tests use `pytest` and `httpx.AsyncClient` against a FastAPI `TestClient`.
- Python 3.11+ assumed (uses modern type hints).
- Path strings: forward slashes everywhere in code; use `pathlib.Path` for any filesystem operation.
- Commits are atomic per task. Commit messages use `feat:`/`test:`/`docs:`/`chore:` prefixes.
- The `runner/` virtualenv is independent from `ai_pictionary`'s other Python deps. Use `py -3.11 -m venv runner/.venv`.

---

## Task 1: Discover the OpenClaw skill format

Before writing `SKILL.md` we need to know what the schema actually looks like. There may be frontmatter, required fields, a manifest file, etc.

**Files:**
- Read-only investigation. No files written yet.

- [ ] **Step 1: Look for any existing skills in the running container**

Run:
```bash
MSYS_NO_PATHCONV=1 docker exec openclaw sh -c "find /home/node -name 'SKILL.md' -o -name 'skill.json' -o -name 'skill.yaml' 2>/dev/null | head -20"
```
Expected: paths to one or more existing skills, OR no output if none exist yet.

- [ ] **Step 2: Read one existing skill in full as a template**

If Step 1 found any, run:
```bash
MSYS_NO_PATHCONV=1 docker exec openclaw sh -c "cat <path-from-step-1>"
```
Read the structure carefully — note frontmatter format, required sections, how procedures are written, how tools are referenced.

- [ ] **Step 3: If no existing skills, fetch the official skill template**

Open `https://github.com/openclaw/skills` in a browser and read 1–2 example skills (e.g., `skills/thesethrose/agent-browser/SKILL.md`). Note the frontmatter and section conventions.

- [ ] **Step 4: Write a one-page note**

Create `runner/openclaw-skill-format-notes.md` with:
- Required frontmatter fields (name, description, etc.)
- Required body sections
- How to reference credentials by name
- How to invoke browser tool actions
- How to send Telegram messages
- Any "skill discovery" path conventions (where in the workspace skills must live)

This note is consumed by Task 16 (writing the actual SKILL.md). Don't proceed until you understand the format.

- [ ] **Step 5: Commit**

```bash
git add runner/openclaw-skill-format-notes.md
git commit -m "docs: capture openclaw skill format for pictionary skill"
```

---

## Task 2: Discover the openclaw docker-compose location

We need to find the file that brought up the `openclaw` container so we can add the bind mount in Task 12.

- [ ] **Step 1: Inspect the openclaw container's compose labels**

Run:
```bash
docker inspect openclaw --format '{{ index .Config.Labels "com.docker.compose.project.config_files" }}'
```
Expected: a path like `/home/adr2370/openclaw/docker-compose.yml` (or similar).

- [ ] **Step 2: Verify the file exists and read it**

If the path is inside WSL, access it from Windows via `\\wsl$\<distro>\home\adr2370\openclaw\docker-compose.yml` or read it from inside any WSL distro. Either way:
```bash
MSYS_NO_PATHCONV=1 wsl cat <path-from-step-1>
```
Expected: a YAML file with services including `openclaw`, `chromium`, `chromium-proxy`, `ollama`, `hass-mcp`, `ha-proxy`.

- [ ] **Step 3: Identify the openclaw service block**

Find the lines that define the `openclaw` service. Note the existing `volumes:` list — this is what Task 12 will append to.

- [ ] **Step 4: Write the path into the runner README**

Open `runner/README.md` (create if it doesn't exist yet) and add a "Deployment notes" section with the compose file path and the `openclaw` service location within it. This anchors Task 12.

- [ ] **Step 5: Commit**

```bash
git add runner/README.md
git commit -m "docs: record openclaw docker-compose location for runner deploy"
```

---

## Task 3: Scaffold the runner project

**Files:**
- Create: `runner/requirements.txt`
- Create: `runner/config.example.json`
- Create: `runner/tests/__init__.py`
- Create: `runner/tests/conftest.py`
- Create: `runner/.gitignore`

- [ ] **Step 1: Write `runner/requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
pydantic==2.9.2
pydantic-settings==2.6.0
httpx==0.27.2
pytest==8.3.3
pytest-asyncio==0.24.0
```

- [ ] **Step 2: Create the runner virtualenv and install deps**

Run:
```bash
cd runner && py -3.11 -m venv .venv && .venv/Scripts/pip install -r requirements.txt
```
Expected: `Successfully installed ...` ending with no errors.

- [ ] **Step 3: Write `runner/config.example.json`**

```json
{
  "host": "127.0.0.1",
  "port": 18790,
  "token": "REPLACE_WITH_LONG_RANDOM_STRING",
  "ai_pictionary_dir": "C:/Users/adr23/Projects/ai_pictionary",
  "main_py_args": [],
  "host_csv_dir": "C:/Users/adr23/Projects/ai_pictionary/bulk_upload_csvs",
  "openclaw_csv_dir": "/home/node/uploads",
  "log_dir": "C:/Users/adr23/.openclaw-runner/logs"
}
```

- [ ] **Step 4: Write `runner/.gitignore`**

```
.venv/
__pycache__/
*.pyc
config.json
logs/
.pytest_cache/
```

- [ ] **Step 5: Write `runner/tests/__init__.py`** — empty file.

- [ ] **Step 6: Write `runner/tests/conftest.py`**

```python
import json
from pathlib import Path

import pytest


@pytest.fixture
def tmp_config(tmp_path):
    """Returns a Path to a freshly-written runner config in tmp_path."""
    cfg = {
        "host": "127.0.0.1",
        "port": 0,
        "token": "test-token-do-not-use-in-prod",
        "ai_pictionary_dir": str(tmp_path / "ai_pictionary"),
        "main_py_args": [],
        "host_csv_dir": str(tmp_path / "ai_pictionary" / "bulk_upload_csvs"),
        "openclaw_csv_dir": "/home/node/uploads",
        "log_dir": str(tmp_path / "logs"),
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg))
    Path(cfg["ai_pictionary_dir"]).mkdir(parents=True, exist_ok=True)
    Path(cfg["host_csv_dir"]).mkdir(parents=True, exist_ok=True)
    Path(cfg["log_dir"]).mkdir(parents=True, exist_ok=True)
    return cfg_path
```

- [ ] **Step 7: Verify pytest discovers the tests directory**

Run:
```bash
cd runner && .venv/Scripts/pytest --collect-only
```
Expected: `0 tests collected` (no failures, no errors — just an empty test session).

- [ ] **Step 8: Commit**

```bash
git add runner/requirements.txt runner/config.example.json runner/.gitignore runner/tests/__init__.py runner/tests/conftest.py
git commit -m "feat: scaffold runner project (deps, config template, test harness)"
```

---

## Task 4: Config loader

**Files:**
- Create: `runner/config.py`
- Create: `runner/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`runner/tests/test_config.py`:
```python
import json
from pathlib import Path

import pytest

from runner.config import RunnerConfig, load_config


def test_load_config_from_file(tmp_config):
    cfg = load_config(tmp_config)
    assert cfg.token == "test-token-do-not-use-in-prod"
    assert cfg.port == 0
    assert cfg.openclaw_csv_dir == "/home/node/uploads"


def test_load_config_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "does-not-exist.json")


def test_token_must_not_be_placeholder(tmp_path):
    bad = {
        "host": "127.0.0.1",
        "port": 18790,
        "token": "REPLACE_WITH_LONG_RANDOM_STRING",
        "ai_pictionary_dir": str(tmp_path),
        "main_py_args": [],
        "host_csv_dir": str(tmp_path),
        "openclaw_csv_dir": "/home/node/uploads",
        "log_dir": str(tmp_path),
    }
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="placeholder"):
        load_config(p)
```

- [ ] **Step 2: Run test, verify it fails**

Run:
```bash
cd runner && .venv/Scripts/pytest tests/test_config.py -v
```
Expected: `ImportError` or `ModuleNotFoundError: runner.config`.

- [ ] **Step 3: Write `runner/config.py`**

```python
import json
from pathlib import Path

from pydantic import BaseModel, field_validator


class RunnerConfig(BaseModel):
    host: str
    port: int
    token: str
    ai_pictionary_dir: str
    main_py_args: list[str]
    host_csv_dir: str
    openclaw_csv_dir: str
    log_dir: str

    @field_validator("token")
    @classmethod
    def reject_placeholder(cls, v: str) -> str:
        if v == "REPLACE_WITH_LONG_RANDOM_STRING" or len(v) < 16:
            raise ValueError("token is a placeholder or too short — generate a real one")
        return v


def load_config(path: Path) -> RunnerConfig:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"runner config not found: {path}")
    return RunnerConfig.model_validate_json(path.read_text())
```

- [ ] **Step 4: Add `runner/__init__.py`** — empty file, so `runner.config` is importable.

- [ ] **Step 5: Run tests, verify pass**

Run:
```bash
cd runner && .venv/Scripts/pytest tests/test_config.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add runner/config.py runner/__init__.py runner/tests/test_config.py
git commit -m "feat(runner): config loader with token validation"
```

---

## Task 5: Path translation host ↔ openclaw container

The runner returns CSV paths to the OpenClaw skill, but the skill sees files at `/home/node/uploads/...` (the bind mount destination), not the host path. This module translates.

**Files:**
- Create: `runner/paths.py`
- Create: `runner/tests/test_paths.py`

- [ ] **Step 1: Write the failing test**

`runner/tests/test_paths.py`:
```python
from runner.paths import host_to_openclaw


def test_translates_host_path_to_container_path():
    result = host_to_openclaw(
        host_path="C:/Users/adr23/Projects/ai_pictionary/bulk_upload_csvs/ai_pictionary_bulk_upload_SHORTS_20260426_020000.csv",
        host_root="C:/Users/adr23/Projects/ai_pictionary/bulk_upload_csvs",
        container_root="/home/node/uploads",
    )
    assert result == "/home/node/uploads/ai_pictionary_bulk_upload_SHORTS_20260426_020000.csv"


def test_handles_backslash_paths():
    result = host_to_openclaw(
        host_path=r"C:\Users\adr23\Projects\ai_pictionary\bulk_upload_csvs\foo.csv",
        host_root=r"C:\Users\adr23\Projects\ai_pictionary\bulk_upload_csvs",
        container_root="/home/node/uploads",
    )
    assert result == "/home/node/uploads/foo.csv"


def test_raises_when_path_outside_host_root():
    import pytest
    with pytest.raises(ValueError, match="not under host_root"):
        host_to_openclaw(
            host_path="C:/somewhere/else/file.csv",
            host_root="C:/Users/adr23/Projects/ai_pictionary/bulk_upload_csvs",
            container_root="/home/node/uploads",
        )
```

- [ ] **Step 2: Run test, verify it fails**

Run:
```bash
cd runner && .venv/Scripts/pytest tests/test_paths.py -v
```
Expected: `ModuleNotFoundError: runner.paths`.

- [ ] **Step 3: Write `runner/paths.py`**

```python
from pathlib import PurePosixPath, PureWindowsPath


def host_to_openclaw(host_path: str, host_root: str, container_root: str) -> str:
    """Translate a host path under host_root to its mirror under container_root.

    Accepts both forward-slash and backslash host paths; returns POSIX form.
    Raises ValueError if host_path is not under host_root.
    """
    host_path_p = PureWindowsPath(host_path)
    host_root_p = PureWindowsPath(host_root)

    try:
        rel = host_path_p.relative_to(host_root_p)
    except ValueError as e:
        raise ValueError(
            f"host_path={host_path!r} is not under host_root={host_root!r}"
        ) from e

    rel_posix = PurePosixPath(*rel.parts)
    return str(PurePosixPath(container_root) / rel_posix)
```

- [ ] **Step 4: Run tests, verify pass**

Run:
```bash
cd runner && .venv/Scripts/pytest tests/test_paths.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add runner/paths.py runner/tests/test_paths.py
git commit -m "feat(runner): host-to-openclaw path translation"
```

---

## Task 6: CSV discovery — find the latest pair of CSVs

After `main.py` runs, we need to identify which two CSVs are "the new ones." Strategy: snapshot the directory listing before the run; take the new files after the run; among new files pick the highest-mtime SHORTS and the highest-mtime VIDEO.

**Files:**
- Create: `runner/csvs.py`
- Create: `runner/tests/test_csvs.py`

- [ ] **Step 1: Write the failing test**

`runner/tests/test_csvs.py`:
```python
import time
from pathlib import Path

import pytest

from runner.csvs import find_new_pair, snapshot


def test_snapshot_returns_set_of_existing_files(tmp_path):
    (tmp_path / "old1.csv").write_text("x")
    (tmp_path / "old2.csv").write_text("x")
    snap = snapshot(tmp_path)
    assert {p.name for p in snap} == {"old1.csv", "old2.csv"}


def test_find_new_pair_picks_shorts_and_video(tmp_path):
    (tmp_path / "ai_pictionary_bulk_upload_SHORTS_20260101_000000.csv").write_text("x")
    (tmp_path / "ai_pictionary_bulk_upload_VIDEO_20260101_000000.csv").write_text("x")
    before = snapshot(tmp_path)

    time.sleep(0.05)
    (tmp_path / "ai_pictionary_bulk_upload_SHORTS_20260426_020000.csv").write_text("x")
    (tmp_path / "ai_pictionary_bulk_upload_VIDEO_20260426_020000.csv").write_text("x")

    shorts, video = find_new_pair(tmp_path, before=before)
    assert shorts.name == "ai_pictionary_bulk_upload_SHORTS_20260426_020000.csv"
    assert video.name == "ai_pictionary_bulk_upload_VIDEO_20260426_020000.csv"


def test_find_new_pair_raises_if_missing_one_side(tmp_path):
    before = snapshot(tmp_path)
    (tmp_path / "ai_pictionary_bulk_upload_SHORTS_20260426_020000.csv").write_text("x")
    with pytest.raises(FileNotFoundError, match="VIDEO"):
        find_new_pair(tmp_path, before=before)
```

- [ ] **Step 2: Run test, verify it fails**

Run:
```bash
cd runner && .venv/Scripts/pytest tests/test_csvs.py -v
```
Expected: `ModuleNotFoundError: runner.csvs`.

- [ ] **Step 3: Write `runner/csvs.py`**

```python
from pathlib import Path


def snapshot(directory: Path) -> set[Path]:
    """Return the set of files currently in `directory` (non-recursive)."""
    directory = Path(directory)
    return {p for p in directory.iterdir() if p.is_file()}


def find_new_pair(directory: Path, before: set[Path]) -> tuple[Path, Path]:
    """Find the newest SHORTS and VIDEO CSVs that did not exist in `before`.

    Returns (shorts_path, video_path).
    Raises FileNotFoundError if either side is missing.
    """
    directory = Path(directory)
    after = snapshot(directory)
    new_files = after - before

    shorts = sorted(
        (p for p in new_files if "_SHORTS_" in p.name and p.suffix == ".csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    video = sorted(
        (p for p in new_files if "_VIDEO_" in p.name and p.suffix == ".csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not shorts:
        raise FileNotFoundError("No new SHORTS CSV found after main.py run")
    if not video:
        raise FileNotFoundError("No new VIDEO CSV found after main.py run")

    return shorts[0], video[0]
```

- [ ] **Step 4: Run tests, verify pass**

Run:
```bash
cd runner && .venv/Scripts/pytest tests/test_csvs.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add runner/csvs.py runner/tests/test_csvs.py
git commit -m "feat(runner): discover new SHORTS+VIDEO CSV pair after a run"
```

---

## Task 7: Subprocess runner with concurrency lock

This module owns the `python main.py` subprocess: launch it, log to a file, return exit code, refuse parallel runs.

**Files:**
- Create: `runner/runs.py`
- Create: `runner/tests/test_runs.py`

- [ ] **Step 1: Write the failing test**

`runner/tests/test_runs.py`:
```python
import sys
from pathlib import Path

import pytest

from runner.runs import RunInProgressError, RunResult, Runner


@pytest.fixture
def runner_for_test(tmp_path):
    """A Runner that 'runs main.py' as a tiny inline Python script writing two CSVs."""
    workdir = tmp_path / "ai_pictionary"
    workdir.mkdir()
    csv_dir = workdir / "bulk_upload_csvs"
    csv_dir.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    fake_main = workdir / "main.py"
    fake_main.write_text(
        "import sys, time\n"
        "open(r'" + str(csv_dir).replace("\\", "/") +
        "/ai_pictionary_bulk_upload_SHORTS_20260426_020000.csv', 'w').write('x')\n"
        "open(r'" + str(csv_dir).replace("\\", "/") +
        "/ai_pictionary_bulk_upload_VIDEO_20260426_020000.csv', 'w').write('x')\n"
        "print('done', flush=True)\n"
        "sys.exit(0)\n"
    )
    return Runner(
        ai_pictionary_dir=workdir,
        host_csv_dir=csv_dir,
        log_dir=log_dir,
        python_executable=sys.executable,
        main_py_args=[],
    )


def test_run_executes_main_and_returns_csv_paths(runner_for_test):
    result: RunResult = runner_for_test.run()
    assert result.exit_code == 0
    assert result.shorts_csv.name.startswith("ai_pictionary_bulk_upload_SHORTS_")
    assert result.video_csv.name.startswith("ai_pictionary_bulk_upload_VIDEO_")
    assert result.log_path.exists()
    assert "done" in result.log_path.read_text()


def test_concurrent_run_raises(runner_for_test, monkeypatch):
    runner_for_test._lock.acquire()
    try:
        with pytest.raises(RunInProgressError):
            runner_for_test.run()
    finally:
        runner_for_test._lock.release()


def test_run_failure_returns_nonzero(tmp_path):
    workdir = tmp_path / "ai_pictionary"
    workdir.mkdir()
    (workdir / "bulk_upload_csvs").mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    fake_main = workdir / "main.py"
    fake_main.write_text("import sys; sys.exit(7)\n")

    runner = Runner(
        ai_pictionary_dir=workdir,
        host_csv_dir=workdir / "bulk_upload_csvs",
        log_dir=log_dir,
        python_executable=sys.executable,
        main_py_args=[],
    )
    result = runner.run()
    assert result.exit_code == 7
    assert result.shorts_csv is None
    assert result.video_csv is None
```

- [ ] **Step 2: Run test, verify it fails**

Run:
```bash
cd runner && .venv/Scripts/pytest tests/test_runs.py -v
```
Expected: `ModuleNotFoundError: runner.runs`.

- [ ] **Step 3: Write `runner/runs.py`**

```python
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from runner.csvs import find_new_pair, snapshot


class RunInProgressError(RuntimeError):
    pass


@dataclass
class RunResult:
    exit_code: int
    shorts_csv: Optional[Path]
    video_csv: Optional[Path]
    log_path: Path
    duration_seconds: float


class Runner:
    def __init__(
        self,
        ai_pictionary_dir: Path,
        host_csv_dir: Path,
        log_dir: Path,
        python_executable: str,
        main_py_args: list[str],
    ):
        self.ai_pictionary_dir = Path(ai_pictionary_dir)
        self.host_csv_dir = Path(host_csv_dir)
        self.log_dir = Path(log_dir)
        self.python_executable = python_executable
        self.main_py_args = list(main_py_args)
        self._lock = threading.Lock()

    def run(self) -> RunResult:
        if not self._lock.acquire(blocking=False):
            raise RunInProgressError("a pictionary run is already in progress")

        try:
            ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
            log_path = self.log_dir / f"{ts}.log"
            self.log_dir.mkdir(parents=True, exist_ok=True)

            before = snapshot(self.host_csv_dir)
            start = datetime.now()

            cmd = [self.python_executable, "main.py", *self.main_py_args]
            with log_path.open("wb") as log_file:
                proc = subprocess.run(
                    cmd,
                    cwd=str(self.ai_pictionary_dir),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )

            duration = (datetime.now() - start).total_seconds()

            if proc.returncode != 0:
                return RunResult(
                    exit_code=proc.returncode,
                    shorts_csv=None,
                    video_csv=None,
                    log_path=log_path,
                    duration_seconds=duration,
                )

            shorts, video = find_new_pair(self.host_csv_dir, before=before)
            return RunResult(
                exit_code=0,
                shorts_csv=shorts,
                video_csv=video,
                log_path=log_path,
                duration_seconds=duration,
            )
        finally:
            self._lock.release()
```

- [ ] **Step 4: Run tests, verify pass**

Run:
```bash
cd runner && .venv/Scripts/pytest tests/test_runs.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add runner/runs.py runner/tests/test_runs.py
git commit -m "feat(runner): subprocess execution with concurrency lock and logging"
```

---

## Task 8: FastAPI app

**Files:**
- Create: `runner/runner.py`
- Create: `runner/tests/test_api.py`

- [ ] **Step 1: Write the failing test**

`runner/tests/test_api.py`:
```python
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from runner.runner import build_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    workdir = tmp_path / "ai_pictionary"
    workdir.mkdir()
    csv_dir = workdir / "bulk_upload_csvs"
    csv_dir.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    fake_main = workdir / "main.py"
    fake_main.write_text(
        "import sys\n"
        "open(r'" + str(csv_dir).replace("\\", "/") +
        "/ai_pictionary_bulk_upload_SHORTS_20260426_020000.csv', 'w').write('x')\n"
        "open(r'" + str(csv_dir).replace("\\", "/") +
        "/ai_pictionary_bulk_upload_VIDEO_20260426_020000.csv', 'w').write('x')\n"
        "sys.exit(0)\n"
    )

    cfg = {
        "host": "127.0.0.1",
        "port": 0,
        "token": "test-token-1234567890abcdef",
        "ai_pictionary_dir": str(workdir),
        "main_py_args": [],
        "host_csv_dir": str(csv_dir),
        "openclaw_csv_dir": "/home/node/uploads",
        "log_dir": str(log_dir),
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg))

    app = build_app(cfg_path, python_executable=sys.executable)
    return TestClient(app)


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_run_requires_auth(client):
    r = client.post("/run-pictionary")
    assert r.status_code == 401


def test_run_rejects_wrong_token(client):
    r = client.post("/run-pictionary", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_run_succeeds_with_correct_token(client):
    r = client.post(
        "/run-pictionary",
        headers={"Authorization": "Bearer test-token-1234567890abcdef"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["exit_code"] == 0
    assert body["shorts_csv_path"] == "/home/node/uploads/ai_pictionary_bulk_upload_SHORTS_20260426_020000.csv"
    assert body["video_csv_path"] == "/home/node/uploads/ai_pictionary_bulk_upload_VIDEO_20260426_020000.csv"
    assert "log_path" in body
    assert body["duration_seconds"] >= 0
```

- [ ] **Step 2: Run test, verify it fails**

Run:
```bash
cd runner && .venv/Scripts/pytest tests/test_api.py -v
```
Expected: `ImportError` for `runner.runner.build_app`.

- [ ] **Step 3: Write `runner/runner.py`**

```python
import sys
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, status

from runner.config import RunnerConfig, load_config
from runner.paths import host_to_openclaw
from runner.runs import RunInProgressError, Runner


def build_app(config_path: Path, python_executable: str = sys.executable) -> FastAPI:
    cfg: RunnerConfig = load_config(config_path)

    runner = Runner(
        ai_pictionary_dir=Path(cfg.ai_pictionary_dir),
        host_csv_dir=Path(cfg.host_csv_dir),
        log_dir=Path(cfg.log_dir),
        python_executable=python_executable,
        main_py_args=cfg.main_py_args,
    )

    app = FastAPI(title="Pictionary Runner", version="1.0")

    def require_token(authorization: str | None = Header(default=None)) -> None:
        expected = f"Bearer {cfg.token}"
        if authorization != expected:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid or missing token",
            )

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/run-pictionary")
    def run_pictionary(_: None = Depends(require_token)) -> dict:
        try:
            result = runner.run()
        except RunInProgressError as e:
            raise HTTPException(status_code=409, detail=str(e))

        if result.exit_code != 0:
            tail = result.log_path.read_text(errors="replace").splitlines()[-50:]
            return {
                "ok": False,
                "exit_code": result.exit_code,
                "log_path": str(result.log_path),
                "log_tail": "\n".join(tail),
                "duration_seconds": result.duration_seconds,
            }

        shorts_container = host_to_openclaw(
            host_path=str(result.shorts_csv),
            host_root=cfg.host_csv_dir,
            container_root=cfg.openclaw_csv_dir,
        )
        video_container = host_to_openclaw(
            host_path=str(result.video_csv),
            host_root=cfg.host_csv_dir,
            container_root=cfg.openclaw_csv_dir,
        )

        return {
            "ok": True,
            "exit_code": 0,
            "shorts_csv_path": shorts_container,
            "video_csv_path": video_container,
            "log_path": str(result.log_path),
            "duration_seconds": result.duration_seconds,
        }

    return app


def main() -> None:
    import argparse
    import uvicorn

    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True, type=Path)
    args = p.parse_args()

    cfg = load_config(args.config)
    app = build_app(args.config)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests, verify pass**

Run:
```bash
cd runner && .venv/Scripts/pytest tests/test_api.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Run the full test suite**

Run:
```bash
cd runner && .venv/Scripts/pytest -v
```
Expected: all tests pass (config + paths + csvs + runs + api).

- [ ] **Step 6: Commit**

```bash
git add runner/runner.py runner/tests/test_api.py
git commit -m "feat(runner): FastAPI app with /health and /run-pictionary endpoints"
```

---

## Task 9: Generate runner.token and write the real config

**Files:**
- Create: `C:/Users/adr23/.openclaw-runner/config.json` (outside the repo, locked-down location)
- Create: `runner/install_windows.md`

- [ ] **Step 1: Generate a strong token**

Run:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Copy the output. Save it somewhere temporary; you'll paste it into both the runner config (this task) and the OpenClaw credentials store (Task 15).

- [ ] **Step 2: Create the runner config directory**

Run:
```bash
mkdir -p /c/Users/adr23/.openclaw-runner/logs
```

- [ ] **Step 3: Write the real config**

Create `C:/Users/adr23/.openclaw-runner/config.json` with the actual token from Step 1:

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

- [ ] **Step 4: Lock the file down (Windows ACL)**

Run in PowerShell:
```powershell
icacls "C:\Users\adr23\.openclaw-runner\config.json" /inheritance:r /grant:r "$env:USERNAME:(R)"
```
Expected: `Successfully processed 1 files; Failed processing 0 files`.

- [ ] **Step 5: Smoke-test the runner manually**

Run from a terminal:
```bash
cd /c/Users/adr23/Projects/ai_pictionary/runner && .venv/Scripts/python -m runner.runner --config C:/Users/adr23/.openclaw-runner/config.json
```
Expected: uvicorn starts, logs "Application startup complete." and "Uvicorn running on http://127.0.0.1:18790".

In a second terminal:
```bash
curl http://127.0.0.1:18790/health
```
Expected: `{"ok":true}`.

Stop the runner with Ctrl+C (do NOT hit /run-pictionary yet — that fires real `main.py`).

- [ ] **Step 6: Write `runner/install_windows.md`** with these manual steps captured for future reference, then commit.

```bash
git add runner/install_windows.md
git commit -m "docs(runner): manual install + smoke test instructions"
```

---

## Task 10: Install runner as a Windows startup service

We use Windows Task Scheduler "at logon" with a hidden window. NSSM is overkill if the user isn't already on it.

- [ ] **Step 1: Create a launcher batch file**

Create `C:/Users/adr23/.openclaw-runner/launch.bat`:
```bat
@echo off
cd /d C:\Users\adr23\Projects\ai_pictionary\runner
.venv\Scripts\pythonw.exe -m runner.runner --config C:\Users\adr23\.openclaw-runner\config.json
```

- [ ] **Step 2: Register a Task Scheduler entry**

Run in elevated PowerShell:
```powershell
$action = New-ScheduledTaskAction -Execute "C:\Users\adr23\.openclaw-runner\launch.bat"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "OpenClawPictionaryRunner" -Action $action -Trigger $trigger -Settings $settings -RunLevel Limited
```
Expected: task registered, no errors.

- [ ] **Step 3: Start the task immediately**

```powershell
Start-ScheduledTask -TaskName "OpenClawPictionaryRunner"
```

- [ ] **Step 4: Verify it's running**

```bash
curl http://127.0.0.1:18790/health
```
Expected: `{"ok":true}`.

- [ ] **Step 5: Verify openclaw can reach it via host.docker.internal**

Run:
```bash
MSYS_NO_PATHCONV=1 docker exec openclaw sh -c "wget -qO- http://host.docker.internal:18790/health"
```
Expected: `{"ok":true}`. **If this fails**, the openclaw container isn't configured with `extra_hosts: ["host.docker.internal:host-gateway"]` — fix this in the docker-compose now (it's a one-line addition under the `openclaw` service) before continuing.

- [ ] **Step 6: Append the install steps to `runner/install_windows.md` and commit**

```bash
git add runner/install_windows.md
git commit -m "docs(runner): Windows Task Scheduler install steps"
```

---

## Task 11: Add the bind mount to the openclaw container

This is the file-visibility step from the spec. Without this, the OpenClaw browser plugin cannot read the CSVs.

- [ ] **Step 1: Open the docker-compose file** found in Task 2.

- [ ] **Step 2: Locate the `openclaw` service block.** It already has a `volumes:` section with two entries (workspace and config bind mounts).

- [ ] **Step 3: Add a third entry**

Append under `openclaw.volumes:`:
```yaml
      - C:/Users/adr23/Projects/ai_pictionary/bulk_upload_csvs:/home/node/uploads:ro
```
(Adjust path quoting/escaping if compose syntax demands it. If compose runs from inside WSL, use `/mnt/c/Users/adr23/Projects/ai_pictionary/bulk_upload_csvs` instead.)

- [ ] **Step 4: Restart only the openclaw container**

Run from the directory containing the compose file:
```bash
docker compose up -d openclaw
```
Expected: `Recreating openclaw ... done`.

- [ ] **Step 5: Verify the mount is visible from inside openclaw**

```bash
MSYS_NO_PATHCONV=1 docker exec openclaw sh -c "ls /home/node/uploads/ | head -5"
```
Expected: a list of `ai_pictionary_bulk_upload_*.csv` files.

- [ ] **Step 6: Verify it's read-only**

```bash
MSYS_NO_PATHCONV=1 docker exec openclaw sh -c "touch /home/node/uploads/test 2>&1"
```
Expected: `touch: /home/node/uploads/test: Read-only file system`.

(No commit — this task only modifies a file outside the `ai_pictionary` repo.)

---

## Task 12: Add credentials to OpenClaw

- [ ] **Step 1: Open the OpenClaw Control UI** at `http://localhost:18789` in a browser. Authenticate with the gateway token from `openclaw.json` if prompted.

- [ ] **Step 2: Navigate to Credentials** (or whatever the equivalent section is — the UI may call it "Secrets" or "Vault").

- [ ] **Step 3: Add three credentials**

| Name | Value |
|---|---|
| `socialchamp.email` | (your Social Champ login email) |
| `socialchamp.password` | (your Social Champ password) |
| `runner.token` | (the same token saved in `C:/Users/adr23/.openclaw-runner/config.json`) |

- [ ] **Step 4: Verify they appear in the credentials list.** No commit (lives outside repo).

---

## Task 13: Write the OpenClaw skill

This is the procedural guide the agent reads when the cron fires. Format depends on what Task 1 discovered.

**Files (in OpenClaw workspace, NOT in this repo):**
- Create: `/home/adr2370/openclaw/workspace/.openclaw/skills/pictionary-biweekly/SKILL.md`
- Create: `/home/adr2370/openclaw/workspace/.openclaw/skills/pictionary-biweekly/pictionary-config.json`
- Create: `/home/adr2370/openclaw/workspace/.openclaw/skills/pictionary-biweekly/README.md`

(The exact directory under the workspace may differ — Task 1 will have established the correct skills path. Adjust accordingly.)

- [ ] **Step 1: Create the skill directory**

```bash
MSYS_NO_PATHCONV=1 docker exec openclaw sh -c "mkdir -p /home/node/.openclaw/workspace/.openclaw/skills/pictionary-biweekly"
```

- [ ] **Step 2: Write `SKILL.md`**

Use the frontmatter format you captured in Task 1. The body should be:

```markdown
---
name: pictionary-biweekly
description: Generate the biweekly Pictionary batch via the host runner, then upload both CSVs to Social Champ and reconnect every connected social account.
---

# Pictionary Biweekly

You are running the biweekly Pictionary content pipeline. This is fully automated — no human supervision. If anything is unclear or fails, abort and report via Telegram. Do not improvise outside the steps below.

## Inputs you can rely on

- Credentials: `socialchamp.email`, `socialchamp.password`, `runner.token` (in OpenClaw credentials store)
- Config file: `./pictionary-config.json` (sibling to this SKILL.md)
- Browser tool: openclaw-managed Chromium (use it for any web navigation)
- Telegram channel: send messages to user `@adr2370`

## Step 0: Preflight

Check for `failed.flag` in the workspace root. If present:
1. Read its contents.
2. Telegram-DM @adr2370: `❌ Pictionary biweekly cron fired but failed.flag is set from a previous run. Refusing to fire. Contents: <contents>. Clear the flag manually when ready.`
3. Stop here. Do nothing else.

## Step 1: Run the generator

POST to `http://host.docker.internal:18790/run-pictionary` with `Authorization: Bearer <runner.token>`. This call may take HOURS — do not time out client-side.

On success the response looks like:
```json
{
  "ok": true,
  "exit_code": 0,
  "shorts_csv_path": "/home/node/uploads/ai_pictionary_bulk_upload_SHORTS_<ts>.csv",
  "video_csv_path":  "/home/node/uploads/ai_pictionary_bulk_upload_VIDEO_<ts>.csv",
  "log_path": "...",
  "duration_seconds": NNNN
}
```

On failure it returns `{"ok": false, ...}` or a non-200. In either failure case, GO TO "Failure handling" below.

Save `shorts_csv_path` and `video_csv_path` for later steps.

## Step 2: Open Social Champ and log in

1. Browser-tool: navigate to `https://socialchamp.com/login` (or the current login URL).
2. If you land on the dashboard already (saved session), skip to Step 3.
3. Otherwise: type `socialchamp.email` into the email field, `socialchamp.password` into the password field, click Sign In.
4. Wait for the dashboard to load. Take a screenshot.

## Step 3: Reconnect every connected account

1. Navigate to the Social Accounts page (look for "Social Accounts" or "Connected Accounts" in the sidebar).
2. For each connected account in the list:
   - Click the account's "Reconnect" button (or "Refresh", "Reauthorize" — whatever this provider calls it).
   - An OAuth popup opens.
   - Click through it: "Continue as Alex" → "Authorize" / "Allow".
   - Wait for the popup to close and the success indicator to appear.
   - Move to the next account.
3. Do NOT skip accounts that look like they don't need reconnecting. Always do all of them.

## Step 4: Bulk upload SHORTS

1. Read `pictionary-config.json`. Extract `shorts_target_accounts`.
2. Navigate to Bulk Upload (in the Publish or Content menu).
3. Select the accounts listed in `shorts_target_accounts`.
4. Drag/upload the file at `shorts_csv_path` into the upload area. (Use the browser tool's file-upload action with that path — it's accessible via the openclaw bind mount.)
5. Wait for the parse-success indicator showing N posts detected.
6. Click "Schedule" / "Submit" / "Import".
7. Wait for confirmation. Take a screenshot.

## Step 5: Bulk upload VIDEO

Same as Step 4 but with `video_target_accounts` and `video_csv_path`.

## Step 6: Report success

Telegram-DM @adr2370:
```
✅ Pictionary biweekly run complete.
SHORTS: <N> posts → <accounts joined with comma>
VIDEO:  <M> posts → <accounts joined with comma>
Generator runtime: <duration_seconds / 60> minutes
Next run: <date of next 1st or 15th>
```

Update `pictionary-config.json`'s `last_successful_run` to the current ISO timestamp.

## Failure handling

On ANY error from any step:

1. Take a screenshot of whatever the browser is showing.
2. Capture the last ~50 lines of the runner log if Step 1 failed (it's at `log_path` from the response).
3. Write `failed.flag` in the workspace root with contents:
   ```
   step: <step name where it failed>
   time: <ISO timestamp>
   error: <short description>
   ```
4. Telegram-DM @adr2370:
   ```
   ❌ Pictionary biweekly failed at step "<step name>".
   Error: <error>
   Screenshot attached.
   Run is BLOCKED until failed.flag is cleared.
   ```
   Attach the screenshot.
5. Stop. Do not retry. Do not move to the next step.

## Hard rules

- Never call `/run-pictionary` more than once per invocation of this skill.
- Never edit any file in `bulk_upload_csvs/` — it's read-only anyway.
- Never re-trigger Telegram messages on retries (there are no retries).
- Never modify `main.py` or the host runner from inside the skill.
```

- [ ] **Step 3: Write `pictionary-config.json` (empty placeholder for now)**

```json
{
  "shorts_target_accounts": [],
  "video_target_accounts": [],
  "known_quirks": [],
  "last_successful_run": null
}
```

The first supervised run (Task 16) populates the account lists.

- [ ] **Step 4: Write `README.md`** in the same directory:

```markdown
# pictionary-biweekly skill

Runs Alex's biweekly Pictionary pipeline:
1. Calls the host runner (`host.docker.internal:18790`) to execute `main.py`.
2. Logs into Social Champ.
3. Reconnects all social accounts.
4. Bulk-uploads SHORTS and VIDEO CSVs to their respective account groups.
5. Reports via Telegram.

Spec: `ai_pictionary/docs/superpowers/specs/2026-04-12-pictionary-biweekly-openclaw-design.md`
```

- [ ] **Step 5: Write the skill files into the container**

Easiest method: write the three files locally in a tmp dir, then `docker cp` them in:

```bash
docker cp /tmp/SKILL.md openclaw:/home/node/.openclaw/workspace/.openclaw/skills/pictionary-biweekly/SKILL.md
docker cp /tmp/pictionary-config.json openclaw:/home/node/.openclaw/workspace/.openclaw/skills/pictionary-biweekly/pictionary-config.json
docker cp /tmp/README.md openclaw:/home/node/.openclaw/workspace/.openclaw/skills/pictionary-biweekly/README.md
```

OR (if simpler) write them through the host bind mount at `/home/adr2370/openclaw/workspace/.openclaw/skills/pictionary-biweekly/` directly via WSL.

- [ ] **Step 6: Verify the agent can see the skill**

In the OpenClaw Control UI, browse the agent's available skills. The new `pictionary-biweekly` skill should appear in the list. If it does not, check Task 1's notes — the discovery path may be different.

(No git commit — files live in the OpenClaw workspace volume, not in this repo.)

---

## Task 14: Add the cron entry (initially DISABLED)

We want the entry in place so the supervised first run can verify the wiring, but disabled so it doesn't auto-fire before we've confirmed everything works.

- [ ] **Step 1: Read the current `jobs.json`**

```bash
MSYS_NO_PATHCONV=1 docker exec openclaw sh -c "cat /home/node/.openclaw/cron/jobs.json"
```
Expected: `{"version": 1, "jobs": []}`.

- [ ] **Step 2: Write the new `jobs.json`** with the entry in place but `enabled: false`:

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
      "enabled": false
    }
  ]
}
```

Write it via the bind mount: edit `/home/adr2370/openclaw/config/cron/jobs.json` directly from WSL, OR use `docker cp` from a temp file.

- [ ] **Step 3: Verify openclaw picks up the new job**

In the OpenClaw Control UI, navigate to Cron / Jobs. The new entry should appear, marked disabled.

If the schema fields above are not what OpenClaw actually expects, the UI will show a validation error. Adjust the field names per what Task 1 discovered, then re-write.

- [ ] **Step 4: Reload openclaw if needed**

Some OpenClaw versions reload cron on file change; others require a SIGHUP or container restart. If the UI doesn't show the job:

```bash
docker restart openclaw
```

(No commit — OpenClaw config volume.)

---

## Task 15: Supervised first run

This is the human-in-the-loop step where you watch the agent work through Social Champ for the first time, capturing the account names into `pictionary-config.json`.

- [ ] **Step 1: Open the OpenClaw Control UI** at `http://localhost:18789`.

- [ ] **Step 2: Open a chat with the `main` agent** in the Control UI (so you can see what it's thinking and watch the browser tool).

- [ ] **Step 3: Send the agent a message**:

> Run the `pictionary-biweekly` skill manually. I'm watching. Walk me through each step out loud as you go. **Important:** in Step 1, do NOT call `/run-pictionary` yet — instead, manually use one of the existing CSV files in `/home/node/uploads/` for testing the upload flow. Once we know the upload flow works end-to-end, we'll run the real generator.

The agent should:
1. Check for `failed.flag` (none → proceed).
2. Skip the runner call (you told it to).
3. Open Social Champ, log in.
4. Walk through reconnecting accounts.
5. Walk through uploading the most recent SHORTS CSV from `/home/node/uploads/`.
6. Walk through uploading the most recent VIDEO CSV from `/home/node/uploads/`.

- [ ] **Step 4: As the agent works, capture which accounts get SHORTS vs VIDEO.**

Watch the browser tool's screenshots. Note the exact account names as they appear in the Social Champ UI. Tell the agent in chat:

> The SHORTS upload should target these accounts: <list>. The VIDEO upload should target these accounts: <list>. Update `pictionary-config.json` with both lists, then continue.

- [ ] **Step 5: Verify the success Telegram DM lands.**

After Step 6 of the skill, you should receive a Telegram DM from the OpenClaw bot. Check that it lands.

If anything fails: have the agent describe the failure in chat. Fix it (could be a SKILL.md ambiguity, a credentials issue, or a Social Champ UI surprise). Iterate until the full skill executes cleanly with the test CSVs.

- [ ] **Step 6: Run the REAL pipeline once, end-to-end.**

Once the test run is clean, send the agent:

> Run `pictionary-biweekly` for real now — call the runner. I'll wait.

This will take hours (main.py runs for a long time). Wait for the success DM.

- [ ] **Step 7: Verify the generator's CSVs were what got uploaded.**

Cross-check the timestamps in `bulk_upload_csvs/` against what Social Champ shows in its scheduled posts queue. The newest pair should be there.

(No commit — this is operational, not code.)

---

## Task 16: Enable the cron entry

After a clean end-to-end run, flip the cron job to enabled.

- [ ] **Step 1: Edit `/home/adr2370/openclaw/config/cron/jobs.json`** and change `"enabled": false` to `"enabled": true`.

- [ ] **Step 2: Verify in the Control UI** that the job is enabled and shows a "next fire" timestamp matching the next 1st or 15th of the month at 2 AM Pacific.

- [ ] **Step 3: If openclaw needs a kick:**

```bash
docker restart openclaw
```

- [ ] **Step 4: Done.** No more steps until the next 1st or 15th, when the cron fires unattended and you receive a Telegram DM.

---

## Task 17: Final smoke test and documentation update

- [ ] **Step 1: Run the runner test suite one more time** to make sure nothing's regressed:

```bash
cd /c/Users/adr23/Projects/ai_pictionary/runner && .venv/Scripts/pytest -v
```
Expected: all tests pass.

- [ ] **Step 2: Verify the runner is still running** as a Windows scheduled task:

```bash
curl http://127.0.0.1:18790/health
```
Expected: `{"ok":true}`.

- [ ] **Step 3: Verify openclaw can still reach it:**

```bash
MSYS_NO_PATHCONV=1 docker exec openclaw sh -c "wget -qO- http://host.docker.internal:18790/health"
```
Expected: `{"ok":true}`.

- [ ] **Step 4: Update the project README** at `ai_pictionary/README.md` with a small "Automation" section pointing at:
  - The spec: `docs/superpowers/specs/2026-04-12-pictionary-biweekly-openclaw-design.md`
  - The plan: `docs/superpowers/plans/2026-04-12-pictionary-biweekly-openclaw.md`
  - The runner: `runner/README.md`
  - "How to clear `failed.flag`" — one paragraph explaining what to do if the agent halts itself.

- [ ] **Step 5: Final commit**

```bash
git add README.md
git commit -m "docs: link to biweekly automation spec/plan/runner"
```

---

## Self-review

**Spec coverage check:**
- Goal (run unattended): ✓ Task 14 + 16 (cron enabled)
- main.py executed via host runner: ✓ Tasks 3–10 (runner) + Task 13 Step 1 (skill calls it)
- CSV bind mount visibility: ✓ Task 11
- SKILL.md procedural flow: ✓ Task 13
- Cron entry: ✓ Task 14 + 16
- Credentials: ✓ Task 12
- Failure handling (failed.flag, Telegram): ✓ Task 13's SKILL.md body
- Telegram on success AND failure: ✓ Task 13's Step 6 and Failure handling sections
- Supervised first run captures `pictionary-config.json`: ✓ Task 15
- Out-of-scope items NOT introduced (no API integration, no smart reconnect): ✓

**Placeholder scan:**
- Account name placeholders in `pictionary-config.json` are intentional and filled in Task 15. ✓
- Compose file path is "discovered in Task 2" before being touched in Task 11. ✓
- OpenClaw skill format is "discovered in Task 1" before being authored in Task 13. ✓
- No "TODO", "TBD", "fill in later", "implement later" in any task body. ✓

**Type / name consistency:**
- `RunnerConfig` fields used identically in `runner.py`, `runs.py`, and `tests/test_api.py`. ✓
- `host_to_openclaw(host_path, host_root, container_root)` signature consistent across `paths.py`, tests, and `runner.py`. ✓
- `RunResult` fields (`exit_code`, `shorts_csv`, `video_csv`, `log_path`, `duration_seconds`) consistent across `runs.py`, tests, and `runner.py`. ✓
- Skill name `pictionary-biweekly` consistent across SKILL.md frontmatter, cron `skill` field, and Task 15 invocation. ✓

No issues found. Plan is ready.
