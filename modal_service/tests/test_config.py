from modal_service.config import Environment, generation_enabled, limits_for


def test_generation_is_disabled_by_default_in_every_environment():
    assert all(not limits_for(environment).generation_enabled for environment in Environment)


def test_generation_requires_explicit_true_override():
    assert not generation_enabled(Environment.DEVELOPMENT)
    assert not generation_enabled(Environment.DEVELOPMENT, "false")
    assert generation_enabled(Environment.DEVELOPMENT, "true")


def test_first_smoke_guard_is_single_container_and_small_budget():
    limits = limits_for(Environment.DEVELOPMENT)
    assert limits.max_containers == 1
    assert limits.daily_cost_cap_usd <= 1.0
    assert limits.jobs_per_user_per_day == 5
    assert limits.generations_per_user_per_day == 1
    assert limits.global_jobs_per_day == 10
