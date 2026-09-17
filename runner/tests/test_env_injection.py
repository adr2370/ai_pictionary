"""Verify that main_py_env vars reach the subprocess."""
import json
import sys

from fastapi.testclient import TestClient

from runner.runner import build_app


def test_main_py_env_reaches_subprocess(tmp_path):
    workdir = tmp_path / "ai_pictionary"
    workdir.mkdir()
    csv_dir = workdir / "bulk_upload_csvs"
    csv_dir.mkdir()
    wsl_dir = tmp_path / "wsl_uploads"
    wsl_dir.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    marker = tmp_path / "env_seen.txt"
    (workdir / "main.py").write_text(
        "import os, sys\n"
        f"open(r'{str(marker).replace(chr(92), '/')}', 'w').write(os.environ.get('PICTIONARY_TEST_MARKER', 'MISSING'))\n"
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
        "main_py_env": {"PICTIONARY_TEST_MARKER": "hello-from-config"},
        "host_csv_dir": str(csv_dir),
        "wsl_csv_dir": str(wsl_dir),
        "openclaw_csv_dir": "/home/node/uploads",
        "log_dir": str(log_dir),
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg))

    app = build_app(cfg_path, python_executable=sys.executable)
    client = TestClient(app)

    r = client.post(
        "/run-pictionary",
        headers={"Authorization": "Bearer test-token-1234567890abcdef"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert marker.read_text() == "hello-from-config"
