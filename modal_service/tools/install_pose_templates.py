r"""Install a validated pose-template package without invoking a GPU.

Usage: python -m modal_service.tools.install_pose_templates C:\path\to\package
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

import modal

from modal_service.templates import validate_template_package


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument(
        "--resource-prefix",
        default=os.getenv("GRU_MASCOT_RESOURCE_PREFIX", "gru-mascot"),
        help="Modal resource prefix. The staging deploy uses gru-mascot-v2-staging.",
    )
    parser.add_argument(
        "--environment",
        default=os.getenv("GRU_MASCOT_MODAL_ENVIRONMENT", ""),
        help="Required Modal environment name. It must be explicit to avoid the CLI default environment.",
    )
    args = parser.parse_args()
    package = validate_template_package(args.package)
    if args.resource_prefix == "gru-mascot":
        raise SystemExit("Refusing the production resource prefix. Pass an explicit non-production prefix.")
    if not args.environment or args.environment == "main":
        raise SystemExit("Refusing an implicit or production Modal environment.")
    volume = modal.Volume.from_name(
        f"{args.resource_prefix}-assets",
        environment_name=args.environment,
        create_if_missing=False,
    )
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
