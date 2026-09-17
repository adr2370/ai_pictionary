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
        "wsl_csv_dir": str(tmp_path / "wsl_uploads"),
        "openclaw_csv_dir": "/home/node/uploads",
        "log_dir": str(tmp_path / "logs"),
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg))
    Path(cfg["ai_pictionary_dir"]).mkdir(parents=True, exist_ok=True)
    Path(cfg["host_csv_dir"]).mkdir(parents=True, exist_ok=True)
    Path(cfg["wsl_csv_dir"]).mkdir(parents=True, exist_ok=True)
    Path(cfg["log_dir"]).mkdir(parents=True, exist_ok=True)
    return cfg_path
