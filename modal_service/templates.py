"""Validation for versioned, administrator-installed pose template packages."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from modal_service.validation import validate_image


class TemplatePackageError(ValueError):
    code = "INVALID_TEMPLATE_PACKAGE"


POSE_ID_PATTERN = re.compile(r"^pose_[0-9]{2}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ValidatedTemplatePackage:
    root: Path
    version: str
    manifest: dict[str, object]
    files: tuple[Path, ...]


def validate_template_package(root: Path) -> ValidatedTemplatePackage:
    root = root.resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise TemplatePackageError("manifest.json is required.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = str(manifest.get("version", "")).strip()
    poses = manifest.get("poses")
    if not version or not isinstance(poses, list) or not 6 <= len(poses) <= 20:
        raise TemplatePackageError("A version and 6 to 20 poses are required.")
    ids = [str(pose.get("pose_id", "")) for pose in poses if isinstance(pose, dict)]
    if len(ids) != len(poses) or len(set(ids)) != len(ids) or not all(POSE_ID_PATTERN.fullmatch(value) for value in ids):
        raise TemplatePackageError("Pose identifiers must be present and unique.")
    consistency = manifest.get("consistency_pose_ids")
    mvp = manifest.get("mvp_pose_ids")
    if not isinstance(consistency, list) or len(consistency) != 3 or not set(consistency).issubset(ids):
        raise TemplatePackageError("Exactly three valid consistency poses are required.")
    if not isinstance(mvp, list) or len(mvp) != 6 or not set(mvp).issubset(ids):
        raise TemplatePackageError("Exactly six valid MVP poses are required.")
    referenced = [manifest_path]
    for pose in poses:
        reference = _safe_reference(root, str(pose.get("reference", "")))
        name = str(pose.get("name", "")).strip()
        pose_version = str(pose.get("version", "")).strip()
        instruction = str(pose.get("instruction", "")).strip()
        expected_hash = str(pose.get("sha256", "")).lower()
        if not name or not pose_version or not instruction or not SHA256_PATTERN.fullmatch(expected_hash) or not reference.is_file():
            raise TemplatePackageError(f"Pose {pose.get('pose_id')} is incomplete.")
        content = reference.read_bytes()
        validate_image(content, None)
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise TemplatePackageError(f"Pose {pose.get('pose_id')} checksum does not match.")
        referenced.append(reference)
    return ValidatedTemplatePackage(root, version, manifest, tuple(referenced))


def _safe_reference(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if not relative or root not in candidate.parents:
        raise TemplatePackageError("Template references must stay inside the package.")
    return candidate
