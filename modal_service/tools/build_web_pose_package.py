"""Build the immutable web-poses-v1 package from the approved 4x3 sheet."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from modal_service.catalog import POSES, POSE_TEMPLATE_VERSION


def build(sheet_path: Path, output_root: Path) -> None:
    with Image.open(sheet_path) as source:
        sheet = source.convert("RGB")
    if sheet.width % 4 or sheet.height % 3:
        raise ValueError("The approved pose sheet must be a 4x3 grid.")
    output_root.mkdir(parents=True, exist_ok=True)
    references = output_root / "references"
    references.mkdir(exist_ok=True)
    cell_width, cell_height = sheet.width // 4, sheet.height // 3
    manifest_poses = []
    for index, pose in enumerate(POSES):
        row, column = divmod(index, 4)
        crop = sheet.crop((column * cell_width, row * cell_height, (column + 1) * cell_width, (row + 1) * cell_height))
        path = references / f"{pose.option_id}.png"
        crop.save(path, "PNG", optimize=True)
        content = path.read_bytes()
        manifest_poses.append({
            "role": pose.role, "option_id": pose.option_id, "template_id": pose.template_id,
            "name": pose.name, "reference": f"references/{path.name}", "instruction": pose.instruction,
            "version": POSE_TEMPLATE_VERSION, "sha256": hashlib.sha256(content).hexdigest(),
        })
    manifest = {"version": POSE_TEMPLATE_VERSION, "catalog_version": POSE_TEMPLATE_VERSION, "poses": manifest_poses}
    (output_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("sheet", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.sheet, args.output)
