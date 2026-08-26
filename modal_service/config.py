"""Configuration with explicit cost and runtime limits per environment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass(frozen=True)
class RuntimeLimits:
    max_containers: int
    max_retries_per_pose: int
    mvp_pose_count: int
    daily_cost_cap_usd: float
    estimated_generation_cost_usd: float
    model_timeout_seconds: int
    jobs_per_user_per_day: int
    generations_per_user_per_day: int
    global_jobs_per_day: int
    user_daily_cost_cap_usd: float
    global_requests_per_minute: int
    reads_per_user_per_minute: int
    writes_per_user_per_minute: int
    worker_lease_seconds: int
    estimated_gpu_hourly_usd: float
    generation_enabled: bool = False


LIMITS = {
    Environment.DEVELOPMENT: RuntimeLimits(1, 1, 6, 30.00, 1.00, 900, 100, 30, 100, 30.00, 120, 120, 12, 1_020, 0.0, False),
    Environment.STAGING: RuntimeLimits(1, 1, 6, 10.0, 0.20, 600, 10, 3, 50, 0.60, 120, 60, 6, 720, 0.0, False),
    # A controlled production rollout: one Master set per request, with a
    # hard daily reservation ceiling while the web flow is being validated.
    Environment.PRODUCTION: RuntimeLimits(1, 1, 3, 10.0, 1.00, 1_800, 10, 3, 10, 1.00, 120, 60, 6, 1_800, 0.0, False),
}


def limits_for(value: str) -> RuntimeLimits:
    return LIMITS[Environment(value)]


def required_environment(value: str | None) -> Environment:
    if value is None or not value.strip():
        raise RuntimeError("GRU_MASCOT_ENV must be explicitly configured for deployment.")
    try:
        return Environment(value.strip().lower())
    except ValueError as error:
        raise RuntimeError("GRU_MASCOT_ENV must be development, staging, or production.") from error


def generation_enabled(environment: Environment, override: str | None = None) -> bool:
    if override is None:
        return LIMITS[environment].generation_enabled
    return override.strip().lower() == "true"
