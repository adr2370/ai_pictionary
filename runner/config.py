from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class RunnerConfig(BaseModel):
    host: str
    port: int
    token: str
    ai_pictionary_dir: str
    main_py_args: list[str]
    main_py_python: str | None = None
    main_py_env: dict[str, str] = Field(default_factory=dict)
    host_csv_dir: str
    wsl_csv_dir: str
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
