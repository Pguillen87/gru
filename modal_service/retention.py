"""Small, deterministic retention helpers for sensitive source uploads."""

from __future__ import annotations

import shutil
import time
from pathlib import Path


SOURCE_RETENTION_SECONDS = 72 * 60 * 60
TEMPORARY_RETENTION_SECONDS = 72 * 60 * 60


def purge_expired_originals(root: Path, *, now: float | None = None) -> int:
    """Delete only source files older than the bounded retry window."""
    cutoff = (time.time() if now is None else now) - SOURCE_RETENTION_SECONDS
    deleted = 0
    for path in root.glob("original/*/source.bin"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
                shutil.rmtree(path.parent, ignore_errors=True)
                deleted += 1
        except OSError:
            continue
    return deleted


def purge_expired_temporary_assets(root: Path, *, now: float | None = None) -> int:
    cutoff = (time.time() if now is None else now) - TEMPORARY_RETENTION_SECONDS
    deleted = 0
    temporary = root / "temporary"
    if not temporary.is_dir():
        return 0
    for path in temporary.iterdir():
        try:
            if path.is_dir() and path.stat().st_mtime < cutoff:
                shutil.rmtree(path)
                deleted += 1
        except OSError:
            continue
    return deleted


def delete_job_assets(root: Path, job_id: str) -> int:
    deleted = 0
    for folder in ("original", "temporary", "masters", "poses", "consistency"):
        target = root / folder / job_id
        if target.exists():
            shutil.rmtree(target)
            deleted += 1
    return deleted
