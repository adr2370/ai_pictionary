import json
import sys

import pytest
from fastapi.testclient import TestClient

from runner.runner import build_app


@pytest.fixture
def client(tmp_path):
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

    wsl_dir = tmp_path / "wsl_uploads"
    wsl_dir.mkdir()

    cfg = {
        "host": "127.0.0.1",
        "port": 0,
        "token": "test-token-1234567890abcdef",
        "ai_pictionary_dir": str(workdir),
        "main_py_args": [],
        "host_csv_dir": str(csv_dir),
        "wsl_csv_dir": str(wsl_dir),
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


def test_run_succeeds_with_correct_token(client, tmp_path):
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

    # Verify the CSVs were actually copied into the WSL staging dir
    wsl_dir = tmp_path / "wsl_uploads"
    assert (wsl_dir / "ai_pictionary_bulk_upload_SHORTS_20260426_020000.csv").exists()
    assert (wsl_dir / "ai_pictionary_bulk_upload_VIDEO_20260426_020000.csv").exists()
