from datetime import UTC, datetime

from modal_service.rate_limits import consume_limit


def test_fixed_window_limit_returns_retry_information():
    store = {}
    now = datetime(2026, 8, 24, 12, 0, 30, tzinfo=UTC)
    assert consume_limit(store, "write:user", 2, now=now).allowed
    assert consume_limit(store, "write:user", 2, now=now).allowed
    blocked = consume_limit(store, "write:user", 2, now=now)
    assert not blocked.allowed
    assert blocked.retry_after_seconds == 30
