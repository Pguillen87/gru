"""Versioned, rollback-friendly model cache metadata for the Qwen worker."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = 1
MANIFESTS_FOLDER = "manifests"
ACTIVE_POINTER = "active.json"
READY_MARKER = "READY"


class ModelCacheNotReady(RuntimeError):
    code = "MODEL_CACHE_NOT_READY"


@dataclass(frozen=True)
class ModelCacheSpec:
    model_id: str
    model_revision: str
    lora_id: str
    lora_revision: str
    lora_weight: str

    @property
    def cache_revision(self) -> str:
        identity = "\0".join(asdict(self).values())
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class CachedFile:
    path: str
    size: int


@dataclass(frozen=True)
class ActiveModelCache:
    cache_revision: str
    model_snapshot: Path
    lora_file: Path
    expected_size: int
    expected_files: tuple[CachedFile, ...]


def prepare_model_cache(
    root: Path,
    spec: ModelCacheSpec,
    *,
    snapshot_download: Callable[..., str],
    hf_hub_download: Callable[..., str],
) -> ActiveModelCache:
    """Download pinned artifacts administratively, validate them, then activate atomically."""
    root.mkdir(parents=True, exist_ok=True)
    model_snapshot = Path(
        snapshot_download(
            repo_id=spec.model_id,
            revision=spec.model_revision,
            cache_dir=str(root),
        )
    ).resolve()
    lora_file = Path(
        hf_hub_download(
            repo_id=spec.lora_id,
            filename=spec.lora_weight,
            revision=spec.lora_revision,
            cache_dir=str(root),
        )
    ).resolve()
    files = _inventory(root, model_snapshot, lora_file)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "cache_status": "complete",
        "cache_revision": spec.cache_revision,
        "cache_created_at": datetime.now(UTC).isoformat(),
        "model_id": spec.model_id,
        "model_revision": spec.model_revision,
        "lora_id": spec.lora_id,
        "lora_revision": spec.lora_revision,
        "lora_weight": spec.lora_weight,
        "model_snapshot": _relative(root, model_snapshot),
        "lora_file": _relative(root, lora_file),
        "expected_size": sum(item.size for item in files),
        "expected_files": [asdict(item) for item in files],
    }
    manifests = root / MANIFESTS_FOLDER
    manifests.mkdir(parents=True, exist_ok=True)
    _atomic_json(manifests / f"{spec.cache_revision}.json", manifest)
    _activate(root, spec.cache_revision)
    return validate_active_cache(root, spec)


def validate_active_cache(root: Path, spec: ModelCacheSpec) -> ActiveModelCache:
    try:
        pointer = _read_json(root / ACTIVE_POINTER)
        revision = str(pointer["cache_revision"])
        if revision != spec.cache_revision:
            raise ModelCacheNotReady(
                "The active model cache revision does not match this deployment."
            )
        if (root / READY_MARKER).read_text(encoding="utf-8").strip() != revision:
            raise ModelCacheNotReady(
                "The model cache ready marker is missing or stale."
            )
        manifest = _read_json(root / MANIFESTS_FOLDER / f"{revision}.json")
        _validate_manifest_identity(manifest, spec)
        files = tuple(
            CachedFile(str(item["path"]), int(item["size"]))
            for item in manifest["expected_files"]
        )
        if not files:
            raise ModelCacheNotReady("The model cache manifest has no files.")
        for item in files:
            candidate = _resolve_inside(root, item.path)
            if not candidate.is_file() or candidate.stat().st_size != item.size:
                raise ModelCacheNotReady("The model cache is incomplete or corrupt.")
        model_snapshot = _resolve_inside(root, str(manifest["model_snapshot"]))
        lora_file = _resolve_inside(root, str(manifest["lora_file"]))
        if not model_snapshot.is_dir() or not lora_file.is_file():
            raise ModelCacheNotReady("The model cache entry points are unavailable.")
        return ActiveModelCache(
            cache_revision=revision,
            model_snapshot=model_snapshot,
            lora_file=lora_file,
            expected_size=int(manifest["expected_size"]),
            expected_files=files,
        )
    except ModelCacheNotReady:
        raise
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
        raise ModelCacheNotReady("The model cache manifest is invalid.") from error


def activate_cached_revision(root: Path, revision: str) -> None:
    """Move the active pointer without deleting previous cache revisions."""
    if not revision or any(
        character not in "0123456789abcdef" for character in revision
    ):
        raise ModelCacheNotReady("The cache revision is invalid.")
    manifest = root / MANIFESTS_FOLDER / f"{revision}.json"
    if not manifest.is_file():
        raise ModelCacheNotReady("The requested cache revision does not exist.")
    _activate(root, revision)


def _validate_manifest_identity(manifest: dict[str, Any], spec: ModelCacheSpec) -> None:
    expected = {
        "schema_version": SCHEMA_VERSION,
        "cache_status": "complete",
        "cache_revision": spec.cache_revision,
        "model_id": spec.model_id,
        "model_revision": spec.model_revision,
        "lora_id": spec.lora_id,
        "lora_revision": spec.lora_revision,
        "lora_weight": spec.lora_weight,
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ModelCacheNotReady(
            "The model cache manifest does not match this deployment."
        )


def _inventory(
    root: Path, model_snapshot: Path, lora_file: Path
) -> tuple[CachedFile, ...]:
    candidates = [path for path in model_snapshot.rglob("*") if path.is_file()]
    if lora_file not in candidates:
        candidates.append(lora_file)
    if not candidates:
        raise ModelCacheNotReady("No model artifacts were downloaded.")
    unique_files: dict[str, CachedFile] = {}
    for path in candidates:
        relative = _relative(root, path)
        unique_files[relative] = CachedFile(relative, path.stat().st_size)
    return tuple(sorted(unique_files.values(), key=lambda item: item.path))


def _activate(root: Path, revision: str) -> None:
    _atomic_json(
        root / ACTIVE_POINTER,
        {"schema_version": SCHEMA_VERSION, "cache_revision": revision},
    )
    _atomic_text(root / READY_MARKER, revision)


def _read_json(path: Path) -> dict[str, Any]:
    return dict(json.loads(path.read_text(encoding="utf-8")))


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    _atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise ModelCacheNotReady(
            "A model cache artifact is outside the cache root."
        ) from error


def _resolve_inside(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ModelCacheNotReady("The model cache contains an unsafe path.")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise ModelCacheNotReady("The model cache contains an unsafe path.") from error
    return candidate
