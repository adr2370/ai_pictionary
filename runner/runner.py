import shutil
import sys
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, status

from runner.config import RunnerConfig, load_config
from runner.paths import host_to_openclaw
from runner.runs import RunInProgressError, Runner


def build_app(config_path: Path, python_executable: str = sys.executable) -> FastAPI:
    cfg: RunnerConfig = load_config(config_path)

    main_py_python = cfg.main_py_python or python_executable

    runner = Runner(
        ai_pictionary_dir=Path(cfg.ai_pictionary_dir),
        host_csv_dir=Path(cfg.host_csv_dir),
        log_dir=Path(cfg.log_dir),
        python_executable=main_py_python,
        main_py_args=cfg.main_py_args,
        main_py_env=cfg.main_py_env,
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

        wsl_dir = Path(cfg.wsl_csv_dir)
        wsl_dir.mkdir(parents=True, exist_ok=True)
        shorts_in_wsl = wsl_dir / result.shorts_csv.name
        video_in_wsl = wsl_dir / result.video_csv.name
        shutil.copy2(result.shorts_csv, shorts_in_wsl)
        shutil.copy2(result.video_csv, video_in_wsl)

        shorts_container = host_to_openclaw(
            host_path=str(shorts_in_wsl),
            host_root=cfg.wsl_csv_dir,
            container_root=cfg.openclaw_csv_dir,
        )
        video_container = host_to_openclaw(
            host_path=str(video_in_wsl),
            host_root=cfg.wsl_csv_dir,
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
