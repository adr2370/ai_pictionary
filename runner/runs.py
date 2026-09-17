import os
import subprocess
import threading
from dataclasses import dataclass, field
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
        main_py_env: Optional[dict[str, str]] = None,
    ):
        self.ai_pictionary_dir = Path(ai_pictionary_dir)
        self.host_csv_dir = Path(host_csv_dir)
        self.log_dir = Path(log_dir)
        self.python_executable = python_executable
        self.main_py_args = list(main_py_args)
        self.main_py_env = dict(main_py_env or {})
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
            subprocess_env = {**os.environ, **self.main_py_env}
            with log_path.open("wb") as log_file:
                proc = subprocess.run(
                    cmd,
                    cwd=str(self.ai_pictionary_dir),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    env=subprocess_env,
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
