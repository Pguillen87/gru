from __future__ import annotations

from pathlib import Path


def test_production_deploy_script_is_cost_fail_closed_and_resource_scoped():
    source = Path("modal_service/deploy_v2_production_fail_closed.ps1").read_text(encoding="utf-8")

    assert '$env:GRU_MASCOT_APP_NAME = "gru-mascot-v2-production"' in source
    assert '$env:GRU_MASCOT_ENV = "production"' in source
    assert '$env:GRU_MASCOT_RESOURCE_PREFIX = "gru-mascot-v2-production"' in source
    assert '$env:GRU_PULEIRO_BFF_SECRET_NAME = "gru-mascot-v2-production-puleiro-bff"' in source
    assert '$env:GPU_GENERATION_ENABLED = "false"' in source
    assert '$env:MASTER_GENERATION_ENABLED = "false"' in source
    assert '$env:POSE_GENERATION_ENABLED = "false"' in source
    assert "modal deploy -m modal_service.app" in source
