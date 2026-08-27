from __future__ import annotations

from pathlib import Path


def test_modal_resources_and_secrets_are_environment_scoped():
    source = Path("modal_service/app.py").read_text(encoding="utf-8")
    assert 'os.getenv("GRU_MASCOT_APP_NAME", "gru-mascot")' in source
    assert 'os.getenv("GRU_MASCOT_RESOURCE_PREFIX", "gru-mascot")' in source
    assert 'os.getenv("GRU_FIREBASE_SECRET_NAME", "gru-mascot-firebase-admin")' in source
    assert 'os.getenv("GRU_PULEIRO_BFF_SECRET_NAME", "gru-mascot-puleiro-bff")' in source
    assert 'modal.Volume.from_name(f"{RESOURCE_PREFIX}-assets"' in source
    assert 'modal.Dict.from_name(f"{RESOURCE_PREFIX}-jobs"' in source


def test_cost_bearing_staging_flags_still_fail_closed():
    source = Path("modal_service/app.py").read_text(encoding="utf-8")
    assert "MASTER_GENERATION_ENABLED = feature_enabled(os.getenv(\"MASTER_GENERATION_ENABLED\"))" in source
    assert "POSE_GENERATION_ENABLED = feature_enabled(os.getenv(\"POSE_GENERATION_ENABLED\"))" in source


def test_staging_deploy_has_explicit_fail_closed_master_and_poses_only_modes():
    source = Path("modal_service/deploy_v2_staging.ps1").read_text(encoding="utf-8")
    assert '[string]$Mode = "fail-closed"' in source
    assert '"fail-closed"' in source
    assert '"master-only"' in source
    assert '"poses-only"' in source
    assert '$env:GPU_GENERATION_ENABLED = "false"' in source
    assert '$env:MASTER_GENERATION_ENABLED = "false"' in source
    assert '$env:POSE_GENERATION_ENABLED = "false"' in source
    assert '$env:MASTER_GENERATION_ENABLED = "true"' in source
    assert '$env:POSE_GENERATION_ENABLED = "true"' in source


def test_bff_auth_contract_is_environment_configurable_and_capped():
    source = Path("modal_service/bff_auth.py").read_text(encoding="utf-8")
    assert 'os.getenv("PULEIRO_BFF_JWT_ISSUER", "puleiro-bff")' in source
    assert 'os.getenv("PULEIRO_BFF_JWT_AUDIENCE", "gru-modal")' in source
    assert "min(int(os.getenv" in source and ", 120)" in source


def test_template_installer_is_explicitly_staging_scoped_and_refuses_production_prefix():
    installer = Path("modal_service/tools/install_pose_templates.py").read_text(encoding="utf-8")
    staging = Path("modal_service/install_pose_templates_staging.ps1").read_text(encoding="utf-8")

    assert 'args.resource_prefix == "gru-mascot"' in installer
    assert 'args.environment == "main"' in installer
    assert '"gru-mascot-v2-staging"' in staging
