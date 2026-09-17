import time

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
