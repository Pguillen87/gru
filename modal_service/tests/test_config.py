from modal_service.config import Environment, generation_enabled, limits_for
from modal_service.app import (
    MASTER_SEEDS,
    PERSISTENT_WORKER_MAX_CONTAINERS,
    WORKER_SCALEDOWN_SECONDS,
    inference_config_hash,
)


def test_generation_is_disabled_by_default_in_every_environment():
    assert all(not limits_for(environment).generation_enabled for environment in Environment)


def test_generation_requires_explicit_true_override():
    assert not generation_enabled(Environment.DEVELOPMENT)
    assert not generation_enabled(Environment.DEVELOPMENT, "false")
    assert generation_enabled(Environment.DEVELOPMENT, "true")


def test_development_guard_is_single_container_with_workspace_credit_ceiling():
    limits = limits_for(Environment.DEVELOPMENT)
    assert limits.max_containers == 1
    assert limits.daily_cost_cap_usd == 30.0
    assert limits.jobs_per_user_per_day == 100
    assert limits.generations_per_user_per_day == 30
    assert limits.global_jobs_per_day == 100


def test_persistent_worker_preserves_approved_generation_identity():
    assert MASTER_SEEDS == (0, 1, 2)
    assert PERSISTENT_WORKER_MAX_CONTAINERS == 1
    assert WORKER_SCALEDOWN_SECONDS == 45
    assert inference_config_hash() == "9aa836a88e56ec34"
