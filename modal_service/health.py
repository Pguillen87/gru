"""Pure health payload helpers for the GRU Mascot service."""

from __future__ import annotations

from datetime import UTC, datetime


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def generation_ready(*, generation_enabled: bool, templates_installed: bool, model_configured: bool) -> bool:
    """Return true only when a paid generation may be scheduled safely."""
    return generation_enabled and templates_installed and model_configured


def live_payload(service: str, environment: str) -> dict[str, object]:
    return {
        "status": "alive",
        "service": service,
        "environment": environment,
        "checked_at": timestamp(),
    }


def ready_payload(
    *,
    service: str,
    environment: str,
    model_configured: bool,
    dependency_checks: dict[str, object] | None = None,
) -> dict[str, object]:
    """API readiness is independent from the optional GPU generation feature."""
    checks: dict[str, object] = {"api": "healthy", "model_configuration": "healthy" if model_configured else "unhealthy"}
    checks.update(dependency_checks or {})
    ready = model_configured and all(value != "unhealthy" for value in checks.values())
    return {
        "status": "ready" if ready else "not_ready",
        "service": service,
        "environment": environment,
        "checks": checks,
        "checked_at": timestamp(),
    }


def generation_payload(
    *,
    service: str,
    environment: str,
    generation_enabled: bool,
    templates_installed: bool,
    model_configured: bool,
) -> dict[str, object]:
    master_ready = generation_enabled and model_configured
    poses_ready = generation_ready(
        generation_enabled=generation_enabled,
        templates_installed=templates_installed,
        model_configured=model_configured,
    )
    return {
        # The endpoint as a whole is ready only if both paid pipelines can
        # run. Consumers may however use the explicit child capabilities to
        # distinguish a master-only outage from a pose-template outage.
        "status": "ready" if poses_ready else "not_ready",
        "service": service,
        "environment": environment,
        # Kept at the top level during the migration from the original /health
        # contract so existing diagnostics do not have to infer nested checks.
        "generation_enabled": generation_enabled,
        "templates_installed": templates_installed,
        "model_configured": model_configured,
        "checks": {
            "generation_enabled": generation_enabled,
            "templates_installed": templates_installed,
            "model_configuration": "healthy" if model_configured else "unhealthy",
        },
        "capabilities": {
            "master": {"ready": master_ready},
            "poses": {"ready": poses_ready},
        },
        "checked_at": timestamp(),
    }
