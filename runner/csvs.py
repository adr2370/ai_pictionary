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
