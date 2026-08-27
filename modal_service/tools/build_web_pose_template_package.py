"""Build the immutable web-poses-v1 package from the repository-owned reference sheet.

This is a packaging tool, not an inference or GPU tool. It records the source
commit and checksums so the deployed package can be traced back to the exact
reviewed asset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from modal_service.catalog import POSE_REFERENCES, POSE_TEMPLATE_VERSION

SOURCE_COMMIT = "e0098b50fb27d8cf79a97d3b3ca9967f7e9e5f0a"
SOURCE_PATH = "public/assets/pose-reference-sheet.webp"


def build(source: Path, destination: Path) -> Path:
    """Split the 4×3 internal preview sheet into twelve immutable references."""
    with Image.open(source) as image:
        sheet = image.convert("RGBA")
    if sheet.width < 4 or sheet.height < 3:
        raise ValueError("The pose reference sheet is too small.")
    destination.mkdir(parents=True, exist_ok=True)
    cell_width, cell_height = sheet.width // 4, sheet.height // 3
    poses: list[dict[str, object]] = []
    for index, reference in enumerate(POSE_REFERENCES):
        row, column = divmod(index, 4)
        crop = sheet.crop((column * cell_width, row * cell_height, (column + 1) * cell_width, (row + 1) * cell_height))
        folder = destination / reference.option_id
        folder.mkdir(exist_ok=True)
        output = folder / "reference.png"
        crop.save(output, format="PNG", optimize=True)
        poses.append({
            "option_id": reference.option_id,
            "role": reference.role,
            "label": reference.label,
            "instruction": reference.instruction,
            "reference": f"{reference.option_id}/reference.png",
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        })
    manifest = {
        "version": POSE_TEMPLATE_VERSION,
        "catalog_version": POSE_TEMPLATE_VERSION,
        "asset_provenance": {
            "source_type": "internal_repository_asset",
            "repository": "Pguillen87/PuleiroGru",
            "commit": SOURCE_COMMIT,
            "source_path": SOURCE_PATH,
            "rights_basis": "Repository-authored asset committed by the repository owner; internal GRU pose-reference use only.",
        },
        "poses": poses,
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(build(args.source, args.destination))


if __name__ == "__main__":
    main()
