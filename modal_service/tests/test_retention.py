from pathlib import Path

from modal_service.retention import SOURCE_RETENTION_SECONDS, delete_job_assets, purge_expired_originals, purge_expired_temporary_assets


def test_purge_deletes_only_expired_source_uploads(tmp_path: Path):
    old_source = tmp_path / "original" / "old" / "source.bin"
    current_source = tmp_path / "original" / "current" / "source.bin"
    result = tmp_path / "masters" / "old" / "master_1.png"
    for path in (old_source, current_source, result):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"content")
    now = 1_000_000.0
    old_source.touch()
    import os
    os.utime(old_source, (now - SOURCE_RETENTION_SECONDS - 1, now - SOURCE_RETENTION_SECONDS - 1))
    os.utime(current_source, (now - 10, now - 10))

    assert purge_expired_originals(tmp_path, now=now) == 1
    assert not old_source.exists()
    assert current_source.exists()
    assert result.exists()


def test_temporary_assets_expire_but_private_results_remain(tmp_path: Path):
    temporary = tmp_path / "temporary" / "job_old" / "masters"
    result = tmp_path / "poses" / "job_old" / "pose_01.png"
    temporary.mkdir(parents=True)
    result.parent.mkdir(parents=True)
    result.write_bytes(b"result")
    import os
    os.utime(temporary.parent, (0, 0))
    assert purge_expired_temporary_assets(tmp_path, now=SOURCE_RETENTION_SECONDS + 1) == 1
    assert not temporary.exists()
    assert result.exists()


def test_job_asset_deletion_is_idempotent(tmp_path: Path):
    for folder in ("original", "temporary", "masters", "poses", "consistency"):
        target = tmp_path / folder / "job_123" / "asset.bin"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"private")
    assert delete_job_assets(tmp_path, "job_123") == 5
    assert delete_job_assets(tmp_path, "job_123") == 0
