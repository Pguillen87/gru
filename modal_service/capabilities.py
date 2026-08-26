"""Truthful, versioned capability reporting for the private Web contract."""

from __future__ import annotations

from modal_service.catalog import (
    MASTER_PROMPT_VERSION,
    POSE_CATALOG,
    POSE_CATALOG_VERSION,
    POSE_PROMPT_VERSION,
    POSE_TEMPLATE_VERSION,
)


def capability_payload(
    *,
    generation_enabled: bool,
    model_configured: bool,
    templates_installed: bool,
    pose_worker_installed: bool,
) -> dict[str, object]:
    master_reasons = []
    if not generation_enabled:
        master_reasons.append("GENERATION_DISABLED")
    if not model_configured:
        master_reasons.append("MODEL_NOT_CONFIGURED")
    pose_reasons = list(master_reasons)
    if not templates_installed:
        pose_reasons.append("POSE_TEMPLATES_UNAVAILABLE")
    if not pose_worker_installed:
        pose_reasons.append("POSE_WORKER_UNAVAILABLE")
    return {
        "contractVersion": "v2",
        "master": {
            "ready": not master_reasons,
            "modelVersion": "Qwen-Image-Edit-2511",
            "promptVersion": MASTER_PROMPT_VERSION,
            "segmentationModel": "facebook/sam2.1-hiera-small",
            "reasons": master_reasons,
        },
        "poses": {
            "ready": not pose_reasons,
            "workerVersion": POSE_PROMPT_VERSION,
            "catalogVersion": POSE_CATALOG_VERSION,
            "templateVersion": POSE_TEMPLATE_VERSION,
            "reasons": pose_reasons,
        },
        "poseCatalog": POSE_CATALOG,
    }
