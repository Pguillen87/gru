"""Validation for versioned, administrator-installed pose template packages."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from modal_service.catalog import POSE_REFERENCES, POSE_TEMPLATE_VERSION
from modal_service.validation import validate_image


class TemplatePackageError(ValueError):
    code = "INVALID_TEMPLATE_PACKAGE"


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ValidatedTemplatePackage:
    root: Path
    version: str
    manifest: dict[str, object]
    files: tuple[Path, ...]

    def reference_for(self, option_id: str) -> Path:
        entry = next(item for item in self.manifest["poses"] if item["option_id"] == option_id)
        return self.root / str(entry["reference"])


def validate_template_package(root: Path) -> ValidatedTemplatePackage:
    root = root.resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise TemplatePackageError("manifest.json is required.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = str(manifest.get("version", "")).strip()
    catalog_version = str(manifest.get("catalog_version", "")).strip()
    poses = manifest.get("poses")
    if version != POSE_TEMPLATE_VERSION or catalog_version != POSE_TEMPLATE_VERSION or not isinstance(poses, list):
        raise TemplatePackageError("Template and catalog versions must match the published pose catalog.")
    expected = {reference.option_id: reference for reference in POSE_REFERENCES}
    supplied = {str(pose.get("option_id", "")): pose for pose in poses if isinstance(pose, dict)}
    if set(supplied) != set(expected) or len(supplied) != len(poses):
        raise TemplatePackageError("Exactly one reference for every published pose option is required.")
    _validate_provenance(manifest.get("asset_provenance"))
    referenced = [manifest_path]
    for option_id, expected_reference in expected.items():
        pose = supplied[option_id]
        reference = _safe_reference(root, str(pose.get("reference", "")))
        role = str(pose.get("role", "")).strip()
        label = str(pose.get("label", "")).strip()
        instruction = str(pose.get("instruction", "")).strip()
        expected_hash = str(pose.get("sha256", "")).lower()
        if (
            role != expected_reference.role
            or label != expected_reference.label
            or instruction != expected_reference.instruction
            or not SHA256_PATTERN.fullmatch(expected_hash)
            or not reference.is_file()
        ):
            raise TemplatePackageError(f"Pose reference {option_id} is incomplete or incompatible.")
        content = reference.read_bytes()
        validate_image(content, None)
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise TemplatePackageError(f"Pose {pose.get('pose_id')} checksum does not match.")
        referenced.append(reference)
    return ValidatedTemplatePackage(root, version, manifest, tuple(referenced))


def validate_active_template_package(asset_root: Path) -> ValidatedTemplatePackage:
    pointer = asset_root / "pose_templates" / "active.json"
    if not pointer.is_file():
        raise TemplatePackageError("No active pose template package is installed.")
    try:
        version = str(json.loads(pointer.read_text(encoding="utf-8"))["version"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise TemplatePackageError("The active pose template pointer is invalid.") from error
    return validate_template_package(asset_root / "pose_templates" / "versions" / version)


def _validate_provenance(value: object) -> None:
    if not isinstance(value, Mapping):
        raise TemplatePackageError("Asset provenance is required.")
    required = ("source_type", "repository", "commit", "source_path", "rights_basis")
    if any(not str(value.get(field, "")).strip() for field in required):
        raise TemplatePackageError("Asset provenance is incomplete.")


def _safe_reference(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if not relative or root not in candidate.parents:
        raise TemplatePackageError("Template references must stay inside the package.")
    return candidate
