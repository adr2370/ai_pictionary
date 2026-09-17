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
        "wsl_csv_dir": str(tmp_path),
        "openclaw_csv_dir": "/home/node/uploads",
        "log_dir": str(tmp_path),
    }
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="placeholder"):
        load_config(p)
