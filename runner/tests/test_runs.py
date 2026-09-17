import sys

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
        "import sys\n"
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


def test_concurrent_run_raises(runner_for_test):
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
