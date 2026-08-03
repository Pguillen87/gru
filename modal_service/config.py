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


LIMITS = {
    Environment.DEVELOPMENT: RuntimeLimits(1, 1, 6, 5.0, 0.20, 600),
    Environment.STAGING: RuntimeLimits(1, 1, 6, 10.0, 0.20, 600),
    Environment.PRODUCTION: RuntimeLimits(2, 2, 6, 100.0, 0.20, 600),
}


def limits_for(value: str) -> RuntimeLimits:
    return LIMITS[Environment(value)]
