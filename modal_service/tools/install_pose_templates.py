r"""Install a validated pose-template package without invoking a GPU.

Usage: python -m modal_service.tools.install_pose_templates C:\path\to\package
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import modal

from modal_service.templates import validate_template_package


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    package = validate_template_package(args.package)
    volume = modal.Volume.from_name("gru-mascot-assets", create_if_missing=False)
    remote_root = f"pose_templates/versions/{package.version}"
    with volume.batch_upload(force=True) as batch:
        for file in package.files:
            batch.put_file(file, f"{remote_root}/{file.relative_to(package.root).as_posix()}")
    with tempfile.TemporaryDirectory(prefix="gru-templates-") as temporary:
        active = Path(temporary, "active.json")
        active.write_text(json.dumps({"version": package.version}), encoding="utf-8")
        with volume.batch_upload(force=True) as batch:
            batch.put_file(active, "pose_templates/active.json")
    print(f"Installed pose template package {package.version}.")


if __name__ == "__main__":
    main()
