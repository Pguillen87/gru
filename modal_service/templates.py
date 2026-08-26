"""Validation for versioned, administrator-installed pose template packages."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from modal_service.catalog import POSE_CATALOG_VERSION, POSE_BY_OPTION
from modal_service.validation import validate_image


class TemplatePackageError(ValueError):
    code = "INVALID_TEMPLATE_PACKAGE"


POSE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


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
    if version != POSE_CATALOG_VERSION or not isinstance(poses, list) or len(poses) != len(POSE_BY_OPTION):
        raise TemplatePackageError("The immutable web-poses-v1 package with all 12 poses is required.")
    ids = [str(pose.get("option_id", "")) for pose in poses if isinstance(pose, dict)]
    if len(ids) != len(poses) or len(set(ids)) != len(ids) or not all(POSE_ID_PATTERN.fullmatch(value) for value in ids):
        raise TemplatePackageError("Pose identifiers must be present and unique.")
    if set(ids) != set(POSE_BY_OPTION):
        raise TemplatePackageError("Template options must exactly match the Web pose catalog.")
    referenced = [manifest_path]
    for pose in poses:
        reference = _safe_reference(root, str(pose.get("reference", "")))
        option_id = str(pose.get("option_id", ""))
        definition = POSE_BY_OPTION.get(option_id)
        role = str(pose.get("role", ""))
        template_id = str(pose.get("template_id", ""))
        name = str(pose.get("name", "")).strip()
        pose_version = str(pose.get("version", "")).strip()
        instruction = str(pose.get("instruction", "")).strip()
        expected_hash = str(pose.get("sha256", "")).lower()
        if (
            definition is None
            or role != definition.role
            or template_id != definition.template_id
            or not name
            or not VERSION_PATTERN.fullmatch(pose_version)
            or not instruction
            or not SHA256_PATTERN.fullmatch(expected_hash)
            or not reference.is_file()
        ):
            raise TemplatePackageError(f"Pose {option_id} is incomplete or incompatible.")
        content = reference.read_bytes()
        validate_image(content, None)
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise TemplatePackageError(f"Pose {option_id} checksum does not match.")
        referenced.append(reference)
    return ValidatedTemplatePackage(root, version, manifest, tuple(referenced))


def _safe_reference(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if not relative or root not in candidate.parents:
        raise TemplatePackageError("Template references must stay inside the package.")
    return candidate
