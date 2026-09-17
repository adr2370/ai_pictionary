import pytest

from runner.paths import host_to_openclaw


def test_translates_host_path_to_container_path():
    result = host_to_openclaw(
        host_path="C:/Users/adr23/Projects/ai_pictionary/bulk_upload_csvs/ai_pictionary_bulk_upload_SHORTS_20260426_020000.csv",
        host_root="C:/Users/adr23/Projects/ai_pictionary/bulk_upload_csvs",
        container_root="/home/node/uploads",
    )
    assert result == "/home/node/uploads/ai_pictionary_bulk_upload_SHORTS_20260426_020000.csv"


def test_handles_backslash_paths():
    result = host_to_openclaw(
        host_path=r"C:\Users\adr23\Projects\ai_pictionary\bulk_upload_csvs\foo.csv",
        host_root=r"C:\Users\adr23\Projects\ai_pictionary\bulk_upload_csvs",
        container_root="/home/node/uploads",
    )
    assert result == "/home/node/uploads/foo.csv"


def test_raises_when_path_outside_host_root():
    with pytest.raises(ValueError, match="not under host_root"):
        host_to_openclaw(
            host_path="C:/somewhere/else/file.csv",
            host_root="C:/Users/adr23/Projects/ai_pictionary/bulk_upload_csvs",
            container_root="/home/node/uploads",
        )
