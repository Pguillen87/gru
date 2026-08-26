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
    generation_enabled: bool = False


LIMITS = {
    Environment.DEVELOPMENT: RuntimeLimits(1, 1, 6, 30.00, 1.00, 900, 100, 30, 100, 30.00, False),
    Environment.STAGING: RuntimeLimits(1, 1, 6, 10.0, 0.20, 600, 10, 3, 50, 0.60, False),
    Environment.PRODUCTION: RuntimeLimits(2, 2, 6, 100.0, 0.20, 600, 20, 5, 1_000, 1.00, False),
}


def limits_for(value: str) -> RuntimeLimits:
    return LIMITS[Environment(value)]


def generation_enabled(environment: Environment, override: str | None = None) -> bool:
    if override is None:
        return LIMITS[environment].generation_enabled
    return override.strip().lower() == "true"


def feature_enabled(override: str | None, *, default: bool = False) -> bool:
    """Parse an explicit feature switch; cost-bearing switches fail closed."""
    if override is None:
        return default
    return override.strip().lower() == "true"
