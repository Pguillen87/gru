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

PRODUCTION_RESOURCE_PREFIX = "gru-mascot-v2-production"


def validate_install_target(*, resource_prefix: str, environment: str, allow_production: bool) -> None:
    if not environment:
        raise SystemExit("A Modal environment must be explicit.")
    if environment != "main":
        if allow_production:
            raise SystemExit("--allow-production is valid only for the Production target.")
        return
    if not allow_production or resource_prefix != PRODUCTION_RESOURCE_PREFIX:
        raise SystemExit("Production installation requires --allow-production and the exact Production resource prefix.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument(
        "--resource-prefix",
        default=os.getenv("GRU_MASCOT_RESOURCE_PREFIX", "gru-mascot"),
        help="Modal resource prefix for the explicitly selected environment.",
    )
    parser.add_argument(
        "--environment",
        default=os.getenv("GRU_MASCOT_MODAL_ENVIRONMENT", ""),
        help="Required Modal environment name. It must be explicit to avoid the CLI default environment.",
    )
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Allow installation only for gru-mascot-v2-production in the main environment.",
    )
    args = parser.parse_args()
    package = validate_template_package(args.package)
    validate_install_target(
        resource_prefix=args.resource_prefix,
        environment=args.environment,
        allow_production=args.allow_production,
    )
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
