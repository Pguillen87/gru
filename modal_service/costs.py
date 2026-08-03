"""Deterministic cost guard used before every chargeable generation."""

from __future__ import annotations


class CostLimitExceeded(ValueError):
    code = "COST_LIMIT_REACHED"


class RateLimitExceeded(ValueError):
    code = "RATE_LIMITED"


def can_reserve(current_usd: float, requested_usd: float, cap_usd: float) -> bool:
    return current_usd + requested_usd <= cap_usd


def require_reservation(current_usd: float, requested_usd: float, cap_usd: float) -> float:
    if not can_reserve(current_usd, requested_usd, cap_usd):
        raise CostLimitExceeded("Daily generation cost cap reached.")
    return round(current_usd + requested_usd, 4)


def require_job_quota(current_jobs: int, cap: int) -> int:
    if current_jobs >= cap:
        raise RateLimitExceeded("Daily job limit reached.")
    return current_jobs + 1
